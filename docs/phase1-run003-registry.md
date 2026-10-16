# Run 003 — pre-registration registry

**Case:** `case-002-relationship-anxiety-and-contribution`
**Prepared:** 2026-10-14
**State:** private custody **complete** in the organisation repository, with
access verified and committed-byte hashes **verified** (§3). Remaining: nominate
an unexposed evaluator, resolve the host object-purge request, and dispose of
the duplicate custody copy.

> **Authorisation.** Fixture authoring and pre-registration only. Inference,
> Run 003 execution and deployment are **not** authorised and are separate
> decisions.

---

## 1. Pinned implementation

| | |
|---|---|
| Repository | `Sanuvia/sanuvia-reasoning-engine` |
| **Frozen executable implementation** | `0c0634c5ea9d971d149fd11abdedbd827f2b2e89` |
| PR #6 final merge commit | `9160df01af5ad4190156f3a79f20b700e1e9b697` |
| Governance freeze record | `7.0-extraction-schema-v3-participant-labels` |
| Freeze record SHA-256 | `16c7cbad9b364b0db86b9219a6dc2f0d768ba9afb9237246d678454aa8bf371c` |

The executable implementation is unchanged since the freeze: `git diff` from
`0c0634c` to `main` over `src/`, `sanuvia-phase1/src/`,
`sanuvia-phase1/fixtures/` and all `*.py` was empty before this fixture was
added, and the fixture is additive — it modifies no frozen module.

---

## 2. Case and fixture identity

| | |
|---|---|
| Case id | `case-002-relationship-anxiety-and-contribution` |
| Transcript id | `case-002-relationship-anxiety-and-contribution` |
| **Executable fixture** | `sanuvia-phase1/fixtures/longitudinal/case_002.py` |
| **Isolated reference/provenance** | `sanuvia-phase1/reference/case_002_reference.py` |
| Fixture/isolation tests | `sanuvia-phase1/tests/phase1/test_case_002_fixture.py` |
| Source package version | `v1.0` |
| Seal-manifest SHA-256 (supplied) | `6dbcc2f5edecdabcf62488d7009cae2d26b8d4a2f0d9d86df44a7323bea644e6` |

The seal-manifest hash is **transcribed, not verified** — verifying it requires
hashing the sealed package.

### 2.1 Source provenance anchors

Reference ids only. The **source-media SHA-256 values are deliberately not
reproduced here**, and this is a change from the previous revision.

Two reasons. The public allowlist for this repository is exclusive and does not
include them. And a source-file fingerprint is a de-anonymisation aid:
published openly, it lets anyone holding a candidate recording confirm it is the
source material about identifiable people. The hashes stay with the project
owner and in the sealed package, where they serve their provenance purpose
without that exposure.

| Ref | Use |
|---|---|
| `SRC-201-A` | executable participant material |
| `SRC-204-A` | executable participant material |
| `SRC-204-R` | reference formulation only — never executable |
| `SRC-206-A` | executable participant material |
| `SRC-207-A` | participant material; later formulation isolated |
| `SRC-209-A` | participant material; later prescription isolated |

**Supplied but UNVERIFIED.** The source media was never received — only the
package documents — so there is nothing here to hash the supplied values
against. No claim of verification is made, and none should be inferred from
their presence in the sealed package.

## 3. Private custody — COMPLETE

### 3.1 Repository and commit

| | |
|---|---|
| Repository | `Sanuvia/sanuvia-case-002-custody` |
| Visibility | **private** — verified `private=true`, `visibility=private` |
| Forks / archived | 0 / no |
| **Commit SHA** | `6c0cded0282d67a3ee62a67cb92acd1e5c47e80e` |
| Branch | `main` |

### 3.2 Effective access — verified before transfer

Checked across every path, including inherited organisation and team access:

| Principal | Permission | Source |
|---|---|---|
| authorised holder A | admin | direct collaborator |
| authorised holder B | admin | organisation ownership |
| one further organisation member | read | organisation default permission |

| Path | Result |
|---|---|
| Team grants | **none** |
| Outside collaborators | **none** |
| Forks | **0** |

Both authorised holders hold admin. The third principal's inherited **read**
access was **accepted explicitly by the project owner** as a member of the
organisation, and is recorded here as an accepted decision rather than an
unresolved finding.

