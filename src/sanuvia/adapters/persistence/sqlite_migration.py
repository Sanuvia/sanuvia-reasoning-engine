"""SQLite schema migration for the space/subject isolation change (Finding 1).

Adds ``space`` (and, for hypotheses/predictions, ``subject``) ownership to a
database created by the pre-isolation schema (``user_version = 0``), and rewrites
the stored JSON blobs so they decode under the new domain constructors — which
now require ``Hypothesis.subject_id`` / ``Prediction.subject_id`` and carry a
``space_id`` on every owned object.

Migration guarantees / assumptions (documented for review):

* **Existing data is preserved.** No reasoning row is dropped. Every evidence,
  hypothesis, prediction, world-model version, ledger entry, etc. is carried
  forward, with ownership made explicit.
* **No silent mis-assignment.** Pre-migration data predates spaces, so it is
  assigned to the single ``DEFAULT_SPACE_ID`` (never a random or per-row space).
* **Subject is recovered, not guessed.** Hypotheses/predictions had no subject
  column. Each is assigned the subject of the WorldModel version that references
  its id (``active_hypothesis_ids`` / ``active_prediction_ids``). Only if a row
  is referenced by no model do we fall back to the database's single distinct
  evidence subject; if even that is ambiguous we use ``UNKNOWN_SUBJECT`` and the
  row is quarantined under that subject rather than leaked to a real one.
* **Idempotent.** Guarded by ``PRAGMA user_version``; running twice is a no-op.

The migration operates on raw JSON (never through the domain constructors), so a
legacy blob that lacks the new required fields is patched *before* anything tries
to decode it.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from sanuvia.domain import DEFAULT_SPACE_ID

SCHEMA_VERSION = 1

# Sentinel subject for hypotheses/predictions whose owner cannot be recovered.
UNKNOWN_SUBJECT = "subject:unknown-pre-migration"

_DEFAULT_SPACE = str(DEFAULT_SPACE_ID)


def migrate(conn: sqlite3.Connection, schema_sql: str) -> None:
    """Bring ``conn`` up to :data:`SCHEMA_VERSION`, then ensure the schema exists.

    Safe on a brand-new database (nothing to migrate — the schema is simply
    created) and idempotent on an already-migrated one.
    """
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if version >= SCHEMA_VERSION:
        conn.executescript(schema_sql)  # create any missing tables (IF NOT EXISTS)
        conn.commit()
        return

    _migrate_v0_to_v1(conn)
    conn.executescript(schema_sql)  # create tables the migration didn't recreate
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


# -- helpers ------------------------------------------------------------------


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _patch_fields(text: str, **fields: Any) -> str:
    """Add missing top-level ``fields`` keys to a codec blob (never overwrite)."""
    obj = json.loads(text)
    obj.setdefault("fields", {})
    for key, value in fields.items():
        obj["fields"].setdefault(key, value)
    return json.dumps(obj)


def _tuple_values(encoded: Any) -> list[str]:
    """Extract the string members of a codec-encoded tuple (or [] if absent)."""
    if isinstance(encoded, dict) and "__tuple__" in encoded:
        return [v for v in encoded["__tuple__"] if isinstance(v, str)]
    return []


# -- the v0 -> v1 migration ---------------------------------------------------


def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    # 1. Recover the owner subject for each hypothesis/prediction id from the
    #    world models that reference it (before we touch world_models).
    hyp_subject: dict[str, str] = {}
    pred_subject: dict[str, str] = {}
    if _table_exists(conn, "world_models"):
        for (blob,) in conn.execute("SELECT json FROM world_models").fetchall():
            fields = json.loads(blob).get("fields", {})
            subject = fields.get("subject_id")
            if not isinstance(subject, str):
                continue
            for hid in _tuple_values(fields.get("active_hypothesis_ids")):
                hyp_subject.setdefault(hid, subject)
            for pid in _tuple_values(fields.get("active_prediction_ids")):
                pred_subject.setdefault(pid, subject)

    # 2. Fallback subject: the single distinct evidence subject, if unambiguous.
    fallback_subject = _sole_evidence_subject(conn)

    # 3. Column-additive tables: add space (and subject where missing), backfill.
    _add_space_column(conn, "evidence", rewrite=lambda b: _patch_fields(
        b, space_id=_DEFAULT_SPACE, actor_id=None))
    _add_space_column(conn, "inference", rewrite=lambda b: _patch_fields(
        b, space_id=_DEFAULT_SPACE))
    _add_space_column(conn, "inquiries", rewrite=lambda b: _patch_fields(
        b, space_id=_DEFAULT_SPACE))
    _add_space_column(conn, "recognition", rewrite=lambda b: _patch_fields(
        b, space_id=_DEFAULT_SPACE))

    _migrate_hypotheses(conn, hyp_subject, fallback_subject)
    _migrate_predictions(conn, pred_subject, fallback_subject)

    # 4. Anomalies / provenance: id-keyed, no new column — just patch the blob so
    #    the added space_id field decodes.
    _rewrite_blobs(conn, "anomalies", lambda b: _patch_fields(b, space_id=_DEFAULT_SPACE))
    _rewrite_blobs(conn, "provenance", lambda b: _patch_fields(b, space_id=_DEFAULT_SPACE))

    # 5. PK-changing tables: recreate with a leading space column.
    _recreate_world_models(conn)
    _recreate_current_pointer(conn)
    _recreate_ledger(conn)


def _sole_evidence_subject(conn: sqlite3.Connection) -> str | None:
    if not _table_exists(conn, "evidence") or "subject" not in _columns(conn, "evidence"):
        return None
    rows = conn.execute("SELECT DISTINCT subject FROM evidence").fetchall()
    subjects = [r[0] for r in rows if r[0] is not None]
    return subjects[0] if len(subjects) == 1 else None


def _add_space_column(
    conn: sqlite3.Connection, table: str, *, rewrite: Any
) -> None:
    if not _table_exists(conn, table):
        return
    cols = _columns(conn, table)
    if "space" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN space TEXT")
    conn.execute(f"UPDATE {table} SET space = ? WHERE space IS NULL", (_DEFAULT_SPACE,))
    _rewrite_blobs(conn, table, rewrite)


def _rewrite_blobs(conn: sqlite3.Connection, table: str, rewrite: Any) -> None:
    if not _table_exists(conn, table):
        return
    rows = conn.execute(f"SELECT rowid, json FROM {table}").fetchall()
    for rowid, blob in rows:
        conn.execute(
            f"UPDATE {table} SET json = ? WHERE rowid = ?", (rewrite(blob), rowid)
        )


def _migrate_hypotheses(
    conn: sqlite3.Connection, hyp_subject: dict[str, str], fallback: str | None
) -> None:
    if not _table_exists(conn, "hypotheses"):
        return
    cols = _columns(conn, "hypotheses")
    if "space" not in cols:
        conn.execute("ALTER TABLE hypotheses ADD COLUMN space TEXT")
    if "subject" not in cols:
        conn.execute("ALTER TABLE hypotheses ADD COLUMN subject TEXT")
    for rowid, hid, blob in conn.execute(
        "SELECT rowid, hypothesis_id, json FROM hypotheses"
    ).fetchall():
        subject = hyp_subject.get(hid) or fallback or UNKNOWN_SUBJECT
        patched = _patch_fields(blob, subject_id=subject, space_id=_DEFAULT_SPACE)
        conn.execute(
            "UPDATE hypotheses SET space = ?, subject = ?, json = ? WHERE rowid = ?",
            (_DEFAULT_SPACE, subject, patched, rowid),
        )


def _migrate_predictions(
    conn: sqlite3.Connection, pred_subject: dict[str, str], fallback: str | None
) -> None:
    if not _table_exists(conn, "predictions"):
        return
    cols = _columns(conn, "predictions")
    if "space" not in cols:
        conn.execute("ALTER TABLE predictions ADD COLUMN space TEXT")
    if "subject" not in cols:
        conn.execute("ALTER TABLE predictions ADD COLUMN subject TEXT")
    for rowid, pid, blob in conn.execute(
        "SELECT rowid, id, json FROM predictions"
    ).fetchall():
        subject = pred_subject.get(pid) or fallback or UNKNOWN_SUBJECT
        patched = _patch_fields(blob, subject_id=subject, space_id=_DEFAULT_SPACE)
        conn.execute(
            "UPDATE predictions SET space = ?, subject = ?, json = ? WHERE rowid = ?",
            (_DEFAULT_SPACE, subject, patched, rowid),
        )


def _recreate_world_models(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "world_models") or "space" in _columns(conn, "world_models"):
        return
    rows = conn.execute("SELECT subject, version, json FROM world_models").fetchall()
    conn.execute("ALTER TABLE world_models RENAME TO world_models_v0")
    conn.execute(
        "CREATE TABLE world_models (space TEXT, subject TEXT, version TEXT, json TEXT, "
        "PRIMARY KEY (space, subject, version))"
    )
    for subject, version, blob in rows:
        conn.execute(
            "INSERT INTO world_models (space, subject, version, json) VALUES (?, ?, ?, ?)",
            (_DEFAULT_SPACE, subject, version, _patch_fields(blob, space_id=_DEFAULT_SPACE)),
        )
    conn.execute("DROP TABLE world_models_v0")


def _recreate_current_pointer(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "current_pointer") or "space" in _columns(
        conn, "current_pointer"
    ):
        return
    rows = conn.execute("SELECT subject, json FROM current_pointer").fetchall()
    conn.execute("ALTER TABLE current_pointer RENAME TO current_pointer_v0")
    conn.execute(
        "CREATE TABLE current_pointer (space TEXT, subject TEXT, json TEXT, "
        "PRIMARY KEY (space, subject))"
    )
    for subject, blob in rows:
        conn.execute(
            "INSERT INTO current_pointer (space, subject, json) VALUES (?, ?, ?)",
            (_DEFAULT_SPACE, subject, _patch_fields(blob, space_id=_DEFAULT_SPACE)),
        )
    conn.execute("DROP TABLE current_pointer_v0")


def _recreate_ledger(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "ledger") or "space" in _columns(conn, "ledger"):
        return
    rows = conn.execute("SELECT subject, seq, json FROM ledger").fetchall()
    conn.execute("ALTER TABLE ledger RENAME TO ledger_v0")
    conn.execute(
        "CREATE TABLE ledger (space TEXT, subject TEXT, seq INTEGER, json TEXT, "
        "PRIMARY KEY (space, subject, seq))"
    )
    for subject, seq, blob in rows:
        conn.execute(
            "INSERT INTO ledger (space, subject, seq, json) VALUES (?, ?, ?, ?)",
            (_DEFAULT_SPACE, subject, seq, _patch_ledger_blob(blob)),
        )
    conn.execute("DROP TABLE ledger_v0")


def _patch_ledger_blob(text: str) -> str:
    """A RevisionLedgerEntry wraps a RevisionEvent; patch the nested event's
    ``space_id`` so it decodes under the new RevisionEvent constructor."""
    obj = json.loads(text)
    event = obj.get("fields", {}).get("revision_event")
    if isinstance(event, dict):
        event.setdefault("fields", {}).setdefault("space_id", _DEFAULT_SPACE)
    return json.dumps(obj)
