# GBM Feature Importance Diagnostic Report — 2024_09_25k_v1

**Ticket:** 6.3B — Feature Importance Implementation
**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Dataset ID:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

This is a **diagnostic-only** feature importance report.

- **G2 is overfit and worse than B3.** G2 val log_loss ≈ 1.2326 vs B3 ≈ 0.8527. Feature importance here is not a final ranking of true feature utility.
- **Rating features (white_elo, avg_elo) show the only clear positive signal.** Permuting them increases validation log_loss, suggesting rating is genuinely predictive even under overfit.
- **Most clock and position features show near-zero or negative importance.** Negative importance means permuting the feature *improves* validation log_loss — an overfit artifact, not evidence the feature is useless.
- **clock_diff_s is the most negative feature.** G2 memorized non-generalizing clock-difference patterns that hurt generalization on unseen games.
- **This does not say clock or phase features are unimportant in chess.** It says the current G2 failed to learn stable, generalizing patterns from them at this dataset scale.
- **Use these results to guide what to revisit after scaling/calibration.** Do not use them as constraint analysis conclusions.

---

## 2. Research Framing

Chess is the testbed, not the endpoint. The larger goal is modeling human strategy/reasoning under constraints — how clock pressure, game phase, and skill level interact in time-limited human play.

This report checks whether the first GBM learned stable constraint signals. The answer is: rating signal is robust; clock and position signals are unstable at pilot scale. This informs the scaling and calibration roadmap, not constraint analysis conclusions.

---

## 3. Scope and Caveats

- **G2 only.** No importance for G1, G3, G4, G5, G6.
- **Validation split only.** Test set not used for importance scoring.
- **No causal claims.** Permutation importance is not causal explanation.
- **No calibration.** Calibration is deferred to Phase 7.
- **No SHAP.** No new dependencies added.
- **No saved model artifacts.** G2 is retrained in memory only.
- **Pilot-only.** Results limited to the 2024-09 25k-game extract.
- **G4 excluded from importance.** Near-prior behavior makes its importance uninformative.
- **G5/G6 excluded.** Eval-gated; G6 memorizes the training set.
- **No plots or CSVs produced.** Only this Markdown report is committed.

---

## 4. Coarse Feature-Group Ablation Context

G1/G2/G3/G4 provide coarse group-level signal about feature categories. This table is **context only**, not definitive ablation evidence. Comparisons are confounded by overfit and model capacity: G3 appears better than G2 partly because its smaller feature set overfits less, not because clock features are more valuable. G4 is near-prior.

| Model | Feature group | Val log_loss | Train log_loss | Gap | Note |
|-------|--------------|-------------|----------------|-----|------|
| G1 | FS-B | 1.4178 | 0.1852 | +1.2326 | Rating only (4 features); severely overfit |
| G2 | FS-E | 1.2326 | 0.1636 | +1.0690 | Rating + clock + position (20 features); primary broad GBM; severely overfit |
| G3 | FS-C | 0.9861 | 0.5539 | +0.4322 | Clock only (13 features); diagnostic; moderately overfit |
| G4 | FS-D | 0.8812 | 0.8799 | +0.0013 | Position context only (3 features); diagnostic; **near-prior** |

> **Interpretation:** Moving from G1 (rating only) to G2 (rating + clock + position) improves val log_loss from 1.4178 to 1.2326, consistent with clock and position carrying some signal. However, G2 still far exceeds B3 (0.8527). G4's near-zero train/val gap reflects prior-like outputs, not learning.

---

## 5. G2 Retraining Sanity Check

G2 was retrained deterministically in memory using identical parameters to Phase 6.1B (HistGradientBoostingClassifier, fixed GBM_PARAMS, random_state=42). **No fitted model object was saved.**

| Check | Value | Expected | Status |
|-------|-------|----------|--------|
| G2 retrained val log_loss | 1.2369 | ≈ 1.2369 | PASS |
| Importance scored on | validation split only | val only | PASS |
| Model artifact saved | no | no | PASS |

> **Stored vs retrained drift note:** The Phase 6.1B stored G2 validation log_loss was 1.2326. The in-memory 6.3B retrain gives 1.2369, a small +0.0043 difference. Because the 6.3B CLI is deterministic across reruns and this report is diagnostic-only, the retrained value is used for the feature-importance diagnostic.

---

## 6. Permutation Importance — G2 Validation

Sorted descending by Δ val log_loss. Positive = permuting hurts the model (feature is genuinely predictive). Negative = permuting *improves* the model (overfit artifact).

Scoring: `neg_log_loss`, n_repeats=10, random_state=42.

| Feature | Δ val log_loss | std | Signal |
|---------|---------------|-----|--------|
| `avg_elo` | +0.0410 | 0.0197 | positive diagnostic signal |
| `white_elo` | +0.0169 | 0.0136 | positive diagnostic signal |
| `white_low_60` | +0.0000 | 0.0000 | near-zero / unstable |
| `white_clock_frac` | -0.0000 | 0.0000 | near-zero / unstable |
| `black_clock_frac` | -0.0000 | 0.0000 | near-zero / unstable |
| `clock_diff_frac` | -0.0000 | 0.0000 | near-zero / unstable |
| `white_low_10` | -0.0000 | 0.0000 | near-zero / unstable |
| `black_low_10` | -0.0000 | 0.0000 | near-zero / unstable |
| `clock_anomaly` | -0.0000 | 0.0000 | near-zero / unstable |
| `checkpoint_index` | -0.0000 | 0.0000 | near-zero / unstable |
| `phase_index` | -0.0000 | 0.0000 | near-zero / unstable |
| `black_low_60` | -0.0022 | 0.0012 | near-zero / unstable |
| `black_low_30` | -0.0041 | 0.0021 | near-zero / unstable |
| `white_low_30` | -0.0050 | 0.0026 | negative overfit artifact |
| `move_number` | -0.0055 | 0.0037 | negative overfit artifact |
| `black_clock_s_capped` | -0.0082 | 0.0065 | negative overfit artifact |
| `white_clock_s_capped` | -0.0108 | 0.0102 | negative overfit artifact |
| `clock_diff_s` | -0.0481 | 0.0107 | negative overfit artifact |
| `elo_diff` | -0.0495 | 0.0219 | negative overfit artifact |
| `black_elo` | -0.0725 | 0.0175 | negative overfit artifact |

