"""Area 1 — GOLDEN/REAL configuration consistency.

The guard runs BEFORE execution: GOLDEN may use only scripted doubles, REAL may
not fall back to any scripted double and needs a complete RealRunConfig. A
mis-configured run raises ConfigurationError rather than producing partially-real,
un-interpretable output.
"""

from __future__ import annotations

import dataclasses

import pytest

from fixtures.longitudinal.case_001 import CASE_001
from fixtures.longitudinal.case_001_transcript import (
    CASE_001_APPRAISAL_SCRIPT,
    CASE_001_HYPOTHESIS_CATALOGUE,
    CASE_001_TRANSCRIPT,
    case_001_scripted_extractor,
)
from fixtures.offline_real import OFFLINE_PARTICIPANTS, offline_real_config

from sanuvia.adapters.reasoning import ScriptedAppraiser

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_appraisers import ExternalEvidenceAppraiser
from sanuvia_phase1.evidence_extractors import ExternalEvidenceExtractor, ScriptedEvidenceExtractor
from sanuvia_phase1.failures import ConfigurationError
from sanuvia_phase1.language_models import ExternalLanguageModel, ScriptedLanguageModel
from sanuvia_phase1.runconfig import GOLDEN, REAL, validate_run_configuration


def _scripted_extractor() -> ScriptedEvidenceExtractor:
    return ScriptedEvidenceExtractor({})


def _scripted_lm() -> ScriptedLanguageModel:
    return ScriptedLanguageModel(())


def _external_lm() -> ExternalLanguageModel:
    return ExternalLanguageModel(lambda _req: "{}")


def _external_extractor(
    participants: tuple[str, ...] = OFFLINE_PARTICIPANTS,
) -> ExternalEvidenceExtractor:
    return ExternalEvidenceExtractor(
        lambda _req: "{}", permitted_participants=participants
    )


def _external_appraiser() -> ExternalEvidenceAppraiser:
    return ExternalEvidenceAppraiser(lambda _req: "{}")


# --- GOLDEN -------------------------------------------------------------------


def test_golden_all_scripted_is_valid() -> None:
    validate_run_configuration(
        GOLDEN,
        extractor=_scripted_extractor(),
        stateless_model=_scripted_lm(),
        transcript_model=_scripted_lm(),
        appraiser=None,
        config=None,
    )  # no raise


def test_golden_rejects_a_real_component() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            GOLDEN,
            extractor=_scripted_extractor(),
            stateless_model=_external_lm(),  # real model in a golden run
            transcript_model=_scripted_lm(),
            appraiser=None,
            config=None,
        )


def test_golden_rejects_a_supplied_real_config() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            GOLDEN,
            extractor=_scripted_extractor(),
            stateless_model=_scripted_lm(),
            transcript_model=_scripted_lm(),
            appraiser=None,
            config=offline_real_config(),
        )


# --- REAL ---------------------------------------------------------------------


def test_real_fully_configured_is_valid() -> None:
    validate_run_configuration(
        REAL,
        extractor=_external_extractor(),
        stateless_model=_external_lm(),
        transcript_model=_external_lm(),
        appraiser=_external_appraiser(),
        config=offline_real_config(),
    )  # no raise


def test_real_rejects_scripted_fallback() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_scripted_lm(),  # scripted fallback in a real run
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=offline_real_config(),
        )


def test_real_rejects_scripted_appraiser() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=ScriptedAppraiser({}),  # scripted appraiser in a real run
            config=offline_real_config(),
        )


def test_real_requires_appraiser_and_config() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=None,  # missing real appraiser
            config=offline_real_config(),
        )
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=None,  # missing config
        )


def test_real_rejects_incomplete_config() -> None:
    cfg = offline_real_config()
    holey = dataclasses.replace(
        cfg, extraction=dataclasses.replace(cfg.extraction, provider="")
    )
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=holey,
        )


def test_unknown_mode_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        validate_run_configuration(
            "hybrid",
            extractor=_scripted_extractor(),
            stateless_model=_scripted_lm(),
            transcript_model=_scripted_lm(),
            appraiser=None,
            config=None,
        )


