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
- Filters: games reaching first selected checkpoint (ply ≥ 20 / move 10); no eval filter on broad subset
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

**Erratum (Ticket 7.3B, 2026-06-10):** The "Filters" line above originally read
"Stockfish-annotated positions; broad subset ≥ 1 eval position" — this was incorrect.
The broad modeling population (B1–B3) has no eval requirement. The actual filter is:
clean Lichess 10+0 games that reached the first selected checkpoint (ply ≥ 20 / move 10).
2,460 clean games produced 2,323 broad feature games (137 games with n_plies < 20 excluded
as they did not reach the first checkpoint). The eval-annotated subset (13.7% of broad rows)
was used only for exploratory B4/B5 baselines, not for B1–B3.

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
may not be reliable. Phase 7 Calibration and Phase 8 Stockfish/eval validation also needed.

---

## EXP-003 — Phase 6.3B G2 Permutation Feature Importance Diagnostic

Experiment ID: EXP-003
Date: 2026-06-08
Owner: Malachi Wang
Status: complete

Question:
Which G2 features show positive permutation importance on the validation set?
Are clock and position features genuinely useful to G2 or overfit artifacts?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract
- Broad primary_numbered view: train=4344 / val=931 rows
- Eval source: Stockfish (embedded in Lichess PGN comments)
- Label: result_class (BLACK_WIN / DRAW / WHITE_WIN)

Features:
- FS-E: Rating + clock + position (20 numeric cols after string drop)
- String categoricals dropped: selected_position_type, phase
- 20 features used: white_elo, black_elo, elo_diff, avg_elo, clock features (13),
  move_number, checkpoint_index, phase_index

Split:
- Importance scored on validation split only (931 rows)
- Test split not used
- Split unit: game_id, seed=42

Models:
- G2 retrained in memory using identical GBM_PARAMS (max_iter=300, lr=0.05,
  max_leaf_nodes=31, min_samples_leaf=20, l2_reg=0.1, random_state=42)
- No model artifact saved

Metrics:
- sklearn permutation_importance with scoring='neg_log_loss'
- n_repeats=10, random_state=42
- delta_log_loss = -importances_mean (positive = predictive, negative = overfit)

Results:
G2 retrained val log_loss: 1.2369 (6.3B deterministic retrain).
Stored Phase 6.1B G2 val log_loss: 1.2326. Difference: +0.0043 — small
reconstruction drift between saved Phase 6.1B metrics and in-memory 6.3B retrain.
Accepted and documented; qualitative findings identical.

Permutation importance (top/bottom, deterministic 6.3B CLI values):
- avg_elo:      +0.0410 — positive diagnostic signal
- white_elo:    +0.0169 — positive diagnostic signal
- clock_diff_s: −0.0481 — negative overfit artifact (most negative)
- 18 of 20 features: near-zero or negative

Interpretation:
Rating signal (white_elo, avg_elo) survives overfit well enough to show positive
importance on validation. G2 placed the largest learned weight on clock-difference
patterns that do not generalize (clock_diff_s: −0.048). All position and most clock
features show near-zero or negative importance — overfit signatures, not evidence
these variables are irrelevant to chess outcomes.

The four rating features (white_elo, black_elo, elo_diff, avg_elo) are correlated;
permutation distributes signal unpredictably across them. Interpret as a group:
rating signal is robustly present in G2.

Known limitations:
- G2 is overfit (val log_loss 1.2369 >> B3 0.853). Importances reflect the overfit
  model's learned function, not the true predictive value of features.
- Permutation importance is not causal explanation.
- Clock/position negative importance means G2 failed to generalize them — not that
  they are unimportant to chess outcomes.
- Results are pilot-scale only (931 val rows, 4344 train rows).
- No calibration performed.
- No SHAP. No new dependencies.

Next step:
Phase 7 Calibration or Phase 8 Stockfish/eval validation. Feature importance from
a better-fit model on more data will be more informative for constraint analysis.

---

## EXP-004 — Phase 7.1B Calibration Diagnostics (B1, B3, G2)

Experiment ID: EXP-004
Date: 2026-06-08
Owner: Malachi Wang
Status: complete

Question:
How well-calibrated are B1, B3, and G2 on the validation split? What are
the OvR reliability gaps, ECE, and classwise Brier scores for each model?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract
- Time control: 10+0
- Split: validation only (931 rows, broad primary_numbered view)
- Eval source: Stockfish (embedded in Lichess PGN comments)
- Label: result_class (BLACK_WIN / DRAW / WHITE_WIN)
- Class distribution: BLACK_WIN=443 (47.6%), DRAW=59 (6.3%), WHITE_WIN=429 (46.1%)

Features:
- Calibration assessed on model probability outputs; no feature access needed.
- B1 uses FS-A (prior); B3 uses FS-E (18 cols); G2 uses FS-E (20 numeric cols).

Split:
- Split unit: game_id
- Assessment on validation split only; test split not used.

Models:
- B1: DummyClassifier(strategy='prior')
- B3: LogisticRegression on FS-E
- G2: HistGradientBoostingClassifier on FS-E (primary_numbered view)
- G4 excluded: near-prior (max_prob mean ≈ 0.476) — deceptively calibrated
- G5/G6 excluded: eval-gated / memorization

Metrics:
Primary: ECE (OvR, 5-bin uniform). Secondary: classwise Brier (OvR),
top-label confidence-accuracy table (10-bin uniform).

Results:
ECE OvR (val):
- B1:  BLACK_WIN=0.0023, DRAW=0.0012, WHITE_WIN=0.0035
- B3:  BLACK_WIN=0.0260, DRAW=0.0009, WHITE_WIN=0.0327
- G2:  BLACK_WIN=0.2338, DRAW=0.0608, WHITE_WIN=0.2034

Classwise Brier OvR (val):
- B1:  BLACK_WIN=0.2494, DRAW=0.0594, WHITE_WIN=0.2485
- B3:  BLACK_WIN=0.2388, DRAW=0.0589, WHITE_WIN=0.2362
- G2:  BLACK_WIN=0.3125, DRAW=0.0681, WHITE_WIN=0.3012

G2 top-label confidence-accuracy (val, selected bins):
- [0.50, 0.60): n=185, acc=0.432, conf=0.549, gap=+0.116
- [0.70, 0.80): n=171, acc=0.491, conf=0.751, gap=+0.260
- [0.80, 0.90): n=193, acc=0.497, conf=0.851, gap=+0.353
- [0.90, 1.00): n=175, acc=0.594, conf=0.949, gap=+0.355

Interpretation:
B3 is reasonably calibrated on BLACK_WIN and WHITE_WIN (ECE ≈ 0.03).
G2 is severely overconfident (ECE ≈ 0.20–0.23): the GBM memorized training
patterns that produce high-confidence predictions without corresponding accuracy.
DRAW ECE is small for all models but reflects near-zero predictions on a sparse
class, not genuine calibration. No post-hoc calibrators were fitted.

Known limitations:
- DRAW class sparsity (59/931 val rows, 6.3%): DRAW OvR calibration metrics
  dominated by near-zero predictions — not informative.
- 5 reliability bins may have sparse counts, especially for extreme bins.
- No calibration applied; diagnostics only.
- No plots produced.
- Pilot scale only (931 val rows).

Next step:
Phase 7.2 Probability Interpretation or Phase 8 Stockfish/eval validation. A
post-hoc calibration experiment (Platt/isotonic) may be warranted after model
improvement in Phase 8.

---

## EXP-005 — Phase 7.2B Probability Interpretation Guardrails (B1, B3, G2)

Experiment ID: EXP-005
Date: 2026-06-09
Owner: Malachi Wang
Status: complete

Question:
What do the current model probabilities (B1, B3, G2) mean? Which models are
safe to use for descriptive probability claims, which require caution, and
which are forbidden for interpretation? What guardrails apply before constraint
or subgroup claims can be made?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract
- Time control: 10+0
- Split: validation only (931 rows, broad primary_numbered view)
- Eval source: Stockfish (embedded in Lichess PGN comments)
- Label: result_class (BLACK_WIN / DRAW / WHITE_WIN)
- Class distribution: BLACK_WIN=443 (47.6%), DRAW=59 (6.3%), WHITE_WIN=429 (46.1%)

Features:
- Calibration and log-loss metrics assessed from existing artifacts.
- No new feature computation or model training.

Split:
- Assessment on validation split only; test split not used.

Models assessed:
- B1: DummyClassifier(strategy='prior') — appears calibrated, degenerate
- B3: LogisticRegression on FS-E — safest broad model, cautiously usable
- G2: HistGradientBoostingClassifier on FS-E — severely overfit, not usable

Metrics:
- val log_loss: B1=0.8853, B3=0.8527, G2=1.2326
- G2 train log_loss: 0.1636; overfit gap: +1.0690
- ECE OvR: B3 BW=0.026, WW=0.033; G2 BW=0.234, WW=0.203
- G2 [0.9,1.0] high-conf bucket: n=175, acc=0.594, conf=0.949, gap=+0.355

Results:
Probability interpretation guardrails established:
- ALLOWED (with caveats): B3 BLACK_WIN / WHITE_WIN as pilot-scale descriptive estimates
- CAUTIOUS: B3 for dataset distribution descriptions; B3 DRAW excluded (sparsity)
- FORBIDDEN: G2 probability claims; B1 as informative; causal-effect claims;
  constraint-effect claims (require Phase 8/9); test-split revealed results

Interpretation:
B3 is the only currently usable model for cautious descriptive claims about
outcome probabilities. G2 is severely overfit and overconfident. B1's low ECE
is a prior-only trap. DRAW probability (all models) is unreliable at this
class frequency (6.3%). No constraint-effect conclusions are established;
Phase 8 (Scaling) is required before any cross-stratum comparisons.

Known limitations:
- Pilot scale only (931 val rows).
- No post-hoc calibrators; B3 ECE reflects raw LR probabilities.
- DRAW class too sparse for reliable probability estimates.
- Correlational findings only; no causal design.
- Guardrails are conservative by design; may be relaxed after Phase 8.

Next step:
Phase 8 (Stockfish/eval-conditioned modeling) before constraint-effect claims.
Post-hoc calibration (Phase 7.3) deferred until model quality improves.

---

## EXP-006 — Phase 7.3B Modeling Hygiene Hardening

Experiment ID: EXP-006
Date: 2026-06-10
Owner: Malachi Wang
Status: complete

Question:
What documentation, infrastructure, and model-comparison gaps exist before Phase 8?
Specifically: (1) are there unfair model comparisons due to missing early stopping?
(2) are there undocumented population exclusions? (3) is the test split protected?
(4) are there leakage risks in the test suite? (5) has roadmap/log drift accumulated?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract (same pilot, no new data)
- Validation split: 931 rows (broad primary_numbered view)
- No new data acquisition or dataset version.

Models added:
- G2b: HistGradientBoostingClassifier on FS-E, same as G2 but with
  early_stopping=True, validation_fraction=0.15, n_iter_no_change=10.
  This is a fair comparison: G2 ran 300 unstopped iterations on 4,344 training
  rows because sklearn early_stopping='auto' does not activate below 10,000 samples.

Metrics (G2b val, primary_numbered):
- See gbm_hygiene_results_2024_09_25k_v1.json for G2b val log_loss and n_iter_actual.
- G2b expected to use fewer iterations and produce better-calibrated probabilities
  than G2 at this sample size.

Infrastructure changes:
- bootstrap_ci.py: game-level cluster bootstrap (1,000 replicates, seed=42)
  for val log_loss CIs on B1, B3, G2, G2b. Resamples game_ids, not rows.
- WORKFLOW.md §13: formal holdout/test-split policy documented.
- dataset_card: C9 caveat documenting 137 excluded short games (n_plies < 20).
- EXPERIMENT_LOG: EXP-001 filter erratum corrected; Phase 8 naming drift fixed (EXP-002–005).
- ROADMAP.md: Phase 7.3 hardening section added; completed tickets stanza updated.
- v1 report module warning comments: gbm_feature_importance.py, calibration.py,
  baseline_evaluation.py each note hardcoded v1 metrics that require re-derivation
  if dataset or model parameters change.
- test_data_integrity.py: population accounting test + prediction/split consistency checks.
- test_baselines.py: permuted-label anti-leakage test.
- test_gbm.py: G2b-specific tests.

Known limitations:
- G2b still uses the same small pilot dataset; expect similar overfit signature.
- Bootstrap CIs on 931 val rows are wide; precise interval endpoints should not
  be over-interpreted at this sample size.
- Short-game exclusion (137 games) is a population-definition choice, not a bug;
  any future dataset version should document whether this exclusion still applies.
- Holdout policy is documented but historically-exposed test metrics (Phases 5.2B,
  6.1B) stand as records and were not used for model selection decisions.

Next step:
Phase 8 (Stockfish/eval-conditioned modeling) — G2b bootstrap CIs provide
the fair uncertainty baseline for comparing against any Phase 8 models.

---

## EXP-007 — Phase 8.1B Fixed-Depth Stockfish Evaluation

Experiment ID: EXP-007
Date: 2026-06-10
Owner: Malachi Wang
Status: complete

Question:
Can local fixed-depth Stockfish evaluation (depth=12) provide full coverage of the
pilot checkpoint positions, replacing the sparse (13.7%), selection-biased Lichess
cloud eval? How well does local SF eval agree with existing Lichess cloud evals on the
overlap positions?

Dataset:
- Source: Lichess 10+0 (600+0) games, 2024-09 extract (same pilot, no new data)
- Positions: primary_numbered checkpoints from ten_zero_positions_broad_2024_09_25k_v1.parquet
- Input: 6,205 positions across 2,323 unique games
- Engine: Stockfish 18, depth=12 (fixed)

Coverage result:
- 6,205/6,205 positions evaluated (100% coverage, 0 failures)
- Up from 932/6,205 (13.7%) Lichess cloud eval coverage
- No selection bias: local eval evaluates all games uniformly

Eval distribution:
- equal (|cp| < 100): 1,791 (28.9%)
- winning_white [300, 10000): 1,385 (22.3%)
- losing_black (−10000, −300]: 1,103 (17.8%)
- slight_white [100, 300): 1,031 (16.6%)
- slight_black (−300, −100]: 683 (11.0%)
- mate_white (cp = 10000): 119 (1.9%)
- mate_black (cp = −10000): 93 (1.5%)

Lichess eval overlap agreement (932 positions):
- Sign agreement (non-mate positions): 829/872 = 95.1%
- Mean absolute cp difference: 68.8 cp
- Note: exact equality not expected; Lichess used a different Stockfish version
  at variable depth. 95.1% sign agreement confirms the local eval is directionally
  consistent with the Lichess cloud eval.

Output artifact:
- data/processed/sf_eval_broad_2024_09_25k_v1.parquet (6,205 rows, gitignored)
- data/processed/sf_eval_metadata_2024_09_25k_v1.json (gitignored)
- reports/stockfish_eval_2024_09_25k_v1.md (committed)

Implementation notes:
- FEN reconstruction via python-chess: stream raw PGN, replay moves to target ply,
  call board.fen(). fen_hash = sha256[:16]. No FENs stored in pipeline previously.
- PGN indexed in a single pass; stops early once all 2,323 target game_ids found.
- Bug fixed during implementation: pl.DataFrame(rows) infers Null type for nullable
  int columns (sf_eval_mate, sf_nodes, etc.) from first 100 rows. Fix: explicit
  _RESULT_SCHEMA constant with pl.from_dicts(rows, schema=_RESULT_SCHEMA).

Known limitations:
- Depth=12 is pragmatic; deeper eval would produce slightly different centipawn values.
- Fixed-depth local eval is not causal; it encodes position strength at a checkpoint.
- Models trained on sf_eval_* features will be implemented in Ticket 8.2B.
- No models trained in this ticket.

Next step:
Phase 8.2 — Existing-vs-fixed eval comparison audit and eval-conditioned modeling.


---

## EXP-008 — Phase 8.2B Eval-Conditioned Modeling / Ablation

Experiment ID: EXP-008
Date: 2026-06-10
Owner: Malachi Wang
Status: complete

Question:
After controlling for objective position strength via fixed-depth Stockfish
eval, do human/context features (rating, clock, checkpoint/phase) still add
predictive signal for empirical human game outcomes?

Dataset:
- dataset_id: lichess_ten_zero_2024_09_25k_v1
- version_tag: 2024_09_25k_v1
- Stockfish artifact: data/processed/sf_eval_broad_2024_09_25k_v1.parquet
  (8.1B; Stockfish 18, depth=12, 6,205 primary_numbered positions)
- Broad primary view: train=4,344 / val=931 / test=930 rows
- Join: (game_id, selected_position_type), 0 orphans

Models (all LogisticRegression max_iter=1000 lbfgs; no GBMs):
- E1 (FS-H): sf_eval_cp_clipped + sf_is_mate_eval only
- E3 (FS-I): rating (FS-B) + eval block
- E4 (FS-J): rating + clock (FS-C) + eval block
- E5 (FS-K): full B3 human context (FS-E) + eval block
- References: B1/B2/B3 loaded from committed baseline artifacts (not retrained)

Primary validation metrics (log_loss / accuracy / macro_f1 / Brier):
- E1: 0.7581 / 0.6520 / 0.4489 / 0.4515
- E3: 0.7500 / 0.6584 / 0.4533 / 0.4467
- E4: 0.7362 / 0.6617 / 0.4555 / 0.4363
- E5: 0.7310 / 0.6563 / 0.4518 / 0.4356  (best E; B3 reference = 0.8527)

Key pairwise game-level bootstrap deltas (1,000 replicates, seed=42;
delta = LL(B) - LL(A), negative = B improved):
- E3 -> E4 (KEY: clock after eval + rating): -0.0138 [-0.0266, -0.0002]
  EXCLUDES ZERO — clock adds resolvable predictive signal, but the upper
  bound is extremely close to zero; fragile at pilot scale.
- E1 -> E3 (rating after eval): -0.0081 [-0.0223, +0.0042] contains zero.
- E4 -> E5 (context after clock): -0.0052 [-0.0147, +0.0042] contains zero.
- B3 -> E1 (eval alone vs champion): -0.0946 [-0.1355, -0.0477] excludes zero.
- B3 -> E5 (champion vs best E): -0.1217 [-0.1565, -0.0828] excludes zero —
  best eval-conditioned model clearly improves on B3.

Caveats:
- All findings are predictive associations, not causal effects.
- Stockfish depth=12 eval is objective position context, not ground truth.
- Late checkpoints are increasingly decided; per-checkpoint slices reported
  (E5 val log_loss: move_10=0.794 → move_40=0.639). Degradation curves NOT
  established.
- DRAW directional only (59/931 val rows). DRAW is not solved.
- 27 terminal sf_depth=0 rows (0.4%) are mechanically decided.
- Test split untouched for selection (metrics recorded only).

Artifacts (gitignored):
- data/processed/eval_conditioned_results_2024_09_25k_v1.json
- data/processed/eval_conditioned_predictions_2024_09_25k_v1.parquet (24,820 rows)
Committed report: reports/eval_conditioned_modeling_2024_09_25k_v1.md

