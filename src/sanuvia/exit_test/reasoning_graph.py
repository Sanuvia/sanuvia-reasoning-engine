"""Deterministic Reasoning Lineage Graph.

The visual companion to ``reasoning_trace.md``. It visualises how the Persistent
Reasoning Core evolves over time — the WorldModel version spine, the evidence
that drove each revision, the competing hypotheses and how they were affected,
the predictions they yielded, the inquiries raised, and the anomaly resolutions.

Like the trace, it is generated **automatically from the engine's own state** —
the RevisionLedger and the immutable reasoning objects (WorldModel versions,
Hypotheses, Predictions, Inquiries, AnomalyResolutions) — never hand-drawn or
special-cased for the scenario. A neutral :class:`GraphModel` is built once from
that state, then rendered to Mermaid (for embedding in Markdown) and Graphviz
DOT. Because the engine is deterministic, both renderings are reproducible.

Usage::

    python -m sanuvia.exit_test.reasoning_graph              # print Markdown (Mermaid)
    python -m sanuvia.exit_test.reasoning_graph --write PATH # write PATH (default reasoning_graph.md)
    python -m sanuvia.exit_test.reasoning_graph --dot PATH   # also write a Graphviz .dot
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from sanuvia.domain import RevisionOutcome, WorldModelVersionId

from .session_state import SessionState, canonical_session_state

# --- neutral graph model ------------------------------------------------------

_KINDS = ("start", "version", "evidence", "hypothesis", "prediction", "inquiry", "anomaly")


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    kind: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Edge:
    src: str
    dst: str
    style: str  # "solid" | "dashed"
    label: str


@dataclass
class GraphModel:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    _node_ids: set[str] = field(default_factory=set)
    _edge_keys: set[tuple[str, str, str, str]] = field(default_factory=set)

    def add_node(self, node: Node) -> None:
        if node.id not in self._node_ids:
            self._node_ids.add(node.id)
            self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        key = (edge.src, edge.dst, edge.style, edge.label)
        if key not in self._edge_keys:
            self._edge_keys.add(key)
            self.edges.append(edge)


def _sid(prefix: str, raw: str) -> str:
    return f"{prefix}_{re.sub(r'[^0-9A-Za-z]', '_', raw)}"


_SUPPORTING = {RevisionOutcome.STRENGTHEN, RevisionOutcome.HYPOTHESIZE}


# --- build the graph from a session's state ----------------------------------


def build_graph(state: SessionState) -> GraphModel:
    subject = state.subject_id
    results = state.interactions
    store = state  # SessionState exposes the repository ports as attributes
    g = GraphModel()

    ledger = list(store.ledger.read(subject))
    rev_by_id = {e.revision_event.id: e.revision_event for e in ledger}

    # 1. START + WorldModel version spine (in ledger order)
    g.add_node(Node("START", "start", ("start",)))
    version_order: list[WorldModelVersionId] = []
    seen: set[WorldModelVersionId] = set()
    for entry in ledger:
        to_v = entry.revision_event.to_model_version_id
        if to_v is not None and to_v not in seen:
            seen.add(to_v)
            version_order.append(to_v)
    for version_id in version_order:
        model = store.world_models.get_version(subject, version_id)
        u = "—" if model is None else f"{model.model_uncertainty.value:.3f}"
        g.add_node(Node(_sid("V", version_id), "version", (version_id, f"u={u}")))

    # 2. Evidence nodes (in stored order)
    for e in store.evidence.list_for_subject(subject):
        g.add_node(
            Node(
                _sid("E", e.id),
                "evidence",
                (e.id, f"{e.evidence_class.value} · r={e.reliability.value:.3f}"),
            )
        )

    # 3. Hypothesis nodes with support progression (lineage retained)
    for h in store.hypotheses.list_for_subject(subject):
        lineage = store.hypotheses.lineage(h.hypothesis_id)
        progression = "→".join(f"{r.support.value:.2f}" for r in lineage)
        g.add_node(
            Node(
                _sid("H", h.hypothesis_id),
                "hypothesis",
                (h.hypothesis_id, f"support {h.support.value:.3f}", progression),
            )
        )

    # 4. Prediction nodes (each tied to the version that produced it)
    for p in store.predictions.list_for_subject(subject):
        g.add_node(
            Node(
                _sid("P", p.id),
                "prediction",
                (p.id, f"L={p.likelihood.value:.3f}", f"@{p.model_version_id}"),
            )
        )

    # 5. Inquiry nodes
    for inq in store.inquiries.list_for_subject(subject):
        g.add_node(
            Node(
                _sid("Q", inq.id),
                "inquiry",
                (inq.id, f"u={inq.current_uncertainty.value:.3f}"),
            )
        )

    # 6. Anomaly nodes (collected from the engine's per-interaction results)
    anomalies = [
        a
        for r in results
        for a in r.revision_result.anomaly_resolutions
    ]
    anomaly_to_version: dict[str, str] = {}
    for entry in ledger:
        ev = entry.revision_event
        if ev.anomaly_resolution_id is not None and ev.to_model_version_id is not None:
            anomaly_to_version.setdefault(ev.anomaly_resolution_id, ev.to_model_version_id)
    for a in anomalies:
        g.add_node(Node(_sid("A", a.id), "anomaly", (a.id, a.disposition.value)))

    # --- edges ---------------------------------------------------------------

    # spine: START/version -> version, labelled with the outcomes committed
    transitions: dict[tuple[str, str], list[str]] = {}
    for entry in ledger:
        ev = entry.revision_event
        assert ev.to_model_version_id is not None
        frm_id = (
            "START"
            if ev.from_model_version_id is None
            else _sid("V", ev.from_model_version_id)
        )
        to_id = _sid("V", ev.to_model_version_id)
        transitions.setdefault((frm_id, to_id), []).append(ev.outcome.value)
    for (frm_id, to_id), outcomes in transitions.items():
        label = ", ".join(dict.fromkeys(outcomes))
        g.add_edge(Edge(frm_id, to_id, "solid", label))

    # evidence -> hypothesis, per revision event (how each hypothesis changed)
    for entry in ledger:
        ev = entry.revision_event
        style = "solid" if ev.outcome in _SUPPORTING else "dashed"
        for eid in ev.triggering_evidence_ids:
            g.add_edge(
                Edge(_sid("E", eid), _sid("H", ev.affected_object_id), style, ev.outcome.value)
            )

    # hypothesis -> prediction
    for p in store.predictions.list_for_subject(subject):
        for hid in p.derived_from_hypothesis_ids:
            g.add_edge(Edge(_sid("H", hid), _sid("P", p.id), "solid", "yields"))

    # version -> inquiry (the revision that raised it)
    for inq in store.inquiries.list_for_subject(subject):
        rid = inq.produced_by_revision_id
        raising = rev_by_id.get(rid) if rid is not None else None
        if raising is not None and raising.to_model_version_id is not None:
            g.add_edge(
                Edge(
                    _sid("V", raising.to_model_version_id),
                    _sid("Q", inq.id),
                    "solid",
                    "raises",
                )
            )

    # anomaly -> evidence (triggered by); anomaly -> version (if it drove a revision)
    for a in anomalies:
        for eid in a.triggering_evidence_ids:
            g.add_edge(Edge(_sid("A", a.id), _sid("E", eid), "dashed", "on"))
        led_to_version = anomaly_to_version.get(a.id)
        if led_to_version is not None:
            g.add_edge(Edge(_sid("A", a.id), _sid("V", led_to_version), "solid", "→revise"))

    return g


# --- renderers ---------------------------------------------------------------

_MERMAID_OPEN = {
    "start": ("((", "))"),
    "version": ("[[", "]]"),
    "evidence": ("([", "])"),
    "hypothesis": ("[", "]"),
    "prediction": ("[/", "/]"),
    "inquiry": ("((", "))"),
    "anomaly": ("{", "}"),
}


def render_mermaid(g: GraphModel) -> str:
    lines = ["flowchart LR"]
    for node in g.nodes:
        open_, close = _MERMAID_OPEN[node.kind]
        label = "<br/>".join(node.lines)
        lines.append(f'    {node.id}{open_}"{label}"{close}')
    lines.append("")
    for e in g.edges:
        arrow = "-->" if e.style == "solid" else "-.->"
        connector = f"{arrow}|{e.label}|" if e.label else arrow
        lines.append(f"    {e.src} {connector} {e.dst}")
    lines.append("")
    # colour by kind (theme-neutral, readable in light and dark)
    palette = {
        "start": "#6b7280",
        "version": "#0f766e",
        "evidence": "#64748b",
        "hypothesis": "#1d4ed8",
        "prediction": "#15803d",
        "inquiry": "#7c3aed",
        "anomaly": "#b91c1c",
    }
    for kind in _KINDS:
        lines.append(
            f"    classDef {kind} fill:{palette[kind]},color:#ffffff,stroke:#111827;"
        )
    for kind in _KINDS:
        ids = ",".join(n.id for n in g.nodes if n.kind == kind)
        if ids:
            lines.append(f"    class {ids} {kind};")
    return "\n".join(lines)


_DOT_SHAPE = {
    "start": "circle",
    "version": "box3d",
    "evidence": "stadium",
    "hypothesis": "box",
    "prediction": "parallelogram",
    "inquiry": "circle",
    "anomaly": "diamond",
}


def render_dot(g: GraphModel) -> str:
    lines = ["digraph reasoning {", "    rankdir=LR;", '    node [style=filled, fontcolor=white];']
    palette = {
        "start": "#6b7280",
        "version": "#0f766e",
        "evidence": "#64748b",
        "hypothesis": "#1d4ed8",
        "prediction": "#15803d",
        "inquiry": "#7c3aed",
        "anomaly": "#b91c1c",
    }
    for node in g.nodes:
        label = "\\n".join(node.lines)
        lines.append(
            f'    {node.id} [label="{label}", shape={_DOT_SHAPE[node.kind]}, '
            f'fillcolor="{palette[node.kind]}"];'
        )
    for e in g.edges:
        style = "solid" if e.style == "solid" else "dashed"
        lines.append(f'    {e.src} -> {e.dst} [label="{e.label}", style={style}];')
    lines.append("}")
    return "\n".join(lines)


def build_canonical_graph() -> GraphModel:
    """Convenience: build the graph for the canonical reference scenario."""
    return build_graph(canonical_session_state())


def render_markdown(state: SessionState) -> str:
    """The visual companion document: the graph as an embedded Mermaid diagram."""
    g = build_graph(state)
    return "\n".join(
        [
            "# Sanuvia — Persistent Reasoning Core: Reasoning Lineage Graph",
            "",
            "The visual companion to `reasoning_trace.md`. Generated automatically "
            "from the RevisionLedger and the immutable reasoning objects — not "
            "hand-drawn. Re-running produces an identical diagram.",
            "",
            "**Legend** — "
            "`[[version]]` WorldModel version · `([evidence])` · `[hypothesis]` · "
            "`[/prediction/]` · `((inquiry))` · `{anomaly}`. "
            "Solid evidence→hypothesis edges strengthen/hypothesise; dashed edges "
            "contradict.",
            "",
            "```mermaid",
            render_mermaid(g),
            "```",
            "",
        ]
    )


def render_canonical_markdown() -> str:
    """Convenience: render the canonical reference scenario's graph document."""
    return render_markdown(canonical_session_state())


def main(argv: list[str]) -> int:
    canonical = canonical_session_state()
    if "--dot" in argv:
        idx = argv.index("--dot")
        path = argv[idx + 1] if idx + 1 < len(argv) else "reasoning_graph.dot"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_dot(build_graph(canonical)) + "\n")
        print(f"wrote {path}")
    if "--write" in argv:
        idx = argv.index("--write")
        path = argv[idx + 1] if idx + 1 < len(argv) else "reasoning_graph.md"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(canonical) + "\n")
        print(f"wrote {path}")
    if "--write" not in argv and "--dot" not in argv:
        print(render_markdown(canonical))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
