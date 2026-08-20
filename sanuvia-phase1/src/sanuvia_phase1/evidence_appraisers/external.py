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

Governance (unresolved — Felix/Lillian/devs): the provider/model and the exact
appraisal prompt/response schema are NOT decided here.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

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


def _num(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default


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
        data: Any = json.loads(self._client(request))
        if not isinstance(data, dict):
            raise ValueError("appraisal response must be a JSON object")

        supports = tuple(HypothesisId(str(x)) for x in data.get("supports", []) or [])
        contradicts = tuple(
            HypothesisId(str(x)) for x in data.get("contradicts", []) or []
        )

        proposals: list[ProposedHypothesis] = []
        for item in data.get("proposals", []) or []:
            if not isinstance(item, dict):
                continue
            hid = item.get("hypothesis_id")
            statement = item.get("statement")
            if not hid or not statement:
                continue  # a proposal must have an id and a statement
            proposals.append(
                ProposedHypothesis(
                    hypothesis_id=HypothesisId(str(hid)),
                    statement=str(statement),
                    initial_support=_num(item.get("initial_support"), 0.4),
                    supporting_evidence_ids=tuple(
                        EvidenceRecordId(str(e))
                        for e in item.get("supporting_evidence_ids", []) or []
                    ),
                )
            )

        return Appraisal(
            supports=supports, contradicts=contradicts, proposals=tuple(proposals)
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
