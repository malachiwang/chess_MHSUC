# Next-Move Loss Pilot — 2024_09_250k_v1

**Ticket:** 15.0B — Checkpoint-Level Next-Move Loss Extraction (pilot)
**Dataset:** `lichess_ten_zero_2024_09_250k_v1`

## 1. Executive summary

Pilot of 1000 checkpoint rows (`--limit 1000`); 982 successfully evaluated. This is the measurement layer for Contrast C4 (next-move quality), which tests board-play quality directly rather than inferring it from final outcomes. Pilot metric: clipped centipawn loss, mover's perspective. Expected-score loss (the intended C4 headline) is deferred to 15.0C/15.1A with a train-fit cp→expected-score transform. Predictive/descriptive only — not causal, no degradation-curve language; Stockfish eval is objective context, not absolute ground truth.

## 2. Input artifacts

- sf_eval (pre-move best-line value, ply, fen_hash): `data/processed/sf_eval_broad_2024_09_250k_v1.parquet`
- features (clocks, ratings, termination): `data/processed/feature_positions_broad_2024_09_250k_v1.parquet`
- raw PGN cache (post-move reconstruction): `data/raw/lichess/lichess_*_first*.pgn` (gitignored)

## 3. Pilot configuration

- `--limit`: 1000
- Stockfish depth: 12 (post-move position only; no best-move search, no MultiPV)
- Deterministic: first N checkpoint rows in artifact (stream) order; seedless.

## 4. Reconstruction/evaluation success

| Outcome | Count |
|---|---|
| Attempted | 1000 |
| OK (evaluated) | 982 |
| No next move (game ended at checkpoint) | 18 |
| FEN reconstruction error | 0 |
| Illegal move | 0 |
| Game not found in PGN | 0 |
| Engine error | 0 |
| FEN-hash mismatches (checkpoint vs stored) | 0 |

## 5. Output schema

Columns: `dataset_id`, `version_tag`, `game_id`, `selected_position_type`, `checkpoint_ply`, `move_number`, `mover_color`, `actual_move_uci`, `pre_fen`, `post_fen`, `pre_sf_eval_cp`, `pre_sf_eval_mate`, `post_sf_eval_cp`, `post_sf_eval_mate`, `mover_pre_cp`, `mover_post_cp`, `cp_loss`, `clipped_cp_loss`, `is_mate_band`, `white_rating`, `black_rating`, `mover_rating`, `mover_clock_s`, `time_bucket`, `termination`, `is_time_forfeit`, `split_set`, `sf_depth`, `status`, `fen_hash_matches`

## 6. Loss metric definitions

- `mover_pre_cp` = checkpoint `sf_eval_cp` oriented to the mover (the stored value is already the engine best-line value at depth 12).
- `mover_post_cp` = new eval of the post-move position, oriented to the same mover.
- `cp_loss = max(0, mover_pre_cp − mover_post_cp)`; `clipped_cp_loss = min(cp_loss, 1000)`.
- Expected-score loss is DEFERRED (15.0C/15.1A, train-fit transform).

## 7. Basic pilot summaries

Clipped cp loss (OK, non-mate-band rows, n=943):

- mean 58.1 | median 24.0 | p75 76.0 | p90 161.0
- zero loss: 29.4% | >100cp: 19.1% | >200cp: 6.7%

Counts by checkpoint: move_10=376, move_20=278, move_30=178, move_40=111

Counts by time-forfeit flag: False=842, True=101

## 8. Mate-band handling

39 OK rows are mate-band (pre or post eval is a mate score or hits ±10000). They are flagged `is_mate_band=True` and EXCLUDED from the cp-loss summaries above; never silently mixed into cp statistics.

## 9. Runtime and compute estimate

- Pilot runtime: 19.6 s for 1000 attempted rows.
- Extrapolated full-month (~64k checkpoint rows): ~21 min (post-move evals only; consistent with the 15.0A ~30 min/month estimate). Two months ~1 h.

## 10. Known limitations

- Expected-score loss deferred (cp loss only in this pilot).
- Depth-parity: pre-move (mover to move) vs post-move (opponent to move) both evaluated at depth 12; the odd/even search-parity asymmetry is acknowledged and should be sensitivity-checked at depth 13 in a later pass.
- Board-decided low-clock cells are a survivor population (11.2B caveat).
- Loss distributions are right-skewed; medians/percentiles reported alongside means.
- Stockfish depth-12 eval is objective context, not absolute ground truth; this is association between constraint state and next-move loss, not causal.

## 11. Recommendation for full extraction

Pilot succeeded: reconstruction + post-move evaluation + loss computation work end-to-end and FEN hashes match the stored checkpoint hashes. Recommend 15.0C: run the full both-months post-move pass (gated on explicit approval), then add the train-fit cp→expected-score transform and the descriptive Constraint Atlas curves.

Output artifact: `data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet` (gitignored under `data/`; not staged).
