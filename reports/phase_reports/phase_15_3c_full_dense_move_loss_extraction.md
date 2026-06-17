# Phase 15.3C — Full Dense Move-by-Move Loss Extraction

**Labels:** IMPLEMENTATION + long-running extraction | move-quality / Constraint Atlas (Phase 15.3)
**Date:** 2026-06-17
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION (approved one-month full run; 2024-09 only)

## 1. Executive summary

Ran the approved **full dense move-by-move loss extraction for 2024-09 10+0
(600+0) only**, at depth 12, both colors, `move_number >= 5`, chunked and resumable
under `caffeinate`. All **25,945 accepted 600+0 games** were processed →
**1,496,890 per-ply rows** across **25,611 games** with usable move≥5 rows
(334 too short), in **1,514,689 Stockfish evals** (+1,471,279 cache-reuse hits,
7,812 terminal positions). Runtime **45,831.8 s (~12.7 h)** at 33.4 evals/s over six
~5,000-game chunks. Validation is clean: 0 replay failures, 0 eval errors, 0
duplicate keys, 100% player-hash coverage, no raw usernames; mover-perspective sign
correct for both colors (ES mean 0.0347 White / 0.0344 Black); ES loss bounded
[0, 0.838]; clipped cp loss never negative. The **preflight reproduced the 15.3B
pilot counts exactly** (86,977 rows / 1,486 games / 88,012 evals) before the full
run started.

The artifact carries the new **time-control-aware schema** (15.3C-A): all rows are
`600+0` / `initial_time_s=600` / `increment_s=0` / `no_increment` / `rapid`, with the
increment-only fields null — forward-compatible for later time controls without a
re-extraction.

**This is 2024-09 only. 2024-10 dense extraction has NOT been run. No cross-time-
control data, no visual atlas, and no dense controlled model were produced.**
Predictive/descriptive only — not causal, not a degradation curve; Stockfish eval is
objective position context, not absolute ground truth.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; the 15.3A/15.3B/15.3C-A phase reports and
`reports/dense_move_loss_pilot_2024_09_v1.md`; `src/chess_mhsuc/dense_move_loss.py`
and `tests/test_dense_move_loss.py`; confirmed inputs
`data/raw/lichess/lichess_2024_09_first250k.pgn`,
`data/interim/game_records_2024_09_250k_v1.parquet`,
`data/processed/splits_2024_09_250k_v1.json`,
`data/processed/player_metadata_2024_09_250k_v1.parquet`,
`data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json`.

## 3. Files modified

- `src/chess_mhsuc/dense_move_loss.py` — added full-month mode, chunking/resume,
  time-control-aware schema, preflight, extended validation.
- `tests/test_dense_move_loss.py` — +16 tests.
- `ROADMAP.md` — 15.3C marked complete (2024-09); 2024-10 pending; next = 15.3D.
- `EXPERIMENT_LOG.md` — added EXP-041.
- `PREREGISTRATION.md` — **unchanged** (extraction design matches 15.3C-A; no
  metric/contrast/threshold change).

## 4. Files created

- `reports/dense_move_loss_2024_09_250k_v1.md` — committed aggregate report (18 §).
- `reports/phase_reports/phase_15_3c_full_dense_move_loss_extraction.md` — this report.
- `data/processed/dense_move_loss_2024_09_250k_v1.parquet` — final artifact
  (1,496,890 rows × 65 cols; **gitignored**; not staged).
- `data/processed/dense_move_loss_2024_09_250k_v1_chunks/` — 6 chunk parquets +
  `manifest.json` (**gitignored**; retained for resumability).

## 5. Tests run

- `pytest tests/test_dense_move_loss.py` → **46 passed** (30 prior + 16 new).
- Full suite `pytest` → **1,790 passed** (1,774 prior + 16), 3 pre-existing warnings.

New tests cover: full-month flag safety (refuse 2024-10 / non-depth-12 / non-600+0),
pilot-cap still refuses uncapped without the full-month flag, TimeControl parsing,
family/speed/clock-fraction/increment-buffer conventions, gross-vs-net think time
(no-increment and increment fixtures), low-clock flags, expanded-schema username
guard, chunk naming, resume game-id detection, and chunk concatenation.

## 6. Preflight command and result

```bash
caffeinate -dimsu PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn --month 2024_09 \
  --preflight --min-move-number 5 --depth 12 --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --out <tmp> --report <tmp>
```

Result: **PASS** — rows 86,977 (target 86,977), games 1,486 (target 1,486), evals
88,012 (target 88,012), 0 replay failures, 0 duplicate keys. Exact reproduction, so
the full-month code path is confirmed identical to the 15.3B pilot.

## 7. Full extraction command

```bash
caffeinate -dimsu PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn --month 2024_09 \
  --allow-full-month-2024-09 --time-control 600+0 --min-move-number 5 --depth 12 \
  --chunk-size 5000 --resume --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --chunk-dir data/processed/dense_move_loss_2024_09_250k_v1_chunks \
  --out data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --report reports/dense_move_loss_2024_09_250k_v1.md
```

The full-month flag is locked to month==2024_09, depth==12, 600+0; the CLI refuses
2024-10, any other depth, or any other time control through this path.

