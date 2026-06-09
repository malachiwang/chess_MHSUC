# Calibration Diagnostic Report — 2024_09_25k_v1

**Ticket:** 7.1B — Calibration Implementation
**Labels:** ML | D2 | IMPLEMENTATION
**Dataset ID:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

This is a **diagnostics-only** calibration report. No post-hoc calibrators are fitted. No model artifacts are saved.

Key findings:

- **B3 (LogisticRegression) is reasonably calibrated** on BLACK_WIN and WHITE_WIN. ECE ≈ 0.03 for these classes. Confidence-accuracy gap is small.
- **G2 (GBM) is severely overconfident.** ECE ≈ 0.20–0.23 for BLACK_WIN and WHITE_WIN. The highest confidence bucket ([0.9, 1.0]) has mean_conf ≈ 0.95 but accuracy ≈ 0.59 — a gap of ≈ +0.36.
- **DRAW is sparsely represented (~6% of validation rows).** ECE for DRAW appears low for all models, but this reflects uniform near-zero predictions on a sparse class, not genuine calibration.
- **B1 (prior) is constant and miscalibrated** by construction: all rows predict the same class-prior probabilities regardless of game state.
- **G2's overconfidence is consistent with its val log_loss = 1.2326 >> B3 = 0.8527.** The GBM memorized training patterns that do not generalize.
- **No calibration is applied.** Phase 7.2 and Phase 8 (scaling) are the next steps.

---

## 2. Research Framing

Chess is the testbed, not the endpoint. The larger goal is modeling human strategy and reasoning under constraints — how clock pressure, game phase, and skill level interact in time-limited play.

Calibration matters here because probability estimates are used directly as constraint-signal proxies. An overconfident model produces artificially narrow predictions that distort constraint-effect estimates. This report quantifies the calibration gap before any correction is applied.

---

## 3. Scope and Caveats

- **Models: B1, B3, G2 only.** G4 is excluded: near-prior behavior (max_prob mean ≈ 0.476) would appear deceptively calibrated. G5 and G6 are excluded: eval-gated (different row scope). G6 memorizes the training set. B0 is excluded: most-frequent dummy with degenerate probability output. B2, B3-balanced, B4, B5 are excluded to keep the report focused.
- **Validation split only.** Calibration is assessed on the val split (931 rows for broad models). Test split not used.
- **OvR framing.** Reliability tables and ECE use one-vs-rest (OvR) binary decomposition per class.
- **No post-hoc calibrators fitted.** Platt scaling, isotonic regression, and temperature scaling are not applied. Deferred to Phase 7.2.
- **No plots.** Only this Markdown report is committed.
- **No new dependencies.** No sklearn.calibration.CalibratedClassifierCV used.
- **DRAW sparsity.** ~59/931 val rows are DRAW (~6.3%). DRAW OvR metrics are noisy; all models predict near-zero p_DRAW for most rows. Low DRAW ECE does not indicate genuine calibration.
- **Pilot scale only.** Results limited to the 2024-09 25k-game extract.

---

## 4. B1 Calibration Diagnostics

**Split:** validation | **Rows:** 931

**Class distribution (val):**

| Class | Count | Pct |
| --- | --- | --- |
| BLACK_WIN | 443 | 47.6% |
| DRAW | 59 | 6.3% |
| WHITE_WIN | 429 | 46.1% |

### Top-label confidence-accuracy

Top-label confidence = max predicted probability. Gap = mean_confidence − accuracy (positive = overconfident).

| Bin | n | Accuracy | Mean confidence | Gap (conf−acc) |
| --- | --- | --- | --- | --- |
| [0.40, 0.50) | 931 | 0.4758 | 0.4735 | -0.0023 |

### OvR reliability (5-bin uniform)

**BLACK_WIN (p_BLACK_WIN vs 1-vs-rest label)** | ECE = 0.0023 | Classwise Brier = 0.2494

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.40, 0.60) | 931 | 0.4758 | 0.4735 | -0.0023 |

**DRAW (p_DRAW vs 1-vs-rest label)** | ECE = 0.0012 | Classwise Brier = 0.0594

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 931 | 0.0634 | 0.0622 | -0.0012 |

**WHITE_WIN (p_WHITE_WIN vs 1-vs-rest label)** | ECE = 0.0035 | Classwise Brier = 0.2485

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.40, 0.60) | 931 | 0.4608 | 0.4643 | +0.0035 |

---

## 5. B3 Calibration Diagnostics

**Split:** validation | **Rows:** 931

**Class distribution (val):**

| Class | Count | Pct |
| --- | --- | --- |
| BLACK_WIN | 443 | 47.6% |
| DRAW | 59 | 6.3% |
| WHITE_WIN | 429 | 46.1% |

### Top-label confidence-accuracy

Top-label confidence = max predicted probability. Gap = mean_confidence − accuracy (positive = overconfident).

