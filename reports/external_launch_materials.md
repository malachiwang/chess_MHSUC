# chess-MHSUC External Launch Materials

Final outward-facing launch material, derived from `reports/portfolio_launch_pack.md`. All numbers are
verified against the repository's source-of-truth files (see §11). Everything here is descriptive and
non-causal: this is a **replication and benchmark** study, not a novelty, causal, SOTA, decision-tree,
or neural-network project.

Repository: https://github.com/malachiwang06-lgtm/chess-MHSUC (matches `CITATION.cff`).

---

## 1. GitHub repository metadata

Manual steps for Malachi (GitHub → repo → "About" gear / Settings):

**Repository description** (paste into the About description field):

> Reproducible replication/benchmark of human chess under clock constraints: 8.3M+ moves across 145K+
> Lichess games and 3 time controls, decomposing the clock signal into time-forfeit vs board-decided
> move quality. Descriptive, non-causal, MIT.

(Under 350 characters.)

**Website / link field:**
GitHub's "Website" field requires a URL, not an in-repo file path, so it cannot point directly at
`reports/benchmark_report.md`. Recommended options, in order:
1. Leave the Website field set to the repository itself (or blank), and rely on the README's link to
   `reports/benchmark_report.md`.
2. If GitHub Pages is ever enabled, point it at the rendered report.
For reference inside the README/outreach, the canonical "read more" target is
`reports/benchmark_report.md` (renders on GitHub at
`https://github.com/malachiwang06-lgtm/chess-MHSUC/blob/main/reports/benchmark_report.md`).

**Topics** (add in the About → topics field; lowercase, hyphenated, no spaces):

```
chess
lichess
stockfish
data-science
reproducible-research
benchmark
replication-study
statistical-analysis
python
polars
time-pressure
sports-analytics
```

**Pinning:** after the description and topics are set, pin the repository on your GitHub profile
(Profile → "Customize your pins" → select chess-MHSUC). Do this once the metadata looks finished.

**Release tag:** not required (see §10).

---

## 2. Resume bullets

### A. Data science / ML version

- Engineered a deterministic pipeline turning 145K+ Lichess games into 8.3M+ Stockfish-evaluated,
  move-level records across 3 time controls and 2 monthly samples, with leakage-aware game-ID splitting.
- Measured human move quality as expected-score loss and decomposed the clock-to-outcome signal into
  mechanical time-forfeit and board-decided channels, showing the predictive clock signal is mostly flagging.
- Validated results with game-normalized weighting, player-clustered uncertainty, and cross-month
  replication, keeping all conclusions descriptive and non-causal.

### B. SWE / data engineering version

- Built a deterministic PGN-to-Parquet pipeline (Polars, python-chess, Stockfish) producing 8.3M+
  reproducible move-level rows, with a read-only CLI that regenerates 12 benchmark figures in seconds.
- Covered the pipeline and statistics layer with 1,951 automated tests and byte-identical figure
  regeneration, enforcing data boundaries that keep raw data and large Parquets out of version control.
- Packaged the project for public release with MIT licensing, a third-party NOTICE, and citation
  metadata, clearly separating shipped code from gitignored datasets.

### C. Quant / analytics version

- Analyzed 8.3M+ event-level records to benchmark decision quality under a depleting resource (the
  chess clock), using expected-value loss instead of raw point estimates.
- Decomposed an observed risk signal into a mechanical settlement channel (time-forfeit) and a
  behavioral channel (board-decided move quality) to isolate where the predictive signal lives.
- Quantified uncertainty with clustered bootstrap resampling and out-of-sample monthly replication,
  framing every result as a conditional association rather than a causal effect.

---

## 3. Compact resume version (2 lines, tight space)

- chess-MHSUC — Reproducible benchmark of human chess under clock constraints: 8.3M+ Stockfish-evaluated
  moves, 145K+ games, 3 time controls, separating time-forfeit risk from board-play move quality.
- Built the deterministic PGN-to-Parquet pipeline, expected-score-loss statistics, 1,951 tests, and a
  public MIT-licensed package with game-normalized, player-clustered, cross-month-replicated results.

---

## 4. LinkedIn project entry

**Project title:** chess-MHSUC — Human Chess Under Clock Constraints (Replication & Benchmark)

**Date range:** [start] – [end] (placeholder)

**Project URL:** https://github.com/malachiwang06-lgtm/chess-MHSUC

