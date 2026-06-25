# Phase 16.2G — Prior-Art / Repository Overlap / Project Kill Audit

**Ticket:** 16.2G — Prior-Art / Repository Overlap / Project Kill Audit (research-audit / project-decision only)
**Status:** complete (expanded evidence base — 9 repositories inspected at source level + multiple
full-paper inspections). No code, no models, no figures, no Stockfish, no extraction, no data modified,
no third-party source copied into `chess-MHSUC`. External clones live only under
`/Users/malachiwang/chess-prior-art/` (verified outside the repo).

> Claim discipline: this audit uses "no equivalent was found in the inspected sources", "apparently
> distinct within the reviewed literature", "partial overlap", "replication", "extension", "commodity",
> "search/source remains inconclusive". It does NOT use "novel", "first-ever", "unique", "state of the
> art", or "definitive absence of prior work". A systematic search + source inspection is not a proof of
> absence.

**Evidence-tier legend (used throughout):** **[SV]** directly source-verified (code inspected at a named
commit); **[PV]** paper-verified (methods/results text inspected); **[RO]** README-only; **[SO]**
search-snippet only; **[U]** unresolved.

## 1. Executive verdict

The expanded review (9 repos at source + AKM/ChessMimic full-text) **confirms and strengthens** the
earlier assessment rather than overturning it. The vast majority of `chess-MHSUC` is **commodity
engineering or replication of established findings**:
- The move-quality **metric layer** (expected-score loss, clipped CP, normalization/equal-weighting) is
  commodity — present in `ianfab/chess-analysis` [SV], and expected-centipawn-loss is a training/eval
  metric in `oxi` [SV] and `allie` [SV].
- **Clock parsing + increment-aware think time** is commodity (`oxi/pgn_processor.rs` [SV], `maia2` [SV]).
- **"Lower clock → more error / blunder rate vs time remaining"** is established: Anderson–Kleinberg–
  Mullainathan [PV] explicitly analyze "empirical blunder rate as a function of time remaining."
- **Faster controls → more error, skill interacts** is established (Time-Pressure-&-Skill literature [SO/PV]).
- **Outcome prediction conditioned on ratings + time control + remaining clock** exists: ChessMimic [PV].
- Human move/time/outcome **prediction** with rating+clock is a crowded field (Maia, Maia-2, Maia-3,
  Oxi, Allie, ChessMimic) — the project deliberately does descriptive move-quality analysis instead, so
  it is not redundant with them, but it does not compete with or extend them.

**One component remains apparently distinct within the reviewed sources, now on much stronger evidence:**
the **termination-channel decomposition** (separating the clock→outcome signal into time-forfeit vs
board-decided after position + rating control), **board-decided-only move-quality analysis**, and
**player-side timeout attribution**. A decisive-capability grep across all 8 clones returned **0 files**;
the four closest clock-aware sources (ChessMimic [PV], Allie [SV], Maia [SV], Oxi [SV]) and AKM [PV] do
not perform it. It is, however, a **modest descriptive result** and is already implemented (not remaining
work).

**Primary recommendation (independently reassessed across all four outcomes): Outcome 2 — reframe as a
replication/benchmark**, anchored by the apparently-distinct termination decomposition, with **Secondary:
Outcome 3 — retain as portfolio engineering** (the portfolio score is in fact higher; the two are
complementary). Outcome 1 (continue as research) is rejected (no important, bounded, remaining gap; the
distinct piece is done; the field is crowded). Outcome 4 (stop) is rejected (the work is rigorous,
reproducible, and a clean replication). **Increment analysis (16.3A) is downgraded to optional** — it
would be further replication, not a distinct contribution.

## 2. Audit scope and search methodology

