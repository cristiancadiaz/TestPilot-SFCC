"""Unified Pydantic models for TestPilot SFCC — the single source of truth.

This module mirrors the JSON Schema contracts under ``specs/`` (v2) exactly:

- ``specs/synthetic-user-config.schema.json`` — request body of ``POST /v1/run``.
- ``specs/execution_report.schema.json``       — response of ``POST /v1/run``.

The schemas are the authoritative contract (breaking-change-sensitive, HITL).
These models intentionally mirror schema **v2** (scope realignment 2026-06-03):
journey flows + ``full_journey`` composition alias + ``mode`` (gate|exploratory).

Scope notes (U0, wave 1):
- The ``audit`` and ``network_summary`` objects of the report v2 are NOT modeled
  here — they are added by U6 (audit) and U7 (network capture). U0 models the
  minimum viable report of wave 1 plus the required ``mode`` field.
- ``orders_created`` is an INTERNAL invariant field (always 0). The contract does
  not publish it (``additionalProperties: false``), so it is excluded from
  serialization via ``Field(exclude=True)`` while staying accessible as an
  attribute (BR-U3-01 asserts it internally; the Markdown report documents it).
- Credentials (env access / shopper) are resolved server-side from Secrets
  Manager and never travel in this contract — they are modeled in U4, not here.

See ``CLAUDE.md`` § Hard Invariants 1 (zero contamination), 2 (closed flow
catalog), 3 (JSON Schema gate).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# --------------------------------------------------------------------------------
# Closed catalogs (snake_case enum values — mirror specs/ v2 exactly, invariant #2)
# --------------------------------------------------------------------------------

EnvironmentId = Literal["sandbox", "development", "staging"]
"""Target SFCC environment. ``production`` is impossible by construction."""

# Flow values accepted in the request config (7 — includes the full_journey alias).
FlowSelection = Literal[
    "checkout_full",
    "checkout_card_declined",
    "search_and_filter",
    "browse_discounted_products",
    "pdp_validation",
    "cart_review",
    "full_journey",
]

# Flow values that appear in a result (6 — NEVER full_journey: the report always
# shows the EXPANDED composition, one FlowResult per modular flow, H6.3 AC4).
FlowName = Literal[
    "checkout_full",
    "checkout_card_declined",
    "search_and_filter",
    "browse_discounted_products",
    "pdp_validation",
    "cart_review",
]

ProfileId = Literal["mobile_co", "desktop_co", "desktop_ec"]

Mode = Literal["gate", "exploratory"]

AuditDimension = Literal[
    "commerce_integrity",
    "performance",
    "locale_correctness",
    "accessibility",
    "client_health",
    "content_integrity",
]


# --------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------


class TrafficLight(str, Enum):
    """Deterministic deploy verdict. Computed by the p95 rule only (P7/C10)."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


# --------------------------------------------------------------------------------
# Request contract: SyntheticUserConfig (mirrors synthetic-user-config.schema.json v2)
# --------------------------------------------------------------------------------


class Product(BaseModel):
    """A product the synthetic shopper will search for and add to the cart."""

    model_config = ConfigDict(extra="forbid")

    search_term: str = Field(min_length=2, max_length=128)
    validate_variant: bool = True


class RunOptions(BaseModel):
    """Optional run tuning. ``capture_intermediate_screenshots`` is a cost invariant."""

    model_config = ConfigDict(extra="forbid")

    timeout_seconds: int = Field(default=180, ge=30, le=600)
    # Cost invariant (ADR-003): always False. Permitting True would blow the S3
    # budget (~500 MB → ~17 GB/month). Literal[False] enforces the schema const.
    capture_intermediate_screenshots: Literal[False] = False


