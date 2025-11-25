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
- [x] Docker + docker-compose for backend/frontend/Postgres with env wiring and docs.
- [x] Security headers middleware (HSTS, X-Content-Type-Options, X-Frame-Options) and CORS audit.
- [x] Health/readiness endpoint to check DB connectivity for probes.
- [x] Logging: structured logs with request IDs; log key domain events (auth, event CRUD, registrations).
- [x] Email metrics/counters and optional retry/backoff on SMTP failures.
- [x] Add organizer ability to export participants including attendance + cover URL in CSV.
- [x] Event cover images: add image upload option or validated URL regex; show placeholder on missing/failed load.
- [x] Persist filter/query params in event list for shareable links.
- [x] Add route-level guard to redirect logged-in users away from login/register.
- [x] Add frontend loading/error spinners for event details/register actions.
- [x] Improve accessibility: form labels/aria, focus states, keyboard nav on filters and pagination.
- [ ] Password reset flow (request + token + reset form) with backend email template.
- [ ] Refresh tokens with short-lived access tokens to reduce JWT leak impact.
- [ ] Per-IP and per-account rate limiting on sensitive endpoints (login, register, password reset).
- [ ] Email templating (HTML + localization) and resend confirmation option for registrations.
- [ ] Background cleanup job for expired invites/tokens and past event registrations.
- [ ] Role-based permission matrix documentation and tests ensuring unauthorized calls are blocked.
- [ ] Database indexes for common query fields (event start_time, category, owner_id, tags).
- [ ] Timezone-aware date handling end-to-end (backend, Angular date pipes, database).
- [ ] ICS calendar export for events and calendar subscription per user.
- [ ] Configuration sanity checks at startup (fail fast if essential env vars are missing).
- [ ] End-to-end tests (Playwright) for auth, event browse, register/unregister, and organizer edit flows.
- [ ] Stress/load tests for critical endpoints (event list, registration, recommendations).
- [ ] Pagination and sorting for all list endpoints (registrations, users).
- [ ] Task queue for background jobs (emails/heavy processing).
- [ ] Account deletion / data export flows for privacy regulations.
- [ ] CI caching for npm/pip to speed up pipelines and document cache keys.

## Low
- [ ] Add Prettier/ESLint config and `npm run lint` hook; backend ruff/black + make lint.
- [ ] Seed data/scripts for local dev (sample users/events with tags/covers).
- [ ] Add API docs updates for new endpoints (unregister, attendance toggle, organizer upgrade).
- [ ] Convert backend tests to pytest and expand fixtures for speed.
- [ ] Document Node/Angular version guidance (avoid odd Node versions).
- [ ] Add staging/prod Angular environment files with feature flags (e.g., recommendations toggle).
- [ ] Soft-delete support for events and registrations with an audit history.
- [ ] Admin dashboards for monitoring event stats (registrations over time, popular tags).
- [ ] Public read-only events API with stricter rate limiting for third-party integrations.
- [ ] Searchable filter bar on event list (tags, category, date range, location).
- [ ] Mobile-first layouts and responsive breakpoints for main screens.
- [ ] Skeleton loaders and optimistic updates for event registration and attendance toggles.
- [ ] Notifications center in UI (toasts/snackbars) for API success/error messages.
- [ ] Organization profile pages with logo, description, and links to their events.
- [ ] Duplicate/clone event action for organizers.
- [ ] Recommendation explanation in UI ("Because you attended X" / "Similar tags: Y").
- [ ] Pre-commit hooks for formatting (black/ruff for Python, prettier/eslint for Angular).
- [ ] Coverage reporting for backend/frontend with minimum thresholds in CI.
- [ ] Integration tests hitting a real test database (not just unit tests).
- [ ] Contract tests around API schema to keep UI and backend in sync.
- [ ] Bulk operations for organizers (bulk email registrants, bulk close events, bulk tag edits).
- [ ] "Favorite events" / "watchlist" feature for students.
- [ ] Maintenance mode flag to temporarily disable registrations during deployments.
- [ ] Draft vs published events with scheduled publishing.
- [ ] DB backup/restore scripts and disaster-recovery documentation.
- [ ] Database migration to backfill/normalize existing event data (e.g., cover_url, tags).

