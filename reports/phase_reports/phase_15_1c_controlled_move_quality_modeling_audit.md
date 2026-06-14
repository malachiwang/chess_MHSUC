# Phase 15.1C — Controlled Move-Quality Modeling Audit

**Labels:** AUDIT/DESIGN | read-only inspection, doc-only
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

This audit designs the controlled C4 move-quality modeling layer (to be built in
15.1D) **before** any model is fit. The central question: after conditioning on eval
band, checkpoint/phase, rating, termination channel, and month — with mover-player
clustering — does **clock** state retain any stable association with next-move
expected-score (ES) loss, or is the robust move-quality structure **eval state**?

The inputs are ready and clean: both next-move-loss artifacts have every required
column, split labels, and 100% mover-player-hash coverage (0 nulls). The ES-loss
target is **bounded [0, ~0.81], right-skewed, and ~33% zero-inflated** — so the
recommended primary model is a **transparent additive linear model for mean ES loss
(OLS) with a mover-player cluster bootstrap**, plus **large-loss logistic models**
(P(ES>0.05), P(ES>0.10)) as robustness; a two-part model is deferred.

The recommended **primary controlled contrast** is the coarse clock effect
(`60_180` and `under_60` vs `over_180`) net of checkpoint, eval band, rating, month,
and the board-decided/time-forfeit binary, with the **eval-band contrast as a
positive control** (expected to remain large with CIs excluding zero). The empirical
audit reconfirms the 9.2B clock×checkpoint confound is severe (move_10 is 99.96%
`over_180`), so **clock is only estimable in the late group and must be
checkpoint-conditioned**; `under_60` is sparse (≈750–800 rows/month) and should be
exploratory/descriptive, with `60_180` (≈2,600/month) the stable low-clock contrast.

`statsmodels` is **not installed**; 15.1D should use scikit-learn estimators plus the
project's own cluster bootstrap (no new dependency, no reliance on analytic clustered
SEs). Everything here is **predictive/descriptive association, not causal**; Stockfish
eval is objective position context, not absolute ground truth.

## 2. Scientific motivation after 15.1B and 11.3B

11.2B/11.2C reframed the final-outcome clock signal as primarily the time-forfeit /
flagging channel, moving the board-play-quality question to next-move quality (C4).
15.1B (descriptive Atlas) found **no replicated clock gradient** among stable cells
and a **strong replicated eval-band pattern** (loss peaks near_equal/slight, lowest
decided). 11.3B confirmed both the flagging-channel result and the eval-band structure
**survive mover-player clustering**, and that strict player-disjoint splitting is
infeasible (giant component) so **player-clustered uncertainty** is the robustness
route. 15.1D turns the descriptive Atlas into a **controlled** estimate: does clock
matter for move quality *after* simultaneously adjusting for the confounders, with
honest clustered uncertainty? The pre-registered expectation is a **clock null** and
an **eval-band positive control**.

## 3. Available modeling inputs

Read-only inspection of the four artifacts (joined via `game_id`):

| Check | 2024-09 | 2024-10 |
|---|---|---|
| OK rows | 64,371 | 61,868 |
| Non-mate-band rows (modeling base) | 61,956 | 59,625 |
| Mate-band excluded | 2,415 | 2,243 |
| `mover_player_hash` nulls (non-mate) | 0 | 0 |
| Unique movers | 12,910 | 12,882 |
| Split (train / val / test, non-mate) | 43,476 / 9,281 / 9,199 | 41,693 / 8,941 / 8,991 |
| `mover_rating` range / median / nulls | 422–2709 / 1601 / 0 | 400–2717 / 1594 / 0 |
| board_decided / time_forfeit (non-mate) | 53,640 / 8,316 | 51,579 / 8,046 |

All required modeling columns are present and joinable: `expected_score_loss`,
`clipped_cp_loss`, `mover_pre_cp` (eval band), `time_bucket`/`mover_clock_s` (clock
bins), `selected_position_type` (phase/checkpoint), `mover_rating`, `termination` /
`is_time_forfeit`, `split_set`, and `mover_player_hash` (derived 100% via
`join_mover_player`). Eval bands, clock bins, rating bins, and termination channel are
all derivable with the existing `constraint_atlas` helpers.

**Target distribution (non-mate, both months agree):** mean ES loss ≈ 0.034, median
≈ 0.010, **~33% exact zeros**, ~20% > 0.05, ~9% > 0.10, max ≈ 0.81. Bounded, right-
skewed, zero-inflated — this drives the model-family choice (§10).

**Clock×checkpoint confound (decisive):**

