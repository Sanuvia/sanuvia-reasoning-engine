"""Pytest bootstrap for the Controlled Reasoning Demonstrator (Phase 1).

Ensures the Phase 1 package (``src/``) and the fixtures package (this directory)
are importable when the suite is run from here, while Phase 0 remains importable
via its existing editable install. This file adds nothing named ``sanuvia`` to
the path, so it cannot shadow or modify the frozen Phase 0 package.
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).parent.resolve()
for _entry in (_HERE / "src", _HERE):
    _path = str(_entry)
    if _path not in sys.path:
        sys.path.insert(0, _path)
