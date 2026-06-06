"""
tests/test_features.py — unit and integration tests for features.py.

All tests use synthetic Polars DataFrames only.
No real data files are read.
"""

import json
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.features import (
    add_clock_features,
    add_duplicate_checkpoint_flag,
    add_eval_features,
    add_position_features,
    add_rating_features,
    add_slice_columns,
    build_feature_metadata,
    build_feature_table,
    drop_forbidden_columns,
    main,
    _DEFAULT_PREDICTIVE_FEATURES,
    _EVAL_PREDICTIVE_FEATURES,
    _CAUTION_COLUMNS,
    _LABEL_COLUMNS,
    _SLICE_COLUMNS,
    _DROPPED_COLUMNS,
    _FORBIDDEN_LEAKAGE_COLUMNS,
)


# ---------------------------------------------------------------------------
# Synthetic schema and helpers
# ---------------------------------------------------------------------------

_FULL_SCHEMA = {
    "game_id": pl.String,
    "ply": pl.Int64,
    "move_number": pl.Int64,
    "side_to_move_next": pl.String,
    "selected_position_type": pl.String,
    "white_clock_s": pl.Int64,
    "black_clock_s": pl.Int64,
    "clock_diff_s": pl.Int64,
    "eval_cp": pl.Int64,
    "eval_mate": pl.Int64,
    "has_eval": pl.Boolean,
    "phase": pl.String,
    "result_class": pl.String,
    "white_result_numeric": pl.Float64,
    "white_elo": pl.Int64,
    "black_elo": pl.Int64,
    "elo_diff": pl.Int64,
    "termination": pl.String,
    "n_plies_total": pl.Int64,
}


def _pos(
    game_id: str = "g1",
    ply: int = 20,
    move_number: int = 10,
    side_to_move_next: str = "white",
    selected_position_type: str = "move_10",
    white_clock_s: int = 500,
    black_clock_s: int = 480,
    clock_diff_s: int = 20,
    eval_cp: int | None = None,
    eval_mate: int | None = None,
    has_eval: bool = False,
    phase: str = "opening",
    result_class: str = "WHITE_WIN",
    white_result_numeric: float = 1.0,
    white_elo: int = 1500,
    black_elo: int = 1500,
    elo_diff: int = 0,
    termination: str = "Normal",
    n_plies_total: int = 80,
) -> dict:
    return {
        "game_id": game_id,
        "ply": ply,
        "move_number": move_number,
        "side_to_move_next": side_to_move_next,
        "selected_position_type": selected_position_type,
        "white_clock_s": white_clock_s,
        "black_clock_s": black_clock_s,
        "clock_diff_s": clock_diff_s,
        "eval_cp": eval_cp,
        "eval_mate": eval_mate,
        "has_eval": has_eval,
        "phase": phase,
        "result_class": result_class,
        "white_result_numeric": white_result_numeric,
        "white_elo": white_elo,
        "black_elo": black_elo,
        "elo_diff": elo_diff,
        "termination": termination,
        "n_plies_total": n_plies_total,
    }


def _df(rows: list[dict]) -> pl.DataFrame:
    return pl.from_dicts(rows, schema=_FULL_SCHEMA)


# ---------------------------------------------------------------------------
# A. add_rating_features
# ---------------------------------------------------------------------------


class TestAddRatingFeatures:
    def test_avg_elo_computed_correctly(self):
        df = _df([_pos(white_elo=1600, black_elo=1400)])
        out = add_rating_features(df)
        assert out["avg_elo"][0] == pytest.approx(1500.0)

    def test_avg_elo_equal_ratings(self):
        df = _df([_pos(white_elo=1500, black_elo=1500)])
        out = add_rating_features(df)
        assert out["avg_elo"][0] == pytest.approx(1500.0)

    def test_original_rating_cols_preserved(self):
        df = _df([_pos(white_elo=1600, black_elo=1400, elo_diff=200)])
        out = add_rating_features(df)
        assert out["white_elo"][0] == 1600
        assert out["black_elo"][0] == 1400
        assert out["elo_diff"][0] == 200

    def test_avg_elo_returns_float(self):
        df = _df([_pos(white_elo=1601, black_elo=1400)])
        out = add_rating_features(df)
        assert out["avg_elo"].dtype == pl.Float64


