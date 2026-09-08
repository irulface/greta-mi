import os, tempfile, asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.db import Session, Record, Config
from app.ingestion import run_job
import pytest
@pytest.fixture
def client():
    with TestClient(app) as c:yield c

def role(c,name='Buyer'):assert c.post('/api/v1/auth/demo',json={'role':name}).status_code==200

def body():return {'title':'New compressor RFI test','category_id':'rotating','closing_date':'2099-12-20','requirement':'Require 5 MW compressor for offshore application.','supplier_ids':['s1'],'questions':[{'id':'q1','text':'Lead time in weeks','type':'integer','required':True}]}

def test_auth_required(client):
    assert client.get('/api/v1/workspace').status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'invalid@example.com','password':'incorrect'}).status_code==401

def test_admin_cannot_approve_and_requester_cannot_issue(client):
    role(client,'Admin')
    assert client.post('/api/v1/rfis',json=body()).status_code==403
    assert client.post('/api/v1/rfis/r2/status',json={'status':'Approved'}).status_code==403
    role(client,'Fungsi Pengguna')
    assert client.get('/api/v1/admin/config').status_code==403
    r=client.post('/api/v1/rfis',json=body());assert r.status_code==200,r.text
    id=r.json()['id']
    assert client.post(f'/api/v1/rfis/{id}/status',json={'status':'Internal Review'}).status_code==200
    assert client.post(f'/api/v1/rfis/{id}/status',json={'status':'Approved'}).status_code==403

def test_complete_lifecycle_response_lock_and_repository(client):
    role(client);r=client.post('/api/v1/rfis',json=body());assert r.status_code==200,r.text
    id=r.json()['id']
    assert client.post(f'/api/v1/rfis/{id}/status',json={'status':'Issued'}).status_code==409
    for status in ['Internal Review','Approved','Issued','Open']:
        r=client.post(f'/api/v1/rfis/{id}/status',json={'status':status});assert r.status_code==200,r.text
    assert client.put(f'/api/v1/rfis/{id}',json=body()).status_code==409
    links=client.post(f'/api/v1/rfis/{id}/invitations',json={}).json();token=links[0]['path'].split('=')[1]
    assert client.get('/api/v1/respond/'+token).json()['supplier']=='Nusantara Compressor'
    assert client.post('/api/v1/respond/'+token,json={'answers':{},'submit':True}).status_code==422
    assert client.post('/api/v1/respond/'+token,json={'answers':{'q1':'nan'},'submit':True}).status_code==422
    assert client.post('/api/v1/respond/'+token,json={'answers':{'q1':'20'},'submit':False}).status_code==200
    assert client.get('/api/v1/respond/'+token).json()['draft']['q1']=='20'
    assert client.post('/api/v1/respond/'+token,json={'answers':{'q1':'20'},'submit':True}).status_code==200
    assert client.post('/api/v1/respond/'+token,json={'answers':{'q1':'22'},'submit':True}).status_code==409
    assert client.get('/api/v1/rfis/'+id).json()['responses'][0]['answers']['q1']=='20'
    for status in ['Closed','Analysis','Completed','Archived']:
        assert client.post(f'/api/v1/rfis/{id}/status',json={'status':status}).status_code==200
    docs=client.post('/api/v1/repository/search',json={'query':'New compressor RFI test'}).json()
    assert any(d.get('rfi_id')==id for d in docs)
    assert client.get('/api/v1/respond/'+token).status_code==410

def test_negative_data_scope_search_and_mcp(client):
    with Session() as db:
        db.add(Record(id='secret-b',kind='document',owner='Buyer',region='Region 2',data={'name':'Secret Region 2','text':'secretbanana compressor price 99999','status':'Indexed'}))
        db.add(Record(id='secret-restricted',kind='document',owner='Admin',region='Region 1',classification='RESTRICTED',data={'name':'Restricted','text':'secretbanana confidential'}));db.commit()
    role(client)
    assert client.get('/api/v1/repository/documents/secret-b').status_code==404
    assert client.get('/api/v1/repository/documents/secret-restricted/download').status_code==404
    assert client.post('/api/v1/repository/search',json={'query':'secretbanana'}).json()==[]
    r=client.post('/api/v1/ai/chat',json={'message':'secretbanana','mode':'sources'});assert r.status_code==200 and not r.json()['citations']
    assert client.post('/api/v1/mcp/call',json={'tool':'get_po_history','parameters':{'region':'Region 2'}}).status_code==403
    assert client.post('/api/v1/mcp/call',json={'tool':'execute_sql','parameters':{}}).status_code==403

