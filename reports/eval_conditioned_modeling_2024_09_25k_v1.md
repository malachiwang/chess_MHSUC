# Eval-Conditioned Modeling — Ablation Report

**Ticket:** 8.2B — Existing-vs-Fixed Eval Comparison Implementation (implementation includes eval-conditioned ablation per 8.2A audit)
**Dataset:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

This report asks: once a chess engine has told us how good the position is, do human-context facts (player ratings, clock situation, game phase) still help predict how the game actually ended? We trained four logistic models that all see the local Stockfish evaluation from Ticket 8.1B, then added human-context features step by step and measured what improves on the validation split with game-level bootstrap confidence intervals.

Headline: adding clock features on top of eval + rating produced a statistically resolvable improvement (E3→E4 delta -0.0138, 95% CI [-0.0266, -0.0002], CI excludes zero).

The best eval-conditioned model (E5, val log_loss 0.7310) improves on the current broad champion B3 (0.8527).

## 2. Research Question

After controlling for objective position strength via fixed-depth Stockfish eval, do human/context features (rating, clock, checkpoint/phase) still add predictive signal for empirical human game outcomes? This is the transition from ordinary chess outcome prediction to human outcome probability under constraints. All comparisons are predictive associations on the validation split — not causal claims.

## 3. Data and Join Integrity

| Check | Value |
|---|---|
| Joined rows (primary_numbered) | 6,205 |
| Train / val / test rows | 4,344 / 931 / 930 |
| Orphan rows after join | 0 |
| sf artifact rows | 6,205 |
| Terminal sf_depth=0 rows | 27 |

Join key: `(game_id, selected_position_type)` — unique in both tables. The `(game_id, ply)` key was rejected per the 8.2A audit (duplicate-ply hazard when a move_N and 'last' checkpoint share a ply). Only `sf_*` columns plus keys were selected from the sf artifact (no suffix pollution). 'last' positions are excluded throughout (primary_numbered view, consistent with B3 and 8.1B).

## 4. Eval Feature Semantics

- `sf_eval_cp_clipped` — `sf_eval_cp` clipped to ±1000 cp (White POV); mate sentinels ±10000 map to ±1000. Same convention as the existing `eval_cp_clipped`.
- `sf_is_mate_eval` — True where `sf_eval_status == "ok_mate"`.

Excluded from features: `sf_eval_available` (constant), `sf_eval_status` and `sf_eval_bucket` (strings; bucket reserved for report slicing), `sf_eval_sign`/`sf_eval_abs` (redundant or direction-destroying), `sf_eval_mate_abs` (sparse), `sf_depth`/`sf_nodes`/`sf_time_ms`/engine metadata (provenance). All Lichess eval columns (`eval_cp`, `eval_cp_clipped`, `eval_mate`, `eval_mate_abs`, `is_mate_eval`, `eval_white_winning`, `has_eval`) are excluded from every primary feature set — they are sparse (15% coverage), selection-biased, and measure the same construct as `sf_eval_cp`.

## 5. Models / Feature Sets

| Model | Feature set | N features | Description |
|---|---|---|---|
| E1 | FS-H | 2 | sf_eval_cp_clipped, sf_is_mate_eval |
| E3 | FS-I | 6 | white_elo, black_elo, elo_diff, avg_elo… |
| E4 | FS-J | 19 | white_elo, black_elo, elo_diff, avg_elo… |
| E5 | FS-K | 24 | white_elo, black_elo, elo_diff, avg_elo… |

References (not retrained; loaded from the committed baseline run): B1 (prior), B2 (rating-only logistic), B3 (rating + clock + context logistic — current broad champion). All models are logistic regression (`max_iter=1000`, `lbfgs`); no GBMs were trained in this ticket.

## 6. Validation Metrics

All primary metrics on the validation split (931 rows, 348 games). Test split untouched for selection.

| Model | val log_loss | val accuracy | val macro_f1 | val Brier |
|---|---|---|---|---|
| B1 (ref) | 0.8853 | 0.4758 | 0.2149 | 0.5573 |
| B2 (ref) | 0.8740 | 0.5124 | 0.3521 | 0.5483 |
| B3 (ref) | 0.8527 | 0.5381 | 0.3702 | 0.5338 |
| E1 | 0.7581 | 0.6520 | 0.4489 | 0.4515 |
| E3 | 0.7500 | 0.6584 | 0.4533 | 0.4467 |
| E4 | 0.7362 | 0.6617 | 0.4555 | 0.4363 |
| E5 **(best E)** | 0.7310 | 0.6563 | 0.4518 | 0.4356 |

Decisive-only diagnostic (val rows with WHITE_WIN/BLACK_WIN only; diagnostic — does not replace the primary multiclass metric):

| Model | n rows | decisive-only log_loss |
|---|---|---|
| E1 | 872 | 0.6197 |
| E3 | 872 | 0.6122 |
| E4 | 872 | 0.5965 |
| E5 | 872 | 0.5967 |

## 7. Game-Level Bootstrap CIs

Game-level cluster bootstrap, 1000 replicates, seed=42. Rows from the same game are resampled together (1–4 rows per game; row-level CIs would be invalid).

