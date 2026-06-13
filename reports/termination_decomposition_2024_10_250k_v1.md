# Termination Decomposition — 2024_10_250k_v1

**Ticket:** 11.2B — Termination Decomposition Implementation (locked Contrast C2)
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`

---

## 1. Executive summary

All-games E3→E4 validation delta: -0.0120. Board-decided-only delta (frozen models, prediction-side filter, no retraining): 0.0060 (excludes zero); retained fraction 50%. Interpretation in Section 9. Predictive associations only — filtering time-forfeit games induces selection and does not create a causal design.

## 2. Dataset and artifacts

- Predictions (frozen E3/E4, all-games-trained): `data/processed/eval_conditioned_predictions_2024_10_250k_v1.parquet`
- Termination keys: `data/processed/feature_positions_broad_2024_10_250k_v1.parquet` (primary view; join on `(game_id, selected_position_type)`)
- Bootstrap: 1000 replicates, seed=42, game-level clusters; CI threshold 300 games.

## 3. Termination composition

Dataset primary view, by descriptive channel (rows/games):

- normal_decisive: 50,921 rows / 19,800 games
- normal_draw: 3,665 rows / 987 games
- rules_infraction_or_other: 1 rows / 1 games
- time_forfeit: 8,252 rows / 2,708 games

Validation rows by checkpoint (board_decided True/False games):

- move_10: time-forfeit: 400r/400g; board-decided: 3,124r/3,124g
- move_20: time-forfeit: 351r/351g; board-decided: 2,564r/2,564g
- move_30: time-forfeit: 287r/287g; board-decided: 1,606r/1,606g
- move_40: time-forfeit: 206r/206g; board-decided: 904r/904g

Late-checkpoint validation rows by min-clock bucket (board-decided vs time-forfeit):

- under_60s: time-forfeit: 170r/147g; board-decided: 105r/94g
- 60_180s: time-forfeit: 175r/161g; board-decided: 483r/424g
- over_180s: time-forfeit: 148r/120g; board-decided: 1,922r/1,343g

Dataset by split (board-decided True/False games):

- train: time-forfeit: 5,846r/1,922g; board-decided: 38,100r/14,525g
- val: time-forfeit: 1,244r/400g; board-decided: 8,198r/3,124g
- test: time-forfeit: 1,162r/386g; board-decided: 8,289r/3,139g

## 4. Join validation

- Prediction validation rows per model: 9,442; joined rows equal prediction rows: yes; missing termination after join: 0; keys unique on both sides: yes.

## 5. Overall E3→E4 decomposition

| Group | Rows | Games | E3 ll | E4 ll | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| all_games | 9,442 | 3,524 | 0.7463 | 0.7344 | -0.0120 | [-0.0177, -0.0062] | No |  |
| board_decided | 8,198 | 3,124 | 0.7348 | 0.7409 | 0.0060 | [0.0015, 0.0109] | No |  |
| time_forfeit | 1,244 | 400 | 0.8220 | 0.6915 | -0.1305 | [-0.1525, -0.1091] | No |  |
| channel_normal_decisive | 7,656 | 2,975 | 0.5947 | 0.6024 | 0.0077 | [0.0031, 0.0122] | No |  |
| channel_normal_draw | 542 | 149 | 2.7138 | 2.6965 | -0.0173 | N/A | — | below min game threshold |

Delta = log_loss(E4) − log_loss(E3); negative = clock features improved. `normal_decisive` mixes checkmate and resignation (not separable from PGN headers); channel rows beyond the binary split are descriptive.

## 6. Board-decided-only E3→E4 result

| board_decided | 8,198 | 3,124 | 0.7348 | 0.7409 | 0.0060 | [0.0015, 0.0109] | No |  |

## 7. Time-forfeit-only result

| time_forfeit | 1,244 | 400 | 0.8220 | 0.6915 | -0.1305 | [-0.1525, -0.1091] | No |  |

Time-forfeit games are where the mechanical flagging channel lives; a large delta here is expected and does not by itself say anything about board-decided play.

## 8. Late-checkpoint / late-clock localization

Move_30+move_40 only, by min-clock bucket; all-games vs board-decided (prediction-side filter):

| Group | Rows | Games | E3 ll | E4 ll | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| all_games / under_60s | 275 | 241 | 0.8611 | 0.6142 | -0.2468 | N/A | — | below min game threshold |
| all_games / 60_180s | 658 | 585 | 0.6967 | 0.6524 | -0.0442 | [-0.0636, -0.0242] | No |  |
| all_games / over_180s | 2,070 | 1,463 | 0.6916 | 0.6850 | -0.0066 | [-0.0133, 0.0007] | Yes |  |
| board_decided / under_60s | 105 | 94 | 0.7522 | 0.9184 | 0.1662 | N/A | — | below min game threshold |
| board_decided / 60_180s | 483 | 424 | 0.6411 | 0.6350 | -0.0061 | [-0.0270, 0.0146] | Yes |  |
| board_decided / over_180s | 1,922 | 1,343 | 0.6868 | 0.6844 | -0.0024 | [-0.0095, 0.0050] | Yes |  |

Board-decided under_60s cells are expected to be descriptive-only (sample-size collapse; see Section 10). Board-decided low-clock games are a selected survivor population (players who navigated time pressure without flagging).

## 9. Retained-fraction interpretation

Retained fraction |board_decided| / |all_games| = 0.50 (50%). **Caution: board-decided delta has the OPPOSITE sign to the all-games delta; the magnitude-based fraction overstates retention.**

The board-decided delta collapses (zero or sign-reversed): the clock residual in this month is substantially explained by the termination channel; the central claim must be re-framed honestly toward the flagging channel.

## 10. Risks and caveats

- Timeout is not purely mechanical: flagging is often the consequence of earlier time expenditure, so removing time-forfeit games removes some genuine clock-relevant signal as well.
- Filtering induces selection bias; board-decided low-clock games are a survivor population. Nothing here is a causal design, and no claim is made that time pressure causes worse reasoning.
- `Normal` mixes checkmate and resignation; draws are separable only via the result. No mate-vs-resignation claims.
- Board-decided under_60s late-clock cells are descriptive-only due to sample-size collapse; the localization conclusion rests on 60_180s.
- Ordered-bucket patterns are patterns; this is not a degradation curve.
- Player-level clustering remains unresolved (Phase 11.3); DRAW remains sparse and not solved; Stockfish eval is position context, not ground truth.
