"""Initial Greta schema, full text index, and optional pgvector HNSW index."""
from alembic import op
from app.db import Base
import os
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    connection=op.get_bind()
    if connection.dialect.name=='postgresql':op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    Base.metadata.create_all(connection)
    if connection.dialect.name=='postgresql':
        op.execute("CREATE INDEX IF NOT EXISTS ix_chunks_fts ON document_chunks USING gin (to_tsvector('simple', content))")
        dims=int(os.getenv('EMBEDDING_DIMENSIONS','1536'))
        if not 1<=dims<=2000:raise ValueError('HNSW vector dimensions must be between 1 and 2000; use halfvec for larger embeddings in a later migration.')
        op.execute(f'CREATE INDEX IF NOT EXISTS ix_chunks_hnsw_{dims} ON document_chunks USING hnsw ((embedding::vector({dims})) vector_cosine_ops) WHERE vector_dims(embedding) = {dims}')

def downgrade():
    raise RuntimeError('Destructive downgrade is intentionally disabled. Restore a database backup instead.')
