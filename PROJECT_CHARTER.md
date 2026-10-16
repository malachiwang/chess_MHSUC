# Project charter

Repository: [malachiwang/chess_MHSUC](https://github.com/malachiwang/chess_MHSUC).
MHSUC stands for Modeling Human Strategy Under Constraints.

## 1. Research question

How are human chess outcomes and next-move quality associated with remaining time,
player ratings, and board evaluation? The study distinguishes prediction of losing
on time from engine-measured quality of the moves played.

## 2. Current scope

The completed project is an observational replication and benchmark study of
Lichess standard rated games. Outcome prediction uses 10+0 checkpoints; the later
move-quality study uses 3+0, 5+0, and 10+0 archive-prefix samples from September and
October 2024. The [README](README.md) gives counts and supported conclusions.

## 3. Original objective and changes in direction

The initial objective was calibrated White-win/draw/Black-win probabilities at
successive game positions. Work began with 10+0, selected checkpoints, dummy and
logistic baselines, then gradient-boosted trees. The tree pilot overfit and
calibration work remained diagnostic. Fixed-depth Stockfish evaluation replaced
reliance on sparse Lichess annotations for the later outcome comparisons.

The termination analysis found that the gain from clock features was concentrated
in games ending on time. Subsequent work therefore measured next-move quality
directly, first at checkpoints and then densely for both colors. The later
prior-work audit led to replication and benchmark framing. The original every-ply
outcome predictor and neural sequence models remain aspirations, not deliverables.
See [ROADMAP.md](ROADMAP.md) and [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) for the record.

## 4. Deliverables and intended use

The repository provides reusable parsing, measurement, modeling, and reporting
code; tests with synthetic inputs; saved analysis reports; and figures. It is
intended for research inspection and reproduction. It is not a move recommendation
service, cheating detector, player surveillance tool, or deployed prediction API.

## 5. Measurement and interpretation

Game results are outcome labels. Engine evaluations provide an approximate board
reference, not ground truth or a direct measure of human reasoning. Expected-score
loss is a fitted transformation of evaluations. Associations after adjustment are
not causal effects. Time-forfeit filtering changes the analyzed population.

## 6. Data and privacy

Real data and model artifacts remain outside Git. Raw PGNs may contain usernames;
processed tables omit them. Salted player hashes are retained locally for dependence
checks. [DATA_POLICY.md](DATA_POLICY.md) governs data operations and publication.

## 7. Compute and extensions

The implementation was developed locally. Reproducing dense depth-12 engine
measurements is substantial work and is separate from the README smoke example.
New data collection, engine runs, dependencies, or model families require a scoped
proposal. More data should answer a documented uncertainty rather than serve as an
end in itself. Deferred ideas are listed in the roadmap, without an active commitment.

## 8. Evidence standards

Claims need documented source scope and filters, a saved result, and an explicit
analysis population. Outcome-model comparisons require game-ID splits, baselines,
probability metrics, and calibration diagnostics. Report log loss and multiclass
Brier score alongside class-specific behavior; accuracy alone can hide draw failure.
Keep validation model selection distinct from final test evaluation.

For move-level analyses, identify the measurement, weighting, controls, cluster
unit, sparse cells, and uncertainty procedure. Report month-specific results and
negative or conditioning-sensitive findings. Do not describe recurring-player
samples as independent or infer novelty from an incomplete literature search.

## 9. Record preservation

Experiment reports and protocols record what was known when each stage ran. Their
old next-step instructions are historical. The current overview is the README;
[MANIFEST.md](MANIFEST.md) points to the supporting records. No research result is
replaced simply because the direction of the project changed.