class SyntheticUserConfig(BaseModel):
    """Validated input of ``POST /v1/run`` — mirrors the v2 schema exactly.

    The NL instruction never reaches the executor; only this validated,
    user-confirmed config does (C12).
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["v2"] = "v2"
    environment_id: EnvironmentId
    flows: list[FlowSelection] = Field(min_length=1, max_length=6)
    mode: Mode = "gate"
    profiles: list[ProfileId] = Field(min_length=1, max_length=3)
    products: list[Product] = Field(min_length=1, max_length=10)
    options: RunOptions | None = None

    @field_validator("flows", "profiles")
    @classmethod
    def _unique_items(cls, value: list[str]) -> list[str]:
        """Enforce ``uniqueItems: true`` from the schema."""
        if len(value) != len(set(value)):
            raise ValueError("items must be unique")
        return value


# --------------------------------------------------------------------------------
# Response contract: ExecutionReport (mirrors execution_report.schema.json v2)
# --------------------------------------------------------------------------------


class BrowserProfile(BaseModel):
    """Resolved synthetic profile: device + country."""

    model_config = ConfigDict(extra="forbid")

    name: ProfileId
    viewport_width: int = Field(ge=320)
    viewport_height: int = Field(ge=480)
    locale: str = Field(min_length=2, max_length=10)
    user_agent: str = Field(min_length=10)
    is_mobile: bool


class StepResult(BaseModel):
    """One step within a flow execution."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["success", "failed", "skipped"]
    # 'setup' for auto-preparation steps of a modular flow in single-module mode
    # (their failure is a precondition error, not a failure of the module under
    # test); 'flow' for the flow proper (H6.2 AC3).
    phase: Literal["setup", "flow"] = "flow"
    duration_ms: int = Field(ge=0)
    error: str | None = None
    screenshot_url: str | None = None
    # Findings-driven evidence (RF-26 / ADR-003): 'fail' and 'final' in all modes;
    # 'finding' (one of the 6 dimensions) and 'critical' (FlowCatalog critical
    # point) only in audit mode. Never capture a clean OK step.
    screenshot_state: Literal["fail", "final", "finding", "critical"] | None = None
    # Present only when screenshot_state == 'finding'.
    finding_dimension: AuditDimension | None = None


class FlowResult(BaseModel):
    """Result of one executed flow (never the full_journey alias)."""

    model_config = ConfigDict(extra="forbid")

    flow_name: FlowName
    status: Literal["success", "failed", "error"]
    steps: list[StepResult] = Field(min_length=1)
    duration_ms: int = Field(ge=0)
    # Zero-contamination invariant: always 0. Internal — not published in the JSON
    # contract (additionalProperties: false); excluded from model_dump().
    orders_created: int = Field(default=0, exclude=True)


class ProfileResult(BaseModel):
    """Result for one profile × flow combination."""

    model_config = ConfigDict(extra="forbid")

    profile: BrowserProfile
    flow_result: FlowResult
    traffic_light: TrafficLight


class BaselineComparison(BaseModel):
    """Comparison of the current run against the p95 baseline."""

    model_config = ConfigDict(extra="forbid")

    p95_ms: int = Field(ge=0)
    current_ms: int = Field(ge=0)
    bootstrap_mode: bool
    runs_count: int = Field(ge=0)


class RunRecord(BaseModel):
    """Flattened per-combination record persisted to DynamoDB (via src/baseline/)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    environment_id: EnvironmentId
    profile_name: ProfileId
    flow_name: FlowName
    duration_ms: int = Field(ge=0)
    status: Literal["success", "failed", "error"]
    created_at: datetime


class ExecutionReport(BaseModel):
    """Output of ``POST /v1/run`` — minimum viable report of wave 1 + mode.

    The ``audit`` and ``network_summary`` objects of report v2 are deferred to
    U6/U7. ``run_id`` mirrors the schema field name (the task text said
    ``test_run_id``, but the published contract uses ``run_id`` — schema wins).
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    environment_id: EnvironmentId
    mode: Mode
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    traffic_light: TrafficLight
    bootstrap_mode: bool
    profile_results: list[ProfileResult] = Field(min_length=1)
    baseline_comparison: BaselineComparison | None = None
    # Zero-contamination invariant: always 0. Internal — excluded from model_dump().
    orders_created: int = Field(default=0, exclude=True)
