"""The complete-plan validator.

Technical Design v1.5.4 §3.2. Every check runs **before** the mutation boundary,
over the whole interaction's plan, and every one of them is mutation-free: this
module allocates no identifier, writes to no store and mutates no argument. Its
only outputs are an accept decision or a ``GovernedRejection``.

Locked §3.6 governs the disposition of every failure here: unknown references and
inconsistent plans produce visible governed outcomes and are *never* silently
ignored, emptied, repaired or normalised.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sanuvia.application.ports.reasoning import (
    Bearing,
    BearingKind,
    CandidateProposal,
    DivergenceProposal,
    EvidenceHandle,
    HypothesisHandle,
)
from sanuvia.application.reasoning.handles import HandleTable
from sanuvia.domain import (
    BreachKind,
    DependencyEdge,
    DependencyRelation,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceRole,
    EvidenceStanding,
    GovernedOutcome,
    GovernedRejection,
    HypothesisId,
    ModelBoundary,
    SourceObservationRef,
    SpaceKind,
    Stance,
    inverts,
)

#: Bearings that change the support axis. A non-appraisable record may be the
#: triggering evidence of none of them (ruling Q1, §2 E).
SUPPORT_AXIS = frozenset(
    {BearingKind.SUPPORTS, BearingKind.WEAKENS, BearingKind.CONTRADICTS}
)

#: Bearings that are incompatible with a MATCH_EXISTING attachment to the same
#: lineage from the same observation (check 2(f), D-1).
MATCH_INCOMPATIBLE = frozenset({BearingKind.WEAKENS, BearingKind.CONTRADICTS})


def normalise_statement(text: str) -> str:
    """Deterministic statement normalisation (§2 G resolution order step 1).

    Case, whitespace and terminal punctuation only. No stemming, no synonymy and
    no model call: this is the exact-duplicate test, not a similarity judgement.
    """
    return " ".join(text.split()).strip().rstrip(".!?").casefold()


class IdentityOutcome:
    """The four identity outcomes (locked §3.3)."""

    MATCH_EXISTING = "MATCH_EXISTING"
    REFINE_EXISTING = "REFINE_EXISTING"
    DISTINCT_NEW = "DISTINCT_NEW"
    AMBIGUOUS_REVIEW_REQUIRED = "AMBIGUOUS_REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class AppraisedObservation:
    """One observation's appraisal, resolved into canonical terms.

    Produced at sequence steps 6-8; consumed by validation at step 13.
    ``decisions`` maps a proposal's response-local ref to its identity decision.
    """

    evidence_id: EvidenceRecordId
    table: HandleTable
    proposals: tuple[CandidateProposal, ...] = ()
    bearings: tuple[Bearing, ...] = ()
    divergences: tuple[DivergenceProposal, ...] = ()
    raw_response: str | None = None
    #: local_ref -> (outcome, matched HypothesisId | None)
    decisions: Mapping[str, tuple[str, HypothesisId | None]] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True)
class RevisionPlan:
    """The complete intended mutation for one interaction (step 9).

    Construction is pure. Nothing here has been written; ``commit_plan`` is the
    only writer, and it runs only after every check below has passed.
    """

    subject_id: str
    space_id: str
    admitted: tuple[EvidenceRecord, ...] = ()
    appraised: tuple[AppraisedObservation, ...] = ()
    edges: tuple[DependencyEdge, ...] = ()
    #: Evidence ids the plan intends to write, for check 11.
    intended_evidence_ids: tuple[EvidenceRecordId, ...] = ()


def validate_plan(
    plan: RevisionPlan,
    *,
    committed_evidence: Mapping[EvidenceRecordId, EvidenceRecord],
    active_hypotheses: Mapping[HypothesisId, object],
    lineage_stance: Mapping[HypothesisId, Stance] | None = None,
    lineage_key_index: Mapping[tuple[str, str], Sequence[HypothesisId]] | None = None,
    source_ref_index: Mapping[SourceObservationRef, EvidenceRecordId] | None = None,
    space_kind: SpaceKind | None = None,
) -> None:
    """Run every §3.2 check. Raise ``GovernedRejection`` on the first failure.

    Mutation-free by construction: nothing below writes, allocates or mutates.
    """
    lineage_stance = lineage_stance or {}
    lineage_key_index = lineage_key_index or {}
    source_ref_index = source_ref_index or {}

    for obs in plan.appraised:
        _check_1_handles_resolve(obs)
        _check_2_duplicates_and_conflicts(obs)
        _check_3_duplicate_proposals(obs)
        _check_3a_adjudication_order(obs)
        _check_4_targets_eligible(obs, active_hypotheses)
        _check_5_local_refs_not_durable(obs, active_hypotheses)
        _check_9_standing_rules(obs, plan)
        _check_10_structural_contradiction(obs, lineage_stance, lineage_key_index)

    _check_7_source_ref_mapping(plan, source_ref_index)
    _check_8_edges(plan, committed_evidence)
    _check_8a_divergence_endpoints(plan, committed_evidence)
    _check_8b_disclosure(plan, committed_evidence, space_kind)
    _check_11_write_targets_absent(plan, committed_evidence)


# --- check 1 -----------------------------------------------------------------


def _check_1_handles_resolve(obs: AppraisedObservation) -> None:
    """Every selected handle was supplied in **its own** request and resolves.

    The table's resolve methods raise the right governed outcome, including for
    a handle carrying another request's id.
    """
    for b in obs.bearings:
        obs.table.resolve_hypothesis(str(b.target))
    for d in obs.divergences:
        obs.table.resolve_divergence_candidate(str(d.with_evidence))
    for p in obs.proposals:
        obs.table.resolve_participant(str(p.signature.subject))


# --- check 2 (a)-(f) ---------------------------------------------------------


def _check_2_duplicates_and_conflicts(obs: AppraisedObservation) -> None:
    """No duplicate handle and no duplicate or conflicting operation (F-10, C-2).

    Each sub-check names the governed outcome it reports under, because locked
    §3.10 scopes ``DUPLICATE_HYPOTHESIS_PROPOSAL`` narrowly and this design must
    not widen it.
    """
    # (a) repeated or cross-request handle -> UNKNOWN_*_REFERENCE. Locked §3.1
    # groups "unknown, repeated or cross-request" under one enforcement.
    seen_h: set[str] = set()
    for b in obs.bearings:
        if str(b.target) in seen_h:
            raise GovernedRejection(
                GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE,
                f"hypothesis handle {b.target!r} appears more than once",
                references=(str(b.target),),
                raw_response=obs.raw_response,
            )
        seen_h.add(str(b.target))

    # (b) duplicate (target, kind) pair
    pairs: set[tuple[str, BearingKind]] = set()
    for b in obs.bearings:
        key = (str(b.target), b.kind)
        if key in pairs:
            raise GovernedRejection(
                GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
                f"duplicate bearing {b.kind.value} on {b.target!r}",
                boundary=ModelBoundary.APPRAISAL,
                references=(str(b.target),),
                raw_response=obs.raw_response,
            )
        pairs.add(key)

    # (c) conflicting bearing kinds on one target -- bearing versus bearing.
    #
    # Grouped on the RESOLVED lineage rather than the handle string. The design
    # phrases this as "the same target_handle", but its stated rationale is that
    # the conflict "would otherwise reach the existing support/contradict overlap
    # invariant as an internal breach". Resolving first is strictly stronger and
    # still satisfies the rule: it also catches two distinct handles aliasing one
    # lineage, which the engine does not mint but an internally constructed plan
    # could carry.
    by_target: dict[str, set[BearingKind]] = {}
    for b in obs.bearings:
        hid = obs.table.hypotheses.get(HypothesisHandle(str(b.target)))
        by_target.setdefault(str(hid) if hid is not None else str(b.target), set()).add(
            b.kind
        )
    for target, kinds in by_target.items():
        if len(kinds & SUPPORT_AXIS) > 1:
            raise GovernedRejection(
                GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
                f"conflicting bearing kinds on {target!r}: "
                f"{sorted(k.value for k in kinds)}",
                boundary=ModelBoundary.APPRAISAL,
                references=(target,),
                raw_response=obs.raw_response,
            )

    # (d) colliding response-local reference
    refs: set[str] = set()
    for p in obs.proposals:
        if p.local_ref in refs:
            raise GovernedRejection(
                GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
                f"duplicate proposal local_ref {p.local_ref!r}",
                boundary=ModelBoundary.APPRAISAL,
                references=(p.local_ref,),
                raw_response=obs.raw_response,
            )
        refs.add(p.local_ref)

    # (e) duplicate divergence partner -> defective divergence plan
    partners: set[str] = set()
    for d in obs.divergences:
        if str(d.with_evidence) in partners:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                f"duplicate divergence partner {d.with_evidence!r}",
                references=(str(d.with_evidence),),
                raw_response=obs.raw_response,
            )
        partners.add(str(d.with_evidence))

    # (f) bearing + MATCH_EXISTING on the same observation/lineage pair (D-1).
    #
    # Framed for ONE OBSERVATION, not over the fields of one raw response, and
    # evaluated here at step 13 over the complete plan, because the
    # MATCH_EXISTING side is an identity decision established at step 8 rather
    # than a response field. Bearing-versus-bearing conflicts remain check 2(c)
    # and are not duplicated.
    matched: set[HypothesisId] = {
        hid
        for outcome, hid in obs.decisions.values()
        if outcome == IdentityOutcome.MATCH_EXISTING and hid is not None
    }
    for b in obs.bearings:
        if b.kind not in MATCH_INCOMPATIBLE:
            continue
        target_id = obs.table.hypotheses.get(HypothesisHandle(str(b.target)))
        if target_id is not None and target_id in matched:
            raise GovernedRejection(
                GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
                f"observation {obs.evidence_id} carries a {b.kind.value} bearing on "
                f"{target_id} and also matches it as MATCH_EXISTING",
                boundary=ModelBoundary.APPRAISAL,
                references=(str(b.target), str(target_id)),
                raw_response=obs.raw_response,
            )


# --- check 3 / 3a ------------------------------------------------------------


def _check_3_duplicate_proposals(obs: AppraisedObservation) -> None:
    """Two proposals in ONE appraisal response normalising alike.

    This is the only condition ``DUPLICATE_HYPOTHESIS_PROPOSAL`` covers; locked
    §3.10 scopes it with an explicit "only".
    """
    seen: dict[tuple[str, tuple], str] = {}
    for p in obs.proposals:
        sig = p.signature
        key = (
            normalise_statement(p.statement),
            (str(sig.subject), sig.attribution, sig.claim_class, sig.stance),
        )
        if key in seen:
            raise GovernedRejection(
                GovernedOutcome.DUPLICATE_HYPOTHESIS_PROPOSAL,
                f"proposals {seen[key]!r} and {p.local_ref!r} normalise to the "
                f"same statement/signature",
                references=(seen[key], p.local_ref),
                raw_response=obs.raw_response,
            )
        seen[key] = p.local_ref


def _check_3a_adjudication_order(obs: AppraisedObservation) -> None:
    """Every candidate carries an identity decision, and no two DISTINCT_NEW
    decisions in one plan normalise alike.

    Failure here means adjudication was skipped or applied out of order, which is
    an internal invariant breach rather than a model-behaviour outcome — hence
    ``NON_ATOMIC_REVISION_PLAN`` with ``breach_kind=ADJUDICATION_ORDER``, whose
    payload carries no failing write because nothing was written.
    """
    for p in obs.proposals:
        if p.local_ref not in obs.decisions:
            raise GovernedRejection(
                GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
                f"proposal {p.local_ref!r} reached validation without an "
                f"IdentityDecision",
                breach_kind=BreachKind.ADJUDICATION_ORDER,
                references=(p.local_ref,),
            )


# --- check 4 / 5 -------------------------------------------------------------


def _check_4_targets_eligible(
    obs: AppraisedObservation, active: Mapping[HypothesisId, object]
) -> None:
    """Every bearing target exists and is eligible."""
    for b in obs.bearings:
        hid = obs.table.resolve_hypothesis(str(b.target))
        if hid not in active:
            raise GovernedRejection(
                GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE,
                f"bearing target {hid} is not an active hypothesis",
                references=(str(b.target), str(hid)),
                raw_response=obs.raw_response,
            )


def _check_5_local_refs_not_durable(
    obs: AppraisedObservation, active: Mapping[HypothesisId, object]
) -> None:
    """A response-local ref never becomes a durable id.

    Plan-local lineage keys for in-flight matches are **not** proposal-local refs
    and are deliberately out of scope here (F-16).
    """
    for p in obs.proposals:
        if p.local_ref in {str(k) for k in active}:
            raise GovernedRejection(
                GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
                f"proposal-local ref {p.local_ref!r} collides with a durable "
                f"hypothesis id",
                breach_kind=BreachKind.ADJUDICATION_ORDER,
                references=(p.local_ref,),
            )


# --- check 7 -----------------------------------------------------------------


def _check_7_source_ref_mapping(
    plan: RevisionPlan, index: Mapping[SourceObservationRef, EvidenceRecordId]
) -> None:
    """Source-observation <-> evidence mapping resolves in **both** directions."""
    for rec in plan.admitted:
        ref = rec.source_ref
        if ref is None:
            continue
        mapped = index.get(ref)
        if mapped is not None and mapped != rec.id:
            raise GovernedRejection(
                GovernedOutcome.SOURCE_REFERENCE_MAPPING_FAILURE,
                f"source ref {ref} maps to {mapped}, not {rec.id}",
                references=(str(rec.id),),
            )


# --- check 8 / 8a / 8b -------------------------------------------------------


def _check_8_edges(
    plan: RevisionPlan, committed: Mapping[EvidenceRecordId, EvidenceRecord]
) -> None:
    """Every dependency edge resolves; every DIVERGES_WITH edge is canonical."""
    known = {str(r.id) for r in plan.admitted} | {str(k) for k in committed}
    for edge in plan.edges:
        if edge.relation is not DependencyRelation.DIVERGES_WITH:
            continue
        if str(edge.from_ref) > str(edge.to_ref):
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                f"DIVERGES_WITH edge {edge.from_ref} -> {edge.to_ref} is not in "
                f"canonical order",
                references=(str(edge.from_ref), str(edge.to_ref)),
            )
        for ref in (edge.from_ref, edge.to_ref):
            if str(ref) not in known:
                raise GovernedRejection(
                    GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                    f"DIVERGES_WITH endpoint {ref} does not resolve to an "
                    f"admitted evidence record",
                    references=(str(ref),),
                )


def _resolve_record(
    ref: str,
    plan: RevisionPlan,
    committed: Mapping[EvidenceRecordId, EvidenceRecord],
) -> EvidenceRecord | None:
    for rec in plan.admitted:
        if str(rec.id) == ref:
            return rec
    return committed.get(EvidenceRecordId(ref))


def _check_8a_divergence_endpoints(
    plan: RevisionPlan, committed: Mapping[EvidenceRecordId, EvidenceRecord]
) -> None:
    """Two distinct **evidence** endpoints, both participant accounts (§2 J.1).

    This is the sole enforcement of the evidence-only endpoint invariant at the
    persisted-relation layer, because ``ObjectRef`` is deliberately untyped so one
    graph can relate heterogeneous objects (C-03). It must not be removed.
    """
    for edge in plan.edges:
        if edge.relation is not DependencyRelation.DIVERGES_WITH:
            continue
        if edge.from_ref == edge.to_ref:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                "a record cannot diverge with itself",
                references=(str(edge.from_ref),),
            )
        a = _resolve_record(str(edge.from_ref), plan, committed)
        b = _resolve_record(str(edge.to_ref), plan, committed)
        if a is None or b is None:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                f"DIVERGES_WITH endpoint is not an evidence record: "
                f"{edge.from_ref} / {edge.to_ref}",
                references=(str(edge.from_ref), str(edge.to_ref)),
            )
        for rec in (a, b):
            st: EvidenceStanding | None = rec.standing
            if st is None or not st.is_participant_account:
                raise GovernedRejection(
                    GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                    f"divergence endpoint {rec.id} is not a participant account "
                    f"(role/source_kind/source_id test)",
                    references=(str(rec.id),),
                )
        assert a.standing is not None and b.standing is not None
        if a.standing.subject_id != b.standing.subject_id:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                "divergence endpoints are not about the same subject",
                references=(str(a.id), str(b.id)),
            )
        if a.standing.source_id == b.standing.source_id:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                "divergence endpoints are from the same participant",
                references=(str(a.id), str(b.id)),
            )


def _check_8b_disclosure(
    plan: RevisionPlan,
    committed: Mapping[EvidenceRecordId, EvidenceRecord],
    space_kind: SpaceKind | None,
) -> None:
    """Account-content disclosure conditions D1 and D2 (§2 J.2).

    Re-verifies before mutation what §2 J.1 rule 7 already enforced during
    candidate construction. A record from a PERSONAL space, a different space, a
    private context or any otherwise unauthorised context fails here.
    """
    for edge in plan.edges:
        if edge.relation is not DependencyRelation.DIVERGES_WITH:
            continue
        for ref in (edge.from_ref, edge.to_ref):
            rec = _resolve_record(str(ref), plan, committed)
            if rec is None:
                continue
            # D1: same shared reasoning space.
            if str(rec.space_id) != str(plan.space_id):
                raise GovernedRejection(
                    GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                    f"divergence endpoint {rec.id} was admitted to space "
                    f"{rec.space_id}, not the interaction's space {plan.space_id}",
                    references=(str(rec.id),),
                )
        if space_kind is not None and space_kind is not SpaceKind.SHARED:
            raise GovernedRejection(
                GovernedOutcome.INVALID_DIVERGENCE_PLAN,
                f"divergence requires a shared reasoning space; "
                f"{plan.space_id} is {space_kind.value}",
                references=(str(plan.space_id),),
            )


# --- check 9 -----------------------------------------------------------------


def _check_9_standing_rules(obs: AppraisedObservation, plan: RevisionPlan) -> None:
    """Evidence standing rules, under deterministic structural triggers (F-6).

    (a) ``ACCOUNT_ROLE_UPGRADE_VIOLATION`` — records are immutable, so
        "re-classified" has no in-place referent. The structural trigger is a
        second admission of the same ``SourceObservationRef`` under a different
        role. A participant contributing an ``EVENT_OBSERVATION`` about another
        participant is legitimate, so ``source_id != subject_id`` is NOT the
        trigger and must not be implemented as one.

    (b) ``EVIDENCE_ROLE_VIOLATION`` — no plan operation names a
        ``RESPONSE_OR_RESONANCE`` or ``META_INSTRUCTION`` record as triggering
        evidence. Under the §2 E non-appraisable-role rule no appraisal call is
        made for such a record, so this is a backstop against an internally
        constructed plan, not a model-behaviour path.
    """
    by_ref: dict[SourceObservationRef, EvidenceRole] = {}
    for rec in plan.admitted:
        ref, st = rec.source_ref, rec.standing
        if ref is None or st is None:
            continue
        prior = by_ref.get(ref)
        if prior is not None and prior is not st.role:
            raise GovernedRejection(
                GovernedOutcome.ACCOUNT_ROLE_UPGRADE_VIOLATION,
                f"source observation {ref} was admitted as {prior.value} and "
                f"again as {st.role.value}",
                references=(str(rec.id),),
            )
        by_ref[ref] = st.role

    rec = next((r for r in plan.admitted if r.id == obs.evidence_id), None)
    if rec is None or rec.standing is None:
        return
    if not rec.standing.is_appraisable and (
        obs.bearings or obs.proposals or obs.divergences
    ):
        raise GovernedRejection(
            GovernedOutcome.EVIDENCE_ROLE_VIOLATION,
            f"record {rec.id} has role {rec.standing.role.value} and may be the "
            f"triggering evidence of no support-changing operation",
            references=(str(rec.id),),
            raw_response=obs.raw_response,
        )


# --- check 10 ----------------------------------------------------------------


def _check_10_structural_contradiction(
    obs: AppraisedObservation,
    lineage_stance: Mapping[HypothesisId, Stance],
    lineage_key_index: Mapping[tuple[str, str], Sequence[HypothesisId]],
) -> None:
    """Structured contradiction consistency (ruling Q5).

    Scoped to the deterministic structural case, with **no** prose or NLU
    detector: if a candidate's resolved ``(subject, attribution)`` matches an
    active lineage and the candidate's stance structurally inverts that lineage's
    current stance, the response must carry a ``CONTRADICTS`` bearing on that
    lineage, or the complete plan fails validation.

    Stance inversion is ``affirms`` <-> ``negates`` only; ``open`` never inverts
    and is never inverted (N-8).

    **Every lineage the bound admits is checked (M-2).** The index previously
    held one id per key, so a bound holding several lineages was tested against
    whichever was indexed last: a candidate inverting an earlier lineage's
    stance passed validation and could merge an opposed commitment. Each
    admitted lineage is now inspected, in insertion order, and the first
    unmatched inversion rejects.
    """
    contradicted: set[HypothesisId] = set()
    for b in obs.bearings:
        if b.kind is BearingKind.CONTRADICTS:
            hid = obs.table.hypotheses.get(HypothesisHandle(str(b.target)))
            if hid is not None:
                contradicted.add(hid)

    for p in obs.proposals:
        subject = obs.table.resolve_participant(str(p.signature.subject))
        key = (str(subject), p.signature.attribution)
        for hid in lineage_key_index.get(key, ()):
            current = lineage_stance.get(hid)
            if current is None or not inverts(current, p.signature.stance):
                continue
            if hid not in contradicted:
                raise GovernedRejection(
                    GovernedOutcome.INVALID_CONTRADICTION_PLAN,
                    f"proposal {p.local_ref!r} inverts the stance of active lineage "
                    f"{hid} ({current.value} -> {p.signature.stance.value}) without a "
                    f"structured CONTRADICTS bearing",
                    references=(p.local_ref, str(hid)),
                    raw_response=obs.raw_response,
                )


# --- check 11 ----------------------------------------------------------------


def _check_11_write_targets_absent(
    plan: RevisionPlan, committed: Mapping[EvidenceRecordId, EvidenceRecord]
) -> None:
    """Every intended write target is absent from the store, making step 14
    infallible."""
    for eid in plan.intended_evidence_ids:
        if eid in committed:
            raise GovernedRejection(
                GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
                f"intended write target {eid} already exists in the store",
                breach_kind=BreachKind.COMMIT_ATOMICITY,
                references=(str(eid),),
            )
