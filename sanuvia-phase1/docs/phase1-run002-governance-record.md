# Phase 1 — Run 002 Governance Record

**Status:** SEALED by Lillian; **Case 001 EXECUTED** under her explicit authorisation
**Record version:** `0.7-run002-git-state-corrected`
**Scope:** Run 002 execution plumbing and the single governed Case 001 execution
**Pinned correction commit:** `3f2bda15a74e5f2f3d57caa3888e115d7960d035`
**Technical review:** bounded correction reviewed and approved by Lillian, who then
sealed Run 002 and authorised Case 001 execution. The execution was performed once,
against the pinned commit, execution configuration `48c8fb06…f07f2c4` and reviewed
pre-seal archive `cbcd83fd…2537971`.
**Companion:** [Run 001 Governance / Freeze Record](phase1-governance-freeze-record.md) —
frozen at `3.0-run001-verified`, **untouched by this record**.

**Version history (audit trail — never overwritten):**

| Version | record_sha256 | Note |
|---|---|---|
| `0.2-run002-execution-path-corrected` | `4386ad61f118700d748003dab1f8b67a85a2ebe9605de37d6f5e212e95657d73` | the record as committed inside `3f2bda1`; referenced the corrected commit indirectly, by content hash |
| `0.3-run002-preseal-pinned` | `e9ae2a6e5e81ccc54a36547400756954e7f2843d8c79c027ad8362d35cb75aa4` | repinned to name commit `3f2bda15a74e5f2f3d57caa3888e115d7960d035` explicitly; **superseded**: its "No push to any remote" line was inaccurate — the pinned commit had already been pushed to `origin` from this repository, outside the work that produced the record |
| `0.4-run002-preseal-pinned` | `7f2dd8a14fe3cfcb3e713fcba515425b39a65e0c788d0e3dd145db4a61ceafa3` | corrected the push statement to the verified facts; **superseded**: it still described Case 001 as not executed, and two of its cross-references to version `0.3` went stale when `0.4` was issued |
| `0.5-run002-case001-executed` | `cfd133e6c964a61809eb79c64dafda9e79defc2415d9425f25908d13f8b08c8b` | records Lillian's seal and the single authorised Case 001 execution (§7); repairs the two stale `0.3` cross-references. **Superseded**: it stated the governance commits were not pushed, which ceased to be true when the repository owner pushed the branch |
| `0.6-run002-case001-executed-pushed` | `089b8cf5a1489d71cbbb7bc3e1ea8d78ee086803b106b8d1b6331e5264e3d789` | records that the branch, including the Case 001 execution commit, has been pushed to `origin`. **Superseded**: §8 named `origin` as `8ab7b49…` and said local `HEAD` matched it. That sentence was falsified by its own commit and has since been overtaken by a further push (§9) |
| `0.7-run002-git-state-corrected` | published alongside — see *Record hash* | corrects the Git-state record (§9) to the verified values and states the self-reference limit that produced the error. Non-material documentation correction: no Gate, regression or Case 001 rerun performed or required, and no experimental artifact altered |

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
| 7 | **Case 001 HAS now been executed — once — under Lillian's explicit authorisation**, after she sealed Run 002. Statement 7 of versions `0.2`–`0.4` recorded that Case 001 had not been executed; that was true when written and is superseded here. The execution is recorded in §7. Gate 1 and Gate 2 evidence remains what it was: produced over synthetic, non-Case-001 input. |

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
object cannot contain its own hash, so every later version that names the commit
explicitly — `0.3`, `0.4` and this version `0.5` — necessarily lives in a subsequent,
governance-only commit that changes no code. Every version is listed in the version
history above and none is overwritten.

**The previously tested backend is NOT byte-identical to the corrected backend and must
not be represented as such.** Historical preflight evidence — commit `9a89662` and
earlier, and `local_run001/` — is untouched: nothing was overwritten, amended or
deleted.

---

## 6. Not done, deliberately

