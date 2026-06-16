# Phase 15.3B — Dense Move-by-Move Loss Extraction Pilot

**Labels:** IMPLEMENTATION (pilot) | move-quality / Constraint Atlas (Phase 15.3)
**Date:** 2026-06-16
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION (capped pilot only)

## 1. Executive summary

Implemented and ran a **capped pilot** for dense move-by-move next-move loss
extraction — the dense generalization of the four White-only numbered checkpoints
(`next_move_loss.py`, 15.0C) to **every ply, both colors**. The pilot processed the
first **1,500 accepted 600+0 games** of 2024-09 → **86,977 per-ply rows** across
**1,486 games** (14 games were too short for any `move_number >= 5` row), with
**88,012 Stockfish evals**, **0 replay failures, 0 eval errors, 0 duplicate keys,
0 missing clocks**, and **100% mover/opponent player-hash join**. Runtime ~40 min
at depth 12 (41.7 evals/s over the full position distribution).

The pipeline is **validated and correct**: mover-perspective sign conversion holds
for both colors (ES mean 0.0345 White / 0.0348 Black), expected-score loss is
bounded `[0, 0.79]`, clipped cp loss is never negative, and the **eval-band pattern
reproduces the checkpoint finding** (`slight` highest median ES 0.0175 → `decided`
lowest 0.0042). The dense extraction is methodologically ready.

**This is a pilot only. No full dense extraction has been run. No dense atlas and no
dense controlled model have been produced.** The full both-months dense pass is a
real compute decision: extrapolated **~22 h at depth 12** (machine-kept-awake or
chunked), with depth-10 / stratified options available. Recommendation: **15.3C-A —
Dense Extraction Strategy Decision Audit** (decide depth / chunking / sampling
before committing the full run), NOT an automatic full depth-12 run.

Predictive/descriptive only — not causal, not a degradation curve, no
"low clock causes blunders" / "time pressure causes worse reasoning"; Stockfish
depth-12 eval is objective position context, not absolute ground truth.

## 2. Files inspected

`ROADMAP.md`, `EXPERIMENT_LOG.md`, `PREREGISTRATION.md`,
`reports/phase_reports/phase_15_3a_dense_move_by_move_loss_feasibility_audit.md`,
`reports/phase_reports/phase_15_2b_roadmap_recovery_patch.md`,
`reports/next_move_loss_combined.md`, `reports/constraint_atlas_combined.md`,
`reports/controlled_move_quality_combined.md`; source modules
`src/chess_mhsuc/next_move_loss.py`, `stockfish_eval.py`, `parse_pgn.py`,
`player_metadata.py`, `constraint_atlas.py`; artifacts
`data/interim/game_records_2024_09_250k_v1.parquet`,
`data/processed/splits_2024_09_250k_v1.json`,
`data/processed/player_metadata_2024_09_250k_v1.parquet`,
`data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json`.

## 3. Files created

- `src/chess_mhsuc/dense_move_loss.py` — dense per-ply extraction module (pilot-only;
  no full-run path).
- `tests/test_dense_move_loss.py` — 30 tests (pure logic + synthetic games; no engine).
- `reports/dense_move_loss_pilot_2024_09_v1.md` — committed aggregate pilot report.
- `reports/phase_reports/phase_15_3b_dense_move_loss_pilot.md` — this report.
- `data/processed/dense_move_loss_pilot_2024_09_v1.parquet` — pilot artifact
  (**gitignored under `data/`; not staged**).

## 4. Files modified

- `ROADMAP.md` — 15.3A/15.3B marked complete; next pointer set to 15.3C-A.
- `EXPERIMENT_LOG.md` — added EXP-040.
- `PREREGISTRATION.md` — unchanged (no metric-policy or design change; the 15.3A
  policy stands).

## 5. Tests run

- `pytest tests/test_dense_move_loss.py` → **30 passed**.
- Full suite `pytest` → **1,774 passed** (1,744 prior + 30 new), 3 pre-existing
  sklearn warnings only.

Tests cover: clock-before reconstruction (White & Black), first-move default 600,
think-time, negative/over-600/missing clock anomaly flags, mover-perspective sign
conversion (both colors), cp-loss raw vs clipped (incl. negative raw and value
clipping), ES-loss nonnegative/bounded, mate-band flagging, phase/clock/think/rating
bucketing, move-tag extraction (capture/check/castle/promotion), row-key uniqueness,
no-username schema guard, pilot-cap constants, refusal of an over-cap run, large-run
override gating, report renderer validation sections, terminal checkmate eval,
mover-result label, and the `min_move_number` opening filter.

## 6. Pilot command

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn \
  --month 2024_09 \
  --max-accepted-games 1500 \
  --min-move-number 5 \
  --depth 12 \
  --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --out data/processed/dense_move_loss_pilot_2024_09_v1.parquet \
  --report reports/dense_move_loss_pilot_2024_09_v1.md \
  --timing-subtest-depth 10 --timing-subtest-games 25 --overwrite
