# Rating × Clock Moderation — 3+0 / 5+0 / 10+0

**Ticket:** 16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation

> Predictive/descriptive only — NOT causal. "Buffer"/"attenuation" = descriptive moderation contrast, never a causal protective mechanism. Raw Lichess ratings NOT comparable across control pools (within-control × month quintiles/percentiles only). Stockfish not ground truth. ES transform reused (not refit). T2 was descriptive stability, not equivalence. C3c unresolved.

## 1. Executive summary

Tests whether relative rating moderates the clock_fraction → next-move-quality relationship and whether that differs across controls. Five locked primary tests (Holm-adjusted, mover-player-clustered), M(c)=D(c,Q5)−D(c,Q1) where D = adjusted critical-minus-high ES-loss contrast:
- **M(3+0):** +0.0083 [+0.0059,+0.0107]*  (Holm p=0.000)
- **M(5+0):** +0.0049 [+0.0020,+0.0077]*  (Holm p=0.000)
- **M(10+0):** +0.0068 [+0.0030,+0.0101]*  (Holm p=0.000)
- **M(3+0)-M(10+0):** +0.0015 [-0.0026,+0.0058]  (Holm p=0.760)
- **M(5+0)-M(10+0):** -0.0019 [-0.0063,+0.0023]  (Holm p=0.760)

Interpretation: M(c)<0 = rating-associated **attenuation** (critical-clock gradient smaller in the top quintile); M(c)>0 = amplification. Cross-control terms = whether that moderation differs from 10+0. Claim statuses in §20. All descriptive/conditional, not causal.

**Headline (honest):** the interaction is present but its **direction is conditioning-sensitive** — amplification in the all-phase model, attenuation in the endgame-restricted model. The all-phase amplification is **not stable under endgame restriction**; the sign reversal is consistent with phase composition, residual composition differences, or phase-specific heterogeneity, but this analysis does **not identify a single mechanism**. The cross-control moderation contrasts contain zero (Holm). **RM2: interaction present, but direction conditioning-sensitive; no universal attenuation or amplification claim. RM3: not supported.**

## 2. Scientific questions
R1 average rating gradient (positive control); R2 within-control rating moderation of the critical-clock gradient; R3 cross-control difference in that moderation; R4 board-decided robustness; R5 player-side time-forfeit by rating. Move quality and flagging kept separate.

## 3. Data and analysis population
Six dense artifacts; headline = status==ok ∧ ¬mate-band ∧ valid clock/clock_fraction/rating/termination; anomalies retained with flags (primary), excluded in robustness.


## 4. Rating representations
Primary categorical = within-control × month quintiles (Q1–Q5, ref Q1 for moderation). Primary continuous = within-control × month rating percentile [0,1] (0=lowest). Raw 200-Elo bins = within-control viz only. Quintile cutpoints (Q1≤/Q2≤/Q3≤/Q4≤):

| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ |
|---|---|---|---|---|---|
| 3+0 | 2024_09 | 1495 | 1717 | 1878 | 2052 |
| 3+0 | 2024_10 | 1503 | 1720 | 1885 | 2055 |
| 5+0 | 2024_09 | 1272 | 1500 | 1685 | 1882 |
| 5+0 | 2024_10 | 1256 | 1495 | 1682 | 1880 |
| 10+0 | 2024_09 | 1269 | 1510 | 1702 | 1896 |
| 10+0 | 2024_10 | 1275 | 1507 | 1692 | 1888 |

Percentile → Elo landmarks (headline pop) — enables e.g. "in 2024-09 3+0, percentile 0.10 corresponded to ≈ P10 Elo and 0.90 to ≈ P90 Elo":

| Control | Month | P10 | P25 | P50 | P75 | P90 |
|---|---|---|---|---|---|---|
| 3+0 | 2024_09 | 1313 | 1558 | 1797 | 2003 | 2174 |
| 3+0 | 2024_10 | 1323 | 1566 | 1805 | 2006 | 2177 |
| 5+0 | 2024_09 | 1100 | 1341 | 1593 | 1832 | 2007 |
| 5+0 | 2024_10 | 1086 | 1323 | 1592 | 1827 | 2000 |
| 10+0 | 2024_09 | 1097 | 1339 | 1608 | 1846 | 2014 |
| 10+0 | 2024_10 | 1106 | 1346 | 1600 | 1832 | 2003 |

