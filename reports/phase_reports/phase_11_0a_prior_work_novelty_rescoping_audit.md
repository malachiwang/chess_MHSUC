# Ticket 11.0A — Prior-Work / Novelty / Move-Quality Curve Re-Scoping Audit

**Labels:** AUDIT/REPORTING | doc-only
**Date:** 2026-06-12
**Owner:** Malachi Wang
**Proposal under audit:** `docs/roadmap_rescope_v11_draft.md` (v11-draft, v2-merged)

Source verification status: **COMPLETE** (web access available; all eight required
source areas verified directly; residual caveats noted per source in §3).

---

## 1. Executive summary

**The v11 direction remains worth pursuing.** Direct verification of all eight required
source areas confirms the central premise: no prior work performs eval-controlled,
outcome-level clock-residual decomposition with moderation tests — the 11.0A kill
condition ("prior work already does eval-controlled clock-residual moderation") is
**not triggered**. The nearest neighbors are: Anderson et al. (move-level error vs.
difficulty/skill/time, tablebase endgames), ChessMimic (outcome prediction without
engine-eval control, blitz), and Barthelemy's variation-entropy paper (engine-derived
narrowness vs. think time and move quality, descriptive). None occupies the residual-
moderation lane. Two verification findings *sharpen* the plan rather than threaten it:
(a) Barthelemy 2025 is the closest engine-narrowness prior art and must be cited as
such in Phase 14; (b) jk_182's mistake-rate post reports that *inaccuracy* rates
**decrease** at low clock in 3+0 — a non-monotonicity warning for Phase 15 curve
expectations. The proposal should proceed to 11.0B with the small edits listed in §9.

## 2. Existing project claim

Current supported claim, conservatively stated (from
`reports/eval_conditioned_modeling_2024_{09,10}_250k_v1.md`,
`reports/constraint_slices_2024_{09,10}_250k_v1.md`,
`reports/cross_month_replication_2024_10_250k_v1.md`, EXP-008–EXP-011):

> Across two independent Lichess 10+0 monthly samples (2024-09, 2024-10; 250k raw games
> each), after controlling for fixed-depth Stockfish eval and ratings, clock features add
> a small but replicated predictive signal for game outcomes
> (E3→E4 = −0.0138 [−0.0186, −0.0091] and −0.0120 [−0.0177, −0.0062]; delta =
> log_loss(E4) − log_loss(E3), negative = clock improved), localized most strongly to
> late-game low-clock positions (60–180s late-checkpoint cells exclude zero in both
> months; under-60s point deltas ≈ −0.25, descriptive).

Standing qualifiers preserved: predictive modeling, not causal inference; Stockfish eval
is objective position context, not absolute ground truth; reasoning quality is not
directly measured; DRAW is sparse and not solved; no "degradation curve" language;
flagging-channel and player-leakage robustness are open (Phase 11.2/11.3 of the
proposal).

## 3. Prior-work source table

Verification method: WebSearch + direct fetch of abstracts/PDFs on 2026-06-12.
"Verified" = claims below were read from the source or its abstract; residual caveats
flagged inline.

### 3.1 Anderson, Kleinberg, Mullainathan — *Assessing Human Error Against a Benchmark of Perfection*
- **Citation:** KDD 2016 (pp. 705–714) and ACM TKDD 11(4), 2017.
- **URLs:** https://www.cs.toronto.edu/~ashton/pubs/tbase-tkdd.pdf ; https://arxiv.org/abs/1606.04956
- **Status:** peer-reviewed (KDD + TKDD). Verified (PDF fetched; full body skimmed via
  extraction — fine-grained section detail partially summarized).
- **Establishes:** move-level human-error (blunder) prediction in tablebase-solved
  positions (ground-truth optimal play) from millions of amateur games; features
  organized as skill / time available / inherent difficulty; difficulty features
  dominate skill and time; error probability rises when **fewer near-optimal moves**
  are available (narrowness at the move level); time–difficulty interactions are
  examined at the move level.
- **Does not establish:** outcome-level (game-result) modeling controlling for engine
  eval; residual decomposition of what clock adds beyond eval+rating; cross-month or
  cross-time-control replication of any residual; moderation of an *outcome-level*
  clock residual by position character; anything outside tablebase endgame domains.
- **Implication:** the **key comparison paper**. Our move-level Phase 15 work is
  replication-framed against it; our outcome-level residual-moderation lane is
  unoccupied by it. Its narrowness finding independently motivates Phase 14's
  narrowness core (and must be cited as move-level precedent).

