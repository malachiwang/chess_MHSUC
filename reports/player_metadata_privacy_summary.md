# Player Metadata Privacy Summary

**Ticket:** 11.3B — Player Metadata Extraction + Clustered Uncertainty
**Status:** privacy-safe extraction implemented; hashed IDs in gitignored artifacts only

## 1. Purpose

Player-clustered uncertainty (11.3A's recommended hardening, since strict
player-disjoint splitting is infeasible) requires a `game_id → player` map. This
document records exactly what player information is extracted, what is and is not
persisted, and the anonymization policy — so that no raw usernames ever enter the
repository.

## 2. Raw identifier source

Player usernames exist **only** in the raw Lichess PGN headers
(`data/raw/lichess/lichess_<YYYY>_<MM>_first250k.pgn`, gitignored): the `White`,
`Black`, and `Site` (game slug) tags, plus optional `WhiteTitle`/`BlackTitle`. The
parser strips usernames at parse time (DATA_POLICY.md), so no processed artifact
carries them; this module re-reads the raw headers solely to compute hashes.

## 3. What is extracted

Header-level only, per game:

- `game_id` (the Site slug);
- a one-way **hash** of the normalized White username (`white_player_hash`);
- a one-way **hash** of the normalized Black username (`black_player_hash`);
- bot flags `white_is_bot` / `black_is_bot` (from `WhiteTitle`/`BlackTitle == "BOT"`);
- `version_tag`.

Usernames are normalized (strip whitespace, lower-case) and hashed immediately;
the raw strings are never written to disk.

## 4. What is not committed

- **No raw usernames** — anywhere (artifacts, reports, source, tests, fixtures).
- **No player hashes in committed files** — hashes live only in gitignored
  `data/processed/player_metadata_*.parquet`.
- Committed reports contain **aggregate counts only**.
- An `assert_no_raw_usernames` guard refuses to persist any frame carrying a
  raw-username column. A test confirms hashes do not contain the source string.

## 5. Hashing / anonymization policy

- One-way `blake2b` (12-byte digest) over `pepper + normalized_username`.
- The pepper is a fixed, **non-secret** determinism device (default
  `chess-mhsuc-player-v1`, overridable via `--pepper` or `$CHESS_MHSUC_PLAYER_PEPPER`).
  It is not a credential: the hashes never leave gitignored artifacts and no
  usernames are committed, so there is nothing to reverse from the repository.
- Anonymous / missing / `?` usernames normalize to `None` and hash to `None`
  (no fabricated identity).

## 6. Generated ignored artifacts

| Artifact | Rows | Gitignored |
|---|---|---|
| `data/processed/player_metadata_2024_09_250k_v1.parquet` | 250,000 | yes (`data/`, `*.parquet`) |
| `data/processed/player_metadata_2024_10_250k_v1.parquet` | 250,000 | yes |

Columns: `game_id, white_player_hash, black_player_hash, white_is_bot,
black_is_bot, version_tag`. No raw-username columns. Verified via `git check-ignore`.

## 7. Reported aggregate counts

From the two raw caches (header-level; covers all time controls in the first-250k
prefix, a superset of the 600+0 primary games):

| Month | Games | Unique players | Bot games | Anonymous (W/B) | game_id unique |
|---|---|---|---|---|---|
| 2024-09 | 250,000 | 108,642 | 634 | 0 / 0 | yes |
| 2024-10 | 250,000 | 112,556 | 434 | 0 / 0 | yes |

Join coverage onto the analysis frames (primary 600+0 games only):

| Use | Month | Rows | Player hash matched |
|---|---|---|---|
| Termination (E3/E4 val rows/model) | 2024-09 | 19,646 | 100.0% |
| Termination (E3/E4 val rows/model) | 2024-10 | 18,884 | 100.0% |
| Atlas (non-mate next-move rows w/ mover) | 2024-09 | 61,956 | 100.0% |
| Atlas (non-mate next-move rows w/ mover) | 2024-10 | 59,625 | 100.0% |

All primary games matched a hashed identity; 0 anonymous rows dropped.

## 8. Bot / deleted / anonymous handling

- Bots: detected via `WhiteTitle`/`BlackTitle == "BOT"` and flagged, **not
  filtered** (634 / 434 of 250k header games; a negligible share of the 600+0
  primary set). A flag preserves sample while allowing later sensitivity checks.
- Deleted / anonymous: none observed in either raw cache (0 `?`/empty White or
  Black). Had any existed, they would normalize to `None`, hash to `None`, and be
  dropped from clustering with an accounting note.

## 9. Reproducibility caveats

- With the fixed default pepper, re-running extraction reproduces identical hashes
  (deterministic), enabling reproducible clustered CIs.
- Changing the pepper changes all hashes (only the partition labels change; CIs are
  invariant to the labeling).
- The raw PGN caches are local and gitignored; regenerating metadata requires them.
- Hashes are opaque identifiers for clustering only — they support no identity
  research and are never deanonymized.
