"""Tests for the final review-polish features (all above the API)."""

from __future__ import annotations

import base64
import io
import zipfile
from typing import Any

from sanuvia.adapters.http import controllers
from sanuvia.adapters.http.manager import TestCaseManager


def _run(sample_id: str) -> tuple[TestCaseManager, dict[str, Any]]:
    mgr = TestCaseManager()
    controllers.load_sample(mgr, {"sample_id": sample_id})
    return mgr, controllers.run_all(mgr)


# -- 7. Dataset purpose --------------------------------------------------------


def test_dataset_purpose_present_before_running() -> None:
    mgr = TestCaseManager()
    state = controllers.load_sample(mgr, {"sample_id": "dataset-competing-resolve"})
    p = state["dataset_purpose"]
    assert p is not None
    assert "competing hypotheses" in p["purpose"].lower()
    assert p["expected_exit_test"] == "PASS"
    assert isinstance(p["expected_behaviour"], list) and p["expected_behaviour"]
    # catalogue also exposes the purpose
    listed = controllers.list_samples()["samples"]
    d1 = next(s for s in listed if s["id"] == "dataset-competing-resolve")
    assert d1["purpose"]


def test_dataset_purpose_absent_for_handbuilt() -> None:
    mgr = TestCaseManager()
    assert controllers.get_state(mgr)["dataset_purpose"] is None


# -- 4. Automatic reasoning summary --------------------------------------------


def test_reasoning_summary_generated_from_state() -> None:
    _, state = _run("dataset-longitudinal-eight")
    s = state["reasoning_summary"]
    assert "competing explanations" in s
    assert "H_stress" in s  # a real hypothesis id from state
    assert "uncertainty" in s.lower()
    assert "behaved consistently with the supplied evidence." in s or "Review the differences" in s


def test_reasoning_summary_pending_before_run() -> None:
    mgr = TestCaseManager()
    assert "No interactions" in controllers.get_state(mgr)["reasoning_summary"]


# -- 5. Explain why ------------------------------------------------------------


def test_explain_why_from_state() -> None:
    _, state = _run("dataset-longitudinal-eight")
    ew = state["explain_why"]
    assert ew
    top = ew[0]
    assert top["hypothesis_id"] == "H_stress"
    assert top["supporting_evidence"]
    assert len(top["support_progression"]) == 8
    assert top["current_support"] == 0.87
    assert "strengthening evidence" in top["reason"]


# -- 8. Final engineering verdict ----------------------------------------------


def test_review_result_pass_for_dataset_case() -> None:
    mgr, _ = _run("dataset-competing-resolve")
    r = controllers.get_review_result(mgr)
    assert r["overall"] == "PASS"
    assert r["expected_vs_actual"] == "100%"
    assert r["reasoning_correct"] == "YES"
    assert r["deterministic"] == "YES"
    assert r["exit_test"] == "PASS"
    assert r["ready_for_phase_1"] == "YES"
    assert r["dataset"] == "D1 · Competing hypotheses that resolve"


# -- 6. One-click review package -----------------------------------------------


def test_review_package_zip_contains_all_artifacts() -> None:
    mgr, _ = _run("dataset-prediction-invalidation")
    pkg = controllers.export_package(mgr)
    assert pkg["filename"].endswith(".zip")
    zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(pkg["zip_base64"])))
    assert set(zf.namelist()) == {
        "review-report.md", "reasoning_trace.md", "reasoning_graph.md",
        "reasoning_graph.dot", "test_case.json", "exit_test.json",
    }
    # engine artifacts inside are non-empty and correct
    assert b"flowchart LR" not in zf.read("reasoning_trace.md")
    assert zf.read("reasoning_graph.dot").startswith(b"digraph reasoning {")
    import json as _json
    assert _json.loads(zf.read("exit_test.json"))["passed"] is True


# -- 9. Determinism of review-derived outputs ----------------------------------


def test_review_outputs_are_byte_identical_across_runs() -> None:
    def derived(sample_id: str) -> Any:
        _, s = _run(sample_id)
        return (
            s["reasoning_summary"],
            s["explain_why"],
            s["hypothesis_evolution"],
            s["world_model_timeline"],
            s["prediction_lifecycle"],
            [r["match"] for r in (s["expected_vs_actual"] or [])],
            [t["uncertainty_after"] for t in s["timeline"]],
        )

    assert derived("dataset-longitudinal-eight") == derived("dataset-longitudinal-eight")

    # the review package's engine artifacts are byte-identical too
    def artifacts(sample_id: str) -> dict[str, bytes]:
        mgr, _ = _run(sample_id)
        zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(controllers.export_package(mgr)["zip_base64"])))
        return {n: zf.read(n) for n in ("reasoning_trace.md", "reasoning_graph.md",
                                        "reasoning_graph.dot", "exit_test.json")}

    assert artifacts("dataset-competing-resolve") == artifacts("dataset-competing-resolve")
