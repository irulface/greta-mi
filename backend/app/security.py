import hashlib, hmac, os, secrets, time
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select
from .db import Session, User, LoginSession, Audit, DATA

DEV = os.getenv('APP_ENV', 'development') == 'development'
PERMISSIONS = {
 'Admin': {'admin', 'repository:read', 'repository:write', 'market:read', 'supplier:read', 'supplier:write'},
 'Buyer': {'rfi:read', 'rfi:create', 'rfi:manage', 'rfi:approve', 'repository:read', 'repository:write', 'supplier:read', 'supplier:write', 'market:read', 'ai', 'procurement'},
 'Fungsi Pengguna': {'rfi:read', 'rfi:create', 'repository:read', 'supplier:read', 'market:read', 'ai'},
 'Market Intelligence Analyst': {'rfi:read', 'repository:read', 'repository:write', 'supplier:read', 'supplier:write', 'market:read', 'market:write', 'ai', 'procurement'}
}
def hash_password(password):
    salt = secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
def verify_password(password, hashed):
    salt, value = hashed.split(':')
    return hmac.compare_digest(value, hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex())
def db_session():
    with Session() as db: yield db

def current_user(request: Request, db=Depends(db_session)):
    raw = request.cookies.get('greta_session', '')
    token = hashlib.sha256(raw.encode()).hexdigest()
    session = db.get(LoginSession, token)
    if not session or session.expires < time.time(): raise HTTPException(401, 'Silakan masuk untuk melanjutkan.')
    user = db.get(User, session.user_id)
    if not user or not user.active: raise HTTPException(401, 'Akun tidak aktif.')
    return user

def require(user, permission):
    if permission not in PERMISSIONS.get(user.role, set()): raise HTTPException(403, 'Role Anda tidak memiliki izin untuk tindakan ini.')
def visible(user, record):
    if record.region not in ('Global', user.region): return False
    if record.classification == 'RESTRICTED' and record.owner != user.id: return False
    if record.classification == 'CONFIDENTIAL' and user.role == 'Fungsi Pengguna' and record.owner != user.id: return False
    if record.kind == 'rfi' and user.role == 'Fungsi Pengguna' and record.owner != user.id: return False
    return True

def audit(db, user, event, target='', details=None, correlation_id=None):
    row = Audit(actor=user.id if isinstance(user, User) else str(user), event=event, target=target, details=details or {})
    if correlation_id: row.correlation_id = correlation_id
    db.add(row)

def cipher():
    key = os.getenv('APP_MASTER_KEY')
    if not key:
        if not DEV: raise HTTPException(503, 'APP_MASTER_KEY belum dikonfigurasi di server.')
        path = DATA / '.master-key'
        if not path.exists():
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as f: f.write(Fernet.generate_key())
        key = path.read_text().strip()
    return Fernet(key.encode())
