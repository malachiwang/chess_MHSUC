# Experiment Log

Use this file to record durable experiment summaries. Not every exploratory notebook cell needs to be logged, but every result that influences project direction should be summarized here.

## Experiment template

```text
Experiment ID:
Date:
Owner:
Status: planned / running / complete / abandoned

Question:

Dataset:
- Source:
- Time control:
- Scan/sample size:
- Filters:
- Number of games:
- Number of rows/positions:
- Eval source:
- Label:

Features:

Split:
- Split unit:
- Train/validation/test proportions:
- Leakage controls:

Models:

Metrics:

Results:

Interpretation:

Known limitations:

Next step:
```

---

## EXP-000 — Placeholder

Status: not started

Use the template above after the first data/modeling run.

---

## EXP-001 — Phase 5.2B Baseline Models (B0–B5 + B3-balanced)

Experiment ID: EXP-001
Date: 2026-06-07
Owner: Malachi Wang
Status: complete

Question:
Can simple baselines (DummyClassifier + LogisticRegression) predict human chess
game outcomes from mid-game snapshots? What is the baseline floor for Phase 6?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract
- Time control: 10+0
- Scan/sample size: ~25k games scanned
- Filters: Stockfish-annotated positions; broad subset ≥ 1 eval position
- Number of games (broad): 2460 clean games; train=1626 / val=348 / test=349
- Number of rows/positions (broad primary_numbered view): 6205
- Eval source: Stockfish (embedded in Lichess PGN comments)
- Label: result_class (BLACK_WIN / DRAW / WHITE_WIN) from game termination

Features:
- FS-A: dummy (label frequencies only)
- FS-B: game metadata (white_elo, black_elo, elo_diff, time_control_seconds)
- FS-E: FS-B + clock features + position features (18 columns)
- FS-F / FS-G: eval-gated feature sets (exploratory)

Split:
- Split unit: game_id (not row-level)
- Train/validation/test proportions: 70 / 15 / 15
- Leakage controls: stratified by result_class, seed=42, split by game

Models:
- B0: DummyClassifier(strategy='most_frequent')
- B1: DummyClassifier(strategy='prior')
- B2: LogisticRegression on FS-B
- B3: LogisticRegression on FS-E
- B3-balanced: LogisticRegression(class_weight='balanced') on FS-E (diagnostic)
- B4: LogisticRegression on FS-F (eval-gated, exploratory)
- B5: LogisticRegression on FS-G (eval-gated, exploratory)

Metrics:
Primary: log_loss (validation set). Secondary: accuracy, multiclass_brier, macro_f1.

Results:
Broad baselines (val log_loss, sorted ascending):
- B3  (FS-E): 0.8527 — best broad baseline
- B2  (FS-B): 0.8740
- B1  (FS-A prior): 0.8853
- B0  (FS-A most_frequent): 18.8929 (expected; excluded from comparison)
- B3-balanced (diagnostic): 1.0623 (DRAW recall improved, log_loss cost)

Eval baselines (exploratory):
- B4 (FS-F): val log_loss=0.7833, test acc=0.7071
- B5 (FS-G): val log_loss=0.8598, test acc=0.7000

Signal decomposition (B1→B3, val log_loss):
B1 prior (0.8853) → B2 +metadata (0.8740, Δ−0.011) → B3 +clock/pos (0.8527, Δ−0.021)
Full B1→B3 improvement: Δ−0.0326 log_loss units.

Confusion matrices (B3, val): all unweighted LR models predict 0 DRAW rows.
B3-balanced DRAW recall improves to 0.322 (from 0.000) at the cost of log_loss.

Interpretation:
Clock and position features carry real but modest predictive signal. The baseline
floor is B3 val log_loss ≈ 0.85. DRAW class (~6% of rows) is systematically
under-predicted without class weighting, making accuracy misleading. Log_loss is
the correct primary metric for this task.

Known limitations:
- DRAW class sparsity in eval splits (~4 val / ~2 test rows): eval DRAW metrics noisy.
- No hyperparameter tuning performed on LR models.
- No calibration assessed.
- Eval and broad baselines are not directly comparable (selection bias ~+20 Elo).

Next step:
Phase 6 GBM (HistGradientBoostingClassifier) experiments targeting B3 val
log_loss < 0.8527. Calibration assessment in Phase 6.2.
