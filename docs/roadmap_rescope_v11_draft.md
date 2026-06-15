# chess-MHSUC — ROADMAP Re-Scoping Proposal (v11-draft, v2-merged)

**SUPERSEDED IN PART (reconciled 2026-06-14, Tickets 15.1E → 15.1H):** this v11 draft is
retained as historical design context; its detailed Phase 14–15 sequence is no longer
authoritative. It is superseded in part by the post-11.2B / 15.1D / 15.1F / 15.1G evidence
chain. **The live operational roadmap is `ROADMAP.md`** (see its "Post-C4 Reconciliation
(Ticket 15.1H)" section). In particular: Phase 15 move-quality work was **pulled earlier**
after the board-decided outcome residual collapsed (11.2B); the **C4 result is now
consolidated** as a descriptive/predictive move-quality finding (small, replicated, robust,
secondary clock association; eval-state dominant), with **prior trajectory deferred** as a
limitation; Phases 12/13 are non-blocking backlog; and **sharpness (Phase 14) has not been
shown** and begins with a feasibility/compute audit (14.1A). Phases/criteria below are
retained for provenance only.

**Status:** ACCEPTED AND APPLIED (Ticket 11.0B, 2026-06-12), following the 11.0A
prior-work verification (`reports/phase_reports/phase_11_0a_prior_work_novelty_rescoping_audit.md`)
and Malachi's approval defaults. This file is the authoritative detailed Phase 11–17
architecture referenced by `ROADMAP.md`. Provenance: originally stored as PROPOSAL ONLY
(commit `01e0747`); the 11.0A §9 edits are folded in below.
**v2 change log:** merges the "Revision Addendum — Explicit Sharpness Definition" into this
document. The addendum becomes Appendix B.1 (definition layer), with minimal touch-ups to
13.2, 14.1A, 14.1B, 14.2A, and Appendix C. No phases, tickets, or success/kill criteria
were removed; no new phases or tickets were added.
**Relationship to current ROADMAP.md:** Additive. Nothing from the existing roadmap is deleted.
Phases 1–9 remain recorded as completed. Phase 10 (sequence models) remains gated and is
renumbered into the gate at the end of this document. The previous recommendation —
"research packaging / outreach readiness before more modeling" — is not discarded; it is
explicitly reconciled: packaging moves to Phase 17 and is *preceded* by claim hardening
(Phase 11), because the prior-work findings changed what the packaged claim must say.

---

## 0. Guiding thesis and corrected novelty lane

**Thesis:** chess-MHSUC studies how objective chess value becomes human-realizable value
under bounded constraints (rating, clock, phase, time control, positional sharpness).

**The defensible novelty lane (narrow, stated positively):**
- eval-controlled clock residuals on human game outcomes (E3 → E4 contrast, paired bootstrap CIs);
- replicated cross-month (2024-09, 2024-10);
- localized to late-game low-clock positions;
- to be tested against the flagging/time-forfeit channel;
- to be tested against player leakage (clustered uncertainty → disjoint splits);
- to be extended to positional sharpness as a **moderator of the clock residual** (not as a
  direct blunder predictor — that is prior work);
- to be extended to rating and time-control moderation (dose-response design);
- to be bridged to next-move quality as a mechanism-style (still predictive) analysis;
- eventually synthesized as a "human-realizable value" layer on top of engine eval.

Nearest prior art (per the 11.0A verification): Anderson/Kleinberg/Mullainathan establish
narrowness→error at the *move* level in tablebase domains; Barthelemy's variation-entropy
preprint (arXiv:2505.03251) establishes engine-derived narrowness/entropy as descriptively
relevant to human struggle and think time, expertise-dependently. Neither performs
eval-controlled, outcome-level clock-residual decomposition or moderation — that lane is
open (11.0A kill condition not triggered).

**Post-11.2B note (2026-06-12, KNOWN RESULT).** The pre-registered termination
decomposition (Ticket 11.2B) showed that the replicated all-games E3→E4 outcome residual
is **substantially the time-forfeit / flagging channel**: among board-decided games it
collapsed (2024-09, CI contains zero) or sign-reversed (2024-10), while time-forfeit
games carry the signal (−0.118/−0.131). Consequences for this document: the novelty-lane
bullet "eval-controlled clock residuals on human game outcomes" must be read as a
**flagging-channel** outcome residual, not a board-play residual; "moderator of the clock
residual" (the sharpness bullet) is now split across three targets — flagging risk
(C3a), board-decided outcomes (C3b, cautious/secondary), and move-quality loss (C3c);
and the board-play-quality question moves to the next-move-quality bridge (Phase 15 /
Contrast C4), which does not depend on the outcome residual surviving. See
`reports/phase_reports/phase_11_2c_claim_reframing_audit.md` and `PREREGISTRATION.md`.

**Standing list of claims we must NOT make (verbatim, keep in all reports):**
- "Sharp positions are harder for humans" as a novel claim (established at the move level
  by Anderson/Kleinberg/Mullainathan).
- "Humans blunder more under time pressure" as a novel claim (established descriptively
  and in resource-rational work).
- "Clock state is informative about human play" as a novel claim (ChessMimic,
  Omori & Tadepalli, ALLIE-adjacent work).
- "We are building the best human chess predictor" (Maia/Chessformer/ChessMimic lane).
- "Time pressure causes worse reasoning" (no causal design).
- "Stockfish is ground truth" (objective context only).
- "DRAW is solved."
- "Degradation curves" for any ordered-bucket pattern without a design that licenses it.
- ChessMimic is a "neural ceiling." **Approved wording:** "ChessMimic is a strong neural
  reference point, not a direct ceiling, because it differs in data domain (blitz vs. our
  10+0 rapid), time control, target setup, and baseline controls (material-based logistic
  baselines, not eval-controlled)."

**Standing hygiene (unchanged, restated for the new arc):**
- No `git add .`; never stage `data/`, raw PGNs, Parquet/JSON artifacts, caches, model
  binaries, plots, `.venv`, `.DS_Store`, `__pycache__`.
- A-ticket (audit/design) before B-ticket (implementation), always.
- Validation for model selection; test only for locked final evaluation.
- Pre-registered primary contrasts; everything else labeled exploratory.
- Predictive language throughout; no causal phrasing.

---

## 1. Model ladder naming conventions (additive; nothing renamed)

| ID | Definition | Status |
|----|------------|--------|
| B1–B3 | Pre-Stockfish baselines | frozen, historical |
| E1 | Stockfish eval only (cp-based) | frozen |
| E3 | eval + rating (cp-based) | **frozen lineage — never silently altered** |
| E4 | eval + rating + clock (cp-based, original clock features) | **frozen lineage** |
| E4a | alias for frozen E4, used when compared against E4b/E4c | new label only |
| E4b | E3 + rich clock dynamics + relative clock features | Phase 12 |
| E4c | E4b + game-history/trajectory features | Phase 12 |
| E3w / E4w (a.k.a. E3_score / E4_score) | **parallel** expected-score/WDL-scale versions of E3/E4 | Phase 12, robustness layer |
| E6 | E4c + static board difficulty features | Phase 13 |
| E7 | E6 + WDL outputs + best-move-type/obviousness flags | Phase 13 |
| E8 | E7 + MultiPV sharpness | Phase 14 |
| E9 | E8 + interactions (clock × sharpness, rating × sharpness, clock × rating × sharpness, phase × sharpness) | Phase 14 |
| M-series | next-move-quality (mediation/atlas) models, separate target | Phase 15 |

**Rule (incorporates correction B):** the cp-based E3/E4 result is the historical anchor and
is preserved for comparability in every report. E3w/E4w run in parallel. If the score-scale
migration changes the result materially, that divergence is **reported as a finding**, never
hidden, and never silently substituted.

---

## 2. Phase 11 — Positioning, reconciliation, and claim hardening

### 11.0A — Prior-Work / Novelty / Move-Quality Curve Re-Scoping Audit  *(doc-only; current ticket)*
Deliverables:
1. Draft source table for `docs/RELATED_WORK.md` (file NOT created in this ticket). Each
   entry requires: full citation, URL, status label (peer-reviewed / arXiv preprint /
   blog-hobbyist / unverified), one paragraph "what it establishes," one paragraph
   "what it does not establish," and one line "implication for our claim."
   Required entries (verify directly; do not launder):
   - Anderson, Kleinberg, Mullainathan — "Assessing Human Error Against a Benchmark of
     Perfection" (KDD 2016; TKDD 2017). Peer-reviewed. Establishes move-level human-error
     prediction with skill/time/difficulty features and tablebase ground truth; players err
     more when fewer near-optimal moves exist. Does NOT do eval-controlled outcome-level
     residual decomposition, moderation tests, or cross-time-control replication.
     **Key comparison paper.**
   - Maia (KDD 2020), Maia-2 (NeurIPS 2024, arXiv:2409.20553), Maia4All (preprint;
     exact identifier to be pinned in RELATED_WORK.md), Chessformer/"Maia-3"
     (arXiv:2605.19091; **ICLR 2026 poster** — peer-reviewed venue; Maia-3 reaches
     57.1% move-matching). Human move prediction conditioned on skill. Owns the
     move-imitation lane.
   - ChessMimic (arXiv:2606.04473, preprint, single author, not peer-reviewed). Per-rating
     transformers for move/clock/outcome on Lichess **blitz**; outcome AUC 0.78 vs
     **material**+rating+clock logistic baselines. Does NOT control for engine eval; does
     NOT perform residual moderation analysis; out of scope for rapid 10+0.
     Use approved "reference point, not ceiling" wording.
   - DeepMind searchless chess / ChessBench (Ruoss et al., preprint + releases).
     Stockfish-distillation transformer lane; relevant as tokenizer/data-format prior art
     and as evidence the engine-imitation lane is occupied.
   - Resource-rational chess under time pressure (CogSci proceedings; a peer-reviewed
     journal version also exists — Kuperwajs et al., PMC12553403): expertise modulates
     time-pressure effects; value-of-computation framing.
   - Decision-time field evidence (econ preprint): best-vs-second-best engine gap predicts
     longer think times. Validates MultiPV gap as behaviorally meaningful.
   - Position-complexity / variation-entropy work (physics preprint): engine-derived
     entropy correlates with human think time.
   - jk_182 Lichess blogs (hobbyist): descriptive clock × eval × outcome heatmaps (3+0)
     and clock-vs-mistake-rate analyses. Cite as descriptive precedent; our contribution
     is the controlled, replicated, inferential treatment.
2. Corrected novelty claim text (Section 0 above is the draft).
3. Explicit sharpness definition section (Appendix B.1 is the authoritative text; the
   audit document carries it as a definition section, to later inform 14.1A — it is a
   definition/roadmap refinement, not a separate implementation ticket).
4. Move-quality curve design + metric recommendation (Section "Phase 15" and Appendix A).
5. ROADMAP patch proposal (this document).
6. Open questions for Malachi (Appendix C).

Success: every claim in every existing report maps to one of
{established by prior work / independently replicated by us / open / forbidden}.
Kill/re-scope: if verification finds prior work performing eval-controlled clock-residual
moderation, the sharpness arc is re-scoped before any implementation.

### 11.0B — ROADMAP Re-Scoping Patch  *(doc-only; requires explicit Malachi approval)*
Apply this document to `ROADMAP.md` (additively), update `EXPERIMENT_LOG.md` index, create
`docs/RELATED_WORK.md` from the 11.0A table, and create `PREREGISTRATION.md` v1 stub.
No code. Success: repo docs and actual plan agree; the stale "package first" instruction
is reconciled rather than left contradicting the new arc.

### 11.1A — Scientific Claim Audit + PREREGISTRATION v1
Write the 3–5 primary contrasts for Phases 12–14 before any new feature exists:
1. E4a→E4b delta (do richer clock features absorb residual signal?), both months.
2. Board-decided-only E3→E4 delta vs. all-games delta (Phase 11.2 dependency).
3. Difference-of-deltas across sharpness terciles (Phase 14 headline; exact definition
   deferred to 14.2A but named now).
4. Next-move expected-score loss ~ clock bucket contrast at late checkpoints (Phase 15).
Everything else = exploratory, labeled as such in all reports.

### 11.2A — Termination Decomposition Feasibility Audit  *(incorporates correction D)*
**Inspect before designing.** Check whether parsed data and/or raw PGNs preserve:
- `Termination` header values and their actual vocabulary in our two months;
- `Result` cross-check; whether "Time forfeit" is reliably distinguishable from
  "Normal" (mate/resignation) and from abandonment;
- whether termination survives our cleaning pipeline or must be re-parsed (tee-cache
  makes re-parse cheap if needed).
Deliverable: feasibility verdict + exact channel taxonomy we can support
(ideal: timeout / checkmate / resignation / draw-type; minimum: time-forfeit vs. board-decided).

### 11.2B — Termination Decomposition Implementation  *(if 11.2A says feasible)*
Two designs, both months:
1. **Filter design:** re-run E3→E4 (and the P3 late-clock slices) on board-decided games only.
2. **Channel design:** multinomial termination-channel analysis — does low clock predict
   board-decided losses, or mostly mechanical timeout risk?
Success: board-decided clock delta retains a substantial fraction (guideline: ≥ ~half) of
its magnitude with CI excluding zero → claim upgrades to "not merely flagging."
Re-frame (not failure): if the residual is overwhelmingly the timeout channel, the project
honestly re-frames as quantifying the flagging channel; packaging text changes accordingly.

**RESULT (11.2B, 2026-06-12): the re-frame branch fired.** The board-decided delta
collapsed (2024-09: +0.0010, CI contains zero, retained fraction 0.07) / sign-reversed
(2024-10: +0.0060, CI excludes zero on the positive side); time-forfeit delta
−0.118/−0.131. The "not merely flagging" upgrade was NOT met. The project re-frames as
quantifying the flagging channel and moves the board-play-quality question to Phase 15 /
Contrast C4. See the 11.2C reframing audit.

### 11.3A — Player-Disjoint Split Feasibility Audit  *(incorporates correction E)*
Chess rows have TWO players; "player-disjoint" means no username appearing as White or
Black in train appears in val/test. Audit:
- username/player-ID availability in parsed data; safe anonymization (salted hash, no raw
  usernames committed anywhere);
- the bipartite player–game graph: size of the largest connected component (frequent
  players may connect most games, making strict disjointness destroy sample size);
- the practical ladder: (1) current game-level hash split [baseline, keep],
  (2) player-clustered bootstrap on existing splits [cheap, likely first implementation],
  (3) approximate disjoint split (cap leakage at a measured small overlap),
  (4) strict disjoint split [only if the graph permits].
Deliverable: feasibility verdict + recommended rung of the ladder + expected sample-size cost.

### 11.3B — Player-Leakage Robustness Implementation  *(rung chosen by 11.3A)*
Success: E3→E4 delta survives player-clustered uncertainty (and disjoint split if feasible)
with CI excluding zero. Re-frame: meaningful shrinkage = "part of the clock signal is a
stable player trait" — reported as a finding.

---

## 3. Phase 12 — Score-scale robustness layer and stronger clock controls

### 12.0A — Expected-Score / WDL Scale Audit  *(incorporates correction B: parallel, not replacement)*
Audit two routes to an outcome-scale objective control:
- Stockfish WDL output availability in our engine wrapper at depth 12;
- a cp→expected-score logistic mapping fit on the TRAIN split only (fallback that needs
  no new engine runs).
Decide route; define E3w/E4w. The cp-based E3/E4 lineage is untouched.

### 12.0B — Implement E3w/E4w on both months
Success: results reproduce in direction on the score scale. Divergence from cp-scale
results = reported robustness finding (e.g., "the clock residual is larger/smaller when
the objective control is on the outcome scale"), never a silent substitution.

### 12.1A — Clock-Dynamics / History Feature Audit
Confirm parsed data preserves per-move clock readings sufficient for: previous-move think
time, rolling think time (3/5-move), burn rate/burstiness, cumulative time used, clock
differential and ratio, board-leader-behind-on-clock flags, time-per-remaining-move
(moves-remaining heuristic fit on train only), eval trajectory across prior checkpoints,
cumulative |eval| movement, lead changes.

### 12.1B — Implement E4b (rich clock) and E4c (E4b + history)
### 12.1C — Evaluate E4a → E4b → E4c, both months
Success: richer features absorb more residual; late-game low-clock localization persists.
Either result is useful: this establishes the strongest non-sharpness baseline so that
Phase 14 sharpness cannot free-ride on weak clock modeling.

---

## 4. Phase 13 — Cheap difficulty layer

### 13.1A/B — Static board difficulty features
Material count/imbalance, queens-on/rooks-on, minor counts, legal-move counts (both sides),
checks/captures available, forcing-move density, king-safety proxies (castled status, pawn
shield, open/semi-open files near king), passed/advanced-passed/doubled/isolated pawns,
fifty-move counter, repetition state if feasible.

### 13.2A/B — WDL outputs + best-move-type / rule-based obviousness flags
From existing single-PV best moves and board logic only (no human data — this preserves
the exogeneity needed for the Phase 14 headline test):
`best_move_is_capture / _check / _recapture / _promotion / _quiet`,
`best_move_is_forced_evasion`, `best_move_is_quiet_only_move` (needs 14.1 MultiPV for the
"only" part; flag stub now, populate later), `obvious_recapture_only_move`.
Additionally, `best_move_is_simple_trade` is scoped here with its **own mini-audit**:
"simple equal trade" is not cleanly rule-computable (it requires recapture-sequence /
exchange-value reasoning, likely a static-exchange-evaluation approach) and therefore does
NOT enter the Phase 14 headline composite in v1; it may be promoted into a pre-registered
composite v2 only after its stability is demonstrated.
Principle: **trades/captures/checks are forcingness features, not sharpness.** An
engine-narrow position whose only good move is an obvious recapture is fake-sharp.
A trade can be part of a sharp line, but "trade exists" or "best move is recapture" often
lowers human-sharpness. (Full definition layer: Appendix B.1.)

### 13.3B — Evaluate E6/E7 + board-difficulty report
Sanity success criteria: quiet-only-move-type flags associate with worse conversion;
obvious-recapture narrowness does not.

---

## 5. Phase 14 — MultiPV sharpness (the headline novelty bet)

Phase 14 implements and tests the explicit layered sharpness definition in
**Appendix B.1** (local narrowness → obviousness discount → gated forward fragility);
14.1A/14.1B/14.2A reference that definition rather than restating it.

**Post-11.2B reframing (2026-06-12).** Because 11.2B showed the board-decided outcome
clock residual collapsed, sharpness moderation is **no longer assumed to moderate a
board-decided final-outcome residual as the sole or default headline.** Per the 11.2C
audit and `PREREGISTRATION.md`, sharpness is tested against three distinct targets:
**C3a — flagging risk** (does sharpness × clock predict time-forfeit risk?, well
motivated by 11.2B); **C3b — board-decided outcomes** (cautious/secondary, since the
overall board-decided residual collapsed); **C3c — move-quality loss** (sharpness ×
clock on next-move expected-score loss — the natural extension of Contrast C4 and the
recommended central sharpness test). The headline among the three is confirmed with
Malachi before 14.2A. The Tier A engine-side-only discipline and the advantaged-player
conversion orientation are unchanged. Phase 14's MultiPV compute is now justified
primarily by C3a and C3c; confirm the arc is still worth its cost (Appendix C / 14.1A)
under the reframed targets before committing.

### 14.1A — MultiPV Feasibility / Compute Audit
Cost of MultiPV-5 depth-12 on existing checkpoints (~65k + ~63k positions); pilot subset
plan if needed; decide whether depth-8/10 intermediate evals are harvestable from the same
search (depth-instability features) at near-zero cost; mate-band handling (separate bucket).
**Censoring note:** with MultiPV-K, "number of value-preserving moves" is right-censored
at K. This is harmless for the binary composite (≤2 good moves is fully observable at
K=5) but means continuous count/entropy features cannot distinguish "K good moves" from
"many good moves"; document this, and choose K (5 vs 10) consciously against compute cost.
**Orientation audit (per Appendix B.1):** side-to-move sharpness is the computational
primitive (it is what a MultiPV run at the checkpoint natively produces); advantaged-player
conversion sharpness, defensive sharpness, and mutual sharpness are derived views
(filters/restrictions on the primitive), not separate engine runs.
**Nearest-prior-art citation obligation (per 11.0A):** Phase 14 documents must cite
Barthelemy (arXiv:2505.03251, preprint) as the closest engine-derived narrowness/entropy
prior art, and the decision-time gap evidence (arXiv:2201.10808; arXiv:2406.15463,
preprints) as behavioral validation that best-vs-second-best gaps are meaningful to
humans — while stating that none performs eval-controlled outcome-residual moderation.

### 14.1B — Pilot Sharpness Extraction (one month first)
Implements the **local narrowness + obviousness discount layers only** of the Appendix B.1
definition (forward-line fragility is gated; see below).
Narrowness core, computed in expected-score space (side-to-move primitive; derived
orientations per 14.1A):
best-vs-second expected-score gap; count of moves within 30/50/100 cp of best AND within
5/10/20 expected-score points of best (both unit families retained — cp for literature
comparability, score for the headline); entropy over softmaxed top-5 scores;
worst-of-top-5 (tail risk); one-good-move / few-good-moves flags.
Composite headline feature (pre-registered in 14.2A) — **high sharpness = narrow AND
non-obvious**:
`sharp := (value-preserving move count ≤ 2 in score terms) AND NOT (best move is an
obvious recapture or forced evasion)`.
("Simple trade" is excluded from the v1 composite pending the 13.2 mini-audit; promotion
to a composite v2 requires its own pre-registration.)
**Forward-line fragility (gated; later extension per Appendix B.1):** only-move chain
length along the PV (K=6), number of narrow decision nodes in the next K plies, number of
quiet-only-move nodes, average/minimum good-move count along the PV, cumulative
expected-score fragility under second-best/plausible deviations, multi-precise-move-
sequence flags — all behind a separate compute estimate inside 14.1A. The first
implementation ships without these; the line version comes only after the basic version
works.

### 14.2A — Sharpness Interaction Pre-Registration
Lock the headline contrast BEFORE modeling: **difference of paired clock deltas across
train-defined sharpness terciles (or the binary composite), late checkpoints
(move_30+move_40), engine-side sharpness only, both months.**
**Orientation pre-registration (per Appendix B.1):** the headline view is
**advantaged-player conversion sharpness** — the side-to-move primitive restricted to
positions where the side to move is the board leader — because it is the thesis-central
case (how hard is it for the better-placed player to preserve and convert objective
value?). Side-to-move-overall is the labeled secondary view; defensive and mutual
sharpness are exploratory. Final orientation choice is confirmed with Malachi via
Appendix C before 14.2B runs.
Tier-A discipline: the headline moderator uses NO human-behavior-derived inputs (avoids
circularity). Learned human difficulty is Tier B and lives in Phase 15.

### 14.2B — Implement E8/E9 + interaction tests
### 14.3B — Sharpness Slice Report
By month, checkpoint, clock bucket, rating bucket, board leader/trailer; exploratory
slices labeled. The report's related-work paragraph carries the 14.1A nearest-prior-art
citations (Barthelemy; decision-time gap evidence), clearly labeled as preprints.
**Success:** clock × sharpness difference-of-deltas CI excludes zero in 2024-09 AND
replicates in sign in 2024-10 AND survives the 11.2 board-decided filter.
**Kill:** if sharpness neither moderates the clock residual nor adds main-effect signal
beyond E4c/E7 in either month → stop the sharpness arc, write up the controlled null
honestly (a well-controlled null is informative), proceed to Phase 15 descriptives and
Phase 16/17.

---

## 6. Phase 15 — Constraint Atlas (move-quality curves) + mediation  *(new; incorporates Malachi's design request)*

**Framing (answer to "how to be non-novel but useful"):** the descriptive curves replicate
known phenomena *within our controlled pipeline* and make the project legible. Reports
must say "consistent with prior descriptive and move-level work (Anderson et al.;
resource-rational literature; jk_182 blogs), we observe…" — replication framing, never
novelty framing. Their scientific role is (a) motivating and (b) mechanism-bridging the
novel moderation tests.

### 15.0A — Move-Quality Curve / Constraint Atlas Audit
Answer, against the actual repo (do not assume):
1. Do parsed checkpoints preserve the next actual move and clocks needed for think time?
2. Do we have (or can we cheaply reconstruct) FENs before AND after the actual next move?
3. Does `stockfish_eval.py` support post-move evaluation cheaply (one extra eval per
   checkpoint position ≈ doubling current engine cost — confirm)?
4. Loss definition feasibility (Appendix A): eval-swing (A) is available with one extra
   eval; loss-vs-engine-best (B) becomes ~free after 14.1B MultiPV. Recommend A-in-score-
   space first, upgrade to B later; document depth-parity convention (Appendix A).
5. Compute cost estimate for both 250k-month datasets.
6. Rating-bin stability: audit cell counts for 100-pt vs 200-pt bins per time bucket;
   expectation at current scale: 200-pt bins (or 4 existing buckets) for CI-bearing
   curves; 100-pt only for smoothed pooled visualization; quantiles reserved for Phase 16.
7. Time-bin stability for 10+0: under_10 / 10_30 / 30_60 / 60_180 / over_180 — audit n in
   under_10 at each checkpoint; collapse if sparse. Bins must be re-derived per time
   control in Phase 16.
8. Blunder threshold candidates: expected-score loss ≥ 0.10 (primary candidate),
   cp ≥ 200 (literature-comparable secondary); pre-register one, sensitivity-check both.
9. Perspective: side-to-move primary; advantaged-player view derived; player-specific
   deferred. Draws scored 0.5. Mate/near-mate = separate band. Orientation formalization
   for the "human realizability gap" is DEFERRED until these definitions exist
   (incorporates correction F — do not commit to a G(s,r,t) formula yet).
10. **Non-monotonicity caution (per 11.0A):** jk_182's descriptive 3+0 analysis reports
   that *inaccuracy* rates decrease at low clock while mistake rates stay roughly
   steady — plausibly simplification and/or selection effects. Curves must pre-accept
   non-monotone shapes as reportable findings, not anomalies; "loss rises as clock
   falls" is not the only acceptable shape.

### 15.0B — Implement Checkpoint-Level Next-Move Loss Extraction
### 15.0C — Generate Descriptive Constraint Curves (the Atlas)
Curve interpretation inherits the 15.0A non-monotonicity caution: non-monotone shapes
(e.g., inaccuracy rates falling at low clock) are reportable findings, framed against
the selection-vs-degradation distinction, never forced into a monotone narrative.
Plot suite (all with bootstrap CI ribbons; median + 75th/90th percentiles where skewed):
1. Time remaining vs mean/median next-move expected-score loss; lines = rating buckets.
2. Same x-axis vs clipped cp loss (secondary, familiar metric).
3. Rating × time heatmap (color = expected-score loss; variant: P(large mistake)).
4. Eval-band-conditioned panels: equal / slight / decided / winning / mate-band
   (prevents the "100cp at +1000 ≠ 100cp at equal" distortion).
5. Phase-conditioned panels (move_10/20/30/40) — never marginal-over-checkpoint clock
   plots (checkpoint–clock confound, per the 9.2B audit insight).
6. Sharpness-conditioned curves (after 14.1B): clock × sharpness; rating lines within
   high-sharpness positions.
7. Board-leader low-clock conversion plots, especially in sharp positions.
8. Cross-time-control signature plots (deferred to Phase 16; same axes, within-pool
   rating quantiles).

### 15.1A/B — Controlled Next-Move Quality Modeling (M-series)
`expected-score loss ~ time bucket + rating + eval band + phase (+ interactions:
time×rating, time×eval band, time×sharpness, time×rating×sharpness)`.
Controls must include PRIOR trajectory / cumulative loss (the "clock as symptom of past
struggle" confound). Robustness: board-decided only; mate-band excluded/separate;
player-clustered uncertainty per 11.3. Language: "loss is higher in these constraint
states," never "time causes degradation."

### 15.2A/B — Sharpness × Clock Move-Quality Mediation
The mechanism bridge: does low clock predict worse next moves *especially* in sharp
positions, conditional on eval, rating, phase, prior trajectory? Tier-B learned difficulty
D(s, r) (expected loss model, train-fit only) is built here; optional frozen-Maia import
as a human-prior obviousness feature is considered here and only here.
Success: the outcome-level interaction reappears at the move level.

---

## 7. Phase 16 — Cross-time-control and Elo-by-time-control dose-response

### 16.1A — Time-Control Expansion Audit
Choose 3+0, 5+0, 10+0 (anchor), and one increment control (10+5 or 15+10); sample-size
and compute estimates; **rating-pool non-comparability**: Lichess maintains separate
rating pools per speed — use within-pool rating quantiles or explicitly disclaim
cross-pool comparison; population self-selection caveat in all reports; flagging
prevalence will differ by control (interacts with 11.2 channel analysis — plan to run the
termination decomposition per control).

### 16.1B — Parse + evaluate selected controls (reuse pipeline; per-control time bins)
### 16.2B — Cross-Time-Control Clock × Sharpness Report
### 16.3B — Elo-by-Time-Control Sharpness Report
Falsifiable expected pattern (pre-register direction, not magnitude):
clock and clock × sharpness footprints largest in fast no-increment, smallest with
increment; rating quantiles buffer sharpness mainly when time is adequate.
Success: monotone-ish ordering, phrased as "the predictive footprint changes in the
direction a bounded-resource account expects."
Kill (of interpretation, not project): flat/reversed pattern is reported as evidence
against the time-scarcity interpretation.

---

## 8. Phase 17 — Research packaging and outreach  *(reconciles the prior "package first" recommendation)*

### 17.1A/B — Packaging
README research section; one-page summary; signature table
{month × (overall delta, late-clock slice, sharpness interaction)} + time-control gradient
if Phase 16 done; `docs/RELATED_WORK.md` finalized from 11.0A; ChessMimic paragraph uses
the approved "reference point, not ceiling" wording and positions our ladder as
decomposing what interpretable, eval-controlled features recover of a neural model's
outcome edge — without claiming a direct benchmark unless we actually run one on our
domain; "do not overclaim" section embedded in the summary itself.

---

## 9. Gate — Neural / sequence models (formerly Phase 10; remains closed)

Opens only if ALL hold:
1. Phases 11–15 complete (16 strongly preferred);
2. a specific, written question exists that interpretable models demonstrably cannot
   answer;
3. the answer is not available by importing a frozen published model (Maia-2, ChessMimic
   weights are public);
4. Malachi explicitly approves.
Currently: no qualifying question identified. Competing in the transformer-prediction
lane is explicitly out of scope.

---

## Appendix A — Next-move loss metric recommendation

**Primary metric: expected-score loss** (per correction/metric audit):
convert evals to expected score (Stockfish WDL or train-fit cp→score logistic),
mover's perspective, draws = 0.5. Rationale: 100cp near equality is large; 100cp at +1000
is noise; expected score linearizes outcome relevance and aggregates cleanly.

**Secondary metric: clipped centipawn loss** (cap at e.g. 1000cp; mate scores mapped to
cap) for comparability with prior chess literature. Raw cp reported only inside eval-band-
conditioned panels (option 4), which is the third leg of the recommendation.

**Avoid as headline: percent swing** (denominator explodes near 0); if ever used,
`max(|eval_before|, threshold)` denominator, exploratory only. "Practical loss relative
to available value" is deferred pending a stability audit (15.0A may scope it; not before).

**Loss definition options (15.0A must pick):**
- **Option A (eval-swing):** loss = max(0, score_before − score_after_actual), mover
  perspective. One extra eval per checkpoint. Caveat: conflates positions where even the
  best move loses value; at fixed depth, score_before already presumes best play, so A
  approximates B up to depth artifacts.
- **Option B (vs engine best):** loss = score(best move) − score(actual move). Cleanest
  "accuracy" notion; nearly free once 14.1B MultiPV exists.
- **Option C:** cp-space versions of A/B for the secondary metric.
- **Recommendation:** A in expected-score space now; upgrade to B after 14.1B; report both
  once both exist.
- **Depth-parity note:** evaluating pre-move (depth d, mover to move) vs post-move
  (depth d, opponent to move) introduces an odd/even search-parity artifact. Pick one
  convention (e.g., evaluate both at depth 12 and acknowledge the parity asymmetry, or
  evaluate post-move at depth 11), document it, and sensitivity-check on a subsample.

## Appendix B — Tier A / Tier B sharpness discipline (anti-circularity)

- **Tier A (headline moderation tests):** engine-side sharpness only — MultiPV narrowness
  in score space + rule-based obviousness discounts from board logic. No human-behavior-
  derived inputs. This keeps the clock × sharpness test non-tautological.
- **Tier B (mechanism layer, Phase 15.2):** learned difficulty D(s, r) from train-split
  human move quality; optional frozen Maia-2 human-prior features. Acceptable for
  mediation/practical-eval modeling; never substituted into Tier A tests.
- Human-sharpness is rating-indexed in principle (a quiet only-move obvious to 2200 may be
  invisible to 1200); the models express this through rating × sharpness interactions
  rather than baking rating into the feature.

### Appendix B.1 — Explicit sharpness definition (merged addendum; authoritative for Phase 14)

Sharpness must not be used vaguely. **Definition:**

> A position is sharp when preserving objective value requires a narrow and non-obvious
> move or sequence of moves.

This has three separable components:

**1. Local engine narrowness** — how many good moves exist now?
MultiPV-style features: best-vs-second-best eval or expected-score gap; number of moves
within 30/50/100 cp of best; number of moves within 5%/10% expected-score loss of best;
entropy over top candidate moves; one-good-move / few-good-moves flags. This captures
whether the position has many safe continuations or only one/few value-preserving moves.

**2. Human obviousness / non-obviousness** — engine narrowness alone is not enough.
A position where the only good move is an obvious recapture or forced evasion is
engine-narrow but often human-easy. Distinguish: best move is recapture; is capture; is
check; is forced/legal evasion; is quiet; is a quiet only-move; obvious-recapture-only-move
("fake sharpness") flag. Trades, captures, and recaptures are modeled as forcingness /
best-move-type features, not automatically as sharpness. A trade can be part of a sharp
line, but "trade exists" or "best move is recapture" often lowers human-sharpness.
("Simple trade" detection requires its own mini-audit — see 13.2 — and is excluded from
the v1 headline composite.)

**3. Forward-line sharpness (gated/later; compute-heavier)** — how long does the precision
demand continue? A position requiring one accurate move is sharp; a position requiring
four or five accurate moves in sequence is much sharper. Later features: only-move chain
length along the principal variation; number of narrow decision nodes in the next K plies;
number of quiet-only-move nodes in the next K plies; average/minimum good-move count along
the PV; cumulative expected-score fragility if second-best or plausible alternatives are
chosen; whether conversion requires multiple precise moves in a row.

**Layered terminology (use consistently in all reports):**
- *Engine narrowness:* few moves preserve value.
- *Human non-obviousness:* the preserving move is not natural/easy for humans.
- *Forward fragility:* multiple precise moves are required over the next several plies.
- *Human sharpness:* narrowness plus non-obviousness, optionally extended by forward
  fragility.

**Initial headline definition (v1, implemented in 14.1B):**
High sharpness = only 1–2 value-preserving moves AND the best/value-preserving move is not
an obvious recapture or forced evasion (simple-trade exclusion deferred to composite v2
pending the 13.2 mini-audit).

**Later extension:** line sharpness = the number and severity of precision demands along
the next K plies of the engine principal variation. First implementation uses local
narrowness + obviousness discount only; the sequence/line version comes after the basic
version works.

**Orientation taxonomy (audited in 14.1A; pre-registered in 14.2A):**
side-to-move sharpness (computational primitive); advantaged-player conversion sharpness
(derived headline view — how hard is it for the player with the better position to
actually preserve and convert that advantage?); defensive sharpness for the worse side
(derived, exploratory); both-sides/tactical mutual sharpness (derived, exploratory).

**Chess.com analogy (caveat):** the intuitive idea resembles "great move"/"excellent move"
sequences — not merely that the move is good, but that it is unusually important, not
obvious, and alternatives lose significant value. Do NOT rely on Chess.com labels: they
are a proprietary, version-unstable, unauditable human-difficulty model, and importing
them would violate the Tier A anti-circularity rule. Reconstruct the logic from
Stockfish/MultiPV, expected-score loss, and rule-based obviousness flags.

**Roadmap intent:** the sharpness phase is not merely "add MultiPV features" — it
specifically tests whether clock pressure matters more when objective value depends on
narrow, non-obvious, and possibly multi-move precision.

## Appendix C — Open questions for Malachi (carry into 11.0B approval)

1. Approve the Phase 11 → 17 ordering and the reconciliation of "package first" into
   Phase 17? (Alternative: minimal packaging pass immediately after 11.2/11.3.)
2. Termination minimum bar: if PGNs only support time-forfeit vs. board-decided (no finer
   channels), is that sufficient for 11.2B, or re-parse for more?
3. Player-leakage rung: is player-clustered bootstrap acceptable as the headline
   robustness if strict disjoint splits prove destructive?
4. Blunder threshold to pre-register: expected-score loss ≥ 0.10, or a different value?
5. Rating bins for the Atlas: accept 200-pt (or existing 4 buckets) for CI-bearing curves,
   100-pt for smoothed visuals only?
6. First increment control for Phase 16: 10+5 or 15+10?
7. Compute budget ceiling for MultiPV-5 and next-move evals (rough wall-clock tolerance)?
8. Approve Tier A / Tier B sharpness discipline as a standing rule?
9. Mate-band handling: separate bucket (recommended) or exclusion in first pass?
10. Should EXPERIMENT_LOG numbering continue EXP-012+ for the new arc (recommended)?
11. Sharpness orientation for the 14.2A headline contrast: approve advantaged-player
    conversion sharpness (derived from the side-to-move primitive, restricted to
    board-leader-to-move positions) as the headline view, with side-to-move-overall as
    the labeled secondary? (Per Appendix B.1.)
12. Approve excluding `best_move_is_simple_trade` from the v1 headline composite pending
    the 13.2 stability mini-audit, with promotion only via a pre-registered composite v2?

