"""Allowlisted external evidence and explicitly approved enterprise review packages."""
import ipaddress
import json
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select
from .db import Config, Record, Session, User, WorkflowDelivery, now, uid
from .security import audit, cipher, current_user, db_session, require
from .market import StrictInput, accessible, get, public
from .advanced import analysis, authorize

router = APIRouter(prefix='/api/v1/enterprise', tags=['External MCP and enterprise workflows'])
PROTOCOL = '2025-06-18'
MAX_RESPONSE = 2 * 1024 * 1024


def endpoint_check(endpoint, resolve=False):
    url = urlparse(endpoint)
    allowed = {v.strip().lower() for v in os.getenv('ENTERPRISE_ALLOWED_HOSTS', '').split(',') if v.strip()}
    try: port_ok = url.port in (None, 443)
    except ValueError: port_ok = False
    if url.scheme != 'https' or url.hostname not in allowed or url.username or url.password or url.query or url.fragment or not port_ok:
        raise HTTPException(422, 'Endpoint wajib HTTPS, port 443, tanpa query/credential, dan host ada di ENTERPRISE_ALLOWED_HOSTS.')
    if resolve:
        try:
            addresses = socket.getaddrinfo(url.hostname, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise HTTPException(422, 'External connector hanya boleh mengakses alamat IP publik.')
        except socket.gaierror as exc: raise HTTPException(502, 'DNS konektor tidak tersedia.') from exc
    return (url, addresses[0][4][0]) if resolve else url


class ToolPolicy(StrictInput):
    name: str = Field(pattern=r'^[A-Za-z0-9_.-]{1,100}$')
    description: str = Field(min_length=5, max_length=500)
    parameters: dict[str, Literal['string', 'number', 'boolean']] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list, max_length=20)


