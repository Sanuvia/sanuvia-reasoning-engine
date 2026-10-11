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

import dataclasses

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..extraction import EvidenceExtractor, ExtractedEvidence, ObservationSpec, stamp
from ..transcript import TranscriptInteraction
from sanuvia.domain import GovernedRejection

from ..participants import build_participant_vocabulary
from ..standing import complete_standing
from ..validation import validate_extraction


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """A prompt for a real evidence-extraction model.

    ``participants`` is the request-scoped participant vocabulary (§2 B): the
    only participant references the model may see, and the only ones it may
    name back. Without it the model has no way to know which labels are legal
    and would invent identifiers that the application would then have to guess
    about.
    """

    system: str
    transcript_text: str
    instruction: str
    participants: tuple[str, ...] = ()


ExtractionClient = Callable[[ExtractionRequest], str]

SYSTEM = (
    "You extract EVIDENCE from a snippet of relationship/conversation text for an "
    "internal reasoning experiment. Extract only OBSERVATIONS — what was said or "
    "what happened — NOT interpretations, diagnoses, or inferences about feelings "
    "or motives. Respond with ONLY a JSON object of the form:\n"
    '{"evidence": [{"observation": string, "evidence_class": '
    '"narrative|reflective|behavioural|contradictory|missing|failed_acquisition", '
    '"reliability": number, "classification_confidence": number, '
    '"provenance_confidence": number, "text_span": string|null, '
    '"role": "event_observation|account|response_or_resonance|meta_instruction", '
    '"subject_kind": "participant|dyad|third_party|none", '
    '"subject": participant_label|null}]}\n'
    "role says what the observation IS: event_observation for something that "
    "happened, account for a participant's own telling of it, "
    "response_or_resonance for a reaction to what the system said, "
    "meta_instruction for an instruction about the process itself. "
    "subject says what the observation is ABOUT: it is one of the participant "
    "labels given for this request, exactly as given, and null when "
    "subject_kind is dyad or none. Use only the labels given; do not invent a "
    "participant and do not use a name from the text. Do not state who spoke "
    "-- that is supplied, not yours to decide. Return an empty list if the "
    "text contains no extractable observation. Do not output any prose outside "
    "the JSON object."
)

INSTRUCTION = "Extract the observations now."


class ExternalEvidenceExtractor:
    """Adapts a caller-supplied extraction client into the ``EvidenceExtractor``
    port. Real runs are **not** guaranteed deterministic."""

    def __init__(
        self,
        client: ExtractionClient,
        *,
        extractor_id: str = "external-extractor",
        permitted_participants: Sequence[str] = (),
    ) -> None:
        self._client = client
        self.extractor_id = extractor_id
        #: The authorized participant roster. A CONTEXTUAL fact the application
        #: supplies (§2 E, R2). The CANONICAL ids never leave this object: each
        #: request mints request-scoped labels over them, and only the labels
        #: are sent. A proposed subject outside the vocabulary is a governed
        #: failure, not a value to repair.
        self._permitted = tuple(permitted_participants)

    @property
    def permitted_participants(self) -> tuple[str, ...]:
        """The authorized roster, for the REAL-mode configuration guard.

        Exposed read-only so ``validate_run_configuration`` can refuse an
        unconfigured extractor BEFORE a run starts, rather than letting every
        extracted subject be rejected one at a time with no statement of why.
        """
        return self._permitted

    def extract(
        self, interaction: TranscriptInteraction, transcript_id: str
    ) -> tuple[ExtractedEvidence, ...]:
        if not interaction.text.strip():
            return ()  # a hold: no raw text -> no evidence
        # The request-scoped vocabulary (§2 B). Minted per interaction over the
        # authorized roster, so the labels a reply may name are fixed before
        # the call and a label from another interaction fails resolution rather
        # than aliasing silently.
        vocabulary = build_participant_vocabulary(
            f"{transcript_id}:{interaction.index}", self._permitted
        )
        request = ExtractionRequest(
            system=SYSTEM,
            transcript_text=interaction.text,
            instruction=INSTRUCTION,
            participants=vocabulary.labels,
        )
        # Strict validation: malformed output raises MalformedOutputError — it is
        # never coerced into empty evidence or defaulted confidences.
        raw = self._client(request)
        observations = validate_extraction(raw)
        out: list[ExtractedEvidence] = []
        for k, obs in enumerate(observations, start=1):
            ref = f"{transcript_id}:{interaction.index}:{k}"
            # The application validates the PROPOSED standing and supplies the
            # contextual half itself. An invalid proposal raises
            # EVIDENCE_ROLE_VIOLATION here, which rejects the whole interaction
            # (Q6): no repair, no normalisation, no segment-level partial
            # commit. The complete extraction output is already preserved in
            # the validated observations above.
            try:
                standing = complete_standing(
                    obs.standing,
                    ref=ref,
                    speaker=interaction.speaker,
                    vocabulary=vocabulary,
                )
            except GovernedRejection as rejection:
                # Q6: the COMPLETE extraction output is preserved on the
                # rejection, so the audit can show what the extractor actually
                # returned for the interaction it rejected. Re-raised rather
                # than repaired: no normalisation, no partial commit, and no
                # segment is salvaged.
                raise GovernedRejection(
                    rejection.outcome,
                    rejection.detail,
                    boundary=rejection.boundary,
                    breach_kind=rejection.breach_kind,
                    references=rejection.references,
                    raw_response=raw,
                    provenance=(("extractor_id", self.extractor_id),),
                ) from None
            spec = ObservationSpec(
                ref=ref,
                observation=obs.observation,
                evidence_class=obs.evidence_class,
                reliability=obs.reliability,
                classification_confidence=obs.classification_confidence,
                provenance_confidence=obs.provenance_confidence,
                text_span=obs.text_span,
                standing=obs.standing,  # the proposal, as returned
            )
            stamped = stamp(spec, interaction, transcript_id, self.extractor_id)
            out.append(dataclasses.replace(stamped, standing=standing))
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
