# Phase 9 — CI/CD and Engineering Workflow

## 1. What We Built

- `.github/workflows/ci.yml` — install, lint, unit tests, Docker build, and real integration tests, running on every pull request and every push to `main`.
- `.github/workflows/deploy.yml` — build, push to ECR, deploy to ECS, health check — triggered only after CI succeeds on `main`, authenticating to AWS via OIDC (no long-lived AWS keys stored anywhere), and cleanly gated off since this project has no AWS account connected.
- A new IAM OIDC provider + tightly-scoped deploy role (`infrastructure/aws/terraform/github_oidc.tf`), restricted to this exact repository's `main` branch.
- A real backend lint step: `ruff`, configured project-wide, with the genuine issues it found fixed.
- **This was all verified for real, on GitHub's actual infrastructure** — not just written and assumed correct. Full evidence in section 7.

## 2. Why This Phase Exists

Every previous phase was verified by *me, manually, in this session* — running `pytest`, rebuilding Docker, clicking through the browser. That doesn't scale, and more importantly, it depends entirely on the person doing it remembering to do it, correctly, every time, before every merge. CI/CD is what makes "did we check this" stop being a matter of discipline and start being a matter of infrastructure: the checks run themselves, automatically, on every single change, and a failing check physically blocks bad code from reaching `main` (for CI) or production (for CD) — not because someone was careful, but because the pipeline enforces it.

## 3. Prerequisites

Phases 1–8 (the whole application, tested and containerized) are assumed, especially Phase 7's test suite (what CI actually runs) and Phase 8's Terraform (what CD would deploy).

## 4. Core Concepts

### Git branches and pull requests

A **branch** is a named, independent line of development — `main` is just the branch everyone treats as "the current real state of the project." A **pull request (PR)** is a proposal to merge one branch into another, with a diff, a discussion thread, and — this is the part CI plugs into — a place for automated checks to report pass/fail *before* anyone merges. `ci.yml`'s `on: pull_request` trigger means every PR gets the full check suite run against it automatically, visible right on the PR itself.

### CI vs. CD

**Continuous Integration (CI)**: automatically verify every change — does it build, does it pass its tests, is it correctly formatted/linted. `ci.yml` is CI. **Continuous Deployment (CD)**: automatically *ship* a change that passes CI to a real environment. `deploy.yml` is CD. They're deliberately separate files here, connected by one specific mechanism (section on `workflow_run` below) — CI's job is "is this good," CD's job is "make it live," and conflating them would make it harder to reason about which failure means what.

### Build pipeline and artifacts

A **pipeline** is the ordered sequence of automated steps a change goes through — install dependencies → lint → test → build → (for CD) deploy. Each step is a **gate**: if it fails, everything after it is skipped, because there's no point deploying code that didn't even pass its own tests. An **artifact** is something a pipeline step produces that a later step (or a human) needs — here, the built Docker images pushed to ECR are the artifact `deploy.yml` hands off between its "build" and "deploy" steps.

### Secrets, in GitHub Actions specifically

`deploy.yml` never contains an AWS access key. It uses `secrets.AWS_DEPLOY_ROLE_ARN` — a value stored encrypted in the repository's settings, injected into the workflow run at execution time, never visible in logs or in the repository itself. Even more specifically, this project's deploy role uses **OIDC** (section 6) instead of a static key/secret pair at all — the strongest version of "don't commit secrets," extended to "don't even store long-lived ones."

### Deployment gates

A gate is anything that must pass before deployment proceeds. This project has two, stacked: (1) `workflow_run` — `deploy.yml` only triggers after `ci.yml` completes on `main`, and its job condition additionally checks `github.event.workflow_run.conclusion == 'success'`, so a failing CI run cannot trigger a deploy at all; (2) `vars.AWS_DEPLOY_ENABLED` — an explicit, deliberate on/off switch, defaulting to off. Two independent gates, for two independent reasons: the first stops broken code from deploying; the second stops deployment from running at all against an environment that doesn't (yet) exist for this project.

