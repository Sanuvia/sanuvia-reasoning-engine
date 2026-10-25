# Phase 1 — Governance / Freeze Record

**Status:** READY (Run 001) — artifact + runtime verified · **Prepared:** 2026-08-26 · **Updated:** 2026-08-31
**Companion:** [Experiment Manifest](phase1-experiment-manifest.md) ·
[Semantic Evaluation Protocol](phase1-semantic-evaluation-protocol.md)
**Machine-readable source of truth:** `sanuvia_phase1.governance` (`FREEZE_RECORD`)
**Freeze record version:** `8.0-run003-output-cap-1536-and-chat-template-pin`
**Freeze record hash:** `sha256:f62c33b1dd72d623c685267cb54e5eade5bfeb41e86b9a7c556a7f5384a17bac`

**Version history (audit trail — never overwritten):**
| Version | freeze_record_sha256 |
|---|---|
| `1.0-structure` | `8a8841ba3003bbab0aadff8fa0f3ccceab6ec965cf209d5cc2f77ae30a91a44f` |
| `2.0-run001` | `0291e6e4b0452c4a4ca32daa4424e32982919b8da0558dc5b41d39644d8fe4ad` |
| `3.0-run001-verified` | `3f46ef56e12c776251a223180cfbf842f228fbbcb743ff5c466f7acf45c0a2dd` |
| `4.0-appraisal-schema-v2` | `8cf8dd7d25588dc892211b6fdf7f8e8f74e83a718c3308e372b4af6c06dc925a` |
| `5.0-appraisal-schema-v3-signature` | `d3e6c79f0475dd46cfd5e5629d95cc9be650eb7d28efb24ac37300280743905c` |
| `6.0-slice2-extractor-standing` | `f79197af53a2ff04dc77dec84523f59f692f49e1b623f4b5f524880ba58930bf` |
| `7.0-extraction-schema-v3-participant-labels` | `16c7cbad9b364b0db86b9219a6dc2f0d768ba9afb9237246d678454aa8bf371c` |
| `8.0-run003-output-cap-1536-and-chat-template-pin` | `f62c33b1dd72d623c685267cb54e5eade5bfeb41e86b9a7c556a7f5384a17bac` |

This record pins the frozen Phase 1 protocol for the first real run. As of
`3.0-run001-verified`, the exact model artifact identity, its locally-computed
SHA-256, and the llama.cpp runtime build are **verified and frozen**. The only
remaining pending item is `eval_hardware` (non-blocking, recorded at run time).
The record is immutable: its content hash changes if the version or any frozen
value changes, which by the pre-registration rule requires a new version.

`is_real_run_permitted()` is now **YES** — no blocking items remain.

**Execution status (corrected 2026-10-25).** This record previously read "No
model has been executed and Case 001 has not been run." That ceased to be true
when Run 002 executed and is corrected here:

- **Case 001 was executed** once under Run 002, under the project owner's
  explicit authorisation. See the [Run 002 Governance Record](phase1-run002-governance-record.md).
- **Run 003 Stage 1 was attempted** once against Case 002 on 2026-10-23 and
  **failed** on output truncation after a single model call. It is retained as
  a failed attempt, nothing was salvaged from it, and it has not been retried.
- **The semantic evaluation has not been run**, and no Run 003 results exist.

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
| `max_output_tokens` | 1536 |
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
| `extractor_prompt_version` | `extraction.observations.v3@sha256:05e1a9…e1a3` |
| `extractor_schema_version` | `schema.extraction.v3@sha256:18b9b9…0519` |
| `appraiser_prompt_version` | `appraisal.support-contradict-propose.v3@sha256:d58799…c93c` |
| `appraiser_schema_version` | `schema.appraisal.v3@sha256:f8567c…2459` |
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

- **FROZEN / APPROVED (44 items)** — the three-condition structure, same-sequential-
  evidence, Case 001 unchanged, Phase 0 frozen, local-only provider; model Qwen3-4B
  on llama.cpp GGUF at Q4_K_M with context 8192 / max-out 1536 / stop none;
  the pinned serving chat-template digest;
  temperature 0.0 / seed 0 / retries 0; the **verified artifact identity + SHA-256 +
  llama.cpp build**; pinned prompt & schema versions; per-run retention + failure
  integrity; C.4/C.5 raw-observables-only; id-based divergence diagnostic-only; the
  pre-registration freeze; the approved semantic evaluation protocol (0–2 scale, two
  evaluators, best-effort blinding); the negative-result disposition; and all
  approved semantic constraints.
