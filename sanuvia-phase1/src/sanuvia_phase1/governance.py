"""Formal, immutable governance / freeze record for the Phase 1 real run.

This is the single source of truth for what has been **frozen/approved** versus
what is **pending governance approval**. It exists so that a real run is
pre-registered: the approved protocol is pinned by a content hash
(:func:`freeze_record_sha256`), and any change to a frozen value changes that hash.

Governance rule (enforced by construction): unresolved values are recorded as
``PENDING_GOVERNANCE_APPROVAL`` with a ``value`` of ``None`` — never silently
chosen. Values marked ``FROZEN`` are those already fixed by the authoritative
documents / the approved Phase 1 protocol, and each cites its source. Nothing in
this module runs a model, downloads anything, or changes Phase 0, Case 001,
prompts, or evaluation criteria.

Version history is preserved for audit (:data:`FREEZE_RECORD_HISTORY`); a new
version is a new pinned hash, never a silent overwrite.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from . import prompts

# Neutral source labels for approved decisions (no personal names).
APPROVAL_SOURCE = "Phase 1 protocol approval (2026-08-23)"
RUN001_APPROVAL_SOURCE = "Phase 1 Run-001 governance approval (2026-08-26)"
RUN001_VERIFICATION_SOURCE = "Run-001 artifact verification (2026-08-31)"

# Current record version and the audit trail of prior pinned hashes.
FREEZE_RECORD_VERSION = "3.0-run001-verified"
FREEZE_RECORD_HISTORY: tuple[tuple[str, str], ...] = (
    # (version, freeze_record_sha256) — never overwritten.
    ("1.0-structure", "8a8841ba3003bbab0aadff8fa0f3ccceab6ec965cf209d5cc2f77ae30a91a44f"),
    ("2.0-run001", "0291e6e4b0452c4a4ca32daa4424e32982919b8da0558dc5b41d39644d8fe4ad"),
)


class GovernanceStatus(str, Enum):
    FROZEN = "frozen"
    PENDING_GOVERNANCE_APPROVAL = "pending_governance_approval"


@dataclass(frozen=True, slots=True)
class GovernanceItem:
    key: str
    description: str
    status: GovernanceStatus
    value: str | None       # the frozen value, or None while pending
    source: str             # citation for a frozen value / where it will be set
    blocking: bool          # if pending, does it block the real run?

    @property
    def is_blocking_now(self) -> bool:
        return (
            self.blocking
            and self.status is GovernanceStatus.PENDING_GOVERNANCE_APPROVAL
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "description": self.description,
            "status": self.status.value,
            "value": self.value,
            "source": self.source,
            "blocking": self.blocking,
        }


def _frozen(key: str, description: str, value: str, source: str) -> GovernanceItem:
    return GovernanceItem(key, description, GovernanceStatus.FROZEN, value, source, False)


def _pending(key: str, description: str, source: str, *, blocking: bool = True) -> GovernanceItem:
    return GovernanceItem(
        key, description, GovernanceStatus.PENDING_GOVERNANCE_APPROVAL, None, source, blocking
    )


def _p(prompt_id: str) -> str:
    return f"{prompt_id}@sha256:{prompts.prompt(prompt_id).content_sha256}"


def _s(schema_id: str) -> str:
    return f"{schema_id}@sha256:{prompts.schema(schema_id).content_sha256}"


# The canonical freeze record. Order is stable (it feeds the content hash).
FREEZE_RECORD: tuple[GovernanceItem, ...] = (
    # --- Experimental structure (approved) ---
    _frozen(
        "experimental_structure",
        "Exactly three conditions; no new experimental conditions",
        "sanuvia_persistent | fm_stateless | fm_transcript",
        f"Experiment Manifest §2; {APPROVAL_SOURCE}",
    ),
    _frozen(
        "same_sequential_evidence",
        "All conditions process the same ordered evidence sequence",
        "identical seq labels enforced by the pipeline fairness guard",
        "Experiment Manifest §2/§8",
    ),
    _frozen(
        "case_001_unchanged",
        "Case 001 fixture is unchanged (6 interactions; seq-5 is an empty hold)",
        "fixtures/longitudinal/case_001.py",
        "Experiment Manifest §8",
    ),
    _frozen(
        "phase0_frozen",
        "Phase 0 engine is frozen; consumed only via its public API",
        "src/sanuvia/** unmodified; import isolation enforced",
        "repo policy; preflight phase0_import_frozen",
    ),
    _frozen(
        "provider_local_only",
        "Provider is local only (no cloud, no API key, no download)",
        "local_qwen",
        "Experiment Manifest §3",
    ),
    # --- Model / serving (approved for Run 001) ---
    _frozen("model_family", "Model family/name", "Qwen3-4B", RUN001_APPROVAL_SOURCE),
    _frozen("serving_runtime_backend", "Serving / runtime / backend arrangement",
            "llama.cpp (GGUF)", RUN001_APPROVAL_SOURCE),
    _frozen("quantization", "Model quantization", "Q4_K_M", RUN001_APPROVAL_SOURCE),
    _frozen("context_window", "Context window", "8192", RUN001_APPROVAL_SOURCE),
    _frozen("max_output_tokens", "Max output tokens", "512", RUN001_APPROVAL_SOURCE),
    _frozen("stop_sequences", "Stop sequences", "none", RUN001_APPROVAL_SOURCE),
    # --- Generation parameters (approved for Run 001) ---
    _frozen("temperature", "Sampling temperature", "0.0", RUN001_APPROVAL_SOURCE),
    _frozen("seed", "Random seed / seed policy", "0 (fixed)", RUN001_APPROVAL_SOURCE),
    _frozen("retry_policy", "Repeat / retry policy", "0 (Run 001)", RUN001_APPROVAL_SOURCE),
    # --- Prompt / schema versions (pinned by content hash) ---
    _frozen("extractor_prompt_version", "Evidence-extraction prompt version",
            _p(prompts.EXTRACTION_PROMPT_ID), "prompts.py registry; Manifest §4"),
    _frozen("extractor_schema_version", "Evidence-extraction schema version",
            _s(prompts.EXTRACTION_SCHEMA_ID), "prompts.py registry; Manifest §4"),
    _frozen("appraiser_prompt_version", "Evidence-appraisal prompt version",
            _p(prompts.APPRAISAL_PROMPT_ID), "prompts.py registry; Manifest §4"),
    _frozen("appraiser_schema_version", "Evidence-appraisal schema version",
            _s(prompts.APPRAISAL_SCHEMA_ID), "prompts.py registry; Manifest §4"),
    _frozen("stateless_prompt_version", "Stateless-baseline prompt version",
            _p(prompts.BASELINE_PROMPT_ID), "prompts.py registry; Manifest §4"),
    _frozen("stateless_schema_version", "Stateless-baseline schema version",
            _s(prompts.BASELINE_SCHEMA_ID), "prompts.py registry; Manifest §4"),
    _frozen("transcript_prompt_version", "Transcript-baseline prompt version (shared with stateless)",
            _p(prompts.BASELINE_PROMPT_ID), "prompts.py registry; Manifest §4"),
    _frozen("transcript_schema_version", "Transcript-baseline schema version (shared with stateless)",
            _s(prompts.BASELINE_SCHEMA_ID), "prompts.py registry; Manifest §4"),
    # --- Retention & integrity (approved: implemented) ---
    _frozen(
        "per_run_retention",
        "Every real run retains raw prompts, raw responses, parsed outputs, run "
        "metadata, model/version, serving info, generation parameters, git commit, "
        "run id, timestamps, and failures/retries",
        "manifest.RunManifest (immutable, deterministic, secret-free)",
        "Experiment Manifest §7",
    ),
    _frozen(
        "failure_policy_integrity",
        "A failed call never becomes a successful call; malformed output is "
        "rejected and not retried; nothing is defaulted/fabricated on failure "
        "(unchanged for Run 001)",
        "failures.CallStatus + validation + manifest.call_with_recording",
        f"Experiment Manifest §6; {RUN001_APPROVAL_SOURCE}",
    ),
    # --- C.4/C.5 interpretation (approved: raw observables only) ---
    _frozen(
        "c4_c5_interpretation",
        "Report raw longitudinal observables only: NO aggregate behavioural-"
        "divergence formula, NO weighting, NO numerical threshold, NO overall "
        "Phase-1 pass/fail; id-based divergence remains diagnostic only",
        "raw longitudinal observables only; no aggregate/weighting/threshold/"
        "pass-fail; id-based divergence diagnostic only",
        f"Programme v1.4 C.4/C.5; {RUN001_APPROVAL_SOURCE}",
    ),
    _frozen(
        "id_divergence_diagnostic_only",
        "Id-based hypothesis divergence is diagnostic only; never an evaluation score",
        "metrics.id_based_diagnostics (HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT)",
        "Experiment Manifest §12",
    ),
    _frozen(
        "preregistration_freeze",
        "After results are observed, no criterion/prompt/parameter/condition/"
        "interpretation may change; any change requires a new version + separate run",
        "Experiment Manifest §13",
        "Experiment Manifest §13",
    ),
    # --- Human semantic evaluation protocol (approved) ---
    _frozen(
        "semantic_dimensions",
        "Five human-evaluation dimensions",
        "hypothesis_continuity | hypothesis_revision | evidence_grounding | "
        "uncertainty_handling | inquiry_quality",
        f"Semantic Evaluation Protocol §10; {RUN001_APPROVAL_SOURCE}",
    ),
    _frozen(
        "semantic_scale",
        "0–2 ordinal scale per dimension; every score requires written "
        "justification citing relevant interactions; NO composite/aggregate score",
        "Semantic Evaluation Protocol §10",
        f"Semantic Evaluation Protocol §10; {RUN001_APPROVAL_SOURCE}",
    ),
    _frozen(
        "semantic_evaluators",
        "Two independent evaluators; reconciliation after independent scoring, with "
        "written rationale",
        "Semantic Evaluation Protocol §11",
        f"Semantic Evaluation Protocol §11; {RUN001_APPROVAL_SOURCE}",
    ),
    _frozen(
        "semantic_blinding",
        "Neutral condition labels; randomised presentation order; blinding is "
        "best-effort only; Sanuvia structured outputs may reveal condition identity "
        "(recorded limitation); NO substantial presentation-normalisation layer for "
        "Run 001",
        "Semantic Evaluation Protocol §11",
        f"Semantic Evaluation Protocol §11; {RUN001_APPROVAL_SOURCE}",
    ),
    # --- Negative-result disposition (approved) ---
    _frozen(
        "negative_result_disposition",
        "A null or adverse result is a valid Phase-1 result: retained and reported "
        "unchanged. No result-motivated tuning of prompts, Case 001, Phase 0, "
        "generation parameters, evaluation criteria, or interpretation after "
        "observing Run-001 outputs; no rerun of Run 001 seeking a favourable "
        "result; any later result-motivated change becomes a new explicitly "
        "versioned, pre-registered experiment",
        "Programme v1.4 C.1; Experiment Manifest §12",
        f"Programme v1.4 C.1; {RUN001_APPROVAL_SOURCE}",
    ),
    # --- Semantic constraints (approved) ---
    _frozen(
        "observation_vs_interpretation",
        "Observation vs interpretation: the extractor emits observations, not inferences",
        "extractor boundary emits observations only; enforced by tests",
        "Reasoning Semantics v0.2; Experiment Manifest §2/§8",
    ),
    _frozen(
        "resonance_not_accuracy",
        "Resonance != accuracy: ER-007 ('I feel better') supports no hypothesis",
        "test_case_001_discipline (ER-007 appraises empty)",
        "Experiment Manifest §8; fixture discipline",
    ),
    _frozen(
        "provenance_limits",
        "Provenance limits: ER-006 (unverified, partner-referenced) is not cited as support",
        "test_case_001_discipline (ER-006 not used as support)",
        "Experiment Manifest §8; fixture discipline",
    ),
    _frozen(
        "retain_competing_hypotheses",
        "Competing hypotheses are retained, not collapsed into a single narrative",
        "trajectory observables (hypothesis set retained across interactions)",
        "Experiment Manifest §9",
    ),
    _frozen(
        "empty_hold_preserved",
        "seq-5 is preserved as a genuine no-new-evidence hold",
        "fixtures/longitudinal/case_001.py (seq-5 empty)",
        "Experiment Manifest §8",
    ),
    _frozen(
        "do_not_engineer_h1_h4",
        "Do not engineer the H1/H4 inquiry result",
        "fixture is not tuned to force any hypothesis pair",
        f"{APPROVAL_SOURCE}; Programme v1.4 C.5",
    ),
    _frozen(
        "retain_observed_h1_h2",
        "Retain the observed H1/H2 final inquiry result (recorded, not forced)",
        "observed_inquiry_pairs recorded as an observation",
        APPROVAL_SOURCE,
    ),
    _frozen(
        "golden_is_structural_control",
        "Deterministic Case 001 is a structural/golden control, not empirical model "
        "evidence; empirical data requires the real run",
        "golden mode uses scripted doubles; real mode required for empirical data",
        "Experiment Manifest §8; README",
    ),
    # --- Verified artifact / runtime identity (Run 001) ---
    # Identified from the actual installed GGUF and computed locally — not invented.
    # Local path (host-specific, not part of the portable identity hash):
    # /Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf
    _frozen(
        "model_artifact_version",
        "Exact model artifact + version, identified from the installed GGUF",
        "Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b :: "
        "Qwen3-4B-Q4_K_M.gguf (2497280256 bytes)",
        RUN001_VERIFICATION_SOURCE,
    ),
    _frozen(
        "artifact_sha256",
        "SHA-256 computed over the installed artifact; verified == published digest",
        "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5",
        RUN001_VERIFICATION_SOURCE,
    ),
    _frozen(
        "llama_cpp_build",
        "Exact llama.cpp runtime build in use",
        "build 10721 (commit 8e53fcefd), macos-x64 prebuilt release (v0.3.0-dev)",
        RUN001_VERIFICATION_SOURCE,
    ),
    # --- Pending governance approval (non-blocking) ---
    _pending(
        "eval_hardware",
        "Evaluation hardware (CPU/GPU/RAM of the eval host) — recorded at run time",
        "Experiment Manifest §3", blocking=False,
    ),
)


def frozen_items() -> tuple[GovernanceItem, ...]:
    return tuple(i for i in FREEZE_RECORD if i.status is GovernanceStatus.FROZEN)


def pending_items() -> tuple[GovernanceItem, ...]:
    return tuple(
        i for i in FREEZE_RECORD if i.status is GovernanceStatus.PENDING_GOVERNANCE_APPROVAL
    )


def blocking_items() -> tuple[GovernanceItem, ...]:
    return tuple(i for i in FREEZE_RECORD if i.is_blocking_now)


def is_real_run_permitted() -> bool:
    """True only when no blocking governance item is still pending."""
    return not blocking_items()


def _canonical() -> str:
    # Stable serialization for the content hash — version + order + each field.
    lines = [f"version:{FREEZE_RECORD_VERSION}"]
    lines += [
        f"{i.key}|{i.status.value}|{i.value or ''}|{int(i.blocking)}" for i in FREEZE_RECORD
    ]
    return "\n".join(lines)


def freeze_record_sha256() -> str:
    """Content hash pinning the frozen protocol. Changes if the version or any
    frozen value (including a pinned prompt/schema hash) changes — the immutability
    anchor for a real run."""
    return hashlib.sha256(_canonical().encode("utf-8")).hexdigest()


def render_checklist() -> str:
    """A clearly visible governance checklist: FROZEN / PENDING / BLOCKING."""
    lines = [
        "PHASE 1 GOVERNANCE / FREEZE CHECKLIST",
        "=" * 37,
        f"freeze_record_version: {FREEZE_RECORD_VERSION}",
        f"freeze_record_sha256: {freeze_record_sha256()}",
        f"real run permitted: {'YES' if is_real_run_permitted() else 'NO'}",
        "prior versions:",
    ]
    for version, digest in FREEZE_RECORD_HISTORY:
        lines.append(f"  {version}: {digest}")
    lines.append("")
    lines.append("FROZEN / APPROVED")
    for item in frozen_items():
        lines.append(f"  [FROZEN]  {item.key}: {item.value}")
        lines.append(f"            {item.description}  ({item.source})")
    lines.append("")
    lines.append("PENDING GOVERNANCE APPROVAL")
    for item in pending_items():
        flag = "BLOCKING" if item.blocking else "non-blocking"
        lines.append(f"  [PENDING/{flag}]  {item.key}: {item.description}  ({item.source})")
    lines.append("")
    lines.append("BLOCKING THE REAL RUN")
    blocking = blocking_items()
    if not blocking:
        lines.append("  (none — all blocking items are frozen/approved)")
    else:
        for item in blocking:
            lines.append(f"  [BLOCKING]  {item.key}: {item.description}")
    return "\n".join(lines)
