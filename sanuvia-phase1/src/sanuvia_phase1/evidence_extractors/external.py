"""ExternalEvidenceExtractor — the real evidence-extraction seam (opt-in).

Provider-neutral: it wraps a caller-injected ``client`` callable that takes an
``ExtractionRequest`` and returns the model's raw JSON reply. No vendor SDK is
imported, no model is chosen, no key is read, and nothing here runs in the
default test/CI path.

The system prompt instructs the model to emit **observations, not inferences**
(evidence-vs-inference boundary). The reply is parsed with a strict structured
reader — not an open-ended NLU parser — and every item is provenance-stamped.

Governance (unresolved — requires governance approval): which provider/model,
access method, temperature/seed, and the exact extraction prompt/schema are **not**
selected here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ..extraction import EvidenceExtractor, ExtractedEvidence, ObservationSpec, stamp
from ..transcript import TranscriptInteraction
from ..validation import validate_extraction


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """A prompt for a real evidence-extraction model."""

    system: str
    transcript_text: str
    instruction: str


ExtractionClient = Callable[[ExtractionRequest], str]

SYSTEM = (
    "You extract EVIDENCE from a snippet of relationship/conversation text for an "
    "internal reasoning experiment. Extract only OBSERVATIONS — what was said or "
    "what happened — NOT interpretations, diagnoses, or inferences about feelings "
    "or motives. Respond with ONLY a JSON object of the form:\n"
    '{"evidence": [{"observation": string, "evidence_class": '
    '"narrative|reflective|behavioural|contradictory|missing|failed_acquisition", '
    '"reliability": number, "classification_confidence": number, '
    '"provenance_confidence": number, "text_span": string|null}]}\n'
    "Return an empty list if the text contains no extractable observation. Do not "
    "output any prose outside the JSON object."
)

INSTRUCTION = "Extract the observations now."


class ExternalEvidenceExtractor:
    """Adapts a caller-supplied extraction client into the ``EvidenceExtractor``
    port. Real runs are **not** guaranteed deterministic."""

    def __init__(
        self, client: ExtractionClient, *, extractor_id: str = "external-extractor"
    ) -> None:
        self._client = client
        self.extractor_id = extractor_id

    def extract(
        self, interaction: TranscriptInteraction, transcript_id: str
    ) -> tuple[ExtractedEvidence, ...]:
        if not interaction.text.strip():
            return ()  # a hold: no raw text -> no evidence
        request = ExtractionRequest(
            system=SYSTEM, transcript_text=interaction.text, instruction=INSTRUCTION
        )
        # Strict validation: malformed output raises MalformedOutputError — it is
        # never coerced into empty evidence or defaulted confidences.
        observations = validate_extraction(self._client(request))
        out: list[ExtractedEvidence] = []
        for k, obs in enumerate(observations, start=1):
            spec = ObservationSpec(
                ref=f"{transcript_id}:{interaction.index}:{k}",
                observation=obs.observation,
                evidence_class=obs.evidence_class,
                reliability=obs.reliability,
                classification_confidence=obs.classification_confidence,
                provenance_confidence=obs.provenance_confidence,
                text_span=obs.text_span,
            )
            out.append(stamp(spec, interaction, transcript_id, self.extractor_id))
        return tuple(out)


def evidence_extractor_from_env() -> EvidenceExtractor:
    """Placeholder factory — intentionally refuses to auto-select a provider (§18).

    Real extraction is opt-in: construct ``ExternalEvidenceExtractor(client=...)``
    explicitly with an approved provider/model and extraction prompt/schema."""
    raise RuntimeError(
        "No evidence-extraction provider is configured. Real extraction is opt-in: "
        "construct ExternalEvidenceExtractor(client=...) with an approved "
        "provider/model and prompt/schema (governance unresolved)."
    )
