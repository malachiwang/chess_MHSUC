# Phase Report: Ticket 4.1B — Feature Dataset Assessment

**Labels:** DATA / ML / ANALYSIS | D4 | IMPLEMENTATION
**Date:** 2026-06-06
**Status:** Complete. Assessment generated from real feature tables.
**Version tag:** `2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 4.1B — Feature Dataset Assessment Implementation
DATA / ML / ANALYSIS | D4 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR Summary

This ticket creates `assess_dataset.py`, a reproducible assessment module that
reads the Phase 3.2B feature Parquet tables and produces a Markdown report
(this file) plus a JSON sidecar. No modeling, splitting, or transformation
is performed — only inspection. The Markdown report IS the implementation report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/assess_dataset.py` | Created |
| `tests/test_assess_dataset.py` | Created |
| `ROADMAP.md` | Modified — marked 4.1A and 4.1B complete |

No files under `data/` were staged.

---

## 4. Dataset Overview

| Table | Rows | Games | Columns |
|-------|------|-------|---------|
| Broad | 8,528 | 2,323 | 40 |
| Eval  | 1,168 | 365 | 40 |

Version tag: `2024_09_25k_v1`
Assessment timestamp: `2026-06-06T23:23:22.086596+00:00`

---

## 5. Target Distribution

### Broad table (8,528 rows)

| result_class | count | % |
|--------------|-------|---|
| WHITE_WIN | 3,985 | 46.73% |
| BLACK_WIN | 4,046 | 47.44% |
| DRAW | 497 | 5.83% |

### Eval table (1,168 rows)

| result_class | count | % |
|--------------|-------|---|
| WHITE_WIN | 572 | 48.97% |
| BLACK_WIN | 519 | 44.43% |
| DRAW | 77 | 6.59% |

**Key findings:**
- Three-class target confirmed present in both tables.
- DRAW class is minority class (~5-7%); majority baseline will have poor recall on draws.
- Class distribution broadly consistent between broad and eval subsets.

---

## 6. Rating Distribution (broad)

| Column | Min | Max | Mean | Median | Std |
|--------|-----|-----|------|--------|-----|
| white_elo | 514.0 | 2677.0 | 1557.1 | 1572.0 | 357.6 |
| black_elo | 538.0 | 2652.0 | 1560.4 | 1581.0 | 357.0 |
| avg_elo | 567.5 | 2653.0 | 1558.7 | 1576.0 | 353.2 |
| elo_diff | -1192.0 | 1192.0 | -3.3 | -1.0 | 106.9 |

**Eval subset selection bias:** avg_elo broad = 1558.7093105065667, eval = 1578.5359589041095 (Δ = +19.8 Elo).
Higher-rated games slightly more likely to have eval annotations.

---

## 7. Clock Distribution (broad)

| Column | Min | Max | Mean | Median |
|--------|-----|-----|------|--------|
| white_clock_s (raw) | 0.0 | 1113.0 | 402.986 | 438.0 |
| black_clock_s (raw) | 0.0 | 7139.0 | 403.376 | 438.0 |
| white_clock_frac | 0.0 | 1.0 | 0.671 | 0.73 |
| black_clock_frac | 0.0 | 1.0 | 0.671 | 0.73 |
| clock_diff_frac | -0.9983333333333334 | 0.7233333333333334 | 0.0 | 0.002 |

| Low-time flag | N true | % |
|---------------|--------|---|
| white_low_60 | 283 | 3.32% |
| black_low_60 | 307 | 3.6% |
| white_low_30 | 173 | 2.03% |
| black_low_30 | 204 | 2.39% |
| white_low_10 | 93 | 1.09% |
| black_low_10 | 125 | 1.47% |

Clock anomalies (clock_s > 600): 7

**Key findings:**
- Low-time flags show strong asymmetric signal between WHITE_WIN and BLACK_WIN.
- white_low_60 and black_low_60 are expected to be useful features.

---

## 8. Eval Distribution (broad, eval-rows only)

Eval coverage: 13.7% (1,168 / 8,528 rows)

| eval_cp_clipped bin | N | % of eval rows |
|---------------------|---|----------------|
| le_neg500 | 225 | 19.26% |
| neg500_to_neg200 | 120 | 10.27% |
| neg200_to_neg50 | 81 | 6.93% |
| neg50_to_50 | 202 | 17.29% |
| 50_to_200 | 129 | 11.04% |
| 200_to_500 | 181 | 15.5% |
| ge_500 | 230 | 19.69% |

