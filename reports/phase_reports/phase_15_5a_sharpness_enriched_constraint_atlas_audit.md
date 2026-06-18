# Phase 15.5A — Sharpness-Enriched Constraint Atlas Audit

**Labels:** AUDIT / DESIGN | report-only (no MultiPV, no Stockfish, no models, no figures, no data artifacts)
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (design audit)

## 1. Executive summary

Phase 15.4 found a small, replicated, **fragile** conditional clock residual on next-move
expected-score loss (focal `60_180` vs `over_180` ≈ +0.0009; attenuates under
continuous-eval control and is borderline board-decided-only). Phase 15.5 asks whether
this residual **localizes to objective positional sharpness / value fragility**. This
ticket (**15.5A, design-only**) audits whether the existing MultiPV sharpness artifacts
can support a sharpness-enriched atlas/model. **Finding: existing sharpness is
checkpoint-only and White-to-move only** — joining to the dense substrate (via the
corrected key `dense.ply = checkpoint_ply + 1`) covers **121,165 rows = 4.36% of the
2.78M dense headline rows, all White mover**, four plies/game. The C3c-critical
`sharp × 60_180` cell is ~675 pooled (~350/month) — still **exploratory/underpowered**.
No MultiPV/Stockfish/models/figures were run; no artifacts created.

**Recommendation: Option D.** 15.5B should build a **checkpoint-overlap** sharpness-
enriched atlas + exploratory `clock × sharpness` model on the matched ~121k White-mover
rows, **without running full dense MultiPV** (prohibitive, §16). The `sharp × 60_180`
interaction must be labelled **exploratory/no-claim** given the cell counts; a sampled
dense MultiPV extraction is deferred to a later explicit ticket only if the checkpoint-
overlap signal warrants it. The prior C3c status (directional, underpowered, **not
confirmed, not disproven**) is preserved.

## 2. Why sharpness now

After conditioning on eval/phase/rating/termination (15.4D), the remaining clock residual
is small and fragile. Sharpness is a plausible **moderator**: positions differ in how
much a sub-optimal move costs (objective value fragility). The Phase 15.5 goal is to
**locate where the clock residual concentrates** — descriptive localization, **not** a
proof of causal degradation and **not** a claim that sharp positions cause blunders.

## 3. Prior sharpness evidence and current claim status (preserved)

From Phase 14 (14.1–14.2D, EXP-030/031, C3c):
- Sharpness = **objective value fragility**, MultiPV-5 depth-12; explicitly **not** human
  obviousness / human difficulty (surface-bait tags are exploratory only).
- Primary composite `sharp_value_fragility_v1` = `n_good_10es ≤ 2 AND worst_top5_loss_es
  ≥ 0.10 AND legal_move_count ≥ 8`; base rate ≈ 0.14 (confirmed: 0.142 / month here).
- C3c `clock=60_180 × sharp_value_fragility_v1` move-quality interaction: pooled
  train+val **directional positive** (~+0.010), per-month mixed (one month CI excluded 0,
  one contained 0), **test pooled near zero**; the sharp × 60_180 cells were
  **underpowered**. **Final status: not confirmed, not disproven (no-claim).**

This audit does **not** rewrite that as a success or a failure.

## 4. Non-claims and interpretation boundaries

Not causal; **not** human difficulty / human obviousness; **not** "sharp positions cause
blunders"; Stockfish/MultiPV is objective value context, **not** ground truth and **not**
a measure of human difficulty; **not** confirming sharpness moderation unless evidence
supports it; **not** disproving C3c unless evidence supports it; **not** cross-time-control;
**not** full-dense-sharpness (existing sharpness is checkpoint-only). Allowed language:
objective value fragility; positional sharpness proxy; conditional association;
descriptive localization; moderation candidate; exploratory/underpowered; not causal.

## 5. Available artifacts and schemas

**Dense move-quality** (`dense_move_loss_2024_09/10_250k_v1.parquet`, gitignored):
2,933,756 rows (1,496,890 + 1,436,866), 65 cols; key `game_id + ply`; both colors;
`expected_score_loss`/`cp_loss_clipped`/`cp_loss_raw`, `clock_before_s`/`clock_fraction`,
`eval_band`, `phase`, `mover_elo`, `termination`/`is_time_forfeit`, `mover_player_hash`,
`is_mate_band`, `status`.

