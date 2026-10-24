"""Concrete ``QwenBackend`` over a local llama.cpp server.

Committed execution plumbing. A behaviour-preserving copy of the Run 002
backend, which is protected evidence and is left untouched. The Run 002 file
was deliberately uncommitted; this one is committed so the executed code
carries a commit reference and a hash, which pre-registration requires.

CHANGED: identifier names only -- LlamaServerBackendRun002 -> LlamaServerBackend,
Run002Call -> BackendCall, RUN002_CHAT_TEMPLATE_KWARGS -> CHAT_TEMPLATE_KWARGS,
and the ``run002`` marker inside ``backend_id`` -> ``local``.

NOT CHANGED: any behaviour. The request body, the template control, the
invariant, the error typing and the provenance log are the Run 002 logic.
That is deliberate and load-bearing.

WHY THE BEHAVIOUR MUST NOT DRIFT

Run 002 had to solve Qwen3 emitting ``<think>`` reasoning into a strict-JSON
boundary. Two controls fixed it, and both are preserved exactly:

1. every request carries ``chat_template_kwargs={"enable_thinking": false}``,
   so the model's own unchanged template fires its non-thinking branch;
2. the server must run WITHOUT ``--reasoning-format none``, whose pure content
   parser would echo the injected scaffold back into ``content``.

A third control, the ``reasoning_content`` invariant, asserts at runtime that
the first two held: a non-empty ``reasoning_content`` is a governed
MALFORMED_OUTPUT carrying the verbatim content. It does not strip, extract,
repair or retry.

Rewriting this from scratch would risk silently reintroducing the bug Run 002
spent a run discovering. Copying it is the lower-risk option.

``content`` is returned verbatim; the existing frozen validators decide success
or malformed. No prompt, schema, validator or generation parameter is touched.
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
CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}


class ReasoningInvariantViolation(MalformedOutputError, ModelError):
    """The reasoning_content invariant failed: a MALFORMED_OUTPUT, typed to survive
    the FROZEN port unchanged.

    Dual inheritance is deliberate and is the whole reason the invariant is *visible*
    in the real Case 001 path. Two frozen call sites decide the recorded status:

      * ``QwenClient._generate_recorded``'s thunk (qwen.py) re-raises ``ModelError``
        unchanged but wraps EVERY other exception into a plain ``ModelError`` — a bare
        ``MalformedOutputError`` would therefore be downgraded to ``model_error``;
      * ``call_with_recording`` (manifest.py) tests ``except MalformedOutputError``
        BEFORE ``except ModelError``.

    Being both, this exception passes the thunk with its type intact and is then
    recorded as ``CallStatus.MALFORMED_OUTPUT`` with ``raw`` (the verbatim
    ``message.content``) preserved and no retry — without editing any frozen file.

    ``boundary`` is ``None`` when raised from ``generate()``, whose port signature
    carries no ``BoundaryKind``; the authoritative boundary in the manifest is the one
    ``call_with_recording`` was given for that call.
    """

    def __init__(
        self, boundary: BoundaryKind | None, detail: str, raw: str | None = None
    ) -> None:
        super().__init__(boundary, detail, raw)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class BackendCall:
    """Full result of one backend call (raw content + runtime metadata)."""

    content: str                 # message.content, verbatim
    reasoning_content: str | None  # message.reasoning_content, if the server exposed it
    raw_server_json: str
    elapsed_seconds: float
    request_body: dict[str, object]


class LlamaServerBackend:
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
            backend_id=f"llama.cpp-server ({self._llama_cpp_build}) local",
            model_id=self._model_id,
            model_version=Maybe.available(self._model_version),
            artifact_id=Maybe.available(self._artifact_id),
            context_window=self._context_window,
        )

    # --- frozen QwenBackend port -------------------------------------------------
    def generate(self, prompt: str, params: GenerationParams) -> str:
        """Port-conforming call used by the REAL Case 001 harness — invariant enforced.

        This is the method ``QwenClient._generate_recorded`` calls for all three
        conditions, so the reasoning_content invariant is enforced HERE, through the
        very same ``generate_ex()`` + ``enforce_reasoning_invariant()`` mechanism the
        sacrificial Gate 1 runner uses. There is no second implementation and no
        condition-specific path.

        The complete backend response is preserved: ``generate_ex`` has already written
        the full server JSON (content, reasoning_content, finish reason, usage) to the
        provenance log before this returns or raises, and a violation carries the
        verbatim ``message.content`` as ``raw``.

        On success ``message.content`` is returned UNCHANGED for the existing frozen
        validator. No stripping, no ``<think>`` removal, no JSON extraction, no
        sanitisation, no repair, no retry."""
        return self.enforce_reasoning_invariant(self.generate_ex(prompt, params))

    # --- richer Run-002 call -----------------------------------------------------
    def generate_ex(self, prompt: str, params: GenerationParams) -> BackendCall:
        self._call_index += 1
        body: dict[str, object] = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params.temperature,      # frozen: 0.0
            "seed": params.seed,                     # frozen: 0
            "n_predict": params.max_output_tokens,   # frozen: 1536
            "stream": False,
            "chat_template_kwargs": dict(CHAT_TEMPLATE_KWARGS),  # enable_thinking=false
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
        return BackendCall(
            content=content,
            reasoning_content=reasoning_content,
            raw_server_json=raw_server_response,
            elapsed_seconds=elapsed,
            request_body=body,
        )

    @staticmethod
    def enforce_reasoning_invariant(
        call: BackendCall, boundary: BoundaryKind | None = None
    ) -> str:
        """Runtime invariant (Step 5): enable_thinking=false => reasoning_content empty.

        The SINGLE implementation of the invariant, shared by the port-conforming
        ``generate()`` (the real Case 001 path) and by the sacrificial Gate 1 runner.

        Returns ``content`` verbatim when the invariant holds. Raises
        ``ReasoningInvariantViolation`` — a ``MalformedOutputError`` recorded as
        MALFORMED_OUTPUT, raw content preserved — when the server returned a NON-EMPTY
        reasoning_content. No stripping / extraction / repair / retry.

        ``boundary`` is optional: ``generate()``'s port signature carries none, and the
        boundary written to the manifest is the one ``call_with_recording`` holds."""
        rc = call.reasoning_content
        if rc is not None and rc.strip() != "":
            raise ReasoningInvariantViolation(
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
