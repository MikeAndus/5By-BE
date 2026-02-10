# Five-By Backend

Stateless FastAPI backend scaffold for the Five-By project. This node provides core primitives only: app bootstrapping, async DB session wiring, Alembic setup, structured logging, request correlation IDs, CORS, and a health endpoint.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# set DATABASE_URL (local Postgres)
export DATABASE_URL="postgres://postgres:postgres@localhost:5432/fiveby"
export CORS_ALLOW_ORIGINS="http://localhost:5173"

uvicorn app.main:app --reload --port 8000
```

## Run migrations (scaffold verification)

```bash
alembic upgrade head
```

## Seed immutable grids

Grid data is checked in at `app/data/grids.json` and loaded only via CLI.

```bash
# validate and seed all grids (idempotent)
python -m app.cli.seed_grids --data app/data/grids.json

# validate only (no writes)
python -m app.cli.seed_grids --dry-run

# seed first 25 valid records
python -m app.cli.seed_grids --limit 25

# continue seeding valid rows even if invalid rows exist (still exits non-zero)
python -m app.cli.seed_grids --continue-on-error
```

Seeder summary logs include:
- `total_records`
- `valid_count`
- `invalid_count`
- `inserted_count`
- `skipped_count`
- `dry_run`
- `limit`

## Health checks

```bash
curl -s http://localhost:8000/health | jq
curl -s "http://localhost:8000/health?db=1" | jq
```