Next step:
Phase 9 (scale-up) audit — re-examine the fragile E3->E4 clock finding and
the E-model advantage at larger N before any constraint-effect claims.

---

## EXP-009 — Phase 9.1B Scale-Up Replication

Experiment ID: EXP-009
Date: 2026-06-10
Owner: Malachi Wang
Status: complete

Question:
Does the fragile 8.2B clock finding (E3->E4: clock adds predictive signal
after eval + rating, CI barely excluding zero) survive a 10x scale-up?

Dataset:
- dataset_id: lichess_ten_zero_2024_09_250k_v1
- version_tag: 2024_09_250k_v1
- Source: same 2024-09 Lichess archive; deterministic first-250,000-games
  prefix (SUPERSET of the 25k pilot; splits redrawn game-level seed=42;
  scale-robustness test, not independent cross-month replication)
- Raw sample: 250,000 games scanned -> 26,041 600+0 -> 25,887 clean ->
  24,520 broad feature games -> 65,368 primary positions
- Splits (rows): train=45,818 / val=9,823 / test=9,727
- Raw prefix tee-cached to data/raw/lichess/lichess_2024_09_first250k.pgn
  (583 MB, gitignored)

Stockfish:
- Stockfish 18, depth=12 (8.1B semantics), local cached PGN
- Coverage: 65,368/65,368 (100%), 0 failures, runtime 1,838 s
- Depth histogram: 65,080 @ depth 12; 288 terminal sf_depth=0 rows (0.4%)
- Lichess overlap: 10,166 rows; non-mate sign agreement 95.6%; mean |cp|
  diff 60.3

Models (logistic-only; no GBMs):
- References retrained: B1=0.8813, B2=0.8684, B3=0.8533 (val log_loss)
- E1 (sf_eval only)=0.7568; E3 (+rating)=0.7514; E4 (+clock)=0.7377;
  E5 (+full context)=0.7329 (best)
- All values within ~0.002 of pilot — extremely stable across 10x.

PRIMARY RESULT — E3 -> E4 paired game-level bootstrap delta (val):
- This run: -0.0138, 95% CI [-0.0186, -0.0091] — EXCLUDES ZERO
- Pilot (8.2B): -0.0138, 95% CI [-0.0266, -0.0002] — excluded zero barely
- Verdict: PILOT FINDING CONFIRMED. Identical point estimate; CI narrowed
  ~3x as expected from sqrt(10) more games.

Secondary deltas (all now exclude zero at scale):
- E1->E3 (rating after eval): -0.0054 [-0.0099, -0.0010] (pilot: unresolved)
- E4->E5 (context after clock): -0.0048 [-0.0068, -0.0028] (pilot: unresolved)
- B3->E1: -0.0965 [-0.1099, -0.0832]; B3->E5: -0.1204 [-0.1321, -0.1095]

Per-checkpoint E3->E4 deltas (new diagnostic):
- move_10: -0.0025 [contains zero]; move_20: -0.0033 [contains zero]
- move_30: -0.0238 [excludes zero]; move_40: -0.0606 [excludes zero]
- Clock signal concentrates in late checkpoints. Diagnostic only; does not
  establish degradation curves.

Caveats:
- Predictive associations only; not causal effects.
- Stockfish depth=12 eval is position context, not ground truth.
- Superset sample; external validity beyond 2024-09 not established.
- Player-level leakage unresolved (no usernames stored); grows with scale.
- DRAW not solved: 603/9,823 val rows; unweighted LR predicts zero DRAW
  argmax rows (per-class DRAW f1=0.0 at support 603).
- Test split untouched for selection (WORKFLOW.md section 13).

Artifacts (gitignored): sf_eval_broad/eval_conditioned_* 2024_09_250k_v1
under data/processed/. Committed: reports/scale_up_2024_09_250k_v1.md,
reports/eval_conditioned_modeling_2024_09_250k_v1.md, phase report.

Next step:
Phase 9.2 candidates: pilot-disjoint or cross-month sample for external
validity; rating-band effect stability; GBM diagnostic now defensible at
45k train rows; player-level leakage quantification.

---

## EXP-010 — Phase 9.2B Constraint Slice Analysis

Experiment ID: EXP-010
Date: 2026-06-10
Owner: Malachi Wang
Status: complete

Question:
Where does the replicated E3->E4 clock signal (EXP-009: -0.0138
[-0.0186, -0.0091]) concentrate? Slices fixed by the 9.2A audit BEFORE
results were computed; no post-hoc tuning.

Inputs (no models trained or retrained):
- dataset_id: lichess_ten_zero_2024_09_250k_v1 / 2024_09_250k_v1
- data/processed/eval_conditioned_predictions_2024_09_250k_v1.parquet
  (E3/E4 validation rows, 9,823 per model, pairing validated per cell)
- Slice keys joined from feature_positions_broad + sf_eval_broad on
  (game_id, selected_position_type); 0 orphans; val split only.
- Bootstrap: game-level clustered, 1,000 replicates, seed=42; CI only for
  cells with >= 300 unique games; sub-threshold cells reported descriptively.

Reference (per-checkpoint, matches EXP-009):
- move_10 -0.0025 [cz], move_20 -0.0033 [cz],
  move_30 -0.0238 [excl], move_40 -0.0606 [excl]

P1 — eval decidedness (|sf_eval_cp|):
- equal  -0.0151 [-0.0214, -0.0093] excludes zero (1,967 games)
- slight -0.0096 [-0.0169, -0.0026] excludes zero (2,100 games)
- decided -0.0168 [-0.0245, -0.0095] excludes zero (2,429 games)
- mate   -0.0021 [-0.0307, +0.0298] contains zero (306 games)
- Signal present across contested AND decided positions — not merely a
  won-position-conversion story.

P2 — avg_elo bucket:
- under_1200 -0.0096 [-0.0207, +0.0019] contains zero (665 games)
- 1200_1600 -0.0150 [-0.0224, -0.0075] excludes zero (1,349 games)
- 1600_2000 -0.0140 [-0.0224, -0.0064] excludes zero (1,335 games)
- 2000_plus -0.0155 [-0.0312, -0.0001] excludes zero (329 games)
- No strong skill-dependence pattern; magnitudes similar across bands.

P3 — min-clock bucket WITHIN move_30+move_40 (key constraint test):
- under_60s -0.2541, 228 games — BELOW CI THRESHOLD, descriptive only
- 60_180s   -0.0534 [-0.0717, -0.0335] EXCLUDES ZERO (616 games)
- over_180s -0.0074 [-0.0136, -0.0014] excludes zero (1,582 games)
- Within late game, the signal is ~7x larger where remaining time is low
  (60-180s vs >180s), with a very large descriptive point delta under 60s.
  The clock signal localizes to actual time scarcity, not just game length.
  Consistent with time-pressure relevance. Predictive association only.

Exploratory:
- Clock imbalance: balanced -0.0006 [cz]; moderate -0.0061 [excl];
  large -0.0442 [excl] — graded with imbalance size.
- Terminal sensitivity: delta identical with/without 44 terminal rows
  (-0.0138 both) — result robust to terminal positions.

Confounding diagnostic (mandatory): marginal clock x checkpoint cross-tab
confirms low clock is almost entirely a late-checkpoint phenomenon
(move_10: 3,674/3,678 rows >180s) — why marginal clock buckets are not
primary.

Caveats:
- Predictive associations; not causal; reasoning quality not measured.
- Slices localize one already-confirmed effect; not independent hypothesis
  tests; no multiple-comparison correction claimed.
- Degradation curves not established by ordered-bucket patterns.
- Stockfish eval is position context, not ground truth.
- under_60s cell descriptive only (228 games).
- Test split untouched. Player-level leakage unresolved. DRAW not solved.

Artifacts: data/processed/constraint_slices_2024_09_250k_v1.json (gitignored);
committed report reports/constraint_slices_2024_09_250k_v1.md.

Next step:
Candidates: cross-month/pilot-disjoint external validity for the localized
finding; under_60s cell needs a larger sample (or longer games) to reach CI
threshold; GBM diagnostic at 45k train rows; player-leakage quantification.

---

## EXP-011 — Phase 9.3B Cross-Month Replication

Experiment ID: EXP-011
Date: 2026-06-11
Owner: Malachi Wang
Status: complete

Question:
Do the 2024-09 findings (EXP-009 overall clock effect; EXP-010 late-clock
localization) replicate on a fully separate month?

Design:
- dataset_id: lichess_ten_zero_2024_10_250k_v1 / 2024_10_250k_v1
- Source: lichess_db_standard_rated_2024-10.pgn.zst, deterministic first
  250,000 raw games — fully disjoint from all 2024-09 data (Design B from
  the 9.3A audit; no skip-offset parser work).
- Same pipeline, model definitions, slice definitions (fixed since 9.2A,
  not tuned on 2024-10 results), seeds (splits + bootstrap seed=42).

Dataset:
- 24,908 600+0 games -> 24,801 clean -> 23,496 broad games -> 62,839
  primary positions; splits 43,946/9,442/9,451 rows (16,447/3,524/3,525 games)
- Month comparison: avg_elo within 5 Elo of 2024-09; DRAW rate identical
  (6.1%); termination mix similar; ~4% fewer 10+0 games in first 250k.
- Stockfish 18 depth=12: 62,839/62,839 (100%), 0 failures, 1,626 s;
  299 terminal sf_depth=0 rows; Lichess overlap sign agreement 95.5%.

PRIMARY RESULT — overall E3->E4 (val, paired game-level bootstrap):
- 2024-10: -0.0120, 95% CI [-0.0177, -0.0062] — EXCLUDES ZERO
- 2024-09 reference: -0.0138 [-0.0186, -0.0091]
- Verdict: REPLICATED. Same direction, overlapping CIs, point estimates
  within 0.002.

Per-checkpoint (pattern reproduces):
- move_10 -0.0002 [cz], move_20 -0.0005 [cz],
  move_30 -0.0218 [excl], move_40 -0.0625 [excl]

P3 late-clock localization (within move_30+40): REPLICATED
- under_60s -0.2468 (241 games, descriptive; 2024-09: -0.2541)
- 60_180s   -0.0442 [-0.0636, -0.0242] EXCLUDES ZERO (2024-09: -0.0534)
- over_180s -0.0066 [-0.0133, +0.0007] contains zero narrowly
  (2024-09: -0.0074 barely excluded — boundary cell flips at the
  resolvability edge; gradient low-clock >> high-clock reproduces)

Other results:
- All five pairwise deltas exclude zero again (E1->E3 -0.0068, E4->E5
  -0.0042, B3->E1 -0.1018, B3->E5 -0.1248).
- Baselines within ~0.002 of 2024-09 (B3 0.8549 vs 0.8533).
- P1: equal/decided exclude zero; slight at the boundary (contains this
  month). P2: middle rating bands exclude zero; 2000_plus descriptive
  (277 games). Imbalance graded; terminal sensitivity: delta unchanged.

Caveats:
- Predictive associations; not causal; reasoning quality not measured.
- Two adjacent months, one platform, one time control — external validity
  beyond these months is not proven.
- Stockfish eval is position context, not ground truth. Degradation curves
  not established. DRAW not solved (575/9,442 val rows). Player-level
  leakage unresolved. Test split untouched.

Artifacts (gitignored): all *_2024_10_250k_v1 under data/. Committed:
cross_month_replication / eval_conditioned_modeling / constraint_slices
2024_10_250k_v1 reports + phase report.

Next step:
The clock signal now stands on two independent months. Candidates:
pooled-month analysis to push under_60s past the CI threshold
(pre-specified pooling rule required); player-level leakage quantification;
GBM diagnostic at ~44k train rows; Phase 10 feasibility audit only after
Malachi decides the replication program is sufficient.

---

## EXP-012 — Phase 11.0A/11.0B Prior-Work Verification and v11 Roadmap Application

Experiment ID: EXP-012
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (documentation/research-planning milestone; no models trained)

Question:
Is the v11 research arc's novelty lane (eval-controlled clock residuals on human game
outcomes + sharpness moderation program) actually open, given prior work?

11.0A verification result:
- All eight required source areas verified directly (web search + abstract/PDF fetch).
- KILL CONDITION NOT TRIGGERED: no prior work performs eval-controlled, outcome-level
  clock-residual decomposition or moderation.
- Nearest neighbors: Anderson/Kleinberg/Mullainathan (move-level narrowness->error,
  tablebase domains; key comparison paper); Barthelemy arXiv:2505.03251 (descriptive
  engine-narrowness/entropy vs human struggle/think time — closest sharpness neighbor;
  mandatory Phase 14 citation); ChessMimic arXiv:2606.04473 (blitz outcome AUC 0.78,
  material-based baselines, no eval control — "reference point, not ceiling").
- New caution adopted: jk_182 (descriptive, 3+0) reports inaccuracy rates DECREASE at
  low clock — Phase 15 curves pre-accept non-monotone shapes.

11.0B application (doc-only):
- 11.0A §9 edits folded into docs/roadmap_rescope_v11_draft.md (Chessformer -> ICLR 2026
  poster; Maia-2 -> NeurIPS 2024; Maia4All ID flagged; nearest-prior-art citation
  obligations in Phase 14; jk_182 caution in Phase 15; novelty-lane prior-art sentence).
- ROADMAP.md pointer section replaced with active v11 arc status (Phases 11-17 next;
  Phase 10/sequence models remain gated; Phases 0-9 historical record unchanged;
  "package first" reconciled into Phase 17 after claim hardening).
- docs/RELATED_WORK.md created from the verified 11.0A source table.
- PREREGISTRATION.md v1 stub created: frozen E3/E4 anchors (-0.0138 / -0.0120 with CIs),
  four primary future contrasts (E4a->E4b/E4c; board-decided-only E3->E4; sharpness
  difference-of-deltas; next-move expected-score loss ~ clock), split/evaluation
  discipline, anti-overclaiming language, revision policy.
- Standing rules adopted (Malachi approval defaults): Tier A/B sharpness discipline;
  EXP-012+ numbering for the new arc; labeled-preprint citation policy; advantaged-
  player conversion sharpness as Phase 14 headline orientation; simple-trade excluded
  from v1 composite.

Caveats:
- No new data, models, or metrics in this milestone.
- Maia4All exact arXiv identifier not yet pinned (flagged in RELATED_WORK.md).
- PREREGISTRATION.md is a stub; 11.1A refines it before any Phase 12+ feature exists.

Next step:
11.1A — Scientific Claim Audit + PREREGISTRATION v1 refinement.

---

## EXP-013 — Phase 11.1A Scientific Claim Audit + PREREGISTRATION v1 Refinement

Experiment ID: EXP-013
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (documentation/audit milestone; no models trained)

Question:
Is PREREGISTRATION.md specific enough to lock the v11 arc's primary contrasts before
any Phase 12+ feature exists?

Stub audit verdict: NOT specific enough — six gaps closed:
central-claim section absent; contrasts unstructured; no metric conventions; split
discipline missing train-defined-bins / cross-month-independence / no-raw-usernames
rules; exploratory list incomplete; revision policy underspecified.

Refinement applied (PREREGISTRATION.md stub -> v1):
- Central scientific claim locked (current supported claim + future v11 hypothesis,
  with standing qualifiers).
- Four primary contrasts locked with question/comparison/metric/datasets/success:
  C1 E4a->E4b->E4c rich clock robustness (Phase 12, both months);
  C2 board-decided-only E3->E4 vs all-games (Phase 11.2; >= ~half magnitude guideline;
  collapse -> honest flagging-channel re-frame);
  C3 sharpness moderation difference-of-deltas (Phase 14; late checkpoints;
  Tier A engine-side only; advantaged-player conversion headline orientation;
  kill condition restated);
  C4 next-move expected-score loss ~ clock bucket (Phase 15; prior-trajectory control
  mandatory; non-monotone shapes reportable per jk_182 caution).
- Deferred parameters named, not silent: 14.2A (composite, pooled analysis),
  15.0A (loss definition, bins, blunder threshold) — these may finalize parameters
  but not alter intended contrasts.
- Metric conventions: log loss primary (outcomes); expected-score loss primary
  (move quality); clipped cp secondary; raw cp eval-band-conditioned only; percent
  swing exploratory; draws=0.5; mate-band separate; cp lineage preserved; WDL parallel.
- Split discipline: train-defined bins/thresholds only; cross-month = independent
  validation; player-clustered checks once 11.3 lands; no raw usernames ever committed.
- Revision policy: pre-implementation changes logged; post-implementation primary
  definitions immutable against observed results; deviations documented beside
  preserved originals; new contrasts need new sections before results viewed.

Caveats: no new data or models; open parameters listed in the phase report carry to
their designated lock-in tickets.

Next step:
11.2A — Termination Decomposition Feasibility Audit (feeds locked Contrast 2).

---

## EXP-014 — Phase 11.2A Termination Decomposition Feasibility Audit

Experiment ID: EXP-014
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (read-only feasibility audit; no models trained, no data written)

Question:
Can the pipeline separate time-forfeit from board-decided outcomes to test locked
Contrast 2 (board-decided-only E3->E4 clock residual)?

Verdict: FEASIBILITY LEVEL 0-1 — proceed to 11.2B with existing artifacts only.
- termination + is_time_forfeit already in both months' feature tables (parsed from
  raw, preserved by cleaning, never used as model features).
- Raw vocabulary (250k prefixes, counted): Normal / Time forfeit / Abandoned /
  Unterminated / Rules infraction. Clean 600+0 set: only Normal / Time forfeit /
  Rules infraction (Abandoned excluded by cleaning; 1 Rules infraction game/month).
- Time-forfeit games hold 13.1% of primary rows in BOTH months.
- E3/E4 predictions reusable via (game_id, selected_position_type) join; primary
  11.2B design = prediction-side filter of frozen models, NO retraining.

Sample sizes (val, measured):
- Board-decided retains 87.6% (09) / 86.8% (10) of val rows.
- Late 60_180s board-decided: 464 g (09) / 424 g (10) — above 300-game CI threshold;
  carries the localization conclusion.
- Late under_60s board-decided: 101 g / 94 g — descriptive only; cell loses ~57% of
  games to the TF filter (low-clock cells are heavily time-forfeit-composed — the
  channel question is real).

Taxonomy: primary binary time_forfeit vs board_decided; descriptive channels
time_forfeit / normal_decisive (mate OR resignation — not separable) / normal_draw /
rules_infraction footnote. No unknown-handling needed (clean set excludes Abandoned).

Found: PREREGISTRATION.md C2 wording inconsistency ("same frozen models, refit") —
must be clarified before 11.2B (primary = prediction-side filter; refit = optional
secondary), permitted under the revision policy with logging.

Caveats: timeout is partly cognitive consequence, not purely mechanical; board-decided
low-clock games are a survivor population; Normal mixes mate/resignation; nothing here
is causal; player clustering separate (11.3).

Next step:
11.2B — Termination Decomposition Implementation (Recommendation A).

---

## EXP-015 — Phase 11.2B Termination Decomposition (Contrast C2)

Experiment ID: EXP-015
Date: 2026-06-12
Owner: Malachi Wang
Status: complete

