# Phase 14.1A — MultiPV Sharpness Feasibility / Compute Audit

**Labels:** AUDIT/DESIGN | read-only inspection + tiny no-artifact engine smoke
**Date:** 2026-06-14
**Owner:** Malachi Wang

## 1. Executive summary

MultiPV sharpness extraction is **feasible and cheap**. The checkpoint FENs are already
stored directly in the gitignored next-move-loss artifacts (`pre_fen`), so **no raw-PGN
reconstruction is needed**; MultiPV is a one-line change to the existing engine call
(`engine.analyse(board, Limit(depth=d), multipv=K)` — do **not** set MultiPV via
`configure`). A 30-position smoke benchmark on this machine gives **MultiPV-5 depth-12 ≈
66 ms/position → ~70 min/month → ~2.3 h for both months** — well under the 6–8 h "proceed"
gate. Dedup is negligible (~0.1% repeated FENs). The recommended v1 plan: extract a rich
**side-to-move local-narrowness** feature set (MultiPV-5, depth-12) plus board-logic
obviousness discounts, with a **train-defined binary `sharp_local_v1`** headline; defer
forward-line fragility and simple-trade detection. First modeling target (after a 14.1B
pilot and a 14.2A pre-registration) is **move-quality moderation (C3c)** — does the small
controlled clock→next-move-loss association grow in sharp positions — with outcome-level
flagging (C3a) / board-decided (C3b) views strictly secondary and kept separate. **Sharpness
has not been shown; nothing here is a sharpness result.** Predictive/descriptive framing
only; Stockfish eval is objective context, not absolute ground truth.

## 2. Why sharpness comes after C4

The C4 / move-quality arc is closed (15.1G): the outcome-level clock signal is substantially
the flagging channel (11.2B); eval state dominates next-move ES loss; clock has a small,
replicated, robust, **secondary** association after controls (15.1D/15.1F). Sharpness (C3)
is the natural extension — does **objective narrowness/non-obviousness moderate** the
constraint→move-quality relationship — and it builds directly on the settled C4 baseline
(move-quality target, eval-state-dominant structure, mover-player-clustered uncertainty).
Sharpness is **not** framed as rescuing the collapsed board-decided outcome residual.

## 3. Current engine / evaluation infrastructure

`stockfish_eval.py` uses `chess.engine.SimpleEngine.popen_uci` (python-chess 1.11.2) and
`engine.analyse(board, Limit(depth=depth))` — **single-PV only**, no `multipv` argument. The
reusable pieces:

- `resolve_stockfish_path()` (binary present at `/opt/homebrew/bin/stockfish`),
  `get_stockfish_version()`;
- `score_to_white_pov(PovScore) -> (cp, mate)` (White-POV, MATE_CP_SENTINEL convention) —
  reusable per candidate;
- `derive_sf_eval_features`, `_fen_hash` (16-char sha256 prefix, matches the stored
  `fen_hash`).

**Minimal MultiPV API:** pass `multipv=K` to `analyse()`, which returns a **list of K info
dicts** ordered best-first for the side to move; each has `score` (PovScore), `pv` (move
list; `pv[0]` = candidate move), `depth`, `nodes`. **Caveat confirmed in the smoke test:**
python-chess auto-manages MultiPV — calling `engine.configure({"MultiPV": K})` raises
`EngineError: cannot set MultiPV which is automatically managed`. So 14.1B must rely solely
on the `multipv=` kwarg. A small new helper (e.g. `analyse_fen_multipv`) returning the
per-candidate `(relative_cp, white_cp, mate, move_uci, depth)` list, reusing
`score_to_white_pov` and adding a relative (mover-POV) extractor, is all the code needed.
Depth-12 keeps evaluation semantics consistent with 15.0C's single-PV pass (the checkpoint
`pre_sf_eval_cp` is a depth-12 best-line value), so MultiPV-1 should match it.

## 4. Checkpoint universe and artifact readiness

Read-only inspection of both `next_move_loss_*` artifacts:

