# Controlled Move-Quality Modeling — 2024_10_250k_v1

**Ticket:** 15.1D — Controlled Move-Quality Modeling Implementation (Contrast C4)

## 1. Executive summary

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0038, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Eval-band positive control (vs decided): near_equal: +0.0225 (excludes 0); slight: +0.0293 (excludes 0); clear: +0.0159 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

Predictive/descriptive association only — not causal, not a degradation curve.

## 2. Input artifacts

- Next-move loss: `data/processed/next_move_loss_2024_10_250k_v1.parquet`
- Player metadata (hashed, gitignored): `data/processed/player_metadata_2024_10_250k_v1.parquet`

## 3. Modeling sample

- Non-mate modeling rows: 59,625 (12,882 unique movers).
- By split: test=8,991, train=41,693, val=8,941.
- Estimation (train+val): 50,634 rows, 11,676 movers. Confirmation (test): 8,991 rows.

## 4. Target and covariates

- Target: `expected_score_loss` (mover's perspective), non-mate rows.
- Model: `ES_loss ~ C(clock_coarse) + C(selected_position_type) + C(eval_band) + rating_z + C(termination_binary)` (OLS adjusted means).
- Reference levels: clock=`over_180`, checkpoint=`move_10`, eval=`decided`, termination=`board_decided`. `rating_z` standardized on TRAIN rows only (mean=1573.4, sd=344.5).
- Checkpoint reference `move_10` is the most populous (opening) phase; the additive clock and eval contrasts do not depend on this choice.

## 5. Train/validation/test discipline

Coefficients estimated on **train+val**; **test reserved as a locked confirmation** (refit, point estimates only; §12). No tuning on test; reference levels and covariates fixed in advance (15.1C).

## 6. Primary OLS adjusted-mean model

Full coefficient table (adjusted ES-loss deltas vs the reference cell):

| Coefficient | estimate |
|---|---|
| intercept | +0.01171 |
| clock=under_60 | +0.00653 |
| clock=60_180 | +0.00376 |
| checkpoint=move_20 | +0.00451 |
| checkpoint=move_30 | +0.00100 |
| checkpoint=move_40 | -0.00491 |
| eval=near_equal | +0.02250 |
| eval=slight | +0.02925 |
| eval=clear | +0.01586 |
| rating_z | -0.00716 |
| termination=time_forfeit | +0.00024 |

## 7. Player-clustered uncertainty

Mover-player cluster bootstrap: 200/200 successful refits, 11,676 clusters, 50,634 rows, seed=42. 95% percentile CIs below.

## 8. Clock contrasts

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0038 | +0.0038 [+0.0012, +0.0063] **excludes 0** |
| clock_under_60_vs_over_180 | +0.0065 | +0.0065 [+0.0020, +0.0124] **excludes 0** |

`60_180` is the stable low-clock contrast; `under_60` is sparse/confounded (exploratory). The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0038, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

## 9. Eval-band positive-control contrasts

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| eval_near_equal_vs_decided | +0.0225 | +0.0225 [+0.0202, +0.0251] **excludes 0** |
| eval_slight_vs_decided | +0.0293 | +0.0293 [+0.0268, +0.0318] **excludes 0** |
| eval_clear_vs_decided | +0.0159 | +0.0159 [+0.0138, +0.0182] **excludes 0** |

Eval-band positive control (vs decided): near_equal: +0.0225 (excludes 0); slight: +0.0293 (excludes 0); clear: +0.0159 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

## 10. Termination contrast

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| termination_time_forfeit_vs_board_decided | +0.0002 | +0.0002 [-0.0015, +0.0018] contains 0 |

Secondary and cautious: termination follows later play/time dynamics and filtering induces selection; not causal.

## 11. Large-loss logistic robustness

- **ES>0.05** (positive rate 0.2003, 200/200 refits), log-odds contrasts:
  - clock_60_180_vs_over_180: +0.1501 [+0.0452, +0.2670] **excludes 0**
  - eval_slight_vs_decided: +1.8063 [+1.6600, +1.9925] **excludes 0**
- **ES>0.10** (positive rate 0.0919, 200/200 refits), log-odds contrasts:
  - clock_60_180_vs_over_180: +0.1871 [+0.0239, +0.3436] **excludes 0**
  - eval_slight_vs_decided: +1.8223 [+1.6052, +2.0854] **excludes 0**

Logistic models are skew-robust robustness checks; signs are read for agreement with the OLS contrasts, not as calibrated odds ratios.

## 12. Test confirmation

Locked test-split refit, point-estimate contrasts (no tuning):

| Contrast | test ΔES loss | train+val ΔES loss |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0042 | +0.0038 |
| clock_under_60_vs_over_180 | +0.0098 | +0.0065 |
| eval_near_equal_vs_decided | +0.0201 | +0.0225 |
| eval_slight_vs_decided | +0.0260 | +0.0293 |
| eval_clear_vs_decided | +0.0129 | +0.0159 |
| termination_time_forfeit_vs_board_decided | +0.0004 | +0.0002 |

## 13. Interpretation

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0038, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Eval-band positive control (vs decided): near_equal: +0.0225 (excludes 0); slight: +0.0293 (excludes 0); clear: +0.0159 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

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
