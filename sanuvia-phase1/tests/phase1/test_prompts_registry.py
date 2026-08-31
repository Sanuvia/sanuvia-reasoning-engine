"""Prompts and schemas are immutable, identified artifacts with drift detection."""

from __future__ import annotations

from sanuvia_phase1 import prompts

# Recorded artifact hashes — a change here means a prompt/schema was rewritten.
_EXPECTED_PROMPT = {
    "extraction.observations.v1": "a45066719aa656a3ef544d6184988fd7e42461609ef9ffbb870cf14d218697d1",
    "appraisal.support-contradict-propose.v1": "790e63375fbfb49575924514b3fc277793e23ff68a6e116ffde4a3aa864e8398",
    "baseline.reasoning.v1": "3557977b65552a1a19b3cff3a53f58b93c0efb6e802b821abe0b063cf03943bc",
}
_EXPECTED_SCHEMA = {
    "schema.extraction.v1": "a9cabea9ce522314e9157b39862eb8a9103b3243e507865be4716eedc161c094",
    "schema.appraisal.v1": "f36e78e0be64836de9b2df7e6aaffe0ac7087760a07c1aca6f56f2e5a1b91004",
    "schema.baseline.v1": "efa45b71e5043f3921048215677c04f140db7f3597b903b9b27a046582fbc11e",
}


def test_all_prompt_ids_present() -> None:
    assert set(prompts.PROMPTS) == set(_EXPECTED_PROMPT)


def test_all_schema_ids_present() -> None:
    assert set(prompts.SCHEMAS) == set(_EXPECTED_SCHEMA)


def test_prompt_hashes_are_stable() -> None:
    for pid, expected in _EXPECTED_PROMPT.items():
        assert prompts.prompt(pid).content_sha256 == expected


def test_schema_hashes_are_stable() -> None:
    for sid, expected in _EXPECTED_SCHEMA.items():
        assert prompts.schema(sid).content_sha256 == expected


def test_integrity_check_passes_when_no_drift() -> None:
    assert prompts.verify_prompt_integrity() == []


def test_baseline_prompt_is_shared_between_baselines() -> None:
    # Fairness: both baselines use the SAME prompt id (only their context differs).
    assert prompts.BASELINE_PROMPT_ID == "baseline.reasoning.v1"


def test_unknown_id_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        prompts.prompt("nope")
    with pytest.raises(KeyError):
        prompts.schema("nope")
