# Phase 15.3C-A — Dense Extraction Strategy / Visualization Architecture Decision Audit

**Labels:** AUDIT / DESIGN / DECISION | report-only (no code, no Stockfish, no extraction, no models, no figures, no data artifacts)
**Date:** 2026-06-16
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (decision audit)

## 1. Executive summary

The 15.3B pilot proved the dense move-by-move loss pipeline is correct and measured
its cost: **~22.2 h for both 10+0 months at depth 12**. That is now a real
compute-and-design decision, not an automatic proceed. This audit recommends:

- **Extraction (15.3C): primary = Option E — one month (2024-09) first, full dense,
  depth 12, chunked + resumable + `caffeinate`**, then 2024-10 as a follow-up after
  validation. **Fallback = Option C — depth-10 full + a depth-12 validation subset**
  if the depth-12 one-month run proves too costly or unstable.
- **Keep depth 12** for scientific continuity: every prior layer (checkpoint
  next-move loss 15.0C, MultiPV sharpness 14.1C, the cp→ES transform scale 348.41)
  was built at depth 12, and the ES transform was *fit on depth-12 cp values* — using
  depth-10 evals through that transform would be a calibration mismatch.
- **Full population dense, not stratified**, so the Constraint Atlas curves need no
  weighting and report honest cell counts.
- **Make the dense schema time-control-aware now** (in 15.3C) — add `time_control_raw`,
  `initial_time_s`, `increment_s`, `clock_fraction`, `increment_buffer`, net/gross
  think-time, and low-clock flags — so the artifact does not become a 10+0-only dead
  end even though every current row is 600+0.
- **Treat visualizations as first-class 15.4A/15.4B deliverables**, with **raw rating
  bins primary** and **within-time-control percentile bins as an optional normalized
  view**, and clock shown in **absolute + fraction + increment-buffer** forms.
- **Preserve the Phase 16 cross-time-control architecture** (1+0 … 15+10) without
  implementing it now.

This ticket changes no code, runs nothing, and creates only this report.
Predictive/descriptive framing only — not causal; Stockfish eval is objective
position context, not absolute ground truth.

## 2. Pilot result recap (15.3B)

15.3B implemented `dense_move_loss.py` and validated the pipeline on the first 1,500
accepted 2024-09 600+0 games (both colors, `move_number >= 5`, depth 12, Option A —
one eval per pre-move position with the post-move eval reused from the next position):

- 86,977 rows across 1,486 games with usable move≥5 rows (14 of 1,500 too short);
- 88,012 engine evals (+85,491 cache-reuse hits, 451 terminal positions);
- 41.7 evals/s over the full position distribution; ~40 min runtime;
- **~22.2 h extrapolated depth-12 both-month full run** (~11.1 h/month);
- 0 replay failures, 0 eval errors, 0 duplicate keys;
- 100% mover/opponent player-hash coverage; no raw usernames;
- mover-perspective sign correct for **both** colors (ES mean 0.0345 White / 0.0348
  Black); ES bounded [0, 0.788]; clipped cp never negative;
- descriptive eval-band pattern reproduced the checkpoint finding (`slight` peak,
  `decided` lowest).

**The pilot passed validation, so a 15.3B2 pilot-fix ticket is not needed.**

Read-only artifact distributions used in this audit (no outputs written):
clock_before p10/median/p90 = 192 / 462 / 582 s; clock buckets `under_60` 2,549 (2.9%)
/ `60_180` 5,395 (6.2%) / `over_180` 79,033 (90.9%); 12 raw rating bins spanning
400–2799; result_class WHITE_WIN 40,940 / BLACK_WIN 40,297 / DRAW 5,740 (6.6%);
`is_time_forfeit` True 11,676 (13.4%). **No time-control / increment columns exist
in the artifact** (all rows are 600+0 with absolute-second clocks) — the direct
evidence for the §9 schema additions.

## 3. Why 15.3C requires an explicit strategy decision

The pilot removed all *correctness* risk but surfaced three *decision* risks:

1. **Cost:** ~22 h at depth 12 is a long campaign that a single uninterrupted session
   cannot cover; macOS sleep already suspended a multi-hour run once (14.1C).
2. **Depth/continuity trade-off:** depth 10 is ~2–3× faster but breaks comparability
   with depth-12-anchored prior work and the depth-12-fit ES transform.
