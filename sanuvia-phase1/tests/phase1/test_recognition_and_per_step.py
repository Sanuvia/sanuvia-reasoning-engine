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
    recs, _ = _sanuvia_with_ids()
    return recs


def _sanuvia_with_ids() -> tuple[list[TrajectoryRecord], dict[str, str]]:
    c = SanuviaPersistentCondition(CASE_001)
    c.start()
    recs = [c.step(i) for i in CASE_001.interactions]
    c.finish()
    return recs, _durable_ids(c)

def _durable_ids(condition) -> dict[str, str]:
    """Authored fixture id -> engine-issued durable id.

    Locked §3.3 / Technical Design v1.5.4: the engine issues every durable
    hypothesis id after adjudication, so the fixture's authored ids are no
    longer what the engine reports.

    **Derived independently of ``attribution`` (B-1).** This previously split
    the lineage attribution, which only worked while attribution wrongly
    carried identity. Attribution is now the governed voice label and is
    identical across lineages. The mapping comes from the authored STATEMENT,
    matched exactly against what the engine stored -- no heuristic -- so these
    tests keep asserting the exact lineage rather than weakening to a count.
    """
    hypotheses = condition._store.hypotheses.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id
    )
    by_statement: dict[str, str] = {}
    for hypothesis in hypotheses:
        by_statement.setdefault(hypothesis.statement, hypothesis.hypothesis_id)

    mapping: dict[str, str] = {}
    for appraisal in CASE_001.appraisal_script.values():
        for proposal in appraisal.proposals:
            durable = by_statement.get(proposal.statement)
            if durable is not None:
                mapping[str(proposal.hypothesis_id)] = durable
    return mapping



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
    recs, durable = _sanuvia_with_ids()
    h1 = next(h for h in recs[5].hypotheses if h.hypothesis_id == durable[H1])
    # Support attaches to the observation under appraisal, deterministically.
    assert "evidence-5" in h1.supporting_evidence_ids  # where H1 was proposed
    assert "evidence-8" in h1.supporting_evidence_ids  # and where it was supported
    # The fixture additionally authored ``supporting_evidence_ids=(evidence-1,)``
    # on this proposal. Technical Design v1.5.4 §2 C REMOVES that field from the
    # model-facing surface -- "Proposal support attaches the current evidence
    # deterministically" (locked §3.1) -- so a proposal can no longer name an
    # evidence record at all. That is the structural closure of the Run 002
    # defect in which `e1`, `obs1` and `observation_1` were persisted as
    # model-invented evidence references.
    assert "evidence-1" not in h1.supporting_evidence_ids
    assert all(
        e in ("evidence-5", "evidence-8") for e in h1.supporting_evidence_ids
    ), "every attachment must be an observation actually appraised against H1"
    assert h1.contradicting_evidence_ids == ()
    # Contradiction is preserved separately, never collapsed into support:
    h3 = next(h for h in recs[5].hypotheses if h.hypothesis_id == durable[H3])
    assert h3.contradicting_evidence_ids == ("evidence-5",)


def test_revision_events_are_structured_not_only_counts() -> None:
    recs, durable = _sanuvia_with_ids()
    # count and structured events agree
    for r in recs:
        assert len(r.revision_events) == r.revision_count
    # seq-1: a single HYPOTHESIZE citing evidence-1
    assert [e.outcome for e in recs[0].revision_events] == ["hypothesize"]
    assert recs[0].revision_events[0].triggering_evidence_ids == ("evidence-1",)
    assert recs[0].revision_events[0].affected_object_id == durable[H3]
    # seq-4: multiple structured events, including a WEAKEN of H3
    outcomes = {e.outcome for e in recs[3].revision_events}
    assert {"hypothesize", "weaken"} <= outcomes
    # every revision event cites triggering evidence (provenance)
    assert all(
        len(e.triggering_evidence_ids) > 0 for r in recs for e in r.revision_events
    )


def test_prediction_supporting_hypothesis_links() -> None:
    recs, durable = _sanuvia_with_ids()
    p = recs[5].predictions[0]
    assert p.derived_from_hypothesis_ids == (durable[H1],)  # traceable to hypothesis
    assert len(p.derived_from_evidence_ids) > 0            # and to evidence
    assert p.model_version_id == "wm-6"                    # and to a model snapshot
