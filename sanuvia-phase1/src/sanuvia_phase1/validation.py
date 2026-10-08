"""Strict output validation for the external model boundaries.

Every real model reply is validated against the expected schema *before* it is
allowed to become structured data. The rule is uniform across all four boundaries
(extraction, appraisal, stateless baseline, transcript baseline):

* a reply that is not a JSON object, or whose present fields have the wrong type,
  or whose confidences fall outside ``[0, 1]``, is **rejected** as
  ``MALFORMED_OUTPUT`` — we never coerce it into empty evidence, empty
  hypotheses, default values, or fabricated confidence/uncertainty;
* an *absent* optional key is a legitimately empty answer (the model genuinely
  held nothing), which is distinct from a *malformed* one — this distinction is
  explicit and documented, not silent.

The validators return small typed structures; the adapters map those to their
Phase-0 / Phase-1 shapes. No defaults are invented here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sanuvia.domain import ClaimClass, EvidenceClass, IdentityOutcome, Stance

from .extraction import ProposedStanding

from .failures import BoundaryKind, MalformedOutputError

# --- validated structures -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidatedObservation:
    observation: str
    evidence_class: EvidenceClass
    reliability: float
    classification_confidence: float
    provenance_confidence: float
    text_span: str | None
    #: The standing the extractor PROPOSED (§2 E, R2). ``None`` where it
    #: supplied none -- never defaulted here.
    standing: "ProposedStanding | None" = None


@dataclass(frozen=True, slots=True)
class ValidatedProposal:
    """A candidate reading as the model may state it (v1.5.4 §2 C).

    ``local_ref`` is response-local and never becomes durable. Three fields the
    v1 schema asked the model for are retired, because none of them is the
    model's to decide:

    * ``hypothesis_id`` -- the engine issues durable identity after
      adjudication (locked §3.3);
    * ``initial_support`` -- R6 derives support from the observation's
      reliability;
    * ``supporting_evidence_ids`` -- support attaches to the single observation
      under appraisal, deterministically.
    """

    local_ref: str
    statement: str
    #: The governed commitment signature the model stated (§2 C / §2 H),
    #: minus ``attribution``: the voice is not the model's to choose.
    signature: "ValidatedSignature"


@dataclass(frozen=True, slots=True)
class ValidatedIdentityResolution:
    """A validated R1 resolver reply (§2 G structured output).

    ``matched_ref`` is a resolution-scoped label, never a durable id: the
    adapter never sent one, so the model cannot return one.

    ``confidence`` is **provenance only** (F-8). It is carried and reported; no
    threshold is applied, nothing parks because it is low, and the returned
    outcome is never rewritten on account of it.
    """

    outcome: IdentityOutcome
    matched_ref: str | None
    rationale: str
    confidence: float


@dataclass(frozen=True, slots=True)
class ValidatedSignature:
    """A proposal's stated signature, validated against the governed enums.

    ``subject`` is a request-scoped participant label. It is checked for shape
    only: whether it resolves is complete-plan check 1's decision, in
    ``src/sanuvia``, not the adapter's.

    ``attribution`` is absent by design. It is the voice (§2 H), and an
    appraiser's proposal is the working reading by construction, so accepting
    a model-supplied value would let the model decide whether its own
    interpretation is the participant's own commitment.
    """

    subject: str
    claim_class: ClaimClass
    stance: Stance
    temporal_scope: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedAppraisal:
    supports: tuple[str, ...]
    contradicts: tuple[str, ...]
    proposals: tuple[ValidatedProposal, ...]


@dataclass(frozen=True, slots=True)
class ValidatedHeldHypothesis:
    hypothesis_id: str
    statement: str


@dataclass(frozen=True, slots=True)
class ValidatedContinuityClaim:
    text: str
    cited_evidence_id: str | None


@dataclass(frozen=True, slots=True)
class ValidatedBaseline:
    best_explanations: tuple[str, ...]
    competing_hypotheses_held: tuple[ValidatedHeldHypothesis, ...]
    question_asked: str | None
    continuity_claims: tuple[ValidatedContinuityClaim, ...]


# --- primitives ---------------------------------------------------------------


def parse_json_object(raw_text: str, boundary: BoundaryKind) -> dict[str, Any]:
    try:
        data: Any = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MalformedOutputError(
            boundary, f"response is not valid JSON: {exc}", raw_text
        ) from exc
    if not isinstance(data, dict):
        raise MalformedOutputError(
            boundary, "response must be a JSON object", raw_text
        )
    return data


def _unit_interval(
    value: Any, field: str, boundary: BoundaryKind, raw: str
) -> float:
    # bool is an int subclass — reject it explicitly so True/False can't pass as 1/0.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MalformedOutputError(
            boundary, f"{field!r} must be a number in [0,1], got {value!r}", raw
        )
    number = float(value)
    if not (0.0 <= number <= 1.0):
        raise MalformedOutputError(
            boundary, f"{field!r} must be within [0,1], got {number!r}", raw
        )
    return number


def _require_nonempty_str(
    value: Any, field: str, boundary: BoundaryKind, raw: str
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MalformedOutputError(
            boundary, f"{field!r} must be a non-empty string", raw
        )
    return value


def _require_list(value: Any, field: str, boundary: BoundaryKind, raw: str) -> list[Any]:
    if value is None:
        return []  # an absent list is a legitimately empty answer
    if not isinstance(value, list):
        raise MalformedOutputError(boundary, f"{field!r} must be a list", raw)
    return value


def _str_tuple(value: Any, field: str, boundary: BoundaryKind, raw: str) -> tuple[str, ...]:
    items = _require_list(value, field, boundary, raw)
    out: list[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, str):
            raise MalformedOutputError(
                boundary, f"{field}[{i}] must be a string, got {item!r}", raw
            )
        out.append(item)
    return tuple(out)


# --- boundary validators ------------------------------------------------------


def _optional_proposed_standing(
    item: dict, field: str, boundary, raw_text: str
) -> "ProposedStanding | None":
    """Shape-check the proposed standing fields. Permitted VALUES are the
    application's decision, not the validator's.

    Absent ``role`` means the extractor proposed no standing, which is left
    absent rather than defaulted -- defaulting is exactly how a
    RESPONSE_OR_RESONANCE turn would silently become ordinary supporting
    evidence.

    Whether ``role`` and ``subject`` are permitted is decided by
    ``standing.complete_standing``, which rejects an invalid proposal as
    EVIDENCE_ROLE_VIOLATION under ruling Q6.
    """
    if "role" not in item and "subject_kind" not in item:
        return None
    if "source_kind" in item or "source_id" in item:
        raise MalformedOutputError(
            boundary,
            f"{field}.source_kind/source_id are not the extractor's to supply: "
            f"who spoke is a contextual fact the application supplies (§2 E)",
            raw_text,
        )
    role = _require_nonempty_str(item.get("role"), f"{field}.role", boundary, raw_text)
    subject_kind = _require_nonempty_str(
        item.get("subject_kind"), f"{field}.subject_kind", boundary, raw_text
    )
    subject = item.get("subject")
    if subject is not None and not isinstance(subject, str):
        raise MalformedOutputError(
            boundary, f"{field}.subject must be a string or null", raw_text
        )
    return ProposedStanding(role=role, subject_kind=subject_kind, subject=subject)


def validate_extraction(raw_text: str) -> tuple[ValidatedObservation, ...]:
    """Validate an evidence-extraction reply.

    Requires each evidence item to carry a non-empty ``observation``, a known
    ``evidence_class``, and all three confidences within ``[0,1]``. A missing or
    ill-typed field is rejected — never defaulted to ``0.5`` or ``"reflective"``."""
    boundary = BoundaryKind.EVIDENCE_EXTRACTION
    data = parse_json_object(raw_text, boundary)
    items = _require_list(data.get("evidence"), "evidence", boundary, raw_text)

    out: list[ValidatedObservation] = []
    for k, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise MalformedOutputError(
                boundary, f"evidence[{k}] must be an object", raw_text
            )
        observation = _require_nonempty_str(
            item.get("observation"), f"evidence[{k}].observation", boundary, raw_text
        )
        cls_raw = item.get("evidence_class")
        if not isinstance(cls_raw, str):
            raise MalformedOutputError(
                boundary, f"evidence[{k}].evidence_class must be a string", raw_text
            )
        try:
            evidence_class = EvidenceClass(cls_raw.strip().lower())
        except ValueError as exc:
            raise MalformedOutputError(
                boundary,
                f"evidence[{k}].evidence_class is not a known class: {cls_raw!r}",
                raw_text,
            ) from exc
        span = item.get("text_span")
        if span is not None and not isinstance(span, str):
            raise MalformedOutputError(
                boundary, f"evidence[{k}].text_span must be a string or null", raw_text
            )
        out.append(
            ValidatedObservation(
                observation=observation,
                evidence_class=evidence_class,
                reliability=_unit_interval(
                    item.get("reliability"), f"evidence[{k}].reliability", boundary, raw_text
                ),
                classification_confidence=_unit_interval(
                    item.get("classification_confidence"),
                    f"evidence[{k}].classification_confidence",
                    boundary,
                    raw_text,
                ),
                provenance_confidence=_unit_interval(
                    item.get("provenance_confidence"),
                    f"evidence[{k}].provenance_confidence",
                    boundary,
                    raw_text,
                ),
                text_span=span,
                standing=_optional_proposed_standing(
                    item, f"evidence[{k}]", boundary, raw_text
                ),
            )
        )
    return tuple(out)


def _require_enum(value: object, enum_cls, field: str, boundary, raw_text: str):
    """One of the governed enum values, by value. No coercion, no default."""
    allowed = {member.value: member for member in enum_cls}
    if not isinstance(value, str) or value not in allowed:
        raise MalformedOutputError(
            boundary,
            f"{field} must be one of {sorted(allowed)}; got {value!r}",
            raw_text,
        )
    return allowed[value]


def _require_signature(
    value: object, field: str, boundary, raw_text: str
) -> ValidatedSignature:
    """A proposal's stated signature. Rejected, never defaulted."""
    if not isinstance(value, dict):
        raise MalformedOutputError(boundary, f"{field} must be an object", raw_text)
    if "attribution" in value:
        raise MalformedOutputError(
            boundary,
            f"{field}.attribution is not the model's to supply: attribution is "
            f"the governed voice label and an appraiser's proposal is the "
            f"working reading by construction",
            raw_text,
        )
    scope = value.get("temporal_scope")
    if scope is not None and not isinstance(scope, str):
        raise MalformedOutputError(
            boundary, f"{field}.temporal_scope must be a string or null", raw_text
        )
    return ValidatedSignature(
        subject=_require_nonempty_str(
            value.get("subject"), f"{field}.subject", boundary, raw_text
        ),
        claim_class=_require_enum(
            value.get("claim_class"), ClaimClass, f"{field}.claim_class",
            boundary, raw_text,
        ),
        stance=_require_enum(
            value.get("stance"), Stance, f"{field}.stance", boundary, raw_text
        ),
        temporal_scope=scope,
    )


