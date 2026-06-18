# Phase 16.1A — Time-Control Selection / Feasibility Audit

**Labels:** AUDIT / DESIGN | report-only (no code, no Stockfish, no extraction, no models, no figures, no data artifacts)
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (selection / feasibility audit)

## 1. Executive summary

Phase 15 closed the dense 10+0 move-quality arc (eval dominates; small monotone fragile
clock residual; final-outcome clock signal tied to flagging) and the sharpness arc (C3c
unresolved). Phase 16 asks whether these patterns vary **across time controls**
(dose-response). This audit selects the feasible, scientifically-useful time-control set
before any expensive extraction. **Key feasibility finding (read-only):** the existing raw
caches (`data/raw/lichess/lichess_2024_09/10_first250k.pgn`) **already contain all time
controls** — the `game_records` artifacts were merely *parser-filtered* to 600+0. Per month
the caches hold ~**52k 3+0**, ~**33k 5+0**, ~**26k 10+0** (anchor), ~20k 3+2, ~11k 5+3,
~**4.8k 10+5**, ~**1.3k 15+10**, ~73k 1+0. So a **no-increment speed dose-response
(3+0 / 5+0 / 10+0)** is fully feasible **from existing local data with no new download**;
10+5/15+10 are too rare in the first-250k caches for well-powered standalone controls.
**Recommended first wave: 3+0, 5+0, 10+0** (no-increment, abundant, same months), with an
increment contrast best served by **5+0 vs 5+3 / 3+0 vs 3+2** (abundant) rather than the
rare 10+5/15+10. Rating pools are **not** cross-comparable → **within-time-control rating
quantiles** are primary. No code/Stockfish/models/figures; nothing staged.

## 2. Why Phase 16 now

The 10+0 result is replicated but narrow. To learn whether the small clock residual is a
general bounded-resource pattern (a "dose-response") rather than a 10+0 artifact, we need
other time controls. But controls differ in game length, **rating pools**, increment
availability, **termination/flagging rates**, and clock dynamics — so **selection and
feasibility must precede extraction**, especially given the rating-pool comparability trap.

## 3. Current 10+0 anchor result

Dense artifacts 2024-09 (1,496,890 rows) + 2024-10 (1,436,866) = 2,933,756, both colors,
depth 12. Atlas (15.4B): marginal clock curve U-shaped/confounded; eval state dominates
(slight 0.044 → decided 0.017). Controlled (15.4D): focal `60_180 vs over_180` ES-loss
residual **+0.0009** (small, monotone, replicated, fragile under continuous-eval and
board-decided controls). Final-outcome clock signal tied to time-forfeit (11.2B). Sharpness
(15.5): main effect replicated but partly mechanical; **C3c unresolved**.

## 4. Candidate time controls

| TC | speed | 2024-09 cache games | 2024-10 | Phase-16 value |
|---|---|---|---|---|
| 3+0 | blitz (no-inc) | 52,293 | 51,751 | **abundant — core no-inc contrast** |
| 5+0 | blitz (no-inc) | 33,547 | 33,661 | **abundant — core, bridges blitz↔rapid** |
| 10+0 | rapid (no-inc) | 26,041 | 24,908 | **anchor (already extracted)** |
| 10+5 | rapid (inc) | 4,843 | 4,759 | moderate — increment contrast vs 10+0, lower power |
| 15+10 | rapid/classical (inc) | 1,317 | 1,351 | **too small** for standalone; defer/pool |
| 3+2 | blitz (inc) | 20,346 | 20,125 | abundant — increment contrast vs 3+0 |
| 5+3 | blitz (inc) | 11,511 | 10,979 | abundant — increment contrast vs 5+0 |
| 1+0 | bullet (no-inc) | 72,689 | 74,821 | abundant but qualitatively different (bullet); separate treatment |

