"""
schemas.py — dataclass schemas for chess-MHSUC pipeline records.

Design notes:
  - All eval fields use White's point of view. Positive = White advantage.
  - eval_cp stores centipawns. Example: 0.47 pawns → eval_cp = 47.
  - For forced-mate positions, eval_cp uses the sentinel ±MATE_CP_SENTINEL (10000).
    eval_mate stores the exact distance with White-POV sign:
      positive N = White has forced mate in N moves
      negative N = Black has forced mate in N moves
    This sentinel convention is project-defined, not a Lichess centipawn score.
  - Missing eval is represented as None. Never imputed to 0.
  - Clocks are stored as integer seconds remaining after the move.
  - clock_diff_s = white_clock_s - black_clock_s (positive = White has more time).
  - Selected-position checkpoints are taken after Black's Nth full move.
    "move_10" = after Black plays move 10 = ply 20 (1-indexed).
"""

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Result constants
# ---------------------------------------------------------------------------

RESULT_WHITE_WIN = "WHITE_WIN"
RESULT_DRAW = "DRAW"
RESULT_BLACK_WIN = "BLACK_WIN"

# ---------------------------------------------------------------------------
# Time control target
# ---------------------------------------------------------------------------

TIME_CONTROL_TARGET = "600+0"

# ---------------------------------------------------------------------------
# Phase constants
# ---------------------------------------------------------------------------

PHASE_OPENING = "opening"       # move_number <= 10
PHASE_MIDDLEGAME = "middlegame"  # 11 <= move_number <= 35
PHASE_ENDGAME = "endgame"        # move_number > 35

# ---------------------------------------------------------------------------
# Eval sentinel for mate scores stored in eval_cp
# ---------------------------------------------------------------------------

MATE_CP_SENTINEL = 10_000
"""
When a position has forced mate, eval_cp is set to ±MATE_CP_SENTINEL.
  +10000 → White has forced mate (White wins decisively).
  -10000 → Black has forced mate (Black wins decisively).
The exact mate distance is stored in eval_mate.
This is a project-defined convention, not a Lichess-native centipawn value.
Models using eval_cp as a continuous feature should be aware of these outliers.
"""

# ---------------------------------------------------------------------------
# Checkpoint ply mapping  (ply numbers are 1-indexed)
# ---------------------------------------------------------------------------

CHECKPOINT_PLIES: dict[int, str] = {
    20: "move_10",
    40: "move_20",
    60: "move_30",
    80: "move_40",
}
"""
Maps ply number (1-indexed) to selected_position_type label.
  ply 20 = after Black's 10th move  → "move_10"
  ply 40 = after Black's 20th move  → "move_20"
  ply 60 = after Black's 30th move  → "move_30"
  ply 80 = after Black's 40th move  → "move_40"
The "last" checkpoint (final ply) is handled separately in select_checkpoints().
"""

# ---------------------------------------------------------------------------
# Rejection reason constants
# ---------------------------------------------------------------------------

REJECT_MALFORMED_PGN = "malformed_pgn"
REJECT_WRONG_TC = "wrong_time_control"
REJECT_VARIANT = "variant_or_nonstandard"
REJECT_INVALID_ELO = "missing_or_invalid_elo"
REJECT_INVALID_RESULT = "missing_or_invalid_result"
REJECT_MISSING_CLOCK = "missing_clock"


# ---------------------------------------------------------------------------
# GameRecord
# ---------------------------------------------------------------------------

@dataclass
class GameRecord:
    """
    One row per parsed game. Covers accepted and rejected games alike.

    Rejection fields (accepted_basic = False) still carry any fields that
    were successfully extracted before the rejection criterion was hit.

    Username fields (White, Black) are intentionally absent. Per DATA_POLICY.md,
    usernames are not retained in processed outputs.

    Fields
    ------
    game_id
        Derived from the Site URL last path segment (e.g. "abcd1234").
        None if Site header is absent or unparseable.
    source_file
        Archive filename (e.g. "lichess_db_standard_rated_2024-09.pgn.zst").
        None if not provided to the parser.
    source_month
        Extracted from source_file with pattern YYYY-MM (e.g. "2024-09").
        None if not parseable.
    utc_date
        Raw UTCDate header value (e.g. "2024.09.15"). None if absent.
    utc_time
        Raw UTCTime header value (e.g. "12:00:00"). None if absent.
    time_control
        Raw TimeControl header value (e.g. "600+0"). None if absent.
    result_raw
        Raw Result header: "1-0", "0-1", "1/2-1/2", or None if invalid/absent.
    result_class
        Derived: RESULT_WHITE_WIN, RESULT_DRAW, RESULT_BLACK_WIN, or None.
    white_result_numeric
        1.0 (White win), 0.5 (Draw), 0.0 (Black win), or None if invalid result.
    termination
        Raw Termination header value. None if absent.
    white_elo
        Parsed integer WhiteElo. None if invalid or absent.
    black_elo
        Parsed integer BlackElo. None if invalid or absent.
    elo_diff
        white_elo - black_elo (White-positive). None if either Elo is None.
    white_rating_diff
        Parsed integer WhiteRatingDiff. None if absent.
    black_rating_diff
        Parsed integer BlackRatingDiff. None if absent.
    event
        Raw Event header. None if absent.
    n_plies
        Total number of main-line plies in the game.
    has_clock
        True if any main-line ply comment contains %clk.
    has_eval
        True if any main-line ply comment contains %eval.
    accepted_basic
        True if ALL of the following hold:
          - time_control == TIME_CONTROL_TARGET ("600+0")
          - Variant header is absent or "Standard"
          - white_elo and black_elo are valid integers > 0
          - result_raw in {"1-0", "0-1", "1/2-1/2"}
          - has_clock is True
    accepted_eval
        True if accepted_basic AND has_eval.
    rejection_reason
        First applicable rejection reason string if not accepted_basic, else None.
        Priority order: wrong_time_control, variant_or_nonstandard,
        missing_or_invalid_elo, missing_or_invalid_result, missing_clock.
    """
    game_id: str | None
    source_file: str | None
    source_month: str | None
    utc_date: str | None
    utc_time: str | None
    time_control: str | None
    result_raw: str | None
    result_class: str | None
    white_result_numeric: float | None
    termination: str | None
    white_elo: int | None
    black_elo: int | None
    elo_diff: int | None
    white_rating_diff: int | None
    black_rating_diff: int | None
    event: str | None
    n_plies: int
    has_clock: bool
    has_eval: bool
    accepted_basic: bool
    accepted_eval: bool
    rejection_reason: str | None


