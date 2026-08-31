# Phase 1 — Governance / Freeze Record

**Status:** READY (Run 001) — artifact + runtime verified · **Prepared:** 2026-08-26 · **Updated:** 2026-08-31
**Companion:** [Experiment Manifest](phase1-experiment-manifest.md) ·
[Semantic Evaluation Protocol](phase1-semantic-evaluation-protocol.md)
**Machine-readable source of truth:** `sanuvia_phase1.governance` (`FREEZE_RECORD`)
**Freeze record version:** `3.0-run001-verified`
**Freeze record hash:** `sha256:3f46ef56e12c776251a223180cfbf842f228fbbcb743ff5c466f7acf45c0a2dd`

**Version history (audit trail — never overwritten):**
| Version | freeze_record_sha256 |
|---|---|
| `1.0-structure` | `8a8841ba3003bbab0aadff8fa0f3ccceab6ec965cf209d5cc2f77ae30a91a44f` |
| `2.0-run001` | `0291e6e4b0452c4a4ca32daa4424e32982919b8da0558dc5b41d39644d8fe4ad` |
| `3.0-run001-verified` | `3f46ef56e12c776251a223180cfbf842f228fbbcb743ff5c466f7acf45c0a2dd` |

This record pins the frozen Phase 1 protocol for the first real run. As of
`3.0-run001-verified`, the exact model artifact identity, its locally-computed
SHA-256, and the llama.cpp runtime build are **verified and frozen**. The only
remaining pending item is `eval_hardware` (non-blocking, recorded at run time).
The record is immutable: its content hash changes if the version or any frozen
value changes, which by the pre-registration rule requires a new version.

`is_real_run_permitted()` is now **YES** — no blocking items remain. **No model
has been executed and Case 001 has not been run.**

---

## 1. Frozen / approved

### Experimental structure
| Key | Frozen value |
|---|---|
| `experimental_structure` | `sanuvia_persistent \| fm_stateless \| fm_transcript` (no new conditions) |
| `same_sequential_evidence` | identical seq labels enforced by the pipeline fairness guard |
| `case_001_unchanged` | Case 001 (6 interactions; seq-5 empty hold) |
| `phase0_frozen` | `src/sanuvia/**` unmodified; import isolation enforced |
| `provider_local_only` | `local_qwen` (no cloud, no API key, no download) |

### Model / serving (approved, Run 001)
| Key | Frozen value |
|---|---|
| `model_family` | Qwen3-4B |
| `serving_runtime_backend` | llama.cpp (GGUF) |
| `quantization` | Q4_K_M |
| `context_window` | 8192 |
| `max_output_tokens` | 512 |
| `stop_sequences` | none |

