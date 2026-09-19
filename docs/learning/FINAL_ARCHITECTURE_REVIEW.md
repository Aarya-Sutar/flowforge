# Final Architecture Review — FlowForge, Whiteboard Style

## 0. How to Use This Document

This isn't a new explanation of the system — Phases 1 through 10 already did that, in depth, with live evidence. This document is **rehearsal**: the three architecture flows the spec asks for, narrated the way you'd actually narrate them standing at a whiteboard in an interview, with the "why" surfaced at every arrow, because "why not X" is what a real interviewer asks after you draw the boxes. Read it once, then close it and redraw the diagrams from memory — that's the actual test.

Three flows, because FlowForge genuinely has three different concerns pulling in three different directions: **serving a user's request fast** (flow 1), **doing slow, uncertain, possibly-wrong work safely in the background** (flow 2), and **shipping code changes without a human manually touching production** (flow 3). A good whiteboard answer keeps these visibly separate rather than drawing one giant box.

---

## 1. Flow One — The Synchronous Request Path

```
Frontend → Authentication → FastAPI → Service Layer → PostgreSQL
```

**Narration:**

"A browser never talks to the database, and it never talks to Celery or Redis directly — it talks to exactly one thing, the FastAPI backend, over HTTP. That's the first decision worth defending: a single, well-defined API surface, not a frontend that reaches into infrastructure directly.

Every request except login/register carries a JWT in the `Authorization` header. That token is checked in exactly one place — `get_current_user()` in `backend/app/api/deps.py` — decoding it with `decode_access_token()` (`backend/app/core/security.py`) and loading the real `User` row. I say 'exactly one place' deliberately: the frontend also has a route guard (`RequireAuth`, `frontend/src/components/auth/RequireAuth.tsx`), but that's UX only — hide a link a user shouldn't click — not security. If you deleted the frontend entirely and hit the API with `curl`, the real boundary would still hold, because it lives in `deps.py`, not in React.

Past auth, the route handler (e.g. `create_request()` in `backend/app/api/routes/requests.py`) does the minimum work needed to answer the HTTP request, then delegates to a service function — `request_service.create_request()` — which is where the actual SQLAlchemy write happens against PostgreSQL. Routes stay thin on purpose: HTTP concerns (status codes, request/response schemas) live in `routes/`, business logic lives in `services/`. That split is why `dashboard_service.get_summary()` can be unit-tested with a plain SQLite session and no HTTP layer involved at all.

The request returns to the browser here — fast, synchronous, done. Nothing about AI classification has happened yet. That boundary is flow one's whole point: it's short, predictable, and never blocks on something slow or uncertain."

**Why this shape, if asked:**
- *Why not call the AI provider inline, in the request handler?* Because AI latency is 1-30+ seconds and unpredictable (timeouts, retries) — a synchronous HTTP request holding that long is a bad user experience and a resource-exhaustion risk under load. This is the entire reason flow two exists as a separate path.
- *Why JWT, not server-side sessions?* Stateless — no session store to keep in sync across horizontally-scaled backend replicas (relevant the moment ECS runs more than one task, Phase 8). Trade-off acknowledged elsewhere in the docs: revocation before expiry isn't built, a real gap, not hidden.
- *Why a service layer instead of business logic directly in routes?* Testability (Phase 1-2) and reuse — `request_service` functions are called from routes and, indirectly, are the same functions covered by unit tests that never spin up FastAPI at all.

---

## 2. Flow Two — The Asynchronous Processing Path

```
FastAPI → Redis → Celery Worker → AI Provider → Rule Engine → Workflow → PostgreSQL → Audit Trail
```

**Narration:**

"This is what happens *after* flow one already returned `201` to the browser. `_enqueue_processing()` (`backend/app/api/routes/requests.py`) calls `process_request.apply_async(...)` — that's a message published to Redis, acting purely as a message broker here, not a database. FastAPI's job in this diagram ends the moment that message is published.

A separate OS process — the Celery worker, running `backend/app/workers/celery_app.py`, a different container in Docker Compose and a different ECS service in Terraform — picks the message up independently. First thing it does: `pipeline_lock()` (`backend/app/services/locking.py`), a Redis `SETNX`-based lock keyed on the request ID, so a retried or duplicated message can't process the same request twice concurrently. Deliberately fail-open: if Redis itself is unreachable, the lock is skipped rather than blocking processing entirely — a documented trade-off, not an oversight.

