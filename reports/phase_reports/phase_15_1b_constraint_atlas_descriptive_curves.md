# Phase 15.1B — Constraint Atlas Descriptive Curves Implementation

**Labels:** ANALYSIS/REPORTING | IMPLEMENTATION
**Date:** 2026-06-13
**Owner:** Malachi Wang

## 1. Executive summary

Implemented the descriptive Constraint Atlas over the 15.0C next-move loss artifacts:
per-cell expected-score-loss summaries across clock (conditioned on checkpoint), rating,
eval band, phase, and termination channel, with the 15.1A cell-count policy and
game-level bootstrap CIs on the headline late-group cells. Markdown reports only (no
plots, no data writes). The disciplined readout produces three honest findings:
**(1)** among CI-bearing cells there is **no clean clock gradient** in next-move loss
(late-group cells are flat ~0.028–0.031 ES loss in both months); **(2)** an apparent
"lower clock → higher loss" bump exists only in **sparse `<60s` descriptive-only cells
and does NOT replicate** (2024-09 `<10s` 0.042 vs 2024-10 `<10s` 0.028); **(3)** a
**strong replicated eval-band pattern** — ES loss peaks at near_equal/slight positions
and is lowest at decided positions, both months. Descriptive association only — not
causal, not a degradation curve; Stockfish eval is objective context, not absolute
ground truth.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/constraint_atlas.py` | Atlas module: pure bins, summaries, game-level bootstrap, month + combined report renderers, CLI |
| `tests/test_constraint_atlas.py` | 55 tests (pure logic + synthetic frames) |
| `reports/constraint_atlas_2024_09_250k_v1.md` | 2024-09 month report (15 sections) |
| `reports/constraint_atlas_2024_10_250k_v1.md` | 2024-10 month report |
| `reports/constraint_atlas_combined.md` | Combined two-month report (15 sections) |
| `reports/phase_reports/phase_15_1b_constraint_atlas_descriptive_curves.md` | This report |

No data artifacts created; no plots (markdown tables only — no `reports/tables` CSV
convention exists in the repo).

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 15.1B done; pointer → 11.3A |
| `EXPERIMENT_LOG.md` | EXP-021 added |

No PREREGISTRATION change (C4 descriptive layer matches the locked plan).

## 4. Implementation summary

Pure helpers: `clock_bucket_coarse/fine`, `rating_bin` (200-pt), `eval_band`
(near_equal/slight/clear/decided/mate_band), `termination_channel`, `cell_status`
(hidden_sparse <50 / descriptive_only 50–299 / ci_ok ≥300), large-loss indicators.
`load_atlas_frame` validates required columns, filters to OK rows, adds derived bins;
**`result_class` is optional** (not in the next_move_loss artifact, so the
normal_decisive/normal_draw sub-split is unavailable from the artifact alone — the
headline board_decided/time_forfeit binary uses `is_time_forfeit` and is unaffected;
documented). `cell_summary` computes the full ES + clipped-cp stat set on non-mate-band
rows. `bootstrap_mean_es_ci` is **game-level clustered** (resample game_ids; a game
contributes ≤4 checkpoints), applied only to the headline late-group fine-clock cells.

## 5. Commands run

```bash
PYTHONPATH=src python -m chess_mhsuc.constraint_atlas \
  --input data/processed/next_move_loss_2024_09_250k_v1.parquet \
  --version-tag 2024_09_250k_v1 --report reports/constraint_atlas_2024_09_250k_v1.md
PYTHONPATH=src python -m chess_mhsuc.constraint_atlas \
  --input data/processed/next_move_loss_2024_10_250k_v1.parquet \
  --version-tag 2024_10_250k_v1 --report reports/constraint_atlas_2024_10_250k_v1.md
PYTHONPATH=src python -m chess_mhsuc.constraint_atlas --combined \
  --input data/processed/next_move_loss_2024_09_250k_v1.parquet \
  --input data/processed/next_move_loss_2024_10_250k_v1.parquet \
  --report reports/constraint_atlas_combined.md
```

## 6. Tests run

- `tests/test_constraint_atlas.py`: **55 passed** (bins, eval band, termination channel,
  cell status, load/validation, summary mate-band exclusion, large-loss indicators,
  grouped summary, deterministic game-level bootstrap, report sections/caveats/
  forbidden-phrase/determinism).
- Full suite: **1,635 passed** (was 1,580; +55), 0 regressions.

## 7. Month report summaries

- **2024-09:** 61,956 non-mate-band OK rows; overall mean ES loss 0.0345, median 0.0102
  (right-skewed); median clipped cp 19. Checkpoint×clock (high-clock cells): mean ES loss
  edges down at later checkpoints (move_10 0.0362 → move_40 0.0252). Late fine-clock
  CI-bearing cells flat (30–60s 0.0299, 60–180s 0.0307, >180s 0.0295).
- **2024-10:** 59,625 non-mate-band OK rows; mean ES loss 0.0341, median 0.0101; median
  clipped cp 19. Late fine-clock CI-bearing cells flat (30–60s 0.0306, 60–180s 0.0306,
  >180s 0.0281). The 2024-09 `<10s`/`10–30s` bump is absent here.

## 8. Combined report summary

Strong cross-month agreement on every overall statistic. Replication verdicts:
- **No clock gradient (replicates):** CI-bearing late cells flat in both months.
- **Low-clock bump (does NOT replicate):** sparse `<60s` descriptive-only cells diverge
  between months → artifact, not signal. Pre-accepted per the 15.1A non-monotonicity
  caution.
- **Eval-band pattern (replicates strongly):** late, over-180s — near_equal/slight have
  the highest ES loss (2024-09 0.0345/0.0414; 2024-10 0.0322/0.0396), decided the lowest
  (0.0168/0.0148). Sensible: decided positions have little expected-score left to lose.
- **Termination (descriptive):** time-forfeit checkpoint loss runs slightly above
  board-decided in CI-bearing late cells (e.g. 2024-10 time-forfeit ~0.034 vs
  board-decided ~0.028) — a selected-survivor descriptive difference, not a mechanism
  claim.

## 9. Sparse-cell and caveat summary

Low-clock late cells (`under_60`, and finer `<10`/`10_30`) and rating tails (≤600, ≥2400)
are descriptive-only or hidden_sparse and are labeled throughout; the non-replicating
low-clock bump (§8) is the concrete reason they must not be emphasized. Standing caveats
in every report: descriptive/not causal; no degradation-curve language; Stockfish eval
not absolute ground truth; White-to-move scope (even-ply checkpoints); survivorship in
board-decided low-clock cells; right-skew (medians/quantiles reported); DRAW sparse;
sharpness not implemented and not invoked.

## 10. Recommended next ticket

**11.3A — Player-Disjoint / Player-Clustered Feasibility Audit.** Controlled C4 modeling
(next-move loss ~ time + rating + eval band + phase + prior trajectory, with
interactions) and sharpness moderation (15.2B) must not proceed until player-leakage /
clustering is addressed. The Atlas already shows the most analytically important point
descriptively: **eval-band conditioning dominates and must be controlled**, and the raw
clock gradient on move quality is flat among resolvable cells — so any controlled model
must condition on eval band and treat low-clock cells cautiously.
