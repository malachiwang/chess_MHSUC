# Phase 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction

**Ticket:** 16.1C — Full Matched-Size 3+0 / 5+0 Dense Extraction (extraction only)
**Engine:** Stockfish 18 @ depth 12 (`/opt/homebrew/bin/stockfish`)
**ES transform:** `next_move_expected_score_transform_2024_09_2024_10_v1.json` (scale 348.41, reused — NOT refit)

> **Matched-size dense extraction artifacts. NOT a final cross-time-control analysis.
> No causal claims. No cross-control modeling, no atlas figures, no Phase 16
> statistical claims here. These artifacts are inputs for 16.2. Cross-control
> comparisons must use within-control rating quantiles; rating pools are not
> directly comparable across controls.**

## 1. Executive summary

Full matched-size dense per-ply next-move loss extraction for the Phase 16 no-increment
first wave — **3+0 (180+0)** and **5+0 (300+0)**, both anchor months (2024-09, 2024-10),
depth 12, both colors, `move_number >= 5`, chunked/resumable, caffeinated. Each of the
four extractions used a **matched accepted-game cap of 24,000 games** (the value
recommended by the ticket and 16.1B; close to the 2024-10 10+0 anchor of 24,552 games).

All four artifacts passed validation: **0 duplicate keys, 0 replay failures, 0 eval
errors, 0 missing-clock rows, both mover colors present, 1.0 player-hash coverage, no
username columns, time-control fields correct, `clock_fraction` computed off
`initial_time_s` (verified exact).** Existing 10+0 anchor artifacts and pilot artifacts
were not touched. All dense artifacts are gitignored under `data/` and not staged.

Descriptive headline (NOT a claim): the **time-forfeit (flagging) rate is a clean monotone
dose-response in base time** — 3+0 ≈ 36–37% > 5+0 ≈ 28% > 10+0 ≈ 13.7% — while **average
next-move move-quality loss is similar across controls** (ES mean ~0.034–0.035 everywhere).
Rating pools differ by control (3+0 median ~1.79k vs 5+0/10+0 median ~1.59k), confirming
within-control rating quantiles are mandatory for any later comparison.

## 2. Files inspected

- `ROADMAP.md`, `EXPERIMENT_LOG.md`, `PREREGISTRATION.md` (governance).
- `reports/phase_reports/phase_16_1a_time_control_selection_feasibility_audit.md` (availability: 3+0 52,293/51,751; 5+0 33,547/33,661 — both > 24k both months).
- `reports/phase_reports/phase_16_1b_cross_time_control_pilot_dense_extraction.md` (pilot CLI + cap recommendation).
- `reports/dense_move_loss_pilot_2024_09_3plus0_v1.md` and the three other 16.1B pilot reports.
- `reports/dense_move_loss_2024_09_250k_v1.md`, `reports/dense_move_loss_2024_10_250k_v1.md`, and the 15.3C/15.3D phase reports (10+0 anchors).
- `src/chess_mhsuc/dense_move_loss.py`, `tests/test_dense_move_loss.py`.
- `src/chess_mhsuc/dense_constraint_atlas.py`, `src/chess_mhsuc/dense_controlled_model.py` (downstream schema compatibility).

## 3. Files created

Extraction artifacts (gitignored under `data/`, not staged):

```
data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet   (143M)
data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet   (141M)
data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet   (143M)
data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet   (141M)
```

Chunk directories (gitignored): `dense_move_loss_2024_{09,10}_{3,5}plus0_24k_v1_chunks/` (5 chunks + `manifest.json` each).

Extraction reports (CLI-generated):

```
reports/dense_move_loss_2024_09_3plus0_24k_v1.md
reports/dense_move_loss_2024_09_5plus0_24k_v1.md
reports/dense_move_loss_2024_10_3plus0_24k_v1.md
reports/dense_move_loss_2024_10_5plus0_24k_v1.md
```

Phase report: `reports/phase_reports/phase_16_1c_full_matched_size_3plus0_5plus0_dense_extraction.md` (this file).

## 4. Files modified

- `src/chess_mhsuc/dense_move_loss.py` — see §5.
- `tests/test_dense_move_loss.py` — see §5.
- `ROADMAP.md` — 16.1C marked complete; next ticket 16.2A.
- `EXPERIMENT_LOG.md` — EXP-052 added.
- `PREREGISTRATION.md` — UNCHANGED (no preregistered design change).

## 5. Code changes

A real pilot-to-full gap was found and fixed: the chunked/resumable runner
(`run_full_month_chunked`) was reachable only via `--allow-full-month-*`, which are
**locked to 600+0**. A 24,000-game non-anchor run would otherwise have fallen through to
the **non-resumable** `run_pilot` — unacceptable for ~8.5h-per-run extractions with no
crash recovery. The change is minimal and reuses the already-tested chunked runner:

