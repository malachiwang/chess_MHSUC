# Cross-Time-Control Move Quality — 3+0 / 5+0 / 10+0

**Ticket:** 16.2B — Cross-Time-Control Atlas / Controlled Modeling Implementation

> Predictive/descriptive only — **NOT causal**. Raw Lichess ratings are NOT comparable across control pools (within-control rating quintiles used throughout). The expected-score transform is reused across controls (a comparability assumption, not refit). Stockfish eval is objective context, not ground truth. Game-level time-forfeit prevalence uses one row per game; move-level termination shares are a different denominator.

## 1. Executive summary

First full no-increment cross-time-control analysis over six dense artifacts. Four distinct questions (T1 termination prevalence; T2 average move quality; T3 within-control clock gradient; T4 cross-control moderation). Headline findings (see claim-status table §18):
- **T1 (game-level time-forfeit prevalence):** 3+0 ≈ 0.292/0.301, 5+0 ≈ 0.226/0.226, 10+0 ≈ 0.115/0.116 (Sep/Oct). Monotone 3+0 > 5+0 > 10+0 both months — descriptive.
- **T2 (average ES loss):** broadly similar across controls (3+0 mean 0.0338, 5+0 0.0349, 10+0 0.0346; 2024-09). Descriptively stable / broadly similar — **not 'identical', and NOT a formal equivalence result** (no equivalence margin or test was run; T2 is descriptive and is not classified by the replication ladder).
- **T3/T4:** see §10–§11; clock gradients are conditional, replicated, and small relative to eval state; both survive mover-player clustering (R8, §14); very-low-clock cells are heavily endgame-confounded (§15).
- Replication note: T1/T3/T4 are formally replicated contrasts; T2 is descriptive stability only. "All four questions replicated" would be incorrect.

## 2. Scientific questions
T1 game-level termination prevalence; T2 average move quality; T3 within-control clock gradient (conditional on eval/phase/rating-quintile/month/color/termination/anomaly); T4 cross-control moderation (TC × clock_fraction). Kept distinct; no single 'time pressure effect'.

## 3. Data and denominators
Six dense artifacts (status all ok, 0 dup keys, both colors, 1.0 player-hash, no usernames).

| Control | Month | Headline rows | Headline games | Rows/game |
|---|---|---|---|---|
| 3+0 | 2024_09 | 1,422,173 | 23,703 | 60.0 |
| 3+0 | 2024_10 | 1,420,818 | 23,721 | 59.9 |
| 5+0 | 2024_09 | 1,367,293 | 23,756 | 57.6 |
| 5+0 | 2024_10 | 1,364,419 | 23,734 | 57.5 |
| 10+0 | 2024_09 | 1,416,313 | 25,582 | 55.4 |
| 10+0 | 2024_10 | 1,362,459 | 24,524 | 55.6 |

Row counts are nearly equal but game counts differ (10+0 has more games, fewer rows/game) → matched accepted-game caps do NOT imply equal move-level denominators. Pooled estimates use game-normalized weights with equal control-month aggregate weight (§16).

## 4. Analysis populations
Primary headline = status==ok ∧ ¬mate-band ∧ valid clock/clock_fraction/rating/termination; anomaly rows (clock_fraction>1, negative think-time) RETAINED with explicit flags. Robustness excludes anomalies. Mate-band excluded from headline.

## 5. Rating normalization
Within-control × month mover-rating quintiles (Q1–Q5, ref Q3). Cutpoints (Q1≤/Q2≤/Q3≤/Q4≤):

| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ |
|---|---|---|---|---|---|
| 3+0 | 2024_09 | 1495 | 1717 | 1878 | 2052 |
| 3+0 | 2024_10 | 1503 | 1720 | 1885 | 2055 |
| 5+0 | 2024_09 | 1272 | 1500 | 1685 | 1882 |
| 5+0 | 2024_10 | 1256 | 1495 | 1682 | 1880 |
| 10+0 | 2024_09 | 1269 | 1510 | 1702 | 1896 |
| 10+0 | 2024_10 | 1275 | 1507 | 1692 | 1888 |

3+0 cutpoints sit ~200 Elo above 5+0/10+0 — raw cross-pool rating differences are NOT skill differences. Raw 200-Elo bins are robustness only (R9).