Live web search (June 2026) across five categories + targeted candidate searches; **9 repositories
shallow-cloned and inspected at source level** (no checkpoints/datasets downloaded); full-paper text
inspected for AKM (ar5iv) and ChessMimic (arXiv); abstract/methods-level for Maia-2, the Time-Pressure-
&-Skill study, Barthelemy, and the CNN-LSTM rating paper. Saturation: repeated queries returned the same
core sources, and the §C decisive-capability grep returned 0 across every clone. Appendix lists queries,
repos, commits, files, and the per-source evidence tier.

## 3. Chess-MHSUC component inventory

Data engineering: PGN ingestion, clock parsing (`[%clk]`), rating extraction, player hashing, board
reconstruction, move-number/phase, termination parsing, dense per-ply Parquet, multi-month + multi-TC
sampling. Engine: Stockfish pre/post-move eval, CP loss, clipped CP loss, expected-score loss, large-loss
probability, MultiPV fragility/sharpness. Behavior: outcome modeling + move-quality modeling (NOT human
move prediction). Statistics: board+rating-controlled outcome ablation, clock residual, termination
decomposition, player-side timeout attribution, board-decided-only analysis, cross-control comparison,
rating×clock + TC×clock interactions, phase/eval localization, cross-month replication, game-normalized
weighting, game/mover-player clustered bootstrap, Holm. Visuals: move quality vs seconds/clock-fraction/
move-number, rating-bin/percentile curves, TC comparisons, heatmaps, termination plots, phase/eval-
conditioned curves.

## 4. Sources and repositories inspected

**Repositories cloned + inspected at source level [SV]** (all under `/Users/malachiwang/chess-prior-art/`,
none inside the repo):

| # | Repo | Commit | Date | License | What it is | Termination decomp / board-decided / timeout-attribution |
|---|---|---|---|---|---|---|
| 1 | ianfab/chess-analysis | 4375c3c | 2023-02-02 | AGPL-3.0 | ACPL/EV/EL move-quality metric tool | no (0 grep) |
| 2 | CSSLab/maia2 | 16c1383 | 2025-07-23 | MIT | human move predictor (skill embedding) | no |
| 3 | marcusbuffett/oxi | 97c674b | 2026-06-24 | **none** | human move predictor (Rust/Burn), ECL calibration | no |
| 4 | CSSLab/maia-chess | 749204c | 2026-05-24 | GPL-3.0 | Maia / Maia-3 move predictor + blunder_prediction | termination parsed as metadata only |
| 5 | ippolito-cmu/allie | a50f2d8 | 2025-11-14 | MIT | generative move/time/outcome predictor (Allie) | termination-*aware* token; no decomposition |
| 6 | Time-Management-…-Human-Data (TillmannRheude) | 22b75a8 | 2021-10-28 | MIT | NN think-time predictor | no |
| 7 | trbarron/Chess-Bidding-Analysis | 956a1c8 | 2025-10-27 | **none** | Armageddon bid analysis | no |
| 8 | bleongcw/Arrakis_Engine | 8e5725e | 2026-06-23 | AGPL-3.0 | Stockfish+LLM coaching app | no |

**Papers inspected at full text [PV]:** Anderson–Kleinberg–Mullainathan (ar5iv 1606.04956); ChessMimic
(arXiv 2606.04473). **Abstract/methods-level [SO/PV]:** "Time Pressure, Skill, and Move Quality in
Chess" (ResearchGate 272548799, 403 on full text → abstract-verified); Maia-2 (2409.20553); Barthelemy
variation entropy (2505.03251); CNN-LSTM rating-from-clock (2409.11506); Allie paper "Human-aligned
Chess with a Bit of Search" (2410.03893); jk_182 Lichess blog (project citation).

## 5. Repository and license inventory

