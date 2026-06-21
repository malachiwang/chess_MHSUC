# Dense Move Loss — 2024-10 180+0 Matched-Size Extraction

**Ticket:** 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction
**Engine:** Stockfish 18 @ depth 12

> **Matched-size dense extraction artifact. Not a final cross-time-control analysis. No causal claims. Use within-control rating quantiles for comparisons.**

## 1. Executive summary

Capped matched-size dense per-ply next-move loss extraction for **2024-10 180+0** — every accepted game in the matched cap, both colors, move_number >= 5. 24,000 accepted games processed → **1,491,120 per-ply rows** in 1,508,508 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **Extraction only — no cross-time-control modeling, no atlas figures, no Phase 16 statistical claims.** Predictive/descriptive only — not causal; rating pools across controls are not directly comparable (use within-control quantiles); Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_10; time control: 180+0. Depth 12. Both colors, move_number >= 5.
- Accepted 180+0 games (header-derived, capped): 24,000; processed: 24,000.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).
- ES transform scale reused from the 10+0 train fit (NOT refit).

## 3. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 5.
- Chunk dir: `data/processed/dense_move_loss_2024_10_3plus0_24k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained.
- Run under `caffeinate -dimsu` (machine-awake).

## 4. Runtime and throughput
- Wall-clock: 30875.2 s; engine seconds: 30651.1 s.
- Engine evals: 1,508,508; cache reuse: 1,467,381; terminal: 6,351.
- Throughput: 49.2 evals/s.

## 5. Replay validation
- Rows: 1,491,120; unique games: 23,739; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 6. Evaluation validation
- OK rows: 1,491,120; eval-error rows: 0; mate-band (flagged, excluded from headline): 70,302.
- raw cp loss negative share: 0.2206 (actual move beat prior static eval; expected).

## 7. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 82.
- clock > start rows: 6; negative think-time rows: 82 (flagged, not dropped).

## 8. Time-control-aware schema validation
- time_control_raw: {'180+0': 1491120}
- initial_time_s: {'180': 1491120}; increment_s: {'0': 1491120} (expect 0 for no-increment); family: {'no_increment': 1491120} (expect no_increment); speed: {'blitz': 1491120} (expect blitz).
- clock_fraction range: [0.0, 6.2389] (computed off initial_time_s, not a hardcoded 600).
- increment_buffer null share: 1.0 (1.0 expected for a no-increment control).

## 9. Row schema and privacy validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).
- mover_player_hash match fraction: 1.0 (1,491,120/1,491,120); one-way hashes only; no raw usernames written.

## 10. Loss metric summary
- ES loss (OK, non-mate, n=1,420,818): mean 0.0336 | median 0.0112 | p90 0.0897 | zero share 0.2548.
- ES loss >= 0.05: 0.1955 | >= 0.10: 0.0863.
- clipped cp loss: mean 56.6 | median 20.0 | p90 151.0; >= 100: 0.1662 | >= 200: 0.067.
- Both-color orientation: White ES mean 0.0336 / Black ES mean 0.0336 (close ⇒ sign correct).

## 11. Coverage by color / phase / eval / clock / result / rating
- mover color: {'black': 739410, 'white': 751710}
- phase: {'endgame': 421539, 'middlegame': 787428, 'opening': 282153}
- eval band: {'clear': 436832, 'decided': 77804, 'mate_band': 70302, 'near_equal': 522198, 'slight': 383984}
- clock bucket: {'60_180': 1143501, 'over_180': 4047, 'under_60': 343572}
- result class: {'BLACK_WIN': 681160, 'DRAW': 92465, 'WHITE_WIN': 717495}
- rating bucket: {'1000_1199': 62889, '1200_1399': 117509, '1400_1599': 224513, '1600_1799': 315197, '1800_1999': 371372, '2000_2199': 250334, '2200_2399': 92580, '2400_2599': 31163, '2600_2799': 3158, '2800_2999': 600, '3000_3199': 37, '400_599': 587, '600_799': 3565, '800_999': 17616}

## 12. Non-claims
- Extraction-only artifact; inputs for 16.2, not a Phase 16 result.
- No causal claim; faster controls flagging more is descriptive, not 'time pressure causes worse reasoning' or 'low clock causes blunders'.
- Rating pools differ by control; comparisons must use within-control rating quantiles. clock_fraction is the cross-control clock axis.
- Stockfish eval = objective context, not ground truth; sharpness moderation neither confirmed nor disproven here.

## 13. Artifact
- Artifact: `data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet` (gitignored under `data/`; not staged).
- Failed games: 0.
