"""v1.1/v0.4 reconciliation — surface the Inquiry status lifecycle (§8A/§5A) and
the dependency/provenance graph (Sys Arch v1.1 §5A; Eng Spec v0.4 §8A;
Programme v1.4 Part 4A per-step 'dependencies'). Both are produced by the frozen
Phase 0 engine and now surfaced by Phase 1 (no Phase 0 change)."""

from __future__ import annotations

from fixtures.longitudinal.case_001 import CASE_001, H1, H2, H3

from sanuvia_phase1 import metrics
from sanuvia_phase1.conditions import SanuviaPersistentCondition, StatelessFmCondition
from sanuvia_phase1.language_models import ScriptedLanguageModel
from sanuvia_phase1.trajectory import TrajectoryRecord


def _sanuvia() -> list[TrajectoryRecord]:
    c = SanuviaPersistentCondition(CASE_001)
    c.start()
    recs = [c.step(i) for i in CASE_001.interactions]
    c.finish()
    return recs


def _stateless() -> list[TrajectoryRecord]:
    c = StatelessFmCondition(ScriptedLanguageModel(("{}",) * len(CASE_001.interactions)))
    c.start()
    return [c.step(i) for i in CASE_001.interactions]


# --- Inquiry status lifecycle (§8A / §5A) ------------------------------------


def test_sanuvia_surfaces_inquiry_status() -> None:
    recs = _sanuvia()
    # Inquiries are surfaced at seq-2/3/4/6, all in the engine's 'proposed' status.
    assert metrics.inquiry_status_series(recs) == [
        None, "proposed", "proposed", "proposed", None, "proposed"
    ]
    for r in recs:
        if r.inquiry is not None:
            assert r.inquiry.status in {
                "proposed", "active", "dormant", "locally_resolved",
                "reopened", "superseded", "closed",
            }


def test_fm_inquiry_has_no_structured_status() -> None:
    recs = _stateless()
    for r in recs:
        if r.inquiry is not None:
            assert r.inquiry.status == ""  # FM holds no structured Inquiry object


# --- Dependency / provenance graph (§5A / §8A) -------------------------------


def test_sanuvia_surfaces_dependency_edges_that_grow() -> None:
    recs = _sanuvia()
    counts = metrics.dependency_edge_count_series(recs)
    # The append-only graph is non-empty once hypotheses form and grows / holds.
    assert counts[0] >= 1
    assert counts[-1] >= counts[0]
    # Real, typed relations the frozen engine wrote:
    final = {(e.from_ref, e.relation, e.to_ref) for e in recs[5].dependency_edges}
    assert ("evidence-5", "supports", H1) in final
    assert ("evidence-8", "supports", H1) in final
    assert ("pred-1", "derived_from", H1) in final       # prediction → hypothesis
    assert ("evidence-2", "supports", H2) in final
    assert ("evidence-5", "contradicts", H3) in final     # contradiction preserved


def test_fm_baselines_have_no_dependency_graph() -> None:
    recs = _stateless()
    assert all(r.dependency_edges == () for r in recs)
    assert metrics.dependency_edge_count_series(recs) == [0, 0, 0, 0, 0, 0]


def test_dependency_edges_are_deterministic() -> None:
    a = _sanuvia()
    b = _sanuvia()
    assert [r.dependency_edges for r in a] == [r.dependency_edges for r in b]
