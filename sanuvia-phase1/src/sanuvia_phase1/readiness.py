"""Runtime server readiness — distinct from configuration preflight.

`preflight-real` answers *"is this machine configured and installed correctly?"*
It inspects configuration, registry hashes, the artifact on disk and the runtime
binary. It never starts a server and never generates a token, so a 17/17 PASS
says **nothing** about whether a server is running, how it was started, or
whether the strict-JSON boundary will work.

This module answers the other question: *"is the running server actually ready,
and configured the way the boundary requires?"*

WHAT IT PROVES
--------------

* a server answers at the configured address;
* it completes a generation and returns content;
* that content carries **no** ``<think>`` scaffold, which is the observable
  signature of the one configuration mistake that silently corrupts a run;
* ``reasoning_content`` came back empty, so the backend's invariant holds;
* the content parses as JSON, so the strict-JSON boundary is viable.

WHAT IT CANNOT PROVE
--------------------

**It cannot read the server's launch flags.** Nothing in the HTTP API exposes
them. The ``--reasoning-format none`` check is therefore an inference from
observed behaviour, not a direct reading of how the process was started: that
flag's pure content parser echoes the template's injected scaffold into
``content``, so scaffold in the content means the flag is almost certainly set,
and clean content is *consistent with* it being absent.

That is a real limitation and it is named rather than papered over. A server
could in principle behave correctly on one probe and not on the next; this is a
point-in-time check, not a guarantee about the run that follows.

It also proves nothing about Case 002, the fixture, R1, or the engine. It never
touches them.

WHICH ARTIFACT THE SERVER LOADED
--------------------------------

The behavioural probe alone cannot say which model answered. When the approved
identifiers are supplied (``approved_model_path``, ``approved_sha256``,
``approved_build``), readiness also records and checks the machine itself:

* the **launch command** of the process listening on the port, read from the
  operating system (``lsof`` + ``ps``) -- so ``--reasoning-format none`` is now
  checked directly, not only inferred, and the ``-m`` artifact is read;
* the server's own ``/props``: the **model path it loaded** and its
  **build** (``build_info``), plus the chat-template hash;
* the **SHA-256 of the approved artifact on disk**, recomputed.

Together these tie the probe's answer to the approved artifact and runtime.

SAFETY
------

The probe is a harmless synthetic request. No Case 002 content, no private
fixture, no participant data, no R1 path, no Stage 1 pipeline, and no evidence
directory. It cannot consume the single authorised execution attempt, because
it never touches the runner's repeat-execution guard.

Fails closed: unreachable, misconfigured, malformed or unverifiable all give
BLOCKED.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .failures import ModelError, ModelTimeout
from .llama_server_backend import BackendCall, LlamaServerBackend
from .preflight import BLOCKED, PASS, UNAVAILABLE, Check
from .qwen import GenerationParams

#: The address the runner uses by default.
DEFAULT_BASE_URL = "http://127.0.0.1:8080"

#: A harmless synthetic probe. Deliberately trivial, deliberately nothing to do
#: with any case: it asks for a tiny JSON object and nothing else.
PROBE_PROMPT = (
    "Respond with ONLY this JSON object and no other text:\n"
    '{"ready": true}'
)

#: The scaffold a mis-started server echoes into content.
THINK_SCAFFOLD = "<think>"


@dataclass(frozen=True, slots=True)
class ServerFacts:
    """What the machine itself says about the running server."""

    launch_command: str | None
    pid: int | None
    props_model_path: str | None
    props_build_info: str | None
    chat_template_sha256: str | None


def _http_get_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - local address
        data = json.loads(response.read().decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _launch_command_for_port(port: int) -> tuple[int | None, str | None]:
    """PID and full command line of the process LISTENING on ``port``."""
    try:
        pids = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout.split()
        if not pids:
            return None, None
        pid = int(pids[0])
        command = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout.strip()
        return pid, command or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None


def observe_server(
    base_url: str,
    *,
    http_get: Callable[[str], dict[str, object]] = _http_get_json,
    launch_command_for_port: Callable[[int], tuple[int | None, str | None]] = (
        _launch_command_for_port
    ),
) -> ServerFacts:
    """Read the launch command from the OS and the loaded model from ``/props``."""
    port = urlparse(base_url).port or 80
    pid, command = launch_command_for_port(port)
    try:
        props = http_get(base_url.rstrip("/") + "/props")
    except Exception:  # unreachable props is recorded as unknown, never as fine
        props = {}
    template = props.get("chat_template")
    return ServerFacts(
        launch_command=command,
        pid=pid,
        props_model_path=props.get("model_path") if isinstance(props.get("model_path"), str) else None,  # type: ignore[arg-type]
        props_build_info=props.get("build_info") if isinstance(props.get("build_info"), str) else None,  # type: ignore[arg-type]
        chat_template_sha256=(
            hashlib.sha256(template.encode("utf-8")).hexdigest()
            if isinstance(template, str) else None
        ),
    )


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_file(a: str | None, b: str) -> bool:
    return a is not None and os.path.realpath(a) == os.path.realpath(b)


def _model_arg(command: str) -> str | None:
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    for flag in ("-m", "--model"):
        if flag in argv and argv.index(flag) + 1 < len(argv):
            return argv[argv.index(flag) + 1]
    return None


def identity_checks(
    facts: ServerFacts,
    *,
    approved_model_path: str,
    approved_sha256: str,
    approved_build: str,
    approved_chat_template_sha256: str | None = None,
    digest_of: Callable[[str], str] = file_sha256,
) -> tuple[Check, ...]:
    """Tie the running server to the approved artifact and runtime."""
    checks: list[Check] = []
    command = facts.launch_command
    if command is None:
        checks.append(Check("launch_command_recorded", BLOCKED,
                            "no process found listening on the port; launch command unknown"))
    else:
        checks.append(Check("launch_command_recorded", PASS, f"pid {facts.pid}: {command}"))
        flat = " ".join(command.split())
        if "--reasoning-format none" in flat or "--reasoning-format=none" in flat:
            checks.append(Check("launch_flags_without_reasoning_format_none", BLOCKED,
                                "the server was started WITH --reasoning-format none"))
        else:
            checks.append(Check("launch_flags_without_reasoning_format_none", PASS,
                                "read from the launch command: --reasoning-format none absent"))
        model_arg = _model_arg(command)
        checks.append(Check(
            "launched_with_approved_artifact",
            PASS if _same_file(model_arg, approved_model_path) else BLOCKED,
            f"-m {model_arg} (approved: {approved_model_path})",
        ))

    checks.append(Check(
        "loaded_artifact_is_approved",
        PASS if _same_file(facts.props_model_path, approved_model_path) else BLOCKED,
        f"/props model_path {facts.props_model_path} (approved: {approved_model_path})",
    ))
    try:
        actual = digest_of(approved_model_path)
    except OSError as exc:
        checks.append(Check("artifact_digest_verified", BLOCKED, f"cannot read artifact: {exc}"))
    else:
        checks.append(Check(
            "artifact_digest_verified",
            PASS if actual == approved_sha256 else BLOCKED,
            f"sha256 {actual} (approved: {approved_sha256})",
        ))
    build_ok = facts.props_build_info is not None and all(
        part in facts.props_build_info for part in approved_build.split()
    )
    checks.append(Check(
        "runtime_build_matches", PASS if build_ok else BLOCKED,
        f"/props build_info {facts.props_build_info} (approved: {approved_build})",
    ))
    # ALWAYS RECORDED, never skipped.
    #
    # This check used to be appended only when an expected digest was supplied,
    # so omitting --chat-template-sha256 made it VANISH from the result: a run
    # with one fewer verification reported 11/11 and read as complete, while an
    # earlier run with the digest reported 12/12. A reader comparing the two
    # could not see that a check had gone missing rather than passed.
    #
    # An unsupplied expectation is now UNAVAILABLE, not absent. The count stays
    # constant, the observed digest is still recorded so it can be pinned
    # later, and -- because overall is PASS only when every check is PASS --
    # the gap blocks rather than passes silently.
    if approved_chat_template_sha256 is None:
        checks.append(Check(
            "chat_template_unchanged", UNAVAILABLE,
            f"no approved digest supplied, so the template could not be "
            f"verified; the server reports {facts.chat_template_sha256}",
        ))
    else:
        checks.append(Check(
            "chat_template_unchanged",
            PASS if facts.chat_template_sha256 == approved_chat_template_sha256 else BLOCKED,
            f"/props chat_template sha256 {facts.chat_template_sha256} "
            f"(approved: {approved_chat_template_sha256})",
        ))
    return tuple(checks)


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    checks: tuple[Check, ...]
    facts: ServerFacts | None = field(default=None)

    @property
    def overall(self) -> str:
        """PASS only when every check passes. Anything else blocks execution."""
        return PASS if all(c.status == PASS for c in self.checks) else BLOCKED

    def blocked(self) -> tuple[Check, ...]:
        return tuple(c for c in self.checks if c.status != PASS)


def _probe_params() -> GenerationParams:
    """Frozen generation settings, so the probe exercises the real path.

    ``max_output_tokens`` is the one deliberate departure: the probe needs a
    few tokens, not the frozen 1536, and generating the full budget would
    make readiness needlessly slow. Temperature and seed stay as frozen so
    the probe runs through the same determinism settings the run will.
    """
    return GenerationParams(
        temperature=0.0, max_output_tokens=64, context_tokens=8192, seed=0, stop=()
    )


def check_server_readiness(
    *,
    base_url: str = DEFAULT_BASE_URL,
    provenance_path: str,
    model_version: str = "readiness-probe",
    artifact_id: str = "readiness-probe",
    llama_cpp_build: str = "readiness-probe",
    backend: object | None = None,
    approved_model_path: str | None = None,
    approved_sha256: str | None = None,
    approved_build: str | None = None,
    approved_chat_template_sha256: str | None = None,
    observe: Callable[[str], ServerFacts] | None = None,
    digest_of: Callable[[str], str] = file_sha256,
) -> ReadinessResult:
    """Probe the running server once and report readiness.

    ``backend`` overrides the real one for offline testing. A real check passes
    ``None`` and gets the committed llama.cpp backend, so the probe travels the
    same code path the run will — including the ``enable_thinking`` control and
    the ``reasoning_content`` invariant.
    """
    checks: list[Check] = []
    facts: ServerFacts | None = None
    if approved_model_path and approved_sha256 and approved_build:
        facts = (observe or observe_server)(base_url)
        checks.extend(identity_checks(
            facts,
            approved_model_path=approved_model_path,
            approved_sha256=approved_sha256,
            approved_build=approved_build,
            approved_chat_template_sha256=approved_chat_template_sha256,
            digest_of=digest_of,
        ))
    probe = backend if backend is not None else LlamaServerBackend(
        base_url,
        model_id="qwen3-4b",
        model_version=model_version,
        artifact_id=artifact_id,
        llama_cpp_build=llama_cpp_build,
        context_window=8192,
        provenance_path=provenance_path,
    )

    # 1. reachable, and completes a generation.
    call: BackendCall | None = None
    try:
        call = probe.generate_ex(PROBE_PROMPT, _probe_params())  # type: ignore[attr-defined]
    except ModelTimeout as exc:
        checks.append(Check("server_reachable", BLOCKED, f"timed out: {exc}"))
    except ModelError as exc:
        checks.append(Check("server_reachable", BLOCKED, f"unreachable or failing: {exc}"))
    except Exception as exc:  # never swallow: an unexpected failure still blocks
        checks.append(
            Check("server_reachable", BLOCKED, f"{type(exc).__name__}: {exc}")
        )

    if call is None:
        # Fail closed. Everything downstream is unverifiable without a response,
        # and "unverifiable" must never read as "fine".
        for name in (
            "generation_completed",
            "no_thinking_scaffold_in_content",
            "reasoning_content_invariant",
            "strict_json_boundary_viable",
        ):
            checks.append(Check(name, UNAVAILABLE, "no response: not verifiable"))
        return ReadinessResult(tuple(checks), facts)

    checks.append(Check("server_reachable", PASS, f"responded at {base_url}"))

    content = call.content
    if not content.strip():
        checks.append(Check("generation_completed", BLOCKED, "empty content returned"))
    else:
        checks.append(
            Check("generation_completed", PASS, f"{len(content)} characters returned")
        )

    # 2. The configuration signature. See the module docstring: this is an
    #    inference from observed behaviour, not a reading of the launch flags.
    if THINK_SCAFFOLD in content:
        checks.append(Check(
            "no_thinking_scaffold_in_content", BLOCKED,
            "content carries a <think> scaffold, which is what "
            "--reasoning-format none produces; the server is very likely "
            "started with it and the strict-JSON boundary will fail",
        ))
    else:
        checks.append(Check(
            "no_thinking_scaffold_in_content", PASS,
            "no <think> scaffold in content, consistent with the server being "
            "started WITHOUT --reasoning-format none (inferred from behaviour, "
            "not read from the server's flags)",
        ))

    # 3. The backend's own invariant: enable_thinking=false => no reasoning_content.
    reasoning = call.reasoning_content
    if reasoning is not None and reasoning.strip():
        checks.append(Check(
            "reasoning_content_invariant", BLOCKED,
            "non-empty reasoning_content under enable_thinking=false: the "
            "server split reasoning off content, which the backend treats as "
            "malformed output",
        ))
    else:
        checks.append(Check(
            "reasoning_content_invariant", PASS,
            "reasoning_content empty, as enable_thinking=false requires",
        ))

    # 4. The boundary every real call depends on.
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        checks.append(Check(
            "strict_json_boundary_viable", BLOCKED,
            f"probe response is not parseable JSON ({exc}); the strict "
            f"validators would reject every reply",
        ))
    else:
        checks.append(
            Check("strict_json_boundary_viable", PASS, "probe response parsed as JSON")
        )

    return ReadinessResult(tuple(checks), facts)


def render(result: ReadinessResult) -> str:
    """A short report. Mirrors the preflight's shape so both read alike."""
    lines = [f"SERVER READINESS: {result.overall}"]
    for check in result.checks:
        lines.append(f"  {check.status:11} {check.name}: {check.detail}")
    if result.overall != PASS:
        lines.append("")
        lines.append(
            "Readiness is not established. Stage 1 must not be executed: a run "
            "started now would consume the single authorised attempt against a "
            "server that is not known to be correctly configured."
        )
    return "\n".join(lines)