| Checkpoint | under_60 | 60_180 | over_180 | (2024-09 non-mate) |
|---|---|---|---|---|
| move_10 | 1 | 9 | 24,211 | 99.96% over_180 |
| move_20 | 24 | 238 | 18,741 | |
| move_30 | 241 | 1,067 | 10,718 | |
| move_40 | 508 | 1,294 | 4,904 | |

Low clock is essentially a move_30/40 phenomenon → **marginal clock effects are
forbidden**; clock must enter only checkpoint-conditioned (or estimated within the
late group). `under_60` totals ≈749–773 rows/month (late) — above 300 but small and
confounded.

**Eval band counts (non-mate, 2024-09):** near_equal 18,899 · slight 18,549 · clear
21,299 · **decided 3,209** (smallest but CI-eligible). Good positive-control
structure. **`mover_color` is uniformly White** (even-ply checkpoints) → the model
estimates **White-to-move decision quality**; Black-to-move generality is out of scope
until an odd-ply sampling extension exists.

**No data was written.**

## 4. Target definition

**Primary target:** `expected_score_loss` (mover's perspective), **non-mate-band rows
only**, mate-band excluded from the headline model.

**Secondary targets (robustness):** `clipped_cp_loss`, and large-loss indicators
`expected_score_loss > 0.05`, `> 0.10`, `clipped_cp_loss > 100`, `> 200`.

Because the target is bounded/skewed/zero-inflated:

- **Primary: OLS (mean ES loss)** — transparent, directly interpretable as adjusted
  mean ES-loss differences; the quantity of scientific interest is the adjusted mean
  difference across clock buckets, and OLS estimates it consistently. Uncertainty
  comes from the cluster bootstrap (not model-based SEs), so OLS's homoskedastic-normal
  assumptions are not relied on for inference.
- **Robustness: large-loss logistic models** — interpretable as adjusted probability/
  odds of a sizeable mistake, robust to skew and to the ES transform's exact shape.
- **Deferred: two-part (hurdle) model** — only if the mean and large-loss models
  disagree in a way that demands separating "any loss" from "severity". Not in 15.1D's
  default scope to avoid over-interpretation.
- **Not recommended as primary:** beta/quasi-binomial GLM (needs statsmodels, and the
  zero mass breaks beta support); quantile regression (median is ~0.010 with 33% zeros,
  so a median model is uninformative — quantiles are better reported descriptively as
  in 15.1B).

## 5. Predictor and covariate design

**Core covariates (primary additive model):**

- `clock_bucket` — coarse `{under_60, 60_180, over_180}`, reference `over_180`.
- `selected_position_type` — `{move_10, move_20, move_30, move_40}`, reference
  `move_10` (or the late group for the late-only secondary model).
- `eval_band` — `{near_equal, slight, clear, decided}`, reference `decided` (so the
  positive-control contrasts read as "harder bands vs decided").
- `rating_z` — continuous mover rating, standardized (mean/sd from the **training**
  rows only, applied to all). No nulls; full range supports continuous use.
- `month` — `{2024_09, 2024_10}` fixed effect (pooled model); also fit per month.
- `termination_binary` — `{board_decided, time_forfeit}`, reference `board_decided`.

**Optional / secondary predictors:** continuous `mover_pre_cp` magnitude (alternative
to banded eval); `log(mover_clock_s)` (continuous clock, late group only); 200-pt
rating bins (robustness vs continuous).

**Discipline:** because 15.1B showed marginal clock summaries mislead, **every clock
term is checkpoint-conditioned** — either by including `selected_position_type` in the
additive model (primary) or by restricting clock estimation to the late group
(secondary). The primary clock contrast is reported with the confound explicitly
controlled.

## 6. Primary controlled contrast

**Primary C4 controlled contrast (lock in PREREGISTRATION):**

> Among non-mate checkpoint rows, the association between **coarse clock bucket** and
> **expected-score loss**, after controlling for checkpoint, eval band, mover rating,
> month, and termination channel, with **mover-player-clustered** uncertainty.

Candidate primary formula:

```
expected_score_loss ~ C(clock_bucket, ref=over_180)
                     + C(selected_position_type, ref=move_10)
                     + C(eval_band, ref=decided)
                     + rating_z
                     + C(month)
                     + C(termination_binary, ref=board_decided)
```

- **Primary clock test:** coefficients on `60_180` and `under_60` (vs `over_180`).
  `60_180` is the **stable** low-clock contrast (≈2,600/month); `under_60` is
  **exploratory/descriptive-only** (≈750–800/month, heavily confounded). Report a
  late-group-restricted refit as the clock-focused companion.
- **Eval-band positive control:** coefficients on near_equal/slight/clear (vs
  decided) — expected to be large and positive with clustered CIs excluding zero,
  matching 11.3B (slight−decided +0.024, near_equal−decided +0.016).

**Interpretation rules (pre-specified):**

- Clock coefficients near zero / CI crossing zero / not replicating across months ⇒
  **confirms the descriptive no-clock-gradient result** (a clock null is an acceptable,
  pre-registered outcome — not a failure).
- Eval-band coefficients large with clustered CIs excluding zero in both months ⇒
  **eval state is the robust move-quality structure**.
- A clock effect appearing only inside an interaction is **secondary/exploratory**
  unless it was pre-registered (§7).

## 7. Interaction test plan (staged, mostly exploratory)

Fit the additive primary model first; then add **one interaction family at a time**
(never all at once — the sparse low-clock cells make a saturated model unstable):

1. `clock_bucket × selected_position_type` — clock meaning changes by phase
   (most defensible; arguably belongs near-primary given the confound).
2. `clock_bucket × eval_band` — does low clock matter differently in equal/slight vs
   decided positions?
3. `clock_bucket × rating` — do stronger players buffer time pressure?
4. `termination_binary × clock_bucket` — time-forfeit rows may behave differently.
5. `month × clock_bucket` — replication / heterogeneity check.

All interactions are **exploratory** unless explicitly pre-registered before 15.1D
runs. Each is reported with mover-player-clustered CIs and month-by-month replication;
an interaction is only "noted" if it replicates.

## 8. Train/validation/test and replication discipline

C4 controlled modeling is **inferential/descriptive, not predictive**, so the
discipline differs from the baseline/GBM tickets. Recommended design for 15.1D:

- **Primary estimation on train + validation pooled**, with **test reserved as a
  locked confirmation subset** — refit the primary model on test and check the clock
  and eval-band contrasts agree in sign/magnitude. Do **not** tune anything on test.
- **Month is replication, not a random split:** fit and report **per month first**,
  then pooled (with a `month` fixed effect). A contrast is only credited if it
  replicates across 2024-09 and 2024-10.
- **Inference via mover-player cluster bootstrap over the estimation rows** (§9), not
  via the random split — the split protects against over-fitting the *specification*,
  while clustering provides honest uncertainty given repeated players.
- `rating_z` standardization uses **train-only** moments to avoid leakage into the
  held-out confirmation.

Rationale: this mirrors the project's existing "replicate across months + clustered
CI" pattern (9.3B, 11.3B) while keeping a clean test-set confirmation, and avoids
treating an inferential model as if it were a tuned predictor.

## 9. Player-clustered uncertainty plan

- **Primary:** mover-player cluster bootstrap. Resample `mover_player_hash` clusters
  with replacement, **rebuild the design matrix and refit** the model on each
  replicate, and collect the coefficient/contrast distribution → 95% percentile CIs.
- **Secondary:** game-clustered bootstrap (game_id); **row-level only as a reference
  lower bound**.
- **Two-way White×Black clustering remains deferred** (per 11.3B); for move-quality
  rows the mover is the decision-maker, so mover-player clustering is the natural
  primary unit and the deferral is less consequential here than for outcome models.

**Tooling gap:** `clustered_uncertainty.py` currently bootstraps a **mean**, a
**mean-difference**, and a **paired log-loss delta**, but has **no model-refit
bootstrap**. 15.1D must add a `cluster_bootstrap_refit(...)` that reuses the existing
`_cluster_index` helper to draw player clusters, then refits the sklearn estimator and
records named contrasts. Feasibility: ~12,900 mover clusters, ~62k rows/month, a small
design matrix — an OLS refit is milliseconds, so **500 replicates is feasible**
(use 200 for a documented first pass if runtime is tight). Seed convention: `seed=42`,
matching the codebase. Minimum cluster count guard: reuse the `<2` raise and `<30`
note already in `clustered_uncertainty.py`.

## 10. Model-family recommendation

| Option | Role in 15.1D |
|---|---|
| A — grouped adjusted means / post-stratified summaries | Useful cross-check; cannot adjust many covariates jointly → not primary |
| **B — OLS for mean ES loss + cluster bootstrap** | **Primary.** Transparent adjusted mean differences; inference from cluster bootstrap, not normal-theory SEs |
| **C — large-loss logistic (P(ES>0.05), P(ES>0.10))** | **Secondary/robustness.** Skew-robust, interpretable as adjusted mistake probability |
| D — two-part / hurdle | Deferred; only if mean vs large-loss models diverge |

**Implementation note:** use scikit-learn (`LinearRegression`, `LogisticRegression`)
with explicit one-hot design matrices built in Polars/NumPy; **do not add
statsmodels** (not installed) — uncertainty comes from the cluster bootstrap, so
analytic clustered SEs are unnecessary. This keeps the dependency surface unchanged.

## 11. Proposed 15.1D implementation scope

Build (tight scope):

- `src/chess_mhsuc/controlled_move_quality.py`:
  - target/filter utilities (non-mate base, train-only `rating_z` moments);
  - design-matrix builder (one-hot clock/checkpoint/eval_band/month/termination +
    `rating_z`), with explicit reference levels;
  - OLS adjusted-mean model (sklearn) returning named contrasts;
  - large-loss logistic models (sklearn) for ES>0.05 / ES>0.10;
  - `cluster_bootstrap_refit` over `mover_player_hash` for contrast CIs (reusing
    `clustered_uncertainty._cluster_index`);
  - per-month + pooled + test-confirmation runners;
  - markdown report generation;
  - CLI.
- `tests/test_controlled_move_quality.py`: design-matrix correctness, reference-level
  handling, deterministic bootstrap, contrast extraction, train-only scaling, a
  synthetic positive-control recovery test.

**Explicitly excluded:** sharpness, MultiPV, neural models, cross-time-control, any new
Stockfish runs, two-part model, statsmodels.

## 12. Proposed 15.1D report outputs

- `reports/controlled_move_quality_2024_09_250k_v1.md`
- `reports/controlled_move_quality_2024_10_250k_v1.md`
- `reports/controlled_move_quality_combined.md`
- `reports/phase_reports/phase_15_1d_controlled_move_quality_modeling.md`

Each must contain: input artifacts; model formulas; sample exclusions (mate-band, etc.);
target definitions; covariates and reference levels; coefficient/contrast tables with
mover-player-clustered 95% CIs; game-clustered CIs as secondary; month-by-month then
pooled; the **clock-effect interpretation** (expected null / confound-conditioned); the
**eval-band positive-control interpretation**; limitations; recommended next ticket.

## 13. Risks and caveats

- **Not causal.** Controlled adjustment is association, not a reasoning-degradation
  mechanism; no "degradation curve" language for ordered buckets.
- **White-to-move only** (even-ply checkpoints) — limits generality; document prominently.
- **Sparse low-clock cells** (`under_60` ≈750–800/month, confounded) — exploratory/
  descriptive-only; `60_180` is the stable low-clock contrast.
- **A clock null is likely** given 15.1B/11.3B; the model may simply confirm the null,
  which is a valid pre-registered outcome, not a failure.
- **Eval-band dominance may partly reflect chess-value geometry** (decided positions
  have little expected score left to lose) as much as human difficulty — interpret the
  positive control as structure, not as proof of differential human reasoning.
- **ES transform is train-fitted and approximate** (logistic, scale 348.4); large-loss
  logistic models hedge against its exact shape.
- **Player-clustered bootstrap handles repeated movers but not exact two-way
  (White×Black) dependence** (deferred).
- **Time-forfeit filtering induces survivor bias** (board-decided low-clock are a
  selected population); the termination binary is a covariate, not a fix.
- **Stockfish depth-12 eval is objective context, not absolute ground truth; DRAW
  remains sparse and not solved; sharpness is not implemented and not invoked.**

## 14. Roadmap / preregistration implications

PREREGISTRATION C4 already specifies expected-score loss (mover's perspective) as
primary with clipped cp secondary, prior-trajectory control for modeling, and the
non-monotonicity caution. This audit is consistent and adds operational specificity. A
small C4 clarification is warranted: lock the **primary controlled contrast** (clock
net of checkpoint/eval/rating/month/termination), the **eval-band positive control**,
**mover-player-clustered uncertainty**, **train+val estimation with test confirmation,
month as replication**, and that **a clock null is a pre-registered acceptable
outcome**. (Note: the audit's prior-trajectory control is not in the current artifacts
— next-move-loss rows carry no pre-checkpoint trajectory feature — so 15.1D's controls
are eval band + phase + rating + termination + month; a trajectory feature would be a
separate extraction ticket, flagged in §13/§15.)

## 15. Recommended next ticket

**15.1D — Controlled Move-Quality Modeling Implementation** (per §11–§12): sklearn OLS
adjusted-mean model + large-loss logistic robustness, mover-player cluster-bootstrap
contrasts, per-month + pooled + test confirmation, descriptive/inferential framing with
no causal language. Sharpness moderation (C3 / 15.2B) and any prior-trajectory feature
remain separate, later tickets.
