# ML-powered personalization (recommendations)

This project implements an **offline-trained ML recommender** that:

1. Trains a lightweight ranking model (logistic regression) from existing product data.
2. Writes **per-user top-N recommendations** into the database (`user_recommendations`).
3. Serves recommendations via `GET /api/recommendations` and can rank the main event list via `GET /api/events?sort=recommended`.
4. Supports **near-real-time personalization** by updating per-user implicit interests and optionally refreshing the cache through the worker.

The ML system is intentionally pragmatic: it is designed to run inside the existing FastAPI + Postgres stack with no external ML
infrastructure required.

## Contents

- TL;DR
- Scope: goals and non-goals
- Architecture
- Data sources and storage tables
- Feature engineering
- Training data construction (labels, weights, negative sampling)
- Model training and offline evaluation
- Serving behavior and cache freshness
- Interaction tracking + online learning + near-real-time refresh
- Scheduled retraining and worker jobs
- Quality guardrails (CTR/conversion rollback)
- Admin endpoints
- Configuration reference
- Ops checklist + troubleshooting
- Privacy notes

## TL;DR

- Offline trainer + cache writer: `backend/scripts/recompute_recommendations_ml.py`
  - trains logistic regression (SGD + L2)
  - persists model weights in `recommender_models`
  - persists per-user top-N in `user_recommendations`
- Serving + sorting:
  - `GET /api/recommendations` prefers cached ML rows when fresh; otherwise falls back to heuristic ranking
  - `GET /api/events?sort=recommended` can use cached ranks for the events list
- Interaction tracking:
  - `POST /api/analytics/interactions` stores telemetry in `event_interactions`
  - optionally updates per-user implicit interest scores (tags/categories/cities)
  - optionally enqueues a per-user refresh job
- Guardrails:
  - `evaluate_personalization_guardrails` job compares CTR + click→register conversion for recommended vs time sorting
  - can roll back `recommender_models.is_active` if quality drops and re-score using the previous model

## Scope, goals, non-goals

### Goals

- Improve and personalize discovery for **student** users:
  - recommended list: `GET /api/recommendations`
  - recommended ranking in the main list: `GET /api/events?sort=recommended`
- Use only data already present in the application (no external data dependencies).
- Provide minimal explainability via a `reason` string shown as `recommendation_reason` in the UI.
- Support safe rollout:
  - A/B percentage for the recommended sorting experiment
  - quality guardrails with automatic rollback

### Non-goals (current state)

- “True online learning” of global weights (global weights are updated by retraining jobs, not continuously).
- A deep-learning recommender or vector database.
- Fully-fledged MLOps (feature store, automated hyperparameter search, model registry service, etc.).

## Architecture (how it fits together)

### Components

- UI (React/Vite): displays lists and sends interaction telemetry.
- Backend API (FastAPI): serves rankings, stores interactions, updates per-user interests, exposes admin controls.
- Postgres: source of truth for all ML artifacts and training signals.
- Worker (DB-backed queue): runs retraining, per-user refresh, and guardrails.

### Code entry points

- Offline trainer: `backend/scripts/recompute_recommendations_ml.py`
- Cron/CronJob job enqueuer: `backend/scripts/enqueue_scheduled_jobs.py`
- Task queue + job types: `backend/app/task_queue.py`
- Serving + telemetry endpoints:
  - cached recommendation fetch: `backend/app/api.py` (`_load_cached_recommendations`, `_recommendations_cache_is_fresh`)
  - recommendations endpoint: `backend/app/api.py` (`GET /api/recommendations`)
  - recommended sorting: `backend/app/api.py` (`GET /api/events`, `sort=recommended`)
  - interactions endpoint: `backend/app/api.py` (`POST /api/analytics/interactions`)

## Data sources (signals used)

The trainer uses only data stored in the DB:

- Explicit preferences:
  - user interest tags: `user_interest_tags`
- Content metadata:
  - event tags: `event_tags`
  - event fields: `category`, `city`, `owner_id`, `start_time`, `max_seats`, `publish_at`, `status`, `deleted_at`
- Explicit positive outcomes:
  - registrations (`registrations`, with `attended`)
  - favorites (`favorite_events`)
- Implicit feedback / analytics:
  - `event_interactions` per event: `impression`, `click`, `view`, `dwell`, `share`, `favorite`, `register`, `unregister`
  - `event_interactions` without event: `search`, `filter` (`event_id = NULL`, details stored in `meta`)
