# Phase 16.2A — Cross-Time-Control Move-Quality Atlas / Modeling Audit

**Ticket:** 16.2A — Cross-Time-Control Move-Quality Atlas / Modeling Audit (audit/design only)
**Status:** complete — DESIGN-ONLY. No analysis code written, no models fit, no figures generated,
no Stockfish, no extraction, no Parquet modified. Read-only inspection only.

> **This locks the scientific and statistical design for the first full cross-time-control
> analysis (16.2B) over the six no-increment dense datasets (3+0, 5+0, 10+0 × 2024-09/2024-10).
> All language is predictive/descriptive; nothing here is causal. Raw Lichess ratings are NOT
> comparable across pools — within-control rating quantiles are mandatory. Stockfish eval is
> objective context, not ground truth.**

## 1. Executive summary

- Six dense month/control artifacts are ready and validated (16.1C): 3+0, 5+0, 10+0 × 2024-09/2024-10,
  identical 65-column schema, same reused ES transform (scale 348.41).
- Phase 16.2 should compare the three controls using **`clock_fraction`** (= clock_before_s /
  initial_time_s) as the cross-control clock axis and **within-control × month rating quintiles** as
  the rating control. Absolute seconds are control-specific diagnostics only.
- **Termination behavior and board-move quality are separate scientific targets and must be modeled
  separately.** The headline cross-control difference appears to be in time-forfeit prevalence
  (game-level dose-response 3+0 ~29–30% > 5+0 ~22.6% > 10+0 ~11.5%), while average next-move
  expected-score loss is comparatively flat (~0.0336–0.0352). Neither is yet a modeled result.
- 16.2B should build (a) a descriptive atlas, (b) separate within-control controlled models, (c) a
  pooled time-control × clock-fraction interaction model, (d) a game-level termination model, plus
  core robustness — all with month-specific replication and game-clustered uncertainty, in a
  **dedicated new module** that reuses tested Phase 15.4 helpers without altering the stable 10+0 code.
- Cell-adequacy audit: all proposed fine (7-bucket) atlas cells and coarse (4-bucket) model cells are
  adequately powered in every control/month, including the board-decided-only crit-clock robustness
  population. One structural caveat dominates design: **`clock_fraction` and game phase are heavily
  confounded** — the critical-clock band is almost entirely endgame — so phase conditioning is
  mandatory and the extreme-low-clock estimand is effectively "low clock within the endgame."

## 2. Evidence and artifacts reviewed

- **3+0 / 5+0 matched-size extraction reports + artifacts:** `reports/dense_move_loss_2024_{09,10}_{3,5}plus0_24k_v1.md`; `data/processed/dense_move_loss_2024_{09,10}_{3,5}plus0_24k_v1.parquet` (read-only).
- **10+0 anchor reports + artifacts:** `reports/dense_move_loss_2024_{09,10}_250k_v1.md`; `data/processed/dense_move_loss_2024_{09,10}_250k_v1.parquet` (read-only).
- **Phase 15.4 atlas + controlled model:** `reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md`, `reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md`; `src/chess_mhsuc/dense_constraint_atlas.py`, `src/chess_mhsuc/dense_controlled_model.py`.
- **Phase 11 termination decomposition:** termination_decomposition reports (flagging-channel reframing).
- **Phase 16.1A/B/C reports** (selection/feasibility, pilot, full matched-size).
- **Governance:** ROADMAP.md, EXPERIMENT_LOG.md (through EXP-052), PREREGISTRATION.md.
- **Tests reviewed for conventions:** test_dense_constraint_atlas.py, test_dense_controlled_model.py, test_dense_move_loss.py.
- **Read-only diagnostics:** `/tmp/phase_16_2a_cell_adequacy.txt` (10-section cell/clustering audit; not committed).

## 3. Phase 16 scientific questions

Four distinct estimands, kept separate (do NOT collapse into one "time pressure effect"):

- **A. Unconditional descriptive comparison.** How do average move-quality loss, clock state, and
  termination rates differ across the observed 3+0, 5+0, 10+0 populations? (Atlas, no conditioning.)
- **B. Within-control clock association.** Within each control, how does `clock_fraction` relate to
  next-move loss after conditioning on eval band, phase, rating quintile, month, color, and
  termination channel? (Separate within-control models.)
