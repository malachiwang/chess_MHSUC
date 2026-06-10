# Bootstrap CI Report — lichess_ten_zero_2024_09_25k_v1

**Version tag:** `2024_09_25k_v1`
**Ticket:** 7.3B (Modeling Hygiene Hardening)

## Summary

Game-level cluster bootstrap 95% confidence intervals for validation log_loss and pairwise deltas. Resampling is at the game_id level (not row level) to respect the within-game dependency of checkpoint rows.

Models assessed: B1, B2, B3, G2, G2b.

**Replicates:** 1000  **Seed:** 42  **CI:** 95% (percentile method)

## Per-model log_loss CIs

| Model | Val log_loss | CI lower | CI upper | Width | n_games | n_rows |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | 0.8853 | 0.8279 | 0.9444 | 0.1164 | 348 | 931 |
| B2 | 0.8740 | 0.8127 | 0.9394 | 0.1267 | 348 | 931 |
| B3 | 0.8527 | 0.7910 | 0.9170 | 0.1261 | 348 | 931 |
| G2 | 1.2326 | 1.0687 | 1.4123 | 0.3437 | 348 | 931 |
| G2b | 1.1808 | 1.0292 | 1.3581 | 0.3289 | 348 | 931 |

## Pairwise delta log_loss CIs (delta = LL(B) - LL(A))

Negative delta means B improved over A. **contains_zero** = True means the CI includes 0, so the improvement is not statistically resolvable at 95%.

| Comparison | Point delta | CI lower | CI upper | contains_zero | n_games |
| --- | --- | --- | --- | --- | --- |
| B1 → B2 | -0.0112 | -0.0286 | +0.0060 | True | 348 |
| B2 → B3 | -0.0214 | -0.0360 | -0.0065 | False | 348 |
| B3 → G2 | +0.3799 | +0.2595 | +0.5137 | False | 348 |
| B3 → G2b | +0.3281 | +0.2181 | +0.4542 | False | 348 |

**B2 → B3 (clock features):** point delta = -0.0214  95% CI [-0.0360, -0.0065]  CI contains zero: No — CI excludes 0.

## Methodology

### Why game-level resampling?

Each game contributes multiple checkpoint rows (move_10, move_20). Row-level bootstrap would treat these as independent, underestimating variance. Game-level cluster bootstrap draws whole games with replacement, preserving the within-game correlation structure.

### Paired pairwise bootstrap

For delta CIs the same bootstrap game_id sample is used for both models in each replicate (paired bootstrap). This removes game-sampling variance from the delta estimate and is the correct approach for model comparisons on the same dataset.

### Procedure

1. Extract unique validation game_ids for the model (N games).
2. Draw N game_ids with replacement.
3. Collect all rows belonging to drawn game_ids (with multiplicity).
4. Compute log_loss on that bootstrap sample.
5. Repeat 1000 times (seed=42).
6. Compute 2.5th and 97.5th percentile for 95% CI.

### Primary_numbered view

Bootstrap uses the primary_numbered view (excludes `selected_position_type == 'last'`), consistent with how all broad models are evaluated.

## Interpretation

**Note:** At this pilot scale (approx 348 val games, approx 931 rows), bootstrap CIs are wide. Interval endpoints should not be over-interpreted.

### G2 vs G2b

- G2 (300 unstopped iterations): 1.2326 [1.0687, 1.4123]
- G2b (early stopping, val_fraction=0.15): 1.1808 [1.0292, 1.3581]

G2b improves point val log_loss over G2. However, the per-model CIs overlap substantially. Whether the improvement is statistically resolvable should be judged from the paired B3→G2b delta CI above, not from comparing the individual CIs.

G2b is a fair-comparison diagnostic: same FS-E features as G2, but with `early_stopping=True, validation_fraction=0.15, n_iter_no_change=10`. G2 ran 300 unstopped iterations because sklearn `early_stopping='auto'` does not activate below 10,000 training samples (pilot train: 4,344 rows).

### B3 baseline reference

B3 (LogisticRegression on FS-E): 0.8527 [0.7910, 0.9170]

B3 remains the best broad model at this pilot scale. For a new model to be considered an improvement over B3, the B3→newmodel paired delta CI must exclude zero.

## Caveats

- Pilot scale only (approx 348 val games). CIs are wide.
- G2b results depend on the extra predictions artifact (gbm_hygiene). Re-run bootstrap after any G2b hyperparameter change.
- CIs are percentile-method bootstrap, not BCa. At this sample size the distinction is negligible.
- If n_nan > 0 in the payload, some replicates drew a sample with fewer than 2 classes and were excluded from CI computation.
