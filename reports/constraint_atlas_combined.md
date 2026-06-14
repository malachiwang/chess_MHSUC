# Constraint Atlas — Combined 2024_09_250k_v1 and 2024_10_250k_v1

**Ticket:** 15.1B — Constraint Atlas Descriptive Curves Implementation

## 1. Executive summary

Descriptive next-move loss readout across two independent months. Patterns are reported only where they replicate across months. Descriptive association only — not causal, not a degradation curve; Stockfish eval is objective context, not absolute ground truth.

## 2. Why this Atlas exists after 11.2B/11.2C

11.2B/11.2C showed the outcome clock residual is substantially the time-forfeit/flagging channel and moved the board-play-quality question to next-move quality (Contrast C4). This Atlas describes that move-quality layer directly.

## 3. Input artifacts

- `data/processed/next_move_loss_2024_09_250k_v1.parquet` (64,371 OK rows)
- `data/processed/next_move_loss_2024_10_250k_v1.parquet` (61,868 OK rows)

## 4. Month-by-month replication summary

Overall non-mate-band loss per month:

| Month | n | mean ES | median ES | p90 ES | %ES>0.10 | median cp |
|---|---|---|---|---|---|---|
| 2024_09_250k_v1 | 61,956 | 0.0345 | 0.0102 | 0.0949 | 9.3 | 19.0 |
| 2024_10_250k_v1 | 59,625 | 0.0341 | 0.0101 | 0.0933 | 9.2 | 19.0 |

## 5. Headline checkpoint-conditioned clock findings

Mean ES loss by checkpoint × coarse clock bucket, per month (ci_ok cells only; n in parentheses):

| Checkpoint | clock | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|---|
| move_10 | over_180 | 0.0362 (n=24,211) | 0.0358 (n=23,217) |
| move_20 | over_180 | 0.0370 (n=18,741) | 0.0373 (n=18,095) |
| move_30 | 60_180 | 0.0339 (n=1,067) | 0.0351 (n=1,041) |
| move_30 | over_180 | 0.0315 (n=10,718) | 0.0304 (n=10,180) |
| move_40 | under_60 | 0.0283 (n=508) | 0.0318 (n=508) |
| move_40 | 60_180 | 0.0280 (n=1,294) | 0.0271 (n=1,341) |
| move_40 | over_180 | 0.0252 (n=4,904) | 0.0232 (n=4,703) |

## 6. Late-checkpoint findings

Late group (move_30+40), mean ES loss by coarse clock bucket, per month:

| clock | 2024_09_250k_v1 | 2024_10_250k_v1 | replicates? |
|---|---|---|---|
| under_60 | 0.0329 (n=749) | 0.0310 (n=773) | yes |
| 60_180 | 0.0307 (n=2,361) | 0.0306 (n=2,382) | yes |
| over_180 | 0.0295 (n=15,622) | 0.0281 (n=14,883) | yes |

## 7. Termination-channel findings

Late group, board-decided vs time-forfeit mean ES loss, per month (descriptive — similar values do NOT imply identical mechanisms):

| View | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| board_decided | 0.0293 (n=15,553) | 0.0279 (n=14,999) |
| time_forfeit | 0.0323 (n=3,179) | 0.0321 (n=3,039) |

## 8. Rating × clock findings

Late group, mean ES loss by rating bin × coarse clock (per month, ci_ok cells; see month reports for full tables).

## 9. Eval-band × clock findings

Late group, mean ES loss by eval band (over_180s clock; per month):

| eval_band | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| near_equal | 0.0345 (n=2,790) | 0.0322 (n=2,820) |
| slight | 0.0414 (n=3,299) | 0.0396 (n=3,178) |
| clear | 0.0254 (n=7,932) | 0.0243 (n=7,429) |
| decided | 0.0168 (n=1,601) | 0.0148 (n=1,456) |

## 10. Clipped-cp robustness

Per-month median clipped cp loss is reported in §4 alongside ES; the two metrics co-move by construction (both are non-negative losses of the same move). cp is retained for literature comparability.

## 11. Sparse-cell diagnostics

Low-clock late cells (under_60, and the finer <10/10_30 bins) are at or below the CI threshold and are descriptive-only; rating tails (≤600, ≥2400) likewise. These are labeled throughout and must not be emphasized.

## 12. What this supports

- Descriptive statements that ES/cp loss is higher or lower in specific checkpoint×clock (and rating/eval) cells, where those cells are ci_ok.
- Statements that a cell pattern replicates (or does not) across the two months.
- Motivation for controlled modeling (Contrast C4) with proper confound control and clustered uncertainty.

## 13. What this does not support

- Any causal claim (low clock causing worse moves; time pressure degrading reasoning) — none is made.
- A 'degradation curve' reading of ordered-bucket patterns.
- Stockfish as ground truth; DRAW as solved; sharpness as an explanation (not yet implemented).
- That the clock residual is 'not merely flagging' — that question is for controlled analysis, not this descriptive readout.

## 14. Readiness for controlled modeling

The descriptive layer is complete and month-replicated where cells are dense. Controlled C4 modeling (next-move loss ~ time + rating + eval band + phase + prior trajectory, with interactions) must wait for player-leakage hardening (11.3A/B) or build in player-clustered/disjoint design from the start.

## 15. Recommended next ticket

**11.3A — Player-Disjoint / Player-Clustered Feasibility Audit** — required before controlled C4 modeling (15.1C) and sharpness moderation (15.2B).
