#!/bin/bash
# Creates the airflow database inside the same PostgreSQL instance.
# Docker runs .sh init scripts as the postgres superuser automatically.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE airflow OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'airflow') \gexec
EOSQL