| Repo | License | Class | Reuse status |
|---|---|---|---|
| ianfab/chess-analysis | AGPL-3.0 | copyleft/reciprocal | **reference-only** (copying imposes AGPL) |
| maia-chess | GPL-3.0 | copyleft/reciprocal | reference-only |
| Arrakis_Engine | AGPL-3.0 | copyleft/reciprocal | reference-only |
| oxi | **no license** | no license found | **reference-only by default** (no grant) |
| Chess-Bidding-Analysis | **no license** | no license found | reference-only by default |
| maia2 | MIT | permissive | reusable (but a predictor; not this project's estimand) |
| allie | MIT | permissive | reusable (predictor; not this estimand) |
| Time-Management-…-Human-Data | MIT | permissive | reusable (think-time predictor) |

Two repos (oxi, Chess-Bidding-Analysis) have **no license file** → must be treated as reference-only
absent explicit permission. The three closest metric/tool repos (ianfab AGPL, maia-chess GPL, Arrakis
AGPL) are copyleft → reference-only. No large datasets/checkpoints downloaded.

## 6. Full capability comparison matrix (revised)

Legend: ✓ present · ~ partial/feature-only · ✗ absent. [SV] unless noted.

| Capability | chess-MHSUC | ianfab | maia2 | oxi | maia-chess | allie | TimeMgmt | ChessMimic[PV] | AKM[PV] | TimePress-Skill[SO] | Barthelemy[SO] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PGN ingestion | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Clock parsing (`%clk`) | ✓ | ✗ | ~filter | ✓ | ✓ | ✓ | ✓ | ✓ | ~time remaining | ~ | ✗ |
| Increment-aware think time | ✓ | ✗ | ✗ | ✓ | ~ | ✓ | ✓ | ✓ (think-time model) | ✗ | ✗ | ✗ |
| Remaining clock as **fraction** | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ (raw) | ✗ | ✗ | ✗ |
| Rating conditioning | quintile/pctile/bins | raw bins | embedding | bins | bins | bins | ~ | per-100-Elo bands | single Elo | skill groups | ✗ |
| Time-control conditioning | 3 matched | ✗ | filter | ✓ | ✗ | ✓ (v2) | ~ | ✓ (input) | 3-min only | bullet/blitz/rapid | ✗ |
| Increment support | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ (v2) | ~ | ✗ | ✗ | ✗ | ✗ |
| Stockfish/engine eval | ✓ | ✓ | NN | ✓ (ECL) | ✓ (CP CSV) | ✓ (CP eval) | ✗ | ✗ | tablebase | ✓ | ✓ MultiPV |
| Move-quality metric | ES loss/clipped CP/large-loss | EV/EL/capped CPL | ACPL+blunder | ECL+blunder | CP | CP loss (model) | ✗ | ✗ (accuracy only) | blunder(minimax) | CPL/blunder | ✗ |
| Human move prediction | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ |
| Time-usage prediction | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Outcome prediction | ✓ (+clock ablation) | ✗ | ✗ | ~value | ✗ | ✓ | ✗ | ✓ (+clock+TC) | ✗ | ✗ | ✗ |
| Termination parsing | ✓ | ✗ | ✗ | ✗ | ~metadata | ~token | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Time-forfeit channel decomposition** | **✓** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Board-decided restriction** | **✓** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Player-side timeout attribution** | **✓** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Move-number analysis | ✓ | ✓ (ply) | ✗ | ~ | ✗ | ✗ | ~ | ✗ | ~ | ~ | ✗ |
| Phase conditioning | ✓ | via ply | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | endgame only | ✗ | ✗ |
| Eval-state conditioning | ✓ | ✓ (cp) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ~difficulty | ✗ | ✓ |
| Sharpness/complexity | MultiPV fragility | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | blunder-potential | ✗ | ✓ entropy/gap |
| Rating × clock interaction | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ (rating×time) | ✗ |
| TC × clock interaction | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ~ | ✗ |
| Cross-month replication | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Cross-control replication | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ~ | ✗ |
| Game/player clustering | ✓ | per-player agg | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Multiple-testing control (Holm) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Visual atlas | matplotlib atlases | df+mpl | ✗ | charts | ✗ | ✗ | plots | demo | paper figs | paper figs | paper figs |

The **time-forfeit decomposition / board-decided / player-side-timeout** rows are ✓ for chess-MHSUC and
✗ for every inspected source. Everything else is matched by at least one source.

## 7. Commodity engineering

Must not be presented as contributions (each verified in ≥1 source): PGN ingestion; **clock parsing +
increment-aware think time** (`oxi/pgn_processor.rs` parses `[%clk]`, `MIN_CLOCK_TIME` filter,
`prev_clock − clock + increment` [SV]; `maia2/utils.py` `extract_clock_time` [SV]); rating/eval/ply
conditioning (`ianfab/stats.py` groupby elo/ply/cp [SV]); **expected-score / expected-loss / capped CPL**
(`ianfab` EV/EL + capped CPL [SV]; `oxi` ECL [SV]; `allie` centipawn-loss [SV]); large-loss/blunder rate;
game/player clustering and Holm (standard statistics); matplotlib plotting.

## 8. Reimplemented prior work

- **Move-quality metric design** (expected-score/expected-loss, capping, normalize-by-potential-loss,
  equal-weighting, "ACPL over-weights single moves / correlates with game length") = independent
  reimplementation of `ianfab/chess-analysis` [SV] (AGPL, 2023). Same rationale, near point-for-point.
- **Sharpness / MultiPV fragility** = reimplementation/extension of Barthelemy variation entropy [SO] and
  AKM's "blunder potential" (good-moves/legal-moves) [PV]. C3c unresolved → no validated novel result.
- **Clock→blunder gradient** = reimplementation/extension of AKM's "empirical blunder rate as a function
  of time remaining" [PV] (AKM: 3-min FICS, tablebase endgame; project: Stockfish all-phase, multi-TC).

## 9. Replication contributions

- **T3 within-control clock gradient** (lower clock → higher loss): replicates AKM [PV] with a different
  ground truth (Stockfish all-phase vs 6-piece tablebase), metric (ES loss vs minimax blunder), and added
  cross-month replication + clustering.
- **Cross-control gradients (T4)** + **RM1 rating gradient**: replicate the Time-Pressure-&-Skill
  literature [SO] (faster→worse, skill interacts) and Maia-2's monotone ACPL-by-skill [SO], with stronger
  methodology.

## 10. Extension contributions

- **Methodological package**: game-normalized weighting + game/mover-player-clustered bootstrap +
  cross-month replication + Holm + board-decided robustness + normalized `clock_fraction` axis applied to
  the clock/move-quality question — a real rigor extension over the descriptive/blog/predictor prior work
  (none of the 8 clones implements clustering or Holm; grep = 0).
- **RM2 rating × clock conditioning-sensitivity**: the rating×time interaction is established (Time-
  Pressure-&-Skill [SO]); the *sign-instability-under-phase/eval-localization* observation is an
  apparently-distinct cautionary note that resolves to a **null** ("no universal direction").

## 11. Candidate distinct contributions

**The termination-channel decomposition + board-decided-only move quality + player-side timeout
attribution.** Now source-verified against the closest clock-aware repos: ChessMimic [PV] predicts
outcomes from position+rating+TC+clock but does not parse termination, separate timeout, analyze move
quality, or use an engine; Allie [SV] is termination-*aware* (a `<RESIGNED-OR-CHECKMATED>` token) and
computes its own policy's centipawn loss, but performs no outcome-by-termination decomposition, no
board-decided-only empirical analysis, and no timeout attribution; Maia [SV] stores termination as a
metadata column only; Oxi [SV] uses clock+ECL as predictor features/metrics. AKM [PV] uses time-remaining
but no termination split. **Verdict: apparently distinct within the inspected sources — modest in
importance, already implemented.**

## 12. Candidate A kill test — termination decomposition (revised)

Per-source answers to the eight sub-questions (board-eval control / strength control / remaining clock /
predict outcomes / parse timeout / separate timeout-vs-board-decided / move quality after excluding
timeouts / player-side timeout attribution):

| Source | board-eval | strength | clock | outcome | parse timeout | TF vs board split | MQ excl. timeout | player-side attrib |
|---|---|---|---|---|---|---|---|---|
| ChessMimic [PV] | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Allie [SV] | ✓(model CP) | ✓ | ✓ | ✓ | ~aware | ✗ | ✗ | ✗ |
| Maia/Maia-2/3 [SV] | ✗ | ✓ | ~filter | ✗ | ~metadata | ✗ | ✗ | ✗ |
| Oxi [SV] | ✓(ECL) | ✓ | ✓ | ~value | ✗ | ✗ | ✗ | ✗ |
| AKM [PV] | ✓(tablebase) | ✓ | ✓ | ✗(blunder) | ✗ | ✗ | ✗ | ✗ |
| ianfab [SV] | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

No inspected source has all of {timeout parse + TF-vs-board split + board-decided-only move quality +
player-side attribution}. The closest (ChessMimic, Allie) condition outcome on clock or are
termination-aware but do not decompose. **Verdict: apparently distinct** (much stronger than the 2-repo
version). Caveat: still not an absence proof; importance modest (the folk observation "fast-chess results
are heavily flagging" is well known, but no inspected source formalizes the decomposition under
position+rating control).

## 13. Candidate B kill test — replicated cross-control gradients (revised)

Required combination: normalized remaining time + multiple TCs + move-quality outcome + rating/position
controls + independent-sample replication + board-decided restriction + player/game-clustered uncertainty.
**Findings:** AKM [PV] has clock→blunder + rating + difficulty control but single TC (3-min), no
replication/clustering, no board-decided split. Time-Pressure-&-Skill [SO] has rating×TC move quality but
no clustering/board-decided/normalized-clock. ChessMimic [PV] has multi-TC + clock but predicts (no move
quality, no clustering). **Verdict: mostly done (the association) + method-extension (the clustering /
replication / board-decided / normalized-clock package is not matched by any inspected source).** The
scientific claim is replication; the rigor is the extension.

## 14. Candidate C kill test — rating-moderation instability (revised)

Required: rating × remaining-time interaction + move-quality target + phase/move-number-specific +
eval-state localization + sign reversal/heterogeneity. **Findings:** Time-Pressure-&-Skill [SO]
establishes the rating × time-pressure interaction on move quality (weaker degrade more). The project's
specific *sign-instability under phase/eval localization* was not found as such, but it resolves to a
**null** ("no universal direction, no mechanism"). **Verdict: partial overlap / apparently-distinct-but-
fragile-null** — low standalone value; correctly reported by the project as cautionary, not a result.

## 15. Visualization-code overlap (revised)

`ianfab/chess-analysis/stats.py` [SV] aggregates move quality by **rating range, ply (move number), and
current evaluation** (the project's rating-bin, move-number, eval-band panels), output as pandas tables
(matplotlib is a dependency). `oxi` [SV] has `gen_chart.py` / `metrics_renderer.rs` (training/eval
charts, not human move-quality-vs-clock). No inspected repo plots move-quality-vs-**clock-fraction**,
time-control-overlaid curves, termination-rate-by-control, board-decided-only curves, or player-side-
timeout-by-rating (decisive-capability grep = 0). **Answer to the guiding question:** the rating ×
move-number × eval panels are conceptually adaptable from `ianfab` (AGPL → do not copy); the clock-
fraction / termination / board-decided views are the project's own; the plotting stack is commodity
matplotlib. No reuse warranted.

| Source file | function/script | input cols | plot type | license | adaptation to Parquets |
|---|---|---|---|---|---|
| ianfab/chess-analysis stats.py | groupby elo/ply/cp → `.agg` | elo, ply, ce, ce2, result | pandas tables (mpl dep) | AGPL-3.0 | low concept / **AGPL blocks copy** |
| oxi gen_chart.py / metrics_renderer.rs | training/eval charts | model metrics | training charts | none | n/a (model-internal) |
| hobbyist viz repos [SO] | various | PGN→CSV | blunder/move-by-rating | varies | low value, not clock-fraction |

## 16. Reusable code and licensing (revised)

- AGPL/GPL (ianfab, maia-chess, Arrakis) and no-license (oxi, Chess-Bidding) → **reference-only**; do not
  copy. The project already reimplemented the equivalent metric/clock logic independently → leave
  `chess-MHSUC` unchanged.
- MIT (maia2, allie, Time-Management) → permissively reusable, but all three are predictors/think-time
  models — not aligned with the project's descriptive estimands. No reuse warranted.
- Migration cost (copyleft contamination, schema mismatch, loss of 1,925-test coverage + deterministic
  pipeline) exceeds value. **Retain existing implementations; cite ianfab (metrics), AKM and the
  time-pressure literature (clock→error), Barthelemy (sharpness), Maia/Allie/ChessMimic (the prediction
  context the project does NOT compete with).**

## 17. What should not be claimed

The metric design; rating/phase/eval/move-number conditioning; "clock improves outcome prediction";
"lower clock → more error/blunder" (AKM did blunder-rate-vs-time-remaining); faster controls → more
error; rating × time-pressure interaction; sharpness/MultiPV-fragility as a validated result; any
"novel/first/unique/SOTA/best predictor".

## 18. What can still be claimed (defensibly)

- "No equivalent termination-channel decomposition (time-forfeit vs board-decided under position +
  rating control) with board-decided-only move-quality analysis and a validated player-side timeout
  denominator was found in the inspected sources (9 repos at source + AKM/ChessMimic full text)" —
  apparently distinct, descriptive, modest.
- "A rigorous replication and cross-control extension of the clock/move-quality relationship (AKM;
  time-pressure-&-skill literature) with game-normalized weighting, game/player-clustered uncertainty,
  cross-month replication, board-decided robustness, and Holm-controlled contrasts."
