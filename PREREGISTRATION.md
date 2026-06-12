# PREREGISTRATION.md — v1

## Status

v1, refined by Ticket 11.1A (2026-06-12) from the 11.0B stub. This document locks the
central scientific claim, the four primary contrasts of the v11 arc (Phases 12–15),
metric conventions, split/evaluation discipline, exploratory boundaries, and the
revision policy — before any Phase 12+ feature exists. Phase-specific lock-ins that
require not-yet-existing definitions (e.g., the exact 14.2A sharpness composite, the
15.0A loss-definition choice) are named here and finalized in their designated
pre-registration tickets; the *intended contrast* is locked now.

## Purpose

Pre-register the primary contrasts of the v11 research arc so that headline results
cannot be the product of post-hoc selection. Anything not listed as a primary contrast
is exploratory and must be labeled as such in every report.

## Central scientific claim

### Current supported claim

> Across two independent Lichess 10+0 monthly samples (2024-09 and 2024-10, 250k raw
> games each), after controlling for fixed-depth Stockfish eval and ratings, clock
> features add a small but replicated predictive signal for game outcomes. Slice
> analysis shows the signal is strongest in late-game low-clock positions. This is
> predictive evidence of residual human/context signal, not causal evidence that time
> pressure degrades reasoning.

Standing qualifiers (apply to every restatement): Stockfish eval is objective position
context, not ground truth; clock effects are associations, not proof of reasoning
degradation; DRAW remains sparse and not solved; reasoning quality is not directly
measured; "degradation curve" language is not used; the difficulty of sharp positions
is not claimed as novel (Anderson et al., move level; see `docs/RELATED_WORK.md`);
ChessMimic is a strong neural reference point, not a direct ceiling.

### Future v11 hypothesis

> The v11 arc tests whether the residual clock signal is amplified in positions where
> objective value is harder for humans to realize — especially positions that are
> engine-narrow, non-obvious, and eventually forward-fragile — and whether that
> amplification varies by rating and time-control environment.

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

### Contrast 1 — Rich clock/history robustness (Phase 12)

- **Question:** do richer clock-dynamics/history features absorb additional residual
  signal beyond the frozen E4a baseline?
- **Comparison:** E4a (frozen E3 + original clock features) → E4b (E3 + rich clock
  dynamics + relative clock features) → E4c (E4b + game-history/trajectory features).
  Feature lists fixed in 12.1A before evaluation.
- **Primary metric:** validation log-loss deltas, paired game-level clustered bootstrap
  (1,000 replicates, seed=42), CI on each delta. cp-based historical lineage preserved
  in all tables; if E3w/E4w exist (Phase 12.0), the score-scale versions run as a
  parallel robustness analysis, never as a replacement.
- **Required datasets:** 2024-09 250k and 2024-10 250k (both months mandatory).
- **Success criterion:** richer clock/history features improve or clarify the residual
  signal in both months. If E4b/E4c absorb the E4a signal (the original features become
  redundant given richer ones), that is reported as a finding about where the signal
  lives, not as failure. Either way, E4c becomes the strongest non-sharpness baseline
  that Phase 14 must beat or moderate.

### Contrast 2 — Board-decided-only clock residual (Phase 11.2)

- **Question:** is the E3→E4 clock residual mostly mechanical timeout/flagging risk, or
  does it survive among board-decided games?
- **Comparison:** all-games E3→E4 delta vs. board-decided-only E3→E4 delta (same months,
  same frozen models, refit on the filtered population). Conditional on the 11.2A
  feasibility verdict for termination fields; the minimum supported taxonomy is
  time-forfeit vs. board-decided.
- **Primary metric:** validation log-loss delta with paired game-level bootstrap CI on
  the board-decided subset; late-clock slice replication on the subset where cell sizes
  permit (300-game CI threshold inherited from Phase 9.2).
- **Required datasets:** both months.
- **Success criterion:** the board-decided delta retains a meaningful fraction
  (guideline from the v11 roadmap: ≥ ~half) of the all-games magnitude and ideally
  excludes zero. If it collapses, the claim is honestly re-framed: the clock residual
  is largely a termination/flagging-channel signal, and packaging language changes
  accordingly. Re-framing is a legitimate outcome, not failure.

### Contrast 3 — Sharpness moderation of the clock residual (Phase 14)

