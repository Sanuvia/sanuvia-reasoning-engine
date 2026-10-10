"""GOLDEN / REAL configuration consistency (Area 1).

Two execution modes exist and must never be silently mixed:

* GOLDEN — deterministic scripted extractor + deterministic scripted models, no
  network, byte-identical replay. No :class:`RealRunConfig`.
* REAL   — injected real model/client for every boundary, with an explicit
  :class:`RealRunConfig` naming the provider/model/version, prompts, schemas, and
  inference parameters.

:func:`validate_run_configuration` runs BEFORE any execution and fails loudly on
any inconsistency: a GOLDEN run that carries a real component, or a REAL run that
carries a scripted double or lacks its configuration. GOLDEN never pretends to be
REAL, and REAL never silently falls back to scripted behaviour. No provider is
auto-selected here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.application.ports.reasoning import EvidenceAppraiser

from .evidence_extractors.scripted import ScriptedEvidenceExtractor
from .extraction import EvidenceExtractor
from .failures import ConfigurationError, Maybe
from .language_models.scripted import ScriptedLanguageModel
from .ports import LanguageModel

GOLDEN = "golden"
REAL = "real"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """The explicit identity and parameters of one real model role.

    ``provider``/``model``/``prompt_id``/``schema_id`` are mandatory and must be
    stated, never auto-selected. ``model_version`` and ``seed`` are :class:`Maybe`
    because a provider may not expose them — recorded as unavailable rather than
    invented. ``temperature``/``max_output_tokens``/``context_window`` are our own
    choices, so a plain ``None`` means "not set", which we do know."""

    role: str  # one of the BoundaryKind values
    provider: str
    model: str
    prompt_id: str
    schema_id: str
    temperature: float | None = None
    seed: Maybe = field(default_factory=Maybe.not_provided_by_provider)
    model_version: Maybe = field(default_factory=Maybe.not_captured)
    max_output_tokens: int | None = None
    context_window: int | None = None
    extra_params: tuple[tuple[str, str], ...] = ()

    def _missing_mandatory(self) -> list[str]:
        missing: list[str] = []
        for name, value in (
            ("provider", self.provider),
            ("model", self.model),
            ("prompt_id", self.prompt_id),
            ("schema_id", self.schema_id),
        ):
            if not value or not value.strip():
                missing.append(name)
        return missing

    def to_payload(self) -> dict[str, object]:
        return {
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "prompt_id": self.prompt_id,
            "schema_id": self.schema_id,
            "temperature": self.temperature,
            "seed": self.seed.to_payload(),
            "model_version": self.model_version.to_payload(),
            "max_output_tokens": self.max_output_tokens,
            "context_window": self.context_window,
            "extra_params": [list(pair) for pair in self.extra_params],
        }


@dataclass(frozen=True, slots=True)
class RealRunConfig:
    """The complete, explicit configuration for a REAL run — one spec per boundary."""

    extraction: ModelSpec
    appraisal: ModelSpec
    stateless_baseline: ModelSpec
    transcript_baseline: ModelSpec
    notes: str = ""

    def specs(self) -> tuple[ModelSpec, ...]:
        return (
            self.extraction,
            self.appraisal,
            self.stateless_baseline,
            self.transcript_baseline,
        )

    def _incomplete(self) -> list[str]:
        problems: list[str] = []
        for spec in self.specs():
            for missing in spec._missing_mandatory():
                problems.append(f"{spec.role}.{missing}")
        return problems


def _is_scripted_model(model: LanguageModel) -> bool:
    return isinstance(model, ScriptedLanguageModel)


def _is_scripted_extractor(extractor: EvidenceExtractor) -> bool:
    return isinstance(extractor, ScriptedEvidenceExtractor)


def _is_scripted_appraiser(appraiser: EvidenceAppraiser | None) -> bool:
    return isinstance(appraiser, ScriptedAppraiser)


def validate_run_configuration(
    mode: str,
    *,
    extractor: EvidenceExtractor,
    stateless_model: LanguageModel,
    transcript_model: LanguageModel,
    appraiser: EvidenceAppraiser | None,
    config: RealRunConfig | None,
) -> None:
    """Fail (with :class:`ConfigurationError`) unless every component matches ``mode``.

    Called before execution starts so a mis-configured run never produces
    partially-real, partially-scripted, un-interpretable output."""
    if mode == GOLDEN:
        problems: list[str] = []
        if not _is_scripted_extractor(extractor):
            problems.append("extractor is not a ScriptedEvidenceExtractor")
        if not _is_scripted_model(stateless_model):
            problems.append("stateless_model is not a ScriptedLanguageModel")
        if not _is_scripted_model(transcript_model):
            problems.append("transcript_model is not a ScriptedLanguageModel")
        if appraiser is not None and not _is_scripted_appraiser(appraiser):
            problems.append("appraiser is a real appraiser (golden must be scripted/None)")
        if config is not None:
            problems.append("a RealRunConfig was supplied for a GOLDEN run")
        if problems:
            raise ConfigurationError(
                "GOLDEN run must use only deterministic scripted components: "
                + "; ".join(problems)
            )
        return

    if mode == REAL:
        problems = []
        if _is_scripted_extractor(extractor):
            problems.append("extractor is a ScriptedEvidenceExtractor (REAL must not use a scripted double)")
        if _is_scripted_model(stateless_model):
            problems.append("stateless_model is a ScriptedLanguageModel (REAL must not fall back to scripted)")
        if _is_scripted_model(transcript_model):
            problems.append("transcript_model is a ScriptedLanguageModel (REAL must not fall back to scripted)")
        if appraiser is None:
            problems.append("REAL run requires an injected real EvidenceAppraiser")
        elif _is_scripted_appraiser(appraiser):
            problems.append("appraiser is a scripted appraiser (REAL must not fall back to scripted)")
        if config is None:
            problems.append("REAL run requires an explicit RealRunConfig")
        else:
            for incomplete in config._incomplete():
                problems.append(f"RealRunConfig.{incomplete} is missing")
        if problems:
            raise ConfigurationError(
                "REAL run is not fully configured: " + "; ".join(problems)
            )
        return

    raise ConfigurationError(f"unknown execution mode {mode!r} (expected {GOLDEN!r} or {REAL!r})")