- "The apparent direction of rating × clock moderation is not stable under phase/evaluation localization
  (cautionary; no universal direction; no mechanism identified)."
- Engineering/reproducibility (deterministic pipeline, 1,925 tests, preregistration, clustered
  uncertainty, leakage-aware splitting).

## 19. Research-value assessment

The only apparently-distinct element (termination decomposition) is modest and already done; the
headline results replicate AKM and the time-pressure literature or resolve to nulls (RM2/RM3). No
*important, bounded, remaining* research task would materially raise the contribution; the field of
clock/rating-aware chess modeling is crowded (Maia/Maia-2/Maia-3, Oxi, Allie, ChessMimic). Research-
continuation value is **low-to-moderate**.

**Scoring rubric (0–5; explanations follow; no false precision):**

| Category | Score | Why |
|---|---|---|
| Originality | 2 | one apparently-distinct decomposition; metric/conditioning/cross-control/clock-gradient all have prior art (incl. AKM clock→blunder) |
| Importance | 2 | the distinct piece is a modest clarification, not a major gap |
| Technical quality | 4 | clustering, replication, weighting, Holm, preregistration — rigorous |
| Reproducibility | 5 | 1,925 tests, deterministic CLIs, reports, frozen transform, preregistration |
| Interpretability | 4 | claims clearly stated and heavily caveated |
| Publication potential | 2 | short replication/benchmark note at best; not a method/novelty paper |
| Portfolio value | 4 | strong (scored fully in §20) |
| Remaining cost (reverse: lower remaining effort → higher) | 2 | continuing *as research* is unbounded mechanism-seeking |