### 3.2 Maia / Maia-2 / Maia4All / Chessformer ("Maia-3")
- **Citations:** McIlroy-Young, Sen, Kleinberg, Anderson — *Aligning Superhuman AI with
  Human Behavior: Chess as a Model System*, KDD 2020 (arXiv:2006.01855). Tang et al. —
  *Maia-2: A Unified Model for Human-AI Alignment in Chess*, NeurIPS 2024
  (arXiv:2409.20553). Maia4All — individual-level extension (two-stage embedding
  framework; models individuals from ~20 games; preprint — exact arXiv ID not pinned in
  this audit, related to arXiv:2605.11893 *Toward Modeling Player-Specific Chess
  Behaviors*; label **preprint/partially verified**). *Chessformer: A Unified
  Architecture for Chess Modeling* (arXiv:2605.19091) — **ICLR 2026 poster** (upgraded
  from "preprint" in the proposal); introduces Geometric Attention Bias; powers
  "Maia-3" with 57.1% move-matching accuracy.
- **URLs:** https://arxiv.org/abs/2006.01855 ; https://arxiv.org/abs/2409.20553 ;
  https://arxiv.org/abs/2605.19091 ; https://arxiv.org/abs/2605.11893
- **Status:** KDD 2020 + NeurIPS 2024 peer-reviewed; Chessformer ICLR 2026
  (peer-reviewed venue); Maia4All preprint. Verified except Maia4All ID.
- **Establishes:** skill-conditioned human **move prediction** is a mature, crowded
  lane (46–52% → 57.1% accuracy across generations); per-skill and per-individual
  modeling solved to a strong standard; public weights exist.
- **Does not establish:** outcome-level residual analysis; eval-controlled clock
  residuals; sharpness moderation of outcome predictability.
- **Implication:** stay out of move-imitation. Frozen Maia-2 import is correctly
  confined to Tier B (Phase 15.2). The gate's "import a frozen published model" test
  is well-founded.

### 3.3 ChessMimic
- **Citation:** Thomas Johnson, *ChessMimic: Per-Rating Transformer Models for Human
  Move, Clock, and Outcome Prediction in Online Blitz Chess*, arXiv:2606.04473.
- **URL:** https://arxiv.org/abs/2606.04473
- **Status:** arXiv preprint, single author, not peer-reviewed. Verified (abstract
  fetched directly).
- **Establishes:** three encoder-only transformers (move / think-time / outcome), one
  instance per 100-Elo band, Lichess **blitz**; move model beats Maia-2; outcome model
  reaches **AUC 0.78** out of sample vs. logistic baselines using **material** +
  ratings + clock.
- **Does not establish:** any engine-eval control in outcome baselines (abstract
  confirms material-based logistics, not eval-controlled); residual or moderation
  analysis; anything on 10+0 rapid; calibration/log-loss style probabilistic claims.
- **Implication:** the proposal's approved wording is accurate as written —
  "a strong neural reference point, not a direct ceiling" (different domain, time
  control, target setup, baseline controls). Our E-ladder decomposes what
  interpretable, eval-controlled features recover; no direct benchmark claim unless we
  run one on our domain.

### 3.4 DeepMind searchless chess / ChessBench
- **Citation:** Ruoss et al., *Amortized Planning with Large-Scale Transformers: A Case
  Study on Chess* (initially "Grandmaster-Level Chess Without Search"),
  arXiv:2402.04494; ChessBench dataset (~15B Stockfish-16-annotated datapoints);
  code at github.com/google-deepmind/searchless_chess.
- **URLs:** https://arxiv.org/abs/2402.04494 ; https://github.com/google-deepmind/searchless_chess
- **Status:** arXiv preprint + public releases (NeurIPS-adjacent; treat as preprint).
  Verified.
- **Establishes:** the engine-imitation/distillation lane is occupied at extreme scale
  (270M params, 2895 Lichess blitz Elo without search); tokenizer/data-format prior
  art for board-state transformers.
- **Does not establish:** anything about human realizability, clock effects, or
  human-error structure (the target is Stockfish, not humans).
- **Implication:** low direct relevance to Phases 11–17; reinforces the sequence-model
  gate (both imitation lanes — human and engine — are occupied).

### 3.5 Resource-rational chess under time pressure
- **Citations:** Kuperwajs et al., *Time Spent Thinking in Online Chess Reflects the
  Value of Computation* (journal version on PMC: PMC12553403; peer-reviewed) and
  Kuperwajs & co., *Exploring resource-rational planning under time pressure in online
  chess* (CogSci proceedings).
