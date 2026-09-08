"""Supplier identities are isolated from internal roles and sessions."""
import hashlib
import secrets
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .db import Record, SupplierAccount, SupplierSession, DATA, now
from .security import DEV, audit, current_user, db_session, require, hash_password, verify_password
from .market import StrictInput, get

router = APIRouter(prefix='/api/v1/portal', tags=['Supplier portal'])
COOKIE = 'greta_supplier_session'
ATTEMPTS = {}


def digest(raw): return hashlib.sha256(raw.encode()).hexdigest()


def supplier_user(request: Request, db=Depends(db_session)):
    session = db.get(SupplierSession, digest(request.cookies.get(COOKIE, '')))
    account = db.get(SupplierAccount, session.account_id) if session and session.expires > time.time() else None
    if not account or not account.active: raise HTTPException(401, 'Masuk ke portal supplier untuk melanjutkan.')
    supplier = db.get(Record, account.supplier_id)
    if not supplier or supplier.kind != 'supplier': raise HTTPException(401, 'Perusahaan tidak tersedia.')
    return account


def account_info(account):
    return {'id': account.id, 'supplier_id': account.supplier_id, 'email': account.email, 'name': account.name,
            'active': account.active, 'activated': bool(account.password), 'created_at': account.created_at}


class Enroll(StrictInput):
    supplier_id: str
    email: str = Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$', max_length=254)
    name: str = Field(min_length=2, max_length=150)


