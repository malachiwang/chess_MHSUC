# Dense Move Loss — 2024-09 Full 10+0 Extraction

**Ticket:** 15.3C — Full Dense Move-by-Move Loss Extraction (2024-09 only)
**Engine:** Stockfish 18 @ depth 12

## 1. Executive summary

Full dense per-ply next-move loss extraction for **2024-09 10+0 (600+0) only** — every accepted game, both colors, move_number >= 5. 25,945 accepted games processed → **1,496,890 per-ply rows** in 1,514,689 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **2024-10 has NOT been run; no visual atlas; no dense controlled model.** Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_09 (10+0 / 600+0 only). Depth 12. Both colors, move_number >= 5.
- Accepted 600+0 games available: 25,945; processed: 25,945.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).

## 3. Command and environment
- Stockfish: Stockfish 18; depth 12; ES transform scale reused (not refit).
- Run under `caffeinate -dimsu` (machine-awake); chunked + resumable.

## 4. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 6.
- Chunk dir: `data/processed/dense_move_loss_2024_09_250k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained (no auto-delete).

## 5. Runtime and throughput
- Wall-clock: 45831.8 s; engine seconds: 45380.0 s.
- Engine evals: 1,514,689; cache reuse: 1,471,279; terminal: 7,812.
- Throughput: 33.4 evals/s.

## 6. Preflight reproduction
- (preflight run separately before this extraction; see phase report.)

## 7. Replay validation
- Rows: 1,496,890; unique games: 25,611; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 8. Evaluation validation
- OK rows: 1,496,890; eval-error rows: 0; mate-band (flagged, excluded from headline): 80,577.
- raw cp loss negative share: 0.2218 (actual move beat prior static eval; expected).

## 9. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 133.
- clock > start (600 s) rows: 132; negative think-time rows: 133 (flagged, not dropped).

## 10. Time-control-aware schema validation
- time_control_raw: {'600+0': 1496890}
- initial_time_s: {'600': 1496890}; increment_s: {'0': 1496890}; family: {'no_increment': 1496890}; speed: {'rapid': 1496890}.
- clock_fraction range: [0.0, 11.9367].
- increment_buffer null share: 1.0 (1.0 expected for 10+0); low_increment_buffer_flag null share: 1.0.

## 11. Row schema validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).

## 12. Loss metric summary
- ES loss (OK, non-mate, n=1,416,313): mean 0.0346 | median 0.0114 | p90 0.0926 | zero share 0.2567.
- clipped cp loss: mean 58.9 | median 21.0 | p90 158.0.
- Both-color orientation: White ES mean 0.0347 / Black ES mean 0.0344 (close ⇒ sign correct).

## 13. Large-loss rates
- ES loss >= 0.05: 0.2009 | >= 0.10: 0.0903.
- clipped cp >= 100: 0.1752 | >= 200: 0.072.

## 14. Coverage by color / phase / eval / clock / rating
- mover color: {'black': 741863, 'white': 755027}
- phase: {'endgame': 416288, 'middlegame': 778845, 'opening': 301757}
- eval band: {'clear': 477381, 'decided': 89203, 'mate_band': 80577, 'near_equal': 474669, 'slight': 375060}
- clock bucket: {'60_180': 95862, 'over_180': 1354833, 'under_60': 46195}
- result class: {'BLACK_WIN': 679788, 'DRAW': 112005, 'WHITE_WIN': 705097}
- rating bucket: {'1000_1199': 149195, '1200_1399': 215541, '1400_1599': 293149, '1600_1799': 317874, '1800_1999': 270489, '2000_2199': 120678, '2200_2399': 32504, '2400_2599': 5513, '2600_2799': 1202, '400_599': 2413, '600_799': 19474, '800_999': 68858}

## 15. Player-hash coverage and privacy
- mover_player_hash match fraction: 1.0 (1,496,890/1,496,890); one-way hashes only; no raw usernames written.

## 16. Comparison to 15.3B pilot
- 15.3B pilot (first 1,500 games): 86,977 rows, 88,012 evals, ES mean 0.0347, median 0.0115. This full-month run extends the same pipeline to all accepted games; per-row distributions are expected to be consistent with the pilot.

## 17. Known limitations
- 2024-09 only; 2024-10 dense extraction NOT run; no cross-time-control data.
- No visual atlas; no dense controlled model.
- Depth-parity (mover-to-move vs opponent-to-move, same depth) acknowledged (15.0C benign); re-check recommended.
- Mate-band rows flagged and excluded from headline; loss right-skewed (medians/percentiles reported with means).
- No pre-move trajectory / prior-quality control (stated limitation).
- Stockfish eval is objective context, not absolute ground truth; predictive/descriptive, not causal.

## 18. Recommendation for next step
- Artifact: `data/processed/dense_move_loss_2024_09_250k_v1.parquet` (gitignored under `data/`; not staged).
- Recommend **15.3D — Full Dense Move-by-Move Loss Extraction Replication Month (2024-10)** before any dense atlas, so final claims use both monthly samples.
