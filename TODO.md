# TODO (Event Link)

## High
- [ ] Add Alembic migrations and replace `AUTO_CREATE_TABLES` in production; generate migration for cover_url/attended columns.
- [ ] Harden auth: central organizer/student dependency helpers, consistent JWT expiry validation, and rate limit login/register.
- [ ] Implement global exception/response wrapper for consistent error payloads (code/message) across APIs.
- [ ] Add organizer invite approval audit trail (store who/when upgraded, not just code).
- [ ] Student unregister flow in UI (button state, messages) wired to new DELETE endpoint.
- [ ] Organizer upgrade UI: handle invalid/missing invite code error states with UX copy.
- [ ] Participant attendance toggle: add backend tests and UI loading/error states.
- [ ] Event validation: max length constraints, cover_url validation, password complexity; return structured errors.
- [ ] Recommendations: exclude past events and respect capacity/full state.
- [ ] Event pagination: add controls for page size selection and display total pages; update backend tests for page_size.
- [ ] Add 403/404 routing guards coverage in Angular tests.
- [ ] CI pipeline (GitHub Actions): install deps, run backend tests, run Angular tests.

## Medium
- [ ] Docker + docker-compose for backend/frontend/Postgres with env wiring and docs.
- [ ] Security headers middleware (HSTS, X-Content-Type-Options, X-Frame-Options) and CORS audit.
- [ ] Health/readiness endpoint to check DB connectivity for probes.
- [ ] Logging: structured logs with request IDs; log key domain events (auth, event CRUD, registrations).
- [ ] Email metrics/counters and optional retry/backoff on SMTP failures.
- [ ] Add organizer ability to export participants including attendance + cover URL in CSV.
- [ ] Event cover images: add image upload option or validated URL regex; show placeholder on missing/failed load.
- [ ] Persist filter/query params in event list for shareable links.
- [ ] Add route-level guard to redirect logged-in users away from login/register.
- [ ] Add frontend loading/error spinners for event details/register actions.
- [ ] Improve accessibility: form labels/aria, focus states, keyboard nav on filters and pagination.

## Low
- [ ] Add Prettier/ESLint config and `npm run lint` hook; backend ruff/black + make lint.
- [ ] Seed data/scripts for local dev (sample users/events with tags/covers).
- [ ] Add API docs updates for new endpoints (unregister, attendance toggle, organizer upgrade).
- [ ] Convert backend tests to pytest and expand fixtures for speed.
- [ ] Document Node/Angular version guidance (avoid odd Node versions).
- [ ] Add staging/prod Angular environment files with feature flags (e.g., recommendations toggle).
