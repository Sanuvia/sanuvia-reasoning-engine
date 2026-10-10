"""The reasoning trace is a deterministic pure renderer over session state."""

from __future__ import annotations

from sanuvia.exit_test.session_state import canonical_session_state
from sanuvia.exit_test.trace import render_canonical_trace, render_trace


def test_trace_is_deterministic() -> None:
    assert render_canonical_trace() == render_canonical_trace()


def test_render_trace_is_a_pure_function_of_state() -> None:
    state = canonical_session_state()
    # Same state in -> identical document out (no hidden inputs).
    assert render_trace(state) == render_trace(state)


def test_trace_has_expected_structure() -> None:
    text = render_canonical_trace()
    for marker in (
        "## Interaction 1",
        "## Interaction 6",
        "# End-of-run summaries",
        "## RevisionLedger (authoritative history)",
        "## Hypothesis lineage (support over time)",
        "## Prediction history",
        "## ModelUncertainty timeline",
    ):
        assert marker in text, f"missing section: {marker}"


def test_trace_is_generated_from_real_engine_state() -> None:
    text = render_canonical_trace()
    assert "`wm-1`" in text and "`wm-5`" in text
    assert "evidence-1" in text
    assert "rev-1" in text
    assert "model holds" in text
    assert "disposition **escalate**" in text
    # Consolidation. R6 derives a new lineage's support from reliability
    # (0.5*0.7 = 0.35) rather than the authored 0.40, so after interaction 2
    # the supports are hyp-2 0.610 and hyp-1 0.350 and the UNCHANGED formula
    # ((1-top)+rival)/2 gives (0.390+0.350)/2 = 0.370, where the authored 0.40
    # starting points previously gave (0.360+0.400)/2 = 0.380. Uncertainty
    # still FALLS on consolidation, which is what this asserts.
    assert "0.500 → 0.370" in text
    # Destabilisation, same R6 offset. After interaction 3 the supports are
    # hyp-2 0.766 and hyp-1 0.350 -> (0.234+0.350)/2 = 0.292; interaction 4's
    # contradiction drops hyp-2 to 0.460 while hyp-1 strengthens to 0.610 ->
    # (0.390+0.460)/2 = 0.425. Uncertainty still RISES on destabilisation.
    assert "0.292 → 0.425" in text
