# Phase 16.2D — Rating-Bucket / Clock Moderation Audit

**Ticket:** 16.2D — Rating-Bucket / Clock Moderation Audit (audit / statistical-design only)
**Status:** complete — DESIGN-ONLY. No analysis code, no models, no figures, no Stockfish, no extraction,
no Parquet/JSON/model/figure modified. Read-only cell-adequacy inspection only.

> Predictive/descriptive only — NOT causal. Raw Lichess ratings are NOT comparable across control pools
> (within-control × month rating quintiles/percentiles only). "Buffer" is used ONLY as a descriptive
> contrast label, never a causal protective mechanism. Stockfish eval is objective context, not ground
> truth. T2 remains descriptive stability (not equivalence). C3c sharpness moderation stays unresolved.

## 1. Executive summary

Designs the next Phase-16 analysis: **does relative player rating moderate the observed clock_fraction →
next-move-quality relationship, and does that moderation differ across 3+0, 5+0, 10+0?** Phase 16.2B used
rating quintiles only as main-effect controls + a heatmap; it never tested `clock_fraction × rating` or
`time_control × clock_fraction × rating`. No current claim says higher-rated movers are more/less
insulated from low-clock states.

Locked design: rating = within-control × month **quintiles** (primary categorical) + within-control ×
month **percentile [0,1]** (primary continuous/parsimonious); raw 200-Elo bins within-control = viz only.
Primary moderation estimand **M(c) = D(c,Q5) − D(c,Q1)** where D = adjusted critical-minus-high ES-loss
contrast; cross-control **M(3+0)−M(10+0)**, **M(5+0)−M(10+0)**. Five-test primary family (Holm-adjusted).
Mover-player-clustered uncertainty primary; board-decided-only and endgame-only mandatory localizations;
both-month replication.

**Cell-adequacy verdict:** all-games rating×clock cells are headline-capable everywhere; **board-decided-
only critical-clock low quintiles in 10+0 are exploratory-tier (~199–213 games/movers)** → the continuous
percentile spec is the better-powered route there, and the categorical Q5−Q1 board-decided 10+0 contrast
is flagged exploratory. Endgame-only critical×quintile is well-powered. Recommended next ticket:
**16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation** (dedicated new module). Increment
contrasts and Phase 17 stay deferred.

## 2. Evidence and artifacts reviewed

16.2C consolidation; 16.2B implementation report + main analysis report (incl. executed R8); 16.2A design
audit; Phase-11.3 player-disjoint/clustering work + `clustered_uncertainty.py`;
`cross_time_control_analysis.py` + tests (read-only). Read-only cell audit →
`/tmp/phase_16_2d_rating_cell_audit.txt` (not committed). Six dense artifacts confirmed present and
gitignored.

## 3. Existing rating treatment

16.2B: rating quintiles computed within control × month; included as a main-effect control; rating×clock
heatmap (Fig 6); raw cross-pool comparisons prohibited. **NOT done:** any formal `clock_fraction ×
rating` or `time_control × clock_fraction × rating` interaction. So no project claim establishes
rating-associated insulation from low-clock states — that is the novel target here.

## 4. Scientific questions and estimands

- **R1 (average rating gradient, descriptive positive control):** do relatively higher-rated movers have
  lower average next-move loss within each control × month?
- **R2 (within-control rating moderation):** does the critical-vs-high contrast differ across rating
  groups within each control?
- **R3 (cross-control rating moderation):** does that rating-related attenuation/amplification itself
  differ across controls?
- **R4 (board-decided rating moderation):** does R2/R3 survive restricting to board-decided games?
- **R5 (rating × time-forfeit):** how does player-side game-level time-forfeit prevalence vary by relative
  rating within each control?

Move quality (R1–R4) and flagging (R5) are kept separate — no single "rating resilience" effect.

## 5. Rating representation

**Primary categorical = within-control × month mover-rating quintiles (Q1–Q5)** = relative rating rank
within the relevant control-month pool. Cutpoints (Q1≤/Q2≤/Q3≤/Q4≤), from the audit:

| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ |
|---|---|---|---|---|---|
| 3+0 | 2024-09 | 1495 | 1717 | 1878 | 2052 |
| 3+0 | 2024-10 | 1503 | 1720 | 1885 | 2055 |
| 5+0 | 2024-09 | 1272 | 1500 | 1685 | 1882 |
| 5+0 | 2024-10 | 1256 | 1495 | 1682 | 1880 |
| 10+0 | 2024-09 | 1269 | 1510 | 1702 | 1896 |
| 10+0 | 2024-10 | 1275 | 1507 | 1692 | 1888 |

3+0 cutpoints sit ~200 Elo above 5+0/10+0 → **Q5 in 3+0 is NOT the same absolute skill as Q5 in 10+0.**
The existing deterministic quantile assignment (linear-interpolation cutpoints, left-closed bins) remains
appropriate; ties at round-number Elos exist (most-common Elo ≈ 2,843/6,746 rows of ~1.42M) but do not
destabilize quintile assignment.

**Primary continuous robustness = within-control × month rating percentile, scaled [0,1]** (rank/(n−1)
within stratum; higher = relatively higher rating; orientation LOCKED). Feasible: ~1,950 distinct Elo
values per stratum. Used for parsimonious trend + the three-way interaction; report the predicted
critical-minus-high contrast at percentile **0.10 vs 0.90** (not a one-unit coefficient).

**Secondary raw-Elo visualization = 200-Elo bins WITHIN a control only** (candidate <1200 / 1200–1399 /
… / 2200+; exact bins + tail collapsing locked after count audit — 3+0 has few <1200, 10+0 few ≥2200).
Never compared across pools as equivalent skill.

## 6. Clock representation

Retain 16.2B coarse buckets: critical ≤0.05 / low (0.05,0.15] / medium (0.15,0.50] / high >0.50 (ref
high). Primary moderation target **critical vs high**; secondary low vs high; exploratory medium vs high.
Fine 7-bucket clock_fraction stays descriptive (atlas) only.

## 7. Primary moderation contrasts

For control c, rating group q: **D(c,q) = adjusted ES loss(critical) − adjusted ES loss(high)** (positive
= more loss in critical clock). **Within-control rating contrast M(c) = D(c,Q5) − D(c,Q1).** M(c) < 0 =
the critical-clock gradient is *smaller* among the highest relative quintile = **rating-associated
attenuation of the critical-clock gradient** (NOT causal protection). Report D(c,Q1..Q5) — assess shape
(smooth / plateau / reversal / tail-concentrated), do **not** assume monotonicity. **Cross-control:
M(3+0) − M(10+0)** and **M(5+0) − M(10+0)** (three-way interaction, not causal).

## 8. Descriptive atlas design

9 proposed figures (consolidate if redundant): (1) clock_fraction × ES loss by quintile, panels per
control (headline Q1/Q3/Q5, all quintiles in tables); (2) critical-clock contrast by quintile per control
(months visible); (3) rating × clock heatmap (ES loss or large-loss prob) per control; (4) board-decided-
only critical-clock contrast by quintile; (5) M(3+0)/M(5+0)/M(10+0) with mover-player-clustered CIs;
(6) M(3+0)−M(10+0), M(5+0)−M(10+0); (7) player-side game-level TF prevalence by quintile, control × month;
(8) endgame-only rating moderation (mandatory — critical ≈ endgame); (9) month-replication summary for
primary contrasts. Game-cluster + player-cluster CIs on headline cells.

## 9. Within-control model design

Per control:
```
expected_score_loss ~ C(clock_fraction_coarse, ref=high) * C(rating_quintile, ref=Q1)
                    + C(eval_band, ref=decided) + C(phase) + C(month) + C(mover_color)
                    + C(termination_channel, ref=board_decided) + clock_gt_initial + neg_think
```
Derived contrasts: critical-vs-high and low-vs-high within each Q1–Q5; **Q5−Q1 difference in the
critical-clock contrast** (= M(c)) and the low-clock analogue. Rating main effects not interpreted across
controls. Audit confirms: design-matrix full-rank with the existing constant-column drop in
`_finalize`; the interaction adds 3 clock × 4 non-ref-quintile = 12 product columns (well-conditioned at
these cell counts); the existing weighted-OLS + sufficient-statistics cluster bootstrap helpers
(`fit_weighted_ols`, `weighted_cluster_bootstrap`, `contrast_ci`) can be reused **unchanged** — M(c) is a
deterministic linear combination of two interaction coefficients, extractable per bootstrap replicate.

