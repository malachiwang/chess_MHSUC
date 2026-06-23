# Phase 16.2F — Rating-Moderation Claim Consolidation / Phase 16 Closure Audit

**Ticket:** 16.2F — Rating-Moderation Claim Consolidation / Phase 16 Closure Audit (documentation /
claim-consolidation / phase-decision audit only)
**Status:** complete — report-only. No code, no models, no figures, no Stockfish, no extraction, no
Parquet/JSON/model/figure modified.

> Predictive/descriptive only — NOT causal. "Buffer"/"attenuation"/"amplification" are descriptive
> contrast labels, never causal mechanisms. Raw Lichess ratings are NOT comparable across speed pools
> (within-control × month rating quintiles/percentiles are the inferential representation; absolute Elo
> mappings are interpretation aids only). Stockfish eval is objective context, not ground truth. T2 is
> descriptive stability, NOT equivalence. C3c sharpness moderation remains unresolved.

## 1. Executive summary

Consolidates the rating × clock results (16.2E) with the settled cross-time-control claims (T1–T4) and
freezes the RM1–RM5 boundaries. The headline guard: **the rating interaction is real but its DIRECTION is
conditioning-sensitive — it must NOT become a "rating resilience" (or "rating vulnerability") story.**

- **RM1** average rating gradient: supported descriptively (move loss falls with rating; positive control).
- **RM2** within-control rating moderation: **conditioning-sensitive interaction** — all-phase
  amplification (Holm-significant), endgame/eval-localized attenuation or sign instability; no universal
  direction; no mechanism identified.
- **RM3** cross-control difference in rating moderation: **not supported** (both contrasts contain 0, Holm).
- **RM4** board-decided rating moderation: **mixed/unresolved**.
- **RM5** player-side time-forfeit gradient: **weak descriptive** (validated denominator).

Decision: **close the no-increment Phase 16 baseline after 16.2F.** Next branch: **16.3A —
Increment-Control Matched-Pair Feasibility / Design Audit** (3+0 vs 3+2, 5+0 vs 5+3). Phase 17 packaging
deferred pending the increment-feasibility decision.

## 2. Evidence reviewed

16.2D design audit; 16.2E implementation report + main analysis report (incl. executed robustness matrix,
percentile→Elo landmarks, player-side denominator proof); 16.2C cross-TC consolidation; 16.2B
implementation + main report; Phase-15 dense 10+0 controlled model; Phase-15.5C sharpness closure;
governance (ROADMAP, EXPERIMENT_LOG through EXP-057, PREREGISTRATION); `rating_clock_moderation.py` +
tests (read-only, to verify estimands + executed robustness).

## 3. Phase 16 scientific lineage

10+0 dense move-quality (Phase 15.4) → cross-time-control 3+0/5+0/10+0 (16.1 extraction → 16.2B analysis
→ 16.2C consolidation: T1–T4) → rating × clock moderation (16.2D audit → 16.2E implementation: RM1–RM5) →
this closure audit (16.2F). All predictive/descriptive; clock axis = `clock_fraction`; rating axis =
within-control × month quintiles/percentile.

## 4. RM1 consolidation

**Statement:** Average observed move loss generally decreases with relative rating within the sampled
control-month pools. **Status: supported descriptively.** (Raw 200-Elo bins: ES mean falls monotonically
with rating in every control — e.g. 3+0 <1200 ≈0.0453 → 2200+ ≈0.0249.) Qualifications: not causal; not
the primary rating-moderation claim; absolute Elo distributions differ across pools; raw-bin patterns are
within-control only (not cross-pool skill categories). This is an expected positive control.

## 5. RM2 consolidation

**Statement:** Relative rating modifies the modeled critical-clock move-quality contrast, but the
direction is not stable across analysis populations. **Status: conditioning-sensitive interaction.**

Detail: D(c,q) = adjusted ES loss(critical clock) − adjusted ES loss(high clock); M(c) = D(c,Q5) − D(c,Q1).
- **All-phase** (categorical AND percentile): amplification — M(3+0) ≈ +0.0083, M(5+0) ≈ +0.0049,
  M(10+0) ≈ +0.0068; all three survive the five-test Holm procedure within controls. Percentile 0.90−0.10
  diff agrees (positive all controls).
