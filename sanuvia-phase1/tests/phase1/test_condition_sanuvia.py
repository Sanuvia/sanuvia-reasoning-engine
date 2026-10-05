"""Sanuvia Persistent condition — hypothesis retention, revision, silence-hold,
prediction, uncertainty, provenance, and the OBSERVED inquiry selection."""

from __future__ import annotations

from _identity_support import durable_ids

from fixtures.longitudinal.case_001 import CASE_001
from fixtures.longitudinal.case_001 import H1, H2, H3, H4

from sanuvia_phase1 import metrics
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.trajectory import TrajectoryRecord


def _run() -> list[TrajectoryRecord]:
    records, _ = _run_with_ids()
    return records


def _run_with_ids() -> tuple[list[TrajectoryRecord], dict[str, str]]:
    """Run Case 001 and return the authored-id -> durable-id mapping.

    Technical Design v1.5.4 / locked §3.3: the **engine** issues every durable
    hypothesis id, so the fixture's authored ids (H1..H4) are no longer the
    identity the engine reports. The Scripted fixture migration carries the
    authored id in the lineage attribution, which is what lets these tests keep
    asserting the *same four lineages* at full strength rather than weakening to
    a count.

    Case 001 behaviour is otherwise unchanged: four distinct lineages, identical
    retention, identical uncertainty, identical observed inquiry pairs, and H1's
    support series is still [None, None, None, 0.4, 0.4, 0.64].
    """
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    records = [condition.step(i) for i in CASE_001.interactions]
    condition.finish()
    mapping = durable_ids(condition._store, CASE_001)
    assert len(mapping) == 4, f"expected four lineages, got {mapping}"
    return records, mapping


def test_all_four_hypotheses_live_from_interaction_four() -> None:
    records, durable = _run_with_ids()
    ids = metrics.hypothesis_ids(records[3])  # seq-4
    assert {durable[H1], durable[H2], durable[H3], durable[H4]} <= ids


def test_hypotheses_retained_through_hold_and_to_end() -> None:
    records, durable = _run_with_ids()
    expected = {durable[H1], durable[H2], durable[H3], durable[H4]}
    for record in records[3:]:  # seq-4, seq-5 (hold), seq-6
        assert expected <= metrics.hypothesis_ids(record)
    assert metrics.retention_series(records) == [None, 1.0, 1.0, 1.0, 1.0, 1.0]


def test_support_is_revised_and_h1_crosses_prediction_threshold() -> None:
    records, durable = _run_with_ids()
    support = metrics.support_series(records)
    h1 = support[durable[H1]]
    assert h1 == [None, None, None, 0.4, 0.4, 0.64]  # proposed, held, then strengthened
    assert h1[5] is not None and h1[5] > 0.6


def test_prediction_forms_only_once_h1_crosses_threshold() -> None:
    records = _run()
    assert metrics.prediction_count_series(records) == [0, 0, 0, 0, 0, 1]
    final = records[5].predictions
    assert len(final) == 1
    assert final[0].likelihood == 0.64
    # No relationship-failure trajectory is ever produced (structural Phase 0 guard).
    assert final[0].trajectory_kind == "observed_trajectory"


def test_uncertainty_is_non_monotonic() -> None:
    records = _run()
    series = metrics.uncertainty_series(records)
    assert series == [0.3, 0.5, 0.425, 0.425, 0.425, 0.455]
    # It both rises and falls (not "merely decreasing").
    rises = falls = False
    for i in range(1, len(series)):
        prev, cur = series[i - 1], series[i]
        if prev is None or cur is None:
            continue
        if cur > prev:
            rises = True
        if cur < prev:
            falls = True
    assert rises and falls


def test_seq5_is_a_genuine_hold_silence_is_not_disconfirmation() -> None:
    records, durable = _run_with_ids()
    seq4, seq5 = records[3], records[4]
    assert seq5.seq_label == "seq-5"
    assert seq5.ingested_evidence_ids == ()          # no new evidence
    assert seq5.revision_count == 0                  # model holds
    assert seq5.model_uncertainty == seq4.model_uncertainty  # unchanged
    # hypotheses and their supports are unchanged across the hold.
    before = {h.hypothesis_id: h.support for h in seq4.hypotheses}
    after = {h.hypothesis_id: h.support for h in seq5.hypotheses}
    assert before == after
    # H4, which never received contradicting evidence, keeps its support across
    # the hold. The value is 0.4, not the fixture's authored 0.3: R6 derives a
    # DISTINCT_NEW lineage's initial support from the existing mechanism,
    # support_after_support(0.0, reliability=0.8, learning_rate=0.5) = 0.4. The
    # model no longer supplies a support value (locked §4).
    assert after[durable[H4]] == 0.4


def test_provenance_traceable_whenever_a_revision_committed() -> None:
    records = _run()
    for record in records:
        if record.revision_count and record.revision_count > 0:
            assert record.provenance_traceable is True


def test_inquiry_is_surfaced_and_observed_pair_is_recorded_not_engineered() -> None:
    records, durable = _run_with_ids()
    # An inquiry is surfaced (uncertainty is not narratively resolved to one answer).
    assert any(metrics.inquiry_presence_series(records))
    # The model stays unresolved (>=2 live hypotheses) while inquiries are open.
    for record in records:
        if record.inquiry is not None:
            assert len(record.hypotheses) >= 2

    pairs = metrics.observed_inquiry_pairs(records)
    # OBSERVED result (recorded verbatim, not engineered): the frozen support-driven
    # top-two selection pairs H3/H2, H2/H3, H2/H1, H1/H2 across interactions 2,3,4,6.
    # Unchanged from the pre-v1.5.4 observation once the authored ids are mapped
    # to the engine-issued ones: the same four pairs, in the same order.
    assert pairs == [
        (2, (durable[H3], durable[H2])),
        (3, (durable[H2], durable[H3])),
        (4, (durable[H2], durable[H1])),
        (6, (durable[H1], durable[H2])),
    ]
    # OBSERVED LIMITATION: the fixture's discriminating pair (H1 vs H4) is NEVER
    # auto-selected — targeted-EIG inquiry selection is deferred (not in Phase 0).
    for _idx, activated in pairs:
        assert frozenset(activated) != frozenset({durable[H1], durable[H4]})