- **URLs:** https://pmc.ncbi.nlm.nih.gov/articles/PMC12553403/ ;
  https://escholarship.org/uc/item/75b4m9c2 ;
  https://cocosci.princeton.edu/papers/KuperwajsTime2025.pdf
- **Status:** peer-reviewed (journal + CogSci proceedings). Verified.
- **Establishes:** think time tracks the value of computation; players spend more time
  when thinking is more valuable and when they have more time; additional planning
  yields better moves when a better move exists; expertise modulates time-pressure
  effects; move quality measured in centipawns as a function of time settings.
- **Does not establish:** outcome-level residual decomposition; sharpness as moderator
  of an eval-controlled outcome residual; replication infrastructure of our kind.
- **Implication:** "humans blunder more under pressure / time allocation is strategic"
  is established — keep on the forbidden-as-novel list; cite as the cognitive-science
  frame for the bounded-resource interpretation in Phases 15–16.

### 3.6 Decision-time field evidence (best-vs-second-best gap)
- **Citation:** *Speed, Quality, and the Optimal Timing of Complex Decisions: Field
  Evidence*, arXiv:2201.10808 (econ); corroborated by *Emergent Complexity in the
  Decision-Making Process of Chess Players*, arXiv:2406.15463 (think time decreases
  as the best-vs-second-best evaluation gap Δ grows; Lichess blitz, move-level
  timestamps).
- **URLs:** https://arxiv.org/abs/2201.10808 ; https://arxiv.org/abs/2406.15463
- **Status:** preprints (econ / interdisciplinary). Verified.
- **Establishes:** MultiPV-style best-vs-second-best gaps are behaviorally meaningful —
  they predict human think time in the field; benefit-of-computation measures built
  from engines track real decisions.
- **Does not establish:** gap features as moderators of outcome-level clock residuals.
- **Implication:** validates Phase 14's narrowness primitive as behaviorally grounded
  rather than an engine artifact; cite in 14.1A.

### 3.7 Position-complexity / variation entropy
- **Citation:** Marc Barthelemy, *Chess variation entropy and engine relevance for
  humans*, arXiv:2505.03251.
- **URL:** https://arxiv.org/abs/2505.03251
- **Status:** arXiv preprint (physicist author; physics/complex-systems lane). Verified.
- **Establishes:** entropy over principal-variation continuations measures position
  demand; non-expert players struggle in high-entropy variations, especially when
  |eval| < 100cp (~2/3 of positions); experts reduce entropy faster through the
  middlegame; entropy correlates with think time.
- **Does not establish:** outcome-level eval-controlled residual moderation; clock ×
  narrowness interaction tests; replication discipline.
- **Implication:** **closest neighbor to the Phase 14 sharpness concept** — engine-
  derived narrowness matters more for weaker players, descriptively. Phase 14 reports
  must cite it as nearest prior art and position our contribution precisely: an
  inferential, pre-registered moderation test of an eval-controlled *outcome* residual,
  with obviousness discounts and cross-month replication — none of which the entropy
  paper does.

### 3.8 jk_182 Lichess blogs
- **Citations/URLs (hobbyist blog, not peer-reviewed; verified):**
  - *How the Evaluation and Clock impact Results of Blitz Games* (3+0):
    https://lichess.org/@/jk_182/blog/how-the-evaluation-and-clock-impact-results-of-blitz-games/I2kRp2sk
  - *How does the Clock impact the Rate of Mistakes?*:
    https://lichess.org/@/jk_182/blog/how-does-the-clock-impact-the-rate-of-mistakes/JSazQplM
  - *Analysing Armageddon Games: Time Usage, Scores and Sharpness*:
    https://lichess.org/@/jk_182/blog/analysing-armageddon-games-time-usage-scores-and-sharpness/jAYwzPZo
- **Establishes (descriptively):** clock × eval × outcome heatmaps in 3+0; expected-
  score-based mistake thresholds (5/10/20%); **a notable nuance: inaccuracy rates
  *decrease* at low clock while mistake rates stay roughly steady** (plausibly
  simplification/selection effects); an informal "sharpness" notion already circulates
  in this space.
- **Does not establish:** controls, CIs, replication, or residual decomposition.
- **Implication:** cite as descriptive precedent exactly as the proposal says. The
  inaccuracy-rate nuance is a concrete warning for Phase 15: expect non-monotone
  curves; do not pre-commit to "loss rises as clock falls" as the only acceptable shape.

