"""The participant labels must survive prompt composition (§2 B).

The v3 extraction system prompt tells the model that ``subject`` "is one of the
participant labels given for this request". ``ExternalEvidenceExtractor`` mints
those labels and puts them on ``ExtractionRequest.participants`` -- and
``compose_extraction_prompt`` dropped them. The model was therefore asked to
name a label it had never been shown, so every proposed subject was refused by
the vocabulary for being unoffered, and the boundary could only ever fail.

Asserting the request object would not have caught that: the request was always
correct. These tests inspect the string the **backend actually receives**,
through the real ``QwenClient`` extraction path, and then follow the reply back
through to the canonical participant id.

Offline throughout: the backend is a fake in this process. No provider is
selected, no network is reached, no model inference is run.
"""

from __future__ import annotations

import json

import pytest

from sanuvia.domain import GovernedOutcome, GovernedRejection

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.extraction import ExtractedEvidence
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.participants import build_participant_vocabulary
from sanuvia_phase1.qwen import (
    GenerationParams,
    QwenClient,
    QwenRuntimeInfo,
    qwen_real_run_config,
)
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

#: Canonical participant ids. These must never appear in a prompt.
ROSTER = ("pA", "pB")
TRANSCRIPT_ID = "t-boundary"
INTERACTION = 1

#: The labels this request offers, derived from the same function the extractor
#: uses rather than restated, so the test cannot drift from the implementation.
VOCABULARY = build_participant_vocabulary(f"{TRANSCRIPT_ID}:{INTERACTION}", ROSTER)


class _RecordingBackend:
    """A fake Qwen backend that records every prompt it is handed."""

    def __init__(self, reply: str) -> None:
        self.prompts: list[str] = []
        self._reply = reply

    def describe(self) -> QwenRuntimeInfo:
        return QwenRuntimeInfo(
            backend_id="fake-offline",
            model_id="qwen3-4b",
            model_version=Maybe.available("fake-2024.1"),
            artifact_id=Maybe.available("/models/fake-qwen3-4b.gguf"),
            context_window=8192,
        )

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.prompts.append(prompt)
        return self._reply


def _client(backend: _RecordingBackend) -> QwenClient:
    """The production client, with the real manifest recorder attached."""
    transcript = Transcript(
        TRANSCRIPT_ID,
        SubjectId("s-boundary"),
        shared_space_id("dyad-boundary"),
        (TranscriptInteraction(INTERACTION, "seq-1", "it ran late", speaker="pA"),),
    )
    builder = RunManifestBuilder(
        run_id="boundary",
        created_at="2026-01-01T00:00:00Z",
        git_commit_sha="sha",
        phase1_version="0.1.0",
        mode="real",
        transcript=transcript,
        model_specs=qwen_real_run_config(participants=ROSTER).specs(),
    )
    return QwenClient(
        backend,
        GenerationParams(
            temperature=0.0, max_output_tokens=128, context_tokens=4096, seed=0
        ),
        builder,
    )


def _label(participant: str) -> str:
    label = VOCABULARY.label_for(participant)
    assert label is not None, participant
    return label


def _reply(subject: object) -> str:
    return json.dumps(
        {
            "evidence": [
                {
                    "observation": "the evening ran late",
                    "evidence_class": "narrative",
                    "reliability": 0.8,
                    "classification_confidence": 0.9,
                    "provenance_confidence": 0.9,
                    "text_span": None,
                    "role": "account",
                    "subject_kind": "participant",
                    "subject": subject,
                }
            ]
        }
    )


def _extract(
    subject: object,
) -> tuple[_RecordingBackend, tuple[ExtractedEvidence, ...]]:
    """Drive the REAL QwenClient extraction path over a fake backend.

    ``client.as_extractor`` builds the production ``ExternalEvidenceExtractor``
    over ``client.extraction_client()``, which composes the prompt and calls
    ``backend.generate``. Nothing here is stubbed except the backend itself.
    """
    backend = _RecordingBackend(_reply(subject))
    extractor = _client(backend).as_extractor(permitted_participants=ROSTER)
    extracted = extractor.extract(
        TranscriptInteraction(
            INTERACTION, "seq-1", "it ran late", speaker="pA"
        ),
        TRANSCRIPT_ID,
    )
    return backend, extracted


# --- 1. the offered labels reach the backend --------------------------------


def test_the_offered_labels_reach_the_prompt_the_backend_receives() -> None:
    """The defining assertion: inspect the generated string, not the request."""
    backend, _ = _extract(_label("pB"))

    (prompt,) = backend.prompts
    assert "PARTICIPANT LABELS:" in prompt
    for label in VOCABULARY.labels:
        assert label in prompt, f"{label} never reached the backend"


