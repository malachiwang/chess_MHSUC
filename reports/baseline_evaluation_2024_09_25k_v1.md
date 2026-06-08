# Baseline Evaluation Report

**Ticket:** 5.3B — Baseline Evaluation Report
**Labels:** ML/REPORTING | D2 | IMPLEMENTATION
**Date:** 2026-06-07
**dataset_id:** `lichess_ten_zero_2024_09_25k_v1`
**version_tag:** `2024_09_25k_v1`

---

## 1. Context

Chess is the testbed for this pilot project. The goal is to predict game
outcomes (White win / Draw / Black win) from mid-game position snapshots
of human chess games played on Lichess (10+0 time control).

This work is a study of human strategy/reasoning under time pressure, not
engine evaluation. Clock usage, position complexity, and material balance
are all candidate signals.

This document summarises the Phase 5.2B baseline models (DummyClassifier +
LogisticRegression) as reported in `baseline_results_2024_09_25k_v1.json`.
Broad and eval-gated baseline results are not directly comparable: the eval
subset is gated on Stockfish annotation availability, which introduces
selection bias (~+20 Elo vs broad).

---

## 2. Baseline Inventory

| ID | Model | FS | Table | Expl | Diag | Val log_loss | Val acc |
|----|-------|----|-------|------|------|--------------|---------|
| B0 | DummyClassifier | FS-A | broad | N | N | 18.8929 | 0.4758 |
| B1 | DummyClassifier | FS-A | broad | N | N | 0.8853 | 0.4758 |
| B2 | LogisticRegression | FS-B | broad | N | N | 0.8740 | 0.5124 |
| B3 | LogisticRegression | FS-E | broad | N | N | 0.8527 | 0.5381 |
| B4 | LogisticRegression | FS-F | eval | Y | N | 0.7833 | 0.5918 |
| B5 | LogisticRegression | FS-G | eval | Y | N | 0.8598 | 0.6190 |
| B3-balanced | LogisticRegression | FS-E | broad | Y | Y | 1.0623 | 0.4393 |

---

## 3. Validation Comparison (Broad Primary Baselines)

Sorted ascending by validation log_loss. Primary metric: log_loss.
Accuracy is secondary (misleading when DRAW class is ~6% of rows).

| ID | Model | FS | Expl | Diag | Val log_loss | Val acc | Val brier | Val macro_f1 |
|----|-------|----|------|------|--------------|---------|-----------|--------------|
| B3 | LogisticRegression | FS-E | N | N | 0.8527 | 0.5381 | 0.5338 | 0.3702 |
| B2 | LogisticRegression | FS-B | N | N | 0.8740 | 0.5124 | 0.5483 | 0.3521 |
| B1 | DummyClassifier | FS-A | N | N | 0.8853 | 0.4758 | 0.5573 | 0.2149 |
> **Note:** B0 (DummyClassifier `most_frequent`) is excluded from this table: it predicts p=1.0 for the majority class, giving log_loss ≈ 18.9. This is expected behaviour. B0 is not directly comparable to probabilistic classifiers and is shown only in the inventory table.

---

## 4. Signal Decomposition

Signal decomposition: incremental log_loss improvement as features are added
(validation set, broad split, primary_numbered view).

| Model | Features added | Val log_loss | Δ vs prior |
|-------|----------------|--------------|------------|
| B1 | Prior (label frequencies only) | 0.8853 | — |
| B2 | + game metadata (FS-B) | 0.8740 | -0.0112 |
| B3 | + clock + position (FS-E) | 0.8527 | -0.0214 |

Full B1→B3 improvement: -0.0326 log_loss units. Clock timing and position context carry real predictive signal. However, all broad baselines predict 0 DRAW rows (minority class ~6% of rows), so accuracy is misleading. Log_loss is the primary metric.

---

## 5. Diagnostic Baseline: B3-balanced