3. **Design lock-in:** writing the full dense artifact with a 10+0-only schema would
   force a re-extraction when the project extends to other time controls.

Each must be decided before 15.3C executes, not during.

## 4. Extraction options considered

### Option A — Full depth-12, both months, single campaign
- **Pros:** strongest continuity with depth-12 checkpoint/sharpness work; no
  depth-change uncertainty; one artifact pair.
- **Cons:** ~22 h; needs `caffeinate`/chunking/overnight plan; a late bug is expensive
  (re-run both months).

### Option B — Full depth-10, both months
- **Pros:** ~2–3× faster; quick path to a dense atlas; cheap iteration.
- **Cons:** loss magnitudes shift; **the cp→ES transform was fit on depth-12 cp** so
  depth-10 evals through it are mis-calibrated; weak continuity; mandatory depth
  re-validation.

### Option C — Hybrid: depth-10 full + depth-12 validation subset
- **Pros:** practical full coverage with a depth-10↔depth-12 calibration anchor.
- **Cons:** two depth regimes complicate headline wording and comparison to prior
  depth-12 results; still needs the transform-calibration caveat.

### Option D — Stratified depth-12 sample
- **Pros:** cheaper than full; can enrich rare low-clock / high-rating / sharp cells.
- **Cons:** not population-dense → curves need weighting; visualizations become
  sample-design-dependent; honest marginal cell counts are lost.

### Option E — One month depth-12 first, then the second
- **Pros:** preserves depth 12; halves immediate cost/risk; yields a real full-month
  artifact to validate before committing the second ~11 h; replication preserved by
  running month 2 next.
- **Cons:** delays cross-month replication by one run; asymmetric coverage until
  month 2 completes.

## 5. Depth decision: 12 vs 10 vs hybrid

**Decision: depth 12.** Rationale:

- **Transform calibration:** `next_move_expected_score_transform_2024_09_2024_10_v1.json`
  (scale 348.41) was fit on depth-12 cp values; the dense ES headline must use the
  same depth or the transform no longer maps cp→ES correctly.
- **Continuity:** the checkpoint atlas (15.1B/15.1D), the robustness arc (15.1F), and
  MultiPV sharpness (14.1C) are all depth 12; a depth-12 dense layer is directly
  comparable to all of them.
