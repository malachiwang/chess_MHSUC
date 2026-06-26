# Phase 17.0A — Replication/Benchmark Reframing and Public Packaging Audit

**Ticket:** 17.0A — Replication/Benchmark Reframing and Public Packaging Audit (documentation /
narrative-design / visualization-selection / packaging audit only)
**Status:** complete — audit only. No models, no Stockfish, no extraction, no Parquet/JSON/model/figure
modified, no third-party source copied. Read-only inspection + design.

> Claim discipline: cautious replication/benchmark language only. Uses "no equivalent analysis was found
> in the directly inspected sources." Does NOT use "first", "first-ever", "novel", "unique",
> "unprecedented", "no one has done this", "state of the art".

## 1. Executive recommendation

Convert `chess-MHSUC` into an **honest, technically strong replication/benchmark + portfolio artifact**,
anchored by the apparently-distinct termination-channel decomposition. The science is settled; the
remaining work is **packaging**, not analysis. Two decisive feasibility findings:
1. **All fields the headline figures need already exist in the six dense Parquets** (`clock_before_s` =
   actual seconds, `move_number`, `clock_fraction`, `expected_score_loss`, `cp_loss_clipped`,
   `is_time_forfeit`/`termination`, `mover_elo`, `eval_band`, `phase`, `time_control_raw`, `month`,
   `initial_time_s`, `mover_player_hash`). **17.0B requires NO new extraction and NO Stockfish** — read
   Parquets, aggregate, plot.
2. **The current 19-figure suite is clock-fraction-based with no actual-seconds, no move-number, and no
   move-number×clock-heatmap views** — exactly the inadequacy Malachi flagged. The headline set needs 4
   new figures (actual-seconds + move-number axes) plus 2 adapted from existing figures.

**Recommended next ticket: 17.0B — Replication/Benchmark Public Package Implementation** (bounded:
rewrite README, write a concise benchmark report, generate 6 approved headline figures + an appendix
index from existing Parquets, add related-work + reproducibility, update governance). Increment analysis
and all new modeling stay deferred.

## 2. Evidence reviewed

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; 16.2G prior-art/decision audit; 16.2F and 16.2C consolidations;
the cross-time-control and rating-clock main reports; the Phase-11 termination-decomposition lineage
(`phase_11_2a/b`, `termination_decomposition_{2024_09,2024_10,combined}.md`,
`player_clustered_termination_decomposition.md`); the current `README.md` (157 lines — describes the OLD
private-first 10+0 outcome-prediction framing, now stale) and `requirements.txt` (no LICENSE/CITATION
present); the 19 existing Phase-16 figures (listed in §6); a read-only schema check of the dense Parquet
(65 cols, all headline fields present).

## 3. Final project identity

**Top-level framing (LOCKED):** "A reproducible replication and benchmark study of human move quality and
clock constraints in online chess, with an explicit decomposition of mechanical time-forfeit risk versus
board-play quality."

**Secondary framing:** "A large-scale data-engineering and statistical-modeling project covering 145,000+
games, 8M+ move-level observations, 3 time controls, 2 independent months, clustered uncertainty, and
extensive robustness analysis."

**Apparently-distinct empirical component:** "Separating the clock-related final-outcome signal into
time-forfeit and board-decided channels, then comparing it with next-move quality among board-decided
games." (No equivalent analysis was found in the directly inspected sources — 16.2G.)

The project must NO LONGER be framed as a novel modeling framework, a new expected-score-loss method, a
new rating/time analysis, a new human move predictor, a new difficulty framework, or SOTA.

## 4. Public claim hierarchy

**Level 1 — Headline finding:** "Clock information in online chess reflects two distinct channels: a
dominant mechanical time-forfeit channel for final outcomes, and a smaller association with next-move
quality that remains in board-decided games." Qualifications: predictive/descriptive, not causal; not a
reasoning-degradation claim; Stockfish = objective context, not ground truth; no equivalent decomposition
found in inspected prior work. (Backing: termination_decomposition_combined — board-decided residual
+0.0010 [CI∋0] / +0.0060 Sep/Oct; time-forfeit −0.118 / −0.131.)

