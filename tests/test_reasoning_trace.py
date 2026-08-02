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
    assert "0.500 → 0.380" in text  # consolidation
    assert "0.308 → 0.415" in text  # destabilisation
