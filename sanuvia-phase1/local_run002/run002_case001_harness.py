"""LOCAL Run 002 Case 001 execution harness (local plumbing, governed execution).

An exact analogue of local_run001/run001_harness.py. It wires the Run-002 backend
into the EXISTING frozen provider-neutral seams and drives the EXISTING frozen
pipeline over the EXISTING frozen Case 001 transcript. The ONLY differences from the
Run 001 harness are the backend class (LlamaServerBackendRun002, whose generate()
enforces the reasoning-content invariant), the port, the run id, and the output
directory.

It changes no experimental content: prompts, schemas, conditions, generation
parameters, the frozen validators/failure policy, and Phase 0 are all imported
unchanged from the frozen package. No retries. No fallback. No repair. It does not
interpret, score, or tune anything; it only executes once and records raw provenance.

All three conditions -- sanuvia_persistent, fm_stateless, fm_transcript -- are driven
from ONE pipeline.run_transcript_demonstration call over the SAME Case 001 sequence,
so the fairness guard applies exactly as it does in Run 001.

Governed pins (asserted before any model call):
  commit                       3f2bda15a74e5f2f3d57caa3888e115d7960d035
  execution configuration sha  48c8fb0619e245bf7248702811d6d8cb133a6572c70c15435417fda81f07f2c4
  reviewed pre-seal archive    cbcd83fd9e9228b85a6f01afaf146c263801fd8e303c0844c9c8e9f672537971
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import traceback

_HERE = pathlib.Path(__file__).resolve().parent
_PHASE1 = _HERE.parent            # sanuvia-phase1
_REPO = _PHASE1.parent            # repo root
for _p in (str(_PHASE1 / "src"), str(_PHASE1), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fixtures.longitudinal.case_001_transcript import CASE_001_TRANSCRIPT

from sanuvia_phase1 import __version__ as PHASE1_VERSION
from sanuvia_phase1 import governance, pipeline, report
from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.qwen import GenerationParams, QwenClient, qwen_real_run_config

from llama_server_backend_run002 import LlamaServerBackendRun002

BASE_URL = "http://127.0.0.1:8137"
MODEL_PATH = "/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf"

PINNED_COMMIT = "3f2bda15a74e5f2f3d57caa3888e115d7960d035"
PINNED_CONFIG_SHA = "48c8fb0619e245bf7248702811d6d8cb133a6572c70c15435417fda81f07f2c4"
PINNED_ARCHIVE_SHA = "cbcd83fd9e9228b85a6f01afaf146c263801fd8e303c0844c9c8e9f672537971"

_CONFIG_PATH = _HERE / "evidence_preseal/config/execution_configuration.json"
_ARCHIVE_PATH = _HERE / "run002_evidence_preseal.tar.gz"


def _frozen(key: str) -> str:
    for item in governance.FREEZE_RECORD:
        if item.key == key and item.status is governance.GovernanceStatus.FROZEN:
            assert item.value is not None
            return item.value
    raise SystemExit(f"governance frozen value missing: {key}")


def _sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_pins() -> dict:
    """Refuse to execute unless the governed pins hold. No model call happens first."""
    problems = []
    cfg_sha = _sha(_CONFIG_PATH)
    arc_sha = _sha(_ARCHIVE_PATH)
    if cfg_sha != PINNED_CONFIG_SHA:
        problems.append(f"execution configuration sha {cfg_sha} != pinned {PINNED_CONFIG_SHA}")
    if arc_sha != PINNED_ARCHIVE_SHA:
        problems.append(f"pre-seal archive sha {arc_sha} != pinned {PINNED_ARCHIVE_SHA}")
    for rel in ("sanuvia-phase1/local_run002/llama_server_backend_run002.py",
                "sanuvia-phase1/src/sanuvia_phase1/qwen.py",
                "sanuvia-phase1/src/sanuvia_phase1/manifest.py",
                "sanuvia-phase1/src/sanuvia_phase1/validation.py",
                "sanuvia-phase1/src/sanuvia_phase1/prompts.py"):
        blob = subprocess.run(["git", "-C", str(_REPO), "show", f"{PINNED_COMMIT}:{rel}"],
                              capture_output=True, check=True).stdout
        live = (_REPO / rel).read_bytes()
        if hashlib.sha256(blob).hexdigest() != hashlib.sha256(live).hexdigest():
            problems.append(f"{rel} differs from pinned commit")
    if problems:
        for p in problems:
            print("PIN FAILURE:", p)
        raise SystemExit("governed pins do not hold — refusing to execute Case 001")
    return {"execution_configuration_sha256": cfg_sha, "preseal_archive_sha256": arc_sha}


def main() -> int:
    pins = _assert_pins()
    print("governed pins verified; proceeding to the single Case 001 execution")

    out_dir = _HERE / "evidence_case001"
    out_dir.mkdir(exist_ok=True)
    provenance_path = out_dir / "raw_calls.jsonl"
    if provenance_path.exists():
        raise SystemExit(f"{provenance_path} already exists — refusing to rerun Case 001")

    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(_REPO), capture_output=True, text=True
    ).stdout.strip()
    freeze_hash = governance.freeze_record_sha256()
    freeze_version = governance.FREEZE_RECORD_VERSION
    model_version = _frozen("model_artifact_version")
    artifact_sha = _frozen("artifact_sha256")
    llama_build = _frozen("llama_cpp_build")

    # Frozen config, carrying the verified artifact identity (as the preflight does).
    config = qwen_real_run_config(
        model_version=Maybe.available(model_version),
        artifact_id=Maybe.available(artifact_sha),
    )

    created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    run_id = "run-002"
    builder = RunManifestBuilder(
        run_id=run_id,
        created_at=created_at,
        git_commit_sha=git_sha,
        phase1_version=PHASE1_VERSION,
        mode="real",
        transcript=CASE_001_TRANSCRIPT,
        model_specs=config.specs(),
        governance_freeze_hash=freeze_hash,
    )

    backend = LlamaServerBackendRun002(
        BASE_URL,
        model_id="qwen3-4b",
        model_version=model_version,
        artifact_id=artifact_sha,
        llama_cpp_build=llama_build,
        context_window=8192,
        provenance_path=str(provenance_path),
    )
    # Frozen generation parameters exactly.
    params = GenerationParams(
        temperature=0.0, max_output_tokens=512, context_tokens=8192, seed=0, stop=()
    )
    client = QwenClient(backend, params, builder, retries=0)

    status = "completed"
    abort_error: str | None = None
    abort_tb: str | None = None
    tdr = None
    try:
        tdr = pipeline.run_transcript_demonstration(
            CASE_001_TRANSCRIPT,
            client.as_extractor(),
            {},   # appraisal_script unused: a real appraiser is injected
            {},   # hypothesis_catalogue unused with a real appraiser
            client.as_stateless_model(),
            client.as_transcript_model(),
            case_id="case-001",
            mode=pipeline.REAL,
            appraiser=client.as_appraiser(),
            config=config,
            on_interaction_start=client.begin_interaction,
        )
    except BaseException as exc:  # capture the exact frozen-policy failure; do NOT retry
        status = "aborted"
        abort_error = f"{type(exc).__name__}: {exc}"
        abort_tb = traceback.format_exc()

    manifest = builder.finalize()

    evidence = {
        "run_id": run_id,
        "execution_status": status,
        "abort_error": abort_error,
        "abort_traceback": abort_tb,
        "governed_pins": {
            "pinned_commit": PINNED_COMMIT,
            "head_commit_at_execution": git_sha,
            **pins,
        },
        "git_commit": git_sha,
        "governance_freeze_version": freeze_version,
        "governance_freeze_hash": freeze_hash,
        "model_artifact_version": model_version,
        "artifact_sha256": artifact_sha,
        "llama_cpp_build": llama_build,
        "generation_parameters": {
            "temperature": 0.0,
            "seed": 0,
            "context": 8192,
            "max_output_tokens": 512,
            "stop_sequences": None,
            "retries": 0,
        },
        "conditions_driven": ["sanuvia_persistent", "fm_stateless", "fm_transcript"],
        "single_execution": True,
        "retries_configured": 0,
        "manifest": manifest.to_payload(),
        "demonstration": report.transcript_to_payload(tdr) if tdr is not None else None,
    }
    (out_dir / "run002_case001_evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("STATUS:", status)
    if abort_error:
        print("ABORT:", abort_error)
    print("manifest.call_records:", len(manifest.call_records))
    print("per_interaction_status:", manifest.per_interaction_status)
    print("evidence:", out_dir / "run002_case001_evidence.json")
    print("raw_calls:", provenance_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
