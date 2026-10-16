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

Verification is recorded in the [dated cleanup report](reports/phase_reports/documentation_cleanup.md).
The route below was inspected against implementation and CLI help; its production
commands were not executed during the documentation follow-up. No data download,
engine analysis, transform fit, model training, or output regeneration was performed.

## 7. Reproducing figures

This ordered route builds the prerequisites for the six dense Parquets, then the
benchmark figures. It is a documented full workflow, not a verified end-to-end run.
All production commands below were **checked by inspection only**. Lightweight CLI
checks ran the nine modules' `--help` entry points and validated the 20 expanded
argument sets, stopping immediately after argument parsing. No stage processed
data. The unchanged README synthetic example was not rerun. A fresh clone has
none of the required real data.

Use the README environment setup first. Most stages use python-chess and Polars;
compressed input needs zstandard, splits need NumPy/scikit-learn, transform fitting
needs NumPy/SciPy, and plotting needs NumPy/Polars/Matplotlib. SciPy is used by the
implementation and is available through the scientific Python dependency stack;
it is not separately pinned in `requirements.txt`. Engine stages also require a
local Stockfish executable, with version 18 and depth 12 recorded for the saved runs.
These commands do not reproduce the outcome-model training or inferential reports;
those are separate branches described in section 3 and the model card.

### 7.1. Choose separate destinations

Run the blocks in order from the repository root, in the same Bash session. Choose
an unused output directory and suffix. This example keeps new data and reports under
`data/reproduction/`, except for the two checkpoint evaluation Parquets required at
fixed paths by the transform fitter. Their new suffix separates them from originals.
Confirm the engine path and version before a later engine run.

```bash
set -e
export PYTHONPATH=src
REPRO_ROOT=data/reproduction/docs_followup_20261016
REPRO_SUFFIX=repro_20261016
REPRO_STOCKFISH=/opt/homebrew/bin/stockfish

test ! -e "$REPRO_ROOT"
for month in 2024_09 2024_10; do
  test ! -e "data/processed/sf_eval_broad_${month}_250k_${REPRO_SUFFIX}.parquet"
done
mkdir -p "$REPRO_ROOT/raw" "$REPRO_ROOT/interim" \
  "$REPRO_ROOT/processed" "$REPRO_ROOT/reports" data/processed
```

This preparation was not run. Some writers do not guard against existing paths;
choose new destinations rather than adding overwrite flags. No command here writes
into committed `reports/` or `reports/figures/`.

### 7.2. Acquire archive prefixes and parse 10+0 metadata

Entry point: [run_parser.main](src/chess_mhsuc/run_parser.py). Requires network access
to the two standard-rated archives and python-chess, Polars, and zstandard. It streams
compressed input, stops at 250,000 raw games, and writes the consumed uncompressed
PGN prefix through `--raw-cache`. The prefix includes all time controls, even though
the stored parser game/position tables are 10+0. Do not add `--max-accepted`, which
could stop before the desired raw-game cap.

```bash
for month in 2024_09 2024_10; do
  month_dash="${month/_/-}"
  python -m chess_mhsuc.run_parser \
    --url "https://database.lichess.org/standard/lichess_db_standard_rated_${month_dash}.pgn.zst" \
    --source-file "lichess_db_standard_rated_${month_dash}.pgn.zst" \
    --max-games 250000 --version-tag "$REPRO_SUFFIX" \
    --output-dir "$REPRO_ROOT/interim" \
    --raw-cache "$REPRO_ROOT/raw/lichess_${month}_first250k.pgn"
done
```

Outputs per month, with `tag=${month}_250k_${REPRO_SUFFIX}`:
`game_records_<tag>.parquet`, `position_records_<tag>.parquet`, and
`parser_validation_<tag>_metadata.json` under `interim/`, plus the raw cache above.
Check scan counts, parse errors, and acceptance counts before proceeding. A consumed
prefix may include parser lookahead; preserve the actual cache for replay.

Status: production command inspected only; `--help` executed successfully.
The CLI has no local-input flag. With an existing cache, `stream_and_parse` is the
implemented in-memory entry point and `write_outputs` writes its tables/metadata;
using that API requires supplying its explicit provenance/output arguments. Do not
invent `run_parser --input` or silently substitute a different prefix.

### 7.3. Clean positions, build features, and assign splits

