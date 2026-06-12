# Ticket 11.1A — Scientific Claim Audit + PREREGISTRATION v1 Refinement

**Labels:** AUDIT/REPORTING | doc-only
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Summary

Audited the 11.0B `PREREGISTRATION.md` stub and refined it into a locked v1.
Documentation only; no code, data, or artifacts touched.

**Stub audit findings (gaps closed by this refinement):**
1. No central-claim section — added "Current supported claim" + "Future v11
   hypothesis" with the standing qualifiers attached.
2. Primary contrasts were named but unstructured — each of the four now carries
   question, comparison, primary metric, required datasets, and success criterion
   (plus kill condition for Contrast 3 and the deferred-parameter pointers to
   14.2A/15.0A).
3. No metric-conventions section — added (log loss primary for outcomes;
   expected-score loss primary for move quality; clipped cp secondary; raw cp only
   eval-band-conditioned; percent swing exploratory/dangerous; draws = 0.5; mate-band
   separate; cp lineage preserved; WDL parallel never silent replacement).
4. Split discipline lacked the train-defined-bins rule, the
   cross-month-as-independent-validation statement, and the no-raw-usernames rule —
   all added.
5. Exploratory list was incomplete — now explicitly covers defensive/mutual
   sharpness, gated forward-line sharpness, pre-Phase-16 cross-TC analyses,
   neural/frozen-model comparisons, sparse 100-Elo bins, percent swing,
   selection-vs-degradation decompositions, and composite-v2 promotions.
6. Revision policy refined per the ticket: logged pre-implementation changes;
   post-implementation primary definitions immutable against observed results;
   feasibility deviations documented beside the preserved original; new contrasts
   need new sections before results are viewed.

## 2. Final current supported claim

> Across two independent Lichess 10+0 monthly samples (2024-09 and 2024-10, 250k raw
> games each), after controlling for fixed-depth Stockfish eval and ratings, clock
> features add a small but replicated predictive signal for game outcomes. Slice
> analysis shows the signal is strongest in late-game low-clock positions. This is
> predictive evidence of residual human/context signal, not causal evidence that time
> pressure degrades reasoning.

Future v11 hypothesis: the residual clock signal is amplified where objective value is
harder for humans to realize (engine-narrow, non-obvious, eventually forward-fragile
positions), with rating and time-control moderation.

## 3. The four locked primary contrasts

| # | Contrast | Phase | Headline statistic | Success criterion (abbreviated) |
|---|---|---|---|---|
| 1 | E4a → E4b → E4c rich clock/history robustness | 12 | Paired val log-loss deltas + bootstrap CIs, both months | Improvement or clarified absorption — either is a finding; E4c becomes the baseline Phase 14 must beat |
| 2 | Board-decided-only E3→E4 vs all-games | 11.2 | Paired delta + CI on board-decided subset | ≥ ~half magnitude retained, ideally CI excludes zero; collapse → honest flagging-channel re-frame |
| 3 | Sharpness moderation (difference of paired clock deltas across train-defined strata; late checkpoints; Tier A engine-side only; advantaged-player conversion orientation headline) | 14 | Difference-of-deltas + bootstrap CI | Expected sign both months; CI excludes zero in primary month or pre-registered pooled analysis; survives 11.2 filter; kill condition restated |
| 4 | Next-move expected-score loss ~ clock bucket at late checkpoints (controlled for rating, eval band, phase, prior trajectory) | 15 | Expected-score loss contrasts; clipped cp secondary | Mechanism-style bridge; non-monotone shapes reportable; no causal/degradation wording |

Deferred parameters are named, not silent: exact sharpness composite and pooled
analysis → 14.2A; loss definition (Option A/B), bins, blunder threshold → 15.0A.
Neither lock-in ticket may alter the intended contrasts.

## 4. Secondary/exploratory boundaries

All non-primary analyses must carry exploratory labels; the refined document lists the
specific families (rating × sharpness beyond C3, defensive/mutual orientations, gated
forward fragility, pre-Phase-16 cross-TC, neural comparisons, sparse bins, percent
swing, selection-vs-degradation, composite v2). Promotions require pre-registration
entries before the promoting analysis runs.

## 5. Unresolved questions

Carried (not blockers for 11.2A): blunder threshold value (Appendix C #4 — to be fixed
in 15.0A); mate-band handling (#9 — 14.1A/15.0A); first increment control (#6 — Phase
16); MultiPV compute ceiling (#7 — 14.1A); selection-vs-degradation promotion (11.0A
new question 15 — candidate for a future pre-registration entry); Maia4All identifier
pinning (RELATED_WORK.md note).

## 6. Files

Created: this report. Modified: `PREREGISTRATION.md` (stub → refined v1);
`ROADMAP.md` (one-line next-ticket pointer update). `EXPERIMENT_LOG.md`: EXP-013
added (style supports doc/audit milestones — EXP-012 precedent).

## 7. Recommended next ticket

**11.2A — Termination Decomposition Feasibility Audit** (inspect whether parsed
data/raw PGNs support the time-forfeit vs. board-decided taxonomy needed by locked
Contrast 2).

## 8. Safety

No code modified; no data touched; nothing staged or committed. Language greps clean
("degradation curve" / "causes worse reasoning" only in forbidden/caution contexts;
no unqualified "neural ceiling").