**Research continuation score ≈ 21 / 40.** High reproducibility/technical quality do not rescue low
originality/importance/publication for a *research-continuation* decision.

## 20. Portfolio-value assessment

High. Large-scale PGN→dense-Parquet engineering across months and time controls; disciplined Stockfish
evaluation; a correct, well-tested statistics layer (sufficient-statistic clustered bootstrap, Holm,
game-normalized weighting); preregistration and ruthless claim discipline; ~1,925 passing tests;
reproducible deterministic CLIs/reports.

| Category | Score | Why |
|---|---|---|
| Originality | 2 | recorded honestly; not the portfolio axis |
| Importance | 3 | intelligible, well-motivated questions even where replication |
| Technical quality | 4 | correct, non-trivial statistics + engineering |
| Reproducibility | 5 | deterministic, tested, documented end-to-end |
| Interpretability | 4 | clear narrative, explicit non-claims |
| Publication potential | 2 | low, not the portfolio axis |
| Portfolio value | 5 | exactly the rigor/scale/discipline recruiters value |
| Remaining cost (reverse: retention needs ~no further effort) | 5 | value already realized |

**Portfolio retention score ≈ 30 / 40.** Portfolio (≈30) > research continuation (≈21).

## 21. Migration / reuse options

Retain all existing implementations unchanged (no replacement). Add prior-art citations (ianfab for
metrics; AKM and the time-pressure literature for clock→error; Barthelemy for sharpness; Maia/Allie/
ChessMimic for the human-prediction context the project deliberately does not compete with). No
third-party code enters the repo; copyleft/no-license repos stay reference-only.

