"""Tunable reasoning constants.

============================= PHASE-0 PLACEHOLDERS ==========================
Every value in this class is a **Phase-0 placeholder**, not a product algorithm
and not a value drawn from the frozen specification. They exist so the reasoning
*structure* (accumulate → revise → predict → inquire) can run and be tested
end-to-end; the specific arithmetic is expected to be replaced.

They are gathered in one immutable, injectable place precisely so they read as
tunable placeholder policy rather than magic numbers scattered through the
engine, and so they can be swapped without touching the reasoning structure.

None of these encodes a *deferred transition function* (revision escalation,
recognition computation, inquiry reopening thresholds) — those are not
implemented at all, here or anywhere. These govern only the placeholder
support/uncertainty arithmetic and the thresholds at which the engine chooses to
form a prediction or raise an inquiry.
=============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReasoningConfig:
    # (Phase-0 placeholder) How fast hypothesis support moves toward 1 (support)
    # or 0 (contradiction), scaled by the evidence's reliability. 0 = never move,
    # 1 = jump fully. Not a calibrated learning rate — a stand-in.
    support_learning_rate: float = 0.5

    # (Phase-0 placeholder) A hypothesis at/above this support counts as
    # "established" — a contradiction against it is treated as an anomaly
    # (FR-MR-004). Threshold value is illustrative only.
    established_support_threshold: float = 0.6

    # (Phase-0 placeholder) Contradiction disposition, chosen by the contradicting
    # evidence's reliability. This is a stand-in for the assumption-selection
    # logic the spec defers — it does NOT implement second-order revision:
    #   reliability >= revise  -> REVISE   (proceed to a revision event)
    #   reject <= reliability   -> ESCALATE (insufficient basis; second-order,
    #                                        deferred — no revision event)
    #   reliability <  reject   -> REJECT   (dismiss; no revision event)
    contradiction_revise_reliability: float = 0.5
    contradiction_reject_reliability: float = 0.2

    # (Phase-0 placeholder) A hypothesis at/above this support yields a Prediction;
    # below it, any prediction derived from that hypothesis is invalidated
    # (dropped from the current model version's active set). Prediction lifecycle
    # governance is spec-unresolved; this threshold is a stand-in.
    prediction_support_threshold: float = 0.6

    # (Phase-0 placeholder) Material uncertainty at/above this raises an Inquiry.
    inquiry_uncertainty_threshold: float = 0.4

    def __post_init__(self) -> None:
        for name in (
            "support_learning_rate",
            "established_support_threshold",
            "contradiction_revise_reliability",
            "contradiction_reject_reliability",
            "prediction_support_threshold",
            "inquiry_uncertainty_threshold",
        ):
            value = getattr(self, name)
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"ReasoningConfig.{name} must lie in [0, 1]")
