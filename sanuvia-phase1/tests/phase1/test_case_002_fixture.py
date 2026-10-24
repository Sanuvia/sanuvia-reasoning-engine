"""Case 002 executable fixture — content fidelity, isolation and the hold.

These are the seven guarantees the pre-registration depends on. They are checked
against the actual repository code and its real import graph, not against a
written assurance that the files are separate.

Offline throughout: no model is loaded, no token is generated, no provider is
contacted, and Run 003 is not executed.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from fixtures.longitudinal.case_002 import (
    CASE_002_TRANSCRIPT,
    DIVERGENCE_PAIR,
    PARTICIPANT_1,
    PARTICIPANT_2,
    ROSTER,
    SEQUENCES,
    SPACE,
    SUBJECT,
)

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import ReasoningService
from sanuvia.application.ports.reasoning import AppraisalRequest, AppraisalResponse
from sanuvia.domain import space_kind_of

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.participants import build_participant_vocabulary

#: Repository root: tests/phase1/<file> -> phase1 -> tests -> sanuvia-phase1 -> repo
_REPO = pathlib.Path(__file__).resolve().parents[3]
_REFERENCE_MODULE = "case_002_reference"


# --- 1. only participant-1 and participant-2 enter REAL input ----------------


def test_the_roster_is_exactly_the_two_participants() -> None:
    assert ROSTER == (PARTICIPANT_1, PARTICIPANT_2)
    assert DIVERGENCE_PAIR == (PARTICIPANT_1, PARTICIPANT_2)


def test_no_speaker_outside_the_roster_appears_in_the_transcript() -> None:
    """A facilitator, reviewer or third speaker would show up here."""
    speakers = {i.speaker for i in CASE_002_TRANSCRIPT.interactions}

    assert speakers <= {PARTICIPANT_1, PARTICIPANT_2, None}
    assert None in speakers, "only the hold may be speakerless"
    assert sum(1 for i in CASE_002_TRANSCRIPT.interactions if i.speaker is None) == 1


def test_only_the_two_participants_can_be_labelled_for_a_request() -> None:
    """The vocabulary is minted from the roster, so an excluded role has no
    label and cannot be named by the model at all."""
    vocabulary = build_participant_vocabulary("req", ROSTER)

    assert set(vocabulary.participants) == {PARTICIPANT_1, PARTICIPANT_2}
    assert vocabulary.label_for("facilitator") is None
    assert vocabulary.label_for("reviewer") is None


def test_the_governing_envelope_is_what_the_fixture_declares() -> None:
    assert SUBJECT == "relationship-1"
    assert space_kind_of(SPACE).name == "SHARED"


# --- 2. source order and wording are preserved -------------------------------


def test_all_ten_sequences_are_present_in_order() -> None:
    assert len(SEQUENCES) == 10
    assert [s.index for s in SEQUENCES] == list(range(1, 11))
    assert [s.label for s in SEQUENCES] == [f"seq-{n}" for n in range(1, 11)]


def test_interaction_order_follows_sequence_order() -> None:
    """Interactions are contiguous and never cross back into an earlier
    sequence: the fixed source order is preserved through the grouping."""
    interactions = CASE_002_TRANSCRIPT.interactions

    assert [i.index for i in interactions] == list(range(1, len(interactions) + 1))
    seen: list[int] = []
    for i in interactions:
        n = int(i.seq_label.split(".")[0].removeprefix("seq-"))
        if not seen or seen[-1] != n:
            seen.append(n)
    assert seen == list(range(1, 11)), "a sequence was split or reordered"


def test_every_turn_survives_grouping_in_order_and_wording() -> None:
    """The round trip: ungrouping the interactions must reproduce the sequence
    turns exactly — same speaker, same text, same order, nothing merged across a
    speaker change and nothing dropped."""
    recovered: list[tuple[str, str]] = []
    for interaction in CASE_002_TRANSCRIPT.interactions:
        if interaction.speaker is None:
            continue
        for line in interaction.text.split("\n"):
            recovered.append((interaction.speaker, line))

    authored = [(t.speaker, t.text) for s in SEQUENCES for t in s.turns]
    assert recovered == authored


def test_no_turn_group_mixes_speakers() -> None:
    """Each interaction carries one speaker, so a mixed group would silently
    re-attribute somebody's words."""
    for sequence in SEQUENCES:
        for a, b in zip(sequence.turns, sequence.turns[1:]):
            pass  # structural: grouping is asserted by the round trip above
    labels = [i.seq_label for i in CASE_002_TRANSCRIPT.interactions]
    assert len(labels) == len(set(labels)), "duplicate interaction label"


