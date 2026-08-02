"""Controllers — thin request handlers for the Test Case workflow.

Each function only marshals input, calls the Application API (via
``TestCaseManager`` / ``TestCase``), executes an existing artifact module, or
formats an export — and returns a JSON-serialisable dict. There is no reasoning,
no natural-language understanding, and no duplicated reasoning logic here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sanuvia.exit_test import run as run_exit_test
from sanuvia.exit_test.reasoning_graph import (
    build_canonical_graph,
    build_graph,
    render_dot,
    render_mermaid,
)
from sanuvia.exit_test.trace import render_canonical_trace, render_trace

from . import samples
from .manager import TestCaseManager
from .report import build_review_report
from .testcase import EvidenceSpec, ProposalInput

_PANEL_KEYS = [
    "evidence", "world_model", "hypotheses", "predictions", "inquiries",
    "revision_events", "anomaly_resolutions", "revision_ledger",
    "model_uncertainty", "uncertainty_before", "provenance",
    "recognition_conditions", "sequence",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state(manager: TestCaseManager) -> dict[str, Any]:
    snapshot = manager.current().snapshot()
    snapshot["test_cases"] = manager.summaries()
    snapshot["current_test_case"] = manager.current().id
    return snapshot


def _spec_from_body(body: dict[str, Any]) -> EvidenceSpec:
    proposals = tuple(
        ProposalInput(
            hypothesis_id=str(p["hypothesis_id"]),
            statement=str(p.get("statement", "")),
            initial_support=float(p.get("initial_support", 0.4)),
        )
        for p in body.get("proposals", [])
    )
    metadata = tuple(
        (str(k), str(v)) for k, v in (tuple(m) for m in body.get("metadata", []))
    )
    return EvidenceSpec(
        content=str(body["content"]),
        evidence_class=str(body.get("evidence_class", "behavioural")),
        reliability=float(body.get("reliability", 0.7)),
        classification_confidence=float(body.get("classification_confidence", 0.9)),
        source=str(body.get("source", "review-harness")),
        provenance_confidence=float(body.get("provenance_confidence", 1.0)),
        classification_status=str(body.get("classification_status", "")),
        metadata=metadata,
        supports=tuple(str(s) for s in body.get("supports", [])),
        contradicts=tuple(str(c) for c in body.get("contradicts", [])),
        proposals=proposals,
    )


def get_state(manager: TestCaseManager) -> dict[str, Any]:
    return _state(manager)


# -- evidence sequence & stepping ----------------------------------------------


def add_evidence(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.current().add_evidence(_spec_from_body(body))
    return _state(manager)


def run_next(manager: TestCaseManager) -> dict[str, Any]:
    manager.current().run_next()
    return _state(manager)


def run_all(manager: TestCaseManager) -> dict[str, Any]:
    manager.current().run_all()
    return _state(manager)


def reset(manager: TestCaseManager) -> dict[str, Any]:
    manager.current().reset()
    return _state(manager)


def get_step(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    """Full current state with the *panels* replaced by the view as of `step`."""
    step = int(body["step"])
    full = _state(manager)
    stepped = manager.current().snapshot_at(step)
    for key in _PANEL_KEYS:
        full[key] = stepped.get(key)
    full["viewing_step"] = step
    return full


# -- test-case management ------------------------------------------------------


def new_test_case(manager: TestCaseManager) -> dict[str, Any]:
    manager.new_test_case()
    return _state(manager)


def select_test_case(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.select(str(body["test_case_id"]))
    return _state(manager)


def duplicate_test_case(manager: TestCaseManager) -> dict[str, Any]:
    manager.duplicate_current()
    return _state(manager)


def rename_test_case(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.current().rename(str(body["name"]))
    return _state(manager)


def save_test_case(manager: TestCaseManager) -> dict[str, Any]:
    manager.save_current()
    state = _state(manager)
    state["saved"] = True
    return state


# -- notes & tags --------------------------------------------------------------


def add_note(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.current().add_note(str(body["text"]))
    return _state(manager)


def remove_note(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.current().remove_note(int(body["index"]))
    return _state(manager)


def set_tags(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.current().set_tags([str(t) for t in body.get("tags", [])])
    return _state(manager)


# -- sample library ------------------------------------------------------------


def list_samples() -> dict[str, Any]:
    return {"samples": samples.list_samples()}


def load_sample(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    manager.load_sample(str(body["sample_id"]))
    return _state(manager)


# -- import / export -----------------------------------------------------------


def export_test_case(manager: TestCaseManager) -> dict[str, Any]:
    case = manager.current()
    return {"test_case": case.spec_dict(), "filename": f"{case.id}.json"}


def import_test_case(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    spec = body.get("test_case", body)
    manager.import_test_case(spec)
    return _state(manager)


def export_trace(manager: TestCaseManager) -> dict[str, Any]:
    return {
        "markdown": render_trace(manager.current().reasoning_state()),
        "filename": f"{manager.current().id}-trace.md",
    }


def export_graph_mermaid(manager: TestCaseManager) -> dict[str, Any]:
    graph = build_graph(manager.current().reasoning_state())
    return {"mermaid": render_mermaid(graph), "filename": f"{manager.current().id}-graph.mmd"}


def export_graph_dot(manager: TestCaseManager) -> dict[str, Any]:
    graph = build_graph(manager.current().reasoning_state())
    return {"dot": render_dot(graph), "filename": f"{manager.current().id}-graph.dot"}


def export_report(manager: TestCaseManager) -> dict[str, Any]:
    case = manager.current()
    state = case.snapshot()
    trace = render_trace(case.reasoning_state())
    mermaid = render_mermaid(build_graph(case.reasoning_state()))
    report = run_exit_test()
    case.last_exit_passed = report.passed
    exit_result = {
        "passed": report.passed,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail}
            for c in report.checks
        ],
    }
    markdown = build_review_report(state, trace, mermaid, exit_result, _now())
    return {"markdown": markdown, "filename": f"{case.id}-review-report.md"}


# -- comparison & search -------------------------------------------------------


def compare(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    a = manager.get(str(body["a"]))
    b = manager.get(str(body["b"]))
    sa, sb = a.snapshot(), b.snapshot()

    def hyps(s: dict[str, Any]) -> list[list[Any]]:
        return [[h["hypothesis_id"], h["support"]] for h in s["hypotheses"]]

    return {
        "a": {"id": a.id, "name": a.name},
        "b": {"id": b.id, "name": b.name},
        "evidence": {
            "a": [e["id"] for e in sa["evidence"]],
            "b": [e["id"] for e in sb["evidence"]],
        },
        "hypotheses": {"a": hyps(sa), "b": hyps(sb)},
        "predictions": {
            "a": [p["id"] for p in sa["predictions"]],
            "b": [p["id"] for p in sb["predictions"]],
        },
        "revision_count": {
            "a": len(sa["revision_ledger"]), "b": len(sb["revision_ledger"]),
        },
        "model_uncertainty": {
            "a": sa["model_uncertainty"], "b": sb["model_uncertainty"],
        },
        "exit_test": {"a": a.last_exit_passed, "b": b.last_exit_passed},
    }


def search(manager: TestCaseManager, body: dict[str, Any]) -> dict[str, Any]:
    results = manager.search(
        str(body.get("query", "")),
        [str(t) for t in body.get("tags", [])],
    )
    return {"results": results}


# -- per-test-case artifacts ---------------------------------------------------


def get_trace(manager: TestCaseManager) -> dict[str, Any]:
    return {"markdown": render_trace(manager.current().reasoning_state())}


def get_graph(manager: TestCaseManager) -> dict[str, Any]:
    graph = build_graph(manager.current().reasoning_state())
    return {"mermaid": render_mermaid(graph), "dot": render_dot(graph)}


def get_exit_test(manager: TestCaseManager) -> dict[str, Any]:
    report = run_exit_test()
    manager.current().last_exit_passed = report.passed
    return {
        "passed": report.passed,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail}
            for c in report.checks
        ],
    }


# -- reference mode (canonical exit-test scenario) -----------------------------


def get_reference_trace() -> dict[str, Any]:
    return {"markdown": render_canonical_trace()}


def get_reference_graph() -> dict[str, Any]:
    graph = build_canonical_graph()
    return {"mermaid": render_mermaid(graph), "dot": render_dot(graph)}
