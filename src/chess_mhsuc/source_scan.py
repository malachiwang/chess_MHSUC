"""
source_scan.py — streaming capped scanner for Lichess monthly PGN archives.

Streams a .pgn.zst file from a URL without full decompression to disk.
Counts game-level statistics up to a configurable cap.

Usage:
    python -m chess_mhsuc.source_scan \\
        --url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst \\
        --max-games 50000 \\
        --output data/interim/source_scan_2024_09_50k_v1.json
"""

import argparse
import io
import json
import statistics
import sys
import time
import urllib.request
from collections import Counter
from dataclasses import dataclass, field

import chess.pgn
import zstandard

TARGET_TIME_CONTROL = "600+0"
VALID_RESULTS = {"1-0", "0-1", "1/2-1/2"}
DEFAULT_MAX_GAMES = 50_000
CONNECT_TIMEOUT_S = 60
READ_CHUNK_SIZE = 1 << 16   # 64 KiB
BUFFER_SIZE = 1 << 17       # 128 KiB


@dataclass
class ScanResult:
    url: str = ""
    max_games: int = 0
    n_total: int = 0

    # 600+0 qualifying counts
    n_600_0_total: int = 0
    n_600_0_basic_pass: int = 0   # 600+0 + valid Elo + valid Result + %clk
    n_600_0_eval_pass: int = 0    # basic_pass + %eval

    # rejection tallies for 600+0 games (can overlap)
    n_600_0_invalid_elo: int = 0
    n_600_0_invalid_result: int = 0
    n_600_0_no_clock: int = 0
    n_600_0_no_eval: int = 0      # among basic_pass games

    # result and termination distributions (600+0 basic_pass games)
    result_dist: Counter = field(default_factory=Counter)
    termination_dist: Counter = field(default_factory=Counter)

    # Elo lists (600+0 basic_pass games)
    white_elos: list = field(default_factory=list)
    black_elos: list = field(default_factory=list)

    # timing
    elapsed_s: float = 0.0


def _is_valid_elo(elo_str: str) -> bool:
    """Return True if the Elo string is a valid integer (not '?' or missing)."""
    if not elo_str or elo_str == "?":
        return False
    try:
        val = int(elo_str)
        return val > 0
    except (ValueError, TypeError):
        return False


def _game_has_annotation(game: chess.pgn.Game, tag: str) -> bool:
    """Return True if any main-line node comment contains the annotation tag."""
    node = game
    while node.variations:
        node = node.variations[0]
        if tag in node.comment:
            return True
    return False


def inspect_game(game: chess.pgn.Game, result: ScanResult) -> None:
    """Inspect a single parsed game and update result counts in-place."""
    headers = game.headers
    tc = headers.get("TimeControl", "")

    if tc != TARGET_TIME_CONTROL:
        return

    result.n_600_0_total += 1

    white_elo = headers.get("WhiteElo", "?")
    black_elo = headers.get("BlackElo", "?")
    game_result = headers.get("Result", "*")
    termination = headers.get("Termination", "")

    valid_elo = _is_valid_elo(white_elo) and _is_valid_elo(black_elo)
    valid_result = game_result in VALID_RESULTS
    has_clock = _game_has_annotation(game, "%clk")

    if not valid_elo:
        result.n_600_0_invalid_elo += 1
    if not valid_result:
        result.n_600_0_invalid_result += 1
    if not has_clock:
        result.n_600_0_no_clock += 1

    if not (valid_elo and valid_result and has_clock):
        return

    result.n_600_0_basic_pass += 1
    result.result_dist[game_result] += 1
    result.termination_dist[termination] += 1
    result.white_elos.append(int(white_elo))
    result.black_elos.append(int(black_elo))

    has_eval = _game_has_annotation(game, "%eval")
    if not has_eval:
        result.n_600_0_no_eval += 1
    else:
        result.n_600_0_eval_pass += 1


def scan_stream(
    text_stream: io.TextIOWrapper,
    max_games: int,
    url: str = "",
) -> ScanResult:
    """Read games from an open text stream up to max_games total games."""
    result = ScanResult(url=url, max_games=max_games)
    t0 = time.monotonic()
    while result.n_total < max_games:
        game = chess.pgn.read_game(text_stream)
        if game is None:
            break
        result.n_total += 1
        inspect_game(game, result)
    result.elapsed_s = time.monotonic() - t0
    return result


