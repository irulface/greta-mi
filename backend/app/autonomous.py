"""Phase 4: owner-scoped periodic observe → compare → assess → alert agents."""
import asyncio
from time import monotonic
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import Field, model_validator
from sqlalchemy import select, func
from .db import AgentRun, Config, MarketPoint, Record, Session, User, now, uid
from .security import audit, current_user, db_session, require
from .market import StrictInput, PointsInput, get, public, records, upsert_points, parse_import
from .agent_evidence import (DOMAINS, OperationalMetric, metric_contract, local_evidence, add_enterprise, finalize_coverage, qualify_snapshot,
    snapshot_access, snapshot_sources, compare_snapshots, merged_baseline, assessment, summarize, fingerprint)

router = APIRouter(prefix='/api/v1/agents', tags=['Autonomous intelligence'])
ACTIVE = ['PENDING', 'RUNNING']


class SignalInput(OperationalMetric):
    name: str = Field(min_length=3, max_length=150)
    category_id: str
    source: str = Field(min_length=5, max_length=500)
    notes: str = Field(default='', max_length=3000)


@router.get('/signals')
def signals(category: str = '', user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement')
    result = []
    for row in records(db, user, 'agent_signal', category):
        recent = list(db.scalars(select(MarketPoint).where(MarketPoint.series_id == row.id).order_by(MarketPoint.observed_on.desc()).limit(100)))
        result.append({**public(row), 'observations': [{'date': p.observed_on, 'value': float(p.value), 'confidence': float(p.confidence),
            'source': p.source, 'notes': p.notes, 'updated_at': p.updated_at} for p in reversed(recent)]})
    return result


@router.post('/signals')
def add_signal(body: SignalInput, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, body.category_id, 'category'); metric_contract(body)
    row = Record(kind='agent_signal', owner=user.id, region=user.region, classification='CONFIDENTIAL', data={**body.model_dump(), 'is_demo': False})
    db.add(row); db.flush(); audit(db, user, 'agent.signal.created', row.id); db.commit(); return public(row)


def add_values(db, user, id, body):
    require(user, 'procurement'); row = get(db, user, id, 'agent_signal', lock=True)
    if row.owner != user.id and user.role != 'Market Intelligence Analyst': raise HTTPException(403, 'Observasi dikelola pemilik atau Analyst.')
    if any(p.value < 0 or (row.data['metric'] == 'po_overdue_count' and p.value != int(p.value)) for p in body.observations):
        raise HTTPException(422, 'Nilai operasional tidak boleh negatif; jumlah PO harus integer.')
    result = upsert_points(db, user, row, body); db.commit(); return result


@router.post('/signals/{id}/observations')
def observations(id: str, body: PointsInput, user=Depends(current_user), db=Depends(db_session)):
    return add_values(db, user, id, body)


@router.post('/signals/{id}/import')
async def import_signal(id: str, file: UploadFile = File(...), user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, id, 'agent_signal')
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024: raise HTTPException(413, 'Maksimum file 5 MB.')
    parsed = parse_import(content, file.filename or '')
    return add_values(db, user, id, PointsInput(observations=parsed))


class Policy(StrictInput):
    demand_change_pct: float = Field(default=15, gt=0, le=1000)
    lead_time_change_pct: float = Field(default=20, gt=0, le=1000)
    price_change_pct: float = Field(default=10, gt=0, le=1000)
    po_change_pct: float = Field(default=15, gt=0, le=1000)
    inventory_critical_months: float = Field(default=3, gt=0, le=120)
    inventory_watch_months: float = Field(default=6, gt=0, le=240)

    @model_validator(mode='after')
    def ordered(self):
        if self.inventory_watch_months <= self.inventory_critical_months: raise ValueError('Watch coverage must exceed critical coverage')
        return self


class AgentInput(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    category_id: str
    signal_ids: list[str] = Field(default_factory=list, max_length=30)
    interval_minutes: int = Field(default=1440, ge=15, le=10080)
    max_source_age_days: int = Field(default=90, ge=1, le=730)
    min_confidence: float = Field(default=.5, ge=0, le=1)
    runtime_seconds: int = Field(default=150, ge=15, le=300)
    use_mcp: bool = False
    include_demo: bool = False
    enabled: bool = False
    policy: Policy = Field(default_factory=Policy)
    version: int = Field(default=1, ge=1)


def system_enabled(db, region):
    config = db.get(Config, 'agent-control:' + region)
    return not config or config.data.get('enabled', True)


def owner(db, user, id, lock=False):
    require(user, 'procurement'); row = get(db, user, id, 'autonomous_agent', lock=lock)
    if row.owner != user.id: raise HTTPException(403, 'Hanya pemilik dapat mengubah atau menjalankan agent.')
    return row


def validate_plan(db, user, body):
    require(user, 'procurement'); get(db, user, body.category_id, 'category')
    if len(set(body.signal_ids)) != len(body.signal_ids): raise HTTPException(422, 'Pilih signal yang unik.')
    for id in body.signal_ids:
        row = get(db, user, id, 'agent_signal')
        if row.data['category_id'] != body.category_id: raise HTTPException(422, 'Signal harus dalam kategori agent.')
    if body.use_mcp:
        config = db.get(Config, 'mcp')
        if not config or not config.data.get('enabled'): raise HTTPException(409, 'Konfigurasikan internal MCP sebelum mengaktifkan pembacaan enterprise.')


def cancel_active(db, id, reason):
    for run in db.scalars(select(AgentRun).where(AgentRun.agent_id == id, AgentRun.status.in_(ACTIVE)).with_for_update()):
        run.status = 'CANCELLED'; run.error = reason; run.finished_at = now(); run.lease = None


def run_public(db, user, run, details=False):
    safe = {'id': run.id, 'agent_id': run.agent_id, 'status': run.status, 'trigger': run.trigger, 'version': run.version,
            'created_at': run.created_at, 'started_at': run.started_at, 'finished_at': run.finished_at, 'error': run.error}
    # A comparison may contain old evidence as well as current evidence.
    can_read = snapshot_access(db, user, run.snapshot) and snapshot_access(db, user, run.baseline)
    safe['evidence_available'] = can_read
    if can_read:
        safe['result'] = run.result
        if details: safe.update({'snapshot': run.snapshot, 'steps': run.steps, 'config': run.config})
    else: safe['error'] = 'Evidence access changed; report is no longer available to this user.'
    return safe


def agent_public(db, user, row):
    latest = db.scalar(select(AgentRun).where(AgentRun.agent_id == row.id).order_by(AgentRun.created_at.desc()).limit(1))
    data = public(row); data.pop('baseline_run_id', None)
    return {**data, 'can_manage': row.owner == user.id, 'system_enabled': system_enabled(db, row.region),
            'latest_run': run_public(db, user, latest) if latest else None}


@router.get('')
def agents(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); return [agent_public(db, user, r) for r in records(db, user, 'autonomous_agent')]


@router.post('')
def create(body: AgentInput, user=Depends(current_user), db=Depends(db_session)):
    validate_plan(db, user, body)
    row = Record(kind='autonomous_agent', owner=user.id, region=user.region, classification='CONFIDENTIAL', data={**body.model_dump(),
        'version': 1, 'shared_with': [], 'baseline_run_id': None, 'next_run': now() if body.enabled else None})
    db.add(row); db.flush(); audit(db, user, 'agent.created', row.id); db.commit(); return agent_public(db, user, row)


@router.put('/{id}')
def edit(id: str, body: AgentInput, user=Depends(current_user), db=Depends(db_session)):
    row = owner(db, user, id, lock=True); validate_plan(db, user, body)
    if row.data['version'] != body.version: raise HTTPException(409, 'Agent sudah berubah. Muat ulang sebelum menyimpan.')
    cancel_active(db, id, 'Configuration changed; queued work cancelled.')
    row.data = {**body.model_dump(), 'version': body.version + 1, 'shared_with': row.data['shared_with'],
                'baseline_run_id': None, 'next_run': now() if body.enabled else None}
    row.updated_at = now(); audit(db, user, 'agent.updated', id, {'version': body.version + 1, 'baseline_reset': True}); db.commit()
    return agent_public(db, user, row)


class Toggle(StrictInput):
    enabled: bool


@router.post('/{id}/toggle')
def toggle(id: str, body: Toggle, user=Depends(current_user), db=Depends(db_session)):
    row = owner(db, user, id, lock=True)
    cancel_active(db, id, 'Agent paused or restarted by owner.')
    row.data = {**row.data, 'enabled': body.enabled, 'version': row.data['version'] + 1, 'next_run': now() if body.enabled else None}
    row.updated_at = now(); audit(db, user, 'agent.enabled', id, body.model_dump()); db.commit(); return agent_public(db, user, row)


class Sharing(StrictInput):
    user_ids: list[str] = Field(max_length=30)


@router.put('/{id}/sharing')
def sharing(id: str, body: Sharing, user=Depends(current_user), db=Depends(db_session)):
    row = owner(db, user, id, lock=True)
    for sid in body.user_ids:
        recipient = db.get(User, sid)
        if not recipient or not recipient.active or recipient.region != user.region or recipient.role not in ('Buyer', 'Market Intelligence Analyst'): raise HTTPException(422, 'Penerima harus Buyer/Analyst aktif dalam region yang sama.')
        for source_id in row.data['signal_ids']: get(db, recipient, source_id, 'agent_signal')
    row.data = {**row.data, 'shared_with': sorted(set(body.user_ids) - {user.id})}; row.updated_at = now()
    audit(db, user, 'agent.sharing', id, body.model_dump()); db.commit(); return agent_public(db, user, row)


def queue(db, agent, trigger, slot):
    existing = db.scalar(select(AgentRun).where(AgentRun.agent_id == agent.id, AgentRun.status.in_(ACTIVE)))
    if existing: return existing
    run = AgentRun(agent_id=agent.id, owner=agent.owner, version=agent.data['version'], trigger=trigger, slot=slot,
                   config={k: v for k, v in agent.data.items() if k in AgentInput.model_fields})
    db.add(run); db.flush(); return run


@router.post('/{id}/run')
def run_once(id: str, user=Depends(current_user), db=Depends(db_session)):
    row = owner(db, user, id, lock=True)
    if not system_enabled(db, user.region): raise HTTPException(409, 'Eksekusi agent dihentikan Admin.')
    run = queue(db, row, 'manual', 'manual:' + uid()); audit(db, user, 'agent.run.requested', run.id); db.commit()
    return run_public(db, user, run)


@router.get('/{id}/runs')
def runs(id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, id, 'autonomous_agent')
    return [run_public(db, user, r) for r in db.scalars(select(AgentRun).where(AgentRun.agent_id == id).order_by(AgentRun.created_at.desc()).limit(50))]


@router.get('/{id}/runs/{run_id}')
def run_detail(id: str, run_id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); get(db, user, id, 'autonomous_agent'); run = db.get(AgentRun, run_id)
    if not run or run.agent_id != id: raise HTTPException(404)
    return run_public(db, user, run, True)


@router.post('/{id}/runs/{run_id}/cancel')
def cancel(id: str, run_id: str, user=Depends(current_user), db=Depends(db_session)):
    owner(db, user, id, lock=True)
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    if not run or run.agent_id != id: raise HTTPException(404)
    if run.status in ACTIVE:
        run.status = 'CANCELLED'; run.error = 'Cancelled by owner.'; run.lease = None; run.finished_at = now()
        audit(db, user, 'agent.run.cancelled', run_id); db.commit()
    return run_public(db, user, run)


def alert_access(db, user, row):
    agent = db.get(Record, row.data['agent_id'])
    from .market import accessible
    if not accessible(user, agent): return False
    run = db.get(AgentRun, row.data['run_id'])
    return bool(run and snapshot_access(db, user, run.snapshot) and snapshot_access(db, user, run.baseline))


@router.get('/inbox/alerts')
def inbox(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read')
    if user.role not in ('Buyer', 'Market Intelligence Analyst'): return []
    # Recipients follow the agent's current sharing policy, not a stale copied ACL.
    agent_ids = [r.id for r in records(db, user, 'autonomous_agent')]
    return [public(r) for r in db.scalars(select(Record).where(Record.kind == 'agent_alert', Record.region == user.region,
        Record.data['agent_id'].as_string().in_(agent_ids)).order_by(Record.created_at.desc()).limit(500)) if alert_access(db, user, r)][:100]


class Disposition(StrictInput):
    status: Literal['ACKNOWLEDGED', 'RESOLVED']
    note: str = Field(min_length=3, max_length=2000)


@router.put('/inbox/alerts/{id}')
def disposition(id: str, body: Disposition, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); row = db.scalar(select(Record).where(Record.id == id, Record.kind == 'agent_alert').with_for_update())
    if not row or not alert_access(db, user, row): raise HTTPException(404)
    if row.data['status'] == 'RESOLVED': raise HTTPException(409, 'Alert sudah diselesaikan.')
    row.data = {**row.data, 'status': body.status, 'history': [*row.data.get('history', []), {'by': user.id, 'at': now(), **body.model_dump()}]}
    row.updated_at = now(); audit(db, user, 'agent.alert.' + body.status.lower(), id); db.commit(); return public(row)


@router.get('/control/status')
def control_status(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'admin')
    rows = list(db.scalars(select(Record).where(Record.kind == 'autonomous_agent', Record.region == user.region)))
    ids = [r.id for r in rows]
    active = db.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.agent_id.in_(ids), AgentRun.status.in_(ACTIVE)))
    return {'enabled': system_enabled(db, user.region), 'region': user.region, 'agents': len(rows), 'active_runs': active}


@router.put('/control/status')
def control(body: Toggle, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'admin'); id = 'agent-control:' + user.region
    config = db.get(Config, id) or Config(id=id, data={})
    config.data = {'enabled': body.enabled, 'updated_at': now(), 'by': user.id}; db.add(config)
    if not body.enabled:
        for agent in db.scalars(select(Record).where(Record.kind == 'autonomous_agent', Record.region == user.region).with_for_update()): cancel_active(db, agent.id, 'Stopped by region administrator.')
    audit(db, user, 'agent.control', user.region, body.model_dump()); db.commit(); return control_status(user, db)


def queue_due():
    with Session() as db:
        rows = list(db.scalars(select(Record).where(Record.kind == 'autonomous_agent', Record.data['enabled'].as_boolean().is_(True), Record.data['next_run'].as_string() <= now()).with_for_update(skip_locked=True)))
        for agent in rows:
            user = db.get(User, agent.owner)
            if user and user.active and user.role in ('Buyer', 'Market Intelligence Analyst') and system_enabled(db, agent.region):
                queue(db, agent, 'scheduled', agent.data['next_run'])
            agent.data = {**agent.data, 'next_run': (datetime.now(timezone.utc) + timedelta(minutes=agent.data['interval_minutes'])).isoformat()}
        db.commit()


class Abandoned(Exception): pass


def validate_claim(db, run, lease):
    if not run or run.status != 'RUNNING' or run.lease != lease: raise Abandoned()
    agent = db.get(Record, run.agent_id); user = db.get(User, run.owner)
    if not agent or agent.data['version'] != run.version or not user or not user.active or user.role not in ('Buyer', 'Market Intelligence Analyst') or user.region != agent.region or not system_enabled(db, agent.region): raise Abandoned()
    get(db, user, agent.data['category_id'], 'category')
    return agent, user


def recover_interrupted():
    with Session() as db:
        for run in db.scalars(select(AgentRun).where(AgentRun.status == 'RUNNING').with_for_update(skip_locked=True)):
            deadline = datetime.fromisoformat(run.started_at) + timedelta(seconds=run.config['runtime_seconds'] + 30)
            if datetime.now(timezone.utc) > deadline:
                run.status = 'FAILED'; run.error = 'Worker lease expired. No partial result was published.'; run.lease = None; run.finished_at = now()
                audit(db, run.owner, 'agent.run.interrupted', run.id)
        db.commit()


async def process_agent_run():
    with Session() as db:
        run = db.scalar(select(AgentRun).where(AgentRun.status == 'PENDING').order_by(AgentRun.created_at).with_for_update(skip_locked=True).limit(1))
        if not run: return False
        lease = uid(); run.lease = lease; run.status = 'RUNNING'; run.started_at = now(); id = run.id; config = run.config
        run.steps = [{'step': 'PLAN', 'at': now(), 'detail': 'Read scoped evidence, compare last baseline, assess risk, publish in-app change alert.'}]; db.commit()
    deadline = monotonic() + config['runtime_seconds']

    async def checkpoint(step, detail):
        if monotonic() >= deadline: raise TimeoutError()
        with Session() as db:
            run = db.scalar(select(AgentRun).where(AgentRun.id == id).with_for_update())
            validate_claim(db, run, lease)
            run.steps = [*run.steps, {'step': step, 'at': now(), 'detail': detail}]; db.commit()

    async def execute():
        await checkpoint('READ_LOCAL', 'Evaluate RFI, market data, supplier records, price, events and selected operational metrics.')
        with Session() as db:
            run = db.get(AgentRun, id); agent, user = validate_claim(db, run, lease)
            previous_id = agent.data.get('baseline_run_id')
            previous = db.get(AgentRun, previous_id) if previous_id else None
            # Revoked historical evidence cannot be used to create a new report.
            prior = previous.baseline if previous and snapshot_access(db, user, previous.baseline) else {}
            last_snapshot = previous.snapshot if prior else {}
            prior_risk = previous.result.get('risk', {}).get('level') if prior else None
            snapshot = local_evidence(db, user, config)
            await add_enterprise(snapshot, db, user, config, checkpoint)
        await checkpoint('COMPARE', 'Compare matching measurement bases; missing sources never become zero values.')
        snapshot = finalize_coverage(qualify_snapshot(snapshot, prior, config))
        baseline = merged_baseline(prior, snapshot)
        changes = compare_snapshots(prior, snapshot, config['policy'])
        if prior:
            for domain in DOMAINS:
                before = last_snapshot.get('coverage', {}).get(domain, {}).get('state', 'MISSING'); after = snapshot['coverage'][domain]['state']
                if before != after: changes.append({'key': 'coverage:' + domain, 'domain': domain, 'label': domain + ' evidence coverage', 'type': 'COVERAGE_CHANGED', 'before': before, 'after': after, 'material': True, 'severity': 'MEDIUM' if after != 'AVAILABLE' else 'INFO'})
        risk = assessment(snapshot, baseline, config['policy'])
        if prior and prior_risk != risk['level'] and not any(c['material'] for c in changes):
            changes.append({'key': 'observed-risk', 'domain': 'Risk assessment', 'label': 'Observed procurement risk',
                'type': 'RISK_CHANGED', 'before': prior_risk, 'after': risk['level'], 'material': True,
                'severity': 'HIGH' if risk['level'] == 'HIGH' else 'MEDIUM'})
        report = {'initial_baseline': not bool(prior), 'risk': risk, 'previous_risk': prior_risk, 'changes': changes,
                  'material_changes': sum(c['material'] for c in changes), 'summary': summarize(changes, prior_risk, risk, not bool(prior)),
                  'coverage': snapshot['coverage'], 'is_demo': config['include_demo'], 'alert_id': None}
        await checkpoint('ASSESS', 'Apply explicit thresholds and identify evidence gaps; no purchase or external write is permitted.')
        # Commit alert, baseline and terminal status atomically under current configuration and ACLs.
        with Session() as db:
            run = db.get(AgentRun, id)
            agent = db.scalar(select(Record).where(Record.id == run.agent_id).with_for_update())
            run = db.scalar(select(AgentRun).where(AgentRun.id == id).with_for_update().execution_options(populate_existing=True))
            agent, user = validate_claim(db, run, lease)
            if not snapshot_access(db, user, snapshot) or not snapshot_access(db, user, baseline): raise Abandoned()
            material = [c for c in changes if c['material']]
            if prior and material:
                key = 'agent-alert-' + fingerprint({'agent': agent.id, 'run': run.id, 'version': run.version, 'changes': sorted(material, key=lambda c: c['key']), 'risk': risk['level']})
                if not db.get(Record, key):
                    row = Record(id=key, kind='agent_alert', owner=user.id, region=agent.region, classification='CONFIDENTIAL', data={
                        'agent_id': agent.id, 'run_id': run.id, 'category_id': config['category_id'], 'title': agent.data['name'] + ' — what changed',
                        'message': report['summary'], 'severity': 'HIGH' if risk['level'] == 'HIGH' else 'MEDIUM' if any(c['severity'] == 'MEDIUM' for c in material) else 'INFO',
                        'status': 'OPEN', 'detected_at': now(), 'source_ids': sorted(set(snapshot_sources(snapshot) + snapshot_sources(baseline))),
                        'history': [], 'is_demo': config['include_demo'], 'channel': 'in_app'})
                    db.add(row); audit(db, user, 'agent.alert.published', key)
                report['alert_id'] = key
            run.snapshot = snapshot; run.baseline = baseline; run.result = report
            run.status = 'COMPLETED' if all(c['state'] == 'AVAILABLE' for c in snapshot['coverage'].values()) else 'PARTIAL'
            run.steps = [*run.steps, {'step': 'PUBLISH', 'at': now(), 'detail': 'In-app alert saved.' if report['alert_id'] else 'Baseline saved; no material change alert.'}]
            run.finished_at = now(); run.lease = None; agent.data = {**agent.data, 'baseline_run_id': run.id}
            audit(db, user, 'agent.run.' + run.status.lower(), run.id, {'material_changes': report['material_changes']})
            if monotonic() >= deadline: raise TimeoutError()
            db.commit()

    try: await asyncio.wait_for(execute(), timeout=config['runtime_seconds'])
    except Exception as exc:
        with Session() as db:
            run = db.scalar(select(AgentRun).where(AgentRun.id == id).with_for_update())
            if run.status == 'RUNNING' and run.lease == lease:
                run.status = 'CANCELLED' if isinstance(exc, Abandoned) else 'FAILED'
                run.error = 'Authorization or configuration changed; result discarded.' if isinstance(exc, Abandoned) else 'Time budget exceeded; result discarded.' if isinstance(exc, TimeoutError) else 'Evaluation failed; previous baseline retained.'
                run.lease = None; run.finished_at = now(); audit(db, run.owner, 'agent.run.' + run.status.lower(), id); db.commit()
    return True


async def agent_tick():
    recover_interrupted(); queue_due(); await process_agent_run()
