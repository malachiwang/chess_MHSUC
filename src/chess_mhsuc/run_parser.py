"""
run_parser.py — capped streaming parser for Lichess monthly PGN archives.

Streams a .pgn.zst file from a URL without full decompression to disk.
Parses only 600+0 games up to a configurable raw-games cap.
Writes two local-only Parquet tables plus a metadata JSON sidecar.

This module is for validation/interim use only.  It does NOT produce a
final cleaned or model-ready dataset.  That is Phase 3 work.

Usage:
    python -m chess_mhsuc.run_parser \\
        --url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst \\
        --max-games 25000 \\
        --max-accepted 2500 \\
        --source-file lichess_db_standard_rated_2024-09.pgn.zst \\
        --output-dir data/interim \\
        --version-tag v1

Output files (under --output-dir, never committed):
    game_records_{month}_{cap}_{tag}.parquet      — all 600+0 games
    position_records_{month}_{cap}_{tag}.parquet  — checkpoints from accepted games
    parser_validation_{month}_{cap}_{tag}_metadata.json

See schemas.py for field definitions and eval/clock conventions.
See DATA_POLICY.md for data safety rules.
"""

import argparse
import dataclasses
import io
import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import chess.pgn
import polars as pl
import zstandard

from chess_mhsuc.parse_pgn import (
    extract_game_record,
    extract_ply_records,
    parse_source_month,
    select_checkpoints,
)
from chess_mhsuc.schemas import GameRecord, PositionRecord

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TARGET_TC = "600+0"
CONNECT_TIMEOUT_S = 60
READ_CHUNK_SIZE = 1 << 16   # 64 KiB  — mirrors source_scan.py
BUFFER_SIZE = 1 << 17       # 128 KiB

# Progress print interval (raw games scanned)
_PROGRESS_INTERVAL = 5_000

# ---------------------------------------------------------------------------
# Parquet schemas
# ---------------------------------------------------------------------------
# Explicit schemas prevent polars from inferring Null dtype when all values
# in a column happen to be None (which would break downstream reads).

GAME_RECORD_SCHEMA: dict[str, pl.DataType] = {
    "game_id":              pl.String,
    "source_file":          pl.String,
    "source_month":         pl.String,
    "utc_date":             pl.String,
    "utc_time":             pl.String,
    "time_control":         pl.String,
    "result_raw":           pl.String,
    "result_class":         pl.String,
    "white_result_numeric": pl.Float64,
    "termination":          pl.String,
    "white_elo":            pl.Int64,
    "black_elo":            pl.Int64,
    "elo_diff":             pl.Int64,
    "white_rating_diff":    pl.Int64,
    "black_rating_diff":    pl.Int64,
    "event":                pl.String,
    "n_plies":              pl.Int64,
    "has_clock":            pl.Boolean,
    "has_eval":             pl.Boolean,
    "accepted_basic":       pl.Boolean,
    "accepted_eval":        pl.Boolean,
    "rejection_reason":     pl.String,
}

POSITION_RECORD_SCHEMA: dict[str, pl.DataType] = {
    "game_id":                pl.String,
    "ply":                    pl.Int64,
    "move_number":            pl.Int64,
    "side_to_move_next":      pl.String,
    "selected_position_type": pl.String,
    "white_clock_s":          pl.Int64,
    "black_clock_s":          pl.Int64,
    "clock_diff_s":           pl.Int64,
    "eval_cp":                pl.Int64,
    "eval_mate":              pl.Int64,
    "has_eval":               pl.Boolean,
    "phase":                  pl.String,
    "result_class":           pl.String,
    "white_result_numeric":   pl.Float64,
    "white_elo":              pl.Int64,
    "black_elo":              pl.Int64,
    "elo_diff":               pl.Int64,
    "termination":            pl.String,
    "n_plies_total":          pl.Int64,
}


# ---------------------------------------------------------------------------
# Core parse loop
# ---------------------------------------------------------------------------

