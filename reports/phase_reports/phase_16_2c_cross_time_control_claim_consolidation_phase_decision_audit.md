# Phase 16.2C — Cross-Time-Control Claim Consolidation / Phase 16 Decision Audit

**Ticket:** 16.2C — Cross-Time-Control Claim Consolidation / Phase 16 Decision Audit (audit/report-only)
**Status:** complete — report-only. No code, no models, no figures, no Stockfish, no extraction, no
Parquet/JSON/model/figure artifact modified.

> All language predictive/descriptive — **NOT causal**. Raw Lichess ratings are NOT comparable across
> control pools (within-control quintiles only). Stockfish eval is objective context, not ground truth.
> The expected-score transform is reused across controls (a comparability assumption, not refit). T2 is
> descriptive stability, NOT a formal equivalence result. C3c sharpness moderation remains unresolved.

## 1. Executive summary

Phase 16 (no-increment cross-time-control, 3+0 / 5+0 / 10+0 × 2024-09 / 2024-10) is consolidated here
into four frozen claims:

- **T1 — game-level time-forfeit prevalence:** 3+0 > 5+0 > 10+0, both months. **Replicated descriptive
  ordering.**
- **T2 — average move quality:** mean next-move ES loss broadly similar across controls. **Descriptively
  stable** — NOT a formal equivalence result, NOT in the replication classifier.
- **T3 — within-control clock gradient:** lower clock fraction → higher ES loss within every control
  after conditioning. **Replicated conditional association**; shrinks but stays positive board-decided;
  survives mover-player clustering.
- **T4 — cross-control moderation:** the conditional low-clock gradient is steeper in faster controls.
  **Replicated conditional moderation**; survives mover-player clustering.

The interpretation boundary is preserved (eight simultaneous facts in §8). The settled result is NOT
"fast chess causes blunders" and NOT "time pressure only affects flagging." The recommended next branch
is **16.2D — Rating-Bucket / Clock Moderation Audit** (design-only): does skill buffer the low-clock
move-quality gradient, and does that buffer differ across controls? Increment contrasts and Phase 17
packaging are deferred until rating moderation is characterized.

## 2. Evidence base reviewed

- Phase 16 design + implementation: 16.2A audit, 16.2B implementation report, main analysis report
  `cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md` (incl. executed R8).
- Phase 16 extraction lineage: 16.1C matched-size extraction report.
- Phase 15 dense 10+0 lineage: `dense_controlled_move_quality_model_10plus0_...`, `constraint_atlas_10plus0_...`.
- Phase 11 termination decomposition: `phase_11_2a/b/c`, `termination_decomposition_{2024_09,2024_10,combined}.md`,
  `player_clustered_termination_decomposition.md`.
- Phase 15.5 sharpness closure: `phase_15_5c_sharpness_result_consolidation_c3c_claim_update.md` (C3c UNRESOLVED).
- Governance: ROADMAP, EXPERIMENT_LOG (through EXP-054), PREREGISTRATION.
- Code/tests inspected to confirm executed estimands + R8 (no modification): `cross_time_control_analysis.py`,
  `test_cross_time_control_analysis.py`.

## 3. Phase 16 dataset and estimands

Six dense artifacts (status ok, 0 dup keys, both colors, 1.0 player-hash, no usernames), headline
~1.36–1.42M rows each. Cross-control axes: clock = `clock_fraction` (= clock_before_s/initial_time_s);
rating = within-control × month quintiles. Outcome: `expected_score_loss` (primary), `cp_loss_clipped`
(transform-free secondary). Within-control models unweighted; pooled = game-normalized weights, equal
control-month aggregate weight. Game-clustered sufficient-statistics bootstrap (500 draws, seed
20240621) primary; mover-player-clustered (200 draws) robustness.

## 4. T1 claim consolidation

**Statement:** Observed game-level time-forfeit prevalence is higher in 3+0 than 5+0 and higher in 5+0
than 10+0 across both sampled months.

**Status: replicated descriptive ordering.** Observed prevalence (one row per game): 3+0 0.292/0.301,
5+0 0.226/0.226, 10+0 0.115/0.116 (Sep/Oct). Adjusted logit odds ratios vs 10+0: 3+0 ≈ 3.22, 5+0 ≈ 2.23.

