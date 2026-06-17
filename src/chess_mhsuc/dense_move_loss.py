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
from datetime import datetime, timezone
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
    # Time-control-aware fields (15.3C-A; forward-compatible — all 600+0 today).
    "time_control_raw":       pl.Utf8,
    "initial_time_s":         pl.Int64,
    "increment_s":            pl.Int64,
    "time_control_family":    pl.Utf8,
    "speed_category":         pl.Utf8,
    "clock_fraction":         pl.Float64,
    "increment_buffer":       pl.Float64,
    "think_time_gross_s":     pl.Float64,
    "think_time_net_s":       pl.Float64,
    "low_clock_absolute_flag": pl.Boolean,
    "low_clock_fraction_flag": pl.Boolean,
    "low_increment_buffer_flag": pl.Boolean,
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


# Low-clock thresholds (documented; constraint-state flags, not claims).
LOW_CLOCK_ABS_S = 60.0          # absolute remaining-clock low-state
LOW_CLOCK_FRACTION = 0.10       # relative (clock_before / initial_time) low-state
LOW_INCREMENT_BUFFER = 3.0      # remaining clock < this many increments (increment games)


def parse_time_control(tc_raw: str | None) -> tuple[int | None, int | None]:
    """Parse a PGN TimeControl string `initial+increment` -> (initial_s, increment_s).
    Returns (None, None) for missing/unparseable/`-` (correspondence/unlimited)."""
    if not tc_raw or tc_raw in ("-", "?"):
        return None, None
    try:
        if "+" in tc_raw:
            base, inc = tc_raw.split("+", 1)
            return int(base), int(inc)
        return int(tc_raw), 0
    except (ValueError, AttributeError):
        return None, None


def time_control_family_for(increment_s: int | None) -> str | None:
    if increment_s is None:
        return None
    return "no_increment" if increment_s == 0 else "increment"


def speed_category_for(initial_time_s: int | None, increment_s: int | None) -> str | None:
    """Lichess-style category by estimated duration = initial + 40*increment
    (ultrabullet folded into bullet; documented). 600+0 -> rapid."""
    if initial_time_s is None or increment_s is None:
        return None
    est = initial_time_s + 40 * increment_s
    if est < 180:
        return "bullet"
    if est < 480:
        return "blitz"
    if est < 1500:
        return "rapid"
    return "classical"


def clock_fraction_for(clock_before_s: float | None, initial_time_s: int | None) -> float | None:
    if clock_before_s is None or not initial_time_s:
        return None
    return clock_before_s / initial_time_s