## 4. Claim map

| Claim | Classification | Basis |
|---|---|---|
| "Clock matters for human chess" | **Established by prior work** | ChessMimic, resource-rational work, jk_182; our novelty is the eval-controlled residual, not the raw relevance |
| "Time pressure causes worse reasoning" | **Forbidden/overclaim** | No causal design; resource-rational work is also non-causal on this |
| "Sharp positions are harder for humans" | **Established by prior work** (move/think-time level) | Anderson et al. (narrowness→error), Barthelemy (entropy→struggle) |
| "Clock adds residual signal after eval + rating" | **Independently measured by chess-MHSUC** | EXP-008/009/011; two months; CIs exclude zero; no prior work found doing this |
| "Clock residual localizes to late-game low-clock positions" | **Independently measured by chess-MHSUC** | EXP-010/011; replicated localization |
| "Sharpness moderates the clock residual" | **Open/defensible future claim** | Phase 14; nearest neighbors (3.1, 3.7) are move-level/descriptive, not residual-moderation |
| "Clock × sharpness varies by rating" | **Open/defensible future claim** | Phase 14/16; Barthelemy's expertise gradient is descriptive precedent to cite |
| "Clock × sharpness varies by time control" | **Open/defensible future claim** | Phase 16 dose-response; no prior art found |
| "Next-move loss bridges outcome residuals to move-quality behavior" | **Open/defensible future claim** (replication-framed at the descriptive level) | Phase 15; curve *content* overlaps Anderson/jk_182 — the bridge to the outcome residual is ours |
| "Human-realizable value can be modeled as a layer on top of engine eval" | **Open/defensible future claim** (long-term synthesis; keep aspirational wording) | Phase 15–17 synthesis |
| "We are building the best human chess predictor" | **Forbidden/overclaim** | Maia/Chessformer/ChessMimic own that lane |
| "ChessMimic is a neural ceiling" | **Forbidden/overclaim** | Approved wording only: "strong neural reference point, not a direct ceiling" (domain/TC/target/baseline differences verified in §3.3) |

## 5. Corrected novelty lane (proposed exact wording)

> **chess-MHSUC's defensible contribution:** a controlled, replicated, inferential
> treatment of *eval-controlled clock residuals* on human game outcomes. Concretely:
> after conditioning on fixed-depth Stockfish evaluation and player ratings, clock
> features add a small predictive signal for game outcomes (paired game-level bootstrap
> CIs excluding zero), replicated across two independent months (2024-09, 2024-10) and
> localized to late-game low-clock positions. Planned hardening: tests against the
> flagging/time-forfeit channel (termination decomposition) and against player leakage
> (player-clustered uncertainty, then disjoint splits if feasible). Planned extensions:
> positional **sharpness as a moderator of the clock residual** (engine-side narrowness
> with obviousness discounts — not a direct blunder predictor, which is prior work);
> rating and time-control moderation in a dose-response design; a next-move-quality
> bridge that is mechanism-style but still predictive; and, long-term, a
> "human-realizable value" layer on top of engine eval. We do not claim that clock
> matters for chess (known), that sharp positions are hard (known at the move level),
> or that we predict human play best (occupied lane); we claim the controlled residual,
> its localization, its replication, and the moderation program built on it.

This matches Section 0 of the proposal; one addition is recommended (see §9): an
explicit "nearest prior art" sentence naming Anderson et al. and Barthelemy.

## 6. Sharpness definition review (Appendix B.1)

**Verdict: accept Appendix B.1 as-is**, with one citation obligation (Barthelemy as
nearest neighbor) added in 14.1A/14.3B text. The layered definition (local engine
narrowness → human obviousness discount → gated forward fragility) is sound and now
externally grounded: narrowness→error is established at the move level (Anderson),
best-vs-second gaps are behaviorally meaningful (decision-time evidence), and PV
entropy correlates with struggle, expertise-dependently (Barthelemy).

- **Fake-sharpness (recaptures/trades):** correct and necessary. An engine-narrow
  position whose only good move is an obvious recapture is human-easy; without the
  obviousness discount, the sharpness moderator would partly measure forcing-sequence
  prevalence, diluting or faking the interaction. The decision to exclude
  `best_move_is_simple_trade` from the v1 composite pending its own mini-audit is
  right — SEE-style trade detection is genuinely not rule-trivial.