## 22. Continue / reframe / archive / stop decision (independently reassessed)

All four outcomes were re-evaluated against the expanded evidence (not preserved from the prior pass):
- **Outcome 1 (continue as research): rejected.** No important, bounded, remaining gap; the distinct
  piece is done; AKM/ChessMimic/Allie/Oxi/Maia show the surrounding space is crowded.
- **Outcome 2 (reframe as replication/benchmark): PRIMARY.** The project is a rigorous replication of
  AKM's clock→error and the time-pressure-&-skill interaction, a cross-control extension, and one
  apparently-distinct clarifying decomposition (termination channel). This is exactly "broad methods/
  claims exist; the project adds stronger replication/decomposition/robustness; still scientifically
  useful." Useful but modest.
- **Outcome 3 (retain as portfolio engineering): SECONDARY (higher score).** The engineering/reproducibility
  is excellent (≈30/40 vs ≈21/40). If there is no appetite for a short writeup, the decision collapses
  cleanly to Outcome 3.
- **Outcome 4 (stop): rejected.** The work is rigorous, reproducible, and a clean replication — not pure
  sunk cost.

The expanded review **confirmed** Outcome 2 as primary (strengthening the termination-decomposition
evidence) while making explicit that the portfolio framing (Outcome 3) scores higher and is complementary.

