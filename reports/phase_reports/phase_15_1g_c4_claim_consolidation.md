# Phase 15.1G — C4 Claim Consolidation / Move-Quality Arc Summary

**Labels:** CONSOLIDATION / REPORTING | doc-only
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

The C4 / move-quality arc is now consolidated. The settled result, in conservative
language:

> **At the final-outcome level, clock features primarily capture flagging / time-forfeit
> risk (11.2B). At the next-move level, eval state is the dominant structure in
> expected-score (ES) loss (15.1B). After conditioning on checkpoint, eval band, rating,
> month, and termination, clock retains a small, replicated association with next-move ES
> loss (15.1D), which survives continuous-eval, late-only, board-decided-only,
> rating-specification, metric, and clustering robustness checks (15.1F). This association
> is predictive/descriptive — not causal — and is roughly 5–8× smaller than the eval-band
> structure.**

The descriptive (15.1B) and controlled (15.1D/15.1F) results are **not contradictory**:
15.1B's flat *marginal* clock cells were composition-masked, and conditioning on eval band
revealed a small residual that the marginal view averaged away. The one major unadjusted
confound is **prior trajectory** ("clock as symptom of past struggle"), which is absent
from the current artifacts; it is **deferred** (Task 11) and stated as the headline
limitation — the C4 clock claim is therefore held as predictive/descriptive only and never
as causal.

## 2. Why C4 was needed after termination decomposition

11.2B showed the replicated all-games E3→E4 clock-outcome residual collapses or
sign-reverses once time-forfeit games are removed, i.e. it is substantially the **flagging
channel**. 11.2C reframed the project away from "clock improves board-decided outcome
prediction" toward separating flagging risk from board move quality. That left an open
question 11.2B could not answer from final outcomes alone: *does low clock relate to worse
board play, not just to running out of time?* C4 answers it by **measurement** — next-move
ES loss at fixed checkpoints — rather than inference from outcomes.

## 3. Evidence chain by ticket

| Ticket | Question | Method | Key result | Implication for C4 | Caveat |
|---|---|---|---|---|---|
| 11.2B | Is the outcome clock residual board-play or flagging? | Prediction-side filter of frozen E3/E4 val preds by termination; game-cluster bootstrap | All-games −0.0138/−0.0120; board-decided +0.0010 (cz) / +0.0060 (sign-rev); time-forfeit −0.118/−0.131 | Outcome clock signal is **substantially flagging**, not board-decided outcome | Selection from filtering; Normal mixes mate/resign |
| 11.2C | How should the claim be framed? | Doc reframing | Clock residual = flagging channel; board-play question → C4 | Motivates a **move-level** test | Not causal |
| 11.3B | Do results survive repeated-player dependence? | Player-clustered bootstrap (mover/White/Black) | Flagging delta and eval-band structure both survive; game-cluster reproduces 11.2B exactly | Findings **robust to player leakage** | One-way clustering; two-way deferred |
| 15.1B | How does next-move loss vary descriptively? | Constraint Atlas, game-cluster CIs | No replicated **marginal** clock gradient; strong replicated **eval-band** pattern | Eval state dominates; marginal clock flat | Marginal cells composition-mixed |
| 15.1D | Controlled clock effect after covariates? | OLS adjusted-mean + mover-player bootstrap; large-loss logistic; locked test | Clock 60_180 +0.0034 pooled (excl 0, both months + test); eval-band ~5–8× larger; termination ≈0 after controls | Small **non-null** clock association emerges under controls | Coarse bands; sparse under_60; no trajectory |
| 15.1F | Is the small clock effect robust? | 12-check robustness matrix; locked 15.1E criteria | **SURVIVES** all mandatory checks (pooled 60_180 +0.0034 throughout) | Clock association is **robust + secondary** | Per-month subset CIs sometimes touch 0; no trajectory |

## 4. Numerical signature table

All values are adjusted/contrast estimates with 95% CIs; clock/eval contrasts are
mover-player-clustered unless noted. Outcome deltas are log-loss(E4)−log-loss(E3)
(negative = clock improved outcome prediction).

