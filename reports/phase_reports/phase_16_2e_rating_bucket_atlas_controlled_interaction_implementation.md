# Phase 16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation

**Ticket:** 16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation
**Status:** complete. New dedicated module + tests + atlas + interaction models + 9 figures + 2 reports.
No Stockfish, no extraction, no Parquet modified, stable 16.2B/Phase-15 modules unchanged.

> Predictive/descriptive only — NOT causal. "Buffer"/"attenuation"/"amplification" = descriptive
> moderation contrast labels, never causal mechanisms. Raw Lichess ratings NOT comparable across pools
> (within-control × month quintiles/percentiles only). Stockfish not ground truth. ES transform reused
> (not refit). T2 was descriptive stability, not equivalence. C3c unresolved.

## 1. Executive summary

Tests whether relative rating moderates the clock_fraction → next-move-quality relationship and whether
that differs across controls. **Headline (honest, conditioning-sensitive):**

- **The rating moderation of the critical-clock gradient is real but its DIRECTION is conditioning-
  sensitive.** All-phase (all-games): M(c) = D(c,Q5)−D(c,Q1) is **positive** (amplification — top
  quintile shows a *larger* critical-clock penalty): M(3+0)+0.0084, M(5+0)+0.0049, M(10+0)+0.0066, all
  Holm-significant. Endgame-restricted: M(c) **reverses to negative** (rating-associated attenuation in
  the endgame-restricted model): M(5+0) −0.0067 (replicated), M(10+0) −0.0044 (directional), M(3+0)
  −0.0006 (null). **The all-phase amplification is not stable under endgame restriction.** The sign
  reversal is consistent with phase composition, residual composition differences, or phase-specific
  heterogeneity, but **this analysis does not identify a single mechanism**.
- **Cross-control moderation is NOT supported:** M(3+0)−M(10+0) +0.0015 and M(5+0)−M(10+0) −0.0019 both
  contain zero (Holm p 0.76). The rating moderation does **not** clearly differ across controls.
- **Player-side time-forfeit** is weakly, descriptively lower for higher quintiles in 3+0/5+0, flat in
  10+0 (modest, not causal).

Net: **RM2 — interaction present, but direction conditioning-sensitive; no universal attenuation or
amplification claim. RM3 — not supported.** This refines the Phase-16 picture rather than establishing
that rating attenuates time pressure. Recommended next: **16.2F — Rating-Moderation Claim Consolidation /
Phase 16 Closure Audit**.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; 16.2D design audit; 16.2C consolidation; 16.2B implementation
+ main report; `cross_time_control_analysis.py` + tests; `clustered_uncertainty.py`. Six dense artifacts
confirmed present + gitignored.

## 3. Files created

`src/chess_mhsuc/rating_clock_moderation.py`; `tests/test_rating_clock_moderation.py` (22 tests);
`reports/rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md`; this phase report;
`reports/figures/phase_16_2_rating_clock_moderation/` (9 PNGs).

## 4. Files modified

ROADMAP.md, EXPERIMENT_LOG.md (EXP-057). PREREGISTRATION, `cross_time_control_analysis.py`, its tests,
all Phase-15 modules, all Parquets, ES transform — unchanged.

## 5. Implementation architecture

Dedicated module importing validated pure helpers from `cross_time_control_analysis` (load/validate,
headline population, clock buckets, quintiles, anomaly flags, weights, `_onehot`/`_finalize`,
`fit_weighted_ols`, `weighted_cluster_bootstrap`, `contrast_ci`, `classify_replication`) — **no edits to
16.2B**. Added: `assign_rating_percentiles` (within-control×month average-rank [0,1]); within-control and
pooled categorical TC×clock×quintile + percentile three-way design builders; `_linear_contrast` +
`primary_five_contrasts` + `quintile_clock_contrasts` (deterministic linear reads of bootstrap coefs);
`holm_adjust`; player-side termination table + attribution validator; orchestration; figures (Agg); CLI.
**Key design fact:** with refs TC=10+0/clock=high/rq=Q1, all five M-contrasts are linear reads of ONE
pooled categorical fit (M(c)−M(10+0) = the three-way coefficient) → one mover-player-clustered bootstrap
yields the whole family jointly → Holm.

## 6. Tests