Entry points: [cleaning.main](src/chess_mhsuc/cleaning.py),
[features.main](src/chess_mhsuc/features.py), and [splits.main](src/chess_mhsuc/splits.py).
Requires the parser outputs, Polars, NumPy, and scikit-learn. Cleaning produces the
10+0 game table, broad/eval position tables, and a metadata JSON. Features produces
broad/eval feature tables and `feature_metadata_<tag>.json`. Splits consumes both
feature tables and that metadata, and writes assignments and a modeling plan;
it does not train a predictor.

```bash
for month in 2024_09 2024_10; do
  tag="${month}_250k_${REPRO_SUFFIX}"
  python -m chess_mhsuc.cleaning \
    --game-records "$REPRO_ROOT/interim/game_records_${tag}.parquet" \
    --position-records "$REPRO_ROOT/interim/position_records_${tag}.parquet" \
    --output-dir "$REPRO_ROOT/processed" --version-tag "$tag"
  python -m chess_mhsuc.features \
    --positions-broad "$REPRO_ROOT/processed/ten_zero_positions_broad_${tag}.parquet" \
    --positions-eval "$REPRO_ROOT/processed/ten_zero_positions_eval_${tag}.parquet" \
    --output-dir "$REPRO_ROOT/processed" --version-tag "$tag"
  python -m chess_mhsuc.splits \
    --dataset-id "lichess_ten_zero_${tag}" --version-tag "$tag" \
    --feature-broad "$REPRO_ROOT/processed/feature_positions_broad_${tag}.parquet" \
    --feature-eval "$REPRO_ROOT/processed/feature_positions_eval_${tag}.parquet" \
    --feature-metadata "$REPRO_ROOT/processed/feature_metadata_${tag}.json" \
    --output-dir "$REPRO_ROOT/processed" \
    --report-output-dir "$REPRO_ROOT/reports/splits_${month}" \
    --train-frac 0.70 --val-frac 0.15 --seed 42
done
```

Split outputs are `splits_<tag>.json` and `modeling_plan_<tag>.json`. The report
basename is hardcoded to `phase_5_1b_modeling_split_baseline_plan_implementation.md`;
separate month directories prevent collisions. Its template includes historical
test language, not evidence that tests ran during a reproduction. Assessment and
dataset-card generators are optional reporting branches, not required inputs to the
engine or dense stages. Status: production commands inspected only; all three help
commands executed successfully.

### 7.4. Evaluate numbered checkpoints with Stockfish

Entry point: [stockfish_eval.main](src/chess_mhsuc/stockfish_eval.py). Requires the
cleaned broad positions, their split assignments, the matching raw PGN prefix,
python-chess/Polars/zstandard, and Stockfish. `--splits` is optional in the CLI but
required here: the next stage selects rows whose `split_set` is `train`.
Omit `--include-last` to retain the numbered-checkpoint view.

```bash
for month in 2024_09 2024_10; do
  tag="${month}_250k_${REPRO_SUFFIX}"
  python -m chess_mhsuc.stockfish_eval \
    --dataset-id "lichess_ten_zero_${tag}" --version-tag "$tag" \
    --positions "$REPRO_ROOT/processed/ten_zero_positions_broad_${tag}.parquet" \
    --splits "$REPRO_ROOT/processed/splits_${tag}.json" \
    --raw-pgn "$REPRO_ROOT/raw/lichess_${month}_first250k.pgn" \
    --stockfish-path "$REPRO_STOCKFISH" --depth 12 \
    --output-parquet "data/processed/sf_eval_broad_${tag}.parquet" \
    --output-metadata "$REPRO_ROOT/processed/sf_eval_metadata_${tag}.json" \
    --output-report "$REPRO_ROOT/reports/stockfish_eval_${tag}.md"
done
```

The output Parquets contain checkpoint evaluations, result labels, and split labels;
they must be available for both months before fitting the common score transform.
Inspect failures and row/key coverage before proceeding. This is engine analysis,
not a smoke test. Status: production command inspected only; `--help` executed.
The engine was not started or version-verified in this follow-up.

### 7.5. Fit the expected-score transform

Entry point: [next_move_loss.main / load_fit_rows](src/chess_mhsuc/next_move_loss.py).
Requires both stage-7.4 Parquets, Polars, NumPy, and SciPy. This mode fits the single
logistic scale to realized game score on pooled training rows. It does not need
PGN replay, a fitted outcome classifier, or post-move checkpoint loss tables.

