# Phase Report: Ticket 7.1B — Calibration Implementation

**Labels:** ML | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Status:** Complete. calibration.py (15 functions A–O) + 79 tests + report rendered.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 7.1B — Calibration Implementation
ML | D2 | IMPLEMENTATION

---

## 2. ELI5 / TLDR

This ticket creates `calibration.py`, which loads baseline and GBM prediction
artifacts, standardizes their schemas, filters to B1/B3/G2, and computes
calibration diagnostics (confidence-accuracy buckets, OvR reliability tables,
ECE, classwise Brier). Renders a caveated 12-section Markdown diagnostic report.
No post-hoc calibrators fitted. No model artifacts saved. No plots. No new
dependencies.

Output: `reports/calibration_2024_09_25k_v1.md` + this phase report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/calibration.py` | Created — 15 functions (A–O) + CLI |
| `tests/test_calibration.py` | Created — 79 tests |
| `ROADMAP.md` | Modified — added 7.1A complete + 7.1B complete entries |
| `EXPERIMENT_LOG.md` | Modified — added EXP-004 |
| `reports/calibration_2024_09_25k_v1.md` | Created (committed) |
| `reports/phase_reports/phase_7_1b_calibration_implementation.md` | Created (this file) |

---

## 4. Module Summary

`calibration.py` — 15 functions A–O:

| Function | Purpose |
|----------|---------|
| A. `get_class_order` | Return canonical class order from baselines.CLASS_ORDER |
| B. `load_baseline_predictions` | Read Parquet; validate baseline_id + prob cols |
| C. `load_gbm_predictions` | Read Parquet; validate model_id + prob cols |
| D. `standardize_prediction_schema` | Rename baseline_id→model_id; filter GBM to primary_numbered; concat |
| E. `filter_calibration_models` | Keep B1, B3, G2 only; exclude G4/G5/G6/B0 |
| F. `check_probability_sanity` | Validate nulls, non-negativity, prob sums ≈ 1 |
| G. `compute_confidence_accuracy_table` | Top-label confidence vs accuracy in uniform bins |
| H. `compute_reliability_table` | OvR reliability for a single class, 5-bin uniform |
| I. `compute_ece` | Weighted absolute ECE from OvR reliability rows |
| J. `compute_classwise_brier` | OvR classwise Brier score for a single class |
| K. `summarize_model_calibration` | Full calibration summary for one model/split |
| L. `render_markdown_table` | Generic Markdown table renderer |
| M. `render_calibration_report` | Assemble 12-section Markdown diagnostic report |
| N. `write_text` | Write text to file, creating parent dirs |
| O. `main` | CLI: --dataset-id, --version-tag, --baseline-predictions, --gbm-predictions, --output |

---

## 5. Key Implementation Notes

**Schema normalization:** Baseline predictions use `baseline_id`; GBM predictions
use `model_id`. Function D (`standardize_prediction_schema`) renames `baseline_id`
→ `model_id` and filters GBM to `view == "primary_numbered"` before concatenating.
This ensures row counts match the broad baseline scope (931 val rows each).

**OvR framing:** All reliability tables and ECE use one-vs-rest (OvR) binary
decomposition per class. ECE = Σ_bins (n_bin / total_n) × |mean_pred_prob − frac_positive|.

**Confidence-accuracy table:** Uses top-label confidence (max probability),
10-bin uniform. Gap = mean_confidence − accuracy. Positive gap = overconfident.

**G4 excluded:** Near-prior behavior (max_prob mean ≈ 0.476) would appear
deceptively calibrated. Documented in Scope and Caveats section.

**G6 excluded:** Memorizes training set (train log_loss ≈ 0.004). G5 also
excluded (eval-gated, different row scope).

**DRAW sparsity caveat:** 59/931 val rows (6.3%). DRAW ECE appears small for
all models but reflects near-zero predictions on a sparse class, not calibration.
A `DRAW sparsity warning` block is injected per-model when DRAW count < 30.

**No post-hoc calibrators:** Platt scaling, isotonic regression, and temperature
scaling are not applied. This is a diagnostics-only report.

---

## 6. CLI

```bash
PYTHONPATH=src python -m chess_mhsuc.calibration \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \
    --output reports/calibration_2024_09_25k_v1.md
