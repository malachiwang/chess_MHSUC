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

Status: complete (chat audit only — no files produced).

Audit inspected the 2024-09 25k interim dataset (2,467 game records, 8,528
position rows). Key decisions recorded:

- Game-level filters: `accepted_basic == True AND termination != "Abandoned"`
- Time forfeit games (11.5%) RETAINED — central to research question
- Missing eval RETAINED — eval_cp nullable by design
- No new label columns in v1 — result_class already present from parser
- No feature engineering in cleaning step
- Clock anomalies (7 rows with clock_s > 600) retained for now
- "Last" checkpoint duplication (83 games) retained — caller's responsibility

### Ticket 3.1B — Cleaning and Labeling Implementation

Status: complete. See `reports/phase_reports/phase_3_1b_cleaning_rules_implementation.md`.

Implemented:

```text
src/chess_mhsuc/cleaning.py     pure cleaning functions + CLI
tests/test_cleaning.py          30 tests, all passing
```

Test results: 193 total (19 source_scan + 110 parse_pgn + 34 run_parser + 30 cleaning), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run executed on 2024-09 25k interim dataset. All 8 validation checks passed.

```text
Raw game rows:        2,467
Clean game rows:      2,460   (5 rejected + 2 accepted-abandoned excluded)
Retained time forfeit:  283   (11.5%)
Broad position rows:  8,528
Eval position rows:   1,168   (13.7% eval coverage)
```

### Ticket 3.2A — Feature Engineering Audit

Status: complete (chat audit only — no files produced).

Audit defined v1 feature policy:
- Leakage: result_class, termination, n_plies_total, white/black_rating_diff forbidden as model inputs
- Rating features: white_elo, black_elo, elo_diff, avg_elo
- Clock features: raw + capped (÷600 fracs) + low-time flags (60/30/10s) + clock_anomaly
- Eval features: eval_cp_clipped (±1000 clip), is_mate_eval, eval_mate_abs, eval_white_winning
- Position features: move_number, phase, selected_position_type, checkpoint_index, phase_index
- Caution columns: is_last_checkpoint, side_to_move_next, white_to_move_next, duplicate_ply_checkpoint
- Slice columns: is_time_forfeit, termination, has_eval, game_id
- Labels: result_class, white_result_numeric

### Ticket 3.2B — Feature Engineering Implementation

Status: complete. See `reports/phase_reports/phase_3_2b_feature_engineering_implementation.md`.

Implemented:

```text
src/chess_mhsuc/features.py     pure feature functions + CLI (40-column output)
tests/test_features.py          84 tests, all passing
```

Test results: 277 total (19 source_scan + 110 parse_pgn + 34 run_parser + 30 cleaning + 84 features), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run on 2024-09 25k cleaned dataset. All 19 validation checks passed.

```text
Broad input rows:   8,528  →  broad output rows: 8,528  (no rows dropped)
Eval input rows:    1,168  →  eval output rows:  1,168  (no rows dropped)
Columns:            19 input → 40 output (23 added, 2 dropped: ply, n_plies_total)
Clock anomalies:        7 rows flagged by clock_anomaly=True
Duplicate ply:        166 rows flagged by duplicate_ply_checkpoint=True (83 games × 2 rows)
Eval coverage:       13.7% of broad positions
```

## Phase 4: Data assessment

Goal: verify dataset quality before modeling.

### Ticket 4.1A — Dataset Assessment Audit

Status: complete (chat audit only — no files produced).

Audit inspected the 2024-09 25k feature tables (8,528 broad rows, 1,168 eval rows).
Key findings recorded: target distribution confirmed (WW 46.7%, BW 47.4%, DRAW 5.8%),
eval coverage 13.7%, low-time flags show strong result asymmetry, leakage safety confirmed,
eval subset has mild avg_elo selection bias (+20 Elo vs broad).

### Ticket 4.1B — Dataset Assessment Implementation

Status: complete. See `reports/phase_reports/phase_4_1b_feature_dataset_assessment.md`.

Implemented:

```text
src/chess_mhsuc/assess_dataset.py     13 pure functions + CLI (assessment + Markdown + JSON)
tests/test_assess_dataset.py          45 tests, all passing
```

Test results: 322 total (277 prior + 45 assess_dataset), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run on 2024-09 25k feature tables. All 8 baseline readiness checks passed.

```text
Broad rows:      8,528  |  Unique games: 2,323
Eval rows:       1,168  |  Unique games:   365
Result dist:     WHITE_WIN 46.73%  /  BLACK_WIN 47.44%  /  DRAW 5.83%
Eval coverage:  13.7%
avg_elo bias:   +20 Elo in eval vs broad
Leakage:        SAFE (both tables)
```