def increment_buffer_for(clock_before_s: float | None, increment_s: int | None) -> float | None:
    """clock_before / increment for increment games; None for no-increment."""
    if clock_before_s is None or not increment_s:  # increment_s 0 or None -> None
        return None
    return clock_before_s / increment_s


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
        ["game_id", "result_class", "termination", "white_elo", "black_elo",
         "time_control"]
    ).iter_rows(named=True):
        gid = r["game_id"]
        meta[gid] = {
            "result_class": r["result_class"],
            "termination": r["termination"],
            "is_time_forfeit": r["termination"] == "Time forfeit",
            "white_elo": r["white_elo"],
            "black_elo": r["black_elo"],
            "time_control": r["time_control"],
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

    # Time-control-aware fields (forward-compatible; all 600+0 today).
    tc_raw = game_meta.get("time_control", "600+0")
    init_s, inc_s = parse_time_control(tc_raw)
    cb = rec["clock_before_s"]
    clk_frac = clock_fraction_for(cb, init_s)
    inc_buf = increment_buffer_for(cb, inc_s)
    tt_gross = rec["think_time_s"]                         # raw clock drop
    tt_net = (tt_gross + inc_s) if (tt_gross is not None and inc_s is not None) else None
    low_abs = (cb < LOW_CLOCK_ABS_S) if cb is not None else None
    low_frac = (clk_frac < LOW_CLOCK_FRACTION) if clk_frac is not None else None
    low_inc_buf = (inc_buf < LOW_INCREMENT_BUFFER) if inc_buf is not None else None

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
        "time_control_raw": tc_raw,
        "initial_time_s": init_s,
        "increment_s": inc_s,
        "time_control_family": time_control_family_for(inc_s),
        "speed_category": speed_category_for(init_s, inc_s),
        "clock_fraction": clk_frac,
        "increment_buffer": inc_buf,
        "think_time_gross_s": tt_gross,
        "think_time_net_s": tt_net,
        "low_clock_absolute_flag": low_abs,
        "low_clock_fraction_flag": low_frac,
        "low_increment_buffer_flag": low_inc_buf,
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
# F. Per-game extraction (shared by pilot + full-month chunked runners)
# ---------------------------------------------------------------------------

def extract_game_rows(
    engine: chess.engine.SimpleEngine,
    game: chess.pgn.Game,
    game_id: str,
    game_meta: dict,
    month: str,
    depth: int,
    min_move_number: int,
    es_scale: float | None,
    counters: dict,
) -> tuple[list[dict], str | None]:
    """Replay one game, evaluate its emitted positions (one eval per distinct
    pre-move FEN, post-move reused via per-game cache), and return
    (rows, replay_failure_reason). Updates engine/cache/terminal counters."""
    records, _fens, replay_fail = build_move_records(game, game_meta, min_move_number)
    cache: dict[str, dict] = {}
    rows: list[dict] = []
    t_eng = time.time()
    for rec in records:
        eb = eval_white_pov(engine, rec["pre_fen"], depth, cache, counters)
        ea = eval_white_pov(engine, rec["post_fen"], depth, cache, counters)
        rows.append(assemble_row(game_id, month, rec, game_meta, eb, ea, depth, es_scale))
    counters["engine_seconds"] += time.time() - t_eng
    return rows, replay_fail


# ---------------------------------------------------------------------------
# F2. Pilot extraction loop (capped; streams PGN in order)
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
                game_rows, replay_fail = extract_game_rows(
                    engine, game, gid, gmeta, month, depth, min_move_number,
                    es_scale, counters)
                if replay_fail is not None:
                    counters["games_replay_failed"] += 1
                    failed_games.append({"game_id": gid, "reason": replay_fail,
                                         "rows_kept": len(game_rows)})
                rows.extend(game_rows)

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
# F3. Full-month chunked, resumable extraction
# ---------------------------------------------------------------------------

def _chunk_path(chunk_dir: Path, idx: int) -> Path:
    return chunk_dir / f"chunk_{idx:04d}.parquet"


def completed_game_ids_from_chunks(chunk_dir: Path) -> tuple[set[str], int]:
    """Source-of-truth resume state: union of game_ids already in chunk files, and
    the next chunk index (== number of existing chunk_*.parquet files)."""
    chunks = sorted(chunk_dir.glob("chunk_*.parquet"))
    done: set[str] = set()
    for cf in chunks:
        done |= set(pl.read_parquet(cf, columns=["game_id"])["game_id"].to_list())
    return done, len(chunks)


def run_full_month_chunked(
    raw_pgn: str,
    month: str,
    accepted_meta: dict[str, dict],
    stockfish_path: str,
    depth: int,
    min_move_number: int,
    es_scale: float | None,
    chunk_size: int,
    chunk_dir: str | Path,
    player_metadata_path: str | Path | None,
    resume: bool,
    progress_every: int = 500,
) -> tuple[dict, list[dict], list[Path]]:
    """
    Stream the full month, evaluating EVERY accepted game (no game cap), flushing a
    finalized chunk parquet every ``chunk_size`` processed games. Resumable: on
    ``resume`` it skips game_ids already present in completed chunk files and
    continues chunk numbering. Returns (counters, failed_games, chunk_files).
    """
    chunk_dir = Path(chunk_dir)
    chunk_dir.mkdir(parents=True, exist_ok=True)

    completed_ids: set[str] = set()
    next_chunk_idx = 0
    if resume:
        completed_ids, next_chunk_idx = completed_game_ids_from_chunks(chunk_dir)
        if completed_ids:
            print(f"  [dense] resume: {len(completed_ids):,} games already in "
                  f"{next_chunk_idx} chunk(s); skipping them", file=sys.stderr)

    counters = {
        "games_scanned": 0, "games_accepted": 0, "games_skipped_resume": 0,
        "games_replay_failed": 0, "engine_evals": 0, "eval_cache_hits": 0,
        "terminal_positions": 0, "rows": 0, "engine_seconds": 0.0,
        "accepted_available": len(accepted_meta),
    }
    failed_games: list[dict] = []
    buffer_rows: list[dict] = []
    games_in_buffer = 0

    def _flush(idx: int) -> Path:
        frame, _cov = finalize_frame(buffer_rows, player_metadata_path)
        path = _chunk_path(chunk_dir, idx)
        frame.write_parquet(path, compression="snappy")
        print(f"  [dense] wrote {path.name} ({frame.height:,} rows)", file=sys.stderr)
        return path

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    t0 = time.time()
    try:
        for stream in open_pgn_stream(raw_pgn):
            while True:
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
                if gid in completed_ids:
                    counters["games_skipped_resume"] += 1
                    continue

                gmeta = accepted_meta[gid]
                game_rows, replay_fail = extract_game_rows(
                    engine, game, gid, gmeta, month, depth, min_move_number,
                    es_scale, counters)
                if replay_fail is not None:
                    counters["games_replay_failed"] += 1
                    failed_games.append({"game_id": gid, "reason": replay_fail,
                                         "rows_kept": len(game_rows)})
                buffer_rows.extend(game_rows)
                games_in_buffer += 1
                counters["games_accepted"] += 1

                if games_in_buffer >= chunk_size:
                    _flush(next_chunk_idx)
                    next_chunk_idx += 1
                    buffer_rows.clear()
                    games_in_buffer = 0

                if (progress_every and counters["games_accepted"]
                        and counters["games_accepted"] % progress_every == 0):
                    print(f"  [dense] processed {counters['games_accepted']:,} games "
                          f"| evals={counters['engine_evals']:,} "
                          f"| chunk={next_chunk_idx}", file=sys.stderr)
            break  # only the first stream context is needed
        if buffer_rows:
            _flush(next_chunk_idx)
            next_chunk_idx += 1
    finally:
        engine.quit()

    counters["runtime_s"] = round(time.time() - t0, 1)
    counters["engine_seconds"] = round(counters["engine_seconds"], 1)
    chunk_files = sorted(chunk_dir.glob("chunk_*.parquet"))
    counters["n_chunks"] = len(chunk_files)
    return counters, failed_games, chunk_files


def concatenate_chunks(chunk_files: list[Path], out_path: str | Path) -> pl.DataFrame:
    """Concatenate finalized chunk parquets into the final month artifact."""
    if not chunk_files:
        raise ValueError("no chunk files to concatenate")
    frame = pl.concat([pl.read_parquet(cf) for cf in chunk_files], how="vertical")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(out_path, compression="snappy")
    return frame


def write_chunk_manifest(
    chunk_dir: Path, chunk_files: list[Path], month: str, depth: int,
    chunk_size: int, counters: dict,
) -> Path:
    """Write a human-readable chunk manifest (gitignored under data/)."""
    manifest = {
        "month": month, "depth": depth, "chunk_size": chunk_size,
        "n_chunks": len(chunk_files),
        "chunk_files": [cf.name for cf in chunk_files],
        "games_accepted": counters.get("games_accepted"),
        "games_skipped_resume": counters.get("games_skipped_resume"),
        "rows_total": counters.get("rows"),
        "engine_evals": counters.get("engine_evals"),
        "written_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    path = chunk_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


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
    s["rows_by_result_class"] = _counts("result_class")

    # clock/think anomaly detail (flagged, never dropped)
    s["clock_over_start_rows"] = int(
        df.filter((pl.col("clock_before_s") > _TEN_ZERO_START_S)
                  | (pl.col("clock_after_s") > _TEN_ZERO_START_S)).height)
    s["negative_think_rows"] = int(df.filter(pl.col("think_time_s") < 0).height)

    # time-control-aware schema validation (10+0 should be uniform)
    if df.height:
        s["time_control"] = {
            "time_control_raw": _counts("time_control_raw"),
            "initial_time_s": _counts("initial_time_s"),
            "increment_s": _counts("increment_s"),
            "time_control_family": _counts("time_control_family"),
            "speed_category": _counts("speed_category"),
            "clock_fraction_min": round(float(df["clock_fraction"].min()), 4)
                if df["clock_fraction"].drop_nulls().len() else None,
            "clock_fraction_max": round(float(df["clock_fraction"].max()), 4)
                if df["clock_fraction"].drop_nulls().len() else None,
            "increment_buffer_null_share": round(
                df["increment_buffer"].null_count() / df.height, 4),
            "low_increment_buffer_flag_null_share": round(
                df["low_increment_buffer_flag"].null_count() / df.height, 4),
        }

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
        raw = sorted(v for v in ok_nonmate["cp_loss_raw"].to_list() if v is not None)
        if raw:
            s["cp_loss_raw"] = {
                "n": len(raw), "min": int(raw[0]), "max": int(raw[-1]),
                "mean": round(statistics.mean(raw), 1),
                "median": float(statistics.median(raw)),
                "p90": _pctile([float(x) for x in raw], 0.90),
                "negative_share": round(sum(1 for x in raw if x < 0) / len(raw), 4),
            }
        # both-color orientation sanity (means/medians should be close)
        s["by_color"] = {}
        for col in ("white", "black"):
            sub = ok_nonmate.filter(pl.col("mover_color") == col)
            if sub.height:
                s["by_color"][col] = {
                    "n": sub.height,
                    "es_mean": round(float(sub["expected_score_loss"].mean()), 4),
                    "es_median": round(float(sub["expected_score_loss"].median()), 4),
                    "cp_mean": round(float(sub["cp_loss_clipped"].mean()), 1),
                    "cp_median": float(sub["cp_loss_clipped"].median()),
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


# Published, validated 2024-09 full-dense stats (15.3C / EXP-041) — used as the
# replication baseline so the 2024-10 report does not re-read the 156 MB artifact.
_M_2024_09_STATS = {
    "rows": 1_496_890, "rows_per_game": 58.4, "mate_band_share": 0.054,
    "es_mean": 0.0346, "es_median": 0.0114, "es_p90": 0.0926,
    "es_ge_0_05": 0.20, "es_ge_0_10": 0.0903,
    "cp_ge_100": 0.175, "cp_ge_200": 0.072,
}


def _compare_to_2024_09(summary: dict) -> str:
    """Markdown comparison block: 2024-10 (live summary) vs the published 2024-09
    full-dense baseline."""
    b = _M_2024_09_STATS
    e = summary.get("es_loss", {})
    rows = summary.get("rows", 0)
    games = summary.get("unique_games", 0)
    rpg = round(rows / games, 1) if games else None
    mb = round(summary.get("rows_mate_band", 0) / rows, 3) if rows else None
    L = [
        "| Metric | 2024-09 | 2024-10 |",
        "|---|---|---|",
        f"| Rows | {b['rows']:,} | {rows:,} |",
        f"| Rows/game | {b['rows_per_game']} | {rpg} |",
        f"| Mate-band share | {b['mate_band_share']} | {mb} |",
        f"| ES loss mean | {b['es_mean']} | {e.get('mean')} |",
        f"| ES loss median | {b['es_median']} | {e.get('median')} |",
        f"| ES loss p90 | {b['es_p90']} | {e.get('p90')} |",
        f"| ES >= 0.10 | {b['es_ge_0_10']} | {e.get('ge_0_10')} |",
    ]
    return "\n".join(L)


def render_full_month_report(
    month: str, depth: int, chunk_size: int, counters: dict, summary: dict,
    failed_games: list[dict], coverage: dict, out_path: str, chunk_dir: str,
    sf_version: str, preflight: dict | None,
    compare_block: str | None = None, next_recommendation: str | None = None,
) -> str:
    s = summary
    t = s["throughput"]
    L: list[str] = []
    a = L.append
    a(f"# Dense Move Loss — {month.replace('_', '-')} Full 10+0 Extraction")
    a("")
    a("**Ticket:** 15.3C — Full Dense Move-by-Move Loss Extraction (2024-09 only)")
    a(f"**Engine:** {sf_version} @ depth {depth}")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Full dense per-ply next-move loss extraction for **{month.replace('_', '-')} "
      f"10+0 (600+0) only** — every accepted game, both colors, move_number >= "
      f"{summary.get('min_move_number', 5)}. {counters['games_accepted']:,} accepted "
      f"games processed → **{s['rows']:,} per-ply rows** in {t['engine_evals']:,} "
      "engine evals. One Stockfish eval per pre-move position (Option A); post-move "
      "eval reused. Primary metric: expected-score loss, mover perspective; secondary: "
      "clipped centipawn loss. **2024-10 has NOT been run; no visual atlas; no dense "
      "controlled model.** Predictive/descriptive only — not causal, not a degradation "
      "curve; Stockfish eval is objective context, not absolute ground truth.")
    a("")
    a("## 2. Extraction scope")
    a(f"- Month: {month} (10+0 / 600+0 only). Depth {depth}. Both colors, "
      f"move_number >= {summary.get('min_move_number', 5)}.")
    a(f"- Accepted 600+0 games available: {counters.get('accepted_available', 'NA'):,}; "
      f"processed: {counters['games_accepted']:,}.")
    a("- Eval strategy: Option A (one eval per pre-move position; post-move reused).")
    a("")
    a("## 3. Command and environment")
    a(f"- Stockfish: {sf_version}; depth {depth}; ES transform scale reused (not refit).")
    a("- Run under `caffeinate -dimsu` (machine-awake); chunked + resumable.")
    a("")
    a("## 4. Chunking and resumability")
    a(f"- Chunk size: {chunk_size:,} accepted games/chunk; chunks: {counters.get('n_chunks')}.")
    a(f"- Chunk dir: `{chunk_dir}` (gitignored). Games skipped on resume: "
      f"{counters.get('games_skipped_resume', 0):,}.")
    a("- Final artifact = vertical concat of chunk parquets; chunks retained (no auto-delete).")
    a("")
    a("## 5. Runtime and throughput")
    a(f"- Wall-clock: {t['runtime_s']} s; engine seconds: {t['engine_seconds']} s.")
    a(f"- Engine evals: {t['engine_evals']:,}; cache reuse: {t['eval_cache_hits']:,}; "
      f"terminal: {t['terminal_positions']:,}.")
    a(f"- Throughput: {t['evals_per_second']} evals/s.")
    a("")
    a("## 6. Preflight reproduction")
    if preflight:
        a(f"- Preflight (first 1,500 games): rows {preflight['rows']} "
          f"(target 86,977), games {preflight['games']} (target 1,486), "
          f"evals {preflight['evals']} (target 88,012) → **{preflight['verdict']}**.")
    else:
        a("- (preflight run separately before this extraction; see phase report.)")
    a("")
    a("## 7. Replay validation")
    a(f"- Rows: {s['rows']:,}; unique games: {s['unique_games']:,}; "
      f"duplicate (game_id, ply) keys: {s['duplicate_key_count']}.")
    a(f"- Replay failures (partial rows kept): {counters['games_replay_failed']}.")
    a("")
    a("## 8. Evaluation validation")
    a(f"- OK rows: {s['rows_ok']:,}; eval-error rows: {s['rows_eval_error']}; "
      f"mate-band (flagged, excluded from headline): {s['rows_mate_band']:,}.")
    if "cp_loss_raw" in s:
        a(f"- raw cp loss negative share: {s['cp_loss_raw']['negative_share']} "
          "(actual move beat prior static eval; expected).")
    a("")
    a("## 9. Clock and think-time validation")
    a(f"- Missing-clock rows: {s['missing_clock_rows']}; clock-anomaly (no bucket): "
      f"{s['clock_anomaly_rows']}; think-anomaly (no bucket): {s['think_anomaly_rows']}.")
    a(f"- clock > start (600 s) rows: {s['clock_over_start_rows']}; negative think-time "
      f"rows: {s['negative_think_rows']} (flagged, not dropped).")
    a("")
    a("## 10. Time-control-aware schema validation")
    if "time_control" in s:
        tc = s["time_control"]
        a(f"- time_control_raw: {tc['time_control_raw']}")
        a(f"- initial_time_s: {tc['initial_time_s']}; increment_s: {tc['increment_s']}; "
          f"family: {tc['time_control_family']}; speed: {tc['speed_category']}.")
        a(f"- clock_fraction range: [{tc['clock_fraction_min']}, {tc['clock_fraction_max']}].")
        a(f"- increment_buffer null share: {tc['increment_buffer_null_share']} "
          f"(1.0 expected for 10+0); low_increment_buffer_flag null share: "
          f"{tc['low_increment_buffer_flag_null_share']}.")
    a("")
    a("## 11. Row schema validation")
    a(f"- No raw-username columns: {s['no_username_cols']}; columns: "
      f"{len(_OUTPUT_SCHEMA) + len(_HASH_COLS)} (typed schema + player hashes).")
    a("")
    a("## 12. Loss metric summary")
    if "es_loss" in s:
        e = s["es_loss"]
        a(f"- ES loss (OK, non-mate, n={e['n']:,}): mean {e['mean']} | median {e['median']} "
          f"| p90 {e['p90']} | zero share {e['zero_share']}.")
    if "cp_loss_clipped" in s:
        c = s["cp_loss_clipped"]
        a(f"- clipped cp loss: mean {c['mean']} | median {c['median']} | p90 {c['p90']}.")
    if "by_color" in s and s["by_color"]:
        bc = s["by_color"]
        a(f"- Both-color orientation: White ES mean {bc.get('white', {}).get('es_mean')} / "
          f"Black ES mean {bc.get('black', {}).get('es_mean')} (close ⇒ sign correct).")
    a("")
    a("## 13. Large-loss rates")
    if "es_loss" in s:
        e = s["es_loss"]
        a(f"- ES loss >= 0.05: {e['ge_0_05']} | >= 0.10: {e['ge_0_10']}.")
    if "cp_loss_clipped" in s:
        c = s["cp_loss_clipped"]
        a(f"- clipped cp >= 100: {c['ge_100']} | >= 200: {c['ge_200']}.")
    a("")
    a("## 14. Coverage by color / phase / eval / clock / rating")
    a(f"- mover color: {s['rows_by_mover_color']}")
    a(f"- phase: {s['rows_by_phase']}")
    a(f"- eval band: {s['rows_by_eval_band']}")
    a(f"- clock bucket: {s['rows_by_clock_bucket']}")
    a(f"- result class: {s['rows_by_result_class']}")
    a(f"- rating bucket: {s['rows_by_rating_bucket']}")
    a("")
    a("## 15. Player-hash coverage and privacy")
    if coverage.get("available"):
        a(f"- mover_player_hash match fraction: {coverage['match_fraction']} "
          f"({coverage['n_matched']:,}/{coverage['n_rows']:,}); one-way hashes only; "
          "no raw usernames written.")
    else:
        a("- player metadata not provided; hash columns null.")
    a("")
    if compare_block:
        a("## 16. Comparison to 2024-09 full dense extraction")
        a(compare_block)
        a("")
        a("Both months use the identical pipeline and the same train-fit ES transform; "
          "matching per-row distributions are the cross-month replication check.")
    else:
        a("## 16. Comparison to 15.3B pilot")
        a("- 15.3B pilot (first 1,500 games): 86,977 rows, 88,012 evals, ES mean 0.0347, "
          "median 0.0115. This full-month run extends the same pipeline to all accepted "
          "games; per-row distributions are expected to be consistent with the pilot.")
    a("")
    a("## 17. Known limitations")
    if month == "2024_10":
        a("- 2024-10 10+0 only; this completes the SECOND 10+0 anchor month (with "
          "2024-09); no cross-time-control data; no other time controls extracted.")
    else:
        a("- 2024-09 10+0 only; the 2024-10 replication month is a separate run; "
          "no cross-time-control data.")
    a("- No visual atlas; no dense controlled model.")
    a("- Depth-parity (mover-to-move vs opponent-to-move, same depth) acknowledged "
      "(15.0C benign); re-check recommended.")
    a("- Mate-band rows flagged and excluded from headline; loss right-skewed "
      "(medians/percentiles reported with means).")
    a("- No pre-move trajectory / prior-quality control (stated limitation).")
    a("- Stockfish eval is objective context, not absolute ground truth; "
      "predictive/descriptive, not causal.")
    a("")
    a("## 18. Recommendation for next step")
    a(f"- Artifact: `{out_path}` (gitignored under `data/`; not staged).")
    if next_recommendation:
        a(f"- {next_recommendation}")
    else:
        a("- Recommend **15.3D — Full Dense Move-by-Move Loss Extraction Replication Month "
          "(2024-10)** before any dense atlas, so final claims use both monthly samples.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# J. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Dense move-by-move loss extraction. Default = capped pilot "
                    "(15.3B). --allow-full-month-2024-09 runs the approved full 2024-09 "
                    "10+0 depth-12 extraction (chunked/resumable); no other month or "
                    "depth is permitted through that flag.")
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
    # --- 15.3C full-month / chunking / preflight ---
    p.add_argument("--time-control", default=None,
                   help="full-month mode requires 600+0 (or unset)")
    p.add_argument("--allow-full-month-2024-09", dest="allow_full_month_2024_09",
                   action="store_true",
                   help="run the FULL 2024-09 10+0 dense extraction (no game cap); "
                        "restricted to month==2024_09, depth==12, 600+0")
    p.add_argument("--allow-full-month-2024-10", dest="allow_full_month_2024_10",
                   action="store_true",
                   help="run the FULL 2024-10 10+0 dense extraction (no game cap); "
                        "restricted to month==2024_10, depth==12, 600+0")
    p.add_argument("--chunk-size", type=int, default=5000)
    p.add_argument("--chunk-dir", default=None)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--cleanup-chunks", action="store_true",
                   help="delete chunk files AFTER a successful concatenation")
    p.add_argument("--preflight", action="store_true",
                   help="reproduce the 15.3B 1,500-game pilot counts and exit")
    args = p.parse_args(argv)

    # --- full-month safety gate (must be evaluated before any pilot-cap logic) ---
    # Each month-specific flag is restricted to its own month; there is no
    # both-month / all-month path. Supported full-month combos: 2024_09 and
    # 2024_10, each at depth 12 and 600+0 only.
    full_month_flag_month = None
    if args.allow_full_month_2024_09 and args.allow_full_month_2024_10:
        print("ERROR: cannot set both --allow-full-month-2024-09 and "
              "--allow-full-month-2024-10; there is no both-month mode. Run each month "
              "separately.", file=sys.stderr)
        return 2
    if args.allow_full_month_2024_09:
        full_month_flag_month = "2024_09"
    elif args.allow_full_month_2024_10:
        full_month_flag_month = "2024_10"

    is_full_month = full_month_flag_month is not None
    if is_full_month:
        if args.month != full_month_flag_month:
            print(f"ERROR: --allow-full-month-{full_month_flag_month.replace('_', '-')} is "
                  f"restricted to month=={full_month_flag_month}; got {args.month!r}. Use "
                  "the flag that matches the requested month.", file=sys.stderr)
            return 2
        if args.depth != 12:
            print(f"ERROR: full-month mode is locked to depth 12 (continuity with the "
                  f"depth-12 ES transform); got depth {args.depth}.", file=sys.stderr)
            return 2
        if args.time_control not in (None, "600+0"):
            print(f"ERROR: full-month mode is restricted to 600+0; got "
                  f"{args.time_control!r}.", file=sys.stderr)
            return 2

    # --- pilot-cap safety (only when NOT full-month and NOT preflight) ---
    if not is_full_month and not args.preflight:
        if args.max_accepted_games <= 0:
            print("ERROR: --max-accepted-games must be a positive pilot cap.", file=sys.stderr)
            return 2
        if (args.max_accepted_games > PILOT_HARD_MAX_GAMES
                and not args.pilot_override_allow_large):
            print(f"ERROR: --max-accepted-games {args.max_accepted_games} exceeds the pilot "
                  f"cap of {PILOT_HARD_MAX_GAMES}. Use --allow-full-month-2024-09 / "
                  "--allow-full-month-2024-10 for an approved full month run, or "
                  "--pilot-override-allow-large to raise the pilot cap (still capped).",
                  file=sys.stderr)
            return 2

    # --- common setup ---
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
    print(f"  [dense] accepted 600+0 games available: {len(accepted_meta):,}",
          file=sys.stderr)

    # =====================================================================
    # MODE: preflight — reproduce the 15.3B 1,500-game pilot counts, then exit
    # =====================================================================
    if args.preflight:
        rows, counters, failed = run_pilot(
            args.raw_pgn, args.month, accepted_meta, sf_path, args.depth,
            PILOT_DEFAULT_MAX_GAMES, args.min_move_number, es_scale)
        df, _cov = finalize_frame(rows, args.player_metadata)
        n_rows = df.height
        n_games = int(df["game_id"].n_unique())
        n_evals = counters["engine_evals"]
        dups = df.height - df.select(_KEY).unique().height
        colors = set(df["mover_color"].unique().to_list())
        tc_ok = (df["time_control_raw"].unique().to_list() == ["600+0"]
                 and df["initial_time_s"].unique().to_list() == [600]
                 and df["increment_s"].unique().to_list() == [0])
        no_user = not ({"white", "black", "White", "Black"} & set(df.columns))
        hash_full = df.filter(pl.col("mover_player_hash").is_null()).height == 0
        print(f"\n=== preflight {args.month} (first {PILOT_DEFAULT_MAX_GAMES} games) ===")
        if args.month == "2024_09":
            # exact reproduction of the 15.3B pilot
            ok = (n_rows == 86977 and n_games == 1486)
            print(f"  rows={n_rows} (target 86977) | games={n_games} (target 1486) | "
                  f"evals={n_evals} (target 88012) | replay_fail="
                  f"{counters['games_replay_failed']} dups={dups} -> "
                  f"{'PASS' if ok else 'MISMATCH'}")
        else:
            # broad sanity for a new month (no exact target)
            ok = (80_000 <= n_rows <= 110_000 and counters["games_replay_failed"] == 0
                  and counters.get("engine_evals", 0) > 0 and dups == 0
                  and colors == {"white", "black"} and tc_ok and no_user and hash_full
                  and df.filter(pl.col("status") != _STATUS_OK).height == 0)
            print(f"  rows={n_rows} (~80k-100k expected) | games={n_games} | "
                  f"evals={n_evals} | replay_fail={counters['games_replay_failed']} | "
                  f"dups={dups} | colors={sorted(colors)} | tc_600_0={tc_ok} | "
                  f"hash_full={hash_full} | no_username={no_user} -> "
                  f"{'PASS' if ok else 'FAIL'}")
        if not ok:
            print("  ERROR: preflight did not pass; investigate before the full run.",
                  file=sys.stderr)
            return 3
        return 0

    # =====================================================================
    # MODE: full-month dense extraction (chunked, resumable) — 2024_09 / 2024_10
    # =====================================================================
    if is_full_month:
        out = Path(args.out)
        report = Path(args.report)
        if out.exists() and not args.overwrite and not args.resume:
            raise FileExistsError(f"{out} exists; pass --overwrite or --resume")
        chunk_dir = Path(args.chunk_dir
                         or f"data/processed/dense_move_loss_{version_tag}_chunks")
        print(f"  [dense] FULL-MONTH {args.month}: ~{len(accepted_meta):,} games, "
              f"depth {args.depth}, chunk_size {args.chunk_size}, chunk_dir {chunk_dir}",
              file=sys.stderr)

        counters, failed, chunk_files = run_full_month_chunked(
            args.raw_pgn, args.month, accepted_meta, sf_path, args.depth,
            args.min_move_number, es_scale, args.chunk_size, chunk_dir,
            args.player_metadata, args.resume)

        df = concatenate_chunks(chunk_files, out)
        counters["rows"] = df.height
        write_chunk_manifest(chunk_dir, chunk_files, args.month, args.depth,
                             args.chunk_size, counters)

        # coverage from final frame
        matched = int(df.filter(pl.col("mover_player_hash").is_not_null()).height)
        coverage = {"available": args.player_metadata is not None,
                    "n_rows": df.height, "n_matched": matched,
                    "match_fraction": round(matched / df.height, 4) if df.height else 0.0}
        summary = summarize(df, counters)
        summary["min_move_number"] = args.min_move_number

        # 2024-10 replication: compare to the 2024-09 full artifact + recommend 15.4A
        compare_block = None
        next_recommendation = None
        if args.month == "2024_10":
            compare_block = _compare_to_2024_09(summary)
            next_recommendation = (
                "Recommend **15.4A — CP/ES Constraint Atlas Visualization Audit**: both "
                "10+0 anchor months (2024-09 + 2024-10) now have full dense artifacts, so "
                "the dense visual atlas can be designed (then implemented in 15.4B). Do not "
                "skip the 15.4A audit.")

        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(render_full_month_report(
            args.month, args.depth, args.chunk_size, counters, summary, failed,
            coverage, str(out), str(chunk_dir), sf_version, preflight=None,
            compare_block=compare_block, next_recommendation=next_recommendation))

        if args.cleanup_chunks:
            for cf in chunk_files:
                cf.unlink()
            print(f"  [dense] cleaned up {len(chunk_files)} chunk files", file=sys.stderr)

        t = summary["throughput"]
        print(f"\n=== full dense {args.month} ===")
        print(f"  games={counters['games_accepted']} rows={df.height} "
              f"chunks={counters.get('n_chunks')} evals={t['engine_evals']} "
              f"runtime={counters['runtime_s']}s eps={t['evals_per_second']}")
        if "es_loss" in summary:
            e = summary["es_loss"]
            print(f"  ES loss: mean={e['mean']} median={e['median']} p90={e['p90']} "
                  f">=0.10={e['ge_0_10']}")
        print(f"  artifact: {out} | report: {report}")
        return 0

    # =====================================================================
    # MODE: pilot (default; capped)
    # =====================================================================
    out = Path(args.out)
    report = Path(args.report)
    if out.exists() and not args.overwrite:
        raise FileExistsError(f"{out} exists; pass --overwrite")
    print(f"  [dense] pilot cap {args.max_accepted_games:,}", file=sys.stderr)

    rows, counters, failed = run_pilot(
        args.raw_pgn, args.month, accepted_meta, sf_path, args.depth,
        args.max_accepted_games, args.min_move_number, es_scale)

    df, coverage = finalize_frame(rows, args.player_metadata)
    summary = summarize(df, counters)

    subtest = None
    if args.timing_subtest_depth is not None:
        fens = [r["pre_fen"] for r in rows][: args.timing_subtest_games * 40]
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