1. **New `main` routing branch** — non-anchor time control with cap > `PILOT_HARD_MAX_GAMES`
   (still gated by the existing `--pilot-override-allow-large` safety flag) routes through
   `run_full_month_chunked`. The chunk dir is auto-derived as `<out>_chunks`.
   `build_accepted_meta_from_raw` already caps the accepted set to `--max-accepted-games`,
   so the runner processes exactly the matched set (no internal game cap needed).
2. **New `render_matched_size_report`** — a control-aware, extraction-only report renderer.
   (The full-month renderer hardcodes "Full 10+0 / Ticket 15.3C / 600+0 / 1.0 expected for
   10+0"; the pilot renderer hardcodes "pilot only" + a full-run extrapolation block —
   neither fits a capped matched-size non-anchor run.)
3. **3 new tests** (68 module tests total): renderer extraction-only framing and no "10+0"
   leakage; gate refuses a >cap non-anchor run without override; with override it routes
   into the chunked path. No edits to `dense_constraint_atlas.py` / `dense_controlled_model.py`.

The shared `extract_game_rows` / `finalize_frame` / `summarize` path is unchanged, so the
schema is byte-for-byte the same family as the 10+0 anchors (65 columns).

## 6. Tests run

```
PYTHONPATH=src .venv/bin/pytest tests/test_dense_move_loss.py   -> 68 passed
PYTHONPATH=src .venv/bin/pytest                                  -> 1860 passed, 3 warnings
```

(Run before extraction. The 3 warnings are pre-existing sklearn `y_pred` warnings in
unrelated modeling tests.)

## 7. Extraction commands

A single caffeinated sequential script (`/tmp/chess_mhsuc_run_16_1c.sh`, outside git) ran
all four extractions in order. Representative invocation (2024-09 3+0):

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn \
  --month 2024_09 --time-control 180+0 \
  --allow-time-control-pilot --max-accepted-games 24000 --pilot-override-allow-large \
  --min-move-number 5 --depth 12 --resume \
  --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --out data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet \
  --report reports/dense_move_loss_2024_09_3plus0_24k_v1.md