**Fixed input paths:** `load_fit_rows` reads
`data/processed/sf_eval_broad_<tag>.parquet`. In fitting mode, `--sf-eval` and
`--features` do not redirect those reads. The new tags in stage 7.4 are therefore
part of this recipe, not arbitrary filename decoration.

```bash
python -m chess_mhsuc.next_move_loss \
  --dataset-id "lichess_ten_zero_2024_09_250k_${REPRO_SUFFIX}" \
  --version-tag "2024_09_250k_${REPRO_SUFFIX}" \
  --fit-es-transform \
  --fit-version-tags "2024_09_250k_${REPRO_SUFFIX},2024_10_250k_${REPRO_SUFFIX}" \
  --es-transform-out "$REPRO_ROOT/processed/expected_score_transform.json"
```

Output: JSON containing `scale`, fit counts, MSE, clipping, version tags, and time.
The saved original fit used 89,764 training rows and scale about 348.4; these are
comparison values from [the extraction record](reports/next_move_loss_combined.md),
not guaranteed outputs of an unverified rerun. Reusing the recorded full-precision
fit would require its local-only JSON. Status: fitting command inspected only;
`--help` executed. No transform was fitted.

Optional historical branch: `next_move_loss.main` without `--fit-es-transform`
evaluates the move after each checkpoint, using `--sf-eval`, `--features`, `--raw-pgn`,
`--es-transform`, and an explicit `--limit` or `--allow-full-run`, with `--output`
and `--report` overrides. Those checkpoint loss tables are not prerequisites for
dense extraction, which evaluates its own consecutive positions.

### 7.6. Extract player metadata from each raw prefix

Entry point: [player_metadata.main](src/chess_mhsuc/player_metadata.py). Requires
uncompressed PGN prefixes and Polars. It reads all controls in the prefix, so the
same month-level metadata can serve 3+0, 5+0, and 10+0. It writes game IDs, player
hashes, bot flags, and a version tag, without raw username columns. Use the same
pepper across months; the explicit value below is the implementation's public
project default, not a secret or a claim of irreversible anonymization.

```bash
for month in 2024_09 2024_10; do
  tag="${month}_250k_${REPRO_SUFFIX}"
  python -m chess_mhsuc.player_metadata \
    --dataset-id "lichess_ten_zero_${tag}" --version-tag "$tag" \
    --raw-pgn "$REPRO_ROOT/raw/lichess_${month}_first250k.pgn" \
    --pepper chess-mhsuc-player-v1 \
    --output "$REPRO_ROOT/processed/player_metadata_${tag}.parquet"
done
```

This stage can run any time after prefix acquisition, but its Parquets must exist
before dense extraction to reproduce player-hash coverage. Status: production
command inspected only; `--help` executed. No player records were extracted.

### 7.7. Build the six dense Parquets

Entry point: [dense_move_loss.main](src/chess_mhsuc/dense_move_loss.py). Requires the
raw prefixes, fitted transform, player metadata, and Stockfish plus python-chess,
Polars, and zstandard. The 10+0 route also reads the **interim parser game records**
for `accepted_basic` and time control, plus split metadata. Do not substitute the
cleaned game population without documenting the changed sample. Games absent from
the checkpoint splits receive `split_set='unknown'` in dense output.

For 10+0, choose the matching month-specific full-run flag. It means all accepted
games in the supplied prefix, not the full source archive, and is restricted to
depth 12. The default 1,500-game pilot cap does not apply in this mode.

```bash
for month in 2024_09 2024_10; do
  tag="${month}_250k_${REPRO_SUFFIX}"
  month_dash="${month/_/-}"
  python -m chess_mhsuc.dense_move_loss \
    --raw-pgn "$REPRO_ROOT/raw/lichess_${month}_first250k.pgn" \
    --month "$month" --version-tag "$tag" \
    --game-records "$REPRO_ROOT/interim/game_records_${tag}.parquet" \
    --splits "$REPRO_ROOT/processed/splits_${tag}.json" \
    --time-control 600+0 --allow-full-month-${month_dash} \
    --min-move-number 5 --depth 12 --stockfish-path "$REPRO_STOCKFISH" \
    --expected-score-transform "$REPRO_ROOT/processed/expected_score_transform.json" \
    --player-metadata "$REPRO_ROOT/processed/player_metadata_${tag}.parquet" \
    --chunk-size 5000 --chunk-dir "$REPRO_ROOT/chunks/${month}_10plus0" \
    --out "$REPRO_ROOT/processed/dense_move_loss_${month}_10plus0.parquet" \
    --report "$REPRO_ROOT/reports/dense_move_loss_${month}_10plus0.md"
done
```

