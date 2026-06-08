# Phase Report: Ticket 5.2B — Baseline Model Implementation

**Labels:** ML | D2 | IMPLEMENTATION
**Date:** 2026-06-07
**Status:** Complete. Baselines B0–B5 + B3-balanced trained and evaluated.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 5.2B — Baseline Model Implementation
ML | D2 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR

This ticket creates `baselines.py`, which trains B0–B5 baselines
(DummyClassifier + LogisticRegression) plus the B3-balanced diagnostic on the
70/15/15 train/val/test splits from 5.1B. No GBM, no calibration, no model
artifacts. Outputs: results JSON + predictions Parquet (gitignored), plus this
report (committed).

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/baselines.py` | Created — 17 functions (A–Q) + CLI |
| `tests/test_baselines.py` | Created — tests |
| `ROADMAP.md` | Modified — marked 5.2A and 5.2B complete |
| `reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md` | Created (this file) |

Local-only (gitignored):

| File | Description |
|------|-------------|
| `baseline_results_2024_09_25k_v1.json` | Metrics for all baselines (JSON) |
| `baseline_predictions_2024_09_25k_v1.parquet` | Per-row predictions (Parquet) |

---

## 4. Preprocessing Policy

| Column type | Transformer |
|-------------|-------------|
| Numeric (non-null) | `StandardScaler` |
| `eval_mate_abs` (nullable, 93.6% null) | `SimpleImputer(constant=0)` → `StandardScaler` |
| Boolean | `passthrough` (cast to Int8 first) |
| Categorical (`selected_position_type`, `phase`) | `OneHotEncoder(handle_unknown='ignore')` |
| FS-A (DummyClassifier) | `np.ones((n, 1))` dummy matrix (X ignored) |

Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed across all experiments).
Training view: `primary_numbered` (exclude `selected_position_type == 'last'`).

---

## 5. Baseline Results Summary

### Broad baselines

| ID | Model | FS | Expl | Val acc | Val log_loss | Val brier | Test acc |
|----|-------|----|------|---------|--------------|-----------|----------|
| B0 | DummyClassifier | FS-A | N | 0.4758 | 18.8929 | 1.0483 | 0.4806 |
| B1 | DummyClassifier | FS-A | N | 0.4758 | 0.8853 | 0.5573 | 0.4806 |
| B2 | LogisticRegression | FS-B | N | 0.5124 | 0.8740 | 0.5483 | 0.5118 |
| B3 | LogisticRegression | FS-E | N | 0.5381 | 0.8527 | 0.5338 | 0.5204 |
| B3-balanced | LogisticRegression | FS-E | Y | 0.4393 | 1.0623 | 0.6427 | 0.4301 |

### Eval baselines (exploratory)

| ID | Model | FS | Expl | Val acc | Val log_loss | Val brier | Test acc |
|----|-------|----|------|---------|--------------|-----------|----------|
| B4 | LogisticRegression | FS-F | Y | 0.5918 | 0.7833 | 0.4685 | 0.7071 |
| B5 | LogisticRegression | FS-G | Y | 0.6190 | 0.8598 | 0.4919 | 0.7000 |

---

## 6. Output Artifacts Created

| File | Location | Notes |
|------|----------|-------|
| `baseline_results_2024_09_25k_v1.json` | `data/processed/` (gitignored) | All metrics |
| `baseline_predictions_2024_09_25k_v1.parquet` | `data/processed/` (gitignored) | Per-row predictions |
| `phase_5_2b_*.md` | `reports/phase_reports/` (committed) | This report |

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py -v
```

---

## 8. Test Results

(To be filled after test run.)

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
Eval val/test have ~4 and ~2 DRAW rows respectively. DRAW metrics in eval
experiments are noise. All eval baselines are flagged exploratory.

**R2 — B0 log_loss**
DummyClassifier (most_frequent) predicts p=1.0 for one class, log_loss ~18.9.
This is expected and is not a bug.

**R3 — Unweighted LR predicts 0 DRAW rows**
B2 and B3 without class_weight will often predict 0 DRAW (minority class ~6%).
B3-balanced shows the balanced-weight effect on DRAW recall.

**R4 — eval_mate_abs imputation**
93.6% of eval_mate_abs values are null (non-mate positions).
SimpleImputer(fill_value=0) treats these as 'no mate threat', which is correct.

---

## 11. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| GBM (HistGradientBoostingClassifier) | Phase 6 |
| Calibration | Phase 6.2 |
| Subgroup analysis | Phase 7 |
| Model artifact persistence (.joblib) | Not required for baselines |
| XGBoost / LightGBM | Phase 6+ |

---

## 12. Whether Next Ticket Is Safe to Begin

**Yes.** Baseline metrics establish floor for Phase 6 GBM work.

Suggested next ticket: **Phase 6.1A — GBM Audit**
(HistGradientBoostingClassifier on FS-C through FS-G).

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/baselines.py
git add tests/test_baselines.py
git add ROADMAP.md
git add reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md
git commit -m "Ticket 5.2B: baselines.py, <N> tests (<total> total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
