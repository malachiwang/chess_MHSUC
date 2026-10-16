# Model and measurement card

This repository contains research model implementations and saved evaluations, not
a single deployed model or downloadable fitted weights. See the
[README](README.md) for the main results and [pipeline guide](PIPELINE_OVERVIEW.md)
for data flow.

## Outcome models

| Family | Implementation | Recorded scope |
|---|---|---|
| Dummy priors and logistic regression | [baselines.py](src/chess_mhsuc/baselines.py) | B0-B5 and balanced diagnostic; 10+0 checkpoint experiments |
| Histogram gradient boosting | [gbm.py](src/chess_mhsuc/gbm.py) | G1-G6 pilot feature ablations, no neural models |
| Fixed-evaluation logistic regression | [eval_conditioned_modeling.py](src/chess_mhsuc/eval_conditioned_modeling.py) | E1: engine evaluation; E3: evaluation + rating; E4: adds clocks; E5: adds position context |

The target is `BLACK_WIN`, `DRAW`, or `WHITE_WIN`. Features include ratings and
differences, clock state, move/phase context, and evaluation where the model family
uses it. Local engine features clip centipawns to +/-1000 and include a mate flag.
Sparse Lichess annotations are not mixed into the fixed-evaluation feature sets.
Termination and post-game rating changes are excluded from predictive inputs.

Primary rows are after Black's moves 10, 20, 30, and 40, excluding `last`.
[splits.py](src/chess_mhsuc/splits.py) uses game-ID-level 70/15/15 partitions,
stratified by result with seed 42. Rows from one game stay together, but players can
span splits. These are not player-disjoint evaluations.

## Saved prediction evaluations

| Experiment | Validation scope | Main result and record |
|---|---|---|
| September 25k pilot, broad models | 4,344 training rows; 931 validation rows | G2 log loss 1.2326 versus B3 logistic 0.8527; G2 overfit. [Report](reports/gbm_evaluation_2024_09_25k_v1.md) |
| September 250k fixed-evaluation ablation | 45,818 training rows; 9,823 validation rows from 3,678 games | E3/E4/E5 log loss 0.7514/0.7377/0.7329. [Report](reports/eval_conditioned_modeling_2024_09_250k_v1.md) |
| September and October termination comparison | Frozen 10+0 E3/E4 validation predictions; 3,678/3,524 games | Clock improvement is concentrated in time-forfeit games; no replicated gain in the complementary group. [Report](reports/termination_decomposition_combined.md) |

Log loss is mean negative log probability of the observed class. Multiclass Brier
score is the mean sum of squared differences between the probability vector and
the one-hot outcome vector; lower is better for both. Accuracy and per-class
precision/recall are diagnostics. Draw recall remains weak: all four broad pilot
GBMs predict no draws on validation, and the September scaled E models also report
zero draw recall. Do not describe these as solving draw prediction.

[Calibration diagnostics](reports/calibration_2024_09_25k_v1.md) assess reliability
on the pilot's 931 validation rows. Expected calibration error averages the absolute
gap between predicted probability and observed frequency within probability bins,
weighted by bin count. It depends on the bins and class support. G2 is overconfident;
low draw ECE does not establish reliable draw probabilities. No post-hoc calibrator
was fitted. Some historical reports exposed test metrics; they are not fresh,
unseen holdouts for further selection. See [WORKFLOW.md](WORKFLOW.md).

## Move-quality measurement and regressions

The later dense study measures moves rather than predicting which move a human
will choose. Stockfish 18 depth-12 evaluations before/after a move are converted to
mover-perspective loss. The shared logistic score transform was fit to realized
White score (win 1, draw 0.5, loss 0) on 89,764 pooled 10+0 training rows. Its saved
[report](reports/next_move_loss_combined.md) gives scale approximately 348.4 and
training MSE 0.183. This is a measurement transform, not proof of calibration across
all time controls.

[cross_time_control_analysis.py](src/chess_mhsuc/cross_time_control_analysis.py)
fits adjusted linear models of expected-score loss, plus a game-level logistic
model of time-forfeit. Within-control clock models weight rows equally; pooled
interaction models use game-normalized, equal-control-month weights.
[rating_clock_moderation.py](src/chess_mhsuc/rating_clock_moderation.py) also uses
game normalization within control and assesses rating interactions with clustered
uncertainty and multiplicity adjustment. These descriptive regression results are
not held-out prediction scores. [Sharpness analysis](src/chess_mhsuc/sharpness_interaction.py)
uses MultiPV value-fragility measures; the clock interaction remains unresolved.

## Limitations and intended use

The samples are nonrandom archive prefixes from two months. Players recur across
samples; player-clustered sensitivity does not remove all dependence or confounding.
Low-clock states concentrate late in games, phase is a move-number approximation,
and ratings differ across control pools. Time-forfeit filtering selects survivors.
Engine evaluations and the score transform are approximate measurements.

Use the code and reports to inspect or reproduce the study. Do not use these
models as a cheating detector, surveillance system, move recommender, rating system,
or evidence that time pressure causes worse reasoning. Real tables, prediction
files, hashes, fitted transform JSON, and model artifacts are local-only.