- Popularity proxy:
  - `seats_taken = COUNT(registrations)`

## Storage model (what is persisted)

### Cached recommendations (`user_recommendations`)

Each row represents one event in one student’s top-N ranking:

- `user_id`, `event_id`
- `score` (sigmoid output of the model)
- `rank` (1..N)
- `model_version` (which model generated it)
- `generated_at` (freshness check)
- `reason` (human-readable explanation shown by the UI)

### Persisted models (`recommender_models`)

Stores the active model weights used for refresh/scoring:

- `model_version` (string identifier)
- `feature_names` (must match the trainer’s `FEATURE_NAMES` order)
- `weights` (list of floats)
- `meta` (training metadata such as hitrate@10 and hyperparameters)
- `is_active` (the currently active model; guardrails can roll back to a previous model)

### Interaction tracking (`event_interactions`)

Raw telemetry used for training and for guardrails:

- `user_id` (nullable for anonymous interactions)
- `event_id` (nullable for search/filter)
- `interaction_type` (string)
- `occurred_at`
- `meta` (JSON dict)

Common `meta` fields:

- impressions (from events list):
  - `source`: `"events_list"`
  - `sort`: `"time"` or `"recommended"`
  - `position`: numeric index in the list (optional)
- dwell:
  - `seconds`: number of seconds spent on the event page (optional)
- search/filter:
  - `tags`: list of tag strings (optional)
  - `category`: category string (optional)
  - `city`: city string (optional)

### Online-learning state (`user_implicit_interest_*`)

Per-user implicit preference scores updated by the interactions endpoint:

- `user_implicit_interest_tags`: `user_id`, `tag_id`, `score`, `last_seen_at`
- `user_implicit_interest_categories`: `user_id`, `category`, `score`, `last_seen_at`
- `user_implicit_interest_cities`: `user_id`, `city`, `score`, `last_seen_at`

## Feature engineering (what the model learns)

The model is logistic regression and consumes a small fixed feature vector defined in:

- `backend/scripts/recompute_recommendations_ml.py` (`FEATURE_NAMES`, `_build_feature_vector`)

### Feature list (order matters)

The `feature_names` persisted in `recommender_models` must match this order exactly:

1. `bias`: constant 1.0
2. `overlap_interest_ratio`:
   - sum of the user’s interest-tag weights over event tags, divided by number of event tags
3. `overlap_history_ratio`:
   - fraction of event tags that the user has previously interacted with (from registration/favorite history)
4. `same_city`:
   - 1.0 if user city equals event city; otherwise a fallback weight from implicit city preferences
5. `category_match`:
   - 1.0 if event category is in user’s history; otherwise a fallback weight from implicit category preferences
6. `organizer_match`:
   - 1.0 if the organizer is in user’s history; else 0.0
7. `popularity`:
   - `min(log1p(seats_taken)/5, 1.0)`
8. `days_until`:
   - time-to-event normalized to `[0..1]` over a 180-day window (0 for past events)

### How per-user preferences are built in training

For each student, the trainer builds:

- `interest_tag_weights`:
  - explicit tags from `user_interest_tags`: weight = 1.0
  - implicit tags from `user_implicit_interest_tags`: weight = decayed(score)/max_score
- history sets (from positive history, including the offline holdout):
  - `history_tags`
  - `history_categories`
  - `history_organizer_ids`
- implicit fallback weights:
  - `category_weights` from `user_implicit_interest_categories` (decayed + normalized)
  - `city_weights` from `user_implicit_interest_cities` (decayed + normalized)

## Training data construction (labels + weighting)

Training examples are `(user, event)` feature vectors with:

- label `y ∈ {0,1}`
- sample weight `w` (importance / confidence)

All training logic lives in `backend/scripts/recompute_recommendations_ml.py`.

### Positive labels (`y=1`)

Positives come from:

- registrations:
  - base weight = `1.0`
  - plus `+0.5` if `attended` is true
- favorites:
  - weight = `1.2`
- interaction telemetry (if present):
  - click: `0.4`
  - view: `0.25`
  - dwell: `0.35`, increased up to `0.8` based on `meta.seconds`
  - share: `0.6`
  - favorite: `1.2`
  - register: `1.0`

