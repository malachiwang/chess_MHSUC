# PREREGISTRATION.md — v1 Stub

## Status

v1 STUB, created by Ticket 11.0B (2026-06-12). This is not a final preregistration.
Ticket 11.1A (Scientific Claim Audit + PREREGISTRATION v1 refinement) will refine the
primary contrasts below into fully specified, locked statements (exact estimands,
datasets, splits, thresholds) before any Phase 12+ feature exists. Until then, this
stub freezes the historical anchors and names the primary contrasts at the level of
detail currently available.

## Purpose

Pre-register the primary contrasts of the v11 research arc (Phases 12–15) before the
features and analyses that would test them are implemented, so that headline results
cannot be the product of post-hoc selection. Anything not listed as a primary contrast
is exploratory and must be labeled as such in every report.

## Frozen historical comparisons

These are frozen lineage anchors. They are never silently altered, re-run with changed
definitions, or substituted. (Delta convention throughout: `log_loss(E4) − log_loss(E3)`;
negative = adding clock improved.)

- **E3** = Stockfish eval (cp-based, fixed depth 12) + rating. Frozen.
- **E4** (alias **E4a**) = E3 + original clock features. Frozen.
- Recorded anchors (validation split, paired game-level bootstrap, 1,000 replicates,
  seed=42):
  - 2024-09 250k: E3→E4 = −0.0138, 95% CI [−0.0186, −0.0091].
  - 2024-10 250k: E3→E4 = −0.0120, 95% CI [−0.0177, −0.0062].
  - Late-checkpoint low-clock localization (both months; under-60s cells descriptive,
    below the 300-game CI threshold).
- If the Phase 12 score-scale migration (E3w/E4w) changes results materially, the
  divergence is reported as a finding; cp-based anchors remain in every comparison
  table.

## Primary future contrasts

1. **E4a → E4b (and → E4c) delta** — do richer clock-dynamics/history features absorb
   residual clock signal? Both months; paired game-level bootstrap; same delta
   convention. (Phase 12.)
2. **Board-decided-only E3→E4 delta vs. all-games delta** — does the clock residual
   survive removal of the time-forfeit channel? Guideline from the v11 roadmap:
   retaining ≥ ~half the magnitude with CI excluding zero upgrades the claim to "not
   merely flagging"; an overwhelmingly-timeout result re-frames the project honestly.
   (Phase 11.2; depends on the 11.2A feasibility verdict.)
3. **Difference of paired clock deltas across sharpness strata** — train-defined
   sharpness terciles or the binary composite (`narrow AND non-obvious`, per Appendix
   B.1 of the v11 roadmap), late checkpoints (move_30+move_40), engine-side (Tier A)
   sharpness only, both months. Headline orientation: advantaged-player conversion
   sharpness; side-to-move-overall as labeled secondary. Exact definition locked in
   14.2A before modeling. (Phase 14.)
4. **Next-move expected-score loss ~ clock-bucket contrast at late checkpoints** —
   the move-level bridge; expected-score loss primary metric, clipped centipawn loss
   secondary. Exact loss definition (eval-swing vs. vs-engine-best) chosen in 15.0A
   per Appendix A of the v11 roadmap. (Phase 15.)

## Secondary / exploratory analyses

Everything else is exploratory and must be labeled exploratory in all reports,
including (non-exhaustively): all other slice analyses; rating-band and
clock-imbalance breakdowns beyond the pre-registered contrasts; per-checkpoint
decompositions of new deltas; sharpness orientation variants beyond the headline and
labeled secondary; curve shapes in the Constraint Atlas; any composite-v2 sharpness
definition (requires its own pre-registration before promotion); selection-vs-
degradation decompositions unless promoted by 11.1A.

## Split and evaluation discipline

- Validation split is the working evaluation surface for all model selection and all
  primary contrasts. **The test split is not used for model selection** (WORKFLOW.md
  §13); it opens at most once per major version for locked final evaluation.
- Splits are game-level (seed=42); player-clustered uncertainty and player-disjoint
  splits enter via Phase 11.3 and, once adopted, apply to subsequent primary contrasts.
- Uncertainty: paired game-level clustered bootstrap, 1,000 replicates, seed=42, unless
  a pre-registered revision changes this for a stated reason.
- Slice definitions for pre-registered contrasts are fixed before results are computed
  and never tuned after seeing them.

## Anti-overclaiming language

- All findings are predictive associations. **Causal language is prohibited unless a
  causal design is actually introduced** (none is currently planned).
- "Degradation curve" language is avoided unless a design explicitly licenses it;
  ordered-bucket patterns are reported as patterns.
- Stockfish evaluation is objective position context, not ground truth. Reasoning
  quality is not directly measured. DRAW remains sparse and is not solved.
- Novelty claims follow `docs/RELATED_WORK.md` (forbidden list included there);
  ChessMimic is described only as "a strong neural reference point, not a direct
  ceiling."

## Revision policy

This document may be revised only by an explicit ticket (next: 11.1A), with changes
recorded in the ticket's report and visible in git history. Revisions may refine,
add, or withdraw contrasts **before** the data/features that would test them exist;
once a contrast's inputs exist, its definition is locked and any change must be
reported as a deviation, not silently edited. Exploratory→primary promotions require
their own pre-registration entry before the promoting analysis is run.
