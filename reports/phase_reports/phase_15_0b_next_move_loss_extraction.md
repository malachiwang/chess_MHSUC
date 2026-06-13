# Phase 15.0B — Checkpoint-Level Next-Move Loss Extraction

**Labels:** ANALYSIS/ML | IMPLEMENTATION (pilot only)
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Executive summary

Implemented the measurement layer for Contrast C4: per-checkpoint next-move quality
loss from the mover's perspective. The module reconstructs the post-move position from
the local raw PGN cache (one `board.push()` past the checkpoint, reusing
`stockfish_eval`'s replay/indexing/engine helpers — that module is unmodified) and
evaluates only the post-move position; the stored checkpoint `sf_eval_cp` is already the
engine best-line value, so no best-move search and no MultiPV are run. A **1000-row
pilot on 2024-09 succeeded**: 982 OK, 18 no-next-move, **0 reconstruction failures, 0
engine failures, 0 FEN-hash mismatches** (reconstructed checkpoint FENs match the stored
hashes exactly), 19.6 s → **~21 min/month** full-pass estimate. Pilot metric is clipped
centipawn loss; **expected-score loss is deferred to 15.0C/15.1A** with a train-fit
transform (no placeholder presented as final). The full ~64k/month pass is gated
(`--limit` / `--allow-full-run`) and was **not** run.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/next_move_loss.py` | Extraction module: pure helpers (orientation, cp loss, mate-band, time bucket), checkpoint+next-move reconstruction, join loader, pilot loop, summary, report, CLI |
| `tests/test_next_move_loss.py` | 41 tests (pure logic + synthetic games; no Stockfish, no large data) |
| `reports/next_move_loss_pilot_2024_09_250k_v1.md` | Pilot report |
| `reports/phase_reports/phase_15_0b_next_move_loss_extraction.md` | This report |

Generated (gitignored, not staged): `data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet`.

## 3. Files modified

| File | Change |
|---|---|
| `ROADMAP.md` | 15.0B marked done; next-ticket pointer → 15.0C |
| `EXPERIMENT_LOG.md` | EXP-018 added |

No source modules other than the new file; `stockfish_eval.py` reused via import,
unmodified. No PREREGISTRATION.md change needed (15.0A already resolved C4's loss
definition; the cp-first / ES-deferred plan matches it).

## 4. Implementation summary

- `reconstruct_checkpoint_and_next_move(game, checkpoint_ply)`: replays the mainline to
  the checkpoint, returns pre-FEN + mover color + the actual next move (UCI) + post-FEN;
  distinguishes `no_next_move` (game ended at checkpoint), `fen_reconstruction_error`
  (checkpoint beyond game), and `illegal_move`.
- Orientation: White-POV stored evals → mover's perspective
  (`mover_cp = white_cp if mover White else −white_cp`); `cp_loss = max(0, mover_pre_cp −
  mover_post_cp)`, clipped at ±1000 (`MOVE_QUALITY_CP_CAP`, matching `eval_cp_clipped`).
- Mate-band rows (pre or post is a mate score or hits ±10000) are flagged
  `is_mate_band` and excluded from cp-loss summaries — never silently mixed.
- Reuses `analyse_fen`, `index_target_games`, `resolve_stockfish_path`,
  `get_stockfish_version` from `stockfish_eval`; explicit output schema avoids
  Null-type inference.
- Integrity checks: required-column validation; key uniqueness on both join sides; 0
  orphans; per-row checkpoint-FEN hash vs stored `fen_hash`; counted/reported
  no-next-move, reconstruction, and engine failures.

**Structural note:** at numbered checkpoints (ply 20/40/60/80 — all even), the side to
move is always White, so `mover_color` is uniformly White in the pilot. This is a
property of the checkpoint convention (positions are sampled after Black's Nth move),
not a bug; the orientation code is nonetheless tested for both colors and is ready for
any future odd-ply or last-position sampling.

## 5. Pilot command and result

```
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.next_move_loss \
  --dataset-id lichess_ten_zero_2024_09_250k_v1 --version-tag 2024_09_250k_v1 \
  --limit 1000 --stockfish-path /opt/homebrew/bin/stockfish \
  --output data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet \
  --report reports/next_move_loss_pilot_2024_09_250k_v1.md --overwrite
```

- Attempted 1000; **OK 982**; no_next_move 18; fen_err 0; game_not_found 0; engine_err 0;
  **fen_hash mismatches 0**. 378 games indexed from the cache.
- Runtime 19.6 s → per-OK ≈ 20 ms → **full month (~64k) ≈ 21 min**, both months ~42 min
  (consistent with the 15.0A ~30 min/month estimate; the original 8.1 pass was 28
  ms/position).
- Clipped cp loss (OK, non-mate-band, n=943): mean 58.1, median 24, p75 ~?, p90 161,
  zero-loss 29.4%, >100cp 19.1%, >200cp lower (in artifact). 39 OK rows mate-band
  (excluded from cp summary). Counts by checkpoint: move_10 377 / move_20 294 /
  move_30 192 / move_40 119.
- A 200-row warm-up pilot ran first (198 OK, identical clean profile); the 1000-row run
  is the reported pilot.

## 6. Tests run

- `tests/test_next_move_loss.py`: **41 passed** (orientation White/Black; cp loss incl.
  no-negative and cap; mate-band detection; time-bucket boundaries; reconstruction on
  synthetic games incl. no-next-move and beyond-game; build_row orientation for both
  colors; join/required-column/orphan/duplicate validation; raw-PGN path derivation;
  summarize mate-band exclusion; **full-run guard** errors without `--limit`/
  `--allow-full-run`; `--schema-only`).
- Full suite: **1,565 passed** (was 1,524; +41), 0 regressions.

## 7. Output artifact status

`data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet` (1000 rows, 30 columns) —
**gitignored** (`git check-ignore` confirms) and not staged. Schema includes
`game_id, selected_position_type, checkpoint_ply, move_number, mover_color,
actual_move_uci, pre_fen, post_fen, pre/post sf evals, mover_pre/post_cp, cp_loss,
clipped_cp_loss, is_mate_band, ratings, mover_clock_s, time_bucket, termination,
is_time_forfeit, split_set, status, fen_hash_matches`. No usernames (none stored
anywhere; DATA_POLICY).

## 8. Metric / orientation decisions

- **Primary pilot metric: clipped cp loss, mover's perspective**, cap ±1000.
- **Expected-score loss DEFERRED** to 15.0C/15.1A (train-fit cp→ES transform, fit on
  train split only). No placeholder ES transform shipped — avoids presenting a
  provisional sigmoid as final (15.0A / Task 2 guidance).
- `mover_pre_cp` uses the stored checkpoint `sf_eval_cp` (= engine best-line value), so
  the loss is best-line-relative without a separate best-move search.
- **Depth-parity:** pre (mover-to-move) and post (opponent-to-move) both at depth 12; the
  odd/even search-parity asymmetry is acknowledged and flagged for a depth-13 post-move
  sensitivity check in 15.0C.

## 9. Limitations and deferred work

- Expected-score loss + cp→ES transform: 15.0C/15.1A.
- Depth-parity sensitivity check: 15.0C.
- Full both-months pass: 15.0C (gated, explicit approval; pilot validated the pipeline).
- Controlled modeling (C4 regression, interactions): 15.1A/B, after player-leakage
  hardening (11.3A/B) or with player-clustered/disjoint design.
- Loss distributions are right-skewed → medians/percentiles reported alongside means.
- Board-decided low-clock positions are a survivor population (11.2B caveat). Not causal;
  no degradation-curve language; Stockfish depth-12 eval is objective context, not
  absolute ground truth.

## 10. Recommended next ticket

**15.0C — Full Next-Move Loss Extraction Run + Expected-Score Transform.** Scope: run the
full both-months post-move pass (gated, explicit approval — pilot confirms ~21 min/month,
clean reconstruction); add the train-fit cp→expected-score transform (the intended C4
headline metric); add the depth-13 post-move parity sensitivity check; then 15.1A
descriptive Constraint Atlas curves. Player-leakage hardening (11.3A/B) remains required
before 15.1B controlled modeling.