- **The depth-10 subtest (202.8 evals/s) was not distribution-matched** (first ~17
  games' positions) → its implied ~4.6 h is an optimistic lower bound; the realistic
  depth-10 saving is ~2–3× (≈8–12 h, per 15.3A), not ~5×.

Depth 10 / hybrid (Option C) is retained only as a **fallback** if depth-12 wall-clock
proves unworkable; if taken, it **requires** a depth-10-vs-depth-12 calibration subset
and a re-fit (or explicit re-use caveat) of the cp→ES transform.

## 6. Full dense vs stratified decision

**Decision: full population dense (not stratified).** The Constraint Atlas is a
*descriptive curve* deliverable; population density means the curves need no weighting
and every cell reports an honest count under the existing policy (hidden <50 /
descriptive 50–299 / CI ≥300 with game-level — and player-clustered — bootstrap). Low-
clock cells are sparse (under_60 ≈ 3%) but dense already yields ~5× the checkpoint
count there, and pooling both months plus the clustered bootstrap covers uncertainty.
Stratified enrichment (Option D) is retained only as an **optional later supplement**
for rare cells (e.g., high-sharpness low-clock), never the primary artifact.

## 7. Chunking and machine-awake plan

A depth-12 month is ~11 h, so 15.3C must be **resumable** and **sleep-proof**:

- **`caffeinate`:** run under `caffeinate -dimsu` (or keep the lid open, plugged in) so
  display/idle/disk sleep cannot suspend the engine (the 14.1C failure mode).
- **Chunking + resumability:** process accepted games in chunks (e.g. **5,000 accepted
  games per shard**), writing one gitignored shard parquet per chunk, then concatenate
  shards into the final month artifact. On restart, skip game_ids already present in
  completed shards. This bounds the loss from any interruption to one chunk (~2 h),
  not the whole month. (The 15.3B module writes a single artifact at the end and holds
  rows in memory; ~1.5M rows/month is fine in memory, but chunked shard-writing is the
  resumability mechanism to add in 15.3C.)
- **Preflight mini-chunk:** before the long run, re-extract the first 1,500 games and
  confirm the 15.3B pilot counts reproduce within tolerance (row count, evals, ES
  mean/median, anomaly counts) — a cheap guard that the full-run code path is sound.

## 8. Recommended 15.3C extraction scope

```
Recommended 15.3C (primary = Option E):
- Strategy : one-month depth-12 full dense first; second month only after month-1 validation.
- Month    : 2024-09 first.
- Universe : ALL accepted 600+0 games (accepted_basic ∩ time_control==600+0; ~25,945),
             move_number >= 5, both colors.
- Depth    : 12 (Stockfish 18, /opt/homebrew/bin/stockfish).
- Eval     : Option A (one eval per pre-move position; post-move reused).
- ES        : reuse train-fit transform scale 348.41 (NOT refit).
- Chunking : ~5,000 accepted games per shard; resumable (skip completed game_ids); caffeinate.
- Preflight: first 1,500 games reproduce 15.3B pilot counts within tolerance.
- Mate-band: kept + flagged (is_mate_band), excluded from headline loss summaries.
- Terminal : terminal post-positions resolved without engine (checkmate/draw), counted.
- Schema   : add the §9 time-control-aware fields (forward-compat; all 600+0 now).
- Artifact : data/processed/dense_move_loss_2024_09_250k_v1.parquet  (gitignored)
- Report   : reports/dense_move_loss_2024_09_250k_v1.md             (committed, aggregate-only)
- Follow-up: 15.3C2 (or 15.3D) — 2024-10 full dense after 2024-09 passes; then a combined report.

Fallback (Option C) if depth-12 one-month runtime is unacceptable:
- depth-10 full both months + a depth-12 validation subset + cp→ES transform re-fit/caveat.
```

Estimated month-1 runtime ≈ 11 h at the pilot rate (chunked, caffeinated). Estimated
month artifact ≈ ~1.5M rows; storage modest (snappy parquet; `pre_fen` is the largest
column — a fen_hash-only variant is available if size becomes a concern).

## 9. Required dense schema additions for future time controls

Add (or reserve) these fields in 15.3C so the artifact is time-control-aware from the
start. Source = the PGN `TimeControl` header (already streamed; also present in
`game_records.time_control`). For 10+0: `initial_time_s=600`, `increment_s=0`,
`time_control_family="no_increment"`, `speed_category="rapid"`,
`increment_buffer=null`, `think_time_net_s == think_time_gross_s`.

| Field | Definition |
|---|---|
| `time_control_raw` | Original PGN `TimeControl` string, e.g. `600+0`, `180+2`, `900+10`. |
| `initial_time_s` | Base starting seconds parsed from `TimeControl`. |
| `increment_s` | Increment seconds parsed from `TimeControl`. |
| `time_control_family` | `no_increment` (increment_s==0) or `increment`. |
| `speed_category` | `bullet` / `blitz` / `rapid` / `classical` / `unknown`, by a documented rule on estimated game duration `initial_time_s + 40*increment_s` (Lichess-style: <29 s eq. bullet, <179 s blitz, <1499 s rapid, else classical). |
| `clock_fraction` | `clock_before_s / initial_time_s` (∈ ~[0,1+], increment can push >1). |
| `increment_buffer` | `clock_before_s / increment_s` for increment games; **null** for no-increment. |
| `think_time_gross_s` | Elapsed decision time = previous same-player `clock_after` − current `clock_after` (the raw clock drop). |
| `think_time_net_s` | Increment-aware: increment games = `prev_clock_after + increment_s − current_clock_after`; no-increment games = `think_time_gross_s`. |
| `low_clock_absolute_flag` | `clock_before_s < 60` (absolute low-clock state). |
| `low_clock_fraction_flag` | `clock_fraction < 0.10` (relative low-clock state). |
| `low_increment_buffer_flag` | `increment_buffer < K` for increment games (e.g. K≈3); **null** for no-increment. |

For 10+0 the increment-specific fields (`increment_buffer`, `low_increment_buffer_flag`)
are null/not-applicable and `clock_fraction = clock_before_s/600`. Adding them now (all
constant or null in the 10+0 artifact) prevents a re-extraction when increment controls
arrive and lets visualization code branch on `time_control_family` without schema
surgery later.

## 10. Visualization architecture requirements

**Visualizations are first-class 15.4A/15.4B deliverables, not Phase 17 polish.**
Tooling: matplotlib (already in the stack); figures are small committed PNGs/SVGs;
the underlying dense data stays gitignored. Every curve carries game-level (and, where
relevant, mover-player-clustered) bootstrap CIs and obeys the existing cell-count
policy (hidden <50 / descriptive 50–299 / CI ≥300). Mover-perspective ES loss is the
headline metric; clipped cp secondary; raw cp only inside eval-band panels;
**percent-eval-swing forbidden as a headline.**

### Core 10+0 dense visualizations (15.4A/B)
1. Time remaining (absolute) vs ES loss.
2. Time remaining vs clipped cp loss.
3. Time remaining vs large-loss probability (ES≥0.05/0.10, cp≥100/200).
4. Move number / phase vs loss.
5. Eval-band-conditioned cp/ES loss curves (the dominant axis from 15.1B/15.1D).
6. Rating-bin-conditioned cp/ES loss curves.
7. Rating × time heatmaps.
8. Think-time vs loss curves (think-time validated in 15.3B; 7 flagged anomalies).
9. Board-decided vs time-forfeit comparison panels.
10. Mate-band-separated diagnostics.

### Later sharpness visualizations
1. Sharpness-conditioned time–loss curves.
2. Sharpness × clock heatmaps.
3. Sharpness × rating × time panels.
4. High-sharpness low-clock large-loss rates.

### Later cross-time-control visualizations
1. Absolute-clock panels per time control.
2. Clock-fraction panels per time control.
3. Increment-buffer plots for increment games.
4. Raw rating-bin views across time controls.
5. Within-time-control percentile views across time controls.
6. Increment vs no-increment comparison panels.
7. Speed-category comparison panels.

## 11. Raw rating bins vs percentile bins

Per Malachi's correction:

- **Raw rating bins are first-class and usually primary** (interpretability). Bins:
  `<800, 800-999, 1000-1199, 1200-1399, 1400-1599, 1600-1799, 1800-1999, 2000-2199,
  2200+` (the pilot spans 400–2799). They answer *"how do players with this displayed
  rating behave under constraints?"*
- **Percentile / quantile bins are an optional normalized view** (bottom 20% / 20–40 /
  40–60 / 60–80 / top 20%, computed **within each time-control pool**), especially for
  cross-time-control analysis. They answer *"how does relative skill position within a
  pool moderate constraint degradation?"*
- Design knob: `rating_mode = raw_bins | percentile_bins` (later optional `zscore`).
  Percentile edges must be **train-defined** and applied to val/test (split discipline).
- **Caveat (does not suppress raw plots):** raw Lichess ratings are not perfectly
  latent-skill-matched across time-control pools — a 1600 bullet and a 1600 rapid
  player are not assumed identical strength. Raw-bin plots remain useful and required;
  the caveat is stated, not used to hide them.

## 12. Time-control-aware clock features

Absolute remaining clock alone is insufficient across time controls because
**8 seconds in 10+0 is a different constraint state from 8 seconds in 3+2 or 10+5.**
Required clock views:

- **No-increment games:** `clock_before_s`, `clock_fraction`, `think_time_s`.
- **Increment games:** `clock_before_s`, `clock_fraction`,
  `increment_buffer = clock_before_s / increment_s`, `think_time_net_s`.

Cross-time-control plots must therefore offer three lenses: **absolute clock**,
**normalized clock-fraction**, and (increment only) **increment-buffer**. For the
10+0 artifact, absolute and fraction are co-linear (÷600), but the fraction column
must exist so the same plotting code generalizes.

## 13. Increment-specific design requirements

- `think_time_gross_s` (raw clock drop) vs `think_time_net_s` (adds back the increment
  for increment games) — they **coincide** for no-increment controls and **diverge**
  for increment controls; the headline think-time metric for increment games should be
  net.
- `increment_buffer` and `low_increment_buffer_flag` capture "how many increments of
  cushion" a mover has — a constraint dimension that does not exist in no-increment
  play and must not be conflated with absolute seconds.
- Visualization must branch on `time_control_family`; never overlay an absolute-clock
  curve from 10+0 directly onto a 3+2 curve without the fraction/buffer normalization.

## 14. Cross-time-control extension plan (Phase 16 — preserved, not implemented)

Candidate controls: `1+0, 3+0, 5+0, 10+0` (no-increment) and `3+2, 5+3, 10+5, 15+10`
(increment). Staged plan to preserve:

```
16.1A — Time-Control Source Availability / Sampling Audit
16.1B — Multi-Time-Control PGN Cache Assembly
16.2A — Cross-Time-Control Dense Extraction Pilot
16.2B — Cross-Time-Control Dense Extraction Implementation
16.3A — Cross-Time-Control Visualization Audit
16.3B — Cross-Time-Control Visualization Implementation
16.4A — Cross-Time-Control Modeling Audit
16.4B — Cross-Time-Control Modeling Implementation
```

The §9 schema and §10–13 visualization knobs are the forward-compatibility hooks that
let this plan reuse the dense pipeline rather than rebuild it. **Not implemented now**;
within-pool rating-quantile caveat remains mandatory for any cross-TC comparison.

## 15. Validation requirements for 15.3C

15.3C must validate (reusing the 15.3B summary machinery): row uniqueness; replay
failures; eval failures; duplicate keys; player-hash coverage; **no raw usernames**;
both-color orientation (ES means close across colors); ES bounds [0,1] and
nonnegative; clipped cp nonnegativity; raw-cp negative rate (sanity, not error);
mate-band share; terminal-skipped rows; clock-anomaly and think-time-anomaly rates;
rows by month / mover color / phase / eval band / rating bin / clock bucket /
result_class; **new time-control fields populated correctly** (initial 600, increment
0, family no_increment, clock_fraction in range, increment fields null) for the 10+0
artifact; runtime and evals/s; **pilot reproduction on the first 1,500 games within
tolerance**; and a **depth comparison only if depth-10/hybrid is chosen**.

## 16. Decision gates after 15.3C (before 15.4A visualizations)

- dense month artifact exists and concatenated cleanly from shards;
- validation passes (above);
- aggregate report(s) written (committed; data gitignored);
- row counts plausible (~1.5M/month; ~58 rows/game);
- no metric-orientation bug (both-color ES means close);
- no clock-reconstruction bug (anomaly rates ≈ pilot's tiny levels);
- full runtime acceptable and machine-awake plan held;
- artifact size acceptable (or fen_hash-only variant adopted);
- time-control-aware fields present and correct;
- **Malachi approves proceeding to 15.4A.**

## 17. Risks and mitigations

| Risk | Mitigation |
|---|---|
| ~22 h compute / sleep suspension | one-month-first; chunked resumable shards; `caffeinate`; preflight mini-chunk. |
| Depth change breaks continuity / ES calibration | keep depth 12 (transform fit at d12); depth-10 only as fallback with re-fit + calibration subset. |
| Low-clock cell sparsity (under_60 ≈ 3%) | full population dense + pool both months + clustered bootstrap; optional later stratified enrichment for rare cells. |
| DRAW sparsity (~6.6%) | report DRAW cells descriptively; never claim a DRAW result. |
| 10+0-only schema lock-in | add time-control-aware fields in 15.3C (constant/null now, populated later). |
| Raw rating not skill-matched across pools | raw bins primary + percentile bins optional + stated caveat; never suppress raw plots. |
| Memory for full-month rows | chunked shard writes; concatenate at end; fen_hash-only fallback. |
| Late bug in a long run | preflight reproduction of 15.3B counts before committing the full month. |

## 18. Recommended next ticket

**15.3C — Full Dense Move-by-Move Loss Extraction** (implementation): one-month
(2024-09) depth-12 full dense, chunked/resumable under `caffeinate`, with the §9
time-control-aware schema additions and a preflight reproduction of the 15.3B pilot
counts; then **15.3C2/15.3D — 2024-10 full dense** after month-1 validation, followed
by a combined report. Fallback Option C (depth-10 full + depth-12 validation subset)
only if depth-12 one-month runtime proves unacceptable.

## 19. Non-claims

- This ticket does **not** run full dense extraction, produce final dense
  visualizations, run dense controlled models, or extend to new time controls.
- No causal claim. No "low clock causes blunders." No "time pressure causes worse
  reasoning." No "Stockfish is ground truth." No "human obviousness modeled." No
  "DRAW solved." No "best predictor."
- **C4 unchanged. C3c unchanged.** No thresholds or classifications changed.
- The settled metric policy (primary ES loss; secondary clipped cp; raw cp in
  eval-band panels only; percent-eval-swing forbidden as headline) is preserved.
