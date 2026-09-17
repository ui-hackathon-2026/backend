# Backend (FastAPI)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health
- DB health: http://localhost:8000/api/v1/db-health

## Auth

Simple username + password accounts, no roles yet.

```bash
curl -X POST localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "rina", "password": "secret123"}'

curl -X POST localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "rina", "password": "secret123"}'

curl localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <access_token>"
```

Rules: username unique (3-50 chars), password min 6 chars, Argon2
hashing, JWT Bearer valid 7 days. Protect any route with
`CurrentUserDep` from `app.api.deps`.

## Layout

```
app/
  main.py          # app factory, lifespan, middleware, exception handlers
  core/            # config, database engine/session, domain exceptions
  api/deps.py      # shared dependencies (SessionDep)
  api/v1/          # HTTP routes only, one module per resource
  schemas/         # Pydantic request/response models
  services/        # business logic, raises domain exceptions (no HTTP here)
  models/          # SQLAlchemy ORM models (import them in __init__ for Alembic)
```

Rules: routes → services → models. Services never import FastAPI;
routes never touch the engine directly; driver errors never leak to
clients (logged server-side, mapped to 503 `database unavailable`).

## Database

Set `DATABASE_URL` in `.env` (see `.env.example`). Plain `postgresql://`
scheme works too, it is normalized to the psycopg driver automatically.

Migrations (URL comes from `.env`, not `alembic.ini`):

```bash
alembic revision --autogenerate -m "add xyz"
alembic upgrade head
```

## Test

```bash
pytest
```
