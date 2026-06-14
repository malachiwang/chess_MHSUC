# Phase 15.1E — Clock Association Robustness Audit

**Labels:** AUDIT/DESIGN | read-only inspection, doc-only
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

15.1D found a **small, monotone, replicated, test-confirmed** controlled association
between lower clock and higher next-move expected-score (ES) loss, ~5–8× smaller than
the dominant eval-band structure. This audit stress-tests that finding before any C4
consolidation and defines the mandatory checks for 15.1F (an implementation ticket).

Two robustness threats are **empirically confirmed as live** (read-only inspection):

1. **Within-band cp composition varies by clock bucket.** Inside `slight`, low-clock
   rows sit higher in the band (mean |cp| ≈ 205 at `under_60`/`60_180` vs ≈ 189 at
   `over_180`, both months); inside `near_equal` the reverse (≈ 30–38 at low clock vs
   ≈ 45 at `over_180`). So the small clock coefficient could partly be residual eval
   composition the four coarse bands do not absorb → **continuous-cp control is
   mandatory**.
2. **`under_60` is mostly flagging games.** It is only **31% (2024-09) / 36% (2024-10)
   board-decided**, versus 86.5% overall — i.e. ~2/3 time-forfeit. Its larger
   `under_60` estimate (≈ +0.007) is heavily a flagging-survivor population, not a clean
   board-move-quality signal → **board-decided-only model is mandatory; `under_60`
   stays exploratory**; `60_180` (late n ≈ 2,360–2,380/month) is the stable contrast.

The data are ready (no extraction needed): `mover_pre_cp`, `clipped_cp_loss`,
large-loss indicators, termination, splits, and mover-player hashes are all present.
15.1F is an **implementation** ticket; no further audit is required. The one genuinely
missing control — prior trajectory — is absent from the artifacts and is carried as a
**stated limitation** (a future extraction ticket), not a 15.1F blocker. Everything
remains **predictive/descriptive, not causal**; this is not a "degradation curve" and
does not prove worse reasoning under time pressure; Stockfish eval is objective context,
not absolute ground truth.

## 2. Current C4 finding from 15.1D

Conservatively restated:

- **Clock:** `60_180` vs `over_180` pooled adjusted ΔES loss **+0.0034**
  [+0.0015, +0.0051]; `under_60` vs `over_180` **+0.0072** [+0.0042, +0.0115]. Both
  exclude zero under mover-player clustering, replicate in both months (09: +0.0031 /
  +0.0080; 10: +0.0038 / +0.0065), and are confirmed on the locked test split
  (+0.0045 / +0.0073). Monotone: less clock → more loss.
- **Eval band (dominant):** slight +0.0286, near_equal +0.0223, clear +0.0158 vs decided
  (pooled, all exclude zero, both months + test). ~5–8× the clock effect.
- **Termination:** `time_forfeit` vs `board_decided` ≈ 0 after controls (pooled −0.0003,
  contains zero).
- **Large-loss logistic:** signs agree with OLS (lower clock and harder bands raise
  mistake probability; eval far larger).

This **refines** 15.1B (the descriptive marginal cells were flat because eval-band
composition varies across clock cells) rather than overturning it. Predictive/
descriptive only; not causal; not a degradation curve.

## 3. Why robustness is required

The clock effect is **small in absolute terms** (≈ +0.003–0.007 ES loss) and lives next
to two known confounds — the eval-band/clock and checkpoint/clock structure documented
since 9.2B/15.1A. A coefficient this small can be created or erased by plausible
specification choices (band coarseness, rating shape, metric, clustering, survivor
composition). It is real enough to test but too small to headline without showing it is
not a specification artifact. The aim of 15.1F is to decide whether the association is
**robust (secondary headline)**, **fragile (consolidate around eval band + flagging)**,
or **mixed (conditional, not headlined)**.

## 4. Robustness threat inventory (ranked)

