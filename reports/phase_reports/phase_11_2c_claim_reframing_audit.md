# Phase 11.2C — Claim Reframing Audit After Termination Decomposition

**Labels:** AUDIT/REPORTING | doc-only
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Executive summary

Ticket 11.2B triggered the pre-registered collapse/reframe branch of Contrast C2: the
all-games E3→E4 clock residual replicated, but the **board-decided-only residual
collapsed (2024-09: +0.0010, CI contains zero) or sign-reversed (2024-10: +0.0060, CI
excludes zero on the positive side)**, while time-forfeit games carry an order-of-
magnitude-larger delta (−0.118 / −0.131). The replicated clock residual is real and
predictive, but in the current outcome-prediction setup it **predominantly quantifies
the time-forfeit / flagging channel, not board-decided outcome signal.** This audit
reframes the central claim honestly, splits Contrast C3 (sharpness moderation) into
flagging-risk / board-decided-outcome / move-quality variants so future sharpness work
does not assume a surviving board-outcome residual, strengthens Contrast C4 (next-move
quality) as the now-central board-play test, and recommends moving the **15.0A
move-quality / Constraint Atlas audit earlier** as the next ticket — with player-leakage
hardening (11.3A/B) reordered to follow it but still required before any C4 primary
modeling result is locked. No code, data, or models were touched.

## 2. What 11.2B changed

The pre-registered C2 contrast (PREREGISTRATION.md) filtered the frozen all-games E3/E4
validation predictions by termination channel (no retraining) and recomputed paired
game-level bootstrap deltas. Results, both months:

| Group | 2024-09 | 2024-10 |
|---|---|---|
| All games | −0.0138 [−0.0186, −0.0091] excl. zero | −0.0120 [−0.0177, −0.0062] excl. zero |
| Board-decided | +0.0010 [−0.0029, +0.0049] contains zero | +0.0060 [+0.0015, +0.0109] excl. zero (positive) |
| Time-forfeit | −0.1183 [−0.1423, −0.0978] | −0.1305 [−0.1525, −0.1091] |
| Retained fraction | 0.07 | 0.50 — sign-reversed; magnitude overstates retention |

Late-checkpoint board-decided localization did **not** replicate (60_180s: −0.0294
excl. zero in 2024-09 but −0.0061 contains zero in 2024-10; under_60s flips to ~+0.17
descriptive in both months). The collapse is not a power artifact: board-decided groups
hold ~3,100–3,300 games each.

## 3. Previous central claim

> Across two independent Lichess 10+0 monthly samples, after controlling for
> fixed-depth Stockfish eval and ratings, clock features add a small but replicated
> predictive signal for game outcomes, localized most strongly to late-game low-clock
> positions.

The unstated working interpretation that the v11 arc was being built on: this residual
reflects, at least in part, *board-play / cognitive* signal — that clock pressure is
associated with worse play that shows up in the game result after controlling for
position value and skill. 11.2B does not support that interpretation.

## 4. Revised central claim

> Across two independent Lichess 10+0 monthly samples, after controlling for
> fixed-depth Stockfish eval and ratings, clock features add a small but replicated
> predictive signal for game outcomes. A pre-registered termination decomposition
> (11.2B) shows this residual is **substantially attributable to the time-forfeit /
> flagging channel**: among board-decided games the residual is approximately zero
> (2024-09) or slightly reversed (2024-10). The project has therefore measured and
> replicated a real human-constraint outcome channel that, in the current outcome
> setup, is **primarily a flagging-risk channel rather than a board-decided outcome
> signal.** Whether low clock relates to board-*play* quality remains open and must be
> tested directly (next-move quality, Contrast C4), not inferred from final-outcome
> residuals.

All standing qualifiers carry unchanged: predictive not causal; no claim that time
pressure causes worse reasoning; Stockfish eval is objective context, not ground truth;
DRAW sparse and not solved; no "degradation curve" language; filtering time-forfeit
games induces selection (board-decided low-clock games are a survivor population) and
does not create a causal design.

## 5. What remains supported

- The **all-games E3→E4 clock residual is real, replicated, and predictive** (the
  EXP-009/EXP-011 anchors are unchanged).
- The residual is **strongest in low-clock settings because clock state is highly
  informative about time-forfeit / flagging risk** — the time-forfeit-only delta is
  ~10× the all-games delta in both months.
- The project **has measured a real human-constraint outcome channel**, replicated
  across two independent months — but in the current outcome setup it is **primarily a
  termination / flagging channel.**
