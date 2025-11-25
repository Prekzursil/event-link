# TODO (Event Link)

## High
- [x] Add Alembic migrations and replace `AUTO_CREATE_TABLES` in production; generate migration for cover_url/attended columns.
- [x] Harden auth: central organizer/student dependency helpers, consistent JWT expiry validation, and rate limit login/register.
- [x] Implement global exception/response wrapper for consistent error payloads (code/message) across APIs.
- [x] Add organizer invite approval audit trail (store who/when upgraded, not just code).
- [x] Student unregister flow in UI (button state, messages) wired to new DELETE endpoint.
- [x] Organizer upgrade UI: handle invalid/missing invite code error states with UX copy.
- [x] Participant attendance toggle: add backend tests and UI loading/error states.
- [x] Event validation: max length constraints, cover_url validation, password complexity; return structured errors.
- [x] Recommendations: exclude past events and respect capacity/full state.
- [x] Event pagination: add controls for page size selection and display total pages; update backend tests for page_size.
- [x] Add 403/404 routing guards coverage in Angular tests.
- [x] CI pipeline (GitHub Actions): install deps, run backend tests, run Angular tests.
- [x] CI: run Angular tests headless (ChromeHeadless) to avoid display errors in Actions.
- [x] Make sure emailing actually works, and configure it otherwise so that mails are being sent.

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

## Suggestions (to triage)
- [ ] Add end-to-end tests (Playwright) covering auth, event browse, register/unregister, and organizer edit flows.
- [ ] Implement email templating (HTML + localization) and resend confirmation option for registrations.
- [ ] Add background cleanup job for expired invites/tokens and past event registrations.
- [ ] Add CI caching for npm/pip to speed up pipelines and document cache keys.
- [ ] Provide DB backup/restore scripts and document disaster-recovery steps.
- [ ] Add role-based permission matrix documentation and tests ensuring organizers/students cannot call unauthorized endpoints.
- [ ] Implement refresh tokens and short-lived access tokens to reduce the blast radius of leaked JWTs.
- [ ] Add a password reset flow (request + token + reset form) and backend email template for it.
- [ ] Enforce stricter password rules and add a password strength meter in the UI.
- [ ] Add per-IP and per-account rate limiting on sensitive endpoints (login, register, password reset).
- [ ] Introduce database-level indexes for common query fields (event start_time, category, owner_id, tags).
- [ ] Add a database migration that backfills or normalizes existing event data (e.g., cover_url, tags).
- [ ] Add stress/load tests for critical endpoints (event list, registration, recommendations).
- [ ] Implement soft-delete support for events and registrations with an audit history.
- [ ] Add admin-only dashboards for monitoring event stats (registrations over time, popular tags).
- [ ] Expose a public read-only events API with stricter rate limiting for third-party integrations.
- [ ] Add ICS calendar export for events and calendar subscription per user.
- [ ] Implement timezone-aware date handling end-to-end (backend, Angular date pipes, database).
- [ ] Add a searchable filter bar to the event list (tags, category, date range, location).
- [ ] Add mobile-first layouts and responsive design breakpoints for the main screens.
- [ ] Add skeleton loaders and optimistic updates for event registration and attendance toggles.
- [ ] Implement a notifications center in the UI (toasts/snackbars) for API success/error messages.
- [ ] Add organization profile pages with logo, description, and links to their events.
- [ ] Allow organizers to duplicate an event (clone details, dates, tags) to speed up creation.
- [ ] Add a simple recommendation explanation in the UI (“Because you attended X” / “Similar tags: Y”).
- [ ] Implement server-side logging of key audit events (login, role changes, event updates).
- [ ] Add structured JSON logging in the backend with correlation IDs per request.
- [ ] Create Dockerfiles for backend and frontend plus a docker-compose setup for local dev.
- [ ] Add pre-commit hooks for formatting (black/ruff for Python, prettier/eslint for Angular).
- [ ] Add coverage reporting for backend and frontend and set a minimum coverage threshold in CI.
- [ ] Introduce integration tests that hit a real test database instead of only unit tests.
- [ ] Add contract tests around the API schema so UI and backend stay in sync.
- [ ] Implement pagination and sorting for all list endpoints, not just events (registrations, users).
- [ ] Add bulk operations for organizers (bulk email registrants, bulk close events, bulk tag edits).
- [ ] Add a “favorite events” or “watchlist” feature for students.
- [ ] Implement account deletion / data export flows to support privacy and data regulations.
- [ ] Introduce configuration sanity checks at startup (fail fast if essential env vars are missing).
- [ ] Add health and readiness endpoints for the backend (DB connectivity, migrations status).
- [ ] Add a maintenance mode flag to temporarily disable registrations during deployments.
- [ ] Implement background jobs via a task queue (Celery/RQ) for email sending and heavy processing.
- [ ] Add UI and API support for draft vs published events and schedule publishing.


