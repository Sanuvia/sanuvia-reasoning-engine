"""Raw trajectory metrics — pure functions over ``TrajectoryRecord`` sequences.

Deliberately *raw*: there is **no aggregate divergence score**, no assertion that
divergence must increase, and no pass/fail thresholds. These functions expose
per-interaction and cross-interaction structural measurements for later
interpretation and scoring (numerical thresholds remain a governance
decision).

Engine-only quantities (support, uncertainty, revision count, provenance) are
``None`` for FM baselines; the series functions preserve that ``None`` rather
than substituting a number.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .trajectory import TrajectoryRecord

# --- per-record ---------------------------------------------------------------


def hypothesis_ids(record: TrajectoryRecord) -> frozenset[str]:
    return frozenset(h.hypothesis_id for h in record.hypotheses)


def hypothesis_set_size(record: TrajectoryRecord) -> int:
    return len(record.hypotheses)


def inquiry_present(record: TrajectoryRecord) -> bool:
    return record.inquiry is not None


def prediction_count(record: TrajectoryRecord) -> int:
    return len(record.predictions)


def unsupported_memory_count(record: TrajectoryRecord) -> int:
    return len(record.unsupported_memory_claims)


def retention_rate(
    previous: frozenset[str], current: frozenset[str]
) -> float | None:
    """Fraction of the previous interaction's hypotheses still present.

    ``None`` when there were no prior hypotheses (undefined, not zero)."""
    if not previous:
        return None
    return len(previous & current) / len(previous)


# --- cross-interaction series -------------------------------------------------


def hypothesis_size_series(records: Sequence[TrajectoryRecord]) -> list[int]:
    return [hypothesis_set_size(r) for r in records]


def retention_series(records: Sequence[TrajectoryRecord]) -> list[float | None]:
    out: list[float | None] = []
    prev: frozenset[str] | None = None
    for record in records:
        cur = hypothesis_ids(record)
        out.append(None if prev is None else retention_rate(prev, cur))
        prev = cur
    return out


def inquiry_presence_series(records: Sequence[TrajectoryRecord]) -> list[bool]:
    return [inquiry_present(r) for r in records]


def prediction_count_series(records: Sequence[TrajectoryRecord]) -> list[int]:
    return [prediction_count(r) for r in records]


def unsupported_memory_series(records: Sequence[TrajectoryRecord]) -> list[int]:
    return [unsupported_memory_count(r) for r in records]


def uncertainty_series(records: Sequence[TrajectoryRecord]) -> list[float | None]:
    return [r.model_uncertainty for r in records]


def revision_count_series(records: Sequence[TrajectoryRecord]) -> list[int | None]:
    return [r.revision_count for r in records]


def provenance_series(records: Sequence[TrajectoryRecord]) -> list[bool | None]:
    return [r.provenance_traceable for r in records]


def support_series(
    records: Sequence[TrajectoryRecord],
) -> dict[str, list[float | None]]:
    """Per-hypothesis support across interactions.

    Keys are every hypothesis id that appears in any record (sorted for
    determinism); the value is the support at each interaction, or ``None`` where
    that hypothesis is absent or carries no support (FM baselines)."""
    ids: set[str] = set()
    for record in records:
        ids.update(h.hypothesis_id for h in record.hypotheses)

    series: dict[str, list[float | None]] = {hid: [] for hid in sorted(ids)}
    for record in records:
        present = {h.hypothesis_id: h.support for h in record.hypotheses}
        for hid in series:
            series[hid].append(present.get(hid))
    return series


def observed_inquiry_pairs(
    records: Sequence[TrajectoryRecord],
) -> list[tuple[int, tuple[str, ...]]]:
    """The activated hypothesis ids of each surfaced inquiry, with its interaction
    index. Used to record *which* pair the frozen engine actually selected — never
    to require a particular pair."""
    out: list[tuple[int, tuple[str, ...]]] = []
    for record in records:
        if record.inquiry is not None:
            out.append((record.interaction_index, record.inquiry.activated_hypothesis_ids))
    return out


def recognition_record_series(
    records: Sequence[TrajectoryRecord],
) -> list[int | None]:
    """Count of Recognition Condition *records the engine emitted* per interaction.

    ``None`` where the condition has no Recognition concept (FM baselines). For
    the Sanuvia condition this is normally ``0`` at every point: Recognition
    *computation* (``detect_recognition_condition``) is deferred (interface-only)
    in Phase 0, so no records are written — an explicit "records absent", **not**
    a fabricated "no recognition exists" judgment."""
    out: list[int | None] = []
    for record in records:
        out.append(None if record.recognition_records is None else len(record.recognition_records))
    return out


def revision_event_count_series(records: Sequence[TrajectoryRecord]) -> list[int]:
    """Number of *structured* committed revision events surfaced per interaction."""
    return [len(record.revision_events) for record in records]


def inquiry_status_series(records: Sequence[TrajectoryRecord]) -> list[str | None]:
    """The frozen Phase-0 Inquiry status (§8A/§5A lifecycle) where an inquiry is
    surfaced; ``None`` where no inquiry is present."""
    return [None if r.inquiry is None else r.inquiry.status for r in records]


def dependency_edge_count_series(records: Sequence[TrajectoryRecord]) -> list[int]:
    """Count of dependency/provenance edges surfaced per interaction (Sanuvia
    grows over time; FM baselines are ``0``)."""
    return [len(record.dependency_edges) for record in records]


# --- Diagnostic id-based observables (NOT an evaluation; NO score / NO threshold)

# The supplied authoritative documents name a primary metric — Programme v1.4 C.5
# "rate of behavioural divergence between Sanuvia and baseline over a longitudinal
# case" — but they define NO computable formula, weighting, or "similar vs
# diverged" threshold (Programme v1.4 C.4/C.5 explicitly defer these to the programme
# governance process). We therefore expose only raw per-point observables and DO NOT
# compute the aggregate rate. The aggregate remains pending governance.
DIVERGENCE_RATE_STATUS = (
    "PENDING GOVERNANCE — Programme v1.4 C.5 names 'rate of behavioural divergence' "
    "as the primary metric, but the supplied authoritative documents define no "
    "formula, weighting, or similar/diverged threshold (deferred to the programme "
    "governance process per Programme v1.4 C.4/C.5). Raw per-point observables are exposed "
    "instead; the aggregate rate is not computed."
)

# The hypothesis-set comparison below is by *hypothesis id*. A hypothesis id is an
# opaque handle, NOT a semantic identity: two conditions can express the same
# reading under different ids, or drift semantically under a stable id. This makes
# the id comparison a DEBUGGING DIAGNOSTIC only — it is NOT a valid measure of
# semantic hypothesis continuity/revision, and a difference here is NOT evidence
# that Sanuvia reasons better (or worse) than a baseline. The semantic evaluation
# protocol (continuity/revision, uncertainty, inquiry quality) is defined
# SEPARATELY by the programme team and is not implemented here.
HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT = (
    "DIAGNOSTIC ONLY (id-based) — not a semantic continuity/revision evaluation, "
    "and not evidence that any condition performs better. Hypothesis ids are opaque "
    "handles, not semantic identity. Semantic evaluation is defined separately."
)


@dataclass(frozen=True, slots=True)
class IdBasedDiagnosticPoint:
    """Per-interaction, id-based comparison of Sanuvia vs one baseline — a DEBUGGING
    diagnostic, not an evaluation result.

    The inquiry-presence and uncertainty-comparability fields are plain structural
    observations. ``hypothesis_id_sets_differ`` compares *hypothesis ids* only and
    carries the :data:`HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT`: it is not a semantic
    identity comparison and must never be presented as evidence of better reasoning.
    Nothing here is weighted, summed, normalised, or thresholded."""

    interaction_index: int
    seq_label: str
    inquiry_present_sanuvia: bool
    inquiry_present_baseline: bool
    inquiry_presence_differs: bool
    sanuvia_uncertainty: float | None
    baseline_uncertainty: float | None
    uncertainty_comparable: bool  # both conditions expose a numeric uncertainty?
    sanuvia_hypothesis_ids: tuple[str, ...]
    baseline_hypothesis_ids: tuple[str, ...]
    hypothesis_id_sets_differ: bool  # id-based DIAGNOSTIC — see the caveat above


def id_based_diagnostics(
    sanuvia: Sequence[TrajectoryRecord],
    baseline: Sequence[TrajectoryRecord],
) -> list[IdBasedDiagnosticPoint]:
    """Per-sampled-point id-based DIAGNOSTIC observables (no aggregate, no threshold).

    Retained only for debugging. The ``hypothesis_id_sets_differ`` field is an
    id-level diff, NOT a semantic continuity/revision evaluation — see
    :data:`HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT`. Zips the two conditions by position;
    requires equal length (both are driven through the same interaction sequence)."""
    if len(sanuvia) != len(baseline):
        raise ValueError("conditions must have the same number of sampled points")
    out: list[IdBasedDiagnosticPoint] = []
    for s, b in zip(sanuvia, baseline, strict=True):
        s_inq = s.inquiry is not None
        b_inq = b.inquiry is not None
        s_ids = tuple(sorted(hypothesis_ids(s)))
        b_ids = tuple(sorted(hypothesis_ids(b)))
        out.append(
            IdBasedDiagnosticPoint(
                interaction_index=s.interaction_index,
                seq_label=s.seq_label,
                inquiry_present_sanuvia=s_inq,
                inquiry_present_baseline=b_inq,
                inquiry_presence_differs=s_inq != b_inq,
                sanuvia_uncertainty=s.model_uncertainty,
                baseline_uncertainty=b.model_uncertainty,
                uncertainty_comparable=(
                    s.model_uncertainty is not None and b.model_uncertainty is not None
                ),
                sanuvia_hypothesis_ids=s_ids,
                baseline_hypothesis_ids=b_ids,
                hypothesis_id_sets_differ=s_ids != b_ids,
            )
        )
    return out
