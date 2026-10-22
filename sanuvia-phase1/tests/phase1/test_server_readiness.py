"""Server readiness — offline, no server, no inference, no Case 002.

Every backend here is a fake in this process. Nothing contacts a server, loads
a model, generates a token, touches the private fixture, or runs any part of
Stage 1.

The scenarios the authorisation asks for: a ready server, an unavailable one,
a misconfigured one, a malformed response, and the guarantee that readiness
never reaches the Stage 1 pipeline.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from sanuvia_phase1 import readiness
from sanuvia_phase1.failures import ModelError, ModelTimeout
from sanuvia_phase1.llama_server_backend import BackendCall
from sanuvia_phase1.preflight import BLOCKED, PASS, UNAVAILABLE
from sanuvia_phase1.qwen import GenerationParams


class _FakeProbe:
    """Stands in for the llama.cpp backend. Never contacts anything."""

    def __init__(
        self,
        *,
        content: str = '{"ready": true}',
        reasoning_content: str | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, GenerationParams]] = []
        self._content = content
        self._reasoning = reasoning_content
        self._raise = raise_exc

    def generate_ex(self, prompt: str, params: GenerationParams) -> BackendCall:
        self.calls.append((prompt, params))
        if self._raise is not None:
            raise self._raise
        return BackendCall(
            content=self._content,
            reasoning_content=self._reasoning,
            raw_server_json="{}",
            elapsed_seconds=0.01,
            request_body={},
        )


def _check(tmp_path: pathlib.Path, probe: _FakeProbe) -> readiness.ReadinessResult:
    return readiness.check_server_readiness(
        provenance_path=str(tmp_path / "probe.jsonl"), backend=probe
    )


def _status(result: readiness.ReadinessResult, name: str) -> str:
    return next(c.status for c in result.checks if c.name == name)


# --- 1. a ready server -------------------------------------------------------


def test_a_correctly_configured_server_is_ready(tmp_path: pathlib.Path) -> None:
    result = _check(tmp_path, _FakeProbe())

    assert result.overall == PASS
    assert result.blocked() == ()
    for name in (
        "server_reachable", "generation_completed",
        "no_thinking_scaffold_in_content", "reasoning_content_invariant",
        "strict_json_boundary_viable",
    ):
        assert _status(result, name) == PASS


def test_the_probe_uses_the_frozen_determinism_settings(
    tmp_path: pathlib.Path,
) -> None:
    """The probe must travel the same determinism path the run will."""
    probe = _FakeProbe()
    _check(tmp_path, probe)

    (_, params), = probe.calls
    assert params.temperature == 0.0
    assert params.seed == 0
    assert params.context_tokens == 8192


def test_the_probe_sends_no_case_content(tmp_path: pathlib.Path) -> None:
    """Synthetic only — no case material, no participant data."""
    probe = _FakeProbe()
    _check(tmp_path, probe)

    (prompt, _), = probe.calls
    assert prompt == readiness.PROBE_PROMPT
    for forbidden in ("participant-1", "participant-2", "relationship-1", "::P1"):
        assert forbidden not in prompt


# --- 2. an unavailable server ------------------------------------------------


@pytest.mark.parametrize(
    "exc",
    [ModelError("connection refused"), ModelTimeout("timed out"),
     RuntimeError("something unexpected")],
)
def test_an_unavailable_server_blocks(
    tmp_path: pathlib.Path, exc: Exception
) -> None:
    """Fail closed, whatever the failure mode."""
    result = _check(tmp_path, _FakeProbe(raise_exc=exc))

    assert result.overall == BLOCKED
    assert _status(result, "server_reachable") == BLOCKED


def test_unreachable_leaves_downstream_checks_unverifiable_not_passing(
    tmp_path: pathlib.Path,
) -> None:
    """The distinction that matters: unverifiable must never read as fine."""
    result = _check(tmp_path, _FakeProbe(raise_exc=ModelError("refused")))

    for name in (
        "generation_completed", "no_thinking_scaffold_in_content",
        "reasoning_content_invariant", "strict_json_boundary_viable",
    ):
        assert _status(result, name) == UNAVAILABLE
    assert result.overall == BLOCKED


# --- 3. a misconfigured server ----------------------------------------------


def test_a_think_scaffold_in_content_blocks(tmp_path: pathlib.Path) -> None:
    """The signature of --reasoning-format none: the scaffold reaches content."""
    result = _check(
        tmp_path, _FakeProbe(content='<think>\n\n</think>{"ready": true}')
    )

    assert result.overall == BLOCKED
    assert _status(result, "no_thinking_scaffold_in_content") == BLOCKED
    detail = next(
        c.detail for c in result.checks if c.name == "no_thinking_scaffold_in_content"
    )
    assert "--reasoning-format none" in detail


def test_non_empty_reasoning_content_blocks(tmp_path: pathlib.Path) -> None:
    """The backend's own invariant, checked before the run rather than during."""
    result = _check(
        tmp_path, _FakeProbe(reasoning_content="let me think about this")
    )

    assert result.overall == BLOCKED
    assert _status(result, "reasoning_content_invariant") == BLOCKED


