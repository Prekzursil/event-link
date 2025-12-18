# ML recommendations (v1)

This project supports an **offline-trained** (batch) ML recommender that writes a per-user cached ranking to the DB.
At request time, `GET /api/recommendations` prefers this cache (if present + fresh) and falls back to the existing
heuristic recommender when needed.

## Data used (today)

The trainer uses only data already stored in the DB:

- User interest tags (`user_interest_tags`)
- Event tags (`event_tags`)
- Registrations (and `attended`) + favorites
- Event attributes: `category`, `city`, `owner_id`, `start_time`
- Popularity proxy: number of registrations per event

## Storage

Recommendations are stored in `user_recommendations`:

- `user_id`, `event_id`, `score`, `rank`
- `model_version`, `generated_at`, `reason`

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

## Runtime behavior

`GET /api/recommendations`:

- uses cached rows when `recommendations_use_ml_cache=true` and the cache age is within
  `recommendations_cache_max_age_seconds`
- falls back to the existing tag/popularity heuristic otherwise

## Next steps (recommended)

- Add scheduled retraining (cron/K8s CronJob) and/or a background job type.
- Track more interactions (event views/clicks/search/filter usage) for richer supervision.
- Add online A/B testing + monitoring (CTR, registration conversion).
- Upgrade to embeddings / matrix factorization when dataset grows.

