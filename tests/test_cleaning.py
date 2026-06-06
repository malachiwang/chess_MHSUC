"""
tests/test_cleaning.py — unit tests for cleaning.py.

All tests use synthetic Polars DataFrames only.
No real data files are read.
"""

import json
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.cleaning import (
    build_cleaning_metadata,
    clean_game_records,
    clean_position_records,
    filter_eval_positions,
    main,
)

# ---------------------------------------------------------------------------
# Minimal schemas for synthetic DataFrames
# ---------------------------------------------------------------------------

_GAME_SCHEMA = {
    "game_id": pl.String,
    "accepted_basic": pl.Boolean,
    "accepted_eval": pl.Boolean,
    "termination": pl.String,
    "result_class": pl.String,
    "white_rating_diff": pl.Int64,
    "black_rating_diff": pl.Int64,
}

_POS_SCHEMA = {
    "game_id": pl.String,
    "ply": pl.Int64,
    "has_eval": pl.Boolean,
    "eval_cp": pl.Int64,
    "eval_mate": pl.Int64,
    "selected_position_type": pl.String,
    "termination": pl.String,
}


def _make_game(
    game_id: str,
    accepted_basic: bool = True,
    accepted_eval: bool = False,
    termination: str = "Normal",
    result_class: str = "WHITE_WIN",
    white_rating_diff: int | None = 5,
    black_rating_diff: int | None = -5,
) -> dict:
    return {
        "game_id": game_id,
        "accepted_basic": accepted_basic,
        "accepted_eval": accepted_eval,
        "termination": termination,
        "result_class": result_class,
        "white_rating_diff": white_rating_diff,
        "black_rating_diff": black_rating_diff,
    }


def _make_pos(
    game_id: str,
    ply: int = 20,
    has_eval: bool = False,
    eval_cp: int | None = None,
    eval_mate: int | None = None,
    selected_position_type: str = "move_10",
    termination: str = "Normal",
) -> dict:
    return {
        "game_id": game_id,
        "ply": ply,
        "has_eval": has_eval,
        "eval_cp": eval_cp,
        "eval_mate": eval_mate,
        "selected_position_type": selected_position_type,
        "termination": termination,
    }


def _games_df(rows: list[dict]) -> pl.DataFrame:
    return pl.from_dicts(rows, schema=_GAME_SCHEMA)


def _pos_df(rows: list[dict]) -> pl.DataFrame:
    return pl.from_dicts(rows, schema=_POS_SCHEMA)


# ---------------------------------------------------------------------------
# TestCleanGameRecords
# ---------------------------------------------------------------------------


class TestCleanGameRecords:
    def test_keeps_normal_accepted_game(self):
        df = _games_df([_make_game("g1", accepted_basic=True, termination="Normal")])
        out = clean_game_records(df)
        assert out.height == 1
        assert out["game_id"][0] == "g1"

    def test_keeps_time_forfeit_game(self):
        """Time forfeit games must be retained — central to research question."""
        df = _games_df([_make_game("g2", accepted_basic=True, termination="Time forfeit")])
        out = clean_game_records(df)
        assert out.height == 1

    def test_removes_accepted_abandoned(self):
        """accepted_basic=True but termination==Abandoned must be dropped."""
        df = _games_df([_make_game("g3", accepted_basic=True, termination="Abandoned")])
        out = clean_game_records(df)
        assert out.height == 0

    def test_removes_rejected_game(self):
        """accepted_basic=False games must be excluded."""
        df = _games_df([_make_game("g4", accepted_basic=False, termination="Normal")])
        out = clean_game_records(df)
        assert out.height == 0

    def test_retains_no_eval_game(self):
        """accepted_eval=False / missing eval must be retained."""
        df = _games_df([_make_game("g5", accepted_eval=False)])
        out = clean_game_records(df)
        assert out.height == 1

    def test_retains_null_rating_diff(self):
        """null white_rating_diff / black_rating_diff must be retained."""
        df = _games_df([_make_game("g6", white_rating_diff=None, black_rating_diff=None)])
        out = clean_game_records(df)
        assert out.height == 1

    def test_mixed_batch_correct_count(self):
        rows = [
            _make_game("keep1", accepted_basic=True, termination="Normal"),
            _make_game("keep2", accepted_basic=True, termination="Time forfeit"),
            _make_game("drop1", accepted_basic=False, termination="Normal"),
            _make_game("drop2", accepted_basic=True, termination="Abandoned"),
        ]
        out = clean_game_records(_games_df(rows))
        assert out.height == 2
        assert set(out["game_id"].to_list()) == {"keep1", "keep2"}


# ---------------------------------------------------------------------------
# TestCleanPositionRecords
# ---------------------------------------------------------------------------


