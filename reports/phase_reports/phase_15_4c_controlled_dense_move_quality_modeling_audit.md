# Phase 15.4C — Controlled Dense Move-Quality Modeling Audit

**Labels:** AUDIT / DESIGN | report-only (no modeling code, no model fits, no figures, no data artifacts)
**Date:** 2026-06-17
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (design audit)

## 1. Executive summary

15.4B showed the **marginal** dense clock curves are confounded and U-shaped/
non-monotone — so raw clock plots cannot stand as simple (let alone causal) evidence.
This ticket (**15.4C, design-only**) specifies the **controlled dense per-ply
move-quality model** that 15.4D will implement: it estimates the **conditional
association** between clock state and next-move expected-score loss **after**
controlling for eval state, phase/move-number, rating, termination channel, month, and
mover color, with game-clustered uncertainty. The inferential target is a **conditional
association, not causality**. No modeling code was written, no models were fit, no
figures were generated, no data artifacts were created.

**Feasibility (confirmed read-only):** headline substrate is **2,778,772 rows** (status
OK, mate-band excluded), board-decided **2,387,377** / time-forfeit **391,395**;
**50,106 games**, **31,381 mover-player hashes** (both clustering levels feasible);
continuous-eval fields (`expected_score_before`, `eval_before_cp`) present with 0 nulls;
splits train 1.94M / val 414k / test 414k. **statsmodels is NOT installed** → 15.4D must
reuse the existing 15.1D/15.1F machinery (numpy `_ols_fit` + sklearn logistic +
`clustered_uncertainty.cluster_bootstrap_refit`), no new dependency. **Critical
power caveat:** the extreme-low-clock board-decided corner is sparse (under_10 ×
board-decided = **1,820 rows**, `slight` band only 72) → headline power lives at
`60_180` vs `over_180` and in continuous-clock, exactly as at the checkpoint level (15.1D).

## 2. Why controlled modeling is needed after the atlas

The atlas (15.4B) is **descriptive**: each raw clock curve mixes phase, eval state,
rating, termination, and survivor effects. The marginal ES-loss-by-clock curve is
U-shaped — *highest* at 300+ s (0.0358) because high-clock moves concentrate in complex
opening/early-middlegame positions, mildly elevated at 0–5 s (≈0.034), lowest at
60–180 s (≈0.0288). A U-shaped **marginal** curve does **not** contradict the earlier
controlled C4 result; it is exactly what a confounded marginal looks like. The dense
controlled model is needed to ask the conditional question: **net of eval/phase/rating/
termination/month, does clock retain a residual association with next-move loss at the
per-ply scale**, and does it replicate across months — turning the descriptive map into
a controlled (still associational) statement.

## 3. Existing evidence to preserve

- **15.1D (controlled checkpoint model):** target = next-move ES loss; eval state
  dominates; clock retains a **small replicated residual association** after controls
  (pooled `60_180` vs `over_180` ≈ +0.0034; `under_60` vs `over_180` ≈ +0.0072);
  ~5–8× smaller than the eval-band effect.
- **15.1F (robustness):** that association survives continuous within-band |cp| control,
  late-only, **board-decided-only**, rating specs, clipped-cp and large-loss targets,
  and game/White/Black clustering; per-month subsets occasionally touch 0 (low power),
  verdict rests on pooled + sign + replication.
- **15.4B (atlas):** eval state dominates (ES mean slight 0.044 → decided 0.017, ~2.6×
  spread); marginal clock curve U-shaped; month replication near-exact.

15.4C designs the model that tests whether the 15.1D/15.1F **small residual** persists
on the dense per-ply substrate.

## 4. Non-claims and interpretation boundaries

**Allowed language:** conditional association; residual predictive/descriptive signal;
controlled dense move-quality model; associational result. **Forbidden:** causal
time-pressure degradation; "low clock causes blunders"; reasoning-quality measurement;
Stockfish as ground truth; human-obviousness modeling; any sharpness result (Phase 15.5);
cross-time-control generalization (Phase 16); "the atlas already proves the clock effect";
"clock proves cognitive degradation"; "DRAW solved". A **null** clock association is a
pre-registered acceptable outcome (carried from 15.1C/C4).

## 5. Dense substrate and available fields

All present in both artifacts (0 nulls in the modeling fields). Exact names:

| Need | Field | Notes |
|---|---|---|
| month / game id / ply / move number | `month`, `game_id`, `ply`, `move_number` | |
| mover color | `mover_color` | |
| mover player hash | `mover_player_hash` | cluster key (31,381 unique) |
| rating | `mover_elo` | **mover rating** (use this, not game average) |
| clock | `clock_before_s`, `clock_fraction` | bucket or log1p |
| think time | `think_time_gross_s`, `think_time_net_s` | gross==net for 10+0 |
| eval band | `eval_band` | precomputed near_equal/slight/clear/decided/mate_band |
| continuous eval | `expected_score_before` (mover-POV ES), `eval_before_cp` (White-POV cp) | 0 nulls — continuous-eval robustness feasible |
| phase / move bucket | `phase`, `move_number` | |
| termination | `termination`, `is_time_forfeit`, `result_class` | row-level; board-decided = `~is_time_forfeit` |
| targets | `expected_score_loss`, `cp_loss_clipped`, `cp_loss_raw` | mover-perspective |
| mate-band | `is_mate_band` | excluded from headline |
| status | `status` | all `ok` |
| split | `split_set` | train/val/test/unknown |

No field is missing or uncertain for the planned model.

## 6. Target variables

- **PRIMARY: `expected_score_loss`** (bounded, outcome-relevant, handles cp
  nonlinearity). OLS adjusted-mean; coefficients read directly as ES-loss differences.
- **Secondary:** `cp_loss_clipped` (familiar metric); `I(expected_score_loss>=0.05)`,
  `I(expected_score_loss>=0.10)`, `I(cp_loss_clipped>=100)`, `I(cp_loss_clipped>=200)`
  (large-loss; LPM primary, logistic robustness).
- **Diagnostic only:** `cp_loss_raw` (signed/noisy; never headline).
- **Do not refit the ES transform** (reuse scale 348.4059).

## 7. Candidate predictors and controls

**Focal predictor — clock state.** Encodings to evaluate:
- coarse buckets `under_10 / 10_30 / 30_60 / 60_180 / over_180` (**primary**, ref `over_180`);
- 7 atlas seconds buckets (robustness/appendix);
- `log1p(clock_before_s)` continuous (powered robustness);
- `clock_fraction` buckets (secondary/future cross-TC);
- `under_60` / `under_30` / `under_10` indicators (robustness).

**Controls:** `eval_band` (or continuous eval, §14); `phase`/`move_number` (§12);
`mover_elo` bin or `rating_z` (§13); `month` fixed effect; `mover_color`;
`termination_channel`/`is_time_forfeit` (§11); optional `result_class`; anomaly flags;
`move_number` continuous (robustness). **No sharpness/MultiPV in 15.4D.**

## 8. Primary model specification

Interpretable linear adjusted-mean model on ES loss (numpy OLS via the 15.1D
`build_design`/`_ols_fit` pattern; explicit one-hot with fixed reference levels):

```
expected_score_loss
  ~ C(clock_coarse, ref=over_180)
  + C(eval_band, ref=decided)
  + C(phase_bucket)
  + C(rating_bin)         # 200-Elo, mover_elo
  + C(month, ref=2024_09)
  + C(mover_color, ref=white)
  + C(termination_channel, ref=board_decided)
  + intercept
```

**Focal contrasts:** `60_180` vs `over_180` (powered headline) and the finer
low-clock buckets vs `over_180` (monotone check), mirroring 15.1D. Coefficients are
expected-score-loss differences. Keep the primary model **additive** (no high-order
interactions). **Continuous-eval robustness model** (eval fully present):

```
expected_score_loss
  ~ C(clock_coarse) + binned_or_spline(expected_score_before)  # or abs(eval_before_cp)
  + C(phase_bucket) + C(rating_bin) + C(month) + C(mover_color) + C(termination_channel)
```

This tests that the clock residual is not an artifact of coarse eval-band binning
(the key 15.1F threat).

## 9. Secondary model specifications

- **S1 — clipped CP loss:** same RHS, target `cp_loss_clipped` (familiar units; skewed
  → report with median context).
- **S2 — large-loss probability:** `I(ES>=0.10)` (and `>=0.05`) via **LPM** (primary,
  interpretable) + sklearn **logistic** robustness appendix.
- **S3 — board-decided-only:** primary model on `~is_time_forfeit` rows (2,387,377;
  well-powered for coarse contrasts; under_10 corner sparse → exploratory).
