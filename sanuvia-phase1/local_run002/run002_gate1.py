"""Run 002 — FINAL sacrificial Gate 1, driven through the ACTUAL Case 001 execution path.

Drives the integrated Run-002 backend (llama_server_backend_run002.py) through the
FROZEN extraction + baseline prompts over a SYNTHETIC (non-Case-001) input, using the
EXACT execution path the real Case 001 harness uses:

    QwenClient.extraction_client() / .baseline_client()
        -> QwenClient._generate_recorded  (FROZEN adapter)
            -> call_with_recording        (FROZEN manifest recording)
                -> LlamaServerBackendRun002.generate()   <-- invariant enforced here
                    -> generate_ex() + enforce_reasoning_invariant()

The reasoning_content invariant therefore runs where Case 001 will run it, not in a
runner-local thunk. The raw ``message.content`` returned by that path is then passed
UNCHANGED to the EXISTING frozen validators (json.loads boundary +
validate_extraction / validate_baseline) — exactly as ExternalEvidenceExtractor and
capture.parse_baseline_turn do. No stripping / extraction / sanitisation / repair /
retry / prompt modification. Exactly one generation attempt per boundary. Case 001 is
never used.

Server MUST be launched with the model's OWN embedded Qwen3 template (no
--chat-template-file override) and WITHOUT --reasoning-format none, e.g.:

  llama-server -m <gguf> -c 8192 --host 127.0.0.1 --port <port> --jinja \
    --no-webui -np 1 --no-warmup
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path("/Users/elite/Documents/sanuvia")
_PHASE1 = _REPO / "sanuvia-phase1"
for _p in (str(_PHASE1 / "src"), str(_PHASE1), str(_REPO / "src"), str(pathlib.Path(__file__).resolve().parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1.conditions._prompt import INSTRUCTION as BASE_INSTR
from sanuvia_phase1.conditions._prompt import SYSTEM as BASE_SYS
from sanuvia_phase1.evidence_extractors.external import INSTRUCTION as EX_INSTR
from sanuvia_phase1.evidence_extractors.external import SYSTEM as EX_SYS
from sanuvia_phase1.evidence_extractors.external import ExtractionRequest
from sanuvia_phase1.failures import BoundaryKind, MalformedOutputError
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.ports import LmRequest
from sanuvia_phase1.qwen import GenerationParams, QwenClient
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction
from sanuvia_phase1.validation import validate_baseline, validate_extraction

from llama_server_backend_run002 import LlamaServerBackendRun002

# SYNTHETIC sacrificial input — deliberately NOT Case 001 content.
SYNTHETIC_TEXT = "Person A: I finished the quarterly report yesterday and emailed it to the team."

MODEL_SHA = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
TEMPLATE_SHA = "57f1fd00f0013a2be96aa79b857391f27e23df5b5f847072b524c897e24d0361"
BUILD = "build 10721 (commit 8e53fcefd)"
# Frozen generation params (unchanged from Run 001).
PARAMS = GenerationParams(temperature=0.0, max_output_tokens=512, context_tokens=8192,
                          seed=0, stop=())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_transcript() -> Transcript:
    """A one-interaction SYNTHETIC transcript — never Case 001."""
    return Transcript(
        "synthetic-run002-gate1",
        SubjectId("s-synth"),
        shared_space_id("synth"),
        (TranscriptInteraction(1, "seq-1", SYNTHETIC_TEXT),),
    )


def _client_for(qc: QwenClient, boundary: BoundaryKind, model_role: str):
    """The SAME client factories the three conditions use — no Gate-1-specific path."""
    if boundary is BoundaryKind.EVIDENCE_EXTRACTION:
        return qc.extraction_client()
    return qc.baseline_client(boundary, model_role)


def _run(name, boundary_label, boundary_kind, request, validator, val_boundary,
         backend, provenance_path, out):
    # --- the ACTUAL Case 001 execution path -----------------------------------
    builder = RunManifestBuilder(
        run_id=f"run002-gate1-{name}",
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        git_commit_sha="uncommitted-gate1", phase1_version="0.1.0", mode="real",
        transcript=_synthetic_transcript(),
    )
    qc = QwenClient(backend, PARAMS, builder, retries=0)  # frozen adapter, retries=0
    qc.begin_interaction(1, "seq-1")
    client = _client_for(qc, boundary_kind, boundary_label)

    invariant_ok, invariant_error, raw = True, "", None
    try:
        raw = client(request)  # exactly one attempt; invariant enforced inside generate()
    except MalformedOutputError as exc:
        invariant_ok = False
        invariant_error = exc.detail
        raw = exc.raw  # verbatim message.content, preserved by the invariant
    manifest = builder.finalize()
    record = manifest.call_records[0]

    # --- complete backend response, straight from the provenance log ----------
    prov = [json.loads(line) for line in
            pathlib.Path(provenance_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    last = prov[-1]
    server_json_text = last["raw_server_response"]
    server = json.loads(server_json_text)
    choice = server["choices"][0]
    message = choice.get("message", {})
    message_content = message.get("content")
    reasoning_content = message.get("reasoning_content")
    finish_reason = choice.get("finish_reason")
    usage = server.get("usage")

    # --- the frozen validators, on the UNCHANGED message.content --------------
    validator_input = raw
    passed_unchanged = (validator_input == message_content)
    try:
        json.loads(validator_input)
        json_loads_ok = True
    except Exception:  # noqa: BLE001
        json_loads_ok = False
    try:
        if val_boundary is None:
            validator(validator_input)
        else:
            validator(validator_input, val_boundary)
        validator_pass, validator_error = True, ""
    except MalformedOutputError as exc:
        validator_pass, validator_error = False, exc.detail

    has_think = ("<think>" in validator_input) or ("</think>" in validator_input)
    rc_nonempty = bool(reasoning_content is not None and reasoning_content.strip() != "")

    evidence = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "boundary": boundary_label,
        "execution_path": (
            "QwenClient.{}() -> _generate_recorded -> call_with_recording -> "
            "LlamaServerBackendRun002.generate() -> generate_ex + "
            "enforce_reasoning_invariant".format(
                "extraction_client" if boundary_kind is BoundaryKind.EVIDENCE_EXTRACTION
                else "baseline_client")
        ),
        "same_path_as_case_001": True,
        "input_prompt": last["raw_prompt"],
        "input_prompt_sha256": _sha(last["raw_prompt"]),
        "request_body_sent": last["request_body"],
        "enable_thinking": False,

        # complete API response
        "server_json": server_json_text,
        "server_json_sha256": _sha(server_json_text),
        "finish_reason": finish_reason,
        "usage": usage,

        # message.content / reasoning_content
        "message_content": message_content,
        "message_content_sha256": _sha(message_content) if message_content is not None else None,
        "reasoning_content": reasoning_content,
        "reasoning_content_present": reasoning_content is not None,
        "reasoning_content_nonempty": rc_nonempty,
        "reasoning_content_invariant_ok": invariant_ok,
        "reasoning_content_invariant_error": invariant_error,

        # exact validator input + results
        "validator_input": validator_input,
        "validator_input_sha256": _sha(validator_input) if validator_input is not None else None,
        "message_content_passed_unchanged_to_validator": passed_unchanged,
        "json_loads_succeeds": json_loads_ok,
        "strict_validator_pass": validator_pass,
        "strict_validator_error": validator_error,
        "contains_think": has_think,

        # recorded boundary outcome (frozen manifest)
        "call_record_status": record.status,
        "call_record_attempts": record.attempts,
        "call_record_raw_response_sha256": (
            _sha(record.raw_response) if record.raw_response is not None else None),
        "per_interaction_status": dict(manifest.per_interaction_status),

        "no_stripping": True, "no_extraction": True, "no_sanitisation": True,
        "no_repair": True, "no_retry": True, "no_prompt_modification": True,
        "attempts": record.attempts,
        "elapsed_seconds": round(last["elapsed_seconds"], 3),
        "runtime": {"model_sha256": MODEL_SHA, "template_sha256": TEMPLATE_SHA,
                    "llama_cpp_build": BUILD, "params": {
                        "temperature": 0.0, "seed": 0, "n_predict": 512,
                        "context": 8192, "stop": None, "retries": 0}},
    }
    gate_pass = ((not has_think) and json_loads_ok and validator_pass and invariant_ok
                 and not rc_nonempty and passed_unchanged
                 and record.status == "success" and record.attempts == 1)
    evidence["gate1_boundary_pass"] = gate_pass
    (out / f"gate1_{name}_raw.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "gate1_all_calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(evidence, ensure_ascii=False) + "\n")
    print(f"[{name}] think={has_think} json_loads={json_loads_ok} "
          f"validator={'PASS' if validator_pass else 'FAIL'} "
          f"reasoning_content_nonempty={rc_nonempty} "
          f"status={record.status} attempts={record.attempts} "
          f"content_unchanged={passed_unchanged} "
          f"elapsed={evidence['elapsed_seconds']}s -> {'PASS' if gate_pass else 'FAIL'}")
    print("  validator input (verbatim, first 200 chars): "
          + validator_input[:200].replace("\n", "\\n"))
    return gate_pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("gate1_all_calls.jsonl", "gate1_backend_provenance.jsonl"):
        if (out / stale).exists():
            (out / stale).unlink()

    provenance_path = str(out / "gate1_backend_provenance.jsonl")
    backend = LlamaServerBackendRun002(
        f"http://127.0.0.1:{args.port}",
        model_id="Qwen3-4B-Q4_K_M", model_version="bc640142", artifact_id=MODEL_SHA,
        llama_cpp_build=BUILD, context_window=8192,
        provenance_path=provenance_path, timeout=600.0)

    r_ext = _run("extraction", "evidence_extraction", BoundaryKind.EVIDENCE_EXTRACTION,
                 ExtractionRequest(system=EX_SYS, transcript_text=SYNTHETIC_TEXT,
                                   instruction=EX_INSTR),
                 validate_extraction, None, backend, provenance_path, out)
    r_base = _run("baseline", "stateless_baseline", BoundaryKind.STATELESS_BASELINE,
                  LmRequest(system=BASE_SYS, context=f"turn-1: {SYNTHETIC_TEXT}",
                            instruction=BASE_INSTR),
                  validate_baseline, BoundaryKind.STATELESS_BASELINE, backend,
                  provenance_path, out)
    overall = r_ext and r_base
    print(f"\nGATE 1 OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
