# Reset & Rerun semantics (test harness vs. durable production)

Finding 2 of the Phase 0 engineering review reproduced a defect: with the durable
SQLite backend, resetting and rerunning a deterministic Test Case failed with a
duplicate-id error. This document defines the two distinct lifecycles so the
distinction stays explicit.

## The failure that was fixed

The review harness runs each Test Case with a **deterministic** id generator
(`SequentialIdGenerator`) so a rerun reproduces byte-identically — the first
evidence id is always `evidence-1`. Against the **durable** SQLite backend the
database file persists between runs, so a rerun re-issued `evidence-1` while the
row from the previous run was still on disk, and the insert collided:

```
InvariantViolation: EvidenceRecord evidence-1 already exists
```

## Two lifecycles

### Test harness — deterministic, resettable

The Engineering Review Harness runs **deterministic Test Cases**. A rerun MUST
reproduce the same reasoning exactly.

- Ids come from `SequentialIdGenerator` (`evidence-1`, `wm-1`, …).
- **Reset is a first-class lifecycle operation.** `TestCase._build()` (invoked by
  *Run Full Sequence* and *Reset*) calls `SqliteReasoningStore.reset()`, which
  truncates every table so the deterministic rerun starts from a clean database
  and cannot collide. The saved *definitions* (the authored evidence sequence and
  review metadata) live separately on disk and are **not** touched by reset —
  reasoning state is regenerated deterministically by rerunning them.
- Equivalent behaviour on the in-memory backend is automatic: each build
  allocates a fresh store, so state and ids reset together.

### Durable production — collision-safe, never reset-erased

Durable reasoning for **real subjects** is different: it accumulates over time and
must never be wiped.

- Ids come from a **collision-safe** generator. `build_sqlite_dependencies`
  therefore defaults to `UuidGenerator` (and the wall clock). Every id is unique
  across the lifetime of the database, so appends never collide — no reset is
  needed or wanted.
- Deterministic, test-only id generators (`SequentialIdGenerator`) must **not**
  be used for durable production operation. They exist for reproducible tests.
- There is no "reset" in production. `SqliteReasoningStore.reset()` is a
  test-harness affordance; durable wiring never calls it, and durable state is
  preserved across restarts and reconnects (the store only ever appends).

## Summary

| | Test harness | Durable production |
|---|---|---|
| Id generator | `SequentialIdGenerator` (deterministic) | `UuidGenerator` (collision-safe) |
| Clock | `ManualClock` | `SystemClock` |
| Reset | clears the DB each rebuild (lifecycle op) | never — state is permanent |
| Rerun | reproduces byte-identically | not applicable (append-only) |
| Guarantee | determinism | durability |

## Verification

`tests/adapters/test_sqlite_reset_rerun.py`:

- reproduces the original duplicate-id failure,
- proves the harness reset/rerun is clean and byte-identically deterministic,
- proves durable wiring uses collision-safe ids and never erases prior state.
