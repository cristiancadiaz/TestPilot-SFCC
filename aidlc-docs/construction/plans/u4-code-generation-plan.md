# U4 API — Code Generation Plan (reconciled to specs v2 + U1/U2/U3 real APIs, 2026-06-08)

> **Part 1 — Planning.** This plan supersedes the earlier 3-step stub (which was
> aspirational — it claimed a single `src/api/main.py` already existed and was
> marked `[x]`, but no `src/api/` exists in the tree). U4 is the largest unit;
> this plan reconciles it to the S1–S8 service design, the error taxonomy, and the
> **actual** models/APIs of U1/U2/U3. Awaiting HITL approval before generation.

## Purpose & scope

U4 is the FastAPI integration layer: it turns a validated `SyntheticUserConfig`
into a run by orchestrating the executor (U1), reporter (U3) and baseline (U2),
and exposes the REST surface the dashboard (MD0) and CI/CD consume.

**In scope (S1–S8, build-sequence Sprint 2):**
- `POST /v1/run` — orchestrated run (S1 `RunOrchestrator`)
- `GET /v1/runs/{id}`, `GET /v1/runs/latest`, `GET /v1/runs` (list+filters) (S2)
- `GET /v1/runs/{id}/status` — live polling state (S7 `LiveStatusTracker`)
- `POST/GET/PUT/DELETE /v1/environments` — registry CRUD (S5)
- environment resolution `environment_id → ResolvedEnvironment` (S6)
- `GET /health` (+ dependency check → 503)
- `GET /v1/runs/{id}/screenshots/...` — evidence URLs (screenshots router)
- static mount of `src/dashboard/dist/` + SPA fallback (S8)
- `SecurityHeadersMiddleware`, `RequestLoggingMiddleware`, single exception handler

**Out of scope (deferred):**
- `POST /v1/translate` + `src/agents/` NL translator → **U8 (wave 2)**. The NL
  window is wave-2; U4 ships the structured API only (decision D-U4-2).
- `audit` / `network_summary` enrichment → U6 / U7.
- Real AWS wiring (table/secret/bucket creation, IAM) → infra/CDK milestone.

## What U4 wires (already built — do NOT reimplement)

| Dep | Real API | Notes |
|---|---|---|
| U1 executor | `run_profile(profile, flow_name, config, env, run_id) -> ProfileResult` (async) | Returns GREEN placeholder verdict; sets `http_credentials` from `env.env_access`. |
| U3 reporter | `generate_report(run_id, environment_id, mode, started_at, finished_at, profile_results, baseline_manager) -> ExecutionReport` | Computes the real verdict; reads baseline. |
| U2 baseline | `BaselineManager.save_run(run, mode)` (gate-only guard), `get_baseline_comparison(...)`, `list_runs(...)`; `BaselineStore` Protocol + `InMemoryBaselineStore` | U3 reads; **U4 owns `save_run`** (decision D-U3-3). |
| models | `SyntheticUserConfig`, `ResolvedEnvironment` (flat: `environment_id`, `store_url`, `env_access`, `shopper`), `Credentials`, `ExecutionReport`, `ProfileResult`, `RunRecord`, `BrowserProfile`, `TrafficLight` | — |