| Quantity | 2024-09 | 2024-10 | Pooled |
|---|---|---|---|
| E3→E4 all-games (outcome) | −0.0138 [−0.0186,−0.0091] | −0.0120 [−0.0177,−0.0062] | — |
| E3→E4 board-decided (outcome) | +0.0010 [−0.0029,+0.0049] (cz) | +0.0060 [+0.0015,+0.0109] (sign-rev) | — |
| E3→E4 time-forfeit (outcome) | −0.1183 [−0.1423,−0.0978] | −0.1305 [−0.1525,−0.1091] | — |
| Descriptive ES loss, eval band (late, over_180) | near_eq 0.0345 / slight 0.0414 / decided 0.0168 | near_eq 0.0322 / slight 0.0396 / decided 0.0148 | — |
| Controlled clock 60_180 vs over_180 | +0.0031 [+0.0003,+0.0057] | +0.0038 [+0.0012,+0.0063] | +0.0034 [+0.0015,+0.0052] |
| Controlled under_60 vs over_180 (exploratory, sparse) | +0.0080 [+0.0020,+0.0137] | +0.0065 [+0.0020,+0.0124] | +0.0072 [+0.0042,+0.0115] |
| Controlled eval-band (vs decided), positive control | — | — | near_eq +0.0223 / slight +0.0286 / clear +0.0158 |

**Robustness headline (15.1F, pooled clock 60_180 vs over_180, all survive):** continuous
within-band cp control +0.0034 · board-decided-only +0.0034 · late-only +0.0033 · rating
quantile-bins +0.0032 / quadratic +0.0033 · clipped_cp +6.09 (dir.) · logistic ES>0.05
+0.088 / ES>0.10 +0.141 (dir.) · game-cluster +0.0034 · White +0.0034 · Black +0.0034.

## 5. Descriptive Atlas result

15.1B (game-cluster CIs, both months): **no replicated clock gradient among stable
descriptive cells** (late fine-clock cells flat ~0.028–0.031); an apparent low-clock bump
did **not** replicate (sparse artifact). The **eval-band pattern replicated strongly**:
ES loss peaks at near_equal/slight, lowest at decided. Reading: eval state is the dominant
descriptive structure; raw marginal clock curves are flat and were not over-read.

## 6. Controlled modeling result

15.1D (OLS adjusted means + mover-player bootstrap, train+val with locked-test
confirmation): the **eval-band positive control** is dominant and replicated; a **small,
non-null, monotone, replicated** clock association appears after controls (60_180 +0.0034
pooled; under_60 +0.0072 but sparse/confounded), confirmed on the held-out test split.
**Termination (time-forfeit vs board-decided) is ≈0 after controls** — consistent with
11.2B (flagging is clock expiry, not systematically worse moves). Logistic large-loss
signs agree with OLS.

## 7. Robustness result

15.1F ran the 15.1E mandatory matrix and applied the pre-locked criteria. The clock
association **SURVIVES**: it is not eliminated by continuous within-band cp control (the
top-ranked coarse-band threat), survives board-decided-only (isolated from flagging), and
is stable across rating specs, late-only, all three metrics (directional), and
game/White/Black clustering. Honest nuance: some *per-month subset* CIs touch zero for this
~+0.003 effect (low power), but pooled estimates exclude zero with consistent positive sign
— exactly what the locked criteria require.

## 8. Player-clustered uncertainty status

11.3B established mover-player clustering as the primary uncertainty unit and showed the
11.2B flagging result and the 15.1B eval-band structure both survive it (strict
player-disjoint splitting is infeasible — giant component). 15.1D/15.1F carry mover-player
clustering as primary; 15.1F adds game / White / Black one-way clustering, all leaving the
clock contrast excluding zero. Exact two-way (White×Black) clustering remains deferred.

## 9. Allowed C4 claims

1. The final-outcome clock signal in the original E3→E4 comparison is **substantially a
   flagging / time-forfeit channel** (11.2B; replicated, survives player clustering).
2. Next-move expected-score loss is **strongly structured by eval state** (15.1B/15.1D;
   replicated; the dominant move-quality structure).
3. After controls, **clock has a small, replicated, robust association** with next-move ES
   loss in the two 10+0 monthly samples (pooled 60_180 vs over_180 ≈ +0.0034).
4. The clock association **survives board-decided-only** move-quality modeling, so at the
   move-quality level it is **not solely a time-forfeit-game artifact**.
5. The clock association is **secondary** to eval-band effects (~5–8× smaller).
6. These findings are **predictive/descriptive** and **replicated across the two sampled
   months** (and on a locked test split for the controlled model).
7. **Player-clustered uncertainty does not remove** the key findings.

## 10. Claims this does not support

- "Time pressure causes worse reasoning."
- "Clock proves cognitive degradation."
- "Low clock causes blunders."
- "Stockfish is ground truth."
- "DRAW modeling is solved."
- "We have the best human chess predictor."
- "Sharpness moderation has been shown" (not implemented).
- "Prior trajectory has been controlled" (deferred; absent from artifacts).
- "The clock effect is large" (it is small, secondary to eval band).
- "The original outcome clock signal is not merely flagging" (that upgrade was **not** met;
  the project reframed to the flagging channel).