- **Endgame-restricted**: M(3+0) ≈ null (−0.0006), M(5+0) ≈ −0.0067 (replicated attenuation), M(10+0) ≈
  −0.0044 (directional attenuation).
- **Eval-localized** (R12): near_equal+slight flips M(3+0) to −0.0058*; decided flips M(5+0) to −0.0078*.

No single universal direction is supported; **no mechanism is identified.** RM2 must NOT be summarized as
merely "supported" — the conditioning qualifier is mandatory.

## 6. RM3 consolidation

**Statement:** The strength or direction of rating moderation does not clearly differ across the sampled
3+0, 5+0, and 10+0 controls. **Status: not supported.** Evidence: both locked cross-control contrasts
contain zero — M(3+0)−M(10+0) +0.0015 [−0.0026,+0.0058], M(5+0)−M(10+0) −0.0019 [−0.0063,+0.0023]; Holm
p ≈ 0.76; consistent under game-clustering, clipped-CP, ES≥0.10, anomaly-excluded, unweighted. This is
evidence of an **unresolved/null cross-control difference, NOT evidence of exact equality.**

## 7. RM4 consolidation

**Statement:** Board-decided-only rating moderation is mixed and does not yield a stable cross-control
pattern. **Status: mixed/unresolved.** 3+0 all-phase amplification persists (M +0.0137*); 5+0 ≈ −0.0038
(ns); 10+0 ≈ +0.0083 (unadj excl 0 but Holm ns). Sparse 10+0 low-quintile critical board-decided cells
(~199–213 games/movers, 16.2D) limit categorical interpretation → the continuous-percentile route is the
cleaner sparse-tail read. No universal board-play moderation claim.

## 8. RM5 consolidation

**Statement:** Observed player-side time-forfeit prevalence decreases weakly with relative rating in 3+0
and 5+0 and is approximately flat in 10+0. **Status: weak descriptive pattern.** Validated denominator
(see §18): 144,128 eligible games, 288,256 player-side rows, 29,693 positives, overall prevalence 0.1030.
By quintile: 3+0 ~0.16→0.13, 5+0 slight decrease, 10+0 ~flat 0.055. NOT evidence that rating causes
time-management resilience.

## 9. Absolute-Elo interpretation

16.2E §4 supplies, for all six control-month pools: Q1–Q5 absolute-Elo ranges; P10/P25/P50/P75/P90 Elo
landmarks; row/game/mover counts; raw 200-Elo-bin summaries within control. Landmarks confirm the pools
differ (e.g. 2024-09 3+0 P10 ≈ 1313 / P90 ≈ 2174 vs 10+0 P10 ≈ 1097 / P90 ≈ 2014). **Distinction
preserved:** relative rating rank is the inferential representation; absolute Elo mappings are
interpretation aids; raw Elo bins are descriptive within controls only and are not equivalent categories
across speed pools.

## 10. Phase and eval localization (the central interpretation problem)

**Why does the all-phase model show amplification while endgame- and eval-localized models show
attenuation or sign instability?** Critical-clock states are overwhelmingly late-game; conditioning on
phase or eval band changes the population being contrasted. **Allowed conclusion:** the all-phase rating
interaction is **not stable under phase and evaluation localization**; the sign changes are consistent
with phase composition, residual composition differences, or phase-specific heterogeneity, but **the
current analysis does not identify a single mechanism.** Explicitly NOT claimed: that the sign change is
proven to be caused by phase composition; that higher-rated players reach low-clock states more often as
an established mechanism; that stronger players are harmed more / protected; that endgame attenuation
demonstrates psychological resilience.

## 11. Robustness reconciliation

Executed matrix (16.2E §19), not a capability list:

