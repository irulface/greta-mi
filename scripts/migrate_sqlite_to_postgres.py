#!/usr/bin/env python3
"""Copy a stopped local SQLite installation into an empty, migrated PostgreSQL DB.

Run with backend/.venv/bin/python. The target comes from backend/.env; database
credentials and record contents are never printed. Source data is retained.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, select, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.db import Base, DATA, engine


def digest(rows):
    def normalize(value):
        if hasattr(value, 'tolist'):
            return value.tolist()
        raise TypeError(type(value).__name__)
    values = [json.dumps(dict(row), sort_keys=True, ensure_ascii=False, default=normalize) for row in rows]
    return hashlib.sha256('\n'.join(sorted(values)).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DATA / 'greta.db')
    args = parser.parse_args()
    source = args.source.resolve()
    if engine.dialect.name != 'postgresql':
        raise SystemExit('DATABASE_URL must point to PostgreSQL.')
    if not source.is_file():
        raise SystemExit('Source SQLite database does not exist.')
    backup_dir = DATA / 'backups'
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = backup_dir / ('greta-before-postgres-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.db')
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as old, sqlite3.connect(backup) as saved:
        old.backup(saved)
    source_engine = create_engine('sqlite:///' + str(backup))
    names = set(inspect(source_engine).get_table_names())
    counts = {}
    with source_engine.connect() as old, engine.begin() as target:
        expected = {table.name for table in Base.metadata.sorted_tables}
        if not expected.issubset(set(inspect(target).get_table_names())):
            raise SystemExit('Run alembic upgrade head on the target first.')
        for table in Base.metadata.sorted_tables:
            target.execute(text(f'LOCK TABLE "{table.name}" IN ACCESS EXCLUSIVE MODE'))
            if target.scalar(select(func.count()).select_from(table)):
                raise SystemExit('Refusing to overwrite a nonempty PostgreSQL database. No records copied.')
        for table in Base.metadata.sorted_tables:
            source_rows = list(old.execute(select(table)).mappings()) if table.name in names else []
            if source_rows:
                target.execute(table.insert(), [dict(row) for row in source_rows])
            target_rows = list(target.execute(select(table)).mappings())
            if digest(source_rows) != digest(target_rows):
                raise RuntimeError('Data verification failed for ' + table.name + '; transaction rolled back.')
            counts[table.name] = len(source_rows)
    source_engine.dispose()
    print(json.dumps({'status': 'migrated', 'backup': str(backup), 'verified_rows': counts}, indent=2))


if __name__ == '__main__':
    main()
