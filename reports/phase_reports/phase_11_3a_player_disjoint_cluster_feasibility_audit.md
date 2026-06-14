# Phase 11.3A — Player-Disjoint / Player-Clustered Feasibility Audit

**Labels:** AUDIT/DESIGN | read-only inspection, doc-only
**Date:** 2026-06-13
**Owner:** Malachi Wang

## 1. Executive summary

Human chess data is player-repeated, and our current splits are **game-disjoint but not
player-disjoint**. This audit measures the resulting dependence and tests whether strict
player-disjoint splitting is feasible. Findings:

- **Player identifiers exist only in the raw PGN headers** (`White`, `Black` usernames).
  They are **intentionally stripped at parse time** (`parse_pgn.extract_game_record`, per
  `DATA_POLICY.md`) and are **absent from every processed artifact** — game records,
  feature tables, E3/E4 predictions, and the next-move-loss artifacts. Usernames are **raw
  (not anonymized)** in the PGN. They **can** be recovered by joining on `game_id` (the
  Lichess Site slug, which survives), so a future hashed-ID join is technically possible.
- **Player dependence is severe.** Within each month, **~87% of checkpoint rows touch a
  player who appears in more than one split**, and **~4,200 players appear in both train
  and test**. Game-disjoint splitting does not control this.
- **Concentration is moderate, not extreme:** median 2 games/player, max ~36; the top 10%
  of players contribute ~30% of checkpoint rows. Enough to widen honest uncertainty, not
  enough to be dominated by a handful of accounts.
- **Cross-month overlap is material:** ~19.5% of 2024-09 players also play in 2024-10, and
  ~40% of each month's checkpoint rows involve a cross-month player — so the two months are
  **not fully independent replications at the player level**.
- **Strict player-disjoint 3-way splitting is infeasible.** The player–game graph has a
  **giant connected component holding ~92% of games / ~86% of players per month** (~95%
  pooled). Assigning whole components to splits would force ~92% of games into a single
  split; an alternative edge-cut would discard a large fraction of games. A held-out
  **player-disjoint robustness slice** is possible but costly.
- **Recommended hardening: Option A — player-clustered (mover-player) bootstrap**, plus
  hashed player IDs in ignored artifacts only. The existing game-level cluster bootstrap
  generalizes directly (swap the cluster key from `game_id` to a hashed player ID). This is
  the practical first layer before controlled C4 modeling (15.1C) and C3 sharpness
  moderation (15.2B).

All player work in this audit was done **in memory with salted, non-reversible hashes**;
**no usernames were written, printed, staged, or committed**, and **no `data/` artifact was
touched**.

## 2. Scientific motivation after 11.2B and 15.1B

11.2B reframed the outcome clock residual as **primarily the time-forfeit / flagging
channel** (time-forfeit games carry −0.118/−0.131 cz; board-decided residual collapses or
sign-reverses). 15.1B then found **no replicated clock gradient** in stable next-move-loss
cells, with the strongest replicated structure being eval-band (loss peaks near
equal/slight, lowest at decided).

Both results rest on **uncertainty estimates** (bootstrap CIs) and, prospectively, on
**train/test generalization** (controlled C4/C3 modeling). If the same players recur across
rows and across splits:

1. **flagging-risk estimates (11.2B)** may have understated CIs;
2. **next-move-loss summaries (15.1B)** may be over-weighted toward frequent players;
3. **controlled C4 modeling** could leak player identity from train into test;
4. **C3 sharpness × clock moderation** could claim moderation that is really player
   composition;
5. any **rating/time/phase** claim inherits the same risk.

This ticket quantifies the dependence and decides the hardening route. It does **not**
implement splits, train models, or rerun any extraction.

## 3. Current split design

`splits.py` assigns splits with **`split_unit = "game_id"`** (confirmed in both
`splits_2024_09_250k_v1.json` and `splits_2024_10_250k_v1.json`): two-step
StratifiedShuffleSplit, `seed=42`, fracs 0.70/0.15/0.15, stratified on `result_class`.
Split labels are **stored per game and propagate** into feature/eval/next-move artifacts
via `game_id` (the next-move-loss artifacts carry a `split_set` column).