### Ticket 4.2A — Dataset Version Metadata Audit

Status: complete (chat audit only — no files produced).

Audit inspected all four per-stage metadata JSON files (parser, cleaning, features, assessment).
Key decisions recorded: canonical dataset_id = `lichess_ten_zero_2024_09_25k_v1`;
parser version_tag drift documented (metadata records "v1", canonical is "2024_09_25k_v1");
assessment test_count placeholder documented; manifest schema defined (17 functions A–Q).

### Ticket 4.2B — Dataset Version Metadata Implementation

Status: complete. See `reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md`.

Implemented:

```text
src/chess_mhsuc/dataset_version.py     17 pure functions + CLI (JSON manifest + dataset card + report)
tests/test_dataset_version.py          87 tests, all passing
```

Test results: 409 total (322 prior + 87 dataset_version), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data CLI run on 2024-09 25k pipeline artifacts. All 11 artifacts found.

```text
dataset_id:     lichess_ten_zero_2024_09_25k_v1
broad_rows:     8,528  |  eval_rows: 1,168
artifacts:      11/11 found, all SHA256-hashed
leakage_safe:   True  |  baseline_readiness: True
git commit:     70b5f7367d19 (pipeline code state)
```

Output artifacts (committed):
- `reports/phase_reports/dataset_card_lichess_ten_zero_2024_09_25k_v1.md`
- `reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md`

Output artifacts (local-only, gitignored):
- `data/processed/dataset_version_lichess_ten_zero_2024_09_25k_v1.json`

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

Status: **complete** (chat audit, 2026-06-07).

Split policy defined: 70/15/15, game_id-level, stratified on result_class, seed 42.
Primary training view: primary_numbered (exclude selected_position_type == "last").
Feature sets FS-A through FS-G defined. Baselines B0–B5 planned (DummyClassifier ×2,
LogisticRegression ×4). Primary metrics: log_loss + macro_F1 + per-class P/R/F1.
Eval table inherits broad split assignments via game_id join; no separate eval split.

### Ticket 5.1B — Modeling Split + Baseline Plan Implementation

Create `splits.py` with game_id-level split assignments and modeling plan JSON.

```text
split unit: game_id (never row-level)
ratio: 70/15/15, seed 42, stratified by result_class
broad split: train=1,626 / val=348 / test=349 games (2,323 total)
eval split: train=256 / val=56 / test=53 games (365 total, inherits broad)
primary view rows: train=4,344 / val=931 / test=930 (numbered checkpoints only)
DRAW broad: train=77 / val=16 / test=17 games
baselines planned: B0 (DummyClassifier most_frequent), B1 (prior),
  B2 (LR rating-only), B3 (LR rating+clock+position),
  B4 (LR eval-only, exploratory), B5 (LR full, exploratory)
label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed)
```

Status: **complete** (2026-06-07). 92 new tests. 501 total passing.

Files created:
- `src/chess_mhsuc/splits.py` — 16 functions + CLI
- `tests/test_splits.py` — 92 tests
- `reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md`

Local-only (gitignored):
- `data/processed/splits_2024_09_25k_v1.json`
- `data/processed/modeling_plan_2024_09_25k_v1.json`

### Ticket 5.2A — Baseline Model Audit

Define exact preprocessing, label encoding, class imbalance policy, metrics,
and baseline training plan before implementation.

Status: **complete** (2026-06-07). Chat-only audit.

Key decisions: strip `multi_class` from LR params (sklearn 1.8 breaking change);
`SimpleImputer(fill_value=0)` for `eval_mate_abs` (93.6% null); B3-balanced added
as diagnostic; `zero_division=0` for per-class metrics.

### Ticket 5.2B — Baseline Model Implementation

Train B0–B5 + B3-balanced baselines on primary_numbered view. No GBM, no calibration.

```text
B0: DummyClassifier most_frequent | broad | val acc=0.4758 | val log_loss=18.89
B1: DummyClassifier prior         | broad | val acc=0.4758 | val log_loss=0.8853
B2: LR rating-only (FS-B)         | broad | val acc=0.5124 | val log_loss=0.8740
B3: LR rating+clock (FS-E)        | broad | val acc=0.5381 | val log_loss=0.8527
B3-balanced: LR FS-E balanced     | broad | val acc=0.4393 | val log_loss=1.0623
B4: LR eval-only (FS-F)           | eval  | val acc=0.5918 | val log_loss=0.7833 (exploratory)
B5: LR full (FS-G)                | eval  | val acc=0.6190 | val log_loss=0.8598 (exploratory)
```