Clarifications: **one row per game** (NOT move-row termination share — longer time-forfeit games inflate
the move-level share, a different denominator); **raw prevalence is the primary finding**; the minimally
adjusted logistic model (TC + month + rating quintile) is secondary support; the game-length-adjusted
model is secondary and cautiously interpreted (game length is partly downstream of the termination
process); **no causal time-control effect** is asserted.

## 5. T2 claim consolidation

**Statement:** Average observed next-move expected-score loss is broadly similar across the sampled 3+0,
5+0, and 10+0 populations (mean ~0.0337 / ~0.0350 / ~0.0346).

**Status: descriptively stable.** Explicitly: **no formal equivalence margin; no equivalence test; no
replicated-equivalence classification.** Small observed mean differences remain (5+0 slightly highest,
3+0 slightly lowest). "Broadly similar" must NOT become "identical" or "unaffected by time control."
T2 remains **outside the coefficient replication classifier** (which covers only the T1/T3/T4 contrasts);
it is a descriptive similarity statement, not a difference/equivalence estimate.

## 6. T3 claim consolidation

**Statement:** Within each observed time control, lower remaining clock fraction is associated with
higher next-move expected-score loss after conditioning on eval band, phase, within-control rating
quintile, month, color, termination channel, and anomaly flags.

**Status: replicated conditional association in all three controls.** Critical-vs-high contrast: 3+0
+0.0117, 5+0 +0.0077, 10+0 +0.0056 (all CIs exclude 0, both months). Qualifications: predictive/
descriptive, NOT causal; **eval state dominates** the move-loss variation (clock is the smaller term);
**phase conditioning is mandatory**; **extreme-low-clock rows are primarily late-game** (critical-clock
≈ endgame); **board-decided-only gradients remain positive but smaller** (3+0 +0.0062, 5+0 +0.0051,
10+0 +0.0031); **survives mover-player clustering** (§10).

## 7. T4 claim consolidation

**Statement:** The conditional clock-loss gradient is steeper in the sampled faster controls than in
10+0.

**Status: replicated conditional moderation.** Critical-clock interaction vs 10+0: 3+0 × critical
+0.0089, 5+0 × critical +0.0033 (both CIs exclude 0, both months). Qualifications: this is an
**interaction, not a causal time-control effect**; **survives mover-player clustering** (§10); **partly
flagging-related** (attenuates board-decided-only); it does **not** imply all moves in faster controls
are worse (T2: average loss broadly similar); it does **not** establish a psychological mechanism.

## 8. Board-decided and flagging-channel reconciliation

Eight facts the project preserves **simultaneously** (none alone is the whole story):

1. Flagging prevalence differs dramatically across controls (T1).
2. Average observed move-quality loss is broadly similar across controls (T2).
3. Within every control, lower clock fraction is associated with worse next moves (T3).
4. The conditional low-clock gradient is steeper in faster controls (T4).
5. Part of the gradient is related to the flagging channel (board-decided attenuation).
6. A smaller gradient remains in board-decided games (T3 board-decided: +0.0062/+0.0051/+0.0031).
7. Extreme-low-clock positions are heavily concentrated in endgames.
8. Eval state remains a larger predictor of move loss than clock.

This must not be simplified to "fast chess causes blunders" or "time pressure only affects flagging."

## 9. Phase and eval-state localization

`clock_fraction` and game phase are heavily confounded: critical-clock (≤0.05) cells are almost entirely
endgame (opening critical ≈ 0). Therefore controlled low-clock contrasts are conditional on phase, and
extreme-low-clock estimates describe **low-clock variation within late-game positions**, not a generic
all-game clock effect. Eval state is the dominant predictor of next-move loss; clock is a small,
replicated secondary term. These are localization caveats, not weaknesses in the replicated direction.

## 10. Player-clustered robustness

Executed R8 (cluster key game_id → mover_player_hash, 200 draws, seed 20240621). All five headline
targets survive — same sign, near-unchanged point estimates, player-clustered CIs exclude zero:

| Target | game-clustered | player-clustered | sign | player CI excl 0 | player clusters |
|---|---|---|---|---|---|
| T3 3+0 critical vs high | +0.0117 | +0.0117 [+.0110,+.0124] | agrees | yes | 22,332 |
| T3 5+0 critical vs high | +0.0077 | +0.0077 [+.0068,+.0086] | agrees | yes | 26,114 |
| T3 10+0 critical vs high | +0.0056 | +0.0056 [+.0046,+.0064] | agrees | yes | 31,381 |
| T4 3+0 × critical (vs 10+0) | +0.0089 | +0.0089 [+.0075,+.0102] | agrees | yes | 77,408 |
| T4 5+0 × critical (vs 10+0) | +0.0033 | +0.0033 [+.0023,+.0048] | agrees | yes | 77,408 |

T3 and T4 are not weakened by mover-player clustering. (Cross-month player overlap ~18–22% → months not
fully independent; game-clustered CIs primary, player-clustered confirmatory.)

## 11. Reconciliation with the Phase 11 outcome result

Phase 11 found the final-outcome clock signal is **primarily localized to the time-forfeit (flagging)
channel** (board-decided E3→E4 outcome residual collapses/sign-reverses; the signal is substantially
the flagging channel, survives clustering 11.3B). Phase 16 finds the move-quality clock gradient
**persists in board-decided games** but is **smaller** than the all-games gradient.

**Safe synthesis:** The strongest clock-related cross-control difference is observed in
termination/flagging prevalence (T1). A smaller conditional association with next-move quality remains
even after restricting to board-decided games (T3 board-decided). These are consistent: the flagging
channel dominates the *outcome* signal, while a smaller board-play association survives at the *move*
level. Do **not** say "time pressure only affects flagging" — board-decided gradients are positive — and
do **not** say the outcome residual is rescued — it remains collapsed (Phase 11).

## 12. Reconciliation with the Phase 15 10+0 result

The Phase 16 10+0 `clock_fraction` analysis is **directionally compatible** with the earlier Phase 15
absolute-clock lineage (small, monotone, replicated low-clock move-quality association after eval/phase/
rating/termination conditioning). Phase 16 **refines** it by showing: (a) the association generalizes
across 3+0, 5+0, and 10+0; (b) the gradient differs by control (T4); (c) normalized `clock_fraction`
provides the cross-control axis (absolute seconds are not comparable); (d) rating pools require
within-control normalization (3+0 quintile cutpoints ~200 Elo above 5+0/10+0). No conflict with Phase 15.

## 13. Reconciliation with the sharpness arc

**C3c (clock × sharpness move-quality moderation) remains UNRESOLVED** (Phase 15.5C: bounded unresolved,
underpowered, sparse checkpoint overlap). The strong Phase 16 clock-fraction result does **NOT**
retroactively promote sharpness moderation: sharpness moderation and clock-fraction moderation are
**separate claims** on different constructs (objective value fragility vs remaining clock). T4 is a
clock × time-control interaction, not a clock × sharpness interaction. C3c stays neither confirmed nor
disproven.

## 14. Final safe Phase 16 language

> Across two monthly samples of observed Lichess 3+0, 5+0, and 10+0 games, game-level time-forfeit
> prevalence is substantially higher in faster controls. Average next-move expected-score loss is
> broadly similar across the sampled controls, although this is a descriptive observation rather than a
> formal equivalence result. Within every control, lower remaining clock fraction is associated with
> higher next-move loss after conditioning on observed position, phase, rating-quantile, month, color,
> termination, and anomaly fields, and this conditional gradient is steeper in the faster controls. The
> gradients shrink but remain positive in board-decided games and survive mover-player-clustered
> uncertainty checks. These results are predictive and descriptive, not causal, and extreme-low-clock
> estimates primarily describe late-game states.

## 15. Forbidden interpretations

NOT: time pressure causes worse reasoning; low clock causes blunders; faster time controls cause worse
chess; faster controls cause flagging; faster controls do not harm move quality; time pressure affects
only flagging; players reason equally well at every speed; 3+0/5+0/10+0 are equivalent in move quality;
T2 is replicated equivalence; Stockfish is ground truth; raw ratings comparable across pools;
cross-time-control differences are causal; sharpness moderation confirmed or disproven; DRAW solved.

## 16. Phase 16 claim-status table

