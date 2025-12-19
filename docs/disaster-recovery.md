# Disaster recovery (Postgres)

This repo ships with small helper scripts for backing up and restoring the Postgres database used by `docker compose`.

## Backup

Prereqs:
- Docker / Docker Desktop
- `docker compose up -d db` (the `db` container must be running)

Create a compressed SQL backup:

```bash
bash scripts/db-backup.sh
```

This writes a timestamped file to `./backups/` by default.

Custom output path:

```bash
bash scripts/db-backup.sh backups/eventlink-prod-20250101.sql.gz
```

Recommendations:
- Store backups outside the host (object storage, offsite).
- Encrypt backups at rest.
- Keep multiple restore points (e.g., daily + weekly).
- Regularly test restores in a staging environment.

## Restore

Prereqs:
- Docker / Docker Desktop
- A backup created with `pg_dump` (this repo’s `db-backup.sh` produces a `.sql.gz` file)

Restore from a backup file:

```bash
bash scripts/db-restore.sh backups/eventlink-20250101T000000Z.sql.gz
```

Notes:
- The restore script **drops and recreates the `public` schema** (data loss if you point it at the wrong DB).
- For production, consider running the restore against a separate environment first.

## Deployment safety: disable registrations

If you need to deploy migrations and want to avoid writes from students during the deploy window, set:

```bash
MAINTENANCE_MODE_REGISTRATIONS_DISABLED=true
```

This makes registration-related endpoints return `503 Service Unavailable` until you turn it off.

## Suggested DR runbook (high level)

1. Enable maintenance mode (`MAINTENANCE_MODE_REGISTRATIONS_DISABLED=true`).
2. Take a final backup (`bash scripts/db-backup.sh`).
3. Restore to a clean Postgres instance (`bash scripts/db-restore.sh ...`) or promote your standby.
4. Ensure the backend is on the same code revision expected by the DB schema.
5. Run `alembic upgrade head` (or rely on `AUTO_RUN_MIGRATIONS=true` in docker compose).
6. Verify:
   - `GET /api/health`
   - Login + event list + event details
   - A test registration in staging
7. Disable maintenance mode.