### Rollback

If a bad deploy reaches ECS, `deploy.yml`'s health check step is the detection mechanism — it polls the ALB after deploying and fails the workflow (loudly) if the app never becomes healthy. The actual rollback (documented in Phase 8's runbook) is `terraform apply -var="backend_image=<previous-tag>"` — this only works because Phase 8's ECR repos are configured `IMMUTABLE`: a given image tag can never be silently overwritten, so "the previous tag" always still points at exactly what it did before.

### Why automated tests belong *before* deployment, not after

The alternative — deploy first, find out if it works by watching production — means every mistake is a live incident instead of a red CI check nobody but the author needs to see. `ci.yml` running the exact same test suite (Phase 7's 141 tests) that's been the safety net for every phase since Phase 1 is what makes "deploy" mean "deploy something already known to work," not "deploy something and hope."

## 5. Mental Model

Think of `main` as a claim: "this is the real, working state of the project." CI is the thing that makes that claim actually true, automatically, every time — rather than true only when whoever pushed last remembered to run the tests. CD is the thing that takes that verified-true state and makes it the state of a running system, without a human manually SSHing in or clicking through a console.

## 6. IAM/OIDC for GitHub Actions, in depth

The old pattern: create an IAM user, generate an access key + secret, paste them into GitHub repo secrets. This works, but that key never expires on its own, works from anywhere (not just this specific repo's workflows), and if a workflow log or a compromised dependency ever leaks it, it's a permanent, until-manually-rotated problem.

The pattern used here (`github_oidc.tf`): GitHub's own token service issues a short-lived, cryptographically signed token to every workflow run, asserting facts like "this is repo `Aarya-Sutar/flowforge`, branch `main`, run number N." `aws_iam_openid_connect_provider.github_actions` tells AWS to trust tokens signed by GitHub's OIDC issuer. `data.aws_iam_policy_document.github_actions_assume_role`'s `condition` block is the actual access control: it only trusts tokens whose `sub` claim matches `repo:Aarya-Sutar/flowforge:ref:refs/heads/main` exactly — a workflow run on a fork, or a different branch, gets a validly-signed token that this role simply refuses to trust. No long-lived credential ever exists; `aws-actions/configure-aws-credentials`'s OIDC mode exchanges the short-lived GitHub token for short-lived AWS credentials, scoped to exactly this role's permissions, valid only for the run's duration.

## 7. Live Verification — What Actually Happened

This is the section that matters most for this phase: not what the workflow *should* do, but what it *actually did*, watched directly on GitHub's real infrastructure.

**Run #1** (commit `05a4d72`, the initial push of both workflows):

| Job | Result | Duration |
|---|---|---|
| Backend — install, lint, unit tests | ✅ Passed | 55s |
| Frontend — install, typecheck, lint, build | ❌ **Failed** | 57s |
| Integration tests (real Postgres + Redis + Celery worker) | ✅ Passed | 1m 40s |

**Overall: Failure.** The frontend job failed with a real, genuine error: `error TS2304: Cannot find name 'LayoutProps'`.

**Root cause, investigated and confirmed locally**: `LayoutProps` is a type Next.js *generates* (as a side effect of `next dev`/`next build`/`next typegen`) into a `.next/types/` directory — gitignored, since it's build output, not source. This machine's local `.next/` had been generated by dozens of `npm run build` calls across Phases 6–8, so `npx tsc --noEmit` always had those types available locally. A genuinely fresh checkout — exactly what `actions/checkout` produces — has no `.next/` directory at all, so the standalone type-check step failed on code that had never actually been verified against a truly clean checkout before. Reproduced directly: `rm -rf .next && npx tsc --noEmit` failed identically on this machine; `npx next typegen && npx tsc --noEmit` fixed it.

**Fix applied**: added an explicit `npx next typegen` step before the type-check in `ci.yml`, committed as `49567dc`.

**Run #2** (commit `49567dc`, after the fix):

| Job | Result | Duration |
|---|---|---|
| Backend — install, lint, unit tests | ✅ Passed | 51s |
| Frontend — install, typecheck, lint, build | ✅ Passed | 41s |
| Integration tests (real Postgres + Redis + Celery worker) | ✅ Passed | 1m 38s |

**Overall: Success.** Total run time: 2m 35s.

**The Deploy workflow**, checked after both runs: `Deploy #1` (triggered by the failing CI run) shows **Skipped** — correctly, since its condition requires `conclusion == 'success'`. `Deploy #2` (triggered by the passing CI run) *also* shows **Skipped**, in 7 seconds — correctly, because `vars.AWS_DEPLOY_ENABLED` is unset. Both gates, independently, behaved exactly as designed: neither a failing CI run nor a passing one with no AWS account connected produces a false "deployed" claim or a misleading red failure — both produce an honest, clearly-labeled skip.

**This is the single most important piece of evidence in this entire phase**: the CI/CD pipeline wasn't just written to look correct — it was pushed, it ran on GitHub's real infrastructure, it found a real bug on its very first execution, that bug was fixed based on the real failure (not a hypothetical one), and the fix was verified by a second real run. This is precisely what the spec means by "verify that the workflow actually runs" and "do not create a fake CI/CD configuration."

## 8. Reading GitHub Actions Logs and Diagnosing Failures

The exact process used above, generalized:

1. **Open the failing run** (`Actions` tab → the run → the failing job). GitHub groups output by step; the failing step is auto-expanded.
2. **Read the actual error text first**, not just "it failed" — `Cannot find name 'LayoutProps'` named the exact symbol and, implicitly, the exact file (`tsc`'s own output includes the file/line).
3. **Distinguish real errors from notices/warnings** — this run's log also showed "Node.js 20 is deprecated" and "ubuntu-latest will migrate to Ubuntu 26" annotations on *every* job, including the ones that passed. Those are GitHub infrastructure notices, not failures — the `Process completed with exit code 2` line is what actually indicates a real failure, tied to a specific job.
4. **Reproduce locally before guessing at a fix** — `rm -rf .next && npx tsc --noEmit` reproduced the exact CI failure on this machine in seconds, which is what turned "I think I know what's wrong" into "I've confirmed what's wrong."
5. **Fix, push, and watch the next run** — don't assume a fix worked; the same live-verification discipline this project has used since Phase 3 applies here too.

## 9. Codebase Mapping

| Layer | File | Responsibility |
|---|---|---|
| CI workflow | `.github/workflows/ci.yml` | Lint, unit tests, integration tests, on PR + push to main |
| CD workflow | `.github/workflows/deploy.yml` | Build, push, deploy, health check — gated, main only |
| OIDC + deploy role | `infrastructure/aws/terraform/github_oidc.tf` | AWS trust relationship for the deploy workflow |
| Backend lint config | `backend/ruff.toml` | Rule selection, FastAPI-specific exception documented inline |

## 10. Design Decisions

**Why `workflow_run` instead of just adding deploy steps to `ci.yml` guarded by `if: github.ref == 'refs/heads/main'`?** Two reasons: it keeps CI's purpose (verify) and CD's purpose (ship) in genuinely separate files with separate histories, and it means CD only ever runs after CI has *fully completed and reported a conclusion* — a job-level `if` inside the same workflow can still run in parallel with other jobs that haven't finished yet, which `workflow_run` structurally can't do (it can only fire after the referenced workflow is entirely done).

**Why a repo variable (`vars.AWS_DEPLOY_ENABLED`) instead of just leaving `secrets.AWS_DEPLOY_ROLE_ARN` unset and letting the AWS step fail?** A missing-secret failure shows as a red ❌ on every single push to main, forever, for a condition that's actually completely expected ("this portfolio project has no AWS account") — indistinguishable, at a glance, from an actual regression. An explicit, named gate that shows as a clean gray "skipped" tells the true story: this is correctly configured and intentionally not turned on, not broken.

**Why fix the discovered bug immediately rather than documenting it as a known issue?** Unlike Phase 7's Redis-outage investigation (a deep, multi-attempt architectural question with no clean answer found), this had an identified, verifiable, one-line root cause and a confirmed fix within minutes — there was no reason to leave a fixable, understood bug in place just to have something to write about. The honest documentation here is showing the real failure and real fix, not manufacturing an artificial "known limitation."

## 11. Trade-offs

- **No branch protection rules configured** (requiring CI to pass before a PR can merge) — this would need repository admin settings changes, which weren't made in this session; the workflows exist and gate correctly at the check level, but nothing currently *enforces* that a human can't merge a PR with a failing check.
- **A real pull request was never opened via GitHub's UI in this session** — no `gh` CLI or authenticated browser access was available. Verification instead came from `push`-triggered runs directly against `main`, which exercises the same job logic `pull_request` would, just not the PR-specific UI integration (inline check annotations on a PR's "Files changed" tab, merge-button gating). The `on: pull_request` trigger itself is standard, well-documented GitHub Actions syntax — not exercised live, but not novel or risky syntax either.
- **The deploy workflow's correctness beyond the gate logic is unverified** — the ECR push / ECS update / health-check steps have real, plausible syntax but have never actually run (by design, since `AWS_DEPLOY_ENABLED` is off). Unlike the CI workflow, this part carries the same "written and locally reasoned about, not live-verified" status as Phase 8's Terraform.

## 12. Failure Scenarios

| What failed | How it was detected | Recovery | What's logged |
|---|---|---|---|
| Frontend type-check on a fresh checkout (real, this phase) | CI run #1's frontend job, exit code 2 | Root-caused, reproduced locally, fixed, verified by run #2 | Full `tsc` output naming the exact missing type |
| CI workflow fails on a future PR | The PR's checks tab shows a red ❌ directly on the PR, blocking a confident merge (though not a technically enforced one — see section 11) | Same process as section 8 | Same as any other Actions run |
| Deploy workflow triggered before AWS is ever configured | `vars.AWS_DEPLOY_ENABLED` gate — confirmed live, both runs | N/A — nothing to recover from, it correctly never attempted anything | A clean "skipped" status, not a log entry to dig through |
| A deploy's health check fails (once actually enabled) | `deploy.yml`'s final step, polling the ALB | Manual: `terraform apply -var="backend_image=<previous-tag>"` (Phase 8's rollback procedure) | The workflow run's failed health-check step |

## 13. Debugging Guide

1. **"My PR's checks are red."** Open the specific failing job, read the actual error (not just the red X), and check whether it's a real failure or one of GitHub's own infra notices (section 8).
2. **"It works locally but fails in CI."** This is exactly what happened in this phase — suspect anything gitignored that your local environment has accumulated but a fresh checkout wouldn't (build output, generated types, cached dependencies) before suspecting the code itself.
3. **"The deploy workflow isn't running at all."** Check whether CI actually succeeded first (`workflow_run` only fires after `ci.yml` completes) — a deploy workflow that never appears is often just waiting on a CI run that hasn't finished, not broken.
4. **"Deploy shows as skipped and I expected it to run."** Check the exact `if:` condition against the actual repo variable/secret state — `vars.AWS_DEPLOY_ENABLED` must be the literal string `"true"`, not merely "set."

## 14. Hands-on Exercises

1. Open a real pull request (using `gh` CLI or GitHub's web UI, whichever you have access to) and watch the same `ci.yml` checks run in the PR's own "Checks" tab — compare the UI to the `push`-triggered runs this phase actually used.
2. Add branch protection to `main` requiring the CI workflow's jobs to pass before merging — the enforcement gap flagged in section 11.
3. Deliberately break something (e.g., introduce a failing test) on a branch, open a PR, and confirm the check fails and is visibly blocking.
4. Set up a real AWS account, apply Phase 8's Terraform for real, set `AWS_DEPLOY_ROLE_ARN`/`AWS_DEPLOY_ENABLED`/`ALB_URL`, and watch `deploy.yml` actually deploy for the first time — the one part of this phase's pipeline that remains genuinely unverified.
5. Add a step that posts a comment or a badge update summarizing test results directly on the PR — a common real-world CI enhancement not built here.

## 15. Interview Questions

- Walk through exactly what happened when this project's CI workflow ran for the first time — what failed, why, and how it was fixed.
- Why does the deploy workflow use `workflow_run` instead of being triggered directly by `push`?
- Explain OIDC-based AWS authentication for GitHub Actions well enough to convince someone it's more secure than a static access key in a repo secret.
- Why does this project's deploy job show "skipped" instead of "failed" when AWS isn't configured, and why does that distinction matter?
- What's the actual difference between what CI verifies and what CD does, and why keep them in separate workflow files here?

## 16. Reverse Explanation Questions

- Explain, in your own words, why the `LayoutProps` bug could exist for multiple phases without ever being noticed locally, and why CI was exactly the right mechanism to catch it.
- Explain the two independent deployment gates in `deploy.yml` and what each one specifically protects against.
- Explain why "the workflow ran and found a real bug" is a *better* outcome for this phase than "the workflow ran and passed immediately" would have been, from a learning standpoint.

## 17. Quiz

1. What was the exact root cause of CI run #1's failure, in one sentence?
2. Name the two separate conditions that both have to be true for `deploy.yml`'s job to actually attempt a deployment.
3. True or false: the AWS credentials used in `deploy.yml`, once enabled, would be a long-lived access key stored as a GitHub secret.
4. Why did `Deploy #1` show as skipped even though its triggering CI run failed?
5. What command reproduced the CI failure locally, and why did that specific command (versus just running `npm run build`) prove the root cause precisely?

## 18. Common Misconceptions

- **"If it works when I run it locally, CI is just a formality."** This phase's own Run #1 is the direct counterexample — real, live proof that a local machine's accumulated state can hide a bug a fresh environment immediately exposes.
- **"A skipped job means something is broken."** Distinguished directly in this phase: skipped means a condition correctly evaluated to false — an intentional, designed outcome, different from failed (a condition or step didn't meet its bar) and different from cancelled.
- **"OIDC is more complicated, so a static access key is easier and just as safe for a personal project."** More setup, yes (an IAM OIDC provider + a trust policy) — but "easier" isn't "as safe": a static key is a permanent secret that works from anywhere until manually rotated; OIDC issues credentials that are short-lived and restricted to exactly this repository's main branch by construction.

## 19. Phase Checklist

- [x] CI workflow runs on every PR and push to main
- [x] **Verified live, twice, on GitHub's real infrastructure** — not just written
- [x] A real bug found on the very first execution, root-caused, fixed, and the fix verified by a second real run
- [x] Deploy workflow correctly gated — confirmed to skip cleanly (not fail) both when CI fails and when AWS isn't configured
- [x] AWS authentication via OIDC, no long-lived credentials anywhere, scoped to this exact repository and branch
- [x] Real backend linting (ruff) added, genuine issues found and fixed, false positives explicitly documented rather than silently suppressed
- [x] Rollback procedure documented and consistent with Phase 8's immutable ECR tags

## 20. What I Should Be Able to Explain

1. The complete, real story of this phase's first CI run: what failed, why, how it was diagnosed, and how the fix was verified — with actual timings and job names, not a hypothetical.
2. Why CI and CD are separate workflow files connected by `workflow_run`, and what that connection actually enforces.
3. How OIDC-based AWS authentication works well enough to explain it to someone who's only ever used static access keys.
4. The difference between a deployment gate correctly skipping and a pipeline failing, and why conflating them would be dishonest about this project's actual state.
5. Why "verify that the workflow actually runs" isn't a checkbox — it's what turned a plausible-looking YAML file into something that found and fixed a real bug within minutes of existing.

We'll verify this together when you're ready.