```

(+ `300+0`, and the two 2024-10 controls with the matching month raw cache / player
metadata.) Run under `caffeinate -dimsu`. Note: `--allow-time-control-pilot` is the
existing safety-gate name; here it gates a finite-cap matched-size run (24,000), not a
1,500-game pilot. The gate's behavior is still **finite-cap safety**
(`--pilot-override-allow-large` is required above the 2,000 hard cap); the name is
historical, not a behavior limit.

## 8. Runtime and throughput

Campaign start Thu 2026-06-18 21:41 EDT → end Sat 2026-06-20 06:47 EDT (~33.1h wall total,
sequential). No interruptions; `--resume` available but never needed (0 games skipped on
resume).

| Month | Control | Runtime | Evals | Throughput |
|---|---|---|---|---|
| 2024-09 | 3+0 | 30,757 s (~8.5h) | 1,512,713 | 49.6 ev/s |
| 2024-09 | 5+0 | 28,767 s (~8.0h) | 1,454,997 | 51.0 ev/s |
| 2024-10 | 3+0 | 30,875 s (~8.6h) | 1,508,508 | 49.2 ev/s |
| 2024-10 | 5+0 | 28,738 s (~8.0h) | 1,454,106 | 51.0 ev/s |

Throughput is consistent (49–51 ev/s); the 16.1B September 5+0 slow-pilot anomaly did not
recur. 3+0 runs are slightly slower (more evals/game).

## 9. Artifact validation

All four pass. `status` is 100% `ok`; mate-band rows are flagged and excluded from the
headline metric.

| Artifact | Rows | Games | Dups | Replay fail | Eval err | Mate-band | Hash cov | Username cols |
|---|---|---|---|---|---|---|---|---|
| 09 3+0 | 1,495,648 | 23,708 | 0 | 0 | 0 | 73,475 | 1.0 | none |
| 09 5+0 | 1,437,932 | 23,767 | 0 | 0 | 0 | 70,639 | 1.0 | none |
| 10 3+0 | 1,491,120 | 23,739 | 0 | 0 | 0 | 70,302 | 1.0 | none |
| 10 5+0 | 1,437,116 | 23,744 | 0 | 0 | 0 | 72,697 | 1.0 | none |

Required-column check: all present (`game_id, ply, mover_color, clock_fraction,
initial_time_s, increment_s, time_control_raw, time_control_family, speed_category,
expected_score_loss, cp_loss_clipped, is_mate_band, status, termination, is_time_forfeit,
result_class, mover_elo, mover_player_hash`, …). Schema = 65 columns, identical family to
the 10+0 anchors.

Time-control schema (all rows per artifact):

| Artifact | time_control_raw | initial_time_s | increment_s | family | speed | cf=clk/init exact |
|---|---|---|---|---|---|---|
| 3+0 (both) | 180+0 | 180 | 0 | no_increment | blitz | yes (0 err) |
| 5+0 (both) | 300+0 | 300 | 0 | no_increment | blitz | yes (0 err) |

`expected_score_loss` bounded in [0, ~0.8]; `cp_loss_clipped` nonnegative. Both mover
colors present in every artifact.

## 10. Matched-size denominator summary

Accepted-game cap = **24,000** per month/control (header-derived acceptance:
TimeControl match + both Elos + decisive/draw result + termination tag). `games_accepted`
= 24,000 in every manifest; `games_skipped_resume` = 0.

| Artifact | Accepted (cap) | Games with rows | Games yielding 0 rows | Rows/game |
|---|---|---|---|---|
| 09 3+0 | 24,000 | 23,708 | 292 | 63.1 |
| 09 5+0 | 24,000 | 23,767 | 233 | 60.5 |
| 10 3+0 | 24,000 | 23,739 | 261 | 62.8 |
| 10 5+0 | 24,000 | 23,744 | 256 | 60.5 |

The ~230–290 games per artifact that contributed no rows are very short games (all plies
below `move_number >= 5`); this is expected behavior and identical in kind to the 10+0
anchors. Cap not exceeded; not all available 3+0/5+0 games were extracted.

## 11. Clock and clock-fraction diagnostics

`clock_fraction = clock_before_s / initial_time_s` (verified max abs error 0.0 — uses
`initial_time_s`, not a hardcoded 600). Missing-clock rows = 0 in all four. Anomalies are
tiny and flagged (not dropped).

| Artifact | cf min | cf p10 | cf p50 | cf p90 | cf max | clock>start | neg think-time |
|---|---|---|---|---|---|---|---|
| 09 3+0 | 0.0 | 0.139 | 0.650 | 0.961 | 6.65 | 41 | 114 |
| 09 5+0 | 0.0 | 0.193 | 0.700 | 0.960 | 4.05 | 27 | 145 |
| 10 3+0 | 0.0 | 0.133 | 0.650 | 0.961 | 6.24 | 6 | 82 |
| 10 5+0 | 0.0 | 0.193 | 0.697 | 0.960 | 3.30 | 62 | 165 |

clock_fraction can slightly exceed 1.0 (clock berserk/reconstruction edge cases, flagged);
counts are negligible (<65/1.5M). The cross-control clock axis for 16.2 is `clock_fraction`
(comparable across controls), not absolute seconds.

## 12. Rating quantile diagnostics

Mover-Elo summary (NOT comparable across controls — within-control quantiles mandatory):

| Artifact | min | p25 | p50 | p75 | max |
|---|---|---|---|---|---|
| 09 3+0 | 400 | 1553 | 1794 | 2000 | 3042 |
| 09 5+0 | 411 | 1332 | 1587 | 1828 | 3034 |
| 10 3+0 | 400 | 1562 | 1802 | 2003 | 3005 |
| 10 5+0 | 400 | 1314 | 1585 | 1823 | 3006 |
| 09 10+0 (anchor) | 400 | 1326 | 1599 | 1840 | 2709 |
| 10 10+0 (anchor) | 400 | 1337 | 1594 | 1828 | 2717 |

3+0 pools are notably higher-rated (median ~1.79–1.80k) than 5+0 (~1.585k) and 10+0
(~1.595k). 5+0 pools are close to 10+0 but not identical. This re-confirms the 16.1A caveat:
**a 1600 in blitz ≠ a 1600 in rapid**; cross-control comparison must use within-control
rating quantiles (cutpoints to be defined in 16.2A).

## 13. Termination-channel diagnostics

| Artifact | Time-forfeit rate | Board-decided rate | TF rows | Normal rows |
|---|---|---|---|---|
| 09 3+0 | 0.361 | 0.639 | 540,075 | 955,573 |
| 09 5+0 | 0.280 | 0.720 | 402,646 | 1,035,286 |
| 10 3+0 | 0.371 | 0.629 | 553,539 | 937,581 |
| 10 5+0 | 0.281 | 0.719 | 404,270 | 1,032,846 |
| 09 10+0 (anchor) | 0.137 | 0.863 | — | — |
| 10 10+0 (anchor) | 0.137 | 0.863 | — | — |

Strong, month-replicated **monotone termination-channel dose-response in base time**:
3+0 (~36–37%) > 5+0 (~28%) > 10+0 (~13.7%). Result-class mix is balanced (White/Black wins
near-symmetric; draws ~6.5–7%). Descriptive only — see §17.

## 14. Move-quality metric diagnostics

Headline = expected-score loss (mover perspective), OK ∧ non-mate-band rows.

| Artifact | ES n | ES mean | ES median | ES p75 | ES p90 | ES≥0.05 | ES≥0.10 |
|---|---|---|---|---|---|---|---|
| 09 3+0 | 1,422,173 | 0.0338 | 0.0113 | 0.038 | 0.090 | 0.195 | 0.0865 |
| 09 5+0 | 1,367,293 | 0.0349 | 0.0117 | 0.040 | 0.093 | 0.203 | 0.0911 |
| 10 3+0 | 1,420,818 | 0.0336 | 0.0112 | 0.038 | 0.090 | 0.196 | 0.0863 |
| 10 5+0 | 1,364,419 | 0.0352 | 0.0119 | 0.040 | 0.094 | 0.205 | 0.0920 |

Clipped CP loss (secondary):

| Artifact | mean | median | p90 | cp≥100 | cp≥200 | raw-cp neg share |
|---|---|---|---|---|---|---|
| 09 3+0 | 57.1 | 20.0 | 152 | 0.167 | 0.068 | 0.211 |
| 09 5+0 | 59.1 | 21.0 | 157 | 0.175 | 0.072 | 0.208 |
| 10 3+0 | 56.6 | 20.0 | 151 | 0.166 | 0.067 | 0.212 |
| 10 5+0 | 59.7 | 21.0 | 159 | 0.177 | 0.073 | 0.207 |

Both metrics are tightly month-replicated and close across controls (5+0 marginally higher
than 3+0). The raw-cp negative share (~0.21) is expected (actual move beats the prior
static eval).

## 15. Comparison to 10+0 anchor readiness

| Quantity | 3+0 (09/10) | 5+0 (09/10) | 10+0 anchor (09/10) |
|---|---|---|---|
| Rows/game | 63.1 / 62.8 | 60.5 / 60.5 | 58.4 / 58.5 |
| ES mean | 0.0338 / 0.0336 | 0.0349 / 0.0352 | 0.0346 / 0.0346 |
| ES median | 0.0113 / 0.0112 | 0.0117 / 0.0119 | 0.0114 / 0.0114 |
| ES p90 | 0.090 / 0.090 | 0.093 / 0.094 | 0.0926 / 0.0926 |
| Time-forfeit rate | 0.361 / 0.371 | 0.280 / 0.281 | 0.137 / 0.137 |
| Mover-Elo median | 1794 / 1802 | 1587 / 1585 | 1599 / 1594 |
| clock_fraction range | [0, ~6.7] | [0, ~4.0] | [0, ~11.9] |

Readiness summary: all three no-increment controls now have full, schema-identical, depth-12
dense artifacts on a matched 24k-game footing, with the same reused ES transform. The
**flagging channel separates strongly by base time** while **board-move quality is roughly
flat** — the same qualitative split seen in the 16.1B pilots, now at full matched size.
Rating-pool differences (esp. higher-rated 3+0) make within-control quantiles a hard
requirement for 16.2.

## 16. Data safety and privacy

- Raw PGNs untouched (read-only). Existing 10+0 dense artifacts untouched (mtimes Jun 16/17).
  16.1B pilot artifacts untouched.
- All four new artifacts + chunk dirs are gitignored (`.gitignore:8 data/`); nothing staged.
- No username columns in any artifact; 1.0 one-way `mover_player_hash` coverage; no raw
  usernames written anywhere.
- ES transform JSON not modified, not refit.

## 17. Non-claims

- **Extraction-only.** These are inputs for 16.2, not a Phase 16 result. No cross-control
  modeling, atlas figures, or statistical claims are made here.
- The termination-channel dose-response (3+0 flags more than 5+0 more than 10+0) is
  **descriptive**, NOT causal. This is NOT "faster time controls cause worse chess," NOT
  "time pressure causes worse reasoning," NOT "low clock causes blunders."
- Rating pools are **not directly comparable** across controls; use within-control rating
  quantiles. `clock_fraction` is the cross-control clock axis.
- Stockfish eval is objective context, **not absolute ground truth**.
- No increment controls, no 1+0 bullet, no 10+5/15+10, no sharpness joins, no MultiPV here.
- Sharpness moderation is neither confirmed nor disproven by this ticket.

## 18. Recommendation for next ticket

**16.2A — Cross-Time-Control Move-Quality Atlas / Modeling Audit.** Design (do not yet
implement) the cross-control comparison: within-control rating quantile cutpoints,
`clock_fraction`-based clock axis, board-decided-only vs all-games handling, eval-band
conditioning (the dominant move-quality factor at 10+0), and the descriptive-vs-controlled
plan. Do not jump to 16.2B implementation or Phase 17.
