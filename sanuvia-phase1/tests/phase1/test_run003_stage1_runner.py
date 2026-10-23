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


def _label_in(prompt: str) -> str | None:
    """The first request-scoped participant label offered in a prompt."""
    import re

    m = re.search(r"\S+::P\d+", prompt)
    return m.group(0) if m else None


class _FakeBackend:
    """Records every prompt; answers with valid-shaped JSON. No network."""

    def __init__(
        self, *, fail_on: int | None = None, fail_on_baseline_call: int | None = None
    ) -> None:
        self.prompts: list[str] = []
        self.params: list[GenerationParams] = []
        self.appraisals = 0
        self.baseline_calls = 0
        self._fail_on = fail_on
        self._fail_on_baseline_call = fail_on_baseline_call

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
        # Dispatch order matters: the APPRAISAL prompt also contains
        # "PARTICIPANT LABELS", so it must be matched on its own discriminator
        # first. Getting this wrong fed extraction JSON to the appraiser, which
        # then proposed nothing and every interaction merely held.
        if "matched_ref" in prompt:                 # identity resolution (R1)
            return json.dumps({"outcome": "distinct_new", "matched_ref": None,
                               "rationale": "synthetic", "confidence": 0.5})
        if "CURRENT HYPOTHESES" in prompt:          # appraisal
            self.appraisals += 1
            subject = _label_in(prompt) or "p1"
            statement = ("she withdraws when the evening runs late"
                         if self.appraisals == 1
                         else "she withdraws when the evening runs late, midweek")
            return json.dumps({"supports": [], "contradicts": [], "proposals": [{
                "local_ref": f"c{self.appraisals}", "statement": statement,
                "signature": {"subject": subject, "claim_class": "behaviour_pattern",
                              "stance": "open", "temporal_scope": None},
            }]})
        if "PARTICIPANT LABELS" in prompt:          # extraction
            label = _label_in(prompt)
            return json.dumps({"evidence": [{
                "observation": "a synthetic observed event",
                "evidence_class": "behavioural",
                "reliability": 0.8, "classification_confidence": 0.9,
                "provenance_confidence": 0.9, "text_span": None,
                "role": "account", "subject_kind": "participant",
                "subject": label,
            }]})
        # Anything else is an FM baseline call (both baselines share the shape).
        self.baseline_calls += 1
        if (self._fail_on_baseline_call is not None
                and self.baseline_calls >= self._fail_on_baseline_call):
            raise ModelError("synthetic backend failure during a baseline")
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


ROSTER = ("participant-1", "participant-2")


