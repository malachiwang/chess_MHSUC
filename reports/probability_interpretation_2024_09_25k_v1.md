# Probability Interpretation Guardrails Report — 2024_09_25k_v1

**Ticket:** 7.2B — Probability Interpretation Report Implementation
**Labels:** REPORTING/ML | D1 | IMPLEMENTATION
**Dataset ID:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

This report defines what model probabilities mean and do not mean, and establishes guardrails for how they may be used in future phases.

Chess is the testbed, not the endpoint. The larger project is modeling human strategy/reasoning under constraints. Before future phases can make claims about how time pressure, game phase, or rating affect outcomes, they need a clear statement of what current probabilities are and are not.

Key guardrails:

- **B3 is the safest current broad probability model.** Val log_loss = 0.8527. Moderately calibrated for BLACK_WIN/WHITE_WIN (ECE ≈ 0.026–0.033).
- **B3 is only cautiously usable for BLACK_WIN and WHITE_WIN.** DRAW probabilities from B3 are unreliable.
- **G2 probabilities are not trustworthy for interpretation.** G2 val log_loss = 1.2326 with overfit gap = +1.0690. ECE BLACK_WIN/WHITE_WIN ≈ 0.234–0.203.
- **B1's low ECE is a trap.** B1 predicts only class priors; appearing calibrated does not make it useful.
- **Current probabilities are human empirical outcome estimates, not engine evaluations or causal effects.**
- **No constraint-effect claims are established yet.** Phase 8 and Phase 9 are required before any causal or subgroup conclusions.

---

## 2. What a Predicted Probability Means

For a selected mid-game checkpoint position with available features (player ratings, clock state, move number, game-phase proxy), the model estimates the probability that the game eventually ends in **BLACK_WIN / DRAW / WHITE_WIN**, among human games in the sampled **Lichess 10+0 (600+0) population** with similar feature values.

More precisely:

- **`p_BLACK_WIN`**: model-estimated empirical probability that Black wins the game, conditional on the features available at this checkpoint.
- **`p_DRAW`**: model-estimated empirical probability that the game ends as a draw.
- **`p_WHITE_WIN`**: model-estimated empirical probability that White wins the game.

These probabilities are:

- **Human-behavior-conditioned.** They reflect how human Lichess players in this time control tend to resolve games from similar feature contexts, not how an engine would play from the same position.
- **Feature-conditioned empirical frequencies.** They estimate outcome rates conditional on the features the model was given — rating, clock, move number, and phase proxy. They are not conditioned on the full board position or engine evaluation (for broad models).
- **Checkpoint-level estimates.** Predictions come from selected positions (after move 10/20/30/40 or the last available pre-result position), not from every ply. They are snapshots, not continuous trajectory estimates.
- **Sampled-population probabilities.** They are specific to the 2024-09 Lichess 10+0 pilot extract. Generalization to other time controls, rating ranges, or populations is not established.

---

## 3. What a Predicted Probability Does NOT Mean

Current model probabilities are **not**:

- **Not objective engine evaluation.** Broad models (B3, G2) do not use Stockfish evaluation. A high p_WHITE_WIN can reflect a large rating advantage, not an objectively winning position.
- **Not a true game-theoretic win probability.** Human outcomes depend on player fatigue, time pressure, blunder probability, and psychology — not on minimax search. These estimates reflect human behavior, not perfect-play analysis.
- **Not a causal effect.** A higher p_WHITE_WIN when clock < 30s does not prove that time pressure causes White to win more. It is a correlation in the training data, potentially confounded by rating, game phase, and position selection.
- **Not a stable out-of-sample guarantee.** These probabilities are conditioned on the specific 2024-09 Lichess 10+0 pilot extract. Generalization to other time controls, rating ranges, or years is not established.
- **Not a full trajectory probability from every ply.** Predictions are made at selected checkpoints only (after move 10/20/30/40 or the last pre-result position). They do not describe how probability evolves continuously through a game.
- **Not a final constraint-effect measurement.** Subgroup comparisons (e.g., probability by rating bucket, by clock pressure, by phase) are descriptive patterns in a small pilot dataset, not validated constraint findings.

---

## 4. Current Model Trustworthiness Summary

