"""
tests/test_stockfish_eval.py — Unit tests for stockfish_eval.py.

All tests use synthetic PGNs and mocked engine objects.
No real Stockfish binary is required by any test.

Test categories:
  1. Stockfish path resolution (A)
  2. FEN reconstruction (F → E)
  3. Score to White POV conversion (G)
  4. Eval feature derivation (H)
  5. Position loading and filtering (C)
  6. Engine wrapper / analyse_fen (I)
  7. CLI / output schema / report (M, K)
  8. Resume behavior
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import chess
import chess.engine
import chess.pgn
import polars as pl
import pytest

# Make sure src/ is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chess_mhsuc.stockfish_eval import (
    MATE_CP_SENTINEL,
    DEFAULT_DEPTH,
    analyse_fen,
    build_metadata,
    derive_sf_eval_features,
    load_primary_numbered_positions,
    reconstruct_fen_at_ply,
    render_stockfish_eval_report,
    resolve_stockfish_path,
    run_stockfish_eval,
    score_to_white_pov,
    write_outputs,
    _extract_game_id,
    _EVAL_STATUS_OK_CP,
    _EVAL_STATUS_OK_MATE,
    _EVAL_STATUS_FEN_ERR,
    _EVAL_STATUS_ILLEGAL,
    _EVAL_STATUS_ENG_ERR,
    _EVAL_STATUS_SKIPPED,
    _OUTPUT_COLUMNS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SYNTHETIC_PGN_SHORT = """\
