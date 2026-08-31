"""Local Qwen client boundary (provider-neutral, injected, local-only).

This is the REAL model boundary for the first Qwen evaluation. It is deliberately
free of any vendor SDK import, model download, or network call: a caller injects a
:class:`QwenBackend` (a local runtime such as llama.cpp / Ollama-local /
transformers), and this module composes prompts, records every call in the
immutable manifest, classifies errors/timeouts, and adapts the backend to the
three existing external boundaries (extraction, appraisal, both baselines).

Nothing here selects or downloads a model. The candidate model, its resource
needs, and what remains missing are documented in :data:`QWEN3_4B`; availability
is *detected* (never fetched) by :func:`detect_local_qwen`.

Qwen-specific logic never enters the frozen Phase 0 engine: the client only feeds
the existing `ExternalEvidenceExtractor` / `ExternalEvidenceAppraiser` /
`ExternalLanguageModel` seams.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from . import prompts
from .evidence_appraisers.external import AppraisalRequest, ExternalEvidenceAppraiser
from .evidence_extractors.external import ExtractionRequest, ExternalEvidenceExtractor
from .failures import BoundaryKind, Maybe, ModelError
from .language_models.external import ExternalLanguageModel
from .manifest import RunManifestBuilder, call_with_recording
from .ports import LmRequest
from .runconfig import ModelSpec, RealRunConfig

PROVIDER = "local_qwen"


# --- candidate model documentation (NOT a download, NOT a selection at runtime) --


@dataclass(frozen=True, slots=True)
class QwenCandidate:
    model_id: str
    display_name: str
    approx_params: str
    approx_disk_gb_q4: float
    approx_ram_gb_q4: float
    recommended_backends: tuple[str, ...]
    smaller_fallbacks: tuple[str, ...]
    notes: str


# Documented candidate model for the first real run (project direction). The artifact
# is NOT bundled or downloaded here.
QWEN3_4B = QwenCandidate(
    model_id="qwen3-4b",
    display_name="Qwen3-4B",
    approx_params="~4B",
    approx_disk_gb_q4=2.5,   # Q4_K_M GGUF, approximate
    approx_ram_gb_q4=6.0,    # working set incl. context, approximate
    recommended_backends=(
        "ollama (tag 'qwen3:4b')",
        "llama.cpp GGUF (e.g. Qwen3-4B-Q4_K_M.gguf)",
        "transformers ('Qwen/Qwen3-4B')",
    ),
    smaller_fallbacks=("qwen3-1.7b", "qwen3-0.6b"),
    notes=(
        "Smallest suitable option per project direction. Not downloaded/selected "
        "at runtime; a concrete artifact + local runtime must be provided before a "
        "real run."
    ),
)


# --- generation parameters + runtime metadata --------------------------------


@dataclass(frozen=True, slots=True)
class GenerationParams:
    """Explicit generation parameters. No implicit experimental defaults: the
    caller states them, and they are recorded in the manifest via the config."""

    temperature: float
    max_output_tokens: int
    context_tokens: int
    seed: int | None = None  # None => backend default (recorded as unavailable)
    stop: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QwenRuntimeInfo:
    """What a backend can tell us about itself (for the manifest)."""

    backend_id: str
    model_id: str
    model_version: Maybe
    artifact_id: Maybe
    context_window: int | None


@runtime_checkable
class QwenBackend(Protocol):
    """A local text-generation backend. Provider-neutral and injected.

    ``generate`` returns the model's raw text. It should raise
    :class:`~sanuvia_phase1.failures.ModelTimeout` on timeout and
    :class:`~sanuvia_phase1.failures.ModelError` on a runtime failure; any other
    exception is wrapped as a ModelError by the client (never silently swallowed)."""

    def describe(self) -> QwenRuntimeInfo: ...

    def generate(self, prompt: str, params: GenerationParams) -> str: ...


# --- prompt composition (deterministic string assembly) -----------------------


def compose_extraction_prompt(request: ExtractionRequest) -> str:
    return f"{request.system}\n\nTEXT:\n{request.transcript_text}\n\n{request.instruction}"


def compose_appraisal_prompt(request: AppraisalRequest) -> str:
    hypotheses = (
        "\n".join(f"- {hid}: {statement}" for hid, statement in request.active_hypotheses)
        or "(no current hypotheses)"
    )
    return (
        f"{request.system}\n\nOBSERVATION:\n{request.evidence_observation}\n\n"
        f"CURRENT HYPOTHESES:\n{hypotheses}\n\n{request.instruction}"
    )


def compose_baseline_prompt(request: LmRequest) -> str:
    return f"{request.system}\n\nEVIDENCE:\n{request.context}\n\n{request.instruction}"


# --- the client ---------------------------------------------------------------


class QwenClient:
    """Adapts a local :class:`QwenBackend` to the four external boundaries, recording
    every call in an immutable run manifest.

    Call :meth:`begin_interaction` before the calls belonging to an interaction so
    each recorded call is attributed to the right interaction/seq label."""

    def __init__(
        self,
        backend: QwenBackend,
        params: GenerationParams,
        manifest: RunManifestBuilder,
        *,
        retries: int = 0,
    ) -> None:
        self._backend = backend
        self._params = params
        self._manifest = manifest
        self._retries = retries
        self._index = 0
        self._seq = ""

    def begin_interaction(self, index: int, seq_label: str) -> None:
        self._index = index
        self._seq = seq_label

    def runtime_info(self) -> QwenRuntimeInfo:
        return self._backend.describe()

    def _generate_recorded(
        self, boundary: BoundaryKind, model_role: str, prompt: str
    ) -> str:
        def thunk() -> str:
            try:
                return self._backend.generate(prompt, self._params)
            except ModelError:
                raise  # already typed (ModelError / ModelTimeout)
            except Exception as exc:  # never swallow — classify as a model error
                raise ModelError(f"{type(exc).__name__}: {exc}") from exc

        return call_with_recording(
            self._manifest,
            boundary=boundary,
            interaction_index=self._index,
            seq_label=self._seq,
            model_role=model_role,
            thunk=thunk,
            retries=self._retries,
            # A local model has no server-side session/cache; record that honestly.
            session_id=Maybe.not_provided_by_provider(),
            cache_id=Maybe.not_provided_by_provider(),
        )

    def extraction_client(self) -> Callable[[ExtractionRequest], str]:
        def client(request: ExtractionRequest) -> str:
            return self._generate_recorded(
                BoundaryKind.EVIDENCE_EXTRACTION,
                "evidence_extraction",
                compose_extraction_prompt(request),
            )

        return client

    def appraisal_client(self) -> Callable[[AppraisalRequest], str]:
        def client(request: AppraisalRequest) -> str:
            return self._generate_recorded(
                BoundaryKind.EVIDENCE_APPRAISAL,
                "evidence_appraisal",
                compose_appraisal_prompt(request),
            )

        return client

    def baseline_client(
        self, boundary: BoundaryKind, model_role: str
    ) -> Callable[[LmRequest], str]:
        def client(request: LmRequest) -> str:
            return self._generate_recorded(
                boundary, model_role, compose_baseline_prompt(request)
            )

        return client

    def as_extractor(
        self, extractor_id: str = "qwen-local-extractor.v1"
    ) -> ExternalEvidenceExtractor:
        return ExternalEvidenceExtractor(self.extraction_client(), extractor_id=extractor_id)

    def as_appraiser(self) -> ExternalEvidenceAppraiser:
        return ExternalEvidenceAppraiser(self.appraisal_client())

    def as_stateless_model(self) -> ExternalLanguageModel:
        return ExternalLanguageModel(
            self.baseline_client(BoundaryKind.STATELESS_BASELINE, "stateless_baseline")
        )

    def as_transcript_model(self) -> ExternalLanguageModel:
        return ExternalLanguageModel(
            self.baseline_client(BoundaryKind.TRANSCRIPT_BASELINE, "transcript_baseline")
        )


# --- REAL config factory ------------------------------------------------------


def qwen_real_run_config(
    *,
    model_id: str = QWEN3_4B.model_id,
    model_version: Maybe | None = None,
    artifact_id: Maybe | None = None,
    backend_id: str = "llama.cpp-gguf",
    quantization: str = "Q4_K_M",
    temperature: float = 0.0,
    seed: int | None = 0,
    max_output_tokens: int = 512,
    context_window: int = 8192,
    stop_sequences: str = "none",
) -> RealRunConfig:
    """An explicit REAL config for the local-Qwen evaluation.

    Defaults are conservative and deterministic (temperature 0.0, seed 0), but every
    experimental parameter is stated, not implicit. Fields a runtime cannot yet
    supply (exact model version, artifact digest) are :class:`Maybe`, recorded as
    unavailable rather than invented."""
    version = model_version if model_version is not None else Maybe.not_captured()
    artifact = artifact_id if artifact_id is not None else Maybe.not_captured()
    seed_field = Maybe.available(str(seed)) if seed is not None else Maybe.not_provided_by_provider()

    def _spec(role: str, prompt_id: str, schema_id: str) -> ModelSpec:
        return ModelSpec(
            role=role,
            provider=PROVIDER,
            model=model_id,
            prompt_id=prompt_id,
            schema_id=schema_id,
            temperature=temperature,
            seed=seed_field,
            model_version=version,
            max_output_tokens=max_output_tokens,
            context_window=context_window,
            extra_params=(
                ("backend_id", backend_id),
                ("quantization", quantization),
                ("stop_sequences", stop_sequences),
                ("artifact_availability", artifact.availability.value),
                ("artifact_value", artifact.value or ""),
                ("prompt_sha256", prompts.prompt(prompt_id).content_sha256),
                ("schema_sha256", prompts.schema(schema_id).content_sha256),
                ("seed_policy", "fixed:0 (deterministic where the backend supports it)"),
            ),
        )

    return RealRunConfig(
        extraction=_spec(
            "evidence_extraction", prompts.EXTRACTION_PROMPT_ID, prompts.EXTRACTION_SCHEMA_ID
        ),
        appraisal=_spec(
            "evidence_appraisal", prompts.APPRAISAL_PROMPT_ID, prompts.APPRAISAL_SCHEMA_ID
        ),
        stateless_baseline=_spec(
            "stateless_baseline", prompts.BASELINE_PROMPT_ID, prompts.BASELINE_SCHEMA_ID
        ),
        transcript_baseline=_spec(
            "transcript_baseline", prompts.BASELINE_PROMPT_ID, prompts.BASELINE_SCHEMA_ID
        ),
        notes=(
            "Local Qwen (candidate: Qwen3-4B). Provider-neutral injected backend; "
            "no cloud, no download. Model artifact/version to be supplied at runtime."
        ),
    )


# --- availability detection (no network, no download, no daemon calls) --------


# llama.cpp CLI/server binaries we recognise on PATH (any one suffices).
LLAMA_CPP_BINARIES = ("llama-cli", "llama-server", "llama", "main")


def sha256_file(path: str, *, chunk: int = 1 << 20) -> str:
    """SHA-256 of a local file (streamed). Local read only — no network."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class QwenAvailability:
    available: bool
    reason: str
    model_id: str
    artifact: Maybe
    runtimes_present: tuple[str, ...] = field(default=())
    artifact_sha256: Maybe = field(default_factory=Maybe.not_captured)

    @property
    def has_llama_cpp(self) -> bool:
        return any(
            r == "llama_cpp" or r in LLAMA_CPP_BINARIES for r in self.runtimes_present
        )