| ID | Model | FS | Expl | Diag | Val log_loss | Val acc | Val brier | Val macro_f1 |
|----|-------|----|------|------|--------------|---------|-----------|--------------|
| B3-balanced | LogisticRegression | FS-E | Y | Y | 1.0623 | 0.4393 | 0.6427 | 0.3738 |
> **Note:** B0 (DummyClassifier `most_frequent`) is excluded from this table: it predicts p=1.0 for the majority class, giving log_loss ≈ 18.9. This is expected behaviour. B0 is not directly comparable to probabilistic classifiers and is shown only in the inventory table.

B3-balanced is a diagnostic variant of B3 with `class_weight='balanced'`.
It improves DRAW recall but at a substantial log_loss cost (1.0623 vs 0.8527).
DRAW support is ~59 rows in the broad validation set (~6%). DRAW metrics are
noisy and should be interpreted cautiously.

### B3 and B3-balanced confusion matrices (validation set)

**B3 confusion matrix (val split):**

| Actual \ Pred | BW | D | WW |
|---|---|---|---|
| **BLACK_WIN** | 265 | 0 | 178 |
| **DRAW** | 23 | 0 | 36 |
| **WHITE_WIN** | 193 | 0 | 236 |

**B3-balanced confusion matrix (val split):**

| Actual \ Pred | BW | D | WW |
|---|---|---|---|
| **BLACK_WIN** | 186 | 111 | 146 |
| **DRAW** | 13 | 19 | 27 |
| **WHITE_WIN** | 134 | 91 | 204 |

---

## 6. Test Snapshot (Broad Primary Baselines)

| ID | Test log_loss | Test acc | Test brier | Test macro_f1 |
|----|---------------|----------|------------|---------------|
| B3 | 0.8552 | 0.5204 | 0.5331 | 0.3571 |
| B2 | 0.8675 | 0.5118 | 0.5425 | 0.3499 |
| B1 | 0.8832 | 0.4806 | 0.5564 | 0.2164 |
> **Note:** Test set results are reported here once for record-keeping. Do not use test metrics to select or tune models.

---

## 7. Eval Baselines (Exploratory — Not Comparable to Broad)

Eval baselines use a gated subset of games with Stockfish evaluations.
Results are exploratory. Eval val/test have very sparse DRAW support
(~4 val / ~2 test DRAW rows). Broad and eval-gated baseline results
are not directly comparable.

| ID | Model | FS | Expl | Diag | Val log_loss | Val acc | Val brier | Val macro_f1 |
|----|-------|----|------|------|--------------|---------|-----------|--------------|
| B4 | LogisticRegression | FS-F | Y | N | 0.7833 | 0.5918 | 0.4685 | 0.3614 |
| B5 | LogisticRegression | FS-G | Y | N | 0.8598 | 0.6190 | 0.4919 | 0.3958 |
> **Note:** B0 (DummyClassifier `most_frequent`) is excluded from this table: it predicts p=1.0 for the majority class, giving log_loss ≈ 18.9. This is expected behaviour. B0 is not directly comparable to probabilistic classifiers and is shown only in the inventory table.

---

## 8. Key Findings

1. **Best broad primary baseline:** B3 (LogisticRegression, FS-E) with val log_loss=0.8527, val acc=0.5381.
2. Clock and position features (B2→B3) provide a real but modest improvement.
3. All unweighted broad baselines predict 0 DRAW rows (minority class ~6%).
4. B3-balanced improves DRAW recall at a substantial log_loss cost.
5. Eval baselines show higher test accuracy due to eval-feature signal,
   but the eval test set is tiny (~53 rows, ~2 DRAW rows); spike unreliable.
6. No broad baseline achieves log_loss below 0.85. This sets the floor for
   Phase 6 GBM experiments.

---

## 9. Recommended Next Step

Phase 6 GBM experiments should aim to beat the B3 validation log_loss of
0.8527 on the broad split.
Calibration (Phase 6.2) should be assessed for any model that substantially
improves on the baseline floor.
