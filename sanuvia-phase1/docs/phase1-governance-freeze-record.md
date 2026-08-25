# Phase 1 — Governance / Freeze Record

**Status:** DRAFT — pending governance approval · **Prepared:** 2026-08-23
**Companion:** [Experiment Manifest](phase1-experiment-manifest.md) ·
[Semantic Evaluation Protocol](phase1-semantic-evaluation-protocol.md)
**Machine-readable source of truth:** `sanuvia_phase1.governance` (`FREEZE_RECORD`)
**Freeze record hash:** `sha256:8a8841ba3003bbab0aadff8fa0f3ccceab6ec965cf209d5cc2f77ae30a91a44f`

This record pins the frozen Phase 1 protocol for the first real run. The approved
experimental *structure* is frozen; every unresolved experimental *value* is marked
**PENDING GOVERNANCE APPROVAL** and is **not** chosen here. The record is immutable:
its content hash (above) changes if any frozen value — including a pinned
prompt/schema hash — changes, which by the pre-registration rule (Experiment
Manifest §13) requires a new protocol version and a separate run.

`is_real_run_permitted()` is currently **NO** — 8 blocking items are still pending.
**No model was run and none was downloaded.**

---

## 1. Frozen / approved

Structure, provenance, retention, integrity, and the approved semantic constraints
are frozen. Each cites its source.

### Experimental structure
| Key | Frozen value | Source |
|---|---|---|
| `experimental_structure` | `sanuvia_persistent \| fm_stateless \| fm_transcript` (no new conditions) | Experiment Manifest §2; Phase 1 protocol approval |
| `same_sequential_evidence` | identical seq labels enforced by the pipeline fairness guard | Experiment Manifest §2/§8 |
| `case_001_unchanged` | `fixtures/longitudinal/case_001.py` (6 interactions; seq-5 empty hold) | Experiment Manifest §8 |
| `phase0_frozen` | `src/sanuvia/**` unmodified; import isolation enforced | repo policy; preflight |
| `provider_local_only` | `local_qwen` (no cloud, no API key, no download) | Experiment Manifest §3 |

### Prompt / schema versions (pinned by content hash)
| Key | Frozen value | Source |
|---|---|---|
| `extractor_prompt_version` | `extraction.observations.v1@sha256:a45066…97d1` | prompts.py; Manifest §4 |
| `extractor_schema_version` | `schema.extraction.v1@sha256:a9cabe…c094` | prompts.py; Manifest §4 |
| `appraiser_prompt_version` | `appraisal.support-contradict-propose.v1@sha256:790e63…8398` | prompts.py; Manifest §4 |
| `appraiser_schema_version` | `schema.appraisal.v1@sha256:f36e78…1004` | prompts.py; Manifest §4 |
| `stateless_prompt_version` | `baseline.reasoning.v1@sha256:355797…43bc` | prompts.py; Manifest §4 |
| `stateless_schema_version` | `schema.baseline.v1@sha256:efa45b…c11e` | prompts.py; Manifest §4 |
| `transcript_prompt_version` | `baseline.reasoning.v1@sha256:355797…43bc` (shared with stateless) | prompts.py; Manifest §4 |
| `transcript_schema_version` | `schema.baseline.v1@sha256:efa45b…c11e` (shared with stateless) | prompts.py; Manifest §4 |

### Retention & integrity
| Key | Frozen value | Source |
|---|---|---|
| `per_run_retention` | `manifest.RunManifest` retains raw prompts, raw responses, parsed outputs, run metadata, model/version, serving info, generation parameters, git commit, run id, timestamps, failures/retries (immutable, deterministic, secret-free) | Experiment Manifest §7 |
| `failure_policy_integrity` | a failed call never becomes a successful call; malformed output is rejected, not retried; nothing defaulted/fabricated on failure | Experiment Manifest §6 |
| `id_divergence_diagnostic_only` | id-based hypothesis divergence is diagnostic only, never an evaluation score | Experiment Manifest §12 |
| `preregistration_freeze` | no criterion/prompt/parameter/condition/interpretation changes after results are observed | Experiment Manifest §13 |

