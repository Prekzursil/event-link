# Event Link - Claude Assistant Guide

This guide helps AI assistants understand the Event Link project structure, setup, and common tasks.

## Project Overview

Event Link is a full-stack event management platform that allows:
- **Students**: Browse, search, register for events, manage favorites
- **Organizers**: Create, manage, and track events with participant management
- **Features**: Email notifications, calendar exports, recommendations, password reset

**Tech Stack**:
- Frontend: React + Vite + TypeScript + Tailwind (Radix UI components)
- Backend: FastAPI + SQLAlchemy + PostgreSQL
- Auth: JWT with access/refresh tokens
- Email: SMTP with HTML templates
- Containerization: Docker Compose

## Directory Structure

```
event-link/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api.py             # Main API routes (45KB)
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── config.py          # Settings from .topsecret file
│   │   ├── database.py        # Database session management
│   │   ├── auth.py            # JWT token + password hashing
│   │   ├── email_service.py   # SMTP email sending
│   │   ├── email_templates.py # HTML email templates
│   │   └── logging_utils.py   # Structured logging
│   ├── alembic/               # Database migrations
│   ├── tests/                 # Unit tests
│   ├── main.py                # FastAPI app entry point
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile
│   └── .topsecret.example     # Secret configuration template
├── ui/                         # React frontend
├── docs/                      # Documentation
├── loadtests/                 # k6 performance tests
├── docker-compose.yml         # Multi-container orchestration
├── .env.example               # Environment template
├── start.bat                  # Windows helper script
└── README.md
```

## Key File Paths

### Backend Critical Files
- **Entry**: `/backend/main.py`
- **API Routes**: `/backend/app/api.py:1-1200` (all endpoints)
- **Database Models**: `/backend/app/models.py:1-150` (User, Event, Registration, Tag, FavoriteEvent, PasswordResetToken)
- **Configuration**: `/backend/app/config.py:15-58` (Settings class)
- **Auth Logic**: `/backend/app/auth.py:1-100` (JWT creation/validation, password hashing)
- **Migrations**: `/backend/alembic/versions/` (4 migration files)

### Frontend Critical Files
- **Entry**: `/ui/src/main.tsx`
- **Routes**: `/ui/src/App.tsx` (react-router)
- **Auth Context**: `/ui/src/contexts/AuthContext.tsx`
- **API Client**: `/ui/src/services/api.ts`
- **Auth Service**: `/ui/src/services/auth.service.ts`
- **Event Service**: `/ui/src/services/event.service.ts`
- **Pages**: `/ui/src/pages/` (auth, events, organizer, profile)

## Configuration

### Backend (.topsecret or .env)

**Required**:
```bash
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/eventlink
SECRET_KEY=<use: python -c "import secrets; print(secrets.token_urlsafe(32))">
```

**Optional**:
```bash
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:4200,http://127.0.0.1:4200
AUTO_CREATE_TABLES=true           # Dev only
AUTO_RUN_MIGRATIONS=true          # Auto-apply Alembic
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_MINUTES=43200  # 30 days

# Email (optional)
EMAIL_ENABLED=true
SMTP_HOST=smtp.mailhost.com
SMTP_PORT=587
SMTP_USERNAME=user
SMTP_PASSWORD=pass
SMTP_SENDER=notifications@eventlink.test
SMTP_USE_TLS=true
```

### Frontend (Vite env)

Set the API base URL via `VITE_API_URL`. Example `ui/.env.local`:

```bash
VITE_API_URL=http://localhost:8000
```

## Running the Application

### Local Development

#### Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head  # Optional: apply migrations
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Health Check**: http://localhost:8000/api/health
**Swagger Docs**: http://localhost:8000/docs

#### Frontend:
```bash
cd ui
npm install
npm run dev  # Runs on http://localhost:5173
```

### Docker Compose (Recommended)

```bash
cp .env.example .env
docker compose up --build
```

Services:
- Frontend: http://localhost:4200
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432

### Windows Helper

```bash
start.bat  # Opens two terminals for backend + frontend
```

## API Endpoints Summary

### Authentication
- `POST /register` - User registration (student role)
- `POST /login` - User login (returns access + refresh tokens)
- `POST /refresh` - Refresh access token
- `GET /me` - Current user profile
- `POST /password/forgot` - Request password reset email
- `POST /password/reset` - Confirm password reset

### Events
- `GET /api/events` - List events (filters: search, category, date_from, date_to, location, tags, skip, limit)
- `GET /api/events/{id}` - Event details
- `POST /api/events` - Create event (organizer only)
- `PUT /api/events/{id}` - Update event (owner or admin)
- `DELETE /api/events/{id}` - Delete event (owner or admin)
- `POST /api/events/{id}/clone` - Clone event (organizer only)
- `GET /api/events/{id}/ics` - Export event as iCalendar

### Registration
- `POST /api/events/{id}/register` - Register for event
- `POST /api/events/{id}/register/resend` - Resend registration email
- `DELETE /api/events/{id}/register` - Unregister from event
- `GET /api/organizer/events/{id}/participants` - List participants (owner or admin)
- `PUT /api/organizer/events/{id}/participants/{user_id}` - Update attendance (owner or admin)

### Admin
- `GET /api/admin/stats` - Summary stats (registrations over time, popular tags)
- `GET /api/admin/users` - List users + stats
- `PATCH /api/admin/users/{id}` - Update user role/active flag
- `GET /api/admin/events` - List events (including unpublished/deleted with filters)

### User Events
- `GET /api/me/events` - User's registered events
- `GET /api/me/favorites` - User's favorite events
- `POST /api/events/{id}/favorite` - Add to favorites
- `DELETE /api/events/{id}/favorite` - Remove from favorites

