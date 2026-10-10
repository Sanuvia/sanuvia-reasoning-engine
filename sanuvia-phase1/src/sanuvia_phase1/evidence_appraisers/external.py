"""ExternalEvidenceAppraiser — the real evidence-appraisal seam (opt-in).

Implements the FROZEN Phase 0 ``EvidenceAppraiser`` protocol by delegating to a
caller-injected ``client``. Provider-neutral: no vendor SDK, no model chosen, no
key read, nothing runs in the default test/CI path.

Boundary (Programme v1.4 Part 2; frozen ``EvidenceAppraiser`` docstring): the
appraiser is the *language-understanding* step. It may only:

* PROPOSE candidate hypotheses (id + statement + initial support), and
* say which EXISTING hypotheses the observation SUPPORTS or CONTRADICTS.

It does **not** revise the model, set uncertainty, choose inquiries, or persist
anything — those remain the frozen Phase 0 engine's authority. Hypothesis
*identity* is spec-unresolved, so the appraiser supplies the ``hypothesis_id``
(exactly as the frozen ``ScriptedAppraiser`` does).

Governance (unresolved — requires governance approval): the provider/model and the exact
appraisal prompt/response schema are NOT decided here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sanuvia.application.ports.reasoning import (
    AppraisalRequest as PortAppraisalRequest,
    AppraisalResponse,
    Bearing,
    BearingKind,
    CandidateProposal,
    CommitmentSignatureView,
    HypothesisHandle,
    Appraisal,
    EvidenceAppraiser,
    ProposedHypothesis,
)
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    Stance,
    EvidenceRecord,
    EvidenceRecordId,
    Hypothesis,
    HypothesisId,
    SubjectId,
)

from ..validation import validate_appraisal


@dataclass(frozen=True, slots=True)
class HypothesisPromptView:
    """One active hypothesis as the model sees it, signature included.

    ``handle`` is request-scoped and ``subject`` is a request-scoped
    participant label: no durable ``HypothesisId`` or ``ParticipantId`` crosses
    this boundary (TD-V1).
    """

    handle: str
    statement: str
    subject: str
    attribution: str
    claim_class: str
    stance: str
    temporal_scope: str | None = None


@dataclass(frozen=True, slots=True)
class AppraisalPrompt:
    """A prompt for a real appraisal model — one observation vs the current
    hypotheses.

    Renamed from ``AppraisalRequest`` in Technical Design v1.5.4 §2 C: that name
    now belongs to the **port**, and this stays what it always was — adapter-
    internal prompt assembly.
    """

    system: str
    evidence_observation: str
    #: Each active hypothesis as the model sees it. Carries the full governed
    #: signature (§2 C / §2 H) alongside the handle and statement, so the model
    #: can see what each existing commitment commits to -- whose it is, in
    #: which voice, at which claim class, stance and temporal scope -- rather
    #: than a bare statement. Nothing here is a durable identifier: ``handle``
    #: is request-scoped and ``subject`` is a request-scoped participant label.
    active_hypotheses: tuple["HypothesisPromptView", ...]
    #: The request-scoped participant labels a proposal's signature subject may
    #: name. Without these the model has no way to know which labels are legal,
    #: and complete-plan check 1 would reject every proposal it made.
    participants: tuple[str, ...]
    instruction: str


AppraisalClient = Callable[[AppraisalPrompt], str]

SYSTEM = (
    "You APPRAISE a single observation against the current hypotheses for an "
    "internal reasoning experiment. You do NOT decide model state, uncertainty, or "
    "predictions — you only (a) PROPOSE candidate hypotheses and (b) say which "
    "EXISTING hypotheses the observation supports or contradicts. Respond with ONLY "
    "a JSON object of the form:\n"
    '{"supports": [handle], "contradicts": [handle], '
    '"proposals": [{"local_ref": string, "statement": string, '
    '"signature": {"subject": participant_label, "claim_class": string, '
    '"stance": string, "temporal_scope": string|null}}]}\n'
    "Reference existing hypotheses by the handle given for this request, exactly "
    "as given. For a new proposal supply a local_ref that is unique within this "
    "response; it labels the proposal in this reply only and is not an identifier. "
    "Every proposal must carry a signature saying what it commits to: subject is "
    "one of the participant labels given for this request; claim_class is one of "
    "intention, behaviour_pattern, interpretation, relational_dynamic; stance is "
    "one of affirms, negates, open; temporal_scope is a short phrase or null. "
    "Do not assign hypothesis ids, support values, evidence references, or the "
    "attribution — those are not yours to decide. Do not output any prose outside "
    "the JSON object."
)

INSTRUCTION = "Return the appraisal JSON now."


class ExternalEvidenceAppraiser:
    """Adapts a caller-supplied appraisal client into the ``EvidenceAppraiser`` port.

    Real runs are **not** guaranteed deterministic."""

    def __init__(self, client: AppraisalClient) -> None:
        self._client = client

    def appraise(self, request: PortAppraisalRequest) -> AppraisalResponse:
        """Technical Design v1.5.4 §2 C port.

        The adapter renders handles, calls the model, preserves the raw response
        and translates the reply into handle space. It performs no validation
        that matters: every governed control runs after this returns, in
        ``src/sanuvia``. **No retries, no repair, no normalisation** -- a
        malformed reply raises ``MalformedOutputError`` and is never silently
        skipped or defaulted.

        The prompt shape is unchanged -- one observation against the current
        hypotheses, as Run 002 executed. The response **schema** is migrated to
        v1.5.4 §2 C under the authorized schema migration: references are
        handles, a proposal is ``local_ref`` plus ``statement``, and the three
        retired model-facing fields are gone. This is a schema migration, not a
        prompt redesign; the prompt id is bumped to v2 rather than edited in
        place, so Run 002's ``...v1`` reference keeps meaning what it meant.
        """
        prompt = AppraisalPrompt(
            system=SYSTEM,
            evidence_observation=request.observation.content,
            # Handles, never durable ids: this is what closes locked §3.1's
            # prohibition on exposing canonical identity to the model.
            active_hypotheses=tuple(
                HypothesisPromptView(
                    handle=str(view.handle),
                    statement=view.statement,
                    subject=str(view.signature.subject),
                    attribution=view.signature.attribution,
                    claim_class=view.signature.claim_class.value,
                    stance=view.signature.stance.value,
                    temporal_scope=view.signature.temporal_scope,
                )
                for view in request.existing
            ),
            participants=tuple(str(p) for p in request.participants),
            instruction=INSTRUCTION,
        )
        raw = self._client(prompt)
        validated = validate_appraisal(raw)

        bearings = tuple(
            Bearing(HypothesisHandle(x), BearingKind.SUPPORTS)
            for x in validated.supports
        ) + tuple(
            Bearing(HypothesisHandle(x), BearingKind.CONTRADICTS)
            for x in validated.contradicts
        )
        proposals = tuple(
            CandidateProposal(
                local_ref=p.local_ref,
                statement=p.statement,
                signature=CommitmentSignatureView(
                    # The model's stated subject, as a request-scoped label.
                    # It is NOT trusted blindly: complete-plan check 1 resolves
                    # it through this request's participant table, so a label
                    # the model invented fails there rather than here.
                    subject=p.signature.subject,
                    # B-1 corrected. attribution is the governed VOICE label
                    # (§2 H), not a per-proposal identifier. A proposal
                    # returned by an appraiser is the appraiser's working
                    # interpretation by construction, so it is always the
                    # working reading; "participant account" is reserved for a
                    # commitment separately attributed to the participant and
                    # is never chosen here. The model does not supply this
                    # field: letting it choose the voice would let it decide
                    # whether its own interpretation is the participant's
                    # commitment.
                    attribution=VOICE_SANUVIA_WORKING_READING,
                    claim_class=p.signature.claim_class,
                    stance=p.signature.stance,
                    temporal_scope=p.signature.temporal_scope,
                ),
            )
            for p in validated.proposals
        )
        return AppraisalResponse(
            proposals=proposals, bearings=bearings, raw_response=raw
        )


def evidence_appraiser_from_env() -> EvidenceAppraiser:
    """Placeholder factory — intentionally refuses to auto-select a provider.

    Real appraisal is opt-in: construct ``ExternalEvidenceAppraiser(client=...)``
    with an approved provider/model and appraisal prompt/schema (governance
    unresolved)."""
    raise RuntimeError(
        "No evidence-appraisal provider is configured. Real appraisal is opt-in: "
        "construct ExternalEvidenceAppraiser(client=...) with an approved "
        "provider/model and prompt/schema (governance unresolved)."
    )
