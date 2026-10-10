"""Normalization — turn each condition's native output into a TrajectoryRecord.

Two entry points:

* :func:`from_interaction_result` — the frozen Phase 0 ``InteractionResult``
  (Sanuvia condition). Real support/uncertainty/revision/provenance are captured.
* :func:`from_baseline_turn` — a parsed foundation-model ``BaselineTurn`` (FM
  conditions). Engine-only quantities are left ``None`` — never faked.

:func:`parse_baseline_turn` parses the constrained-JSON response contract (§9)
into a ``BaselineTurn``; it is a strict structured reader, **not** an NLU parser
for arbitrary prose.
"""

from __future__ import annotations

import json
from typing import Any

from sanuvia.application.reasoning.core_loop import InteractionResult

from .case import CaseInteraction
from .failures import BoundaryKind
from .validation import validate_baseline
from sanuvia.domain import GovernedRejection

from .trajectory import (
    InteractionOutcome,
    BaselineTurn,
    ContinuityClaim,
    DependencyEdgeView,
    HeldHypothesis,
    HypothesisView,
    InquiryView,
    PredictionView,
    RecognitionView,
    RevisionEventView,
    TrajectoryRecord,
)


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# --- Sanuvia condition --------------------------------------------------------


def from_interaction_result(
    condition: str,
    interaction: CaseInteraction,
    evidence_refs: tuple[str, ...],
    result: InteractionResult,
    dependency_edges: tuple[DependencyEdgeView, ...] = (),
) -> TrajectoryRecord:
    hypotheses = tuple(
        HypothesisView(
            hypothesis_id=str(h.hypothesis_id),
            statement=h.statement,
            support=h.support.value,
            status="active",
            supporting_evidence_ids=tuple(str(e) for e in h.supporting_evidence_ids),
            contradicting_evidence_ids=tuple(
                str(e) for e in h.contradicting_evidence_ids
            ),
        )
        for h in result.active_hypotheses
    )

    inquiry: InquiryView | None = None
    if result.inquiry is not None:
        inquiry = InquiryView(
            inquiry_id=str(result.inquiry.id),
            statement=result.inquiry.statement,
            activated_hypothesis_ids=tuple(
                str(x) for x in result.inquiry.activated_hypothesis_ids
            ),
            status=result.inquiry.status.value,  # §8A/§5A Inquiry status lifecycle
        )

    predictions = tuple(
        PredictionView(
            prediction_id=str(p.id),
            trajectory_kind=p.trajectory.kind.value,
            likelihood=p.likelihood.value,
            model_version_id=str(p.model_version_id),
            derived_from_hypothesis_ids=tuple(
                str(h) for h in p.derived_from_hypothesis_ids
            ),
            derived_from_evidence_ids=tuple(
                str(e) for e in p.derived_from_evidence_ids
            ),
        )
        for p in result.predictions
    )

    revisions = result.revision_events_since_prior
    revision_events = tuple(
        RevisionEventView(
            sequence_no=entry.sequence_no,
            outcome=entry.revision_event.outcome.value,
            affected_object_id=str(entry.revision_event.affected_object_id),
            triggering_evidence_ids=tuple(
                str(e) for e in entry.revision_event.triggering_evidence_ids
            ),
            from_model_version_id=(
                None
                if entry.revision_event.from_model_version_id is None
                else str(entry.revision_event.from_model_version_id)
            ),
            to_model_version_id=(
                None
                if entry.revision_event.to_model_version_id is None
                else str(entry.revision_event.to_model_version_id)
            ),
        )
        for entry in revisions
    )

    # Recognition Condition RECORDS the engine actually emitted. In Phase 0 the
    # detection computation (detect_recognition_condition) is interface-only and
    # deferred, so the store is not written to — this is normally ``()``. We
    # surface exactly what the engine emits and fabricate no judgment.
    recognition_records = tuple(
        RecognitionView(
            recognition_id=str(r.id),
            kind=r.kind.value,
            description=r.description,
            supporting_evidence_ids=tuple(str(e) for e in r.supporting_evidence_ids),
            model_version_id=str(r.model_version_id),
        )
        for r in result.recognition_events
    )

    # Every committed RevisionEvent must cite triggering evidence (a Phase 0
    # domain invariant); we verify it rather than assume it.
    provenance_traceable = all(
        len(entry.revision_event.triggering_evidence_ids) > 0 for entry in revisions
    )

    if result.committed and result.model is not None:
        model_version_id: str | None = str(result.model.model_version_id)
    elif result.model_version_before is not None:
        model_version_id = str(result.model_version_before)
    else:
        model_version_id = None

    raw = _canonical(
        {
            "committed": result.committed,
            "uncertainty_before": result.model_uncertainty_before,
            "uncertainty_after": result.model_uncertainty,
            "revision_outcomes": [
                e.revision_event.outcome.value for e in revisions
            ],
        }
    )

    return TrajectoryRecord(
        condition=condition,
        interaction_index=interaction.index,
        seq_label=interaction.seq_label,
        ingested_evidence_ids=evidence_refs,
        hypotheses=hypotheses,
        inquiry=inquiry,
        predictions=predictions,
        unsupported_memory_claims=(),  # the engine never invents memory
        raw=raw,
        model_uncertainty=result.model_uncertainty,
        revision_count=len(revisions),
        provenance_traceable=provenance_traceable,
        model_version_id=model_version_id,
        revision_events=revision_events,
        recognition_records=recognition_records,
        dependency_edges=dependency_edges,
        # §5.7: a committed interaction and a hold are both "nothing was
        # refused"; they differ by whether a new version committed.
        outcome=(
            InteractionOutcome.COMMITTED
            if result.committed
            else (
                InteractionOutcome.NO_EVIDENCE_HOLD
                if not evidence_refs
                else InteractionOutcome.HELD
            )
        ),
        governed_failure=None,
        committed=bool(result.committed),
    )


