# Phase 16.0A — Synthesis Readiness / Public-Facing Claim Audit

**Labels:** AUDIT / DESIGN | doc-only, no modeling
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Audits whether the project is ready for a final, public-facing synthesis and defines the
exact claim architecture. **No model was run; no thresholds or prior classifications were
changed.** Verdict: **the evidence is sufficient and the project is ready for final report
drafting (Option A)** — the core arc (outcome flagging-channel reframing + small robust
move-quality clock association, eval-state-dominant) is settled, replicated, robustness-checked,
and player-clustered; the sharpness arc is honestly bounded (feasible features; C3c
underpowered/no-claim; C3a/C3b not pursued). The reusable **claim hierarchy, candidate
abstract, forbidden-claims list, report outline, and table/figure inventories** are in
`reports/synthesis_readiness_audit.md`. No additional modeling is required before synthesis;
remaining work is figure/table generation and minor doc cleanup, both doable inside the
synthesis ticket.

## 2. Files inspected

PREREGISTRATION.md, ROADMAP.md, EXPERIMENT_LOG.md; the combined result reports
(`c4_move_quality_arc_summary`, `termination_decomposition_combined`,
`controlled_move_quality_combined`, `clock_association_robustness_combined`,
`constraint_atlas_combined`, `multipv_sharpness_combined`, `sharpness_interaction_combined`,
`player_clustered_*`); key phase reports (11.2B, 15.1G, 15.1H, 14.2D, 14.3A); and the full
`reports/` + `docs/` inventory (`find`).

## 3. Files modified

- `reports/synthesis_readiness_audit.md` (created — reusable claim architecture).
- `reports/phase_reports/phase_16_0a_…md` (created — this record).
- `ROADMAP.md` — 16.0A complete; next → 16.0B.
- `EXPERIMENT_LOG.md` — EXP-038.
- `PREREGISTRATION.md` — synthesis-readiness status note (no locked-analysis rewrite).

No code, data, or tests touched.

## 4. Current evidence inventory

- **Outcome (E3/E4):** clock improves outcome prediction (09 −0.0138, 10 −0.0120), replicated.
- **Termination:** outcome clock signal ≈ flagging channel; board-decided residual collapsed
  (+0.0010 / +0.0060); time-forfeit large (−0.118 / −0.131); survives player clustering.
- **Move quality:** eval-state dominant; small robust replicated clock association (`60_180`
  vs `over_180` pooled +0.0034); survives 15.1F robustness + board-decided-only + clustering.
- **Sharpness:** features feasible/stable (base rate ≈0.14); C3c interaction
  underpowered/no-claim; C3a/C3b audited and not pursued.

## 5. Claim hierarchy

Five levels (full text in `reports/synthesis_readiness_audit.md`):
- **L1 headline:** (1) clock improves outcome prediction; (2) that signal is largely the
  flagging channel, not board-play degradation; (3) eval-state dominates move quality, clock a
  small robust residual after controls.
- **L2 secondary (caveated):** robustness survival; board-decided-only same-sign; clustering
  doesn't remove it; sharpness features feasible/stable.
- **L3 exploratory:** constraint atlas, surface-bait, sharpness distributions, C3b feasibility.
- **L4 unresolved:** C3c sharpness × clock move-quality moderation — directional,
  underpowered/no-claim, not confirmed, not disproven.
- **L5 abandoned/not-recommended:** C3a (confounded / null-by-construction), human-obviousness
  modeling (deferred), DRAW-specific modeling, prior-trajectory control (deferred).

## 6. Candidate public-facing abstract

Drafted in `reports/synthesis_readiness_audit.md` (labeled DRAFT, not final). It states the
flagging-channel reframing, eval-state dominance, the small move-quality clock residual, the
feasible-but-unresolved sharpness layer, and "predictive/descriptive, not causal."

## 7. Forbidden public claims

Listed prominently in the claim-architecture doc: no causal/time-pressure-degradation claims;
no "E3/E4 measures move quality"; no "sharpness proven/explains clock"; no "human obviousness
modeled"; no "Stockfish is ground truth"; no "DRAW solved"; no "best human predictor"; and the
sharpness result is **neither null nor confirmed** (underpowered/no-claim).

## 8. Final report section outline

15-section outline (abstract → question → data → eval/targets → E3/E4 → termination → next-move
loss → atlas → controlled models → robustness/clustering → sharpness features → sharpness
interaction (underpowered) → limitations → future work → conclusion). Full list in the claim
doc.

## 9. Required tables

10-table inventory mapped to source reports (dataset summary; E3/E4; termination decomposition;
next-move-loss summary; atlas; controlled move-quality; robustness; sharpness distribution; C3c
result+classification; claim/evidence-status table). See claim doc.