For the other controls, accepted games come directly from raw headers, capped at
24,000 per control/month. Both gate flags are required for this cap; the implemented
branch uses chunked extraction despite the older “pilot only” wording in help.

```bash
for month in 2024_09 2024_10; do
  tag="${month}_250k_${REPRO_SUFFIX}"
  for minutes in 3 5; do
    control_tag="${minutes}plus0"
    python -m chess_mhsuc.dense_move_loss \
      --raw-pgn "$REPRO_ROOT/raw/lichess_${month}_first250k.pgn" \
      --month "$month" --version-tag "$tag" \
      --time-control "${minutes}+0" --allow-time-control-pilot \
      --max-accepted-games 24000 --pilot-override-allow-large \
      --min-move-number 5 --depth 12 --stockfish-path "$REPRO_STOCKFISH" \
      --expected-score-transform "$REPRO_ROOT/processed/expected_score_transform.json" \
      --player-metadata "$REPRO_ROOT/processed/player_metadata_${tag}.parquet" \
      --chunk-size 5000 --chunk-dir "$REPRO_ROOT/chunks/${month}_${control_tag}" \
      --out "$REPRO_ROOT/processed/dense_move_loss_${month}_${control_tag}.parquet" \
      --report "$REPRO_ROOT/reports/dense_move_loss_${month}_${control_tag}.md"
  done
done
```

Outputs: six dense Parquets, six extraction reports, per-run chunks, and chunk
manifests. Keep chunks for deliberate resumption; no cleanup or overwrite flag is
shown. Before plotting, inspect key uniqueness, engine/replay failures, clock
coverage, both mover colors, and player-hash coverage. A missing transform path
only warns and leaves expected-score columns null, so file existence and valid
`scale` are prerequisites, not optional conveniences.

Status: both production blocks inspected only; `--help` executed. These are
multi-hour engine workloads. The October 10+0 report compares against hardcoded
historical September summary constants, not the newly reproduced September file;
that comparison is not independent verification of the new run.

### 7.8. Generate descriptive figures and count tables

Entry point: [benchmark_figures.main](src/chess_mhsuc/benchmark_figures.py). Requires
all six dense Parquets, NumPy, Polars, and Matplotlib. It filters the headline
population, creates weights, and writes 12 PNGs and a Markdown count table. It
performs no engine analysis or inferential model fitting. Both output arguments
are explicit to avoid replacing committed artifacts.

```bash
python -m chess_mhsuc.benchmark_figures \
  --dense-2024-09-3plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_09_3plus0.parquet" \
  --dense-2024-09-5plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_09_5plus0.parquet" \
  --dense-2024-09-10plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_09_10plus0.parquet" \
  --dense-2024-10-3plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_10_3plus0.parquet" \
  --dense-2024-10-5plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_10_5plus0.parquet" \
  --dense-2024-10-10plus0 "$REPRO_ROOT/processed/dense_move_loss_2024_10_10plus0.parquet" \
  --figure-dir "$REPRO_ROOT/benchmark_figures" \
  --count-tables "$REPRO_ROOT/benchmark_counts.md"
```

Status: production command inspected only; `--help` executed. The six input files
are absent, so figures and numerical results were not regenerated. The unchanged
generator still calls this operation “read-only” and emits the old count-table
weighting prose. Its new output would need the same explanatory qualification as
the [annotated saved count table](reports/figures/benchmark/count_tables.md).

Historical extraction records: [September 10+0](reports/phase_reports/phase_15_3c_full_dense_move_loss_extraction.md),
[October 10+0](reports/phase_reports/phase_15_3d_full_dense_move_loss_replication_month.md),
and [3+0/5+0](reports/phase_reports/phase_16_1c_full_matched_size_3plus0_5plus0_dense_extraction.md).
Their original local paths and next-step statements remain historical. The new
paths above are reproduction destinations, not assertions that those artifacts
already exist or will exactly reproduce saved values in a different environment.

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
