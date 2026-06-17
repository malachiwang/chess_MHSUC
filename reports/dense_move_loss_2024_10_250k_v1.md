# Dense Move Loss — 2024-10 Full 10+0 Extraction

**Ticket:** 15.3C — Full Dense Move-by-Move Loss Extraction (2024-09 only)
**Engine:** Stockfish 18 @ depth 12

## 1. Executive summary

Full dense per-ply next-move loss extraction for **2024-10 10+0 (600+0) only** — every accepted game, both colors, move_number >= 5. 24,842 accepted games processed → **1,436,866 per-ply rows** in 1,454,008 engine evals. One Stockfish eval per pre-move position (Option A); post-move eval reused. Primary metric: expected-score loss, mover perspective; secondary: clipped centipawn loss. **2024-10 has NOT been run; no visual atlas; no dense controlled model.** Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is objective context, not absolute ground truth.

## 2. Extraction scope
- Month: 2024_10 (10+0 / 600+0 only). Depth 12. Both colors, move_number >= 5.
- Accepted 600+0 games available: 24,842; processed: 24,842.
- Eval strategy: Option A (one eval per pre-move position; post-move reused).

## 3. Command and environment
- Stockfish: Stockfish 18; depth 12; ES transform scale reused (not refit).
- Run under `caffeinate -dimsu` (machine-awake); chunked + resumable.

## 4. Chunking and resumability
- Chunk size: 5,000 accepted games/chunk; chunks: 5.
- Chunk dir: `data/processed/dense_move_loss_2024_10_250k_v1_chunks` (gitignored). Games skipped on resume: 0.
- Final artifact = vertical concat of chunk parquets; chunks retained (no auto-delete).

## 5. Runtime and throughput
- Wall-clock: 31770.2 s; engine seconds: 31539.0 s.
- Engine evals: 1,454,008; cache reuse: 1,412,314; terminal: 7,410.
- Throughput: 46.1 evals/s.

## 6. Preflight reproduction
- (preflight run separately before this extraction; see phase report.)

## 7. Replay validation
- Rows: 1,436,866; unique games: 24,552; duplicate (game_id, ply) keys: 0.
- Replay failures (partial rows kept): 0.

## 8. Evaluation validation
- OK rows: 1,436,866; eval-error rows: 0; mate-band (flagged, excluded from headline): 74,407.
- raw cp loss negative share: 0.2206 (actual move beat prior static eval; expected).

## 9. Clock and think-time validation
- Missing-clock rows: 0; clock-anomaly (no bucket): 0; think-anomaly (no bucket): 125.
- clock > start (600 s) rows: 109; negative think-time rows: 125 (flagged, not dropped).

## 10. Time-control-aware schema validation
- time_control_raw: {'600+0': 1436866}
- initial_time_s: {'600': 1436866}; increment_s: {'0': 1436866}; family: {'no_increment': 1436866}; speed: {'rapid': 1436866}.
- clock_fraction range: [0.0, 6.2033].
- increment_buffer null share: 1.0 (1.0 expected for 10+0); low_increment_buffer_flag null share: 1.0.

## 11. Row schema validation
- No raw-username columns: True; columns: 65 (typed schema + player hashes).

## 12. Loss metric summary
- ES loss (OK, non-mate, n=1,362,459): mean 0.0346 | median 0.0114 | p90 0.0926 | zero share 0.2555.
- clipped cp loss: mean 58.9 | median 21.0 | p90 158.0.
- Both-color orientation: White ES mean 0.0347 / Black ES mean 0.0345 (close ⇒ sign correct).

## 13. Large-loss rates
- ES loss >= 0.05: 0.2006 | >= 0.10: 0.0902.
- clipped cp >= 100: 0.1746 | >= 200: 0.0717.

## 14. Coverage by color / phase / eval / clock / rating
- mover color: {'black': 712153, 'white': 724713}
- phase: {'endgame': 400382, 'middlegame': 747197, 'opening': 289287}
- eval band: {'clear': 454805, 'decided': 85567, 'mate_band': 74407, 'near_equal': 458630, 'slight': 363457}
- clock bucket: {'60_180': 94299, 'over_180': 1297765, 'under_60': 44802}
- result class: {'BLACK_WIN': 655079, 'DRAW': 109852, 'WHITE_WIN': 671935}
- rating bucket: {'1000_1199': 137808, '1200_1399': 202158, '1400_1599': 297839, '1600_1799': 305805, '1800_1999': 259106, '2000_2199': 114837, '2200_2399': 25956, '2400_2599': 2820, '2600_2799': 138, '400_599': 4682, '600_799': 18009, '800_999': 67708}

## 15. Player-hash coverage and privacy
- mover_player_hash match fraction: 1.0 (1,436,866/1,436,866); one-way hashes only; no raw usernames written.

## 16. Comparison to 2024-09 full dense extraction
| Metric | 2024-09 | 2024-10 |
|---|---|---|
| Rows | 1,496,890 | 1,436,866 |
| Rows/game | 58.4 | 58.5 |
| Mate-band share | 0.054 | 0.052 |
| ES loss mean | 0.0346 | 0.0346 |
| ES loss median | 0.0114 | 0.0114 |
| ES loss p90 | 0.0926 | 0.0926 |
| ES >= 0.10 | 0.0903 | 0.0902 |

Both months use the identical pipeline and the same train-fit ES transform; matching per-row distributions are the cross-month replication check.

## 17. Known limitations
- 2024-10 10+0 only; this completes the SECOND 10+0 anchor month (with 2024-09); no cross-time-control data; no other time controls extracted.
- No visual atlas; no dense controlled model.
- Depth-parity (mover-to-move vs opponent-to-move, same depth) acknowledged (15.0C benign); re-check recommended.
- Mate-band rows flagged and excluded from headline; loss right-skewed (medians/percentiles reported with means).
- No pre-move trajectory / prior-quality control (stated limitation).
- Stockfish eval is objective context, not absolute ground truth; predictive/descriptive, not causal.

## 18. Recommendation for next step
- Artifact: `data/processed/dense_move_loss_2024_10_250k_v1.parquet` (gitignored under `data/`; not staged).
- Recommend **15.4A — CP/ES Constraint Atlas Visualization Audit**: both 10+0 anchor months (2024-09 + 2024-10) now have full dense artifacts, so the dense visual atlas can be designed (then implemented in 15.4B). Do not skip the 15.4A audit.
