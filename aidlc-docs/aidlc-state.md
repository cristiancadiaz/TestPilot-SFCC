# AI-DLC State Tracking

## Project Information

- **Project Name**: TestPilot SFCC
- **Project Type**: Brownfield documentation-first MVP
- **Start Date**: 2026-05-20
- **Workspace Root**: `F:\Development_Projects\IA\TestPilot-SFCC`
- **Current Stage**: INCEPTION PHASE - scope realignment re-entry COMPLETE (E4 approved); next gate = specs/ contracts HITL
- **Last Reconciled**: 2026-06-03
- **Scope Realignment**: 2026-06-02/03, branch `rework/storefront-audit-scope`. The project returned from pre-Construction to Inception (Requirements Analysis) to restore the full PRD scope: store journey flows, 6-dimension audit document, network capture, NL window. Fixed scope — time is the adjustment variable. Rationale: `inception/scope-realignment-brief.md`.

## Workspace State

- **Existing Code**: No application source code committed yet for the MVP modules.
- **Existing Product Artifacts**: Yes. Canonical README/PRODUCT/AGENTS/DESIGN files, PRD snapshot under `docs/product/`, product research under `docs/research/`, API schemas under `specs/`, Antigravity mission briefs, and AI-DLC artifacts are present.
- **Reverse Engineering Needed**: No for the current Station 4 review. Existing reverse engineering artifacts are treated as a historical snapshot and should be refreshed before Construction if source code is added.
- **Workspace Root Verified**: Yes, normalized from previous `F:\Development_Projects\IA\06_testing_sintetico` reference to `F:\Development_Projects\IA\TestPilot-SFCC`.

## Code Location Rules

- **Application Code**: Workspace root under `src/`, `tests/`, `specs/`, and `infra/` only.
- **AI-DLC Documentation**: `aidlc-docs/`.
- **Course/Prompt Material**: `.hardcore-ai/` and `.aidlc-rules/` are local reference material and are ignored by git.
- **Protected Files**: Never read or edit `.env`, `.env.local`, `.env.production`, `secrets/`, or `infra/cdk.context.json`.

## Extension Configuration

| Extension | Enabled | Mode | Source |
|---|---:|---|---|
| Security Baseline | Yes | Full | AI-DLC requirements analysis |
| Property-Based Testing | Yes | Partial | Baseline/reporter invariants |

## Stage Progress

### Inception Phase

- [x] Workspace Detection - represented by this state file and audit log.
- [x] Reverse Engineering - artifacts exist in `aidlc-docs/inception/reverse-engineering/`.
- [x] Requirements Analysis - `aidlc-docs/inception/requirements/requirements.md`.
- [x] User Stories - `aidlc-docs/inception/user-stories/user-stories.md`.
- [x] Workflow Planning - `aidlc-docs/inception/plans/execution-plan.md`.
- [x] Application Design - `aidlc-docs/inception/application-design/`.
- [x] Units Generation - `aidlc-docs/inception/application-design/unit-of-work.md`.

### Inception Re-entry — Scope Realignment (2026-06-03, all HITL-approved)