| Bin | n | Accuracy | Mean confidence | Gap (conf−acc) |
| --- | --- | --- | --- | --- |
| [0.40, 0.50) | 283 | 0.4947 | 0.4821 | -0.0126 |
| [0.50, 0.60) | 504 | 0.5179 | 0.5374 | +0.0195 |
| [0.60, 0.70) | 90 | 0.6222 | 0.6305 | +0.0083 |
| [0.70, 0.80) | 20 | 0.8500 | 0.7424 | -0.1076 |
| [0.80, 0.90) | 21 | 0.6667 | 0.8467 | +0.1800 |
| [0.90, 1.00) | 13 | 1.0000 | 0.9533 | -0.0467 |

### OvR reliability (5-bin uniform)

**BLACK_WIN (p_BLACK_WIN vs 1-vs-rest label)** | ECE = 0.0260 | Classwise Brier = 0.2388

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 14 | 0.0714 | 0.1136 | +0.0422 |
| [0.20, 0.40) | 139 | 0.3165 | 0.3467 | +0.0301 |
| [0.40, 0.60) | 705 | 0.5021 | 0.4871 | -0.0150 |
| [0.60, 0.80) | 50 | 0.5400 | 0.6481 | +0.1081 |
| [0.80, 1.00) | 23 | 0.7391 | 0.8895 | +0.1504 |

**DRAW (p_DRAW vs 1-vs-rest label)** | ECE = 0.0009 | Classwise Brier = 0.0589

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 931 | 0.0634 | 0.0625 | -0.0009 |

**WHITE_WIN (p_WHITE_WIN vs 1-vs-rest label)** | ECE = 0.0327 | Classwise Brier = 0.2362

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 25 | 0.0400 | 0.0673 | +0.0273 |
| [0.20, 0.40) | 198 | 0.3939 | 0.3473 | -0.0467 |
| [0.40, 0.60) | 637 | 0.4615 | 0.4826 | +0.0210 |
| [0.60, 0.80) | 60 | 0.7667 | 0.6531 | -0.1136 |
| [0.80, 1.00) | 11 | 0.9091 | 0.8831 | -0.0260 |

---

## 6. G2 Calibration Diagnostics

**Split:** validation | **Rows:** 931

**Class distribution (val):**

| Class | Count | Pct |
| --- | --- | --- |
| BLACK_WIN | 443 | 47.6% |
| DRAW | 59 | 6.3% |
| WHITE_WIN | 429 | 46.1% |

### Top-label confidence-accuracy

Top-label confidence = max predicted probability. Gap = mean_confidence − accuracy (positive = overconfident).

| Bin | n | Accuracy | Mean confidence | Gap (conf−acc) |
| --- | --- | --- | --- | --- |
| [0.40, 0.50) | 25 | 0.4800 | 0.4806 | +0.0006 |
| [0.50, 0.60) | 185 | 0.4324 | 0.5487 | +0.1162 |
| [0.60, 0.70) | 182 | 0.4890 | 0.6462 | +0.1572 |
| [0.70, 0.80) | 171 | 0.4912 | 0.7509 | +0.2597 |
| [0.80, 0.90) | 193 | 0.4974 | 0.8507 | +0.3533 |
| [0.90, 1.00) | 175 | 0.5943 | 0.9494 | +0.3551 |

### OvR reliability (5-bin uniform)

**BLACK_WIN (p_BLACK_WIN vs 1-vs-rest label)** | ECE = 0.2338 | Classwise Brier = 0.3125

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 168 | 0.4464 | 0.1009 | -0.3455 |
| [0.20, 0.40) | 186 | 0.4624 | 0.3046 | -0.1578 |
| [0.40, 0.60) | 181 | 0.3923 | 0.5090 | +0.1167 |
| [0.60, 0.80) | 177 | 0.5198 | 0.6983 | +0.1785 |
| [0.80, 1.00) | 219 | 0.5434 | 0.8977 | +0.3543 |

**DRAW (p_DRAW vs 1-vs-rest label)** | ECE = 0.0608 | Classwise Brier = 0.0681

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 903 | 0.0631 | 0.0121 | -0.0511 |
| [0.20, 0.40) | 12 | 0.0833 | 0.2664 | +0.1831 |
| [0.40, 0.60) | 10 | 0.1000 | 0.5003 | +0.4003 |
| [0.60, 0.80) | 4 | 0.0000 | 0.6367 | +0.6367 |
| [0.80, 1.00) | 2 | 0.0000 | 0.8779 | +0.8779 |

**WHITE_WIN (p_WHITE_WIN vs 1-vs-rest label)** | ECE = 0.2034 | Classwise Brier = 0.3012

| Bin | n | Frac positive | Mean pred prob | Gap (pred−frac) |
| --- | --- | --- | --- | --- |
| [0.00, 0.20) | 242 | 0.3884 | 0.0988 | -0.2896 |
| [0.20, 0.40) | 189 | 0.4497 | 0.3003 | -0.1495 |
| [0.40, 0.60) | 181 | 0.4862 | 0.4926 | +0.0064 |
| [0.60, 0.80) | 172 | 0.4709 | 0.6970 | +0.2261 |
| [0.80, 1.00) | 147 | 0.5510 | 0.8978 | +0.3468 |

---

## 7. Model Comparison: ECE and Classwise Brier (val)