Question (locked C2):
Does the replicated E3->E4 clock residual survive removal of time-forfeit games,
or is it mostly mechanical flagging/timeout risk?

Design (as pre-registered, after logged pre-implementation wording clarification):
- Prediction-side filter of FROZEN all-games E3/E4 validation predictions.
- NO retraining. Join by (game_id, selected_position_type) to feature-table
  termination columns. Paired game-level bootstrap, 1,000 reps, seed=42.
- Channels: binary time_forfeit vs board_decided; descriptive normal_decisive
  (mate OR resignation, not separable) / normal_draw / rules_infraction (1/month).

RESULT — the board-decided residual COLLAPSES (replicated):
- 2024-09: all -0.0138 [-0.0186,-0.0091]; board-decided +0.0010 [-0.0029,+0.0049]
  contains zero (retained fraction 0.07); time-forfeit -0.1183 [-0.1423,-0.0978].
- 2024-10: all -0.0120 [-0.0177,-0.0062]; board-decided +0.0060 [+0.0015,+0.0109]
  EXCLUDES zero in the POSITIVE direction (sign-reversed; fraction 0.50 overstates);
  time-forfeit -0.1305 [-0.1525,-0.1091].
- Late-clock board-decided: 60_180s -0.0294 excl (09) but -0.0061 cz (10) — the
  localized board-decided residual does NOT replicate. under_60s flips to ~+0.17 in
  BOTH months (descriptive, ~100 games): among flagging survivors, clock features
  actively mislead.

Interpretation (pre-registered collapse branch; predictive language only):
The replicated clock residual is substantially attributable to the time-forfeit/
flagging channel. The project now quantifies the flagging channel rather than
demonstrating a board-outcome clock residual. Central claim re-framed in
reports/termination_decomposition_combined.md section 8.

Caveats: filtering induces selection bias; board-decided low-clock games are a
survivor population; timeout is partly a consequence of earlier time expenditure,
so the decomposition bounds but does not perfectly separate channels; not causal;
not a degradation curve.

Implementation: termination_decomposition.py + 39 tests (1,524 total passing).
One sign-guard bug in interpretation logic found and fixed during implementation,
before reports were finalized.

Next step:
Claim-reframing audit BEFORE 11.3A: revisit v11 novelty lane and C3/C4 framing
(candidates: flagging-risk as explicit object; finer board-decided analysis;
pivot weight to the C4 move-quality bridge, which does not depend on outcome deltas).

---

## EXP-016 — Phase 11.2C Claim Reframing After Termination Decomposition

Experiment ID: EXP-016
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (documentation/reframing audit; no models trained)

Trigger:
11.2B (EXP-015) fired the pre-registered C2 collapse/reframe branch — the all-games
E3->E4 clock residual replicated, but the board-decided-only residual collapsed
(2024-09 +0.0010 cz) / sign-reversed (2024-10 +0.0060 positive); time-forfeit games
carry the signal (-0.118/-0.131). The residual is substantially the flagging channel.

Reframing applied (documentation-only):
- Central claim revised: the replicated clock residual is primarily a time-forfeit /
  flagging channel, not a board-decided outcome signal. Whether low clock relates to
  board-PLAY quality is now open and must be tested directly via next-move quality
  (Contrast C4), not inferred from outcome residuals.
- What remains supported: all-games residual real/replicated/predictive; strongest at
  low clock because clock predicts flagging risk; a real human-constraint outcome
  channel measured and replicated (but primarily flagging).
- What is weakened: the outcome residual is NOT evidence of worse board-decided
  outcomes after eval+rating control; the "clock as board-play/cognitive signal"
  reading is unsupported; late low-clock board-decided localization did not replicate.
- C3 split: C3a flagging-risk sharpness moderation; C3b board-decided-outcome
  (cautious/secondary); C3c move-quality sharpness moderation (recommended central).
- C4 elevated: directly measures next-move expected-score loss; does NOT depend on the
  outcome residual surviving board-decided filtering; now the central board-play test.

Docs edited: PREREGISTRATION.md (Post-11.2B status; C2 completed; C3->C3a/b/c; C4
elevated; revision log), ROADMAP.md (reframing + reorder), docs/roadmap_rescope_v11_
draft.md (Section 0 note; C2 result; Phase 14 split), docs/RELATED_WORK.md
(move-quality prior work more central), phase_11_2c report.

Next step:
15.0A — Move-Quality Curve / Constraint Atlas Audit, MOVED EARLIER (it directly tests
board-play quality; it is a feasibility/compute audit robust to later split changes).
11.3A/11.3B player-leakage hardening reordered to follow 15.0A but still required
before any C4 primary modeling result (15.1B); they also gain the job of checking
whether player leakage inflates the flagging-channel estimate.

---

## EXP-017 — Phase 15.0A Move-Quality / Constraint Atlas Feasibility Audit

Experiment ID: EXP-017
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (read-only feasibility/design audit; no models, no Stockfish, no data written)

Question:
Can the project measure next-move quality loss (the Constraint Atlas) directly, rather
than inferring board-play quality from final outcomes (which 11.2B showed is mostly the
flagging channel)?

Verdict: FEASIBLE, Level 1-2.
- No FEN or played move stored in any processed artifact (only irreversible fen_hash);
  sf_eval stored cp/mate only (no best move, no WDL, no MultiPV).
- BUT raw PGN caches present locally (data/raw/lichess/lichess_2024_{09,10}_first250k.pgn,
  583 MB each, gitignored) and stockfish_eval.reconstruct_fen_at_ply already replays
  mainline moves to a target ply -> post-move FEN is one extra board.push().
- 98.5% of primary checkpoints (64,371/65,368 in 2024-09) have a next move; 997 games
  ended at the checkpoint (excluded by definition, reported). By checkpoint: move_10
  24,384 / move_20 19,639 / move_30 12,950 / move_40 7,398.
- KEY: the checkpoint sf_eval_cp is already the engine best-line (analyse) value, so
  engine-best-relative loss needs ONLY a post-move eval pass (no best-move search/MultiPV).

Recommended primary metric: expected-score loss, mover's perspective,
  loss = max(0, ES_best_before - ES_after_actual), draws = 0.5, mate-band separate.
  Cheap first metric = clipped-cp loss (same structure, cp scale, clip +/-1000).
  cp-based E3/E4 lineage preserved separately; percent swing avoided.
cp->ES: train-fit transform (route b, portable) default; engine WDL (route a) as
  robustness. Fit on train only.
Depth-parity caveat: pre-move (mover, d12) vs post-move (opponent, d12) -> handle +
  sensitivity-check (recommend both d12 with documented parity caveat + d13 spot check).

Compute: ~28 ms/position (8.1 throughput) -> ~30 min/month post-move pass, ~1h both
months; <5 MB/month artifact. Pilot one month / --limit first; full pass gated on
explicit approval (8.1B/9.x gate). Checkpoint rows only first; MultiPV deferred to Phase 14.

Bins: late-clock under_60s/60_180s/over_180s (proven, CI-bearing; under_60s descriptive);
rating 200-Elo or existing 4 buckets for CIs; eval bands equal/slight/decided/mate-band;
phase move_10..40 + late group; termination channels never silently mixed; medians +
75/90th percentiles for skew; game-clustered bootstrap CIs.

Staging vs 11.3A/B: 15.0A safe now; 15.0B extraction safe before 11.3A/B (per-position
targets, no models); 15.1A/B controlled modeling waits for 11.3A/B or player-clustered/
disjoint design.

Caveats: not causal; no degradation-curve language; Stockfish not absolute ground truth;
survivorship in board-decided low-clock cells; skewed loss distributions; sharpness
difficulty not novel (Anderson/Barthelemy); DRAW not solved.

Next step:
15.0B — Checkpoint-Level Next-Move Loss Extraction (may precede 11.3A/B; full Stockfish
post-move pass gated on explicit approval, pilot first).

---

## EXP-018 — Phase 15.0B Checkpoint-Level Next-Move Loss Extraction (pilot)

Experiment ID: EXP-018
Date: 2026-06-12
Owner: Malachi Wang
Status: complete (implementation + pilot; full pass gated, not run)

Purpose:
Build the measurement layer for Contrast C4 — per-checkpoint next-move quality loss
(mover's perspective) — to test board-play quality directly rather than infer it from
final outcomes (which 11.2B showed is mostly the flagging channel).

Implementation:
- next_move_loss.py: reconstructs post-move FEN from the local raw PGN cache (one
  board.push() past the checkpoint, reusing stockfish_eval replay/index/engine helpers,
  unmodified); evaluates ONLY the post-move position (checkpoint sf_eval_cp is already
  the engine best-line value -> no best-move search, no MultiPV).
- Metric: clipped cp loss, mover's perspective, cp_loss = max(0, mover_pre_cp -
  mover_post_cp), cap +/-1000. Expected-score loss DEFERRED to 15.0C/15.1A (train-fit
  transform; no placeholder shipped).
- Mate-band rows flagged + excluded from cp summaries. Full-run gated
  (--limit / --allow-full-run); refuses full pass by default.
- 41 tests; full suite 1,565 passing (+41), 0 regressions.

Pilot (2024-09, --limit 1000):
- 982 OK, 18 no-next-move, 0 fen errors, 0 engine errors, 0 FEN-hash mismatches
  (reconstructed checkpoint FENs match stored hashes exactly), 378 games indexed.
- runtime 19.6s -> est full month ~21 min (both months ~42 min; 8.1 throughput ~28
  ms/pos). Consistent with 15.0A estimate.
- Clipped cp loss (OK non-mate-band, n=943): mean 58.1, median 24, p90 161,
  zero-loss 29.4%, >100cp 19.1%. 39 mate-band OK rows excluded. By checkpoint:
  move_10 377 / move_20 294 / move_30 192 / move_40 119.
- Structural note: at numbered checkpoints (even ply 20/40/60/80) the mover is always
  White; orientation code tested for both colors regardless.

Artifact: data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet (gitignored, not staged).

Caveats: not causal; no degradation-curve language; Stockfish depth-12 not absolute
ground truth; depth-parity (pre mover-to-move vs post opponent-to-move, both d12) flagged
for a d13 sensitivity check; board-decided low-clock = survivor population; right-skewed
loss -> medians/percentiles.

Next step:
15.0C — full both-months post-move pass (gated, explicit approval) + train-fit cp->ES
transform + depth-parity sensitivity check, then 15.1A descriptive Constraint Atlas
curves. 11.3A/B before 15.1B controlled modeling.

---

## EXP-019 — Phase 15.0C Full Next-Move Loss Extraction + Expected-Score Transform

Experiment ID: EXP-019
Date: 2026-06-13
Owner: Malachi Wang
Status: complete

Purpose:
Produce full checkpoint-level next-move loss artifacts for both months and add a
train-fit cp->expected-score transform, completing the C4 measurement layer.

Expected-score transform (Option A, implemented):
- Logistic ES(cp)=1/(1+exp(-cp_clipped/scale)), cp clipped +/-1000, fit by bounded MSE
  to White expected score (win=1/draw=0.5/loss=0) on 89,764 POOLED TRAIN rows from both
  months. scale=348.4, MSE 0.183. Train-only; same transform pre/post and both months
  for comparability; cp lineage preserved (no silent replacement); mate-band excluded.

Full extraction (--allow-full-run, depth 12, post-move position only, ES transform applied):
- 2024-09: attempted 65,368, OK 64,371, no-next-move 997, fen/engine/hash failures
  0/0/0, runtime 1,471s (~24.5 min). Clipped cp loss mean 58.3 median 19 p90 159
  zero 33.3% >100cp 17.3% >200cp 7.3%. ES loss mean 0.0345 median 0.0102 p90 0.0949
  >0.10 9.3%. mate-band (OK) 2,415.
- 2024-10: attempted 62,839, OK 61,868, no-next-move 971, failures 0/0/0, runtime
  1,419s (~23.7 min). Clipped cp loss mean 57.4 median 19 p90 157. ES loss mean 0.0341
  median 0.0101 p90 0.0933. mate-band (OK) 2,243.
- Total 126,239 checkpoint moves evaluated; cross-month agreement strong on every stat.

Depth-parity sensitivity (2024-09, 400-row depth-13 post-move re-eval via stored
post_fen): mean clipped cp loss 57.8 (d12) vs 58.0 (d13); per-row mean abs delta 14cp;
median delta 0. Benign in aggregate; depth-12 retained.

Descriptive observation (NOT a claim): board-decided vs time-forfeit games have
near-identical checkpoint next-move loss in both months (clipped cp means within ~1cp;
ES means within 0.0009) -> consistent with the 11.2B flagging-channel reframing (the
outcome residual is clock-exhaustion mechanics, not worse board moves at checkpoints).
No conclusion until Atlas curves + controls.

Tests: 56 in test_next_move_loss.py (+15 ES); full suite 1,580 passing, 0 regressions.
Artifacts (gitignored): next_move_loss_{2024_09,2024_10}_250k_v1.parquet,
next_move_expected_score_transform_2024_09_2024_10_v1.json.

Caveats: not causal; no degradation-curve language; Stockfish depth-12 not absolute
ground truth; survivorship in board-decided low-clock; right-skewed loss; ES is
logistic-on-clipped-cp (WDL cross-check deferred).

Next step:
15.1A — Constraint Atlas Descriptive Curves Audit. 11.3A/B before 15.1B controlled modeling.

---

## EXP-020 — Phase 15.1A Constraint Atlas Descriptive Curves Audit

Experiment ID: EXP-020
Date: 2026-06-13
Owner: Malachi Wang
Status: complete (read-only audit/design; no models, no Stockfish, no data written)

Question:
How should the Constraint Atlas descriptively summarize next-move loss across clock,
rating, eval, phase, and termination channel without misleading marginal curves or
causal language?

Artifact integrity (read-only): 15.0C artifacts CLEAN, no repair needed.
- 2024-09: 65,368 total / 64,371 ok / 997 no-next-move; 2024-10: 62,839 / 61,868 / 971.
- 0 duplicate (game_id, selected_position_type); 0 nulls in headline metrics
  (expected_score_loss, clipped_cp_loss, cp_loss, es_pre/post, mover_pre_cp,
  mover_clock_s, mover_rating, time_bucket, split_set); 33 cols; counts match 15.0C.
- mover_color always White (numbered even-ply checkpoints) -> Atlas describes
  White-to-move decision quality (documented scope limitation, not a defect).

Design decisions:
- Headline metric: expected-score loss (mover perspective) mean+median+p75/p90 +
  large-loss probs (ES>0.05, ES>0.10); clipped cp loss secondary; mate-band excluded;
  month-by-month then combined; all-games AND board-decided side-by-side.
- Clock: coarse under_60/60_180/over_180 bucketed WITHIN checkpoint. Marginal clock
  curves FORBIDDEN (confound: move_10 99.96% over-180s; low clock only at move_30/40).
  Finer <10/10-30/30-60/60-180/>180 exploratory within late group (sub-300 descriptive).
- Rating: 200-pt bins / quantiles for CI cells across ~800-2199 (range 422-2709, median
  1601); tails descriptive; 100-pt only smoothed pooled.
- Eval bands: near_equal(<=100)/slight(100-300)/clear(300-700)/decided(700-1000, fold
  the 226 >1000 rows in); mate_band separate.
- Phase: per-checkpoint + late group (move_30+40); never collapse without phase-conditioning.
- Termination: always show composition; all-games vs board-decided side-by-side;
  time-forfeit a distinct population; re-examine the 15.0C coarse board-decided≈
  time-forfeit observation STRATIFIED before any reading.
- Cell rules: n<50 hidden; 50-300 descriptive no-CI; >=300 CI-bearing; GAME-level
  bootstrap (multiple checkpoints/game); player-clustered deferred.

Staging: 15.1B descriptive curves MAY proceed before 11.3A/B if descriptive,
month-replicated, game-level bootstrap, no player-level/causal claims. Controlled
modeling (15.1C/15.2B) waits for 11.3A/B.

Repair needs: NONE. Artifacts sufficient for 15.1B. Black-to-move checkpoints a possible
future sampling extension, not a prerequisite.

Caveats: descriptive only; not causal; no degradation-curve language; Stockfish depth-12
not absolute ground truth; survivorship in board-decided low-clock; right-skewed loss;
White-to-move scope.

Next step:
15.1B — Constraint Atlas Descriptive Curves Implementation. 11.3A/B before 15.1C/15.2B.

---

## EXP-021 — Phase 15.1B Constraint Atlas Descriptive Curves

Experiment ID: EXP-021
Date: 2026-06-13
Owner: Malachi Wang
Status: complete (descriptive readout; no models, no Stockfish, no data written)

Purpose:
Descriptively summarize next-move loss (expected-score loss, mover perspective) across
clock/rating/eval/phase/termination using the 15.0C artifacts. Measurement, not modeling.

Implementation:
- constraint_atlas.py: pure bins (clock coarse/fine, 200-pt rating, eval bands
  near_equal/slight/clear/decided/mate_band, termination channel), cell-count policy
  (n<50 hidden / 50-300 descriptive / >=300 ci_ok), game-level clustered bootstrap on
  headline late cells, month + combined markdown reports, CLI. result_class optional
  (not in artifact; binary board_decided/time_forfeit via is_time_forfeit unaffected).
- 55 tests; full suite 1,635 passing, 0 regressions. Markdown tables only (no plots, no
  data writes).

Key descriptive findings (BOTH months unless noted):
1. Overall mean ES loss ~0.034, median ~0.010 (right-skewed); median clipped cp 19.
2. NO clean clock gradient among CI-bearing cells: late-group fine-clock cells flat
   (30-60s/60-180s/over-180s all ~0.028-0.031) in both months.
3. Apparent low-clock bump (2024-09 <10s ES 0.042) DOES NOT REPLICATE (2024-10 <10s
   0.028) -> sparse-cell artifact (n~90, descriptive-only). Pre-accepted per 15.1A /
   jk_182 non-monotonicity caution.
4. STRONG REPLICATED eval-band pattern (late, over-180s): ES loss peaks near_equal/slight
   (09: 0.0345/0.0414; 10: 0.0322/0.0396), lowest decided (0.0168/0.0148). Decided
   positions have little expected score left to lose. Eval-band conditioning dominates.
5. Time-forfeit checkpoint loss slightly above board-decided in CI cells (descriptive;
   survivor-population caveat).

Replication: overall stats agree closely across months; the no-gradient and eval-band
patterns replicate; the low-clock bump does not.

Caveats: descriptive/not causal; no degradation-curve language; Stockfish not absolute
ground truth; White-to-move scope (even-ply checkpoints); survivorship in board-decided
low-clock; right-skew (medians/quantiles); DRAW sparse; sharpness not implemented/invoked.
Not "not merely flagging" — that is a controlled question.

Next step:
11.3A — Player-Disjoint / Player-Clustered Feasibility Audit (before controlled C4
modeling 15.1C and sharpness moderation 15.2B). Controlled models MUST condition on eval
band (it dominates) and treat low-clock cells cautiously.

## EXP-022 — Phase 11.3A Player-Disjoint / Player-Clustered Feasibility Audit