def from_rejected_plan(
    condition: str,
    interaction: CaseInteraction,
    evidence_refs: tuple[str, ...],
    rejection: GovernedRejection,
) -> TrajectoryRecord:
    """The audit record for an interaction whose plan was REFUSED (§5.7, §5.8).

    TD-18 is a distinction between two boundaries, and this is the one it is
    specified at. Rejected reasoning *state* does not survive -- the UnitOfWork
    restored every store and every identifier counter. The *interaction* does:
    the observations that were admitted, the raw appraiser response where an
    appraisal call occurred (F-15), the governed outcome, and an explicit
    ``committed: false``.

    Without this, a rejected plan propagated as an exception and NO trajectory
    record was written at all -- the observations, the raw response and the
    rejected/hold discriminator were simply absent from the audit.

    Every reasoning-state view is empty, because nothing was committed. That is
    what distinguishes this record from ``NO_EVIDENCE_HOLD``, which is empty
    for the opposite reason: it admitted no observations and built no plan. The
    two can never be confused, because the hold carries no observations and no
    raw response -- a structural difference, not a flag.

    ``raw`` carries every appraisal response collected for the interaction, in
    call order and attributed to the observation each answered. A single field
    cannot represent a multi-record interaction: a rejection on the third
    observation would otherwise discard what the appraiser returned for the
    first two.
    """
    return TrajectoryRecord(
        condition=condition,
        interaction_index=interaction.index,
        seq_label=interaction.seq_label,
        # Present, with refs -- evidence WAS admitted before the refusal.
        ingested_evidence_ids=evidence_refs,
        # All reasoning-state views empty: nothing committed.
        hypotheses=(),
        inquiry=None,
        predictions=(),
        unsupported_memory_claims=(),
        # §5.8: the raw appraiser response, canonical-JSON echoed like every
        # other trajectory record's ``raw``. ``appraisal_responses`` is an
        # ordered, attributed list so a multi-record interaction shows what the
        # appraiser returned for EACH observation, including the failing one --
        # an earlier record's response is not lost because a later record
        # rejected.
        raw=_canonical(
            {
                "outcome": InteractionOutcome.REJECTED_PLAN.value,
                "governed_failure": rejection.outcome.value,
                "committed": False,
                "boundary": (
                    rejection.boundary.value
                    if rejection.boundary is not None
                    else None
                ),
                "boundary_raw_response": rejection.raw_response,
                "boundary_provenance": dict(rejection.provenance),
                "appraisal_responses": [
                    {"evidence_id": evidence_id, "raw_response": raw_response}
                    for evidence_id, raw_response in rejection.appraisal_responses
                ],
            }
        ),
        model_uncertainty=None,
        revision_count=0,
        provenance_traceable=None,
        model_version_id=None,
        revision_events=(),
        recognition_records=(),
        dependency_edges=(),
        outcome=InteractionOutcome.REJECTED_PLAN,
        governed_failure=rejection.outcome.value,
        committed=False,
        appraisal_responses=tuple(rejection.appraisal_responses),
        boundary=(
            rejection.boundary.value if rejection.boundary is not None else None
        ),
        # The failing boundary's own raw response, kept SEPARATE from the
        # interaction's appraisal responses above. For a resolver failure both
        # boundaries were crossed in the same interaction, and replacing one
        # with the other would lose half the evidence needed to read it.
        boundary_raw_response=rejection.raw_response,
        boundary_provenance=tuple(rejection.provenance),
    )


