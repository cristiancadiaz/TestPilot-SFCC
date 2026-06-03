# C4 Diagrams - TestPilot SFCC

> Station 4 critical artifact. These diagrams describe the intended architecture for TestPilot SFCC from an ecommerce/SFCC product ownership perspective: release safety, checkout stability, environment isolation, and consumption by both engineers and downstream agents.
>
> **Realigned 2026-06-03** (branch `rework/storefront-audit-scope`): adds the non-technical user
> (NL window), journey flows, the audit synthesis agent (P7 — never decides the traffic light),
> and network/performance capture. Wave 1 (checkout gate) semantics unchanged.

## Level 1 - System Context

```mermaid
C4Context
    title TestPilot SFCC - C4 Level 1 System Context

    Person(engineer, "SFCC Engineer", "Launches QA runs before merge/deploy and reviews deploy-gate evidence.")
    Person(techLead, "Tech Lead", "Owns release confidence, quality gates, and operational risk.")
    Person(nonTech, "Non-technical Member (QA/PM)", "Describes a test in natural language and reads the audit document. Never writes JSON.")
    System_Ext(cicdAgent, "CI/CD or Review Agent", "Consumes latest structured report to decide whether a release is safe.")

    System(testPilot, "TestPilot SFCC", "Internal synthetic QA platform for SFCC storefronts. Runs journey and checkout flows with Playwright, captures network/performance data, compares against baseline, and emits JSON/Markdown reports plus a 6-dimension audit document. The traffic light is always a deterministic rule.")

    System_Ext(sfccStorefront, "SFCC/SFRA Storefront", "Sandbox, development, or staging storefront under test.")
    System_Ext(secretsManager, "AWS Secrets Manager", "Stores environment access credentials and shopper credentials.")
    System_Ext(dynamoDb, "DynamoDB", "Stores environment registry, run history, and baseline inputs.")
    System_Ext(s3, "Amazon S3", "Stores findings-driven visual evidence, HAR network traces, and audit documents.")
    System_Ext(anthropic, "Claude API", "NL-to-config translation and audit synthesis. Synthesizes, never judges the traffic light (P7).")

    Rel(engineer, testPilot, "Registers environments, launches runs, reviews Markdown report", "HTTPS / Dashboard")
    Rel(techLead, testPilot, "Reviews history, baseline, and deploy-gate decisions", "HTTPS / Dashboard")
    Rel(nonTech, testPilot, "Describes test in Spanish, confirms preview, reads audit document", "HTTPS / NL window")
    Rel(cicdAgent, testPilot, "Reads latest gate-mode run status and structured report", "REST /v1")

    Rel(testPilot, sfccStorefront, "Runs synthetic journey and checkout flows with env access and shopper login", "Playwright browser")
    Rel(testPilot, secretsManager, "Resolves env_access and shopper credentials by environment_id", "AWS SDK")
    Rel(testPilot, dynamoDb, "Persists environments, runs, and baseline records (gate mode only)", "AWS SDK")
    Rel(testPilot, s3, "Stores and retrieves evidence, HAR traces, and audit documents", "AWS SDK")
    Rel(testPilot, anthropic, "NL translation (pre-run, validated) and audit synthesis (post-run, sanitized input)", "Anthropic SDK")
```

### Level 1 Notes

- `TestPilot SFCC` is an internal release-confidence system, not a public SaaS.
- The primary business user is the SFCC engineering team that needs a deploy-safe decision in less than 30 minutes; the realignment adds non-technical members (QA/PM/business) via the NL window (UC6).
- The system boundary intentionally excludes SFCC production execution; the target environments are sandbox, development, and staging.
- Credentials never enter the run payload. `environment_id` is the only selector used to resolve URLs and secrets.
- Claude API has exactly two roles, both bounded: (a) pre-run NL→config translation, always schema+catalog validated with user-confirmed preview (the NL text never reaches the executor — C12); (b) post-run audit synthesis over deterministic findings with sanitized input (the agent never decides the traffic light — P7/C10).
- Two operation modes: `gate` (deterministic, feeds the baseline, blocks deploys) and `exploratory` (discovery; never enters the baseline — C11).

## Level 2 - Container

