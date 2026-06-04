# Project Charter

Project title: **Modeling Human Strategy Under Constraints**  
Repository: `chess-MHSUC`

## 1. Mission

This project studies how human chess outcomes are shaped by objective position quality, player rating, clock pressure, and game phase.

The long-term goal is to build a calibrated model that predicts White win / Draw / Black win probabilities at each point in a game, accounting for the fact that humans are not engines and do not play with unlimited precision or unlimited time.

## 2. Core hypothesis

Engine evaluation carries predictive value, but it is incomplete for human games. Human conversion and collapse depend on constraints such as:

- player rating,
- rating gap,
- clock pressure,
- phase of the game,
- time-control environment,
- position volatility or complexity,
- termination mode.

The project begins by testing whether clock and rating features improve outcome prediction beyond engine evaluation alone, especially in late-game and low-time regimes.

## 3. Initial research setting

The first controlled setting is:

```text
Data source: Lichess standard rated database
Game type: standard chess
Time control: 10+0 only, TimeControl "600+0"
Ratings: all valid ratings
Outcome label: White win / Draw / Black win
Processed usernames: dropped by default
Variants: excluded
Unrated games: excluded
```

This scope is intentionally narrow. It exists to make the first pipeline reliable and interpretable.

## 4. What this project is

This project is:

- a human outcome prediction project,
- a bounded-rationality modeling project,
- a chess analytics and ML pipeline project,
- a reproducible data science project,
- a possible foundation for later research outreach.

## 5. What this project is not

This project is not initially:

- a chess engine,
- a move recommendation system,
- a chess.com/Lichess clone,
- a neural-network-first project,
- a web app,
- a full scrape of all chess data,
- a public dataset release,
- a NeurIPS/ICML paper draft before pilot evidence exists.

## 6. Primary outcome task

The primary task is three-class prediction:

```text
White win / Draw / Black win
```

Binary labels such as `White win vs not White win` are allowed only for early debugging, sanity checks, and simple baselines. They are not the final target.

## 7. Position granularity

The long-term target is every-ply prediction.

The initial pilot may use selected positions to reduce pipeline complexity. Acceptable early checkpoints include:

```text
after move 10
after move 20
after move 30
after move 40
final available pre-result position
```

This is a stepping stone only. The docs and code should not redefine the project as checkpoint-only prediction.

## 8. Evidence standards

A claim is not considered supported unless it is backed by:

- documented dataset version and filters,
- clean train/validation/test split by game ID,
- baseline comparison,
- appropriate probability metrics,
- error/calibration assessment,
- written report or experiment log entry.

Accuracy alone is not sufficient.

Preferred metrics include:

- log loss,
- Brier score,
- calibration curves,
- confusion matrices where useful,
- ablation tables,
- subgroup performance by rating bucket, phase, and low-time state.

## 9. Data ethics and privacy stance

Lichess games are public, but processed project datasets should still minimize unnecessary identity retention.

Policy:

- Raw PGNs may contain usernames locally.
- Processed datasets should drop usernames by default.
- If player-level splitting becomes necessary, use hashed or anonymized IDs.
- Do not publish raw or processed real game data from this repository.
- Reproducibility should come from scripts and documented data sources, not Git-hosted datasets.

## 10. Modeling stance

This project is model-agnostic but should begin with interpretable baselines and tabular models.

Preferred model sequence:

1. Rule/probability baselines.
2. Logistic regression.
3. Gradient-boosted tree model.
4. Calibrated gradient-boosted model.
5. Neural sequence model only after tabular results justify the added complexity.

## 11. Sample-size stance

The first iteration should be capped and staged.

Recommended ramp:

```text
Parser smoke test:        100-1,000 games
First data audit:         10,000-25,000 games scanned or sampled
First modeling pilot:     25,000-50,000 qualifying positions/games, depending on eval availability
Serious pilot:            100,000-300,000 qualifying rows
Scale-up candidate:       500,000+ qualifying rows only after baselines are validated
```

The project should not download or process huge files just because storage is available. Scale must answer a specific research or validation need.

## 12. Compute stance

Default development is local-first on Malachi's MacBook Pro M3 Pro.

Cloud compute is not part of the initial plan. It may be considered later for:

- large fixed-depth Stockfish evaluation,
- sequence-model training,
- repeated multi-million-row experiments,
- workloads that demonstrably exceed local capacity.

## 13. Public/private stance

The repository is private-first.

Potential future public release may include:

- cleaned code,
- methods,
- generated figures,
- reports,
- reproduction instructions.

It should not include raw or processed real game datasets.

## 14. Outreach stance

Professor feedback is useful, but outreach should be strongest after the project has at least:

- a clean pilot dataset,
- a documented pipeline,
- one ablation table,
- one calibration assessment,
- one concise written summary.

Early informal conceptual questions are allowed, but formal research outreach should wait for pilot evidence.
