# Phase 14.1B — Pilot Sharpness Extraction

**Labels:** IMPLEMENTATION / PILOT (Sharpness arc, C3)
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

Implemented and ran the MultiPV sharpness pilot: a MultiPV-5 engine read at 1,000
stratified 2024-09 checkpoints (250 per checkpoint), computing **objective
value-fragility** features (the v1 sharpness primitive) plus **exploratory surface
move tags and surface-bait diagnostics**. The pilot succeeded cleanly: **1000/1000 OK,
FEN round-trip 1.0, all candidates legal 1.0, median MultiPV count 5, top-1 vs the stored
best-line median |Δcp| 15**. Features are non-degenerate (median best→second ES gap 0.012,
median `n_good_10es` = 5, `sharp_value_fragility_v1` base rate 0.142). Depth-10 vs depth-12:
the **sharpness composite agrees 0.95** across depths (the literal top-1 move agrees only
0.64 — expected in flat positions), favoring depth-12. **No sharpness result is claimed;
surface tags are NOT a model of human obviousness** (deferred to a later Tier B layer).
Recommend proceeding to full both-months extraction (MultiPV-5 depth-12, projected ~3.7 h).
Predictive/descriptive only; MultiPV at fixed depth approximates narrowness, not ground truth.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/multipv_sharpness.py` | MultiPV extraction, value-fragility / clutter / entropy features, surface tags, surface-bait diagnostics, candidate composites, depth comparison, report renderer, CLI |
| `tests/test_multipv_sharpness.py` | 22 tests (no engine): sampling, score orientation, ES bounds, fragility/censoring/drop-off/entropy, clutter, move tags, surface-bait, composites, report privacy, CLI |
| `reports/multipv_sharpness_pilot_2024_09_250k_v1.md` | Pilot report (13 sections) |
| `reports/phase_reports/phase_14_1b_pilot_sharpness_extraction.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 14.1B done; pointer → 14.1C |
| `EXPERIMENT_LOG.md` | EXP-031 added |

No edits to `stockfish_eval.py` (its helpers `score_to_white_pov`, `resolve_stockfish_path`,
`get_stockfish_version`, `MATE_CP_SENTINEL` and `next_move_loss.expected_score`/`_fen_hash`
were imported and reused unchanged). No new dependencies. No existing data artifacts modified.

## 4. Implementation summary

`multipv_sharpness.py` reads checkpoint FENs directly from the next-move-loss artifact
(`pre_fen`), samples 250 per checkpoint (non-mate preferred, mate-band backfill), and runs
`engine.analyse(board, Limit(depth=d), multipv=K)` (the `multipv=` kwarg — never
`engine.configure`). Per candidate it stores mover-POV cp (via `relative_score_to_mover`),
White-POV cp (via `score_to_white_pov`), mate, ES (train cp→ES transform, scale 348.41),
loss-from-best, and surface tags. Pure feature functions (`fragility_features`,
`clutter_features`, `surface_bait`, `composites`) make the logic unit-testable without an
engine. Output is one wide row per checkpoint (140 columns).

## 5. Commands run

```bash
PYTHONPATH=src python -m chess_mhsuc.multipv_sharpness \
  --input data/processed/next_move_loss_2024_09_250k_v1.parquet \
  --output data/processed/multipv_sharpness_pilot_2024_09_250k_v1.parquet \
  --report reports/multipv_sharpness_pilot_2024_09_250k_v1.md \
  --version-tag 2024_09_250k_v1 --pilot-size 1000 --multipv-k 5 \
  --depth 12 --compare-depth 10 --seed 42
```

## 6. Tests run

- `tests/test_multipv_sharpness.py`: **22 passed** (no engine calls).
- Full suite: **1,727 passed** (was 1,705; +22), 0 regressions.

## 7. Pilot sample summary

1,000 rows, **250 per checkpoint** (move_10/20/30/40), all non-mate (the stratified sampler
preferred non-mate rows and there were enough, so **0 mate-band were sampled** — the
mate-band path is implemented and flagged but not exercised by this sample). Deterministic at
seed 42.

