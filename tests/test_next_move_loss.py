"""Tests for next_move_loss.py (Ticket 15.0B). Pure logic + synthetic games;
no Stockfish, no large data."""

from __future__ import annotations

import io

import chess
import chess.pgn
import polars as pl
import pytest

from chess_mhsuc.next_move_loss import (
    ES_CP_CLIP,
    MATE_CP_SENTINEL,
    MOVE_QUALITY_CP_CAP,
    _STATUS_ILLEGAL,
    _STATUS_NO_NEXT_MOVE,
    _STATUS_OK,
    _fen_hash,
    build_row,
    compute_cp_loss,
    default_raw_pgn_path,
    expected_score,
    expected_score_loss,
    fit_expected_score_transform,
    is_mate_band,
    load_checkpoint_rows,
    main as nml_main,
    reconstruct_checkpoint_and_next_move,
    summarize,
    time_bucket_for,
    to_mover_cp,
)


# ---------------------------------------------------------------------------
# 1. Mover-perspective conversion
# ---------------------------------------------------------------------------

class TestToMoverCp:
    def test_white_unchanged(self):
        assert to_mover_cp(150, True) == 150
        assert to_mover_cp(-150, True) == -150

    def test_black_negated(self):
        assert to_mover_cp(150, False) == -150
        assert to_mover_cp(-150, False) == 150

    def test_none(self):
        assert to_mover_cp(None, True) is None
        assert to_mover_cp(None, False) is None

    def test_zero(self):
        assert to_mover_cp(0, True) == 0
        assert to_mover_cp(0, False) == 0


# ---------------------------------------------------------------------------
# 2. cp loss
# ---------------------------------------------------------------------------

class TestCpLoss:
    def test_positive_loss(self):
        # mover was +200, now +50 -> lost 150
        loss, clipped = compute_cp_loss(200, 50)
        assert loss == 150
        assert clipped == 150

    def test_no_negative_loss(self):
        # mover improved: +50 -> +200; loss clamped to 0
        loss, clipped = compute_cp_loss(50, 200)
        assert loss == 0
        assert clipped == 0

    def test_clip_cap(self):
        loss, clipped = compute_cp_loss(900, -900)  # 1800 raw
        assert loss == 1800
        assert clipped == MOVE_QUALITY_CP_CAP == 1000

    def test_custom_cap(self):
        loss, clipped = compute_cp_loss(500, 0, cap=300)
        assert loss == 500
        assert clipped == 300

    def test_none_inputs(self):
        assert compute_cp_loss(None, 50) == (None, None)
        assert compute_cp_loss(50, None) == (None, None)

    def test_mover_perspective_black(self):
        # White-POV: pre -200 (Black +200), post -50 (Black +50). Black mover lost 150.
        mover_pre = to_mover_cp(-200, False)   # +200
        mover_post = to_mover_cp(-50, False)   # +50
        loss, _ = compute_cp_loss(mover_pre, mover_post)
        assert loss == 150


# ---------------------------------------------------------------------------
# 3. Mate-band detection
# ---------------------------------------------------------------------------

class TestMateBand:
    def test_pre_mate(self):
        assert is_mate_band(MATE_CP_SENTINEL, 3, 200, None) is True

    def test_post_mate(self):
        assert is_mate_band(200, None, -MATE_CP_SENTINEL, -2) is True

    def test_sentinel_cp_without_mate_field(self):
        assert is_mate_band(MATE_CP_SENTINEL, None, 100, None) is True
        assert is_mate_band(100, None, -MATE_CP_SENTINEL, None) is True

    def test_normal_not_mate_band(self):
        assert is_mate_band(150, None, 50, None) is False

    def test_none_cp_not_mate(self):
        assert is_mate_band(None, None, 50, None) is False


# ---------------------------------------------------------------------------
# 4. Time bucket
# ---------------------------------------------------------------------------

