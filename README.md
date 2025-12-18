# Event Link

Full-stack event management app with a React (Vite) frontend and a FastAPI + SQLAlchemy backend.

## Project structure

```
event-link/
├── backend/      # FastAPI app, Alembic migrations, and tests
├── ui/           # React + Vite frontend
├── docs/         # Additional documentation (e.g., permissions)
├── loadtests/    # k6 load-testing scripts
├── start.bat     # Windows helper to launch backend + frontend
└── docker-compose.yml
```

## Prerequisites

- **Node.js**: 20+ (for Vite + TypeScript)
- **npm**
- **Python**: 3.11+
- **Docker**: optional, for containerized runs

## GitHub credentials (Codex/MCP + git)

If you use Codex GitHub MCP tooling or want `git push` to work without interactive prompts, see
`docs/github-auth.md`.

## Backend configuration

Environment is read from `.topsecret` in `backend/` (or standard env vars). Minimum settings:

```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db
SECRET_KEY=change-me
# Comma-separated or JSON list; defaults cover localhost/127.0.0.1 for ports 3000/4200/5173
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:4200,http://localhost:3000
# Optional admin-only endpoints (comma-separated or JSON list)
ADMIN_EMAILS=admin@example.com
# Use migrations in prod; enable for quick local setup
AUTO_CREATE_TABLES=true
# Run Alembic automatically on startup (recommended for dev/CI)
AUTO_RUN_MIGRATIONS=true
# Email (optional)
EMAIL_ENABLED=true
SMTP_HOST=smtp.mailhost.com
SMTP_PORT=587
SMTP_USERNAME=user
SMTP_PASSWORD=pass
SMTP_SENDER=notifications@eventlink.test
SMTP_USE_TLS=true
# Public API rate limiting (optional)
PUBLIC_API_RATE_LIMIT=60
PUBLIC_API_RATE_WINDOW_SECONDS=60
```

`ALLOWED_ORIGINS` accepts comma- or JSON-separated lists. If email is enabled but SMTP settings
are missing, sending is skipped with a warning.

## Local setup

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
# optional: apply migrations before first run
alembic upgrade head
# start the API
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Health check: http://localhost:8000/api/health

### Frontend (React + Vite)

```bash
cd ui
npm install
npm run dev  # serves on http://localhost:5173
```

Configure the API base URL via `VITE_API_URL` (default is `http://localhost:8000`), for example in
`ui/.env.local` (you can start from `ui/.env.example`):

```bash
VITE_API_URL=http://localhost:8000
```

Optional feature flags are also read from Vite env (e.g. `VITE_FEATURE_RECOMMENDATIONS=false`).

### Windows helper

From the repo root, `start.bat` will install backend requirements (if missing) and open two
terminal windows for the API and UI using `python -m uvicorn main:app` and `npm run dev`.

## Running with Docker Compose

```bash
cp .env.example .env  # optional; set secrets/ports
docker compose up --build
```

Services:
- Frontend: http://localhost:4200 (nginx)
- Backend API: http://localhost:8000 (FastAPI)
- Postgres: exposed on `${POSTGRES_PORT:-5432}`

`docker-compose.yml` wires the backend to Postgres and forwards environment values from `.env`.
The backend applies Alembic migrations on startup when `AUTO_RUN_MIGRATIONS=true`.

## Seeding sample data (dev only)

The seed script clears existing tables and inserts sample users/events/tags/registrations for local development.

- Local (venv): `cd backend && python seed_data.py`
- Docker Compose: `docker compose exec backend python seed_data.py`

## Backups / disaster recovery

See `docs/disaster-recovery.md` for Postgres backup/restore scripts and a basic DR runbook.

Sample credentials:
- Student: `student@test.com` / `test123`
- Organizer: `organizer@test.com` / `test123`

## API overview

- Auth: `POST /register`, `POST /login`, `POST /refresh`, `GET /me`
- Events: `GET /api/events` (filters + pagination), `POST /api/events` (organizer),
  `PUT /api/events/{id}`, `DELETE /api/events/{id}` (soft-delete), `POST /api/events/{id}/restore`, `GET /api/events/{id}/ics`
  - Filters include `search`, `category`, `tags_csv`, `start_date`, `end_date`, `location`, `city`, `include_past`, plus paging.
- Registration: `POST /api/events/{id}/register`, `DELETE /api/events/{id}/register`
- Organizer: `GET /api/organizer/events/{id}/participants` (with pagination/sorting)
- Public: `GET /api/public/events`, `GET /api/public/events/{id}` (rate-limited)
- Profile: `GET /api/me/profile`, `PUT /api/me/profile` (supports `city`, `university`, `faculty`, `study_level`, `study_year`, `interest_tag_ids`)
- Metadata: `GET /api/metadata/universities` (Romanian university catalog for UI dropdowns)
- Admin: `GET /api/admin/stats`, `GET /api/admin/users`, `PATCH /api/admin/users/{userId}`, `GET /api/admin/events`,
  `POST /api/admin/events/{eventId}/registrations/{userId}/restore`
- Recommendations and search utilities are available under `/api/events` filters, plus calendar
  exports at `/api/me/calendar` for the current user.
- Docs: Swagger at `/docs`, ReDoc at `/redoc`

## Testing

- **Backend tests**: `cd backend && pytest`
- **Frontend checks**: `cd ui && npm test` (lint + typecheck + build)
- **Load tests (k6)**: `K6_BASE_URL=http://localhost:8000 k6 run loadtests/events.js`

## Pre-commit hooks (optional)

This repo includes `.pre-commit-config.yaml` to run format/lint checks before commits:

- Install: `pipx install pre-commit` (or `pip install pre-commit`)
- Enable: `pre-commit install`

Notes:
- Python hooks cover `backend/` (ruff + black).
- UI hooks cover `ui/` (prettier + eslint) and require `cd ui && npm install`.