### 3.3 Committed-byte hashes — VERIFIED

Extracted from the commit and hashed, not read from a working copy:

```
git show HEAD:<path> | shasum -a 256
```

| Artifact | Committed-byte SHA-256 |
|---|---|
| `fixtures/longitudinal/case_002.py` | `9bf5350c71c2e7a887a02f0ada72ce93dd40f4a730134f8e5f7ee2f14c5aace7` |
| `reference/case_002_reference.py` | `ef6294033faeeb61d0973cabddde48beda2cc7dd89758e17cc2d1539718ab4e8` |
| `tests/phase1/test_case_002_fixture.py` | `ebd1f4725ccccfee7a768d9386f3eb4a7c4c8be5949dcca58f45ec52ab908a54` |

Three-way agreement confirmed — committed object, on-disk copy and authored
source give identical digests for each file, so nothing was transformed on
commit, line endings included. The custody working tree is clean, so it equals
the commit.

These are **artifact** hashes and are not the source-package anchors in §2.1.

### 3.4 What the commit contains

Five files: the three artifacts, a `.gitignore`, and a README stating the
custody boundary. The anonymisation map, post-result reference formulations,
source media, transcript excerpts and the six source-media fingerprints are
**not** present.

### 3.5 Duplicate custody copy — needs disposition

An earlier attempt placed the same three artifacts in a **user-account** private
repository, commit `75bb3fabbd865d2b19cfb394c35fea4eef6e1b03`, while the
organisation repository's inherited read access was still unresolved. The
artifact hashes are identical, so the two copies are byte-equivalent.

That copy is now redundant and **doubles the custody surface**. Recommended:
delete it and keep the organisation repository as the single custodial source.
Recorded rather than deleted unilaterally.

## 4. Governed identity

| Key | Value |
|---|---|
| `subject_id` | `relationship-1` |
| `space_id` | `space:shared:relationship-1` |
| `space_kind` | `SHARED` (verified from the identifier, not asserted) |
| Executable roster | `participant-1`, `participant-2` |
| Divergence-eligible pair | `participant-1`, `participant-2` |
| Facilitator / reviewer | excluded from REAL input and from the roster |

### 4.1 Participant labels

Request-scoped, minted per interaction over the sorted roster as
`{request_id}::P{n}`:

| Label | Canonical |
|---|---|
| `<request_id>::P1` | `participant-1` |
| `<request_id>::P2` | `participant-2` |

Only labels reach the model. The canonical ids never enter a prompt, and the
mapping back happens inside the application boundary in
`ParticipantVocabulary.resolve`.

---

## 5. Transcript structure

**10 sequences, preserved in fixed order, mapped to 39 interactions — APPROVED.**

The mapping is approved by the project owner. Sequence 3 remains **one empty
hold**.

A sequence is not always one interaction. `TranscriptInteraction` carries exactly
one speaker, so a sequence in which both participants speak cannot be a single
interaction without mis-attributing one of them. The sealed coverage decision
requires the opposite — "two incompatible attributable accounts" retained in the
partnership and dentist sequences, and an attributable divergence pair — and
divergence (§2 J.1 rules 3–5) requires two records with **different**
`source_id`. Consecutive same-speaker turns are therefore grouped, each group
becoming one interaction labelled `seq-N.K`; single-speaker sequences keep
`seq-N`.

| Sequence | Turns | `participant-1` | `participant-2` | Interactions |
|---:|---:|---:|---:|---:|
| 1 | 7 | 7 | 0 | 1 |
| 2 | 23 | 14 | 9 | 15 |
| **3** | **0** | 0 | 0 | **1 (hold)** |
| 4 | 4 | 2 | 2 | 2 |
| 5 | 3 | 2 | 1 | 2 |
| 6 | 16 | 11 | 5 | 9 |
| 7 | 7 | 6 | 1 | 3 |
| 8 | 2 | 2 | 0 | 1 |
| 9 | 9 | 4 | 5 | 4 |
| 10 | 3 | 3 | 0 | 1 |
| **Total** | **74** | **51** | **23** | **39** |

### 5.1 The deliberate empty hold

Sequence 3 carries no turns. It is one interaction with empty `text` and no
speaker — a governed harness hold, not a programme event and not evidence.

