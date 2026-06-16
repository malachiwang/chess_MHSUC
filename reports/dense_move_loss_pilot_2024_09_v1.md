# Dense Move Loss Pilot — 2024-09

**Ticket:** 15.3B — Dense Move-by-Move Loss Extraction Pilot (PILOT ONLY)
**Engine:** Stockfish 18 @ depth 12

## 1. Executive summary

Dense per-ply next-move loss pilot on the first 1,500 accepted 600+0 games of 2024-09 (cap 1,500). Both White and Black moves with move number >= 5 are measured — extending the four White-only numbered checkpoints to a dense curve. **This is a pilot only; no full dense extraction has been run.** One Stockfish eval per pre-move position (Option A); the post-move eval is the next position's eval (reused). Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is objective position context, not absolute ground truth.

## 2. Pilot scope

- Month: 2024_09
- Accepted games scanned to fill cap: 15,054
- Accepted games used: 1,500 (cap 1,500)
- Universe: non-terminal plies, move_number >= 5, both colors
- Eval strategy: Option A (one eval per pre-move position; post-move reused)

## 3. Runtime and throughput

- Wall-clock runtime: 2422.5 s
- Engine seconds: 2108.5 s
- Engine evals: 88,012 | cache reuse hits: 85,491 | terminal positions: 451
- Throughput: 41.7 evals/s

## 4. Replay validation

- Rows written: 86,977
- Unique games: 1,486
- Duplicate (game_id, ply) keys: 0
- Games with a replay failure (partial rows kept): 0

## 5. Clock / think-time validation

- Missing-clock rows: 0
- Clock-anomaly rows (no coarse bucket): 0
- Think-time-anomaly rows (no bucket): 7
- clock_before_s default for a side's first move: 600 s (10+0).

## 6. Evaluation validation

- OK rows: 86,977
- Mate-band rows (flagged, excluded from headline): 4,874
- Eval-error rows: 0

## 7. Row schema validation

- No raw-username columns: True
- Columns: 53 (typed schema + mover/opponent player hashes)

## 8. Loss metric summary

Expected-score loss (OK, non-mate-band, n=82,103): mean 0.0347 | median 0.0115 | p90 0.0939 | zero share 0.2563
Clipped cp loss (n=82,103): mean 59.1 | median 21.0 | p90 160.0 | zero share 0.2563

## 9. Large-loss rates

- ES loss >= 0.05: 0.2029 | >= 0.10: 0.0913
- clipped cp >= 100: 0.1782 | >= 200: 0.0718

## 10. Coverage by color / phase / clock / rating

- By mover color: {'black': 43121, 'white': 43856}
- By phase: {'endgame': 24559, 'middlegame': 44901, 'opening': 17517}
- By clock bucket: {'60_180': 5395, 'over_180': 79033, 'under_60': 2549}
- By eval band: {'clear': 27996, 'decided': 5184, 'mate_band': 4874, 'near_equal': 26949, 'slight': 21974}
- By rating bucket: {'1000_1199': 9285, '1200_1399': 13490, '1400_1599': 17053, '1600_1799': 17350, '1800_1999': 15599, '2000_2199': 6208, '2200_2399': 1691, '2400_2599': 459, '2600_2799': 142, '400_599': 20, '600_799': 1236, '800_999': 4444}

## 11. Player-hash join coverage

- mover_player_hash match fraction: 1.0 (86,977/86,977)

## 12. Full-run runtime extrapolation

- 15.3A both-months dense universe estimate: ~3,340,000 positions.
- At pilot throughput (41.7 evals/s, depth 12): ~22.2 h both months (~11.1 h/month).
- Depth-10 timing subtest (1000 positions): 202.8 evals/s -> ~4.6 h both months.

## 13. Known limitations

- Pilot only; one month, capped game count; not the full dense atlas.
- Depth-parity: pre-move (mover to move) and post-move (opponent to move) are both evaluated at the same fixed depth; the half-ply search-parity asymmetry is acknowledged (15.0C found it benign) and should be re-checked.
- Mate-band rows are flagged and excluded from headline loss summaries.
- Loss distributions are right-skewed; medians/percentiles reported with means.
- No pre-move trajectory / prior-quality control here (stated limitation).
- Stockfish eval is objective context, not absolute ground truth; associations are predictive/descriptive, not causal.

## 14. Recommendation for 15.3C

Artifact: `data/processed/dense_move_loss_pilot_2024_09_v1.parquet` (gitignored under `data/`; not staged).

Recommendation is derived from the measured throughput and validation above; see the phase report for the explicit 15.3C routing decision.
