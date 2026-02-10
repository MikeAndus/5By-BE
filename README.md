# five-by-backend

## Requirements

- Python 3.11+

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Set environment variables in `.env` as needed:

- `DATABASE_URL` is required for database connectivity checks.
- `OPENAI_API_KEY` is optional in this phase.
- `CORS_ALLOWED_ORIGINS` is a comma-separated allowlist.

## Run Server

Local:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Render-compatible:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Run Migrations

```bash
alembic upgrade head
```

## Healthcheck

```bash
curl http://localhost:8000/health
```

Success response (`200`):

```json
{
  "status": "ok",
  "service": "five-by-backend",
  "db": {
    "status": "ok"
  }
}
```

Database unavailable response (`503`):

```json
{
  "error": {
    "code": "db_unavailable",
    "message": "Database is not reachable"
  }
}
```

Unexpected server error (`500`):

```json
{
  "error": {
    "code": "internal_error",
    "message": "Unexpected server error"
  }
}
```
