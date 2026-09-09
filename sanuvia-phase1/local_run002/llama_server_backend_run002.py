"""LOCAL Run 002 execution plumbing — QwenBackend over llama.cpp (Option A, corrected).

Local-only execution plumbing. NOT part of the frozen protocol, NOT committed. It is a
Run-002 sibling of local_run001/llama_server_backend.py; the Run 001 adapter is left
untouched. The ONLY behavioural differences from Run 001 are the two runtime/template
controls the isolated investigation proved necessary to run Qwen3 in genuine
non-thinking mode, plus a passive integrity invariant:

  1. Each request carries ``chat_template_kwargs = {"enable_thinking": false}`` so the
     model's OWN, UNCHANGED Qwen3 template fires its non-thinking branch (injecting the
     empty ``<think>\\n\\n</think>`` scaffold into the PROMPT). The model then generates
     no reasoning and answers directly with JSON.
  2. The server is launched WITHOUT ``--reasoning-format none`` (the pure content parser
     that would echo the template's injected scaffold into ``message.content``). The
     default reasoning-aware parser assembles ``content`` as the model's actual answer.
  3. reasoning_content invariant (Step 5): the successful configuration produces NO
     reasoning_content. If the server ever returns a NON-EMPTY ``reasoning_content``, the
     call is treated as MALFORMED (raised as ``MalformedOutputError`` with the raw
     content preserved). This does NOT modify ``content``, does NOT strip ``<think>``,
     does NOT extract JSON, does NOT retry, does NOT sanitise. It only asserts the
     runtime invariant "enable_thinking=false => reasoning_content empty".

Prompt text, schema, validator, and generation parameters are unchanged. ``content`` is
returned verbatim; the EXISTING frozen validators decide success/malformed.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from sanuvia_phase1.failures import (
    BoundaryKind, MalformedOutputError, Maybe, ModelError, ModelTimeout,
)
from sanuvia_phase1.qwen import GenerationParams, QwenRuntimeInfo

# The single Run-002 template control. The model's own template reads this kwarg; no
# template file is overridden, so the embedded Qwen3 template is used UNCHANGED.
RUN002_CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}


@dataclass(frozen=True, slots=True)
class Run002Call:
    """Full result of one backend call (raw content + runtime metadata)."""

    content: str                 # message.content, verbatim
    reasoning_content: str | None  # message.reasoning_content, if the server exposed it
    raw_server_json: str
    elapsed_seconds: float
    request_body: dict


class LlamaServerBackendRun002:
    """Concrete Run-002 ``QwenBackend`` over local llama-server /v1/chat/completions."""

    def __init__(
        self,
        base_url: str,
        *,
        model_id: str,
        model_version: str,
        artifact_id: str,
        llama_cpp_build: str,
        context_window: int,
        provenance_path: str,
        timeout: float = 1800.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_id = model_id
        self._model_version = model_version
        self._artifact_id = artifact_id
        self._llama_cpp_build = llama_cpp_build
        self._context_window = context_window
        self._provenance_path = provenance_path
        self._timeout = timeout
        self._call_index = 0

    def describe(self) -> QwenRuntimeInfo:
        return QwenRuntimeInfo(
            backend_id=f"llama.cpp-server ({self._llama_cpp_build}) run002",
            model_id=self._model_id,
            model_version=Maybe.available(self._model_version),
            artifact_id=Maybe.available(self._artifact_id),
            context_window=self._context_window,
        )

    # --- frozen QwenBackend port -------------------------------------------------
    def generate(self, prompt: str, params: GenerationParams) -> str:
        """Port-conforming call: returns raw ``content`` verbatim.

        The reasoning_content invariant is NOT enforced here because this signature
        carries no BoundaryKind; callers that want the invariant recorded as
        MALFORMED_OUTPUT use ``generate_ex`` + ``enforce_reasoning_invariant`` inside a
        thunk that knows the boundary (see run002_gate1.py)."""
        return self.generate_ex(prompt, params).content

    # --- richer Run-002 call -----------------------------------------------------
    def generate_ex(self, prompt: str, params: GenerationParams) -> Run002Call:
        self._call_index += 1
        body: dict[str, object] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params.temperature,      # frozen: 0.0
            "seed": params.seed,                     # frozen: 0
            "n_predict": params.max_output_tokens,   # frozen: 512
            "stream": False,
            "chat_template_kwargs": dict(RUN002_CHAT_TEMPLATE_KWARGS),  # enable_thinking=false
        }
        if params.stop:  # frozen: none -> not set
            body["stop"] = list(params.stop)
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._base_url + "/v1/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw_server_response = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            elapsed = time.time() - started
            reason = getattr(exc, "reason", exc)
            self._log(prompt, body, None, error=f"{type(exc).__name__}: {reason}", elapsed=elapsed)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ModelTimeout(f"llama-server request timed out: {reason}") from exc
            raise ModelError(f"llama-server request failed: {reason}") from exc
        elapsed = time.time() - started

        try:
            payload = json.loads(raw_server_response)
        except json.JSONDecodeError as exc:
            self._log(prompt, body, raw_server_response, error=f"non-JSON server response: {exc}", elapsed=elapsed)
            raise ModelError(f"llama-server returned non-JSON: {exc}") from exc
        choices = payload.get("choices")
        if not choices:
            self._log(prompt, body, raw_server_response, error="response missing choices", elapsed=elapsed)
            raise ModelError(f"llama-server response missing choices: {raw_server_response[:300]}")
        message = choices[0].get("message", {})
        content = message.get("content")
        if content is None:
            self._log(prompt, body, raw_server_response, error="response missing message.content", elapsed=elapsed)
            raise ModelError("llama-server response missing message.content")
        reasoning_content = message.get("reasoning_content")
        self._log(prompt, body, raw_server_response, content=content,
                  reasoning_content=reasoning_content, elapsed=elapsed)
        return Run002Call(
            content=content,
            reasoning_content=reasoning_content,
            raw_server_json=raw_server_response,
            elapsed_seconds=elapsed,
            request_body=body,
        )

    @staticmethod
    def enforce_reasoning_invariant(call: Run002Call, boundary: BoundaryKind) -> str:
        """Runtime invariant (Step 5): enable_thinking=false => reasoning_content empty.

        Returns ``content`` verbatim when the invariant holds. Raises
        MalformedOutputError (raw content preserved) when the server returned a
        NON-EMPTY reasoning_content. No stripping / extraction / repair / retry."""
        rc = call.reasoning_content
        if rc is not None and rc.strip() != "":
            raise MalformedOutputError(
                boundary,
                "runtime invariant violated: reasoning_content non-empty under "
                "enable_thinking=false (server split reasoning off content)",
                raw=call.content,
            )
        return call.content

    def _log(
        self,
        prompt: str,
        body: dict[str, object],
        raw_server_response: str | None,
        *,
        content: str | None = None,
        reasoning_content: str | None = None,
        error: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        entry = {
            "call_index": self._call_index,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": round(elapsed, 3) if elapsed is not None else None,
            "endpoint": self._base_url + "/v1/chat/completions",
            "request_body": body,
            "raw_prompt": prompt,
            "raw_server_response": raw_server_response,
            "content": content,
            "reasoning_content": reasoning_content,
            "error": error,
        }
        with open(self._provenance_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
