"""
parse_pgn.py — single-game PGN parser for chess-MHSUC.

Parses one chess.pgn.Game object at a time. Does NOT handle data acquisition,
streaming, cleaning, feature engineering, or dataset writing.

Entry point:
    game_record, position_records = parse_game(game, source_file="lichess_...pgn.zst")

See schemas.py for field definitions and eval/clock conventions.
"""

import re
from urllib.parse import urlparse

import chess
import chess.pgn

from chess_mhsuc.schemas import (
    CHECKPOINT_PLIES,
    MATE_CP_SENTINEL,
    PHASE_ENDGAME,
    PHASE_MIDDLEGAME,
    PHASE_OPENING,
    REJECT_INVALID_ELO,
    REJECT_INVALID_RESULT,
    REJECT_MISSING_CLOCK,
    REJECT_VARIANT,
    REJECT_WRONG_TC,
    RESULT_BLACK_WIN,
    RESULT_DRAW,
    RESULT_WHITE_WIN,
    TIME_CONTROL_TARGET,
    GameRecord,
    PlyRecord,
    PositionRecord,
)

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

_CLK_RE = re.compile(r'\[%clk\s+(\d+:\d{2}:\d{2})\]')
_EVAL_RE = re.compile(r'\[%eval\s+([^\]]+)\]')
_MATE_TOKEN_RE = re.compile(r'^#(-?\d+)$')
_MONTH_RE = re.compile(r'(\d{4}-\d{2})')

_VALID_RESULTS = {"1-0", "0-1", "1/2-1/2"}


# ---------------------------------------------------------------------------
# Primitive parsers
# ---------------------------------------------------------------------------

def parse_int(value: str | None) -> int | None:
    """Parse a string to int. Returns None on failure or if value is '?'."""
    if not value or value == "?":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_rating_diff(value: str | None) -> int | None:
    """
    Parse a signed rating-diff string such as '+12', '-5', or '0'.
    Python's int() handles leading '+' signs natively.
    Returns None on failure.
    """
    if not value or value == "?":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def parse_result(
    headers: chess.pgn.Headers,
) -> tuple[str | None, str | None, float | None]:
    """
    Map the raw Result header to (result_raw, result_class, white_result_numeric).

    Returns (None, None, None) for absent or unrecognised results.
    """
    raw = headers.get("Result", "")
    if raw == "1-0":
        return "1-0", RESULT_WHITE_WIN, 1.0
    if raw == "0-1":
        return "0-1", RESULT_BLACK_WIN, 0.0
    if raw == "1/2-1/2":
        return "1/2-1/2", RESULT_DRAW, 0.5
    return None, None, None


def parse_game_id(site: str | None) -> str | None:
    """
    Extract the game ID from a Lichess Site URL.

    Example: "https://lichess.org/abcd1234" → "abcd1234"
    Returns None if site is absent or unparseable.
    """
    if not site:
        return None
    try:
        path = urlparse(site).path
        segment = path.strip("/").split("/")[-1]
        return segment if segment else None
    except Exception:
        return None


def parse_source_month(source_file: str | None) -> str | None:
    """
    Extract the YYYY-MM month string from a Lichess archive filename.

    Example: "lichess_db_standard_rated_2024-09.pgn.zst" → "2024-09"
    Returns None if not parseable.
    """
    if not source_file:
        return None
    m = _MONTH_RE.search(source_file)
    return m.group(1) if m else None


def parse_clock_seconds(clock_str: str | None) -> int | None:
    """
    Parse a clock string in 'H:MM:SS' format to integer seconds.

    Examples:
        "0:10:00" → 600
        "0:09:53" → 593
        "0:00:01" → 1
        "0:00:00" → 0
        None or "" → None
    """
    if not clock_str:
        return None
    try:
        parts = clock_str.strip().split(":")
        if len(parts) != 3:
            return None
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return None


