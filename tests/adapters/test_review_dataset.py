"""Machine-verification of the engineering review dataset.

Runs every dataset Test Case step-by-step through the real engine and asserts the
documented per-step expected reasoning evolution actually holds. This both
validates the dataset annotations and regression-tests the engine's behaviour
across all major reasoning behaviours. The engine is unchanged; the dataset lives
entirely above the API.
"""

from __future__ import annotations

from typing import Any

import pytest

from sanuvia.adapters.http import controllers
from sanuvia.adapters.http.manager import TestCaseManager
from sanuvia.adapters.http.review_dataset import DATASET


def _predictions(state: dict[str, Any]) -> set[str]:
    return {p["from_hypotheses"][0] for p in state["predictions"]}


@pytest.mark.parametrize("case", DATASET, ids=[c["id"] for c in DATASET])
def test_dataset_case_matches_expected_evolution(case: dict[str, Any]) -> None:
    mgr = TestCaseManager()
    controllers.load_sample(mgr, {"sample_id": case["id"]})
    exps = case["step_expectations"]
    assert len(exps) == len(case["evidence_specs"]), f"{case['id']}: expectation count"

    prev_u: float | None = None
    for i, exp in enumerate(exps, start=1):
        state = controllers.run_next(mgr)
        where = f"{case['id']} step {i}"

        # WorldModel version + commit/hold
        assert state["world_model"] is not None, f"{where}: no committed model"
        assert state["world_model"]["version"] == exp["version"], f"{where}: version"
        assert state["timeline"][i - 1]["committed"] == exp["committed"], f"{where}: committed"

        # Inquiry presence
        assert bool(state["inquiries"]) == exp["inquiry"], f"{where}: inquiry"

        # Active predictions (by originating hypothesis)
        assert _predictions(state) == set(exp["predictions"]), f"{where}: predictions"

        # Anomaly disposition
        dispositions = [a["disposition"] for a in state["anomaly_resolutions"]]
        if exp["anomaly"] is None:
            assert not dispositions, f"{where}: unexpected anomaly {dispositions}"
        else:
            assert exp["anomaly"] in dispositions, f"{where}: expected {exp['anomaly']}"

        # ModelUncertainty trend
        u = state["model_uncertainty"]
        assert u is not None, f"{where}: uncertainty"
        trend = exp["uncertainty"]
        if trend == "first":
            assert prev_u is None
        elif trend == "up":
            assert u > prev_u, f"{where}: expected up ({prev_u}->{u})"  # type: ignore[operator]
        elif trend == "down":
            assert u < prev_u, f"{where}: expected down ({prev_u}->{u})"  # type: ignore[operator]
        elif trend == "flat":
            assert abs(u - prev_u) < 1e-9, f"{where}: expected flat ({prev_u}->{u})"  # type: ignore[operator]
        prev_u = u

    # Determinism: an independent rerun reproduces identical reasoning.
    mgr2 = TestCaseManager()
    controllers.load_sample(mgr2, {"sample_id": case["id"]})
    s2 = controllers.run_all(mgr2)
    s1 = controllers.get_state(mgr)

    def rkey(s: dict[str, Any]) -> Any:
        return (
            s["model_uncertainty"],
            s["world_model"]["version"],
            tuple((h["hypothesis_id"], h["support"]) for h in s["hypotheses"]),
            tuple(e["id"] for e in s["evidence"]),
            tuple(x["event"]["outcome"] for x in s["revision_ledger"]),
        )

    assert rkey(s1) == rkey(s2), f"{case['id']}: non-deterministic rerun"
    # Ledger integrity: append-only, contiguous sequence numbers.
    seqs = [x["sequence_no"] for x in s1["revision_ledger"]]
    assert seqs == list(range(len(seqs))), f"{case['id']}: ledger not contiguous"


def test_dataset_covers_all_required_behaviours() -> None:
    behaviours = {c["behavior"] for c in DATASET}
    for required in (
        "competing-hypotheses-resolution", "contradiction-revision",
        "failed-acquisition", "escalation-holds", "prediction-creation",
        "prediction-invalidation", "recovery-after-contradiction",
        "oscillating-support", "uncertainty-convergence", "longitudinal",
    ):
        assert required in behaviours, f"missing behaviour: {required}"
    # dispositions covered across the dataset
    dispositions = {
        e["anomaly"] for c in DATASET for e in c["step_expectations"] if e["anomaly"]
    }
    assert {"revise", "escalate", "reject"} <= dispositions


def test_failed_acquisition_yields_multiple_candidates() -> None:
    mgr = TestCaseManager()
    controllers.load_sample(mgr, {"sample_id": "dataset-failed-acquisition"})
    controllers.run_next(mgr)                       # opens H_topic
    state = controllers.run_next(mgr)               # the failed acquisition
    hyp_ids = {h["hypothesis_id"] for h in state["hypotheses"]}
    assert {"H_avoidance", "H_external"} <= hyp_ids  # competing candidates, not a default


def test_longitudinal_case_has_eight_steps() -> None:
    case = next(c for c in DATASET if c["id"] == "dataset-longitudinal-eight")
    assert len(case["evidence_specs"]) == 8
