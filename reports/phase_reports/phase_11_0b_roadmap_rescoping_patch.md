# Ticket 11.0B — ROADMAP Re-Scoping Patch

**Labels:** REPORTING | doc-only
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Summary

Applied the v11 research re-scope to the project documentation after the 11.0A
prior-work verification confirmed the novelty lane is open (kill condition not
triggered). Documentation-only; no code, data, or artifacts touched.

## 2. Files created

| File | Content |
|---|---|
| `docs/RELATED_WORK.md` | Verified source table from 11.0A §3 (status labels, URLs, establishes / does-not-establish / implication per source), positioning summary, forbidden claims, defensible lane, report obligations |
| `PREREGISTRATION.md` | v1 stub: frozen E3/E4 anchors with recorded CIs, four primary future contrasts (E4a→E4b/E4c; board-decided-only E3→E4; sharpness difference-of-deltas; next-move expected-score loss ~ clock), split/test discipline, anti-overclaiming language, revision policy |
| `reports/phase_reports/phase_11_0b_roadmap_rescoping_patch.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `docs/roadmap_rescope_v11_draft.md` | Status header: PROPOSAL ONLY → ACCEPTED AND APPLIED (provenance preserved). 11.0A §9 edits folded in: (1) Chessformer → ICLR 2026 poster, Maia-3 57.1%, Maia-2 → NeurIPS 2024, resource-rational journal version noted; (2) nearest-prior-art citation obligations added to 14.1A and 14.3B (Barthelemy arXiv:2505.03251; decision-time gap evidence arXiv:2201.10808/2406.15463); (3) jk_182 non-monotonicity caution added to 15.0A (item 10) and 15.0C; (4) §0 novelty lane gains a nearest-prior-art sentence; (5) Maia4All labeled "preprint; identifier to be pinned in RELATED_WORK.md". No phases, tickets, orderings, or success/kill criteria changed |
| `ROADMAP.md` | Pointer section "Proposed v11 Research Re-Scope" replaced with "Active v11 Research Arc" (§9 edit 6): v11 accepted after 11.0A; current arc Phase 11 onward; Phases 0–9 historical record unchanged; Phase 10/sequence models remain gated; detailed architecture lives in the v11 doc; "package first" reconciled into Phase 17; standing rules and next ticket recorded |
| `EXPERIMENT_LOG.md` | EXP-012 added (documentation/research-planning milestone — precedent: EXP-006 hygiene-hardening entry). New-arc numbering EXP-012+ adopted per approval default |

## 4. Approval basis

Malachi's approval defaults for the Appendix C / 11.0A questions were applied:
Phase 11→17 ordering; packaging reconciled into Phase 17 after claim hardening;
Tier A/B sharpness discipline as standing rule; EXP-012+ numbering;
advantaged-player conversion sharpness as Phase 14 headline orientation
(side-to-move-overall labeled secondary); simple-trade excluded from v1 composite;
labeled-preprint citation policy; ChessMimic "reference point, not ceiling" wording;
jk_182 non-monotonic low-clock caution included in Phase 15 framing.

## 5. Safety

No code modified; no `data/` paths touched; no tests needed (no code changed);
nothing staged or committed. Verification greps confirm: no unqualified "ChessMimic
is a neural ceiling" language anywhere; "PROPOSAL ONLY" survives only in provenance
context; "degradation curve(s)" appears only in cautionary/forbidden-language contexts.

## 6. Recommended next ticket

**11.1A — Scientific Claim Audit + PREREGISTRATION v1 refinement** (refine the four
primary contrasts into fully specified, locked statements before any Phase 12+
feature exists).