def detect_local_qwen(
    *,
    model_id: str = QWEN3_4B.model_id,
    artifact_env: str = "SANUVIA_QWEN_MODEL_PATH",
) -> QwenAvailability:
    """Detect (never fetch) local Qwen support.

    Pure filesystem/PATH/importlib checks — no network, no daemon calls, no model
    download, no model completion. Reports which local runtimes appear installed
    (incl. llama.cpp binaries), whether a model artifact path is configured and
    exists, and — when it exists — the artifact's SHA-256 (a local file read)."""
    runtimes: list[str] = []
    if shutil.which("ollama"):
        runtimes.append("ollama")
    for binary in LLAMA_CPP_BINARIES:
        if shutil.which(binary):
            runtimes.append(binary)
    for module in ("llama_cpp", "transformers", "vllm"):
        if importlib.util.find_spec(module) is not None:
            runtimes.append(module)

    artifact_path = os.environ.get(artifact_env, "").strip()
    artifact_sha256 = Maybe.not_captured()
    if artifact_path and os.path.isfile(artifact_path):
        artifact = Maybe.available(artifact_path)
        artifact_sha256 = Maybe.available(sha256_file(artifact_path))
    elif artifact_path:
        artifact = Maybe.not_captured()  # configured but missing on disk
    else:
        artifact = Maybe.not_provided_by_provider()  # not configured at all

    has_runtime = bool(runtimes)
    has_artifact = artifact.availability.name == "AVAILABLE"

    if has_runtime and has_artifact:
        available = True
        reason = f"runtime(s) {runtimes} present and artifact configured at {artifact.value}"
    elif not has_runtime and not has_artifact:
        available = False
        reason = (
            "no local Qwen runtime detected (checked ollama, llama.cpp binaries, "
            f"llama_cpp, transformers, vllm) and no model artifact configured via "
            f"${artifact_env}"
        )
    elif not has_runtime:
        available = False
        reason = "a model artifact is configured but no local runtime is installed"
    else:
        available = False
        reason = (
            f"runtime(s) {runtimes} present but no model artifact configured/found "
            f"(set ${artifact_env} to an existing model file)"
        )

    return QwenAvailability(
        available=available,
        reason=reason,
        model_id=model_id,
        artifact=artifact,
        runtimes_present=tuple(runtimes),
        artifact_sha256=artifact_sha256,
    )