## 10. Required figures

7 figures identified (E3→E4 delta; termination forest; atlas ES-loss heatmap; controlled clock
contrast with CIs; sharpness base-rate; C3c forest labeled underpowered; optional pipeline
diagram). **Not generated here** — `reports/figures/` exists (empty); generation is a 16.0B task.

## 11. Report readiness by arc

| Arc | Status |
|---|---|
| E3/E4 outcome modeling | ready (needs final summary table + figure) |
| Termination decomposition | ready (needs forest figure) |
| Next-move-loss extraction | ready |
| Constraint atlas | ready (needs figure) |
| Controlled move-quality | ready (needs figure) |
| Clock association robustness | ready (needs summary table) |
| Player-clustered uncertainty | ready |
| MultiPV sharpness extraction | ready (needs distribution figure) |
| C3c sharpness interaction | ready — unresolved/underpowered, clearly labeled |
| C3a/C3b audit | ready — not pursued, documented |

All arcs are **ready or ready-pending-figure/table**; none is blocking. No arc requires more
modeling for the synthesis to be written honestly.

## 12. Repo / documentation readiness

- **ROADMAP coherent** through Phase 14/15 (the 15.1H "Post-C4 Reconciliation" section is the
  live source of truth; v11 draft tagged superseded-in-part). ✓
- **PREREGISTRATION coherent**, with locked contrasts + post-result status notes (C2/C4/§C3c +
  14.2C/14.2D/14.3A notes); no contradictions. ✓
- **EXPERIMENT_LOG complete** through EXP-037. ✓
- **Report filenames consistent** (`<topic>_<tag>.md` + `phase_reports/phase_<n>_…`). ✓
- **Heavy artifacts ignored** (`data/` + `*.parquet` gitignored; no raw data or hashes
  committed). ✓
- **Generated reports suffice to reproduce conclusions** (each arc has month + combined +
  phase reports). ✓
- **Minor cleanup (non-blocking):** results are somewhat scattered across many reports — the
  new `synthesis_readiness_audit.md` concentrates the claim architecture; a final report will
  consolidate the rest. The 14.1B pilot report carries a full-precision float (cosmetic, in a
  committed prior-ticket file) — leave as-is. No stale "Phase 8 scaling"/numbering issues found
  in the live ROADMAP head.

## 13. Remaining gaps and limitations

- Lichess **10+0 only**; **two monthly samples**; **observational/predictive, not causal**.
- Stockfish depth-12 eval is a **benchmark/context measure, not ground truth** of human
  decision quality.
- Outcome clock signal is **mostly flagging/time-forfeit**; the **board-decided outcome signal
  collapsed**.
- Next-move-loss approximates move quality but depends on engine eval + the **train-fit
  expected-score transform**.
- The **clock/move-quality association is small**; **eval-state effects dominate**.
- **C3c sharpness moderation unresolved/underpowered**; **human obviousness not modeled**.
- **Time-management and selection effects remain**; **White-to-move-only** checkpoint scope.
- **DRAW not specially solved**; **no best-human-move-prediction claim**.

## 14. Recommendation

**Option A — proceed to final report drafting.** The evidence is sufficient, the claim
architecture is locked and honest, and remaining gaps are caveat-able. No additional modeling
is needed. Figure/table generation and final consolidation happen inside the synthesis ticket.
**Do not** return to sharpness modeling unless the project explicitly chooses C3c enrichment
(14.2E) or C3b flagging (14.3B).

## 15. Roadmap reconciliation

Next pointer → **16.0B — Final Report Skeleton / Claim Architecture Draft** (assemble the
report skeleton from `synthesis_readiness_audit.md`; generate the inventoried tables/figures
into `reports/figures/`; consolidate the per-arc reports). Preserved optional fallbacks:
**14.2E — Third-Month / Pooled-Power C3c Enrichment Audit** and **14.3B — C3b Flagging
Sharpness Pre-Registration** (both the user's call; not on the default path).

## 16. Recommended next ticket

**16.0B — Final Report Skeleton / Claim Architecture Draft.** Fallbacks (deliberate choice
only): 14.2E (C3c enrichment) or 14.3B (C3b flagging). No modeling on the default path.

## Explicit non-claims

No modeling was run. No sharpness moderation has been shown; C3c is neither null nor confirmed
(underpowered/no-claim); C3a/C3b have not been modeled. No causality; no "time pressure causes
worse reasoning"; no human obviousness; surface-bait is exploratory only; Stockfish is not
ground truth; DRAW is not solved; no best-predictor claim. No thresholds or prior
classifications were changed.
