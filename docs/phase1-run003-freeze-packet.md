# Phase 1 — Run 003 Configuration and Implementation-Freeze Packet

**Prepared:** 2026-10-12 · **Status:** preparation only.

> **Amended 2026-10-24 — governance record `8.0-run003-output-cap-1536-and-chat-template-pin`,
> hash `sha256:f62c33b1dd72d623c685267cb54e5eade5bfeb41e86b9a7c556a7f5384a17bac`.**
> `max_output_tokens` is now **1536**, superseding the 512 recorded below, and
> the serving chat-template digest is now a frozen item. Values in this
> document that were written against the 512 cap are marked at the point where
> they appear. Nothing else in the configuration changed. Run 003 Stage 1
> attempt 1 (2026-10-23) executed at 512 and **failed**; it is retained as a
> failed attempt and is not superseded by this amendment.

> **This document does not declare the freeze.** Implementation freeze, Case 002
> release, Run 003 execution and deployment remain four separate decisions, none
> of which is taken or implied here. Case 002 was not opened. No model inference
> was run and no external provider was contacted.

Everything below is divided into **verified** (observed on the machine, from the
repository), **proposed** (constructed from the existing contract, awaiting
approval) and **pending** (decisions only the project owner can make). Nothing
is carried over from memory; every hash in this document was recomputed, with
the single stated exception of the supplied seal-manifest hash in §5.1.

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

Extraction and appraisal at v3 are the versions approved for Run 003.
The R1 pair is **registered and hashed but not approved** — see §6.5.

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

`temperature 0.0` · `seed 0 (fixed)` · `max_output_tokens 1536` *(amended; was 512)* ·
`context_window 8192` · `stop_sequences none` · `retries 0` ·
`quantization Q4_K_M` · `provider local_qwen` (local only, no cloud, no API key)

Preflight check `approved_generation_config` confirms these against governance:
`temperature=0.0, seed=0, max_output_tokens=1536, context_window=8192, stop=none, retries=0`
*(amended 2026-10-24; the packet as prepared on 2026-10-12 read `max_output_tokens=512`).*

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

## 5. Authorised Case 002 configuration — SUPPLIED

The project owner supplied the configuration below. It is **configuration
metadata**, recorded here exactly as provided.

> **It was not derived from the Case 002 package.** That package was not
> accessed, listed, read, inspected, copied, hashed or processed at any point in
> preparing this packet. Nothing below was obtained by looking at it.

### 5.1 Authorised values

| Key | Authorised value |
|---|---|
| `subject_id` | `relationship-1` |
| `space_kind` | `SHARED` |
| Executable participant roster | `participant-1`, `participant-2` |
| Divergence-eligible pair | `participant-1`, `participant-2` |
| Facilitator | **excluded** from the REAL input and from the participant roster |
| Reviewer | **excluded** from the REAL input and from the participant roster |

**Seal-manifest SHA-256**, recorded exactly as supplied:

```
6dbcc2f5edecdabcf62488d7009cae2d26b8d4a2f0d9d86df44a7323bea644e6
```

> This value is **transcribed, not verified.** Verifying it would mean hashing
> the sealed package, which is precisely what this packet must not do. It is
> recorded so the seal can be checked later by whoever is authorised to open the
> package. Every other hash in this document was recomputed; this one was not,
> and that distinction is deliberate.

### 5.2 How the authorised values enter the configuration

```python
ROSTER = ("participant-1", "participant-2")

config    = qwen_real_run_config(participants=ROSTER, ...)
extractor = client.as_extractor(permitted_participants=ROSTER)
```

`space_kind=SHARED` follows from the space identifier rather than being set
separately — verified: `shared_space_id("relationship-1")` yields
`space:shared:relationship-1`, and `space_kind_of(...)` returns `SHARED`. A
shared space is what §2 J.1 rule 7 requires before any divergence candidate may
be offered, so the divergence-eligible pair above is consistent with the space
kind rather than an independent assertion.

**The facilitator and reviewer are excluded by construction, not by filtering.**
They are absent from the roster, so no request-scoped label is ever minted for
them; a model naming one is refused by `ParticipantVocabulary.resolve` as an
unoffered label, and they can never be a validated `source_id` or `subject_id`.
The exclusion therefore needs no separate enforcement path.

### 5.3 Validation rules, as implemented

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

### 5.4 Label generation under the authorised roster — VERIFIED

Minted from the authorised roster. The transcript id is left as a placeholder
because it belongs to the sealed package and was not looked up:

