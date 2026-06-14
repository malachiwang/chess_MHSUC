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

### Current supported claim (revised after 11.2B; see "Post-11.2B claim status")

> Across two independent Lichess 10+0 monthly samples (2024-09 and 2024-10, 250k raw
> games each), after controlling for fixed-depth Stockfish eval and ratings, clock
> features add a small but replicated predictive signal for game outcomes. A
> pre-registered termination decomposition (11.2B) shows this residual is substantially
> attributable to the time-forfeit / flagging channel: among board-decided games the
> residual is approximately zero (2024-09) or slightly reversed (2024-10). The project
> has measured and replicated a real human-constraint outcome channel that, in the
> current outcome setup, is primarily a flagging-risk channel rather than a
> board-decided outcome signal. Whether low clock relates to board-*play* quality
> remains open and must be tested directly (next-move quality, Contrast C4), not
> inferred from final-outcome residuals. This is predictive evidence, not causal
> evidence that time pressure degrades reasoning.

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

Post-11.2B refinement: because 11.2B showed the outcome residual is primarily the
flagging channel, the amplification question is now tested against three distinct
targets (flagging risk, board-decided outcomes cautiously, and move-quality loss) — see
the C3a/C3b/C3c split and the strengthened C4. The board-play-quality target (C4 /
C3c) is the central one; it does not depend on the outcome residual surviving.

## Post-11.2B claim status

Ticket 11.2B executed the pre-registered Contrast C2 and triggered its collapse/reframe
branch. Recorded result, both months (prediction-side filter of frozen all-games E3/E4
models; no retraining; paired game-level bootstrap, 1,000 replicates, seed=42):

- **All-games clock residual replicated:** 2024-09 −0.0138 [−0.0186, −0.0091];
  2024-10 −0.0120 [−0.0177, −0.0062]. CIs exclude zero in both months.
- **Board-decided-only residual collapsed / sign-reversed:** 2024-09 +0.0010
  [−0.0029, +0.0049] (CI contains zero, retained fraction 0.07); 2024-10 +0.0060
  [+0.0015, +0.0109] (CI excludes zero on the *positive* side; the magnitude-based
  retained fraction 0.50 overstates retention because the sign reversed).
- **Time-forfeit channel explains most of the all-games residual:** time-forfeit-only
  delta −0.1183 (2024-09) / −0.1305 (2024-10), ~10× the all-games delta.
- **Late-game low-clock board-decided localization did not replicate** (60_180s:
  −0.0294 excl. zero in 2024-09 but −0.0061 contains zero in 2024-10).

Interpretation (predictive only): the replicated clock residual is primarily a
time-forfeit / flagging channel, not a board-decided outcome signal. The central claim
is reframed accordingly (above). The board-play-quality question is now carried by C4.
Filtering time-forfeit games induces selection (board-decided low-clock games are a
survivor population) and does not create a causal design. See
`reports/termination_decomposition_combined.md` and
`reports/phase_reports/phase_11_2c_claim_reframing_audit.md`.

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

### Contrast 2 — Board-decided-only clock residual (Phase 11.2) — COMPLETED (11.2B)

**Status: COMPLETED, 2026-06-12 (11.2B). Result: COLLAPSE branch.** All-games residual
replicated; board-decided-only residual collapsed (2024-09, CI contains zero) /
sign-reversed (2024-10, positive); time-forfeit channel carries the signal (−0.118 /
−0.131). Per the pre-registered collapse branch, the central claim is reframed toward
the flagging channel (see "Post-11.2B claim status"). **Consequence for future
contrasts:** sharpness moderation (C3) is split so it no longer assumes a surviving
board-decided outcome residual; C4 (move-quality) is elevated as the central board-play
test. Full record: `reports/termination_decomposition_combined.md`,
`reports/phase_reports/phase_11_2c_claim_reframing_audit.md`. The pre-registered
definition below is preserved unaltered for provenance.

- **Question:** is the E3→E4 clock residual mostly mechanical timeout/flagging risk, or
  does it survive among board-decided games?
- **Comparison (primary design):** all-games E3→E4 validation delta vs.
  board-decided-only E3→E4 validation delta, computed by **filtering the saved
  validation predictions of the frozen all-games E3/E4 models** by termination
  channel. **No retraining for the primary analysis.** Same months; the minimum
  supported taxonomy is time-forfeit vs. board-decided (confirmed feasible by 11.2A).
- **Secondary (optional, different estimand):** refitting E3/E4 on board-decided-only
  training data answers "does the residual exist in a board-decided world?" — it is
  NOT the primary C2 test and may only run if a later ticket explicitly approves it
  as a pre-registered secondary.
- *Revision log: clarified by Ticket 11.2B (2026-06-12) before any C2 results were
  computed — the 11.0B stub wording "same frozen models, refit on the filtered
  population" was internally contradictory (found by the 11.2A audit). This is a
  pre-implementation clarification, not a post-result change.*
- **Primary metric:** validation log-loss delta with paired game-level bootstrap CI on
  the board-decided subset; late-clock slice replication on the subset where cell sizes
  permit (300-game CI threshold inherited from Phase 9.2).
