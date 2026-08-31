"""Shared prompt scaffolding for the foundation-model baseline conditions.

The system prompt states the **constrained-JSON response contract** (§9). It is
used by the real ``ExternalLanguageModel``; the deterministic
``ScriptedLanguageModel`` ignores it. The prompt/response contract is a Phase 1
governance item (provider/model/prompt not yet approved).
"""

from __future__ import annotations

from ..case import CaseEvidence

SYSTEM = (
    "You are a reasoning baseline condition in an internal experiment. Read the "
    "provided evidence and respond with ONLY a single JSON object of the form:\n"
    '{"best_explanations": [string],'
    ' "competing_hypotheses_held": [{"id": string, "statement": string}],'
    ' "question_asked": string|null,'
    ' "continuity_claims": [{"text": string, "cited_evidence_id": string|null}]}\n'
    "Cite an evidence id in a continuity claim only if the evidence was actually "
    "shown to you. Do not output any prose outside the JSON object."
)

INSTRUCTION = "Return the JSON object now."


def render_lines(evidence: tuple[CaseEvidence, ...]) -> list[str]:
    """One 'ref: text' line per evidence record (raw observation text only)."""
    return [f"{ev.ref}: {ev.text}" for ev in evidence]


def render_current(evidence: tuple[CaseEvidence, ...]) -> str:
    """Context for the STATELESS baseline: the current interaction's evidence only."""
    lines = render_lines(evidence)
    return "\n".join(lines) if lines else "(no new evidence this interaction)"
