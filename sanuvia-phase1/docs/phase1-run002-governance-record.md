# Phase 1 — Run 002 Governance Record

**Status:** PRE-SEAL (not a sealed freeze) · **Record version:** `0.3-run002-preseal-pinned`
**Scope:** Run 002 execution plumbing only · **Case 001: NOT EXECUTED**
**Pinned correction commit:** `3f2bda15a74e5f2f3d57caa3888e115d7960d035`
**Technical review:** bounded correction reviewed and approved by Lillian; package
finalised at her authorisation. Final seal verification is hers and has **not** been
performed here.
**Companion:** [Run 001 Governance / Freeze Record](phase1-governance-freeze-record.md) —
frozen at `3.0-run001-verified`, **untouched by this record**.

**Version history (audit trail — never overwritten):**

| Version | record_sha256 | Note |
|---|---|---|
| `0.2-run002-execution-path-corrected` | `4386ad61f118700d748003dab1f8b67a85a2ebe9605de37d6f5e212e95657d73` | the record as committed inside `3f2bda1`; referenced the corrected commit indirectly, by content hash |
| `0.3-run002-preseal-pinned` | published alongside — see *Record hash* | repinned to name commit `3f2bda15a74e5f2f3d57caa3888e115d7960d035` explicitly; no substantive change to any approved statement |

> This record does not seal a freeze and does not amend Run 001. It records one
> bounded correction to the Run 002 execution path, and the evidence produced by the
> corrected path. The record's own SHA-256 is published alongside it (a document
> cannot contain its own hash) — see *Record hash* below.

---

## 1. The bounded correction

Lillian identified one execution-path mismatch in the committed Run 002 code.

**Defect.** The real Case 001 harness reaches the backend through the frozen
`QwenClient` adapter, which calls the backend's port-conforming `generate()`. In the
previously committed backend:

- `generate_ex()` captured `reasoning_content`;
- the sacrificial Gate 1 runner enforced `enforce_reasoning_invariant()` in a
  runner-local thunk;
- but `generate()` returned `generate_ex(...).content` **without enforcing the
  invariant**.

The invariant was therefore proven on a path Case 001 would never take.

**Correction.** `generate()` now enforces the invariant, using the existing
`generate_ex()` + `enforce_reasoning_invariant()` mechanism — one implementation, no
duplicate:

```python
def generate(self, prompt: str, params: GenerationParams) -> str:
    return self.enforce_reasoning_invariant(self.generate_ex(prompt, params))
```

The invariant is unchanged and remains the already-approved one:

> `enable_thinking=false` **AND** non-empty `reasoning_content` → visible
> `MALFORMED_OUTPUT`.

**Why the violation is *visible*.** Two frozen call sites decide the recorded status.
`QwenClient._generate_recorded`'s thunk re-raises `ModelError` unchanged but wraps
every other exception into a plain `ModelError`; `manifest.call_with_recording` tests
`except MalformedOutputError` **before** `except ModelError`. A bare
`MalformedOutputError` raised from `generate()` would therefore have been downgraded to
`model_error`. The invariant now raises `ReasoningInvariantViolation`, which subclasses
**both** `MalformedOutputError` and `ModelError`: it crosses the frozen port with its
type intact and is recorded as `CallStatus.MALFORMED_OUTPUT`, raw preserved, no retry —
**without editing any frozen file**.

---

## 2. Required statements

| # | Statement |
|---|---|
| 1 | The **actual Case 001 execution path enforces the reasoning-content invariant**. The invariant is enforced inside `LlamaServerBackendRun002.generate()`, the method `QwenClient._generate_recorded` calls. |
| 2 | **Non-empty `reasoning_content` results in visible `MALFORMED_OUTPUT`** — recorded as `CallStatus.MALFORMED_OUTPUT` on the `CallRecord`, never `model_error` and never `success`; subsequent interactions are `NOT_EXECUTED`. |
| 3 | The **complete backend response is preserved**. `generate_ex()` writes the full server JSON (message content, `reasoning_content`, finish reason, usage) to the provenance log before returning or raising, and a violation carries the verbatim `message.content` as `raw`, recorded in `CallRecord.raw_response`. |
| 4 | **`message.content` is passed unchanged to the existing validator.** No stripping, no `<think>` removal, no JSON extraction, no sanitisation, no repair, no retry. Verified by SHA-256 identity across `message.content`, the validator input, and `CallRecord.raw_response`. |
| 5 | **Prompts, schemas and validators remain unchanged.** Every frozen protocol file is byte-identical to the previous commit (see `BYTE_IDENTITY.json`). |
| 6 | The **accepted Qwen3/llama.cpp configuration remains unchanged** — Qwen3-4B-Q4_K_M (`7485fe6f…4fdf5`), llama.cpp build 10721 (`8e53fcefd`), the model's own embedded template, no `--reasoning-format none`, `chat_template_kwargs={"enable_thinking": false}`, temperature 0.0, seed 0, max output 512, context 8192, no stop sequences, retries 0. |
| 7 | **Case 001 has NOT been executed.** No Case 001 input was constructed and no Case 001 model call was issued. The only model calls in this correction are the two sacrificial Gate 1 calls over synthetic, non-Case-001 text. |

