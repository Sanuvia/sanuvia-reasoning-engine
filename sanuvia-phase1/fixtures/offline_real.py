"""Offline REAL-mode harness for tests.

A REAL run must use non-scripted components and a complete ``RealRunConfig`` — but
tests must stay offline. This helper supplies an explicit config whose provider is
the honest identifier ``"offline-test"`` (NOT a real vendor — nothing is
auto-selected, nothing reaches a network). It lets tests exercise the REAL wiring
and the configuration guard without choosing a provider.
"""

from __future__ import annotations

from collections.abc import Sequence

from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.runconfig import ModelSpec, RealRunConfig

#: The authorized participant roster these offline tests run under. Stated here
#: so every REAL-mode test uses one roster, and so the extractor's roster and
#: the config's roster come from the same place -- a mismatch between them is
#: itself a ConfigurationError, which is a thing worth being able to test.
OFFLINE_PARTICIPANTS: tuple[str, ...] = ("pA", "pB")


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


def offline_real_config(
    participants: Sequence[str] = OFFLINE_PARTICIPANTS,
    *,
    identity_resolution: bool = False,
) -> RealRunConfig:
    """A complete, explicit REAL config for offline tests (no vendor, no network).

    ``identity_resolution`` adds the R1 boundary spec, which REAL requires
    whenever an identity resolver is actually supplied.
    """
    return RealRunConfig(
        participants=tuple(participants),
        identity_resolution=_spec("identity_resolution") if identity_resolution else None,
        extraction=_spec("evidence_extraction"),
        appraisal=_spec("evidence_appraisal"),
        stateless_baseline=_spec("stateless_baseline"),
        transcript_baseline=_spec("transcript_baseline"),
        notes="offline test harness — no network, no real provider",
    )
