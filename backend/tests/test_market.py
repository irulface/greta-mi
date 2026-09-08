import asyncio
import io
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import Config, MarketPoint, MarketRun, Record, Session, User, engine, uid
from app.market import statistics_for
from app.market_automation import process_market_run, queue_due_schedules


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def role(client, role='Market Intelligence Analyst'):
    assert client.post('/api/v1/auth/demo', json={'role': role}).status_code == 200


def series(client, **extra):
    role(client)
    result = client.post('/api/v1/market/series', json={
        'name': 'Sourced steel benchmark', 'category_id': 'octg', 'commodity': 'Steel HRC',
        'geography': 'Indonesia', 'currency': 'USD', 'unit': 'MT', 'metric_type': 'price',
        'frequency': 'monthly', 'source': 'Analyst market bulletin', **extra,
    })
    assert result.status_code == 200, result.text
    return result.json()['id']


def observe(client, id, observations, replace=False):
    result = client.post(f'/api/v1/market/series/{id}/observations', json={'observations': observations, 'replace_existing': replace})
    assert result.status_code == 200, result.text
    return result.json()


def sourced_series(client, **extra):
    id = series(client, **extra)
    observe(client, id, [{'date': '2024-01-01', 'value': 100}, {'date': '2024-02-01', 'value': 125}])
    return id


def test_statistics_use_dates_and_do_not_fabricate_missing_periods():
    rows = [{'date': '2023-01-01', 'value': 100, 'confidence': 1}, {'date': '2023-10-01', 'value': 150, 'confidence': .8},
            {'date': '2023-12-01', 'value': 180, 'confidence': 1}, {'date': '2024-01-01', 'value': 200, 'confidence': 1}]
    result = statistics_for(rows)
    assert result['mom'] == pytest.approx(11.1111)
    assert result['qoq'] == pytest.approx(33.3333)
    assert result['yoy'] == 100
    assert result['cagr'] == pytest.approx(100, abs=.15)
    assert result['ma_7'] is None and result['high'] == 200 and result['low'] == 100
    result = statistics_for([{'date': '2023-01-01', 'value': 0, 'confidence': 1}, {'date': '2023-06-01', 'value': 100, 'confidence': 1}])
    assert result['mom'] is None and result['cagr'] is None and result['volatility'] is None


def test_series_points_permissions_corrections_and_atomic_import(client):
    id = sourced_series(client)
    original = client.get('/api/v1/market/series/' + id).json()
    assert original['statistics']['mom'] == 25
    role(client, 'Buyer')
    assert client.post(f'/api/v1/market/series/{id}/observations', json={'observations': [{'date': '2024-03-01', 'value': 90}]}).status_code == 403
    role(client)
    assert observe(client, id, [{'date': '2024-01-01', 'value': 100}])['unchanged'] == 1
    result = client.post(f'/api/v1/market/series/{id}/observations', json={'observations': [{'date': '2024-03-01', 'value': 150}, {'date': '2024-02-01', 'value': 140}]})
    assert result.status_code == 409
    assert client.get('/api/v1/market/series/' + id).json()['statistics']['count'] == 2
    assert observe(client, id, [{'date': '2024-02-01', 'value': 140}], True)['updated'] == 1
    with Session() as db:
        from app.db import Audit
        assert db.scalar(select(Audit).where(Audit.event == 'market.point.corrected'))
    bad = b'date,value,source\n2024-03-01,170,Market report\n2024-04-01,NaN,Market report\n'
    assert client.post(f'/api/v1/market/series/{id}/import', files={'file': ('invalid.csv', bad)}).status_code == 422
    assert client.get('/api/v1/market/series/' + id).json()['statistics']['count'] == 2
    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(f'/api/v1/market/series/{id}/observations', json={'observations': [{'date': future, 'value': 100}]}).status_code == 422


def test_csv_xlsx_import_and_formula_safe_export(client):
    from openpyxl import Workbook
    id = series(client)
    workbook = Workbook(); sheet = workbook.active
    sheet.append(['date', 'value', 'confidence', 'source', 'notes'])
    sheet.append([datetime(2024, 1, 1), 120, .8, 'Monthly bulletin', 'Verified'])
    content = io.BytesIO(); workbook.save(content)
    result = client.post(f'/api/v1/market/series/{id}/import', files={'file': ('valid.xlsx', content.getvalue())})
    assert result.status_code == 200, result.text
    assert result.json()['inserted'] == 1
    sheet.append([datetime(2024, 2, 1), '=1+2', 1, 'Monthly bulletin', ''])
    content = io.BytesIO(); workbook.save(content)
    assert client.post(f'/api/v1/market/series/{id}/import', files={'file': ('formula.xlsx', content.getvalue())}).status_code == 422
    good = b'date,value,confidence,source,notes\n2024-02-01,140,0.9,Market bulletin,=HYPERLINK("https://example.org")\n'
    result = client.post(f'/api/v1/market/series/{id}/import', files={'file': ('valid.csv', good)})
    assert result.status_code == 200, result.text
    exported = client.get(f'/api/v1/market/series/{id}/export')
    assert exported.status_code == 200 and "'=HYPERLINK" in exported.text


