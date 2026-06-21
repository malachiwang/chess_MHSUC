# Dense Move Loss — 2024-09 300+0 Matched-Size Extraction

**Ticket:** 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction
**Engine:** Stockfish 18 @ depth 12

> **Matched-size dense extraction artifact. Not a final cross-time-control analysis. No causal claims. Use within-control rating quantiles for comparisons.**

## 1. Executive summary

Capped matched-size dense per-ply next-move loss extraction for **2024-09 300+0** — every accepted game in the matched cap, both colors, move_number >= 5. 24,000 accepted games processed → **1,437,932 per-ply rows** in 1,454,997 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **Extraction only — no cross-time-control modeling, no atlas figures, no Phase 16 statistical claims.** Predictive/descriptive only — not causal; rating pools across controls are not directly comparable (use within-control quantiles); Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_09; time control: 300+0. Depth 12. Both colors, move_number >= 5.
- Accepted 300+0 games (header-derived, capped): 24,000; processed: 24,000.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).
- ES transform scale reused from the 10+0 train fit (NOT refit).

## 3. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 5.
- Chunk dir: `data/processed/dense_move_loss_2024_09_5plus0_24k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained.
- Run under `caffeinate -dimsu` (machine-awake).

## 4. Runtime and throughput
- Wall-clock: 28767.0 s; engine seconds: 28546.3 s.
- Engine evals: 1,454,997; cache reuse: 1,414,165; terminal: 6,702.
- Throughput: 51.0 evals/s.

## 5. Replay validation
- Rows: 1,437,932; unique games: 23,767; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 6. Evaluation validation
- OK rows: 1,437,932; eval-error rows: 0; mate-band (flagged, excluded from headline): 70,639.
- raw cp loss negative share: 0.2172 (actual move beat prior static eval; expected).

## 7. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 145.
- clock > start rows: 27; negative think-time rows: 145 (flagged, not dropped).

## 8. Time-control-aware schema validation
- time_control_raw: {'300+0': 1437932}
- initial_time_s: {'300': 1437932}; increment_s: {'0': 1437932} (expect 0 for no-increment); family: {'no_increment': 1437932} (expect no_increment); speed: {'blitz': 1437932} (expect blitz).
- clock_fraction range: [0.0, 4.0467] (computed off initial_time_s, not a hardcoded 600).
- increment_buffer null share: 1.0 (1.0 expected for a no-increment control).

## 9. Row schema and privacy validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).
- mover_player_hash match fraction: 1.0 (1,437,932/1,437,932); one-way hashes only; no raw usernames written.

## 10. Loss metric summary
- ES loss (OK, non-mate, n=1,367,293): mean 0.0349 | median 0.0117 | p90 0.0931 | zero share 0.2512.
- ES loss >= 0.05: 0.2027 | >= 0.10: 0.0911.
- clipped cp loss: mean 59.1 | median 21.0 | p90 157.0; >= 100: 0.1745 | >= 200: 0.0715.
- Both-color orientation: White ES mean 0.0349 / Black ES mean 0.0349 (close ⇒ sign correct).

## 11. Coverage by color / phase / eval / clock / result / rating
- mover color: {'black': 712810, 'white': 725122}
- phase: {'endgame': 396965, 'middlegame': 759480, 'opening': 281487}
- eval band: {'clear': 441709, 'decided': 80506, 'mate_band': 70639, 'near_equal': 474338, 'slight': 370740}
- clock bucket: {'60_180': 422648, 'over_180': 867839, 'under_60': 147445}
- result class: {'BLACK_WIN': 647632, 'DRAW': 98723, 'WHITE_WIN': 691577}
- rating bucket: {'1000_1199': 136393, '1200_1399': 215819, '1400_1599': 296855, '1600_1799': 298360, '1800_1999': 252647, '2000_2199': 124399, '2200_2399': 22712, '2400_2599': 928, '2600_2799': 63, '2800_2999': 333, '3000_3199': 397, '400_599': 2037, '600_799': 17884, '800_999': 69105}

## 12. Non-claims
- Extraction-only artifact; inputs for 16.2, not a Phase 16 result.
- No causal claim; faster controls flagging more is descriptive, not 'time pressure causes worse reasoning' or 'low clock causes blunders'.
- Rating pools differ by control; comparisons must use within-control rating quantiles. clock_fraction is the cross-control clock axis.
- Stockfish eval = objective context, not ground truth; sharpness moderation neither confirmed nor disproven here.

## 13. Artifact
- Artifact: `data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet` (gitignored under `data/`; not staged).
- Failed games: 0.