Status: **complete** (2026-06-07). 90 new tests. 591 total passing.

Files created:
- `src/chess_mhsuc/baselines.py` — 17 functions (A–Q) + CLI
- `tests/test_baselines.py` — 90 tests
- `reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md`

Local-only (gitignored):
- `data/processed/baseline_results_2024_09_25k_v1.json`
- `data/processed/baseline_predictions_2024_09_25k_v1.parquet`

### Ticket 5.3A — Baseline Evaluation Audit

Audit the baseline results JSON and reporting structure before writing the
evaluation report. No files created.

Status: **complete** (2026-06-08). Audit-only. No files changed.

Findings:
- `payload["baselines"]` is a dict keyed by baseline_id (not a list).
- B0 (most_frequent DummyClassifier) excluded from primary comparison table.
- Signal decomposition: B1 prior (0.8853) → B2 (0.8740, Δ−0.011) → B3 (0.8527, Δ−0.021).
- All broad unweighted LR models predict 0 DRAW rows.
- Eval test acc spike (B4=0.7071) is small-sample artifact.
- `feature_columns_dropped` key NOT present in baseline results (GBM-only hotfix).

### Ticket 5.3B — Baseline Evaluation Report Implementation

Create `baseline_evaluation.py` (17 functions A–Q) and associated tests +
Markdown report. Render evaluation report from the baseline results JSON.

Status: **complete** (2026-06-08). 106 new tests. 826 total passing.

Files created:
- `src/chess_mhsuc/baseline_evaluation.py` — 17 functions (A–Q) + CLI
- `tests/test_baseline_evaluation.py` — 106 tests
- `reports/baseline_evaluation_2024_09_25k_v1.md` (committed)
- `reports/phase_reports/phase_5_3b_baseline_evaluation_implementation.md`
- `EXPERIMENT_LOG.md` — EXP-001 added

Key report findings:
- Best broad primary baseline: B3 (FS-E) val log_loss=0.8527
- Full B1→B3 signal: Δ−0.0326 log_loss units
- No broad baseline below 0.85 — this is the Phase 6 floor

## Phase 6: GBM modeling

Goal: train the first serious nonlinear tabular model.

### Ticket 6.1A — GBM Model Choice Audit

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

Status: complete. HistGradientBoostingClassifier selected. No new dependencies.

### Ticket 6.1B — First GBM Implementation

Train first GBM model on the verified dataset.

Required:

```text
same split as baselines
same metrics
ablation comparison
feature importance or permutation importance if feasible
```

Status: complete. G1–G6 trained (HistGBM). Best broad: G2 val log_loss=1.2326. Best eval (expl): G5 val log_loss=1.1854.

Local artifacts (gitignored):

```text
data/processed/gbm_results_2024_09_25k_v1.json
data/processed/gbm_predictions_2024_09_25k_v1.parquet
```

### Ticket 6.2A — GBM Evaluation Slice Audit

Audit GBM and baseline artifacts to determine which slice diagnostics are
feasible on the existing dataset. Determine what can be computed from the
existing predictions Parquet without retraining.

Status: complete. Five feasible slices identified: phase, move_number,
is_time_forfeit, has_eval, avg_elo bucket (via feature join). G2 confirmed
as primary broad GBM. G4 identified as near-prior/degenerate. G6 identified
as complete memorisation. Audit report in chat only (no files created).

### Ticket 6.2B — GBM Evaluation Implementation

Implement `gbm_evaluation.py` (18 functions A–R + CLI): load GBM/baseline
results, compute slice accuracy, confidence bucket diagnostic, avg_elo join,
and render a durable Markdown evaluation report.

Status: complete. See `reports/gbm_evaluation_2024_09_25k_v1.md` and
`reports/phase_reports/phase_6_2b_gbm_evaluation_implementation.md`.

Key results:
- G2 val log_loss=1.2326 — does NOT beat B3 (0.8527)
- G1/G2 train/val gap >+1.0 — severe overfit
- G4 near-prior (max_prob mean≈0.476) — diagnostic only, not a winner
- G6 train_ll≈0.004 — complete memorisation of 645 eval training rows
- All broad GBMs predict 0 DRAW on validation

Local artifacts (gitignored): none new (reuses 6.1B artifacts).

### Ticket 6.3A — Feature Importance Audit

Audit-only. Inspect HistGBM for native `feature_importances_` availability,
permutation importance feasibility, model artifact availability, feature columns
for G1–G6, scoring metric choice, and report language constraints.

