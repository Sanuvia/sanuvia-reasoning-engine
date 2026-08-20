"""Demonstrator: identical-evidence guarantee, deterministic replay, and a guard
that Phase 0 is consumed (not shadowed)."""

from __future__ import annotations

import pathlib

import sanuvia

from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models
from fixtures.longitudinal.case_001 import CASE_001

from sanuvia_phase1 import demonstrator, report


def _run() -> demonstrator.DemonstrationReport:
    stateless, transcript = deterministic_language_models()
    conditions = demonstrator.build_default_conditions(CASE_001, stateless, transcript)
    return demonstrator.run(CASE_001, conditions)


def test_all_three_conditions_present() -> None:
    rep = _run()
    assert set(rep.records_by_condition) == {
        "sanuvia_persistent",
        "fm_stateless",
        "fm_transcript",
    }


def test_identical_evidence_sequence_across_conditions() -> None:
    rep = _run()
    expected = tuple(CASE_001.evidence_refs(i) for i in CASE_001.interactions)
    assert rep.evidence_refs_per_interaction == expected
    # seq-5 is an empty interaction for ALL three conditions.
    assert expected[4] == ()
    for records in rep.records_by_condition.values():
        got = tuple(r.ingested_evidence_ids for r in records)
        assert got == expected


def test_deterministic_replay_is_byte_identical() -> None:
    first = report.to_json(_run())
    second = report.to_json(_run())
    assert first == second


def test_phase0_is_consumed_not_shadowed() -> None:
    # The frozen Phase 0 package must still resolve to the repo-root src tree —
    # Phase 1 must not shadow or duplicate it.
    sanuvia_path = pathlib.Path(sanuvia.__file__).resolve()
    assert sanuvia_path.parts[-2:] == ("sanuvia", "__init__.py")
    assert "sanuvia-phase1" not in str(sanuvia_path)
