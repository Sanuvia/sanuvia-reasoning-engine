"""ExternalEvidenceExtractor — the real evidence-extraction seam (opt-in).

Provider-neutral: it wraps a caller-injected ``client`` callable that takes an
``ExtractionRequest`` and returns the model's raw JSON reply. No vendor SDK is
imported, no model is chosen, no key is read, and nothing here runs in the
default test/CI path.

The system prompt instructs the model to emit **observations, not inferences**
(evidence-vs-inference boundary). The reply is parsed with a strict structured
reader — not an open-ended NLU parser — and every item is provenance-stamped.

Governance (unresolved — requires Felix/both developers): which provider/model,
access method, temperature/seed, and the exact extraction prompt/schema are **not**
selected here.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sanuvia.domain import EvidenceClass

from ..extraction import EvidenceExtractor, ExtractedEvidence, ObservationSpec, stamp
from ..transcript import TranscriptInteraction


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


def _to_class(value: str) -> EvidenceClass:
    try:
        return EvidenceClass(value.strip().lower())
    except ValueError as exc:  # fail loud rather than silently mislabel evidence
        raise ValueError(f"unknown evidence_class from extractor: {value!r}") from exc


def _num(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default


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
        data: Any = json.loads(self._client(request))
        if not isinstance(data, dict):
            raise ValueError("extractor response must be a JSON object")

        out: list[ExtractedEvidence] = []
        items = data.get("evidence", []) or []
        for k, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            span = item.get("text_span")
            spec = ObservationSpec(
                ref=f"{transcript_id}:{interaction.index}:{k}",
                observation=str(item.get("observation", "")),
                evidence_class=_to_class(str(item.get("evidence_class", "reflective"))),
                reliability=_num(item.get("reliability"), 0.5),
                classification_confidence=_num(item.get("classification_confidence"), 0.5),
                provenance_confidence=_num(item.get("provenance_confidence"), 0.5),
                text_span=None if span is None else str(span),
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
