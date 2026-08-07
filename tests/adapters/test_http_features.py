"""Tests for the reviewer-experience features (all above the API)."""

from __future__ import annotations

from typing import Any

from sanuvia.adapters.http import controllers, samples
from sanuvia.adapters.http.manager import TestCaseManager
from sanuvia.adapters.http.testcase_store import InMemoryTestCaseSpecStore


def _run_sample(mgr: TestCaseManager, sample_id: str) -> dict[str, Any]:
    controllers.load_sample(mgr, {"sample_id": sample_id})
    return controllers.run_all(mgr)


# -- 1. sample library ---------------------------------------------------------


def test_sample_library_includes_quick_samples_and_review_dataset() -> None:
    listed = controllers.list_samples()["samples"]
    names = {s["name"] for s in listed}
    # the quick curated samples
    assert {"Relationship Distance", "Failed Acquisition", "Escalation (model holds)",
            "Prediction Revision"} <= names
    # the official engineering review dataset (12 cases, prefixed "D1..D12")
    dataset = [s for s in listed if "Review Dataset" in s["tags"]]
    assert len(dataset) == 12
    assert len(listed) == 22


def test_loading_a_sample_creates_an_editable_copy() -> None:
    mgr = TestCaseManager()
    state = controllers.load_sample(mgr, {"sample_id": "sample-reassurance-seeking"})
    assert state["metadata"]["test_case_name"] == "Reassurance Seeking"
    assert "Relationship" in state["tags"]
    assert state["metadata"]["sequence_length"] == 2
    # it is editable: add another evidence item
    controllers.add_evidence(mgr, {"content": "x", "evidence_class": "behavioural", "reliability": 0.6})
    assert controllers.get_state(mgr)["metadata"]["sequence_length"] == 3


def test_sample_originals_are_not_mutated() -> None:
    before = samples.get_sample("sample-prediction-revision")
    mgr = TestCaseManager()
    _run_sample(mgr, "sample-prediction-revision")
    controllers.add_evidence(mgr, {"content": "extra", "evidence_class": "behavioural", "reliability": 0.5})
    after = samples.get_sample("sample-prediction-revision")
    assert before == after  # deep-copied on read; original untouched


def test_prediction_revision_sample_invalidates_prediction() -> None:
    mgr = TestCaseManager()
    state = _run_sample(mgr, "sample-prediction-revision")
    timeline = state["timeline"]
    assert any(t["predictions"] >= 1 for t in timeline)  # a prediction formed
    assert timeline[-1]["predictions"] == 0  # invalidated by the final contradiction


# -- 2. import / export --------------------------------------------------------


def test_export_then_import_round_trips() -> None:
    mgr = TestCaseManager()
    _run_sample(mgr, "sample-trust-recovery")
    exported = controllers.export_test_case(mgr)
    assert exported["filename"].endswith(".json")
    spec = exported["test_case"]

    state = controllers.import_test_case(mgr, {"test_case": spec})
    # imported becomes a new editable case with the same sequence
    assert state["metadata"]["sequence_length"] == len(spec["evidence_specs"])
    assert state["metadata"]["interactions_run"] == 0
    run = controllers.run_all(mgr)
    assert run["world_model"] is not None


def test_export_trace_graph_report() -> None:
    mgr = TestCaseManager()
    _run_sample(mgr, "sample-relationship-distance")
    assert "Reasoning Trace" in controllers.export_trace(mgr)["markdown"]
    assert controllers.export_graph_mermaid(mgr)["mermaid"].startswith("flowchart LR")
    assert controllers.export_graph_dot(mgr)["dot"].startswith("digraph reasoning {")

    report = controllers.export_report(mgr)["markdown"]
    for section in ("# Sanuvia Engineering Review Report", "## Summary", "## Evidence Sequence",
                    "## Uncertainty Timeline", "## Reasoning Trace",
                    "## Reasoning Lineage Graph", "## Exit Test"):
        assert section in report
    assert "PASS" in report  # exit test embedded


# -- 3. summary ----------------------------------------------------------------


