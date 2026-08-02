"""The six typed uncertainty values.

Implementation Principle (Programme Part 2): *"Uncertainty is six typed values,
not one float."* Collapsing confidence into a single generic number destroys the
ability to reason about *what kind* of not-knowing exists. Each value below is a
**distinct type** so the type checker forbids using one where another is meant;
they are intentionally not interchangeable and never coerced to a bare float.

All six wrap a magnitude in the closed interval ``[0.0, 1.0]``. Their *meaning*
differs (documented per class), which is exactly why they are separate types.

FR references: FR-EM-002 (ProvenanceConfidence), FR-EM-004
(ClassificationConfidence), FR-RS-002/005 (HypothesisSupport), FR-RS-004/005
(PredictionLikelihood), FR-PU-002/004 (ModelUncertainty), plus EvidenceReliability
(RP016 uncertainty set).
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import InvariantViolation


@dataclass(frozen=True, slots=True)
class _UncertaintyValue:
    """Base for a magnitude in ``[0.0, 1.0]``. Not a public type — always use one
    of the six concrete subclasses so the *kind* of uncertainty is explicit.

    Frozen and slotted: uncertainty values are immutable value objects.
    """

    value: float

    def __post_init__(self) -> None:
        # ``bool`` is a subclass of ``int``; reject it explicitly so
        # ``EvidenceReliability(True)`` cannot masquerade as 1.0.
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise InvariantViolation(
                f"{type(self).__name__} must be a real number, got "
                f"{type(self.value).__name__}"
            )
        if not (0.0 <= float(self.value) <= 1.0):
            raise InvariantViolation(
                f"{type(self).__name__} must lie in [0.0, 1.0], got {self.value!r}"
            )
        # Normalise ints to float so equality/repr are consistent.
        object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True, slots=True)
class EvidenceReliability(_UncertaintyValue):
    """How much a single piece of evidence can be relied upon. Higher = more
    reliable. Attached to an ``EvidenceRecord``."""


@dataclass(frozen=True, slots=True)
class HypothesisSupport(_UncertaintyValue):
    """Degree to which current evidence supports a hypothesis (FR-RS-002).
    Higher = better supported. Retained historically across re-evaluation, never
    silently overwritten (FR-RS-003)."""


@dataclass(frozen=True, slots=True)
class ModelUncertainty(_UncertaintyValue):
    """Aggregate uncertainty carried by a WorldModel (FR-PU-002/004), distinct
    from any individual hypothesis's support. Higher = *less* certain. This is
    the value that must be able to **increase** as new evidence destabilises an
    earlier interpretation — not merely decrease."""


@dataclass(frozen=True, slots=True)
class ClassificationConfidence(_UncertaintyValue):
    """Confidence in an evidence *classification* — e.g. that a record is truly
    Behavioural rather than Narrative (FR-EM-004). Higher = more confident."""


@dataclass(frozen=True, slots=True)
class ProvenanceConfidence(_UncertaintyValue):
    """Confidence in the recorded *origin* of a piece of evidence (FR-EM-002).
    Higher = more confident the provenance is accurate."""


@dataclass(frozen=True, slots=True)
class PredictionLikelihood(_UncertaintyValue):
    """Likelihood attached to a Prediction (FR-RS-004/005). Higher = more
    likely. Never omitted for being low (FR-RS-005)."""
