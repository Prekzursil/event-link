# Event Link Backend

## Configuration

Environment variables (or `.topsecret` file) are loaded via `pydantic-settings`:

- `DATABASE_URL` (required)
- `SECRET_KEY` (required)
- `ALLOWED_ORIGINS` (comma-separated or JSON list; defaults to localhost/127.0.0.1 on ports 3000 and 4200)
- `ADMIN_EMAILS` (comma-separated or JSON list; optional; emails granted admin-only endpoints)
- `AUTO_CREATE_TABLES` (bool; enable for local dev only)
- `AUTO_RUN_MIGRATIONS` (bool; run Alembic upgrade head on startup – recommended for dev/CI)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)
- Email: `EMAIL_ENABLED` (default true), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER`, `SMTP_USE_TLS`
- Background jobs: `TASK_QUEUE_ENABLED` (default false), `TASK_QUEUE_POLL_INTERVAL_SECONDS`, `TASK_QUEUE_MAX_ATTEMPTS`, `TASK_QUEUE_STALE_AFTER_SECONDS`
- Public API: `PUBLIC_API_RATE_LIMIT` (default 60 per window), `PUBLIC_API_RATE_WINDOW_SECONDS` (default 60)
- Maintenance mode: `MAINTENANCE_MODE_REGISTRATIONS_DISABLED` (default false; returns 503 for registration-related endpoints)
- Alembic uses `DATABASE_URL` from the same env for migrations.

## Running locally

```bash
cd backend
# install deps
pip install -r requirements.txt
# (optional) create tables automatically if AUTO_CREATE_TABLES=true
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If `TASK_QUEUE_ENABLED=true`, run a worker in another terminal:

```bash
cd backend
python -m app.worker
```

Health endpoint: `GET /api/health`

## Database migrations (Alembic)

```bash
cd backend
# run migrations
alembic upgrade head
# create new migration (after model changes)
alembic revision --autogenerate -m "your message"
```

`AUTO_CREATE_TABLES` should not be used in production; rely on Alembic migrations instead.

## Tests

```bash
cd backend
pytest
```

## Notes

- CORS origins are configurable via `ALLOWED_ORIGINS`; defaults target localhost/127.0.0.1 for dev—set staging/prod hosts explicitly (avoid `*` when using credentials).
- Email sending is optional and failures are logged without breaking the request; when `TASK_QUEUE_ENABLED=true`, emails are queued and sent by the worker.
- In production, manage schema with migrations instead of `AUTO_CREATE_TABLES`.
