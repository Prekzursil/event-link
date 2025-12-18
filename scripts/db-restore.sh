#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup.sql.gz|backup.sql>" >&2
  exit 2
fi

backup_file="$1"
if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required (Docker Desktop / Docker Engine)." >&2
  exit 1
fi

# Load .env if present (docker compose reads it too, but we also need defaults for the script).
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

db_name="${POSTGRES_DB:-eventlink}"
db_user="${POSTGRES_USER:-eventlink}"

echo "This will restore '$backup_file' into Postgres database '$db_name' in docker compose service 'db'."
echo "WARNING: This will overwrite existing data (drops and recreates the public schema)."
read -r -p "Continue? [y/N] " confirm
if [[ "${confirm,,}" != "y" ]]; then
  echo "Aborted."
  exit 1
fi

docker compose up -d db >/dev/null

echo "Resetting schema..."
docker compose exec -T db psql -U "$db_user" -d "$db_name" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "Restoring backup..."
if [[ "$backup_file" == *.gz ]]; then
  gunzip -c "$backup_file" | docker compose exec -T db psql -U "$db_user" -d "$db_name" -v ON_ERROR_STOP=1
else
  cat "$backup_file" | docker compose exec -T db psql -U "$db_user" -d "$db_name" -v ON_ERROR_STOP=1
fi

echo "Restore complete."
echo "Next: run migrations if needed (backend runs Alembic on startup when AUTO_RUN_MIGRATIONS=true)."