**What this prevents:** *game leakage* — the same game (all its checkpoints) lands in
exactly one split. Verified: splits key on `game_id`, and checkpoints inherit by join.

**What this does NOT prevent:**

- **player leakage** — the same account appears in multiple splits (measured in §8);
- **repeated-player dependence** — rows from one player are correlated (rating, style,
  tilt, flagging propensity), so row/game bootstraps **understate** uncertainty;
- **cross-month repeated-player dependence** — months are treated as independent
  replications, but ~40% of rows involve a player present in both months (§7);
- **rating/time-control pool dependence** — frequent players concentrate in specific
  rating bands, so dense cells are partly the same people.

Month is currently treated as **replication, not a random split** — appropriate, but §7
shows it is only *approximate* player-level independence.

## 4. Player identifier availability

Read-only trace of the pipeline:

| Stage | Player identifier present? | Notes |
|---|---|---|
| Raw PGN headers | **Yes** — `White`, `Black` usernames; `Site` slug = `game_id` | Raw usernames; optional `WhiteTitle`/`BlackTitle` (e.g. `BOT`) |
| `parse_pgn.extract_game_record` | **No** — usernames intentionally dropped | Docstring: "Username fields (White, Black) are intentionally absent. Per DATA_POLICY.md…" |
| `GameRecord` / `schemas.py` | **No** | Only `game_id`, Elo, result, clocks, eval — no name field |
| Cleaning / feature tables | **No** | Nothing to preserve; usernames never enter |
| E3/E4 eval-conditioned predictions | **No** | Keyed by `game_id` |
| Next-move-loss artifacts | **No** | 33 columns; no username/player column |

**Answers to the core identifier questions:**

- Raw Lichess PGNs include White/Black usernames: **yes**.
- Usernames in parser output / cleaned tables / feature tables / next-move-loss artifacts:
  **no** (stripped at parse).
- Anonymized player identifiers anywhere: **none currently** — there is no hashed player ID
  in any artifact.
- Stable across months: usernames are **stable account names**, so the same account is the
  same string in both months (case-normalized below); a future hashed ID would be stable.
- Anonymous / deleted / "?" players: **none observed** — 0 games in either month's primary
  set had `?`, `anonymous`, or empty White/Black (rated games require accounts).
- Bots: identifiable via `WhiteTitle`/`BlackTitle == "BOT"`. **Bot-involved primary games:
  12 (2024-09), 7 (2024-10)** — negligible (<0.06%). Not currently filtered; flaggable.
- Case normalization: Lichess usernames are case-insensitive; this audit lower-cased before
  hashing so the same account always maps to one ID.

**Join feasibility:** because `game_id` survives end-to-end and the raw cache is present
locally, a `game_id → (white, black)` map can be rebuilt from raw PGN headers and joined to
**every** artifact. This audit did exactly that (100% of primary `game_id`s matched in the
raw cache, both months) — but **only to derive aggregate counts via salted hashes**, never
to persist identifiers.

## 5. Privacy and anonymization policy

Proposed standing policy for any player work (11.3B onward):

1. **Never commit raw usernames** or any deanonymized identifier. (Reaffirms `DATA_POLICY.md`.)
2. If player IDs are needed, derive **stable salted hashes** (`blake2b(salt + lower(user))`),
   generated **only into gitignored `data/` artifacts**, never into committed files.
3. The **salt is not committed** if its exposure would enable reversal of a small username
   space. For within-project reproducibility, a fixed project salt may live in an **ignored**
   config; reports never depend on raw names.
4. **Reports include aggregate counts only** — distributions, fractions, component sizes. No
   per-player rows, **no top-player name lists**, no deanonymization.
5. **Code should expose only hashed IDs**, not username columns. If a username column is
   transiently needed to build the hash, it must be dropped before any write.
6. **Bot / deleted / anonymous values** must be handled explicitly (title-based bot flag;
   `?`/empty guarded) and reported only as counts.

Recommendations: hashed player IDs **yes, in ignored artifacts only**; committed reports
**may** carry aggregate overlap/concentration counts (as in this report); code **must not**
expose username columns.

## 6. Player overlap and concentration findings

