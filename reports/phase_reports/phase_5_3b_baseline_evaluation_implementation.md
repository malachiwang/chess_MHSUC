# Phase Report: Ticket 5.3B — Baseline Evaluation Report Implementation

**Labels:** ML/REPORTING | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Status:** Complete. baseline_evaluation.py (17 functions A–Q) + 106 tests + report rendered.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 5.3B — Baseline Evaluation Report Implementation
ML/REPORTING | D2 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR

This ticket creates `baseline_evaluation.py`, which reads the `baseline_results_2024_09_25k_v1.json`
produced by Phase 5.2B and renders a human-readable Markdown evaluation report.
No model training, no new data, no calibration. Output: one committed Markdown report
(`reports/baseline_evaluation_2024_09_25k_v1.md`) + this phase report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/baseline_evaluation.py` | Created — 17 functions (A–Q) + CLI |
| `tests/test_baseline_evaluation.py` | Created — 106 tests |
| `ROADMAP.md` | Modified — added 5.3A and 5.3B ticket entries |
| `EXPERIMENT_LOG.md` | Modified — added EXP-001 |
| `reports/baseline_evaluation_2024_09_25k_v1.md` | Created (committed) |
| `reports/phase_reports/phase_5_3b_baseline_evaluation_implementation.md` | Created (this file) |

---

## 4. Module Summary

`baseline_evaluation.py` — 17 functions A–Q:

| Function | Purpose |
|----------|---------|
| A. `load_baseline_results` | Load + validate baseline results JSON; raises if baselines not a dict |
| B. `get_baselines` | Convert `payload["baselines"]` dict → list |
| C. `filter_broad_primary_baselines` | Broad, non-diagnostic (B0–B3) |
| D. `filter_eval_exploratory_baselines` | Eval, exploratory (B4, B5) |
| E. `filter_diagnostic_baselines` | Diagnostic flag = True (B3-balanced) |
| F. `get_split_metrics` | Get metrics dict for one split |
| G. `get_per_class_metric` | Get one per-class metric value |
| H. `sort_by_validation_log_loss` | Sort ascending by val log_loss |
| I. `format_float` | Format float to N decimal places; "N/A" if None |
| J. `render_inventory_table` | Full inventory Markdown table (all 7 baselines) |
| K. `render_validation_table` | Comparison table (excluding B0), sorted by val log_loss |
| L. `render_confusion_matrix` | Confusion matrix as Markdown table |
| M. `render_signal_decomposition` | B1 → B2 → B3 log_loss progression table |
| N. `render_test_snapshot` | Test metrics for broad primary baselines |
| O. `render_baseline_evaluation_report` | Assemble full 9-section report |
| P. `write_text` | Write text to file, creating parent dirs |
| Q. `main` | CLI: `--dataset-id`, `--version-tag`, `--baseline-results`, `--output` |

---

## 5. Key Implementation Notes

**`baselines` is a dict, not a list:** The JSON schema from baselines.py stores
`payload["baselines"]` as a dict keyed by baseline_id. `get_baselines()` converts
it to a list via `list(payload["baselines"].values())`. The validator in
`load_baseline_results` enforces this schema.

**B0 excluded from comparison table:** B0 (DummyClassifier `most_frequent`) predicts
p=1.0 for the majority class, giving log_loss ≈ 18.9. The `_is_b0()` helper detects
this by checking `model_type == "DummyClassifier" and sklearn_params["strategy"] == "most_frequent"`.
B0 appears only in the inventory table.

**Log_loss is the primary column:** In all comparison tables, `Val log_loss` appears
before `Val acc`. This matches the modeling_plan metric_policy.

---

## 6. CLI

```bash
PYTHONPATH=src python -m chess_mhsuc.baseline_evaluation \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \
    --output reports/baseline_evaluation_2024_09_25k_v1.md
```

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py tests/test_baseline_evaluation.py -v
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through gbm) | 720 | All passed (no regression) |
| `test_baseline_evaluation.py` | 106 | All passed |

**826 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibration performed.
- No data files staged.
- Only source code, tests, ROADMAP.md, EXPERIMENT_LOG.md, and reports are staged/committed.

---

## 10. Risks / Assumptions

**R1 — baselines dict schema assumed**
`load_baseline_results` validates that `payload["baselines"]` is a dict. Any file
produced by an incompatible version of baselines.py would raise ValueError.

**R2 — B0 detection is heuristic**
B0 exclusion relies on `model_type == "DummyClassifier" and strategy == "most_frequent"`.
If a future experiment adds another DummyClassifier with this strategy under a different
baseline_id, it would also be excluded from comparison tables.

**R3 — Eval DRAW sparsity**
Eval val/test DRAW support is ~4/~2 rows. Eval section is marked exploratory.

---

## 11. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| GBM evaluation report | Phase 6.3+ |
| Calibration assessment | Phase 6.2 |
| Subgroup/slice analysis | Phase 7 |
| Interactive/notebook evaluation | Not required |

---

## 12. Whether Next Ticket Is Safe to Begin

**Yes.** Phase 6 GBM work is already complete (6.1B). The evaluation report
establishes the baseline floor: B3 val log_loss=0.8527.

Suggested next ticket: **Phase 6.2A — Calibration Audit**.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/baseline_evaluation.py
git add tests/test_baseline_evaluation.py
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git add reports/baseline_evaluation_2024_09_25k_v1.md
git add reports/phase_reports/phase_5_3b_baseline_evaluation_implementation.md
git commit -m "Ticket 5.3B: baseline_evaluation.py, 106 tests (826 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
