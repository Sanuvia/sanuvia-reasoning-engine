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

### 3.2 Effective access — verified

Checked across every path, including inherited organisation and team access:

| Principal | Permission | Source |
|---|---|---|
| authorised holder A | admin | **direct** collaborator on this repository |
| authorised holder B | admin | organisation ownership |
| one further organisation member | read | **not direct** — organisation-level |

| Path | Result |
|---|---|
| Direct grants on this repository | **one** — authorised holder A only |
| Team grants | **none** |
| Outside collaborators | **none** |
| Forks | **0** |

Both authorised holders hold admin.

### 3.2.1 The third principal — correction to an earlier entry

An earlier revision of this record described the third principal's read access
as *"accepted explicitly by the project owner."* **That overstated the
evidence and is withdrawn.**

What the record actually supports:

| Question | Answer |
|---|---|
| Which account? | identified; held privately and deliberately not named in this public file |
| Direct grant on the custody repository? | **no** — only authorised holder A is a direct collaborator |
| Source of access | organisation-level, not a repository grant made during custody setup |
| Written authorisation from the project owner? | **none located** |
| What exists instead | an informal remark from the implementation author that the account is an organisation member |

That remark came from the implementation author, not the project owner, and it
asserts **membership**, not authorisation for Case 002 access. Membership is not
consent, and inheritance is not consent. Neither is treated as authorisation
here.

**Status: UNAUTHORISED-BUT-PRESENT.** The access exists and is not supported by
a located authorisation.

### 3.2.2 Removing it

Not possible with the permissions held. The grant is organisation-level, so it
cannot be revoked on the repository; the organisation's
`default_repository_permission` could not even be read with the current token,
which returns `null` for a non-owner. The same read level appears on another
organisation repository, consistent with an organisation-wide base permission
rather than anything specific to custody.

**Requires an organisation owner** to either change the organisation-wide
default repository permission — which would affect every organisation
repository — or remove the account's organisation membership. Neither was
attempted: the authority required is not held, and organisation-wide permissions
were not altered.

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

### 3.5 Duplicate custody copy — DELETED 2026-10-16

A redundant user-account private repository held byte-equivalent copies of the
same three artifacts. It was deleted by the implementation author through the
host's web interface, after the CLI route was refused for want of the
`delete_repo` token scope.

**Pre-deletion verification** (fresh clones of both): canonical private at the
authorised HEAD; all three protected artifacts byte-equivalent; no files,
branches, tags, forks or issues unique to the duplicate. The only difference was
README boilerplate.

**Post-deletion verification:**

| Check | Result |
|---|---|
| Duplicate repository | **gone** — host returns `404 Not Found` |
| Private repositories remaining on that account | **none** |
| Canonical repository | intact, private, 0 forks, not archived |
| Canonical HEAD | unchanged at the authorised SHA |
| Canonical tracked files | unchanged — three artifacts, `.gitignore`, README |
| Committed-byte hashes, recomputed from a fresh clone | **all three unchanged** |

**Custody surface is now single.** One private repository holds Case 002, and
its committed bytes are unchanged by the deletion.

Backups retained: local branch `backup/prereg-pre-rewrite-20261015` and a
bundle. These cover the public pre-registration branch, not the custody
artifacts; custody is held by the canonical repository and the authoring
machine's working tree.

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

## 8. Exposure register — per workspace

Exposure is recorded **per workspace**, not per product. An earlier revision
recorded it per product and concluded that "Claude" was disqualified. That
conflated distinct workspaces and is corrected here.

| Workspace / party | Case-naive? | Evidence |
|---|---|---|
| Project owner | no | authorised holder; released the package |
| Implementation author | no | authorised; received the package for fixture authoring |
| **Author's development workspace** | **no — EXPOSED** | received the full package on 2026-10-14; see §8.1 |
| Overview / Product Agent workspace | no | declared exposed at seal in the sealed package |
| **Independent review workspace** | **unknown — no evidence of exposure** | see §8.1.1 |
| Any model / inference API | yes | no Case 002 content was sent to a model |

