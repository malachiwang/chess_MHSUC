"""Tests for chess_mhsuc.gbm — Phase 6.1B"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from chess_mhsuc.baselines import CLASS_ORDER, LABEL_MAP
from chess_mhsuc.gbm import (
    GBM_PARAMS,
    STRING_CATEGORICALS_TO_DROP,
    build_gbm_model,
    build_gbm_params,
    build_gbm_prediction_rows,
    build_gbm_registry,
    build_gbm_results_payload,
    get_gbm_feature_columns,
    prepare_gbm_X,
    print_gbm_summary,
    render_gbm_report,
    run_all_gbm,
    save_gbm_outputs,
    train_one_gbm,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_broad_df(n: int = 120) -> pl.DataFrame:
    """Synthetic broad feature DataFrame."""
    rng = np.random.default_rng(42)
    game_ids = [f"game_{i:04d}" for i in range(n)]
    results = (["BLACK_WIN"] * (n // 3) + ["DRAW"] * (n // 3) + ["WHITE_WIN"] * (n // 3))[:n]

    return pl.DataFrame({
        "game_id": pl.Series(game_ids, dtype=pl.Utf8),
        "result_class": pl.Series(results, dtype=pl.Utf8),
        "white_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "black_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "elo_diff": pl.Series(rng.integers(-500, 500, n).tolist(), dtype=pl.Int64),
        "avg_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "white_time_remaining": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "black_time_remaining": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "white_time_used_total": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "black_time_used_total": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "white_time_used_last": pl.Series(rng.uniform(0, 60, n).tolist(), dtype=pl.Float64),
        "black_time_used_last": pl.Series(rng.uniform(0, 60, n).tolist(), dtype=pl.Float64),
        "white_low_60": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_60": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "white_low_30": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_30": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "white_low_10": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_10": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "clock_anomaly": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "selected_position_type": pl.Series(["numbered"] * n, dtype=pl.Utf8),
        "move_number": pl.Series(rng.integers(1, 40, n).tolist(), dtype=pl.Int64),
        "phase": pl.Series(["middle"] * n, dtype=pl.Utf8),
        "checkpoint_index": pl.Series(rng.integers(0, 4, n).tolist(), dtype=pl.Int64),
        "phase_index": pl.Series(rng.integers(0, 3, n).tolist(), dtype=pl.Int64),
        "is_time_forfeit": pl.Series([False] * n, dtype=pl.Boolean),
        "has_eval": pl.Series([False] * n, dtype=pl.Boolean),
        "duplicate_ply_checkpoint": pl.Series([False] * n, dtype=pl.Boolean),
    })


def _make_eval_df(n: int = 60) -> pl.DataFrame:
    """Synthetic eval feature DataFrame (includes eval columns)."""
    rng = np.random.default_rng(42)
    game_ids = [f"game_{i:04d}" for i in range(n)]
    results = (["BLACK_WIN"] * (n // 3) + ["DRAW"] * (n // 3) + ["WHITE_WIN"] * (n // 3))[:n]
    eval_mate = [None if i % 10 != 0 else float(rng.integers(1, 10)) for i in range(n)]

    return pl.DataFrame({
        "game_id": pl.Series(game_ids, dtype=pl.Utf8),
        "result_class": pl.Series(results, dtype=pl.Utf8),
        "white_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "black_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "elo_diff": pl.Series(rng.integers(-500, 500, n).tolist(), dtype=pl.Int64),
        "avg_elo": pl.Series(rng.integers(1000, 2000, n).tolist(), dtype=pl.Int64),
        "eval_cp": pl.Series(rng.uniform(-1000, 1000, n).tolist(), dtype=pl.Float64),
        "eval_mate_abs": pl.Series(eval_mate, dtype=pl.Float64),
        "is_mate_eval": pl.Series([m is not None for m in eval_mate], dtype=pl.Boolean),
        "eval_white_winning": pl.Series(
            rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean
        ),
        "white_time_remaining": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "black_time_remaining": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "white_time_used_total": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "black_time_used_total": pl.Series(rng.uniform(0, 600, n).tolist(), dtype=pl.Float64),
        "white_time_used_last": pl.Series(rng.uniform(0, 60, n).tolist(), dtype=pl.Float64),
        "black_time_used_last": pl.Series(rng.uniform(0, 60, n).tolist(), dtype=pl.Float64),
        "white_low_60": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_60": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "white_low_30": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_30": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "white_low_10": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "black_low_10": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "clock_anomaly": pl.Series(rng.integers(0, 2, n).astype(bool).tolist(), dtype=pl.Boolean),
        "selected_position_type": pl.Series(["numbered"] * n, dtype=pl.Utf8),
        "move_number": pl.Series(rng.integers(1, 40, n).tolist(), dtype=pl.Int64),
        "phase": pl.Series(["middle"] * n, dtype=pl.Utf8),
        "checkpoint_index": pl.Series(rng.integers(0, 4, n).tolist(), dtype=pl.Int64),
        "phase_index": pl.Series(rng.integers(0, 3, n).tolist(), dtype=pl.Int64),
        "is_time_forfeit": pl.Series([False] * n, dtype=pl.Boolean),
        "has_eval": pl.Series([True] * n, dtype=pl.Boolean),
        "duplicate_ply_checkpoint": pl.Series([False] * n, dtype=pl.Boolean),
    })


def _make_assignments(broad_df: pl.DataFrame) -> dict[str, str]:
    """Assign games in groups of 3 (one per class) to same split."""
    all_games = broad_df["game_id"].unique(maintain_order=True).to_list()
    splits = ["train", "val", "test"]
    return {gid: splits[(i // 3) % 3] for i, gid in enumerate(all_games)}


def _make_modeling_plan() -> dict:
    """Synthetic modeling plan with list-format feature_sets."""
    return {
        "feature_sets": [
            {"id": "FS-A", "features": []},
            {"id": "FS-B", "features": ["white_elo", "black_elo", "elo_diff", "avg_elo"]},
            {"id": "FS-C", "features": [
                "white_time_remaining", "black_time_remaining",
                "white_time_used_total", "black_time_used_total",
                "white_time_used_last", "black_time_used_last",
                "white_low_60", "black_low_60",
                "white_low_30", "black_low_30",
                "white_low_10", "black_low_10",
                "clock_anomaly",
            ]},
            {"id": "FS-D", "features": [
                "selected_position_type", "move_number", "phase",
                "checkpoint_index", "phase_index",
            ]},
            {"id": "FS-E", "features": [
                "white_elo", "black_elo", "elo_diff", "avg_elo",
                "white_time_remaining", "black_time_remaining",
                "white_time_used_total", "black_time_used_total",
                "white_time_used_last", "black_time_used_last",
                "white_low_60", "black_low_60",
                "white_low_30", "black_low_30",
                "white_low_10", "black_low_10",
                "clock_anomaly",
                "selected_position_type", "move_number", "phase",
                "checkpoint_index", "phase_index",
            ]},
            {"id": "FS-F", "features": [
                "eval_cp", "eval_mate_abs",
                "is_mate_eval", "eval_white_winning",
                "selected_position_type", "move_number", "phase",
                "checkpoint_index", "phase_index",
            ]},
            {"id": "FS-G", "features": [
                "white_elo", "black_elo", "elo_diff", "avg_elo",
                "eval_cp", "eval_mate_abs",
                "is_mate_eval", "eval_white_winning",
                "white_time_remaining", "black_time_remaining",
                "white_time_used_total", "black_time_used_total",
                "white_time_used_last", "black_time_used_last",
                "white_low_60", "black_low_60",
                "white_low_30", "black_low_30",
                "white_low_10", "black_low_10",
                "clock_anomaly",
                "selected_position_type", "move_number", "phase",
                "checkpoint_index", "phase_index",
            ]},
        ],
        "baseline_plan": [
            {"id": "B0", "model": "DummyClassifier", "feature_set": "FS-A",
             "table": "broad", "exploratory": False,
             "sklearn_params": {"strategy": "most_frequent"}},
        ],
    }


# ===========================================================================
# A. build_gbm_params
# ===========================================================================

class TestBuildGbmParams:
    def test_returns_dict(self):
        assert isinstance(build_gbm_params(), dict)

    def test_max_iter(self):
        assert build_gbm_params()["max_iter"] == 300

    def test_learning_rate(self):
        assert build_gbm_params()["learning_rate"] == 0.05

    def test_max_leaf_nodes(self):
        assert build_gbm_params()["max_leaf_nodes"] == 31

    def test_min_samples_leaf(self):
        assert build_gbm_params()["min_samples_leaf"] == 20

    def test_l2_regularization(self):
        assert build_gbm_params()["l2_regularization"] == 0.1

    def test_random_state_42(self):
        assert build_gbm_params()["random_state"] == 42

    def test_no_class_weight_by_default(self):
        assert "class_weight" not in build_gbm_params()

    def test_class_weight_balanced(self):
        assert build_gbm_params(class_weight="balanced")["class_weight"] == "balanced"

    def test_does_not_mutate_gbm_params(self):
        build_gbm_params(class_weight="balanced")
        assert "class_weight" not in GBM_PARAMS


# ===========================================================================
# B. get_gbm_feature_columns
# ===========================================================================

class TestGetGbmFeatureColumns:
    def test_fs_b_used_equals_requested(self):
        plan = _make_modeling_plan()
        req, used = get_gbm_feature_columns("FS-B", plan)
        assert req == used

    def test_no_string_cats_in_used(self):
        plan = _make_modeling_plan()
        for fs_id in ["FS-B", "FS-C", "FS-D", "FS-E", "FS-F", "FS-G"]:
            _, used = get_gbm_feature_columns(fs_id, plan)
            assert "selected_position_type" not in used
            assert "phase" not in used

    def test_fs_d_drops_string_cats_from_requested(self):
        plan = _make_modeling_plan()
        req, used = get_gbm_feature_columns("FS-D", plan)
        assert "selected_position_type" in req
        assert "phase" in req
        assert "selected_position_type" not in used
        assert "phase" not in used

    def test_fs_d_retains_numeric_ordinals(self):
        plan = _make_modeling_plan()
        _, used = get_gbm_feature_columns("FS-D", plan)
        assert "checkpoint_index" in used
        assert "phase_index" in used
        assert "move_number" in used

    def test_returns_two_lists(self):
        plan = _make_modeling_plan()
        result = get_gbm_feature_columns("FS-B", plan)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_used_subset_of_requested(self):
        plan = _make_modeling_plan()
        req, used = get_gbm_feature_columns("FS-E", plan)
        assert set(used).issubset(set(req))

    def test_string_categoricals_to_drop_contains_expected(self):
        assert "selected_position_type" in STRING_CATEGORICALS_TO_DROP
        assert "phase" in STRING_CATEGORICALS_TO_DROP

    def test_fs_c_no_string_cats_in_req(self):
        plan = _make_modeling_plan()
        req, used = get_gbm_feature_columns("FS-C", plan)
        assert req == used  # FS-C has no string cats


# ===========================================================================
# C. prepare_gbm_X
# ===========================================================================

class TestPrepareGbmX:
    def test_returns_pandas_dataframe(self):
        import pandas as pd
        df = _make_broad_df(30)
        X = prepare_gbm_X(df, ["white_elo", "black_elo"])
        assert isinstance(X, pd.DataFrame)

    def test_boolean_cast_to_int8(self):
        df = _make_broad_df(30)
        X = prepare_gbm_X(df, ["white_low_60"])
        assert X["white_low_60"].dtype == np.int8

    def test_shape_correct(self):
        df = _make_broad_df(30)
        X = prepare_gbm_X(df, ["white_elo", "black_elo", "elo_diff"])
        assert X.shape == (30, 3)

    def test_eval_mate_abs_nan_preserved(self):
        df = _make_eval_df(30)
        X = prepare_gbm_X(df, ["eval_mate_abs"])
        assert X["eval_mate_abs"].isna().any()

    def test_eval_mate_abs_dtype_float64(self):
        df = _make_eval_df(30)
        X = prepare_gbm_X(df, ["eval_mate_abs"])
        assert X["eval_mate_abs"].dtype == np.float64

    def test_column_order_preserved(self):
        df = _make_broad_df(30)
        cols = ["black_elo", "white_elo", "elo_diff"]
        X = prepare_gbm_X(df, cols)
        assert list(X.columns) == cols

    def test_empty_feature_list_returns_empty_df(self):
        df = _make_broad_df(30)
        X = prepare_gbm_X(df, [])
        assert X.shape[0] == 30
        assert X.shape[1] == 0


# ===========================================================================
# D. build_gbm_model
# ===========================================================================

class TestBuildGbmModel:
    def _entry(self, class_weight=None):
        return {"model_id": "G1", "feature_set_id": "FS-B",
                "table": "broad", "exploratory": False,
                "diagnostic": False, "class_weight": class_weight}

    def test_returns_histgbm(self):
        assert isinstance(build_gbm_model("G1", self._entry()), HistGradientBoostingClassifier)

    def test_max_iter_param(self):
        m = build_gbm_model("G1", self._entry())
        assert m.max_iter == 300

    def test_learning_rate_param(self):
        m = build_gbm_model("G1", self._entry())
        assert m.learning_rate == 0.05

    def test_random_state_42(self):
        m = build_gbm_model("G1", self._entry())
        assert m.random_state == 42

    def test_no_class_weight_by_default(self):
        m = build_gbm_model("G1", self._entry())
        assert m.class_weight is None

    def test_class_weight_balanced(self):
        m = build_gbm_model("G1", self._entry(class_weight="balanced"))
        assert m.class_weight == "balanced"


# ===========================================================================
# E. build_gbm_registry
# ===========================================================================

class TestBuildGbmRegistry:
    def test_returns_dict(self):
        assert isinstance(build_gbm_registry(), dict)

    def test_has_g1_through_g6(self):
        reg = build_gbm_registry()
        for mid in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            assert mid in reg, f"{mid} missing from registry"

    def test_g1_fs_b_broad(self):
        reg = build_gbm_registry()
        assert reg["G1"]["feature_set_id"] == "FS-B"
        assert reg["G1"]["table"] == "broad"

    def test_g2_fs_e_broad(self):
        reg = build_gbm_registry()
        assert reg["G2"]["feature_set_id"] == "FS-E"
        assert reg["G2"]["table"] == "broad"

    def test_g3_fs_c_diagnostic(self):
        reg = build_gbm_registry()
        assert reg["G3"]["feature_set_id"] == "FS-C"
        assert reg["G3"]["diagnostic"] is True

    def test_g4_fs_d_diagnostic(self):
        reg = build_gbm_registry()
        assert reg["G4"]["feature_set_id"] == "FS-D"
        assert reg["G4"]["diagnostic"] is True

    def test_g5_fs_f_eval_exploratory(self):
        reg = build_gbm_registry()
        assert reg["G5"]["feature_set_id"] == "FS-F"
        assert reg["G5"]["table"] == "eval"
        assert reg["G5"]["exploratory"] is True

    def test_g6_fs_g_eval_exploratory(self):
        reg = build_gbm_registry()
        assert reg["G6"]["feature_set_id"] == "FS-G"
        assert reg["G6"]["table"] == "eval"
        assert reg["G6"]["exploratory"] is True

    def test_g1_g2_not_exploratory(self):
        reg = build_gbm_registry()
        assert reg["G1"]["exploratory"] is False
        assert reg["G2"]["exploratory"] is False

    def test_all_have_model_id_key(self):
        reg = build_gbm_registry()
        for mid, entry in reg.items():
            assert entry["model_id"] == mid

    def test_exactly_six_entries(self):
        assert len(build_gbm_registry()) == 6


# ===========================================================================
# F. build_gbm_prediction_rows
# ===========================================================================

class TestBuildGbmPredictionRows:
    def setup_method(self):
        n = 12
        df = _make_broad_df(n)
        y = np.array([0, 1, 2] * 4)
        proba = np.eye(3)[y]
        self.df = df
        self.y = y
        self.proba = proba
        self.n = n

    def _call(self, **kw):
        defaults = dict(
            model_id="G1", split_set="val", df=self.df,
            y_true=self.y, y_pred=self.y, proba=self.proba,
            table="broad", view="primary_numbered",
            exploratory=False, diagnostic=False,
        )
        defaults.update(kw)
        return build_gbm_prediction_rows(**defaults)

    def test_returns_polars_df(self):
        assert isinstance(self._call(), pl.DataFrame)

    def test_row_count(self):
        assert len(self._call()) == self.n

    def test_has_model_id_column(self):
        assert "model_id" in self._call().columns

    def test_no_baseline_id_column(self):
        assert "baseline_id" not in self._call().columns

    def test_p_prefix_columns(self):
        result = self._call()
        assert "p_BLACK_WIN" in result.columns
        assert "p_DRAW" in result.columns
        assert "p_WHITE_WIN" in result.columns

    def test_no_prob_prefix_columns(self):
        result = self._call()
        assert not any(c.startswith("prob_") for c in result.columns)

    def test_context_columns_present(self):
        result = self._call()
        for col in ["table", "view", "exploratory", "diagnostic", "y_true", "y_pred"]:
            assert col in result.columns, f"missing {col}"

    def test_model_id_value(self):
        result = self._call(model_id="G2")
        assert result["model_id"].unique().to_list() == ["G2"]

    def test_proba_sums_to_one(self):
        result = self._call()
        row_sums = result["p_BLACK_WIN"] + result["p_DRAW"] + result["p_WHITE_WIN"]
        assert all(abs(s - 1.0) < 1e-9 for s in row_sums.to_list())

    def test_has_selected_position_type(self):
        assert "selected_position_type" in self._call().columns

    def test_has_move_number(self):
        assert "move_number" in self._call().columns

    def test_has_is_time_forfeit(self):
        assert "is_time_forfeit" in self._call().columns


# ===========================================================================
# G. train_one_gbm
# ===========================================================================

class TestTrainOneGbm:
    def setup_method(self):
        self.broad_df = _make_broad_df(120)
        self.eval_df = _make_eval_df(60)
        self.assignments = _make_assignments(self.broad_df)
        plan = _make_modeling_plan()
        self.plan = plan
        fs_data = plan["feature_sets"]
        self.fs_lookup = {fs["id"]: list(fs["features"]) for fs in fs_data}

    def _train(self, model_id: str) -> tuple[dict, pl.DataFrame]:
        entry = build_gbm_registry()[model_id]
        return train_one_gbm(
            model_id, entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )

    def test_g1_returns_tuple(self):
        result, pred_df = self._train("G1")
        assert isinstance(result, dict)
        assert isinstance(pred_df, pl.DataFrame)

    def test_g1_model_id_key(self):
        result, _ = self._train("G1")
        assert result["model_id"] == "G1"

    def test_g1_model_type(self):
        result, _ = self._train("G1")
        assert result["model_type"] == "HistGradientBoostingClassifier"

    def test_g1_metrics_structure(self):
        result, _ = self._train("G1")
        assert "metrics" in result
        for split in ("train", "val", "test"):
            assert split in result["metrics"]

    def test_g1_has_accuracy(self):
        result, _ = self._train("G1")
        assert "accuracy" in result["metrics"]["val"]

    def test_g1_has_multiclass_brier(self):
        result, _ = self._train("G1")
        assert "multiclass_brier" in result["metrics"]["val"]

    def test_g1_no_brier_score_key(self):
        result, _ = self._train("G1")
        for split in ("train", "val", "test"):
            assert "brier_score" not in result["metrics"][split]

    def test_g1_feature_columns_used_no_string_cats(self):
        result, _ = self._train("G1")
        for col in STRING_CATEGORICALS_TO_DROP:
            assert col not in result["feature_columns_used"]

    def test_g1_has_feature_columns_dropped(self):
        result, _ = self._train("G1")
        assert "feature_columns_dropped" in result

    def test_g1_feature_columns_dropped_is_empty(self):
        # FS-B has no string categoricals — dropped list must be []
        result, _ = self._train("G1")
        assert result["feature_columns_dropped"] == []

    def test_g4_has_feature_columns_dropped(self):
        result, _ = self._train("G4")
        assert "feature_columns_dropped" in result

    def test_g4_feature_columns_dropped_contains_string_cats(self):
        result, _ = self._train("G4")
        dropped = result["feature_columns_dropped"]
        assert "selected_position_type" in dropped
        assert "phase" in dropped

    def test_g4_drops_selected_position_type(self):
        result, _ = self._train("G4")
        assert "selected_position_type" in result["feature_columns_requested"]
        assert "selected_position_type" not in result["feature_columns_used"]

    def test_g4_retains_checkpoint_index(self):
        result, _ = self._train("G4")
        assert "checkpoint_index" in result["feature_columns_used"]

    def test_predictions_has_model_id_col(self):
        _, pred_df = self._train("G1")
        assert "model_id" in pred_df.columns

    def test_predictions_has_all_splits(self):
        _, pred_df = self._train("G1")
        splits = set(pred_df["split_set"].unique().to_list())
        assert splits == {"train", "val", "test"}

    def test_g5_eval_table_trains(self):
        result, _ = self._train("G5")
        assert result["table"] == "eval"
        assert result["n_train_rows"] > 0

    def test_n_train_rows_positive(self):
        result, _ = self._train("G1")
        assert result["n_train_rows"] > 0


# ===========================================================================
# H. run_all_gbm
# ===========================================================================

class TestRunAllGbm:
    def setup_method(self):
        self.broad_df = _make_broad_df(120)
        self.eval_df = _make_eval_df(60)
        self.assignments = _make_assignments(self.broad_df)
        self.plan = _make_modeling_plan()

    def _run(self):
        return run_all_gbm(
            self.broad_df, self.eval_df, self.assignments, self.plan
        )

    def test_returns_dict_and_df(self):
        results, pred_df = self._run()
        assert isinstance(results, dict)
        assert isinstance(pred_df, pl.DataFrame)

    def test_has_all_six_models(self):
        results, _ = self._run()
        for mid in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            assert mid in results

    def test_no_errors(self):
        results, _ = self._run()
        for mid, res in results.items():
            assert "error" not in res, f"{mid} failed: {res.get('error')}"

    def test_predictions_has_model_id_col(self):
        _, pred_df = self._run()
        assert "model_id" in pred_df.columns

    def test_predictions_no_baseline_id_col(self):
        _, pred_df = self._run()
        assert "baseline_id" not in pred_df.columns

    def test_predictions_has_six_model_ids(self):
        _, pred_df = self._run()
        model_ids = set(pred_df["model_id"].unique().to_list())
        assert model_ids == {"G1", "G2", "G3", "G4", "G5", "G6"}

    def test_all_results_have_metrics(self):
        results, _ = self._run()
        for mid, res in results.items():
            assert "metrics" in res, f"{mid} missing metrics"

    def test_g1_val_accuracy_in_range(self):
        results, _ = self._run()
        acc = results["G1"]["metrics"]["val"]["accuracy"]
        assert 0.0 <= acc <= 1.0


# ===========================================================================
# I. build_gbm_results_payload
# ===========================================================================

class TestBuildGbmResultsPayload:
    def _payload(self, **kw):
        defaults = dict(
            dataset_id="test_id", version_tag="v1",
            split_artifact_path="splits.json",
            modeling_plan_path="plan.json",
            gbm_results={"G1": {"model_id": "G1"}},
        )
        defaults.update(kw)
        return build_gbm_results_payload(**defaults)

    def test_top_level_key_gbm_models(self):
        assert "gbm_models" in self._payload()

    def test_no_baselines_key(self):
        assert "baselines" not in self._payload()

    def test_has_dataset_id(self):
        assert self._payload()["dataset_id"] == "test_id"

    def test_has_created_at_utc(self):
        assert "created_at_utc" in self._payload()

    def test_no_generated_at_key(self):
        assert "generated_at" not in self._payload()

    def test_has_class_order(self):
        assert self._payload()["class_order"] == CLASS_ORDER

    def test_has_label_map(self):
        assert self._payload()["label_map"] == LABEL_MAP

    def test_has_gbm_params(self):
        assert "gbm_params" in self._payload()

    def test_has_split_artifact_path(self):
        assert self._payload()["split_artifact_path"] == "splits.json"

    def test_has_modeling_plan_path(self):
        assert self._payload()["modeling_plan_path"] == "plan.json"


# ===========================================================================
# J. save_gbm_outputs
# ===========================================================================

class TestSaveGbmOutputs:
    def setup_method(self):
        self.payload = build_gbm_results_payload(
            "test_id", "v1", "splits.json", "plan.json",
            {"G1": {"model_id": "G1"}}
        )
        self.pred_df = pl.DataFrame({
            "model_id": ["G1"] * 6,
            "split_set": ["val"] * 6,
            "game_id": [f"g_{i}" for i in range(6)],
        })

    def test_creates_json_file(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "v1")
            assert Path(paths["results_json"]).exists()

    def test_creates_parquet_file(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "v1")
            assert Path(paths["predictions_parquet"]).exists()

    def test_json_has_gbm_models_key(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "v1")
            with open(paths["results_json"]) as f:
                data = json.load(f)
            assert "gbm_models" in data

    def test_json_no_baselines_key(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "v1")
            with open(paths["results_json"]) as f:
                data = json.load(f)
            assert "baselines" not in data

    def test_parquet_readable(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "v1")
            df = pl.read_parquet(paths["predictions_parquet"])
            assert len(df) == 6

    def test_version_tag_in_filenames(self):
        with tempfile.TemporaryDirectory() as d:
            paths = save_gbm_outputs(self.payload, self.pred_df, d, "2024_09_v1")
            assert "2024_09_v1" in paths["results_json"]
            assert "2024_09_v1" in paths["predictions_parquet"]


# ===========================================================================
# K. render_gbm_report
# ===========================================================================

class TestRenderGbmReport:
    def setup_method(self):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df)
        plan = _make_modeling_plan()
        results, _ = run_all_gbm(broad_df, eval_df, assignments, plan)
        self.payload = build_gbm_results_payload(
            "test_id", "v1", "splits.json", "plan.json", results
        )
        self.output_paths = {
            "results_json": "data/processed/gbm_results_v1.json",
            "predictions_parquet": "data/processed/gbm_predictions_v1.parquet",
        }

    def test_returns_string(self):
        assert isinstance(render_gbm_report(self.payload, self.output_paths), str)

    def test_title_contains_ticket_6_1b(self):
        assert "Ticket 6.1B" in render_gbm_report(self.payload, self.output_paths)

    def test_labels_ml_d2_implementation(self):
        assert "ML | D2 | IMPLEMENTATION" in render_gbm_report(self.payload, self.output_paths)

    def test_no_d4_label(self):
        assert "D4" not in render_gbm_report(self.payload, self.output_paths)

    def test_first_gbm_implementation_in_title(self):
        assert "First GBM Implementation" in render_gbm_report(self.payload, self.output_paths)

    def test_histgbm_mentioned(self):
        assert "HistGradientBoostingClassifier" in render_gbm_report(self.payload, self.output_paths)

    def test_g1_in_report(self):
        assert "G1" in render_gbm_report(self.payload, self.output_paths)


# ===========================================================================
# L. print_gbm_summary
# ===========================================================================

class TestPrintGbmSummary:
    def test_runs_without_error(self, capsys):
        payload = build_gbm_results_payload(
            "test_id", "v1", "s.json", "p.json",
            {"G1": {
                "model_id": "G1", "table": "broad",
                "feature_set_id": "FS-B",
                "exploratory": False, "diagnostic": False,
                "metrics": {
                    "val": {"accuracy": 0.5, "log_loss": 1.0, "multiclass_brier": 0.5},
                    "test": {"accuracy": 0.5, "log_loss": 1.0},
                },
            }}
        )
        print_gbm_summary(payload)
        assert "G1" in capsys.readouterr().out

    def test_prints_all_model_ids(self, capsys):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df)
        plan = _make_modeling_plan()
        results, _ = run_all_gbm(broad_df, eval_df, assignments, plan)
        payload = build_gbm_results_payload("x", "v1", "s.json", "p.json", results)
        print_gbm_summary(payload)
        out = capsys.readouterr().out
        for mid in ["G1", "G2", "G3", "G4", "G5", "G6"]:
            assert mid in out

    def test_reads_gbm_models_key(self, capsys):
        payload = {"gbm_models": {}}
        print_gbm_summary(payload)
        assert "GBM" in capsys.readouterr().out


# ===========================================================================
# Schema enforcement
# ===========================================================================

class TestSchemaEnforcement:
    def test_no_prob_prefix_in_prediction_rows(self):
        n = 12
        df = _make_broad_df(n)
        y = np.array([0, 1, 2] * 4)
        proba = np.eye(3)[y]
        result = build_gbm_prediction_rows(
            "G1", "val", df, y, y, proba,
            "broad", "primary_numbered", False, False,
        )
        assert not any(c.startswith("prob_") for c in result.columns)

    def test_p_prefix_columns_all_present(self):
        n = 12
        df = _make_broad_df(n)
        y = np.array([0, 1, 2] * 4)
        proba = np.eye(3)[y]
        result = build_gbm_prediction_rows(
            "G1", "val", df, y, y, proba,
            "broad", "primary_numbered", False, False,
        )
        assert "p_BLACK_WIN" in result.columns
        assert "p_DRAW" in result.columns
        assert "p_WHITE_WIN" in result.columns

    def test_payload_has_created_at_utc_not_generated_at(self):
        payload = build_gbm_results_payload("x", "v1", "s.json", "p.json", {})
        assert "created_at_utc" in payload
        assert "generated_at" not in payload

    def test_train_one_gbm_no_brier_score_key(self):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df)
        plan = _make_modeling_plan()
        fs_lookup = {fs["id"]: list(fs["features"]) for fs in plan["feature_sets"]}
        entry = build_gbm_registry()["G1"]
        result, _ = train_one_gbm("G1", entry, fs_lookup, broad_df, eval_df, assignments)
        for split in ("train", "val", "test"):
            assert "brier_score" not in result["metrics"][split]

    def test_train_one_gbm_has_multiclass_brier(self):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df)
        plan = _make_modeling_plan()
        fs_lookup = {fs["id"]: list(fs["features"]) for fs in plan["feature_sets"]}
        entry = build_gbm_registry()["G1"]
        result, _ = train_one_gbm("G1", entry, fs_lookup, broad_df, eval_df, assignments)
        for split in ("train", "val", "test"):
            assert "multiclass_brier" in result["metrics"][split]

    def test_report_labels_no_d4(self):
        payload = build_gbm_results_payload("x", "v1", "s.json", "p.json", {})
        report = render_gbm_report(payload, {})
        assert "D4" not in report

    def test_report_labels_have_ml_d2(self):
        payload = build_gbm_results_payload("x", "v1", "s.json", "p.json", {})
        report = render_gbm_report(payload, {})
        assert "ML | D2 | IMPLEMENTATION" in report