## 6. Clock-fraction construction
`clock_fraction = clock_before_s / initial_time_s` (verified). Fine atlas buckets: ≤.02/.02-.05/.05-.10/.10-.25/.25-.50/.50-.75/>.75. Coarse model buckets: critical≤.05 / low .05-.15 / medium .15-.50 / high >.50 (ref=high). clock_fraction>1 stays in the top bucket with an anomaly flag.

## 7. Game-level termination prevalence (T1)
**One row per game** (NOT move rows).

| Control | Month | Games | TF games | Pr(time forfeit) | Pr(board decided) |
|---|---|---|---|---|---|
| 3+0 | 2024_09 | 23,703 | 6,914 | 0.2917 | 0.7083 |
| 3+0 | 2024_10 | 23,721 | 7,138 | 0.3009 | 0.6991 |
| 5+0 | 2024_09 | 23,756 | 5,375 | 0.2263 | 0.7737 |
| 5+0 | 2024_10 | 23,734 | 5,359 | 0.2258 | 0.7742 |
| 10+0 | 2024_09 | 25,582 | 2,945 | 0.1151 | 0.8849 |
| 10+0 | 2024_10 | 24,524 | 2,854 | 0.1164 | 0.8836 |

## 8. Descriptive move-quality atlas (T2)

| Control | Month | rows | ES mean | ES median | ES p90 | Pr(ES≥.10) | Pr(ES≥.05) | CP mean | CP median | CP p90 | Pr(CP≥100) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10+0 | 2024_09 | 1,416,313 | 0.0346 | 0.0114 | 0.0926 | 0.0903 | 0.2009 | 58.8959 | 21.0 | 158.0 | 0.1752 |
| 10+0 | 2024_10 | 1,362,459 | 0.0346 | 0.0114 | 0.0926 | 0.0902 | 0.2006 | 58.8976 | 21.0 | 158.0 | 0.1746 |
| 3+0 | 2024_09 | 1,422,173 | 0.0338 | 0.0113 | 0.0898 | 0.0865 | 0.1953 | 57.0765 | 20.0 | 152.0 | 0.1671 |
| 3+0 | 2024_10 | 1,420,818 | 0.0336 | 0.0112 | 0.0897 | 0.0863 | 0.1955 | 56.6349 | 20.0 | 151.0 | 0.1662 |
| 5+0 | 2024_09 | 1,367,293 | 0.0349 | 0.0117 | 0.0931 | 0.0911 | 0.2027 | 59.0755 | 21.0 | 157.0 | 0.1745 |
| 5+0 | 2024_10 | 1,364,419 | 0.0352 | 0.0119 | 0.094 | 0.092 | 0.2045 | 59.7376 | 21.0 | 159.0 | 0.1769 |

See Fig 1–3, 7, 8. Average ES loss is broadly similar across controls; eval state and phase dominate the within-control variation.

## 9. Board-decided-only atlas
Board-decided-only within-control models in §10 (`board_decided` games only; termination term removed). See Fig 5. This isolates board play from the flagging channel.

## 10. Within-control controlled models (T3)
OLS `expected_score_loss ~ C(clock_coarse,ref=high) + C(eval_band,ref=decided) + C(phase,ref=middlegame) + C(rating_quintile,ref=Q3) + C(month) + C(color) + C(termination,ref=board_decided) + clock_gt_initial + neg_think`. Game-clustered bootstrap CIs; `*` = CI excludes 0.

### All games

| Control | clock contrast | pooled | 2024-09 | 2024-10 | replication |
|---|---|---|---|---|---|
| 3+0 | critical vs high | +0.0117 [+0.0109,+0.0126]* | +0.0114 [+0.0101,+0.0125]* | +0.0120 [+0.0109,+0.0131]* | replicated |
| 3+0 | low vs high | +0.0062 [+0.0057,+0.0068]* | +0.0059 [+0.0052,+0.0066]* | +0.0065 [+0.0057,+0.0072]* | replicated |
| 3+0 | medium vs high | +0.0027 [+0.0024,+0.0030]* | +0.0027 [+0.0022,+0.0031]* | +0.0027 [+0.0023,+0.0031]* | replicated |
| 5+0 | critical vs high | +0.0077 [+0.0069,+0.0086]* | +0.0071 [+0.0058,+0.0083]* | +0.0082 [+0.0070,+0.0094]* | replicated |
| 5+0 | low vs high | +0.0044 [+0.0038,+0.0050]* | +0.0040 [+0.0031,+0.0048]* | +0.0048 [+0.0040,+0.0055]* | replicated |
| 5+0 | medium vs high | +0.0020 [+0.0017,+0.0023]* | +0.0018 [+0.0013,+0.0023]* | +0.0021 [+0.0017,+0.0025]* | replicated |
| 10+0 | critical vs high | +0.0056 [+0.0046,+0.0067]* | +0.0054 [+0.0040,+0.0070]* | +0.0057 [+0.0041,+0.0073]* | replicated |
| 10+0 | low vs high | +0.0026 [+0.0020,+0.0033]* | +0.0028 [+0.0018,+0.0038]* | +0.0024 [+0.0015,+0.0033]* | replicated |
| 10+0 | medium vs high | +0.0005 [+0.0002,+0.0008]* | +0.0005 [+0.0001,+0.0009]* | +0.0005 [+0.0000,+0.0009]* | replicated |