| Model | Class | ECE (OvR) | Classwise Brier (OvR) |
| --- | --- | --- | --- |
| B1 | BLACK_WIN | 0.0023 | 0.2494 |
| B1 | DRAW | 0.0012 | 0.0594 |
| B1 | WHITE_WIN | 0.0035 | 0.2485 |
| B3 | BLACK_WIN | 0.0260 | 0.2388 |
| B3 | DRAW | 0.0009 | 0.0589 |
| B3 | WHITE_WIN | 0.0327 | 0.2362 |
| G2 | BLACK_WIN | 0.2338 | 0.3125 |
| G2 | DRAW | 0.0608 | 0.0681 |
| G2 | WHITE_WIN | 0.2034 | 0.3012 |

> **Interpretation notes:**
> - B1 is a prior-only model; ECE reflects how well the class prior matches > class prevalence, not generalization.
> - B3 shows low ECE on BLACK_WIN and WHITE_WIN (≈ 0.03), indicating > reasonable calibration for a logistic baseline.
> - G2 shows high ECE on BLACK_WIN and WHITE_WIN (≈ 0.20–0.23), confirming > severe overconfidence consistent with its val log_loss of 1.2326.
> - DRAW ECE values are small for all models but this reflects the near-zero > p_DRAW predictions and class sparsity, not genuine calibration.

---

## 8. Interpretation

**B1 (DummyClassifier — prior):** Predicts class prior for every row. Confidence-accuracy table shows a single high-n bin at the prior probability. This is the calibration floor: any model that learns nothing beyond the prior will show similar OvR ECE to B1.

**B3 (LogisticRegression on FS-E):** The best broad baseline (val log_loss = 0.8527). B3's probabilities are reasonably spread; confidence-accuracy gaps are small for BLACK_WIN and WHITE_WIN. DRAW ECE is misleadingly small — B3 predicts near-zero p_DRAW for almost every row, which happens to be 'close' to the true binary label simply because DRAW is rare.

**G2 (HistGBM on FS-E):** Severely overconfident. The GBM memorized training patterns that produce high-confidence predictions on validation, but accuracy in the 0.9+ confidence bucket is only ≈ 0.59. This overconfidence is a direct consequence of the overfit: the model assigns confident probabilities to patterns it learned from training that do not generalize.

**DRAW class across all models:** No model predicts meaningful DRAW probabilities. The class-prior for DRAW is ≈ 6.3%. All models output p_DRAW ≈ 0.04–0.08 for most rows. DRAW OvR ECE appears small, but this is an artifact of sparsity and near-constant predictions, not calibration.

---

## 9. Known Limitations

- **No calibration applied.** Isotonic regression, Platt scaling, and temperature scaling not assessed. Deferred to Phase 7.2.
- **Pilot scale.** 931 val rows is small; bin counts can be low, especially for DRAW.
- **DRAW ECE is unreliable.** Sparsity (~59 rows) and near-zero p_DRAW predictions make ECE trivially small regardless of model quality.
- **No test set evaluation.** Calibration is assessed only on val split.
- **Reliability curves not plotted.** Visual inspection of calibration curves would provide additional insight; deferred since no plots are allowed in this ticket.
- **Classwise Brier ≠ overall Brier.** The sum of OvR Brier scores does not equal the multiclass Brier score reported in earlier phases.
- **B3 probabilities may reflect LR calibration artifacts.** LogisticRegression is known to be reasonably calibrated but may still show bias near the boundaries.

---

## 10. What This Does NOT Say

- **Not a final calibration.** No calibrators are fitted. These are raw model probability diagnostics.
- **Not a claim that B3 is well-calibrated.** B3 ECE ≈ 0.03 on BLACK_WIN/WHITE_WIN is relatively good, but B3 still fails on DRAW and produces lower-quality probabilities than a calibrated model would.
- **Not a causal finding.** Calibration gaps do not imply causal effects of any feature.
- **Not a constraint analysis.** Phase 9 constraint analysis requires a better-calibrated model on more data.

---

## 11. Reproducibility

Command used to generate this report:

```bash
PYTHONPATH=src python -m chess_mhsuc.calibration \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --version-tag 2024_09_25k_v1 \\
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
    --output reports/calibration_2024_09_25k_v1.md
```

All input data files are local-only and gitignored (`data/`). No model artifacts were created. No calibrators were fitted. This committed Markdown report (`reports/calibration_2024_09_25k_v1.md`) is the only tracked artifact.

---

## 12. Acceptance Criteria Met

- [x] Calibration diagnostic report exists
- [x] Confidence-accuracy buckets computed for B1, B3, G2
- [x] OvR reliability tables computed for B1, B3, G2
- [x] ECE (OvR) computed for all three classes for each model
- [x] Classwise Brier (OvR) computed for all three classes
- [x] Validation split only used
- [x] No post-hoc calibrators fitted
- [x] No model artifacts saved
- [x] No plots produced
- [x] No new dependencies added
- [x] DRAW sparsity caveat included
- [x] G4 exclusion (near-prior) documented
- [x] G6 exclusion (memorization) documented
- [x] No causal claims made
- [x] No test-set usage
- [x] No local data artifacts staged
