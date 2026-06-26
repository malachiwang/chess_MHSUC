# Chess-MHSUC — Human Chess Under Clock Constraints

A reproducible **replication and benchmark study** of human move quality and clock
constraints in online chess, with an explicit decomposition of **mechanical time-forfeit
risk** versus **board-play move quality**.

- **145,000+** Lichess games · **8.3M+** move-level observations
- **3 time controls** (3+0, 5+0, 10+0) · **2 independent monthly samples** (2024-09, 2024-10)
- Every move evaluated with Stockfish (depth 12); move quality measured as **expected-score loss**
- Game-normalized weighting · game- and player-clustered uncertainty · cross-month replication

**Central finding (descriptive, not causal).** The predictive value of a player's clock in
online chess comes mostly from a **mechanical time-forfeit (flagging) channel**, not from worse
board play. At the move level, the elevated next-move loss seen at very low clock is partly carried
by games that end on time: when those games are removed, the low-clock elevation **shrinks
substantially but does not vanish** (figure H2). After conditioning on position, phase, and rating,
a small low-clock association with worse board moves remains, is steeper in faster time controls, and
replicates across two months.

> These results are **predictive and descriptive, not causal**. Stockfish provides objective
> position context, not ground truth. We do not claim that time pressure *causes* worse reasoning.
> No equivalent time-forfeit-versus-board-decided decomposition was found in the directly inspected
> prior work (see [prior-art audit](reports/phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md)).

