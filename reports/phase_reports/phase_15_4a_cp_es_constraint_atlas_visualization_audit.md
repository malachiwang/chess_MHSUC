# Phase 15.4A — CP / ES Constraint Atlas Visualization Audit

**Labels:** AUDIT / DESIGN | report-only (no plotting code, no figures, no data artifacts)
**Date:** 2026-06-17
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (design audit)

## 1. Executive summary

The dense 10+0 anchor substrate is ready for visualization: both months
(2024-09 + 2024-10) are extracted, validated, and cross-month-replicated, with every
conditioning field needed for the atlas already precomputed in the artifact. This
ticket (**15.4A, design-only**) specifies the CP/ES Constraint Atlas — its metrics,
filters, plot families, axis/bin designs, month-replication rule, tables, and the
module/CLI/validation architecture — so that **15.4B can implement it directly**. No
plotting code was written, no figures were generated, no data artifacts were created,
no models were run. The atlas is **descriptive/predictive, not causal**.

**Key readiness finding:** the dense artifacts already carry `clock_bucket`,
`rating_bucket`, `eval_band`, `phase`, `think_time_bucket`, `clock_fraction`,
`termination`, `is_time_forfeit`, and `result_class` — so 15.4B needs **no new joins
and no re-derivation** beyond reading. **Naming catch:** `src/chess_mhsuc/constraint_atlas.py`
already exists (the 15.1B *checkpoint* atlas); 15.4B must use a new module name
(recommended `dense_constraint_atlas.py`) to avoid clobbering it.

## 2. Existing dense substrate

| | 2024-09 | 2024-10 | Combined |
|---|---|---|---|
| Rows | 1,496,890 | 1,436,866 | **2,933,756** |
| Usable games (move≥5) | 25,611 | 24,552 | 50,163 |
| Accepted games | 25,945 | 24,842 | 50,787 |
| Engine evals | 1,514,689 | 1,454,008 | 2,968,697 |
| Runtime / eps | ~12.7 h / 33.4 | ~8.8 h / 46.1 | — |
| File size | 149 MB | 144 MB | — |
| Columns | 65 | 65 | — |
| Validation | clean (0 replay/eval fail, 0 dup keys, 100% hash, sign correct both colors) | same | — |

Cross-month replication is essentially exact: ES loss mean 0.0346 / median 0.0114 /
p90 0.0926 in **both** months; rows/game 58.4 vs 58.5; mate-band 5.4% vs 5.2%.
(Source: `reports/dense_move_loss_2024_09_250k_v1.md`,
`reports/dense_move_loss_2024_10_250k_v1.md`, and the 15.3C/15.3D phase reports.)

## 3. Scientific purpose of the atlas

The atlas is a **legibility bridge** from the settled C4 move-quality result to a
visual, per-ply picture:

- At final-outcome level, the clock signal is substantially the flagging/time-forfeit
  channel (11.2B; survives clustering 11.3B).
- At next-move level, **eval state dominates** move-quality loss (15.1B/15.1D), and
  after controls the clock retains a **small replicated** association with next-move
  expected-score loss (15.1D/15.1F).

The dense substrate lets us show **how next-move move-quality loss varies across
clock, rating, eval state, phase, and think-time** at every ply (both colors), rather
than only at four White-to-move checkpoints. It is a descriptive map, not a causal
demonstration.

## 4. Non-claims and caveats