def test_regional_comparison_requires_compatible_units_and_common_dates(client):
    a = sourced_series(client); b = series(client, geography='Singapore')
    observe(client, b, [{'date': '2024-01-01', 'value': 110}, {'date': '2024-03-01', 'value': 200}])
    result = client.get(f'/api/v1/market/comparison?ids={a},{b}')
    assert result.status_code == 200, result.text
    assert result.json()['as_of'] == '2024-01-01' and result.json()['gaps'][1]['vs_first_pct'] == 10
    c = sourced_series(client, currency='IDR')
    assert client.get(f'/api/v1/market/comparison?ids={a},{c}').status_code == 422
    with Session() as db:
        row = db.get(Record, b); row.region = 'Region 2'; db.commit()
    assert client.get(f'/api/v1/market/comparison?ids={a},{b}').status_code == 404


def test_market_event_and_landscape_require_analyst_review(client):
    role(client)
    body = {'title': 'Steel mill maintenance', 'category_id': 'octg', 'description': 'Planned shutdown reduces available production.', 'date': '2024-03-01',
            'type': 'Plant shutdown', 'source': 'Mill publication', 'geography': 'Indonesia', 'expected_impact': 'Delivery windows may extend', 'probability': .7, 'assessment': 'Check delivery dates.'}
    event = client.post('/api/v1/market/events', json=body)
    assert event.status_code == 200, event.text
    assert event.json()['probability'] == .7
    supplier = client.post('/api/v1/suppliers', json={'name': 'Market test steel mill', 'country': 'Indonesia', 'category_id': 'octg'}).json()
    approval = {'classification': 'Specialist', 'rationale': 'Certified for specialty steel based on the supplier dossier.', 'source_ids': [event.json()['id']]}
    role(client, 'Buyer')
    assert client.put(f"/api/v1/market/suppliers/{supplier['id']}/landscape", json=approval).status_code == 403
    role(client)
    result = client.put(f"/api/v1/market/suppliers/{supplier['id']}/landscape", json=approval)
    assert result.status_code == 200 and result.json()['landscape_history'][-1]['approved_by'] == 'Market Intelligence Analyst'
    assert client.post('/api/v1/market/events', json={**body, 'probability': 2}).status_code == 422


def test_shared_workspace_filters_private_sources_and_prevents_lost_updates(client):
    id = sourced_series(client)
    private_id = uid()
    with Session() as db:
        db.add(Record(id=private_id, kind='document', owner='Market Intelligence Analyst', region='Region 1', classification='RESTRICTED', data={'name': 'Private analyst source', 'text': 'DO_NOT_SHARE_THIS'})); db.commit()
    body = {'title': 'Shared steel outlook', 'category_id': 'octg', 'notes': 'Review steel sources.', 'reference_ids': [id, private_id], 'shared_with': ['Buyer'], 'version': 1}
    result = client.post('/api/v1/market/workspaces', json=body)
    assert result.status_code == 200, result.text
    workspace_id = result.json()['id']
    role(client, 'Buyer')
    shared = next(r for r in client.get('/api/v1/market/workspaces').json() if r['id'] == workspace_id)
    assert shared['reference_ids'] == [id] and shared['unavailable_count'] == 1
    assert 'Private analyst source' not in json.dumps(shared) and not shared['can_edit']
    assert client.get('/api/v1/market/references/' + private_id).status_code == 404
    assert client.put('/api/v1/market/workspaces/' + workspace_id, json=body).status_code == 403
    role(client)
    result = client.put('/api/v1/market/workspaces/' + workspace_id, json={**body, 'notes': 'Updated notes.'})
    assert result.json()['version'] == 2
    assert client.put('/api/v1/market/workspaces/' + workspace_id, json=body).status_code == 409
    view = client.post('/api/v1/market/views', json={'title': 'Steel sources', 'target': 'price', 'category_id': 'octg', 'query': 'steel'}).json()
    results = client.get(f"/api/v1/market/views/{view['id']}/results").json()['results']
    assert any(row['id'] == id for row in results)
    assert all(row['id'] != 'steel' for row in results)