- **S4 — anomaly-excluded:** drop `clock_before_s>600` and negative-think rows.
- **S5 — month-specific replication:** fit the primary model separately for 2024-09 and
  2024-10; compare clock-coefficient sign and scale.

## 10. Interaction tests (secondary, labeled)

Limited, pre-specified interactions (each its own secondary model, not in the primary):
`clock × eval_band`, `clock × phase_bucket`, `clock × rating_bin`,
`clock × termination_channel`. Purpose: locate where any clock residual concentrates
(late game? specific eval states? rating tier? flagging channel?). **No sharpness
interaction** (Phase 15.5). Interaction cells at the extreme low-clock end are sparse
(under_10 board-decided ≈ 1,820) → interaction estimates there are exploratory.

## 11. Termination-channel strategy

Row-level `is_time_forfeit` / `termination` exist (no join). Design:
- **Primary:** include `termination_channel` (board_decided ref vs time_forfeit) as a control.
- **Secondary S3:** board-decided-only restriction.
- **Diagnostic:** time-forfeit-only fit.

Interpretation rule: if the clock coefficient **shrinks strongly** once termination is
controlled / restricted to board-decided, report that the dense clock signal is
substantially the flagging channel (consistent with 11.2B). If it **persists**
board-decided-only, report it as a small **residual move-quality association** —
descriptive, not causal.

## 12. Phase / move-number strategy

Clock and late-game are entangled (late moves have less clock). **Primary:** `phase`
categorical (opening/middlegame/endgame) — or the 6-level move-number bucket from the
atlas. **Robustness:** `move_number` continuous / finer bins. Phase effects must not be
misattributed to clock.

## 13. Rating strategy

**Primary:** 200-Elo bins on **`mover_elo`** (the mover's rating, explicitly — not game
average; both white/black Elo exist but mover_elo is the correct field). **Robustness:**
`rating_z` (train-only standardization) or continuous `mover_elo`. Collapse `<1000` and
`≥2200` tails per the atlas cell-count finding.

## 14. Eval-state strategy

**Primary:** `eval_band` categorical (ref `decided`). **Robustness:** continuous
`expected_score_before` (mover-POV; 0 nulls) or `abs(eval_before_cp)`, binned or spline.
Rationale: eval state dominates loss (~2.6× spread, 15.4B), so it is the mandatory
control; the continuous version guards against within-band residual confounding (15.1F).

## 15. Think-time strategy

**Not in the primary model** — think-time is partly downstream of clock and position
complexity, so conditioning on it could block/distort the clock association (bad
control). **Secondary descriptive only:** `expected_score_loss ~ think_time_bucket +
controls`, with the caveat that think-time is not deliberation quality (lag/recording
artifacts; ~130/mo negative-think flagged).

## 16. Uncertainty and clustering strategy

Per-ply rows are **not independent** (clustered within game and within player). **Do not
use naive row-level SEs as headline.**
- **Primary:** **game-clustered** bootstrap (50,106 game clusters) — reuse
  `clustered_uncertainty.cluster_bootstrap_refit` + `summarize_contrasts`.
- **Robustness:** **mover-player-clustered** (31,381 clusters), if feasible.
- **Efficiency tactic (recommended for 15.4D):** because the row-reindex refit in the
  existing `cluster_bootstrap_refit` is O(n_rows × reps) and n_rows ≈ 2.78M, precompute
  **per-cluster sufficient statistics** (cluster XᵀX and Xᵀy), then each bootstrap
  replicate sums sampled clusters' small matrices and solves — O(n_clusters × reps × p²),
  fast. If that is not implemented, fall back to `--bootstrap 200` and/or fit on a
  selected column subset, and document the choice.

## 17. Train/validation/test and month-replication policy

Descriptive/associational modeling — **no test-set tuning, no model selection.**
- Fit the **pooled** model on **train+val** with a month fixed effect for the headline
  coefficients (mirrors 15.1D); **test = locked confirmation** fit reported once.
- Fit **month-specific** models for replication.
- `rating_z` (if used) standardized on **train only**.
- Key replication check: **same sign and similar scale** of the clock coefficients in
  2024-09 vs 2024-10 (and on the locked test split).

## 18. Computational feasibility

- Both artifacts load together at selected columns (~2.93M × ~15 cols) comfortably in
  memory (the 15.4B atlas already did the full read in ~8 s).
