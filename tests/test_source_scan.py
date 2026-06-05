"""
Tests for source_scan.py using synthetic PGN fixtures.

No real game data. All PGN strings are hand-crafted minimal examples.
"""

import io
import json

import pytest

from chess_mhsuc.source_scan import (
    ScanResult,
    _is_valid_elo,
    build_summary,
    inspect_game,
    scan_stream,
)

import chess.pgn


# ---------------------------------------------------------------------------
# Synthetic PGN fixtures
# ---------------------------------------------------------------------------

# 10+0, valid Elos, valid Result, has %clk and %eval → eval_pass
PGN_600_CLOCK_EVAL = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1234"]
[Date "2024.09.01"]
[White "PlayerA"]
[Black "PlayerB"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1480"]
[TimeControl "600+0"]
[Termination "Normal"]

1. e4 { [%clk 0:10:00] [%eval 0.25] } e5 { [%clk 0:10:00] [%eval 0.25] } 1-0

"""

# 10+0, valid Elos, valid Result, has %clk, NO %eval → basic_pass only
PGN_600_CLOCK_ONLY = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1235"]
[Date "2024.09.01"]
[White "PlayerC"]
[Black "PlayerD"]
[Result "0-1"]
[WhiteElo "1600"]
[BlackElo "1590"]
[TimeControl "600+0"]
[Termination "Normal"]

1. e4 { [%clk 0:10:00] } e5 { [%clk 0:09:58] } 0-1

"""

# 10+0, valid Elos, valid Result, NO %clk → fails basic_pass
PGN_600_NO_CLOCK = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1236"]
[Date "2024.09.01"]
[White "PlayerE"]
[Black "PlayerF"]
[Result "1/2-1/2"]
[WhiteElo "1400"]
[BlackElo "1420"]
[TimeControl "600+0"]
[Termination "Normal"]

1. e4 e5 1/2-1/2

"""

# Wrong time control (5+0) → not counted as 600+0 at all
PGN_WRONG_TC = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1237"]
[Date "2024.09.01"]
[White "PlayerG"]
[Black "PlayerH"]
[Result "1-0"]
[WhiteElo "1550"]
[BlackElo "1530"]
[TimeControl "300+0"]
[Termination "Normal"]

1. e4 { [%clk 0:05:00] [%eval 0.15] } e5 1-0

"""

# 10+0 but invalid Elo ("?") → invalid_elo rejection
PGN_INVALID_ELO = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1238"]
[Date "2024.09.01"]
[White "PlayerI"]
[Black "PlayerJ"]
[Result "1-0"]
[WhiteElo "?"]
[BlackElo "1500"]
[TimeControl "600+0"]
[Termination "Normal"]

1. e4 { [%clk 0:10:00] [%eval 0.20] } e5 1-0

"""

# 10+0 but invalid Result ("*") → invalid_result rejection
PGN_INVALID_RESULT = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/abcd1239"]
[Date "2024.09.01"]
[White "PlayerK"]
[Black "PlayerL"]
[Result "*"]
[WhiteElo "1700"]
[BlackElo "1680"]
[TimeControl "600+0"]
[Termination "Abandoned"]

1. e4 { [%clk 0:10:00] } e5 *

"""


def _parse(pgn_str: str) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(pgn_str))


# ---------------------------------------------------------------------------
# _is_valid_elo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("elo_str, expected", [
    ("1500", True),
    ("800", True),
    ("?", False),
    ("", False),
    ("0", False),
    ("-1", False),
    ("abc", False),
])
def test_is_valid_elo(elo_str, expected):
    assert _is_valid_elo(elo_str) == expected


# ---------------------------------------------------------------------------
# inspect_game — individual fixture tests
# ---------------------------------------------------------------------------

def test_inspect_game_eval_pass():
    r = ScanResult()
    inspect_game(_parse(PGN_600_CLOCK_EVAL), r)
    assert r.n_600_0_total == 1
    assert r.n_600_0_basic_pass == 1
    assert r.n_600_0_eval_pass == 1
    assert r.n_600_0_no_clock == 0
    assert r.n_600_0_invalid_elo == 0
    assert r.n_600_0_invalid_result == 0
    assert r.result_dist["1-0"] == 1
    assert r.white_elos == [1500]
    assert r.black_elos == [1480]