def stream_and_parse(
    text_stream: io.TextIOWrapper,
    source_file: str | None,
    max_games: int,
    max_accepted: int | None = None,
    url: str = "",
) -> dict:
    """
    Parse games from an open text stream up to max_games raw games.

    Only 600+0 games are fully parsed.  Non-600+0 games are skipped after a
    header-only check (no board replay, no ply extraction).

    Per-game exceptions are caught, logged, and skipped — they do not abort
    the run.

    Parameters
    ----------
    text_stream
        Open, readable text stream of PGN data.
    source_file
        Archive filename string for metadata (e.g. "lichess_...pgn.zst").
        Not a path that is read — only stored in GameRecord.source_file.
    max_games
        Hard cap on raw games read.  Required — no unbounded default.
    max_accepted
        Optional secondary cap: stop when this many accepted_basic games
        have been collected (whichever cap is hit first).
    url
        URL string for metadata only.

    Returns
    -------
    dict with keys:
        game_records      : list[GameRecord]   all 600+0 games parsed
        position_records  : list[PositionRecord]  checkpoints for accepted games
        n_raw_scanned     : int
        n_600_0_total     : int
        n_parse_errors    : int
        error_log         : list[dict]  {game_site, error} per failed game
        elapsed_s         : float
        url               : str
    """
    game_records: list[GameRecord] = []
    position_records: list[PositionRecord] = []
    n_raw = 0
    n_600_0 = 0
    n_accepted_basic = 0
    n_parse_errors = 0
    error_log: list[dict] = []

    t0 = time.monotonic()

    while n_raw < max_games:
        try:
            game = chess.pgn.read_game(text_stream)
        except Exception as e:
            # Stream-level parse failure (very rare); log and try to continue.
            n_parse_errors += 1
            error_log.append({"game_site": "stream_error", "error": str(e)})
            continue

        if game is None:
            break  # EOF

        n_raw += 1

        # --- Fast pre-filter: skip non-600+0 without ply extraction ---
        tc = game.headers.get("TimeControl", "")
        if tc != TARGET_TC:
            continue

        n_600_0 += 1

        # --- Full parse for 600+0 games ---
        game_site = game.headers.get("Site", "unknown")
        try:
            game_record = extract_game_record(game, source_file=source_file)
            game_records.append(game_record)

            if game_record.accepted_basic:
                ply_records = extract_ply_records(
                    game, game_id=game_record.game_id
                )
                pos_records = select_checkpoints(ply_records, game_record)
                position_records.extend(pos_records)
                n_accepted_basic += 1

        except Exception as e:
            n_parse_errors += 1
            error_log.append({"game_site": game_site, "error": str(e)})
            continue

        # --- Secondary accepted_basic cap ---
        if max_accepted is not None and n_accepted_basic >= max_accepted:
            break

    elapsed = time.monotonic() - t0

    return {
        "game_records": game_records,
        "position_records": position_records,
        "n_raw_scanned": n_raw,
        "n_600_0_total": n_600_0,
        "n_parse_errors": n_parse_errors,
        "error_log": error_log,
        "elapsed_s": elapsed,
        "url": url,
    }


# ---------------------------------------------------------------------------
# DataFrame construction
# ---------------------------------------------------------------------------

