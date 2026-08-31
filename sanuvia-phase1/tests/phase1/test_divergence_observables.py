"""C-4 — raw per-point observables only; the aggregate 'rate of behavioural
divergence' (Programme v1.4 C.5) is NOT computed (thresholds/weights deferred).
The hypothesis-id comparison is a DEBUGGING diagnostic, never a semantic
evaluation and never evidence that Sanuvia performs better."""

from __future__ import annotations

import pytest

from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models
from fixtures.longitudinal.case_001 import CASE_001

from sanuvia_phase1 import demonstrator, metrics


def _report() -> demonstrator.DemonstrationReport:
    stateless, transcript = deterministic_language_models()
    conds = demonstrator.build_default_conditions(CASE_001, stateless, transcript)
    return demonstrator.run(CASE_001, conds)


def test_id_based_diagnostics_are_raw_per_point() -> None:
    rep = _report()
    san = list(rep.records_by_condition["sanuvia_persistent"])
    st = list(rep.records_by_condition["fm_stateless"])
    points = metrics.id_based_diagnostics(san, st)

    assert len(points) == len(CASE_001.interactions) == 6
    # Uncertainty is structurally non-comparable: Sanuvia has a float, FM None.
    for p in points:
        assert p.sanuvia_uncertainty is not None
        assert p.baseline_uncertainty is None
        assert p.uncertainty_comparable is False
    # The observable comparisons are exposed as raw booleans.
    assert all(isinstance(p.inquiry_presence_differs, bool) for p in points)
    assert all(isinstance(p.hypothesis_id_sets_differ, bool) for p in points)


def test_id_diagnostic_is_labelled_diagnostic_not_an_evaluation() -> None:
    # The id-based measure carries an explicit "diagnostic only / not evidence of
    # better reasoning / not semantic identity" caveat.
    caveat = metrics.HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT
    assert "DIAGNOSTIC ONLY" in caveat
    assert "not evidence" in caveat.lower()
    assert "semantic" in caveat.lower()


def test_no_aggregate_rate_or_threshold_is_invented() -> None:
    # Governance decision (Run 001): raw observables only; no aggregate is computed.
    assert "raw per-point observables only" in metrics.DIVERGENCE_RATE_STATUS
    assert "no aggregate rate" in metrics.DIVERGENCE_RATE_STATUS
    # No aggregate/threshold/pass-fail/score function is exposed, and the old
    # 'divergence'-named API is gone (renamed to make the diagnostic nature clear).
    for forbidden in (
        "divergence_rate", "divergence_score", "pass_fail", "threshold",
        "divergence_observables",
    ):
        assert not hasattr(metrics, forbidden)


def test_id_based_diagnostics_requires_equal_length() -> None:
    rep = _report()
    san = list(rep.records_by_condition["sanuvia_persistent"])
    st = list(rep.records_by_condition["fm_stateless"])
    with pytest.raises(ValueError):
        metrics.id_based_diagnostics(san, st[:-1])
