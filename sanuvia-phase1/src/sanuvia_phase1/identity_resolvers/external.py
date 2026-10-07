"""ExternalIdentityResolver — the bounded R1 model-assisted resolver (opt-in).

Technical Design v1.5.4 §2 G, resolution-order case 4 only.

What this is
------------

A **bounded adjudicator**, not a second reasoning engine and not the owner of
durable identity. It is consulted for one thing: a candidate that is plausible
under the signature bound but is **not** an exact normalised match, which the
deterministic arm cannot safely decide. Cases 1-3 never reach it.

What crosses the boundary
-------------------------

Outbound, and nothing else (§2 G bounded inputs): the candidate's statement and
signature, and the plausible existing candidates the signature bound admits.
Not the evidence store, not the hypothesis store, not unrelated state.

**No durable identifier is sent.** Each plausible candidate is presented under
a resolution-scoped label (``C1``, ``C2``, ...) minted here and mapped back
after the reply, exactly as the appraisal boundary uses request-scoped handles.
A model that cannot see a ``HypothesisId`` cannot assign one.

Inbound: a structured outcome, the label of the matched candidate where the
outcome is a merge, a rationale and a confidence. The raw response is preserved
verbatim, and ``resolver_id`` plus the prompt/schema version travel with the
decision as provenance.

What it does NOT do
-------------------

* **No retries.** One call, one answer.
* **No repair, rewriting or normalisation.** A malformed or unusable reply is a
  visible governed failure (F-7 case (d)), raised as
  ``INVALID_APPRAISAL_RESPONSE`` with ``boundary=IDENTITY_RESOLVER`` and
  carrying the exact raw reply plus this resolver's provenance.
* **A closed reference vocabulary.** The reply may name only the refs this
  request offered. An unoffered label is unusable output, never carried
  forward as though it were a durable identifier.
* **No confidence threshold.** ``confidence`` is provenance only (F-8): it is
  recorded and reported, and never changes an outcome.
* **No durable identity.** The engine issues every durable id at step 9, after
  adjudication.

The application validates every answer before it can take effect: that the
outcome is one of the four governed values, that a named lineage was one the
bound admitted, that ``DISTINCT_NEW`` names nothing, that a merge outcome names
something, and that R1a discards an inverted-stance merge (§2 H, C-1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sanuvia.application.ports.reasoning import CandidateProposal
from sanuvia.domain import (
    GovernedOutcome,
    GovernedRejection,
    HypothesisId,
    IdentityDecision,
    IdentityOutcome,
    ModelBoundary,
)

from ..failures import MalformedOutputError
from ..validation import validate_identity_resolution

#: Stable provenance id recorded on every decision this resolver produces.
RESOLVER_ID = "identity.r1.bounded.v1"

#: The versioned prompt and schema this resolver runs under (§2 G provenance).
#: Declared here rather than imported from the registry so the adapter carries
#: its own identity without a circular import; the registry pins the hashes.
PROMPT_VERSION = "identity.r1.bounded.v1"
SCHEMA_VERSION = "schema.identity.v1"

SYSTEM = (
    "You decide whether a CANDIDATE commitment is the same commitment as one of "
    "the EXISTING commitments listed, for an internal reasoning experiment. You "
    "do NOT create identifiers, set support, or decide model state. Respond with "
    "ONLY a JSON object of the form:\n"
    '{"outcome": string, "matched_ref": string|null, "rationale": string, '
    '"confidence": number}\n'
    "outcome is one of: match_existing (the candidate states the same "
    "commitment as the matched one), refine_existing (the candidate clarifies, "
    "qualifies or narrows the matched commitment while the prior statement "
    "remains true of it), distinct_new (a different commitment), "
    "ambiguous_review_required (you cannot safely distinguish). "
    "matched_ref is the ref of the existing commitment for match_existing and "
    "refine_existing, and null otherwise. Use only the refs given. "
    "A change that negates, contradicts or withdraws the prior commitment is a "
    "reversal, not a refinement. If you are unsure, answer "
    "ambiguous_review_required rather than guessing. Do not output any prose "
    "outside the JSON object."
)

INSTRUCTION = "Return the identity resolution JSON now."


@dataclass(frozen=True, slots=True)
class CandidateRef:
    """One plausible existing commitment, under a resolution-scoped label."""

    ref: str
    statement: str


@dataclass(frozen=True, slots=True)
class IdentityResolutionPrompt:
    """The bounded input to one resolution. Carries no durable identifier."""

    system: str
    candidate_statement: str
    candidate_subject: str
    candidate_claim_class: str
    candidate_stance: str
    candidate_temporal_scope: str | None
    existing: tuple[CandidateRef, ...]
    instruction: str


IdentityResolutionClient = Callable[[IdentityResolutionPrompt], str]


class ExternalIdentityResolver:
    """Adapts a caller-supplied client into the ``IdentityResolver`` port.

    Real runs are **not** guaranteed deterministic.
    """

    resolver_id: str = RESOLVER_ID

    def __init__(self, client: IdentityResolutionClient) -> None:
        self._client = client

    def resolve(
        self,
        candidate: CandidateProposal,
        plausible: Sequence[tuple[HypothesisId, str]],
    ) -> IdentityDecision:
        # Resolution-scoped labels, minted here. The durable ids stay on this
        # side of the boundary; only ``C1``, ``C2``, ... are sent.
        by_ref: dict[str, HypothesisId] = {
            f"C{i}": hid for i, (hid, _) in enumerate(plausible, start=1)
        }
        signature = candidate.signature
        prompt = IdentityResolutionPrompt(
            system=SYSTEM,
            candidate_statement=candidate.statement,
            candidate_subject=str(signature.subject),
            candidate_claim_class=signature.claim_class.value,
            candidate_stance=signature.stance.value,
            candidate_temporal_scope=signature.temporal_scope,
            existing=tuple(
                CandidateRef(ref=ref, statement=statement)
                for ref, (_, statement) in zip(by_ref, plausible)
            ),
            instruction=INSTRUCTION,
        )

        raw = self._client(prompt)
        try:
            validated = validate_identity_resolution(raw)
        except MalformedOutputError as exc:
            # A malformed reply is a GOVERNED failure at this boundary, not a
            # transport error that escapes to the caller. Raising it as
            # MalformedOutputError meant rollback happened but no governed
            # rejected-plan record was ever produced, so the audit lost both
            # the outcome and the model's words.
            #
            # Converted, never repaired: no retry, no normalisation, no
            # fallback outcome. The exact raw reply and the resolver
            # provenance travel with it.
            raise self._governed_failure(
                candidate, str(exc), raw
            ) from None

        # CLOSED REFERENCE VOCABULARY.
        #
        # The request offered C1, C2, ... and the model may name only those.
        # This previously fell back to the model's own string when the label
        # was unknown, so a reply naming "hyp-1" was carried forward AS a
        # durable HypothesisId -- and was accepted whenever a lineage happened
        # to be called that. A reply naming "hyp-9" was refused only because no
        # such lineage existed, which is a membership accident, not a rule.
        #
        # The application must never infer that a model-supplied string is a
        # durable identifier. An unoffered label is unusable output.
        matched: HypothesisId | None = None
        if validated.matched_ref is not None:
            if validated.matched_ref not in by_ref:
                raise self._governed_failure(
                    candidate,
                    f"matched_ref {validated.matched_ref!r} was not offered for "
                    f"this resolution; the offered references are "
                    f"{sorted(by_ref)}",
                    raw,
                )
            matched = by_ref[validated.matched_ref]

        return IdentityDecision(
            outcome=validated.outcome,
            candidate_local_ref=candidate.local_ref,
            matched_hypothesis_id=matched,
            plausible_matches=tuple(by_ref.values()),
            rationale=validated.rationale,
            confidence=validated.confidence,
            resolver_id=self.resolver_id,
            resolver_raw_response=raw,
        )


    def _governed_failure(
        self, candidate: CandidateProposal, detail: str, raw: str
    ) -> GovernedRejection:
        """F-7 case (d): an unusable identity-resolver response.

        Carries the complete provenance the audit needs to attribute the
        failure: the exact raw reply, which resolver produced it, and the
        versioned prompt and schema it ran under.
        """
        return GovernedRejection(
            GovernedOutcome.INVALID_APPRAISAL_RESPONSE,
            f"identity resolver response unusable for candidate "
            f"{candidate.local_ref!r}: {detail}",
            boundary=ModelBoundary.IDENTITY_RESOLVER,
            references=(candidate.local_ref,),
            raw_response=raw,
            provenance=(
                ("resolver_id", self.resolver_id),
                ("prompt_version", PROMPT_VERSION),
                ("schema_version", SCHEMA_VERSION),
            ),
        )


def identity_resolver_from_env():
    """Placeholder factory — intentionally refuses to auto-select a provider."""
    raise RuntimeError(
        "No identity-resolution provider is configured. R1 is opt-in: construct "
        "ExternalIdentityResolver(client=...) with an approved provider/model "
        "and prompt/schema."
    )
