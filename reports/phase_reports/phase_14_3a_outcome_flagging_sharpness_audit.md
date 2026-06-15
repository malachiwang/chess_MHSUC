# Phase 14.3A — Outcome / Flagging Sharpness Audit

**Labels:** AUDIT / DESIGN | doc-only, no modeling
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Audits whether testing sharpness moderation in the **outcome (C3a)** and
**flagging/time-forfeit (C3b)** channels is scientifically worthwhile, separate from the
closed C3c move-quality question. **No model was run.** Findings: C3a is **either confounded
or null-by-construction** (all-games C3a largely rediscovers the flagging channel per 11.2B;
board-decided-only C3a would moderate a clock-outcome residual that **already collapsed** in
11.2B — so there is little to moderate); C3b (flagging) is **coherent and its target is
available**, but (i) the clock→time-forfeit gradient is strongly **mechanical** (over_180 ~12%
→ 60_180 ~35% → under_60 ~64–69%), so the *main effect* is not the question; (ii) the
*interaction* (sharp moderating clock→flagging) hinges on the **same scarce sharp×low-clock
cells** that made C3c underpowered (sharp×`60_180` ≈348/329; sharp×`under_60` ≈82/97); and
(iii) `is_time_forfeit` is **game-level** (it does not identify *who* flagged), so a clean
player-to-move target needs an extra `result_class` join + orientation. Even a positive C3b
would be a **time-management / selection-into-complexity** channel result, explicitly **not**
move-quality degradation. **Recommendation: Option C — stop sharpness modeling and move to
final synthesis (16.0A)**, with a narrowly-scoped **flagging-only C3b pre-registration (14.3B)**
named as the fallback if the project specifically wants the channel result. C3a is **not**
recommended. No thresholds changed; C3c stays unresolved/no-claim.

## 2. Files inspected

PREREGISTRATION.md (C3 split + §C3c notes), ROADMAP.md, EXPERIMENT_LOG.md; reports
(`c4_move_quality_arc_summary`, `termination_decomposition_combined`,
`controlled_move_quality_combined`, `clock_association_robustness_combined`,
`multipv_sharpness_combined`, `sharpness_interaction_combined`, `phase_14_2d…`); code
(`termination_decomposition.py`, `sharpness_interaction.py`, `multipv_sharpness.py`,
`controlled_move_quality.py`, `clustered_uncertainty.py`, `player_metadata.py`). Read-only
schema + cell-count check of the joined sharpness frame.

## 3. Files modified

- `ROADMAP.md` — 14.3A complete; next pointer → 16.0A (flagging-only 14.3B preserved as fallback).
- `EXPERIMENT_LOG.md` — EXP-037.
- `PREREGISTRATION.md` — short audit/status note (C3a/C3b separate from C3c; require their own
  pre-registration; not modeled). No model lock.
- This phase report (created).

## 4. Why this is separate from C3c

C3c = sharpness × clock moderation of **next-move expected-score loss** (move quality). C3a/C3b
target **final outcome** and **flagging risk** — different dependent variables. **C3a/C3b are
not next-move quality; they do not rescue C3c; they do not show human obviousness; they do not
show causal time-pressure degradation.** C3c stays **unresolved / underpowered / no-claim**
regardless of any C3a/C3b result.

## 5. C3a definition

**C3a = sharpness moderation of outcome-level clock residuals** — does objective
value-fragility change how much clock state contributes to final-game-outcome prediction,
beyond eval and rating? Outcome prediction, not move quality.

## 6. C3b definition

**C3b = sharpness moderation of timeout/flagging-channel risk** — in low-clock states, are
objectively sharp/value-fragile positions associated with higher subsequent time-forfeit risk?
Flagging/channel analysis, not move quality.

## 7. Feasibility audit