| Model | Type | Val log_loss | Status |
| --- | --- | --- | --- |
| B1 | DummyClassifier (prior) | 0.8853 | Prior reference only. Low ECE is a trap. |
| **B3** | LogisticRegression (FS-E) | 0.8527 | **Safest current broad model.** Cautious use only. |
| G2 | HistGBM (FS-E) | 1.2326 | Not trustworthy. Overfit, overconfident. |
| G4 | HistGBM (FS-D) | 0.881 | Deceptive near-prior. Not useful. |
| G5/G6 | HistGBM (FS-F/G, eval-gated) | 1.185 / 1.641 | Selection-biased. G6 memorizes. Not broad. |
| B3-balanced | LR class_weight=balanced | 1.062 | Class-weight diagnostic. Not probability-calibrated. |
| B4/B5 | LR (eval-gated, exploratory) | 0.783 / 0.860 | Eval-gated, biased. Not for broad claims. |

> Note: log_loss values are from the validation split on the broad primary_numbered view. B4/B5/G5/G6 are restricted to eval-annotated positions (~13.7% of positions) and are not comparable to broad model values.

---

## 5. B1 Interpretation — The Low-ECE Trap

B1 has ECE ≈ 0.0023 for BLACK_WIN — lower than B3's 0.0260. This is not evidence that B1 is a better probability model.

B1 predicts the class prior for every single row: approximately 47.6% BLACK_WIN, 6.3% DRAW, 46.1% WHITE_WIN. It assigns the same probability regardless of position, rating, or clock state.

Its low ECE occurs because validation class frequencies happen to approximately match the training class prior. Any model that ignores all features and always outputs the prior will show low ECE when the class distribution is stable across splits.

**This is a known pitfall in calibration evaluation:** ECE alone does not measure whether a model is informative. A perfectly uninformative model that predicts the marginal class frequency can appear well-calibrated.

**B1 is useful only as a base-rate reference.** It establishes the prior probability floor. Any model that does not beat B1 in log_loss has not learned meaningful signal beyond class frequencies.

---

## 6. B3 Interpretation — Safest Current Broad Model

B3 (LogisticRegression on FS-E) achieves val log_loss = 0.8527, the best of all broad models. Its probability spread is meaningful: p_WHITE_WIN has mean ≈ 0.458, std ≈ 0.118, ranging up to 0.980 for large rating gaps.

**Calibration:** ECE for BLACK_WIN ≈ 0.0260 and WHITE_WIN ≈ 0.0327 indicate moderate calibration for these classes. DRAW ECE ≈ 0.0009 appears small but is misleading — see Section 8.

**What B3 probabilities capture:** Primarily the effect of rating differential on outcome probability. Clock and position features contribute additional signal, but their individual effects are not isolated in the current model.

**Safe use:** B3 BLACK_WIN/WHITE_WIN probabilities may be cited descriptively as rough outcome scores, subject to the following conditions:

1. Explicitly label as 'pilot-scale, descriptive, not causal'.
2. Cite that broad models do not use engine evaluation.
3. Never interpret B3 DRAW probabilities as meaningful.
4. Do not use B3 for final constraint analysis — that requires Phase 8/9.
5. Do not call B3 'calibrated' without caveats about its limitations.

---

## 7. G2 Interpretation — Negative Example of Overfit Overconfidence

G2 (HistGBM on FS-E): train log_loss = 0.1636, val log_loss = 1.2326, overfit gap = +1.0690. G2 does not beat B3 on any metric. It is worse than logistic regression because the small pilot dataset (~4,344 train rows) is insufficient to support the nonlinear capacity of a gradient-boosted model.

ECE: BLACK_WIN = 0.2338, WHITE_WIN = 0.2034. G2 probability spread: p_WHITE_WIN std ≈ 0.289 (compared to B3 std ≈ 0.118). G2's wider spread is not a sign of richer signal — it is a sign of overfit noise pushing predictions toward the extremes.

In G2's [0.9, 1.0] top-label confidence bucket (n=175): mean confidence = 0.949, accuracy = 0.594, gap = +0.355. G2 assigns very high confidence to predictions that are correct barely more than half the time. This is overfit overconfidence: the model learned to be extremely certain about training patterns that do not generalize.

**G2 probabilities must not be used for downstream interpretation, probability claims, or constraint analysis.** G2 is documented here as a reference case illustrating what miscalibrated overconfidence looks like in a small-data GBM.

---

## 8. DRAW Probability Caveat

DRAW is sparse: 59/931 validation rows (6.3%). This imbalance means DRAW is systematically under-modeled in every current model.

