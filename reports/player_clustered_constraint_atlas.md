# Player-Clustered Constraint Atlas Checks

**Ticket:** 11.3B — Player Metadata Extraction + Clustered Uncertainty

## 1. Executive summary

Re-checks the strongest 15.1B descriptive finding — the **eval-band structure** of next-move expected-score (ES) loss — under bootstrap clustered by **mover player** (the White player at these even-ply checkpoints). The eval-band ordering (loss highest near equal/slight, lowest at decided) **persists with non-overlapping CIs**; the slight−decided and near_equal−decided differences exclude zero in both months. Late-group coarse-clock cells remain **flat** (overlapping CIs), so the 15.1B 'no replicated clock gradient in stable cells' conclusion is unchanged. CIs are modestly wider than game-clustered, as expected. Descriptive association only — not causal, not a degradation curve.

## 2. Inputs and privacy policy

- Next-move loss artifacts (15.0C), OK non-mate-band rows.
- Player hashes from gitignored `player_metadata_*.parquet` (salted one-way hashes; **no raw usernames**).
- Bootstrap: 1000 replicates, seed=42, 95% percentile CI, clustered by `mover_player_hash`.

## 3. Player metadata join validation

| Month | rows | matched mover hash | unmatched | non-mate w/ player |
|---|---|---|---|---|
| 2024_09_250k_v1 | 64,371 | 64,371 (100.0%) | 0 | 61,956 |
| 2024_10_250k_v1 | 61,868 | 61,868 (100.0%) | 0 | 59,625 |

## 4. Uncertainty methods

- Mean ES loss per eval band with **mover-player-clustered** 95% CI (resample mover players; each row has exactly one mover ⇒ clean partition).
- Pairwise differences (slight−decided, near_equal−decided) with the same clustering (a player contributing to both bands is resampled as one unit).
- Late-group (move_30+40) coarse-clock cells with the same clustering.

## 5. Eval-band expected-score loss with player-clustered CIs

| eval_band | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| near_equal | 0.0342 [0.0333, 0.0351] (excludes 0; clusters=8,753) | 0.0335 [0.0326, 0.0344] (excludes 0; clusters=8,636) |
| slight | 0.0417 [0.0407, 0.0427] (excludes 0; clusters=8,949) | 0.0419 [0.0409, 0.0430] (excludes 0; clusters=8,938) |
| clear | 0.0310 [0.0301, 0.0320] (excludes 0; clusters=9,304) | 0.0301 [0.0292, 0.0310] (excludes 0; clusters=9,202) |
| decided | 0.0181 [0.0163, 0.0201] (excludes 0; clusters=2,418) | 0.0179 [0.0160, 0.0200] (excludes 0; clusters=2,282) |

Pairwise differences (player-clustered):

| difference | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| slight vs decided | +0.0236 [+0.0215, +0.0258] **excludes 0** | +0.0240 [+0.0219, +0.0262] **excludes 0** |
| near equal vs decided | +0.0161 [+0.0139, +0.0181] **excludes 0** | +0.0156 [+0.0135, +0.0178] **excludes 0** |

## 6. Late-clock expected-score loss with player-clustered CIs

Late group (move_30+move_40), coarse clock bucket:

| clock | 2024_09_250k_v1 | 2024_10_250k_v1 |
|---|---|---|
| under_60 | 0.0329 [0.0276, 0.0386] (excludes 0; clusters=614) | 0.0310 [0.0267, 0.0357] (excludes 0; clusters=668) |
| 60_180 | 0.0307 [0.0280, 0.0335] (excludes 0; clusters=1,848) | 0.0306 [0.0281, 0.0332] (excludes 0; clusters=1,896) |
| over_180 | 0.0295 [0.0285, 0.0305] (excludes 0; clusters=7,436) | 0.0281 [0.0272, 0.0290] (excludes 0; clusters=7,240) |

## 7. Comparison to 15.1B

- **Eval-band structure (replicates, survives clustering):** loss peaks at near_equal/slight and is lowest at decided in both months; the near_equal−decided and slight−decided differences exclude zero under mover-player clustering. This is the same ordering 15.1B reported descriptively, now with player-clustered CIs.
- **No clock gradient (unchanged):** late coarse-clock cells overlap in CI; player clustering does not create a gradient.
- **Sparse low-clock cells:** under_60 remains small; treated cautiously (consistent with the non-replicating low-clock bump in 15.1B).

## 8. Interpretation

The 15.1B headline — **eval-band conditioning dominates next-move loss, and there is no replicated raw clock gradient among stable cells** — is robust to repeated-player dependence. Controlled C4 modeling must condition on eval band and should carry player-clustered uncertainty. Descriptive only; Stockfish eval is objective context, not absolute ground truth.

## 9. Caveats

- Mover is always White at numbered checkpoints (White-to-move scope).
- Mover-player clustering captures the decision-maker's repeated-player dependence; the opponent's dependence is not separately clustered here.
- ES loss is right-skewed; means are reported with clustered CIs but medians/quantiles (15.1B) remain the fuller description.
- Descriptive association only — not causal, not a degradation curve; DRAW remains sparse and not solved; sharpness not invoked.
