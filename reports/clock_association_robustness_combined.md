# Clock Association Robustness — Combined

**Ticket:** 15.1F — Clock Association Robustness Implementation (Contrast C4)

## 1. Executive summary

Under the locked 15.1E criteria, the small controlled clock association **SURVIVES** the mandatory robustness checks. Pooled baseline clock contrast +0.0034 [+0.0015, +0.0051] **excl 0**; continuous-eval-control +0.0034 [+0.0015, +0.0052] **excl 0**; board-decided-only +0.0034 [+0.0010, +0.0063] **excl 0**. In all cases the clock effect is small and **secondary to the eval-band structure** (15.1D eval contrasts ~5–8× larger). Predictive/descriptive — not causal, not a degradation curve.

## 2. Why this robustness pass exists

15.1D found a small, replicated, test-confirmed clock association after controls. 15.1E ranked the threats (coarse eval bands; checkpoint×clock; survivor/termination composition) and locked the interpretation criteria. This pass runs the mandatory checks and applies those criteria.

## 3. Baseline 15.1D replication

Pooled baseline clock contrast +0.0034 [+0.0015, +0.0051] **excl 0** reproduces 15.1D (`60_180` vs `over_180` ≈ +0.0034). Per-month: +0.0031 [+0.0003, +0.0057] **excl 0** / +0.0038 [+0.0012, +0.0063] **excl 0**.

## 4. Robustness matrix

Primary contrast = `60_180` vs `over_180` (adjusted Δ ES loss unless the metric row notes otherwise); mover-player-clustered unless the cluster row notes otherwise. `(dir.)` = directional metric (cp/log-odds scale).

| Check | 2024-09 | 2024-10 | pooled | verdict |
|---|---|---|---|---|
| baseline (15.1D) | +0.0031 [+0.0003, +0.0057] **excl 0** | +0.0038 [+0.0012, +0.0063] **excl 0** | +0.0034 [+0.0015, +0.0051] **excl 0** | survives |
| continuous eval control | +0.0031 [+0.0002, +0.0057] **excl 0** | +0.0038 [+0.0012, +0.0065] **excl 0** | +0.0034 [+0.0015, +0.0052] **excl 0** | survives |
| late-only (move_30+40) | +0.0028 [-0.0006, +0.0065] contains 0 | +0.0037 [+0.0005, +0.0065] **excl 0** | +0.0033 [+0.0009, +0.0053] **excl 0** | survives |
| board-decided-only | +0.0040 [+0.0001, +0.0088] **excl 0** | +0.0028 [-0.0002, +0.0060] contains 0 | +0.0034 [+0.0010, +0.0063] **excl 0** | survives |
| rating quantile bins | +0.0028 [+0.0000, +0.0055] **excl 0** | +0.0035 [+0.0009, +0.0062] **excl 0** | +0.0032 [+0.0012, +0.0049] **excl 0** | survives |
| rating quadratic | +0.0030 [+0.0001, +0.0056] **excl 0** | +0.0036 [+0.0011, +0.0063] **excl 0** | +0.0033 [+0.0013, +0.0050] **excl 0** | survives |
| metric: clipped_cp_loss | +5.7711 [+0.8339, +9.9923] **excl 0** | +6.4126 [+2.2354, +10.7528] **excl 0** | +6.0865 [+2.8387, +9.1775] **excl 0** | survives (dir.) |
| metric: logistic ES>0.05 | +0.0129 [-0.0974, +0.1183] contains 0 | +0.1501 [+0.0452, +0.2670] **excl 0** | +0.0883 [+0.0209, +0.1603] **excl 0** | survives (dir.) |
| metric: logistic ES>0.10 | +0.0800 [-0.1167, +0.2265] contains 0 | +0.1871 [+0.0239, +0.3436] **excl 0** | +0.1409 [+0.0077, +0.2492] **excl 0** | survives (dir.) |
| cluster: game_id | +0.0031 [-0.0000, +0.0062] contains 0 | +0.0038 [+0.0009, +0.0077] **excl 0** | +0.0034 [+0.0012, +0.0057] **excl 0** | survives |
| cluster: White-player | +0.0031 [+0.0003, +0.0057] **excl 0** | +0.0038 [+0.0012, +0.0063] **excl 0** | +0.0034 [+0.0015, +0.0051] **excl 0** | survives |
| cluster: Black-player | +0.0031 [+0.0001, +0.0061] **excl 0** | +0.0038 [+0.0011, +0.0065] **excl 0** | +0.0034 [+0.0010, +0.0055] **excl 0** | survives |