**All current models keep p_DRAW near the class prior for almost every row.** B3 p_DRAW has std ≈ 0.025, max ≈ 0.168. The model rarely assigns p_DRAW above 0.15, regardless of position.

B3 DRAW ECE ≈ 0.0009 — extremely small, but this is misleading. When a model outputs near-zero p_DRAW for nearly every row and the true DRAW rate is also low (~6.3%), the OvR calibration error is trivially small even if the model has no DRAW-discriminating power.

**DRAW probability interpretation rules:**

- Do not interpret p_DRAW values from any current model.
- Do not cite DRAW ECE as evidence of DRAW calibration.
- Acknowledge that DRAW is not currently modeled.
- Future work (more data, class rebalancing, or alternative DRAW indicators) is required before DRAW probabilities can be discussed.

---

## 9. Probability vs Engine Evaluation

Broad models (B1 through B3, G1 through G4) **do not use Stockfish evaluation at all.** Their probabilities are conditioned solely on rating, clock, and position-context features.

This creates a crucial distinction:

- A position where White has a 400-Elo rating advantage may receive high p_WHITE_WIN from B3 regardless of whether the position is objectively advantageous.
- A position that is objectively lost for Black (by engine analysis) may receive balanced B3 probabilities if the rating gap is small.
- B3 probabilities reflect **human outcome frequencies under observed feature conditioning**, not objective chess truth.

Eval-gated models (B4/B5 for LR, G5/G6 for GBM) add Stockfish evaluation features but are restricted to the ~13.7% of positions with eval annotations — a selection-biased subset with avg_elo ≈ +20 Elo vs the broad population. These models are exploratory and cannot support broad population claims.

**Phase 8 (Stockfish validation)** will assess whether conclusions from broad models align with objectively evaluated positions. Until then, broad model probabilities must not be framed as engine-based win assessments.

---

## 10. Probability vs Causal Constraint Claims

The project's core hypothesis is that human outcomes depend on constraints (clock pressure, game phase, rating, position complexity). Future phases may want to claim: 'under time pressure, players convert winning positions less often.'

**Current probabilities do not support such claims.** Here is why:

- **Observational confounding.** Clock state, rating, and game phase are correlated in the training data. A model that sees 'low clock → lower p_WHITE_WIN' may simply be capturing the confound that lower-rated players run low on time more often.
- **No causal design.** We have not constructed matched samples, controlled experiments, or instrumental variables. Probability differences across subgroups are descriptive patterns, not causal constraint effects.
- **No stable clock signal.** G2 permutation importance shows clock_diff_s has the strongest negative importance at pilot scale — the model failed to learn generalizing clock patterns. B3 uses clock features but has not been ablated to isolate their independent probability contributions.
- **Noisy at pilot scale.** Slice diagnostics from the 2024-09 extract (931 val rows, 82–194 per elo bucket) are too noisy for reliable constraint conclusions.

**What is needed for Phase 9 constraint analysis:**

1. A better-fit model (after Phase 8 scaling/Stockfish validation).
2. Larger dataset for stable subgroup-level signal.
3. Explicit causal or quasi-experimental design.
4. Calibration check on any model used for constraint claims.
5. Documentation per PROJECT_CHARTER.md §8 evidence standards.

---

## 11. Allowed / Cautious / Forbidden Claims

