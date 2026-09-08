import os, uuid
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(os.getenv('GRETA_ENV_FILE', str(Path(__file__).resolve().parents[1] / '.env')))
from sqlalchemy import create_engine, String, Text, JSON, Integer, DateTime, ForeignKey, Boolean, Numeric, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from pgvector.sqlalchemy import Vector

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA}/greta.db')
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    region: Mapped[str] = mapped_column(String, default='Region 1')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class LoginSession(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires: Mapped[int] = mapped_column(Integer)
class Record(Base):
    __tablename__ = 'records'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String, index=True)
    region: Mapped[str] = mapped_column(String, index=True, default='Region 1')
    owner: Mapped[str] = mapped_column(String, default='system')
    classification: Mapped[str] = mapped_column(String, default='INTERNAL')
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)
class Chunk(Base):
    __tablename__ = 'document_chunks'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    content: Mapped[str] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer, default=1)
    embedding: Mapped[list | None] = mapped_column(Vector(), nullable=True)
class Config(Base):
    __tablename__ = 'configurations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String)
    event: Mapped[str] = mapped_column(String, index=True)
    target: Mapped[str] = mapped_column(String, default='')
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    correlation_id: Mapped[str] = mapped_column(String, default=uid)
    timestamp: Mapped[str] = mapped_column(String, default=now)

class EmailOutbox(Base):
    __tablename__ = 'email_outbox'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    rfi_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey('records.id'))
    invitation_id: Mapped[str] = mapped_column(ForeignKey('records.id'), unique=True)
    recipient: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='PENDING', index=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_id: Mapped[str] = mapped_column(String, unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class MarketPoint(Base):
    __tablename__ = 'market_points'
    __table_args__ = (UniqueConstraint('series_id', 'observed_on', name='uq_market_series_date'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    series_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    observed_on: Mapped[str] = mapped_column(String, index=True)
    value: Mapped[float] = mapped_column(Numeric(24, 8))
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=1)
    source: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[str] = mapped_column(String, default=now)


class MarketRun(Base):
    __tablename__ = 'market_runs'
    __table_args__ = (UniqueConstraint('task_id', 'slot', name='uq_market_run_slot'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    task_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    slot: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    status: Mapped[str] = mapped_column(String, default='PENDING', index=True)
    result_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)


class SupplierAccount(Base):
    __tablename__ = 'supplier_accounts'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    supplier_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    activation_hash: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    activation_expires: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=now)


class SupplierSession(Base):
    __tablename__ = 'supplier_sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey('supplier_accounts.id'), index=True)
    expires: Mapped[int] = mapped_column(Integer)


class WorkflowDelivery(Base):
    __tablename__ = 'workflow_deliveries'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    package_id: Mapped[str] = mapped_column(ForeignKey('records.id'), unique=True)
    owner: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String, default='PENDING', index=True)
    payload: Mapped[str] = mapped_column(Text)
    connector_id: Mapped[str] = mapped_column(ForeignKey('configurations.id'))
    connector_version: Mapped[int] = mapped_column(Integer)
    receipt: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now)


class AgentRun(Base):
    __tablename__ = 'agent_runs'
    __table_args__ = (UniqueConstraint('agent_id', 'slot', name='uq_agent_run_slot'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    agent_id: Mapped[str] = mapped_column(ForeignKey('records.id'), index=True)
    owner: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    slot: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String, default='manual')
    status: Mapped[str] = mapped_column(String, default='PENDING', index=True)
    lease: Mapped[str | None] = mapped_column(String, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    started_at: Mapped[str | None] = mapped_column(String, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
