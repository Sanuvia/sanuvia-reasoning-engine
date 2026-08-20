"""Sanuvia Phase 1 — Controlled Reasoning Demonstrator.

An *internal* reasoning experiment (not a product) that drives one longitudinal
evidence sequence through three conditions and records a normalized reasoning
trajectory for each:

    A. Sanuvia Persistent Reasoning   — the frozen Phase 0 engine (consumed as-is)
    B. Stateless FM baseline          — a foundation model given only the current evidence
    C. Transcript-context FM baseline — a foundation model given all prior transcript text

Phase 0 is a **read-only dependency**. Nothing in this package imports Phase 0
for mutation; the Sanuvia condition consumes only the public Phase 0 API
(`ReasoningService`, `WorldModelView`, `ScriptedAppraiser`,
`build_in_memory_dependencies`, and the `exit_test` renderers).

See ``docs/phase1-controlled-demonstrator.md`` and ``README.md``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
