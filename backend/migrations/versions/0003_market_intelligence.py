"""Phase 2 observations and durable market automation runs."""
from alembic import op
from sqlalchemy import select
from app.db import MarketPoint, MarketRun, Record, uid, now

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    MarketPoint.__table__.create(connection, checkfirst=True)
    MarketRun.__table__.create(connection, checkfirst=True)
    for row in connection.execute(select(Record.__table__).where(Record.kind == 'price')).mappings():
        data = row['data']
        existing = set(connection.execute(select(MarketPoint.observed_on).where(MarketPoint.series_id == row['id'])).scalars())
        for day, value in zip(data.get('dates', []), data.get('series', [])):
            if day not in existing:
                connection.execute(MarketPoint.__table__.insert().values(id=uid(), series_id=row['id'], observed_on=day,
                    value=value, confidence=data.get('confidence', 1), source=data.get('source', 'Legacy import'), notes='', updated_at=now()))


def downgrade():
    raise RuntimeError('Restore a database backup instead of deleting market history.')