class TestCleanPositionRecords:
    def test_keeps_position_whose_game_is_clean(self):
        games = _games_df([_make_game("g1")])
        clean = clean_game_records(games)
        pos = _pos_df([_make_pos("g1", ply=20)])
        out = clean_position_records(pos, clean)
        assert out.height == 1

    def test_removes_position_whose_game_is_excluded(self):
        games = _games_df([_make_game("g_drop", accepted_basic=False)])
        clean = clean_game_records(games)
        pos = _pos_df([_make_pos("g_drop", ply=20)])
        out = clean_position_records(pos, clean)
        assert out.height == 0

    def test_retains_position_without_eval(self):
        games = _games_df([_make_game("g1")])
        clean = clean_game_records(games)
        pos = _pos_df([_make_pos("g1", has_eval=False, eval_cp=None)])
        out = clean_position_records(pos, clean)
        assert out.height == 1

    def test_retains_last_checkpoint(self):
        games = _games_df([_make_game("g1")])
        clean = clean_game_records(games)
        pos = _pos_df([_make_pos("g1", ply=82, selected_position_type="last")])
        out = clean_position_records(pos, clean)
        assert out.height == 1

    def test_retains_duplicated_last_and_numbered_checkpoint(self):
        """If 'last' coincides with a numbered checkpoint, both rows are retained."""
        games = _games_df([_make_game("g1")])
        clean = clean_game_records(games)
        pos = _pos_df([
            _make_pos("g1", ply=40, selected_position_type="move_20"),
            _make_pos("g1", ply=40, selected_position_type="last"),
        ])
        out = clean_position_records(pos, clean)
        assert out.height == 2

    def test_retains_time_forfeit_position(self):
        games = _games_df([_make_game("g1", termination="Time forfeit")])
        clean = clean_game_records(games)
        pos = _pos_df([_make_pos("g1", termination="Time forfeit")])
        out = clean_position_records(pos, clean)
        assert out.height == 1

    def test_mixed_game_ids_only_clean_retained(self):
        games = _games_df([
            _make_game("g_keep"),
            _make_game("g_drop", termination="Abandoned"),
        ])
        clean = clean_game_records(games)
        pos = _pos_df([
            _make_pos("g_keep"),
            _make_pos("g_drop"),
        ])
        out = clean_position_records(pos, clean)
        assert out.height == 1
        assert out["game_id"][0] == "g_keep"


# ---------------------------------------------------------------------------
# TestFilterEvalPositions
# ---------------------------------------------------------------------------


class TestFilterEvalPositions:
    def test_keeps_only_has_eval_true(self):
        pos = _pos_df([
            _make_pos("g1", has_eval=True, eval_cp=50),
            _make_pos("g2", has_eval=False, eval_cp=None),
        ])
        out = filter_eval_positions(pos)
        assert out.height == 1
        assert out["game_id"][0] == "g1"

    def test_retains_sentinel_eval_cp(self):
        """eval_cp == ±10000 (forced-mate sentinel) must be retained."""
        pos = _pos_df([
            _make_pos("g1", has_eval=True, eval_cp=10_000, eval_mate=3),
            _make_pos("g2", has_eval=True, eval_cp=-10_000, eval_mate=-2),
        ])
        out = filter_eval_positions(pos)
        assert out.height == 2

    def test_does_not_alter_eval_values(self):
        pos = _pos_df([_make_pos("g1", has_eval=True, eval_cp=123, eval_mate=None)])
        out = filter_eval_positions(pos)
        assert out["eval_cp"][0] == 123
        assert out["eval_mate"][0] is None

    def test_empty_input_returns_empty(self):
        pos = _pos_df([])
        out = filter_eval_positions(pos)
        assert out.height == 0


# ---------------------------------------------------------------------------
# TestBuildCleaningMetadata
# ---------------------------------------------------------------------------


