# Human Chess Under Clock Constraints: A Replication and Benchmark Study

A repository-native benchmark report (not a formal paper). All results are **predictive and
descriptive, not causal**; Stockfish provides objective position context, not ground truth.

## Executive summary

Across 145,000+ Lichess games and 8.3M+ move-level observations in three no-increment time controls
(3+0, 5+0, 10+0) and two independent monthly samples (September and October 2024), this study asks a
simple question: when a player has little time on the clock and the position looks worse, is that
because they are **about to lose on time**, or because they are **playing worse moves on the board**?

The answer, descriptively, is mostly the former. Games decided by running out of time are much more
common in faster controls (≈ 29–30% of 3+0 games, ≈ 23% of 5+0, ≈ 12% of 10+0). When those games are
removed, the clock-related signal in the *final outcome* nearly disappears, while the *move-level*
association between low clock and worse next moves shrinks substantially but does not vanish — a
smaller board-play association remains, is steeper in faster controls, and replicates across both
months. The broad "low clock → more error" gradient itself is an established finding (replicated
here); the explicit time-forfeit-versus-board-decided decomposition was not found in the directly
inspected prior work.

## Prior work and positioning

- **Lower clock → more error** is established: Anderson, Kleinberg & Mullainathan (2016) analyze
  "blunder rate as a function of time remaining" (tablebase endgames). This study replicates the
  gradient using Stockfish across all phases and multiple controls.
