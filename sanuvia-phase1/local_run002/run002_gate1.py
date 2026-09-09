"""Run 002 — FINAL sacrificial Gate 1 (integrated backend, corrected Option A).

Drives the integrated Run-002 backend (llama_server_backend_run002.py) through the
FROZEN extraction + baseline prompts over a SYNTHETIC (non-Case-001) input, enforces
the reasoning_content runtime invariant, and passes the raw content UNCHANGED to the
EXISTING frozen validators (json.loads boundary + validate_extraction /
validate_baseline). No stripping / extraction / sanitisation / repair / retry / prompt
modification. Exactly one generation attempt per boundary. Case 001 is never used.

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

from sanuvia_phase1.conditions._prompt import INSTRUCTION as BASE_INSTR
from sanuvia_phase1.conditions._prompt import SYSTEM as BASE_SYS
from sanuvia_phase1.evidence_extractors.external import INSTRUCTION as EX_INSTR
from sanuvia_phase1.evidence_extractors.external import SYSTEM as EX_SYS
from sanuvia_phase1.evidence_extractors.external import ExtractionRequest
from sanuvia_phase1.failures import BoundaryKind, MalformedOutputError
from sanuvia_phase1.ports import LmRequest
from sanuvia_phase1.qwen import (
    GenerationParams, compose_baseline_prompt, compose_extraction_prompt,
)
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


def _run(name, boundary_label, boundary_kind, prompt, validator, val_boundary,
         backend, out):
    call = backend.generate_ex(prompt, PARAMS)  # exactly one attempt
    # Runtime invariant: reasoning_content must be empty (Step 5). Returns content
    # verbatim; raises MalformedOutputError (raw preserved) if violated.
    invariant_ok = True
    invariant_error = ""
    try:
        raw = backend.enforce_reasoning_invariant(call, boundary_kind)
    except MalformedOutputError as exc:
        invariant_ok = False
        invariant_error = exc.detail
        raw = call.content  # preserved verbatim for evidence; still passed to validator below
    raw_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        json.loads(raw)
        json_loads_ok = True
    except Exception:  # noqa: BLE001
        json_loads_ok = False
    try:
        if val_boundary is None:
            validator(raw)
        else:
            validator(raw, val_boundary)
        validator_pass, validator_error = True, ""
    except MalformedOutputError as exc:
        validator_pass, validator_error = False, exc.detail
    has_think = ("<think>" in raw) or ("</think>" in raw)
    rc = call.reasoning_content
    record = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "boundary": boundary_label,
        "input_prompt": prompt,
        "request_body_sent": call.request_body,
        "enable_thinking": False,
        "raw_response": raw,                         # message.content, verbatim
        "raw_response_sha256": raw_sha,
        "server_json": call.raw_server_json,
        "reasoning_content_present": rc is not None,
        "reasoning_content_nonempty": bool(rc is not None and rc.strip() != ""),
        "reasoning_content_invariant_ok": invariant_ok,
        "reasoning_content_invariant_error": invariant_error,
        "json_loads_succeeds": json_loads_ok,
        "strict_validator_pass": validator_pass,
        "strict_validator_error": validator_error,
        "contains_think": has_think,
        "no_stripping": True, "no_extraction": True, "no_sanitisation": True,
        "no_repair": True, "no_retry": True, "no_prompt_modification": True,
        "attempts": 1,
        "elapsed_seconds": round(call.elapsed_seconds, 3),
        "runtime": {"model_sha256": MODEL_SHA, "template_sha256": TEMPLATE_SHA,
                    "llama_cpp_build": BUILD, "params": {
                        "temperature": 0.0, "seed": 0, "n_predict": 512,
                        "context": 8192, "stop": None, "retries": 0}},
    }
    gate_pass = ((not has_think) and json_loads_ok and validator_pass
                 and invariant_ok and not record["reasoning_content_nonempty"])
    record["gate1_boundary_pass"] = gate_pass
    (out / f"gate1_{name}_raw.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "gate1_all_calls.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[{name}] think={has_think} json_loads={json_loads_ok} "
          f"validator={'PASS' if validator_pass else 'FAIL'} "
          f"reasoning_content_nonempty={record['reasoning_content_nonempty']} "
          f"attempts=1 elapsed={record['elapsed_seconds']}s -> {'PASS' if gate_pass else 'FAIL'}")
    print("  raw (verbatim, first 200 chars): " + raw[:200].replace("\n", "\\n"))
    return gate_pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("gate1_all_calls.jsonl",):
        if (out / stale).exists():
            (out / stale).unlink()

    backend = LlamaServerBackendRun002(
        f"http://127.0.0.1:{args.port}",
        model_id="Qwen3-4B-Q4_K_M", model_version="bc640142", artifact_id=MODEL_SHA,
        llama_cpp_build=BUILD, context_window=8192,
        provenance_path=str(out / "gate1_backend_provenance.jsonl"), timeout=600.0)

    ext_prompt = compose_extraction_prompt(
        ExtractionRequest(system=EX_SYS, transcript_text=SYNTHETIC_TEXT, instruction=EX_INSTR))
    base_prompt = compose_baseline_prompt(
        LmRequest(system=BASE_SYS, context=f"turn-1: {SYNTHETIC_TEXT}", instruction=BASE_INSTR))

    r_ext = _run("extraction", "evidence_extraction", BoundaryKind.EVIDENCE_EXTRACTION,
                 ext_prompt, validate_extraction, None, backend, out)
    r_base = _run("baseline", "stateless_baseline", BoundaryKind.STATELESS_BASELINE,
                  base_prompt, validate_baseline, BoundaryKind.STATELESS_BASELINE, backend, out)
    overall = r_ext and r_base
    print(f"\nGATE 1 OVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
