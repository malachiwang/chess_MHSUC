# Phase 16.2B — Cross-Time-Control Atlas / Controlled Modeling Implementation

**Ticket:** 16.2B — Cross-Time-Control Atlas / Controlled Modeling Implementation
**Status:** complete. New dedicated module + tests + atlas + controlled models + 10 figures + 2 reports.
No Stockfish, no extraction, no Parquet modified, stable Phase-15 modules unchanged.

> Predictive/descriptive only — NOT causal. Raw ratings NOT cross-pool comparable (within-control
> quintiles throughout). ES transform reused (comparability assumption, not refit). Stockfish not
> ground truth. Game-level time-forfeit prevalence uses one row per game.

## 1. Executive summary

First full no-increment cross-time-control analysis over six dense artifacts (3+0/5+0/10+0 ×
2024-09/2024-10). Four distinct questions resolved — **three (T1, T3, T4) are formally month-replicated
contrasts; T2 is a descriptive similarity statement, not a replicated equivalence result**:

- **T1 — game-level time-forfeit prevalence (replicated descriptive ordering):** monotone
  **3+0 (0.292/0.301) > 5+0 (0.226/0.226) > 10+0 (0.115/0.116)** (Sep/Oct), replicated. Adjusted logit
  TC odds-ratios vs 10+0: 3+0 ≈ 3.22, 5+0 ≈ 2.23 (descriptive).
- **T2 — average move quality (descriptively stable; NOT a formal equivalence result):** ES loss
  **broadly similar** (mean 3+0 ≈ 0.0337, 5+0 ≈ 0.0350, 10+0 ≈ 0.0346). Not "identical." No equivalence
  margin or equivalence test was run, so T2 is **not classified as replicated equivalence** — it is
  outside the replication classifier (which applies to T1/T3/T4 coefficient contrasts).
- **T3 — within-control clock gradient (replicated conditional gradients):** lower clock fraction →
  higher ES loss, replicated in all three controls after conditioning (3+0 critical-vs-high +0.0117,
  5+0 +0.0077, 10+0 +0.0056); survives mover-player clustering (R8 §18).
- **T4 — cross-control moderation (replicated conditional moderation):** the conditional clock gradient
  **differs across controls** (pooled interaction 3+0×critical +0.0089, 5+0×critical +0.0033 vs 10+0,
  both replicated; survive mover-player clustering R8) — the low-clock gradient is steeper in faster
  controls.
- Board-decided-only (R1) shrinks but does not eliminate the gradient (3+0 +0.0062, 10+0 +0.0031),
  consistent with the gradient being partly flagging-channel, partly board play. Very-low-clock cells
  are heavily endgame-confounded (§15 of the analysis report).

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; 16.2A audit; 16.1C phase report + 4 extraction reports;
10+0 anchor reports (constraint atlas, controlled model, dense extraction); Phase 11 termination
decomposition; `dense_constraint_atlas.py`, `dense_controlled_model.py`, `dense_move_loss.py`,
`clustered_uncertainty.py` (for `_cluster_index`) + their tests.

## 3. Files created

- `src/chess_mhsuc/cross_time_control_analysis.py` (dedicated module, ~1,100 lines).
- `tests/test_cross_time_control_analysis.py` (39 tests).
- `reports/cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md` (main report).
- `reports/phase_reports/phase_16_2b_cross_time_control_atlas_controlled_modeling_implementation.md`.
- `reports/figures/phase_16_2_cross_time_control/` (10 tracked PNGs).

## 4. Files modified

`ROADMAP.md`, `EXPERIMENT_LOG.md` (EXP-054). PREREGISTRATION unchanged. No stable Phase-15 module,
Parquet artifact, ES transform, or raw PGN touched.

## 5. Implementation architecture

