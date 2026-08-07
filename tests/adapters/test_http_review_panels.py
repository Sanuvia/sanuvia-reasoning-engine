"""Tests for the reviewer-experience panels (all derived from engine outputs)."""

from __future__ import annotations

from typing import Any

from sanuvia.adapters.http import controllers
from sanuvia.adapters.http.manager import TestCaseManager


def _run(sample_id: str) -> tuple[TestCaseManager, dict[str, Any]]:
    mgr = TestCaseManager()
    controllers.load_sample(mgr, {"sample_id": sample_id})
    return mgr, controllers.run_all(mgr)


# -- 1. Expected vs Actual -----------------------------------------------------


def test_expected_vs_actual_all_match_for_dataset_case() -> None:
    _, state = _run("dataset-prediction-invalidation")
    eva = state["expected_vs_actual"]
    assert eva is not None and len(eva) == 5
    assert all(row["match"] for row in eva)
    step4 = eva[3]
    assert step4["fields"]["prediction"]["expected"] == []      # invalidated
    assert step4["fields"]["prediction"]["actual"] == []


def test_expected_vs_actual_absent_for_handbuilt_case() -> None:
    mgr = TestCaseManager()  # empty hand-built case, no expectations
    controllers.add_evidence(mgr, {"content": "x", "evidence_class": "behavioural",
                                   "reliability": 0.7,
                                   "proposals": [{"hypothesis_id": "H", "statement": "s", "initial_support": 0.4}]})
    state = controllers.run_next(mgr)
    assert state["expected_vs_actual"] is None


# -- 2. Reviewer Verdict -------------------------------------------------------


def test_verdict_pass_for_correct_run() -> None:
    _, state = _run("dataset-competing-resolve")
    v = state["verdict"]
    assert v["overall"] == "PASS"
    labels = {c["label"] for c in v["checks"]}
    assert {"competing hypotheses retained", "uncertainty revised",
            "predictions grounded in hypotheses", "provenance preserved",
            "immutable model respected"} == labels
    assert all(c["pass"] for c in v["checks"])


def test_verdict_pending_before_run() -> None:
    mgr = TestCaseManager()
    assert controllers.get_state(mgr)["verdict"]["overall"] == "PENDING"


# -- 3. Uncertainty history (chart source) -------------------------------------


def test_uncertainty_series_from_timeline() -> None:
    _, state = _run("dataset-competing-resolve")
    us = [t["uncertainty_after"] for t in state["timeline"]]
    assert us == [0.5, 0.395, 0.317, 0.247, 0.2]  # real engine values, no fake data


# -- 4. Hypothesis evolution ---------------------------------------------------


def test_hypothesis_evolution_series() -> None:
    _, state = _run("dataset-longitudinal-eight")
    he = state["hypothesis_evolution"]
    assert he["steps"] == 8
    series = {s["hypothesis_id"]: s["support"] for s in he["series"]}
    assert series["H_distance"][0] == 0.4 and series["H_distance"][3] < 0.6  # contradicted
    assert series["H_external"][:4] == [None, None, None, None]  # appears at step 5
    assert series["H_external"][4] == 0.4


# -- 5. Prediction lifecycle ---------------------------------------------------


def test_prediction_lifecycle_events() -> None:
    _, state = _run("dataset-prediction-invalidation")
    life = {p["hypothesis_id"]: p["events"] for p in state["prediction_lifecycle"]}
    events = [(e["event"], e.get("version")) for e in life["H_withdrawal"]]
    assert ("created", "wm-2") in events
    assert any(e[0] == "invalidated" for e in events)


# -- 6. WorldModel timeline ----------------------------------------------------


def test_world_model_timeline_nodes() -> None:
    _, state = _run("sample-relationship-distance")
    wt = state["world_model_timeline"]
    assert [n["version"] for n in wt] == ["wm-1", "wm-2", "wm-3"]
    n0 = wt[0]
    assert set(n0) >= {"version", "uncertainty", "active_hypotheses",
                       "prediction_count", "inquiry_count", "triggered_evidence"}
    assert n0["inquiry_count"] == 1  # step 1 raised an inquiry


# -- 7. Revisions grouped by interaction ---------------------------------------


def test_revisions_by_interaction() -> None:
    _, state = _run("sample-relationship-distance")
    rbi = state["revisions_by_interaction"]
    assert len(rbi) == 3
    step1 = rbi[0]
    outcomes = {r["outcome"] for r in step1["revisions"]}
    assert outcomes == {"hypothesize"}
    assert step1["version"] == "wm-1"
    assert len(step1["revisions"]) == 2  # two hypotheses proposed


# -- 8. Provenance viewer (evidence chains) ------------------------------------


def test_evidence_chains_trace_full_lineage() -> None:
    _, state = _run("sample-relationship-distance")
    chains = state["evidence_chains"]
    assert len(chains) == 3
    first = chains[0]
    assert first["evidence_id"] == "evidence-1"
    assert first["versions"] == ["wm-1"]
    assert any(r["outcome"] == "hypothesize" for r in first["revisions"])
    assert first["inquiries"]  # evidence-1 led to the version that raised an inquiry


# -- 9. Review report ----------------------------------------------------------


def test_review_report_has_professional_sections() -> None:
    mgr, _ = _run("dataset-prediction-invalidation")
    report = controllers.export_report(mgr)["markdown"]
    for section in ("# Sanuvia Engineering Review Report", "## Executive Summary",
                    "**Overall:", "## Dataset", "## Step-by-Step Reasoning",
                    "## Hypothesis Evolution", "## Prediction Evolution",
                    "## Uncertainty Timeline", "## WorldModel History",
                    "## Expected vs Actual", "## Exit Test", "Determinism"):
        assert section in report, f"missing: {section}"


# -- 10 / behaviour preserved --------------------------------------------------


def test_reasoning_unchanged_and_expectations_persist_on_save() -> None:
    from sanuvia.adapters.http.testcase_store import InMemoryTestCaseSpecStore
    store = InMemoryTestCaseSpecStore()
    mgr = TestCaseManager(spec_store=store)
    controllers.load_sample(mgr, {"sample_id": "dataset-escalation-holds"})
    controllers.save_test_case(mgr)
    # reload: expectations survive so Expected-vs-Actual still works
    reloaded = TestCaseManager(spec_store=store)
    controllers.run_all(reloaded)
    eva = controllers.get_state(reloaded)["expected_vs_actual"]
    assert eva is not None and all(r["match"] for r in eva)
