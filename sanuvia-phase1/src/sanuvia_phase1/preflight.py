"""REAL-evaluation preflight.

Confirms a real Qwen run would be trustworthy WITHOUT running it. Produces a clear
PASS / BLOCKED result and explains exactly what is missing. It never downloads a
model, never runs the model, and never executes the Case-001 comparison.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
from dataclasses import dataclass

from . import governance, prompts
from .failures import ConfigurationError
from .evidence_appraisers.external import ExternalEvidenceAppraiser
from .evidence_extractors.external import ExternalEvidenceExtractor
from .language_models.external import ExternalLanguageModel
from .qwen import QwenAvailability, detect_local_qwen, qwen_real_run_config
from .runconfig import REAL, RealRunConfig, validate_run_configuration

PASS = "PASS"
BLOCKED = "BLOCKED"
UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightResult:
    checks: tuple[Check, ...]

    @property
    def overall(self) -> str:
        # Trustworthy only if EVERY check passes; anything else blocks a real run.
        return PASS if all(c.status == PASS for c in self.checks) else BLOCKED

    def render(self) -> str:
        lines = ["REAL-EVALUATION PREFLIGHT", "=" * 25, ""]
        for c in self.checks:
            lines.append(f"[{c.status:^11}] {c.name}")
            lines.append(f"              {c.detail}")
        lines.append("")
        lines.append(f"OVERALL: {self.overall}")
        if self.overall != PASS:
            blocking = [c.name for c in self.checks if c.status != PASS]
            lines.append("Blocked by: " + ", ".join(blocking))
            lines.append(
                "The real evaluation is NOT runnable until every check is PASS. "
                "Nothing was downloaded or executed."
            )
        return "\n".join(lines)


def _repo_root(override: pathlib.Path | None) -> pathlib.Path:
    if override is not None:
        return override
    # preflight.py -> sanuvia_phase1 -> src -> sanuvia-phase1 -> <repo root>
    return pathlib.Path(__file__).resolve().parents[3]


def _check_config(config: RealRunConfig) -> Check:
    problems = config._incomplete()
    if problems:
        return Check("real_run_config_complete", BLOCKED, "missing: " + ", ".join(problems))
    return Check(
        "real_run_config_complete", PASS,
        f"provider={config.extraction.provider}, model={config.extraction.model}, "
        "all four boundaries specified",
    )


def _check_prompts(config: RealRunConfig) -> Check:
    missing = [s.prompt_id for s in config.specs() if s.prompt_id not in prompts.PROMPTS]
    if missing:
        return Check("prompts_present", BLOCKED, f"unregistered prompt ids: {missing}")
    return Check("prompts_present", PASS, "all referenced prompt ids registered")


def _check_prompt_integrity() -> Check:
    problems = prompts.verify_prompt_integrity()
    if problems:
        return Check("prompt_integrity_no_drift", BLOCKED, "; ".join(problems))
    return Check(
        "prompt_integrity_no_drift", PASS, "prompt hashes match recorded values"
    )


def _check_schemas(config: RealRunConfig) -> Check:
    missing = [s.schema_id for s in config.specs() if s.schema_id not in prompts.SCHEMAS]
    if missing:
        return Check("schemas_present", BLOCKED, f"unregistered schema ids: {missing}")
    return Check("schemas_present", PASS, "all referenced schema ids registered")


def _check_no_scripted_doubles(config: RealRunConfig) -> Check:
    # Run the REAL guard against representative external (non-scripted) adapters.
    # The no-op clients are never called; only component *types* + config matter.
    try:
        validate_run_configuration(
            REAL,
            extractor=ExternalEvidenceExtractor(lambda _r: ""),
            stateless_model=ExternalLanguageModel(lambda _r: ""),
            transcript_model=ExternalLanguageModel(lambda _r: ""),
            appraiser=ExternalEvidenceAppraiser(lambda _r: ""),
            config=config,
        )
    except ConfigurationError as exc:
        return Check("no_scripted_doubles_in_real", BLOCKED, str(exc))
    return Check(
        "no_scripted_doubles_in_real", PASS,
        "REAL guard passes: no scripted double, no golden component mixed in",
    )


def _check_provider_is_local(config: RealRunConfig) -> Check:
    non_local = {s.provider for s in config.specs() if s.provider != "local_qwen"}
    if non_local:
        return Check("no_network_dependency", BLOCKED, f"non-local providers: {non_local}")
    return Check(
        "no_network_dependency", PASS,
        "provider=local_qwen for every boundary; backend is injected/local — no "
        "cloud SDK, no API key, no network call",
    )


def _check_model_available(availability: QwenAvailability) -> Check:
    if availability.available:
        return Check("model_installed_available", PASS, availability.reason)
    return Check("model_installed_available", BLOCKED, availability.reason)


def _check_model_version(config: RealRunConfig, availability: QwenAvailability) -> Check:
    version = config.extraction.model_version
    if version.availability.name == "AVAILABLE":
        return Check("model_version_identifiable", PASS, f"model_version={version.value}")
    if not availability.available:
        return Check(
            "model_version_identifiable", BLOCKED,
            "model not available, so its exact version cannot be identified yet",
        )
    return Check(
        "model_version_identifiable", BLOCKED,
        "runtime present but the config does not yet record an exact model version",
    )


def _check_governance_freeze() -> Check:
    blocking = governance.blocking_items()
    if blocking:
        return Check(
            "governance_freeze_complete",
            BLOCKED,
            "pending governance items block the run: "
            + ", ".join(item.key for item in blocking),
        )
    return Check(
        "governance_freeze_complete",
        PASS,
        f"all blocking governance items frozen/approved "
        f"(freeze_record_sha256={governance.freeze_record_sha256()[:12]}…)",
    )


def _check_import_isolation() -> Check:
    import sanuvia  # the frozen Phase 0 package

    path = pathlib.Path(sanuvia.__file__).resolve()
    if path.parts[-2:] != ("sanuvia", "__init__.py"):
        return Check("phase0_import_frozen", BLOCKED, f"unexpected sanuvia path: {path}")
    if "sanuvia-phase1" in str(path):
        return Check(
            "phase0_import_frozen", BLOCKED,
            f"Phase 0 resolved from inside the Phase 1 tree: {path}",
        )
    return Check("phase0_import_frozen", PASS, f"frozen Phase 0 at {path}")


def _check_phase0_git_untouched(repo_root: pathlib.Path) -> Check:
    if shutil.which("git") is None:
        return Check(
            "phase0_git_untouched", UNAVAILABLE, "git not available; cannot confirm"
        )
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--",
             "src/sanuvia", "tests", "pyproject.toml"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Check("phase0_git_untouched", UNAVAILABLE, f"git check failed: {exc}")
    if out.returncode != 0:
        return Check(
            "phase0_git_untouched", UNAVAILABLE,
            f"git returned {out.returncode}: {out.stderr.strip()}",
        )
    changed = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if changed:
        return Check(
            "phase0_git_untouched", BLOCKED,
            "Phase 0 paths show changes: " + "; ".join(changed),
        )
    return Check(
        "phase0_git_untouched", PASS,
        "no changes under src/sanuvia, tests/, or pyproject.toml",
    )


def run_real_preflight(
    config: RealRunConfig | None = None,
    *,
    availability: QwenAvailability | None = None,
    repo_root: pathlib.Path | None = None,
) -> PreflightResult:
    """Run every preflight check and return a PASS/BLOCKED result. Never runs the model."""
    cfg = config if config is not None else qwen_real_run_config()
    avail = availability if availability is not None else detect_local_qwen()
    root = _repo_root(repo_root)

    checks = (
        _check_config(cfg),
        _check_prompts(cfg),
        _check_prompt_integrity(),
        _check_schemas(cfg),
        _check_no_scripted_doubles(cfg),
        _check_provider_is_local(cfg),
        _check_governance_freeze(),
        _check_model_available(avail),
        _check_model_version(cfg, avail),
        _check_import_isolation(),
        _check_phase0_git_untouched(root),
    )
    return PreflightResult(checks)