def _run(tmp_path: pathlib.Path, backend: _FakeBackend, name: str = "ev") -> dict[str, object]:
    return run003_stage1.execute(
        roster=ROSTER,
        case_id="case-synthetic",
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
        backend=_FakeBackend(), roster=ROSTER,
        transcript=_synthetic_transcript(),
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
        backend=_FakeBackend(), roster=ROSTER,
        transcript=_synthetic_transcript(),
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
        backend=_FakeBackend(), roster=ROSTER,
        transcript=_synthetic_transcript(),
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


# --- the public module must not depend on private material -------------------


def test_the_module_imports_without_the_private_fixture() -> None:
    """A public checkout has no Case 002 fixture — it lives in private custody.

    A module-level import of it would make this module unimportable there, and
    would make the public test suite depend on private material being on disk.
    The import is deferred, so importing the runner must not touch it.
    """
    import ast

    tree = ast.parse(pathlib.Path(run003_stage1.__file__).read_text(encoding="utf-8"))
    top_level = [
        n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
    ]
    modules = {
        n.module for n in top_level if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not any("case_002" in m for m in modules), (
        "the Case 002 fixture is imported at module level; it must be deferred"
    )


def test_a_missing_fixture_fails_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """If the fixture genuinely is absent, say so plainly rather than raising a
    bare ModuleNotFoundError from deep inside the runner."""
    def _boom() -> tuple[object, str, tuple[str, ...]]:
        raise RuntimeError(
            "the Case 002 fixture is not importable here. It is held in private "
            "custody and is not part of this repository"
        )

    monkeypatch.setattr(run003_stage1, "_load_case_002", _boom)
    with pytest.raises(RuntimeError, match="private custody"):
        run003_stage1.execute(
            evidence_dir=tmp_path / "ev2", base_url="http://127.0.0.1:0",
            model_version="v", artifact_id="/a", llama_cpp_build="b", pins=PINS,
            backend=_FakeBackend(),
        )


# --- the connected reasoning path, with real synthetic evidence --------------


def test_extraction_appraisal_and_r1_are_all_exercised(tmp_path: pathlib.Path) -> None:
    """The connected path, not a sequence of no-ops.

    The fake backend returns real evidence and real proposals, so extraction
    feeds appraisal, appraisal founds a lineage, and a second non-exact
    proposal reaches §2 G case 4 where R1 adjudicates.
    """
    backend = _FakeBackend()
    evidence = _run(tmp_path, backend)

    assert evidence["execution_status"] == "completed"
    joined = "\n".join(backend.prompts)
    assert "PARTICIPANT LABELS" in joined, "extraction never ran"
    assert "CURRENT HYPOTHESES" in joined, "appraisal never ran"
    assert "matched_ref" in joined, "R1 never ran — no case-4 candidate reached it"


def test_the_extraction_audit_is_saved_on_success(tmp_path: pathlib.Path) -> None:
    """Successful output must say what was extracted, with its standing."""
    _run(tmp_path, _FakeBackend())

    saved = json.loads((tmp_path / "ev" / "execution_evidence.json").read_text())
    audit = saved["extraction_audit"]
    assert audit, "no extraction audit recorded"
    observed = [r for r in audit if r.get("evidence_count")]
    assert observed, "no interaction recorded any evidence"
    standing = observed[0]["evidence"][0]["standing"]
    assert standing["role"] == "account"
    assert standing["source_kind"] == "participant"
    assert standing["source_id"] in ROSTER
    assert standing["subject_id"] in ROSTER


def test_a_later_failure_preserves_completed_extraction(
    tmp_path: pathlib.Path,
) -> None:
    """A failure after extraction must not discard what already succeeded."""
    # Fail once extraction and the first appraisal have gone through.
    backend = _FakeBackend(fail_on=3)
    evidence = _run(tmp_path, backend)

    assert evidence["execution_status"] == "aborted"
    saved = json.loads((tmp_path / "ev" / "execution_evidence.json").read_text())
    assert saved["extraction_audit"], "completed extraction was lost on failure"
    assert saved["abort_error"] and saved["abort_traceback"]


def test_a_later_failure_still_records_the_calls_that_happened(
    tmp_path: pathlib.Path,
) -> None:
    backend = _FakeBackend(fail_on=3)
    _run(tmp_path, backend)

    assert len(backend.prompts) == 3, "calls before the failure were not made"
    assert (tmp_path / "ev" / "execution_evidence.json").is_file()


def test_a_setup_failure_leaves_no_evidence_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that never started must not claim the directory.

    Otherwise the already-exists guard would refuse the real first attempt as
    though it were a repeat.
    """
    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("synthetic setup failure")

    monkeypatch.setattr(run003_stage1, "build_runner", _boom)
    target = tmp_path / "ev-setup"

    with pytest.raises(RuntimeError, match="synthetic setup failure"):
        run003_stage1.execute(
            evidence_dir=target, base_url="http://127.0.0.1:0", model_version="v",
            artifact_id="/a", llama_cpp_build="b", pins=PINS,
            transcript=_synthetic_transcript(), backend=_FakeBackend(),
            roster=ROSTER, case_id="c",
        )

    assert not target.exists(), "an empty evidence directory was left behind"


def test_after_a_setup_failure_a_real_attempt_is_still_possible(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of cleaning up: the authorised attempt is not burned."""
    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("synthetic setup failure")

    monkeypatch.setattr(run003_stage1, "build_runner", _boom)
    target = tmp_path / "ev-retry"
    with pytest.raises(RuntimeError):
        run003_stage1.execute(
            evidence_dir=target, base_url="http://127.0.0.1:0", model_version="v",
            artifact_id="/a", llama_cpp_build="b", pins=PINS,
            transcript=_synthetic_transcript(), backend=_FakeBackend(),
            roster=ROSTER, case_id="c",
        )
    monkeypatch.undo()

    evidence = _run(tmp_path, _FakeBackend(), name="ev-retry")
    assert evidence["execution_status"] == "completed"


def test_the_recording_proxy_adds_no_model_call(tmp_path: pathlib.Path) -> None:
    """Capturing the audit must not cost a second extraction pass."""
    backend = _FakeBackend()
    _run(tmp_path, backend)

    # The appraisal prompt also carries participant labels, so extraction is
    # identified by its own discriminator rather than by that shared section.
    extraction_calls = sum(
        1 for p in backend.prompts
        if "TEXT:" in p and "CURRENT HYPOTHESES" not in p and "matched_ref" not in p
    )
    speaking_turns = sum(
        1 for i in _synthetic_transcript().interactions if i.text.strip()
    )
    assert extraction_calls == speaking_turns, "extraction ran more than once per turn"


def test_the_r1_spec_records_identity_hashes_not_extraction_ones(
    tmp_path: pathlib.Path,
) -> None:
    """The recorded R1 provenance must name the identity artifacts.

    Inheriting the extraction spec's ``extra_params`` recorded the extraction
    hashes against the identity boundary — an audit that looks complete while
    naming the wrong artifact.
    """
    from sanuvia_phase1 import prompts

    config, _, _ = run003_stage1.build_runner(
        base_url="http://127.0.0.1:0", model_version="v", artifact_id="/a",
        llama_cpp_build="b", provenance_path=tmp_path / "p.jsonl",
        backend=_FakeBackend(), roster=ROSTER, transcript=_synthetic_transcript(),
    )
    r1 = dict(config.identity_resolution.extra_params)   # type: ignore[attr-defined]

    assert r1["prompt_sha256"] == prompts.prompt(prompts.IDENTITY_PROMPT_ID).content_sha256
    assert r1["schema_sha256"] == prompts.schema(prompts.IDENTITY_SCHEMA_ID).content_sha256
    assert r1["prompt_sha256"] != prompts.prompt(prompts.EXTRACTION_PROMPT_ID).content_sha256
    # and the extraction spec is untouched
    ex = dict(config.extraction.extra_params)            # type: ignore[attr-defined]
    assert ex["prompt_sha256"] == prompts.prompt(prompts.EXTRACTION_PROMPT_ID).content_sha256


def test_the_command_line_entry_point_is_connected() -> None:
    """``python -m ...`` must actually run, not exit silently."""
    source = pathlib.Path(run003_stage1.__file__).read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source, "module has no entry point"

    with pytest.raises(SystemExit) as exc:
        run003_stage1.main(["--help"])
    assert exc.value.code == 0


# --- progress preserved as it is produced ------------------------------------

def _progress(tmp_path: pathlib.Path, name: str = "ev") -> list[dict[str, object]]:
    path = tmp_path / name / "progress.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_a_baseline_failure_keeps_the_completed_sanuvia_trajectory(
    tmp_path: pathlib.Path,
) -> None:
    """The reviewed case: Sanuvia completes, then the first baseline call fails.

    Before, only extraction and the call records survived. Now the finished
    condition is on disk with every step, as it was produced.
    """
    backend = _FakeBackend(fail_on_baseline_call=1)
    evidence = _run(tmp_path, backend)

    assert evidence["execution_status"] == "aborted"
    assert "during a baseline" in str(evidence["abort_error"])
    assert evidence["completed_conditions"] == ["sanuvia_persistent"]
    assert evidence["steps_completed"] == {"sanuvia_persistent": 3}

    saved = json.loads(
        (tmp_path / "ev" / "completed_conditions" / "sanuvia_persistent.json").read_text()
    )
    assert [r["seq_label"] for r in saved] == ["seq-1", "seq-2", "seq-3"]
    steps = _progress(tmp_path)
    assert [(s["condition"], s["position"]) for s in steps] == [
        ("sanuvia_persistent", 0), ("sanuvia_persistent", 1), ("sanuvia_persistent", 2),
    ]
    # The saved evidence file says the same, and no complete report is claimed.
    on_disk = json.loads((tmp_path / "ev" / "execution_evidence.json").read_text())
    assert on_disk["completed_conditions"] == ["sanuvia_persistent"]
    assert not (tmp_path / "ev" / "trajectories.json").exists()


def test_a_failure_inside_a_baseline_keeps_its_finished_steps(
    tmp_path: pathlib.Path,
) -> None:
    """Partial progress of the condition that failed is kept too."""
    evidence = _run(tmp_path, _FakeBackend(fail_on_baseline_call=2))

    assert evidence["execution_status"] == "aborted"
    assert evidence["completed_conditions"] == ["sanuvia_persistent"]
    assert evidence["steps_completed"] == {"sanuvia_persistent": 3, "fm_stateless": 1}
    stateless = [s for s in _progress(tmp_path) if s["condition"] == "fm_stateless"]
    assert len(stateless) == 1
    record = stateless[0]["record"]
    assert isinstance(record, dict) and record["seq_label"] == "seq-1"
    assert not (tmp_path / "ev" / "completed_conditions" / "fm_stateless.json").exists()


def test_a_completed_run_saves_each_condition_as_the_final_report_does(
    tmp_path: pathlib.Path,
) -> None:
    """The observers record exactly what the pipeline returns: same records."""
    evidence = _run(tmp_path, _FakeBackend())

    assert evidence["execution_status"] == "completed"
    assert evidence["completed_conditions"] == [
        "sanuvia_persistent", "fm_stateless", "fm_transcript",
    ]
    final = json.loads((tmp_path / "ev" / "trajectories.json").read_text())
    for condition, records in final.items():
        saved = json.loads(
            (tmp_path / "ev" / "completed_conditions" / f"{condition}.json").read_text()
        )
        assert saved == records, f"{condition}: saved progress differs from the report"
    assert len(_progress(tmp_path)) == sum(len(r) for r in final.values())


def test_the_observers_add_no_model_call(tmp_path: pathlib.Path) -> None:
    """Saving progress must not cost a single extra call on the one attempt."""
    with_observers = _FakeBackend()
    _run(tmp_path, with_observers, name="a")

    without = _FakeBackend()
    config, client, _ = run003_stage1.build_runner(
        base_url="http://127.0.0.1:0", model_version="v", artifact_id="/a",
        llama_cpp_build="b", provenance_path=tmp_path / "b.jsonl",
        transcript=_synthetic_transcript(), backend=without, roster=ROSTER,
    )
    from sanuvia_phase1 import pipeline

    pipeline.run_transcript_demonstration(
        _synthetic_transcript(), client.as_extractor(permitted_participants=ROSTER),
        {}, {}, client.as_stateless_model(), client.as_transcript_model(),
        case_id="case-synthetic", mode=pipeline.REAL, appraiser=client.as_appraiser(),
        config=config,  # type: ignore[arg-type]
        identity_resolver=client.as_identity_resolver(),
        on_interaction_start=client.begin_interaction,
    )
    assert with_observers.prompts == without.prompts


# --- setup failure: recorded, attempt not consumed ----------------------------

def test_a_setup_failure_is_recorded_beside_the_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(**_kwargs: object) -> object:
        raise RuntimeError("synthetic setup failure")

    monkeypatch.setattr(run003_stage1, "build_runner", _boom)
    backend = _FakeBackend()
    target = tmp_path / "ev-setup"
    with pytest.raises(RuntimeError, match="synthetic setup failure"):
        run003_stage1.execute(
            evidence_dir=target, base_url="http://127.0.0.1:0", model_version="v",
            artifact_id="/a", llama_cpp_build="b", pins=PINS,
            transcript=_synthetic_transcript(), backend=backend,
            roster=ROSTER, case_id="c",
        )

    assert not target.exists(), "the attempt must not be consumed"
    records = list(tmp_path.glob("ev-setup.setup-failure-*.json"))
    assert len(records) == 1, "no setup-failure record was kept"
    record = json.loads(records[0].read_text())
    assert record["outcome"] == "setup_failure"
    assert record["error"] == "RuntimeError: synthetic setup failure"
    assert "synthetic setup failure" in record["traceback"]
    assert record["backend_calls"] == 0
    assert record["model_call_occurred"] is False
    assert record["governed_attempt_consumed"] is False
    assert record["evidence_dir_removed"] is True
    assert backend.prompts == []