def test_empty_reasoning_content_is_acceptable(tmp_path: pathlib.Path) -> None:
    """Absent and blank both satisfy the invariant."""
    for value in (None, "", "   "):
        result = _check(tmp_path, _FakeProbe(reasoning_content=value))
        assert _status(result, "reasoning_content_invariant") == PASS


# --- 4. a malformed response -------------------------------------------------


def test_non_json_content_blocks(tmp_path: pathlib.Path) -> None:
    """If the probe cannot parse, the strict validators would reject every reply."""
    result = _check(tmp_path, _FakeProbe(content="Sure! Here is your answer."))

    assert result.overall == BLOCKED
    assert _status(result, "strict_json_boundary_viable") == BLOCKED


def test_empty_content_blocks(tmp_path: pathlib.Path) -> None:
    result = _check(tmp_path, _FakeProbe(content="   "))

    assert result.overall == BLOCKED
    assert _status(result, "generation_completed") == BLOCKED


def test_a_single_failing_check_blocks_the_whole_result(
    tmp_path: pathlib.Path,
) -> None:
    """Readiness is all-or-nothing: PASS must mean every check passed."""
    result = _check(tmp_path, _FakeProbe(content="not json"))

    assert any(c.status == PASS for c in result.checks), "test is not meaningful"
    assert result.overall == BLOCKED


# --- 5. readiness never touches Stage 1 --------------------------------------


def test_readiness_never_invokes_the_stage_1_pipeline(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defining separation, enforced rather than asserted."""
    from sanuvia_phase1 import pipeline

    def _boom(*_a: object, **_k: object) -> object:
        raise AssertionError("readiness must not run the Stage 1 pipeline")

    monkeypatch.setattr(pipeline, "run_transcript_demonstration", _boom)
    monkeypatch.setattr(pipeline, "build_extracted_case", _boom)

    assert _check(tmp_path, _FakeProbe()).overall == PASS


def test_readiness_does_not_import_the_runner_or_the_fixture() -> None:
    """By import graph, not by assertion."""
    import ast

    source = pathlib.Path(readiness.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(a.name for a in node.names)

    assert not any("run003_stage1" in n for n in names)
    assert not any("case_002" in n for n in names)
    assert "identity_resolvers" not in str(names)


def test_readiness_creates_no_evidence_directory(tmp_path: pathlib.Path) -> None:
    """A failed readiness check must not look like a consumed attempt.

    If readiness created the runner's evidence directory, the repeat-execution
    guard would later refuse the real first attempt as though it were a repeat.
    """
    before = set(tmp_path.iterdir())
    _check(tmp_path, _FakeProbe(raise_exc=ModelError("refused")))
    after = set(tmp_path.iterdir())

    assert after == before, "readiness created files on failure"


def test_a_failed_readiness_check_does_not_block_a_later_real_attempt(
    tmp_path: pathlib.Path,
) -> None:
    """Readiness and the execution guard are independent."""
    from sanuvia_phase1 import run003_stage1

    evidence_dir = tmp_path / "ev"
    _check(tmp_path, _FakeProbe(raise_exc=ModelError("refused")))

    assert not evidence_dir.exists()
    # The guard is keyed on the directory, which readiness never creates.
    assert not any(p.name == "ev" for p in tmp_path.iterdir())
    assert run003_stage1.RUN_ID == "run-003-stage-1"


# --- reporting ---------------------------------------------------------------


def test_the_report_states_the_consequence_of_failure(
    tmp_path: pathlib.Path,
) -> None:
    rendered = readiness.render(_check(tmp_path, _FakeProbe(raise_exc=ModelError("x"))))

    assert "SERVER READINESS: BLOCKED" in rendered
    assert "must not be executed" in rendered
    assert "single authorised attempt" in rendered


def test_the_report_is_quiet_when_ready(tmp_path: pathlib.Path) -> None:
    rendered = readiness.render(_check(tmp_path, _FakeProbe()))

    assert "SERVER READINESS: PASS" in rendered
    assert "must not be executed" not in rendered


def test_the_configuration_check_is_described_as_inferred(
    tmp_path: pathlib.Path,
) -> None:
    """It cannot read the launch flags, and must not claim to.

    The passing detail has to say so, or a reader will take it as a direct
    verification of how the server was started.
    """
    result = _check(tmp_path, _FakeProbe())
    detail = next(
        c.detail for c in result.checks if c.name == "no_thinking_scaffold_in_content"
    )

    assert "inferred" in detail.lower()
    assert "not read from the server" in detail.lower()
