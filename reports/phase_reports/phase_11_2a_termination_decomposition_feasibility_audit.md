# Phase 11.2A — Termination Decomposition Feasibility Audit

**Labels:** AUDIT | read-only
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. Executive summary

**Feasibility: Level 0–1 (best case). Proceed to 11.2B with existing artifacts only
(Recommendation A).** Termination information is already parsed, preserved through
cleaning, and present in both months' feature tables as two columns (`termination`,
`is_time_forfeit`); existing E3/E4 prediction artifacts carry
`(game_id, selected_position_type)` and join to the feature tables with the proven
zero-orphan key. No parser changes, no re-parsing, no new engine runs are needed.
One join, one filter, the existing paired-bootstrap machinery. The main scientific
caution from the numbers: the under-60s late-clock cell loses ~57% of its games to
the time-forfeit filter (228→101 and 241→94 games), so the board-decided localization
replication rests on the 60–180s cell, which stays above the 300-game CI threshold in
both months (464 and 424 games). One pre-registration wording fix is needed before
11.2B (see §11/§14).

## 2. Scientific motivation

Locked Contrast 2 (PREREGISTRATION.md): is the replicated E3→E4 clock residual
(−0.0138 / −0.0120, CIs excluding zero in both months) mostly mechanical
timeout/flagging risk, or does it survive among games decided on the board? Survival
at ≥ ~half magnitude with a CI excluding zero upgrades the claim to "not merely
flagging"; collapse re-frames the project honestly as quantifying the flagging
channel. Either outcome is reportable.

## 3. Current data and code inspection

Read-only inspection performed (no code modified, no data written):

- `src/chess_mhsuc/parse_pgn.py` / `run_parser.py`: `termination` is a GameRecord
  field parsed from the PGN `Termination` header and stored in the interim game and
  position records.
- `src/chess_mhsuc/cleaning.py`: keeps termination; **excludes `Abandoned` games**
  by rule (`termination != "Abandoned"`), records
  `termination_distribution_clean`, and runs a `no_abandoned_in_clean` check. Time
  forfeit is explicitly retained ("central to the research question" — a comment
  already present from Phase 3).
- `src/chess_mhsuc/features.py`: feature tables carry `termination` (string) and the
  derived boolean `is_time_forfeit`. Both are in the forbidden-as-features list
  (label-adjacent metadata), so they were never model inputs — exactly what a clean
  decomposition needs.
- Prediction artifacts (`eval_conditioned_predictions_{tag}.parquet`): columns include
  `model_id, split_set, game_id, selected_position_type, result_class, y_true,
  p_*` — joinable to the feature table on `(game_id, selected_position_type)`
  (the key verified unique and zero-orphan throughout Phases 8–9).
- `game_id` is stable across raw → interim → processed → sf → prediction artifacts
  (it is the join spine of the whole pipeline).

## 4. Termination availability

| Layer | Termination present? | Column(s) |
|---|---|---|
| Raw PGN headers | Yes | `[Termination "..."]` |
| Interim parse output | Yes | `termination` |
| Cleaned game/position tables | Yes (Abandoned excluded) | `termination` |
| Feature tables (both months) | **Yes** | `termination`, `is_time_forfeit` |
| sf_eval artifacts | No (not needed — join via key) | — |
| E3/E4 prediction artifacts | No (not needed — join via key) | — |

## 5. Raw termination vocabulary

Counted directly from the local cached 250k prefixes (all time controls, full file):

| Value | 2024-09 | 2024-10 |
|---|---|---|
| Normal | 163,152 | 162,356 |
| Time forfeit | 86,104 | 86,901 |
| Abandoned | 726 | 719 |
| Unterminated | 13 | 14 |
| Rules infraction | 5 | 10 |