def test_brief_citations_missing_data_and_scope_are_explicit(client):
    id = sourced_series(client, category_id='electrical')
    result = client.post('/api/v1/market/briefs', json={'category_id': 'electrical', 'mode': 'evidence'})
    assert result.status_code == 200, result.text
    report = result.json()
    assert len(report['sections']) == 9 and any(c['id'] == id for c in report['citations'])
    assert not report['is_demo']
    assert next(s for s in report['sections'] if s['title'] == 'Demand Outlook')['missing_data']
    assert client.get(f"/api/v1/market/briefs/{report['id']}/export").status_code == 200
    role(client, 'Buyer')
    assert client.get(f"/api/v1/market/briefs/{report['id']}/export").status_code == 404
    role(client)
    result = client.put(f"/api/v1/market/briefs/{report['id']}/review", json={'status': 'REVIEWED'})
    assert result.status_code == 200 and result.json()['review_status'] == 'REVIEWED'
    with Session() as db:
        source = db.get(Record, id); source.region = 'Region 2'; db.commit()
    assert client.get(f"/api/v1/market/briefs/{report['id']}/export").status_code == 404


def test_ai_brief_rejects_fabricated_citation_ids(client, monkeypatch):
    import app.market_research as research
    sourced_series(client, category_id='logistics')
    async def invalid(db, messages, **kwargs):
        return json.dumps({'sections': [{'title': title, 'text': 'Unsupported claim.', 'citation_ids': ['fabricated-source'], 'missing_data': False} for title in research.SECTIONS]}), {}
    monkeypatch.setattr(research, 'azure_call', invalid)
    result = client.post('/api/v1/market/briefs', json={'category_id': 'logistics', 'mode': 'ai'})
    assert result.status_code == 502
    async def valid(db, messages, **kwargs):
        source_ids = [source['id'] for source in json.loads(messages[-1]['content'])['sources']]
        assert source_ids and 'secret-b' not in source_ids
        return json.dumps({'sections': [{'title': title, 'text': 'Sourced assessment.', 'citation_ids': source_ids[:1], 'missing_data': False} for title in research.SECTIONS]}), {'total_tokens': 100}
    monkeypatch.setattr(research, 'azure_call', valid)
    result = client.post('/api/v1/market/briefs', json={'category_id': 'logistics', 'mode': 'ai'})
    assert result.status_code == 200, result.text


def test_brief_sharing_requires_source_access_and_can_be_revoked(client):
    sourced_series(client, category_id='subsea')
    report = client.post('/api/v1/market/briefs', json={'category_id': 'subsea', 'shared_with': ['Buyer']}).json()
    role(client, 'Buyer')
    assert client.get(f"/api/v1/market/briefs/{report['id']}/export").status_code == 200
    assert client.put(f"/api/v1/market/briefs/{report['id']}/sharing", json={'shared_with': ['Fungsi Pengguna']}).status_code == 403
    role(client)
    assert client.put(f"/api/v1/market/briefs/{report['id']}/sharing", json={'shared_with': []}).status_code == 200
    role(client, 'Buyer')
    assert client.get(f"/api/v1/market/briefs/{report['id']}/export").status_code == 404
    role(client)
    with Session() as db:
        db.add(Record(kind='document', owner='Market Intelligence Analyst', region='Region 1', classification='RESTRICTED', data={'name': 'Restricted subsea source', 'category_id': 'subsea', 'text': 'Private data'})); db.commit()
    assert client.post('/api/v1/market/briefs', json={'category_id': 'subsea', 'shared_with': ['Buyer']}).status_code == 422


