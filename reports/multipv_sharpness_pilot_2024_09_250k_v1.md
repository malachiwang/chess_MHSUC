# MultiPV Sharpness Pilot — 2024_09_250k_v1

**Ticket:** 14.1B — Pilot Sharpness Extraction

## 1. Executive summary

MultiPV-5 pilot over 1,000 stratified 2024-09 checkpoints. MultiPV extraction worked reliably (1,000 OK; FEN round-trip match 1.0; all-candidates-legal 1.0; top-1 vs existing best-line median |Δcp| 15.0). **Primary v1 sharpness = objective value fragility**; surface tags and surface-bait are **exploratory diagnostics, NOT human obviousness** (deferred to a later Tier B layer). **No sharpness result is claimed.** Predictive/descriptive only; MultiPV at fixed depth approximates narrowness, not ground truth.

## 2. Input artifact and sample design

- Input: `data/processed/next_move_loss_2024_09_250k_v1.parquet` (OK rows).
- Stratified: 1,000 rows, ~250 per checkpoint (move_10/20/30/40); non-mate preferred, mate-band backfilled if short.
- Non-mate 1,000; mate-band 0.

## 3. Engine settings and runtime

- Stockfish `Stockfish 18`, MultiPV-5, fixed depth; cp→ES scale 348.41.
- depth 10: 35.3s / 1,000 pos = 35.3 ms/pos.
- depth 12: 106.3s / 1,000 pos = 106.3 ms/pos.

## 4. MultiPV validation checks

- FEN round-trip hash match: 1.0 (no stored fen_hash in the next-move-loss artifact, so this validates FEN parse integrity).
- All candidate moves legal: 1.0.
- Median MultiPV count: 5.0 (expect min(K, legal)).
- Top-1 vs existing `pre_sf_eval_cp` median |Δcp|: 15.0 (depth-12 here vs the stored depth-12 best-line value).
- Mate-band rows flagged; value-fragility composites computed on non-mate rows.

## 5. Depth-10 vs depth-12 comparison

On 1,000 shared positions: top-1 move agreement 0.637; top-1 median |Δcp| 16.0; `n_good_10es` agreement 0.881; `sharp_value_fragility_v1` agreement 0.95.

## 6. Objective value-fragility features

- Median best→second ES gap: 0.01179001440907923.
- Median `n_good_10es` (candidates within 0.10 ES of best, censored at K): 5.0.
- Median legal-move count: 32.0.
- `sharp_value_fragility_v1` rate (non-mate): 0.142.
Features are non-degenerate (gaps and viable-set counts vary across positions).

## 7. Surface move tags

- Best move quiet rate (non-mate): 0.679.
- Per-candidate tags populated: check / capture / promotion / quiet / moved & captured piece type. Recapture deferred (needs opponent last-move square, not in the checkpoint FEN). Forced-evasion context via `ctx_in_check`/`n_legal_evasions`.

## 8. Surface-bait diagnostics (exploratory)

- `surface_bait_10es` rate (non-mate): 0.024 — positions where a forcing-looking (check/capture/promotion) candidate exists in the top-K but the best such move loses >0.10 ES. **Exploratory only; not a model of human obviousness.**

## 9. Candidate sharpness composites

`sharp_value_fragility_v1 = n_good_10es<=2 AND worst_top5_loss_es>=0.10 AND legal_move_count>=8`; plus `_relaxed`, `_strict`, continuous `sharp_score_candidate` (best→second ES gap), and exploratory `surface_bait_v1`. **Candidate features pending 14.2A pre-registration — none is a sharpness claim.**

## 10. Artifact schema

Gitignored `data/processed/multipv_sharpness_pilot_2024_09_250k_v1.parquet`: one row per checkpoint, wide `pv{1..K}_*` columns, fragility/clutter/entropy features, surface tags, surface-bait diagnostics, candidate composites, status/validation fields. No raw PGN text or usernames.

## 11. Recommended full-extraction settings

- **MultiPV-5, depth-12** for both months — projected ~3.7 h for both months at the measured 106 ms/pos. This exceeds the 14.1A 30-position smoke estimate (~2.3 h) because the stratified pilot includes more complex late checkpoints, but remains under the 6–8 h GO gate. Depth-10 (~3× faster) is a fallback only if depth-12 proves unstable; the pilot shows the sharpness composite is depth-stable, so depth-12 is preferred.

## 12. Risks and caveats

- No sharpness result; pilot feature extraction only. Not causal; no 'degradation curve' language; surface tags are NOT human obviousness.
- White-to-move only (even-ply checkpoints). MultiPV fixed-depth approximates narrowness, not ground truth; candidate ordering can shift with depth.
- `n_good_*` counts right-censored at K; viable fractions are lower bounds.
- Recapture/forced-evasion-from-history deferred; DRAW sparse; prior trajectory deferred.

## 13. Recommendation

MultiPV pilot succeeded and features are sane → proceed to **14.1C — Full Sharpness Extraction** (both months, MultiPV-5 depth-12), then **14.2A — Sharpness Interaction Pre-Registration** before any C3c modeling.