- **C. Cross-control moderation.** Does the conditional `clock_fraction` gradient differ across 3+0,
  5+0, 10+0? (Pooled time-control × clock-fraction interaction.)
- **D. Termination-channel contrast.** Are cross-control differences concentrated in time-forfeit
  frequency rather than board-decided move-quality loss? (Game-level termination model + board-decided
  robustness.)

## 4. Dataset and denominator reconciliation (MANDATORY)

Read-only counts (headline population = status==ok ∧ ¬mate-band ∧ valid clock/rating/termination):

| Control | Month | Raw rows | Raw games | Headline rows | Headline games | Rows/game |
|---|---|---|---|---|---|---|
| 3+0 | 2024-09 | 1,495,648 | 23,708 | 1,422,173 | 23,703 | 60.0 |
| 3+0 | 2024-10 | 1,491,120 | 23,739 | 1,420,818 | 23,721 | 59.9 |
| 5+0 | 2024-09 | 1,437,932 | 23,767 | 1,367,293 | 23,756 | 57.6 |
| 5+0 | 2024-10 | 1,437,116 | 23,744 | 1,364,419 | 23,734 | 57.5 |
| 10+0 | 2024-09 | 1,496,890 | 25,611 | 1,416,313 | 25,582 | 55.4 |
| 10+0 | 2024-10 | 1,436,866 | 24,552 | 1,362,459 | 24,524 | 55.6 |

**Key fact:** row counts are nearly equal across controls (~1.36–1.42M), but **game counts are not**
(10+0 has ~25.6k/24.5k games vs ~23.7k for the capped 3+0/5+0), and **rows/game differ** (10+0 ~55 vs
3+0 ~60). The matched 24,000 accepted-game cap does NOT imply equal move-level denominators, because
faster controls have more plies per game (longer games / more flagging-driven endgames). 10+0 was
extracted at full month (no cap), so it has more games.

- **Option A (all rows + control/month weights):** no discarded data, within-control estimates
  unaffected; risk = pooled estimates overweight longer-game controls at the row level.
- **Option B (deterministically restrict 10+0 to 24,000 accepted games/month):** matched accepted-game
  denominator; risk = the dense artifacts do **not** store an explicit accepted-game ordering (only
  game_id + ply), so a defensible deterministic subsample would require re-deriving raw-PGN header
  order — out of scope here and discards 10+0 data. **Not recommended as primary.**
- **Option C (game-level weighting):** each control-month equal aggregate weight; each game equal total
  weight within its control-month; long games do not dominate.

**LOCKED policy for 16.2B:**
1. **Primary inferential layer = separate within-control models** (Question B) — no cross-control
   weighting needed; each control speaks for itself.
2. **Pooled interaction model (Question C) = game-normalized weighting with equal control-month
   aggregate weight** — i.e., each move row weighted by `1 / (rows_in_its_game)` then renormalized so
   each of the six control-month datasets contributes equal total weight. This makes the estimand
   "average over games, balanced across controls," not "average over rows."
3. **Unweighted row-level pooled model = reported as robustness (R7 complement).**
4. Option B deterministic 10+0 subsampling = optional robustness only (R13), not primary; documented
   as discarding data and requiring a re-derived ordering.
5. The report/figures must always state game counts alongside row counts; never imply equal caps =
   equal move denominators.

## 5. Analysis population and exclusion policy

**Primary headline population:** status==ok; non-mate-band; valid `clock_before_s`; valid
`clock_fraction`; valid `mover_elo`; valid `termination`.

Audit findings:
- `clock_fraction > 1` rows are **negligible**: ≤185 rows per artifact (0.00–0.01%). (Berserk/clock
  reconstruction edge cases, already flagged.)
- Negative think-time rows: tiny (82–165 per artifact, from 16.1C), flagged not dropped.
- Duplicate (game_id, ply) keys: **0** in all six (verified 16.1C / 15.3C-D).
- All-opening short games already absent (extraction `move_number >= 5`; ~230–290 zero-row games/control
  already excluded at extraction).
- Mate-band rows present and flagged (`is_mate_band`); excluded from headline ES-loss population.

**LOCKED policy:**
- **Primary:** retain anomaly rows (clock_fraction>1, negative think-time) WITH explicit flags, matching
  Phase 15.4 discipline.
- **Robustness (R2/R11):** exclude `clock_fraction > 1` and negative-think-time anomalies (impact
  negligible given counts).