def test_summary_reports_engine_counts() -> None:
    mgr = TestCaseManager()
    state = _run_sample(mgr, "sample-contradictory-evidence")
    su = state["summary"]
    assert su["evidence_records"] == 4
    assert su["interactions_executed"] == 4
    assert su["world_model_versions"] == 4
    assert su["revision_events"] >= 4
    assert su["engine_version"].startswith("Persistent Reasoning Core")
    assert su["deterministic"] is True


# -- 4. step timeline ----------------------------------------------------------


def test_timeline_and_step_view() -> None:
    mgr = TestCaseManager()
    _run_sample(mgr, "sample-relationship-distance")
    timeline = controllers.get_state(mgr)["timeline"]
    assert [t["step"] for t in timeline] == [1, 2, 3]
    assert timeline[0]["hypotheses_created"] == 2

    # selecting a step shows the panels as of that step
    step1 = controllers.get_step(mgr, {"step": 1})
    assert step1["viewing_step"] == 1
    assert step1["world_model"]["version"] == "wm-1"
    step3 = controllers.get_step(mgr, {"step": 3})
    assert step3["world_model"]["version"] == "wm-3"


# -- 5. review report done above (export_report) -------------------------------
# -- 6. reviewer notes ---------------------------------------------------------


def test_notes_add_and_remove() -> None:
    mgr = TestCaseManager()
    controllers.add_note(mgr, {"text": "Unexpected uncertainty increase."})
    controllers.add_note(mgr, {"text": "Prediction revised correctly."})
    state = controllers.get_state(mgr)
    assert state["notes"] == ["Unexpected uncertainty increase.", "Prediction revised correctly."]
    state = controllers.remove_note(mgr, {"index": 0})
    assert state["notes"] == ["Prediction revised correctly."]


# -- 7. tags -------------------------------------------------------------------


def test_tags_set() -> None:
    mgr = TestCaseManager()
    state = controllers.set_tags(mgr, {"tags": ["Relationship", "Regression"]})
    assert state["tags"] == ["Relationship", "Regression"]


# -- 8. comparison mode --------------------------------------------------------


def test_comparison_of_two_test_cases() -> None:
    mgr = TestCaseManager()
    _run_sample(mgr, "sample-escalation-holds")       # test-case-2
    _run_sample(mgr, "sample-prediction-revision")    # test-case-3
    diff = controllers.compare(mgr, {"a": "test-case-2", "b": "test-case-3"})
    assert diff["a"]["name"] == "Escalation (model holds)"
    assert diff["b"]["name"] == "Prediction Revision"
    # escalation holds -> fewer committed revisions than prediction-revision
    assert diff["revision_count"]["a"] < diff["revision_count"]["b"]
    assert "model_uncertainty" in diff and "hypotheses" in diff


# -- 9. search -----------------------------------------------------------------


def test_search_by_name_evidence_and_tag() -> None:
    mgr = TestCaseManager()
    controllers.load_sample(mgr, {"sample_id": "sample-relationship-distance"})
    controllers.load_sample(mgr, {"sample_id": "sample-failed-acquisition"})

    by_name = controllers.search(mgr, {"query": "Relationship Distance"})["results"]
    assert any(r["name"] == "Relationship Distance" for r in by_name)

    by_evidence = controllers.search(mgr, {"query": "unanswered"})["results"]
    assert any(r["name"] == "Failed Acquisition" for r in by_evidence)

    by_tag = controllers.search(mgr, {"query": "", "tags": ["Attachment"]})["results"]
    assert any(r["name"] == "Relationship Distance" for r in by_tag)


# -- persistence of review metadata (save/load) --------------------------------


def test_saved_definition_round_trips_notes_and_tags() -> None:
    store = InMemoryTestCaseSpecStore()
    mgr = TestCaseManager(spec_store=store)
    controllers.load_sample(mgr, {"sample_id": "sample-mixed-signals"})
    controllers.set_tags(mgr, {"tags": ["Conflict", "Regression"]})
    controllers.add_note(mgr, {"text": "watch the tie-break"})
    controllers.save_test_case(mgr)

    reloaded = TestCaseManager(spec_store=store)
    state = controllers.get_state(reloaded)
    assert set(state["tags"]) >= {"Conflict", "Regression"}
    assert "watch the tie-break" in state["notes"]
    assert state["metadata"]["sequence_length"] == 3