Status: complete. Audit report in chat only (no files created).

Key findings:
- HistGradientBoostingClassifier in sklearn 1.9.0 does NOT expose `feature_importances_`
- `sklearn.inspection.permutation_importance` available; no new dependency needed
- G2 retrainable deterministically from local data artifacts (~4 seconds)
- Only white_elo (+0.029) and avg_elo (+0.029) show positive importance
- 15 of 20 features show negative importance — overfit artifacts, not uselessness
- clock_diff_s is most negative (≈−0.048): G2 overfit clock patterns

### Ticket 6.3B — Feature Importance Implementation

Implement `gbm_feature_importance.py` (16 functions A–P + CLI): retrain G2 in
memory, compute validation-set permutation importance, and render a caveated
12-section Markdown diagnostic report. No model artifacts saved, no calibration,
no SHAP, no new dependencies.

Status: complete. See `reports/gbm_feature_importance_2024_09_25k_v1.md` and
`reports/phase_reports/phase_6_3b_feature_importance_implementation.md`.

Key results:
- G2 retrained val log_loss: 1.2369 (consistent with Phase 6.1B)
- Positive signal: white_elo (+0.0169), avg_elo (+0.0410)
- Near-zero / negative: all clock and position features
- clock_diff_s most negative (−0.0481): largest overfit artifact
- Report explicitly frames all results as overfit diagnostics, not final rankings

Local artifacts (gitignored): none (G2 retrained in memory only).

## Phase 7 — Calibration

### Ticket 7.1A — Calibration Audit
ML | D2 | CAUTIOUS

Status: complete (audit-only; no files created). Key findings:
- B3 ECE OvR: BLACK_WIN=0.026, DRAW=0.001, WHITE_WIN=0.033 — reasonably calibrated
- G2 ECE OvR: BLACK_WIN=0.234, DRAW=0.061, WHITE_WIN=0.203 — severely overconfident
- G2 [0.9,1.0] confidence bucket: mean_conf=0.949, acc=0.594, gap=+0.355
- DRAW sparsity (~59/931 val rows, 6.3%): DRAW ECE not informative
- G4 excluded (near-prior); G5/G6 excluded (eval-gated/memorization)

### Ticket 7.1B — Calibration Implementation
ML | D2 | IMPLEMENTATION
Requires post-implementation report.

Status: complete. See `reports/calibration_2024_09_25k_v1.md` and
`reports/phase_reports/phase_7_1b_calibration_implementation.md`.

Key results (val split, 931 rows):
- B1 ECE OvR: BLACK_WIN=0.002, DRAW=0.001, WHITE_WIN=0.004 (prior — degenerate)
- B3 ECE OvR: BLACK_WIN=0.026, DRAW=0.001, WHITE_WIN=0.033 — best calibrated
- G2 ECE OvR: BLACK_WIN=0.234, DRAW=0.061, WHITE_WIN=0.203 — severely overconfident
- B3 classwise Brier: BLACK_WIN=0.239, DRAW=0.059, WHITE_WIN=0.236
- G2 classwise Brier: BLACK_WIN=0.313, DRAW=0.068, WHITE_WIN=0.301
- No post-hoc calibrators fitted. Diagnostics only.

Local artifacts (gitignored): none.

### Ticket 7.2A — Probability Interpretation Audit
REPORTING/ML | D1 | CAUTIOUS

Status: complete (audit-only; no files created). Key findings:
- B3 is the only currently usable model for cautious descriptive probability claims
- G2 is overfit (gap=+1.069) and overconfident (ECE≈0.20–0.23); probabilities not usable
- B1's low ECE is a prior-only trap; predicts constant class frequencies
- DRAW probability unreliable for all models (6.3% sparsity, 59/931 val rows)
- Guardrail categories defined: Allowed, Cautious, Forbidden claims
- No constraint-effect claims established; requires Phase 8 + Phase 9

### Ticket 7.2B — Probability Interpretation Report Implementation
REPORTING/ML | D1 | IMPLEMENTATION
Requires post-implementation report.

Status: complete. See `reports/probability_interpretation_2024_09_25k_v1.md` and
`reports/phase_reports/phase_7_2b_probability_interpretation_implementation.md`.

Key outputs:
- probability_interpretation.py (12 functions A–L + CLI)
- 73 tests in test_probability_interpretation.py; 1123 total tests passing
- 14-section guardrails report generated from real artifacts
- Allowed/Cautious/Forbidden claims matrix codified
- Explicit prohibition on G2 probability interpretation, DRAW claims, causal claims

Local artifacts (gitignored): none.

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