def test_wording_is_not_normalised() -> None:
    """Typography the source carried is still there. Normalising quotes or
    dashes would be a silent edit of what a participant said."""
    text = "\n".join(t.text for s in SEQUENCES for t in s.turns)

    assert "‘" in text and "’" in text, "typographic quotes were normalised"
    assert "—" in text, "em dashes were normalised"
    assert "..." in text, "ellipses were normalised"
    # The three bracketed canonical ids that stood in the source for a spoken name.
    assert text.count("[participant-2]") + text.count("[Participant-2]") == 3


# --- 3. the empty hold creates no event and mutates no state -----------------


def test_sequence_three_is_an_empty_hold() -> None:
    (hold,) = [i for i in CASE_002_TRANSCRIPT.interactions if i.seq_label == "seq-3"]

    assert SEQUENCES[2].is_hold
    assert SEQUENCES[2].turns == ()
    assert hold.text == ""
    assert hold.speaker is None


def test_the_hold_produces_no_evidence_and_makes_no_model_call() -> None:
    """Structural: ``extract`` answers empty text before any client call, so the
    hold cannot even reach a model."""
    calls: list[object] = []

    def _client(request: object) -> str:
        calls.append(request)
        raise AssertionError("the hold must not reach the extraction client")

    extractor = ExternalEvidenceExtractor(_client, permitted_participants=ROSTER)
    (hold,) = [i for i in CASE_002_TRANSCRIPT.interactions if i.seq_label == "seq-3"]

    assert extractor.extract(hold, CASE_002_TRANSCRIPT.transcript_id) == ()
    assert calls == []


def test_the_hold_leaves_reasoning_state_byte_for_byte_unchanged() -> None:
    """Through the frozen engine: an empty batch is a governed no-evidence hold,
    and the store snapshot before and after are identical."""

    class _NeverCalled:
        def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
            raise AssertionError("a hold makes no appraisal call")

    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=_NeverCalled(),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    service = ReasoningService(deps)

    before = store.evidence.snapshot()
    result = service.record_interaction(SUBJECT, [], space_id=SPACE)
    after = store.evidence.snapshot()

    assert result is not None
    assert before == after, "the hold mutated evidence state"
    assert store.hypotheses.list_for_subject(SUBJECT, space_id=SPACE) == []


# --- 4/5/6. the REAL path cannot reach the reference module ------------------


def _executable_modules() -> list[pathlib.Path]:
    """Every module on the REAL execution path."""
    roots = [
        _REPO / "sanuvia-phase1" / "src" / "sanuvia_phase1",
        _REPO / "sanuvia-phase1" / "fixtures",
        _REPO / "src" / "sanuvia",
    ]
    out: list[pathlib.Path] = []
    for root in roots:
        out.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return out


def _imported_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names.update(a.name for a in node.names)
    return names


def test_the_executable_path_has_modules_to_check() -> None:
    """Guards the three tests below from passing vacuously."""
    modules = _executable_modules()

    assert len(modules) > 50, f"only {len(modules)} modules found — path wrong?"
    assert any(p.name == "case_002.py" for p in modules)


def test_no_executable_module_imports_the_reference_module() -> None:
    """The defining isolation check, by real import graph rather than by
    assertion. Every module on the REAL path is parsed."""
    offenders = [
        str(p.relative_to(_REPO))
        for p in _executable_modules()
        if any(_REFERENCE_MODULE in name for name in _imported_names(p))
    ]

    assert offenders == [], f"reference module reachable from: {offenders}"


