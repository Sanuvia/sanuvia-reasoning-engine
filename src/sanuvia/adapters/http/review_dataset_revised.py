"""The review dataset, revised for the v1.5.4 semantic-state engine.

----------------------------------------------------------------------------
WHY THIS IS A SEPARATE MODULE
----------------------------------------------------------------------------

``review_dataset`` is **evidence**. It is the dataset the Phase 0 engine was
reviewed against, and it stays byte-identical to its state at base commit
``9883e6c`` so that any later claim about what changed can be checked against
it. Nothing here edits it.

This module is a thin **override layer**, not a copy. It deep-copies the
original and applies an explicitly enumerated list of expectation changes.
That shape is deliberate:

* a copy could drift silently; an override list cannot. Every difference
  between the original and the revised dataset is a row in ``REVISIONS``,
  and ``assert_only_declared_changes()`` proves there are no others;
* each row carries its classification and its derivation, so the dataset
  and the reasoning for changing it cannot become separated.

----------------------------------------------------------------------------
CLASSIFICATION SCHEME
----------------------------------------------------------------------------

M   mechanical identifier change (authored id -> engine-issued durable id)
A1  R6 numeric consequence (a value moves; nothing discrete changes)
A2  R6 threshold-discrete consequence (a value crosses, or stops crossing,
    an **unchanged** threshold, so a discrete outcome changes)
D   consequence of another approved v1.5.4 rule
B   requires a governance decision -- NOT APPLIED HERE
U   unexplained -- treated as a defect, NOT APPLIED HERE

Only M / A1 / A2 / D changes are applied. B and U are recorded in
``REFERRED_TO_GOVERNANCE`` and deliberately left unchanged, so the revised
dataset still fails on them and the open question stays visible.

----------------------------------------------------------------------------
THE GOVERNING RULE BEHIND EVERY APPLIED CHANGE
----------------------------------------------------------------------------

R6. A new lineage's support is derived from the triggering observation:

    support = support_after_support(0.0, reliability, learning_rate)
            = 0 + 0.5 * reliability * (1 - 0)

The dataset's authored ``initial_support`` (the ``_p(...)`` default of 0.4)
is **no longer consulted**. Every applied change below follows from that one
approved rule plus two things that are **unchanged**:
``prediction_support_threshold`` (0.6) and ``aggregate_model_uncertainty``.

No threshold was altered. No fixture was altered. No expectation was changed
because the implementation happened to emit something different -- each one is
derived from R6 arithmetic that can be recomputed from the evidence specs.
"""

from __future__ import annotations

import copy
from typing import Any

from . import review_dataset

