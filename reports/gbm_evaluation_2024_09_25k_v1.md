# GBM Evaluation Report — 2024_09_25k_v1

**Ticket:** 6.2B — GBM Evaluation Implementation
**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION
**Date:** 2026-06-08
**Dataset ID:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

The first GBM experiment produced a clear negative/diagnostic result:

- **G2 (primary broad GBM) did not beat B3** (best broad logistic baseline). G2 val log_loss ≈ 1.2326 vs B3 ≈ 0.8527.
- **G2 overfit badly.** Training log_loss ≈ 0.164 vs validation ≈ 1.233: the model memorised the small training set.
- **G4 looks numerically closer to B3** (val log_loss ≈ 0.881) but is a near-prior diagnostic model — not a winner.
- **G6 memorised the tiny eval training set.** Train log_loss ≈ 0.004; val log_loss ≈ 1.641.
- **Slice diagnostics are feasible but noisy** at this dataset size.
- This is a controlled diagnostic result, not a project failure. It defines what must be addressed before scaling: more data, regularisation tuning, or calibration.

---

## 2. Research Framing

Chess is the testbed, not the endpoint. The larger goal of this project is modeling human strategy/reasoning under constraints — how clock pressure, game phase, and skill level interact to determine outcomes in time-limited human play.

GBM evaluation here is used to determine whether the first nonlinear model gives a reliable reference point before deeper constraint analysis. It does not. This is expected for a pilot-scale dataset and informs the scaling roadmap.

---

## 3. Dataset and Artifact Context

| Field | Value |
|-------|-------|
| dataset_id | `lichess_ten_zero_2024_09_25k_v1` |
| version_tag | `2024_09_25k_v1` |
| Source | Lichess standard rated 10+0, 2024-09 pilot extract |
| Split method | game_id-level, 70/15/15, seed=42, stratified by result_class |
| Broad primary train rows | 4,344 |
| Broad primary val rows | 931 |
| Broad primary test rows | 930 |
| Eval primary train rows | 645 |
| Eval primary val rows | 147 |
| Eval primary test rows | 140 |
| Primary view | Excludes `selected_position_type == 'last'` |

**Data artifacts:** All Parquet/JSON data files are local-only and gitignored. Only this Markdown report is committed to the repository.

**Pilot-only caveat:** All conclusions are limited to the 2024-09 25k-game extract. Results may not generalise to larger datasets or different time controls.

**Eval subset bias:** The eval subset is gated on Stockfish annotation availability, introducing selection bias (~+20 Elo vs broad). Eval and broad models are not directly comparable.

**DRAW sparsity:** DRAW represents ~6% of broad val rows (~59/931). All accuracy-based metrics can hide DRAW failure.

---

## 4. GBM Model Inventory