def test_encrypted_config_and_endpoint_allowlist(client):
    role(client,'Admin');key='test-secret-do-not-expose'
    r=client.put('/api/v1/admin/config/azure',json={'endpoint':'https://test.openai.azure.com','model':'test','api_key':key,'enabled':False});assert r.status_code==200 and key not in r.text
    assert key not in client.get('/api/v1/admin/config').text
    with Session() as db:assert key not in db.get(Config,'azure').secret
    assert client.put('/api/v1/admin/config/azure',json={'endpoint':'http://127.0.0.1:8080','api_key':key}).status_code==422
    assert client.put('/api/v1/admin/config/mcp',json={'endpoint':'https://arbitrary.example.com','enabled':True}).status_code==422

def test_upload_index_dedup_and_path_guard(client):
    role(client);content=b'Example compressor lead time 19 weeks.'
    r=client.post('/api/v1/repository/upload',files={'file':('test-compressor.txt',content,'text/plain')});assert r.status_code==200,r.text
    asyncio.run(run_job(r.json()['id']))
    docs=client.post('/api/v1/repository/search',json={'query':'Example compressor lead'}).json();doc=next(x for x in docs if x['name']=='test-compressor.txt')
    assert doc['status']=='Indexed' and doc['has_file']
    assert client.get('/api/v1/repository/documents/'+doc['id']+'/download').content==content
    again=client.post('/api/v1/repository/upload',files={'file':('copy.txt',content,'text/plain')}).json();asyncio.run(run_job(again['id']))
    with Session() as db:assert db.get(Record,again['id']).data['duplicate']==1
    assert client.post('/api/v1/repository/upload',files={'file':('bad.exe',b'bad','application/octet-stream')}).status_code==422
    role(client,'Admin');assert client.post('/api/v1/repository/index',json={'path':'/etc'}).status_code==422

def test_no_fabricated_ai_without_connection(client):
    role(client)
    assert client.post('/api/v1/ai/chat',json={'message':'Compressor lead time','mode':'ai'}).status_code==503
    assert client.post('/api/v1/repository/search',json={'query':'compressor','mode':'semantic'}).status_code==503
    r=client.post('/api/v1/ai/chat',json={'message':'Compressor lead time','mode':'sources'});assert r.status_code==200 and r.json()['citations']

