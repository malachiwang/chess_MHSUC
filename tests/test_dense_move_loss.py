"""Tests for dense_move_loss.py (Ticket 15.3B). Pure logic + synthetic games;
no Stockfish, no large data."""

from __future__ import annotations

import io

import chess
import chess.pgn
import polars as pl
import pytest

from chess_mhsuc.dense_move_loss import (
    PILOT_DEFAULT_MAX_GAMES,
    PILOT_HARD_MAX_GAMES,
    _OUTPUT_SCHEMA,
    _STATUS_OK,
    assemble_row,
    build_accepted_meta_from_raw,
    build_move_records,
    canonicalize_time_control,
    clock_bucket_coarse,
    clock_flags,
    clock_fraction_for,
    completed_game_ids_from_chunks,
    concatenate_chunks,
    cp_loss_clipped,
    cp_loss_raw,
    es_loss,
    finalize_frame,
    increment_buffer_for,
    main as dense_main,
    mover_result_label,
    parse_clk_seconds,
    parse_time_control,
    phase_for,
    rating_bin,
    render_matched_size_report,
    render_report,
    speed_category_for,
    summarize,
    terminal_white_eval,
    think_time,
    think_time_bucket,
    time_control_family_for,
)
from chess_mhsuc.next_move_loss import expected_score


# ---------------------------------------------------------------------------
# Synthetic game helpers
# ---------------------------------------------------------------------------

def _game_from_san(moves_with_clk: list[tuple[str, str | None]],
                   site: str = "https://lichess.org/abcd1234") -> chess.pgn.Game:
    """Build a chess.pgn.Game from (SAN, clk-string|None) pairs."""
    game = chess.pgn.Game()
    game.headers["Site"] = site
    node = game
    board = game.board()
    for san, clk in moves_with_clk:
        move = board.parse_san(san)
        board.push(move)
        node = node.add_variation(move)
        if clk is not None:
            node.comment = f"[%clk {clk}]"
    return game


_META = {
    "result_class": "WHITE_WIN", "termination": "Normal",
    "is_time_forfeit": False, "white_elo": 1600, "black_elo": 1500,
    "split_set": "train",
}


# ---------------------------------------------------------------------------
# 1-3. Clock-before reconstruction + think time
# ---------------------------------------------------------------------------

def test_parse_clk_seconds():
    assert parse_clk_seconds("[%clk 0:10:00]") == 600.0
    assert parse_clk_seconds("[%clk 0:09:53]") == 593.0
    assert parse_clk_seconds("hello [%clk 0:00:01] x") == 1.0
    assert parse_clk_seconds(None) is None
    assert parse_clk_seconds("no clock here") is None


def test_first_move_clock_before_is_600_white_and_black():
    # White's move 5 and Black's move 5 are the first emitted (min_move_number=5);
    # but clock_before for a side's FIRST move (move 1) defaults to 600.
    moves = [("e4", "0:09:59"), ("e5", "0:09:58")]  # both first moves
    game = _game_from_san(moves)
    recs, _, fail = build_move_records(game, _META, min_move_number=1)
    assert fail is None
    white_first = recs[0]
    black_first = recs[1]
    assert white_first["clock_before_s"] == 600.0  # White's first move
    assert white_first["clock_after_s"] == 599.0
    assert black_first["clock_before_s"] == 600.0  # Black's first move
    assert black_first["clock_after_s"] == 598.0


def test_clock_before_reconstruction_white_and_black():
    moves = [
        ("e4", "0:10:00"), ("e5", "0:09:59"),
        ("Nf3", "0:09:50"), ("Nc6", "0:09:40"),
    ]
    game = _game_from_san(moves)
    recs, _, _ = build_move_records(game, _META, min_move_number=1)
    # White's 2nd move: before = White's clock after move 1 = 600
    w2 = [r for r in recs if r["mover_is_white"]][1]
    assert w2["clock_before_s"] == 600.0
    assert w2["clock_after_s"] == 590.0
    # Black's 2nd move: before = Black's clock after move 1 = 599
    b2 = [r for r in recs if not r["mover_is_white"]][1]
    assert b2["clock_before_s"] == 599.0
    assert b2["clock_after_s"] == 580.0