- **Question:** is the clock residual larger in high-sharpness positions than in
  low-sharpness positions?
- **Primary contrast:** difference of paired clock deltas across train-defined
  sharpness strata — terciles or the binary high-sharpness composite
  (`narrow AND non-obvious`, per Appendix B.1 of the v11 roadmap) — at late checkpoints
  (move_30 + move_40), both months.
- **Model comparison:** clock-enabled vs. no-clock model pairs within strata (the E8/E9
  structure as defined in Phase 14); the exact final model pair is locked in 14.2A
  before modeling, but the intended contrast — difference-of-deltas across sharpness
  strata — is locked here and may not be replaced by a different headline.
- **Primary metric:** difference in paired log-loss deltas between high- and
  low-sharpness strata, with bootstrap CI on the difference-of-deltas (game-level
  clusters; replicate-paired across strata).
- **Headline orientation:** advantaged-player conversion sharpness (side-to-move
  primitive restricted to board-leader-to-move positions); side-to-move-overall as the
  labeled secondary view. Defensive and mutual sharpness are exploratory.
- **Tier A discipline (binding):** the headline moderator uses engine-side/rule-based
  inputs only — MultiPV narrowness in expected-score space plus rule-based obviousness
  discounts. No human-behavior-derived difficulty may enter the headline moderator
  (anti-circularity; Appendix B of the v11 roadmap).
- **Required datasets:** both months; strata defined on train only.
- **Success criterion:** the difference-of-deltas has the expected sign (larger clock
  delta in high-sharpness strata) in both months, with the CI excluding zero in the
  primary month or in a pooled analysis that is itself pre-registered in 14.2A before
  results are viewed; and the result survives the board-decided-only filter if 11.2
  makes that feasible. **Kill condition** (from the v11 roadmap, restated): if
  sharpness neither moderates the clock residual nor adds main-effect signal beyond
  E4c/E7 in either month, the sharpness arc stops and the controlled null is written up.

### Contrast 4 — Next-move quality constraint curve (Phase 15)

- **Question:** do low clock and (later) sharpness correspond to worse next-move
  quality, especially in late/sharp positions?