## 23. Exact recommended next action

Pivot from "more analysis" to **honest packaging**: a short replication/benchmark writeup (or portfolio
report) framed as **"a rigorous replication and cross-control extension of clock/move-quality
relationships in online chess, plus a clarifying termination-channel decomposition,"** with explicit
prior-art positioning (ianfab/chess-analysis; Anderson–Kleinberg–Mullainathan; Time-Pressure-&-Skill;
Maia/Allie/ChessMimic; Barthelemy). **Downgrade increment analysis (16.3A) to optional** (further
replication). This is a Phase-17-style packaging pivot. No follow-up action is started in this ticket.

## 24. Evidence gaps and open questions

- Absence is not proven: a dedicated flagging-risk/time-forfeit-prediction paper could exist under other
  terminology (time scramble, esports forfeit); the candidate-A queries returned only rules/forums [U].
- ChessMimic and Allie code: ChessMimic repo URL not resolved from the arXiv page [U] (paper-verified
  only); Allie v2 (`y0mingzhang/chess-v2`, "all time controls") not cloned [U].
- Time-Pressure-&-Skill full text was 403 (abstract-verified [SO], not [PV]).
- Hobbyist visualization repos assessed from search summaries [SO], not all cloned.
- Maia-3 (in maia-chess [SV]) checkpoints/paper not inspected at result level (out of scope).

---

## Appendix — search queries, repos, commits, files, evidence tiers