#: The four governed identity outcomes, by their model-facing spelling. The
#: resolver may return these and nothing else: it cannot invent a fifth.
_IDENTITY_OUTCOMES: dict[str, IdentityOutcome] = {
    "match_existing": IdentityOutcome.MATCH_EXISTING,
    "refine_existing": IdentityOutcome.REFINE_EXISTING,
    "distinct_new": IdentityOutcome.DISTINCT_NEW,
    "ambiguous_review_required": IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED,
}


def validate_identity_resolution(raw_text: str) -> ValidatedIdentityResolution:
    """Validate a bounded R1 resolver reply. Never repaired, never defaulted.

    A malformed or unusable reply raises ``MalformedOutputError``, which the
    application surfaces as ``INVALID_APPRAISAL_RESPONSE`` with
    ``boundary=IDENTITY_RESOLVER`` (F-7 case (d)). There is no retry, no
    rewriting and no fallback outcome: guessing on the model's behalf is
    exactly what the governed failure exists to prevent.
    """
    boundary = BoundaryKind.IDENTITY_RESOLUTION
    data = parse_json_object(raw_text, boundary)

    outcome_value = data.get("outcome")
    if not isinstance(outcome_value, str) or outcome_value not in _IDENTITY_OUTCOMES:
        raise MalformedOutputError(
            boundary,
            f"outcome must be one of {sorted(_IDENTITY_OUTCOMES)}; "
            f"got {outcome_value!r}",
            raw_text,
        )
    outcome = _IDENTITY_OUTCOMES[outcome_value]

    matched_ref = data.get("matched_ref")
    if matched_ref is not None and not isinstance(matched_ref, str):
        raise MalformedOutputError(
            boundary, "matched_ref must be a string or null", raw_text
        )
    if isinstance(matched_ref, str) and not matched_ref.strip():
        raise MalformedOutputError(
            boundary, "matched_ref must be a non-empty string or null", raw_text
        )

    # Outcome/reference SHAPE rules (A-1). These are shape, not semantic
    # identity adjudication: whether a merge names something, and whether a
    # creation names nothing, is decidable from the reply alone.
    #
    # They live here, at the adapter's validation boundary, because that is
    # where the resolver's provenance -- resolver_id, prompt version, schema
    # version -- is available to travel with the governed failure. Raised from
    # the application layer instead, the rejection could carry only the
    # resolver id, so the audit could not say which prompt or schema version
    # produced the unusable reply.
    #
    # The equivalent application-layer checks remain as defence in depth: an
    # IdentityDecision reaching the engine from any other path is still
    # refused there.
    if outcome is IdentityOutcome.MATCH_EXISTING and matched_ref is None:
        raise MalformedOutputError(
            boundary,
            "outcome match_existing must name the matched_ref it matches",
            raw_text,
        )
    if outcome is IdentityOutcome.DISTINCT_NEW and matched_ref is not None:
        raise MalformedOutputError(
            boundary,
            f"outcome distinct_new must not name a matched_ref; got "
            f"{matched_ref!r}. A distinct commitment founds a lineage, and the "
            f"engine issues its durable identity after adjudication",
            raw_text,
        )

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise MalformedOutputError(
            boundary, f"confidence must be a number; got {confidence!r}", raw_text
        )
    if not 0.0 <= float(confidence) <= 1.0:
        raise MalformedOutputError(
            boundary, f"confidence must lie in [0,1]; got {confidence!r}", raw_text
        )

    return ValidatedIdentityResolution(
        outcome=outcome,
        matched_ref=matched_ref,
        rationale=_require_nonempty_str(
            data.get("rationale"), "rationale", boundary, raw_text
        ),
        confidence=float(confidence),
    )