- **PENDING GOVERNANCE APPROVAL (1 item)** — eval hardware (non-blocking, recorded
  at run time).
- **BLOCKING THE REAL RUN** — none.

## What has changed since the Run 001 approval

The blanket claim that "the prompts, schemas ... are unchanged" previously stood
here. It is no longer true and has been removed rather than qualified.

| | |
|---|---|
| **Changed** | the **extraction** prompt and schema, `v2 → v3`. `subject` is now a request-scoped participant label rather than a bare string (§2 B), so the model names only what the request offered it and the application maps the label back to a canonical id. |
| | the **appraisal** prompt and schema, at `v3` since the v1.5.4 signature migration. |
| **Unchanged** | Phase 0, Case 001, the three conditions, the baseline prompt/schema, the generation parameters, the model artifact and runtime identity, the C.4/C.5 interpretation, and the semantic protocol. |

Both bumps are new ids, not edits in place, so Run 002's `...v2` references keep
meaning what they meant. The pinned values are those in the table above and are
derived from the live registry, not transcribed.

| Boundary | Prompt id | Prompt SHA-256 | Schema id | Schema SHA-256 |
|---|---|---|---|---|
| Evidence extraction | `extraction.observations.v3` | `05e1a9d408d720fa87fc663d8a0a17ff7fe757f5323e74047b86c0bac74ce1a3` | `schema.extraction.v3` | `18b9b9968492e773237745d52c5d8a6ea09b5ccebe8f4007760e7baaf3320519` |
| Evidence appraisal | `appraisal.support-contradict-propose.v3` | `d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c` | `schema.appraisal.v3` | `f8567cd05b764d0b4cc139e14216736db252b6874fd1c4f3020b878099d12459` |

`prompts.verify_prompt_integrity()` returns no drift against these values, and
the preflight `prompt_integrity_no_drift` check passes.

## Approval scope — unresolved, for the project owner

The provider, model, runtime and generation parameters above are **FROZEN**, and
`is_real_run_permitted()` is `True` with zero blocking items. Their recorded
source is *"Phase 1 Run-001 governance approval (2026-08-26)"*, with the
artifact identity verified on 2026-08-31.

Two questions that approval does not answer, and that are **not** assumed here:

1. **Does the Run-001 approval extend to a Run 003 executed under the v3
   extraction prompt/schema?** The approval predates the v3 bump. The model,
   runtime and parameters are unchanged; what the model is asked for is not.
2. **The R1 identity-resolution boundary has no approval at all.** It did not
   exist at the time of the Run-001 approval, carries no governance item, and
   `qwen_real_run_config()` emits no `identity_resolution` spec. If R1 runs in
   Run 003 its provider, model, prompt and schema need their own approval. If
   it does not run, §2 G parks non-exact candidates and nothing is needed.

*Corrected 2026-10-25: this line previously read "No real Qwen run has
occurred and no model inference has been run." Real inference has occurred —
Case 001 under Run 002, and one failed Case 002 extraction call on 2026-10-23.
What has not occurred is a completed Run 003 and the semantic evaluation.*

---

## Amendment 8.0 — output cap, and a pinned chat template

**Date:** 2026-10-24 · **Scope:** two frozen items. Nothing else.

### `max_output_tokens`: 512 → 1536

Run 003 Stage 1 attempt 1 stopped on its first extraction call. The server
answered; the reply hit `finish_reason: length` at exactly 512 completion
tokens and was cut mid-string, so strict validation rejected it and the frozen
zero-retry policy ended the run.

The reply was otherwise well formed: four complete observations with every
required field, the fifth truncated. Measured from it, one observation costs
~103 output tokens. The largest interaction groups seven turns, giving a
worst case near 730 tokens. 1536 is roughly twice that; 1024 would leave only
~1.4x against an estimate that assumes one observation per turn, and 2048 has
no measured basis.

Worst case becomes ~554 prompt + 1536 output = ~2,090 of the 8,192 window, so
the context window is untouched and needs no change.

### `chat_template_sha256`: newly pinned

Readiness verified the serving chat template on 2026-10-22, but the expected
digest was supplied by hand rather than pinned, so a later run that omitted it
skipped the check and still reported a complete pass. The observed digest is
now a frozen item, so the check verifies by default.

### Unchanged

Interaction grouping, model and artifact, prompts, schemas, validators,
context window, temperature, seed, zero-retry, roster and R1 configuration.

### Comparability caveat

Run 002 executed at `max_output_tokens=512`. Run 003 will execute at 1536.
Any cross-run comparison spans **different output caps** and must say so.
Nothing else in the generation configuration differs.