def parse_eval_comment(
    comment: str,
    side_to_move_next: str,
) -> tuple[int | None, int | None, str | None]:
    """
    Parse the %eval annotation from a ply comment string.

    Parameters
    ----------
    comment
        The full comment string attached to a ply node.
    side_to_move_next
        "white" or "black" — the side that moves next from this position.
        Required to convert Lichess's "side-to-move" mate convention to White POV.

    Returns
    -------
    (eval_cp, eval_mate, raw_eval)
        eval_cp   : centipawns White-POV, ±MATE_CP_SENTINEL for forced mate, None if absent
        eval_mate : mate distance White-POV (+ = White wins, − = Black wins), None if not mate
        raw_eval  : the raw token string (e.g. "0.47", "#3", "#-2"), None if absent

    Eval conventions
    ----------------
    Decimal eval (e.g. [%eval 0.47]):
        eval_cp = round(0.47 * 100) = 47, eval_mate = None

    Mate token [%eval #N] (N > 0 → side to move has forced mate):
        side_to_move_next == "white":  White wins → eval_cp = +10000, eval_mate = +N
        side_to_move_next == "black":  Black wins → eval_cp = -10000, eval_mate = -N

    Mate token [%eval #-N] (N > 0 → opponent has forced mate):
        side_to_move_next == "white":  Black wins → eval_cp = -10000, eval_mate = -N
        side_to_move_next == "black":  White wins → eval_cp = +10000, eval_mate = +N
    """
    m = _EVAL_RE.search(comment)
    if not m:
        return None, None, None

    raw = m.group(1).strip()
    mate_m = _MATE_TOKEN_RE.match(raw)

    if mate_m:
        n = int(mate_m.group(1))
        # n > 0: side to move has mate in n; n < 0: opponent has mate in abs(n)
        if n > 0:
            if side_to_move_next == "white":
                return MATE_CP_SENTINEL, n, raw
            else:
                return -MATE_CP_SENTINEL, -n, raw
        else:
            # n is already negative: abs(n) = -n
            if side_to_move_next == "white":
                return -MATE_CP_SENTINEL, n, raw
            else:
                return MATE_CP_SENTINEL, -n, raw
    else:
        try:
            val = float(raw)
            cp = round(val * 100)
            return cp, None, raw
        except ValueError:
            return None, None, raw


def phase_for_move(move_number: int) -> str:
    """
    Return the game phase for a given full-move number.

    Opening:    move_number <= 10
    Middlegame: 11 <= move_number <= 35
    Endgame:    move_number > 35

    This is the v1 approximation defined in PIPELINE_OVERVIEW.md §8.
    Material-based phase detection is deferred to a later ticket.
    """
    if move_number <= 10:
        return PHASE_OPENING
    if move_number <= 35:
        return PHASE_MIDDLEGAME
    return PHASE_ENDGAME


# ---------------------------------------------------------------------------
# Game-level record extraction
# ---------------------------------------------------------------------------

def _scan_main_line(game: chess.pgn.Game) -> tuple[int, bool, bool]:
    """
    Walk the main line once to count plies and detect clock/eval annotations.

    Returns (n_plies, has_clock, has_eval).
    """
    n = 0
    has_clk = False
    has_ev = False
    node = game
    while node.variations:
        node = node.variations[0]
        n += 1
        c = node.comment
        if not has_clk and "%clk" in c:
            has_clk = True
        if not has_ev and "%eval" in c:
            has_ev = True
    return n, has_clk, has_ev


