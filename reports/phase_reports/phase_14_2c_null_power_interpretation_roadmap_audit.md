# Phase 14.2C — Null / Power Interpretation and Roadmap Reconciliation Audit

**Labels:** AUDIT / DESIGN | doc-only, no modeling
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Interprets the 14.2B C3c result and reconciles the roadmap. **No model was run.** The
disciplined reading:

> **C3c is not confirmed. C3c is not disproven. C3c is underpowered / no-claim under the
> pre-registered criteria.**

The pooled train+val interaction is **directional only** (+0.0102 [+0.0013, +0.0194]); it
failed the locked criteria for two reasons that are *both* informative: (a) the limiting
sharp×`60_180` per-month cell fell to **297 / 282 (< 300)**, and (b) the **locked test split
did not confirm** (pooled test +0.0012; 2024-10 sign-flipped to −0.0035). A power audit shows
the per-month ≥300 gate is **structurally hard to clear** at the 250k-prefix scale (sharp ≈
13% of a ~2,200-row monthly `60_180` cell ⇒ ≈290/month), so ordinary additional months grow
**pooled** precision but not the per-month cell. **Recommendation: freeze C3c as
"directional but underpowered / no-claim" and proceed to a doc-level consolidation (14.2D),
because the effect is small, secondary to eval state, and did not confirm out-of-sample** —
with a clearly described **fallback** (a third-month enrichment audit + rerun of the *same
locked model*) if the project later decides C3c is worth the multi-stage engine compute.
**Thresholds were not changed; no model was rerun.** Not causal; not human obviousness.

## 2. Files inspected

PREREGISTRATION.md (§C3c), ROADMAP.md, EXPERIMENT_LOG.md; the 14.2B reports
(`sharpness_interaction_{2024_09,2024_10,combined}.md`, `phase_14_2b…`); the supporting
arc reports (`multipv_sharpness_combined`, `c4_move_quality_arc_summary`,
`clock_association_robustness_combined`, `controlled_move_quality_combined`). Read-only count
check of the joined estimation frame (cell totals + sharp rate).

## 3. Files modified

- `ROADMAP.md` — 14.2C complete; next pointer → 14.2D (consolidation; enrichment fallback named).
- `EXPERIMENT_LOG.md` — EXP-035.
- `PREREGISTRATION.md` — short 14.2C interpretation note under §C3c (no design rewrite).
- This phase report (created).

## 4. 14.2B result recap

- **Target:** `expected_score_loss` (mover perspective), non-mate. **Feature:**
  `sharp_value_fragility_v1`. **Contrast:** `60_180` vs `over_180` × sharp (DiD = interaction
  coef). **Model:** controlled OLS (checkpoint + eval band + rating_z + month + termination).
  **Uncertainty:** mover-player-clustered bootstrap, 200 reps, seed 42.
- **Cell adequacy (train+val):** sharp×`60_180` = 297 (2024-09) / 282 (2024-10); pooled 579.
- **Train+val interaction:** 2024-09 +0.0074 [−0.0079, +0.0217] (contains 0); 2024-10 +0.0131
  [+0.0001, +0.0274] (excl 0); pooled +0.0102 [+0.0013, +0.0194] (excl 0); same-sign both.
- **Locked test confirmation:** pooled +0.0012; 2024-09 +0.0054; 2024-10 **−0.0035** (sign flip).
- **Robustness headline:** not used to upgrade (primary criteria failed).
- **Classification:** UNDERPOWERED / NO CLAIM.

## 5. Why the result is underpowered / no-claim

Three separable reasons (none is a "null"):

1. **Cell adequacy.** sharp×`60_180` train+val was 297 / 282 — **2024-10 below the locked
   ≥300/month rule**, 2024-09 borderline. The pooled 579 is adequate, but the pre-registration
   required **per-month** adequacy, which binds.
2. **Month-specific uncertainty.** 2024-09 is positive but its CI **includes zero**; 2024-10 is
   positive and only **barely** excludes zero. Not the "positive in both months with resolvable
   CIs" the strong-support rule requires.
3. **Test confirmation.** The reserved test split did **not** confirm: pooled test +0.0012 is
   near zero and **2024-10 flips sign** (−0.0035). So the train+val signal is not stable
   out-of-sample — a fragility beyond mere cell count.
4. **Robustness discipline.** Per the lock, robustness checks **cannot upgrade** the
   classification once primary criteria fail; any positive robustness cell is **secondary only**
   and not a finding.

## 6. Power and cell-count bottleneck

Read-only counts (train+val): the `60_180` clock cell is ≈2,208 (2024-09) / 2,244 (2024-10),
of which **≈13% are sharp** ⇒ sharp×`60_180` ≈ **297 / 282**. Implications:

| Scenario | sharp×`60_180` per month | pooled |
|---|---|---|
| Current (2 months) | ~290 | 579 |
| +1 ordinary month (3 total) | ~290 (unchanged) | ~870 |
| +2 ordinary months (4 total) | ~290 (unchanged) | ~1,160 |

