# Sharpness Interaction Modeling — Combined

**Ticket:** 14.2B — C3c clock × sharpness move-quality moderation (pre-registered 14.2A)

## 1. Executive summary

Classification: **UNDERPOWERED / NO CLAIM**. Pooled primary `clock=60_180 × sharp_value_fragility_v1` interaction = +0.0102 [+0.0013, +0.0194] **excl 0**; per month +0.0074 [-0.0079, +0.0217] contains 0 / +0.0131 [+0.0001, +0.0274] **excl 0**. Predictive/descriptive moderation only — not causal, not human obviousness, no outcome/flagging claim.

## 2. Pre-registered primary question

Does the small controlled `60_180`-vs-`over_180` clock association with next-move ES loss become larger in sharp/value-fragile positions? Estimand = the `clock=60_180:sharp` interaction coefficient (DiD); positive ⇒ yes. Locked in PREREGISTRATION §C3c.

## 3. Inputs and joins

- 2024_09_250k_v1: joined 61,956 (coverage 1.0), sharp recompute mismatches 0.
- 2024_10_250k_v1: joined 59,625 (coverage 1.0), sharp recompute mismatches 0.

## 4. Primary row universe

- 2024_09_250k_v1: est 52,757, test 9,199.
- 2024_10_250k_v1: est 50,634, test 8,991.
- pooled: est 103,391, test 18,190.

## 5. Primary feature and contrast

Feature `sharp_value_fragility_v1` (validated by exact recompute). Contrast `60_180` vs `over_180` × sharp. Reference clock `over_180`.

## 6. Cell adequacy

| scope | sharp×60_180 | under_60×sharp |
|---|---|---|
| 2024_09_250k_v1 | 297 | 70 |
| 2024_10_250k_v1 | 282 | 83 |
| pooled | 579 | 153 |

(14.2A CI threshold ≥300/month for the limiting sharp×60_180 cell; under_60×sharp exploratory only.)

## 7. Primary train+val results

| scope | clock=60_180 × sharp | under_60 × sharp (exploratory) |
|---|---|---|
| 2024_09_250k_v1 | +0.0074 [-0.0079, +0.0217] contains 0 | +0.0092 [-0.0152, +0.0378] contains 0 |
| 2024_10_250k_v1 | +0.0131 [+0.0001, +0.0274] **excl 0** | +0.0195 [-0.0032, +0.0479] contains 0 |
| pooled | +0.0102 [+0.0013, +0.0194] **excl 0** | +0.0145 [-0.0030, +0.0352] contains 0 |

## 8. Month-specific replication

- 2024-09 +0.0074 [-0.0079, +0.0217] contains 0; 2024-10 +0.0131 [+0.0001, +0.0274] **excl 0**. Same-sign both months: True.

## 9. Pooled estimate

- `clock=60_180 × sharp`: +0.0102 [+0.0013, +0.0194] **excl 0** (clusters 21,652, rows 103,391).

## 10. Locked test confirmation

- pooled test point estimate `clock=60_180:sharp`: 0.0012; per month 2024_09_250k_v1 0.0054; 2024_10_250k_v1 -0.0035.

## 11. Robustness checks

Pooled decisive checks:
- continuous eval control: +0.0101 [+0.0014, +0.0192] **excl 0**.
- board-decided-only: +0.0038 [-0.0060, +0.0161] contains 0.

Per-month robustness tables are in the month reports (continuous-eval, board-decided, rating bins/quadratic, sharp relaxed/strict, clipped-cp + large-loss logistic targets, game/White/Black clustering).

## 12. Exploratory surface-bait diagnostics

Surface-bait moderator (per month, exploratory; **NOT human obviousness, no headline**): 2024_09_250k_v1 +0.0267 [-0.0128, +0.0747] contains 0; 2024_10_250k_v1 +0.0381 [+0.0019, +0.0768] **excl 0**.

## 13. Success / weak / null classification

****UNDERPOWERED / NO CLAIM**.** Basis: sharp×60_180 min monthly cell = 282; months +0.0074 / +0.0131; pooled +0.0102 [+0.0013,+0.0194] excl 0; limiting cell < 300/month → underpowered per 14.2A kill criterion.

The limiting sharp×60_180 cell and/or the clustered interaction CI are too small to support a claim. Reported as **underpowered / no claim** per the 14.2A kill criterion — not a null *finding*, an absence of resolving power.

## 14. What this does and does not show

- Not causal; no claim that time pressure causes worse moves or worse reasoning.
- `sharp_value_fragility_v1` is an engine-side value-fragility proxy — **NOT human obviousness** (deferred Tier B) and not a complete account of practical difficulty.
- Surface-bait is an exploratory diagnostic only, never a headline; not human obviousness.
- No outcome/flagging (C3a/C3b) sharpness model is run here.
- No 'degradation curve'; Stockfish eval is objective context, not ground truth; DRAW remains sparse and not solved; this is not a best-predictor claim.
- On any support, the moderation is a small, secondary, predictive/descriptive finding on top of eval-state-dominant move quality.

## 15. Recommended next ticket

**14.2C — Null / Power Interpretation and Roadmap Reconciliation Audit.** Outcome/flagging sharpness (C3a/C3b) remains a separate later arc; prior-trajectory extraction is an optional follow-up.