Expected behaviour, asserted by test: `ExternalEvidenceExtractor.extract`
answers empty text with `()` **before any client call**, so the hold cannot
reach a model; the interaction admits no evidence and makes no appraisal call;
and the evidence-store snapshot before and after is byte-identical.

---

## 6. Approved R1 identity-resolution configuration

| Field | Value |
|---|---|
| Provider | `local_qwen` |
| Model | `qwen3-4b` |
| Prompt id | `identity.r1.bounded.v1` |
| Prompt SHA-256 | `45d0675753216e1439230776ffbf2150f82c760f04dd276b87344276415398d6` |
| Schema id | `schema.identity.v1` |
| Schema SHA-256 | `31e731bed3c0917e15b6f669a8f9329f2adef046fe8673a6e3d24e7a178217e8` |
| Temperature / seed | `0.0` / `0` (fixed) |
| Max output / context | `512` / `8192` |

### 6.1 Extraction and appraisal pins

| Boundary | Prompt | Prompt SHA-256 | Schema | Schema SHA-256 |
|---|---|---|---|---|
| Extraction | `extraction.observations.v3` | `05e1a9d408d720fa87fc663d8a0a17ff7fe757f5323e74047b86c0bac74ce1a3` | `schema.extraction.v3` | `18b9b9968492e773237745d52c5d8a6ea09b5ccebe8f4007760e7baaf3320519` |
| Appraisal | `appraisal.support-contradict-propose.v3` | `d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c` | `schema.appraisal.v3` | `f8567cd05b764d0b4cc139e14216736db252b6874fd1c4f3020b878099d12459` |

`verify_prompt_integrity()` reports no drift.

### 6.2 Model artifact and path

