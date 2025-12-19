# ML recommendations

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

To enqueue the retraining job (idempotent: won’t enqueue if one is queued/running). Deduplication is enforced at the DB
level via `background_jobs.dedupe_key` (unique on `(job_type, dedupe_key)`), and `enqueue_job()` returns the existing
queued/running job on conflict.

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

## Online learning (lightweight user embedding)

When enabled, `POST /api/analytics/interactions` also updates a student's implicit interest tags based on interactions
and search/filter usage:

- table: `user_implicit_interest_tags`
- gated by `recommendations_online_learning_enabled=true`
- uses `recommendations_online_learning_dwell_threshold_seconds` to treat long dwell as a positive signal

This does **not** update the global model weights continuously; it updates per-user implicit interests so near-real-time
re-scoring can react without a full retrain.

## Quality guardrails (CTR/conversion rollback)

Guardrails evaluate recent personalization quality using tracked interactions and automatically roll back the active
model if it underperforms the baseline.

- job type: `evaluate_personalization_guardrails`
- enable via `personalization_guardrails_enabled=true`
- enqueue via `python backend/scripts/enqueue_scheduled_jobs.py --guardrails` (or `--all`)

The evaluator compares `events_list` interactions where `meta.sort` is `recommended` vs `time` (CTR and click→register
conversion within a time window). On failure it activates the previous model and triggers a cache recompute.

## Admin controls

- `GET /api/admin/personalization/status` (queue/flags + active model version)
- `POST /api/admin/personalization/guardrails/evaluate` (enqueue guardrails evaluation)
- `POST /api/admin/personalization/models/activate` (activate a specific model version; optional recompute)

## Ops checklist

- Run a worker (`task_queue_enabled=true`) if you expect scheduled jobs / realtime refresh / guardrails to run.
- Run at least one retrain to persist an active model (`recommender_models.is_active=true`).
- Enable `recommendations_realtime_refresh_enabled=true` for near-real-time per-user refresh.

## Monitoring

Admin metrics endpoint:

- `GET /api/admin/personalization/metrics?days=30` (CTR + registration conversion from tracked interactions)
