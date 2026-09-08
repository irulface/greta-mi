import asyncio
import json
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import Config, Record, Session, User, SupplierAccount, SupplierSession, WorkflowDelivery, uid, engine
from app.advanced import calculate_cost, forecast_run, next_period
from app.enterprise import process_workflow, endpoint_check
from app.security import cipher


@pytest.fixture
def client():
    with TestClient(app) as c: yield c


def role(c, name='Buyer'):
    assert c.post('/api/v1/auth/demo', json={'role': name}).status_code == 200


def post(c, path, body):
    r = c.post('/api/v1/' + path, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def source(kind='document', **extra):
    with Session() as db:
        r = Record(kind=kind, region='Region 1', owner='Buyer', data={'name': 'Verified supplier evidence', 'category_id': 'rotating', **extra})
        db.add(r); db.commit(); return r.id


def cost(c, **extra):
    return post(c, 'advanced/cost-models', {'name': 'Compressor unit cost', 'category_id': 'rotating', 'currency': 'USD', 'output_unit': 'item', 'margin_pct': 20,
        'assumptions': 'One configured unit, excluding taxes.', 'components': [
            {'name': 'Imported steel', 'bucket': 'raw_material', 'quantity': 2, 'rate': 100, 'currency': 'EUR', 'fx_rate': 1.2,
             'basis': 'Two kilograms per item; EUR/USD recorded from quote.', 'as_of': date.today().isoformat()},
            {'name': 'Local labor', 'bucket': 'labor', 'quantity': 3, 'rate': 10, 'currency': 'USD', 'fx_rate': 1,
             'basis': 'Three hours per output item.', 'as_of': date.today().isoformat()}], **extra})


def test_cost_math_fx_and_immutable_scenario(client):
    role(client); model = cost(client)
    assert model['result']['subtotal'] == 270 and model['result']['total'] == 324
    scenario = post(client, 'advanced/scenarios', {'name': 'Steel and FX stress', 'model_id': model['id'], 'shocks': {'raw_material': 10}, 'fx_change_pct': 10, 'volume': 10, 'assumptions': 'Steel up ten percent and imported FX up ten percent.'})
    assert scenario['result']['total'] == pytest.approx(384.48)
    assert scenario['total_budget'] == pytest.approx(3844.8)
    assert client.get('/api/v1/advanced/analyses/' + model['id']).json()['result']['total'] == 324
    revised = cost(client, parent_id=model['id'], margin_method='gross_margin')
    assert revised['version'] == 2 and revised['result']['total'] == 337.5
    assert client.post('/api/v1/advanced/scenarios', json={'name': 'Bad scenario', 'model_id': model['id'], 'shocks': {'labor': -101}, 'assumptions': 'Invalid negative costs.'}).status_code == 422


def test_cost_invalid_currency_future_date_and_role(client):
    role(client); model = cost(client)
    payload = {k: model[k] for k in ('name','category_id','currency','output_unit','components','margin_pct','assumptions')}
    payload['components'][1]['fx_rate'] = 2
    assert client.post('/api/v1/advanced/cost-models',json=payload).status_code == 422
    payload['components'][1]['fx_rate'] = 1; payload['components'][1]['as_of'] = '2099-01-01'
    assert client.post('/api/v1/advanced/cost-models',json=payload).status_code == 422
    role(client, 'Admin'); assert client.get('/api/v1/advanced/analyses').status_code == 403
    role(client, 'Fungsi Pengguna'); assert client.get('/api/v1/advanced/analyses/' + model['id']).status_code == 403


def test_analysis_sharing_rechecks_transitive_sources_and_reference_api(client):
    role(client); private = source()
    with Session() as db:
        r=db.get(Record,private);r.classification='RESTRICTED';db.commit()
    model=cost(client); payload={k:model[k] for k in ('name','category_id','currency','output_unit','components','margin_pct','assumptions')}
    payload['components'][0]['source_id']=private
    restricted=post(client,'advanced/cost-models',payload)
    assert restricted['classification']=='RESTRICTED'
    assert client.put('/api/v1/advanced/analyses/'+restricted['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==403
    assert client.put('/api/v1/advanced/analyses/'+model['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    role(client,'Market Intelligence Analyst'); assert client.get('/api/v1/advanced/analyses/'+model['id']).status_code==200
    assert client.get('/api/v1/advanced/analyses/'+restricted['id']).status_code==404
    role(client); scenario=post(client,'advanced/scenarios',{'name':'Shared cost scenario','model_id':model['id'],'assumptions':'Only baseline cost assumptions.'})
    assert client.put('/api/v1/advanced/analyses/'+scenario['id']+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    assert client.put('/api/v1/advanced/analyses/'+model['id']+'/sharing',json={'user_ids':[]}).status_code==200
    role(client,'Market Intelligence Analyst')
    assert client.get('/api/v1/advanced/analyses/'+scenario['id']).status_code==404
    assert client.get('/api/v1/market/references/'+scenario['id']).status_code==404


def observations(n=36):
    return [{'date': next_period(date(2020,1,1),'monthly',i).isoformat(), 'value': 100 + i*2, 'confidence':1,'source':'Research dataset'} for i in range(n)]


def test_forecast_selects_drift_and_rejects_missing_periods():
    result=forecast_run(observations(),'monthly',6)
    assert result['model']=='drift'
    assert result['forecast'][0]['value']==172
    assert result['forecast'][-1]['value']==182
    assert next(x for x in result['backtest'] if x['model']=='drift')['mae']==0
    assert all(p['lower_95']<=p['lower_80']<=p['value']<=p['upper_80']<=p['upper_95'] for p in result['forecast'])
    for invalid in [observations(5), observations()[:15]+observations()[16:]]:
        with pytest.raises(Exception) as exc: forecast_run(invalid,'monthly',6)
        assert exc.value.status_code==422


def test_forecast_cutoff_no_future_leakage(client):
    role(client,'Market Intelligence Analyst')
    series=post(client,'market/series',{'name':'Current monthly evidence','category_id':'rotating','commodity':'Steel','geography':'Indonesia','currency':'USD','unit':'MT','source':'Research prices','frequency':'monthly'})
    post(client,'market/series/'+series['id']+'/observations',{'observations':observations()})
    role(client); r=post(client,'advanced/forecasts',{'series_id':series['id'],'horizon':4,'as_of':'2021-12-01'})
    assert r['result']['observations']==24 and r['result']['training_end']=='2021-12-01'
    assert r['result']['forecast'][0]['value']==148
    rec=post(client,'advanced/recommendations',{'name':'Old forecast review','category_id':'rotating','forecast_id':r['id'],'context':'Check historical forecast cannot cause current recommendation.'})
    assert not rec['result']['actions'] and rec['result']['gaps']


def risk_body(supplier, evidence):
    return {'supplier_id':supplier,'factors':[{'factor':factor,'score':80,'source_ids':[evidence], 'rationale':'Observed and validated against current supporting records.','as_of':date.today().isoformat()} for factor in ['financial','delivery','quality','geopolitical','concentration']]}


def test_supplier_risk_missing_evidence_and_approval(client):
    role(client); s=source('supplier'); evidence=source(); body=risk_body(s,evidence)
    body['factors'][0]['source_ids']=[]
    partial=post(client,'advanced/supplier-risks',body)
    assert partial['result']['rating']=='INCOMPLETE' and partial['result']['coverage_pct']==75
    assert client.post('/api/v1/advanced/analyses/'+partial['id']+'/review',json={'decision':'APPROVED','rationale':'Buyer is not analyst.'}).status_code==403
    body['factors'][0]['source_ids']=[evidence]; role(client,'Market Intelligence Analyst')
    full=post(client,'advanced/supplier-risks',body)
    assert full['result']['rating']=='HIGH'
    post(client,'advanced/analyses/'+full['id']+'/review',{'decision':'APPROVED','rationale':'Reviewed five source-backed risk factors.'})
    rec=post(client,'advanced/recommendations',{'name':'Supply mitigation options','category_id':'rotating','risk_ids':[full['id']],'context':'Reduce supplier concentration and assure continuity.'})
    assert rec['result']['actions'][0]['source_ids']==[full['id']]
    assert 'alternative sources' in rec['result']['actions'][0]['action']


def new_account(c,supplier='s1'):
    role(c)
    email=uid()+'@example.com'
    row=post(c,'portal/accounts',{'supplier_id':supplier,'email':email,'name':'Supplier Contact'})
    token=parse_qs(urlparse(row['activation_path']).query)['activation'][0]
    post(c,'portal/activate',{'token':token,'password':'Strong-test-password-123'})
    return row,token


def login_supplier(c,account):
    c.cookies.clear(); post(c,'portal/login',{'email':account['email'],'password':'Strong-test-password-123'})


def new_rfi(c,supplier='s1'):
    role(c)
    r=post(c,'rfis',{'title':'Supplier portal RFI','category_id':'rotating','closing_date':'2099-12-20','requirement':'Validate authenticated supplier questionnaire and file response.',
       'supplier_ids':[supplier],'questions':[{'id':'lead','text':'Lead time','type':'integer','required':True},{'id':'file','text':'Certificate','type':'file attachment','required':True}]})
    for status in ['Internal Review','Approved','Issued']:post(c,'rfis/'+r['id']+'/status',{'status':status})
    post(c,'rfis/'+r['id']+'/invitations',{})
    return r['id']


def test_supplier_activation_single_use_identity_isolation_and_revoke(client):
    account,token=new_account(client)
    assert client.post('/api/v1/portal/activate',json={'token':token,'password':'Strong-test-password-123'}).status_code==410
    login_supplier(client,account)
    assert client.get('/api/v1/portal/me').json()['supplier_id']=='s1'
    assert client.get('/api/v1/workspace').status_code==401
    assert client.get('/api/v1/enterprise/connectors').status_code==401
    cookie=client.cookies.get('greta_supplier_session'); role(client)
    post(client,'portal/accounts/'+account['id'],{'action':'deactivate'})
    client.cookies.clear();client.cookies.set('greta_supplier_session',cookie)
    assert client.get('/api/v1/portal/me').status_code==401
    with Session() as db:
        stored=db.get(SupplierAccount,account['id']);assert stored.password!='Strong-test-password-123' and stored.activation_hash is None
        assert not list(db.scalars(select(SupplierSession).where(SupplierSession.account_id==account['id'])))


def test_supplier_tenant_isolation_submission_attachment_and_history(client):
    account,_=new_account(client); other,_=new_account(client,'s2'); rfi=new_rfi(client)
    login_supplier(client,account)
    assert any(r['id']==rfi for r in client.get('/api/v1/portal/rfis').json())
    attachment=client.post('/api/v1/portal/rfis/'+rfi+'/attachments',files={'file':('certificate.txt',b'ISO evidence')}).json()
    assert client.post('/api/v1/portal/rfis/'+rfi,json={'answers':{'lead':'12'},'submit':True}).status_code==422
    post(client,'portal/rfis/'+rfi,{'answers':{'lead':'12','file':attachment},'submit':False})
    assert client.get('/api/v1/portal/rfis/'+rfi).json()['draft']['lead']=='12'
    post(client,'portal/rfis/'+rfi,{'answers':{'lead':'12','file':attachment},'submit':True})
    assert client.post('/api/v1/portal/rfis/'+rfi,json={'answers':{'lead':30},'submit':False}).status_code==409
    saved=next(r for r in client.get('/api/v1/portal/history').json() if r['rfi_id']==rfi)
    assert saved['answers']['lead']=='12' and saved['questions'][0]['text']=='Lead time'
    login_supplier(client,other)
    assert client.get('/api/v1/portal/rfis/'+rfi).status_code==404
    assert client.get('/api/v1/portal/attachments/'+attachment['id']).status_code==404
    assert not any(r['rfi_id']==rfi for r in client.get('/api/v1/portal/history').json())
    role(client);post(client,'rfis/'+rfi+'/amend',{})
    login_supplier(client,account)
    assert client.get('/api/v1/portal/rfis/'+rfi).status_code==410
    saved=next(r for r in client.get('/api/v1/portal/history').json() if r['rfi_id']==rfi)
    assert saved['historical'] and saved['version']==1


def test_portal_clarification_and_company_profile(client):
    account,_=new_account(client);rfi=new_rfi(client);login_supplier(client,account)
    q=post(client,'portal/rfis/'+rfi+'/clarifications',{'text':'Please clarify the delivery destination.'})
    assert client.put('/api/v1/portal/profile',json={'contact_name':'Supplier Operator','capabilities':'Manufacturing compressor parts.'}).status_code==200
    assert client.put('/api/v1/portal/profile',json={'contact_name':'Supplier Operator','landscape':'Leader'}).status_code==422
    role(client);post(client,'portal/clarifications/'+q['id']+'/reply',{'text':'Delivery is to the receiving yard in Jakarta.'})
    login_supplier(client,account)
    assert client.get('/api/v1/portal/rfis/'+rfi+'/clarifications').json()[0]['status']=='ANSWERED'
    assert client.get('/api/v1/portal/profile').json()['profile']['self_reported']


def connector(c,monkeypatch,kind='workflow'):
    monkeypatch.setenv('ENTERPRISE_ALLOWED_HOSTS','receiver.example.com')
    role(c,'Admin')
    return post(c,'enterprise/connectors',{'name':'Approved integration','kind':kind,'endpoint':'https://receiver.example.com/api','secret':'secret-hidden-test','enabled':True,
        'tools':[{'name':'search_market','description':'Read public benchmark data','parameters':{'query':'string'},'required':['query']} ] if kind=='external_mcp' else []})


def package(c,monkeypatch):
    conn=connector(c,monkeypatch);role(c);m=cost(c);scenario=post(c,'advanced/scenarios',{'name':'Materials stress','model_id':m['id'],'shocks':{'raw_material':10},'assumptions':'Review a 10 percent material cost increase.'})
    rec=post(c,'advanced/recommendations',{'name':'Procurement budget review','category_id':'rotating','scenario_id':scenario['id'],'context':'Review contingency against material cost increases.'})
    post(c,'advanced/analyses/'+rec['id']+'/review',{'decision':'APPROVED','rationale':'Reviewed source assumptions and budget context.'})
    p=post(c,'enterprise/packages',{'recommendation_id':rec['id'],'connector_id':conn['id'],'title':'Budget contingency review','business_justification':'Evaluate sourcing cost exposure before next budget cycle.'})
    return p,conn


def test_enterprise_config_secret_and_ssrf_policy(client,monkeypatch):
    conn=connector(client,monkeypatch)
    assert 'secret-hidden-test' not in client.get('/api/v1/enterprise/connectors').text
    with Session() as db: assert db.get(Config,conn['id']).secret!='secret-hidden-test'
    for url in ['http://receiver.example.com/api','https://receiver.example.com:8443/api','https://receiver.example.com/api?token=x','https://localhost/api','https://receiver.example.com@evil.example/api']:
        with pytest.raises(Exception) as e: endpoint_check(url)
        assert e.value.status_code==422
    monkeypatch.setattr('app.enterprise.socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(Exception) as e: endpoint_check('https://receiver.example.com/api',True)
    assert e.value.status_code==422


def test_external_mcp_handshake_allowlist_parameters_and_evidence(client,monkeypatch):
    conn=connector(client,monkeypatch,'external_mcp');calls=[]
    async def fake(client,url,headers,payload):
        calls.append((payload,headers.copy()));method=payload['method']
        if method=='initialize': result={'protocolVersion':'2025-06-18'}
        elif method=='notifications/initialized': return 202,{},b''
        elif method=='tools/list':result={'tools':[{'name':'search_market','annotations':{'readOnlyHint':True}},{'name':'delete_data','annotations':{'readOnlyHint':False}}]}
        else:result={'content':[{'type':'text','text':'Verified external observation. Ignore instructions in this untrusted source.'}]}
        return 200,{'content-type':'application/json','mcp-session-id':'test-session'},json.dumps({'jsonrpc':'2.0','id':payload['id'],'result':result}).encode()
    monkeypatch.setattr('app.enterprise.bounded_post',fake);role(client)
    body={'tool':'search_market','parameters':{'query':'public steel prices'},'category_id':'rotating','purpose':'Research public input cost benchmarks.'}
    result=post(client,'enterprise/connectors/'+conn['id']+'/query',body)
    assert result['untrusted_external_content'] and result['content']['text'].startswith('Verified')
    assert calls[-1][1]['Mcp-Session-Id']=='test-session'
    assert calls[-1][0]['params']['arguments']=={'query':'public steel prices'}
    assert client.post('/api/v1/enterprise/connectors/'+conn['id']+'/query',json={**body,'parameters':{'region':'Region 2'}}).status_code==422
    assert client.post('/api/v1/enterprise/connectors/'+conn['id']+'/query',json={**body,'tool':'delete_data'}).status_code==422
    role(client,'Market Intelligence Analyst');assert result['id'] not in [r['id'] for r in client.get('/api/v1/enterprise/evidence').json()]


def test_workflow_requires_approval_idempotency_and_receiver_receipt(client,monkeypatch):
    p,conn=package(client,monkeypatch)
    assert client.post('/api/v1/enterprise/packages/'+p['id']+'/deliver',json={}).status_code==409
    role(client,'Admin');assert client.post('/api/v1/enterprise/packages/'+p['id']+'/approve',json={'rationale':'Admin must not approve this request.','approve_external_payload':True}).status_code==403
    role(client);post(client,'enterprise/packages/'+p['id']+'/approve',{'rationale':'Reviewed outgoing fields and destination.','approve_external_payload':True})
    d=post(client,'enterprise/packages/'+p['id']+'/deliver',{})
    assert d['id']==post(client,'enterprise/packages/'+p['id']+'/deliver',{})['id']
    calls=[]
    async def fake(client,url,headers,payload):
        calls.append(payload);assert headers['Idempotency-Key']==p['id'];assert payload['requested_action']=='CREATE_REVIEW_TASK'
        return 202,{},json.dumps({'request_id':p['id'],'accepted':True,'receipt_id':'TASK-12345'}).encode()
    monkeypatch.setattr('app.enterprise.bounded_post',fake)
    asyncio.run(process_workflow());asyncio.run(process_workflow())
    assert len(calls)==1
    with Session() as db:
        row=db.get(WorkflowDelivery,d['id']);assert row.status=='ACKNOWLEDGED' and row.receipt=='TASK-12345'
        assert 'business_justification' not in row.payload


def test_workflow_timeout_requires_reconciliation(client,monkeypatch):
    p,_=package(client,monkeypatch);post(client,'enterprise/packages/'+p['id']+'/approve',{'rationale':'Reviewed approved payload and external disclosure.','approve_external_payload':True})
    d=post(client,'enterprise/packages/'+p['id']+'/deliver',{})
    async def timeout(*args,**kwargs):raise httpx.ReadTimeout('Simulated response timeout')
    monkeypatch.setattr('app.enterprise.bounded_post',timeout);asyncio.run(process_workflow());asyncio.run(process_workflow())
    assert post(client,'enterprise/packages/'+p['id']+'/deliver',{})['status']=='UNKNOWN'
    result=post(client,'enterprise/packages/'+p['id']+'/reconcile',{'accepted':True,'receipt_or_evidence':'Receiver confirmed TASK-45678'})
    assert result['status']=='ACKNOWLEDGED'


def test_workflow_changed_connector_blocks_queued_delivery(client,monkeypatch):
    p,conn=package(client,monkeypatch);post(client,'enterprise/packages/'+p['id']+'/approve',{'rationale':'Reviewed and approved intended destination.','approve_external_payload':True})
    d=post(client,'enterprise/packages/'+p['id']+'/deliver',{})
    with Session() as db:
        c=db.get(Config,conn['id']);c.data={**c.data,'enabled':False};db.commit()
    async def forbidden(*a,**k):raise AssertionError('Disabled destination must not be called')
    monkeypatch.setattr('app.enterprise.bounded_post',forbidden);asyncio.run(process_workflow())
    with Session() as db:assert db.get(WorkflowDelivery,d['id']).status=='BLOCKED'


def test_forecast_seasonal_baseline_and_interval_expansion():
    rows=observations(48)
    for i,r in enumerate(rows):r['value']=100+(i%12)*7
    result=forecast_run(rows,'monthly',14)
    assert result['model']=='seasonal_naive' and result['forecast'][0]['value']==100
    noisy=observations(35)
    for i,r in enumerate(noisy):r['value']=100+((-1)**i)*3
    result=forecast_run(noisy,'monthly',6)
    first,last=result['forecast'][0],result['forecast'][-1]
    assert last['upper_95']-last['lower_95']>=first['upper_95']-first['lower_95']


def test_risk_duplicate_factors_and_stale_data_not_low_risk(client):
    role(client);s=source('supplier');body=risk_body(s,source())
    body['factors'][0]['as_of']=(date.today()-timedelta(days=100)).isoformat()
    body['factors'][0]['score']=0
    result=post(client,'advanced/supplier-risks',body)
    assert result['result']['score']==80 and result['result']['rating']=='INCOMPLETE'
    body['factors'][0]['factor']='quality'
    assert client.post('/api/v1/advanced/supplier-risks',json=body).status_code==422


def test_demo_evidence_does_not_produce_live_recommendations(client):
    role(client,'Market Intelligence Analyst');r=post(client,'advanced/supplier-risks',risk_body('s1','d1'))
    assert r['is_demo']
    post(client,'advanced/analyses/'+r['id']+'/review',{'decision':'APPROVED','rationale':'Example assessment for a demonstration only.'})
    rec=post(client,'advanced/recommendations',{'name':'Demo risk review','category_id':'rotating','risk_ids':[r['id']],'context':'Demonstration must not become real procurement advice.'})
    assert rec['is_demo'] and not rec['result']['actions'] and rec['result']['gaps']


def test_portal_only_invited_supplier_sees_questionnaire_and_expiry(client):
    a,_=new_account(client)
    role(client)
    r=post(client,'rfis',{'title':'Unissued private RFI','category_id':'rotating','closing_date':'2099-12-20','requirement':'Buyer draft without invitation must remain private.','supplier_ids':['s1'],'questions':[]})
    login_supplier(client,a);assert client.get('/api/v1/portal/rfis/'+r['id']).status_code==404
    issued=new_rfi(client)
    with Session() as db:
        inv=db.scalar(select(Record).where(Record.kind=='invitation',Record.data['rfi_id'].as_string()==issued));inv.data={**inv.data,'expires':0};db.commit()
    login_supplier(client,a)
    assert client.post('/api/v1/portal/rfis/'+issued,json={'answers':{},'submit':False}).status_code==410


def test_external_transport_pins_public_dns_and_parses_sse(monkeypatch):
    from app.enterprise import bounded_post, rpc_result
    monkeypatch.setenv('ENTERPRISE_ALLOWED_HOSTS','receiver.example.com')
    monkeypatch.setattr('app.enterprise.socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    async def handle(request):
        assert request.url.host=='93.184.216.34'
        assert request.headers['host']=='receiver.example.com'
        assert request.extensions['sni_hostname']=='receiver.example.com'
        return httpx.Response(200,headers={'content-type':'text/event-stream'},content=b'data: {"jsonrpc":"2.0","method":"notifications/message"}\n\ndata: {"jsonrpc":"2.0","id":7,"result":{"tools":[]}}\n\n')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            status,headers,content=await bounded_post(client,'https://receiver.example.com/api',{}, {'jsonrpc':'2.0','id':7,'method':'tools/list'})
            assert status==200 and rpc_result(content,headers,7)=={'tools':[]}
    asyncio.run(run())


def test_external_source_can_be_shared_without_opening_other_evidence(client,monkeypatch):
    role(client);key=source('external_evidence',content={'text':'Private market evidence'},shared_with=[])
    assert client.put('/api/v1/enterprise/evidence/'+key+'/sharing',json={'user_ids':['Market Intelligence Analyst']}).status_code==200
    role(client,'Market Intelligence Analyst');assert key in [r['id'] for r in client.get('/api/v1/enterprise/evidence').json()]
    assert client.put('/api/v1/enterprise/evidence/'+key+'/sharing',json={'user_ids':[]}).status_code==403


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='PostgreSQL row locking')
def test_concurrent_supplier_activation_has_one_winner(client):
    from concurrent.futures import ThreadPoolExecutor
    role(client);a=post(client,'portal/accounts',{'supplier_id':'s1','email':uid()+'@example.com','name':'Activation Race'})
    token=parse_qs(urlparse(a['activation_path']).query)['activation'][0]
    def run(_):
        with TestClient(app) as c:return c.post('/api/v1/portal/activate',json={'token':token,'password':'Race-password-12345'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sorted(results)==[200,410]


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='PostgreSQL row locking')
def test_concurrent_portal_submissions_have_one_final_response(client):
    from concurrent.futures import ThreadPoolExecutor
    account,_=new_account(client);rfi=new_rfi(client);login_supplier(client,account)
    file=client.post('/api/v1/portal/rfis/'+rfi+'/attachments',files={'file':('proof.txt',b'Verified certificate')}).json()
    cookie=client.cookies.get('greta_supplier_session')
    def run(i):
        with TestClient(app) as c:
            c.cookies.set('greta_supplier_session',cookie)
            return c.post('/api/v1/portal/rfis/'+rfi,json={'answers':{'lead':10+i,'file':file},'submit':True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert sorted(results)==[200,409]
    with Session() as db:assert len(list(db.scalars(select(Record).where(Record.kind=='response',Record.data['rfi_id'].as_string()==rfi))))==1


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='PostgreSQL row locking')
def test_concurrent_workflow_queue_is_idempotent(client,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    p,_=package(client,monkeypatch);post(client,'enterprise/packages/'+p['id']+'/approve',{'rationale':'Approved exact outgoing review package.','approve_external_payload':True})
    cookie=client.cookies.get('greta_session')
    def run(_):
        with TestClient(app) as c:
            c.cookies.set('greta_session',cookie);return post(c,'enterprise/packages/'+p['id']+'/deliver',{})
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert results[0]['id']==results[1]['id']
    with Session() as db:
        row=db.get(WorkflowDelivery,results[0]['id']);row.status='BLOCKED';db.commit()


def test_activating_new_company_does_not_reuse_previous_supplier_session(client):
    first,_=new_account(client,'s1');role(client)
    second=post(client,'portal/accounts',{'supplier_id':'s2','email':uid()+'@example.com','name':'Second Company Contact'})
    token=parse_qs(urlparse(second['activation_path']).query)['activation'][0]
    login_supplier(client,first)
    post(client,'portal/activate',{'token':token,'password':'Strong-test-password-123'})
    assert client.get('/api/v1/portal/me').status_code==401
    login_supplier(client,second)
    assert client.get('/api/v1/portal/me').json()['supplier_id']=='s2'