**MultiPV sharpness** (`multipv_sharpness_2024_09/10_250k_v1.parquet`, gitignored):
**64,371 (09) / 61,868 (10) rows** (~126k total), 140 cols; key
`game_id + checkpoint_ply + selected_position_type` (`checkpoint_ply ∈ {20,40,60,80}` =
move_10/20/30/40); **`side_to_move` = white for ALL rows** (checkpoints are even-ply →
White to move); MultiPV-5 depth-12; `pre_fen`, `pre_sf_eval_cp`, `pv1..5_*`,
`sharp_value_fragility_v1`(+`_relaxed`/`_strict`), `sharp_score_candidate`,
`best_second_gap_es`, `n_good_10es`(+censored), `worst_top5_loss_es`, `legal_move_count`,
`top5_entropy_es`, `viable_fraction_*`, surface-bait tags, `is_mate_band`, `status`.

A 1,000-row pilot (`multipv_sharpness_pilot_2024_09_250k_v1.parquet`) also exists.

## 6. Dense–sharpness join feasibility (key section)

- **Sharpness is checkpoint-only** (4 plies/game: move_10/20/30/40) and **White-to-move
  only**. It is **not** dense per-ply.
- **Correct join key:** sharpness describes the position *after* `checkpoint_ply`
  half-moves (White to move). The dense move played *from* that position is at
  **`dense.ply = checkpoint_ply + 1`** (White mover) — matching the checkpoint
  next-move-loss semantics (15.0C). A naive `dense.ply == checkpoint_ply` join is
  **wrong** (it matches the Black move *into* the checkpoint; empirically all-Black) and
  must not be used.
- **Coverage (corrected join), measured read-only:**

| month | dense headline | matched | % | mover colors |
|---|---|---|---|---|
| 2024-09 | 1,416,313 | 61,732 | 4.36% | white only |
| 2024-10 | 1,362,459 | 59,433 | 4.36% | white only |
| **combined** | **2,778,772** | **121,165** | **4.36%** | white only |

- Coverage is **checkpoint-overlap only**, **White-mover only**, ~4 rows/game. It does
  **not** include Black moves and does **not** include the dense low-clock mass.

**Conclusion: existing sharpness supports a checkpoint-overlap (White-to-move)
sharpness atlas/model, NOT a full dense per-ply sharpness atlas.**

## 7. Existing sharpness metric definitions

Primary (mover/side-to-move = White perspective): **`sharp_value_fragility_v1`** (binary;
`n_good_10es ≤ 2 ∧ worst_top5_loss_es ≥ 0.10 ∧ legal_move_count ≥ 8`; rate 0.142).
Continuous candidates: `best_second_gap_es` (gap best→2nd in ES), `n_good_10es` (count of
near-best moves within 0.10 ES, censored at K=5), `worst_top5_loss_es`, `top5_entropy_es`,
`viable_fraction_10es_lower_bound`, `sharp_score_candidate`. Variants: `_relaxed`,
`_strict`. Orientation: **objective value fragility from the side-to-move perspective —
NOT human obviousness, NOT tactical-puzzle difficulty.** Surface-bait tags are
exploratory only and must not be a headline.

## 8. Cell-count and power feasibility (matched White-mover rows)

Combined matched rows by clock (corrected join): `under_10` 179, `10_30` 439, `30_60` 938,
`60_180` 5,181, `over_180` 114,428. Sharp (`sharp_value_fragility_v1=1`) counts:

| cell | combined n | sharp n | board-decided sharp n |
|---|---|---|---|
| sharp × 60_180 | 5,181 | ~675 | ~455 |
| sharp × under_60 (<60 s) | ~1,556 | ~208 | smaller |
| sharp × under_10 | 179 | tiny | tiny |

Per-month the `sharp × 60_180` cell is ~330–350; pooled ~675 (**< the 1,000 headline
threshold**). The `sharp × under_60` and `sharp × under_10` cells are **sparse (<200–300)**
→ **no-claim**. **This is the same underpowered corner that left C3c unresolved**, and the
dense substrate does **not** improve it because sharpness coverage is still checkpoint-
limited and White-only. **15.5B can support exploratory analysis only for the
sharp × low-clock interaction; the eval-band/phase marginal sharpness contrasts have
ample rows (tens of thousands) and can be descriptive headline.**

## 9. Analysis path options

