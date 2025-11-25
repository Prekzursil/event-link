# Event Link

A full-stack application with Angular frontend and FastAPI backend.

## Project Structure

```
event-link/
├── ui/                 # Angular frontend application
├── backend/           # FastAPI backend application
├── .gitignore        # Git ignore file
└── README.md         # This file
```

## Prerequisites

- **Node.js**: Version 20+ (LTS recommended)
- **npm**
- **Python**: Version 3.11+

## Configuration (backend)

Create `backend/.topsecret` (env file) with at least:
```
DATABASE_URL=postgresql://user:pass@host:5432/db
SECRET_KEY=change-me
# Comma-separated or JSON list; defaults cover localhost/127.0.0.1 for ports 3000 and 4200
ALLOWED_ORIGINS=http://localhost:4200,http://localhost:3000
AUTO_CREATE_TABLES=true
# Email (optional)
SMTP_HOST=smtp.mailhost.com
SMTP_PORT=587
SMTP_USERNAME=user
SMTP_PASSWORD=pass
SMTP_SENDER=notifications@eventlink.test
SMTP_USE_TLS=true
```

Key settings:
- `ALLOWED_ORIGINS`: CORS origins list (comma/JSON list). Defaults suit local dev; set staging/prod origins as needed.
- `AUTO_CREATE_TABLES`: Set `true` for local/dev convenience; use migrations in prod.
- `SECRET_KEY`: JWT signing secret.
- `DATABASE_URL`: Point to Postgres/SQLite/etc.

## Installation

### Backend Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```

### Frontend Setup (Angular)

1. Navigate to the UI directory:
   ```bash
   cd ui
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Running the Application
From the repo root you can also double-click `start.bat` on Windows to launch both servers (installs backend deps if missing).

### Start the Backend (FastAPI)

From the `backend` directory:

```bash
# Option 1: Using uv
uv run uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Option 2: After activating virtual environment
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Option 3: Using Python directly
python main.py
```

The backend will be available at: http://localhost:8000

- API Documentation (Swagger): http://localhost:8000/docs
- Alternative API Documentation (ReDoc): http://localhost:8000/redoc

### Start the Frontend (Angular)

From the `ui` directory:

```bash
npm start
# or
ng serve
```

The frontend will be available at: http://localhost:4200. Configure the API base URL in `ui/src/environments/environment.ts` (replaced with `environment.prod.ts` for production builds).

## API Endpoints (high level)

- `POST /register` – student registration + JWT
- `POST /login` – login
- `GET /api/events` – paginated events with filters
- `POST /api/events` – organizer create (auth)
- `POST /api/events/{id}/register` – student register for event
- `GET /api/recommendations` – student recommendations
- Plus organizer tools, participant views, and health at `/api/health`.

## Docker Compose

Quick start with containers (requires Docker):

```bash
cp .env.example .env  # adjust secrets if needed
docker compose up --build
```

Services:
- Frontend: http://localhost:4200 (served by nginx)
- Backend API: http://localhost:8000 (FastAPI)
- Postgres: exposed on ${POSTGRES_PORT:-5432}

Environment overrides come from `.env` (see `.env.example`). The backend runs Alembic migrations on startup before launching Uvicorn.
