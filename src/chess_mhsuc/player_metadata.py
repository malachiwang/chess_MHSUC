"""
Privacy-safe player metadata extraction — Ticket 11.3B.

Player usernames live ONLY in the raw PGN headers (`White`, `Black`); the parser
strips them at parse time (DATA_POLICY.md) so no processed artifact carries them.
This module rebuilds a `game_id -> hashed-player-id` map from the raw PGN headers
for player-clustered uncertainty, and NEVER persists or reports raw usernames.

What is extracted (header-level only): game_id (Site slug), White/Black usernames
(used transiently to compute hashes, then dropped), optional WhiteTitle/BlackTitle
bot flags.

What is written: an IGNORED parquet under data/processed/ with columns
    game_id, white_player_hash, black_player_hash, white_is_bot, black_is_bot,
    version_tag
— hashes only, no raw usernames. Reports built downstream contain aggregate
counts only (never hashes or usernames).

Hashing: one-way blake2b over a normalized (stripped, lower-cased) username plus a
fixed, NON-SECRET project pepper. The pepper only makes hashes deterministic across
runs; it is not a secret because the hashed IDs never leave gitignored artifacts and
no usernames are ever committed. Override via --pepper or the
CHESS_MHSUC_PLAYER_PEPPER env var if desired.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.player_metadata \\
        --dataset-id lichess_ten_zero_2024_09_250k_v1 \\
        --version-tag 2024_09_250k_v1 \\
        --output data/processed/player_metadata_2024_09_250k_v1.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Iterable, Iterator

import polars as pl

# Non-secret determinism device (see module docstring). Not a credential.
DEFAULT_PEPPER = "chess-mhsuc-player-v1"
_PEPPER_ENV = "CHESS_MHSUC_PLAYER_PEPPER"
_HASH_DIGEST_SIZE = 12  # 24 hex chars

_OUTPUT_COLS = [
    "game_id", "white_player_hash", "black_player_hash",
    "white_is_bot", "black_is_bot", "version_tag",
]
# Raw username columns must NEVER appear in any persisted artifact.
_FORBIDDEN_OUTPUT_COLS = {"white", "black", "white_user", "black_user",
                          "White", "Black"}


# ---------------------------------------------------------------------------
# A. Normalization + hashing (pure)
# ---------------------------------------------------------------------------

def normalize_username(name: str | None) -> str | None:
    """
    Normalize a raw username: strip whitespace, lower-case. Missing / empty /
    anonymous placeholders ('?') normalize to None (no stable identity).
    """
    if name is None:
        return None
    s = name.strip()
    if s == "" or s == "?":
        return None
    return s.lower()


def hash_player(normalized: str | None, pepper: str = DEFAULT_PEPPER) -> str | None:
    """
    One-way hash of a normalized username. Returns None for None input
    (anonymous / missing). Never returns the raw username.
    """
    if normalized is None:
        return None
    digest = hashlib.blake2b(
        pepper.encode("utf-8") + normalized.encode("utf-8", "ignore"),
        digest_size=_HASH_DIGEST_SIZE,
    )
    return digest.hexdigest()


def resolve_pepper(cli_pepper: str | None = None) -> str:
    """CLI override > env var > default. Documented as non-secret."""
    if cli_pepper:
        return cli_pepper
    return os.environ.get(_PEPPER_ENV, DEFAULT_PEPPER)


# ---------------------------------------------------------------------------
# B. PGN header parsing (pure-ish; operates on text or a file)
# ---------------------------------------------------------------------------

def game_id_from_site(site: str | None) -> str | None:
    """Extract the Lichess game slug from a Site URL (last path component)."""
    if not site:
        return None
    slug = site.rstrip("/").split("/")[-1]
    return slug or None


def parse_header_line(line: str) -> tuple[str, str] | None:
    """Parse a single PGN header line `[Key "Value"]` -> (Key, Value) or None."""
    if not line.startswith("["):
        return None
    try:
        key = line[1:line.index(" ")]
        value = line[line.index('"') + 1:line.rindex('"')]
    except ValueError:
        return None
    return key, value


def iter_game_headers(lines: Iterable[str]) -> Iterator[dict[str, str]]:
    """
    Yield one header dict per game from an iterable of PGN lines. A new game
    begins at each `[Event ...]` line. Movetext lines are ignored.
    """
    cur: dict[str, str] = {}
    started = False
    for line in lines:
        if line.startswith("[Event "):
            if started and cur:
                yield cur
            cur = {}
            started = True
        if line.startswith("["):
            kv = parse_header_line(line)
            if kv is not None:
                cur[kv[0]] = kv[1]
    if started and cur:
        yield cur


def headers_from_text(text: str) -> list[dict[str, str]]:
    """Convenience wrapper for tests: parse all game headers from PGN text."""
    return list(iter_game_headers(text.splitlines()))


def _headers_to_metadata_row(
    h: dict[str, str], pepper: str, version_tag: str,
) -> dict | None:
    """Build one hashed metadata row from a header dict, or None if no game_id."""
    game_id = game_id_from_site(h.get("Site"))
    if game_id is None:
        return None
    return {
        "game_id": game_id,
        "white_player_hash": hash_player(normalize_username(h.get("White")), pepper),
        "black_player_hash": hash_player(normalize_username(h.get("Black")), pepper),
        "white_is_bot": h.get("WhiteTitle", "") == "BOT",
        "black_is_bot": h.get("BlackTitle", "") == "BOT",
        "version_tag": version_tag,
    }


# ---------------------------------------------------------------------------
# C. Raw PGN location
# ---------------------------------------------------------------------------

def locate_raw_pgn(version_tag: str) -> Path:
    """
    Map a version tag (e.g. '2024_09_250k_v1') to its local raw PGN cache path
    (e.g. data/raw/lichess/lichess_2024_09_first250k.pgn). Raises if absent.
    """
    parts = version_tag.split("_")
    if len(parts) < 3:
        raise ValueError(f"cannot parse month/size from version tag {version_tag!r}")
    year, month = parts[0], parts[1]
    size = parts[2]  # e.g. '250k' or '25k'
    candidate = Path(f"data/raw/lichess/lichess_{year}_{month}_first{size}.pgn")
    if not candidate.exists():
        raise FileNotFoundError(
            f"raw PGN cache not found for {version_tag}: expected {candidate}"
        )
    return candidate


# ---------------------------------------------------------------------------
# D. Extraction
# ---------------------------------------------------------------------------

def extract_player_metadata(
    pgn_path: str | Path,
    version_tag: str,
    pepper: str = DEFAULT_PEPPER,
) -> pl.DataFrame:
    """
    Stream the raw PGN cache and return a hashed player-metadata frame
    (game_id + hashes + bot flags + version_tag). No raw usernames retained.
    """
    rows: list[dict] = []
    with open(pgn_path, encoding="utf-8", errors="ignore") as f:
        for h in iter_game_headers(f):
            row = _headers_to_metadata_row(h, pepper, version_tag)
            if row is not None:
                rows.append(row)
    df = pl.DataFrame(rows, schema={
        "game_id": pl.Utf8,
        "white_player_hash": pl.Utf8,
        "black_player_hash": pl.Utf8,
        "white_is_bot": pl.Boolean,
        "black_is_bot": pl.Boolean,
        "version_tag": pl.Utf8,
    })
    assert_no_raw_usernames(df)
    return df


def assert_no_raw_usernames(df: pl.DataFrame) -> None:
    """Guard: the metadata frame must not carry any raw-username column."""
    bad = _FORBIDDEN_OUTPUT_COLS & set(df.columns)
    if bad:
        raise ValueError(f"refusing to persist raw username columns: {sorted(bad)}")


def metadata_counts(df: pl.DataFrame) -> dict:
    """Aggregate counts for reporting (no hashes, no usernames)."""
    white = df["white_player_hash"]
    black = df["black_player_hash"]
    uniq = set(white.drop_nulls().to_list()) | set(black.drop_nulls().to_list())
    bot_games = int(df.filter(pl.col("white_is_bot") | pl.col("black_is_bot")).height)
    return {
        "n_games": df.height,
        "n_unique_white_players": white.n_unique(),
        "n_unique_black_players": black.n_unique(),
        "n_unique_players": len(uniq),
        "n_white_anon": int(white.null_count()),
        "n_black_anon": int(black.null_count()),
        "n_bot_games": bot_games,
        "game_id_unique": df["game_id"].n_unique() == df.height,
    }


# ---------------------------------------------------------------------------
# E. Joins
# ---------------------------------------------------------------------------

def join_white_black(df: pl.DataFrame, meta: pl.DataFrame) -> pl.DataFrame:
    """
    Left-join white/black player hashes + bot flags onto any frame with a
    game_id column. Raises if the join multiplies rows (meta must be 1/game).
    """
    if meta.select("game_id").n_unique() != meta.height:
        raise ValueError("player metadata has duplicate game_id rows")
    cols = ["game_id", "white_player_hash", "black_player_hash",
            "white_is_bot", "black_is_bot"]
    n_before = df.height
    out = df.join(meta.select(cols), on="game_id", how="left")
    if out.height != n_before:
        raise ValueError(f"join changed row count: {n_before} -> {out.height}")
    return out


def join_mover_player(nml: pl.DataFrame, meta: pl.DataFrame) -> pl.DataFrame:
    """
    Add mover/opponent player hashes + bot flags to a next-move-loss frame
    (which has a `mover_color` column). Mover is White when mover_color=='white',
    else Black; opponent is the other side. Implemented for both colors even
    though numbered checkpoints are currently White-to-move only.
    """
    joined = join_white_black(nml, meta)
    is_white = pl.col("mover_color") == "white"
    return joined.with_columns([
        pl.when(is_white).then(pl.col("white_player_hash"))
        .otherwise(pl.col("black_player_hash")).alias("mover_player_hash"),
        pl.when(is_white).then(pl.col("black_player_hash"))
        .otherwise(pl.col("white_player_hash")).alias("opponent_player_hash"),
        pl.when(is_white).then(pl.col("white_is_bot"))
        .otherwise(pl.col("black_is_bot")).alias("mover_is_bot"),
        pl.when(is_white).then(pl.col("black_is_bot"))
        .otherwise(pl.col("white_is_bot")).alias("opponent_is_bot"),
    ])


def join_coverage(joined: pl.DataFrame, hash_col: str = "white_player_hash") -> dict:
    """Report how many rows got a non-null player hash after a join."""
    n = joined.height
    matched = int(joined.filter(pl.col(hash_col).is_not_null()).height)
    return {
        "n_rows": n,
        "n_matched": matched,
        "n_unmatched": n - matched,
        "match_fraction": round(matched / n, 4) if n else None,
    }


# ---------------------------------------------------------------------------
# F. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Privacy-safe player metadata extraction (Ticket 11.3B). "
                    "Writes hashed IDs only; never raw usernames."
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--raw-pgn", default=None,
                        help="override; default located from --version-tag")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pepper", default=None,
                        help=f"override hashing pepper (else ${_PEPPER_ENV} or default)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"{output} exists; pass --overwrite")

    pepper = resolve_pepper(args.pepper)
    raw_pgn = Path(args.raw_pgn) if args.raw_pgn else locate_raw_pgn(args.version_tag)
    print(f"[player_metadata] reading {raw_pgn}", file=sys.stderr)

    df = extract_player_metadata(raw_pgn, args.version_tag, pepper)
    assert_no_raw_usernames(df)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output)

    counts = metadata_counts(df)
    print(f"[player_metadata] wrote {output} ({df.height:,} games)", file=sys.stderr)
    print(f"  unique players: {counts['n_unique_players']:,}; "
          f"bot games: {counts['n_bot_games']}; "
          f"anon white/black: {counts['n_white_anon']}/{counts['n_black_anon']}; "
          f"game_id unique: {counts['game_id_unique']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