def test_think_time_computation():
    assert think_time(600.0, 593.0) == 7.0
    assert think_time(None, 593.0) is None
    assert think_time(600.0, None) is None


# ---------------------------------------------------------------------------
# 4-5. Anomaly flags
# ---------------------------------------------------------------------------

def test_negative_think_time_anomaly_flag():
    clock_anom, think_anom = clock_flags(580.0, 590.0, think_time(580.0, 590.0))
    assert think_anom is True  # clock went UP -> negative think time


def test_clock_over_600_anomaly_flag():
    clock_anom, _ = clock_flags(601.0, 605.0, think_time(601.0, 605.0))
    assert clock_anom is True


def test_missing_clock_flags():
    clock_anom, think_anom = clock_flags(600.0, None, None)
    assert clock_anom is True
    assert think_anom is True


# ---------------------------------------------------------------------------
# 6-7. Mover-perspective sign conversion (via assemble_row)
# ---------------------------------------------------------------------------

def _eval(cp, mate=None, available=True, terminal=False):
    return {"cp": cp, "mate": mate, "available": available, "terminal": terminal}


def _rec(ply, move_number, mover_is_white, move_uci="e2e4"):
    return {
        "ply": ply, "move_number": move_number, "mover_is_white": mover_is_white,
        "pre_fen": chess.STARTING_FEN, "post_fen": chess.STARTING_FEN,
        "move_uci": move_uci, "clock_before_s": 300.0, "clock_after_s": 295.0,
        "think_time_s": 5.0, "white_clock_before_s": 300.0,
        "black_clock_before_s": 300.0, "white_clock_after_s": 295.0,
        "black_clock_after_s": 300.0, "move_is_capture": False,
        "move_is_check": False, "move_is_promotion": False, "move_is_castle": False,
        "clock_anomaly": False, "think_time_anomaly": False,
    }


def test_mover_perspective_white():
    # White to move; white-POV before +50, after +20 -> mover loss 30.
    row = assemble_row("g", "2024_09", _rec(20, 11, True), _META,
                       _eval(50), _eval(20), depth=12, es_scale=348.41)
    assert row["cp_loss_raw"] == 30
    assert row["cp_loss_clipped"] == 30
    assert row["side_to_move"] == "white"


def test_mover_perspective_black():
    # Black to move; white-POV before -50 (Black +50), after -20 (Black +20) ->
    # mover (Black) value before 50, after 20 -> loss 30.
    row = assemble_row("g", "2024_09", _rec(21, 11, False), _META,
                       _eval(-50), _eval(-20), depth=12, es_scale=348.41)
    assert row["cp_loss_raw"] == 30
    assert row["cp_loss_clipped"] == 30
    assert row["mover_color"] == "black"


# ---------------------------------------------------------------------------
# 8. CP loss raw vs clipped
# ---------------------------------------------------------------------------

def test_cp_loss_raw_can_be_negative():
    assert cp_loss_raw(20, 50) == -30          # actual move improved static eval
    assert cp_loss_clipped(20, 50) == 0        # clipped loss floored at 0


def test_cp_loss_clipped_caps_values():
    # before +5000 (mate-ish), after -5000 -> clipped to +/-1000 -> loss 2000.
    assert cp_loss_clipped(5000, -5000) == 2000
    assert cp_loss_raw(5000, -5000) == 10000


# ---------------------------------------------------------------------------
# 9. Expected-score loss nonnegative and bounded
# ---------------------------------------------------------------------------

def test_es_loss_nonnegative_and_bounded():
    s = 348.41
    eb = expected_score(300, s)
    ea = expected_score(-300, s)
    loss = es_loss(eb, ea)
    assert 0.0 <= loss <= 1.0
    # improving move -> floored at 0
    assert es_loss(expected_score(-100, s), expected_score(100, s)) == 0.0


# ---------------------------------------------------------------------------
# 10. Mate-band flagging
# ---------------------------------------------------------------------------

def test_mate_band_flag_and_excluded_intent():
    row = assemble_row("g", "2024_09", _rec(40, 21, True), _META,
                       _eval(10000, mate=1), _eval(50), depth=12, es_scale=348.41)
    assert row["is_mate_band"] is True
    assert row["eval_band"] == "mate_band"


# ---------------------------------------------------------------------------
# 11-14. Bucketing
# ---------------------------------------------------------------------------

