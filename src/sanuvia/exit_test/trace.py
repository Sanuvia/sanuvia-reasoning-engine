"""Deterministic human-readable reasoning trace — a pure renderer.

Renders how a reasoning session evolved over time, section per interaction plus
end-of-run summaries, entirely from a :class:`SessionState` — the engine's own
per-interaction results and persisted immutable state. It does not run the
engine and is not tied to any particular scenario: pass a live review session's
state or the canonical reference state and it renders that.

Usage (canonical reference scenario)::

    python -m sanuvia.exit_test.trace              # print to stdout
    python -m sanuvia.exit_test.trace --write PATH # also write PATH (default reasoning_trace.md)
"""

from __future__ import annotations

import sys

from sanuvia.application.reasoning.core_loop import InteractionResult

from .session_state import SessionState, canonical_session_state


def _f(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def _render_interaction(index: int, r: InteractionResult) -> list[str]:
    out = [f"## Interaction {index}", ""]

    out.append("**Incoming evidence**")
    for e in r.ingested_evidence:
        out.append(
            f"- `{e.id}` · class `{e.evidence_class.value}` · "
            f"reliability {_f(e.reliability.value)}"
        )
    out.append("")

    before_version = r.model_version_before or "— (genesis)"
    out.append(
        f"**WorldModel before revision:** `{before_version}` · "
        f"ModelUncertainty {_f(r.model_uncertainty_before)}"
    )
    out.append("")

    out.append("**Active competing hypotheses (before)**")
    if r.competing_hypotheses_before:
        for h in r.competing_hypotheses_before:
            out.append(f"- `{h.hypothesis_id}` · support {_f(h.support.value)}")
    else:
        out.append("- (none yet)")
    out.append("")

    before = {h.hypothesis_id: h.support.value for h in r.competing_hypotheses_before}
    out.append("**Support changes**")
    for h in r.active_hypotheses:
        after = h.support.value
        if h.hypothesis_id in before:
            prev = before[h.hypothesis_id]
            if abs(after - prev) < 1e-12:
                out.append(f"- `{h.hypothesis_id}` · {_f(after)} (unchanged)")
            else:
                out.append(
                    f"- `{h.hypothesis_id}` · {_f(prev)} → {_f(after)} "
                    f"(Δ {after - prev:+.3f})"
                )
        else:
            out.append(f"- `{h.hypothesis_id}` · new @ {_f(after)}")
    out.append("")

    anomalies = r.revision_result.anomaly_resolutions
    out.append("**AnomalyResolution**")
    if anomalies:
        for a in anomalies:
            trig = ", ".join(a.triggering_evidence_ids)
            out.append(
                f"- `{a.id}` · disposition **{a.disposition.value}** · "
                f"triggered by {trig}"
            )
    else:
        out.append("- none")
    out.append("")

    events = r.revision_result.revision_events
    out.append("**RevisionEvents created**")
    if events:
        for ev in events:
            trig = ", ".join(ev.triggering_evidence_ids)
            frm = ev.from_model_version_id or "∅"
            out.append(
                f"- `{ev.id}` · **{ev.outcome.value}** on `{ev.affected_object_id}` "
                f"· {frm} → `{ev.to_model_version_id}` · evidence {trig}"
            )
    else:
        out.append("- none (model holds)")
    out.append("")

    if r.committed and r.model is not None:
        out.append(f"**New WorldModel version:** `{r.model.model_version_id}`")
    else:
        out.append(
            f"**New WorldModel version:** none — model holds at "
            f"`{r.model_version_before}`"
        )
    out.append("")

    out.append("**Active predictions (this version)**")
    if r.predictions:
        for p in r.predictions:
            src = ", ".join(p.derived_from_hypothesis_ids)
            out.append(
                f"- `{p.id}` · likelihood {_f(p.likelihood.value)} · "
                f"`{p.trajectory.kind.value}` · from {src}"
            )
    elif not r.committed:
        out.append("- (model holds; predictions unchanged)")
    else:
        out.append("- none")
    out.append("")

    out.append("**Inquiry generated**")
    if r.inquiry is not None:
        out.append(
            f"- `{r.inquiry.id}` · status `{r.inquiry.status.value}` · "
            f"uncertainty {_f(r.inquiry.current_uncertainty.value)}"
        )
        out.append(f'  > "{r.inquiry.statement}"')
    else:
        out.append("- none")
    out.append("")

    out.append(
        f"**ModelUncertainty:** {_f(r.model_uncertainty_before)} → "
        f"{_f(r.model_uncertainty)}"
    )
    out.append("")
    return out


def _render_summaries(state: SessionState) -> list[str]:
    subject = state.subject_id
    space = state.space_id  # Finding 2: query the session's own space, not the default
    out = ["---", "", "# End-of-run summaries", ""]

    out.append("## RevisionLedger (authoritative history)")
    out.append("")
    ledger = list(state.ledger.read(subject, space_id=space))
    if ledger:
        out.append("| seq | outcome | affected | from → to | triggering evidence |")
        out.append("| --- | --- | --- | --- | --- |")
        for entry in ledger:
            ev = entry.revision_event
            frm = ev.from_model_version_id or "∅"
            trig = ", ".join(ev.triggering_evidence_ids)
            out.append(
                f"| {entry.sequence_no} | {ev.outcome.value} | "
                f"`{ev.affected_object_id}` | {frm} → `{ev.to_model_version_id}` | {trig} |"
            )
    else:
        out.append("_no committed revisions yet_")
    out.append("")

    out.append("## Hypothesis lineage (support over time)")
    out.append("")
    hyps = list(state.hypotheses.list_for_subject(subject, space_id=space))
    if hyps:
        for h in hyps:
            lineage = state.hypotheses.lineage(
                h.hypothesis_id, subject, space_id=space
            )
            progression = " → ".join(_f(rec.support.value) for rec in lineage)
            out.append(f"- `{h.hypothesis_id}` — \"{h.statement}\"")
            out.append(
                f"  - support: {progression}  ({len(lineage)} evaluation(s) retained)"
            )
    else:
        out.append("_no hypotheses yet_")
    out.append("")

    out.append("## Prediction history")
    out.append("")
    preds = list(state.predictions.list_for_subject(subject, space_id=space))
    if preds:
        out.append("| prediction | model version | likelihood | trajectory | from |")
        out.append("| --- | --- | --- | --- | --- |")
        for p in preds:
            src = ", ".join(p.derived_from_hypothesis_ids)
            out.append(
                f"| `{p.id}` | `{p.model_version_id}` | {_f(p.likelihood.value)} | "
                f"{p.trajectory.kind.value} | {src} |"
            )
    else:
        out.append("_no predictions yet_")
    out.append("")

    out.append("## ModelUncertainty timeline")
    out.append("")
    if state.interactions:
        out.append("| interaction | before | after | committed |")
        out.append("| --- | --- | --- | --- |")
        for i, r in enumerate(state.interactions, start=1):
            out.append(
                f"| {i} | {_f(r.model_uncertainty_before)} | "
                f"{_f(r.model_uncertainty)} | {'yes' if r.committed else 'no (holds)'} |"
            )
    else:
        out.append("_no interactions yet_")
    out.append("")
    return out


def render_trace(state: SessionState) -> str:
    """Render the full deterministic reasoning trace for ``state`` as Markdown."""
    lines = [
        "# Sanuvia — Persistent Reasoning Core: Reasoning Trace",
        "",
        "Deterministic longitudinal trace generated directly from the session's "
        "own reasoning state (per-interaction results + persisted immutable "
        "state). Re-rendering the same state produces an identical document.",
        "",
        f"Subject: `{state.subject_id}` · Interactions: {len(state.interactions)}",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(state.interactions, start=1):
        lines.extend(_render_interaction(i, r))
    lines.extend(_render_summaries(state))
    return "\n".join(lines)


def render_canonical_trace() -> str:
    """Convenience: render the canonical reference scenario's trace."""
    return render_trace(canonical_session_state())


def main(argv: list[str]) -> int:
    text = render_canonical_trace()
    if "--write" in argv:
        idx = argv.index("--write")
        path = argv[idx + 1] if idx + 1 < len(argv) else "reasoning_trace.md"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"wrote {path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
