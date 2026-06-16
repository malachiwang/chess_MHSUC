# Phase 15.2B — Roadmap Recovery Patch

**Labels:** DOCUMENTATION / GOVERNANCE | doc-only patch
**Date:** 2026-06-15
**Owner:** Malachi Wang

## 1. Executive summary

Applied the 15.2A recovery architecture to the governance documents. The premature synthesis
routing is reversed: **the 16.0A synthesis-readiness audit is reclassified as an early/off-
roadmap claim-architecture checkpoint (reusable in Phase 17), not Phase 16 work**, and
**`16.0B — Final Report Skeleton` is removed as the default next ticket.** The official roadmap
now restores **Phase 15 (Constraint Atlas / move-quality curves) as active and expanded to dense
move-by-move resolution**, **Phase 16 as cross-time-control dose-response**, and **Phase 17 as
packaging**. The default next ticket is **15.3A — Dense Move-by-Move Loss Feasibility Audit**.
No code, models, Stockfish, or data artifacts were touched; no thresholds or result
classifications were changed; nothing is staged or committed.

## 2. Files inspected

`ROADMAP.md`, `docs/roadmap_rescope_v11_draft.md`, `PREREGISTRATION.md`, `EXPERIMENT_LOG.md`;
`reports/phase_reports/phase_15_2a_roadmap_recovery_dense_move_quality_architecture_audit.md`,
`reports/synthesis_readiness_audit.md`,
`reports/phase_reports/phase_16_0a_synthesis_readiness_public_claim_audit.md`. All present.

## 3. Files modified

- `ROADMAP.md`
- `docs/roadmap_rescope_v11_draft.md`
- `PREREGISTRATION.md`
- `EXPERIMENT_LOG.md`
- (created) `reports/phase_reports/phase_15_2b_roadmap_recovery_patch.md`

## 4. Recovery patch applied

The synthesis-first default (16.0A → 16.0B) is removed; the v11 architecture (Phase 15 atlas /
Phase 16 cross-TC / Phase 17 packaging) is restored as authoritative, with Phase 15 explicitly
expanded to the dense move-by-move endpoint the project actually targets.

## 5. ROADMAP changes

- Appended a **⚠️ RECLASSIFIED** tag to the 16.0A entry (early/off-roadmap checkpoint; reusable
  in Phase 17; not Phase 16).
- Added **15.2A complete** and **15.2B complete** live-arc entries.
- **Replaced the "Next ticket: 16.0B" bullet** with **"Next ticket: 15.3A — Dense Move-by-Move
  Loss Feasibility Audit"** plus preserved fallbacks (14.2E, 14.3B, 16.0A snapshot).
- Added a **"Roadmap Recovery Note (Ticket 15.2B)"** section: the recovery rationale, the
  restored **Phase 15.2–15.7** continuation, the **metric policy** (primary ES loss; secondary
  clipped cp; raw cp only in eval-band panels; %eval-swing forbidden as headline) and the **M0→M3
  model ladder**, the restored **Phase 16 (cross-TC dose-response, with the within-pool
  rating-quantile caveat and candidate controls 3+0/5+0/10+0/increment)**, and the restored
  **Phase 17 (packaging)** with suggested tickets.
- Updated the **Completed tickets** section (Phase 11, Phase 14, Phase 15 checkpoint layer,
  16.0A reclassification, Phase 15.2A/B).

## 6. v11 draft changes

Added a top **"ROADMAP RECOVERY (Tickets 15.2A → 15.2B)"** note: the synthesis misroute
contradicted the draft's own architecture; Phase 15 stays active and unfinished at dense
resolution; Phase 16 = cross-TC; Phase 17 = packaging; 16.0A reclassified; the **§15.2A/B
sharpness×clock mediation = the executed 14.2A–14.2D work (directional/underpowered/no-claim)**;
dense CP/ES-loss analysis remains unfinished and active. `ROADMAP.md` is named authoritative for
the restored continuation. The body is otherwise unchanged (provenance retained).

## 7. PREREGISTRATION changes

Added a **"Post-15.2A Roadmap Recovery Note"** after the 16.0A synthesis-readiness note:
reclassifies 16.0A; restores the Phase 15 empirical path; Phase 16 cross-TC; Phase 17 packaging;
**C3c remains directional/underpowered/no-claim**; final synthesis is not the default next step.
**No locked analysis, threshold, contrast, or classification is rewritten.**

## 8. EXPERIMENT_LOG changes

Added **EXP-039 — Roadmap Recovery Patch** (doc-only; reclassification; restored Phase 15/16/17;
next = 15.3A; settled findings preserved; no models; no thresholds changed).

## 9. Reclassification of 16.0A

16.0A is now labeled, in ROADMAP / v11-draft / PREREGISTRATION, as an **early/off-roadmap
synthesis / claim-architecture checkpoint, reusable in Phase 17 packaging — not Phase 16
dose-response work, and not the trigger for final report drafting.** Its files
(`phase_16_0a…`, `synthesis_readiness_audit.md`) were **not deleted, renamed, or edited**.

## 10. Restored Phase 15 path

15.2B (complete) → **15.3A Dense Move-by-Move Loss Feasibility Audit** → 15.3B/C dense pilot/full
extraction → 15.4A–D CP/ES Constraint Atlas + controlled dense modeling → 15.5A–D
sharpness-enriched atlas + interaction panel → 15.6A–C sharpness prediction-improvement
(M0→M3) → 15.7A–C trajectory / prior-quality controls.

## 11. Restored Phase 16 path

**Cross-time-control dose-response** (3+0, 5+0, 10+0 anchor, 10+5/15+10 increment) with the
**mandatory within-pool rating-quantile / rating-pool caveat**; tickets 16.1A–16.3B.

## 12. Restored Phase 17 path

**Packaging / public report** after the empirical arcs (synthesis readiness → report skeleton →
tables/figures → draft → outreach); 16.0A reusable here.

## 13. Next ticket

**15.3A — Dense Move-by-Move Loss Feasibility Audit** (not final synthesis).

## 14. Verification

`git status --short` shows the 4 modified docs + this new report; `git diff --stat` touches only
those docs; no code/data changes; safety greps clean (forbidden phrases only in negated/forbidden
contexts). Details in the final response.

## 15. Non-claims / safeguards

No code changed. No models run. No Stockfish run. No data artifacts modified. No thresholds or
classifications changed. Nothing staged or committed. Settled findings preserved verbatim;
C3c stays directional/underpowered/no-claim; no causal / "time pressure causes worse reasoning" /
"low clock causes blunders" / "Stockfish is ground truth" / "human obviousness modeled" /
"sharpness moderation confirmed-or-disproven" / "DRAW solved" / "best predictor" claims.