class TestBuildCleaningMetadata:

    @pytest.fixture
    def sample_data(self):
        raw_games = _games_df([
            _make_game("g1", accepted_basic=True, termination="Normal", result_class="WHITE_WIN"),
            _make_game("g2", accepted_basic=True, termination="Time forfeit", result_class="BLACK_WIN"),
            _make_game("g3", accepted_basic=False, termination="Normal"),
            _make_game("g4", accepted_basic=True, termination="Abandoned"),
        ])
        clean_games = clean_game_records(raw_games)
        raw_pos = _pos_df([
            _make_pos("g1", has_eval=True, eval_cp=50, selected_position_type="move_10"),
            _make_pos("g1", has_eval=False, eval_cp=None, selected_position_type="last"),
            _make_pos("g2", has_eval=True, eval_cp=-100, selected_position_type="move_10"),
        ])
        broad_pos = clean_position_records(raw_pos, clean_games)
        eval_pos = filter_eval_positions(broad_pos)
        return raw_games, clean_games, raw_pos, broad_pos, eval_pos

    def test_required_keys_present(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={"game_records": "a.parquet", "position_records": "b.parquet"},
            output_paths={"game_records_clean": "c.parquet"},
            version_tag="test_v1",
        )
        required = {
            "version_tag", "timestamp_utc", "input_paths", "output_paths",
            "cleaning_rules", "raw_game_rows", "clean_game_rows",
            "excluded_game_rows", "excluded_not_accepted_basic",
            "excluded_abandoned_accepted", "retained_time_forfeit",
            "raw_position_rows", "broad_position_rows", "eval_position_rows",
            "eval_coverage_broad_pct", "result_distribution_clean",
            "termination_distribution_clean", "checkpoint_distribution_broad",
        }
        assert required <= set(meta.keys())

    def test_row_counts_correct(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="t",
        )
        assert meta["raw_game_rows"] == 4
        assert meta["clean_game_rows"] == 2       # g1 and g2 survive
        assert meta["excluded_game_rows"] == 2    # g3 (rejected) + g4 (abandoned)
        assert meta["excluded_not_accepted_basic"] == 1   # g3
        assert meta["excluded_abandoned_accepted"] == 1   # g4

    def test_position_counts_correct(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="t",
        )
        assert meta["raw_position_rows"] == 3
        assert meta["broad_position_rows"] == 3   # all from g1 and g2
        assert meta["eval_position_rows"] == 2    # g1 move_10 + g2 move_10

    def test_distributions_are_dicts(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="t",
        )
        assert isinstance(meta["result_distribution_clean"], dict)
        assert isinstance(meta["termination_distribution_clean"], dict)
        assert isinstance(meta["checkpoint_distribution_broad"], dict)

    def test_result_distribution_values(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="t",
        )
        dist = meta["result_distribution_clean"]
        assert dist.get("WHITE_WIN", 0) == 1
        assert dist.get("BLACK_WIN", 0) == 1

    def test_version_tag_stored(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="2024_09_25k_v1",
        )
        assert meta["version_tag"] == "2024_09_25k_v1"

    def test_retained_time_forfeit_count(self, sample_data):
        raw_games, clean_games, raw_pos, broad_pos, eval_pos = sample_data
        meta = build_cleaning_metadata(
            raw_games, clean_games, raw_pos, broad_pos, eval_pos,
            input_paths={}, output_paths={}, version_tag="t",
        )
        assert meta["retained_time_forfeit"] == 1   # g2


# ---------------------------------------------------------------------------
# TestCleaningCLI
# ---------------------------------------------------------------------------


class TestCleaningCLI:
    """Integration tests for main() using synthetic Parquet files written to tmp_path."""

    @pytest.fixture
    def interim_files(self, tmp_path):
        """Write minimal synthetic interim Parquet files."""
        raw_games = _games_df([
            _make_game("g1", accepted_basic=True, termination="Normal", result_class="WHITE_WIN"),
            _make_game("g2", accepted_basic=True, termination="Time forfeit", result_class="BLACK_WIN"),
            _make_game("g3", accepted_basic=False, termination="Normal"),
        ])
        raw_pos = _pos_df([
            _make_pos("g1", has_eval=True, eval_cp=50, selected_position_type="move_10"),
            _make_pos("g1", has_eval=False, eval_cp=None, selected_position_type="last"),
            _make_pos("g2", has_eval=True, eval_cp=-30, selected_position_type="move_10"),
        ])
        game_path = tmp_path / "game_records.parquet"
        pos_path = tmp_path / "position_records.parquet"
        raw_games.write_parquet(str(game_path))
        raw_pos.write_parquet(str(pos_path))
        return game_path, pos_path

    def _run(self, interim_files, tmp_path, tag="test_v1"):
        game_path, pos_path = interim_files
        out_dir = tmp_path / "processed"
        rc = main([
            "--game-records", str(game_path),
            "--position-records", str(pos_path),
            "--output-dir", str(out_dir),
            "--version-tag", tag,
        ])
        return rc, out_dir, tag

    def test_exits_zero_on_valid_input(self, interim_files, tmp_path):
        rc, _, _ = self._run(interim_files, tmp_path)
        assert rc == 0

    def test_output_files_created(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        assert (out_dir / f"ten_zero_game_records_{tag}.parquet").exists()
        assert (out_dir / f"ten_zero_positions_broad_{tag}.parquet").exists()
        assert (out_dir / f"ten_zero_positions_eval_{tag}.parquet").exists()
        assert (out_dir / f"cleaning_metadata_{tag}.json").exists()

    def test_metadata_json_has_version_tag(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        meta = json.loads((out_dir / f"cleaning_metadata_{tag}.json").read_text())
        assert meta["version_tag"] == tag

    def test_no_username_cols_in_output(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        forbidden = {"white", "black", "White", "Black", "white_name", "black_name"}
        gr = pl.read_parquet(str(out_dir / f"ten_zero_game_records_{tag}.parquet"))
        pb = pl.read_parquet(str(out_dir / f"ten_zero_positions_broad_{tag}.parquet"))
        pe = pl.read_parquet(str(out_dir / f"ten_zero_positions_eval_{tag}.parquet"))
        assert not (forbidden & set(gr.columns))
        assert not (forbidden & set(pb.columns))
        assert not (forbidden & set(pe.columns))

    def test_no_csv_files_written(self, interim_files, tmp_path):
        self._run(interim_files, tmp_path)
        csv_files = list(tmp_path.rglob("*.csv"))
        assert not csv_files
