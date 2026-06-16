# Phase 15.2A — Roadmap Recovery / Dense Move-Quality Architecture Audit

**Labels:** RECOVERY / AUDIT | report-only, no code/model/data changes
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

The project was prematurely routed toward synthesis (16.0A → "16.0B Final Report Skeleton").
That conflicts with the accepted v11 roadmap, where **Phase 16 = cross-time-control
dose-response** and **Phase 17 = packaging** — synthesis/report drafting is Phase 17, not
Phase 16. This audit restores the architecture: **Phase 15 (Constraint Atlas / move-quality
curves) is not finished at the resolution the project actually wants.** All move-quality work
to date is **checkpoint-only** — the `next_move_loss` artifact has exactly four
`selected_position_type` values (`move_10/20/30/40`, ~2.67 rows/game), so there are **no dense
move-by-move degradation curves** yet. Phases 12–13 (score-scale/clock-dynamics, difficulty
layer) were deliberately deferred (15.1H) and remain unstarted. The recommendation: **do not
proceed to packaging**; reclassify 16.0A as an early/off-roadmap synthesis checkpoint; restore
Phase 15 as active and extend it to **dense move-by-move move-quality extraction + a richer
Constraint Atlas + a fuller sharpness panel**; then Phase 16 (cross-TC) and Phase 17
(packaging). The 15.2B patch applies this to the governance files; the next empirical ticket is
**15.3A — Dense Move-by-Move Loss Feasibility Audit.** No code, models, data, or docs were
changed in this ticket. All results remain predictive/descriptive, not causal.

## 2. Why this recovery audit exists

After C3c (sharpness × clock checkpoint move-quality moderation) came back
underpowered/no-claim and the outcome/flagging sharpness audit (14.3A) recommended not
extending, the project jumped to **16.0A — Synthesis Readiness**, which set the default next
step to "16.0B Final Report Skeleton." That treated a coherent *checkpoint-level* story as the
finish line. But the accepted v11 roadmap's Phase 15 endpoint is **move-quality curves** (a
Constraint Atlas of how quality varies with constraints), and the project's stated goal
includes **dense move-by-move degradation curves**, rating × time heatmaps, eval/phase-
conditioned quality curves, large-loss/blunder-probability curves, and a fuller sharpness
panel — none of which exist at dense resolution. Packaging before that empirical work is
premature. This audit recovers the path.

## 3. Files inspected

- Governance: `ROADMAP.md`, `docs/roadmap_rescope_v11_draft.md`, `PREREGISTRATION.md`,
  `EXPERIMENT_LOG.md`.
- Premature synthesis path: `reports/synthesis_readiness_audit.md`,
  `reports/phase_reports/phase_16_0a_synthesis_readiness_public_claim_audit.md`.
- Core result reports: `termination_decomposition_combined`, `next_move_loss_combined`,
  `constraint_atlas_combined`, `controlled_move_quality_combined`,
  `clock_association_robustness_combined`, `multipv_sharpness_combined`,
  `sharpness_interaction_combined` (all present).
- Key phase reports: 11.2B, 11.2C, 11.3B; 15.0A–15.1H; 14.1A–14.3A (all present).
- Source modules (capability inventory, read-only): `next_move_loss.py`, `constraint_atlas.py`,
  `controlled_move_quality.py`, `clock_association_robustness.py`, `multipv_sharpness.py`,
  `sharpness_interaction.py`, `player_metadata.py`, `clustered_uncertainty.py`.
- Artifacts (existence/ignore only): `next_move_loss_{09,10}`, `multipv_sharpness_{09,10}`,
  `player_metadata_{09,10}` — all present and gitignored.
- **Empirical confirmations (read-only):** `next_move_loss` has exactly 4 distinct
  `selected_position_type` (`move_10/20/30/40`), ~2.67 rows/game; it **lacks** `clock_after_s`,
  `think_time_s`, `result_class`, and a dense `ply` column (`result_class` lives in
  `feature_positions_broad`).

