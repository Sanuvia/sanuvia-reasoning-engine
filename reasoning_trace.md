# Sanuvia — Persistent Reasoning Core: Reasoning Trace

Deterministic longitudinal trace generated directly from the session's own reasoning state (per-interaction results + persisted immutable state). Re-rendering the same state produces an identical document.

Subject: `subject-exit-test` · Interactions: 6

---

## Interaction 1

**Incoming evidence**
- `evidence-1` · class `behavioural` · reliability 0.700

**WorldModel before revision:** `— (genesis)` · ModelUncertainty —

**Active competing hypotheses (before)**
- (none yet)

**Support changes**
- `H_external_routine` · new @ 0.400
- `H_emotional_distance` · new @ 0.400

**AnomalyResolution**
- none

**RevisionEvents created**
- `rev-1` · **hypothesize** on `H_external_routine` · ∅ → `wm-1` · evidence evidence-1
- `rev-2` · **hypothesize** on `H_emotional_distance` · ∅ → `wm-1` · evidence evidence-1

**New WorldModel version:** `wm-1`

**Active predictions (this version)**
- none

**Inquiry generated**
- `inq-1` · status `proposed` · uncertainty 0.500
  > "Which explanation better fits the evidence: 'external routine change' or 'increasing emotional distance'?"

**ModelUncertainty:** — → 0.500

## Interaction 2

**Incoming evidence**
- `evidence-2` · class `behavioural` · reliability 0.800

**WorldModel before revision:** `wm-1` · ModelUncertainty 0.500

**Active competing hypotheses (before)**
- `H_external_routine` · support 0.400
- `H_emotional_distance` · support 0.400

**Support changes**
- `H_external_routine` · 0.400 (unchanged)
- `H_emotional_distance` · 0.400 → 0.640 (Δ +0.240)

**AnomalyResolution**
- none

**RevisionEvents created**
- `rev-3` · **strengthen** on `H_emotional_distance` · wm-1 → `wm-2` · evidence evidence-2

**New WorldModel version:** `wm-2`

**Active predictions (this version)**
- `pred-1` · likelihood 0.640 · `observed_trajectory` · from H_emotional_distance

**Inquiry generated**
- none

**ModelUncertainty:** 0.500 → 0.380

## Interaction 3

**Incoming evidence**
- `evidence-3` · class `behavioural` · reliability 0.800

**WorldModel before revision:** `wm-2` · ModelUncertainty 0.380

**Active competing hypotheses (before)**
- `H_emotional_distance` · support 0.640
- `H_external_routine` · support 0.400

**Support changes**
- `H_external_routine` · 0.400 (unchanged)
- `H_emotional_distance` · 0.640 → 0.784 (Δ +0.144)

**AnomalyResolution**
- none

**RevisionEvents created**
- `rev-4` · **strengthen** on `H_emotional_distance` · wm-2 → `wm-3` · evidence evidence-3

**New WorldModel version:** `wm-3`

**Active predictions (this version)**
- `pred-2` · likelihood 0.784 · `observed_trajectory` · from H_emotional_distance

**Inquiry generated**
- none

**ModelUncertainty:** 0.380 → 0.308

## Interaction 4

**Incoming evidence**
- `evidence-4` · class `contradictory` · reliability 0.800

**WorldModel before revision:** `wm-3` · ModelUncertainty 0.308

**Active competing hypotheses (before)**
- `H_emotional_distance` · support 0.784
- `H_external_routine` · support 0.400

**Support changes**
- `H_external_routine` · 0.400 → 0.640 (Δ +0.240)
- `H_emotional_distance` · 0.784 → 0.470 (Δ -0.314)

**AnomalyResolution**
- `anom-1` · disposition **revise** · triggered by evidence-4

**RevisionEvents created**
- `rev-5` · **strengthen** on `H_external_routine` · wm-3 → `wm-4` · evidence evidence-4
- `rev-6` · **contradict** on `H_emotional_distance` · wm-3 → `wm-4` · evidence evidence-4

**New WorldModel version:** `wm-4`

**Active predictions (this version)**
- `pred-3` · likelihood 0.640 · `observed_trajectory` · from H_external_routine

**Inquiry generated**
- `inq-2` · status `proposed` · uncertainty 0.415
  > "Which explanation better fits the evidence: 'external routine change' or 'increasing emotional distance'?"

**ModelUncertainty:** 0.308 → 0.415

## Interaction 5

**Incoming evidence**
- `evidence-5` · class `failed_acquisition` · reliability 0.300

**WorldModel before revision:** `wm-4` · ModelUncertainty 0.415

