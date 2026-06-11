# Ticket 9.2B — Constraint Slice / Interaction Implementation

**Labels:** ANALYSIS/ML | D2 | IMPLEMENTATION
**Date:** 2026-06-10
**Owner:** Malachi Wang
**Dataset:** `lichess_ten_zero_2024_09_250k_v1`

---

## 1. ELI5 / TLDR

9.1B confirmed that clock features add predictive signal after controlling
for engine eval and ratings (E3→E4: −0.0138, CI excludes zero). This ticket
asks *where* that signal lives, by recomputing the paired delta inside
slices that were fixed by the 9.2A audit before any results were computed.
**No models were trained** — everything reuses the existing 9.1B prediction
artifact.

**Key finding (P3):** within late checkpoints (move_30+40), the delta is
−0.2541 where under 60s remain (228 games — below the CI threshold,
descriptive only), −0.0534 [−0.0717, −0.0335] at 60–180s (excludes zero),
and only −0.0074 [−0.0136, −0.0014] above 180s. **The clock signal
localizes to actual time scarcity, not just game length** — consistent
with time-pressure relevance, with the clock×checkpoint confound
controlled. Predictive association only; not causal.

Also: the signal is present across equal, slight, and decided positions
(P1 — so it is not merely "clocks predict whether a won position gets
converted"), and is stable across rating bands (P2).

---

## 2. Files Created

| File | Description |
|---|---|
| `src/chess_mhsuc/constraint_slices.py` | New module: 11 functions (A–K) + CLI |
| `tests/test_constraint_slices.py` | 74 tests, no real data required |
| `reports/constraint_slices_2024_09_250k_v1.md` | Committed slice report (deterministic) |
| `reports/phase_reports/phase_9_2b_constraint_slice_implementation.md` | This report |

Local-only (gitignored): `data/processed/constraint_slices_2024_09_250k_v1.json`

## 3. Files Modified

| File | Change |
|---|---|
| `ROADMAP.md` | Phase 9.2 stanza added; 9.2A and 9.2B marked complete |
| `EXPERIMENT_LOG.md` | EXP-010 added |

No model code touched. `eval_conditioned_modeling.py` is imported only for
its `validate_pairing` helper; `bootstrap_ci.py` functions reused unchanged.

---

## 4. Inputs

- `eval_conditioned_predictions_2024_09_250k_v1.parquet` — E3/E4 validation
  rows (9,823 per model; alignment by `(game_id, selected_position_type,
  result_class)` verified at load; 'last' rows rejected; test split never
  selected).
- `feature_positions_broad_2024_09_250k_v1.parquet` +
  `sf_eval_broad_2024_09_250k_v1.parquet` — slice keys only (avg_elo,
  capped clocks, clock_diff_s, sf_eval_cp, sf_depth), joined on
  `(game_id, selected_position_type)` with 0 orphans.

## 5. Slice Definitions

Fixed by the 9.2A audit before results were computed; not tuned afterwards.

| Slice | Role | Cells |
|---|---|---|
| checkpoint | reference | move_10 / 20 / 30 / 40 |
| decidedness (P1) | primary | \|cp\|<100 equal; 100–299 slight; 300–9999 decided; ≥10000 mate |
| elo_bucket (P2) | primary | <1200; 1200–1599; 1600–1999; ≥2000 (avg_elo) |
| late_clock (P3) | primary | WITHIN move_30+40: min capped clock <60s; 60–179s; ≥180s |
| clock_imbalance | exploratory | \|clock_diff_s\| <30; 30–89; ≥90 |
| terminal sensitivity | exploratory | overall delta with/without sf_depth=0 rows |

Rejected per audit: marginal clock buckets as primary (confounded with
checkpoint — mandatory cross-tab included in the report), side-to-move
(constant), material/sharpness (not in feature table), elo_diff as primary,
full clock×checkpoint grid (sparse).

## 6. Data Sufficiency

CI rule: cells with ≥ 300 unique games get a 1,000-replicate game-level
clustered bootstrap CI (seed=42); smaller cells report the point delta with
an explicit "below min game threshold" note. One primary cell is
sub-threshold: late_clock under_60s (228 games). No cell silently dropped;
no post-hoc merging.

## 7. Results Summary

Reference per-checkpoint deltas reproduce 9.1B exactly (move_10 −0.0025 cz,
move_20 −0.0033 cz, move_30 −0.0238 excl, move_40 −0.0606 excl).

**P1 — decidedness:** equal −0.0151 [−0.0214, −0.0093]; slight −0.0096
[−0.0169, −0.0026]; decided −0.0168 [−0.0245, −0.0095] — all exclude zero;
mate −0.0021 [−0.0307, +0.0298] contains zero (306 games). The signal is
present in contested *and* decided positions.

**P2 — rating:** under_1200 −0.0096 (contains zero, 665 games); 1200_1600
−0.0150 and 1600_2000 −0.0140 (both exclude zero); 2000_plus −0.0155
[−0.0312, −0.0001] (excludes zero, 329 games). Magnitudes similar across
bands — no strong skill-dependence pattern.

**P3 — late-checkpoint clock (key):** under_60s −0.2541 (228 games,
descriptive); 60_180s −0.0534 [−0.0717, −0.0335] excludes zero (616 games);
over_180s −0.0074 [−0.0136, −0.0014] excludes zero (1,582 games). Within
late game, the signal is ~7× larger where remaining time is low.

**Exploratory:** clock imbalance graded (balanced −0.0006 cz; moderate
−0.0061 excl; large −0.0442 excl). Terminal sensitivity: delta −0.0138 with
and without the 44 terminal val rows — robust.

## 8. Bootstrap / Uncertainty

Game-level clustered paired bootstrap reusing `bootstrap_ci.py` public
functions (`run_paired_delta_bootstrap`, `compute_delta_ci`,
`compute_point_log_loss`) — within each cell, E3/E4 pairing is asserted via
`validate_pairing` before resampling. delta = LL(E4) − LL(E3); negative
means clock features improved. No row-level bootstrap anywhere.

## 9. Tests / Validation

- `tests/test_constraint_slices.py`: **74 tests, 0 failures** — bucket
  boundary cases (decidedness 0/99/100/299/300/9999/10000; elo
  1199/1200/1599/1600/1999/2000; clock 29/59/60/179/180; imbalance
  0/29/30/89/90), join integrity, pairing validity (misaligned labels and
  missing models fail), delta sign convention with manual log_loss check,
  bootstrap determinism and threshold behavior, report sections/caveats/
  forbidden phrases, no-hardcoded-counts, JSON schema, gitignore check,
  end-to-end CLI.
- Full suite: **1,478 passed** (was 1,404; +74), 0 regressions.
- Real CLI run: reference checkpoint deltas reproduce 9.1B to the 4th
  decimal; report byte-identical across two runs (modulo self-referential
  output paths in the Reproducibility section).
- Language grep: only negated/caveated forms. Forbidden artifact scan: clean.

## 10. Data / Git Safety

- JSON artifact under `data/processed/` — gitignored (verified with
  `git check-ignore`). Nothing staged; no `git add .`; no model binaries,
  CSVs, or plots.
- No data artifacts modified — predictions, features, and sf_eval inputs
  were read-only.

## 11. Scientific Caveats

- All slice results are predictive associations on the validation split —
  **not causal effects**, and reasoning quality is **not directly measured**.
- Slices localize a single already-confirmed effect; they are not
  independent hypothesis tests; no multiple-comparison correction is claimed.
- Ordered-bucket patterns do **not** establish degradation curves.
- Stockfish depth=12 eval is objective position context, **not ground truth**.
- under_60s is descriptive only (228 games < 300 threshold).
- Decidedness, checkpoint, and clock depletion remain mutually correlated;
  P3's conditioning controls the largest confound, not all of them.
- Test split untouched. Player-level leakage unresolved. DRAW sparse, not
  solved. Phase 10 not started.

## 12. Acceptance Criteria

| Criterion | Status |
|---|---|
| Slice definitions documented (fixed pre-results) | DONE |
| Row/game counts per cell reported (incl. DRAW counts) | DONE |
| E3→E4 deltas for reference + P1 + P2 + P3 | DONE |
| Game-level CIs where ≥300 games | DONE |
| Sub-threshold cells descriptive with explicit note | DONE (under_60s) |
| Mandatory clock×checkpoint confounding cross-tab | DONE |
| No models trained; no test selection; no causal claims | DONE |
| 74 new tests; full suite 1,478 passed | DONE |
| Report deterministic | DONE |
| Data artifacts ignored and unstaged | DONE |
| ROADMAP Phase 9.2 stanza; EXP-010 | DONE |

## 13. Suggested Commit

```bash
git add src/chess_mhsuc/constraint_slices.py
git add tests/test_constraint_slices.py
git add reports/constraint_slices_2024_09_250k_v1.md
git add reports/phase_reports/phase_9_2b_constraint_slice_implementation.md
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git commit -m "Ticket 9.2B: implement constraint slice analysis"
```

Do NOT stage `data/` or any Parquet/JSON data artifacts.
