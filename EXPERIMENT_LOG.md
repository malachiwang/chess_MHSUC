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
log_loss < 0.8527. Evaluation and slice diagnostics in Phase 6.2B.

---

## EXP-002 — Phase 6.1B/6.2B GBM Models (G1–G6 + evaluation)

Experiment ID: EXP-002
Date: 2026-06-08
Owner: Malachi Wang
Status: complete

Question:
Does the first HistGradientBoostingClassifier (GBM) beat the best broad
logistic baseline (B3, val log_loss=0.8527)? What are the overfitting
patterns, DRAW failure modes, and slice-level diagnostics?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract
- Time control: 10+0
- Scan/sample size: ~25k games scanned
- Broad primary_numbered view: train=4344 / val=931 / test=930 rows
- Eval primary_numbered view: train=645 / val=147 / test=140 rows
- Eval source: Stockfish (embedded in Lichess PGN comments)
- Label: result_class (BLACK_WIN / DRAW / WHITE_WIN)

Features:
- FS-B: game metadata (white_elo, black_elo, elo_diff, time_control_seconds)
- FS-C: clock features (13 cols)
- FS-D: position context (move_number, checkpoint, phase — 3 cols after drop)
- FS-E: FS-B + clock + position (18 cols, 2 string cols dropped → 20 used)
- FS-F: eval-gated features + position (exploratory)
- FS-G: all features including eval (exploratory)

Split:
- Split unit: game_id (not row-level)
- Train/validation/test: 70/15/15
- Leakage controls: stratified by result_class, seed=42

Models:
- G1: HistGBM on FS-B (broad primary)
- G2: HistGBM on FS-E (broad primary — primary comparison vs B3)
- G3: HistGBM on FS-C (broad diagnostic — clock ablation)
- G4: HistGBM on FS-D (broad diagnostic — position context only)
- G5: HistGBM on FS-F (eval exploratory)
- G6: HistGBM on FS-G (eval exploratory)
Fixed params: max_iter=300, lr=0.05, max_leaf_nodes=31, min_samples_leaf=20,
l2_reg=0.1, seed=42. No tuning, no calibration.

Metrics:
Primary: log_loss (validation set). Secondary: accuracy, multiclass_brier, macro_f1.

Results:
Broad primary (val log_loss):
- G2 (FS-E): 1.2326 — primary broad GBM; does NOT beat B3 (0.8527)
- G1 (FS-B): 1.4178

Broad diagnostic:
- G4 (FS-D): 0.8812 — near-prior/degenerate; low gap reflects prior behaviour
- G3 (FS-C): 0.9861 — moderate overfit

Eval exploratory:
- G5 (FS-F): 1.1854 — significant overfit
- G6 (FS-G): 1.6409 — complete memorisation (train_ll≈0.004)

Overfitting gaps (train→val log_loss):
G1: +1.233, G2: +1.069, G3: +0.432, G4: +0.001, G5: +0.763, G6: +1.637

DRAW: all broad GBMs predict 0 DRAW on validation (mirrors unweighted LR).

Slice diagnostics (G2 val):
- Phase: endgame 0.561 > middlegame 0.500 > opening 0.480
- Move_number: increases monotonically (10→0.480, 40→0.561)
- is_time_forfeit: True=0.569, False=0.491 (limited support, n=102)
- has_eval: False=0.524, True=0.367 (eval=bias proxy)
- avg_elo bucket: non-monotone; 1400–1600 dip (acc=0.385); noisy at pilot scale

Confidence bucket diagnostic (G2 val):
Weak, non-monotone confidence/accuracy relationship. Consistent with
miscalibrated overfit model. No calibration fitted.

Interpretation:
G2 does not beat B3 on any metric. This is a controlled diagnostic result:
GBM overfits the small pilot dataset (~4,344 broad rows). G4's near-prior
behaviour confirms position-context features (phase/checkpoint/move_number)
alone do not discriminate individual games at this scale. The baseline floor
(B3 val log_loss=0.8527) stands. More data, regularisation tuning, or
calibration needed before nonlinear gains can be claimed.

Known limitations:
- No hyperparameter tuning (fixed GBM_PARAMS).
- No calibration assessed (deferred to Phase 7).
- Eval-gated models not directly comparable to broad models.
- DRAW class sparsity in broad validation (~59/931 rows ≈ 6%).
- Eval DRAW support very sparse (~14 val rows).
- Slice patterns noisy at pilot scale; not reliable for constraint conclusions.

Next step:
Phase 6.3A — Feature Importance Audit. Note: importances from the overfit G2
may not be reliable. Phase 7 Calibration and Phase 8 Scaling also needed.