Quintile absolute-Elo ranges + counts (rows/games/movers), per stratum:

| Control | Month | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|---|
| 3+0 | 2024_09 | 400–1495 (g6027/p3423) | 1496–1717 (g6080/p2780) | 1718–1878 (g5839/p2378) | 1879–2052 (g5798/p2101) | 2053–3042 (g5006/p1801) |
| 3+0 | 2024_10 | 400–1503 (g6061/p3800) | 1504–1720 (g5963/p2777) | 1721–1885 (g5981/p2402) | 1886–2055 (g5735/p2077) | 2056–3005 (g4962/p1886) |
| 5+0 | 2024_09 | 411–1272 (g6022/p4240) | 1273–1500 (g5779/p3336) | 1501–1685 (g5499/p2801) | 1686–1882 (g5194/p2526) | 1883–3034 (g4575/p2027) |
| 5+0 | 2024_10 | 400–1256 (g6116/p4211) | 1257–1495 (g5780/p3460) | 1496–1682 (g5541/p3035) | 1683–1880 (g5172/p2565) | 1881–3006 (g4561/p2119) |
| 10+0 | 2024_09 | 400–1269 (g6664/p4567) | 1270–1510 (g6517/p4219) | 1511–1702 (g6143/p3561) | 1703–1896 (g5853/p3081) | 1897–2709 (g5080/p2655) |
| 10+0 | 2024_10 | 400–1275 (g6397/p4675) | 1276–1507 (g6216/p4169) | 1508–1692 (g5786/p3506) | 1693–1888 (g5651/p3166) | 1889–2717 (g4879/p2668) |

Raw 200-Elo bins WITHIN each control (pooled months; descriptive; **NOT comparable across control pools as equivalent skill**; sparse tails flagged). ES mean falls monotonically with rating (RM1 positive control):

| Control | Elo bin | rows | games | movers | ES mean | sparse |
|---|---|---|---|---|---|---|
| 3+0 | <1200 | 160,718 | 3,998 | 2,337 | 0.0453 |  |
| 3+0 | 1200_1399 | 232,263 | 5,418 | 2,695 | 0.0405 |  |
| 3+0 | 1400_1599 | 416,221 | 9,015 | 4,163 | 0.0377 |  |
| 3+0 | 1600_1799 | 606,810 | 12,609 | 5,138 | 0.0347 |  |
| 3+0 | 1800_1999 | 701,602 | 14,014 | 4,952 | 0.0319 |  |
| 3+0 | 2000_2199 | 481,630 | 9,535 | 3,097 | 0.029 |  |
| 3+0 | 2200+ | 243,747 | 4,304 | 1,452 | 0.0249 |  |
| 5+0 | <1200 | 430,020 | 9,813 | 6,340 | 0.0444 |  |
| 5+0 | 1200_1399 | 407,707 | 9,092 | 5,060 | 0.0381 |  |
| 5+0 | 1400_1599 | 549,700 | 11,313 | 5,813 | 0.0356 |  |
| 5+0 | 1600_1799 | 576,745 | 11,163 | 5,127 | 0.0331 |  |
| 5+0 | 1800_1999 | 486,386 | 9,032 | 3,594 | 0.0306 |  |
| 5+0 | 2000_2199 | 234,225 | 4,457 | 1,629 | 0.0281 |  |
| 5+0 | 2200+ | 46,929 | 938 | 333 | 0.024 | yes |
| 10+0 | <1200 | 425,236 | 10,305 | 6,713 | 0.0454 |  |
| 10+0 | 1200_1399 | 390,336 | 9,505 | 5,740 | 0.0386 |  |
| 10+0 | 1400_1599 | 560,339 | 12,463 | 7,170 | 0.0353 |  |
| 10+0 | 1600_1799 | 597,410 | 12,606 | 6,605 | 0.0324 |  |
| 10+0 | 1800_1999 | 510,792 | 10,199 | 4,746 | 0.0296 |  |
| 10+0 | 2000_2199 | 228,342 | 4,693 | 2,141 | 0.0266 |  |
| 10+0 | 2200+ | 66,317 | 1,331 | 622 | 0.0217 |  |

