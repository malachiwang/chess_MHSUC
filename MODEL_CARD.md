# Model Card

This file should be filled after the first serious model exists. Until then, it is a template.

## Model name

TBD

## Model version

TBD

## Intended use

Predict human chess game outcome probabilities under constraints:

```text
White win / Draw / Black win
```

Inputs may include:

```text
engine eval
ratings
clock state
move number
phase
termination info where appropriate for analysis, not pre-result prediction
```

## Not intended for

The model is not intended for:

- cheating detection,
- player surveillance,
- move recommendation,
- rating assignment,
- claiming objective chess truth beyond engine evaluation,
- replacing chess engines.

## Training data

TBD.

Expected initial source:

```text
Lichess standard rated PGN database
TimeControl "600+0"
standard chess only
rated games only
all valid ratings
```

## Labels

Primary:

```text
White win / Draw / Black win
```

Secondary/debugging:

```text
White win vs not White win
```

## Features

TBD.

Candidate feature groups:

```text
position eval
rating features
clock features
phase features
move number
termination category for retrospective analysis
```

## Evaluation

Preferred metrics:

```text
log loss
Brier score
calibration curve
ablation table
subgroup performance
```

Accuracy alone is insufficient.

## Calibration

TBD.

Report whether predicted probabilities match observed frequencies.

## Known limitations

Expected early limitations:

- existing Lichess eval annotations may be selection-biased,
- 10+0 may not generalize to other time controls,
- online ratings are not FIDE ratings,
- row-level correlations require careful game-level splitting,
- checkpoint prediction is not identical to every-ply prediction.

## Ethical/data considerations

Processed datasets should drop usernames by default.

The model should not be framed as a player surveillance or cheating detection tool.
