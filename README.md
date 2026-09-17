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

## Simulator

`POST /api/v1/simulate/stability` validates formula weights (must sum
100%, else 400), runs the predictor, and persists the run.
`GET /api/v1/simulate/stability/{run_id}` returns the stored result.

The default predictor runs the vendored LightGBM training artifacts
(`app/ml/artifacts`, 7 targets: stability, phase separation,
feasibility, viscosity, droplet size, PDI, pH) and reports
`engine_used: LIGHTGBM_GPU`. When artifacts are missing or inference
fails, it falls back to a deterministic stub clearly marked
(`engine_used: STUB_DETERMINISTIC`, `is_stub: true`). Swap engines by
passing any `Predictor` implementation to `run_simulation`. Ingredients
unknown to the `ingredients` catalog flip the OOD flag.

## Formulas

`POST /api/v1/formulas` accepts 4-phase ingredient groups
(`phase_a` oil, `phase_b` water, `phase_c` emulsifier, `phase_d`
heat-sensitive actives), validates the 100% mass balance, and returns
`VALID_BALANCED`. Full CRUD plus append-only version snapshots on every
update (`GET /api/v1/formulas/{id}/versions`).

## Compliance

`POST /api/v1/compliance/audit` runs the hybrid Tier 1 deterministic
guard (BPOM limits, halal, TKDN) grounded by keyword retrieval over the
`knowledge_chunks` table with INCI synonym resolution, then Tier 3 LLM
reasoning for toxicology narrative and label warnings with a
deterministic fallback when the engine is down. `POST
/api/v1/compliance/ask-rag` answers regulatory questions with citations
from the same chunks.

## Projects & Briefs

`POST /api/v1/projects` opens a loose workspace in `new` mode (prompt
text) or `enhance` mode (reference formula + instruction, ref required).
`POST /api/v1/uploads/brief` ingests a marketing PDF (max 10 MB) and
returns extracted text with a preview. Order of use is never enforced.

## Copilot

`POST /api/v1/copilot/chat` accepts a message plus optional session,
project, canvas snapshot, and brief reference. It streams
`text/event-stream` events: session meta, per-agent progress steps
(architect, auditor, sentinel, synthesizer), reply tokens, and a final
result carrying the parsed formulation spec. Sessions and messages
persist for multi-turn context. LLM outage yields an error event,
never a dropped connection.

## Optimize, Batch, Similarity

`POST /api/v1/optimize/pareto` runs greedy random search over the mass
simplex honoring locked ingredients, scores every trial in one
vectorized surrogate batch, and returns Top-3 plus 3D scatter points.
`POST /api/v1/batch-sheet/generate` converts a formula to exact gram
weights with SOP steps. `POST /api/v1/similarity/check` compares
Jaccard, cosine, and phase-chassis overlap against stored formulas.
`GET /api/v1/suppliers` reads the supplier catalog. Patent FTO and 3D
conformers honestly answer 503 until their engines connect.

## Workbench

`GET /api/v1/workbench/ingredients` reads the lab catalog with
`phase`/`role`/`q`/`halal_only` filters. `POST
/api/v1/workbench/calculate-moments` computes HLB, SOR, phase totals,
COGS, TKDN, radar metrics, and warnings purely from request numbers.
`POST /api/v1/workbench/formulas` saves a flat-ingredient draft into
the canonical formula storage. Weights must sum 100% ± 1%.

## Orchestrator

`POST /api/v1/orchestrator/synthesize` turns target params into a
4-phase blueprint reusing the optimizer, catalog phases, and LLM
rationale. `POST /api/v1/orchestrator/parse-brief-pdf` extracts
structured brief data from a marketing PDF. `GET
/api/v1/orchestrator/chassis` serves curated brand templates,
`GET /api/v1/orchestrator/hero-ingredients` lists TKDN botanicals.

## Test

```bash
pytest
```
