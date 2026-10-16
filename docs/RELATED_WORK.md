# Related work and attribution

The project uses established engine-based move-quality measurements and investigates
clock associations previously studied in chess research. It does not claim a new
metric, a leading human-move predictor, or priority for the observed associations.

The [later repository-overlap audit](../reports/phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md)
compares the implementation and research questions with prior work and supports the
replication framing. The [third-party notice](../NOTICE.md) records license scope.
The termination comparison and unresolved sharpness interaction are described in
the [README](../README.md) with their evaluation limits.

The original literature table below preserves attribution, source-status labels,
and the reasoning behind the earlier proposal. Its “unoccupied” and “novelty lane”
statements are superseded by the later audit and are not current claims. Verification
dates refer to that historical review; sources were not re-reviewed for this cleanup.

<details>
<summary>Historical source table and positioning notes</summary>

## Status and citation hygiene

Created by Ticket 11.0B (2026-06-12) from the verified source table in
`reports/phase_reports/phase_11_0a_prior_work_novelty_rescoping_audit.md` (§3).
All entries below were verified by direct web search and abstract/PDF fetch on
2026-06-12; residual caveats are flagged inline. Standing policy (Malachi-approved):
preprints are citable when relevant but must always be labeled as
arXiv/preprint/poster/not-peer-reviewed; only peer-reviewed sources support
"established by prior work" classifications in claim maps; never launder a vague
source; if a source cannot be verified, label it unverified/incomplete rather than
citing it confidently.

## Source status legend

- **peer-reviewed** — published at a peer-reviewed venue (conference proceedings or journal).
- **arXiv preprint** — public preprint, not (yet) peer-reviewed.
- **ICLR poster / venue poster** — accepted at a peer-reviewed venue; cite with venue.
- **blog-hobbyist** — descriptive, no review, no inferential controls.
- **unverified/incomplete** — could not be fully pinned during verification; do not cite as authority.

## Source table

| Source | Status | What it establishes | What it does not establish | Implication for chess-MHSUC |
|---|---|---|---|---|
| Anderson, Kleinberg, Mullainathan — *Assessing Human Error Against a Benchmark of Perfection* (KDD 2016; TKDD 11(4) 2017). https://www.cs.toronto.edu/~ashton/pubs/tbase-tkdd.pdf | peer-reviewed | Move-level human-error prediction in tablebase-solved positions; difficulty features dominate skill and time; errors rise when fewer near-optimal moves exist (move-level narrowness); move-level time–difficulty interactions | Outcome-level modeling controlling for engine eval; residual decomposition of clock beyond eval+rating; cross-month/TC replication; moderation of an outcome-level residual | **Key comparison paper.** Phase 15 move-level work is replication-framed against it; the outcome-level residual-moderation lane is unoccupied by it; its narrowness finding motivates Phase 14 |
| McIlroy-Young, Sen, Kleinberg, Anderson — *Aligning Superhuman AI with Human Behavior: Chess as a Model System* (KDD 2020). https://arxiv.org/abs/2006.01855 | peer-reviewed | Skill-conditioned human move prediction (Maia; 46–52% accuracy per band) | Outcome residual analysis; eval-controlled clock work | The move-imitation lane is mature and occupied; stay out |
| Tang et al. — *Maia-2: A Unified Model for Human-AI Alignment in Chess* (NeurIPS 2024). https://arxiv.org/abs/2409.20553 | peer-reviewed | Unified skill-aware human move model across rating bands; public weights | Same as above | Frozen Maia-2 import is confined to Tier B (Phase 15.2) only |
| Maia4All — individual-level Maia extension (two-stage embeddings; ~20 games per individual; related: arXiv:2605.11893) | arXiv preprint; **identifier partially verified** | Individual-level move modeling from small samples | Outcome residual analysis | Reinforces that per-player modeling is occupied; pin exact ID before citing in any packaged document |
| *Chessformer: A Unified Architecture for Chess Modeling* (arXiv:2605.19091; ICLR 2026 poster; powers "Maia-3", 57.1% move-matching). https://arxiv.org/abs/2605.19091 | ICLR 2026 poster (peer-reviewed venue) | State-of-the-art human move prediction architecture (Geometric Attention Bias) | Outcome residual analysis; eval-controlled anything | Confirms the imitation lane's pace; no overlap with our residual lane |
| Johnson — *ChessMimic: Per-Rating Transformer Models for Human Move, Clock, and Outcome Prediction in Online Blitz Chess* (arXiv:2606.04473). https://arxiv.org/abs/2606.04473 | arXiv preprint, single author, **not peer-reviewed** | Per-100-Elo transformers for move/think-time/outcome on Lichess **blitz**; outcome AUC 0.78 vs material+rating+clock logistic baselines; beats Maia-2 on moves | Engine-eval control in outcome baselines; residual or moderation analysis; anything on 10+0 rapid; probabilistic calibration claims | **Approved wording only:** "a strong neural reference point, not a direct ceiling" — different domain (blitz vs 10+0 rapid), time control, target setup, and baseline controls (material-based, not eval-controlled) |
| Ruoss et al. — *Amortized Planning with Large-Scale Transformers: A Case Study on Chess* / ChessBench (arXiv:2402.04494; github.com/google-deepmind/searchless_chess) | arXiv preprint + public releases | Engine-distillation at extreme scale (270M params, 2895 Lichess blitz Elo, no search); tokenizer/data-format prior art | Anything about human realizability, clock effects, or human error structure | Low direct relevance; reinforces the sequence-model gate (engine-imitation lane occupied) |
| Kuperwajs et al. — *Time Spent Thinking in Online Chess Reflects the Value of Computation* (journal version: PMC12553403) + *Exploring resource-rational planning under time pressure in online chess* (CogSci proceedings). https://pmc.ncbi.nlm.nih.gov/articles/PMC12553403/ ; https://escholarship.org/uc/item/75b4m9c2 | peer-reviewed (journal + proceedings) | Think time tracks value of computation; expertise modulates time-pressure effects; extra planning improves chosen moves when a better move exists | Outcome-level residual decomposition; sharpness moderation of residuals | "Humans blunder more under pressure / allocate time strategically" is established — forbidden as a novel claim; cite as the cognitive-science frame for the bounded-resource interpretation |
| *Speed, Quality, and the Optimal Timing of Complex Decisions: Field Evidence* (arXiv:2201.10808); corroborating: *Emergent Complexity in the Decision-Making Process of Chess Players* (arXiv:2406.15463) | arXiv preprints (econ / interdisciplinary) | Best-vs-second-best engine gaps predict human think time in the field; engine-built benefit-of-computation measures track real decisions | Gap features as moderators of outcome-level clock residuals | Behavioral validation of the Phase 14 narrowness primitive; cite in 14.1A (labeled preprints) |
| Barthelemy — *Chess variation entropy and engine relevance for humans* (arXiv:2505.03251). https://arxiv.org/abs/2505.03251 | arXiv preprint | PV-entropy as position demand; non-experts struggle in high-entropy variations, especially \|eval\| < 100cp; experts reduce entropy faster; entropy correlates with think time | Outcome-level eval-controlled residual moderation; clock × narrowness interaction tests; replication discipline | **Closest neighbor to the Phase 14 sharpness concept — mandatory nearest-prior-art citation** in Phase 14 documents; our contribution is the inferential, pre-registered moderation of an eval-controlled outcome residual with obviousness discounts and cross-month replication |
| jk_182 Lichess blogs — *How the Evaluation and Clock impact Results of Blitz Games* (3+0); *How does the Clock impact the Rate of Mistakes?*; *Analysing Armageddon Games: Time Usage, Scores and Sharpness*. https://lichess.org/@/jk_182/blog | blog-hobbyist | Descriptive clock × eval × outcome heatmaps (3+0); expected-score mistake thresholds (5/10/20%); **inaccuracy rates decrease at low clock while mistake rates stay roughly steady**; an informal "sharpness" notion | Controls, CIs, replication, residual decomposition | Descriptive precedent; our contribution is the controlled, replicated, inferential treatment. The non-monotonicity nuance is a standing Phase 15 caution |