| Spec | Executed? | Bearing on RM2/RM3 |
|---|---|---|
| R1 board-decided | yes | mixed (RM4); RM3 still null |
| R2 endgame-only | yes | **sign reversal** to attenuation → RM2 conditioning-sensitive |
| R3 continuous percentile | yes | agrees all-phase amplification; RM3 unaffected |
| R4 raw 200-Elo bins | yes | descriptive RM1; ES falls with rating |
| R5 clipped-CP | yes | same direction all-phase; cross-control null |
| R6 ES≥0.10 (LPM) | yes | same direction; cross-control null |
| R7 anomaly-excluded | yes | ≈ primary |
| R8 month-specific | yes | replication classes reported |
| R9 mover-player clustering | yes | primary uncertainty |
| R10 game clustering | yes | directionally consistent with mover-player |
| R11 unweighted rows | yes | same direction |
| R12 eval localization | yes | **sign flips** in some strata → conditioning-sensitive |
| R13 categorical vs percentile 3-way | yes | percentile diff agrees with categorical M all-phase |
| R14/R15/R16 | no (justified) | optional; not needed for the locked family |

**Central conclusion:** the *presence* of a rating interaction in all-phase models is robust to metric,
weighting, anomaly, and clustering choices; its *direction* is NOT robust to phase and evaluation
localization. This distinction is the core RM2 finding.

## 12. Reconciliation with T1–T4

T1 replicated descriptive flagging ordering (3+0 > 5+0 > 10+0); T2 descriptively stable average move loss
(not equivalence); T3 replicated conditional within-control clock gradients; T4 replicated conditional
cross-control clock moderation. **Rating results refine but do not overturn T1–T4.** Safe relationship:
the low-clock gradient exists across all controls, but the evidence does not support a simple universal
account of how relative rating modifies it.

## 13. Reconciliation with Phase 11 termination findings

Phase 11: the final-outcome clock signal is primarily associated with the time-forfeit (flagging)
channel. Phase 16: a smaller move-quality association remains in board-decided games. Rating analysis
adds: rating-related variation in move-quality and player-side time-forfeit patterns is heterogeneous and
conditioning-sensitive. **Do NOT claim rating explains the Phase 11 flagging result.**

## 14. Reconciliation with Phase 15 10+0 findings

The Phase 16 10+0 clock-fraction gradient is directionally compatible with the Phase 15 absolute-clock
lineage (small, monotone, replicated, eval-dominated). The rating layer adds a 10+0 within-control
moderation that is all-phase amplification / endgame attenuation — same conditioning-sensitivity as the
faster controls. No conflict with Phase 15.

## 15. Reconciliation with sharpness

**C3c (clock × sharpness move-quality moderation) remains UNRESOLVED.** The rating interaction is a
separate construct (relative rating, not objective value fragility) and does NOT license any inference
about human difficulty, obviousness, or sharpness mechanisms. C3c stays neither confirmed nor disproven.

## 16. Final Phase 16 claim table

| Claim | Final status | Replication | Robustness | Main limitation |
|---|---|---|---|---|
| T1 termination ordering | supported | replicated descriptive | raw + adjusted | non-causal |
| T2 average move-quality similarity | supported descriptively | not equivalence-classified | two months, CP context | no equivalence test |
| T3 within-control clock gradient | supported | replicated | board-decided, player-clustered | late-game concentration |
| T4 cross-control clock moderation | supported | replicated | weighted, player-clustered | no causal mechanism |
| RM1 average rating gradient | supported descriptively | stable descriptive pattern | raw bins, percentile | expected positive control |
| RM2 rating moderation | conditioning-sensitive | all-phase supported; localized direction unstable | R1–R13 | no universal direction |
| RM3 moderation differs by control | not supported | cross-control contrasts null | Holm + clustering | not proof of equality |
| RM4 board-decided rating moderation | mixed/unresolved | non-uniform | sparse-tail-aware | weak 5+0/10+0 evidence |
| RM5 player-side TF rating gradient | weak descriptive | non-uniform | validated denominator | no causal identification |
| C3c sharpness moderation | unresolved | not conclusive | sparse overlap | underpowered |

## 17. Final safe Phase 16 synthesis

> Across two monthly samples of observed Lichess 3+0, 5+0, and 10+0 games, faster controls have
> substantially higher game-level time-forfeit prevalence, while average next-move expected-score loss is
> broadly similar across the sampled controls. Within each control, lower remaining clock fraction is
> associated with greater next-move loss after conditioning on observed position, phase, relative rating,
> month, color, termination, and anomaly fields, and this gradient is steeper in faster controls.
> Relative rating also interacts with the critical-clock gradient, but the direction is
> conditioning-sensitive: all-phase models show amplification, whereas endgame- and eval-localized
> analyses show attenuation or instability in some controls. The evidence therefore does not support a
> universal claim that higher relative rating either buffers or amplifies low-clock effects.
> Cross-control differences in rating moderation are unsupported. All results are predictive and
> descriptive, not causal.

