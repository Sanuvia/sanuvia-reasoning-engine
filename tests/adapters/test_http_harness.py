"""Review-harness tests: canonical EvidenceRecord form + Test Case workflow.

These confirm the harness relays *structured* evidence (no NLU) to the engine,
surfaces the engine's own output, renders trace/graph per test case, supports the
full test-case workflow (add / run-next / run-all / reset / duplicate / save-load),
keeps isolated history per test case, and reuses the canonical modules.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sanuvia.adapters.http import controllers
from sanuvia.adapters.http.appraiser import HarnessAppraiser
from sanuvia.adapters.http.manager import TestCaseManager
from sanuvia.adapters.http.server import ReviewHandler, ReviewServer
from sanuvia.adapters.http.testcase_store import InMemoryTestCaseSpecStore
from sanuvia.application.ports.reasoning import Appraisal
from sanuvia.domain import (
    ClassificationConfidence,
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceReliability,
    HypothesisId,
    Provenance,
    ProvenanceConfidence,
    SubjectId,
)


def _ev1() -> dict[str, Any]:
    return {
        "content": "partner went quiet during a disagreement",
        "evidence_class": "behavioural",
        "reliability": 0.7,
        "source": "reflection:session-1",
        "classification_status": "provisional",
        "metadata": [["channel", "written"]],
        "proposals": [
            {"hypothesis_id": "H_avoid", "statement": "avoids conflict", "initial_support": 0.4},
            {"hypothesis_id": "H_reassure", "statement": "seeks reassurance", "initial_support": 0.4},
        ],
    }


def _ev2() -> dict[str, Any]:
    return {
        "content": "asked repeatedly whether things were okay",
        "evidence_class": "behavioural",
        "reliability": 0.85,
        "supports": ["H_reassure"],
    }


def test_initial_state_has_one_empty_test_case() -> None:
    mgr = TestCaseManager()
    state = controllers.get_state(mgr)
    assert state["world_model"] is None
    assert state["sequence"] == []
    assert len(state["test_cases"]) == 1
    assert state["current_test_case"] == "test-case-1"
    assert state["metadata"]["backend"] == "memory"


def test_add_does_not_run_until_run_next() -> None:
    mgr = TestCaseManager()
    state = controllers.add_evidence(mgr, _ev1())
    assert len(state["sequence"]) == 1
    assert state["sequence"][0]["ran"] is False
    assert state["world_model"] is None  # queued, not run

    state = controllers.run_next(mgr)
    assert state["sequence"][0]["ran"] is True
    assert state["world_model"]["version"] == "wm-1"
    assert {h["hypothesis_id"] for h in state["hypotheses"]} == {"H_avoid", "H_reassure"}
    assert state["inquiries"]
    assert state["model_uncertainty"] == 0.5


def test_canonical_evidence_fields_are_recorded() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    state = controllers.run_next(mgr)
    e = state["evidence"][0]
    assert e["id"] == "evidence-1"
    assert e["class"] == "behavioural"
    assert e["source"] == "reflection:session-1"
    assert e["classification_status"] == "provisional"
    assert ["channel", "written"] in e["metadata"]
    assert e["subject"] == state["metadata"]["subject"]


def test_add_and_run_sequence_consolidates() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.run_next(mgr)
    controllers.add_evidence(mgr, _ev2())
    state = controllers.run_next(mgr)
    assert state["world_model"]["version"] == "wm-2"
    assert state["model_uncertainty"] < 0.5
    assert any("H_reassure" in p["from_hypotheses"] for p in state["predictions"])
    assert state["metadata"]["interactions_run"] == 2


def test_run_all_is_deterministic() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.add_evidence(mgr, _ev2())

    def summary() -> Any:
        s = controllers.run_all(mgr)
        return (
            s["world_model"]["version"],
            s["model_uncertainty"],
            [h["support"] for h in s["hypotheses"]],
            [e["id"] for e in s["evidence"]],
        )

    assert summary() == summary()  # rerun reproduces identical state


def test_step_by_step_matches_run_all() -> None:
    a = TestCaseManager()
    controllers.add_evidence(a, _ev1())
    controllers.add_evidence(a, _ev2())
    controllers.run_next(a)
    stepwise = controllers.run_next(a)

    b = TestCaseManager()
    controllers.add_evidence(b, _ev1())
    controllers.add_evidence(b, _ev2())
    allatonce = controllers.run_all(b)

    assert stepwise["world_model"] == allatonce["world_model"]


def test_reset_keeps_sequence_but_clears_reasoning() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.run_next(mgr)
    state = controllers.reset(mgr)
    assert state["world_model"] is None
    assert len(state["sequence"]) == 1  # sequence retained
    assert state["sequence"][0]["ran"] is False


def test_new_and_switch_test_cases_are_isolated() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.run_next(mgr)

    state = controllers.new_test_case(mgr)
    assert state["current_test_case"] == "test-case-2"
    assert state["world_model"] is None
    assert len(state["test_cases"]) == 2

    state = controllers.select_test_case(mgr, {"test_case_id": "test-case-1"})
    assert state["world_model"]["version"] == "wm-1"
    assert "H_avoid" in controllers.get_trace(mgr)["markdown"]


def test_duplicate_copies_sequence_unran() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.add_evidence(mgr, _ev2())
    controllers.run_all(mgr)

    state = controllers.duplicate_test_case(mgr)
    assert state["metadata"]["sequence_length"] == 2
    assert state["metadata"]["interactions_run"] == 0  # copy is unran
    # running the copy reproduces the same result
    state = controllers.run_all(mgr)
    assert state["world_model"]["version"] == "wm-2"


def test_save_and_load_test_case_definition() -> None:
    store = InMemoryTestCaseSpecStore()
    mgr = TestCaseManager(spec_store=store)
    controllers.add_evidence(mgr, _ev1())
    controllers.add_evidence(mgr, _ev2())
    controllers.save_test_case(mgr)

    # a fresh manager over the same store loads the saved definition
    reloaded = TestCaseManager(spec_store=store)
    state = controllers.get_state(reloaded)
    assert state["metadata"]["sequence_length"] == 2
    assert state["metadata"]["interactions_run"] == 0  # only the definition persists
    state = controllers.run_all(reloaded)
    assert state["world_model"]["version"] == "wm-2"


def test_trace_graph_reflect_test_case_reference_is_canonical() -> None:
    mgr = TestCaseManager()
    controllers.add_evidence(mgr, _ev1())
    controllers.run_next(mgr)

    trace = controllers.get_trace(mgr)["markdown"]
    assert "H_avoid" in trace and "H_reassure" in trace
    assert "H_emotional_distance" not in trace

    graph = controllers.get_graph(mgr)
    assert graph["mermaid"].startswith("flowchart LR")

    ref = controllers.get_reference_trace()["markdown"]
    assert "H_emotional_distance" in ref
    assert "H_reassure" not in ref


def test_exit_test_reuses_module_and_records_status() -> None:
    mgr = TestCaseManager()
    report = controllers.get_exit_test(mgr)
    assert report["passed"] is True
    assert len(report["checks"]) == 8
    assert controllers.get_state(mgr)["metadata"]["last_exit_passed"] is True


def test_harness_appraiser_relays_and_consumes() -> None:
    appraiser = HarnessAppraiser()
    appraiser.set_pending(Appraisal(supports=(HypothesisId("H1"),)))
    evidence = EvidenceRecord(
        id=EvidenceRecordId("e1"),
        subject_id=SubjectId("s"),
        evidence_class=EvidenceClass.BEHAVIOURAL,
        content="x",
        provenance=Provenance(source="t", confidence=ProvenanceConfidence(0.9)),
        reliability=EvidenceReliability(0.7),
        classification_confidence=ClassificationConfidence(0.9),
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert appraiser.appraise(SubjectId("s"), evidence, []).supports == (HypothesisId("H1"),)
    assert appraiser.appraise(SubjectId("s"), evidence, []).supports == ()


def test_live_server_end_to_end() -> None:
    server = ReviewServer(("127.0.0.1", 0), ReviewHandler, TestCaseManager())
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health") as r:
            assert json.loads(r.read())["status"] == "ok"
        add = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/evidence/add",
            data=json.dumps(_ev1()).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(add).read()
        run = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/evidence/run-next", data=b"{}",
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(run) as r:
            state = json.loads(r.read())
        assert state["world_model"]["version"] == "wm-1"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
