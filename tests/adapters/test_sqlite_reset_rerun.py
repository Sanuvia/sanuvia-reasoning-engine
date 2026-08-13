"""Finding 2 — durable SQLite reset / rerun semantics.

Reproduces the original failure first (a deterministic rerun against a persisted
SQLite file collides on ``evidence-1``), then proves:

* the review harness's reset/rerun is clean and byte-identically deterministic;
* durable production wiring uses collision-safe ids and never erases state.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from sanuvia.adapters.http import controllers
from sanuvia.adapters.http.manager import TestCaseManager
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator, UuidGenerator
from sanuvia.adapters.wiring import build_sqlite_dependencies
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    EvidenceClass,
    HypothesisId,
    InvariantViolation,
    SubjectId,
)

SUBJECT = SubjectId("subject-reset-test")
H = HypothesisId("H_durable")


class _AlwaysProposes:
    """Appraiser that proposes one hypothesis, then supports it — independent of
    the evidence id (so it works with non-deterministic uuid ids)."""

    def appraise(self, subject_id: SubjectId, evidence: Any, working: Any) -> Appraisal:
        if any(w.hypothesis_id == H for w in working):
            return Appraisal(supports=(H,))
        return Appraisal(proposals=(ProposedHypothesis(H, "durable explanation", 0.7, ()),))


def _evidence() -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT,
        evidence_class=EvidenceClass.BEHAVIOURAL,
        content="an observation",
        source="reflection",
        reliability=0.7,
        classification_confidence=0.9,
    )


# -- 1. Reproduce the ORIGINAL failure ----------------------------------------


def test_original_duplicate_id_failure_reproduced(tmp_path: Any) -> None:
    """WITHOUT the fix: deterministic ids + a reused durable file collide.

    This is the exact defect Lillian reproduced — a rerun re-issues ``evidence-1``
    while the row from the first run still exists on disk."""
    db = str(tmp_path / "collision.db")

    # First run: deterministic ids write evidence-1.
    deps1 = build_sqlite_dependencies(
        path=db, appraiser=ScriptedAppraiser({}),
        clock=ManualClock(), ids=SequentialIdGenerator(),
    )
    ReasoningService(deps1).record_interaction(SUBJECT, [_evidence()])

    # Rerun the WRONG way: reopen the same file with a FRESH deterministic id
    # generator (restarts at evidence-1) and DO NOT reset -> collision.
    deps2 = build_sqlite_dependencies(
        path=db, appraiser=ScriptedAppraiser({}),
        clock=ManualClock(), ids=SequentialIdGenerator(),
    )
    with pytest.raises(InvariantViolation, match="evidence-1 already exists"):
        ReasoningService(deps2).record_interaction(SUBJECT, [_evidence()])


# -- 2. The fix: harness reset/rerun is clean and deterministic ----------------


def _reasoning_only(snapshot: dict[str, Any]) -> str:
    """A stable, reasoning-only projection of a harness snapshot for comparison."""
    keep = {
        "world_model": snapshot.get("world_model"),
        "timeline": snapshot.get("timeline"),
        "hypothesis_evolution": snapshot.get("hypothesis_evolution"),
        "world_model_timeline": snapshot.get("world_model_timeline"),
        "expected_vs_actual": [
            r.get("match") for r in (snapshot.get("expected_vs_actual") or [])
        ],
    }
    return json.dumps(keep, sort_keys=True)


def test_harness_sqlite_reset_rerun_is_clean_and_deterministic(tmp_path: Any) -> None:
    mgr = TestCaseManager(backend="sqlite", db_base=str(tmp_path / "harness.db"))
    controllers.load_sample(mgr, {"sample_id": "dataset-competing-resolve"})

    first = controllers.run_all(mgr)          # run
    second = controllers.run_all(mgr)         # reset + rerun (must NOT raise)
    third = controllers.run_all(mgr)          # once more for good measure

    # No duplicate-id error occurred, and the reasoning is byte-identical.
    assert "error" not in first and "error" not in second
    assert _reasoning_only(first) == _reasoning_only(second) == _reasoning_only(third)
    assert first["world_model"]["version"] == "wm-5"


# -- 3. Durable production semantics: collision-safe + never erased ------------


def test_durable_sqlite_defaults_to_collision_safe_ids_and_preserves_state(
    tmp_path: Any,
) -> None:
    db = str(tmp_path / "durable.db")

    # First durable session (default wiring -> UuidGenerator, no reset).
    deps1 = build_sqlite_dependencies(path=db, appraiser=_AlwaysProposes())
    ReasoningService(deps1).record_interaction(SUBJECT, [_evidence()])
    model_after_first = deps1.world_models.get_current_model(SUBJECT)
    assert model_after_first is not None
    first_version = model_after_first.model_version_id

    # Reopen the SAME durable file in a new session and add more evidence.
    # Durable wiring must NOT reset — prior reasoning must survive.
    deps2 = build_sqlite_dependencies(path=db, appraiser=_AlwaysProposes())
    ReasoningService(deps2).record_interaction(SUBJECT, [_evidence()])

    # Prior evidence and the earlier model version are still present (not erased),
    # and the reissue produced a NEW unique version rather than colliding.
    assert len(deps2.evidence.list_for_subject(SUBJECT)) == 2
    assert deps2.world_models.get_version(SUBJECT, first_version) is not None
    current = deps2.world_models.get_current_model(SUBJECT)
    assert current is not None and current.model_version_id != first_version


def test_reset_is_explicit_and_only_the_harness_uses_it(tmp_path: Any) -> None:
    """reset() wipes durable rows; it exists for the test harness, and durable
    wiring never calls it (proven by the preservation test above)."""
    store = SqliteReasoningStore(str(tmp_path / "reset.db"))
    deps = build_sqlite_dependencies(store=store, appraiser=_AlwaysProposes())
    ReasoningService(deps).record_interaction(SUBJECT, [_evidence()])
    assert len(store.evidence.list_for_subject(SUBJECT)) == 1
    store.reset()
    assert len(store.evidence.list_for_subject(SUBJECT)) == 0
    assert store.world_models.get_current_model(SUBJECT) is None