### Verified artifact / runtime identity (Run 001)
| Key | Frozen value |
|---|---|
| `model_artifact_version` | `Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b :: Qwen3-4B-Q4_K_M.gguf (2497280256 bytes)` |
| `artifact_sha256` | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` (computed locally; verified == published) |
| `llama_cpp_build` | build 10721 (commit 8e53fcefd), macos-x64 prebuilt release (v0.3.0-dev) |

Local artifact path (host-specific deployment metadata, not part of the portable
identity hash): `/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf`.

### Generation parameters (approved, Run 001)
| Key | Frozen value |
|---|---|
| `temperature` | 0.0 |
| `seed` | 0 (fixed) |
| `retry_policy` | 0 (Run 001) |

### Prompt / schema versions (pinned by content hash)
| Key | Frozen value |
|---|---|
| `extractor_prompt_version` | `extraction.observations.v1@sha256:a45066…97d1` |
| `extractor_schema_version` | `schema.extraction.v1@sha256:a9cabe…c094` |
| `appraiser_prompt_version` | `appraisal.support-contradict-propose.v1@sha256:790e63…8398` |
| `appraiser_schema_version` | `schema.appraisal.v1@sha256:f36e78…1004` |
| `stateless_prompt_version` | `baseline.reasoning.v1@sha256:355797…43bc` |
| `stateless_schema_version` | `schema.baseline.v1@sha256:efa45b…c11e` |
| `transcript_prompt_version` | `baseline.reasoning.v1` (shared with stateless) |
| `transcript_schema_version` | `schema.baseline.v1` (shared with stateless) |

### Retention & integrity
| Key | Frozen value |
|---|---|
| `per_run_retention` | manifest retains raw prompts, raw responses, parsed outputs, run metadata, model/version, serving info, generation parameters, git commit, run id, timestamps, failures/retries (immutable, secret-free) |
| `failure_policy_integrity` | failed call never becomes successful; malformed output rejected, not retried; nothing defaulted/fabricated (unchanged for Run 001) |
| `id_divergence_diagnostic_only` | id-based hypothesis divergence is diagnostic only, never an evaluation score |
| `preregistration_freeze` | no criterion/prompt/parameter/condition/interpretation changes after results are observed |

### C.4 / C.5 interpretation and negative-result disposition (approved)
| Key | Frozen value |
|---|---|
| `c4_c5_interpretation` | report raw longitudinal observables only; **no** aggregate formula, **no** weighting, **no** numerical threshold, **no** overall pass/fail; id-based divergence diagnostic only |
| `negative_result_disposition` | a null/adverse result is a valid Phase-1 result, retained and reported unchanged; no result-motivated tuning of prompts/Case 001/Phase 0/parameters/criteria/interpretation; no rerun of Run 001 for a favourable result; any later result-motivated change becomes a new versioned, pre-registered experiment |

### Human semantic evaluation protocol (approved)
| Key | Frozen value |
|---|---|
| `semantic_dimensions` | hypothesis_continuity \| hypothesis_revision \| evidence_grounding \| uncertainty_handling \| inquiry_quality |
| `semantic_scale` | 0–2 ordinal per dimension; written justification citing interactions; **no** composite/aggregate |
| `semantic_evaluators` | two independent evaluators; reconciliation with written rationale |
| `semantic_blinding` | neutral condition labels; randomised order; best-effort blinding; Sanuvia structured outputs may reveal identity (recorded limitation); no presentation-normalisation layer for Run 001 |

### Semantic constraints (approved)
| Key | Frozen value |
|---|---|
| `observation_vs_interpretation` | extractor emits observations, not inferences |
| `resonance_not_accuracy` | ER-007 ("I feel better") supports no hypothesis |
| `provenance_limits` | ER-006 (unverified, partner-referenced) is not cited as support |
| `retain_competing_hypotheses` | competing hypotheses retained, not collapsed |
| `empty_hold_preserved` | seq-5 preserved as a genuine no-new-evidence hold |
| `do_not_engineer_h1_h4` | the H1/H4 inquiry result is not engineered |
| `retain_observed_h1_h2` | the observed H1/H2 final inquiry result is recorded, not forced |
| `golden_is_structural_control` | deterministic Case 001 is a structural/golden control, not empirical model evidence |

---

## 2. Pending governance approval

| Key | Needs | Blocking? |
|---|---|---|
| `eval_hardware` | eval host CPU/GPU/RAM | non-blocking (recorded at run time) |

---

## 3. Blocking the real run

**None.** All blocking governance items are frozen/approved and the environment is
verified. `python -m sanuvia_phase1 preflight-real` reports **OVERALL: PASS** when
run with the verified artifact path (`SANUVIA_QWEN_MODEL_PATH`) and llama.cpp on
PATH. Run 001 is permitted, but is **not** executed here — execution awaits an
explicit, separate go-ahead.

---

## Governance summary

- **FROZEN / APPROVED (43 items)** — the three-condition structure, same-sequential-
  evidence, Case 001 unchanged, Phase 0 frozen, local-only provider; model Qwen3-4B
  on llama.cpp GGUF at Q4_K_M with context 8192 / max-out 512 / stop none;
  temperature 0.0 / seed 0 / retries 0; the **verified artifact identity + SHA-256 +
  llama.cpp build**; pinned prompt & schema versions; per-run retention + failure
  integrity; C.4/C.5 raw-observables-only; id-based divergence diagnostic-only; the
  pre-registration freeze; the approved semantic evaluation protocol (0–2 scale, two
  evaluators, best-effort blinding); the negative-result disposition; and all
  approved semantic constraints.
- **PENDING GOVERNANCE APPROVAL (1 item)** — eval hardware (non-blocking, recorded
  at run time).
- **BLOCKING THE REAL RUN** — none.

*No real Qwen run has occurred. Phase 0, Case 001, the prompts, schemas, conditions,
generation parameters, C.4/C.5 interpretation, and semantic protocol are unchanged.*