## 8. Artifact created

`data/processed/dense_move_loss_2024_09_250k_v1.parquet` — 1,496,890 rows × 65
columns (53 base + 12 time-control-aware fields + 2 player-hash columns; the schema
dict + hashes). 156 MB snappy parquet. Six chunk shards (each ~286–293k rows except
the final 56,432-row remainder) + `manifest.json`. All gitignored under `data/`.

## 9. Runtime and throughput

- Wall-clock 45,831.8 s (~12.7 h); engine seconds 45,380.0 s; 33.4 evals/s.
- 1,514,689 engine evals; 1,471,279 cache-reuse hits (post-move position reused as
  the next pre-move position); 7,812 terminal positions resolved without the engine.
- ~58.4 rows/game; 6 chunks at chunk_size 5,000.
- The realized rate (33.4 eps) is below the pilot's 41.7 eps — the full distribution
  includes more long, complex late-game positions than the first 1,500 games — so the
  run landed at ~12.7 h vs the ~11 h projection (still within the 15.3A band once the
  optimistic-sample caveat is applied).

## 10. Validation summary

| Check | Result |
|---|---|
| Rows | 1,496,890 |
| Unique games | 25,611 (of 25,945 accepted; 334 too short for move≥5) |
| Duplicate (game_id, ply) keys | 0 |
| Status | all `ok`; 0 eval-error, 0 replay-failure |
| Mate-band rows (flagged, excluded from headline) | 80,577 (5.4%) |
| Missing-clock rows | 0 |
| clock > 600 s rows | 132 (flagged, retained) |
| Negative think-time rows | 133 (flagged, retained) |
| ES loss range | [0.0, 0.838] |
| clipped cp loss < 0 | 0 |
| raw cp loss negative share | 0.222 (move beat prior static eval; expected) |
| Both-color ES mean (White / Black) | 0.0347 / 0.0344 (sign correct) |
| Player-hash coverage | 1.0 (1,496,890 / 1,496,890) |
| Raw-username columns | none |
| Clock buckets | under_60 46,195 / 60_180 95,862 / over_180 1,354,833 |
| Result class | WHITE_WIN 705,097 / BLACK_WIN 679,788 / DRAW 112,005 |
| Loss headline (OK, non-mate) | ES mean 0.0346, median 0.0114, p90 0.0926 |
| Large-loss | ES≥0.05 ~0.20, ES≥0.10 0.090; cp≥100 0.175, cp≥200 0.072 |

Dense yields ~18× the checkpoint low-clock observations (under_60 46,195 vs the
checkpoint layer's handful), the key payoff for the Constraint Atlas.

## 11. Time-control-aware schema additions

Added (and validated uniform for this 10+0 month): `time_control_raw` = `600+0`,
`initial_time_s` = 600, `increment_s` = 0, `time_control_family` = `no_increment`,
`speed_category` = `rapid` (estimated-duration rule, documented),
`clock_fraction` = clock_before/600 (range [0.0, 11.94] — the upper tail is the 132
malformed-clock artifacts, flagged), `increment_buffer` = null (100% null share, as
required for no-increment), `think_time_gross_s` (= `think_time_s`) and
`think_time_net_s` (= gross + increment = gross here), and the three low-clock flags
(`low_clock_absolute_flag`, `low_clock_fraction_flag`, `low_increment_buffer_flag` =
null for no-increment). These make the artifact forward-compatible with increment and
other time controls without a re-extraction.

## 12. Comparison to 15.3B pilot

| Metric | 15.3B pilot (1,500 games) | 15.3C full month (25,945 games) |
|---|---|---|
| Rows | 86,977 | 1,496,890 |
| Rows/game | 58.5 | 58.4 |
| Mate-band share | 5.6% | 5.4% |
| ES loss mean / median | 0.0347 / 0.0115 | 0.0346 / 0.0114 |
| Both-color ES (W/B) | 0.0345 / 0.0348 | 0.0347 / 0.0344 |
| Player-hash coverage | 1.0 | 1.0 |

The full-month distributions match the pilot, as expected from the exact preflight
reproduction.

## 13. Recommendation for next ticket

**15.3D — Full Dense Move-by-Move Loss Extraction Replication Month (2024-10)** —
run the same full dense extraction for 2024-10 (depth 12, chunked/resumable) before
any dense Constraint Atlas, so final atlas claims use both monthly samples (the
project's standing cross-month replication discipline). Only after 2024-10 validates
should 15.4A (CP/ES Constraint Atlas Visualization Audit) begin. (If Malachi
explicitly prefers to inspect 2024-09 visually first, 15.4A could be brought forward,
but the roadmap still needs 2024-10 for replicated claims.)

## 14. Non-claims

- This is **2024-09 only**. 2024-10 dense extraction has **not** been run.
  Cross-time-control extraction has **not** been run.
- No visual atlas was generated. No dense controlled model was run.
- No causal claim. No "low clock causes blunders." No "time pressure causes worse
  reasoning." No "Stockfish is ground truth." No "human obviousness modeled." No
  "DRAW solved." No "best predictor."
- **C4 unchanged. C3c unchanged.** No thresholds or classifications changed; the ES
  transform was reused, not refit.