Computed read-only over the **primary next-move-loss game sets** (salted hashes, in memory):

| Metric | 2024-09 | 2024-10 |
|---|---|---|
| Primary games | 24,520 | 23,496 |
| Unique players (either side) | 17,116 | 17,209 |
| Unique White / Black players | 12,996 / 12,930 | 12,956 / 12,841 |
| Games per player — median | 2 | 2 |
| Games per player — p75 / p90 / p99 | 4 / 6 / 14 | 3 / 6 / 14 |
| Games per player — max / mean | 36 / 2.87 | 32 / 2.73 |
| Top 1% players → game-appearances | 6.1% | 6.2% |
| Top 5% / 10% players → game-appearances | 20.6% / 33.0% | 20.8% / 33.1% |
| Top 1% mover-players → checkpoint rows | 5.2% | 5.3% |
| Top 5% / 10% mover-players → checkpoint rows | 18.0% / 29.5% | 18.3% / 29.6% |
| Bot-involved primary games | 12 | 7 |

**Reading:** concentration is **moderate and stable across months**. The typical player
appears in ~2 games; a long but thin tail (max ~30–36). The top decile carries ~30% of
checkpoint rows — material enough that **player-clustered uncertainty will be wider than
game-clustered**, but no single account dominates. The distributions are near-identical
across months, which is itself reassuring for the replication design.

## 7. Cross-month overlap findings

| Metric | Value |
|---|---|
| Players appearing in **both** months | 3,346 |
| Fraction of 2024-09 players also in 2024-10 | 19.5% |
| Fraction of 2024-10 players also in 2024-09 | 19.4% |
| 2024-09 games involving a cross-month player | 9,647 / 24,520 (39.3%) |
| 2024-09 checkpoint rows involving a cross-month player | 26,184 / 65,368 (40.1%) |
| 2024-10 games involving a cross-month player | 9,051 / 23,496 (38.5%) |
| 2024-10 checkpoint rows involving a cross-month player | 24,714 / 62,839 (39.3%) |

**Reading:** ~1 in 5 players recur across months, and **~40% of each month's rows involve a
recurring player**. The two months are a **strong but not fully independent** replication:
agreement between 2024-09 and 2024-10 is partly the same accounts. This does not invalidate
the replication (60% of rows are month-unique players, and the *patterns* — eval-band
dominance, no clock gradient — are structural), but cross-month CIs should eventually be
**player-clustered across the pooled set**, and any "two independent months" language should
be softened to "two months with ~40% player-level overlap by row."

## 8. Train/validation/test overlap findings

| Metric | 2024-09 | 2024-10 |
|---|---|---|
| Players spanning >1 split | 6,817 / 17,116 (39.8%) | 6,499 / 17,209 (37.8%) |
| Games touching a multi-split player | 21,278 / 24,520 (86.8%) | 20,034 / 23,496 (85.3%) |
| Checkpoint rows touching a multi-split player | 56,548 / 65,368 (86.5%) | 53,413 / 62,839 (85.0%) |
| Players in **both train and test** | 4,223 | 3,982 |
| Players in **both train and val** | 4,181 | 3,975 |

**Reading: this is the headline risk.** ~40% of players, but **~86–87% of games/rows**,
touch a player who appears in more than one split — because a frequent player's several
games scatter across train/val/test under game-level random assignment. **~4,000+ players
sit in both train and test in each month.** Any future supervised C4/C3 model therefore has
a concrete player-identity leakage path from train into test, and current bootstrap CIs (game
or row clustered) **understate** uncertainty for player-correlated effects.

## 9. Strict player-disjoint split feasibility

A strict split requires partitioning *players* into disjoint train/val/test sets such that
no game crosses a boundary — i.e. assigning **whole connected components** of the player–game
graph (nodes = players, edges = games). Component structure:

| Graph | Games | Players | Components | Largest comp (games) | Largest comp (players) | Largest comp (rows) |
|---|---|---|---|---|---|---|
| 2024-09 | 24,520 | 17,116 | 946 | **22,552 (92.0%)** | 14,719 (86.0%) | 60,021 (91.8%) |
| 2024-10 | 23,496 | 17,209 | 1,082 | **21,762 (92.6%)** | 14,640 (85.1%) | 57,966 (92.2%) |
| Pooled 09+10 | 48,016 | 30,979 | 1,409 | **45,434 (94.6%)** | 27,613 (89.1%) | 121,011 (94.4%) |

