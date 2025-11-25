# Event Link Backend

## Configuration

Environment variables (or `.topsecret` file) are loaded via `pydantic-settings`:

- `DATABASE_URL` (required)
- `SECRET_KEY` (required)
- `ALLOWED_ORIGINS` (comma-separated or JSON list; defaults to localhost/127.0.0.1 on ports 3000 and 4200)
- `AUTO_CREATE_TABLES` (bool; enable for local dev only)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (default 30)
- Email: `EMAIL_ENABLED` (default true), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER`, `SMTP_USE_TLS`
- Alembic uses `DATABASE_URL` from the same env for migrations.

## Running locally

```bash
cd backend
# install deps
pip install -r requirements.txt
# (optional) create tables automatically if AUTO_CREATE_TABLES=true
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
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
python -m unittest tests.test_api
```

## Notes

- CORS origins are configurable via `ALLOWED_ORIGINS`; defaults target localhost/127.0.0.1 for dev—set staging/prod hosts explicitly (avoid `*` when using credentials).
- Email sending is optional and failures are logged without breaking the request.
- In production, manage schema with migrations instead of `AUTO_CREATE_TABLES`.
