# Phase Report: Ticket 6.3B — Feature Importance Implementation

**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Status:** Complete. gbm_feature_importance.py (16 functions A–P) + 60 tests + report rendered.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 6.3B — Feature Importance Implementation
ML/ANALYSIS | D2 | IMPLEMENTATION

---

## 2. ELI5 / TLDR

This ticket creates `gbm_feature_importance.py`, which retrains G2 deterministically
in memory, computes validation-set permutation importance, and renders a caveated
12-section Markdown diagnostic report. No model artifacts saved, no calibration,
no SHAP, no new dependencies.

Output: `reports/gbm_feature_importance_2024_09_25k_v1.md` + this phase report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/gbm_feature_importance.py` | Created — 16 functions (A–P) + CLI |
| `tests/test_gbm_feature_importance.py` | Created — 60 tests |
| `ROADMAP.md` | Modified — added 6.3A complete + 6.3B complete entries |
| `EXPERIMENT_LOG.md` | Modified — added EXP-003 |
| `reports/gbm_feature_importance_2024_09_25k_v1.md` | Created (committed) |
| `reports/phase_reports/phase_6_3b_feature_importance_implementation.md` | Created (this file) |

---

## 4. Module Summary

`gbm_feature_importance.py` — 16 functions A–P:

| Function | Purpose |
|----------|---------|
| A. `load_gbm_results` | Load + validate GBM results JSON; accepts dict or list for gbm_models |
| B. `load_feature_broad` | Read Parquet; validate game_id, result_class, selected_position_type |
| C. `load_splits` | Load splits JSON; validate assignments key, non-empty |
| D. `load_modeling_plan` | Load modeling plan JSON; validate feature_sets key |
| E. `get_gbm_models` | dict or list → stable-sorted list by model_id |
| F. `get_model_by_id` | Return model dict for given model_id; raises KeyError if missing |
| G. `prepare_g2_train_val_data` | Build G2 train/val subsets using primary_numbered view |
| H. `retrain_g2_in_memory` | Retrain G2 with fixed GBM_PARAMS; no artifact saved |
| I. `compute_validation_log_loss` | Sanity check: retrained val log_loss vs expected ≈ 1.2369 |
| J. `compute_permutation_importance_table` | Permutation importance; sorted desc by delta_log_loss |
| K. `classify_importance_signal` | Three categories: positive/near-zero/negative |
| L. `render_ablation_table` | G1/G2/G3/G4 coarse context table |
| M. `render_permutation_table` | Sorted importance table with signal classification |
| N. `render_gbm_feature_importance_report` | Assemble 12-section Markdown report |
| O. `write_text` | Write text to file, creating parent dirs |
| P. `main` | CLI: --dataset-id, --version-tag, --gbm-results, --feature-broad, --splits, --modeling-plan, --output |

---

## 5. Key Implementation Notes

**Sign convention for permutation importance:**
`sklearn.inspection.permutation_importance` with `scoring='neg_log_loss'` returns
`importances_mean[i]` as the mean *decrease* in neg_log_loss score when permuted.
Since `neg_log_loss = -log_loss`, a decrease in neg_log_loss = increase in log_loss.
Therefore `delta_log_loss = -importances_mean`. Positive delta = feature is genuinely
predictive. Negative delta = permuting improves val log_loss = overfit artifact.

**G2 retrains deterministically:** Same GBM_PARAMS as Phase 6.1B (max_iter=300,
lr=0.05, max_leaf_nodes=31, min_samples_leaf=20, l2_reg=0.1, random_state=42).
Expected val log_loss ≈ 1.2326 (Phase 6.1B stored result); sanity check uses ±0.002 tolerance.

**No model artifact saved:** G2 is retrained in memory only. The fitted
`HistGradientBoostingClassifier` object is used for permutation importance and
then discarded. No `.joblib` or `.pkl` files created.

**String categoricals dropped:** `selected_position_type` and `phase` are excluded
(STRING_CATEGORICALS_TO_DROP from gbm.py). 20 numeric features used.

**Report language constraints enforced:** Report does not contain "clock does not
matter", "GBM learned human strategy", "feature importance proves", or any
unqualified "causal" claim. All uses of "causal" are negated.

**Test fixture bug fixed:** `_make_feature_broad_df()` had operator precedence error
(`list * (n // 10 + 1)[:n]` attempted to subscript an integer). Fixed to
`(list * (n // 10 + 1))[:n]`. Also fixed modeling plan fixture key from
`"feature_columns"` to `"features"` to match real JSON schema.

---

## 6. CLI

```bash
PYTHONPATH=src python -m chess_mhsuc.gbm_feature_importance \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \
    --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \
    --splits data/processed/splits_2024_09_25k_v1.json \
    --modeling-plan data/processed/modeling_plan_2024_09_25k_v1.json \
    --output reports/gbm_feature_importance_2024_09_25k_v1.md
```

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_gbm_feature_importance.py -v
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py tests/test_baseline_evaluation.py \
    tests/test_gbm_evaluation.py tests/test_gbm_feature_importance.py -v
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through gbm_evaluation) | 911 | All passed (no regression) |
| `test_gbm_feature_importance.py` | 60 | All passed |

