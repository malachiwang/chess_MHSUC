# Phase 15.0A — Move-Quality / Constraint Atlas Feasibility Audit

**Labels:** AUDIT/DESIGN | doc-only, read-only inspection
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Executive summary

**Next-move quality analysis is feasible.** No processed artifact stores the FEN or the
played move (only an irreversible `fen_hash`), but the raw PGN caches for both months are
present locally (`data/raw/lichess/lichess_2024_{09,10}_first250k.pgn`, 583 MB each,
gitignored) and the existing `stockfish_eval.reconstruct_fen_at_ply` already replays
mainline moves to a target ply. Getting the next move and the post-move FEN is **one
additional `board.push()`** in that same loop. 98.5% of primary checkpoints (64,371 /
65,368 in 2024-09) have a next move. A decisive simplification: the checkpoint
`sf_eval_cp` already stored by Phase 8.1 **is the engine best-line (analyse) value at
that position**, so engine-best loss needs only a *post-move* evaluation pass — best-move
search/MultiPV is not required for the first move-quality metric. **Recommended primary
metric: expected-score loss, mover's perspective**, `max(0, ES_best_before −
ES_after_actual)`, where `ES_best_before` is the existing checkpoint eval converted to
expected score and `ES_after_actual` is a new post-move eval. Feasibility is **Level 1–2**
(reconstruct post-move FEN from the raw cache; one new Stockfish post-move pass ≈ the
size and cost of the original 8.1 pass, ~30 min/month). 15.0B extraction may proceed
before 11.3A/B (it produces per-position targets, not predictive models); 15.1A/B
controlled modeling must wait for player-clustered/disjoint design. All of this is
predictive/descriptive — not causal, no "degradation curve" language, Stockfish eval is
objective context, not absolute ground truth.

## 2. Scientific motivation after 11.2B/11.2C

11.2B showed the all-games E3→E4 outcome residual is substantially the time-forfeit /
flagging channel; among board-decided games it collapsed/sign-reversed. 11.2C reframed
the central claim and elevated Contrast C4 (next-move quality) as the central board-play
test, because it **measures board-play quality directly rather than inferring it from
final outcomes** and is structurally immune to the C2 collapse. The Constraint Atlas
(Phase 15) is the descriptive + controlled layer that answers: does constraint state
(clock, rating, eval band, phase, time control, eventually sharpness) correspond to
measurable changes in next-move expected-score loss? This audit scopes feasibility only.

## 3. Current artifact and code inspection (read-only)

Inspected schemas (2024-09 250k; 2024-10 mirrors it):

- `ten_zero_positions_broad` (89,888 × 19): `game_id, ply, move_number,
  side_to_move_next, selected_position_type, white_clock_s, black_clock_s, clock_diff_s,
  eval_cp, eval_mate, has_eval, phase, result_class, white_result_numeric, white_elo,
  black_elo, elo_diff, termination, n_plies_total`.
- `feature_positions_broad` (89,888 × 40): adds capped clocks, fracs, low-clock flags,
  `eval_cp_clipped, is_mate_eval, eval_white_winning, is_last_checkpoint,
  white_to_move_next, checkpoint_index, phase_index, is_time_forfeit,
  duplicate_ply_checkpoint, avg_elo`.
- `sf_eval_broad` (65,368 × 27): `game_id, ply, selected_position_type, split_set,
  move_number, result_class, fen_hash, sf_eval_available, sf_eval_status, sf_eval_cp,
  sf_eval_mate, sf_eval_mate_abs, sf_eval_abs, sf_eval_sign, sf_eval_bucket, sf_depth,
  sf_nodes, sf_time_ms, sf_engine_name, sf_engine_version, ...`. **No best move, no WDL,
  no MultiPV, no FEN** — only cp/mate score + `fen_hash` (sha256 prefix, irreversible).
- `ten_zero_game_records` (25,887 × 22): per-game metadata; **no move list**.
- `sf_eval_metadata`: depth=12, Stockfish 18, 65,368 evals in 1,838 s (≈28 ms/position),
  288 terminal depth-0 rows. No WDL/best-move fields.

Code: `stockfish_eval.reconstruct_fen_at_ply(game, target_ply)` replays
`game.mainline_moves()` and returns `board.fen()` after `target_ply` half-moves — i.e.
the checkpoint (pre-move) position. `analyse_fen` calls
`engine.analyse(board, Limit(depth=depth))` with default `multipv=1`, no WDL request, and
persists only the score (cp/mate) + depth + nodes. The PV/best move is *available* in the
returned `info` but was never stored; WDL would require `UCI_ShowWDL` + `PovScore.wdl()`.

**`eval_cp`/`eval_mate`/`has_eval` in the position/feature tables are the sparse
Lichess-embedded evals (~15% coverage)** and must not be used as the objective
move-quality anchor; the full-coverage depth-12 `sf_eval_cp` is the correct anchor.

## 4. Data availability for next-move quality

| Needed input | Available? | Where |
|---|---|---|
| `game_id`, `selected_position_type`, `ply`, `move_number` | Yes | position/sf tables |
| `side_to_move_next` | Yes | position/feature tables |
| clocks before move | Yes | `white_clock_s`/`black_clock_s` (+capped) |
| clocks after move | No (only pre-checkpoint clocks stored) | — (reconstructable from PGN clock comments if ever needed) |
| rating / result / termination / split | Yes | feature + sf tables |
| current (pre-move) Stockfish eval | Yes | `sf_eval_cp` (= best-line value at depth 12) |
| **pre-move FEN** | No (only `fen_hash`) | reconstructable from raw PGN cache |
| **actual next move (SAN/UCI)** | No | reconstructable from raw PGN cache (one more move in the replay loop) |
| **post-move FEN** | No | generated by pushing the next move during replay |
| best-move identity / MultiPV | No | would need a new search (deferred) |
| WDL | No | needs `UCI_ShowWDL` in a new pass, or a cp→ES transform |

Next-move availability (2024-09 primary view): **64,371 / 65,368 (98.5%) have a next
move** (`n_plies_total > ply`); 997 games ended exactly at the checkpoint (no next move —
mostly checkmate/resignation/flag on the checkpoint ply). By checkpoint: move_10 24,384;
move_20 19,639; move_30 12,950; move_40 7,398. The 997 no-next-move rows are excluded
from move-quality analysis by definition and that exclusion is itself reportable
(games decided *at* the checkpoint). Resignations/timeouts immediately *after* the
checkpoint still have a next move (the played move before the game ended) and are kept,
with termination labeled.

## 5. Feasibility level by metric

Reconstruction of pre-move FEN + next move + post-move FEN is **Level 2** (not stored;
generated by replaying the raw PGN cache with the existing replay code) and requires no
parser change (Level 3 avoided). New engine evaluation of post-move positions adds a
**Level 1** requirement. Combined per metric:

| Metric | Level | Notes |
|---|---|---|
| Actual eval swing (Option 1) | **1–2** | post-move FEN from cache + 1 new eval/position |
| Engine-best cp loss (Option 2) | **1–2** | checkpoint best-line value already in `sf_eval_cp`; only post-move eval needed (true best-*move* identification/MultiPV would be heavier — deferred) |
| Expected-score loss (Option 3) | **1–2** | same reconstruction + cp→ES transform or WDL pass |
| Blunder probability (Option 4) | **0** once loss exists | threshold on the above; pre-register threshold |
| Percent swing (Option 5) | n/a | exploratory/avoid (denominator explodes near zero) |

**Key insight collapsing Options 1 and 2:** at fixed depth, `engine.analyse` returns the
position's value *under best play* — so the stored checkpoint `sf_eval_cp` already equals
the engine-best value (`ES_best_before`). There is no separate "current value ignoring
the best move" in a search engine. Thus the cheap post-move-only pass already yields
engine-best-relative loss, up to the depth-parity artifact (§7). True best-*move*
enumeration / MultiPV (to identify *which* move is best, or count near-best moves for
sharpness) is a separate, heavier pass and is correctly deferred to Phase 14.

## 6. Recommended move-quality target

**Primary: expected-score loss, mover's perspective**

```
ES_best_before  = expected_score( sf_eval at checkpoint, oriented to the mover )
ES_after_actual = expected_score( new eval of post-move position, oriented to the same mover )
expected_score_loss = max(0, ES_best_before − ES_after_actual)
```

- Use `ES_best_before` (the checkpoint analyse value = best-line value), not a distinct
  `ES_before_position` — in this pipeline they coincide, but the report must name the
  metric as best-line-relative and not silently call it "swing from a non-best baseline."
- **First-pass pragmatics:** if WDL/ES conversion is deferred, the identical structure on
  the cp scale (`clipped_cp_loss = max(0, cp_best_before − cp_after_actual)`, clipped at
  ±1000, mover-oriented) is the cheap first metric; expected-score loss is the headline
  once the conversion (§8) is fixed. Report both once both exist; preserve the cp-based
  E3/E4 historical lineage separately and never silently replace it.

**Secondary:** clipped centipawn loss (literature comparability); large-loss probability
(blunder indicator) at a pre-registered threshold. **Raw cp** only inside eval-band
panels. **Percent swing** exploratory or avoided.

## 7. Orientation convention

- **Mover's perspective is primary.** `ES_best_before` = expected score for the player
  about to move at the checkpoint; `ES_after_actual` = expected score for *that same
  player* after their actual move (the post-move eval is from the opponent's
  side-to-move, so negate/orient to the mover). Loss = `max(0, before − after)`.
- Draws scored 0.5 in expected-score space. White-perspective storage is fine internally
  but all loss computations orient to the mover.
- **Advantaged-player conversion orientation stays for sharpness/conversion analyses
  (Phase 14 / C3c), not for the primary next-move-quality metric** — next-move loss is
  inherently a mover-perspective quantity.
- **Depth-parity caveat (must handle in 15.0B):** evaluating the pre-move position
  (mover to move, depth 12) vs the post-move position (opponent to move, depth 12)
  introduces an odd/even search-parity asymmetry. Pick one convention — evaluate both at
  depth 12 and acknowledge the parity asymmetry, or evaluate post-move at depth 11/13 —
  document it, and sensitivity-check on a subsample. Recommend: both at depth 12 for
  consistency with the existing `sf_eval` pass, with a documented parity caveat and a
  small depth-13 post-move sensitivity check.

## 8. Expected-score / WDL conversion recommendation

- Stockfish 18 supports `UCI_ShowWDL`; python-chess exposes `PovScore.wdl()` when the
  engine reports it. The existing `sf_eval` pass did **not** enable it, so checkpoint
  WDL is not stored. Two feasible routes, decided in 15.0B:
  - **(a) Enable WDL in the new post-move pass** and re-derive checkpoint ES the same
    way (cheap; requires re-evaluating checkpoints with WDL on, or accepting a cp→ES
    transform for the already-stored checkpoint cp).
  - **(b) Fit a cp→expected-score transform on the TRAIN split only** (logistic of
    actual game result on checkpoint cp, or a standard Lichess-style win% sigmoid),
    applied to both `cp_best_before` and `cp_after_actual`. This needs no new WDL and
    reuses stored cp.
- **Recommendation:** route (b) as the portable default (train-fit cp→ES, no dependency
  on engine WDL availability), with route (a) WDL as a robustness cross-check. Either
  way: **draws = 0.5; mate-band handled separately or excluded in the first pass; the
  cp-based E3/E4 lineage is preserved as a parallel layer, never silently replaced.**
- The transform is a learned mapping → **fit on train only** (split discipline), applied
  unchanged to validation.

## 9. Binning and stratification design

- **Time remaining (mover's clock at checkpoint):** the 9.2B late-clock buckets are the
  proven, CI-bearing choice — `under_60s / 60_180s / over_180s`. The finer
  `under_10 / 10_30 / 30_60 / 60_180 / over_180` scheme is feasible for *pooled
  descriptive* curves but `under_10`/`10_30` will be sparse at early checkpoints
  (almost all move_10 clocks are >180s — the clock×checkpoint confound from 9.2B);
  15.0B's cell-count audit decides per-checkpoint. **Do not run marginal clock buckets
  that conflate time remaining with phase** — bucket *within* checkpoint.
- **Rating (avg_elo):** 200-Elo bins or the existing four buckets for CI-bearing curves
  (100-Elo bins were sparse for CIs at this scale, per 11.0A/15.0A precedent — the 2000+
  cell is already ~300 games per month); 100-Elo only for smoothed pooled visuals;
  within-time-control quantiles reserved for Phase 16.
- **Eval bands (from `sf_eval_cp`):** `equal (|cp|<100) / slight (100–300) / decided
  (300–10000) / mate-band (|cp|≥10000 or ok_mate)` — mate-band separate or excluded in
  the first pass. This prevents the "100cp at +1000 ≠ 100cp at equal" distortion.
- **Phase / checkpoint:** move_10/20/30/40; late group move_30+move_40.
- **Termination:** report all-games, board-decided-only, and time-forfeit-labeled
  separately; never mix channels silently (11.2B lesson).
- **Sharpness:** deferred to after Phase 14's MultiPV pass; conditioning slot reserved.

## 10. Sample-size implications

Per month, primary checkpoints with a next move ≈ 64k (move_10 24.4k → move_40 7.4k);
board-decided primary rows ≈ 56.8k (2024-09). Late-group (move_30+40) board-decided with
next move ≈ 19k–20k rows. The late-clock board-decided cells inherit 11.2B's numbers:
`60_180s` stays CI-bearing (~400–500 games/month), `under_60s` is descriptive-only
(~100 games/month, below the 300-game threshold). Eval-band × time × rating cells will be
thin at the tails (mate-band, 2000+, under_60s) — descriptive-only there, CI-bearing in
the dense interior. Loss distributions are heavily right-skewed → report **median + 75th/
90th percentiles** alongside means, with game-clustered bootstrap CIs where cells permit.

## 11. Compute-cost estimate

- Existing `sf_eval`: 65,368 positions in 1,838 s ≈ **28 ms/position** (depth 12, SF18).
- **Post-move pass (primary metric):** ~64,371 post-move positions/month ≈ **~30 min/
  month**, **~1 h both months** — same order as the original 8.1 pass. Plus one raw-PGN
  streaming pass/month to reconstruct positions (the 8.1 pass took ~the same; the cache
  is local so no re-download).
- **Storage:** a move-quality artifact of ~64k rows/month with a dozen columns ≈ <5 MB/
  month Parquet (gitignored). Negligible.
- **Best-move/MultiPV pass:** NOT needed for the first metric (checkpoint value already
  stored); defer to Phase 14 where MultiPV is its own ~65k×5 cost.
- **Recommendation:** evaluate **checkpoint rows only** first (not every ply). Run a
  **pilot of one month** (or a capped subset, e.g. `--limit`) to validate the post-move
  reconstruction + parity convention, then the full both-months pass **only after
  explicit approval** (same gate as the 8.1B/9.x full Stockfish runs). Avoid MultiPV
  until the basic move-quality pipeline works.

## 12. Proposed descriptive outputs (the Atlas)

All with game-clustered bootstrap CI ribbons where cells permit; medians + 75th/90th
percentiles for skew; sub-threshold cells descriptive-only; no causal wording:

1. Time remaining (within checkpoint) vs mean/median expected-score loss; lines = rating.
2. Same vs clipped cp loss (secondary, familiar).
3. Rating × time heatmap (color = expected-score loss; variant: P(large loss)).
4. Eval-band-conditioned panels (equal/slight/decided/mate-band).
5. Phase-conditioned panels (move_10/20/30/40; late group).
6. Board-decided-only curves (the post-11.2B headline population).
7. Time-forfeit-labeled descriptive comparison (never silently merged).
8. Sharpness-conditioned curves — reserved for after Phase 14.

## 13. Proposed controlled-modeling layer (later; not this ticket)

1. Descriptive curves (15.0C).
2. Controlled regression: `next_move_loss ~ time_bucket + rating_bucket + eval_band +
   phase + prior_trajectory` (prior-trajectory / cumulative-loss control mandatory — the
   "clock as symptom of past struggle" confound).
3. Interactions: time × rating, time × eval band, time × termination, time × sharpness
   (later).
4. Robustness: board-decided-only; mate-band excluded/separate; **player-clustered
   uncertainty (and disjoint splits if 11.3 permits)**; cross-month replication.

15.0A is the audit only; modeling comes later.

## 14. Relationship to player-leakage audits (11.3A/B)

- **15.0A (this audit): safe before 11.3A/B** — pure documentation/inspection.
- **15.0B (extraction): safe before 11.3A/B.** It produces *per-position move-quality
  targets* (a measurement of each played move's loss) — no model is trained or evaluated,
  so train/val/test leakage is irrelevant to the artifact itself. Gating it on player
  leakage would be unnecessary.
- **15.0C (descriptive curves): mostly safe**, but uncertainty must be at least
  game-clustered; player-clustered is preferable and can be a labeled robustness add-on
  once 11.3 lands.
- **15.1A/B (controlled modeling): must wait for 11.3A/B** or be built with
  player-clustered uncertainty / player-disjoint splits from the start. Inference about
  constraint→loss associations is where player leakage would inflate confidence.
- This ordering matches the 11.2C recommendation: 15.0A → 15.0B (extraction) can proceed;
  11.3A/B run before 15.1B locks any primary C4 modeling result, and additionally check
  whether player leakage inflates the flagging-channel estimate.

## 15. Risks and caveats

- **Not causal**; no "degradation curve" language; constraint→loss is association, framed
  as "association between constraint state and next-move loss." No claim that low clock
  causes worse reasoning.
- Stockfish depth-12 eval is objective position context, **not absolute ground truth**;
  loss is relative to a fixed-depth engine and inherits its blind spots.
- **Depth-parity artifact** (§7) must be handled and sensitivity-checked.
- **Selection / survivorship:** board-decided low-clock positions are a survivor
  population (players who navigated time pressure without flagging) — the same 11.2B
  caveat; reported, not papered over.
- Loss distributions are skewed → means alone mislead; report medians/percentiles.
- The 997 no-next-move rows (games decided at the checkpoint) are excluded by definition;
  the exclusion is reported, not silent.
- Sharpness itself being difficult is **not** claimed as novel (Anderson et al.;
  Barthelemy — move-level prior work). DRAW remains sparse and not solved.
- A train-fit cp→ES transform is a learned mapping → train-only, applied unchanged to val.

## 16. Roadmap / preregistration implications

- No PREREGISTRATION.md change is required: Contrast C4 already names expected-score loss
  (mover's perspective), the prior-trajectory control, and the loss-definition lock-in at
  15.0A; this audit confirms expected-score loss as primary and clipped-cp as the cheap
  first pass — consistent with C4 as written. The one parameter C4 defers to 15.0A — the
  exact loss definition — is resolved here: **best-line-relative expected-score loss,
  mover's perspective, `max(0, ES_best_before − ES_after_actual)`**, with the cp-scale
  variant as the cheap first metric and the blunder threshold still to be pre-registered
  in 15.0B/15.1A.
- ROADMAP next-ticket pointer updated to 15.0B.

## 17. Recommended next ticket

**15.0B — Checkpoint-Level Next-Move Loss Extraction.** It is the natural next step,
feasible at Level 1–2, may proceed before 11.3A/B (it builds per-position targets, not
models), and reuses the existing `stockfish_eval` replay + engine infrastructure (one
extra `board.push()` for the post-move FEN, one post-move eval pass, a train-fit cp→ES
transform). Scope notes for 15.0B: (1) reconstruct post-move FEN from the local raw
cache; (2) handle the depth-parity convention + sensitivity check; (3) exclude the 997
no-next-move rows with a reported count; (4) compute clipped-cp loss first, then
expected-score loss; (5) write a gitignored move-quality artifact; (6) **the full
both-months Stockfish post-move pass runs only after explicit approval** (8.1B/9.x gate),
with a one-month or `--limit` pilot first. 11.3A/B remain queued before 15.1B controlled
modeling.
