# Synthesis Readiness — Claim Architecture (chess-MHSUC)

*Reusable claim architecture for the eventual public-facing writeup. Produced by Ticket
16.0A (synthesis-readiness audit). This is a planning/consolidation document — it makes no
new empirical claim and runs no model. Process/decision record:
`reports/phase_reports/phase_16_0a_synthesis_readiness_public_claim_audit.md`.*

## Claim hierarchy

### Level 1 — Headline claims (safe for abstract / public summary)

1. In Lichess 10+0 games, **clock information improves final-outcome prediction** beyond
   Stockfish evaluation and rating (E3→E4: 2024-09 −0.0138 [−0.0186, −0.0091]; 2024-10
   −0.0120 [−0.0177, −0.0062] log-loss; replicated, game-clustered, survives player
   clustering).
2. **Termination decomposition shows this outcome-level clock signal is largely a
   timeout/flagging channel**, not direct evidence of degraded board play: the board-decided
   residual collapsed/sign-reversed (2024-09 +0.0010 cz; 2024-10 +0.0060) while the
   time-forfeit channel is large (−0.118 / −0.131). Replicated; survives player clustering.
3. At the **next-move level, evaluation state dominates** expected-score loss; after
   controlling for eval band, rating, checkpoint, month, and termination, **clock retains a
   small, replicated association** with next-move loss (`60_180` vs `over_180` pooled +0.0034
   [+0.0015, +0.0052]), ~5–8× smaller than the eval-band structure. Predictive/descriptive.

### Level 2 — Secondary claims (valid, must be caveated)

- The small move-quality clock association **survives the pre-registered robustness checks**
  (continuous-eval control, late-only, board-decided-only, rating spec, metric, clustering;
  15.1F).
- It remains same-sign under **board-decided-only** modeling (not solely a time-forfeit
  artifact at the move level).
- **Player-clustered uncertainty does not eliminate** the small move-quality association nor
  the flagging-channel / eval-band findings (11.3B).
- **MultiPV value-fragility ("sharpness") features are feasible and stable** across both
  months (`sharp_value_fragility_v1` base rate ≈0.14; FEN round-trip 1.0; depth-stable
  composite).

### Level 3 — Exploratory / diagnostic (not headline)

- Constraint Atlas descriptive move-quality patterns (eval-band, clock, rating, checkpoint).
- Surface-bait diagnostics (explicitly **not** human obviousness).
- Sharpness descriptive distributions; relaxed/strict sharpness variants.
- The C3b flagging-channel feasibility discussion (audited, not modeled).

### Level 4 — Unresolved (must be labeled unresolved)

- **C3c — sharpness × clock next-move-quality moderation: directional train+val signal but
  UNDERPOWERED / NO-CLAIM under the locked criteria; not confirmed, not disproven.** (Pooled
  train+val interaction +0.0102 [+0.0013, +0.0194]; per-month sharp×`60_180` cell 297/282 <
  300; held-out test weak with October sign flip.)

### Level 5 — Abandoned / not recommended (reopen only deliberately)

- **C3a all-outcome sharpness moderation** — confounded by the flagging channel.
- **Board-decided C3a** — likely null-by-construction after 11.2B (the residual it would
  moderate already collapsed).
- **Human-obviousness modeling** — deferred Tier B idea, not implemented.
- **DRAW-specific modeling** — not solved; out of scope.
- **Prior-trajectory control** — deferred; absent from artifacts (stated C4 limitation).

## Candidate public-facing abstract (DRAFT — not final)

> This project studies whether clock information adds predictive value to chess outcome and
> move-quality models beyond objective position evaluation and rating. Across two independent
> Lichess 10+0 monthly samples, adding clock features improves final-outcome prediction, but
> termination decomposition shows that this improvement is primarily a timeout/flagging
> channel rather than direct evidence of degraded board-play quality. At the next-move level,
> evaluation state dominates expected-score loss; after controlling for evaluation, rating,
> checkpoint, month, and termination, clock retains a small, replicated association with
> next-move loss. MultiPV-derived sharpness features are feasible and stable, but the
> pre-registered sharpness × clock moderation test is underpowered/no-claim. The results
> support a cautious interpretation: clock matters predictively, but mostly through flagging
> at the outcome level and only weakly at the move-quality level. All results are
> predictive/descriptive, not causal.

## Forbidden public claims

- "Time pressure causes worse reasoning."
- "Clock pressure degrades chess skill."
- "Low clock causes blunders."
- "The original E3/E4 result measures move quality."
- "The project proves sharpness moderation."
- "Sharpness explains the clock effect."
- "Human obviousness has been modeled."
- "Stockfish is ground truth."
- "DRAW is solved."
- "This is the best human chess predictor."
- "The sharpness result is null." / "The sharpness result is confirmed." (it is
  underpowered/no-claim.)

## Final report outline (draft)

1. Abstract — 2. Research question & contribution — 3. Data & checkpoints — 4. Evaluation &
outcome targets — 5. Baseline outcome models: E3 vs E4 — 6. Termination decomposition:
flagging vs board-decided — 7. Next-move loss extraction & expected-score transform —
8. Constraint atlas: descriptive move-quality patterns — 9. Controlled move-quality models —
10. Robustness & clustered uncertainty — 11. MultiPV sharpness features — 12. Sharpness
interaction: directional but underpowered/no-claim — 13. Limitations — 14. Future work —
15. Conclusion.

## Required tables (inventory; source report)

1. Dataset summary by month — `scale_up_*`, `cross_month_replication_*`, dataset cards.
2. E3/E4 outcome log-loss comparison — `eval_conditioned_modeling_*`, `cross_month_*`.
3. Termination decomposition (all / board-decided / time-forfeit) — `termination_decomposition_combined`, `player_clustered_termination_decomposition`.
4. Next-move-loss artifact summary — `next_move_loss_combined`.
5. Constraint atlas key descriptive results — `constraint_atlas_combined`, `player_clustered_constraint_atlas`.
6. Controlled move-quality primary results — `controlled_move_quality_combined`.
7. Robustness checks summary — `clock_association_robustness_combined`.
8. Sharpness feature distribution summary — `multipv_sharpness_combined`.
9. C3c sharpness interaction result + classification — `sharpness_interaction_combined`.
10. Claim hierarchy / evidence-status table — this document.

## Required figures (inventory; generate later in 16.0B, not here)

1. E3→E4 outcome log-loss delta by month.
2. Termination decomposition forest plot (all-games vs board-decided vs time-forfeit, both months).
3. Constraint atlas: ES loss by eval band × clock bucket.
4. Controlled move-quality: clock contrast / adjusted means with clustered CIs.
5. Sharpness feature distribution: sharp vs non-sharp base rate by checkpoint/month.
6. C3c forest plot: per-month + pooled train+val + test confirmation, labeled underpowered/no-claim.
7. (Optional) pipeline/schema diagram.

`reports/figures/` exists (empty) for these; figure generation is a 16.0B task.
