# Phase 15.3D — Full Dense Move-by-Move Loss Extraction Replication Month

**Labels:** IMPLEMENTATION + long-running extraction | move-quality / Constraint Atlas (Phase 15.3)
**Date:** 2026-06-17
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION (approved replication-month run; 2024-10 only)

## 1. Executive summary

Replicated the full dense move-by-move next-move loss extraction for the second
10+0 anchor month, **2024-10 600+0 only**, at depth 12, both colors,
`move_number >= 5`, chunked/resumable under `caffeinate` — mirroring 15.3C. All
**24,842 accepted 600+0 games** were processed → **1,436,866 per-ply rows** across
**24,552 games** with usable move≥5 rows (290 too short), in **1,454,008 Stockfish
evals** over five chunks. Runtime ~8.8 h at 46.1 evals/s.

Validation is clean and the **cross-month replication is essentially exact**:
ES loss mean 0.0346 / median 0.0114 / p90 0.0926 — identical to 2024-09 to 4 dp;
rows/game 58.5 (vs 58.4); mate-band 5.2% (vs 5.4%); 0 replay failures, 0 eval
errors, 0 duplicate keys, 100% player-hash coverage, no raw usernames;
mover-perspective sign correct for both colors (ES mean 0.0347 White / 0.0345
Black). The time-control-aware schema is uniform (`600+0` / 600 / 0 /
`no_increment` / `rapid`, increment fields null).

A duplicate-run incident occurred mid-extraction and was resolved under the
**15.3D-Hotfix** triage (two extra overnight wrapper chains were terminated; the
single authoritative run was preserved and never collided on the `data/` chunk dir).
The final artifact is clean and uncorrupted.

**Both 10+0 anchor months (2024-09 + 2024-10) now have full dense artifacts.** This
completes the dense 10+0 substrate. No cross-time-control data, no visual atlas, and
no dense controlled model were produced. Predictive/descriptive only — not causal;
Stockfish eval is objective position context, not absolute ground truth.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; the 15.3A/B/C-A/C phase reports and
`reports/dense_move_loss_2024_09_250k_v1.md`; `src/chess_mhsuc/dense_move_loss.py`,
`tests/test_dense_move_loss.py`; confirmed 2024-10 inputs
`data/raw/lichess/lichess_2024_10_first250k.pgn`,
`data/interim/game_records_2024_10_250k_v1.parquet`,
`data/processed/splits_2024_10_250k_v1.json`,
`data/processed/player_metadata_2024_10_250k_v1.parquet`,
`data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json`.

## 3. Files modified

- `src/chess_mhsuc/dense_move_loss.py` — added `--allow-full-month-2024-10` (locked
  to month==2024_10 / depth 12 / 600+0); generalized the full-month gate (each
  month-specific flag restricted to its month; no both-month mode); month-generic
  full-month execution branch with a 2024-09 comparison block + 15.4A recommendation
  for the replication month; preflight broad-sanity for new months; month-aware §17
  limitations in the report renderer.
- `tests/test_dense_move_loss.py` — +7 tests.
- `ROADMAP.md` — 15.3D marked complete; both anchor months noted; next = 15.4A.
- `EXPERIMENT_LOG.md` — added EXP-042.
- `PREREGISTRATION.md` — **unchanged** (extraction design matches 15.3C-A / 15.3C).

## 4. Files created

- `reports/dense_move_loss_2024_10_250k_v1.md` — committed aggregate report (18 §,
  incl. the 2024-09 comparison).
- `reports/phase_reports/phase_15_3d_full_dense_move_loss_replication_month.md` — this.
- `data/processed/dense_move_loss_2024_10_250k_v1.parquet` — final artifact
  (1,436,866 rows × 65 cols, 144 MB; **gitignored**; not staged).
- `data/processed/dense_move_loss_2024_10_250k_v1_chunks/` — 5 chunk parquets +
  `manifest.json` (**gitignored**; retained for resumability).

## 5. Tests run

- `pytest tests/test_dense_move_loss.py` → **53 passed** (46 prior + 7 new).
- Full suite `pytest` → **1,797 passed** (run after the source changes; see §6 note).

New tests: 2024-10 full-month flag accepts 2024_10 and refuses 2024_09 / non-depth-12
/ non-600+0; no both-month mode; the 2024-09 flag still refuses 2024_10; the 2024-09
comparison block renders; expanded schema still excludes raw usernames.

## 6. Preflight command and result

```bash
caffeinate -dimsu PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_10_first250k.pgn --month 2024_10 \
  --preflight --min-move-number 5 --depth 12 --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_10_250k_v1.parquet \
  --out <tmp> --report <tmp>
```

Result: **PASS** (broad sanity for a new month) — 88,052 rows, 1,473 games, 89,066
evals, 0 replay failures, 0 dup keys, both colors present, `time_control_raw=600+0` /
`initial_time_s=600` / `increment_s=0`, full player-hash coverage, no raw usernames.

## 7. Full extraction command

