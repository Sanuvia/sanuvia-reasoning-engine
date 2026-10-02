"""Request-scoped handles and the closed divergence-candidate set.

Technical Design v1.5.4 §2 B and §2 J.1.

The handle table is **engine-owned and authoritative**. The adapter receives it,
renders it, resolves returned values against it, and never extends it. Canonical
ids and durable participant identifiers never cross into model-facing fields.

The evidence handle space has exactly two parts and they are not interchangeable:

* ``observation`` — the one record under appraisal. Proposal support attaches to
  it deterministically; the model never *selects* it.
* ``divergence_candidates`` — a closed, engine-selected set the model may select
  from **only** as divergence partners. Selecting one has no effect on support,
  weakening or contradiction.

That second part is the "closed selectable set with a demonstrated use case"
locked §3.1 permits as the sole exception to removing free-form evidence
selection. The demonstrated use case is divergence and nothing else, which is why
no model-facing field can carry an evidence identifier as *support*.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sanuvia.application.ports.reasoning import (
    CommitmentSignatureView,
    EvidenceCandidateView,
    EvidenceHandle,
    EvidenceStandingView,
    HypothesisHandle,
    HypothesisView,
    ObservationView,
    ParticipantLabel,
)
from sanuvia.domain import (
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceStanding,
    GovernedOutcome,
    GovernedRejection,
    Hypothesis,
    HypothesisId,
    ParticipantId,
)

#: §2 J.1 rule 8 (R7). At most the eight most-recent eligible accounts are
#: offered. There is **no** time-window expiry: an eligible account does not
#: become ineligible through age alone.
MAX_DIVERGENCE_CANDIDATES = 8


@dataclass(frozen=True, slots=True)
class HandleTable:
    """The authoritative per-call handle table (§2 B).

    Every handle and label carries the ``request_id``, so one from another
    request fails resolution rather than silently aliasing.
    """

    request_id: str
    observation: EvidenceHandle
    observation_id: EvidenceRecordId
    divergence_candidates: Mapping[EvidenceHandle, EvidenceRecordId] = field(
        default_factory=dict
    )
    hypotheses: Mapping[HypothesisHandle, HypothesisId] = field(default_factory=dict)
    participants: Mapping[ParticipantLabel, ParticipantId] = field(default_factory=dict)

    # -- authoritative resolution -------------------------------------------
    #
    # The adapter may pre-check these as a convenience (§1.2); these are the
    # authoritative calls, and they are what check 1 and check 2(a) run.

    def resolve_divergence_candidate(self, handle: str) -> EvidenceRecordId:
        """Resolve a divergence partner handle, or reject visibly.

        An unknown handle, a handle from another request, and a handle naming
        the observation itself all fail here. Locked §3.6 forbids treating any
        of them as a silent no-op.
        """
        resolved = self.divergence_candidates.get(EvidenceHandle(handle))
        if resolved is None:
            raise GovernedRejection(
                GovernedOutcome.UNKNOWN_EVIDENCE_REFERENCE,
                f"evidence handle {handle!r} was not supplied in request "
                f"{self.request_id!r} as a divergence candidate",
                references=(handle,),
            )
        return resolved

    def resolve_hypothesis(self, handle: str) -> HypothesisId:
        """Resolve a hypothesis handle, or reject visibly."""
        resolved = self.hypotheses.get(HypothesisHandle(handle))
        if resolved is None:
            raise GovernedRejection(
                GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE,
                f"hypothesis handle {handle!r} was not supplied in request "
                f"{self.request_id!r}",
                references=(handle,),
            )
        return resolved

    def resolve_participant(self, label: str) -> ParticipantId:
        """Resolve a participant label (§2 C).

        A label that was not supplied fails here, which is what stops the model
        minting a participant and silently re-attributing a commitment. Reported
        under ``INVALID_APPRAISAL_RESPONSE`` because neither evidence- nor
        hypothesis-reference outcome fits the referent (§4, F-7 case (c)); the
        caller supplies the boundary discriminator.
        """
        resolved = self.participants.get(ParticipantLabel(label))
        if resolved is None:
            raise GovernedRejection(
                GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
                f"participant label {label!r} was not supplied in request "
                f"{self.request_id!r}",
                boundary=_APPRAISAL_BOUNDARY,
                references=(label,),
            )
        return resolved

    def classify_unknown_evidence_handle(self, handle: str) -> str:
        """Why an evidence handle failed: ``cross-request`` or ``never-issued``.

        TD-13d requires these to be distinguishable, and TD-19 compares this
        classification rather than the literal handle string (N-4).
        """
        return (
            "cross-request"
            if _request_id_of(handle) not in (None, self.request_id)
            else "never-issued"
        )


# Imported late to keep the public import list in this module focused.
from sanuvia.domain.errors import ModelBoundary as _MB  # noqa: E402

_APPRAISAL_BOUNDARY = _MB.APPRAISAL

_SEP = "::"


def _request_id_of(handle: str) -> str | None:
    """The request id embedded in a handle, if it is well-formed."""
    return handle.split(_SEP, 1)[0] if _SEP in handle else None


def _mint(request_id: str, prefix: str, n: int) -> str:
    """A request-scoped handle. Carrying the request id is what makes a handle
    from another request fail resolution rather than alias silently (§2 B)."""
    return f"{request_id}{_SEP}{prefix}{n}"


def standing_view(
    standing: EvidenceStanding, labels: Mapping[ParticipantId, ParticipantLabel]
) -> EvidenceStandingView:
    """Project standing for the model, replacing ids with request-scoped labels."""
    return EvidenceStandingView(
        role=standing.role,
        source_kind=standing.source_kind,
        subject_kind=standing.subject_kind,
        source=labels.get(standing.source_id) if standing.source_id else None,
        subject=labels.get(standing.subject_id) if standing.subject_id else None,
    )


def build_divergence_candidates(
    *,
    observation: EvidenceRecord,
    admitted: Sequence[EvidenceRecord],
    existing_pairs: frozenset[tuple[EvidenceRecordId, EvidenceRecordId]] = frozenset(),
) -> tuple[EvidenceRecord, ...]:
    """The closed divergence-candidate set for one observation (§2 J.1).

    ``admitted`` is supplied in **membership order** — committed records in
    admission sequence, then this interaction's own batch by evidence batch index
    then response order (rule 9). Membership order is deliberately *not*
    canonical-identifier order: all of an interaction's ``evidence-N`` ids are
    minted together before any appraisal call, so identifier allocation carries
    no chronological meaning within an interaction.

    Rules applied, in order:

    1. scope — caller supplies only same ``(space_id, subject_id)`` records;
    2. the observation must itself be a participant account;
    3. each candidate must be a participant account;
    4. same ``standing.subject_id``;
    5. different ``standing.source_id``;
    6. ``DYAD`` and ``THIRD_PARTY`` subject kinds excluded;
    6b. an already-recorded ``DIVERGES_WITH`` pair is excluded before disclosure;
    7. same shared reasoning space (caller enforces ``SpaceKind.SHARED``);
    8. at most the eight most recent, by membership order.

    Returns records in **presentation order** (rule 10): ascending canonical
    ``EvidenceRecordId``, which affects only reproducibility of the request.
    """
    from sanuvia.domain import EvidenceSubjectKind

    obs_standing = observation.standing
    # Rule 2: if the record under appraisal is not a participant account, the
    # candidate set is empty and no divergence can be proposed for it.
    if obs_standing is None or not obs_standing.is_participant_account:
        return ()
    if obs_standing.subject_kind in (
        EvidenceSubjectKind.DYAD,
        EvidenceSubjectKind.THIRD_PARTY,
    ):
        return ()

    eligible: list[EvidenceRecord] = []
    for rec in admitted:
        if rec.id == observation.id:
            continue
        st = rec.standing
        if st is None or not st.is_participant_account:  # rules 3
            continue
        if st.subject_kind in (  # rule 6
            EvidenceSubjectKind.DYAD,
            EvidenceSubjectKind.THIRD_PARTY,
        ):
            continue
        if st.subject_id != obs_standing.subject_id:  # rule 4
            continue
        if st.source_id == obs_standing.source_id:  # rule 5
            continue
        pair = tuple(sorted((str(observation.id), str(rec.id))))
        if pair in existing_pairs:  # rule 6b (Q4)
            continue
        eligible.append(rec)

    # Rule 8: the eight most recent by membership order.
    bounded = eligible[-MAX_DIVERGENCE_CANDIDATES:]
    # Rule 10: presentation order.
    return tuple(sorted(bounded, key=lambda r: str(r.id)))


def build_table(
    *,
    request_id: str,
    observation: EvidenceRecord,
    active_hypotheses: Sequence[Hypothesis],
    candidates: Sequence[EvidenceRecord],
    participants: Sequence[ParticipantId],
) -> HandleTable:
    """Build the authoritative handle table for one appraisal call (§2 B)."""
    labels = {
        pid: ParticipantLabel(_mint(request_id, "P", i + 1))
        for i, pid in enumerate(sorted(set(participants)))
    }
    return HandleTable(
        request_id=request_id,
        observation=EvidenceHandle(_mint(request_id, "E", 0)),
        observation_id=observation.id,
        divergence_candidates={
            EvidenceHandle(_mint(request_id, "E", i + 1)): rec.id
            for i, rec in enumerate(candidates)
        },
        hypotheses={
            HypothesisHandle(_mint(request_id, "H", i + 1)): h.hypothesis_id
            for i, h in enumerate(active_hypotheses)
        },
        participants={label: pid for pid, label in labels.items()},
    )


def build_request_views(
    *,
    table: HandleTable,
    observation: EvidenceRecord,
    active_hypotheses: Sequence[Hypothesis],
    candidates: Sequence[EvidenceRecord],
    signatures: Mapping[HypothesisId, CommitmentSignatureView],
) -> tuple[ObservationView, tuple[HypothesisView, ...], tuple[EvidenceCandidateView, ...]]:
    """Project the request's model-facing views (§2 C).

    Nothing here carries a canonical ``EvidenceRecordId``, a durable
    ``HypothesisId`` or a ``ParticipantId`` — TD-V1 asserts exactly that.
    """
    inverse = {pid: label for label, pid in table.participants.items()}

    obs_standing = observation.standing
    obs_view = ObservationView(
        handle=table.observation,
        content=observation.content,
        standing=standing_view(obs_standing, inverse) if obs_standing else None,  # type: ignore[arg-type]
    )

    by_id = {h.hypothesis_id: h for h in active_hypotheses}
    hyp_views: list[HypothesisView] = []
    for handle, hid in table.hypotheses.items():
        h = by_id.get(hid)
        sig = signatures.get(hid)
        if h is None or sig is None:
            continue
        hyp_views.append(
            HypothesisView(handle=handle, statement=h.statement, signature=sig)
        )

    by_eid = {r.id: r for r in candidates}
    cand_views: list[EvidenceCandidateView] = []
    for handle, eid in table.divergence_candidates.items():
        rec = by_eid.get(eid)
        if rec is None or rec.standing is None:
            continue
        cand_views.append(
            EvidenceCandidateView(
                handle=handle,
                content=rec.content,
                standing=standing_view(rec.standing, inverse),
            )
        )
    return obs_view, tuple(hyp_views), tuple(cand_views)
