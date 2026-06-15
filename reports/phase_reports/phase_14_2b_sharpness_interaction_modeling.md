# Phase 14.2B — Sharpness Interaction Modeling

**Labels:** IMPLEMENTATION / MODELING (Contrast C3c)
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Implemented and ran the pre-registered (14.2A §C3c) **clock × sharpness move-quality
moderation** model: does the controlled `60_180`-vs-`over_180` clock association with
next-move expected-score (ES) loss grow in objectively sharp / value-fragile positions?
**Result classification: UNDERPOWERED / NO CLAIM** — per the locked 14.2A kill criterion,
**not** a stretched finding. The pooled interaction is directionally positive
(+0.0102 [+0.0013, +0.0194], excl 0) and same-sign in both months, **but** (a) the limiting
**sharp × `60_180` cell falls to 297 / 282 per month** on the estimation split — below the
locked ≥300/month threshold; (b) the **2024-09** month-specific CI **contains zero**
(+0.0074 [−0.0079, +0.0217]); and (c) the **locked test confirmation is weak and
sign-flips** (pooled test +0.0012; 2024-09 +0.0054, 2024-10 −0.0035). No design changes were
made after seeing results. Predictive/descriptive moderation only — **not causal, not human
obviousness, no outcome/flagging claim.**

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/sharpness_interaction.py` | Join+validate (sharp recompute check), primary universe/filters, controlled interaction design (reuses `clock_association_robustness.build_variant_design` + adds sharp main + clock×sharp), `fit_interaction` (cluster-bootstrap), test confirmation, 12 robustness families, classification, month/combined reports, CLI (+`--smoke`) |
| `tests/test_sharpness_interaction.py` | 15 tests (recompute, filters, cell adequacy, design/interaction columns, DiD recovery, fit/bootstrap, classification, report ordering+non-claims, CLI) |
| `reports/sharpness_interaction_2024_09_250k_v1.md` | 2024-09 month report (13 sections) |
| `reports/sharpness_interaction_2024_10_250k_v1.md` | 2024-10 month report |
| `reports/sharpness_interaction_combined.md` | Combined report (15 sections) |
| `reports/phase_reports/phase_14_2b_sharpness_interaction_modeling.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 14.2B done; pointer → 14.2C (null/power interpretation) |
| `EXPERIMENT_LOG.md` | EXP-034 |
| `PREREGISTRATION.md` | post-result status note under §C3c (no design change) |

No edits to `controlled_move_quality.py` / `clock_association_robustness.py` /
`clustered_uncertainty.py` (imported, reused). No new dependencies. **No engine calls; no
re-extraction; existing artifacts not modified.**

## 4. Commands run

```bash
# smoke (mechanics; reports NOT written):
python -m chess_mhsuc.sharpness_interaction … --bootstrap-reps 10 --seed 42 --smoke
# final (locked 200 reps):
python -m chess_mhsuc.sharpness_interaction \
  --next-move-loss-09 … --sharpness-09 … --players-09 … (and -10) \
  --report-dir reports --bootstrap-reps 200 --seed 42
```
Final run ≈ 65 s. 200 reps used as pre-registered.

## 5. Tests run

- `tests/test_sharpness_interaction.py`: **15 passed**.
- Full suite: **1,744 passed** (was 1,729; +15), 0 regressions.

## 6. Input artifacts

`next_move_loss_{09,10}`, `multipv_sharpness_{09,10}`, `player_metadata_{09,10}` (all
gitignored). No artifact modified.

## 7. Join validation summary

Both months: sharpness artifact unique on `(game_id, selected_position_type)`; modeling
frame unique on the key; **inner join, no row multiplication; 100% coverage** of the
non-mate frame; **`sharp_value_fragility_v1` exact-recompute mismatches = 0** (validated
against `n_good_10es`/`worst_top5_loss_es`/`ctx_legal_move_count`). Mover-player hash present
for all rows.

## 8. Primary analysis implementation

