# Phase 7.3B — Modeling Hygiene Hardening

**Ticket:** 7.3B  
**Phase:** 7 — Pre-Phase-8 Hardening  
**Date:** 2026-06-10  
**Owner:** Malachi Wang  

---

## 1. Files Changed

| File | Change |
|---|---|
| `EXPERIMENT_LOG.md` | EXP-001 filter erratum corrected; Phase 8 naming drift fixed (EXP-002–005 Next step lines); EXP-006 added |
| `ROADMAP.md` | Phase 7.3 section added; completed tickets stanza updated |
| `WORKFLOW.md` | §13 Holdout/test-split policy added |
| `reports/phase_reports/dataset_card_lichess_ten_zero_2024_09_25k_v1.md` | C9 caveat: 137 excluded short games documented |
| `src/chess_mhsuc/gbm.py` | G2b added to `_GBM_REGISTRY`; `build_gbm_model` supports early_stopping/validation_fraction/n_iter_no_change from entry; `run_all_gbm` gains `model_ids` filter; `save_gbm_outputs` gains `output_prefix`; CLI adds `--model-ids`, `--output-prefix` |
| `src/chess_mhsuc/bootstrap_ci.py` | New file — 17 functions (A–Q) + CLI |
| `src/chess_mhsuc/gbm_feature_importance.py` | v1-constants warning comment added |
| `src/chess_mhsuc/calibration.py` | v1-constants warning comment added |
| `src/chess_mhsuc/baseline_evaluation.py` | v1-prose warning comment added |
| `tests/test_gbm.py` | Updated `test_exactly_six_entries` → seven; added G2b registry/model tests |
| `tests/test_bootstrap_ci.py` | New file — 44 tests |
| `tests/test_baselines.py` | Added `TestPermutedLabelAntiLeakage` (3 tests) |
| `tests/test_data_integrity.py` | New file — 13 tests |

---

## 2. Summary of Behavior Added/Changed

### Documentation corrections
- **EXP-001 filter erratum:** The EXP-001 dataset filter previously stated
  "Stockfish-annotated positions; broad subset ≥ 1 eval position." This was
  incorrect — broad models have no eval requirement. Corrected to: "games
  reaching first selected checkpoint (ply ≥ 20 / move 10); no eval filter
  on broad subset." An erratum paragraph was appended to EXP-001.
- **Phase 8 naming drift:** EXP-002 through EXP-005 all had Next step lines
  saying "Phase 8 Scaling." Corrected to "Phase 8 Stockfish/eval validation"
  to match ROADMAP.md Phase 8 definition.
- **ROADMAP.md:** Phase 7.3A/7.3B section added with status and ticket details.
  Completed tickets stanza updated to cover Phases 0–7.

### Short-game exclusion documented (C9)
137 games (5.6% of 2,460 clean games) have `n_plies < 20` and produce no
feature-position rows. C9 caveat added to dataset card with breakdown by
result_class and termination type. This is a population-definition conditioning,
not a bug.

### Holdout/test-split policy (WORKFLOW.md §13)
Formal policy documented: validation split is the working evaluation surface;
test split opens at most once per major version. Historical test exposures from
Phases 5.2B, 6.1B stand as records but should not be used for future model
selection.

### G2b — Fair GBM comparison
G2 ran 300 unstopped iterations because `early_stopping='auto'` (sklearn default)
does not activate for n_samples < 10,000 (pilot train: 4,344 rows). G2b is added
as a diagnostic model with `early_stopping=True, validation_fraction=0.15,
n_iter_no_change=10`.

**G2b results (val, primary_numbered, 931 rows):**
- val log_loss: **1.1808** (G2 was 1.2326; improvement: −0.0518)
- val accuracy: 0.4962
- val Brier: 0.6593

G2b is still significantly worse than B3 (log_loss 0.8527). The overfit
diagnosis from Phase 6.1B stands — early stopping helps but cannot overcome
a 4,344-row training set that cannot support the model's capacity.

### Bootstrap CIs
Game-level cluster bootstrap (1,000 replicates, seed=42) for B1, B2, B3, G2, G2b.

Per-model log_loss CIs:

