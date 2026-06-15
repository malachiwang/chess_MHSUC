# Phase 14.2D — C3c Underpowered Result Consolidation

**Labels:** CONSOLIDATION / DOC-ONLY | no modeling
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Freezes the final, stable interpretation of the C3c sharpness × clock move-quality
moderation result so future tickets do not overclaim, reclassify, or keep reopening it.
**No model was run; no thresholds, model, contrast, or the 14.2B classification were
changed.** Final status:

> **C3c status: unresolved. Directional train+val signal, underpowered/no-claim under the
> locked criteria, no threshold changes.**

The next clean step is a *separate* question — whether sharpness is relevant to the
outcome/flagging channels (C3a/C3b) — not a rerun of the same underpowered model. Revisiting
C3c itself is possible only via enriched data under the *same locked design* (with a new
pre-registration if power is to be judged pooled rather than per-month) or a separately
pre-registered design; threshold relaxation after seeing results is forbidden.

## 2. Files inspected

PREREGISTRATION.md (§C3c + 14.2B/14.2C notes), ROADMAP.md, EXPERIMENT_LOG.md; the C3c reports
(`sharpness_interaction_combined.md`, `phase_14_2b…`, `phase_14_2c…`); the arc context
(`c4_move_quality_arc_summary`, `multipv_sharpness_combined`, `controlled_move_quality_combined`,
`clock_association_robustness_combined`).

## 3. Files modified

- `ROADMAP.md` — 14.2D complete; next pointer → 14.3A (with enrichment + synthesis options preserved).
- `EXPERIMENT_LOG.md` — EXP-036.
- `PREREGISTRATION.md` — final §C3c consolidation note (locked design unchanged).
- This phase report (created).

## 4. Final C3c status

**Unresolved / underpowered / no-claim.** The locked sharpness×`60_180` interaction was
positive in train+val (pooled +0.0102 [+0.0013, +0.0194]; 2024-09 +0.0074 [−0.0079, +0.0217];
2024-10 +0.0131 [+0.0001, +0.0274]), but it did **not** satisfy the pre-registered
confirmation criteria: the per-month sharp×`60_180` cells (297 / 282) fell below the locked
≥300/month adequacy threshold, 2024-09 was not individually resolved (CI contains zero), and
the held-out test confirmation was weak with an October sign flip (pooled test +0.0012;
2024-09 +0.0054; 2024-10 −0.0035). This is **not** evidence that C3c is false, and **not**
strong enough to claim sharpness moderation.

## 5. Stable project wording

**Long form (reuse verbatim):**

> C3c is directional but underpowered/no-claim. The locked sharpness × 60_180 interaction was
> positive in train+val, including the pooled estimate, but did not satisfy the pre-registered
> confirmation criteria because the per-month sharp × 60_180 cells fell below the adequacy
> threshold, 2024-09 was not individually resolved, and the held-out test confirmation was
> weak with an October sign flip. This is not evidence that C3c is false, but it is also not
> evidence strong enough to claim sharpness moderation.

**Short form:**

> C3c status: unresolved. Directional train+val signal, underpowered/no-claim under locked
> criteria, no threshold changes.

## 6. Why the result remains no-claim

Three independent reasons, none of which is a "null":

1. **Per-month cell adequacy failed.** sharp×`60_180` train+val = 297 / 282 < the locked
   ≥300/month gate; the pooled 579 is adequate but the pre-registration bound on per-month
   power.
2. **Month-specific CIs not jointly resolved.** 2024-09's CI contains zero; 2024-10 only
   barely excludes it — not "positive and resolved in both months."
3. **Test confirmation weak / unstable.** The reserved test split did not confirm; 2024-10
   flipped sign — a fragility beyond cell count.

Robustness checks cannot upgrade this (locked discipline): any positive robustness/exploratory
cell is secondary only.

## 7. Future revisit conditions

C3c may be revisited **only** via:

- **Path A — same locked model on enriched ordinary-month data.** Add ≥1 ordinary 10+0 month
  through the established pipeline (parse → checkpoint eval → next-move loss → MultiPV sharpness
  → player-metadata join → rerun the *locked* C3c model). Improves **pooled** precision, but
  ordinary months keep the per-month sharp×`60_180` cell ≈290, so the per-month gate is not
  fixed; **judging by pooled power instead requires a new pre-registration note before rerun.**
- **Path B — new pooled-power enrichment design.** Pre-register pooled (not per-month)
  sharp×`60_180` adequacy as the primary gate; keep the original threshold/model/contrast fixed;
  label the outcome as a **new enrichment analysis**, not retroactive proof of the 14.2B claim.
- **Path C — sharp-position oversampling design.** Pre-register a sampling design that enriches
  sharp × low-clock rows (with weighting / a redesigned estimand). Not directly comparable to
  the full-population two-month analysis; treat as a **new design**, not a continuation.

## 8. Forbidden revisit paths

- Relaxing the `sharp_value_fragility_v1` threshold after seeing the result.
- Switching the primary clock contrast away from `60_180` after seeing the result.
- Headlining surface-bait instead of the locked sharpness feature.
- Using exploratory robustness as the main claim.
- Re-running until a month happens to pass.
- Reclassifying as supported using pooled train+val alone (ignoring the per-month gate and the
  test split).

## 9. Roadmap reconciliation

14.2D marked complete. Next pointer → **14.3A — Outcome/Flagging Sharpness Audit** (a separate,
to-be-pre-registered question: does sharpness moderate the time-forfeit / outcome channels?
— C3a/C3b). Preserved alternatives: **14.2E — Third-Month / Pooled-Power Enrichment Audit**
(only if the project chooses to revisit C3c, per Paths A/B), and **16.0A — Final Synthesis /
Public-Facing Claim Audit** (if the project chooses to stop modeling). No
modeling-implementation pointer is set.

## 10. PREREGISTRATION status

§C3c retains its locked design and the 14.2B/14.2C notes; 14.2D adds only a final consolidation
note (status frozen: directional/underpowered/no-claim; not confirmed; not disproven; no
threshold change; future revisit only under the same locked design on enriched data or a new
pre-registered design). **The locked model, contrast, threshold, and criteria are not rewritten.**

## 11. Explicit non-claims

- C3c is **not confirmed**; C3c is **not disproven**; it is **not a null result** — it is
  underpowered/no-claim.
- **No claim that sharpness moderation is shown.**
- The positive pooled train+val estimate is **directional only**.
- No causality; no "time pressure causes worse reasoning".
- **No human-obviousness claim** (the v1 feature is an engine-side value-fragility proxy).
- Surface-bait diagnostics are **not** headline evidence.
- **No threshold relaxation after seeing results**; no reclassification using pooled train+val
  alone.
- No "degradation curve"; Stockfish eval is objective context, not ground truth; DRAW remains
  sparse and not solved; not a best-predictor claim.

## 12. Recommended next ticket

**14.3A — Outcome/Flagging Sharpness Audit** (separate audit + pre-registration for C3a/C3b;
does not reuse the underpowered C3c model). Fallbacks the user may select instead:
**14.2E — Third-Month / Pooled-Power Enrichment Audit** (revisit C3c under Paths A/B) or
**16.0A — Final Synthesis / Public-Facing Claim Audit** (stop modeling, consolidate the whole
arc). Prior-trajectory extraction remains an optional follow-up for any future controlled work.