### 8.1 Author's development workspace — exposed

On 2026-10-14 this workspace received, in full: the executable transcript, the
reference and provenance document **including the anonymisation map and the
post-result reference formulations**, the seal manifest, and the Stage 2
interaction protocol. That is the complete prohibited set.

The sealed package records this party's exposure as `none` and names it as a
candidate independent evaluator *"if the source remains withheld."* The source
did not remain withheld, so **this workspace cannot act as the independent
case-naive evaluator**, and no independent-evaluation claim may rest on work
produced in it.

### 8.1.1 Independent review workspace — status unknown, not assumed

A separate review workspace is **not** recorded as exposed here.

No evidence was found either way. Exposure of the authoring workspace says
nothing about a separate workspace, and treating them as one party was the error
in the earlier revision. A workspace is disqualified only on evidence that the
protected material actually reached it — not by sharing a product name with an
exposed one.

**To close this**, the holder of that workspace should confirm whether any of
the transcript, source material, anonymisation map, reference formulations, seal
manifest or Stage 2 protocol ever reached it. Until that confirmation exists,
its status is **unknown**, and an independent-evaluation claim should not rest
on it either — unknown is not the same as clear.

## 8.2 Verification actually run — 2026-10-16 (re-verified 16:16)

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
| `preflight-real` | approved config, roster, artifact path | **PASS 17/17** at `2026-10-16T16:16:31` |

The isolation check was previously validated against a deliberately planted
violation, confirming it fails when it should rather than passing vacuously.

**`preflight-real` performs no inference.** It inspects configuration, registry
hashes, the artifact on disk and the runtime binary; it loads no weights and
generates no token. No Case 002 content was involved in it.

---

## 8.3 Residual public exposure — source-media fingerprints

An earlier revision of the public branch carried the six source-media SHA-256
fingerprints in an intermediate commit. The branch was rewritten to a single
clean commit and force-pushed; branch history and all public files are now free
of them.

**The rewrite does not undo the exposure.** Verified after the rewrite: the
superseded commit is **still served by the host when addressed by its SHA**,
because a force-push to a pull-request branch leaves it referenced by the pull
request's timeline. Rewriting also cannot reach clones, forks, caches, CI logs,
proxies or search indexes.

The values **cannot be rotated** — they are digests of fixed media — so the
residual risk is permanent. They must be treated as **having been publicly
exposed** for the window between the original push and the rewrite.

**A host purge request is drafted and not yet submitted.** It is held with the
project owner and is deliberately **not** committed to this public repository:
it has to name the commit to be purged, and publishing that here would signpost
exactly where the values sit.

**Recording rule:** this item stays **OUTSTANDING** until the host confirms
removal in writing, with the confirmation reference recorded alongside it. An
unconfirmed purge must never be recorded as complete. A successful purge would
end ongoing availability from the host; it would not undo the exposure.

## 9. Open items and blockers

**Cleared:** fixture authored; canonical private custody verified; the three
committed-byte hashes recomputed from the committed objects in a fresh clone;
and the redundant duplicate repository **deleted**, leaving a single custody
surface (§3.5).

| # | Item | State |
|---|---|---|
| 1 | **Inherited read grant on custody** | **UNAUTHORISED-BUT-PRESENT.** No written authorisation located; removal needs an organisation owner (§3.2.1, §3.2.2) |
| 2 | **Host object purge** | **OUTSTANDING.** Request prepared, **not submitted** — needs the host's web support form. May only be marked resolved on written host confirmation (§8.3) |
| 3 | **Independent evaluator** | author's workspace **disqualified**; review workspace status **unknown**, needs confirmation from its holder (§8.1, §8.1.1) |
| 4 | **Source-media anchors** | supplied and **UNVERIFIED** — the media was never received (§2.1) |
| 5 | **Map and post-result formulations** | outside the repository, pending owner decision |
| 6 | **Run 003 authorisation** | separate decision; not implied by anything here |

### Accepted decisions, not blockers

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