### Organizer
- `GET /api/organizer/events` - User's created events
- `GET /api/organizers/{id}` - Organizer profile
- `PUT /api/organizers/me/profile` - Update organizer profile

### Utilities
- `GET /api/recommendations` - Personalized event recommendations
- `GET /api/me/calendar` - User's event calendar (iCalendar)
- `GET /api/health` - Health check

## Database Schema

### Models (backend/app/models.py)

**User**:
- id, email (unique), hashed_password, name, role (student/organizator)
- timestamps: created_at, updated_at
- relationships: owned_events, registrations, favorite_events

**Event**:
- id, title, description, category, date, location, max_participants
- owner_id (FK to User)
- cover_url, organizer_name, organizer_website, is_published, publish_date
- timestamps: created_at, updated_at
- relationships: owner, registrations, tags, favorited_by

**Registration** (junction):
- id, user_id (FK), event_id (FK), attended (boolean)
- timestamp: registered_at
- unique constraint: (user_id, event_id)

**Tag**:
- id, name (unique)
- many-to-many with Event via event_tags

**FavoriteEvent**:
- id, user_id (FK), event_id (FK)
- timestamp: created_at
- unique constraint: (user_id, event_id)

**PasswordResetToken**:
- id, user_id (FK), token (unique), expires_at, used_at

### Migrations

Use Alembic for schema changes:
```bash
cd backend
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

## Testing

### Backend Unit Tests
```bash
cd backend
pytest
```

### Frontend Unit Tests
```bash
cd ui
npm test  # eslint + typecheck + build
```

### Load Tests (k6)
```bash
K6_BASE_URL=http://localhost:8000 k6 run loadtests/events.js
```

## Common Development Tasks

### Add a new API endpoint

1. Define Pydantic schemas in `/backend/app/schemas.py`
2. Add route handler in `/backend/app/api.py`
3. Update permissions in route decorator if needed
4. Add tests in `/backend/tests/test_api.py`

### Add a new database field

1. Update model in `/backend/app/models.py`
2. Generate migration: `alembic revision --autogenerate -m "Add field_name"`
3. Review migration file in `/backend/alembic/versions/`
4. Apply: `alembic upgrade head`
5. Update Pydantic schemas in `/backend/app/schemas.py`

### Add a new UI page or component

1. Pages live under `/ui/src/pages/*` and are wired in `/ui/src/App.tsx`
2. Reusable components live under `/ui/src/components/*`
3. API calls go through `/ui/src/services/*` (axios client in `/ui/src/services/api.ts`)

### Debugging Tips

**Backend**:
- Check logs for request IDs and errors
- Use `/docs` for interactive API testing
- View SQL queries: `echo=True` in database.py

**Frontend**:
- Open browser DevTools Network tab
- Check console for HTTP errors
- Use React DevTools extension

**Database**:
- Connect: `psql $DATABASE_URL`
- View tables: `\dt`
- Check migrations: `alembic current`

## Architecture Patterns

### Backend
- **Dependency Injection**: FastAPI's `Depends()` for database sessions
- **Middleware**: CORS, request logging, request ID tracking
- **Background Tasks**: Async email sending via `BackgroundTasks`
- **JWT Auth**: OAuth2PasswordBearer with access + refresh tokens
- **Validation**: Pydantic models for request/response validation
- **ORM**: SQLAlchemy 2.0 with relationship loading strategies

### Frontend
- **Routing**: react-router routes in `ui/src/App.tsx` (guarded routes via wrappers)
- **State**: Auth state via `AuthContext` (`ui/src/contexts/AuthContext.tsx`)
- **HTTP**: axios client in `ui/src/services/api.ts` with feature services per domain
- **UI**: Tailwind + Radix UI primitives + small local components
- **i18n**: lightweight EN/RO translation helpers used by UI and emails

## Security Notes

- Passwords hashed with bcrypt (12 rounds)
- JWT tokens signed with HS256
- CORS configured via ALLOWED_ORIGINS
- Rate limiting on registration endpoint
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via React escaping (avoid `dangerouslySetInnerHTML`)

## Common Issues & Solutions

**Backend won't start**:
- Check DATABASE_URL is correct
- Ensure PostgreSQL is running
- Verify .topsecret file exists with SECRET_KEY

**Frontend can't connect**:
- Verify backend is running on port 8000
- Check CORS settings in backend config.py
- Confirm `VITE_API_URL` (or fallback) points at the API base URL

**Database migrations fail**:
- Check for conflicting migrations: `alembic current`
- Reset: `alembic downgrade base && alembic upgrade head`
- Ensure no manual schema changes outside Alembic

**Email not sending**:
- Check EMAIL_ENABLED=true
- Verify SMTP credentials are correct
- View logs for SMTP errors

## Useful Commands Cheat Sheet

```bash
# Backend
cd backend && source .venv/bin/activate
python -m uvicorn main:app --reload
alembic upgrade head
alembic revision --autogenerate -m "message"
pytest --cov=app

# Frontend
cd ui
npm run dev
npm test
npm run build
npm run preview

# Docker
docker compose up --build
docker compose down -v  # Remove volumes
docker compose logs -f backend
docker compose exec backend alembic upgrade head

# Database
psql $DATABASE_URL
\dt  # List tables
\d+ users  # Describe table

# Load testing
K6_BASE_URL=http://localhost:8000 k6 run loadtests/events.js
```

## Project Status

- MVP completed with core features
- Auth system with JWT tokens
- Event lifecycle (create, update, delete, clone)
- Registration system with email notifications
- Recommendations based on user favorites
- Password reset functionality
- CI/CD setup
- Docker deployment ready

## Next Steps / Future Enhancements

Check issues and project boards for planned features.
