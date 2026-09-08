import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import AgentRun, Config, Record, Session, User, uid, engine
from app.autonomous import process_agent_run, queue_due, recover_interrupted
from app.agent_evidence import parse_gateway

@pytest.fixture
def client():
    with TestClient(app) as c:
        with Session() as db:
            config=db.get(Config,'mcp')
            before=(dict(config.data),config.secret) if config else None
        try: yield c
        finally:
            with Session() as db:
                config=db.get(Config,'mcp')
                if before:
                    config.data,config.secret=before
                elif config:db.delete(config)
                db.commit()

def role(c,name='Buyer'): assert c.post('/api/v1/auth/demo',json={'role':name}).status_code==200

def post(c,path,body):
    response=c.post('/api/v1/'+path,json=body)
    assert response.status_code==200,response.text
    return response.json()

def category():
    with Session() as db:
        r=Record(kind='category',owner='Buyer',region='Region 1',data={'name':'Agent test category'});db.add(r);db.commit();return r.id

def source(cat,kind='supplier',**extra):
    with Session() as db:
        r=Record(kind=kind,owner='Buyer',region='Region 1',data={'name':'Source for agent','category_id':cat,**extra});db.add(r);db.commit();return r.id

def signal(c,cat,metric,values=None,**extra):
    units={'demand_quantity':'MT','inventory_coverage':'months','supplier_lead_time':'weeks','po_open_value':'currency','po_overdue_count':'orders'}
    r=post(c,'agents/signals',{'name':metric+' sourced series','category_id':cat,'metric':metric,'unit':units[metric],'currency':'USD' if metric=='po_open_value' else '', 'scope':'OCTG supply plan','source':'Organization planning team',**extra})
    if values is not None:post(c,'agents/signals/'+r['id']+'/observations',{'observations':[{'date':(date.today()-timedelta(days=2-i)).isoformat(),'value':v} for i,v in enumerate(values)]})
    return r['id']

def agent(c,cat=None,**extra):
    role(c);return post(c,'agents',{'name':'Category autonomous watch','category_id':cat or category(),**extra})

def run(c,a):
    r=post(c,'agents/'+a['id']+'/run',{});asyncio.run(process_agent_run())
    response=c.get('/api/v1/agents/'+a['id']+'/runs/'+r['id']);assert response.status_code==200,response.text
    result=response.json();assert result['status'] in ('PARTIAL','COMPLETED'),result
    return result

def core(c):
    role(c);cat=category();ids={m:signal(c,cat,m,v) for m,v in [('demand_quantity',[100,100]),('inventory_coverage',[4,4]),('supplier_lead_time',[8,8])]}
    return agent(c,cat,signal_ids=list(ids.values())),ids

def change(c,id,value,day=None,replace=False):return post(c,'agents/signals/'+id+'/observations',{'observations':[{'date':day or date.today().isoformat(),'value':value}],'replace_existing':replace})

def test_initial_baseline_compound_risk_and_dedup(client):
    a,ids=core(client);first=run(client,a)
    assert first['result']['initial_baseline'] and first['result']['risk']['level']=='MEDIUM'
    assert first['result']['material_changes']==0 and first['result']['alert_id'] is None
    change(client,ids['demand_quantity'],118);change(client,ids['inventory_coverage'],2.3);change(client,ids['supplier_lead_time'],10)
    second=run(client,a);r=second['result']
    assert r['previous_risk']=='MEDIUM' and r['risk']['level']=='HIGH'
    assert '+18.00%' in r['summary'] and '+25.00%' in r['summary'] and '2.3' in r['summary']
    assert r['material_changes']==3 and r['alert_id']
    third=run(client,a)
    assert third['result']['risk']['level']=='HIGH' and third['result']['material_changes']==0 and third['result']['alert_id'] is None
    alerts=[r for r in client.get('/api/v1/agents/inbox/alerts').json() if r['agent_id']==a['id']]
    assert len(alerts)==1 and alerts[0]['channel']=='in_app'

def test_missing_sources_not_zero_or_low_risk(client):
    a=agent(client);r=run(client,a)
    assert r['result']['risk']['level']=='UNKNOWN' and not r['result']['risk']['complete']
    assert all(c['state']=='MISSING' for c in r['snapshot']['coverage'].values())
    assert not r['snapshot']['metrics'] and not r['result']['changes']