| # | Threat | Evidence in this audit | Severity |
|---|---|---|---|
| 1 | **Coarse eval-band residual** — within-band cp differs by clock | Confirmed: `slight` low-clock |cp| ≈ 205 vs `over_180` ≈ 189; `near_equal` low-clock ≈ 30–38 vs ≈ 45 (both months) | **High** |
| 2 | **Checkpoint × clock structure** — clock meaning differs by phase; low clock concentrates late | Confirmed: `move_10` has 1 `under_60` row; late group holds essentially all low-clock | **High** |
| 3 | **Survivor / termination composition** — low-clock rows are selected | Confirmed: `under_60` only 31%/36% board-decided vs 86.5% overall | **High** (for `under_60`) |
| 4 | **Sparse `under_60`** — small, confounded cell | Confirmed: 774 / 801 rows, mostly late + time-forfeit | Medium |
| 5 | **Rating specification** — linear `rating_z` may be too simple | Not yet tested; standard sensitivity | Medium |
| 6 | **ES-transform sensitivity** — train-fitted logistic | Untested at contrast level; `clipped_cp_loss` available as raw alternative | Medium |
| 7 | **Player clustering / two-way dependence** — mover-only clustering | Game / White / Black clustering available; two-way deferred | Low–Medium |
| 8 | **White-to-move-only design** — even-ply checkpoints | Structural; documented limitation | Low (scope) |
| 9 | **Missing prior-trajectory control** — clock may proxy past struggle | Confirmed absent from artifacts | Medium (limitation) |

Threats 1–3 are the live ones that could plausibly move the small estimate; they drive
the mandatory checks.

## 5. Mandatory 15.1F checks

A minimal, decisive set (each reports the `60_180`-vs-`over_180` clock contrast,
mover-player-clustered, per month + pooled, with the eval-band contrasts retained as the
positive control):

1. **Continuous eval control (Threat 1).** Add continuous `abs(mover_pre_cp)` (and/or
   finer cp bins) *alongside* the eval bands; compare the clock coefficient to 15.1D.
   The key test: does absorbing within-band cp drive the clock estimate toward zero?
2. **Late-only model (Threats 2, 4).** Fit on `move_30 + move_40` only; primary contrast
   `60_180` vs `over_180`; `under_60` exploratory. Removes the all-high-clock early
   checkpoints from identification.
3. **Board-decided-only model (Threats 3, 5).** Exclude time-forfeit games and refit.
   This is the cleanest move-quality test: does a clock association persist *outside*
   flagging games? (Given `under_60` is ~2/3 time-forfeit, expect its estimate to move
   most.)
4. **Rating-specification sensitivity (Threat 5).** Replace linear `rating_z` with rating
   bins or add a quadratic term; confirm the clock contrast is stable.
5. **Metric sensitivity (Threat 6).** Repeat the clock contrast with `clipped_cp_loss`
   and with the large-loss indicators (ES>0.05, ES>0.10). Direction must agree.
6. **Cluster sensitivity (Threat 7).** Mover-player primary; add game-clustered and
   White/Black (wider-of-two) as secondary; confirm CIs do not collapse to zero only
   under one clustering.

**Mandatory output — robustness matrix:** rows = checks 1–6; columns = 2024-09 /
2024-10 / pooled; entries = clock `60_180` estimate + 95% CI + verdict
(survives / weakens / flips). One row per check keeps it compact.

## 6. Optional / exploratory checks

All exploratory unless promoted before 15.1F runs: `clock × checkpoint`,
`clock × eval_band`, `clock × rating`, and `termination × clock` interactions; finer
clock bins within the late group; a fixed-sigmoid cp→ES sensitivity (only if trivial);
`under_60`-specific descriptive models; combining `under_60 + 60_180` as a single
low-clock level (only if Threat-3 composition is shown comparable).

## 7. Success / failure / mixed interpretation criteria (lock before 15.1F runs)

**Survives** (→ small secondary headline, still not causal, still eval-dominated):
- `60_180` vs `over_180` stays positive in **both months**;
- pooled CI **excludes zero** under mover-player clustering;
- **not materially eliminated** by continuous/finer eval control (check 1) — i.e. the
  estimate stays clearly positive, not driven to ≈0;
- **board-decided-only** estimate keeps the same (positive) sign (check 3);
- metric robustness agrees in direction (check 5).

**Weakens / disappears** (→ consolidate around eval-band structure + flagging-risk
separation; clock = mainly a flagging predictor, move-quality association unresolved):
- continuous/finer eval control drives the estimate to ≈0 or CI crosses zero;
- board-decided-only fails (sign flips or CI crosses zero);
- sign does not replicate across months;
- metric robustness disagrees.

**Mixed** (→ report as conditional/sensitive; do **not** headline clock; propose a
specific extraction, e.g. trajectory, only if a named confound is implicated):
- survives some checks but not the eval-control or board-decided check;
- replicates in one month only.

This is **post-15.1D robustness planning**, not goalpost-moving: the criteria are fixed
now, before 15.1F estimates anything.

## 8. Data and artifact readiness

No extraction or repair needed. Confirmed present in both `next_move_loss_*` artifacts:
`expected_score_loss`, `clipped_cp_loss`, large-loss indicators (derivable),
`mover_pre_cp` (for continuous eval + finer bins), `selected_position_type`,
`mover_rating`, `termination`/`is_time_forfeit` (board-decided filter), `split_set`, and
100% mover-player-hash join via `player_metadata`. The only missing control
(prior trajectory) is genuinely absent and is a documented limitation, not a blocker.

