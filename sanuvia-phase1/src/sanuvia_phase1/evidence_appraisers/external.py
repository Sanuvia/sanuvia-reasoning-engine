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
class AppraisalPrompt:
    """A prompt for a real appraisal model — one observation vs the current
    hypotheses.

    Renamed from ``AppraisalRequest`` in Technical Design v1.5.4 §2 C: that name
    now belongs to the **port**, and this stays what it always was — adapter-
    internal prompt assembly.
    """

    system: str
    evidence_observation: str
    active_hypotheses: tuple[tuple[str, str], ...]  # (hypothesis_id, statement)
    instruction: str


AppraisalClient = Callable[[AppraisalPrompt], str]

SYSTEM = (
    "You APPRAISE a single observation against the current hypotheses for an "
    "internal reasoning experiment. You do NOT decide model state, uncertainty, or "
    "predictions — you only (a) PROPOSE candidate hypotheses and (b) say which "
    "EXISTING hypotheses the observation supports or contradicts. Respond with ONLY "
    "a JSON object of the form:\n"
    '{"supports": [hypothesis_id], "contradicts": [hypothesis_id], '
    '"proposals": [{"hypothesis_id": string, "statement": string, '
    '"initial_support": number, "supporting_evidence_ids": [evidence_id]}]}\n'
    "Reference existing hypothesis ids exactly as given; you assign ids for new "
    "proposals. Do not output any prose outside the JSON object."
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

        The prompt is unchanged: one observation against the current hypotheses,
        exactly the shape Run 002 executed. Locked §8 authorises no prompt
        change, so the handle table is rendered into the existing hypothesis
        list rather than restructuring the prompt.
        """
        prompt = AppraisalPrompt(
            system=SYSTEM,
            evidence_observation=request.observation.content,
            # Handles, never durable ids: this is what closes locked §3.1's
            # prohibition on exposing canonical identity to the model.
            active_hypotheses=tuple(
                (str(view.handle), view.statement) for view in request.existing
            ),
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
        label = request.participants[0] if request.participants else None
        proposals = tuple(
            CandidateProposal(
                local_ref=p.hypothesis_id,
                statement=p.statement,
                signature=CommitmentSignatureView(
                    subject=label if label is not None else str(request.subject_id),
                    attribution=f"external-appraisal:{p.hypothesis_id}",
                    claim_class=ClaimClass.INTERPRETATION,
                    stance=Stance.OPEN,
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
