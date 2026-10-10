"""Authored-id -> durable-id mapping for Phase 1 fixture assertions.

Shared by every Phase 1 test that asserts against a fixture's authored
hypothesis ids.

**Derived independently of ``attribution`` (B-1).** These mappings used to
split the lineage attribution, which only worked while attribution wrongly
carried identity. ``attribution`` is now the governed voice label (§2 H) and is
identical across lineages, so it carries nothing to split.

The mapping comes from the authored **statement** instead: each fixture
proposal authors a statement alongside its id, and the engine stores that
statement verbatim on the hypothesis it founds. The match is exact string
equality -- no similarity, no normalisation, no heuristic.
"""

from __future__ import annotations

from typing import Any


def durable_ids(store: Any, case: Any) -> dict[str, str]:
    """Authored fixture hypothesis id -> engine-issued durable id."""
    by_statement: dict[str, str] = {}
    for hypothesis in store.hypotheses.list_for_subject(
        case.subject_id, space_id=case.space_id
    ):
        by_statement.setdefault(hypothesis.statement, hypothesis.hypothesis_id)

    mapping: dict[str, str] = {}
    for appraisal in case.appraisal_script.values():
        for proposal in appraisal.proposals:
            durable = by_statement.get(proposal.statement)
            if durable is not None:
                mapping[str(proposal.hypothesis_id)] = durable
    return mapping
