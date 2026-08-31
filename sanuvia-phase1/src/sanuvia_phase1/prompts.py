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

_EXTRACTION_SCHEMA = (
    '{"evidence": [{"observation": string, "evidence_class": '
    '"narrative|reflective|behavioural|contradictory|missing|failed_acquisition", '
    '"reliability": number[0..1], "classification_confidence": number[0..1], '
    '"provenance_confidence": number[0..1], "text_span": string|null}]}'
)

_APPRAISAL_SCHEMA = (
    '{"supports": [hypothesis_id], "contradicts": [hypothesis_id], '
    '"proposals": [{"hypothesis_id": string, "statement": string, '
    '"initial_support": number[0..1], "supporting_evidence_ids": [evidence_id]}]}'
)

_BASELINE_SCHEMA = (
    '{"best_explanations": [string], '
    '"competing_hypotheses_held": [{"id": string, "statement": string}], '
    '"question_asked": string|null, '
    '"continuity_claims": [{"text": string, "cited_evidence_id": string|null}]}'
)


# --- stable ids ---------------------------------------------------------------

EXTRACTION_PROMPT_ID = "extraction.observations.v1"
APPRAISAL_PROMPT_ID = "appraisal.support-contradict-propose.v1"
BASELINE_PROMPT_ID = "baseline.reasoning.v1"  # shared by both baselines

EXTRACTION_SCHEMA_ID = "schema.extraction.v1"
APPRAISAL_SCHEMA_ID = "schema.appraisal.v1"
BASELINE_SCHEMA_ID = "schema.baseline.v1"  # shared by both baselines


PROMPTS: dict[str, PromptSpec] = {
    spec.prompt_id: spec
    for spec in (
        PromptSpec(EXTRACTION_PROMPT_ID, "evidence_extraction", _EXTRACTION_SYSTEM),
        PromptSpec(APPRAISAL_PROMPT_ID, "evidence_appraisal", _APPRAISAL_SYSTEM),
        PromptSpec(BASELINE_PROMPT_ID, "baseline", _BASELINE_SYSTEM),
    )
}

SCHEMAS: dict[str, SchemaSpec] = {
    spec.schema_id: spec
    for spec in (
        SchemaSpec(EXTRACTION_SCHEMA_ID, "evidence_extraction", _EXTRACTION_SCHEMA),
        SchemaSpec(APPRAISAL_SCHEMA_ID, "evidence_appraisal", _APPRAISAL_SCHEMA),
        SchemaSpec(BASELINE_SCHEMA_ID, "baseline", _BASELINE_SCHEMA),
    )
}

# Recorded hashes — the drift guard. If a prompt text is edited, its live hash no
# longer matches, and both `verify_prompt_integrity()` and the preflight fail.
EXPECTED_PROMPT_SHA256: dict[str, str] = {
    EXTRACTION_PROMPT_ID: "a45066719aa656a3ef544d6184988fd7e42461609ef9ffbb870cf14d218697d1",
    APPRAISAL_PROMPT_ID: "790e63375fbfb49575924514b3fc277793e23ff68a6e116ffde4a3aa864e8398",
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