## 4. Accepted v11 roadmap baseline

From `docs/roadmap_rescope_v11_draft.md` (authoritative phase architecture):

```
Phase 11: positioning / claim hardening.
Phase 12: score-scale robustness + stronger clock controls.
Phase 13: cheap difficulty layer.
Phase 14: MultiPV sharpness.
Phase 15: Constraint Atlas / move-quality curves (+ sharpness×clock mediation, v11 §15.2).
Phase 16: cross-time-control dose-response.
Phase 17: packaging.
```

**The recent 16.0A synthesis-readiness ticket conflicts with this architecture because Phase 16
is cross-time-control dose-response, not synthesis or final report drafting.** (Note a numbering
tangle: in the v11 draft the sharpness × clock move-quality mediation is **§15.2A/B**, but it
was executed under Phase 14 numbering after the 15.1H reconciliation pulled sharpness forward.
15.2B should reconcile this explicitly.)

## 5. Completed work inventory

| Roadmap item | Planned purpose | Actual work completed | Status | Evidence/report | Required follow-up |
|---|---|---|---|---|---|
| 11.2 termination decomposition | Separate flagging vs board-decided in outcome clock signal | E3→E4 by channel, both months, clustered | complete | `termination_decomposition_combined`, `phase_11_2b/c` | none |
| 11.3 player metadata/clustering | Player-leakage hardening | Hashed IDs + clustered bootstrap; findings survive | complete | `phase_11_3b`, `player_clustered_*` | none |
| Phase 12 score-scale / rich clock controls (E3w/E4w, E4b/E4c) | ES/WDL-scale robustness + clock dynamics + history | not done (deliberately deferred 15.1H "non-blocking backlog") | deferred | ROADMAP 15.1H note | reconsider in 15.7 (trajectory) / Phase 12 revival |
| Phase 13 cheap difficulty layer (E6/E7) | Static board difficulty + obviousness flags | not done (deferred) | deferred | ROADMAP 15.1H note | optional; superseded in part by MultiPV sharpness |
| 14.1 MultiPV sharpness extraction | Engine-side value-fragility features | Pilot + full both months; validated, stable | complete | `multipv_sharpness_combined`, `phase_14_1a/b/c` | extend to continuous-feature panels (15.5) |
| 14.2 sharpness interaction modeling (v11 §15.2 mediation) | Sharpness × clock move-quality moderation | Locked model run; underpowered/no-claim | complete-but-narrower-than-roadmap | `sharpness_interaction_combined`, `phase_14_2a–d` | richer panel (15.5/15.6); optional enrichment 14.2E |
| 14.3 outcome/flagging sharpness audit | C3a/C3b feasibility | Audited; C3a not recommended, C3b deferred | complete (audit) | `phase_14_3a` | optional 14.3B |
| 15.0 next-move loss extraction | Move-quality measurement layer | Checkpoint-level (4 plies) extraction, both months | complete-but-narrower-than-roadmap | `next_move_loss_combined`, `phase_15_0a–c` | **dense extraction (15.3)** |
| 15.1 constraint atlas (descriptive curves) | Move-quality curves | Checkpoint-level atlas (eval/clock/rating/phase), clustered | complete-but-narrower-than-roadmap | `constraint_atlas_combined`, `phase_15_1a/b` | **dense atlas (15.4)** |
| 15.1 controlled checkpoint move-quality modeling | Controlled M-series | OLS adjusted-mean + robustness + clustering | complete-but-narrower-than-roadmap | `controlled_move_quality_combined`, `phase_15_1c–g` | dense controlled modeling (15.4) |
| 15.1 robustness | Stress-test clock association | 12-check matrix; survives | complete | `clock_association_robustness_combined`, `phase_15_1f` | dense re-run (15.4) |
| Dense move-by-move CP-loss / ES-loss atlas | True degradation curves over plies | not done | not-started | — | **15.3 + 15.4** |
| Sharpness-conditioned move-quality curves | Sharpness × quality panels | not done | not-started | — | 15.5 |
| Sharpness prediction-improvement modeling | Does sharpness add predictive value (M0→M3) | not done | not-started | — | 15.6 |
| Prior trajectory / cumulative-loss controls | "Clock as symptom of past struggle" control | not done (deferred C4 limitation) | deferred | `phase_15_1g` limitation | 15.7 |
| Phase 16 cross-time-control dose-response | Cross-TC clock/quality/sharpness | not done | not-started | — | Phase 16 (after 15) |
| Phase 17 packaging | Synthesis + report + outreach | 16.0A claim-architecture snapshot only | misnumbered (as "Phase 16") | `phase_16_0a`, `synthesis_readiness_audit` | reuse in Phase 17 |

