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
    Appraisal,
    EvidenceAppraiser,
    ProposedHypothesis,
)
from sanuvia.domain import (
    EvidenceRecord,
    EvidenceRecordId,
    Hypothesis,
    HypothesisId,
    SubjectId,
)

from ..validation import validate_appraisal


@dataclass(frozen=True, slots=True)
class AppraisalRequest:
    """A prompt for a real appraisal model — one observation vs the current hypotheses."""

    system: str
    evidence_observation: str
    active_hypotheses: tuple[tuple[str, str], ...]  # (hypothesis_id, statement)
    instruction: str


AppraisalClient = Callable[[AppraisalRequest], str]

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

    def appraise(
        self,
        subject_id: SubjectId,  # noqa: ARG002 (part of the frozen port signature)
        evidence: EvidenceRecord,
        active_hypotheses: Sequence[Hypothesis],
    ) -> Appraisal:
        request = AppraisalRequest(
            system=SYSTEM,
            evidence_observation=evidence.content,
            active_hypotheses=tuple(
                (str(h.hypothesis_id), h.statement) for h in active_hypotheses
            ),
            instruction=INSTRUCTION,
        )
        # Strict validation: a malformed reply (or a proposal missing its id,
        # statement, or a valid initial_support) raises MalformedOutputError — it
        # is never silently skipped or defaulted.
        validated = validate_appraisal(self._client(request))

        supports = tuple(HypothesisId(x) for x in validated.supports)
        contradicts = tuple(HypothesisId(x) for x in validated.contradicts)
        proposals = tuple(
            ProposedHypothesis(
                hypothesis_id=HypothesisId(p.hypothesis_id),
                statement=p.statement,
                initial_support=p.initial_support,
                supporting_evidence_ids=tuple(
                    EvidenceRecordId(e) for e in p.supporting_evidence_ids
                ),
            )
            for p in validated.proposals
        )
        return Appraisal(
            supports=supports, contradicts=contradicts, proposals=proposals
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
