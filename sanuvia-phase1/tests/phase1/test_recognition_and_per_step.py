"""C-2 / C-3 — Recognition Condition records (deferred vs absent) and per-step
supporting/contradicting evidence, structured revision events, and prediction
supporting-hypothesis links."""

from __future__ import annotations

from fixtures.longitudinal.case_001 import CASE_001, H1, H3

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


# --- C-2: Recognition Condition records --------------------------------------


def test_recognition_records_absent_for_sanuvia_and_not_fabricated() -> None:
    recs = _sanuvia()
    # An empty TUPLE (not None) = "the engine emitted no Recognition records".
    # Recognition *computation* is deferred (detect_recognition_condition is
    # interface-only), so nothing is written — this is an explicit absence, not a
    # fabricated "no recognition exists" judgment.
    for r in recs:
        assert r.recognition_records == ()
    assert metrics.recognition_record_series(recs) == [0, 0, 0, 0, 0, 0]


def test_recognition_records_not_applicable_for_fm() -> None:
    recs = _stateless()
    # None = "not applicable" — a foundation-model baseline has no Recognition
    # Condition concept.
    for r in recs:
        assert r.recognition_records is None
    assert metrics.recognition_record_series(recs) == [None] * 6


# --- C-3: per-step supporting/contradicting evidence --------------------------


def test_per_step_supporting_and_contradicting_evidence_surfaced() -> None:
    recs = _sanuvia()
    h1 = next(h for h in recs[5].hypotheses if h.hypothesis_id == H1)
    assert "evidence-5" in h1.supporting_evidence_ids
    assert "evidence-1" in h1.supporting_evidence_ids  # provenance to ER-001 preserved
    assert h1.contradicting_evidence_ids == ()
    # Contradiction is preserved separately, never collapsed into support:
    h3 = next(h for h in recs[5].hypotheses if h.hypothesis_id == H3)
    assert h3.contradicting_evidence_ids == ("evidence-5",)


def test_revision_events_are_structured_not_only_counts() -> None:
    recs = _sanuvia()
    # count and structured events agree
    for r in recs:
        assert len(r.revision_events) == r.revision_count
    # seq-1: a single HYPOTHESIZE citing evidence-1
    assert [e.outcome for e in recs[0].revision_events] == ["hypothesize"]
    assert recs[0].revision_events[0].triggering_evidence_ids == ("evidence-1",)
    assert recs[0].revision_events[0].affected_object_id == "H3_anticipatory_protection"
    # seq-4: multiple structured events, including a WEAKEN of H3
    outcomes = {e.outcome for e in recs[3].revision_events}
    assert {"hypothesize", "weaken"} <= outcomes
    # every revision event cites triggering evidence (provenance)
    assert all(
        len(e.triggering_evidence_ids) > 0 for r in recs for e in r.revision_events
    )


def test_prediction_supporting_hypothesis_links() -> None:
    recs = _sanuvia()
    p = recs[5].predictions[0]
    assert p.derived_from_hypothesis_ids == (H1,)          # traceable to hypothesis
    assert len(p.derived_from_evidence_ids) > 0            # and to evidence
    assert p.model_version_id == "wm-6"                    # and to a model snapshot