| Claim | Status | Replication | Robustness | Main limitation |
|---|---|---|---|---|
| T1 termination ordering | supported | replicated descriptive ordering | raw + adjusted game-level | non-causal |
| T2 average ES similarity | supported descriptively | not an equivalence classification | two months + CP context | no equivalence test |
| T3 within-control gradients | supported | replicated | board-decided + player-clustered | endgame concentration |
| T4 cross-control moderation | supported | replicated | player-clustered + weighting checks | no causal mechanism |
| C3c sharpness moderation | unresolved | not replicated conclusively | sparse checkpoint overlap | underpowered |

## 17. Remaining scientific gaps

- **Rating moderation** (does skill buffer the low-clock gradient; does the buffer differ by control) — next branch.
- Increment contrast (3+0 vs 3+2, 5+0 vs 5+3).
- Think-time allocation / loss-rate signatures.
- Broader month/time-period replication (only two months).
- Stronger causal identification (currently descriptive/predictive only).
- Human-difficulty measures distinct from objective value fragility.

## 18. Rating-bucket moderation rationale (next analysis)

Phase 16 used rating quintiles as **controls** and produced a rating×clock heatmap (Fig 6), but did NOT
formally test the moderation terms `clock_fraction × rating_quintile` or
`clock_fraction × rating_quintile × time_control`. Questions for 16.2D/E:

1. Does rating **buffer** the low-clock move-quality gradient (smaller gradient for stronger players)?
2. Does that buffer **differ across** 3+0, 5+0, 10+0?
3. Do stronger players retain an advantage under critical-clock states?
4. Does rating moderation survive **board-decided-only** restriction?
5. Is the pattern **replicated** across both months?
6. Are raw 200-Elo-bin visualizations consistent with within-control quintile models?

Primary rating representation: **within-control × month quintiles.** Secondary visualization: raw 200-Elo
bins **within each control only.** Never compare the same raw rating as equivalent across control pools.
This is high-value, already-supported (data + module + bootstrap exist), and directly answers whether
skill buffers clock constraints — the logical step before adding increment as another interaction axis.

## 19. Increment-analysis timing decision

**Defer increment controls until after rating moderation.** The no-increment baseline should first be
fully characterized across rating groups before adding increment as another major interaction axis.
Future candidates: 3+0 vs 3+2, 5+0 vs 5+3 (blitz increment, better powered than rapid). **No extraction
in 16.2D/E.**

## 20. Think-time diagnostic timing decision

Recorded as an **optional later branch** (not the immediate next ticket): Think-Time Loss-Rate /
Flagging-Signature Diagnostic. Candidate metrics: `expected_score_loss / max(think_time_net_s, 1)`,
`cp_loss_clipped / max(think_time_net_s, 1)`. Deferred behind rating moderation.

## 21. Packaging-readiness decision

**Do not move to Phase 17 yet.** The central cross-control result is strong, but rating moderation is a
high-value, already-supported next analysis that directly answers whether skill buffers clock
constraints. Packaging waits until the rating-moderation question is resolved.

## 22. Recommended next ticket

**16.2D — Rating-Bucket / Clock Moderation Audit** (design-only). It should precede **16.2E —
Rating-Bucket Atlas / Controlled Interaction Implementation**. Neither 16.2D nor 16.2E is implemented in
this ticket.

## 23. Open questions for Malachi

1. **16.2D scope** — confirm the moderation target is `clock_fraction × rating_quintile` within control
   first, then the three-way `× time_control`? (Recommended: yes — within-control first, three-way second.)
2. **Rating granularity** — quintiles primary with raw 200-Elo bins as secondary visualization only?
   (Recommended: yes.)
3. **Board-decided-only** — make it a mandatory parallel population for the moderation test (as in T3)?
   (Recommended: yes.)
4. **Increment vs rating ordering** — confirm rating moderation precedes any increment extraction?
   (Recommended: yes.)

---

**Non-claims (this ticket):** report-only; no code/models/figures/Stockfish/extraction/data changes.
No causal claims. T2 is descriptive stability, not equivalence. C3c unresolved (not promoted by T4).
Raw ratings not cross-pool comparable. Stockfish not ground truth. No "fast chess causes blunders",
"time pressure only affects flagging", "faster controls cause flagging", "players reason equally well",
"DRAW solved". C4 & C3c unchanged. PREREGISTRATION unchanged.
