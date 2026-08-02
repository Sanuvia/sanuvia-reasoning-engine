"""Phase 0 synthetic exit test — the proof this phase exists to produce.

Feeds a fixed, synthetic evidence sequence directly into the reasoning engine
(no product UI, no foundation model, no external infrastructure) and verifies
every Phase 0 pass condition. Fully deterministic and reproducible: it runs on
the in-memory adapters and the deterministic Clock / IdGenerator, so the same
sequence yields identical results every time.

Run it as a script::

    python -m sanuvia.exit_test

Exit code 0 = all pass conditions met; 1 = at least one failed.
"""

from __future__ import annotations

from .runner import CheckResult, HarnessReport, run

__all__ = ["run", "HarnessReport", "CheckResult"]
