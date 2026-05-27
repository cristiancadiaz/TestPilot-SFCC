# NFR Tactics And Verification Matrix - TestPilot SFCC

> Station 4 critical artifact. This matrix translates non-functional requirements into concrete architecture tactics and verification criteria.

## Verification Policy

Each NFR must have:

- A concrete architecture tactic.
- A measurable or automatable verification method.
- A responsible component or unit.
- A decision about whether it blocks MVP release.

## Matrix

| NFR | Quality Attribute | Architecture Tactic | Verification Criteria | Owner | MVP Gate |
|---|---|---|---|---|---|
| RNF-01 Credential security | Security | Use `environment_id` in payload and resolve `env_access` + `shopper` credentials server-side through Secrets Manager. Pydantic models use redacted representations for secret-bearing types. | API tests prove request payloads contain no URL, email, password, card, token, or key fields. Log tests prove redaction filters mask matching fields. | U0, U4 | Blocking |
| RNF-02 Zero contamination | Business safety | Payment always fails by design. `orders_created=0` is asserted in executor/reporter/API layers. Shopper emails must use `@testpilot.internal`. | Unit tests fail if `orders_created != 0`. Fixtures and test data grep only use `@testpilot.internal` synthetic shopper emails. | U1, U3, U4 | Blocking |
| RNF-03 Structured logging without secrets | Observability / Security | Use Python logging with JSON formatter, request/run correlation ID, and redaction filter for `password`, `token`, `card`, `key`, `env_access`, and `shopper`. | Tests pass representative log payloads and assert secret-like values are redacted. Manual review confirms no stack traces or credentials in error responses. | U1, U2, U3, U4 | Blocking |
| RNF-04 Safe error handling | Reliability / Security | Define typed errors and a central API error taxonomy. Map infrastructure failures to 503, run timeout to 504, auth to 401, validation to 422, and unexpected failures to 500 without stack traces. | API tests cover each error family and assert `error_code` plus no stack trace fields. | U1, U4 | Blocking |
| RNF-05 Input validation | Security / Correctness | Validate API inputs through Pydantic and JSON Schema before execution. Reject unsupported flows/profiles and unknown fields. | Tests prove invalid flow names return validation errors and no browser is launched. Contract tests validate examples against schema. | U0, U4 | Blocking |
| RNF-06 API authentication | Security | Require `X-API-Key` on all `/v1/*` endpoints. Fail loud on startup if `TESTPILOT_API_KEY` is missing outside local test mode. | API tests assert every endpoint returns 401 without key. Startup test asserts missing key fails in production mode. | U4 | Blocking |
| RNF-07 Executor performance and anti-flake | Performance / Reliability | Run profiles concurrently with bounded semaphore. Use Playwright waits (`wait_for_selector`, `expect`, `wait_for_load_state`) instead of fixed sleeps. Apply global run timeout. | Static grep rejects `time.sleep(` in `src/executor/`. Integration tests mock slow profiles and verify timeout behavior. | U1, U4 | Blocking |
| RNF-08 Supply chain and reproducible build | Maintainability / Security | Pin Python dependencies, use official Playwright Docker image with fixed tag, run as non-root user, and exclude secrets/build noise via `.dockerignore`. | CI runs `ruff check`, `mypy --strict`, dependency audit, and Dockerfile checks for no `:latest` and non-root user. | U0 | Blocking |
| RNF-09 Property-based testing for baseline/reporting | Correctness | Use Hypothesis for p95 bounds, monotonic traffic-light behavior, bootstrap invariant, and report serialization robustness. | PBT suite passes: p95 is within min/max of successful runs, bootstrap always returns green, and report serialization does not fail for valid generated reports. | U2, U3 | Blocking for U2/U3 |
| RNF-10 Build reproducibility | Maintainability | Define project metadata and tool config in `pyproject.toml`; keep generated dashboard build deterministic if MD0 uses Vite/React. | Fresh clone can run install, tests, lint, and type check with documented commands. No implicit global tools required beyond chosen package manager. | U0, MD0 | Blocking |
| RNF-11 Dashboard security headers | Security | Serve dashboard with CSP, `X-Content-Type-Options`, `Referrer-Policy`, and frame restrictions from FastAPI middleware or static server config. | Browser/API test checks expected security headers on dashboard and `/v1/*` responses. | MD0, U4 | Blocking for dashboard release |
| RNF-12 Environment and secret cache TTL | Performance / Security | Cache environment registry for 60s and resolved credentials for at most 5 minutes. Invalidate on environment update. | Unit tests verify cache hit, expiry, and invalidation behavior. Manual operational note documents max stale window. | U4 | Non-blocking for first local stub, blocking before shared staging |
| RNF-13 Polling-friendly live status | Performance / UX | Maintain in-memory live status during run and expose lightweight `GET /v1/runs/{id}/status` for dashboard polling. | Test asserts status endpoint avoids loading full screenshots/report and can return within target budget under mocked store. | U4, MD0 | Blocking for dashboard live view |
| RNF-14 Screenshot cost discipline | Cost / Operability | Capture screenshots only on failed steps and final flow state. Keep intermediate OK screenshots disabled for MVP. | Tests assert a successful 10-step flow produces one final screenshot and a failed flow captures the failed step. Review verifies no `screenshot_on_success` option is exposed in MVP API. | U1, U4, MD0 | Blocking |

## Cross-Cutting Verification Commands

These commands become the default verification set once code exists:

```powershell
ruff format .
ruff check .
mypy src
pytest
```

Additional targeted checks:

```powershell
rg -n "time\.sleep\(" src/executor
rg -n "@(?!testpilot\.internal)" tests src
rg -n "password|token|card|key" aidlc-docs src tests
```

The grep checks are intentionally conservative. Any hit must be manually reviewed rather than automatically treated as a failure.

## Release Gate Interpretation

- **Blocking** means the MVP should not be considered release-ready without automated or explicitly reviewed evidence.
- **Non-blocking for local stub** means acceptable during local design validation, but it becomes blocking before shared staging or CI/CD consumption.
- If an NFR conflicts with `AGENTS.md`, `AGENTS.md` is the operating constraint for this repository until an ADR explicitly changes it.