| ID | FS | Table | Role | n_train | n_feat | Dropped | Notes |
|----|----|----|------|---------|--------|---------|-------|
| G1 | FS-B | broad | primary | 4344 | 4 | — | Rating features only |
| G2 | FS-E | broad | primary | 4344 | 20 | selected_position_type, phase | Rating + clock + position; **primary broad GBM** |
| G3 | FS-C | broad | diagnostic | 4344 | 13 | — | Clock features only; diagnostic ablation |
| G4 | FS-D | broad | diagnostic | 4344 | 3 | selected_position_type, phase | Position context only (move#, checkpoint, phase); near-prior |
| G5 | FS-F | eval | exploratory | 645 | 7 | selected_position_type, phase | Eval features + position; eval-gated exploratory |
| G6 | FS-G | eval | exploratory | 645 | 24 | selected_position_type, phase | All features incl. eval; eval-gated exploratory |

All models: `HistGradientBoostingClassifier`, fixed params (max_iter=300, lr=0.05, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0.1, random_state=42). No tuning, no calibration.

---

## 5. Metric Policy Reminder

- **Primary metric: validation log_loss.** Lower is better.
- macro_f1 and per-class metrics (especially DRAW) also reported.
- Multiclass Brier score helps diagnose probability quality.
- Accuracy is secondary — misleading when DRAW is ~6% of rows.
- Test metrics are held out and are not used for model selection.
- Confidence bucket table is a diagnostic only — no calibration is fitted.

---

## 6. Primary Broad GBMs vs B3 Baseline

B3 is the best broad logistic baseline from Phase 5.3B. G2 uses the same feature set (FS-E) and is the direct apples-to-apples comparison.

| Model | Role | Val log_loss | Val macro_f1 | Val acc | Val Brier | DRAW recall | DRAW support |
|-------|------|-------------|-------------|---------|----------|-------------|--------------|
| **B3** *(reference)* | broad LR baseline | 0.8527 | 0.3702 | 0.5381 | 0.5338 | 0.0000 | 59 |
| G1 | broad primary GBM | 1.4178 | 0.3246 | 0.4662 | 0.7508 | 0.0000 | 59 |
| G2 | broad primary GBM | 1.2326 | 0.3458 | 0.4995 | 0.6817 | 0.0000 | 59 |

> **G2 does not beat B3.** G2 validation log_loss = 1.2326 vs B3 = 0.8527. G2 is worse than B3 on every reported metric. This is a controlled diagnostic result, not a project failure. The large train/val gap (G2 train log_loss ≈ 0.164) confirms the model has overfit the small pilot training set (~4,344 rows).

---

## 7. Broad Diagnostic GBMs (G3, G4)

These models are **diagnostic only** and are not compared to B3 as performance claims.

| Model | Role | Val log_loss | Val macro_f1 | Val acc | Val Brier | DRAW recall | DRAW support |
|-------|------|-------------|-------------|---------|----------|-------------|--------------|
| G3 | broad diagnostic GBM | 0.9861 | 0.3407 | 0.4930 | 0.6076 | 0.0000 | 59 |
| G4 | broad diagnostic GBM | 0.8812 | 0.3239 | 0.4780 | 0.5563 | 0.0000 | 59 |

**G3 (FS-C, clock features only):** Clock features alone show moderate overfit (train/val gap ≈ +0.432). Clock carries signal but is insufficient on its own.

**G4 (FS-D, position context only — move number, checkpoint, phase):**
G4 has the best broad-GBM validation log_loss numerically (≈ 0.881), but this is because G4 is a **near-prior / degenerate model**. Its predicted probabilities span a very narrow range (p_BLACK_WIN ≈ 0.45–0.48, p_DRAW ≈ 0.05–0.11, p_WHITE_WIN ≈ 0.44–0.48); mean max-probability ≈ 0.476. G4 has learned to output the training class prior conditioned on game phase and checkpoint position, but does not discriminate individual games. Its near-zero train/val gap reflects this prior-like behaviour, not genuine generalisation. **G4 must not be called the best or winning GBM.**

---

## 8. Eval-Gated Exploratory GBMs (G5, G6)

G5 and G6 are **exploratory only**. They use a gated eval subset (Stockfish-annotated games), which is not directly comparable to broad models. Eval val/test splits have very sparse DRAW support (~14 val rows for DRAW).

| Model | Role | Val log_loss | Val macro_f1 | Val acc | Val Brier | DRAW recall | DRAW support |
|-------|------|-------------|-------------|---------|----------|-------------|--------------|
| G5 | eval exploratory GBM | 1.1854 | 0.3687 | 0.5102 | 0.6321 | 0.0714 | 14 |
| G6 | eval exploratory GBM | 1.6409 | 0.3936 | 0.5986 | 0.6331 | 0.0000 | 14 |

**G5 (eval_only features):** Significant overfit (train/val gap ≈ +0.763). Eval features carry signal but the eval training set (645 rows) is too small.

**G6 (all features including eval):** Train log_loss ≈ 0.004 — **complete memorisation** of 645 training rows. Val log_loss ≈ 1.641. G6 is a calibration/overfitting failure case. Eval-gated results must not be used to claim that eval features work broadly.

---

## 9. Overfitting Diagnosis

| Model | Train LL | Val LL | Gap | Interpretation |
|-------|----------|--------|-----|----------------|
| G1 | 0.1852 | 1.4178 | +1.2326 | Severe overfit — rating features memorised |
| G2 | 0.1636 | 1.2326 | +1.0690 | Severe overfit — primary broad GBM, far worse than B3 on val |
| G3 | 0.5539 | 0.9861 | +0.4322 | Moderate overfit — clock-only diagnostic |
| G4 | 0.8799 | 0.8812 | +0.0013 | Near-zero gap — near-prior behaviour, not genuine generalisation |
| G5 | 0.4229 | 1.1854 | +0.7625 | Significant overfit — eval-gated, small training set |
| G6 | 0.0036 | 1.6409 | +1.6373 | Complete memorisation — train_ll≈0.004, catastrophic val overfit |

The train/val gap is the primary overfitting signal. G1 and G2 have gaps > 1.0 — they have memorised the training set. G6 has effectively zero training loss, indicating complete memorisation of 645 eval training rows. Only G4 shows a small gap, but as noted above, this reflects near-prior behaviour rather than genuine learning.

---

## 10. Confidence Bucket Diagnostic (G2 Validation)

This table shows accuracy by model confidence bucket for G2 validation rows. **This is a diagnostic only — no calibration is fitted here.** Calibration belongs in Phase 7.

| Confidence bucket | n | Avg confidence | Accuracy |
|-------------------|---|----------------|----------|
| 0.4–0.5 | 25 | 0.4806 | 0.4800 |
| 0.5–0.6 | 185 | 0.5487 | 0.4324 |
| 0.6–0.7 | 182 | 0.6462 | 0.4890 |
| 0.7–0.8 | 171 | 0.7509 | 0.4912 |
| 0.8–0.9 | 193 | 0.8507 | 0.4974 |
| 0.9–1.0 | 175 | 0.9494 | 0.5943 |

The confidence/accuracy relationship is weak and non-monotone, consistent with a miscalibrated overfit model. High-confidence predictions (0.9–1.0) are somewhat more accurate but the overall pattern is unreliable.

---

## 11. DRAW Class Analysis

| Model | Table | Role | DRAW recall | DRAW precision | DRAW F1 | DRAW support |
|-------|-------|------|-------------|----------------|---------|--------------|
| G1 | broad | primary | 0.0000 | 0.0000 | 0.0000 | 59 |
| G2 | broad | primary | 0.0000 | 0.0000 | 0.0000 | 59 |
| G3 | broad | diagnostic | 0.0000 | 0.0000 | 0.0000 | 59 |
| G4 | broad | diagnostic | 0.0000 | 0.0000 | 0.0000 | 59 |
| G5 | eval | exploratory | 0.0714 | 0.0833 | 0.0769 | 14 |
| G6 | eval | exploratory | 0.0000 | 0.0000 | 0.0000 | 14 |

All broad GBMs (G1–G4) predict 0 DRAW rows on validation. This mirrors the behaviour of unweighted logistic regression baselines. DRAW remains structurally weak at this dataset size and class distribution. Accuracy metrics can hide this failure entirely — macro_f1 and per-class recall are required to see it.

---

## 12. Slice Analysis — G2 Validation

G2 is used for slice analysis because it is the primary broad GBM. All slices are on the **validation set** only.

**Caveats:** phase and move_number are correlated (opening≈move_10, endgame≈move_40). is_time_forfeit has limited support (~102 True rows). has_eval is a coverage/bias proxy, not a causal predictor. avg_elo buckets are noisy (n=82–194 per bucket); the pattern should not be over-interpreted at this sample size.

**Phase**

| phase | n | Accuracy |
|---|---|---|
| endgame | 107 | 0.5607 |
| middlegame | 476 | 0.5000 |
| opening | 348 | 0.4799 |

**Move number**

| move_number | n | Accuracy |
|---|---|---|
| 10 | 348 | 0.4799 |
| 20 | 289 | 0.4948 |
| 30 | 187 | 0.5080 |
| 40 | 107 | 0.5607 |

**Time forfeit (is_time_forfeit)**

| is_time_forfeit | n | Accuracy |
|---|---|---|
| False | 829 | 0.4910 |
| True | 102 | 0.5686 |

**Has eval annotation (has_eval)**

| has_eval | n | Accuracy |
|---|---|---|
| False | 784 | 0.5242 |
| True | 147 | 0.3673 |

**avg_elo bucket** _Join: 931/931 rows matched (0 nulls)._

| avg_elo bucket | n | Accuracy |
|---|---|---|
| <1200 | 166 | 0.5000 |
| 1200–1400 | 126 | 0.5556 |
| 1400–1600 | 187 | 0.3850 |
| 1600–1800 | 194 | 0.5567 |
| 1800–2000 | 176 | 0.5000 |
| >2000 | 82 | 0.5366 |

Slice accuracy varies across groups but no single slice dominates. The patterns are consistent with a noisy pilot dataset and should not be treated as degradation curves or reliable constraint findings yet.

---

## 13. Held-Out Test Snapshot

> **Test metrics are not used for model selection.** This is a one-time held-out snapshot for record-keeping only. Do not tune models based on test results.

| Model | Test log_loss | Test acc | Test Brier | Test macro_f1 | Note |
|-------|---------------|----------|------------|---------------|------|
| G2 | 1.1796 | 0.5129 | 0.6532 | 0.4375 | primary broad GBM |
| B3 *(reference)* | 0.8552 | 0.5204 | 0.5331 | 0.3571 | broad LR baseline |

---

## 14. Key Findings

1. **G2 does not beat B3.** G2 val log_loss=1.2326 vs B3=0.8527. G2 is worse on every reported metric.
2. **G1 and G2 overfit strongly.** Train/val log_loss gaps exceed +1.0.
3. **G4 is a near-prior diagnostic model**, not a competitive predictor. Its apparent proximity to B3 in val log_loss reflects prior-like output, not genuine generalisation.
4. **G6 memorises the eval training set.** Train log_loss ≈ 0.004; catastrophic val overfit.
5. **Broad GBMs still fail DRAW.** G1–G4 all predict 0 DRAW on validation. DRAW class failure is not addressed by fixed unweighted HistGBM on this data.
6. **Slice diagnostics are feasible but noisy** at this dataset scale. No single slice dominates; elo-bucket patterns should not be over-interpreted.
7. **More data, regularisation adjustment, and/or calibration may be needed** before claiming nonlinear gains over logistic regression.

---

## 15. Recommended Next Steps

- **6.3A — Feature Importance Audit:** Audit before implementing. Note that the current GBM is weak/overfit — feature importances from G2 are computed on an overfit model and may not be reliable.
- **Phase 7 — Calibration:** Calibration assessment remains a separate audit/implementation phase. The confidence bucket diagnostic in this report provides motivation; actual calibration fitting is deferred.
- **Phase 8 — Scaling:** The negative GBM result most likely reflects insufficient training data (~4,344 broad primary rows) for a flexible nonlinear model. Scaling the dataset is the most direct path to GBM gains.
- **Phase 9 — Constraint analysis:** Should wait for a more robust model and/or larger dataset. Slice findings from the current overfit GBM would be unreliable inputs to constraint conclusions.
- **No neural networks in current scope.** Not justified at this data scale.

---

## 16. Reproducibility

Command used to generate this report:

```bash
PYTHONPATH=src python -m chess_mhsuc.gbm_evaluation \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --version-tag 2024_09_25k_v1 \\
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
    --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
    --output reports/gbm_evaluation_2024_09_25k_v1.md
```

All input data files are local-only and gitignored (`data/`). This committed Markdown report (`reports/gbm_evaluation_2024_09_25k_v1.md`) is the tracked artifact.

---

## 17. Acceptance Criteria Met

- [x] GBM evaluation report exists
- [x] Report compares broad GBMs against B3
- [x] Report identifies G2 as primary broad GBM
- [x] Report states G2 does not beat B3 by validation log_loss
- [x] Report notes G4 as diagnostic/near-prior, not winner
- [x] Report separates broad (G1–G4) and eval-gated (G5/G6) GBMs
- [x] Report includes train/val overfitting table
- [x] Report includes DRAW class analysis
- [x] Report includes confidence bucket diagnostic (not calibration)
- [x] Report includes phase, move_number, is_time_forfeit, has_eval slices
- [x] Report includes avg_elo bucket slice (or skip note if feature-broad absent)
- [x] Report includes held-out test snapshot, not used for model selection
- [x] Report does not implement calibration
- [x] Report does not implement feature importance
- [x] Report does not claim eval GBMs are better overall
- [x] No local data artifacts staged
