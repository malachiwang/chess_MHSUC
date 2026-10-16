# Project presentation notes

This file consolidates the earlier resume, LinkedIn, and interview variants. Use
[the README](../README.md) for the current scientific account and
[external launch notes](external_launch_materials.md) for repository metadata.

## Short description

I studied how remaining clock time relates to human chess outcomes and move quality.
I built a PGN-to-Parquet pipeline, compared outcome models, and measured moves using
Stockfish evaluations. In the 10+0 validation analysis, adding clocks mainly helped
predict games ending on time. A separate three-control analysis found smaller
adjusted low-clock differences in move quality even among other games.

## Resume bullets

- Built a Python pipeline for Lichess PGNs, clock and evaluation extraction, game-level
  splits, and dense Stockfish move-quality measurements; saved analyses cover 145,020
  games and 8,353,475 filtered move observations across three controls and two months.
- Compared logistic and gradient-boosted outcome models, documented pilot overfitting
  and weak draw prediction, and separated time-forfeit from other validation outcomes.
- Assessed conditional clock and rating associations with game- and player-clustered
  uncertainty, preserving negative findings and the limits of observational data.

## Technical explanation

The implementation has two parts. Outcome models predict White win, draw, or Black
win at selected 10+0 checkpoints. Dummy priors, logistic regression, and histogram
gradient boosting are implemented. The tree pilot overfit; fixed-evaluation logistic
ablations provide the later outcome comparison. Calibration was assessed, not fitted.

Move-quality analysis instead measures the change in engine evaluation around a
played move and maps it to expected-score loss. It uses both colors from move 5
onward, with control-specific adjusted regressions and separate descriptive figures.
The models, weighting conventions, and evaluation populations are in the
[model card](../MODEL_CARD.md). The dense study is not a new human-move predictor.

## Evidence to cite

| Statement | Supporting record |
|---|---|
| 145,020 games and 8,353,475 headline rows | [Count tables](figures/benchmark/count_tables.md) |
| Outcome-model gain concentrated in time forfeits | [10+0 termination comparison](termination_decomposition_combined.md) |
| Adjusted move-quality contrasts across three controls | [Cross-control analysis](cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md) |
| Tree pilot overfit | [GBM evaluation](gbm_evaluation_2024_09_25k_v1.md) |
| Rating interaction changes direction with conditioning | [Rating analysis](rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md) |
| Sharpness remains unresolved | [Checkpoint-overlap analysis](sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md) |

## Interpretation and reproduction

Describe associations rather than causal effects. The archive-prefix samples are
not representative random samples, players recur across months, and engine scores
are approximate references. Do not imply that filtering time forfeits perfectly
separates mechanical and behavioral mechanisms, or that all analyses use the same
weights or held-out population. Prior work motivates replication framing; absence
of an exact match in a bounded review does not establish novelty.

The repository includes code, reports, figures, and a runnable synthetic parser
example. It does not include the dense tables, prediction files, fitted transform
JSON, player metadata, or model weights. Full figure reproduction requires the
local artifacts described in the [pipeline guide](../PIPELINE_OVERVIEW.md).
Test counts from earlier release audits describe those recorded runs, not a fresh
verification in every environment.
