# Phase Report: Ticket 6.1B — First GBM Implementation

**Labels:** ML | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Status:** Complete. GBM models G1–G6 trained and evaluated.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 6.1B — First GBM Implementation
ML | D2 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR

This ticket creates `gbm.py`, which trains G1–G6 GBM models
(HistGradientBoostingClassifier) on the 70/15/15 train/val/test splits
from Phase 5.1B. No calibration, no model artifacts (.joblib/.pkl) saved.
Outputs: results JSON + predictions Parquet (gitignored), plus this report
(committed).

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/gbm.py` | Created — 12 functions (A–L) + CLI |
| `tests/test_gbm.py` | Created — tests |
| `ROADMAP.md` | Modified — marked 6.1A and 6.1B complete |
| `reports/phase_reports/phase_6_1b_gbm_implementation.md` | Created (this file) |

Local-only (gitignored):

| File | Description |
|------|-------------|
| `gbm_results_2024_09_25k_v1.json` | Metrics for all GBM models (JSON) |
| `gbm_predictions_2024_09_25k_v1.parquet` | Per-row predictions (Parquet) |

---

## 4. Model Configuration

| Parameter | Value |
|-----------|-------|
| Model class | `HistGradientBoostingClassifier` |
| `max_iter` | 300 |
| `learning_rate` | 0.05 |
| `max_leaf_nodes` | 31 |
| `min_samples_leaf` | 20 |
| `l2_regularization` | 0.1 |
| `random_state` | 42 |
| String categoricals | Dropped (`selected_position_type`, `phase`) |
| `eval_mate_abs` | Native NaN (no imputation required) |

Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed).
Training view: `primary_numbered` (exclude `selected_position_type == 'last'`).

---

## 5. GBM Results Summary

### Broad models

| ID | Model | FS | Expl | Diag | Val acc | Val log_loss | Val brier | Test acc |
|----|-------|----|------|------|---------|--------------|-----------|----------|
| G1 | HistGBM | FS-B | N | N | 0.4662 | 1.4178 | 0.7508 | 0.5000 |
| G2 | HistGBM | FS-E | N | N | 0.4995 | 1.2326 | 0.6817 | 0.5129 |
| G3 | HistGBM | FS-C | N | Y | 0.4930 | 0.9861 | 0.6076 | 0.4452 |
| G4 | HistGBM | FS-D | N | Y | 0.4780 | 0.8812 | 0.5563 | 0.4828 |

### Eval models (exploratory)

| ID | Model | FS | Expl | Diag | Val acc | Val log_loss | Val brier | Test acc |
|----|-------|----|------|------|---------|--------------|-----------|----------|
| G5 | HistGBM | FS-F | Y | N | 0.5102 | 1.1854 | 0.6321 | 0.6429 |
| G6 | HistGBM | FS-G | Y | N | 0.5986 | 1.6409 | 0.6331 | 0.7071 |

---

## 6. Output Artifacts Created

| File | Location | Notes |
|------|----------|-------|
| `gbm_results_2024_09_25k_v1.json` | `data/processed/` (gitignored) | All metrics |
| `gbm_predictions_2024_09_25k_v1.parquet` | `data/processed/` (gitignored) | Per-row predictions |
| `phase_6_1b_*.md` | `reports/phase_reports/` (committed) | This report |

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py -v
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through baselines) | 607 | All passed (no regression) |
| `test_gbm.py` | 113 | All passed |

**720 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibration performed.
- No data files staged.
- Only source code, tests, ROADMAP.md, and this report are staged/committed.

---

## 10. Risks / Assumptions

**R1 — DRAW class sparsity**
Broad val DRAW support ~59 rows (6.3%). Eval val/test DRAW very sparse (~14/2).
All eval models are flagged exploratory.

**R2 — String categorical dropping**
`selected_position_type` and `phase` dropped from feature sets that include them.
Their numeric equivalents (`checkpoint_index`, `phase_index`) are retained.

**R3 — eval_mate_abs native NaN**
93.6% of eval_mate_abs values are null. HistGBM handles NaN natively;
no imputation needed (unlike baselines which used SimpleImputer).

**R4 — No hyperparameter tuning**
GBM_PARAMS are fixed from audit 6.1A. No grid search, no early stopping.

---

## 11. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Calibration | Phase 6.2 |
| Hyperparameter tuning | Phase 6+ |
| Subgroup analysis | Phase 7 |
| Model artifact persistence (.joblib) | Not required for this ticket |
| XGBoost / LightGBM | Phase 6+ (requires audit) |

---

## 12. Whether Next Ticket Is Safe to Begin

**Yes.** GBM metrics establish comparison vs baselines for Phase 6.2 work.

Suggested next ticket: **Phase 6.2A — Calibration Audit**.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/gbm.py
git add tests/test_gbm.py
git add ROADMAP.md
git add reports/phase_reports/phase_6_1b_gbm_implementation.md
git commit -m "Ticket 6.1B: gbm.py, <N> tests (<total> total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
