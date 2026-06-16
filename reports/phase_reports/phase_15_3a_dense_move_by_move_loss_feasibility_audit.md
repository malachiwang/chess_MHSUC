# Phase 15.3A — Dense Move-by-Move Loss Feasibility Audit

**Labels:** AUDIT / DESIGN | report-only, no code/model/Stockfish/data changes
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Dense move-by-move loss extraction is **feasible** with the existing pipeline and local raw
caches, but it is a **heavy engine job**: at full coverage it is **≈ 3.34M ply-rows both
months** (2024-09 ≈ 1.70M, 2024-10 ≈ 1.63M; median 60 plies/game, mean ~66, p90 113), requiring
**≈ 3.3–3.4M Stockfish evaluations** via the efficient **one-eval-per-position sequential
strategy (Option A)** — projected **~17–24 h at depth-12** (~25 ms/eval from prior passes),
~8–12 h at depth-10. The raw PGN caches exist for both months
(`data/raw/lichess/lichess_2024_{09,10}_first250k.pgn`), the parser already captures per-ply
`%clk` clocks (0% null at checkpoints), and `result_class`/`termination`/Elos are available in
`game_records`/`position_records`. The current `next_move_loss` and `position_records` artifacts
are **checkpoint-only** (4 plies/game), so dense rows require **new extraction** (full per-ply
replay + a Stockfish eval at every ply). **Recommendation: a 15.3B pilot of ~1,500 full-dense
2024-09 games at depth-12** (~100k evals, ~40 min) to validate replay/clocks/think-time/FEN-hash
and measure real ms/eval + storage, with a depth-10 timing sub-test; full extraction (15.3C)
gated on that pilot + a machine-awake plan (the 14.1C overnight-sleep suspension risk is real for
a multi-hour run). No dense result exists yet; this changes no prior C4/C3c conclusions. All
future results remain predictive/descriptive, not causal.

## 2. Why dense move-quality is needed

The existing pipeline only measures next-move loss at **`move_10`, `move_20`, `move_30`,
`move_40`** — four checkpoints per game. That is insufficient for the project's intended dense
move-quality degradation atlas. Dense (or dense-sampled) move-quality is required for: centipawn-
loss curves over time remaining; expected-score-loss curves over time remaining; rating × time
heatmaps; phase-conditioned curves; eval-band-conditioned curves; large-loss/blunder-probability
curves; think-time analysis (clocks permitting); and later sharpness-conditioned curves and
trajectory controls. The checkpoint layer gives four snapshots; the dense layer gives the curve.

## 3. Files inspected

Governance/recovery: `ROADMAP.md`, `docs/roadmap_rescope_v11_draft.md`, `PREREGISTRATION.md`,
`EXPERIMENT_LOG.md`, `phase_15_2a…`, `phase_15_2b…`. Move-quality reports:
`next_move_loss_combined`, `constraint_atlas_combined`, `controlled_move_quality_combined`,
`clock_association_robustness_combined`, `phase_15_0a–c`, `phase_15_1a/b/c/d/f` (all present).
Source modules (capability inventory, read-only): `parse_pgn.py`, `run_parser.py`,
`stockfish_eval.py`, `next_move_loss.py`, `constraint_atlas.py`, `controlled_move_quality.py`,
`clock_association_robustness.py`, `player_metadata.py`, `clustered_uncertainty.py`. Artifacts:
the `data/` inventory + read-only schema/count checks on `next_move_loss_*`,
`position_records_*` (interim), `game_records_*` (interim), `multipv_sharpness_*`,
`player_metadata_*`.

## 4. Existing checkpoint-level capability

```
Checkpoint-level analysis (DONE):
  next_move_loss at move_10/20/30/40 (4 plies/game, ~2.67 OK rows/game);
  Constraint Atlas (15.1B), controlled modeling + robustness (15.1D/F);
  mover is always White (even-ply checkpoints) — a scope limitation.

Dense move-by-move analysis (NEW, this arc):
  one row per played ply (or a stratified sample), both colors;
  required for true degradation curves over time/phase/rating/eval.
```

`position_records_*` (interim) is **also checkpoint-only** (89,888 rows / 24,520 games ≈ 3.67
rows/game; `ply` min = 20) — it stores selected checkpoints + "last", **not** every ply.

## 5. Existing artifact inventory

- **Raw PGN caches (gitignored):** `data/raw/lichess/lichess_2024_09_first250k.pgn`,
  `…_2024_10_first250k.pgn` — present for both months (the same caches used for 15.0 FEN replay,
  11.3B hashing, 14.1C MultiPV).
