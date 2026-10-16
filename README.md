# chess_MHSUC: human chess under clock constraints

How does the time left on a player's clock relate to their next move and the final
result? Chess provides recorded decisions, player ratings, and clock annotations,
plus an engine-based reference for evaluating moves. It also has a complication:
a player can lose by running out of time even when their board position is good.

I built a Python pipeline to study these two questions separately: whether clocks
improve outcome prediction beyond engine evaluation and ratings, and whether low
remaining time is associated with worse moves. The completed work is an
observational replication and benchmark study, not a new chess engine or a causal
study of reasoning. Saved reports cover 10+0 outcome models and a later move-quality
analysis of 3+0, 5+0, and 10+0 games.

The outcome-model improvement is concentrated in games ending on time. The separate
move-quality analysis finds a small adjusted low-clock association that remains
among games not ending on time. Neither result establishes why an individual player
made a mistake.

## Data and scope

The source is the [Lichess standard rated game database](https://database.lichess.org/),
using the first 250,000 games in each September and October 2024 archive. These are
archive prefixes, not random samples or complete months. Here, 3+0 means three
minutes per player with no increment; 5+0 and 10+0 work the same way.

The 10+0 parser requires standard chess, positive integer ratings, a recognized
result, and clock annotations; cleaning removes abandoned games. The later 3+0 and
5+0 extraction selects the first 24,000 accepted games per control and month using
time control, game ID, integer ratings, result, and termination headers. Rated and
standard provenance comes from the source archive; these routes do not independently
validate every aspect of an arbitrary PGN. See [pipeline details](PIPELINE_OVERVIEW.md).

Dense extraction measures both players' moves from full move 5 onward. Headline
analysis excludes engine failures and mate-band evaluations, and requires non-null
loss, clock, rating, and termination fields. Clock anomalies remain flagged in the
main analysis and are excluded in sensitivity checks. The resulting denominators are:

| Control | Month | Games with headline rows | Move observations |
|---|---|---:|---:|
| 3+0 | September 2024 | 23,703 | 1,422,173 |
| 3+0 | October 2024 | 23,721 | 1,420,818 |
| 5+0 | September 2024 | 23,756 | 1,367,293 |
| 5+0 | October 2024 | 23,734 | 1,364,419 |
| 10+0 | September 2024 | 25,582 | 1,416,313 |
| 10+0 | October 2024 | 24,524 | 1,362,459 |
| **Total** | | **145,020** | **8,353,475** |

These are post-filter counts, not the number initially scanned or accepted. The
[count tables](reports/figures/benchmark/count_tables.md) give the denominators and
rating-bin counts. An earlier [25,000-game pilot](reports/phase_reports/dataset_card_lichess_ten_zero_2024_09_25k_v1.md)
produced 8,528 checkpoint rows from 2,323 games and is a separate evaluation sample.

Raw PGNs, processed tables, prediction files, fitted transform metadata, and model
artifacts are not distributed. Raw PGNs can contain usernames; processed tables
omit them, with salted player hashes used for dependence checks. Only the small
synthetic fixture is included as game data. See [DATA_POLICY.md](DATA_POLICY.md).

## Implemented approach

| Stage | Implementation |
|---|---|
| Read PGNs, extract clocks and existing evaluations, clean and build features | [parser](src/chess_mhsuc/parse_pgn.py), [streaming entry point](src/chess_mhsuc/run_parser.py), [cleaning](src/chess_mhsuc/cleaning.py), [features](src/chess_mhsuc/features.py) |
| Compare outcome probabilities for White win, draw, and Black win | [game-level splits](src/chess_mhsuc/splits.py), [dummy/logistic baselines](src/chess_mhsuc/baselines.py), [histogram gradient boosting](src/chess_mhsuc/gbm.py), [fixed-evaluation logistic models](src/chess_mhsuc/eval_conditioned_modeling.py) |
| Diagnose probabilities and separate termination groups | [calibration diagnostics](src/chess_mhsuc/calibration.py), [termination comparison](src/chess_mhsuc/termination_decomposition.py) |
| Measure next-move quality and compare clock states | [Stockfish evaluation](src/chess_mhsuc/stockfish_eval.py), [dense extraction](src/chess_mhsuc/dense_move_loss.py), [cross-control models](src/chess_mhsuc/cross_time_control_analysis.py), [rating interactions](src/chess_mhsuc/rating_clock_moderation.py) |
| Account for repeated observations and draw figures | [clustered uncertainty](src/chess_mhsuc/clustered_uncertainty.py), [benchmark figures](src/chess_mhsuc/benchmark_figures.py) |

Outcome experiments use a 70/15/15 split by game ID, stratified by result, with seed
42. Numbered checkpoints follow Black's moves 10, 20, 30, and 40; the final-position
rows are excluded from primary modeling. The later dense analyses are descriptive
and adjusted regressions over observed moves, not held-out prediction benchmarks.

Move quality uses Stockfish 18 at depth 12. A centipawn is one hundredth of a pawn
on the engine's evaluation scale. **Expected-score loss** maps clipped evaluations
to a score between 0 and 1, then takes the non-negative drop from before to after
the played move, from the mover's perspective. A loss of 0.01 is one percentage
point on that fitted score scale, not an observed probability of making a mistake.
The logistic transform was fit on pooled 10+0 training rows and reused across
controls. Clipped centipawn loss provides a second measurement. Engine scores are
approximations, not ground truth.

## Saved results

**Outcome prediction, 10+0 checkpoints.** E3 uses fixed-depth evaluation and ratings;
E4 adds clocks. Log loss is the mean negative log probability assigned to the actual
three-class result, so lower is better. The table reports `log_loss(E4) - log_loss(E3)`
on frozen validation predictions, with paired game-bootstrap 95% confidence intervals.
The September evaluation has 9,823 rows from 3,678 games; October has 3,524 validation
games. The termination groups are filtered after prediction, without retraining.

| Validation group | September delta [95% CI] | October delta [95% CI] |
|---|---|---|
| All games | -0.0138 [-0.0186, -0.0091] | -0.0120 [-0.0177, -0.0062] |
| Not time-forfeit | +0.0010 [-0.0029, +0.0049] | +0.0060 [+0.0015, +0.0109] |
| Time-forfeit | -0.1183 [-0.1423, -0.0978] | -0.1305 [-0.1525, -0.1091] |

Adding clocks helps mainly in time-forfeit games. In the other games it provides no
clear improvement in September and slightly worsens October log loss. Sources:
[termination decomposition](reports/termination_decomposition_combined.md) and
[September ablation](reports/eval_conditioned_modeling_2024_09_250k_v1.md).

**Move quality, all three controls.** In the six dense samples above, adjusted
critical-versus-high-clock contrasts in expected-score loss are:

| Control | All games [95% CI] | Not time-forfeit [95% CI] |
|---|---|---|
| 3+0 | +0.0117 [+0.0109, +0.0126] | +0.0062 [+0.0044, +0.0077] |
| 5+0 | +0.0077 [+0.0069, +0.0086] | +0.0051 [+0.0033, +0.0069] |
| 10+0 | +0.0056 [+0.0046, +0.0067] | +0.0031 [+0.0014, +0.0047] |

Critical means at most 5% of initial time remains; high means more than 50%.
These pooled-month, within-control regressions adjust for evaluation band, phase,
rating quintile, month, mover color, termination where applicable, and clock anomalies.
They weight move rows equally and bootstrap whole games. Pooled cross-control
interaction models and headline figures instead use game-normalized weights.
See the [cross-control report, sections 10, 14, and 16](reports/cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md)
for month-specific results and player-clustered checks. The unadjusted curves are
U-shaped; they should not be read as these adjusted contrasts.

Time-forfeit rates in the headline game samples are 29.17%/30.09% for 3+0,
22.63%/22.58% for 5+0, and 11.51%/11.64% for 10+0 (September/October).
These are game proportions, not shares of move rows. The
[figures](reports/figures/benchmark/) and [appendix index](reports/appendix_figure_index.md)
show the descriptive patterns.

## Limitations and negative findings

- These are observational associations. Filtering out time-forfeit games selects a
  different population; it does not isolate a causal effect of time pressure.
  The code's “board-decided” group means not time-forfeit, including other
  termination categories. `Normal` does not distinguish resignation from checkmate.
- Archive prefixes cover only two months. Players recur across games, splits, and
  months, so the monthly results are not independent replications. Player-clustered
  checks address some dependence but do not create a player-disjoint holdout.
- Very low clock is concentrated in late-game positions. Phase is approximated by
  move number, and rating pools differ across controls. Reusing the 10+0 score
  transform across controls is a measurement assumption.
- The pilot gradient-boosted model overfit: validation log loss was 1.2326 versus
  0.8527 for the logistic baseline on 931 rows. Broad GBMs had zero draw recall.
  [Evaluation](reports/gbm_evaluation_2024_09_25k_v1.md) and
  [calibration diagnostics](reports/calibration_2024_09_25k_v1.md) document this;
  no fitted post-hoc calibrator is provided.
- The [rating interaction](reports/rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md)
  changes direction under endgame restriction. There is no universal “rating protects
  against time pressure” result. The [sharpness interaction](reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md)
  remains underpowered and unresolved.

## Setup and small example

Run from the repository root. [.python-version](.python-version) specifies Python
3.13.11. The example needs only `python-chess`; it reads the existing synthetic PGN
and writes no files. The fixture's comments are parser test inputs, not meaningful
engine analysis of the game.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install 'python-chess>=1.999'
export PYTHONPATH=src
python - <<'PYTHON'
from pathlib import Path
import chess.pgn
from chess_mhsuc.parse_pgn import parse_game

with Path('tests/fixtures/tiny_clock_eval_game.pgn').open() as stream:
    game = chess.pgn.read_game(stream)
record, positions = parse_game(game)
print(record.game_id, record.result_class, record.n_plies)
for position in positions:
    print(position.selected_position_type, position.ply,
          position.white_clock_s, position.black_clock_s, position.eval_cp)
PYTHON
```

Expected output (checkpoint, half-move number, White/Black seconds, evaluation):

```text
synth0001 WHITE_WIN 82
move_10 20 500 500 10000
move_20 40 470 470 -10000
move_30 60 440 440 25
move_40 80 410 410 None
last 82 407 407 None
```

`None` means the checkpoint has no evaluation annotation; earlier evaluations are
not carried forward. Values of +/-10000 are the parser's mate sentinels.

For the analysis modules and tests, install the existing dependency list:

```bash
python -m pip install -r requirements.txt
python -m pytest -q tests/test_parse_pgn.py tests/test_benchmark_figures.py
```

The dependency file contains minimum versions, not a locked environment. This
cleanup ran the example and 136 selected tests on Python 3.13.11 using available
packages; it did not perform a fresh dependency installation or rerun research.
[Full reproduction prerequisites and figure command](PIPELINE_OVERVIEW.md#7-reproducing-figures)
are separate from this smoke example.

## Status and further reading

Completed work includes the checkpoint pipeline, baseline and tree experiments,
calibration diagnostics, fixed-depth engine evaluation, termination comparisons,
dense move-quality analyses, and saved figures. The research log closes with public
packaging work; there is no active research run. Neural sequence models, increment
comparisons, richer position-difficulty measures, and a better-powered sharpness
study remain deferred proposals.

[MODEL_CARD.md](MODEL_CARD.md) describes the implemented model families.
[MANIFEST.md](MANIFEST.md) indexes the technical records.
[ROADMAP.md](ROADMAP.md) separates current status from historical plans, and
[EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) preserves the sequence of experiments.
The [historical benchmark report](reports/benchmark_report.md) remains unchanged;
use this README and the pipeline guide for current scope and reproduction details.
In particular, its transform JSON is local-only and its two months share players.

This work uses established move-quality metrics and studies associations already
examined in chess research. [Related work](docs/RELATED_WORK.md) and the
[repository-overlap audit](reports/phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md)
record attribution and the decision to use replication framing. No priority or
state-of-the-art claim is made. Original code and documentation use the
[MIT license](LICENSE); [NOTICE.md](NOTICE.md) records third-party scope.
