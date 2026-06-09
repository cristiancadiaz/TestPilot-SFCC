"""API exception hierarchy for TestPilot SFCC — U4 (error-taxonomy.md §5).

A single ``TestPilotApiError`` base is mapped to an HTTP response by the exception
handler in ``src.api.app``. Each subclass fixes its ``status_code`` and
``error_code``. The response body (error-taxonomy §3) NEVER includes stack traces,
server paths, secret values or auth headers.
"""

from __future__ import annotations


class TestPilotApiError(Exception):
    """Base for all HTTP-mappable API errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        message: str = "",
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message or self.error_code)
        self.message = message or self.error_code
        self.details = details


class UnauthorizedError(TestPilotApiError):
    status_code = 401
    error_code = "unauthorized"


class EnvironmentNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "environment_not_found"


class EnvironmentInactiveError(TestPilotApiError):
    status_code = 409
    error_code = "environment_inactive"


class EnvironmentAlreadyExistsError(TestPilotApiError):
    status_code = 409
    error_code = "environment_already_exists"


class SecretNotFoundError(TestPilotApiError):
    status_code = 502
    error_code = "secret_not_found"


class InvalidSecretPathError(TestPilotApiError):
    status_code = 422
    error_code = "invalid_secret_path"


class ValidationFailedError(TestPilotApiError):
    status_code = 422
    error_code = "validation_failed"


class RunNotFoundError(TestPilotApiError):
    status_code = 404
    error_code = "run_not_found"


class ScreenshotNotFoundError(TestPilotApiError):
    # Additive to error-taxonomy.md (§8 process) for the evidence endpoint (U4 Phase C).
    status_code = 404
    error_code = "screenshot_not_found"


class NoRunsYetError(TestPilotApiError):
    status_code = 404
    error_code = "no_runs_yet"


class RunTimeoutError(TestPilotApiError):
    status_code = 504
    error_code = "run_timeout"


class InvariantViolatedError(TestPilotApiError):
    """``orders_created != 0`` — critical incident (CRITICAL log + alert metric)."""

    status_code = 500
    error_code = "invariant_violated"


class RateLimitedError(TestPilotApiError):
    """HTTP 429 when the daily run cap is exceeded (D-U8-5)."""

    status_code = 429
    error_code = "rate_limited"


class InstructionRejectedError(TestPilotApiError):
    """Returned when a translator-proposed instruction/config is rejected
    (out-of-catalog or prompt-injection detection)."""

    status_code = 422
    error_code = "instruction_rejected"
