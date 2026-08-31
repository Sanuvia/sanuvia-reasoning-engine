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

from sanuvia.domain import EvidenceClass

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


@dataclass(frozen=True, slots=True)
class ValidatedProposal:
    hypothesis_id: str
    statement: str
    initial_support: float
    supporting_evidence_ids: tuple[str, ...]


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
            )
        )
    return tuple(out)


def validate_appraisal(raw_text: str) -> ValidatedAppraisal:
    """Validate an evidence-appraisal reply.

    A proposal must carry a non-empty id AND statement AND an ``initial_support``
    within ``[0,1]``; a malformed proposal is rejected (not silently skipped, not
    defaulted to ``0.4``)."""
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
        proposals.append(
            ValidatedProposal(
                hypothesis_id=_require_nonempty_str(
                    item.get("hypothesis_id"),
                    f"proposals[{k}].hypothesis_id",
                    boundary,
                    raw_text,
                ),
                statement=_require_nonempty_str(
                    item.get("statement"), f"proposals[{k}].statement", boundary, raw_text
                ),
                initial_support=_unit_interval(
                    item.get("initial_support"),
                    f"proposals[{k}].initial_support",
                    boundary,
                    raw_text,
                ),
                supporting_evidence_ids=_str_tuple(
                    item.get("supporting_evidence_ids"),
                    f"proposals[{k}].supporting_evidence_ids",
                    boundary,
                    raw_text,
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