| Model | val log_loss | 95% CI lower | 95% CI upper |
|---|---|---|---|
| B1 | 0.8853 | 0.8279 | 0.9444 |
| B2 | 0.8740 | 0.8127 | 0.9394 |
| B3 | 0.8527 | 0.7910 | 0.9170 |
| E1 | 0.7581 | 0.6864 | 0.8325 |
| E3 | 0.7500 | 0.6783 | 0.8253 |
| E4 | 0.7362 | 0.6640 | 0.8135 |
| E5 | 0.7310 | 0.6610 | 0.8048 |

## 8. Pairwise Delta Results

Paired game-level bootstrap; delta = log_loss(B) − log_loss(A). Negative delta means B improved. A CI excluding zero means the difference is statistically resolvable at this sample size; it does not establish any causal mechanism.

| Comparison | Point delta | 95% CI lower | 95% CI upper | CI contains zero |
|---|---|---|---|---|
| E3 → E4 | -0.0138 | -0.0266 | -0.0002 | No |
| E1 → E3 | -0.0081 | -0.0223 | 0.0042 | Yes |
| E4 → E5 | -0.0052 | -0.0147 | 0.0042 | Yes |
| B3 → E1 | -0.0946 | -0.1355 | -0.0477 | No |
| B3 → E5 | -0.1217 | -0.1565 | -0.0828 | No |

Interpretation (cautious):

- **E3 → E4 (key comparison):** adding clock features after eval + rating produces a CI excluding zero — clock carries predictive signal beyond objective position strength and rating at this sample size. This is a predictive association, not a causal claim.
- **E1 → E3:** rating over eval alone: delta -0.0081, CI contains zero.
- **E4 → E5:** checkpoint/phase context beyond rating + clock + eval: delta -0.0052, CI contains zero.
- **B3 → E1:** eval alone vs full human context: delta -0.0946, CI excludes zero.
- **B3 → E5 (best E):** delta -0.1217, CI excludes zero.

## 9. Per-Checkpoint-Type Slice

Validation log_loss by checkpoint type. Late checkpoints are increasingly decided positions (move_40: 71% of positions have |cp| ≥ 300), so pooled metrics blend easy late positions with hard early ones. This slice exists so the pooled number is not over-read. It does not establish degradation curves.

| Model | move_10 | move_20 | move_30 | move_40 |
|---|---|---|---|---|
| E1 | 0.8095 (n=348) | 0.7316 (n=289) | 0.7180 (n=187) | 0.7324 (n=107) |
| E3 | 0.8002 (n=348) | 0.7228 (n=289) | 0.7136 (n=187) | 0.7238 (n=107) |
| E4 | 0.7958 (n=348) | 0.7135 (n=289) | 0.7034 (n=187) | 0.6609 (n=107) |
| E5 | 0.7943 (n=348) | 0.7094 (n=289) | 0.6992 (n=187) | 0.6389 (n=107) |

## 10. Lichess Eval Overlap Appendix

Sanity context from 8.1B (descriptive only; no model in this ticket was trained on Lichess eval columns):

- 932 of 6,205 positions also have a Lichess cloud eval.
- Non-mate sign agreement: 829/872 = 95.1%.
- Mean absolute cp difference: 68.8 cp (different Stockfish versions, variable Lichess depth vs fixed depth=12 locally).
- Lichess eval columns and `sf_eval_cp_clipped` were never mixed in any primary feature set.

## 11. DRAW Caveat

DRAW is 59/931 validation rows (6.3%). DRAW metrics are directional only because DRAW is sparse; per-class DRAW numbers must not be treated as reliable at pilot scale.

## 12. Terminal Position / sf_depth=0 Caveat

27 of 6,205 positions are terminal (26 checkmate already on board, 1 stalemate). The engine returns sf_depth=0 for these because no search is possible — expected behavior, not evaluation failures. These rows are legitimate population members but are mechanically decided, so they trivially favor eval-conditioned models; they are 0.4% of rows.

## 13. Scientific Interpretation

Fixed-depth Stockfish eval is objective position context, not ground truth and not a causal variable. Residual rating/clock associations after conditioning on eval are predictive associations, not causal effects of those variables on outcomes. Late checkpoints are increasingly decided positions; per-checkpoint slices are reported for this reason. DRAW metrics are directional only because DRAW is sparse. Test split was not used for model selection.

## 14. Forbidden Claims / Limitations

- No causal claims are made or supported by this report.
- Stockfish depth=12 eval is an approximation, not ground truth; deeper or different engine versions would differ.
- This report does not establish degradation curves.
- DRAW is not solved; DRAW metrics are directional only.
- Phase 9 (scaling) is not started; no cross-stratum claims.
- Test-split metrics are recorded but were not used for any selection.
- Pilot scale (931 val rows, 348 games) produces wide CIs; interval endpoints should not be over-interpreted.

## 15. Reproducibility

```bash
PYTHONPATH=src python -m chess_mhsuc.eval_conditioned_modeling \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --features data/processed/feature_positions_broad_2024_09_25k_v1.parquet \
    --sf-eval data/processed/sf_eval_broad_2024_09_25k_v1.parquet \
    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \
    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \
    --output-results data/processed/eval_conditioned_results_2024_09_25k_v1.json \
    --output-predictions data/processed/eval_conditioned_predictions_2024_09_25k_v1.parquet \
    --output-report reports/eval_conditioned_modeling_2024_09_25k_v1.md \
    --overwrite
```

The markdown report body is deterministic (timestamps live in the results JSON only). LogisticRegression with lbfgs is deterministic for fixed inputs; bootstrap uses seed=42.