**Level 2 — Replicated benchmark findings:** time-forfeit prevalence much higher in faster controls (3+0
~0.29–0.30 > 5+0 ~0.23 > 10+0 ~0.12, game-level); lower remaining clock → greater next-move ES loss;
the conditional low-clock gradient is steeper in faster controls; the gradient shrinks but stays positive
board-decided; replicates across Sep/Oct 2024; headline clock gradients survive mover-player clustering.
Framed as rigorous replication/extension (cf. AKM "blunder rate vs time remaining"; time-pressure-&-skill
literature), not novelty.

**Level 3 — Cautionary/secondary:** average ES loss broadly similar across controls (no equivalence
test); relative rating interacts with the low-clock gradient but the direction changes under phase/eval
localization; rating moderation does not clearly differ across controls; sharpness moderation unresolved.

## 5. Analyses to retain, demote, or omit

| Analysis | Final role | Reason |
|---|---|---|
| Termination decomposition (TF vs board-decided) | **Headline** | Apparently distinct, interpretable, the anchor |
| Board-decided-only move-quality analysis | **Headline** | Separates mechanical vs board-play channels |
| Cross-control clock gradients (T3/T4) | **Main replication** | Strong, replicated, cluster-robust |
| Average move-quality comparison (T2) | **Supporting** | Descriptive; explicitly not equivalence |
| Rating × clock moderation (RM2) | **Secondary/cautionary** | Conditioning-sensitive; no universal direction |
| Cross-control rating moderation (RM3) | **Secondary** | Null/unsupported |
| Player-side timeout gradient (RM5) | **Secondary** | Weak descriptive |
| Rating-bin average gradient (RM1) | **Supporting/appendix** | Established positive control |
| Sharpness / MultiPV fragility (C3c) | **Appendix or omit** | Unresolved; reimpl of prior complexity work |
| Outcome-prediction ablation (E3→E4) | **Methods/history** | Lineage to the decomposition, not a public headline |
| Increment work | **Deferred** | Out of scope; would be further replication |

Analyses are not retained merely because they took effort (sharpness, the controlled-interaction figures,
the full Q1–Q5 grids all move to appendix/omit).

## 6. Current figure audit

19 existing figures, every one **clock-fraction-based** (no actual-seconds axis), with no move-number
figure and no move-number×clock heatmap. Per-figure status:

**`reports/figures/phase_16_2_cross_time_control/` (16.2B):**

| Figure | Status | Reason |
|---|---|---|
| 01 clock_fraction × ES by control | **appendix only** | superseded by actual-seconds H3 |
| 02 clock_fraction × clipped CP | **appendix only** | secondary metric |
| 03 large-loss probability | **appendix only** | secondary metric |
| 04 game-level termination rate by control | **retain after caption/title revision** | becomes **H1** |
| 05 board-decided clock_fraction × ES | **replace** | feeds H2 but needs all-games-vs-board-decided overlaid + actual seconds |
| 06 rating × clock heatmap | **appendix only** | H5 instead is move-number × actual-clock |
| 07 eval-band × clock | **appendix only** | localization detail |
| 08 phase × clock | **appendix only** | localization detail |
| 09 controlled clock interactions | **appendix only** | technical coefficients |
| 10 month replication summary | **retain after caption revision** | feeds **H6** |

**`reports/figures/phase_16_2_rating_clock_moderation/` (16.2E):**

| Figure | Status | Reason |
|---|---|---|
| 01 clock × ES by rating quintile | **replace** | H3 needs actual seconds + absolute-Elo legends |
| 02 critical-clock contrast by quintile | **appendix only** | technical contrast |
| 03 rating × clock heatmap | **appendix only** | superseded by H5 |
| 04 board-decided moderation | **appendix only** | secondary |
| 05 within-control rating moderation M(c) | **appendix only** | technical |
| 06 cross-control rating moderation | **appendix only** | null result, technical |
| 07 player-side time-forfeit by rating | **retain after caption revision** | secondary RM5 panel |
| 08 endgame-only moderation | **appendix only** | localization |
| 09 month replication (rating) | **discard** | duplicates 16.2B-10 scope |

Summary: **retain-with-revision 3** (16.2B-04→H1, 16.2B-10→H6, 16.2E-07 secondary); **replace 2** (feed
H2/H3); **appendix-only 13**; **discard 1**. None modified in this ticket.