## 6. Misnumbered / misrouted work

- **16.0A "Synthesis Readiness" + the implied "16.0B Final Report Skeleton" are misrouted.**
  Phase 16 is cross-time-control dose-response; synthesis/packaging is Phase 17. 16.0A set the
  default next ticket to report drafting, skipping the unfinished Phase 15 dense work and all of
  Phase 16.
- **Sharpness × clock mediation numbering tangle:** v11 §15.2 (mediation) was executed as Phase
  14.2 (after 15.1H pulled sharpness forward). Harmless to the science but should be noted in
  the patch so the restored Phase 15.2+ numbering does not collide.

## 7. Work completed but narrower than intended

The move-quality arc is **real and sound but checkpoint-resolution only**:
- Extraction (15.0) sampled **4 plies/game** (`move_10/20/30/40`), not dense plies.
- The Constraint Atlas (15.1B) and controlled modeling (15.1D/F) are **checkpoint** summaries —
  they do show eval-band/clock/rating/phase structure, but as 4-point snapshots, **not curves
  over move number / think time**.
- Sharpness modeling (14.2) tested a single **binary** feature at checkpoints; no continuous
  sharpness, no sharpness-conditioned quality curves, no prediction-improvement (M0→M3) test.
- Rating × time and eval-band panels exist **at checkpoints** (atlas §9–10) but not as dense
  heatmaps over the full game.

These are legitimate results to keep; they are simply not the dense degradation-curve endpoint.

## 8. Work skipped or still unfinished

- **Dense move-by-move (or stratified-ply) loss extraction** — not started (the core gap).
- **Raw/clipped CP-loss and ES-loss curves over plies** — not started.
- **Rating × time heatmaps; eval-band/phase-conditioned quality curves** at dense resolution —
  not started.
- **Large-loss / blunder-probability curves** (ES>0.05/0.10, CP>100/200 over plies) — not
  started.
- **Sharpness-conditioned move-quality curves + sharpness × {clock, rating, eval, phase}
  panels** — not started.
- **Sharpness prediction-improvement modeling (M0→M3)** — not started.
- **Prior trajectory / cumulative-loss / time-management controls** — deferred.
- **Phase 12 (score-scale + clock dynamics) and Phase 13 (difficulty layer)** — deferred,
  unstarted.
- **Phase 16 cross-time-control dose-response** — not started.
- **Phase 17 packaging** — only the 16.0A snapshot exists.

## 9. Correct interpretation of the mistaken 16.0A synthesis checkpoint

**The 16.0A synthesis-readiness audit should not be treated as Phase 16 work. It remains useful
as a claim-architecture snapshot, but it must be reclassified as either an early/off-roadmap
synthesis checkpoint or later Phase 17-adjacent material. It must not set the default next
ticket to final report drafting.** Do not delete, rename, or edit the 16.0A files in this
ticket — 15.2B applies the reclassification in the governance docs, and the claim hierarchy /
forbidden-claims content is reusable verbatim in Phase 17.

## 10. Restored roadmap architecture