#: One applied expectation change.
#:
#: ``case``/``step`` locate it (``step`` is 1-based, matching the dataset's own
#: step numbering), ``field`` names the expectation key, ``before``/``after``
#: are the values, and ``derivation`` shows the arithmetic.
REVISIONS: tuple[dict[str, Any], ...] = (
    {
        "case": "dataset-competing-resolve",
        "step": 2,
        "field": "predictions",
        "before": ["H_reassurance"],
        "after": [],
        "classification": "A2",
        "derivation": (
            "H_reassurance is proposed at step 1 from evidence of reliability "
            "0.7, so R6 gives it 0.5*0.7 = 0.35 (not the authored 0.4). Step 2 "
            "supports it at reliability 0.7: 0.35 + 0.5*0.7*(1-0.35) = 0.5775, "
            "which is below the unchanged threshold 0.6, so no prediction forms. "
            "Step 3 supports it at 0.8: 0.5775 + 0.5*0.8*(1-0.5775) = 0.7465, "
            "which crosses. The prediction therefore appears one step later "
            "than authored; step 3 onward is unchanged and still passes."
        ),
    },
    {
        "case": "dataset-oscillating-evidence",
        "step": 2,
        "field": "predictions",
        "before": ["H_pursue"],
        "after": [],
        "classification": "A2",
        "derivation": (
            "H_pursue reaches 0.5775 at step 2 by the same R6 arithmetic as "
            "dataset-competing-resolve, which is below the unchanged 0.6."
        ),
    },
    {
        "case": "dataset-oscillating-evidence",
        "step": 3,
        "field": "predictions",
        "before": ["H_pursue", "H_withdraw"],
        "after": [],
        "classification": "A2",
        "derivation": (
            "At step 3 both rivals stand at 0.5775, so neither crosses 0.6. "
            "The oscillation the case demonstrates is unaffected: the two "
            "hypotheses still rise and fall against each other, they simply do "
            "so below the prediction threshold at this step."
        ),
    },
    {
        "case": "dataset-oscillating-evidence",
        "step": 4,
        "field": "predictions",
        "before": ["H_pursue", "H_withdraw"],
        "after": ["H_pursue"],
        "classification": "A2",
        "derivation": (
            "Step 4 lifts H_pursue to 0.725, which crosses 0.6, while "
            "H_withdraw remains at 0.5775 and does not. One prediction forms, "
            "not two. This sharpens rather than weakens the case: the leader "
            "is now the only hypothesis carrying a prediction."
        ),
    },
    {
        "case": "dataset-high-uncertainty-converges",
        "step": 2,
        "field": "predictions",
        "before": ["H_anx"],
        "after": [],
        "classification": "A2",
        "derivation": (
            "Three candidates open at step 1 from reliability-0.6 evidence, so "
            "R6 gives each 0.5*0.6 = 0.30. Step 2 supports H_anx at reliability "
            "0.7: 0.30 + 0.5*0.7*(1-0.30) = 0.545, below the unchanged 0.6. "
            "Convergence still occurs, one step later."
        ),
    },
    {
        "case": "dataset-failed-acquisition",
        "step": 3,
        "field": "uncertainty",
        "before": "down",
        "after": "up",
        # A1, not A2. No threshold is crossed anywhere in this change: the
        # uncertainty value moves continuously (0.400 -> 0.4725) and the trend
        # label follows from comparing two computed values. A2 is reserved for
        # a value crossing, or ceasing to cross, an unchanged threshold -- which
        # is what the five prediction revisions above do against the 0.600
        # prediction threshold. Reporting classification only; the revised
        # values and the scoring behaviour are unchanged.
        "classification": "A1",
        "authority": "approved R6 support derivation; uncertainty trend decided",
        "derivation": (
            "A leader change, not a drift. UNCHANGED INPUTS: the evidence specs, "
            "their reliabilities (0.7, 0.3, 0.6, 0.8), the support learning rate "
            "(0.5) and aggregate_model_uncertainty ((1-top)+rival)/2 are all "
            "exactly as authored; only R6's support derivation differs.\n"
            "Step 2 under R6: H_topic = 0.5*0.7 = 0.35; H_avoidance and "
            "H_external open from the reliability-0.3 failed acquisition at "
            "0.5*0.3 = 0.15 each. Ordered 0.35/0.15/0.15, so "
            "u2 = ((1-0.35)+0.15)/2 = 0.400.\n"
            "Step 3 supports H_avoidance at reliability 0.6: "
            "0.15 + 0.5*0.6*(1-0.15) = 0.405, which OVERTAKES H_topic at 0.35. "
            "Ordered 0.405/0.35/0.15, so u3 = ((1-0.405)+0.35)/2 = 0.4725.\n"
            "0.400 -> 0.4725 is a RISE. Pre-R6 the authored 0.4 starting points "
            "let H_avoidance reach 0.4 + 0.5*0.6*0.6 = 0.58 and win outright, "
            "giving ((1-0.58)+0.4)/2 = 0.41 and a fall.\n"
            "The rise is what the unchanged scoring function is specified to "
            "do: scoring.py states 'two strongly-supported rivals (genuine "
            "competition) -> HIGHER uncertainty', and step 3 produces exactly "
            "that near-tie, 0.405 against 0.35. The case's purpose -- a failed "
            "acquisition yields competing candidates rather than a single "
            "default -- is unaffected and still holds."
        ),
    },
)

