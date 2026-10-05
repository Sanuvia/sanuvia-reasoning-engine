# Phase 1 Semantic State — Revised Slice Allocation

**Branch:** `phase1-semantic-state-v1.5.4` · **Date:** 2026-10-05
**Authority:** Architecture v0.2, Technical Design v1.5.4, Reading A confirmed

This supersedes the implicit allocation carried in earlier records. It exists
because confirming **Reading A** changed what the deterministic arm can do on
its own, and that has to be stated rather than inferred from test counts.

---

## Slice 1 — deterministic foundation (delivered)

Implemented and tested on **both** adapters, Scripted and External.

| Capability | State |
|---|---|
| Durable identity engine-issued after adjudication | delivered |
| Immutable `(subject, attribution)` retrieval bound, attribution a governed **voice** label | delivered |
| Exact normalised match against every `StatementVersion` → `MATCH_EXISTING` | delivered |
| Empty bound → `DISTINCT_NEW` | delivered |
| Populated bound, no exact match → **parks** `AMBIGUOUS_REVIEW_REQUIRED` | delivered |
| R1a stance-inversion merge protection | delivered |
| Plural lineages per bound: adjudicator, store index, check 10 | delivered |
| Commitment signature across the model boundary, both directions | delivered |
| `commit_plan` sole writer; atomic rollback incl. identifier counters | delivered |
| Source-reference mapping (TD-03) on the running engine | delivered |
| Rollback capability as a visible governed condition | delivered |
| Rejected-plan audit at the trajectory boundary (TD-18) | delivered |
| Scripted/External parity (TD-19) | delivered |

## Slice 2 — deferred, NOT implemented

| Capability | Why it is Slice 2 |
|---|---|
| **R1 model-assisted identity resolver** | Locked §3.3 permits a narrow resolver for non-identical comparison. Not implemented, not stubbed in any real path, not simulated. |
| `REFINE_EXISTING` | Produced only by the resolver. Unreachable by construction and asserted so. |
| `DISTINCT_NEW` for a **non-exact** candidate under a populated bound | Requires a comparison the deterministic arm cannot make. Until R1, such a candidate parks. |
| Resolution of parked candidates | Ruling Q2: parked candidates are created, preserved and reported; no resolution path. |
| Prediction lifecycle governance | Locked §8. Trajectory content is preserved unchanged; no creation, expiry or confirmation policy is introduced. |
| Standing rules (check 9), disclosure (check 8b), divergence endpoints (check 8a) | Implemented in the validator, unwired at the call site. Wiring them changes which interactions reject — behaviour, not mapping. |

---

## What Reading A costs, stated plainly

`attribution` is a voice, so **every commitment one voice holds about one
subject shares a single retrieval bound**. Under §2 G that means:

* an exact re-presentation of a committed statement **attaches** to its lineage;
* any **other** statement under that bound is a plausible candidate at
  resolution-order case 4, and with no resolver configured it **parks**.

**On the real External path this is the live behaviour.** Identity is
engine-owned for exact matches and *undecided but preserved* otherwise. A
second genuinely distinct commitment for one subject cannot be created by the
deterministic arm. That is not a defect; it is the sequencing consequence of
bringing the deterministic arm forward without R1, and §3.4's
burden-of-distinctness rule forbids discharging it by automatic creation.

**No Run 003 readiness is implied.** Run 003 needs R1 wired, which the
Technical Design already assumes.

## How the Scripted suites still express plurality

Through an injected **test double**, not a heuristic.
`ScriptedIdentityResolver` returns the decision a fixture **authored** and
compares nothing. The design's own matrix anticipates this: TD-06, TD-08 and
TD-13b specify running "with the `IdentityResolver` injected or stubbed so the
outcome is controlled".

It is wired into the exit-test fixture, the HTTP harness and review dataset
runner, the Phase 1 **scripted** condition, the demo and scripted test
helpers. `deps.identity_resolver` defaults to `None`, so every real path runs
the unassisted deterministic arm.

In the Phase 1 condition the guard is **structural**: the resolver is bound to
the same branch that selects the scripted appraiser, so an injected real
appraiser — the only thing a REAL/Run 003 configuration may use — never
receives one.
