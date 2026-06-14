# Phase 15.1A — Constraint Atlas Descriptive Curves Audit

**Labels:** AUDIT/DESIGN | read-only inspection, doc-only
**Date:** 2026-06-13
**Owner:** Malachi Wang

## 1. Executive summary

The 15.0C next-move loss artifacts are **complete and clean — no repair needed.** Both
months: 0 duplicate keys, 0 nulls in any headline metric (`expected_score_loss`,
`clipped_cp_loss`, `cp_loss`, `es_pre/post`, `mover_pre_cp`, `mover_clock_s`,
`mover_rating`, `time_bucket`, `split_set`), 33 columns, row counts matching the 15.0C
reports. The Constraint Atlas (15.1B) can be designed directly on them. Recommended
headline: **mean + median + p75/p90 + large-loss probabilities of expected-score loss
(mover's perspective)**, shown month-by-month then combined, with clipped cp loss as the
interpretable secondary and mate-band excluded from headline curves. The binning that
matters most: **bucket clock within checkpoint** — the artifact confirms the 9.2B
confound starkly (move_10 is 99.96% over-180s; low clock exists only at move_30/40), so
marginal clock curves are forbidden. **15.1B may proceed before 11.3A/B** if it stays
descriptive, month-replicated, uses game-level bootstrap, and makes no player-level
inferential claims; controlled modeling (15.1C/15.2B) waits for player-leakage hardening.
One scope limitation to document prominently: at numbered checkpoints the mover is always
White, so the Atlas describes **White-to-move decision quality**. Descriptive, not
causal; Stockfish depth-12 eval is objective context, not absolute ground truth.

## 2. Scientific motivation after 11.2B and 15.0C

11.2B/11.2C reframed the outcome clock residual as primarily the flagging channel and
moved the board-play-quality question to Contrast C4. 15.0C built the measurement layer
(next-move expected-score loss for 126,239 checkpoint moves across two months). The Atlas
descriptively answers: how does next-move quality loss vary with clock, rating, eval
state, phase, and termination channel — within our controlled, replicated pipeline,
framed as replication of known descriptive/move-level phenomena (Anderson et al.;
resource-rational work; jk_182), never as novel and never as causal.

## 3. Artifact schema and integrity findings

Read-only inspection of both `next_move_loss_*.parquet`:

| Check | 2024-09 | 2024-10 |
|---|---|---|
| Total rows | 65,368 | 62,839 |
| status=ok | 64,371 | 61,868 |
| status=no_next_move | 997 | 971 |
| ok, non-mate-band | 61,956 | 59,625 |
| Duplicate `(game_id, selected_position_type)` | 0 | 0 |
| Nulls in headline metrics (ok rows) | 0 | 0 |
| Columns | 33 | 33 |
| `mover_color` (ok) | white only | white only |

Row counts match the 15.0C reports exactly. Required C4 columns all present:
`expected_score_loss, cp_loss, clipped_cp_loss, es_pre, es_post, mover_pre_cp,
mover_post_cp, pre_sf_eval_cp/mate, post_sf_eval_cp/mate, is_mate_band, mover_clock_s,
time_bucket, white_rating, black_rating, mover_rating, termination, is_time_forfeit,
selected_position_type, split_set, sf_depth, status, fen_hash_matches, pre_fen, post_fen,
actual_move_uci`. **mover_color always White** is structural (numbered checkpoints are at
even plies 20/40/60/80 → after Black's move → White to move). No suspicious values; no
repair required.

## 4. Headline metric recommendation

- **Primary: expected-score loss, mover's perspective** — report **mean, median, p75,
  p90**, plus **large-loss probabilities**: P(ES loss > 0.05), P(ES loss > 0.10).
- **Secondary: clipped cp loss** (mean/median/p90 + P(>100cp), P(>200cp)) for
  interpretability and literature comparability; raw cp only inside eval-band panels.
- **Skew handling:** loss is heavily right-skewed (2024-09 ES median 0.0102 vs mean
  0.0345) → always report median + upper quantiles alongside means; never means alone.
- **Mate-band:** excluded from headline loss curves (flagged `is_mate_band`); shown in a
  separate small panel/count, never silently pooled.
- **Months:** show **month-by-month first, then combined** — pool only after displaying
  2024-09/2024-10 replication (they agreed to 3 decimals in 15.0C).
- **Default population:** show **all-games and board-decided side-by-side** as co-headline
  (not board-decided-only as the sole headline) — time-forfeit rows are valid moves
  before a flag and a distinct, scientifically interesting population.
- **Uncertainty:** game-level clustered bootstrap for means (multiple checkpoints per
  game); see §10.

## 5. Clock-bin design

`time_bucket` (under_60s / 60_180s / over_180s) and raw `mover_clock_s` are both present.
**Headline: the coarse three buckets, bucketed WITHIN checkpoint.** The marginal
clock×checkpoint cross-tab (2024-09 ok) is decisive:

| | under_60s | 60_180s | over_180s |
|---|---|---|---|
| move_10 | 1 | 9 | 24,211 |
| move_20 | 24 | 238 | 18,741 |
| move_30 | 241 | 1,067 | 10,718 |
| move_40 | 508 | 1,294 | 4,904 |

Low clock is essentially a move_30/40 phenomenon → **marginal "clock vs loss" curves are
forbidden (confound); always condition on checkpoint.** Finer exploratory bins within the
late group (move_30+40): `<10s` 88, `10–30s` 220, `30–60s` 441, `60–180s` 2,361, `>180s`
15,622 — so `<10s`/`10–30s` are descriptive-only (sub-300), `30–60s`+ are CI-bearing. Use
finer bins only as labeled exploratory within the late group.

## 6. Rating-bin design

`white_rating`, `black_rating`, `mover_rating` all present (`mover_rating` = white_rating
here since mover is always White). Range 422–2709, median 1601. 200-pt bins (2024-09 ok):
1000–1999 hold 6.2k–13.2k rows each; 800/2000/2200 hold 0.8k–5.0k; tails (≤600, ≥2400)
<800. **Recommend 200-pt bins (or rating quantiles) for CI-bearing headline across
~800–2199**; tail bins (≤600, ≥2400) descriptive-only; **100-pt bins only for smoothed
pooled visuals** (dense middle 1200–1900 would still support them, but tails fragment).
For future cross-time-control work (Phase 16): within-time-control quantiles; for 10+0
alone, absolute Lichess bins are fine at these sample sizes.

## 7. Eval-band design

From mover-perspective `mover_pre_cp` (|cp|), 2024-09 ok non-mate distribution:
near_equal (≤100) 18,899 · slight (100–300) 18,549 · clear (300–700) 21,299 · decided
(700–1000) 2,983 · >1000 226. **Recommend:** `near_equal / slight / clear / decided`,
**folding the 226 |cp|>1000 rows into `decided`** (or labeling a tiny `near_mate_cp`
cell), with `mate_band` separate/excluded. Eval-band conditioning is **required** for cp
interpretability (100cp at equality ≫ 100cp at +900); ES loss is less sensitive but
panels should still condition for consistency.

## 8. Phase/checkpoint design

`selected_position_type` ∈ {move_10, move_20, move_30, move_40} (no `last` in primary).
Counts (2024-09 ok): 24,384 / 19,639 / 12,950 / 7,398. **Show per-checkpoint curves and
the late group (move_30+move_40)** — the prior clock signal localized there. **Never
collapse across checkpoints without also showing phase-conditioned results** (the clock
confound, §5).

## 9. Termination-channel design

Channels present (15.0C / termination_decomposition taxonomy): all-games; board_decided;
time_forfeit; normal_decisive; normal_draw; rules_infraction (1/month). **Always show
termination-channel composition**; **show all-games and board-decided side-by-side**;
treat **time-forfeit as a distinct descriptive population**, not noise. The 15.0C coarse
observation (board-decided ≈ time-forfeit checkpoint loss) **must be re-examined
stratified by clock/phase/eval before any interpretation** — similar marginal loss
distributions do not imply identical mechanisms, and time-forfeit rows concentrate in
late low-clock cells (the cells where stratification matters most).

## 10. Cell-count and uncertainty policy

- **n < 50:** hidden/greyed, never labeled.
- **50 ≤ n < 300:** descriptive point estimate only, explicit "no CI" marker.
- **n ≥ 300:** CI-bearing headline cell.
- **Bootstrap: game-level clustered** (resample game_ids; a game contributes ≤4
  checkpoints) — row-level bootstrap would understate uncertainty. 1,000 replicates,
  seed=42, per month.
- **Player-clustered uncertainty deferred** to after 11.3A/B (or a 15.1B+ robustness add-on).

## 11. Proposed 15.1B outputs

Design (filenames for 15.1B; tables as markdown, figures optional/deferred):

1. **Time-bucket × checkpoint table** — mean/median ES loss, p75/p90, large-loss
   probabilities, n; month-by-month + combined. (`constraint_atlas_time_checkpoint_*`)
2. **Clock vs ES loss curves within late group** — board-decided and all-games panels.
3. **Rating × time heatmap** — ES loss / large-loss probability, 200-pt bins.
4. **Eval-band-conditioned curves** — separate near_equal/slight/clear/decided.
5. **Termination-channel comparison** — all-games vs board-decided vs time-forfeit,
   stratified by clock/phase.
6. **Month-replication table** — same cells, 2024-09 vs 2024-10.
7. **Robustness table** — clipped cp loss mirrors ES loss (or not).
8. **Sample-size diagnostic** — per-cell n, hidden/sparse flags.

Headline report: `reports/constraint_atlas_2024_09_250k_v1.md`,
`..._2024_10_...md`, `reports/constraint_atlas_combined.md`. JSON results gitignored under
`data/processed/`. No plots required in v1 (tables with CIs suffice); figures optional.

## 12. Relationship to 11.3A/B player-leakage audits

15.0B/15.0C were safe before 11.3A/B (they produced measurement artifacts). **15.1B
descriptive curves may also proceed before 11.3A/B**, provided they: (a) are labeled
descriptive; (b) are month-replicated; (c) use game-level clustered bootstrap; (d) make
no player-level or causal/inferential claims. **Controlled modeling and formal
player-dependence inference (15.1C / 15.2B sharpness moderation) must wait for 11.3A/B**
or build in player-clustered/disjoint design from the start.

## 13. Artifact repair needs

**None.** All required columns present, 0 nulls, 0 dups, ES transform adequate, time
buckets/ratings/eval bands all derivable. The only limitation is scope, not a defect:
**`mover_color` is always White** (numbered even-ply checkpoints), so the Atlas describes
White-to-move decision quality. This does not block 15.1B; it must be stated in the
Atlas. Adding Black-to-move (odd-ply) checkpoints for symmetry is a possible future
ticket (15.0D-style sampling extension), not a prerequisite.

## 14. Risks and caveats

- Marginal clock curves are misleading (clock×checkpoint confound) — bucket within
  checkpoint (§5).
- Board-decided low-clock cells are a selected survivor population (11.2B).
- Loss is right-skewed → medians/quantiles mandatory.
- White-to-move-only scope (§13).
- Similar marginal loss across termination channels ≠ identical mechanisms (§9).
- Descriptive only; no causal language; no "degradation curve" for ordered-bucket
  patterns; Stockfish depth-12 eval is objective context, not absolute ground truth;
  DRAW remains sparse and not solved.
- Descriptive Atlas may use all OK rows (it is summary measurement, not model selection
  or test evaluation); the test-split reservation applies to controlled modeling
  (15.1C+), not to descriptive curves.

## 15. Roadmap / preregistration implications

PREREGISTRATION C4 already specifies expected-score loss (mover's perspective) as primary
with clipped cp secondary, prior-trajectory control for modeling, and the
non-monotonicity caution — this audit is consistent and needs no C4 edit. A one-line
note that the descriptive Atlas (15.1B) precedes controlled modeling (15.1C/15.2B, gated
on 11.3A/B) is optional. ROADMAP next-ticket pointer → 15.1B.

## 16. Recommended next ticket

**15.1B — Constraint Atlas Descriptive Curves Implementation** (tables with game-level
bootstrap CIs per §11; month-by-month + combined; all-games and board-decided
side-by-side; descriptive only). Player-leakage hardening (11.3A/B) remains required
before 15.1C / 15.2B controlled modeling and sharpness moderation.