- [x] Requirements Analysis v2 - `requirements.md` realigned: RF-21..RF-29, RNF-14..RNF-15, C10..C12, restructuring analysis with brief/PRD traceability. RF-14..RF-20 and RNF-11..RNF-13 (application design 2026-05-24) backported after numbering-collision detection. APPROVED.
- [x] User Stories iteración 3 - 40 stories / 157 ACs; decisions D14-D18; new persona Valentina (non-technical, UC6); J4 de-deferred (H7.3); coverage-matrix updated (M20-M23). APPROVED.
- [x] Units Generation v2 - U5 (journey flows), U6 (audit collectors + synthesis agent), U7 (network capture), U8 (NL window + modes); dependency matrix + Fases 5-6 + checkpoints 4-6; story-map extended. APPROVED.
- [x] **specs/ contracts HITL gate (cascade #6)** - APPROVED with recommendations (full_journey as enum value, audit doc as S3 ref, network_summary per profile) and APPLIED 2026-06-03: `synthetic-user-config.schema.json` → v2, `execution_report.schema.json` → v2, `translate-request-response.schema.json` created. Schemas + examples validated (Draft 2020-12). v1 remains valid 30 days (P2).

### Construction Phase

- [x] Construction planning artifacts exist under `aidlc-docs/construction/`.
- [x] **U0 Setup Base — COMPLETE (2026-06-06).** Wave-1 first unit. Delivered: `pyproject.toml` + `uv.lock` (TASK-001), `Dockerfile` + `.dockerignore` (TASK-002), `src/models.py` unified Pydantic models mirroring specs v2 (TASK-003), `tests/test_models.py` 20 tests (TASK-004), Gate 1 + `u0/code/code-summary.md` (TASK-006). TASK-005 (translator/api dedup) DEFERRED to U4 — that scaffolding does not exist yet. **Gate 1:** ruff/mypy/pytest/docker build all exit 0; pip-audit initially found 4 transitive vulns (starlette×3, pytest×1) — RESOLVED via HITL-approved security bump 2026-06-06 (starlette→1.2.1 direct pin, fastapi→0.136.3, pytest→9.0.3, pytest-asyncio→1.4.0, pytest-playwright→0.8.0); pip-audit now clean; `/v1/run` 422 check N/A (no API in U0).
- [x] **Wave-1 code-gen plans reconciled to v2 (2026-06-06, HITL-approved).** U1 (desktop_ec + auth/login + 10-step checkouts), U2 (composite key + gate-only guard), MD0 (new plan: React/Vite/TS). `ResolvedEnvironment`+`Credentials` added to `src/models.py` (U0 amendment) to unblock U1.
- [x] **Sprint 1 wave-1 core COMPLETE (2026-06-08): U1 Executor + U2 Baseline + MD0 Dashboard.** All code generated and verified. **U1** committed `a72b4ba`; Gate 3 closed (added `test_env_access_passed_as_http_credentials` to cover the http_credentials criterion). **U2** Baseline: ruff/mypy/37 tests verde, Gate 2 closed. **MD0** Dashboard: `pnpm build` (tsc strict + vite) + 37 vitest tests + lint verde — ESLint flat config fixed (added `@typescript-eslint/parser`; it was parsing `.ts` with espree). Gate 6 marked partial: code-gen done, but CSP headers + "5 screens vs real backend" defer to U4 integration and Lighthouse is a pending perf pass. Full Python suite: 88 tests verde. HITL-authorized: includes `src/executor/flows/` (protected path).
- [x] **U3 Reporter COMPLETE (2026-06-08).** `src/reporter/` (`generate_report`, `compute_profile_verdict`, `to_json_dict`, `to_markdown`). Computes the deterministic verdict (U1 leaves GREEN placeholder → U3 replaces): per profile×flow (failed→RED, error→YELLOW, success→p95 rule via U2) and global=worst-of. JSON validates vs `execution_report.schema.json` v2 (snake_case — corrected the stub's camelCase/percentDiff errors). Decisions D-U3-1/2/3 applied (HITL-approved): report baseline = worst-verdict combo; report bootstrap = all-combos; U3 read-only on baseline (save_run is U4). Gate 4 closed. 21 U3 tests (15 deterministic + PBT); full suite 110 verde.
- [~] **U4 API — IN PROGRESS (phased, D-U4-3). Phase A COMPLETE (2026-06-08).** `src/api/` built from scratch: schemas, errors (taxonomy §5), `verify_api_key`, Security+RequestLogging middlewares, Protocols+in-memory fakes (Environment/Secrets/RunReport/Screenshot — D-U4-1, no moto), EnvironmentResolver (S6), RunOrchestrator (S1: uuid4 + resolve + `asyncio.gather` over profiles×flows under `Semaphore(3)` + `wait_for(1800)` → U3 `generate_report` → U2 gate-only `save_run` → persist + live tracker; invariant #1 → 500), LiveStatusTracker (S7), `POST /v1/run` + `/health`, app factory + structured exception handlers. Wave-1 flow guard (full_journey + journey flows → 422). 12 tests; full suite 122 verde. **Decisions D-U4-1/2/3 applied.** `/v1/translate` + `src/agents` → U8 (TASK-005 dedup moves to U8). **Phase A = the E2E spine: dashboard → /v1/run → report works.**
  - [ ] Phase B — environments registry CRUD (S5) + runs history (S2: GET {id}/latest/list) + `/status` (S7).
  - [ ] Phase C — screenshots router + static mount of dashboard dist + CSP finalize (closes MD0 Gate 6 CSP) + full error-taxonomy test coverage. Gate 5 closes here.
- [ ] Wave 2 (U5-U8) — after wave 1, per their plans.

### Operations Phase

- [ ] Not started.

## Current Inception Artifacts

### Reverse Engineering

- `business-overview.md`
- `architecture.md`
- `code-structure.md`
- `api-documentation.md`
- `component-inventory.md`
- `technology-stack.md`
- `dependencies.md`
- `code-quality-assessment.md`
- `reverse-engineering-timestamp.md`

### Requirements, Planning, And Design

- `architecture/c4-diagrams.md`
- `architecture/adrs/adr-001-structured-config-and-environment-resolved-credentials.md`
- `architecture/adrs/adr-002-screenshot-capture-policy.md`
- `architecture/nfr-tactics-verification.md`
- `requirements/requirements.md`
- `requirements/requirement-verification-questions.md`
- `plans/execution-plan.md`
- `user-stories/user-stories.md`
- `user-stories/gherkin-scenarios.md`
- `user-stories/coverage-matrix.md`
- `application-design/components.md`
- `application-design/component-methods.md`
- `application-design/component-dependency.md`
- `application-design/services.md`
- `application-design/unit-of-work.md`
- `application-design/unit-of-work-dependency.md`
- `application-design/unit-of-work-story-map.md`
- `application-design/env-vars-catalog.md`
- `application-design/error-taxonomy.md`
- `application-design/logging-strategy.md`

## Optional Follow-Ups

These items are useful for navigation, but they are not blocking for Station 4 Inception completion:

1. Optionally create index files that map AI-DLC expected names to the current organized files:
   - `workspace-detection.md`
   - `requirements-analysis.md`
   - `workflow-planning.md`
   - `application-design.md`
   - `units-generation.md`

## Resolved Critical Gaps

- [x] C4 Level 1 and Level 2 diagrams in Mermaid - `aidlc-docs/inception/architecture/c4-diagrams.md`.
- [x] Minimum ADR documented - `aidlc-docs/inception/architecture/adrs/adr-001-structured-config-and-environment-resolved-credentials.md`.
- [x] Formal Gherkin scenarios documented - `aidlc-docs/inception/user-stories/gherkin-scenarios.md`.
- [x] NFR tactics and verification matrix documented - `aidlc-docs/inception/architecture/nfr-tactics-verification.md`.
- [x] Screenshot policy conflict resolved - `aidlc-docs/inception/architecture/adrs/adr-002-screenshot-capture-policy.md`.

## Next Recommended Step

**🏁 Scope realignment cascade COMPLETE (2026-06-03).** All 9 cascade steps done and HITL-approved: research notes, product docs, requirements v2, stories iteración 3, units U5-U8, specs v2, construction plans + architecture pass, state/audit, harness (CLAUDE.md local + AGENTS.md + tech matrix + PRODUCT.md §6 + flow-guardian composition exception).

**U0 Setup Base CLOSED (2026-06-06)** — Gate 1 passed (TASK-006). **Next: U1 Executor + U2 Baseline + MD0 Dashboard in parallel** per `construction/plans/build-sequence.md` (Sprint 1). Then U3 (needs U1+U2), U4 (integrates all; also where TASK-005 translator/api dedup lands). Wave 2 (U5-U8) follows its plans after wave 1. Refresh `inception/reverse-engineering/` when more code lands.