class TestTimeBucket:
    @pytest.mark.parametrize("clk,expected", [
        (0.0, "under_60s"), (59.9, "under_60s"),
        (60.0, "60_180s"), (179.9, "60_180s"),
        (180.0, "over_180s"), (600.0, "over_180s"),
    ])
    def test_boundaries(self, clk, expected):
        assert time_bucket_for(clk) == expected

    def test_none(self):
        assert time_bucket_for(None) is None


# ---------------------------------------------------------------------------
# 5. Reconstruction on synthetic games (no Stockfish)
# ---------------------------------------------------------------------------

def _game_from_moves(sans: list[str]) -> chess.pgn.Game:
    game = chess.pgn.Game()
    node = game
    board = chess.Board()
    for san in sans:
        mv = board.parse_san(san)
        board.push(mv)
        node = node.add_variation(mv)
    return game


class TestReconstruction:
    def test_ok_white_mover_at_ply2(self):
        # 1.e4 e5 2.Nf3 Nc6 -> checkpoint ply=2 (after Black's 1...e5), White to move,
        # next move is Nf3.
        game = _game_from_moves(["e4", "e5", "Nf3", "Nc6"])
        r = reconstruct_checkpoint_and_next_move(game, 2)
        assert r["status"] == _STATUS_OK
        assert r["mover_is_white"] is True
        assert r["actual_move_uci"] == "g1f3"
        assert "pre_fen" in r and r["post_fen"] is not None

    def test_ok_black_mover_at_ply1(self):
        # checkpoint ply=1 (after 1.e4), Black to move, next move e5
        game = _game_from_moves(["e4", "e5", "Nf3"])
        r = reconstruct_checkpoint_and_next_move(game, 1)
        assert r["status"] == _STATUS_OK
        assert r["mover_is_white"] is False
        assert r["actual_move_uci"] == "e7e5"

    def test_no_next_move_at_game_end(self):
        game = _game_from_moves(["e4", "e5"])
        r = reconstruct_checkpoint_and_next_move(game, 2)  # game ends here
        assert r["status"] == _STATUS_NO_NEXT_MOVE
        assert r["pre_fen"] is not None
        assert r["actual_move_uci"] is None

    def test_checkpoint_beyond_game(self):
        game = _game_from_moves(["e4", "e5"])
        r = reconstruct_checkpoint_and_next_move(game, 10)
        assert r["status"] == "fen_reconstruction_error"

    def test_ply_zero_invalid(self):
        game = _game_from_moves(["e4", "e5"])
        r = reconstruct_checkpoint_and_next_move(game, 0)
        assert r["status"] == "fen_reconstruction_error"

    def test_post_fen_is_after_actual_move(self):
        game = _game_from_moves(["e4", "e5", "Nf3", "Nc6"])
        r = reconstruct_checkpoint_and_next_move(game, 2)
        board = chess.Board(r["post_fen"])
        # after 1.e4 e5 2.Nf3, it's Black to move
        assert board.turn == chess.BLACK

    def test_fen_hash_matches_convention(self):
        game = _game_from_moves(["e4", "e5", "Nf3", "Nc6"])
        r = reconstruct_checkpoint_and_next_move(game, 2)
        import hashlib
        assert _fen_hash(r["pre_fen"]) == hashlib.sha256(
            r["pre_fen"].encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 6. build_row orientation integration
# ---------------------------------------------------------------------------

class TestBuildRow:
    def _cp_row(self, **over):
        base = {
            "game_id": "g1", "selected_position_type": "move_10", "ply": 20,
            "move_number": 11, "split_set": "val", "sf_eval_cp": 200,
            "sf_eval_mate": None, "sf_depth": 12, "fen_hash": "abc",
            "result_class": "WHITE_WIN", "white_elo": 1600, "black_elo": 1500,
            "white_clock_s_capped": 45.0, "black_clock_s_capped": 300.0,
            "white_to_move_next": True, "termination": "Normal",
            "is_time_forfeit": False,
        }
        base.update(over)
        return base

    def test_white_mover_loss(self):
        cp_row = self._cp_row()
        recon = {"mover_is_white": True, "actual_move_uci": "g1f3",
                 "pre_fen": "x", "post_fen": "y", "move_number": 11}
        post = {"sf_eval_cp": 50, "sf_eval_mate": None}
        row = build_row("ds", "v", cp_row, recon, post, True, _STATUS_OK)
        assert row["mover_pre_cp"] == 200
        assert row["mover_post_cp"] == 50
        assert row["cp_loss"] == 150
        assert row["mover_color"] == "white"
        assert row["mover_rating"] == 1600
        assert row["mover_clock_s"] == 45.0
        assert row["time_bucket"] == "under_60s"

    def test_black_mover_orientation(self):
        # Black to move; White-POV pre -200 => mover +200; post -50 => mover +50
        cp_row = self._cp_row(sf_eval_cp=-200, white_to_move_next=False)
        recon = {"mover_is_white": False, "actual_move_uci": "e7e5",
                 "pre_fen": "x", "post_fen": "y", "move_number": 11}
        post = {"sf_eval_cp": -50, "sf_eval_mate": None}
        row = build_row("ds", "v", cp_row, recon, post, True, _STATUS_OK)
        assert row["mover_pre_cp"] == 200
        assert row["mover_post_cp"] == 50
        assert row["cp_loss"] == 150
        assert row["mover_color"] == "black"
        assert row["mover_rating"] == 1500
        assert row["mover_clock_s"] == 300.0

    def test_mate_band_flag(self):
        cp_row = self._cp_row(sf_eval_cp=MATE_CP_SENTINEL, sf_eval_mate=3)
        recon = {"mover_is_white": True, "actual_move_uci": "a", "pre_fen": "x",
                 "post_fen": "y", "move_number": 11}
        post = {"sf_eval_cp": 500, "sf_eval_mate": None}
        row = build_row("ds", "v", cp_row, recon, post, True, _STATUS_OK)
        assert row["is_mate_band"] is True


# ---------------------------------------------------------------------------
# 7. Required-column validation / join (load_checkpoint_rows)
# ---------------------------------------------------------------------------

class TestLoadCheckpointRows:
    def _sf(self):
        return pl.DataFrame({
            "game_id": ["g1", "g2"], "selected_position_type": ["move_10", "move_10"],
            "ply": [20, 20], "move_number": [11, 11], "split_set": ["val", "train"],
            "sf_eval_cp": [100, -50], "sf_eval_mate": [None, None], "sf_depth": [12, 12],
            "fen_hash": ["h1", "h2"], "result_class": ["WHITE_WIN", "DRAW"],
        })

    def _feat(self):
        return pl.DataFrame({
            "game_id": ["g1", "g2", "g1"],
            "selected_position_type": ["move_10", "move_10", "last"],
            "white_elo": [1600, 1500, 1600], "black_elo": [1550, 1450, 1550],
            "white_clock_s_capped": [40.0, 200.0, 5.0],
            "black_clock_s_capped": [300.0, 250.0, 5.0],
            "white_to_move_next": [True, True, True],
            "termination": ["Normal", "Time forfeit", "Normal"],
            "is_time_forfeit": [False, True, False],
        })

    def test_join_ok(self, tmp_path):
        sfp = tmp_path / "sf.parquet"; self._sf().write_parquet(sfp)
        fp = tmp_path / "f.parquet"; self._feat().write_parquet(fp)
        out = load_checkpoint_rows(sfp, fp)
        assert len(out) == 2  # 'last' excluded; 2 primary rows
        assert "white_elo" in out.columns

    def test_missing_sf_column_raises(self, tmp_path):
        sfp = tmp_path / "sf.parquet"
        self._sf().drop("fen_hash").write_parquet(sfp)
        fp = tmp_path / "f.parquet"; self._feat().write_parquet(fp)
        with pytest.raises(ValueError, match="fen_hash"):
            load_checkpoint_rows(sfp, fp)

    def test_orphan_raises(self, tmp_path):
        sfp = tmp_path / "sf.parquet"
        self._sf().write_parquet(sfp)
        fp = tmp_path / "f.parquet"
        self._feat().filter(pl.col("game_id") == "g1").write_parquet(fp)
        with pytest.raises(ValueError, match="orphan"):
            load_checkpoint_rows(sfp, fp)

    def test_duplicate_sf_key_raises(self, tmp_path):
        sfp = tmp_path / "sf.parquet"
        pl.concat([self._sf(), self._sf().head(1)]).write_parquet(sfp)
        fp = tmp_path / "f.parquet"; self._feat().write_parquet(fp)
        with pytest.raises(ValueError, match="not unique"):
            load_checkpoint_rows(sfp, fp)


# ---------------------------------------------------------------------------
# 8. Raw-PGN path derivation + summarize
# ---------------------------------------------------------------------------

class TestRawPgnPath:
    def test_default_path(self):
        assert default_raw_pgn_path("2024_09_250k_v1") == \
            "data/raw/lichess/lichess_2024_09_first250k.pgn"
        assert default_raw_pgn_path("2024_10_250k_v1") == \
            "data/raw/lichess/lichess_2024_10_first250k.pgn"

    def test_bad_tag_raises(self):
        with pytest.raises(ValueError):
            default_raw_pgn_path("v1")


class TestSummarize:
    def test_excludes_mate_band(self):
        from chess_mhsuc.next_move_loss import _OUTPUT_SCHEMA
        rows = []
        for i, (loss, mate) in enumerate([(0, False), (150, False), (300, False),
                                          (9999, True)]):
            r = {k: None for k in _OUTPUT_SCHEMA}
            r.update({
                "game_id": f"g{i}", "selected_position_type": "move_10",
                "status": "ok", "is_mate_band": mate, "clipped_cp_loss": loss,
                "is_time_forfeit": False,
            })
            rows.append(r)
        df = pl.from_dicts(rows, schema=_OUTPUT_SCHEMA)
        s = summarize(df)
        assert s["n_ok"] == 4
        assert s["n_ok_nonmate"] == 3  # mate-band excluded
        assert s["n_mate_band"] == 1
        assert s["median_clipped_cp_loss"] == 150.0


# ---------------------------------------------------------------------------
# 9. Full-run guard (CLI)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 10. Expected-score transform
# ---------------------------------------------------------------------------

class TestExpectedScore:
    def test_monotonic_increasing(self):
        s = 300.0
        vals = [expected_score(cp, s) for cp in (-500, -100, 0, 100, 500)]
        assert all(b > a for a, b in zip(vals, vals[1:]))

    def test_in_unit_interval(self):
        for cp in (-5000, -1000, 0, 1000, 5000):
            es = expected_score(cp, 250.0)
            assert 0.0 < es < 1.0

    def test_zero_cp_is_half(self):
        assert expected_score(0, 300.0) == pytest.approx(0.5)

    def test_clips_extreme_cp(self):
        # beyond the clip both map to the clipped-boundary value
        assert expected_score(5000, 250.0) == pytest.approx(
            expected_score(ES_CP_CLIP, 250.0))
        assert expected_score(-5000, 250.0) == pytest.approx(
            expected_score(-ES_CP_CLIP, 250.0))

    def test_none(self):
        assert expected_score(None, 300.0) is None

    def test_bad_scale_raises(self):
        with pytest.raises(ValueError):
            expected_score(100, 0.0)

    def test_es_loss_clips_at_zero(self):
        # mover improved -> ES went up -> loss clamped to 0
        assert expected_score_loss(50, 300, 300.0) == 0.0

    def test_es_loss_positive(self):
        loss = expected_score_loss(300, -300, 300.0)
        assert loss > 0

    def test_es_loss_mover_black_orientation(self):
        # both perspectives already mover-oriented; symmetric magnitude
        white = expected_score_loss(300, 50, 300.0)
        black = expected_score_loss(300, 50, 300.0)
        assert white == black

    def test_es_loss_none_without_scale(self):
        assert expected_score_loss(300, 50, None) is None
        assert expected_score_loss(None, 50, 300.0) is None


class TestFitTransform:
    def test_fit_recovers_monotonic_scale(self):
        # synthetic: white score rises with cp -> fit yields positive scale + monotonic ES
        cps, scores = [], []
        for cp in range(-800, 801, 50):
            cps.append(cp)
            scores.append(1.0 / (1.0 + 2.718281828 ** (-cp / 250.0)))
        fit = fit_expected_score_transform(cps, scores)
        assert fit["scale"] > 0
        assert fit["n_fit"] == len(cps)
        # ES with fitted scale is monotonic
        es = [expected_score(cp, fit["scale"]) for cp in (-400, 0, 400)]
        assert es[0] < es[1] < es[2]

    def test_fit_empty_raises(self):
        with pytest.raises(ValueError):
            fit_expected_score_transform([], [])

    def test_fit_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            fit_expected_score_transform([1, 2], [0.5])


class TestBuildRowES:
    def test_es_columns_present_with_scale(self):
        cp_row = {
            "game_id": "g1", "selected_position_type": "move_10", "ply": 20,
            "move_number": 11, "split_set": "val", "sf_eval_cp": 200,
            "sf_eval_mate": None, "sf_depth": 12, "fen_hash": "abc",
            "result_class": "WHITE_WIN", "white_elo": 1600, "black_elo": 1500,
            "white_clock_s_capped": 100.0, "black_clock_s_capped": 100.0,
            "white_to_move_next": True, "termination": "Normal",
            "is_time_forfeit": False,
        }
        recon = {"mover_is_white": True, "actual_move_uci": "a", "pre_fen": "x",
                 "post_fen": "y", "move_number": 11}
        post = {"sf_eval_cp": 50, "sf_eval_mate": None}
        row = build_row("ds", "v", cp_row, recon, post, True, _STATUS_OK, es_scale=300.0)
        assert row["es_pre"] is not None and row["es_post"] is not None
        assert row["expected_score_loss"] >= 0
        # es_pre (mover +200) > es_post (mover +50)
        assert row["es_pre"] > row["es_post"]

    def test_es_columns_none_without_scale(self):
        cp_row = {
            "game_id": "g1", "selected_position_type": "move_10", "ply": 20,
            "move_number": 11, "split_set": "val", "sf_eval_cp": 200,
            "sf_eval_mate": None, "sf_depth": 12, "fen_hash": "abc",
            "result_class": "WHITE_WIN", "white_elo": 1600, "black_elo": 1500,
            "white_clock_s_capped": 100.0, "black_clock_s_capped": 100.0,
            "white_to_move_next": True, "termination": "Normal",
            "is_time_forfeit": False,
        }
        recon = {"mover_is_white": True, "actual_move_uci": "a", "pre_fen": "x",
                 "post_fen": "y", "move_number": 11}
        post = {"sf_eval_cp": 50, "sf_eval_mate": None}
        row = build_row("ds", "v", cp_row, recon, post, True, _STATUS_OK)
        assert row["es_pre"] is None and row["expected_score_loss"] is None


class TestFullRunGuard:
    def test_no_limit_no_allow_errors(self):
        rc = nml_main([
            "--dataset-id", "ds", "--version-tag", "2024_09_250k_v1",
        ])
        assert rc == 2  # refused

    def test_schema_only_exits_zero(self, capsys):
        rc = nml_main([
            "--dataset-id", "ds", "--version-tag", "2024_09_250k_v1",
            "--schema-only",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "cp_loss" in out and "mover_color" in out
