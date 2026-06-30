# chess-MHSUC Portfolio Launch Pack

Copy-ready external-facing material for resume, GitHub, LinkedIn, applications, interviews, and
research outreach. All wording is descriptive/non-causal and uses only verified numbers (see §17).
This project is a **reproducible replication and benchmark study**, not a novelty or causal claim.

---

## 1. One-sentence project description

**General (25–35 words).**
Built a reproducible benchmark of human chess under clock constraints across 145K+ online games and
8.3M+ moves, separating mechanical time-forfeit risk from board-play move quality over three time
controls and two monthly samples.

**Technical (35–50 words).**
Engineered a deterministic PGN-to-Parquet pipeline over 8.3M+ Stockfish-evaluated moves from 145K+
Lichess games (3+0/5+0/10+0, two months), measuring expected-score loss with game-normalized,
player-clustered statistics, and decomposing the clock-to-outcome signal into time-forfeit and
board-decided channels — descriptive, replicated, and non-causal.

**Resume-header (12–18 words).**
Reproducible 8.3M-move chess benchmark separating time-forfeit risk from board-play move quality
across three time controls.

---

## 2. GitHub repository short description

> Reproducible replication/benchmark of human chess under clock constraints: 8.3M+ moves across 145K+
> Lichess games and 3 time controls, decomposing the clock signal into time-forfeit vs board-decided
> move quality. Descriptive, non-causal, MIT.

(Under 350 characters; includes chess, clock constraints, 8.3M moves, replication/benchmark,
time-forfeit vs board-decided.)

---

## 3. GitHub About/sidebar topics

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

(Lowercase, hyphenated, no spaces — valid GitHub topics. 12 listed; trim to 8–10 if preferred.)

---

## 4. Resume bullets

### Version A — Data science / ML internship

- Engineered a deterministic pipeline turning 145K+ Lichess games into 8.3M+ Stockfish-evaluated,
  move-level records across 3 time controls and 2 monthly samples, with leakage-aware game-ID splitting.
- Measured human move quality as expected-score loss and decomposed the clock-to-outcome signal into
  mechanical time-forfeit and board-decided channels, showing the predictive clock signal is mostly flagging.
- Validated findings with game-normalized weighting, player-clustered uncertainty, and cross-month
  replication, holding all claims descriptive and non-causal under a preregistered discipline.

### Version B — SWE / data engineering

- Built a deterministic PGN-to-Parquet data pipeline (Polars, python-chess, Stockfish) producing 8.3M+
  reproducible move-level rows, with a read-only CLI that regenerates 12 benchmark figures in seconds.
- Covered the pipeline and statistics layer with 1,951 automated tests and byte-identical figure
  regeneration, enforcing clean data boundaries that keep raw data and large Parquets out of version control.
- Packaged the project for public release with MIT licensing, a third-party NOTICE, citation metadata,
  and documentation that clearly separates shipped code from gitignored datasets.

### Version C — Quant / analytics

- Analyzed 8.3M+ large-scale event records to benchmark decision quality under a depleting resource
  (the chess clock), using expected-value loss rather than raw point estimates.
- Decomposed an observed risk signal into a mechanical settlement channel (time-forfeit) and a
  behavioral channel (board-decided move quality), isolating where the predictive signal actually lives.
- Quantified uncertainty with clustered bootstrap resampling and out-of-sample monthly replication,
  framing every result as a conditional association rather than a causal effect.

Each bullet starts with an action verb, carries a verified number where natural, avoids novelty/causal
overclaim, and uses simple ATS-safe punctuation.

---

## 5. LinkedIn project entry

**Project title:** chess-MHSUC — Human Chess Under Clock Constraints (Replication & Benchmark)

**Description:**
A reproducible benchmark study of how human chess move quality relates to the remaining clock, built
on 8.3M+ Stockfish-evaluated moves from 145K+ Lichess games across three time controls and two months.
The project separates two things that look alike in the data: players literally losing on time versus
players making worse moves on the board. It pairs a deterministic data pipeline and a tested
statistics layer with public benchmark figures, and keeps every conclusion descriptive rather than
causal.

**Skills:** Python · Polars · python-chess · Stockfish · data pipelines · statistical analysis ·
bootstrap uncertainty · reproducible research · data visualization · technical writing

**Link:** https://github.com/malachiwang06-lgtm/chess-MHSUC

---

## 6. 30-second interview explanation

I built a benchmark of human chess under time pressure. Using 8.3M+ moves from 145K+ Lichess games
across three time controls, I evaluated every move with Stockfish and measured how much expected score
a player gave up. The main question: when a low clock looks bad, is it because the player is about to
lose on time, or because they are playing worse moves? Descriptively, it is mostly the former — once
you remove games that ended on time, the clock signal in the final outcome nearly disappears, while a
smaller board-play association remains. Technically it shows I can build a reproducible large-data
pipeline and reason carefully about confounding, without overclaiming causation.

---

## 7. 2-minute technical interview explanation