- **Target:** next-move expected-score loss (mover's perspective); secondary: clipped
  centipawn loss. The exact loss definition (eval-swing Option A vs. vs-engine-best
  Option B, per Appendix A of the v11 roadmap) is chosen in 15.0A before extraction;
  the intended primary — expected-score loss at checkpoints — is locked here.
- **Primary contrast:** expected-score loss by clock bucket at late checkpoints,
  conditioned on rating bucket, eval band, and phase; the initial controlled model is
  `expected-score loss ~ time bucket + rating + eval band + phase + prior trajectory`,
  with interactions (time × rating, time × eval band, time × sharpness) added only
  after the main-effects model is reported. Prior-trajectory control is mandatory
  (the "clock as symptom of past struggle" confound).
- **Required datasets:** both months (extraction cost permitting; one-month pilot first
  is acceptable if 15.0A's compute audit requires it, with the second month as
  confirmation).
- **Success criterion:** descriptive curves plus controlled models provide a
  mechanism-style (still predictive) bridge between the outcome-level residual and
  move-level behavior. Non-monotone shapes are reportable findings (jk_182 caution:
  inaccuracy rates can fall at low clock), framed against the selection-vs-degradation
  distinction. No causal or "degradation curve" wording regardless of shape.

## Secondary / exploratory analyses

Everything else is exploratory and must be labeled exploratory in all reports,
including (non-exhaustively):

- rating × sharpness interactions beyond the Contrast 3 primary;
- defensive sharpness and mutual/both-sides sharpness orientations;
- forward-line sharpness / forward fragility features before local sharpness succeeds
  (gated per the v11 roadmap);
- cross-time-control dose-response analyses until Phase 16 pre-registers its
  per-control design (direction may be pre-stated; magnitudes are not);
- any neural / frozen-Maia / ChessMimic comparison (Tier B at most; never in Tier A);
- 100-Elo-bin visualizations where cell counts are sparse (CI-bearing curves use
  200-pt bins or the existing four buckets, per the 15.0A cell-count audit);
- percent-swing metrics (dangerous near zero; exploratory only, with a
  `max(|eval|, threshold)` denominator if ever used);
- selection-vs-degradation decompositions (a candidate for promotion via a future
  pre-registration entry, per 11.0A open question 15);
- per-checkpoint decompositions of any new delta beyond those named in the contrasts;
- composite-v2 sharpness definitions (e.g., adding `best_move_is_simple_trade`)
  — promotion requires its own pre-registration entry before the promoting analysis runs.

## Metric conventions

- **Outcome prediction:** multiclass log loss is the primary metric; accuracy,
  macro-F1, and Brier are reported but never headline. Probabilities sum to 1;
  class order fixed (BLACK_WIN, DRAW, WHITE_WIN).
- **Move quality:** expected-score loss (mover's perspective) is primary; **clipped
  centipawn loss** (cap ~1000cp; mate scores mapped to cap) is secondary for
  literature comparability; **raw centipawn loss** appears only inside
  eval-band-conditioned panels or with explicit caveats; **percent swing** is
  exploratory and dangerous near zero (see above).
- **Draws** are scored 0.5 in expected-score contexts unless a later pre-registered
  revision changes this.
- **Mate-band positions** are handled as a separate band or explicitly excluded,
  per the relevant phase audit (14.1A / 15.0A); they are never silently pooled into
  cp-based features.
- **cp-based historical lineage is preserved:** frozen E3/E4 anchors appear in every
  comparison table; WDL/expected-score model variants (E3w/E4w) are parallel
  robustness layers, never silent replacements; material divergence between scales is
  itself a reported finding.

## Split and evaluation discipline

- Splits are game-level (seed=42). **The test split is not used for model selection**
  (WORKFLOW.md §13); validation is the working surface for all design and selection
  decisions; test opens at most once per major version for locked final evaluation.
- **All bins, thresholds, terciles, mappings, and learned transforms are defined on
  the train split only** (sharpness strata, cp→expected-score mappings,
  moves-remaining heuristics, difficulty models, etc.) and applied unchanged to
  validation.
- **Cross-month replication is treated as independent validation:** a primary contrast
  is "replicated" only if it holds on both monthly datasets, each with its own splits.
- **Player leakage:** player-clustered uncertainty (and player-disjoint splits if the
  11.3A graph audit permits) are applied to primary contrasts once Phase 11.3
  establishes them; until then, the player-leakage caveat is mandatory in every
  report. **No raw usernames are ever committed** anywhere in the repo; any player
  identifier used for clustering is a salted hash kept in gitignored data artifacts.
- Slice definitions for pre-registered contrasts are fixed before results are computed
  and never tuned after seeing them; sub-threshold cells (< 300 games) are reported
  descriptively with explicit no-CI markers, never silently dropped or merged.
- Exploratory analyses are labeled exploratory in every table and section where they
  appear.

## Anti-overclaiming language

- All findings are predictive associations. **Causal language is prohibited unless a
  causal design is actually introduced** (none is currently planned). In particular,
  the project never claims that time pressure causes worse reasoning.
- "Degradation curve" language is avoided unless a design explicitly licenses it;
  ordered-bucket patterns are reported as patterns; non-monotone shapes are findings.
- Stockfish evaluation is objective position context, not ground truth. Reasoning
  quality is not directly measured. DRAW remains sparse and is not solved.
- Novelty claims follow `docs/RELATED_WORK.md` (forbidden list included there);
  the difficulty of sharp positions is not claimed as novel; ChessMimic is described
  only as "a strong neural reference point, not a direct ceiling."

## Revision policy

- **Before a contrast's implementation begins:** this document may be revised by an
  explicit ticket, with each change logged (date, ticket, rationale) and visible in
  git history.
- **After a contrast's inputs exist (implementation has begun):** its primary
  definitions may not be changed based on observed results. If feasibility forces a
  change (e.g., a field is unavailable, a cell is empty), the originally planned
  contrast is preserved in the document and the deviation is documented alongside it —
  the original is never silently edited away.
- **Major new contrasts** require a new pre-registration section/version added before
  any results bearing on them are viewed; exploratory→primary promotions likewise
  require their own entry before the promoting analysis is run.
- Phase-designated lock-in tickets (14.2A for the sharpness composite and pooled
  analysis; 15.0A for the loss definition, bins, and blunder threshold) finalize the
  open parameters named in this document and may not alter the intended contrasts.
