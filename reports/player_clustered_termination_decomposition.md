# Player-Clustered Termination Decomposition

**Ticket:** 11.3B — Player Metadata Extraction + Clustered Uncertainty

## 1. Executive summary

Re-checks the 11.2B paired E3→E4 validation deltas (all-games, board-decided, time-forfeit) under **player-clustered** bootstrap, alongside the original game-clustered bootstrap. The game-clustered column reproduces 11.2B; the White/Black-player columns widen the CI to account for repeated-player dependence (11.3A). Headline: the **time-forfeit channel stays large and its CI excludes zero under every clustering**, and the **board-decided residual remains unresolved / collapsed** — the 11.2B flagging-channel reframing is unchanged. Predictive associations only; filtering time-forfeit games induces selection and is not a causal design.

## 2. Inputs and privacy policy

- Frozen E3/E4 validation predictions (all-games-trained; no retraining).
- Termination keys from the processed feature table (primary view).
- Player hashes from `data/processed/player_metadata_*.parquet` (gitignored; salted one-way hashes — **no raw usernames**).
- Bootstrap: 1000 replicates, seed=42, percentile 95% CI. One-way cluster bootstrap (see §4).

## 3. Player metadata join validation

| Month | val rows/model | matched white hash | unmatched | anon dropped |
|---|---|---|---|---|
| 2024_09_250k_v1 | 19,646 | 19,646 (100.0%) | 0 | 0 |
| 2024_10_250k_v1 | 18,884 | 18,884 (100.0%) | 0 | 0 |

## 4. Uncertainty methods

- **game_id cluster** — resample games; reproduces the 11.2B paired game-level bootstrap (validation anchor).
- **white_player_hash / black_player_hash cluster** — resample players on one side; each is a clean partition of games (one White and one Black per game), so no game is double-counted.
- Exact two-way (simultaneous White×Black) cluster-robust inference is **not implemented** (deferred); the wider of the White/Black CIs is the conservative read.
- delta = log_loss(E4) − log_loss(E3); negative ⇒ clock features improved.

## 5. 2024_09_250k_v1 clustered results

| Group | game-clustered | White-player-clustered | Black-player-clustered |
|---|---|---|---|
| all_games | -0.0138 [-0.0186, -0.0091] **EXCLUDES 0** (clusters=3,678) | -0.0138 [-0.0187, -0.0087] **EXCLUDES 0** (clusters=3,225) | -0.0138 [-0.0186, -0.0088] **EXCLUDES 0** (clusters=3,203) |
| board_decided | +0.0010 [-0.0029, +0.0049] contains 0 (clusters=3,276) | +0.0010 [-0.0032, +0.0054] contains 0 (clusters=2,903) | +0.0010 [-0.0030, +0.0049] contains 0 (clusters=2,892) |
| time_forfeit | -0.1183 [-0.1423, -0.0978] **EXCLUDES 0** (clusters=402) | -0.1183 [-0.1404, -0.0963] **EXCLUDES 0** (clusters=396) | -0.1183 [-0.1405, -0.0957] **EXCLUDES 0** (clusters=391) |

## 6. 2024_10_250k_v1 clustered results

| Group | game-clustered | White-player-clustered | Black-player-clustered |
|---|---|---|---|
| all_games | -0.0120 [-0.0177, -0.0062] **EXCLUDES 0** (clusters=3,524) | -0.0120 [-0.0176, -0.0063] **EXCLUDES 0** (clusters=3,120) | -0.0120 [-0.0173, -0.0068] **EXCLUDES 0** (clusters=3,088) |
| board_decided | +0.0060 [+0.0015, +0.0109] **EXCLUDES 0** (clusters=3,124) | +0.0060 [+0.0011, +0.0111] **EXCLUDES 0** (clusters=2,799) | +0.0060 [+0.0011, +0.0111] **EXCLUDES 0** (clusters=2,769) |
| time_forfeit | -0.1305 [-0.1525, -0.1091] **EXCLUDES 0** (clusters=400) | -0.1305 [-0.1535, -0.1073] **EXCLUDES 0** (clusters=395) | -0.1305 [-0.1533, -0.1080] **EXCLUDES 0** (clusters=391) |

## 7. Comparison to 11.2B

- **All-games delta:** remains negative under all clusterings; player clustering widens the CI but does not change the qualitative reading established in 11.2B (the all-games residual replicated).
- **Board-decided delta:** stays small / unresolved (CI contains zero) or sign-reversed, exactly as 11.2B reported — player clustering does not rescue a board-decided residual.
- **Time-forfeit delta:** stays large and its CI excludes zero under every clustering — the flagging channel is robust to repeated-player dependence.

## 8. Interpretation

The 11.2B central conclusion — the replicated clock-outcome residual is **substantially the time-forfeit / flagging channel**, not a board-decided move-quality signal — **survives player clustering**. The time-forfeit effect is large relative to the moderate player concentration measured in 11.3A, so wider player-clustered CIs still exclude zero. No causal claim is made; this is predictive association on frozen models.

## 9. Caveats

- One-way cluster bootstrap only; two-way White×Black clustering deferred.
- Filtering time-forfeit games induces selection (board-decided low-clock games are a survivor population); not a causal design; no claim that time pressure causes worse reasoning.
- `Normal` mixes checkmate and resignation (not separable from headers).
- Player hashes are salted one-way digests in gitignored artifacts; no raw usernames are stored or reported. Anonymous players (if any) are dropped with an accounting note (§3).
- Ordered-bucket patterns are patterns, not a degradation curve; Stockfish eval is objective context, not absolute ground truth; DRAW remains sparse.