def scan_url(url: str, max_games: int = DEFAULT_MAX_GAMES) -> ScanResult:
    """Open a .pgn.zst URL and stream-scan up to max_games games."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "chess-MHSUC/0.1 source-scan"},
    )
    with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT_S) as response:
        dctx = zstandard.ZstdDecompressor()
        raw_reader = dctx.stream_reader(
            response, read_size=READ_CHUNK_SIZE, closefd=False
        )
        buffered = io.BufferedReader(raw_reader, buffer_size=BUFFER_SIZE)
        text_stream = io.TextIOWrapper(buffered, encoding="utf-8", errors="replace")
        return scan_stream(text_stream, max_games=max_games, url=url)


def _elo_summary(elos: list) -> dict:
    if not elos:
        return {"count": 0}
    return {
        "count": len(elos),
        "min": min(elos),
        "max": max(elos),
        "mean": round(statistics.mean(elos), 1),
        "median": statistics.median(elos),
        "stdev": round(statistics.stdev(elos), 1) if len(elos) > 1 else 0.0,
    }


def build_summary(result: ScanResult) -> dict:
    """Build a JSON-serializable summary dict from a ScanResult."""
    basic = result.n_600_0_basic_pass
    total = result.n_total
    return {
        "scan_metadata": {
            "url": result.url,
            "max_games_cap": result.max_games,
            "n_total_scanned": total,
            "elapsed_s": round(result.elapsed_s, 2),
            "games_per_second": round(total / result.elapsed_s, 1) if result.elapsed_s > 0 else 0,
        },
        "time_control_filter": {
            "target": TARGET_TIME_CONTROL,
            "n_600_0_total": result.n_600_0_total,
            "n_600_0_pct_of_total": round(100 * result.n_600_0_total / total, 2) if total > 0 else 0,
        },
        "pass_rates": {
            "n_600_0_basic_pass": basic,
            "n_600_0_basic_pass_pct_of_600": round(100 * basic / result.n_600_0_total, 2) if result.n_600_0_total > 0 else 0,
            "n_600_0_eval_pass": result.n_600_0_eval_pass,
            "n_600_0_eval_pass_pct_of_basic": round(100 * result.n_600_0_eval_pass / basic, 2) if basic > 0 else 0,
        },
        "rejection_reasons_600_0": {
            "invalid_elo": result.n_600_0_invalid_elo,
            "invalid_result": result.n_600_0_invalid_result,
            "no_clock": result.n_600_0_no_clock,
            "no_eval_among_basic_pass": result.n_600_0_no_eval,
        },
        "result_dist_600_0_basic_pass": dict(result.result_dist),
        "termination_dist_600_0_basic_pass": dict(result.termination_dist),
        "elo_summary_white_600_0_basic_pass": _elo_summary(result.white_elos),
        "elo_summary_black_600_0_basic_pass": _elo_summary(result.black_elos),
    }


def write_summary(summary: dict, output_path: str) -> None:
    from pathlib import Path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Stream-scan a Lichess .pgn.zst file and emit a JSON summary."
    )
    parser.add_argument("--url", required=True, help="URL of the .pgn.zst file")
    parser.add_argument(
        "--max-games",
        type=int,
        default=DEFAULT_MAX_GAMES,
        help=f"Maximum number of games to scan (default: {DEFAULT_MAX_GAMES})",
    )
    parser.add_argument(
        "--output", required=True, help="Path for the output JSON summary"
    )
    args = parser.parse_args(argv)

    print(f"Scanning: {args.url}", file=sys.stderr)
    print(f"Cap: {args.max_games:,} games", file=sys.stderr)

    result = scan_url(args.url, max_games=args.max_games)
    summary = build_summary(result)
    write_summary(summary, args.output)

    print(f"Done. {result.n_total:,} games scanned in {result.elapsed_s:.1f}s", file=sys.stderr)
    print(f"600+0 total: {result.n_600_0_total:,}", file=sys.stderr)
    print(f"600+0 basic_pass: {result.n_600_0_basic_pass:,}", file=sys.stderr)
    print(f"600+0 eval_pass:  {result.n_600_0_eval_pass:,}", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