- **Mate-band:** excluded from headline ES-loss models; reported separately as diagnostic only.

## 6. Rating-pool normalization

**Primary rating variable = within-control × month mover-rating QUINTILE (Q1–Q5).**

Quintile cutpoints (headline pop), read-only:

| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ | (Q5 >) | min / max |
|---|---|---|---|---|---|---|---|
| 3+0 | 2024-09 | 1495 | 1717 | 1878 | 2052 | 2052 | 400 / 3042 |
| 3+0 | 2024-10 | 1503 | 1720 | 1885 | 2055 | 2055 | 400 / 3005 |
| 5+0 | 2024-09 | 1272 | 1500 | 1685 | 1882 | 1882 | 411 / 3034 |
| 5+0 | 2024-10 | 1256 | 1495 | 1682 | 1880 | 1880 | 400 / 3006 |
| 10+0 | 2024-09 | 1269 | 1510 | 1702 | 1896 | 1896 | 400 / 2709 |
| 10+0 | 2024-10 | 1275 | 1507 | 1692 | 1888 | 1888 | 400 / 2717 |

Findings: **3+0 cutpoints sit ~200+ Elo above 5+0/10+0** (e.g. Q3 ~1878 vs ~1685/1700); 5+0 ≈ 10+0.
This empirically confirms the 16.1A caveat — a "1600" means a different population in each control —
and that **raw cross-control rating differences must never be read as player-strength differences.**
Cross-month cutpoints are near-identical within control (stable; supports per-control pooling if
needed, but per-month is cleaner).

**LOCKED:** compute quintile cutpoints **within each control × month** (Option A); use Q1–Q5 as the
primary rating control; document cutpoints in the 16.2B report. Secondary = raw 200-Elo bins **within
each control only** (lineage with Phase 15.4). Color-specific quintiles NOT used as primary (color is a
separate covariate); month-pooled-within-control quintiles = optional robustness (R9 family). Never
interpret raw rating across controls as strength.

## 7. Clock representation

**Primary cross-control clock axis = `clock_fraction` = clock_before_s / initial_time_s.** Verified in
16.1C to use `initial_time_s` exactly (0 error), so it is directly comparable across controls.

**Atlas (fine) buckets — LOCKED, all powered (Section 2 of audit):**
`≤0.02 | (0.02,0.05] | (0.05,0.10] | (0.10,0.25] | (0.25,0.50] | (0.50,0.75] | >0.75`.
Smallest fine cell = 10+0 ≤0.02 ≈ 7k rows / ~1,490–1,510 games per month — adequate.

**Controlled-model (coarse) buckets — LOCKED, all powered:**
`critical ≤0.05 | low (0.05,0.15] | medium (0.15,0.50] | high >0.50` (ref = **high**).
Coarse cell counts (rows/games), headline:

| Control·Month | crit ≤.05 | low .05–.15 | med .15–.50 | high >.50 |
|---|---|---|---|---|
| 3+0 09 | 48k/6,639 | 91k/9,840 | 354k/17,599 | 928k/23,572 |
| 5+0 09 | 30k/4,678 | 65k/7,508 | 299k/15,645 | 971k/23,726 |
| 10+0 09 | 18k/2,285 | 37k/4,066 | 226k/12,071 | 1,134k/25,493 |

(2024-10 near-identical.) Every coarse cell ≥ ~17k rows / ≥ ~2,250 games → headline-capable everywhere.

**Absolute-second diagnostics (control-specific, NOT pooled axis):** keep per-control absolute buckets
for within-control reading and 10+0 lineage (the existing `clock_coarse` under_10/10_30/30_60/60_180/
over_180 from Phase 15.4 remains valid for 10+0 only). Do NOT use absolute seconds as the pooled axis.

**Continuous specs (robustness R3):** `clock_fraction` linear; piecewise-linear / restricted spline in
`clock_fraction`; `log(clock_before_s + 1)` as a secondary diagnostic. **Avoid raw inverse-clock
transforms** (unstable near zero). Recommended: atlas = fine buckets; controlled headline = coarse
categorical; robustness = continuous/spline.

## 8. Termination-channel decomposition

`board_decided` (¬is_time_forfeit) and `time_forfeit` (is_time_forfeit) are distinct targets.

Audit (game-level is the correct denominator for prevalence):