No-increment speed ladder 3+0 → 5+0 → 10+0 is the cleanest dose-response and all three are
abundant. Increment contrast is **better powered at blitz** (3+0 vs 3+2, 5+0 vs 5+3) than at
rapid (10+0 vs 10+5, where 10+5 ≈ 4.8k). 15+10 (~1.3k) is too thin for a standalone control.

## 5. Data availability and artifact inventory

- **Raw caches:** `data/raw/lichess/lichess_2024_09/10_first250k.pgn` (556 MB each,
  gitignored) — **first 250,000 games of each month, ALL time controls** (verified by
  `TimeControl` header counts, §4). Clock annotations (`%clk`) present; usernames present
  in headers (stripped at parse; hashed downstream).
- **Parsed `game_records` (interim):** 600+0 ONLY (~26k/25k rows) — the parser/acceptance
  retained only 10+0. **No game_records exist for other controls yet.**
- **Dense move-loss / sharpness artifacts:** 10+0 only.
- **Conclusion:** other-control raw data is **already local** (in the caches); only the
  *parsed accepted-game sets* and dense artifacts are 10+0-only. **No new download is needed
  for 3+0/5+0** (abundant in caches). 10+5/15+10 would need a larger monthly slice (the
  original Lichess `.pgn.zst` source) to be well-powered.

## 6. Time-control parsing and schema readiness

- `dense_move_loss.py` already has `parse_time_control`, `time_control_family_for`,
  `speed_category_for`, `clock_fraction`, increment-aware fields (`increment_buffer`,
  `low_increment_buffer_flag`, `think_time_net_s`) — the **schema is already
  time-control-aware** (added in 15.3C-A/15.3C).
- **BUT the pipeline is hardcoded to 600+0 acceptance:** `load_accepted_game_meta` filters
  `accepted_basic & time_control == "600+0"`, and the full-month/preflight flags are locked
  to `2024_09`/`2024_10` × `600+0` × depth 12. So 16.1B **requires a code change** to:
  (a) derive an accepted-game set for an arbitrary target TC (re-parse the raw cache headers
  for that TC, or generalize `game_records`), and (b) generalize the run flags to a chosen
  `--time-control` (still safety-gated). The per-ply replay, clock reconstruction, and
  metric logic are TC-agnostic and reusable as-is.
- **Increment interpretation:** no-increment vs increment games need different clock reading
  — `think_time_net_s = think_time_gross_s + increment_s` (already implemented); the
  first wave (no-increment) keeps net == gross, so it is the lowest-risk starting point.

## 7. Rating-pool comparability problem (mandatory)

Lichess maintains **separate rating pools per speed category** (bullet/blitz/rapid/
classical). **A 1600 in 3+0 (blitz) is not equivalent to a 1600 in 10+0 (rapid).** Raw
ratings must **not** be treated as directly comparable across controls. Strategy:
- **Primary:** **within-time-control rating quantiles** (Q1–Q5 quintiles, or deciles if
  sample size supports), computed per control (and per month), train-defined.
- **Secondary/descriptive:** raw 200-Elo bins **within each control**, never pooled across.
- **Report:** both, with explicit rating-pool caveats and TC-specific denominators.

## 8. Absolute clock vs clock fraction vs increment-aware clocks

- **Absolute seconds** — valid **within** a fixed control; invalid for comparing 3+0 vs
  10+0 directly.
- **Clock fraction** `clock_before_s / initial_time_s` — the **cross-control** axis
  (3+0 ÷180, 5+0 ÷300, 10+0 ÷600); better but ignores increment.
- **Increment-aware** — for increment games, low base clock is survivable because increment
  replenishes; use `increment_buffer = clock_before_s / max(increment_s, 1)` and a low-buffer
  flag (e.g. `clock_before_s ≤ 2·increment_s`).
- **Recommended Phase-16 encodings:** within-control = absolute clock buckets; cross-control
  = clock-fraction buckets; increment-specific diagnostic = increment_buffer (increment
  controls only). **Never** silently equate "under 10 s" in 3+0 and 15+10. For the
  no-increment first wave, clock-fraction is the clean cross-control axis.

## 9. Termination-channel strategy