## 10. Cross-control three-way model design

Avoid the full categorical TC × clock × 5-quintile as the only headline (interpretability + tail
sparsity). **Primary pooled = percentile-based:**
```
expected_score_loss ~ C(time_control, ref=10+0) * C(clock_fraction_coarse, ref=high) * rating_percentile
                    + C(eval_band) + C(phase) + C(month) + C(mover_color)
                    + C(termination_channel) + anomaly_flags     [game-normalized, equal control-month weights]
```
Primary pooled estimands: **difference in the 0.10→0.90 percentile rating moderation of the critical-clock
gradient for 3+0 vs 10+0, and 5+0 vs 10+0.** Full categorical three-way = exploratory/diagnostic only if
adequately powered. TC main effect descriptive, not causal.

## 11. Board-decided-only design (mandatory)

Refit all primary specs on `termination_channel == board_decided` (drop the constant termination term).
Primary board-decided contrast = Q5−Q1 critical-clock gradient per control — tests whether observed
rating moderation merely reflects differential flagging. **Power caveat (key audit finding):** 10+0
board-decided critical-clock low quintiles are thin — Q1 ≈1k rows/207 games/213 movers, **Q2 ≈1k/199/193
(below the 200 games/movers headline threshold)** → the 10+0 categorical Q5−Q1 board-decided contrast is
**exploratory-tier**; rely on the **continuous percentile** board-decided spec there (better powered), and
do not treat all-games and board-decided estimates as interchangeable. 3+0/5+0 board-decided are mostly
adequate (Q1/Q2 ~311–413 games).

## 12. Game-level time-forfeit rating analysis (R5)

**Recommend Option B — two player-side rows per game** (rating is player-specific; one row/game obscures
which side flagged). Feasibility CONFIRMED: in a TF game the **loser flagged**, derivable from
`result_class` + `mover_color` (decisive TF = WHITE_WIN/BLACK_WIN, ~29.7k of ~30.6k TF games);
**~892 DRAW-by-timeout games (~3%)** cannot attribute a flagging loser (flag + insufficient material) →
document + exclude from the player-side flagging outcome (or treat as non-forfeit-loss). Player-side row:
`game_id, color, player_rating, within-control-month quintile, did_player_forfeit_on_time, opponent_rating,
rating_diff, month, time_control`. Cluster at game AND player. Descriptive primary table: player-side TF
prevalence by control × month × quintile. Audit's first-row proxy shows a **weak/flat** gradient (3+0 Q1
0.317 → Q5 0.282; 5+0 0.248 → 0.229 non-monotone; 10+0 ~flat 0.11–0.12) — modest, to be tested properly
in 16.2E. Do not say rating causes resilience/prevents flagging.

## 13. Phase and eval-state handling

Critical-clock ≈ endgame (confirmed). Hierarchy: (1) all-phase model with the existing phase main effect
(lineage); (2) **endgame-only model mandatory** (well-powered: critical×quintile endgame ≥4k rows/≥700
games every control) — answers "within late-game positions, does relative rating modify the critical-clock
contrast?"; (3) avoid a primary clock × rating × phase (or 4-way) interaction. Eval band stays a mandatory
control; audit shows critical × quintile × eval cells are adequate except the `slight` band (1–2k rows,
exploratory). Robustness: non-mate headline; near-equal-vs-decided localization where powered; no claim
from sparse mate-band cells. Guard against rating moderation merely reflecting higher-rated players
reaching different eval states (eval band conditioned + eval-localized robustness).

## 14. Weighting and estimand policy

**Use game-normalized weights even within control** for rating moderation (rating groups differ in average
game length — higher quintiles reach more low-clock decisions, see §18). Pooled = game-normalized + equal
control-month aggregate weight (16.2B policy). Unweighted row-level = robustness. State estimand as
"average observed game/player" (game-normalized), with "average observed move" (unweighted) as the
contrast.

## 15. Clustered uncertainty

