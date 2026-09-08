"""Market feeds, personal alerts and durable scheduled research."""
import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select

from .db import Config, MarketPoint, MarketRun, Record, Session, User, now, uid
from .security import PERMISSIONS, audit, cipher, current_user, db_session, require
from .market import StrictInput, PointInput, PointsInput, accessible, change, get, points, public, records, statistics_for, upsert_points
from .market_research import BriefInput, generate_brief, researcher

router = APIRouter(prefix='/api/v1/market', tags=['Market automation'])
EIA_URL = 'https://api.eia.gov/v2/petroleum/pri/spt/data/'
EIA_SERIES = {'brent': ('RBRTE', 'Europe Brent Spot Price FOB'), 'wti': ('RWTC', 'Cushing WTI Spot Price FOB')}


class ProviderInput(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    provider: Literal['eia', 'json']
    series_id: str
    benchmark: Literal['brent', 'wti'] = 'brent'
    endpoint: str = Field(default='', max_length=1000)
    api_key: str = Field(default='', max_length=2000)
    enabled: bool = True


def validate_endpoint(endpoint):
    parsed = urlparse(endpoint)
    allowed = {host.strip() for host in os.getenv('MARKET_API_ALLOWED_HOSTS', '').split(',') if host.strip()}
    try: valid_port = parsed.port in (None, 443)
    except ValueError: valid_port = False
    if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password or parsed.query or parsed.fragment or not valid_port:
        raise HTTPException(422, 'Endpoint JSON harus HTTPS, tanpa query/credential, dan host terdaftar di MARKET_API_ALLOWED_HOSTS.')


def provider_public(db, row):
    config = db.get(Config, 'market:' + row.id)
    return {**public(row), 'has_secret': bool(config and config.secret), 'using_demo_key': row.data['provider'] == 'eia' and not (config and config.secret)}


@router.get('/providers')
def providers(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read'); return [provider_public(db, row) for row in records(db, user, 'market_provider')]


def save_provider(db, user, body, row=None):
    require(user, 'admin'); series = get(db, user, body.series_id, 'price')
    if series.data.get('is_demo'): raise HTTPException(422, 'Pilih seri nyata sebagai target API.')
    if body.provider == 'json': validate_endpoint(body.endpoint)
    if body.provider == 'eia' and (series.data.get('currency') != 'USD' or series.data.get('unit') != 'BBL' or series.data.get('frequency') != 'monthly' or series.data.get('metric_type') != 'price'):
        raise HTTPException(422, 'EIA spot price memerlukan seri harga USD / BBL dengan frekuensi monthly.')
    row = row or Record(kind='market_provider', owner=user.id, region=user.region, data={})
    data = body.model_dump(); data.pop('api_key')
    if body.provider == 'eia': data['endpoint'] = EIA_URL
    row.data = data; db.add(row); db.flush()
    config = db.get(Config, 'market:' + row.id) or Config(id='market:' + row.id, data={})
    if body.api_key: config.secret = cipher().encrypt(body.api_key.encode()).decode()
    db.add(config); audit(db, user, 'market.provider.saved', row.id); db.commit(); return provider_public(db, row)


@router.post('/providers')
def create_provider(body: ProviderInput, user=Depends(current_user), db=Depends(db_session)):
    return save_provider(db, user, body)


@router.put('/providers/{id}')
def update_provider(id: str, body: ProviderInput, user=Depends(current_user), db=Depends(db_session)):
    return save_provider(db, user, body, get(db, user, id, 'market_provider', lock=True))


async def fetch_feed(db, provider):
    if not provider.data['enabled']: raise HTTPException(409, 'Konektor dinonaktifkan.')
    config = db.get(Config, 'market:' + provider.id)
    secret = cipher().decrypt(config.secret.encode()).decode() if config and config.secret else ''
    if provider.data['provider'] == 'eia':
        endpoint = EIA_URL; headers = {}
        params = {'api_key': secret or 'DEMO_KEY', 'frequency': 'monthly', 'data[0]': 'value',
                  'facets[series][]': EIA_SERIES[provider.data['benchmark']][0],
                  'sort[0][column]': 'period', 'sort[0][direction]': 'desc', 'length': 120}
    else:
        endpoint = provider.data['endpoint']; validate_endpoint(endpoint)
        params = {}; headers = {'Authorization': 'Bearer ' + secret} if secret else {}
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            async with client.stream('GET', endpoint, params=params, headers=headers) as response:
                if response.status_code != 200: raise HTTPException(502, f'API pasar mengembalikan status {response.status_code}. Periksa konfigurasi atau kuota.')
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 5 * 1024 * 1024: raise HTTPException(502, 'Respons API melebihi 5 MB.')
        payload = json.loads(content)
        if provider.data['provider'] == 'eia':
            data = payload['response']['data']
            expected = EIA_SERIES[provider.data['benchmark']][0]
            observations = []
            for item in data:
                if item.get('value') in (None, ''): continue
                if item.get('series') != expected or item.get('units') != '$/BBL': raise ValueError('Unexpected EIA series or unit')
                observations.append(PointInput(date=item['period'] + '-01', value=item['value'], confidence=1,
                    source='U.S. EIA — ' + EIA_SERIES[provider.data['benchmark']][1], notes='Monthly spot price average; publication date may follow the observation month.'))
        else:
            observations = [PointInput.model_validate(item) for item in payload['observations']]
        return PointsInput(observations=observations, replace_existing=True)
    except HTTPException: raise
    except httpx.HTTPError as exc: raise HTTPException(502, 'API pasar tidak dapat dihubungi atau timeout.') from exc
    except (ValueError, KeyError, TypeError) as exc: raise HTTPException(502, 'Schema, nilai, atau unit respons API tidak sesuai kontrak.') from exc


async def sync_provider(db, user, provider):
    require(user, 'market:write')
    if not accessible(user, provider): raise HTTPException(404)
    observations = await fetch_feed(db, provider)
    series = get(db, user, provider.data['series_id'], 'price', lock=True)
    result = upsert_points(db, user, series, observations)
    provider.data = {**provider.data, 'last_sync': now(), 'last_result': result}
    audit(db, user, 'market.provider.synced', provider.id, result); db.commit(); return result


@router.post('/providers/{id}/sync')
async def sync(id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:write'); return await sync_provider(db, user, get(db, user, id, 'market_provider'))


@router.post('/providers/{id}/test')
async def test_provider(id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'admin'); row = get(db, user, id, 'market_provider')
    body = await fetch_feed(db, row)
    audit(db, user, 'market.provider.test', id, {'count': len(body.observations)}); db.commit()
    return {'status': 'Connected', 'observations': len(body.observations), 'data_saved': False}


class RuleInput(StrictInput):
    title: str = Field(min_length=3, max_length=200)
    category_id: str
    metric: Literal['change_pct', 'above', 'below', 'benchmark_gap', 'new_document', 'market_event']
    series_id: str = ''
    benchmark_id: str = ''
    threshold: float = Field(default=10, ge=-1000000, le=1000000)
    period: Literal['mom', 'qoq', 'yoy', 'previous'] = 'mom'
    severity: Literal['Low', 'Medium', 'High'] = 'Medium'
    enabled: bool = True


def validate_rule(db, user, body):
    researcher(user); get(db, user, body.category_id, 'category')
    if body.metric not in ('new_document', 'market_event'):
        series = get(db, user, body.series_id, 'price')
        if series.data.get('is_demo') or series.data['category_id'] != body.category_id: raise HTTPException(422, 'Pilih seri nyata pada kategori aturan.')
        if body.metric == 'benchmark_gap':
            baseline = get(db, user, body.benchmark_id, 'price')
            dimensions = ['commodity', 'currency', 'unit', 'metric_type', 'category_id']
            if baseline.data.get('is_demo') or baseline.id == series.id or any(series.data.get(k) != baseline.data.get(k) for k in dimensions):
                raise HTTPException(422, 'Benchmark harus berbeda dan mempunyai commodity, currency, unit, metrik, serta kategori yang sama.')


@router.get('/rules')
def rules(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read'); return [public(row) for row in records(db, user, 'alert_rule')]


@router.post('/rules')
def create_rule(body: RuleInput, user=Depends(current_user), db=Depends(db_session)):
    validate_rule(db, user, body)
    row = Record(kind='alert_rule', owner=user.id, region=user.region, data={**body.model_dump(), 'version': 1})
    db.add(row); db.flush(); audit(db, user, 'market.rule.created', row.id); db.commit(); return public(row)


@router.put('/rules/{id}')
def edit_rule(id: str, body: RuleInput, user=Depends(current_user), db=Depends(db_session)):
    validate_rule(db, user, body); row = get(db, user, id, 'alert_rule', lock=True)
    row.data = {**body.model_dump(), 'version': row.data['version'] + 1}; row.updated_at = now()
    audit(db, user, 'market.rule.updated', id); db.commit(); return public(row)


def evaluate_rule(db, user, rule):
    if not rule.data.get('enabled'): return 0
    if not accessible(user, rule): return 0
    data = rule.data; candidates = []
    if data['metric'] in ('new_document', 'market_event'):
        kind = 'document' if data['metric'] == 'new_document' else 'event'
        for row in records(db, user, kind, data['category_id'], False):
            if row.created_at < rule.created_at: continue
            if kind == 'document' and row.data.get('status') != 'Indexed': continue
            candidates.append((row.id + ':' + str(row.data.get('version', 1)), 'Sumber baru: ' + row.data.get('name', row.data.get('title', row.id)), [row.id], None))
    else:
        series = get(db, user, data['series_id'], 'price')
        observations = points(db, series)
        if not observations: return 0
        latest = observations[-1]; source_ids = [series.id]
        value = latest['value']
        if data['metric'] == 'change_pct':
            value = change(value, observations[-2]['value']) if data['period'] == 'previous' and len(observations) >= 2 else statistics_for(observations).get(data['period'])
        if data['metric'] == 'benchmark_gap':
            baseline = get(db, user, data['benchmark_id'], 'price')
            matched = [p for p in points(db, baseline) if p['date'] == latest['date']]
            if not matched: return 0
            value = change(value, matched[0]['value']); source_ids.append(baseline.id)
        triggered = value is not None and (value < data['threshold'] if data['metric'] == 'below' else value > data['threshold'])
        if triggered:
            unit = '%' if data['metric'] in ('change_pct', 'benchmark_gap') else series.data['unit']
            candidates.append((latest['date'], f"{series.data['name']}: {value:.4g} {unit}; threshold {data['threshold']} ({data['metric']}), per {latest['date']}.", source_ids, value))
    count = 0
    for fingerprint, message, source_ids, value in candidates:
        id = 'alert-' + hashlib.sha256(f"{rule.id}:{data['version']}:{fingerprint}".encode()).hexdigest()
        if db.get(Record, id): continue
        alert = Record(id=id, kind='market_alert', owner=user.id, region=rule.region, data={
            'title': data['title'], 'message': message, 'category_id': data['category_id'], 'rule_id': rule.id,
            'severity': data['severity'], 'status': 'OPEN', 'source_ids': source_ids, 'value': value, 'detected_at': now()})
        db.add(alert); db.flush(); audit(db, user, 'market.alert.triggered', id); count += 1
    rule.data = {**rule.data, 'last_evaluated': now()}
    return count


@router.post('/rules/evaluate')
def evaluate_now(user=Depends(current_user), db=Depends(db_session)):
    researcher(user); count = 0
    ids = [row.id for row in records(db, user, 'alert_rule')]
    for id in ids:
        rule = get(db, user, id, 'alert_rule', lock=True)
        try: count += evaluate_rule(db, user, rule)
        except HTTPException: rule.data = {**rule.data, 'last_error': 'Data source unavailable'}
    db.commit(); return {'created': count}


@router.get('/alerts')
def alerts(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read')
    return [public(row) for row in records(db, user, 'market_alert') if all(accessible(user, db.get(Record, id)) for id in row.data['source_ids'])]


class AlertStatus(StrictInput):
    status: Literal['ACKNOWLEDGED', 'RESOLVED']


@router.put('/alerts/{id}')
def update_alert(id: str, body: AlertStatus, user=Depends(current_user), db=Depends(db_session)):
    row = get(db, user, id, 'market_alert', lock=True)
    row.data = {**row.data, 'status': body.status}; row.updated_at = now()
    audit(db, user, 'market.alert.status', id, {'status': body.status}); db.commit(); return public(row)


class ScheduleInput(StrictInput):
    title: str = Field(min_length=3, max_length=150)
    task_type: Literal['brief', 'provider_sync', 'alerts']
    target_id: str = ''
    interval_hours: int = Field(default=24, ge=1, le=720)
    mode: Literal['evidence', 'ai'] = 'evidence'
    enabled: bool = True


def schedule_permission(db, user, data):
    researcher(user)
    if data['task_type'] == 'brief': get(db, user, data['target_id'], 'category')
    elif data['task_type'] == 'provider_sync':
        require(user, 'market:write'); provider = get(db, user, data['target_id'], 'market_provider')
        credential = db.get(Config, 'market:' + provider.id)
        if provider.data['provider'] == 'eia' and not (credential and credential.secret):
            raise HTTPException(422, 'Atur API key EIA organisasi untuk sinkronisasi terjadwal. DEMO_KEY hanya untuk eksplorasi manual.')


@router.get('/schedules')
def schedules(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read')
    result = []
    for row in records(db, user, 'market_schedule'):
        runs = list(db.scalars(select(MarketRun).where(MarketRun.task_id == row.id).order_by(MarketRun.created_at.desc()).limit(10)))
        result.append({**public(row), 'runs': [{key: getattr(run, key) for key in ['id', 'status', 'result_id', 'error', 'created_at', 'finished_at']} for run in runs]})
    return result


@router.post('/schedules')
def create_schedule(body: ScheduleInput, user=Depends(current_user), db=Depends(db_session)):
    data = body.model_dump(); schedule_permission(db, user, data)
    data['next_run'] = (datetime.now(timezone.utc) + timedelta(hours=body.interval_hours)).isoformat()
    row = Record(kind='market_schedule', owner=user.id, region=user.region, data=data)
    db.add(row); db.flush(); audit(db, user, 'market.schedule.created', row.id); db.commit(); return public(row)


class EnabledInput(StrictInput):
    enabled: bool


@router.put('/schedules/{id}')
def toggle_schedule(id: str, body: EnabledInput, user=Depends(current_user), db=Depends(db_session)):
    row = get(db, user, id, 'market_schedule', lock=True); schedule_permission(db, user, row.data)
    row.data = {**row.data, 'enabled': body.enabled, 'next_run': (datetime.now(timezone.utc) + timedelta(hours=row.data['interval_hours'])).isoformat()}
    audit(db, user, 'market.schedule.enabled', id, body.model_dump()); db.commit(); return public(row)


@router.post('/schedules/{id}/run')
def run_now(id: str, user=Depends(current_user), db=Depends(db_session)):
    row = get(db, user, id, 'market_schedule', lock=True); schedule_permission(db, user, row.data)
    existing = db.scalar(select(MarketRun).where(MarketRun.task_id == id, MarketRun.status.in_(['PENDING', 'RUNNING'])))
    if existing: return {'id': existing.id, 'status': existing.status}
    run = MarketRun(task_id=id, slot='manual-' + uid(), owner=user.id)
    db.add(run); db.flush(); audit(db, user, 'market.schedule.run', id); db.commit(); return {'id': run.id, 'status': run.status}


def queue_due_schedules():
    with Session() as db:
        tasks = list(db.scalars(select(Record).where(Record.kind == 'market_schedule', Record.data['enabled'].as_boolean().is_(True), Record.data['next_run'].as_string() <= now()).with_for_update(skip_locked=True)))
        for task in tasks:
            active = db.scalar(select(MarketRun).where(MarketRun.task_id == task.id, MarketRun.status.in_(['PENDING', 'RUNNING'])))
            if not active: db.add(MarketRun(task_id=task.id, slot=task.data['next_run'], owner=task.owner))
            task.data = {**task.data, 'next_run': (datetime.now(timezone.utc) + timedelta(hours=task.data['interval_hours'])).isoformat()}
        db.commit()


async def process_market_run():
    with Session() as db:
        run = db.scalar(select(MarketRun).where(MarketRun.status == 'PENDING').order_by(MarketRun.created_at).with_for_update(skip_locked=True).limit(1))
        if not run: return False
        run.status = 'RUNNING'; run.started_at = now(); run_id = run.id; db.commit()
    with Session() as db:
        run = db.get(MarketRun, run_id); task = db.get(Record, run.task_id); user = db.get(User, run.owner)
        try:
            if not user or not user.active or not accessible(user, task): raise HTTPException(403, 'Schedule owner no longer authorized')
            schedule_permission(db, user, task.data)
            if task.data['task_type'] == 'brief':
                result = await generate_brief(db, user, BriefInput(category_id=task.data['target_id'], mode=task.data['mode']))
                run.result_id = result['id']
            elif task.data['task_type'] == 'provider_sync':
                await sync_provider(db, user, get(db, user, task.data['target_id'], 'market_provider'))
            else: evaluate_now(user=user, db=db)
            run.status = 'COMPLETED'
        except Exception as exc:
            db.rollback(); run = db.get(MarketRun, run_id)
            run.status = 'FAILED'; run.error = str(exc.detail)[:300] if isinstance(exc, HTTPException) else type(exc).__name__
        run.finished_at = now(); audit(db, run.owner, 'market.run.' + run.status.lower(), run.id); db.commit()
    return True


_next_rule_scan = 0
async def market_tick():
    global _next_rule_scan
    queue_due_schedules()
    await process_market_run()
    if time.monotonic() < _next_rule_scan: return
    _next_rule_scan = time.monotonic() + 60
    with Session() as db:
        interrupted = list(db.scalars(select(MarketRun).where(MarketRun.status == 'RUNNING', MarketRun.started_at < (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()).with_for_update(skip_locked=True)))
        for run in interrupted:
            run.status = 'FAILED'; run.error = 'Worker interrupted. Review results before running again.'; run.finished_at = now()
        db.commit()
        ids = list(db.scalars(select(Record.id).where(Record.kind == 'alert_rule')))
        for id in ids:
            rule = db.scalar(select(Record).where(Record.id == id).with_for_update(skip_locked=True))
            if not rule: continue
            user = db.get(User, rule.owner)
            try:
                if user and user.active and user.role in ('Buyer', 'Market Intelligence Analyst'): evaluate_rule(db, user, rule)
                db.commit()
            except Exception:
                db.rollback()
