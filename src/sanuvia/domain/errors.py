"""Domain-level errors.

These signal violations of reasoning invariants — they are part of the domain
contract, not infrastructure failures. They must never be raised to *coerce* a
result; they exist to make illegal states unrepresentable.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain invariant violations."""


class InvariantViolation(DomainError):
    """A reasoning-object invariant was violated (e.g. an out-of-range
    uncertainty, or an Inquiry that references neither evidence nor a
    hypothesis)."""


class EvidenceInferenceConflation(DomainError):
    """Raised when code attempts to treat an InferenceRecord as an
    EvidenceRecord, or to re-ingest a system-derived inference as fresh
    evidence.

    This is the structural guarantee behind the Blueprint's rule that the
    system must never treat its own conclusions as proof (FR-EM-005). It should
    almost never be reachable at runtime — the type system is the first line of
    defence — but it exists so the boundary is enforced even against
    dynamically-typed callers.
    """


class NotYetSpecified(DomainError):
    """Raised by interfaces for transition functions that the frozen
    specification deliberately leaves unresolved (e.g. recognition-condition
    computation, revision escalation, inquiry reopening thresholds).

    Phase 0 represents the affected objects as *data*; the governing
    computation is not implemented and must not be faked. Calling such an
    interface is a programming error in Phase 0, hence an explicit failure
    rather than a silent default.
    """


# --- Governed failure outcomes (Technical Design v1.5.4 §4) -------------------
#
# Locked Architecture §3.10 lists thirteen provisional outcome names and assigns
# final classification and naming to the technical design. §4 of the design keeps
# all thirteen and adds INVALID_APPRAISAL_RESPONSE under that delegation (R8).
#
# These are *governed outcomes*, not exceptions in the ordinary sense: each one
# rejects a complete plan before mutation (class T), parks a candidate without
# committing (V/R), or withholds an inquiry while the rest of the plan commits
# (W). None may be repaired, retried, dropped or silently normalised.

from enum import Enum


class GovernedOutcome(Enum):
    """The governed failure outcomes (§4). Fourteen names, no more."""

    UNKNOWN_EVIDENCE_REFERENCE = "UNKNOWN_EVIDENCE_REFERENCE"
    UNKNOWN_HYPOTHESIS_REFERENCE = "UNKNOWN_HYPOTHESIS_REFERENCE"
    DUPLICATE_HYPOTHESIS_PROPOSAL = "DUPLICATE_HYPOTHESIS_PROPOSAL"
    AMBIGUOUS_HYPOTHESIS_IDENTITY = "AMBIGUOUS_HYPOTHESIS_IDENTITY"
    EVIDENCE_ROLE_VIOLATION = "EVIDENCE_ROLE_VIOLATION"
    ACCOUNT_ROLE_UPGRADE_VIOLATION = "ACCOUNT_ROLE_UPGRADE_VIOLATION"
    INVALID_CONTRADICTION_PLAN = "INVALID_CONTRADICTION_PLAN"
    INVALID_DIVERGENCE_PLAN = "INVALID_DIVERGENCE_PLAN"
    INVALID_INQUIRY_EQUIVALENT_OPTIONS = "INVALID_INQUIRY_EQUIVALENT_OPTIONS"
    INVALID_INQUIRY_NO_REVISION_PATH = "INVALID_INQUIRY_NO_REVISION_PATH"
    STATEMENT_CAPTURE_FAILURE = "STATEMENT_CAPTURE_FAILURE"
    SOURCE_REFERENCE_MAPPING_FAILURE = "SOURCE_REFERENCE_MAPPING_FAILURE"
    NON_ATOMIC_REVISION_PLAN = "NON_ATOMIC_REVISION_PLAN"
    INVALID_APPRAISAL_RESPONSE = "INVALID_APPRAISAL_RESPONSE"


class ModelBoundary(Enum):
    """Required discriminator on INVALID_APPRAISAL_RESPONSE (§4, F-7).

    The outcome covers two model boundaries, so its audit payload must say which
    one was crossed — the same principle as ``BreachKind`` below.
    """

    APPRAISAL = "APPRAISAL"
    IDENTITY_RESOLVER = "IDENTITY_RESOLVER"


class BreachKind(Enum):
    """Required discriminator on NON_ATOMIC_REVISION_PLAN (§4).

    ``ADJUDICATION_ORDER`` is raised pre-mutation at check 3a and implies **no**
    failing write; ``COMMIT_ATOMICITY`` is raised inside the commit region and
    carries the failing write and the restored-state assertion.
    """

    ADJUDICATION_ORDER = "ADJUDICATION_ORDER"
    COMMIT_ATOMICITY = "COMMIT_ATOMICITY"


class GovernedRejection(DomainError):
    """A governed outcome that rejects the complete plan before mutation.

    Carries the outcome, the discriminators where the outcome requires them, and
    a diagnostic payload. It is never repaired and never retried: the caller
    restores the UnitOfWork and emits the rejected-plan audit record.

    The diagnostic payload is audit only. Nothing here affects whether or how
    the plan is rejected, and nothing here is read by the reasoning path.
    """

    def __init__(
        self,
        outcome: GovernedOutcome,
        detail: str = "",
        *,
        boundary: "ModelBoundary | None" = None,
        breach_kind: "BreachKind | None" = None,
        references: tuple[str, ...] = (),
        raw_response: str | None = None,
        appraisal_responses: tuple[tuple[str, str | None], ...] = (),
    ) -> None:
        if outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE and boundary is None:
            raise InvariantViolation(
                "INVALID_APPRAISAL_RESPONSE requires a boundary discriminator (§4, F-7)"
            )
        if outcome is GovernedOutcome.NON_ATOMIC_REVISION_PLAN and breach_kind is None:
            raise InvariantViolation(
                "NON_ATOMIC_REVISION_PLAN requires a breach_kind discriminator (§4)"
            )
        self.outcome = outcome
        self.detail = detail
        self.boundary = boundary
        self.breach_kind = breach_kind
        self.references = references
        #: The failing call's raw appraiser response, where an appraisal call
        #: occurred (F-15). ``None`` where none did, or on the Scripted path,
        #: which produces no raw response by construction.
        self.raw_response = raw_response
        #: Every appraisal response collected for this interaction, in call
        #: order, each attributed to the observation it answered:
        #: ``((evidence_id, raw_response), ...)``.
        #:
        #: §5.8 requires the rejected-plan audit to carry "the raw appraiser
        #: response" for the interaction. An interaction may admit several
        #: observations and make an appraisal call for each, so a single field
        #: cannot represent it: a later record's rejection would discard the
        #: responses already collected for the earlier ones. This keeps them,
        #: ordered and attributable, so a reviewer can see what the appraiser
        #: returned across the whole interaction, including the failing call.
        self.appraisal_responses = appraisal_responses
        super().__init__(f"{outcome.value}: {detail}" if detail else outcome.value)