def validate_appraisal(raw_text: str) -> ValidatedAppraisal:
    """Validate an evidence-appraisal reply.

    A proposal must carry a non-empty ``local_ref`` AND ``statement``; a
    malformed proposal is rejected (not silently skipped, not defaulted).

    Hypothesis references are **handles**, which the adapter issued for this
    request. The validator checks shape only: whether a handle resolves is a
    governed control that runs after this returns, in ``src/sanuvia``."""
    boundary = BoundaryKind.EVIDENCE_APPRAISAL
    data = parse_json_object(raw_text, boundary)

    supports = _str_tuple(data.get("supports"), "supports", boundary, raw_text)
    contradicts = _str_tuple(data.get("contradicts"), "contradicts", boundary, raw_text)

    proposals: list[ValidatedProposal] = []
    for k, item in enumerate(
        _require_list(data.get("proposals"), "proposals", boundary, raw_text), start=1
    ):
        if not isinstance(item, dict):
            raise MalformedOutputError(
                boundary, f"proposals[{k}] must be an object", raw_text
            )
        for retired in ("hypothesis_id", "initial_support", "supporting_evidence_ids"):
            if retired in item:
                raise MalformedOutputError(
                    boundary,
                    f"proposals[{k}].{retired} is retired in schema.appraisal.v2: "
                    f"the engine issues durable identity, R6 derives support, and "
                    f"support attaches to the observation under appraisal",
                    raw_text,
                )
        proposals.append(
            ValidatedProposal(
                local_ref=_require_nonempty_str(
                    item.get("local_ref"),
                    f"proposals[{k}].local_ref",
                    boundary,
                    raw_text,
                ),
                statement=_require_nonempty_str(
                    item.get("statement"), f"proposals[{k}].statement", boundary, raw_text
                ),
                signature=_require_signature(
                    item.get("signature"), f"proposals[{k}].signature",
                    boundary, raw_text,
                ),
            )
        )
    return ValidatedAppraisal(supports, contradicts, tuple(proposals))


