# Controlled Dense Move-Quality Model — 10+0, 2024-09 and 2024-10

**Ticket:** 15.4D | **bootstrap:** 500 game-clustered draws, seed 20240617 | **runtime:** 61s

## 1. Executive summary

Controlled dense per-ply model of next-move **expected-score loss**, net of eval state, phase, mover rating, month, mover color, and termination channel, with **game-clustered** uncertainty. The estimand is a **conditional association, not causal**. Eval state is the positive control; clock is the focal predictor (reference `over_180`). Headline focal contrast `60_180` vs `over_180` = **+0.0009** [+0.0005, +0.0014] * (`*` = CI excludes 0). Marginal atlas (15.4B) clock curves are U-shaped/confounded; this controlled model is the inferential statement. Stockfish eval is objective context, not ground truth.

## 2. Inputs and validation
- Combined rows: 2,933,756; months 2024_09, 2024_10; per-month counts match 15.3C/15.3D; no raw-username columns; ES∈[0,1]; clipped cp≥0; both colors present; player hashes present: True.

## 3. Filtering and denominators
| month | rows | mate-band (excl.) | clock>600 | negative think |
|---|---|---|---|---|
| 2024_09 | 1,496,890 | 80,577 | 116 | 133 |
| 2024_10 | 1,436,866 | 74,407 | 91 | 125 |
- Headline rows (status ok ∧ ¬mate-band ∧ both colors): **2,778,772**.
- Board-decided headline: 2,387,377; time-forfeit excluded from S3.

## 4. Model specification

`expected_score_loss ~ C(clock_coarse, ref=over_180) + C(eval_band, ref=decided) + C(phase, ref=middlegame) + C(rating_bin, ref=1600_1799) + C(month, ref=2024_09) + C(mover_color, ref=white) + C(termination_channel, ref=board_decided) + clock_anom + think_anom + intercept`. Numpy OLS adjusted-mean; coefficients are expected-score-loss differences vs the reference cell.

## 5. Primary expected-score-loss model

OLS on 2,778,772 headline rows; 50,106 game clusters; 500/500 bootstrap refits.

## 6. Clock coefficient table

| contrast | estimate | 95% CI (game-clustered) |
|---|---|---|
| clock under_10 vs over_180 | +0.0083 | [+0.0068, +0.0101] * |
| clock 10_30 vs over_180 | +0.0045 | [+0.0034, +0.0056] * |
| clock 30_60 vs over_180 | +0.0030 | [+0.0022, +0.0039] * |
| clock 60_180 vs over_180 | +0.0009 | [+0.0005, +0.0014] * |

Reference = `over_180`. Coefficient = conditional ES-loss difference vs over_180.

## 7. Eval-state positive-control table

| contrast | estimate | 95% CI (game-clustered) |
|---|---|---|
| eval near_equal vs decided | +0.0222 | [+0.0218, +0.0227] * |
| eval slight vs decided | +0.0306 | [+0.0302, +0.0311] * |
| eval clear vs decided | +0.0165 | [+0.0161, +0.0169] * |

Eval band dominates (reference `decided`): the slight/near_equal coefficients are much larger in magnitude than the clock coefficients — the positive control.

## 8. Month-specific replication

| contrast | 2024-09 | 2024-10 |
|---|---|---|
| clock under_10 vs over_180 | +0.0079 [+0.0053, +0.0105] * | +0.0086 [+0.0061, +0.0111] * |
| clock 10_30 vs over_180 | +0.0045 [+0.0031, +0.0059] * | +0.0046 [+0.0031, +0.0063] * |
| clock 30_60 vs over_180 | +0.0036 [+0.0024, +0.0047] * | +0.0025 [+0.0015, +0.0037] * |
| clock 60_180 vs over_180 | +0.0010 [+0.0004, +0.0015] * | +0.0009 [+0.0003, +0.0015] * |

## 9. Board-decided-only robustness

| contrast | estimate | 95% CI (game-clustered) |
|---|---|---|
| clock under_10 vs over_180 | +0.0079 | [+0.0035, +0.0125] * |
| clock 10_30 vs over_180 | +0.0024 | [+0.0005, +0.0044] * |
| clock 30_60 vs over_180 | +0.0027 | [+0.0015, +0.0037] * |
| clock 60_180 vs over_180 | +0.0004 | [-0.0001, +0.0009] |

Restricted to `is_time_forfeit == False` (termination control dropped as constant). Tests whether the clock residual survives outside the direct flagging channel. (Extreme `under_10` board-decided cells are sparse — read cautiously.)

