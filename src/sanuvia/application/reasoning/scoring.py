"""Pure scoring functions for the reasoning engine.

All functions here are deterministic and side-effect free — no I/O, no ports.
They implement the arithmetic of support, aggregate model uncertainty, and
expected information gain. Keeping them pure makes the engine's behaviour easy to
reason about and test in isolation.

Design intent for uncertainty (Definition of Done: "uncertainty changes
appropriately rather than merely decreasing"):

* A single well-supported hypothesis with no strong rival  -> LOW uncertainty.
* Two strongly-supported rivals (genuine competition)       -> HIGHER uncertainty.
* No/weakly-supported hypotheses                            -> HIGH uncertainty.

This lets uncertainty *increase* when new evidence raises a competing hypothesis
(destabilisation), *decrease* when evidence consolidates a single explanation,
and *hold* when nothing material changes.
"""

from __future__ import annotations


def clamp_unit(value: float) -> float:
    """Clamp a value into ``[0.0, 1.0]``."""
    return max(0.0, min(1.0, value))


def support_after_support(
    current: float, reliability: float, learning_rate: float
) -> float:
    """New support after a supporting observation.

    Moves ``current`` toward 1.0 by a fraction of the remaining headroom, scaled
    by the observation's reliability. Diminishing returns: strongly-supported
    hypotheses gain less from each further confirmation.
    """
    return clamp_unit(current + learning_rate * reliability * (1.0 - current))


def support_after_contradiction(
    current: float, reliability: float, learning_rate: float
) -> float:
    """New support after a contradicting observation.

    Moves ``current`` toward 0.0 proportionally to its present magnitude and the
    observation's reliability.
    """
    return clamp_unit(current - learning_rate * reliability * current)


def aggregate_model_uncertainty(supports: list[float]) -> float:
    """Aggregate model uncertainty from the current hypotheses' supports.

    ``base``       = how weakly the *best* explanation is supported (1 - top).
    ``competition`` = the support commanded by the strongest *rival*.
    Uncertainty is their mean, so both a weak leader and a strong rival raise it.

    With no hypotheses, the model knows nothing: uncertainty is maximal.
    """
    if not supports:
        return 1.0
    ordered = sorted(supports, reverse=True)
    top = ordered[0]
    rival = ordered[1] if len(ordered) > 1 else 0.0
    base = 1.0 - top
    return clamp_unit((base + rival) / 2.0)


def expected_information_gain(supports: list[float]) -> float:
    """A simple expected-information-gain proxy for the current competition.

    Highest when the top two hypotheses are close and both non-trivial — i.e.
    when acquiring discriminating evidence would most reduce uncertainty. Used to
    decide whether raising an Inquiry is worthwhile (FR-IQ-005). Zero when there
    is no genuine competition to resolve.
    """
    if len(supports) < 2:
        return 0.0
    ordered = sorted(supports, reverse=True)
    top, rival = ordered[0], ordered[1]
    closeness = 1.0 - abs(top - rival)  # 1.0 when tied
    strength = (top + rival) / 2.0  # weight by how live both are
    return clamp_unit(closeness * strength)