def extract_game_record(
    game: chess.pgn.Game,
    source_file: str | None = None,
) -> GameRecord:
    """
    Build a GameRecord from a parsed chess.pgn.Game object.

    Determines acceptance status and rejection reason.
    Does NOT retain username fields (White, Black).
    """
    headers = game.headers

    # --- Header fields ---
    site = headers.get("Site")
    game_id = parse_game_id(site)
    source_month = parse_source_month(source_file)
    utc_date = headers.get("UTCDate") or None
    utc_time = headers.get("UTCTime") or None
    time_control = headers.get("TimeControl") or None
    termination = headers.get("Termination") or None
    event = headers.get("Event") or None
    variant = headers.get("Variant") or None

    result_raw, result_class, white_result_numeric = parse_result(headers)

    white_elo_raw = headers.get("WhiteElo")
    black_elo_raw = headers.get("BlackElo")
    white_elo = parse_int(white_elo_raw)
    black_elo = parse_int(black_elo_raw)

    # Enforce > 0 (Elo of 0 is invalid)
    if white_elo is not None and white_elo <= 0:
        white_elo = None
    if black_elo is not None and black_elo <= 0:
        black_elo = None

    elo_diff = (white_elo - black_elo
                if white_elo is not None and black_elo is not None
                else None)

    white_rating_diff = parse_rating_diff(headers.get("WhiteRatingDiff"))
    black_rating_diff = parse_rating_diff(headers.get("BlackRatingDiff"))

    # --- Scan main line ---
    n_plies, has_clock, has_eval = _scan_main_line(game)

    # --- Determine acceptance (priority order from Ticket 2.1A) ---
    variant_ok = variant is None or variant == "Standard"
    tc_ok = time_control == TIME_CONTROL_TARGET
    elo_ok = white_elo is not None and black_elo is not None
    result_ok = result_raw in _VALID_RESULTS

    rejection_reason: str | None
    if not tc_ok:
        rejection_reason = REJECT_WRONG_TC
    elif not variant_ok:
        rejection_reason = REJECT_VARIANT
    elif not elo_ok:
        rejection_reason = REJECT_INVALID_ELO
    elif not result_ok:
        rejection_reason = REJECT_INVALID_RESULT
    elif not has_clock:
        rejection_reason = REJECT_MISSING_CLOCK
    else:
        rejection_reason = None

    accepted_basic = rejection_reason is None
    accepted_eval = accepted_basic and has_eval

    return GameRecord(
        game_id=game_id,
        source_file=source_file,
        source_month=source_month,
        utc_date=utc_date,
        utc_time=utc_time,
        time_control=time_control,
        result_raw=result_raw,
        result_class=result_class,
        white_result_numeric=white_result_numeric,
        termination=termination,
        white_elo=white_elo,
        black_elo=black_elo,
        elo_diff=elo_diff,
        white_rating_diff=white_rating_diff,
        black_rating_diff=black_rating_diff,
        event=event,
        n_plies=n_plies,
        has_clock=has_clock,
        has_eval=has_eval,
        accepted_basic=accepted_basic,
        accepted_eval=accepted_eval,
        rejection_reason=rejection_reason,
    )


# ---------------------------------------------------------------------------
# Ply-level record extraction
# ---------------------------------------------------------------------------

def extract_ply_records(
    game: chess.pgn.Game,
    game_id: str | None = None,
) -> list[PlyRecord]:
    """
    Walk the main line and build one PlyRecord per ply.

    Clock values are carried forward: white_clock_s is updated only when
    White plays; its most recent value is reused on Black's plies and vice
    versa. This ensures both clock values are present on each row once both
    sides have played at least one annotated move.

    Eval is parsed per-ply from the comment using the side_to_move_next
    context required to convert Lichess's "side to move" mate convention
    to White POV.
    """
    records: list[PlyRecord] = []
    white_clock_s: int | None = None
    black_clock_s: int | None = None

    node = game
    ply = 0

    while node.variations:
        node = node.variations[0]
        ply += 1

        board_after = node.board()  # board state AFTER this move
        side_to_move_next = "white" if board_after.turn == chess.WHITE else "black"

        # Full-move number: after Black's Nth move, fullmove_number = N+1, turn = WHITE
        move_number = (
            board_after.fullmove_number - 1
            if board_after.turn == chess.WHITE
            else board_after.fullmove_number
        )

        # SAN (requires the pre-move board state)
        try:
            san = node.parent.board().san(node.move)
        except Exception:
            san = None

        comment = node.comment

        # --- Clock ---
        clk_m = _CLK_RE.search(comment)
        if clk_m:
            clk_val = parse_clock_seconds(clk_m.group(1))
            # The clock annotation after a ply belongs to the side that just moved.
            # Side that just moved = opposite of side_to_move_next.
            if side_to_move_next == "black":
                # White just moved
                white_clock_s = clk_val
            else:
                # Black just moved
                black_clock_s = clk_val

        clock_diff_s = (
            white_clock_s - black_clock_s
            if white_clock_s is not None and black_clock_s is not None
            else None
        )

        # --- Eval ---
        eval_cp, eval_mate, raw_eval = parse_eval_comment(comment, side_to_move_next)
        has_eval = raw_eval is not None

        records.append(PlyRecord(
            game_id=game_id,
            ply=ply,
            move_number=move_number,
            side_to_move_next=side_to_move_next,
            san=san,
            white_clock_s=white_clock_s,
            black_clock_s=black_clock_s,
            clock_diff_s=clock_diff_s,
            eval_cp=eval_cp,
            eval_mate=eval_mate,
            raw_eval=raw_eval,
            has_eval=has_eval,
        ))

    return records