**Reconciliation note:** the 2026-05-24 design references `env.config.store_url`
and `EnvironmentAccessCredentials/ShopperCredentials`. The **actual** U0 model is
flat (`env.store_url`, `env.env_access: Credentials`, `env.shopper: Credentials`)
— U4 uses the real model (as U1's runner already does).

## New models U4 adds to `src/models.py` (mirror MD0 `types/api.ts` + design)

- `EnvironmentConfig` — `environment_id`, `store_url`, `env_access_secret_path`,
  `shopper_secret_path`, `active`, timestamps. (Registry record.)
- `RunState` enum (`pending|running|completed|failed`), `ProfileRunStatus`,
  `RunStatus` (live tracker payload; `orders_created: 0`).
- `RunListItem`, `RunListResponse` (`items, page, page_size, total, has_more`).
- `RunListQuery` (env, traffic_light, flow, from_date, to_date, page, page_size;
  default last 7 days — BR-U4-16).
- `ApiErrorPayload` (`error_code`, `message`, `request_id`, `details?`).
- `EnvironmentAccessCredentials` shape for Secrets JSON validation (or reuse `Credentials`).

## Exception hierarchy + error mapping (from `error-taxonomy.md`)

`TestPilotApiError(Exception)` base (`status_code`, `error_code`) with subclasses:
`EnvironmentNotFoundError` (404), `EnvironmentInactiveError` (409),
`SecretNotFoundError` (502), `InvalidSecretPathError` (422),
`RunNotFoundError` (404), `RunTimeoutError` (504),
`InvariantViolatedError` (500, CRITICAL log + metric). Plus `unauthorized` (401),
`no_runs_yet` (404), `validation_failed` (422, mapped from Pydantic),
`internal_error` (500), `infrastructure_error` (503 if it escapes the run).
Single `app.add_exception_handler(TestPilotApiError, ...)` → structured body
`{error_code, message, request_id, details?}`; **never** stack traces / paths /
secret values / auth headers (Security baseline + BR §3).

## Endpoint inventory

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/v1/run` | 200 `ExecutionReport` (+`X-Run-Id`) | 401, 422, 404 env, 409 inactive, 502 secret, 504 timeout, 500 invariant |
| GET | `/v1/runs/{id}` | 200 `ExecutionReport` | 401, 422 bad uuid, 404 |
| GET | `/v1/runs/latest` | 200 report + `age_seconds`+`ttl_ok` | 401, 404 no_runs_yet |
| GET | `/v1/runs` | 200 `RunListResponse` | 401, 422 |
| GET | `/v1/runs/{id}/status` | 200 `RunStatus` | 401, 404 |
| POST | `/v1/environments` | 201 `EnvironmentConfig` | 401, 409, 422 invalid_secret_path |
| GET | `/v1/environments` | 200 list | 401 |
| GET | `/v1/environments/{id}` | 200 | 401, 404 |
| PUT | `/v1/environments/{id}` | 200 | 401, 404, 400 id-change |
| DELETE | `/v1/environments/{id}` | 204 | 401, 404 |
| GET | `/v1/runs/{id}/screenshots/{...}` | 200 URL / redirect | 401, 404 |
| GET | `/health` | 200 / 503 | — (no auth) |
| GET | `/`, `/assets/*`, SPA fallback | 200 static | — |

## Service interfaces (Protocols) + backends — **decision D-U4-1**

Mirror U2's pattern: define narrow Protocols, ship **in-memory fakes** for the
wave-1 milestone (hermetic tests, local E2E + dashboard with **no AWS creds**);
boto3 adapters are thin shims behind the same Protocols, wired in the infra
milestone. `moto` is **not** added now.

- `EnvironmentStore` (Protocol) + `InMemoryEnvironmentStore` — registry persistence.
- `SecretsClient` (Protocol) + `InMemorySecretsClient` — `get_json(path)`.
- `RunReportStore` (Protocol) + `InMemoryRunReportStore` — **new gap**: U2's
  `BaselineStore` only holds flattened `RunRecord`s; full `ExecutionReport`
  retrieval for `GET /v1/runs/{id}` needs its own store.
- `ScreenshotStore` (Protocol) + `InMemoryScreenshotStore` — resolve S3 keys → URLs.
- `LiveStatusTracker` — in-memory ring buffer (max 100), thread-safe (S7).
- boto3 adapters (`DynamoDb*Store`, `SecretsManagerClient`, `S3ScreenshotStore`):
  thin, created but exercised lightly (or deferred to infra) — flagged in summary.

*(Alt for D-U4-1: add `moto` and implement/test real DynamoDB/Secrets/S3 now.)*

## Open decisions (HITL — recommended defaults in **bold**)

- **D-U4-1 — AWS backends.** **Protocols + in-memory fakes for wave-1**; boto3
  adapters as thin shims, real wiring in infra. No `moto` dependency added.
- **D-U4-2 — `/v1/translate` + `src/agents`.** **Out of U4 → U8 (wave 2).** Keeps
  `anthropic` usage and TASK-005 (translator/api dedup) in U8, where both the API
  and translator exist. *(Correction: TASK-005 lands in U8, not U4.)*
- **D-U4-3 — phased build (U4 is 5–7 days).** **Build in 3 reviewable phases**, each
  ending ruff+mypy+pytest green; Gate 5 closes at the end of Phase C.

## Steps (phased)

### Phase A — Core run path (the E2E spine) [x] ✅ (2026-06-08)
> Deviation: API-only models went to **`src/api/schemas.py`** (not `src/models.py`) to
> respect the CLAUDE.md boundary "api/ … Pydantic schemas". `src/models.py` stays the
> spec-mirrored contract source.
- [x] `src/api/schemas.py`: `EnvironmentConfig`, `RunState`, `ProfileRunStatus`,
      `RunStatus`, `RunListItem/Response`, `RunListQuery`, `ApiErrorPayload`.
- [x] `src/api/errors.py` — exception hierarchy (taxonomy §5).
- [x] `src/api/security.py` — `verify_api_key` dependency (X-API-Key vs `API_KEY` env).
- [x] `src/api/middleware.py` — `SecurityHeadersMiddleware`, `RequestLoggingMiddleware`
      (request_id, no secrets — logging-strategy).
- [x] `src/api/stores.py` — `EnvironmentStore`/`SecretsClient`/`RunReportStore`/
      `ScreenshotStore` Protocols + in-memory fakes.
- [x] `src/api/services/environment_resolver.py` (S6) — resolve + 5-min cache.
- [x] `src/api/services/run_orchestrator.py` (S1) — `uuid4` run_id, resolve env,
      `asyncio.gather` over profiles×flows under `Semaphore(MAX_CONCURRENT_PROFILES=3)`
      + `asyncio.wait_for(RUN_TIMEOUT_SECONDS=1800)`, call `generate_report` (U3),
      then `save_run` per combo (U2, gate-only), persist report, update tracker.
      Invariant #1 checked (→ 500 `invariant_violated`). Wave-1 flow guard (full_journey
      + journey flows → 422).
- [x] `src/api/services/live_status_tracker.py` (S7).
- [x] `src/api/routers/runs.py` — `POST /v1/run`; `src/api/routers/health.py`;
      `src/api/deps.py` providers.
- [x] `src/api/app.py` — app factory: middlewares, structured exception handlers
      (`TestPilotApiError`, `RequestValidationError`→validation_failed, `Exception`→500).
- [x] `tests/test_api_run.py` — 12 tests: 200 + `X-Run-Id`; 401 no/bad key; 422 invalid
      flow + full_journey; 404 env; gate-saved/exploratory-not; 500 invariant; health
      200/503; security headers. ruff+mypy(15 files)+pytest green; full suite 122.

### Phase B — Environments registry + run history [x] ✅ (2026-06-08)
- [x] `src/api/services/environment_registry.py` (S5) — CRUD + secret-path validation
      on create (→ 422 `invalid_secret_path`; 409 already-exists). 60s read cache deferred
      to the DynamoDB adapter (in-memory store is already O(1)).
- [x] `src/api/routers/environments.py` — POST(201)/GET/GET{id}/PUT/DELETE(204).
- [x] `src/api/routers/runs.py` — `GET /v1/runs/{id}` (404, 422 bad uuid), `/latest`
      (age+ttl_ok, **gate-only**, 404 no_runs_yet), `GET /v1/runs` (filters, default 7
      days, pagination), `GET /v1/runs/{id}/status`.
- [x] `tests/test_api_environments.py` (10) + `tests/test_api_runs.py` (13) — per-endpoint codes.

### Phase C — Evidence, static, hardening [x] ✅ (2026-06-08)
- [x] `src/api/routers/screenshots.py` — `ScreenshotStore` → 307 redirect; 404 missing.
- [x] Static mount of `src/dashboard/dist/` (S8) — omitted gracefully if absent (BR-U4-22);
      `/v1/*`+`/health` registered first, StaticFiles last (SPA fallback).
- [x] CSP / security headers (set in Phase A middleware) — closes MD0 Gate 6 CSP criterion.
- [x] `tests/test_error_taxonomy.py` (10) — one test per row; 5xx bodies carry no stack
      traces / secret messages; `invariant_violated` → CRITICAL log.
- [x] `GET /health` returns 503 when a dependency probe fails.
- [x] `tests/test_api_assets.py` (5) — screenshots 307/404/auth + static serving.

### Step D — `aidlc-docs/construction/u4/code/code-summary.md` [x] ✅

## Gate 5 — promotion criteria (build-sequence.md) ✅ (2026-06-08)
- [x] All documented endpoints return correct HTTP codes
- [x] No stack traces in responses (5xx bodies structured, redacted)
- [x] Auth mandatory on every `/v1/*` (health exempt)
- [x] `/health` returns 503 when dependencies are down
- [x] Environment CRUD works against the store (in-memory fake; **DynamoDB adapter behind
      same Protocol deferred to infra — D-U4-1**)
- [x] `LiveStatusTracker` updates during parallel runs
- [x] Paginated history with filters
- [x] `ruff` + `mypy --strict` exit 0; full `pytest` suite 160 green
- [x] `orders_created=0` enforced end-to-end (orchestrator → 500 `invariant_violated`)

## Security baseline compliance (extension enabled)
- Auth on all `/v1/*`; secrets only via `SecretsClient` (never in request/response/logs).
- No stack traces / server paths / secret paths in error bodies (taxonomy §3).
- Security headers + CSP (Phase C). `capture_intermediate_screenshots` stays `Literal[False]`.
- Structured logging with `request_id`; zero-secret logging (RNF-03).

## Verification commands
```bash
uv run ruff check src/api/ tests/test_api*.py tests/test_error_taxonomy.py
uv run mypy src/api/
uv run pytest tests/test_api_run.py tests/test_api_environments.py tests/test_api_runs.py tests/test_error_taxonomy.py -v
uv run pytest    # full suite stays green
```

## Notes / risks
- `RunReportStore` is a newly-identified need (U2's `BaselineStore` holds only
  flattened `RunRecord`s, not full reports). Without it `GET /v1/runs/{id}` cannot
  return an `ExecutionReport`.
- Orchestrator order matters: run profiles → `generate_report` (reads baseline) →
  `save_run` per combo (so the current run is never compared against itself).
- Phase A alone enables the **full E2E demo** (dashboard → `/v1/run` → report);
  Phases B/C complete the surface and close Gate 5.