Inside the lock: `_run_pipeline_locked()` (`backend/app/services/processing_service.py`) runs three stages. NORMALIZE cleans the text. CLASSIFY calls the AI provider — `mock`, `ollama`, or an OpenAI-compatible endpoint, all behind one `AIProvider` interface (`backend/app/ai/base.py`) — and validates the response against a strict Pydantic schema (`backend/app/ai/schemas.py`) before trusting a single field of it. That validation step is the hallucination defense: if the model returns a category that isn't a real enum value, or a confidence outside 0-1, it's rejected right there, not silently accepted.

Here's the sentence that answers the interview follow-up before it's asked: **the AI never makes the final decision.** Its output is one input to ROUTE, where `evaluate_rules()` (`backend/app/rules/engine.py`) runs deterministic, database-stored, admin-editable rules against it — things like 'confidence below 0.70 → manual review' or 'category=Finance and amount>10000 → assign to finance-approval team.' The rule engine decides the workflow outcome; the AI just supplies data the rules can act on. That's a deliberate governance boundary — you can audit and change what triggers manual review without touching a model or retraining anything.

Every stage writes to PostgreSQL — a `WorkflowTask` gets created if a team is assigned — and every stage also writes to `audit_logs` via `audit_service.record_event()`, in the same transaction as the change itself. That log is the shared source of truth I use to answer 'what actually happened to this request' — not scattered container logs, not guesswork."

**Why this shape, if asked:**
- *Why Redis and not, say, calling the worker function directly in a background thread?* Durability and horizontal scaling — a message sitting in Redis survives a backend restart; an in-process background thread doesn't, and doesn't scale past one machine either.
- *Why is the AI advisory instead of authoritative?* Two reasons stated directly in Phase 4/5 docs: models can be wrong/inconsistent, and a business needs an auditable, changeable policy layer that doesn't require a retrain to adjust — a rule is one row in a database table an admin can edit through `/rules`.
- *Why record audit events in the same transaction as the state change, rather than fire-and-forget logging afterward?* If the transaction rolls back, the audit event rolls back with it — the log never claims something happened that didn't actually commit.
- *What happens if the AI call fails outright, or Postgres is down mid-pipeline?* That's Phase 10's Scenario C and Scenario D exactly — `docs/learning/PHASE_10_SYSTEM_INTEGRATION.md` — retry-then-manual-review for the AI case (explicit, because a judgment call is needed), `autoretry_for=(OperationalError,)` for the database case (automatic, because there's no judgment call, just "try again").

---

## 3. Flow Three — The Deployment Pipeline

```
GitHub → GitHub Actions → Docker → ECR → ECS/Fargate → RDS / ElastiCache / CloudWatch
```

**Narration:**

"A push to `main` triggers `ci.yml`: backend lint+unit tests, frontend typecheck+lint+build, and a real integration job that builds the full Docker Compose stack — actual Postgres, actual Redis, an actual Celery worker — and runs pytest against it. That integration job is the same 'Docker Build' step the deployment pipeline needs anyway, so it's not duplicated later.

`deploy.yml` is triggered by `workflow_run` — specifically watching for `ci.yml` to complete on `main` — rather than re-running the tests itself. That's the actual enforcement of 'tests must pass before deploy': it's structural, not a comment saying so. The job itself is gated a second way, `if: vars.AWS_DEPLOY_ENABLED == 'true'` — a repository variable that's currently unset, so the job shows as cleanly *skipped*, not failed, because there's genuinely no AWS account connected to deploy to.

If it were enabled: OIDC federated auth (`aws_iam_openid_connect_provider`, Terraform, Phase 9) gets short-lived AWS credentials with no long-lived secret stored in GitHub at all — scoped, via a `StringLike` condition, specifically to `repo:Aarya-Sutar/flowforge:ref:refs/heads/main`, so a PR from a fork can't assume that role. Images get built and pushed to ECR, then three ECS services (`flowforge-backend`, `flowforge-celery-worker`, `flowforge-frontend`) get `--force-new-deployment`, and the workflow waits for ECS to report the services stable before declaring success.

On the infrastructure side (Terraform, Phase 8, never applied): a VPC with public and private subnets, but deliberately **no NAT Gateway** — the real security enforcement is security groups chained to each other by reference (`ecs_tasks` SG, `rds` SG, `redis` SG), not subnet placement or IP ranges, and skipping the NAT Gateway saves a real, non-trivial monthly cost for infrastructure that isn't even running yet. IAM has a hard split between the ECS *execution* role (pull images, write logs — what AWS needs) and the *task* role (what the running application code itself is allowed to do — currently zero attached policies, because the application doesn't call any AWS APIs at runtime yet). Least privilege isn't a slogan here, it's a specific, checkable fact about that role."

