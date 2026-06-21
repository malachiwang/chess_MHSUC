# Dense Move Loss — 2024-10 300+0 Matched-Size Extraction

**Ticket:** 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction
**Engine:** Stockfish 18 @ depth 12

> **Matched-size dense extraction artifact. Not a final cross-time-control analysis. No causal claims. Use within-control rating quantiles for comparisons.**

## 1. Executive summary

Capped matched-size dense per-ply next-move loss extraction for **2024-10 300+0** — every accepted game in the matched cap, both colors, move_number >= 5. 24,000 accepted games processed → **1,437,116 per-ply rows** in 1,454,106 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **Extraction only — no cross-time-control modeling, no atlas figures, no Phase 16 statistical claims.** Predictive/descriptive only — not causal; rating pools across controls are not directly comparable (use within-control quantiles); Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_10; time control: 300+0. Depth 12. Both colors, move_number >= 5.
- Accepted 300+0 games (header-derived, capped): 24,000; processed: 24,000.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).
- ES transform scale reused from the 10+0 train fit (NOT refit).

## 3. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 5.
- Chunk dir: `data/processed/dense_move_loss_2024_10_5plus0_24k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained.
- Run under `caffeinate -dimsu` (machine-awake).

## 4. Runtime and throughput
- Wall-clock: 28737.8 s; engine seconds: 28517.8 s.
- Engine evals: 1,454,106; cache reuse: 1,413,372; terminal: 6,754.
- Throughput: 51.0 evals/s.

## 5. Replay validation
- Rows: 1,437,116; unique games: 23,744; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 6. Evaluation validation
- OK rows: 1,437,116; eval-error rows: 0; mate-band (flagged, excluded from headline): 72,697.
- raw cp loss negative share: 0.2165 (actual move beat prior static eval; expected).

## 7. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 165.
- clock > start rows: 62; negative think-time rows: 165 (flagged, not dropped).

## 8. Time-control-aware schema validation
- time_control_raw: {'300+0': 1437116}
- initial_time_s: {'300': 1437116}; increment_s: {'0': 1437116} (expect 0 for no-increment); family: {'no_increment': 1437116} (expect no_increment); speed: {'blitz': 1437116} (expect blitz).
- clock_fraction range: [0.0, 3.3] (computed off initial_time_s, not a hardcoded 600).
- increment_buffer null share: 1.0 (1.0 expected for a no-increment control).

## 9. Row schema and privacy validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).
- mover_player_hash match fraction: 1.0 (1,437,116/1,437,116); one-way hashes only; no raw usernames written.

## 10. Loss metric summary
- ES loss (OK, non-mate, n=1,364,419): mean 0.0352 | median 0.0119 | p90 0.094 | zero share 0.2499.
- ES loss >= 0.05: 0.2045 | >= 0.10: 0.092.
- clipped cp loss: mean 59.7 | median 21.0 | p90 159.0; >= 100: 0.1769 | >= 200: 0.0727.
- Both-color orientation: White ES mean 0.0353 / Black ES mean 0.0351 (close ⇒ sign correct).

## 11. Coverage by color / phase / eval / clock / result / rating
- mover color: {'black': 712462, 'white': 724654}
- phase: {'endgame': 396486, 'middlegame': 759505, 'opening': 281125}
- eval band: {'clear': 444512, 'decided': 83425, 'mate_band': 72697, 'near_equal': 470314, 'slight': 366168}
- clock bucket: {'60_180': 421707, 'over_180': 868087, 'under_60': 147322}
- result class: {'BLACK_WIN': 657522, 'DRAW': 100022, 'WHITE_WIN': 679572}
- rating bucket: {'1000_1199': 146927, '1200_1399': 217835, '1400_1599': 281122, '1600_1799': 303307, '1800_1999': 251321, '2000_2199': 117369, '2200_2399': 22469, '2400_2599': 529, '2600_2799': 157, '2800_2999': 355, '3000_3199': 273, '400_599': 4014, '600_799': 21090, '800_999': 70348}

## 12. Non-claims
- Extraction-only artifact; inputs for 16.2, not a Phase 16 result.
- No causal claim; faster controls flagging more is descriptive, not 'time pressure causes worse reasoning' or 'low clock causes blunders'.
- Rating pools differ by control; comparisons must use within-control rating quantiles. clock_fraction is the cross-control clock axis.
- Stockfish eval = objective context, not ground truth; sharpness moderation neither confirmed nor disproven here.

## 13. Artifact
- Artifact: `data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet` (gitignored under `data/`; not staged).
- Failed games: 0.
