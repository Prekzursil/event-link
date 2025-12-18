#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

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

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
default_out_dir="$repo_root/backups"
default_out_file="$default_out_dir/${db_name}-${timestamp}.sql.gz"

target="${1:-$default_out_file}"
if [[ -d "$target" || "${target: -1}" == "/" ]]; then
  mkdir -p "$target"
  out_file="${target%/}/${db_name}-${timestamp}.sql.gz"
else
  mkdir -p "$(dirname "$target")"
  out_file="$target"
fi

echo "Backing up Postgres database '$db_name' from docker compose service 'db'..."
echo "Output: $out_file"

docker compose exec -T db pg_dump -U "$db_user" -d "$db_name" --no-owner --no-privileges | gzip -c >"$out_file"

echo "Backup complete."
