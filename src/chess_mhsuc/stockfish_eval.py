"""
stockfish_eval.py — Fixed-depth Stockfish evaluation for pilot checkpoint positions.

Evaluates all primary_numbered checkpoint positions in the broad dataset using
a local Stockfish engine at fixed depth.  Produces a Parquet artifact, metadata
JSON, and two Markdown reports (summary + phase report).

This module does NOT train models, modify feature Parquet files, or scale data.
Local Stockfish eval is objective-position context, not perfect truth.
Fixed-depth evaluation is not causal.

Functions
---------
A. resolve_stockfish_path
B. get_stockfish_version
C. load_primary_numbered_positions
D. open_pgn_stream           (streaming helper)
E. index_target_games        (find specific games in PGN stream)
F. reconstruct_fen_at_ply
G. score_to_white_pov
H. derive_sf_eval_features
I. analyse_fen
J. run_stockfish_eval
K. write_outputs
L. render_stockfish_eval_report
M. main (CLI)

Usage
-----
PYTHONPATH=src python -m chess_mhsuc.stockfish_eval \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --version-tag 2024_09_25k_v1 \\
    --positions data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet \\
    --raw-pgn <PATH_OR_URL> \\
    --depth 12 \\
    --output-parquet data/processed/sf_eval_broad_2024_09_25k_v1.parquet \\
    --output-metadata data/processed/sf_eval_metadata_2024_09_25k_v1.json \\
    --output-report reports/stockfish_eval_2024_09_25k_v1.md \\
    --limit 10 \\
    --dry-run

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import chess
import chess.engine
import chess.pgn
import polars as pl
import zstandard


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MATE_CP_SENTINEL = 10_000
DEFAULT_DEPTH = 12
DEFAULT_VERSION_TAG = "2024_09_25k_v1"
DEFAULT_DATASET_ID = "lichess_ten_zero_2024_09_25k_v1"

# Eval buckets for sf_eval_cp (same conventions as project's existing eval features)
# Boundaries: ±100 (equal), ±300 (slight/clear boundary)
_BUCKET_BOUNDARIES = [(-MATE_CP_SENTINEL, "mate_black"),
                      (-300,              "losing_black"),
                      (-100,              "slight_black"),
                      (100,               "equal"),
                      (300,               "slight_white"),
                      (MATE_CP_SENTINEL,  "winning_white"),
                      (MATE_CP_SENTINEL + 1, "mate_white")]

_EVAL_STATUS_OK_CP   = "ok_cp"
_EVAL_STATUS_OK_MATE = "ok_mate"
_EVAL_STATUS_FEN_ERR = "fen_reconstruction_error"
_EVAL_STATUS_ILLEGAL = "illegal_position"
_EVAL_STATUS_ENG_ERR = "engine_error"
_EVAL_STATUS_TIMEOUT = "timeout"
_EVAL_STATUS_SKIPPED = "skipped"

_LICHESS_PGNS_URL = (
    "https://database.lichess.org/standard/"
    "lichess_db_standard_rated_2024-09.pgn.zst"
)

# Columns to include in the output Parquet (in order)
_OUTPUT_COLUMNS = [
    "dataset_id",
    "version_tag",
    "game_id",
    "ply",
    "selected_position_type",
    "split_set",
    "move_number",
    "result_class",
    "has_lichess_eval",
    "lichess_eval_cp",
    "lichess_eval_mate",
    "fen_hash",
    "sf_eval_available",
    "sf_eval_status",
    "sf_eval_cp",
    "sf_eval_mate",
    "sf_eval_mate_abs",
    "sf_eval_abs",
    "sf_eval_sign",
    "sf_eval_bucket",
    "sf_depth",
    "sf_nodes",
    "sf_time_ms",
    "sf_engine_name",
    "sf_engine_version",
    "sf_eval_timestamp_utc",
    "sf_error",
]


# ---------------------------------------------------------------------------
# A. Stockfish path resolution
# ---------------------------------------------------------------------------

def resolve_stockfish_path(explicit_path: str | None = None) -> str:
    """
    Resolve the Stockfish binary path.

    Resolution order:
    1. ``explicit_path`` argument
    2. ``STOCKFISH_PATH`` environment variable
    3. ``shutil.which("stockfish")``

    Raises
    ------
    FileNotFoundError
        If Stockfish cannot be found through any channel, with instructions.
    """
    candidate = explicit_path or os.environ.get("STOCKFISH_PATH") or shutil.which("stockfish")
    if not candidate:
        raise FileNotFoundError(
            "Stockfish binary not found.\n"
            "To fix: install Stockfish (e.g. 'brew install stockfish' on macOS)\n"
            "or set STOCKFISH_PATH=/path/to/stockfish,\n"
            "or pass --stockfish-path /path/to/stockfish to the CLI."
        )
    if not Path(candidate).exists():
        raise FileNotFoundError(
            f"Stockfish path '{candidate}' does not exist.\n"
            "Check the path and try again."
        )
    return str(candidate)


# ---------------------------------------------------------------------------
# B. Get Stockfish version
# ---------------------------------------------------------------------------

def get_stockfish_version(stockfish_path: str) -> str:
    """
    Return the Stockfish version string (e.g. 'Stockfish 18').

    Uses UCI protocol via subprocess.  Falls back to 'unknown' on error.
    """
    try:
        result = subprocess.run(
            [stockfish_path],
            input="uci\nquit\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if line.startswith("id name "):
                return line[len("id name "):].strip()
        # Fallback: first non-empty stdout line is often the version header
        for line in result.stdout.splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# C. Load primary-numbered positions
# ---------------------------------------------------------------------------

def load_primary_numbered_positions(
    positions_path: Path,
    splits_path: Path | None = None,
    include_last: bool = False,
) -> pl.DataFrame:
    """
    Load checkpoint positions from the broad positions Parquet.

    Filters to primary_numbered (excludes ``selected_position_type == 'last'``
    by default).  If ``splits_path`` is provided, joins ``split_set`` from the
    splits JSON so each row knows its train/val/test assignment.

    Parameters
    ----------
    positions_path:
        Path to ``ten_zero_positions_broad_*.parquet``.
    splits_path:
        Optional path to ``splits_*.json``.  If provided, adds ``split_set``
        column.  If absent, ``split_set`` is set to ``"unknown"``.
    include_last:
        If True, include ``selected_position_type == 'last'`` rows too.

    Returns
    -------
    pl.DataFrame
        Columns: game_id, ply, selected_position_type, move_number,
        result_class, split_set, eval_cp, eval_mate, has_eval.
    """
    df = pl.read_parquet(positions_path)

    if not include_last:
        df = df.filter(pl.col("selected_position_type") != "last")

    # Attach split assignments
    if splits_path is not None and splits_path.exists():
        with open(splits_path) as f:
            splits_data = json.load(f)
        assignments: dict[str, str] = splits_data.get("assignments", {})
        split_series = pl.Series(
            "split_set",
            [assignments.get(gid, "unknown") for gid in df["game_id"].to_list()],
            dtype=pl.Utf8,
        )
        df = df.with_columns(split_series)
    else:
        df = df.with_columns(pl.lit("unknown").alias("split_set"))

    # Ensure required columns exist
    needed = ["game_id", "ply", "selected_position_type", "move_number",
              "result_class", "split_set", "eval_cp", "eval_mate", "has_eval"]
    for col in needed:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    return df.select(needed)


# ---------------------------------------------------------------------------
# D. Open PGN stream helper
# ---------------------------------------------------------------------------

def open_pgn_stream(raw_pgn: str) -> Generator[io.TextIOWrapper, None, None]:
    """
    Open a PGN source as a text stream.

    Supports:
    - Local ``.pgn`` file
    - Local ``.pgn.zst`` file (zstd-compressed)
    - HTTP(S) URL to a ``.pgn.zst`` (streamed, not fully downloaded)

    Yields a text stream suitable for ``chess.pgn.read_game()``.
    """
    is_url = raw_pgn.startswith("http://") or raw_pgn.startswith("https://")

    if is_url:
        req = urllib.request.Request(
            raw_pgn, headers={"User-Agent": "chess-MHSUC/0.1 stockfish-eval"}
        )
        response = urllib.request.urlopen(req, timeout=60)
        try:
            if raw_pgn.endswith(".zst"):
                dctx = zstandard.ZstdDecompressor()
                raw_reader = dctx.stream_reader(response, read_size=131_072, closefd=False)
                buffered = io.BufferedReader(raw_reader, buffer_size=524_288)
                yield io.TextIOWrapper(buffered, encoding="utf-8", errors="replace")
            else:
                yield io.TextIOWrapper(response, encoding="utf-8", errors="replace")
        finally:
            response.close()
    else:
        path = Path(raw_pgn)
        if not path.exists():
            raise FileNotFoundError(f"Raw PGN not found: {raw_pgn}")
        if raw_pgn.endswith(".zst"):
            dctx = zstandard.ZstdDecompressor()
            with open(path, "rb") as fh:
                with dctx.stream_reader(fh, read_size=131_072) as raw_reader:
                    buffered = io.BufferedReader(raw_reader, buffer_size=524_288)
                    yield io.TextIOWrapper(buffered, encoding="utf-8", errors="replace")
        else:
            with open(path, encoding="utf-8", errors="replace") as fh:
                yield fh


# ---------------------------------------------------------------------------
# E. Index target games from PGN stream
# ---------------------------------------------------------------------------

def index_target_games(
    raw_pgn: str,
    target_game_ids: set[str],
    progress: bool = True,
) -> dict[str, chess.pgn.Game]:
    """
    Stream the PGN source and return a dict of ``{game_id: game}`` for
    every game whose ID is in ``target_game_ids``.

    Stops early once all target games have been found.
    """
    found: dict[str, chess.pgn.Game] = {}
    n_scanned = 0

    for stream in open_pgn_stream(raw_pgn):
        while True:
            try:
                game = chess.pgn.read_game(stream)
            except Exception:
                n_scanned += 1
                continue
            if game is None:
                break
            n_scanned += 1

            site = game.headers.get("Site", "")
            game_id = _extract_game_id(site)
            if game_id and game_id in target_game_ids:
                found[game_id] = game

            if progress and n_scanned % 1000 == 0:
                print(
                    f"  [index] scanned {n_scanned:,} games, "
                    f"found {len(found):,}/{len(target_game_ids):,}",
                    file=sys.stderr,
                )

            if len(found) == len(target_game_ids):
                break

    return found


def _extract_game_id(site: str) -> str | None:
    """Extract the game ID from a Lichess Site URL (last path segment)."""
    if not site:
        return None
    segment = site.rstrip("/").split("/")[-1]
    return segment if segment else None


# ---------------------------------------------------------------------------
# F. Reconstruct FEN at target ply
# ---------------------------------------------------------------------------

def reconstruct_fen_at_ply(
    game: chess.pgn.Game,
    target_ply: int,
) -> tuple[str | None, str]:
    """
    Replay mainline moves and return the FEN after ``target_ply`` half-moves.

    ``target_ply`` is 1-indexed: ply=1 means after White's first move,
    ply=2 after Black's reply, etc.

    Returns
    -------
    (fen, status)
        ``fen`` is None on error; ``status`` is one of the _EVAL_STATUS_* constants.
    """
    if target_ply < 1:
        return None, _EVAL_STATUS_FEN_ERR

    board = game.board()
    current_ply = 0

    for move in game.mainline_moves():
        try:
            board.push(move)
        except Exception:
            return None, _EVAL_STATUS_ILLEGAL
        current_ply += 1
        if current_ply == target_ply:
            return board.fen(), _EVAL_STATUS_OK_CP  # status updated later

    # target_ply exceeds game length
    return None, _EVAL_STATUS_FEN_ERR


# ---------------------------------------------------------------------------
# G. Score to White POV
# ---------------------------------------------------------------------------

def score_to_white_pov(
    score: chess.engine.PovScore,
) -> tuple[int | None, int | None]:
    """
    Convert a ``chess.engine.PovScore`` to White-POV (sf_eval_cp, sf_eval_mate).

    Convention matches the project's existing eval fields:
    - positive cp = White advantage
    - negative cp = Black advantage
    - +MATE_CP_SENTINEL = White has forced mate
    - -MATE_CP_SENTINEL = Black has forced mate
    - sf_eval_mate: signed distance (+ = White wins, - = Black wins); None for non-mate

    Parameters
    ----------
    score : chess.engine.PovScore
        Score from ``engine.analyse()``.

    Returns
    -------
    (sf_eval_cp, sf_eval_mate)
    """
    white_score = score.white()

    if white_score.is_mate():
        mate_in = white_score.mate()  # type: ignore[union-attr]
        # Positive mate = White has forced mate; negative = Black has forced mate
        if mate_in is None:
            return None, None
        if mate_in > 0:
            return MATE_CP_SENTINEL, mate_in
        else:
            return -MATE_CP_SENTINEL, mate_in
    else:
        cp = white_score.score()
        if cp is None:
            return None, None
        # Clamp to ±(MATE_CP_SENTINEL - 1) for non-mate positions
        cp = max(-MATE_CP_SENTINEL + 1, min(MATE_CP_SENTINEL - 1, cp))
        return cp, None


# ---------------------------------------------------------------------------
# H. Derive SF eval features
# ---------------------------------------------------------------------------

def derive_sf_eval_features(
    sf_eval_cp: int | None,
    sf_eval_mate: int | None,
) -> dict:
    """
    Derive secondary eval features from the primary (sf_eval_cp, sf_eval_mate) pair.

    Returns a dict with keys:
    - sf_eval_mate_abs: abs(sf_eval_mate) or None
    - sf_eval_abs:      abs(sf_eval_cp) or None
    - sf_eval_sign:     1 (White better), -1 (Black better), 0 (equal), None
    - sf_eval_bucket:   string label based on sf_eval_cp boundaries

    Bucket boundaries (sf_eval_cp):
    mate_black ≤ -10000 | losing_black (-10000, -300] | slight_black (-300, -100]
    equal (-100, 100) | slight_white [100, 300) | winning_white [300, 10000) | mate_white ≥ 10000
    """
    if sf_eval_cp is None:
        return {
            "sf_eval_mate_abs": None,
            "sf_eval_abs": None,
            "sf_eval_sign": None,
            "sf_eval_bucket": None,
        }

    sf_eval_mate_abs = abs(sf_eval_mate) if sf_eval_mate is not None else None
    sf_eval_abs = abs(sf_eval_cp)
    sf_eval_sign = 1 if sf_eval_cp > 0 else (-1 if sf_eval_cp < 0 else 0)

    # Bucket assignment
    if sf_eval_cp <= -MATE_CP_SENTINEL:
        bucket = "mate_black"
    elif sf_eval_cp <= -300:
        bucket = "losing_black"
    elif sf_eval_cp <= -100:
        bucket = "slight_black"
    elif sf_eval_cp < 100:
        bucket = "equal"
    elif sf_eval_cp < 300:
        bucket = "slight_white"
    elif sf_eval_cp < MATE_CP_SENTINEL:
        bucket = "winning_white"
    else:
        bucket = "mate_white"

    return {
        "sf_eval_mate_abs": sf_eval_mate_abs,
        "sf_eval_abs": sf_eval_abs,
        "sf_eval_sign": sf_eval_sign,
        "sf_eval_bucket": bucket,
    }


# ---------------------------------------------------------------------------
# I. Analyse a single FEN
# ---------------------------------------------------------------------------

def analyse_fen(
    engine: chess.engine.SimpleEngine,
    fen: str,
    depth: int,
) -> dict:
    """
    Analyse a position FEN with the engine at the given depth.

    Returns a dict with all output schema fields for one position.
    On error, returns a dict with sf_eval_available=False and the error recorded.
    """
    t0 = time.time()
    result: dict = {
        "sf_eval_available": False,
        "sf_eval_status": _EVAL_STATUS_ENG_ERR,
        "sf_eval_cp": None,
        "sf_eval_mate": None,
        "sf_eval_mate_abs": None,
        "sf_eval_abs": None,
        "sf_eval_sign": None,
        "sf_eval_bucket": None,
        "sf_depth": depth,
        "sf_nodes": None,
        "sf_time_ms": None,
        "sf_error": None,
    }

    try:
        board = chess.Board(fen)
    except Exception as e:
        result["sf_eval_status"] = _EVAL_STATUS_ILLEGAL
        result["sf_error"] = f"Board init failed: {e}"
        result["sf_time_ms"] = int((time.time() - t0) * 1000)
        return result

    try:
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
    except Exception as e:
        result["sf_eval_status"] = _EVAL_STATUS_ENG_ERR
        result["sf_error"] = str(e)[:200]
        result["sf_time_ms"] = int((time.time() - t0) * 1000)
        return result

    elapsed_ms = int((time.time() - t0) * 1000)

    score = info.get("score")
    if score is None:
        result["sf_eval_status"] = _EVAL_STATUS_ENG_ERR
        result["sf_error"] = "Engine returned no score"
        result["sf_time_ms"] = elapsed_ms
        return result

    sf_eval_cp, sf_eval_mate = score_to_white_pov(score)

    if sf_eval_cp is None:
        result["sf_eval_status"] = _EVAL_STATUS_ENG_ERR
        result["sf_error"] = "score_to_white_pov returned None"
        result["sf_time_ms"] = elapsed_ms
        return result

    derived = derive_sf_eval_features(sf_eval_cp, sf_eval_mate)

    result.update({
        "sf_eval_available": True,
        "sf_eval_status": _EVAL_STATUS_OK_MATE if sf_eval_mate is not None else _EVAL_STATUS_OK_CP,
        "sf_eval_cp": sf_eval_cp,
        "sf_eval_mate": sf_eval_mate,
        "sf_eval_mate_abs": derived["sf_eval_mate_abs"],
        "sf_eval_abs": derived["sf_eval_abs"],
        "sf_eval_sign": derived["sf_eval_sign"],
        "sf_eval_bucket": derived["sf_eval_bucket"],
        "sf_depth": info.get("depth", depth),
        "sf_nodes": info.get("nodes"),
        "sf_time_ms": elapsed_ms,
        "sf_error": None,
    })
    return result


# ---------------------------------------------------------------------------
# J. Run full evaluation loop
# ---------------------------------------------------------------------------

def run_stockfish_eval(
    positions_df: pl.DataFrame,
    raw_pgn: str,
    stockfish_path: str,
    depth: int = DEFAULT_DEPTH,
    limit: int | None = None,
    dry_run: bool = False,
    resume_parquet: Path | None = None,
    dataset_id: str = DEFAULT_DATASET_ID,
    version_tag: str = DEFAULT_VERSION_TAG,
    engine_version: str = "unknown",
) -> pl.DataFrame:
    """
    Main evaluation loop.

    For each row in ``positions_df``:
    - Stream the raw PGN to find the game
    - Reconstruct the FEN at target ply
    - Evaluate with Stockfish

    Supports ``--limit`` (cap number of rows evaluated) and ``--resume``
    (skip rows whose (game_id, ply) already exist in ``resume_parquet``).

    Parameters
    ----------
    positions_df:
        Output of ``load_primary_numbered_positions()``.
    raw_pgn:
        Path or URL to the raw PGN archive.
    stockfish_path:
        Resolved path to the Stockfish binary.
    depth:
        Fixed analysis depth.
    limit:
        Maximum number of rows to evaluate.  None = evaluate all.
    dry_run:
        If True, print progress but do not write outputs.
    resume_parquet:
        If provided and exists, skip (game_id, ply) pairs already in it.
    dataset_id, version_tag:
        Metadata fields written to output.
    engine_version:
        Stockfish version string for recording.

    Returns
    -------
    pl.DataFrame
        One row per evaluated position, with all output schema columns.
    """
    # Determine which rows to process
    df = positions_df
    if resume_parquet is not None and Path(resume_parquet).exists():
        existing = pl.read_parquet(resume_parquet)
        done_pairs = set(zip(existing["game_id"].to_list(), existing["ply"].to_list()))
        mask = ~pl.Series([
            (g, p) in done_pairs
            for g, p in zip(df["game_id"].to_list(), df["ply"].to_list())
        ])
        df = df.filter(mask)
        print(f"  [resume] skipping {len(positions_df) - len(df)} already-evaluated rows", file=sys.stderr)

    if limit is not None:
        df = df.head(limit)

    if dry_run:
        print(f"  [dry-run] would evaluate {len(df)} positions at depth={depth}", file=sys.stderr)

    # Collect unique game_ids needed
    target_game_ids: set[str] = set(df["game_id"].to_list())
    print(f"  [eval] indexing {len(target_game_ids)} games from PGN...", file=sys.stderr)

    game_index = index_target_games(raw_pgn, target_game_ids, progress=True)
    n_found = len(game_index)
    n_missing = len(target_game_ids) - n_found
    print(
        f"  [eval] found {n_found}/{len(target_game_ids)} games "
        f"({n_missing} missing from PGN)",
        file=sys.stderr,
    )

    engine_name = engine_version.split()[0] if engine_version != "unknown" else "Stockfish"
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows: list[dict] = []
    n_ok = 0
    n_fail = 0

    # Open engine only when actually evaluating positions
    engine = (
        None if dry_run
        else chess.engine.SimpleEngine.popen_uci(stockfish_path)
    )

    try:
        for i, pos_row in enumerate(df.iter_rows(named=True)):
            game_id = pos_row["game_id"]
            target_ply = int(pos_row["ply"])
            sel_type = pos_row["selected_position_type"]
            move_number = pos_row.get("move_number")
            result_class = pos_row.get("result_class")
            split_set = pos_row.get("split_set", "unknown")
            has_lichess_eval = bool(pos_row.get("has_eval", False))
            lichess_eval_cp = pos_row.get("eval_cp")
            lichess_eval_mate = pos_row.get("eval_mate")

            row: dict = {
                "dataset_id": dataset_id,
                "version_tag": version_tag,
                "game_id": game_id,
                "ply": target_ply,
                "selected_position_type": sel_type,
                "split_set": split_set,
                "move_number": move_number,
                "result_class": result_class,
                "has_lichess_eval": has_lichess_eval,
                "lichess_eval_cp": lichess_eval_cp,
                "lichess_eval_mate": lichess_eval_mate,
                "fen_hash": None,
                "sf_eval_available": False,
                "sf_eval_status": _EVAL_STATUS_SKIPPED,
                "sf_eval_cp": None,
                "sf_eval_mate": None,
                "sf_eval_mate_abs": None,
                "sf_eval_abs": None,
                "sf_eval_sign": None,
                "sf_eval_bucket": None,
                "sf_depth": depth,
                "sf_nodes": None,
                "sf_time_ms": None,
                "sf_engine_name": engine_name,
                "sf_engine_version": engine_version,
                "sf_eval_timestamp_utc": timestamp_utc,
                "sf_error": None,
            }

            if game_id not in game_index:
                row["sf_eval_status"] = _EVAL_STATUS_FEN_ERR
                row["sf_error"] = "game_id not found in PGN stream"
                rows.append(row)
                n_fail += 1
                continue

            game = game_index[game_id]
            fen, fen_status = reconstruct_fen_at_ply(game, target_ply)

            if fen is None:
                row["sf_eval_status"] = fen_status
                row["sf_error"] = f"FEN reconstruction failed at ply {target_ply}"
                rows.append(row)
                n_fail += 1
                continue

            row["fen_hash"] = hashlib.sha256(fen.encode()).hexdigest()[:16]

            if not dry_run and engine is not None:
                eval_result = analyse_fen(engine, fen, depth)
            else:
                # In dry-run mode, don't actually call the engine
                eval_result = {
                    "sf_eval_available": False,
                    "sf_eval_status": "dry_run",
                    "sf_eval_cp": None,
                    "sf_eval_mate": None,
                    "sf_eval_mate_abs": None,
                    "sf_eval_abs": None,
                    "sf_eval_sign": None,
                    "sf_eval_bucket": None,
                    "sf_depth": depth,
                    "sf_nodes": None,
                    "sf_time_ms": 0,
                    "sf_error": None,
                }

            row.update(eval_result)
            rows.append(row)

            if eval_result["sf_eval_available"]:
                n_ok += 1
            else:
                n_fail += 1

            if (i + 1) % 100 == 0 or (i + 1) == len(df):
                print(
                    f"  [eval] {i + 1}/{len(df)} positions "
                    f"(ok={n_ok}, fail={n_fail})",
                    file=sys.stderr,
                )

    finally:
        if engine is not None:
            engine.quit()

    result_df = pl.DataFrame(rows)
    # Ensure all expected columns are present
    for col in _OUTPUT_COLUMNS:
        if col not in result_df.columns:
            result_df = result_df.with_columns(pl.lit(None).alias(col))
    result_df = result_df.select(_OUTPUT_COLUMNS)

    return result_df


# ---------------------------------------------------------------------------
# K. Write outputs
# ---------------------------------------------------------------------------

def write_outputs(
    results_df: pl.DataFrame,
    metadata: dict,
    output_parquet: Path,
    output_metadata: Path,
    output_report: Path,
    report_text: str,
    overwrite: bool = False,
) -> None:
    """Write Parquet artifact, metadata JSON, and Markdown report."""
    for path in [output_parquet, output_metadata, output_report]:
        if path.exists() and not overwrite:
            raise FileExistsError(
                f"Output exists: {path}\nUse --overwrite to replace it."
            )
        path.parent.mkdir(parents=True, exist_ok=True)

    results_df.write_parquet(output_parquet, compression="snappy")
    print(f"  [write] Parquet: {output_parquet} ({len(results_df)} rows)", file=sys.stderr)

    with open(output_metadata, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  [write] metadata: {output_metadata}", file=sys.stderr)

    with open(output_report, "w") as f:
        f.write(report_text)
    print(f"  [write] report: {output_report}", file=sys.stderr)


# ---------------------------------------------------------------------------
# L. Render Stockfish eval report (committed Markdown summary)
# ---------------------------------------------------------------------------

def render_stockfish_eval_report(
    results_df: pl.DataFrame,
    metadata: dict,
    dry_run: bool = False,
) -> str:
    """
    Render the committed Markdown summary report.

    Timestamp is kept in the metadata JSON only; the Markdown body is
    deterministic so repeated runs with the same results produce the same file.
    """
    dataset_id = metadata.get("dataset_id", "unknown")
    version_tag = metadata.get("version_tag", "unknown")
    depth = metadata.get("depth", "unknown")
    sf_version = metadata.get("stockfish_version", "unknown")
    n_req = metadata.get("n_requested", 0)
    n_eval = metadata.get("n_evaluated", 0)
    n_fail = metadata.get("n_failed", 0)
    status_counts = metadata.get("status_counts", {})
    runtime_s = metadata.get("runtime_s", None)
    dry_run_flag = metadata.get("dry_run", dry_run)

    lines = []
    lines.append("# Stockfish Evaluation — Fixed-Depth Pilot Assessment")
    lines.append("")
    lines.append(f"**Ticket:** 8.1B — Fixed-Depth Stockfish Evaluation Implementation")
    lines.append(f"**Dataset:** `{dataset_id}`")
    lines.append(f"**Version tag:** `{version_tag}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. ELI5 / TLDR
    lines.append("## 1. ELI5 / TLDR")
    lines.append("")
    if dry_run_flag:
        lines.append(
            "This report covers a **dry-run only** (FEN reconstruction test, no engine analysis). "
            "Full Stockfish evaluation is pending explicit approval. "
            "The implementation is code-complete and ready to run."
        )
    else:
        lines.append(
            f"This artifact provides local fixed-depth Stockfish evaluations "
            f"({n_eval:,} positions at depth={depth}) for the `{dataset_id}` "
            "pilot checkpoint positions. It replaces the sparse, selection-biased "
            "Lichess cloud evals (13.7% coverage) with full-coverage objective "
            "position context for Phase 8.2 eval-conditioned modeling. "
            "This module does NOT train models."
        )
    lines.append("")

    # 2. Scope
    lines.append("## 2. Scope")
    lines.append("")
    lines.append(f"- Input: `ten_zero_positions_broad_{version_tag}.parquet`")
    lines.append("- Positions: primary_numbered checkpoints (excludes `selected_position_type == 'last'`)")
    lines.append(f"- Requested: {n_req:,} positions")
    lines.append(f"- Evaluated: {n_eval:,} positions")
    lines.append(f"- Failed/skipped: {n_fail:,} positions")
    lines.append("")

    # 3. Engine and depth
    lines.append("## 3. Engine and Depth")
    lines.append("")
    lines.append(f"- Engine: {sf_version}")
    lines.append(f"- Depth: {depth} (fixed)")
    lines.append("- `chess.engine.SimpleEngine` via python-chess 1.11.2")
    lines.append("- No time limit; deterministic at fixed depth")
    lines.append("")

    # 4. Output artifact
    lines.append("## 4. Output Artifact")
    lines.append("")
    lines.append(f"- `data/processed/sf_eval_broad_{version_tag}.parquet` (gitignored)")
    lines.append(f"- `data/processed/sf_eval_metadata_{version_tag}.json` (gitignored)")
    lines.append("- This report (committed)")
    lines.append("")

    # 5. Coverage
    lines.append("## 5. Coverage")
    lines.append("")
    if len(results_df) > 0 and "sf_eval_available" in results_df.columns:
        n_available = results_df["sf_eval_available"].sum()
        pct = round(100 * n_available / max(len(results_df), 1), 2)
        lines.append(f"- Positions with sf_eval_available=True: {n_available:,} ({pct}%)")
        if "has_lichess_eval" in results_df.columns:
            n_lichess = results_df["has_lichess_eval"].sum()
            lines.append(f"- Positions with existing Lichess eval: {n_lichess:,}")
            lines.append(f"- Lichess eval coverage was: 13.7% (sparse, selection-biased)")
    else:
        lines.append("- (dry-run: FEN reconstruction verified, no engine results yet)")
    lines.append("")

    # 6. Status counts
    lines.append("## 6. Status Counts")
    lines.append("")
    if status_counts:
        lines.append("| Status | Count |")
        lines.append("|---|---|")
        for status, count in sorted(status_counts.items()):
            lines.append(f"| {status} | {count:,} |")
    else:
        lines.append("(no status counts — dry-run)")
    lines.append("")

    # 7. Eval distribution
    lines.append("## 7. Eval Distribution")
    lines.append("")
    if (
        len(results_df) > 0
        and "sf_eval_bucket" in results_df.columns
        and results_df["sf_eval_bucket"].drop_nulls().len() > 0
    ):
        bucket_counts = (
            results_df.filter(pl.col("sf_eval_available"))
            .group_by("sf_eval_bucket")
            .agg(pl.len().alias("n"))
            .sort("n", descending=True)
        )
        lines.append("| Bucket | N |")
        lines.append("|---|---|")
        for r in bucket_counts.iter_rows(named=True):
            lines.append(f"| {r['sf_eval_bucket']} | {r['n']:,} |")
        # Cp stats
        eval_df = results_df.filter(pl.col("sf_eval_available"))
        if len(eval_df) > 0:
            cp_vals = eval_df["sf_eval_cp"].drop_nulls()
            if len(cp_vals) > 0:
                lines.append("")
                lines.append(
                    f"sf_eval_cp: mean={round(cp_vals.mean(), 1)}, "
                    f"std={round(cp_vals.std(), 1)}, "
                    f"min={cp_vals.min()}, max={cp_vals.max()}"
                )
    else:
        lines.append("(dry-run: no eval distribution available)")
    lines.append("")

    # 8. Lichess eval overlap preview
    lines.append("## 8. Lichess Eval Overlap Preview")
    lines.append("")
    if (
        len(results_df) > 0
        and "has_lichess_eval" in results_df.columns
        and "sf_eval_available" in results_df.columns
        and not dry_run_flag
    ):
        overlap_df = results_df.filter(
            pl.col("has_lichess_eval") & pl.col("sf_eval_available")
        )
        n_overlap = len(overlap_df)
        lines.append(f"- Positions with both Lichess eval and SF eval: {n_overlap:,}")
        if n_overlap > 0 and "lichess_eval_cp" in overlap_df.columns:
            # Sign agreement (exclude mate sentinels)
            non_mate = overlap_df.filter(
                (pl.col("lichess_eval_cp").is_not_null())
                & (pl.col("sf_eval_cp").is_not_null())
                & (pl.col("lichess_eval_cp").abs() < MATE_CP_SENTINEL)
                & (pl.col("sf_eval_cp").abs() < MATE_CP_SENTINEL)
            )
            if len(non_mate) > 0:
                sign_agree = non_mate.filter(
                    (pl.col("lichess_eval_cp").sign() == pl.col("sf_eval_cp").sign())
                    | ((pl.col("lichess_eval_cp") == 0) & (pl.col("sf_eval_cp") == 0))
                )
                agree_pct = round(100 * len(sign_agree) / len(non_mate), 1)
                lines.append(
                    f"- Sign agreement (non-mate, lichess vs SF): "
                    f"{len(sign_agree):,}/{len(non_mate):,} = {agree_pct}%"
                )
                mae = round(
                    float((non_mate["lichess_eval_cp"] - non_mate["sf_eval_cp"]).abs().mean()),
                    1,
                )
                lines.append(f"- Mean absolute difference (cp): {mae}")
        lines.append(
            "- Note: exact equality not expected — Lichess evals are variable-depth "
            "and from a different Stockfish version."
        )
    else:
        lines.append("(dry-run or not yet run — overlap preview not available)")
    lines.append("")

    # 9. Runtime / storage
    lines.append("## 9. Runtime / Storage")
    lines.append("")
    if runtime_s is not None:
        lines.append(f"- Total runtime: {runtime_s:.0f}s ({runtime_s / 60:.1f}min)")
    else:
        lines.append("- Runtime: N/A (dry-run)")
    lines.append(f"- Storage estimate: {n_eval * 50 / 1e6:.2f} MB (Parquet)")
    lines.append("")

    # 10. Caveats
    lines.append("## 10. Caveats")
    lines.append("")
    lines.append(
        "- **Local Stockfish eval is objective-position context, not perfect truth.** "
        f"Stockfish depth={depth} provides a strong but approximate evaluation. "
        "Different depths or versions may produce different centipawn values."
    )
    lines.append(
        "- **Fixed-depth Stockfish is not causal.** "
        "Eval at a checkpoint reflects position strength, not what causes outcomes. "
        "A high sf_eval_cp does not mean the stronger position caused the win — "
        "player decisions after that checkpoint also matter."
    )
    lines.append(
        "- **Eval does not make clock or rating effects causal.** "
        "Clock pressure, rating, and position strength are correlated features, "
        "not a causal chain."
    )
    lines.append(
        "- **Existing Lichess eval coverage was sparse and selection-biased.** "
        "Only 13.7% of broad rows had Lichess evals; those games had ~20 Elo higher avg_elo. "
        "This artifact removes that bias."
    )
    lines.append(
        "- **This artifact prepares Phase 8.2 modeling but does not itself retrain models.** "
        "Models using sf_eval_* features will be implemented in Ticket 8.2B."
    )
    lines.append(
        "- **Test split is not used for model selection.** "
        "Following WORKFLOW.md §13 holdout policy."
    )
    lines.append(
        "- **Data artifact is gitignored and must not be committed.** "
        "Only this report and the phase report are committed."
    )
    lines.append("")

    # 11. Reproducibility
    lines.append("## 11. Reproducibility")
    lines.append("")
    lines.append(
        "Re-run with the same `--depth`, `--stockfish-path`, and `--positions` "
        "to regenerate the artifact. The Markdown report body is deterministic "
        "(timestamps kept in JSON metadata only)."
    )
    lines.append("")
    lines.append("```bash")
    lines.append("PYTHONPATH=src python -m chess_mhsuc.stockfish_eval \\")
    lines.append(f"    --dataset-id {dataset_id} \\")
    lines.append(f"    --version-tag {version_tag} \\")
    lines.append(
        "    --positions data/processed/ten_zero_positions_broad_"
        + version_tag
        + ".parquet \\"
    )
    lines.append("    --raw-pgn <RAW_PGN_PATH_OR_URL> \\")
    lines.append("    --depth 12 \\")
    lines.append(
        "    --output-parquet data/processed/sf_eval_broad_"
        + version_tag
        + ".parquet \\"
    )
    lines.append(
        "    --output-metadata data/processed/sf_eval_metadata_"
        + version_tag
        + ".json \\"
    )
    lines.append(
        "    --output-report reports/stockfish_eval_"
        + version_tag
        + ".md \\"
    )
    lines.append("    --overwrite")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build metadata dict
# ---------------------------------------------------------------------------

def build_metadata(
    dataset_id: str,
    version_tag: str,
    positions_path: str,
    raw_pgn: str,
    output_parquet: str,
    depth: int,
    stockfish_path: str,
    stockfish_version: str,
    run_started_utc: str,
    run_finished_utc: str,
    n_requested: int,
    n_evaluated: int,
    n_failed: int,
    status_counts: dict,
    include_last: bool,
    limit: int | None,
    dry_run: bool,
    command: list[str],
    runtime_s: float,
    git_commit: str | None = None,
) -> dict:
    """Build the metadata JSON dict."""
    import chess
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "source_positions_path": str(positions_path),
        "raw_pgn_path": str(raw_pgn),
        "output_parquet_path": str(output_parquet),
        "depth": depth,
        "stockfish_path_used": str(stockfish_path),
        "stockfish_version": stockfish_version,
        "python_chess_version": chess.__version__,
        "run_started_utc": run_started_utc,
        "run_finished_utc": run_finished_utc,
        "runtime_s": round(runtime_s, 2),
        "n_requested": n_requested,
        "n_evaluated": n_evaluated,
        "n_failed": n_failed,
        "status_counts": status_counts,
        "include_last": include_last,
        "limit": limit,
        "dry_run": dry_run,
        "command": command,
        "git_commit": git_commit,
    }


# ---------------------------------------------------------------------------
# Git commit helper
# ---------------------------------------------------------------------------

def _get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() or None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# M. CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chess_mhsuc.stockfish_eval",
        description="Fixed-depth Stockfish evaluation for pilot checkpoint positions.",
    )
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--version-tag", default=DEFAULT_VERSION_TAG)
    parser.add_argument(
        "--positions",
        required=True,
        help="Path to ten_zero_positions_broad_*.parquet",
    )
    parser.add_argument(
        "--splits",
        default=None,
        help="Optional path to splits_*.json to attach split_set column",
    )
    parser.add_argument(
        "--raw-pgn",
        required=True,
        help="Path to raw PGN archive (.pgn, .pgn.zst) or HTTPS URL",
    )
    parser.add_argument("--stockfish-path", default=None, help="Explicit Stockfish binary path")
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument(
        "--output-parquet",
        required=True,
        help="Output Parquet path, e.g. data/processed/sf_eval_broad_*.parquet",
    )
    parser.add_argument(
        "--output-metadata",
        required=True,
        help="Output metadata JSON path",
    )
    parser.add_argument(
        "--output-report",
        required=True,
        help="Output Markdown report path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of positions to evaluate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test FEN reconstruction without running engine analysis",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip (game_id, ply) pairs already in the output Parquet",
    )
    parser.add_argument(
        "--include-last",
        action="store_true",
        help="Include selected_position_type=='last' positions",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )
    args = parser.parse_args(argv)

    run_started_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t_start = time.time()
    command = sys.argv[:]

    # Safety checks
    positions_path = Path(args.positions)
    if not positions_path.exists():
        print(f"ERROR: positions file not found: {positions_path}", file=sys.stderr)
        return 1

    splits_path = Path(args.splits) if args.splits else None

    # Resolve Stockfish
    try:
        sf_path = resolve_stockfish_path(args.stockfish_path)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    sf_version = get_stockfish_version(sf_path)
    print(f"  [init] Stockfish: {sf_version} ({sf_path})", file=sys.stderr)
    print(f"  [init] depth={args.depth}", file=sys.stderr)

    # Load positions
    positions_df = load_primary_numbered_positions(
        positions_path,
        splits_path=splits_path,
        include_last=args.include_last,
    )
    n_positions = len(positions_df)
    print(f"  [init] loaded {n_positions:,} positions from {positions_path}", file=sys.stderr)

    resume_parquet = Path(args.output_parquet) if args.resume else None

    # Run evaluation
    results_df = run_stockfish_eval(
        positions_df=positions_df,
        raw_pgn=args.raw_pgn,
        stockfish_path=sf_path,
        depth=args.depth,
        limit=args.limit,
        dry_run=args.dry_run,
        resume_parquet=resume_parquet,
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        engine_version=sf_version,
    )

    run_finished_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runtime_s = time.time() - t_start

    # Compute summary stats
    n_evaluated = int(results_df["sf_eval_available"].sum()) if "sf_eval_available" in results_df.columns else 0
    n_failed = len(results_df) - n_evaluated
    status_counts: dict[str, int] = {}
    if "sf_eval_status" in results_df.columns:
        for row in results_df.group_by("sf_eval_status").agg(pl.len().alias("n")).iter_rows(named=True):
            status_counts[row["sf_eval_status"]] = row["n"]

    metadata = build_metadata(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        positions_path=args.positions,
        raw_pgn=args.raw_pgn,
        output_parquet=args.output_parquet,
        depth=args.depth,
        stockfish_path=sf_path,
        stockfish_version=sf_version,
        run_started_utc=run_started_utc,
        run_finished_utc=run_finished_utc,
        n_requested=len(results_df),
        n_evaluated=n_evaluated,
        n_failed=n_failed,
        status_counts=status_counts,
        include_last=args.include_last,
        limit=args.limit,
        dry_run=args.dry_run,
        command=command,
        runtime_s=runtime_s,
        git_commit=_get_git_commit(),
    )

    report_text = render_stockfish_eval_report(results_df, metadata, dry_run=args.dry_run)

    out_parquet = Path(args.output_parquet)
    out_metadata = Path(args.output_metadata)
    out_report = Path(args.output_report)

    write_outputs(
        results_df=results_df,
        metadata=metadata,
        output_parquet=out_parquet,
        output_metadata=out_metadata,
        output_report=out_report,
        report_text=report_text,
        overwrite=args.overwrite,
    )

    print(
        f"\n  [done] {len(results_df)} rows | "
        f"ok={n_evaluated} | fail={n_failed} | "
        f"runtime={runtime_s:.1f}s",
        file=sys.stderr,
    )

    if args.dry_run:
        print("  [dry-run] FEN reconstruction complete. Approve full run to evaluate with engine.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