## 7. Headline visualization specification

Six headline figures, all generated from existing Parquets (no Stockfish/extraction). Non-causal captions;
readable at README width; absolute Elo in legends where rating appears; all-games vs board-decided always
distinguishable; actual seconds where seconds matter.

- **H1 — Time-forfeit prevalence by time control** (game-level, both months). *Adapt 16.2B-04.* Bars/points
  3+0/5+0/10+0 × Sep/Oct. Purpose: establish the mechanical termination-channel difference.
- **H2 — All-games vs board-decided clock gradient** (NEW). x = actual seconds remaining (`clock_before_s`,
  capped to [0, initial_time_s]); y = mean ES loss; two lines (all games, board-decided); panel per
  control; provide a clock_fraction twin in appendix. Purpose: removing timeout games attenuates but does
  not eliminate the association.
- **H3 — Move quality vs actual seconds remaining by rating group** (NEW). Panels per control; lines = Q1/
  Q3/Q5 with **absolute Elo ranges in the legend** (e.g. 3+0 Q1 ≤1495, Q5 ≥2053) or raw 200-Elo bins where
  powered; control-appropriate second bins or a defensible smoother. Purpose: how observed move quality
  changes as actual clock declines.
- **H4 — Move quality vs move number** (NEW). Panels per control × a selected rating group; x = move_number;
  lines = clock state (high/medium/low/critical from `clock_fraction` coarse buckets). Purpose: where in
  the game the low-clock association emerges.
- **H5 — Move-number × actual-clock heatmap** (NEW). ≥1 heatmap per control; color = mean ES loss; x =
  move_number bins, y = actual-seconds bins. Purpose: the joint move-number/remaining-time danger region.
- **H6 — Month replication summary** (adapt 16.2B-10). Sep/Oct/pooled for the headline clock contrasts
  (and the board-decided headline). Purpose: not a one-sample artifact.

Headline set = **6 figures** (2 adapted, 4 new). Each answers one distinct question.

## 8. Technical appendix visualization specification

Indexed, not compressed into one figure: full Q1–Q5 rating curves; all raw 200-Elo-bin curves; board-
decided versions of each headline; endgame-restricted versions; eval-state-localized versions; clipped-CP
versions; large-loss probability; player-side timeout prevalence by rating (16.2E-07); rating-moderation
contrasts (16.2E-02/04/05/06/08); clustered-uncertainty comparisons; the existing 16.2B-01/02/03/06/07/08/
09 and 16.2E-01/03 as the fraction-axis appendix. The 13 appendix-only existing figures are reused
as-is (linked from an appendix index), not regenerated, except where a caption revision is cheap.

## 9. Existing-data and implementation feasibility

**Read-only schema check (dense Parquet, 65 cols):** all required fields present — `clock_before_s`
(actual seconds; 3+0 spans 0–1197s with known clock>initial anomalies → cap to [0, initial_time_s] and
note), `move_number` (5–223), `clock_fraction`, `expected_score_loss`, `cp_loss_clipped`,
`is_time_forfeit` (bool), `termination`, `mover_elo`, `eval_band`, `phase`, `time_control_raw`, `month`,
`initial_time_s`, `mover_player_hash`, `is_mate_band`, `status`.

| Question | Finding |
|---|---|
| Reusable aggregation functions | yes — `cross_time_control_analysis` (load/validate, headline population, buckets, quintiles, weights, game-cluster bootstrap) + `rating_clock_moderation` (percentile, raw-Elo bins, player-side table) [pure helpers, import only] |
| New model fitting required | **no** — headline figures are aggregations (means + game-cluster bootstrap CIs); no new OLS/interaction fits needed for figures |
| Plots from existing Parquets | **yes** — all six controls' Parquets already on disk |
| Actual-seconds field exists | **yes** (`clock_before_s`) |
| Move-number field exists | **yes** (`move_number`) |
| Additional Stockfish needed | **no** |
| Estimated runtime | minutes (read 6 Parquets ~8.4M headline rows, group-by aggregations + a few game-clustered bootstraps; ≪ the 16.2E modeling run) |
| Expected figure count | 6 headline + ~13 appendix (mostly reused existing) |