**Read more:** [benchmark report](reports/benchmark_report.md) ·
[headline figures](reports/figures/benchmark/) ·
[appendix figure index](reports/appendix_figure_index.md) · [reproducibility](#reproducibility)

---

## What this project studies

Given a board position and human context — engine evaluation, player ratings, clocks, move
number, game phase — how does observed human move quality (and the final game outcome) relate to
the remaining clock? And crucially: how much of the "low clock looks worse" pattern is **players
literally losing on time** versus **playing worse moves on the board**?

## What prior work already established

This project does **not** introduce a new metric, a new human-move predictor, or a new
position-difficulty framework. The following are established and are replicated here, not claimed
as contributions:

- Lower remaining clock is associated with higher blunder/error rates (Anderson, Kleinberg &
  Mullainathan, 2016 — "blunder rate as a function of time remaining").
- Faster time controls and time pressure are associated with lower move quality, and skill
  interacts with this ("Time Pressure, Skill, and Move Quality in Chess"; related literature).
- Expected-score / expected-loss and capped-centipawn move-quality metrics, and conditioning by
  rating, move number, and evaluation state ([ianfab/chess-analysis](https://github.com/ianfab/chess-analysis)).
- Rating-conditioned human move/clock/outcome modeling (Maia, Maia-2/Maia-3, ChessMimic, Oxi, Allie).

See [Prior work and attribution](#prior-work-and-attribution).

## What this project replicates

- Time-forfeit prevalence rises sharply as the base time falls (3+0 ≈ 0.29–0.30, 5+0 ≈ 0.23,
  10+0 ≈ 0.12, game-level, both months).
- After conditioning on position evaluation, game phase, and rating, lower remaining clock is
  associated with a small monotone increase in next-move expected-score loss within every control;
  this **conditional** gradient is steeper in faster controls, replicates across both months, and
  survives clustering by player (critical-vs-high contrast ≈ +0.012 / +0.008 / +0.006 for
  3+0 / 5+0 / 10+0; see the model reports).

> **Marginal vs conditional — read the figures carefully.** The unadjusted descriptive curves
> (H2–H3) are **U-shaped**: move-quality loss is elevated at *both* very low clock *and* high clock,
> with a dip in between. High-clock loss is elevated because full-clock positions include complex
> opening/middlegame play; very-low-clock loss is elevated but those states are concentrated in
> endgames. The *unadjusted* critical-minus-high gap is therefore mixed (+0.003 / −0.002 / −0.006 by
> control) and confounded by game stage. The clean "lower clock → higher loss" gradient is the
> **conditional, model-adjusted** result above, not something visible in a raw aggregate. The figures
> show the descriptive curves and the board-decided attenuation; the monotone gradient lives in the
> model contrasts.

## The termination-channel decomposition

The apparently distinct empirical component: separating the clock-related **final-outcome** signal
into a **time-forfeit channel** and a **board-decided channel**, then comparing it with **next-move
quality among board-decided games**. The board-decided outcome residual is near zero (Sep ≈ +0.001,
CI contains zero; Oct ≈ +0.006), while the time-forfeit channel carries a large signal (≈ −0.12 to
−0.13). At the move level, removing time-forfeit games attenuates the low-clock loss but leaves a
small positive board-play association. No equivalent decomposition was found in the directly
inspected sources.

## Data

First 250k games per month of the public Lichess standard database, filtered to rated 3+0 / 5+0 /
10+0 games with both ratings and clock annotations. 3+0 and 5+0 were extracted at a matched cap of
24,000 accepted games per month/control; 10+0 is the full-month anchor. Usernames are never stored;
only salted one-way player hashes (used solely for clustering). Dense per-ply move-level tables are
gitignored (data is not redistributed); the extraction pipeline is in the repo.

## Methods

- **Move quality:** Stockfish (depth 12) pre/post-move evaluation → **expected-score loss**
  (mover perspective; logistic cp→score transform, fit once on training data, reused everywhere),
  with clipped centipawn loss as a transform-free cross-check.
- **Clock:** actual seconds remaining and a normalized clock fraction (seconds / base time).
- **Statistics:** game-normalized weighting; game- and mover-player-clustered sufficient-statistic
  bootstrap; Holm multiplicity control for the locked contrast families; two independent months as
  replication.
- All claims are predictive/descriptive. The full scientific reports are under `reports/`.

## Headline results

| Figure | Question |
|---|---|
| [H1](reports/figures/benchmark/H1_time_forfeit_prevalence_by_control.png) | How does time-forfeit prevalence differ by time control? |
| [H2](reports/figures/benchmark/H2_all_games_vs_board_decided_actual_seconds.png) | All-games vs board-decided move quality vs actual seconds remaining |
| H3 ([3+0](reports/figures/benchmark/H3_move_quality_actual_seconds_by_elo_3plus0.png) · [5+0](reports/figures/benchmark/H3_move_quality_actual_seconds_by_elo_5plus0.png) · [10+0](reports/figures/benchmark/H3_move_quality_actual_seconds_by_elo_10plus0.png)) | Move quality vs actual seconds by absolute Elo band |
| H4 ([3+0](reports/figures/benchmark/H4_move_quality_by_move_number_and_clock_state_3plus0.png) · [5+0](reports/figures/benchmark/H4_move_quality_by_move_number_and_clock_state_5plus0.png) · [10+0](reports/figures/benchmark/H4_move_quality_by_move_number_and_clock_state_10plus0.png)) | Where in the game does the low-clock association emerge? |
| H5 ([3+0](reports/figures/benchmark/H5_move_number_actual_clock_heatmap_3plus0.png) · [5+0](reports/figures/benchmark/H5_move_number_actual_clock_heatmap_5plus0.png) · [10+0](reports/figures/benchmark/H5_move_number_actual_clock_heatmap_10plus0.png)) | Joint move-number × remaining-time danger region |
| [H6](reports/figures/benchmark/H6_month_replication_summary.png) | Does the low-clock time-forfeit attenuation replicate across months? |

Aggregation counts behind these figures: [count_tables.md](reports/figures/benchmark/count_tables.md).

## Board-decided robustness

Restricting to games that ended by checkmate/resignation/agreement (not on time) attenuates the
low-clock move-quality association but does not eliminate it (H2). The conditional within-control
critical-vs-high contrast falls from roughly +0.012/+0.008/+0.006 (3+0/5+0/10+0) to roughly
+0.006/+0.005/+0.003 board-decided — smaller, positive, and still month-replicated. At the raw level,
mean move-quality loss at critical clock is consistently lower among board-decided games than among
all games, in both months (H6).

## Cross-time-control replication

Average next-move expected-score loss is **broadly similar** across the three controls
(≈ 0.034–0.035; this is a descriptive observation, not a formal equivalence test). The low-clock
gradient is steeper in faster controls. Both patterns replicate across September and October 2024.

## Rating and phase sensitivity

Higher relative rating is associated with lower average loss (an expected positive control).
Relative rating also interacts with the low-clock gradient, but **the direction is sensitive to
conditioning** — it points one way across all phases and the other way within endgames — so we make
**no universal claim** that rating buffers or amplifies low-clock effects, and we find no clear
difference in this moderation across controls.

## Limitations

Descriptive/predictive only — no causal identification. Stockfish evaluation is objective context,
not ground truth. Very-low-clock states are concentrated in late-game positions, so extreme-low-clock
results largely describe endgames. Raw Elo bands are within-control and are not identical populations
across controls. Two months only. Position-sharpness moderation remains unresolved (appendix).

## Reproducibility

```bash
# environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src

# tests
pytest

# regenerate the headline figures from the dense move-level Parquets (read-only; no Stockfish)
python -m chess_mhsuc.benchmark_figures \
  --dense-2024-09-3plus0  data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet \
  --dense-2024-09-5plus0  data/processed/dense_move_loss_2024_09_5plus0_24k_v1.parquet \
  --dense-2024-09-10plus0 data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-2024-10-3plus0  data/processed/dense_move_loss_2024_10_3plus0_24k_v1.parquet \
  --dense-2024-10-5plus0  data/processed/dense_move_loss_2024_10_5plus0_24k_v1.parquet \
  --dense-2024-10-10plus0 data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --figure-dir reports/figures/benchmark
```

The dense Parquets are gitignored (data is not redistributed). Building them from raw Lichess PGNs
uses the extraction pipeline in `src/chess_mhsuc/` (`dense_move_loss.py`) and a local Stockfish; see
the phase reports under `reports/phase_reports/`. ~1,900+ automated tests cover the pipeline.

## Prior work and attribution

| Work | What it did | This project |
|---|---|---|
| [ianfab/chess-analysis](https://github.com/ianfab/chess-analysis) (AGPL-3.0) | expected-loss / capped-CP metrics + rating/ply/eval conditioning | independently reimplements the metric design; adds clock / time-control / termination layer |
| Anderson, Kleinberg & Mullainathan (2016) | blunder rate vs time remaining (tablebase endgames) | replicates the clock→error gradient with Stockfish, all phases, multiple controls |
| "Time Pressure, Skill, and Move Quality in Chess" | rating × time-pressure on move quality | replicates the interaction; adds clustering, replication, localization |
| [Maia](https://github.com/CSSLab/maia-chess) / Maia-2 / Maia-3, [ChessMimic](https://arxiv.org/abs/2606.04473), [Oxi](https://github.com/marcusbuffett/oxi), [Allie](https://github.com/ippolito-cmu/allie) | rating/clock-conditioned human move/time/outcome prediction | does **not** compete with prediction; performs descriptive move-quality + outcome decomposition instead |
| Barthelemy, "Chess variation entropy…" | position-complexity / best-vs-second-move gap | the sharpness proxy is reimplemented; that analysis is left **unresolved** |

This repository copies no third-party source code. AGPL/GPL/no-license repositories above are
referenced only. Stockfish (GPL-3.0) and Lichess data retain their own licenses; this project's MIT
license covers only its own original code and documentation.

## License

[MIT](LICENSE) — covers this project's original code and documentation only. Stockfish (GPL-3.0),
the Lichess data, third-party dependencies, and all referenced external repositories retain their own
licenses; no third-party source is copied into this repository. See [NOTICE.md](NOTICE.md) for the
full scope and third-party notice.