Experiment ID: EXP-022
Date: 2026-06-13
Owner: Malachi Wang
Status: complete (read-only audit; no code/data changes; no models; no Stockfish; no
usernames written/printed/committed — all player work via in-memory salted hashes)

Purpose:
Quantify player-repetition dependence and decide the hardening route (strict player-disjoint
split vs player-clustered uncertainty) required before controlled C4/C3 modeling.

Player identifier availability:
- Raw PGN headers carry raw usernames (White/Black) + Site slug = game_id; optional
  WhiteTitle/BlackTitle == "BOT". Usernames STRIPPED at parse (DATA_POLICY.md), absent from
  every processed artifact (game records, features, E3/E4 preds, next-move-loss). No hashed
  ID exists yet. Recoverable via game_id join (100% of primary game_ids matched in raw cache,
  both months). No anonymous/"?"/empty players; bot-involved primary games 12 (09) / 7 (10).

Current split design + leakage:
- split_unit = game_id (StratifiedShuffleSplit, seed 42, 0.70/0.15/0.15, stratify
  result_class). Prevents game leakage; does NOT prevent player leakage / repeated-player
  dependence / cross-month dependence.

Concentration (primary game sets, salted hashes):
- 09: 24,520 games, 17,116 players, median 2 games/player, p90 6, max 36; top10% players ->
  33.0% game-appearances, top10% mover-players -> 29.5% checkpoint rows.
- 10: 23,496 games, 17,209 players, median 2, max 32; top10% -> 33.1% / 29.6%. Stable across
  months; moderate (no single account dominates).

Cross-month overlap:
- 3,346 players in both months (~19.5% of 09, 19.4% of 10); ~40% of each month's checkpoint
  rows involve a cross-month player -> strong but not fully independent replication.

Train/val/test overlap (HEADLINE RISK):
- Players spanning >1 split: 39.8% (09) / 37.8% (10). Games touching a multi-split player:
  86.8% / 85.3%. Rows touching: 86.5% / 85.0%. Players in BOTH train and test: 4,223 / 3,982.

Strict player-disjoint feasibility (player-game graph, union-find):
- Giant component holds 92.0% games / 86.0% players (09), 92.6% / 85.1% (10), 94.6% / 89.1%
  (pooled). Strict 3-way disjoint split INFEASIBLE (component assignment forces ~92% into one
  split; edge-cut discards most games). Player-disjoint held-out slice possible but costly.

Recommendation:
- Option A — hashed player IDs in ignored artifacts only + player-clustered (mover-player /
  two-way) bootstrap, generalizing existing game-cluster machinery (bootstrap_ci.py,
  constraint_atlas.bootstrap_mean_es_ci, termination_decomposition). Re-verify 11.2B
  termination deltas (likely survive — large effect vs moderate concentration) and 15.1B
  eval-band headline under player clustering. NOT Option B (giant component).

Next step:
11.3B — Player Metadata Extraction + Clustered-Bootstrap Implementation (Option A). Required
before controlled C4 modeling (15.1C) and C3 sharpness moderation (15.2B).

## EXP-023 — Phase 11.3B Player Metadata Extraction + Clustered Uncertainty

Experiment ID: EXP-023
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (implementation; no models trained, no Stockfish, no existing artifacts
modified; player metadata artifacts gitignored; no raw usernames stored/printed/committed)

Purpose:
Implement player-clustered uncertainty (11.3A's recommended hardening, since strict
player-disjoint splitting is infeasible) and re-check whether the 11.2B termination and 15.1B
atlas headline findings survive repeated-player dependence.

Implementation:
- player_metadata.py: normalize (strip/lower) + blake2b one-way hash (non-secret pepper),
  PGN header parser, raw-PGN locator, hashed-ID joins (white/black + mover/opponent), CLI.
  Output frame = hashes + bot flags + version_tag only; assert_no_raw_usernames guard.
- clustered_uncertainty.py: validate_cluster_key, clustered_mean_ci, clustered_mean_diff_ci,
  clustered_paired_delta_ci (configurable cluster key; game_id reproduces game-level), plus
  termination + atlas rerun report generators and a CLI. One-way clustering; two-way
  White×Black deferred (reports the wider of White/Black as conservative).
- 21 + 15 module tests; full suite 1,671 passing (+36), 0 regressions.
- Extraction: 250k games/month, 108,642 / 112,556 unique players, 634 / 434 bot games, 0
  anonymous; 100% join coverage onto primary 600+0 frames.

CORRECTNESS ANCHOR: game-clustered paired delta reproduces the published 11.2B CIs to 4 dp
(2024-09 all-games −0.0138 [−0.0186,−0.0091]; 2024-10 board-decided +0.0060 [+0.0015,+0.0109]).

Key results (1000 replicates, seed 42):
- 11.2B termination SURVIVES clustering. Time-forfeit: 09 −0.1183, 10 −0.1305, CI excludes
  zero under game/White/Black clustering. Board-decided: 09 +0.0010 (contains 0), 10 +0.0060
  (small, sign-reversed) — no board-decided residual rescued. All-games stays negative,
  excludes zero. Player CIs only modestly wider than game CIs (moderate concentration).
- 15.1B atlas eval-band SURVIVES mover-player clustering. Mean ES loss: near_equal ~0.034,
  slight ~0.042 (peak), clear ~0.031, decided ~0.018 (lowest), both months, all CIs exclude
  zero. Pairwise slight−decided +0.024 / near_equal−decided +0.016 exclude zero both months.
  Late coarse-clock cells flat (under_60/60_180/over_180 ~0.029-0.033, overlapping CIs) -> no
  clock gradient, unchanged.

Interpretation: both headline conclusions are robust to repeated-player dependence. Flagging
channel is the substantive clock-outcome signal; eval-band conditioning dominates next-move
loss; no replicated raw clock gradient among stable cells. Predictive/descriptive only.

Caveats: one-way clustering (two-way deferred); mover-player clustering only on decision-maker;
filtering TF induces selection (not causal); pepper non-secret (hashes never leave ignored
artifacts); DRAW sparse; Stockfish eval objective context not ground truth.

Next step:
15.1C — Controlled Move-Quality Modeling Audit (eval-band-conditioned C4 modeling with
mover-player-clustered uncertainty). C3 sharpness moderation (15.2B) likewise unblocked.

## EXP-024 — Phase 15.1C Controlled Move-Quality Modeling Audit

Experiment ID: EXP-024
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (audit/design, doc-only; no models, no regressions, no Stockfish, no data
written)

Purpose:
Design the controlled C4 move-quality model before implementation: does clock retain a stable
association with next-move ES loss after conditioning on eval band, checkpoint, rating, month,
and termination, with mover-player clustering — or is eval state the robust structure?

Input audit (read-only, both months):
- Non-mate modeling base 61,956 (09) / 59,625 (10); mover_player_hash 100% coverage (0 null);
  ~12,900 unique movers; splits present; mover_rating full range no nulls.
- Target expected_score_loss: bounded [0,~0.81], right-skewed, ~33% zero-inflated, ~20% >0.05,
  ~9% >0.10. Drives model-family choice.
- Clock×checkpoint confound severe (move_10 99.96% over_180); under_60 ~750-800/mo (sparse,
  confounded) -> exploratory; 60_180 ~2,600/mo stable. eval decided ~3,000 (smallest, CI-ok).
- mover_color uniformly White -> White-to-move scope.
- statsmodels NOT installed -> use sklearn + own cluster bootstrap (no new dep).

Design decisions:
- Target: expected_score_loss (non-mate), mate-band excluded. Primary = OLS adjusted-mean +
  mover-player cluster bootstrap; secondary = large-loss logistic (ES>0.05/0.10); two-part
  deferred.
- Primary contrast: coarse clock (60_180/under_60 vs over_180) net of C(checkpoint) +
  C(eval_band, ref=decided) + rating_z + C(month) + C(termination_binary). Eval-band = positive
  control. A clock null is a pre-registered acceptable outcome.
- Interactions staged & exploratory (clock×checkpoint, clock×eval, clock×rating,
  termination×clock, month×clock), one family at a time.
- Discipline: estimate on train+val, test reserved as locked confirmation; month = replication
  (per-month then pooled); rating_z scaled on train only; inference via cluster bootstrap.
- Uncertainty: mover-player cluster bootstrap (refit per replicate, 500 reps target / 200 first
  pass, seed 42), game-clustered secondary, row-level reference only. clustered_uncertainty.py
  lacks a model-refit bootstrap -> 15.1D adds cluster_bootstrap_refit reusing _cluster_index.
- NOTE: no pre-checkpoint trajectory feature exists in the artifacts -> controls =
  eval+phase+rating+termination+month; prior-trajectory = separate future extraction ticket.

Next step:
15.1D — Controlled Move-Quality Modeling Implementation (controlled_move_quality.py + tests +
3 reports). Excludes sharpness/MultiPV/neural/cross-TC/new Stockfish. Not causal; White-to-move
scope; Stockfish eval objective context not ground truth.

## EXP-025 — Phase 15.1D Controlled Move-Quality Modeling Implementation

Experiment ID: EXP-025
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (controlled C4 modeling; no Stockfish, no outcome models, no data artifacts
modified, no new deps; nothing staged/committed)

Purpose:
Controlled C4 estimate: after conditioning on checkpoint, eval band, rating, month, and
termination with mover-player clustering, does clock retain a stable association with next-move
ES loss, or is eval state the robust structure?

Implementation:
- controlled_move_quality.py: build_model_frame (atlas loader + mover-hash join + non-mate
  filter + month/termination_binary/large-loss targets), build_design (explicit one-hot, fixed
  refs clock=over_180/checkpoint=move_10/eval=decided/termination=board_decided/month=2024_09,
  intercept col), numpy OLS (_ols_fit), sklearn logistic (C=inf, fit_intercept=False),
  per-month + pooled (month FE) + locked-test, CLI. rating_z standardized on TRAIN only.
- clustered_uncertainty.py: added cluster_bootstrap_refit (refit model per resampled-cluster
  replicate; skips/counts degenerate refits) + summarize_contrasts (percentile CIs for named
  coefs). Generic, reused by the modeling module.
- 16 module tests; full suite 1,687 passing (+16), 0 regressions. 200 bootstrap reps, seed 42,
  200/200 OLS refits; ~11s/month.

Results (adjusted ΔES loss, mover-player-clustered 95% CI):
- EVAL-BAND POSITIVE CONTROL dominant + replicated (pooled): slight +0.0286 [+0.0270,+0.0302],
  near_equal +0.0223 [+0.0205,+0.0239], clear +0.0158 [+0.0143,+0.0173] vs decided. Both months
  + test confirm. Recovers 15.1B structure.
- CLOCK association SMALL but NON-NULL + REPLICATED: 60_180 vs over_180 pooled +0.0034
  [+0.0015,+0.0051]; under_60 vs over_180 +0.0072 [+0.0042,+0.0115]. Monotone (less clock→more
  loss). Both months (09: +0.0031/+0.0080; 10: +0.0038/+0.0065) AND locked test (60_180 +0.0045,
  under_60 +0.0073) exclude zero. ~5-8× smaller than eval band.
- TERMINATION tf vs board_decided ≈ 0 after controls (pooled -0.0003, contains 0) — consistent
  with 11.2B flagging reframing (flagging = clock expiry, not worse moves).
- Logistic large-loss (log-odds) signs agree with OLS (clock + eval both raise mistake prob;
  eval far larger).

Interpretation: REFINES (not overturns) 15.1B. Descriptive marginal cells flat because eval-band
composition varies across clock; conditioning on eval band (required by 15.1A/15.1C) reveals a
small ordered clock residual. Eval state is the robust dominant move-quality structure; clock
residual small but replicated + test-confirmed. Predictive/descriptive ONLY — not causal, no
degradation-curve language, no reasoning-degradation claim. Prior-trajectory control DEFERRED
(absent from artifacts) = stated limitation.

Next step:
15.1E — Clock Association Robustness Audit (continuous mover_pre_cp vs 4 bands, residual
clock×checkpoint confounding, rating non-linearity, sparse under_60, two-way White×Black
dependence). C4 consolidation folds in after; C3 sharpness (15.2A) separate later arc.

## EXP-026 — Phase 15.1E Clock Association Robustness Audit

Experiment ID: EXP-026
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (audit/design, doc-only; no models, no regressions, no Stockfish, no data
written)

Purpose:
Stress-test the small 15.1D controlled clock association (60_180 vs over_180 ≈ +0.0034 pooled;
under_60 ≈ +0.0072) before C4 consolidation: artifact of coarse eval bands / checkpoint-clock
structure / survivor composition / rating spec / ES transform / clustering, or robust?

Empirically-confirmed live threats (read-only):
1. Within-band |cp| varies by clock bucket: slight low-clock ≈205cp vs over_180 ≈189cp;
   near_equal low-clock ≈30-38 vs ≈45 (both months) → coarse-band residual confound.
2. under_60 only 31% (09) / 36% (10) board-decided vs 86.5% overall → ~2/3 time-forfeit,
   flagging-survivor population; under_60 concentrated at move_30/40 (move_10 has 1 row).

Mandatory 15.1F checks (each reports 60_180 vs over_180 clock contrast, mover-player-clustered,
month + pooled, eval-band positive control retained):
1. Continuous abs(mover_pre_cp) eval control (+ finer cp bins) — does it drive clock→0?
2. Late-only model (move_30+40).
3. Board-decided-only model (exclude time-forfeit) — decisive move-quality test.
4. Rating-spec sensitivity (bins / quadratic).
5. Metric sensitivity (clipped_cp_loss + large-loss indicators).
6. Cluster sensitivity (mover primary; game + White/Black secondary).
Output = compact robustness matrix (check × month/pooled).

Interpretation criteria LOCKED pre-implementation:
- SURVIVES: 60_180 positive both months, pooled CI excludes 0, NOT eliminated by continuous
  eval control, board-decided-only same sign, metric direction agrees → small SECONDARY
  headline (still not causal, still eval-dominated).
- WEAKENS: eval control → ≈0 / board-decided fails / sign not replicated / metric disagrees →
  consolidate around eval-band + flagging; clock = mainly flagging predictor.
- MIXED: conditional/sensitive; do not headline clock.

Readiness: data complete, no extraction (mover_pre_cp, clipped_cp_loss, large-loss, termination,
splits, mover-hash all present). Prior-trajectory absent = stated limitation, not a blocker.
v11 draft tagged superseded-in-part; full reconciliation deferred to post-15.1F. Phase 14
sharpness stays after C4 consolidation.

Next step:
15.1F — Clock Association Robustness Implementation (mandatory matrix; locked criteria). If a
named confound (likely prior trajectory) is implicated, trajectory extraction precedes C4
consolidation; else C4 consolidation follows.

## EXP-027 — Phase 15.1F Clock Association Robustness Implementation

Experiment ID: EXP-027
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (robustness modeling; no Stockfish, no new data artifacts, no new deps, no
existing modules modified; nothing staged/committed)

Purpose:
Run the 15.1E mandatory robustness matrix on the small 15.1D clock association and apply the
locked 15.1E criteria: does 60_180 vs over_180 survive continuous eval control, late-only,
board-decided-only, rating spec, metric, and cluster variations?

Implementation:
- clock_association_robustness.py: build_variant_design (reuses 15.1D reference levels;
  adaptive checkpoint ref; optional abs_cp_z within-band control; rating linear/quadratic/
  train-quantile-bins; optional month/termination), fit_variant (OLS/logistic, chosen cluster
  key, via cluster_bootstrap_refit), 12-check mandatory specs, verdict_for_contrast +
  overall_conclusion (locked gate), matrix renderer, month+combined reports, CLI. No edits to
  controlled_move_quality.py / clustered_uncertainty.py (imported/reused).
- 18 tests incl. baseline-design-equals-cmq and baseline-contrast reproduction; full suite
  1,705 passing (+18), 0 regressions. 200 reps seed 42; combined run ~82s.

CONCLUSION: SURVIVES. Pooled 60_180 vs over_180 +0.0034 [+0.0015,+0.0052]; every mandatory
check pooled-excludes-0 and positive both months:
- continuous within-band |cp| control +0.0034 [+0.0015,+0.0052] (KEY coarse-band threat — NOT
  eliminated);
- board-decided-only +0.0034 [+0.0010,+0.0063] (isolated from flagging — survives);
- rating quantile bins +0.0032 / quadratic +0.0033; late-only pooled +0.0033;
- clipped_cp +6.09 [+2.84,+9.18]; logistic ES>0.05 +0.088 [+0.021,+0.160]; ES>0.10 +0.141
  [+0.008,+0.249] (directional, agree);
- game_id +0.0034 / White-player +0.0034 / Black-player +0.0034.
under_60 board-decided-only contains 0 (+0.0045 [-0.0013,+0.0109]) — sparse, ~2/3 TF (15.1E).
Per-month subset CIs occasionally touch 0 (low power for ~+0.003 effect); verdict rests on
pooled + consistent positive sign per locked criteria.

Interpretation: C4 clock association credited as SMALL, replicated, controlled, SECONDARY to
eval band (~5-8× larger), predictive/descriptive NOT causal. Eval-band structure remains the
dominant robust move-quality structure; outcome-level clock signal stays substantially the
flagging channel (11.2B). Main remaining alt-explanation = prior trajectory (deferred, absent
from artifacts) = stated limitation.

Next step:
15.1G — C4 Claim Consolidation / Move-Quality Arc Summary (15.1B + 11.3B + 15.1D + 15.1F).
Prior-trajectory feature extraction = candidate follow-up. C3 sharpness 15.2A separate arc.

## EXP-028 — Phase 15.1G C4 Claim Consolidation / Move-Quality Arc Summary

Experiment ID: EXP-028
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (consolidation/reporting, doc-only; no models, no regressions, no Stockfish,
no data written)

Purpose:
Consolidate the C4 / move-quality arc (11.2B → 15.1F) into a settled claim, fix allowed vs
forbidden claims, reconcile descriptive vs controlled results, and decide the prior-trajectory
question.

SETTLED C4 CLAIM (predictive/descriptive, NOT causal):
- Final-outcome clock signal = substantially flagging/time-forfeit channel (11.2B; survives
  player clustering 11.3B).
- Next-move ES loss dominated by eval state (15.1B descriptive + 15.1D controlled; replicated).
- After controls (checkpoint+eval+rating+month+termination), clock retains a SMALL replicated
  association with next-move ES loss: pooled 60_180 vs over_180 +0.0034 [+0.0015,+0.0052].
- SURVIVES all 15.1F mandatory robustness checks incl. continuous within-band cp control and
  board-decided-only (not solely a time-forfeit artifact at move-quality level).
- ~5-8× smaller than eval-band structure; replicated both months + locked test; survives
  mover/game/White/Black clustering.

Descriptive↔controlled reconciliation: 15.1B flat MARGINAL clock cells were composition-masked
(clock buckets differ in eval composition); conditioning on eval band reveals the small
residual. Not contradictory.

Allowed claims (7): flagging-channel outcome result; eval-state dominance; small replicated
controlled clock association; survives board-decided-only; secondary to eval band;
predictive/replicated; survives player clustering.
Forbidden: causes worse reasoning / cognitive degradation / low clock causes blunders /
Stockfish ground truth / DRAW solved / best human predictor / sharpness shown / trajectory
controlled / clock effect large / "not merely flagging" / unqualified degradation curve.