If multiple signals exist for the same `(user_id, event_id)`, the trainer keeps the maximum weight.

### Negative labels (`y=0`)

Negatives come from:

- explicit negative: `unregister`
  - weight = `2.0`
  - also removes any positive label for the same `(user, event)` pair
- negative sampling per positive:
  - default: `--negatives-per-positive 3`
  - prefers impression-exposed events (shown but not converted) when available

#### Impression-aware negative weighting

When sampling negatives from impressions, the weight depends on the impression position:

- position ≤ 2: `0.25`
- position ≤ 5: `0.15`
- position ≤ 10: `0.10`
- otherwise: `0.05`
- unknown position: `0.05`

This approximates exposure bias (items shown high in the list but ignored are stronger negatives).

### Weak positives from search/filter intent

The trainer also converts `search`/`filter` telemetry (where `event_id = NULL`) into weak supervision:

- For each user with search/filter signals (tags/category/city), it tries to add up to 3 weak-positive examples:
  - randomly sample candidate events
  - accept events matching inferred tags/category/city
  - add with label `y=1` and weight `0.15`

This weight is intentionally low: it nudges the model without overfitting on noisy intent.

## Model training (algorithm)

The trainer uses **logistic regression** trained with **SGD** and **L2 regularization**:

- prediction: `p = sigmoid(w · x)`
- loss: weighted binary cross-entropy
- update: SGD gradient step with L2 weight decay

Default hyperparameters (script flags):

- epochs: `6`
- learning rate: `0.35`
- L2: `0.01`
- seed: `1337`

## Offline evaluation (hitrate@10)

After training, the script prints `hitrate@10`, computed as:

- for each user with at least 2 positives:
  - hold out one positive event
  - sample `--eval-negatives` random negatives
  - score all candidates and check whether the held-out positive is in the top-10

This is mainly a smoke test; production quality is monitored by guardrails (CTR + conversion).

## Cache write behavior (what gets recommended)

After training (or when refreshing with `--skip-training`), the script writes `user_recommendations` for each target student.

Eligibility filters applied before ranking:

- `status == "published"`
- `publish_at` is null or already in the past
- not in the past (`start_time >= now`)
- not full (`seats_taken < max_seats` when max seats is set)
- exclude events the user is already registered for

## Serving behavior (API)

### `GET /api/recommendations`

Implementation: `backend/app/api.py` (`recommended_events`, `_load_cached_recommendations`)

1. If `recommendations_use_ml_cache=true` and cached rows are fresh, return cached recommendations (up to 10).
2. Otherwise, fall back to heuristic recommendations:
   - tag match from history + profile tags
   - if still empty: popular/upcoming events (registrations count, then `start_time`)

Personalization exclusions are always respected when serving:

- events from blocked organizers are excluded
- events containing hidden tags are excluded

### `GET /api/events` recommended sorting

If the current user is a student and has a fresh cache, `GET /api/events?sort=recommended` orders results by
`user_recommendations.rank`.

There is also an experiment hook: if the client does not explicitly set `sort`, the backend can auto-select recommended
sorting for a percentage of students:

- experiment: `personalization_ml_sort`
- percent: `experiments_personalization_ml_percent`

### “Reason” strings (“Why am I seeing this?”)

The trainer writes a `reason` string to `user_recommendations`, which the API passes through as `recommendation_reason`.
The API may append a “Near you: <city>” suffix when the event city matches the user city.

## Interaction tracking + online learning + near-real-time refresh

### `POST /api/analytics/interactions`

This endpoint stores analytics events in `event_interactions`. When enabled, it also updates per-user implicit interests and may enqueue a refresh job.

Gating:

- `analytics_enabled=true`
- rate-limited by `analytics_rate_limit` and `analytics_rate_window_seconds`

### Online learning updates (per-user implicit interests)

Enabled by: `recommendations_online_learning_enabled=true`

Signals used:

- per-event interactions: `click`, `view`, `dwell`, `share`, `favorite`, `register`
- search/filter (no event): adds small deltas from `meta.tags`, `meta.category`, `meta.city`

The update logic:

- exponential decay using `recommendations_online_learning_decay_half_life_hours`
- score cap `recommendations_online_learning_max_score`
- hidden tags are excluded from implicit tag updates

Note: this updates per-user implicit preference scores; it does not update the global model weights continuously.

