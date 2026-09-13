# RecoverAI

**AI Revenue Recovery Agent** — watches Razorpay (test mode) for failed subscription payments, diagnoses why the money is at risk, executes a bounded recovery action, and reports recovered vs. at-risk revenue with a full audit trail.

This is a boilerplate/foundation repository: the architecture, contracts, and connections between every layer are real and working; several individual features (the real Razorpay API calls, LLM classification, checkout-abandonment recovery) are intentionally stubbed for a coding agent (Antigravity) to finish. **Read [AGENTS.md](./AGENTS.md), [ARCHITECTURE.md](./ARCHITECTURE.md), [DATA_FLOW.md](./DATA_FLOW.md), and [PROJECT_STATUS.md](./PROJECT_STATUS.md) before making architectural changes.**

## Architecture summary

```
Razorpay webhook → verify signature → normalize event → deduplicate
  → classify failure (deterministic → LLM fallback) → load/create case
  → check stopping rules → decide next action (pure) → schedule/execute
  → audit everything → dashboard reads current state
```

- **Frontend:** React + Vite + TypeScript + Tailwind CSS + React Router (client-side SPA, no Next.js).
- **Backend:** FastAPI + Python + SQLAlchemy + PostgreSQL (the only backend).
- **Async jobs:** Celery + Redis.
- **Integrations:** Razorpay (test mode), LLM as a fallback classifier only.

Full detail in [ARCHITECTURE.md](./ARCHITECTURE.md).

## Repository structure

```
recoverai/
├── AGENTS.md, ARCHITECTURE.md, DATA_FLOW.md, PROJECT_STATUS.md, README.md
├── .env.example                 # backend env vars (copy to backend/.env)
├── docker-compose.yml           # Postgres + Redis (dev only)
├── backend/
│   ├── app/
│   │   ├── domain/              # enums, NormalizedEvent, Decision contract — source of truth
│   │   ├── models/               # SQLAlchemy models
│   │   ├── schemas/              # Pydantic API request/response contracts
│   │   ├── api/                  # FastAPI routers (thin)
│   │   ├── services/             # business logic — see AGENTS.md for the dependency graph
│   │   ├── integrations/         # razorpay/ (SDK isolated here) + llm/ (fallback classifier)
│   │   ├── workers/               # Celery app + tasks
│   │   └── db/                    # engine/session
│   ├── alembic/                   # migrations
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/                   # centralized fetch layer
    │   ├── types/                 # TS types mirroring backend schemas
    │   ├── pages/                 # Dashboard, Cases, CaseDetail, Simulator
    │   └── components/
    └── package.json
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker (for Postgres + Redis via `docker-compose`) — or your own local Postgres 16 / Redis 7
- A Razorpay test-mode account (for real webhook testing; the simulator works without one)

## Environment setup

```bash
cp .env.example backend/.env          # fill in Razorpay test keys when you have them
cp frontend/.env.example frontend/.env.local
```

## PostgreSQL + Redis setup

```bash
docker compose up -d postgres redis
```

This starts Postgres on `localhost:5432` (db/user/pass: `recoverai`/`recoverai`/`recoverai`) and Redis on `localhost:6379`. Data persists in the `recoverai_postgres_data` Docker volume.

## Backend setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head              # creates all tables
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (`/docs` for interactive OpenAPI docs, `/health` for a liveness check).

## Celery worker startup

In a separate terminal (same venv):

```bash
cd backend
source .venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

The worker must be running for scheduled/executed recovery actions (`retry_now`, `retry_later`, `send_payment_update_link`, `notify_customer`) to actually run — see `PROJECT_STATUS.md` for what happens if it isn't (the attempt is created and audited, but stays `PENDING`).

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The app is now at `http://localhost:5173`, talking to the backend at `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Migrations

```bash
cd backend
alembic upgrade head                        # apply
alembic revision -m "describe your change"  # create a new migration (hand-edit it — see alembic/versions/0001_initial_schema.py as a template)
```

## Testing

```bash
cd backend
pytest                # 30 tests, runs against a throwaway SQLite file — no Postgres/Redis required
```

```bash
cd frontend
npm run build          # tsc -b && vite build — type-checks and builds
```

## Development workflow

1. Bring up Postgres + Redis (`docker compose up -d postgres redis`), run migrations, start the backend, start the Celery worker, start the frontend.
2. Open the frontend, go to **Simulator**, run a batch — this exercises the entire pipeline (webhook_orchestrator → classifier → decision engine → executor → audit) without needing a real Razorpay account.
3. Watch cases populate on the **Dashboard** and **Cases** pages; drill into a case to see its diagnosis, decision, attempt history, and audit trail.
4. Once you have a real Razorpay test-mode account and webhook configured, point it at `POST /api/webhooks/razorpay` (use a tunnel like `ngrok` for local dev) and compare real vs. simulated cases — they're always distinguishable via the `source` field.
5. Before changing architecture, read AGENTS.md's "Rules future agents must follow" — most of the constraints in this codebase (decision engine purity, audit-only-via-audit_service, bounded retries, one enum source of truth) are load-bearing for the PRD's non-functional requirements, not arbitrary style choices.
