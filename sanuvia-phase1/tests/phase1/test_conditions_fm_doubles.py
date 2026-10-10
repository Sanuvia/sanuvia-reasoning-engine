"""Foundation-model baseline conditions (deterministic test doubles)."""

from __future__ import annotations

from fixtures.longitudinal.case_001_baseline_scripts import (
    STATELESS_SCRIPT,
    TRANSCRIPT_SCRIPT,
)

from sanuvia_phase1 import metrics
from sanuvia_phase1.conditions import (
    StatelessFmCondition,
    TranscriptContextFmCondition,
)
from sanuvia_phase1.language_models import ScriptedLanguageModel
from sanuvia_phase1.trajectory import TrajectoryRecord

# We reuse the Case-001 interaction shape but only need the sequence positions;
# text is irrelevant to the deterministic double.
from fixtures.longitudinal.case_001 import CASE_001


def _run(condition_cls: type, script: tuple[str, ...]) -> list[TrajectoryRecord]:
    condition = condition_cls(ScriptedLanguageModel(script))
    condition.start()
    records = [condition.step(i) for i in CASE_001.interactions]
    condition.finish()
    return records


def test_stateless_retains_no_reasoning_state() -> None:
    records = _run(StatelessFmCondition, STATELESS_SCRIPT)
    # A fresh reading each turn -> retention is never positive.
    for rate in metrics.retention_series(records):
        assert rate in (None, 0.0)
    # No new evidence at seq-5 -> nothing to derive.
    assert metrics.hypothesis_size_series(records)[4] == 0
    # Engine-only quantities are absent (never faked).
    for record in records:
        assert record.model_uncertainty is None
        assert record.revision_count is None
        assert record.provenance_traceable is None
        assert record.model_version_id is None
        for view in record.hypotheses:
            assert view.support is None


def test_transcript_collapses_and_makes_unsupported_memory_claims() -> None:
    records = _run(TranscriptContextFmCondition, TRANSCRIPT_SCRIPT)
    # Converges to a single narrative rather than holding competing hypotheses.
    assert all(size <= 1 for size in metrics.hypothesis_size_series(records))
    # Performs textual continuity without a traceable evidence id.
    assert sum(metrics.unsupported_memory_series(records)) > 0
    # Engine-only quantities are absent (never faked).
    for record in records:
        assert record.model_uncertainty is None
        assert record.revision_count is None


def test_transcript_retains_only_text_no_leaked_state() -> None:
    # Two runs of the same condition instance (re-started) are identical — proof it
    # carries no structured state beyond the raw transcript it rebuilds each run.
    condition = TranscriptContextFmCondition(ScriptedLanguageModel(TRANSCRIPT_SCRIPT))
    condition.start()
    first = [condition.step(i) for i in CASE_001.interactions]
    condition2 = TranscriptContextFmCondition(ScriptedLanguageModel(TRANSCRIPT_SCRIPT))
    condition2.start()
    second = [condition2.step(i) for i in CASE_001.interactions]
    assert first == second


def test_stateless_records_evidence_refs_and_condition_name() -> None:
    interaction = CASE_001.interactions[0]  # seq-1: ER-001
    lm = ScriptedLanguageModel(('{"best_explanations": ["a"]}',))
    cond = StatelessFmCondition(lm)
    cond.start()
    rec = cond.step(interaction)
    assert rec.ingested_evidence_ids == ("ER-001",)
    assert rec.condition == "fm_stateless"
