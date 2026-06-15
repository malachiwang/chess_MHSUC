# Phase 15.1H — Roadmap Reconciliation Patch

**Labels:** DOCUMENTATION / RECONCILIATION | doc-only, surgical
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

Reconciled the roadmap docs with the post-C4 evidence chain so the project no longer
carries stale v11 promises into the sharpness arc. The patch is **surgical**: it adds a
"Post-C4 Reconciliation" section to `ROADMAP.md` (the live source of truth), updates the
supersession note on the v11 draft, and adds a sharpness pre-arc status note to
`PREREGISTRATION.md`. Completed history is preserved (the chronological completed-ticket
log and the v11 draft are retained for provenance). The next ticket is **14.1A — MultiPV
Sharpness Feasibility / Compute Audit**.

## 2. Why reconciliation was needed

The original v11 ordering (Phase 12 score-scale → 13 difficulty → 14 sharpness → 15
move-quality mediation) was written before the experiments learned that (a) the
board-decided outcome clock residual collapses — the E3→E4 signal is substantially the
flagging channel (11.2B) — and (b) eval state, not clock, dominates next-move quality, with
a small robust secondary clock association after controls (15.1B/D/F/G). Phase 15 was
therefore pulled earlier and executed directly, and C4 is now closed. The live roadmap and
the old v11 draft had drifted apart; this patch closes the gap before sharpness begins.

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | Annotated the stale top sequence bullet; added "Post-C4 Reconciliation (Ticket 15.1H)" section; marked 15.1H complete; next → 14.1A |
| `docs/roadmap_rescope_v11_draft.md` | Supersession note updated (15.1E → 15.1H; C4 consolidated; retained as historical context only) |
| `PREREGISTRATION.md` | Added sharpness pre-arc status (untested; feasibility-first; fresh 14.2A pre-registration required) |
| `EXPERIMENT_LOG.md` | EXP-029 added |
| `reports/phase_reports/phase_15_1h_roadmap_reconciliation_patch.md` | This report |

No source, tests, or data artifacts touched.

## 4. Stale assumptions identified (and how handled)

| Stale assumption | Status | Handling |
|---|---|---|
| Phase 14 sharpness is the immediate headline bet before C4 closure | False — C4 closed first | Reconciliation section reframes sharpness as a later, feasibility-first arc |
| Phase 15 is future move-quality *mediation* | False — already executed and closed (C4) | Marked C4 CLOSED; Phase 15 pulled earlier (11.2B) |
| Original outcome clock signal is "not merely flagging" | Not met | Live claim states it is substantially the flagging channel |
| Board-decided outcome residual survived | False (collapsed/sign-reversed) | Stated in live claim |
| Prior trajectory has been controlled | False — deferred | Stated as explicit limitation + optional follow-up |
| Clock effect is large | False — small, secondary | Live claim says small/secondary (~5–8× < eval band) |
| Sharpness moderation has been shown | False — not implemented | "Sharpness has NOT been shown; feasibility audit first; new pre-registration required" |
| Phase 12/13 block C4 | False — C4 closed | Phase 12/13 reframed as non-blocking backlog |

No causal or "degradation curve" language was introduced; no unqualified "ground truth"
claim. Historical context (standing rules, the v11 phase detail) was preserved, not deleted.

## 5. ROADMAP.md changes

Two edits: (1) the original-sequence bullet now carries a one-line ⚠️ pointer to the
reconciliation section; (2) a new **"Post-C4 Reconciliation (2026-06-14, Ticket 15.1H)"**
section states the live claim, what changed vs the original ordering, the Phase 12/13
status, and the reframed sharpness sequence. The chronological completed-ticket log above
it is unchanged (history preserved).

## 6. v11 draft status

`docs/roadmap_rescope_v11_draft.md` is **retained as historical design context** and is
**superseded in part**. Its top note now records the 15.1E → 15.1H reconciliation, the C4
consolidation, the trajectory deferral, the Phase 12/13 backlog status, and the
sharpness-not-shown / feasibility-first position. The body is unchanged.

## 7. PREREGISTRATION / EXPERIMENT_LOG changes

- `PREREGISTRATION.md`: the existing 15.1G C4-consolidation + trajectory-deviation note is
  unchanged; one bullet added — sharpness is untested, the arc starts with 14.1A, a fresh
  14.2A pre-registration is required before any sharpness modeling, and the C3a/C3b/C3c
  split stands with C3c (move-quality moderation) as the first target. Prior locked
  contrasts were **not** rewritten.
- `EXPERIMENT_LOG.md`: EXP-029 records the reconciliation, the live claim, the trajectory
  deferral, the v11 supersession, and the next-ticket recommendation.

## 8. Updated live roadmap direction

**Post-C4 live claim (predictive/descriptive, not causal):** outcome-level clock signal is
substantially flagging/time-forfeit risk; next-move ES loss is dominated by eval state;
after controls, clock retains a small, replicated, robust, secondary association with
next-move loss; prior trajectory deferred as a limitation.

**Sequence from here:** 14.1A (sharpness feasibility/compute audit) → 14.1B (pilot
extraction) → 14.2A (sharpness interaction pre-registration) → 14.2B (implement tests) →
14.3B (slice report). Phase 12/13 are non-blocking backlog; the prior-trajectory extraction
is the optional follow-up most tied to the open C4 caveat.

## 9. Prior-trajectory decision status

Deferred (Option A, decided in 15.1G). It is a stated limitation and the main recommended
optional follow-up; it is required only **before any causal / mediation clock claim**
(PREREGISTRATION deviation note). This ticket does not change that decision — it only
records it consistently across the roadmap docs.

## 10. Sharpness arc handoff

Sharpness is **open and unproven**. The handoff for 14.1A: sharpness is no longer framed as
rescuing the (collapsed) board-decided outcome residual; it tests whether constraint effects
are **moderated by objective narrowness / non-obviousness**, with **move-quality moderation
(C3c)** as the first target, building on the settled C4 baseline (move-quality target,
eval-state-dominant structure, small robust clock association, mover-player-clustered
uncertainty). Outcome-level sharpness interactions must keep the flagging-risk channel
distinct from board-decided results (C3a vs C3b). No sharpness claim until MultiPV features
exist and pre-registered tests run.

## 11. Limitations and caveats

- This is a documentation patch; it makes no new empirical claim.
- The C4 claim boundaries are unchanged (descriptive/predictive, not causal; clock small and
  secondary; prior trajectory deferred).
- The v11 draft remains a long historical document; only its top note was updated — readers
  should treat `ROADMAP.md` as authoritative.
- Stockfish eval is objective context, not absolute ground truth; DRAW remains sparse;
  sharpness is not implemented or invoked.

## 12. Recommended next ticket

**14.1A — MultiPV Sharpness Feasibility / Compute Audit.** Begin the sharpness arc with a
feasibility/compute audit (not implementation), framed per §10. A **prior-trajectory
feature-extraction audit/implementation** remains the recommended optional follow-up if a
closer-to-causal C4 statement is later desired.
