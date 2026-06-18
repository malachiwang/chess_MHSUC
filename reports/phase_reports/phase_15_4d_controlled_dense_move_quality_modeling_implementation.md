# Phase 15.4D — Controlled Dense Move-Quality Modeling Implementation

**Labels:** IMPLEMENTATION | move-quality / Constraint Atlas (Phase 15.4)
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION

## 1. Executive summary

Implemented the controlled dense per-ply move-quality model designed in 15.4C. A new
module `dense_controlled_model.py` reads the two dense 10+0 artifacts (2024-09 +
2024-10) **read-only**, fits a numpy-OLS adjusted-mean model of next-move
**expected-score loss** net of eval state, phase, mover rating, month, mover color, and
termination channel, with a fast **game-clustered sufficient-statistics bootstrap**
(500 draws) and a mover-player-clustered robustness pass. 16 tests added; full suite
**1,831 passed**. Full run: 2,778,772 headline rows, 50,106 game clusters, **~61 s**
(no Stockfish, no models beyond OLS/LPM + one logistic sign-check).

**Headline conditional-association result (predictive/descriptive, NOT causal):**
- Eval state **dominates** (positive control): vs `decided`, slight +0.0306, near_equal
  +0.0222, clear +0.0165 (all CI exclude 0) — ~3–30× the clock coefficients.
- A **clean monotone clock gradient** net of controls: vs `over_180`, under_10 +0.0083,
  10_30 +0.0045, 30_60 +0.0030, **60_180 +0.0009** — all small, positive, CI exclude 0,
  **replicated in both months** and under **mover-player clustering** (+0.0009).
- **Honest nuances:** the focal `60_180` contrast **attenuates to ~0 under continuous-eval
  control** (+0.0001, CI contains 0) and is **borderline board-decided-only** (+0.0004,
  CI contains 0); the more-constrained buckets (under_10/10_30/30_60) remain positive
  board-decided. The residual **concentrates** in `slight`-eval (+0.0025), middlegame
  (+0.0024), and the time-forfeit channel (+0.0011).
- **vs checkpoint (15.1D):** same sign, **~4× smaller** at 60_180 (dense +0.0009 vs
  checkpoint +0.0034). This **refines** rather than simply confirms the checkpoint result.

The atlas's U-shaped marginal (15.4B) remains a descriptive warning; this controlled
model is the inferential statement. Stockfish eval is objective context, not ground truth.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; the 15.4C audit; dense reports + atlas report
+ 15.3C/D/15.4B phase reports; `controlled_move_quality.py` (reused `build_design`/
`_ols_fit`/`_make_logistic_fit` patterns), `clock_association_robustness.py`,
`clustered_uncertainty.py` (reused `_cluster_index`, `summarize_contrasts`),
`dense_constraint_atlas.py` (reused bucket helpers), `dense_move_loss.py`; tests.

## 3. Files created

- `src/chess_mhsuc/dense_controlled_model.py` — controlled-model module.
- `tests/test_dense_controlled_model.py` — 16 tests.
- `reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md` — model report.
- `reports/phase_reports/phase_15_4d_controlled_dense_move_quality_modeling_implementation.md` — this.

## 4. Files modified

- `ROADMAP.md` — 15.4D marked complete; next → 15.5A.
- `EXPERIMENT_LOG.md` — added EXP-046.
- **Unchanged:** PREREGISTRATION, `dense_move_loss.py`, `dense_constraint_atlas.py`,
  `constraint_atlas.py`.

## 5. Code architecture

Pure functions + thin CLI: `load_dense` (selected columns), `validate_schema`,
`add_model_columns` (clock_coarse/rating_bin/move_bucket/termination_channel/anomaly
flags via reused atlas helpers), `filter_headline`, `build_design` (explicit one-hot,
fixed reference levels, intercept; **drops constant columns** so subgroup/anomaly-free
fits stay full-rank; rating bins|z, eval band|continuous modes), `ols_fit` (numpy
lstsq), **`ols_cluster_bootstrap`** (per-cluster XᵀX/Xᵀy sufficient statistics; each
replicate is a `bincount`-weighted sum + solve — fast, no row-resampling materialization),
`fit_ols_contrasts` (+`summarize_contrasts`), `logistic_sign_check` (single sklearn fit),
report writer, CLI. No notebook, no new dependency, no seaborn.

## 6. Tests run

- `pytest tests/test_dense_controlled_model.py` → **16 passed**.
- Full suite `pytest` → **1,831 passed** (1,815 prior + 16), 3 pre-existing warnings.

Coverage: validator (accept / reject usernames / reject missing cols / count-check),
headline filter (mate-band excluded, both colors), bucket derivation, design reference-
level omission, OLS recovers known coefficients, cluster bootstrap full==lstsq +
bracketing + <2-cluster raise, contrast extraction, large-loss target, board-decided/
month splits, end-to-end CLI, CLI refusal on missing columns.

## 7. CLI command

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_controlled_model \
  --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --report reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md \
  --bootstrap 500 --seed 20240617 --player-cluster
