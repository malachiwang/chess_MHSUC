# Phase 15.5B — Existing-Sharpness Checkpoint-Overlap Join + Atlas / Exploratory Model

**Labels:** IMPLEMENTATION | sharpness / Constraint Atlas (Phase 15.5)
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION

## 1. Executive summary

Implemented the 15.5A design: a **checkpoint-overlap, White-mover-only** sharpness-
enriched atlas + exploratory `clock × sharpness` model over the dense substrate, using the
**existing** MultiPV sharpness artifacts (no Stockfish/MultiPV run). A new module
`sharpness_enriched_atlas.py` joins on the corrected key `dense.ply = checkpoint_ply + 1`,
validates White-mover coverage, renders 6 PNG figures, and fits a game-clustered model. 14
tests added; full suite **1,845 passed**. Run: 126,239 matched rows → 121,165 headline
(4.36% of dense headline, White-mover only), sharp rate 0.1414, **~7 s**.

**Results (predictive/descriptive, NOT causal; sharpness = objective value fragility):**
- **Sharp main effect (net of controls, at over_180): +0.0214 [+0.0198, +0.0231]**,
  replicated (Sep +0.0213, Oct +0.0215). Value-fragile positions carry materially higher
  next-move ES loss — but this is **partly mechanical** (the flag is defined via
  `worst_top5_loss_es ≥ 0.10`, so sharp positions have a worse achievable downside by
  construction), so it is a descriptive localization, not a behavioral surprise.
- **Focal `clock 60_180 × sharp` interaction: +0.0104 [+0.0018, +0.0194] pooled** — but
  **both per-month CIs contain 0** (Sep +0.0095 [−0.0024, +0.0236]; Oct +0.0113
  [−0.0008, +0.0232]) and **board-decided-only contains 0** (+0.0056 [−0.0046, +0.0155]).
  The lower-clock × sharp cells are sparse (<200) → no-claim. **This is EXPLORATORY and
  does not cleanly replicate.**
- **C3c status is UNCHANGED: not confirmed, not disproven.** The pooled directional-positive
  interaction (~+0.010) matches the original Phase 14 C3c train+val pooled value, and remains
  underpowered/month-fragile — the same corner that left C3c unresolved.

Stockfish/MultiPV is objective value context, not ground truth; this is **not** a dense-wide
sharpness analysis.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; the 15.5A audit; dense atlas + controlled-model
reports + 15.4B/D phase reports; Phase 14 sharpness/C3c reports; `multipv_sharpness.py`,
`sharpness_interaction.py`, `dense_controlled_model.py`, `dense_constraint_atlas.py`,
`dense_move_loss.py`; tests.

## 3. Files created

- `src/chess_mhsuc/sharpness_enriched_atlas.py` — checkpoint-overlap join + atlas + model.
- `tests/test_sharpness_enriched_atlas.py` — 14 tests.
- `reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md` — report.
- `reports/phase_reports/phase_15_5b_existing_sharpness_checkpoint_overlap_implementation.md` — this.
- `reports/figures/phase_15_5_sharpness_enriched_atlas/` — 6 PNG figures.

## 4. Files modified

- `ROADMAP.md`; `EXPERIMENT_LOG.md`.
- **Unchanged:** PREREGISTRATION, `dense_move_loss.py`, `dense_controlled_model.py`,
  `dense_constraint_atlas.py`, `multipv_sharpness.py`.

## 5. Code architecture

Pure functions + CLI: selected-column dense/sharpness loaders, `validate_dense`/
`validate_sharpness` (incl. White-only side_to_move assert), `join_checkpoint_overlap`
(`ply = checkpoint_ply + 1`), `validate_join` (asserts White-mover only — rejects the
wrong equal-ply join), `add_columns` (clock/rating buckets via reused atlas helpers,
termination channel, anomaly flags, sharp label), `filter_headline`, `sharp_clock_cells`,
`build_design` (clock + sharp + clock×sharp + eval + phase + rating + month + termination +
anomaly; **mover_color omitted — constant White**; constant columns dropped), `fit_model`
(reuses `dense_controlled_model.ols_cluster_bootstrap` + `summarize_contrasts`), 6
matplotlib (Agg) renderers, report writer. No new dependency, no notebook, no seaborn.

## 6. Tests run

- `pytest tests/test_sharpness_enriched_atlas.py` → **14 passed**.
- Full suite → **1,845 passed** (1,831 prior + 14).

Coverage includes: dense/sharpness validators, **corrected-join White-only** + the
**wrong equal-ply join trap** (matches Black, rejected), headline filter, buckets/cells,
sparse-cell policy, design omits mover_color + has interaction, model contrast extraction,
end-to-end CLI (6 figures + checkpoint-overlap/White-mover labels), CLI refusal on missing
columns.

## 7. CLI command

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.sharpness_enriched_atlas \
  --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --sharpness-month data/processed/multipv_sharpness_2024_09_250k_v1.parquet \
  --sharpness-month data/processed/multipv_sharpness_2024_10_250k_v1.parquet \
  --out-dir reports/figures/phase_15_5_sharpness_enriched_atlas \
  --report reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md \
  --bootstrap 500 --seed 20240617