# --- Foundation-model conditions ---------------------------------------------


def parse_baseline_turn(
    json_text: str,
    boundary: BoundaryKind = BoundaryKind.STATELESS_BASELINE,
) -> BaselineTurn:
    """Parse the constrained-JSON baseline response contract into a BaselineTurn.

    Delegates to the strict :func:`~sanuvia_phase1.validation.validate_baseline`:
    a non-object reply, an ill-typed field, or a held hypothesis / continuity
    claim missing a required field raises ``MalformedOutputError`` (tagged with
    ``boundary``) — it is never coerced into empty hypotheses or default values.
    An *absent* optional key is treated as a legitimately empty answer, which is a
    distinct (documented) case from malformed output.
    """
    validated = validate_baseline(json_text, boundary)
    return BaselineTurn(
        best_explanations=validated.best_explanations,
        competing_hypotheses_held=tuple(
            HeldHypothesis(hypothesis_id=h.hypothesis_id, statement=h.statement)
            for h in validated.competing_hypotheses_held
        ),
        question_asked=validated.question_asked,
        continuity_claims=tuple(
            ContinuityClaim(text=c.text, cited_evidence_id=c.cited_evidence_id)
            for c in validated.continuity_claims
        ),
    )


def from_baseline_turn(
    condition: str,
    interaction: CaseInteraction,
    evidence_refs: tuple[str, ...],
    turn: BaselineTurn,
    raw_json: str,
) -> TrajectoryRecord:
    hypotheses = tuple(
        HypothesisView(
            hypothesis_id=h.hypothesis_id,
            statement=h.statement,
            support=None,  # FM baselines hold no structured support value
            status="held",
        )
        for h in turn.competing_hypotheses_held
    )

    inquiry: InquiryView | None = None
    if turn.question_asked is not None:
        inquiry = InquiryView(
            inquiry_id=None, statement=turn.question_asked, activated_hypothesis_ids=()
        )

    # An "unsupported memory" claim is a continuity claim with no citation.
    unsupported = tuple(
        c for c in turn.continuity_claims if c.cited_evidence_id is None
    )

    return TrajectoryRecord(
        condition=condition,
        interaction_index=interaction.index,
        seq_label=interaction.seq_label,
        ingested_evidence_ids=evidence_refs,
        hypotheses=hypotheses,
        inquiry=inquiry,
        predictions=(),  # FM baselines emit no structured predictions in this contract
        unsupported_memory_claims=unsupported,
        raw=_canonical(json.loads(raw_json)),
        model_uncertainty=None,
        revision_count=None,
        provenance_traceable=None,
        model_version_id=None,
        revision_events=(),  # FM baselines produce no structured revisions
        recognition_records=None,  # not applicable to a foundation-model baseline
    )
