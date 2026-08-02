"""JSON codec for domain objects (used by the SQLite adapter).

Domain objects are immutable frozen dataclasses built from primitives, enums,
datetimes, nested value objects, and tuples. This codec encodes them to a
JSON-safe structure and reconstructs them faithfully, so a store can persist
whole reasoning objects without a bespoke relational schema per type.

It is an *adapter-layer* concern: the domain and application never import it. It
touches only public domain types and their declared fields, so it introduces no
new behaviour — a decoded object is constructed through the same constructor
(and thus the same invariants) as any other.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import Enum
from typing import Any

from sanuvia import domain as d

# Concrete dataclass types that may be persisted.
_DATACLASSES: tuple[type, ...] = (
    d.Provenance,
    d.EvidenceRecord,
    d.InferenceRecord,
    d.Hypothesis,
    d.FutureTrajectory,
    d.Prediction,
    d.Inquiry,
    d.ProvenanceRecord,
    d.SystemModellingContext,
    d.WorldModel,
    d.CurrentModelSnapshot,
    d.AnomalyResolution,
    d.RevisionEvent,
    d.RevisionLedgerEntry,
    d.RecognitionEvent,
    d.DependencyEdge,
    d.EvidenceReliability,
    d.HypothesisSupport,
    d.ModelUncertainty,
    d.ClassificationConfidence,
    d.ProvenanceConfidence,
    d.PredictionLikelihood,
)

_ENUMS: tuple[type[Enum], ...] = (
    d.EvidenceClass,
    d.InquiryStatus,
    d.RevisionOutcome,
    d.RevisionStatus,
    d.AnomalyDisposition,
    d.TrajectoryKind,
    d.RecognitionKind,
    d.DependencyRelation,
)

_DATACLASS_BY_NAME: dict[str, type] = {t.__name__: t for t in _DATACLASSES}
_ENUM_BY_NAME: dict[str, type[Enum]] = {t.__name__: t for t in _ENUMS}


def encode(obj: Any) -> Any:
    """Encode a domain object (or primitive) to a JSON-safe structure."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Enum):
        return {"__enum__": type(obj).__name__, "member": obj.name}
    if isinstance(obj, datetime):
        return {"__dt__": obj.isoformat()}
    if isinstance(obj, tuple):
        return {"__tuple__": [encode(item) for item in obj]}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            "__type__": type(obj).__name__,
            "fields": {
                f.name: encode(getattr(obj, f.name))
                for f in dataclasses.fields(obj)
            },
        }
    raise TypeError(f"Cannot encode object of type {type(obj).__name__}")


def decode(data: Any) -> Any:
    """Reconstruct a domain object from :func:`encode` output."""
    if data is None or isinstance(data, (bool, int, float, str)):
        return data
    if isinstance(data, dict):
        if "__enum__" in data:
            return _ENUM_BY_NAME[data["__enum__"]][data["member"]]
        if "__dt__" in data:
            return datetime.fromisoformat(data["__dt__"])
        if "__tuple__" in data:
            return tuple(decode(item) for item in data["__tuple__"])
        if "__type__" in data:
            cls = _DATACLASS_BY_NAME[data["__type__"]]
            kwargs = {k: decode(v) for k, v in data["fields"].items()}
            return cls(**kwargs)
    raise TypeError(f"Cannot decode value: {data!r}")