PRIOR-TRAJECTORY DECISION: Option A — DEFER. Original C4 prereg locked trajectory "mandatory",
but (a) deviation logged pre-results at 15.1C (absent from artifacts), (b) 15.1F discharged the
immediate confounds, (c) "mandatory" was motivated by the clock-as-symptom-of-past-struggle
confound which threatens a CAUSAL reading — and the C4 claim is explicitly descriptive/
predictive, never causal. So "mandatory" reinterpreted (deviation note) as required before any
causal/mediation C4 claim; descriptive C4 closed now with trajectory as stated headline
limitation + recommended optional follow-up. (Judgment call on a pre-registered mandatory item;
Option B = extract trajectory then re-run controlled+robustness, if a closer-to-causal claim is
wanted.)

Next step:
15.1H — Phase 15 / Roadmap Reconciliation Patch (reconcile ROADMAP.md vs v11 draft, fold in C4
claim, sequence sharpness) → 14.1A MultiPV Sharpness Feasibility/Compute Audit. Prior-trajectory
extraction = optional follow-up.

## EXP-029 — Phase 15.1H Roadmap Reconciliation Patch

Experiment ID: EXP-029
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (documentation reconciliation, doc-only; no code/tests/data/models/Stockfish;
nothing staged/committed)

Purpose:
Reconcile the roadmap docs with the post-C4 evidence chain so the project stops carrying stale
v11 promises before the sharpness arc.

Stale assumptions fixed:
- Original v11 ordering listed Phase 14 sharpness then Phase 15 move-quality as future/unexecuted
  — but Phase 15 was pulled earlier (11.2B) and C4 is now CLOSED.
- Removed/annotated any implication that the board-decided outcome residual survived, that the
  outcome signal is "not merely flagging," that prior trajectory was controlled, that the clock
  effect is large, or that sharpness moderation was shown.
- ROADMAP top sequence bullet annotated to point at the new reconciliation section.

Changes:
- ROADMAP.md: added "Post-C4 Reconciliation (Ticket 15.1H)" section (live claim; Phase 15 pulled
  earlier; C4 closed; trajectory deferred; sharpness not shown / feasibility-first; Phase 12/13
  non-blocking backlog; updated reframed sharpness sequence 14.1A→14.1B→14.2A→14.2B→14.3B). Marked
  15.1H complete, next = 14.1A.
- docs/roadmap_rescope_v11_draft.md: supersession note updated (15.1E→15.1H; C4 consolidated;
  retained as historical context only).
- PREREGISTRATION.md: added sharpness pre-arc status (untested; 14.1A feasibility first; fresh
  14.2A pre-registration required before any sharpness modeling; C3a/C3b/C3c split stands, C3c
  first target).

Live claim (predictive/descriptive, NOT causal): outcome clock signal = substantially flagging;
next-move ES loss dominated by eval state; small replicated robust SECONDARY controlled clock
association after controls; prior trajectory deferred limitation.

Prior-trajectory: deferred (Option A, 15.1G); required only before a causal/mediation claim.
Sharpness: not shown; needs MultiPV features + fresh pre-registration.

Next step:
14.1A — MultiPV Sharpness Feasibility / Compute Audit. Prior-trajectory feature-extraction
audit/impl = optional follow-up if a closer-to-causal C4 statement is later desired.

## EXP-030 — Phase 14.1A MultiPV Sharpness Feasibility / Compute Audit

Experiment ID: EXP-030
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (feasibility/design audit; read-only inspection + a tiny 30-position MultiPV
smoke benchmark that wrote NO persistent artifact; no bulk engine job; no models; nothing
staged/committed)

Purpose:
Audit whether MultiPV sharpness extraction is feasible and define the v1 sharpness feature set,
orientation, schema, pilot, and compute gate before any implementation.

Engine/MultiPV feasibility:
- stockfish_eval.py is single-PV (engine.analyse(board, Limit(depth))). MultiPV is a one-line
  change: pass multipv=K to analyse() -> list of K info dicts ordered best-first for the mover.
  CAVEAT (confirmed in smoke): do NOT engine.configure({"MultiPV":K}) -> raises "cannot set
  MultiPV which is automatically managed". Reuse score_to_white_pov + _fen_hash; add a relative
  (mover-POV) extractor. Depth-12 keeps semantics consistent with 15.0C single-PV.

Checkpoint universe (read-only):
- Both months: 126,239 OK checkpoints, 121,581 OK non-mate, 4,658 mate-band. By checkpoint
  ~24k/19k/13k/7k (move_10/20/30/40) per month. **pre_fen stored DIRECTLY** -> no raw-PGN
  reconstruction. fen_hash + pre_sf_eval_cp present for validation. Dedup negligible (~0.1%).

Compute (30-pos smoke benchmark, depth-12 single-thread, no artifacts):
- MultiPV-3 d10 ~11 ms/pos (~0.40 h both); MultiPV-5 d10 ~28 (~1.0 h); MultiPV-3 d12 ~37
  (~1.3 h); **MultiPV-5 d12 ~66 ms/pos -> ~70 min/month -> ~2.3 h both (RECOMMENDED)**;
  MultiPV-10 d12 ~139 (~4.9 h). K=5 returns exactly 5 lines; top-1 stable across d10/d12.
  GATE: MultiPV-5 d12 < 6-8 h -> GO (full extraction after 14.1B pilot).

v1 design:
- Side-to-move LOCAL narrowness (gap best-second, count-within-{30/50/100cp,5/10/20 ES-pts}
  right-censored at K, entropy/concentration, worst-of-topk) + board-logic obviousness
  discounts (capture/check/promotion/quiet, forced_evasion, obvious_recapture,
  fake_sharpness_discount). Forward-line fragility + simple-trade DEFERRED.
- Headline = train-defined binary sharp_local_v1 = (value-preserving count within 10 ES-pts <=2)
  AND NOT (obvious_recapture OR forced_evasion), MultiPV-K>=5. Continuous gap/entropy + train
  tercile = secondary. ES via existing 15.0C cp->ES transform (scale 348.4).
- Orientation: store side-to-move primitive for ALL positions; advantaged-player/defensive =
  derived views (filter by eval sign, no extra engine work). First target = move-quality C3c;
  C3a flagging / C3b board-decided outcome secondary + kept separate.

Artifact schema (gitignored, 1 row/checkpoint, joinable on game_id+selected_position_type):
game_id, selected_position_type, checkpoint_ply, fen_hash, engine_name/version, depth,
multipv_k, side_to_move, wide pv{1..K}_move_uci/_cp/_white_cp/_mate/_es, narrowness features,
obviousness flags, sharp_local_binary_v1 + sharp_score_v1, status/multipv_count/is_mate_band/
fen_hash_matches. No raw PGN/usernames; player hashes joined later from player_metadata.

Pilot (14.1B): 1,000 stratified 2024-09 positions (250/checkpoint), MultiPV-5 d10 then d12,
gitignored artifact + report, validation (fen_hash match, >=min(K,legal) lines, top-1 vs
pre_sf_eval_cp agreement, mate-band explicit, runtime). Full extraction only after pilot.

Prior trajectory: do NOT block extraction; revisit at 14.2A (sharpness result may strengthen
the case). 14.2A must lock feature def/threshold/orientation/targets/split/clustering/
replication/criteria/trajectory-required before any C3c modeling.

Caveats: no sharpness result exists; predictive/descriptive only; White-to-move scope; MultiPV
fixed-depth = approximation not ground truth; anti-circularity (Tier A: engine-geometry, not
human-outcome-derived); benchmark = single 30-pos run, approximate.

Next step:
14.1B — Pilot Sharpness Extraction → (full extraction on passing pilot) → 14.2A Sharpness
Interaction Pre-Registration.

## EXP-031 — Phase 14.1B Pilot Sharpness Extraction

Experiment ID: EXP-031
Date: 2026-06-14
Owner: Malachi Wang
Status: complete (pilot extraction; gitignored pilot artifact written; no full extraction; no
models; no existing modules modified; no new deps; nothing staged/committed)

Purpose:
Pilot MultiPV sharpness extraction on 1,000 stratified 2024-09 checkpoints; validate, compute
v1 objective value-fragility features + exploratory surface diagnostics, recommend full-run
settings.

FRAMING REVISION (Malachi): primary v1 sharpness = OBJECTIVE VALUE FRAGILITY (narrow viable
set / steep drop-off / legal-choice clutter). Surface move tags (check/capture/promotion/quiet/
forced-evasion) + surface-bait diagnostics are EXPLORATORY ONLY — NOT human obviousness (Tier B,
deferred). No sharpness result; no obviousness modeled.

Implementation:
- multipv_sharpness.py: reads pre_fen directly (no reconstruction); engine.analyse(...,
  multipv=K) (never engine.configure MultiPV); relative_score_to_mover (mover POV) +
  score_to_white_pov (White POV) + expected_score (scale 348.41); pure feature fns
  (fragility_features: n_good_{5/10/20es,30/50/100cp} censored at K, best-second/third gaps,
  worst/mean top5 loss, max adjacent gap, cliff, softmax entropy/concentration T=0.10;
  clutter_features: legal_move_count + viable-fraction lower bounds; move_tags; surface_bait;
  composites: sharp_value_fragility_v1 = n_good_10es<=2 AND worst_top5_loss_es>=0.10 AND
  legal_move_count>=8, + relaxed/strict + continuous sharp_score_candidate + exploratory
  surface_bait_v1); stratified sampler; depth comparison; report; CLI. Reuses stockfish_eval +
  next_move_loss helpers unchanged.
- 22 tests (no engine); full suite 1,727 passing (+22), 0 regressions.

Pilot (MultiPV-5, d10 + d12, seed 42, 1000 rows / 250 per checkpoint, Stockfish 18):
- VALIDATION: 1000/1000 OK; FEN round-trip 1.0 (NML has no stored fen_hash -> parse-integrity
  check); all candidates legal 1.0; median MultiPV count 5 (fewer only where legal<5); top-1 vs
  stored pre_sf_eval_cp median |Δcp| 15; 0 mate-band sampled (non-mate plentiful; mate path
  implemented but unexercised).
- RUNTIME: d10 ~35 ms/pos, d12 ~106 ms/pos (> 14.1A 30-pos smoke 66 ms — stratified sample has
  more complex late positions). Full projection ~3.7 h both months -> under 6-8 h GO gate.
- DEPTH STABILITY: top-1 move agreement 0.64 (flat positions -> ambiguous best move), n_good_10es
  agreement 0.88, sharp_value_fragility_v1 agreement 0.95 -> composite depth-stable, depth-12
  preferred.
- FEATURE SANITY: median best-2nd ES gap 0.012, median n_good_10es 5 (median NOT sharp), median
  legal_move_count 32; sharp_v1 rate 0.142 / relaxed 0.074 / strict 0.068 / surface_bait_10es
  0.024 / best_move_is_quiet 0.679. Non-degenerate. Candidate features pending 14.2A.
- Artifact gitignored (140 cols, no PGN/usernames/hashes).

Next step:
14.1C — Full Sharpness Extraction (both months, MultiPV-5 d12, ~3.7 h) -> 14.2A Sharpness
Interaction Pre-Registration before any C3c modeling. Prior-trajectory = optional follow-up.

## EXP-032 — Phase 14.1C Full Sharpness Extraction

Experiment ID: EXP-032
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (full MultiPV extraction both months; gitignored artifacts written; no
moderation models; no new deps; nothing staged/committed)

Purpose:
Full MultiPV-5 depth-12 sharpness feature extraction over both 10+0 months, producing the
gitignored artifacts 14.2A needs to lock sharpness thresholds.

Implementation:
- multipv_sharpness.py: added --full (all OK rows, single depth pass, no stratified sampling),
  --combined (render cross-month report from extracted artifacts, no engine), --report-only
  (re-render a month report from a saved artifact, no engine); full_summary +
  render_month_full_report + render_combined_full_report; rounded report medians; NaN-safe
  runtime cells. Pilot path preserved. +2 tests; full suite 1,729 passing, 0 regressions.

Extraction (Stockfish 18, MultiPV-5, depth-12, seed 42):
- 2024-09: 64,371/64,371 OK (61,956 non-mate, 2,415 mate-band). 2024-10: 61,868/61,868 OK
  (59,625 non-mate, 2,243 mate-band).
- Validation BOTH months: FEN round-trip 1.0; all-candidates-legal 1.0; median MultiPV count 5;
  <K-legal share ~5.8% (single-legal-move forced positions); top-1 vs stored pre_sf_eval_cp
  |Δcp| median 14 / p90 49. Only null among key features = best_second_gap_es (617/616 =
  single-legal-move rows; expected). n_good_*/worst_top5_loss/sharp_v1 zero nulls.

Feature distributions (non-mate), 2024-09 / 2024-10 — strikingly stable:
- sharp_value_fragility_v1 0.1417 / 0.1407 (matches pilot 0.142); relaxed 0.0817/0.0836;
  strict 0.0732/0.0744.
- median best->2nd ES gap 0.0126/0.0124; median n_good_10es 5/5; median worst_top5_loss_es
  0.0463/0.0465; median legal moves 34/34.
- surface_bait_10es 0.022/0.024; best-move quiet 0.692/0.690, check 0.078/0.079, capture
  0.258/0.260.
- by-checkpoint sharp_v1 eases later: move_10 0.148/0.151, move_20 0.152/0.153, move_30
  0.134/0.123, move_40 0.103/0.102 (replicated trend).
- Month-to-month: sharp_v1 Δ 0.0010; medians identical; no anomaly before 14.2A.

Runtime: awake rate ~100 ms/pos (~3.5 h both months of compute). Raw wall-clock inflated by
overnight system sleep on battery (pmset: repeated Clamshell/Maintenance Sleep suspends) —
suspension, not engine cost. Operational note: keep machine awake/plugged for long runs.

Framing: primary v1 = OBJECTIVE value fragility; surface tags + surface-bait = EXPLORATORY,
NOT human obviousness (Tier B deferred). Candidate composites pending 14.2A. No sharpness/
moderation/obviousness claim. Predictive/descriptive; MultiPV fixed-depth approximates
narrowness, not ground truth; White-to-move scope.

Next step:
14.2A — Sharpness Interaction Pre-Registration (lock feature/threshold/orientation/C3c target/
uncertainty/criteria before any C3c/C3a/C3b modeling). Prior-trajectory = optional follow-up.

## EXP-033 — Phase 14.2A Sharpness Interaction Pre-Registration

Experiment ID: EXP-033
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (pre-registration / design, doc-only; NO modeling run; no data/code/tests
changed; nothing staged/committed)

Purpose:
Lock the C3c clock × sharpness move-quality moderation test before 14.2B implementation.

Question: does the small controlled 60_180-vs-over_180 clock association with next-move ES
loss (15.1D/15.1F, pooled +0.0034) become LARGER in objectively sharp positions?

LOCKED (PREREGISTRATION §C3c):
- Target: expected_score_loss (mover perspective, non-mate), 15.1D/15.1F family.
- Feature: sharp_value_fragility_v1 = n_good_10es<=2 AND worst_top5_loss_es>=0.10 AND
  legal_move_count>=8 (engine-side value fragility; NOT human obviousness; base rate ~0.142).
- Contrast: 60_180 vs over_180 × sharp; estimand = DiD = interaction coefficient (positive ⇒
  low-clock association larger when sharp). under_60×sharp secondary/exploratory.
- Model: OLS expected_score_loss ~ C(clock,ref=over_180) + sharp + clock:sharp +
  C(checkpoint,ref=move_10) + C(eval_band,ref=decided) + rating_z + C(month,ref=2024_09) +
  C(termination_binary,ref=board_decided). Rating linear primary (15.1F), bins/quadratic
  sensitivity. Estimate train+val; test locked confirmation; no test selection.
- Uncertainty: mover-player-clustered bootstrap (cluster_bootstrap_refit + summarize_contrasts),
  200 reps seed 42, per-month then pooled.
- Strong support: positive both months + pooled CI excludes 0 + not single-cell-driven +
  survives robustness (esp. continuous-eval + board-decided-only). Weak/null/kill criteria
  fully specified.

Read-only feasibility (no model): join unique on (game_id, selected_position_type); 100%
coverage onto non-mate frame (61,956/59,625); mover-hash present all rows. PRIMARY-CELL
ADEQUACY: sharp×60_180 = 348 (2024-09) / 329 (2024-10) / ~677 pooled — just above the ≥300 CI
threshold → power bottleneck + kill criterion (no claim if <~300/mo after primary filters).
under_60×sharp ~110/mo → exploratory only.

12 pre-registered robustness checks (month replication, board-decided-only, termination
control, eval control band+continuous-cp, rating spec, checkpoint, sharpness-threshold
sensitivity, large-loss logistic, clipped-cp secondary, exploratory surface-bait [NOT
obviousness], cluster sensitivity, mate-band sensitivity).

Forbidden: causal claims; "time pressure causes worse moves/reasoning"; sharpness proven pre-
model; v1 = all human difficulty; human obviousness modeled; Stockfish ground truth; DRAW
solved; best predictor; degradation curve.

Next step:
14.2B — Sharpness Interaction Modeling Implementation (fit the locked model; no design changes
without a logged deviation).

## EXP-034 — Phase 14.2B Sharpness Interaction Modeling

Experiment ID: EXP-034
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (modeling; pre-registered 14.2A model fit exactly; no engine; no data
artifacts modified; nothing staged/committed)

Purpose:
Fit the locked C3c clock × sharpness move-quality moderation: does the controlled
60_180-vs-over_180 clock association with next-move ES loss grow in sharp positions?

Implementation:
- sharpness_interaction.py: join next_move_loss ⋈ multipv_sharpness ⋈ player_metadata; validate
  (keys unique, inner join no-multiplication, 100% coverage, EXACT sharp_value_fragility_v1
  recompute = 0 mismatches); primary universe (non-mate, non-null, mover hash); design = car
  controlled base + sharp main + clock×sharp interaction; fit_interaction via
  cluster_bootstrap_refit + summarize_contrasts (mover-player, 200 reps seed 42); train+val
  estimate + locked test confirmation; 12 robustness families; classification; reports; CLI
  (+--smoke). Reuses cmq + car + clustered_uncertainty unchanged. 15 tests; full suite 1,744
  passing (+15), 0 regressions. Final run ~65s.

CLASSIFICATION: UNDERPOWERED / NO CLAIM (per locked 14.2A kill criterion; threshold NOT moved).
- Primary clock=60_180 × sharp (train+val, mover-clustered): 2024-09 +0.0074 [−0.0079,+0.0217]
  contains 0; 2024-10 +0.0131 [+0.0001,+0.0274] excl 0; pooled +0.0102 [+0.0013,+0.0194] excl 0.
  Same-sign both months.
- KILL TRIGGER: limiting sharp×60_180 cell on estimation split = 297 (09) / 282 (10) < 300/mo
  (14.2A measured 348/329 on full non-mate frame; reserving test split lowers it). under_60×sharp
  ~50/mo (exploratory).
