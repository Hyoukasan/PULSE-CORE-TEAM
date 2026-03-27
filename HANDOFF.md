# Pulse Core Handoff

## What Was Done Today

- Removed dangerous auto-reset behavior from app startup.
  - `create_app()` no longer executes `drop_all/create_all`.
- Added safe DB CLI commands in `app/main/__init__.py`:
  - `db-init`, `db-drop` (confirm), `db-reset` (confirm)
  - `seed-roles`, `db-smoke`, `seed-demo-data`
- Aligned ORM models with ERD:
  - Fixed `Professor.group_is -> group_id`
  - Added one-to-one relations in `User`: `student_profile`, `professor_profile`
  - Fixed `Student` / `Professor` reverse relations to `Group`
- Added core business layer:
  - `app/src/core/validators.py`
  - `app/src/core/schemas.py`
  - `app/src/core/services.py`
- Added API v1 blueprint and endpoints:
  - `GET /api/v1/health`
  - `POST /api/v1/users/register`
  - `POST /api/v1/groups/assign`
  - `POST /api/v1/groups/sync`
- Added minimal security for sheet sync:
  - `POST /api/v1/groups/sync` requires header `X-API-Key`
  - key is loaded from `SHEETS_SYNC_API_KEY` in config/env

## Required Environment Variables

- `SECRET_KEY`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `SHEETS_SYNC_API_KEY` (required for `/api/v1/groups/sync`)

Optional:
- `DATABASE_URL` (if omitted, uses local SQLite file in `instance/pulse_project.db`)

## Quick Start (Local)

1. Activate venv
2. Initialize DB:
   - `flask --app pulse_project db-init`
3. Seed roles:
   - `flask --app pulse_project seed-roles`
4. Add demo records:
   - `flask --app pulse_project seed-demo-data`

Optional check:
- `flask --app pulse_project db-smoke`

## API Examples

Register user:

```json
POST /api/v1/users/register
{
  "username": "alex",
  "email": "alex@test.local",
  "password": "strongpass123",
  "role": "student"
}
```

Assign user to group:

```json
POST /api/v1/groups/assign
{
  "user_id": 1,
  "group_number": "DEMO-1"
}
```

Sync groups from table/webhook:

```json
POST /api/v1/groups/sync
X-API-Key: <SHEETS_SYNC_API_KEY>
{
  "rows": [
    { "number": "A-101", "name": "A101" },
    { "number": "B-202", "name": "B202" }
  ]
}
```

## Known Gaps (Next Person)

- API routes are currently in `app/api/v1/auth/auth.py` (file name is legacy; can be renamed).
- No full migration flow yet (`flask db migrate/upgrade` still to be wired for team flow).
- No automated tests yet for core services.
- `.env` currently contains real-like secrets and should not be committed.
