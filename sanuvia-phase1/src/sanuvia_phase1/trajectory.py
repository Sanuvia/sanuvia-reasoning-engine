"""Normalized trajectory DTOs — the comparable record every condition emits.

A :class:`TrajectoryRecord` captures *one interaction* for *one condition* in a
shape that is comparable across conditions **without faking comparability**:
quantities only the Sanuvia engine can produce (real support values, aggregate
model uncertainty, revision counts, provenance traceability, model version) are
``None`` for the foundation-model baselines — never fabricated.

All DTOs are frozen and built from primitives so the whole report serialises to
canonical JSON for byte-identical deterministic replay.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HypothesisView:
    """A live hypothesis as seen this interaction.

    ``support`` is a real float for the Sanuvia condition and ``None`` for FM
    baselines (which hold no structured support value). The Sanuvia engine
    tracks *supporting* and *contradicting* evidence separately (frozen
    ``Hypothesis`` fields), so both are surfaced; FM baselines carry neither
    (empty tuples)."""

    hypothesis_id: str
    statement: str
    support: float | None
    status: str
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class InquiryView:
    """A surfaced inquiry/question. ``inquiry_id`` is set only for Sanuvia.

    ``status`` is the frozen Phase-0 ``Inquiry`` status-lifecycle value
    (Eng Spec v0.4 §8A / Sys Arch v1.1 §5A — Inquiry is a persistent, status-bearing
    object: proposed | active | dormant | locally_resolved | reopened | superseded |
    closed). Empty for FM baselines, which hold no structured Inquiry object."""

    inquiry_id: str | None
    statement: str
    activated_hypothesis_ids: tuple[str, ...]
    status: str = ""


@dataclass(frozen=True, slots=True)
class DependencyEdgeView:
    """One directed dependency/provenance edge from the frozen Phase-0 dependency
    graph (Sys Arch v1.1 §5A "Dependency and Provenance Relationships"; Eng Spec
    v0.4 §8A ``DependencyEdge``). Relations the engine writes: ``supports`` /
    ``contradicts`` (evidence → hypothesis), ``derived_from`` (prediction →
    hypothesis), etc. Empty for FM baselines (no structured graph)."""

    from_ref: str
    to_ref: str
    relation: str


@dataclass(frozen=True, slots=True)
class PredictionView:
    """A prediction/trajectory. FM baselines emit none under the Phase 1 contract.

    ``derived_from_hypothesis_ids`` / ``derived_from_evidence_ids`` are the
    prediction's provenance links (frozen ``Prediction`` fields), so every
    prediction is traceable to a model snapshot **and** its supporting
    hypotheses (Programme v1.4 Part 4A pass condition)."""

    prediction_id: str
    trajectory_kind: str
    likelihood: float | None
    model_version_id: str | None
    derived_from_hypothesis_ids: tuple[str, ...] = ()
    derived_from_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RevisionEventView:
    """One committed revision since the previous interaction (frozen
    ``RevisionEvent``). Surfaced as a *structured event*, not merely a count —
    Programme v1.4 Part 4A requires "revision events since the prior interaction"
    as a per-step output. FM baselines produce none."""

    sequence_no: int
    outcome: str
    affected_object_id: str
    triggering_evidence_ids: tuple[str, ...]
    from_model_version_id: str | None
    to_model_version_id: str | None


@dataclass(frozen=True, slots=True)
class RecognitionView:
    """A Recognition Condition *record* (frozen ``RecognitionEvent``).

    NOTE: this surfaces records the engine **actually emits**. Recognition
    *computation* (``detect_recognition_condition``) is interface-only and
    deferred in Phase 0, so no records are emitted for the current cases — the
    demonstrator reports that absence explicitly and fabricates no judgment. See
    ``recognition_records`` on :class:`TrajectoryRecord`."""

    recognition_id: str
    kind: str
    description: str
    supporting_evidence_ids: tuple[str, ...]
    model_version_id: str


@dataclass(frozen=True, slots=True)
class ContinuityClaim:
    """A claim that references prior context.

    ``cited_evidence_id`` is the evidence a claim attributes itself to. A claim
    with no citation (``None``) is an *unsupported memory* claim — exactly the
    Case-001 Failure-Condition-1 / unsupported-memory-rate signal."""

    text: str
    cited_evidence_id: str | None


@dataclass(frozen=True, slots=True)
class TrajectoryRecord:
    """One interaction × one condition, normalized for comparison.

    COMMON fields are populated by every condition. SANUVIA-ONLY fields are real
    for the Sanuvia condition and ``None`` for FM baselines.
    """

    # -- COMMON --
    condition: str
    interaction_index: int
    seq_label: str
    ingested_evidence_ids: tuple[str, ...]
    hypotheses: tuple[HypothesisView, ...]
    inquiry: InquiryView | None
    predictions: tuple[PredictionView, ...]
    unsupported_memory_claims: tuple[ContinuityClaim, ...]
    raw: str  # canonical JSON echo of the source output (audit)
    # -- SANUVIA-ONLY (None for FM baselines; never faked) --
    model_uncertainty: float | None = None
    revision_count: int | None = None
    provenance_traceable: bool | None = None
    model_version_id: str | None = None
    # Structured committed revisions since the prior interaction (Sanuvia real;
    # FM ``()``). Complements ``revision_count``.
    revision_events: tuple[RevisionEventView, ...] = ()
    # Dependency/provenance edges touching the active hypotheses & predictions
    # (Programme v1.4 Part 4A per-step "dependencies"; Sys Arch v1.1 §5A). Sanuvia
    # real (append-only, grows over interactions); ``()`` for FM baselines.
    dependency_edges: tuple[DependencyEdgeView, ...] = ()
    # Recognition Condition RECORDS the engine actually emitted this interaction.
    # ``()`` for Sanuvia means "engine emitted none" (computation deferred, not a
    # judgment that no condition exists); ``None`` for FM means "not applicable"
    # (a foundation-model baseline has no Recognition Condition concept).
    recognition_records: tuple[RecognitionView, ...] | None = None


# --- Foundation-model structured output (Phase 1 response contract, §9) -------


@dataclass(frozen=True, slots=True)
class HeldHypothesis:
    """A competing hypothesis a baseline reports holding this turn."""

    hypothesis_id: str
    statement: str


@dataclass(frozen=True, slots=True)
class BaselineTurn:
    """Parsed constrained-JSON output of a baseline language model.

    Mirrors::

        {"best_explanations": [], "competing_hypotheses_held": [],
         "question_asked": null, "continuity_claims": []}
    """

    best_explanations: tuple[str, ...]
    competing_hypotheses_held: tuple[HeldHypothesis, ...]
    question_asked: str | None
    continuity_claims: tuple[ContinuityClaim, ...]
