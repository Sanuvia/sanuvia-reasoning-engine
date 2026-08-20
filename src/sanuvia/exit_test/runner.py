"""Runs the canonical scenario and verifies every Phase 0 pass condition."""

from __future__ import annotations

from dataclasses import dataclass

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.application.reasoning.core_loop import InteractionResult
from sanuvia.domain import (
    EvidenceRecord,
    HypothesisId,
    InferenceRecord,
    WorldModel,
)

from .scenario import H_A, H_B, SUBJECT, Harness, build


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HarnessReport:
    checks: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def render(self) -> str:
        lines = ["Sanuvia — Phase 0 Synthetic Exit Test", "=" * 44]
        for c in self.checks:
            mark = "PASS" if c.passed else "FAIL"
            lines.append(f"[{mark}] {c.name}")
            lines.append(f"       {c.detail}")
        lines.append("-" * 44)
        lines.append("RESULT: " + ("PASS — Phase 0 proof holds" if self.passed else "FAIL"))
        return "\n".join(lines)


def _execute(harness: Harness) -> tuple[list[InteractionResult], list[WorldModel]]:
    results: list[InteractionResult] = []
    versions: list[WorldModel] = []
    for inp in harness.inputs:
        r = harness.service.record_interaction(SUBJECT, [inp])
        results.append(r)
        if r.committed and r.model is not None:
            versions.append(r.model)
    return results, versions


def _serialise(results: list[InteractionResult]) -> tuple[object, ...]:
    return tuple(
        (
            None if r.model is None else r.model.model_version_id,
            r.committed,
            r.model_uncertainty,
            tuple((h.hypothesis_id, h.support.value) for h in r.active_hypotheses),
            tuple(
                (p.id, p.likelihood.value, p.trajectory.kind) for p in r.predictions
            ),
            tuple(
                (e.sequence_no, e.revision_event.outcome)
                for e in r.revision_events_since_prior
            ),
            None if r.inquiry is None else r.inquiry.statement,
        )
        for r in results
    )


def _lineages(result: InteractionResult) -> set[HypothesisId]:
    return {h.hypothesis_id for h in result.active_hypotheses}


def _hyps_with_predictions(result: InteractionResult) -> set[HypothesisId]:
    return {
        hid for p in result.predictions for hid in p.derived_from_hypothesis_ids
    }


# --- individual pass conditions ----------------------------------------------


def _check_versions_appended_not_mutated(
    store: InMemoryReasoningStore,
    versions: list[WorldModel],
    results: list[InteractionResult],
) -> CheckResult:
    ids = [v.model_version_id for v in versions]
    distinct = len(set(ids)) == len(ids) and len(ids) >= 2
    # Re-read every version created during the run; each must be byte-identical
    # to what was appended (immutable, never mutated in place).
    unchanged = all(
        store.world_models.get_version(SUBJECT, v.model_version_id) == v
        for v in versions
    )
    pointer = store.world_models.get_current_pointer(SUBJECT)
    pointer_ok = pointer is not None and pointer.model_version_id == ids[-1]
    passed = distinct and unchanged and pointer_ok
    return CheckResult(
        "WorldModel versions are appended, never mutated",
        passed,
        f"{len(ids)} distinct versions appended; every prior version re-read "
        f"unchanged; current pointer -> latest ({ids[-1]}).",
    )


def _check_competing_hypotheses(
    store: InMemoryReasoningStore, results: list[InteractionResult]
) -> CheckResult:
    after_i1 = _lineages(results[0])
    both_retained = (
        store.hypotheses.latest(H_A, SUBJECT) is not None
        and store.hypotheses.latest(H_B, SUBJECT) is not None
    )
    passed = {H_A, H_B} <= after_i1 and both_retained
    return CheckResult(
        "Competing hypotheses are retained",
        passed,
        f"After I1 the model holds {len(after_i1)} competing hypotheses "
        f"({sorted(after_i1)}); both lineages persist through the run.",
    )