def test_signal_validation_atomic_import_and_corrections(client):
    role(client);cat=category();id=signal(client,cat,'po_overdue_count',[1,2])
    for value in [-1,1.5]:assert client.post('/api/v1/agents/signals/'+id+'/observations',json={'observations':[{'date':date.today().isoformat(),'value':value}]}).status_code==422
    assert client.post('/api/v1/agents/signals/'+id+'/import',files={'file':('bad.csv',b'date,value\n2025-01-01,3\n2025-02-01,not-a-number\n')}).status_code==422
    good=client.post('/api/v1/agents/signals/'+id+'/import',files={'file':('good.csv',b'date,value,source\n2025-01-01,3,Procurement ledger\n')});assert good.status_code==200,good.text
    assert client.post('/api/v1/agents/signals/'+id+'/observations',json={'observations':[{'date':'2025-01-01','value':5}]}).status_code==409
    change(client,id,5,'2025-01-01',True)
    role(client,'Admin');assert client.get('/api/v1/agents/signals').status_code==403

def test_stale_and_low_confidence_not_used_as_improvement(client):
    a,ids=core(client);run(client,a)
    with Session() as db:
        from app.db import MarketPoint
        for row in db.scalars(select(MarketPoint).where(MarketPoint.series_id==ids['inventory_coverage'])):row.confidence=0
        db.commit()
    result=run(client,a)
    assert result['snapshot']['coverage']['Inventory']['state']=='DEGRADED'
    assert not any(s['metric']=='inventory_coverage' for s in result['result']['risk']['signals'])
    assert result['result']['risk']['level']!='LOW'
    with Session() as db:
        for p in db.scalars(select(MarketPoint).where(MarketPoint.series_id==ids['demand_quantity'])):p.observed_on=(date.fromisoformat(p.observed_on)-timedelta(days=200)).isoformat()
        db.commit()
    stale=run(client,a);assert stale['snapshot']['coverage']['Demand']['state']=='DEGRADED'
    assert not any(c['type']=='VALUE_CHANGED' and c['key']==ids['demand_quantity'] and c['material'] for c in stale['result']['changes'])

def test_rfi_supplier_market_event_document_changes(client):
    a=agent(client);cat=a['category_id'];s=source(cat,landscape='Leader');rfi=source(cat,'rfi',title='Category RFI',status='Open',version=1)
    doc=source(cat,'document',status='Indexed',text='Initial supplier evidence');event=source(cat,'event',title='Plant maintenance',description='Planned availability change',date=date.today().isoformat())
    role(client,'Market Intelligence Analyst');price=post(client,'market/series',{'name':'Sourced benchmark','category_id':cat,'commodity':'Steel','geography':'Indonesia','currency':'USD','unit':'MT','source':'Market publication'})
    post(client,'market/series/'+price['id']+'/observations',{'observations':[{'date':date.today().isoformat(),'value':100}]})
    role(client);base=run(client,a)
    for domain in ['RFI','Supplier Data','Market Data','Market Events','Price']:assert base['snapshot']['coverage'][domain]['state']=='AVAILABLE'
    with Session() as db:
        for id,extra in [(s,{'landscape':'Challenger'}),(rfi,{'status':'Response Received'}),(doc,{'text':'Updated supplier evidence'}),(event,{'description':'Confirmed delayed supply'})]:
            row=db.get(Record,id);row.data={**row.data,**extra};db.commit()
    result=run(client,a);assert {c['key'] for c in result['result']['changes']}=={s,rfi,doc,event}
    assert all(c['before']['content_checksum']!=c['after']['content_checksum'] for c in result['result']['changes'])