```
Phase 11  ✓ complete (claim hardening, termination, player clustering)
Phase 12  deferred (score-scale + clock dynamics) — backlog, may revive in 15.7/Phase 12
Phase 13  deferred (difficulty layer) — backlog, partly superseded by MultiPV sharpness
Phase 14  ✓ MultiPV sharpness extraction complete; sharpness×clock checkpoint mediation
          complete-but-underpowered
Phase 15  ACTIVE, EXPANDED — Constraint Atlas / move-quality curves at DENSE resolution
          (checkpoint layer done; dense extraction + dense atlas + sharpness panel +
          prediction-improvement + trajectory controls remain)
Phase 16  cross-time-control dose-response (NOT synthesis)
Phase 17  packaging (synthesis readiness, report skeleton, tables/figures, draft, outreach)
```

## 11. Phase 15 continuation plan

Default path (unless 15.3A finds a hard compute blocker):

```
15.2B — Roadmap Recovery Patch
15.3A — Dense Move-by-Move Loss Feasibility Audit
15.3B — Dense Move-by-Move Loss Extraction Pilot
15.3C — Full Dense Move-by-Move Loss Extraction
15.4A — Centipawn / Expected-Score Constraint Atlas Audit
15.4B — Centipawn / Expected-Score Constraint Atlas Implementation
15.4C — Controlled Dense Move-Quality Modeling Audit
15.4D — Controlled Dense Move-Quality Modeling Implementation
15.5A — Sharpness-Enriched Constraint Atlas Audit
15.5B — Sharpness-Enriched Constraint Atlas Implementation
15.5C — Sharpness Interaction Panel Audit
15.5D — Sharpness Interaction Panel Implementation
15.6A — Sharpness Prediction-Improvement Audit
15.6B — Sharpness Prediction-Improvement Implementation
15.6C — Sharpness Prediction Robustness / Interpretation Audit
15.7A — Time-Trajectory / Prior-Quality Controls Feasibility Audit
15.7B — Trajectory Feature Extraction / Modeling Implementation
15.7C — Trajectory-Controlled Move-Quality Modeling
```

### Checkpoint-level vs dense move-by-move (explicit separation)

```
Checkpoint-level analysis:
  Existing work at move_10, move_20, move_30, move_40.
  Useful and already implemented (atlas + controlled modeling + robustness + sharpness mediation).
  NOT sufficient for the full move-by-move degradation endpoint.

Dense move-by-move analysis:
  New work over many/all plies or a stratified sample of plies.
  Required for true move-quality degradation curves and the richer Constraint Atlas.
```

### Candidate dense move-loss row schema (15.3)

`game_id, ply, move_number, side_to_move, mover_color, dense_position_type, clock_before_s,
clock_after_s, think_time_s, white_elo, black_elo, mover_elo, opponent_elo, termination,
is_time_forfeit, result_class, pre_fen (or fen_hash), move_uci, eval_before_cp,
eval_after_actual_cp, cp_loss_raw, cp_loss_clipped, expected_score_before,
expected_score_after_actual, expected_score_loss, phase, eval_band, clock_bucket,
rating_bucket, split, mover_player_hash`.

**Field availability (verified against existing artifacts):**
- **Available at checkpoints today (re-derivable per ply with new extraction):** `game_id`,
  `move_number`, `mover_color`, ratings (stored as `white_rating`/`black_rating`/`mover_rating`,
  rename to `*_elo`), `termination`, `is_time_forfeit`, `pre_fen`/`fen_hash`, `move_uci`
  (`actual_move_uci`), `eval_before_cp` (`mover_pre_cp`/`pre_sf_eval_cp`), `eval_after_actual_cp`
  (`mover_post_cp`/`post_sf_eval_cp`), `cp_loss_raw` (`cp_loss`), `cp_loss_clipped`
  (`clipped_cp_loss`), `expected_score_before/after` (`es_pre`/`es_post`),
  `expected_score_loss`, `eval_band`/`clock_bucket`/`split`/`mover_player_hash` (derivable/join).