- **Time pressure and skill** interact with move quality ("Time Pressure, Skill, and Move Quality in
  Chess"; related literature) — replicated here with clustering and cross-month replication.
- **Move-quality metrics** (expected-loss / capped centipawn loss) and rating/move-number/evaluation
  conditioning exist in `ianfab/chess-analysis` (AGPL-3.0; reimplemented independently, not copied).
- **Rating/clock-conditioned human prediction** (Maia/Maia-2/Maia-3, ChessMimic, Oxi, Allie) is a
  separate, crowded task. This project does **not** predict human moves; it analyzes move quality and
  decomposes outcomes. ChessMimic conditions an outcome model on ratings, time control, and remaining
  clock but does not parse termination or separate timeout from board-decided outcomes; Allie is
  termination-aware (a token) but performs no such decomposition.

What this project does **not** claim: a new metric, a new predictor, a new difficulty framework,
novelty of the clock→error gradient, a causal effect, or state of the art.

## Data

First 250,000 games per month of the public Lichess standard database, filtered to rated standard
3+0 / 5+0 / 10+0 games with both player ratings and `%clk` clock annotations. 3+0 and 5+0 are
extracted at a matched cap of 24,000 accepted games per month/control; 10+0 is the full-month anchor.
Per-control headline move-level rows ≈ 1.36–1.42M each (~8.35M total). Usernames are never stored;
only salted one-way player hashes, used solely for clustering. Game-level denominators and 200-Elo
bin counts are in [count_tables.md](figures/benchmark/count_tables.md).

## Move-quality measurement

Each move is evaluated with Stockfish at depth 12, before and after the played move. The primary
metric is **expected-score loss** from the mover's perspective: engine centipawns are mapped to an
expected game score via a logistic transform fit once on training data and reused everywhere, and the
loss is the drop in expected score from the best available move to the move played. Clipped centipawn
loss is reported as a transform-free cross-check. Mate-band positions are flagged and excluded from
headline aggregates. These metric choices follow established practice (e.g. `ianfab/chess-analysis`)
and are not claimed as contributions.

## Termination-channel decomposition

We separate the clock-related signal in the **final game outcome** into two channels:

- **Time-forfeit channel** — games that ended because a player's clock reached zero.
- **Board-decided channel** — games that ended by checkmate, resignation, or agreement.

Adding clock information to an outcome model that already controls for board evaluation and player
rating improves prediction, but the improvement is concentrated in the time-forfeit channel. Among
board-decided games the outcome residual is near zero (2024-09 ≈ +0.001, confidence interval contains
zero; 2024-10 ≈ +0.006), while time-forfeit games carry a large signal (≈ −0.12 to −0.13). In plain
terms: clock predicts outcomes mostly because players flag, not because board play collapses.

## Cross-time-control replication

**Time-forfeit prevalence (Figure H1)** falls monotonically with base time and is stable across
months: 3+0 ≈ 0.29 / 0.30, 5+0 ≈ 0.23 / 0.23, 10+0 ≈ 0.12 / 0.12 (Sep / Oct, game-level).

**Average move quality** is broadly similar across the three controls (mean expected-score loss
≈ 0.034–0.035). This is a descriptive observation, **not** a formal equivalence test, and small
differences remain.

## Actual-seconds degradation curves

**Figure H2** plots **game-normalized** mean expected-score loss against **actual seconds remaining**
(not a normalized fraction), with separate panels per control because 10 seconds means something
different in 3+0 than in 10+0. The descriptive curve is **U-shaped**: loss is elevated at *both* very
low seconds and high seconds, with a dip in between. The high-seconds elevation reflects complex
opening/middlegame positions played with a full clock; the very-low-seconds elevation is the
low-clock region of interest. Two series per panel — all games and board-decided games — show the
central result: at low remaining time the board-decided curve sits **below** the all-games curve (the
time-forfeit games carried part of the apparent low-clock elevation), and the two converge as time
increases. The gap is the attenuation; the residual board-decided low-clock elevation is the
surviving board-play association.

**Three relationships, kept distinct.** This report separates: (1) the **marginal descriptive**
relationship — the raw/game-normalized curves above, which are U-shaped and whose unadjusted
critical-minus-high gap is mixed and small (+0.003 / −0.002 / −0.006 for 3+0 / 5+0 / 10+0), confounded
by game stage because critical-clock states are endgame-concentrated; (2) the **conditional,
model-adjusted** relationship — after controlling for position evaluation, phase, rating, month,
color, and termination, lower clock is associated with a small *positive* monotone increase in loss
(critical-vs-high ≈ +0.012 / +0.008 / +0.006; in the model reports), which is **not** directly visible
in the unadjusted curves; and (3) the **board-decided attenuation** — the gap between the all-games
and board-decided curves at low clock (H2, H6). The headline figures show (1) and (3); (2) lives in
the controlled model results.

**Figure H3** breaks the all-games curve down by **absolute 200-Elo band** within each control, with
exact Elo ranges and counts in the legend and [count table](figures/benchmark/count_tables.md).
Higher-rated bands sit lower (less loss) at every clock level; the curves are within-control and are
**not** identical populations across controls.

## Move-number localization

**Figure H4** plots move quality against **move number**, split by clock state (high / medium / low /
critical), per control. **Figure H5** is a **move-number × actual-seconds heatmap** of mean
expected-score loss per control, with cells below 200 observations masked. Together they show the
joint danger region: the highest loss concentrates in mid-game moves played with little time
remaining, while the masked diagonal reflects states that rarely co-occur (you cannot be at move 80
with a full clock). Because very-low-clock states are concentrated late in the game, extreme-low-clock
results largely describe endgames.

## Rating-stratified results

Higher relative rating is associated with lower average loss at every clock level (Figure H3) — an
expected positive control. Relative rating also interacts with the low-clock gradient, but the
**direction of that interaction is sensitive to conditioning**: across all phases it points one way,
and within endgames it points the other. We therefore make **no universal claim** that rating buffers
or amplifies low-clock effects, and we find no clear difference in this moderation across controls.
The full rating-moderation analysis (quintiles, percentiles, Holm-controlled contrasts) is in the
[appendix index](appendix_figure_index.md).

## Board-decided robustness

Restricting to board-decided games (Figure H2; appendix board-decided curves) attenuates the
within-control low-clock contrast from roughly +0.012 / +0.008 / +0.006 (3+0 / 5+0 / 10+0) to roughly
+0.006 / +0.005 / +0.003 — smaller, still positive, and still replicated across months (model contrasts
in the appendix). At the raw aggregate level, mean move-quality loss at critical clock is consistently
lower among board-decided games than among all games in both months (Figure H6) — the time-forfeit
attenuation, replicated.

## Secondary and unresolved results

- Player-side time-forfeit prevalence decreases weakly with rating in 3+0 and 5+0 and is roughly flat
  in 10+0 (descriptive; appendix).
- A position-**sharpness** moderation analysis (using a MultiPV best-versus-second-move gap, in the
  spirit of Barthelemy's variation entropy) remains **unresolved** and underpowered; it is documented
  in the technical reports but is not part of the headline narrative.

## Limitations

Descriptive/predictive only; no causal identification. Stockfish evaluation is objective context, not
ground truth. The expected-score transform is fit on training data and reused across controls (a
comparability assumption). Very-low-clock states are endgame-concentrated. Raw Elo bands are
within-control. Two months only. Players can recur across months (≈ 18–22% overlap), so months are not
fully independent — hence player-clustered uncertainty.

## Reproducibility

`PYTHONPATH=src pytest` (~1,900+ tests). Headline figures regenerate from the existing dense Parquets
with `python -m chess_mhsuc.benchmark_figures …` (read-only; no Stockfish, no extraction; ~20s). The
dense Parquets are gitignored; rebuild them from raw Lichess PGNs via `dense_move_loss.py` and a local
Stockfish (see `reports/phase_reports/`). The cp→score transform JSON and the full scientific reports
are in the repo.

## Attribution

This repository copies no third-party source code. Stockfish (GPL-3.0) and the Lichess data retain
their own licenses; `ianfab/chess-analysis` (AGPL-3.0), `CSSLab/maia-chess` (GPL-3.0), and other
referenced repositories are cited for comparison only. The project's own code and documentation are
MIT-licensed. Full prior-art comparison: the
[prior-art / repository-overlap audit](phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md).

---

## Portfolio summary

**One sentence.** Built a reproducible 8M+ move analysis of human chess under clock constraints,
separating mechanical time-forfeit risk from board-play move-quality patterns across 145K+ games and
3 time controls, with clustered uncertainty and cross-month replication.

**Resume bullets (verified numbers):**
- Engineered a deterministic PGN→dense-Parquet pipeline over 145K+ Lichess games / 8.3M+ move-level
  observations across 3 time controls and 2 independent months, with leakage-aware splitting and
  ~1,900+ automated tests.
- Built a statistics layer (game-normalized weighting, game/mover-player sufficient-statistic
  clustered bootstrap, Holm multiplicity control) and decomposed the clock→outcome signal into
  time-forfeit vs board-decided channels — a decomposition not found in directly inspected prior work.
- Replicated and extended established clock/move-quality findings (cf. Anderson, Kleinberg &
  Mullainathan) across time controls under explicit non-causal, preregistered claim discipline.

**30-second explanation.** Does low clock mean worse chess, or just flagging? Using 8M+ Stockfish-
evaluated Lichess moves across three time controls and two months, I decomposed the clock signal: a
clock's value for predicting *outcomes* is mostly players running out of time; once you remove those
games, a smaller association with worse *board moves* remains, steeper in faster controls and
replicated across months. The broad gradient was known; the decomposition wasn't found in the
sources I inspected. It's descriptive, not causal.

**2-minute explanation.** Extends the 30-second version with: the matched-size cross-control design
and game-normalized, player-clustered uncertainty; the actual-seconds and move-number figures showing
*where* the association lives (mid-game time scrambles); the rating analysis whose direction flips
under phase conditioning (so no "skill buffers time pressure" claim); the engineering (a deterministic
8M-row pipeline, ~1,900+ tests, a preregistration discipline that forced honest, non-causal claims);
and the prior-art audit that reframed the project from "novel" to "rigorous replication + one
apparently-distinct decomposition."