| Control | Month | TF rows | TF games | BD games |
|---|---|---|---|---|
| 3+0 | 09 | 36.9% | 29.2% (6,914/23,703) | 70.8% |
| 3+0 | 10 | 37.9% | 30.1% (7,138/23,721) | 69.9% |
| 5+0 | 09 | 28.7% | 22.6% (5,375/23,756) | 77.4% |
| 5+0 | 10 | 28.8% | 22.6% (5,359/23,734) | 77.4% |
| 10+0 | 09 | 14.1% | 11.5% (2,945/25,582) | 88.5% |
| 10+0 | 10 | 14.1% | 11.6% (2,854/24,524) | 88.5% |

Move-level TF% > game-level TF% because TF games are longer (more rows). **Prevalence claims use
game-level rates.**

**Required populations for 16.2B:** (1) all games; (2) board-decided only; (3) time-forfeit only where
meaningful; (4) game-level termination-rate analysis. **A move-level model with `termination_channel`
as a covariate does NOT replace a board-decided-only robustness analysis** (Phase 11 lesson). The
report must separately present: cross-control TF prevalence (game-level); move-quality loss within
eventual TF games; move-quality loss within board-decided games.

## 9. Move-quality outcome policy

- **Primary outcome:** `expected_score_loss` (mover perspective).
- **Secondary:** `cp_loss_clipped` (median/p75/p90).
- **Binary outcomes:** ES≥0.05, ES≥0.10 (headline ES≥0.10), cp≥100, cp≥200.
- **Diagnostic only:** raw centipawn loss; percent-eval-swing forbidden as headline.
- **ES transform reused (scale 348.41), NOT refit per control.** State explicitly that reusing one
  train-fit cp→ES transform across controls is a **comparability assumption and a robustness
  limitation** (the cp→ES mapping was fit on 10+0 train data); cp-based outcomes are the transform-free
  cross-check.

## 10. Descriptive atlas design

Markdown tables + tracked PNGs. Game-cluster bootstrap CIs on headline cells. Month-specific
replication shown. Proposed figures (each tied to a distinct question — consolidate any that do not):

1. **Fig 1 — clock_fraction (fine) vs mean ES loss, lines = 3+0/5+0/10+0**, month-replicated. (Q-A/B)
2. **Fig 2 — clock_fraction vs clipped CP loss**, same structure. (transform-free cross-check)
3. **Fig 3 — large-loss probability vs clock_fraction** (ES≥0.10 headline, ES≥0.05 secondary). (Q-B)
4. **Fig 4 — termination rates by control × month** (game-level TF / BD fractions). (Q-D)
5. **Fig 5 — board-decided-only clock curves** — scientifically central (isolates board play from
   flagging). (Q-D)
6. **Fig 6 — rating-quintile × clock_fraction heatmap**, faceted by control. (Q-B, confound check)
7. **Fig 7 — eval-band-conditioned clock curves** — required because eval state dominates loss. (Q-B)
8. **Fig 8 — phase-conditioned clock curves** — required because clock_fraction ≈ phase (Section 17). (Q-B)
9. **Fig 9 — cross-control month-replication summary** (Sept vs Oct estimates side by side). (Q-5)

Optional appendix only (NOT headline unless explicitly promoted later): think-time loss-rate /
flagging-signature diagnostic.

## 11. Controlled within-control model design (PRIMARY inferential layer)

Separate OLS models for 3+0, 5+0, 10+0 (numpy `ols_fit` lineage; sklearn logistic for binaries):

```
expected_score_loss ~ C(clock_fraction_bucket, ref=high)
                    + C(eval_band, ref=decided)
                    + C(phase, ref=middlegame)
                    + C(rating_quintile, ref=Q3)
                    + C(month, ref=2024_09)
                    + C(mover_color, ref=white)
                    + C(termination_channel, ref=board_decided)
                    + clock_anomaly_flags
```

Primary within-control contrasts (locked after this cell audit; all powered): **critical vs high,
low vs high, medium vs high.** Do **not** force the old 60–180s vs over-180s absolute contrast into the
cross-control analysis (it is 10+0-specific). For 10+0, retain the existing absolute-clock model
(`dense_controlled_move_quality_model_10plus0...`) as a **lineage comparison**, but `clock_fraction` is
the cross-control axis. Eval band is the positive control (expected dominant).