- **Required datasets:** both months.
- **Success criterion:** the board-decided delta retains a meaningful fraction
  (guideline from the v11 roadmap: ≥ ~half) of the all-games magnitude and ideally
  excludes zero. If it collapses, the claim is honestly re-framed: the clock residual
  is largely a termination/flagging-channel signal, and packaging language changes
  accordingly. Re-framing is a legitimate outcome, not failure.

### Contrast 3 — Sharpness moderation (Phase 14) — split after 11.2B

11.2B showed the board-decided outcome residual collapsed, so C3 may no longer assume a
surviving board-decided outcome residual to moderate. C3 is split into three
distinct-target contrasts. The Tier A anti-circularity discipline (engine-side/rule-based
sharpness only; MultiPV narrowness in expected-score space plus rule-based obviousness
discounts; no human-behavior-derived difficulty in any headline moderator — Appendix B
of the v11 roadmap) and the advantaged-player-conversion headline orientation apply to
all three. Strata are train-defined; both months required; late checkpoints (move_30 +
move_40); difference-of-deltas with game-level bootstrap CIs.

- **C3a — Flagging-risk sharpness moderation (well-motivated by 11.2B).** Does sharpness
  / position type interact with clock in predicting *time-forfeit risk*? Target is the
  termination channel (time-forfeit vs. board-decided), not board-play quality. Locked
  intended contrast: difference in clock's contribution to flagging-risk prediction
  across sharpness strata. Exact model/target form locked in 14.2A.
- **C3b — Board-decided outcome sharpness moderation (cautious / secondary).** Does a
  board-decided outcome clock residual exist in specific sharpness strata even though it
  collapsed overall? Optional and explicitly secondary; framed cautiously because C2
  collapsed; never a headline; a positive stratum-specific finding requires the
  pre-registered pooled/secondary handling and the board-decided filter.
- **C3c — Move-quality sharpness moderation (likely the most relevant after 11.2B).**
  Does sharpness amplify clock's association with worse *next-move expected-score loss*?
  Target is move quality (the C4 metric), not final outcome. Locked intended contrast:
  difference of clock's move-quality contribution across sharpness strata. This is the
  natural sharpness extension of C4 and is structurally immune to the C2 collapse.
- **Primary metric (each):** difference in paired deltas between high- and low-sharpness
  strata on the relevant target, with bootstrap CI on the difference-of-deltas
  (game-level clusters; replicate-paired across strata).
- **Headline among the three:** to be confirmed with Malachi before 14.2A; the audit
  (11.2C) recommends C3c (move-quality) as the central sharpness test, with C3a
  (flagging) as a strong secondary and C3b (board outcome) cautious/secondary.
- **Success criterion (each):** the difference-of-deltas has the expected sign in both
  months, CI excluding zero in the primary month or a 14.2A-pre-registered pooled
  analysis. **Kill condition** (restated): if sharpness neither moderates clock on any
  of the three targets nor adds main-effect signal beyond E4c/E7 in either month, the
  sharpness arc stops and the controlled null is written up.

### Contrast 4 — Next-move quality constraint curve (Phase 15) — ELEVATED after 11.2B

**Post-11.2B status: this is now the central board-play test.** C4 directly measures
next-move expected-score loss; it **does not depend on the outcome residual surviving
board-decided filtering** and is therefore structurally immune to the C2 collapse. It is
the contrast that answers the question 11.2B left open — *does low clock relate to
board-play quality, not just flagging?* — by measurement rather than inference from
final outcomes. Its priority is raised accordingly (see the reordering: 15.0A audit
recommended next).

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
- **Player leakage:** the 11.3A graph audit established that a **strict player-disjoint
  3-way split is infeasible** (a giant connected component holds ~92% of games / ~86% of
  players per month), so the planned robustness route is **player-clustered (mover-player /
  two-way) bootstrap** applied to primary contrasts once Phase 11.3B implements it; a
  player-disjoint *held-out slice* may serve as a secondary check only. Controlled C4/C3
  modeling requires this player-aware uncertainty plan before any primary result. Until
  11.3B lands, the player-leakage caveat is mandatory in every report (~86% of checkpoint
  rows touch a player spanning >1 split). **No raw usernames are ever committed** anywhere
  in the repo; any player identifier used for clustering is a salted hash kept in gitignored
  data artifacts.
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

### Revision log

- **2026-06-12 (Ticket 11.1A):** stub → v1; four primary contrasts locked.
- **2026-06-12 (Ticket 11.2B):** C2 wording clarified before any C2 results were
  computed (primary = prediction-side filter of frozen models, no retraining).
- **2026-06-12 (Ticket 11.2C):** reframing after the pre-registered C2 collapse branch.
  C2 marked completed (collapse result); central supported claim revised toward the
  flagging-channel framing; C3 split into C3a (flagging-risk) / C3b (board-decided
  outcome, cautious/secondary) / C3c (move-quality); C4 elevated as the central
  board-play test. **This is a pre-next-analysis reframing executed under the
  collapse branch that was written before C2 ran — not result-shopping.** No C3/C4
  inputs exist yet, so their definitions remain revisable per the revision policy; the
  C2 definition is frozen and preserved for provenance.