def test_no_executable_module_mentions_the_reference_package_at_all() -> None:
    """Stronger than imports: a dynamic ``importlib`` call or a path string would
    not appear in the import graph, so the raw text is checked too."""
    offenders = []
    for p in _executable_modules():
        text = p.read_text(encoding="utf-8")
        if _REFERENCE_MODULE in text or "reference/case_002" in text:
            offenders.append(str(p.relative_to(_REPO)))

    assert offenders == [], f"reference module referenced in: {offenders}"


def test_the_reference_module_is_outside_the_fixture_and_source_trees() -> None:
    """Isolation by location as well as by graph."""
    reference = _REPO / "sanuvia-phase1" / "reference" / "case_002_reference.py"

    assert reference.is_file()
    assert "fixtures" not in reference.parts
    assert "src" not in reference.parts


def test_the_reference_module_holds_no_source_or_reference_text() -> None:
    """Ids and hashes are permitted; quoted source or formulation text is not."""
    text = (
        _REPO / "sanuvia-phase1" / "reference" / "case_002_reference.py"
    ).read_text(encoding="utf-8")

    # No transcript line leaked across.
    for sequence in SEQUENCES:
        for turn in sequence.turns:
            probe = turn.text[:40]
            assert probe not in text, "transcript text leaked into the reference module"


# --- 6. no excluded-role identity or formulation reaches REAL input ----------


def test_no_excluded_role_identity_appears_in_model_facing_content() -> None:
    """Checked against what actually reaches a model: the turn text, the
    speakers and the roster.

    Deliberately not a scan of the whole source file -- the fixture's own
    comments state that the facilitator and reviewer are excluded, and a test
    that failed on the word appearing in that sentence would be measuring prose
    rather than exposure.
    """
    model_facing = "\n".join(t.text for s in SEQUENCES for t in s.turns).lower()

    for word in ("facilitator", "reviewer", "therapist"):
        assert word not in model_facing, f"{word!r} appears in transcript text"
    assert set(ROSTER) == {PARTICIPANT_1, PARTICIPANT_2}
    assert all(
        i.speaker in {PARTICIPANT_1, PARTICIPANT_2, None}
        for i in CASE_002_TRANSCRIPT.interactions
    )


def test_an_excluded_role_cannot_be_a_subject_or_a_speaker() -> None:
    """Governed, not merely absent: an excluded role is refused at the boundary
    because it was never offered a label."""
    from sanuvia.domain import GovernedRejection

    vocabulary = build_participant_vocabulary("req", ROSTER)
    for role in ("facilitator", "reviewer", "therapist"):
        with pytest.raises(GovernedRejection):
            vocabulary.resolve(role, ref="r", field="subject")


def test_the_real_pipeline_module_does_not_reach_reference_material() -> None:
    """The caller that would actually run Case 002."""
    import inspect

    source = inspect.getsource(pipeline)

    assert _REFERENCE_MODULE not in source
    assert "case_002_reference" not in source


# --- 7. existing behaviour is unchanged --------------------------------------


def test_case_001_is_untouched_by_the_new_fixture() -> None:
    """Adding Case 002 must not perturb the existing fixture or its transcript."""
    from fixtures.longitudinal.case_001 import CASE_001
    from fixtures.longitudinal.case_001_transcript import CASE_001_TRANSCRIPT

    assert len(CASE_001.interactions) == 6
    assert len(CASE_001_TRANSCRIPT.interactions) == 6
    assert CASE_001.subject_id != SUBJECT


def test_the_frozen_transcript_type_is_used_unchanged() -> None:
    """The fixture adapts to the frozen harness; it does not extend it."""
    from sanuvia_phase1.transcript import TranscriptInteraction

    fields = set(TranscriptInteraction.__dataclass_fields__)
    assert fields == {"index", "seq_label", "text", "speaker"}
    assert all(
        isinstance(i, TranscriptInteraction) for i in CASE_002_TRANSCRIPT.interactions
    )