The atlas and its report must state it is: **not causal**; not reasoning-quality
ground truth; not Stockfish-as-ground-truth (depth-12 eval is objective context, not
truth); **not** a model of human obviousness; **not** cross-time-control (10+0 only);
**not** sharpness-conditioned (Phase 15.5); **not** a final/public report; **not**
model selection; and **not** evidence that "low clock causes blunders" or that "time
pressure causes worse reasoning." Loss is right-skewed; medians/percentiles accompany
means. Low-clock cells are a survivor population (board-decided games that didn't flag)
and must be read with that caveat.

## 5. Available fields and schema readiness

All present in both artifacts (65 columns). Exact field names:

| Need | Field(s) | Notes |
|---|---|---|
| game id / month / ply / move number | `game_id`, `month`, `ply`, `move_number` | |
| mover color | `mover_color`, `side_to_move`, `opponent_color` | |
| rating | `mover_elo`, `opponent_elo`, `white_elo`, `black_elo`, `elo_diff_mover` | |
| rating bucket | `rating_bucket` | precomputed 200-Elo `"{lo}_{lo+199}"` |
| clock before/after | `clock_before_s`, `clock_after_s` (+ both-side `white_/black_clock_before/after_s`) | bucket on `clock_before_s` (time available to decide) |
| think time | `think_time_s`, `think_time_gross_s`, `think_time_net_s` | gross == net for 10+0 |
| time control | `time_control_raw`, `initial_time_s`, `increment_s`, `time_control_family`, `speed_category` | all uniform 600+0 / 600 / 0 / no_increment / rapid |
| clock fraction | `clock_fraction` | `clock_before_s/600`; future-proof |
| increment | `increment_buffer`, `low_increment_buffer_flag` | null for 10+0 |
| termination / result / channel | `termination` (Normal/Time forfeit/Rules infraction), `is_time_forfeit`, `result_class`, `mover_result` | **present — no join needed** |
| eval before/after | `eval_before_cp`/`_mate`, `eval_after_actual_cp`/`_mate` | White-POV |
| raw / clipped cp loss | `cp_loss_raw`, `cp_loss_clipped` | mover-perspective |
| expected-score | `expected_score_before`, `expected_score_after_actual`, `expected_score_loss` | mover-perspective |
| mate-band flag | `is_mate_band` | |
| phase / move-number | `phase` (opening/middlegame/endgame), `move_number`, `dense_position_type` (="dense") | |
| eval band | `eval_band` (near_equal/slight/clear/decided/mate_band) | precomputed |
| clock bucket | `clock_bucket` (under_60/60_180/over_180) | coarse; finer buckets derivable from `clock_before_s` |
| think-time bucket | `think_time_bucket` | precomputed |
| player hashes | `mover_player_hash`, `opponent_player_hash` | one-way; for clustering |
| split | `split_set` | train/val/test/unknown |
| status | `status`, `failure_reason` | all `ok` in final artifacts |
| move tags | `move_is_capture/check/promotion/castle` | optional facets |

**Nothing is missing.** The precomputed `clock_bucket` is only coarse (3 levels); the
atlas's finer clock axis (§10) is derived from `clock_before_s` at plot time.

## 6. Metric policy: expected-score loss, clipped CP loss, raw CP loss

- **Primary y-axis: `expected_score_loss`** (mover perspective). Scientifically
  preferred — cp is nonlinear in win-probability, so ES loss is comparable across eval
  regimes.
- **Secondary y-axis: `cp_loss_clipped`** — intuitive and comparable to chess
  literature; report **median / p75 / p90** (skewed; mean shown alongside).
- **Diagnostic only: `cp_loss_raw`** — signed and noisy (negative when the actual move
  beat the prior static eval, ~21% of rows); **never headline**; eval-band panels only.
- **Large-loss binary panels:** `expected_score_loss >= 0.05`, `>= 0.10`;
  `cp_loss_clipped >= 100`, `>= 200`.
- **`%`-eval-swing is forbidden as a headline metric** (standing policy).

## 7. Filtering and inclusion policy

Defaults for headline figures:

- include `status == "ok"` rows (all rows in the final artifacts);
- **exclude `is_mate_band` rows from headline** loss figures; include them in separate
  mate-band diagnostics with counts;
- include **both colors** (values already mover-perspective; verified by near-equal
  per-color ES means);
- **retain but flag** clock anomalies (`clock_before_s`/`after_s` > 600, negative
  think-time); make anomaly-sensitive plots (clock, think-time) able to **optionally
  exclude** anomalies via a flag, but never silently drop them;
- state the **figure-level denominator** explicitly in each caption (e.g. "OK,
  non-mate-band rows, both months, n=…").

Combined denominators to expect: 2,933,756 OK rows; 154,984 mate-band (5.3%) excluded
from headline → ~2,778,772 headline rows; ~401,842 time-forfeit rows (13.7%) kept (with
a board-decided/time-forfeit split available).

## 8. Core plot families

(Designs only; implement in 15.4B. Headline = ES loss; CP variants secondary.)

- **A — Clock vs ES loss:** x = `clock_before_s` buckets (§10); y = mean + median ES
  loss with bootstrap CI ribbons; Sep/Oct overlaid or faceted; line variants per rating
  bin or per eval band.
- **B — Clock vs clipped CP loss:** x = clock bucket; y = median / p75 / p90 cp loss
  (skew-aware).
- **C — Large-loss probability vs clock:** y = P(ES≥0.05), P(ES≥0.10), P(cp≥100);
  facets month / rating band / eval band.
- **D — Rating × clock heatmap:** x = clock bucket, y = rating bin, color = mean ES
  loss (and a large-loss-probability variant); one panel per month + a replication
  table.
- **E — Eval-band-conditioned curves:** separate panels for near_equal / slight /
  clear / decided (+ mate-band diagnostic); prevents mixing cp/ES across eval regimes
  (the dominant axis from 15.1B/15.1D).
- **F — Phase / move-number curves:** x = move-number bucket or `phase`; y = loss;
  facet by clock or rating; **separates low-clock from late-game**.
- **G — Think-time curves:** x = `think_time_gross_s` (= net for 10+0) buckets; y =
  loss; with the think-time anomaly caveat.
- **H — Termination-channel diagnostics:** all-games headline vs board-decided-only
  (`is_time_forfeit == False`) vs time-forfeit-only panels — **feasible directly**
  (fields present); descriptive, no causal inference.
- **I — Month-replication panels:** Sep + Oct side-by-side/overlaid; required for every
  headline figure.

## 9. Month-replication design

**Rule:** every headline plot must either (1) show 2024-09 and 2024-10 **separately**
(facet/overlay), or (2) show a pooled result **with a small replication table** giving
the month-specific values. **Pooled-only visuals are not allowed as primary.** This
operationalizes the project's standing cross-month replication discipline.

## 10. Clock-axis design

Primary 10+0 absolute-clock buckets on `clock_before_s` (the time available to decide):

```
0_5, 5_10, 10_30, 30_60, 60_180, 180_300, 300+
```

Grounded cell counts (combined, all rows): 0_5 = 6,184; 5_10 = 8,148; 10_30 = 28,965;
30_60 = 47,700; 60_180 = 190,161; 180_300 = 344,664; 300+ = 2,307,934. So the sub-10s
buckets are usable for **marginal** clock curves but **thin when faceted** by
rating×eval — in faceted figures, collapse to a coarser low end (e.g. `under_10`,
`10_30`, `30_60`, `60_180`, `over_180`) or merge `0_5`+`5_10`. Apply the existing
cell-count policy (hide <50 / descriptive 50–299 / CI ≥300).

`clock_fraction` buckets (secondary / future cross-time-control compatibility; for
10+0 these are co-linear with seconds ÷600):

```
0_1%, 1_2%, 2_5%, 5_10%, 10_30%, 30_50%, 50%+
```

**For 10+0, absolute seconds are primary; `clock_fraction` is secondary/future-proof.**

## 11. Rating-bin design

**Primary: raw 200-Elo bins** (interpretability):

```
<1000, 1000_1199, 1200_1399, 1400_1599, 1600_1799, 1800_1999, 2000_2199, 2200+
```

Grounded counts (combined 200-Elo): 400=7,095; 600=37,483; 800=136,566; 1000=287,003;
1200=417,699; 1400=590,988; 1600=623,679; 1800=529,595; 2000=235,515; 2200=58,460;
2400=8,333; 2600=1,340. So **collapse `<1000` and `≥2200` (or `≥2400`)** in faceted
figures (the tails are thin, especially crossed with low clock — e.g. under_60 × 400 =
171, × 2600 = 199). **200-Elo is the stable headline; use 100-Elo only for marginal
(non-faceted) rating curves** where counts are large. Use `rating_bucket` directly
where its 200-Elo edges suffice, else bin `mover_elo` at plot time. For future
cross-time-control work, add **within-time-control quantile bins** as a secondary
normalized view — **never hide the raw-rating plots.**

## 12. Eval-band design

Use the **precomputed `eval_band`** (mover-perspective `|cp|`): `near_equal` (≤100),
`slight` (≤300), `clear` (≤700), `decided` (>700), `mate_band` (diagnostic).
Combined counts: near_equal 933,299; clear 932,186; slight 738,517; decided 174,770;
mate_band 154,984. **Why it matters:** 100 cp in a near-equal position is not
equivalent to 100 cp in a decided one — eval-band conditioning is the dominant axis
(15.1B/15.1D) and prevents cp/ES mixing across regimes.

## 13. Phase / move-number design

Move-number buckets:

```
5_10, 11_20, 21_30, 31_40, 41_60, 61+
```

or the precomputed `phase` (opening ≤10 / middlegame 11–30 / endgame >30). Purpose:
**separate low-clock from late-game phase** (they are confounded — late moves tend to
have less clock). Facet phase × clock so the two axes are not conflated.

## 14. Think-time design

For 10+0, `think_time_net_s == think_time_gross_s`. Buckets:

```
0_1, 1_2, 2_5, 5_10, 10_30, 30+
```

Caveats: think-time can be anomalous from clock-recording issues; high think-time may
reflect disconnection/lag/recording artifacts, **not** deliberation; ~125–133
negative-think and ~109–132 clock>600 rows per month are flagged. Do **not** interpret
think-time as deliberation quality directly; offer an anomaly-excluded variant.

## 15. Termination-channel design

**Fields exist in the dense artifact** (`termination`, `is_time_forfeit`,
`result_class`, `mover_result`) — **no join needed.** Design:

- headline figures: **all games**;
- diagnostic: **board-decided only** (`is_time_forfeit == False`, ~2.53M rows);
- diagnostic: **time-forfeit only** (`is_time_forfeit == True`, ~401,842 rows / 13.7%).

Purpose: check whether the move-quality curves are dominated by games ending on time
(consistent with the 11.2B flagging reframing). `termination` has only Normal / Time
forfeit / Rules infraction; `Normal` mixes mate/resignation (not separable) — never
claim separation. Descriptive only; no causal inference.

## 16. Table outputs (specify; create in 15.4B)

- row counts by month / rating bin / clock bucket / eval band / phase;
- mean / median / p90 ES loss by month × clock bucket;
- median / p90 clipped cp loss by month × clock bucket;
- large-loss rates (ES≥0.05/0.10, cp≥100/200) by month × clock bucket;
- sparse cells to collapse (counts < CI threshold), listed explicitly;
- anomaly counts by month (clock>600, negative think-time, mate-band, no-clock).

Tables: markdown in the report; CSV under the figure dir only if needed (15.4B).

## 17. Implementation architecture for 15.4B

**New module** `src/chess_mhsuc/dense_constraint_atlas.py` (do **not** reuse/overwrite
the existing checkpoint `constraint_atlas.py`). Reuse, do not duplicate: `eval_band`,
`rating_bin`, cell-count policy from `constraint_atlas.py`; the game-level and
mover-player-clustered bootstrap from `clustered_uncertainty.py`; the ES transform
constants from `next_move_loss.py`. Structure (pure functions + thin CLI; **no plotting
logic in notebooks**):

```
- load_dense(paths)            # read both months, validate schema, concat
- validate_schema(df)          # required columns, no usernames, bounds
- filter_headline(df, ...)     # status ok, drop mate-band, anomaly flag
- assign_buckets(df, ...)      # clock/rating/eval/phase/think buckets (mostly precomputed)
- aggregate_cell(df, by, metric)        # mean/median/p90/large-loss + n
- bootstrap_ci(df, by, metric, cluster) # game-level + mover-player-clustered
- render_<family>(...)         # matplotlib figure per plot family A–I
- render_tables(...)           # markdown/CSV tables
- write_report(...) / main()   # CLI
```

Plotting library: **matplotlib** (already in the stack). Every figure: month-aware
(§9), cell-count-gated, CI-bearing, mover-perspective, ES-primary.

## 18. CLI design for 15.4B (proposal only)

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_constraint_atlas \
  --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \
  --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \
  --out-dir reports/figures/phase_15_4_constraint_atlas \
  --report reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md \
  --bootstrap 1000 \
  --seed 20240617
```

Suggested flags: `--clock-axis seconds|fraction` (default seconds), `--rating-bin 200|100`
(default 200), `--exclude-anomalies` (default off), `--figure-format png|svg|both`
(default per repo convention — open question §23).

## 19. Output file naming for 15.4B (proposal only)

Figure dir: `reports/figures/phase_15_4_constraint_atlas/`
Report: `reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md`
Figures (PNG default; recommend committing small PNGs — confirm in §23):

```
fig_15_4_01_clock_vs_es_loss_by_month.png
fig_15_4_02_clock_vs_clipped_cp_loss_by_month.png
fig_15_4_03_large_loss_probability_by_clock.png
fig_15_4_04_rating_clock_heatmap_es_loss.png
fig_15_4_05_eval_band_clock_es_loss.png
fig_15_4_06_phase_clock_es_loss.png
fig_15_4_07_think_time_es_loss.png
fig_15_4_08_termination_channel_diagnostic.png
```

(SVG/PDF acceptable if Malachi prefers vector; PNG keeps the committed footprint small.)

## 20. Validation checks for 15.4B

15.4B must validate: both dense artifacts load; schemas match across months; required
columns present; **row counts match 15.3C/15.3D reports** (1,496,890 + 1,436,866 =
2,933,756); no raw-username columns; `expected_score_loss` bounded [0,1]; `cp_loss_clipped`
≥ 0; mate-band excluded from headline; per-cell counts reported and sparse cells
collapsed/labeled (hide <50 / descriptive 50–299 / CI ≥300); **month-specific plots
produced**; no model fitting; no data-artifact staging; figure files created **only**
under the figure/report directory.

## 21. What 15.4B must not do

No cross-time-control analysis; no sharpness joins; no MultiPV; no controlled
regressions; no causal language; no threshold changes; no ES-transform refit; no
modification of the dense artifacts; no public-facing synthesis; no packaging/outreach
report.

## 22. Recommended 15.4B ticket scope

**15.4B — CP/ES Constraint Atlas Visualization Implementation:** implement
`dense_constraint_atlas.py` + tests; generate the first-pass figures (families A–I)
and tables for 2024-09 + 2024-10 with month replication; write
`reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md`; update ROADMAP + EXPERIMENT_LOG;
run tests; preserve data safety (figures under the figure dir only; dense artifacts
untouched; nothing staged). 15.4B must **not** do Phase 15.5 sharpness or Phase 16
cross-time-control.

## 23. Open questions for Malachi

1. **Rating bins:** headline at **200 Elo** (recommended — stable cells), or adaptive
   100/200 by cell count for the marginal rating curves?
2. **Primary clock axis:** **absolute seconds** (recommended for 10+0) with
   `clock_fraction` as a secondary panel — confirm?
3. **Figure format:** **PNG only** (small committed footprint) or PNG + SVG/PDF (vector
   for a future write-up)?
4. **Termination panels in 15.4B:** include now (fields are present, cheap —
   recommended) or defer to a later ticket?
5. **Report register:** first atlas report **technical-only**, or partially
   human-readable (some plain-language framing alongside the technical tables)?

## Non-claims (summary)

Design-only audit; no figures, no models, no data artifacts. The atlas is
predictive/descriptive, not causal; Stockfish eval is objective context, not ground
truth; no "low clock causes blunders" / "time pressure causes worse reasoning" / "human
obviousness modeled" / "sharpness moderation confirmed-or-disproven" / "DRAW solved" /
"best predictor." **C4 unchanged. C3c unchanged.** PREREGISTRATION unchanged.