- No parser investigation was performed.
- No prompt, schema, validator, configuration or research-semantics change.
- No tuning, no retry, and no rerun — of the correction or of Case 001.
- No push was performed by the work that produced this record, or by the Case 001
  execution itself. Every push of this branch was made by the repository owner. The
  branch — including the Case 001 execution commit — is now on `origin`; see §8.
  Push state is recorded in the evidence package (`INTEGRITY_REPORT.md`,
  `CONSISTENCY_CHECK.json`) rather than assumed.

---

## 7. The governed Case 001 execution

Authorised by Lillian after sealing Run 002. Executed **once**. No retry, no rerun, no
repair, no tuning. The harness asserted the governed pins *before* issuing any model
call and would have refused to run had any failed; it also refuses to run at all if a
Case 001 provenance log already exists, so a second execution cannot overwrite the
first.

| Pin | Value | Verified |
|---|---|---|
| Commit | `3f2bda15a74e5f2f3d57caa3888e115d7960d035` | yes — backend, `qwen.py`, `manifest.py`, `validation.py`, `prompts.py` byte-identical to that commit |
| Execution configuration | `48c8fb0619e245bf7248702811d6d8cb133a6572c70c15435417fda81f07f2c4` | yes |
| Reviewed pre-seal archive | `cbcd83fd9e9228b85a6f01afaf146c263801fd8e303c0844c9c8e9f672537971` | yes |

All three conditions were driven from **one** `pipeline.run_transcript_demonstration`
call over the **same** frozen Case 001 transcript
(`case-001-leadership-trajectory`, 6 interactions, `seq-5` an empty hold), so the
frozen fairness guard applies unchanged.

### Result — `execution_status: completed`

| Condition | Interactions | Sequence | Outcome |
|---|---|---|---|
| `sanuvia_persistent` | 6 | `seq-1 … seq-6` | all `success` |
| `fm_stateless` | 6 | `seq-1 … seq-6` | all `success` |
| `fm_transcript` | 6 | `seq-1 … seq-6` | all `success` |

**25 model calls**, every one `success` at **1 attempt** — `evidence_extraction` 5
(`seq-5` correctly issued none: an empty hold produces no extraction call),
`evidence_appraisal` 8, `stateless_baseline` 6, `transcript_baseline` 6. Per-interaction
status is `success` for all six seq labels. Evidence references per interaction:
1, 1, 3, 1, 0, 2 — `seq-5` preserved as a genuine no-new-evidence hold.

**No governed failure occurred.** The reasoning-content invariant held on every call:
`reasoning_content` was absent on all 25, no `message.content` contained `<think>`,
every `finish_reason` was `stop`, and no backend error was recorded. Because nothing
was malformed, no interaction was stopped and no `MALFORMED_OUTPUT` / `NOT_EXECUTED`
status arose. Had one arisen it would have been recorded visibly and the affected
interaction stopped, unrepaired — the mechanism proven by Gate 2.

This is the result Run 001 could not reach: Run 001 aborted at its **first** call with
`MalformedOutputError: response is not valid JSON` (1 call record, the `<think>`
envelope). Run 001's evidence is untouched.

Totals: 9,687 tokens, 1,466 s of model time. Frozen generation parameters throughout
(temperature 0.0, seed 0, max output 512, context 8192, no stop sequences, retries 0);
governance freeze `3.0-run001-verified` / `3f46ef56…c0a2dd`. Complete server JSON,
`message.content`, `reasoning_content`, finish reason and usage are preserved for every
call in `evidence_case001/raw_calls.jsonl`, and the full run manifest — all 25 call
records with raw responses — in `evidence_case001/run002_case001_evidence.json`.

---

## 8. Push state

The branch `run002/final-interface` has been pushed to `origin` by the repository
owner. As of record version `0.6`, `origin/run002/final-interface` is
`8ab7b49c57d3b08006482c19f61cb21fcfbf5390` — the Case 001 execution commit — and local
`HEAD` matches it.

No push was performed by the work that produced the correction, the evidence package or
this record. Pushing does not alter any evidence: the artifacts were produced at the
pinned commit `3f2bda15…`, which remains an **ancestor** of the remote head, and the
commits between the pinned commit and the remote head change no source file — they
carry record versions `0.3`–`0.6` only.