| Model | Val log_loss | 95% CI lower | 95% CI upper | Width |
|---|---|---|---|---|
| B1 | 0.8853 | 0.8279 | 0.9444 | 0.1165 |
| B2 | 0.8740 | 0.8127 | 0.9394 | 0.1267 |
| B3 | 0.8527 | 0.7910 | 0.9170 | 0.1260 |
| G2 | 1.2326 | 1.0687 | 1.4123 | 0.3436 |
| G2b | 1.1808 | 1.0292 | 1.3581 | 0.3289 |

Pairwise delta log_loss CIs (delta = LL(B) - LL(A); negative = B improved):

| Comparison | Point delta | CI lower | CI upper | CI contains zero |
|---|---|---|---|---|
| B1 -> B2 | -0.0112 | -0.0286 | +0.0060 | Yes |
| B2 -> B3 | -0.0214 | -0.0360 | -0.0065 | **No** |
| B3 -> G2 | +0.3799 | +0.2595 | +0.5137 | No |
| B3 -> G2b | +0.3281 | +0.2181 | +0.4542 | No |

Key findings:
- **B2->B3 delta CI excludes zero** [-0.0360, -0.0065]: adding clock features
  to rating-only features produces a statistically resolvable improvement.
- **B1->B2 delta CI contains zero** [-0.0286, +0.0060]: adding rating features
  improves the point estimate but is not statistically resolvable at this N.
- G2b per-model CI [1.0292, 1.3581] overlaps G2 CI [1.0687, 1.4123] substantially.
  G2b improves the point estimate vs G2 but that is not assessed by a paired delta here.
- B3 -> G2b delta CI [+0.2181, +0.4542] excludes zero (in the wrong direction):
  GBM is clearly worse than B3 even with early stopping.

### Warning comments
Warning comments added to three v1 report modules noting that prose metric
values are hardcoded for the v1 pilot dataset and must be re-derived if
dataset version, feature set, or model parameters change.

---

## 3. Assumptions Made

- G2b uses the same FS-E feature set as G2; no other hyperparameters changed.
- `validation_fraction=0.15` is drawn from the training set (4,344 rows),
  giving ~660 early-stopping validation rows and ~3,684 training rows.
- Bootstrap uses the primary_numbered view (excludes `selected_position_type == 'last'`),
  consistent with all broad model evaluations.
- EXP-001 filter erratum was caught from audit 7.3A; no data or model results change.

---

## 4. Tests / Checks Run

- `pytest` (full suite): **1225 passed, 1 warning** (sklearn y_pred classes warning, pre-existing)
- `tests/test_gbm.py`: 120 tests (was 109)
- `tests/test_bootstrap_ci.py`: 79 new tests (was 44; expanded with pairwise delta, B2, report checks)
- `tests/test_baselines.py`: 109 tests (was 106) — includes permuted-label anti-leakage
- `tests/test_data_integrity.py`: 13 new tests
- Deterministic report check: `diff -u` of two CLI runs produces no output

---

## 5. Results of Tests/Checks

All 1225 tests pass. No regressions. Deterministic report confirmed.

---

## 6. Known Risks / Limitations

- G2b is still far from B3. Early stopping is not sufficient at this sample
  size — the architecture / capacity choice (HistGBM with 300 leaves, small
  min_samples_leaf) is likely the root cause.
- Bootstrap CIs are wide at this pilot scale (~348 val games). Do not
  over-interpret interval endpoints.
- The holdout policy documents forward-looking behavior. Historically, test
  metrics were printed by the CLI and logged in reports. No historical results
  are deleted; they are marked as not to be used for future selection.
- DRAW class CIs are dominated by class sparsity (6.3% of val rows, ~59 rows).
  Do not report DRAW-specific metrics as anything other than directional.
- v1 report modules (calibration, baseline_evaluation, gbm_feature_importance)
  have warning comments but have NOT been refactored to remove hardcoded prose
  values. That is a future task if a new dataset version is processed.

---

## 7. Suggested Next Step

**Phase 8 — Stockfish/eval-conditioned modeling.** The hygiene hardening
(7.3B) closes the outstanding infrastructure gaps before scaling. Specifically:

- Bootstrap CIs establish a rigorous baseline: any Phase 8 model must beat
  B3's CI upper bound (0.9170) to be considered a genuine improvement.
- G2b provides a fair GBM baseline for Phase 8 model comparisons.
- WORKFLOW.md §13 formalizes the test-split protocol going forward.
- The 137 short-game exclusion (C9) is documented and should be re-evaluated
  for any new dataset version.