def _records_to_df(records: list, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    """Convert a list of dataclass instances to a polars DataFrame."""
    if not records:
        return pl.DataFrame(schema=schema)
    dicts = [dataclasses.asdict(r) for r in records]
    return pl.from_dicts(dicts, schema=schema)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def build_metadata(
    result: dict,
    source_url: str,
    source_file: str | None,
    raw_games_cap: int,
    max_accepted_basic: int | None,
    output_paths: dict[str, str],
    version_tag: str,
) -> dict:
    """Build the metadata sidecar dict from a parse result."""
    game_records: list[GameRecord] = result["game_records"]
    position_records: list[PositionRecord] = result["position_records"]

    n_accepted_basic = sum(1 for gr in game_records if gr.accepted_basic)
    n_accepted_eval = sum(1 for gr in game_records if gr.accepted_eval)

    rejection_counts: Counter = Counter()
    result_dist: Counter = Counter()
    termination_dist: Counter = Counter()
    for gr in game_records:
        if gr.rejection_reason:
            rejection_counts[gr.rejection_reason] += 1
        if gr.result_class:
            result_dist[gr.result_class] += 1
        if gr.termination:
            termination_dist[gr.termination] += 1

    checkpoint_dist: Counter = Counter()
    phase_dist: Counter = Counter()
    for pr in position_records:
        checkpoint_dist[pr.selected_position_type] += 1
        phase_dist[pr.phase] += 1

    return {
        "source_url": source_url,
        "source_file": source_file,
        "source_month": parse_source_month(source_file),
        "raw_games_cap": raw_games_cap,
        "max_accepted_basic": max_accepted_basic,
        "raw_games_scanned": result["n_raw_scanned"],
        "n_600_0_total": result["n_600_0_total"],
        "n_game_records": len(game_records),
        "n_accepted_basic": n_accepted_basic,
        "n_accepted_eval": n_accepted_eval,
        "n_position_records": len(position_records),
        "n_parse_errors": result["n_parse_errors"],
        "rejection_reason_counts": dict(rejection_counts),
        "result_distribution": dict(result_dist),
        "termination_distribution": dict(termination_dist),
        "checkpoint_type_distribution": dict(checkpoint_dist),
        "phase_distribution": dict(phase_dist),
        "elapsed_s": round(result["elapsed_s"], 2),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version_tag": version_tag,
        "output_paths": output_paths,
    }


# ---------------------------------------------------------------------------
# Output writing
# ---------------------------------------------------------------------------

def write_outputs(
    result: dict,
    game_records_path: Path,
    position_records_path: Path,
    metadata_path: Path,
    source_url: str,
    source_file: str | None,
    raw_games_cap: int,
    max_accepted_basic: int | None,
    version_tag: str,
) -> dict:
    """
    Write Parquet tables and metadata JSON.

    Returns the metadata dict (also written to metadata_path).
    """
    # Ensure parent directory exists
    game_records_path.parent.mkdir(parents=True, exist_ok=True)

    # Game records Parquet (all 600+0 games, accepted + rejected)
    df_games = _records_to_df(result["game_records"], GAME_RECORD_SCHEMA)
    df_games.write_parquet(str(game_records_path))

    # Position records Parquet (checkpoints from accepted_basic games only)
    df_positions = _records_to_df(result["position_records"], POSITION_RECORD_SCHEMA)
    df_positions.write_parquet(str(position_records_path))

    # Metadata JSON
    output_paths = {
        "game_records": str(game_records_path),
        "position_records": str(position_records_path),
        "metadata": str(metadata_path),
    }
    metadata = build_metadata(
        result, source_url, source_file, raw_games_cap, max_accepted_basic,
        output_paths, version_tag,
    )
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    return metadata


# ---------------------------------------------------------------------------
# Validation checks
# ---------------------------------------------------------------------------

def validation_checks(
    df_games: pl.DataFrame,
    df_positions: pl.DataFrame,
) -> dict[str, bool]:
    """
    Run post-parse data integrity checks.

    Returns a dict mapping check name to bool (True = passed).
    """
    results: dict[str, bool] = {}

    # Username columns absent
    bad_cols = {"white", "black", "White", "Black", "white_name", "black_name"}
    results["no_username_cols_games"] = not bool(bad_cols & set(df_games.columns))
    results["no_username_cols_positions"] = not bool(bad_cols & set(df_positions.columns))

    if df_games.height > 0:
        # game_id uniqueness (among non-null game_ids)
        gids = df_games["game_id"].drop_nulls()
        results["game_id_unique"] = gids.n_unique() == gids.len()

        # result_class values in expected set (ignoring nulls)
        valid_result_classes = {"WHITE_WIN", "DRAW", "BLACK_WIN"}
        rc_vals = set(df_games["result_class"].drop_nulls().unique().to_list())
        results["result_class_values_valid"] = rc_vals.issubset(valid_result_classes)

        # rejection_reason values in known set (ignoring nulls)
        known_reasons = {
            "wrong_time_control", "variant_or_nonstandard",
            "missing_or_invalid_elo", "missing_or_invalid_result",
            "missing_clock",
        }
        rr_vals = set(df_games["rejection_reason"].drop_nulls().unique().to_list())
        results["rejection_reason_values_valid"] = rr_vals.issubset(known_reasons)

        # n_plies > 0 for accepted_basic games only.
        # Rejected abandoned games can have n_plies = 0, which is valid.
        acc = df_games.filter(pl.col("accepted_basic"))
        if acc.height > 0:
            results["accepted_basic_n_plies_positive"] = acc["n_plies"].min() > 0
        else:
            results["accepted_basic_n_plies_positive"] = True
    else:
        results["game_id_unique"] = True
        results["result_class_values_valid"] = True
        results["rejection_reason_values_valid"] = True
        results["accepted_basic_n_plies_positive"] = True

    if df_positions.height > 0:
        # Clock values non-negative
        wclk = df_positions["white_clock_s"].drop_nulls()
        bclk = df_positions["black_clock_s"].drop_nulls()
        clk_ok = True
        if wclk.len() > 0:
            clk_ok = clk_ok and (wclk.min() >= 0)
        if bclk.len() > 0:
            clk_ok = clk_ok and (bclk.min() >= 0)
        results["clock_values_non_negative"] = clk_ok

        # Eval_cp bounds: must be in [-10000, 10000] when not null
        ecp = df_positions["eval_cp"].drop_nulls()
        if ecp.len() > 0:
            results["eval_cp_in_bounds"] = (
                ecp.min() >= -10_000 and ecp.max() <= 10_000
            )
        else:
            results["eval_cp_in_bounds"] = True

        # Eval sentinel consistency: eval_cp == ±10000 iff eval_mate is not null
        sentinel = 10_000
        is_sentinel = (df_positions["eval_cp"] == sentinel) | (
            df_positions["eval_cp"] == -sentinel
        )
        has_mate = df_positions["eval_mate"].is_not_null()
        # Rows with sentinel should have eval_mate set
        sentinel_without_mate = (is_sentinel & ~has_mate).sum()
        # Rows with eval_mate should have sentinel eval_cp
        mate_without_sentinel = (has_mate & ~is_sentinel).sum()
        results["eval_sentinel_consistent"] = (
            sentinel_without_mate == 0 and mate_without_sentinel == 0
        )

        # Phase values in expected set
        valid_phases = {"opening", "middlegame", "endgame"}
        phase_vals = set(df_positions["phase"].unique().to_list())
        results["phase_values_valid"] = phase_vals.issubset(valid_phases)

        # selected_position_type values in expected set
        valid_cptypes = {"move_10", "move_20", "move_30", "move_40", "last"}
        cpt_vals = set(df_positions["selected_position_type"].unique().to_list())
        results["checkpoint_type_values_valid"] = cpt_vals.issubset(valid_cptypes)
    else:
        results["clock_values_non_negative"] = True
        results["eval_cp_in_bounds"] = True
        results["eval_sentinel_consistent"] = True
        results["phase_values_valid"] = True
        results["checkpoint_type_values_valid"] = True

    return results


# ---------------------------------------------------------------------------
# Validation summary printer
# ---------------------------------------------------------------------------

def print_validation_summary(
    metadata: dict,
    checks: dict[str, bool],
    df_games: pl.DataFrame,
    df_positions: pl.DataFrame,
) -> None:
    """Print a human-readable validation summary to stdout."""

    def _pct(n: int, d: int) -> str:
        return f"{100 * n / d:.1f}%" if d > 0 else "n/a"

    def _dist_lines(dist: dict, total: int) -> list[str]:
        lines = []
        for k, v in sorted(dist.items(), key=lambda x: -x[1]):
            lines.append(f"  {k:<22} {v:>7,}  ({_pct(v, total)})")
        return lines

    print()
    print("=" * 60)
    print("  Parser Validation Summary")
    print("=" * 60)

    n_raw = metadata["raw_games_scanned"]
    n_600 = metadata["n_600_0_total"]
    n_acc = metadata["n_accepted_basic"]
    n_eval = metadata["n_accepted_eval"]
    n_pos = metadata["n_position_records"]
    n_err = metadata["n_parse_errors"]
    elapsed = metadata["elapsed_s"]
    rate = round(n_raw / elapsed, 1) if elapsed > 0 else 0

    print(f"  Raw games scanned:        {n_raw:>8,}")
    print(f"  600+0 total:              {n_600:>8,}  ({_pct(n_600, n_raw)} of raw)")
    print(f"  Accepted basic:           {n_acc:>8,}  ({_pct(n_acc, n_600)} of 600+0)")
    print(f"  Accepted eval:            {n_eval:>8,}  ({_pct(n_eval, n_acc)} of basic)")
    print(f"  Position records:         {n_pos:>8,}")
    print(f"  Parse errors:             {n_err:>8,}")
    print(f"  Elapsed:                  {elapsed:>7.1f}s  ({rate} raw games/s)")

    avg_cp = n_pos / n_acc if n_acc > 0 else 0
    print(f"  Avg checkpoints/game:     {avg_cp:>8.2f}")

    if metadata["rejection_reason_counts"]:
        print()
        print("  Rejection reasons:")
        for k, v in sorted(metadata["rejection_reason_counts"].items()):
            print(f"    {k:<32} {v:>6,}")

    if metadata["result_distribution"]:
        print()
        print("  Result distribution (accepted basic):")
        for line in _dist_lines(metadata["result_distribution"], n_acc):
            print(line)

    if metadata["termination_distribution"]:
        print()
        print("  Termination distribution (accepted basic):")
        for line in _dist_lines(metadata["termination_distribution"], n_acc):
            print(line)

    if metadata["checkpoint_type_distribution"]:
        print()
        print("  Checkpoint type distribution:")
        for k, v in sorted(metadata["checkpoint_type_distribution"].items()):
            print(f"  {k:<22} {v:>7,}")

    if metadata["phase_distribution"]:
        print()
        print("  Phase distribution (position records):")
        for line in _dist_lines(metadata["phase_distribution"], n_pos):
            print(line)

    print()
    print("  Data integrity checks:")
    all_pass = True
    for check_name, passed in sorted(checks.items()):
        status = "PASS" if passed else "FAIL"
        print(f"    {check_name:<38} {status}")
        if not passed:
            all_pass = False
    print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES — see above'}")

    print()
    print("  Output paths:")
    for label, path in metadata.get("output_paths", {}).items():
        print(f"    {label:<20} {path}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# URL streaming entry point
# ---------------------------------------------------------------------------

def run_url(
    url: str,
    source_file: str | None,
    max_games: int,
    max_accepted: int | None,
) -> dict:
    """Open a .pgn.zst URL and stream-parse up to max_games raw games."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "chess-MHSUC/0.1 run-parser"},
    )
    with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT_S) as response:
        dctx = zstandard.ZstdDecompressor()
        raw_reader = dctx.stream_reader(
            response, read_size=READ_CHUNK_SIZE, closefd=False
        )
        buffered = io.BufferedReader(raw_reader, buffer_size=BUFFER_SIZE)
        text_stream = io.TextIOWrapper(
            buffered, encoding="utf-8", errors="replace"
        )
        return stream_and_parse(
            text_stream,
            source_file=source_file,
            max_games=max_games,
            max_accepted=max_accepted,
            url=url,
        )


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def _make_stem(
    source_file: str | None,
    max_games: int,
    version_tag: str,
) -> str:
    """
    Build the common filename stem from source metadata.

    Examples:
        source_file="lichess_db_standard_rated_2024-09.pgn.zst",
        max_games=25000, version_tag="v1"  →  "2024_09_25k_v1"
    """
    month = parse_source_month(source_file) or "unknown"
    month_slug = month.replace("-", "_")
    if max_games % 1_000 == 0:
        cap_str = f"{max_games // 1_000}k"
    else:
        cap_str = str(max_games)
    return f"{month_slug}_{cap_str}_{version_tag}"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Stream a Lichess .pgn.zst archive, parse 600+0 games up to a "
            "cap, and write interim Parquet + metadata outputs."
        )
    )
    parser.add_argument("--url", required=True, help="URL of the .pgn.zst archive")
    parser.add_argument(
        "--max-games",
        type=int,
        required=True,
        help=(
            "Maximum raw games to scan.  Required — there is no unbounded "
            "default.  Recommended first run: 25000."
        ),
    )
    parser.add_argument(
        "--max-accepted",
        type=int,
        default=None,
        help=(
            "Stop early when this many accepted_basic 600+0 games have been "
            "collected (whichever cap is hit first)."
        ),
    )
    parser.add_argument(
        "--source-file",
        required=True,
        help="Archive filename string for metadata (e.g. lichess_db_standard_rated_2024-09.pgn.zst)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for output files (e.g. data/interim).  Must be gitignored.",
    )
    parser.add_argument(
        "--version-tag",
        required=True,
        help="Version suffix for output filenames (e.g. v1).",
    )
    args = parser.parse_args(argv)

    stem = _make_stem(args.source_file, args.max_games, args.version_tag)
    out_dir = Path(args.output_dir)
    game_records_path = out_dir / f"game_records_{stem}.parquet"
    position_records_path = out_dir / f"position_records_{stem}.parquet"
    metadata_path = out_dir / f"parser_validation_{stem}_metadata.json"

    print(f"Streaming: {args.url}", file=sys.stderr)
    print(f"Raw games cap:  {args.max_games:,}", file=sys.stderr)
    if args.max_accepted:
        print(f"Accepted cap:   {args.max_accepted:,}", file=sys.stderr)
    print(f"Output stem:    {stem}", file=sys.stderr)
    print(f"Output dir:     {out_dir}", file=sys.stderr)

    try:
        result = run_url(
            url=args.url,
            source_file=args.source_file,
            max_games=args.max_games,
            max_accepted=args.max_accepted,
        )
    except Exception as e:
        print(f"ERROR during streaming: {e}", file=sys.stderr)
        return 1

    print(
        f"Stream complete. {result['n_raw_scanned']:,} raw games scanned, "
        f"{result['n_600_0_total']:,} were 600+0, "
        f"{result['n_parse_errors']} parse errors.",
        file=sys.stderr,
    )
    print("Writing outputs...", file=sys.stderr)

    metadata = write_outputs(
        result=result,
        game_records_path=game_records_path,
        position_records_path=position_records_path,
        metadata_path=metadata_path,
        source_url=args.url,
        source_file=args.source_file,
        raw_games_cap=args.max_games,
        max_accepted_basic=args.max_accepted,
        version_tag=args.version_tag,
    )

    # Load the written DataFrames for validation checks and summary
    df_games = pl.read_parquet(str(game_records_path))
    df_positions = pl.read_parquet(str(position_records_path))

    checks = validation_checks(df_games, df_positions)
    print_validation_summary(metadata, checks, df_games, df_positions)

    # Log any parse errors
    if result["error_log"]:
        print("Parse error log (first 20):", file=sys.stderr)
        for entry in result["error_log"][:20]:
            print(f"  {entry['game_site']}: {entry['error']}", file=sys.stderr)

    n_failures = sum(1 for v in checks.values() if not v)
    if n_failures > 0:
        print(
            f"WARNING: {n_failures} validation check(s) failed.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
