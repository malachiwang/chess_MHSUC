# MultiPV Sharpness Extraction — Combined

**Ticket:** 14.1C — Full Sharpness Extraction

## 1. Executive summary

Full MultiPV-5 depth-12 extraction for both 10+0 months. Extraction was clean and the candidate value-fragility features are stable across months. **Primary v1 = objective value fragility; surface tags / surface-bait are exploratory, NOT human obviousness** (deferred Tier B). **No sharpness result is claimed; no moderation model was run.** Predictive/descriptive only; MultiPV approximates narrowness, not ground truth.

## 2. Input and output artifacts

- in `data/processed/next_move_loss_2024_09_250k_v1.parquet` → out `data/processed/multipv_sharpness_2024_09_250k_v1.parquet` (gitignored).
- in `data/processed/next_move_loss_2024_10_250k_v1.parquet` → out `data/processed/multipv_sharpness_2024_10_250k_v1.parquet` (gitignored).

## 3. Engine settings

- Stockfish `Stockfish 18`, MultiPV-5, fixed depth-12; cp→ES scale 348.41.

## 4. Extraction counts and runtime

| Month | total | OK | non-mate | mate-band | runtime (min) | ms/pos |
|---|---|---|---|---|---|---|
| 2024_09_250k_v1 | 64,371 | 64,371 | 61,956 | 2,415 | see month report | — |
| 2024_10_250k_v1 | 61,868 | 61,868 | 59,625 | 2,243 | see month report | — |

## 5. Validation summary

| Month | FEN match | all legal | median MultiPV | <K legal | top1 |Δcp| median/p90 |
|---|---|---|---|---|---|
| 2024_09_250k_v1 | 1.0 | 1.0 | 5.0 | 0.0586 | 14.0/49.0 |
| 2024_10_250k_v1 | 1.0 | 1.0 | 5.0 | 0.0578 | 14.0/49.0 |

## 6. Objective value-fragility feature distributions (non-mate)

| Month | med best-2nd gap | med n_good_10es | med worst_top5_loss | med legal moves |
|---|---|---|---|---|
| 2024_09_250k_v1 | 0.0126 | 5.0 | 0.0463 | 34.0 |
| 2024_10_250k_v1 | 0.0124 | 5.0 | 0.0465 | 34.0 |

## 7. Candidate sharpness composite distributions (non-mate)

| Month | sharp_v1 | relaxed | strict |
|---|---|---|---|
| 2024_09_250k_v1 | 0.1417 | 0.0817 | 0.0732 |
| 2024_10_250k_v1 | 0.1407 | 0.0836 | 0.0744 |

Candidate features pending 14.2A — none is a sharpness claim.

## 8. Surface tag and surface-bait diagnostic distributions (exploratory)

| Month | best quiet | best check | best capture | bait_10es | bait_20es |
|---|---|---|---|---|---|
| 2024_09_250k_v1 | 0.6923 | 0.0784 | 0.258 | 0.0222 | 0.0092 |
| 2024_10_250k_v1 | 0.6904 | 0.0789 | 0.2601 | 0.0238 | 0.0096 |

**Exploratory surface diagnostics — NOT human obviousness.**

## 9. Month-to-month stability

- sharp_v1 rate: 0.1417 vs 0.1407 (Δ 0.001).
- median n_good_10es: 5.0 vs 5.0.
- surface_bait_10es: 0.0222 vs 0.0238.
- FEN match / all-legal identical at 1.0 / 1.0 both months. Distributions agree closely — no anomaly requiring investigation before 14.2A.

## 10. Artifact status

Both full artifacts gitignored; reports contain aggregate statistics only (no FENs, PGN text, usernames, or player hashes).

## 11. Implications for 14.2A pre-registration

Distributions are stable and non-degenerate across months, so 14.2A can lock the v1 sharpness feature/threshold (e.g. a train-defined `sharp_value_fragility_v1` or a train tercile of the continuous score), the orientation (side-to-move primitive vs advantaged-player view), and the C3c (move-quality) primary target with mover-player-clustered uncertainty and month replication — before any modeling.

## 12. Limitations and caveats

- No sharpness result; extraction only. Not causal; no 'degradation curve' language; surface tags NOT human obviousness. White-to-move only; MultiPV fixed-depth approximates narrowness, not ground truth; `n_good_*` censored at K; DRAW sparse; prior trajectory deferred.

## 13. Recommended next ticket

**14.2A — Sharpness Interaction Pre-Registration** (lock v1 feature/threshold/orientation/target/uncertainty/criteria before any C3c modeling).
