# MultiPV Sharpness Extraction — 2024_09_250k_v1

**Ticket:** 14.1C — Full Sharpness Extraction

## 1. Executive summary

Full MultiPV-5 depth-12 extraction over all 64,371 OK checkpoints. 64,371 OK; FEN round-trip 1.0; all-candidates-legal 1.0; top-1 vs stored best-line median |Δcp| 14.0. **Primary v1 = objective value fragility**; surface tags / surface-bait are **exploratory diagnostics, NOT human obviousness** (deferred Tier B). **No sharpness result is claimed.** Predictive/descriptive only; MultiPV at fixed depth approximates narrowness, not absolute ground truth.

## 2. Input artifact

- `data/processed/next_move_loss_2024_09_250k_v1.parquet` (OK rows; `pre_fen` read directly — no raw-PGN reconstruction).

## 3. Output artifact

- `data/processed/multipv_sharpness_2024_09_250k_v1.parquet` (gitignored; one row per checkpoint, 140 cols; no raw PGN/usernames/hashes).

## 4. Engine settings and runtime

- Stockfish `Stockfish 18`, MultiPV-5, fixed depth-12; cp→ES scale 348.41.
- Runtime: report regenerated from the saved artifact (`--report-only`); see the 14.1C phase report / EXP-032 for wall-clock and the system-sleep caveat. Awake extraction rate ~100 ms/pos.

## 5. Extraction counts

- Total attempted: 64,371; OK: 64,371; non-mate 61,956; mate-band 2,415.
- Status counts: {'ok': 64371}.

## 6. Validation checks

- FEN round-trip hash match: 1.0 (validates FEN parse integrity; the next-move-loss artifact carries no stored fen_hash).
- All candidate moves legal: 1.0.
- Median MultiPV count: 5.0; share with <K legal moves: 0.0586.
- Top-1 vs stored `pre_sf_eval_cp` |Δcp|: median 14.0, p90 49.0.
- Missing-value counts (key features, OK rows): {'multipv_count': 0, 'n_good_10es': 0, 'best_second_gap_es': 617, 'worst_top5_loss_es': 0}.
- Mate-band rows flagged (`is_mate_band`); composites summarized on non-mate rows.

## 7. Objective value-fragility features (non-mate)

- Median best→second ES gap 0.0126; median `n_good_10es` 5.0; median `worst_top5_loss_es` 0.0463; median legal-move count 34.0.

Per-checkpoint (`sharp_value_fragility_v1` rate / median `n_good_10es`):

| checkpoint | n | sharp_v1 rate | median n_good_10es | surface_bait_10es |
|---|---|---|---|---|
| move_10 | 24,221 | 0.1483 | 5.0 | 0.0246 |
| move_20 | 19,003 | 0.152 | 5.0 | 0.0241 |
| move_30 | 12,026 | 0.1339 | 5.0 | 0.0184 |
| move_40 | 6,706 | 0.103 | 5.0 | 0.0154 |

## 8. Surface move tags (exploratory)

- Best move: quiet 0.6923, check 0.0784, capture 0.258, promotion 0.0008.
- Per-candidate check/capture/promotion/quiet + piece types stored. Recapture deferred (checkpoint FEN lacks opponent last-move square).

## 9. Surface-bait diagnostics (exploratory)

- `surface_bait_10es` 0.0222; `surface_bait_20es` 0.0092. **Exploratory only; NOT human obviousness.**

## 10. Candidate sharpness composites (non-mate)

- `sharp_value_fragility_v1` 0.1417; `_relaxed` 0.0817; `_strict` 0.0732. **Candidate features pending 14.2A — not a sharpness claim.**

## 11. Artifact schema

One row per checkpoint: keys + `pre_fen`/`computed_fen_hash`/`fen_hash_matches`, wide `pv{1..K}_*` (move/cp/mate/es/loss/tags), fragility/clutter/entropy features, surface tags, surface-bait diagnostics, candidate composites, status/validation. No raw PGN, usernames, or player hashes.

## 12. Limitations and caveats

- No sharpness result; extraction only. Not causal; no 'degradation curve' language; surface tags are NOT human obviousness. White-to-move only. MultiPV fixed-depth approximates narrowness, not ground truth. `n_good_*` censored at K. DRAW sparse; prior trajectory deferred.

## 13. Recommendation

Read against the other month in the combined report; proceed to **14.2A — Sharpness Interaction Pre-Registration** before any C3c modeling.