@router.get('/accounts')
def accounts(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:manage')
    from .market import accessible
    return [account_info(a) for a in db.scalars(select(SupplierAccount)) if accessible(user, db.get(Record, a.supplier_id))]


@router.post('/accounts')
def enroll(body: Enroll, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:manage'); get(db, user, body.supplier_id, 'supplier')
    token = secrets.token_urlsafe(40)
    account = SupplierAccount(supplier_id=body.supplier_id, email=body.email.strip().lower(), name=body.name,
                              activation_hash=digest(token), activation_expires=int(time.time()) + 86400 * 2)
    db.add(account)
    try: db.flush()
    except IntegrityError: db.rollback(); raise HTTPException(409, 'Email sudah terdaftar di portal.')
    audit(db, user, 'portal.account.invited', account.id, {'supplier_id': body.supplier_id, 'email_sent': False})
    db.commit(); return {**account_info(account), 'activation_path': '/?portal=1&activation=' + token, 'expires_in_hours': 48}


class AccountAction(StrictInput):
    action: str = Field(pattern=r'^(deactivate|reactivate|reset)$')


@router.post('/accounts/{id}')
def manage_account(id: str, body: AccountAction, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:manage'); account = db.scalar(select(SupplierAccount).where(SupplierAccount.id == id).with_for_update())
    if not account: raise HTTPException(404)
    get(db, user, account.supplier_id, 'supplier')
    db.execute(delete(SupplierSession).where(SupplierSession.account_id == id))
    token = None
    if body.action == 'deactivate':
        account.active = False; account.activation_hash = None
    else:
        account.active = True
        if body.action == 'reset':
            token = secrets.token_urlsafe(40); account.activation_hash = digest(token)
            account.activation_expires = int(time.time()) + 86400 * 2; account.password = None
    audit(db, user, 'portal.account.' + body.action, id); db.commit()
    return {**account_info(account), **({'activation_path': '/?portal=1&activation=' + token} if token else {})}


class Activate(StrictInput):
    token: str = Field(min_length=30, max_length=200)
    password: str = Field(min_length=12, max_length=200)


@router.post('/activate')
def activate(body: Activate, request: Request, response: Response, db=Depends(db_session)):
    account = db.scalar(select(SupplierAccount).where(SupplierAccount.activation_hash == digest(body.token)).with_for_update())
    if not account or not account.active or account.activation_expires < time.time(): raise HTTPException(410, 'Aktivasi tidak valid atau kedaluwarsa.')
    account.password = hash_password(body.password); account.activation_hash = None; account.activation_expires = 0
    db.execute(delete(SupplierSession).where(SupplierSession.id == digest(request.cookies.get(COOKIE, ''))))
    response.delete_cookie(COOKIE)
    audit(db, 'supplier:' + account.id, 'portal.activated', account.supplier_id); db.commit(); return {'activated': True, 'email': account.email}


class Login(StrictInput):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


@router.post('/login')
def login(body: Login, request: Request, response: Response, db=Depends(db_session)):
    key = request.client.host if request.client else 'unknown'; recent = [t for t in ATTEMPTS.get(key, []) if time.time() - t < 300]
    if len(recent) >= 10: raise HTTPException(429, 'Terlalu banyak percobaan. Coba kembali dalam 5 menit.')
    account = db.scalar(select(SupplierAccount).where(SupplierAccount.email == body.email.strip().lower()))
    if not account or not account.active or not account.password or not verify_password(body.password, account.password):
        ATTEMPTS[key] = recent + [time.time()]; raise HTTPException(401, 'Email atau password tidak cocok.')
    ATTEMPTS.pop(key, None); token = secrets.token_urlsafe(40)
    db.add(SupplierSession(id=digest(token), account_id=account.id, expires=int(time.time()) + 8 * 3600))
    audit(db, 'supplier:' + account.id, 'portal.login', account.supplier_id); db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=not DEV, samesite='strict', max_age=8 * 3600, path='/')
    return account_info(account)


@router.get('/me')
def me(account=Depends(supplier_user)): return account_info(account)


@router.post('/logout')
def logout(request: Request, response: Response, account=Depends(supplier_user), db=Depends(db_session)):
    db.execute(delete(SupplierSession).where(SupplierSession.id == digest(request.cookies.get(COOKIE, '')))); db.commit()
    response.delete_cookie(COOKIE); return {'ok': True}


@router.get('/profile')
def profile(account=Depends(supplier_user), db=Depends(db_session)):
    supplier = db.get(Record, account.supplier_id)
    return {'company_name': supplier.data['name'], 'country': supplier.data.get('country', ''),
            'profile': supplier.data.get('portal_profile', {}), 'updated_at': supplier.updated_at}


class Profile(StrictInput):
    website: str = Field(default='', max_length=300)
    contact_name: str = Field(min_length=2, max_length=150)
    phone: str = Field(default='', max_length=80)
    capabilities: str = Field(default='', max_length=5000)
    certifications: str = Field(default='', max_length=3000)


@router.put('/profile')
def update_profile(body: Profile, account=Depends(supplier_user), db=Depends(db_session)):
    supplier = db.scalar(select(Record).where(Record.id == account.supplier_id).with_for_update())
    supplier.data = {**supplier.data, 'portal_profile': {**body.model_dump(), 'self_reported': True, 'updated_by': account.name, 'updated_at': now()}}
    supplier.updated_at = now(); audit(db, 'supplier:' + account.id, 'portal.profile.updated', supplier.id); db.commit()
    return profile(account, db)


def invited_rfi(db, account, id, writable=False):
    rfi = db.scalar(select(Record).where(Record.id == id, Record.kind == 'rfi').with_for_update())
    if not rfi or account.supplier_id not in rfi.data.get('supplier_ids', []): raise HTTPException(404, 'RFI tidak tersedia.')
    invitations = list(db.scalars(select(Record).where(Record.kind == 'invitation', Record.data['rfi_id'].as_string() == id,
        Record.data['supplier_id'].as_string() == account.supplier_id).order_by(Record.created_at.desc())))
    if not invitations: raise HTTPException(404, 'Buyer belum mengundang perusahaan Anda ke RFI ini.')
    inv = next((i for i in invitations if not i.data.get('revoked')), None)
    if writable:
        if not inv or inv.data['expires'] < time.time() or rfi.data['status'] not in ('Issued', 'Open', 'Response Received'):
            raise HTTPException(410, 'RFI belum dibuka atau sudah ditutup.')
        closing = datetime.fromisoformat(rfi.data['closing_date'] + 'T23:59:59+07:00').timestamp()
        if closing < time.time(): raise HTTPException(410, 'Tanggal penutupan RFI telah lewat.')
    return rfi, inv


@router.get('/rfis')
def rfis(account=Depends(supplier_user), db=Depends(db_session)):
    ids = {r.data['rfi_id'] for r in db.scalars(select(Record).where(Record.kind == 'invitation', Record.data['supplier_id'].as_string() == account.supplier_id))}
    result = []
    for id in ids:
        row = db.get(Record, id)
        if not row or account.supplier_id not in row.data.get('supplier_ids', []) or row.data.get('status') == 'Draft': continue
        result.append({'id': id, **{k: row.data[k] for k in ('number', 'title', 'status', 'closing_date', 'version')}})
    return result


@router.get('/rfis/{id}')
def questionnaire(id: str, account=Depends(supplier_user), db=Depends(db_session)):
    rfi, inv = invited_rfi(db, account, id, writable=True)
    supplier = db.get(Record, account.supplier_id)
    return {**{k: rfi.data[k] for k in ('title', 'number', 'requirement', 'closing_date', 'questions')},
            'supplier': supplier.data['name'], 'submitted': inv.data.get('used', False), 'draft': inv.data.get('draft', {})}


class Answers(StrictInput):
    answers: dict
    submit: bool = False


@router.post('/rfis/{id}')
def submit(id: str, body: Answers, account=Depends(supplier_user), db=Depends(db_session)):
    rfi, inv = invited_rfi(db, account, id, writable=True)
    from .main import persist_response
    audit(db, 'supplier:' + account.id, 'portal.response.action', id, {'submit': body.submit})
    return persist_response(db, inv, rfi, body)


@router.post('/rfis/{id}/attachments')
async def upload(id: str, file: UploadFile = File(...), account=Depends(supplier_user), db=Depends(db_session)):
    rfi, inv = invited_rfi(db, account, id, writable=True)
    from .main import persist_attachment
    return await persist_attachment(db, inv, rfi, file)


@router.get('/history')
def history(account=Depends(supplier_user), db=Depends(db_session)):
    result = []
    for row in db.scalars(select(Record).where(Record.kind.in_(['response', 'response_version']), Record.data['supplier_id'].as_string() == account.supplier_id).order_by(Record.updated_at.desc())):
        rfi = db.get(Record, row.data['rfi_id'])
        if not rfi: continue
        version = row.data.get('rfi_version', rfi.data.get('version', 1))
        old = db.scalar(select(Record).where(Record.kind == 'rfi_version', Record.data['rfi_id'].as_string() == rfi.id, Record.data['version'].as_integer() == version)) if row.kind == 'response_version' else None
        questions = (old or rfi).data.get('questions', [])
        result.append({'questions': questions, 'id': row.id, 'rfi_id': rfi.id, 'title': rfi.data['title'], 'number': rfi.data['number'], 'answers': row.data['answers'],
            'submitted_at': row.data.get('submitted_at'), 'version': row.data.get('rfi_version', rfi.data.get('version', 1)), 'historical': row.kind == 'response_version'})
    return result


@router.get('/attachments/{id}')
def download(id: str, account=Depends(supplier_user), db=Depends(db_session)):
    row = db.get(Record, id)
    if not row or row.kind != 'attachment' or row.data.get('supplier_id') != account.supplier_id: raise HTTPException(404)
    path = Path(row.data['storage_path']).resolve()
    if not path.is_relative_to(DATA / 'files') or not path.is_file(): raise HTTPException(404)
    audit(db, 'supplier:' + account.id, 'portal.attachment.download', id); db.commit()
    return FileResponse(path, filename=row.data['name'], media_type='application/octet-stream')


class Message(StrictInput):
    text: str = Field(min_length=3, max_length=5000)


@router.get('/rfis/{id}/clarifications')
def threads(id: str, account=Depends(supplier_user), db=Depends(db_session)):
    invited_rfi(db, account, id)
    return [{'id': r.id, **r.data} for r in db.scalars(select(Record).where(Record.kind == 'portal_clarification',
        Record.data['rfi_id'].as_string() == id, Record.data['supplier_id'].as_string() == account.supplier_id).order_by(Record.created_at))]


@router.post('/rfis/{id}/clarifications')
def question(id: str, body: Message, account=Depends(supplier_user), db=Depends(db_session)):
    rfi, inv = invited_rfi(db, account, id, writable=True)
    row = Record(kind='portal_clarification', region=rfi.region, owner=rfi.owner, classification=rfi.classification,
        data={'rfi_id': id, 'supplier_id': account.supplier_id, 'text': body.text, 'author': account.name, 'created_at': now(), 'status': 'OPEN'})
    db.add(row); db.flush(); audit(db, 'supplier:' + account.id, 'portal.clarification.created', row.id); db.commit(); return {'id': row.id, **row.data}


@router.get('/clarifications')
def inbox(user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:manage'); from .market import accessible
    return [{'id': r.id, **r.data} for r in db.scalars(select(Record).where(Record.kind == 'portal_clarification')) if accessible(user, db.get(Record, r.data['rfi_id']))]


@router.post('/clarifications/{id}/reply')
def reply(id: str, body: Message, user=Depends(current_user), db=Depends(db_session)):
    require(user, 'rfi:manage'); row = get(db, user, id, 'portal_clarification', lock=True); get(db, user, row.data['rfi_id'], 'rfi')
    row.data = {**row.data, 'reply': body.text, 'replied_by': user.name, 'replied_at': now(), 'status': 'ANSWERED'}
    audit(db, user, 'portal.clarification.answered', id); db.commit(); return {'id': row.id, **row.data}