- The full measurement-and-replication infrastructure (eval control, paired game-level
  bootstrap, cross-month replication, slice machinery, termination decomposition) is
  validated and reusable.

## 6. What is weakened or no longer supported

- The current E3→E4 outcome residual should **no longer be interpreted as evidence that
  clock pressure predicts worse board-decided outcomes** after eval and rating control.
- The original "clock residual as board-play / cognitive signal" interpretation **is
  not supported by 11.2B.**
- Any **sharpness moderation of final game outcomes must now distinguish
  flagging-risk moderation from board-decided-outcome moderation** — the two are
  different targets, and 11.2B shows the board-decided outcome channel is weak overall.
- The late-game low-clock *localization* of a board-decided residual is **not
  established** (failed to replicate after filtering).

## 7. Implications for C1, C2, C3, and C4

- **C1 (rich clock/history robustness, Phase 12):** still valid but its *interpretation*
  shifts. E4b/E4c improving residual prediction now most plausibly means better
  flagging-risk modeling (distinguishing chronic time trouble from acute low-clock
  states), not better board-play prediction. C1's success criterion is unchanged;
  its framing must name the flagging channel explicitly.
- **C2 (board-decided clock residual, Phase 11.2):** **COMPLETED.** Result: collapse /
  sign-reversal, replicated. The pre-registered collapse branch is invoked. C2 is
  marked done in PREREGISTRATION.md.
- **C3 (sharpness moderation, Phase 14):** must be **split** so it no longer assumes a
  surviving board-decided outcome residual to moderate (see §9 and PREREGISTRATION.md).
- **C4 (next-move quality, Phase 15):** **strengthened and elevated.** C4 measures
  next-move expected-score loss directly and **does not depend on the outcome residual
  surviving board-decided filtering.** It is now the central test of whether low clock
  (and sharpness) relate to board-play quality (see §10).

## 8. Revised role of flagging / timeout risk

Flagging / timeout risk moves from a *nuisance channel to be controlled away* to a
**legitimate, replicated object of study in its own right.** The project has cleanly
quantified it (time-forfeit delta −0.12/−0.13, replicated). Two honest framings are now
available and both are defensible: (a) the project quantifies how engine-eval-controlled
clock state predicts flagging-driven outcomes; (b) the project pivots toward board-play
quality via C4. These are complementary, not exclusive. What is **not** allowed is
continuing to present the all-games outcome residual as board-play evidence.

## 9. Revised role of sharpness

Sharpness (Phase 14) is reframed from "moderator of a board-decided outcome clock
residual" (the assumption 11.2B undermined) into three distinct, separately-framed
questions:

- **C3a — Flagging-risk sharpness moderation:** does sharpness / position type interact
  with clock in predicting *time-forfeit risk*? This is a constraint/termination
  target, not board-play quality, and is well-motivated by 11.2B (the signal lives in
  the flagging channel).
- **C3b — Board-decided outcome sharpness moderation:** optional / secondary. Only
  pursued if specific strata show a board-decided residual; framed cautiously because
  the overall board-decided residual collapsed. Not a headline.
- **C3c — Move-quality sharpness moderation:** likely the **most scientifically
  relevant** sharpness test after 11.2B — connects sharpness to next-move expected-score
  loss (Tier A engine-side sharpness, per Appendix B/B.1) rather than final outcome.
  This is the natural sharpness extension of C4.

Sharpness may still matter for human-realizable value, but the **target shifts from
final-outcome deltas toward move-quality loss and/or termination-channel risk.** The
Tier A / Tier B anti-circularity discipline is unchanged.

## 10. Revised role of move-quality analysis

Move-quality analysis (C4 / Phase 15) becomes the **key bridge** for the project's
central remaining question. Rationale:

- It **directly measures board-play quality** (next-move expected-score loss), the exact
  object 11.2B showed cannot be read off the outcome residual.
- It **does not depend on the outcome residual surviving** board-decided filtering — it
  is structurally immune to the C2 collapse.
- It connects to the genuinely-novel-relative-to-prior-work lane: while move-level
  difficulty/error prediction is prior work (Anderson et al.; Barthelemy), the
  controlled, replicated, eval-conditioned *bridge* from a replicated outcome channel to
  move-level behavior — and the clock × sharpness move-quality interaction — remains
  the project's distinctive contribution.

This elevates Phase 15's 15.0A audit in the ordering (see §15).

## 11. Roadmap impact