## 11. Pooled interaction model (T4)
Pooled OLS adds `C(time_control,ref=10+0) + TC×clock_coarse`. Game-normalized weights, equal control-month aggregate weight. Interaction = (control clock gradient) − (10+0 clock gradient). TC main effect is descriptive, NOT causal.

| TC × clock | pooled | 2024-09 | 2024-10 | replication |
|---|---|---|---|---|
| 3+0 × critical | +0.0089 [+0.0075,+0.0103]* | +0.0091 [+0.0072,+0.0111]* | +0.0087 [+0.0066,+0.0106]* | replicated |
| 3+0 × low | +0.0065 [+0.0057,+0.0074]* | +0.0060 [+0.0048,+0.0073]* | +0.0070 [+0.0059,+0.0083]* | replicated |
| 3+0 × medium | +0.0046 [+0.0042,+0.0050]* | +0.0045 [+0.0039,+0.0051]* | +0.0046 [+0.0040,+0.0052]* | replicated |
| 5+0 × critical | +0.0033 [+0.0018,+0.0047]* | +0.0036 [+0.0017,+0.0057]* | +0.0031 [+0.0010,+0.0050]* | replicated |
| 5+0 × low | +0.0037 [+0.0028,+0.0046]* | +0.0032 [+0.0020,+0.0045]* | +0.0041 [+0.0028,+0.0053]* | replicated |
| 5+0 × medium | +0.0028 [+0.0024,+0.0033]* | +0.0028 [+0.0022,+0.0035]* | +0.0029 [+0.0023,+0.0036]* | replicated |

## 12. Termination model
Game-level (one row/game). (1) raw prevalence (§7); (2) minimally adjusted logit (TC + month + rating quintile); (3) game-length-adjusted (secondary — length is partly downstream of forfeit, interpret cautiously). TC odds ratios vs 10+0:

| Model | 3+0 OR | 5+0 OR |
|---|---|---|
| adjusted (month+rating) | 3.22 | 2.234 |
| + game-length (secondary) | 3.289 | 2.314 |
Odds ratios > 1 mean higher time-forfeit odds than 10+0 at equal covariates — descriptive, NOT a causal effect of time control.

## 13. Month replication
Every headline contrast reports 2024-09, 2024-10, pooled, and a replication class (replicated / directionally_replicated / pooled_only / not_replicated / null_or_unresolved). See §10–§11 tables and Fig 10.

## 14. Robustness results

| Spec | Description | 3+0 crit-vs-high pooled | 5+0 crit | 10+0 crit |
|---|---|---|---|---|
| R1 | board-decided only | +0.0062 [+0.0044,+0.0077]* | +0.0051 [+0.0033,+0.0069]* | +0.0031 [+0.0014,+0.0047]* |
| R2 | anomaly-excluded | +0.0117 [+0.0109,+0.0126]* | +0.0077 [+0.0069,+0.0086]* | +0.0056 [+0.0045,+0.0066]* |
| R4 | clipped-CP outcome | +22.5708 [+21.2010,+24.0375]* | +15.3769 [+14.0699,+17.0042]* | +11.1520 [+9.3925,+13.0925]* |

(R3 continuous/spline, R5 ES≥0.10 binary, R7 unweighted pooled, R9 raw-bins available via module flags.)

### R8 — mover-player-clustered robustness (executed, 200 draws, seed 20240621)

Headline T3/T4 contrasts refit with the bootstrap cluster key switched from `game_id` to
`mover_player_hash` (the salted one-way mover hash; clusters whole players, not games). Both runs use
200 draws here for a like-for-like comparison (the primary tables use 500 game-clustered draws; point
estimates are identical, CIs differ trivially).

