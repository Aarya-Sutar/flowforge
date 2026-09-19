# FlowForge

Intelligent business process automation platform. A user submits a business request (IT, HR, Finance, etc.); FlowForge classifies it with AI, validates that classification with deterministic business rules, routes it to the right team, and keeps a full audit trail.

This repository is being built in phases — see [`FLOWFORGE_SPEC.md`](FLOWFORGE_SPEC.md) for the full plan and [`docs/learning/`](docs/learning) for phase-by-phase explanations of how and why it's built this way.

**Status: Phase 9 — CI/CD and Engineering Workflow** (GitHub Actions: CI runs on every push/PR; deploy is wired for real via OIDC but gated off, since no AWS account is connected).

[![CI](https://github.com/Aarya-Sutar/flowforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Aarya-Sutar/flowforge/actions/workflows/ci.yml)

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

Run tests (fast unit suite — no external services needed; integration tests under `tests/integration/` auto-skip if the Docker Compose stack isn't reachable and run automatically if it is):

```bash
cd backend
pytest -v
```

To explicitly run the integration suite against a live stack:

```bash
docker compose up -d
docker compose exec backend python -m app.seed   # needed for admin-only integration tests
cd backend
pytest tests/integration -v
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
│   │   ├── core/      config, database session, security (JWT/hashing), structured
│   │   │              logging, request-ID middleware, rate limiting, Redis client
│   │   ├── models/    SQLAlchemy ORM models
│   │   ├── schemas/   Pydantic request/response schemas
│   │   ├── services/  business logic, async processing pipeline, distributed lock
│   │   ├── workers/   Celery app + tasks (background request processing)
│   │   └── rules/     deterministic rule engine (condition/action parsing, evaluation)
│   ├── alembic/       database migrations
│   └── tests/         pytest suite (tests/integration/ requires a live Docker Compose stack)
├── frontend/          Next.js application (TypeScript)
│   └── src/
│       ├── app/        routes: login, register, dashboard, requests, tasks, rules, settings
│       ├── components/ auth guard, layout, dashboard charts, request detail, ui primitives
│       ├── contexts/    AuthContext (JWT session state)
│       ├── lib/         API client, per-resource service modules, error handling
│       └── types/       shared TypeScript types matching the backend schemas
├── infrastructure/aws/ Terraform for ECS/Fargate + RDS + ElastiCache (validated, not deployed — see Phase 8 docs)
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
- [`docs/learning/PHASE_6_FRONTEND_ENGINEERING.md`](docs/learning/PHASE_6_FRONTEND_ENGINEERING.md) — Phase 6 deep dive
- [`docs/learning/PHASE_7_PRODUCTION_ENGINEERING.md`](docs/learning/PHASE_7_PRODUCTION_ENGINEERING.md) — Phase 7 deep dive
- [`docs/learning/PHASE_8_CLOUD_AWS.md`](docs/learning/PHASE_8_CLOUD_AWS.md) — Phase 8 deep dive (infrastructure code + deployment runbook; not deployed)
- [`docs/learning/PHASE_9_CICD.md`](docs/learning/PHASE_9_CICD.md) — Phase 9 deep dive (includes the real CI run that failed, and the real fix that made it pass)