def test_pipeline_enforces_the_guard_before_execution() -> None:
    # A GOLDEN transcript run that smuggles in a real extractor is rejected before
    # the frozen engine or any model runs.
    stateless = ScriptedLanguageModel(())
    transcript_model = ScriptedLanguageModel(())
    with pytest.raises(ConfigurationError):
        pipeline.run_transcript_demonstration(
            CASE_001_TRANSCRIPT,
            _external_extractor(),  # not allowed in golden
            CASE_001_APPRAISAL_SCRIPT,
            CASE_001_HYPOTHESIS_CATALOGUE,
            stateless,
            transcript_model,
            case_id="guard",
            mode=pipeline.GOLDEN,
        )


def test_golden_pipeline_still_runs_with_scripted_components() -> None:
    from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models

    stateless, transcript_model = deterministic_language_models()
    tdr = pipeline.run_transcript_demonstration(
        CASE_001_TRANSCRIPT,
        case_001_scripted_extractor(),
        CASE_001_APPRAISAL_SCRIPT,
        CASE_001_HYPOTHESIS_CATALOGUE,
        stateless,
        transcript_model,
        case_id="guard-ok",
        mode=pipeline.GOLDEN,
    )
    assert tdr.mode == "golden"
    assert len(tdr.demonstration.records_by_condition["sanuvia_persistent"]) == len(
        CASE_001.interactions
    )


# --- REAL participant roster --------------------------------------------------
#
# The roster is required BEFORE execution. Without this check an unconfigured
# REAL run starts, mints an empty request vocabulary, and refuses every extracted
# subject one at a time -- which reads as a model failure rather than a missing
# configuration.


def test_real_rejects_a_missing_participant_roster() -> None:
    with pytest.raises(ConfigurationError) as exc:
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=offline_real_config(participants=()),
        )
    assert "RealRunConfig.participants is empty" in str(exc.value)


def test_real_rejects_an_extractor_built_without_a_roster() -> None:
    """The config stating a roster is not enough: the extractor that will do
    the extracting has to have been built with it."""
    with pytest.raises(ConfigurationError) as exc:
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(participants=()),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=offline_real_config(),
        )
    assert "empty participant roster" in str(exc.value)


def test_real_rejects_a_roster_mismatch() -> None:
    """Two rosters that disagree is worse than one that is missing: the run
    would look configured while extracting under a different vocabulary."""
    with pytest.raises(ConfigurationError) as exc:
        validate_run_configuration(
            REAL,
            extractor=_external_extractor(participants=("pA", "pC")),
            stateless_model=_external_lm(),
            transcript_model=_external_lm(),
            appraiser=_external_appraiser(),
            config=offline_real_config(participants=("pA", "pB")),
        )
    assert "does not match" in str(exc.value)


def test_real_accepts_a_roster_stated_in_a_different_order() -> None:
    """Order is not part of the configuration: minting sorts."""
    validate_run_configuration(
        REAL,
        extractor=_external_extractor(participants=("pB", "pA")),
        stateless_model=_external_lm(),
        transcript_model=_external_lm(),
        appraiser=_external_appraiser(),
        config=offline_real_config(participants=("pA", "pB")),
    )


def test_golden_rejects_a_real_identity_resolver() -> None:
    """A golden run's identity decisions are fixture-authored."""
    from sanuvia_phase1.identity_resolvers import ExternalIdentityResolver

    with pytest.raises(ConfigurationError, match="identity resolver"):
        validate_run_configuration(
            GOLDEN,
            extractor=_scripted_extractor(),
            stateless_model=_scripted_lm(),
            transcript_model=_scripted_lm(),
            appraiser=ScriptedAppraiser({}),
            config=None,
            identity_resolver=ExternalIdentityResolver(lambda _p: "{}"),
        )


def test_real_accepts_no_identity_resolver() -> None:
    """R1 is opt-in. ``None`` parks non-exact candidates (§2 G); it is a valid
    REAL configuration, not a degraded one."""
    validate_run_configuration(
        REAL,
        extractor=_external_extractor(),
        stateless_model=_external_lm(),
        transcript_model=_external_lm(),
        appraiser=_external_appraiser(),
        config=offline_real_config(),
        identity_resolver=None,
    )