def test_sharing_owner_control_review_and_revocation(client):
    a,ids=core(client);run(client,a);change(client,ids['demand_quantity'],120);r=run(client,a);alert=r['result']['alert_id']
    assert client.put('/api/v1/agents/'+a['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    role(client,'Market Intelligence Analyst');assert a['id'] in [x['id'] for x in client.get('/api/v1/agents').json()]
    assert client.post('/api/v1/agents/'+a['id']+'/run',json={}).status_code==403
    assert client.get('/api/v1/agents/'+a['id']+'/runs/'+r['id']).json()['evidence_available']
    assert client.put('/api/v1/agents/inbox/alerts/'+alert,json={'status':'ACKNOWLEDGED','note':'Checked operational inputs.'}).status_code==200
    role(client);assert client.put('/api/v1/agents/'+a['id']+'/sharing',json={'user_ids':[]}).status_code==200
    role(client,'Market Intelligence Analyst');assert client.get('/api/v1/agents/'+a['id']+'/runs').status_code==404
    assert alert not in [x['id'] for x in client.get('/api/v1/agents/inbox/alerts').json()]

def test_restricted_evidence_never_leaks_through_shared_runs(client):
    a,ids=core(client)
    with Session() as db:r=db.get(Record,ids['demand_quantity']);r.classification='RESTRICTED';db.commit()
    run(client,a);assert client.put('/api/v1/agents/'+a['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==404
    with Session() as db:r=db.get(Record,ids['demand_quantity']);r.classification='CONFIDENTIAL';db.commit()
    assert client.put('/api/v1/agents/'+a['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    result=run(client,a)
    with Session() as db:r=db.get(Record,ids['demand_quantity']);r.classification='RESTRICTED';db.commit()
    role(client,'Market Intelligence Analyst');response=client.get('/api/v1/agents/'+a['id']+'/runs/'+result['id']).json()
    assert not response['evidence_available'] and 'snapshot' not in response and 'result' not in response

def test_config_revision_resets_baseline_cancels_work(client):
    a,ids=core(client);run(client,a);queued=post(client,'agents/'+a['id']+'/run',{})
    body={k:a[k] for k in ['name','category_id','signal_ids','interval_minutes','max_source_age_days','runtime_seconds','use_mcp','include_demo','enabled','policy','version']}
    response=client.put('/api/v1/agents/'+a['id'],json={**body,'name':'Updated monitoring policy'})
    assert response.status_code==200 and response.json()['version']==2
    assert client.put('/api/v1/agents/'+a['id'],json=body).status_code==409
    with Session() as db:assert db.get(AgentRun,queued['id']).status=='CANCELLED'
    r=run(client,response.json());assert r['result']['initial_baseline'] and r['result']['alert_id'] is None

def test_pause_admin_stop_prevent_publishing(client):
    a=agent(client);queued=post(client,'agents/'+a['id']+'/run',{});post(client,'agents/'+a['id']+'/toggle',{'enabled':False})
    with Session() as db:assert db.get(AgentRun,queued['id']).status=='CANCELLED'
    post(client,'agents/'+a['id']+'/run',{});role(client,'Admin');assert client.get('/api/v1/agents').status_code==403
    assert client.put('/api/v1/agents/control/status',json={'enabled':False}).status_code==200
    role(client);assert client.post('/api/v1/agents/'+a['id']+'/run',json={}).status_code==409
    with Session() as db:assert not list(db.scalars(select(AgentRun).where(AgentRun.agent_id==a['id'],AgentRun.status.in_(['PENDING','RUNNING']))))
    role(client,'Admin');assert client.put('/api/v1/agents/control/status',json={'enabled':True}).status_code==200

def mcp_enabled(monkeypatch):
    monkeypatch.setenv('MCP_ALLOWED_HOSTS','mcp.example.test')
    with Session() as db:
        row=db.get(Config,'mcp') or Config(id='mcp',data={})
        row.data={'enabled':True,'endpoint':'https://mcp.example.test/mcp'};row.secret=None;db.add(row);db.commit()

def gateway(cat,metric='demand_quantity',value=100,days=1,**extra):
    units={'demand_quantity':'MT','inventory_coverage':'months','supplier_lead_time':'weeks','po_open_value':'currency','po_overdue_count':'orders'}
    return {'structuredContent':{'category_id':cat,'region':'Region 1','observations':[{'key':metric,'metric':metric,'value':value,'as_of':(date.today()-timedelta(days=days)).isoformat(),'unit':units[metric],'currency':'USD' if metric=='po_open_value' else '', 'scope':'OCTG supply plan','source':'Enterprise planning system',**extra}]}}

def test_gateway_rejects_wrong_scope_metric_units_and_dates():
    from fastapi import HTTPException
    good=gateway('category');assert parse_gateway(good,'get_demand_history','category','Region 1')[0].value==100
    invalid=[gateway('wrong'),gateway('category',unit='MT',metric='inventory_coverage'),gateway('category',days=-1),gateway('category',previous_value=90),gateway('category',previous_value=90,previous_as_of=date.today().isoformat())]
    wrong_region=gateway('category');wrong_region['structuredContent']['region']='Region 2';invalid.append(wrong_region)
    for data in invalid:
        with pytest.raises(HTTPException) as error:parse_gateway(data,'get_demand_history','category','Region 1')
        assert error.value.status_code==502
    with pytest.raises(HTTPException):parse_gateway(gateway('category',metric='po_overdue_count',value=1.5),'get_open_purchase_orders','category','Region 1')

def test_mcp_outage_recovery_preserves_baseline_and_stable_risk(client,monkeypatch):
    from fastapi import HTTPException
    mcp_enabled(monkeypatch);a=agent(client,use_mcp=True);state={'value':100,'days':1,'outage':False};calls=[]
    async def fake(db,user,tool,params,correlation,**kwargs):
        assert params=={'category':a['category_id']} and kwargs['max_response_bytes']==2*1024*1024
        calls.append(tool)
        if tool!='get_demand_history' or state['outage']:raise HTTPException(502,'Unavailable')
        return gateway(a['category_id'],value=state['value'],days=state['days'])
    monkeypatch.setattr('app.agent_evidence.mcp_call',fake)
    base=run(client,a);assert base['snapshot']['coverage']['Demand']['state']=='AVAILABLE'
    state['outage']=True;failed_source=run(client,a)
    assert failed_source['snapshot']['coverage']['Demand']['state']=='DEGRADED'
    assert not any(c['type']=='VALUE_CHANGED' for c in failed_source['result']['changes'])
    state.update(outage=False,value=118,days=0);recovered=run(client,a)
    change=next(c for c in recovered['result']['changes'] if c['type']=='VALUE_CHANGED')
    assert change['before']==100 and change['after']==118 and change['pct']==18
    assert recovered['result']['risk']['level']=='MEDIUM'
    repeated=run(client,a);assert repeated['result']['material_changes']==0 and repeated['result']['risk']['level']=='MEDIUM'
    assert set(calls)=={'get_demand_history','get_inventory_position','get_open_purchase_orders','get_lead_time_history'}

def test_cancel_during_tool_read_discards_all_results(client,monkeypatch):
    mcp_enabled(monkeypatch);a=agent(client,use_mcp=True);queued=post(client,'agents/'+a['id']+'/run',{});calls=[]
    async def cancel_on_read(db,user,tool,params,correlation,**kwargs):
        calls.append(tool)
        with Session() as other:
            row=other.get(AgentRun,queued['id']);row.status='CANCELLED';row.lease=None;other.commit()
        return gateway(a['category_id'])
    monkeypatch.setattr('app.agent_evidence.mcp_call',cancel_on_read)
    asyncio.run(process_agent_run())
    with Session() as db:
        row=db.get(AgentRun,queued['id']);assert row.status=='CANCELLED' and not row.result and not row.snapshot
        assert db.get(Record,a['id']).data['baseline_run_id'] is None
    assert len(calls)==1

def test_deadline_and_interrupted_worker_keep_previous_baseline(client,monkeypatch):
    mcp_enabled(monkeypatch);a=agent(client);baseline=run(client,a)
    queued=post(client,'agents/'+a['id']+'/run',{})
    with Session() as db:
        row=db.get(AgentRun,queued['id']);row.config={**row.config,'runtime_seconds':.01,'use_mcp':True};db.commit()
    async def slow(*args,**kwargs):await asyncio.sleep(1)
    monkeypatch.setattr('app.agent_evidence.mcp_call',slow);asyncio.run(process_agent_run())
    with Session() as db:
        row=db.get(AgentRun,queued['id']);assert row.status=='FAILED' and 'Time budget' in row.error and not row.result
        assert db.get(Record,a['id']).data['baseline_run_id']==baseline['id']
    queued=post(client,'agents/'+a['id']+'/run',{})
    with Session() as db:
        row=db.get(AgentRun,queued['id']);row.status='RUNNING';row.lease='lost-worker';row.started_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();db.commit()
    recover_interrupted()
    with Session() as db:
        row=db.get(AgentRun,queued['id']);assert row.status=='FAILED' and row.lease is None and not row.result
        assert db.get(Record,a['id']).data['baseline_run_id']==baseline['id']

def test_due_schedule_is_idempotent_and_owner_must_remain_active(client):
    a=agent(client,enabled=True);queue_due();queue_due()
    with Session() as db:
        rows=list(db.scalars(select(AgentRun).where(AgentRun.agent_id==a['id'])));assert len(rows)==1 and rows[0].trigger=='scheduled'
        id=rows[0].id;user=db.get(User,'Buyer');user.active=False;db.commit()
    try:
        asyncio.run(process_agent_run())
        with Session() as db:assert db.get(AgentRun,id).status=='CANCELLED'
    finally:
        with Session() as db:db.get(User,'Buyer').active=True;db.commit()
        post(client,'agents/'+a['id']+'/toggle',{'enabled':False})

def test_corrections_zero_baseline_and_repeated_change_episodes(client):
    role(client);cat=category();id=signal(client,cat,'demand_quantity',[0,0]);a=agent(client,cat,signal_ids=[id]);run(client,a)
    change(client,id,100);first=run(client,a)
    delta=next(c for c in first['result']['changes'] if c['type']=='VALUE_CHANGED');assert delta['pct'] is None
    assert first['result']['risk']['level']=='UNKNOWN' and 'zero baseline' in first['result']['summary']
    change(client,id,120,replace=True);second=run(client,a)
    assert any(c.get('corrected') for c in second['result']['changes'])
    change(client,id,100,replace=True);run(client,a);change(client,id,120,replace=True);third=run(client,a)
    assert third['result']['alert_id']!=second['result']['alert_id']

def test_source_limits_and_demo_evidence_are_explicit(client):
    a=agent(client);source(a['category_id'],'supplier',is_demo=True)
    assert run(client,a)['snapshot']['coverage']['Supplier Data']['state']=='MISSING'
    with Session() as db:
        db.add_all([Record(kind='event',owner='Buyer',region='Region 1',data={'category_id':a['category_id'],'title':'Event '+str(i)}) for i in range(201)]);db.commit()
    result=run(client,a)
    assert result['snapshot']['coverage']['Market Events']['state']=='DEGRADED'
    assert any(i['code']=='SOURCE_LIMIT' for i in result['snapshot']['issues'])

def test_mcp_response_budget_and_runtime_allowlist(client,monkeypatch):
    from fastapi import HTTPException
    from app.intelligence import mcp_call
    mcp_enabled(monkeypatch);calls=[];original=httpx.AsyncClient
    def handler(request):
        body=json.loads(request.content);calls.append(body)
        if body['method']=='tools/call':return httpx.Response(200,json={'result':{'structuredContent':'x'*2048}})
        return httpx.Response(200,json={'result':{}})
    monkeypatch.setattr('app.intelligence.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    with Session() as db:
        with pytest.raises(HTTPException) as error:asyncio.run(mcp_call(db,db.get(User,'Buyer'),'get_demand_history',{'category':'cat'},uid(),max_response_bytes=1024))
        assert error.value.status_code==502 and len(calls)==3
        assert calls[2]['params']['arguments']=={'category':'cat','region':'Region 1','user_id':'Buyer'}
        monkeypatch.setenv('MCP_ALLOWED_HOSTS','')
        with pytest.raises(HTTPException) as error:asyncio.run(mcp_call(db,db.get(User,'Buyer'),'get_demand_history',{},uid(),max_response_bytes=1024))
        assert error.value.status_code==422 and len(calls)==3

def test_all_eight_domains_can_complete_and_requester_cannot_read(client):
    a,ids=core(client);po=signal(client,a['category_id'],'po_overdue_count',[0,0])
    body={**a,'signal_ids':[*a['signal_ids'],po]}
    from app.autonomous import AgentInput
    response=client.put('/api/v1/agents/'+a['id'],json={k:v for k,v in body.items() if k in AgentInput.model_fields});assert response.status_code==200
    for kind in ['rfi','document','event']:source(a['category_id'],kind)
    role(client,'Market Intelligence Analyst');price=post(client,'market/series',{'name':'All domains price','category_id':a['category_id'],'commodity':'Steel','geography':'Indonesia','currency':'USD','unit':'MT','source':'Market publication'})
    post(client,'market/series/'+price['id']+'/observations',{'observations':[{'date':date.today().isoformat(),'value':100}]})
    role(client);result=run(client,a);assert result['status']=='COMPLETED' and result['result']['risk']['covered_domains']==8
    role(client,'Fungsi Pengguna');assert client.get('/api/v1/agents').status_code==403 and client.get('/api/v1/agents/signals').status_code==403
    assert client.get('/api/v1/agents/inbox/alerts').json()==[]

@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='PostgreSQL row-lock concurrency')
def test_postgres_concurrent_enqueue_and_worker_claim(client):
    a=agent(client);cookie=dict(client.cookies)
    def enqueue(_):
        with TestClient(app) as c:
            c.cookies.update(cookie);return post(c,'agents/'+a['id']+'/run',{})['id']
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(enqueue,range(2)))
    assert ids[0]==ids[1]
    with ThreadPoolExecutor(max_workers=2) as pool:worked=list(pool.map(lambda _:asyncio.run(process_agent_run()),range(2)))
    assert sorted(worked)==[False,True]
    with Session() as db:
        row=db.get(AgentRun,ids[0]);assert row.status=='PARTIAL'
        assert sum(s['step']=='PUBLISH' for s in row.steps)==1

def test_risk_change_alert_when_observation_period_rolls_forward(client):
    role(client);cat=category();ids=[signal(client,cat,m,v) for m,v in [('demand_quantity',[100,120]),('inventory_coverage',[8,8]),('supplier_lead_time',[8,8])]]
    a=agent(client,cat,signal_ids=ids);assert run(client,a)['result']['risk']['level']=='MEDIUM'
    change(client,ids[0],120);result=run(client,a)
    assert result['result']['risk']['level']=='LOW' and result['result']['alert_id']
    assert any(c['type']=='RISK_CHANGED' for c in result['result']['changes'])

def test_enterprise_basis_change_never_computes_percentage(client,monkeypatch):
    from fastapi import HTTPException
    mcp_enabled(monkeypatch);a=agent(client,use_mcp=True);state={'unit':'MT','value':100,'days':1}
    async def fake(db,user,tool,params,correlation,**kwargs):
        if tool!='get_demand_history':raise HTTPException(502)
        return gateway(a['category_id'],**state)
    monkeypatch.setattr('app.agent_evidence.mcp_call',fake);run(client,a)
    state.update(unit='kg',value=100000,days=0);result=run(client,a)
    assert any(c['type']=='BASIS_CHANGED' for c in result['result']['changes'])
    assert not any(c['type']=='VALUE_CHANGED' for c in result['result']['changes'])
    assert result['result']['risk']['level']=='UNKNOWN'

def test_low_confidence_historical_value_cannot_establish_risk_growth(client):
    a,ids=core(client)
    with Session() as db:
        from app.db import MarketPoint
        prior=db.scalar(select(MarketPoint).where(MarketPoint.series_id==ids['demand_quantity']).order_by(MarketPoint.observed_on).limit(1))
        prior.confidence=0;prior.value=1;db.commit()
    result=run(client,a)
    assert 'demand_quantity' in result['result']['risk']['missing_risk_metrics']
    assert not any(s['metric']=='demand_quantity' for s in result['result']['risk']['signals'])

def test_response_counts_preserve_underlying_response_permissions(client):
    a=agent(client);rfi=source(a['category_id'],'rfi');response=source(a['category_id'],'response',rfi_id=rfi,submitted=True)
    with Session() as db:db.get(Record,response).classification='RESTRICTED';db.commit()
    result=run(client,a);entity=next(e for e in result['snapshot']['entities'] if e['key']==rfi)
    assert entity['fields']['submitted_responses']==1 and entity['dependencies'][0]['id']==response
    assert client.put('/api/v1/agents/'+a['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    role(client,'Market Intelligence Analyst');shared=client.get('/api/v1/agents/'+a['id']+'/runs/'+result['id']).json()
    assert not shared['evidence_available'] and 'result' not in shared

def test_synchronous_collection_over_budget_cannot_publish(client,monkeypatch):
    import app.autonomous as module
    a=agent(client);queued=post(client,'agents/'+a['id']+'/run',{});clock={'value':0};collect=module.local_evidence
    monkeypatch.setattr(module,'monotonic',lambda:clock['value'])
    def slow_collection(db,user,config):
        result=collect(db,user,config);clock['value']+=config['runtime_seconds']+1;return result
    monkeypatch.setattr(module,'local_evidence',slow_collection);asyncio.run(process_agent_run())
    with Session() as db:
        row=db.get(AgentRun,queued['id']);assert row.status=='FAILED' and 'Time budget' in row.error
        assert not row.result and db.get(Record,a['id']).data['baseline_run_id'] is None