`tests/test_rating_clock_moderation.py` → 22 passed; regression (16.2B + new) → 61 passed; **full suite
1,921 passed** (+22). Coverage: percentile (bounded/deterministic/oriented/tie-equal/within-stratum);
quintiles (levels/within-control/no cross-reuse); designs (interaction + three-way terms present, refs
dropped, full rank); contrast linear reads (D, M, cross-control, missing-term→None); Holm
(ordering/bounds/monotone/five-family); weighting (equal game + stratum); cluster bootstrap; board-
decided/endgame filters; player-side attribution (two rows, loser flagged, draw-timeout excluded, no
usernames); privacy.

## 7. CLI invocation

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.rating_clock_moderation \
  --dense-2024-09-3plus0 data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet \
  --dense-2024-09-5plus0 data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet \
  --dense-2024-09-10plus0 data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-2024-10-3plus0 data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet \
  --dense-2024-10-5plus0 data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet \
  --dense-2024-10-10plus0 data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --player-bootstrap 500 --game-bootstrap 500 --seed 20240621 \
  --figure-dir reports/figures/phase_16_2_rating_clock_moderation \
  --report reports/rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md
```

## 8. Runtime and memory

~242–298s wall (~210s models, ~30s figures). Many fits: within-control × {all, board-decided, endgame} ×
{pooled, 2024-09, 2024-10} + pooled categorical ×{all, board-decided} + percentile three-way, each a
500-draw mover-player-clustered sufficient-statistics bootstrap. ~8.35M headline rows; selected-column
reads + sufficient-statistics bootstrap keep memory modest. Single process, no Stockfish.

## 9. Artifact validation

Six artifacts pass 16.2B identity validation (TC/initial-time/increment/family/speed/month; 0 dup keys;
both colors; no usernames). Rating-field validation clean: rating_percentile ∈ [0,1], quintiles ⊆
Q1–Q5, 0 null mover_elo in headline, no username columns.

## 10. Rating-quintile validation

Within-control × month; cutpoints reproduce 16.2B (3+0 Q1≤1495/Q2≤1717/Q3≤1878/Q4≤2052 Sep; 5+0/10+0 ~200
Elo lower); per-stratum (not reused across controls); higher quintile = higher relative rating.

## 11. Rating-percentile validation + absolute-Elo landmarks

Within-control × month average-rank percentile [0,1] (0=lowest); deterministic; ties get equal
percentile; max-Elo row of each stratum = 1.0; correlation with mover_elo > 0.9 within stratum. Used for
the parsimonious three-way; predictions read at 0.10 vs 0.90. **Main report §4 now lists the executed
percentile→Elo landmarks (P10/P25/P50/P75/P90), Q1–Q5 absolute-Elo ranges + counts, and the raw 200-Elo
bin table per control.** Example: 2024-09 3+0 P10 ≈ 1313 Elo, P90 ≈ 2174; 2024-09 10+0 P10 ≈ 1097, P90 ≈
2014 — confirming the pools differ and raw Elo is not cross-comparable.

## 12. Cell-adequacy validation

All-games rating×clock cells headline-capable (16.2D); board-decided 10+0 Q1/Q2 critical exploratory →
percentile route is the principal 10+0 board-decided read; endgame-only critical×quintile well-powered.
Tiers computed in-module (`build_rating_clock_cells`).

## 13. Weighting validation

Game-normalized even within control (unit-tested: equal total weight per game within stratum, equal
aggregate per control-month, positive, mean-1). Estimand = average game-weighted decision; unweighted
rows = R11.

## 14. Within-control model results

All-games D(c,Q1..Q5) and M(c) (mover-player-clustered):

| Control | D(Q1) | D(Q5) | M(c)=Q5−Q1 | replication |
|---|---|---|---|---|
| 3+0 | +0.0106* | +0.0189* | **+0.0084*** | replicated |
| 5+0 | +0.0083* | +0.0132* | **+0.0049*** | directionally_replicated |
| 10+0 | +0.0031 | +0.0097* | **+0.0066*** | replicated |

All-games = **amplification** (D rises Q1→Q5). Critical-clock penalty is positive at every quintile.
Within-control percentile 0.90−0.10 diff agrees (3+0 +0.0083, 5+0 +0.0054, 10+0 +0.0086, all excl 0).

## 15. Pooled three-way results

Percentile three-way (§10 table): predicted critical-minus-high contrast rises with rating percentile in
every control (0.10→0.90 positive). Consistent with the all-games categorical amplification. TC main
effect + three-way not interpreted causally.

## 16. Holm-adjusted primary family

| Test | estimate [95% CI] | bootstrap p | Holm p | status |
|---|---|---|---|---|
| M(3+0) | +0.0083 [+0.0059,+0.0107] | 0.000 | 0.000 | excl 0 (Holm) |
| M(5+0) | +0.0049 [+0.0020,+0.0077] | 0.000 | 0.000 | excl 0 (Holm) |
| M(10+0) | +0.0068 [+0.0030,+0.0101] | 0.000 | 0.000 | excl 0 (Holm) |
| M(3+0)−M(10+0) | +0.0015 [−0.0026,+0.0058] | 0.508 | 0.760 | contains 0 |
| M(5+0)−M(10+0) | −0.0019 [−0.0063,+0.0023] | 0.380 | 0.760 | contains 0 |

**Within-control amplification survives Holm; cross-control moderation does NOT (both contain 0).**

## 17. Board-decided results

| Test | estimate [95% CI] | Holm p |
|---|---|---|
| M(3+0) | +0.0137 [+0.0080,+0.0193]* | 0.000 |
| M(5+0) | −0.0038 [−0.0115,+0.0043] | 0.528 |
| M(10+0) | +0.0083 [+0.0006,+0.0156]* | 0.112 |
| M(3+0)−M(10+0) | +0.0054 [−0.0041,+0.0147] | 0.528 |
| M(5+0)−M(10+0) | −0.0121 [−0.0235,−0.0006]* | 0.144 |

Mixed: 3+0 amplification persists; 5+0/10+0 unresolved under Holm. 10+0 low-quintile cells exploratory →
read via percentile. Not a clean board-decided moderation claim.

## 18. Endgame results

| Control | D(Q1) | D(Q5) | M(c)=Q5−Q1 | replication |
|---|---|---|---|---|
| 3+0 | +0.0108* | +0.0102* | −0.0006 [−0.0034,+0.0026] | null_or_unresolved |
| 5+0 | +0.0108* | +0.0041* | **−0.0067 [−0.0097,−0.0038]*** | replicated |
| 10+0 | +0.0065* | +0.0020* | **−0.0044 [−0.0082,−0.0005]*** | directionally_replicated |

**Within endgames the moderation REVERSES to rating-associated attenuation in the endgame-restricted
model** (5+0 replicated, 10+0 directional, 3+0 null). The contrast stays positive at every quintile
(clock still matters) but the gradient is smaller for higher quintiles in 5+0/10+0 — modest, not present
in 3+0. This is a conditioning-specific result; the analysis does not identify a single mechanism for the
all-phase-vs-endgame sign reversal (phase composition, residual composition, or phase-specific
heterogeneity are all consistent).

## 19. Player-side termination results

**Denominator proof (genuine prevalence):** 145,020 total games → 144,128 eligible (892 ambiguous
draw-timeout excluded) → **288,256 player-side rows = 2 × eligible** (verified). Positives
(did_forfeit=1) = **29,693 = the decisive time-forfeit games** (one loser each); zeros = 258,563
(includes both sides of every eligible non-time-forfeit game). **Overall player-side prevalence 0.1030**
(≈ half the game-level TF rate, as expected). The table is genuine prevalence — it is NOT "fraction of
time-forfeit games." By stratum: 3+0 ~0.142/0.147, 5+0 ~0.111/0.110, 10+0 ~0.056/0.057 (Sep/Oct).
Two player-side rows/eligible game; no usernames (player hashes only).

Player-side TF prevalence by quintile is weakly **decreasing** with rating in 3+0 (Q1 ~0.16 → Q5 ~0.13)
and 5+0 (slight), ~flat in 10+0 (~0.055). Descriptive; not causal.

## 20. Month replication

5-class classifier on M(c): all-games 3+0/10+0 replicated, 5+0 directional; endgame 5+0 replicated, 10+0
directional, 3+0 null. Cross-control contrasts null. (T2 descriptive-stability language not used here.)

## 21. Clustered uncertainty

Mover-player-clustered primary (500 draws, seed 20240621; player hashes clustered across months+controls
in the pooled fit), game-clustered available as secondary. Two-way game/player not implemented in the
sufficient-statistics bootstrap (16.2D limitation) — mover clustering captures most dependence given tiny
cross-control overlap.

## 22. Robustness matrix

**Executed** (main report §19 has the full executed matrix with M-contrast estimates):
- R1 board-decided (§17, executed) — mixed; RM3 still null.
- R2 endgame-only (§18, executed) — **sign reversal** to attenuation; RM2 conditioning-sensitive.
- R3 continuous percentile (§10, executed) — agrees all-phase; RM3 unaffected.
- R4 raw 200-Elo bins (§4 main report, executed) — descriptive; ES mean falls with rating (RM1).
- R5 clipped-CP (executed) — same direction; RM2/RM3 unchanged.
- R6 ES≥0.10 LPM (executed) — same direction; RM2/RM3 unchanged.
- R7 anomaly-excluded (executed) — ≈ primary; RM2/RM3 unchanged.
- R8 month-specific (§14/§18, executed) — replication classes reported.
- R9 mover-player clustering (executed; the primary uncertainty).
- R10 game-clustered (executed) — directionally consistent with mover-player primary.
- R11 unweighted rows (executed) — same direction.
- R12 eval localization, near_equal+slight & decided (executed) — see main report §19.
- R13 categorical vs continuous three-way (executed) — percentile diff agrees with categorical M all-phase.

**Not executed (optional, justified):** R14 single-control players (tiny cross-control overlap → expected
negligible); R15 player fixed effects (needs selection/sample-loss audit first); R16 min-decisions
restriction (not needed for the locked family). Conclusion: all-phase amplification stable across
R5/R6/R7/R10/R11/R3; not stable under R2 (endgame) → RM2 conditioning-sensitive; RM3 null unchanged
across every executed spec.

## 23. Figure inventory

`reports/figures/phase_16_2_rating_clock_moderation/` (PNG, dpi 110): _01 clock×ES by quintile (Q1/Q3/Q5)
· _02 D(c,Q1..Q5) by quintile · _03 rating×clock heatmap · _04 board-decided moderation (10+0 low-Q
marked sparse) · _05 within-control M(c) (Holm p) · _06 cross-control moderation · _07 player-side TF by
quintile · _08 endgame-only moderation (sign-flip) · _09 five-test summary. All titled, axis-labeled,
rating representation stated, CIs shown, "descriptive/not causal" framing; inspected _02 + _08 visually.

## 24. Claim-status update

| Claim | Status |
|---|---|
| RM1 average rating gradient | supported descriptively (higher quintiles lower average loss; positive control) |
| RM2 within-control rating moderation | **present but conditioning-sensitive** — amplification all-phase (Holm-sig), attenuation within endgames (5+0 replicated, 10+0 directional); NOT a single-direction claim |
| RM3 cross-control rating moderation | **NOT supported** (M(3+0)−M(10+0), M(5+0)−M(10+0) contain 0, Holm 0.76) |
| RM4 board-decided moderation | mixed/unresolved (3+0 amplification persists; 5+0/10+0 ns under Holm) |
| RM5 player-side time-forfeit gradient | weak descriptive decrease with rating in 3+0/5+0, flat 10+0 |

## 25. Non-claims

No causal claims. "Buffer"/"attenuation"/"amplification" are descriptive contrasts. NOT: higher rating
causes time-pressure resilience; rating protects from clock pressure; higher-rated immune to low clock;
lower-rated reason worse; rating causes fewer blunders; fast chess harms lower-rated players; time
pressure causes move-quality degradation; same raw Elo = same skill across pools; 3+0 ratings comparable
to 10+0; Stockfish is ground truth; T2 established equivalence; sharpness moderation resolved; DRAW
solved. The all-phase amplification is not stable under endgame restriction and is not a
skill-harms-under-pressure claim; no single mechanism is identified for the sign reversal. The endgame
attenuation is modest, non-uniform, descriptive. C4 & C3c unchanged.

## 26. Recommended next ticket

**16.2F — Rating-Moderation Claim Consolidation / Phase 16 Closure Audit** (doc-only): consolidate the
conditioning-sensitive RM2 (amplification all-phase vs attenuation endgame), the null RM3, board-decided
+ player-side results; reconcile with T1–T4; decide Phase-16 closure vs increment branch. Do NOT jump to
increment extraction or Phase 17 without consolidation.