```
interaction 1: {'<transcript-id>:1::P1': 'participant-1',
                '<transcript-id>:1::P2': 'participant-2'}
interaction 2: {'<transcript-id>:2::P1': 'participant-1',
                '<transcript-id>:2::P2': 'participant-2'}
```

Request-scoped, so interaction 2's labels are not interaction 1's even for the
same participant. Only labels reach the model; `participant-1` and
`participant-2` never enter a prompt. The mapping back to a canonical identifier
happens inside the application boundary in `ParticipantVocabulary.resolve`, and
an unoffered label raises `GovernedRejection(EVIDENCE_ROLE_VIOLATION)`.

### 5.5 Roster-dependent checks — now CLEARED

These were blocked while the roster was outstanding. With the authorised roster
supplied they are evaluated and pass:

| Check | State |
|---|---|
| `no_scripted_doubles_in_real` | **PASS** — REAL guard accepts the configuration |
| `preflight-real` overall | **PASS** — 17/17 (§7) |
| extractor/config roster agreement | **PASS** — same roster on both sides, accepted |

One roster-dependent item remains outstanding, and it is not a preflight check:

| Item | State |
|---|---|
| end-to-end extraction against the real transcript | **not run** — that is Run 003, and the transcript is in the sealed package |

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
| `max_output_tokens` / `context_window` | `1536` / `8192` | `1536` amended 2026-10-24 (was `512`); `8192` unchanged |
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
> default. Running R1 in Run 003 requires the project owner's explicit approval
> of §6.1.
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

### 7.1 `preflight-real` under the authorised roster

Re-run with the authorised roster `("participant-1", "participant-2")` on both
the config and the extractor. Earlier placeholder runs are superseded.

| Configuration | Overall | Result |
|---|---|---|
| Authorised roster, **without** R1 (`identity_resolver=None`) | **PASS** | 17/17 |
| Authorised roster, **with** the proposed R1 spec | **PASS** | 17/17 |

Both pass, which is itself the point: preflight does **not** discriminate
between the two R1 options, so a green preflight is not evidence that either has
been chosen. §6.5 remains the governing statement.

The REAL guard was also exercised directly with the authorised roster on both
the config and the extractor, and accepted it.

The 17 passing checks include `governance_freeze_complete`,
`prompt_integrity_no_drift`, `approved_model_and_quantisation`,
`approved_generation_config`, `llama_cpp_build_matches_frozen`,
`artifact_sha256_recorded`, `no_scripted_doubles_in_real`,
`no_network_dependency`, `phase0_import_frozen` and `phase0_git_untouched`.

> **What a PASS here does and does not mean.** It means the configuration is
> complete and internally consistent, the artifact and runtime match their
> frozen identities, and no scripted double or network dependency is present. It
> does **not** mean Run 003 is authorised to execute, that R1 has been decided,
> or that the implementation is frozen. Those are the decisions in §8.

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
| Roster contents | supplied by the project owner | §5 — now supplied |

---

## 8. Outstanding decisions required from the project owner

**Settled by the current authorisation:**

- The participant roster is supplied (§5) and every roster-dependent preflight
  check now passes.

**Still open:**

1. **Approve or decline the proposed R1 configuration** in §6.1 — and if
   declined, confirm that Run 003 runs with `identity_resolver=None` and parks
   non-exact candidates. Both are decisions; neither is a default. **The roster
   authorisation does not bear on this**: it authorised participants, not an
   identity-resolution provider, and preflight passes either way.
2. **Confirm the model-version transcription.** The run configuration records
   `model_version` from the frozen `model_artifact_version`. Confirm that
   transcribing the frozen value into the run config is intended, since it is
   what clears `model_version_identifiable`.
3. **Confirm `SANUVIA_QWEN_MODEL_PATH`** should point at
   `/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf` for Run 003. The
   file at that path verifies against the frozen SHA-256; the variable is
   currently unset.
4. **Declare the implementation freeze**, if and when the above are settled.
   This packet does not declare it.

---

## 9. Withheld and not executed — confirmed

- **The Case 002 package was not opened.** It was not accessed, listed, read,
  inspected, copied, hashed or processed. No Case 002 *content* appears in this
  document, and no Case 002 material is tracked in the repository.
- **The configuration in §5 is supplied metadata, not an inspection result.**
  `subject_id`, `space_kind`, the roster, the divergence-eligible pair, the
  facilitator/reviewer exclusions and the seal-manifest hash were all provided by
  the project owner. None of them was derived from the package. The
  seal-manifest hash is **transcribed and not verified**, because verifying it
  would require hashing the sealed package.
- **No fixtures were authored** and nothing was pre-registered.
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
