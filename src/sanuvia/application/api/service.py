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
    ClassificationConfidence,
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceReliability,
    Provenance,
    ProvenanceConfidence,
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


class ReasoningService:
    """Application service coordinating evidence intake and one reasoning
    interaction. Framework-free; wired against ports."""

    def __init__(self, deps: ReasoningDependencies) -> None:
        self._deps = deps
        self._loop = CoreLoop(deps)

    def record_interaction(
        self, subject_id: SubjectId, inputs: Sequence[EvidenceInput]
    ) -> InteractionResult:
        """Ingest a batch of observations as one interaction and return the
        resulting reasoning state."""
        records = tuple(self._to_record(i) for i in inputs)
        return self._loop.ingest(subject_id, records)

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

    def _to_record(self, item: EvidenceInput) -> EvidenceRecord:
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
        )