Carry the Phase 11/15 lesson (clock outcome signal dominated by time-forfeit). Phase 16
tracks, per control: all games / board-decided / time-forfeit; **termination rates by
control** (faster controls flag more — directly relevant); and controlled move-quality with
and without termination controls (+ board-decided-only robustness). Faster-control flagging
rates are themselves a dose-response signal to report descriptively.

## 10. Move-quality targets and metric policy

Reuse the Phase-15 policy: **primary `expected_score_loss`**, secondary `cp_loss_clipped`
(median/p75/p90), binary ES≥0.05/0.10 & cp≥100/200, raw cp diagnostic-only. **ES transform:**
the 10+0-fit logistic (scale 348.41) was fit on depth-12 cp; **reuse it across controls for
comparability at first, documented as a robustness assumption** (a depth-12 cp→ES mapping is
position-level and time-control-agnostic in principle). **Do not silently refit per control**;
a later audit may validate/relax this if cross-control cp distributions differ materially.

## 11. Sampling strategy options

- **Option A — full dense per control:** clean but a multi-day Stockfish campaign (§12); not
  the first step.
- **Option B — matched-size dense samples** (e.g. ~10k–25k accepted games/control/month,
  same months as 10+0): recommended for the eventual extraction.
- **Option C — stratified samples** (balance rating quantile / termination / phase / clock):
  efficient for sparse low-clock cells; more complex.
- **Option D — pilot first** (~1k–2k accepted games/control): measure rows, clock/termination
  distributions, runtime, and validate non-600+0 pipeline support. **Recommended first**,
  because the pipeline does not yet support non-600+0 (§6).

**Recommended: D → B.** Pilot 3+0 and 5+0 first (10+0 already done); then matched-size full
extractions for the selected set.

## 12. Compute-cost estimate

Anchors: 2024-09 10+0 ~1.50M rows / ~1.51M evals / ~12.7 h (33 eps); 2024-10 ~1.44M / ~8.8 h
(46 eps); 15.3B pilot ~1,500 games ~40 min. Blitz games are **shorter** (fewer plies/game)
than rapid, so rows/game and cost/game are lower for 3+0/5+0. Rough estimates (per month,
depth 12, chunked):
- **Pilot ~1.5k accepted games/control:** ~25–40 min each.
- **Full 3+0 (~50k accepted):** more games but shorter → on the order of the 10+0 full run
  (~8–14 h); **5+0 (~33k):** ~6–10 h; per month. A two-control × two-month full extraction is
  a **multi-day** campaign → must be **chunked/resumable + caffeinated**, and pilots must
  precede it. Exact costs are unknown until the pilot measures rows/game and eps per control.

## 13. Recommended Phase 16 time-control set

**First wave (no-increment speed dose-response): 3+0, 5+0, 10+0.** All abundant in existing
caches, same months, lowest pipeline risk (no increment), cleanest scientific contrast.
**Second wave (increment contrast, blitz — better powered): 5+0 vs 5+3 (and/or 3+0 vs 3+2).**
**Deferred:** 10+5 (moderate, ~4.8k), 15+10 (~1.3k, too thin) — revisit only if a larger
monthly slice is acquired or if pooled increment-rapid is specifically wanted. 1+0 (bullet)
is a separate qualitative regime — optional later, treated apart.

## 14. Recommended extraction/sample design

- **Months:** 2024-09 + 2024-10 (match the 10+0 anchor; same raw caches).
- **Depth:** **12** (comparability with 10+0; do not change without a later audit).
- **Pilot sizes:** ~1,500 accepted games/control/month (3+0, 5+0) first.
- **Full (post-pilot):** matched-size (Option B) — choose a common accepted-game count
  across controls (e.g. ~25k, capped by the scarcest selected control) for balanced power.
- **Filters:** target `time_control_raw`; `move_number ≥ 5`; both colors; chunked/resumable;
  `caffeinate`.