## 10. Clipped-CP robustness

| contrast | estimate | 95% CI (game-clustered) |
|---|---|---|
| clock under_10 vs over_180 | +16.1938 | [+13.4463, +19.3446] * |
| clock 10_30 vs over_180 | +8.6899 | [+6.6854, +10.5532] * |
| clock 30_60 vs over_180 | +5.9524 | [+4.5551, +7.4567] * |
| clock 60_180 vs over_180 | +2.1509 | [+1.4266, +2.9444] * |

Target = `cp_loss_clipped` (centipawns; familiar but skewed).

## 11. Large-loss probability robustness

Linear probability models (OLS on indicator); focal clock contrast:

| target | 60_180 vs over_180 | logistic-sign |
|---|---|---|
| es_ge_05 | +0.00110 [-0.0013, +0.0033] | — |
| es_ge_10 | +0.00580 [+0.0040, +0.0073] * | +0.0686 |

LPM = primary (interpretable); single unregularized logistic provides a sign check (no bootstrap).

## 12. Alternative clock/eval/rating robustness

| spec | 60_180 vs over_180 |
|---|---|
| continuous-eval control | +0.0001 [-0.0004, +0.0006] |
| rating_z (continuous) | +0.0011 [+0.0006, +0.0015] * |
| anomaly-excluded | +0.0009 [+0.0005, +0.0014] * |

## 13. Interaction summaries

Focal `60_180` vs `over_180` clock contrast within subgroups (subgroup fits; sparse subgroups flagged):

| subgroup family | subgroup | 60_180 vs over_180 | n |
|---|---|---|---|
| eval_band | near_equal | +0.0008 [-0.0004, +0.0018] | 933,299 |
| eval_band | slight | +0.0025 [+0.0015, +0.0036] * | 738,517 |
| eval_band | clear | -0.0000 [-0.0005, +0.0006] | 932,186 |
| eval_band | decided | +0.0000 [-0.0008, +0.0008] | 174,770 |
| phase | opening | -0.0089 [-0.0196, +0.0033] | 588,926 |
| phase | middlegame | +0.0024 [+0.0015, +0.0035] * | 1,476,812 |
| phase | endgame | -0.0000 [-0.0006, +0.0003] | 713,034 |
| termination_channel | board_decided | +0.0004 [-0.0001, +0.0009] | 2,387,377 |
| termination_channel | time_forfeit | +0.0011 [+0.0003, +0.0020] * | 391,395 |

Exploratory; locates where any clock residual concentrates. No sharpness interaction (Phase 15.5).

## 14. Uncertainty and clustering

- Primary: game-clustered sufficient-statistics bootstrap, 500 draws, 50,106 game clusters.
- mover-player-clustered robustness (31,381 clusters): 60_180 vs over_180 +0.0009 [+0.0005, +0.0013] *.
- Naive row-level SEs are NOT used (per-ply rows are within-game/within-player correlated).

## 15. Comparison to 15.1D/15.1F checkpoint controlled result

| quantity | checkpoint (15.1D/F) | dense (15.4D) |
|---|---|---|
| 60_180 vs over_180 (ES loss) | ~+0.0034 [+0.0015,+0.0051] | +0.0009 [+0.0005, +0.0014] * |
| eval band dominates | yes | yes (see §7) |
| board-decided-only survives | yes (small) | see §9 |

## 16. Interpretation

- Eval state dominates the dense controlled model (positive control, §7).
- The focal clock contrast (`60_180` vs `over_180`) is reported with its sign, magnitude, game-clustered CI, month replication (§8), and board-decided survival (§9). The result is read as a **conditional association**, not causal, and is compared honestly to the checkpoint result (§15) — not forced to match it.
- The atlas U-shaped marginal (15.4B) remains a descriptive warning; this controlled model is the inferential statement.
- Extreme low-clock board-decided cells are sparse (survivor population); those subgroup estimates are exploratory.

## 17. Non-claims

Conditional/predictive association only; **NOT causal**. No "low clock causes blunders"; no "time pressure causes worse reasoning"; no "clock proves cognitive degradation". Stockfish eval is objective context, not ground truth. No human-obviousness modeling; no sharpness (Phase 15.5); no cross-time-control (Phase 16); no synthesis. C4 and C3c unchanged; ES transform not refit.

## 18. Recommended next ticket

**15.5A — Sharpness-Enriched Constraint Atlas Audit** (design joining the MultiPV sharpness layer to the dense atlas; C3c move-quality-first). Not Phase 16; not synthesis.
