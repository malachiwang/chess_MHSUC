# Phase 11.3B — Player Metadata Extraction + Clustered Uncertainty

**Labels:** IMPLEMENTATION / HARDENING
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

Implemented privacy-safe player metadata extraction and a configurable clustered
bootstrap, then re-checked the two headline findings under **player clustering**.
Both survive:

- **11.2B termination decomposition:** the **time-forfeit channel stays large with
  a CI excluding zero** under game-, White-player-, and Black-player-clustered
  bootstrap (2024-09 −0.1183; 2024-10 −0.1305), and the **board-decided residual
  stays unresolved/collapsed** (2024-09 +0.0010 contains zero; 2024-10 +0.0060,
  small). The flagging-channel reframing is unchanged.
- **15.1B Constraint Atlas eval-band structure:** under **mover-player clustering**,
  ES loss peaks at slight/near_equal and is lowest at decided, with the
  slight−decided (+0.024) and near_equal−decided (+0.016) differences **excluding
  zero in both months**; late coarse-clock cells stay **flat** (overlapping CIs).

Correctness anchor: with `cluster_col = game_id`, the new bootstrap **reproduces
the published 11.2B numbers exactly** (e.g. 2024-09 all-games −0.0138
[−0.0186, −0.0091]; 2024-10 board-decided +0.0060 [+0.0015, +0.0109]). Player
clustering widens CIs only modestly — consistent with the *moderate* player
concentration measured in 11.3A. No raw usernames are stored or reported; all
player work uses salted one-way hashes in gitignored artifacts.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/player_metadata.py` | Privacy-safe extraction: normalize/hash, PGN-header parse, raw-PGN locator, hashed-ID join helpers, CLI |
| `src/chess_mhsuc/clustered_uncertainty.py` | Configurable one-way cluster bootstrap (mean / mean-diff / paired delta) + termination & atlas rerun report generators + CLI |
| `tests/test_player_metadata.py` | 21 tests (normalization, hashing, header parse, joins, locator) |
| `tests/test_clustered_uncertainty.py` | 15 tests (validation, mean/diff/paired CIs, determinism, widening, guards) |
| `reports/player_clustered_termination_decomposition.md` | 11.2B rerun under clustering |
| `reports/player_clustered_constraint_atlas.md` | 15.1B eval-band/clock rerun under clustering |
| `reports/player_metadata_privacy_summary.md` | Privacy/anonymization policy + aggregate counts |
| `reports/phase_reports/phase_11_3b_player_metadata_clustered_uncertainty.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 11.3B marked complete; pointer → 15.1C |
| `EXPERIMENT_LOG.md` | EXP-023 added |
| `PREREGISTRATION.md` | player-leakage clause: clustered route now *implemented*; controlled C4/C3 must carry player-clustered uncertainty |

The frozen modules `termination_decomposition.py` and `constraint_atlas.py` were
**not modified** — their pure functions (`load_termination_keys`,
`attach_and_validate`, `load_atlas_frame`, binning) are imported and reused.

## 4. Player metadata extraction

`player_metadata.py` streams the raw PGN headers and emits one hashed row per game.
Both 250k caches extracted cleanly:

| Month | Games | Unique players | Bot games | Anonymous | game_id unique |
|---|---|---|---|---|---|
| 2024-09 | 250,000 | 108,642 | 634 | 0 | yes |
| 2024-10 | 250,000 | 112,556 | 434 | 0 | yes |

Join coverage onto the primary 600+0 analysis frames was **100%** (termination
val rows 19,646 / 18,884; atlas non-mate rows 61,956 / 59,625; 0 anon dropped).

## 5. Privacy / anonymization implementation

- Usernames normalized (strip, lower-case) then hashed with `blake2b` (12-byte) over
  a fixed **non-secret** pepper; raw strings never written.
- Output frame carries hashes + bot flags + version_tag only; an
  `assert_no_raw_usernames` guard blocks any raw-username column.
- Artifacts are gitignored (`data/`, `*.parquet`; verified via `git check-ignore`).
- Committed reports carry aggregate counts only. Full policy in
  `reports/player_metadata_privacy_summary.md`.

## 6. Clustered uncertainty implementation

`clustered_uncertainty.py` provides a one-way cluster bootstrap with a configurable
cluster key:

- `validate_cluster_key` — missing/null guard.
- `clustered_mean_ci` — clustered 95% CI for a mean (raises < 2 clusters; notes < 30).
- `clustered_mean_diff_ci` — clustered CI for a difference of group means (a cluster
  contributes both groups together, preserving within-player cross-group correlation).
- `clustered_paired_delta_ci` — clustered paired log-loss delta E3→E4 (same clusters
  for both models per replicate; reproduces the game-level result when keyed on
  `game_id`).