# ---------------------------------------------------------------------------
# Checkpoint selection
# ---------------------------------------------------------------------------

def select_checkpoints(
    ply_records: list[PlyRecord],
    game_record: GameRecord,
) -> list[PositionRecord]:
    """
    Select v1 checkpoint positions from a list of PlyRecords.

    Returns one PositionRecord per checkpoint, plus one for "last".
    Games shorter than 20 plies return an empty list.

    If "last" coincides with a numbered checkpoint ply, both rows are
    emitted with different selected_position_type values.
    """
    if not ply_records:
        return []

    ply_map: dict[int, PlyRecord] = {r.ply: r for r in ply_records}
    last_ply = max(ply_map)

    # Must reach at least ply 20 for any checkpoint to exist
    if last_ply < 20:
        return []

    # Collect (ply, type) pairs
    candidates: list[tuple[int, str]] = []
    for target_ply, pos_type in sorted(CHECKPOINT_PLIES.items()):
        if target_ply <= last_ply:
            candidates.append((target_ply, pos_type))
    candidates.append((last_ply, "last"))

    result: list[PositionRecord] = []
    for target_ply, pos_type in candidates:
        pr = ply_map.get(target_ply)
        if pr is None:
            continue
        result.append(PositionRecord(
            game_id=game_record.game_id,
            ply=pr.ply,
            move_number=pr.move_number,
            side_to_move_next=pr.side_to_move_next,
            selected_position_type=pos_type,
            white_clock_s=pr.white_clock_s,
            black_clock_s=pr.black_clock_s,
            clock_diff_s=pr.clock_diff_s,
            eval_cp=pr.eval_cp,
            eval_mate=pr.eval_mate,
            has_eval=pr.has_eval,
            phase=phase_for_move(pr.move_number),
            result_class=game_record.result_class,
            white_result_numeric=game_record.white_result_numeric,
            white_elo=game_record.white_elo,
            black_elo=game_record.black_elo,
            elo_diff=game_record.elo_diff,
            termination=game_record.termination,
            n_plies_total=game_record.n_plies,
        ))

    return result


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def parse_game(
    game: chess.pgn.Game,
    source_file: str | None = None,
) -> tuple[GameRecord, list[PositionRecord]]:
    """
    Parse a single chess.pgn.Game object.

    Returns
    -------
    (game_record, position_records)
        game_record      : GameRecord for this game (accepted or rejected)
        position_records : list of PositionRecord checkpoints; empty if game
                           is not accepted_basic or is too short
    """
    game_record = extract_game_record(game, source_file=source_file)
    ply_records = extract_ply_records(game, game_id=game_record.game_id)

    # Only extract checkpoints for accepted games of sufficient length
    if game_record.accepted_basic:
        position_records = select_checkpoints(ply_records, game_record)
    else:
        position_records = []

    return game_record, position_records
