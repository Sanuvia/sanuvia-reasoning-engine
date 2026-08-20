"""ScriptedEvidenceExtractor — a deterministic TEST DOUBLE.

Maps each interaction (by index) to a pre-authored tuple of observation specs and
stamps provenance from the actual interaction. It performs no inference and makes
no network call, so the transcript path stays byte-identically reproducible. This
is the extraction-layer equivalent of ``ScriptedLanguageModel``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..extraction import ExtractedEvidence, ObservationSpec, stamp
from ..transcript import TranscriptInteraction


class ScriptedEvidenceExtractor:
    """Returns pre-authored observations per interaction index (provenance stamped).

    Unknown/empty interactions yield no evidence (a hold). Implements
    ``EvidenceExtractor``."""

    def __init__(
        self,
        script: Mapping[int, Sequence[ObservationSpec]],
        *,
        extractor_id: str = "scripted-extractor-v1",
    ) -> None:
        self.extractor_id = extractor_id
        self._script: dict[int, tuple[ObservationSpec, ...]] = {
            index: tuple(specs) for index, specs in script.items()
        }

    def extract(
        self, interaction: TranscriptInteraction, transcript_id: str
    ) -> tuple[ExtractedEvidence, ...]:
        specs = self._script.get(interaction.index, ())
        return tuple(
            stamp(spec, interaction, transcript_id, self.extractor_id) for spec in specs
        )