## 12. Controlled pooled interaction model design (Question C)

```
expected_score_loss ~ C(time_control, ref=10+0)
                    + C(clock_fraction_bucket, ref=high)
                    + C(time_control) : C(clock_fraction_bucket)
                    + C(eval_band, ref=decided)
                    + C(phase, ref=middlegame)
                    + C(rating_quintile, ref=Q3)
                    + C(month, ref=2024_09)
                    + C(mover_color, ref=white)
                    + C(termination_channel, ref=board_decided)
                    + clock_anomaly_flags
   [game-normalized weights, equal control-month aggregate weight — §4/§16]
```

Primary interaction question: does the conditional `clock_fraction` gradient differ between 3+0, 5+0,
10+0? **Do not interpret the time-control main effect causally** (it absorbs pool/selection
differences). **Do NOT include broad high-order interactions** (time_control×eval_band,
time_control×phase) in the primary model — reserve them for targeted localization robustness after the
main model converges. Rating quintile is within-control by construction, so it enters as a control that
is already pool-normalized.

## 13. Flagging / termination model design (game-level)

Termination is a **game-level** property — model it on one row per game, not by repeating the constant
game outcome across every move row.

```
is_time_forfeit ~ C(time_control, ref=10+0)
                + rating controls (within-control quintile or raw-bin)
                + game_length / final_ply
                + C(month)
                + (color/outcome controls only if coherent at game level)
   [logistic; one row per game; game is the unit, no move-level repetition]
```

Game-level row construction: collapse each game to (game_id, time_control, month, mover/white rating
representation, final ply / n_moves, is_time_forfeit). Descriptive estimand =
`Pr(time_forfeit | observed control and covariates)`. **Not** a causal effect of time control. Also
report time-forfeit rate by within-control rating quintile (descriptive). Open question for Malachi
(§24): whether this lands in 16.2B or a separate 16.2C.

## 14. Repeated-observation and uncertainty strategy

Move rows are nested in games → players → control-month samples.

- **Primary uncertainty = game-clustered sufficient-statistics bootstrap** (the efficient Phase 15.4D
  `ols_cluster_bootstrap`: per-cluster XᵀX/Xᵀy, bincount-weighted resample — NOT naïve row resampling).
- **Player-clustered robustness (R8):** feasible. Audit findings — within-month cross-control mover
  overlap is **small** (3+0&5+0 ~283–298; 3+0&10+0 ~237–239; 5+0&10+0 ~424–454; all-three ~22), so
  controls are largely player-disjoint and pooled cross-control contamination is minor but nonzero.
  Cross-month overlap within control is **18–22%** of movers → months are **not** fully independent
  (consistent with prior phases). Concentration is moderate (median 2 games/mover, p90 6–9, max 34–43).
- For the **pooled** model, cluster by game primary; player-clustered (mover-hash) as robustness.
  Do not assume player independence; do not assume cross-month independence.

## 15. Month-replication policy

Every headline result reports **2024-09, 2024-10, and pooled** estimates. Replication ladder (strict):

- **Replicated:** same direction AND both month CIs exclude 0.
- **Directionally replicated:** same direction, but one/both month CIs include 0.
- **Pooled-only:** pooled CI excludes 0 but months unstable/disagree.
- **Not replicated:** month signs disagree materially, or pooled driven by one month.

"Replicated" is not used loosely.

## 16. Weighting and estimand policy

- **Row-weighted estimand:** average over move rows (longer games dominate).
- **Game-weighted estimand:** average over games (each game equal total weight).
- **Equal control-month estimand:** each of six datasets equal aggregate weight.

**LOCKED hierarchy:** (1) separate within-control models (no cross-control weighting); (2) pooled model
= **game-normalized weights with equal control-month aggregate weight** (primary pooled estimand =
"per-game, balanced across controls"); (3) unweighted row-level pooled = robustness. The report states
the estimand in words next to every pooled number.

## 17. Cell adequacy and power audit

Thresholds (move-rows AND games per control-month cell): **headline-capable ≥1,000 rows AND ≥200 games;
exploratory 200–999 rows or 50–199 games; no-claim <200 rows or <50 games.**

Findings (read-only `/tmp/phase_16_2a_cell_adequacy.txt`):
- **Coarse clock buckets:** all headline-capable everywhere (smallest crit ≤.05 = 17–18k rows / 2,254–
  2,285 games in 10+0). ✔
