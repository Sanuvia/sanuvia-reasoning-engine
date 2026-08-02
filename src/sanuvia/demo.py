"""End-to-end API demonstration.

Shows a complete interaction through the *existing* API contract — nothing
special-cased:

    EvidenceInput  --ReasoningService.record_interaction-->  Core Loop
                   -->  WorldModel revision  -->  InteractionResult
                   -->  WorldModelView (read-only)

It uses the in-memory adapters and a scripted appraiser (the Phase-0 stand-in for
the language-understanding boundary), so it runs with no infrastructure and is
fully deterministic.

Run it::

    python -m sanuvia.demo
"""

from __future__ import annotations

from collections.abc import Sequence

from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.application.reasoning.core_loop import InteractionResult
from sanuvia.domain import EvidenceClass, EvidenceRecordId, HypothesisId, SubjectId

SUBJECT = SubjectId("alex-jordan")
H_AVOID = HypothesisId("H_conflict_avoidance")
H_REASSURE = HypothesisId("H_need_for_reassurance")


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.3f}"


def _build_service() -> ReasoningService:
    # The service assigns evidence ids deterministically ("evidence-1", ...),
    # so the scripted appraiser is keyed by those ids. In production this
    # ScriptedAppraiser is replaced by an FM-backed appraiser behind the same port.
    script = {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(
                ProposedHypothesis(H_AVOID, "tends to avoid conflict", 0.4, ()),
                ProposedHypothesis(H_REASSURE, "seeks reassurance", 0.4, ()),
            )
        ),
        EvidenceRecordId("evidence-2"): Appraisal(supports=(H_REASSURE,)),
    }
    deps = build_in_memory_dependencies(
        appraiser=ScriptedAppraiser(script),
        clock=ManualClock(),
        ids=SequentialIdGenerator(),
    )
    return ReasoningService(deps)


def _print_interaction(n: int, submitted: EvidenceInput, r: InteractionResult) -> None:
    print(f"\n--- Interaction {n} ---")

    print("[1] EvidenceInput submitted")
    print(
        f"      class={submitted.evidence_class.value} "
        f"reliability={submitted.reliability:.2f} "
        f'content="{submitted.content}"'
    )

    print("[2] Core Loop")
    before = r.model_version_before or "(genesis — no model yet)"
    print(f"      get_current_model         -> {before}")
    print(f"      get_user_cognitive_state  -> {r.cognitive_state.value}")
    print(f"      select_acquisition_strategy -> {r.acquisition_strategy.value}")
    if r.revision_result.anomaly_resolutions:
        for a in r.revision_result.anomaly_resolutions:
            print(f"      anomaly                   -> {a.disposition.value}")
    if r.revision_result.revision_events:
        print("      revise_model              ->")
        for ev in r.revision_result.revision_events:
            print(
                f"          {ev.id}: {ev.outcome.value} {ev.affected_object_id} "
                f"(from {', '.join(ev.triggering_evidence_ids)})"
            )
    else:
        print("      revise_model              -> no committed revision (model holds)")

    print("[3] WorldModel change")
    after_version = r.model.model_version_id if r.model else "(none)"
    print(
        f"      version:     {r.model_version_before or '(none)'} -> {after_version}"
    )
    print(
        f"      uncertainty: {_fmt(r.model_uncertainty_before)} -> "
        f"{_fmt(r.model_uncertainty)}"
    )

    print("[4] Response (InteractionResult)")
    print("      active hypotheses:")
    for h in r.active_hypotheses:
        print(f"          {h.hypothesis_id:<26} support {h.support.value:.3f}")
    if r.predictions:
        print("      predictions:")
        for p in r.predictions:
            print(
                f"          {p.id}: likelihood {p.likelihood.value:.3f} "
                f"({p.trajectory.kind.value})"
            )
    else:
        print("      predictions: none")
    if r.inquiry is not None:
        print(f'      inquiry: {r.inquiry.id} "{r.inquiry.statement}"')
    else:
        print("      inquiry: none")


def run() -> None:
    service = _build_service()

    interactions: Sequence[EvidenceInput] = (
        EvidenceInput(
            subject_id=SUBJECT,
            evidence_class=EvidenceClass.BEHAVIOURAL,
            content="went quiet and changed the subject during a disagreement",
            source="reflection:session-1",
            reliability=0.70,
            classification_confidence=0.9,
        ),
        EvidenceInput(
            subject_id=SUBJECT,
            evidence_class=EvidenceClass.BEHAVIOURAL,
            content="asked several times whether everything was still okay",
            source="reflection:session-2",
            reliability=0.85,
            classification_confidence=0.9,
        ),
    )

    print("=== Sanuvia Persistent Reasoning Core — end-to-end API demo ===")
    print(f"Subject: {SUBJECT}")

    for i, item in enumerate(interactions, start=1):
        result = service.record_interaction(SUBJECT, [item])
        _print_interaction(i, item, result)

    # The read path: a read-only projection of current understanding.
    print("\n--- Read path: WorldModelView.understanding() ---")
    snap = service.view().understanding(SUBJECT)
    print(f"      current version:  {snap.model_version_id}")
    print(f"      uncertainty:      {_fmt(snap.model_uncertainty)}")
    print(f"      revisions so far: {snap.revision_count}")
    print("      hypotheses:")
    for h in snap.hypotheses:
        print(f"          {h.hypothesis_id:<26} support {h.support.value:.3f}")
    print("      predictions:")
    for p in snap.predictions:
        print(f"          {p.id}: likelihood {p.likelihood.value:.3f}")
    print(
        "\nNote: the view exposes only queries — it has no method that could "
        "mutate reasoning state."
    )


if __name__ == "__main__":
    run()