```mermaid
C4Container
    title TestPilot SFCC - C4 Level 2 Containers

    Person(engineer, "SFCC Engineer", "Launches QA runs and reviews evidence.")
    Person(techLead, "Tech Lead", "Reviews release gate and trends.")
    System_Ext(cicdAgent, "CI/CD or Review Agent", "Consumes JSON report.")
    System_Ext(sfccStorefront, "SFCC/SFRA Storefront", "Storefront under test.")
    System_Ext(secretsManager, "AWS Secrets Manager", "Credential store.")
    System_Ext(dynamoDb, "DynamoDB", "Environment registry, run history, and baseline storage.")
    System_Ext(s3, "Amazon S3", "Screenshot storage.")
    System_Ext(anthropic, "Claude API", "Optional AI translation/classification.")

    Container_Boundary(testPilotBoundary, "TestPilot SFCC") {
        Container(dashboard, "Dashboard Web", "React + Vite + TS", "NL window with preview/confirm, generic profiles-by-flows matrix, environments, history, audit document view, remaining daily runs.")
        Container(api, "FastAPI REST API", "Python 3.12 / FastAPI", "Owns /v1 endpoints incl. /v1/translate, auth, validation, orchestration, status, history, and evidence proxy.")
        Container(models, "Shared Models", "Pydantic + JSON Schema v2", "Defines SyntheticUserConfig (flows, mode), EnvironmentConfig, RunRecord, ExecutionReport (audit, network_summary), and traffic-light contracts.")
        Container(executor, "Playwright Executor", "Python / Playwright", "Runs the closed flow catalog (checkout + journey flows, full_journey composition) across mobile-CO, desktop-CO, and desktop-EC. Hosts network capture and dimension data collection.")
        Container(netcapture, "Network Capture", "Playwright listeners / CDP", "HAR-style trace (allowlist, redacted, no bodies), SFRA controller timings, Core Web Vitals per key page.")
        Container(baseline, "Baseline Manager", "Python", "Calculates p95, bootstrap mode, and traffic-light performance decisions. Gate-mode runs only.")
        Container(reporter, "Reporter", "Python", "Produces structured JSON and human-readable Markdown reports; embeds audit findings and network summary.")
        Container(translator, "NL Translator", "Anthropic SDK", "Pre-run NL to SyntheticUserConfig with strict validation and preview. Primary UX entry; never the executor's input.")
        Container(auditAgent, "Audit Synthesis Agent", "Anthropic SDK", "Post-run synthesis of deterministic findings into the 6-dimension audit document. Sanitized input; never decides the traffic light (P7).")
    }

    Rel(engineer, dashboard, "Uses", "Browser")
    Rel(techLead, dashboard, "Reviews gate and history", "Browser")
    Rel(cicdAgent, api, "Reads latest gate-mode run and run detail", "REST /v1")

    Rel(dashboard, api, "Translates NL, launches runs, polls status, reads history and audit", "HTTPS /v1")
    Rel(api, translator, "Translates NL to validated config preview", "Python adapter")
    Rel(api, models, "Validates request/response contracts", "Python imports")
    Rel(api, executor, "Starts profile/flow execution (expanded full_journey)", "async function calls")
    Rel(executor, netcapture, "Captures per profile-flow", "in-process listeners")
    Rel(api, baseline, "Reads and writes baseline/run history (gate mode only)", "Protocol interface")
    Rel(api, reporter, "Builds final report", "Python function calls")
    Rel(reporter, auditAgent, "Requests synthesis over sanitized findings (graceful degradation)", "Python adapter")

    Rel(executor, sfccStorefront, "Executes journey and checkout flows; payment failure validation", "Playwright")
    Rel(api, secretsManager, "Fetches env_access and shopper secrets", "AWS SDK")
    Rel(api, dynamoDb, "Stores environments and run records", "AWS SDK")
    Rel(baseline, dynamoDb, "Reads successful historical gate runs for p95", "AWS SDK")
    Rel(api, s3, "Stores/proxies evidence, HAR traces, audit documents", "AWS SDK")
    Rel(translator, anthropic, "Model calls (pre-run)", "HTTPS")
    Rel(auditAgent, anthropic, "Model calls (post-run, token-budgeted)", "HTTPS")
```

### Level 2 Notes

- The API is the integration hub. Dashboard and downstream agents should consume `/v1/*`; they should not read storage directly.
- `Shared Models` protect downstream agents from schema drift. Any field change in `specs/` remains a contract concern (now at v2 — HITL approved 2026-06-03).
- `Baseline Manager` is intentionally isolated from the executor so Playwright code never writes directly to DynamoDB. Only gate-mode runs feed it (C11).
- `Playwright Executor` only handles browser behavior, step results, and raw data capture (prices, URLs, network, console). It does not own reporting, baseline, audit synthesis, or persistence decisions.
- `NL Translator` and `Audit Synthesis Agent` are the only two Claude API touchpoints, on opposite sides of the run: translator pre-run (validated, previewed, confirmed), audit agent post-run (sanitized findings in, prose out). Neither can alter the traffic light or reach the storefront.
- `full_journey` is expanded by the API/FlowCatalog before execution — the executor only ever sees modular flows.

## Validation Notes

| Concern | Architectural Answer |
|---|---|
| Release decision must be fast | Three critical profiles run in parallel behind the API/orchestrator. |
| Checkout must not create orders | Payment failure is an invariant of executor flows and is asserted by reporter/API layers. Journey flows contain no payment steps at all. |
| Credentials must not leak | Payload carries `environment_id`; API resolves secrets from Secrets Manager and redacts logs. HAR traces persist metadata+timings only, with auth headers/cookies redacted. |
| Reports must be agent-readable | `ExecutionReport` is a typed contract emitted as JSON under `/v1` (v2). |
| SFCC selector fragility | Selectors are centralized in `src/executor/selectors.py`; future auto-healing remains outside MVP. |
| Baseline must avoid false yellows | Bootstrap mode blocks yellow performance alerts until 14 successful runs exist — per profile-flow pair, so each new catalog flow bootstraps independently. |
| LLM must not produce false verdicts | P7/C10: the audit agent synthesizes over deterministic findings and cannot move the traffic light; the NL translator output is schema+catalog validated with user-confirmed preview before any browser launches. |
| Exploration must not pollute the gate | `mode=exploratory` runs never enter the baseline and are excluded from `/v1/runs/latest` gate decisions. |
| Audit evidence must not explode cost | ADR-003: findings-driven captures only (finding or declared critical point); C4 cost KPI watched; S3 lifecycle 90d → Glacier. |
