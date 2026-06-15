"""Tests for multipv_sharpness.py (Ticket 14.1B). No engine calls."""

from __future__ import annotations

import chess
import chess.engine
import numpy as np
import polars as pl
import pytest

from chess_mhsuc import multipv_sharpness as ms


# ---------------------------------------------------------------------------
# Input validation + sampling
# ---------------------------------------------------------------------------

def _synth_input(n_per=300, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    start = chess.Board().fen()
    for cp in ms.CHECKPOINTS:
        for _ in range(n_per):
            rows.append({
                "game_id": f"g{rng.integers(0, 100000)}",
                "selected_position_type": cp,
                "pre_fen": start,
                "mover_color": "white",
                "pre_sf_eval_cp": int(rng.integers(-50, 50)),
                "is_mate_band": False,
                "status": "ok",
            })
    return pl.DataFrame(rows)


def test_load_pilot_input_validates_columns(tmp_path):
    bad = tmp_path / "bad.parquet"
    pl.DataFrame({"game_id": ["x"], "status": ["ok"]}).write_parquet(bad)
    with pytest.raises(ValueError, match="missing required columns"):
        ms.load_pilot_input(bad)


def test_stratified_sample_counts():
    df = _synth_input(300)
    s = ms.stratified_sample(df, size=1000, seed=42)
    assert s.height == 1000
    counts = {r["selected_position_type"]: r["len"]
              for r in s.group_by("selected_position_type").len().to_dicts()}
    assert all(counts[c] == 250 for c in ms.CHECKPOINTS)


def test_stratified_sample_deterministic():
    df = _synth_input(300)
    a = ms.stratified_sample(df, 1000, 7)["game_id"].to_list()
    b = ms.stratified_sample(df, 1000, 7)["game_id"].to_list()
    assert a == b


# ---------------------------------------------------------------------------
# Score orientation
# ---------------------------------------------------------------------------

def test_relative_score_white_to_move():
    # +120 cp for White, White to move -> mover_cp positive
    sc = chess.engine.PovScore(chess.engine.Cp(120), chess.WHITE)
    cp, mate = ms.relative_score_to_mover(sc)
    assert cp == 120 and mate is None


def test_relative_score_black_to_move():
    # PovScore(relative, turn): relative -120 for Black (= White +120), Black to
    # move -> mover (Black) sees -120; White-POV is +120.
    sc = chess.engine.PovScore(chess.engine.Cp(-120), chess.BLACK)
    cp, mate = ms.relative_score_to_mover(sc)
    assert cp == -120
    from chess_mhsuc.stockfish_eval import score_to_white_pov
    assert score_to_white_pov(sc)[0] == 120


def test_relative_score_mate():
    sc = chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)
    cp, mate = ms.relative_score_to_mover(sc)
    assert cp == ms.MATE_CP_SENTINEL and mate == 3


# ---------------------------------------------------------------------------
# Expected-score conversion
# ---------------------------------------------------------------------------

