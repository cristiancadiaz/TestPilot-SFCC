# C4 Diagrams - TestPilot SFCC

> Station 4 critical artifact. These diagrams describe the intended MVP architecture for TestPilot SFCC from an ecommerce/SFCC product ownership perspective: release safety, checkout stability, environment isolation, and consumption by both engineers and downstream agents.

## Level 1 - System Context

```mermaid
C4Context
    title TestPilot SFCC - C4 Level 1 System Context

    Person(engineer, "SFCC Engineer", "Launches QA runs before merge/deploy and reviews deploy-gate evidence.")
    Person(techLead, "Tech Lead", "Owns release confidence, quality gates, and operational risk.")
    System_Ext(cicdAgent, "CI/CD or Review Agent", "Consumes latest structured report to decide whether a release is safe.")

    System(testPilot, "TestPilot SFCC", "Internal synthetic QA platform for SFCC storefronts. Runs checkout flows with Playwright, compares against baseline, and emits JSON/Markdown reports with a traffic light.")

    System_Ext(sfccStorefront, "SFCC/SFRA Storefront", "Sandbox, development, or staging storefront under test.")
    System_Ext(secretsManager, "AWS Secrets Manager", "Stores environment access credentials and shopper credentials.")
    System_Ext(dynamoDb, "DynamoDB", "Stores environment registry, run history, and baseline inputs.")
    System_Ext(s3, "Amazon S3", "Stores screenshots and visual evidence.")
    System_Ext(anthropic, "Claude API", "Optional translator/classifier capability. Not the primary run entry point in MVP.")

    Rel(engineer, testPilot, "Registers environments, launches runs, reviews Markdown report", "HTTPS / Dashboard")
    Rel(techLead, testPilot, "Reviews history, baseline, and deploy-gate decisions", "HTTPS / Dashboard")
    Rel(cicdAgent, testPilot, "Reads latest run status and structured report", "REST /v1")

    Rel(testPilot, sfccStorefront, "Runs synthetic checkout flows with env access and shopper login", "Playwright browser")
    Rel(testPilot, secretsManager, "Resolves env_access and shopper credentials by environment_id", "AWS SDK")
    Rel(testPilot, dynamoDb, "Persists environments, runs, and baseline records", "AWS SDK")
    Rel(testPilot, s3, "Stores and retrieves screenshots", "AWS SDK")
    Rel(testPilot, anthropic, "Optional NL translation and error classification", "Anthropic SDK")
```

### Level 1 Notes

- `TestPilot SFCC` is an internal release-confidence system, not a public SaaS.
- The primary business user is the SFCC engineering team that needs a deploy-safe decision in less than 30 minutes.
- The system boundary intentionally excludes SFCC production execution for MVP; the target environments are sandbox, development, and staging.
- Credentials never enter the run payload. `environment_id` is the only selector used to resolve URLs and secrets.

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
        Container(dashboard, "Dashboard Web", "React or static HTML/JS", "Registers environments, launches runs, shows live status, history, screenshots, and deploy-gate result.")
        Container(api, "FastAPI REST API", "Python 3.12 / FastAPI", "Owns /v1 endpoints, auth, validation, orchestration, status, history, and screenshot proxy.")
        Container(models, "Shared Models", "Pydantic + JSON Schema", "Defines SyntheticUserConfig, EnvironmentConfig, RunRecord, ExecutionReport, and traffic-light contracts.")
        Container(executor, "Playwright Executor", "Python / Playwright", "Runs checkout-full and checkout-card-declined across mobile-CO, desktop-CO, and desktop-EC profiles.")
        Container(baseline, "Baseline Manager", "Python", "Calculates p95, bootstrap mode, and traffic-light performance decisions.")
        Container(reporter, "Reporter", "Python", "Produces structured JSON and human-readable Markdown reports.")
        Container(translator, "AI Translator/Classifier", "Anthropic SDK", "Optional adapter for NL to config and future error classification.")
    }

    Rel(engineer, dashboard, "Uses", "Browser")
    Rel(techLead, dashboard, "Reviews gate and history", "Browser")
    Rel(cicdAgent, api, "Reads latest run and run detail", "REST /v1")

    Rel(dashboard, api, "Launches runs, polls status, reads history", "HTTPS /v1")
    Rel(api, models, "Validates request/response contracts", "Python imports")
    Rel(api, executor, "Starts profile/flow execution", "async function calls")
    Rel(api, baseline, "Reads and writes baseline/run history", "Protocol interface")
    Rel(api, reporter, "Builds final report", "Python function calls")
    Rel(api, translator, "Optionally translates/classifies", "Python adapter")

    Rel(executor, sfccStorefront, "Executes login, search, PDP, cart, checkout, payment failure validation", "Playwright")
    Rel(api, secretsManager, "Fetches env_access and shopper secrets", "AWS SDK")
    Rel(api, dynamoDb, "Stores environments and run records", "AWS SDK")
    Rel(baseline, dynamoDb, "Reads successful historical runs for p95", "AWS SDK")
    Rel(api, s3, "Stores/proxies screenshots", "AWS SDK")
    Rel(translator, anthropic, "Optional model calls", "HTTPS")
```

### Level 2 Notes

- The API is the integration hub. Dashboard and downstream agents should consume `/v1/*`; they should not read storage directly.
- `Shared Models` protect downstream agents from schema drift. Any field change in `specs/` remains a contract concern.
- `Baseline Manager` is intentionally isolated from the executor so Playwright code never writes directly to DynamoDB.
- `Playwright Executor` only handles browser behavior and step results. It does not own reporting, baseline, or persistence decisions.
- `AI Translator/Classifier` is optional for MVP execution; structured `SyntheticUserConfig` remains the safest primary entry point.

## Validation Notes

| Concern | Architectural Answer |
|---|---|
| Release decision must be fast | Three critical profiles run in parallel behind the API/orchestrator. |
| Checkout must not create orders | Payment failure is an invariant of executor flows and is asserted by reporter/API layers. |
| Credentials must not leak | Payload carries `environment_id`; API resolves secrets from Secrets Manager and redacts logs. |
| Reports must be agent-readable | `ExecutionReport` is a typed contract emitted as JSON under `/v1`. |
| SFCC selector fragility | Selectors are centralized in `src/executor/selectors.py`; future auto-healing remains outside MVP. |
| Baseline must avoid false yellows | Bootstrap mode blocks yellow performance alerts until 14 successful runs exist. |
