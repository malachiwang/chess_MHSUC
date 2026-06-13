# Phase 15.0C — Full Next-Move Loss Extraction + Expected-Score Transform

**Labels:** ANALYSIS/ML | IMPLEMENTATION (full execution)
**Date:** 2026-06-13
**Owner:** Malachi Wang

## 1. Executive summary

Ran the full both-months next-move loss extraction and added a train-fit cp→expected-score
transform. **126,239 checkpoint moves evaluated end-to-end across both months with 0
reconstruction failures, 0 engine failures, 0 FEN-hash mismatches.** Expected-score loss
(the intended C4 headline metric) is now available alongside the cp-based metrics; the two
months agree closely (median clipped cp loss 19 both; ES median ~0.010 both). A depth-13
parity check confirms the depth-12 convention is benign in aggregate (0.2cp shift). The
measurement layer is ready for the Constraint Atlas (15.1A). Descriptive measurement only
— not causal, no degradation-curve language.

## 2. Files created

| File | Content |
|---|---|
| `reports/next_move_loss_2024_09_250k_v1.md` | 2024-09 full extraction report (16 sections) |
| `reports/next_move_loss_2024_10_250k_v1.md` | 2024-10 full extraction report |
| `reports/next_move_loss_combined.md` | Combined two-month report |
| `reports/phase_reports/phase_15_0c_full_next_move_loss_extraction.md` | This report |

Generated (gitignored, not staged): `data/processed/next_move_loss_2024_09_250k_v1.parquet`,
`data/processed/next_move_loss_2024_10_250k_v1.parquet`,
`data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json`.

## 3. Files modified

| File | Change |
|---|---|
| `src/chess_mhsuc/next_move_loss.py` | Added expected-score transform (`expected_score`, `expected_score_loss`, `fit_expected_score_transform`), ES columns in schema + `build_row`/`run_extraction`, `load_fit_rows`, `depth_parity_check`, CLI modes `--fit-es-transform` / `--parity-check` / `--es-transform`, ES in summaries/report |
| `tests/test_next_move_loss.py` | +15 tests (ES transform, fit, build_row ES) — 56 total |
| `ROADMAP.md` | 15.0C done; pointer → 15.1A |
| `EXPERIMENT_LOG.md` | EXP-019 added |

`stockfish_eval.py` reused via import, unmodified. No PREREGISTRATION change needed (C4
already specified expected-score loss; this ticket realizes it on the cp scale + ES).

## 4. Expected-score transform implementation

Logistic `ES(cp) = 1/(1 + exp(−cp_clipped/scale))`, cp clipped ±1000 (mate sentinels fold
to the cap), one parameter fit by bounded MSE (scipy) to White expected score
(win=1/draw=0.5/loss=0). **Fit on 89,764 pooled TRAIN rows from both months
(scale=348.4, MSE 0.183)** — one transform for cross-month comparability; train-only
(split discipline); same transform for pre/post cp. cp-based metrics retained
(no silent replacement). Mate-band excluded from ES summaries. Monotonic by construction;
output in (0,1); covered by 15 tests.

## 5. Full extraction commands and runtime

```bash
# 1. fit the pooled cp->ES transform (no PGN/engine)
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.next_move_loss \
  --version-tag 2024_09_250k_v1 --dataset-id lichess_ten_zero_2024_09_250k_v1 \
  --fit-es-transform --fit-version-tags 2024_09_250k_v1,2024_10_250k_v1 \
  --es-transform-out data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json

# 2. full extraction, both months (--allow-full-run), with the ES transform
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.next_move_loss \
  --dataset-id lichess_ten_zero_2024_09_250k_v1 --version-tag 2024_09_250k_v1 \
  --allow-full-run --es-transform <transform.json> \
  --output data/processed/next_move_loss_2024_09_250k_v1.parquet --report <scratch>
#   (same for 2024_10_250k_v1)
```

Runtime: 2024-09 1,471 s (~24.5 min); 2024-10 1,419 s (~23.7 min); ~48 min total
(consistent with the ~21–24 min/month estimate). Committed month reports were authored
from the artifacts; the CLI's own run report went to gitignored scratch paths.

## 6. Extraction success summary

| | 2024-09 | 2024-10 |
|---|---|---|
| OK / attempted | 64,371 / 65,368 | 61,868 / 62,839 |
| no-next-move | 997 | 971 |
| fen/engine/hash failures | 0 / 0 / 0 | 0 / 0 / 0 |
| clipped cp loss mean / median | 58.3 / 19 | 57.4 / 19 |
| ES loss mean / median | 0.0345 / 0.0102 | 0.0341 / 0.0101 |
| mate-band (OK) | 2,415 | 2,243 |

## 7. Depth-parity sensitivity

`--parity-check` re-evaluated the stored `post_fen` of a 400-row 2024-09 sample at depth
13 (no PGN needed): mean clipped cp loss 57.8 (d12) vs 58.0 (d13); per-row mean absolute
delta 14cp; median delta 0. The pre/post search-parity asymmetry is benign in aggregate;
depth-12 retained.

## 8. Tests run

- `tests/test_next_move_loss.py`: **56 passed** (was 41; +15 ES/transform/build_row-ES).
- Full suite: **1,580 passed** (was 1,565; +15), 0 regressions.

## 9. Output artifact status

All three generated artifacts under `data/processed/` are **gitignored** (`git
check-ignore` confirms all three) and not staged. Month/combined reports under `reports/`
are committable. No usernames anywhere.

## 10. Limitations and caveats

- Board-decided low-clock cells are a survivor population (11.2B caveat).
- Right-skewed loss → medians/percentiles reported alongside means.
- ES transform is a logistic-on-clipped-cp fit to outcomes; mate-band excluded; a
  WDL-based cross-check (route a) was not run — deferred as optional robustness.
- Depth-parity benign in aggregate (§7); per-month re-check deferrable.
- Stockfish depth-12 eval is objective context, not absolute ground truth; this is
  association between constraint state and next-move loss, **not causal**, and not a
  degradation curve.
- Descriptive board-decided ≈ time-forfeit checkpoint loss (combined §6) is an early
  sign consistent with 11.2B; no conclusion until Atlas curves + controls.

## 11. Recommended next ticket

**15.1A — Constraint Atlas Descriptive Curves Audit.** Player-leakage hardening (11.3A/B)
remains required before 15.1B controlled modeling.
