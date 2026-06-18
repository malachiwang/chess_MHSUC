# Phase 15.4B — CP / ES Constraint Atlas Visualization Implementation

**Labels:** IMPLEMENTATION | move-quality / Constraint Atlas (Phase 15.4)
**Date:** 2026-06-17
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION

## 1. Executive summary

Implemented the dense CP/ES Constraint Atlas designed in 15.4A. A new module
`dense_constraint_atlas.py` reads the two dense 10+0 artifacts (2024-09 + 2024-10)
**read-only** and renders **9 PNG figures + a markdown report** of next-move
move-quality loss across clock, rating, eval state, phase, think-time, and termination
channel — with **every headline figure shown for both months**. Headline metric:
**expected-score loss** (mover perspective); clipped centipawn loss is the secondary
skew-aware view. The full run reads 2,933,756 rows, filters to **2,778,772 headline
rows** (status OK, mate-band excluded), and completes in ~8 s (no Stockfish, no models).
33 tests added; full suite **1,815 passed**.

**Headline descriptive result (month-replicated):** the **marginal** ES-loss-by-clock
curve is mildly **U-shaped** — highest at 300+ s (0.0358 both months) and slightly
elevated at 0–5 s (≈0.034), lowest in the 60–180 s mid-range (≈0.0288). So *marginally*,
low clock does **not** show worse move quality (high-clock moves concentrate in complex
opening positions). **Eval state dominates** (ES mean by band: slight 0.044 > near_equal
0.033 ≈ clear 0.031 > decided 0.017 — a ~2.6× spread vs clock's ~1.25× non-monotone
spread), reproducing 15.1B/15.1D. These are **marginal, uncontrolled** curves; the
inferential statement remains the controlled C4 result (15.1D/15.1F: a *small* replicated
clock association **after** conditioning on eval/phase/rating/termination). Predictive/
descriptive only — **not causal**; Stockfish eval is objective context, not ground truth.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; `phase_15_4a_…` audit; the dense reports
(`dense_move_loss_2024_09/10_…md`, `phase_15_3c/15_3d`); `constraint_atlas.py` (15.1B
checkpoint atlas — confirmed it exists, not reused), `clustered_uncertainty.py`
(reused the game-clustered bootstrap concept), `dense_move_loss.py` (schema); existing
tests.

## 3. Files created

- `src/chess_mhsuc/dense_constraint_atlas.py` — new atlas module (pure bucket/aggregation/
  bootstrap helpers + matplotlib renderers + report writer + CLI).
- `tests/test_dense_constraint_atlas.py` — 18 tests.
- `reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md` — committed atlas report.
- `reports/phase_reports/phase_15_4b_cp_es_constraint_atlas_visualization_implementation.md` — this.
- `reports/figures/phase_15_4_constraint_atlas/` — 9 committable PNG figures (46–99 KB each).

## 4. Files modified

- `ROADMAP.md` — 15.4B marked complete; next → 15.5A.
- `EXPERIMENT_LOG.md` — added EXP-044.
- `PREREGISTRATION.md` — **unchanged**. `constraint_atlas.py` and `dense_move_loss.py`
  **unchanged** (deliberately, to avoid clobbering).

## 5. CLI command

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_constraint_atlas \
  --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --out-dir reports/figures/phase_15_4_constraint_atlas \
  --report reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md \
  --bootstrap 500 --seed 20240617