def test_csrf_and_logout(client):
    role(client)
    assert client.post('/api/v1/rfis',json=body(),headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/v1/auth/logout',json={}).status_code==200
    assert client.get('/api/v1/workspace').status_code==401

def test_supplier_attachments_conditions_and_amendment(client):
    role(client);b=body();b['questions']=[{'id':'oem','text':'Are you the OEM?','type':'yes/no','required':True},{'id':'letter','text':'Authorization letter','type':'file attachment','required':True,'condition':{'question_id':'oem','equals':'No'}}]
    r=client.post('/api/v1/rfis',json=b);assert r.status_code==200,r.text
    id=r.json()['id']
    for status in ['Internal Review','Approved','Issued']:
        assert client.post(f'/api/v1/rfis/{id}/status',json={'status':status}).status_code==200
    token=client.post(f'/api/v1/rfis/{id}/invitations',json={}).json()[0]['path'].split('=')[1]
    assert client.post('/api/v1/respond/'+token,json={'answers':{'oem':'No'},'submit':True}).status_code==422
    a=client.post('/api/v1/respond/'+token+'/attachments',files={'file':('authorization.txt',b'Letter from the OEM','text/plain')});assert a.status_code==200,a.text
    assert client.post('/api/v1/respond/'+token,json={'answers':{'oem':'No','letter':a.json()},'submit':True}).status_code==200
    assert client.get('/api/v1/attachments/'+a.json()['id']).content==b'Letter from the OEM'
    r=client.post(f'/api/v1/rfis/{id}/amend',json={});assert r.status_code==200,r.text
    assert r.json()['status']=='Draft' and r.json()['version']==2
    assert client.get('/api/v1/respond/'+token).status_code==410
    assert client.get('/api/v1/rfis/'+id).json()['responses']==[]
    with Session() as db:
        from sqlalchemy import select
        assert any(x.data.get('rfi_id')==id for x in db.scalars(select(Record).where(Record.kind=='response_version')))

def test_template_versions_and_global_scope(client):
    role(client)
    template={'name':'Compressor template','category_id':'rotating','questions':body()['questions']}
    one=client.post('/api/v1/rfi/templates',json=template);assert one.status_code==200,one.text
    two=client.post('/api/v1/rfi/templates',json=template);assert two.json()['version']==2
    assert one.json()['id']==two.json()['id']
    results=client.get('/api/v1/search?q=compressor').json();assert {'rfi','supplier','document'}.issubset({r['kind'] for r in results})
    assert not client.get('/api/v1/search?q=secretbanana').json()

def test_azure_v1_contract_and_scoped_rag(client,monkeypatch):
    import app.intelligence as intelligence
    import httpx, json
    role(client,'Admin')
    assert client.put('/api/v1/admin/config/azure',json={'endpoint':'https://test.openai.azure.com','model':'company-reasoning','embedding':'company-embedding','api_key':'mock-azure-key','enabled':True}).status_code==200
    seen=[]
    def handler(request):
        seen.append(request)
        assert request.headers['api-key']=='mock-azure-key'
        payload=json.loads(request.content)
        assert payload['model']=='company-reasoning'
        assert '/openai/v1/chat/completions' in str(request.url)
        assert 'secretbanana' not in json.dumps(payload['messages'][0])
        return httpx.Response(200,json={'choices':[{'message':{'content':'Compressor lead time is indicative. [d1]'}}],'usage':{'total_tokens':20}})
    original=httpx.AsyncClient
    monkeypatch.setattr(intelligence.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    role(client)
    r=client.post('/api/v1/ai/chat',json={'message':'gas compressor','mode':'ai'});assert r.status_code==200,r.text
    assert r.json()['mode']=='ai' and r.json()['citations'] and seen
    payload=json.loads(seen[-1].content)
    assert 'Secret Region 2' not in json.dumps(payload) and '99999' not in json.dumps(payload)

def test_mcp_initialize_call_and_identity_scope(client,monkeypatch):
    import app.intelligence as intelligence
    import httpx,json
    from app.security import cipher
    with Session() as db:
        c=db.get(Config,'mcp') or Config(id='mcp',data={});c.data={'enabled':True,'endpoint':'https://mcp.company.example/mcp'};c.secret=cipher().encrypt(b'mock-gateway-token').decode();db.add(c);db.commit()
    requests=[]
    def handler(request):
        p=json.loads(request.content);requests.append(p)
        if p['method']=='initialize':return httpx.Response(200,headers={'Mcp-Session-Id':'test-session'},json={'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-03-26','capabilities':{},'serverInfo':{'name':'mock','version':'1'}}})
        if p['method']=='notifications/initialized':return httpx.Response(202)
        assert request.headers['Mcp-Session-Id']=='test-session'
        assert request.headers['Authorization']=='Bearer mock-gateway-token'
        assert p['params']['arguments']['user_id']=='Buyer'
        assert p['params']['arguments']['region']=='Region 1'
        return httpx.Response(200,json={'jsonrpc':'2.0','id':2,'result':{'content':[{'type':'text','text':'{"available":8,"region":"Region 1"}'}]}})
    original=httpx.AsyncClient
    monkeypatch.setattr(intelligence.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    role(client)
    r=client.post('/api/v1/mcp/call',json={'tool':'get_inventory_position','parameters':{'category':'rotating'}});assert r.status_code==200,r.text
    assert len(requests)==3
    assert client.post('/api/v1/mcp/call',json={'tool':'get_po_history','parameters':{'sql':'SELECT *'}}).status_code==422

def test_production_bootstrap_taxonomy_and_user_administration(client):
    role(client,'Admin')
    c=client.post('/api/v1/admin/categories',json={'name':'Test Instrumentation','group':'Equipment','subcategory':'Controls','commodity':'Control valve'});assert c.status_code==200,c.text
    assert c.json()['region']=='Global'
    u=client.post('/api/v1/admin/users',json={'name':'Region Two Buyer','email':'regiontwo@company.example','password':'strong-test-password-123','role':'Buyer','region':'Region 2'});assert u.status_code==200,u.text
    assert client.put('/api/v1/admin/users/Admin',json={'role':'Buyer','region':'Region 1','active':True}).status_code==409
    assert client.put('/api/v1/admin/users/'+u.json()['id'],json={'role':'Fungsi Pengguna','region':'Region 2','active':False}).status_code==200

def test_semantic_search_embeds_query_and_filters_before_similarity(client,monkeypatch):
    import app.intelligence as intelligence
    import httpx,json
    from app.db import Chunk
    with Session() as db:
        db.add(Record(id='semantic-doc',kind='document',owner='Buyer',region='Region 1',data={'name':'Turbomachinery paper','text':'Centrifugal machinery','status':'Indexed'}));db.flush()
        db.add(Chunk(document_id='semantic-doc',content='Centrifugal machinery',embedding=[1.0,0.0,0.0],page=4));db.commit()
    original=httpx.AsyncClient
    def handler(request):
        assert request.url.path=='/openai/v1/embeddings'
        assert json.loads(request.content)['model']=='company-embedding'
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.0,0.0,0.0]}]})
    monkeypatch.setattr(intelligence.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
    role(client)
    r=client.post('/api/v1/repository/search',json={'query':'gas compressor','mode':'semantic'});assert r.status_code==200,r.text
    assert r.json()[0]['id']=='semantic-doc' and r.json()[0]['page']==4
    assert all(x['id']!='secret-b' for x in r.json())
