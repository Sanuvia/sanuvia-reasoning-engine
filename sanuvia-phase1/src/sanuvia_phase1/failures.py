"""Phase 1 failure taxonomy — typed outcomes for the external model boundaries.

A single real (non-golden) model call has exactly one terminal outcome. When a
call fails we NEVER substitute a semantic value (no empty evidence, no default
confidence, no fabricated uncertainty); the failure is recorded and propagates.
A failed model call remains a failed model call.

These types are shared by the external adapters (`evidence_extractors`,
`evidence_appraisers`, `language_models`), the strict `validation` layer, the
`runconfig` guard, and the run `manifest`. Nothing here imports Phase 0, chooses
a provider, or performs I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CallStatus(str, Enum):
    """The terminal status of one external model call. Exactly these six."""

    SUCCESS = "success"
    MALFORMED_OUTPUT = "malformed_output"
    MODEL_ERROR = "model_error"
    TIMEOUT = "timeout"
    RETRY_EXHAUSTED = "retry_exhausted"
    CONFIGURATION_ERROR = "configuration_error"


class BoundaryKind(str, Enum):
    """Which external boundary a call/failure belongs to."""

    EVIDENCE_EXTRACTION = "evidence_extraction"
    EVIDENCE_APPRAISAL = "evidence_appraisal"
    STATELESS_BASELINE = "stateless_baseline"
    TRANSCRIPT_BASELINE = "transcript_baseline"


class Availability(str, Enum):
    """Why a manifest field has (or lacks) a value.

    Distinguishes an honestly-absent value from an invented one, and — crucially —
    "the provider does not expose this" from "our system did not capture it"."""

    AVAILABLE = "available"
    NOT_PROVIDED_BY_PROVIDER = "not_provided_by_provider"
    NOT_CAPTURED = "not_captured"


@dataclass(frozen=True, slots=True)
class Maybe:
    """A manifest value that may be unavailable for a stated, honest reason.

    ``value`` is always a string when ``availability`` is ``AVAILABLE`` and always
    ``None`` otherwise — we never render a placeholder as if it were real."""

    availability: Availability
    value: str | None = None

    @staticmethod
    def available(value: str) -> "Maybe":
        return Maybe(Availability.AVAILABLE, value)

    @staticmethod
    def not_provided_by_provider() -> "Maybe":
        return Maybe(Availability.NOT_PROVIDED_BY_PROVIDER, None)

    @staticmethod
    def not_captured() -> "Maybe":
        return Maybe(Availability.NOT_CAPTURED, None)

    def to_payload(self) -> dict[str, str | None]:
        return {"availability": self.availability.value, "value": self.value}


# --- exceptions ---------------------------------------------------------------


class Phase1Error(Exception):
    """Base class for all Phase 1 hardening errors."""


class ConfigurationError(Phase1Error):
    """A run was mis-configured (e.g. REAL mode with a scripted double, or a
    missing REAL configuration). Raised BEFORE any execution begins."""


class MalformedOutputError(Phase1Error):
    """A model returned output that does not satisfy the expected schema.

    The raw text (if any) is preserved so a reviewer can audit exactly what came
    back. We raise rather than coerce the reply into a default/empty value."""

    def __init__(
        self, boundary: BoundaryKind, detail: str, raw: str | None = None
    ) -> None:
        super().__init__(detail)
        self.boundary = boundary
        self.detail = detail
        self.raw = raw


class ModelError(Phase1Error):
    """The model/provider call itself failed (transport, provider error, etc.).

    Real client adapters raise this (or a subclass) so failures are typed rather
    than leaking arbitrary provider exceptions across the boundary."""


class ModelTimeout(ModelError):
    """The model/provider call exceeded its time budget."""


class RetryExhaustedError(Phase1Error):
    """A retryable call failed on every attempt."""

    def __init__(
        self,
        boundary: BoundaryKind,
        attempts: int,
        last_status: CallStatus,
        detail: str,
        raw: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.boundary = boundary
        self.attempts = attempts
        self.last_status = last_status
        self.detail = detail
        self.raw = raw


def classify_exception(exc: BaseException) -> CallStatus:
    """Map a raised exception to its terminal :class:`CallStatus`.

    Order matters: the more specific subclasses are checked first."""
    if isinstance(exc, MalformedOutputError):
        return CallStatus.MALFORMED_OUTPUT
    if isinstance(exc, RetryExhaustedError):
        return CallStatus.RETRY_EXHAUSTED
    if isinstance(exc, ModelTimeout):
        return CallStatus.TIMEOUT
    if isinstance(exc, ConfigurationError):
        return CallStatus.CONFIGURATION_ERROR
    if isinstance(exc, ModelError):
        return CallStatus.MODEL_ERROR
    # An unexpected exception type is treated as a model error, never as success.
    return CallStatus.MODEL_ERROR
