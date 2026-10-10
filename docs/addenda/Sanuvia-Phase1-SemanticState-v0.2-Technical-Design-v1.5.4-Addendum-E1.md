# Technical Design v1.5.4 — Addendum / Errata E-1

**Subject:** Prediction trajectory carrier on `CandidateProposal`
**Status:** Errata to v1.5.4. Clarifying, not amending.
**Date:** 2026-10-04

Issued as a separate document so that the v1.5.4 seal
(`6e4e05b7…a8de5`) remains valid. No governed rule in v1.5.4 is amended or
retracted.

---

## E-1.1 Defect

The v1.5.4 appraiser port defined `CandidateProposal` as
`(local_ref, statement, signature)`.

Three omissions are correct and stand, per the §2 C narrowing: `hypothesis_id`
(durable identity is engine-issued after adjudication), `initial_support` (R6
fixes the derivation) and `supporting_evidence_ids` (support attaches to the
single observation deterministically).

`predicted_trajectory` was omitted with them. It is neither an identity field
nor a support field; it is authored proposal content.

The omission produced a silent break rather than a failure.
`_RevisionRun.traj_hints` remained declared and remained read by
`_regenerate_predictions`, but no code path wrote to it. Authored trajectory
content was discarded at the port boundary, and every prediction fell back to
the generated `"trajectory consistent with: {statement}"` description.

## E-1.2 Authority

Locked §8 defers the prediction lifecycle — creation policy, invalidation
policy, trajectory governance — to a later governed cycle. A deferral requires
existing behaviour to be preserved unchanged until that cycle rules on it.
Dropping the carrier discarded content within the deferred scope. Retaining it
unchanged is what the deferral requires.

## E-1.3 Clarification

`CandidateProposal` retains an optional `predicted_trajectory`, typed as the
existing domain `FutureTrajectory`. No new type is introduced.

The field is **content only**:

1. It does not influence support. R6 remains the sole source of support for a
   new lineage: `support_after_support(0.0, reliability, learning_rate)`.
2. It does not influence model uncertainty or any other derived state.
3. It does not influence inquiry formation.
4. It carries no identity. It names no hypothesis and forms no part of the
   `CommitmentSignature` or the lineage key.

Existing prediction creation is carried into the revision plan unchanged.
Prediction persistence occurs inside `commit_plan`, preserving the sole-writer
invariant (§1.5, TD-W1).

`prediction_support_threshold` is **unchanged** and is evaluated **before** any
trajectory content is consulted, so content attached to a sub-threshold lineage
is recorded and never read. A candidate parked as `AMBIGUOUS_REVIEW_REQUIRED`
creates no hypothesis and therefore records no trajectory.

**No prediction extension is introduced.** The set of conditions under which a
prediction is created is identical to v1.5.4 as sealed.

## E-1.4 Separation of two distinct conditions

Two independent conditions were identified and are recorded separately.

| | Condition A | Condition B |
|---|---|---|
| **Statement** | A prediction is created but trajectory content is not propagated | No prediction is created, because the support threshold is not crossed |
| **Present** | Yes — latent | Yes — active |
| **Cause** | `CandidateProposal` omitted the carrier, so `traj_hints` was never written | Under R6, one observation at reliability 0.8 yields support `0 + 0.5×0.8×(1−0)` = **0.400**, below `prediction_support_threshold` **0.600** |
| **Disposition** | Corrected by this errata | Not corrected. Recorded as an R6 threshold consequence |

Condition B masks Condition A: where no prediction is created, an omitted
carrier produces no observable symptom. The two must not be conflated.

### Observed state

`test_proposal_trajectory_hint_flows_into_prediction` fails on
`len(result.predictions)` with `assert 0 == 1`. The hypothesis is created
(`hyp-1`) with support `0.400`; `active_prediction_ids` is empty. The failure
is prediction formation, not trajectory propagation — Condition B.

### Scope boundary

The threshold is unchanged. The fixture is unchanged. The authored
`initial_support=0.7`, which under pre-R6 derivation crossed 0.600 directly, is
correctly no longer consulted.

`test_proposal_trajectory_hint_flows_into_prediction` is retained unmodified
and remains failing, as the standing record of the R6 threshold consequence.
Its disposition requires a governance decision and is referred.

### Verification of Condition A

`test_trajectory_hint_survives_the_port_once_r6_support_crosses_the_gate`
reaches the threshold through R6 accumulation — a second supporting
observation, support `0.400 → 0.640`, against the unchanged `0.600` — and
asserts that the authored description `"distance then repair"` reaches the
prediction rather than the generated fallback, and that the two observations
resolve to one lineage.

`test_trajectory_on_a_proposal_cannot_create_a_prediction` asserts the
converse: trajectory content on a sub-threshold lineage, with an authored
`initial_support` of 0.95 that R6 does not consult, yields support 0.400 and no
prediction. A prediction appearing there would indicate that trajectory content
had become a support-bearing input and that R6 was no longer the sole source of
support.

## E-1.5 Scope

This errata changes no governed rule, threshold, outcome name, identity
semantics or architecture. It retains a content-only field omitted by the
v1.5.4 port definition, and records an open R6 threshold consequence.
