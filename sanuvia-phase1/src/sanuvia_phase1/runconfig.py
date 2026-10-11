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

Two REAL-mode requirements are checked here rather than discovered at runtime:

* the **authorized participant roster** (``RealRunConfig.participants``). Without
  it the extractor mints an empty request vocabulary, so every proposed subject
  is refused one observation at a time and the run looks like a model failure
  instead of a missing configuration. Absent or mismatched is a
  :class:`ConfigurationError` before anything executes.
* the **identity resolver**. R1 is opt-in, so ``None`` is valid; but a scripted
  test double is never valid in REAL, and a configured resolver must carry its
  own :class:`ModelSpec` like every other real boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.reasoning.scripted_identity_resolver import (
    ScriptedIdentityResolver,
)
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
    """The complete, explicit configuration for a REAL run — one spec per boundary.

    ``participants`` is the authorized participant roster for the run: the
    canonical identifiers the extraction boundary may mint request-scoped labels
    over, and the only identifiers a recorded speaker may be. It is mandatory in
    REAL mode and stated, never derived from the transcript — deriving it would
    let the transcript's own content decide who is authorized.

    ``identity_resolution`` is the R1 boundary's spec. ``None`` means no
    resolver is configured, which is a valid REAL configuration: §2 G parks
    non-exact candidates rather than guessing. Supplying a resolver without its
    spec is not.
    """

    extraction: ModelSpec
    appraisal: ModelSpec
    stateless_baseline: ModelSpec
    transcript_baseline: ModelSpec
    participants: tuple[str, ...] = ()
    identity_resolution: ModelSpec | None = None
    notes: str = ""

    def specs(self) -> tuple[ModelSpec, ...]:
        base = (
            self.extraction,
            self.appraisal,
            self.stateless_baseline,
            self.transcript_baseline,
        )
        if self.identity_resolution is None:
            return base
        return (*base, self.identity_resolution)

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


def _is_scripted_resolver(resolver: object | None) -> bool:
    return isinstance(resolver, ScriptedIdentityResolver)


def _extractor_roster(extractor: EvidenceExtractor) -> tuple[str, ...] | None:
    """The authorized roster an extractor was built with, or ``None``.

    Read through the attribute rather than declared on the ``EvidenceExtractor``
    Protocol: a scripted extractor authors its evidence outright and has no
    roster, so requiring one of every extractor would be false. ``None`` means
    "this extractor does not take a roster", which only REAL mode objects to.
    """
    roster = getattr(extractor, "permitted_participants", None)
    if roster is None:
        return None
    return tuple(roster)


def validate_run_configuration(
    mode: str,
    *,
    extractor: EvidenceExtractor,
    stateless_model: LanguageModel,
    transcript_model: LanguageModel,
    appraiser: EvidenceAppraiser | None,
    config: RealRunConfig | None,
    identity_resolver: object | None = None,
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
        if identity_resolver is not None and not _is_scripted_resolver(
            identity_resolver
        ):
            problems.append(
                "a real identity resolver was supplied for a GOLDEN run "
                "(golden identity decisions are fixture-authored)"
            )
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
        if _is_scripted_resolver(identity_resolver):
            problems.append(
                "identity_resolver is a ScriptedIdentityResolver (REAL must not "
                "decide identity from fixture-authored data)"
            )
        if config is None:
            problems.append("REAL run requires an explicit RealRunConfig")
        else:
            for incomplete in config._incomplete():
                problems.append(f"RealRunConfig.{incomplete} is missing")
            # The authorized roster. Checked here so a missing one is a stated
            # configuration failure before execution, rather than an empty
            # request vocabulary that refuses every extracted subject in turn.
            if not config.participants:
                problems.append(
                    "RealRunConfig.participants is empty (REAL requires the "
                    "authorized participant roster; the extraction boundary "
                    "mints its request-scoped labels over it)"
                )
            roster = _extractor_roster(extractor)
            if roster is None:
                problems.append(
                    "extractor exposes no permitted_participants (REAL requires "
                    "an extractor configured with the authorized roster)"
                )
            elif not roster:
                problems.append(
                    "extractor was built with an empty participant roster "
                    "(REAL must not run with an empty request vocabulary)"
                )
            elif config.participants and tuple(sorted(roster)) != tuple(
                sorted(config.participants)
            ):
                problems.append(
                    f"extractor roster {sorted(roster)} does not match "
                    f"RealRunConfig.participants {sorted(config.participants)}"
                )
            if identity_resolver is not None and config.identity_resolution is None:
                problems.append(
                    "an identity resolver was supplied but "
                    "RealRunConfig.identity_resolution is missing"
                )
        if problems:
            raise ConfigurationError(
                "REAL run is not fully configured: " + "; ".join(problems)
            )
        return

    raise ConfigurationError(f"unknown execution mode {mode!r} (expected {GOLDEN!r} or {REAL!r})")