### Near-real-time refresh (re-scoring using the last active model)

Enabled by:

- `task_queue_enabled=true`
- `recommendations_use_ml_cache=true`
- `recommendations_realtime_refresh_enabled=true`

The endpoint enqueues a per-user refresh when the batch includes a meaningful signal:

- click/view/share/favorite/register/unregister/search/filter
- dwell ≥ 10 seconds

Throttle:

- uses the latest `user_recommendations.generated_at`
- skips if age is below `recommendations_realtime_refresh_min_interval_seconds`

Enqueued job:

- job type: `refresh_user_recommendations_ml`
- payload: `{"user_id": <id>, "top_n": <...>, "skip_training": true}`
- dedupe key: `<user_id>` (at most one queued/running refresh per user)

## Scheduled retraining (cron/K8s)

The task queue supports these ML-related job types (`backend/app/task_queue.py`):

- `recompute_recommendations_ml` (train + rewrite caches)
- `refresh_user_recommendations_ml` (rewrite cache for one user using persisted weights)
- `evaluate_personalization_guardrails` (CTR/conversion checks + auto-rollback)

### Enqueue scheduled jobs

Use `backend/scripts/enqueue_scheduled_jobs.py`:

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"

python backend/scripts/enqueue_scheduled_jobs.py --retrain-ml --top-n 50
python backend/scripts/enqueue_scheduled_jobs.py --guardrails
python backend/scripts/enqueue_scheduled_jobs.py --all
```

### Example cron (nightly)

```cron
0 3 * * * cd /path/to/event-link && DATABASE_URL=... SECRET_KEY=... python backend/scripts/enqueue_scheduled_jobs.py --retrain-ml --guardrails
```

In Kubernetes, run the same command from a CronJob using the `backend` image.

## Quality guardrails (CTR/conversion rollback)

Implementation: `backend/app/task_queue.py` (`_evaluate_personalization_guardrails`)

Enabled by: `personalization_guardrails_enabled=true`

Signals used (from `event_interactions`):

- only interactions with `meta.source == "events_list"`
- variants identified by `meta.sort in {"recommended","time"}`
- impressions: `interaction_type == "impression"`
- clicks: `interaction_type == "click"`
- conversions: `interaction_type == "register"` within a `click_to_register_window_hours` window after a click for the same (user,event)

Computed metrics:

- CTR: `clicks / impressions`
- click→register conversion: `registers / clicks`

Decision:

- requires minimum volume for both variants: `personalization_guardrails_min_impressions`
- rollback if CTR or conversion drops more than configured thresholds:
  - `personalization_guardrails_ctr_drop_ratio`
  - `personalization_guardrails_conversion_drop_ratio`

Rollback action:

1. Deactivate the current model and activate the previous model in `recommender_models`.
2. Enqueue a global cache rewrite using `skip_training=true` (re-score using the previous model).

## Admin endpoints

- `GET /api/admin/personalization/status` (queue/flags + active model version)
- `GET /api/admin/personalization/metrics?days=30` (CTR + conversion from tracked interactions)
- `POST /api/admin/personalization/guardrails/evaluate` (enqueue guardrails evaluation)
- `POST /api/admin/personalization/models/activate` (activate a specific model version; optional recompute)

## Configuration reference (env vars)

Settings live in `backend/app/config.py` (pydantic settings). Key flags:

### Core prerequisites

- `DATABASE_URL` (required)
- `SECRET_KEY` (required)

### Analytics

- `ANALYTICS_ENABLED` (default: `true`)
- `ANALYTICS_RATE_LIMIT` (default: `120`)
- `ANALYTICS_RATE_WINDOW_SECONDS` (default: `60`)

### ML cache + refresh

- `RECOMMENDATIONS_USE_ML_CACHE` (default: `true`)
- `RECOMMENDATIONS_CACHE_MAX_AGE_SECONDS` (default: `86400`)
- `RECOMMENDATIONS_REALTIME_REFRESH_ENABLED` (default: `false`)
- `RECOMMENDATIONS_REALTIME_REFRESH_MIN_INTERVAL_SECONDS` (default: `300`)
- `RECOMMENDATIONS_REALTIME_REFRESH_TOP_N` (default: `50`)

### Online learning (implicit interests)

- `RECOMMENDATIONS_ONLINE_LEARNING_ENABLED` (default: `false`)
- `RECOMMENDATIONS_ONLINE_LEARNING_DWELL_THRESHOLD_SECONDS` (default: `10`)
- `RECOMMENDATIONS_ONLINE_LEARNING_DECAY_HALF_LIFE_HOURS` (default: `72`)
- `RECOMMENDATIONS_ONLINE_LEARNING_MAX_SCORE` (default: `10.0`)

### Task queue (worker)

- `TASK_QUEUE_ENABLED` (default: `false`)
- `TASK_QUEUE_POLL_INTERVAL_SECONDS` (default: `1.0`)
- `TASK_QUEUE_MAX_ATTEMPTS` (default: `3`)
- `TASK_QUEUE_STALE_AFTER_SECONDS` (default: `300`)

### Guardrails

- `PERSONALIZATION_GUARDRAILS_ENABLED` (default: `false`)
- `PERSONALIZATION_GUARDRAILS_DAYS` (default: `7`)
- `PERSONALIZATION_GUARDRAILS_MIN_IMPRESSIONS` (default: `200`)
- `PERSONALIZATION_GUARDRAILS_CTR_DROP_RATIO` (default: `0.5`)
- `PERSONALIZATION_GUARDRAILS_CONVERSION_DROP_RATIO` (default: `0.5`)
- `PERSONALIZATION_GUARDRAILS_CLICK_TO_REGISTER_WINDOW_HOURS` (default: `72`)

### Experiment / rollout

- `EXPERIMENTS_PERSONALIZATION_ML_PERCENT` (default: `0`)

## How to run training manually

### Full retrain + cache rewrite

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"

python backend/scripts/recompute_recommendations_ml.py
```

