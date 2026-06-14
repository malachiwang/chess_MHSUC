# Constraint Atlas — 2024_10_250k_v1

**Ticket:** 15.1B — Constraint Atlas Descriptive Curves Implementation

## 1. Executive summary

Descriptive next-move loss readout over 59,625 non-mate-band OK checkpoint moves. Overall mean expected-score (ES) loss 0.0341, median 0.0101 (right-skewed). Board-decided and time-forfeit populations are summarized separately and side-by-side; clock is always conditioned on checkpoint. Descriptive only — see caveats (§14).

## 2. Input artifact and schema

`data/processed/next_move_loss_2024_10_250k_v1.parquet` (OK rows; mate-band flagged and excluded from loss summaries). Derived bins: clock_coarse, clock_fine, rating_bin, eval_band, channel, board_decided, is_late, large-loss indicators.

## 3. Metric definitions

- Primary: `expected_score_loss = max(0, ES(mover_pre_cp) − ES(mover_post_cp))` (mover's perspective; train-fit logistic transform, scale 348.4).
- Secondary: `clipped_cp_loss = min(max(0, mover_pre_cp − mover_post_cp), 1000)`.
- Large-loss probabilities: P(ES>0.05), P(ES>0.10), P(cp>100), P(cp>200).

## 4. Cell-count policy

hidden_sparse (n<50) — not summarized; descriptive_only (50≤n<300) — point estimates, no CI; ci_ok (n≥300) — CI-eligible. Game-level clustered bootstrap CIs are shown only for the headline late-group clock cells (§7).

## 5. Overall loss summary

| Population | n | mean ES | median ES | p75 ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|
| all_games | 59,625 | 0.0341 | 0.0101 | 0.0387 | 0.0933 | 9.2 | 57.4 | 19.0 | 17.0 |
| board_decided | 51,579 | 0.0340 | 0.0100 | 0.0385 | 0.0926 | 9.1 | 57.4 | 19.0 | 17.0 |
| time_forfeit | 8,046 | 0.0349 | 0.0108 | 0.0399 | 0.0978 | 9.7 | 57.4 | 19.0 | 17.2 |

## 6. Checkpoint-conditioned clock summary

All-games, by checkpoint × coarse clock bucket:

| selected_position_type | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|---|
| move_10 | 60_180 | 4 | hidden_sparse | — | — | — | — | — | — | — |
| move_10 | over_180 | 23217 | ci_ok | 0.0358 | 0.0119 | 0.0997 | 10.0000 | 55.8 | 19.0 | 16.5 |
| move_20 | 60_180 | 243 | descriptive_only | 0.0330 | 0.0072 | 0.1086 | 11.5000 | 54.6 | 13.0 | 19.8 |
| move_20 | over_180 | 18095 | ci_ok | 0.0373 | 0.0123 | 0.1020 | 10.3000 | 63.8 | 23.0 | 19.4 |
| move_20 | under_60 | 28 | hidden_sparse | — | — | — | — | — | — | — |
| move_30 | 60_180 | 1041 | ci_ok | 0.0351 | 0.0093 | 0.0851 | 8.9000 | 63.7 | 20.0 | 18.4 |
| move_30 | over_180 | 10180 | ci_ok | 0.0304 | 0.0081 | 0.0792 | 7.6000 | 55.6 | 17.0 | 16.1 |
| move_30 | under_60 | 265 | descriptive_only | 0.0295 | 0.0086 | 0.0707 | 6.4000 | 57.2 | 21.0 | 18.9 |
| move_40 | 60_180 | 1341 | ci_ok | 0.0271 | 0.0050 | 0.0700 | 6.6000 | 50.8 | 12.0 | 14.6 |
| move_40 | over_180 | 4703 | ci_ok | 0.0232 | 0.0047 | 0.0604 | 5.5000 | 44.8 | 10.0 | 12.7 |
| move_40 | under_60 | 508 | ci_ok | 0.0318 | 0.0050 | 0.0897 | 9.4000 | 58.6 | 10.5 | 17.1 |

Board-decided only, by checkpoint × coarse clock bucket:

| selected_position_type | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|---|
| move_10 | 60_180 | 3 | hidden_sparse | — | — | — | — | — | — | — |
| move_10 | over_180 | 20529 | ci_ok | 0.0360 | 0.0121 | 0.0999 | 10.0000 | 56.2 | 19.0 | 16.6 |
| move_20 | 60_180 | 127 | descriptive_only | 0.0226 | 0.0036 | 0.0711 | 5.5000 | 39.4 | 6.0 | 13.4 |
| move_20 | over_180 | 15913 | ci_ok | 0.0372 | 0.0122 | 0.1013 | 10.2000 | 63.9 | 23.0 | 19.4 |
| move_20 | under_60 | 8 | hidden_sparse | — | — | — | — | — | — | — |
| move_30 | 60_180 | 657 | ci_ok | 0.0336 | 0.0088 | 0.0805 | 8.2000 | 62.8 | 20.0 | 18.7 |
| move_30 | over_180 | 8931 | ci_ok | 0.0303 | 0.0077 | 0.0791 | 7.5000 | 55.8 | 16.0 | 16.3 |
| move_30 | under_60 | 84 | descriptive_only | 0.0212 | 0.0063 | 0.0555 | 3.6000 | 44.2 | 17.0 | 11.9 |
| move_40 | 60_180 | 933 | ci_ok | 0.0258 | 0.0041 | 0.0629 | 6.3000 | 49.5 | 8.0 | 13.4 |
| move_40 | over_180 | 4196 | ci_ok | 0.0224 | 0.0043 | 0.0592 | 5.3000 | 43.7 | 10.0 | 12.3 |
| move_40 | under_60 | 198 | descriptive_only | 0.0278 | 0.0045 | 0.0713 | 7.6000 | 53.9 | 9.5 | 16.2 |

## 7. Late-checkpoint clock summary

Late group (move_30+move_40), by finer clock bucket and termination view (ES loss; game-level bootstrap 95% CI on mean ES for ci_ok cells):

| View | clock_fine | n | status | mean ES | 95% CI | median ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| all | <10 | 90 | descriptive_only | 0.0277 | — | 0.0042 | 8.9 |
| all | 10_30 | 216 | descriptive_only | 0.0333 | — | 0.0070 | 7.9 |
| all | 30_60 | 467 | ci_ok | 0.0306 | [0.0253, 0.0361] | 0.0059 | 8.6 |
| all | 60_180 | 2382 | ci_ok | 0.0306 | [0.0280, 0.0335] | 0.0070 | 7.6 |
| all | over_180 | 14883 | ci_ok | 0.0281 | [0.0271, 0.0291] | 0.0069 | 6.9 |
| board_decided | <10 | 9 | hidden_sparse | — | — | — | — |
| board_decided | 10_30 | 69 | descriptive_only | 0.0265 | — | 0.0054 | 7.2 |
| board_decided | 30_60 | 204 | descriptive_only | 0.0252 | — | 0.0048 | 5.4 |
| board_decided | 60_180 | 1590 | ci_ok | 0.0290 | [0.0259, 0.0321] | 0.0059 | 7.1 |
| board_decided | over_180 | 13127 | ci_ok | 0.0278 | [0.0266, 0.0289] | 0.0065 | 6.8 |
| time_forfeit | <10 | 81 | descriptive_only | 0.0268 | — | 0.0043 | 7.4 |
| time_forfeit | 10_30 | 147 | descriptive_only | 0.0365 | — | 0.0082 | 8.2 |
| time_forfeit | 30_60 | 263 | descriptive_only | 0.0348 | — | 0.0070 | 11.0 |
| time_forfeit | 60_180 | 792 | ci_ok | 0.0337 | [0.0294, 0.0389] | 0.0095 | 8.7 |
| time_forfeit | over_180 | 1756 | ci_ok | 0.0308 | [0.0278, 0.0341] | 0.0097 | 7.7 |

## 8. Board-decided vs time-forfeit summary

Late group, board-decided vs time-forfeit, by coarse clock bucket:

| tf_view | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| board_decided | 60_180 | 1590 | ci_ok | 0.0290 | 0.0059 | 0.0724 | 7.1000 |
| board_decided | over_180 | 13127 | ci_ok | 0.0278 | 0.0065 | 0.0729 | 6.8000 |
| board_decided | under_60 | 282 | descriptive_only | 0.0258 | 0.0048 | 0.0674 | 6.4000 |
| time_forfeit | 60_180 | 792 | ci_ok | 0.0337 | 0.0095 | 0.0839 | 8.7000 |
| time_forfeit | over_180 | 1756 | ci_ok | 0.0308 | 0.0097 | 0.0790 | 7.7000 |
| time_forfeit | under_60 | 491 | ci_ok | 0.0340 | 0.0071 | 0.0941 | 9.6000 |

## 9. Rating × clock summary

Late group, rating bin × coarse clock bucket (ES loss; sparse cells labeled):

| rating_bin | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| 1000_1199 | 60_180 | 209 | descriptive_only | 0.0329 | 0.0098 | 0.0698 | 6.7000 |
| 1000_1199 | over_180 | 1251 | ci_ok | 0.0308 | 0.0069 | 0.0834 | 8.2000 |
| 1000_1199 | under_60 | 56 | descriptive_only | 0.0251 | 0.0055 | 0.0536 | 3.6000 |
| 1200_1399 | 60_180 | 286 | descriptive_only | 0.0332 | 0.0087 | 0.0770 | 8.0000 |
| 1200_1399 | over_180 | 1956 | ci_ok | 0.0293 | 0.0075 | 0.0724 | 6.9000 |
| 1200_1399 | under_60 | 81 | descriptive_only | 0.0339 | 0.0062 | 0.0725 | 7.4000 |
| 1400_1599 | 60_180 | 413 | ci_ok | 0.0321 | 0.0073 | 0.0884 | 8.7000 |
| 1400_1599 | over_180 | 3232 | ci_ok | 0.0288 | 0.0069 | 0.0737 | 7.0000 |
| 1400_1599 | under_60 | 133 | descriptive_only | 0.0337 | 0.0059 | 0.0988 | 10.5000 |
| 1600_1799 | 60_180 | 465 | ci_ok | 0.0322 | 0.0050 | 0.0792 | 8.4000 |
| 1600_1799 | over_180 | 3345 | ci_ok | 0.0284 | 0.0076 | 0.0745 | 6.8000 |
| 1600_1799 | under_60 | 158 | descriptive_only | 0.0280 | 0.0060 | 0.0572 | 7.0000 |
| 1800_1999 | 60_180 | 498 | ci_ok | 0.0278 | 0.0070 | 0.0751 | 7.6000 |
| 1800_1999 | over_180 | 2906 | ci_ok | 0.0271 | 0.0064 | 0.0760 | 7.2000 |
| 1800_1999 | under_60 | 170 | descriptive_only | 0.0290 | 0.0043 | 0.0794 | 7.6000 |
| 2000_2199 | 60_180 | 273 | descriptive_only | 0.0236 | 0.0017 | 0.0618 | 4.8000 |
| 2000_2199 | over_180 | 1226 | ci_ok | 0.0228 | 0.0054 | 0.0647 | 5.2000 |
| 2000_2199 | under_60 | 99 | descriptive_only | 0.0304 | 0.0070 | 0.1040 | 11.1000 |
| 2200_2399 | 60_180 | 97 | descriptive_only | 0.0176 | 0.0038 | 0.0456 | 3.1000 |
| 2200_2399 | over_180 | 250 | descriptive_only | 0.0227 | 0.0048 | 0.0642 | 6.0000 |
| 2200_2399 | under_60 | 29 | hidden_sparse | — | — | — | — |
| 2400_2599 | 60_180 | 13 | hidden_sparse | — | — | — | — |
| 2400_2599 | over_180 | 20 | hidden_sparse | — | — | — | — |
| 2400_2599 | under_60 | 6 | hidden_sparse | — | — | — | — |
| 400_599 | 60_180 | 6 | hidden_sparse | — | — | — | — |
| 400_599 | over_180 | 41 | hidden_sparse | — | — | — | — |
| 400_599 | under_60 | 0 | hidden_sparse | — | — | — | — |
| 600_799 | 60_180 | 21 | hidden_sparse | — | — | — | — |
| 600_799 | over_180 | 135 | descriptive_only | 0.0334 | 0.0103 | 0.0722 | 6.7000 |
| 600_799 | under_60 | 9 | hidden_sparse | — | — | — | — |
| 800_999 | 60_180 | 101 | descriptive_only | 0.0464 | 0.0062 | 0.1221 | 11.9000 |
| 800_999 | over_180 | 521 | ci_ok | 0.0316 | 0.0063 | 0.0737 | 8.1000 |
| 800_999 | under_60 | 32 | hidden_sparse | — | — | — | — |

## 10. Eval-band × clock summary

Late group, eval band × coarse clock bucket (ES loss):

| eval_band | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| clear | 60_180 | 1213 | ci_ok | 0.0252 | 0.0076 | 0.0578 | 4.4000 |
| clear | over_180 | 7429 | ci_ok | 0.0243 | 0.0073 | 0.0559 | 4.5000 |
| clear | under_60 | 388 | ci_ok | 0.0235 | 0.0060 | 0.0585 | 4.1000 |
| decided | 60_180 | 233 | descriptive_only | 0.0142 | 0.0037 | 0.0335 | 1.7000 |
| decided | over_180 | 1456 | ci_ok | 0.0148 | 0.0031 | 0.0299 | 2.2000 |
| decided | under_60 | 101 | descriptive_only | 0.0104 | 0.0026 | 0.0335 | 2.0000 |
| near_equal | 60_180 | 412 | ci_ok | 0.0372 | 0.0036 | 0.1372 | 12.4000 |
| near_equal | over_180 | 2820 | ci_ok | 0.0322 | 0.0029 | 0.1012 | 10.1000 |
| near_equal | under_60 | 151 | descriptive_only | 0.0391 | 0.0036 | 0.1246 | 11.9000 |
| slight | 60_180 | 524 | ci_ok | 0.0452 | 0.0100 | 0.1283 | 14.1000 |
| slight | over_180 | 3178 | ci_ok | 0.0396 | 0.0139 | 0.1125 | 12.1000 |
| slight | under_60 | 133 | descriptive_only | 0.0593 | 0.0217 | 0.1641 | 21.8000 |

## 11. Phase/checkpoint summary

By checkpoint (all clocks pooled within checkpoint):

| selected_position_type | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|
| move_10 | 23221 | ci_ok | 0.0358 | 0.0119 | 0.0997 | 10.0000 | 55.8 | 19.0 | 16.5 |
| move_20 | 18366 | ci_ok | 0.0373 | 0.0122 | 0.1021 | 10.3000 | 63.7 | 23.0 | 19.4 |
| move_30 | 11486 | ci_ok | 0.0308 | 0.0082 | 0.0796 | 7.7000 | 56.4 | 17.0 | 16.4 |
| move_40 | 6552 | ci_ok | 0.0247 | 0.0048 | 0.0644 | 6.0000 | 47.1 | 11.0 | 13.4 |

## 12. Clipped-cp robustness summary

Does clipped cp loss mirror ES loss by checkpoint? (both shown above; the cp and ES orderings agree by construction — both are non-negative losses of the same move — and are reported together so cp can be read against the literature's centipawn-loss convention).

## 13. Sparse-cell diagnostics

23 of the late rating×clock cells are below the 300-row CI threshold (descriptive_only or hidden_sparse) — chiefly low-clock and rating-tail cells. These are labeled in the tables and must not be emphasized.

## 14. Limitations and caveats

- Descriptive measurement only — no causal claims; this is an association between constraint state and next-move loss, not evidence that time pressure causes worse moves or degrades reasoning.
- Ordered-bucket patterns are reported as patterns, not as a degradation curve.
- Stockfish depth-12 eval is objective position context, not absolute ground truth.
- Clock summaries are conditioned on checkpoint/phase; marginal all-checkpoint clock curves would conflate time remaining with game phase and are not shown.
- Numbered checkpoints are even-ply, so the mover is always White: this Atlas describes White-to-move decision quality.
- Board-decided low-clock cells are a selected survivor population (11.2B).
- Loss distributions are right-skewed; medians and upper quantiles are reported alongside means. Mate-band rows are excluded from loss summaries.
- DRAW remains sparse and is not solved. Sharpness is not implemented yet and is not invoked as an explanation.

## 15. Recommendation for combined interpretation

Read this month against the other in the combined report; a pattern is only noted if it replicates across 2024-09 and 2024-10. No controlled or causal conclusion is drawn here.