- **`game_records_*` (interim):** one row/game; `n_plies`, `has_clock`, `has_eval`,
  `time_control` (all "600+0"), `result_class`, `termination`, Elos, `accepted_basic` —
  2024-09: 25,945 accepted (all clocked); 2024-10: 24,842.
- **`position_records_*` (interim):** checkpoint per-ply rows with `white_clock_s`/`black_clock_s`
  (0% null), `phase`, `result_class`, `termination`, Elos, `n_plies_total` — confirms the parser
  extracts `%clk`; `eval_cp` is 85.8% null (Lichess `%eval` sparse → **Stockfish needed**).
- **`next_move_loss_*` (processed):** checkpoint loss + the cp→ES transform conventions
  (`next_move_expected_score_transform_…json`, scale 348.4), mover-POV/cp-clip/mate-band logic.
- **`player_metadata_*` (gitignored):** hashed mover/White/Black IDs (join by `game_id`).
- **`splits_*.json`:** game-level train/val/test assignments (join by `game_id`).

## 6. Raw PGN / replay feasibility

- **Replay:** `parse_pgn.py` (`parse_game`, `extract_ply_records`) and
  `next_move_loss.reconstruct_fen_at_ply` / `stockfish_eval` already replay mainline games and
  emit per-ply FENs; dense extraction walks every `board.push(move)` instead of stopping at 4
  checkpoints. Feasible.
- **Caches:** present for both months; 14.1C confirmed 100% of primary `game_id`s match the raw
  cache.
- **Game-ID alignment:** `game_id` = Lichess Site slug, parsed identically everywhere; dense
  rows join cleanly to `game_records`/`player_metadata`/`splits` by `game_id`.
- **Per-ply FEN / hash:** `board.fen()` + the existing 16-char sha256 `_fen_hash` at every ply.
- **Privacy:** usernames are stripped at parse (DATA_POLICY.md); dense artifacts store **no
  usernames**; player hashes are joined later by `game_id` + `mover_color`.
- **Uncertainty:** none material — the caches and replay path are proven. The only open item is
  measuring real dense throughput, which the pilot does.

## 7. Per-ply clock and think-time feasibility

Lichess records `%clk` **after** each move. The parser already carries per-side clocks forward
(`white_clock_s`/`black_clock_s`, 0% null at checkpoints), so dense per-ply clocks are
reconstructable. For non-increment 10+0:

```
clock_after_s   = the mover's %clk on this ply
clock_before_s  = the mover's previous clock_after_s   (600 s on that player's first move)
think_time_s    = previous_same_player_clock_after_s − current_clock_after_s
```