def test_inspect_game_clock_only():
    r = ScanResult()
    inspect_game(_parse(PGN_600_CLOCK_ONLY), r)
    assert r.n_600_0_total == 1
    assert r.n_600_0_basic_pass == 1
    assert r.n_600_0_eval_pass == 0
    assert r.n_600_0_no_eval == 1


def test_inspect_game_no_clock():
    r = ScanResult()
    inspect_game(_parse(PGN_600_NO_CLOCK), r)
    assert r.n_600_0_total == 1
    assert r.n_600_0_basic_pass == 0
    assert r.n_600_0_no_clock == 1


def test_inspect_game_wrong_tc():
    r = ScanResult()
    inspect_game(_parse(PGN_WRONG_TC), r)
    assert r.n_600_0_total == 0
    assert r.n_600_0_basic_pass == 0


def test_inspect_game_invalid_elo():
    r = ScanResult()
    inspect_game(_parse(PGN_INVALID_ELO), r)
    assert r.n_600_0_total == 1
    assert r.n_600_0_basic_pass == 0
    assert r.n_600_0_invalid_elo == 1


def test_inspect_game_invalid_result():
    r = ScanResult()
    inspect_game(_parse(PGN_INVALID_RESULT), r)
    assert r.n_600_0_total == 1
    assert r.n_600_0_basic_pass == 0
    assert r.n_600_0_invalid_result == 1


# ---------------------------------------------------------------------------
# scan_stream — multi-game stream tests
# ---------------------------------------------------------------------------

ALL_SIX_GAMES = (
    PGN_600_CLOCK_EVAL
    + PGN_600_CLOCK_ONLY
    + PGN_600_NO_CLOCK
    + PGN_WRONG_TC
    + PGN_INVALID_ELO
    + PGN_INVALID_RESULT
)


def test_scan_stream_counts_all_games():
    r = scan_stream(io.StringIO(ALL_SIX_GAMES), max_games=100)
    assert r.n_total == 6
    assert r.n_600_0_total == 5       # all except WRONG_TC
    assert r.n_600_0_basic_pass == 2  # CLOCK_EVAL + CLOCK_ONLY
    assert r.n_600_0_eval_pass == 1   # CLOCK_EVAL only


def test_scan_stream_respects_cap():
    r = scan_stream(io.StringIO(ALL_SIX_GAMES), max_games=3)
    assert r.n_total == 3


def test_scan_stream_cap_zero():
    r = scan_stream(io.StringIO(ALL_SIX_GAMES), max_games=0)
    assert r.n_total == 0


def test_scan_stream_empty_input():
    r = scan_stream(io.StringIO(""), max_games=100)
    assert r.n_total == 0


# ---------------------------------------------------------------------------
# build_summary — JSON serializability
# ---------------------------------------------------------------------------

def test_build_summary_is_json_serializable():
    r = scan_stream(io.StringIO(ALL_SIX_GAMES), max_games=100)
    summary = build_summary(r)
    # Must not raise
    serialized = json.dumps(summary)
    parsed = json.loads(serialized)
    assert parsed["scan_metadata"]["n_total_scanned"] == 6
    assert parsed["pass_rates"]["n_600_0_basic_pass"] == 2
    assert parsed["pass_rates"]["n_600_0_eval_pass"] == 1


def test_build_summary_structure():
    r = scan_stream(io.StringIO(PGN_600_CLOCK_EVAL), max_games=100)
    summary = build_summary(r)
    assert "scan_metadata" in summary
    assert "time_control_filter" in summary
    assert "pass_rates" in summary
    assert "rejection_reasons_600_0" in summary
    assert "result_dist_600_0_basic_pass" in summary
    assert "termination_dist_600_0_basic_pass" in summary
    assert "elo_summary_white_600_0_basic_pass" in summary
    assert "elo_summary_black_600_0_basic_pass" in summary
