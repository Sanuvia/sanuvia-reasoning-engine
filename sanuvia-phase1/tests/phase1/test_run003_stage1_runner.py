"""Run 003 Stage 1 runner — offline verification, no inference.

Everything here runs against a **synthetic transcript** and a **fake backend**
in this process. No model is loaded, no token is generated, no server is
contacted, and no Case 002 content reaches any of it.

What these cover, as the authorisation requires:

* R1 wiring — that the resolver is constructed, reaches the recorded client,
  and that its calls are recorded under their own boundary;
* failure recording — that a governed stop is captured as evidence rather than
  swallowed, and never retried;
* prevention of accidental repeat execution;
* that the approved roster, generation settings and pins are what the runner
  actually uses;
* that the reference module stays out of the execution path.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1 import run003_stage1
from sanuvia_phase1.failures import BoundaryKind, Maybe, ModelError
from sanuvia_phase1.identity_resolvers.external import ExternalIdentityResolver
from sanuvia_phase1.qwen import GenerationParams, QwenRuntimeInfo
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

PINS = run003_stage1.Pins(
    frozen_engine_commit="0" * 40,
    custody_commit="1" * 40,
    fixture_sha256="a" * 64,
    reference_sha256="b" * 64,
    tests_sha256="c" * 64,
)


class _FakeBackend:
    """Records every prompt; answers with valid-shaped JSON. No network."""

    def __init__(self, *, fail_on: int | None = None) -> None:
        self.prompts: list[str] = []
        self.params: list[GenerationParams] = []
        self._fail_on = fail_on

    def describe(self) -> QwenRuntimeInfo:
        return QwenRuntimeInfo(
            backend_id="fake-offline", model_id="qwen3-4b",
            model_version=Maybe.available("fake"), artifact_id=Maybe.available("/fake"),
            context_window=8192,
        )

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.prompts.append(prompt)
        self.params.append(params)
        if self._fail_on is not None and len(self.prompts) >= self._fail_on:
            raise ModelError("synthetic backend failure")
        if "PARTICIPANT LABELS" in prompt:          # extraction
            return json.dumps({"evidence": []})
        if "outcome" in prompt and "matched_ref" in prompt:   # identity resolution
            return json.dumps({"outcome": "distinct_new", "matched_ref": None,
                               "rationale": "synthetic", "confidence": 0.5})
        if "CURRENT HYPOTHESES" in prompt:          # appraisal
            return "{}"
        return json.dumps({"best_explanations": [], "competing_hypotheses_held": [],
                           "question_asked": None, "continuity_claims": []})


def _synthetic_transcript() -> Transcript:
    """Synthetic, not Case 002: two speaking turns and one empty hold."""
    return Transcript(
        "t-synthetic", SubjectId("subject-synthetic"), shared_space_id("synthetic"),
        (
            TranscriptInteraction(1, "seq-1", "a synthetic line", "participant-1"),
            TranscriptInteraction(2, "seq-2", "", None),
            TranscriptInteraction(3, "seq-3", "another synthetic line", "participant-2"),
        ),
    )


def _run(tmp_path: pathlib.Path, backend: _FakeBackend, name: str = "ev") -> dict[str, object]:
    return run003_stage1.execute(
        evidence_dir=tmp_path / name,
        base_url="http://127.0.0.1:0",      # never contacted; backend is injected
        model_version="fake-version",
        artifact_id="/fake/artifact.gguf",
        llama_cpp_build="fake build",
        pins=PINS,
        transcript=_synthetic_transcript(),
        backend=backend,
    )


# --- wiring ------------------------------------------------------------------


def test_the_runner_wires_the_approved_roster_and_settings(tmp_path: pathlib.Path) -> None:
    config, client, _ = run003_stage1.build_runner(
        base_url="http://127.0.0.1:0", model_version="v", artifact_id="/a",
        llama_cpp_build="b", provenance_path=tmp_path / "p.jsonl",
        backend=_FakeBackend(),
    )
    assert config.participants == ("participant-1", "participant-2")  # type: ignore[attr-defined]
    assert config.extraction.temperature == 0.0                      # type: ignore[attr-defined]
    assert config.extraction.seed.value == "0"                       # type: ignore[attr-defined]
    assert config.extraction.max_output_tokens == 512                # type: ignore[attr-defined]
    assert config.extraction.context_window == 8192                  # type: ignore[attr-defined]


def test_r1_is_configured_with_its_own_model_spec(tmp_path: pathlib.Path) -> None:
    """A configured resolver needs its boundary spec, or the REAL guard refuses."""
    config, _, _ = run003_stage1.build_runner(
        base_url="http://127.0.0.1:0", model_version="v", artifact_id="/a",
        llama_cpp_build="b", provenance_path=tmp_path / "p.jsonl",
        backend=_FakeBackend(),
    )
    spec = config.identity_resolution                                # type: ignore[attr-defined]
    assert spec is not None
    assert spec.role == "identity_resolution"
    assert spec.prompt_id == "identity.r1.bounded.v1"
    assert spec.schema_id == "schema.identity.v1"
    assert len(config.specs()) == 5                                  # type: ignore[attr-defined]


def test_the_client_builds_a_real_bounded_resolver(tmp_path: pathlib.Path) -> None:
    _, client, _ = run003_stage1.build_runner(
        base_url="http://127.0.0.1:0", model_version="v", artifact_id="/a",
        llama_cpp_build="b", provenance_path=tmp_path / "p.jsonl",
        backend=_FakeBackend(),
    )
    resolver = client.as_identity_resolver()

    assert isinstance(resolver, ExternalIdentityResolver)
    assert resolver.resolver_id == "identity.r1.bounded.v1"


def test_the_identity_boundary_has_its_own_recording_kind() -> None:
    """R1 must not be recorded as appraisal: one interaction can cross both."""
    kinds = {k.value for k in BoundaryKind}
    assert {"identity_resolution", "evidence_appraisal"} <= kinds
    assert len(kinds) == len(list(BoundaryKind)), "a boundary value is duplicated"


def test_the_identity_prompt_carries_only_resolution_scoped_refs() -> None:
    from sanuvia_phase1.identity_resolvers.external import (
        INSTRUCTION, SYSTEM, CandidateRef, IdentityResolutionPrompt,
    )
    from sanuvia_phase1.qwen import compose_identity_prompt

    rendered = compose_identity_prompt(IdentityResolutionPrompt(
        system=SYSTEM, candidate_statement="candidate", candidate_subject="req::P1",
        candidate_claim_class="behaviour_pattern", candidate_stance="open",
        candidate_temporal_scope=None,
        existing=(CandidateRef("C1", "prior"),), instruction=INSTRUCTION,
    ))
    assert "C1" in rendered
    assert "hypothesis-" not in rendered and "hyp-" not in rendered


# --- execution, failure recording, no retry ----------------------------------


def test_a_run_writes_evidence_and_records_the_pins(tmp_path: pathlib.Path) -> None:
    evidence = _run(tmp_path, _FakeBackend())

    assert evidence["pins"] == {
        "frozen_engine_commit": PINS.frozen_engine_commit,
        "custody_commit": PINS.custody_commit,
        "fixture_sha256": PINS.fixture_sha256,
        "reference_sha256": PINS.reference_sha256,
        "tests_sha256": PINS.tests_sha256,
    }
    assert evidence["roster"] == ["participant-1", "participant-2"]
    assert (tmp_path / "ev" / "execution_evidence.json").is_file()


def test_a_backend_failure_is_captured_as_evidence_not_swallowed(
    tmp_path: pathlib.Path,
) -> None:
    """A governed stop must leave a complete record, not an empty directory."""
    evidence = _run(tmp_path, _FakeBackend(fail_on=1))

    assert evidence["execution_status"] == "aborted"
    assert evidence["abort_error"] is not None
    assert evidence["abort_traceback"] is not None
    written = json.loads((tmp_path / "ev" / "execution_evidence.json").read_text())
    assert written["execution_status"] == "aborted"
    assert written["abort_error"]


def test_a_failure_is_not_retried(tmp_path: pathlib.Path) -> None:
    """``retries=0``: the first failure is the outcome."""
    backend = _FakeBackend(fail_on=1)
    _run(tmp_path, backend)

    assert len(backend.prompts) == 1, "the failed call was retried"


# --- single execution --------------------------------------------------------


def test_a_second_execution_into_the_same_directory_is_refused(
    tmp_path: pathlib.Path,
) -> None:
    """One authorised attempt. A repeat must not overwrite or append."""
    _run(tmp_path, _FakeBackend())

    with pytest.raises(FileExistsError, match="not authorised"):
        _run(tmp_path, _FakeBackend())


def test_the_refusal_happens_before_any_backend_call(tmp_path: pathlib.Path) -> None:
    """The guard must fire before the model is touched, not after."""
    _run(tmp_path, _FakeBackend())
    second = _FakeBackend()

    with pytest.raises(FileExistsError):
        _run(tmp_path, second)
    assert second.prompts == [], "a repeat attempt reached the backend"


# --- isolation ---------------------------------------------------------------


def test_the_runner_never_imports_the_reference_module() -> None:
    import ast

    source = pathlib.Path(run003_stage1.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(a.name for a in node.names)

    assert not any("case_002_reference" in n for n in names)
    assert "case_002_reference" not in source


def test_generation_settings_are_the_frozen_ones(tmp_path: pathlib.Path) -> None:
    """What the backend is actually handed, not what the config declares."""
    backend = _FakeBackend()
    _run(tmp_path, backend)

    assert backend.params, "no call was made"
    for p in backend.params:
        assert p.temperature == 0.0
        assert p.seed == 0
        assert p.max_output_tokens == 512
        assert p.context_tokens == 8192
