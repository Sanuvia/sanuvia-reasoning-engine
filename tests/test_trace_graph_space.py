"""Second review, Finding 2 — trace & graph must preserve space_id.

A valid interaction is run in a NON-default (shared) space, producing a committed
ledger entry. The trace and graph renderers must query the repositories for that
space (via ``SessionState.space_id``) rather than falling back to the default
space. Verified on both persistence adapters.
"""

from __future__ import annotations

from typing import Any

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import (
    build_in_memory_dependencies,
    build_sqlite_dependencies,
)
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    EvidenceClass,
    HypothesisId,
    SubjectId,
    shared_space_id,
)
from sanuvia.exit_test.reasoning_graph import build_graph, render_mermaid
from sanuvia.exit_test.session_state import from_interactions
from sanuvia.exit_test.trace import render_trace

SUBJECT = SubjectId("subject-space")
SHARED = shared_space_id("finding-2")
H = HypothesisId("H_space")


class _Proposes:
    """Proposes one strongly-supported hypothesis, then supports it — so the
    interaction commits a revision (a ledger entry) and forms a prediction."""

    def appraise(self, subject_id: SubjectId, evidence: Any, working: Any) -> Appraisal:
        if any(w.hypothesis_id == H for w in working):
            return Appraisal(supports=(H,))
        return Appraisal(proposals=(ProposedHypothesis(H, "a space-scoped explanation", 0.8, ()),))


def _evidence() -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT,
        evidence_class=EvidenceClass.BEHAVIOURAL,
        content="observation in the shared space",
        source="reflection",
        reliability=0.8,
        classification_confidence=0.9,
    )


def _make_session(backend: str):
    if backend == "memory":
        store: Any = InMemoryReasoningStore()
        deps = build_in_memory_dependencies(
            store=store, appraiser=_Proposes(),
            clock=ManualClock(), ids=SequentialIdGenerator())
    else:
        store = SqliteReasoningStore(":memory:")
        deps = build_sqlite_dependencies(
            store=store, appraiser=_Proposes(),
            clock=ManualClock(), ids=SequentialIdGenerator())
    service = ReasoningService(deps)
    # A valid interaction in the NON-default shared space.
    r1 = service.record_interaction(SUBJECT, [_evidence()], space_id=SHARED)
    r2 = service.record_interaction(SUBJECT, [_evidence()], space_id=SHARED)
    assert r1.committed and r1.space_id == SHARED
    return store, (r1, r2)


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_trace_and_graph_preserve_non_default_space(backend: str) -> None:
    store, interactions = _make_session(backend)

    # from_interactions recovers the space from the interactions themselves.
    state = from_interactions(SUBJECT, interactions, store)
    assert state.space_id == SHARED  # not DEFAULT_SPACE_ID

    trace = render_trace(state)
    graph_md = render_mermaid(build_graph(state))

    # The trace contains the interaction/revision/ledger information.
    assert "RevisionLedger (authoritative history)" in trace
    assert "evidence-1" in trace                      # the ingested evidence
    assert "H_space" in trace                         # the committed hypothesis
    assert "hypothesize" in trace.lower()             # the committed revision outcome
    assert "_no committed revisions yet_" not in trace
    assert "_no hypotheses yet_" not in trace

    # The graph contains the WorldModel / evidence / revision lineage.
    assert "flowchart" in graph_md
    assert "evidence-1" in graph_md                   # evidence node
    assert "H_space" in graph_md                      # hypothesis node
    assert "wm-1" in graph_md                         # WorldModel version node
    assert "hypothesize" in graph_md.lower()          # revision edge label


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_renderers_do_not_fall_back_to_default_space(backend: str) -> None:
    """Proof it does NOT fall back to DEFAULT_SPACE_ID: rendering the SAME
    session with the default space yields empty summaries (the data lives only in
    the shared space), while the correct space yields populated ones."""
    store, interactions = _make_session(backend)

    wrong = from_interactions(SUBJECT, interactions, store, space_id=DEFAULT_SPACE_ID)
    right = from_interactions(SUBJECT, interactions, store, space_id=SHARED)

    wrong_trace = render_trace(wrong)
    right_trace = render_trace(right)

    # The end-of-run SUMMARY sections are built from repository queries — the
    # exact place the space bug manifested. Under the default space they are
    # empty (the data lives only in the shared space), confirming no fallback.
    # (Per-interaction sections render the passed-in results, which are already
    # space-correct, so they are not part of this contrast.)
    assert "_no committed revisions yet_" in wrong_trace
    assert "_no hypotheses yet_" in wrong_trace

    # The correct (shared) space populates the summaries.
    assert "_no committed revisions yet_" not in right_trace
    assert "_no hypotheses yet_" not in right_trace

    # The graph is built entirely from repository queries: under the default
    # space it has NO version / evidence / hypothesis nodes; under the shared
    # space it does. This is the direct "does not fall back to DEFAULT" proof.
    wrong_graph = render_mermaid(build_graph(wrong))
    right_graph = render_mermaid(build_graph(right))
    assert "H_space" not in wrong_graph and "evidence-1" not in wrong_graph and "wm-1" not in wrong_graph
    assert "H_space" in right_graph and "evidence-1" in right_graph and "wm-1" in right_graph
