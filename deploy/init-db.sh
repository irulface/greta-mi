#!/usr/bin/env bash
set -euo pipefail
# Runs only when the dedicated PostgreSQL volume is empty.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set app_user="$APP_DB_USER" --set app_password="$APP_DB_PASSWORD" --set app_db="$APP_DB_NAME" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L', :'app_user', :'app_password') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'app_db', :'app_user') \gexec
SQL
psql --username "$POSTGRES_USER" --dbname "$APP_DB_NAME" --set ON_ERROR_STOP=1 \
  --command 'CREATE EXTENSION IF NOT EXISTS vector;'
