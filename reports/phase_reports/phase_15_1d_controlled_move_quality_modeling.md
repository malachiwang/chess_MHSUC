# Phase 15.1D — Controlled Move-Quality Modeling Implementation

**Labels:** IMPLEMENTATION / MODELING (Contrast C4)
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

Implemented the controlled C4 move-quality model (OLS adjusted-mean ES loss + mover-
player cluster bootstrap, large-loss logistic robustness) and ran it per month, pooled,
and on the locked test split. Two clean results:

- **Eval-band positive control (replicates, dominant):** adjusted ES loss is highest at
  slight (pooled **+0.0286** vs decided), then near_equal (**+0.0223**), then clear
  (**+0.0158**), all with mover-player-clustered CIs excluding zero in both months and
  on test. The model recovers the 15.1B descriptive structure.
- **Clock association (small but REPLICATED — not null):** after conditioning on
  checkpoint, eval band, rating, month, and termination, the `60_180`-vs-`over_180`
  contrast is **+0.0034 pooled [+0.0015, +0.0051]**, and `under_60`-vs-`over_180` is
  **+0.0072 [+0.0042, +0.0115]** — small, **monotone** (less clock → more loss), and
  **excluding zero in both months, pooled, and on the locked test split**.

This **refines rather than overturns** 15.1B. The descriptive marginal cells looked
flat because eval-band composition varies across clock cells; once eval band is
conditioned on (which 15.1A/15.1C required), a small ordered clock residual emerges. It
is **~5–8× smaller than the eval-band structure**, is a **predictive association, not
causal**, and termination (`time_forfeit` vs `board_decided`) is **~0 after controls**
(pooled −0.0003, contains zero) — consistent with the 11.2B reframing that flagging is
about the clock expiring, not systematically worse moves. Because the clock association
is non-null, the recommended next step is a **robustness audit** (15.1E), not immediate
consolidation. No causal language, no degradation-curve framing; Stockfish eval is
objective context, not ground truth.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/controlled_move_quality.py` | Modeling-frame builder, one-hot design (fixed reference levels), OLS + large-loss logistic fits, cluster-bootstrap contrast estimation, month/combined report renderers, CLI |
| `tests/test_controlled_move_quality.py` | 16 tests (design/reference levels, train-only `rating_z`, OLS recovery, bootstrap determinism/counts/guards, logistic, sample sizes, report privacy) |
| `reports/controlled_move_quality_2024_09_250k_v1.md` | 2024-09 month report (15 sections) |
| `reports/controlled_move_quality_2024_10_250k_v1.md` | 2024-10 month report |
| `reports/controlled_move_quality_combined.md` | Combined month + pooled report (14 sections) |
| `reports/phase_reports/phase_15_1d_controlled_move_quality_modeling.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `src/chess_mhsuc/clustered_uncertainty.py` | Added generic `cluster_bootstrap_refit` (refit a model per resampled-cluster replicate) + `summarize_contrasts` (percentile CIs for named coefficients) |
| `tests/test_clustered_uncertainty.py` | (unchanged — new bootstrap-refit tests live in `test_controlled_move_quality.py`, exercising the `clustered_uncertainty` functions) |
| `ROADMAP.md` | 15.1D done; pointer → 15.1E |
| `EXPERIMENT_LOG.md` | EXP-025 added |
| `PREREGISTRATION.md` | C4 result-status note (clock non-null small/replicated; eval-band positive control confirmed) |

No existing data artifacts modified. No new dependencies (sklearn already present;
**statsmodels not added**).

## 4. Implementation summary

`controlled_move_quality.py` reuses `constraint_atlas.load_atlas_frame` (validation +
eval_band/clock_coarse/board_decided derivation) and `player_metadata.join_mover_player`
(100% mover-hash coverage), filters to the non-mate modeling sample, and adds `month`,
`termination_binary`, and large-loss targets. The design matrix is an explicit one-hot
with an intercept column and fixed reference levels (clock=`over_180`,
checkpoint=`move_10`, eval=`decided`, termination=`board_decided`, month=`2024_09`);
`rating_z` is standardized on **train rows only**. OLS is `numpy.linalg.lstsq`
(deterministic); large-loss logistic is sklearn (`C=inf`, `fit_intercept=False`).
Uncertainty is the new `cluster_bootstrap_refit`, resampling `mover_player_hash`
clusters and refitting each replicate. Test rows are held out and refit only for
point-estimate confirmation.

## 5. Commands run

```bash
PYTHONPATH=src python -m chess_mhsuc.controlled_move_quality \
  --input data/processed/next_move_loss_2024_09_250k_v1.parquet \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --version-tag 2024_09_250k_v1 \
  --report reports/controlled_move_quality_2024_09_250k_v1.md --bootstrap-reps 200 --seed 42
PYTHONPATH=src python -m chess_mhsuc.controlled_move_quality \
  --input data/processed/next_move_loss_2024_10_250k_v1.parquet \
  --player-metadata data/processed/player_metadata_2024_10_250k_v1.parquet \
  --version-tag 2024_10_250k_v1 \
  --report reports/controlled_move_quality_2024_10_250k_v1.md --bootstrap-reps 200 --seed 42
PYTHONPATH=src python -m chess_mhsuc.controlled_move_quality --combined \
  --input <sep>.parquet --input <oct>.parquet \
  --player-metadata <sep_meta>.parquet --player-metadata <oct_meta>.parquet \
  --report reports/controlled_move_quality_combined.md --bootstrap-reps 200 --seed 42
```

