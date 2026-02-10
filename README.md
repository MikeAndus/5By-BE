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

## Health checks

```bash
curl -s http://localhost:8000/health | jq
curl -s "http://localhost:8000/health?db=1" | jq
```
