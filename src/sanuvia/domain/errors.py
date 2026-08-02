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