| Question | Finding |
|---|---|
| Sharpness joinable to outcome/termination rows? | Yes — `(game_id, selected_position_type)`, unique keys, 100% coverage (as in 14.2B). |
| `is_time_forfeit` present/reliable? | Present in `next_move_loss` (game-level, from the 11.2B-clean termination taxonomy). |
| Termination labels clean? | Yes (11.2B: clean set = Normal / Time forfeit / Rules-1). |
| Outcome target (`result_class`) present? | **Not** in `next_move_loss`; present in `feature_positions_broad_*` and `eval_conditioned_predictions_*` (joinable by the same keys). |
| Player/cluster IDs available? | Yes — mover/White/Black hashes via `player_metadata`. |
| New artifacts needed? | **No** — existing artifacts + joins suffice for both C3a and C3b. |
| Split discipline | Same as C4 arc: train+val estimate, test reserved; mover-player-clustered bootstrap. |

**Orientation limitation (important):** `is_time_forfeit` is **game-level** — it marks that the
game ended on time, not that the *player to move at the checkpoint* flagged. A clean
player-to-move flagging target = `is_time_forfeit AND mover lost`, which needs `result_class`
(feature-table join) and the even-ply mover-is-White convention. Constructable, but it is a
**derived, orientation-sensitive** target, not a primitive.

## 8. Orientation audit

