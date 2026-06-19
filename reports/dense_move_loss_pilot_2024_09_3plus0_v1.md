# Dense Move Loss Pilot — 2024-09

**Ticket:** 15.3B — Dense Move-by-Move Loss Extraction Pilot (PILOT ONLY)
**Engine:** Stockfish 18 @ depth 12

## 1. Executive summary

Dense per-ply next-move loss pilot on the first 1,500 accepted 600+0 games of 2024-09 (cap 1,500). Both White and Black moves with move number >= 5 are measured — extending the four White-only numbered checkpoints to a dense curve. **This is a pilot only; no full dense extraction has been run.** One Stockfish eval per pre-move position (Option A); the post-move eval is the next position's eval (reused). Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is objective position context, not absolute ground truth.

## 2. Pilot scope

- Month: 2024_09
- Accepted games scanned to fill cap: 7,403
- Accepted games used: 1,500 (cap 1,500)
- Universe: non-terminal plies, move_number >= 5, both colors
- Eval strategy: Option A (one eval per pre-move position; post-move reused)

## 3. Runtime and throughput

- Wall-clock runtime: 1937.4 s
- Engine seconds: 1929.5 s
- Engine evals: 96,020 | cache reuse hits: 93,450 | terminal positions: 400
- Throughput: 49.8 evals/s

## 4. Replay validation

- Rows written: 94,935
- Unique games: 1,485
- Duplicate (game_id, ply) keys: 0
- Games with a replay failure (partial rows kept): 0

## 5. Clock / think-time validation

- Missing-clock rows: 0
- Clock-anomaly rows (no coarse bucket): 0
- Think-time-anomaly rows (no bucket): 9
- clock_before_s default for a side's first move: 600 s (10+0).

## 6. Evaluation validation

- OK rows: 94,935
- Mate-band rows (flagged, excluded from headline): 4,465
- Eval-error rows: 0

## 7. Row schema validation

- No raw-username columns: True
- Columns: 65 (typed schema + mover/opponent player hashes)

## 8. Loss metric summary

Expected-score loss (OK, non-mate-band, n=90,470): mean 0.0338 | median 0.011 | p90 0.0898 | zero share 0.2565
Clipped cp loss (n=90,470): mean 57.0 | median 20.0 | p90 151.0 | zero share 0.2565

## 9. Large-loss rates

- ES loss >= 0.05: 0.195 | >= 0.10: 0.0864
- clipped cp >= 100: 0.1665 | >= 200: 0.0677

## 10. Coverage by color / phase / clock / rating

- By mover color: {'black': 47087, 'white': 47848}
- By phase: {'endgame': 27416, 'middlegame': 49841, 'opening': 17678}
- By clock bucket: {'60_180': 72572, 'over_180': 296, 'under_60': 22067}
- By eval band: {'clear': 28061, 'decided': 5140, 'mate_band': 4465, 'near_equal': 33317, 'slight': 23952}
- By rating bucket: {'1000_1199': 3985, '1200_1399': 8766, '1400_1599': 14162, '1600_1799': 21875, '1800_1999': 21256, '2000_2199': 14945, '2200_2399': 6226, '2400_2599': 1747, '2600_2799': 323, '600_799': 210, '800_999': 1440}

## 11. Player-hash join coverage

- mover_player_hash match fraction: 1.0 (94,935/94,935)

## 12. Full-run runtime extrapolation

- 15.3A both-months dense universe estimate: ~3,340,000 positions.
- At pilot throughput (49.8 evals/s, depth 12): ~18.6 h both months (~9.3 h/month).

## 13. Known limitations

- Pilot only; one month, capped game count; not the full dense atlas.
- Depth-parity: pre-move (mover to move) and post-move (opponent to move) are both evaluated at the same fixed depth; the half-ply search-parity asymmetry is acknowledged (15.0C found it benign) and should be re-checked.
- Mate-band rows are flagged and excluded from headline loss summaries.
- Loss distributions are right-skewed; medians/percentiles reported with means.
- No pre-move trajectory / prior-quality control here (stated limitation).
- Stockfish eval is objective context, not absolute ground truth; associations are predictive/descriptive, not causal.

## 14. Recommendation for 15.3C

Artifact: `data/processed/dense_move_loss_pilot_2024_09_3plus0_v1.parquet` (gitignored under `data/`; not staged).

Recommendation is derived from the measured throughput and validation above; see the phase report for the explicit 15.3C routing decision.
