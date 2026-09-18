# FlowForge

Intelligent business process automation platform. A user submits a business request (IT, HR, Finance, etc.); FlowForge classifies it with AI, validates that classification with deterministic business rules, routes it to the right team, and keeps a full audit trail.

This repository is being built in phases — see [`FLOWFORGE_SPEC.md`](FLOWFORGE_SPEC.md) for the full plan and [`docs/learning/`](docs/learning) for phase-by-phase explanations of how and why it's built this way.

**Status: Phase 5 — Business Automation** (deterministic rule engine, routing, task creation, seed data).

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

Optionally seed demo data (users, workflow rules, sample requests spanning every processing outcome):

```bash
docker compose exec backend python -m app.seed
```

Seeded logins (password `password123`): `admin@flowforge.dev` (ADMIN), `operator@flowforge.dev` (OPERATOR), `user@flowforge.dev` (USER).

## Local development without Docker

**Backend**

```bash
cd backend
python -m venv .venv
./.venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env       # point DATABASE_URL at a local Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

In a separate terminal, run the Celery worker (requires a local Redis instance — set `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` in `.env` accordingly):

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

Run tests:

```bash
cd backend
pytest -v
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

## Project structure

```
flowforge/
├── backend/          FastAPI application (Python)
│   ├── app/
│   │   ├── ai/        LLM provider abstraction (mock/Ollama/OpenAI-compatible)
│   │   ├── api/       route handlers + shared dependencies
│   │   ├── core/      config, database session, security (JWT/hashing)
│   │   ├── models/    SQLAlchemy ORM models
│   │   ├── schemas/   Pydantic request/response schemas
│   │   ├── services/  business logic, including the async processing pipeline
│   │   ├── workers/   Celery app + tasks (background request processing)
│   │   └── rules/     deterministic rule engine (condition/action parsing, evaluation)
│   ├── alembic/       database migrations
│   └── tests/         pytest suite
├── frontend/          Next.js application (TypeScript)
│   └── src/
│       ├── app/        routes (App Router)
│       ├── components/ reusable UI components
│       ├── lib/         API client, utilities
│       └── types/       shared TypeScript types
├── infrastructure/aws/ AWS deployment config (added in Phase 8)
├── docs/learning/       phase-by-phase learning documents
└── docker-compose.yml
```

## Documentation

- [`FLOWFORGE_SPEC.md`](FLOWFORGE_SPEC.md) — what is being built
- [`TEACHING_GUIDE.md`](TEACHING_GUIDE.md) — how it's being taught
- [`docs/learning/PHASE_1_FOUNDATIONS.md`](docs/learning/PHASE_1_FOUNDATIONS.md) — Phase 1 deep dive
- [`docs/learning/PHASE_2_BACKEND_DATABASE.md`](docs/learning/PHASE_2_BACKEND_DATABASE.md) — Phase 2 deep dive
- [`docs/learning/PHASE_3_ASYNC_PROCESSING.md`](docs/learning/PHASE_3_ASYNC_PROCESSING.md) — Phase 3 deep dive
- [`docs/learning/PHASE_4_AI_PIPELINE.md`](docs/learning/PHASE_4_AI_PIPELINE.md) — Phase 4 deep dive
- [`docs/learning/PHASE_5_BUSINESS_AUTOMATION.md`](docs/learning/PHASE_5_BUSINESS_AUTOMATION.md) — Phase 5 deep dive
