# ADR-002: Screenshot Capture Policy

## Status

Accepted

## Date

2026-05-27

## Context

Some AI-DLC and PRD-derived artifacts proposed capturing screenshots for every checkout module in both OK and FAIL states. That policy increases visual evidence, but it conflicts with the repository operating constraint in `AGENTS.md`: screenshots only on failure plus the final step.

The same constraint exists for cost and usability reasons. Capturing each step would grow S3 usage and create a large review surface. TestPilot SFCC needs evidence that helps engineers decide quickly whether a release is safe; it should not generate visual noise that slows review.

## Decision

The MVP screenshot policy is:

- Capture a screenshot when a step fails.
- Capture a screenshot for the final step of each executed flow.
- Do not capture screenshots for successful intermediate steps.
- Do not expose `screenshot_on_success` as a normal run-time option for MVP.
- Keep screenshot storage behind S3 or local `SCREENSHOT_DIR`, depending on environment.

This ADR aligns AI-DLC Inception artifacts with `AGENTS.md`.

## Consequences

### Positive

- Lower S3 storage and transfer cost.
- Lower cognitive load when engineers review reports.
- Less risk of storing unnecessary storefront/session visual data.
- Screenshot evidence stays focused on failures and final proof of flow completion.

### Negative

- The dashboard cannot show a complete visual replay of every successful step in MVP.
- Some visual regressions on successful intermediate steps may require trace/log review instead of screenshot review.
- Full visual replay requires a separate ADR and cost review.

## Verification

This decision is verified when:

- `SyntheticUserConfig` does not expose `screenshot_on_success` as a regular configurable field.
- The executor captures screenshots only for failed steps and final flow steps.
- Tests assert that a successful multi-step flow produces only the final screenshot.
- Tests assert that a failed step captures a screenshot.
- Documentation does not describe OK + FAIL screenshots for every module as the MVP implementation policy.

## Related Artifacts

- `AGENTS.md`
- `README.md`
- `specs/synthetic-user-config.schema.json`
- `aidlc-docs/inception/requirements/requirements.md`
- `aidlc-docs/inception/user-stories/user-stories.md`
- `aidlc-docs/inception/application-design/components.md`
- `aidlc-docs/inception/application-design/unit-of-work.md`