| | 2024-09 | 2024-10 | Both |
|---|---|---|---|
| OK checkpoints | 64,371 | 61,868 | **126,239** |
| OK non-mate-band | 61,956 | 59,625 | **121,581** |
| mate-band (OK) | 2,415 | 2,243 | 4,658 |
| move_10 / 20 / 30 / 40 (OK) | 24,384 / 19,639 / 12,950 / 7,398 | 23,364 / 18,927 / 12,365 / 7,212 | — |
| split (OK) train/val/test | 45,147 / 9,665 / 9,559 | 43,243 / 9,315 / 9,310 | — |
| unique `pre_fen` (OK) | 64,326 (dedup 0.1%) | 61,849 (dedup 0.0%) | negligible |

**Readiness:** `pre_fen` (checkpoint FEN) is stored **directly** as a column — MultiPV reads
it straight from the parquet, no reconstruction. `fen_hash` is present for validation;
`pre_sf_eval_cp` / `mover_pre_cp` give the existing best-line value for top-1 agreement;
`is_mate_band`, `selected_position_type`, `split_set`, `game_id` are all present. **Dedup
gives no meaningful savings** (FENs are essentially unique), so cost scales with full row
count. Mover is always White at these even-ply checkpoints (scope limitation carried from
15.x). **Cache key** (if ever needed): `(fen_hash, depth, multipv_k, engine_version)`.

## 5. MultiPV compute-cost estimate

30-position smoke benchmark (2024-09 non-mate FENs, depth-12 single-thread Stockfish on this
machine; **no artifacts written**):

| Setting | ms/position | per month (~63k OK) | both months (~126k) |
|---|---|---|---|
| MultiPV-3 depth-10 | ~11 | ~12 min | ~0.40 h |
| MultiPV-5 depth-10 | ~28 | ~30 min | ~0.99 h |
| MultiPV-3 depth-12 | ~37 | ~39 min | ~1.31 h |
| **MultiPV-5 depth-12 (recommended)** | **~66** | **~70 min** | **~2.32 h** |
| MultiPV-10 depth-12 | ~139 | ~146 min | ~4.86 h |

Notes: K=5 returned exactly 5 lines per position; K=10 averaged 9.8 (a few positions have
fewer legal moves → right-censor at K). Runtime scales roughly linearly in K and steeply in
depth (d10→d12 ≈ 2.3×). Anchors are consistent with 15.0B/15.0C (single-PV ~20 ms/pos). Dedup
won't reduce cost. These are approximate single-run timings.

## 6. v1 sharpness feature design

Project definition: *a position is sharp when preserving objective value requires a narrow
and non-obvious move or sequence.* v1 implements **local narrowness + obviousness discount**
only; **forward-line fragility is deferred**. Scores for ranking/gaps use the **side-to-move
(relative) POV** (candidates ordered best-first for the mover); White-POV cp is also stored
for lineage. Expected-score (ES) values reuse the existing train-fit cp→ES transform
(scale 348.4, 15.0C) applied per candidate.

**A. Local engine narrowness** (from the MultiPV-K list):
- `multipv_best_score`, `multipv_second_score`, `best_second_gap_score`,
  `best_second_gap_cp`;
- value-preserving counts within {30, 50, 100} cp of best and within {5, 10, 20} ES-points
  of best (right-censored at K);
- entropy and softmax concentration over the top-k scores; `worst_of_topk_score_loss`;
- `one_good_move_score_10` (exactly one move within 10 ES-pts), `few_good_moves_score_10`
  (≤2 within 10 ES-pts);
- `sharp_local_binary_v1` (see §7).

**B. Obviousness / fake-sharpness discounts** (pure board logic on `pre_fen` + `pv[0]`, no
human labels): best move is capture / check / promotion / quiet; in-check with limited legal
evasions → `forced_evasion`; `obvious_recapture` (best move recaptures on the square the
opponent just moved to — feasible from `post_fen`/last move if available, else flag as
unavailable); `fake_sharpness_discount` = engine-narrow **but** obvious recapture / forced
evasion. **Simple-trade detection is deferred** (not trivially reliable; consistent with the
v11 standing rule excluding `best_move_is_simple_trade` from the v1 composite).

**C. Deferred forward-line fragility** (explicitly out of v1): only-move chain length along
the PV; narrow decision nodes over the next K plies; quiet-only-move nodes; cumulative ES
fragility; multi-precise-move sequences. Reason: higher compute/complexity; local sharpness
must work first.

## 7. v1 headline composite recommendation

**Recommend a train-defined binary headline plus a continuous secondary**, decided at 14.2A:

