"""Prompts and schemas as immutable, identified experimental artifacts.

Prompts and response schemas can change a model's behaviour, so they are treated
as versioned artifacts with stable IDs and content hashes. The prompt *texts*
already live with the external adapters (the extraction / appraisal SYSTEM prompts
and the shared baseline SYSTEM prompt); this module does NOT rewrite them — it
registers them under stable IDs and records their SHA-256 so drift is detectable.

Fairness note: the stateless and transcript-context baselines intentionally share
the SAME baseline prompt (``baseline.reasoning.v1``). The only difference between
those conditions is the *context* each is given (current turn vs accumulated
transcript), never the prompt — so we register one baseline prompt id and both
baseline ModelSpecs reference it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .conditions._prompt import SYSTEM as _BASELINE_SYSTEM
from .evidence_appraisers.external import SYSTEM as _APPRAISAL_SYSTEM
from .evidence_extractors.external import SYSTEM as _EXTRACTION_SYSTEM
from .identity_resolvers.external import SYSTEM as _IDENTITY_SYSTEM


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PromptSpec:
    prompt_id: str
    role: str
    text: str

    @property
    def content_sha256(self) -> str:
        return sha256(self.text)


@dataclass(frozen=True, slots=True)
class SchemaSpec:
    schema_id: str
    role: str
    contract: str

    @property
    def content_sha256(self) -> str:
        return sha256(self.contract)


# --- schema contracts (authored here; MUST match validation.py enforcement) ---

# v2 (§2 E, R2 bounded extractor authority). Adds the semantic standing the
# extractor may PROPOSE -- role, subject_kind, subject -- and nothing else.
# source_kind/source_id are absent by design: who spoke is a contextual fact
# the application supplies and never accepts from the model.
_EXTRACTION_SCHEMA = (
    '{"evidence": [{"observation": string, "evidence_class": '
    '"narrative|reflective|behavioural|contradictory|missing|failed_acquisition", '
    '"reliability": number[0..1], "classification_confidence": number[0..1], '
    '"provenance_confidence": number[0..1], "text_span": string|null, '
    '"role": "event_observation|account|response_or_resonance|meta_instruction", '
    '"subject_kind": "participant|dyad|third_party|none", '
    '"subject": string|null}]}'
)

# v3 (Technical Design v1.5.4 §2 C / §2 H). References are request-scoped
# handles; a
# proposal is a response-local label plus a statement. Three v1 fields are
# retired because none is the model's to decide: hypothesis_id (the engine
# issues durable identity), initial_support (R6 derives it) and
# supporting_evidence_ids (support attaches to the observation under appraisal).
_APPRAISAL_SCHEMA = (
    '{"supports": [handle], "contradicts": [handle], '
    '"proposals": [{"local_ref": string, "statement": string, '
    '"signature": {"subject": participant_label, "claim_class": string, '
    '"stance": string, "temporal_scope": string|null}}]}'
)

# R1 bounded identity resolution (§2 G case 4). Refs are resolution-scoped: no
# durable HypothesisId crosses this boundary.
_IDENTITY_SCHEMA = (
    '{"outcome": "match_existing|refine_existing|distinct_new|'
    'ambiguous_review_required", "matched_ref": string|null, '
    '"rationale": string, "confidence": number[0..1]}'
)

_BASELINE_SCHEMA = (
    '{"best_explanations": [string], '
    '"competing_hypotheses_held": [{"id": string, "statement": string}], '
    '"question_asked": string|null, '
    '"continuity_claims": [{"text": string, "cited_evidence_id": string|null}]}'
)


# --- stable ids ---------------------------------------------------------------

EXTRACTION_PROMPT_ID = "extraction.observations.v2"
APPRAISAL_PROMPT_ID = "appraisal.support-contradict-propose.v3"
IDENTITY_PROMPT_ID = "identity.r1.bounded.v1"
BASELINE_PROMPT_ID = "baseline.reasoning.v1"  # shared by both baselines

EXTRACTION_SCHEMA_ID = "schema.extraction.v2"
APPRAISAL_SCHEMA_ID = "schema.appraisal.v3"
IDENTITY_SCHEMA_ID = "schema.identity.v1"
BASELINE_SCHEMA_ID = "schema.baseline.v1"  # shared by both baselines


PROMPTS: dict[str, PromptSpec] = {
    spec.prompt_id: spec
    for spec in (
        PromptSpec(EXTRACTION_PROMPT_ID, "evidence_extraction", _EXTRACTION_SYSTEM),
        PromptSpec(APPRAISAL_PROMPT_ID, "evidence_appraisal", _APPRAISAL_SYSTEM),
        PromptSpec(IDENTITY_PROMPT_ID, "identity_resolution", _IDENTITY_SYSTEM),
        PromptSpec(BASELINE_PROMPT_ID, "baseline", _BASELINE_SYSTEM),
    )
}

SCHEMAS: dict[str, SchemaSpec] = {
    spec.schema_id: spec
    for spec in (
        SchemaSpec(EXTRACTION_SCHEMA_ID, "evidence_extraction", _EXTRACTION_SCHEMA),
        SchemaSpec(APPRAISAL_SCHEMA_ID, "evidence_appraisal", _APPRAISAL_SCHEMA),
        SchemaSpec(IDENTITY_SCHEMA_ID, "identity_resolution", _IDENTITY_SCHEMA),
        SchemaSpec(BASELINE_SCHEMA_ID, "baseline", _BASELINE_SCHEMA),
    )
}

# Recorded hashes — the drift guard. If a prompt text is edited, its live hash no
# longer matches, and both `verify_prompt_integrity()` and the preflight fail.
EXPECTED_PROMPT_SHA256: dict[str, str] = {
    EXTRACTION_PROMPT_ID: "08d015d89737a539f359a47b3147fe20893557977e73cd7fa91df11a68e32844",
    APPRAISAL_PROMPT_ID: "d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c",
    IDENTITY_PROMPT_ID: "45d0675753216e1439230776ffbf2150f82c760f04dd276b87344276415398d6",
    BASELINE_PROMPT_ID: "3557977b65552a1a19b3cff3a53f58b93c0efb6e802b821abe0b063cf03943bc",
}


def prompt(prompt_id: str) -> PromptSpec:
    if prompt_id not in PROMPTS:
        raise KeyError(f"unknown prompt id: {prompt_id!r}")
    return PROMPTS[prompt_id]


def schema(schema_id: str) -> SchemaSpec:
    if schema_id not in SCHEMAS:
        raise KeyError(f"unknown schema id: {schema_id!r}")
    return SCHEMAS[schema_id]


def verify_prompt_integrity() -> list[str]:
    """Return a list of drift problems (empty when every prompt matches its
    recorded hash). Detects casual prompt rewriting between conditions/runs."""
    problems: list[str] = []
    for prompt_id, expected in EXPECTED_PROMPT_SHA256.items():
        spec = PROMPTS.get(prompt_id)
        if spec is None:
            problems.append(f"prompt {prompt_id!r} is missing from the registry")
            continue
        actual = spec.content_sha256
        if actual != expected:
            problems.append(
                f"prompt {prompt_id!r} content drifted: expected {expected[:12]}…, "
                f"got {actual[:12]}…"
            )
    return problems