**Web search queries (June 2026):** (1) AKM time pressure centipawn; (2) time-forfeit flagging prediction
timeout vs board-decided; (3) Maia clock/time-control conditioned prediction; (4) move quality centipawn
vs clock rating Lichess; (5) time-pressure blunder probability clock fraction; (6) bullet/blitz/rapid
ACPL comparison; (7) outcome prediction board-eval + clock ablation + forfeit decomposition; (8) github
move-quality vs time-remaining rating-bin viz; (9) MultiPV entropy best-second gap complexity; (10)
Maia-2/ChessMimic/Allie clock-aware prediction; (11) board-decided-only / who-flagged timeout attribution;
(12) ChessMimic 2606.04473 github.

**Repositories cloned (shallow, under /Users/malachiwang/chess-prior-art/, none inside chess-MHSUC):**
1. ianfab/chess-analysis `4375c3c` (2023-02-02) AGPL-3.0 — README, LICENSE, requirements.txt, stats.py,
   common.py, analyze.py, pgn2epd.py — EV/EL + capped CPL + groupby elo/ply/cp; grep clock/time/termination = 0. [SV]
2. CSSLab/maia2 `16c1383` (2025-07-23) MIT — main.py, utils.py (`extract_clock_time` `[%clk]`), dataset.py
   (board/move/active_elo/opponent_elo); clock = filter; no termination. [SV]
3. marcusbuffett/oxi `97c674b` (2026-06-24) **no license** — README, Cargo.toml, src/pgn_processor.rs
   (`[%clk]`+MIN_CLOCK+increment think time), src/eval_dataset.rs (ECL+blunder rate of model), config.rs
   (centipawn-loss-calibration); "timeout" = training wall-clock; no termination decomposition. [SV]
4. CSSLab/maia-chess `749204c` (2026-05-24) GPL-3.0 — blunder_prediction/…/utils.py (termination as a
   stored field), data_generators/pgnCPsToCSV_multi.py (`game.headers['Termination']` column); Maia/Maia-3
   move predictor; no decomposition. [SV]
5. ippolito-cmu/allie `a50f2d8` (2025-11-14) MIT — src/modeling/data.py (`normal_termination`,
   `<RESIGNED-OR-CHECKMATED>` token), src/evaluation/evaluate.py (`compute_centipawn_loss_and_accuracy`,
   model-resigned/white-advantage); termination-aware generative predictor; no decomposition/attribution. [SV]
6. TillmannRheude/Time-Management-…-Human-Data `22b75a8` (2021-10-28) MIT — NN think-time predictor;
   termination grep = 0. [SV]
7. trbarron/Chess-Bidding-Analysis `956a1c8` (2025-10-27) **no license** — Armageddon bid analysis;
   termination/decomposition grep = 0. [SV]
8. bleongcw/Arrakis_Engine `8e5725e` (2026-06-23) AGPL-3.0 — Stockfish+LLM coaching app; no analysis
   decomposition. [SV]

Decisive-capability grep (board-decided / timeout-exclusion / player-side-timeout / clock-fraction /
expected-score-loss) across all 8 clones = **0 files each**.

**Papers:** AKM ar5iv 1606.04956 [PV] (target blunder; uses time-remaining; tablebase; no termination
split; difficulty > skill > time); ChessMimic arXiv 2606.04473 [PV] (move/think-time/outcome prediction;
outcome conditions on pos+rating+TC+clock; per-100-Elo bands; NO termination parse/split, NO move quality,
NO engine); Time-Pressure-&-Skill [SO] (rating × time-pressure: weaker degrade more); Maia-2 [SO]
(monotone ACPL/blunder by skill); Barthelemy 2505.03251 [SO] (variation entropy / best-2nd gap); CNN-LSTM
2409.11506 [SO] (rating from moves+clock).

**Sources rejected:** chess.com/uschess/chessworld timeout *rules* pages (not analysis); ACPL calculators
/ accuracy-by-rating blogs (commodity); Chess960 complexity (2512.14319, different scope); neural look-
ahead/representation papers (engine internals); Arrakis/coaching apps (tooling, not analysis).
