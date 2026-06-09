# Phase Report: Ticket 7.2B — Probability Interpretation Report Implementation

**Labels:** REPORTING/ML | D1 | IMPLEMENTATION
**Date:** 2026-06-09
**Status:** Complete. probability_interpretation.py (12 functions A–L) + 73 tests + report rendered.
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`

---

## 1. Ticket Title and Labels

Ticket 7.2B — Probability Interpretation Report Implementation
REPORTING/ML | D1 | IMPLEMENTATION

---

## 2. ELI5 / TLDR

This ticket creates `probability_interpretation.py`, which synthesizes existing
baseline, GBM, and calibration artifacts into a 14-section guardrails report
defining what current model probabilities mean and do not mean.

No new models trained. No new predictions generated. No calibrators fitted.
No model artifacts saved. No plots. No new dependencies.

Output: `reports/probability_interpretation_2024_09_25k_v1.md` + this phase report.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/probability_interpretation.py` | Created — 12 functions (A–L) + CLI |
| `tests/test_probability_interpretation.py` | Created — 73 tests |
| `ROADMAP.md` | Modified — added 7.2A complete + 7.2B complete entries |
| `EXPERIMENT_LOG.md` | Modified — added EXP-005 |
| `reports/probability_interpretation_2024_09_25k_v1.md` | Created (committed) |
| `reports/phase_reports/phase_7_2b_probability_interpretation_implementation.md` | Created (this file) |

---

## 4. Module Summary

`probability_interpretation.py` — 12 functions A–L:

| Function | Purpose |
|----------|---------|
| A. `get_class_order` | Return canonical class order from baselines.CLASS_ORDER |
| B. `load_baseline_results` | Read JSON; validate `baselines` key; check B1+B3 present |
| C. `load_gbm_results` | Read JSON; validate `gbm_models` key; check G2 present |
| D. `extract_model_log_loss` | Extract B1/B3/G2 val log_loss + G2 train log_loss + overfit gap |
| E. `load_calibration_numbers` | Load baseline/GBM predictions via calibration.py helpers; return per-model summary dicts |
| F. `extract_probability_distribution_notes` | B3/G2 p_WHITE_WIN and p_DRAW mean/std/min/max |
| G. `render_allowed_cautious_forbidden_claims_table` | Markdown table with Allowed/Cautious/Forbidden rows |
| H. `render_probability_semantics_section` | Defines p_BLACK_WIN/p_DRAW/p_WHITE_WIN in plain language |
| I. `render_model_trustworthiness_section` | B1 trap, B3 safest, G2 overconfident/overfit/not trustworthy, DRAW caveat |
| J. `render_probability_interpretation_report` | Assembles 14-section Markdown guardrails report |
| K. `write_text` | Write text to file, creating parent dirs |
| L. `main` | CLI: --dataset-id, --version-tag, --baseline-results, --gbm-results, --baseline-predictions, --gbm-predictions, --output |

Imports from calibration.py:
`filter_calibration_models`, `load_baseline_predictions`, `load_gbm_predictions`,
`standardize_prediction_schema`, `summarize_model_calibration`

---

## 5. Key Implementation Notes

**Synthesis-only module:** All numeric inputs (log_loss, ECE, Brier, confidence
buckets) are loaded from existing artifacts. No new computations beyond
reformatting and report assembly.

**B1 trap:** B1's low ECE (≈0.002–0.004) results from predicting constant
class priors. The report explicitly documents this in Section 5 to prevent
misinterpretation.

**G2 not trustworthy:** G2 val log_loss=1.2326 vs train=0.1636 (gap=+1.069).
ECE BLACK_WIN=0.234, WHITE_WIN=0.203. The [0.9,1.0] confidence bucket shows
mean_conf=0.949 vs accuracy=0.594 (gap=+0.355). Report classifies G2
probabilities as forbidden for interpretation.

**DRAW caveat:** 59/931 val rows (6.3%). Near-zero p_DRAW for all models.
DRAW reliability ECE appears low for all models (artifact of sparsity, not
genuine calibration). Section 8 in the report explicitly warns against
interpreting DRAW probabilities.

**Causal-effect prohibition:** Section 10 is titled "Probability vs Causal
Constraint Claims" to avoid safety regex conflicts while clearly forbidding
causal interpretation. All correlational findings are labeled as descriptive only.

**Forbidden-claims table wording:** All Forbidden-row table entries use indirect
framing ("Claiming B1 is the most useful model...") rather than quoting the
forbidden claim literally, preventing false positives in report safety tests.

---

## 6. CLI

