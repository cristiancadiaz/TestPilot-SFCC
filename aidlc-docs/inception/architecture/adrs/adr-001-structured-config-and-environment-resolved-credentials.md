# ADR-001: Structured Run Config And Environment-Resolved Credentials

## Status

Accepted

## Date

2026-05-27

## Context

TestPilot SFCC runs synthetic checkout flows against SFCC/SFRA environments. Each run needs:

- A target environment: `sandbox`, `development`, or `staging`.
- A storefront URL.
- Environment access credentials, such as HTTP Basic Auth or proxy gate credentials.
- Shopper credentials for a registered SFCC customer using the `@testpilot.internal` domain.
- Product, flow, profile, and screenshot options.

The original product direction included an AI translator for natural language to config. That remains useful, but a release gate must be deterministic and auditable. SFCC checkout automation also touches sensitive areas: login, cart, payment failure validation, order creation prevention, and potentially protected staging storefronts.

From an SFCC ecommerce product ownership perspective, the critical risk is not only whether the agent can launch a browser. The critical risk is whether a release-blocking system can be trusted by engineers, Tech Leads, and downstream CI/CD agents without leaking credentials or running against the wrong environment.

## Decision

`POST /v1/run` will receive a structured `SyntheticUserConfig` payload as the primary MVP entry point.

The payload must include `environment_id`, products, flows, profiles, and run options. It must not include:

- Storefront URLs.
- Environment access usernames or passwords.
- Shopper emails or passwords.
- Payment credentials.

The backend resolves `environment_id` through the Environment Registry and Secrets Manager:

1. Look up `EnvironmentConfig`.
2. Resolve `env_access_credentials` from `testpilot/{env}/env-access`.
3. Resolve `shopper_credentials` from `testpilot/{env}/shopper`.
4. Execute Playwright flows using the resolved environment and credentials.

Natural-language translation can remain as an optional adapter, but it is not the release-gate contract for MVP execution.

## Consequences

### Positive

- The API contract is stable and machine-readable for downstream agents.
- CI/CD consumers can validate payloads before invoking a run.
- Credentials never travel in request bodies, browser clients, or CI/CD logs.
- Environment selection is auditable through `environment_id`.
- It becomes harder to accidentally run checkout tests against the wrong storefront.
- The dashboard can validate JSON before sending a run request.
- The LLM is removed from the critical path for deterministic deploy gating.

### Negative

- The first user experience is less conversational than a pure natural-language interface.
- The dashboard must provide a JSON editor or structured form.
- A separate translator endpoint or helper flow is needed if the team wants NL authoring later.
- Product and QA users need to understand the closed catalog of flows and profiles.

## Alternatives Considered

### Natural Language As Primary Input

The user describes the run in natural language and the backend translates it through Claude before execution.

Rejected for MVP release gating because translation ambiguity can create false confidence. For example, "run checkout for mobile Colombia with declined payment" has several interpretations: product choice, decline timing, profile mapping, and expected validation text.

### Credentials In The Payload

The dashboard or CI/CD agent sends `storefront_url`, shopper email, password, and environment access credentials in each run request.

Rejected because it increases the chance of leaking credentials through logs, browser history, request captures, CI/CD traces, or copied JSON fixtures.

### Hardcoded Staging Environment

The MVP only supports one staging URL and one shopper account, hardcoded in environment variables.

Rejected because TestPilot must support sandbox, development, and staging from the start. Hardcoding would make environment drift invisible and would block the dashboard environment registry.

## Verification

This decision is verified when:

- `SyntheticUserConfig` has `environment_id` but no credential or storefront URL fields.
- API validation rejects unknown fields in run requests.
- Environment credentials are resolved server-side through Secrets Manager.
- Logs redact secret paths and any values matching password, token, card, or key patterns.
- Tests confirm that valid run payloads contain no shopper email or password.
- Tests confirm that missing or inactive `environment_id` returns a typed API error.

## Related Artifacts

- `specs/prd.md`
- `specs/synthetic-user-config.schema.json`
- `aidlc-docs/inception/requirements/requirements.md`
- `aidlc-docs/inception/application-design/components.md`
- `aidlc-docs/inception/application-design/services.md`
- `aidlc-docs/inception/application-design/env-vars-catalog.md`
- `aidlc-docs/inception/application-design/error-taxonomy.md`
- `aidlc-docs/inception/architecture/c4-diagrams.md`