```bash
caffeinate -dimsu PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_10_first250k.pgn --month 2024_10 \
  --time-control 600+0 --allow-full-month-2024-10 --min-move-number 5 --depth 12 \
  --chunk-size 5000 --resume --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_10_250k_v1.parquet \
  --game-records data/interim/game_records_2024_10_250k_v1.parquet \
  --splits data/processed/splits_2024_10_250k_v1.json \
  --chunk-dir data/processed/dense_move_loss_2024_10_250k_v1_chunks \
  --out data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --report reports/dense_move_loss_2024_10_250k_v1.md
```

## 8. Artifact created

`data/processed/dense_move_loss_2024_10_250k_v1.parquet` — 1,436,866 rows × 65
columns (53 base + 12 time-control-aware + 2 player-hash). 144 MB snappy parquet.
Five chunk shards (~282–288k rows each) + `manifest.json`. All gitignored.

## 9. Runtime and throughput

- Wall-clock ~8.8 h (engine ~31,540 s); **46.1 evals/s**.
- 1,454,008 engine evals; cache reuse + terminal handling as in 15.3C; ~58.5 rows/game.
- 5 chunks at chunk_size 5,000 (last partial chunk 281,912 rows).
- Throughput higher than 2024-09's 33.4 eps; the early ~1.5 h were CPU-throttled by
  the duplicate runs (resolved under 15.3D-Hotfix) before settling to ~55–60 games/min.

## 10. Validation summary

| Check | Result |
|---|---|
| Rows | 1,436,866 |
| Unique games | 24,552 (of 24,842 accepted; 290 too short for move≥5) |
| Duplicate (game_id, ply) keys | 0 |
| Status | all `ok`; 0 eval-error, 0 replay-failure |
| Mate-band rows (flagged, excluded from headline) | 74,407 (5.2%) |
| Missing-clock rows | 0 |
| clock > 600 s rows | 109 (flagged, retained) |
| Negative think-time rows | 125 (flagged, retained) |
| ES loss range | [0.0, 0.881] |
| clipped cp loss < 0 | 0 |
| raw cp loss negative share | 0.209 (move beat prior static eval; expected) |
| Both-color ES mean (White / Black) | 0.0347 / 0.0345 (sign correct) |
| Player-hash coverage | 1.0 (1,436,866 / 1,436,866) |
| Raw-username columns | none |
| Clock buckets | under_60 44,802 / 60_180 94,299 / over_180 1,297,765 |
| Result class | WHITE_WIN 671,935 / BLACK_WIN 655,079 / DRAW 109,852 |
| Loss headline (OK, non-mate) | ES mean 0.0346, median 0.0114, p90 0.0926 |
| Large-loss | ES≥0.05 0.201, ES≥0.10 0.090; cp≥100 0.175, cp≥200 0.072 |

## 11. Time-control-aware schema validation

Uniform for this 10+0 month: `time_control_raw` = `600+0`, `initial_time_s` = 600,
`increment_s` = 0, `time_control_family` = `no_increment`, `speed_category` =
`rapid`, `clock_fraction` ∈ [0.0, 6.20] (upper tail = the 109 flagged clock
artifacts), `increment_buffer` null share 1.0 (correct for no-increment),
`think_time_net == gross`, `low_increment_buffer_flag` null. Identical conventions to
15.3C — the two months are schema-compatible.

## 12. Comparison to 2024-09

| Metric | 2024-09 | 2024-10 |
|---|---|---|
| Rows | 1,496,890 | 1,436,866 |
| Rows/game | 58.4 | 58.5 |
| Mate-band share | 0.054 | 0.052 |
| ES loss mean | 0.0346 | 0.0346 |
| ES loss median | 0.0114 | 0.0114 |
| ES loss p90 | 0.0926 | 0.0926 |
| ES ≥ 0.10 | 0.0903 | 0.0902 |
| clipped cp ≥ 100 | 0.175 | 0.175 |
| Both-color ES (W / B) | 0.0347 / 0.0344 | 0.0347 / 0.0345 |

The two independent monthly samples agree to within rounding — a strong cross-month
replication of the dense move-quality distribution.

## 13. Recommendation for next ticket

**15.4A — CP/ES Constraint Atlas Visualization Audit.** Both 10+0 anchor months now
have full dense artifacts, so the dense visual atlas can be designed (per 15.3C-A:
raw rating bins primary + within-time-control percentile optional; clock as absolute
+ fraction + increment-buffer; eval-band conditioning mandatory; game-level /
mover-player-clustered bootstrap CIs; existing cell-count policy). Implementation
follows in 15.4B. Do not skip the 15.4A audit.

## 14. Non-claims

- This is **2024-10 10+0 only**, completing the **second 10+0 anchor month** (with
  2024-09) — **not** cross-time-control analysis.
- Cross-time-control extraction has **not** been run. No visual atlas was generated.
  No dense controlled model was run.
- No causal claim. No "low clock causes blunders." No "time pressure causes worse
  reasoning." No "Stockfish is ground truth." No "human obviousness modeled." No
  "DRAW solved." No "best predictor."
- **C4 unchanged. C3c unchanged.** No thresholds or classifications changed; the ES
  transform was reused, not refit.