- Any unqualified "degradation curve" language for ordered-bucket patterns.

## 11. Prior-trajectory decision

**Decision: Option A — defer prior-trajectory extraction; close C4 as a
predictive/descriptive claim with the trajectory confound as the stated headline
limitation.**

Rationale and prereg reconciliation:
- The original C4 plan locked prior-trajectory control as "mandatory" (PREREGISTRATION
  §C4). That requirement was written **before** the measurement layer existed.
- The deviation was logged **pre-results** at 15.1C (and reaffirmed at 15.1D/15.1F): the
  next-move-loss artifacts carry **no pre-checkpoint trajectory feature**, so trajectory
  could not be included; it was recorded as a future extraction and a stated limitation —
  **not silently dropped**.
- 15.1F already discharged the *immediate* mandatory confounds (eval-band coarseness,
  checkpoint/clock structure, survivor/termination composition, rating spec, metric,
  clustering). Trajectory is the **one remaining** named confound.
- Crucially, "mandatory" was motivated by the **"clock as symptom of past struggle"**
  confound, which threatens a **causal** reading. The consolidated C4 claim is explicitly
  **predictive/descriptive and never causal**, so trajectory is required for a *causal /
  mediation* extension, not for the descriptive claim as stated.

Therefore the "mandatory" lock is **reinterpreted (with a deviation note in
PREREGISTRATION) as mandatory before any causal / mediation C4 claim**, and the
predictive/descriptive C4 claim is closed now with trajectory as an explicit limitation and
a recommended optional follow-up (a 15.1x trajectory-extraction audit/implementation pair).

This is a genuine judgment call on a pre-registered "mandatory" item; if a stronger
(closer-to-causal) C4 statement is wanted, Option B (extract trajectory, then re-run the
controlled + robustness models) should be taken **before** closing C4.

## 12. Relationship to future sharpness work

C3 sharpness moderation (Phase 14 / 15.2A) asks whether sharpness *amplifies* clock's
association with next-move loss. It builds directly on a settled C4 baseline: the
move-quality target, the eval-band-dominant structure, the small robust clock association,
and the mover-player-clustered uncertainty machinery all carry over. Sharpness is a
separate later arc and should begin only after the roadmap is reconciled (§13).

## 13. Roadmap / preregistration implications

- `ROADMAP.md`: mark 15.1G complete; record the consolidated C4 claim and the
  Option-A trajectory decision; point next to a **roadmap reconciliation patch** before the
  sharpness arc.
- `PREREGISTRATION.md`: record the post-robustness C4 interpretation status and the explicit
  deviation note on the trajectory "mandatory" lock (causal vs descriptive distinction).
- `docs/roadmap_rescope_v11_draft.md`: already tagged superseded-in-part (15.1E); the full
  reconciliation is the next ticket's job, not done here.

## 14. Limitations and caveats

- **Prior-trajectory confound unadjusted** (absent from artifacts) — the main alternative
  explanation for the small clock association; deferred, stated, recommended as follow-up.
- Not causal; no "degradation curve" framing; clock effect small and secondary to eval band.
- **White-to-move only** (even-ply checkpoints) — scope, not generality.
- `under_60` sparse and ~2/3 time-forfeit — exploratory; the headline is `60_180`.
- Eval-band dominance may partly reflect chess-value geometry (decided positions have little
  ES to lose) as much as human difficulty.
- ES transform train-fitted/approximate; clipped-cp and large-loss metrics agree in
  direction. Mover-player clustering ≠ exact two-way dependence (deferred).
- Two months of 10+0 only; Stockfish depth-12 eval is objective context, **not absolute
  ground truth**; DRAW remains sparse and not solved; sharpness not implemented or invoked.

## 15. Recommended next ticket

**15.1H — Phase 15 / Roadmap Reconciliation Patch.** The live roadmap has drifted from the
original v11 proposal because the experiments learned new things (11.2B flagging reframe;
15.1D small controlled clock association; 15.1F robustness survival). Reconcile
`ROADMAP.md` and the v11 draft, fold in the consolidated C4 claim, and sequence the
sharpness arc — then proceed to **14.1A — MultiPV Sharpness Feasibility / Compute Audit**.
A **prior-trajectory feature-extraction audit** remains the recommended optional follow-up
if a closer-to-causal C4 statement is later desired.
