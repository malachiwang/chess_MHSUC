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

### Ticket 0.1A — Project Initialization + Lichess Source Format Audit

Audit scope:

```text
Governance consistency audit
Repo structure audit
Environment assumptions audit
Lichess source format assumptions audit
Data safety audit
```

Required report:

```text
Files inspected
Governance consistency findings
Repo structure findings
Environment / dependency findings
Lichess source format findings
Data safety findings
Recommended changes for 0.1B
Risks / assumptions
Whether 0.1B is safe to begin
```

Status: complete. See `reports/phase_reports/phase_0_1b_project_initialization_implementation.md`.

### Ticket 0.1B — Project Initialization + Lichess Source Documentation Implementation

Implementation scope:

```text
Rename reports/notes/ to reports/phase_reports/
Strengthen .gitignore (add *.sqlite, *.db, *.joblib, *.pkl, *.pt, *.pth, *.onnx)
Unify audit report format between CLAUDE.md and WORKFLOW.md
Add explicit report-location and no-standalone-report-tickets rules
Repurpose MANIFEST.md as a stable project manifest
Update ROADMAP.md Ticket 0.1 descriptions
Add Lichess parser-format assumptions to PIPELINE_OVERVIEW.md
```

Required report: `reports/phase_reports/phase_0_1b_project_initialization_implementation.md`

Status: complete.

### Ticket 0.2A — Environment Audit

Audit scope:

```text
Python executable and version
Virtual environment status
All required package availability in .venv vs. ambient shell
System tool availability: Stockfish, zstd CLI, brew
Repo dependency-file status (requirements.txt, pyproject.toml, Makefile, .python-version)
Recommendation for 0.2B
Risk assessment
```

Status: complete.

### Ticket 0.2B — Environment Documentation Implementation

Implementation scope:

```text
Create requirements.txt (curated direct dependencies, >= version pins)
Create .python-version (3.13.11)
Add Setup section to README.md (venv creation, activation, install, verification)
Update ROADMAP.md Ticket 0.2 descriptions
Update MANIFEST.md to include requirements.txt and .python-version
```

Required report: `reports/phase_reports/phase_0_2b_environment_documentation_implementation.md`

Status: complete.

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

Status: complete. See `reports/phase_reports/phase_1_1a_lichess_source_availability_audit.md`.

### Ticket 1.1B — Source Scanner Implementation

Implement a capped source scanner that can stream PGN data and summarize header/annotation availability.

Expected files:

```text
src/chess_mhsuc/source_scan.py
tests/conftest.py
tests/test_source_scan.py
reports/phase_reports/phase_1_1b_source_scanner_implementation.md
```

Out of scope:

```text
full model-ready dataset generation
large downloads without explicit permission
```

Status: complete. See `reports/phase_reports/phase_1_1b_source_scanner_implementation.md`.

Key findings from 50k-game scan of 2024-09 archive:

```text
600+0 rate:     9.85% of games
clock rate:     99.65% of 600+0 games have %clk
eval rate:      15.2% of basic_pass games have %eval  ← critical constraint
result dist:    1-0 48.9% / 0-1 46.6% / draw 4.5%
time forfeit:   11.3% of basic_pass terminations
elo range:      ~450–2680, mean ~1532
```

## Phase 2: PGN parsing and schema

Goal: extract reliable game-level and selected position-level records.

### Ticket 2.1A — PGN Schema Audit

Status: complete. Audit conducted via sampled real game inspection and
source-scan findings from Ticket 1.1B.

Key decisions recorded:
- Eval policy: Option C (nullable). eval_cp/eval_mate are None when absent.
  has_eval boolean on every ply row.
- Checkpoint definition: after Black's Nth full move = ply 2N (1-indexed).
  Checkpoints: move_10 (ply 20), move_20 (ply 40), move_30 (ply 60),
  move_40 (ply 80), last (final ply of game).
- Mate eval sign: White POV, requires side_to_move_next context.
  +N = White has mate in N. -N = Black has mate in N.
- Low-time flags deferred to feature engineering (Phase 3).
- Rejection priority: wrong_time_control → variant_or_nonstandard →
  missing_or_invalid_elo → missing_or_invalid_result → missing_clock.

### Ticket 2.1B — PGN Parser Implementation

Status: complete. See `reports/phase_reports/phase_2_1b_pgn_schema_parser_implementation.md`.

Implemented:

```text
src/chess_mhsuc/schemas.py       GameRecord, PlyRecord, PositionRecord + constants
src/chess_mhsuc/parse_pgn.py     full single-game parser
tests/fixtures/tiny_clock_eval_game.pgn  82-ply synthetic legal fixture
tests/test_parse_pgn.py          110 tests, all passing
```

Test results: 129 total (19 source_scan + 110 parse_pgn), all passed.
Python 3.13.11, pytest-9.0.3.

### Ticket 2.2A — Parser Validation Audit

Status: complete (chat audit only — no files produced).

Audit produced the streaming architecture and safety design used in 2.2B:
- urllib.request + zstandard streaming (no full decompression to disk)
- TC pre-filter before ply extraction (~90% of raw games skipped cheaply)
- Per-game exception handling with error_log
- Explicit Parquet schemas to prevent Null-type inference
- 11 post-run validation checks (username cols, game_id uniqueness, eval sentinel, etc.)
- max-games required (no unbounded default); max-accepted optional secondary cap

### Ticket 2.2B — Parser Validation + Capped Real-Data Loading Implementation

Status: complete. See `reports/phase_reports/phase_2_2b_parser_validation_implementation.md`.

Implemented:

```text
src/chess_mhsuc/run_parser.py     streaming CLI parser (zstd URL → Parquet + JSON)
tests/test_run_parser.py          34 tests, all passing
```

Test results: 163 total (19 source_scan + 110 parse_pgn + 34 run_parser), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data validation run executed (25k raw games, 2024-09 archive). All 11 validation
checks passed after one targeted fix: `n_plies_positive` scoped to accepted_basic rows
only (rejected abandoned games legitimately have n_plies=0). No parser logic changed.

No broad feature expansion included.

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
