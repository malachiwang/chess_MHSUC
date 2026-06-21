# Dense Move Loss — 2024-09 180+0 Matched-Size Extraction

**Ticket:** 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction
**Engine:** Stockfish 18 @ depth 12

> **Matched-size dense extraction artifact. Not a final cross-time-control analysis. No causal claims. Use within-control rating quantiles for comparisons.**

## 1. Executive summary

Capped matched-size dense per-ply next-move loss extraction for **2024-09 180+0** — every accepted game in the matched cap, both colors, move_number >= 5. 24,000 accepted games processed → **1,495,648 per-ply rows** in 1,512,713 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **Extraction only — no cross-time-control modeling, no atlas figures, no Phase 16 statistical claims.** Predictive/descriptive only — not causal; rating pools across controls are not directly comparable (use within-control quantiles); Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_09; time control: 180+0. Depth 12. Both colors, move_number >= 5.
- Accepted 180+0 games (header-derived, capped): 24,000; processed: 24,000.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).
- ES transform scale reused from the 10+0 train fit (NOT refit).

## 3. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 5.
- Chunk dir: `data/processed/dense_move_loss_2024_09_3plus0_24k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained.
- Run under `caffeinate -dimsu` (machine-awake).

## 4. Runtime and throughput
- Wall-clock: 30757.1 s; engine seconds: 30528.3 s.
- Engine evals: 1,512,713; cache reuse: 1,471,940; terminal: 6,643.
- Throughput: 49.6 evals/s.

## 5. Replay validation
- Rows: 1,495,648; unique games: 23,708; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 6. Evaluation validation
- OK rows: 1,495,648; eval-error rows: 0; mate-band (flagged, excluded from headline): 73,475.
- raw cp loss negative share: 0.2199 (actual move beat prior static eval; expected).

## 7. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 114.
- clock > start rows: 41; negative think-time rows: 114 (flagged, not dropped).

## 8. Time-control-aware schema validation
- time_control_raw: {'180+0': 1495648}
- initial_time_s: {'180': 1495648}; increment_s: {'0': 1495648} (expect 0 for no-increment); family: {'no_increment': 1495648} (expect no_increment); speed: {'blitz': 1495648} (expect blitz).
- clock_fraction range: [0.0, 6.65] (computed off initial_time_s, not a hardcoded 600).
- increment_buffer null share: 1.0 (1.0 expected for a no-increment control).

## 9. Row schema and privacy validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).
- mover_player_hash match fraction: 1.0 (1,495,648/1,495,648); one-way hashes only; no raw usernames written.

## 10. Loss metric summary
- ES loss (OK, non-mate, n=1,422,173): mean 0.0338 | median 0.0113 | p90 0.0898 | zero share 0.2541.
- ES loss >= 0.05: 0.1953 | >= 0.10: 0.0865.
- clipped cp loss: mean 57.1 | median 20.0 | p90 152.0; >= 100: 0.1671 | >= 200: 0.0678.
- Both-color orientation: White ES mean 0.0338 / Black ES mean 0.0338 (close ⇒ sign correct).

## 11. Coverage by color / phase / eval / clock / result / rating
- mover color: {'black': 741683, 'white': 753965}
- phase: {'endgame': 428576, 'middlegame': 785329, 'opening': 281743}
- eval band: {'clear': 443276, 'decided': 81993, 'mate_band': 73475, 'near_equal': 516370, 'slight': 380534}
- clock bucket: {'60_180': 1150937, 'over_180': 4144, 'under_60': 340567}
- result class: {'BLACK_WIN': 683530, 'DRAW': 102940, 'WHITE_WIN': 709178}
- rating bucket: {'1000_1199': 64860, '1200_1399': 130815, '1400_1599': 216071, '1600_1799': 322002, '1800_1999': 361629, '2000_2199': 250608, '2200_2399': 93541, '2400_2599': 27399, '2600_2799': 2704, '2800_2999': 114, '3000_3199': 616, '400_599': 223, '600_799': 3656, '800_999': 21410}

## 12. Non-claims
- Extraction-only artifact; inputs for 16.2, not a Phase 16 result.
- No causal claim; faster controls flagging more is descriptive, not 'time pressure causes worse reasoning' or 'low clock causes blunders'.
- Rating pools differ by control; comparisons must use within-control rating quantiles. clock_fraction is the cross-control clock axis.
- Stockfish eval = objective context, not ground truth; sharpness moderation neither confirmed nor disproven here.

## 13. Artifact
- Artifact: `data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet` (gitignored under `data/`; not staged).
- Failed games: 0.