[Event "Test"]
[Site "https://lichess.org/test0001"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1500"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6
8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 1-0
"""

_SYNTHETIC_PGN_MINIMAL = """\
[Event "Minimal"]
[Site "https://lichess.org/mini0001"]
[Result "1/2-1/2"]

1. e4 e5 1/2-1/2
"""

_SYNTHETIC_PGN_THREEMOVE = """\
[Event "ThreeMove"]
[Site "https://lichess.org/three001"]
[Result "1-0"]

1. e4 c5 2. Nf3 1-0
"""


def _make_game_from_pgn(pgn_text: str) -> chess.pgn.Game:
    return chess.pgn.read_game(io.StringIO(pgn_text))


def _make_positions_df(rows: list[dict]) -> pl.DataFrame:
    """Create a minimal positions DataFrame for testing."""
    defaults = {
        "game_id": "test001",
        "ply": 20,
        "selected_position_type": "move_10",
        "move_number": 10,
        "result_class": "WHITE_WIN",
        "split_set": "val",
        "eval_cp": None,
        "eval_mate": None,
        "has_eval": False,
    }
    result = []
    for row in rows:
        r = {**defaults, **row}
        result.append(r)
    return pl.DataFrame(result)


def _fake_pov_score(cp: int | None = None, mate: int | None = None, white: bool = True) -> chess.engine.PovScore:
    """Create a PovScore mock."""
    if mate is not None:
        inner = chess.engine.Mate(mate)
    else:
        inner = chess.engine.Cp(cp if cp is not None else 0)
    if white:
        return chess.engine.PovScore(inner, chess.WHITE)
    else:
        return chess.engine.PovScore(inner, chess.BLACK)


# ---------------------------------------------------------------------------
# 1. Stockfish path resolution
# ---------------------------------------------------------------------------

class TestResolveStockfishPath:
    def test_explicit_path_wins(self, tmp_path):
        sf = tmp_path / "stockfish"
        sf.write_text("fake")
        result = resolve_stockfish_path(str(sf))
        assert result == str(sf)

    def test_env_var_fallback(self, tmp_path, monkeypatch):
        sf = tmp_path / "stockfish_env"
        sf.write_text("fake")
        monkeypatch.setenv("STOCKFISH_PATH", str(sf))
        result = resolve_stockfish_path(None)
        assert result == str(sf)

    def test_explicit_path_overrides_env(self, tmp_path, monkeypatch):
        sf_explicit = tmp_path / "explicit"
        sf_explicit.write_text("fake")
        sf_env = tmp_path / "from_env"
        sf_env.write_text("fake")
        monkeypatch.setenv("STOCKFISH_PATH", str(sf_env))
        result = resolve_stockfish_path(str(sf_explicit))
        assert result == str(sf_explicit)

    def test_which_fallback(self, tmp_path, monkeypatch):
        sf = tmp_path / "stockfish_which"
        sf.write_text("fake")
        monkeypatch.delenv("STOCKFISH_PATH", raising=False)
        with patch("shutil.which", return_value=str(sf)):
            result = resolve_stockfish_path(None)
        assert result == str(sf)

    def test_raises_if_absent(self, monkeypatch):
        monkeypatch.delenv("STOCKFISH_PATH", raising=False)
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="Stockfish binary not found"):
                resolve_stockfish_path(None)

    def test_raises_if_path_not_exists(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent_stockfish")
        with pytest.raises(FileNotFoundError, match="does not exist"):
            resolve_stockfish_path(fake_path)

    def test_clear_error_message_mentions_install(self, monkeypatch):
        monkeypatch.delenv("STOCKFISH_PATH", raising=False)
        with patch("shutil.which", return_value=None):
            try:
                resolve_stockfish_path(None)
            except FileNotFoundError as e:
                assert "install" in str(e).lower() or "stockfish" in str(e).lower()


# ---------------------------------------------------------------------------
# 2. FEN reconstruction
# ---------------------------------------------------------------------------

class TestReconstructFenAtPly:
    def test_ply1_after_e4(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_SHORT)
        fen, status = reconstruct_fen_at_ply(game, 1)
        assert fen is not None
        # After 1.e4, the e4 pawn is on e4, Black to move
        board = chess.Board(fen)
        assert board.piece_at(chess.E4) is not None
        assert board.turn == chess.BLACK

    def test_ply2_after_e4_e5(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_SHORT)
        fen, status = reconstruct_fen_at_ply(game, 2)
        assert fen is not None
        board = chess.Board(fen)
        # After 1.e4 e5, White to move
        assert board.turn == chess.WHITE
        assert board.piece_at(chess.E5) is not None

    def test_ply20_is_after_move10(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_SHORT)
        fen, status = reconstruct_fen_at_ply(game, 20)
        assert fen is not None
        # FEN string must be valid
        board = chess.Board(fen)
        assert board.ply() == 20

    def test_returns_none_if_ply_exceeds_game_length(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_MINIMAL)
        # Minimal game has 2 plies; request ply 100
        fen, status = reconstruct_fen_at_ply(game, 100)
        assert fen is None
        assert status == _EVAL_STATUS_FEN_ERR

    def test_invalid_ply_zero_returns_error(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_SHORT)
        fen, status = reconstruct_fen_at_ply(game, 0)
        assert fen is None
        assert status == _EVAL_STATUS_FEN_ERR

    def test_ply3_three_move_game(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_THREEMOVE)
        fen, status = reconstruct_fen_at_ply(game, 3)
        assert fen is not None
        board = chess.Board(fen)
        assert board.ply() == 3

    def test_ply_at_exact_game_end(self):
        # Minimal game: 1.e4 e5 = 2 plies
        game = _make_game_from_pgn(_SYNTHETIC_PGN_MINIMAL)
        fen, status = reconstruct_fen_at_ply(game, 2)
        assert fen is not None

    def test_fen_is_valid_chess_position(self):
        game = _make_game_from_pgn(_SYNTHETIC_PGN_SHORT)
        fen, _ = reconstruct_fen_at_ply(game, 10)
        assert fen is not None
        board = chess.Board(fen)
        assert board.is_valid()


# ---------------------------------------------------------------------------
# 3. Score to White POV conversion
# ---------------------------------------------------------------------------

class TestScoreToWhitePov:
    def test_positive_cp_white_pov(self):
        score = _fake_pov_score(cp=100, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp == 100
        assert mate is None

    def test_negative_cp_white_pov(self):
        score = _fake_pov_score(cp=-200, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp == -200
        assert mate is None

    def test_black_pov_score_is_converted(self):
        # If engine reports from Black's POV, White POV should be negated
        score = _fake_pov_score(cp=150, white=False)
        cp, mate = score_to_white_pov(score)
        assert cp == -150
        assert mate is None

    def test_mate_for_white(self):
        score = _fake_pov_score(mate=3, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp == MATE_CP_SENTINEL
        assert mate == 3

    def test_mate_for_black(self):
        score = _fake_pov_score(mate=-2, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp == -MATE_CP_SENTINEL
        assert mate == -2

    def test_non_mate_gives_none_mate(self):
        score = _fake_pov_score(cp=47, white=True)
        cp, mate = score_to_white_pov(score)
        assert mate is None

    def test_zero_cp(self):
        score = _fake_pov_score(cp=0, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp == 0
        assert mate is None

    def test_large_cp_clamped_below_sentinel(self):
        # Non-mate scores should be clamped to avoid hitting ±MATE_CP_SENTINEL
        score = _fake_pov_score(cp=9999, white=True)
        cp, mate = score_to_white_pov(score)
        assert cp < MATE_CP_SENTINEL
        assert mate is None


# ---------------------------------------------------------------------------
# 4. Eval feature derivation
# ---------------------------------------------------------------------------

class TestDeriveEvalFeatures:
    def test_positive_cp_slight_white(self):
        d = derive_sf_eval_features(sf_eval_cp=150, sf_eval_mate=None)
        assert d["sf_eval_sign"] == 1
        assert d["sf_eval_abs"] == 150
        assert d["sf_eval_bucket"] == "slight_white"
        assert d["sf_eval_mate_abs"] is None

    def test_negative_cp_losing_black(self):
        d = derive_sf_eval_features(sf_eval_cp=-400, sf_eval_mate=None)
        assert d["sf_eval_sign"] == -1
        assert d["sf_eval_abs"] == 400
        assert d["sf_eval_bucket"] == "losing_black"

    def test_zero_cp_equal(self):
        d = derive_sf_eval_features(sf_eval_cp=0, sf_eval_mate=None)
        assert d["sf_eval_sign"] == 0
        assert d["sf_eval_bucket"] == "equal"

    def test_mate_white_bucket(self):
        d = derive_sf_eval_features(sf_eval_cp=MATE_CP_SENTINEL, sf_eval_mate=3)
        assert d["sf_eval_bucket"] == "mate_white"
        assert d["sf_eval_mate_abs"] == 3

    def test_mate_black_bucket(self):
        d = derive_sf_eval_features(sf_eval_cp=-MATE_CP_SENTINEL, sf_eval_mate=-2)
        assert d["sf_eval_bucket"] == "mate_black"
        assert d["sf_eval_mate_abs"] == 2

    def test_none_cp_all_none(self):
        d = derive_sf_eval_features(sf_eval_cp=None, sf_eval_mate=None)
        assert d["sf_eval_sign"] is None
        assert d["sf_eval_abs"] is None
        assert d["sf_eval_bucket"] is None
        assert d["sf_eval_mate_abs"] is None

    def test_boundary_equal_at_99(self):
        d = derive_sf_eval_features(sf_eval_cp=99, sf_eval_mate=None)
        assert d["sf_eval_bucket"] == "equal"

    def test_boundary_slight_white_at_100(self):
        d = derive_sf_eval_features(sf_eval_cp=100, sf_eval_mate=None)
        assert d["sf_eval_bucket"] == "slight_white"

    def test_winning_white_at_300(self):
        d = derive_sf_eval_features(sf_eval_cp=300, sf_eval_mate=None)
        assert d["sf_eval_bucket"] == "winning_white"

    def test_slight_black_at_minus_150(self):
        d = derive_sf_eval_features(sf_eval_cp=-150, sf_eval_mate=None)
        assert d["sf_eval_bucket"] == "slight_black"


# ---------------------------------------------------------------------------
# 5. Position loading and filtering
# ---------------------------------------------------------------------------

class TestLoadPrimaryNumberedPositions:
    def test_excludes_last_by_default(self, tmp_path):
        # Create minimal Parquet with last and move_10 rows
        df = pl.DataFrame({
            "game_id": ["g1", "g1", "g1"],
            "ply": [20, 40, 48],
            "selected_position_type": ["move_10", "move_20", "last"],
            "move_number": [10, 20, 24],
            "result_class": ["WHITE_WIN"] * 3,
            "eval_cp": [None, None, None],
            "eval_mate": [None, None, None],
            "has_eval": [False, False, False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        result = load_primary_numbered_positions(pq)
        assert "last" not in result["selected_position_type"].to_list()
        assert len(result) == 2

    def test_includes_last_when_flag_set(self, tmp_path):
        df = pl.DataFrame({
            "game_id": ["g1", "g1"],
            "ply": [20, 48],
            "selected_position_type": ["move_10", "last"],
            "move_number": [10, 24],
            "result_class": ["WHITE_WIN", "WHITE_WIN"],
            "eval_cp": [None, None],
            "eval_mate": [None, None],
            "has_eval": [False, False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        result = load_primary_numbered_positions(pq, include_last=True)
        assert "last" in result["selected_position_type"].to_list()
        assert len(result) == 2

    def test_game_id_ply_uniqueness_expected(self, tmp_path):
        df = pl.DataFrame({
            "game_id": ["g1", "g1", "g2"],
            "ply": [20, 40, 20],
            "selected_position_type": ["move_10", "move_20", "move_10"],
            "move_number": [10, 20, 10],
            "result_class": ["WHITE_WIN"] * 3,
            "eval_cp": [None, None, None],
            "eval_mate": [None, None, None],
            "has_eval": [False, False, False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        result = load_primary_numbered_positions(pq)
        pairs = list(zip(result["game_id"].to_list(), result["ply"].to_list()))
        assert len(pairs) == len(set(pairs))

    def test_split_set_joined_from_json(self, tmp_path):
        df = pl.DataFrame({
            "game_id": ["g1", "g2"],
            "ply": [20, 20],
            "selected_position_type": ["move_10", "move_10"],
            "move_number": [10, 10],
            "result_class": ["WHITE_WIN", "BLACK_WIN"],
            "eval_cp": [None, None],
            "eval_mate": [None, None],
            "has_eval": [False, False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        splits_data = {"assignments": {"g1": "train", "g2": "val"}}
        sp = tmp_path / "splits.json"
        sp.write_text(json.dumps(splits_data))
        result = load_primary_numbered_positions(pq, splits_path=sp)
        splits = dict(zip(result["game_id"].to_list(), result["split_set"].to_list()))
        assert splits["g1"] == "train"
        assert splits["g2"] == "val"

    def test_split_set_unknown_if_no_splits(self, tmp_path):
        df = pl.DataFrame({
            "game_id": ["g1"],
            "ply": [20],
            "selected_position_type": ["move_10"],
            "move_number": [10],
            "result_class": ["WHITE_WIN"],
            "eval_cp": [None],
            "eval_mate": [None],
            "has_eval": [False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        result = load_primary_numbered_positions(pq)
        assert result["split_set"][0] == "unknown"

    def test_required_columns_present(self, tmp_path):
        df = pl.DataFrame({
            "game_id": ["g1"],
            "ply": [20],
            "selected_position_type": ["move_10"],
            "move_number": [10],
            "result_class": ["WHITE_WIN"],
            "eval_cp": [None],
            "eval_mate": [None],
            "has_eval": [False],
        })
        pq = tmp_path / "positions.parquet"
        df.write_parquet(pq)
        result = load_primary_numbered_positions(pq)
        for col in ["game_id", "ply", "selected_position_type", "split_set"]:
            assert col in result.columns


# ---------------------------------------------------------------------------
# 6. Engine wrapper (analyse_fen with mock engine)
# ---------------------------------------------------------------------------

class TestAnalyseFen:
    def _make_mock_engine(self, cp: int = 50, mate: int | None = None, depth: int = 12):
        engine = MagicMock(spec=chess.engine.SimpleEngine)
        if mate is not None:
            score_val = chess.engine.PovScore(chess.engine.Mate(mate), chess.WHITE)
        else:
            score_val = chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE)
        engine.analyse.return_value = {
            "score": score_val,
            "depth": depth,
            "nodes": 12345,
        }
        return engine

    def test_ok_cp_result(self):
        engine = self._make_mock_engine(cp=70, depth=12)
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert result["sf_eval_available"] is True
        assert result["sf_eval_status"] == _EVAL_STATUS_OK_CP
        assert result["sf_eval_cp"] == 70
        assert result["sf_eval_mate"] is None
        assert result["sf_depth"] == 12

    def test_ok_mate_result(self):
        engine = self._make_mock_engine(mate=3, depth=12)
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert result["sf_eval_available"] is True
        assert result["sf_eval_status"] == _EVAL_STATUS_OK_MATE
        assert result["sf_eval_cp"] == MATE_CP_SENTINEL
        assert result["sf_eval_mate"] == 3

    def test_engine_error_produces_not_available(self):
        engine = MagicMock(spec=chess.engine.SimpleEngine)
        engine.analyse.side_effect = Exception("engine crashed")
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert result["sf_eval_available"] is False
        assert result["sf_eval_status"] == _EVAL_STATUS_ENG_ERR
        assert result["sf_error"] is not None

    def test_invalid_fen_produces_illegal_status(self):
        engine = MagicMock(spec=chess.engine.SimpleEngine)
        result = analyse_fen(engine, "not_a_valid_fen", depth=12)
        assert result["sf_eval_available"] is False
        assert result["sf_eval_status"] == _EVAL_STATUS_ILLEGAL

    def test_nodes_recorded(self):
        engine = self._make_mock_engine(cp=30)
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert result["sf_nodes"] == 12345

    def test_sf_depth_recorded(self):
        engine = self._make_mock_engine(depth=15)
        result = analyse_fen(engine, chess.Board().fen(), depth=15)
        assert result["sf_depth"] == 15

    def test_time_ms_non_negative(self):
        engine = self._make_mock_engine(cp=0)
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert result["sf_time_ms"] is not None
        assert result["sf_time_ms"] >= 0

    def test_derived_features_present(self):
        engine = self._make_mock_engine(cp=200)
        result = analyse_fen(engine, chess.Board().fen(), depth=12)
        assert "sf_eval_abs" in result
        assert "sf_eval_sign" in result
        assert "sf_eval_bucket" in result
        assert result["sf_eval_sign"] == 1


# ---------------------------------------------------------------------------
# 7. CLI / output schema / report
# ---------------------------------------------------------------------------

class TestOutputSchema:
    def test_all_required_columns_present(self):
        positions = _make_positions_df([
            {"game_id": "g1", "ply": 20, "selected_position_type": "move_10"},
        ])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake_path_not_used",
                stockfish_path="/fake/sf",
                depth=12,
                limit=1,
                dry_run=True,
            )
        for col in _OUTPUT_COLUMNS:
            assert col in result_df.columns, f"Missing column: {col}"

    def test_game_id_ply_unique_in_output(self):
        positions = _make_positions_df([
            {"game_id": "g1", "ply": 20},
            {"game_id": "g1", "ply": 40},
            {"game_id": "g2", "ply": 20},
        ])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                dry_run=True,
            )
        pairs = list(zip(result_df["game_id"].to_list(), result_df["ply"].to_list()))
        assert len(pairs) == len(set(pairs))

    def test_dataset_id_version_tag_in_output(self):
        positions = _make_positions_df([{"game_id": "g1", "ply": 20}])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                dry_run=True,
                dataset_id="test_dataset",
                version_tag="test_v1",
            )
        assert result_df["dataset_id"][0] == "test_dataset"
        assert result_df["version_tag"][0] == "test_v1"


class TestMetadata:
    def test_required_fields_present(self):
        meta = build_metadata(
            dataset_id="test",
            version_tag="v1",
            positions_path="pos.parquet",
            raw_pgn="pgn.zst",
            output_parquet="out.parquet",
            depth=12,
            stockfish_path="/path/sf",
            stockfish_version="Stockfish 18",
            run_started_utc="2026-06-10T00:00:00Z",
            run_finished_utc="2026-06-10T00:01:00Z",
            n_requested=100,
            n_evaluated=99,
            n_failed=1,
            status_counts={"ok_cp": 99, "fen_reconstruction_error": 1},
            include_last=False,
            limit=None,
            dry_run=False,
            command=["python", "-m", "chess_mhsuc.stockfish_eval"],
            runtime_s=60.0,
        )
        required = [
            "dataset_id", "version_tag", "depth", "stockfish_version",
            "python_chess_version", "n_requested", "n_evaluated", "n_failed",
            "status_counts", "run_started_utc", "run_finished_utc", "dry_run",
        ]
        for k in required:
            assert k in meta, f"Missing metadata key: {k}"

    def test_python_chess_version_recorded(self):
        meta = build_metadata(
            dataset_id="test", version_tag="v1", positions_path="p", raw_pgn="r",
            output_parquet="o", depth=12, stockfish_path="sf", stockfish_version="SF18",
            run_started_utc="2026", run_finished_utc="2026",
            n_requested=0, n_evaluated=0, n_failed=0, status_counts={},
            include_last=False, limit=None, dry_run=True, command=[],
            runtime_s=0.0,
        )
        assert meta["python_chess_version"] == chess.__version__

    def test_depth_recorded_correctly(self):
        meta = build_metadata(
            dataset_id="test", version_tag="v1", positions_path="p", raw_pgn="r",
            output_parquet="o", depth=15, stockfish_path="sf", stockfish_version="SF18",
            run_started_utc="2026", run_finished_utc="2026",
            n_requested=0, n_evaluated=0, n_failed=0, status_counts={},
            include_last=False, limit=None, dry_run=True, command=[],
            runtime_s=0.0,
        )
        assert meta["depth"] == 15


class TestRenderReport:
    def _make_empty_results(self) -> pl.DataFrame:
        return pl.DataFrame({col: pl.Series(col, [], dtype=pl.Utf8) for col in _OUTPUT_COLUMNS[:3]})

    def _make_meta(self, **kwargs) -> dict:
        defaults = {
            "dataset_id": "test_ds",
            "version_tag": "test_v1",
            "depth": 12,
            "stockfish_version": "Stockfish 18",
            "n_requested": 6205,
            "n_evaluated": 6180,
            "n_failed": 25,
            "status_counts": {"ok_cp": 6160, "ok_mate": 20, "fen_reconstruction_error": 25},
            "dry_run": False,
            "runtime_s": 240.0,
        }
        defaults.update(kwargs)
        return defaults

    def test_report_contains_ticket_label(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "8.1B" in report

    def test_report_contains_causal_caveat(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "causal" in report.lower() or "not causal" in report.lower()

    def test_report_contains_not_perfect_truth(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "not perfect truth" in report or "objective-position context" in report

    def test_report_contains_gitignore_note(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "gitignore" in report.lower() or "not be committed" in report

    def test_report_contains_selection_bias_note(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "selection" in report.lower() or "sparse" in report.lower()

    def test_report_contains_phase_82_reference(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        assert "8.2" in report or "Phase 8.2" in report

    def test_report_dry_run_note_when_dry_run_true(self):
        meta = self._make_meta(dry_run=True)
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta, dry_run=True)
        assert "dry-run" in report.lower() or "dry run" in report.lower()

    def test_report_is_deterministic(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        r1 = render_stockfish_eval_report(empty, meta)
        r2 = render_stockfish_eval_report(empty, meta)
        assert r1 == r2

    def test_no_forbidden_claims(self):
        meta = self._make_meta()
        empty = self._make_empty_results()
        report = render_stockfish_eval_report(empty, meta)
        forbidden = [
            "stockfish proves",
            "validated human strategy",
            "degradation curve established",
            "draw solved",
            "now final",
        ]
        report_lower = report.lower()
        for phrase in forbidden:
            assert phrase not in report_lower, f"Forbidden claim found: '{phrase}'"


class TestWriteOutputs:
    def test_creates_all_three_files(self, tmp_path):
        df = pl.DataFrame({col: pl.Series(col, [], dtype=pl.Utf8) for col in _OUTPUT_COLUMNS[:3]})
        meta = {"test": True}
        out_pq = tmp_path / "out.parquet"
        out_json = tmp_path / "out.json"
        out_md = tmp_path / "out.md"
        write_outputs(df, meta, out_pq, out_json, out_md, "# report", overwrite=True)
        assert out_pq.exists()
        assert out_json.exists()
        assert out_md.exists()

    def test_raises_if_exists_without_overwrite(self, tmp_path):
        df = pl.DataFrame({})
        existing = tmp_path / "exists.parquet"
        existing.write_text("x")
        with pytest.raises(FileExistsError):
            write_outputs(df, {}, existing, tmp_path / "m.json", tmp_path / "r.md", "", overwrite=False)

    def test_overwrite_replaces_file(self, tmp_path):
        df = pl.DataFrame({"x": [1, 2]})
        out_pq = tmp_path / "out.parquet"
        out_json = tmp_path / "m.json"
        out_md = tmp_path / "r.md"
        write_outputs(df, {}, out_pq, out_json, out_md, "first", overwrite=True)
        write_outputs(df, {}, out_pq, out_json, out_md, "second", overwrite=True)
        assert out_md.read_text() == "second"


# ---------------------------------------------------------------------------
# 8. Resume behavior
# ---------------------------------------------------------------------------

class TestResumeBehavior:
    def test_resume_skips_existing_pairs(self, tmp_path):
        existing = pl.DataFrame({
            "game_id": ["g1"],
            "ply": [20],
            "sf_eval_available": [True],
        })
        resume_pq = tmp_path / "existing.parquet"
        existing.write_parquet(resume_pq)

        positions = _make_positions_df([
            {"game_id": "g1", "ply": 20},
            {"game_id": "g2", "ply": 20},
        ])

        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                dry_run=True,
                resume_parquet=resume_pq,
            )

        assert len(result_df) == 1
        assert result_df["game_id"][0] == "g2"

    def test_no_duplicate_game_id_ply_after_resume(self, tmp_path):
        existing = pl.DataFrame({"game_id": ["g1"], "ply": [20], "sf_eval_available": [True]})
        resume_pq = tmp_path / "existing.parquet"
        existing.write_parquet(resume_pq)

        positions = _make_positions_df([
            {"game_id": "g1", "ply": 20},
            {"game_id": "g1", "ply": 40},
        ])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                dry_run=True,
                resume_parquet=resume_pq,
            )
        pairs = list(zip(result_df["game_id"].to_list(), result_df["ply"].to_list()))
        assert len(pairs) == len(set(pairs))

    def test_resume_false_no_skip(self):
        positions = _make_positions_df([{"game_id": "g1", "ply": 20}])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                dry_run=True,
                resume_parquet=None,
            )
        assert len(result_df) == 1


# ---------------------------------------------------------------------------
# 9. extract_game_id helper
# ---------------------------------------------------------------------------

class TestExtractGameId:
    def test_standard_lichess_url(self):
        assert _extract_game_id("https://lichess.org/abcd1234") == "abcd1234"

    def test_url_with_trailing_slash(self):
        assert _extract_game_id("https://lichess.org/abcd1234/") == "abcd1234"

    def test_empty_string_returns_none(self):
        assert _extract_game_id("") is None

    def test_none_input_returns_none(self):
        # Passing None-equivalent (empty string used in practice)
        assert _extract_game_id("") is None

    def test_url_with_subdomain(self):
        result = _extract_game_id("https://lichess.org/game/abcd1234")
        assert result == "abcd1234"


# ---------------------------------------------------------------------------
# 10. Limit behavior
# ---------------------------------------------------------------------------

class TestLimitBehavior:
    def test_limit_caps_output_rows(self):
        positions = _make_positions_df([
            {"game_id": f"g{i}", "ply": 20} for i in range(10)
        ])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                limit=3,
                dry_run=True,
            )
        assert len(result_df) == 3

    def test_no_limit_processes_all(self):
        positions = _make_positions_df([
            {"game_id": f"g{i}", "ply": 20} for i in range(5)
        ])
        with patch("chess_mhsuc.stockfish_eval.index_target_games") as mock_idx:
            mock_idx.return_value = {}
            result_df = run_stockfish_eval(
                positions_df=positions,
                raw_pgn="fake",
                stockfish_path="/fake/sf",
                depth=12,
                limit=None,
                dry_run=True,
            )
        assert len(result_df) == 5