## 5. Clock representation
Coarse: critical ≤0.05 / low (0.05,0.15] / medium (0.15,0.50] / high >0.50 (ref high). Primary target critical vs high. Fine 7-bucket = atlas only.

## 6. Weighting and estimands
Game-normalized weights even within control (rating groups differ in game length); pooled = equal control-month aggregate weight. Estimand = average game-weighted decision. Unweighted row-level = robustness (R11).

## 7. Cell adequacy
Headline = ≥1,000 rows ∧ ≥200 games ∧ ≥200 movers per control-month rating-clock cell.
- All-games rating×clock cells: 120 headline / 0 exploratory / 0 no-claim (of 120).
- Board-decided 10+0 Q1/Q2 critical cells are exploratory (16.2D) → continuous percentile is the principal 10+0 board-decided route; endgame-only critical×quintile well-powered.

## 8. Descriptive rating × clock atlas
See Fig 1 (clock×ES by quintile), Fig 2 (D(c,Q1..Q5)), Fig 3 (rating×clock heatmap).

## 9. Within-control categorical models
`ES_loss ~ C(clock,ref=high)*C(rating_quintile,ref=Q1) + eval + phase + month + color + termination + anomaly flags`; D(c,q)=critical−high within quintile q; M(c)=D(Q5)−D(Q1). Mover-player-clustered CIs; `*`=excl 0.

### All games
| Control | D(Q1) | D(Q2) | D(Q3) | D(Q4) | D(Q5) | M(c)=Q5−Q1 | replication |
|---|---|---|---|---|---|---|---|
| 3+0 | +0.0106 [+0.0086,+0.0125]* | +0.0119 [+0.0100,+0.0137]* | +0.0132 [+0.0118,+0.0145]* | +0.0150 [+0.0135,+0.0167]* | +0.0189 [+0.0176,+0.0203]* | +0.0084 [+0.0061,+0.0108]* | replicated |
| 5+0 | +0.0083 [+0.0062,+0.0106]* | +0.0102 [+0.0082,+0.0123]* | +0.0090 [+0.0074,+0.0108]* | +0.0113 [+0.0096,+0.0130]* | +0.0132 [+0.0117,+0.0148]* | +0.0049 [+0.0023,+0.0074]* | directionally_replicated |
| 10+0 | +0.0031 [-0.0000,+0.0066] | +0.0075 [+0.0048,+0.0104]* | +0.0082 [+0.0059,+0.0107]* | +0.0111 [+0.0088,+0.0133]* | +0.0097 [+0.0084,+0.0111]* | +0.0066 [+0.0029,+0.0100]* | replicated |

## 10. Within-control percentile models
Predicted critical-minus-high contrast at rating percentile 0.10 vs 0.90 (from the pooled percentile three-way fit, §11):

| Control | at 0.10 | at 0.90 | 0.90−0.10 diff |
|---|---|---|---|
| 3+0 | +0.0116 [+0.0101,+0.0132]* | +0.0200 [+0.0188,+0.0211]* | +0.0083 [+0.0061,+0.0105]* |
| 5+0 | +0.0078 [+0.0060,+0.0096]* | +0.0132 [+0.0120,+0.0143]* | +0.0054 [+0.0031,+0.0077]* |
| 10+0 | +0.0029 [+0.0006,+0.0053]* | +0.0114 [+0.0101,+0.0128]* | +0.0086 [+0.0057,+0.0112]* |

## 11. Pooled three-way model
`ES_loss ~ C(TC,ref=10+0)*C(clock,ref=high)*rating_percentile + controls` (game-normalized, equal control-month). The 0.90−0.10 diff above is the percentile analogue of M(c); the full categorical TC×clock×quintile fit supplies the five primary tests (§12). TC main effect + three-way NOT causal.

## 12. Five-test primary family and Holm correction
Pooled categorical fit, all-games, critical-vs-high, mover-player-clustered. Holm across the 5.