```

**Bootstrap = 500** game-clustered draws (fast per-cluster-sum implementation; whole run
~8 s). Read-only; not a Stockfish job.

## 6. Tests run

- `pytest tests/test_dense_constraint_atlas.py` → **18 passed**.
- Full suite `pytest` → **1,815 passed** (1,797 prior + 18), 3 pre-existing warnings.

Coverage: bucket helpers (clock seconds/coarse/fraction, rating 200-Elo, phase/move,
think-time), cell-status policy, schema validator (accept / reject usernames / reject
missing cols / reject non-600+0 / count-check), headline filter (mate-band excluded,
both colors kept), cell summary (median/p75/p90 + large-loss rates), game-clustered
bootstrap (bracketing + single-cluster NaN-CI), and an end-to-end CLI on a synthetic
parquet (9 figures + report manifest) + CLI refusal on missing columns.

## 7. Input validation

Both artifacts loaded (2,933,756 rows); schema validated: all required columns present;
**no raw-username columns**; `expected_score_loss` ∈ [0,1]; `cp_loss_clipped` ≥ 0; time
control uniformly 600+0 / 600 / 0 / rapid; **per-month row counts match 15.3C/15.3D**
(2024-09 1,496,890; 2024-10 1,436,866).

## 8. Filtering and denominator summary

- Headline rows = status OK ∧ ¬mate-band ∧ both colors = **2,778,772**.
- Mate-band excluded from headline (diagnostic only): **154,984** (5.3%).
- Anomalies flagged, not dropped: clock>600 116 (Sep) / 91 (Oct); negative think 133 / 125;
  missing clock 0 / 0.

## 9. Figures generated

Under `reports/figures/phase_15_4_constraint_atlas/`:

1. `fig_15_4_01_clock_vs_es_loss_by_month.png` — clock × ES loss, per month, game-clustered 95% CI.
2. `fig_15_4_02_clock_vs_clipped_cp_loss_by_month.png` — clock × clipped cp (median/p75/p90).
3. `fig_15_4_03_large_loss_probability_by_clock.png` — P(ES≥0.05), P(ES≥0.10) by clock, per month.
4. `fig_15_4_04_rating_clock_heatmap_es_loss.png` — rating × clock mean-ES heatmap (sparse <200 blank).
5. `fig_15_4_05_eval_band_clock_es_loss.png` — eval-band-conditioned clock curves.
6. `fig_15_4_06_phase_clock_es_loss.png` — move-number × coarse-clock curves.
7. `fig_15_4_07_think_time_es_loss.png` — think-time × ES loss, per month.
8. `fig_15_4_08_termination_channel_diagnostic.png` — board-decided vs time-forfeit clock curves.
9. `fig_15_4_09_month_replication_summary.png` — Sep vs Oct ES-by-clock bars.

## 10. Tables generated

In the atlas report: per-month row counts (vs expected); §5 full clock-bucket ES tables
(mean [95% CI], n, cell-status) for both months; §14 anomaly table; plus figure manifest.

## 11. Month replication result

Near-exact across months. ES-loss-by-clock (2024-09 / 2024-10): 0_5 0.0338/0.0340;
5_10 0.0306/0.0320; 10_30 0.0291/0.0297; 30_60 0.0296/0.0288; 60_180 0.0288/0.0287;
180_300 0.0304/0.0305; 300+ 0.0358/0.0358. The U-shape and the 300+ peak replicate in
both independent monthly samples.

## 12. Anomaly and sparse-cell diagnostics

All headline clock cells are `headline` (n≥1000). Sparse handling: heatmap cells with
n<200 are blanked; clock tables label cells sparse/marked/headline. Anomaly counts are
tiny (≤0.01% of rows) and flagged, never dropped.

## 13. Interpretation

- **Eval state dominates** next-move loss (slight 0.044 → decided 0.017; ~2.6× spread),
  reproducing the checkpoint 15.1B/15.1D finding on dense, both-color data.
- The **marginal** clock curve is U-shaped and is **not** "less clock → more loss": the
  300+ bucket (most clock) has the *highest* marginal loss because high-clock moves
  concentrate in complex opening/early-middlegame positions (confounded with phase and
  eval band). This is precisely why marginal curves are not the inferential statement.
- The controlled C4 result (15.1D/15.1F) — a **small** replicated clock association
  **after** conditioning on eval band, phase, rating, termination — is unchanged and is
  the inferential claim; the atlas visualizes the descriptive structure around it.
- Low-clock cells are a survivor population (board-decided games that did not flag);
  the termination-channel diagnostic (board-decided vs time-forfeit) is provided.
- Patterns replicate across 2024-09 and 2024-10.

## 14. Non-claims

Predictive/descriptive only; **not causal**. No "low clock causes blunders"; no "time
pressure causes worse reasoning"; Stockfish eval is objective context, not ground truth;
no human-obviousness modeling; no sharpness conditioning (Phase 15.5); no cross-time-
control (Phase 16); not a public/synthesis report; no model fitting/selection. **C4 and
C3c unchanged.** No thresholds or transforms changed; dense artifacts not modified.

## 15. Recommendation for next ticket

**15.4C — Controlled Dense Move-Quality Modeling Audit** (per ROADMAP's restored Phase
15.4 sequence): design the per-ply controlled model that reproduces the C4
small-clock-association result on the dense substrate, net of eval band / phase /
rating / termination, with mover-player clustering — turning these marginal atlas
curves into the controlled inferential statement. Sharpness enrichment (Phase 15.5)
follows. Not Phase 16 cross-time-control; not synthesis.