**Problem.** In fast online chess, low remaining time correlates with worse outcomes. But that could be
two different things: people running out of time, or people actually playing worse moves. I wanted to
separate them.

**Data and scale.** I used the public Lichess database — 145K+ rated games in 3+0, 5+0, and 10+0,
across two separate months for replication. That expands to 8.3M+ move-level rows.

**Pipeline.** A deterministic PGN-to-Parquet pipeline parses games, extracts clocks and ratings, and
evaluates each position with Stockfish before and after the played move. Usernames are never stored —
only salted one-way hashes for clustering.

**Metric.** Instead of raw centipawn loss, the headline metric is expected-score loss: I map engine
centipawns to an expected game result with a logistic transform fit once on training data, so a
blunder in a already-winning position is not over-counted. Clipped centipawn loss is a transform-free
cross-check.

**Key decomposition.** I split the clock-to-outcome signal into a time-forfeit channel and a
board-decided channel. Adding clock to an outcome model helps prediction, but the improvement is
concentrated in time-forfeit games. Among board-decided games the outcome residual is near zero. So the
clock predicts outcomes mostly because people flag, not because board play collapses.

**Figures and statistics.** The public benchmark uses game-normalized weighting so long games do not
dominate, plus player-clustered bootstrap uncertainty, and everything is shown to replicate across both
months.

**Prior-art correction.** A prior-art search showed the clock-to-error gradient itself is established
work, so I reframed the project from "novel finding" to "rigorous replication plus one apparently
distinct decomposition" — I could not find an equivalent time-forfeit-versus-board-decided split in the
sources I inspected.

**Limitations.** It is descriptive, not causal. Stockfish is objective context, not ground truth.
Very-low-clock states are concentrated in endgames. Two months only.

**What it shows.** End-to-end: a deterministic 8M-row pipeline, ~1,951 tests, honest statistical
interpretation, and a public, reproducible package.

---

## 8. Recruiter-friendly explanation

I studied whether running low on the chess clock makes people play worse, using millions of online
games. The interesting part is separating two explanations that look identical in raw data — losing on
time versus making worse moves — and showing the predictive signal is mostly the first one. It is a
data-engineering and statistics project: I built the data pipeline, the analysis, the tests, and the
public write-up, and I was careful not to overclaim.

---

## 9. Research/professor-facing explanation

This is a reproducible replication-and-benchmark study of human move quality under clock constraints on
Lichess (3+0/5+0/10+0; September and October 2024; 145K+ games, 8.3M+ plies). Move quality is
operationalized as mover-perspective expected-score loss from depth-12 Stockfish evaluations, with a
once-fit logistic cp-to-score transform and clipped centipawn loss as a robustness check. The
contribution I would foreground is decompositional rather than predictive: I separate the clock-related
final-outcome signal into a mechanical time-forfeit channel and a board-decided channel, and find the
board-decided outcome residual is near zero while the time-forfeit channel carries the signal. The
established clock-to-error gradient (cf. Anderson, Kleinberg & Mullainathan) is replicated, and a small
board-play association survives conditioning on evaluation, phase, and rating. Uncertainty is
game- and player-clustered; results replicate across months. Claims are explicitly non-causal and
preregistered, and I did not find an equivalent decomposition in the repositories and papers I
inspected (a bounded, not universal, statement).

---

## 10. Technical deep-dive talking points

- **PGN → dense Parquet:** parse Lichess PGNs with python-chess, extract `%clk` clocks, ratings,
  termination, and per-ply positions into a fixed 65-column schema; deterministic, leakage-aware.
- **Stockfish → expected-score loss:** evaluate each position before/after the played move at depth 12;
  map centipawns to expected score via a logistic transform fit once on training data and reused.
- **Why expected-score loss over raw centipawns:** it down-weights "blunders" in already-decided
  positions and reflects how much real game result was actually surrendered — the right headline unit.
- **Why game-normalized weighting:** without it, long games dominate the average; each game contributes
  equal total weight within its control-month, matching the inferential models.
- **Marginal vs conditional:** the raw curves are U-shaped and the unadjusted critical-minus-high gap is
  mixed/small; the clean "lower clock → more loss" gradient is the conditional, model-adjusted result —
  I keep these explicitly distinct so I never present a model effect as a visible raw effect.
- **Why the time-forfeit decomposition matters:** it explains *why* low clock predicts bad outcomes —
  mostly flagging, not collapsing board play — which most prior framings collapse together.
- **Why board-decided robustness matters:** restricting to games not decided on time attenuates but does
  not eliminate the low-clock move-quality association, so the board-play residual is real but small.
- **Why prior-art search changed framing:** it confirmed the gradient is established, so I dropped any
  novelty framing and positioned the work as replication + one apparently-distinct decomposition.
- **What tests cover:** parsing, clock/eval extraction, the cp-to-score transform, weighting, clustering,
  figure aggregation, and privacy guards — 1,951 tests, with byte-identical figure regeneration.
- **What is intentionally not claimed:** no causation, no SOTA prediction, no new metric/model, no
  universal rating-buffer claim, no solved position-sharpness.

