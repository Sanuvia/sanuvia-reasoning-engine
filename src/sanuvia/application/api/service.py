"""The write-side API — ``ReasoningService``.

Callers hand in ``EvidenceInput`` (a transport-friendly DTO); the service turns
each into an immutable ``EvidenceRecord`` at the boundary, assigning its id and
(if unset) timestamp via the ``IdGenerator`` / ``Clock`` ports, then runs one
Core Loop interaction.

Two boundary guarantees:

* Only *evidence* can be handed in. There is no input DTO for inferences and no
  method that accepts one, so the never-re-ingest rule (FR-EM-005) holds at the
  API surface too, not just internally.
* Reads go through :class:`WorldModelView`, which the service hands out via
  :meth:`view`; the service never exposes the write repositories to a reader.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from sanuvia.application.reasoning.core_loop import CoreLoop, InteractionResult
from sanuvia.application.reasoning.dependencies import ReasoningDependencies
from sanuvia.domain import (
    EvidenceStanding,
    SourceObservationRef,
    DEFAULT_SPACE_ID,
    ActorId,
    ClassificationConfidence,
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceReliability,
    Provenance,
    ProvenanceConfidence,
    SpaceId,
    SubjectId,
)

from .views import WorldModelView


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    """A transport-friendly description of a single observation.

    Deliberately mirrors ``EvidenceRecord`` minus the machine-assigned id: the
    service assigns the id (and the timestamp, if ``occurred_at`` is omitted) so
    callers never fabricate them. Confidences are plain floats here and become
    typed uncertainty values inside the service.
    """

    subject_id: SubjectId
    evidence_class: EvidenceClass
    content: str
    source: str
    reliability: float
    classification_confidence: float
    provenance_confidence: float = 1.0
    occurred_at: datetime | None = None
    acquisition_metadata: tuple[tuple[str, str], ...] = field(default=())
    # Isolation boundary (Finding 1). None -> the interaction's space is used.
    space_id: SpaceId | None = None
    # Who contributed this observation (a.k.a. member id) — optional.
    actor_id: ActorId | None = None
    # Where the observation came from, including the within-interaction index
    # that Run 002 lost (Technical Design v1.5.4 §2 A).
    source_ref: "SourceObservationRef | None" = None
    # The three governed semantic properties (§2 E). Proposed at extraction and
    # validated here; the application owns the contextual facts.
    standing: "EvidenceStanding | None" = None


class ReasoningService:
    """Application service coordinating evidence intake and one reasoning
    interaction. Framework-free; wired against ports."""

    def __init__(self, deps: ReasoningDependencies) -> None:
        self._deps = deps
        self._loop = CoreLoop(deps)

    def record_interaction(
        self,
        subject_id: SubjectId,
        inputs: Sequence[EvidenceInput],
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> InteractionResult:
        """Ingest a batch of observations as one interaction and return the
        resulting reasoning state.

        The interaction is scoped to ``(space_id, subject_id)`` (Finding 1). Each
        observation is stamped with that scope; an ``EvidenceInput`` that names a
        different subject or space is rejected by the Core Loop's ownership gate.
        """
        # The rollback boundary opens HERE -- above the first ``_to_record``
        # call -- because canonical ``evidence-N`` ids are minted in that
        # comprehension, before any store write (Technical Design v1.5.4 §3.1
        # step 0, §5.5, F-6). Opening it inside the Core Loop instead would
        # leave those identifiers outside the boundary, and a store-only
        # atomicity test would still pass.
        uow = self._unit_of_work()
        if uow is None:
            records = tuple(self._to_record(i, space_id=space_id) for i in inputs)
            return self._loop.ingest(subject_id, records, space_id=space_id)

        uow.begin()
        try:
            records = tuple(self._to_record(i, space_id=space_id) for i in inputs)
            result = self._loop.ingest(subject_id, records, space_id=space_id)
        except BaseException:
            # Every rejection restores, pre-mutation included: the counters have
            # already advanced even when nothing was written (F-4).
            uow.restore()
            raise
        uow.commit()
        return result

    def _unit_of_work(self):
        """A UnitOfWork over this service's stores, when they support snapshots.

        Returns ``None`` for a store bundle that predates snapshot support, so
        adapters outside the Phase 1 path keep working unchanged.
        """
        from sanuvia.application.reasoning.unit_of_work import UnitOfWork

        bundle = getattr(self._deps, "store_bundle", None)
        if bundle is None:
            return None
        try:
            from sanuvia.application.reasoning.unit_of_work import bundle_stores

            stores = bundle_stores(bundle)
        except Exception:
            return None
        if not all(hasattr(s, "snapshot") for s in stores.values()):
            return None
        return UnitOfWork(stores=stores, ids=getattr(self._deps, "ids", None))

    def view(self) -> WorldModelView:
        """A read-only projection of current understanding. The returned view has
        no mutating surface."""
        d = self._deps
        return WorldModelView(
            evidence=d.evidence,
            hypotheses=d.hypotheses,
            predictions=d.predictions,
            inquiries=d.inquiries,
            world_models=d.world_models,
            ledger=d.ledger,
            recognition=d.recognition,
        )

    def _to_record(
        self, item: EvidenceInput, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> EvidenceRecord:
        return EvidenceRecord(
            id=EvidenceRecordId(self._deps.ids.new_id("evidence")),
            subject_id=item.subject_id,
            evidence_class=item.evidence_class,
            content=item.content,
            provenance=Provenance(
                source=item.source,
                confidence=ProvenanceConfidence(item.provenance_confidence),
                acquisition_metadata=item.acquisition_metadata,
            ),
            reliability=EvidenceReliability(item.reliability),
            classification_confidence=ClassificationConfidence(
                item.classification_confidence
            ),
            occurred_at=item.occurred_at or self._deps.clock.now(),
            space_id=item.space_id or space_id,
            actor_id=item.actor_id,
            source_ref=item.source_ref,
            standing=item.standing,
        )
