"""Demonstrator orchestration.

Drives ONE immutable ordered interaction sequence through each condition and
collects a normalized ``TrajectoryRecord`` per interaction. It enforces the
identical-evidence guarantee: every condition must record exactly the evidence
refs the fixture declares for each interaction (including the empty seq-5 hold);
any deviation fails loudly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .case import Case
from .conditions import (
    ReasoningCondition,
    SanuviaPersistentCondition,
    StatelessFmCondition,
    TranscriptContextFmCondition,
)
from .ports import LanguageModel
from .trajectory import TrajectoryRecord


@dataclass(frozen=True, slots=True)
class DemonstrationReport:
    """Structured result: per-condition trajectory records over the same sequence."""

    case_id: str
    seq_labels: tuple[str, ...]
    evidence_refs_per_interaction: tuple[tuple[str, ...], ...]
    records_by_condition: Mapping[str, tuple[TrajectoryRecord, ...]]


def build_default_conditions(
    case: Case,
    stateless_model: LanguageModel,
    transcript_model: LanguageModel,
) -> list[ReasoningCondition]:
    """The standard trio: Sanuvia persistent + two FM baselines.

    The two FM baselines take a ``LanguageModel`` — a deterministic
    ``ScriptedLanguageModel`` in CI, or a real ``ExternalLanguageModel`` for
    opt-in evaluation.
    """
    return [
        SanuviaPersistentCondition(case),
        StatelessFmCondition(stateless_model),
        TranscriptContextFmCondition(transcript_model),
    ]


def run(case: Case, conditions: Sequence[ReasoningCondition]) -> DemonstrationReport:
    """Run ``conditions`` over the case's single immutable interaction sequence."""
    interactions = case.interactions
    expected_refs = tuple(case.evidence_refs(interaction) for interaction in interactions)

    records_by_condition: dict[str, tuple[TrajectoryRecord, ...]] = {}
    for condition in conditions:
        condition.start()
        records = tuple(condition.step(interaction) for interaction in interactions)
        condition.finish()

        # Identical-evidence guarantee — a condition may not reorder, skip, add,
        # or modify the disclosed evidence.
        for record, refs in zip(records, expected_refs, strict=True):
            if record.ingested_evidence_ids != refs:
                raise ValueError(
                    f"condition {condition.name!r} altered the evidence sequence at "
                    f"{record.seq_label}: {record.ingested_evidence_ids!r} != {refs!r}"
                )
        records_by_condition[condition.name] = records

    return DemonstrationReport(
        case_id=case.case_id,
        seq_labels=tuple(interaction.seq_label for interaction in interactions),
        evidence_refs_per_interaction=expected_refs,
        records_by_condition=records_by_condition,
    )
