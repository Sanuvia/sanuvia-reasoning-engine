"""Fixture-authored identity resolver — a TEST DOUBLE, never a real resolver.

================================ TEST DOUBLE =================================
Identity decisions returned by this component are **authored by the fixture**,
exactly as ``ScriptedAppraiser`` returns the fixture's authored appraisal. It
is not the R1 model-assisted resolver, it is not a substitute for one, and it
must never be wired into a real-model path or any Run 003 configuration.
==============================================================================

Why it exists
-------------

``attribution`` is a **voice** label (§2 H), so every reading one voice holds
about one subject shares a single retrieval bound. Under §2 G resolution order
(Reading A, confirmed), a candidate that is not an exact match of an existing
lineage under that bound is a *plausible* candidate and goes to resolution-order
case 4 -- the ``IdentityResolver`` port. With no resolver configured it parks.

That is the correct deterministic-arm behaviour and it is what the real
External path does. But the Scripted fixtures, the review dataset and the exit
test all author scenarios in which several distinct commitments coexist for one
subject, and they express that distinctness by giving each one its own authored
``hypothesis_id``. Without a resolver those scenarios cannot be expressed at
all: the second commitment parks and every later reference to it fails.

The design's own test matrix anticipates this. TD-06, TD-08 and TD-13b specify
running "with the ``IdentityResolver`` injected or stubbed so the outcome is
controlled". This is that stub.

What it does NOT do
-------------------

It performs **no semantic matching**. It does not compare statements, measure
similarity, inspect ``attribution``, parse identifiers for meaning, or apply
any heuristic. It looks up a decision the fixture stated and returns it. A
candidate whose reference the fixture never authored gets
``AMBIGUOUS_REVIEW_REQUIRED`` -- the same park the unconfigured arm produces --
because there is no authored decision to return.

Recording decisions
-------------------

Every decision is recorded in ``decisions_made``. Harnesses derive their
authored-id -> durable-id mapping from those records, **not** by parsing
``attribution``, which no longer carries identity (B-1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from sanuvia.application.ports.reasoning import Appraisal, CandidateProposal
from sanuvia.domain import (
    EvidenceRecordId,
    HypothesisId,
    IdentityDecision,
    IdentityOutcome,
)

#: Marks every decision this double produces, so a parked or committed lineage
#: traced back to it is identifiable as fixture-authored rather than resolved.
FIXTURE_RESOLVER_ID = "scripted-fixture-authored-identity"


@dataclass(frozen=True, slots=True)
class AuthoredIdentityDecision:
    """One identity decision stated by a fixture."""

    #: The response-local reference the fixture authored for this commitment.
    local_ref: str
    outcome: IdentityOutcome
    rationale: str


class ScriptedIdentityResolver:
    """Returns the fixture's authored identity decision. Implements
    ``IdentityResolver`` structurally.

    Construct with the set of references the fixture authored as distinct
    commitments. Anything outside that set parks.
    """

    resolver_id: str = FIXTURE_RESOLVER_ID

    def __init__(self, authored_distinct: Sequence[str] | None = None) -> None:
        #: References the fixture declared to be distinct commitments. A
        #: fixture states distinctness by authoring a separate hypothesis id;
        #: this records that statement, it does not infer it.
        self._authored_distinct: set[str] = set(authored_distinct or ())
        #: Every decision returned, in order, for harness mapping and audit.
        self.decisions_made: list[AuthoredIdentityDecision] = []

    def declare_distinct(self, local_ref: str) -> None:
        """Record that the fixture authors ``local_ref`` as its own commitment."""
        self._authored_distinct.add(str(local_ref))

    def resolve(
        self,
        candidate: CandidateProposal,
        plausible: Sequence[tuple[HypothesisId, str]],
    ) -> IdentityDecision:
        """Return the authored decision for this candidate.

        ``plausible`` is accepted because the port requires it and because the
        decision is recorded against it for audit. It is **not read** to make
        the decision: nothing here compares the candidate to the plausible
        lineages, which is what keeps this a double rather than a resolver.
        """
        ref = str(candidate.local_ref)
        matches = tuple(hid for hid, _ in plausible)

        if ref in self._authored_distinct:
            decision = IdentityDecision(
                outcome=IdentityOutcome.DISTINCT_NEW,
                candidate_local_ref=candidate.local_ref,
                plausible_matches=matches,
                rationale=(
                    "fixture-authored: this reference is declared a distinct "
                    "commitment (no comparison performed)"
                ),
                resolver_id=self.resolver_id,
            )
        else:
            decision = IdentityDecision(
                outcome=IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED,
                candidate_local_ref=candidate.local_ref,
                plausible_matches=matches,
                rationale=(
                    "fixture-authored: no authored identity decision for this "
                    "reference, so it parks (no comparison performed)"
                ),
                resolver_id=self.resolver_id,
            )

        self.decisions_made.append(
            AuthoredIdentityDecision(
                local_ref=ref, outcome=decision.outcome,
                rationale=decision.rationale or "",
            )
        )
        return decision


def resolver_for_script(
    script: Mapping[EvidenceRecordId, Appraisal],
) -> ScriptedIdentityResolver:
    """Build a resolver from a ``ScriptedAppraiser`` script.

    Every authored ``hypothesis_id`` the script proposes is a commitment the
    fixture declared distinct. Reading them here is reading the fixture's own
    authored identity statements -- it is not inference from the ids.
    """
    refs: list[str] = []
    for appraisal in script.values():
        for proposal in appraisal.proposals:
            refs.append(str(proposal.hypothesis_id))
    return ScriptedIdentityResolver(refs)