# ---------------------------------------------------------------------------
# B. add_clock_features
# ---------------------------------------------------------------------------


class TestAddClockFeatures:
    def test_caps_white_clock_above_600(self):
        df = _df([_pos(white_clock_s=700, black_clock_s=300)])
        out = add_clock_features(df)
        assert out["white_clock_s_capped"][0] == 600

    def test_caps_black_clock_above_600(self):
        df = _df([_pos(white_clock_s=300, black_clock_s=700)])
        out = add_clock_features(df)
        assert out["black_clock_s_capped"][0] == 600

    def test_clock_below_600_not_capped(self):
        df = _df([_pos(white_clock_s=400, black_clock_s=350)])
        out = add_clock_features(df)
        assert out["white_clock_s_capped"][0] == 400
        assert out["black_clock_s_capped"][0] == 350

    def test_clock_anomaly_true_if_either_raw_above_600(self):
        df = _df([_pos(white_clock_s=700, black_clock_s=300)])
        out = add_clock_features(df)
        assert out["clock_anomaly"][0] is True

    def test_clock_anomaly_false_if_both_at_or_below_600(self):
        df = _df([_pos(white_clock_s=600, black_clock_s=600)])
        out = add_clock_features(df)
        assert out["clock_anomaly"][0] is False

    def test_clock_fracs_correct(self):
        df = _df([_pos(white_clock_s=300, black_clock_s=150)])
        out = add_clock_features(df)
        assert out["white_clock_frac"][0] == pytest.approx(0.5)
        assert out["black_clock_frac"][0] == pytest.approx(0.25)

    def test_clock_diff_frac_uses_capped_values(self):
        df = _df([_pos(white_clock_s=700, black_clock_s=300)])
        out = add_clock_features(df)
        # capped: white=600, black=300 -> diff=300 -> frac=0.5
        assert out["clock_diff_frac"][0] == pytest.approx(0.5)

    def test_zero_clock_triggers_all_low_flags(self):
        df = _df([_pos(white_clock_s=0, black_clock_s=0)])
        out = add_clock_features(df)
        assert out["white_low_10"][0] is True
        assert out["white_low_30"][0] is True
        assert out["white_low_60"][0] is True
        assert out["black_low_10"][0] is True
        assert out["black_low_30"][0] is True
        assert out["black_low_60"][0] is True

    def test_45s_triggers_low_60_only(self):
        df = _df([_pos(white_clock_s=45, black_clock_s=45)])
        out = add_clock_features(df)
        assert out["white_low_60"][0] is True
        assert out["white_low_30"][0] is False
        assert out["white_low_10"][0] is False

    def test_15s_triggers_low_60_and_low_30_not_low_10(self):
        df = _df([_pos(white_clock_s=15, black_clock_s=15)])
        out = add_clock_features(df)
        assert out["white_low_60"][0] is True
        assert out["white_low_30"][0] is True
        assert out["white_low_10"][0] is False

    def test_raw_clocks_preserved(self):
        df = _df([_pos(white_clock_s=700, black_clock_s=300, clock_diff_s=400)])
        out = add_clock_features(df)
        assert out["white_clock_s"][0] == 700
        assert out["black_clock_s"][0] == 300
        assert out["clock_diff_s"][0] == 400


# ---------------------------------------------------------------------------
# C. add_eval_features
# ---------------------------------------------------------------------------