- **Primary (binary): `sharp_local_v1`** =
  `value_preserving_move_count_es_10 <= 2 AND NOT (obvious_recapture OR forced_evasion)`,
  with **MultiPV-K ≥ 5** and the count right-censored at K (K=5 & count=5 ⇒ "5 or more", not
  "exactly 5"). Simple, interpretable, board-logic obviousness discount.
- **Secondary (continuous): `best_second_gap_score`** (mover-POV ES gap best−second) and/or
  top-k entropy, with a **train-defined top-tercile** high-sharpness indicator as an
  alternative binary for robustness.
- Extract the **full feature set**; the headline used for the C3c pre-registration is the
  single binary `sharp_local_v1`; continuous features and the tercile indicator are
  secondary/exploratory. Terciles, if used, are **train-defined** (no test leakage), mirroring
  the C4 discipline.

## 8. Orientation recommendation

Taxonomy and v1 decision:

1. **Side-to-move sharpness** — the computational primitive MultiPV gives directly; **store
   for all positions**.
2. **Advantaged-player conversion sharpness** — derived headline candidate (restrict to
   positions where the side to move is the board leader); how hard the better-placed player
   must work to preserve value. Compute as a **derived view** from the stored primitive (no
   extra engine work).
3. **Defensive sharpness** (worse side must find a narrow resource) — exploratory derived view.
4. **Mutual/tactical sharpness** — exploratory.

**Recommendation:** v1 extraction stores the **side-to-move primitive for every checkpoint**;
the advantaged-player / defensive views are computed later by filtering on the stored eval
sign, not by re-running the engine. **First modeling target = move-quality C3c**: does the
small controlled clock↔next-move-loss association (15.1D/15.1F) **grow in high-sharpness
positions**? Outcome-level views are secondary and **kept separate**: C3a (flagging-risk
sharpness moderation) and C3b (board-decided outcome moderation, cautious — the residual it
would moderate has already collapsed, so framed carefully).

## 9. Proposed artifact schema (for 14.1B, gitignored)

Pilot: `data/processed/multipv_sharpness_pilot_2024_09_250k_v1.parquet`; full later:
`data/processed/multipv_sharpness_{2024_09,2024_10}_250k_v1.parquet`. **One row per
checkpoint**, joinable to next-move-loss on `(game_id, selected_position_type)`.

Columns: `game_id`, `selected_position_type`, `checkpoint_ply`, `fen_hash`, `engine_name`,
`engine_version`, `depth`, `multipv_k`, `side_to_move`; per-candidate top-k as **fixed wide
columns** `pv{1..K}_move_uci`, `pv{1..K}_cp` (mover-POV), `pv{1..K}_white_cp`, `pv{1..K}_mate`,
`pv{1..K}_es` (wide is simpler/safer than nested for Polars/Parquet); narrowness features
(`best_second_gap_score/_cp`, count-within-threshold, entropy, concentration,
`worst_of_topk_score_loss`); obviousness flags (`best_is_capture/check/promotion/quiet`,
`forced_evasion`, `obvious_recapture`, `obvious_recapture_available`); composites
(`sharp_local_binary_v1`, continuous `sharp_score_v1`); status/diagnostics (`status` ∈
{ok, engine_failure, fen_load_failure}, `multipv_count`, `is_mate_band`, `fen_hash_matches`).
**No raw PGN text, no usernames.** Player hashes are joined later from `player_metadata` (not
duplicated here).

## 10. Pilot plan for 14.1B

- **1,000 positions from 2024-09**, **stratified by checkpoint** (250 each move_10/20/30/40),
  including a handful of mate-band rows to exercise the mate-band path.
- **MultiPV-5, depth-10 first** (cheap insurance, ~28 ms/pos → seconds for 1k), then
  **MultiPV-5 depth-12** if depth-10 is stable — compare runtime and feature stability.
- Produce a **pilot report** (`reports/...`) + a gitignored pilot artifact.
- **Full extraction only after** the pilot report passes validation (§11) and the compute
  gate (§12). Given the benchmark, depth-12 is affordable, so the depth-10-first step is
  optional risk reduction, not a necessity.

## 11. Validation checks for 14.1B

- `_fen_hash(pre_fen)` matches the stored `fen_hash` (reconstruction-free, but validates the
  FEN read).
