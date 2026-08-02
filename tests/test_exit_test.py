"""The Phase 0 exit test is part of the automated suite, and stays green."""

from __future__ import annotations

from sanuvia.exit_test import run


def test_all_pass_conditions_hold() -> None:
    report = run()
    failed = [c.name for c in report.checks if not c.passed]
    assert report.passed, f"failed pass conditions: {failed}"


def test_exit_test_is_reproducible() -> None:
    first = run()
    second = run()
    assert [(c.name, c.passed) for c in first.checks] == [
        (c.name, c.passed) for c in second.checks
    ]
    assert first.passed and second.passed
