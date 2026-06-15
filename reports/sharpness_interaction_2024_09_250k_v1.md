# Sharpness Interaction Modeling — 2024_09_250k_v1

**Ticket:** 14.2B — C3c clock × sharpness move-quality moderation (pre-registered 14.2A)

## 1. Executive summary

Per-month fit of the locked C3c interaction. Primary `clock=60_180 × sharp_value_fragility_v1` (train+val, mover-player-clustered): +0.0074 [-0.0079, +0.0217] contains 0. Single month is not decisive — see the combined report for the cross-month classification. Predictive/descriptive moderation only — not causal; not human obviousness.

## 2. Pre-registered design

PREREGISTRATION §C3c (locked 14.2A). Primary estimand = the `clock=60_180:sharp` interaction coefficient (difference-in-differences); positive ⇒ low-clock association larger in sharp positions.

## 3. Input artifacts

- `data/processed/next_move_loss_2024_09_250k_v1.parquet`, `data/processed/multipv_sharpness_2024_09_250k_v1.parquet`, `data/processed/player_metadata_2024_09_250k_v1.parquet` (player metadata gitignored; hashed).

## 4. Join validation

- sharpness rows 64,371, keys unique True; modeling frame rows 61,956, keys unique True; joined 61,956 (coverage 1.0); no row multiplication True; **sharp recompute mismatches 0**.

## 5. Primary row universe and exclusions

- {'start_nonmate_joined': 61956, 'primary_rows': 61956}
- Estimation (train+val) rows: 52,757; test rows: 9,199.

## 6. Cell adequacy

- {'60_180_sharp0': 1911, '60_180_sharp1': 297, 'over_180_sharp0': 42803, 'over_180_sharp1': 7086, 'sharp_x_60_180': 297, 'under_60_sharp': 70} → sharp×60_180 = 297 (14.2A CI threshold ≥300); under_60×sharp = 70 (exploratory).

## 7. Primary model

`expected_score_loss ~ C(clock,ref=over_180) + sharp + clock:sharp + C(checkpoint,ref=move_10) + C(eval_band,ref=decided) + rating_z + C(termination_binary,ref=board_decided)` (OLS; month omitted in single-month fit).

## 8. Primary train+val result

- `clock=60_180 × sharp`: +0.0074 [-0.0079, +0.0217] contains 0 (clusters 11,774, rows 52,757).
- secondary `clock=under_60 × sharp` (exploratory): +0.0092 [-0.0152, +0.0378] contains 0.

## 9. Locked test confirmation

- test-split point estimate `clock=60_180:sharp`: 0.0054.

## 10. Robustness checks

| Robustness check | clock=60_180 × sharp |
|---|---|
| continuous eval control | +0.0073 [-0.0081, +0.0216] contains 0 |
| board-decided-only | +0.0026 [-0.0129, +0.0174] contains 0 |
| rating quantile bins | +0.0073 [-0.0077, +0.0216] contains 0 |
| rating quadratic | +0.0073 [-0.0079, +0.0216] contains 0 |
| sharp relaxed | +0.0105 [-0.0055, +0.0280] contains 0 |
| sharp strict | +0.0123 [-0.0087, +0.0344] contains 0 |
| target: clipped_cp (dir.) | +10.5774 [-14.4479, +31.6070] contains 0 |
| logistic ES>0.05 (dir.) | +0.1054 [-0.1489, +0.4473] contains 0 |
| logistic ES>0.10 (dir.) | +0.1069 [-0.2356, +0.4347] contains 0 |
| cluster: game | +0.0074 [-0.0066, +0.0217] contains 0 |
| cluster: White-player | +0.0074 [-0.0079, +0.0217] contains 0 |
| cluster: Black-player | +0.0074 [-0.0048, +0.0212] contains 0 |

## 11. Exploratory diagnostics

- surface-bait moderator (NOT human obviousness): +0.0267 [-0.0128, +0.0747] contains 0. Exploratory only.

## 12. Classification under 14.2A criteria

See the combined report for the binding cross-month classification.

## 13. Limitations and caveats

- Not causal; no claim that time pressure causes worse moves or worse reasoning.
- `sharp_value_fragility_v1` is an engine-side value-fragility proxy — **NOT human obviousness** (deferred Tier B) and not a complete account of practical difficulty.
- Surface-bait is an exploratory diagnostic only, never a headline; not human obviousness.
- No outcome/flagging (C3a/C3b) sharpness model is run here.
- No 'degradation curve'; Stockfish eval is objective context, not ground truth; DRAW remains sparse and not solved; this is not a best-predictor claim.
- On any support, the moderation is a small, secondary, predictive/descriptive finding on top of eval-state-dominant move quality.
