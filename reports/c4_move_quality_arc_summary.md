# C4 Move-Quality Arc Summary

*Reader-facing summary of the move-quality arc (tickets 11.2B → 15.1F). Full procedure
and ticket-by-ticket detail are in
`reports/phase_reports/phase_15_1g_c4_claim_consolidation.md`.*

## Summary

In Lichess 10+0 games (two months, 2024-09 and 2024-10), we asked whether having less time
on the clock is associated with worse *moves*, separately from the well-known fact that
players lose games by flagging. The answer, in one line: **eval state dominates move
quality; clock matters too, but only a little, and the original "clock predicts outcomes"
signal is mostly about flagging.** All statements below are **predictive/descriptive
associations, not causal**.

## What changed from the original clock-outcome claim

Earlier work found that adding clock features improved game-outcome prediction (the E3→E4
comparison). On closer inspection (11.2B), that improvement is **substantially a flagging /
time-forfeit channel**: once games decided on time are removed, the board-decided outcome
residual collapses or reverses, while the time-forfeit-only signal is large
(≈ −0.12 to −0.13 log-loss). So "clock helps predict who wins" is mostly "clock predicts
who runs out of time," not "low clock means worse board play." This survives
player-clustered uncertainty (11.3B).

## What the move-quality analyses show

Measuring the actual next move at fixed checkpoints (expected-score loss vs the engine
best line):

- **Eval state is the dominant structure.** Loss is highest in near-equal / slight
  positions and lowest in decided positions — replicated across both months, and ~5–8×
  larger than any clock effect.
- **Clock has a small, real, residual association.** After adjusting for checkpoint, eval
  band, rating, month, and termination, having 60–180 s (vs >180 s) is associated with a
  small increase in next-move loss (pooled ≈ +0.0034 expected-score points), replicated in
  both months and on a held-out test split.
- **Descriptive vs controlled are consistent.** The raw marginal clock curves looked flat
  (15.1B) because clock buckets differ in eval composition; once eval state is held fixed,
  the small clock residual appears.

## What is robust

The small clock association **survives every mandatory robustness check** (15.1F): a
continuous within-band evaluation control, a late-game-only model, a **board-decided-only**
model (so it is not just a time-forfeit artifact), rating-shape variations, alternative
loss metrics, and game / White-player / Black-player clustering. It stays small and
secondary to eval state throughout.

## What remains limited

- **Prior trajectory is not controlled.** The data do not record how much the player
  struggled or burned time *before* each checkpoint, so the small clock effect could partly
  reflect earlier difficulty rather than time pressure itself. This is the main open
  caveat and a recommended future extraction.
- Mover is always White at these checkpoints (scope limitation).
- Two months of 10+0 only; the engine evaluation is objective context, not ground truth;
  draws remain hard; sharpness has not been analyzed.

## Safe claim wording

> "In 10+0 Lichess games, the clock's value for predicting *game outcomes* is largely a
> flagging-risk signal. For *move quality*, the position's evaluation is the dominant
> factor; lower clock is associated with a small, replicated, robustness-checked increase
> in next-move expected-score loss after controls. These are predictive associations, not
> evidence that time pressure causes worse reasoning, and the clock effect is much smaller
> than the evaluation-state effect. Prior in-game trajectory is not yet controlled."
