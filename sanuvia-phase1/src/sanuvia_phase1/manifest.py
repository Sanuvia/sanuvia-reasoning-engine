"""Immutable Phase-1 run manifest (Area 3).

A manifest captures enough to reproduce and audit a run: identity (run id, git
SHA, Phase-1 version, mode), the complete transcript/input, the explicit model
specs (provider/model/version/prompts/schemas/parameters), and every external
call's raw response, retries, and terminal status. It is a *sidecar* — it is not
part of the deterministic demonstration JSON, so golden replay stays byte-identical.

Honesty rules:

* secrets/credentials are never stored (the manifest holds identifiers and
  parameters only; API keys live with the injected client, out of band);
* a value a provider does not expose (model version, seed, session/cache id) is
  recorded as :class:`~sanuvia_phase1.failures.Maybe` — distinguishing "not
  provided by provider" from "not captured by our system" — never invented;
* serialization is deterministic (``sort_keys``) so the manifest itself is
  reproducible *where the inputs are*; we do NOT claim reproducibility for the
  external model calls themselves.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Any

from .failures import (
    BoundaryKind,
    CallStatus,
    InteractionStatus,
    Maybe,
    MalformedOutputError,
    ModelError,
    Phase1Error,
    RetryExhaustedError,
    classify_exception,
)
from .runconfig import ModelSpec

if TYPE_CHECKING:  # typing-only imports; the objects are passed in at runtime
    from .transcript import Transcript


@dataclass(frozen=True, slots=True)
class CallRecord:
    """One external model call, with its raw response and terminal status."""

    boundary: str  # BoundaryKind value
    interaction_index: int
    seq_label: str
    model_role: str
    status: str  # CallStatus value
    attempts: int
    raw_response: str | None
    detail: str
    session_id: Maybe
    cache_id: Maybe

    def to_payload(self) -> dict[str, Any]:
        return {
            "boundary": self.boundary,
            "interaction_index": self.interaction_index,
            "seq_label": self.seq_label,
            "model_role": self.model_role,
            "status": self.status,
            "attempts": self.attempts,
            "raw_response": self.raw_response,
            "detail": self.detail,
            "session_id": self.session_id.to_payload(),
            "cache_id": self.cache_id.to_payload(),
        }


@dataclass(frozen=True, slots=True)
class RunManifest:
    """The immutable, finalized record of a run. Frozen — it cannot be mutated."""

    run_id: str
    created_at: str
    git_commit_sha: str
    phase1_version: str
    mode: str
    transcript_id: str
    transcript: tuple[tuple[int, str, str], ...]  # (index, seq_label, text)
    model_specs: tuple[ModelSpec, ...]
    call_records: tuple[CallRecord, ...]
    per_interaction_status: tuple[tuple[str, str], ...]  # (seq_label, status)
    notes: str
    governance_freeze_hash: str = ""  # pins the approved governance freeze record

    def to_payload(self) -> dict[str, Any]:
        return {
            "governance_freeze_hash": self.governance_freeze_hash,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "git_commit_sha": self.git_commit_sha,
            "phase1_version": self.phase1_version,
            "mode": self.mode,
            "transcript_id": self.transcript_id,
            "transcript": [list(turn) for turn in self.transcript],
            "model_specs": [spec.to_payload() for spec in self.model_specs],
            "call_records": [record.to_payload() for record in self.call_records],
            "per_interaction_status": [list(pair) for pair in self.per_interaction_status],
            "notes": self.notes,
            "reproducibility": (
                "Deterministic serialization; the golden path is byte-identical. "
                "External model calls are NOT claimed to be reproducible."
            ),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_payload(), sort_keys=True, indent=2, ensure_ascii=False
        )


class RunManifestBuilder:
    """Mutable accumulator that produces an immutable :class:`RunManifest`.

    Call :meth:`record_call` as external calls complete (or fail), then
    :meth:`finalize` exactly once. After finalization the builder rejects further
    records, and the returned manifest is frozen."""

    def __init__(
        self,
        *,
        run_id: str,
        created_at: str,
        git_commit_sha: str,
        phase1_version: str,
        mode: str,
        transcript: "Transcript",
        model_specs: Sequence[ModelSpec] = (),
        notes: str = "",
        governance_freeze_hash: str = "",
    ) -> None:
        self._run_id = run_id
        self._created_at = created_at
        self._git_commit_sha = git_commit_sha
        self._phase1_version = phase1_version
        self._mode = mode
        self._transcript = transcript
        self._model_specs = tuple(model_specs)
        self._notes = notes
        self._governance_freeze_hash = governance_freeze_hash
        self._calls: list[CallRecord] = []
        self._started: set[str] = set()
        self._finalized = False

    def record_call(self, record: CallRecord) -> None:
        if self._finalized:
            raise Phase1Error("cannot record a call on a finalized manifest")
        self._calls.append(record)

    def mark_started(self, seq_label: str) -> None:
        """Record that processing of an interaction actually began (Run 002
        amendment). An interaction that is neither marked started nor produced any
        call is reported as ``NOT_EXECUTED`` — never ``SUCCESS``."""
        if self._finalized:
            raise Phase1Error("cannot mark an interaction on a finalized manifest")
        self._started.add(seq_label)

    def _per_interaction_status(self) -> tuple[tuple[str, str], ...]:
        # An interaction is EXECUTED if it was explicitly marked started OR produced
        # at least one call. Executed interactions report SUCCESS unless a non-success
        # call was recorded (then the first such CallStatus). Interactions that were
        # never attempted report NOT_EXECUTED — never a silent SUCCESS.
        called: set[str] = {record.seq_label for record in self._calls}
        executed: set[str] = self._started | called
        failures: dict[str, str] = {}
        for record in self._calls:
            if record.status != CallStatus.SUCCESS.value and record.seq_label not in failures:
                failures[record.seq_label] = record.status
        out: list[tuple[str, str]] = []
        for interaction in self._transcript.interactions:
            seq = interaction.seq_label
            if seq not in executed:
                status = InteractionStatus.NOT_EXECUTED.value
            elif seq in failures:
                status = failures[seq]
            else:
                status = InteractionStatus.SUCCESS.value
            out.append((seq, status))
        return tuple(out)

    def finalize(self) -> RunManifest:
        if self._finalized:
            raise Phase1Error("manifest already finalized")
        self._finalized = True
        transcript = tuple(
            (i.index, i.seq_label, i.text) for i in self._transcript.interactions
        )
        return RunManifest(
            run_id=self._run_id,
            created_at=self._created_at,
            git_commit_sha=self._git_commit_sha,
            phase1_version=self._phase1_version,
            mode=self._mode,
            transcript_id=self._transcript.transcript_id,
            transcript=transcript,
            model_specs=self._model_specs,
            call_records=tuple(self._calls),
            per_interaction_status=self._per_interaction_status(),
            notes=self._notes,
            governance_freeze_hash=self._governance_freeze_hash,
        )


def call_with_recording(
    builder: RunManifestBuilder,
    *,
    boundary: BoundaryKind,
    interaction_index: int,
    seq_label: str,
    model_role: str,
    thunk: Callable[[], str],
    retries: int = 0,
    session_id: Maybe | None = None,
    cache_id: Maybe | None = None,
) -> str:
    """Run one external boundary call, recording its outcome on ``builder``.

    Returns the raw model text on success. ``MalformedOutputError`` is recorded as
    ``MALFORMED_OUTPUT`` and re-raised without retrying (a bad schema is
    deterministic). ``ModelError``/``ModelTimeout`` are retried up to ``retries``
    times; if still failing, the terminal record is written and the failure
    propagates (as ``RetryExhaustedError`` when retries were configured). A failed
    call is never turned into a successful-looking result."""
    sid = session_id if session_id is not None else Maybe.not_captured()
    cid = cache_id if cache_id is not None else Maybe.not_captured()
    allowed = retries + 1
    attempts = 0
    last_status = CallStatus.MODEL_ERROR
    last_detail = ""

    while True:
        attempts += 1
        try:
            raw = thunk()
        except MalformedOutputError as exc:
            builder.record_call(
                CallRecord(
                    boundary.value, interaction_index, seq_label, model_role,
                    CallStatus.MALFORMED_OUTPUT.value, attempts, exc.raw, exc.detail, sid, cid,
                )
            )
            raise
        except ModelError as exc:
            last_status = classify_exception(exc)
            last_detail = str(exc)
            if attempts < allowed:
                continue
            terminal = CallStatus.RETRY_EXHAUSTED if retries > 0 else last_status
            builder.record_call(
                CallRecord(
                    boundary.value, interaction_index, seq_label, model_role,
                    terminal.value, attempts, None, last_detail, sid, cid,
                )
            )
            if retries > 0:
                raise RetryExhaustedError(
                    boundary, attempts, last_status, last_detail
                ) from exc
            raise
        else:
            builder.record_call(
                CallRecord(
                    boundary.value, interaction_index, seq_label, model_role,
                    CallStatus.SUCCESS.value, attempts, raw, "", sid, cid,
                )
            )
            return raw