```

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_calibration.py -v
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py tests/test_baseline_evaluation.py \
    tests/test_gbm_evaluation.py tests/test_gbm_feature_importance.py \
    tests/test_calibration.py -v
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through gbm_feature_importance) | 971 | All passed (no regression) |
| `test_calibration.py` | 79 | All passed |

**1050 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Real Data Results

Val split (931 rows), B1/B3/G2 on broad primary_numbered view:

**ECE OvR:**
| Model | BLACK_WIN | DRAW | WHITE_WIN |
|-------|-----------|------|-----------|
| B1 | 0.0023 | 0.0012 | 0.0035 |
| B3 | 0.0260 | 0.0009 | 0.0327 |
| G2 | 0.2338 | 0.0608 | 0.2034 |

**Classwise Brier OvR:**
| Model | BLACK_WIN | DRAW | WHITE_WIN |
|-------|-----------|------|-----------|
| B1 | 0.2494 | 0.0594 | 0.2485 |
| B3 | 0.2388 | 0.0589 | 0.2362 |
| G2 | 0.3125 | 0.0681 | 0.3012 |

**G2 confidence-accuracy (selected bins):**
| Bin | n | acc | mean_conf | gap |
|-----|---|-----|-----------|-----|
| [0.50, 0.60) | 185 | 0.4324 | 0.5487 | +0.1162 |
| [0.70, 0.80) | 171 | 0.4912 | 0.7509 | +0.2597 |
| [0.80, 0.90) | 193 | 0.4974 | 0.8507 | +0.3533 |
| [0.90, 1.00) | 175 | 0.5943 | 0.9494 | +0.3551 |

All values match Phase 7.1A audit findings exactly.

---

## 10. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibrators fitted.
- No new data files staged.
- Only source code, tests, ROADMAP.md, EXPERIMENT_LOG.md, and reports staged/committed.

---

## 11. Risks / Assumptions

**R1 — DRAW sparsity**
59/931 val rows are DRAW (6.3%). All models output near-zero p_DRAW for most
rows. DRAW ECE is trivially small for all models; this reflects class sparsity
and near-constant near-zero predictions, not genuine DRAW calibration. Explicitly
documented in report Scope section and per-model warning blocks.

**R2 — B1 appears well-calibrated**
B1 ECE is extremely small (≈ 0.002–0.004) because it assigns exactly the class
prior to every row. This appears calibrated but is degenerate: it carries no
information beyond the marginal class distribution. Documented in Interpretation.

**R3 — G4 exclusion**
G4 predicts near-prior probabilities (max_prob mean ≈ 0.476). Including it would
show deceptively low ECE; excluded with explicit note.

**R4 — Reliability curve resolution**
5-bin OvR reliability may have sparse extreme bins, especially for DRAW. Bin
counts are shown in all tables for transparency.

---

## 12. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Post-hoc calibration (Platt/isotonic) | Phase 7.2 |
| Temperature scaling | Phase 7.2 |
| Calibration plots | Not allowed this ticket |
| Test set calibration snapshot | Deferred; val split primary |
| DRAW calibration improvement | Requires class rebalancing or more data |
| Calibration on improved model | Phase 8 (Scaling) first |

---

## 13. Whether Next Ticket Is Safe to Begin

**Yes.** Calibration diagnostic is complete and verified against 7.1A audit values.
Recommended next ticket: **Phase 7.2A (Probability Interpretation Audit)** or
**Phase 8 (Scaling)**. Post-hoc calibration is most useful after model improvement.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/calibration.py
git add tests/test_calibration.py
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git add reports/calibration_2024_09_25k_v1.md
git add reports/phase_reports/phase_7_1b_calibration_implementation.md
git commit -m "Ticket 7.1B: calibration.py, 79 tests (1050 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
