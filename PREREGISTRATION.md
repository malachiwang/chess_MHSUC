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

#### C3c — Sharpness × Clock Move-Quality Moderation — PRE-REGISTRATION (locked 14.2A, before any modeling)

**Status: locked before modeling.** This operationalizes C3c for the 14.2B implementation.
It builds on the settled C4 baseline (15.1D/15.1F) and the 14.1C full sharpness artifacts.
**No model has been run.** Predictive/descriptive association and moderation only — **not
causal**; the v1 sharpness feature is an engine-side value-fragility proxy, **not** human
obviousness and **not** a complete account of practical difficulty.

1. **Research question.** Does the small, controlled `60_180`-vs-`over_180` clock
   association with next-move expected-score (ES) loss (15.1D/15.1F, pooled ≈ +0.0034)
   become **larger in objectively sharp / value-fragile positions**? I.e. is there a
   positive **clock × sharpness moderation** of next-move ES loss?

2. **Data universe.** Both 10+0 months (2024-09, 2024-10). Per month, join
   `next_move_loss_<m>_250k_v1.parquet` ⋈ `multipv_sharpness_<m>_250k_v1.parquet`
   ⋈ `player_metadata_<m>_250k_v1.parquet` (hashed mover IDs). Confirmed feasible:
   sharpness artifact is unique on the join key, **100% join coverage** onto the non-mate
   modeling frame, mover-player hash present for all rows.

3. **Join keys.** `(game_id, selected_position_type)` for the next-move-loss ⋈ sharpness
   join; `game_id` for the player-metadata join (then mover hash via `mover_color`, always
   White at these even-ply checkpoints).

4. **Exclusions.** Primary analysis: next-move-loss `status == ok` AND sharpness
   `status == ok` AND **non-mate-band** rows AND required covariates non-null. Mate-band is
   **excluded from the primary analysis** (ES comparability) and only appears in a labeled
   mate-band sensitivity (robustness #12). Single-legal-move rows (where `best_second_gap_es`
   is null) are retained — the primary feature does not require it — but `sharp_value_fragility_v1`
   requires `legal_move_count >= 8` so they are non-sharp by construction.

