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
| **Commit SHA** | *held in the private annex* — deliberately not in this public file |
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

### 3.2.2 Removing it — repository-specific removal is NOT possible

The project owner has asked for the third principal's read access to be removed
**on this repository only**, leaving their wider access unchanged.

**That cannot be done.** The access is not a repository grant, so there is
nothing on the repository to revoke. The platform's organisation base permission
applies to every organisation repository and **cannot be lowered for a single
repository** — repository-level grants can only raise a member's permission
above the base, never reduce it below.

Evidence: only one account appears under `affiliation=direct` on this
repository, and the same read level appears on another organisation repository,
consistent with an organisation-wide base permission rather than anything
specific to custody.

**Minimum change required**, and its blast radius:

| Option | Change | Affects |
|---|---|---|
| **1 — recommended** | Set the organisation base permission to **None**, then grant the two authorised holders explicitly on each repository that needs it | **Every** organisation repository. Members lose automatic access and need explicit grants |
| 2 | Remove the account from the organisation | That account's access to **all** organisation repositories — contradicts the instruction to leave wider access unchanged |
| 3 | Move custody to an owner outside the organisation | Custody only. Rejected earlier: the owner then lacks access unless invited |

**Option 2 is excluded** by the owner's own constraint. **Option 1 is the only
route** that removes this access while keeping the account in the organisation —
but it is organisation-wide by nature, which is exactly what the instruction
says not to change without an explicit decision.

**Decision required from the project owner:** authorise setting the
organisation base permission to **None** and re-granting explicitly, accepting
that every organisation repository is affected; or accept the read access on
custody and record a written authorisation for it.

**Not attempted.** Organisation-wide permissions were not altered, and the
authority to alter them is not held by the account used for this work.

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
recorded it per product and concluded that the product as a whole was
disqualified. That conflated distinct workspaces and is corrected here: the
authoring workspace is exposed, and the project owner's separate independent
review workspace is not.

| Workspace / party | Case-naive? | Evidence |
|---|---|---|
| Project owner | no | authorised holder; released the package |
| Implementation author | no | authorised; received the package for fixture authoring |
| **Author's development workspace** | **no — EXPOSED** | received the full package on 2026-10-14; see §8.1 |
| Overview / Product Agent workspace | no | declared exposed at seal in the sealed package |
| **Independent review workspace** | **yes — no exposure identified** | owner confirmed in writing, 2026-10-19; see §8.1.1 |
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

### 8.1.1 Independent review workspace — no exposure identified

A separate independent review workspace, held by the project owner, is **not**
exposed.

**Evidence:** the project owner has confirmed in writing (2026-10-19) that she
has identified no Case 002 exposure in her independent review workspace.

This is a distinct workspace from the authoring workspace in §8.1. The two share
a product name and nothing else: exposure of one says nothing about the other,
and treating them as a single party was the error in an earlier revision of this
record.

**No blanket disqualification applies.** It is **not** correct to state that all
workspaces of this product are disqualified. The position is per workspace:

| Workspace | Status |
|---|---|
| authoring (§8.1) | **exposed** — disqualified as independent evaluator |
| independent review | **no exposure identified** by its holder |

The owner's confirmation is the evidence of record. It rests on her own
inspection of her workspace, which is the only party able to make that
determination.

## 8.2 Verification — freshly re-run 2026-10-19

Every line below was executed on the authoring machine on 2026-10-19. These are
fresh results, not carried forward.

| Check | Result | Status |
|---|---|---|
| Fixture + isolation tests | 22 passed | fresh |
| Phase 1 suite | 399 passed | fresh |
| Root suite | 365 passed | fresh |
| Phase 1 `mypy --strict` | clean, 89 files | fresh |
| Root `mypy --strict` | clean, 69 files | fresh |
| Round trip | **74/74 turns identical** | fresh |
| Isolation, import graph | **117 modules, 0 violations** | fresh |
| Isolation, raw text | **0 violations** | fresh |
| Empty hold | sequence 3: one interaction, `text=''` | fresh |
| `preflight-real` | **PASS 17/17** at `2026-10-19T01:45:12` | fresh |

The three artifact hashes in §3.3 were **recomputed on 2026-10-19** and all
three match the authorised values. They were taken from the canonical files on
the authoring machine rather than from a clone of the custody repository,
because authenticated access to private repositories was unavailable at the time
(§9). Those files were previously verified byte-identical to the committed
objects, and the digests are unchanged, so no discrepancy exists — but the
source of this particular recomputation is stated rather than implied.

`preflight-real` performs **no inference**: it inspects configuration, registry
hashes, the artifact on disk and the runtime binary. It loads no weights,
generates no token, and touches no case content.

## 8.3 Residual public exposure — source-media fingerprints

An earlier revision of the public branch carried the six source-media SHA-256
fingerprints in an intermediate commit. The branch was rewritten to a single
clean commit and force-pushed; branch history and all public files are now free
of them.

**The rewrite does not undo the exposure.** Re-verified 2026-10-19: the
superseded commit is **still served by the host when addressed by its SHA**, and
**all six of the six distinct fingerprints remain present in its patch** — the
full set, not a subset. A force-push to a pull-request branch leaves the commit
referenced by the pull request's timeline. Rewriting also cannot reach clones,
forks, caches, CI logs, proxies or search indexes.

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

**Cleared:** fixture authored; canonical private custody established; the
redundant duplicate repository deleted, leaving a single custody surface; the
three artifact hashes recomputed and matching; the independent review workspace
confirmed unexposed by its holder.

| # | Item | State |
|---|---|---|
| 1 | **Authenticated GitHub access unavailable** | **BLOCKER.** The CLI is logged out and git holds no credentials for private repositories or pushes. Blocks permission inspection, support submission, packet delivery by link, and publishing this record (§9.1) |
| 2 | **Inherited read grant on custody** | repository-specific removal is **not possible**; the minimum change is organisation-wide and needs an explicit owner decision (§3.2.2) |
| 3 | **Host object purge** | **PENDING.** Request prepared, **not submitted** — submission needs the host's web support form. No support reference exists. May only be recorded as removed on written host confirmation (§8.3) |
| 4 | **Source-media anchors** | supplied and **UNVERIFIED** — the media was never received (§2.1) |
| 5 | **Map and post-result formulations** | outside the repository, pending owner decision |
| 6 | **Run 003 authorisation** | separate decision; not implied by anything here |

### 9.1 Authenticated access blocker

The GitHub CLI reports no logged-in host, and no token is present in the
environment. Public repositories can still be read anonymously, which is why
some read-only checks continue to work, but every authenticated operation fails.

Restoring it is an interactive browser authorisation that also changes stored
credentials, so it was **not** performed unilaterally. Until it is restored,
items 1-3 above cannot progress.

### Accepted decisions, not blockers

- The 10-sequence-to-39-interaction mapping is approved, with sequence 3
  remaining one empty hold (§5).
- The independent review workspace is recorded as unexposed on the owner's
  written confirmation (§8.1.1).

## 10. Not authorised and not done

- Run 003 has **not** been executed. No weights were loaded for Case 002, no
  token was generated, and no Case 002 content reached any model.
- Stage 1 and Stage 2 inference have **not** been run.
- Nothing was deployed.
- No implementation freeze is declared by this registry.
- Release of Case 002 for fixture authoring is **not** authorisation for any of
  the above.
