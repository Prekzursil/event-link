# ML recommendations (v1)

This project supports an **offline-trained** (batch) ML recommender that writes a per-user cached ranking to the DB.
At request time, `GET /api/recommendations` prefers this cache (if present + fresh) and falls back to the existing
heuristic recommender when needed.

## Data used (today)

The trainer uses only data already stored in the DB:

- User interest tags (`user_interest_tags`)
- Event tags (`event_tags`)
- Registrations (and `attended`) + favorites
- Interaction tracking (`event_interactions`): impressions/clicks/views/dwell/share/search/filter/register/unregister
- Event attributes: `category`, `city`, `owner_id`, `start_time`
- Popularity proxy: number of registrations per event

## Storage

Recommendations are stored in `user_recommendations`:

- `user_id`, `event_id`, `score`, `rank`
- `model_version`, `generated_at`, `reason`

Trained model weights are stored in `recommender_models`:

- `model_version`, `feature_names`, `weights`, `meta`
- `is_active` marks which model to use for online refresh / scoring

## How to run training

1. Ensure DB migrations are applied (includes `0013_user_recommendations_cache`).
2. Run the trainer against the target DB:

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"
python backend/scripts/recompute_recommendations_ml.py
```

Useful flags:

- `--dry-run` (train + evaluate, no DB writes)
- `--top-n 50`
- `--epochs 6 --lr 0.35 --l2 0.01`

The script prints a basic offline metric: `hitrate@10`.

## Per-user refresh (near-real-time personalization)

To refresh recommendations for a single user using the last persisted model weights:

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"
python backend/scripts/recompute_recommendations_ml.py --user-id 123 --skip-training
```

This updates `user_recommendations` only for that user.

## Scheduled retraining (cron/K8s)

This repo includes a DB-backed task queue + worker (`docker-compose.yml` service `worker`), and a job type that can
run the ML trainer:

- `recompute_recommendations_ml`
- `refresh_user_recommendations_ml` (used for near-real-time per-user refresh)

To enqueue the retraining job (idempotent: won’t enqueue if one is queued/running):

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"
python backend/scripts/enqueue_scheduled_jobs.py --retrain-ml --top-n 50
```

Example cron (nightly):

```cron
0 3 * * * cd /path/to/event-link && DATABASE_URL=... SECRET_KEY=... python backend/scripts/enqueue_scheduled_jobs.py --retrain-ml
```

In Kubernetes, run the same command from a CronJob using the `backend` image.

## Runtime behavior

`GET /api/recommendations`:

- uses cached rows when `recommendations_use_ml_cache=true` and the cache age is within
  `recommendations_cache_max_age_seconds`
- falls back to the existing tag/popularity heuristic otherwise

When enabled, `POST /api/analytics/interactions` can enqueue `refresh_user_recommendations_ml` jobs to keep a student's
cache fresh after meaningful interactions (click/view/share/register/search/filter). This is gated by:

- `task_queue_enabled=true` (worker running)
- `recommendations_realtime_refresh_enabled=true`
- `recommendations_realtime_refresh_min_interval_seconds` (throttle)

## Monitoring

Admin metrics endpoint:

- `GET /api/admin/personalization/metrics?days=30` (CTR + registration conversion from tracked interactions)