- **OLS is cheap:** with explicit one-hot (~25–40 columns), `XᵀX` is tiny; one pass over
  2.78M rows builds the normal equations — sub-second per fit. sklearn `LinearRegression`
  / numpy `_ols_fit` both fine; avoid pandas `get_dummies` explosions — build the design
  with the existing explicit-one-hot helper.
- **Bootstrap is the cost:** use the per-cluster sufficient-statistics approach (§16);
  500 game-clustered replicates over ~50k clusters × p² is fast. Naive row-reindex refit
  at 2.78M rows × 500 would be slow → either the sufficient-stat tactic or `--bootstrap 200`.
- LPM (linear) is as cheap as OLS; logistic (sklearn, no penalty) over 2.78M × ~30 cols
  is a minute-scale fit — acceptable as robustness, not in the bootstrap loop.
- Month-specific and board-decided fits are smaller and faster.

Recommend: load selected columns; build explicit one-hot design; pooled OLS/LPM first;
sufficient-statistics game-clustered bootstrap for the small focal coefficient set; log
runtime + memory.

## 19. Output tables and reports for 15.4D

Report: `reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md`.
Phase report: `reports/phase_reports/phase_15_4d_controlled_dense_move_quality_modeling_implementation.md`.
Tables (compact; no raw coefficient dumps): model-spec table; clock-bucket coefficient
table (estimate + game-clustered CI); month-specific clock coefficients; board-decided-only;
clipped-cp; large-loss (LPM/logistic); interaction summary; clustering/uncertainty table;
row/filter denominators; and a **side-by-side comparison to the 15.1D/15.1F checkpoint
controlled result**.

## 20. Robustness checks for 15.4D

R1 month-specific; R2 board-decided-only; R3 anomaly-excluded; R4 clipped-cp target;
R5 ES≥0.10 large-loss target; R6 continuous-eval (`expected_score_before`/`abs cp`)
control; R7 alternative clock encodings (7-bucket, log1p, under_60 indicator); R8 rating
continuous vs bins; R9 phase bucket vs move-number continuous; R10 game-clustered vs
mover-player-clustered uncertainty. Verdict rests on pooled estimate + sign + month
replication + board-decided survival (mirroring the 15.1F decision rule).

## 21. What 15.4D must not do

No sharpness joins; no MultiPV; no Phase 16 cross-time-control; no public synthesis /
packaging / outreach; no causal claims; no modification of dense artifacts; no ES-transform
refit; no threshold changes (unless explicitly justified + documented); no Stockfish reruns;
no test-set tuning/model-selection.

## 22. Recommended 15.4D implementation scope

**15.4D — Controlled Dense Move-Quality Modeling Implementation:** new module
`src/chess_mhsuc/dense_controlled_model.py` (reusing `controlled_move_quality.build_design`/
`_ols_fit`, sklearn logistic, and `clustered_uncertainty.cluster_bootstrap_refit`/
`summarize_contrasts`, plus the sufficient-statistics bootstrap tactic) + tests; fit the
primary ES-loss model + S1–S5 + the pre-specified interactions + R1–R10 robustness; write
the controlled-model report + phase report; update ROADMAP + EXPERIMENT_LOG; preserve data
safety (no data artifacts beyond the report; dense artifacts untouched). Proposed CLI:

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_controlled_model \
  --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --report reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md \
  --bootstrap 500 --seed 20240617
```

15.4D must **not** do Phase 15.5 sharpness or Phase 16 cross-time-control.

## 23. Open questions for Malachi (defaults in bold)

1. Primary model: **row-level OLS/LPM on ES loss with clustered uncertainty** (default)
   vs cell-level weighted model?
2. Clock encoding for primary coefficients: **coarse `under_10/10_30/30_60/60_180/over_180`**
   (default) with 7-bucket + log1p as robustness?
3. Uncertainty: **game-clustered primary, mover-player-clustered robustness** (default)?
4. Termination: **include termination control in primary + board-decided-only robustness**
   (default) vs board-decided-only as primary?
5. Think-time: **excluded from primary; secondary descriptive only** (default)?

## Non-claims (summary)

Design-only audit; no models, figures, data artifacts, or code produced. Target inference
is a **conditional association**, not causality; Stockfish eval is objective context, not
ground truth; no "low clock causes blunders" / "time pressure causes worse reasoning" /
human-obviousness / sharpness / cross-time-control / synthesis claims. **C4 and C3c
unchanged. PREREGISTRATION unchanged.**