- **C3b (flagging): player-to-move perspective** is the natural choice (the observed clock is
  the mover's). Because the mover is always White at numbered checkpoints, a player-to-move
  flagging target reduces to "White flags" = `is_time_forfeit AND result=BLACK_WIN`. A
  game-level `game_ends_by_time_forfeit` target is the simpler fallback but does not attribute
  the flag.
- **C3a (outcome): player-to-move expected score / result** (White-perspective here), with the
  caveat that all-games outcome is dominated by the flagging channel. Advantaged-player
  orientation is deferred (mixes orientation with eval sign).

## 9. Candidate targets

- **C3b primary:** `is_time_forfeit` (game-level) or, better, player-to-move flagging
  (`is_time_forfeit AND White lost`) via a `result_class` join. Binary → logistic.
- **C3a primary:** board-decided-only outcome (exclude time-forfeit), e.g. White expected score
  / result; secondary all-games (confounded). Or an E3/E4-style model-delta with/without
  clock×sharpness (no test-set selection).
- **Sharpness feature (unchanged, not tuned):** `sharp_value_fragility_v1`; relaxed/strict and
  continuous as secondary; **surface-bait exploratory only, not a headline, not obviousness.**

## 10. Candidate model families

- **C3b:** `is_time_forfeit ~ C(clock_bucket) + sharp + clock_bucket:sharp + eval band +
  rating_z + checkpoint + month`, logistic, mover-player-clustered bootstrap; primary estimand
  = `clock=60_180 × sharp` (does low-clock flagging risk rise more in sharp positions?). Caveat
  stated: predictive/channel, **not** move-quality degradation; confounded by time management,
  phase, and selection into complicated positions.
- **C3a:** same controls with a final-outcome target; **board-decided-only as primary** (to
  avoid rediscovering flagging); all-games as a labeled, confounded secondary.

## 11. Relationship to termination decomposition (11.2B)

11.2B showed the all-games E3→E4 clock-outcome improvement was **substantially the
time-forfeit/flagging channel**, and the **board-decided outcome residual collapsed/sign-
reversed**. Consequences for this audit: (a) C3b is **scientifically coherent** — it asks
*where* the (already-established) flagging channel is strongest, and sharpness is a plausible
moderator of time pressure; (b) **all-games C3a collapses toward C3b** (same flagging driver);
(c) **board-decided-only C3a is largely null-by-construction** — there is little board-decided
clock-outcome residual left to moderate. So C3a adds little; C3b is the only coherent
outcome-side extension, and even it is a channel/time-management question.

## 12. Power / cell-count considerations

Read-only counts (joined non-mate frame):

| | 2024-09 | 2024-10 |
|---|---|---|
| non-mate rows | 61,956 | 59,625 |
| time-forfeit prevalence | 13.4% | 13.5% |
| TF rate, over_180 / 60_180 / under_60 | 11.7% / 35.5% / 69.0% | 11.8% / 34.6% / 63.8% |
| sharp×`60_180` (TF / board) | 108 / 240 | 114 / 215 |
| sharp×`under_60` (TF / board) | 67 / 15 | 67 / 30 |

The clock→TF gradient is strong (mechanical), so C3b's **main effect** is well-powered — but
that is **not the question**. The C3b *interaction* (sharp moderating clock→flagging) depends on
the **same scarce sharp×low-clock cells** as C3c: sharp×`60_180` ≈348/329, sharp×`under_60`
≈82/97 — i.e. **C3b's interaction power is no better than C3c's** and would likely hit the same
underpowered wall, though the binary high-prevalence TF target gives more events than the
continuous ES-loss target in those cells (a modest power edge, not a fix). Board-decided-only
C3a is both cell-limited **and** null-by-construction.

## 13. Risks and confounds

- **Mechanical clock→flagging confound:** low clock *mechanically* raises TF; any C3b signal
  must be read as moderation of that channel, never as move-quality.
- **C3a collapse:** all-games C3a re-derives the flagging channel; board-decided C3a moderates a
  near-zero residual.
- **Same cell bottleneck as C3c:** the sharp×low-clock cells are the binding constraint again.
- **Orientation:** `is_time_forfeit` is game-level; attributing the flag needs a result join.
- **Selection:** sharp low-clock positions may be selected (players who navigated complexity);
  not causal.
- **Over-reading risk:** a C3b "sharp positions flag more" result is easily mis-told as "time
  pressure causes worse play" — it is not.

## 14. Options considered

- **A — C3b-only flagging pre-registration (14.3B).** Coherent; target available; but shares
  C3c's cell bottleneck and answers a secondary channel question.
- **B — joint C3a/C3b pre-registration.** Adds C3a, which is confounded (all-games) or
  null-by-construction (board-decided) → low value; not recommended.
- **C — stop sharpness modeling, move to final synthesis (16.0A).** Consolidate the whole arc;
  avoids spending modeling effort on a secondary, cell-limited, confound-prone channel question
  when the headline (C4) is settled and C3c is consolidated.

## 15. Recommendation

**Primary: Option C — stop sharpness modeling and move to final synthesis (16.0A).** Rationale:
C3a is confounded or null-by-construction; C3b is a secondary flagging/time-management channel
that (a) shares C3c's underpowered sharp×low-clock cells, (b) answers a question already
qualitatively known from 11.2B (clock→flagging is strong and mechanical), and (c) is easily
over-read as move-quality. The scientifically central move-quality question (C3c) is
consolidated; the project's value is now in synthesizing the settled arc, not extending into a
secondary channel.

**Fallback: Option A — flagging-only C3b pre-registration (14.3B)**, *if* the project
specifically wants the channel result — framed strictly as **flagging/time-management channel
analysis (never move-quality)**, with the player-to-move flagging target (via `result_class`
join), and an up-front acknowledgement that the interaction shares C3c's cell limit (so an
underpowered outcome is likely). **C3a is not recommended in any form.**

## 16. Roadmap reconciliation

Next pointer → **16.0A — Final Synthesis / Public-Facing Claim Audit**. Preserved fallback:
**14.3B — Flagging Sharpness Pre-Registration** (C3b only, flagging-channel framing). C3a is
recorded as **not recommended** (confounded / null-by-construction). No
modeling-implementation pointer is set; any C3b work requires its own pre-registration first.

## 17. Explicit non-claims

- **C3a/C3b have not been modeled.** No sharpness outcome moderation shown; no sharpness
  flagging moderation shown.
- **C3a/C3b do not rescue C3c; C3c remains unresolved / no-claim.**
- No causality; no "time pressure causes worse moves/reasoning".
- **No human-obviousness claim** (the v1 feature is an engine-side proxy); surface-bait
  exploratory only.
- No "degradation curve"; Stockfish eval is objective context, not ground truth; DRAW not
  solved; not a best-predictor claim.

## 18. Recommended next ticket

**16.0A — Final Synthesis / Public-Facing Claim Audit.** Fallback (project's choice):
**14.3B — Flagging Sharpness Pre-Registration** (C3b-only, flagging-channel framing). C3a not
recommended. Prior-trajectory extraction remains an optional follow-up for any future
controlled work.