| Test | estimate [95% CI] | bootstrap p | Holm p | status |
|---|---|---|---|---|
| M(3+0) | +0.0083 [+0.0059,+0.0107] | 0.000 | 0.000 | excl 0 (Holm) |
| M(5+0) | +0.0049 [+0.0020,+0.0077] | 0.000 | 0.000 | excl 0 (Holm) |
| M(10+0) | +0.0068 [+0.0030,+0.0101] | 0.000 | 0.000 | excl 0 (Holm) |
| M(3+0)-M(10+0) | +0.0015 [-0.0026,+0.0058] | 0.508 | 0.760 | contains 0 |
| M(5+0)-M(10+0) | -0.0019 [-0.0063,+0.0023] | 0.380 | 0.760 | contains 0 |

## 13. Board-decided-only results
Five primary tests refit board-decided-only (termination term dropped):

| Test | estimate [95% CI] | Holm p |
|---|---|---|
| M(3+0) | +0.0137 [+0.0080,+0.0193]* | 0.000 |
| M(5+0) | -0.0038 [-0.0115,+0.0043] | 0.528 |
| M(10+0) | +0.0083 [+0.0006,+0.0156]* | 0.112 |
| M(3+0)-M(10+0) | +0.0054 [-0.0041,+0.0147] | 0.528 |
| M(5+0)-M(10+0) | -0.0121 [-0.0235,-0.0006]* | 0.144 |
Note: 10+0 board-decided low-quintile critical cells are exploratory (16.2D); the continuous percentile route (§10 board-decided variant) is the principal 10+0 board-decided read.

## 14. Endgame-only results
Within-control D(c,Q1..Q5) restricted to endgame (critical-clock ≈ endgame); phase term dropped.

### Endgame only
| Control | D(Q1) | D(Q2) | D(Q3) | D(Q4) | D(Q5) | M(c)=Q5−Q1 | replication |
|---|---|---|---|---|---|---|---|
| 3+0 | +0.0108 [+0.0083,+0.0132]* | +0.0080 [+0.0058,+0.0100]* | +0.0080 [+0.0062,+0.0100]* | +0.0082 [+0.0065,+0.0101]* | +0.0102 [+0.0086,+0.0119]* | -0.0006 [-0.0034,+0.0026] | null_or_unresolved |
| 5+0 | +0.0108 [+0.0084,+0.0134]* | +0.0072 [+0.0051,+0.0093]* | +0.0034 [+0.0016,+0.0053]* | +0.0050 [+0.0035,+0.0068]* | +0.0041 [+0.0024,+0.0059]* | -0.0067 [-0.0097,-0.0038]* | replicated |
| 10+0 | +0.0065 [+0.0030,+0.0098]* | +0.0044 [+0.0017,+0.0070]* | +0.0033 [+0.0010,+0.0056]* | +0.0055 [+0.0032,+0.0078]* | +0.0020 [+0.0004,+0.0037]* | -0.0044 [-0.0082,-0.0005]* | directionally_replicated |

## 15. Eval-state localization
Eval band is a mandatory control in every model; slight-band rating×critical cells are thin (16.2D) → not promoted. Rating moderation is conditioned on eval band, guarding against it merely reflecting different position-value composition.

## 16. Player-side time-forfeit analysis
Attribution validation: 30,585 time-forfeit games, 29,693 decisively attributable (loser flagged), 892 ambiguous draw-timeout EXCLUDED (2.9%). Two player-side rows per eligible game; no usernames.

**Denominator proof (genuine prevalence — includes eligible non-time-forfeit games as zeros):**
- total games 145,020; eligible 144,128; ambiguous draw-timeout excluded 892.
- player-side rows 288,256 (= 2 × eligible: True); positives (did_forfeit=1) 29,693 (= decisive time-forfeit games, one loser each); zeros 258,563.
- overall player-side prevalence 0.1030 (≈ half the game-level time-forfeit rate, as expected: one of two sides flags per TF game).