## 8. Runtime summary

Stockfish 18, single-thread, fixed depth. **depth-10: ~35 ms/pos** (34.9 s / 1,000);
**depth-12: ~106 ms/pos** (105.8 s / 1,000). The depth-12 ms/pos is higher than the 14.1A
30-position smoke (~66 ms) because the stratified sample includes more complex late
checkpoints. **Full-extraction projection: MultiPV-5 depth-12 ≈ 3.7 h both months** — above
the smoke estimate but **under the 6–8 h GO gate**.

## 9. Validation summary

- FEN round-trip hash match **1.0** (the next-move-loss artifact carries no stored
  `fen_hash`, so this validates FEN parse integrity rather than against a stored hash).
- All candidate moves legal **1.0**.
- Median MultiPV count **5**; fewer only where legal moves < 5 (11 positions had 1, etc.) —
  matches `min(K, legal_move_count)`.
- Top-1 vs stored `pre_sf_eval_cp` median **|Δcp| 15** (depth-12 MultiPV-1 vs the stored
  depth-12 best-line value — small, consistent).
- Mate-band handled explicitly; composites computed on non-mate rows. No impossible ES.

## 10. Depth stability summary

On the 1,000 shared positions: **top-1 move agreement 0.64**, top-1 median |Δcp| 16,
**`n_good_10es` agreement 0.88**, **`sharp_value_fragility_v1` agreement 0.95**. The literal
top-1 move flips moderately across depths (expected — many positions have several near-equal
moves), but the **sharpness composite is highly depth-stable**, which is what matters for the
feature. → **depth-12 preferred** for the full run.

## 11. Feature sanity summary

Non-degenerate and sensible: median best→second ES gap **0.012** (most positions have a
close second-best), median `n_good_10es` **5** (the median position is *not* sharp — has ≥5
moves within 0.10 ES), median legal-move count **32**. Composite base rates (non-mate):
`sharp_value_fragility_v1` **0.142**, `_relaxed` 0.074, `_strict` 0.068, `surface_bait_10es`
**0.024**, `surface_bait_v1` 0.024, `best_move_is_quiet` 0.679. All candidate features —
**pending 14.2A pre-registration; none is a sharpness claim.**

## 12. Artifact status

`data/processed/multipv_sharpness_pilot_2024_09_250k_v1.parquet` (1,000 rows × 140 cols) —
**gitignored** (verified via `git check-ignore`). No raw PGN text, no usernames, no player
hashes (player hashes are joined later from `player_metadata`, not duplicated here).

## 13. Limitations and caveats

- **No sharpness result**; pilot feature extraction only. Not causal; no "degradation curve"
  language. **Surface tags / surface-bait are exploratory diagnostics, NOT human
  obviousness** (deferred to a later Tier B layer).
- White-to-move only (even-ply checkpoints). MultiPV fixed-depth approximates narrowness, not
  ground truth; candidate ordering shifts with depth (top-1 agreement 0.64).
- `n_good_*` counts right-censored at K=5; viable fractions are lower bounds.
- Recapture and history-based forced-evasion deferred (the checkpoint FEN lacks the
  opponent's last-move square). Anti-circularity: sharpness is defined from engine geometry /
  board logic, not human outcomes (Tier A discipline).
- 0 mate-band sampled here; the mate-band path is implemented but unexercised by this sample.
- DRAW sparse; prior trajectory deferred; Stockfish eval is objective context, not ground truth.

## 14. Recommended next ticket

**14.1C — Full Sharpness Extraction** (both months, MultiPV-5 depth-12, ~3.7 h, gitignored
artifacts + report; reuse this module). Full artifacts are needed so 14.2A can inspect
sharpness distributions reliably before locking thresholds. Then **14.2A — Sharpness
Interaction Pre-Registration** before any C3c modeling. Prior-trajectory extraction remains
an optional follow-up, revisited at 14.2A.