- **Option A — existing sharpness only:** join checkpoint sharpness to dense (corrected
  key); checkpoint-overlap, White-only, ~121k rows; low compute; preserves depth/settings;
  but not dense-wide and the focal interaction stays underpowered.
- **Option B — full dense MultiPV:** run MultiPV-5 d12 over ~2.78M dense rows →
  **compute-prohibitive** (~tens of hours, §16); not acceptable now.
- **Option C — stratified dense sharpness sample:** MultiPV on a clock/eval/phase/rating-
  stratified dense sample (both colors); better coverage than checkpoints; still a new
  Stockfish extraction needing its own audit/implementation ticket.
- **Option D — hybrid:** use existing checkpoint sharpness for 15.5B; let the result
  decide whether a sampled dense extraction (Option C) is worth a later ticket.

**Recommended: Option D.** 15.5B uses existing checkpoint sharpness (Option A mechanics)
and explicitly frames coverage/power; full dense MultiPV (B) is **not** run; sampled dense
sharpness (C) is deferred to a later explicit ticket **only if** the checkpoint-overlap
signal is promising-but-inconclusive.

## 10. Recommended 15.5B scope

**15.5B — Existing-Sharpness Checkpoint-Overlap Join + Atlas/Exploratory Model.**
- New module (e.g. `src/chess_mhsuc/sharpness_enriched_atlas.py`); do not clobber
  `multipv_sharpness.py`, `sharpness_interaction.py`, `dense_constraint_atlas.py`,
  `dense_controlled_model.py`.
- Load dense + sharpness; **join on `dense.ply = checkpoint_ply + 1`** (validated; assert
  matched rows are White mover); validate coverage (~4.36%, White-only) and **state the
  checkpoint-overlap, White-to-move limitation prominently**.
- Sharpness-enriched **atlas tables/figures** for matched rows (sharp vs non-sharp ES loss
  by clock/eval/phase) — descriptive, month-replicated.
- **Exploratory** controlled `clock × sharpness` model on matched rows with game-clustered
  (and mover-player) bootstrap; the `60_180 × sharp` interaction is **labelled
  exploratory/no-claim** given §8 cell counts.
- Report + phase report; update ROADMAP/EXPERIMENT_LOG. **No MultiPV/Stockfish.**

If, on closer inspection, even the marginal sharpness contrasts are too thin to be useful,
15.5B should instead be a **sharpness coverage/power report**, and a **stratified dense
sharpness extraction audit** becomes a later ticket.

## 11. Sharpness-enriched atlas design (checkpoint-overlap, White-to-move)

Figures/tables (all **titled "checkpoint-overlap, White-to-move"**, month-replicated):
1. sharp vs non-sharp ES loss by clock bucket;
2. sharp vs non-sharp clipped CP loss by clock bucket;
3. large-loss probability (ES≥0.10) by clock × sharpness;
4. eval-band-conditioned sharp vs non-sharp ES loss (ample rows → headline-capable);
5. rating × sharpness ES loss (where cells ≥ threshold);
6. month replication: Sep vs Oct sharp/non-sharp summary.
Sparse cells (clock × sharpness low-clock) hidden/labelled per §15.

## 12. Sharpness-enriched controlled model design (exploratory)

```
expected_score_loss
  ~ C(clock_coarse, ref=over_180) + sharp_value_fragility_v1
  + C(clock_coarse) × sharp_value_fragility_v1
  + C(eval_band, ref=decided) + C(phase) + C(rating_bin) + C(month)
  + C(termination_channel, ref=board_decided)
```
(mover_color is constant = White on matched rows → omit.) Primary interaction of interest
`60_180 × sharp_value_fragility_v1`; **exploratory/no-claim** (cell ~675 pooled).
Secondary: `under_60 × sharp` (sparse → no-claim), continuous sharpness metrics
(`best_second_gap_es`, `n_good_10es`), large-loss (ES≥0.10) target, clipped-cp target,
board-decided-only, month-specific replication. Reuse `dense_controlled_model`'s
sufficient-statistics game-clustered bootstrap. **If a month-specific interaction sign
flips or CIs straddle 0, do not claim replication** (echoing C3c).

## 13. Termination-channel strategy

