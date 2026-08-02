"""The end-to-end API demo runs and drives real state changes."""

from __future__ import annotations

from sanuvia.demo import SUBJECT, _build_service
from sanuvia.domain import EvidenceClass
from sanuvia.application.api import EvidenceInput


def test_demo_runs_without_error(capsys) -> None:  # type: ignore[no-untyped-def]
    from sanuvia import demo

    demo.run()
    out = capsys.readouterr().out
    assert "end-to-end API demo" in out
    assert "wm-1 -> wm-2" in out  # WorldModel version advanced


def test_demo_service_produces_expected_state() -> None:
    service = _build_service()
    r1 = service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.BEHAVIOURAL,
                content="went quiet during a disagreement",
                source="reflection:session-1",
                reliability=0.70,
                classification_confidence=0.9,
            )
        ],
    )
    assert r1.model is not None and r1.model.model_version_id == "wm-1"
    assert len(r1.active_hypotheses) == 2  # two competing explanations

    r2 = service.record_interaction(
        SUBJECT,
        [
            EvidenceInput(
                subject_id=SUBJECT,
                evidence_class=EvidenceClass.BEHAVIOURAL,
                content="asked repeatedly whether things were okay",
                source="reflection:session-2",
                reliability=0.85,
                classification_confidence=0.9,
            )
        ],
    )
    # Uncertainty fell as the reassurance hypothesis consolidated, and a
    # prediction was formed — all via the read-only view.
    assert r2.model_uncertainty is not None
    assert r2.model_uncertainty < 0.5
    snap = service.view().understanding(SUBJECT)
    assert snap.model_version_id == "wm-2"
    assert len(snap.predictions) == 1