def test_candidate_es_bounded_and_monotone():
    lo = ms.candidate_es(-400, ms.DEFAULT_SCALE)
    mid = ms.candidate_es(0, ms.DEFAULT_SCALE)
    hi = ms.candidate_es(400, ms.DEFAULT_SCALE)
    assert 0.0 < lo < mid < hi < 1.0
    assert mid == pytest.approx(0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Fragility features
# ---------------------------------------------------------------------------

def test_count_within_threshold_and_censoring():
    # best ES 0.60, others within/outside 0.10
    es = [0.60, 0.58, 0.55, 0.40, 0.30]
    cp = [120, 100, 80, 0, -50]
    f = ms.fragility_features(es, cp, k=5)
    assert f["n_good_5es"] == 3          # losses 0,.02,.05 <= .05
    assert f["n_good_10es"] == 3
    assert f["n_good_20es"] == 4
    assert f["n_good_10es_censored_at_k"] is False


def test_censoring_flag_when_all_within():
    es = [0.50, 0.49, 0.48, 0.47, 0.46]  # all within 0.10 of best
    cp = [10, 8, 6, 4, 2]
    f = ms.fragility_features(es, cp, k=5)
    assert f["n_good_10es"] == 5
    assert f["n_good_10es_censored_at_k"] is True


def test_dropoff_features():
    es = [0.70, 0.60, 0.40, 0.35, 0.30]
    cp = [200, 120, 30, 10, -10]
    f = ms.fragility_features(es, cp, k=5)
    assert f["best_second_gap_es"] == pytest.approx(0.10)
    assert f["best_third_gap_es"] == pytest.approx(0.30)
    assert f["worst_top5_loss_es"] == pytest.approx(0.40)
    assert f["max_adjacent_gap_es"] == pytest.approx(0.20)  # 0.60->0.40
    assert f["best_second_gap_cp"] == 80


def test_entropy_concentration():
    f = ms.fragility_features([0.5, 0.5, 0.5], [0, 0, 0], k=5)
    # equal values -> uniform softmax -> concentration ~ 1/3 (values rounded to 5dp)
    assert f["top5_concentration_es"] == pytest.approx(1 / 3, abs=1e-4)
    assert f["top1_softmax_prob_es"] == pytest.approx(1 / 3, abs=1e-4)


def test_fragility_empty():
    assert ms.fragility_features([], [], k=5) == {"multipv_count": 0}


# ---------------------------------------------------------------------------
# Clutter
# ---------------------------------------------------------------------------

def test_clutter_lower_bounds():
    c = ms.clutter_features(n_good_10es=2, n_good_20es=3, legal_move_count=20)
    assert c["legal_move_count"] == 20
    assert c["viable_fraction_10es_lower_bound"] == pytest.approx(0.10)
    assert c["viable_fraction_20es_lower_bound"] == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# Move tags
# ---------------------------------------------------------------------------

def test_move_tags_capture_and_quiet():
    # 1.e4 d5 2.exd5 -> exd5 is a capture
    board = chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2")
    cap = chess.Move.from_uci("e4d5")
    t = ms.move_tags(board, cap)
    assert t["is_capture"] and not t["is_quiet"]
    assert t["captured_piece_type"] == chess.PAWN
    assert t["moved_piece_type"] == chess.PAWN
    quiet = chess.Move.from_uci("g1f3")
    tq = ms.move_tags(board, quiet)
    assert tq["is_quiet"] and not tq["is_capture"]


def test_move_tags_check_and_promotion():
    # White pawn e7 promotes to Qe8, giving check to the Black king on g8
    # along the empty 8th rank.
    board = chess.Board("6k1/4P3/8/8/8/8/8/4K3 w - - 0 1")
    promo = chess.Move.from_uci("e7e8q")
    t = ms.move_tags(board, promo)
    assert t["is_promotion"] and t["is_legal"]
    assert t["is_check"]


def test_position_choice_context_in_check():
    # Black king in check from a rook, limited evasions
    board = chess.Board("4k3/8/8/8/8/8/8/4R1K1 b - - 0 1")
    ctx = ms.position_choice_context(board)
    assert ctx["in_check"] is True
    assert ctx["n_legal_evasions"] == ctx["legal_move_count"] >= 1


# ---------------------------------------------------------------------------
# Surface-bait + composites
# ---------------------------------------------------------------------------

def _tags(check=False, cap=False, promo=False, quiet=False):
    return {"is_check": check, "is_capture": cap, "is_promotion": promo, "is_quiet": quiet,
            "is_legal": True, "moved_piece_type": 1, "captured_piece_type": None,
            "is_recapture": None}


def test_surface_bait_detects_bad_forcing_move():
    # best move quiet (loss 0); a capture exists but loses 0.15
    tags = [_tags(quiet=True), _tags(cap=True), _tags(quiet=True)]
    loss = [0.0, 0.15, 0.05]
    s = ms.surface_bait(tags, loss)
    assert s["surface_move_available_top5"] is True
    assert s["best_surface_loss_es"] == pytest.approx(0.15)
    assert s["surface_bait_10es"] is True
    assert s["best_move_is_quiet"] is True
    assert s["best_move_quiet_surface_bad_10es"] is True


def test_surface_bait_none_when_best_is_surface():
    tags = [_tags(cap=True), _tags(quiet=True)]
    loss = [0.0, 0.20]
    s = ms.surface_bait(tags, loss)
    assert s["best_move_is_surface"] is True
    assert s["best_surface_loss_es"] == pytest.approx(0.0)
    assert s["surface_bait_10es"] is False


def test_composites_value_fragility():
    frag = {"n_good_5es": 1, "n_good_10es": 2, "n_good_20es": 2,
            "worst_top5_loss_es": 0.15, "legal_move_count": 12,
            "best_second_gap_es": 0.08}
    surf = {"surface_bait_10es": False, "best_move_is_quiet": False}
    c = ms.composites(frag, surf)
    assert c["sharp_value_fragility_v1"] is True
    assert c["sharp_score_candidate"] == 0.08


def test_composites_not_sharp_when_many_good():
    frag = {"n_good_5es": 4, "n_good_10es": 5, "n_good_20es": 5,
            "worst_top5_loss_es": 0.02, "legal_move_count": 30,
            "best_second_gap_es": 0.0}
    c = ms.composites(frag, {"surface_bait_10es": False, "best_move_is_quiet": True})
    assert c["sharp_value_fragility_v1"] is False


# ---------------------------------------------------------------------------
# Report privacy / CLI
# ---------------------------------------------------------------------------

def test_report_excludes_pgn_and_usernames():
    df = pl.DataFrame({
        "ok": [True, True], "is_mate_band": [False, False],
        "fen_hash_matches": [True, True], "all_candidates_legal": [True, True],
        "top1_cp_abs_diff": [3, 5], "multipv_count": [5, 5],
        "sharp_value_fragility_v1": [True, False], "surface_bait_10es": [False, True],
        "best_move_is_quiet": [True, False], "best_second_gap_es": [0.05, 0.02],
        "n_good_10es": [2, 4], "ctx_legal_move_count": [20, 25],
    })
    md = ms.render_report("synth_v1", df, None, {}, {12: {"sec": 1.0, "n": 2, "ms": 500.0}},
                          "stockfish 16", 5, ms.DEFAULT_SCALE)
    assert "MultiPV Sharpness Pilot" in md
    assert "human obviousness" in md.lower()  # must appear as a NEGATED/deferral statement
    assert "1." in md and "pgn" not in md.lower().replace("pgn text", "")


def _extracted_frame(n=8):
    rng = np.random.default_rng(0)
    return pl.DataFrame({
        "game_id": [f"g{i}" for i in range(n)],
        "selected_position_type": [ms.CHECKPOINTS[i % 4] for i in range(n)],
        "status": ["ok"] * n, "ok": [True] * n, "is_mate_band": [False] * n,
        "multipv_k": [5] * n, "multipv_count": [5, 5, 4, 5, 3, 5, 5, 5][:n],
        "fen_hash_matches": [True] * n, "all_candidates_legal": [True] * n,
        "top1_cp_abs_diff": list(rng.integers(0, 30, n)),
        "n_good_10es": [2, 5, 1, 4, 3, 5, 2, 5][:n],
        "best_second_gap_es": [0.02, 0.0, 0.12, 0.01, 0.05, 0.0, 0.08, 0.0][:n],
        "worst_top5_loss_es": [0.12, 0.02, 0.30, 0.04, 0.10, 0.02, 0.15, 0.01][:n],
        "ctx_legal_move_count": [20, 30, 12, 25, 18, 32, 15, 28][:n],
        "sharp_value_fragility_v1": [True, False, True, False, False, False, True, False][:n],
        "sharp_value_fragility_v1_relaxed": [True, False, True, False, False, False, True, False][:n],
        "sharp_value_fragility_v1_strict": [False, False, True, False, False, False, False, False][:n],
        "surface_bait_10es": [False, False, True, False, False, False, True, False][:n],
        "surface_bait_20es": [False, False, True, False, False, False, False, False][:n],
        "best_move_is_quiet": [True, True, False, True, False, True, True, True][:n],
        "pv1_is_check": [False] * n, "pv1_is_capture": [False, True, False, True, False, False, True, False][:n],
        "pv1_is_promotion": [False] * n,
    })


def test_full_summary_and_report():
    df = _extracted_frame(8)
    s = ms.full_summary(df)
    assert s["n_ok"] == 8 and s["n_nonmate"] == 8
    assert s["share_lt_k_legal"] == pytest.approx(2 / 8)  # two rows with count<5
    assert "by_checkpoint" in s and set(s["by_checkpoint"]) == set(ms.CHECKPOINTS)
    md = ms.render_month_full_report("synth_v1", df, {12: {"sec": 60.0, "n": 8, "ms": 100.0}},
                                     "stockfish 18", 5, ms.DEFAULT_SCALE)
    assert "Full Sharpness Extraction" in md
    assert "human obviousness" in md.lower()  # appears only in the negated caveat
    assert "No raw PGN" in md  # schema privacy disclaimer present
    # no per-row FEN strings (board layouts) leak into the aggregate report
    import re
    assert not re.search(r"/[pnbrqkPNBRQK1-8]+/[pnbrqkPNBRQK1-8]+/", md)


def test_combined_report_renders():
    df = _extracted_frame(8)
    s = ms.full_summary(df)
    md = ms.render_combined_full_report(
        ["2024_09_250k_v1", "2024_10_250k_v1"], [s, s],
        [{12: {"sec": 60.0, "n": 8, "ms": 100.0}}, {12: {"sec": 60.0, "n": 8, "ms": 100.0}}],
        "stockfish 18", 5)
    assert "MultiPV Sharpness Extraction — Combined" in md
    assert "NOT human obviousness" in md


def test_cli_parses(monkeypatch, tmp_path):
    import sys as _sys
    called = {}
    def fake(*a, **k):
        called["yes"] = True
        return 0
    # just ensure argparse wiring doesn't crash on --help-style minimal parse
    with pytest.raises(SystemExit):
        ms.main(["--help"])