Include `termination_channel` (board_decided ref) as a control in the model; provide a
board-decided-only robustness (matched board-decided 60_180 ≈ 3,356 rows, sharp ~455) and
a time-forfeit diagnostic. No causal interpretation; consistent with the 11.2B flagging
reframing.

## 14. Month-replication strategy

Every headline sharpness result shows Sep and Oct separately, or pooled **with** a
month-specific table. If the `clock × sharpness` interaction signs disagree across months
(as in C3c), **do not claim replication** — report as exploratory/mixed.

## 15. Sparse-cell policy

Reuse 15.4B/15.4D policy: n<200 suppress/no-claim; 200–999 exploratory/sparse; ≥1000
headline-capable. For interaction cells additionally require enough **game clusters**
(and player clusters) per sharp × clock cell, not just rows.

## 16. Full dense sharpness feasibility and cost

MultiPV-5 depth-12 ≈ 66–106 ms/position (14.1A/B smoke). Over ~2,778,772 dense headline
rows that is **~51–82 hours** of Stockfish on the local Mac — **compute-prohibitive** and
out of scope before Phase 16. A **stratified sample** (e.g. ~150–300k positions enriched
in low-clock/sharp cells, both colors) would be ~3–9 h and *could* close the power gap,
but it is a **new Stockfish extraction** requiring its own audit + implementation +
machine-awake plan. **Do not run full dense MultiPV.** Defer sampled extraction to a later
ticket gated on the 15.5B checkpoint-overlap result.

## 17. Output tables and reports for 15.5B

Report `reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md`; phase
report `reports/phase_reports/phase_15_5b_sharpness_enriched_constraint_atlas_implementation.md`;
figures under `reports/figures/phase_15_5_sharpness_enriched_atlas/`; module
`src/chess_mhsuc/sharpness_enriched_atlas.py`. Tables: join-coverage (matched %, White-only,
checkpoint plies), sharp-rate by clock/eval, sharp vs non-sharp loss by clock (month-split),
`clock × sharpness` interaction (exploratory, with cell counts + clusters), board-decided
robustness, comparison to C3c.

## 18. What 15.5B must not do

No Stockfish; no MultiPV extraction; no full-dense-sharpness claims (coverage is 4.36%
checkpoint-overlap, White-only); no causal claims; **no confirming sharpness moderation
unless evidence supports it; no C3c rewrite**; no Phase 16 cross-time-control; no synthesis/
packaging; no modifying dense/sharpness artifacts; no ES-transform refit; no threshold
changes (unless secondary-only + documented).

## 19. ROADMAP implications

Recommended Phase 15.5 sequence:
- **15.5A** — this audit (complete).
- **15.5B** — Existing-Sharpness Checkpoint-Overlap Join + Atlas/Exploratory Model
  (existing sharpness only; no MultiPV).
- **15.5C** — Sharpness Result Consolidation / C3c Claim Update (and decide whether a
  stratified dense sharpness extraction deserves a later ticket).

If 15.5B coverage/power proves too limited even for exploratory value, 15.5B collapses to a
coverage/power report and 15.5C becomes a Stratified Dense Sharpness Extraction Audit. **Do
not move to Phase 16 until the Phase 15.5 sharpness question is properly resolved or
explicitly parked.**

## 20. Open questions for Malachi (defaults in bold)

1. 15.5B uses **existing checkpoint sharpness only** (checkpoint-overlap, White-to-move),
   despite non-dense coverage — **yes** (default), given §6/§8.
2. Attempt full dense MultiPV — **no** (default; ~51–82 h).
3. Design a sampled dense sharpness extraction later — **only if** the 15.5B checkpoint-
   overlap result is inconclusive-but-promising (default).
4. Label sharpness figures **"checkpoint-overlap, White-to-move"** prominently — **yes**.
5. Controlled `clock × sharpness` — **exploratory/no-claim** (default), given the
   `sharp × 60_180` cell ≈ 675 pooled; headline only the well-powered marginal sharpness
   contrasts (eval-band/clock with tens of thousands of rows).

## Non-claims (summary)

Design-only audit; no MultiPV/Stockfish/models/figures/data artifacts. Existing sharpness
is checkpoint-only, White-to-move; the dense-wide sharpness atlas does **not** exist.
Predictive/descriptive; not causal; not human difficulty/obviousness; Stockfish not ground
truth; C3c status preserved (not confirmed, not disproven). C4 and C3c unchanged.
PREREGISTRATION unchanged.
