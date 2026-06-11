# Constraint Slice Analysis — Localizing the E3→E4 Clock Signal

**Ticket:** 9.2B — Constraint Slice / Interaction Implementation
**Dataset:** `lichess_ten_zero_2024_09_250k_v1`
**Version tag:** `2024_09_250k_v1`

---

## 1. ELI5 / TLDR

The 9.1B scale-up confirmed that clock features add predictive signal for game outcomes after controlling for engine eval and ratings (E3→E4). This report asks *where* that signal lives, by recomputing the paired E3→E4 validation delta inside slices defined before any results were computed: checkpoint, position decidedness, rating bucket, and — the key design point — clock-pressure buckets *within* late checkpoints, because marginal clock buckets are confounded with checkpoint. No models were trained; everything reuses the 9.1B prediction artifact. All findings are predictive associations, not causal effects.

## 2. Result Being Localized

E3 (Stockfish eval + rating) → E4 (eval + rating + clock), 9.1B validation split: delta −0.0138, 95% CI [−0.0186, −0.0091], CI excludes zero. Per-checkpoint reference deltas are recomputed below for self-containment.

## 3. Inputs and Join Integrity

- Predictions: `data/processed/eval_conditioned_predictions_2024_09_250k_v1.parquet` (E3/E4 validation rows, pairing validated per cell)
- Slice keys: `data/processed/feature_positions_broad_2024_09_250k_v1.parquet` + `data/processed/sf_eval_broad_2024_09_250k_v1.parquet` joined on `(game_id, selected_position_type)` — 0 orphans; `last` rows excluded; validation split only; test split never read into the analysis frame.

## 4. Slice Definitions

Fixed by the 9.2A audit before results were computed; not tuned afterwards.

| Slice | Role | Definition |
|---|---|---|
| checkpoint | reference | selected_position_type (primary numbered checkpoints) |
| decidedness | primary (P1) | equal: |sf_eval_cp| < 100; slight: 100 <= |cp| < 300; decided: 300 <= |cp| < 10000; mate: |cp| >= 10000 (absolute value — White/Black direction not used) |
| elo_bucket | primary (P2) | under_1200: avg_elo < 1200; 1200_1600: 1200 <= avg_elo < 1600; 1600_2000: 1600 <= avg_elo < 2000; 2000_plus: avg_elo >= 2000 |
| late_clock | primary (P3) | WITHIN move_30+move_40 only. min_clock_s = min(white_clock_s_capped, black_clock_s_capped). under_60s: min < 60; 60_180s: 60 <= min < 180; over_180s: min >= 180. Marginal clock buckets are NOT primary: confounded with checkpoint (see confounding diagnostic). |
| clock_imbalance | exploratory | balanced: |clock_diff_s| < 30; moderate_imbalance: 30 <= |diff| < 90; large_imbalance: |diff| >= 90 |

## 5. Data Sufficiency

Bootstrap CI rule: cells with ≥ 300 unique games get a game-level clustered bootstrap CI (1000 replicates, seed=42); smaller cells report the point delta with an explicit 'below min game threshold' note. No cell is silently dropped; no cells were merged after seeing results.

## 6. Confounding Diagnostic: Clock Bucket × Checkpoint

