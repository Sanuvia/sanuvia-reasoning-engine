"""Transcript pipeline — the real Phase 1 flow.

    raw transcript text -> EvidenceExtractor -> structured evidence
                                              -> frozen Phase 0 reasoning (Sanuvia)
    raw transcript text -> FM baselines (stateless / transcript-context)

Two explicit modes (never mixed silently):

* ``GOLDEN`` — a ``ScriptedEvidenceExtractor`` yields known evidence; fully
  deterministic (regression / replay / equivalence checks).
* ``REAL``   — an ``ExternalEvidenceExtractor`` (injected client) extracts from
  real text; the run is tagged ``REAL`` and is not guaranteed deterministic.

Fairness (Programme v1.4 Part 4A): the **Sanuvia** condition reasons over the
**extracted structured evidence**; the **FM baselines** read the **raw transcript
text** (stateless: current turn; transcript-context: all prior turns) with **no**
structured Sanuvia state. All three are driven through the *same ordered
interaction sequence* — a guard enforces identical seq labels.

Extraction (raw text -> observation) is done here; **appraisal** (observation ->
which hypotheses) remains the frozen Phase 0 ``EvidenceAppraiser`` port, supplied
as ``appraisal_script`` — the extractor never forms hypotheses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from sanuvia.application.ports.reasoning import Appraisal, EvidenceAppraiser
from sanuvia.domain import EvidenceClass, EvidenceRecordId

from .case import Case, CaseEvidence, CaseInteraction
from .conditions import (
    SanuviaPersistentCondition,
    StatelessFmCondition,
    TranscriptContextFmCondition,
)
from .demonstrator import DemonstrationReport
from .extraction import EvidenceExtractor, EvidenceProvenance, ExtractionResult
from .ports import LanguageModel
from .runconfig import GOLDEN, REAL, RealRunConfig, validate_run_configuration
from .transcript import Transcript
from .trajectory import TrajectoryRecord

__all__ = [
    "GOLDEN",
    "REAL",
    "ExtractedCase",
    "TranscriptDemonstrationReport",
    "build_extracted_case",
    "run_transcript_demonstration",
]


@dataclass(frozen=True, slots=True)
class ExtractedCase:
    """A ``Case`` built from a transcript, plus the per-interaction extraction audit."""

    case: Case
    extractions: tuple[ExtractionResult, ...]
    extractor_id: str
    mode: str


@dataclass(frozen=True, slots=True)
class TranscriptDemonstrationReport:
    """A demonstration produced from raw transcript text — tagged with its mode
    and extractor so a reader always knows how the run was produced."""

    mode: str
    extractor_id: str
    transcript_id: str
    extractions: tuple[ExtractionResult, ...]
    demonstration: DemonstrationReport


def _provenance_source(p: EvidenceProvenance) -> str:
    return (
        f"extractor:{p.extractor_id}; transcript:{p.transcript_id}; "
        f"interaction:{p.source_interaction_index}"
    )


def _provenance_metadata(p: EvidenceProvenance) -> tuple[tuple[str, str], ...]:
    return (
        ("extractor_id", p.extractor_id),
        ("transcript_id", p.transcript_id),
        ("source_interaction_index", str(p.source_interaction_index)),
        ("seq_label", p.seq_label),
        ("extraction_status", p.extraction_status),
        ("text_span", p.text_span or ""),
    )


def build_extracted_case(
    transcript: Transcript,
    extractor: EvidenceExtractor,
    appraisal_script: Mapping[EvidenceRecordId, Appraisal],
    hypothesis_catalogue: Mapping[str, str],
    *,
    case_id: str,
    mode: str,
    on_interaction_start: Callable[[int, str], None] | None = None,
) -> ExtractedCase:
    """Run the extractor over the transcript and assemble a ``Case`` (structured
    evidence + the authored appraisal). Engine ids are assigned in extraction
    order so the appraisal script (keyed by engine id) lines up.

    ``on_interaction_start(index, seq_label)`` is a generic per-interaction hook
    (used by the manifest-recording Qwen client to attribute each call)."""
    interactions: list[CaseInteraction] = []
    extractions: list[ExtractionResult] = []
    counter = 0
    for ti in transcript.interactions:
        if on_interaction_start is not None:
            on_interaction_start(ti.index, ti.seq_label)
        extracted = extractor.extract(ti, transcript.transcript_id)
        extractions.append(ExtractionResult(ti.index, ti.seq_label, extracted))
        evidence: list[CaseEvidence] = []
        for ev in extracted:
            counter += 1
            evidence.append(
                CaseEvidence(
                    ref=ev.ref,
                    engine_id=f"evidence-{counter}",
                    text=ev.observation,  # RawObservation only
                    evidence_class=ev.evidence_class,
                    reliability=ev.reliability,
                    classification_confidence=ev.classification_confidence,
                    provenance_confidence=ev.provenance_confidence,
                    source=_provenance_source(ev.provenance),
                    evidence_role="",
                    acquisition_metadata=_provenance_metadata(ev.provenance),
                )
            )
        interactions.append(CaseInteraction(ti.index, ti.seq_label, tuple(evidence)))

    case = Case(
        case_id=case_id,
        subject_id=transcript.subject_id,
        space_id=transcript.space_id,
        interactions=tuple(interactions),
        appraisal_script=appraisal_script,
        hypothesis_catalogue=hypothesis_catalogue,
    )
    return ExtractedCase(case, tuple(extractions), extractor.extractor_id, mode)


def _raw_text_interactions(transcript: Transcript) -> list[CaseInteraction]:
    """Wrap each raw turn as a single-'evidence' interaction carrying the raw text,
    so the FM baselines read conversation TEXT (not structured Sanuvia evidence).
    Holds (empty text) carry no turn."""
    out: list[CaseInteraction] = []
    for ti in transcript.interactions:
        if ti.text.strip():
            turn = CaseEvidence(
                ref=f"turn-{ti.index}",
                engine_id="",
                text=ti.text,
                evidence_class=EvidenceClass.NARRATIVE,
                reliability=0.5,
                classification_confidence=0.5,
                provenance_confidence=0.5,
                source="raw-transcript",
                evidence_role="",
            )
            out.append(CaseInteraction(ti.index, ti.seq_label, (turn,)))
        else:
            out.append(CaseInteraction(ti.index, ti.seq_label, ()))
    return out


def run_transcript_demonstration(
    transcript: Transcript,
    extractor: EvidenceExtractor,
    appraisal_script: Mapping[EvidenceRecordId, Appraisal],
    hypothesis_catalogue: Mapping[str, str],
    stateless_model: LanguageModel,
    transcript_model: LanguageModel,
    *,
    case_id: str,
    mode: str,
    appraiser: EvidenceAppraiser | None = None,
    config: RealRunConfig | None = None,
    on_interaction_start: Callable[[int, str], None] | None = None,
) -> TranscriptDemonstrationReport:
    """Drive all three conditions from one transcript and return a mode-tagged report.

    ``appraiser`` is the frozen Phase 0 ``EvidenceAppraiser`` boundary. ``None``
    (golden default) uses the case's ``ScriptedAppraiser``; real mode injects a
    real ``EvidenceAppraiser`` (e.g. ``ExternalEvidenceAppraiser``). The frozen
    engine still owns all model revision and persistence.

    ``config`` is required for ``mode=REAL`` and forbidden for ``mode=GOLDEN``.
    The mode↔components consistency is checked BEFORE any execution: a GOLDEN run
    may use only scripted doubles, and a REAL run may not fall back to any scripted
    double and must carry a complete :class:`RealRunConfig`. A mis-configured run
    raises :class:`ConfigurationError` here, before the engine or any model runs."""
    validate_run_configuration(
        mode,
        extractor=extractor,
        stateless_model=stateless_model,
        transcript_model=transcript_model,
        appraiser=appraiser,
        config=config,
    )
    extracted = build_extracted_case(
        transcript, extractor, appraisal_script, hypothesis_catalogue,
        case_id=case_id, mode=mode, on_interaction_start=on_interaction_start,
    )

    def _mark(interaction: CaseInteraction) -> CaseInteraction:
        if on_interaction_start is not None:
            on_interaction_start(interaction.index, interaction.seq_label)
        return interaction

    # Sanuvia reasons over EXTRACTED structured evidence (persistent World Model).
    sanuvia = SanuviaPersistentCondition(extracted.case, appraiser)
    sanuvia.start()
    san_records = tuple(sanuvia.step(_mark(i)) for i in extracted.case.interactions)
    sanuvia.finish()

    # FM baselines read RAW transcript text — no structured Sanuvia state.
    raw = _raw_text_interactions(transcript)
    stateless = StatelessFmCondition(stateless_model)
    stateless.start()
    st_records = tuple(stateless.step(_mark(i)) for i in raw)
    stateless.finish()
    context = TranscriptContextFmCondition(transcript_model)
    context.start()
    tc_records = tuple(context.step(_mark(i)) for i in raw)
    context.finish()

    # Fairness guard: same ordered interaction sequence for all three conditions.
    seq = tuple(ti.seq_label for ti in transcript.interactions)
    records_by_condition: dict[str, tuple[TrajectoryRecord, ...]] = {
        "sanuvia_persistent": san_records,
        "fm_stateless": st_records,
        "fm_transcript": tc_records,
    }
    for name, recs in records_by_condition.items():
        got = tuple(r.seq_label for r in recs)
        if got != seq:
            raise ValueError(
                f"condition {name!r} interaction sequence {got!r} != {seq!r}"
            )

    demonstration = DemonstrationReport(
        case_id=case_id,
        seq_labels=seq,
        evidence_refs_per_interaction=tuple(
            extracted.case.evidence_refs(i) for i in extracted.case.interactions
        ),
        records_by_condition=records_by_condition,
    )
    return TranscriptDemonstrationReport(
        mode=mode,
        extractor_id=extracted.extractor_id,
        transcript_id=transcript.transcript_id,
        extractions=extracted.extractions,
        demonstration=demonstration,
    )
