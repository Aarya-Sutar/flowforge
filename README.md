# FlowForge

Intelligent business process automation platform. A user submits a business request (IT, HR, Finance, etc.); FlowForge classifies it with AI, validates that classification with deterministic business rules, routes it to the right team, and keeps a full audit trail.

This repository is being built in phases — see [`FLOWFORGE_SPEC.md`](FLOWFORGE_SPEC.md) for the full plan and [`docs/learning/`](docs/learning) for phase-by-phase explanations of how and why it's built this way.

**Status: Phase 2 — Backend + Database Engineering** (relational schema, SQLAlchemy relationships, Alembic migrations, service layer, request CRUD with pagination/filtering/sorting, role-based authorization).

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

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
│   │   ├── api/       route handlers + shared dependencies
│   │   ├── core/      config, database session, security (JWT/hashing)
│   │   ├── models/    SQLAlchemy ORM models
│   │   ├── schemas/   Pydantic request/response schemas
│   │   ├── services/  business logic (added from Phase 2 onward)
│   │   ├── workers/   Celery tasks (added in Phase 3)
│   │   └── rules/     deterministic rule engine (added in Phase 5)
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
