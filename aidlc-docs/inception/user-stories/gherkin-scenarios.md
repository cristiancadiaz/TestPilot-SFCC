# Gherkin Scenarios - TestPilot SFCC

> Station 4 critical artifact. These scenarios formalize representative acceptance paths from `user-stories.md` using verifiable Given/When/Then criteria.

## Scope

The scenarios cover the MVP paths that matter most for release confidence:

- Environment registration without exposing secrets.
- Running synthetic checkout flows from structured config.
- Preventing real order contamination.
- Allowing CI/CD agents to consume the latest deploy-gate result.
- Keeping performance alerts honest during baseline bootstrap.

## Feature: Environment Registry

### Scenario: Register staging environment with secret paths only

```gherkin
Feature: Environment Registry
  As a Tech Lead
  I want to register SFCC environments by secret path
  So that TestPilot can run checkout tests without exposing credentials in payloads

  Scenario: Register staging environment with secret paths only
    Given an authenticated engineer opens the environments screen
    And the engineer enters environment_id "staging"
    And the engineer enters store_url "https://staging.example.com"
    And the engineer enters env_access_secret_path "testpilot/staging/env-access"
    And the engineer enters shopper_secret_path "testpilot/staging/shopper"
    When the engineer saves the environment
    Then the API stores the environment config
    And the API response does not include secret values
    And the dashboard displays only the configured secret paths
```

### Scenario: Reject environment payload containing credential values

```gherkin
Feature: Environment Registry

  Scenario: Reject environment payload containing credential values
    Given an authenticated engineer prepares an environment payload
    And the payload includes a field named "password"
    When the engineer sends the payload to POST /v1/environments
    Then the API returns a validation error
    And no environment record is created
    And no credential value is written to logs
```

## Feature: Structured Run Execution

### Scenario: Launch checkout run with structured SyntheticUserConfig

```gherkin
Feature: Structured Run Execution
  As an SFCC engineer
  I want to launch a run using structured config
  So that the release gate is deterministic and auditable

  Scenario: Launch checkout run with structured SyntheticUserConfig
    Given environment_id "staging" is registered and active
    And Secrets Manager contains env_access credentials for "testpilot/staging/env-access"
    And Secrets Manager contains shopper credentials for "testpilot/staging/shopper"
    And the shopper email ends with "@testpilot.internal"
    When the engineer sends POST /v1/run with flows "checkout-full" and "checkout-card-declined"
    And profiles "mobile-co", "desktop-co", and "desktop-ec"
    Then the API validates the SyntheticUserConfig before execution
    And the API resolves storefront and credentials server-side
    And the executor starts one run per requested profile and flow
    And the response includes a testRunId
```

### Scenario: Reject run config with unsupported flow

```gherkin
Feature: Structured Run Execution

  Scenario: Reject run config with unsupported flow
    Given environment_id "staging" is registered and active
    And the run payload includes flow "return-order"
    When the engineer sends POST /v1/run
    Then the API returns a validation error
    And no browser session is launched
    And no run record is saved
```

## Feature: Zero Order Contamination

### Scenario: Checkout flow fails payment by design and creates no order

```gherkin
Feature: Zero Order Contamination
  As a Tech Lead
  I want synthetic checkout tests to never create real orders
  So that staging reports and shopper data stay clean

  Scenario: Checkout flow fails payment by design and creates no order
    Given a valid run is executing against environment_id "staging"
    And the shopper email ends with "@testpilot.internal"
    When the checkout flow reaches payment validation
    Then the payment is declined by design
    And FlowResult.orders_created equals 0
    And the report generator asserts orders_created equals 0
    And the final ExecutionReport can be emitted
```

### Scenario: Block report generation if an order is detected

```gherkin
Feature: Zero Order Contamination

  Scenario: Block report generation if an order is detected
    Given a ProfileResult contains FlowResult.orders_created equal to 1
    When the report generator processes the profile result
    Then report generation fails with an invariant violation
    And the run is marked as failed
    And the Markdown report highlights the contamination risk
```

## Feature: CI/CD Deploy Gate Consumption

### Scenario: CI/CD agent reads latest fresh green report

```gherkin
Feature: CI/CD Deploy Gate Consumption
  As a CI/CD agent
  I want to read the latest structured report
  So that I can make an automated deploy decision

  Scenario: CI/CD agent reads latest fresh green report
    Given a successful run exists with trafficLight "green"
    And the run finished less than 4 hours ago
    When the CI/CD agent sends GET /v1/runs/latest with a valid API key
    Then the API returns status 200
    And the response includes trafficLight "green"
    And the response includes ttlOk true
    And the response schema matches ExecutionReport
```

### Scenario: CI/CD agent cannot read latest report without API key

```gherkin
Feature: CI/CD Deploy Gate Consumption

  Scenario: CI/CD agent cannot read latest report without API key
    Given at least one run exists
    When the CI/CD agent sends GET /v1/runs/latest without X-API-Key
    Then the API returns status 401
    And the response does not reveal whether any run exists
```

## Feature: Baseline Bootstrap

### Scenario: Bootstrap mode prevents yellow performance alerts

```gherkin
Feature: Baseline Bootstrap
  As a Tech Lead
  I want performance alerts to wait for enough baseline data
  So that the team does not lose trust due to early false positives

  Scenario: Bootstrap mode prevents yellow performance alerts
    Given there are 13 successful historical runs for profile "mobile-co" and flow "checkout-full"
    And the current run is slower than the preliminary p95
    When the baseline manager computes the traffic light
    Then bootstrapMode is true
    And the traffic light is "green"
    And the Markdown report includes a bootstrap disclaimer
```

### Scenario: Baseline uses only successful runs for p95

```gherkin
Feature: Baseline Bootstrap

  Scenario: Baseline uses only successful runs for p95
    Given historical runs include statuses "success", "failed", and "error"
    When the baseline manager calculates p95
    Then only runs with status "success" are included
    And failed or error runs do not affect the baseline
```

## Traceability

| Feature | Source Stories | Verification Surface |
|---|---|---|
| Environment Registry | H5.1 | API validation, dashboard rendering, log redaction |
| Structured Run Execution | H4.1, H1.1 | POST /v1/run tests, schema validation |
| Zero Order Contamination | H1.2, H3.3 | FlowResult assertions, reporter tests |
| CI/CD Deploy Gate Consumption | H4.2, H4.3, H4.4 | GET /v1/runs/latest tests |
| Baseline Bootstrap | H2.2, H2.4 | Baseline unit tests and PBT |