class Connector(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    kind: Literal['external_mcp', 'workflow']
    endpoint: str = Field(max_length=1000)
    secret: str = Field(default='', max_length=3000)
    clear_secret: bool = False
    enabled: bool = False
    tools: list[ToolPolicy] = Field(default_factory=list, max_length=30)


def connector_public(row):
    return {'id': row.id, **row.data, 'has_secret': bool(row.secret)}


def connector_get(db, user, id, kind=None):
    row = db.get(Config, id)
    if not row or not id.startswith('enterprise:') or row.data.get('region') != user.region or (kind and row.data['kind'] != kind): raise HTTPException(404)
    return row


@router.get('/connectors')
def connectors(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'market:read')
    if user.role not in ('Admin', 'Buyer', 'Market Intelligence Analyst'): raise HTTPException(403)
    return [connector_public(r) for r in db.scalars(select(Config).where(Config.id.like('enterprise:%'))) if r.data.get('region') == user.region]


def save_connector(db, user, body, row=None):
    require(user, 'admin'); endpoint_check(body.endpoint)
    if len({t.name for t in body.tools}) != len(body.tools): raise HTTPException(422, 'Nama tool harus unik.')
    for tool in body.tools:
        if len(tool.parameters) > 20 or set(tool.required) - set(tool.parameters): raise HTTPException(422, 'Schema parameter tool tidak valid.')
    row = row or Config(id='enterprise:' + uid(), data={})
    row.data = {**body.model_dump(exclude={'secret', 'clear_secret'}), 'region': user.region, 'version': row.data.get('version', 0) + 1}
    if body.clear_secret: row.secret = None
    elif body.secret: row.secret = cipher().encrypt(body.secret.encode()).decode()
    db.add(row); audit(db, user, 'enterprise.connector.saved', row.id, {'version': row.data['version']}); db.commit()
    return connector_public(row)


@router.post('/connectors')
def add_connector(body: Connector, user=Depends(current_user), db=Depends(db_session)): return save_connector(db, user, body)


@router.put('/connectors/{id}')
def edit_connector(id: str, body: Connector, user=Depends(current_user), db=Depends(db_session)):
    return save_connector(db, user, body, connector_get(db, user, id))


def headers_for(row):
    return {'Authorization': 'Bearer ' + cipher().decrypt(row.secret.encode()).decode()} if row.secret else {}


async def bounded_post(client, endpoint, headers, payload):
    url, ip = endpoint_check(endpoint, resolve=True)
    # Pin the validated public address while retaining TLS hostname verification and Host.
    pinned = str(httpx.URL(endpoint).copy_with(host=ip))
    async with client.stream('POST', pinned, headers={**headers, 'Host': url.hostname}, json=payload, extensions={'sni_hostname': url.hostname}) as response:
        content = bytearray()
        async for chunk in response.aiter_bytes():
            content.extend(chunk)
            if len(content) > MAX_RESPONSE: raise HTTPException(502, 'Respons konektor melebihi 2 MB.')
            if 'text/event-stream' in response.headers.get('content-type', '') and 'id' in payload:
                try:
                    rpc_result(bytes(content), response.headers, payload['id'])
                    break
                except HTTPException:
                    pass
        return response.status_code, response.headers, bytes(content)


def rpc_result(content, headers, request_id):
    try:
        if 'text/event-stream' in headers.get('content-type', ''):
            messages = []
            for event in content.decode().replace('\r\n', '\n').split('\n\n'):
                data = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
                if data: messages.append(json.loads(data))
            payload = next(m for m in messages if m.get('id') == request_id)
        else: payload = json.loads(content)
        if payload.get('jsonrpc') != '2.0' or payload.get('id') != request_id or 'error' in payload: raise ValueError()
        result = payload['result']
        if not isinstance(result, dict): raise ValueError()
        return result
    except (ValueError, KeyError, TypeError, StopIteration, AttributeError) as exc:
        raise HTTPException(502, 'Respons MCP tidak sesuai protokol atau mengandung error.') from exc


async def external_rpc(row, tool=None, parameters=None):
    if not row.data['enabled']: raise HTTPException(409, 'Konektor dinonaktifkan.')
    headers = {**headers_for(row), 'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}
    endpoint = row.data['endpoint']
    async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
        status, response_headers, content = await bounded_post(client, endpoint, headers, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'greta-external-evidence', 'version': '1.0'}}})
        if status != 200: raise HTTPException(502, 'Inisialisasi MCP gagal.')
        result = rpc_result(content, response_headers, 1)
        if result.get('protocolVersion') != PROTOCOL: raise HTTPException(502, 'Server harus mendukung MCP ' + PROTOCOL + '.')
        headers['MCP-Protocol-Version'] = PROTOCOL
        if response_headers.get('mcp-session-id'): headers['Mcp-Session-Id'] = response_headers['mcp-session-id']
        status, _, _ = await bounded_post(client, endpoint, headers, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        if status not in (200, 202, 204): raise HTTPException(502, 'Notifikasi inisialisasi MCP gagal.')
        status, rh, content = await bounded_post(client, endpoint, headers, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
        if status != 200: raise HTTPException(502, 'Daftar tool MCP gagal.')
        catalog = rpc_result(content, rh, 2)
        if not isinstance(catalog.get('tools'), list) or any(not isinstance(t, dict) for t in catalog['tools']):
            raise HTTPException(502, 'Schema katalog MCP tidak valid.')
        approved = {t['name'] for t in row.data.get('tools', [])}
        tools = [t for t in catalog.get('tools', []) if t.get('name') in approved and (t.get('annotations') or {}).get('readOnlyHint') is True]
        if tool is None: return {'tools': [{'name': t['name'], 'description': t.get('description', '')[:500]} for t in tools]}
        if tool not in {t['name'] for t in tools}: raise HTTPException(403, 'Tool harus diizinkan Admin dan dideklarasikan read-only oleh server.')
        status, rh, content = await bounded_post(client, endpoint, headers, {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': tool, 'arguments': parameters}})
        if status != 200: raise HTTPException(502, 'Tool MCP gagal.')
        result = rpc_result(content, rh, 3)
        if result.get('isError'): raise HTTPException(502, 'Tool MCP melaporkan kegagalan.')
        # External content is stored as evidence, never executed or inserted into a system prompt.
        blocks = result.get('content', [])
        if not isinstance(blocks, list) or any(not isinstance(c, dict) for c in blocks): raise HTTPException(502, 'Schema konten MCP tidak valid.')
        texts = [c['text'] for c in blocks if c.get('type') == 'text' and isinstance(c.get('text'), str)]
        return {'text': '\n'.join(texts)[:60000], 'structured': result.get('structuredContent')}


@router.post('/connectors/{id}/test')
async def test_connector(id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'admin'); row = connector_get(db, user, id, 'external_mcp')
    try: result = await external_rpc(row)
    except httpx.HTTPError as exc: raise HTTPException(502, 'Koneksi MCP gagal atau timeout.') from exc
    audit(db, user, 'external_mcp.test', id); db.commit(); return result


class ExternalCall(StrictInput):
    tool: str = Field(max_length=100)
    parameters: dict = Field(default_factory=dict)
    category_id: str
    purpose: str = Field(min_length=10, max_length=1000)


@router.post('/connectors/{id}/query')
async def query(id: str, body: ExternalCall, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); row = connector_get(db, user, id, 'external_mcp'); get(db, user, body.category_id, 'category')
    policy = next((t for t in row.data.get('tools', []) if t['name'] == body.tool), None)
    if not policy or set(body.parameters) - set(policy['parameters']) or set(policy['required']) - set(body.parameters): raise HTTPException(422, 'Parameter tidak sesuai allowlist tool.')
    for key, value in body.parameters.items():
        typ = policy['parameters'][key]
        if (typ == 'string' and (not isinstance(value, str) or len(value) > 1000)) or (typ == 'number' and (type(value) not in (int, float) or not __import__('math').isfinite(value))) or (typ == 'boolean' and type(value) is not bool):
            raise HTTPException(422, 'Tipe parameter tidak valid.')
    try: result = await external_rpc(row, body.tool, body.parameters)
    except httpx.HTTPError as exc: raise HTTPException(502, 'Koneksi MCP gagal atau timeout.') from exc
    evidence = Record(kind='external_evidence', owner=user.id, region=user.region, classification='CONFIDENTIAL',
        data={**body.model_dump(), 'name': row.data['name'] + ' / ' + body.tool, 'connector_id': id, 'connector_version': row.data['version'],
              'source_url': row.data['endpoint'], 'retrieved_at': now(), 'content': result, 'shared_with': [], 'untrusted_external_content': True})
    db.add(evidence); db.flush(); audit(db, user, 'external_mcp.query', evidence.id, {'connector_id': id, 'tool': body.tool}); db.commit()
    return public(evidence)


@router.get('/evidence')
def evidence(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); return [public(r) for r in db.scalars(select(Record).where(Record.kind == 'external_evidence')) if accessible(user, r)]


class PackageInput(StrictInput):
    recommendation_id: str
    connector_id: str
    title: str = Field(min_length=5, max_length=200)
    business_justification: str = Field(min_length=10, max_length=5000)


@router.post('/packages')
def prepare(body: PackageInput, user=Depends(current_user), db=Depends(db_session)):
    rec = analysis(db, user, body.recommendation_id, 'recommendation')
    connector = connector_get(db, user, body.connector_id, 'workflow')
    if rec.data.get('is_demo'): raise HTTPException(409, 'Rekomendasi dari data demo tidak dapat dikirim ke sistem enterprise.')
    if rec.data['status'] != 'APPROVED': raise HTTPException(409, 'Rekomendasi memerlukan persetujuan Buyer terlebih dahulu.')
    key = uid()
    payload = {'schema_version': 'greta.procurement-review.v1', 'request_id': key, 'title': body.title,
        'business_justification': body.business_justification, 'category_id': rec.data['category_id'],
        'recommendation_id': rec.id, 'actions': rec.data['result']['actions'], 'gaps': rec.data['result']['gaps'],
        'requested_action': 'CREATE_REVIEW_TASK', 'source_references': rec.data['sources']}
    package = Record(id=key, kind='workflow_package', owner=user.id, region=user.region, classification=rec.classification,
        data={**body.model_dump(), 'payload': payload, 'source_ids': [rec.id], 'connector_version': connector.data['version'],
              'status': 'DRAFT', 'shared_with': rec.data.get('shared_with', [])})
    db.add(package); audit(db, user, 'workflow.package.prepared', key); db.commit(); return public(package)


def package_get(db, user, id, lock=False):
    require(user, 'procurement'); row = get(db, user, id, 'workflow_package', lock=lock)
    if not authorize(db, user, row): raise HTTPException(404)
    return row


@router.get('/packages')
def packages(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); result = []
    for row in db.scalars(select(Record).where(Record.kind == 'workflow_package').order_by(Record.created_at.desc())):
        if not authorize(db, user, row): continue
        delivery = db.scalar(select(WorkflowDelivery).where(WorkflowDelivery.package_id == row.id))
        result.append({**public(row), 'delivery': delivery_public(delivery) if delivery else None})
    return result


class Approval(StrictInput):
    rationale: str = Field(min_length=10, max_length=3000)
    approve_external_payload: Literal[True]


@router.post('/packages/{id}/approve')
def approve(id: str, body: Approval, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:approve'); row = package_get(db, user, id, lock=True)
    if row.data['status'] != 'DRAFT': raise HTTPException(409, 'Paket sudah ditinjau.')
    row.data = {**row.data, 'status': 'APPROVED', 'approval': {'by': user.id, 'at': now(), 'rationale': body.rationale}}
    audit(db, user, 'workflow.package.approved', id); db.commit(); return public(row)


def delivery_public(row):
    return {'id': row.id, 'status': row.status, 'receipt': row.receipt, 'error': row.error, 'updated_at': row.updated_at}


@router.post('/packages/{id}/deliver')
def deliver(id: str, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:approve'); row = package_get(db, user, id, lock=True)
    old = db.scalar(select(WorkflowDelivery).where(WorkflowDelivery.package_id == id))
    if old: return delivery_public(old)
    if row.data['status'] != 'APPROVED': raise HTTPException(409, 'Tinjau dan setujui isi paket sebelum pengiriman.')
    rec = analysis(db, user, row.data['recommendation_id'], 'recommendation')
    if rec.data['status'] != 'APPROVED': raise HTTPException(409, 'Persetujuan rekomendasi sudah tidak berlaku.')
    connector = connector_get(db, user, row.data['connector_id'], 'workflow')
    if not connector.data['enabled'] or connector.data['version'] != row.data['connector_version']: raise HTTPException(409, 'Konektor berubah atau nonaktif. Buat dan tinjau paket baru.')
    delivery = WorkflowDelivery(package_id=id, owner=user.id, connector_id=connector.id, connector_version=connector.data['version'],
        payload=cipher().encrypt(json.dumps(row.data['payload']).encode()).decode())
    db.add(delivery); db.flush(); row.data = {**row.data, 'status': 'QUEUED'}
    audit(db, user, 'workflow.delivery.queued', delivery.id); db.commit(); return delivery_public(delivery)


async def process_workflow():
    with Session() as db:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        for old in db.scalars(select(WorkflowDelivery).where(WorkflowDelivery.status == 'SENDING', WorkflowDelivery.updated_at < cutoff).with_for_update(skip_locked=True)):
            old.status = 'UNKNOWN'; old.error = 'Worker interrupted; reconcile with receiver before any new delivery.'; old.updated_at = now()
        db.commit()
        row = db.scalar(select(WorkflowDelivery).where(WorkflowDelivery.status == 'PENDING').with_for_update(skip_locked=True).limit(1))
        if not row: return
        user = db.get(User, row.owner); package = db.get(Record, row.package_id); connector = db.get(Config, row.connector_id)
        rec = db.get(Record, package.data['recommendation_id']) if package else None
        if not user or not user.active or user.role != 'Buyer' or not package or not authorize(db, user, package) or not rec or rec.data['status'] != 'APPROVED' or not connector or not connector.data['enabled'] or connector.data['version'] != row.connector_version:
            row.status = 'BLOCKED'; row.error = 'Authorization, approval or connector changed.'; row.updated_at = now(); db.commit(); return
        row.status = 'SENDING'; row.updated_at = now(); db.commit(); key = row.id
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=False, trust_env=False) as client:
                status, _, content = await bounded_post(client, connector.data['endpoint'], {**headers_for(connector), 'Idempotency-Key': package.id}, json.loads(cipher().decrypt(row.payload.encode())))
            if status in (200, 201, 202):
                result = json.loads(content)
                if result.get('request_id') != package.id or result.get('accepted') is not True or not isinstance(result.get('receipt_id'), str) or not 1 <= len(result['receipt_id']) <= 200: raise ValueError()
                row.status = 'ACKNOWLEDGED'; row.receipt = result['receipt_id']
            elif 400 <= status < 500 and status not in (408, 409, 429):
                row.status = 'REJECTED'; row.error = 'Receiver rejected request: HTTP ' + str(status)
            else:
                row.status = 'UNKNOWN'; row.error = 'Ambiguous receiver response; reconcile before creating another package.'
        except Exception:
            row.status = 'UNKNOWN'; row.error = 'Transport or receipt could not be verified; reconcile with receiver.'
        row.updated_at = now(); audit(db, user, 'workflow.delivery.' + row.status.lower(), key); db.commit()


class Reconciliation(StrictInput):
    accepted: bool
    receipt_or_evidence: str = Field(min_length=10, max_length=1000)


@router.post('/packages/{id}/reconcile')
def reconcile(id: str, body: Reconciliation, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:approve'); package_get(db, user, id, lock=True)
    row = db.scalar(select(WorkflowDelivery).where(WorkflowDelivery.package_id == id).with_for_update())
    if not row or row.status != 'UNKNOWN': raise HTTPException(409, 'Hanya pengiriman UNKNOWN memerlukan rekonsiliasi.')
    row.status = 'ACKNOWLEDGED' if body.accepted else 'REJECTED'; row.receipt = body.receipt_or_evidence; row.error = None; row.updated_at = now()
    audit(db, user, 'workflow.delivery.reconciled', row.id, body.model_dump()); db.commit(); return delivery_public(row)


class EvidenceSharing(StrictInput):
    user_ids: list[str] = Field(max_length=30)


@router.put('/evidence/{id}/sharing')
def share_evidence(id: str, body: EvidenceSharing, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'procurement'); row = get(db, user, id, 'external_evidence', lock=True)
    if row.owner != user.id: raise HTTPException(403, 'Sharing hanya oleh pemilik evidence.')
    for sid in body.user_ids:
        recipient = db.get(User, sid)
        if not recipient or not recipient.active or recipient.region != user.region or recipient.role not in ('Buyer', 'Market Intelligence Analyst'):
            raise HTTPException(422, 'Penerima harus Buyer/Analyst aktif di region yang sama.')
    row.data = {**row.data, 'shared_with': sorted(set(body.user_ids))}; row.updated_at = now()
    audit(db, user, 'external_evidence.sharing', id, {'recipients': body.user_ids}); db.commit(); return public(row)