def test_phase_bucketing():
    assert phase_for(5) == "opening"
    assert phase_for(10) == "opening"
    assert phase_for(11) == "middlegame"
    assert phase_for(30) == "middlegame"
    assert phase_for(31) == "endgame"
    assert phase_for(None) is None


def test_clock_bucketing():
    assert clock_bucket_coarse(30.0) == "under_60"
    assert clock_bucket_coarse(120.0) == "60_180"
    assert clock_bucket_coarse(300.0) == "over_180"
    assert clock_bucket_coarse(None) is None


def test_think_time_bucketing():
    assert think_time_bucket(0.5) == "instant_lt1"
    assert think_time_bucket(2.0) == "1_3"
    assert think_time_bucket(5.0) == "3_10"
    assert think_time_bucket(20.0) == "10_30"
    assert think_time_bucket(45.0) == "over_30"
    assert think_time_bucket(-1.0) is None
    assert think_time_bucket(None) is None


def test_rating_bucketing():
    assert rating_bin(1600) == "1600_1799"
    assert rating_bin(1599) == "1400_1599"
    assert rating_bin(None) is None


# ---------------------------------------------------------------------------
# 15. Move tag extraction (capture / check / promotion / castle)
# ---------------------------------------------------------------------------

def test_move_tag_capture_and_check():
    # 1.e4 d5 2.exd5 (capture) ... Scholar-ish check later.
    moves = [("e4", None), ("d5", None), ("exd5", None), ("Qxd5", None),
             ("Nc3", None), ("Qe5+", None)]  # Qe5 is not check; build a real check
    game = _game_from_san([("e4", None), ("e5", None), ("Bc4", None),
                           ("Nc6", None), ("Qh5", None), ("Nf6", None),
                           ("Qxf7+", None)], )
    recs, _, fail = build_move_records(game, _META, min_move_number=1)
    assert fail is None
    last = recs[-1]  # Qxf7+ : capture and check
    assert last["move_is_capture"] is True
    assert last["move_is_check"] is True


def test_move_tag_castle():
    game = _game_from_san([("e4", None), ("e5", None), ("Nf3", None),
                           ("Nc6", None), ("Bc4", None), ("Bc5", None),
                           ("O-O", None)])
    recs, _, _ = build_move_records(game, _META, min_move_number=1)
    castle = recs[-1]
    assert castle["move_is_castle"] is True


def test_move_tag_promotion():
    # Set up a board where a promotion is legal via FEN replay game.
    game = chess.pgn.Game()
    game.headers["Site"] = "https://lichess.org/promo0001"
    board = chess.Board("8/P7/8/8/8/8/8/k6K w - - 0 50")
    game.setup(board)
    node = game
    move = board.parse_san("a8=Q")
    node.add_variation(move)
    recs, _, _ = build_move_records(game, _META, min_move_number=1)
    assert recs[0]["move_is_promotion"] is True


# ---------------------------------------------------------------------------
# 16. Row key uniqueness
# ---------------------------------------------------------------------------

def test_row_key_uniqueness():
    rows = [
        assemble_row("g1", "2024_09", _rec(20, 11, True), _META, _eval(10), _eval(5), 12, 348.41),
        assemble_row("g1", "2024_09", _rec(21, 11, False), _META, _eval(-10), _eval(-5), 12, 348.41),
        assemble_row("g2", "2024_09", _rec(20, 11, True), _META, _eval(10), _eval(5), 12, 348.41),
    ]
    df, _ = finalize_frame(rows, None)
    assert df.select(["game_id", "ply"]).unique().height == df.height


# ---------------------------------------------------------------------------
# 17. No raw username fields in output schema
# ---------------------------------------------------------------------------

def test_no_raw_username_cols():
    rows = [assemble_row("g1", "2024_09", _rec(20, 11, True), _META, _eval(10), _eval(5), 12, 348.41)]
    df, _ = finalize_frame(rows, None)
    forbidden = {"white", "black", "White", "Black", "white_user", "black_user"}
    assert not (forbidden & set(df.columns))
    assert "mover_player_hash" in df.columns
    assert "opponent_player_hash" in df.columns


# ---------------------------------------------------------------------------
# 18-19. Pilot cap enforcement / refusal of large run
# ---------------------------------------------------------------------------