Mate-eval rows (is_mate_eval=True): 122

---

## 9. Checkpoint Distribution (broad)

| Checkpoint | Rows | Games | % of rows |
|------------|------|-------|-----------|
| move_10 | 2,323 | 2,323 | 27.24% |
| move_20 | 1,882 | 1,882 | 22.07% |
| move_30 | 1,266 | 1,266 | 14.85% |
| move_40 | 734 | 734 | 8.61% |
| last | 2,323 | 2,323 | 27.24% |

Duplicate ply checkpoint rows: 166 (83 games × 2 rows)

---

## 10. Slice Distributions (broad)

| Slice column | N true | % |
|--------------|--------|---|
| is_time_forfeit | 1,051 | 12.32% |
| has_eval | 1,168 | 13.7% |

| Termination | Count | % |
|-------------|-------|---|
| Normal | 7,477 | 87.68% |
| Time forfeit | 1,051 | 12.32% |

---

## 11. Leakage Safety

| Table | Leakage safe | Forbidden cols found |
|-------|-------------|----------------------|
| Broad | True | [] |
| Eval  | True | [] |

result_class present (label, not feature): True
termination present (slice, not feature): True
game_id present (split key, not feature): True

---

## 12. Broad vs. Eval Comparison

| Checkpoint | Broad rows | Eval rows | Eval coverage % |
|------------|------------|-----------|-----------------|
| move_10 | 2,323 | 365 | 15.71% |
| move_20 | 1,882 | 294 | 15.62% |
| move_30 | 1,266 | 182 | 14.38% |
| move_40 | 734 | 91 | 12.4% |
| last | 2,323 | 236 | 10.16% |

avg_elo broad: 1558.7093105065667 | avg_elo eval: 1578.5359589041095 (Δ = +19.8)

---

## 13. Baseline Readiness

- `no_leakage_cols_broad`: PASS
- `no_leakage_cols_eval`: PASS
- `broad_rows_sufficient`: PASS
- `eval_rows_sufficient`: PASS
- `game_count_sufficient`: PASS
- `draw_class_present`: PASS
- `eval_coverage_nonzero`: PASS
- `no_unexpected_nulls_in_broad`: PASS

**Overall: ALL PASS**

---

## 14. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py -v
```

---

## 15. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan, parse_pgn, run_parser, cleaning, features) | 277 | All passed (no regression) |
| `test_assess_dataset.py` | 45 | All passed |

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 16. Data Safety Confirmation

- `git status` shows only source files and this report as untracked/modified.
- `git status --ignored` confirms `data/` is entirely gitignored.
- No data files staged.
- No CSV files created.
- No model files created.

---

## 17. Risks / Assumptions

**R1 — Eval subset selection bias**
avg_elo in eval subset is +19.8 Elo higher than broad. Models trained on
eval-gated data may generalize less well to lower-rated games.

**R2 — DRAW class minority**
DRAW is ~5-7% of games. Majority-class baseline achieves ~47% accuracy by
predicting WHITE_WIN, but with 0% recall on DRAW. Metrics beyond accuracy required.

**R3 — Duplicate ply checkpoint rows**
166 rows flagged by duplicate_ply_checkpoint. Training code must deduplicate
(recommend: keep numbered checkpoint, drop coincident 'last') before model training.

**R4 — Clock anomaly rows**
7 rows have raw clock_s > 600. Capped features are bounded,
but raw clock values are unreliable for these rows.

**R5 — Move_40 game coverage**
Only a subset of games reach move_40. Phase-stratified analysis required to
avoid confounding checkpoint depth with game characteristics.

---

## 18. Whether Next Ticket Is Safe to Begin

**Yes.**
Feature tables verified. Dataset quality sufficient for baseline modeling.

Suggested next ticket: **Ticket 5.1A — Modeling Split and Baseline Audit**
(define game-level train/val/test split and baseline model design).

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/assess_dataset.py
git add tests/test_assess_dataset.py
git add ROADMAP.md
git add reports/phase_reports/phase_4_1b_feature_dataset_assessment.md
git commit -m "Ticket 4.1B: assess_dataset.py, 45 tests (322 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