The second-largest components are tiny (next few are ~40–100 games; ~73–77% of components
are single games). The **giant component swallows ~92% of games per month** (~95% pooled,
because cross-month players bridge the two monthly giants).

**Verdict — strict 3-way player-disjoint split is infeasible** for this data:

- Component assignment forces the giant component (~92%) entirely into **one** split →
  no 70/15/15 (or any balanced) partition exists.
- An edge-cut alternative (drop games whose two players land in different splits) would
  discard a large fraction of the giant component's ~22.5k games to carve disjoint sides,
  destroying sample size and skewing rating/checkpoint/termination balance.
- This holds **within month and pooled**.

**What is feasible instead:**

- A **player-disjoint held-out robustness slice**: reserve a set of players (drawn from the
  small components plus a carved subset) as a disjoint evaluation set, accepting the loss of
  cross-edge games. This is a *secondary robustness* check, not the primary split, and costs
  many games.
- **Player-disjoint validation only** (rather than full train/val/test disjointness) is
  similarly limited by the giant component.

Because the giant-component result is unambiguous, the connected-component computation does
**not** need to be re-derived in 11.3B as a feasibility gate — it can go straight to the
clustered-uncertainty route, optionally adding a disjoint robustness slice.

## 10. Player-clustered uncertainty feasibility

Player-clustered bootstrap is **practical and recommended**. Options and recommendation:

| Clustering unit | Use | Recommendation |
|---|---|---|
| Game ID | current | Baseline; understates player dependence |
| **Mover player (White at checkpoint)** | next-move-loss rows | **Primary for C4/Atlas** — the row's decision-maker |
| Single player (either side) | outcome rows | Secondary |
| Two-way White×Black | outcome/flagging rows | For flagging analyses where both players matter |
| Game **and** mover player | next-move-loss rows | Most conservative; both dependencies |

**Per analysis:**

- **E3/E4 outcome deltas (11.2B):** outcome depends on *both* players → cluster on game,
  with a two-way (White, Black) player-cluster robustness variant. For the flagging channel
  specifically, the **eventual loser / flagging side** is the natural focal cluster, but
  both-player clustering is the safe default.
- **Next-move-loss rows (C4 / Atlas):** cluster on **mover player** (always White at these
  checkpoints) — that is the unit generating the decision. A game-and-mover combined cluster
  is the conservative add-on.
- **Flagging-risk analyses:** both players matter (one flags, one benefits) → two-way
  cluster.

**Implementation feasibility:** the existing `bootstrap_ci.py` already does **game-level
cluster resampling** via a `{game_id: [row_indices]}` index and
`rng.choice(unique_clusters, size=N, replace=True)`. Swapping the cluster key to a **hashed
mover-player ID** is a direct generalization — same machinery, different grouping column. The
Atlas (`bootstrap_mean_es_ci`) and termination decomposition use the same game-cluster
pattern and would extend identically. Hashed IDs (built in ignored artifacts, §5) let this
run **without exposing usernames**. Compute is trivial (resampling ~17k clusters × ~1k
replicates).

## 11. Implications for 11.2B termination decomposition

- Repeated players **could** have tightened the flagging-channel CIs (rows are
  player-correlated; game clustering does not absorb cross-game player correlation).
- However the flagging effect is **very large** (time-forfeit −0.118/−0.131 cz, replicated
  across two months) relative to **moderate** concentration (top decile ~30% of rows). A
  player-clustered CI will be **wider but is unlikely to cross zero** given the effect size.
- **To verify in 11.3B:** recompute the headline termination-channel deltas under
  two-way (White, Black) player-clustered bootstrap. Expect the qualitative conclusion (the
  residual is the flagging channel) to survive; confirm, don't assume.

## 12. Implications for 15.1B Constraint Atlas

- Descriptive summaries are **less vulnerable** than test-set predictive claims, but dense
  cells are partly the **same frequent players** (top decile ~30% of rows).
