# Termination Decomposition — 2024_09_250k_v1

**Ticket:** 11.2B — Termination Decomposition Implementation (locked Contrast C2)
**Dataset:** `lichess_ten_zero_2024_09_250k_v1`

---

## 1. Executive summary

All-games E3→E4 validation delta: -0.0138. Board-decided-only delta (frozen models, prediction-side filter, no retraining): 0.0010 (contains zero); retained fraction 7%. Interpretation in Section 9. Predictive associations only — filtering time-forfeit games induces selection and does not create a causal design.

## 2. Dataset and artifacts

- Predictions (frozen E3/E4, all-games-trained): `data/processed/eval_conditioned_predictions_2024_09_250k_v1.parquet`
- Termination keys: `data/processed/feature_positions_broad_2024_09_250k_v1.parquet` (primary view; join on `(game_id, selected_position_type)`)
- Bootstrap: 1000 replicates, seed=42, game-level clusters; CI threshold 300 games.

## 3. Termination composition

Dataset primary view, by descriptive channel (rows/games):

- normal_decisive: 53,113 rows / 20,700 games
- normal_draw: 3,719 rows / 1,018 games
- rules_infraction_or_other: 1 rows / 1 games
- time_forfeit: 8,535 rows / 2,801 games

Validation rows by checkpoint (board_decided True/False games):

- move_10: time-forfeit: 402r/402g; board-decided: 3,276r/3,276g
- move_20: time-forfeit: 343r/343g; board-decided: 2,669r/2,669g
- move_30: time-forfeit: 279r/279g; board-decided: 1,725r/1,725g
- move_40: time-forfeit: 192r/192g; board-decided: 937r/937g

Late-checkpoint validation rows by min-clock bucket (board-decided vs time-forfeit):

- under_60s: time-forfeit: 143r/127g; board-decided: 107r/101g
- 60_180s: time-forfeit: 163r/152g; board-decided: 516r/464g
- over_180s: time-forfeit: 165r/142g; board-decided: 2,039r/1,440g

Dataset by split (board-decided True/False games):

- train: time-forfeit: 5,975r/1,967g; board-decided: 39,843r/15,196g
- val: time-forfeit: 1,216r/402g; board-decided: 8,607r/3,276g
- test: time-forfeit: 1,344r/432g; board-decided: 8,383r/3,247g

## 4. Join validation

- Prediction validation rows per model: 9,823; joined rows equal prediction rows: yes; missing termination after join: 0; keys unique on both sides: yes.

## 5. Overall E3→E4 decomposition

| Group | Rows | Games | E3 ll | E4 ll | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| all_games | 9,823 | 3,678 | 0.7514 | 0.7377 | -0.0138 | [-0.0186, -0.0091] | No |  |
| board_decided | 8,607 | 3,276 | 0.7317 | 0.7327 | 0.0010 | [-0.0029, 0.0049] | Yes |  |
| time_forfeit | 1,216 | 402 | 0.8909 | 0.7726 | -0.1183 | [-0.1423, -0.0978] | No |  |
| channel_normal_decisive | 8,041 | 3,121 | 0.5885 | 0.5921 | 0.0035 | [-0.0003, 0.0079] | Yes |  |
| channel_normal_draw | 566 | 155 | 2.7662 | 2.7308 | -0.0354 | N/A | — | below min game threshold |

Delta = log_loss(E4) − log_loss(E3); negative = clock features improved. `normal_decisive` mixes checkmate and resignation (not separable from PGN headers); channel rows beyond the binary split are descriptive.

## 6. Board-decided-only E3→E4 result

| board_decided | 8,607 | 3,276 | 0.7317 | 0.7327 | 0.0010 | [-0.0029, 0.0049] | Yes |  |

## 7. Time-forfeit-only result

| time_forfeit | 1,216 | 402 | 0.8909 | 0.7726 | -0.1183 | [-0.1423, -0.0978] | No |  |

Time-forfeit games are where the mechanical flagging channel lives; a large delta here is expected and does not by itself say anything about board-decided play.

## 8. Late-checkpoint / late-clock localization

Move_30+move_40 only, by min-clock bucket; all-games vs board-decided (prediction-side filter):

| Group | Rows | Games | E3 ll | E4 ll | Delta | 95% CI | CI contains zero | Note |
|---|---|---|---|---|---|---|---|---|
| all_games / under_60s | 250 | 228 | 0.7878 | 0.5337 | -0.2541 | N/A | — | below min game threshold |
| all_games / 60_180s | 679 | 616 | 0.7785 | 0.7250 | -0.0534 | [-0.0717, -0.0335] | No |  |
| all_games / over_180s | 2,204 | 1,582 | 0.6944 | 0.6871 | -0.0074 | [-0.0136, -0.0014] | No |  |
| board_decided / under_60s | 107 | 101 | 0.5543 | 0.7229 | 0.1686 | N/A | — | below min game threshold |
| board_decided / 60_180s | 516 | 464 | 0.6926 | 0.6632 | -0.0294 | [-0.0530, -0.0064] | No |  |
| board_decided / over_180s | 2,039 | 1,440 | 0.6763 | 0.6722 | -0.0041 | [-0.0106, 0.0021] | Yes |  |

Board-decided under_60s cells are expected to be descriptive-only (sample-size collapse; see Section 10). Board-decided low-clock games are a selected survivor population (players who navigated time pressure without flagging).

## 9. Retained-fraction interpretation

Retained fraction |board_decided| / |all_games| = 0.07 (7%).

The board-decided delta collapses (zero or sign-reversed): the clock residual in this month is substantially explained by the termination channel; the central claim must be re-framed honestly toward the flagging channel.

## 10. Risks and caveats

- Timeout is not purely mechanical: flagging is often the consequence of earlier time expenditure, so removing time-forfeit games removes some genuine clock-relevant signal as well.
- Filtering induces selection bias; board-decided low-clock games are a survivor population. Nothing here is a causal design, and no claim is made that time pressure causes worse reasoning.
- `Normal` mixes checkmate and resignation; draws are separable only via the result. No mate-vs-resignation claims.
- Board-decided under_60s late-clock cells are descriptive-only due to sample-size collapse; the localization conclusion rests on 60_180s.
- Ordered-bucket patterns are patterns; this is not a degradation curve.
- Player-level clustering remains unresolved (Phase 11.3); DRAW remains sparse and not solved; Stockfish eval is position context, not ground truth.
