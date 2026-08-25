"""Reporting — canonical JSON (for deterministic replay) + a human-readable
markdown summary, plus optional reuse of the Phase 0 trace/graph renderers for
the Sanuvia condition.

The report exposes *raw per-point observables only*. Programme v1.4 C.5 names
"rate of behavioural divergence" as the primary metric, but its numerical
thresholds / weighting / pass-fail criteria are explicitly deferred (Programme
v1.4 C.4/C.5); this layer therefore surfaces the raw divergence observables and
marks the aggregate rate as pending governance — it does not invent one.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from sanuvia.exit_test.reasoning_graph import build_graph, render_mermaid
from sanuvia.exit_test.trace import render_trace

from . import metrics
from .conditions import SanuviaPersistentCondition
from .demonstrator import DemonstrationReport
from .failures import CallStatus
from .manifest import RunManifest
from .pipeline import TranscriptDemonstrationReport
from .trajectory import TrajectoryRecord


def to_payload(report: DemonstrationReport) -> dict[str, Any]:
    """A plain, JSON-safe dict of the whole report (deterministic structure)."""
    return {
        "case_id": report.case_id,
        "seq_labels": list(report.seq_labels),
        "evidence_refs_per_interaction": [
            list(refs) for refs in report.evidence_refs_per_interaction
        ],
        "conditions": {
            name: [asdict(record) for record in records]
            for name, records in report.records_by_condition.items()
        },
    }


def to_json(report: DemonstrationReport) -> str:
    """Canonical JSON — byte-identical across runs of the deterministic path."""
    return json.dumps(
        to_payload(report), sort_keys=True, indent=2, ensure_ascii=False
    )


def _fmt(values: list[Any]) -> str:
    return " | ".join("—" if v is None else str(v) for v in values)


def render_markdown(report: DemonstrationReport) -> str:
    """A compact side-by-side markdown summary of the raw metrics."""
    lines: list[str] = [
        f"# Controlled Reasoning Demonstrator — {report.case_id}",
        "",
        "Raw per-point observables. Programme v1.4 C.5 primary metric ('rate of "
        "behavioural divergence'): " + metrics.DIVERGENCE_RATE_STATUS,
        "",
        "Interactions: " + " | ".join(report.seq_labels),
        "Evidence:     "
        + " | ".join(
            ",".join(refs) if refs else "(hold)"
            for refs in report.evidence_refs_per_interaction
        ),
        "",
    ]
    for name, records in report.records_by_condition.items():
        recs: list[TrajectoryRecord] = list(records)
        lines.append(f"## {name}")
        lines.append("")
        lines.append(f"- hypothesis set size: {_fmt(metrics.hypothesis_size_series(recs))}")
        lines.append(f"- retention rate:      {_fmt(metrics.retention_series(recs))}")
        lines.append(f"- inquiry present:     {_fmt(metrics.inquiry_presence_series(recs))}")
        lines.append(f"- prediction count:    {_fmt(metrics.prediction_count_series(recs))}")
        lines.append(f"- model uncertainty:   {_fmt(metrics.uncertainty_series(recs))}")
        lines.append(f"- revision count:      {_fmt(metrics.revision_count_series(recs))}")
        lines.append(
            f"- provenance traceable: {_fmt(metrics.provenance_series(recs))}"
        )
        lines.append(
            f"- unsupported-memory:  {_fmt(metrics.unsupported_memory_series(recs))}"
        )
        lines.append(
            f"- revision events:     {_fmt(metrics.revision_event_count_series(recs))}"
        )
        lines.append(
            "- recognition records: "
            + _fmt(metrics.recognition_record_series(recs))
            + "  (Sanuvia 0 = computation deferred → none emitted; — = N/A for FM)"
        )
        lines.append(
            f"- dependency edges:    {_fmt(metrics.dependency_edge_count_series(recs))}"
        )
        lines.append(
            "- inquiry status:      "
            + _fmt(metrics.inquiry_status_series(recs))
        )
        pairs = metrics.observed_inquiry_pairs(recs)
        if pairs:
            rendered = "; ".join(
                f"@{idx}:{'/'.join(ids) if ids else '(none)'}" for idx, ids in pairs
            )
            lines.append(f"- observed inquiry pairs: {rendered}")
        lines.append("")

    # Id-based DIAGNOSTIC observables (Sanuvia vs each FM baseline). This is a
    # debugging aid, NOT an evaluation result and NOT evidence of better reasoning.
    sanuvia = report.records_by_condition.get("sanuvia_persistent")
    if sanuvia is not None:
        lines.append("## id-based diagnostics (debugging only — NOT an evaluation result)")
        lines.append("")
        lines.append(metrics.HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT)
        lines.append("")
        for name, records in report.records_by_condition.items():
            if name == "sanuvia_persistent":
                continue
            points = metrics.id_based_diagnostics(list(sanuvia), list(records))
            inq = sum(1 for p in points if p.inquiry_presence_differs)
            hyp = sum(1 for p in points if p.hypothesis_id_sets_differ)
            comparable = sum(1 for p in points if p.uncertainty_comparable)
            lines.append(
                f"- sanuvia_persistent vs {name}: "
                f"points={len(points)}; inquiry-presence differs at {inq}; "
                f"hypothesis-ID-set differs at {hyp} (id-level diagnostic, not semantic); "
                f"uncertainty-comparable points={comparable} "
                "(raw counts only — not a scored rate)"
            )
        lines.append("")
    return "\n".join(lines)


# --- Transcript-driven runs (raw text → extraction → Phase 0) -----------------


def transcript_to_payload(report: TranscriptDemonstrationReport) -> dict[str, Any]:
    """JSON-safe dict of a transcript run: mode, extractor, extraction audit
    (raw observation + full provenance), and the trajectory demonstration."""
    return {
        "mode": report.mode,
        "extractor_id": report.extractor_id,
        "transcript_id": report.transcript_id,
        "extractions": [
            {
                "interaction_index": ex.interaction_index,
                "seq_label": ex.seq_label,
                "evidence": [
                    {
                        "ref": e.ref,
                        "observation": e.observation,
                        "evidence_class": e.evidence_class.value,
                        "reliability": e.reliability,
                        "classification_confidence": e.classification_confidence,
                        "provenance_confidence": e.provenance_confidence,
                        "provenance": {
                            "transcript_id": e.provenance.transcript_id,
                            "source_interaction_index": e.provenance.source_interaction_index,
                            "seq_label": e.provenance.seq_label,
                            "extractor_id": e.provenance.extractor_id,
                            "text_span": e.provenance.text_span,
                            "extraction_status": e.provenance.extraction_status,
                        },
                    }
                    for e in ex.evidence
                ],
            }
            for ex in report.extractions
        ],
        "demonstration": to_payload(report.demonstration),
    }


def transcript_to_json(report: TranscriptDemonstrationReport) -> str:
    """Canonical JSON for a transcript run (deterministic in golden mode)."""
    return json.dumps(
        transcript_to_payload(report), sort_keys=True, indent=2, ensure_ascii=False
    )


def render_transcript_markdown(report: TranscriptDemonstrationReport) -> str:
    """Human-readable transcript run: mode/extractor banner + extraction audit +
    the trajectory comparison."""
    lines: list[str] = [
        f"# Transcript run — {report.transcript_id}  [mode={report.mode}; "
        f"extractor={report.extractor_id}]",
        "",
        "raw transcript → evidence extraction → frozen Phase 0 reasoning; "
        "FM baselines read raw transcript text.",
        "",
        "## extracted evidence (with provenance)",
        "",
    ]
    for ex in report.extractions:
        if not ex.evidence:
            lines.append(f"- {ex.seq_label}: (no evidence extracted — hold)")
            continue
        for e in ex.evidence:
            span = f' span="{e.provenance.text_span}"' if e.provenance.text_span else ""
            lines.append(
                f"- {ex.seq_label} {e.ref} [{e.evidence_class.value}] "
                f'"{e.observation}"  (from interaction '
                f"{e.provenance.source_interaction_index}, {e.provenance.extractor_id}"
                f"{span})"
            )
    lines.append("")
    lines.append(render_markdown(report.demonstration))
    return "\n".join(lines)


def manifest_to_json(manifest: RunManifest) -> str:
    """Canonical JSON of an immutable run manifest (deterministic serialization)."""
    return manifest.to_json()


def render_manifest_markdown(manifest: RunManifest) -> str:
    """Human-readable manifest summary that makes per-interaction status and any
    failed model calls VISIBLE (Area 2/3). A failed call is shown as a failure —
    never hidden behind a successful-looking record."""
    lines: list[str] = [
        f"# Run manifest — {manifest.run_id}  [mode={manifest.mode}]",
        "",
        f"- created_at:      {manifest.created_at}",
        f"- git_commit_sha:  {manifest.git_commit_sha}",
        f"- phase1_version:  {manifest.phase1_version}",
        f"- transcript_id:   {manifest.transcript_id}",
        f"- model_specs:     {len(manifest.model_specs)} "
        "(empty for golden — no external models)",
        "",
        "## per-interaction status",
        "",
    ]
    for seq_label, status in manifest.per_interaction_status:
        marker = "ok" if status == CallStatus.SUCCESS.value else "FAIL"
        lines.append(f"- {seq_label}: {status}  [{marker}]")

    failures = [
        record
        for record in manifest.call_records
        if record.status != CallStatus.SUCCESS.value
    ]
    lines.append("")
    lines.append("## failed model calls")
    lines.append("")
    if not failures:
        lines.append("- none")
    else:
        for record in failures:
            lines.append(
                f"- {record.seq_label} [{record.boundary}/{record.model_role}] "
                f"{record.status} after {record.attempts} attempt(s): {record.detail}"
            )
    lines.append("")
    return "\n".join(lines)


def render_sanuvia_trace(condition: SanuviaPersistentCondition) -> str:
    """Reuse the frozen Phase 0 trace renderer for the Sanuvia condition."""
    return str(render_trace(condition.session_state()))


def render_sanuvia_graph(condition: SanuviaPersistentCondition) -> str:
    """Reuse the frozen Phase 0 lineage-graph renderer (Mermaid) for the Sanuvia
    condition."""
    return str(render_mermaid(build_graph(condition.session_state())))