Research semantics, the three-condition structure, Phase 0 (`src/sanuvia/**`), the
C.4/C.5 interpretation and the negative-result disposition are unchanged.

---

## 3. Execution path — one path, all three conditions

```
condition (sanuvia_persistent | fm_stateless | fm_transcript)
  -> ExternalEvidenceExtractor / ExternalEvidenceAppraiser / ExternalLanguageModel   [frozen]
  -> QwenClient.extraction_client() / appraisal_client() / baseline_client()         [frozen]
  -> QwenClient._generate_recorded -> thunk                                          [frozen]
  -> manifest.call_with_recording                                                    [frozen]
  -> LlamaServerBackendRun002.generate()            <-- invariant enforced here
       -> generate_ex()                     (complete backend response captured)
       -> enforce_reasoning_invariant()     (single implementation)
  -> validate_extraction / validate_baseline, on the UNCHANGED message.content       [frozen]
```

There is **no condition-specific implementation**: all three conditions reach
`generate()` through `QwenClient._generate_recorded`. `sanuvia_persistent` uses the
extraction and appraisal boundaries; `fm_stateless` the stateless-baseline boundary;
`fm_transcript` the transcript-baseline boundary.

---

## 4. Evidence produced by the corrected path

Sacrificial Gate 1 was re-run **through the corrected `generate()` path** (synthetic,
non-Case-001 input; exactly one attempt per boundary).

| Boundary | `<think>` | `reasoning_content` | attempts | `json.loads` | validator | recorded status | content unchanged into validator | Gate 1 |
|---|---|---|---|---|---|---|---|---|
| `evidence_extraction` | absent | absent (`None`) | 1 | ok | PASS | `success` | yes (SHA-256 identical) | **PASS** |
| `stateless_baseline` | absent | absent (`None`) | 1 | ok | PASS | `success` | yes (SHA-256 identical) | **PASS** |

Gate 2 (failure/interaction accounting) passes against the corrected implementation:
`MALFORMED_OUTPUT` recorded at the boundary, later interactions `NOT_EXECUTED`, raw
backend output preserved, one attempt, on all four boundaries.

Full artifacts, hashes and integrity report: `local_run002/evidence_preseal/`.

---

## 5. Provenance of the correction

| Item | Value |
|---|---|
| Superseded commit (previously tested path) | `9a89662` — *Run 002: add tested execution backend and preflight runner* |
| Superseded backend SHA-256 | `1c8b339c13e24853840d6c2ed0ba5fac449c1917ec5cba8ffc6b6ab87263b9a5` |
| Corrected backend SHA-256 | `6acd622f37e1dc75d97a7e1359ddcc2ccf27f0f0bdbac6c764a7bfb64223c990` |
| Superseded Gate 1 runner SHA-256 | `5a06094acff93dde3889a189bf8ee6c0593650518a11a6cbcbc038209c470e20` |
| Corrected Gate 1 runner SHA-256 | `813312fd4c5cfae97ce45a1e7add75bdda487a537297775dcb747398ff04c60f` |
| Files changed | `local_run002/llama_server_backend_run002.py`, `local_run002/run002_gate1.py`, `docs/phase1-run002-governance-record.md` (this record) |
| **Corrected commit (pinned)** | **`3f2bda15a74e5f2f3d57caa3888e115d7960d035`** — *Run 002: enforce the reasoning-content invariant on the real generate() path*, on branch `run002/final-interface`, parent `9a89662` |
| Verified against the pinned commit | the corrected backend and Gate 1 runner SHA-256 values above are byte-identical to their blobs at `3f2bda15…`; the evidence in this package was produced by exactly that code |

Version `0.2` of this record is the copy committed **inside** `3f2bda15…`; a commit
object cannot contain its own hash, so this version `0.3` — which names the commit
explicitly — necessarily lives in a later, governance-only commit that changes no code.
Both versions are listed in the version history above and neither is overwritten.

**The previously tested backend is NOT byte-identical to the corrected backend and must
not be represented as such.** Historical preflight evidence — commit `9a89662` and
earlier, and `local_run001/` — is untouched: nothing was overwritten, amended or
deleted.

---

## 6. Not done, deliberately

- Case 001 was **not** executed, and no Case 001 model call was issued.
- No parser investigation was performed.
- No prompt, schema, validator or research-semantics change.
- No tuning, no retry, and no rerun for a favourable result.
- No push to any remote.

---

## Record hash

The SHA-256 of this document is published in
`local_run002/evidence_preseal/governance/GOVERNANCE_RECORD_SHA256.txt` and in the
package `SHA256SUMS.txt`, and is recalculated whenever this record changes. The
package's `INTEGRITY_REPORT.md` and `CONSISTENCY_CHECK.json` restate it, and
`CONSISTENCY_CHECK.json` re-derives it from the file on disk so a mismatch is caught
mechanically rather than by reading.
