"""Case 001 as a raw TRANSCRIPT + a deterministic golden extractor.

This connects the real transcript path to the existing authored-evidence path:

    raw transcript text
        -> ScriptedEvidenceExtractor (golden)
        -> the SAME Case-001 observations
        -> frozen Phase 0

The scripted extractor maps each interaction to the exact `CaseEvidence`
observations authored in ``case_001`` (same ref, content,
class, reliability, confidences), so the extracted-evidence Sanuvia trajectory is
**identical** to the structured-fixture Sanuvia trajectory (asserted by test).

The raw ``_TEXT`` snippets are illustrative surface text; in golden mode the
scripted extractor returns the known observations regardless of surface wording.
seq-5 is a genuine reflective pause (empty text → no new evidence).
"""

from __future__ import annotations

from fixtures.longitudinal.case_001 import (
    APPRAISAL_SCRIPT,
    CASE_001,
    HYPOTHESIS_CATALOGUE,
    SPACE,
    SUBJECT,
)

from sanuvia_phase1.case import CaseInteraction
from sanuvia_phase1.evidence_extractors import ScriptedEvidenceExtractor
from sanuvia_phase1.extraction import ObservationSpec
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

# Illustrative raw conversation text per sequence position (seq-5 is a hold).
_TEXT: dict[int, str] = {
    1: "Person 1: If they say no to the promotion, I'll use that as the signal to "
    "plan my exit — there's no growth for me here.",
    2: "Person 1: A few of us MDs, me and MD-1 included, don't share the same view "
    "of how the organisation should be governed. And I don't want to spend another "
    "year proving my worth.",
    3: "Person 1: I look at ED-A and ED-B and I'm at their level; ED-B built the "
    "stakeholder trust, I've been the foundation people use to drive decisions.",
    4: "Person 1: 2026 was about proving my leadership; 2027 is about building and "
    "establishing it — another promotion cycle would feel repetitive. (Partner "
    "referenced earlier delivery/resource plans and analysis leaders used.)",
    5: "",  # a reflective pause — no new evidence this turn
    6: "Person 1: Perfect, I feel better. I don't need to shrink to silence to "
    "avoid upsetting an MD; I listen and adapt, and I don't expect their reasoning "
    "to always make sense to me.",
}


def _specs_for(interaction: CaseInteraction) -> tuple[ObservationSpec, ...]:
    """Build observation specs from the authored Case-001 evidence (guarantees the
    extracted observations match the structured fixture exactly)."""
    return tuple(
        ObservationSpec(
            ref=ce.ref,
            observation=ce.text,  # RawObservation only — no interpretation
            evidence_class=ce.evidence_class,
            reliability=ce.reliability,
            classification_confidence=ce.classification_confidence,
            provenance_confidence=ce.provenance_confidence,
            text_span=None,
        )
        for ce in interaction.evidence
    )


CASE_001_TRANSCRIPT = Transcript(
    transcript_id="case-001-leadership-trajectory",
    subject_id=SUBJECT,
    space_id=SPACE,
    interactions=tuple(
        TranscriptInteraction(i.index, i.seq_label, _TEXT[i.index])
        for i in CASE_001.interactions
    ),
)

CASE_001_EXTRACTOR_SCRIPT: dict[int, tuple[ObservationSpec, ...]] = {
    i.index: _specs_for(i) for i in CASE_001.interactions
}

# Re-exports used by the transcript pipeline (appraisal stays a Phase-0 concern).
CASE_001_APPRAISAL_SCRIPT = APPRAISAL_SCRIPT
CASE_001_HYPOTHESIS_CATALOGUE = HYPOTHESIS_CATALOGUE


def case_001_scripted_extractor() -> ScriptedEvidenceExtractor:
    return ScriptedEvidenceExtractor(
        CASE_001_EXTRACTOR_SCRIPT, extractor_id="case-001-golden-extractor"
    )
