"""The application's API contract — framework-free.

Two surfaces, both defined against the domain model so reads and writes stay
consistent:

* :class:`ReasoningService` — the write path. Turns ``EvidenceInput`` into
  ``EvidenceRecord`` at the boundary (ids/time via ports) and runs one Core Loop
  interaction. It is the only place callers hand data *in*.
* :class:`WorldModelView` — the read path. A read-only projection of current
  understanding with **no mutating method on its surface** (Programme Part 2:
  "The Content Layer never mutates reasoning"). It is what a future Content Layer
  / product surface consumes.

This contract is framework-free by design (deployment-agnostic core). An HTTP
transport (e.g. FastAPI) is a thin *adapter* over this contract and is added
later without touching the core, exactly as the SQLite persistence adapter is.
"""

from __future__ import annotations

from .service import EvidenceInput, ReasoningService
from .views import WorldModelView, WorldModelViewSnapshot

__all__ = [
    "ReasoningService",
    "EvidenceInput",
    "WorldModelView",
    "WorldModelViewSnapshot",
]
