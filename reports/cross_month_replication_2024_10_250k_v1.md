# Cross-Month Replication — 2024-10, 250k Raw Games

**Ticket:** 9.3B — Cross-Month Replication Implementation
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`
**Version tag:** `2024_10_250k_v1`

---

## 1. ELI5 / TLDR

Everything found so far came from one month of Lichess data (2024-09). This
ticket reran the entire pipeline on a fully separate month (2024-10, first
250k raw games) to test whether the findings are month-specific.

**They replicate.** The overall clock effect (E3→E4) came out at
**−0.0120, 95% CI [−0.0177, −0.0062]** — same direction, overlapping CI,
excludes zero (2024-09 reference: −0.0138 [−0.0186, −0.0091]). The
localization replicates too: the signal again concentrates in late
checkpoints and, within them, where remaining time is actually low
(under_60s −0.2468 descriptive; 60_180s −0.0442 with CI excluding zero;
over_180s −0.0066 near zero). All findings remain predictive associations,
not causal claims.

## 2. Research Question

Do the 2024-09 findings — clock features add predictive signal for game
outcomes after controlling for fixed-depth Stockfish eval and ratings, with
the signal concentrated in late-game low-clock positions — replicate on a
fully separate month?

## 3. Why Cross-Month Replication

The 2024-09 250k sample was a deterministic prefix and a superset of the
pilot; every prior result came from one contiguous block of one month. The
9.3A audit identified time-period specificity as the main untested validity
threat and selected cross-month replication (Design B) over a same-month
disjoint block: it tests the actual threat and required no parser changes.

## 4. Dataset and Sampling

- Source: `lichess_db_standard_rated_2024-10.pgn.zst`, deterministic first
  250,000 raw games — fully disjoint from all 2024-09 data.
- Raw prefix tee-cached to `data/raw/lichess/lichess_2024_10_first250k.pgn`
  (583 MB, gitignored); the Stockfish pass read from local disk.
- Same pipeline, same model definitions, same slice definitions (fixed
  since 9.2A — not tuned after seeing 2024-10 results), same seeds.

## 5. 2024-09 Reference Results

| Quantity | 2024-09 250k value |
|---|---|
| E3→E4 overall | −0.0138 [−0.0186, −0.0091], excludes zero |
| Per-checkpoint | move_10 −0.0025 (cz), move_20 −0.0033 (cz), move_30 −0.0238 (excl), move_40 −0.0606 (excl) |
| P3 late-clock | under_60s −0.2541 (descriptive), 60_180s −0.0534 (excl), over_180s −0.0074 (excl) |
| B3 / E5 val log_loss | 0.8533 / 0.7329 |

## 6. 2024-10 Pipeline Integrity

Parser, cleaning, and feature integrity checks: ALL PASS at every stage.
Splits: game-level, seed=42, no game overlap. Join integrity: 62,839 joined
rows, 0 orphans, key `(game_id, selected_position_type)`, no `last` rows.
E3/E4 pairing validated per cell before every paired bootstrap.

## 7. Month-to-Month Dataset Comparison

| Quantity | 2024-09 250k | 2024-10 250k |
|---|---|---|
| Raw games scanned | 250,000 | 250,000 |
| 600+0 games parsed | 26,041 | 24,908 |
| Clean games | 25,887 | 24,801 |
| Broad feature games | 24,520 | 23,496 |
| Primary positions | 65,368 | 62,839 |
| Train / val / test rows | 45,818 / 9,823 / 9,727 | 43,946 / 9,442 / 9,451 |
| Val games | 3,678 | 3,524 |
| Val DRAW rows | 603 (6.1%) | 575 (6.1%) |
| avg_elo (broad rows) mean / median | 1567 / 1590 | 1562 / 1584 |
| Termination (clean): Normal / Time forfeit / Rules | 22,849 / 3,036 / 2 | 21,845 / 2,950 / 6 |
| Lichess eval overlap rows | 10,166 | 10,376 |
| Overlap sign agreement (non-mate) | 95.6% | 95.5% |
| Terminal sf_depth=0 rows | 288 (0.4%) | 299 (0.5%) |

The two months are closely matched on rating distribution, DRAW rate,
termination mix, and eval-coverage characteristics (~4% fewer 10+0 games in
2024-10). No distribution shift large enough to complicate the comparison
was observed; differences in model metrics below are not attributable to an
obvious population shift.

## 8. Stockfish Eval Summary

Stockfish 18, depth=12, local cached PGN. Coverage: **62,839/62,839 (100%),
0 failures**, runtime 1,626 s (~27 min). Depth histogram: 62,540 at depth
12; 299 terminal sf_depth=0 rows (checkmate/stalemate on board — expected,
not failures). Status: ok_cp 60,884; ok_mate 1,955. Protocol: 10-position
dry-run → 1,000-position medium run → resume test (0 duplicates) → full run
after explicit approval. `split_set` joined post-hoc from the splits JSON
(established convention): train=43,946 / val=9,442 / test=9,451, 0 nulls.

## 9. Baseline Metrics

| Model | 2024-10 val log_loss [95% CI] | 2024-09 value |
|---|---|---|
| B1 (prior) | 0.8803 [0.8620, 0.8993] | 0.8813 |
| B2 (rating) | 0.8668 [0.8478, 0.8861] | 0.8684 |
| B3 (rating+clock+context) | 0.8549 [0.8359, 0.8750] | 0.8533 |

Baselines retrained deterministically for 2024-10; values within ~0.002 of
2024-09 — remarkable month-to-month stability.

## 10. Eval-Conditioned Metrics

Validation split (9,442 rows, 3,524 games):

| Model | val log_loss [95% CI] | val acc | 2024-09 ll |
|---|---|---|---|
| E1 (sf_eval only) | 0.7531 [0.7307, 0.7742] | 0.6523 | 0.7568 |
| E3 (+rating) | 0.7463 [0.7240, 0.7687] | 0.6589 | 0.7514 |
| E4 (+clock) | 0.7344 [0.7126, 0.7577] | 0.6682 | 0.7377 |
| E5 (+full context) **(best)** | 0.7302 [0.7093, 0.7524] | 0.6671 | 0.7329 |

All pairwise deltas exclude zero, as in 2024-09: E1→E3 −0.0068
[−0.0107, −0.0027]; E4→E5 −0.0042 [−0.0070, −0.0013]; B3→E1 −0.1018
[−0.1155, −0.0876]; B3→E5 −0.1248 [−0.1359, −0.1131].

## 11. Overall E3→E4 Replication

| | Point delta | 95% CI | Contains zero |
|---|---|---|---|
| 2024-09 250k (reference) | −0.0138 | [−0.0186, −0.0091] | No |
| **2024-10 250k (this run)** | **−0.0120** | **[−0.0177, −0.0062]** | **No** |

**REPLICATED.** Same direction, CI excludes zero, point estimates within
0.002 of each other, CIs overlapping almost completely. Clock features add
predictive signal after controlling for fixed-depth Stockfish eval and
ratings on a fully separate month.

## 12. Per-Checkpoint Replication

| Checkpoint | 2024-10 delta [95% CI] | Zero | 2024-09 |
|---|---|---|---|
| move_10 | −0.0002 [−0.0034, +0.0031] | contains | −0.0025 (contains) |
| move_20 | −0.0005 [−0.0057, +0.0045] | contains | −0.0033 (contains) |
| move_30 | −0.0218 [−0.0323, −0.0106] | **excludes** | −0.0238 (excludes) |
| move_40 | −0.0625 [−0.0822, −0.0439] | **excludes** | −0.0606 (excludes) |

The late-checkpoint concentration pattern reproduces almost exactly.

## 13. Constraint Slice Replication

**P3 — late-checkpoint clock buckets (localization target):**

| Cell | 2024-10 delta [95% CI] | Games | 2024-09 |
|---|---|---|---|
| under_60s | −0.2468 — N/A, below 300-game threshold | 241 | −0.2541 (228 games, descriptive) |
| 60_180s | −0.0442 [−0.0636, −0.0242] **excludes zero** | 585 | −0.0534 (excludes) |
| over_180s | −0.0066 [−0.0133, +0.0007] contains zero | 1,463 | −0.0074 (barely excluded) |

**LOCALIZATION REPLICATED.** The time-scarcity gradient reproduces: within
late checkpoints, the signal is ~7× larger at 60–180s than above 180s, with
a very large descriptive point delta under 60s. The over_180s cell sits at
the resolvability boundary in both months (excluded barely in 2024-09,
contains narrowly in 2024-10) — consistent with a small residual effect in
late positions with ample time.

**P1 — decidedness:** equal −0.0187 (excludes), slight −0.0068 (contains;
2024-09: −0.0096 excluded), decided −0.0106 (excludes), mate −0.0136
(287 games, descriptive). Signal again present in contested *and* decided
positions; the slight cell hovers at the boundary across months.

**P2 — rating:** under_1200 −0.0100 (contains, 624 games), 1200_1600 −0.0121
(excludes), 1600_2000 −0.0119 (excludes), 2000_plus −0.0151 (277 games,
descriptive this month). Magnitudes again similar across bands.

**Exploratory:** clock imbalance graded (balanced −0.0023 cz; moderate
−0.0051 cz; large −0.0345 excludes). Terminal sensitivity: delta −0.0120
with and without the terminal rows — robust.

## 14. DRAW Caveat

DRAW is 575/9,442 validation rows (6.1%) — same rate as 2024-09. Unweighted
logistic models again predict zero DRAW argmax rows. DRAW probability mass
lives in the probabilistic metrics. **DRAW is not solved.**

## 15. Terminal Position Caveat

299 of 62,839 positions (0.5%) are terminal (checkmate/stalemate on board);
sf_depth=0 is expected engine behavior, not failure. These rows are
mechanically decided; the terminal-exclusion sensitivity check shows the
headline delta unchanged without them.

## 16. Test Split Discipline

The 2024-10 test split (9,451 rows, 3,525 games) was not used for any model
selection. Test metrics are recorded in the results JSON per WORKFLOW.md
§13. Best-E selection reads validation log_loss only.

## 17. Interpretation

On two independent months of Lichess 10+0 games (2024-09 and 2024-10, fully
disjoint samples), clock features add statistically resolvable predictive
signal for game outcomes beyond fixed-depth Stockfish eval and player
ratings, and that signal concentrates in late-game positions where
remaining time is actually low. This is consistent with time-pressure
relevance. All of this is predictive association on validation splits —
not causal, and reasoning quality is not directly measured. Slice analyses
localize the confirmed effect; they are not independent hypothesis tests,
and no multiple-comparison correction is claimed.

## 18. Limitations

- Two adjacent months from one platform and one time control; external
  validity beyond these months is not proven.
- Player-level leakage remains unresolved (no usernames stored; the same
  player can appear across splits and across months).
- Stockfish depth=12 eval is objective position context, not ground truth.
- Degradation curves are not established; ordered-bucket patterns are
  reported as patterns.
- under_60s (241 games) and the 2000_plus rating cell (277 games) are
  descriptive this month — below the 300-game CI threshold.
- Phase 10 (sequence models) not started.

## 19. Reproducibility

Pipeline commands follow the 9.1B sequence with the 2024-10 tag throughout
(see `reports/phase_reports/phase_9_3b_cross_month_replication_implementation.md`
§5 for the exact list). Deterministic: immutable archive prefix, seed=42
splits and bootstrap, lbfgs logistic regression, deterministic report
renderers (no timestamps in report bodies). Rendered module reports:
`reports/eval_conditioned_modeling_2024_10_250k_v1.md` and
`reports/constraint_slices_2024_10_250k_v1.md` (both committed); all data
artifacts gitignored under `data/`.
