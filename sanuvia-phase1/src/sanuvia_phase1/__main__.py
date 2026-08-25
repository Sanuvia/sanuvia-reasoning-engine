"""Phase 1 CLI. Mirrors the Phase 0 ``python -m sanuvia.exit_test`` convention.

    python -m sanuvia_phase1 preflight-real   # REAL-evaluation preflight (no run)
    python -m sanuvia_phase1 governance        # print the governance / freeze checklist

Neither command downloads a model, runs a model, or executes the comparison.
``preflight-real`` exits 0 on PASS and non-zero on BLOCKED.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import governance
from .preflight import run_real_preflight
from .qwen import detect_local_qwen, qwen_real_run_config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sanuvia_phase1")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser(
        "preflight-real",
        help="check readiness for the first REAL Qwen evaluation (does not run it)",
    )
    sub.add_parser(
        "governance",
        help="print the governance / freeze checklist (FROZEN / PENDING / BLOCKING)",
    )
    args = parser.parse_args(argv)

    if args.command == "preflight-real":
        result = run_real_preflight(
            qwen_real_run_config(), availability=detect_local_qwen()
        )
        print(result.render())
        return 0 if result.overall == "PASS" else 2

    if args.command == "governance":
        print(governance.render_checklist())
        return 0 if governance.is_real_run_permitted() else 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