Dedicated module (Option B from 16.2A). Reuses only the pure `_cluster_index` helper from
`clustered_uncertainty.py`; reimplements its own bucket helpers, design builders, and a **weighted**
clustered sufficient-statistics bootstrap (XᵀWX/XᵀWy) so pooled game-normalized weighting is supported
(the Phase-15 bootstrap is unweighted). Functions: artifact load + identity validation; headline
population; clock_fraction fine/coarse buckets; within-control×month rating quintiles; control-aware
anomaly flags; game-normalized analysis weights; game-level table; descriptive summaries; within-control
+ pooled-interaction design builders; weighted OLS + clustered bootstrap; replication classifier;
game-level termination logit (sklearn); matplotlib (Agg) figures; report writer; CLI.

## 6. Tests

```
tests/test_cross_time_control_analysis.py                          -> 39 passed
+ test_dense_constraint_atlas + test_dense_controlled_model        -> 73 passed (regression)
full suite                                                          -> 1899 passed, 3 warnings
```

Coverage: identity validation (accept + reject wrong TC/initial-time/increment/missing-cols/username/
dup-keys); population (mate-band + invalid excluded, anomalies retained then robustness-excluded);
quintiles (within control×month, deterministic, tie-stable, not reused across controls); clock-bucket
boundaries (0.02/0.05/0.10/0.15/0.25/0.50/0.75/1.0/>1.0); game-level table (one row/game, inconsistent-
termination rejection, game-rate ≠ move-share when lengths differ); weighting (equal per-game + equal
per-stratum, positive, mean-1 scaling); design matrices (reference levels dropped, month/termination
excludable, pooled interaction columns present); replication (all 5 statuses); output privacy.

## 7. CLI invocation

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.cross_time_control_analysis \
  --dense-2024-09-3plus0 data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet \
  --dense-2024-09-5plus0 data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet \
  --dense-2024-09-10plus0 data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-2024-10-3plus0 data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet \
  --dense-2024-10-5plus0 data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet \
  --dense-2024-10-10plus0 data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --bootstrap 500 --player-bootstrap 200 --seed 20240621 \
  --figure-dir reports/figures/phase_16_2_cross_time_control \
  --report reports/cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md
