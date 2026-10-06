"""Transcript input — the real Phase 1 front end.

A :class:`Transcript` is an ordered sequence of raw conversation-text interactions
(longitudinal order preserved). It is deliberately *dumb data*: it carries no
structured evidence, no hypotheses, and no reasoning state. Turning raw text into
structured observations is the job of an :class:`~sanuvia_phase1.extraction.EvidenceExtractor`;
forming hypotheses from that evidence is the job of the frozen Phase 0 engine.

An interaction with empty ``text`` is a genuine no-new-evidence *hold*.
"""

from __future__ import annotations

from dataclasses import dataclass

from sanuvia.domain import SpaceId, SubjectId


@dataclass(frozen=True, slots=True)
class TranscriptInteraction:
    """One turn of raw conversation text. ``text`` is empty for a genuine hold."""

    index: int
    seq_label: str
    text: str
    #: The participant who spoke this turn, where the transcript records one.
    #:
    #: A CONTEXTUAL fact, so the application supplies it and it is never asked
    #: of the model and never accepted from it (§2 E, R2). It determines
    #: ``standing.source_kind`` and ``standing.source_id``.
    speaker: str | None = None


@dataclass(frozen=True, slots=True)
class Transcript:
    """An ordered, immutable sequence of raw-text interactions for one subject."""

    transcript_id: str
    subject_id: SubjectId
    space_id: SpaceId
    interactions: tuple[TranscriptInteraction, ...]
