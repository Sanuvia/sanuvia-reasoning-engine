"""Sanuvia Persistent condition — a thin wrapper over the frozen Phase 0 engine.

It reimplements nothing. It builds a Phase 0 in-memory dependency bundle with the
case's authored ``ScriptedAppraiser`` and drives the public ``ReasoningService``.
All persistence (WorldModel versions, hypotheses, support, uncertainty, ledger,
provenance, predictions) lives in the frozen engine; this class only translates
case interactions in and normalizes ``InteractionResult`` out.
"""

from __future__ import annotations

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.domain import GovernedRejection
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.reasoning.scripted_identity_resolver import (
    resolver_for_script,
)
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api import ReasoningService
from sanuvia.application.ports.reasoning import EvidenceAppraiser
from sanuvia.application.reasoning.core_loop import InteractionResult
from sanuvia.domain import ObjectRef
from sanuvia.exit_test.session_state import SessionState, from_interactions

from ..capture import from_interaction_result, from_rejected_plan
from ..case import Case, CaseInteraction
from ..trajectory import DependencyEdgeView, TrajectoryRecord


class SanuviaPersistentCondition:
    """Persistent-reasoning condition backed by the frozen Phase 0 core.

    The appraiser is the frozen Phase 0 ``EvidenceAppraiser`` port (the
    language-understanding boundary). By default (golden mode) it is the case's
    ``ScriptedAppraiser``; a real ``EvidenceAppraiser`` (e.g. an injected
    ``ExternalEvidenceAppraiser``) may be supplied for real mode. Either way the
    frozen engine — not the appraiser — owns model revision and persistence."""

    name = "sanuvia_persistent"

    def __init__(self, case: Case, appraiser: EvidenceAppraiser | None = None) -> None:
        self._case = case
        self._appraiser = appraiser
        self._service: ReasoningService | None = None
        self._store: InMemoryReasoningStore | None = None
        self._results: list[InteractionResult] = []

    def start(self) -> None:
        # Deterministic wiring (ManualClock + SequentialIdGenerator), mirroring the
        # Phase 0 exit-test harness, so replay is byte-identical.
        store = InMemoryReasoningStore()
        scripted = self._appraiser is None
        script = dict(self._case.appraisal_script)
        appraiser: EvidenceAppraiser = (
            ScriptedAppraiser(script) if scripted else self._appraiser
        )
        # IDENTITY DECISIONS ARE AUTHORED BY THE CASE, on the scripted path only.
        #
        # A golden case can hold several distinct commitments for one subject,
        # stated by authoring a separate hypothesis id for each. attribution is
        # the governed voice label (§2 H), so those share one retrieval bound
        # and reach §2 G resolution-order case 4; the fixture-authored double
        # returns the case's own authored decision. It compares nothing.
        #
        # The guard is STRUCTURAL: the resolver is bound to the same condition
        # that selects the scripted appraiser, so a real injected appraiser --
        # the only thing a REAL/Run 003 configuration may use -- never gets one.
        # A real run therefore parks non-exact candidates, which is the honest
        # deterministic-arm behaviour until R1 lands.
        resolver = resolver_for_script(script) if scripted else None
        deps = build_in_memory_dependencies(
            store=store,
            appraiser=appraiser,
            clock=ManualClock(),
            ids=SequentialIdGenerator(),
            identity_resolver=resolver,
        )
        self._service = ReasoningService(deps)
        self._store = store
        self._results = []

    def step(self, interaction: CaseInteraction) -> TrajectoryRecord:
        if self._service is None:
            raise RuntimeError("SanuviaPersistentCondition.start() must run before step()")
        # An interaction whose extraction was rejected (ruling Q6) never
        # reaches the engine: it is already decided. The rejected-plan record
        # is emitted for it directly, so the audit shows WHY the interaction
        # produced nothing instead of it looking like an ordinary hold.
        pre_rejection = getattr(interaction, "pre_rejection", None)
        if pre_rejection is not None:
            return from_rejected_plan(
                self.name,
                interaction,
                self._case.evidence_refs(interaction),
                pre_rejection,
            )

        inputs = self._case.evidence_inputs(interaction)  # empty for a hold
        try:
            result = self._service.record_interaction(
                self._case.subject_id, inputs, space_id=self._case.space_id
            )
        except GovernedRejection as rejection:
            # TD-18 at the trajectory boundary (§5.7, §5.8). A refused plan is
            # a governed OUTCOME of the interaction, not a crash: the audit
            # must record that it happened, which observations were admitted,
            # the raw appraiser response and the governed failure.
            #
            # Previously this propagated and no trajectory record was written
            # at all, so the rejected/hold discriminator never reached the
            # audit. Rejected reasoning STATE is still gone -- the UnitOfWork
            # restored every store and counter before this point -- which is
            # exactly the distinction TD-18 asserts.
            #
            # It is not appended to ``self._results``: that list feeds
            # reasoning-state projections, and a rejected interaction
            # contributed none.
            return from_rejected_plan(
                self.name,
                interaction,
                self._case.evidence_refs(interaction),
                rejection,
            )
        self._results.append(result)
        return from_interaction_result(
            self.name,
            interaction,
            self._case.evidence_refs(interaction),
            result,
            dependency_edges=self._dependency_edges(result),
        )

    def _dependency_edges(
        self, result: InteractionResult
    ) -> tuple[DependencyEdgeView, ...]:
        """The dependency/provenance edges touching the current active hypotheses
        and predictions (Sys Arch v1.1 §5A; Eng Spec v0.4 §8A). Read via the public
        ``DependencyEdgeStore`` ports; sorted for deterministic replay."""
        if self._store is None:
            return ()
        graph = self._store.dependencies
        refs: set[str] = {str(h.hypothesis_id) for h in result.active_hypotheses}
        refs.update(str(p.id) for p in result.predictions)
        seen: dict[str, DependencyEdgeView] = {}
        for ref in refs:
            object_ref = ObjectRef(ref)
            for edge in (*graph.edges_to(object_ref), *graph.edges_from(object_ref)):
                seen[str(edge.id)] = DependencyEdgeView(
                    from_ref=str(edge.from_ref),
                    to_ref=str(edge.to_ref),
                    relation=edge.relation.value,
                )
        return tuple(
            sorted(seen.values(), key=lambda e: (e.from_ref, e.to_ref, e.relation))
        )

    def finish(self) -> None:
        return None

    def session_state(self) -> SessionState:
        """Expose the run as a Phase 0 ``SessionState`` for trace/graph rendering."""
        if self._store is None:
            raise RuntimeError("run the condition before requesting session_state()")
        return from_interactions(
            self._case.subject_id,
            self._results,
            self._store,
            space_id=self._case.space_id,
        )