def _check_predictions_revised(results: list[InteractionResult]) -> CheckResult:
    b_at_i3 = H_B in _hyps_with_predictions(results[2])
    b_gone_i4 = H_B not in _hyps_with_predictions(results[3])
    a_at_i4 = H_A in _hyps_with_predictions(results[3])
    passed = b_at_i3 and b_gone_i4 and a_at_i4
    return CheckResult(
        "Predictions are revised as evidence changes",
        passed,
        "H_B carries a prediction at I3, which is invalidated at I4 once H_B is "
        "contradicted; H_A gains a prediction at I4 as it becomes the leader.",
    )


def _check_uncertainty_both_directions(
    results: list[InteractionResult],
) -> CheckResult:
    series = [r.model_uncertainty for r in results if r.model_uncertainty is not None]
    decreased = any(b < a for a, b in zip(series, series[1:]))
    increased = any(b > a for a, b in zip(series, series[1:]))
    passed = decreased and increased
    rounded = [round(u, 3) for u in series]
    return CheckResult(
        "ModelUncertainty can both increase and decrease",
        passed,
        f"uncertainty series {rounded}: falls on consolidation and rises on "
        f"destabilisation.",
    )


def _check_failed_acquisition_competing(
    results: list[InteractionResult],
) -> CheckResult:
    new = _lineages(results[4]) - _lineages(results[3])
    passed = len(new) >= 2
    return CheckResult(
        "Failed Acquisition produces competing candidate explanations",
        passed,
        f"the Failed Acquisition at I5 introduced {len(new)} competing candidate "
        f"hypotheses ({sorted(new)}), not a single default.",
    )


def _check_no_inference_as_evidence(store: InMemoryReasoningStore) -> CheckResult:
    type_separated = not issubclass(InferenceRecord, EvidenceRecord) and not issubclass(
        EvidenceRecord, InferenceRecord
    )
    stored = store.evidence.list_for_subject(SUBJECT)
    all_evidence = all(isinstance(e, EvidenceRecord) for e in stored)
    no_inferences_leaked = len(store.inference.list_for_subject(SUBJECT)) == 0
    passed = type_separated and all_evidence and no_inferences_leaked
    return CheckResult(
        "No InferenceRecord is ever accepted as EvidenceRecord",
        passed,
        f"{len(stored)} evidence records stored, all EvidenceRecord instances; "
        "EvidenceRecord and InferenceRecord are unrelated types with separate "
        "stores (no re-ingestion path).",
    )


def _check_revision_traceable(store: InMemoryReasoningStore) -> CheckResult:
    entries = store.ledger.read(SUBJECT)
    evidence_ids = {e.id for e in store.evidence.list_for_subject(SUBJECT)}
    traceable = all(
        entry.revision_event.triggering_evidence_ids
        and all(
            eid in evidence_ids
            for eid in entry.revision_event.triggering_evidence_ids
        )
        for entry in entries
    )
    passed = traceable and len(entries) > 0
    return CheckResult(
        "Every RevisionEvent is traceable to triggering evidence via the ledger",
        passed,
        f"all {len(entries)} committed ledger entries cite triggering evidence "
        "that resolves to a stored EvidenceRecord.",
    )


def _check_deterministic() -> CheckResult:
    first, _ = _execute(build())
    second, _ = _execute(build())
    passed = _serialise(first) == _serialise(second)
    return CheckResult(
        "The run is deterministic and reproducible",
        passed,
        "two independent runs produced byte-identical version ids, "
        "uncertainties, predictions, and ledger outcomes.",
    )


def run() -> HarnessReport:
    """Execute the canonical scenario and evaluate all pass conditions."""
    harness = build()
    results, versions = _execute(harness)
    store = harness.store
    checks = (
        _check_versions_appended_not_mutated(store, versions, results),
        _check_competing_hypotheses(store, results),
        _check_predictions_revised(results),
        _check_uncertainty_both_directions(results),
        _check_failed_acquisition_competing(results),
        _check_no_inference_as_evidence(store),
        _check_revision_traceable(store),
        _check_deterministic(),
    )
    return HarnessReport(checks)