Scope: this is **one-way** clustering. Each outcome game has two players, so White-
and Black-player-clustered CIs are reported separately (each a clean partition);
**exact two-way (simultaneous White×Black) cluster-robust inference is deferred** and
documented as such (the wider of the two CIs is the conservative read).

## 7. Termination decomposition clustered check

Paired E3→E4 validation deltas, game- vs player-clustered (1000 replicates, seed 42):

| Month | Group | game-clustered | White-player | Black-player |
|---|---|---|---|---|
| 2024-09 | all_games | −0.0138 [−0.0186, −0.0091] ✗0 | −0.0138 [−0.0187, −0.0087] ✗0 | −0.0138 [−0.0186, −0.0088] ✗0 |
| 2024-09 | board_decided | +0.0010 [−0.0029, +0.0049] (0) | +0.0010 [−0.0032, +0.0054] (0) | +0.0010 [−0.0030, +0.0049] (0) |
| 2024-09 | time_forfeit | −0.1183 [−0.1423, −0.0978] ✗0 | −0.1183 [−0.1404, −0.0963] ✗0 | −0.1183 [−0.1405, −0.0957] ✗0 |
| 2024-10 | all_games | −0.0120 [−0.0177, −0.0062] ✗0 | −0.0120 [−0.0176, −0.0063] ✗0 | −0.0120 [−0.0173, −0.0068] ✗0 |
| 2024-10 | board_decided | +0.0060 [+0.0015, +0.0109] ✗0 | +0.0060 [+0.0011, +0.0111] ✗0 | +0.0060 [+0.0011, +0.0111] ✗0 |
| 2024-10 | time_forfeit | −0.1305 [−0.1525, −0.1091] ✗0 | −0.1305 [−0.1535, −0.1073] ✗0 | −0.1305 [−0.1533, −0.1080] ✗0 |

(✗0 = CI excludes zero; (0) = contains zero.) The game-clustered column matches the
published 11.2B CIs to 4 dp. Player clustering widens CIs slightly; **no group
changes its zero-crossing verdict.**

## 8. Constraint Atlas clustered check

Mean ES loss by eval band, mover-player-clustered (1000 replicates, seed 42):

| Band | 2024-09 | 2024-10 |
|---|---|---|
| near_equal | 0.0342 [0.0333, 0.0351] | 0.0335 [0.0326, 0.0344] |
| slight | 0.0417 [0.0407, 0.0427] | 0.0419 [0.0409, 0.0430] |
| clear | 0.0310 [0.0301, 0.0320] | 0.0301 [0.0292, 0.0310] |
| decided | 0.0181 [0.0163, 0.0201] | 0.0179 [0.0160, 0.0200] |

Pairwise (player-clustered): slight−decided +0.0236 / +0.0240 (both **exclude 0**);
near_equal−decided +0.0161 / +0.0156 (both **exclude 0**). Late coarse-clock cells:
under_60 0.0329 / 0.0310, 60_180 0.0307 / 0.0306, over_180 0.0295 / 0.0281 —
**overlapping CIs, flat** in both months. The eval-band structure survives; the
no-clock-gradient conclusion is unchanged.

## 9. Tests run

- `tests/test_player_metadata.py`: **21 passed**.
- `tests/test_clustered_uncertainty.py`: **15 passed**.
- Full suite: **1,671 passed** (was 1,635; +36), 0 regressions.

## 10. Output artifact status

- `data/processed/player_metadata_2024_09_250k_v1.parquet` — gitignored, hashes only.
- `data/processed/player_metadata_2024_10_250k_v1.parquet` — gitignored, hashes only.
- No existing artifacts modified in place; no next-move-loss or prediction artifact
  overwritten. Reports are the only committed outputs.

## 11. Limitations and caveats

- One-way cluster bootstrap; exact two-way White×Black clustering deferred.
- Mover-player clustering captures the decision-maker's dependence; the opponent's
  is not separately clustered in the atlas check.
- Filtering time-forfeit games induces selection (survivor population); predictive
  association only, not a causal design; no claim that time pressure causes worse
  reasoning.
- ES loss is right-skewed; clustered CIs are on means — medians/quantiles (15.1B)
  remain the fuller description.
- Pepper is a non-secret determinism device; hashes never leave gitignored
  artifacts. Stockfish eval is objective context, not absolute ground truth; DRAW
  remains sparse and not solved.

## 12. Recommended next ticket

**15.1C — Controlled Move-Quality Modeling Audit.** Player-clustered uncertainty is
now available, and both headline findings are confirmed robust to repeated-player
dependence. 15.1C should design controlled C4 modeling (next-move ES loss ~ clock +
rating + **eval band** + phase + prior trajectory, with interactions), conditioning
on eval band (which dominates, §8) and carrying mover-player-clustered uncertainty;
strict player-disjoint splitting remains infeasible (11.3A) except as an optional
held-out robustness slice.
