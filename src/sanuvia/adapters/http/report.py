"""Review report generator — a single shareable Markdown engineering report.

Composes review-ready Markdown from artifacts the harness already has: the
current Test Case snapshot (all from engine state), the reasoning trace and
lineage graph (from the existing renderers), and the exit-test result. It
performs no reasoning and duplicates none — it is pure formatting.
"""

from __future__ import annotations

from typing import Any


def _fmt(x: Any) -> str:
    return "—" if x is None else str(x)


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["_none_", ""]
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    out.append("")
    return out


def build_review_report(
    state: dict[str, Any],
    trace_markdown: str,
    graph_mermaid: str,
    exit_result: dict[str, Any] | None,
    generated_at: str,
) -> str:
    meta = state["metadata"]
    summary = state["summary"]
    out: list[str] = [
        f"# Sanuvia Review Report — {meta['test_case_name']}",
        "",
        f"- Generated: {generated_at}",
        f"- Engine: {meta['engine_version']}",
        f"- Backend: {meta['backend']} · Deterministic: {meta['deterministic_mode']}",
        f"- Test Case: `{meta['test_case_id']}` · Subject: `{meta['subject']}`",
        f"- Tags: {', '.join(state.get('tags', [])) or '—'}",
        f"- Created: {meta.get('created_at', '—')}",
        "",
    ]

    # Reviewer notes
    out += ["## Reviewer Notes", ""]
    notes = state.get("notes", [])
    out += ([f"- {n}" for n in notes] if notes else ["_none_"]) + [""]

    # Summary
    out += ["## Summary", ""]
    out += _table(
        ["metric", "value"],
        [
            ["EvidenceRecords", _fmt(summary["evidence_records"])],
            ["Interactions executed", _fmt(summary["interactions_executed"])],
            ["WorldModel versions", _fmt(summary["world_model_versions"])],
            ["Revision events", _fmt(summary["revision_events"])],
            ["Active hypotheses", _fmt(summary["active_hypotheses"])],
            ["Predictions", _fmt(summary["predictions"])],
            ["Inquiries", _fmt(summary["inquiries"])],
            ["Model uncertainty", _fmt(summary["model_uncertainty"])],
            ["Exit test", _fmt(summary["exit_test_status"])],
        ],
    )

    # Evidence sequence
    out += ["## Evidence Sequence", ""]
    out += _table(
        ["#", "class", "reliability", "ran", "evidence id", "content"],
        [
            [str(s["position"]), s["evidence_class"], str(s["reliability"]),
             "yes" if s["ran"] else "no", _fmt(s["evidence_id"]), s["content"]]
            for s in state.get("sequence", [])
        ],
    )

    # Uncertainty timeline
    out += ["## Uncertainty Timeline", ""]
    out += _table(
        ["step", "evidence", "wm version", "hyps +", "predictions", "inquiry", "u before", "u after"],
        [
            [str(t["step"]), _fmt(t["evidence_id"]), _fmt(t["world_model_version"]),
             str(t["hypotheses_created"]), str(t["predictions"]),
             _fmt(t["inquiry"]), _fmt(t["uncertainty_before"]), _fmt(t["uncertainty_after"])]
            for t in state.get("timeline", [])
        ],
    )

    # Current world model
    out += ["## Current World Model", ""]
    wm = state.get("world_model")
    if wm:
        out += _table(["field", "value"], [
            ["version", _fmt(wm["version"])],
            ["model_uncertainty", _fmt(wm["model_uncertainty"])],
            ["active_hypotheses", ", ".join(wm["active_hypotheses"]) or "—"],
            ["active_predictions", ", ".join(wm["active_predictions"]) or "—"],
            ["active_inquiries", ", ".join(wm["active_inquiries"]) or "—"],
            ["provenance_record_id", _fmt(wm["provenance_record_id"])],
        ])
    else:
        out += ["_no committed model_", ""]

    # Hypotheses
    out += ["## Hypotheses", ""]
    out += _table(
        ["hypothesis_id", "support", "statement", "supporting", "contradicting"],
        [
            [h["hypothesis_id"], str(h["support"]), h["statement"],
             ", ".join(h["supporting_evidence"]) or "—",
             ", ".join(h["contradicting_evidence"]) or "—"]
            for h in state.get("hypotheses", [])
        ],
    )

    # Predictions
    out += ["## Predictions", ""]
    out += _table(
        ["id", "likelihood", "trajectory", "from hypotheses"],
        [
            [p["id"], str(p["likelihood"]), p["trajectory_kind"],
             ", ".join(p["from_hypotheses"])]
            for p in state.get("predictions", [])
        ],
    )

    # Inquiries
    out += ["## Inquiries", ""]
    out += _table(
        ["id", "status", "uncertainty", "statement"],
        [
            [i["id"], i["status"], str(i["current_uncertainty"]), i["statement"]]
            for i in state.get("inquiries", [])
        ],
    )

    # Revision ledger
    out += ["## Revision Ledger", ""]
    out += _table(
        ["seq", "outcome", "affected", "from → to", "evidence"],
        [
            [str(x["sequence_no"]), x["event"]["outcome"], x["event"]["affected"],
             f"{x['event']['from_version'] or '∅'} → {x['event']['to_version']}",
             ", ".join(x["event"]["triggering_evidence"])]
            for x in state.get("revision_ledger", [])
        ],
    )

    # Exit test
    out += ["## Exit Test", ""]
    if exit_result is not None:
        verdict = "PASS" if exit_result["passed"] else "FAIL"
        out += [f"Result: **{verdict}**", ""]
        out += _table(
            ["check", "result", "detail"],
            [
                [c["name"], "PASS" if c["passed"] else "FAIL", c["detail"]]
                for c in exit_result["checks"]
            ],
        )
    else:
        out += ["_not run_", ""]

    # Reasoning trace (embedded)
    out += ["## Reasoning Trace", "", trace_markdown, ""]

    # Reasoning lineage graph (embedded)
    out += ["## Reasoning Lineage Graph", "", "```mermaid", graph_mermaid, "```", ""]

    return "\n".join(out)