**Key structural fact:** ordinary additional months **do not raise the per-month cell** — they
only grow **pooled** precision and add replication. So the locked **per-month ≥300 gate cannot
be reliably cleared by adding ordinary months**; clearing it would require either (a) a newly
pre-registered **pooled-power** criterion (a new analysis, explicitly labeled), or (b)
**sharp-position oversampling** (a new sampling design / re-weighted estimand). Neither is a
"fix" to the existing locked C3c — both are new analyses.

## 7. Options considered

- **A — add one ordinary 10+0 month, rerun the same locked model.** Clean continuation, same
  DGP/pipeline, no threshold change; grows pooled precision + a 3-month replication. But the
  per-month gate stays ~290 (still <300), and it costs a full pipeline pass (parse → Stockfish
  eval → next-move-loss → MultiPV; multi-hour engine compute).
- **B — add two months.** Stronger pooled power and replication; more compute/time; per-month
  cell still ~290.
- **C — sharp-position oversampling.** Directly enriches the scarce cell, but changes the
  sampling design / estimand → **a new pre-registered design**, less comparable to the
  full-population two-month extraction.
- **D — relax the sharpness threshold.** **Forbidden** for the existing C3c claim (thresholds
  locked pre-modeling); only admissible as a new, separately pre-registered exploratory
  analysis. High p-hacking risk. Not pursued.
- **E — accept underpowered/no-claim and consolidate.** Scientifically clean; preserves the
  honest limitation; avoids a compute sink on a small secondary effect that did not confirm
  out-of-sample. Leaves the directional signal unresolved (acceptable).
- **F — pivot to C3a/C3b outcome/flagging sharpness.** A *different* question (outcome/flagging
  channel, possibly larger cells); does **not** resolve C3c move-quality moderation; needs its
  own audit + pre-registration. Not a rescue of C3c.

## 8. Recommendation

**Primary: Option E — freeze C3c as "directional but underpowered / no-claim" and proceed to a
doc-level consolidation (14.2D).** Rationale: (1) the effect is small (~+0.01 ES loss) and
**secondary** to the eval-state-dominant move-quality structure; (2) it **did not confirm on
the locked test split** (2024-10 sign flip) — a fragility that more data may not fix; (3) the
per-month ≥300 gate is **structurally unreachable with ordinary months**, so a clean
resolution would require a *new* design anyway; (4) the project headline (the C4 arc) is
already settled, so additional multi-stage engine compute is hard to justify for a fragile
secondary moderation.

**Fallback: Option A — Third-Month Power Enrichment Audit** (plan-only): if the project judges
C3c worth resolving, audit which ordinary month to add (e.g. 2024-11), estimate compute, and
**rerun the identical locked C3c model** on the enriched data — explicitly noting that a
pooled verdict requires a freshly pre-registered pooled-power criterion (the per-month gate
will still ~fail). **Never** relax thresholds to manufacture a claim.

**Not recommended now:** Option C/D (new designs / threshold relaxation) and Option F (pivot)
as a *response to C3c* — F remains available later as an independent sharpness question.

## 9. Roadmap reconciliation

ROADMAP next pointer → **14.2D — C3c Underpowered Result Consolidation** (doc-only: write the
final limitation language; fold C3c into the move-quality arc story as "directional but
underpowered/no-claim"; no further modeling). The **Third-Month Power Enrichment Audit** is
recorded as the named **fallback** the user may select instead; **14.3A — Outcome/Flagging
Sharpness Audit** remains a separate, later option. No modeling-implementation pointer is set.

## 10. PREREGISTRATION status

§C3c keeps its locked design and the 14.2B post-result note. This audit adds only a short
14.2C interpretation line (directional train+val signal; did not pass locked criteria; any
rerun = same locked model on enriched data, or a newly pre-registered design). **The locked
model and criteria are not rewritten.**

## 11. Explicit non-claims

- **C3c is not confirmed; C3c is not disproven; it is underpowered / no-claim.**
- The positive pooled train+val estimate is **directional only**.
- No causality; no "time pressure causes worse moves/reasoning".
- **No human-obviousness claim** (the v1 feature is an engine-side proxy).
- **No threshold relaxation after seeing results.**
- No C3a/C3b outcome/flagging claim (not modeled).
- No "degradation curve"; Stockfish eval is objective context, not ground truth; DRAW not
  solved; not a best-predictor claim.

## 12. Recommended next ticket

**14.2D — C3c Underpowered Result Consolidation** (doc-only final limitation write-up).
**Fallback if resolving C3c is desired:** *14.2D — Third-Month Power Enrichment Audit*
(plan-only; rerun the same locked model on +1 ordinary month, with a freshly pre-registered
pooled-power criterion). C3a/C3b outcome-sharpness (14.3A) is a separate later arc.