def test_json_market_feed_contract_and_exploration_key_schedule_guard(client, monkeypatch):
    import app.market_automation as automation
    id = series(client)
    role(client, 'Admin'); monkeypatch.setenv('MARKET_API_ALLOWED_HOSTS', 'feed.company.example')
    provider = client.post('/api/v1/market/providers', json={'name': 'Approved company feed', 'provider': 'json', 'series_id': id, 'endpoint': 'https://feed.company.example/observations', 'api_key': 'feed-test-key'}).json()
    original = httpx.AsyncClient
    def handler(request):
        assert request.url.host == 'feed.company.example'
        assert request.headers['Authorization'] == 'Bearer feed-test-key'
        assert not request.url.query
        return httpx.Response(200, json={'observations': [{'date': '2024-01-01', 'value': '100.50', 'source': 'Authorized external bulletin'}]})
    monkeypatch.setattr(automation.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    role(client)
    synced = client.post(f"/api/v1/market/providers/{provider['id']}/sync", json={})
    assert synced.status_code == 200, synced.text
    assert synced.json()['inserted'] == 1
    energy = series(client, commodity='Brent crude', unit='BBL', category_id='logistics')
    role(client, 'Admin')
    eia = client.post('/api/v1/market/providers', json={'name': 'EIA exploration', 'provider': 'eia', 'series_id': energy}).json()
    role(client)
    result = client.post('/api/v1/market/schedules', json={'title': 'Regular EIA sync', 'task_type': 'provider_sync', 'target_id': eia['id']})
    assert result.status_code == 422


def test_alerts_are_idempotent_private_and_use_matching_dates(client):
    id = sourced_series(client)
    rule = client.post('/api/v1/market/rules', json={'title': 'Steel increase over ten percent', 'category_id': 'octg', 'metric': 'change_pct', 'series_id': id, 'threshold': 10, 'period': 'mom'}).json()
    assert client.post('/api/v1/market/rules/evaluate', json={}).status_code == 200
    own = [row for row in client.get('/api/v1/market/alerts').json() if row['rule_id'] == rule['id']]
    assert len(own) == 1 and own[0]['value'] == 25
    client.post('/api/v1/market/rules/evaluate', json={})
    assert len([row for row in client.get('/api/v1/market/alerts').json() if row['rule_id'] == rule['id']]) == 1
    assert client.put('/api/v1/market/alerts/' + own[0]['id'], json={'status': 'ACKNOWLEDGED'}).status_code == 200
    role(client, 'Buyer')
    assert not any(row['rule_id'] == rule['id'] for row in client.get('/api/v1/market/alerts').json())
    assert client.put('/api/v1/market/alerts/' + own[0]['id'], json={'status': 'RESOLVED'}).status_code == 404
    role(client)
    baseline = series(client)
    observe(client, baseline, [{'date': '2024-01-01', 'value': 50}])
    gap = client.post('/api/v1/market/rules', json={'title': 'Quote premium', 'category_id': 'octg', 'metric': 'benchmark_gap', 'series_id': id, 'benchmark_id': baseline, 'threshold': 10}).json()
    client.post('/api/v1/market/rules/evaluate', json={})
    assert not any(row['rule_id'] == gap['id'] for row in client.get('/api/v1/market/alerts').json())


def test_new_document_alert_excludes_existing_demo_and_other_regions(client):
    role(client)
    result = client.post('/api/v1/market/rules', json={'title': 'New OCTG report', 'category_id': 'octg', 'metric': 'new_document'})
    assert result.status_code == 200
    rule_id = result.json()['id']; ids = [uid(), uid(), uid()]
    with Session() as db:
        for id, region, demo in zip(ids, ['Region 1', 'Region 2', 'Region 1'], [False, False, True]):
            db.add(Record(id=id, kind='document', region=region, owner='Buyer', data={'name': 'New source', 'category_id': 'octg', 'status': 'Indexed', 'is_demo': demo}))
        db.commit()
    client.post('/api/v1/market/rules/evaluate', json={})
    alerts = [row for row in client.get('/api/v1/market/alerts').json() if row['rule_id'] == rule_id]
    assert len(alerts) == 1 and alerts[0]['source_ids'] == ids[:1]


def test_provider_secret_and_live_contract_are_validated_without_network(client, monkeypatch):
    import app.market_automation as automation
    id = series(client, commodity='Brent crude', unit='BBL', category_id='logistics')
    role(client, 'Admin')
    provider = client.post('/api/v1/market/providers', json={'name': 'EIA test connector', 'provider': 'eia', 'series_id': id, 'api_key': 'test-provider-key'}).json()
    assert 'test-provider-key' not in json.dumps(provider)
    with Session() as db: assert 'test-provider-key' not in db.get(Config, 'market:' + provider['id']).secret
    original = httpx.AsyncClient
    def handler(request):
        assert request.url.host == 'api.eia.gov' and request.url.params['api_key'] == 'test-provider-key'
        assert request.url.params['facets[series][]'] == 'RBRTE'
        return httpx.Response(200, json={'response': {'data': [{'period': '2024-01', 'value': '80.25', 'series': 'RBRTE', 'units': '$/BBL'}]}})
    monkeypatch.setattr(automation.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    tested = client.post(f"/api/v1/market/providers/{provider['id']}/test", json={})
    assert tested.status_code == 200 and tested.json()['data_saved'] is False
    role(client)
    result = client.post(f"/api/v1/market/providers/{provider['id']}/sync", json={})
    assert result.status_code == 200 and result.json()['inserted'] == 1
    assert client.get('/api/v1/market/series/' + id).json()['statistics']['latest'] == 80.25
    assert client.post(f"/api/v1/market/providers/{provider['id']}/sync", json={}).json()['unchanged'] == 1
    role(client, 'Admin')
    assert client.post('/api/v1/market/providers', json={'name': 'Bad source', 'provider': 'json', 'series_id': id, 'endpoint': 'https://127.0.0.1/secrets'}).status_code == 422


def test_scheduled_brief_is_durable_and_failed_runs_are_visible(client):
    sourced_series(client, category_id='maintenance')
    body = {'title': 'Maintenance weekly brief', 'task_type': 'brief', 'target_id': 'maintenance', 'interval_hours': 168, 'mode': 'evidence'}
    schedule = client.post('/api/v1/market/schedules', json=body)
    assert schedule.status_code == 200, schedule.text
    id = schedule.json()['id']
    run = client.post(f'/api/v1/market/schedules/{id}/run', json={}).json()
    assert client.post(f'/api/v1/market/schedules/{id}/run', json={}).json()['id'] == run['id']
    assert asyncio.run(process_market_run())
    with Session() as db:
        done = db.get(MarketRun, run['id'])
        assert done.status == 'COMPLETED' and db.get(Record, done.result_id).kind == 'market_brief'
        row = db.get(Record, id); row.data = {**row.data, 'next_run': (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}; db.commit()
    queue_due_schedules(); queue_due_schedules()
    with Session() as db:
        pending = list(db.scalars(select(MarketRun).where(MarketRun.task_id == id, MarketRun.status == 'PENDING')))
        assert len(pending) == 1
        row = db.get(Record, id); row.data = {**row.data, 'target_id': 'unavailable-category'}; db.commit()
    assert asyncio.run(process_market_run())
    result = next(row for row in client.get('/api/v1/market/schedules').json() if row['id'] == id)
    assert result['runs'][0]['status'] == 'FAILED' and result['runs'][0]['error']


def test_advanced_rfi_analysis_identifies_numeric_deviations(client):
    role(client, 'Buyer')
    supplier_ids = []
    for name in ['Supplier Alpha', 'Supplier Beta', 'Supplier Gamma']:
        result = client.post('/api/v1/suppliers', json={'name': name, 'category_id': 'rotating', 'country': 'Indonesia'})
        assert result.status_code == 200
        supplier_ids.append(result.json()['id'])
    rfi = client.post('/api/v1/rfis', json={'title': 'Advanced comparison RFI', 'category_id': 'rotating', 'closing_date': '2099-12-20', 'requirement': 'Compressor delivery requirements for testing.', 'supplier_ids': supplier_ids, 'questions': [{'id': 'lead', 'text': 'Lead time in weeks', 'type': 'integer', 'required': True}]}).json()
    for status in ['Internal Review', 'Approved', 'Issued']:
        assert client.post(f"/api/v1/rfis/{rfi['id']}/status", json={'status': status}).status_code == 200
    links = client.post(f"/api/v1/rfis/{rfi['id']}/invitations", json={}).json()
    for invitation, value in zip(links, [10, 12, 40]):
        token = invitation['path'].split('=')[1]
        assert client.post('/api/v1/respond/' + token, json={'answers': {'lead': value}, 'submit': True}).status_code == 200
    result = client.post(f"/api/v1/market/rfis/{rfi['id']}/analysis", json={'mode': 'evidence'})
    assert result.status_code == 200, result.text
    finding = result.json()['findings'][0]
    assert finding['median'] == 12 and len(finding['outlier_response_ids']) == 1
    assert len([c for c in result.json()['citations'] if c['kind'] == 'response']) == 3


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='PostgreSQL concurrent row-lock behavior')
def test_concurrent_observations_remain_unique(client):
    from concurrent.futures import ThreadPoolExecutor
    id = series(client)
    body = {'observations': [{'date': '2024-01-01', 'value': 100}]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(f'/api/v1/market/series/{id}/observations', json=body), range(2)))
    assert all(result.status_code == 200 for result in results)
    assert sum(result.json()['inserted'] for result in results) == 1
    assert client.get('/api/v1/market/series/' + id).json()['statistics']['count'] == 1
