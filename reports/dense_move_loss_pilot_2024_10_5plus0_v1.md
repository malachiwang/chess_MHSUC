# Dense Move Loss Pilot — 2024-10

**Ticket:** 15.3B — Dense Move-by-Move Loss Extraction Pilot (PILOT ONLY)
**Engine:** Stockfish 18 @ depth 12

## 1. Executive summary

Dense per-ply next-move loss pilot on the first 1,500 accepted 600+0 games of 2024-10 (cap 1,500). Both White and Black moves with move number >= 5 are measured — extending the four White-only numbered checkpoints to a dense curve. **This is a pilot only; no full dense extraction has been run.** One Stockfish eval per pre-move position (Option A); the post-move eval is the next position's eval (reused). Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is objective position context, not absolute ground truth.

## 2. Pilot scope

- Month: 2024_10
- Accepted games scanned to fill cap: 11,131
- Accepted games used: 1,500 (cap 1,500)
- Universe: non-terminal plies, move_number >= 5, both colors
- Eval strategy: Option A (one eval per pre-move position; post-move reused)

## 3. Runtime and throughput

- Wall-clock runtime: 1939.0 s
- Engine seconds: 1928.0 s
- Engine evals: 90,728 | cache reuse hits: 88,169 | terminal positions: 407
- Throughput: 47.1 evals/s

## 4. Replay validation

- Rows written: 89,652
- Unique games: 1,483
- Duplicate (game_id, ply) keys: 0
- Games with a replay failure (partial rows kept): 0

## 5. Clock / think-time validation

- Missing-clock rows: 0
- Clock-anomaly rows (no coarse bucket): 0
- Think-time-anomaly rows (no bucket): 16
- clock_before_s default for a side's first move: 600 s (10+0).

## 6. Evaluation validation

- OK rows: 89,652
- Mate-band rows (flagged, excluded from headline): 4,258
- Eval-error rows: 0

## 7. Row schema validation

- No raw-username columns: True
- Columns: 65 (typed schema + mover/opponent player hashes)

## 8. Loss metric summary

Expected-score loss (OK, non-mate-band, n=85,394): mean 0.0353 | median 0.0119 | p90 0.0939 | zero share 0.2493
Clipped cp loss (n=85,394): mean 59.6 | median 21.0 | p90 159.0 | zero share 0.2493

## 9. Large-loss rates

- ES loss >= 0.05: 0.2049 | >= 0.10: 0.0921
- clipped cp >= 100: 0.176 | >= 200: 0.0728

## 10. Coverage by color / phase / clock / rating

- By mover color: {'black': 44442, 'white': 45210}
- By phase: {'endgame': 24664, 'middlegame': 47404, 'opening': 17584}
- By clock bucket: {'60_180': 26127, 'over_180': 54095, 'under_60': 9430}
- By eval band: {'clear': 28090, 'decided': 4928, 'mate_band': 4258, 'near_equal': 30016, 'slight': 22360}
- By rating bucket: {'1000_1199': 9316, '1200_1399': 13606, '1400_1599': 19087, '1600_1799': 17841, '1800_1999': 16146, '2000_2199': 7301, '2200_2399': 1156, '2400_2599': 46, '400_599': 94, '600_799': 969, '800_999': 4090}

## 11. Player-hash join coverage

- mover_player_hash match fraction: 1.0 (89,652/89,652)

## 12. Full-run runtime extrapolation

- 15.3A both-months dense universe estimate: ~3,340,000 positions.
- At pilot throughput (47.1 evals/s, depth 12): ~19.7 h both months (~9.8 h/month).

## 13. Known limitations

- Pilot only; one month, capped game count; not the full dense atlas.
- Depth-parity: pre-move (mover to move) and post-move (opponent to move) are both evaluated at the same fixed depth; the half-ply search-parity asymmetry is acknowledged (15.0C found it benign) and should be re-checked.
- Mate-band rows are flagged and excluded from headline loss summaries.
- Loss distributions are right-skewed; medians/percentiles reported with means.
- No pre-move trajectory / prior-quality control here (stated limitation).
- Stockfish eval is objective context, not absolute ground truth; associations are predictive/descriptive, not causal.

## 14. Recommendation for 15.3C

Artifact: `data/processed/dense_move_loss_pilot_2024_10_5plus0_v1.parquet` (gitignored under `data/`; not staged).

Recommendation is derived from the measured throughput and validation above; see the phase report for the explicit 15.3C routing decision.
