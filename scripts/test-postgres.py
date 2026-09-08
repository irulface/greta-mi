"""Run migrations and API tests in a disposable local database, never gretamidb.
Usage: backend/.venv/bin/python scripts/test-postgres.py
Requires a local database admin able to CREATE DATABASE and CREATE EXTENSION vector.
"""
import getpass
import os
from pathlib import Path
import subprocess
import uuid
import psycopg
from psycopg import sql

base = Path(__file__).resolve().parents[1]
name = 'gretami_test_' + uuid.uuid4().hex
admin_user = os.getenv('GRETA_TEST_ADMIN', getpass.getuser())
owner = 'gretami'
with psycopg.connect(host='localhost', dbname='postgres', user=admin_user, autocommit=True) as admin:
    admin.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name), sql.Identifier(owner)))
    try:
        with psycopg.connect(host='localhost', dbname=name, user=admin_user) as testdb:
            testdb.execute('CREATE EXTENSION vector')
        url = 'postgresql+psycopg://gretami@localhost:5432/' + name
        env = {**os.environ, 'GRETA_ENV_FILE': os.devnull, 'DATABASE_URL': url, 'APP_ENV': 'development', 'GRETA_TEST_DATABASE_URL': url}
        subprocess.run([str(base/'backend/.venv/bin/alembic'), 'upgrade', 'head'], cwd=base/'backend', env=env, check=True)
        result = subprocess.run([str(base/'backend/.venv/bin/python'), '-m', 'pytest', '-q', 'tests'], cwd=base/'backend', env=env)
    finally:
        admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
raise SystemExit(result.returncode)