**Conclusion: implementation is authorized in scope — read existing Parquets, aggregate, plot. No
extraction or Stockfish. If, during 17.0B, any headline figure is found to need a field not on disk, STOP
and request approval rather than extracting.**

## 10. Public report structure

Compact public-facing benchmark report (`reports/benchmark_report.md` or similar), structure:

```
# Chess-MHSUC
## What this project studies
## What prior work already established
## What this project replicates
## The termination-channel decomposition   ← anchor
## Data
## Methods
## Headline results                        ← H1–H6
## Board-decided robustness
## Cross-time-control replication
## Rating and phase sensitivity
## Limitations
## Reproducibility
## Prior work and attribution
```

Lead with the decomposition and the replication; keep methods concise; defer technical detail to the
existing scientific reports (preserved unchanged).

## 11. README structure

First screen (above the fold): dataset scale (145K+ games, 8M+ moves, 3 controls, 2 months); the central
decomposition in one sentence; the non-causal boundary; links to the benchmark report and headline
figures. Then:

```
# Chess-MHSUC
## What this project studies            (1 paragraph + the decomposition)
## What prior work already established   (honest, links)
## What this project replicates
## The termination-channel decomposition
## Data
## Methods                               (concise; link to reports)
## Headline results                      (embed H1–H6 thumbnails)
## Board-decided robustness
## Cross-time-control replication
## Rating and phase sensitivity
## Limitations
## Reproducibility
## Prior work and attribution
```

The current README (private-first 10+0 outcome-prediction framing) is fully replaced in 17.0B. No giant
methodology dump at the top.

## 12. Prior-art positioning

Accurate, non-defensive related-work section. For each: what it did / what chess-MHSUC replicates / what
it extends / what it does NOT claim.

| Source | Did | chess-MHSUC replicates | extends | does NOT claim |
|---|---|---|---|---|
| ianfab/chess-analysis (AGPL) | EV/EL + capped CPL + rating/ply/eval conditioning | the metric design + conditioning | adds clock/TC/termination layer | a new metric |
| Anderson–Kleinberg–Mullainathan | blunder rate vs time remaining (tablebase, 3-min) | the clock→error gradient | Stockfish all-phase, multi-TC, clustering | a new error-prediction method |
| Time Pressure, Skill & Move Quality | rating × time-pressure on move quality | the interaction direction | clustering/replication/localization | a new interaction finding |
| Maia / Maia-2 / Maia-3 | rating-conditioned human move prediction | — (different task) | — | to predict human moves / beat Maia |
| ChessMimic | move/think-time/outcome prediction incl. clock | the outcome-clock observation | termination decomposition + move quality | a better predictor |
| Oxi | rating+clock human move predictor (ECL) | clock/ECL plumbing | — | move prediction |
| Allie | generative move/time/outcome, termination-aware token | termination awareness | explicit channel decomposition | a generative model |
| Time-management work | think-time prediction | — | — | think-time prediction |
| Barthelemy variation entropy | position complexity / best-2nd gap | the sharpness proxy idea | — (C3c unresolved) | a validated sharpness result |

State plainly: the project does not compete with the human-move-predictor field; it does descriptive
move-quality + outcome decomposition.

## 13. Resume and portfolio framing

**One-sentence:** "Built a reproducible 8M+ move analysis of human chess under clock constraints,
separating mechanical time-forfeit risk from board-play move-quality patterns across 145K+ games and 3
time controls, with clustered uncertainty and cross-month replication."

**Three resume bullets (verified numbers only):**
- Engineered a deterministic PGN→dense-Parquet pipeline over 145K+ Lichess games / 8.4M+ move-level
  observations across 3 time controls and 2 independent months, with leakage-aware splitting and ~1,925
  automated tests.
- Built a statistics layer (game-normalized weighting, game/mover-player sufficient-statistic clustered
  bootstrap, Holm multiplicity control) and decomposed the clock→outcome signal into time-forfeit vs
  board-decided channels — a decomposition not found in directly inspected prior work.
- Replicated and extended established clock/move-quality findings (cf. Anderson–Kleinberg–Mullainathan)
  across time controls with explicit non-causal, preregistered claim discipline.

