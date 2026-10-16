# Pipeline overview

This guide describes the implementation in this checkout. Two connected paths
exist: 10+0 checkpoint outcome modeling and dense move-quality analysis across
three no-increment controls. The [README](README.md) summarizes the results;
[MODEL_CARD.md](MODEL_CARD.md) describes the models.

## 1. Inputs and provenance

Recorded sources are `lichess_db_standard_rated_2024-09.pgn.zst` and
`lichess_db_standard_rated_2024-10.pgn.zst` from the
[Lichess database](https://database.lichess.org/). The large runs use the first
250,000 raw games per archive. “Full month” in older filenames and CLI flags means
all accepted 10+0 games in the cached prefix, not the complete monthly database.

The initial 25,000-game scan and subsequent 250,000-game scans are distinct dataset
versions. Real inputs and derived artifacts are local-only under `data/`.
[DATA_POLICY.md](DATA_POLICY.md) defines their handling.

## 2. Checkpoint parsing and cleaning

[source_scan.py](src/chess_mhsuc/source_scan.py) inspects source availability.
[run_parser.py](src/chess_mhsuc/run_parser.py) streams a compressed archive with an
explicit `--max-games` cap, optionally caching the consumed prefix with `--raw-cache`.
Its CLI accepts `--url`, not a local `--input` path. For a local synthetic PGN, use
`parse_game` as in the README.

[parse_pgn.py](src/chess_mhsuc/parse_pgn.py) accepts `600+0`, absent or `Standard`
variant, positive integer ratings, a recognized result, and some clock annotation.
Rated provenance comes from the rated archive: the parser does not reject a custom
PGN solely because its Event says casual. It parses main-line moves, drops username
fields, and records rejection reasons. Clock annotations refer to the side that
just moved; the other player's latest clock is carried forward. Missing evaluations
remain missing. [schemas.py](src/chess_mhsuc/schemas.py) defines fields and mate sentinels.

Checkpoints are after plies 20/40/60/80 plus the last ply for games reaching ply 20.
The last row can duplicate a numbered checkpoint's ply, so checkpoint joins use
`(game_id, selected_position_type)`. Primary modeling excludes `last`.
[cleaning.py](src/chess_mhsuc/cleaning.py) retains accepted games with a non-abandoned
termination, keeps time forfeits, and separates broad from evaluation-annotated rows.
Null termination also fails its filter. [features.py](src/chess_mhsuc/features.py)
adds rating, clock, evaluation, and position fields, with explicit anomaly flags.

## 3. Outcome prediction

[assess_dataset.py](src/chess_mhsuc/assess_dataset.py) and
[dataset_version.py](src/chess_mhsuc/dataset_version.py) record counts and provenance.
[splits.py](src/chess_mhsuc/splits.py) assigns whole games to 70/15/15
train/validation/test partitions, stratified by result with seed 42. The
evaluation-annotated subset inherits these assignments.

[baselines.py](src/chess_mhsuc/baselines.py) implements dummy and logistic models;
[gbm.py](src/chess_mhsuc/gbm.py) implements `HistGradientBoostingClassifier`.
[calibration.py](src/chess_mhsuc/calibration.py) measures reliability without fitting
a post-hoc calibrator. [stockfish_eval.py](src/chess_mhsuc/stockfish_eval.py) adds
fixed-depth local evaluations, and [eval_conditioned_modeling.py](src/chess_mhsuc/eval_conditioned_modeling.py)
compares logistic feature ablations using these evaluations.

Labels are White win, draw, and Black win. Result, termination, final game length,
and post-game rating changes are not predictive inputs. Termination is used
retrospectively in [termination_decomposition.py](src/chess_mhsuc/termination_decomposition.py)
to filter frozen validation predictions. Its board-decided flag is the complement
of time-forfeit, not a separately verified checkmate/resignation label.

## 4. Dense move-quality measurement

[next_move_loss.py](src/chess_mhsuc/next_move_loss.py) first measured the next move
from numbered checkpoints, which are White-to-move positions. It fits a pooled
10+0 training-only logistic centipawn-to-score transform. The saved
[transform report](reports/next_move_loss_combined.md) gives 89,764 training rows
and scale approximately 348.4; the full metadata JSON is local-only.

[dense_move_loss.py](src/chess_mhsuc/dense_move_loss.py) extends extraction to both
colors from full move 5 onward. For 10+0 it reads accepted game metadata. For 3+0 and
5+0, `build_accepted_meta_from_raw` selects up to 24,000 games in PGN order using
time control, game ID, integer ratings, recognized result, and nonempty termination.
This header path relies on the standard-rated archive for variant/rated provenance.
It is not identical to the 10+0 cleaning path.

Recorded runs use Stockfish 18, depth 12. Each pre-move position is evaluated once;
the next position's evaluation supplies the preceding move's post-move value.
Expected-score loss is `max(0, ES(before) - ES(after))` in mover perspective, with
`ES(cp) = 1 / (1 + exp(-clip(cp, -1000, 1000) / scale))`. Clipped centipawn loss is a
secondary metric. Finite-search differences can yield negative raw losses; the
expected-score loss floors these at zero. Mate-band rows are flagged separately.

Dense output includes moves, clocks before/after, engine provenance, loss metrics,
and local player hashes. Extraction supports explicit caps and chunked resumption.
The module's old “pilot only” docstring predates the full-run implementation; inspect
`main` and `--help` for the implemented flags. Full runs remain expensive.

## 5. Analysis populations and statistics

[cross_time_control_analysis.py](src/chess_mhsuc/cross_time_control_analysis.py)
requires successful non-mate rows with non-null loss, clocks, rating, and termination.
The main population retains clock/think-time anomalies with flags. Game-level
termination rates count one row per game represented in that population.

Clock fraction is seconds before moving divided by initial seconds. Critical,
low, medium, and high model buckets have boundaries 0.05, 0.15, and 0.50.
Rating quintiles are computed within control and month. Within-control regressions
weight rows equally; pooled interaction models use inverse game-size weights and
equal control-month aggregate weight. [rating_clock_moderation.py](src/chess_mhsuc/rating_clock_moderation.py)
uses game normalization even within control. These estimands are different.

Game-clustered uncertainty keeps moves from a game together. Player-clustered
sensitivity uses the local mover hash. Neither is a player-disjoint train/test
split. [player_metadata.py](src/chess_mhsuc/player_metadata.py) and
[clustered_uncertainty.py](src/chess_mhsuc/clustered_uncertainty.py) implement these
parts. [benchmark_figures.py](src/chess_mhsuc/benchmark_figures.py) draws descriptive,
game-normalized curves; these are not the adjusted regression contrasts.

## 6. Environment and verification

Use Python 3.13.11 and the setup in the [README](README.md#setup-and-small-example).
The source is imported using `PYTHONPATH=src`; there is no package installation
configuration. `requirements.txt` specifies lower bounds rather than exact pins.
Stockfish is a separate executable for engine extraction, unnecessary for the
synthetic parser example or reading reports.

During documentation verification, the parser example and 136 parser/figure-helper
tests passed on the available Python 3.13.11 environment. CLI help for `run_parser`,
`dense_move_loss`, and `benchmark_figures` ran successfully. Several available
packages were below the requirement minima and `duckdb` was absent; a fresh full
installation was not tested. See the [cleanup check record](reports/phase_reports/documentation_cleanup.md).

## 7. Reproducing figures

The figure CLI needs all six dense Parquets listed below. It reads the tables
without engine work, but **writes figures and a count table**. Both output arguments
are set explicitly here so a run does not replace the committed results.
Run this only after supplying the inputs and installing the analysis dependencies:

```bash
export PYTHONPATH=src
python -m chess_mhsuc.benchmark_figures \
  --dense-2024-09-3plus0 data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet \
  --dense-2024-09-5plus0 data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet \
  --dense-2024-09-10plus0 data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-2024-10-3plus0 data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet \
  --dense-2024-10-5plus0 data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet \
  --dense-2024-10-10plus0 data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --figure-dir data/reproduction/benchmark_figures \
  --count-tables data/reproduction/benchmark_counts.md
```

Expected artifacts are 12 PNG figures and a Markdown count table. This command's
options were checked against the CLI, but the command was not run in the fresh
clone because the six Parquets are absent.

Rebuilding those inputs is a separate, multi-stage workflow: cache the archive
prefixes, create 10+0 game/feature/split metadata, evaluate checkpoints, fit the score
transform on training rows, extract player hashes, and run dense evaluation. A
single `dense_move_loss` call cannot reconstruct all those prerequisites. The
[September full extraction record](reports/phase_reports/phase_15_3c_full_dense_move_loss_extraction.md),
[October replication record](reports/phase_reports/phase_15_3d_full_dense_move_loss_replication_month.md),
and [3+0/5+0 record](reports/phase_reports/phase_16_1c_full_matched_size_3plus0_5plus0_dense_extraction.md)
preserve the run decisions. Their original local paths and next-step instructions
are historical, not a one-command setup for a new clone.

## 8. Feature conventions and phase definitions

The checkpoint parser's phase convention is opening through move 10, middlegame
through move 35, and endgame after move 35. The dense extractor uses opening through
10, middlegame through 30, and endgame after 30. Both are move-number proxies, not
material-based board classifications. Do not silently combine these phase labels.

Checkpoint clocks are the latest annotated seconds after a move. Dense
`clock_before_s` is the mover's clock before the measured move. Evaluations use
White perspective in parser records and mover perspective for loss calculations.
Mate sentinel values and missing annotations have distinct meanings. Existing
Lichess evaluations are available only for a selected subset; the dense study uses
local fixed-depth engine evaluations instead.