- **Requires NEW extraction (absent today):** dense `ply` + `dense_position_type` (only 4
  checkpoints exist), per-ply `clock_before_s`/`clock_after_s`/**`think_time_s`** (not stored —
  needs consecutive clock annotations from raw PGN), and a per-ply pre/post Stockfish eval at
  **every** sampled ply (current pass evaluated only the post-move position at 4 checkpoints).
- **Requires a join (not in `next_move_loss`):** `result_class` (present in
  `feature_positions_broad_*`).

The big cost driver: dense extraction multiplies the engine work from ~2.67 evals/game
(checkpoints) to one eval per sampled ply, plus per-ply clock parsing — 15.3A must size this and
recommend dense-vs-stratified sampling.

## 12. Phase 16 restoration plan

**Phase 16 is not synthesis. Phase 16 is cross-time-control dose-response.** Candidate controls:
**3+0, 5+0, 10+0 (anchor), 10+5 or 15+10 increment.** Core question: *do clock, move-quality,
and sharpness patterns vary across time controls in a way consistent with bounded-resource
constraints?* **Required caveat:** Lichess rating pools differ across time controls, so cross-
control comparisons require **within-pool rating quantiles** or explicit rating-pool caveats.
Phase 16 reuses the dense pipeline (parse → eval → loss → sharpness → join) per control.

## 13. Phase 17 packaging restoration plan

Packaging belongs in **Phase 17**, after the empirical work. Phase 17 = synthesis-readiness
audit (reuse 16.0A) + final report skeleton + final tables/figures + final report draft +
README/public summary + optional outreach package. The 16.0A claim-architecture content is
reusable later but must not control the current default path.

## 14. Required 15.2B patch plan

15.2B (the patch ticket) should modify `ROADMAP.md`, `PREREGISTRATION.md`, `EXPERIMENT_LOG.md`,
and optionally `docs/roadmap_rescope_v11_draft.md` to:

1. Add a **roadmap recovery note** (this audit's conclusion; cite `phase_15_2a`).
2. **Reclassify 16.0A synthesis-readiness** as an early/off-roadmap checkpoint / Phase
   17-adjacent (do not delete the files).
3. **Remove `16.0B — Final Report Skeleton` as the default next ticket.**
4. **Restore Phase 15.2 onward as the active path** (the §11 sequence), noting the v11
   §15.2-vs-executed-14.2 numbering reconciliation.
5. **Restore Phase 16 as cross-time-control dose-response.**
6. **Restore Phase 17 as packaging.**
7. **Preserve fallbacks:** C3c enrichment (14.2E), C3b flagging-sharpness (14.3B), early
   synthesis checkpoint (16.0A snapshot).
8. **Set next default to `15.2B — Roadmap Recovery Patch`** → then `15.3A`.

## 15. Recommended next empirical ticket after 15.2B

**15.3A — Dense Move-by-Move Loss Feasibility Audit** (size the per-ply extraction: dense vs
stratified-ply sampling, clock-parsing for think-time, engine compute, schema, pilot plan).
**Not** final synthesis.

## 16. Explicit stop conditions and non-claims

The project must **not** stop merely because: checkpoint C4 is coherent; a conservative
synthesis exists; C3c was underpowered; C3a/C3b were not default; or packaging is tempting. The
dense move-quality endpoint and cross-time-control dose-response remain unfinished and are the
point of the project.

Preserved forbidden claims (unchanged): no causality; no "time pressure causes worse reasoning";
no "low clock causes blunders"; no "Stockfish is ground truth"; no "human obviousness modeled";
no "sharpness moderation confirmed"; no "sharpness moderation disproven" (it is
underpowered/no-claim); no "DRAW solved"; no "best human chess predictor." All current results
remain predictive/descriptive, not causal; Stockfish eval is objective context, not absolute
ground truth.
