# U4 API — Code Summary

> Gate 5 verified (2026-06-08). ruff + mypy --strict (18 source files) + pytest all
> green; full suite **160 tests**. Built in 3 phases (D-U4-3).
>
> Supersedes the earlier stub (which described a single `src/api/main.py`, only 3
> endpoints, and "camelCase" / `ageSeconds`/`ttlOk` / `ordersCreated` — all wrong:
> the API surface is much larger and the contract is snake_case).

---

## Files created (`src/api/`)

| File | Purpose |
|---|---|
| `schemas.py` | API-only Pydantic models (EnvironmentConfig/Update, RunState, ProfileRunStatus, RunStatus, RunListItem/Response/Query, ApiErrorPayload). |
| `errors.py` | `TestPilotApiError` hierarchy (error-taxonomy §5) + `ScreenshotNotFoundError`. |
| `security.py` | `verify_api_key` dependency (X-API-Key vs `API_KEY` env, fail-closed). |
| `middleware.py` | `RequestLoggingMiddleware` (request_id, no secrets), `SecurityHeadersMiddleware` (CSP + headers). |
| `stores.py` | Protocols + in-memory fakes: `EnvironmentStore`, `SecretsClient`, `RunReportStore`, `ScreenshotStore`. |
| `services/environment_resolver.py` (S6) | `environment_id` → `ResolvedEnvironment` + 5-min TTL cache. |
| `services/environment_registry.py` (S5) | CRUD + secret-path validation on create. |
| `services/run_orchestrator.py` (S1) | the run pipeline (see below). |
| `services/live_status_tracker.py` (S7) | in-memory bounded run status for polling. |
| `deps.py` | FastAPI providers reading `app.state`. |
| `routers/runs.py` | `POST /v1/run`, `GET /v1/runs`/`/latest`/`/{id}`/`/{id}/status`. |
| `routers/environments.py` | environments CRUD. |
| `routers/health.py` | `GET /health` (503 on probe failure). |
| `routers/screenshots.py` | `GET /v1/runs/{id}/screenshots/{key}` → 307 redirect. |
| `app.py` | factory: middlewares, 3 exception handlers, routers, in-memory default bundle, static mount of `dashboard/dist`. |

Tests: `test_api_run.py` (12), `test_api_environments.py` (10), `test_api_runs.py` (13),
`test_error_taxonomy.py` (10), `test_api_assets.py` (5) = **50 U4 tests**.

## The run pipeline (RunOrchestrator, S1)

`uuid4` run_id → `resolver.resolve(environment_id)` (404/409/502/422) →
validate flows against the wave-1 `FLOW_REGISTRY` (full_journey / journey flows →
422) → `asyncio.gather` over profiles×flows under `Semaphore(3)` + `asyncio.wait_for(1800s)`
(timeout → 504) → invariant #1 check (`orders_created != 0` → CRITICAL log + 500
`invariant_violated`) → U3 `generate_report` (deterministic verdict) → persist report →
U2 `save_run` per combo (**gate-only guard**) → `tracker.complete`.

## Decisions applied (HITL-approved)

- **D-U4-1** — AWS via Protocols + **in-memory fakes** (no `moto` dependency). boto3
  adapters (DynamoDB/Secrets/S3) + real wiring are the **infra/CDK milestone**.
- **D-U4-2** — `/v1/translate` + `src/agents` NL translator are **out → U8 (wave 2)**.
  TASK-005 (translator/api dedup) moves to U8.
- **D-U4-3** — built in 3 phases: A (E2E spine) → B (environments + history) → C
  (evidence + static + hardening). Gate 5 closed at C.

## Deviations / notes

- API-only models live in **`src/api/schemas.py`**, not `src/models.py` (CLAUDE.md
  boundary "api/ … Pydantic schemas"); `src/models.py` stays the spec-mirrored source.
- New gap filled: **`RunReportStore`** — U2's `BaselineStore` holds only flattened
  `RunRecord`s, so full `ExecutionReport` retrieval (`GET /v1/runs/{id}`) needed its own store.
- `ResolvedEnvironment` is flat (`env_access`/`shopper`/`store_url`) — the 2026-05-24
  design's `env.config.*` shape was reconciled to the real U0 model.
- `/v1/runs/latest` is **gate-only** (exploratory runs never drive the deploy decision).
- `ScreenshotNotFoundError` (404 `screenshot_not_found`) is additive to error-taxonomy.md
  (§8 process) for the evidence endpoint.
- 60s registry read cache (NFR-U4-P1) deferred to the DynamoDB adapter.
- `/v1/run` response is serialized via U3 `to_json_dict` (schema-valid, `orders_created` excluded).

## What this unlocks

- **Full E2E demo** (wave-1 DoD): dashboard → `POST /v1/run` → live status → report + verdict + history.
- **MD0 Gate 6 CSP** criterion is now satisfiable (CSP served by `SecurityHeadersMiddleware`).
- Remaining for production: boto3 adapters + CDK infra (DynamoDB tables, Secrets, S3, ECS).
