# Controlled Move-Quality Modeling — 2024_09_250k_v1

**Ticket:** 15.1D — Controlled Move-Quality Modeling Implementation (Contrast C4)

## 1. Executive summary

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0031, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Eval-band positive control (vs decided): near_equal: +0.0221 (excludes 0); slight: +0.0280 (excludes 0); clear: +0.0158 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

Predictive/descriptive association only — not causal, not a degradation curve.

## 2. Input artifacts

- Next-move loss: `data/processed/next_move_loss_2024_09_250k_v1.parquet`
- Player metadata (hashed, gitignored): `data/processed/player_metadata_2024_09_250k_v1.parquet`

## 3. Modeling sample

- Non-mate modeling rows: 61,956 (12,910 unique movers).
- By split: test=9,199, train=43,476, val=9,281.
- Estimation (train+val): 52,757 rows, 11,774 movers. Confirmation (test): 9,199 rows.

## 4. Target and covariates

- Target: `expected_score_loss` (mover's perspective), non-mate rows.
- Model: `ES_loss ~ C(clock_coarse) + C(selected_position_type) + C(eval_band) + rating_z + C(termination_binary)` (OLS adjusted means).
- Reference levels: clock=`over_180`, checkpoint=`move_10`, eval=`decided`, termination=`board_decided`. `rating_z` standardized on TRAIN rows only (mean=1581.7, sd=351.7).
- Checkpoint reference `move_10` is the most populous (opening) phase; the additive clock and eval contrasts do not depend on this choice.

## 5. Train/validation/test discipline

Coefficients estimated on **train+val**; **test reserved as a locked confirmation** (refit, point estimates only; §12). No tuning on test; reference levels and covariates fixed in advance (15.1C).

## 6. Primary OLS adjusted-mean model

Full coefficient table (adjusted ES-loss deltas vs the reference cell):

| Coefficient | estimate |
|---|---|
| intercept | +0.01316 |
| clock=under_60 | +0.00796 |
| clock=60_180 | +0.00309 |
| checkpoint=move_20 | +0.00380 |
| checkpoint=move_30 | +0.00056 |
| checkpoint=move_40 | -0.00432 |
| eval=near_equal | +0.02206 |
| eval=slight | +0.02803 |
| eval=clear | +0.01576 |
| rating_z | -0.00724 |
| termination=time_forfeit | -0.00086 |

## 7. Player-clustered uncertainty

Mover-player cluster bootstrap: 200/200 successful refits, 11,774 clusters, 52,757 rows, seed=42. 95% percentile CIs below.

## 8. Clock contrasts

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0031 | +0.0031 [+0.0003, +0.0057] **excludes 0** |
| clock_under_60_vs_over_180 | +0.0080 | +0.0080 [+0.0020, +0.0137] **excludes 0** |

`60_180` is the stable low-clock contrast; `under_60` is sparse/confounded (exploratory). The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0031, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

## 9. Eval-band positive-control contrasts

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| eval_near_equal_vs_decided | +0.0221 | +0.0221 [+0.0196, +0.0248] **excludes 0** |
| eval_slight_vs_decided | +0.0280 | +0.0280 [+0.0255, +0.0308] **excludes 0** |
| eval_clear_vs_decided | +0.0158 | +0.0158 [+0.0136, +0.0184] **excludes 0** |

Eval-band positive control (vs decided): near_equal: +0.0221 (excludes 0); slight: +0.0280 (excludes 0); clear: +0.0158 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

## 10. Termination contrast

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| termination_time_forfeit_vs_board_decided | -0.0009 | -0.0009 [-0.0025, +0.0008] contains 0 |

Secondary and cautious: termination follows later play/time dynamics and filtering induces selection; not causal.

## 11. Large-loss logistic robustness

- **ES>0.05** (positive rate 0.2027, 200/200 refits), log-odds contrasts:
  - clock_60_180_vs_over_180: +0.0129 [-0.0974, +0.1183] contains 0
  - eval_slight_vs_decided: +1.6566 [+1.5411, +1.8126] **excludes 0**
- **ES>0.10** (positive rate 0.0931, 200/200 refits), log-odds contrasts:
  - clock_60_180_vs_over_180: +0.0800 [-0.1167, +0.2265] contains 0
  - eval_slight_vs_decided: +1.8216 [+1.6105, +2.0840] **excludes 0**

Logistic models are skew-robust robustness checks; signs are read for agreement with the OLS contrasts, not as calibrated odds ratios.

## 12. Test confirmation

Locked test-split refit, point-estimate contrasts (no tuning):

| Contrast | test ΔES loss | train+val ΔES loss |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0047 | +0.0031 |
| clock_under_60_vs_over_180 | +0.0051 | +0.0080 |
| eval_near_equal_vs_decided | +0.0278 | +0.0221 |
| eval_slight_vs_decided | +0.0332 | +0.0280 |
| eval_clear_vs_decided | +0.0198 | +0.0158 |
| termination_time_forfeit_vs_board_decided | +0.0014 | -0.0009 |

## 13. Interpretation

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0031, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Eval-band positive control (vs decided): near_equal: +0.0221 (excludes 0); slight: +0.0280 (excludes 0); clear: +0.0158 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

## 14. Limitations and caveats

- Predictive/descriptive association only — not causal; no claim that time pressure causes worse moves or degrades reasoning.
- Ordered-bucket patterns are patterns, not a degradation curve.
- Numbered checkpoints are even-ply, so the mover is always White: this models White-to-move decision quality.
- `under_60` is sparse and heavily confounded with late checkpoints (clock×checkpoint confound); its contrast is exploratory, not headline.
- Eval-band dominance may partly reflect chess-value geometry (decided positions have little expected score left to lose) as much as human difficulty.
- The ES transform is train-fitted and approximate; large-loss logistic models hedge against its exact shape.
- Mover-player clustering handles repeated movers but not exact two-way (White×Black) dependence (deferred).
- Time-forfeit filtering induces survivor bias; the termination binary is a covariate, not a correction.
- Prior-trajectory control is DEFERRED — the artifacts carry no pre-checkpoint trajectory feature, so the 'clock as symptom of past struggle' confound is an explicit limitation, not adjusted here.
- Stockfish depth-12 eval is objective position context, not absolute ground truth; DRAW remains sparse and not solved; sharpness is not implemented.

## 15. Recommendation

Read against the other month in the combined report; a contrast is credited only if it replicates across 2024-09 and 2024-10.
