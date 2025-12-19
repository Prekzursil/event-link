# Notifications (digests + filling fast)

This project supports email notifications driven by background jobs.

## User preferences

Students can opt in/out via API:

- `GET /api/me/notifications`
- `PUT /api/me/notifications`

Fields:

- `email_digest_enabled` (weekly digest)
- `email_filling_fast_enabled` (capacity alerts for favorited events)

## Job types

- `send_weekly_digest`
  - Enqueues one `send_email` job per opted-in student (idempotent per user/week).
- `send_filling_fast_alerts`
  - Enqueues `send_email` jobs for opted-in students when a favorited event is near capacity (idempotent per user/event).

Delivery deduplication is stored in `notification_deliveries`.

## Scheduling

Use the helper script (safe to run repeatedly; won’t enqueue if a job is already queued/running):

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"

# weekly (e.g., Mondays)
python backend/scripts/enqueue_scheduled_jobs.py --weekly-digest

# hourly/daily
python backend/scripts/enqueue_scheduled_jobs.py --filling-fast
```

