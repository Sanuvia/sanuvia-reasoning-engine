"""Longitudinal reasoning scenario.

Drives the Core Loop over a scripted sequence modelled on the "Same Transcript"
example (partner lateness / emotional distance) and asserts the behaviours the
Phase 0 exit test and Definition of Done require:

* the model revises across interactions;
* competing hypotheses are retained and revised;
* uncertainty *reduces* when evidence consolidates and *increases* when new
  evidence destabilises an earlier interpretation;
* predictions are generated and later *invalidated* when their hypothesis is
  contradicted;
* a failed acquisition yields competing candidate explanations, not a default;
* an insufficiently-reliable contradiction *escalates* and the model *holds*;
* every revision is traceable to evidence and no inference is stored as evidence.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.application.reasoning import CoreLoop
from sanuvia.domain import (
    AnomalyDisposition,
    ClassificationConfidence,
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceReliability,
    FutureTrajectory,
    HypothesisId,
    Provenance,
    ProvenanceConfidence,
    SubjectId,
    TrajectoryKind,
)

SUBJECT = SubjectId("subject-partner")
H_A = HypothesisId("H_external_routine")
H_B = HypothesisId("H_emotional_distance")


def _ev(
    clock: ManualClock,
    eid: str,
    *,
    cls: EvidenceClass = EvidenceClass.BEHAVIOURAL,
    reliability: float = 0.8,
) -> EvidenceRecord:
    return EvidenceRecord(
        id=EvidenceRecordId(eid),
        subject_id=SUBJECT,
        evidence_class=cls,
        content=f"observation {eid}",
        provenance=Provenance(source="reflection", confidence=ProvenanceConfidence(0.9)),
        reliability=EvidenceReliability(reliability),
        classification_confidence=ClassificationConfidence(0.9),
        occurred_at=clock.now(),
    )


def _build() -> tuple[CoreLoop, ManualClock, InMemoryReasoningStore]:
    clock = ManualClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    store = InMemoryReasoningStore()
    script: dict[EvidenceRecordId, Appraisal] = {
        # I1: one observation proposes two competing explanations.
        EvidenceRecordId("ev1"): Appraisal(
            proposals=(
                ProposedHypothesis(H_A, "external routine change", 0.4, ()),
                ProposedHypothesis(
                    H_B,
                    "increasing emotional distance",
                    0.4,
                    (),
                    predicted_trajectory=FutureTrajectory(
                        TrajectoryKind.RECURRING_CYCLE, "distance/repair cycle"
                    ),
                ),
            )
        ),
        # I2, I3: evidence consolidates the emotional-distance explanation.
        EvidenceRecordId("ev2"): Appraisal(supports=(H_B,)),
        EvidenceRecordId("ev3"): Appraisal(supports=(H_B,)),
        # I4: reliable evidence contradicts H_B (now established) and supports H_A.
        EvidenceRecordId("ev4"): Appraisal(supports=(H_A,), contradicts=(H_B,)),
        # I5: a failed acquisition yields *competing* candidate explanations.
        EvidenceRecordId("ev5"): Appraisal(
            proposals=(
                ProposedHypothesis(
                    HypothesisId("H_avoiding_topic"), "avoiding a difficult topic", 0.3, ()
                ),
                ProposedHypothesis(
                    HypothesisId("H_external_stress"), "an external stressor", 0.3, ()
                ),
            )
        ),
        # I6: a low-reliability contradiction of established H_A -> escalate, hold.
        EvidenceRecordId("ev6"): Appraisal(contradicts=(H_A,)),
    }
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(script),
        clock=clock,
        ids=SequentialIdGenerator(),
    )
    return CoreLoop(deps), clock, store


def test_scenario_produces_persistent_reasoning() -> None:
    loop, clock, store = _build()
    results = []
    for eid, cls, rel in [
        ("ev1", EvidenceClass.BEHAVIOURAL, 0.7),
        ("ev2", EvidenceClass.BEHAVIOURAL, 0.8),
        ("ev3", EvidenceClass.BEHAVIOURAL, 0.8),
        ("ev4", EvidenceClass.CONTRADICTORY, 0.8),
        ("ev5", EvidenceClass.FAILED_ACQUISITION, 0.3),
        ("ev6", EvidenceClass.CONTRADICTORY, 0.3),
    ]:
        clock.tick()
        results.append(loop.ingest(SUBJECT, [_ev(clock, eid, cls=cls, reliability=rel)]))
    r1, r2, r3, r4, r5, r6 = results

    # --- model revises across interactions -------------------------------
    versions = [r.model.model_version_id for r in (r1, r2, r3, r4, r5) if r.model]
    assert len(set(versions)) == 5, "each committing interaction yields a new version"

    # --- competing hypotheses retained -----------------------------------
    assert {h.hypothesis_id for h in r1.active_hypotheses} == {H_A, H_B}
    assert r1.inquiry is not None, "genuine competition should raise an inquiry"

    # --- uncertainty reduces on consolidation, increases on destabilisation
    u1, u2, u3, u4 = (r.model_uncertainty for r in (r1, r2, r3, r4))
    assert u1 is not None and u2 is not None and u3 is not None and u4 is not None
    assert u2 < u1, "supporting evidence consolidated H_B -> uncertainty should fall"
    assert u4 > u3, "contradiction destabilised H_B -> uncertainty should rise"

    # --- predictions generated, then invalidated -------------------------
    def hyp_ids_with_predictions(result) -> set[HypothesisId]:
        return {
            hid
            for p in result.predictions
            for hid in p.derived_from_hypothesis_ids
        }

    assert H_B in hyp_ids_with_predictions(r3), "H_B established -> prediction exists"
    assert H_B not in hyp_ids_with_predictions(r4), "H_B contradicted -> invalidated"
    assert H_A in hyp_ids_with_predictions(r4), "H_A now leads -> its prediction exists"

    # prediction likelihood tracks its hypothesis support (grounding)
    b_pred_i3 = next(p for p in r3.predictions if H_B in p.derived_from_hypothesis_ids)
    b_support_i3 = next(
        h.support.value for h in r3.active_hypotheses if h.hypothesis_id == H_B
    )
    assert b_pred_i3.likelihood.value == b_support_i3

    # --- contradiction of established hypothesis created an anomaly -------
    dispositions_i4 = [a.disposition for a in r4.revision_result.anomaly_resolutions]
    assert AnomalyDisposition.REVISE in dispositions_i4

    # --- failed acquisition -> competing candidate explanations ----------
    new_in_i5 = {
        h.hypothesis_id for h in r5.active_hypotheses
    } - {h.hypothesis_id for h in r4.active_hypotheses}
    assert len(new_in_i5) >= 2, "failed acquisition must yield competing candidates"

    # --- insufficiently-reliable contradiction escalates and holds -------
    assert r6.committed is False, "escalation must not revise the model"
    assert r6.model is not None and r6.model.model_version_id == r5.model.model_version_id
    assert AnomalyDisposition.ESCALATE in [
        a.disposition for a in r6.revision_result.anomaly_resolutions
    ]

    # --- traceability & the never-conflate guarantee ---------------------
    for entry in store.ledger.read(SUBJECT):
        assert entry.revision_event.triggering_evidence_ids, "revision traceable to evidence"
    for pred in store.predictions.list_for_subject(SUBJECT):
        assert pred.derived_from_hypothesis_ids or pred.derived_from_evidence_ids
    # every evidence id in the store is a real EvidenceRecord (no inference leaked)
    stored = store.evidence.list_for_subject(SUBJECT)
    assert all(isinstance(e, EvidenceRecord) for e in stored)
    assert len(stored) == 6


def test_proposal_trajectory_hint_flows_into_prediction() -> None:
    # A proposal that is prediction-worthy on arrival (support >= threshold) and
    # carries a trajectory hint yields a prediction with that trajectory kind.
    clock = ManualClock(datetime(2026, 2, 1, tzinfo=timezone.utc))
    script = {
        EvidenceRecordId("evX"): Appraisal(
            proposals=(
                ProposedHypothesis(
                    HypothesisId("H_cycle"),
                    "a recurring distance/repair cycle",
                    0.7,
                    (),
                    predicted_trajectory=FutureTrajectory(
                        TrajectoryKind.RECURRING_CYCLE, "distance then repair"
                    ),
                ),
            )
        )
    }
    deps = build_in_memory_dependencies(
        appraiser=ScriptedAppraiser(script), clock=clock, ids=SequentialIdGenerator()
    )
    result = CoreLoop(deps).ingest(SUBJECT, [_ev(clock, "evX", reliability=0.8)])
    assert len(result.predictions) == 1
    assert result.predictions[0].trajectory.kind is TrajectoryKind.RECURRING_CYCLE


def test_revision_events_reported_per_interaction() -> None:
    loop, clock, _ = _build()
    clock.tick()
    r1 = loop.ingest(SUBJECT, [_ev(clock, "ev1", reliability=0.7)])
    # Two hypotheses proposed from one observation -> two committed revisions,
    # reported as "since prior interaction".
    assert len(r1.revision_events_since_prior) == 2
    clock.tick()
    r2 = loop.ingest(SUBJECT, [_ev(clock, "ev2", reliability=0.8)])
    # Only the new interaction's revision is reported, not I1's.
    assert len(r2.revision_events_since_prior) == 1
