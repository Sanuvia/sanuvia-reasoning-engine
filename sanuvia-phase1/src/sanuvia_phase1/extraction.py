"""Evidence extraction — the Phase-1 boundary between raw text and structured evidence.

An ``EvidenceExtractor`` turns one raw-text :class:`~sanuvia_phase1.transcript.TranscriptInteraction`
into structured **observations** ready for the frozen Phase 0 public API. It is the
*only* new "language understanding" component, and its responsibility is strictly:

    raw conversation text  ->  candidate structured OBSERVATIONS (+ provenance)

CRITICAL — evidence vs inference (Reasoning Semantics v0.2 "Evidence"; Programme
v1.4 Part 2 "Evidence and inference are distinct"). The extractor must emit
**observations** ("the person said X", "the person did Y"), never **inferences**
("the person fears rejection"). Forming hypotheses from evidence is the frozen
Phase 0 engine's job via the ``EvidenceAppraiser`` port — the extractor must not,
and structurally cannot, create hypotheses or touch the WorldModel.

Every extracted item retains provenance back to the source interaction, transcript,
extractor identity, text span (if available), and an extraction status.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sanuvia.domain import EvidenceClass

from .transcript import TranscriptInteraction


@dataclass(frozen=True, slots=True)
class EvidenceProvenance:
    """Where an extracted observation came from. Kept with every item so a
    reviewer can always trace evidence back to raw text."""

    transcript_id: str
    source_interaction_index: int
    seq_label: str
    extractor_id: str
    text_span: str | None  # the quoted span/phrase the observation derives from
    extraction_status: str  # "extracted" | "no_evidence" | ...


@dataclass(frozen=True, slots=True)
class ObservationSpec:
    """What an extractor decides about one observation *before* provenance is
    stamped. Authored by a scripted extractor, or parsed from a real model.

    ``observation`` is a RawObservation — what was said/happened — never an
    interpretation."""

    ref: str
    observation: str
    evidence_class: EvidenceClass
    reliability: float
    classification_confidence: float
    provenance_confidence: float
    text_span: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedEvidence:
    """A structured observation with provenance, ready to become Phase 0 evidence."""

    ref: str
    observation: str
    evidence_class: EvidenceClass
    reliability: float
    classification_confidence: float
    provenance_confidence: float
    provenance: EvidenceProvenance


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """The evidence extracted from one interaction (empty for a hold / no evidence)."""

    interaction_index: int
    seq_label: str
    evidence: tuple[ExtractedEvidence, ...]


@runtime_checkable
class EvidenceExtractor(Protocol):
    """Turns one raw-text interaction into structured observations.

    Implementations: ``ScriptedEvidenceExtractor`` (deterministic test double) and
    ``ExternalEvidenceExtractor`` (real, provider-neutral, injected client)."""

    extractor_id: str

    def extract(
        self, interaction: TranscriptInteraction, transcript_id: str
    ) -> tuple[ExtractedEvidence, ...]: ...


def stamp(
    spec: ObservationSpec,
    interaction: TranscriptInteraction,
    transcript_id: str,
    extractor_id: str,
    *,
    status: str = "extracted",
) -> ExtractedEvidence:
    """Attach provenance to an observation spec, deriving every provenance field
    from the actual interaction (never fabricated)."""
    return ExtractedEvidence(
        ref=spec.ref,
        observation=spec.observation,
        evidence_class=spec.evidence_class,
        reliability=spec.reliability,
        classification_confidence=spec.classification_confidence,
        provenance_confidence=spec.provenance_confidence,
        provenance=EvidenceProvenance(
            transcript_id=transcript_id,
            source_interaction_index=interaction.index,
            seq_label=interaction.seq_label,
            extractor_id=extractor_id,
            text_span=spec.text_span,
            extraction_status=status,
        ),
    )