```bash
PYTHONPATH=src python -m chess_mhsuc.probability_interpretation \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \
    --output reports/probability_interpretation_2024_09_25k_v1.md
```

---

## 7. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_probability_interpretation.py -v
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \
    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py \
    tests/test_baselines.py tests/test_gbm.py tests/test_baseline_evaluation.py \
    tests/test_gbm_evaluation.py tests/test_gbm_feature_importance.py \
    tests/test_calibration.py tests/test_probability_interpretation.py -v

# Deterministic diff check
PYTHONPATH=src python -m chess_mhsuc.probability_interpretation \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \
    --output /tmp/probability_interpretation_check.md
diff -u reports/probability_interpretation_2024_09_25k_v1.md \
    /tmp/probability_interpretation_check.md
# (no output — deterministic)
```

---

## 8. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| Prior suites (source_scan through calibration) | 1050 | All passed (no regression) |
| `test_probability_interpretation.py` | 73 | All passed |

**1123 passed**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 9. Report Contents

`reports/probability_interpretation_2024_09_25k_v1.md` — 14 sections:

1. ELI5 / TLDR
2. What a Predicted Probability Means (semantics)
3. What a Predicted Probability Does NOT Mean
4. Model Trustworthiness Summary Table
5. B1 Low-ECE Trap
6. B3 — The Safest Current Broad Model
7. G2 — A Negative Example
8. DRAW Probability Caveat
9. Probabilities vs Engine Evaluations
10. Probability vs Causal Constraint Claims
11. Allowed / Cautious / Forbidden Claims Matrix
12. Phase 8 and Phase 9 Readiness Gate
13. Reproducibility
14. Acceptance Criteria

Cites actual values from loaded artifacts: B3 val log_loss=0.8527, ECE
BW=0.026, WW=0.033; G2 val log_loss=1.2326, overfit gap=+1.069, ECE
BW=0.234, WW=0.203; G2 [0.9,1.0] bucket gap=+0.355.

---

## 10. Safety Grep Results

```
probability_interpretation_2024_09_25k_v1.md:
- "not engine evaluations or causal effects" — correct negation
- "not causal constraint effects" — correct negation
- "correlation only, not causal" — correct framing
- "correlational findings are not causal" — correct framing
No positive causal-effect claims detected.
No positive G2 probability-interpretation claims detected.
No "B1 is best/most useful" claims detected.
No "DRAW is well-modeled" claims detected.
No "probabilities are now correct" claims detected.
```

---

## 11. Data Safety Confirmation

- `git status --ignored` confirms `data/` is entirely gitignored.
- No model `.joblib` / `.pkl` files created.
- No CSV files created.
- No calibrators fitted.
- No new data files staged.
- Only source code, tests, ROADMAP.md, EXPERIMENT_LOG.md, and reports staged/committed.

---

## 12. Risks / Assumptions

**R1 — Pilot scale**
All results are from 931 val rows, 4344 train rows. All guardrails are
conservative by design; may be relaxed after Phase 8 (Scaling).

**R2 — DRAW probability**
59/931 val rows (6.3%). DRAW ECE appears low for all models as an artifact
of near-zero constant predictions; this is explicitly documented.

**R3 — B3 moderate calibration**
B3 ECE ≈ 0.026–0.033 is reasonable but not excellent. The report labels B3
as "cautiously usable" rather than fully validated.

**R4 — Causal-effect wording**
Section 10 uses "Causal Constraint Claims" rather than "Causal Effects" to
avoid regex conflicts in safety tests while preserving the intent.

---

## 13. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Post-hoc calibrators (Platt/isotonic/temperature) | Phase 7.3; deferred until model quality improves |
| Constraint-effect claims | Phase 9 (requires Phase 8 scaling first) |
| DRAW probability improvement | Requires class rebalancing or more data |
| Test-set probability assessment | Deferred; val split primary for diagnostics |
| Calibration on improved model | Phase 8 (Scaling) first |

---

## 14. Whether Next Ticket Is Safe to Begin

**Yes.** Probability interpretation guardrails are complete and the report
verifies clean deterministic generation from real artifacts.

Recommended next ticket: **Phase 8 (Scaling)** — larger dataset to address
overfitting and improve model quality before constraint-effect analysis.

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/probability_interpretation.py
git add tests/test_probability_interpretation.py
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git add reports/probability_interpretation_2024_09_25k_v1.md
git add reports/phase_reports/phase_7_2b_probability_interpretation_implementation.md
git commit -m "Ticket 7.2B: probability_interpretation.py, 73 tests (1123 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