# ---------------------------------------------------------------------------
# PlyRecord
# ---------------------------------------------------------------------------

@dataclass
class PlyRecord:
    """
    One row per main-line ply. Stores raw extracted values before feature engineering.

    Fields
    ------
    game_id
        Foreign key to GameRecord. None if game_id is unknown.
    ply
        1-indexed ply number within the game.
        Ply 1 = White's first move. Ply 2 = Black's first move.
    move_number
        Full-move number (1-indexed). Increments after Black's move.
        White's move 10 and Black's move 10 both have move_number = 10.
    side_to_move_next
        "white" or "black" — which side is to move from this position.
        After White's ply (odd ply): "black".
        After Black's ply (even ply): "white".
    san
        Move in Standard Algebraic Notation. None if unavailable.
    white_clock_s
        White's remaining clock in seconds after the most recent White ply
        at or before this ply. Updated when White moves; carried forward otherwise.
        None if White has not yet moved or no clock annotation was found.
    black_clock_s
        Black's remaining clock in seconds, analogous to white_clock_s.
        None until Black plays their first move with a clock annotation.
    clock_diff_s
        white_clock_s - black_clock_s. Positive = White has more time.
        None if either component is None.
    eval_cp
        Engine evaluation in centipawns, White's POV.
        None if no %eval annotation on this ply.
        Uses ±MATE_CP_SENTINEL for forced-mate positions.
    eval_mate
        Mate distance, White's POV.
        Positive N = White has forced mate in N moves.
        Negative N = Black has forced mate in N moves.
        None if no eval or if eval is a decimal (not a mate score).
    raw_eval
        The raw eval token string from the %eval annotation (e.g. "0.47", "#3", "#-2").
        None if no %eval on this ply. Retained for auditing; excluded from processed data.
    has_eval
        True if this ply has a %eval annotation.
    """
    game_id: str | None
    ply: int
    move_number: int
    side_to_move_next: str
    san: str | None
    white_clock_s: int | None
    black_clock_s: int | None
    clock_diff_s: int | None
    eval_cp: int | None
    eval_mate: int | None
    raw_eval: str | None
    has_eval: bool


# ---------------------------------------------------------------------------
# PositionRecord
# ---------------------------------------------------------------------------

@dataclass
class PositionRecord:
    """
    One row per selected checkpoint position per game.

    Checkpoints are defined as positions after Black's Nth full move:
      "move_10" = ply 20  (after Black plays move 10)
      "move_20" = ply 40  (after Black plays move 20)
      "move_30" = ply 60  (after Black plays move 30)
      "move_40" = ply 80  (after Black plays move 40)
      "last"    = final ply of the game (any side)

    If "last" coincides with a numbered checkpoint (e.g. the game ends at ply 40),
    both rows are emitted with different selected_position_type values.
    Deduplication is the caller's responsibility.

    Games shorter than 20 plies produce no checkpoint rows.

    Low-time flags (under_60, under_30, under_10) are NOT included here.
    They belong to the feature engineering stage (Phase 3 / Ticket 3.2B).

    Fields
    ------
    game_id
        Foreign key to GameRecord.
    ply
        1-indexed ply number of this position.
    move_number
        Full-move number at this position.
    side_to_move_next
        "white" or "black" — which side moves next from this position.
    selected_position_type
        One of "move_10", "move_20", "move_30", "move_40", "last".
    white_clock_s
        White's remaining clock in seconds. None if unavailable.
    black_clock_s
        Black's remaining clock in seconds. None if unavailable.
    clock_diff_s
        white_clock_s - black_clock_s. None if either is None.
    eval_cp
        Centipawns, White's POV. None if no eval. ±MATE_CP_SENTINEL for forced mate.
    eval_mate
        Mate distance, White's POV. None if no eval or not a mate score.
    has_eval
        True if this position has a %eval annotation.
    phase
        "opening" (move ≤ 10), "middlegame" (11–35), or "endgame" (> 35).
        Derived from move_number using the initial v1 approximation.
    result_class
        Game outcome label copied from GameRecord.
    white_result_numeric
        1.0, 0.5, or 0.0 copied from GameRecord.
    white_elo
        Copied from GameRecord.
    black_elo
        Copied from GameRecord.
    elo_diff
        Copied from GameRecord.
    termination
        Copied from GameRecord.
    n_plies_total
        Total plies in the game, copied from GameRecord.
    """
    game_id: str | None
    ply: int
    move_number: int
    side_to_move_next: str
    selected_position_type: str
    white_clock_s: int | None
    black_clock_s: int | None
    clock_diff_s: int | None
    eval_cp: int | None
    eval_mate: int | None
    has_eval: bool
    phase: str
    result_class: str | None
    white_result_numeric: float | None
    white_elo: int | None
    black_elo: int | None
    elo_diff: int | None
    termination: str | None
    n_plies_total: int