- Locked TEST confirmation WEAK/SIGN-FLIPS: pooled test +0.0012; 09 +0.0054; 10 −0.0035.
- Independently, strong-support also fails (2024-09 CI contains zero; test not confirming).
Interpretation: directionally suggestive (pooled & 2024-10 exclude zero) but NOT resolvable at
current sample → underpowered/no-claim, an absence of resolving power, not a null finding.

Non-claims: not causal; no "time pressure causes worse moves/reasoning"; NO sharpness-moderation-
shown claim; NO human-obviousness modeled (v1 = engine-side proxy); surface-bait exploratory only;
no C3a/C3b outcome/flagging claim; no degradation curve; Stockfish not ground truth; DRAW not
solved.

Next step:
14.2C — Null / Power Interpretation and Roadmap Reconciliation Audit (accept underpowered &
consolidate; OR enrich power then re-run LOCKED model; OR pivot to C3a/C3b — no threshold moves).

## EXP-035 — Phase 14.2C Null / Power Interpretation and Roadmap Reconciliation Audit

Experiment ID: EXP-035
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (doc/design audit; NO modeling run; no data/code/tests changed; nothing
staged/committed)

Purpose:
Decide how to treat the 14.2B underpowered C3c result and reconcile the roadmap before any
further modeling. No model rerun; no thresholds changed.

14.2B verdict (preserved): C3c is NOT confirmed, NOT disproven, UNDERPOWERED / NO-CLAIM.
Pooled train+val interaction directional only (+0.0102 [+0.0013,+0.0194]); failed locked
criteria via (a) sharp×60_180 per-month cell 297/282 < 300, (b) 2024-09 CI contains 0, (c) test
confirmation weak + 2024-10 sign-flip (−0.0035).

Power audit (read-only counts): 60_180 train+val cell ~2,208/2,244 per month × ~13% sharp ⇒
sharp×60_180 ~290/month. ORDINARY ADDED MONTHS GROW POOLED PRECISION BUT NOT THE PER-MONTH CELL
(~290 stays <300). +1 month → ~870 pooled; +2 → ~1,160 pooled. The locked per-month ≥300 gate is
structurally unreachable with ordinary months → clearing it requires a NEW pre-registered
pooled-power criterion OR sharp-position oversampling (new design). Threshold relaxation
(Option D) forbidden.