**Interview (30s):** problem (does low clock mean worse chess, or just flagging?) → data (8M+ Lichess
moves, 3 controls, 2 months, Stockfish-evaluated) → method (decompose outcome signal by termination
channel; board-decided-only move quality; clustered uncertainty) → result (clock's outcome value is
mostly flagging; a smaller board-play association remains) → prior-art correction (the broad gradient was
known; the decomposition wasn't found in inspected sources) → engineering challenge (deterministic
8M-row pipeline + clustered bootstrap) → limitation (descriptive, not causal). **2-min:** expand each with
the cross-control replication, rating conditioning-sensitivity, and reproducibility. No novelty claims.

## 14. Reproducibility package

Add to the package (17.0B): a `LICENSE` (Malachi to choose — recommend permissive, e.g. MIT, since the
project copies no copyleft code) and `CITATION.cff`; `requirements.txt` already present (verify pins);
reproducibility instructions (PYTHONPATH=src, pytest, the figure-generation CLI reading existing
Parquets); a figure index mapping each figure → the report claim it supports → the source Parquet. Note
that dense Parquets are gitignored (data not shipped); reproduction needs the documented extraction
pipeline (already in the repo) — state this honestly.

## 15. Licensing and attribution

- Project code: recommend a permissive license (MIT) — the project copied no third-party source and
  reimplemented metrics independently; ianfab/chess-analysis (AGPL), maia-chess (GPL), Arrakis (AGPL),
  oxi/Chess-Bidding (no license) remain **reference-only, never copied**.
- Attribution: cite ianfab/chess-analysis, AKM, the time-pressure literature, Maia/Maia-2/Maia-3,
  ChessMimic, Oxi, Allie, Barthelemy in the related-work section (§12). No third-party code enters the
  repo.

## 16. Scope of Ticket 17.0B

**17.0B — Replication/Benchmark Public Package Implementation (bounded):**
- rewrite `README.md` (§11 structure);
- write a concise public benchmark report (§10 structure);
- generate the 6 approved headline figures (H1–H6) from existing Parquets (no Stockfish/extraction),
  reusing pure aggregation helpers; new figures = H2/H3/H4/H5, adapted = H1/H6;
- create an appendix figure index (reuse 13 existing figures + revised captions where cheap);
- add related-work citations + attribution (§12), `LICENSE` + `CITATION.cff` (§14–15);
- add reproducibility instructions;
- update ROADMAP + EXPERIMENT_LOG;
- preserve ALL existing scientific reports and existing figures unchanged.
- **No new modeling.** A small figure-generation module/CLI (read Parquet → aggregate → plot) is the only
  new code; if any headline figure needs an absent field, STOP and request approval.

## 17. Explicitly deferred work

Deferred unless explicitly revived: increment analysis; additional time controls; new Stockfish
extraction; new human-move model; new sharpness model; causal claims; full paper submission; new
neural-network training. The package must not become another research phase.

## 18. Open questions for Malachi

1. **License** — MIT for the project code? (Recommended: yes; no copyleft was copied.)
2. **Headline rating representation in H3** — Q1/Q3/Q5 with absolute-Elo legends (cleaner) vs raw 200-Elo
   bins (more interpretable, sparser tails)? (Recommended: Q1/Q3/Q5 + absolute-Elo legend headline; raw
   bins in appendix.)
3. **H2 axis** — actual seconds as the headline x-axis with a clock_fraction twin in appendix? (Recommended:
   yes — seconds headline, fraction appendix.)
4. **Public report venue** — README + in-repo `reports/benchmark_report.md` only, or also a short
   standalone writeup/preprint? (Recommended: README + in-repo report now; preprint deferred.)
5. **Sharpness** — appendix mention or omit entirely from the public package? (Recommended: one honest
   appendix paragraph marking it unresolved.)

---

**Non-claims (this ticket):** audit only; no models/figures/Stockfish/extraction/data/source/test/PREREG
changes. No novelty/first/unique/SOTA language. The decomposition is "apparently distinct within directly
inspected sources," not "novel." Predictive/descriptive, not causal; Stockfish = objective context, not
ground truth; T2 not equivalence; sharpness unresolved. C4 & C3c unchanged.