```

A 50-game depth-12 smoke run preceded the pilot (validated end-to-end, then its
outputs were removed).

## 7. Pilot artifact

`data/processed/dense_move_loss_pilot_2024_09_v1.parquet` — 86,977 rows × 53 columns
(51 typed schema columns + `mover_player_hash`/`opponent_player_hash`). Gitignored
(`/.gitignore:8 data/`); not staged. No raw usernames; player IDs are one-way
blake2b hashes (11.3B convention).

Schema highlights: keys `game_id`/`ply`; both-side and mover-centric clocks +
`think_time_s`; Elos + `elo_diff_mover`; `termination`/`is_time_forfeit`/
`result_class`/`mover_result`; `pre_fen`/`fen_hash`/`post_fen_hash`; White-POV
`eval_before_cp`/`eval_after_actual_cp` (+ mate); `cp_loss_raw`/`cp_loss_clipped`;
`expected_score_before`/`_after_actual`/`_loss`; `is_mate_band`; `phase`/`eval_band`/
`clock_bucket`/`think_time_bucket`/`rating_bucket`; move tags; `split_set`; `status`/
`failure_reason`.

## 8. Validation results

| Check | Result |
|---|---|
| Rows written | 86,977 |
| Unique games | 1,486 (14 of 1,500 too short for move≥5) |
| Duplicate (game_id, ply) keys | 0 |
| Replay failures | 0 |
| Eval errors | 0 |
| Engine evals / cache-reuse hits / terminal positions | 88,012 / 85,491 / 451 |
| Missing-clock rows | 0 |
| Clock-anomaly rows (no coarse bucket) | 0 |
| Think-time-anomaly rows | 7 (flagged, not dropped) |
| Mate-band rows (flagged, excluded from headline) | 4,874 |
| Mover colors | White 43,856 / Black 43,121 (balanced) |
| No raw-username columns | True |
| Player-hash join | 1.0 (86,977/86,977) |
| ES loss range | [0.0, 0.788] |
| clipped cp loss < 0 | 0 |
| raw cp loss < 0 (move beat prior static eval) | 18,301 (expected; depth-parity/quiet) |
| clock_before_s > 600 | 1 (flagged) |
| ply range / min move_number | 9–233 / 5 |
| split coverage | train 60,430 / val 13,176 / test 12,894 / unknown 477 |

**Sign correctness:** ES loss mean 0.0345 (White) vs 0.0348 (Black), medians 0.0116
vs 0.0113 — both colors balanced, confirming the mover-perspective conversion is
correct for Black moves (the dense extension's main new capability).

**Eval-band cross-check (descriptive):** median ES loss by band —
`slight` 0.0175 (peak) > `clear` 0.0108 ≈ `near_equal` 0.0108 > `decided` 0.0042.
Consistent with the checkpoint 15.1B/15.1D finding that move-quality loss is
dominated by eval state; reproduced here on dense, both-color data. **Descriptive
only — no claim.**

## 9. Runtime and extrapolation

- Wall-clock 2,422.5 s (~40 min); engine seconds 2,108.5; **41.7 evals/s** over the
  full pilot position distribution at depth 12.
- 15.3A both-months dense universe estimate ~3,340,000 positions →
  **~22.2 h both months (~11.1 h/month) at depth 12** at the measured rate. This sits
  in the upper half of the 15.3A 17–24 h band.
- **Depth-10 timing subtest: 202.8 evals/s** on a 1,000-position sample. **CAVEAT:**
  that sample is the first ~17 games' positions, NOT distribution-matched to the full
  pilot, so the implied ~4.6 h is an optimistic lower bound. A realistic depth-10
  full run is closer to the 15.3A ~8–12 h estimate (≈2–3× the depth-12 node count
  reduction, not ~5×). The reliable figure is the depth-12 full-pilot rate.

A ~22 h depth-12 run exceeds a comfortable single session and would need the machine
kept awake/plugged or chunked (cf. the 14.1C overnight-sleep suspension). Depth-10,
stratified sampling, or chunking are all viable reductions.

## 10. Recommendation for 15.3C

**Recommended next ticket: 15.3C-A — Dense Extraction Strategy Decision Audit**
(not an automatic full depth-12 run).

Rationale: the pilot proves the pipeline is correct and complete (validation clean,
both colors, metrics sane, player clustering joinable) and measures real throughput.
But the full both-months run is a genuine compute/quality trade-off — ~22 h at
depth 12 (kept-awake/chunked) vs ~half at depth 10 vs a stratified subset — and the
depth-parity sensitivity should be confirmed at scale. Per the ticket's guard
("do not automatically recommend full depth-12 if the extrapolated runtime is not
acceptable"), the decision (depth, chunking, sampling, awake-run plan) should be
made explicitly in a short audit before 15.3C executes the full extraction.

Validation did NOT fail, so 15.3B2 (pilot fixes) is not required.

## 11. Known risks

- **Compute:** ~22 h depth-12 full run; mitigations = depth-10 (~half), stratified
  sampling, chunked + machine-kept-awake. To be decided in 15.3C-A.
- **Depth parity:** pre-move (mover-to-move) and post-move (opponent-to-move) both at
  the same fixed depth; half-ply asymmetry acknowledged (15.0C found it benign);
  re-check at scale / depth-13 spot-check.
- **Short games:** 14/1,500 produced no move≥5 row; expected, counted, not an error.
- **Clock artifacts:** 7 think-time anomalies + 1 clock>600; flagged, retained, never
  silently dropped.
- **Trajectory control absent:** no pre-move prior-quality feature in the artifact;
  stated limitation for any later controlled model (mandatory only before a causal
  claim, per 15.1G).
- **Mover-orientation scope removed at dense level:** unlike checkpoints (White only),
  dense rows cover both colors — a capability gain, validated above.

## 12. Non-claims

- This is a **pilot only**. No full dense extraction has been run.
- No dense atlas has been produced. No dense controlled model has been run.
- No causal claim. No "low clock causes blunders." No "time pressure causes worse
  reasoning." No "Stockfish is ground truth." No "human obviousness modeled." No
  "DRAW solved." No "best predictor."
- This does **not** change C4. This does **not** change C3c.
- The eval-band reproduction is descriptive corroboration, not a new result.
- No thresholds or classifications were changed.