**Primary = mover-player-clustered bootstrap** for rating interactions (rating is player-associated,
repeated across many moves); **secondary = game-clustered.** Promotion rule: a rating-moderation result is
promoted only if month-specific directions are stable AND the pooled mover-player-clustered CI excludes 0
AND the game-clustered result is directionally consistent. For pooled analyses, cluster player hashes
across months and controls (not independent per stratum). Two-way game/player clustering: audit notes it
is not implemented in the sufficient-statistics bootstrap; if infeasible in 16.2E, report both one-way
cluster choices and take the more conservative (wider) interpretation. (Cross-control player overlap is
tiny ~240–450 movers; cross-month ~18–22% — so one-way mover clustering already captures most dependence.)

## 16. Month-replication policy

Every primary moderation contrast reports 2024-09, 2024-10, pooled + a class: replicated (same sign + both
month mover-player-clustered CIs exclude 0); directionally_replicated; pooled_only; not_replicated;
null_or_unresolved. Interaction contrasts use this classifier — **not** the T2 descriptive-stability
language.

## 17. Multiple-comparison policy

**Primary family = 5 tests:** M(3+0), M(5+0), M(10+0), M(3+0)−M(10+0), M(5+0)−M(10+0) (Q5−Q1 critical-
clock differences). **Report ordinary bootstrap CIs + Holm-adjusted inference across these 5.** Secondary
family = low-vs-high analogues. Exploratory = medium-vs-high, all pairwise quintiles, raw-Elo bins,
eval-band-specific interactions (no Holm; labeled exploratory). **No post-hoc selection of the strongest
quintile contrast.**

## 18. Cell adequacy and power audit

Thresholds: headline ≥1,000 rows ∧ ≥200 games ∧ ≥200 movers; exploratory 300–999 rows or 75–199 games/
movers; no-claim <300 rows or <75 games/movers (per control-month rating-clock cell).

Findings (`/tmp/phase_16_2d_rating_cell_audit.txt`):
- **All-games rating × coarse-clock (pooled):** headline-capable everywhere; thinnest is 10+0 Q1/Q2
  critical = ~4–5k rows / 762–804 games / 669–742 movers. ✔
- **Critical × quintile per month:** thinnest 10+0 Q1/Q2 = ~2k rows / 375–414 games / 337–392 movers —
  headline-capable per month but tight; pooled comfortable. ✔
- **Board-decided-only critical × quintile (pooled) — BINDING CONSTRAINT:** 10+0 Q1 ≈1k/207/213, **Q2
  ≈1k/199/193 (sub-threshold)** → 10+0 board-decided categorical Q5−Q1 = exploratory; use percentile spec.
  3+0/5+0 mostly adequate (≥311 games). ⚠ flagged.
- **Endgame-only critical × quintile (pooled):** well-powered (≥4k rows / ≥700 games all controls). ✔
- **Critical × quintile × eval (3+0):** `clear` dominates (8–12k); `slight` thin (1–2k, exploratory). ⚠
- **Descriptive composition:** critical-clock row counts *rise* with quintile (Q5 > Q1) — higher-rated
  movers reach more low-clock decisions (longer games / more moves), reinforcing game-normalized weighting.

Special-attention cells flagged: 10+0 Q1/Q2 board-decided critical (sub-threshold → percentile route);
slight-eval × rating × critical; raw-Elo tails (3+0 <1200, 10+0 ≥2200); player-side draw-timeout rows.

## 19. Robustness specifications

R1 board-decided-only · R2 endgame-only · R3 continuous percentile · R4 raw 200-Elo bins within control ·
R5 clipped-CP outcome · R6 ES≥0.10 outcome · R7 anomaly exclusion · R8 month-specific · R9 mover-player
clustering · R10 game clustering · R11 game-normalized vs unweighted · R12 equal/near-equal eval
localization · R13 full categorical vs parsimonious continuous three-way. Optional: R14 single-control
players only · R15 player fixed-effect feasibility (audit selection/sample loss first — do not promote
without it) · R16 minimum-decisions-per-player restriction.

## 20. Figure and table plan

Figures → `reports/figures/phase_16_2d_rating_clock_moderation/` (9 per §8; consolidate if redundant).
Tables: quintile cutpoints (6 strata); rating×clock cell counts (rows/games/movers); D(c,Q1..Q5) per
control; M(c) + cross-control differences with CIs + Holm; board-decided + endgame versions; player-side
TF prevalence by quintile; robustness matrix; replication-status table; claim-status table.

