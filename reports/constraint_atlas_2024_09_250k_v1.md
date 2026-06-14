# Constraint Atlas — 2024_09_250k_v1

**Ticket:** 15.1B — Constraint Atlas Descriptive Curves Implementation

## 1. Executive summary

Descriptive next-move loss readout over 61,956 non-mate-band OK checkpoint moves. Overall mean expected-score (ES) loss 0.0345, median 0.0102 (right-skewed). Board-decided and time-forfeit populations are summarized separately and side-by-side; clock is always conditioned on checkpoint. Descriptive only — see caveats (§14).

## 2. Input artifact and schema

`data/processed/next_move_loss_2024_09_250k_v1.parquet` (OK rows; mate-band flagged and excluded from loss summaries). Derived bins: clock_coarse, clock_fine, rating_bin, eval_band, channel, board_decided, is_late, large-loss indicators.

## 3. Metric definitions

- Primary: `expected_score_loss = max(0, ES(mover_pre_cp) − ES(mover_post_cp))` (mover's perspective; train-fit logistic transform, scale 348.4).
- Secondary: `clipped_cp_loss = min(max(0, mover_pre_cp − mover_post_cp), 1000)`.
- Large-loss probabilities: P(ES>0.05), P(ES>0.10), P(cp>100), P(cp>200).

## 4. Cell-count policy

hidden_sparse (n<50) — not summarized; descriptive_only (50≤n<300) — point estimates, no CI; ci_ok (n≥300) — CI-eligible. Game-level clustered bootstrap CIs are shown only for the headline late-group clock cells (§7).

## 5. Overall loss summary

| Population | n | mean ES | median ES | p75 ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|
| all_games | 61,956 | 0.0345 | 0.0102 | 0.0392 | 0.0949 | 9.3 | 58.3 | 19.0 | 17.3 |
| board_decided | 53,640 | 0.0345 | 0.0102 | 0.0391 | 0.0947 | 9.3 | 58.4 | 19.0 | 17.3 |
| time_forfeit | 8,316 | 0.0349 | 0.0105 | 0.0397 | 0.0957 | 9.4 | 57.6 | 18.0 | 16.8 |

## 6. Checkpoint-conditioned clock summary

All-games, by checkpoint × coarse clock bucket:

| selected_position_type | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|---|
| move_10 | 60_180 | 9 | hidden_sparse | — | — | — | — | — | — | — |
| move_10 | over_180 | 24211 | ci_ok | 0.0362 | 0.0122 | 0.1012 | 10.2000 | 56.3 | 19.0 | 17.1 |
| move_10 | under_60 | 1 | hidden_sparse | — | — | — | — | — | — | — |
| move_20 | 60_180 | 238 | descriptive_only | 0.0358 | 0.0113 | 0.0965 | 8.8000 | 64.0 | 23.5 | 16.8 |
| move_20 | over_180 | 18741 | ci_ok | 0.0370 | 0.0118 | 0.1007 | 10.1000 | 63.5 | 22.0 | 19.1 |
| move_20 | under_60 | 24 | hidden_sparse | — | — | — | — | — | — | — |
| move_30 | 60_180 | 1067 | ci_ok | 0.0339 | 0.0078 | 0.0876 | 8.3000 | 62.1 | 15.0 | 17.1 |
| move_30 | over_180 | 10718 | ci_ok | 0.0315 | 0.0084 | 0.0834 | 8.0000 | 57.9 | 18.0 | 16.4 |
| move_30 | under_60 | 241 | descriptive_only | 0.0426 | 0.0120 | 0.1123 | 12.0000 | 79.3 | 29.0 | 22.0 |
| move_40 | 60_180 | 1294 | ci_ok | 0.0280 | 0.0060 | 0.0700 | 7.0000 | 52.9 | 13.0 | 15.1 |
| move_40 | over_180 | 4904 | ci_ok | 0.0252 | 0.0045 | 0.0641 | 6.1000 | 48.3 | 10.0 | 13.5 |
| move_40 | under_60 | 508 | ci_ok | 0.0283 | 0.0031 | 0.0717 | 7.5000 | 54.2 | 7.0 | 14.4 |

Board-decided only, by checkpoint × coarse clock bucket:

| selected_position_type | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|---|
| move_10 | 60_180 | 2 | hidden_sparse | — | — | — | — | — | — | — |
| move_10 | over_180 | 21439 | ci_ok | 0.0363 | 0.0122 | 0.1015 | 10.2000 | 56.6 | 19.0 | 17.2 |
| move_20 | 60_180 | 135 | descriptive_only | 0.0335 | 0.0082 | 0.0961 | 9.6000 | 61.8 | 17.0 | 16.3 |
| move_20 | over_180 | 16504 | ci_ok | 0.0369 | 0.0117 | 0.1004 | 10.1000 | 63.7 | 22.0 | 19.2 |
| move_20 | under_60 | 7 | hidden_sparse | — | — | — | — | — | — | — |
| move_30 | 60_180 | 647 | ci_ok | 0.0349 | 0.0072 | 0.0958 | 9.3000 | 65.6 | 14.0 | 18.2 |
| move_30 | over_180 | 9403 | ci_ok | 0.0312 | 0.0083 | 0.0834 | 8.0000 | 58.1 | 18.0 | 16.4 |
| move_30 | under_60 | 70 | descriptive_only | 0.0332 | 0.0100 | 0.0793 | 8.6000 | 64.2 | 22.0 | 18.6 |
| move_40 | 60_180 | 898 | ci_ok | 0.0267 | 0.0058 | 0.0664 | 6.6000 | 51.8 | 12.5 | 14.5 |
| move_40 | over_180 | 4372 | ci_ok | 0.0250 | 0.0044 | 0.0618 | 5.8000 | 48.1 | 10.0 | 13.2 |
| move_40 | under_60 | 163 | descriptive_only | 0.0217 | 0.0055 | 0.0518 | 5.5000 | 47.7 | 16.0 | 12.3 |

## 7. Late-checkpoint clock summary

Late group (move_30+move_40), by finer clock bucket and termination view (ES loss; game-level bootstrap 95% CI on mean ES for ci_ok cells):

| View | clock_fine | n | status | mean ES | 95% CI | median ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| all | <10 | 88 | descriptive_only | 0.0418 | — | 0.0096 | 11.4 |
| all | 10_30 | 220 | descriptive_only | 0.0354 | — | 0.0079 | 9.5 |
| all | 30_60 | 441 | ci_ok | 0.0299 | [0.0242, 0.0365] | 0.0051 | 8.2 |
| all | 60_180 | 2361 | ci_ok | 0.0307 | [0.0281, 0.0335] | 0.0068 | 7.6 |
| all | over_180 | 15622 | ci_ok | 0.0295 | [0.0284, 0.0305] | 0.0070 | 7.4 |
| board_decided | <10 | 10 | hidden_sparse | — | — | — | — |
| board_decided | 10_30 | 44 | hidden_sparse | — | — | — | — |
| board_decided | 30_60 | 179 | descriptive_only | 0.0229 | — | 0.0055 | 4.5 |
| board_decided | 60_180 | 1545 | ci_ok | 0.0301 | [0.0270, 0.0335] | 0.0061 | 7.7 |
| board_decided | over_180 | 13775 | ci_ok | 0.0292 | [0.0281, 0.0303] | 0.0069 | 7.3 |
| time_forfeit | <10 | 78 | descriptive_only | 0.0431 | — | 0.0099 | 11.5 |
| time_forfeit | 10_30 | 176 | descriptive_only | 0.0360 | — | 0.0066 | 8.5 |
| time_forfeit | 30_60 | 262 | descriptive_only | 0.0347 | — | 0.0051 | 10.7 |
| time_forfeit | 60_180 | 816 | ci_ok | 0.0316 | [0.0274, 0.0360] | 0.0084 | 7.5 |
| time_forfeit | over_180 | 1847 | ci_ok | 0.0315 | [0.0289, 0.0347] | 0.0079 | 8.1 |

## 8. Board-decided vs time-forfeit summary

Late group, board-decided vs time-forfeit, by coarse clock bucket:

| tf_view | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| board_decided | 60_180 | 1545 | ci_ok | 0.0301 | 0.0061 | 0.0774 | 7.7000 |
| board_decided | over_180 | 13775 | ci_ok | 0.0292 | 0.0069 | 0.0763 | 7.3000 |
| board_decided | under_60 | 233 | descriptive_only | 0.0252 | 0.0074 | 0.0633 | 6.4000 |
| time_forfeit | 60_180 | 816 | ci_ok | 0.0316 | 0.0084 | 0.0807 | 7.5000 |
| time_forfeit | over_180 | 1847 | ci_ok | 0.0315 | 0.0079 | 0.0847 | 8.1000 |
| time_forfeit | under_60 | 516 | ci_ok | 0.0364 | 0.0062 | 0.0999 | 10.1000 |

## 9. Rating × clock summary

Late group, rating bin × coarse clock bucket (ES loss; sparse cells labeled):

| rating_bin | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| 1000_1199 | 60_180 | 213 | descriptive_only | 0.0424 | 0.0131 | 0.1110 | 10.8000 |
| 1000_1199 | over_180 | 1398 | ci_ok | 0.0306 | 0.0068 | 0.0757 | 7.7000 |
| 1000_1199 | under_60 | 68 | descriptive_only | 0.0606 | 0.0130 | 0.1952 | 16.2000 |
| 1200_1399 | 60_180 | 267 | descriptive_only | 0.0321 | 0.0085 | 0.0879 | 9.0000 |
| 1200_1399 | over_180 | 2117 | ci_ok | 0.0330 | 0.0074 | 0.0846 | 8.8000 |
| 1200_1399 | under_60 | 85 | descriptive_only | 0.0484 | 0.0127 | 0.1189 | 14.1000 |
| 1400_1599 | 60_180 | 384 | ci_ok | 0.0282 | 0.0073 | 0.0766 | 6.8000 |
| 1400_1599 | over_180 | 3129 | ci_ok | 0.0284 | 0.0068 | 0.0752 | 7.3000 |
| 1400_1599 | under_60 | 116 | descriptive_only | 0.0305 | 0.0050 | 0.0773 | 7.8000 |
| 1600_1799 | 60_180 | 446 | ci_ok | 0.0304 | 0.0085 | 0.0712 | 7.4000 |
| 1600_1799 | over_180 | 3486 | ci_ok | 0.0306 | 0.0076 | 0.0840 | 7.9000 |
| 1600_1799 | under_60 | 154 | descriptive_only | 0.0276 | 0.0040 | 0.0795 | 7.8000 |
| 1800_1999 | 60_180 | 513 | ci_ok | 0.0266 | 0.0048 | 0.0647 | 6.4000 |
| 1800_1999 | over_180 | 3102 | ci_ok | 0.0272 | 0.0068 | 0.0716 | 6.5000 |
| 1800_1999 | under_60 | 167 | descriptive_only | 0.0269 | 0.0021 | 0.0706 | 8.4000 |
| 2000_2199 | 60_180 | 316 | ci_ok | 0.0280 | 0.0058 | 0.0768 | 7.6000 |
| 2000_2199 | over_180 | 1283 | ci_ok | 0.0268 | 0.0067 | 0.0735 | 6.2000 |
| 2000_2199 | under_60 | 96 | descriptive_only | 0.0324 | 0.0024 | 0.0685 | 7.3000 |
| 2200_2399 | 60_180 | 98 | descriptive_only | 0.0209 | 0.0000 | 0.0674 | 6.1000 |
| 2200_2399 | over_180 | 333 | ci_ok | 0.0242 | 0.0021 | 0.0686 | 5.7000 |
| 2200_2399 | under_60 | 30 | hidden_sparse | — | — | — | — |
| 2400_2599 | 60_180 | 18 | hidden_sparse | — | — | — | — |
| 2400_2599 | over_180 | 58 | descriptive_only | 0.0137 | 0.0000 | 0.0212 | 3.4000 |
| 2400_2599 | under_60 | 2 | hidden_sparse | — | — | — | — |
| 2600_2799 | 60_180 | 1 | hidden_sparse | — | — | — | — |
| 2600_2799 | over_180 | 10 | hidden_sparse | — | — | — | — |
| 2600_2799 | under_60 | 4 | hidden_sparse | — | — | — | — |
| 400_599 | 60_180 | 1 | hidden_sparse | — | — | — | — |
| 400_599 | over_180 | 17 | hidden_sparse | — | — | — | — |
| 600_799 | 60_180 | 22 | hidden_sparse | — | — | — | — |
| 600_799 | over_180 | 167 | descriptive_only | 0.0460 | 0.0098 | 0.0935 | 9.0000 |
| 600_799 | under_60 | 6 | hidden_sparse | — | — | — | — |
| 800_999 | 60_180 | 82 | descriptive_only | 0.0523 | 0.0083 | 0.1000 | 11.0000 |
| 800_999 | over_180 | 522 | ci_ok | 0.0322 | 0.0077 | 0.0761 | 7.7000 |
| 800_999 | under_60 | 21 | hidden_sparse | — | — | — | — |

## 10. Eval-band × clock summary

Late group, eval band × coarse clock bucket (ES loss):

| eval_band | clock_coarse | n | status | mean ES | median ES | p90 ES | %ES>0.10 |
|---|---|---|---|---|---|---|---|
| clear | 60_180 | 1225 | ci_ok | 0.0272 | 0.0077 | 0.0620 | 5.1000 |
| clear | over_180 | 7932 | ci_ok | 0.0254 | 0.0078 | 0.0562 | 4.6000 |
| clear | under_60 | 390 | ci_ok | 0.0269 | 0.0069 | 0.0594 | 5.6000 |
| decided | 60_180 | 221 | descriptive_only | 0.0214 | 0.0033 | 0.0402 | 5.0000 |
| decided | over_180 | 1601 | ci_ok | 0.0168 | 0.0035 | 0.0335 | 2.3000 |
| decided | under_60 | 81 | descriptive_only | 0.0102 | 0.0027 | 0.0326 | 0.0000 |
| near_equal | 60_180 | 430 | ci_ok | 0.0331 | 0.0021 | 0.1005 | 10.5000 |
| near_equal | over_180 | 2790 | ci_ok | 0.0345 | 0.0022 | 0.1153 | 12.2000 |
| near_equal | under_60 | 123 | descriptive_only | 0.0393 | 0.0000 | 0.1339 | 11.4000 |
| slight | 60_180 | 485 | ci_ok | 0.0415 | 0.0107 | 0.1188 | 12.8000 |
| slight | over_180 | 3299 | ci_ok | 0.0414 | 0.0129 | 0.1181 | 12.5000 |
| slight | under_60 | 155 | descriptive_only | 0.0548 | 0.0273 | 0.1353 | 20.0000 |

## 11. Phase/checkpoint summary

By checkpoint (all clocks pooled within checkpoint):

| selected_position_type | n | status | mean ES | median ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |
|---|---|---|---|---|---|---|---|---|---|
| move_10 | 24221 | ci_ok | 0.0362 | 0.0122 | 0.1012 | 10.2000 | 56.4 | 19.0 | 17.1 |
| move_20 | 19003 | ci_ok | 0.0370 | 0.0118 | 0.1006 | 10.1000 | 63.6 | 22.0 | 19.1 |
| move_30 | 12026 | ci_ok | 0.0319 | 0.0084 | 0.0841 | 8.1000 | 58.7 | 18.0 | 16.6 |
| move_40 | 6706 | ci_ok | 0.0260 | 0.0049 | 0.0654 | 6.4000 | 49.6 | 11.0 | 13.9 |

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
