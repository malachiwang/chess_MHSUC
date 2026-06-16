"""
Dense move-by-move loss extraction — Ticket 15.3B (PILOT ONLY).

The checkpoint layer (15.0C / `next_move_loss.py`) measures next-move quality
loss at four numbered checkpoints per game (move_10/20/30/40), where the mover is
ALWAYS White. This module extends that measurement to EVERY ply of a game (both
White and Black moves) so the Constraint Atlas can be drawn as a dense curve
rather than four points.

15.3A found the full both-months dense pass would be ~3.3-3.4M evaluated
positions (~17-24h @ depth-12). This module therefore runs a **capped pilot
only**: it refuses uncapped runs and has NO full-run flag. The default cap is
1,500 accepted games; caps above 2,000 require an explicit named override.

Evaluation strategy (Option A from 15.3A): one Stockfish eval per pre-move
position. The post-move eval of move i is the pre-move eval of move i+1 (the same
FEN), so consecutive evals are reused — no MultiPV and no separate best-move
search (a depth-d analyse value is already the best-line value).

Metric policy (15.3A):
  - PRIMARY:   expected_score_loss, mover perspective (train-fit cp->ES transform).
  - SECONDARY: clipped centipawn loss.
  - DIAGNOSTIC: raw centipawn loss (eval-band-conditioned panels only).
  - FORBIDDEN headline: percent eval swing.

All results are predictive/descriptive associations between constraint state and
next-move loss — NOT causal, not a "degradation curve". Stockfish depth-d eval is
objective position context, not absolute ground truth.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.dense_move_loss \\
        --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn \\
        --month 2024_09 \\
        --max-accepted-games 1500 \\
        --min-move-number 5 \\
        --depth 12 \\
        --stockfish-path /opt/homebrew/bin/stockfish \\
        --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \\
        --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \\
        --out data/processed/dense_move_loss_pilot_2024_09_v1.parquet \\
        --report reports/dense_move_loss_pilot_2024_09_v1.md
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import polars as pl

from chess_mhsuc.constraint_atlas import eval_band, rating_bin
from chess_mhsuc.next_move_loss import (
    MOVE_QUALITY_CP_CAP,
    _fen_hash,
    expected_score,
    is_mate_band,
    time_bucket_for,
    to_mover_cp,
)
from chess_mhsuc.player_metadata import join_mover_player
from chess_mhsuc.stockfish_eval import (
    DEFAULT_DEPTH,
    MATE_CP_SENTINEL,
    analyse_fen,
    get_stockfish_version,
    open_pgn_stream,
    resolve_stockfish_path,
)


# ---------------------------------------------------------------------------
# Safety caps (no full-run path exists in this module)
# ---------------------------------------------------------------------------

PILOT_DEFAULT_MAX_GAMES = 1500
PILOT_HARD_MAX_GAMES = 2000  # above this requires the explicit override flag

# 15.3A both-months dense universe estimate (used for full-run extrapolation only).
FULL_RUN_BOTH_MONTHS_POSITIONS = 3_340_000

_CLK_RE = re.compile(r"\[%clk\s+(\d+:\d{2}:\d{2})\]")
_STATUS_OK = "ok"
_STATUS_EVAL_ERR_BEFORE = "eval_error_before"
_STATUS_EVAL_ERR_AFTER = "eval_error_after"
_STATUS_EVAL_ERR_BOTH = "eval_error_both"

_TEN_ZERO_START_S = 600.0  # 10+0 starting clock

_KEY = ["game_id", "ply"]

# Explicit output schema (prevents Null-type inference on early all-None columns).
_OUTPUT_SCHEMA: dict[str, pl.PolarsDataType] = {
    "game_id":                pl.Utf8,
    "month":                  pl.Utf8,
    "ply":                    pl.Int64,
    "move_number":            pl.Int64,
    "side_to_move":           pl.Utf8,
    "mover_color":            pl.Utf8,
    "opponent_color":         pl.Utf8,
    "dense_position_type":    pl.Utf8,
    "move_uci":               pl.Utf8,
    "clock_before_s":         pl.Float64,
    "clock_after_s":          pl.Float64,
    "think_time_s":           pl.Float64,
    "white_clock_before_s":   pl.Float64,
    "black_clock_before_s":   pl.Float64,
    "white_clock_after_s":    pl.Float64,
    "black_clock_after_s":    pl.Float64,
    "white_elo":              pl.Int64,
    "black_elo":              pl.Int64,
    "mover_elo":              pl.Int64,
    "opponent_elo":           pl.Int64,
    "elo_diff_mover":         pl.Int64,
    "termination":            pl.Utf8,
    "is_time_forfeit":        pl.Boolean,
    "result_class":           pl.Utf8,
    "mover_result":           pl.Utf8,
    "pre_fen":                pl.Utf8,
    "fen_hash":               pl.Utf8,
    "post_fen_hash":          pl.Utf8,
    "eval_before_cp":         pl.Int64,
    "eval_before_mate":       pl.Int64,
    "eval_after_actual_cp":   pl.Int64,
    "eval_after_actual_mate": pl.Int64,
    "cp_loss_raw":            pl.Int64,
    "cp_loss_clipped":        pl.Int64,
    "expected_score_before":  pl.Float64,
    "expected_score_after_actual": pl.Float64,
    "expected_score_loss":    pl.Float64,
    "is_mate_band":           pl.Boolean,
    "phase":                  pl.Utf8,
    "eval_band":              pl.Utf8,
    "clock_bucket":           pl.Utf8,
    "think_time_bucket":      pl.Utf8,
    "rating_bucket":          pl.Utf8,
    "move_is_capture":        pl.Boolean,
    "move_is_check":          pl.Boolean,
    "move_is_promotion":      pl.Boolean,
    "move_is_castle":         pl.Boolean,
    "split_set":              pl.Utf8,
    "sf_depth":               pl.Int64,
    "status":                 pl.Utf8,
    "failure_reason":         pl.Utf8,
}

# Columns added by the player-hash join (selected into the final frame).
_HASH_COLS = ["mover_player_hash", "opponent_player_hash"]


# ---------------------------------------------------------------------------
# A. Pure helpers — clocks, buckets, loss, terminal eval
# ---------------------------------------------------------------------------

def parse_clk_seconds(comment: str | None) -> float | None:
    """Extract `[%clk H:MM:SS]` from a move comment as float seconds, else None."""
    if not comment:
        return None
    m = _CLK_RE.search(comment)
    if not m:
        return None
    h, mm, ss = m.group(1).split(":")
    return float(int(h) * 3600 + int(mm) * 60 + int(ss))


def think_time(clock_before_s: float | None, clock_after_s: float | None) -> float | None:
    """Think time = clock_before - clock_after (10+0 has no increment)."""
    if clock_before_s is None or clock_after_s is None:
        return None
    return clock_before_s - clock_after_s


def clock_flags(
    clock_before_s: float | None,
    clock_after_s: float | None,
    think_time_s: float | None,
    start_s: float = _TEN_ZERO_START_S,
) -> tuple[bool, bool]:
    """
    (clock_anomaly, think_time_anomaly). Flags but never drops: missing clock,
    clock out of [0, start], negative or implausibly large (> start) think time.
    """
    clock_anom = False
    if clock_after_s is None:
        clock_anom = True
    else:
        if clock_after_s < 0 or clock_after_s > start_s:
            clock_anom = True
    if clock_before_s is None or clock_before_s < 0 or clock_before_s > start_s:
        clock_anom = True

    think_anom = False
    if think_time_s is None:
        think_anom = True
    elif think_time_s < 0 or think_time_s > start_s:
        think_anom = True
    return clock_anom, think_anom


def phase_for(move_number: int | None) -> str | None:
    """
    Coarse game phase from the full-move number (pilot-local, descriptive only):
    opening (<=10), middlegame (11-30), endgame (>30).
    """
    if move_number is None:
        return None
    if move_number <= 10:
        return "opening"
    if move_number <= 30:
        return "middlegame"
    return "endgame"


def think_time_bucket(think_time_s: float | None) -> str | None:
    """Descriptive think-time bins (seconds). None if missing/negative."""
    if think_time_s is None or think_time_s < 0:
        return None
    if think_time_s < 1:
        return "instant_lt1"
    if think_time_s < 3:
        return "1_3"
    if think_time_s < 10:
        return "3_10"
    if think_time_s < 30:
        return "10_30"
    return "over_30"


def clock_bucket_coarse(clock_s: float | None) -> str | None:
    """under_60 / 60_180 / over_180 from a remaining-clock value (None if missing)."""
    tb = time_bucket_for(clock_s)
    if tb is None:
        return None
    return {"under_60s": "under_60", "60_180s": "60_180",
            "over_180s": "over_180"}[tb]


def clip_cp(value: int | None, cap: int = MOVE_QUALITY_CP_CAP) -> int | None:
    if value is None:
        return None
    return max(-cap, min(cap, value))


def cp_loss_raw(mover_before: int | None, mover_after: int | None) -> int | None:
    """Signed raw cp loss (may be negative if the actual move beat the prior static eval)."""
    if mover_before is None or mover_after is None:
        return None
    return mover_before - mover_after


def cp_loss_clipped(
    mover_before: int | None, mover_after: int | None, cap: int = MOVE_QUALITY_CP_CAP
) -> int | None:
    """Clip both mover-perspective values to +/-cap, then max(0, before - after)."""
    cb = clip_cp(mover_before, cap)
    ca = clip_cp(mover_after, cap)
    if cb is None or ca is None:
        return None
    return max(0, cb - ca)


def es_loss(es_before: float | None, es_after: float | None) -> float | None:
    """expected_score_loss = max(0, ES_before - ES_after); bounded in [0, 1]."""
    if es_before is None or es_after is None:
        return None
    return max(0.0, es_before - es_after)


def mover_result_label(result_class: str | None, mover_is_white: bool) -> str | None:
    """Mover-perspective game result: win / loss / draw."""
    if result_class == "DRAW":
        return "draw"
    if result_class == "WHITE_WIN":
        return "win" if mover_is_white else "loss"
    if result_class == "BLACK_WIN":
        return "loss" if mover_is_white else "win"
    return None


def terminal_white_eval(board: chess.Board) -> tuple[int, int | None] | None:
    """
    White-POV (cp, mate) for a board-terminal position, or None if not terminal.
    Checkmate -> mate sentinel toward the side that just moved; stalemate /
    insufficient material / 75-move / fivefold -> drawn (cp 0).
    """
    if board.is_checkmate():
        # side to move is mated; the previous mover delivered mate.
        if board.turn == chess.WHITE:
            return -MATE_CP_SENTINEL, 0   # White is mated -> Black delivered
        return MATE_CP_SENTINEL, 0        # Black is mated -> White delivered
    if (board.is_stalemate() or board.is_insufficient_material()
            or board.is_seventyfive_moves() or board.is_fivefold_repetition()):
        return 0, None
    return None


# ---------------------------------------------------------------------------
# B. Accepted-game metadata
# ---------------------------------------------------------------------------

def load_accepted_game_meta(
    version_tag: str,
    game_records_path: str | Path | None = None,
    splits_path: str | Path | None = None,
) -> dict[str, dict]:
    """
    Build {game_id -> metadata} for accepted 600+0 games (accepted_basic). Metadata:
    result_class, termination, is_time_forfeit, white_elo, black_elo, split_set.
    split_set defaults to 'unknown' when a game is absent from the splits JSON.
    """
    gr_path = Path(game_records_path
                   or f"data/interim/game_records_{version_tag}.parquet")
    gr = pl.read_parquet(gr_path)
    acc = gr.filter(pl.col("accepted_basic") & (pl.col("time_control") == "600+0"))

    assignments: dict[str, str] = {}
    sp_path = Path(splits_path or f"data/processed/splits_{version_tag}.json")
    if sp_path.exists():
        with open(sp_path) as f:
            assignments = json.load(f).get("assignments", {})

    meta: dict[str, dict] = {}
    for r in acc.select(
        ["game_id", "result_class", "termination", "white_elo", "black_elo"]
    ).iter_rows(named=True):
        gid = r["game_id"]
        meta[gid] = {
            "result_class": r["result_class"],
            "termination": r["termination"],
            "is_time_forfeit": r["termination"] == "Time forfeit",
            "white_elo": r["white_elo"],
            "black_elo": r["black_elo"],
            "split_set": assignments.get(gid, "unknown"),
        }
    return meta


def _game_id_from_site(site: str) -> str | None:
    if not site:
        return None
    slug = site.rstrip("/").split("/")[-1]
    return slug or None


# ---------------------------------------------------------------------------
# C. Per-ply replay (no engine) -> move records + position chain
# ---------------------------------------------------------------------------

def build_move_records(
    game: chess.pgn.Game,
    game_meta: dict,
    min_move_number: int,
) -> tuple[list[dict], list[str], str | None]:
    """
    Replay the mainline once and produce one record per played move with
    move_number >= ``min_move_number`` (both colors). Returns
    (records, position_fens, replay_failure_reason). ``position_fens[k]`` is the
    FEN after k plies (so a record's pre_fen = position_fens[ply-1], post_fen =
    position_fens[ply]). Clocks are tracked across ALL moves so carry-forward is
    correct even for the emitted subset.
    """
    board = game.board()
    position_fens: list[str] = [board.fen()]
    records: list[dict] = []
    white_clk: float | None = None
    black_clk: float | None = None
    failure_reason: str | None = None

    node = game
    ply = 0
    while node.variations:
        nxt = node.variation(0)
        move = nxt.move
        mover_is_white = board.turn == chess.WHITE
        move_number = board.fullmove_number

        # move tags computed on the pre-move board
        try:
            is_capture = board.is_capture(move)
            is_check = board.gives_check(move)
            is_castle = board.is_castling(move)
        except Exception:
            failure_reason = f"illegal_move_at_ply_{ply + 1}"
            break
        is_promotion = move.promotion is not None

        # clocks: snapshot carried values BEFORE this move
        w_before, b_before = white_clk, black_clk
        mover_before = (white_clk if mover_is_white else black_clk)
        if mover_before is None:
            mover_before = _TEN_ZERO_START_S  # side's first move in 10+0

        clk_after = parse_clk_seconds(nxt.comment)
        if clk_after is not None:
            if mover_is_white:
                white_clk = clk_after
            else:
                black_clk = clk_after

        try:
            board.push(move)
        except Exception:
            failure_reason = f"illegal_move_at_ply_{ply + 1}"
            break
        ply += 1
        post_fen = board.fen()
        position_fens.append(post_fen)
        node = nxt

        if move_number < min_move_number:
            continue

        tt = think_time(mover_before, clk_after)
        clock_anom, think_anom = clock_flags(mover_before, clk_after, tt)
        records.append({
            "ply": ply,
            "move_number": move_number,
            "mover_is_white": mover_is_white,
            "pre_fen": position_fens[ply - 1],
            "post_fen": post_fen,
            "move_uci": move.uci(),
            "clock_before_s": mover_before,
            "clock_after_s": clk_after,
            "think_time_s": tt,
            "white_clock_before_s": w_before,
            "black_clock_before_s": b_before,
            "white_clock_after_s": white_clk,
            "black_clock_after_s": black_clk,
            "move_is_capture": is_capture,
            "move_is_check": is_check,
            "move_is_promotion": is_promotion,
            "move_is_castle": is_castle,
            "clock_anomaly": clock_anom,
            "think_time_anomaly": think_anom,
        })

    return records, position_fens, failure_reason


# ---------------------------------------------------------------------------
# D. Engine evaluation of a position (cached) + terminal handling
# ---------------------------------------------------------------------------

def eval_white_pov(
    engine: chess.engine.SimpleEngine,
    fen: str,
    depth: int,
    cache: dict[str, dict],
    counters: dict,
) -> dict:
    """
    Evaluate ``fen`` to White-POV {cp, mate, available}. Terminal positions are
    resolved without the engine. Results are cached per FEN string (so the
    post-move position of move i is reused as the pre-move position of move i+1).
    """
    hit = cache.get(fen)
    if hit is not None:
        counters["eval_cache_hits"] += 1
        return hit

    board = chess.Board(fen)
    term = terminal_white_eval(board)
    if term is not None:
        out = {"cp": term[0], "mate": term[1], "available": True, "terminal": True}
        counters["terminal_positions"] += 1
        cache[fen] = out
        return out

    res = analyse_fen(engine, fen, depth)
    counters["engine_evals"] += 1
    if not res.get("sf_eval_available"):
        out = {"cp": None, "mate": None, "available": False, "terminal": False}
    else:
        out = {"cp": res["sf_eval_cp"], "mate": res["sf_eval_mate"],
               "available": True, "terminal": False}
    cache[fen] = out
    return out


# ---------------------------------------------------------------------------
# E. Assemble one output row from a move record + evals
# ---------------------------------------------------------------------------

def assemble_row(
    game_id: str,
    month: str,
    rec: dict,
    game_meta: dict,
    eval_before: dict,
    eval_after: dict,
    depth: int,
    es_scale: float | None,
) -> dict:
    mover_is_white = rec["mover_is_white"]
    white_cp_b, white_mate_b = eval_before["cp"], eval_before["mate"]
    white_cp_a, white_mate_a = eval_after["cp"], eval_after["mate"]

    mover_before = to_mover_cp(white_cp_b, mover_is_white)
    mover_after = to_mover_cp(white_cp_a, mover_is_white)

    mate_band = is_mate_band(white_cp_b, white_mate_b, white_cp_a, white_mate_a)
    raw = cp_loss_raw(mover_before, mover_after)
    clipped = cp_loss_clipped(mover_before, mover_after)

    es_b = expected_score(mover_before, es_scale) if (es_scale and mover_before is not None) else None
    es_a = expected_score(mover_after, es_scale) if (es_scale and mover_after is not None) else None
    es_l = es_loss(es_b, es_a)

    if not eval_before["available"] and not eval_after["available"]:
        status, fail = _STATUS_EVAL_ERR_BOTH, "engine_eval_unavailable"
    elif not eval_before["available"]:
        status, fail = _STATUS_EVAL_ERR_BEFORE, "engine_eval_unavailable"
    elif not eval_after["available"]:
        status, fail = _STATUS_EVAL_ERR_AFTER, "engine_eval_unavailable"
    else:
        status, fail = _STATUS_OK, None

    white_elo = game_meta["white_elo"]
    black_elo = game_meta["black_elo"]
    mover_elo = white_elo if mover_is_white else black_elo
    opp_elo = black_elo if mover_is_white else white_elo
    elo_diff = (mover_elo - opp_elo) if (mover_elo is not None and opp_elo is not None) else None

    return {
        "game_id": game_id,
        "month": month,
        "ply": rec["ply"],
        "move_number": rec["move_number"],
        "side_to_move": "white" if mover_is_white else "black",
        "mover_color": "white" if mover_is_white else "black",
        "opponent_color": "black" if mover_is_white else "white",
        "dense_position_type": "dense",
        "move_uci": rec["move_uci"],
        "clock_before_s": rec["clock_before_s"],
        "clock_after_s": rec["clock_after_s"],
        "think_time_s": rec["think_time_s"],
        "white_clock_before_s": rec["white_clock_before_s"],
        "black_clock_before_s": rec["black_clock_before_s"],
        "white_clock_after_s": rec["white_clock_after_s"],
        "black_clock_after_s": rec["black_clock_after_s"],
        "white_elo": white_elo,
        "black_elo": black_elo,
        "mover_elo": mover_elo,
        "opponent_elo": opp_elo,
        "elo_diff_mover": elo_diff,
        "termination": game_meta["termination"],
        "is_time_forfeit": game_meta["is_time_forfeit"],
        "result_class": game_meta["result_class"],
        "mover_result": mover_result_label(game_meta["result_class"], mover_is_white),
        "pre_fen": rec["pre_fen"],
        "fen_hash": _fen_hash(rec["pre_fen"]),
        "post_fen_hash": _fen_hash(rec["post_fen"]),
        "eval_before_cp": white_cp_b,
        "eval_before_mate": white_mate_b,
        "eval_after_actual_cp": white_cp_a,
        "eval_after_actual_mate": white_mate_a,
        "cp_loss_raw": raw,
        "cp_loss_clipped": clipped,
        "expected_score_before": es_b,
        "expected_score_after_actual": es_a,
        "expected_score_loss": es_l,
        "is_mate_band": mate_band,
        "phase": phase_for(rec["move_number"]),
        "eval_band": eval_band(mover_before, mate_band),
        "clock_bucket": clock_bucket_coarse(rec["clock_before_s"]),
        "think_time_bucket": think_time_bucket(rec["think_time_s"]),
        "rating_bucket": rating_bin(mover_elo),
        "move_is_capture": rec["move_is_capture"],
        "move_is_check": rec["move_is_check"],
        "move_is_promotion": rec["move_is_promotion"],
        "move_is_castle": rec["move_is_castle"],
        "split_set": game_meta["split_set"],
        "sf_depth": depth,
        "status": status,
        "failure_reason": fail,
    }


# ---------------------------------------------------------------------------
# F. Pilot extraction loop (capped; streams PGN in order)
# ---------------------------------------------------------------------------

def run_pilot(
    raw_pgn: str,
    month: str,
    accepted_meta: dict[str, dict],
    stockfish_path: str,
    depth: int,
    max_accepted_games: int,
    min_move_number: int,
    es_scale: float | None,
    progress_every: int = 100,
) -> tuple[list[dict], dict, list[dict]]:
    """
    Stream the raw PGN in order, evaluate the first ``max_accepted_games`` accepted
    games densely, and return (rows, counters, sample_positions). One engine eval
    per distinct pre-move position; consecutive moves reuse cached evals.
    """
    counters = {
        "games_scanned": 0, "games_accepted": 0, "games_replay_failed": 0,
        "engine_evals": 0, "eval_cache_hits": 0, "terminal_positions": 0,
        "rows": 0, "engine_seconds": 0.0,
    }
    rows: list[dict] = []
    failed_games: list[dict] = []

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    t0 = time.time()
    try:
        for stream in open_pgn_stream(raw_pgn):
            while counters["games_accepted"] < max_accepted_games:
                try:
                    game = chess.pgn.read_game(stream)
                except Exception:
                    continue
                if game is None:
                    break
                counters["games_scanned"] += 1
                gid = _game_id_from_site(game.headers.get("Site", ""))
                if gid is None or gid not in accepted_meta:
                    continue

                gmeta = accepted_meta[gid]
                records, _fens, replay_fail = build_move_records(
                    game, gmeta, min_move_number)
                if replay_fail is not None:
                    counters["games_replay_failed"] += 1
                    failed_games.append({"game_id": gid, "reason": replay_fail,
                                         "rows_kept": len(records)})

                cache: dict[str, dict] = {}
                t_eng = time.time()
                for rec in records:
                    eb = eval_white_pov(engine, rec["pre_fen"], depth, cache, counters)
                    ea = eval_white_pov(engine, rec["post_fen"], depth, cache, counters)
                    rows.append(assemble_row(gid, month, rec, gmeta, eb, ea,
                                             depth, es_scale))
                counters["engine_seconds"] += time.time() - t_eng

                counters["games_accepted"] += 1
                counters["rows"] = len(rows)
                if (progress_every and counters["games_accepted"]
                        and counters["games_accepted"] % progress_every == 0):
                    print(f"  [dense] {counters['games_accepted']}/{max_accepted_games} "
                          f"games | rows={len(rows)} evals={counters['engine_evals']}",
                          file=sys.stderr)
            break  # only the first stream context is needed
    finally:
        engine.quit()

    counters["runtime_s"] = round(time.time() - t0, 1)
    counters["engine_seconds"] = round(counters["engine_seconds"], 1)
    return rows, counters, failed_games


# ---------------------------------------------------------------------------
# G. Player-hash join + frame assembly
# ---------------------------------------------------------------------------

def attach_player_hashes(
    df: pl.DataFrame, player_metadata_path: str | Path | None
) -> tuple[pl.DataFrame, dict]:
    """
    Join mover/opponent one-way player hashes (gitignored metadata). Returns
    (frame_with_hashes, coverage). If no metadata path is given, hash columns are
    null and coverage is reported as 0.
    """
    if player_metadata_path is None:
        out = df.with_columns([
            pl.lit(None, dtype=pl.Utf8).alias("mover_player_hash"),
            pl.lit(None, dtype=pl.Utf8).alias("opponent_player_hash"),
        ])
        return out, {"available": False, "match_fraction": 0.0,
                     "n_matched": 0, "n_rows": df.height}

    meta = pl.read_parquet(player_metadata_path)
    joined = join_mover_player(df, meta)
    matched = int(joined.filter(pl.col("mover_player_hash").is_not_null()).height)
    cov = {
        "available": True,
        "n_rows": joined.height,
        "n_matched": matched,
        "n_unmatched": joined.height - matched,
        "match_fraction": round(matched / joined.height, 4) if joined.height else 0.0,
    }
    return joined, cov


def finalize_frame(rows: list[dict], player_metadata_path: str | Path | None
                   ) -> tuple[pl.DataFrame, dict]:
    """Build the typed frame, attach hashes, and select the locked schema order."""
    base = pl.from_dicts(rows, schema=_OUTPUT_SCHEMA) if rows else pl.DataFrame(
        schema=_OUTPUT_SCHEMA)
    joined, cov = attach_player_hashes(base, player_metadata_path)
    final_cols = list(_OUTPUT_SCHEMA.keys()) + _HASH_COLS
    return joined.select(final_cols), cov


# ---------------------------------------------------------------------------
# H. Validation / summary
# ---------------------------------------------------------------------------

def _pctile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    return float(sorted_vals[min(len(sorted_vals) - 1, int(p * len(sorted_vals)))])


def summarize(df: pl.DataFrame, counters: dict) -> dict:
    """Validation + loss-metric summary over the pilot frame."""
    n = df.height
    ok = df.filter(pl.col("status") == _STATUS_OK)
    ok_nonmate = ok.filter(~pl.col("is_mate_band"))

    s: dict = {
        "rows": n,
        "unique_games": int(df["game_id"].n_unique()),
        "duplicate_key_count": n - int(df.select(_KEY).unique().height),
        "rows_ok": ok.height,
        "rows_mate_band": int(ok["is_mate_band"].sum()) if ok.height else 0,
        "rows_eval_error": int(df.filter(pl.col("status") != _STATUS_OK).height),
        "missing_clock_rows": int(df.filter(pl.col("clock_after_s").is_null()).height),
        "clock_anomaly_rows": int(df.filter(pl.col("clock_bucket").is_null()).height),
        "think_anomaly_rows": int(df.filter(pl.col("think_time_bucket").is_null()).height),
    }

    # raw username guard
    forbidden = {"white", "black", "White", "Black", "white_user", "black_user"}
    s["no_username_cols"] = len(forbidden & set(df.columns)) == 0

    # counts by category
    def _counts(col: str) -> dict:
        if col not in df.columns or df.height == 0:
            return {}
        g = df.group_by(col).len().sort(col)
        return {str(r[0]): int(r[1]) for r in g.iter_rows()}

    s["rows_by_mover_color"] = _counts("mover_color")
    s["rows_by_phase"] = _counts("phase")
    s["rows_by_clock_bucket"] = _counts("clock_bucket")
    s["rows_by_rating_bucket"] = _counts("rating_bucket")
    s["rows_by_eval_band"] = _counts("eval_band")

    # loss metrics (OK, non-mate-band)
    if ok_nonmate.height:
        es = sorted(v for v in ok_nonmate["expected_score_loss"].to_list() if v is not None)
        cp = sorted(v for v in ok_nonmate["cp_loss_clipped"].to_list() if v is not None)
        if es:
            s["es_loss"] = {
                "n": len(es), "min": round(es[0], 4), "max": round(es[-1], 4),
                "mean": round(statistics.mean(es), 4),
                "median": round(statistics.median(es), 4),
                "p90": round(_pctile(es, 0.90), 4),
                "zero_share": round(sum(1 for x in es if x == 0) / len(es), 4),
                "ge_0_05": round(sum(1 for x in es if x >= 0.05) / len(es), 4),
                "ge_0_10": round(sum(1 for x in es if x >= 0.10) / len(es), 4),
            }
        if cp:
            s["cp_loss_clipped"] = {
                "n": len(cp), "min": int(cp[0]), "max": int(cp[-1]),
                "mean": round(statistics.mean(cp), 1),
                "median": float(statistics.median(cp)),
                "p90": _pctile([float(x) for x in cp], 0.90),
                "zero_share": round(sum(1 for x in cp if x == 0) / len(cp), 4),
                "ge_100": round(sum(1 for x in cp if x >= 100) / len(cp), 4),
                "ge_200": round(sum(1 for x in cp if x >= 200) / len(cp), 4),
            }

    # throughput + extrapolation
    eng_s = counters.get("engine_seconds", 0.0) or 0.0
    evals = counters.get("engine_evals", 0)
    eps = round(evals / eng_s, 1) if eng_s > 0 else None
    s["throughput"] = {
        "engine_evals": evals,
        "eval_cache_hits": counters.get("eval_cache_hits", 0),
        "terminal_positions": counters.get("terminal_positions", 0),
        "engine_seconds": eng_s,
        "runtime_s": counters.get("runtime_s"),
        "evals_per_second": eps,
    }
    if eps:
        full_s = FULL_RUN_BOTH_MONTHS_POSITIONS / eps
        s["full_run_extrapolation"] = {
            "both_months_positions_est": FULL_RUN_BOTH_MONTHS_POSITIONS,
            "evals_per_second": eps,
            "both_months_hours": round(full_s / 3600, 1),
            "single_month_hours": round(full_s / 2 / 3600, 1),
        }
    return s


def depth_timing_subtest(
    fens: list[str], stockfish_path: str, depth: int, max_positions: int
) -> dict:
    """Re-evaluate a capped sample of stored pre-move FENs at an alternate depth to
    measure throughput (timing only; results not persisted)."""
    sample = fens[:max_positions]
    if not sample:
        return {"n": 0}
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    t0 = time.time()
    ok = 0
    try:
        for fen in sample:
            res = analyse_fen(engine, fen, depth)
            if res.get("sf_eval_available"):
                ok += 1
    finally:
        engine.quit()
    elapsed = time.time() - t0
    eps = round(ok / elapsed, 1) if elapsed > 0 else None
    out = {"n": ok, "depth": depth, "seconds": round(elapsed, 1),
           "evals_per_second": eps}
    if eps:
        full_s = FULL_RUN_BOTH_MONTHS_POSITIONS / eps
        out["both_months_hours"] = round(full_s / 3600, 1)
    return out


# ---------------------------------------------------------------------------
# I. Report rendering (committed aggregate; no FENs, no per-game data)
# ---------------------------------------------------------------------------

def render_report(
    month: str, depth: int, min_move_number: int, max_games: int,
    counters: dict, summary: dict, failed_games: list[dict],
    player_coverage: dict, out_path: str, subtest: dict | None,
    sf_version: str,
) -> str:
    s = summary
    L: list[str] = []
    a = L.append
    a(f"# Dense Move Loss Pilot — {month.replace('_', '-')}")
    a("")
    a("**Ticket:** 15.3B — Dense Move-by-Move Loss Extraction Pilot (PILOT ONLY)")
    a(f"**Engine:** {sf_version} @ depth {depth}")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Dense per-ply next-move loss pilot on the first {counters['games_accepted']:,} "
      f"accepted 600+0 games of {month.replace('_', '-')} (cap {max_games:,}). "
      f"Both White and Black moves with move number >= {min_move_number} are "
      f"measured — extending the four White-only numbered checkpoints to a dense "
      f"curve. **This is a pilot only; no full dense extraction has been run.** "
      "One Stockfish eval per pre-move position (Option A); the post-move eval is "
      "the next position's eval (reused). Primary metric: expected-score loss, "
      "mover perspective; secondary: clipped centipawn loss. Predictive/descriptive "
      "only — not causal, not a degradation curve; Stockfish eval is objective "
      "position context, not absolute ground truth.")
    a("")
    a("## 2. Pilot scope")
    a("")
    a(f"- Month: {month}")
    a(f"- Accepted games scanned to fill cap: {counters['games_scanned']:,}")
    a(f"- Accepted games used: {counters['games_accepted']:,} (cap {max_games:,})")
    a(f"- Universe: non-terminal plies, move_number >= {min_move_number}, both colors")
    a(f"- Eval strategy: Option A (one eval per pre-move position; post-move reused)")
    a("")
    a("## 3. Runtime and throughput")
    a("")
    t = s["throughput"]
    a(f"- Wall-clock runtime: {t['runtime_s']} s")
    a(f"- Engine seconds: {t['engine_seconds']} s")
    a(f"- Engine evals: {t['engine_evals']:,} | cache reuse hits: {t['eval_cache_hits']:,} "
      f"| terminal positions: {t['terminal_positions']:,}")
    a(f"- Throughput: {t['evals_per_second']} evals/s")
    a("")
    a("## 4. Replay validation")
    a("")
    a(f"- Rows written: {s['rows']:,}")
    a(f"- Unique games: {s['unique_games']:,}")
    a(f"- Duplicate (game_id, ply) keys: {s['duplicate_key_count']}")
    a(f"- Games with a replay failure (partial rows kept): {counters['games_replay_failed']}")
    if failed_games:
        a("- Replay-failure reasons (first few): "
          + ", ".join(f"{f['game_id']}:{f['reason']}" for f in failed_games[:5]))
    a("")
    a("## 5. Clock / think-time validation")
    a("")
    a(f"- Missing-clock rows: {s['missing_clock_rows']}")
    a(f"- Clock-anomaly rows (no coarse bucket): {s['clock_anomaly_rows']}")
    a(f"- Think-time-anomaly rows (no bucket): {s['think_anomaly_rows']}")
    a(f"- clock_before_s default for a side's first move: {int(_TEN_ZERO_START_S)} s (10+0).")
    a("")
    a("## 6. Evaluation validation")
    a("")
    a(f"- OK rows: {s['rows_ok']:,}")
    a(f"- Mate-band rows (flagged, excluded from headline): {s['rows_mate_band']:,}")
    a(f"- Eval-error rows: {s['rows_eval_error']}")
    a("")
    a("## 7. Row schema validation")
    a("")
    a(f"- No raw-username columns: {s['no_username_cols']}")
    a(f"- Columns: {len(_OUTPUT_SCHEMA) + len(_HASH_COLS)} "
      "(typed schema + mover/opponent player hashes)")
    a("")
    a("## 8. Loss metric summary")
    a("")
    if "es_loss" in s:
        e = s["es_loss"]
        a(f"Expected-score loss (OK, non-mate-band, n={e['n']:,}): mean {e['mean']} | "
          f"median {e['median']} | p90 {e['p90']} | zero share {e['zero_share']}")
    if "cp_loss_clipped" in s:
        c = s["cp_loss_clipped"]
        a(f"Clipped cp loss (n={c['n']:,}): mean {c['mean']} | median {c['median']} | "
          f"p90 {c['p90']} | zero share {c['zero_share']}")
    a("")
    a("## 9. Large-loss rates")
    a("")
    if "es_loss" in s:
        e = s["es_loss"]
        a(f"- ES loss >= 0.05: {e['ge_0_05']} | >= 0.10: {e['ge_0_10']}")
    if "cp_loss_clipped" in s:
        c = s["cp_loss_clipped"]
        a(f"- clipped cp >= 100: {c['ge_100']} | >= 200: {c['ge_200']}")
    a("")
    a("## 10. Coverage by color / phase / clock / rating")
    a("")
    a(f"- By mover color: {s['rows_by_mover_color']}")
    a(f"- By phase: {s['rows_by_phase']}")
    a(f"- By clock bucket: {s['rows_by_clock_bucket']}")
    a(f"- By eval band: {s['rows_by_eval_band']}")
    a(f"- By rating bucket: {s['rows_by_rating_bucket']}")
    a("")
    a("## 11. Player-hash join coverage")
    a("")
    if player_coverage.get("available"):
        a(f"- mover_player_hash match fraction: {player_coverage['match_fraction']} "
          f"({player_coverage['n_matched']:,}/{player_coverage['n_rows']:,})")
    else:
        a("- player metadata not provided; hash columns null.")
    a("")
    a("## 12. Full-run runtime extrapolation")
    a("")
    if "full_run_extrapolation" in s:
        f = s["full_run_extrapolation"]
        a(f"- 15.3A both-months dense universe estimate: ~{f['both_months_positions_est']:,} positions.")
        a(f"- At pilot throughput ({f['evals_per_second']} evals/s, depth {depth}): "
          f"~{f['both_months_hours']} h both months (~{f['single_month_hours']} h/month).")
    if subtest and subtest.get("n"):
        a(f"- Depth-{subtest['depth']} timing subtest ({subtest['n']} positions): "
          f"{subtest['evals_per_second']} evals/s -> "
          f"~{subtest.get('both_months_hours')} h both months.")
    a("")
    a("## 13. Known limitations")
    a("")
    a("- Pilot only; one month, capped game count; not the full dense atlas.")
    a("- Depth-parity: pre-move (mover to move) and post-move (opponent to move) "
      "are both evaluated at the same fixed depth; the half-ply search-parity "
      "asymmetry is acknowledged (15.0C found it benign) and should be re-checked.")
    a("- Mate-band rows are flagged and excluded from headline loss summaries.")
    a("- Loss distributions are right-skewed; medians/percentiles reported with means.")
    a("- No pre-move trajectory / prior-quality control here (stated limitation).")
    a("- Stockfish eval is objective context, not absolute ground truth; associations "
      "are predictive/descriptive, not causal.")
    a("")
    a("## 14. Recommendation for 15.3C")
    a("")
    a(f"Artifact: `{out_path}` (gitignored under `data/`; not staged).")
    a("")
    a("Recommendation is derived from the measured throughput and validation above; "
      "see the phase report for the explicit 15.3C routing decision.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# J. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Dense move-by-move loss extraction — PILOT ONLY (Ticket 15.3B). "
                    "Capped by accepted-game count; no full-run path.")
    p.add_argument("--raw-pgn", required=True)
    p.add_argument("--month", required=True, help="e.g. 2024_09")
    p.add_argument("--version-tag", default=None,
                   help="for game_records/splits lookup; default {month}_250k_v1")
    p.add_argument("--max-accepted-games", type=int, default=PILOT_DEFAULT_MAX_GAMES)
    p.add_argument("--min-move-number", type=int, default=5)
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    p.add_argument("--stockfish-path", default=None)
    p.add_argument("--expected-score-transform", default=None)
    p.add_argument("--player-metadata", default=None)
    p.add_argument("--game-records", default=None)
    p.add_argument("--splits", default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--pilot-override-allow-large", action="store_true",
                   help=f"required to exceed the {PILOT_HARD_MAX_GAMES}-game pilot cap")
    p.add_argument("--timing-subtest-depth", type=int, default=None)
    p.add_argument("--timing-subtest-games", type=int, default=100)
    args = p.parse_args(argv)

    # --- hard safety: pilot cap, no full-run path ---
    if args.max_accepted_games <= 0:
        print("ERROR: --max-accepted-games must be a positive pilot cap.", file=sys.stderr)
        return 2
    if (args.max_accepted_games > PILOT_HARD_MAX_GAMES
            and not args.pilot_override_allow_large):
        print(f"ERROR: --max-accepted-games {args.max_accepted_games} exceeds the pilot "
              f"cap of {PILOT_HARD_MAX_GAMES}. This module is pilot-only and has no "
              "full-run mode. Pass --pilot-override-allow-large to raise the cap "
              "(still capped; not a full run).", file=sys.stderr)
        return 2

    out = Path(args.out)
    report = Path(args.report)
    if out.exists() and not args.overwrite:
        raise FileExistsError(f"{out} exists; pass --overwrite")

    version_tag = args.version_tag or f"{args.month}_250k_v1"
    es_scale = None
    if args.expected_score_transform:
        tp = Path(args.expected_score_transform)
        if tp.exists():
            es_scale = float(json.load(open(tp))["scale"])
            print(f"  [dense] ES transform scale={es_scale:.2f}", file=sys.stderr)
        else:
            print(f"  [dense] WARNING: ES transform {tp} missing; ES columns null",
                  file=sys.stderr)

    sf_path = resolve_stockfish_path(args.stockfish_path)
    sf_version = get_stockfish_version(sf_path)
    print(f"  [dense] Stockfish: {sf_version} ({sf_path}); depth={args.depth}",
          file=sys.stderr)

    accepted_meta = load_accepted_game_meta(version_tag, args.game_records, args.splits)
    print(f"  [dense] accepted 600+0 games available: {len(accepted_meta):,}; "
          f"pilot cap {args.max_accepted_games:,}", file=sys.stderr)

    rows, counters, failed = run_pilot(
        args.raw_pgn, args.month, accepted_meta, sf_path, args.depth,
        args.max_accepted_games, args.min_move_number, es_scale)

    df, coverage = finalize_frame(rows, args.player_metadata)
    summary = summarize(df, counters)

    subtest = None
    if args.timing_subtest_depth is not None:
        fens = [r["pre_fen"] for r in rows][: args.timing_subtest_games * 40]
        # cap the subtest to ~ timing_subtest_games games' worth of positions
        subtest = depth_timing_subtest(
            fens, sf_path, args.timing_subtest_depth,
            max_positions=min(len(fens), args.timing_subtest_games * 40))
        print(f"  [dense] timing subtest depth={args.timing_subtest_depth}: "
              f"{subtest.get('evals_per_second')} evals/s", file=sys.stderr)

    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out, compression="snappy")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(
        args.month, args.depth, args.min_move_number, args.max_accepted_games,
        counters, summary, failed, coverage, str(out), subtest, sf_version))

    print(f"  [dense] artifact: {out} ({df.height:,} rows)", file=sys.stderr)
    print(f"  [dense] report: {report}", file=sys.stderr)
    t = summary["throughput"]
    print(f"\n=== 15.3B dense pilot {args.month} ===")
    print(f"  games={counters['games_accepted']} rows={df.height} "
          f"evals={t['engine_evals']} reuse={t['eval_cache_hits']} "
          f"runtime={counters['runtime_s']}s eps={t['evals_per_second']}")
    if "es_loss" in summary:
        e = summary["es_loss"]
        print(f"  ES loss: mean={e['mean']} median={e['median']} p90={e['p90']} "
              f">=0.10={e['ge_0_10']}")
    if "full_run_extrapolation" in summary:
        f = summary["full_run_extrapolation"]
        print(f"  full-run extrapolation: ~{f['both_months_hours']}h both months @ depth {args.depth}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