Useful flags:

- `--dry-run` (train + evaluate, no DB writes)
- `--top-n 50`
- `--epochs 6 --lr 0.35 --l2 0.01`

### Per-user refresh using persisted weights

```bash
export DATABASE_URL="postgresql://..."
export SECRET_KEY="any-value"

python backend/scripts/recompute_recommendations_ml.py --user-id 123 --skip-training
```

Note: `--skip-training` loads weights from `recommender_models` (prefers `RECOMMENDER_MODEL_VERSION`, then active model, then latest model).

## Ops checklist (first-time enablement)

1. Apply DB migrations (must include `0013_user_recommendations_cache` and `0014_event_interactions`).
2. Run at least one training run to persist an active model:
   - `python backend/scripts/recompute_recommendations_ml.py`
3. If you want scheduled jobs / realtime refresh / guardrails:
   - run a worker with `TASK_QUEUE_ENABLED=true`
4. Optional features:
   - near-real-time refresh: `RECOMMENDATIONS_REALTIME_REFRESH_ENABLED=true`
   - online learning: `RECOMMENDATIONS_ONLINE_LEARNING_ENABLED=true`
   - guardrails: `PERSONALIZATION_GUARDRAILS_ENABLED=true` + schedule `--guardrails`

## Troubleshooting

### “No recommendations / empty list”

- Check there is an active model:
  - `SELECT model_version, is_active FROM recommender_models ORDER BY id DESC;`
- Check cache freshness:
  - if `RECOMMENDATIONS_CACHE_MAX_AGE_SECONDS` is too low, caches go stale quickly
- Verify there are eligible events (published, future, not full).

### “Realtime refresh doesn’t happen”

- Ensure `TASK_QUEUE_ENABLED=true` and the worker is running.
- Ensure `RECOMMENDATIONS_REALTIME_REFRESH_ENABLED=true`.
- Ensure you’re not throttled by `RECOMMENDATIONS_REALTIME_REFRESH_MIN_INTERVAL_SECONDS`.

### “Trainer fails with feature mismatch”

- The persisted `feature_names` must match the trainer’s `FEATURE_NAMES` exactly.
- After changing features, bump `RECOMMENDER_MODEL_VERSION` and retrain.

## Privacy notes

The recommender relies on `event_interactions` telemetry which may include:

- user and event identifiers
- timestamps
- optional metadata (`meta`) such as impression position, dwell seconds, and search/filter parameters

If you need stricter privacy controls, consider:

- `ANALYTICS_ENABLED=false` (disables collection and reduces ML quality)
- implementing retention cleanup for `event_interactions` (e.g., keep last N days)
- limiting what is stored in `meta` (avoid sensitive data)