#: Narrative prose corrected to match the applied changes. These are
#: descriptive text, not machine-checked expectations, but leaving them saying
#: the opposite of the step table would reintroduce exactly the drift the
#: dataset's own docstring warns about.
NARRATIVE_REVISIONS: tuple[dict[str, str], ...] = (
    {
        "case": "dataset-failed-acquisition",
        "before": "A topic-avoidance reading opens. A failed acquisition (unanswered prompt) yields two competing candidates rather than a default; an inquiry appears. One candidate is then supported and leads with a prediction.",
        "after": "A topic-avoidance reading opens. A failed acquisition (unanswered prompt) yields two competing candidates rather than a default; an inquiry appears. Support for one candidate then brings it to a near-tie with the original reading (0.405 against 0.35), which raises uncertainty before further evidence resolves it and the leader carries a prediction.",
    },
    {
        "case": "dataset-competing-resolve",
        "before": "Steps 2–3 strengthen reassurance past threshold (prediction; inquiry clears).",
        "after": "Steps 2–3 strengthen reassurance, crossing the prediction threshold at step 3 (inquiry clears).",
    },
)

#: Recorded, NOT applied. Each needs a governance decision.
#:
#: Empty: the one item previously held here -- dataset-failed-acquisition step 3
#: -- was decided and is now applied as revision 6 below.
REFERRED_TO_GOVERNANCE: tuple[dict[str, Any], ...] = ()


def _revised() -> list[dict[str, Any]]:
    cases = copy.deepcopy(review_dataset.DATASET)
    by_id = {c["id"]: c for c in cases}

    for rev in REVISIONS:
        case = by_id[rev["case"]]
        exp = case["step_expectations"][rev["step"] - 1]
        assert exp[rev["field"]] == rev["before"], (
            f"{rev['case']} step {rev['step']}: original "
            f"{rev['field']}={exp[rev['field']]!r}, revision expected "
            f"{rev['before']!r}. The original dataset changed underneath this "
            f"override layer; re-derive before proceeding."
        )
        exp[rev["field"]] = copy.deepcopy(rev["after"])

    for nrev in NARRATIVE_REVISIONS:
        case = by_id[nrev["case"]]
        assert nrev["before"] in case["narrative"], (
            f"{nrev['case']}: narrative text to revise not found"
        )
        case["narrative"] = case["narrative"].replace(nrev["before"], nrev["after"])

    return cases


DATASET: list[dict[str, Any]] = _revised()


def assert_only_declared_changes() -> None:
    """Prove the revised dataset differs from the original ONLY as declared.

    This is the guarantee the override shape exists to provide: it is not
    possible to quietly change an expectation here without adding a row to
    ``REVISIONS`` and stating its classification and derivation.
    """
    declared = {(r["case"], r["step"], r["field"]) for r in REVISIONS}
    found: set[tuple[str, int, str]] = set()

    original = {c["id"]: c for c in review_dataset.DATASET}
    for case in DATASET:
        base = original[case["id"]]
        assert case["evidence_specs"] == base["evidence_specs"], (
            f"{case['id']}: evidence specs must never be revised -- the "
            f"stimulus is the dataset, only the expectation may change"
        )
        for i, (exp, bexp) in enumerate(
            zip(case["step_expectations"], base["step_expectations"]), start=1
        ):
            for field in exp:
                if exp[field] != bexp[field]:
                    found.add((case["id"], i, field))

    undeclared = found - declared
    assert not undeclared, f"undeclared expectation changes: {sorted(undeclared)}"
    unused = declared - found
    assert not unused, f"declared revisions that changed nothing: {sorted(unused)}"


def catalogue() -> list[dict[str, Any]]:
    """Catalogue entries, with the original's own summaries."""
    return review_dataset.catalogue()


def get_case(sample_id: str) -> dict[str, Any] | None:
    """A case from the revised dataset, with the original's purpose block.

    Mirrors ``review_dataset.get_case``: the harness reads ``purpose_block``
    to show a case's purpose before it is run. The purpose text is unrevised --
    none of the applied changes alter what any case is for.
    """
    for case in DATASET:
        if case["id"] == sample_id:
            out = copy.deepcopy(case)
            out["purpose_block"] = copy.deepcopy(review_dataset.PURPOSE.get(sample_id))
            return out
    return None
