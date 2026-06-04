# Roadmap

This roadmap is phase-based, with audit/implementation pairs wherever practical.

Each audit/implementation pair should produce a report. The roadmap is expected to evolve as the project learns from real data.

## Current project direction

```text
Project: Modeling Human Strategy Under Constraints
Initial source: Lichess standard rated PGN database
Initial scope: 10+0 only, TimeControl "600+0"
Initial target: 3-class White win / Draw / Black win
Initial model path: baselines -> logistic regression -> GBM -> calibrated GBM
Final aspiration: every-ply human outcome prediction under constraints
```

## Phase 0: Governance and setup

Goal: establish project rules, structure, and safety before data work.

### Ticket 0.1A — Governance Audit

Audit the needed governance docs, project scope, data policy, Claude behavior rules, and workflow conventions.

Required report:

```text
Scope choices
Open ambiguities
Recommended governance doc set
Data safety requirements
Workflow requirements
```

### Ticket 0.1B — Governance Implementation

Create/update:

```text
README.md
PROJECT_CHARTER.md
ROADMAP.md
WORKFLOW.md
DATA_POLICY.md
CLAUDE.md
PIPELINE_OVERVIEW.md
EXPERIMENT_LOG.md
MODEL_CARD.md
```

Required report:

```text
Files created/modified
Key policies encoded
Remaining setup tasks
```

### Ticket 0.2A — Environment Audit

Verify local Python environment and required tools.

Check:

```text
Python version
virtual environment
installed packages
Stockfish availability
zstd availability
repo structure
.gitignore behavior
```

### Ticket 0.2B — Environment Implementation

Add minimal environment setup support if needed.

Possible files:

```text
requirements.txt
pyproject.toml
Makefile
```

Only add what is useful.

## Phase 1: Lichess source and 10+0 availability

Goal: understand source data before building a full parser.

### Ticket 1.1A — Lichess Source Availability Audit

Questions:

```text
Which monthly source file should be used first?
How large is it?
Can it be streamed without full decompression?
How often does TimeControl "600+0" appear in a capped scan?
How often do qualifying games have clocks?
How often do qualifying games have eval annotations?
What fields appear consistently?
```

Initial scan cap:

```text
10,000-25,000 games
```

Required report:

```text
source file inspected
scan cap
10+0 count/estimate
eval availability estimate
clock availability estimate
field observations
recommendation for parser scope
```

### Ticket 1.1B — Source Scanner Implementation

Implement a capped source scanner that can stream PGN data and summarize header/annotation availability.

Expected files:

```text
src/chess_mhsuc/source_scan.py
tests/test_source_scan.py if practical
reports/phase_reports/phase_1_1b_source_scanner_implementation.md
```

Out of scope:

```text
full model-ready dataset generation
large downloads without explicit permission
```

## Phase 2: PGN parsing and schema

Goal: extract reliable game-level and selected position-level records.

### Ticket 2.1A — PGN Schema Audit

Inspect real sampled games and define schemas for:

```text
game metadata
position/checkpoint rows
skip reasons
```

Required report:

```text
header fields
comment fields
clock format
eval format
termination values
schema recommendation
risks
```

### Ticket 2.1B — PGN Parser Implementation

Implement parser functions for:

```text
headers
result labels
time control
ratings
termination
clock annotations
eval annotations
selected checkpoints
```

Expected files:

```text
src/chess_mhsuc/parse_pgn.py
src/chess_mhsuc/schemas.py
tests/test_parse_pgn.py
tests/fixtures/tiny_clock_eval_game.pgn
```

### Ticket 2.2A — Parser Validation Audit

Run parser on a capped real sample and summarize:

```text
parsed games
skipped games
skip reasons
missing fields
checkpoint extraction success
```

### Ticket 2.2B — Parser Hardening Implementation

Fix parser issues identified in validation.

No broad feature expansion unless explicitly included.

## Phase 3: Cleaning, labeling, and features

Goal: produce a clean model-ready checkpoint dataset.

### Ticket 3.1A — Cleaning and Labeling Audit

Define filters and label behavior.

Must answer:

```text
What qualifies as valid 10+0?
What labels are emitted?
How are draws handled?
How are missing clocks handled?
How are missing evals handled?
How are terminations tracked?
Are usernames dropped?
```

### Ticket 3.1B — Cleaning and Labeling Implementation

Implement cleaning and label extraction.

Expected files:

```text
src/chess_mhsuc/cleaning.py
src/chess_mhsuc/labels.py
tests/test_cleaning.py
tests/test_labels.py
```

### Ticket 3.2A — Feature Engineering Audit

Define first feature set:

```text
rating features
clock features
phase features
eval features
termination features
```

### Ticket 3.2B — Feature Engineering Implementation

Implement feature generation.

Expected files:

```text
src/chess_mhsuc/features.py
tests/test_features.py
```

## Phase 4: Data assessment

Goal: verify dataset quality before modeling.