## 18. Player-side denominator (validation)

145,020 total games → 144,128 eligible (892 ambiguous draw-timeouts excluded) → 288,256 player-side rows
(= 2 × eligible, verified) → 29,693 positive decisive time-forfeit-loss rows (one loser per decisive TF
game) + 258,563 zero rows (both sides of every eligible non-TF game) → overall player-side prevalence
≈ 0.1030 (≈ half the game-level TF rate). This is genuine prevalence including non-TF zeros, NOT a
fraction of time-forfeit games.

## 19. What remains unresolved

- The mechanism behind the RM2 all-phase-vs-localized sign reversal (composition vs heterogeneity — not identified).
- RM3 cross-control difference (null/unresolved, not equality).
- RM4 board-decided moderation in 5+0/10+0 (weak/sparse).
- Causal identification of any clock/rating association (out of scope; descriptive only).
- C3c sharpness moderation (unresolved, underpowered).
- Increment effects on clock/move-quality/termination (the next branch).
- Broader month/time-period replication (only two months); think-time allocation signatures; human-difficulty measures distinct from objective value fragility.

## 20. Phase 16 closure decision

**Close the no-increment Phase 16 baseline after 16.2F.** Rationale: T1–T4 settled with caveats; rating
moderation implemented and consolidated (RM1–RM5); remaining no-increment extensions are lower-priority or
mechanism-seeking; further model slicing risks diminishing returns and multiplicity; the next high-value
contrast is whether increment changes clock, move-quality, and termination patterns. This does NOT declare
every human-constraint question solved — unresolved questions are recorded in §19.

## 21. Increment-branch rationale

**16.3A — Increment-Control Matched-Pair Feasibility / Design Audit.** Candidate comparisons: 3+0 vs 3+2,
5+0 vs 5+3. The audit should determine: available matched sample sizes; whether existing raw caches
suffice; increment-aware clock representations; `clock_fraction` vs increment-buffer variables; matched
base-time vs total-time estimands; rating-pool normalization; termination-channel comparability;
extraction cost; whether new dense extraction is justified. No increment extraction in 16.2F.

## 22. Packaging-readiness decision

**Defer Phase 17 packaging until the increment-feasibility decision.** The no-increment result is mature,
but the increment comparison is a natural, high-value final constraint axis that may materially change the
project narrative. If increment feasibility is poor, Phase 17 can begin after 16.3A.

## 23. Recommended next ticket

**16.3A — Increment-Control Matched-Pair Feasibility / Design Audit** (design-only). Do NOT run increment
extraction or begin Phase 17 packaging in or before it.

## 24. Open questions for Malachi

1. **Phase 16 closure** — confirm closing the no-increment baseline now (vs adding think-time/sharpness
   no-increment extensions first)? (Recommended: close now; extensions optional later.)
2. **Increment candidates** — 3+0 vs 3+2 and 5+0 vs 5+3 as the matched pairs? (Recommended: yes — blitz
   increment is better powered than rapid per 16.1A.)
3. **Increment estimand** — matched base-time vs matched total-time as the primary contrast? (Recommended:
   audit both in 16.3A; lock there.)
4. **Packaging timing** — Phase 17 strictly after 16.3A feasibility? (Recommended: yes.)

---

**Non-claims (this ticket):** report-only; no code/models/figures/Stockfish/extraction/data changes. No
causal claims. NOT: higher rating causes resilience; rating protects from clock pressure; higher-rated
immune to low clock; lower-rated reason worse; rating causes fewer blunders; faster controls harm
lower-rated players; higher-rated suffer more under pressure; skill buffers/amplifies time pressure; the
moderation mechanism is identified; rating moderation differs across controls; raw ratings comparable
across pools; time pressure causes worse reasoning; low clock causes blunders; Stockfish is ground truth;
T2 established equivalence; sharpness moderation resolved; DRAW solved. C4 & C3c unchanged. PREREGISTRATION
unchanged.