Version `0.5` of this record stated that those commits were not pushed. That was true
when written and is superseded here. `CONSISTENCY_CHECK.py` was corrected at the same
time: it had asserted that `origin` pointed *exactly* at the pinned commit, which
encoded a moment in time rather than the property that actually matters. It now asserts
the durable invariants — the pinned commit is an ancestor of the remote head, the remote
head is a commit that exists locally, and no source changed between them.

---

## 9. Git state — corrected record

Raised in Lillian's independent review of the final evidence package: the integrity
report recorded local `HEAD` and `origin` as different commits, while §8 of version
`0.6` said they matched. The review is correct that the two disagreed. On inspection the
repository had also moved on, so the correction required is not the one described.

### Verified state

Established by direct inspection, not inference:

| Command | Result |
|---|---|
| `git rev-parse HEAD` | `8746c8f3cd27bd3bfe5408487ee0c6515148c560` |
| `git rev-parse origin/run002/final-interface` | `8746c8f3cd27bd3bfe5408487ee0c6515148c560` |
| `git ls-remote origin refs/heads/run002/final-interface` | `8746c8f3cd27bd3bfe5408487ee0c6515148c560` |
| `git rev-list --left-right --count origin/run002/final-interface...HEAD` | behind 0, ahead 0 |

`8746c8f…` is the commit carrying record version `0.6`. It has been pushed, so at the
moment of writing local `HEAD` and `origin` are equal.

### What is superseded

Version `0.6` §8 stated that `origin/run002/final-interface` was
`8ab7b49c57d3b08006482c19f61cb21fcfbf5390` and that local `HEAD` matched it. Both halves
are now wrong: `origin` has advanced to `8746c8f…`. That statement is superseded here.
The same stale value appeared in the package's `INTEGRITY_REPORT.md` (§9) and
`BYTE_IDENTITY.json` (`push_state`), both corrected alongside this record.

### Why it went stale, and how this version avoids repeating it

The sentence in `0.6` was falsified by the act of committing it. It was written while
`HEAD` was `8ab7b49…`; committing that text moved `HEAD` to `8746c8f…`, so the record
was inaccurate the moment it existed.

This is the **self-reference limit** already recorded in §5 for the record's own hash: a
commit cannot contain its own SHA, and for the same reason a record cannot state the
`HEAD` its own commit produces. A version that asserted "local `HEAD` is `8746c8f…`"
would recreate the defect exactly — committing it advances `HEAD` past that value.

This version therefore records only **durable** facts:

- `origin/run002/final-interface` holds `8746c8f…`, the commit carrying record `0.6`;
- the pinned Run 002 commit `3f2bda15a74e5f2f3d57caa3888e115d7960d035` remains an
  **ancestor** of that remote head, and no source file changed between them — the
  intervening commits carry record versions `0.3`–`0.7` only;
- **committing this record necessarily advances local `HEAD` one commit beyond
  `origin`.** That is expected and is not a discrepancy. It resolves when the commit is
  pushed, which is a separate, explicitly authorised act.

A future reader should compare `origin` against the pinned commit by **ancestry**, not
by equality with any `HEAD` value quoted in a document.

### Scope of this correction

Documentation only. No Gate 1, Gate 2, regression or Case 001 rerun was performed, and
none was required. The Case 001 evidence, raw model calls, run manifest, provenance,
execution configuration, frozen protocol files, backend, harness and Run 001 evidence
are all unchanged and byte-identical. Version `0.6` is preserved unchanged in history at
commit `8746c8f…`; nothing earlier is rewritten.

---

## Record hash

The SHA-256 of this document is published in
`local_run002/evidence_preseal/governance/GOVERNANCE_RECORD_SHA256.txt` and in the
package `SHA256SUMS.txt`, and is recalculated whenever this record changes. The
package's `INTEGRITY_REPORT.md` and `CONSISTENCY_CHECK.json` restate it, and
`CONSISTENCY_CHECK.json` re-derives it from the file on disk so a mismatch is caught
mechanically rather than by reading.
