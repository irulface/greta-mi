"""Phase 3 supplier identities and durable enterprise delivery."""
from alembic import op
from app.db import SupplierAccount, SupplierSession, WorkflowDelivery
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    for model in (SupplierAccount, SupplierSession, WorkflowDelivery):
        model.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Restore a database backup to preserve supplier and workflow history.')