```
Bootstrap = 500 game-clustered draws; ~7 s (no Stockfish/MultiPV).

## 8. Input validation

Dense: 2,933,756 rows, both months, no usernames, ES∈[0,1], clipped cp≥0, both colors.
Sharpness: ~126k rows, `checkpoint_ply ∈ {20,40,60,80}`, **side_to_move = white only**,
no usernames.

## 9. Join validation

Corrected key `dense.ply = checkpoint_ply + 1`; matched **126,239 rows, White-mover only**
(validator asserts; the wrong `ply == checkpoint_ply` join — which matches Black — is
rejected). Per month: 2024-09 ~64,317, 2024-10 ~61,922 matched (pre-headline).

## 10. Coverage and denominator summary

Headline matched (status OK ∧ ¬mate-band) = **121,165** = **4.36%** of dense headline
(2024-09 4.36%, 2024-10 4.36%); White-mover only; checkpoint-overlap only (4 plies/game).
Matched by clock: over_180 114,428; 60_180 5,181; 30_60 938; 10_30 439; under_10 179.
Sharp rate 0.1414.

## 11. Figures generated

Under `reports/figures/phase_15_5_sharpness_enriched_atlas/` (6 PNGs, all labelled
"checkpoint-overlap, White-mover only"): `fig_15_5_01_sharp_vs_nonsharp_es_loss_by_clock`,
`_02_sharp_vs_nonsharp_clipped_cp_by_clock`, `_03_large_loss_probability_clock_sharpness`,
`_04_eval_band_sharpness_es_loss`, `_05_rating_sharpness_es_loss`,
`_06_month_replication_summary`.

## 12. Exploratory model result

`expected_score_loss ~ clock(ref over_180) + sharp + clock×sharp + eval(ref decided) +
phase + rating_bin + month + termination + anomaly` (mover_color omitted). 121,165 rows;
47,502 game clusters; 498/500 refits.

| contrast | estimate | 95% CI (game-clustered) | read |
|---|---|---|---|
| sharp main effect (at over_180) | +0.0214 | [+0.0198, +0.0231] * | strong, replicated (partly mechanical) |
| clock 60_180 (non-sharp) | +0.0010 | [−0.0006, +0.0028] | consistent w/ 15.4D small base |
| **clock 60_180 × sharp (focal)** | **+0.0104** | **[+0.0018, +0.0194] *** | **EXPLORATORY (month CIs contain 0)** |
| clock 30_60 × sharp | +0.0002 | [−0.0198, +0.0195] | sparse, no-claim |
| clock 10_30 × sharp | +0.0410 | [−0.0008, +0.0869] | sparse, no-claim |
| clock under_10 × sharp | +0.0352 | [−0.0346, +0.1120] | sparse, no-claim |

Board-decided-only focal interaction: **+0.0056 [−0.0046, +0.0155] (contains 0).**

## 13. Month replication

| contrast | 2024-09 | 2024-10 |
|---|---|---|
| sharp main effect (at over_180) | +0.0213 [+0.0189, +0.0235] * | +0.0215 [+0.0193, +0.0239] * |
| clock 60_180 × sharp (focal) | +0.0095 [−0.0024, +0.0236] | +0.0113 [−0.0008, +0.0232] |

The sharp **main effect replicates** cleanly; the **focal interaction does NOT** — both
per-month CIs contain 0. Replication is **not claimed** for the interaction.

## 14. Sparse-cell and power diagnostics

`sharp × 60_180` = 675 (exploratory); `sharp × 30_60` 113, `× 10_30` 49, `× under_10` 17
(all sparse, <200, no-claim); `sharp × over_180` 16,275 (headline). The sharp × low-clock
corner is underpowered — the **same** limitation that left C3c unresolved; the dense
substrate does not fix it because sharpness coverage is checkpoint-limited and White-only.

## 15. Comparison to prior C3c

Phase 14 C3c (`60_180 × sharp_value_fragility_v1`, checkpoint level): train+val pooled
~+0.010 directional positive, test near zero, key cells underpowered → not confirmed, not
disproven. This 15.5B checkpoint-overlap exploratory interaction (+0.0104 pooled; month
CIs contain 0; board-decided contains 0) is **consistent in magnitude and in its
underpowered/month-fragile character**. **C3c status is unchanged.**

## 16. Interpretation

- Coverage is checkpoint-overlap, White-mover only (~4.4%); **not dense-wide**.
- **Sharp main effect** is descriptive, substantial, and replicated — but partly mechanical
  (the flag embeds a downside-loss threshold), so it is localization, not a behavioral claim.
- The **clock × sharpness moderation** — the actual C3c question — is pooled-positive but
  **month-fragile and board-decided-fragile → exploratory/no-claim**; it does not resolve C3c.
- To power the interaction one would need a **stratified dense sharpness extraction** (both
  colors, more low-clock sharp cells) — a separate ticket (deferred, 15.5A Option C).
- Future diagnostic (NOT this ticket): a **Think-Time Loss-Rate / Flagging Signature
  Diagnostic** (cp/ES loss per unit think-time, board-decided vs time-forfeit) — a possible
  later ticket.

## 17. Non-claims

Predictive/descriptive, NOT causal. No "sharp positions cause blunders"; no "low clock
causes blunders"; no "time pressure causes worse reasoning". Sharpness = objective value
fragility, **not** human obviousness/difficulty; MultiPV/Stockfish not ground truth.
Checkpoint-overlap, White-mover only — **NOT a dense-wide sharpness analysis**. C3c not
confirmed, not disproven. C4 and C3c unchanged; no threshold/ES-transform change; artifacts
not modified.

## 18. Recommendation for next ticket

**15.5C — Sharpness Result Consolidation / C3c Claim Update** (consolidate this
checkpoint-overlap result; keep C3c as not-confirmed/not-disproven; decide whether a
stratified dense sharpness extraction is warranted to power the interaction). Not Phase 16;
not synthesis.