Options A-F weighed. RECOMMENDATION: PRIMARY = Option E (freeze C3c "directional but
underpowered/no-claim" + consolidate) — small/secondary effect, did NOT confirm out-of-sample
(Oct sign-flip), per-month gate structurally unreachable with ordinary months, C4 headline
already settled. FALLBACK = Option A (third-month power enrichment audit, plan-only; rerun SAME
locked model on +1 ordinary month, fresh pooled-power pre-reg). Option F (C3a/C3b) = separate
question, not a rescue.

Non-claims: C3c not confirmed/not disproven/underpowered; pooled estimate directional only; no
causality; no human obviousness; no threshold relaxation after results; no C3a/C3b claim; no
Stockfish ground truth; DRAW not solved.

Next step:
14.2D — C3c Underpowered Result Consolidation (doc-only). Fallback (user's compute-budget call):
14.2D Third-Month Power Enrichment Audit. C3a/C3b outcome sharpness = separate 14.3A.

## EXP-036 — C3c Underpowered Result Consolidation

Experiment ID: EXP-036
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (doc-only consolidation; NO modeling; no thresholds/model/contrast/
classification changed; no data/code/tests changed; nothing staged/committed)

Purpose:
Freeze the final stable C3c interpretation so future tickets don't overclaim, reclassify, or
keep reopening the underpowered sharpness × clock move-quality result.

Final C3c status (FROZEN): unresolved — directional train+val signal, UNDERPOWERED / NO-CLAIM
under locked criteria. NOT confirmed, NOT disproven, NOT a null. 14.2B classification preserved
verbatim. Pooled train+val interaction +0.0102 [+0.0013,+0.0194] directional only; failed locked
criteria via per-month cell 297/282<300, 2024-09 CI contains 0, test-split weak + Oct sign-flip.

Stable wording recorded (long + short form) for reuse.

Future revisit conditions: Path A (same locked model on enriched ordinary months — improves
pooled precision but per-month ≥300 gate still binds, so a pooled-power verdict needs a NEW
pre-registration); Path B (new pooled-power enrichment design); Path C (sharp-position
oversampling design). All keep original threshold/model/contrast fixed; new criteria = new
labeled analyses.

Forbidden: relax sharp_value_fragility_v1 threshold post-hoc; switch primary clock contrast
post-hoc; headline surface-bait; use exploratory robustness as main claim; rerun-until-a-month-
passes; reclassify as supported via pooled train+val alone.

Non-claims: no C3c confirmed/disproven; no sharpness-moderation-shown; no causality; no human
obviousness; surface-bait not headline; no threshold relaxation; no Stockfish ground truth;
DRAW not solved.

Next step:
14.3A — Outcome/Flagging Sharpness Audit (separate C3a/C3b question; does NOT reuse the
underpowered C3c model). Alternatives: 14.2E enrichment audit (revisit C3c) or 16.0A final
synthesis. Prior-trajectory extraction = optional follow-up.

## EXP-037 — Outcome / Flagging Sharpness Audit

Experiment ID: EXP-037
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (doc/design audit; NO modeling; no thresholds/C3c-classification changed; no
data/code/tests changed; nothing staged/committed)

Purpose:
Audit whether C3a (outcome) / C3b (flagging) sharpness moderation is worth testing, separate
from the closed/underpowered C3c move-quality question.

Definitions: C3a = sharpness moderation of outcome-level clock residuals; C3b = sharpness
moderation of timeout/flagging-channel risk. NEITHER is next-move quality; neither rescues C3c;
neither shows human obviousness or causal time-pressure degradation.

Feasibility (read-only, no model): join on (game_id, selected_position_type), 100% coverage.
is_time_forfeit present in next_move_loss (GAME-LEVEL — does not say who flagged; player-to-move
flag = is_time_forfeit AND mover lost, needs result_class from feature_positions_broad).
result_class NOT in next_move_loss but in feature table + eval_conditioned_predictions. No new
artifacts needed.

Power/cells: non-mate ~62k/60k; TF prevalence ~13.4%/13.5%; TF clock gradient strongly MECHANICAL
(over_180 ~12% → 60_180 ~35% → under_60 ~64-69%). C3b INTERACTION cells = same scarce sharp×
low-clock cells as C3c (sharp×60_180 ≈348/329, sharp×under_60 ≈82/97) → interaction no better
powered than C3c (binary high-prevalence TF target gives more events = modest edge, not a fix).

Relationship to 11.2B: all-games clock→outcome ≈ flagging channel; board-decided residual
collapsed. ⇒ all-games C3a re-derives C3b (confounded); board-decided C3a is null-by-construction
(little residual to moderate). C3b is the only coherent outcome-side extension, and it is a
time-management/selection CHANNEL question, easily mis-told as move-quality.

RECOMMENDATION: Option C — STOP sharpness modeling, move to FINAL SYNTHESIS (16.0A). C3a NOT
recommended (confounded / null-by-construction). Fallback if channel result wanted: Option A =
flagging-only C3b pre-registration (14.3B), strictly flagging-channel framing, player-to-move
target via result_class join, acknowledging shared cell limit.

Non-claims: C3a/C3b NOT modeled; no outcome/flagging sharpness moderation shown; do not rescue
C3c (unresolved/no-claim); no causality; no human obviousness; surface-bait exploratory;
Stockfish not ground truth; DRAW not solved.

Next step:
16.0A — Final Synthesis / Public-Facing Claim Audit. Fallbacks: 14.3B flagging-only pre-reg
(C3b), or 14.2E C3c enrichment audit.

## EXP-038 — Synthesis Readiness / Public-Facing Claim Audit

Experiment ID: EXP-038
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (doc/design audit; NO modeling; no thresholds/classifications changed; no
data/code/tests changed; nothing staged/committed)

Purpose:
Decide whether the project is ready for final public-facing synthesis and lock the claim
architecture.

VERDICT: READY for final report drafting (Option A). Evidence sufficient; no more modeling
needed; remaining work = figure/table generation + minor consolidation inside the synthesis
ticket.

Claim hierarchy (full text in reports/synthesis_readiness_audit.md):
- L1 headline: (1) clock improves outcome prediction beyond eval+rating (E3→E4 −0.0138/−0.0120);
  (2) that signal is largely the flagging/time-forfeit channel (board-decided collapsed
  +0.0010/+0.0060; TF −0.118/−0.131), NOT board-play degradation; (3) eval-state dominates
  next-move ES loss, clock a small robust residual after controls (60_180 vs over_180 pooled
  +0.0034).
- L2 secondary (caveated): robustness survival; board-decided-only same-sign; clustering doesn't
  remove it; sharpness features feasible/stable.
- L3 exploratory: atlas, surface-bait, sharpness distributions, C3b feasibility.
- L4 unresolved: C3c sharpness×clock move-quality moderation — directional, underpowered/no-claim,
  not confirmed/not disproven.
- L5 abandoned/not-recommended: C3a (confounded/null-by-construction), human obviousness
  (deferred), DRAW-specific, prior-trajectory control (deferred).

Deliverables: candidate abstract (DRAFT), forbidden-claims list, 15-section report outline,
10-table + 7-figure inventories (figures NOT generated here; reports/figures/ empty, ready).
Repo/doc readiness verified: ROADMAP/PREREGISTRATION/EXPERIMENT_LOG coherent; heavy artifacts
ignored; all arcs ready or ready-pending-figure (none blocking).

Limitations restated: 10+0 only; 2 months; observational/predictive not causal; Stockfish =
benchmark not ground truth; outcome clock ≈ flagging; board-decided collapsed; ES transform
train-fit; clock/move-quality effect small; eval dominates; C3c underpowered; no human
obviousness; selection/time-management remain; White-to-move scope; DRAW not solved; no
best-predictor claim.

Non-claims: no modeling run; no sharpness moderation shown; C3c neither null nor confirmed;
C3a/C3b not modeled; no causality; no human obviousness; Stockfish not ground truth; DRAW not
solved.

Next step:
16.0B — Final Report Skeleton / Claim Architecture Draft (assemble skeleton + generate tables/
figures + consolidate). Fallbacks (deliberate choice): 14.2E (C3c enrichment) or 14.3B (C3b
flagging).

## EXP-039 — Roadmap Recovery Patch

Experiment ID: EXP-039
Date: 2026-06-15
Owner: Malachi Wang
Status: complete (doc-only patch applying the 15.2A recovery audit; NO models, NO Stockfish, NO
data artifacts modified, NO thresholds/classifications changed; nothing staged/committed)

Purpose:
Patch the governance docs to match the recovered v11 architecture after 15.2A found the project
prematurely routed into a synthesis path under Phase 16.

Applied (per 15.2A §14):
- Reclassified the mistaken 16.0A synthesis-readiness audit as an early/off-roadmap claim-
  architecture checkpoint / Phase 17-adjacent (files NOT deleted; content reusable in Phase 17).
- Removed "16.0B — Final Report Skeleton" as the default next ticket.
- Restored Phase 15 as active+expanded (15.2 recovery → 15.3 dense move-by-move loss extraction
  → 15.4 CP/ES Constraint Atlas + controlled dense modeling → 15.5 sharpness-enriched atlas +
  interaction panel → 15.6 sharpness prediction-improvement (M0 eval+rating+phase, M1 +clock,
  M2 +sharpness, M3 +clock×sharpness) → 15.7 trajectory/prior-quality controls).
- Restored Phase 16 = cross-time-control dose-response (3+0/5+0/10+0 anchor/increment;
  within-pool rating-quantile caveat mandatory). Restored Phase 17 = packaging.
- Reconciled v11 numbering: v11 §15.2A/B sharpness×clock mediation executed as 14.2A–14.2D,
  final status directional/underpowered/no-claim.
- Files patched: ROADMAP.md (recovery note + restored Phase 15.2–17 + completed-tickets +
  next pointer); docs/roadmap_rescope_v11_draft.md (recovery note); PREREGISTRATION.md
  (post-15.2A recovery note); EXPERIMENT_LOG.md (this entry).

Settled findings PRESERVED unchanged: E3→E4 clock improves outcome prediction; that signal
largely flagging channel (11.2B); eval-state dominates move quality + small robust clock residual
(checkpoint-level); MultiPV sharpness extracted; C3c directional/underpowered/no-claim; C3a not
recommended; C3b coherent/not-default.

Next default empirical ticket: 15.3A — Dense Move-by-Move Loss Feasibility Audit (NOT synthesis).
No thresholds/classifications changed; no causal/obviousness/sharpness-shown claims.

## EXP-040 — Dense Move-by-Move Loss Extraction Pilot

Experiment ID: EXP-040
Date: 2026-06-16
Owner: Malachi Wang
Status: complete (PILOT ONLY; no full dense extraction; no models; no thresholds/classifications
changed; pilot artifact gitignored; nothing staged/committed)

Purpose:
Implement and pilot-run dense per-ply next-move loss extraction (every ply, both colors) — the
dense generalization of the four White-only numbered checkpoints (15.0C) — to size and validate
the pipeline before any full both-months run.

Scope:
- Month: 2024_09. Raw cache data/raw/lichess/lichess_2024_09_first250k.pgn.
- First 1,500 accepted 600+0 games (accepted_basic ∩ time_control==600+0); cap enforced.
- Universe: non-terminal plies, move_number >= 5, both White and Black moves.
- Eval strategy: Option A — one Stockfish eval per pre-move position; post-move eval reused from
  the next position (no MultiPV, no separate best-move search). Stockfish 18 @ depth 12.
- ES via existing train-fit cp->ES transform (scale 348.4059; not refit).

Module + tests:
- New src/chess_mhsuc/dense_move_loss.py (pilot-only; refuses caps > 2,000 without an explicit
  override; NO full-run path). Reuses next_move_loss/stockfish_eval/constraint_atlas/
  player_metadata helpers unmodified.
- tests/test_dense_move_loss.py — 30 tests. Full suite 1,774 passing (1,744 prior + 30).

Results:
- 86,977 per-ply rows across 1,486 games (14 of 1,500 too short for move>=5). 53 columns.
- 88,012 engine evals; 85,491 cache-reuse hits; 451 terminal positions resolved without engine.
- 0 replay failures, 0 eval errors, 0 duplicate (game_id, ply) keys, 0 missing-clock rows.
  7 think-time anomalies + 1 clock>600 flagged (not dropped). 4,874 mate-band rows flagged and
  excluded from headline loss summaries. 100% mover/opponent player-hash join.
- Mover colors balanced (White 43,856 / Black 43,121). Sign conversion correct for BOTH colors:
  ES loss mean 0.0345 White vs 0.0348 Black (medians 0.0116 vs 0.0113).
- Loss metrics (OK, non-mate-band, n=82,103): ES loss mean 0.0347, median 0.0115, p90 0.0939;
  ES>=0.05 20.3%, ES>=0.10 9.1%. Clipped cp loss mean 59.1, median 21, p90 160; zero share 25.6%.
  ES bounded [0, 0.788]; clipped cp never negative; raw cp negative for 18,301 rows (expected).
- DESCRIPTIVE cross-check (no claim): median ES loss by eval band — slight 0.0175 > clear 0.0108
  ~ near_equal 0.0108 > decided 0.0042 — reproduces the checkpoint 15.1B/15.1D eval-dominance
  pattern on dense, both-color data.

Runtime / extrapolation:
- ~40 min wall-clock (engine 2,108.5 s); 41.7 evals/s over the full pilot position distribution.
- Full both-months dense (~3.34M positions) extrapolated ~22.2 h @ depth 12 (~11.1 h/month) —
  upper half of the 15.3A 17–24 h band.
- Depth-10 timing subtest 202.8 evals/s on a 1,000-position non-distribution-matched sample
  (first ~17 games) → optimistic ~4.6 h; realistic depth-10 ~8–12 h per 15.3A. Reliable figure is
  the depth-12 full-pilot rate.

Recommendation:
- Next = 15.3C-A Dense Extraction Strategy Decision Audit (decide depth / chunking / sampling and
  a machine-kept-awake plan; ~22 h depth-12 is a real compute decision → NOT an automatic full
  depth-12 run). Validation did not fail, so 15.3B2 (pilot fixes) is not required.

Non-claims:
PILOT ONLY; no full dense run; no dense atlas; no dense controlled model; predictive/descriptive
only; not causal; no "low clock causes blunders" / "time pressure causes worse reasoning" /
"Stockfish is ground truth" / "human obviousness modeled" / "DRAW solved" / "best predictor".
Does not change C4 or C3c. No thresholds/classifications changed.

## EXP-041 — Full Dense Move-by-Move Loss Extraction: 2024-09

Experiment ID: EXP-041
Date: 2026-06-17
Owner: Malachi Wang
Status: complete (2024-09 ONLY; one-month full dense; no 2024-10 run; no figures; no models; no
thresholds/classifications changed; ES transform reused not refit; artifact + chunks gitignored;
nothing staged/committed)

Purpose:
Run the approved full dense per-ply next-move loss extraction for 2024-09 10+0 (the 15.3C-A
strategy decision): one month first, depth 12, full population, both colors, chunked/resumable
under caffeinate, with the time-control-aware schema added now.

Scope:
- Month: 2024_09 only; 600+0 only; depth 12. Both colors, move_number >= 5.
- Universe: all accepted 600+0 games (accepted_basic; 25,945 available) — no game cap.
- Eval strategy: Option A (one Stockfish eval per pre-move position; post-move reused).
- ES via existing train-fit transform scale 348.4059 (NOT refit).
- Execution: chunk_size 5,000, --resume, caffeinate -dimsu. Stockfish 18.

Module + tests:
- dense_move_loss.py extended: full-month mode (--allow-full-month-2024-09; LOCKED to
  month==2024_09, depth==12, 600+0; refuses 2024-10/other depth/other TC), chunked+resumable
  runner (chunk_NNNN.parquet shards + manifest.json; resume skips game_ids already in chunks;
  concat at end), 12 time-control-aware fields, preflight mode, extended validation. Pilot path +
  cap enforcement preserved.
- tests/test_dense_move_loss.py +16 (46 in file). Full suite 1,790 passing.

Preflight (gate before full run):
- First 1,500 games reproduced the 15.3B pilot EXACTLY: 86,977 rows / 1,486 games / 88,012 evals,
  0 replay failures, 0 dup keys -> PASS. Confirms the full-month code path == pilot path.

Results:
- 25,945 accepted games processed -> 1,496,890 per-ply rows across 25,611 games with usable
  move>=5 rows (334 too short). 65 columns. 156 MB parquet; 6 chunks.
- 1,514,689 engine evals; 1,471,279 cache-reuse hits; 7,812 terminal positions.
- Runtime 45,831.8 s (~12.7 h); 33.4 evals/s (below pilot 41.7 — full distribution has more long
  late-game positions).
- 0 replay failures, 0 eval errors, 0 duplicate (game_id, ply) keys, 0 missing-clock rows.
  132 clock>600 + 133 negative-think rows flagged (Lichess clock artifacts), never dropped.
  80,577 mate-band rows (5.4%) flagged and excluded from headline. 100% mover/opponent player-hash
  coverage; no raw usernames.
- Sign correct BOTH colors: ES loss mean 0.0347 White / 0.0344 Black. ES bounded [0, 0.838];
  clipped cp never negative; raw cp negative share 0.222 (expected).
- Loss (OK, non-mate): ES mean 0.0346, median 0.0114, p90 0.0926; ES>=0.05 ~0.20, ES>=0.10 0.090;
  clipped cp >=100 0.175, >=200 0.072.
- Coverage: under_60 46,195 / 60_180 95,862 / over_180 1,354,833 (dense gives ~18x the checkpoint
  low-clock observations); result_class WHITE_WIN 705,097 / BLACK_WIN 679,788 / DRAW 112,005.

Time-control-aware schema (validated uniform for 10+0):
- time_control_raw 600+0; initial_time_s 600; increment_s 0; family no_increment; speed rapid;
  clock_fraction range [0.0, 11.94] (upper tail = the 132 flagged clock artifacts);
  increment_buffer 100% null (correct for no-increment); think_time_net == gross; low_increment_
  buffer_flag null. Forward-compatible for later time controls without re-extraction.

Comparison to 15.3B pilot:
- rows/game 58.4 (pilot 58.5); mate-band 5.4% (5.6%); ES mean 0.0346 (0.0347); distributions match.

Recommendation:
- Next = 15.3D Full Dense Move-by-Move Loss Extraction Replication Month (2024-10) before any dense
  Constraint Atlas, so atlas claims use both monthly samples. Then 15.4A visualization audit.

Non-claims:
2024-09 ONLY; 2024-10 NOT run; no cross-time-control data; no visual atlas; no dense controlled
model; predictive/descriptive only; not causal; no "low clock causes blunders" / "time pressure
causes worse reasoning" / "Stockfish is ground truth" / "human obviousness modeled" / "DRAW solved"
/ "best predictor". Does not change C4 or C3c. No thresholds/classifications changed.

## EXP-042 — Full Dense Move-by-Move Loss Extraction: 2024-10 Replication Month

Experiment ID: EXP-042
Date: 2026-06-17
Owner: Malachi Wang
Status: complete (2024-10 ONLY; second 10+0 anchor month; no cross-time-control; no figures; no
models; no thresholds/classifications changed; ES transform reused not refit; artifact + chunks
gitignored; nothing staged/committed)

Purpose:
Replicate the 15.3C full dense per-ply next-move loss extraction for the second 10+0 anchor month
(2024-10), so the future dense Constraint Atlas rests on two independent monthly samples.

Scope:
- Month: 2024_10 only; 600+0 only; depth 12. Both colors, move_number >= 5.
- Universe: all accepted 600+0 games (accepted_basic; 24,842 available) — no game cap.
- Eval strategy: Option A (one Stockfish eval per pre-move position; post-move reused).
- ES via existing train-fit transform scale 348.4059 (NOT refit). Chunk_size 5,000, --resume,
  caffeinate. Stockfish 18.

Module + tests:
- dense_move_loss.py: added --allow-full-month-2024-10 (LOCKED month==2024_10/depth==12/600+0);
  generalized the full-month gate (each month flag restricted to its month; NO both-month mode;
  refuses cross-month/other-depth/other-TC/uncapped-without-flag); month-generic full-month branch
  with 2024-09 comparison block + 15.4A recommendation; preflight broad-sanity for new months;
  month-aware §17 in the report renderer. +7 tests (53 in file). Full suite 1,797 passing.

Preflight (broad-sanity gate, new month):
- First 1,500 games: 88,052 rows, 1,473 games, 89,066 evals, 0 replay fail, 0 dups, both colors,
  TC 600+0/600/0, full hash coverage, no usernames -> PASS.

Results:
- 24,842 accepted games -> 1,436,866 rows across 24,552 games with usable move>=5 rows (290 too
  short). 65 columns. 144 MB parquet; 5 chunks.
- 1,454,008 engine evals; runtime ~8.8 h (31,770 s); 46.1 evals/s.
- 0 replay failures, 0 eval errors, 0 duplicate (game_id, ply) keys, 0 missing-clock rows.
  109 clock>600 + 125 negative-think rows flagged (Lichess clock artifacts), never dropped.
  74,407 mate-band rows (5.2%) flagged and excluded from headline. 100% player-hash coverage; no
  raw usernames.
- Sign correct BOTH colors: ES loss mean 0.0347 White / 0.0345 Black. ES bounded [0, 0.881];
  clipped cp never negative; raw cp negative share 0.209.
- Loss (OK, non-mate): ES mean 0.0346, median 0.0114, p90 0.0926; ES>=0.05 0.201, ES>=0.10 0.090;
  clipped cp mean 58.9, median 21, p90 158, >=100 0.175, >=200 0.072.
- Coverage: under_60 44,802 / 60_180 94,299 / over_180 1,297,765; result_class WHITE_WIN 671,935 /
  BLACK_WIN 655,079 / DRAW 109,852. TC fields uniform 600+0/no_increment/rapid; increment_buffer
  100% null; clock_fraction [0, 6.20].

Cross-month replication (2024-09 vs 2024-10) — essentially exact:
- rows 1,496,890 vs 1,436,866; rows/game 58.4 vs 58.5; mate-band 5.4% vs 5.2%;
- ES mean 0.0346 vs 0.0346; median 0.0114 vs 0.0114; p90 0.0926 vs 0.0926; ES>=0.10 0.0903 vs
  0.0902; cp>=100 0.175 vs 0.175.

Operational note (15.3D-Hotfix):
- A mid-run duplicate-launch incident occurred: two extra overnight wrapper chains ([overnight]
  preflight + a dormant [guard] launcher, both started outside this agent) were detected and
  terminated; the single authoritative run was preserved and never collided on the data/ chunk dir
  (the duplicates were in preflight / dormant, writing only to /tmp). Final artifact is clean.

Recommendation:
- Next = 15.4A CP/ES Constraint Atlas Visualization Audit (both anchor months ready). Implementation
  in 15.4B; do not skip the audit.

Non-claims:
2024-10 10+0 ONLY (second anchor month); no cross-time-control; no visual atlas; no dense controlled
model; predictive/descriptive only; not causal; no "low clock causes blunders" / "time pressure
causes worse reasoning" / "Stockfish is ground truth" / "human obviousness modeled" / "DRAW solved"
/ "best predictor". Does not change C4 or C3c. No thresholds/classifications changed.

## EXP-043 — CP / ES Constraint Atlas Visualization Audit

Experiment ID: EXP-043
Date: 2026-06-17
Owner: Malachi Wang
Status: complete (DESIGN-ONLY audit; no figures generated; no models run; no data artifacts
created; no source/test code changed; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Design the dense CP/ES Constraint Atlas before implementation (15.4B), using the 2024-09 + 2024-10
dense move-loss artifacts as the ready 10+0 substrate.

Substrate (ready):
- 2024-09: 1,496,890 rows; 2024-10: 1,436,866 rows; combined 2,933,756 rows, 65 columns, both
  colors, move_number>=5, depth 12, 600+0. Cross-month replicated (ES mean 0.0346/median 0.0114/
  p90 0.0926 both months). All conditioning fields precomputed in the artifact (clock_bucket,
  rating_bucket, eval_band, phase, think_time_bucket, clock_fraction, termination, is_time_forfeit,
  result_class) -> NO joins needed for 15.4B.

Locked design:
- Metrics: PRIMARY expected_score_loss (mover-perspective); SECONDARY clipped cp loss
  (median/p75/p90); DIAGNOSTIC-only raw cp loss; large-loss panels ES>=0.05/0.10, cp>=100/200;
  %-eval-swing forbidden headline.
- Filtering: status ok; exclude mate-band from headline (5.3% combined; kept as diagnostic);
  both colors (already mover-perspective); anomalies (clock>600 ~0.2k/mo, neg-think ~0.13k/mo)
  flagged not dropped, optional-exclude variant.
- Month replication: every headline plot Sep+Oct separately OR pooled + replication table;
  pooled-only NOT allowed as primary.
- Plot families A–I: clock×ES, clock×clipped-cp, large-loss-prob×clock, rating×clock heatmap,
  eval-band-conditioned curves, phase/move-number curves, think-time curves, termination-channel
  diagnostics (board-decided vs time-forfeit; fields present), month-replication panels.
- Clock axis: absolute seconds primary (0_5/5_10/10_30/30_60/60_180/180_300/300+; sub-10s sparse
  ~14k combined -> collapse when faceted); clock_fraction secondary/future (co-linear /600 in 10+0).
- Rating: 200-Elo headline (8 bins; collapse <1000 & >=2200 tails when faceted — grounded by cell
  counts); 100-Elo marginal-only; within-TC percentile deferred to cross-TC work; raw bins never
  hidden.
- Eval band: precomputed near_equal/slight/clear/decided + mate_band diagnostic; conditioning
  mandatory (eval state dominates loss, 15.1B/15.1D).
- Phase: move-number buckets 5_10/11_20/21_30/31_40/41_60/61+ or `phase`; facet vs clock to avoid
  conflating low-clock with late-game.
- Think-time: gross==net (10+0); buckets 0_1/1_2/2_5/5_10/10_30/30+; anomaly caveat (not
  deliberation quality).
- Cell-count policy reused: hide <50 / descriptive 50-299 / CI >=300; game-level + mover-player-
  clustered bootstrap (reuse clustered_uncertainty.py).

Implementation guidance for 15.4B:
- NEW module src/chess_mhsuc/dense_constraint_atlas.py (constraint_atlas.py ALREADY EXISTS = 15.1B
  checkpoint atlas; must not clobber). matplotlib. CLI proposed. Output figures under
  reports/figures/phase_15_4_constraint_atlas/; report reports/constraint_atlas_10plus0_2024_09_
  2024_10_v1.md. Validation list specified. Forbidden-in-15.4B list specified (no cross-TC, no
  sharpness, no MultiPV, no regressions, no causal language, no threshold/ES-transform changes,
  no artifact modification, no public synthesis).

5 design questions raised for Malachi (rating bin width 200 vs adaptive; clock seconds vs fraction
primary; PNG vs PNG+SVG; termination panels now vs later; report technical vs partly human-readable).

Non-claims:
Design-only; predictive/descriptive, not causal; Stockfish not ground truth; no human obviousness;
no cross-time-control yet; no sharpness yet; not final/public report; no model selection; no "low
clock causes blunders"/"time pressure causes worse reasoning"/"DRAW solved". C4 & C3c unchanged.
No figures, models, data artifacts, or code produced.

## EXP-044 — CP / ES Constraint Atlas Visualization Implementation

Experiment ID: EXP-044
Date: 2026-06-17
Owner: Malachi Wang
Status: complete (visualization only; no models; no Stockfish; no data artifacts modified; figures
under reports/figures/ only; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Implement the dense CP/ES Constraint Atlas designed in 15.4A: render descriptive per-ply
move-quality figures + tables over the dense 10+0 substrate (2024-09 + 2024-10).

Inputs:
- data/processed/dense_move_loss_2024_09_250k_v1.parquet (1,496,890 rows)
- data/processed/dense_move_loss_2024_10_250k_v1.parquet (1,436,866 rows)
- read-only; row counts validated against 15.3C/15.3D.

Module + tests:
- NEW src/chess_mhsuc/dense_constraint_atlas.py (separate from constraint_atlas.py = 15.1B
  checkpoint atlas, NOT clobbered). Pure bucket/aggregation/bootstrap helpers + matplotlib (Agg)
  renderers + report writer + CLI. Game-clustered bootstrap via per-cluster sums (fast).
- tests/test_dense_constraint_atlas.py 18 tests; full suite 1,815 passing.

Validation:
- all required columns; NO raw-username columns; ES in [0,1]; clipped cp >= 0; time control
  uniformly 600+0/600/0/rapid; per-month counts match. Headline = status ok & not mate-band &
  both colors = 2,778,772 rows; mate-band excluded 154,984 (5.3%). Anomalies flagged not dropped
  (clock>600 116/91; neg-think 133/125; missing-clock 0/0).

Filtering/metric policy:
- PRIMARY expected_score_loss; SECONDARY clipped cp (median/p75/p90); raw cp diagnostic-only;
  large-loss ES>=0.05/0.10, cp>=100/200; %-eval-swing not headline.

Outputs:
- 9 PNG figures under reports/figures/phase_15_4_constraint_atlas/ (clock×ES with game-clustered
  95% CI; clock×clipped-cp; large-loss prob; rating×clock heatmap; eval-band curves; phase×clock;
  think-time; termination-channel board-decided-vs-TF; month-replication). Bootstrap 500 draws,
  seed 20240617. Runtime ~8 s (read-only; no Stockfish).
- reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md.

KEY DESCRIPTIVE (month-replicated; MARGINAL, not controlled):
- Eval state DOMINATES: ES mean slight 0.044 > near_equal 0.033 ~ clear 0.031 > decided 0.017
  (~2.6x spread), reproducing 15.1B/15.1D.
- Marginal ES-loss-by-clock is U-shaped: highest at 300+ (0.0358 both months), mildly elevated at
  0-5s (~0.034), lowest 60-180s (~0.0288). Marginally low-clock is NOT worse (confounded with
  phase/eval band). The controlled C4 result (15.1D/15.1F: small clock association AFTER controls)
  remains the inferential statement; the atlas is the descriptive map around it.
- Patterns replicate near-exactly across 2024-09 and 2024-10.

Recommendation:
- Next = 15.4C Controlled Dense Move-Quality Modeling Audit (per ROADMAP restored Phase 15.4
  sequence: controlled per-ply model net of eval/phase/rating/termination + mover-player clustering;
  then 15.4D; then Phase 15.5 sharpness). NOT Phase 16; NOT synthesis.

Non-claims:
Predictive/descriptive only; not causal; no "low clock causes blunders"/"time pressure causes worse
reasoning"/"Stockfish is ground truth"/"human obviousness modeled"/"DRAW solved". No sharpness, no
cross-time-control, no model fitting/selection. C4 & C3c unchanged. Dense artifacts not modified.

## EXP-045 — Controlled Dense Move-Quality Modeling Audit

Experiment ID: EXP-045
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (DESIGN-ONLY audit; no models run; no figures; no data artifacts; no source/test
code changed; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Design the controlled dense per-ply move-quality model (for 15.4D) that turns the descriptive
15.4B atlas into a controlled conditional-association estimate of clock vs next-move loss net of
eval/phase/rating/termination/month/color.

Motivation:
15.4B marginal clock curves are U-shaped/confounded (eval state dominates, ~2.6x spread vs clock
~1.25x non-monotone). A U-shaped marginal does NOT contradict the 15.1D/15.1F controlled checkpoint
result (small replicated clock residual after controls). Need the dense controlled model to test
persistence at per-ply scale.

Feasibility (read-only):
- headline 2,778,772 rows (status ok, mate-band excluded); board-decided 2,387,377; time-forfeit
  391,395; 50,106 games; 31,381 mover hashes; splits train 1.94M/val 414k/test 414k.
- continuous-eval fields present (expected_score_before, eval_before_cp; 0 nulls).
- statsmodels NOT installed -> reuse numpy _ols_fit + sklearn logistic + clustered_uncertainty
  cluster_bootstrap_refit/summarize_contrasts (the 15.1D/15.1F machinery; no new dep).
- SPARSITY caveat: under_10 x board-decided = 1,820 rows (slight band 72) -> extreme-low-clock
  board-decided residual underpowered; powered headline contrast = 60_180 vs over_180 (as 15.1D).

Locked design:
- PRIMARY target expected_score_loss (OLS adjusted-mean; coefficients = ES-loss differences). RHS:
  C(clock_coarse, ref=over_180) + C(eval_band, ref=decided) + C(phase) + C(rating_bin, mover_elo
  200-Elo) + C(month) + C(mover_color) + C(termination_channel, ref=board_decided). Additive (no
  high-order interactions in primary). Continuous-eval robustness via binned/spline
  expected_score_before or abs(eval_before_cp).
- Secondary: S1 clipped_cp_loss; S2 I(ES>=0.10)/I(ES>=0.05) LPM primary + sklearn logistic
  robustness; S3 board-decided-only; S4 anomaly-excluded; S5 month-specific replication.
- Interactions (secondary, labeled): clock x {eval_band, phase, rating_bin, termination_channel}.
  NO sharpness interaction (Phase 15.5).
- Think-time EXCLUDED from primary (downstream/bad control); secondary descriptive only.
- Uncertainty: game-clustered bootstrap PRIMARY (reuse cluster_bootstrap_refit; recommend
  per-cluster sufficient-statistics bootstrap since naive row-reindex at 2.78M rows x reps is slow;
  fallback --bootstrap 200); mover-player-clustered robustness.
- Splits: pooled train+val fit w/ month FE for headline; test = locked confirmation (no tuning);
  month-specific replication; rating_z train-only if used. No model selection.
- Robustness R1-R10 (month, board-decided, anomaly-excluded, clipped-cp, large-loss, continuous
  eval, clock encodings, rating continuous, phase-vs-move#, game-vs-player clustering).

15.4D scope:
- new module src/chess_mhsuc/dense_controlled_model.py + tests; fit primary + S1-S5 + interactions
  + R1-R10; report reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md +
  phase_15_4d report; update ROADMAP/EXPERIMENT_LOG. NOT sharpness, NOT cross-TC, NOT synthesis.

Non-claims:
Design-only; conditional association NOT causal; no "low clock causes blunders"/"time pressure
causes worse reasoning"/"Stockfish is ground truth"/"human obviousness"/"sharpness moderation
confirmed-or-disproven"/"DRAW solved". C4 & C3c unchanged. No models/figures/data/code produced.

## EXP-046 — Controlled Dense Move-Quality Modeling Implementation

Experiment ID: EXP-046
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (modeling only; no Stockfish; no figures; no data artifacts modified; nothing
staged/committed; PREREGISTRATION unchanged)

Purpose:
Implement the 15.4C controlled dense per-ply move-quality model: estimate the CONDITIONAL
ASSOCIATION between clock state and next-move ES loss net of eval/phase/rating/month/color/
termination, on the dense 2024-09+2024-10 substrate. Dense analogue of 15.1D/15.1F.

Inputs:
- data/processed/dense_move_loss_2024_09_250k_v1.parquet (1,496,890) + 2024_10 (1,436,866),
  read-only; counts validated; no usernames.

Module + tests:
- NEW src/chess_mhsuc/dense_controlled_model.py (numpy OLS adjusted-mean; explicit one-hot
  build_design with fixed refs + constant-column drop; fast GAME-clustered sufficient-statistics
  bootstrap via per-cluster XtX/Xty + bincount-weighted resample; reuse clustered_uncertainty
  _cluster_index/summarize_contrasts + dense_constraint_atlas bucket helpers; sklearn logistic
  sign-check). 16 tests; full suite 1,831 passing.
- NOTE: naive row-resampling refit was too slow at 2.78M rows (killed, exit 144); replaced with
  sufficient-statistics bincount bootstrap (~61 s whole run).

Validation/filtering:
- headline = status ok & ~mate-band & both colors = 2,778,772 rows; board-decided 2,387,377;
  time-forfeit 391,395; 50,106 game clusters; 31,381 mover-player clusters. anomalies flagged
  (clock>600 ~100/mo, neg-think ~130/mo).

RESULTS (conditional association, NOT causal; game-clustered 95% CI; 500 draws, seed 20240617):
- Eval positive control DOMINATES: vs decided, slight +0.0306 / near_equal +0.0222 / clear +0.0165
  (all excl 0) — ~3-30x the clock coefficients.
- Clock gradient vs over_180 (monotone, all excl 0): under_10 +0.0083 / 10_30 +0.0045 /
  30_60 +0.0030 / FOCAL 60_180 +0.0009 [+0.0005,+0.0014].
- Month replication strong: 60_180 0.0010 (09) / 0.0009 (10); under_10 0.0079/0.0086.
- Mover-player-clustered: 60_180 +0.0009 [+0.0005,+0.0013] excl 0.
- Board-decided-only: 60_180 +0.0004 [-0.0001,+0.0009] CONTAINS 0 (borderline); under_10 +0.0079*,
  10_30 +0.0024*, 30_60 +0.0027* survive.
- Continuous-eval control: 60_180 +0.0001 [-0.0004,+0.0006] CONTAINS 0 (attenuates ~0 -> within-band
  eval confounding for the smallest contrast).
- Clipped cp: monotone +16.2/+8.7/+6.0/+2.15 cp (all excl 0). ES>=0.10 LPM 60_180 +0.0058* (logistic
  sign agrees +0.069); ES>=0.05 LPM +0.0011 contains 0.
- rating_z +0.0011*; anomaly-excluded +0.0009*.
- Interactions: residual concentrates in slight-eval (+0.0025*), middlegame (+0.0024*), time-forfeit
  (+0.0011*); ~0 elsewhere.

Comparison to 15.1D/15.1F:
- Same sign + structure (eval dominates; small positive clock residual; survives clustering) but
  dense focal 60_180 ~4x SMALLER (+0.0009 vs +0.0034) and MORE FRAGILE (attenuates under continuous
  eval; borderline board-decided). REFINES, not just confirms. Reported honestly, not forced to match.

Recommendation:
- Next = 15.5A Sharpness-Enriched Constraint Atlas Audit (C3c move-quality-first). NOT Phase 16;
  NOT synthesis.

Non-claims:
Conditional/predictive only; NOT causal; no "low clock causes blunders"/"time pressure causes worse
reasoning"/"clock proves cognitive degradation"/"Stockfish is ground truth"/"human obviousness"/
"sharpness moderation confirmed-or-disproven"/"DRAW solved". C4 & C3c unchanged; ES transform not
refit; dense artifacts not modified.

## EXP-047 — Sharpness-Enriched Constraint Atlas Audit

Experiment ID: EXP-047
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (DESIGN-ONLY audit; no Stockfish/MultiPV run; no models; no figures; no data
artifacts; no source/test code changed; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Audit whether existing MultiPV sharpness artifacts can support a sharpness-enriched dense
move-quality atlas/model (Phase 15.5), i.e. whether the small fragile 15.4D clock residual
localizes to objective positional value fragility.

Read-only findings:
- Sharpness artifacts: multipv_sharpness_2024_09 (64,371) / 2024_10 (61,868) checkpoint rows
  (~126k), 140 cols, key game_id+checkpoint_ply{20,40,60,80}+selected_position_type,
  side_to_move=WHITE for all rows, MultiPV-5 depth-12. sharp_value_fragility_v1 rate 0.142.
- Dense artifacts: 2,778,772 headline rows, key game_id+ply, both colors.
- CORRECT join = dense.ply = checkpoint_ply + 1 (the White move played FROM the checkpoint
  position; naive ply==checkpoint_ply wrongly matches the Black move INTO the checkpoint).
- Coverage (corrected): 121,165 matched = 4.36% of dense headline, ALL WHITE mover, checkpoint-
  overlap only (4 plies/game). NOT dense-wide, NOT both colors.
- Cell power: sharp x 60_180 ~675 pooled (~350/mo) -> exploratory/underpowered (the same corner
  that left C3c unresolved); sharp x under_60 <300 -> no-claim. Marginal sharp-vs-nonsharp by
  eval/clock have tens of thousands of rows (headline-capable).
- Full dense MultiPV-5 d12 over 2.78M rows ~51-82h -> PROHIBITIVE.

Prior C3c status PRESERVED: sharpness = objective value fragility (NOT human obviousness); C3c
clock x sharpness move-quality moderation directional/underpowered; train+val pooled positive,
test near zero, key cells underpowered; NOT confirmed, NOT disproven.

Recommendation (Option D):
- 15.5B = existing-sharpness CHECKPOINT-OVERLAP (White-to-move) join + atlas + EXPLORATORY
  clock x sharpness model (new module sharpness_enriched_atlas.py; join dense.ply=checkpoint_ply+1;
  game/player-clustered bootstrap). NO MultiPV/Stockfish. sharp x clock interaction labelled
  exploratory/no-claim; headline only well-powered marginal sharpness contrasts. Label all figures
  "checkpoint-overlap, White-to-move".
- Do NOT run full dense MultiPV. Defer stratified dense sharpness extraction to a later ticket only
  if 15.5B is inconclusive-but-promising.
- Phase 15.5 sequence: 15.5A (done) -> 15.5B -> 15.5C consolidation/C3c update. Do not move to
  Phase 16 until Phase 15.5 resolved or explicitly parked.

Non-claims:
Design-only; not causal; not human difficulty/obviousness; MultiPV/Stockfish not ground truth; no
"sharp positions cause blunders"; no "sharpness moderation confirmed-or-disproven"; not dense-wide
sharpness; not cross-time-control; no synthesis. C4 & C3c unchanged. No code/models/figures/data.

## EXP-048 — Existing-Sharpness Checkpoint-Overlap Join + Atlas / Exploratory Model

Experiment ID: EXP-048
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (analysis only; NO Stockfish/MultiPV; no artifacts modified; nothing
staged/committed; PREREGISTRATION unchanged)

Purpose:
Implement the 15.5A checkpoint-overlap sharpness enrichment: join existing MultiPV sharpness to
dense move-quality (corrected key), produce a sharp-vs-non-sharp atlas + EXPLORATORY clock x
sharpness model. Ask whether the small fragile 15.4D clock residual localizes to objective value
fragility.

Inputs:
- dense_move_loss_2024_09/10 (read-only) + multipv_sharpness_2024_09/10 (read-only).

Module + tests:
- NEW src/chess_mhsuc/sharpness_enriched_atlas.py (corrected join dense.ply=checkpoint_ply+1;
  validate_join asserts White-mover only and rejects the wrong ply==checkpoint_ply join; build_design
  with clock+sharp+clock×sharp, mover_color omitted (constant White), constant-column drop; reuse
  dense_controlled_model.ols_cluster_bootstrap + clustered_uncertainty.summarize_contrasts; 6 matplotlib
  figures). 14 tests; full suite 1,845 passing.

Join / coverage:
- Corrected join matched 126,239 rows (headline 121,165) = 4.36% of dense headline, WHITE-MOVER ONLY,
  checkpoint-overlap only (4 plies/game). sharp rate 0.1414. NOT dense-wide.

RESULTS (descriptive/predictive, NOT causal; game-clustered 95% CI, 500 draws, seed 20240617):
- Sharp main effect (net of controls, at over_180): +0.0214 [+0.0198,+0.0231]; replicated
  (Sep +0.0213, Oct +0.0215). PARTLY MECHANICAL: sharp_value_fragility_v1 embeds worst_top5_loss_es
  >= 0.10, so sharp positions have a worse achievable downside by construction -> descriptive
  localization, not a behavioral surprise.
- Focal clock 60_180 x sharp: +0.0104 [+0.0018,+0.0194] POOLED (CI excl 0), BUT both per-month CIs
  CONTAIN 0 (Sep +0.0095 [-0.0024,+0.0236]; Oct +0.0113 [-0.0008,+0.0232]); board-decided-only
  +0.0056 [-0.0046,+0.0155] contains 0. Lower-clock x sharp cells sparse (<200) -> no-claim.
  EXPLORATORY; does NOT cleanly replicate.
- clock 60_180 (non-sharp base): +0.0010 [-0.0006,+0.0028] (consistent w/ 15.4D small base).

Cell power: sharp x 60_180 = 675 (exploratory); sharp x 30_60/10_30/under_10 = 113/49/17 (sparse).
Same underpowered corner that left C3c unresolved; dense substrate doesn't fix it (checkpoint-
limited, White-only sharpness coverage).

C3c status: UNCHANGED — not confirmed, not disproven. Pooled +0.0104 matches the original Phase 14
C3c train+val pooled ~+0.010, with the same month-fragile/underpowered character.

Recommendation:
- Next = 15.5C Sharpness Result Consolidation / C3c Claim Update (keep C3c not-confirmed/not-
  disproven; decide whether a stratified dense sharpness extraction is warranted to power the
  interaction). NOT Phase 16; NOT synthesis.
- Future diagnostic (NOT this ticket): Think-Time Loss-Rate / Flagging Signature Diagnostic.

Non-claims:
Predictive/descriptive; not causal; no "sharp positions cause blunders"/"low clock causes blunders"/
"time pressure causes worse reasoning"; sharpness = objective value fragility, NOT human obviousness/
difficulty; MultiPV/Stockfish not ground truth; checkpoint-overlap White-mover only, NOT dense-wide;
no "sharpness moderation confirmed/disproven". C4 & C3c unchanged; no threshold/ES-transform change.

## EXP-049 — Sharpness Result Consolidation / C3c Claim Update

Experiment ID: EXP-049
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (REPORT-ONLY claim update; no code/models/figures; no Stockfish/MultiPV; no data
artifacts; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Consolidate Phase 14 + Phase 15.5 sharpness evidence into a project-level claim boundary for C3c.

Evidence reviewed:
- Phase 14 C3c (phase_14_1a/b/c, 14_2a-d, 14_3a); 15.5A audit; 15.5B implementation + report;
  15.4D dense controlled model; ROADMAP/EXPERIMENT_LOG/PREREGISTRATION.

Sharpness main effect:
- Clear + replicated: net of controls +0.0214 [+0.0198,+0.0231] (Sep +0.0213 / Oct +0.0215). PARTLY
  MECHANICAL — sharp_value_fragility_v1 embeds worst_top5_loss_es>=0.10 (downside availability), so
  higher realized loss is expected by construction. Descriptive localization, NOT human difficulty.

Clock x sharpness moderation:
- Checkpoint-overlap pooled focal 60_180 x sharp +0.0104 [+0.0018,+0.0194] (excl 0) but per-month
  Sep +0.0095 [-0.0024,+0.0236] / Oct +0.0113 [-0.0008,+0.0232] BOTH contain 0; board-decided
  +0.0056 [-0.0046,+0.0155] contains 0; low-clock sharp cells sparse (sharp×60_180=675; lower <200).
  EXPLORATORY. Directionally consistent with Phase-14 train+val +0.0102 (test ~0).

C3c CLAIM STATUS: UNRESOLVED — not confirmed, not disproven; pooled-positive/directionally
suggestive; month-fragile; board-decided-fragile; underpowered key cells; limited to checkpoint-
overlap White-mover rows (4.36%, NOT dense-wide).

Coverage/power limitations: existing sharpness = checkpoint-only (move_10/20/30/40), White-mover
only, ~4.36% of dense headline; matched subset not representative (no Black, no non-checkpoint
plies, low-clock under-sampled); sparse sharp×low-clock cells.

Decision / next: bound C3c as unresolved; PROCEED TO PHASE 16 (16.1A Time-Control Selection /
Feasibility Audit). Stratified dense sharpness extraction (optional 15.5D, ~3-9h sampled MultiPV,
both colors, stratified) and a Think-Time Loss-Rate / Flagging Signature diagnostic recorded as
OPTIONAL LATER BRANCHES (full dense MultiPV ~51-82h NOT recommended).

Safe-claim language locked (report §9); forbidden-claim list locked (§10).

Non-claims:
Report-only; not causal; sharpness = objective value fragility NOT human obviousness/difficulty;
MultiPV/Stockfish not ground truth; checkpoint-overlap White-mover only NOT dense-wide; no
"sharpness moderation confirmed/disproven"; no "sharp positions cause blunders"; no "low clock
causes blunders". C4 & C3c unchanged. No code/models/figures/data.

## EXP-050 — Time-Control Selection / Feasibility Audit

Experiment ID: EXP-050
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (DESIGN-ONLY audit; no Stockfish/dense extraction/models/figures; no data
artifacts; no source/test code changed; nothing staged/committed; PREREGISTRATION unchanged)

Purpose:
Select feasible, scientifically-useful time controls for Phase 16 cross-time-control dose-response,
before any extraction.

KEY FEASIBILITY (read-only):
- Raw caches lichess_2024_09/10_first250k.pgn already contain ALL time controls (game_records were
  parser-filtered to 600+0). Per-month cache TimeControl counts: 3+0 ~52k, 5+0 ~33k, 10+0 ~26k,
  3+2 ~20k, 5+3 ~11k, 10+5 ~4.8k, 15+10 ~1.3k, 1+0 ~73k. NO new download needed for 3+0/5+0/10+0.
- Pipeline gap: dense_move_loss.py hardcodes 600+0 acceptance (load_accepted_game_meta filters
  time_control=='600+0') + month/TC-locked full-month flags. Schema is already TC-aware
  (parse_time_control, clock_fraction, increment_buffer, think_time_net). 16.1B must generalize
  acceptance to a chosen --time-control (derive accepted set from raw cache headers) + safety-gate.

Selection:
- First wave (no-increment speed dose-response): 3+0, 5+0, 10+0 (abundant, same months, lowest
  pipeline risk). Increment contrast better powered at blitz (5+0 vs 5+3 / 3+0 vs 3+2) than rare
  10+5/15+10 (deferred). 1+0 bullet = separate later regime.

Mandatory design:
- Rating pools NOT cross-comparable -> within-time-control rating QUANTILES primary, raw bins
  within-control secondary. Clock: within-control absolute seconds; cross-control clock_fraction;
  increment-aware increment_buffer = clock_before/max(increment,1). Termination: track all /
  board-decided / time-forfeit + termination RATES by control. Metric: ES loss primary (reuse 10+0
  ES transform across controls as documented assumption, not refit). Depth 12, both months.

Compute: anchors 10+0 ~1.5M rows/~12.7h (33eps) & ~1.44M/8.8h (46eps); pilot ~1.5k games ~25-40min.
Full per-control multi-day -> chunked/resumable/caffeinate; PILOT first (Option D -> B).

Recommendation / next: 16.1B Cross-Time-Control Pilot Dense Extraction (3+0, 5+0) — generalize
pipeline to --time-control + tests; pilots ~1,500 accepted games/control/month; report rows /
clock-fraction / termination-rate / rating-quantile / runtime; NO full extraction yet.

Optional later branches: Think-Time Loss-Rate / Flagging Signature Diagnostic; 15.5D Stratified
Dense Sharpness Extraction Audit; increment-rapid (10+5/15+10) if larger slice acquired; 1+0 bullet.

Non-claims:
Design-only; cross-control = descriptive/conditional, NOT causal; raw ratings NOT cross-pool
comparable; Stockfish not ground truth; no "faster time controls cause worse chess"/"increment
causes better reasoning"/"time pressure causes worse reasoning"/"low clock causes blunders"; no
sharpness claims; no "DRAW solved". C4 & C3c unchanged. No code/extraction/models/figures/data.

## EXP-051 — Cross-Time-Control Pilot Dense Extraction

Experiment ID: EXP-051
Date: 2026-06-18
Owner: Malachi Wang
Status: complete (implementation + PILOT only; no full extraction; pilot artifacts gitignored;
ES transform not refit; existing 10+0 artifacts untouched; nothing staged/committed;
PREREGISTRATION unchanged)

Purpose:
Generalize the dense pipeline to safety-gated non-600+0 time controls and pilot 3+0/5+0 to validate
cross-time-control extraction readiness before the full Phase 16 campaign.

Code (dense_move_loss.py):
- canonicalize_time_control (alias 3+0->180+0/5+0->300+0/10+0->600+0; reject malformed; default
  600+0). build_accepted_meta_from_raw (header-only accepted set from raw cache, since game_records
  is 600+0-only; basic acceptance = both Elos + decisive/draw result + Termination; split_set
  unknown; no usernames). CLI: --time-control + --allow-time-control-pilot gate (non-600+0 refused
  without gate / with --preflight / without finite cap / over cap; full-month stays 600+0-locked;
  600+0 unchanged). 12 tests; full suite 1,857 passing.

Pilots (1,500 accepted games/control/month, depth 12, caffeinate):
- 2024-09 3+0: 94,935 rows / 1,485 games / 96,020 evals / 1937s / 49.8 eps / ES mean 0.0338 / TF 38.7%
- 2024-09 5+0: 91,185 / 1,485 / 92,256 / 12066s(SLOW, transient throttle) / 7.7 eps / 0.035 / TF 28.8%
- 2024-10 3+0: 92,225 / 1,481 / 93,280 / 1919s / 48.8 eps / 0.0339 / TF 36.3%
- 2024-10 5+0: 89,652 / 1,483 / 90,728 / 1939s / 47.1 eps / 0.0353 / TF 27.9%
- All clean: 0 dup keys, 0 eval/replay fail, all status ok, both colors, no usernames, 100% player-
  hash, ES bounded, clipped cp>=0, TC fields correct (180+0/300+0, no_increment, blitz).

DESCRIPTIVE READINESS (replicated, NOT causal):
- TIME-FORFEIT rate = clean monotone DOSE-RESPONSE in base time: 3+0 ~37-39% > 5+0 ~28% > 10+0 ~13.4%.
- Move-quality ES loss SIMILAR across controls (~0.034-0.035) — the cross-control difference is in
  FLAGGING, not board-move loss.
- Rating pools DIFFER (blitz mover-Elo median ~1570-1792 vs rapid ~1601) -> within-control rating
  QUANTILES mandatory (confirmed). clock_fraction correctly off initial_time_s (180/300).

Recommendation:
- Pilots pass -> proceed to 16.1C Full (Matched-Size) 3+0/5+0 Dense Extraction (full per-control is
  LARGE: 3+0 ~3.2M rows, 5+0 ~2.0M; cap to a common ~25k accepted games for balanced power; chunked/
  resumable/caffeinated, no competing load). Then 16.2A move-quality audit.

Non-claims:
Pilot/feasibility only; not a full TC result; cross-control descriptive/conditional NOT causal; raw
ratings NOT cross-pool comparable; Stockfish not ground truth; no "faster time controls cause worse
chess"/"increment causes better reasoning"/"low clock causes blunders"/"time pressure causes worse
reasoning"; no sharpness claims; no "DRAW solved". C4 & C3c unchanged.