**Description:**
A reproducible benchmark study of how human chess move quality relates to the remaining clock, built on
8.3M+ Stockfish-evaluated moves from 145K+ Lichess games across three time controls and two months. The
project separates two things that look alike in the data: players literally losing on time versus
players making worse moves on the board. It pairs a deterministic data pipeline and a tested statistics
layer with public benchmark figures, and keeps every conclusion descriptive rather than causal.

**Skills:** Python · Polars · python-chess · Stockfish · data pipelines · statistical analysis ·
bootstrap uncertainty · reproducible research · data visualization · technical writing

---

## 5. GitHub pinned-repo blurb

> 8.3M+ moves benchmarking human chess under clock constraints: time-forfeit vs board-decided move
> quality, descriptive and non-causal.

(Under 180 characters; mentions 8.3M moves, clock constraints, time-forfeit vs board-decided.)

---

## 6. Interview answer pack

Natural spoken-style answers — plain English first, then the technical detail.

**1. What did you build?**
"I built a benchmark of human chess under time pressure. I took millions of online games, evaluated
every move with a chess engine, and measured how much each player gave up versus the best move. The
twist is I separated two things that look the same in the data — people losing on time versus people
actually playing worse moves. Technically it's a deterministic data pipeline plus a tested statistics
layer over 8.3 million moves."

**2. What model did you use?**
"It's mainly statistics and benchmarking, not one trained model. The public package is descriptive,
game-normalized figures. The deeper analysis is controlled comparisons — does adding clock information
improve outcome prediction beyond the position evaluation and player rating — and then I split that
signal into time-forfeit and board-decided pieces. Move quality itself I measure directly from engine
evaluations, I don't predict it with a classifier."

**3. Why isn't this a decision tree / neural net project?**
"Because the question wasn't 'can I predict the next move' — that's a crowded space already. My question
was 'where does the clock signal actually come from,' and the clean way to answer that is a decomposition
and controlled comparisons, not a black-box predictor. I wanted the result to be interpretable and
honest, so I deliberately didn't wrap it in a model I couldn't explain."

**4. What was the hardest technical part?**
"Two things. First, doing 8 million Stockfish evaluations deterministically and reproducibly, so the
whole thing rebuilds the same way every time. Second, the statistics — the raw curves are U-shaped and
confounded by game stage, so I had to be really careful to separate the marginal descriptive picture
from the conditional, model-adjusted result, and not present one as the other."

**5. What was the main result?**
"Descriptively, the clock predicts outcomes mostly because people flag — run out of time — not because
their board play collapses. When you drop the games that ended on time, the clock signal in the final
outcome nearly disappears. A smaller association with worse moves does survive, it's steeper in faster
time controls, and it replicates across both months."

**6. Is this novel?**
"I frame it as a replication and benchmark, not a novelty claim. The link between low clock and more
errors is established work, and I replicate it. The part I'd call distinct is the explicit time-forfeit
versus board-decided decomposition — I didn't find an equivalent in the repos and papers I looked at,
but I say that as a bounded statement about what I reviewed, not 'first ever.'"

**7. Is this causal?**
"No, and I'm careful about that. It's descriptive and predictive. The engine is objective context, not
ground truth, and low-clock states are concentrated in endgames, so I don't claim time pressure *causes*
worse reasoning — I measure associations and decompose where the signal lives."

**8. Can someone reproduce it?**
"Yes, with one boundary. The code, reports, the 12 figures, the tests, and the plotting CLI are all in
the repo, and the test suite runs out of the box. The 8.3-million-row datasets are gitignored and not
shipped — the README explains how to rebuild them from the raw Lichess data with the pipeline. So the
method is fully reproducible; the multi-gigabyte inputs just aren't in GitHub."

**9. What would you improve next?**
"The biggest honest limitation is no prior-trajectory control — I'd add features for how the position
and clock evolved before each move. I'd also extend to increment time controls and more months, and the
position-sharpness angle is currently underpowered, so I'd either strengthen it or leave it clearly
flagged as unresolved."

**10. Why is this relevant to data science / quant / SWE?**
"It's an end-to-end story: I built the pipeline, the metrics, the statistics, the tests, and the public
write-up. For data science it's careful confounding and uncertainty work; for quant it's risk
decomposition and expected-value loss on large event data; for SWE it's a deterministic, tested,
reproducible pipeline with clean data boundaries."

