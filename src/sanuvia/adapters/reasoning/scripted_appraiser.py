"""Deterministic scripted appraiser (Phase 0 test double, v1.5.4 port).

``ScriptedAppraiser`` does **not generate** candidate hypotheses. It performs no
language understanding and no validation: it returns a pre-authored appraisal and
translates it into handle space. Every governed control lives after the call
site, in ``src/sanuvia``, which is why Scripted and External share one integrity
boundary structurally rather than by duplication (Technical Design v1.5.4 §1.3).

Fixtures are **not** re-authored. Scripts stay keyed by canonical
``EvidenceRecordId`` and authored in canonical terms; this adapter does the
translation.

----------------------------------------------------------------------------
FIXTURE SIGNATURE MIGRATION -- explicit, not a hidden default
----------------------------------------------------------------------------

v1.5.4 §2 C requires every ``CandidateProposal`` to carry a
``CommitmentSignature``. The authored ``ProposedHypothesis`` predates that type
and carries none, so four fields have to come from somewhere. Design §1.3 and R3
assert fixtures need no re-authoring; that holds for handle translation but was
not worked through for the signature.

What is **derived from authored semantics** (no decision taken):

* **existing-hypothesis references** (``supports`` / ``contradicts``) -- resolved
  by matching the authored statement against ``HypothesisView.statement``. The
  catalogue is built from the script's own proposals, so no fixture supplies it.

**Lineage distinctness is no longer derived here (B-1 corrected).** It used to
be carried in ``attribution`` as the authored ``hypothesis_id``, which let a
fixture label decide durable identity. ``attribution`` is now the governed
voice label, so every appraiser-proposed reading for one subject shares one
retrieval bound, and distinctness is decided by adjudication under §2 G --
exact match attaches, non-exact parks without a resolver (Reading A). Fixtures
that need authored identity decisions supply them through the injected
``ScriptedIdentityResolver`` test double, which authors decisions explicitly
rather than inferring them from a label.

What is **assumed** (a semantic decision the fixtures cannot answer). These are
recorded here and in the implementation report rather than buried:

* **A1 -- ``subject``**: the modelled ``subject_id``, reused as the commitment
  subject. Sound for these single-participant fixtures; §2 E is explicit that the
  modelling subject and the commitment subject are different concepts in general.
* **A2 -- ``claim_class``**: ``INTERPRETATION``. The authored type says a
  proposal is "a candidate explanation", which is an interpretation, but the
  fixtures never state a class.
* **A3 -- ``stance``**: ``OPEN``. Chosen because ``OPEN`` never inverts and is
  never inverted (N-8), so a migrated fixture can never trip the check 10
  structural-contradiction rule by accident. A migrated signature must not
  manufacture a contradiction the fixture did not author.

``MIGRATION_ATTRIBUTION_PREFIX`` makes a migrated signature identifiable in any
``IdentityDecision`` it produces, so a migrated lineage key is never mistaken for
an authored one.

An authored signature always wins: ``ProposedHypothesis`` gains an optional
``signature`` field, and when a fixture supplies one this migration does not run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast

from sanuvia.application.ports.reasoning import (
    Appraisal,
    AppraisalRequest,
    AppraisalResponse,
    Bearing,
    BearingKind,
    CandidateProposal,
    CommitmentSignatureView,
    HypothesisHandle,
    ParticipantLabel,
    ProposedHypothesis,
)
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    EvidenceRecordId,
    HypothesisId,
    Stance,
)

#: Marks a signature produced by fixture migration rather than authored.
MIGRATION_ATTRIBUTION_PREFIX = "scripted-fixture-migration"

#: A2 / A3 -- see the module docstring. Named constants, not inline literals, so
#: they are greppable and so changing one is a visible edit.
MIGRATED_CLAIM_CLASS = ClaimClass.INTERPRETATION
MIGRATED_STANCE = Stance.OPEN


def migrated_attribution(authored_hypothesis_id: HypothesisId) -> str:
    """The governed voice label for an appraiser-proposed reading (§2 H).

    **B-1 corrected.** This previously returned
    ``f"{MIGRATION_ATTRIBUTION_PREFIX}:{authored_hypothesis_id}"``, putting a
    fixture-authored label into the immutable half of the lineage key. That let
    a response-local reference decide durable identity: the same statement
    proposed under two authored ids founded two lineages.

    ``attribution`` is a **voice** -- "participant account | Sanuvia working
    reading" (§2 H) -- not a per-proposal identifier. A proposal returned by an
    appraiser is the appraiser's working interpretation by construction, so it
    is always the working reading. ``participant account`` is reserved for a
    commitment separately attributed to the participant and is never chosen
    here.

    The argument is retained so call sites stay explicit about which proposal
    is being signed, and so the removal is visible in the diff rather than
    silent; it no longer affects the result.
    """
    return VOICE_SANUVIA_WORKING_READING


class ScriptedAppraiser:
    """Returns pre-authored appraisals by evidence id, translated to handle space.

    Unknown evidence yields an empty appraisal: the evidence is recorded but
    drives no hypothesis change. That is the authored Phase 0 behaviour and is
    preserved.
    """

    def __init__(
        self,
        script: dict[EvidenceRecordId, Appraisal] | None = None,
        *,
        catalogue: Mapping[HypothesisId, str] | None = None,
    ) -> None:
        self._script: dict[EvidenceRecordId, Appraisal] = dict(script or {})
        #: authored hypothesis id -> authored statement. Built from the script's
        #: own proposals so no fixture has to supply it; an explicit catalogue
        #: may be passed for hypotheses the script references but never proposes.
        self._catalogue: dict[HypothesisId, str] = dict(catalogue or {})
        for appraisal in self._script.values():
            for proposal in appraisal.proposals:
                self._catalogue.setdefault(proposal.hypothesis_id, proposal.statement)

    def set(self, evidence_id: EvidenceRecordId, appraisal: Appraisal) -> None:
        self._script[evidence_id] = appraisal
        for proposal in appraisal.proposals:
            self._catalogue.setdefault(proposal.hypothesis_id, proposal.statement)

    # -- the v1.5.4 port ----------------------------------------------------

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        """Translate the authored appraisal for this observation into handle space.

        Performs **no** validation. An authored reference that cannot be resolved
        is emitted as an unresolvable handle, never dropped and never raised:
        dropping would silently empty a governed failure, and raising would move
        the rejection into the adapter, which has no authority to decide it
        (§1.3, F-11).
        """
        if request.observation_id is None:
            return AppraisalResponse()
        authored = self._script.get(request.observation_id)
        if authored is None:
            return AppraisalResponse()

        by_statement = {view.statement: view.handle for view in request.existing}

        bearings: list[Bearing] = []
        for hid in authored.supports:
            bearings.append(Bearing(self._handle_for(hid, by_statement, request),
                                    BearingKind.SUPPORTS))
        for hid in authored.contradicts:
            bearings.append(Bearing(self._handle_for(hid, by_statement, request),
                                    BearingKind.CONTRADICTS))

        proposals = tuple(
            CandidateProposal(
                local_ref=str(p.hypothesis_id),
                statement=p.statement,
                signature=self._signature_for(p, request),
                # Content only (errata E-1): carried so an authored trajectory
                # survives the port, never so it can force a prediction.
                predicted_trajectory=p.predicted_trajectory,
            )
            for p in authored.proposals
        )
        # raw_response is None on the Scripted path by construction; TD-19
        # excludes it from the cross-path equality for exactly that reason.
        return AppraisalResponse(
            proposals=proposals, bearings=tuple(bearings), raw_response=None
        )

    # -- translation --------------------------------------------------------

    def _handle_for(
        self,
        authored_id: HypothesisId,
        by_statement: Mapping[str, HypothesisHandle],
        request: AppraisalRequest,
    ) -> HypothesisHandle:
        """Resolve an authored hypothesis id to a request-scoped handle.

        Matched on the authored statement, because durable ids are engine-issued
        and an authored id is not one. An unresolvable reference becomes an
        unresolvable handle carrying this request's id, so it fails authoritative
        resolution at check 1 exactly as an External-path invented handle does.
        """
        statement = self._catalogue.get(authored_id)
        if statement is not None and statement in by_statement:
            return by_statement[statement]
        return HypothesisHandle(f"{request.request_id}::unresolved:{authored_id}")

    def _signature_for(
        self, proposal: ProposedHypothesis, request: AppraisalRequest
    ) -> CommitmentSignatureView:
        """An authored signature if the fixture supplies one; else the migration."""
        authored: CommitmentSignatureView | None = proposal.signature
        if authored is not None:
            return authored
        label = next(iter(request.participants), None) if request.participants else None
        return CommitmentSignatureView(
            # A1: the modelled subject reused as the commitment subject.
            # ``build_table`` always supplies at least one participant, so
            # ``label`` is never None here; the fallback is defensive only.
            subject=cast(
                "ParticipantLabel",
                label if label is not None else str(request.subject_id),
            ),
            # Derived: authored lineage distinctness.
            attribution=migrated_attribution(proposal.hypothesis_id),
            claim_class=MIGRATED_CLAIM_CLASS,  # A2
            stance=MIGRATED_STANCE,  # A3
        )
