# Phase 15.1F — Clock Association Robustness Implementation

**Labels:** IMPLEMENTATION / MODELING (Contrast C4)
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

Stress-tested the small 15.1D controlled clock association (`60_180` vs `over_180`,
pooled +0.0034) against the 15.1E mandatory checks, applying the 15.1E-locked criteria.
**Conclusion: SURVIVES.** The pooled clock contrast holds at **+0.0034 [+0.0015, +0.0052]**
and is **not eliminated by continuous within-band cp control** (+0.0034 [+0.0015, +0.0052]
— the key coarse-band threat), **survives board-decided-only** (+0.0034 [+0.0010, +0.0063]
— isolated from flagging), and is stable under rating-bin/quadratic specs, late-only,
all three metrics (directional), and game/White/Black clustering. It replicates in both
months and on the locked test split (15.1D). It remains **small and secondary to the
eval-band structure** (15.1D eval contrasts ~5–8× larger) and is **predictive/descriptive,
not causal** — not a degradation curve, no reasoning-degradation claim.

Honest nuance: in lower-power subsets some *per-month* CIs touch/cross zero (late-only
2024-09; board-decided-only 2024-10; game-cluster 2024-09), as expected for a ~+0.003
effect — but the **pooled** estimate excludes zero and the sign is consistently positive
across months and checks, which is what the locked criteria require.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/clock_association_robustness.py` | Configurable variant design builder, variant fit (OLS/logistic) with chosen cluster key, the 15.1E mandatory-check specs, verdict logic, robustness-matrix renderer, month/combined reports, CLI |
| `tests/test_clock_association_robustness.py` | 18 tests (moments/scaling, variant designs, filters, baseline-design-matches-15.1D, baseline-contrast reproduction, verdict logic, overall-conclusion gate, report privacy) |
| `reports/clock_association_robustness_2024_09_250k_v1.md` | 2024-09 month report |
| `reports/clock_association_robustness_2024_10_250k_v1.md` | 2024-10 month report |
| `reports/clock_association_robustness_combined.md` | Combined (months + pooled + verdict) |
| `reports/phase_reports/phase_15_1f_clock_association_robustness.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 15.1F done; pointer → 15.1G |
| `EXPERIMENT_LOG.md` | EXP-027 added |
| `PREREGISTRATION.md` | C4 robustness result-status note (clock survives) |

**No modifications to `controlled_move_quality.py` or `clustered_uncertainty.py`** — their
public helpers (`build_model_frame`, `build_design`, `train_rating_moments`, `_ols_fit`,
`_make_logistic_fit`, `cluster_bootstrap_refit`, `summarize_contrasts`) and reference-level
constants were imported and reused unchanged, so the 15.1D/11.3B tests are untouched. No
new dependencies; no data artifacts written.

## 4. Implementation summary

`clock_association_robustness.py` reuses the 15.1D modeling layer and adds a configurable
`build_variant_design` (clock/checkpoint/eval one-hot with the 15.1D reference levels;
adaptive checkpoint reference so late-only carries no all-zero column; optional
standardized within-band `abs_cp_z`; rating linear/quadratic/train-quantile-bins;
optional month/termination). `fit_variant` builds the design, fits OLS or logistic, and
cluster-bootstraps the clock contrasts via `cluster_bootstrap_refit`. A fixed list of
mandatory check specs is run on 2024-09, 2024-10, and pooled; `verdict_for_contrast` and
`overall_conclusion` apply the locked 15.1E gate. A baseline-design test asserts the
variant builder reproduces `controlled_move_quality.build_design` exactly.

## 5. Commands run

50-rep smoke (2024-09, ~6 s) confirmed wiring; final runs at **200 reps, seed 42**:

```bash
PYTHONPATH=src python -m chess_mhsuc.clock_association_robustness \
  --input data/processed/next_move_loss_2024_09_250k_v1.parquet \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --version-tag 2024_09_250k_v1 \
  --report reports/clock_association_robustness_2024_09_250k_v1.md --bootstrap-reps 200 --seed 42
# 2024_10 analogous
PYTHONPATH=src python -m chess_mhsuc.clock_association_robustness --combined \
  --input <sep>.parquet --input <oct>.parquet \
  --player-metadata <sep_meta>.parquet --player-metadata <oct_meta>.parquet \
  --report reports/clock_association_robustness_combined.md --bootstrap-reps 200 --seed 42
```

Combined run ≈ 82 s (12 checks × 3 scopes; OLS + logistic refits). 200 reps used
throughout (not reduced).

## 6. Tests run

