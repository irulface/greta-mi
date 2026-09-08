"""Durable, encrypted supplier invitation outbox."""
from alembic import op
from app.db import EmailOutbox

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    EmailOutbox.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Restore a database backup instead of dropping delivery history.')