| | |
|---|---|
| Artifact version | `Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b :: Qwen3-4B-Q4_K_M.gguf (2497280256 bytes)` |
| Artifact SHA-256 | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` — recomputed on the run machine, matches frozen |
| `SANUVIA_QWEN_MODEL_PATH` | `/Users/elite/models/qwen3-4b-q4_k_m/Qwen3-4B-Q4_K_M.gguf` |
| Runtime | llama.cpp build 10721 (commit `8e53fcefd`) — matches frozen |

---

## 7. Stage 2 separation

Stage 2 is a **separate synthetic governed interaction**, not part of the
historical transcript.

- **No Stage 2 content is pre-authored here.** The test response must be
  supplied or approved by the project owner *after* a real Stage 1 surface
  exists, and the surface must not be pre-selected or substituted.
- The turn is bound to canonical role `participant-1` **solely** so it crosses
  the frozen request-scoped participant boundary. That binding is not a claim
  that any person spoke the words.
- `synthetic_governed_interaction=true` and the approving owner must be recorded
  in the execution wrapper and audit provenance, **external to model-facing
  text**. If that marker cannot be preserved outside the model-facing text,
  Stage 2 stops rather than blending the turn into the historical source.
- A synthetic turn is never added to the Case 002 historical transcript and
  never presented as historical participant speech.

**Stage 2 has not been executed.**

---

## 8. Exposure register

| Party | Case-naive? | Exposure |
|---|---|---|
| Project owner | no | authorised holder; released the package |
| Implementation author | no | **authorised**; package received for fixture authoring |
| Authoring assistant | **no** | **EXPOSED 2026-10-14** — full package supplied into the authoring session |
| Overview / Product Agent workspace | **no** | declared exposed at seal in the sealed package |
| Claude | **no — see 8.1** | **EXPOSED 2026-10-14** |
| Any model / inference API | yes | **not exposed**; no Case 002 content was sent to a model |

### 8.1 Claude is not case-naive — correction

The sealed package records Claude's exposure as `none` and names Claude as a
candidate independent evaluator *"if the source remains withheld."* **The source
did not remain withheld.**

The authoring assistant in this work and "Claude" are the **same party**, not
two. On 2026-10-14 that party received, in full:

- the executable transcript (all 10 sequences, verbatim);
- the reference and provenance document — **including the anonymisation map and
  the post-result reference formulations**;
- the seal manifest;
- the Stage 2 interaction protocol.

That is the complete prohibited set: transcript, source-derived material and
reference answers. The condition attached to Claude's evaluator role therefore
fails, and **Claude cannot serve as the independent case-naive evaluator for
Case 002.**

This is recorded as a correction rather than a caveat because the sealed package
states the opposite, and an evaluation claim resting on the stale entry would be
invalid. An independent evaluation requires a party to whom none of the above
has been shown.

## 8.2 Verification actually run — 2026-10-16

Every line below was executed on the authoring machine for this revision. No
result is carried over from an earlier run.

| Check | Command | Result |
|---|---|---|
| Fixture + isolation tests | `pytest tests/phase1/test_case_002_fixture.py` | **22 passed** |
| Phase 1 suite | `pytest` | **399 passed** |
| Phase 1 strict typing | `mypy src tests fixtures` | clean, **89** files |
| Round trip | ungroup 39 interactions, compare to authored turns | **74 = 74, identical** |
| Isolation, import graph | AST scan of executable modules | **117 scanned, 0 violations** |
| Isolation, raw text | text scan for dynamic access | **0 violations** |
| Empty hold | `seq-3` inspection | 1 interaction, `text=''`, `speaker=None` |
| Speakers present | transcript scan | `participant-1`, `participant-2`, `None` (hold only) |
| `preflight-real` | approved config, roster, artifact path | **PASS 17/17** at `2026-10-16T15:45:49` |

The isolation check was previously validated against a deliberately planted
violation, confirming it fails when it should rather than passing vacuously.

**`preflight-real` performs no inference.** It inspects configuration, registry
hashes, the artifact on disk and the runtime binary; it loads no weights and
generates no token. No Case 002 content was involved in it.

---

## 8.3 Residual public exposure — source-media fingerprints

An earlier revision of this branch carried the six source-media SHA-256
fingerprints in an intermediate commit. The branch was rewritten to a single
clean commit and force-pushed on 2026-10-15; the branch history and all public
files are now free of them.

**The rewrite does not undo the exposure.** Verified after the rewrite: the
orphaned commit is **still served by the host's API when addressed by its SHA**.
A force-push to a pull-request branch leaves the superseded commit referenced by
the PR timeline, so it is retained rather than collected.

Rewriting history also cannot reach clones, forks, caches, CI logs, proxies or
any reference already taken.

**The fingerprints must be treated as having been publicly exposed** between the
original push and the rewrite. They cannot be rotated — they are hashes of fixed
media — so the residual risk is permanent: anyone who captured them, and who
also holds a candidate recording, can confirm it is the source material.

Remediation still open:

1. Ask the host to purge the unreachable objects; a force-push alone does not.
2. Treat the values as compromised in any threat model that assumed they were
   private.
3. Keep them out of every future public artifact — §2.1 now cites reference ids
   only.

---

## 9. Open items and blockers

**Cleared:** private custody established in the organisation repository, access
verified across inherited and team paths, artifacts committed, committed-byte
hashes verified, and both authorised holders hold admin (§3).

| # | Item | State |
|---|---|---|
| 1 | **Independent evaluator** | **BLOCKER for evaluation.** Claude is disqualified (§8.1); a genuinely unexposed party is required |
| 2 | **Orphaned public object** | branch rewritten, but the superseded commit is still host-reachable by SHA; purge request outstanding (§8.3) |
| 3 | **Duplicate custody copy** | a user-account private repository holds byte-equivalent copies; recommended for deletion (§3.5) |
| 4 | **Source-media anchors** | supplied and **UNVERIFIED** — the media was never received (§2.1) |
| 5 | **Map and post-result formulations** | outside both repositories, pending owner decision |
| 6 | **Run 003 authorisation** | separate decision; not implied by anything here |

### Accepted decisions, not blockers

- One further organisation member holds inherited **read** access to the custody
  repository, accepted explicitly by the project owner (§3.2).
- The 10-sequence-to-39-interaction mapping is approved, with sequence 3
  remaining one empty hold (§5).

## 10. Not authorised and not done

- Run 003 has **not** been executed. No weights were loaded for Case 002, no
  token was generated, and no Case 002 content reached any model.
- Stage 1 and Stage 2 inference have **not** been run.
- Nothing was deployed.
- No implementation freeze is declared by this registry.
- Release of Case 002 for fixture authoring is **not** authorisation for any of
  the above.
