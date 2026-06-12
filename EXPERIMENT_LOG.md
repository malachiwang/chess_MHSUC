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
