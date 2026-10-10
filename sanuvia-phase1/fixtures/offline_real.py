"""Offline REAL-mode harness for tests.

A REAL run must use non-scripted components and a complete ``RealRunConfig`` — but
tests must stay offline. This helper supplies an explicit config whose provider is
the honest identifier ``"offline-test"`` (NOT a real vendor — nothing is
auto-selected, nothing reaches a network). It lets tests exercise the REAL wiring
and the configuration guard without choosing a provider.
"""

from __future__ import annotations

from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.runconfig import ModelSpec, RealRunConfig


def _spec(role: str) -> ModelSpec:
    return ModelSpec(
        role=role,
        provider="offline-test",
        model="fake-1",
        prompt_id="prompt-test-v0",
        schema_id="schema-test-v0",
        temperature=0.0,
        seed=Maybe.available("0"),
        model_version=Maybe.not_provided_by_provider(),
        max_output_tokens=256,
        context_window=8192,
    )


def offline_real_config() -> RealRunConfig:
    """A complete, explicit REAL config for offline tests (no vendor, no network)."""
    return RealRunConfig(
        extraction=_spec("evidence_extraction"),
        appraisal=_spec("evidence_appraisal"),
        stateless_baseline=_spec("stateless_baseline"),
        transcript_baseline=_spec("transcript_baseline"),
        notes="offline test harness — no network, no real provider",
    )