- The **eval-band pattern** (the headline, replicated both months) is structural and almost
  certainly robust, but should later carry a **mover-player-clustered CI** to be claim-grade.
- **Low-clock sparse cells** (`<10s`, `10–30s`; n~90) are the **most vulnerable** to
  repeated-player concentration — a handful of accounts can move a tiny cell. This reinforces
  the 15.1B verdict that the non-replicating low-clock bump is an **artifact**, and that such
  cells stay descriptive-only.
- No re-run is required now; flag a **player-clustered robustness pass** on the Atlas
  headline cells as an optional 11.3B add-on.

## 13. Implications for future C3/C4 modeling

- **Controlled C4 modeling (15.1C)** must **not** proceed on the current game-level split:
  ~86% of rows touch a multi-split player and ~4,000+ players span train/test, a direct
  leakage path. Required before 15.1C: a **player-aware uncertainty/split plan** — at minimum
  mover-player-clustered evaluation, ideally plus a player-disjoint robustness slice (§9).
- **C3 sharpness × clock moderation (15.2B)** must not claim moderation without
  **player-clustered or player-disjoint robustness**; otherwise apparent moderation could be
  player composition (style/rating) rather than a within-player effect.
- Cross-month "independent replication" language should be qualified (§7): ~40% row-level
  player overlap between months.

## 14. Recommended 11.3B design

**Option A — Player Metadata Extraction + Clustered Bootstrap Implementation** (recommended).

Scope:

1. **Safe player metadata extraction** — rebuild `game_id → (white, black)` from the raw
   PGN headers and emit **hashed, salted player IDs only**, into **gitignored** `data/`
   artifacts (mover-player ID, both-player IDs; bot flag). No usernames persisted.
2. **Joins** of hashed IDs to E3/E4 predictions and next-move-loss artifacts on `game_id`.
3. **Player-concentration report** (aggregate counts only; this audit's tables, productized).
4. **Cluster-bootstrap utilities** generalizing `bootstrap_ci.py`: cluster key ∈ {game,
   mover-player, two-way player, game+mover}, reusing the existing index/resample machinery.
5. **Re-run key uncertainty checks** under player clustering for the **11.2B** headline
   termination deltas and the **15.1B** Atlas headline (eval-band) cells; report whether
   conclusions survive.
6. *(Optional)* construct a **player-disjoint held-out robustness slice** from small
   components for a future C4 sanity check — explicitly secondary, given §9.

**Not Option B** (strict player-disjoint split): the giant component (~92%) makes a balanced
3-way disjoint split impossible; it would only be viable as a costly held-out slice, folded
into Option A step 6.

**Not Option C** (feasibility-only extension): identifiers and graph structure are now
known, so a further pure-audit ticket is unnecessary.

## 15. Open questions

- Should the project salt be a fixed ignored config (reproducible hashed IDs across runs) or
  per-run random (stronger privacy, less reproducible)? Recommend **fixed ignored salt** for
  reproducibility, since IDs never leave ignored artifacts.
- For flagging analyses, is the right focal cluster the **flagging (losing-on-time) side**,
  the **both-player** pair, or the game? Recommend reporting **both game and two-way player**
  and treating divergence as the finding.
- Do we want a **player-disjoint robustness slice** in 11.3B, or defer it to a dedicated
  ticket once C4 modeling is specified? Recommend deferring the slice; ship clustered
  bootstrap first.
- Should bot-involved games (12 / 7) be filtered for C4, or kept with a flag? Negligible
  either way; recommend a **flag, not a filter**, to preserve sample.

## 16. Recommended next ticket

**11.3B — Player Metadata Extraction + Clustered-Bootstrap Implementation (Option A).**
Build hashed player IDs in ignored artifacts, generalize the cluster bootstrap to
mover-player / two-way-player clustering, and re-verify the 11.2B and 15.1B headline
uncertainties under player clustering. This is the prerequisite hardening for controlled C4
modeling (15.1C) and C3 sharpness moderation (15.2B). Strict player-disjoint splitting is
**not** pursued as the primary route (giant component, §9); a player-disjoint held-out slice
may be added as a secondary robustness check.
