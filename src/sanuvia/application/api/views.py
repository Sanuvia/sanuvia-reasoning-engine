"""The read-only ``WorldModelView`` — the Content Layer's seam.

Programme Part 2: *"The Content Layer never mutates reasoning. The layer that
talks to the user gets a read-only WorldModelView with no mutating method
exposed. Enforce this structurally — a distinct type with no mutating surface."*

``WorldModelView`` is that distinct type. It holds only read-capable repository
ports and exposes only query methods — there is no ``add``/``append``/``revise``
on its surface, so a holder of a view cannot change reasoning state. It returns
immutable domain snapshots (all domain objects are frozen).

No-relationship-failure guarantee: every prediction/recognition the view can
surface is typed with ``TrajectoryKind`` / ``RecognitionKind``, neither of which
can express failure (FR-RF-002) — so the read surface is safe by construction.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sanuvia.application.ports.repositories import (
    EvidenceStore,
    HypothesisRepository,
    InquiryRepository,
    PredictionRepository,
    RecognitionRepository,
    RevisionLedgerStore,
    WorldModelRepository,
)
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    EvidenceRecord,
    Hypothesis,
    Inquiry,
    Prediction,
    RecognitionEvent,
    RevisionLedgerEntry,
    SpaceId,
    SubjectId,
    WorldModel,
    WorldModelVersionId,
)


@dataclass(frozen=True, slots=True)
class WorldModelViewSnapshot:
    """An immutable, read-only snapshot of a subject's current understanding —
    what a dashboard / "Deep Understanding" surface would render."""

    subject_id: SubjectId
    model_version_id: WorldModelVersionId | None
    model_uncertainty: float | None
    hypotheses: tuple[Hypothesis, ...]
    predictions: tuple[Prediction, ...]
    inquiries: tuple[Inquiry, ...]
    recognition_events: tuple[RecognitionEvent, ...]
    revision_count: int
    space_id: SpaceId = DEFAULT_SPACE_ID


class WorldModelView:
    """Read-only projection over persistent understanding.

    Constructed with read-capable ports; exposes query methods only. The class
    intentionally has **no** method that writes — this is the structural
    enforcement of "the Content Layer never mutates reasoning".
    """

    def __init__(
        self,
        *,
        evidence: EvidenceStore,
        hypotheses: HypothesisRepository,
        predictions: PredictionRepository,
        inquiries: InquiryRepository,
        world_models: WorldModelRepository,
        ledger: RevisionLedgerStore,
        recognition: RecognitionRepository,
    ) -> None:
        self._evidence = evidence
        self._hypotheses = hypotheses
        self._predictions = predictions
        self._inquiries = inquiries
        self._world_models = world_models
        self._ledger = ledger
        self._recognition = recognition

    # -- individual queries -------------------------------------------------
    #
    # Every read is scoped to (space_id, subject_id) (Finding 1). ``space_id``
    # defaults to the single default space so existing single-space readers are
    # unaffected; a reader for one scope never sees another scope's reasoning.

    def current_model(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> WorldModel | None:
        return self._world_models.get_current_model(subject_id, space_id=space_id)

    def active_hypotheses(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[Hypothesis, ...]:
        model = self._world_models.get_current_model(subject_id, space_id=space_id)
        latest = {
            h.hypothesis_id: h
            for h in self._hypotheses.list_for_subject(subject_id, space_id=space_id)
        }
        if model is None:
            return tuple(latest.values())
        return tuple(
            latest[hid] for hid in model.active_hypothesis_ids if hid in latest
        )

    def active_predictions(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[Prediction, ...]:
        model = self._world_models.get_current_model(subject_id, space_id=space_id)
        if model is None:
            return ()
        active_ids = set(model.active_prediction_ids)
        return tuple(
            p
            for p in self._predictions.list_for_subject(subject_id, space_id=space_id)
            if p.id in active_ids
        )

    def active_inquiries(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[Inquiry, ...]:
        model = self._world_models.get_current_model(subject_id, space_id=space_id)
        if model is None:
            return ()
        active_ids = set(model.active_inquiry_ids)
        return tuple(
            inq
            for inq in self._inquiries.list_for_subject(subject_id, space_id=space_id)
            if inq.id in active_ids
        )

    def revision_history(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[RevisionLedgerEntry, ...]:
        return tuple(self._ledger.read(subject_id, space_id=space_id))

    def recognition_events(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[RecognitionEvent, ...]:
        return tuple(self._recognition.list_for_subject(subject_id, space_id=space_id))

    def evidence(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> tuple[EvidenceRecord, ...]:
        return tuple(self._evidence.list_for_subject(subject_id, space_id=space_id))

    # -- composite snapshot -------------------------------------------------

    def understanding(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> WorldModelViewSnapshot:
        """A single read-only snapshot bundling current understanding for the
        ``(space_id, subject_id)`` scope."""
        model = self._world_models.get_current_model(subject_id, space_id=space_id)
        history: Sequence[RevisionLedgerEntry] = self._ledger.read(
            subject_id, space_id=space_id
        )
        return WorldModelViewSnapshot(
            subject_id=subject_id,
            model_version_id=None if model is None else model.model_version_id,
            model_uncertainty=(
                None if model is None else model.model_uncertainty.value
            ),
            hypotheses=self.active_hypotheses(subject_id, space_id=space_id),
            predictions=self.active_predictions(subject_id, space_id=space_id),
            inquiries=self.active_inquiries(subject_id, space_id=space_id),
            recognition_events=self.recognition_events(subject_id, space_id=space_id),
            revision_count=len(history),
            space_id=space_id,
        )