def validate_baseline(raw_text: str, boundary: BoundaryKind) -> ValidatedBaseline:
    """Validate a baseline (stateless / transcript-context) reply.

    The response must be a JSON object; every *present* key is type-checked
    strictly (a held hypothesis needs both id and statement; a continuity claim
    needs text). An *absent* key is a legitimately empty answer — this is the one
    place emptiness is allowed, and it is explicit, not a fallback for garbage."""
    data = parse_json_object(raw_text, boundary)

    best = _str_tuple(data.get("best_explanations"), "best_explanations", boundary, raw_text)

    held: list[ValidatedHeldHypothesis] = []
    for k, item in enumerate(
        _require_list(
            data.get("competing_hypotheses_held"),
            "competing_hypotheses_held",
            boundary,
            raw_text,
        ),
        start=1,
    ):
        if not isinstance(item, dict):
            raise MalformedOutputError(
                boundary, f"competing_hypotheses_held[{k}] must be an object", raw_text
            )
        held.append(
            ValidatedHeldHypothesis(
                hypothesis_id=_require_nonempty_str(
                    item.get("id"),
                    f"competing_hypotheses_held[{k}].id",
                    boundary,
                    raw_text,
                ),
                statement=_require_nonempty_str(
                    item.get("statement"),
                    f"competing_hypotheses_held[{k}].statement",
                    boundary,
                    raw_text,
                ),
            )
        )

    question = data.get("question_asked")
    if question is not None and not isinstance(question, str):
        raise MalformedOutputError(
            boundary, "'question_asked' must be a string or null", raw_text
        )

    claims: list[ValidatedContinuityClaim] = []
    for k, item in enumerate(
        _require_list(
            data.get("continuity_claims"), "continuity_claims", boundary, raw_text
        ),
        start=1,
    ):
        if not isinstance(item, dict):
            raise MalformedOutputError(
                boundary, f"continuity_claims[{k}] must be an object", raw_text
            )
        cited = item.get("cited_evidence_id")
        if cited is not None and not isinstance(cited, str):
            raise MalformedOutputError(
                boundary,
                f"continuity_claims[{k}].cited_evidence_id must be a string or null",
                raw_text,
            )
        claims.append(
            ValidatedContinuityClaim(
                text=_require_nonempty_str(
                    item.get("text"),
                    f"continuity_claims[{k}].text",
                    boundary,
                    raw_text,
                ),
                cited_evidence_id=cited,
            )
        )

    return ValidatedBaseline(best, tuple(held), question, tuple(claims))