- `tests/test_clock_association_robustness.py`: **18 passed**.
- Full suite: **1,705 passed** (was 1,687; +18), 0 regressions.

## 7. Baseline replication

Pooled baseline clock contrast **+0.0034 [+0.0015, +0.0051]** reproduces 15.1D exactly
(`60_180` vs `over_180`); per month +0.0031 / +0.0038, both excluding zero. A unit test
also confirms the variant design matrix equals `controlled_move_quality.build_design` for
the baseline spec.

## 8. Robustness matrix summary

Primary contrast `60_180` vs `over_180` (mover-player-clustered unless noted), pooled:

| Check | pooled estimate | 95% CI | verdict |
|---|---|---|---|
| baseline (15.1D) | +0.0034 | [+0.0015, +0.0051] | survives |
| continuous eval control | +0.0034 | [+0.0015, +0.0052] | survives |
| late-only (move_30+40) | +0.0033 | [+0.0009, +0.0053] | survives |
| board-decided-only | +0.0034 | [+0.0010, +0.0063] | survives |
| rating quantile bins | +0.0032 | [+0.0012, +0.0049] | survives |
| rating quadratic | +0.0033 | [+0.0013, +0.0050] | survives |
| metric: clipped_cp_loss | +6.09 | [+2.84, +9.18] | survives (dir.) |
| metric: logistic ES>0.05 | +0.088 | [+0.021, +0.160] | survives (dir.) |
| metric: logistic ES>0.10 | +0.141 | [+0.008, +0.249] | survives (dir.) |
| cluster: game_id | +0.0034 | [+0.0012, +0.0057] | survives |
| cluster: White-player | +0.0034 | [+0.0015, +0.0051] | survives |
| cluster: Black-player | +0.0034 | [+0.0010, +0.0055] | survives |

`under_60` (secondary/exploratory) is positive and usually excludes zero in the full
models but **contains zero in board-decided-only** (+0.0045 [−0.0013, +0.0109]) — expected,
since `under_60` is ~2/3 time-forfeit (15.1E) and the board-decided subset is sparse.

## 9. Interpretation under 15.1E criteria

All locked "survives" conditions hold:
- positive in **both months** (baseline +0.0031 / +0.0038);
- **pooled CI excludes zero** (+0.0034 [+0.0015, +0.0052]);
- **not materially eliminated** by continuous within-band cp control (estimate unchanged);
- **board-decided-only same (positive) sign** with pooled CI excluding zero;
- **metric direction agrees** (clipped cp and both large-loss logistics positive, pooled CIs exclude zero).

→ The C4 clock association is credited as a **small, replicated, controlled, secondary**
association between lower clock and higher next-move ES loss. It is descriptive/predictive,
**not causal**, and an order of magnitude smaller than the eval-band structure.

## 10. Limitations and caveats

- Not causal; no "degradation curve" language; no claim that time pressure causes worse
  reasoning. The association is small and secondary to eval band.
- Board-decided move-quality association is distinct from flagging risk; reported separately.
- `under_60` is sparse and ~2/3 time-forfeit → exploratory; the headline is `60_180`.
- Some per-month subset CIs touch zero (low power for a ~+0.003 effect); the verdict rests
  on pooled estimates + consistent sign, per the locked criteria.
- Prior-trajectory control is deferred (absent from artifacts) — the "clock as symptom of
  past struggle" confound is unadjusted and stated. This is the main remaining alternative
  explanation and is flagged for possible future extraction.
- Mover-player clustering ≠ exact two-way (White×Black) dependence (deferred); White/Black
  one-way clustering both leave the contrast excluding zero.
- ES transform is train-fitted/approximate; clipped-cp and large-loss metrics agree in
  direction. White-to-move only (even-ply checkpoints).
- Stockfish depth-12 eval is objective context, not absolute ground truth; DRAW remains
  sparse; sharpness not implemented or invoked.

## 11. Recommended next ticket

**15.1G — C4 Claim Consolidation / Move-Quality Arc Summary.** Consolidate the descriptive
(15.1B), clustered (11.3B), controlled (15.1D), and robustness (15.1F) results into the C4
claim: **eval-band structure is the dominant, robust move-quality structure; a small,
replicated, controlled clock association survives robustness and stands as a secondary,
non-causal finding; the outcome-level clock signal remains substantially the flagging
channel (11.2B).** A prior-trajectory feature-extraction ticket is the main candidate
follow-up if the residual clock confound is to be probed further. Sharpness moderation
(C3 / 15.2A) remains a separate later arc.
