# Phase Report: Ticket 6.2B — GBM Evaluation Implementation

**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Status:** Complete. gbm_evaluation.py (18 functions A–R) + 85 tests + report rendered.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 6.2B — GBM Evaluation Implementation
ML/ANALYSIS | D2 | IMPLEMENTATION

---

## 2. ELI5 / TLDR

This ticket creates `gbm_evaluation.py`, which reads the GBM and baseline
result artifacts produced by Phases 6.1B and 5.2B, computes slice/overfitting/
confidence-bucket diagnostics, and renders a durable Markdown evaluation report.
No model training, no tuning, no calibration, no feature importance.

Output: `reports/gbm_evaluation_2024_09_25k_v1.md` + this phase report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/gbm_evaluation.py` | Created — 18 functions (A–R) + CLI |
| `tests/test_gbm_evaluation.py` | Created — 85 tests |
| `ROADMAP.md` | Modified — replaced calibration 6.2A/B stubs with GBM evaluation entries |
| `EXPERIMENT_LOG.md` | Modified — added EXP-002 |
| `reports/gbm_evaluation_2024_09_25k_v1.md` | Created (committed) |
| `reports/phase_reports/phase_6_2b_gbm_evaluation_implementation.md` | Created (this file) |

---

## 4. Module Summary

`gbm_evaluation.py` — 18 functions A–R:

| Function | Purpose |
|----------|---------|
| A. `load_gbm_results` | Load + validate GBM results JSON; accepts dict or list for gbm_models |
| B. `load_baseline_results` | Load + validate baseline results JSON; requires baselines + class_order |
| C. `load_gbm_predictions` | Read Parquet; validate 19 required prediction columns |
| D. `load_feature_broad` | Load optional feature Parquet for avg_elo join; returns None if path=None |
| E. `get_gbm_models` | dict or list → stable-sorted list by model_id |
| F. `get_baseline_models` | dict or list → stable-sorted list by baseline_id |
| G. `filter_broad_primary_gbms` | table=="broad", not diagnostic, not exploratory → G1, G2 |
| H. `filter_broad_diagnostic_gbms` | table=="broad", diagnostic==True → G3, G4 |
| I. `filter_eval_exploratory_gbms` | table=="eval", exploratory==True → G5, G6 |
| J. `get_split_metrics` | Return metrics dict for one split; raises KeyError if missing |
| K. `get_per_class_metric` | Safe path traversal; returns None if missing |
| L. `format_float` | Format float to N decimal places; "NA" if None |
| M. `compute_slice_accuracy` | Accuracy by slice column for one model/split; raises if col absent |
| N. `compute_confidence_buckets` | Bucket by max(p_BW, p_D, p_WW); diagnostic only, no calibration |
| O. `join_avg_elo_slice` | Left join on (game_id, move_number); skips if feature_broad_df=None |
| P. `render_gbm_evaluation_report` | Assemble full 17-section Markdown report |
| Q. `write_text` | Write text to file, creating parent dirs |
| R. `main` | CLI: --dataset-id, --version-tag, --gbm-results, --gbm-predictions, --baseline-results, --feature-broad (optional), --output |

---

## 5. Key Implementation Notes

**`gbm_models` is a dict:** The JSON schema from gbm.py stores
`payload["gbm_models"]` as a dict keyed by model_id. `get_gbm_models()`
converts to a list and sorts by model_id.

**G4 near-prior flagged explicitly:** G4's val log_loss ≈ 0.881 is lower than
G2's, but this reflects near-prior behaviour (max_prob mean ≈ 0.476, extremely
narrow probability range). The report explicitly states G4 must not be called
the best or winning GBM.

**G2 does not beat B3:** The report explicitly states "G2 does not beat B3"
(G2 val log_loss=1.2326 vs B3=0.8527). This is called a "controlled diagnostic
result, not a project failure."

**No calibration fitting:** `compute_confidence_buckets` is labelled as a
diagnostic only. No CalibratedClassifierCV or isotonic/Platt scaling is
applied. The report defers calibration to Phase 7.

**avg_elo join is optional:** If `--feature-broad` is not passed, the elo
bucket section is skipped with an explanatory note. With it, join is on
`(game_id, move_number)` with left join; 931/931 rows matched (0 nulls) on
real data.

**feature_columns_dropped key:** All G1–G6 model dicts have this key (from
Phase 6.1B hotfix). The inventory table renders dropped columns or "—".

---

## 6. CLI

```bash
PYTHONPATH=src python -m chess_mhsuc.gbm_evaluation \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \
    --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \
    --output reports/gbm_evaluation_2024_09_25k_v1.md
```

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py tests/test_baseline_evaluation.py \
    tests/test_gbm_evaluation.py -v
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through baseline_evaluation) | 826 | All passed (no regression) |
| `test_gbm_evaluation.py` | 85 | All passed |

**911 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibration performed.
- No new data files staged.
- Only source code, tests, ROADMAP.md, EXPERIMENT_LOG.md, and reports are staged/committed.

---

## 10. Risks / Assumptions

**R1 — Real data slice values differ from synthetic fixtures**
Synthetic fixtures cover phase/move_number/is_time_forfeit/has_eval/avg_elo as
designed. Real data has the same columns and the CLI confirmed 931/931 val rows
join correctly.

**R2 — G4 near-prior characterisation**
The near-prior characterisation is based on the audit (Phase 6.2A): p_BLACK_WIN
range [0.452, 0.482], max_prob mean ≈ 0.476. This is documented in the report
and tests verify the phrase "near-prior" appears.

**R3 — Report slices use G2 only**
Slice analysis is for G2 only (primary broad GBM). Other models are not sliced.
This is by design — the report is focused on the primary model.

---

## 11. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Calibration fitting | Phase 7 |
| Feature importance | Phase 6.3A |
| Subgroup/constraint analysis | Phase 9 (after more robust model/data) |
| Hyperparameter tuning | Phase 8 (scaling needed first) |
| Neural networks | Not justified at current data scale |

---

## 12. Whether Next Ticket Is Safe to Begin

**Yes.** The GBM evaluation is complete. The negative result (G2 < B3) is
documented and understood. The recommended next ticket is **Phase 6.3A —
Feature Importance Audit** (noting that importances from the overfit G2 may be
unreliable). Phase 7 (Calibration) and Phase 8 (Scaling) are also open.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/gbm_evaluation.py
git add tests/test_gbm_evaluation.py
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git add reports/gbm_evaluation_2024_09_25k_v1.md
git add reports/phase_reports/phase_6_2b_gbm_evaluation_implementation.md
git commit -m "Ticket 6.2B: gbm_evaluation.py, 85 tests (911 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