- MultiPV returns **≥ min(K, n_legal_moves)** lines; right-censor and record `multipv_count`.
- **Top-1 agreement:** MultiPV `pv1` White-POV cp agrees (within depth tolerance) with the
  existing checkpoint `pre_sf_eval_cp` (the prior best-line value); record agreement rate.
- cp/mate conversion stable; no impossible values (cp within ±MATE_CP_SENTINEL; ES ∈ [0,1]).
- **Mate-band handling explicit** (`is_mate_band` carried; sharpness features null or flagged
  in mate band, never silently computed).
- Generated artifacts **gitignored** (`git check-ignore`).
- **Runtime estimate reported** from the pilot; dedup confirmed negligible.
- Determinism: fixed depth + fixed engine version ⇒ reproducible; record `engine_version`.

## 12. Compute gate and re-scope criteria

- **MultiPV-5 depth-12 both months ≈ 2.3 h** → **GO**: under the 6–8 h proceed threshold;
  full extraction approved **after the 14.1B pilot passes**. No dedup or subset-first needed.
- 8–24 h (not our case): consider depth-10, one-month-first, or overnight.
- > 24 h (not our case): re-scope to MultiPV-3 / depth-10 / sample-based study.
- Contingency: if depth-12 stability or memory is an issue in the pilot, fall back to
  MultiPV-5 depth-10 (~1.0 h both months) and note the depth in pre-registration.

## 13. Relationship to prior trajectory

Prior trajectory remains **deferred** (C4 decision, 15.1G). For sharpness: **do not block
MultiPV extraction on trajectory** — 14.1B extraction is independent of it. Revisit
trajectory at **14.2A pre-registration**, because a sharpness×clock moderation result may
strengthen the case for trajectory controls (sharp positions may correlate with prior
struggle). Default: treat trajectory as the **same stated limitation** as C4 unless a
sharpness result makes it pivotal, in which case extract before the **final** sharpness
claim — not before the pilot.

## 14. 14.2A pre-registration requirements

Before any sharpness modeling, 14.2A must lock: the **sharpness feature definition**
(`sharp_local_v1`) and the obviousness discount; the **threshold / train-defined tercile**
rule; the **orientation** (side-to-move primitive vs advantaged-player-conversion headline);
the **targets** (C3c move-quality **primary**; C3a flagging-risk secondary; C3b
board-decided-outcome secondary/cautious — never conflated); **train/val/test discipline**
(estimate on train+val, locked-test confirmation, as in C4); **mover-player-clustered
uncertainty**; the **month-replication rule** (credit only if it replicates 2024-09/2024-10);
**success/failure/kill criteria** (e.g., a sharpness×clock interaction on next-move loss that
is positive, replicated, CI-excludes-zero under clustering, and survives the C4-style
robustness checks); and **whether prior trajectory is required** for the final claim.

## 15. Risks and caveats

- **No sharpness result exists**; this is a feasibility/design audit only.
- Predictive/descriptive framing only; not causal; no "degradation curve" language.
- **White-to-move only** (even-ply checkpoints) — scope limitation carried forward.
- Stockfish MultiPV at fixed depth is an **approximation of narrowness**, not ground truth;
  candidate ordering can shift with depth/engine version (top-1 was stable in the smoke test).
- **Anti-circularity:** sharpness must be defined from engine geometry / board logic, **not**
  from human move frequencies or outcomes (Tier A discipline), or it would tautologically
  predict human error.
- Obviousness discounts are heuristic; `obvious_recapture` needs the last move / `post_fen`
  and is flagged unavailable when it can't be computed.
- Mate-band excluded from sharpness features; DRAW remains sparse; prior trajectory deferred.
- Benchmark is a single 30-position run on one machine — treat compute numbers as approximate.

## 16. Recommended next ticket

**14.1B — Pilot Sharpness Extraction** (1,000 stratified 2024-09 positions, MultiPV-5
depth-10 then depth-12, gitignored pilot artifact + report, validation per §11). On a passing
pilot, full both-months extraction (~2.3 h) is pre-approved by the §12 gate, followed by
**14.2A — Sharpness Interaction Pre-Registration** before any C3c modeling. Prior-trajectory
extraction remains an optional follow-up, revisited at 14.2A.
