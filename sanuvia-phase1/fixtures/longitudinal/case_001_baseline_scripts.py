"""Deterministic baseline test-double scripts for Case 001.

IMPORTANT — these are **stylized test-double data**, not empirical LLM output.
They model the *documented baseline archetypes* (Sanuvia Phase 1 Prototype Brief,
Expected Behaviour, Conditions 1 & 2) so the demonstrator is byte-identically
reproducible in CI without a network/vendor. They make **no** empirical claim
about how a real foundation model behaves; real behaviour is obtained only via
the opt-in ``ExternalLanguageModel``.

* Stateless archetype: re-derives a fresh single reading each turn (a new
  hypothesis id every interaction → zero retention); at the empty seq-5 it has no
  current evidence and produces generic reassurance / a re-explain prompt.
* Transcript archetype: converges on ONE "most-resolved" narrative (a single,
  stable hypothesis id — it never holds the competing H3/H4), and performs
  textual continuity **without** citing an evidence id (an unsupported-memory
  claim).

There is one response per interaction (six interactions), in order.
"""

from __future__ import annotations

from sanuvia_phase1.language_models import ScriptedLanguageModel

# One JSON object per interaction (seq-1 .. seq-6).
STATELESS_SCRIPT: tuple[str, ...] = (
    '{"best_explanations": ["Person 1 is weighing leaving over lack of growth."],'
    ' "competing_hypotheses_held": [{"id": "stateless-t1", "statement":'
    ' "Considering exit over lack of growth."}],'
    ' "question_asked": "What outcome are you hoping for?",'
    ' "continuity_claims": []}',
    '{"best_explanations": ["There is a disagreement about governance and fatigue'
    ' with proving worth."],'
    ' "competing_hypotheses_held": [{"id": "stateless-t2", "statement":'
    ' "Governance disagreement; tired of proving worth."}],'
    ' "question_asked": "Can you say more about the disagreement?",'
    ' "continuity_claims": []}',
    '{"best_explanations": ["Person 1 feels at a comparable level to peers."],'
    ' "competing_hypotheses_held": [{"id": "stateless-t3", "statement":'
    ' "Feels comparable to peers."}],'
    ' "question_asked": null, "continuity_claims": []}',
    '{"best_explanations": ["Person 1 wants to build in 2027."],'
    ' "competing_hypotheses_held": [{"id": "stateless-t4", "statement":'
    ' "Wants to build rather than seek promotion."}],'
    ' "question_asked": null, "continuity_claims": []}',
    # seq-5: no current evidence -> generic reassurance / re-explain (Condition 1).
    '{"best_explanations": ["A promotion does not define your worth."],'
    ' "competing_hypotheses_held": [],'
    ' "question_asked": "Could you re-explain what has been happening?",'
    ' "continuity_claims": []}',
    '{"best_explanations": ["Person 1 feels better after reframing and will keep'
    ' adapting."],'
    ' "competing_hypotheses_held": [{"id": "stateless-t6", "statement":'
    ' "Feels better; will keep adapting."}],'
    ' "question_asked": null, "continuity_claims": []}',
)

TRANSCRIPT_SCRIPT: tuple[str, ...] = (
    '{"best_explanations": ["Person 1 is considering leaving over lack of growth."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Considering exit over lack of growth."}],'
    ' "question_asked": null, "continuity_claims": []}',
    '{"best_explanations": ["The core issue is a governance disagreement with MD-1."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Governance disagreement is the core issue."}],'
    ' "question_asked": null,'
    ' "continuity_claims": [{"text": "You mentioned earlier you were considering'
    ' leaving.", "cited_evidence_id": null}]}',
    '{"best_explanations": ["Person 1 is underrecognised relative to peers."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Underrecognised relative to peers."}],'
    ' "question_asked": null,'
    ' "continuity_claims": [{"text": "As you have said throughout, the governance'
    ' fit is the theme.", "cited_evidence_id": null}]}',
    '{"best_explanations": ["Person 1 has decided to move on to build elsewhere."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Has decided to move on to build."}],'
    ' "question_asked": null,'
    ' "continuity_claims": [{"text": "This confirms the exit direction you set out'
    ' at the start.", "cited_evidence_id": null}]}',
    # seq-5: no new text; re-derives the same resolved narrative from transcript.
    '{"best_explanations": ["Person 1 has decided to move on to build elsewhere."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Has decided to move on to build."}],'
    ' "question_asked": null,'
    ' "continuity_claims": [{"text": "As established, the decision is to leave.",'
    ' "cited_evidence_id": null}]}',
    '{"best_explanations": ["Person 1 feels resolved and ready to move on."],'
    ' "competing_hypotheses_held": [{"id": "transcript-narrative", "statement":'
    ' "Resolved and ready to move on."}],'
    ' "question_asked": null,'
    ' "continuity_claims": [{"text": "This closes the arc you described earlier.",'
    ' "cited_evidence_id": null}]}',
)


def deterministic_language_models() -> tuple[ScriptedLanguageModel, ScriptedLanguageModel]:
    """The (stateless, transcript) deterministic doubles for Case 001."""
    return (
        ScriptedLanguageModel(STATELESS_SCRIPT),
        ScriptedLanguageModel(TRANSCRIPT_SCRIPT),
    )
