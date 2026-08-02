"""The reasoning lineage graph is a deterministic pure renderer over state."""

from __future__ import annotations

from sanuvia.exit_test.reasoning_graph import (
    build_canonical_graph,
    render_canonical_markdown,
    render_dot,
    render_mermaid,
)
from sanuvia.exit_test.session_state import canonical_session_state
from sanuvia.exit_test.reasoning_graph import build_graph


def test_graph_is_deterministic() -> None:
    assert render_canonical_markdown() == render_canonical_markdown()
    g1, g2 = build_canonical_graph(), build_canonical_graph()
    assert render_mermaid(g1) == render_mermaid(g2)
    assert render_dot(g1) == render_dot(g2)


def test_build_graph_is_a_pure_function_of_state() -> None:
    state = canonical_session_state()
    assert render_mermaid(build_graph(state)) == render_mermaid(build_graph(state))


def test_mermaid_structure() -> None:
    text = render_mermaid(build_canonical_graph())
    assert text.startswith("flowchart LR")
    for vid in ("V_wm_1", "V_wm_2", "V_wm_3", "V_wm_4", "V_wm_5"):
        assert vid in text
    assert "V_wm_3 -->|strengthen, contradict| V_wm_4" in text
    assert "classDef version" in text
    assert "class V_wm_1,V_wm_2,V_wm_3,V_wm_4,V_wm_5 version;" in text


def test_graph_reflects_real_engine_lineage() -> None:
    text = render_mermaid(build_canonical_graph())
    assert "E_evidence_1 -->|hypothesize| H_H_emotional_distance" in text
    assert "E_evidence_4 -.->|contradict| H_H_emotional_distance" in text
    assert "0.40→0.64→0.78→0.47" in text
    assert "A_anom_1 -->|→revise| V_wm_4" in text
    assert 'A_anom_2{"anom-2<br/>escalate"}' in text
    assert "V_wm_1 -->|raises| Q_inq_1" in text


def test_dot_render() -> None:
    dot = render_dot(build_canonical_graph())
    assert dot.startswith("digraph reasoning {")
    assert "rankdir=LR;" in dot
    assert "V_wm_1 -> V_wm_2" in dot