**Bootstrap reps = 200** (the audit's first-pass setting); runtime ≈ 11 s per month, so
200 was comfortably feasible without lowering it. Seed = 42; **200/200 successful OLS
refits** in every run.

## 6. Tests run

- `tests/test_controlled_move_quality.py`: **16 passed**.
- `tests/test_clustered_uncertainty.py` + above: pass together.
- Full suite: **1,687 passed** (was 1,671; +16), 0 regressions.

## 7. Month-specific results

Adjusted ΔES loss [95% mover-player-clustered CI], estimation = train+val:

| Contrast | 2024-09 | 2024-10 |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0031 [+0.0003, +0.0057] ✗0 | +0.0038 [+0.0012, +0.0063] ✗0 |
| clock_under_60_vs_over_180 | +0.0080 [+0.0020, +0.0137] ✗0 | +0.0065 [+0.0020, +0.0124] ✗0 |
| eval_near_equal_vs_decided | +0.0221 [+0.0196, +0.0248] ✗0 | +0.0225 [+0.0202, +0.0251] ✗0 |
| eval_slight_vs_decided | +0.0280 [+0.0255, +0.0308] ✗0 | +0.0293 [+0.0268, +0.0318] ✗0 |
| eval_clear_vs_decided | +0.0158 [+0.0136, +0.0184] ✗0 | +0.0159 [+0.0138, +0.0182] ✗0 |
| termination_tf_vs_board_decided | −0.0009 [−0.0025, +0.0008] (0) | +0.0002 [−0.0015, +0.0018] (0) |

(✗0 = CI excludes zero; (0) = contains zero.) Every clock and eval contrast replicates
in sign and rough magnitude across the two disjoint months.

## 8. Pooled results

Pooled (month fixed effect; 103,391 estimation rows, 21,652 movers; 200/200 refits):

| Contrast | adjusted ΔES loss | 95% CI |
|---|---|---|
| clock_60_180_vs_over_180 | +0.0034 | [+0.0015, +0.0051] ✗0 |
| clock_under_60_vs_over_180 | +0.0072 | [+0.0042, +0.0115] ✗0 |
| eval_near_equal_vs_decided | +0.0223 | [+0.0205, +0.0239] ✗0 |
| eval_slight_vs_decided | +0.0286 | [+0.0270, +0.0302] ✗0 |
| eval_clear_vs_decided | +0.0158 | [+0.0143, +0.0173] ✗0 |
| termination_tf_vs_board_decided | −0.0003 | [−0.0015, +0.0008] (0) |

## 9. Robustness checks

- **Large-loss logistic (pooled, log-odds):** ES>0.05 — clock_60_180 +0.088
  [+0.021, +0.160] ✗0, eval_slight +1.72 [+1.62, +1.83] ✗0; ES>0.10 — clock_60_180
  +0.141 [+0.008, +0.249] ✗0, eval_slight +1.81 [+1.66, +1.99] ✗0. Signs **agree with
  OLS**: lower clock and harder eval bands raise the probability of a sizeable mistake,
  with eval-band effects far larger. (Log-odds read for sign agreement, not as
  calibrated odds ratios.)
- **Locked test confirmation:** pooled test contrasts match train+val closely —
  clock_60_180 test +0.0045 (vs +0.0034), under_60 +0.0073 (vs +0.0072), eval_slight
  +0.0297 (vs +0.0286). The clock and eval signals hold on the untouched test split.

## 10. Interpretation for C4

- **Eval state is the robust, dominant move-quality structure**, replicated and
  confirmed on test — the controlled answer to C4's board-play-quality question.
- **A small clock association survives controls and replicates** (monotone:
  `under_60` > `60_180` > 0 vs `over_180`), but is an order of magnitude smaller than
  eval band. This is a refinement of 15.1B's descriptive null, attributable to
  conditioning on eval band (which is correlated with clock/phase). **Not causal; not a
  reasoning-degradation claim.**
- **Termination is null after controls** (time_forfeit ≈ board_decided), consistent with
  11.2B: the outcome-level clock residual was the flagging channel (clock expiry), and
  at the move level — once clock/eval/etc. are held fixed — time-forfeit games do not
  show systematically worse moves.
- Net: C4 supports eval-state structure strongly and a small, replicated clock
  association weakly; both must be read as predictive associations.

## 11. Limitations and caveats

- Predictive/descriptive association only — not causal; no "degradation curve" language;
  no claim that time pressure causes worse reasoning.
- White-to-move only (even-ply checkpoints).
- `under_60` is sparse and confounded with late checkpoints; its contrast, though it
  excludes zero, is the least stable and is treated cautiously.
- Eval band is coarse (4 levels); the small clock residual could partly reflect
  within-band eval variation not captured by the bands — a target for 15.1E (continuous
  `mover_pre_cp`).
- ES transform is train-fitted/approximate; the large-loss logistic models hedge the
  shape. Mover-player clustering ≠ exact two-way (White×Black) dependence (deferred).
- Prior-trajectory control is **deferred** (no such feature in the artifacts), so the
  "clock as symptom of past struggle" confound is an explicit, unadjusted limitation.
- Stockfish depth-12 eval is objective context, not absolute ground truth; DRAW remains
  sparse; sharpness is not implemented or invoked.

## 12. Recommended next ticket

**15.1E — Clock Association Robustness Audit.** The controlled clock contrast is small
but replicates and excludes zero (and survives test confirmation), so before
consolidating the C4 claim it should be stress-tested: continuous `mover_pre_cp` instead
of 4 eval bands, residual clock×checkpoint confounding, rating non-linearity, the sparse
`under_60` cell, and two-way (White×Black) player dependence. C4 consolidation (15.1B +
11.3B + 15.1D) folds in afterward; sharpness moderation (C3 / 15.2A) remains a separate
later arc.
