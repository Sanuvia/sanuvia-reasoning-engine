# Technical Design v1.5.4 — Addendum E-1, Amendment A-1

**Subject:** Trajectory precedence
**Status:** Amendment to Addendum E-1. Recording existing behaviour; not a new rule.
**Date:** 2026-10-05

**Amends:** `Sanuvia-Phase1-SemanticState-v0.2-Technical-Design-v1.5.4-Addendum-E1.md`
SHA-256 `a06ca426a48aa3750d5395deae202ab839d807387030e5adf5346405bed4533d`

The original addendum's bytes are preserved unchanged. This amendment is a
separate document with its own hash, so the E-1 reference in any prior record
stays valid.

---

## A-1.1 What E-1 left unstated

E-1 established that `CandidateProposal.predicted_trajectory` is content-only.
It did not state what happens when **two** trajectory descriptions compete for
one prediction. Two such cases exist in the implementation. Neither was
introduced by the errata; both were present and undocumented, which is the
defect this amendment closes. The silence was the problem, not the behaviour.

Nothing here adds prediction-lifecycle semantics, which locked §8 defers.
Trajectory content remains content: `traj_hints` is read only by
`_regenerate_predictions`, and only **after** `prediction_support_threshold`
has already admitted the hypothesis. It does not affect support, uncertainty,
derived state, inquiry or identity.

## A-1.2 Across interactions — a new hint replaces the prior trajectory

**Rule.** When a newly authored trajectory exists for a hypothesis, it
**replaces** the description a prior prediction established. When no new hint
is authored, the prior trajectory **carries forward**.

**Authority: preservation.** This was verified against base commit `9883e6c`,
where `_regenerate_predictions` already evaluated

```
run.traj_hints.get(hid) or prior_trajectory.get(hid) or <generated>
```

New-hint-replaces-prior is therefore the pre-existing behaviour, and §8's
"deferred means preserved unchanged" governs. No code changed for this rule.

**Correction of record.** The comment at that site read "a trajectory kind,
once established for a hypothesis, carries forward across versions". That
describes only the second half — the no-new-hint case — and reads as the
opposite precedence for the first. The comment was inaccurate at base and is
corrected; the behaviour is not.

## A-1.3 Within one interaction — last wins

**Rule.** When several proposals in one interaction resolve onto the same
durable lineage and more than one carries a trajectory, the **last** hint in
deterministic order wins.

**Authority: preservation.** At base the hint was keyed by the proposal's own
id and **assigned**, so where two proposals in one batch shared a key the last
hint won. The repair at `f522923` had changed this to `setdefault`, making it
first-wins. That was an undocumented change of behaviour with no stated
criterion behind it, so it is reverted to assignment.

**Determinism.** The order is fixed and is the same order adjudication uses:
ascending evidence batch index, then response order within each appraisal.
Last-wins is therefore reproducible, not incidental.

**Reachability.** The collision is newly *reachable* rather than new in kind.
Several response-local proposals can now resolve onto one durable lineage via
`MATCH_EXISTING`. It cannot arise within a single appraisal response:
complete-plan check 3 rejects two proposals normalising to the same statement
and signature as `DUPLICATE_HYPOTHESIS_PROPOSAL`. It arises across the several
observations of one interaction.

**No new outcome.** A conflict between two authored hints produces no visible
governed outcome, no warning and no record of its own. Introducing one would
be prediction-lifecycle semantics, which §8 defers. Both hints remain in the
raw appraiser responses the audit preserves, so the discarded one is
recoverable.

## A-1.4 Scope

No threshold, reliability, support, uncertainty, inquiry or identity behaviour
is changed. `prediction_support_threshold` remains 0.600 and is still applied
before any hint is consulted. The set of conditions under which a prediction
is created is unchanged.

## A-1.5 Verification

| Rule | Test |
|---|---|
| A-1.2 replace | `test_across_interactions_a_new_hint_replaces_the_prior_trajectory` |
| A-1.2 carry forward | `test_absent_a_new_hint_the_prior_trajectory_carries_forward` |
| A-1.3 last wins | `test_within_one_interaction_the_last_hint_wins` |

The carry-forward test authors its hint through the interaction at which the
prediction first forms — support `0.4 → 0.64` crossing the unchanged `0.600` —
then goes silent. Authoring only at the first interaction would prove nothing,
because no prediction exists then and there is no prior to carry.