---

## 7. Recruiter outreach blurb

> I recently finished a data project benchmarking human chess decisions under time pressure — 8.3M+
> engine-evaluated moves across 145K+ online games — where I separated players losing on time from
> players actually making worse moves. It covers the full stack: a deterministic data pipeline, a tested
> statistics layer, and a public, reproducible package. Code and write-up: [GitHub link].

---

## 8. Professor / research mentor outreach blurb

> I built a reproducible replication-and-benchmark study of human move quality under clock constraints
> on Lichess (145K+ games, 8.3M+ plies, three time controls, two months). The piece I'd most value
> feedback on is a decomposition that separates the clock-related outcome signal into a mechanical
> time-forfeit channel and a board-decided move-quality channel, with game- and player-clustered
> uncertainty and cross-month replication. It's explicitly descriptive and preregistered: [GitHub link].

(No publication-potential overselling.)

---

## 9. Do Not Say This

| Do not say | Say instead |
|---|---|
| "I built a novel chess AI." | "I built a reproducible benchmark study of human chess move quality under clock constraints." |
| "I proved time pressure causes worse moves." | "I measured descriptive associations between clock state, time-forfeit risk, and move-quality loss." |
| "State-of-the-art human move prediction." | "I don't predict moves; I benchmark move quality and decompose the clock-to-outcome signal." |
| "I trained a decision tree / neural network to model this." | "It's controlled statistical comparisons plus descriptive benchmark figures, not a single trained model." |
| "Stockfish gives the ground-truth best move." | "Stockfish provides objective position context, not ground truth." |
| "First study to do this." | "Apparently distinct within the sources I inspected — a bounded, not universal, claim." |
| "Higher rating protects players from time pressure." | "Rating interacts with the low-clock pattern, but the direction is conditioning-sensitive, so I make no universal claim." |
| "Download the 8.3M-move dataset from the repo." | "The dense datasets are gitignored; the repo ships the code to rebuild them." |
| "I solved position sharpness / complexity." | "Position sharpness is included but unresolved and underpowered here." |

---

## 10. Optional release tag recommendation

**Recommendation: do not tag a release yet.** The repository is already public-use ready and citable via
`CITATION.cff`; a version tag adds value only if Malachi wants a fixed, quotable citation anchor right
now (e.g., for an application deadline or a shared link that must not move).

If/when desired, create:
- Tag: `v1.0.0`
- Title: `chess-MHSUC public benchmark release`
- Note (suggested): "First public release of the chess-MHSUC replication/benchmark package: 8.3M+
  move-level observations across 145K+ Lichess games and three time controls, with the time-forfeit vs
  board-decided decomposition, game-normalized figures, and full test suite. Descriptive, non-causal,
  MIT-licensed original code."

Do **not** create the tag without explicit instruction.

---

## 11. Source-of-truth numbers

| Number | Value | Source file | Public wording |
|---|---:|---|---|
| Games | 145,020 | reports/figures/benchmark/count_tables.md | 145K+ games |
| Move rows | 8,353,475 | reports/figures/benchmark/count_tables.md | 8.3M+ moves |
| Time controls | 3 (3+0, 5+0, 10+0) | reports/benchmark_report.md | 3 time controls |
| Monthly samples | 2 (2024-09, 2024-10) | reports/benchmark_report.md | 2 independent monthly samples |
| Benchmark figures | 12 | reports/figures/benchmark/ | 12 benchmark figures |
| Tests | 1,951 | EXP-063 / phase_17_0d report | 1,900+ tests (or exact 1,951) |
| Time-forfeit rate 3+0 | 0.2917 / 0.3009 | count_tables.md | ≈ 29–30% of 3+0 games |
| Time-forfeit rate 5+0 | 0.2263 / 0.2258 | count_tables.md | ≈ 23% of 5+0 games |
| Time-forfeit rate 10+0 | 0.1151 / 0.1164 | count_tables.md | ≈ 12% of 10+0 games |
| Stockfish depth | 12 | reports/benchmark_report.md | depth-12 evaluation |
| License | MIT (original code/docs) | LICENSE / NOTICE.md | MIT-licensed original code and docs |
| Repository URL | github.com/malachiwang06-lgtm/chess-MHSUC | CITATION.cff / git remote | matches CITATION.cff |

Recheck against `count_tables.md` before publishing if the data is ever regenerated.
