# Phase 1 — Run 003 Configuration and Implementation-Freeze Packet

**Prepared:** 2026-10-12 · **Status:** preparation only.

> **This document does not declare the freeze.** Implementation freeze, Case 002
> release, Run 003 execution and deployment remain four separate decisions, none
> of which is taken or implied here. Case 002 was not opened. No model inference
> was run and no external provider was contacted.

Everything below is divided into **verified** (observed on the machine, from the
repository), **proposed** (constructed from the existing contract, awaiting
approval) and **pending** (decisions only Lillian can make). Nothing is carried
over from memory; every hash was recomputed for this document.

---

## 1. Verified commit and repository state

| | |
|---|---|
| Repository | `Sanuvia/sanuvia-reasoning-engine` |
| **Pinned commit** | `2444bf1f2afedd23d26fcbc564131e5b4e707d2c` |
| Merge commit on `main` | `0c0634c5ea9d971d149fd11abdedbd827f2b2e89` (PR #5) |
| Relationship | `2444bf1` is an **ancestor of `main`**; `git diff 2444bf1 origin/main` is **empty** — identical trees |
| Working tree | clean of tracked modifications; 7 protected untracked evidence paths present and unmodified |

Protected evidence re-verified for this packet: **36/36** files byte-identical
against `docs/repair-evidence/protected-evidence-manifest-2026-10-05.txt`, and
`run002_final_evidence_v0.7.tar.gz: OK` against its recorded checksum.

Governance freeze record `7.0-extraction-schema-v3-participant-labels`, hash
`16c7cbad9b364b0db86b9219a6dc2f0d768ba9afb9237246d678454aa8bf371c`.
`is_real_run_permitted()` is `True`, with **zero** blocking items and one
non-blocking pending item (`eval_hardware`, recorded at run time).

---

## 2. Prompt and schema pins — VERIFIED

Read from the live registry at the pinned commit, not transcribed.
`verify_prompt_integrity()` reports **no drift**.

| Boundary | Prompt id | Prompt SHA-256 |
|---|---|---|
| Evidence extraction | `extraction.observations.v3` | `05e1a9d408d720fa87fc663d8a0a17ff7fe757f5323e74047b86c0bac74ce1a3` |
| Evidence appraisal | `appraisal.support-contradict-propose.v3` | `d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c` |
| Identity resolution (R1) | `identity.r1.bounded.v1` | `45d0675753216e1439230776ffbf2150f82c760f04dd276b87344276415398d6` |
| Both baselines (shared) | `baseline.reasoning.v1` | `3557977b65552a1a19b3cff3a53f58b93c0efb6e802b821abe0b063cf03943bc` |

| Boundary | Schema id | Schema SHA-256 |
|---|---|---|
| Evidence extraction | `schema.extraction.v3` | `18b9b9968492e773237745d52c5d8a6ea09b5ccebe8f4007760e7baaf3320519` |
| Evidence appraisal | `schema.appraisal.v3` | `f8567cd05b764d0b4cc139e14216736db252b6874fd1c4f3020b878099d12459` |
| Identity resolution (R1) | `schema.identity.v1` | `31e731bed3c0917e15b6f669a8f9329f2adef046fe8673a6e3d24e7a178217e8` |
| Both baselines (shared) | `schema.baseline.v1` | `efa45b71e5043f3921048215677c04f140db7f3597b903b9b27a046582fbc11e` |

Extraction and appraisal at v3 are the versions Lillian approved for Run 003.
The R1 pair is **registered and hashed but not approved** — see §5.

---

## 3. Model artifact, runtime and generation settings — VERIFIED

### 3.1 Artifact

| | |
|---|---|
| Frozen identity | `Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b :: Qwen3-4B-Q4_K_M.gguf (2497280256 bytes)` |
| Frozen SHA-256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| Found at | `/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf` |
| Size on disk | `2497280256` bytes — **matches** |
| **Recomputed SHA-256** | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` — **matches** |

The hash was recomputed over the full 2.5 GB file for this packet, not read from
the governance record.

### 3.2 Runtime

| | Frozen value | Observed on the machine |
|---|---|---|
| Backend | llama.cpp (GGUF) | `llama-cli`, `llama-server` at `/usr/local/bin` |
| Build | build 10721 (commit `8e53fcefd`), macos-x64 prebuilt (v0.3.0-dev) | `version: 0.3.0-dev (build 10721, commit 8e53fcefd)` — **matches** |

### 3.3 Generation parameters — frozen and matched by `qwen_real_run_config()`

`temperature 0.0` · `seed 0 (fixed)` · `max_output_tokens 512` ·
`context_window 8192` · `stop_sequences none` · `retries 0` ·
`quantization Q4_K_M` · `provider local_qwen` (local only, no cloud, no API key)

Preflight check `approved_generation_config` confirms these against governance:
`temperature=0.0, seed=0, max_output_tokens=512, context_window=8192, stop=none, retries=0`.

---

## 4. Run-machine verification — VERIFIED

**Machine:** `macs-MacBook-Pro-2.local` — Darwin 22.6.0, macOS 13.7.8 (22H730),
x86_64. Python 3.14.6 in `.venv`. 45 GiB free on the repository volume.

Every line below was executed on this machine for this packet.

| Check | Command / source | Result |
|---|---|---|
| Artifact present | `ls -l` on the path above | 2 497 280 256 bytes |
| Artifact integrity | `shasum -a 256` | matches frozen value |
| Runtime present | `command -v llama-cli llama-server` | both at `/usr/local/bin` |
| Build identity | `llama-cli --version` | build 10721, commit `8e53fcefd` |
| Detection | `detect_local_qwen()` with `SANUVIA_QWEN_MODEL_PATH` set | `available=True`, artifact + SHA-256 + build all `available` |
| Pinned code present | `git diff 2444bf1 origin/main` | empty |
| Prompt/schema versions present | `prompts.PROMPTS` / `prompts.SCHEMAS` | all 4 + 4 registered, no drift |
| Local inference path exercisable | `QwenClient` over a fake in-process backend (11 boundary tests) | passed, no provider contacted |
| Storage | `df -h` | 45 GiB free |

**Limitations, stated rather than glossed:**

1. `SANUVIA_QWEN_MODEL_PATH` is **unset** in the shell environment. The artifact
   exists and verifies, but every run must export it, or detection reports the
   model missing. This is the single operational step between the machine as it
   stands and a runnable configuration.
2. **No weights were loaded and no token was generated.** "Local inference path
   exercisable" means the code path from `QwenClient` to `QwenBackend.generate`
   was driven end to end with a fake backend. Actually loading the model is part
   of Run 003 and is not done here.
3. The llama.cpp build matched by string comparison against the frozen value.
   The binary itself is not checksummed by any governance item.

---

## 5. Participant roster — configuration contract

**Lillian supplies the authorised roster separately. It is not invented here and
is not derived from Case 001, which is a single-subject, speakerless transcript
and establishes no roster.** Case 002 was not opened.

### 5.1 Format

A tuple of canonical participant identifier strings, supplied in **two places
that must agree**:

```python
config    = qwen_real_run_config(participants=("<id1>", "<id2>", ...))
extractor = client.as_extractor(permitted_participants=("<id1>", "<id2>", ...))
```

### 5.2 Validation rules, as implemented

`runconfig.validate_run_configuration` refuses a REAL run, before anything
executes, when:

| Rule | Message |
|---|---|
| roster empty in config | `RealRunConfig.participants is empty` |
| extractor exposes no roster | `extractor exposes no permitted_participants` |
| extractor roster empty | `extractor was built with an empty participant roster` |
| the two rosters disagree | `extractor roster [...] does not match RealRunConfig.participants [...]` |

Order is **not** part of the configuration: minting sorts and deduplicates, so a
roster stated in a different order is accepted.

### 5.3 Label generation, verified with placeholders

Exercised with placeholder identifiers only — no real participant identifier was
used, and Case 002 was not opened:

```
input roster (unsorted, duplicated): ('<P2>', '<P1>', '<P1>')
minted labels                      : ('t-demo:1::P1', 't-demo:1::P2')
canonical order after sort+dedupe  : ('<P1>', '<P2>')
label format                       : {request_id}::P{n}
resolve('t-demo:1::P1')            -> '<P1>'
resolve('t-demo:1::P9')            -> GovernedRejection(EVIDENCE_ROLE_VIOLATION)
```

Only labels reach the model; the canonical roster never enters a prompt. The
mapping back to a canonical identifier happens inside the application boundary in
`ParticipantVocabulary.resolve`.

### 5.4 Checks that cannot complete until the roster is supplied

| Check | State without a roster |
|---|---|
| `no_scripted_doubles_in_real` | **BLOCKED** — `RealRunConfig.participants is empty` |
| `preflight-real` overall | **BLOCKED** — by the above alone |
| extractor/config roster agreement | not evaluable |
| end-to-end extraction against the real transcript | not runnable |

Every other preflight check is roster-independent and passes — see §7.

---

## 6. Proposed R1 identity-resolution configuration — PROPOSED, NOT APPROVED

R1 is **not** silently omitted, and `None` is **not** treated as a decision
already taken. A concrete configuration is proposed below so the decision can be
made on something specific.

### 6.1 Proposed pins

Built from the **same template the other four boundaries already use** — no new
provider and no new model pin is introduced. Only the role, prompt and schema
differ from the approved extraction spec.

| Field | Proposed value | Basis |
|---|---|---|
| `role` | `identity_resolution` | existing `BoundaryKind.IDENTITY_RESOLUTION` |
| `provider` | `local_qwen` | existing frozen pin |
| `model` | `qwen3-4b` | existing frozen pin |
| `prompt_id` | `identity.r1.bounded.v1` | registered |
| prompt SHA-256 | `45d0675753216e1439230776ffbf2150f82c760f04dd276b87344276415398d6` | computed |
| `schema_id` | `schema.identity.v1` | registered |
| schema SHA-256 | `31e731bed3c0917e15b6f669a8f9329f2adef046fe8673a6e3d24e7a178217e8` | computed |
| `temperature` / `seed` | `0.0` / `0` fixed | existing frozen pins |
| `max_output_tokens` / `context_window` | `512` / `8192` | existing frozen pins |
| `backend_id` / `quantization` / `stop_sequences` | `llama.cpp-gguf` / `Q4_K_M` / `none` | existing frozen pins |

### 6.2 The configuration object

```python
proposed = dataclasses.replace(
    qwen_real_run_config(participants=<roster>, ...),
    identity_resolution=dataclasses.replace(
        base.extraction,
        role="identity_resolution",
        prompt_id=prompts.IDENTITY_PROMPT_ID,
        schema_id=prompts.IDENTITY_SCHEMA_ID,
        # extra_params carry the identity prompt/schema hashes
    ),
)
```

Verified: `RealRunConfig.specs()` returns **5** boundaries, `_incomplete()` is
empty, and `preflight-real` returns **OVERALL: PASS** with this spec present.

### 6.3 How the resolver is injected

```
run_transcript_demonstration(..., identity_resolver=ExternalIdentityResolver(client))
    -> validate_run_configuration(REAL, ..., identity_resolver=...)
    -> SanuviaPersistentCondition(case, appraiser, identity_resolver=...)
    -> build_in_memory_dependencies(..., identity_resolver=...)
    -> DeterministicAdjudicator -> §2 G resolution-order case 4 only
```

The resolver is consulted for a plausible-but-inexact candidate and nothing
else. It receives the candidate statement and resolution-scoped refs `C1`,
`C2`, …; no durable `HypothesisId` crosses the boundary.

### 6.4 REAL excludes scripted resolvers — verified

Two independent refusals, each with its own test:

| Guard | Refusal |
|---|---|
| `validate_run_configuration(REAL, identity_resolver=ScriptedIdentityResolver())` | `ConfigurationError: identity_resolver is a ScriptedIdentityResolver (REAL must not decide identity from fixture-authored data)` |
| `SanuviaPersistentCondition(..., identity_resolver=ScriptedIdentityResolver())` | `ConfigurationError: a ScriptedIdentityResolver was supplied to the real branch … (G-1)` |

Also refused: a real resolver in GOLDEN; a resolver supplied without a real
appraiser; a configured resolver with no `identity_resolution` spec.
`tests/phase1/test_real_resolver_wiring.py` (22) and
`test_resolver_wiring_guard.py` (6) pass.

### 6.5 Approval status — PENDING

> **The proposed R1 provider/model/prompt/schema is NOT approved.** The
> 2026-08-26 Run-001 governance approval predates R1; R1 carries no governance
> item, and `qwen_real_run_config()` emits no `identity_resolution` spec by
> default. Running R1 in Run 003 requires Lillian's explicit approval of §6.1.
>
> **Not running R1 is equally a decision that has not been taken.** With
> `identity_resolver=None`, §2 G parks a non-exact candidate as
> `AMBIGUOUS_REVIEW_REQUIRED` rather than guessing. That is a valid REAL
> configuration — but it changes what Run 003 can observe, so it is recorded
> here as a choice, not a default.

---

## 7. Non-case preflight results

Run on the machine in §4, with `SANUVIA_QWEN_MODEL_PATH` exported. Case 002 was
not opened and no provider was contacted.

### 7.1 `preflight-real`, three configurations

| Configuration | Overall | Blocked checks |
|---|---|---|
| A. `qwen_real_run_config()` as shipped | **BLOCKED** | `no_scripted_doubles_in_real` (roster empty); `model_version_identifiable` |
| B. + placeholder roster | **BLOCKED** | `model_version_identifiable` only |
| C. + roster + `model_version` + `artifact_id` + proposed R1 spec | **PASS** | none — **17/17** |

Configuration C is the proposed Run 003 configuration. The 17 checks that pass
include `governance_freeze_complete`, `prompt_integrity_no_drift`,
`approved_model_and_quantisation`, `approved_generation_config`,
`llama_cpp_build_matches_frozen`, `artifact_sha256_recorded`,
`no_network_dependency`, `phase0_import_frozen` and `phase0_git_untouched`.

> **Read C correctly.** It used a **placeholder** roster. Preflight validates
> that a roster is present and internally consistent; it cannot validate *who*
> is on it. C demonstrates that the configuration *shape* is complete — it does
> **not** mean Run 003 is ready to execute. The real roster and the R1 decision
> are still required.

`model_version_identifiable` clears only once the config records the exact model
version; passing the frozen `model_artifact_version` satisfies it. That value is
already frozen in governance, so this is transcription, not a new pin.

### 7.2 Code verification

| Check | Result |
|---|---|
| Root tests | **365 passed** |
| Phase 1 tests | **377 passed** |
| Root `mypy --strict` | clean, 69 source files |
| Phase 1 `mypy --strict` | clean, 87 source files |
| Phase 0 exit gate | `RESULT: PASS` (8/8) |
| Deployment smoke (shell, end-to-end) | `SMOKE OK` |
| Subject/space isolation | 20 passed |
| Resolver wiring / guard | 22 / 6 passed |
| Participant vocabulary / Qwen prompt boundary | 18 / 11 passed |
| REAL config guard / speaker context | 17 / 13 passed |

Nothing failed, was skipped, or went unexecuted.

### 7.3 Unverified items

| Item | Why | How to verify |
|---|---|---|
| Actual model load and token generation | Run 003 itself; not done in preparation | execute Run 003 once authorised |
| llama.cpp **binary** checksum | no governance item pins it; only the build string is frozen | add a governance item if binary-level pinning is wanted |
| `eval_hardware` | pending governance, explicitly **non-blocking**; recorded at run time | record during Run 003 |
| Roster contents | supplied separately by Lillian | §5 |

---

## 8. Outstanding decisions required from Lillian

1. **Supply the authorised participant roster** (§5). Until then
   `preflight-real` is BLOCKED and extraction cannot run against a real
   transcript.
2. **Approve or decline the proposed R1 configuration** in §6.1 — and if
   declined, confirm that Run 003 runs with `identity_resolver=None` and parks
   non-exact candidates. Both are decisions; neither is a default.
3. **Confirm the model-version transcription.** Configuration C records
   `model_version` from the frozen `model_artifact_version`. Confirm that
   transcribing the frozen value into the run config is intended, since it is
   what clears `model_version_identifiable`.
4. **Confirm `SANUVIA_QWEN_MODEL_PATH`** should point at
   `/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf` for Run 003. The
   file at that path verifies against the frozen SHA-256; the variable is
   currently unset.
5. **Declare the implementation freeze**, if and when the above are settled.
   This packet does not declare it.

---

## 9. Withheld and not executed — confirmed

- **Case 002 was not opened.** No Case 002 file was read, listed or inspected;
  no Case 002 content appears in this document. No Case 002 material is tracked
  in the repository. Every example above uses placeholder identifiers.
- **Run 003 has not been executed.** No weights were loaded, no token was
  generated, and no model inference was run at any boundary.
- **No external provider was contacted.** Every test in this verification uses a
  fake in-process backend. `provider=local_qwen` for every boundary, and the
  `no_network_dependency` check passes.
- **Nothing was deployed.**
- **No implementation freeze is declared** by this packet, and no Case 002
  release or Run 003 authorisation is implied by it.
- **Protected evidence is unchanged**: 36/36 manifest files byte-identical, the
  sealed Run 002 archive verifies, and all 7 untracked evidence paths remain
  untracked and unmodified.