def test_pilot_cap_constants():
    assert PILOT_DEFAULT_MAX_GAMES <= PILOT_HARD_MAX_GAMES
    assert PILOT_DEFAULT_MAX_GAMES == 1500


def test_refuse_large_run(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "nonexistent.pgn", "--month", "2024_09",
        "--max-accepted-games", "999999",
        "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "pilot-only" in err or "exceeds the pilot cap" in err


def test_large_run_override_passes_cap_check(tmp_path):
    # With the override flag the cap check passes (it then fails later on the
    # missing PGN / stockfish, which is fine — we only assert it gets past the cap).
    with pytest.raises(Exception):
        dense_main([
            "--raw-pgn", "nonexistent.pgn", "--month", "2024_09",
            "--max-accepted-games", "999999", "--pilot-override-allow-large",
            "--stockfish-path", "/nonexistent/stockfish",
            "--out", str(tmp_path / "x.parquet"),
            "--report", str(tmp_path / "x.md"),
        ])


def test_matched_size_non_anchor_requires_override_above_cap(tmp_path, capsys):
    # Non-anchor cap above PILOT_HARD_MAX_GAMES WITHOUT override is refused at gate.
    rc = dense_main([
        "--raw-pgn", "nonexistent.pgn", "--month", "2024_09",
        "--time-control", "3+0", "--allow-time-control-pilot",
        "--max-accepted-games", "24000",
        "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "pilot cap" in capsys.readouterr().err


def test_matched_size_non_anchor_routes_to_chunked(tmp_path):
    # Non-anchor, cap > pilot cap, with override -> routes past the gate into the
    # chunked/resumable matched-size path (then fails on the missing stockfish/PGN,
    # which is fine — we only assert it gets past the gate, not rc==2).
    with pytest.raises(Exception):
        dense_main([
            "--raw-pgn", "nonexistent.pgn", "--month", "2024_09",
            "--time-control", "3+0", "--allow-time-control-pilot",
            "--max-accepted-games", "24000", "--pilot-override-allow-large",
            "--resume", "--stockfish-path", "/nonexistent/stockfish",
            "--out", str(tmp_path / "x.parquet"),
            "--report", str(tmp_path / "x.md"),
        ])


# ---------------------------------------------------------------------------
# 20. Report renderer includes validation summary
# ---------------------------------------------------------------------------

def test_report_renderer_includes_validation_summary():
    rows = [
        assemble_row("g1", "2024_09", _rec(20, 11, True), _META, _eval(10), _eval(5), 12, 348.41),
        assemble_row("g1", "2024_09", _rec(21, 12, False), _META, _eval(-10), _eval(-80), 12, 348.41),
    ]
    df, cov = finalize_frame(rows, None)
    counters = {"games_accepted": 1, "games_scanned": 3, "games_replay_failed": 0,
                "engine_evals": 3, "eval_cache_hits": 1, "terminal_positions": 0,
                "runtime_s": 1.0, "engine_seconds": 0.9}
    summary = summarize(df, counters)
    text = render_report("2024_09", 12, 5, 1500, counters, summary, [], cov,
                         "data/processed/x.parquet", None, "Stockfish 18")
    assert "Replay validation" in text
    assert "Clock / think-time validation" in text
    assert "Loss metric summary" in text
    assert "Full-run runtime extrapolation" in text
    assert "pilot only" in text.lower()


def test_matched_size_renderer_extraction_only():
    meta_3plus0 = {**_META, "time_control": "180+0"}
    rows = [
        assemble_row("g1", "2024_09", _rec(20, 11, True), meta_3plus0, _eval(10), _eval(5), 12, 348.41),
        assemble_row("g1", "2024_09", _rec(21, 12, False), meta_3plus0, _eval(-10), _eval(-80), 12, 348.41),
    ]
    df, cov = finalize_frame(rows, None)
    counters = {"games_accepted": 1, "games_scanned": 3, "games_replay_failed": 0,
                "engine_evals": 3, "eval_cache_hits": 1, "terminal_positions": 0,
                "runtime_s": 1.0, "engine_seconds": 0.9, "n_chunks": 1,
                "games_skipped_resume": 0, "accepted_available": 24000}
    summary = summarize(df, counters)
    summary["min_move_number"] = 5
    text = render_matched_size_report(
        "2024_09", "180+0", 12, 5000, counters, summary, [], cov,
        "data/processed/x.parquet", "data/processed/x_chunks", "Stockfish 18")
    assert "Matched-size dense extraction artifact" in text
    assert "180+0" in text
    assert "within-control rating quantiles" in text.lower()
    assert "no_increment" in text  # speed/family schema validation line
    assert "not causal" in text.lower()
    # extraction-only: must NOT assert a final / 10+0 framing
    assert "Full 10+0 Extraction" not in text


# ---------------------------------------------------------------------------
# 21. Misc — terminal eval, mover_result, min_move_number filter
# ---------------------------------------------------------------------------

def test_terminal_white_eval_checkmate():
    # Fool's mate: 1.f3 e5 2.g4 Qh4#  -> White is checkmated (White to move).
    board = chess.Board()
    for san in ["f3", "e5", "g4", "Qh4#"]:
        board.push_san(san)
    cp, mate = terminal_white_eval(board)
    assert cp == -10000  # White mated -> Black delivered
    assert mate == 0


def test_terminal_white_eval_none_for_normal_position():
    assert terminal_white_eval(chess.Board()) is None


def test_mover_result_label():
    assert mover_result_label("WHITE_WIN", True) == "win"
    assert mover_result_label("WHITE_WIN", False) == "loss"
    assert mover_result_label("BLACK_WIN", False) == "win"
    assert mover_result_label("DRAW", True) == "draw"


def test_min_move_number_filter_excludes_opening():
    game = _game_from_san([("e4", "0:09:59"), ("e5", "0:09:58"),
                           ("Nf3", "0:09:50"), ("Nc6", "0:09:40"),
                           ("Bb5", "0:09:30"), ("a6", "0:09:20")])
    recs, _, _ = build_move_records(game, _META, min_move_number=3)
    # only moves with move_number >= 3 (White Bb5 move 3, Black a6 move 3)
    assert all(r["move_number"] >= 3 for r in recs)
    assert len(recs) == 2


# ===========================================================================
# 15.3C — full-month mode, chunking, time-control-aware schema
# ===========================================================================

# --- full-month flag safety (Tasks 1-3) ---

def test_full_month_refuses_2024_10(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_10", "--allow-full-month-2024-09",
        "--depth", "12", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "restricted to month==2024_09" in capsys.readouterr().err


def test_full_month_refuses_non_depth_12(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--allow-full-month-2024-09",
        "--depth", "10", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "depth 12" in capsys.readouterr().err


def test_full_month_refuses_non_600_0(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--allow-full-month-2024-09",
        "--depth", "12", "--time-control", "180+2",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "600+0" in capsys.readouterr().err


def test_pilot_path_still_refuses_uncapped_without_full_month(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--max-accepted-games", "999999",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    err = capsys.readouterr().err
    assert "exceeds the pilot cap" in err


# --- 15.3D: 2024-10 full-month flag safety ---

def test_full_month_2024_10_flag_accepts_2024_10(tmp_path):
    # the 2024-10 flag passes the gate for month 2024_10 (then fails later on the
    # missing PGN / stockfish — we only assert it gets past the gate, not rc==2 gate).
    with pytest.raises(Exception):
        dense_main([
            "--raw-pgn", "nonexistent.pgn", "--month", "2024_10",
            "--allow-full-month-2024-10", "--depth", "12", "--time-control", "600+0",
            "--stockfish-path", "/nonexistent/stockfish",
            "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
        ])


def test_full_month_2024_10_flag_refuses_2024_09(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--allow-full-month-2024-10",
        "--depth", "12", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "restricted to month==2024_10" in capsys.readouterr().err


def test_full_month_2024_10_refuses_non_depth_12(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_10", "--allow-full-month-2024-10",
        "--depth", "10", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "depth 12" in capsys.readouterr().err


def test_full_month_2024_10_refuses_non_600_0(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_10", "--allow-full-month-2024-10",
        "--depth", "12", "--time-control", "300+2",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "600+0" in capsys.readouterr().err


def test_no_both_month_mode(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--allow-full-month-2024-09",
        "--allow-full-month-2024-10", "--depth", "12",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "both" in capsys.readouterr().err.lower()


def test_2024_09_flag_still_refuses_2024_10(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_10", "--allow-full-month-2024-09",
        "--depth", "12", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "restricted to month==2024_09" in capsys.readouterr().err


def test_compare_to_2024_09_block():
    from chess_mhsuc.dense_move_loss import _compare_to_2024_09
    summary = {"rows": 1500000, "unique_games": 25000, "rows_mate_band": 81000,
               "es_loss": {"mean": 0.035, "median": 0.011, "p90": 0.093, "ge_0_10": 0.09}}
    block = _compare_to_2024_09(summary)
    assert "2024-09" in block and "2024-10" in block
    assert "1,496,890" in block  # the published 2024-09 baseline row count


# --- time-control parsing (Tasks 8-19) ---

def test_parse_time_control():
    assert parse_time_control("600+0") == (600, 0)
    assert parse_time_control("180+2") == (180, 2)
    assert parse_time_control("900") == (900, 0)
    assert parse_time_control("-") == (None, None)
    assert parse_time_control(None) == (None, None)


def test_time_control_family():
    assert time_control_family_for(0) == "no_increment"
    assert time_control_family_for(2) == "increment"
    assert time_control_family_for(None) is None


def test_speed_category_convention():
    assert speed_category_for(600, 0) == "rapid"   # 10+0
    assert speed_category_for(60, 0) == "bullet"    # 1+0
    assert speed_category_for(180, 0) == "blitz"    # 3+0
    assert speed_category_for(900, 10) == "rapid"    # 15+10: est 900+400=1300 -> rapid
    assert speed_category_for(1800, 0) == "classical"


def test_clock_fraction():
    assert clock_fraction_for(300.0, 600) == 0.5
    assert clock_fraction_for(600.0, 600) == 1.0
    assert clock_fraction_for(None, 600) is None
    assert clock_fraction_for(300.0, None) is None


def test_increment_buffer_no_increment_is_null():
    assert increment_buffer_for(60.0, 0) is None   # no-increment -> null
    assert increment_buffer_for(60.0, 2) == 30.0   # increment game
    assert increment_buffer_for(None, 2) is None


def test_assemble_row_time_control_fields_for_10_0():
    row = assemble_row("g", "2024_09", _rec(20, 11, True), _META,
                       _eval(50), _eval(20), depth=12, es_scale=348.41)
    assert row["time_control_raw"] == "600+0"
    assert row["initial_time_s"] == 600
    assert row["increment_s"] == 0
    assert row["time_control_family"] == "no_increment"
    assert row["speed_category"] == "rapid"
    assert row["clock_fraction"] == 300.0 / 600  # _rec clock_before_s=300
    assert row["increment_buffer"] is None
    assert row["think_time_gross_s"] == row["think_time_net_s"]  # no increment
    assert row["low_increment_buffer_flag"] is None
    assert row["low_clock_absolute_flag"] is False  # 300s not < 60


def test_assemble_row_increment_fixture():
    meta_inc = {**_META, "time_control": "180+2"}
    rec = _rec(20, 11, True)
    rec["clock_before_s"] = 5.0   # low clock
    rec["think_time_s"] = 1.0
    row = assemble_row("g", "2024_09", rec, meta_inc, _eval(0), _eval(0),
                       depth=12, es_scale=348.41)
    assert row["initial_time_s"] == 180
    assert row["increment_s"] == 2
    assert row["time_control_family"] == "increment"
    assert row["increment_buffer"] == 2.5            # 5 / 2
    assert row["think_time_net_s"] == 3.0            # gross 1 + increment 2
    assert row["low_increment_buffer_flag"] is True  # 2.5 < 3
    assert row["low_clock_absolute_flag"] is True    # 5 < 60


def test_low_clock_fraction_flag():
    rec = _rec(20, 11, True)
    rec["clock_before_s"] = 30.0  # 30/600 = 0.05 < 0.10
    row = assemble_row("g", "2024_09", rec, _META, _eval(0), _eval(0), 12, 348.41)
    assert row["low_clock_fraction_flag"] is True


def test_expanded_schema_has_no_username_cols():
    rows = [assemble_row("g", "2024_09", _rec(20, 11, True), _META, _eval(10), _eval(5), 12, 348.41)]
    df, _ = finalize_frame(rows, None)
    forbidden = {"white", "black", "White", "Black", "white_user", "black_user"}
    assert not (forbidden & set(df.columns))
    # new TC fields present
    for c in ["time_control_raw", "initial_time_s", "increment_s", "clock_fraction",
              "increment_buffer", "think_time_net_s", "low_clock_absolute_flag"]:
        assert c in df.columns


# --- chunking + resume (Tasks 2, 4-7) ---

def _mk_rows(game_id, plies):
    return [assemble_row(game_id, "2024_09", _rec(p, 5 + p, p % 2 == 0), _META,
                         _eval(10), _eval(5), 12, 348.41) for p in plies]


def test_chunk_naming_and_concatenation(tmp_path):
    cdir = tmp_path / "chunks"
    cdir.mkdir()
    df0, _ = finalize_frame(_mk_rows("g1", [10, 11]), None)
    df1, _ = finalize_frame(_mk_rows("g2", [10, 11]), None)
    df0.write_parquet(cdir / "chunk_0000.parquet")
    df1.write_parquet(cdir / "chunk_0001.parquet")
    files = sorted(cdir.glob("chunk_*.parquet"))
    assert [f.name for f in files] == ["chunk_0000.parquet", "chunk_0001.parquet"]
    final = concatenate_chunks(files, tmp_path / "final.parquet")
    assert final.height == 4
    assert (tmp_path / "final.parquet").exists()


def test_resume_skip_detects_completed_game_ids(tmp_path):
    cdir = tmp_path / "chunks"
    cdir.mkdir()
    df0, _ = finalize_frame(_mk_rows("gA", [10, 11]) + _mk_rows("gB", [10]), None)
    df0.write_parquet(cdir / "chunk_0000.parquet")
    done, next_idx = completed_game_ids_from_chunks(cdir)
    assert done == {"gA", "gB"}
    assert next_idx == 1


def test_completed_ids_empty_when_no_chunks(tmp_path):
    cdir = tmp_path / "chunks"
    cdir.mkdir()
    done, next_idx = completed_game_ids_from_chunks(cdir)
    assert done == set()
    assert next_idx == 0


# ===========================================================================
# 16.1B — cross-time-control pilot support (safety-gated non-600+0)
# ===========================================================================

def test_canonicalize_time_control_aliases():
    assert canonicalize_time_control("3+0") == "180+0"
    assert canonicalize_time_control("5+0") == "300+0"
    assert canonicalize_time_control("10+0") == "600+0"
    assert canonicalize_time_control("10+5") == "600+5"
    assert canonicalize_time_control("180+0") == "180+0"   # canonical passes through
    assert canonicalize_time_control(None) is None


def test_canonicalize_time_control_rejects_malformed():
    for bad in ("abc", "180", "180+", "+0", "180-0", "3x0"):
        with pytest.raises(ValueError):
            canonicalize_time_control(bad)


_RAW_PGN = """\
[Event "Rated Blitz game"]
[Site "https://lichess.org/aaa11111"]
[White "u1"]
[Black "u2"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1480"]
[TimeControl "180+0"]
[Termination "Normal"]

1. e4 {[%clk 0:03:00]} e5 {[%clk 0:03:00]} 2. Nf3 {[%clk 0:02:58]} Nc6 {[%clk 0:02:57]} 1-0

[Event "Rated Blitz game"]
[Site "https://lichess.org/bbb22222"]
[White "u3"]
[Black "u4"]
[Result "0-1"]
[WhiteElo "1600"]
[BlackElo "1620"]
[TimeControl "300+0"]
[Termination "Time forfeit"]

1. d4 {[%clk 0:05:00]} d5 {[%clk 0:05:00]} 0-1

[Event "Rated Rapid game"]
[Site "https://lichess.org/ccc33333"]
[White "u5"]
[Black "u6"]
[Result "1/2-1/2"]
[WhiteElo "1700"]
[BlackElo "1700"]
[TimeControl "600+0"]
[Termination "Normal"]

1. c4 {[%clk 0:10:00]} c5 {[%clk 0:10:00]} 1/2-1/2
"""


def test_build_accepted_meta_from_raw_filters_time_control(tmp_path):
    p = tmp_path / "mix.pgn"
    p.write_text(_RAW_PGN)
    m180 = build_accepted_meta_from_raw(p, "180+0", max_games=100)
    assert set(m180) == {"aaa11111"}
    assert m180["aaa11111"]["result_class"] == "WHITE_WIN"
    assert m180["aaa11111"]["time_control"] == "180+0"
    assert m180["aaa11111"]["is_time_forfeit"] is False
    assert m180["aaa11111"]["white_elo"] == 1500
    assert m180["aaa11111"]["split_set"] == "unknown"
    m300 = build_accepted_meta_from_raw(p, "300+0", max_games=100)
    assert set(m300) == {"bbb22222"}
    assert m300["bbb22222"]["is_time_forfeit"] is True   # Time forfeit
    assert m300["bbb22222"]["result_class"] == "BLACK_WIN"


def test_build_accepted_meta_from_raw_caps(tmp_path):
    # duplicate the 180+0 game id-varied; cap at 1 should return a single game
    pgn = _RAW_PGN + _RAW_PGN.replace("aaa11111", "aaa99999")
    p = tmp_path / "dup.pgn"; p.write_text(pgn)
    m = build_accepted_meta_from_raw(p, "180+0", max_games=1)
    assert len(m) == 1


def test_build_accepted_meta_from_raw_no_username_fields(tmp_path):
    p = tmp_path / "mix.pgn"; p.write_text(_RAW_PGN)
    m = build_accepted_meta_from_raw(p, "180+0", max_games=100)
    for rec in m.values():
        assert not ({"white", "black", "White", "Black", "u1", "u2"} & set(rec))


def test_assemble_row_time_control_fields_for_180_0():
    meta = {**_META, "time_control": "180+0"}
    rec = _rec(20, 11, True)
    rec["clock_before_s"] = 90.0
    row = assemble_row("g", "2024_09", rec, meta, _eval(50), _eval(20), 12, 348.41)
    assert row["time_control_raw"] == "180+0"
    assert row["initial_time_s"] == 180
    assert row["increment_s"] == 0
    assert row["time_control_family"] == "no_increment"
    assert row["clock_fraction"] == 90.0 / 180   # uses initial_time_s, not hardcoded 600


# --- CLI safety gates for non-600+0 ---

def test_cli_refuses_non_600_0_without_pilot_gate(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--time-control", "180+0",
        "--max-accepted-games", "1500", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "allow-time-control-pilot" in capsys.readouterr().err


def test_cli_refuses_non_600_0_malformed_tc(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--time-control", "3x0",
        "--allow-time-control-pilot", "--out", str(tmp_path / "x.parquet"),
        "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "malformed time control" in capsys.readouterr().err


def test_cli_refuses_non_600_0_over_pilot_cap(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--time-control", "180+0",
        "--allow-time-control-pilot", "--max-accepted-games", "999999",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "pilot cap" in capsys.readouterr().err


def test_cli_refuses_non_600_0_with_preflight(tmp_path, capsys):
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--time-control", "300+0",
        "--allow-time-control-pilot", "--preflight",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "600+0-specific" in capsys.readouterr().err


def test_cli_full_month_still_refuses_non_600_0(tmp_path, capsys):
    # full-month + non-600+0 is refused; with the pilot gate present it reaches the
    # full-month "restricted to 600+0" gate (without it, the non-anchor gate refuses first).
    rc = dense_main([
        "--raw-pgn", "x.pgn", "--month", "2024_09", "--allow-full-month-2024-09",
        "--allow-time-control-pilot", "--time-control", "180+0", "--depth", "12",
        "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
    ])
    assert rc == 2
    assert "restricted to 600+0" in capsys.readouterr().err


def test_cli_non_600_0_pilot_gate_passes_then_fails_on_inputs(tmp_path):
    # with the gate + canonical alias + cap, the run passes the gates and then fails
    # later on the missing PGN / stockfish (proves the gate itself accepted it).
    with pytest.raises(Exception):
        dense_main([
            "--raw-pgn", "nonexistent.pgn", "--month", "2024_09", "--time-control", "3+0",
            "--allow-time-control-pilot", "--max-accepted-games", "1500",
            "--stockfish-path", "/nonexistent/stockfish",
            "--out", str(tmp_path / "x.parquet"), "--report", str(tmp_path / "x.md"),
        ])