def test_the_prompt_offers_exactly_the_requests_labels_and_no_others() -> None:
    """Exactly the request's vocabulary -- not a superset, not a stale set."""
    import re

    backend, _ = _extract(_label("pB"))
    (prompt,) = backend.prompts

    section = prompt.split("PARTICIPANT LABELS:\n", 1)[1].split("\n\n", 1)[0]
    assert [s.strip() for s in section.split(",")] == list(VOCABULARY.labels)
    # And no label minted for any other request appears anywhere in the prompt.
    found = set(re.findall(rf"{re.escape(TRANSCRIPT_ID)}:\d+::P\d+", prompt))
    assert found == set(VOCABULARY.labels)


def test_a_different_interaction_offers_different_labels() -> None:
    """Request-scoped means the backend sees interaction 2's labels, not 1's."""
    other = build_participant_vocabulary(f"{TRANSCRIPT_ID}:2", ROSTER)
    # Interaction 2's OWN label, so the reply is valid there and the test is
    # about which labels were offered rather than about a rejection.
    backend = _RecordingBackend(_reply(other.label_for("pB")))
    extractor = _client(backend).as_extractor(permitted_participants=ROSTER)
    extractor.extract(
        TranscriptInteraction(2, "seq-2", "later still", speaker="pA"), TRANSCRIPT_ID
    )

    (prompt,) = backend.prompts
    for label in other.labels:
        assert label in prompt
    for label in VOCABULARY.labels:
        assert label not in prompt, "interaction 1's label leaked into interaction 2"


# --- 2. no canonical identifier is exposed ----------------------------------


def test_no_canonical_roster_id_appears_in_the_prompt() -> None:
    """A model that cannot see a ParticipantId cannot assign one.

    The labels embed no canonical id, so the whole prompt is searched -- not
    only the participant section -- and the transcript text is chosen so that
    neither id occurs in it naturally.
    """
    backend, _ = _extract(_label("pB"))
    (prompt,) = backend.prompts

    for canonical in ROSTER:
        assert canonical not in prompt, f"canonical id {canonical!r} reached the prompt"


def test_the_speaker_is_never_sent_even_though_the_application_knows_it() -> None:
    """Who spoke is supplied, not asked. ``pA`` is the speaker and is still
    absent from the prompt."""
    backend, _ = _extract(_label("pB"))
    (prompt,) = backend.prompts

    assert "pA" not in prompt
    assert "speaker" not in prompt.lower().split("PARTICIPANT LABELS:")[0].replace(
        "do not state who spoke", ""
    )


# --- 3. a returned label maps back to the right canonical participant -------


def test_a_returned_offered_label_maps_to_the_correct_canonical_participant() -> None:
    """The round trip, end to end: pB -> label -> prompt -> reply -> pB."""
    _, extracted = _extract(_label("pB"))

    (evidence,) = extracted
    assert evidence.standing is not None
    assert evidence.standing.subject_id == "pB"


def test_the_other_label_maps_to_the_other_participant() -> None:
    """Proves the mapping is a mapping, not a constant."""
    _, extracted = _extract(_label("pA"))

    (evidence,) = extracted
    assert evidence.standing is not None
    assert evidence.standing.subject_id == "pA"


# --- 4. an unoffered label is still rejected --------------------------------


def test_an_unoffered_label_is_still_rejected_through_the_governed_path() -> None:
    """Carrying the labels must not have turned the vocabulary into a
    formality: a label this request did not offer is still refused."""
    with pytest.raises(GovernedRejection) as exc:
        _extract(f"{TRANSCRIPT_ID}:{INTERACTION}::P9")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    assert "was not supplied in request" in str(exc.value)


def test_a_canonical_id_in_the_reply_is_still_rejected() -> None:
    """``pB`` is authorized and is still refused: it was never offered, and the
    application must not infer that a model string is a canonical reference."""
    with pytest.raises(GovernedRejection) as exc:
        _extract("pB")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_a_label_from_another_interaction_is_still_rejected() -> None:
    other = build_participant_vocabulary(f"{TRANSCRIPT_ID}:2", ROSTER)

    with pytest.raises(GovernedRejection) as exc:
        _extract(other.label_for("pB"))

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_the_rejection_still_carries_the_raw_reply_and_provenance() -> None:
    """Q6 provenance survives the change."""
    with pytest.raises(GovernedRejection) as exc:
        _extract("pB")

    assert exc.value.raw_response is not None
    assert "pB" in exc.value.raw_response
    assert any(k == "extractor_id" for k, _ in exc.value.provenance)