OLS `expected_score_loss ~ C(clock,ref=over_180) + sharp + clock:sharp + C(checkpoint,
ref=move_10) + C(eval_band,ref=decided) + rating_z + [C(month,ref=2024_09) pooled] +
C(termination_binary,ref=board_decided)`. Primary estimand = `clock=60_180 × sharp`
interaction coefficient (DiD). Estimated on **train+val**; **test reserved** as locked
confirmation. Uncertainty = mover-player-clustered bootstrap (`cluster_bootstrap_refit` +
`summarize_contrasts`), 200 reps, seed 42; per month then pooled.

## 9. Cell adequacy summary

| scope | sharp × 60_180 (estimation) | under_60 × sharp |
|---|---|---|
| 2024-09 | **297** | 56 |
| 2024-10 | **282** | 49 |
| pooled | 579 | 105 |

The limiting per-month cell (297 / 282) is **below the locked ≥300/month threshold** — the
14.2A kill criterion. `under_60 × sharp` (~50/month) is exploratory only. (14.2A measured
348/329 on the full non-mate frame; reserving the test split lowers the estimation-set cell.)

## 10. Primary result summary

| scope | clock=60_180 × sharp (train+val, mover-clustered) |
|---|---|
| 2024-09 | +0.0074 [−0.0079, +0.0217] contains 0 |
| 2024-10 | +0.0131 [+0.0001, +0.0274] excl 0 |
| pooled | +0.0102 [+0.0013, +0.0194] excl 0 |

Same-sign both months. **Locked test confirmation:** pooled test +0.0012; 2024-09 +0.0054;
2024-10 **−0.0035** (sign flip). The test split does **not** confirm the train+val signal.

## 11. Robustness summary

Pooled decisive checks: continuous within-band cp control and board-decided-only both
recomputed; per-month tables (month reports) cover continuous-eval, board-decided-only,
rating bins/quadratic, sharp relaxed/strict, clipped-cp + large-loss logistic targets, and
game/White/Black clustering. Robustness is **not used to upgrade** the classification: with
the limiting cell <300/month, the 2024-09 CI containing zero, and a non-confirming test
split, the binding call is underpowered/no-claim regardless of which robustness cells look
positive.

## 12. Exploratory diagnostics summary

Surface-bait moderator computed per month as an **exploratory diagnostic only** (reported in
the month reports). **Explicitly NOT human obviousness; never a headline.** No claim is made
from it.

## 13. Classification under 14.2A criteria

**UNDERPOWERED / NO CLAIM.** The locked kill criterion fires (limiting sharp×60_180 cell
282 < 300/month). Independently, strong support also fails (2024-09 CI contains zero; test
confirmation weak/sign-flipped). This is **an absence of resolving power, not a null
finding**: the pooled/2024-10 point estimates are directionally positive, so a larger sample
(e.g. a third month, or a sharper-position-enriched design) could resolve it — but **no claim
is made now**, and the threshold was **not** moved to manufacture one.

## 14. Explicit non-claims

Not causal; no "time pressure causes worse moves/reasoning"; **no claim sharpness moderation
is shown** (it is not — underpowered); **no claim human obviousness has been modeled**; the
v1 feature is an engine-side proxy, not all of human difficulty; surface-bait is exploratory,
not obviousness, not a headline; no outcome/flagging (C3a/C3b) claim (not modeled here); no
"degradation curve"; Stockfish eval is objective context, not ground truth; DRAW not solved;
not a best-predictor claim.

## 15. Recommended next ticket

**14.2C — Null / Power Interpretation and Roadmap Reconciliation Audit.** Decide whether to
(a) accept the underpowered C3c result and consolidate the sharpness arc as "directionally
suggestive but underpowered at current sample," (b) enrich power (a third 10+0 month, or a
sharp-position-oversampled extraction) before a re-run, or (c) pivot to C3a/C3b outcome
sharpness — without moving the locked C3c thresholds. Prior-trajectory extraction remains an
optional follow-up.