### Semantic constraints (approved)
| Key | Frozen value | Source |
|---|---|---|
| `observation_vs_interpretation` | extractor emits observations, not inferences | Reasoning Semantics v0.2; Manifest §2/§8 |
| `resonance_not_accuracy` | ER-007 ("I feel better") supports no hypothesis | Manifest §8; fixture discipline |
| `provenance_limits` | ER-006 (unverified, partner-referenced) is not cited as support | Manifest §8; fixture discipline |
| `retain_competing_hypotheses` | competing hypotheses retained, not collapsed | Experiment Manifest §9 |
| `empty_hold_preserved` | seq-5 preserved as a genuine no-new-evidence hold | Experiment Manifest §8 |
| `do_not_engineer_h1_h4` | the H1/H4 inquiry result is not engineered | Phase 1 protocol approval; Programme v1.4 C.5 |
| `retain_observed_h1_h2` | the observed H1/H2 final inquiry result is recorded, not forced | Phase 1 protocol approval |
| `golden_is_structural_control` | deterministic Case 001 is a structural/golden control, not empirical model evidence | Manifest §8; README |

### Per-run retention (approved requirement — implemented)

For **every** real run the immutable manifest records: run ID · timestamp · git
commit SHA · Phase 1 version · full transcript · exact model/version · serving/
runtime information · generation parameters · raw prompts (by pinned prompt ID +
hash) · raw model responses · parsed outputs (per-interaction observables) ·
retries · failures · per-interaction status · session/cache identifiers where a
provider exposes them (else recorded as unavailable) · runtime/backend metadata.
**No secrets are stored.** A real-run manifest also pins this record via
`governance_freeze_hash`.

---

## 2. Pending governance approval

These experimental values are **not** decided here. They must be approved and
recorded before (or, where non-blocking, at) the real run.

| Key | Needs | Blocking? | Source |
|---|---|---|---|
| `model_artifact_version` | exact model artifact + version + digest | **BLOCKING** | Manifest §3 |
| `serving_runtime_backend` | serving/runtime/backend arrangement | **BLOCKING** | Manifest §3 |
| `quantization` | model quantization | **BLOCKING** | Manifest §3 |
| `temperature` | sampling temperature (frozen experimental value) | **BLOCKING** | Manifest §5 |
| `seed` | random seed / seed policy | **BLOCKING** | Manifest §5 |
| `retry_policy` | repeat/retry policy (retry count) | **BLOCKING** | Manifest §6 |
| `c4_c5_interpretation` | C.4/C.5 evaluation/pass interpretation (formula, weighting, threshold) — or an explicit pre-registered decision to report observables only | **BLOCKING** | Programme v1.4 C.4/C.5; Manifest §12 |
| `negative_result_disposition` | formal negative-result disposition policy (distinct from the frozen "retain observed H1/H2" constraint) | **BLOCKING** | Programme v1.4 C.1; Manifest §12 |
| `eval_hardware` | eval host CPU/GPU/RAM | non-blocking (recorded at run time) | Manifest §3 |

> The implemented `RealRunConfig` carries placeholder defaults (`temperature=0.0`,
> `seed=0`, `retries=0`) purely so the pipeline is executable/testable offline.
> These are **not** approved values; this record is the source of truth, and they
> remain **PENDING GOVERNANCE APPROVAL** until frozen here.

---

## 3. Blocking the real run

The real run is **blocked** until every item below is approved and recorded, and
`python -m sanuvia_phase1 preflight-real` reports **OVERALL: PASS** (its
`governance_freeze_complete` check reads this record):

1. `model_artifact_version` · 2. `serving_runtime_backend` · 3. `quantization` ·
4. `temperature` · 5. `seed` · 6. `retry_policy` · 7. `c4_c5_interpretation` ·
8. `negative_result_disposition`

Plus the environment gate: a local Qwen runtime + artifact installed and its exact
version identifiable (preflight `model_installed_available` /
`model_version_identifiable`).

---

## Governance summary

- **FROZEN / APPROVED** — the three-condition structure, same-sequential-evidence,
  Case 001 unchanged, Phase 0 frozen, local-only provider, the pinned prompt/schema
  versions, per-run retention + failure integrity, id-based-divergence-diagnostic-
  only, the pre-registration freeze, and all approved semantic constraints (25 items).
- **PENDING APPROVAL** — model artifact/version, serving/runtime, quantization,
  temperature, seed, retry policy, C.4/C.5 interpretation, negative-result
  disposition, eval hardware (9 items).
- **BLOCKING THE REAL RUN** — the 8 blocking pending items above, plus the local
  model install/version environment gate.

*No real Qwen run has occurred. No model was downloaded. Phase 0, Case 001, the
prompts, and the evaluation criteria are unchanged.*