---

## 11. "What model did you use?" answer

**Full answer.**
This project is not built around a decision-tree classifier or a neural network. The public package
uses game-normalized descriptive benchmark figures, and the deeper analysis uses controlled statistical
comparisons of outcome prediction and move-quality loss. The key model comparison asks whether adding
clock information improves final-outcome prediction beyond board evaluation and player rating, and then
separates that signal into time-forfeit and board-decided channels. Move quality itself is measured
directly as expected-score loss from Stockfish evaluations, not predicted by a learned model.

**Recruiter-safe short version.**
It is mainly a statistics-and-benchmarking project, not a single ML model. I compare what clock
information adds to outcome prediction on top of position and rating, and I measure move quality
directly from engine evaluations rather than training a classifier.

---

## 12. (See §10 — technical deep-dive talking points.)

---

## 13. Reproducibility answer

Yes, with one honest boundary. The public code, reports, the 12 benchmark figures, the test suite, and
the figure-plotting CLI are all in the repository, and `PYTHONPATH=src pytest` runs the full suite.
What is *not* shipped is the data: the dense move-level Parquets (8.3M+ rows) are gitignored, and the
raw Lichess PGNs and Stockfish runs are intentionally not bundled. The figures can be regenerated
exactly once those dense Parquets are supplied or rebuilt with the extraction pipeline in the repo,
which the README documents clearly. So the *method* is fully reproducible and the *outputs* are shipped;
the multi-gigabyte inputs are not in GitHub by design.

---

## 14. Novelty answer

I frame it honestly as a replication and benchmark, not a novelty claim. Most of the infrastructure and
the move-quality analysis build on established work — the link between low clock and higher error rates
is a known result, and I replicate it. The part I would call distinct is the explicit decomposition of
the clock-to-outcome signal into a mechanical time-forfeit channel and a board-decided move-quality
channel. I did not find an equivalent decomposition in the repositories and papers I inspected, but I
state that as a bounded observation about what I reviewed, not as a universal "first ever" claim. I
think that framing is more credible than overclaiming, and it is the framing a careful reviewer would
trust.

---

## 15. Numbers and source-of-truth table

| Number | Value | Source file | Public-use wording |
|---|---:|---|---|
| Games | 145,020 | reports/figures/benchmark/count_tables.md; benchmark_report.md | 145K+ games |
| Move rows | 8,353,475 | reports/figures/benchmark/count_tables.md; benchmark_report.md | 8.3M+ moves |
| Time controls | 3 | benchmark_report.md (3+0, 5+0, 10+0) | 3 time controls |
| Monthly samples | 2 | benchmark_report.md (2024-09, 2024-10) | 2 independent monthly samples |
| Benchmark figures | 12 | reports/figures/benchmark/ (H1–H6, 12 PNGs) | 12 benchmark figures |
| Tests | 1,951 | phase_17_0d report / EXP-063 (rerun) | 1,900+ tests (or exact 1,951 tests) |
| Time-forfeit rate 3+0 | 0.2917 / 0.3009 | count_tables.md | ≈ 29–30% of 3+0 games |
| Time-forfeit rate 5+0 | 0.2263 / 0.2258 | count_tables.md | ≈ 23% of 5+0 games |
| Time-forfeit rate 10+0 | 0.1151 / 0.1164 | count_tables.md | ≈ 12% of 10+0 games |
| Board-decided outcome residual | ≈ +0.001 (CI∋0) / +0.006 | benchmark_report.md | near zero among board-decided games |
| Time-forfeit channel signal | ≈ −0.12 to −0.13 | benchmark_report.md | large signal in the time-forfeit channel |
| Stockfish depth | 12 | benchmark_report.md | depth-12 evaluation |
| License | MIT (original code/docs) | LICENSE / NOTICE.md | MIT-licensed original code and docs |

Every number above is taken from the cited repository file; recheck against `count_tables.md` before
publishing if the data is ever regenerated.

---

## 16. Claims to avoid

Do **not** say or imply:

- "novel", "first-ever", "first of its kind", "unique" study or method.
- "state-of-the-art" predictor / model.
- a **causal** effect — e.g. "time pressure causes worse moves", "low clock causes blunders",
  "proof that humans reason worse under time pressure".
- "Stockfish is ground truth" (it is objective context, not truth).
- "decision-tree model" or "neural-network model" as the project's core (it is neither).
- "solved" or "established" position sharpness (it is unresolved/underpowered here).
- a **universal** "skill buffers time pressure" / "rating protects against time pressure" claim (the
  direction is conditioning-sensitive).
- that the full 8.3M-row dataset is downloadable from GitHub (it is gitignored by design).

Prefer: "replication", "benchmark", "extension", "conditional association", "descriptive",
"apparently distinct within the sources I inspected".

---

## 17. Quick-grab summary line

> Reproducible 8.3M-move chess benchmark (145K+ games, 3 time controls, 2 months) separating mechanical
> time-forfeit risk from board-play move quality — descriptive, replicated, non-causal, MIT-licensed.
