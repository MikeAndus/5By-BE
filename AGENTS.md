# AGENTS.md — Andus Labs Development Standards

## Python / FastAPI Backend

### Framework
- Python 3.12, FastAPI, Uvicorn
- SQLAlchemy 2.x with async sessions (`async_session`)
- Alembic for migrations
- Pydantic v2 for request/response schemas

### API Conventions
- All responses use `{data, error}` envelope
- Error responses: `{"error": "short_code", "detail": "Human-readable explanation"}`
- HTTP status codes: 200 success, 201 created, 202 accepted (async), 400 bad request, 404 not found, 500 server error
- UUID v4 for all primary keys, server-generated
- All datetime fields are UTC, ISO 8601 format with timezone (`timestamptz`)
- Pagination: `?limit=N&offset=N` with `{data: [...], total: int}` response

### SQLAlchemy Rules
- All database operations use async sessions — never synchronous
- No ORM lazy loading — all relationships must be explicitly loaded with `selectinload()` or `joinedload()`
- No inline SQL strings — use SQLAlchemy query builder or `text()` for raw SQL
- After writes to the DB, query fresh with `select()` — do not trust relationship caches
- Use `server_default` for columns that need defaults at the DB level (not just Python `default`)

### Alembic Migrations
- Auto-generate with `alembic revision --autogenerate -m "description"`
- Always review generated migration before committing
- Use `op.add_column` / `op.drop_column` — never raw SQL for schema changes
- Include `server_default` on new non-nullable columns added to existing tables

### Error Handling
- Use FastAPI exception handlers, not bare try/except in route functions
- Log exceptions with structured JSON logging (`structlog` or `logging` with JSON formatter)
- Never expose stack traces in API responses

### File Organisation
```
app/
  main.py              — FastAPI app, middleware, startup
  config.py            — Settings via pydantic-settings
  models/              — SQLAlchemy models (one file per domain)
  schemas/             — Pydantic request/response models
  routers/             — Route handlers (one file per domain)
  services/            — Business logic (one file per domain)
  dependencies.py      — FastAPI dependency injection (DB sessions, auth)
```

### Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Router prefixes: `/api/{resource}` (plural)
- Model class names: singular (`Session`, not `Sessions`)
- Table names: plural (`sessions`, not `session`)

---

## Database / PostgreSQL

- PostgreSQL 15+ hosted on Render
- UUID v4 primary keys on all tables (`gen_random_uuid()` default)
- `created_at` and `updated_at` timestamps on every table (both `timestamptz`)
- Foreign keys with appropriate `ON DELETE` behavior (CASCADE for children, SET NULL for optional refs)
- Indexes on foreign key columns and any column used in WHERE clauses
- Use `TEXT` over `VARCHAR` unless there's a specific length constraint

---

## Git & Version Control

- Conventional commit messages: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`
- Do not run linters, formatters, or dev tools (ruff, black) — the CI pipeline handles these
- Do not run test suites — the build system handles test execution separately
- Commit all changes before any branch operations
- Never force-push

---

## Environment Variables

- All secrets and configuration via environment variables
- Never hardcode API keys, database URLs, or credentials
- Use `.env` files for local development (never committed)
- Variable naming: `UPPER_SNAKE_CASE`
- Database: `DATABASE_URL`
- API keys: `{SERVICE}_API_KEY` (e.g. `OPENAI_API_KEY`, `CLERK_API_KEY`)

---

## Auth (Clerk)

- Clerk for authentication when auth is required
- JWT verification on backend via Clerk SDK
- API auth: Bearer token in Authorization header, verified server-side

---

## Forbidden Patterns

- No synchronous database operations in Python
- No ORM lazy loading
- No inline SQL strings
- Do not execute linters, formatters, or test runners (ruff, black, pytest)

---

## Build Manifest

When instructed to update `build-manifest.json`, add or update only your node's entry under the `"nodes"` key. Do not modify or remove entries for other nodes. Include:
- `title`: what this node built
- `completed_at`: ISO timestamp
- `contracts`: any API contracts or interfaces created (with full schemas)
- `schemas`: any database schemas created (with full DDL or model definitions)
- `files_created`: list of all files created or modified
- `decisions`: any implementation decisions that downstream work depends on
- `environment_variables`: any new env vars required
