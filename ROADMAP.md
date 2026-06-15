# Roadmap

This roadmap is phase-based, with audit/implementation pairs wherever practical.

Each audit/implementation pair should produce a report. The roadmap is expected to evolve as the project learns from real data.

## Current project direction

```text
Project: Modeling Human Strategy Under Constraints
Initial source: Lichess standard rated PGN database
Initial scope: 10+0 only, TimeControl "600+0"
Initial target: 3-class White win / Draw / Black win
Initial model path: baselines -> logistic regression -> GBM -> calibrated GBM
Final aspiration: every-ply human outcome prediction under constraints
```

## Active v11 Research Arc (accepted 2026-06-12, Tickets 11.0A/11.0B)

The v11 re-scope was **accepted and applied** after the 11.0A prior-work verification
(`reports/phase_reports/phase_11_0a_prior_work_novelty_rescoping_audit.md`) confirmed
the novelty lane is open — no prior work performs eval-controlled, outcome-level
clock-residual moderation (11.0A kill condition not triggered).

- **Current arc: Phase 11 onward** — positioning/claim hardening (11), score-scale
  robustness + stronger clock controls (12), cheap difficulty layer (13), MultiPV
  sharpness (14), Constraint Atlas / move-quality curves (15), cross-time-control
  dose-response (16), packaging (17). **⚠️ This original ordering was revised by the
  evidence — see "Post-C4 Reconciliation (Ticket 15.1H)" below: Phase 15 move-quality
  work was pulled earlier and is now CLOSED (C4 consolidated), Phase 12/13 are deferred/
  non-blocking, and sharpness (14) has NOT been shown and starts with a feasibility audit.**
- **The authoritative detailed Phase 11–17 architecture lives in
  `docs/roadmap_rescope_v11_draft.md`** (with the 11.0A §9 edits folded in). This file
  stays the high-level active roadmap.
- Phases 0–9 below remain the completed historical record, unchanged.
- Phase 10 / sequence models remain **gated, not next** (gate restated at the end of
  the v11 document; conditions unchanged).
- The earlier "package first" recommendation is reconciled, not discarded: packaging is
  now Phase 17, *after* claim hardening (11.2 termination decomposition, 11.3 player
  leakage), because the 11.0A prior-work findings changed what the packaged claim must say.
- Standing rules adopted with the arc: Tier A / Tier B sharpness discipline
  (anti-circularity); EXP-012+ numbering for the new arc; preprints citable but always
  labeled as such; ChessMimic described only as "a strong neural reference point, not a
  direct ceiling"; advantaged-player conversion sharpness as the Phase 14 headline
  orientation (side-to-move-overall as labeled secondary); `best_move_is_simple_trade`
  excluded from the v1 sharpness composite pending the 13.2 mini-audit.
- Related work: `docs/RELATED_WORK.md`. Pre-registration: `PREREGISTRATION.md`
  (v1, refined by 11.1A — four primary contrasts locked).
- **11.2B result (replicated): the board-decided clock residual COLLAPSES** —
  the E3→E4 signal is substantially the time-forfeit/flagging channel
  (board-decided: +0.0010 cz / +0.0060 sign-reversed; time-forfeit: −0.118/−0.131).
  Central claim re-framed per the pre-registered collapse branch
  (`reports/termination_decomposition_combined.md`).
- **11.2C reframing (done):** the outcome-clock claim is reframed toward the flagging
  channel; the board-play-quality question moves to Contrast C4 (next-move quality),
  which does not depend on the outcome residual surviving. Sharpness (C3) is split into
  C3a flagging-risk / C3b board-decided-outcome (cautious) / C3c move-quality. See
  `reports/phase_reports/phase_11_2c_claim_reframing_audit.md` and the updated
  `PREREGISTRATION.md`.
- **Roadmap reorder:** 11.2C recommends moving the **15.0A move-quality / Constraint
  Atlas audit earlier** to directly test board-play quality. Player-leakage hardening
  (11.3A/11.3B) is reordered to follow 15.0A but remains required before any C4 primary
  modeling result (15.1B) is locked; it also gains a new purpose (checking whether
  player leakage inflates the flagging-channel estimate). No phases removed.
