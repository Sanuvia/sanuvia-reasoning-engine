"""Run 003 Stage 1 — the governed single-execution runner for Case 002.

Execution plumbing only. It connects already-approved parts and decides nothing:
the frozen engine, the prompts, the validators, the Case 002 artifacts and the
generation settings are used exactly as they stand.

WHAT IT CONNECTS, AND WHY EACH PIECE IS THERE
---------------------------------------------

* the **approved roster** ``("participant-1", "participant-2")``, supplied to
  both the extractor and the configuration, because the REAL guard refuses a
  mismatch between them;
* the **R1 resolver** over the same recorded client, so a non-exact candidate is
  adjudicated at §2 G case 4 instead of parked;
* the Case 002 transcript as authored, which carries the 10 sequences, the
  10 → 39 interaction mapping and the empty hold at sequence 3;
* a provenance log and an evidence directory **of this run's own**, so nothing
  can be confused with Run 001 or Run 002 output.

The reference module is never imported here, and an isolation test asserts that
over the real import graph rather than trusting this sentence.

SINGLE EXECUTION
----------------

One attempt is authorised, with no retry and no substitution. The runner
refuses to start if its evidence directory already exists, so a second
invocation cannot silently overwrite or append to the first. ``retries=0`` is
passed to the client, as Run 002 did.

A governed stop or an execution failure is **captured, not swallowed**: the
status, the error, the traceback and the partial manifest are all written. The
runner never retries and never substitutes a run.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import pathlib
import subprocess
import traceback
from dataclasses import dataclass

from . import governance, pipeline, prompts
from .failures import Maybe
from .llama_server_backend import LlamaServerBackend
from .manifest import RunManifestBuilder
from .qwen import GenerationParams, QwenClient, qwen_real_run_config

def _load_case_002() -> tuple[object, str, tuple[str, ...]]:
    """Import the Case 002 fixture, which lives in PRIVATE custody.

    Deliberately deferred rather than a module-level import. The fixture is not
    in this repository -- it is held in the private custody repository -- so a
    public checkout has no such module. A top-level import would make this
    module unimportable there, and would make the public test suite depend on
    private material being present on disk, which is exactly the coupling the
    custody boundary exists to prevent.

    Called only when a real execution needs the real transcript. The offline
    tests inject a synthetic transcript and never reach this.
    """
    try:
        from fixtures.longitudinal.case_002 import (  # noqa: PLC0415
            CASE_002_TRANSCRIPT, CASE_ID, ROSTER,
        )
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "the Case 002 fixture is not importable here. It is held in private "
            "custody and is not part of this repository; place it on the path "
            "before a real execution, or inject a transcript explicitly."
        ) from exc
    return CASE_002_TRANSCRIPT, CASE_ID, ROSTER


RUN_ID = "run-003-stage-1"
PHASE1_VERSION = "0.1.0"

#: The frozen generation parameters, restated so a drift is a visible edit.
TEMPERATURE = 0.0
MAX_OUTPUT_TOKENS = 512
CONTEXT_TOKENS = 8192
SEED = 0


@dataclass(frozen=True, slots=True)
class Pins:
    """What this execution is pinned to. Recorded verbatim in the evidence."""

    frozen_engine_commit: str
    custody_commit: str
    fixture_sha256: str
    reference_sha256: str
    tests_sha256: str


def _git_sha(repo_root: pathlib.Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=15, check=False,
        )
        return out.stdout.strip() or "unavailable"
    except (OSError, subprocess.SubprocessError):
        return "unavailable"


def build_runner(
    *,
    base_url: str,
    model_version: str,
    artifact_id: str,
    llama_cpp_build: str,
    provenance_path: pathlib.Path,
    transcript: object | None = None,
    backend: object | None = None,
    roster: tuple[str, ...] | None = None,
) -> tuple[object, QwenClient, RunManifestBuilder]:
    """Assemble config, backend and client without executing anything.

    Split out from ``execute`` so the wiring can be exercised offline against a
    test backend. ``backend`` overrides the real one for exactly that purpose;
    a real run passes ``None`` and gets the llama.cpp backend.
    """
    used_roster = roster if roster is not None else _load_case_002()[2]
    config = qwen_real_run_config(
        participants=used_roster,
        model_version=Maybe.available(model_version),
        artifact_id=Maybe.available(artifact_id),
    )
    # R1 is configured for this run, so its boundary needs its own ModelSpec.
    config = dataclasses.replace(
        config,
        identity_resolution=dataclasses.replace(
            config.extraction,
            role="identity_resolution",
            prompt_id=prompts.IDENTITY_PROMPT_ID,
            schema_id=prompts.IDENTITY_SCHEMA_ID,
        ),
    )

    used_transcript = (
        transcript if transcript is not None else _load_case_002()[0]
    )
    builder = RunManifestBuilder(
        run_id=RUN_ID,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        git_commit_sha=_git_sha(pathlib.Path(__file__).resolve().parents[3]),
        phase1_version=PHASE1_VERSION,
        mode="real",
        transcript=used_transcript,  # type: ignore[arg-type]
        model_specs=config.specs(),
        governance_freeze_hash=governance.freeze_record_sha256(),
    )
    real_backend = backend if backend is not None else LlamaServerBackend(
        base_url,
        model_id="qwen3-4b",
        model_version=model_version,
        artifact_id=artifact_id,
        llama_cpp_build=llama_cpp_build,
        context_window=CONTEXT_TOKENS,
        provenance_path=str(provenance_path),
    )
    params = GenerationParams(
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        context_tokens=CONTEXT_TOKENS,
        seed=SEED,
        stop=(),
    )
    client = QwenClient(real_backend, params, builder, retries=0)  # type: ignore[arg-type]
    return config, client, builder


def execute(
    *,
    evidence_dir: pathlib.Path,
    base_url: str,
    model_version: str,
    artifact_id: str,
    llama_cpp_build: str,
    pins: Pins,
    transcript: object | None = None,
    backend: object | None = None,
    roster: tuple[str, ...] | None = None,
    case_id: str | None = None,
) -> dict[str, object]:
    """Run Stage 1 once and write the complete evidence.

    Refuses to start if ``evidence_dir`` already exists. That is the guard
    against a second attempt: one authorised execution, no overwrite, no append.
    """
    if evidence_dir.exists():
        raise FileExistsError(
            f"evidence directory {evidence_dir} already exists; a second "
            f"execution is not authorised and must not overwrite the first"
        )
    evidence_dir.mkdir(parents=True)
    provenance_path = evidence_dir / "backend_calls.jsonl"

    if transcript is None or roster is None or case_id is None:
        fixture_transcript, fixture_case_id, fixture_roster = _load_case_002()
        transcript = transcript if transcript is not None else fixture_transcript
        roster = roster if roster is not None else fixture_roster
        case_id = case_id if case_id is not None else fixture_case_id

    config, client, builder = build_runner(
        base_url=base_url,
        model_version=model_version,
        artifact_id=artifact_id,
        llama_cpp_build=llama_cpp_build,
        provenance_path=provenance_path,
        transcript=transcript,
        backend=backend,
        roster=roster,
    )
    used_transcript = transcript

    status = "completed"
    abort_error: str | None = None
    abort_tb: str | None = None
    report = None
    try:
        report = pipeline.run_transcript_demonstration(
            used_transcript,  # type: ignore[arg-type]
            client.as_extractor(permitted_participants=roster),
            {},  # appraisal_script unused: a real appraiser is injected
            {},  # hypothesis_catalogue unused with a real appraiser
            client.as_stateless_model(),
            client.as_transcript_model(),
            case_id=case_id,
            mode=pipeline.REAL,
            appraiser=client.as_appraiser(),
            config=config,  # type: ignore[arg-type]
            identity_resolver=client.as_identity_resolver(),
            on_interaction_start=client.begin_interaction,
        )
    except BaseException as exc:  # capture the governed failure; never retry
        status = "aborted"
        abort_error = f"{type(exc).__name__}: {exc}"
        abort_tb = traceback.format_exc()

    manifest = builder.finalize()
    evidence: dict[str, object] = {
        "run_id": RUN_ID,
        "stage": "stage-1",
        "case_id": case_id,
        "execution_status": status,
        "abort_error": abort_error,
        "abort_traceback": abort_tb,
        "pins": {
            "frozen_engine_commit": pins.frozen_engine_commit,
            "custody_commit": pins.custody_commit,
            "fixture_sha256": pins.fixture_sha256,
            "reference_sha256": pins.reference_sha256,
            "tests_sha256": pins.tests_sha256,
        },
        "roster": list(roster),
        "sequences": 10,
        "interactions": len(used_transcript.interactions),  # type: ignore[attr-defined]
        "generation": {
            "temperature": TEMPERATURE, "seed": SEED,
            "max_output_tokens": MAX_OUTPUT_TOKENS, "context_tokens": CONTEXT_TOKENS,
        },
        "manifest": manifest.to_payload() if hasattr(manifest, "to_payload") else str(manifest),
    }
    (evidence_dir / "execution_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    if report is not None:
        (evidence_dir / "trajectories.json").write_text(
            json.dumps(
                {c: [dataclasses.asdict(r) for r in recs]
                 for c, recs in report.demonstration.records_by_condition.items()},
                indent=2, ensure_ascii=False, default=str,
            ),
            encoding="utf-8",
        )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 003 Stage 1 (single governed execution)")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--artifact-id", required=True)
    parser.add_argument("--llama-cpp-build", required=True)
    parser.add_argument("--frozen-engine-commit", required=True)
    parser.add_argument("--custody-commit", required=True)
    parser.add_argument("--fixture-sha256", required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--tests-sha256", required=True)
    args = parser.parse_args(argv)

    evidence = execute(
        evidence_dir=pathlib.Path(args.evidence_dir),
        base_url=args.base_url,
        model_version=args.model_version,
        artifact_id=args.artifact_id,
        llama_cpp_build=args.llama_cpp_build,
        pins=Pins(
            frozen_engine_commit=args.frozen_engine_commit,
            custody_commit=args.custody_commit,
            fixture_sha256=args.fixture_sha256,
            reference_sha256=args.reference_sha256,
            tests_sha256=args.tests_sha256,
        ),
    )
    print(f"status: {evidence['execution_status']}")
    return 0 if evidence["execution_status"] == "completed" else 1