5. **Primary target.** `expected_score_loss` (mover's perspective), checkpoint-level
   next-move loss — the **same target family as 15.1D / 15.1F**.

6. **Primary sharpness feature (locked binary).**
   `sharp_value_fragility_v1 = (n_good_10es <= 2) AND (worst_top5_loss_es >= 0.10) AND
   (legal_move_count >= 8)` — objective value fragility (narrow viable set, steep drop-off
   outside it, sufficient legal-choice clutter). Base rate ≈ 0.142 both months (14.1C).
   **Not human obviousness; not a complete account of difficulty; a pre-registered
   engine-side proxy.** No threshold tuning based on outcomes.

7. **Primary clock contrast.** `60_180` vs `over_180` (the stable controlled contrast from
   the C4 arc), **interacted with `sharp_value_fragility_v1`**.

8. **Primary estimand (difference-in-differences).**
   `[mean ES loss(60_180) − mean ES loss(over_180) | sharp] − [mean ES loss(60_180) −
   mean ES loss(over_180) | non-sharp]`, recovered as the **`clock=60_180 × sharp` interaction
   coefficient** in the model below. **Positive ⇒ the controlled low-clock association is
   larger in sharp positions.**

9. **Model formula (interpretable controlled OLS, 15.1D/15.1F family).**
   `expected_score_loss ~ C(clock_bucket, ref=over_180) + sharp_value_fragility_v1
   + C(clock_bucket):sharp_value_fragility_v1 + C(selected_position_type, ref=move_10)
   + C(eval_band, ref=decided) + rating_z + C(month, ref=2024_09)
   + C(termination_binary, ref=board_decided)`. Fit per month (no month term) and pooled
   (with month term).

10. **Controls.** Checkpoint, eval band (primary; continuous `abs(mover_pre_cp)` as
    sensitivity per 15.1F), `rating_z` (linear, train-only moments — the 15.1F primary;
    quantile-bin / quadratic as sensitivity), month (pooled), termination binary. Estimate
    on **train+val**, **test reserved as locked confirmation**; **no test-set model selection**.

11. **Uncertainty.** **Mover-player-clustered bootstrap** via the existing
    `clustered_uncertainty.cluster_bootstrap_refit` + `summarize_contrasts` (refit per
    resampled cluster), 200 replicates, seed 42 — the 15.1D/15.1F machinery. Month-specific
    estimates computed separately; pooled with month control. Game-clustered and
    White/Black-player-clustered as cluster-sensitivity (robustness #11). Two-way clustering
    remains deferred.

12. **Replication / success criteria (strong support).** ALL of: (a) the primary
    interaction estimate is **positive in both months**; (b) the **pooled** interaction CI
    **excludes zero** (mover-player-clustered); (c) it is **not driven entirely** by one
    checkpoint, one eval band, mate-band rows, or one termination channel; (d) the direction
    **survives** the required robustness checks (esp. continuous-eval control and
    board-decided-only).

13. **Robustness checks (pre-registered).** (1) month-specific replication + pooled;
    (2) board-decided-only (exclude time-forfeit); (3) termination-controlled (primary +
    sensitivity); (4) eval control (band primary, continuous `abs(mover_pre_cp)` sensitivity);
    (5) rating spec (linear primary, quantile-bin/quadratic sensitivity); (6) checkpoint
    controls + checkpoint-specific estimates where n permits; (7) sharpness-threshold
    sensitivity (`_relaxed`, `_strict` — no outcome tuning); (8) large-loss secondary targets
    (logistic `ES>0.05`, optional `ES>0.10`); (9) clipped-cp-loss secondary (familiar
    robustness; ES loss stays primary); (10) surface-bait as an **exploratory** moderator
    (NOT human obviousness, no headline); (11) cluster sensitivity (mover / game / White-Black);
    (12) mate-band sensitivity (primary excludes; document include/exclude effect).

14. **Weak / null / kill criteria.** *Weak/suggestive:* pooled positive but CI overlaps zero;
    or pooled excludes zero but one month is weak/inconsistent; or only a narrower secondary
    contrast survives. *Null/no-support:* small pooled effect with CI overlapping zero; or
    month signs conflict; or robustness shows a confound/sparse-cell driver. *Kill / no-claim:*
    the **sharp × `60_180` cell** is the power bottleneck — measured ≈ **348 (2024-09) / 329
    (2024-10), ≈ 677 pooled** (just above the project's ≥300 CI threshold); if after primary
    filters this cell falls materially below ~300/month (or the bootstrap interaction CI is
    uninformatively wide), the interaction is reported as **underpowered / no claim**. Also
    no-claim if the feature fails to join, becomes near-degenerate, results depend on post-hoc
    threshold changes, or appear **only** in surface-bait diagnostics or **only** after changing
    the primary clock contrast. `under_60 × sharp` (≈110/month) is **exploratory only**.

15. **Forbidden claims (this contrast).** No causality; no "time pressure causes worse moves /
    worse reasoning"; no claim sharpness is proven before/without the model; no claim the v1
    feature captures all human difficulty; **no claim human obviousness has been modeled**; no
    "Stockfish is ground truth"; no "DRAW is solved"; no "best human predictor"; no
    "degradation curve". Even on strong support, the moderation is a **small, secondary,
    predictive/descriptive** finding conditioned on eval-state-dominant move quality.

**Next implementation ticket: 14.2B** — fit this locked model; no design changes permitted
without a logged deviation.

**Post-result status (14.2B, 2026-06-15):** the locked model was run with **no design
changes** (200 reps, seed 42; join validated, `sharp_value_fragility_v1` recompute 0
mismatches). **Classification: UNDERPOWERED / NO CLAIM.** Pooled `clock=60_180 × sharp`
= +0.0102 [+0.0013, +0.0194] (excl 0), same-sign both months — **but** the limiting
sharp×`60_180` cell on the estimation split fell to **297 / 282 per month (< 300)**, the
2024-09 month CI **contains zero** (+0.0074 [−0.0079, +0.0217]), and the **locked test
confirmation is weak and sign-flips** (pooled test +0.0012; 09 +0.0054; 10 −0.0035). Per the
pre-registered kill criterion this is reported as **underpowered / no claim** (an absence of
resolving power, not a null finding); the threshold was **not** moved. Reports:
`reports/sharpness_interaction_combined.md`,
`reports/phase_reports/phase_14_2b_sharpness_interaction_modeling.md`. No causal / sharpness-
moderation-shown / human-obviousness / outcome-flagging claim. Next: 14.2C decides whether to
consolidate the underpowered result, enrich power then re-run the **same locked model**, or
pivot to C3a/C3b — without altering these locked thresholds.

**14.2C interpretation note (2026-06-15):** the directional train+val signal exists but does
**not** pass the locked criteria, and a power audit shows the per-month sharp×`60_180` cell is
≈290 at the 250k-prefix scale, so **ordinary additional months grow pooled precision but not
the per-month cell** — the locked ≥300/month gate is not reliably reachable by simply adding
months. Therefore any future attempt to resolve C3c must be **either** a rerun of *this same
locked model* on enriched data (acknowledging the per-month gate will likely still bind, so a
**pooled-power verdict requires a new pre-registration**), **or** a separately pre-registered
design (e.g. sharp-position oversampling). The locked C3c model/criteria/thresholds here are
**not** changed. Recommended primary path (14.2C): freeze C3c as directional/underpowered/
no-claim and consolidate; enrichment is the named fallback.

**14.2D consolidation (FINAL status, 2026-06-15):** 14.2B ran the locked model; 14.2C audited
power; **14.2D freezes the status** — C3c is **directional but underpowered/no-claim, not
confirmed, not disproven, not a null**, with **no threshold/model/contrast/classification
changes**. Any future revisit must be **either** a rerun of *this same locked design* on
enriched data (the per-month ≥300 gate will likely still bind, so a **pooled-power verdict
requires a new pre-registration**) **or** a separately pre-registered design (e.g.
sharp-position oversampling) — labeled as a new analysis, never retroactive proof of the 14.2B
estimate. Threshold relaxation, post-hoc contrast switching, surface-bait headlining, and
rerun-until-a-month-passes are forbidden. Consolidation report:
`reports/phase_reports/phase_14_2d_c3c_underpowered_result_consolidation.md`.

**C3a / C3b audit note (14.3A, 2026-06-15):** the outcome (C3a) and flagging (C3b) sharpness
channels were **audited, not modeled** (`reports/phase_reports/phase_14_3a_outcome_flagging_sharpness_audit.md`).
They are **separate from C3c and do not rescue it** (C3c stays unresolved/no-claim). **C3a is
not recommended** — all-games C3a re-derives the flagging channel (11.2B) and board-decided
C3a is null-by-construction (the board-decided clock-outcome residual already collapsed). **C3b
is coherent but low-value/likely-underpowered** — its sharp×low-clock interaction cells are the
same scarce ones that left C3c underpowered, and a positive result would be a
time-management/selection **channel** effect, **never** move-quality. **Any C3a/C3b analysis
requires its own separate pre-registration before modeling.** 14.3A recommends moving to final
synthesis (16.0A); a flagging-only C3b pre-registration is the named fallback if the channel
question is specifically desired. No design or thresholds changed here.

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
- **Controlled-model operational lock (resolved in 15.1C, for 15.1D):** primary model
  is `expected_score_loss ~ C(clock_bucket, ref=over_180) + C(checkpoint) +
  C(eval_band, ref=decided) + rating_z + C(month) + C(termination_binary)` on non-mate
  rows, fit by OLS with a **mover-player-clustered bootstrap** for contrast CIs
  (large-loss logistic ES>0.05/0.10 as robustness). The **eval-band contrast is the
  positive control** (expected to replicate, CIs exclude zero); the **coarse clock
  contrast is the main uncertain/null-prone test** and **a clock null is a
  pre-registered acceptable outcome** (it confirms the 15.1B/11.3B no-gradient result).
  `60_180` is the stable low-clock contrast; `under_60` is exploratory (sparse,
  confounded). Estimate on train+val with **test reserved as a locked confirmation**;
  month is replication (per-month then pooled). **Prior-trajectory control is not
  available in the current next-move-loss artifacts** (no pre-checkpoint trajectory
  feature), so 15.1D's controls are eval band + phase + rating + termination + month;
  adding a trajectory feature is a separate future extraction ticket, and until then
  the "clock as symptom of past struggle" confound is an explicit stated limitation.
- **Controlled-model result status (15.1D, both months + pooled + locked test):** the
  **eval-band positive control replicated** as expected (slight/near_equal/clear all
  > decided, CIs exclude zero, dominant). The **coarse-clock contrast was NOT null**:
  it is small but **monotone and replicated** (`60_180` vs `over_180` ≈ +0.003,
  `under_60` vs `over_180` ≈ +0.007 ES loss; both months and the locked test split
  exclude zero), ~5–8× smaller than the eval-band effect. This **refines** the
  15.1B/11.3B descriptive no-gradient result (which was marginal): conditioning on eval
  band reveals a small clock residual. Termination (`time_forfeit` vs `board_decided`)
  was ≈0 after controls, consistent with the 11.2B flagging-channel reframing. Because
  the clock association is non-null, it is routed to a **robustness audit (15.1E)**
  before any C4 consolidation. All predictive/descriptive — no causal or
  reasoning-degradation claim. (Deviation log: bootstrap reps = 200 as pre-set;
  logistic robustness retained; no design changes vs the 15.1C lock.)
- **Clock-association robustness criteria (locked in 15.1E, for 15.1F — post-15.1D
  planning, not goalpost-moving):** the small controlled clock association is credited
  as a **small SECONDARY** finding only if the `60_180` vs `over_180` contrast (a) stays
  positive in both months, (b) has a pooled mover-player-clustered CI excluding zero,
  (c) is **not materially eliminated** by a continuous within-band cp control, (d) keeps
  the same sign in a **board-decided-only** model (time-forfeit excluded), and (e) agrees
  in direction under a transform-free metric (`clipped_cp_loss` / large-loss). If the
  continuous-eval or board-decided check drives it to ≈0 or flips the sign, or it fails to
  replicate, the C4 claim **consolidates around the eval-band structure and the
  flagging-risk separation**, with clock treated as mainly a flagging-risk predictor and
  the move-quality association reported as weak/unresolved. Mixed outcomes are reported as
  conditional and **not headlined**. Even if it survives, the clock association remains
  small, secondary to eval band, and predictive/descriptive (not causal). Two threats are
  already empirically confirmed (within-band cp varies by clock; `under_60` is ~2/3
  time-forfeit), so the continuous-eval and board-decided checks are mandatory.
- **Clock-association robustness result (15.1F):** the small clock association
  **SURVIVED** all mandatory checks under the locked criteria above. Pooled `60_180`
  vs `over_180` = +0.0034 [+0.0015, +0.0052]; it is **not eliminated by continuous
  within-band cp control** (+0.0034), **survives board-decided-only** (+0.0034, isolated
  from flagging), is stable under rating-bin/quadratic and late-only specs, agrees in
  direction across `clipped_cp_loss` and both large-loss logistics, and holds under
  game/White/Black clustering — positive in both months and on the locked test split. It
  is therefore credited as a **small, replicated, controlled, SECONDARY** association
  (≈5–8× smaller than the eval-band structure), **predictive/descriptive, not causal**.
  The outcome-level clock signal remains substantially the flagging channel (11.2B); the
  main unadjusted alternative is the deferred prior-trajectory confound. (No deviations
  from the 15.1E criteria; 200 bootstrap reps, seed 42.)
- **C4 consolidation + prior-trajectory deviation note (15.1G):** the C4 / move-quality
  arc is consolidated and **closed as a predictive/descriptive claim** (see
  `reports/phase_reports/phase_15_1g_c4_claim_consolidation.md`): eval state dominates
  next-move loss; clock has a small, replicated, robustness-checked secondary association;
  the outcome-level clock signal is substantially the flagging channel. **Deviation:** the
  C4 bullet above locks "prior-trajectory control is mandatory." That requirement was
  written before the measurement layer existed, and the next-move-loss artifacts carry **no
  pre-checkpoint trajectory feature** (logged pre-results at 15.1C). Because the
  trajectory/"clock as symptom of past struggle" confound threatens a **causal** reading and
  the consolidated C4 claim is **explicitly descriptive/predictive, never causal**, the
  "mandatory" lock is **reinterpreted as mandatory before any causal / mediation C4 claim**.
  The descriptive C4 claim is closed now with prior trajectory as an **explicit stated
  limitation** and a **recommended optional follow-up** (a future trajectory-extraction
  audit/implementation, after which the controlled + robustness models would be re-run). This
  is a documented deviation, not a silent omission; a closer-to-causal C4 statement requires
  Option B (extract trajectory first).
- **Sharpness status (pre-arc, 15.1H):** sharpness (C3 / Phase 14) has **not been tested** —
  no MultiPV features exist yet. The sharpness arc begins with a feasibility/compute audit
  (14.1A) and requires a **fresh pre-registration (14.2A) before any sharpness modeling**; no
  moderation claim may be made until those features exist and the pre-registered tests run.
  The C3a (flagging-risk) / C3b (board-decided-outcome, cautious) / C3c (move-quality) split
  stands, with C3c (move-quality moderation, building on the settled C4 baseline) as the
  recommended first sharpness target.
- **Sharpness v1 framing (14.1B):** the v1 sharpness primitive is **objective value
  fragility** (narrow viable move set, steep value drop-off outside it, legal-choice clutter),
  defined from engine MultiPV geometry / board logic only (Tier A, anti-circular). Surface
  move tags (check/capture/promotion/quiet/forced-evasion) and "surface-bait" diagnostics are
  **exploratory only and are explicitly NOT a model of human obviousness** — true human
  obviousness is a deferred Tier B layer. The 14.1B pilot extracted candidate composites
  (`sharp_value_fragility_v1` etc.); the **final feature/threshold/orientation are still
  locked at 14.2A**, not here, and no sharpness result has been claimed.
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
  players per month), so the robustness route is **player-clustered bootstrap**, now
  **implemented in 11.3B** (`clustered_uncertainty.py`: game / White-player / Black-player /
  mover-player clustering; exact two-way White×Black deferred). Controlled C4/C3 modeling
  **must carry mover-player-clustered uncertainty** before any primary result; a
  player-disjoint *held-out slice* may serve as a secondary check only. 11.3B confirmed both
  prior headline findings survive player clustering (11.2B flagging channel; 15.1B eval-band
  structure). The player-leakage caveat remains noted in every report (~86% of checkpoint
  rows touch a player spanning >1 split). **No raw usernames are ever committed** anywhere
  in the repo; any player identifier used for clustering is a salted one-way hash kept in
  gitignored data artifacts.
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