- The v11 detailed roadmap (`docs/roadmap_rescope_v11_draft.md`) is edited surgically to
  record the C2 collapse as a known result and to stop implying a board-decided outcome
  residual is expected to survive. Phase 14 framing now names the C3a/C3b/C3c split;
  sharpness is no longer assumed to moderate a board-outcome residual as the sole
  headline.
- Phase ordering is **reordered, not rewritten:** 15.0A (move-quality audit) is
  recommended next; 11.3A/11.3B (player-leakage) follow it but remain required before
  any C4 *primary modeling result* (15.1B) is locked. No phases are deleted; the
  flagging channel becomes a first-class study object alongside move quality.

## 12. Preregistration impact

`PREREGISTRATION.md` is updated: a "Post-11.2B claim status" section; C2 marked
completed with result + interpretation + consequences; C3 split into C3a/C3b/C3c; C4
strengthened with the explicit "does not depend on the outcome residual" language; a
revision-log entry making clear this is a pre-next-analysis reframing executed under the
pre-registered collapse branch, **not result-shopping** (C2's collapse branch was
written before C2 ran; this audit follows it).

## 13. Documentation edits applied

- `PREREGISTRATION.md`: Post-11.2B claim status; C2 → completed; C3 → C3a/C3b/C3c; C4
  strengthened; revision-log entry; current-supported-claim wording updated to the
  flagging-channel framing.
- `ROADMAP.md`: active-arc section updated to record 11.2C reframing and the reordered
  next ticket (15.0A), with player-leakage hardening reordered after it.
- `docs/roadmap_rescope_v11_draft.md`: post-11.2B note in Section 0; C2 success-criterion
  resolution noted (collapse branch met); Phase 14 / C3 wording adjusted to the
  three-target split.
- `docs/RELATED_WORK.md`: a short note that move-quality prior work (Anderson et al.;
  resource-rational; Barthelemy) is now *more central* to the project's framing because
  the board-play question moves to C4.
- `EXPERIMENT_LOG.md`: EXP-016.

## 14. Open questions

1. **Headline identity:** does the project want flagging-risk prediction to become an
   explicit headline (C3a), or to keep flagging as a quantified channel while the
   board-play headline moves to C4/C3c? (My read: keep both; let C4 results decide the
   emphasis.) Defer to Malachi.
2. **C2 secondary:** is a board-decided-only *refit* (the optional secondary estimand)
   worth running, or is the prediction-side collapse sufficient to settle C2? (Read:
   sufficient; refit only if a stratum-specific board-decided residual appears later.)
3. **Sharpness compute commitment:** Phase 14's MultiPV cost is now justified mainly by
   C3a (flagging) and C3c (move-quality), not C3b (board outcome). Confirm the sharpness
   arc is still worth its compute under the reframed targets before 14.1A.
4. **Player-leakage and the flagging finding:** could heavy-flagging players spanning
   train/val inflate the flagging-channel estimate? Magnitude (−0.12) makes a pure
   artifact unlikely, but 11.3A should quantify it. Noted for 11.3A scope.

## 15. Recommended next ticket

**Recommend: 15.0A — Move-Quality Curve / Constraint Atlas Audit, moved earlier**
(Option C), with 11.3A/11.3B reordered to follow it.

Reasoning:
- 11.2B exposed a specific interpretive gap — *does low clock relate to board-play
  quality, not just flagging?* — and **only the move-quality target answers it.** 15.0A
  is the audit that scopes that test.
- 15.0A is a **feasibility / compute audit**, not a results-producing ticket: it does
  not retrain, does not lock a primary contrast, and (critically) is **not invalidated
  by later player-leakage hardening** — an audit of next-move-evaluation feasibility and
  compute cost is robust to whatever split discipline 11.3A later adopts. This dissolves
  the Option D concern ("don't build C4 on player-leaky data"): the *audit* is safe now;
  the *primary modeling result* (15.1B) is where 11.3A/B must already be applied.
- **11.3A/11.3B are not dropped.** They remain required before any C4 primary modeling
  result is interpreted, and they additionally gain a new purpose (quantifying whether
  player leakage inflates the flagging-channel estimate, §14.4). Reordering them after
  15.0A costs nothing and addresses the core interpretive gap sooner.
- 12.1A (clock dynamics) and a pure flagging-risk arc remain valuable but are still
  outcome/termination-focused; they do not answer the board-play question and can follow.

Rejected: Option A/D (11.3A first) — defers the central interpretive gap for a hardening
step whose primary subject (the board-decided outcome residual) has already largely
collapsed; Option B (12.1A) — improves flagging-risk modeling but does not test
board-play quality. Both remain in the roadmap, just not next.
