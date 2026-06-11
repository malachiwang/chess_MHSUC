# Eval-Conditioned Modeling — Ablation Report

**Ticket:** 9.1B — Scale-Up Implementation (eval-conditioned ablation rerun at scale; replication of 8.2B)
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`
**Version tag:** `2024_10_250k_v1`

---

## 1. ELI5 / TLDR

This report asks: once a chess engine has told us how good the position is, do human-context facts (player ratings, clock situation, game phase) still help predict how the game actually ended? We trained four logistic models that all see the local Stockfish evaluation from Ticket 8.1B, then added human-context features step by step and measured what improves on the validation split with game-level bootstrap confidence intervals.

Headline: adding clock features on top of eval + rating produced a statistically resolvable improvement (E3→E4 delta -0.0120, 95% CI [-0.0177, -0.0062], CI excludes zero).

The best eval-conditioned model (E5, val log_loss 0.7302) improves on the current broad champion B3 (0.8549).

Replication comparison: the reference result (2024-09 250k replication reference) found E3→E4 delta -0.0138 with 95% CI [-0.0186, -0.0091]. This run's value is -0.0120 with CI [-0.0177, -0.0062].

## 2. Research Question

After controlling for objective position strength via fixed-depth Stockfish eval, do human/context features (rating, clock, checkpoint/phase) still add predictive signal for empirical human game outcomes? This is the transition from ordinary chess outcome prediction to human outcome probability under constraints. All comparisons are predictive associations on the validation split — not causal claims.

## 3. Data and Join Integrity

| Check | Value |
|---|---|
| Joined rows (primary_numbered) | 62,839 |
| Train / val / test rows | 43,946 / 9,442 / 9,451 |
| Orphan rows after join | 0 |
| sf artifact rows | 62,839 |
| Terminal sf_depth=0 rows | 299 |

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

All primary metrics on the validation split (9,442 rows, 3,524 games). Test split untouched for selection.

| Model | val log_loss | val accuracy | val macro_f1 | val Brier |
|---|---|---|---|---|
| B1 (ref) | 0.8803 | 0.4763 | 0.2151 | 0.5553 |
| B2 (ref) | 0.8668 | 0.5145 | 0.3531 | 0.5433 |
| B3 (ref) | 0.8549 | 0.5364 | 0.3680 | 0.5354 |
| E1 | 0.7531 | 0.6523 | 0.4485 | 0.4494 |
| E3 | 0.7463 | 0.6589 | 0.4529 | 0.4439 |
| E4 | 0.7344 | 0.6682 | 0.4593 | 0.4356 |
| E5 **(best E)** | 0.7302 | 0.6671 | 0.4586 | 0.4350 |

Decisive-only diagnostic (val rows with WHITE_WIN/BLACK_WIN only; diagnostic — does not replace the primary multiclass metric):

| Model | n rows | decisive-only log_loss |
|---|---|---|
| E1 | 8867 | 0.6256 |
| E3 | 8867 | 0.6185 |
| E4 | 8867 | 0.6075 |
| E5 | 8867 | 0.6062 |

## 7. Game-Level Bootstrap CIs

Game-level cluster bootstrap, 1000 replicates, seed=42. Rows from the same game are resampled together (1–4 rows per game; row-level CIs would be invalid).

| Model | val log_loss | 95% CI lower | 95% CI upper |
|---|---|---|---|
| B1 | 0.8803 | 0.8620 | 0.8993 |
| B2 | 0.8668 | 0.8478 | 0.8861 |
| B3 | 0.8549 | 0.8359 | 0.8750 |
| E1 | 0.7531 | 0.7307 | 0.7742 |
| E3 | 0.7463 | 0.7240 | 0.7687 |
| E4 | 0.7344 | 0.7126 | 0.7577 |
| E5 | 0.7302 | 0.7093 | 0.7524 |

## 8. Pairwise Delta Results

Paired game-level bootstrap; delta = log_loss(B) − log_loss(A). Negative delta means B improved. A CI excluding zero means the difference is statistically resolvable at this sample size; it does not establish any causal mechanism.

| Comparison | Point delta | 95% CI lower | 95% CI upper | CI contains zero |
|---|---|---|---|---|
| E3 → E4 | -0.0120 | -0.0177 | -0.0062 | No |
| E1 → E3 | -0.0068 | -0.0107 | -0.0027 | No |
| E4 → E5 | -0.0042 | -0.0070 | -0.0013 | No |
| B3 → E1 | -0.1018 | -0.1155 | -0.0876 | No |
| B3 → E5 | -0.1248 | -0.1359 | -0.1131 | No |

Interpretation (cautious):

- **E3 → E4 (key comparison):** adding clock features after eval + rating produces a CI excluding zero — clock carries predictive signal beyond objective position strength and rating at this sample size. This is a predictive association, not a causal claim.
- **E1 → E3:** rating over eval alone: delta -0.0068, CI excludes zero.
- **E4 → E5:** checkpoint/phase context beyond rating + clock + eval: delta -0.0042, CI excludes zero.
- **B3 → E1:** eval alone vs full human context: delta -0.1018, CI excludes zero.
- **B3 → E5 (best E):** delta -0.1248, CI excludes zero.

## 9. Per-Checkpoint-Type Slice

Validation log_loss by checkpoint type. Late checkpoints are increasingly decided positions (fraction with |cp| ≥ 300 — move_10: 19%; move_20: 48%; move_30: 62%; move_40: 67%), so pooled metrics blend easy late positions with hard early ones. This slice exists so the pooled number is not over-read. It does not establish degradation curves.

| Model | move_10 | move_20 | move_30 | move_40 |
|---|---|---|---|---|
| E1 | 0.8195 (n=3524) | 0.7181 (n=2915) | 0.6878 (n=1893) | 0.7460 (n=1110) |
| E3 | 0.8082 (n=3524) | 0.7107 (n=2915) | 0.6860 (n=1893) | 0.7461 (n=1110) |
| E4 | 0.8080 (n=3524) | 0.7102 (n=2915) | 0.6642 (n=1893) | 0.6836 (n=1110) |
| E5 | 0.8076 (n=3524) | 0.7076 (n=2915) | 0.6582 (n=1893) | 0.6663 (n=1110) |

Per-checkpoint paired deltas for the key comparison (E3 → E4, validation split):

| Checkpoint | Point delta | 95% CI lower | 95% CI upper | CI contains zero |
|---|---|---|---|---|
| move_10 | -0.0002 | -0.0034 | 0.0031 | Yes |
| move_20 | -0.0005 | -0.0057 | 0.0045 | Yes |
| move_30 | -0.0218 | -0.0323 | -0.0106 | No |
| move_40 | -0.0625 | -0.0822 | -0.0439 | No |

These per-checkpoint deltas are diagnostic; they show where the key signal concentrates and do not establish degradation curves.

## 10. Lichess Eval Overlap Appendix

Descriptive only; no model in this ticket was trained on Lichess eval columns:

- 10,376 of 62,839 positions also have a Lichess cloud eval.
- Non-mate sign agreement: 9,366/9,809 = 95.5%.
- Mean absolute cp difference: 59.9 cp (different Stockfish versions, variable Lichess depth vs fixed local depth).
- Lichess eval columns and `sf_eval_cp_clipped` were never mixed in any primary feature set.

## 11. DRAW Caveat and Metrics

DRAW is 575/9,442 validation rows (6.1%). DRAW metrics must be read cautiously because DRAW is sparse relative to decisive outcomes; DRAW is not solved.

Per-class DRAW metrics on the validation split:

| Model | DRAW precision | DRAW recall | DRAW f1 | DRAW support |
|---|---|---|---|---|
| E1 | 0.0000 | 0.0000 | 0.0000 | 575 |
| E3 | 0.0000 | 0.0000 | 0.0000 | 575 |
| E4 | 0.0000 | 0.0000 | 0.0000 | 575 |
| E5 | 0.0000 | 0.0000 | 0.0000 | 575 |

## 12. Terminal Position / sf_depth=0 Caveat

299 of 62,839 positions (0.5%) are terminal (checkmate or stalemate already on the board). The engine returns sf_depth=0 for these because no search is possible — expected behavior, not evaluation failures. These rows are legitimate population members but are mechanically decided, so they trivially favor eval-conditioned models.

## 13. Scientific Interpretation

Fixed-depth Stockfish eval is objective position context, not ground truth and not a causal variable. Residual rating/clock associations after conditioning on eval are predictive associations, not causal effects of those variables on outcomes. Late checkpoints are increasingly decided positions; per-checkpoint slices are reported for this reason. DRAW metrics are directional only because DRAW is sparse. Test split was not used for model selection.

## 14. Forbidden Claims / Limitations

- No causal claims are made or supported by this report.
- Stockfish depth=12 eval is an approximation, not ground truth; deeper or different engine versions would differ.
- This report does not establish degradation curves.
- DRAW is not solved; DRAW metrics are directional only.
- Phase 9 (scaling) is not started; no cross-stratum claims.
- Test-split metrics are recorded but were not used for any selection.
- This sample (3,524 validation games) still produces bootstrap CIs whose interval endpoints should not be over-interpreted.

## 15. Reproducibility

```bash
PYTHONPATH=src python -m chess_mhsuc.eval_conditioned_modeling \
    --dataset-id lichess_ten_zero_2024_10_250k_v1 \
    --version-tag 2024_10_250k_v1 \
    --features data/processed/feature_positions_broad_2024_10_250k_v1.parquet \
    --sf-eval data/processed/sf_eval_broad_2024_10_250k_v1.parquet \
    --baseline-predictions data/processed/baseline_predictions_2024_10_250k_v1.parquet \
    --baseline-results data/processed/baseline_results_2024_10_250k_v1.json \
    --output-results data/processed/eval_conditioned_results_2024_10_250k_v1.json \
    --output-predictions data/processed/eval_conditioned_predictions_2024_10_250k_v1.parquet \
    --output-report reports/eval_conditioned_modeling_2024_10_250k_v1.md \
    --overwrite
```

The markdown report body is deterministic (timestamps live in the results JSON only). LogisticRegression with lbfgs is deterministic for fixed inputs; bootstrap uses seed=42.