```

No network, no Stockfish.

## 8. Artifact validation

All six pass identity validation: time_control_raw/initial_time_s/increment_s(=0)/family(no_increment)/
speed correct; month tag correct; 0 duplicate (game_id, ply) keys; both mover colors; ES bounded; CP
nonnegative; no username columns; status all ok. (3+0→180+0/180, 5+0→300+0/300, 10+0→600+0/600.)

## 9. Population and denominator summary

| Control | Month | Headline rows | Games | Rows/game |
|---|---|---|---|---|
| 3+0 | 2024-09 | 1,422,173 | 23,703 | 60.0 |
| 3+0 | 2024-10 | 1,420,818 | 23,721 | 59.9 |
| 5+0 | 2024-09 | 1,367,293 | 23,756 | 57.6 |
| 5+0 | 2024-10 | 1,364,419 | 23,734 | 57.5 |
| 10+0 | 2024-09 | 1,416,313 | 25,582 | 55.4 |
| 10+0 | 2024-10 | 1,362,459 | 24,524 | 55.6 |

Headline = status==ok ∧ ¬mate-band ∧ valid clock/clock_fraction/rating/termination. Anomalies retained
with flags (primary); excluded in R2. Row counts ≈ equal, game counts differ → game-normalized pooled
weights (§16 of analysis report).

## 10. Rating-quintile validation

Within-control × month quintiles. Cutpoints (Q1≤/Q2≤/Q3≤/Q4≤): 3+0 ≈ 1495/1717/1878/2052 (Sep);
5+0 ≈ 1272/1500/1685/1882; 10+0 ≈ 1269/1510/1702/1896. 3+0 ~200 Elo above 5+0/10+0 → raw cross-pool
ratings NOT comparable. Tests confirm determinism, tie-stability, and per-stratum cutpoints.

## 11. Clock-bucket validation

`clock_fraction = clock_before_s/initial_time_s`. Fine 7-buckets + coarse 4-buckets (ref=high);
clock_fraction>1 stays in top bucket with `clock_gt_initial_flag`. Boundary behavior unit-tested.

## 12. Atlas outputs

10 figures (§19). Descriptive ES-loss / CP-loss / large-loss curves show a marginal U-shape (loss high
at both very-low and very-high clock fraction — the latter is early/opening play), which the controlled
models resolve by conditioning on phase + eval.

## 13. Within-control model results (T3)

All clock contrasts (critical/low/medium vs high) are **positive and replicated in all three controls**.
Critical-vs-high: 3+0 +0.0117 [+0.0109,+0.0126]; 5+0 +0.0077 [+0.0069,+0.0086]; 10+0 +0.0056
[+0.0046,+0.0067]. Monotone (critical > low > medium) in every control. The 10+0 result is compatible
with the prior Phase-15 absolute-clock finding (small, monotone, replicated) — lineage check passes (R10).

## 14. Pooled interaction results (T4)

Interaction = (control clock gradient) − (10+0 clock gradient), game-normalized weights. **All six
TC×clock interaction terms positive and replicated:** 3+0×critical +0.0089 [+0.0075,+0.0103];
5+0×critical +0.0033 [+0.0018,+0.0047]; (low/medium similar, smaller). The low-clock ES-loss gradient
is **steeper in faster controls** — conditional, NOT causal; TC main effect not interpreted causally.

## 15. Game-level termination results (T1)

Game-level prevalence (one row/game): 3+0 0.292/0.301, 5+0 0.226/0.226, 10+0 0.115/0.116 (Sep/Oct).
Adjusted logit (TC+month+rating-quintile) odds ratios vs 10+0: 3+0 ≈ 3.22, 5+0 ≈ 2.23; game-length-
adjusted (secondary) ≈ 3.29 / 2.31. Descriptive only — game length is partly downstream of forfeit.

## 16. Board-decided-only results (R1)

Board-decided games only (termination term removed). Critical-vs-high shrinks vs all-games but stays
positive + significant: 3+0 +0.0062 [+0.0044,+0.0077]; 5+0 +0.0051; 10+0 +0.0031. → the within-control
clock gradient is **not purely the flagging channel**; a smaller board-play component survives.

## 17. Month replication

Every headline **contrast** classified deterministically (replicated / directionally_replicated /
pooled_only / not_replicated / null_or_unresolved). The T1, T3, and T4 contrasts = **replicated**
(same sign + both month CIs exclude 0). **T2 is NOT in this classifier** — it is a descriptive
similarity statement (average ES loss broadly similar), not a coefficient/difference contrast, and no
equivalence margin or equivalence test was run, so it is **not classified as replicated equivalence**.
"All T1–T4 replicated" would be incorrect. See analysis-report §10–§11 and Fig 10.

## 18. Robustness matrix

| Spec | 3+0 crit-vs-high | 5+0 crit | 10+0 crit | direction |
|---|---|---|---|---|
| Primary (all games) | +0.0117* | +0.0077* | +0.0056* | + |
| R1 board-decided only | +0.0062* | +0.0051* | +0.0031* | + (shrinks) |
| R2 anomaly-excluded | +0.0117* | +0.0077* | +0.0056* | + |
| R4 clipped-CP outcome | +22.6cp* | +15.4cp* | +11.2cp* | + (transform-free) |

**R8 — mover-player-clustered (EXECUTED, 200 draws, seed 20240621):** headline T3/T4 contrasts refit
with cluster key = `mover_player_hash` instead of `game_id`:

| Target | game-clustered (200) | player-clustered (200) | sign | player CI excl 0 | player clusters |
|---|---|---|---|---|---|
| T3 3+0 crit-vs-high | +0.0117 [+.0110,+.0125] | +0.0117 [+.0110,+.0124] | agrees | yes | 22,332 |
| T3 5+0 crit-vs-high | +0.0077 [+.0069,+.0086] | +0.0077 [+.0068,+.0086] | agrees | yes | 26,114 |
| T3 10+0 crit-vs-high | +0.0056 [+.0047,+.0067] | +0.0056 [+.0046,+.0064] | agrees | yes | 31,381 |
| T4 3+0×crit (vs 10+0) | +0.0089 [+.0076,+.0100] | +0.0089 [+.0075,+.0102] | agrees | yes | 77,408 |
| T4 5+0×crit (vs 10+0) | +0.0033 [+.0019,+.0047] | +0.0033 [+.0023,+.0048] | agrees | yes | 77,408 |

**All five headline T3/T4 targets survive mover-player clustering** (point estimates unchanged, signs
agree, every player-clustered CI excludes 0; CIs ≈ same width). T3/T4 are not weakened. All directionally
consistent above; `*` CI excludes 0. (R3 continuous/spline, R5 ES≥0.10 binary, R7 unweighted pooled,
R9 raw-bins available via module flags.)

## 19. Figure inventory

`reports/figures/phase_16_2_cross_time_control/` (PNG, dpi 110):
fig_16_2_01 clock×ES by control (95K); _02 clock×CP (81K); _03 large-loss prob (98K);
_04 game-level termination (27K); _05 board-decided-only curves (95K); _06 rating×clock heatmap (59K);
_07 eval-band×clock (92K); _08 phase×clock (88K); _09 controlled interactions (50K);
_10 month-replication summary (26K). All have titles, labeled axes, control/month distinction, CIs where
relevant, and explicit "descriptive/not causal" framing. Inspected fig 01 + 09 visually.

## 20. Claim-status update

| Claim | Status |
|---|---|
| T1 game-level TF prevalence 3+0 > 5+0 > 10+0, both months | **replicated descriptive ordering** |
| T2 average ES loss broadly similar across controls | **descriptively stable / broadly similar; NOT a formal equivalence result, not classified as replicated equivalence (no equivalence test run)** |
| T3 within-control lower clock → higher loss (conditional) | **replicated conditional gradients, all 3 controls; survives mover-player clustering (R8)** |
| T4 conditional clock gradient differs across controls | **replicated conditional moderation (steeper in faster controls); survives mover-player clustering (R8)** |

## 21. Non-claims

No causal claims. NOT "time pressure causes worse reasoning", "low clock causes blunders", "faster
controls cause worse chess", "faster controls cause flagging", "faster controls do not harm move
quality", "increment causes better reasoning", "players reason equally well at all speeds", "Stockfish
is ground truth", "raw ratings comparable across pools", "cross-time-control differences are causal",
"time pressure affects only flagging", "sharpness moderation confirmed/disproven", "DRAW solved".
Very-low-clock = endgame-confounded; ES transform reused (comparability assumption). C4 & C3c unchanged.

## 22. Performance / runtime

~109s total wall: ~95s models (within-control × {all, board-decided, anomaly-free, CP} + pooled-rep +
per-month + termination logit, 500 game-clustered bootstrap draws each via sufficient-statistics), ~12s
figures. The R8 mover-player-clustered robustness run (5 headline targets, 200 draws) adds ~100s
(separate execution; ~8.35M headline rows). Sufficient-statistics bootstrap avoids materializing
resampled millions of rows. Selected-column reads keep memory modest (six artifacts ~8.5M raw rows →
~8.4M headline). Single process, no Stockfish.

## 23. Recommended next ticket

**16.2C — Cross-Time-Control Claim Consolidation / Phase 16 Decision Audit** (recommended default):
results are coherent (T1 replicated descriptive ordering; T2 descriptively stable / not a formal
equivalence result; T3/T4 replicated conditional contrasts surviving mover-player clustering), so
consolidate the settled Phase-16 claim, reconcile with the 10+0 anchor + Phase-11 flagging reframing,
and decide the Phase-16 path
(increment contrast 16.3 vs packaging). Do NOT jump directly to increment extraction or Phase 17 without
the consolidation ticket.
