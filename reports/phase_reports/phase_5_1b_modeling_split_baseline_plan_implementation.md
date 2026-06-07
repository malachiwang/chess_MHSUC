# Phase Report: Ticket 5.1B — Modeling Split + Baseline Plan Implementation

**Labels:** ML / EVALUATION / DATA | D4 | IMPLEMENTATION
**Date:** 2026-06-07
**Status:** Complete. Split assignments and modeling plan generated.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 5.1B — Modeling Split + Baseline Plan Implementation
ML / EVALUATION / DATA | D4 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR

This ticket creates `splits.py`, which assigns each of the 2,323 unique Lichess games to train/val/test using a 70/15/15 stratified split by `game_id` (never by row), stratified on game-level `result_class`, seed 42. It also produces a modeling plan JSON documenting feature sets FS-A through FS-G, the metric policy, and the B0–B5 baseline plan. No models are trained.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/splits.py` | Created — 16 functions + CLI |
| `tests/test_splits.py` | Created — tests |
| `ROADMAP.md` | Modified — marked 5.1A and 5.1B complete |
| `reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md` | Created (this file) |

Local-only (gitignored):

| File | Description |
|------|-------------|
| `data/processed/splits_2024_09_25k_v1.json` | Game-level split assignments |
| `data/processed/modeling_plan_2024_09_25k_v1.json` | Feature sets, metric policy, baseline plan |

---

## 4. Split Policy Implemented

| Parameter | Value |
|-----------|-------|
| Split unit | `game_id` (never by row) |
| Ratio | 0.7 / 0.15 / 0.15 |
| Seed | 42 |
| Stratification | Game-level `result_class` |
| Method | Two-step `StratifiedShuffleSplit` |
| Row-level splitting | Forbidden |

**Primary training view:** `primary_numbered` — exclude `selected_position_type == 'last'`.
Produces consistent-semantics rows only (side_to_move_next always White).

---

## 5. Split Results (Broad)

Total broad games: **2,323**

| Split | Games | DRAW games | % of all games |
|-------|-------|------------|----------------|
| train | 1,626 | 77 | 70.0% |
| val | 348 | 16 | 15.0% |
| test | 349 | 17 | 15.0% |

**Primary view row counts (broad, numbered checkpoints only):**

| Split | Rows |
|-------|------|
| train | 4,344 |
| val | 931 |
| test | 930 |

---

## 6. Eval Split Inheritance Results

Total eval games: **365** (strict subset of broad games via `game_id` join)

| Split | Eval games |
|-------|-----------|
| train | 256 |
| val | 56 |
| test | 53 |

Eval experiments are **exploratory** due to small n and selection bias.

**Warnings:**

- Split 'val' has only 4 DRAW game(s) (< 8). DRAW class metrics will be very noisy.
- Split 'test' has only 1 DRAW game(s) (< 8). DRAW class metrics will be very noisy.

---

## 7. Feature Sets Defined

| ID | Name | Table | Features |
|----|------|-------|----------|
| `FS-A` | majority_prior | broad | 0 features |
| `FS-B` | rating_only | broad | 4 features |
| `FS-C` | clock_only | broad | 13 features |
| `FS-D` | position_context | broad | 5 features |
| `FS-E` | rating_clock | broad | 22 features |
| `FS-F` | eval_only | eval | 9 features |
| `FS-G` | eval_rating_clock | eval | 26 features |

---

## 8. Baseline Plan Defined

| ID | Model | Feature set | Table | Exploratory |
|----|-------|-------------|-------|-------------|
| B0 | DummyClassifier | FS-A | broad | No |
| B1 | DummyClassifier | FS-A | broad | No |
| B2 | LogisticRegression | FS-B | broad | No |
| B3 | LogisticRegression | FS-E | broad | No |
| B4 | LogisticRegression | FS-F | eval | Yes |
| B5 | LogisticRegression | FS-G | eval | Yes |

All baselines use sklearn only. LogisticRegression: max_iter=1000, solver=lbfgs.
Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed across all experiments).
GBM deferred to Phase 6. Preprocessing deferred to modeling ticket.

---

## 9. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py -v
```

---

## 10. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites | 409 | All passed (no regression) |
| `test_splits.py` | 92 | All passed |

**501 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 11. Output Artifacts Created

| File | Location | Notes |
|------|----------|-------|
| `splits_2024_09_25k_v1.json` | `data/processed/` (gitignored) | 2,323 game assignments |
| `modeling_plan_2024_09_25k_v1.json` | `data/processed/` (gitignored) | FS-A–G, metrics, B0–B5 |
| `phase_5_1b_*.md` | `reports/phase_reports/` (committed) | This report |

---

## 12. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No Parquet files created or modified.
- No CSV, model, or calibration files created.
- No split-augmented feature tables written.
- No models trained.
- Only source code, tests, ROADMAP.md, and this report are staged/committed.

---

## 13. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Preprocessing (one-hot, boolean casting) | Modeling ticket |
| Metric computation | Modeling ticket |
| Model training (B0–B5) | Phase 5.2 |
| GBM (HistGradientBoostingClassifier) | Phase 6 |
| Calibration | Phase 6.2 |
| Subgroup analysis | Phase 7 |
| 'last' checkpoint analysis | Phase 7 (time-forfeit/terminal positions) |
| XGBoost / LightGBM | Phase 6+ (GBM selection audit required) |

---

## 14. Risks / Assumptions

**R1 — DRAW class sparsity**
~16 DRAW games in each of val/test (broad). Per-class DRAW metrics will be noisy.
Eval DRAW is ~3–4 games in val/test — report eval DRAW metrics with extreme caution.

**R2 — Row-level split leakage**
`splits.py` enforces game_id-level splitting. Any code that shuffles rows is a bug.
`validate_split_assignments` errors (not warns) on any violation.

**R3 — Stratification instability**
110 DRAW games makes stratification somewhat seed-sensitive. Seed 42 is fixed.

**R4 — Duplicate checkpoint rows**
166 rows (83 games) in broad. Primary view excludes 'last' entirely — no dedup needed.
'all_checkpoints_dedup' view removes coincident 'last' rows — use this for all-checkpoint experiments.

**R5 — Single-month pilot**
Results from 2024-09 may not generalize to other months. Labeled 'pilot: 2024-09, 25k games.'

---

## 15. Whether Next Ticket Is Safe to Begin

**Yes.** Split assignments and modeling plan are stable.
Preprocessing policy and label mapping are documented.

Suggested next ticket: **Ticket 5.2A — Baseline Modeling Audit**
(define exact preprocessing steps and train B0–B5 baselines).

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/splits.py
git add tests/test_splits.py
git add ROADMAP.md
git add reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md
git commit -m "Ticket 5.1B: splits.py, <N> tests (<total> total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
