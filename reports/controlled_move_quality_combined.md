# Controlled Move-Quality Modeling — Combined

**Ticket:** 15.1D — Controlled Move-Quality Modeling Implementation (Contrast C4)

## 1. Executive summary

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0034, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Eval-band positive control (vs decided): near_equal: +0.0223 (excludes 0); slight: +0.0286 (excludes 0); clear: +0.0158 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

## 2. Why this model exists after 11.2B / 15.1B

11.2B/11.2C reframed the outcome clock residual as primarily the time-forfeit/flagging channel and moved the board-play-quality question to next-move quality (C4). 15.1B described no replicated clock gradient and a strong eval-band pattern. This model tests both under simultaneous controls and mover-player-clustered uncertainty.

## 3. Inputs and modeling design

- Months: 2024_09_250k_v1, 2024_10_250k_v1.
- Target `expected_score_loss` (non-mate); OLS adjusted means; mover-player cluster bootstrap; large-loss logistic robustness.
- Estimation train+val, test reserved as confirmation; bootstrap reps 200, seed 42.

## 4. Month-by-month results

Primary contrasts (adjusted ΔES loss [95% mover-player-clustered CI]):

| Contrast | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0031 [+0.0003, +0.0057] **excludes 0** | +0.0038 [+0.0012, +0.0063] **excludes 0** |
| clock_under_60_vs_over_180 | +0.0080 [+0.0020, +0.0137] **excludes 0** | +0.0065 [+0.0020, +0.0124] **excludes 0** |
| eval_near_equal_vs_decided | +0.0221 [+0.0196, +0.0248] **excludes 0** | +0.0225 [+0.0202, +0.0251] **excludes 0** |
| eval_slight_vs_decided | +0.0280 [+0.0255, +0.0308] **excludes 0** | +0.0293 [+0.0268, +0.0318] **excludes 0** |
| eval_clear_vs_decided | +0.0158 [+0.0136, +0.0184] **excludes 0** | +0.0159 [+0.0138, +0.0182] **excludes 0** |
| termination_time_forfeit_vs_board_decided | -0.0009 [-0.0025, +0.0008] contains 0 | +0.0002 [-0.0015, +0.0018] contains 0 |

## 5. Pooled model results

Pooled (month fixed effect): 103,391 estimation rows, 21,652 movers; bootstrap 200/200 refits.

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0034 | +0.0034 [+0.0015, +0.0051] **excludes 0** |
| clock_under_60_vs_over_180 | +0.0072 | +0.0072 [+0.0042, +0.0115] **excludes 0** |
| eval_near_equal_vs_decided | +0.0223 | +0.0223 [+0.0205, +0.0239] **excludes 0** |
| eval_slight_vs_decided | +0.0286 | +0.0286 [+0.0270, +0.0302] **excludes 0** |
| eval_clear_vs_decided | +0.0158 | +0.0158 [+0.0143, +0.0173] **excludes 0** |
| termination_time_forfeit_vs_board_decided | -0.0003 | -0.0003 [-0.0015, +0.0008] contains 0 |

## 6. Clock contrast summary

The stable low-clock contrast (`60_180` vs `over_180`) has a CI that **excludes zero** (+0.0034, higher ES loss at lower clock). This is a controlled association (not causal) and is examined for cross-month replication before any emphasis.

Cross-month: 2024_09 60_180 vs over_180 +0.0031 [+0.0003, +0.0057] **excludes 0**; 2024_10 60_180 vs over_180 +0.0038 [+0.0012, +0.0063] **excludes 0**.

## 7. Eval-band positive-control summary

Eval-band positive control (vs decided): near_equal: +0.0223 (excludes 0); slight: +0.0286 (excludes 0); clear: +0.0158 (excludes 0). Positive, large contrasts with CIs excluding zero confirm the model recovers the known 15.1B descriptive structure (loss highest near equal/slight, lowest at decided).

## 8. Termination contrast summary

| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |
|---|---|---|
| termination_time_forfeit_vs_board_decided | -0.0003 | -0.0003 [-0.0015, +0.0008] contains 0 |

Cautious/secondary; not causal (selection from filtering).

## 9. Large-loss robustness summary

- ES>0.05: clock_60_180 +0.0883 [+0.0209, +0.1603] **excludes 0**; eval_slight +1.7239 [+1.6198, +1.8332] **excludes 0** (log-odds).
- ES>0.10: clock_60_180 +0.1409 [+0.0077, +0.2492] **excludes 0**; eval_slight +1.8126 [+1.6647, +1.9924] **excludes 0** (log-odds).

Logistic signs agree with OLS where both resolve, supporting robustness to the skew/zero-inflation of ES loss.

## 10. Test confirmation summary

| Contrast | pooled test ΔES | pooled train+val ΔES |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0045 | +0.0034 |
| clock_under_60_vs_over_180 | +0.0073 | +0.0072 |
| eval_near_equal_vs_decided | +0.0240 | +0.0223 |
| eval_slight_vs_decided | +0.0297 | +0.0286 |
| eval_clear_vs_decided | +0.0164 | +0.0158 |
| termination_time_forfeit_vs_board_decided | +0.0010 | -0.0003 |

## 11. What this supports

- Controlled, replicated statements about adjusted mean ES-loss differences across eval band (the robust structure) with clustered CIs.
- A controlled read on whether clock retains an association after adjustment (see §6) — including a null as an informative, pre-registered result.

## 12. What this does not support

- Any causal claim (low clock causing worse moves; time pressure degrading reasoning) — none is made.
- A 'degradation curve' reading of ordered buckets.
- Stockfish as ground truth; DRAW as solved; sharpness as an explanation (not implemented).

## 13. Implications for C4

The board-play-quality question (C4) is answered by measurement + controlled modeling: eval state is the robust move-quality structure; the clock association is present after controls and must be replication-checked. Consistent with the 11.2B reframing that the outcome clock signal is substantially the flagging channel.

## 14. Recommended next ticket

**15.1E — Clock Association Robustness Audit**: the controlled clock contrast is small but **replicates and excludes zero** after adjustment, so before any C4 consolidation it must be stress-tested — eval-band coarseness (continuous `mover_pre_cp` instead of 4 bands), residual clock×checkpoint confounding, rating non-linearity, the sparse `under_60` cell, and two-way (White×Black) player dependence. Consolidation of the C4 claim (15.1B descriptive + 11.3B clustered + 15.1D controlled) folds in afterward. Sharpness moderation (C3 / 15.2A) remains a separate later arc.