In the **cleaned 600+0 data** only three values survive (Abandoned excluded by
cleaning; Unterminated never reaches the clean set): `Normal`, `Time forfeit`,
`Rules infraction`. Verified per month in the primary view (positions):
2024-09 — Normal 56,832 / Time forfeit 8,535 / Rules infraction 1;
2024-10 — Normal 54,586 / Time forfeit 8,252 / Rules infraction 1.
Time-forfeit games hold 13.1% of primary rows in **both** months (striking stability).

**Important limitation:** Lichess `Termination` does not distinguish checkmate from
resignation (both are `Normal`), nor draw subtypes. Draws are separable inside
`Normal` via `result_class == DRAW`, but mate-vs-resignation and
agreement-vs-stalemate-vs-repetition are **not** header-recoverable and must not be
pretended.

## 6. Processed artifact schema findings

- Feature tables: 89,888 (09) / 86,335 (10) broad rows; termination columns present;
  `is_time_forfeit` exactly matches `termination == "Time forfeit"`.
- Prediction artifacts: 4 models × full split coverage; key columns present.
- Splits join via the sf artifact's `split_set` (or splits JSON) as in Phases 9.2/9.3.

## 7. Feasibility level

**Level 0–1.** Termination is present in the processed feature table that the modeling
pipeline already consumes (Level 0 in substance); it is not physically inside the
prediction parquet, so 11.2B performs one join by `(game_id,
selected_position_type)` (Level 1 mechanics). No header re-extraction (Level 2), no
parser change (Level 2–3), no re-scoping (Level 3–4) needed. Reliability is good
(vocabulary is tiny and stable; Abandoned already excluded), with the
`Normal`-mixes-mate-and-resignation ambiguity noted as a Level 4-style caveat handled
by taxonomy design rather than sensitivity machinery.

## 8. Recommended channel taxonomy

Primary (filter design): **binary** —
- `time_forfeit` (`is_time_forfeit == True`)
- `board_decided` (everything else in the clean set)

Descriptive channel breakdown (no pretended precision):
- `time_forfeit`
- `normal_decisive` (Normal & decisive result — checkmate **or** resignation; not separable)
- `normal_draw` (Normal & DRAW result — agreement/stalemate/repetition/insufficient; not separable)
- `rules_infraction_or_other` (1 game per month — report count, exclude from channel tables)

`unknown_or_other` is structurally near-empty in the clean set (Abandoned/Unterminated
never enter), which simplifies 11.2B: no unknown-handling machinery beyond the
1-game `Rules infraction` footnote.

## 9. Sample-size implications

Validation split, measured (rows r / unique games g):

| Quantity | 2024-09 | 2024-10 |
|---|---|---|
| Val total | 9,823 r / 3,678 g | 9,442 r / 3,524 g |
| Board-decided val | 8,607 r / 3,276 g (87.6%) | 8,198 r / 3,124 g (86.8%) |
| Time-forfeit val | 1,216 r / 402 g | 1,244 r / 400 g |
| Late (move_30+40) under_60s — ALL | 250 r / 228 g | 275 r / 241 g |
| Late under_60s — **board-decided** | **107 r / 101 g** | **105 r / 94 g** |
| Late 60_180s — ALL | 679 r / 616 g | 658 r / 585 g |
| Late 60_180s — **board-decided** | **516 r / 464 g** | **483 r / 424 g** |
| Late over_180s — board-decided | 2,039 r / 1,440 g | 1,922 r / 1,343 g |

Implications: (a) the **overall** board-decided delta has ample data (≥3,100 games);
(b) the localization replication rests on **60_180s**, which stays above the 300-game
CI threshold in both months; (c) **under_60s drops to ~100 games — descriptive-only,
and the ~57% game loss there is itself a finding** (low-clock cells are heavily
time-forfeit-composed — the channel question is real, not hypothetical);
(d) sub-threshold cells follow the established descriptive/no-CI convention.

## 10. Reuse of existing E3/E4 predictions

Fully reusable. E3/E4 validation predictions exist for both months with the join key;
the `constraint_slices.py` pattern (attach keys by `(game_id,
selected_position_type)`, validate pairing per cell, paired game-level bootstrap via
`bootstrap_ci` functions) applies directly with `is_time_forfeit` as the slice key.
**No retraining is required for the primary design.**