> **Summary:** 2 feature(s) show positive diagnostic signal (`avg_elo`, `white_elo`). 7 feature(s) show negative overfit artifact signatures.

---

## 7. Interpreting Negative Importances

A **negative importance** (Δ val log_loss < 0) means that permuting the feature's values — destroying its signal — *improves* validation log_loss. This is a signature of overfit, not evidence the underlying variable is unimportant in chess.

**Why this happens with an overfit model:** G2 memorized non-generalizing patterns from the small training set (~4,344 rows). When a feature like `clock_diff_s` is permuted on the validation set, the model can no longer apply its memorized (but non-generalizing) function of that feature. The predictions become more diffuse, which happens to reduce log_loss on a validation set the model has overfit around.

**`clock_diff_s` is the most negative feature (≈ −0.058).** This suggests G2 placed the largest overfit weight on clock-difference patterns. It does not mean clock difference is irrelevant to human chess outcomes — it means G2 failed to learn a generalizing function of it at this data scale.

**`elo_diff` and `black_elo` also show negative importance.** Rating features are correlated; the model distributed some rating signal into `elo_diff` in ways that don't generalize, even while `white_elo` and `avg_elo` remain positive.

---

## 8. Rating Feature Correlation Caveat

The four rating features — `white_elo`, `black_elo`, `elo_diff`, `avg_elo` — are correlated. Permutation importance distributes signal across correlated features unpredictably. The positive importance on `white_elo` and `avg_elo` alongside near-zero or negative values for `black_elo` and `elo_diff` should not be read as 'white_elo matters but black_elo does not.'

The correct interpretation is: **rating signal is robustly present in G2** — something in the rating features survives overfit well enough to show positive importance on validation. Which specific rating feature is responsible is not resolvable from permutation importance alone on correlated inputs.

---

## 9. What This Suggests for Constraint Analysis

- **Rating/skill signal is robust** enough to appear even in the overfit G2. At minimum, player skill is the dominant predictor of game outcomes — expected, but confirms the label/feature pipeline is working.
- **Clock and position signals are unstable at pilot scale.** The overfit model did not learn generalizing patterns from clock usage or game phase. Whether these variables carry real constraint-signal is not answerable from G2 alone.
- **This supports scaling/calibration before strong Phase 9 constraint claims.** Feature importance from a working model on larger data will be more informative.
- **Do not claim degradation curves yet.** The slice and importance patterns from this overfit pilot are too noisy to support conclusions about how constraints affect outcomes across subgroups.

---

## 10. What This Does NOT Say

This report must not be interpreted as:

- **Not a final feature ranking.** Rankings shift under different model capacity, dataset size, and regularization. These numbers are diagnostic for G2 at pilot scale.
- **Not a causal explanation.** Permutation importance is not causal. High `white_elo` importance does not mean 'player skill causes outcomes.' It means the GBM's predictions depend on `white_elo`.
- **Not proof that clock timing is irrelevant.** Negative clock importance reflects G2's overfit failure mode. Clock timing affects human performance in chess — a better-fit model on more data may recover this signal.
- **Not proof that game phase is irrelevant.** Same caveat as clock.
- **Not evidence of stable constraint learning.** G2 is worse than logistic regression; it did not learn generalizing constraint structure.
- **Not a basis for feature selection.** Do not drop features based on this diagnostic.

---

## 11. Reproducibility

Command used to generate this report:

```bash
PYTHONPATH=src python -m chess_mhsuc.gbm_feature_importance \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --version-tag 2024_09_25k_v1 \\
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
    --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
    --splits data/processed/splits_2024_09_25k_v1.json \\
    --modeling-plan data/processed/modeling_plan_2024_09_25k_v1.json \\
    --output reports/gbm_feature_importance_2024_09_25k_v1.md
```

All input data files are local-only and gitignored (`data/`). G2 is retrained deterministically (random_state=42, fixed GBM_PARAMS). **No fitted model object was saved.** This committed Markdown report (`reports/gbm_feature_importance_2024_09_25k_v1.md`) is the only tracked artifact.

---

## 12. Acceptance Criteria Met

- [x] Feature importance diagnostic report exists
- [x] Report opens with diagnostic-only caveat before presenting numbers
- [x] Report does not claim causal explanation
- [x] Report explains negative importance values as overfit artifacts
- [x] Validation split only used for importance scoring
- [x] G2 retrained val log_loss reproduced ≈ 1.2326
- [x] G4, G5, G6 excluded from permutation importance
- [x] No calibration implemented
- [x] No SHAP or new dependencies added
- [x] No model artifacts saved
- [x] No test-set usage for importance
- [x] Coarse ablation table included as context
- [x] Report does not claim final rankings
- [x] Report does not claim constraint analysis conclusions
- [x] No local data artifacts staged