```

**Bootstrap = 500** game-clustered draws (sufficient-statistics implementation; whole
run ~61 s). The initial naive-gather bootstrap was replaced with a `bincount`-weighted
sum after it proved slow at 2.78M rows.

## 8. Input validation

Both artifacts loaded (2,933,756 rows); required columns present; **no raw-username
columns**; ES∈[0,1]; clipped cp≥0; both months and both colors present; per-month counts
match 15.3C/15.3D; player hashes present.

## 9. Filtering and denominator summary

Headline = status OK ∧ ¬mate-band ∧ both colors = **2,778,772** (mate-band excluded:
2024-09 80,577 / 2024-10 74,407). Board-decided headline 2,387,377; time-forfeit 391,395.
Anomalies (clock>600 ~100/mo, negative-think ~130/mo) flagged, included via anomaly
indicators in the primary design, excluded in S4.

## 10. Primary model result

`expected_score_loss ~ C(clock_coarse, ref=over_180) + C(eval_band, ref=decided) +
C(phase, ref=middlegame) + C(rating_bin, ref=1600_1799) + C(month, ref=2024_09) +
C(mover_color, ref=white) + C(termination_channel, ref=board_decided) + anomaly flags`.

| clock contrast (vs over_180) | estimate | 95% CI (game-clustered) |
|---|---|---|
| under_10 | +0.0083 | [+0.0068, +0.0101] * |
| 10_30 | +0.0045 | [+0.0034, +0.0056] * |
| 30_60 | +0.0030 | [+0.0022, +0.0039] * |
| **60_180 (focal)** | **+0.0009** | **[+0.0005, +0.0014] *** |

Monotone: more clock-constrained → higher conditional ES loss. All small (≤0.008).

## 11. Secondary and robustness results

| spec | 60_180 vs over_180 | note |
|---|---|---|
| Eval positive control | slight +0.0306*, near_equal +0.0222*, clear +0.0165* | dominates clock ~3–30× |
| Month 2024-09 / 2024-10 | +0.0010* / +0.0009* | replicated |
| Board-decided-only | +0.0004 [−0.0001,+0.0009] | **contains 0** (under_10/10_30/30_60 stay +*) |
| Clipped CP | +2.15 cp* (under_10 +16.2*) | monotone, significant |
| Large-loss ES≥0.10 (LPM) | +0.0058* | logistic sign agrees (+0.069) |
| Large-loss ES≥0.05 (LPM) | +0.0011 [−0.0013,+0.0033] | contains 0 |
| Continuous-eval control | +0.0001 [−0.0004,+0.0006] | **attenuates to ~0** |
| rating_z (continuous) | +0.0011* | robust |
| anomaly-excluded | +0.0009* | robust |
| mover-player-clustered | +0.0009 [+0.0005,+0.0013]* | robust |

## 12. Interaction results

Focal 60_180 vs over_180 within subgroups (exploratory localization): concentrates in
`slight` eval (+0.0025*) and middlegame (+0.0024*) and the time-forfeit channel
(+0.0011*); ~0 in clear/decided/near_equal eval, opening/endgame phase, and board-decided
(+0.0004, contains 0). No sharpness interaction (Phase 15.5).

## 13. Clustering and uncertainty

Game-clustered sufficient-statistics bootstrap (500 draws, 50,106 clusters) primary;
mover-player-clustered (31,381 clusters) robustness — both give 60_180 ≈ +0.0009 (CI
excludes 0). Naive row-level SEs not used.

## 14. Comparison to prior checkpoint result

Same sign and same qualitative structure as 15.1D/15.1F (eval dominates; small positive
clock residual; survives clustering) but the dense per-ply focal contrast is **~4×
smaller** (+0.0009 vs +0.0034) and is **more fragile** — it attenuates to ~0 under
continuous-eval control and is borderline board-decided-only, while the **steeper
low-clock buckets** (under_10/10_30/30_60) remain positive and board-decided-significant.
Reported honestly; not forced to match the checkpoint magnitude.

## 15. Runtime and feasibility

~61 s end-to-end (load + validate + ~14 OLS/LPM fits each with a 500-draw
sufficient-statistics bootstrap + 1 logistic + 9 interaction subgroup fits +
player-clustered pass). No Stockfish; no figures; no data artifacts. Sufficient-statistics
bootstrap was essential — the naive row-resampling refit was killed for slowness at
2.78M rows and replaced.

## 16. Non-claims

Conditional/predictive association only; **NOT causal**. No "low clock causes blunders";
no "time pressure causes worse reasoning"; no "clock proves cognitive degradation".
Stockfish eval is objective context, not ground truth. No human-obviousness modeling; no
sharpness (Phase 15.5); no cross-time-control (Phase 16); no synthesis. C4 and C3c
unchanged; ES transform not refit; dense artifacts not modified.

## 17. Recommendation for next ticket

**15.5A — Sharpness-Enriched Constraint Atlas Audit** (design joining the MultiPV
sharpness layer to the dense atlas/model — C3c move-quality-first). Not Phase 16; not
synthesis.