## Key positioning summary

The project's lane — eval-controlled clock residuals on human game outcomes, with
replication, localization, and a moderation program — is unoccupied. The nearest
neighbors operate at the move level (Anderson et al., tablebase domains), at the
descriptive level (Barthelemy; jk_182), or at the outcome level without engine-eval
control (ChessMimic). The move-imitation lane (Maia family, Chessformer) and the
engine-imitation lane (ChessBench) are both mature and explicitly avoided.

## Forbidden novelty claims

Never claim as novel (verbatim list from the v11 roadmap §0, grounded in this table):
"sharp positions are harder for humans" (Anderson et al., move level); "humans blunder
more under time pressure" (descriptive + resource-rational work); "clock state is
informative about human play" (ChessMimic and adjacent work); "we are building the best
human chess predictor" (Maia/Chessformer/ChessMimic lane). Also forbidden regardless of
novelty: "time pressure causes worse reasoning" (no causal design); "Stockfish is ground
truth"; "DRAW is solved"; "degradation curves" without a licensing design; "ChessMimic
is a neural ceiling" (approved wording: strong neural reference point, not a direct
ceiling).

## Defensible novelty lane

After conditioning on fixed-depth Stockfish evaluation and player ratings, clock
features add a small, replicated (2024-09, 2024-10), late-game-low-clock-localized
predictive signal for human game outcomes — measured with paired game-level bootstrap
CIs. The forward program: harden against the flagging/time-forfeit channel and player
leakage; extend to positional sharpness as a *moderator* of the clock residual
(engine-side narrowness + obviousness discounts, Tier A); extend to rating and
time-control moderation (dose-response); bridge to next-move quality
(mechanism-style, still predictive); synthesize as a human-realizable value layer
on top of engine eval.

## Notes for future reports

- Phase 14 documents must cite Barthelemy (arXiv:2505.03251) as nearest prior art and
  the decision-time gap evidence (arXiv:2201.10808; arXiv:2406.15463) as behavioral
  grounding — all labeled preprints.
- Phase 15 reports use replication framing verbatim: "consistent with prior descriptive
  and move-level work (Anderson et al.; resource-rational literature; jk_182 blogs),
  we observe…" — and pre-accept non-monotone curve shapes (jk_182 nuance).
- ChessMimic wording is fixed (see Forbidden claims). Any direct benchmark claim
  requires actually running a comparison on our domain.
- Maia4All's exact identifier must be pinned before it is cited in packaged documents.
- **Post-11.2B positioning note (2026-06-12):** the termination decomposition (11.2B)
  showed the project's outcome residual is substantially the time-forfeit / flagging
  channel, and moved the board-play-quality question to next-move-quality analysis
  (Contrast C4). Move-quality prior work — Anderson et al. (move-level error vs.
  difficulty/skill/time), the resource-rational literature, and Barthelemy
  (narrowness/entropy) — is therefore **more central** to the project's framing than
  before: it is the correct comparison set for C4/C3c, while ChessMimic/Maia remain the
  reference points for the (avoided) move/outcome-imitation lane. This does not change
  any source's status label; it raises the relative emphasis of the move-quality
  sources in C4 and Phase 15 reports.
- Update this file whenever a new source is verified; never add a source without a
  status label.

</details>