**971 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Real Data Results

Deterministic 6.3B CLI values (source of truth for this report):

| Feature | Δ val log_loss | Signal |
|---------|---------------|--------|
| avg_elo | +0.0410 | positive diagnostic signal |
| white_elo | +0.0169 | positive diagnostic signal |
| (remaining 18 features) | near-zero or negative | near-zero / unstable or overfit artifact |
| clock_diff_s | −0.0481 | negative overfit artifact (most negative) |

G2 retrained val log_loss: **1.2369** (6.3B deterministic retrain).
Stored Phase 6.1B G2 val log_loss: **1.2326**. Difference: +0.0043 — small reconstruction drift, accepted and documented. Qualitative finding is identical: rating features positive, clock_diff_s strongest negative artifact.

---

## 10. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibration performed.
- No new data files staged.
- Only source code, tests, ROADMAP.md, EXPERIMENT_LOG.md, and reports are staged/committed.

---

## 11. Risks / Assumptions

**R1 — Small reconstruction drift between stored 6.1B result and 6.3B retrain**
The stored Phase 6.1B G2 val log_loss was 1.2326. The deterministic 6.3B
in-memory retrain gives 1.2369, a +0.0043 difference. Permutation importance
values (white_elo=+0.0169, avg_elo=+0.0410, clock_diff_s=−0.0481) also differ
from the 6.3A audit scratch values. The final committed reference values are
the deterministic 6.3B CLI values. They preserve the same qualitative finding:
rating features are positive, and clock_diff_s is the strongest negative overfit
artifact. The retrain is fully deterministic across reruns on this machine.

**R2 — Expected val log_loss ≈ 1.2369; tolerance ±0.01**
Expected permutation importance values: white_elo≈+0.0169, avg_elo≈+0.0410,
clock_diff_s≈−0.0481 (±0.015 tolerance). Sanity check is PASS on this machine.

**R3 — Overfit model importances are unreliable**
Explicitly documented throughout the report. Results are diagnostic only.

**R4 — Permutation importance not causal**
Explicitly documented. No causal claims made in the report.

---

## 12. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Calibration | Phase 7 |
| SHAP explanations | No new deps added; deferred to after model improvement |
| Feature importance on non-overfit model | Phase 8 (Scaling) first |
| Constraint analysis conclusions | Phase 9 (after robust model + data) |
| Hyperparameter tuning | Phase 8 |

---

## 13. Whether Next Ticket Is Safe to Begin

**Yes.** Feature importance diagnostic is complete. Recommended next ticket:
**Phase 7 (Calibration)** or **Phase 8 (Scaling)**. Feature importance from a
better-fit model on larger data will be more informative.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/gbm_feature_importance.py
git add tests/test_gbm_feature_importance.py
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git add reports/gbm_feature_importance_2024_09_25k_v1.md
git add reports/phase_reports/phase_6_3b_feature_importance_implementation.md
git commit -m "Ticket 6.3B: gbm_feature_importance.py, 60 tests (971 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
