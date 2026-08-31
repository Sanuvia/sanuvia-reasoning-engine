"""Case DTOs — the longitudinal fixture shape consumed by every condition.

A :class:`Case` is an immutable, ordered evidence sequence plus the authored
appraisal script that tells the frozen Phase 0 engine, per evidence record,
which existing hypotheses it supports/contradicts and which new hypotheses it
proposes. The appraisal is *authored data*, not inference — it is the Phase 0
``EvidenceAppraiser`` seam (a foundation model in a later phase; scripted here).

Design points that preserve the governing discipline:

* ``CaseEvidence.text`` is the **RawObservation** (fixture "Observation"), never a
  participant's *interpretation* — interpretation becomes a hypothesis, supplied
  by the appraisal, not smuggled into evidence.
* ``evidence_role`` (resonance / accuracy / decision / outcome) is **fixture
  metadata only** — it is never added to the frozen domain object. It exists so a
  reader can see, e.g., that resonance evidence (ER-007) is not appraised as
  accuracy support.
* ``engine_id`` is the deterministic id Phase 0 assigns on ingestion
  (``evidence-1`` …). The appraisal script is keyed by it because the frozen
  ``ScriptedAppraiser`` looks up by ``EvidenceRecord.id``. A fixture-integrity
  test asserts the mapping actually holds when the case is run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sanuvia.application.api import EvidenceInput
from sanuvia.application.ports.reasoning import Appraisal
from sanuvia.domain import EvidenceClass, EvidenceRecordId, SpaceId, SubjectId


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    """One evidence record in a longitudinal case.

    ``ref`` is the human/fixture id (``ER-001``); ``engine_id`` is the Phase 0
    ingestion id (``evidence-1``). Both are stable and deterministic.
    """

    ref: str
    engine_id: str
    text: str
    evidence_class: EvidenceClass
    reliability: float
    classification_confidence: float
    provenance_confidence: float
    source: str
    evidence_role: str  # fixture metadata only; never sent to the engine
    # Optional structured provenance (e.g. from an evidence extractor). Flows into
    # the Phase 0 evidence record via the public ``EvidenceInput.acquisition_metadata``
    # field — it does not affect reasoning. Empty for hand-authored fixtures.
    acquisition_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CaseInteraction:
    """One interaction (one sequence position). ``evidence`` is empty for a
    genuine no-new-evidence "hold" (e.g. Case-001 seq 5)."""

    index: int
    seq_label: str
    evidence: tuple[CaseEvidence, ...]


@dataclass(frozen=True, slots=True)
class Case:
    """An immutable longitudinal fixture: the same sequence handed to all conditions."""

    case_id: str
    subject_id: SubjectId
    space_id: SpaceId
    interactions: tuple[CaseInteraction, ...]
    appraisal_script: Mapping[EvidenceRecordId, Appraisal]
    hypothesis_catalogue: Mapping[str, str]  # hypothesis_id -> statement (reference only)

    def evidence_inputs(self, interaction: CaseInteraction) -> tuple[EvidenceInput, ...]:
        """Build the Phase 0 ``EvidenceInput`` batch for one interaction.

        The batch is empty for a hold. ``EvidenceInput.space_id`` is left ``None``
        so the interaction's call-level ``space_id`` applies uniformly.
        """
        return tuple(
            EvidenceInput(
                subject_id=self.subject_id,
                evidence_class=ev.evidence_class,
                content=ev.text,
                source=ev.source,
                reliability=ev.reliability,
                classification_confidence=ev.classification_confidence,
                provenance_confidence=ev.provenance_confidence,
                acquisition_metadata=ev.acquisition_metadata,
            )
            for ev in interaction.evidence
        )

    def evidence_refs(self, interaction: CaseInteraction) -> tuple[str, ...]:
        """The stable evidence refs disclosed in one interaction (empty for a hold)."""
        return tuple(ev.ref for ev in interaction.evidence)