## 21. Claim ladder

- **RM1 (average rating gradient):** "Relatively higher-rated movers show lower observed average move loss
  within the sampled control-month pools." Descriptive positive control, not novel/causal.
- **RM2 (within-control rating moderation):** "The conditional critical-clock contrast is smaller/larger
  among relatively higher-rated movers within [control]." Only if replicated + cluster-robust.
- **RM3 (cross-control rating moderation):** "The rating-associated difference in the critical-clock
  gradient varies across observed time controls." Only if cross-control contrasts replicate.
- **RM4 (board-decided moderation):** "Rating moderation remains/attenuates after restricting to
  board-decided games" (with the 10+0 low-quintile power caveat).
- **RM5 (time-forfeit rating gradient):** "Observed player-side time-forfeit prevalence varies by relative
  rating within each sampled control." Descriptive, modest, non-causal.

"Buffer" allowed only as a defined descriptive contrast. Forbidden: rating causes resilience / protects
from clock pressure / immune to low clock / causes fewer blunders; lower-rated reason worse; fast chess
harms low-rated players.

## 22. Implementation architecture

**Create a dedicated `src/chess_mhsuc/rating_clock_moderation.py` + `tests/test_rating_clock_moderation.py`**,
importing validated helpers from `cross_time_control_analysis.py` (load/validate, headline population,
clock buckets, quintiles, percentile [new pure helper], anomaly flags, weights, game table, designs,
`fit_weighted_ols`, `weighted_cluster_bootstrap`, `contrast_ci`, `classify_replication`). Reason: protects
the settled 16.2B implementation, isolates interaction/contrast logic, keeps tests focused, avoids
overloading the cross-control CLI. If a helper is not cleanly importable, audit the smallest safe export
(do NOT refactor in 16.2D). Add: rating-percentile helper, interaction design builders, M(c)/cross-control
contrast extractors, Holm adjustment, player-side TF table builder.

## 23. Recommended 16.2E scope

**16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation:** load+validate the six artifacts;
reuse within-control-month quintiles + add within-pool percentiles; descriptive rating×clock atlas; per-
control clock × rating-quintile models + locked Q5−Q1 contrasts; pooled percentile TC×clock×rating model;
board-decided-only + endgame-only models; mover-player- and game-clustered uncertainty; five-test primary
family with Holm; player-side time-forfeit rating analysis (Option B, decisive-TF attribution); reports +
tracked figures; ROADMAP + EXPERIMENT_LOG. **Exclude:** increment, bullet, sharpness, new Stockfish, new
extraction, Phase 17.

## 24. Deferred branches

16.3 increment contrasts (3+0 vs 3+2, 5+0 vs 5+3); Think-Time Loss-Rate / Flagging-Signature Diagnostic;
15.5D stratified dense sharpness; broader monthly replication; Phase 17 packaging. Ordering: 16.2D audit →
16.2E rating implementation → 16.2F rating claim consolidation (if needed) → increment contrast →
packaging.

## 25. Open questions for Malachi

1. **Three-way headline form** — confirm the parsimonious **percentile** TC×clock×rating as primary, full
   categorical three-way as exploratory only? (Recommended: yes.)
2. **Board-decided 10+0 low quintiles** — accept exploratory-tier for the categorical contrast and lean on
   the continuous percentile there? (Recommended: yes.)
3. **Player-side TF (Option B)** — proceed with decisive-TF attribution + exclude ~3% draw-timeout? (Recommended: yes.)
4. **Multiple comparison** — Holm across the 5 primary contrasts + unadjusted CIs elsewhere? (Recommended: yes.)

---

**Non-claims (this ticket):** design-only; no code/models/figures/data/Stockfish/extraction. No causal
claims; "buffer"/"attenuation" are descriptive contrasts only. No "rating causes resilience", "rating
protects from clock pressure", "higher-rated immune to low clock", "rating causes fewer blunders", "lower-
rated reason worse", "fast chess harms low-rated players", "ratings comparable across pools", "time
pressure causes worse reasoning", "low clock causes blunders", "Stockfish is ground truth", "T2 is
equivalence", "sharpness moderation resolved", "DRAW solved". C4 & C3c unchanged. PREREGISTRATION unchanged.
