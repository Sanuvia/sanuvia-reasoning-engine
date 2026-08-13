"""Finding 1 — SQLite schema migration from the pre-space (v0) database.

Builds a database in the OLD schema with OLD-shaped JSON blobs (no ``space_id``
anywhere; no ``subject_id`` on hypotheses/predictions), then opens it with the
current ``SqliteReasoningStore`` — which must migrate it in place, preserving
every row, recovering ownership, and leaving the data decodable and correctly
isolated.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from sanuvia.adapters.persistence import codec
from sanuvia.adapters.persistence.sqlite_migration import SCHEMA_VERSION
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    CurrentModelSnapshot,
    EvidenceRecordId,
    HypothesisId,
    ModelUncertainty,
    ObjectRef,
    PredictionId,
    ReasoningSystemId,
    RevisionEvent,
    RevisionEventId,
    RevisionLedgerEntry,
    RevisionOutcome,
    RevisionStatus,
    SubjectId,
    WorldModel,
    WorldModelVersionId,
)
from tests.conftest import make_evidence, make_hypothesis, make_prediction

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
LEGACY_SUBJECT = SubjectId("legacy-subject")

# The pre-remediation (v0) schema — no space columns; hypotheses/predictions have
# no subject column.
_V0_SCHEMA = """
CREATE TABLE evidence (id TEXT PRIMARY KEY, subject TEXT, json TEXT);
CREATE TABLE hypotheses (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, record_id TEXT, hypothesis_id TEXT, json TEXT);
CREATE TABLE predictions (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, json TEXT);
CREATE TABLE world_models (
    subject TEXT, version TEXT, json TEXT, PRIMARY KEY (subject, version));