### Ticket 4.1A — Dataset Assessment Audit

Define required dataset quality checks.

Must include:

```text
row counts
game counts
missing values
rating distribution
result distribution
termination distribution
clock distribution
eval distribution
checkpoint distribution
```

### Ticket 4.1B — Dataset Assessment Implementation

Implement a reproducible dataset assessment script/notebook.

Expected files:

```text
src/chess_mhsuc/assess_dataset.py
notebooks/01_dataset_assessment.ipynb optional
reports/phase_reports/phase_4_1b_dataset_assessment.md
```

## Phase 5: Baseline modeling

Goal: establish honest baseline performance before GBM.

### Ticket 5.1A — Modeling Split and Baseline Audit

Define:

```text
train/validation/test split by game_id
label format
baseline models
metrics
calibration expectations
```

Mandatory warning:

```text
No row-level split across positions from the same game.
```

### Ticket 5.1B — Baseline Modeling Implementation

Implement baselines:

```text
majority/prior baseline
rating-only
 eval-only
 eval + rating
 eval + rating + clocks
 eval + rating + clocks + phase
```

Expected files:

```text
src/chess_mhsuc/modeling.py
src/chess_mhsuc/evaluate.py
reports/phase_reports/phase_5_1b_baseline_modeling.md
```

## Phase 6: GBM modeling

Goal: train the first serious nonlinear tabular model.

### Ticket 6.1A — GBM Selection Audit

Compare:

```text
sklearn HistGradientBoostingClassifier
XGBoost
LightGBM
```

Recommendation expected:

```text
Which model to use first and why.
```

Current default:

```text
Start with scikit-learn HistGradientBoostingClassifier for lowest dependency friction.
Move to XGBoost if performance/control needs justify it.
```

### Ticket 6.1B — GBM Implementation

Train first GBM model on the verified dataset.

Required:

```text
same split as baselines
same metrics
ablation comparison
feature importance or permutation importance if feasible
```

### Ticket 6.2A — Calibration Audit

Define calibration method and reporting.

Consider:

```text
calibration curve
Brier score
CalibratedClassifierCV
holdout calibration
```

### Ticket 6.2B — Calibration Implementation

Add calibration assessment and optional calibrated model.

## Phase 7: Subgroup analysis

Goal: test the actual research hypothesis across constraints.

### Ticket 7.1A — Rating/Phase/Clock Subgroup Audit

Define subgroup bins:

```text
rating buckets
phase buckets
clock pressure buckets
eval buckets
termination categories
```

### Ticket 7.1B — Subgroup Analysis Implementation

Produce subgroup reports and figures.

Questions:

```text
Does clock pressure improve prediction most in late game?
Does rating matter differently by phase?
Do lower-rated players degrade more under low time?
Does eval conversion differ by rating bucket?
```

## Phase 8: Fixed-depth Stockfish validation

Goal: check whether conclusions depend on existing Lichess eval selection bias.

### Ticket 8.1A — Stockfish Validation Audit

Define:

```text
sample size
positions per game
depth/node limit
runtime estimate
output schema
risk controls
```

### Ticket 8.1B — Stockfish Evaluation Implementation

Evaluate sampled selected positions locally.

Do not run massive evaluation without explicit permission.

### Ticket 8.2A — Existing-vs-Fixed Eval Comparison Audit

Define comparison approach.

### Ticket 8.2B — Existing-vs-Fixed Eval Comparison Implementation

Report whether model conclusions hold under fixed-depth evals.

## Phase 9: Scale-up

Goal: scale only after the pilot pipeline is reliable.

### Ticket 9.1A — Scale-Up Audit

Answer:

```text
What bottlenecks exist?
Do we need more data?
Do we need an external drive?
Do we need cloud compute?
What exact research question requires scale?
```

### Ticket 9.1B — Scale-Up Implementation

Scale to larger samples only with explicit caps and verification.

## Phase 10: Neural sequence model exploration

Goal: explore sequence modeling only if justified.

### Ticket 10.1A — Sequence Model Feasibility Audit

Questions:

```text
Does GBM leave meaningful unexplained temporal structure?
Can local compute handle a small sequence model?
What data representation is needed?
What baseline must the sequence model beat?
```

### Ticket 10.1B — Minimal Sequence Model Implementation

Implement a small sequence baseline only after the audit.

Out of scope:

```text
large transformer training
cloud GPU spending
paper claims without comparison to GBM
```

## Phase 11: Outreach package

Goal: prepare for professor feedback if pilot results are credible.

### Ticket 11.1A — Outreach Readiness Audit

Check whether the project has:

```text
clean pilot dataset
clear pipeline docs
ablation table
calibration figure
subgroup result
known limitations
concise summary
```

### Ticket 11.1B — Outreach Package Implementation

Create:

```text
1-page research summary
figures
methods note
professor email draft
```

## Completed tickets

```text
None yet beyond initial repository setup.
```

Update this section after each stable commit.