## 9. Player-clustered uncertainty requirements

Retain **mover-player clustering as primary** (the decision-maker). Add **game-clustered**
and **White/Black-player-clustered** (report the wider CI) as secondary, reusing
`clustered_uncertainty.cluster_bootstrap_refit`. Exact two-way (simultaneous White×Black)
clustering stays **deferred/optional** unless trivially available. 200 reps / seed 42
matches 15.1D and is sufficient given runtime (~11 s/month there).

## 10. Metric sensitivity plan

Primary target stays `expected_score_loss`. Robustness re-runs use `clipped_cp_loss`
(raw, transform-free) and the binary large-loss indicators (logistic), all with the same
covariates and reference levels. A fixed-sigmoid cp→ES variant is optional and only if
trivial; the ES transform is **never re-fit on test**. Agreement in *direction* across
metrics is the bar, not equality of magnitude (units differ).

## 11. Termination-channel sensitivity plan

Mandatory **board-decided-only** model (check 3) is the headline move-quality test
(removes flagging games). A **time-forfeit-only** model is **secondary/descriptive**
(survivor population; not a move-quality claim). `termination × clock` is exploratory.
Because `under_60` is ~2/3 time-forfeit, the board-decided-only result is the decisive
read on whether a clock/move-quality association exists outside flagging.

## 12. Roadmap and preregistration implications

- `ROADMAP.md` (live) already records 15.1D complete → 15.1E; this audit advances it to
  15.1F. No rewrite needed.
- `docs/roadmap_rescope_v11_draft.md` still describes the **original** Phase 15
  next-move-quality bridge and predates both the 11.2B flagging reframe and the 15.1D
  small-clock finding. A **one-line "superseded by live roadmap" note** is added at its
  head (does not alter the architecture); a full reconciliation patch is **deferred until
  after 15.1F / C4 consolidation**, not done now.
- **Phase 14 sharpness should stay after C4 consolidation**, not before: C4 is the
  active arc and sharpness moderation (C3 / 15.2A) builds on a settled C4 claim.
- **PREREGISTRATION:** add a short note locking the §7 robustness criteria for the small
  C4 clock association (post-15.1D planning). Do not rewrite the C4 section.

## 13. Proposed 15.1F implementation scope

Implementation ticket. Likely additions to `controlled_move_quality.py` (or a thin
`controlled_move_quality_robustness.py` that reuses its design builder + fit helpers):
- continuous `abs_mover_pre_cp` term + optional finer cp bins;
- late-only and board-decided-only fitting modes;
- rating-bin / quadratic-rating variants;
- `clipped_cp_loss` and large-loss targets reused;
- game / White / Black cluster variants via `cluster_bootstrap_refit`;
- a **robustness-matrix** renderer (compact table per §5) + per-month and combined reports;
- tests for the new design terms, the board-decided/late filters, and matrix assembly.

**Excluded:** sharpness, MultiPV, trajectory extraction, new Stockfish runs, Black-to-move
checkpoint generation, statsmodels.

Reports: `reports/controlled_move_quality_robustness_{2024_09,2024_10}_250k_v1.md`,
`reports/controlled_move_quality_robustness_combined.md`, and a phase report.

## 14. Risks and caveats

- Predictive/descriptive only — not causal; no "degradation curve" language; no claim
  that time pressure causes worse reasoning.
- White-to-move only (even-ply checkpoints).
- `under_60` sparse and ~2/3 time-forfeit → exploratory; the headline is `60_180`.
- Even if the association survives, it stays **small and secondary** to eval band.
- Prior-trajectory control is deferred (absent from artifacts) — the "clock as symptom of
  past struggle" confound remains unadjusted and stated.
- Mover-player clustering ≠ exact two-way dependence.
- Stockfish depth-12 eval is objective context, not absolute ground truth; DRAW remains
  sparse and not solved; sharpness is not implemented or invoked.

## 15. Recommended next ticket

**15.1F — Clock Association Robustness Implementation** (the §5 mandatory matrix:
continuous eval control, late-only, board-decided-only, rating sensitivity, metric
sensitivity, cluster sensitivity; §7 criteria locked in advance). If 15.1F implicates a
specific confound that needs new data (most likely prior trajectory), recommend a
trajectory-extraction ticket before C4 consolidation; otherwise proceed to
**C4 consolidation** after 15.1F. Sharpness moderation (C3 / 15.2A) remains a separate
later arc.
