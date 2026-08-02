"""API contract tests: ReasoningService (write) and WorldModelView (read-only)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api import EvidenceInput, ReasoningService, WorldModelView
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    HypothesisId,
    SubjectId,
)

SUBJECT = SubjectId("subject-api")
H1 = HypothesisId("H1")
H2 = HypothesisId("H2")


def _service() -> ReasoningService:
    # The service assigns evidence ids via the IdGenerator: "evidence-1", ...
    # so the scripted appraiser can be keyed by those deterministic ids.
    script = {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(
                ProposedHypothesis(H1, "explanation one", 0.4, ()),
                ProposedHypothesis(H2, "explanation two", 0.4, ()),
            )
        ),
        EvidenceRecordId("evidence-2"): Appraisal(supports=(H1,)),
    }
    deps = build_in_memory_dependencies(
        appraiser=ScriptedAppraiser(script),
        clock=ManualClock(datetime(2026, 3, 1, tzinfo=timezone.utc)),
        ids=SequentialIdGenerator(),
    )
    return ReasoningService(deps)


def test_service_builds_evidence_and_reasons() -> None:
    service = _service()
    result = service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.BEHAVIOURAL,
                content="partner arrived home later",
                source="reflection",
                reliability=0.7,
                classification_confidence=0.9,
            )
        ],
    )
    assert result.committed is True
    assert {h.hypothesis_id for h in result.active_hypotheses} == {H1, H2}


def test_view_reflects_state_after_interactions() -> None:
    service = _service()
    service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.BEHAVIOURAL,
                content="observation A",
                source="reflection",
                reliability=0.7,
                classification_confidence=0.9,
            )
        ],
    )
    service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.BEHAVIOURAL,
                content="observation B",
                source="reflection",
                reliability=0.8,
                classification_confidence=0.9,
            )
        ],
    )
    snapshot = service.view().understanding(SUBJECT)
    assert snapshot.model_version_id is not None
    assert snapshot.model_uncertainty is not None
    assert {h.hypothesis_id for h in snapshot.hypotheses} == {H1, H2}
    assert snapshot.revision_count >= 2  # I1 proposed two hypotheses, I2 strengthened one
    # H1 was strengthened twice (0.4 -> ~0.64) so it should carry a prediction.
    assert any(H1 in p.derived_from_hypothesis_ids for p in snapshot.predictions)


def test_view_has_no_mutating_surface() -> None:
    # Structural enforcement of "the Content Layer never mutates reasoning":
    # the view type exposes only queries.
    forbidden = (
        "add", "append", "set", "put", "revise", "ingest", "record",
        "delete", "update", "remove", "mutate", "write", "commit", "save",
    )
    public_methods = [
        name
        for name, _ in inspect.getmembers(WorldModelView, inspect.isfunction)
        if not name.startswith("_")
    ]
    assert public_methods, "view should expose read methods"
    for name in public_methods:
        assert not any(verb in name for verb in forbidden), (
            f"WorldModelView.{name} looks like a mutator; the view must be read-only"
        )


def test_service_only_ingests_evidence_not_inference() -> None:
    # The only intake DTO is EvidenceInput; everything the service persists as
    # evidence is an EvidenceRecord (FR-EM-005 holds at the API boundary too).
    service = _service()
    service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.NARRATIVE,
                content="things are fine",
                source="reflection",
                reliability=0.6,
                classification_confidence=0.8,
            )
        ],
    )
    stored = service.view().evidence(SUBJECT)
    assert all(isinstance(e, EvidenceRecord) for e in stored)
    assert stored[0].id == EvidenceRecordId("evidence-1")