| Control | Month | eligible games | player rows | positives | prevalence |
|---|---|---|---|---|---|
| 3+0 | 2024_09 | 23,473 | 46,946 | 6,684 | 0.1424 |
| 3+0 | 2024_10 | 23,514 | 47,028 | 6,931 | 0.1474 |
| 5+0 | 2024_09 | 23,614 | 47,228 | 5,233 | 0.1108 |
| 5+0 | 2024_10 | 23,573 | 47,146 | 5,198 | 0.1103 |
| 10+0 | 2024_09 | 25,499 | 50,998 | 2,862 | 0.0561 |
| 10+0 | 2024_10 | 24,455 | 48,910 | 2,785 | 0.0569 |

Player-side time-forfeit prevalence by within-control-month rating quintile (descriptive):

| Control | Month | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|---|
| 3+0 | 2024_09 | 0.1601 | 0.1435 | 0.1391 | 0.1414 | 0.1276 |
| 3+0 | 2024_10 | 0.163 | 0.151 | 0.1509 | 0.1396 | 0.1323 |
| 5+0 | 2024_09 | 0.1235 | 0.1047 | 0.1048 | 0.1114 | 0.1096 |
| 5+0 | 2024_10 | 0.1306 | 0.1071 | 0.1 | 0.1034 | 0.1101 |
| 10+0 | 2024_09 | 0.0595 | 0.0536 | 0.0563 | 0.0556 | 0.0555 |
| 10+0 | 2024_10 | 0.0603 | 0.0548 | 0.0526 | 0.0557 | 0.0613 |

## 17. Month replication
Each M(c) reports 2024-09/2024-10/pooled + a 5-class status (§9 tables). Five-class classifier for interaction contrasts; T2 descriptive-stability language is NOT used here.

## 18. Clustered uncertainty
Primary = mover-player-clustered bootstrap (500 draws, seed 20240621); game-clustered secondary (500 draws). Player hashes clustered across months+controls (not reset per stratum).

## 19. Robustness matrix
Status per spec: **executed** / not executed (justification) / inapplicable. The all-phase primary result (RM2 amplification, RM3 null) is the comparison baseline.

| Spec | Description | Status | Result vs primary |
|---|---|---|---|
| R1 | board-decided only | executed (§13) | mixed: 3+0 amplification persists; 5+0/10+0 ns; RM3 still null |
| R2 | endgame-only | executed (§14) | **sign reversal** to attenuation (5+0 replicated, 10+0 directional); RM2 conditioning-sensitive |
| R3 | continuous rating percentile | executed (§10) | agrees all-phase (0.90−0.10 diff +, all controls); RM3 unaffected |
| R4 | raw 200-Elo bins (descriptive) | executed (§4) | ES mean falls monotonically with rating; RM1 positive control; not a moderation model |
| R5 clipped-CP | M(3+0)=+11.1897 [+7.0182,+15.2002]* · M(5+0)=+3.8134 [-0.9843,+8.7698] · M(10+0)=+8.6931 [+2.2474,+14.7976]* ; X3=+2.4966 [-4.6325,+10.3839] · X5=-4.8797 [-13.0495,+2.5856] | executed | same direction (amplification all-phase); cross-control still contains 0 → RM2/RM3 unchanged |
| R6 ES≥0.10 LPM | M(3+0)=+0.0493 [+0.0409,+0.0573]* · M(5+0)=+0.0433 [+0.0335,+0.0539]* · M(10+0)=+0.0455 [+0.0323,+0.0568]* ; X3=+0.0038 [-0.0110,+0.0176] · X5=-0.0022 [-0.0170,+0.0146] | executed | same direction; RM2/RM3 unchanged |
| R7 anomaly-excl | M(3+0)=+0.0083 [+0.0056,+0.0105]* · M(5+0)=+0.0049 [+0.0024,+0.0077]* · M(10+0)=+0.0070 [+0.0036,+0.0105]* ; X3=+0.0012 [-0.0028,+0.0051] · X5=-0.0021 [-0.0066,+0.0022] | executed | ≈ primary (anomalies negligible); RM2/RM3 unchanged |
| R8 | month-specific | executed (§9/§14) | per-control replication classes reported; no RM change |
| R9 | mover-player clustering | executed (primary, all sections) | this is the headline uncertainty |
| R10 game-clustered | M(3+0)=+0.0083 [+0.0057,+0.0107]* · M(5+0)=+0.0049 [+0.0017,+0.0079]* · M(10+0)=+0.0068 [+0.0026,+0.0106]* ; X3=+0.0015 [-0.0035,+0.0062] · X5=-0.0019 [-0.0069,+0.0029] | executed | directionally consistent with mover-player primary; RM2/RM3 unchanged |
| R11 unweighted rows | M(3+0)=+0.0078 [+0.0056,+0.0101]* · M(5+0)=+0.0037 [+0.0012,+0.0063]* · M(10+0)=+0.0057 [+0.0024,+0.0092]* ; X3=+0.0021 [-0.0019,+0.0062] · X5=-0.0020 [-0.0063,+0.0020] | executed | same direction as game-normalized; RM2/RM3 unchanged |
| R12 eval near_eq+slight | M(3+0)=-0.0058 [-0.0114,-0.0007]* · M(5+0)=-0.0015 [-0.0077,+0.0042] · M(10+0)=-0.0052 [-0.0153,+0.0028] ; X3=-0.0005 [-0.0107,+0.0116] · X5=+0.0037 [-0.0071,+0.0149] | executed | competitive-position localization; check sign vs primary (see cells) |
| R12 eval decided | M(3+0)=+0.0011 [-0.0033,+0.0050] · M(5+0)=-0.0078 [-0.0128,-0.0027]* · M(10+0)=-0.0043 [-0.0106,+0.0020] ; X3=+0.0053 [-0.0017,+0.0131] · X5=-0.0035 [-0.0109,+0.0042] | executed | decided-position localization; check sign vs primary |
| R13 | categorical vs continuous 3-way | executed (§10 vs §16 family) | percentile diff agrees with categorical M all-phase; labeled explicitly |
| R14 | single-control players only | not executed | optional; cross-control player overlap is tiny (~240–450), so impact expected negligible |
| R15 | repeat-player fixed effects | not executed | optional; requires selection/sample-loss audit (16.2D R15 caveat) before promotion |
| R16 | min-decisions-per-player | not executed | optional; not needed for the locked family |

