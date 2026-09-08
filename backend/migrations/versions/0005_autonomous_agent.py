"""Durable Phase 4 agent runs and evidence snapshots."""
from alembic import op
from app.db import AgentRun
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    AgentRun.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Restore a backup to preserve autonomous agent evidence and history.')