CREATE TABLE current_pointer (subject TEXT PRIMARY KEY, json TEXT);
CREATE TABLE ledger (subject TEXT, seq INTEGER, json TEXT, PRIMARY KEY (subject, seq));
CREATE TABLE anomalies (id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE provenance (id TEXT PRIMARY KEY, json TEXT);
"""


def _blob_without(obj: Any, *drop: str) -> str:
    """Encode a domain object, then drop the named fields to simulate a legacy
    blob written before those fields existed."""
    encoded = codec.encode(obj)
    for key in drop:
        encoded["fields"].pop(key, None)
    return json.dumps(encoded)


def _seed_legacy_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(_V0_SCHEMA)

    ev = make_evidence(evidence_id="evidence-1", subject_id=LEGACY_SUBJECT)
    hyp = make_hypothesis(
        record_id="hyprec-1", hypothesis_id="H_legacy", subject_id=LEGACY_SUBJECT,
        support=0.7, supporting=("evidence-1",))
    pred = make_prediction(
        prediction_id="pred-1", hyps=("H_legacy",), subject_id=LEGACY_SUBJECT)
    wm = WorldModel(
        model_version_id=WorldModelVersionId("wm-1"),
        subject_id=LEGACY_SUBJECT,
        reasoning_system_id=ReasoningSystemId("sanuvia-phase0"),
        model_uncertainty=ModelUncertainty(0.4),
        active_hypothesis_ids=(HypothesisId("H_legacy"),),
        active_prediction_ids=(PredictionId("pred-1"),),
        active_inquiry_ids=(),
        created_at=T0,
    )
    pointer = CurrentModelSnapshot(
        subject_id=LEGACY_SUBJECT, model_version_id=WorldModelVersionId("wm-1"),
        committed_at=T0)
    event = RevisionEvent(
        id=RevisionEventId("rev-1"), subject_id=LEGACY_SUBJECT,
        affected_object_id=ObjectRef("H_legacy"), outcome=RevisionOutcome.HYPOTHESIZE,
        triggering_evidence_ids=(EvidenceRecordId("evidence-1"),),
        status=RevisionStatus.COMMITTED, created_at=T0,
        to_model_version_id=WorldModelVersionId("wm-1"))
    entry = RevisionLedgerEntry(sequence_no=0, revision_event=event, appended_at=T0)

    # Legacy ledger blob: strip space_id from the NESTED revision event.
    ledger_encoded = codec.encode(entry)
    ledger_encoded["fields"]["revision_event"]["fields"].pop("space_id", None)

    con.execute("INSERT INTO evidence (id, subject, json) VALUES (?, ?, ?)",
                ("evidence-1", LEGACY_SUBJECT, _blob_without(ev, "space_id", "actor_id")))
    con.execute("INSERT INTO hypotheses (record_id, hypothesis_id, json) VALUES (?, ?, ?)",
                ("hyprec-1", "H_legacy", _blob_without(hyp, "space_id", "subject_id")))
    con.execute("INSERT INTO predictions (id, json) VALUES (?, ?)",
                ("pred-1", _blob_without(pred, "space_id", "subject_id")))
    con.execute("INSERT INTO world_models (subject, version, json) VALUES (?, ?, ?)",
                (LEGACY_SUBJECT, "wm-1", _blob_without(wm, "space_id")))
    con.execute("INSERT INTO current_pointer (subject, json) VALUES (?, ?)",
                (LEGACY_SUBJECT, _blob_without(pointer, "space_id")))
    con.execute("INSERT INTO ledger (subject, seq, json) VALUES (?, ?, ?)",
                (LEGACY_SUBJECT, 0, json.dumps(ledger_encoded)))

    con.execute("PRAGMA user_version = 0")
    con.commit()
    con.close()


def test_legacy_db_migrates_preserving_data_and_ownership(tmp_path: Any) -> None:
    path = str(tmp_path / "legacy.db")
    _seed_legacy_db(path)

    store = SqliteReasoningStore(path)  # triggers migration on open

    # Schema version stamped.
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION

    # Evidence preserved, decodes, assigned to the default space.
    evidence = store.evidence.list_for_subject(LEGACY_SUBJECT)
    assert [e.id for e in evidence] == [EvidenceRecordId("evidence-1")]
    assert evidence[0].space_id == DEFAULT_SPACE_ID

    # Hypothesis: subject recovered from the referencing WorldModel, decodes.
    hyps = store.hypotheses.list_for_subject(LEGACY_SUBJECT)
    assert [h.hypothesis_id for h in hyps] == [HypothesisId("H_legacy")]
    assert hyps[0].subject_id == LEGACY_SUBJECT
    assert hyps[0].space_id == DEFAULT_SPACE_ID

    # Prediction: subject recovered from the WorldModel too.
    preds = store.predictions.list_for_subject(LEGACY_SUBJECT)
    assert [p.id for p in preds] == [PredictionId("pred-1")]
    assert preds[0].subject_id == LEGACY_SUBJECT

    # WorldModel + pointer + ledger preserved and decodable under the new keys.
    model = store.world_models.get_current_model(LEGACY_SUBJECT)
    assert model is not None and model.model_version_id == WorldModelVersionId("wm-1")
    assert model.space_id == DEFAULT_SPACE_ID
    ledger = store.ledger.read(LEGACY_SUBJECT)
    assert len(ledger) == 1
    assert ledger[0].revision_event.space_id == DEFAULT_SPACE_ID

    # Isolation now holds: another space sees none of the migrated data.
    other = HypothesisId("H_legacy")
    assert store.hypotheses.latest(other, space_id=DEFAULT_SPACE_ID) is not None
    from sanuvia.domain import shared_space_id
    assert store.hypotheses.list_for_subject(LEGACY_SUBJECT, space_id=shared_space_id("x")) == []


def test_migration_is_idempotent(tmp_path: Any) -> None:
    path = str(tmp_path / "legacy.db")
    _seed_legacy_db(path)
    SqliteReasoningStore(path).close()          # migrate once
    store = SqliteReasoningStore(path)          # open again — no error, no change
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert len(store.evidence.list_for_subject(LEGACY_SUBJECT)) == 1
    assert len(store.hypotheses.list_for_subject(LEGACY_SUBJECT)) == 1


def test_fresh_db_is_created_at_current_version(tmp_path: Any) -> None:
    store = SqliteReasoningStore(str(tmp_path / "fresh.db"))
    assert store._conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
