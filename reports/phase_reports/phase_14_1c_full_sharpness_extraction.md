# Phase 14.1C — Full Sharpness Extraction

**Labels:** IMPLEMENTATION / EXTRACTION (Sharpness arc, C3)
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Ran the full MultiPV-5 depth-12 sharpness extraction over **both 10+0 months** and
generated gitignored artifacts + committed reports. Extraction was **clean and the
candidate value-fragility features are strikingly stable across months**: 2024-09
**64,371/64,371 OK**, 2024-10 **61,868/61,868 OK**; FEN round-trip **1.0** and
all-candidates-legal **1.0** in both; `sharp_value_fragility_v1` base rate **0.1417 /
0.1407** (matching the 14.1B pilot's 0.142). **Primary v1 = objective value fragility**;
surface tags / surface-bait remain **exploratory diagnostics, explicitly NOT human
obviousness** (deferred Tier B). **No sharpness moderation model was run and no sharpness
result is claimed.** Predictive/descriptive only; MultiPV fixed-depth approximates
narrowness, not absolute ground truth.

## 2. Files created

| File | Content |
|---|---|
| `reports/multipv_sharpness_2024_09_250k_v1.md` | 2024-09 month extraction report (13 sections) |
| `reports/multipv_sharpness_2024_10_250k_v1.md` | 2024-10 month extraction report |
| `reports/multipv_sharpness_combined.md` | Combined cross-month report (13 sections) |
| `reports/phase_reports/phase_14_1c_full_sharpness_extraction.md` | This report |
| `data/processed/multipv_sharpness_2024_09_250k_v1.parquet` | **gitignored** full artifact (64,371 × 140) |
| `data/processed/multipv_sharpness_2024_10_250k_v1.parquet` | **gitignored** full artifact (61,868 × 140) |

## 3. Files modified

| File | Change |
|---|---|
| `src/chess_mhsuc/multipv_sharpness.py` | Added `--full` (all OK rows, single depth pass), `--combined` (render from extracted artifacts, no engine), `--report-only` (re-render a month report from a saved artifact, no engine); `full_summary`, `render_month_full_report`, `render_combined_full_report`; rounded report medians; NaN-safe runtime cells. Pilot behavior preserved. |
| `tests/test_multipv_sharpness.py` | +2 tests (full-summary + combined-report rendering) |
| `ROADMAP.md` | 14.1C done; pointer → 14.2A |
| `EXPERIMENT_LOG.md` | EXP-032 added |

No edits to `stockfish_eval.py` / `next_move_loss.py` (helpers imported, reused). No new
dependencies. **Existing next-move-loss artifacts not modified.**

## 4. Commands run

```bash
# both months (background), then the combined report:
python -m chess_mhsuc.multipv_sharpness --input next_move_loss_2024_09… \
  --output multipv_sharpness_2024_09_250k_v1.parquet --report …_2024_09….md \
  --version-tag 2024_09_250k_v1 --multipv-k 5 --depth 12 --seed 42 --full --overwrite
# (analogous for 2024_10)
python -m chess_mhsuc.multipv_sharpness --combined \
  --input multipv_sharpness_2024_09….parquet --input multipv_sharpness_2024_10….parquet \
  --report reports/multipv_sharpness_combined.md --overwrite
# month reports later re-rendered cleanly from the saved artifacts (no engine):
python -m chess_mhsuc.multipv_sharpness --report-only --input multipv_sharpness_<m>….parquet …
```

## 5. Tests run

- `tests/test_multipv_sharpness.py`: **24 passed**.
- Full suite: **1,729 passed** (was 1,727; +2), 0 regressions.

## 6. Extraction runtime

- **Engine compute rate (representative): ~100 ms/pos** at MultiPV-5 depth-12 (14.1B pilot
  ~106 ms/pos; a bounded mid-run probe measured ~100 ms/pos).
- **Raw wall-clock was heavily inflated by system sleep.** The job ran on battery overnight;
  `pmset` confirmed repeated `Clamshell Sleep` / `Maintenance Sleep` cycles (e.g. a 63-min
  sleep at 07:10), which **suspended** the process. 2024-09's recorded wall-clock (737 min)
  therefore reflects mostly suspended time, **not** compute — the awake rate is ~100 ms/pos
  (≈ 107 min of actual compute for 64,371 rows). 2024-10 ran largely awake during the day.
- Net: at ~100 ms/pos the two months are ~107 + ~103 ≈ **~3.5 h of awake compute** — matching
  the 14.1B projection; the calendar elapsed (≈15 h) is an artifact of overnight suspension,
  not engine cost. (Operational note for future long runs: keep the machine plugged in / awake.)

## 7. Output artifact status

Both `data/processed/multipv_sharpness_{2024_09,2024_10}_250k_v1.parquet` written and
**gitignored** (`git check-ignore` confirms the `data/` rule). One row per checkpoint, 140
columns. **No raw PGN text, usernames, or player hashes** (player hashes are joined later
from `player_metadata`, not duplicated). 10.5 MB / 9.7 MB.

## 8. Validation summary

| Check | 2024-09 | 2024-10 |
|---|---|---|
| Status all `ok` | 64,371 / 64,371 | 61,868 / 61,868 |
| Non-mate / mate-band | 61,956 / 2,415 | 59,625 / 2,243 |
| FEN round-trip match | 1.0 | 1.0 |
| All candidates legal | 1.0 | 1.0 |
| Median MultiPV count | 5 | 5 |
| Share with < K legal moves | 0.059 | 0.058 |
| Top-1 vs stored `pre_sf_eval_cp` \|Δcp\| (median / p90) | 14 / 49 | 14 / 49 |
| Key-feature nulls (OK rows) | only `best_second_gap_es` (617) | only `best_second_gap_es` (616) |

**Null note:** `best_second_gap_es` is null exactly for the **single-legal-move positions**
(617 / 616 rows with `multipv_count == 1` — forced/near-mate positions where no second move
exists). This is expected and correct, not a defect; `n_good_*`, `worst_top5_loss_es`, and
`sharp_value_fragility_v1` have **zero nulls**.

## 9. Feature distribution summary (non-mate)

| Quantity | 2024-09 | 2024-10 |
|---|---|---|
| `sharp_value_fragility_v1` rate | 0.1417 | 0.1407 |
| `_relaxed` / `_strict` rate | 0.0817 / 0.0732 | 0.0836 / 0.0744 |
| median best→second ES gap | 0.0126 | 0.0124 |
| median `n_good_10es` | 5 | 5 |
| median `worst_top5_loss_es` | 0.0463 | 0.0465 |
| median legal-move count | 34 | 34 |
| `surface_bait_10es` / `_20es` rate | 0.022 / 0.009 | 0.024 / 0.010 |
| best-move quiet / check / capture rate | 0.692 / 0.078 / 0.258 | 0.690 / 0.079 / 0.260 |

By-checkpoint `sharp_value_fragility_v1` rate (replicated trend — sharpness eases slightly
at later checkpoints): move_10 0.148 / 0.151, move_20 0.152 / 0.153, move_30 0.134 / 0.123,
move_40 0.103 / 0.102. **All candidate features — pending 14.2A; none is a sharpness claim.**

## 10. Month-to-month stability

Distributions agree closely across the two disjoint months: `sharp_value_fragility_v1` Δ =
0.0010; identical median `n_good_10es` (5), legal-move count (34); near-identical
`worst_top5_loss_es`, surface-bait, and best-move-tag rates; FEN-match and all-legal both
1.0. **No anomaly requiring investigation before 14.2A.**

## 11. Limitations and caveats

- **No sharpness result; extraction only.** No moderation model run. Not causal; no
  "degradation curve" language. **Surface tags / surface-bait are exploratory diagnostics,
  NOT human obviousness** (deferred Tier B).
- White-to-move only (even-ply checkpoints). MultiPV fixed-depth approximates narrowness, not
  ground truth; candidate ordering shifts with depth (14.1B top-1 agreement 0.64 across
  depths, while the sharpness composite agreed 0.95).
- `n_good_*` counts right-censored at K=5; viable fractions are lower bounds. Recapture and
  history-based forced-evasion deferred (checkpoint FEN lacks the opponent's last-move square).
- Candidate composites are pre-`14.2A`; the final feature/threshold/orientation are locked at
  14.2A, not here. DRAW sparse; prior trajectory deferred; Stockfish eval is objective
  context, not absolute ground truth.

## 12. Recommended next ticket

**14.2A — Sharpness Interaction Pre-Registration.** The full artifacts now exist and the
distributions are stable and non-degenerate, so 14.2A can lock the v1 sharpness
feature/threshold (e.g. train-defined `sharp_value_fragility_v1` or a train tercile of the
continuous score), the orientation (side-to-move primitive vs advantaged-player view), and
the **C3c (move-quality) primary target** with mover-player-clustered uncertainty and month
replication — **before any C3c/C3a/C3b modeling**. Prior-trajectory extraction remains an
optional follow-up, revisited at 14.2A.