- **ES transform:** reuse 10+0 transform (documented assumption).
- **Artifact naming (gitignored; create in 16.1B+, not now):**
  `data/processed/dense_move_loss_2024_09_3plus0_v1.parquet`,
  `…_2024_10_3plus0_v1.parquet`, `…_5plus0_v1.parquet`, etc.

## 15. Recommended cross-time-control atlas design (future)

clock_fraction vs ES loss by control; absolute clock vs ES loss within each control;
termination rate by control; time-forfeit vs board-decided move-quality curves;
within-control rating-quantile × clock_fraction heatmaps; phase × clock_fraction by control;
month-replication panels. Future optional appendix — **Think-Time Loss-Rate / Flagging
Signature Diagnostic:** stabilized `clipped_cp_loss / max(think_time_net_s, 1)` and
`expected_score_loss / max(think_time_net_s, 1)`, split by termination channel and clock
bucket (per control) — **not implemented now**.

## 16. Recommended cross-time-control controlled model design (future)

```
expected_score_loss
  ~ C(time_control) + C(clock_fraction_bucket) + C(time_control) × C(clock_fraction_bucket)
  + C(eval_band) + C(phase) + C(within_control_rating_quantile) + C(month)
  + C(termination_channel) + anomaly_flags
```
plus **within-control** models (separate 3+0 / 5+0 / 10+0 fits) comparing clock coefficients
descriptively. Game-clustered (and mover-player) uncertainty. **No causal interpretation.**

## 17. What Phase 16 must not claim

No causal time-control effects; no raw-rating comparability across pools; no "faster time
controls cause worse chess"; no "increment causes better reasoning"; no conflating flagging
with board-play quality; no Stockfish-as-ground-truth; no cross-control synthesis before
month-replication; no sharpness claims (sharpness arc closed).

## 18. Recommended 16.1B scope

**16.1B — Cross-Time-Control Pilot Dense Extraction (3+0, 5+0).** Because the pipeline
hardcodes 600+0 acceptance (§6), 16.1B must: (a) **generalize the dense pipeline to a chosen
`--time-control`** (derive the accepted-game set for the target TC from the raw cache
headers; keep the safety gating — explicit per-(month,TC) allow, depth 12); add tests; (b)
run **small pilots** (~1,500 accepted games/control/month) for **3+0 and 5+0** (10+0 already
done); (c) produce pilot reports with row counts, clock-fraction/absolute-clock distributions,
**termination rates**, rating-pool/quantile distributions, and measured runtime/eps per
control; (d) **NOT** run full multi-control dense extraction yet. Full matched-size extraction
follows in 16.1C/16.2 after the pilot confirms readiness and cost.

## 19. Optional later branches (recorded, not implemented)

- Think-Time Loss-Rate / Flagging Signature Diagnostic.
- Stratified Dense Sharpness Extraction Feasibility Audit (15.5D, from 15.5C).
- Increment-rapid contrast (10+5 / 15+10) — needs a larger monthly slice for power.
- 1+0 bullet regime (separate treatment).
- Phase 17 packaging.

## 20. Open questions for Malachi (defaults in bold)

1. Prioritize the no-increment speed contrast first (3+0/5+0/10+0)? — **Yes (default).**
2. Include an increment contrast in the first wave? — **Not in wave 1; prefer blitz
   increment (5+0 vs 5+3) in wave 2 over the rare 10+5/15+10 (default).**
3. How much compute before Phase 17? — **Pilots first (~25–40 min/control); decide full
   matched-size extraction (multi-day, chunked/caffeinated) after pilot costs are measured.**
4. Think-time loss-rate diagnostic in Phase 16 or later? — **Later optional branch
   (default).**

## Non-claims

Report-only audit; no code/Stockfish/extraction/models/figures/data artifacts. Cross-control
comparisons are **descriptive/conditional associations, not causal**; raw ratings are **not**
cross-pool comparable; Stockfish eval is objective context, not ground truth; no
faster-control/increment causal claims; no sharpness claims. C4 and C3c unchanged.
PREREGISTRATION unchanged.