- **15.0A done:** next-move quality is feasible (Level 1–2). No FEN/move stored in
  processed artifacts, but the local raw PGN caches + the existing `stockfish_eval`
  replay reconstruct post-move FENs (one extra `board.push()`); 98.5% of primary
  checkpoints have a next move; the checkpoint `sf_eval_cp` is already the best-line
  value, so only a post-move eval pass is needed (~30 min/month). Primary metric:
  expected-score loss (mover's perspective), `max(0, ES_best_before − ES_after_actual)`;
  clipped-cp loss as the cheap first metric. See
  `reports/phase_reports/phase_15_0a_move_quality_constraint_atlas_audit.md`.
- **15.0B done (pilot):** `next_move_loss.py` + 41 tests. 1000-row 2024-09 pilot
  succeeded — 982 OK, 0 reconstruction/engine failures, 0 FEN-hash mismatches, ~21
  min/month estimate. Post-move FEN reconstructed from the local raw cache (one
  `board.push()` past the checkpoint); only post-move positions evaluated (checkpoint
  `sf_eval_cp` is already the best-line value). Pilot metric = clipped cp loss
  (mover's perspective, cap ±1000); expected-score loss deferred to 15.0C. Full pass
  gated (`--limit`/`--allow-full-run`), not run. At numbered checkpoints the mover is
  always White (even-ply convention). See
  `reports/phase_reports/phase_15_0b_next_move_loss_extraction.md`.
- **15.0C done:** full both-months next-move loss extraction (126,239 checkpoint moves;
  0 reconstruction/engine failures, 0 FEN-hash mismatches; ~48 min total). Train-fit
  pooled cp→expected-score transform (scale=348.4, 89,764 train rows). Clipped cp loss
  median 19 both months; ES loss median ~0.010 both. Depth-13 parity check benign
  (0.2cp aggregate shift). Board-decided ≈ time-forfeit checkpoint loss (descriptive —
  consistent with the 11.2B flagging-channel reframing). 1,580 tests passing. Artifacts
  gitignored. See `reports/next_move_loss_combined.md` and
  `reports/phase_reports/phase_15_0c_full_next_move_loss_extraction.md`.
- **15.1A done (audit):** 15.0C artifacts complete and clean (0 dups, 0 nulls in
  headline metrics, row counts match; no repair needed). Headline metric = expected-score
  loss (mover's perspective): mean+median+p75/p90 + large-loss probabilities; clipped cp
  secondary; mate-band excluded; month-by-month then combined; all-games and
  board-decided side-by-side. Clock bucketed WITHIN checkpoint (move_10 is 99.96%
  over-180s — marginal clock curves forbidden). Rating 200-pt bins / quantiles; eval
  bands near_equal/slight/clear/decided; cell rules n<50 hidden / 50–300 descriptive /
  ≥300 CI-bearing with game-level bootstrap. Scope limitation: numbered checkpoints are
  White-to-move only. See
  `reports/phase_reports/phase_15_1a_constraint_atlas_descriptive_curves_audit.md`.
- **15.1B done (descriptive):** `constraint_atlas.py` + 55 tests; three committed Atlas
  reports (2024-09, 2024-10, combined). Disciplined readout: **no clock gradient on
  next-move loss among CI-bearing cells** (late cells flat ~0.028–0.031 both months); the
  apparent low-clock bump is a sparse-cell artifact that **does not replicate**
  (2024-09 `<10s` 0.042 vs 2024-10 0.028); **strong replicated eval-band pattern** (ES
  loss peaks at near_equal/slight, lowest at decided, both months). Time-forfeit
  checkpoint loss slightly above board-decided (descriptive). 1,635 tests passing. See
  `reports/constraint_atlas_combined.md` and
  `reports/phase_reports/phase_15_1b_constraint_atlas_descriptive_curves.md`.
- **11.3A complete (audit):** player IDs exist only in raw PGN headers (raw usernames,
  `White`/`Black`), **stripped at parse**, absent from all processed artifacts; recoverable
  via `game_id` join. Player dependence is **severe**: ~86–87% of checkpoint rows touch a
  player spanning >1 split; ~4,000+ players in both train and test each month. Concentration
  moderate (top decile ~30% of rows, max ~36 games). Cross-month: ~19.5% of players recur,
  ~40% of rows involve a cross-month player → months are a strong-but-not-independent
  replication. **Strict player-disjoint 3-way split INFEASIBLE** — player–game graph has a
  giant component (~92% games / ~86% players per month, ~95% pooled). Recommended hardening:
  **player-clustered (mover-player) bootstrap** (existing game-cluster machinery
  generalizes), hashed IDs in ignored artifacts only, no usernames ever committed. See
  `reports/phase_reports/phase_11_3a_player_disjoint_cluster_feasibility_audit.md`.
- **11.3B complete (implementation):** privacy-safe player metadata extraction
  (`player_metadata.py`, hashed IDs in gitignored artifacts, no raw usernames) + configurable
  one-way cluster bootstrap (`clustered_uncertainty.py`: mean / mean-diff / paired delta).
  Both headline findings **survive player clustering**. (1) 11.2B termination: time-forfeit
  channel stays large with CI excluding zero under game/White/Black clustering (09 −0.1183;
  10 −0.1305); board-decided stays unresolved/collapsed; **game-clustered reproduces the
  published 11.2B CIs exactly**. (2) 15.1B atlas: eval-band ordering holds under mover-player
  clustering (slight−decided +0.024, near_equal−decided +0.016, both exclude zero, both
  months); late clock cells flat. Player clustering widens CIs only modestly (moderate
  concentration). 56 module tests; 1,671 total passing. Two-way White×Black clustering
  deferred. See `reports/player_clustered_termination_decomposition.md`,
  `reports/player_clustered_constraint_atlas.md`,
  `reports/player_metadata_privacy_summary.md`,
  `reports/phase_reports/phase_11_3b_player_metadata_clustered_uncertainty.md`.
- **15.1C complete (audit):** controlled C4 modeling design locked. Inputs clean (every
  column, splits, 100% mover-hash coverage). Target = `expected_score_loss` (non-mate,
  ~33% zero-inflated, right-skewed) → **primary OLS adjusted-mean model + cluster bootstrap**;
  large-loss logistic (ES>0.05/0.10) as robustness; two-part deferred. **Primary contrast =
  coarse clock (60_180/under_60 vs over_180) net of checkpoint + eval band + rating_z + month
  + termination binary, mover-player-clustered**; eval-band contrast (vs decided) = positive
  control; **a clock null is a pre-registered acceptable outcome**. under_60 sparse
  (~750–800/mo, confounded) → exploratory; 60_180 (~2,600/mo) stable. Discipline: estimate on
  train+val, **test reserved as locked confirmation**, month = replication. `statsmodels` NOT
  installed → use sklearn + own cluster bootstrap (no new dep). NOTE: next-move-loss rows carry
  NO pre-checkpoint trajectory feature → 15.1D controls = eval+phase+rating+termination+month;
  prior-trajectory is a separate extraction ticket. See
  `reports/phase_reports/phase_15_1c_controlled_move_quality_modeling_audit.md`.
- **15.1D complete (implementation):** controlled C4 model built (`controlled_move_quality.py`:
  one-hot design w/ fixed refs, numpy OLS adjusted-mean, sklearn large-loss logistic,
  `cluster_bootstrap_refit`+`summarize_contrasts` added to `clustered_uncertainty.py`,
  per-month+pooled+locked-test, CLI). 16 tests; 1,687 total passing. 200 bootstrap reps,
  seed 42, 200/200 OLS refits. **RESULTS:** (1) eval-band positive control DOMINANT and
  replicated — slight +0.0286 / near_equal +0.0223 / clear +0.0158 vs decided (pooled, all
  exclude 0, both months + test). (2) clock association SMALL but **NON-NULL and REPLICATED** —
  `60_180` vs `over_180` +0.0034 [+0.0015,+0.0051], `under_60` vs `over_180` +0.0072
  [+0.0042,+0.0115] (pooled; monotone less-clock→more-loss; both months + test exclude 0);
  ~5–8× smaller than eval band. Refines (not overturns) 15.1B: descriptive cells flat
  marginally; small clock residual emerges once eval band is conditioned on. (3) termination
  tf-vs-board_decided ≈0 after controls (consistent w/ 11.2B flagging reframing). Logistic
  signs agree. Predictive/descriptive, not causal. See
  `reports/controlled_move_quality_combined.md` +
  `reports/phase_reports/phase_15_1d_controlled_move_quality_modeling.md`.
- **15.1E complete (audit):** robustness threats to the small 15.1D clock association ranked;
  two confirmed live empirically — (1) within-band |cp| varies by clock (`slight` low-clock
  ≈205cp vs over_180 ≈189cp; `near_equal` low-clock ≈30–38 vs ≈45, both months) → coarse-band
  residual confound; (2) `under_60` only 31%/36% board-decided (vs 86.5% overall) → ~2/3
  time-forfeit, a flagging-survivor population. **Mandatory 15.1F checks:** continuous
  `abs(mover_pre_cp)` eval control, late-only (move_30+40), **board-decided-only**, rating-spec
  sensitivity, metric sensitivity (`clipped_cp_loss` + large-loss), cluster sensitivity
  (mover/game/White-Black) → compact robustness matrix (60_180 contrast × month/pooled).
  Success/weaken/mixed criteria LOCKED pre-implementation. Data ready, no extraction;
  prior-trajectory absent = stated limitation. v11 draft tagged superseded by live roadmap;
  full reconciliation deferred to post-15.1F. See
  `reports/phase_reports/phase_15_1e_clock_association_robustness_audit.md`.
- **15.1F complete (implementation):** clock-association robustness matrix built
  (`clock_association_robustness.py`: configurable variant design reusing the 15.1D layer,
  OLS/logistic variant fit with chosen cluster key, 12-check mandatory matrix, locked-criteria
  verdict logic, month+combined reports, CLI). 18 tests; 1,705 total passing. 200 reps seed 42.
  **CONCLUSION: SURVIVES.** Pooled `60_180` vs `over_180` +0.0034 [+0.0015,+0.0052] holds under
  EVERY mandatory check: continuous within-band |cp| control +0.0034 (coarse-band threat does
  NOT eliminate it), board-decided-only +0.0034 (isolated from flagging), rating bins/quadratic
  ~+0.0032/+0.0033, late-only pooled +0.0033, clipped_cp +6.09 / logistic ES>0.05 +0.088 /
  ES>0.10 +0.141 (directional agree), game/White/Black clustering all +0.0034 — all pooled CIs
  exclude 0, positive both months + locked test. Small + SECONDARY to eval band (~5–8×),
  predictive/descriptive NOT causal. under_60 board-decided-only contains 0 (sparse, ~2/3 TF).
  Per-month subset CIs occasionally touch 0 (low power for ~+0.003 effect); verdict rests on
  pooled + consistent sign per locked criteria. See `reports/clock_association_robustness_combined.md`
  + `reports/phase_reports/phase_15_1f_clock_association_robustness.md`.
- **15.1G complete (consolidation):** C4 / move-quality arc consolidated. **SETTLED C4 CLAIM
  (predictive/descriptive, NOT causal):** (a) the final-outcome clock signal is substantially
  the flagging/time-forfeit channel (11.2B); (b) next-move ES loss is dominated by eval state
  (15.1B/15.1D); (c) after controls, clock retains a small, replicated association with
  next-move ES loss (pooled 60_180 vs over_180 +0.0034) that (d) survives all 15.1F robustness
  checks incl. board-decided-only, and (e) is ~5–8× smaller than the eval-band structure;
  (f) all findings replicate across both months + survive player clustering (11.3B).
  **Prior-trajectory decision: OPTION A — DEFER.** The artifacts carry no pre-checkpoint
  trajectory feature; the original C4 "mandatory" trajectory lock is reinterpreted (deviation
  noted in PREREGISTRATION) as mandatory only before a CAUSAL/mediation claim — the
  descriptive C4 claim is closed now with trajectory as the stated headline limitation +
  recommended optional follow-up. See `reports/phase_reports/phase_15_1g_c4_claim_consolidation.md`
  and `reports/c4_move_quality_arc_summary.md`.
- **15.1H complete (reconciliation):** roadmap docs reconciled with the post-C4 evidence
  chain (this patch). Live claim, Phase 14/15 ordering, Phase 12/13 status, and the sharpness
  handoff are stated in "Post-C4 Reconciliation" below. v11 draft carries a supersession note.
  See `reports/phase_reports/phase_15_1h_roadmap_reconciliation_patch.md`.
- **14.1A complete (audit):** MultiPV sharpness extraction is **feasible and cheap**.
  Checkpoint FENs already stored directly (`pre_fen` column in the next-move-loss artifacts)
  → no raw-PGN reconstruction; MultiPV is a one-line change (`engine.analyse(..., multipv=K)`;
  do NOT set MultiPV via `configure` — python-chess auto-manages it). 30-position smoke
  benchmark: **MultiPV-5 d12 ≈ 66 ms/pos → ~70 min/month → ~2.3 h both months** (MultiPV-3 d12
  ~1.3 h; MultiPV-10 d12 ~4.9 h) — under the 6–8 h GO gate. Universe: 126,239 OK checkpoints
  (121,581 non-mate) both months; dedup negligible (~0.1%). v1 = side-to-move local-narrowness
  feature set (MultiPV-5 d12) + board-logic obviousness discounts; headline = train-defined
  binary `sharp_local_v1` (≤2 value-preserving moves within 10 ES-pts AND not obvious
  recapture/forced evasion); forward-line fragility + simple-trade DEFERRED. First target =
  move-quality C3c (does the small controlled clock↔next-move-loss assoc grow in sharp
  positions); C3a/C3b outcome views secondary + separate. Sharpness NOT shown. See
  `reports/phase_reports/phase_14_1a_multipv_sharpness_feasibility_audit.md`.
- **14.1B complete (pilot):** `multipv_sharpness.py` + 22 tests (1,727 total passing). Ran
  MultiPV-5 pilot on 1,000 stratified 2024-09 checkpoints (250/checkpoint). **Framing revision
  (Malachi): primary v1 = OBJECTIVE value fragility** (narrow viable set, steep drop-off,
  legal-choice clutter); surface tags + surface-bait diagnostics are **EXPLORATORY, NOT human
  obviousness** (deferred to a later Tier B layer). Pilot CLEAN: 1000/1000 OK, FEN round-trip
  1.0, all-candidates-legal 1.0, median MultiPV count 5, top-1 vs stored best-line median
  |Δcp| 15. Features non-degenerate (median best→2nd ES gap 0.012, median n_good_10es 5,
  `sharp_value_fragility_v1` base rate 0.142). Depth-10 vs depth-12: **sharpness-composite
  agreement 0.95** (literal top-1 move only 0.64 — expected in flat positions) → depth-12
  preferred. Runtime: d12 ~106 ms/pos (vs 14.1A 30-pos smoke 66 ms; stratified sample has more
  complex late positions) → **full projection ~3.7 h both months, still under 6–8 h GO gate**.
  Pilot artifact gitignored; no PGN/usernames. Candidate composites pending 14.2A. Sharpness
  NOT shown; no human-obviousness claim. See
  `reports/multipv_sharpness_pilot_2024_09_250k_v1.md` +
  `reports/phase_reports/phase_14_1b_pilot_sharpness_extraction.md`.
- **Next ticket: 14.1C — Full Sharpness Extraction** — both months, MultiPV-5 depth-12 (~3.7 h),
  gitignored artifacts + report, reusing `multipv_sharpness.py`. Full artifacts needed so 14.2A
  can inspect sharpness distributions before locking thresholds → then **14.2A — Sharpness
  Interaction Pre-Registration** before any C3c modeling. Prior-trajectory extraction = optional
  follow-up, revisited at 14.2A.

## Post-C4 Reconciliation (2026-06-14, Ticket 15.1H)

The live arc diverged from the original v11 sequence because the experiments learned new
things. This section is the current source of truth; the bullet list above is the
chronological completed-ticket log, and `docs/roadmap_rescope_v11_draft.md` is retained as
historical design context (superseded in part).

**Post-C4 live claim (predictive/descriptive, NOT causal):**
At the final-outcome level, clock features primarily capture flagging / time-forfeit risk.
At the next-move level, eval state is the dominant structure in expected-score loss. After
conditioning on checkpoint, eval band, rating, month, and termination, clock retains a small,
replicated, robust association with next-move loss. This association is predictive/descriptive,
not causal, and is secondary to eval-band structure (~5–8× smaller). Prior trajectory remains
deferred as an explicit limitation.

**What changed vs the original v11 ordering:**
- **Phase 15 was pulled earlier.** 11.2B collapsed/sign-reversed the board-decided outcome
  residual (the E3→E4 clock signal is substantially the flagging channel), so the board-play
  question moved to direct next-move-quality measurement (C4) rather than waiting behind
  Phases 12–14.
- **C4 is now CLOSED** as a descriptive/predictive move-quality result (15.1B descriptive →
  11.3B player-clustered → 15.1D controlled → 15.1F robustness → 15.1G consolidation). It is
  not an open future "mediation" phase.
- **Prior trajectory is deferred**, not controlled. It is a stated limitation and the main
  recommended optional follow-up (a future trajectory-extraction audit/impl); it is required
  only before any *causal / mediation* clock claim, per the PREREGISTRATION deviation note.
- **Sharpness (Phase 14 / C3) has NOT been shown.** No MultiPV features exist yet. The
  sharpness arc must begin with a **feasibility / compute audit**, not implementation, and may
  not claim moderation until features exist and pre-registered tests run.

**Phase 12 / 13 status (score-scale / rich-clock / cheap-difficulty):**
- Kept as **useful but non-blocking** backlog — they no longer gate C4 (C4 is closed).
- Some score-scale work already happened **inside** Phase 15: C4 used expected-score loss and
  controlled adjusted-mean move-quality modeling with rating/eval/clock/termination controls.
- **Rich trajectory/history features (the Phase 12 E4c-style layer) remain the optional
  follow-up** most relevant to the deferred prior-trajectory caveat.
- Recommendation: do **not** force Phase 12/13 before 14.1A; revisit them as targeted
  robustness/extension tickets if a specific question (e.g. trajectory) demands them.

**Updated sharpness sequence (reframed):**
1. **14.1A — MultiPV Sharpness Feasibility / Compute Audit** (next).
2. 14.1B — Pilot Sharpness Extraction.
3. 14.2A — Sharpness Interaction Pre-Registration (new pre-registration required before any
   sharpness modeling).
4. 14.2B — Implement Sharpness Interaction Tests.
5. 14.3B — Sharpness Slice Report.

Reframing for the sharpness arc: sharpness is **no longer "rescuing" the original
board-decided outcome residual** (that collapsed). It should test whether constraint effects
are **moderated by objective narrowness / non-obviousness**, with the **first target being
move-quality moderation** (C3c, building on the settled C4 baseline) rather than only final
outcomes. Any outcome-level sharpness interaction must keep the **flagging-risk channel
distinct from board-decided results** (C3a vs C3b). No sharpness claim until MultiPV features
exist and pre-registered tests run.

## Phase 0: Governance and setup

Goal: establish project rules, structure, and safety before data work.

### Ticket 0.1A — Project Initialization + Lichess Source Format Audit

Audit scope:

```text
Governance consistency audit
Repo structure audit
Environment assumptions audit
Lichess source format assumptions audit
Data safety audit
```

Required report:

```text
Files inspected
Governance consistency findings
Repo structure findings
Environment / dependency findings
Lichess source format findings
Data safety findings
Recommended changes for 0.1B
Risks / assumptions
Whether 0.1B is safe to begin
```

Status: complete. See `reports/phase_reports/phase_0_1b_project_initialization_implementation.md`.

### Ticket 0.1B — Project Initialization + Lichess Source Documentation Implementation

Implementation scope:

```text
Rename reports/notes/ to reports/phase_reports/
Strengthen .gitignore (add *.sqlite, *.db, *.joblib, *.pkl, *.pt, *.pth, *.onnx)
Unify audit report format between CLAUDE.md and WORKFLOW.md
Add explicit report-location and no-standalone-report-tickets rules
Repurpose MANIFEST.md as a stable project manifest
Update ROADMAP.md Ticket 0.1 descriptions
Add Lichess parser-format assumptions to PIPELINE_OVERVIEW.md
```

Required report: `reports/phase_reports/phase_0_1b_project_initialization_implementation.md`

Status: complete.

### Ticket 0.2A — Environment Audit

Audit scope:

```text
Python executable and version
Virtual environment status
All required package availability in .venv vs. ambient shell
System tool availability: Stockfish, zstd CLI, brew
Repo dependency-file status (requirements.txt, pyproject.toml, Makefile, .python-version)
Recommendation for 0.2B
Risk assessment
```

Status: complete.

### Ticket 0.2B — Environment Documentation Implementation

Implementation scope:

```text
Create requirements.txt (curated direct dependencies, >= version pins)
Create .python-version (3.13.11)
Add Setup section to README.md (venv creation, activation, install, verification)
Update ROADMAP.md Ticket 0.2 descriptions
Update MANIFEST.md to include requirements.txt and .python-version
```

Required report: `reports/phase_reports/phase_0_2b_environment_documentation_implementation.md`

Status: complete.

## Phase 1: Lichess source and 10+0 availability

Goal: understand source data before building a full parser.

### Ticket 1.1A — Lichess Source Availability Audit

Questions:

```text
Which monthly source file should be used first?
How large is it?
Can it be streamed without full decompression?
How often does TimeControl "600+0" appear in a capped scan?
How often do qualifying games have clocks?
How often do qualifying games have eval annotations?
What fields appear consistently?
```

Initial scan cap:

```text
10,000-25,000 games
```

Required report:

```text
source file inspected
scan cap
10+0 count/estimate
eval availability estimate
clock availability estimate
field observations
recommendation for parser scope
```

Status: complete. See `reports/phase_reports/phase_1_1a_lichess_source_availability_audit.md`.

### Ticket 1.1B — Source Scanner Implementation

Implement a capped source scanner that can stream PGN data and summarize header/annotation availability.

Expected files:

```text
src/chess_mhsuc/source_scan.py
tests/conftest.py
tests/test_source_scan.py
reports/phase_reports/phase_1_1b_source_scanner_implementation.md
```

Out of scope:

```text
full model-ready dataset generation
large downloads without explicit permission
```

Status: complete. See `reports/phase_reports/phase_1_1b_source_scanner_implementation.md`.

Key findings from 50k-game scan of 2024-09 archive:

```text
600+0 rate:     9.85% of games
clock rate:     99.65% of 600+0 games have %clk
eval rate:      15.2% of basic_pass games have %eval  ← critical constraint
result dist:    1-0 48.9% / 0-1 46.6% / draw 4.5%
time forfeit:   11.3% of basic_pass terminations
elo range:      ~450–2680, mean ~1532
```

## Phase 2: PGN parsing and schema

Goal: extract reliable game-level and selected position-level records.

### Ticket 2.1A — PGN Schema Audit

Status: complete. Audit conducted via sampled real game inspection and
source-scan findings from Ticket 1.1B.

Key decisions recorded:
- Eval policy: Option C (nullable). eval_cp/eval_mate are None when absent.
  has_eval boolean on every ply row.
- Checkpoint definition: after Black's Nth full move = ply 2N (1-indexed).
  Checkpoints: move_10 (ply 20), move_20 (ply 40), move_30 (ply 60),
  move_40 (ply 80), last (final ply of game).
- Mate eval sign: White POV, requires side_to_move_next context.
  +N = White has mate in N. -N = Black has mate in N.
- Low-time flags deferred to feature engineering (Phase 3).
- Rejection priority: wrong_time_control → variant_or_nonstandard →
  missing_or_invalid_elo → missing_or_invalid_result → missing_clock.

### Ticket 2.1B — PGN Parser Implementation

Status: complete. See `reports/phase_reports/phase_2_1b_pgn_schema_parser_implementation.md`.

Implemented:

```text
src/chess_mhsuc/schemas.py       GameRecord, PlyRecord, PositionRecord + constants
src/chess_mhsuc/parse_pgn.py     full single-game parser
tests/fixtures/tiny_clock_eval_game.pgn  82-ply synthetic legal fixture
tests/test_parse_pgn.py          110 tests, all passing
```

Test results: 129 total (19 source_scan + 110 parse_pgn), all passed.
Python 3.13.11, pytest-9.0.3.

### Ticket 2.2A — Parser Validation Audit

Status: complete (chat audit only — no files produced).

Audit produced the streaming architecture and safety design used in 2.2B:
- urllib.request + zstandard streaming (no full decompression to disk)
- TC pre-filter before ply extraction (~90% of raw games skipped cheaply)
- Per-game exception handling with error_log
- Explicit Parquet schemas to prevent Null-type inference
- 11 post-run validation checks (username cols, game_id uniqueness, eval sentinel, etc.)
- max-games required (no unbounded default); max-accepted optional secondary cap

### Ticket 2.2B — Parser Validation + Capped Real-Data Loading Implementation

Status: complete. See `reports/phase_reports/phase_2_2b_parser_validation_implementation.md`.

Implemented:

```text
src/chess_mhsuc/run_parser.py     streaming CLI parser (zstd URL → Parquet + JSON)
tests/test_run_parser.py          34 tests, all passing
```

Test results: 163 total (19 source_scan + 110 parse_pgn + 34 run_parser), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data validation run executed (25k raw games, 2024-09 archive). All 11 validation
checks passed after one targeted fix: `n_plies_positive` scoped to accepted_basic rows
only (rejected abandoned games legitimately have n_plies=0). No parser logic changed.

No broad feature expansion included.

## Phase 3: Cleaning, labeling, and features

Goal: produce a clean model-ready checkpoint dataset.

### Ticket 3.1A — Cleaning and Labeling Audit

Status: complete (chat audit only — no files produced).

Audit inspected the 2024-09 25k interim dataset (2,467 game records, 8,528
position rows). Key decisions recorded:

- Game-level filters: `accepted_basic == True AND termination != "Abandoned"`
- Time forfeit games (11.5%) RETAINED — central to research question
- Missing eval RETAINED — eval_cp nullable by design
- No new label columns in v1 — result_class already present from parser
- No feature engineering in cleaning step
- Clock anomalies (7 rows with clock_s > 600) retained for now
- "Last" checkpoint duplication (83 games) retained — caller's responsibility

### Ticket 3.1B — Cleaning and Labeling Implementation

Status: complete. See `reports/phase_reports/phase_3_1b_cleaning_rules_implementation.md`.

Implemented:

```text
src/chess_mhsuc/cleaning.py     pure cleaning functions + CLI
tests/test_cleaning.py          30 tests, all passing
```

Test results: 193 total (19 source_scan + 110 parse_pgn + 34 run_parser + 30 cleaning), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run executed on 2024-09 25k interim dataset. All 8 validation checks passed.

```text
Raw game rows:        2,467
Clean game rows:      2,460   (5 rejected + 2 accepted-abandoned excluded)
Retained time forfeit:  283   (11.5%)
Broad position rows:  8,528
Eval position rows:   1,168   (13.7% eval coverage)
```

### Ticket 3.2A — Feature Engineering Audit

Status: complete (chat audit only — no files produced).

Audit defined v1 feature policy:
- Leakage: result_class, termination, n_plies_total, white/black_rating_diff forbidden as model inputs
- Rating features: white_elo, black_elo, elo_diff, avg_elo
- Clock features: raw + capped (÷600 fracs) + low-time flags (60/30/10s) + clock_anomaly
- Eval features: eval_cp_clipped (±1000 clip), is_mate_eval, eval_mate_abs, eval_white_winning
- Position features: move_number, phase, selected_position_type, checkpoint_index, phase_index
- Caution columns: is_last_checkpoint, side_to_move_next, white_to_move_next, duplicate_ply_checkpoint
- Slice columns: is_time_forfeit, termination, has_eval, game_id
- Labels: result_class, white_result_numeric

### Ticket 3.2B — Feature Engineering Implementation

Status: complete. See `reports/phase_reports/phase_3_2b_feature_engineering_implementation.md`.

Implemented:

```text
src/chess_mhsuc/features.py     pure feature functions + CLI (40-column output)
tests/test_features.py          84 tests, all passing
```

Test results: 277 total (19 source_scan + 110 parse_pgn + 34 run_parser + 30 cleaning + 84 features), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run on 2024-09 25k cleaned dataset. All 19 validation checks passed.

```text
Broad input rows:   8,528  →  broad output rows: 8,528  (no rows dropped)
Eval input rows:    1,168  →  eval output rows:  1,168  (no rows dropped)
Columns:            19 input → 40 output (23 added, 2 dropped: ply, n_plies_total)
Clock anomalies:        7 rows flagged by clock_anomaly=True
Duplicate ply:        166 rows flagged by duplicate_ply_checkpoint=True (83 games × 2 rows)
Eval coverage:       13.7% of broad positions
```

## Phase 4: Data assessment

Goal: verify dataset quality before modeling.

### Ticket 4.1A — Dataset Assessment Audit

Status: complete (chat audit only — no files produced).

Audit inspected the 2024-09 25k feature tables (8,528 broad rows, 1,168 eval rows).
Key findings recorded: target distribution confirmed (WW 46.7%, BW 47.4%, DRAW 5.8%),
eval coverage 13.7%, low-time flags show strong result asymmetry, leakage safety confirmed,
eval subset has mild avg_elo selection bias (+20 Elo vs broad).

### Ticket 4.1B — Dataset Assessment Implementation

Status: complete. See `reports/phase_reports/phase_4_1b_feature_dataset_assessment.md`.

Implemented:

```text
src/chess_mhsuc/assess_dataset.py     13 pure functions + CLI (assessment + Markdown + JSON)
tests/test_assess_dataset.py          45 tests, all passing
```

Test results: 322 total (277 prior + 45 assess_dataset), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data run on 2024-09 25k feature tables. All 8 baseline readiness checks passed.

```text
Broad rows:      8,528  |  Unique games: 2,323
Eval rows:       1,168  |  Unique games:   365
Result dist:     WHITE_WIN 46.73%  /  BLACK_WIN 47.44%  /  DRAW 5.83%
Eval coverage:  13.7%
avg_elo bias:   +20 Elo in eval vs broad
Leakage:        SAFE (both tables)
```

### Ticket 4.2A — Dataset Version Metadata Audit

Status: complete (chat audit only — no files produced).

Audit inspected all four per-stage metadata JSON files (parser, cleaning, features, assessment).
Key decisions recorded: canonical dataset_id = `lichess_ten_zero_2024_09_25k_v1`;
parser version_tag drift documented (metadata records "v1", canonical is "2024_09_25k_v1");
assessment test_count placeholder documented; manifest schema defined (17 functions A–Q).

### Ticket 4.2B — Dataset Version Metadata Implementation

Status: complete. See `reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md`.

Implemented:

```text
src/chess_mhsuc/dataset_version.py     17 pure functions + CLI (JSON manifest + dataset card + report)
tests/test_dataset_version.py          87 tests, all passing
```

Test results: 409 total (322 prior + 87 dataset_version), all passed.
Python 3.13.11, pytest-9.0.3.

Real-data CLI run on 2024-09 25k pipeline artifacts. All 11 artifacts found.

```text
dataset_id:     lichess_ten_zero_2024_09_25k_v1
broad_rows:     8,528  |  eval_rows: 1,168
artifacts:      11/11 found, all SHA256-hashed
leakage_safe:   True  |  baseline_readiness: True
git commit:     70b5f7367d19 (pipeline code state)
```

Output artifacts (committed):
- `reports/phase_reports/dataset_card_lichess_ten_zero_2024_09_25k_v1.md`
- `reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md`

Output artifacts (local-only, gitignored):
- `data/processed/dataset_version_lichess_ten_zero_2024_09_25k_v1.json`

## Phase 5: Baseline modeling

Goal: establish honest baseline performance before GBM.

### Ticket 5.1A — Modeling Split and Baseline Audit

Define:

```text
train/validation/test split by game_id
label format
baseline models
metrics
calibration expectations
```

Mandatory warning:

```text
No row-level split across positions from the same game.
```

Status: **complete** (chat audit, 2026-06-07).

Split policy defined: 70/15/15, game_id-level, stratified on result_class, seed 42.
Primary training view: primary_numbered (exclude selected_position_type == "last").
Feature sets FS-A through FS-G defined. Baselines B0–B5 planned (DummyClassifier ×2,
LogisticRegression ×4). Primary metrics: log_loss + macro_F1 + per-class P/R/F1.
Eval table inherits broad split assignments via game_id join; no separate eval split.

### Ticket 5.1B — Modeling Split + Baseline Plan Implementation

Create `splits.py` with game_id-level split assignments and modeling plan JSON.

```text
split unit: game_id (never row-level)
ratio: 70/15/15, seed 42, stratified by result_class
broad split: train=1,626 / val=348 / test=349 games (2,323 total)
eval split: train=256 / val=56 / test=53 games (365 total, inherits broad)
primary view rows: train=4,344 / val=931 / test=930 (numbered checkpoints only)
DRAW broad: train=77 / val=16 / test=17 games
baselines planned: B0 (DummyClassifier most_frequent), B1 (prior),
  B2 (LR rating-only), B3 (LR rating+clock+position),
  B4 (LR eval-only, exploratory), B5 (LR full, exploratory)
label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed)
```

Status: **complete** (2026-06-07). 92 new tests. 501 total passing.

Files created:
- `src/chess_mhsuc/splits.py` — 16 functions + CLI
- `tests/test_splits.py` — 92 tests
- `reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md`

Local-only (gitignored):
- `data/processed/splits_2024_09_25k_v1.json`
- `data/processed/modeling_plan_2024_09_25k_v1.json`

### Ticket 5.2A — Baseline Model Audit

Define exact preprocessing, label encoding, class imbalance policy, metrics,
and baseline training plan before implementation.

Status: **complete** (2026-06-07). Chat-only audit.

Key decisions: strip `multi_class` from LR params (sklearn 1.8 breaking change);
`SimpleImputer(fill_value=0)` for `eval_mate_abs` (93.6% null); B3-balanced added
as diagnostic; `zero_division=0` for per-class metrics.

### Ticket 5.2B — Baseline Model Implementation

Train B0–B5 + B3-balanced baselines on primary_numbered view. No GBM, no calibration.

```text
B0: DummyClassifier most_frequent | broad | val acc=0.4758 | val log_loss=18.89
B1: DummyClassifier prior         | broad | val acc=0.4758 | val log_loss=0.8853
B2: LR rating-only (FS-B)         | broad | val acc=0.5124 | val log_loss=0.8740
B3: LR rating+clock (FS-E)        | broad | val acc=0.5381 | val log_loss=0.8527
B3-balanced: LR FS-E balanced     | broad | val acc=0.4393 | val log_loss=1.0623
B4: LR eval-only (FS-F)           | eval  | val acc=0.5918 | val log_loss=0.7833 (exploratory)
B5: LR full (FS-G)                | eval  | val acc=0.6190 | val log_loss=0.8598 (exploratory)
```

Status: **complete** (2026-06-07). 90 new tests. 591 total passing.

Files created:
- `src/chess_mhsuc/baselines.py` — 17 functions (A–Q) + CLI
- `tests/test_baselines.py` — 90 tests
- `reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md`

Local-only (gitignored):
- `data/processed/baseline_results_2024_09_25k_v1.json`
- `data/processed/baseline_predictions_2024_09_25k_v1.parquet`

### Ticket 5.3A — Baseline Evaluation Audit

Audit the baseline results JSON and reporting structure before writing the
evaluation report. No files created.

Status: **complete** (2026-06-08). Audit-only. No files changed.

Findings:
- `payload["baselines"]` is a dict keyed by baseline_id (not a list).
- B0 (most_frequent DummyClassifier) excluded from primary comparison table.
- Signal decomposition: B1 prior (0.8853) → B2 (0.8740, Δ−0.011) → B3 (0.8527, Δ−0.021).
- All broad unweighted LR models predict 0 DRAW rows.
- Eval test acc spike (B4=0.7071) is small-sample artifact.
- `feature_columns_dropped` key NOT present in baseline results (GBM-only hotfix).

### Ticket 5.3B — Baseline Evaluation Report Implementation

Create `baseline_evaluation.py` (17 functions A–Q) and associated tests +
Markdown report. Render evaluation report from the baseline results JSON.

Status: **complete** (2026-06-08). 106 new tests. 826 total passing.

Files created:
- `src/chess_mhsuc/baseline_evaluation.py` — 17 functions (A–Q) + CLI
- `tests/test_baseline_evaluation.py` — 106 tests
- `reports/baseline_evaluation_2024_09_25k_v1.md` (committed)
- `reports/phase_reports/phase_5_3b_baseline_evaluation_implementation.md`
- `EXPERIMENT_LOG.md` — EXP-001 added

Key report findings:
- Best broad primary baseline: B3 (FS-E) val log_loss=0.8527
- Full B1→B3 signal: Δ−0.0326 log_loss units
- No broad baseline below 0.85 — this is the Phase 6 floor

## Phase 6: GBM modeling

Goal: train the first serious nonlinear tabular model.

### Ticket 6.1A — GBM Model Choice Audit

Compare:

```text
sklearn HistGradientBoostingClassifier
XGBoost
LightGBM
```

Recommendation expected:

```text
Which model to use first and why.
```

Current default:

```text
Start with scikit-learn HistGradientBoostingClassifier for lowest dependency friction.
Move to XGBoost if performance/control needs justify it.
```

Status: complete. HistGradientBoostingClassifier selected. No new dependencies.

### Ticket 6.1B — First GBM Implementation

Train first GBM model on the verified dataset.

Required:

```text
same split as baselines
same metrics
ablation comparison
feature importance or permutation importance if feasible
```

Status: complete. G1–G6 trained (HistGBM). Best broad: G2 val log_loss=1.2326. Best eval (expl): G5 val log_loss=1.1854.

Local artifacts (gitignored):

```text
data/processed/gbm_results_2024_09_25k_v1.json
data/processed/gbm_predictions_2024_09_25k_v1.parquet
```

### Ticket 6.2A — GBM Evaluation Slice Audit

Audit GBM and baseline artifacts to determine which slice diagnostics are
feasible on the existing dataset. Determine what can be computed from the
existing predictions Parquet without retraining.

Status: complete. Five feasible slices identified: phase, move_number,
is_time_forfeit, has_eval, avg_elo bucket (via feature join). G2 confirmed
as primary broad GBM. G4 identified as near-prior/degenerate. G6 identified
as complete memorisation. Audit report in chat only (no files created).

### Ticket 6.2B — GBM Evaluation Implementation

Implement `gbm_evaluation.py` (18 functions A–R + CLI): load GBM/baseline
results, compute slice accuracy, confidence bucket diagnostic, avg_elo join,
and render a durable Markdown evaluation report.

Status: complete. See `reports/gbm_evaluation_2024_09_25k_v1.md` and
`reports/phase_reports/phase_6_2b_gbm_evaluation_implementation.md`.

Key results:
- G2 val log_loss=1.2326 — does NOT beat B3 (0.8527)
- G1/G2 train/val gap >+1.0 — severe overfit
- G4 near-prior (max_prob mean≈0.476) — diagnostic only, not a winner
- G6 train_ll≈0.004 — complete memorisation of 645 eval training rows
- All broad GBMs predict 0 DRAW on validation

Local artifacts (gitignored): none new (reuses 6.1B artifacts).

### Ticket 6.3A — Feature Importance Audit

Audit-only. Inspect HistGBM for native `feature_importances_` availability,
permutation importance feasibility, model artifact availability, feature columns
for G1–G6, scoring metric choice, and report language constraints.

Status: complete. Audit report in chat only (no files created).

Key findings:
- HistGradientBoostingClassifier in sklearn 1.9.0 does NOT expose `feature_importances_`
- `sklearn.inspection.permutation_importance` available; no new dependency needed
- G2 retrainable deterministically from local data artifacts (~4 seconds)
- Only white_elo (+0.029) and avg_elo (+0.029) show positive importance
- 15 of 20 features show negative importance — overfit artifacts, not uselessness
- clock_diff_s is most negative (≈−0.048): G2 overfit clock patterns

### Ticket 6.3B — Feature Importance Implementation

Implement `gbm_feature_importance.py` (16 functions A–P + CLI): retrain G2 in
memory, compute validation-set permutation importance, and render a caveated
12-section Markdown diagnostic report. No model artifacts saved, no calibration,
no SHAP, no new dependencies.

Status: complete. See `reports/gbm_feature_importance_2024_09_25k_v1.md` and
`reports/phase_reports/phase_6_3b_feature_importance_implementation.md`.

Key results:
- G2 retrained val log_loss: 1.2369 (consistent with Phase 6.1B)
- Positive signal: white_elo (+0.0169), avg_elo (+0.0410)
- Near-zero / negative: all clock and position features
- clock_diff_s most negative (−0.0481): largest overfit artifact
- Report explicitly frames all results as overfit diagnostics, not final rankings

Local artifacts (gitignored): none (G2 retrained in memory only).

## Phase 7 — Calibration

### Ticket 7.1A — Calibration Audit
ML | D2 | CAUTIOUS

Status: complete (audit-only; no files created). Key findings:
- B3 ECE OvR: BLACK_WIN=0.026, DRAW=0.001, WHITE_WIN=0.033 — reasonably calibrated
- G2 ECE OvR: BLACK_WIN=0.234, DRAW=0.061, WHITE_WIN=0.203 — severely overconfident
- G2 [0.9,1.0] confidence bucket: mean_conf=0.949, acc=0.594, gap=+0.355
- DRAW sparsity (~59/931 val rows, 6.3%): DRAW ECE not informative
- G4 excluded (near-prior); G5/G6 excluded (eval-gated/memorization)

### Ticket 7.1B — Calibration Implementation
ML | D2 | IMPLEMENTATION
Requires post-implementation report.

Status: complete. See `reports/calibration_2024_09_25k_v1.md` and
`reports/phase_reports/phase_7_1b_calibration_implementation.md`.

Key results (val split, 931 rows):
- B1 ECE OvR: BLACK_WIN=0.002, DRAW=0.001, WHITE_WIN=0.004 (prior — degenerate)
- B3 ECE OvR: BLACK_WIN=0.026, DRAW=0.001, WHITE_WIN=0.033 — best calibrated
- G2 ECE OvR: BLACK_WIN=0.234, DRAW=0.061, WHITE_WIN=0.203 — severely overconfident
- B3 classwise Brier: BLACK_WIN=0.239, DRAW=0.059, WHITE_WIN=0.236
- G2 classwise Brier: BLACK_WIN=0.313, DRAW=0.068, WHITE_WIN=0.301
- No post-hoc calibrators fitted. Diagnostics only.

Local artifacts (gitignored): none.

### Ticket 7.2A — Probability Interpretation Audit
REPORTING/ML | D1 | CAUTIOUS

Status: complete (audit-only; no files created). Key findings:
- B3 is the only currently usable model for cautious descriptive probability claims
- G2 is overfit (gap=+1.069) and overconfident (ECE≈0.20–0.23); probabilities not usable
- B1's low ECE is a prior-only trap; predicts constant class frequencies
- DRAW probability unreliable for all models (6.3% sparsity, 59/931 val rows)
- Guardrail categories defined: Allowed, Cautious, Forbidden claims
- No constraint-effect claims established; requires Phase 8 + Phase 9

### Ticket 7.2B — Probability Interpretation Report Implementation
REPORTING/ML | D1 | IMPLEMENTATION
Requires post-implementation report.

Status: complete. See `reports/probability_interpretation_2024_09_25k_v1.md` and
`reports/phase_reports/phase_7_2b_probability_interpretation_implementation.md`.

Key outputs:
- probability_interpretation.py (12 functions A–L + CLI)
- 73 tests in test_probability_interpretation.py; 1123 total tests passing
- 14-section guardrails report generated from real artifacts
- Allowed/Cautious/Forbidden claims matrix codified
- Explicit prohibition on G2 probability interpretation, DRAW claims, causal claims

Local artifacts (gitignored): none.

## Phase 7.3: Pre-Phase-8 Hardening

### Ticket 7.3A — Modeling Hygiene Hardening Audit

ML/INFRA | D2 | CAUTIOUS

Status: complete.

Summary: Audited pre-Phase-8 modeling hygiene issues: missing clustered uncertainty
estimates, unfair unstopped GBM comparison (sklearn `early_stopping='auto'` does not
activate below 10,000 samples), undocumented short-game exclusion (137 games with n_plies
< 20), test-holdout exposure, leakage hardening gaps, roadmap/log drift (Phase 8 called
"Scaling" in EXP-002–005; EXP-001 filter statement incorrect), and v1-specific hardcoded
report constants.

### Ticket 7.3B — Modeling Hygiene Hardening Implementation

ML/INFRA | D2 | IMPLEMENTATION

Status: complete. See `reports/phase_reports/phase_7_3b_modeling_hygiene_hardening.md`.

Summary: Implemented game-level cluster bootstrap CIs (1,000 replicates, val only),
fair early-stopped G2b diagnostic GBM (early_stopping=True, validation_fraction=0.15),
short-game population documentation and accounting test, holdout/test-split policy
(WORKFLOW.md §14), permuted-label anti-leakage test, prediction/split and primary-view
consistency checks, roadmap/experiment-log corrections, and v1-constant warning comments.

Key findings:
- G2b val log_loss and comparison to G2 and B3: see EXP-006 and bootstrap report.
- Bootstrap CIs confirm whether B2→B3 delta (Δ−0.021 log_loss) is statistically resolvable.
- Short-game exclusion documented: 137 games (n_plies 1–19), not a parser bug, population
  definition is games reaching ply ≥ 20 / move 10.

## Roadmap Reconciliation Note (2026-06-11, Ticket 9.4B)

Fixed-depth Stockfish validation was pulled forward into Phase 8 because
eval-conditioned modeling required engine control. Scaling/replication work
became Phase 9. Older notes that refer to "Phase 8 Scaling" or place
Stockfish validation later (e.g., interpretation prose in early
EXPERIMENT_LOG entries) reflect pre-reorganization numbering. The current
ROADMAP numbering below is authoritative. All existing report links remain
valid.

## Phase 8: Fixed-depth Stockfish validation

Goal: check whether conclusions depend on existing Lichess eval selection bias.

### Ticket 8.1A — Stockfish Validation Audit

Status: complete. See `reports/phase_reports/phase_8_1b_fixed_depth_stockfish_evaluation_implementation.md`
(audit findings reported inline in chat on 2026-06-10; no separate 8.1A phase report file).

Findings: Stockfish 18 at /opt/homebrew/bin/stockfish; python-chess 1.11.2 available; FEN
reconstruction via PGN re-parse confirmed feasible; 6,205 primary_numbered positions; depth=12
recommended (~4min runtime); no new dependencies needed.

### Ticket 8.1B — Stockfish Evaluation Implementation

Status: complete. `stockfish_eval.py` + 76 tests. Full 6,205-position eval completed
(ok=6205, fail=0, runtime=329s). Lichess eval sign agreement: 95.1% on 932-position overlap.
Artifact: `data/processed/sf_eval_broad_2024_09_25k_v1.parquet` (gitignored).
EXP-007 added. Bug fixed: `pl.from_dicts(rows, schema=_RESULT_SCHEMA)` replaces
`pl.DataFrame(rows)` to prevent Null-type inference on nullable int columns.

See `reports/phase_reports/phase_8_1b_fixed_depth_stockfish_evaluation_implementation.md`.

### Ticket 8.2A — Existing-vs-Fixed Eval Comparison Audit

Define comparison approach.

Status: complete (audit delivered inline in chat on 2026-06-10). Verified the 8.1B
artifact (found the sf_depth=0 terminal-row erratum), selected the
(game_id, selected_position_type) join key, designed feature sets FS-H–K and
models E1/E3/E4/E5, and recommended a logistic-only implementation reusing
bootstrap_ci.py public functions.

### Ticket 8.2B — Existing-vs-Fixed Eval Comparison Implementation

Report whether model conclusions hold under fixed-depth evals.
(Implementation includes eval-conditioned ablation per the 8.2A audit.)

Status: complete. `eval_conditioned_modeling.py` + 77 tests (1,378 total passing).
E1/E3/E4/E5 logistic models trained on the broad primary view with the 8.1B
sf_eval artifact. All E-models beat all baselines on val log_loss; best E5=0.7310
vs B3=0.8527 (paired delta −0.1217, CI excludes zero). Key comparison E3→E4
(clock after eval + rating): delta −0.0138, CI [−0.0266, −0.0002] excludes zero
(barely — re-examine at Phase 9 scale). EXP-008 added. 8.1B sf_depth erratum
applied to both 8.1B reports.

See `reports/phase_reports/phase_8_2b_existing_vs_fixed_eval_comparison_implementation.md`.

## Phase 9: Scale-up

Goal: scale only after the pilot pipeline is reliable.

### Ticket 9.1A — Scale-Up Audit

Answer:

```text
What bottlenecks exist?
Do we need more data?
Do we need an external drive?
Do we need cloud compute?
What exact research question requires scale?
```

Status: complete (audit delivered inline in chat on 2026-06-10). Answers: no
external drive or cloud compute needed (250k scale fits local hardware in an
afternoon; all artifacts tens of MB plus a 583 MB raw cache); the research
question requiring scale is whether the fragile 8.2B E3→E4 clock result
survives 10×. Recommended S2=250k same-month superset prefix, logistic-only,
tee-cached raw prefix, parameterization of eval_conditioned_modeling.py.

### Ticket 9.1B — Scale-Up Implementation

Scale to larger samples only with explicit caps and verification.

Status: complete. 250k raw games (deterministic first-N prefix, superset of
pilot) → 25,887 clean → 65,368 primary positions; Stockfish 18 depth=12 full
coverage (65,368/65,368, 288 terminal depth-0 rows); B1/B2/B3 + E1/E3/E4/E5
rerun. **8.2B finding CONFIRMED: E3→E4 delta −0.0138 [−0.0186, −0.0091],
same point estimate as pilot, CI now comfortably excludes zero.** E1→E3 and
E4→E5 also resolved at scale. Per-checkpoint deltas: clock signal
concentrates in move_30/40. EXP-009 added. 1,404 tests passing.

See `reports/phase_reports/phase_9_1b_scale_up_implementation.md` and
`reports/scale_up_2024_09_250k_v1.md`.

### Ticket 9.2A — Constraint Slice / Interaction Audit

Status: complete (audit delivered inline in chat on 2026-06-10). Designed the
slice analysis for localizing the replicated E3→E4 clock signal: primary
slices = eval decidedness, avg_elo bucket, and min-clock bucket WITHIN late
checkpoints (marginal clock buckets rejected — confounded with checkpoint:
99.9% of move_10 rows have >180s remaining). Bootstrap rule: game-level CIs
only for cells ≥300 games; smaller cells reported descriptively. Use existing
9.1B predictions; no retraining.

### Ticket 9.2B — Constraint Slice / Interaction Implementation

Status: complete. `constraint_slices.py` + 74 tests. No models trained.
Key result (P3, within move_30+40): E3→E4 delta by remaining time —
under_60s −0.2541 (228 games, below CI threshold, descriptive),
60_180s −0.0534 [−0.0717, −0.0335] excludes zero,
over_180s −0.0074 [−0.0136, −0.0014]. The clock signal localizes to actual
time scarcity, not just game length — consistent with time-pressure
relevance (predictive association, not causal). P1: signal present across
equal/slight/decided positions (all exclude zero; not merely a
won-position-conversion story). P2: stable across rating bands. Terminal
sensitivity: identical with/without 44 terminal rows. EXP-010 added.

See `reports/phase_reports/phase_9_2b_constraint_slice_implementation.md`
and `reports/constraint_slices_2024_09_250k_v1.md`.

### Ticket 9.3A — Independent Replication / External Validity Audit

Status: complete (audit delivered inline in chat on 2026-06-11). Evaluated
four replication designs; selected Design B (cross-month 250k on 2024-10) —
it tests the actual remaining threat (time-period specificity) and required
zero parser changes, vs. same-month disjoint sampling which needs
skip-offset work and controls less. Identified two small parameterization
fixes (constraint_slices prose, ecm reference comparison).

### Ticket 9.3B — Cross-Month Replication Implementation

Status: complete. Full pipeline rerun on 2024-10 first-250k (fully disjoint
from all 2024-09 data): 24,801 clean games, 62,839 primary positions,
SF 100% coverage (1,626s, 299 terminal rows). **Both replication targets
hit: overall E3→E4 = −0.0120 [−0.0177, −0.0062] excludes zero (2024-09:
−0.0138 [−0.0186, −0.0091]) — REPLICATED. P3 late-clock localization
REPLICATED** (under_60s −0.2468 descriptive; 60_180s −0.0442 excludes zero;
over_180s ≈ 0). The clock signal now stands on two independent months.
EXP-011 added. 1,485 tests passing.

See `reports/phase_reports/phase_9_3b_cross_month_replication_implementation.md`
and `reports/cross_month_replication_2024_10_250k_v1.md`.

## Phase 10: Neural sequence model exploration

Goal: explore sequence modeling only if justified.

### Ticket 10.1A — Sequence Model Feasibility Audit

Questions:

```text
Does GBM leave meaningful unexplained temporal structure?
Can local compute handle a small sequence model?
What data representation is needed?
What baseline must the sequence model beat?
```

### Ticket 10.1B — Minimal Sequence Model Implementation

Implement a small sequence baseline only after the audit.

Out of scope:

```text
large transformer training
cloud GPU spending
paper claims without comparison to GBM
```

## Phase 11: Outreach package

Goal: prepare for professor feedback if pilot results are credible.

### Ticket 11.1A — Outreach Readiness Audit

Check whether the project has:

```text
clean pilot dataset
clear pipeline docs
ablation table
calibration figure
subgroup result
known limitations
concise summary
```

### Ticket 11.1B — Outreach Package Implementation

Create:

```text
1-page research summary
figures
methods note
professor email draft
```

## Completed tickets

Phases 0–9 complete:

- Phase 0: Governance and setup (0.1A/B, 0.2A/B)
- Phase 1: Lichess source and 10+0 availability (1.1A/B)
- Phase 2: PGN parsing and schema (2.1A/B, 2.2A/B)
- Phase 3: Cleaning, labeling, and features (3.1A/B, 3.2A/B)
- Phase 4: Data assessment (4.1A/B, 4.2A/B)
- Phase 5: Baseline modeling (5.1A/B, 5.2A/B, 5.3A/B)
- Phase 6: GBM modeling (6.1A/B, 6.2A/B, 6.3A/B)
- Phase 7: Calibration and probability interpretation (7.1A/B, 7.2A/B, 7.3A/B)
- Phase 8: Fixed-depth Stockfish eval (8.1A/B); eval-conditioned modeling (8.2A/B)
- Phase 9: 250k scale-up (9.1A/B); constraint slices (9.2A/B); cross-month replication (9.3A/B); roadmap reconciliation (9.4A/B)

Update this section after each stable commit.
