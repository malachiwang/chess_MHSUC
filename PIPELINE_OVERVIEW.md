# Pipeline Overview

This document describes the intended data and modeling pipeline for `chess-MHSUC`.

The pipeline should be developed incrementally. Each stage should be auditable and testable before downstream stages rely on it.

## 1. Pipeline summary

```text
Raw Lichess PGN archive
  -> source scan / sampling
  -> PGN parsing
  -> metadata extraction
  -> move replay
  -> clock/eval extraction
  -> cleaning and filtering
  -> label extraction
  -> feature engineering
  -> data assessment
  -> baseline models
  -> GBM models
  -> calibration and subgroup analysis
  -> reports
```

## 2. Stage 1: Data acquisition

Initial source:

```text
Lichess standard rated PGN database
```

Initial target:

```text
TimeControl "600+0"  # 10+0
```

This is ingestion, not open-ended web scraping.

The project should begin with capped samples. It should not start by downloading or processing massive files unless a ticket requires it.

Recommended first scan limits:

```text
1,000 games: parser smoke test
10,000 games: field availability sanity
25,000 games: first useful source audit
50,000 games: early modeling if enough eval/clock-qualified rows exist
```

## 3. Stage 2: Raw storage

Raw files live locally:

```text
data/raw/lichess/
```

Raw files are never committed.

Do not modify raw archives after download. Treat them as immutable input.

## 4. Stage 3: PGN parsing

Parser responsibilities:

- read PGN games,
- extract headers,
- identify time control,
- identify rated standard games,
- replay moves with `python-chess`,
- extract clock annotations,
- extract eval annotations when available,
- track parse errors/skips.

Important headers may include:

```text
Event
Site
Date
WhiteElo
BlackElo
Result
TimeControl
Termination
Variant
```

The parser should not silently assume every field exists.

## 5. Stage 4: Initial filtering

Initial filters:

```text
Include:
- standard chess
- rated games
- TimeControl "600+0"
- valid result
- valid ratings

Exclude:
- variants
- unrated/casual games
- games with invalid/missing critical fields
```

Do not exclude terminations by default. Timeouts, resignations, checkmates, and draws should remain unless a specific experiment says otherwise.

## 6. Stage 5: Label extraction

Primary label:

```text
white_win / draw / black_win
```

Recommended encoding:

```text
result_class:
  WHITE_WIN
  DRAW
  BLACK_WIN

white_result_numeric:
  1.0 for White win
  0.5 for Draw
  0.0 for Black win
```

Binary labels may be derived for debugging:

```text
white_win_vs_not
non_draw_outcome
```

Binary labels are not the final main task.

## 7. Stage 6: Move/position extraction

Long-term target:

```text
every ply / every position
```

Initial pilot:

```text
selected checkpoints first
```

Candidate checkpoint positions:

```text
after move 10
after move 20
after move 30
after move 40
final available pre-result position
```

Checkpoint extraction reduces compute and debugging complexity. It must not redefine the final project goal.

## 8. Stage 7: Feature engineering

Core features:

```text
game_id
ply_number
move_number
side_to_move
white_elo
black_elo
elo_diff
white_clock_seconds
black_clock_seconds
clock_diff_seconds
white_low_time_flag
black_low_time_flag
time_control
termination
result_class
white_result_numeric
```

Eval features when available:

```text
eval_cp_white_pov
eval_abs_cp
eval_bucket
mate_flag
mate_distance_if_available
```

Phase features:

```text
phase_simple:
  opening
  middlegame
  endgame
```

Initial phase approximation:

```text
opening: move <= 10
middlegame: 11 <= move <= 35
endgame: move > 35
```

Later phase improvements may use material count or board features.

Rating features:

```text
rating_bucket_white
rating_bucket_black
rating_bucket_pair
rating_gap_bucket
```

Clock-pressure features:

```text
white_under_60
black_under_60
white_under_30
black_under_30
white_under_10
black_under_10
both_under_30
one_sided_time_pressure
```

## 9. Stage 8: Data assessment

Before modeling, every dataset version needs an assessment report.

Minimum checks:

```text
number of games scanned
number of games included
number of positions/rows generated
skip reasons
missing values by column
rating distribution
result distribution
termination distribution
clock distribution
eval availability
time-control verification
move-count distribution
```

For 10+0, the audit should explicitly count or estimate:

```text
How many scanned games are TimeControl "600+0"?
How many qualifying 10+0 games have clock data?
How many qualifying 10+0 games have eval data?
How many usable checkpoint rows survive?
```

## 10. Stage 9: Baselines

Baseline models are mandatory.

Minimum baselines:

```text
B0: majority-class / empirical prior
B1: rating-only
B2: eval-only
B3: eval + rating
B4: eval + rating + clocks
B5: eval + rating + clocks + phase
```

Each baseline should be evaluated on the same split.

## 11. Stage 10: GBM modeling

First serious model family:

```text
Gradient-boosted decision trees
```

Recommended progression:

```text
1. scikit-learn HistGradientBoostingClassifier for simplest local baseline.
2. XGBoost if stronger performance/control is needed.
3. Calibration wrapper or post-hoc calibration after a stable GBM exists.
```

LightGBM is viable later, but not necessary for the initial implementation.

## 12. Stage 11: Evaluation

Preferred metrics:

```text
log loss
Brier score
calibration curve
confusion matrix
class-wise performance
ablation table
```

Subgroup analysis should include:

```text
rating buckets
phase
low-time state
termination type
eval buckets
```

Accuracy alone is not sufficient.

## 13. Stage 12: Splitting and leakage prevention

Default split unit:

```text
game_id
```

Do not split rows independently if multiple rows come from the same game.

Acceptable splits:

```text
train/validation/test by game_id
time-based holdout later
player-disjoint split later if hashed IDs are retained
```

The first pipeline should use game-level splitting.

## 14. Stage 13: Fixed-depth Stockfish validation

The MVP may use existing Lichess `%eval` annotations.

Later validation should sample games/positions and evaluate them locally with fixed Stockfish settings.

Recommended validation strategy:

```text
sample selected positions only
run fixed-depth or fixed-node Stockfish
compare conclusions against existing-eval dataset
report selection-bias concerns
```

Avoid evaluating every move of every game until there is a clear reason.

## 15. Stage 14: Neural sequence model extension

Neural sequence models are future work, not initial scope.

Possible later models:

```text
LSTM
GRU
small transformer
temporal convolution
```

Use only after:

- parser is stable,
- tabular baseline works,
- GBM results justify a sequence approach,
- compute requirements are understood.

## 16. Lichess PGN format assumptions

The following format details are assumed based on known Lichess PGN conventions. They must be verified against real sample data during Ticket 1.1A (source availability audit) and documented precisely during Ticket 2.1A (PGN schema audit). Do not write a parser that assumes these without testing them.

**Clock annotations**

Clock times are expected to appear as move-comment annotations in the form:

```text
{ [%clk H:MM:SS] }
```

The exact format (hours always present, precision, edge cases near zero) must be verified on real examples and tested explicitly.

**Eval annotations**

Eval values are expected to appear as move-comment annotations in the form:

```text
{ [%eval 0.47] }    # centipawn-like decimal, White-pov
{ [%eval #3] }      # forced mate in 3 for side to move
{ [%eval #-2] }     # opponent has forced mate in 2
```

Sign convention (positive = White advantage) must be verified and confirmed in parser tests. Mate notation must be handled as a distinct case from numeric evals.

**Variant header**

Standard chess games may omit the `Variant` header entirely. The filter for standard games must not require `Variant "Standard"` to be present; it should accept games where `Variant` is absent or explicitly `"Standard"`.

**UTCDate / UTCTime headers**

Lichess PGN files include `UTCDate` and `UTCTime` headers. These are not currently used as features, but should be inspected during schema audits. They are relevant if time-based train/validation/test splits are considered in later phases.

**WhiteRatingDiff / BlackRatingDiff headers**

These headers record the rating-point change after the game. They are not a default feature but should be noted during schema audits. They may be useful for identifying provisional-rating games if filtering is needed.

**Streaming `.pgn.zst` archives**

Lichess monthly archives are distributed as `.pgn.zst` (Zstandard-compressed PGN). The `zstandard` Python library supports streaming decompression. This must be verified on a real sample before the parser is committed. Do not assume full decompression to disk is required or safe given file sizes.

**Eval availability is not universal**

`%eval` annotations are only present for games where a user requested computer analysis or where Lichess automatically analyzed the game. A significant fraction of `10+0` games will have no eval. The actual availability rate must be measured during Ticket 1.1A. All claims made using eval-annotated subsets must acknowledge this selection bias.

---

## 17. Deliverables by maturity level

### Smoke-test deliverable

```text
Parser can process tiny synthetic PGN and 1,000 real games.
```

### Pilot deliverable

```text
Clean checkpoint dataset and first ablation table.
```

### Serious pilot deliverable

```text
100k+ usable rows, GBM, calibration report, subgroup analysis.
```

### Outreach-ready deliverable

```text
Concise research summary, stable repo, documented pipeline, ablation table, calibration figure, known limitations.
```