| Target | game-clustered (200) | player-clustered (200) | sign agrees | player CI excl 0 | player clusters |
|---|---|---|---|---|---|
| T3 3+0 critical vs high | +0.0117 [+0.0110,+0.0125] | +0.0117 [+0.0110,+0.0124] | yes | yes | 22,332 |
| T3 5+0 critical vs high | +0.0077 [+0.0069,+0.0086] | +0.0077 [+0.0068,+0.0086] | yes | yes | 26,114 |
| T3 10+0 critical vs high | +0.0056 [+0.0047,+0.0067] | +0.0056 [+0.0046,+0.0064] | yes | yes | 31,381 |
| T4 3+0 × critical (vs 10+0) | +0.0089 [+0.0076,+0.0100] | +0.0089 [+0.0075,+0.0102] | yes | yes | 77,408 |
| T4 5+0 × critical (vs 10+0) | +0.0033 [+0.0019,+0.0047] | +0.0033 [+0.0023,+0.0048] | yes | yes | 77,408 |

**All five headline T3/T4 targets survive mover-player clustering:** point estimates unchanged, signs
agree, and every player-clustered CI excludes zero. Player-clustered CIs are essentially the same width
as game-clustered (player clusters are fewer than game clusters but still tens of thousands). T3 and T4
are not weakened; claim statuses are unchanged.

## 15. Phase and eval localization
**Very-low clock fraction is concentrated heavily in endgame positions** (critical-clock cells are ~entirely endgame; opening critical ≈ 0). Therefore controlled low-clock contrasts are conditional on phase, and extreme-low-clock results should be read as **low-clock variation within late-game positions**, not a generic all-game clock effect. Eval state dominates ES loss (Fig 7); phase conditioning is mandatory (Fig 8).

## 16. Weighting and estimands
Within-control models = unweighted (each control self-contained). Pooled = game-normalized weight `1/(games_in_stratum × headline_moves_in_game)`, scaled to mean 1, so each game has equal total weight and each of the six control-month strata has equal aggregate weight. Unweighted row-level pooled = robustness R7.

## 17. Limitations
- clock_fraction ≈ phase confound (§15); extreme-low-clock = endgame-dominated.
- ES transform reused across controls (comparability assumption; cp outcomes are the transform-free cross-check).
- Raw ratings not cross-pool comparable; only within-control quintiles used.
- 10+0 extracted at full month (~25.6k games) vs capped 3+0/5+0 (~23.7k) — game-normalized weighting addresses denominators but pools still differ in composition.
- Cross-month player overlap (~18–22%) → months not fully independent; game-clustered CIs primary, mover-player-clustered robustness executed (R8 §14): T3/T4 headline targets survive.
- Descriptive/predictive only; no causal identification.

## 18. Claim-status table

| Claim | Statement | Status |
|---|---|---|
| T1 | Game-level time-forfeit prevalence 3+0 > 5+0 > 10+0, both months | replicated descriptive ordering |
| T2 | Average next-move ES loss broadly similar across controls | descriptively stable / broadly similar; **NOT** a formal equivalence result and **not classified as replicated equivalence** (no equivalence margin or test was run) |
| T3 | Lower clock fraction associated with higher ES loss within control (conditional) | replicated conditional within-control gradients (§10; survives mover-player clustering R8) |
| T4 | Conditional clock–loss gradient differs across controls | replicated conditional cross-control moderation (§11; survives mover-player clustering R8) |

Note: T2 is a descriptive similarity statement, not a coefficient/difference claim, so it is outside the
replication classifier (which applies to T1/T3/T4 contrasts). T1/T3/T4 are replicated in the formal
sense (same sign + both month CIs exclude 0). "All four questions replicated" would be incorrect — T2
is descriptive stability only.

## 19. Safe project language
"observed cross-time-control pattern", "conditional association", "within-control clock gradient", "game-level time-forfeit prevalence", "board-decided-only result", "month-replicated", "directionally replicated", "pooled-only", "not causal".

## 20. Forbidden interpretations
NOT: time pressure causes worse reasoning; low clock causes blunders; faster time controls cause worse chess; faster controls cause flagging; faster controls do not harm move quality; increment causes better reasoning; players reason equally well at all speeds; Stockfish is ground truth; raw ratings comparable across pools; cross-time-control differences are causal; time pressure affects only flagging; sharpness moderation confirmed or disproven; DRAW solved.

_Runtime: 109s total (103s models, 2s figures). Bootstrap draws=500 (player=200), seed=20240621._