# Next-Move Loss Extraction — 2024-10 250k

**Ticket:** 15.0C — Full Next-Move Loss Extraction + Expected-Score Transform
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`

## 1. Executive summary

Full checkpoint-level next-move loss extraction for 2024-10 (independent month):
**61,868 of 62,839 rows evaluated** (971 no-next-move skips; **0 reconstruction
failures, 0 engine failures, 0 FEN-hash mismatches**). Clipped cp loss and expected-score
loss (same pooled-train transform) available. Median clipped cp loss 19, mean 57.4;
expected-score loss median 0.0101, mean 0.0341 — closely matching 2024-09. Descriptive
measurement only — not causal, no degradation-curve language; Stockfish depth-12 eval is
objective position context, not absolute ground truth.

## 2. Input artifacts

- `data/processed/sf_eval_broad_2024_10_250k_v1.parquet`
- `data/processed/feature_positions_broad_2024_10_250k_v1.parquet`
- `data/raw/lichess/lichess_2024_10_first250k.pgn` (gitignored)
- `data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json` (pooled-train transform)

## 3. Full-run configuration

`--allow-full-run`; Stockfish 18, depth 12; post-move actual position only (no best-move
search, no MultiPV). Expected-score transform: pooled both-months train (scale=348.4).

## 4. Reconstruction/evaluation success

| Outcome | Count |
|---|---|
| Attempted | 62,839 |
| OK (evaluated) | 61,868 |
| No next move | 971 |
| FEN reconstruction error | 0 |
| Game not found in PGN | 0 |
| Engine error | 0 |
| FEN-hash mismatches | 0 |

## 5. Output schema

`data/processed/next_move_loss_2024_10_250k_v1.parquet` (33 cols; identical schema to
2024-09 — see that report §5). No usernames.

## 6. Loss metric definitions

Identical to 2024-09 (§6): mover-perspective `cp_loss = max(0, mover_pre_cp −
mover_post_cp)`, clipped at ±1000; `expected_score_loss = max(0, ES(mover_pre_cp) −
ES(mover_post_cp))`.

## 7. Expected-score transform

Same pooled-train logistic transform as 2024-09 (scale=348.4, n=89,764, MSE 0.183) — a
single transform across both months for cross-month comparability (both are 10+0,
Stockfish 18, depth 12). Train-only; cp lineage preserved.

## 8. Basic loss summaries

OK, non-mate-band rows (n=59,625):

- Clipped cp loss: mean 57.4, median 19, p75 68, p90 157, zero-loss 33.0%, >100cp 17.0%, >200cp 7.0%.
- Expected-score loss: mean 0.0341, median 0.0101, p90 0.0933, >0.10 9.2%.

## 9. Counts by checkpoint (OK)

move_10 23,364 · move_20 18,927 · move_30 12,365 · move_40 7,212.

## 10. Counts by termination channel (OK)

Normal 53,699 · Time forfeit 8,168 · Rules infraction 1.

## 11. Counts by clock bucket (OK)

over_180s 58,097 · 60_180s 2,879 · under_60s 892. **Descriptive note:** board-decided vs
time-forfeit checkpoint next-move loss is again near-identical (clipped cp mean 57.4 vs
57.4; ES mean 0.0340 vs 0.0349) — same pattern as 2024-09.

## 12. Mate-band handling

2,243 OK rows are mate-band; flagged and EXCLUDED from loss summaries.

## 13. Depth-parity sensitivity

Covered by the 2024-09 depth-13 sample check (mean shift 0.2cp; benign in aggregate);
the same depth-12 convention is used for 2024-10. A per-month re-check can be added later
if needed.

## 14. Runtime and artifact status

Runtime 1,419 s (~23.7 min). Artifact
`data/processed/next_move_loss_2024_10_250k_v1.parquet` — **gitignored**, not staged.

## 15. Known limitations

Same as 2024-09 (§15): survivorship in board-decided low-clock cells; right-skewed loss;
depth-parity benign in aggregate; transform is logistic-on-clipped-cp with mate-band
excluded; Stockfish eval is objective context, not absolute ground truth; descriptive,
not causal.

## 16. Recommendation for Constraint Atlas curves

Ready for 15.1A descriptive curves. The close 2024-09/2024-10 agreement (median 19 both;
ES median ~0.010 both) supports cross-month replication of any Atlas curve. Controlled
modeling (15.1B) waits for 11.3A/B player-leakage hardening.
