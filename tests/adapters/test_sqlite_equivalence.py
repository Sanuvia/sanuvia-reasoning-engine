"""The SQLite adapter is pure infrastructure: same behaviour as in-memory.

Running the identical canonical scenario against the SQLite adapter must produce
byte-identical reasoning to the in-memory adapter — proving the persistence
backend changes *where* state lives, never *how* reasoning behaves. A second test
confirms state survives across connections (real durability).
"""

from __future__ import annotations

from collections.abc import Callable

from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.wiring import (
    build_in_memory_dependencies,
    build_sqlite_dependencies,
)
from sanuvia.application.api import ReasoningService
from sanuvia.application.reasoning.dependencies import ReasoningDependencies
from sanuvia.exit_test.runner import _serialise
from sanuvia.exit_test.scenario import SUBJECT, appraisal_script, evidence_inputs


def _run(build: Callable[..., ReasoningDependencies]) -> tuple[object, ...]:
    deps = build(
        appraiser=ScriptedAppraiser(appraisal_script()),
        clock=ManualClock(),
        ids=SequentialIdGenerator(),
    )
    service = ReasoningService(deps)
    results = [service.record_interaction(SUBJECT, [i]) for i in evidence_inputs()]
    return _serialise(results)


def test_sqlite_matches_in_memory_exactly() -> None:
    assert _run(build_sqlite_dependencies) == _run(build_in_memory_dependencies)


def test_sqlite_persists_across_connections(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = str(tmp_path / "sanuvia.db")

    # Write the whole scenario through one connection.
    store = SqliteReasoningStore(path)
    deps = build_sqlite_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(appraisal_script()),
        clock=ManualClock(),
        ids=SequentialIdGenerator(),
    )
    service = ReasoningService(deps)
    for item in evidence_inputs():
        service.record_interaction(SUBJECT, [item])
    before = service.view().understanding(SUBJECT)
    store.close()

    # Reopen a fresh connection to the same file and read it back.
    reopened = SqliteReasoningStore(path)
    reopened_deps = build_sqlite_dependencies(
        store=reopened,
        appraiser=ScriptedAppraiser(appraisal_script()),
    )
    after = ReasoningService(reopened_deps).view().understanding(SUBJECT)

    assert after.model_version_id == before.model_version_id
    assert after.model_uncertainty == before.model_uncertainty
    assert {h.hypothesis_id for h in after.hypotheses} == {
        h.hypothesis_id for h in before.hypotheses
    }
    assert after.revision_count == before.revision_count
    reopened.close()
