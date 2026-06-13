# Next-Move Loss Extraction — 2024-09 250k

**Ticket:** 15.0C — Full Next-Move Loss Extraction + Expected-Score Transform
**Dataset:** `lichess_ten_zero_2024_09_250k_v1`

## 1. Executive summary

Full checkpoint-level next-move loss extraction for 2024-09: **64,371 of 65,368 rows
evaluated** (997 no-next-move skips; **0 reconstruction failures, 0 engine failures, 0
FEN-hash mismatches**). Both clipped centipawn loss and expected-score loss (train-fit
transform) are now available — this is the measurement layer for Contrast C4. Median
clipped cp loss 19, mean 58.3; expected-score loss median 0.0102, mean 0.0345.
Descriptive measurement only — not causal, no degradation-curve language; Stockfish
depth-12 eval is objective position context, not absolute ground truth.

## 2. Input artifacts

- `data/processed/sf_eval_broad_2024_09_250k_v1.parquet` (pre-move best-line value, ply, fen_hash, split)
- `data/processed/feature_positions_broad_2024_09_250k_v1.parquet` (clocks, ratings, termination)
- `data/raw/lichess/lichess_2024_09_first250k.pgn` (post-move reconstruction; gitignored)
- `data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json` (pooled-train cp→ES transform)

## 3. Full-run configuration

- `--allow-full-run`; Stockfish 18, depth 12; post-move actual position only (no
  best-move search, no MultiPV — the checkpoint `sf_eval_cp` is already the best-line
  value).
- Expected-score transform: pooled train rows from both months (scale=348.4, n=89,764).

## 4. Reconstruction/evaluation success

| Outcome | Count |
|---|---|
| Attempted | 65,368 |
| OK (evaluated) | 64,371 |
| No next move (game ended at checkpoint) | 997 |
| FEN reconstruction error | 0 |
| Game not found in PGN | 0 |
| Engine error | 0 |
| FEN-hash mismatches | 0 |

## 5. Output schema

`data/processed/next_move_loss_2024_09_250k_v1.parquet` (64,371 OK + skip rows, 33 cols):
`dataset_id, version_tag, game_id, selected_position_type, checkpoint_ply, move_number,
mover_color, actual_move_uci, pre_fen, post_fen, pre_sf_eval_cp, pre_sf_eval_mate,
post_sf_eval_cp, post_sf_eval_mate, mover_pre_cp, mover_post_cp, cp_loss,
clipped_cp_loss, es_pre, es_post, expected_score_loss, is_mate_band, white_rating,
black_rating, mover_rating, mover_clock_s, time_bucket, termination, is_time_forfeit,
split_set, sf_depth, status, fen_hash_matches`. No usernames.

## 6. Loss metric definitions

- `mover_pre_cp` = checkpoint `sf_eval_cp` oriented to the mover (= engine best-line value at depth 12).
- `mover_post_cp` = new depth-12 eval of the post-move position, oriented to the same mover.
- `cp_loss = max(0, mover_pre_cp − mover_post_cp)`; `clipped_cp_loss = min(cp_loss, 1000)`.
- `expected_score_loss = max(0, ES(mover_pre_cp) − ES(mover_post_cp))`, ES the train-fit logistic.

## 7. Expected-score transform

Logistic `ES(cp) = 1/(1 + exp(−cp_clipped/scale))`, cp clipped to ±1000, **scale=348.4**,
fit by bounded MSE to White expected score (win=1, draw=0.5, loss=0) on **89,764 pooled
TRAIN rows from both months** (2024-09: 45,818; 2024-10: 43,946), MSE 0.183. Train-only
(split discipline); the same transform applies to pre- and post-move cp. cp lineage
preserved separately (cp_loss/clipped_cp_loss retained).

## 8. Basic loss summaries

OK, non-mate-band rows (n=61,956):

- Clipped cp loss: mean 58.3, median 19, p75 69, p90 159, zero-loss 33.3%, >100cp 17.3%, >200cp 7.3%.
- Expected-score loss: mean 0.0345, median 0.0102, p90 0.0949, >0.10 9.3%.

## 9. Counts by checkpoint (OK)

move_10 24,384 · move_20 19,639 · move_30 12,950 · move_40 7,398.

## 10. Counts by termination channel (OK)

Normal 55,940 · Time forfeit 8,430 · Rules infraction 1.

## 11. Counts by clock bucket (OK)

over_180s 60,656 · 60_180s 2,855 · under_60s 860. (At numbered checkpoints clocks are
mostly high — the clock×checkpoint confound from 9.2B; bucket within checkpoint for any
analysis.) **Descriptive note:** board-decided vs time-forfeit games have nearly
identical checkpoint next-move loss (clipped cp mean 58.4 vs 57.6; ES mean 0.0345 vs
0.0349) — consistent with the 11.2B finding that the outcome residual reflects flagging
mechanics, not worse board moves. Descriptive only.

## 12. Mate-band handling

2,415 OK rows are mate-band (pre or post eval is a mate score or hits ±10000); flagged
`is_mate_band=True` and EXCLUDED from the loss summaries above.

## 13. Depth-parity sensitivity

Post-move re-evaluated at depth 13 on a 400-row sample: mean clipped cp loss 57.8 (d12)
vs 58.0 (d13) — a 0.2cp aggregate shift; per-row mean absolute delta 14cp, median delta
0. The odd/even search-parity asymmetry does not materially affect the aggregate
summaries.

## 14. Runtime and artifact status

Runtime 1,471 s (~24.5 min). Artifact
`data/processed/next_move_loss_2024_09_250k_v1.parquet` — **gitignored**, not staged.

## 15. Known limitations

- Board-decided low-clock cells are a selected survivor population (11.2B caveat).
- Loss distributions are right-skewed → medians/percentiles reported alongside means.
- Depth-parity: pre (mover-to-move) and post (opponent-to-move) both at depth 12;
  parity asymmetry quantified in §13, found benign in aggregate.
- The cp→ES transform is a logistic on clipped cp fit to outcomes; mate-band excluded.
- Stockfish depth-12 eval is objective context, not absolute ground truth; this is
  association between constraint state and next-move loss, not causal.

## 16. Recommendation for Constraint Atlas curves

The artifact is ready for 15.1A descriptive curves (time × loss, rating × time, eval-band
panels, phase panels, board-decided-only, termination-labeled). Controlled modeling
(15.1B) must wait for player-leakage hardening (11.3A/B) or use player-clustered/disjoint
design.