Design distinction 11.2B must state explicitly:
- **Primary (prediction-side filter):** filter validation rows of the *frozen,
  all-games-trained* E3/E4 to board-decided games and recompute the paired delta.
  Question answered: does the residual hold *among* board-decided games?
- **Secondary (optional, only if pre-registered as secondary):** refit E3/E4 on
  board-decided-only training data. Question answered: does the residual exist in a
  board-decided *world*? More expensive, different estimand.

**Pre-registration inconsistency found:** PREREGISTRATION.md C2 currently says
"same frozen models, refit on the filtered population" — internally contradictory
wording (frozen vs. refit). Under the revision policy this must be fixed *before*
11.2B implementation begins: primary = prediction-side filter (no retraining);
refit = optional secondary. This is a wording clarification of an un-implemented
contrast, permitted with logging.

## 11. Recommended 11.2B design

**Recommendation A: proceed with existing artifacts only.** Scope:
1. Small pre-registration C2 wording fix (primary vs. secondary design), logged.
2. New module `src/chess_mhsuc/termination_decomposition.py` (or a thin extension of
   the constraint-slices pattern): join `is_time_forfeit`/channel keys onto existing
   E3/E4 predictions; compute all-games vs. board-decided paired deltas (overall +
   per-checkpoint + late-clock slices where ≥300 games); descriptive channel table
   (taxonomy §8); composition-shift table (how filtering changes cell composition).
3. `tests/test_termination_decomposition.py` — code ships, so tests ship (join
   integrity, channel derivation incl. result-class split of Normal, filter
   correctness, threshold behavior, deterministic report, forbidden-language).
4. Committed report `reports/termination_decomposition_2024_09_10_250k_v1.md`
   (or per-month, matching repo convention) + phase report + EXP-015.
5. Both months mandatory (C2). No retraining in the primary pass.

## 12. Risks and caveats

- **Timeout is not purely mechanical:** flagging is often the *consequence* of earlier
  cognitive time expenditure; removing TF games removes some genuine clock-relevant
  signal. Survival and collapse both need careful, pre-written interpretation language.
- **Selection bias:** board-decided low-clock games are survivors (players who
  navigated time pressure without flagging) — a selected population, stated plainly.
- **`Normal` mixes checkmate and resignation** — never claim mate/resignation
  separation; draws are separable only by result.
- **under_60s collapses** (~100 games) — descriptive only; the 60_180s cell carries
  the localization conclusion.
- Board-decided filtering does **not** make anything causal; all standing qualifiers
  apply unchanged.
- Player-level clustering remains a separate, unresolved caveat (11.3A/B).
- Draw terminations are not subtype-separable; DRAW remains sparse regardless.

## 13. Files likely touched in 11.2B

`PREREGISTRATION.md` (C2 wording fix, logged); new
`src/chess_mhsuc/termination_decomposition.py`; new
`tests/test_termination_decomposition.py`; committed analysis report; phase report;
`EXPERIMENT_LOG.md` (EXP-015); `ROADMAP.md` pointer. Gitignored outputs under
`data/processed/` (JSON results). No parser/cleaning/feature code changes.

## 14. Open questions

1. C2 wording fix (§10) — apply at the start of 11.2B (recommended) or as a separate
   micro-ticket?
2. Should the descriptive channel analysis include a third panel splitting
   `time_forfeit` by which side flagged (the *board leader* flagging vs. the trailer)?
   Cheap from result_class + clock columns; arguably the most interesting descriptive
   table; propose as labeled-exploratory in 11.2B.
3. Report shape: one combined two-month report (recommended — C2 is a both-months
   contrast) vs. per-month reports.

## 15. Recommended next ticket

**11.2B — Termination Decomposition Implementation** (Recommendation A: existing
artifacts only; C2 pre-registration wording fix applied first; no retraining in the
primary design).