- **Tier A anti-circularity:** essential. If human-behavior-derived difficulty entered
  the headline moderator, "clock matters more in humanly-hard positions" would be
  partially tautological (human difficulty is itself fit to error behavior that clock
  influences). Engine-side-only Tier A keeps the moderation test falsifiable.
  Barthelemy and Anderson both make the *human* response to narrowness part of their
  finding; our Tier A must not.
- **Forward fragility gated:** correct. Compute cost is the stated reason; the better
  reason is inferential discipline — if the local composite shows nothing, PV-chain
  features are unlikely to rescue it and would multiply researcher degrees of freedom.
  Ship local-first, exactly as written.
- **Advantaged-player conversion orientation as headline:** endorsed, pending
  Malachi's explicit approval (Appendix C #11). It is the thesis-central case
  (realizing objective value), distinct from the defensive case, and restricting the
  side-to-move primitive to board-leader-to-move positions is a clean derived view
  with no extra engine cost. Side-to-move-overall as labeled secondary is the correct
  robustness companion.

## 7. Move-quality curve / Constraint Atlas framing

**Verdict: accept the Phase 15 design with the replication framing as written**, plus
three sharpenings:

- **Useful though not novel:** the curves replicate Anderson-style and jk_182-style
  phenomena *inside our controlled, replicated pipeline*, providing (a) legibility for
  outreach, (b) the mechanism bridge from outcome residuals to move behavior, and
  (c) the substrate for the Tier-B difficulty model. The mandated wording —
  "consistent with prior descriptive and move-level work (Anderson et al.;
  resource-rational literature; jk_182), we observe…" — is correct; keep it verbatim.
- **Avoid overclaiming / "degradation curve" language:** ordered-bucket patterns over
  time bins remain patterns. The jk_182 nuance (§3.8) strengthens this: inaccuracy
  rates can *fall* at low clock (simplification, selection into shorter decisive
  games). Phase 15 must pre-accept non-monotone shapes as reportable, not anomalous.
- **Metrics:** expected-score loss as primary — endorsed (100cp at +1000 is noise;
  100cp at equality is large; jk_182 independently converged on expected-score
  thresholds, which is corroborating practice). Clipped centipawn loss secondary for
  literature comparability — endorsed. Percent swing — correctly barred from headline
  (denominator explodes near 0); Appendix A's `max(|eval|, threshold)` fallback is
  fine as exploratory-only.
- **Rating bins:** 100-pt bins are very likely too sparse for CI-bearing curves at
  250k/month scale (our four existing buckets already leave 2000+ at ~280–330 val
  games, below the 300-game CI threshold in one month). Endorse the proposal's
  expectation: 200-pt bins or the existing four buckets for CI-bearing curves; 100-pt
  only for smoothed pooled visuals; within-pool quantiles reserved for Phase 16.
  15.0A's cell-count audit remains mandatory before committing.
- **Conditioning:** eval-band panels (equal/slight/decided/winning/mate-band) and
  phase-conditioned panels are required — and the proposal already encodes the 9.2B
  lesson (never marginal-over-checkpoint clock plots). Sharpness- and time-control-
  conditioned curves enter only after 14.1B / Phase 16 respectively, as written.

## 8. Roadmap assessment

| Phase | Verdict | Notes |
|---|---|---|
| 11 (positioning/claim hardening) | **Accept as-is** | 11.2 (termination) and 11.3 (player leakage) are the two most important hardening steps before any new claims; ordering before packaging is correct |
| 12 (score-scale + clock controls) | **Accept as-is** | Parallel E3w/E4w (not replacement) is the right design; E4b/E4c establish the strongest non-sharpness baseline so Phase 14 cannot free-ride |
| 13 (cheap difficulty layer) | **Accept as-is** | Exogeneity preserved (board logic only); simple-trade mini-audit correctly scoped here |
| 14 (MultiPV sharpness) | **Accept with edits** | Add Barthelemy (arXiv:2505.03251) as named nearest prior art in 14.1A/14.3B; add decision-time gap evidence (arXiv:2201.10808, 2406.15463) as behavioral grounding; censoring note and orientation taxonomy stand |
| 15 (Constraint Atlas) | **Accept with edits** | Add the jk_182 non-monotonicity caution (inaccuracies fall at low clock) to 15.0A/15.0C expectations; everything else stands |
| 16 (cross-TC dose-response) | **Accept as-is** | Rating-pool non-comparability and per-control termination decomposition already handled |
| 17 (packaging) | **Accept as-is** | Reconciliation of "package first" into post-hardening packaging is coherent; the claim must be hardened (11.2/11.3) before it is packaged |
| Sequence-model gate | **Accept as-is** | Verification strengthened it: both imitation lanes (human: Maia-3 at 57.1%; engine: ChessBench at 2895 Elo) are occupied; public weights satisfy condition 3 |