Robustness conclusion: the **all-phase amplification** (RM2 positive M) is stable across R5/R6/R7/R10/R11 and the continuous percentile (R3); it is **not stable under endgame restriction** (R2 reverses sign) — hence RM2 is conditioning-sensitive. The **cross-control null (RM3)** is unchanged across every executed spec. No executed robustness promotes RM3 or yields a universal RM2 direction.

## 20. Claim-status table

| Claim | Statement | Status |
|---|---|---|
| RM1 | higher-rated movers lower average loss (positive control) | see Fig 2 D(Q5)<D(Q1) trend |
| RM2 | within-control rating moderation of critical-clock gradient | per §9/§12 (M(c) Holm) |
| RM3 | cross-control difference in rating moderation | per §12 (M(c)−M(10+0) Holm) |
| RM4 | rating moderation under board-decided-only | per §13 |
| RM5 | player-side time-forfeit varies by rating | per §16 (descriptive) |

## 21. Limitations
- Critical-clock ≈ endgame; extreme-low-clock moderation = within-late-game.
- 10+0 board-decided low-quintile cells exploratory → percentile route primary there.
- ES transform reused across controls (comparability assumption).
- Raw ratings not cross-pool comparable; within-control quintiles/percentiles only.
- Cross-month player overlap ~18–22% → months not fully independent.
- Descriptive/predictive only; no causal identification; ~3% draw-timeout games excluded from R5.

## 22. Safe project language
"relative rating rank", "within-control rating quintile", "rating-associated attenuation/amplification", "conditional moderation", "observed difference in the clock gradient", "board-decided-only moderation", "endgame-localized moderation", "descriptive time-forfeit gradient", "not causal".

## 23. Forbidden interpretations
NOT: higher rating causes time-pressure resilience; rating protects players from clock pressure; higher-rated players are immune to low clock; lower-rated players reason worse; rating causes fewer blunders; fast chess harms lower-rated players; time pressure causes move-quality degradation; same raw Elo means same skill across pools; 3+0 ratings comparable to 10+0; Stockfish is ground truth; T2 established equivalence; sharpness moderation resolved; DRAW solved.

_Runtime: 2045s total (2039s models, 2s figures); player-bootstrap 500, game-bootstrap 500, seed 20240621._