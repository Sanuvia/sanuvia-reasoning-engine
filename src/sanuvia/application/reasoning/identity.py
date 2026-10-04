"""Semantic identity adjudication.

Technical Design v1.5.4 §2 G, with the R1a refinement boundary from §2 H.

Scope note (authorized sequencing adjustment, 2026-09-30). This module implements
the **deterministic arm only** — resolution-order cases 1 to 3, plus the stated
configuration rule for case 4 when no resolver is configured. The **R1
model-assisted resolver remains Slice 2 and is not implemented here**. The
deterministic arm is not a replacement for it: with no resolver configured a
plausible-but-inexact candidate parks as ``AMBIGUOUS_REVIEW_REQUIRED`` rather
than committing on an unmade judgement, exactly as §2 G specifies.

Consequently ``REFINE_EXISTING`` is **not reachable** on this path. It is
produced only by the resolver, so it arrives with Slice 2.

The model proposes candidate language; the engine issues every durable id, and
only after adjudication. Nothing in this module allocates an identifier or writes
to a store: it returns decisions, and ``model_revision`` mints ids for the
``DISTINCT_NEW`` ones at plan construction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sanuvia.application.ports.reasoning import CandidateProposal
from sanuvia.application.reasoning.plan_validation import normalise_statement
from sanuvia.domain import (
    CommitmentSignature,
    HypothesisId,
    IdentityDecision,
    IdentityOutcome,
    ParticipantId,
    Stance,
    StatementVersion,
    inverts,
)

#: A plan-local lineage key: ``(signature subject, attribution)``.
#:
#: The bound admits **many** lineages, not one (M-2). ``subject`` and
#: ``attribution`` are a voice-and-person pair -- "whose commitment is this" --
#: so every distinct commitment one voice holds about one person shares the key.
#: Retrieval therefore returns a *set* of candidates and the adjudicator chooses
#: among them; a mapping that held one lineage per key silently discarded every
#: candidate but the last, which is the defect M-2 names.
#:
#: This is the **immutable retrieval bound** (F-2). ``claim_class`` is
#: deliberately absent: bounding retrieval on a versioned field would mean a
#: candidate proposing the very refinement §2 H calls legitimate failed to
#: retrieve its own lineage and fell through to ``DISTINCT_NEW``, recreating the
#: duplication the split exists to prevent. ``claim_class`` may *rank* retrieved
#: candidates; it may never exclude one.
LineageKey = tuple[str, str]


@runtime_checkable
class IdentityResolver(Protocol):
    """The bounded model-assisted resolver port (R1).

    **Not implemented in this slice.** It is declared here so the deterministic
    arm can state exactly where case 4 would hand off, and so the unconfigured
    behaviour is explicit rather than implicit.

    When Slice 2 wires it, locked §3.3 and §2 G require: invoked only for
    plausible-but-inexact candidates; bounded inputs; structured output; raw
    response preserved; provenance recorded; **no retries**; **no repair,
    rewriting or normalisation loop**.
    """

    resolver_id: str

    def resolve(
        self,
        candidate: CandidateProposal,
        plausible: Sequence[tuple[HypothesisId, str]],
    ) -> IdentityDecision: ...


@dataclass(frozen=True, slots=True)
class LineageView:
    """What the adjudicator needs to know about one retrievable lineage."""

    hypothesis_id: HypothesisId | None
    key: LineageKey
    current_stance: Stance
    #: Every accepted statement version, oldest first. Exact match compares
    #: against **all** of them, not only the current one (F-2), which is what
    #: makes a re-presented earlier statement resolve ``MATCH_EXISTING`` after a
    #: later refinement rather than founding a duplicate.
    versions: tuple[StatementVersion, ...] = ()
    #: True when this lineage was created by an earlier candidate in the same
    #: uncommitted plan and has no durable id yet (F-16).
    in_flight: bool = False
    #: Statement of an in-flight lineage, which has no StatementVersion yet.
    in_flight_statement: str | None = None
    in_flight_signature: CommitmentSignature | None = None


def _signature_matches(
    candidate: CommitmentSignature, version_claim: object, version_stance: Stance,
    version_scope: str | None,
) -> bool:
    """Versioned signature-field equality for the exact-match test."""
    return (
        candidate.claim_class == version_claim
        and candidate.stance == version_stance
        and candidate.temporal_scope == version_scope
    )


class DeterministicAdjudicator:
    """Resolution-order cases 1-3, plus the unconfigured case-4 rule (§2 G).

    Candidates are adjudicated in a **deterministic order** — ascending evidence
    batch index, then response order — so the outcome does not depend on
    iteration accident. The caller supplies them already in that order.
    """

    def __init__(self, resolver: IdentityResolver | None = None) -> None:
        #: Slice 1 wires nothing here. When Slice 2 supplies a resolver, case 4
        #: hands off to it instead of parking.
        self._resolver = resolver

    @property
    def has_resolver(self) -> bool:
        return self._resolver is not None

    def adjudicate(
        self,
        candidate: CandidateProposal,
        signature: CommitmentSignature,
        *,
        committed: Mapping[LineageKey, Sequence[LineageView]],
        in_flight: Mapping[LineageKey, Sequence[LineageView]],
    ) -> IdentityDecision:
        """Adjudicate one candidate against committed state and the in-flight set.

        The scope is the **union** of the two. A rule scoped only to committed
        state cannot see duplicates proposed earlier in the same uncommitted
        plan, which is exactly the Run 002 pattern: five appraisal calls, each
        returning one proposal, three of them inside a single interaction.
        """
        key: LineageKey = (str(signature.subject), signature.attribution)
        normalised = normalise_statement(candidate.statement)

        # Case 2 -- exact normalised match, committed arm first, then in-flight.
        # Every lineage the bound admits is scanned, in retrieval order (M-2):
        # with several commitments under one (subject, attribution), the match
        # may be against any of them, not merely the most recent.
        for source, is_in_flight in ((committed, False), (in_flight, True)):
            for lineage in source.get(key, ()):
                if not self._exact_match(lineage, normalised, signature):
                    continue
                # R1a merge protection. Unreachable under R1a itself -- a
                # lineage can never invert its own stance, because the only way
                # to append a version is REFINE_EXISTING and R1a forbids stance
                # inversion as refinement -- but asserted here so a future
                # change cannot silently merge two opposed commitments into one
                # hypothesis_id.
                if inverts(lineage.current_stance, signature.stance):
                    return self._park(
                        candidate,
                        [lineage],
                        rationale=(
                            "exact statement match, but the candidate stance "
                            "inverts the lineage's current stance; merging would "
                            "put two opposed commitments in one lineage (R1a)"
                        ),
                    )
                return IdentityDecision(
                    outcome=IdentityOutcome.MATCH_EXISTING,
                    candidate_local_ref=candidate.local_ref,
                    matched_hypothesis_id=lineage.hypothesis_id,
                    matched_lineage_key=key,
                    matched_in_flight=is_in_flight,
                    rationale="exact normalised statement and signature match",
                )

        # Case 3 -- no plausible candidate under the signature bound. Every
        # lineage the bound admits is a plausible candidate (§2 G: the resolver
        # receives "only the plausible existing candidates the signature bound
        # admits"), so this is empty only when the bound retrieves nothing.
        plausible: list[LineageView] = [
            lineage
            for src in (committed, in_flight)
            for lineage in src.get(key, ())
        ]
        if not plausible:
            return IdentityDecision(
                outcome=IdentityOutcome.DISTINCT_NEW,
                candidate_local_ref=candidate.local_ref,
                matched_lineage_key=key,
                rationale="no lineage retrievable under (subject, attribution)",
            )

        # Case 4 -- plausible but not exact.
        if self._resolver is None:
            # The stated configuration rule (§2 G): park rather than commit on an
            # unmade judgement. This is NOT a deterministic substitute for the R1
            # resolver; it is the explicit unconfigured behaviour.
            return self._park(
                candidate,
                plausible,
                rationale=(
                    f"{len(plausible)} plausible lineage(s) retrieved under "
                    "(subject, attribution) but no exact match, and no "
                    "IdentityResolver is configured (R1 remains Slice 2)"
                ),
            )
        # The resolver receives EVERY plausible candidate the bound admits
        # (§2 G bounded inputs), not merely the first retrieved.
        return self._resolver.resolve(
            candidate,
            [(lv.hypothesis_id, self._statement_of(lv))
             for lv in plausible if lv.hypothesis_id is not None],
        )

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _exact_match(
        lineage: LineageView, normalised: str, signature: CommitmentSignature
    ) -> bool:
        """Exact normalised match against **every** version of the lineage (F-2)."""
        if lineage.in_flight:
            return (
                lineage.in_flight_statement is not None
                and normalise_statement(lineage.in_flight_statement) == normalised
                and lineage.in_flight_signature is not None
                and _signature_matches(
                    signature,
                    lineage.in_flight_signature.claim_class,
                    lineage.in_flight_signature.stance,
                    lineage.in_flight_signature.temporal_scope,
                )
            )
        return any(
            normalise_statement(v.statement) == normalised
            and _signature_matches(signature, v.claim_class, v.stance, v.temporal_scope)
            for v in lineage.versions
        )

    @staticmethod
    def _statement_of(lineage: LineageView) -> str:
        """The lineage's current statement, for resolver presentation."""
        if lineage.in_flight:
            return lineage.in_flight_statement or ""
        return lineage.versions[-1].statement if lineage.versions else ""

    @staticmethod
    def _park(
        candidate: CandidateProposal,
        plausible: Sequence[LineageView],
        *,
        rationale: str,
    ) -> IdentityDecision:
        """Park the candidate without creating or revising a hypothesis.

        An accepted proposal is never discarded merely because deterministic
        resolution cannot resolve it: it becomes a durable
        ``IdentityAdjudication`` preserving the candidate content, its signature,
        the plausible matches and the decision provenance.
        """
        first = plausible[0]
        return IdentityDecision(
            outcome=IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED,
            candidate_local_ref=candidate.local_ref,
            matched_lineage_key=first.key,
            matched_in_flight=any(lv.in_flight for lv in plausible),
            # EVERY plausible match is preserved on the parked record (M-2).
            # Recording only the first would lose the very ambiguity that
            # caused the park, and the review of a parked candidate needs to
            # see all the lineages it might belong to.
            plausible_matches=tuple(
                lv.hypothesis_id for lv in plausible if lv.hypothesis_id is not None
            ),
            rationale=rationale,
        )


def build_committed_views(
    *,
    lineage_keys: Mapping[LineageKey, HypothesisId],
    current_stance: Mapping[HypothesisId, Stance],
    histories: Mapping[HypothesisId, Sequence[StatementVersion]],
) -> dict[LineageKey, list[LineageView]]:
    """Project committed lineages into the adjudicator's view.

    Keys map to **lists**: one retrieval bound may admit several lineages
    (M-2), and appending rather than assigning is what stops an earlier
    candidate being discarded by a later one sharing the bound.
    """
    views: dict[LineageKey, list[LineageView]] = {}
    for key, hid in lineage_keys.items():
        views.setdefault(key, []).append(
            LineageView(
                hypothesis_id=hid,
                key=key,
                current_stance=current_stance.get(hid, Stance.OPEN),
                versions=tuple(histories.get(hid, ())),
            )
        )
    return views
