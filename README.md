# Modeling Human Strategy Under Constraints

Repository: `chess-MHSUC`

This repository supports a private-first research project on human chess outcome prediction under constraints. The initial research setting is online rated standard chess, beginning with Lichess `10+0` games and expanding only after the ingestion, cleaning, labeling, and baseline modeling pipeline is verified.

## Core research question

Can we build a calibrated model that predicts human chess outcomes from objective position evaluation, rating, game phase, and clock pressure?

More concretely:

> Given a board position and human context — engine evaluation, player ratings, clocks, move number, and game phase — what is the probability of White win / Draw / Black win?

The project treats chess as a testbed for **bounded rationality in sequential decision-making**. Engine evaluation estimates objective advantage under strong play, but human outcomes also depend on rating, time pressure, conversion ability, and game phase.

## Initial scope

The first serious version is intentionally narrow:

- Data source: Lichess standard rated PGN database.
- Initial time control: `10+0`, represented by `TimeControl "600+0"`.
- Game type: standard chess only.
- Rating scope: all valid Lichess ratings.
- Game status: rated games only.
- Variants: excluded.
- Usernames: not retained in processed datasets by default.
- Primary label: three-class outcome: White win / Draw / Black win.
- Secondary label: binary tasks allowed only for debugging and baseline sanity checks.
- Initial prediction positions: selected checkpoints first; every-ply prediction later.
- Initial evaluation source: existing Lichess `%eval` annotations when available.
- Later validation: fixed-depth local Stockfish analysis on sampled positions.

## Why start with 10+0?

`10+0` is narrow, common, and long enough for nontrivial time-management behavior. It is not treated as the final project scope. It is the first controlled environment for building a reliable pipeline.

Later extensions may compare other time formats, including shorter blitz/bullet and longer rapid/classical-style games if suitable data exists.

## Model path

The project begins with interpretable tabular models and scales only when justified:

1. Simple baselines.
2. Logistic regression.
3. Gradient-boosted tree model.
4. Calibrated gradient-boosted model.
5. Neural sequence model only after the tabular pipeline demonstrates useful signal.

The first serious model family should be a GBM/GBDT-style model, not a neural network.

## Repository structure

```text
chess-MHSUC/
  README.md
  PROJECT_CHARTER.md
  ROADMAP.md
  WORKFLOW.md
  DATA_POLICY.md
  CLAUDE.md
  PIPELINE_OVERVIEW.md
  EXPERIMENT_LOG.md
  MODEL_CARD.md

  data/
    raw/lichess/        # local only; ignored by Git
    interim/            # local only; ignored by Git
    processed/          # local only; ignored by Git

  notebooks/            # exploratory analysis; outputs cleared before commit
  reports/
    figures/            # small figures may be committed if useful
    phase_reports/      # durable audit/implementation reports
  src/chess_mhsuc/      # reusable pipeline/modeling code
  tests/                # parser/feature/model tests
```

## Data policy summary

Real datasets are not committed to Git.

Do not commit:

- `.pgn`
- `.pgn.zst`
- `.parquet`
- `.csv`
- `.duckdb`
- large model artifacts
- raw or processed real game data

Allowed:

- code
- governance docs
- markdown reports
- small figures
- tiny synthetic PGN fixtures for parser tests

## Development philosophy

This project should prefer small verified steps over large fragile pipelines.

The standard development loop is:

```text
audit -> implementation -> post-implementation report -> local verification -> commit/push
```

Parser, cleaning, label extraction, train/test splitting, and evaluation changes require special caution because bugs there can silently poison all downstream results.

## External references

- Lichess open database: https://database.lichess.org/
- python-chess PGN documentation: https://python-chess.readthedocs.io/en/latest/pgn.html
- scikit-learn HistGradientBoostingClassifier: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html
- XGBoost documentation: https://xgboost.readthedocs.io/
