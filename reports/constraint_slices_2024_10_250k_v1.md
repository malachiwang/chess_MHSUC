# Constraint Slice Analysis — Localizing the E3→E4 Clock Signal

**Ticket:** 9.2B — Constraint Slice / Interaction Implementation
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`
**Version tag:** `2024_10_250k_v1`

---

## 1. ELI5 / TLDR

The 9.1B scale-up confirmed that clock features add predictive signal for game outcomes after controlling for engine eval and ratings (E3→E4). This report asks *where* that signal lives, by recomputing the paired E3→E4 validation delta inside slices defined before any results were computed: checkpoint, position decidedness, rating bucket, and — the key design point — clock-pressure buckets *within* late checkpoints, because marginal clock buckets are confounded with checkpoint. No models were trained; everything reuses the 9.1B prediction artifact. All findings are predictive associations, not causal effects.

## 2. Result Being Localized

E3 (Stockfish eval + rating) → E4 (eval + rating + clock), 9.1B validation split: delta −0.0138, 95% CI [−0.0186, −0.0091], CI excludes zero. Per-checkpoint reference deltas are recomputed below for self-containment.

## 3. Inputs and Join Integrity

- Predictions: `data/processed/eval_conditioned_predictions_2024_10_250k_v1.parquet` (E3/E4 validation rows, pairing validated per cell)
- Slice keys: `data/processed/feature_positions_broad_2024_10_250k_v1.parquet` + `data/processed/sf_eval_broad_2024_10_250k_v1.parquet` joined on `(game_id, selected_position_type)` — 0 orphans; `last` rows excluded; validation split only; test split never read into the analysis frame.

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
| move_10 | 0 rows / 0 games | 3 rows / 3 games | 3,521 rows / 3,521 games |
| move_20 | 9 rows / 9 games | 77 rows / 77 games | 2,829 rows / 2,829 games |
| move_30 | 94 rows / 94 games | 336 rows / 336 games | 1,463 rows / 1,463 games |
| move_40 | 181 rows / 181 games | 322 rows / 322 games | 607 rows / 607 games |

## 7. Reference: Per-Checkpoint E3→E4 Deltas

Recomputed from the prediction artifact (matches 9.1B).

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| move_10 | 3,524 | 3,524 | 0.8082 | 0.8080 | -0.0002 | [-0.0034, 0.0031] | Yes |  |
| move_20 | 2,915 | 2,915 | 0.7107 | 0.7102 | -0.0005 | [-0.0057, 0.0045] | Yes |  |
| move_30 | 1,893 | 1,893 | 0.6860 | 0.6642 | -0.0218 | [-0.0323, -0.0106] | No |  |
| move_40 | 1,110 | 1,110 | 0.7461 | 0.6836 | -0.0625 | [-0.0822, -0.0439] | No |  |

## 8. P1: Eval Decidedness Slice

Does the clock signal live in contested or decided positions? Buckets use |sf_eval_cp| (absolute; direction not used).

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| equal | 2,749 | 1,945 | 0.9235 | 0.9048 | -0.0187 | [-0.0260, -0.0105] | No |  |
| slight | 2,710 | 2,017 | 0.8370 | 0.8302 | -0.0068 | [-0.0145, 0.0004] | Yes |  |
| decided | 3,682 | 2,268 | 0.5847 | 0.5741 | -0.0106 | [-0.0187, -0.0024] | No |  |
| mate | 301 | 287 | 0.2896 | 0.2761 | -0.0136 | N/A | — | below min game threshold |

## 9. P2: Rating Bucket Slice

Is the clock signal skill-dependent? Buckets use avg_elo.

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| under_1200 | 1,530 | 624 | 0.7719 | 0.7619 | -0.0100 | [-0.0219, 0.0028] | Yes |  |
| 1200_1600 | 3,270 | 1,247 | 0.7206 | 0.7085 | -0.0121 | [-0.0201, -0.0043] | No |  |
| 1600_2000 | 3,844 | 1,376 | 0.7518 | 0.7399 | -0.0119 | [-0.0203, -0.0030] | No |  |
| 2000_plus | 798 | 277 | 0.7762 | 0.7611 | -0.0151 | N/A | — | below min game threshold |

## 10. P3: Late-Checkpoint Clock Bucket Slice

The key constraint test: within move_30+move_40 only, is the signal concentrated where remaining time is actually low? Conditioning on late checkpoints controls the clock×checkpoint confound shown in Section 6.

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| under_60s | 275 | 241 | 0.8611 | 0.6142 | -0.2468 | N/A | — | below min game threshold |
| 60_180s | 658 | 585 | 0.6967 | 0.6524 | -0.0442 | [-0.0636, -0.0242] | No |  |
| over_180s | 2,070 | 1,463 | 0.6916 | 0.6850 | -0.0066 | [-0.0133, 0.0007] | Yes |  |

## 11. Exploratory Slices

Clearly exploratory; interpret only directionally.

**Clock imbalance (marginal, all checkpoints):**

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| balanced | 3,680 | 2,433 | 0.7625 | 0.7602 | -0.0023 | [-0.0049, 0.0004] | Yes |  |
| moderate_imbalance | 3,218 | 2,198 | 0.7460 | 0.7408 | -0.0051 | [-0.0106, 0.0002] | Yes |  |
| large_imbalance | 2,544 | 1,408 | 0.7234 | 0.6889 | -0.0345 | [-0.0526, -0.0169] | No |  |

**Terminal-exclusion sensitivity (overall delta, all val rows):**

| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| terminal_included | 9,442 | 3,524 | 0.7463 | 0.7344 | -0.0120 | [-0.0177, -0.0062] | No |  |
| terminal_excluded | 9,405 | 3,522 | 0.7491 | 0.7371 | -0.0120 | [-0.0172, -0.0064] | No |  |

## 12. Interpretation

- Within late checkpoints, the point delta by remaining-time bucket is: under_60s -0.2468, 60_180s -0.0442, over_180s -0.0066. Where CIs exist, contains-zero flags are shown in Section 10.
- By decidedness, the point delta is: equal -0.0187, slight -0.0068, decided -0.0106, mate -0.0136.

Allowed readings: clock features provide predictive signal in slices whose CI excludes zero; the signal is concentrated in later checkpoints; where the late-game low-clock cells show larger deltas, the pattern is consistent with time-pressure relevance. If the signal concentrates in decided positions, a plausible reading is that clocks help predict whether a winning position is converted before flagging — that is still a predictive association, not a statement about reasoning quality.

## 13. Guardrails / Forbidden Claims

- These slices localize one already-confirmed effect; they are not independent hypothesis tests, and no multiple-comparison correction is claimed.
- Nothing here shows that time pressure *degrades* play, and nothing here directly assesses reasoning — only outcome predictability is analyzed.
- Ordered-bucket patterns are reported as patterns; degradation curves are not established.
- Stockfish depth=12 eval is objective position context, not ground truth.
- Test split was not used. DRAW remains sparse and is not solved.

## 14. Limitations

- Sub-threshold cells (marked 'below min game threshold') have point deltas only; treat them descriptively.
- Slice keys and predictions come from the same dataset (`lichess_ten_zero_2024_10_250k_v1`); external validity beyond the tested month(s) is not established.
- Player-level leakage remains unresolved and applies to every slice.
- Decidedness, checkpoint, and clock depletion are mutually correlated; P3's late-checkpoint conditioning controls the largest confound but not all of them.

## 15. Reproducibility

```bash
PYTHONPATH=src python -m chess_mhsuc.constraint_slices \
    --dataset-id lichess_ten_zero_2024_10_250k_v1 \
    --version-tag 2024_10_250k_v1 \
    --predictions data/processed/eval_conditioned_predictions_2024_10_250k_v1.parquet \
    --features data/processed/feature_positions_broad_2024_10_250k_v1.parquet \
    --sf-eval data/processed/sf_eval_broad_2024_10_250k_v1.parquet \
    --output-json data/processed/constraint_slices_2024_10_250k_v1.json \
    --output-report reports/constraint_slices_2024_10_250k_v1.md \
    --n-replicates 1000 --seed 42 --min-games-for-ci 300 --overwrite
```

Deterministic: fixed slice definitions, seed=42 bootstrap, no timestamps in the report body (timestamp lives in the JSON only).