This is compatible with current parser outputs (it already tracks both sides' clocks). Policies
(no silent drops):
- **Small negative think times** (annotation noise / rounding): clamp display to ≥0 and set
  `think_time_anomaly = True`; keep the raw value too.
- **Clock > 600 s** (impossible for 10+0): keep, flag `clock_anomaly = True`.
- **Missing `%clk`:** `think_time_s = null`, `clock_anomaly = True` (rare — 100% of accepted
  games are clocked, but individual plies could lack annotation).
- **Final timeout move:** `is_time_forfeit` games — keep, tag; the flagging move's clock_after may
  be ~0.
- Flags: `clock_anomaly`, `think_time_anomaly` — computed, never used to drop rows silently.

## 8. Evaluation strategy options

- **Option A — full dense sequential pre-position evaluation (RECOMMENDED).** Evaluate each
  position once, walking the game; the post-move value of ply *i* is the pre-move value of ply
  *i+1* (reused, not recomputed). `cp_loss_i = value(pos_i)_moverPOV − value(pos_{i+1})_moverPOV`
  (clipped at 0). **One eval per ply-position, no MultiPV, no separate best-move search** (the
  depth-d eval at `pos_i` is already the best-line value, exactly as in 15.0C). Most efficient
  and produces true dense curves. Caveat: half-ply depth asymmetry between `pos_i` (mover to
  move) and `pos_{i+1}` (opponent to move) — 15.0C's depth-13 sensitivity check found this
  **benign**; the pilot should re-spot-check it densely.
- **Option B — sampled pre/post pair evaluation.** Two evals per sampled move unless adjacency is
  reused; only cheaper than A if the sample is small, and loses the dense curve. Not recommended
  for full coverage.
- **Option C — stratified dense sample** (phase × clock × eval × rating × termination, optional
  low-clock enrichment): feasible and targeted; supports the atlas if treated descriptively or
  weighted; underrepresents normal positions; best as a *compute-reduction* of Option A, not a
  different method.
- **Option D — hybrid:** full-dense for a capped game subset + low-clock-enriched sampled moves.
  Validates the full pipeline and boosts rare cells; more design complexity.

**Recommendation:** 15.3B pilots **Option A** on a capped game sample (cleanest, most
eval-efficient, true curves); 15.3C runs Option A either full or as a stratified Option-A subset
depending on the pilot's measured throughput and the compute gate (§13/§18).

## 9. Candidate dense row universe

Options: (1) all legal played moves; (2) non-terminal moves only; (3) move ≥ 5 or ≥ 10 (reduce
opening-book noise); (4) move 10–60; (5) stratified sample; (6) low-clock-enriched; (7)
board-decided-only (robustness layer, not primary).

**Recommended pilot universe:** **all non-terminal, non-opening plies (move_number ≥ 5), both
colors,** from accepted 600+0 games — i.e. score every played move except the very first few
book moves and the terminal position. **Recommended likely full universe:** the same
(move ≥ 5, non-terminal), full dense Option A, **with a documented option to cap at move ≤ ~80**
if compute demands it. Dense rows must include **both White and Black moves** — fixing the
checkpoint White-to-move-only limitation. Counts (accepted, full): ~1.70M / ~1.63M plies/month
(all plies); ~1.24M / ~1.19M with plies < 19 excluded (move ≥ 10). Move ≥ 5 is between these
(~1.5M/month).

## 10. Candidate dense schema

One row per played ply (proposed `dense_move_loss_<tag>.parquet`):

```
game_id, month, split, ply, move_number, side_to_move, mover_color, opponent_color,
dense_position_type, move_uci, san_optional,
clock_before_s, clock_after_s, think_time_s,
white_clock_before_s, black_clock_before_s, white_clock_after_s, black_clock_after_s,
white_elo, black_elo, mover_elo, opponent_elo, elo_diff_mover,
termination, is_time_forfeit, result_class, mover_result,
pre_fen (or fen_hash), fen_hash, post_fen_hash,
eval_before_cp, eval_before_mate, eval_after_actual_cp, eval_after_actual_mate,
cp_loss_raw, cp_loss_clipped, expected_score_before, expected_score_after_actual,
expected_score_loss, is_mate_band,
phase, eval_band, clock_bucket, think_time_bucket, rating_bucket,
move_is_capture, move_is_check, move_is_promotion, move_is_castle, legal_move_count_optional,
mover_player_hash, opponent_player_hash,
clock_anomaly, think_time_anomaly, status, failure_reason
```

(Storage note: store `fen_hash` + `pre_fen` for the mover position only; `post_fen_hash` is the
next row's `fen_hash`, so it need not duplicate the full post-FEN.)

## 11. Field availability matrix

| field(s) | already available | source | requires new extraction | notes |
|---|---|---|---|---|
| game_id, month, termination, result_class, white/black_elo | yes | `game_records` / `position_records` | no | game-level join |
| split | yes | `splits_*.json` | no | game-level |
| is_time_forfeit | yes (derivable) | termination == "Time forfeit" | no | |
| mover/opponent_player_hash | yes | `player_metadata` | no | join by game_id + mover_color |
| ply, move_number, side_to_move, mover/opponent_color, move_uci | partial (checkpoints only) | parser | **yes (dense replay)** | need every ply |
| pre_fen, fen_hash, post_fen_hash, move tags (capture/check/promo/castle), legal_move_count | partial | parser/board | **yes (dense replay)** | per-ply board logic |
| per-ply clocks (before/after, both sides), think_time_s | partial (checkpoints only) | parser `%clk` | **yes (dense parse)** | think_time = consecutive-clock diff |
| eval_before_cp/mate, eval_after_actual_cp/mate | no (Lichess %eval 85.8% null) | **Stockfish** | **yes (engine pass)** | the compute driver |
| cp_loss_raw/clipped, ES before/after, expected_score_loss, is_mate_band | no | derived from evals | **yes (compute)** | reuse `next_move_loss`/transform conventions |
| phase, eval_band, clock_bucket, think_time_bucket, rating_bucket | no (derivable) | binning | **yes (compute)** | reuse atlas binning |
| ES transform (scale 348.4) | yes | `next_move_expected_score_transform_…json` | no | reuse train-fit transform |

## 12. Metric policy

- **Primary:** `expected_score_loss`, mover perspective.
- **Secondary:** clipped centipawn loss (cap ±1000).
- **Diagnostics:** raw centipawn loss **only within eval-band-conditioned panels**; large-loss
  indicators ES≥0.05, ES≥0.10, clipped CP≥100, clipped CP≥200.
- **Forbidden as headline:** percent eval swing.
- Rationale: raw CP loss is intuitive but nonlinear and **must not** mix near-equal vs +1000
  positions without eval-band conditioning; clipped CP loss is more stable; ES loss is best for
  scientific interpretation (bounded, outcome-linear). Conventions reuse the checkpoint pipeline
  (mover-POV, cp clip ±1000, mate-band exclusion from headline).

## 13. Runtime and storage estimates

Anchors (prior reports): single-PV Stockfish depth-12 ≈ **20–25 ms/eval** (15.0B/15.0C
checkpoint pass ≈ 24–25 min/month for ~65k evals; 14.1A single-PV ~20 ms). Depth-10 ≈ 2–3×
faster (14.1B pilot: d10 ~35 vs d12 ~106 ms for MultiPV-5 — single-PV ratio is gentler, assume
~2×).

| Strategy (both months) | evals | depth-12 (~25 ms) | depth-10 (~2× faster) |
|---|---|---|---|
| Full dense Option A (all plies, ~3.34M positions) | ~3.4M | **~17–24 h** | ~8–12 h |
| Full dense, move ≥ 10 (~2.44M) | ~2.5M | ~13–17 h | ~6–9 h |
| Stratified Option A (~25% of plies) | ~0.85M | ~4–6 h | ~2–3 h |
| 15.3B pilot (~1,500 games, 2024-09) | ~100k | **~40 min** | ~20 min |

Storage: `next_move_loss` is ~7 MB / 65k rows (incl. two FEN strings). Dense ≈ 3.34M rows; with
one `pre_fen` per row + ~50 columns, estimate **~400–700 MB both months** (or ~150 MB if
`fen_hash` only). Disk: 709 GB free — not a constraint. **Caveat:** the 14.1C run was suspended
repeatedly by overnight system sleep on battery; a ~17–24 h dense run **must** keep the machine
awake/plugged (or be chunked), else wall-clock balloons.

## 14. Sampling strategy options

- **Full dense Option A:** best coverage, ~17–24 h @ d12 — feasible but heavy; needs a
  kept-awake or chunked run.
- **Uniform game sample:** simple; underrepresents low-clock tails.
- **Stratified ply sample:** atlas-friendly; needs weighting or clear descriptive labels.
- **Low-clock-enriched sample:** good for time-pressure tails; not population-representative
  unless weighted.
- **Hybrid pilot (recommended for 15.3B):** a capped full-dense game sample (clean curves +
  pipeline validation) plus, if trivial, a small low-clock-enriched add-on.

**Recommendation:** pilot full-dense Option A on **~1,500 2024-09 games** (≈ median-game
coverage, ~100k evals, ~40 min — enough to estimate full cost precisely and validate every
field). For the **full run**, choose between full-dense (if a kept-awake ~17–24 h is acceptable)
and **stratified Option A** or **depth-10** if compute must be cut — decided at 15.3C after the
pilot measures real throughput.

## 15. Mate, terminal, missing-clock, and anomaly policy

- **Terminal positions / no legal next move:** excluded from headline move-loss (no "next move");
  recorded with `status` if encountered.
- **Checkmate / mate evals:** keep `is_mate_band` rows but separate from non-mate headline (reuse
  the ±MATE_CP_SENTINEL convention; mate folds to the ES cap).
- **Missing clocks:** `think_time_s = null`, `clock_anomaly = True`.
- **Illegal-move / replay failures:** `status = "fen_load_failure"`/`"engine_failure"` +
  `failure_reason`; never silently dropped.
- **Duplicated games:** dedup by `game_id` (caches are unique; assert).
- **Clock > start / negative think time:** keep with `clock_anomaly` / `think_time_anomaly`.
- **Abandoned games:** excluded by cleaning already (clean set = Normal / Time forfeit / Rules-1).
- **Time-forfeit games:** **keep, tag `is_time_forfeit`**; report board-decided and time-forfeit
  **side by side** (per 11.2B).
- **Ultra-short games:** retained but small `n_plies`; flagged via `n_plies`.
- **Openings:** plies < 5 (or < 10) excluded from the primary universe (book noise), tagged via
  `move_number`.
- **No silent drops:** every excluded/failed row carries `status` + `failure_reason`.

## 16. Validation requirements (15.3B pilot must check)

Row uniqueness (`game_id, ply`); legal replay (all moves legal); `move_uci` consistency;
per-player clock monotonicity (decreasing within a side, with anomaly flags); nonnegative
think-time rate; FEN-hash reproducibility (`_fen_hash(board.fen())` stable); eval status counts;
terminal handling; cp-loss sanity (≥0 after clip; finite); ES-loss bounds [0, ~0.8]; zero-loss
share (sanity vs checkpoint ~33%); month/split coverage; **no raw usernames** in output; player-
hash join feasibility (100% expected); no duplicate row multiplication; **depth-parity
spot-check** (d12 vs d13 on a small subset) given the dense chaining.

## 17. 15.3B pilot design recommendation

```
Recommended 15.3B pilot:
- month: 2024-09
- universe: ~1,500 accepted 600+0 games, all non-terminal plies with move_number >= 5, both colors
- eval strategy: Option A (one Stockfish eval per ply-position; post-value reused from next position)
- depth: 12 (project standard; + a depth-10 timing sub-test on the same sample to inform 15.3C)
- expected rows: ~90k–110k dense ply-rows
- expected evals: ~100k (one per position; ~+1500 for final positions)
- expected runtime: ~40 min at depth-12 (~25 ms/eval); ~20 min at depth-10
- artifact: data/processed/dense_move_loss_pilot_2024_09_v1.parquet  (gitignored)
- report:   reports/dense_move_loss_pilot_2024_09_v1.md  (committed; aggregate stats only, no FENs/usernames)
- validation: §16 checks
- kill conditions: §18 gates
- proceed to 15.3C only if validation passes and the extrapolated full runtime/storage are acceptable
```

Rationale for ~1,500 games: large enough to exercise every field, all phases, and low-clock
tails (1,500 × ~66 plies ≈ ~100k rows), yet ~40 min — so the full-run cost (~17–24 h) can be
extrapolated precisely before committing to it.

## 18. Full-extraction decision gates (before 15.3C)

Full dense extraction proceeds only if **all** hold: (1) raw cache / replay confirmed on the
pilot; (2) per-ply clock + think-time reconstruction validated (low anomaly rate); (3) measured
eval runtime acceptable and extrapolated full runtime acceptable (with a kept-awake/chunked plan
given the sleep risk); (4) artifact schema stable; (5) validation pass rate high (FEN-hash 1.0,
all-legal 1.0, no row multiplication); (6) storage acceptable; (7) no major metric bug
(cp_loss/ES bounds sane, depth-parity benign); (8) pilot report reviewed; (9) **Malachi approves
the full run** and the depth (d12 full vs d10 vs stratified Option A).

## 19. Risks and mitigations

- **Compute (~17–24 h @ d12):** mitigate via depth-10, stratified Option A, or chunked/overnight
  runs; **machine must stay awake** (14.1C sleep-suspension precedent) — decided at 15.3C.
- **Depth-parity in dense chaining:** spot-check d12-vs-d13 in the pilot; 15.0C found it benign.
- **Clock-annotation noise:** anomaly flags, never silent drops.
- **Storage growth:** prefer `fen_hash` over full `pre_fen` if size is a concern.
- **Orientation correctness (both colors now):** validate mover-POV cp_loss sign on White and
  Black moves in the pilot (the checkpoint pipeline was White-only).
- **Scope creep:** dense extraction is measurement only; sharpness/trajectory layers stay in
  15.5/15.7.

## 20. Recommended next ticket

**15.3B — Dense Move-by-Move Loss Extraction Pilot** (Option A, ~1,500 2024-09 games, depth-12 +
depth-10 timing sub-test, gitignored pilot artifact + committed aggregate report, §16 validation,
§18 gates). Not full extraction; not final synthesis.

## Non-claims

No dense move-quality result has been produced; no dense CP-loss curves; no dense
sharpness-conditioned curves. This audit changes **no** prior conclusions: C4 stands (eval-state
dominant; small robust secondary clock association), and **C3c remains directional but
underpowered/no-claim**. No causality; no "low clock causes blunders"; no "time pressure causes
worse reasoning"; no "Stockfish is ground truth"; no "human obviousness modeled"; no "DRAW
solved"; no best-predictor claim. Stockfish eval is objective context, not absolute ground truth.
