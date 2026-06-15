# Phase 14.2A — Sharpness Interaction Pre-Registration

**Labels:** PRE-REGISTRATION / DESIGN | doc-only
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Locked the pre-registration for the C3c **clock × sharpness move-quality moderation**
test, to be implemented in 14.2B. The core question: does the small, controlled
`60_180`-vs-`over_180` clock association with next-move expected-score (ES) loss
(15.1D/15.1F, pooled ≈ +0.0034) become **larger in objectively sharp / value-fragile
positions**? The full C3c spec — target, sharpness feature, clock contrast,
difference-in-differences estimand, model, controls, uncertainty, replication/success/
kill criteria, robustness checks, and forbidden claims — is written into
`PREREGISTRATION.md` (§C3c). A read-only join/cell-adequacy check confirmed feasibility and
surfaced the power bottleneck. **No model was run.** Predictive/descriptive moderation only,
not causal; the v1 feature is an engine-side value-fragility proxy, **not** human obviousness.

## 2. Files inspected

- Docs: `ROADMAP.md`, `PREREGISTRATION.md`, `EXPERIMENT_LOG.md`.
- Reports: `reports/c4_move_quality_arc_summary.md`,
  `reports/controlled_move_quality_combined.md`,
  `reports/clock_association_robustness_combined.md`,
  `reports/multipv_sharpness_{2024_09,2024_10}_250k_v1.md`,
  `reports/multipv_sharpness_combined.md`, the 14.1B/14.1C phase reports.
- Code: `multipv_sharpness.py`, `controlled_move_quality.py`,
  `clock_association_robustness.py`, `clustered_uncertainty.py`, `next_move_loss.py`.
- Artifacts (read-only): both `multipv_sharpness_*` parquets (present, gitignored).

## 3. Files modified

- `PREREGISTRATION.md` — added the locked **§C3c** pre-registration block.
- `ROADMAP.md` — 14.2A complete; pointer → 14.2B.
- `EXPERIMENT_LOG.md` — EXP-033.
- This phase report (created).

No code, no data artifacts, no tests touched.

## 4. Current evidence entering this ticket

- C4 closed: outcome clock signal ≈ flagging channel; eval state dominates next-move loss;
  a **small, replicated, robust, secondary** controlled clock association (`60_180` vs
  `over_180` pooled +0.0034 [+0.0015,+0.0052]) survived all 15.1F robustness checks;
  prior trajectory deferred.
- Sharpness extracted (14.1C): both months, FEN-match 1.0, all-legal 1.0;
  `sharp_value_fragility_v1` base rate 0.1417 / 0.1407; distributions stable across months.
- No sharpness moderation model has been run; no human-obviousness model exists.

## 5. Locked primary analysis

Difference-in-differences **clock × sharpness** moderation of next-move ES loss, recovered
as the `clock=60_180 × sharp_value_fragility_v1` interaction coefficient in a controlled OLS,
with mover-player-clustered bootstrap, per month then pooled. Full detail in PREREGISTRATION
§C3c (1–15).

## 6. Primary row universe and joins

Both months. Join `next_move_loss_<m>` ⋈ `multipv_sharpness_<m>` on
`(game_id, selected_position_type)`, ⋈ `player_metadata_<m>` on `game_id` (mover hash).
Primary rows: both statuses OK, **non-mate-band**, covariates non-null. **Verified
read-only:** sharpness artifact unique on the join key; **100% join coverage** onto the
non-mate frame (61,956 / 59,625 rows); mover-player hash present for every row.

## 7. Primary target

`expected_score_loss` (mover's perspective), checkpoint-level — same family as 15.1D/15.1F.

## 8. Primary sharpness feature (locked)

`sharp_value_fragility_v1 = (n_good_10es <= 2) AND (worst_top5_loss_es >= 0.10) AND
(legal_move_count >= 8)`. Engine-side objective value fragility. **Not human obviousness;
not a complete account of difficulty.** Secondary: `_relaxed`, `_strict`, and continuous
`n_good_10es` / `worst_top5_loss_es` / `best_second_gap_es` / `top5_entropy_es` /
`top1_softmax_prob_es`. Surface-bait diagnostics exploratory only.

## 9. Primary clock contrast and estimand

`60_180` vs `over_180`, interacted with `sharp_value_fragility_v1`. Estimand =
`[Δloss(60_180−over_180 | sharp)] − [Δloss(60_180−over_180 | non-sharp)]` = the interaction
coefficient. **Positive ⇒ low-clock association is larger when the position is sharp.**
Secondary: `under_60` vs `over_180` (sparse, exploratory) and the full fine-clock interaction.

## 10. Model controls

`C(clock_bucket, ref=over_180) + sharp_value_fragility_v1 + interaction
+ C(selected_position_type, ref=move_10) + C(eval_band, ref=decided) + rating_z
+ C(month, ref=2024_09) + C(termination_binary, ref=board_decided)`. Rating: linear
`rating_z` (train-only moments) primary, per 15.1F; quantile-bin / quadratic as sensitivity.
Estimate on train+val; test reserved as locked confirmation; no test-set selection.

## 11. Uncertainty and replication rule

Mover-player-clustered bootstrap (`clustered_uncertainty.cluster_bootstrap_refit` +
`summarize_contrasts`), 200 replicates, seed 42; per-month then pooled (month control).
**Strong support** requires: positive interaction in **both months**, **pooled CI excludes
zero**, not driven by a single checkpoint/eval band/mate-band/termination channel, and
direction surviving the robustness checks (esp. continuous-eval and board-decided-only).

## 12. Robustness checks

The 12 pre-registered checks (PREREGISTRATION §C3c.13): month replication; board-decided-only;
termination control; eval control (band + continuous cp); rating spec (linear + bins/quadratic);
checkpoint controls + per-checkpoint estimates; sharpness-threshold sensitivity
(relaxed/strict, no tuning); large-loss secondary targets (logistic ES>0.05/0.10);
clipped-cp-loss secondary; **exploratory** surface-bait moderator (not obviousness, no
headline); cluster sensitivity (mover/game/White-Black); mate-band sensitivity.

## 13. Kill / no-claim criteria

**Power bottleneck is the sharp × `60_180` cell** — measured read-only at **≈348 (2024-09)
/ 329 (2024-10), ≈677 pooled**, just above the project's ≥300 CI threshold. If after primary
filters this cell falls materially below ~300/month or the bootstrap interaction CI is
uninformatively wide → **underpowered / no claim**. Also no-claim if: the feature fails to
join (it does not — 100% coverage), becomes near-degenerate, results depend on post-hoc
threshold changes, appear **only** in surface-bait, or **only** after switching the primary
clock contrast. `under_60 × sharp` (≈110/month) is exploratory only.

## 14. Explicit non-claims

Not causal; no "time pressure causes worse moves/reasoning"; no claim sharpness is proven
before the model runs; no claim the v1 feature captures all human difficulty; **no claim
human obviousness has been modeled**; no "Stockfish is ground truth"; no "DRAW is solved";
no "best human predictor"; no "degradation curve". On strong support, the moderation is a
**small, secondary, predictive/descriptive** finding on top of eval-state-dominant move
quality.

## 15. Recommended next ticket

**14.2B — Sharpness Interaction Modeling Implementation.** Fit the locked §C3c model
(per-month + pooled + locked-test confirmation; mover-player-clustered bootstrap; the 12
robustness checks; the success/weak/null/kill criteria), reusing `controlled_move_quality`
+ `clock_association_robustness` + `clustered_uncertainty`. No design changes without a
logged deviation. Prior-trajectory extraction remains an optional follow-up.
