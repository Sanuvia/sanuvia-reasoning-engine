"""The six typed uncertainty values behave as bounded, immutable, distinct types."""

from __future__ import annotations

import dataclasses

import pytest

from sanuvia.domain import (
    ClassificationConfidence,
    EvidenceReliability,
    HypothesisSupport,
    InvariantViolation,
    ModelUncertainty,
    PredictionLikelihood,
    ProvenanceConfidence,
)

ALL_TYPES = [
    EvidenceReliability,
    HypothesisSupport,
    ModelUncertainty,
    ClassificationConfidence,
    ProvenanceConfidence,
    PredictionLikelihood,
]


def test_there_are_exactly_six_distinct_types() -> None:
    assert len({t.__name__ for t in ALL_TYPES}) == 6


@pytest.mark.parametrize("cls", ALL_TYPES)
def test_accepts_values_in_unit_interval(cls: type) -> None:
    assert cls(0.0).value == 0.0
    assert cls(1.0).value == 1.0
    assert cls(0.5).value == 0.5


@pytest.mark.parametrize("cls", ALL_TYPES)
@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
def test_rejects_out_of_range(cls: type, bad: float) -> None:
    with pytest.raises(InvariantViolation):
        cls(bad)


@pytest.mark.parametrize("cls", ALL_TYPES)
def test_rejects_bool_masquerading_as_number(cls: type) -> None:
    # bool is a subclass of int; True must not slip through as 1.0.
    with pytest.raises(InvariantViolation):
        cls(True)


@pytest.mark.parametrize("cls", ALL_TYPES)
def test_is_immutable(cls: type) -> None:
    value = cls(0.5)
    with pytest.raises(dataclasses.FrozenInstanceError):
        value.value = 0.6  # type: ignore[misc]


def test_ints_are_normalised_to_float() -> None:
    assert isinstance(ModelUncertainty(1).value, float)


def test_equality_is_by_value_within_a_type() -> None:
    assert ModelUncertainty(0.4) == ModelUncertainty(0.4)
    # Distinct types are never equal even at the same magnitude.
    assert ModelUncertainty(0.4) != HypothesisSupport(0.4)
