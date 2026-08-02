"""The canonical Phase 0 evidence sequence.

A fixed, synthetic, six-interaction sequence (modelled on the "Same Transcript"
example — partner lateness / emotional distance) authored to exercise every
Phase 0 pass condition:

* I1 introduces two *competing* explanations from one observation.
* I2, I3 consolidate H_B -> uncertainty falls; H_B crosses threshold -> a
  prediction is formed.
* I4 contradicts the now-established H_B and supports H_A -> anomaly (REVISE),
  H_B's prediction is invalidated, H_A's prediction appears, uncertainty rises.
* I5 is a Failed Acquisition that yields two *competing* candidate explanations.
* I6 is a low-reliability contradiction of the established H_A -> ESCALATE, and
  the model holds (no new version).

Appraisals are keyed by the evidence ids the :class:`ReasoningService` assigns
deterministically ("evidence-1" .. "evidence-6"), since the sequence submits one
observation per interaction in order.
"""

from __future__ import annotations

from dataclasses import dataclass

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import EvidenceClass, EvidenceRecordId, HypothesisId, SubjectId

SUBJECT = SubjectId("subject-exit-test")

H_A = HypothesisId("H_external_routine")
H_B = HypothesisId("H_emotional_distance")
H_C = HypothesisId("H_avoiding_topic")
H_D = HypothesisId("H_external_stressor")


@dataclass(frozen=True)
class Harness:
    service: ReasoningService
    store: InMemoryReasoningStore
    inputs: tuple[EvidenceInput, ...]


def _input(cls: EvidenceClass, content: str, reliability: float) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT,
        evidence_class=cls,
        content=content,
        source="reflection",
        reliability=reliability,
        classification_confidence=0.9,
    )


def appraisal_script() -> dict[EvidenceRecordId, Appraisal]:
    """The scenario's scripted appraisals, keyed by the deterministic evidence
    ids the service assigns ("evidence-1" .. "evidence-6")."""
    return {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(
                ProposedHypothesis(H_A, "external routine change", 0.4, ()),
                ProposedHypothesis(H_B, "increasing emotional distance", 0.4, ()),
            )
        ),
        EvidenceRecordId("evidence-2"): Appraisal(supports=(H_B,)),
        EvidenceRecordId("evidence-3"): Appraisal(supports=(H_B,)),
        EvidenceRecordId("evidence-4"): Appraisal(supports=(H_A,), contradicts=(H_B,)),
        EvidenceRecordId("evidence-5"): Appraisal(
            proposals=(
                ProposedHypothesis(H_C, "avoiding a difficult topic", 0.3, ()),
                ProposedHypothesis(H_D, "an external stressor", 0.3, ()),
            )
        ),
        EvidenceRecordId("evidence-6"): Appraisal(contradicts=(H_A,)),
    }


def evidence_inputs() -> tuple[EvidenceInput, ...]:
    """The fixed, ordered evidence sequence (one observation per interaction)."""
    return (
        _input(EvidenceClass.BEHAVIOURAL, "partner arrived home later", 0.7),
        _input(EvidenceClass.BEHAVIOURAL, "partner seemed preoccupied", 0.8),
        _input(EvidenceClass.BEHAVIOURAL, "less conversation over dinner", 0.8),
        _input(EvidenceClass.CONTRADICTORY, "warm, connected weekend together", 0.8),
        _input(EvidenceClass.FAILED_ACQUISITION, "prompt went unanswered", 0.3),
        _input(EvidenceClass.CONTRADICTORY, "a single terse text message", 0.3),
    )


def build() -> Harness:
    """Assemble a fresh, deterministic harness (fresh in-memory stores)."""
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(appraisal_script()),
        clock=ManualClock(),
        ids=SequentialIdGenerator(),
    )
    return Harness(
        service=ReasoningService(deps), store=store, inputs=evidence_inputs()
    )
