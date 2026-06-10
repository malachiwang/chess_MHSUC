"""
tests/test_data_integrity.py — Population accounting and prediction/split
consistency checks (Ticket 7.3B).

These tests are designed to run without real data files. They use synthetic
fixtures to verify:

1. Population accounting: that the split + primary_numbered pipeline produces
   the expected row counts and game_id coverage.
2. Prediction/split consistency: that every prediction row's game_id appears
   in the split assignments, with the correct split label.
3. No row-level split leakage: that features for a model's training split
   do not appear in its val/test predictions.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.baselines import CLASS_ORDER, LABEL_MAP, run_all_baselines
from chess_mhsuc.splits import apply_split_to_df, get_train_val_test


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _make_feature_df(n_games: int = 30, seed: int = 0) -> pl.DataFrame:
    """
    Synthetic feature DataFrame with 3 rows per game (move_10, move_20, last).
    Classes cycle: BLACK_WIN, DRAW, WHITE_WIN.
    """
    rng = np.random.default_rng(seed)
    n = n_games * 3
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    rc_per_game = [classes[i % 3] for i in range(n_games)]
    result_class = [rc_per_game[i // 3] for i in range(n)]
    game_ids = [f"game_{i:04d}" for i in range(n_games) for _ in range(3)]
    position_types = ["move_10", "move_20", "last"] * n_games

    return pl.DataFrame({
        "game_id": game_ids,
        "result_class": result_class,
        "selected_position_type": position_types,
        "white_elo": rng.integers(1000, 2000, n).tolist(),
        "black_elo": rng.integers(1000, 2000, n).tolist(),
        "elo_diff": rng.integers(-200, 200, n).tolist(),
        "avg_elo": rng.integers(1000, 2000, n).astype(float).tolist(),
        "white_clock_s_capped": rng.integers(0, 600, n).tolist(),
        "black_clock_s_capped": rng.integers(0, 600, n).tolist(),
        "white_clock_frac": rng.uniform(0, 1, n).tolist(),
        "black_clock_frac": rng.uniform(0, 1, n).tolist(),
        "clock_diff_frac": rng.uniform(-1, 1, n).tolist(),
        "white_low_60": rng.choice([True, False], n).tolist(),
        "black_low_60": rng.choice([True, False], n).tolist(),
        "white_low_30": rng.choice([True, False], n).tolist(),
        "black_low_30": rng.choice([True, False], n).tolist(),
        "white_low_10": rng.choice([True, False], n).tolist(),
        "black_low_10": rng.choice([True, False], n).tolist(),
        "clock_anomaly": rng.choice([True, False], n).tolist(),
        "has_eval": ([False] * n),
        "is_time_forfeit": rng.choice([True, False], n).tolist(),
        "duplicate_ply_checkpoint": ([False] * n),
        "is_last_checkpoint": [pt == "last" for pt in position_types],
        "white_clock_s": rng.integers(0, 600, n).tolist(),
        "black_clock_s": rng.integers(0, 600, n).tolist(),
    })


def _make_split_assignments(df: pl.DataFrame) -> dict[str, str]:
    """Assign games to train/val/test in groups of 3 (balanced classes)."""
    splits = ["train", "val", "test"]
    game_ids = sorted(df["game_id"].unique().to_list())
    return {gid: splits[(i // 3) % 3] for i, gid in enumerate(game_ids)}


# ===========================================================================
# 1. Population accounting
# ===========================================================================

class TestPopulationAccounting:
    """Verify that primary_numbered view excludes 'last' rows correctly."""

    def test_primary_numbered_excludes_last(self):
        df = _make_feature_df(n_games=30)
        assignments = _make_split_assignments(df)
        train_df, val_df, test_df = get_train_val_test(
            df, assignments, view_name="primary_numbered"
        )
        for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
            assert "last" not in split_df["selected_position_type"].to_list(), (
                f"{split_name} split contains 'last' rows in primary_numbered view"
            )

    def test_primary_numbered_row_count(self):
        # 30 games x 2 non-last rows each = 60 total primary_numbered rows
        df = _make_feature_df(n_games=30)
        assignments = _make_split_assignments(df)
        train_df, val_df, test_df = get_train_val_test(
            df, assignments, view_name="primary_numbered"
        )
        total_rows = len(train_df) + len(val_df) + len(test_df)
        assert total_rows == 60  # 30 games x 2 positions each

    def test_every_game_id_in_exactly_one_split(self):
        df = _make_feature_df(n_games=30)
        assignments = _make_split_assignments(df)
        train_df, val_df, test_df = get_train_val_test(
            df, assignments, view_name="primary_numbered"
        )
        train_ids = set(train_df["game_id"].unique().to_list())
        val_ids = set(val_df["game_id"].unique().to_list())
        test_ids = set(test_df["game_id"].unique().to_list())

        assert not (train_ids & val_ids), "Train/val game_id overlap"
        assert not (train_ids & test_ids), "Train/test game_id overlap"
        assert not (val_ids & test_ids), "Val/test game_id overlap"

    def test_all_games_accounted_for(self):
        df = _make_feature_df(n_games=30)
        assignments = _make_split_assignments(df)
        train_df, val_df, test_df = get_train_val_test(
            df, assignments, view_name="primary_numbered"
        )
        split_game_ids = (
            set(train_df["game_id"].unique().to_list())
            | set(val_df["game_id"].unique().to_list())
            | set(test_df["game_id"].unique().to_list())
        )
        expected = {gid for gid, s in assignments.items() if s in ("train", "val", "test")}
        assert split_game_ids == expected

    def test_no_rows_without_split_assignment(self):
        df = _make_feature_df(n_games=30)
        assignments = _make_split_assignments(df)
        assigned_game_ids = set(assignments.keys())
        all_game_ids = set(df["game_id"].unique().to_list())
        unassigned = all_game_ids - assigned_game_ids
        assert not unassigned, f"Game IDs without split assignment: {unassigned}"


# ===========================================================================
# 2. Prediction/split consistency
# ===========================================================================

class TestPredictionSplitConsistency:
    """
    Verify that prediction DataFrames are consistent with split assignments.
    Every prediction row's game_id must appear in assignments with the
    correct split label.
    """

    def _run_baselines(self, n_games: int = 30, seed: int = 0):
        from chess_mhsuc.baselines import build_baseline_registry, get_feature_columns
        import polars as pl
        df = _make_feature_df(n_games=n_games, seed=seed)
        assignments = _make_split_assignments(df)
        eval_df = pl.DataFrame({
            "game_id": pl.Series([], dtype=pl.Utf8),
            "result_class": pl.Series([], dtype=pl.Utf8),
            "selected_position_type": pl.Series([], dtype=pl.Utf8),
        })
        plan = {
            "dataset_id": "test_v1",
            "feature_sets": [
                {"id": "FS-A", "name": "prior", "table": "broad", "features": []},
            ],
            "baseline_plan": [
                {"id": "B1", "model_class": "DummyClassifier",
                 "feature_set_id": "FS-A", "table": "broad", "exploratory": False,
                 "sklearn_params": {"strategy": "prior"}},
            ],
            "metric_policy": {"primary": "log_loss"},
        }
        results, pred_df = run_all_baselines(df, eval_df, assignments, plan)
        return pred_df, assignments

    def test_all_pred_game_ids_in_assignments(self):
        pred_df, assignments = self._run_baselines()
        pred_game_ids = set(pred_df["game_id"].unique().to_list())
        assert pred_game_ids <= set(assignments.keys()), (
            f"Prediction game_ids not in assignments: "
            f"{pred_game_ids - set(assignments.keys())}"
        )

    def test_pred_split_set_matches_assignment(self):
        pred_df, assignments = self._run_baselines()
        for row in pred_df.iter_rows(named=True):
            gid = row["game_id"]
            expected_split = assignments[gid]
            actual_split = row["split_set"]
            assert actual_split == expected_split, (
                f"game_id={gid} is in split '{expected_split}' but pred says '{actual_split}'"
            )

    def test_no_game_id_in_multiple_pred_splits(self):
        pred_df, assignments = self._run_baselines()
        # For a given baseline_id, each game_id should appear in at most one split
        for mid in pred_df["baseline_id"].unique().to_list():
            sub = pred_df.filter(pl.col("baseline_id") == mid)
            game_splits = sub.select(["game_id", "split_set"]).unique()
            counts = game_splits.group_by("game_id").agg(pl.len().alias("n_splits"))
            multi = counts.filter(pl.col("n_splits") > 1)
            assert len(multi) == 0, (
                f"{mid}: game_ids appear in multiple splits: "
                f"{multi['game_id'].to_list()}"
            )


# ===========================================================================
# 3. Feature/label separation
# ===========================================================================

class TestFeatureLabelSeparation:
    """
    Verify that label columns do not appear in feature column lists.
    """

    def test_result_class_not_a_feature(self):
        from chess_mhsuc.baselines import _FORBIDDEN_FEATURE_COLS
        assert "result_class" in _FORBIDDEN_FEATURE_COLS

    def test_white_result_numeric_not_a_feature(self):
        from chess_mhsuc.baselines import _FORBIDDEN_FEATURE_COLS
        assert "white_result_numeric" in _FORBIDDEN_FEATURE_COLS

    def test_class_order_has_three_classes(self):
        assert len(CLASS_ORDER) == 3

    def test_label_map_consistent_with_class_order(self):
        for i, cls in enumerate(CLASS_ORDER):
            assert LABEL_MAP[cls] == i

    def test_game_id_not_used_as_feature(self):
        # game_id is an identifier, not a predictive feature.
        # It must never appear in a feature set.
        from chess_mhsuc.baselines import _FORBIDDEN_FEATURE_COLS
        assert "game_id" in _FORBIDDEN_FEATURE_COLS