- **Fine atlas buckets:** all ≥7k rows / ≥~1,490 games. ✔
- **eval_band × coarse-clock:** all cells ≥ ~2k rows; thinnest = decided×high in 3+0/5+0 (20–32k) and
  near_equal/slight×crit (2–8k) — all headline-capable. ✔
- **Board-decided-only × crit-clock (R1 population):** 5–8k rows / **734–1,241 games** — above headline
  threshold but the **thinnest headline cell**; flag for cautious reading. ✔ (with note)
- **Rating-quintile × crit-clock:** 2–13k rows / 375–1,479 games per Q — headline-to-exploratory; 10+0
  Q1–Q2 crit ≈ 2k rows / ~375–414 games (lower power, exploratory-leaning). Flagged.
- **PHASE × CLOCK CONFOUND (critical finding):** crit-clock (≤.05) is **almost entirely endgame**
  (opening crit ≈ 0; middlegame crit = 0–2k; endgame crit = 17–45k). Low `clock_fraction` ≈ late game.
  → phase conditioning is mandatory; the extreme-low-clock estimand is effectively "low clock within
  the endgame," and a clean "low clock, same phase" contrast does not exist at the extreme. Stated as a
  headline limitation.

Flagged cells: extreme-low-clock board-decided (thin, endgame-only); high-rating low-clock (10+0 Q1–Q2
crit lower power); sparse eval-band×crit interactions; time-forfeit-only move-level cells (use with the
game-level model, not as independent move evidence).

## 18. Robustness specifications

- **R1.** Board-decided only (clock curves + within-control models). *(central)*
- **R2.** Exclude clock anomalies and negative think-time.
- **R3.** Continuous / spline `clock_fraction`.
- **R4.** Clipped-CP outcome (transform-free).
- **R5.** ES≥0.10 binary outcome.
- **R6.** Month-specific models (already in the ladder).
- **R7.** Game-normalized vs unweighted row-level pooled.
- **R8.** Player-clustered (mover-hash) uncertainty.
- **R9.** Raw 200-Elo bins within control (vs quintiles).
- **R10.** Existing 10+0 absolute-clock lineage model comparison.
- **R11.** Restrict `clock_fraction ≤ 1`.
- **R12.** Exclude very short games.
- **R13.** (optional) Deterministic 10+0 24k subsample for matched accepted-game denominator.

Compact robustness matrix: primary contrasts (crit-vs-high, low-vs-high) × {per-month, pooled} ×
{R1–R10}.

## 19. Figure and table plan

Figure directory (tracked, small PNGs only): `reports/figures/phase_16_2_cross_time_control/`.
Proposed figures (consolidate per §10 if any do not answer a distinct question):

```
fig_16_2_01_clock_fraction_es_loss_by_control.png
fig_16_2_02_clock_fraction_clipped_cp_by_control.png
fig_16_2_03_large_loss_probability_by_control.png
fig_16_2_04_termination_rate_by_control.png
fig_16_2_05_board_decided_clock_fraction_es_loss.png
fig_16_2_06_rating_clock_heatmap_by_control.png
fig_16_2_07_eval_band_clock_fraction_by_control.png
fig_16_2_08_phase_clock_fraction_by_control.png
fig_16_2_09_controlled_clock_interactions.png
fig_16_2_10_month_replication_summary.png
```

Required tables: dataset denominator table (rows AND games); rating-quintile cutpoints; clock-fraction
cell counts (fine + coarse); termination rates (game-level); descriptive move-quality summaries;
within-control model coefficients; pooled interaction coefficients; robustness matrix; claim-status
table.

## 20. Claim ladder and interpretation rules

- **T1 — Termination prevalence (safe, descriptive):** "Observed time-forfeit prevalence is higher in
  3+0 than 5+0 and higher in 5+0 than 10+0 across both sampled months." Allowed if the game-level model
  + atlas support it. NOT causal.
- **T2 — Average board-move quality (cautious):** "Average next-move expected-score loss is similar
  across the observed 3+0/5+0/10+0 samples." Allowed ONLY if atlas + controlled results support it;
  never say "identical" or "unaffected."
- **T3 — Within-control clock gradient:** "Lower clock fraction is associated with higher next-move
  loss within one or more controls after conditioning on observed position/player covariates." Allowed
  per-control where it replicates; note the phase confound.