| Status | Claim |
| --- | --- |
| **Allowed** | "B3 is the safest current broad probability model." |
| **Allowed** | "B3 is moderately calibrated for BLACK_WIN and WHITE_WIN at pilot scale (ECE ≈ 0.026–0.033)." |
| **Allowed** | "G2 probabilities are overconfident and should not be used for interpretation." |
| **Allowed** | "B1's low ECE is an artifact of prior-only prediction; B1 is not useful for position-level interpretation." |
| **Allowed** | "DRAW probabilities are unreliable for all current models." |
| **Allowed** | "Current probabilities are diagnostic only, not final calibrated estimates." |
| **Allowed** | "Rating/skill signal is robust at pilot scale." |
| **Allowed** | "Clock and phase probability signals are unstable at pilot scale." |
| **Allowed** | "Calibration and scaling are needed before probability-level constraint claims." |
| **Cautious** | "B3 probability differences may be used as rough descriptive outcome scores for position ranking." (with caveats: pilot-scale, not causal, DRAW excluded) |
| **Cautious** | "Higher-rated players tend to receive higher B3 p_WHITE_WIN on average." (correlation only, not causal) |
| **Cautious** | "B3 probability bins can support pipeline sanity checks." (not final claims) |
| **Cautious** | "Rating signal is more reliably captured than clock signal at this dataset scale." |
| **Forbidden** | Claiming the model proves time pressure causes worse play. |
| **Forbidden** | Claiming a +0.10 probability change is a direct constraint-caused shift. |
| **Forbidden** | Claiming the GBM learned stable human constraint strategy. |
| **Forbidden** | Claiming G2's high-confidence predictions are reliable. |
| **Forbidden** | Claiming DRAW class is adequately modeled because DRAW ECE appears small. |
| **Forbidden** | Claiming B1 is the most useful model because its ECE is lowest. |
| **Forbidden** | Framing model outputs as objective engine-based win estimates. |
| **Forbidden** | Claiming we have established a degradation curve for clock/phase pressure. |
| **Forbidden** | Claiming subgroup probability differences are final constraint findings. |
| **Forbidden** | Claiming p_WHITE_WIN equals objective position evaluation. |
| **Forbidden** | Claiming calibration fully corrects probabilities for constraint analysis. |

---

## 12. Readiness for Phase 8 and Phase 9

| Phase | Status | Condition |
| --- | --- | --- |
| Phase 8: Stockfish validation | Not started | Needed to check whether broad model conclusions align with objective position strength |
| Phase 8: Model scaling | Not started | More data needed for stable clock/phase signal |
| Phase 9: Constraint analysis | Not ready | Requires better-fit model, larger dataset, causal design, calibration check |

**B3 may be used as a cautious diagnostic baseline for Phase 8** to compare broad-model probabilities against eval-conditioned probabilities.

**G2 must not be used for any Phase 8 or Phase 9 probability claims.** Its overfit and overconfidence make it an unreliable reference.

**Any future subgroup or constraint claim must include:**

- Documented dataset version and split.
- Calibration assessment on the model used.
- Baseline comparison (at minimum against B3).
- Explicit acknowledgment that correlational findings are not causal.
- Written report per project workflow.

---

## 13. Reproducibility / Source Artifacts

Command used to generate this report:

```bash
PYTHONPATH=src python -m chess_mhsuc.probability_interpretation \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --version-tag 2024_09_25k_v1 \\
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
    --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
    --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
    --output reports/probability_interpretation_2024_09_25k_v1.md
```

**Source artifacts (all local-only, gitignored under `data/`):**

- `data/processed/baseline_results_2024_09_25k_v1.json`
- `data/processed/gbm_results_2024_09_25k_v1.json`
- `data/processed/baseline_predictions_2024_09_25k_v1.parquet`
- `data/processed/gbm_predictions_2024_09_25k_v1.parquet`

**Source context reports (committed):**

- `reports/calibration_2024_09_25k_v1.md`
- `reports/baseline_evaluation_2024_09_25k_v1.md`
- `reports/gbm_evaluation_2024_09_25k_v1.md`
- `reports/gbm_feature_importance_2024_09_25k_v1.md`

No new model outputs, model artifacts, plots, or CSV files were created. This committed Markdown report (`reports/probability_interpretation_2024_09_25k_v1.md`) is the only tracked artifact from this ticket.

---

## 14. Acceptance Criteria Met

- [x] Probability interpretation report exists
- [x] Report defines probability semantics (what p_BLACK_WIN/DRAW/WHITE_WIN means)
- [x] Report lists what probabilities do NOT mean
- [x] Report identifies B3 as safest current broad probability model
- [x] Report explains B1 low-ECE trap
- [x] Report explains why G2 probabilities are not trustworthy
- [x] Report explains DRAW probability unreliability
- [x] Report distinguishes probabilities from engine evaluation
- [x] Report distinguishes probability differences from causal constraint effects
- [x] Report includes allowed/cautious/forbidden claims table
- [x] Report does not compute new model predictions
- [x] Report does not fit post-hoc calibrators
- [x] Report does not make Phase 9 constraint claims
- [x] Report cites actual ECE and log_loss values from prior artifacts
- [x] No model artifacts saved
- [x] No CSV files created
- [x] No plots created
- [x] No new dependencies added
- [x] ROADMAP.md updated (7.2A complete, 7.2B complete)
- [x] EXPERIMENT_LOG.md updated (EXP-005 added)
- [x] Local data artifacts remain gitignored