**Why this shape, if asked:**
- *Why `workflow_run` instead of just adding deploy steps to `ci.yml` directly?* Keeps 'verify' and 'ship' as separately-triggerable, separately-auditable stages — and lets the deploy job apply its own additional gate (`AWS_DEPLOY_ENABLED`) without complicating the CI workflow every contributor's PR runs.
- *Why OIDC instead of a long-lived `AWS_ACCESS_KEY_ID` secret?* A stolen long-lived key works until manually rotated; an OIDC-issued credential expires in under an hour and is scoped to one repo/branch by policy, not by convention.
- *Why no NAT Gateway if the ECS tasks are in private subnets?* Because outbound internet access isn't actually required for this specific workload (it talks to RDS/ElastiCache/ALB inside the VPC, and pulls images via ECR VPC endpoints or the public ECR path at startup only) — paying for a NAT Gateway here would be cost without a corresponding security benefit; the subnets are private for blast-radius reasons, not because outbound access was needed.
- *Is any of this actually running?* No — stated plainly, every time it comes up. Terraform is written and internally consistent; `terraform plan` was never run against a real AWS account. That's an honest scope limit, not a hidden gap.

---

## 4. What Connects All Three Flows

- **The audit trail is the only place all three flows leave a permanent, structured trace of a single request's life** — flow one's creation, flow two's every processing stage, and (indirectly) flow three's deployments changing which code version processed it.
- **Every flow has a synchronous/fast part and a slow/uncertain part, and the architecture never lets the slow part block the fast part** — flow one returns before AI runs; flow three's CI gate runs in parallel with nothing waiting on it inside a user request; flow two's worker is a wholly separate process from the API that enqueued it.
- **Authorization is centralized, not duplicated** — one `require_roles()` dependency (`backend/app/api/deps.py`), used everywhere staff-only behavior is needed, rather than an `if user.role == "ADMIN"` scattered per-route.
- **Nothing in this system is trusted just because it's internal** — the AI's output is schema-validated before use; a database `OperationalError` mid-pipeline doesn't get silently swallowed; a `USER` role is still authenticated but not authorized for staff routes. The pattern repeating across all three flows is: verify before trusting, every layer, not just at the edge.

---

## 5. The Short Versions

**30-second elevator pitch:** "FlowForge takes a business request, answers the user immediately, and classifies it with AI in the background — but a deterministic, admin-editable rule engine decides the actual outcome, not the AI. Every step is written to an audit log in the same transaction as the change, so the whole thing is traceable end to end. It ships through a CI pipeline that actually builds and tests the real Docker stack before anything is allowed to deploy."

**Five-minute whiteboard version:** draw the three diagrams above, left to right, in order — sync path, async path, deploy path — narrating each arrow as "what happens" then "why it's built this way, not some simpler way." That's the shape of a real system-design answer: not just the boxes, but a defensible reason for every arrow between them.

---

## 6. Checklist

- [x] All three spec-required flows diagrammed and narrated
- [x] Every arrow ties to a real file/function already confirmed accurate in Phase 10
- [x] Common "why not X" follow-ups answered directly, not dodged
- [x] Honest about what's unverified (AWS deployment) and what's a real trade-off (Redis fail-open, JWT non-revocation, no NAT Gateway)

Next: redraw all three diagrams from memory, out loud, then we'll do the codebase deep-dive.