- **T4 — Cross-control moderation:** "The conditional clock–loss gradient differs across observed time
  controls." Allowed ONLY if interaction estimates replicate (both months).
- **Forbidden interpretations:** faster controls cause flagging; faster controls do not harm move
  quality; time pressure affects only flagging; players reason equally well at all speeds; any causal
  reading of the time-control main effect; raw-rating strength comparisons across controls.

## 21. Implementation architecture recommendation

- **Option A (extend Phase 15 modules):** less duplication, shared validation/bootstrap; risk =
  complicates stable 10+0 code and its locked outputs.
- **Option B (dedicated module):** `src/chess_mhsuc/cross_time_control_analysis.py` +
  `tests/test_cross_time_control_analysis.py`, reusing **pure** helpers from `dense_constraint_atlas.py`
  / `dense_controlled_model.py` (bucket helpers, `ols_fit`, `ols_cluster_bootstrap`, eval/phase
  conventions) by import, without editing them.

**LOCKED: Option B.** Create a dedicated cross-time-control module; import tested loaders/bootstrap/
bucket helpers unchanged; isolate cross-control weighting/rating-quintile/clock_fraction logic; do not
alter any existing 10+0 output. This protects the Phase 15 lineage and keeps the new estimands
auditable.

## 22. Recommended 16.2B scope

**16.2B — Cross-Time-Control Atlas / Controlled Modeling Implementation.** Scope: load all six dense
artifacts (read-only); validate schema + control/month identity; compute within-control×month rating
quintiles; compute `clock_fraction` fine+coarse buckets; implement the §4/§16 denominator/weighting
policy; generate the descriptive atlas (Figs 1–9 + tables); fit separate within-control models; fit the
pooled time-control × clock_fraction interaction model; run board-decided + core robustness (R1–R10);
build the game-level termination model; generate tracked PNGs; write the analysis report + phase report;
update ROADMAP + EXPERIMENT_LOG. **Exclusions:** no increment controls, no bullet, no sharpness, no
additional Stockfish, no Phase 17 packaging.

## 23. Optional later branches (recorded only)

- 16.3 increment contrast: 3+0 vs 3+2 and/or 5+0 vs 5+3 (blitz increment, better powered than rapid).
- Think-Time Loss-Rate / Flagging-Signature diagnostic.
- 15.5D stratified dense sharpness extraction.
- 1+0 bullet as a separate regime.
- 10+5 / 15+10 after larger-sample acquisition.
- Phase 17 public packaging.

## 24. Open questions for Malachi

1. **Pooled headline weighting** — game-weighted vs equal control-month aggregate?
   **Recommended default:** game-normalized with equal control-month aggregate weight (§16); unweighted
   row-level as robustness.
2. **Termination-rate modeling — in 16.2B or a separate 16.2C?**
   **Recommended default:** include the game-level termination model in 16.2B (it is the likely headline
   cross-control contrast and is cheap; no extraction).
3. **Think-time loss-rate diagnostic — Phase 16 appendix or deferred?**
   **Recommended default:** keep deferred (not headline) unless a specific question needs it.
4. **Compact core report vs larger atlas?**
   **Recommended default:** produce the full 9–10-figure atlas ONLY if each figure answers a distinct
   preregistered question; otherwise consolidate (e.g., merge Figs 1–3 into a 3-panel) to keep a compact
   core report.

Defaults summary: primary science = separate within-control models; pooled = game-normalized / equal
control-month; include game-level termination in 16.2B; think-time deferred; consolidate figures unless
each is distinct.

---

**Non-claims (this audit):** design-only; no code/models/figures/Stockfish/extraction; no Parquet
modified. No causal claims. Termination dose-response and move-quality flatness are descriptive
hypotheses to be tested in 16.2B, not results. Raw ratings NOT cross-pool comparable (within-control
quintiles mandatory). Stockfish not ground truth; ES transform reused (comparability assumption, not
refit). No sharpness (neither confirmed nor disproven). No increment/bullet/10+5/15+10. No "faster
controls cause worse chess / cause flagging," no "time pressure causes worse reasoning," no "low clock
causes blunders," no "increment causes better reasoning," no "players reason equally well at all
speeds," no "DRAW solved." C4 & C3c unchanged. PREREGISTRATION unchanged.