class TestAddEvalFeatures:
    def test_null_eval_stays_null(self):
        df = _df([_pos(eval_cp=None, eval_mate=None)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] is None
        assert out["eval_white_winning"][0] is None

    def test_positive_eval_within_clip_unchanged(self):
        df = _df([_pos(eval_cp=500)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == 500

    def test_negative_eval_within_clip_unchanged(self):
        df = _df([_pos(eval_cp=-500)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == -500

    def test_positive_eval_above_1000_clipped_to_1000(self):
        df = _df([_pos(eval_cp=1200)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == 1000

    def test_negative_eval_below_minus_1000_clipped_to_minus_1000(self):
        df = _df([_pos(eval_cp=-1200)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == -1000

    def test_plus_10000_sentinel_clipped_to_1000(self):
        df = _df([_pos(eval_cp=10_000, eval_mate=3)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == 1000

    def test_minus_10000_sentinel_clipped_to_minus_1000(self):
        df = _df([_pos(eval_cp=-10_000, eval_mate=-2)])
        out = add_eval_features(df)
        assert out["eval_cp_clipped"][0] == -1000

    def test_is_mate_eval_true_when_eval_mate_not_null(self):
        df = _df([_pos(eval_cp=10_000, eval_mate=3)])
        out = add_eval_features(df)
        assert out["is_mate_eval"][0] is True

    def test_is_mate_eval_false_when_eval_mate_null(self):
        df = _df([_pos(eval_cp=200, eval_mate=None)])
        out = add_eval_features(df)
        assert out["is_mate_eval"][0] is False

    def test_eval_mate_abs_correct(self):
        df = _df([
            _pos(game_id="g1", eval_cp=10_000, eval_mate=3),
            _pos(game_id="g2", eval_cp=-10_000, eval_mate=-5),
        ])
        out = add_eval_features(df)
        assert out["eval_mate_abs"][0] == 3
        assert out["eval_mate_abs"][1] == 5

    def test_eval_mate_abs_null_when_eval_mate_null(self):
        df = _df([_pos(eval_cp=200, eval_mate=None)])
        out = add_eval_features(df)
        assert out["eval_mate_abs"][0] is None

    def test_eval_white_winning_true_for_positive_eval(self):
        df = _df([_pos(eval_cp=50)])
        out = add_eval_features(df)
        assert out["eval_white_winning"][0] is True

    def test_eval_white_winning_false_for_negative_eval(self):
        df = _df([_pos(eval_cp=-50)])
        out = add_eval_features(df)
        assert out["eval_white_winning"][0] is False

    def test_eval_white_winning_false_for_zero_eval(self):
        df = _df([_pos(eval_cp=0)])
        out = add_eval_features(df)
        assert out["eval_white_winning"][0] is False

    def test_eval_white_winning_null_for_null_eval(self):
        df = _df([_pos(eval_cp=None)])
        out = add_eval_features(df)
        assert out["eval_white_winning"][0] is None

    def test_raw_eval_preserved(self):
        df = _df([_pos(eval_cp=500, eval_mate=None)])
        out = add_eval_features(df)
        assert out["eval_cp"][0] == 500
        assert out["eval_mate"][0] is None


# ---------------------------------------------------------------------------
# D. add_position_features
# ---------------------------------------------------------------------------


class TestAddPositionFeatures:
    def test_is_last_checkpoint_true_for_last(self):
        df = _df([_pos(selected_position_type="last")])
        out = add_position_features(df)
        assert out["is_last_checkpoint"][0] is True

    def test_is_last_checkpoint_false_for_numbered(self):
        df = _df([_pos(selected_position_type="move_10")])
        out = add_position_features(df)
        assert out["is_last_checkpoint"][0] is False

    def test_white_to_move_next_true_for_white(self):
        df = _df([_pos(side_to_move_next="white")])
        out = add_position_features(df)
        assert out["white_to_move_next"][0] is True

    def test_white_to_move_next_false_for_black(self):
        df = _df([_pos(side_to_move_next="black")])
        out = add_position_features(df)
        assert out["white_to_move_next"][0] is False

    def test_checkpoint_index_mapping(self):
        types = ["move_10", "move_20", "move_30", "move_40", "last"]
        expected = [0, 1, 2, 3, 4]
        rows = [_pos(game_id=f"g{i}", selected_position_type=t, ply=i*20)
                for i, t in enumerate(types, 1)]
        out = add_position_features(_df(rows))
        assert out["checkpoint_index"].to_list() == expected

    def test_phase_index_mapping(self):
        phases = ["opening", "middlegame", "endgame"]
        expected = [0, 1, 2]
        rows = [_pos(game_id=f"g{i}", phase=p) for i, p in enumerate(phases, 1)]
        out = add_position_features(_df(rows))
        assert out["phase_index"].to_list() == expected

    def test_original_columns_preserved(self):
        df = _df([_pos(selected_position_type="move_20", phase="middlegame",
                       side_to_move_next="white", move_number=20)])
        out = add_position_features(df)
        assert "selected_position_type" in out.columns
        assert "phase" in out.columns
        assert "side_to_move_next" in out.columns
        assert "move_number" in out.columns


# ---------------------------------------------------------------------------
# E. add_slice_columns
# ---------------------------------------------------------------------------


class TestAddSliceColumns:
    def test_is_time_forfeit_true_for_time_forfeit(self):
        df = _df([_pos(termination="Time forfeit")])
        out = add_slice_columns(df)
        assert out["is_time_forfeit"][0] is True

    def test_is_time_forfeit_false_for_normal(self):
        df = _df([_pos(termination="Normal")])
        out = add_slice_columns(df)
        assert out["is_time_forfeit"][0] is False

    def test_is_time_forfeit_mixed(self):
        df = _df([
            _pos(game_id="g1", termination="Normal"),
            _pos(game_id="g2", termination="Time forfeit"),
        ])
        out = add_slice_columns(df)
        assert out["is_time_forfeit"].to_list() == [False, True]


# ---------------------------------------------------------------------------
# F. add_duplicate_checkpoint_flag
# ---------------------------------------------------------------------------


class TestAddDuplicateCheckpointFlag:
    def test_detects_duplicate_ply_same_game(self):
        """Two rows with same game_id and ply but different types are flagged."""
        df = _df([
            _pos(game_id="g1", ply=40, selected_position_type="move_20"),
            _pos(game_id="g1", ply=40, selected_position_type="last"),
        ])
        out = add_duplicate_checkpoint_flag(df)
        assert out["duplicate_ply_checkpoint"].to_list() == [True, True]

    def test_unique_game_ply_not_flagged(self):
        df = _df([
            _pos(game_id="g1", ply=20, selected_position_type="move_10"),
            _pos(game_id="g1", ply=40, selected_position_type="move_20"),
        ])
        out = add_duplicate_checkpoint_flag(df)
        assert out["duplicate_ply_checkpoint"].to_list() == [False, False]

    def test_different_games_same_ply_not_flagged(self):
        """Same ply in different games should not flag each other."""
        df = _df([
            _pos(game_id="g1", ply=40, selected_position_type="move_20"),
            _pos(game_id="g2", ply=40, selected_position_type="move_20"),
        ])
        out = add_duplicate_checkpoint_flag(df)
        assert out["duplicate_ply_checkpoint"].to_list() == [False, False]

    def test_no_rows_dropped(self):
        df = _df([
            _pos(game_id="g1", ply=40, selected_position_type="move_20"),
            _pos(game_id="g1", ply=40, selected_position_type="last"),
        ])
        out = add_duplicate_checkpoint_flag(df)
        assert out.height == 2


# ---------------------------------------------------------------------------
# G. drop_forbidden_columns
# ---------------------------------------------------------------------------


class TestDropForbiddenColumns:
    def test_removes_n_plies_total(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "n_plies_total" not in out.columns

    def test_removes_ply(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "ply" not in out.columns

    def test_removes_white_rating_diff_if_present(self):
        df = _df([_pos()]).with_columns(pl.lit(5, dtype=pl.Int64).alias("white_rating_diff"))
        out = drop_forbidden_columns(df)
        assert "white_rating_diff" not in out.columns

    def test_missing_forbidden_col_is_safe(self):
        """Calling drop on a DF that lacks some forbidden cols should not crash."""
        df = _df([_pos()])
        # n_plies_total present, ply present, but no white_rating_diff etc.
        out = drop_forbidden_columns(df)
        assert out is not None

    def test_preserves_result_class(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "result_class" in out.columns

    def test_preserves_white_result_numeric(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "white_result_numeric" in out.columns

    def test_preserves_game_id(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "game_id" in out.columns

    def test_preserves_termination(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "termination" in out.columns

    def test_preserves_has_eval(self):
        df = _df([_pos()])
        out = drop_forbidden_columns(df)
        assert "has_eval" in out.columns


# ---------------------------------------------------------------------------
# H. build_feature_table
# ---------------------------------------------------------------------------


class TestBuildFeatureTable:
    @pytest.fixture
    def sample_df(self):
        return _df([
            _pos(game_id="g1", ply=20, selected_position_type="move_10",
                 white_clock_s=500, black_clock_s=480,
                 eval_cp=50, eval_mate=None, has_eval=True, termination="Normal"),
            _pos(game_id="g1", ply=82, selected_position_type="last",
                 white_clock_s=10, black_clock_s=300,
                 eval_cp=None, has_eval=False, termination="Normal"),
            _pos(game_id="g2", ply=40, selected_position_type="move_20",
                 white_clock_s=350, black_clock_s=310,
                 eval_cp=-200, eval_mate=None, has_eval=True, termination="Time forfeit"),
        ])

    def test_row_count_preserved(self, sample_df):
        out = build_feature_table(sample_df)
        assert out.height == sample_df.height

    def test_added_columns_present(self, sample_df):
        out = build_feature_table(sample_df)
        expected = [
            "avg_elo", "white_clock_s_capped", "black_clock_s_capped",
            "white_clock_frac", "black_clock_frac", "clock_diff_frac",
            "white_low_60", "black_low_60", "white_low_30", "black_low_30",
            "white_low_10", "black_low_10", "clock_anomaly",
            "eval_cp_clipped", "is_mate_eval", "eval_mate_abs", "eval_white_winning",
            "is_last_checkpoint", "white_to_move_next", "checkpoint_index", "phase_index",
            "is_time_forfeit", "duplicate_ply_checkpoint",
        ]
        for col in expected:
            assert col in out.columns, f"Missing: {col}"

    def test_forbidden_columns_absent(self, sample_df):
        out = build_feature_table(sample_df)
        assert "n_plies_total" not in out.columns
        assert "ply" not in out.columns

    def test_does_not_drop_nullable_eval_rows(self, sample_df):
        """Rows with has_eval=False must still be in the output."""
        out = build_feature_table(sample_df)
        assert out.height == 3

    def test_is_time_forfeit_correct(self, sample_df):
        out = build_feature_table(sample_df)
        # g2 is Time forfeit; g1 rows are Normal
        itf = out.filter(pl.col("game_id") == "g2")["is_time_forfeit"][0]
        assert itf is True

    def test_labels_preserved(self, sample_df):
        out = build_feature_table(sample_df)
        assert "result_class" in out.columns
        assert "white_result_numeric" in out.columns


# ---------------------------------------------------------------------------
# I. build_feature_metadata
# ---------------------------------------------------------------------------


class TestBuildFeatureMetadata:
    @pytest.fixture
    def feature_dfs(self):
        broad = build_feature_table(_df([
            _pos(game_id="g1", ply=20, selected_position_type="move_10",
                 white_clock_s=700, black_clock_s=300,
                 eval_cp=50, has_eval=True),
            _pos(game_id="g1", ply=40, selected_position_type="move_20",
                 white_clock_s=400, black_clock_s=350,
                 eval_cp=None, has_eval=False),
            _pos(game_id="g1", ply=40, selected_position_type="last",
                 white_clock_s=400, black_clock_s=350,
                 eval_cp=None, has_eval=False),
        ]))
        eval_df = broad.filter(pl.col("has_eval"))
        return broad, eval_df

    def _meta(self, feature_dfs):
        broad, eval_df = feature_dfs
        return build_feature_metadata(
            df_broad=broad, df_eval=eval_df,
            input_paths={"positions_broad": "a.parquet", "positions_eval": "b.parquet"},
            output_paths={"feature_positions_broad": "c.parquet"},
            version_tag="test_v1",
        )

    def test_required_keys_present(self, feature_dfs):
        meta = self._meta(feature_dfs)
        required = {
            "version_tag", "timestamp_utc", "input_paths", "output_paths",
            "row_counts", "policy", "default_predictive_features",
            "eval_predictive_features", "caution_columns", "label_columns",
            "slice_columns", "dropped_columns", "nullable_eval_columns",
            "forbidden_leakage_columns", "clock_anomaly_count_broad",
            "duplicate_ply_checkpoint_count_broad", "eval_coverage_broad_pct",
        }
        assert required <= set(meta.keys())

    def test_default_predictive_features_excludes_has_eval(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "has_eval" not in meta["default_predictive_features"]

    def test_default_predictive_features_excludes_result_class(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "result_class" not in meta["default_predictive_features"]

    def test_default_predictive_features_excludes_white_result_numeric(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "white_result_numeric" not in meta["default_predictive_features"]

    def test_default_predictive_features_excludes_termination(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "termination" not in meta["default_predictive_features"]

    def test_default_predictive_features_excludes_n_plies_total(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "n_plies_total" not in meta["default_predictive_features"]

    def test_default_predictive_features_excludes_game_id(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "game_id" not in meta["default_predictive_features"]

    def test_eval_predictive_features_contains_eval_fields(self, feature_dfs):
        meta = self._meta(feature_dfs)
        for f in ["eval_cp", "eval_cp_clipped", "is_mate_eval", "eval_mate_abs", "eval_white_winning"]:
            assert f in meta["eval_predictive_features"], f"Missing from eval features: {f}"

    def test_caution_columns_correct(self, feature_dfs):
        meta = self._meta(feature_dfs)
        for c in ["is_last_checkpoint", "side_to_move_next", "white_to_move_next", "duplicate_ply_checkpoint"]:
            assert c in meta["caution_columns"]

    def test_label_columns_correct(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert "result_class" in meta["label_columns"]
        assert "white_result_numeric" in meta["label_columns"]

    def test_slice_columns_correct(self, feature_dfs):
        meta = self._meta(feature_dfs)
        for c in ["game_id", "termination", "is_time_forfeit", "has_eval"]:
            assert c in meta["slice_columns"]

    def test_dropped_columns_include_forbidden(self, feature_dfs):
        meta = self._meta(feature_dfs)
        for c in ["n_plies_total", "ply", "white_rating_diff", "black_rating_diff"]:
            assert c in meta["dropped_columns"]

    def test_forbidden_leakage_columns_present(self, feature_dfs):
        meta = self._meta(feature_dfs)
        # Check some key entries are represented
        combined = " ".join(meta["forbidden_leakage_columns"])
        assert "n_plies_total" in combined
        assert "white_rating_diff" in combined
        assert "result_class" in combined

    def test_version_tag_stored(self, feature_dfs):
        meta = self._meta(feature_dfs)
        assert meta["version_tag"] == "test_v1"

    def test_clock_anomaly_count(self, feature_dfs):
        """The one row with white_clock_s=700 should be flagged."""
        meta = self._meta(feature_dfs)
        assert meta["clock_anomaly_count_broad"] == 1

    def test_duplicate_ply_checkpoint_count(self, feature_dfs):
        """Two rows at ply=40 for g1 (move_20 and last)."""
        meta = self._meta(feature_dfs)
        assert meta["duplicate_ply_checkpoint_count_broad"] == 2


# ---------------------------------------------------------------------------
# J. CLI integration tests
# ---------------------------------------------------------------------------


class TestFeatureCLI:

    @pytest.fixture
    def interim_files(self, tmp_path):
        """Write minimal synthetic broad and eval Parquet files."""
        broad = _df([
            _pos(game_id="g1", ply=20, selected_position_type="move_10",
                 eval_cp=50, has_eval=True),
            _pos(game_id="g1", ply=80, selected_position_type="move_40",
                 eval_cp=None, has_eval=False),
            _pos(game_id="g2", ply=40, selected_position_type="move_20",
                 termination="Time forfeit", eval_cp=-30, has_eval=True),
        ])
        eval_df = _df([
            _pos(game_id="g1", ply=20, selected_position_type="move_10",
                 eval_cp=50, has_eval=True),
            _pos(game_id="g2", ply=40, selected_position_type="move_20",
                 termination="Time forfeit", eval_cp=-30, has_eval=True),
        ])
        broad_path = tmp_path / "broad.parquet"
        eval_path = tmp_path / "eval.parquet"
        broad.write_parquet(str(broad_path))
        eval_df.write_parquet(str(eval_path))
        return broad_path, eval_path

    def _run(self, interim_files, tmp_path, tag="test_v1"):
        broad_path, eval_path = interim_files
        out_dir = tmp_path / "out"
        rc = main([
            "--positions-broad", str(broad_path),
            "--positions-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", tag,
        ])
        return rc, out_dir, tag

    def test_exits_zero_on_valid_input(self, interim_files, tmp_path):
        rc, _, _ = self._run(interim_files, tmp_path)
        assert rc == 0

    def test_output_files_created(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        assert (out_dir / f"feature_positions_broad_{tag}.parquet").exists()
        assert (out_dir / f"feature_positions_eval_{tag}.parquet").exists()
        assert (out_dir / f"feature_metadata_{tag}.json").exists()

    def test_metadata_json_has_version_tag(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        meta = json.loads((out_dir / f"feature_metadata_{tag}.json").read_text())
        assert meta["version_tag"] == tag

    def test_no_username_cols_in_outputs(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        forbidden = {"white", "black", "White", "Black", "white_name", "black_name"}
        broad = pl.read_parquet(str(out_dir / f"feature_positions_broad_{tag}.parquet"))
        eval_out = pl.read_parquet(str(out_dir / f"feature_positions_eval_{tag}.parquet"))
        assert not (forbidden & set(broad.columns))
        assert not (forbidden & set(eval_out.columns))

    def test_no_csv_files_written(self, interim_files, tmp_path):
        self._run(interim_files, tmp_path)
        assert not list(tmp_path.rglob("*.csv"))

    def test_broad_row_count_preserved(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        out = pl.read_parquet(str(out_dir / f"feature_positions_broad_{tag}.parquet"))
        assert out.height == 3

    def test_eval_row_count_preserved(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        out = pl.read_parquet(str(out_dir / f"feature_positions_eval_{tag}.parquet"))
        assert out.height == 2

    def test_forbidden_columns_absent_in_broad_output(self, interim_files, tmp_path):
        rc, out_dir, tag = self._run(interim_files, tmp_path)
        broad = pl.read_parquet(str(out_dir / f"feature_positions_broad_{tag}.parquet"))
        assert "n_plies_total" not in broad.columns
        assert "ply" not in broad.columns
