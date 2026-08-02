"""The reasoning engine is deterministic and reproducible.

Two independent runs of the same scripted scenario must produce byte-identical
results — same version ids, uncertainties, ledger, and predictions. This is what
lets the synthetic exit test be reproducible.
"""

from __future__ import annotations

from sanuvia.domain import EvidenceClass

from .test_core_loop import SUBJECT, _build, _ev


def _run_scenario() -> list[tuple[object, ...]]:
    loop, clock, store = _build()
    trace: list[tuple[object, ...]] = []
    for eid, cls, rel in [
        ("ev1", EvidenceClass.BEHAVIOURAL, 0.7),
        ("ev2", EvidenceClass.BEHAVIOURAL, 0.8),
        ("ev3", EvidenceClass.BEHAVIOURAL, 0.8),
        ("ev4", EvidenceClass.CONTRADICTORY, 0.8),
        ("ev5", EvidenceClass.FAILED_ACQUISITION, 0.3),
        ("ev6", EvidenceClass.CONTRADICTORY, 0.3),
    ]:
        clock.tick()
        r = loop.ingest(SUBJECT, [_ev(clock, eid, cls=cls, reliability=rel)])
        trace.append(
            (
                None if r.model is None else r.model.model_version_id,
                r.committed,
                r.model_uncertainty,
                tuple(h.hypothesis_id for h in r.active_hypotheses),
                tuple((h.hypothesis_id, h.support.value) for h in r.active_hypotheses),
                tuple(
                    (p.id, p.likelihood.value, p.trajectory.kind)
                    for p in r.predictions
                ),
                tuple(
                    (e.sequence_no, e.revision_event.outcome)
                    for e in r.revision_events_since_prior
                ),
                None if r.inquiry is None else r.inquiry.statement,
            )
        )
    return trace


def test_scenario_is_reproducible() -> None:
    assert _run_scenario() == _run_scenario()
