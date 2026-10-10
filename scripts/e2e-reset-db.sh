#!/usr/bin/env bash
# Recreate the database the browser tests use (vigilo_e2e) from scratch.
# It is separate from `vigilo` on purpose: pytest wipes that schema on every run.
# Needs the dev Postgres from docker-compose.yml running on localhost:5433.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T postgres psql -U vigilo -d postgres \
  -c "drop database if exists vigilo_e2e with (force)" \
  -c "create database vigilo_e2e" >/dev/null
DATABASE_URL="postgresql://vigilo:${POSTGRES_PASSWORD:-vigilo-dev-secret}@localhost:5433/vigilo_e2e" \
  uv run --env-file .env alembic -c packages/persistence/alembic.ini upgrade head >/dev/null 2>&1
echo "vigilo_e2e recreated and migrated"