Verdict labels: survives / weakens / mixed / fails / exploratory_only / not_run (per the 15.1E criteria).

## 5. Month-by-month stability

| Check | 2024-09 | 2024-10 |
|---|---|---|
| baseline (15.1D) | +0.0031 [+0.0003, +0.0057] **excl 0** | +0.0038 [+0.0012, +0.0063] **excl 0** |
| continuous eval control | +0.0031 [+0.0002, +0.0057] **excl 0** | +0.0038 [+0.0012, +0.0065] **excl 0** |
| late-only (move_30+40) | +0.0028 [-0.0006, +0.0065] contains 0 | +0.0037 [+0.0005, +0.0065] **excl 0** |
| board-decided-only | +0.0040 [+0.0001, +0.0088] **excl 0** | +0.0028 [-0.0002, +0.0060] contains 0 |

## 6. Continuous eval-control result

Adding standardized within-band |cp|: pooled clock +0.0034 [+0.0015, +0.0052] **excl 0** (verdict survives). This is the key test for the coarse-band residual confound flagged in 15.1E.

## 7. Late-only result

move_30+move_40 only: pooled clock +0.0033 [+0.0009, +0.0053] **excl 0** (verdict survives).

## 8. Board-decided-only result

Time-forfeit excluded: pooled clock +0.0034 [+0.0010, +0.0063] **excl 0** (verdict survives). This isolates move quality from flagging; `under_60` here is +0.0045 [-0.0013, +0.0109] contains 0 (sparse/exploratory).

## 9. Rating and metric sensitivity

Rating quantile bins +0.0032 [+0.0012, +0.0049] **excl 0**; quadratic +0.0033 [+0.0013, +0.0050] **excl 0**. clipped_cp_loss +6.0865 [+2.8387, +9.1775] **excl 0** (directional); logistic ES>0.05 +0.0883 [+0.0209, +0.1603] **excl 0**, ES>0.10 +0.1409 [+0.0077, +0.2492] **excl 0** (log-odds, directional).

## 10. Cluster sensitivity

game_id +0.0034 [+0.0012, +0.0057] **excl 0**; White-player +0.0034 [+0.0015, +0.0051] **excl 0**; Black-player +0.0034 [+0.0010, +0.0055] **excl 0**. Mover-player clustering (baseline) is primary; wider-of-two White/Black is the conservative read. Exact two-way clustering remains deferred.

## 11. Interpretation under 15.1E criteria

**Conclusion: SURVIVES.** Gate checks: baseline: survives; continuous eval control: survives; board-decided-only: survives (pooled est 0.0034); metric direction agrees: True.

All locked conditions hold: positive both months, pooled CI excludes zero, not eliminated by continuous eval control, board-decided-only same sign, metric direction agrees. The C4 clock association is credited as **small, replicated, controlled, and secondary** to eval band — descriptive/predictive, not causal.

## 12. What this supports

- The eval-band structure as the robust, dominant, replicated move-quality structure (15.1B/15.1D), unaffected by these clock-focused variants.
- A disciplined, criteria-locked verdict on the small clock contrast.

## 13. What this does not support

- Any causal claim or 'degradation curve' reading.
- Headlining clock as a move-quality driver.
- Stockfish as ground truth; DRAW as solved; sharpness as an explanation (not implemented).

## 14. Recommended next ticket

**15.1G — C4 Claim Consolidation / Move-Quality Arc Summary**: consolidate with eval band as the dominant structure and a small, robust, secondary clock association (still not causal). Sharpness moderation (C3 / 15.2A) is a separate later arc.
