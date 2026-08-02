"""Runnable entry point: ``python -m sanuvia.exit_test``.

Prints a per-condition report and exits 0 (all pass) or 1 (any fail).
"""

from __future__ import annotations

import sys

from .runner import run


def main() -> int:
    report = run()
    print(report.render())
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
