"""Pure metric functions (no engine required)."""

from __future__ import annotations

from sanuvia_phase1 import metrics
from sanuvia_phase1.trajectory import HypothesisView, InquiryView, TrajectoryRecord


def _rec(
    index: int,
    hyps: tuple[tuple[str, float | None], ...],
    *,
    inquiry: InquiryView | None = None,
    uncertainty: float | None = None,
) -> TrajectoryRecord:
    return TrajectoryRecord(
        condition="c",
        interaction_index=index,
        seq_label=f"seq-{index}",
        ingested_evidence_ids=(),
        hypotheses=tuple(HypothesisView(hid, "s", sup, "active") for hid, sup in hyps),
        inquiry=inquiry,
        predictions=(),
        unsupported_memory_claims=(),
        raw="{}",
        model_uncertainty=uncertainty,
    )


def test_retention_rate() -> None:
    assert metrics.retention_rate(frozenset(), frozenset({"a"})) is None
    assert metrics.retention_rate(frozenset({"a", "b"}), frozenset({"a"})) == 0.5
    assert metrics.retention_rate(frozenset({"a"}), frozenset({"a", "b"})) == 1.0


def test_retention_series_starts_none_then_measures() -> None:
    recs = [
        _rec(1, (("a", 0.4),)),
        _rec(2, (("a", 0.5), ("b", 0.4))),
        _rec(3, (("c", 0.4),)),
    ]
    assert metrics.retention_series(recs) == [None, 1.0, 0.0]
    assert metrics.hypothesis_size_series(recs) == [1, 2, 1]


def test_support_series_fills_gaps_with_none() -> None:
    recs = [
        _rec(1, (("a", 0.4),)),
        _rec(2, (("a", 0.6), ("b", 0.3))),
    ]
    series = metrics.support_series(recs)
    assert series["a"] == [0.4, 0.6]
    assert series["b"] == [None, 0.3]  # absent at interaction 1


def test_uncertainty_series_preserves_none() -> None:
    recs = [_rec(1, (("a", None),), uncertainty=None), _rec(2, (("a", 0.5),), uncertainty=0.4)]
    assert metrics.uncertainty_series(recs) == [None, 0.4]


def test_observed_inquiry_pairs() -> None:
    recs = [
        _rec(1, (("a", 0.4),)),
        _rec(2, (("a", 0.4), ("b", 0.4)), inquiry=InquiryView("inq-1", "?", ("a", "b"))),
    ]
    assert metrics.observed_inquiry_pairs(recs) == [(2, ("a", "b"))]