**Active competing hypotheses (before)**
- `H_external_routine` · support 0.640
- `H_emotional_distance` · support 0.470

**Support changes**
- `H_external_routine` · 0.640 (unchanged)
- `H_emotional_distance` · 0.470 (unchanged)
- `H_avoiding_topic` · new @ 0.300
- `H_external_stressor` · new @ 0.300

**AnomalyResolution**
- none

**RevisionEvents created**
- `rev-7` · **hypothesize** on `H_avoiding_topic` · wm-4 → `wm-5` · evidence evidence-5
- `rev-8` · **hypothesize** on `H_external_stressor` · wm-4 → `wm-5` · evidence evidence-5

**New WorldModel version:** `wm-5`

**Active predictions (this version)**
- `pred-4` · likelihood 0.640 · `observed_trajectory` · from H_external_routine

**Inquiry generated**
- `inq-3` · status `proposed` · uncertainty 0.415
  > "Which explanation better fits the evidence: 'external routine change' or 'increasing emotional distance'?"

**ModelUncertainty:** 0.415 → 0.415

## Interaction 6

**Incoming evidence**
- `evidence-6` · class `contradictory` · reliability 0.300

**WorldModel before revision:** `wm-5` · ModelUncertainty 0.415

**Active competing hypotheses (before)**
- `H_external_routine` · support 0.640
- `H_emotional_distance` · support 0.470
- `H_avoiding_topic` · support 0.300
- `H_external_stressor` · support 0.300

**Support changes**
- `H_external_routine` · 0.640 (unchanged)
- `H_emotional_distance` · 0.470 (unchanged)
- `H_avoiding_topic` · 0.300 (unchanged)
- `H_external_stressor` · 0.300 (unchanged)

**AnomalyResolution**
- `anom-2` · disposition **escalate** · triggered by evidence-6

**RevisionEvents created**
- none (model holds)

**New WorldModel version:** none — model holds at `wm-5`

**Active predictions (this version)**
- (model holds; predictions unchanged)

**Inquiry generated**
- none

**ModelUncertainty:** 0.415 → 0.415

---

# End-of-run summaries

## RevisionLedger (authoritative history)

| seq | outcome | affected | from → to | triggering evidence |
| --- | --- | --- | --- | --- |
| 0 | hypothesize | `H_external_routine` | ∅ → `wm-1` | evidence-1 |
| 1 | hypothesize | `H_emotional_distance` | ∅ → `wm-1` | evidence-1 |
| 2 | strengthen | `H_emotional_distance` | wm-1 → `wm-2` | evidence-2 |
| 3 | strengthen | `H_emotional_distance` | wm-2 → `wm-3` | evidence-3 |
| 4 | strengthen | `H_external_routine` | wm-3 → `wm-4` | evidence-4 |
| 5 | contradict | `H_emotional_distance` | wm-3 → `wm-4` | evidence-4 |
| 6 | hypothesize | `H_avoiding_topic` | wm-4 → `wm-5` | evidence-5 |
| 7 | hypothesize | `H_external_stressor` | wm-4 → `wm-5` | evidence-5 |

## Hypothesis lineage (support over time)

- `H_external_routine` — "external routine change"
  - support: 0.400 → 0.640  (2 evaluation(s) retained)
- `H_emotional_distance` — "increasing emotional distance"
  - support: 0.400 → 0.640 → 0.784 → 0.470  (4 evaluation(s) retained)
- `H_avoiding_topic` — "avoiding a difficult topic"
  - support: 0.300  (1 evaluation(s) retained)
- `H_external_stressor` — "an external stressor"
  - support: 0.300  (1 evaluation(s) retained)

## Prediction history

| prediction | model version | likelihood | trajectory | from |
| --- | --- | --- | --- | --- |
| `pred-1` | `wm-2` | 0.640 | observed_trajectory | H_emotional_distance |
| `pred-2` | `wm-3` | 0.784 | observed_trajectory | H_emotional_distance |
| `pred-3` | `wm-4` | 0.640 | observed_trajectory | H_external_routine |
| `pred-4` | `wm-5` | 0.640 | observed_trajectory | H_external_routine |

## ModelUncertainty timeline

| interaction | before | after | committed |
| --- | --- | --- | --- |
| 1 | — | 0.500 | yes |
| 2 | 0.500 | 0.380 | yes |
| 3 | 0.380 | 0.308 | yes |
| 4 | 0.308 | 0.415 | yes |
| 5 | 0.415 | 0.415 | yes |
| 6 | 0.415 | 0.415 | no (holds) |