Row/game counts per marginal min-clock bucket within each checkpoint (one model's validation rows). Low clock is almost entirely a late-checkpoint phenomenon, which is why marginal clock buckets are not a primary slice and the clock analysis (P3) is conditioned on move_30+move_40.

| Checkpoint | under_60s | 60_180s | over_180s |
|---|---|---|---|
| move_10 | 1 rows / 1 games | 3 rows / 3 games | 3,674 rows / 3,674 games |
| move_20 | 5 rows / 5 games | 82 rows / 82 games | 2,925 rows / 2,925 games |
| move_30 | 84 rows / 84 games | 338 rows / 338 games | 1,582 rows / 1,582 games |
| move_40 | 166 rows / 166 games | 341 rows / 341 games | 622 rows / 622 games |

## 7. Reference: Per-Checkpoint E3→E4 Deltas

Recomputed from the prediction artifact (matches 9.1B).

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| move_10 | 3,678 | 3,678 | 0.8030 | 0.8005 | -0.0025 | [-0.0056, 0.0005] | Yes |  |
| move_20 | 3,012 | 3,012 | 0.7211 | 0.7177 | -0.0033 | [-0.0074, 0.0009] | Yes |  |
| move_30 | 2,004 | 2,004 | 0.7038 | 0.6801 | -0.0238 | [-0.0331, -0.0129] | No |  |
| move_40 | 1,129 | 1,129 | 0.7490 | 0.6884 | -0.0606 | [-0.0802, -0.0403] | No |  |

## 8. P1: Eval Decidedness Slice

Does the clock signal live in contested or decided positions? Buckets use |sf_eval_cp| (absolute; direction not used).

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| equal | 2,689 | 1,967 | 0.9244 | 0.9092 | -0.0151 | [-0.0214, -0.0093] | No |  |
| slight | 2,838 | 2,100 | 0.8422 | 0.8326 | -0.0096 | [-0.0169, -0.0026] | No |  |
| decided | 3,974 | 2,429 | 0.6027 | 0.5860 | -0.0168 | [-0.0245, -0.0095] | No |  |
| mate | 322 | 306 | 0.3429 | 0.3408 | -0.0021 | [-0.0307, 0.0298] | Yes |  |

## 9. P2: Rating Bucket Slice

Is the clock signal skill-dependent? Buckets use avg_elo.

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| under_1200 | 1,613 | 665 | 0.7891 | 0.7795 | -0.0096 | [-0.0207, 0.0019] | Yes |  |
| 1200_1600 | 3,556 | 1,349 | 0.7245 | 0.7096 | -0.0150 | [-0.0224, -0.0075] | No |  |
| 1600_2000 | 3,703 | 1,335 | 0.7463 | 0.7323 | -0.0140 | [-0.0224, -0.0064] | No |  |
| 2000_plus | 951 | 329 | 0.8083 | 0.7928 | -0.0155 | [-0.0312, -0.0001] | No |  |

## 10. P3: Late-Checkpoint Clock Bucket Slice

The key constraint test: within move_30+move_40 only, is the signal concentrated where remaining time is actually low? Conditioning on late checkpoints controls the clock×checkpoint confound shown in Section 6.

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| under_60s | 250 | 228 | 0.7878 | 0.5337 | -0.2541 | N/A | — | below min game threshold |
| 60_180s | 679 | 616 | 0.7785 | 0.7250 | -0.0534 | [-0.0717, -0.0335] | No |  |
| over_180s | 2,204 | 1,582 | 0.6944 | 0.6871 | -0.0074 | [-0.0136, -0.0014] | No |  |

## 11. Exploratory Slices

Clearly exploratory; interpret only directionally.

**Clock imbalance (marginal, all checkpoints):**

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| balanced | 3,956 | 2,544 | 0.7711 | 0.7705 | -0.0006 | [-0.0032, 0.0023] | Yes |  |
| moderate_imbalance | 3,310 | 2,298 | 0.7334 | 0.7274 | -0.0061 | [-0.0110, -0.0012] | No |  |
| large_imbalance | 2,557 | 1,434 | 0.7444 | 0.7002 | -0.0442 | [-0.0595, -0.0288] | No |  |

**Terminal-exclusion sensitivity (overall delta, all val rows):**

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| terminal_included | 9,823 | 3,678 | 0.7514 | 0.7377 | -0.0138 | [-0.0186, -0.0091] | No |  |
| terminal_excluded | 9,779 | 3,674 | 0.7546 | 0.7408 | -0.0138 | [-0.0186, -0.0093] | No |  |

## 12. Interpretation

- Within late checkpoints, the point delta by remaining-time bucket is: under_60s -0.2541, 60_180s -0.0534, over_180s -0.0074. Where CIs exist, contains-zero flags are shown in Section 10.
- By decidedness, the point delta is: equal -0.0151, slight -0.0096, decided -0.0168, mate -0.0021.

Allowed readings: clock features provide predictive signal in slices whose CI excludes zero; the signal is concentrated in later checkpoints; where the late-game low-clock cells show larger deltas, the pattern is consistent with time-pressure relevance. If the signal concentrates in decided positions, a plausible reading is that clocks help predict whether a winning position is converted before flagging — that is still a predictive association, not a statement about reasoning quality.

## 13. Guardrails / Forbidden Claims

- These slices localize one already-confirmed effect; they are not independent hypothesis tests, and no multiple-comparison correction is claimed.
- Nothing here shows that time pressure *degrades* play, and nothing here directly assesses reasoning — only outcome predictability is analyzed.
- Ordered-bucket patterns are reported as patterns; degradation curves are not established.
- Stockfish depth=12 eval is objective position context, not ground truth.
- Test split was not used. DRAW remains sparse and is not solved.

## 14. Limitations

- Sub-threshold cells (marked 'below min game threshold') have point deltas only; treat them descriptively.
- Slice keys and predictions come from the same superset 250k sample; external validity beyond 2024-09 is not established.
- Player-level leakage remains unresolved and applies to every slice.
- Decidedness, checkpoint, and clock depletion are mutually correlated; P3's late-checkpoint conditioning controls the largest confound but not all of them.

## 15. Reproducibility

```bash
PYTHONPATH=src python -m chess_mhsuc.constraint_slices \
    --dataset-id lichess_ten_zero_2024_09_250k_v1 \
    --version-tag 2024_09_250k_v1 \
    --predictions data/processed/eval_conditioned_predictions_2024_09_250k_v1.parquet \
    --features data/processed/feature_positions_broad_2024_09_250k_v1.parquet \
    --sf-eval data/processed/sf_eval_broad_2024_09_250k_v1.parquet \
    --output-json data/processed/constraint_slices_2024_09_250k_v1.json \
    --output-report reports/constraint_slices_2024_09_250k_v1.md \
    --n-replicates 1000 --seed 42 --min-games-for-ci 300 --overwrite
```

Deterministic: fixed slice definitions, seed=42 bootstrap, no timestamps in the report body (timestamp lives in the JSON only).