Nothing should be removed or deferred beyond the gating already built into the proposal.

## 9. Proposed edits before/within 11.0B

To `docs/roadmap_rescope_v11_draft.md` (or applied during the 11.0B patch):

1. **§11.0A source list / future RELATED_WORK.md:** update Chessformer's status from
   "preprint" to **ICLR 2026 poster** (peer-reviewed venue); note Maia-3 = 57.1%
   move-matching. Note the resource-rational line has a peer-reviewed journal version
   (PMC12553403), not only CogSci proceedings.
2. **§14 (14.1A and 14.3B):** add an explicit "nearest prior art" citation obligation —
   Barthelemy (arXiv:2505.03251) for engine-derived narrowness/entropy and its
   expertise gradient; decision-time gap evidence (arXiv:2201.10808; arXiv:2406.15463)
   as behavioral validation of the narrowness primitive.
3. **§15 (15.0A/15.0C):** add the jk_182 non-monotonicity caution: inaccuracy rates can
   decrease at low clock (3+0, descriptive); pre-accept non-monotone curve shapes.
4. **§0 novelty lane:** append one sentence naming nearest prior art (Anderson et al.
   move-level; Barthelemy descriptive narrowness) to inoculate the claim against
   "isn't this known?" readings.
5. **Maia4All entry:** label "preprint; exact identifier to be pinned in
   RELATED_WORK.md" (this audit could not pin the arXiv ID with confidence).
6. `ROADMAP.md`: the 11.0B patch should also mark the "Proposed v11 Research Re-Scope"
   pointer section as superseded/absorbed when (and only when) the patch is applied.

None of these edits change phases, tickets, success/kill criteria, or ordering.

## 10. Open questions for Malachi

Carried from Appendix C of the proposal (unchanged, still all open — answers needed at
or before 11.0B approval): (1) Phase 11→17 ordering and packaging reconciliation;
(2) termination minimum bar (time-forfeit vs. board-decided sufficient?); (3) player-
leakage rung acceptability; (4) blunder threshold (expected-score loss ≥ 0.10?);
(5) Atlas rating bins (200-pt / existing buckets for CIs?); (6) first increment control
(10+5 or 15+10?); (7) MultiPV/next-move compute ceiling; (8) Tier A/B discipline as
standing rule; (9) mate-band handling; (10) EXP-012+ numbering; (11) advantaged-player
conversion sharpness as headline orientation; (12) simple-trade exclusion from v1
composite.

New questions from this audit:

13. Phase 14/15 reports will need to cite preprints (Barthelemy; decision-time
    evidence). Is citing clearly-labeled preprints as motivating/nearest-neighbor
    sources acceptable as a standing policy, with peer-reviewed sources required only
    for "established by prior work" claims in the claim map?
14. ChessMimic is single-author and not peer-reviewed, yet it is our most-cited neural
    reference point. Should packaging (Phase 17) hedge further ("a recent preprint
    reports…"), or is the current approved wording sufficient?
15. jk_182's inaccuracy-rate finding suggests a possible *selection* story (players
    simplify under time pressure). Should 15.1A add a pre-registered secondary contrast
    distinguishing "worse moves at low clock" from "different (simpler) positions at
    low clock," or is that deferred to exploratory analysis?

## 11. Exact next ticket recommendation

**Recommend: 11.0B — ROADMAP Re-Scoping Patch**, incorporating the §9 edits during the
patch (they are small, additive, and none alters structure, criteria, or ordering — a
separate 11.0A-revision round would add a cycle without adding safety). Preconditions
for 11.0B: Malachi reviews this audit, answers (at minimum) Appendix C questions 1, 8,
10, and 11, and explicitly approves applying the proposal. 11.0B then: applies the v11
document to `ROADMAP.md` additively, creates `docs/RELATED_WORK.md` from §3 of this
audit (with the §9 status corrections), creates the `PREREGISTRATION.md` v1 stub, and
updates the `EXPERIMENT_LOG.md` index. If Malachi wants more time on the open
questions, 11.1A (claim audit + pre-registration drafting) cannot proceed first without
the patch — the pre-registration belongs to the new arc — so the fallback is simply to
hold at this audit.

## 12. Final safety check

Run at completion (results in the final chat report): `git status --short`,
`git diff --stat` — expected: only this report file added; no code, data, or artifacts
touched; nothing staged or committed.
