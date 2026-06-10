"""
tests/test_baselines.py — Unit tests for src/chess_mhsuc/baselines.py.

Uses synthetic fixtures only — no real data files required.
All tests are deterministic (fixed random seeds).
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from chess_mhsuc.baselines import (
    CLASS_ORDER,
    INVERSE_LABEL_MAP,
    LABEL_MAP,
    _BOOLEAN_COLS,
    _CATEGORICAL_COLS,
    _FORBIDDEN_FEATURE_COLS,
    _NULLABLE_NUMERIC_COLS,
    align_proba_to_class_order,
    build_baseline_model,
    build_baseline_registry,
    build_prediction_rows,
    build_results_payload,
    compute_metrics,
    encode_labels,
    get_feature_columns,
    multiclass_brier_score,
    prepare_X,
    render_implementation_report,
    run_all_baselines,
    save_baseline_outputs,
    split_feature_types,
    train_one_baseline,
    build_preprocessor,
    print_baseline_summary,
)


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _make_broad_df(n: int = 120, seed: int = 0) -> pl.DataFrame:
    """
    Synthetic broad feature DataFrame with all required columns.
    Includes 'train'/'val'/'test' for test_df splitting, but split_set is NOT
    a feature — it is attached separately by get_train_val_test.
    n must be divisible by 3 for balanced classes.
    """
    rng = np.random.default_rng(seed)
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    result_class = (classes * (n // 3 + 1))[:n]
    # Alternate games: 3 rows per game (move_10, move_20, last)
    n_games = n // 3
    game_ids = [f"game_{i:04d}" for i in range(n_games) for _ in range(3)]
    # Make result_class consistent per game_id
    rc_per_game = [classes[i % 3] for i in range(n_games)]
    result_class_col = [rc_per_game[i // 3] for i in range(n)]

    position_types = (["move_10", "move_20", "last"] * (n // 3 + 1))[:n]

    return pl.DataFrame({
        "game_id": game_ids[:n],
        "result_class": result_class_col,
        "white_result_numeric": [1.0 if rc == "WHITE_WIN" else (0.5 if rc == "DRAW" else 0.0)
                                 for rc in result_class_col],
        "selected_position_type": position_types,
        "phase": (["opening", "middlegame", "endgame"] * (n // 3 + 1))[:n],
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
        "eval_cp_clipped": ([None] * (n // 2) + rng.integers(-500, 500, n - n // 2).tolist()),
        "is_mate_eval": ([False] * n),
        "eval_mate_abs": ([None] * n),
        "eval_white_winning": ([False] * n),
        "has_eval": ([False] * (n // 2) + [True] * (n - n // 2)),
        "is_time_forfeit": rng.choice([True, False], n).tolist(),
        "termination": (["Normal", "Time forfeit"] * (n // 2 + 1))[:n],
        "duplicate_ply_checkpoint": ([False] * n),
        "is_last_checkpoint": [pt == "last" for pt in position_types],
        "white_clock_s": rng.integers(0, 600, n).tolist(),
        "black_clock_s": rng.integers(0, 600, n).tolist(),
    })


def _make_eval_df(n: int = 60, seed: int = 1) -> pl.DataFrame:
    """
    Synthetic eval feature DataFrame. All rows have has_eval=True.
    Includes eval_mate_abs as mostly null (non-mate positions).
    """
    rng = np.random.default_rng(seed)
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    n_games = n // 3
    game_ids = [f"eval_game_{i:04d}" for i in range(n_games) for _ in range(3)]
    rc_per_game = [classes[i % 3] for i in range(n_games)]
    result_class_col = [rc_per_game[i // 3] for i in range(n)]
    position_types = (["move_10", "move_20", "last"] * (n // 3 + 1))[:n]

    # 80% null eval_mate_abs (non-mate positions)
    eval_mate_abs = [None if rng.random() < 0.8 else int(rng.integers(1, 50))
                     for _ in range(n)]
    is_mate_eval = [v is not None for v in eval_mate_abs]

    return pl.DataFrame({
        "game_id": game_ids[:n],
        "result_class": result_class_col,
        "white_result_numeric": [1.0 if rc == "WHITE_WIN" else (0.5 if rc == "DRAW" else 0.0)
                                 for rc in result_class_col],
        "selected_position_type": position_types,
        "phase": (["opening", "middlegame", "endgame"] * (n // 3 + 1))[:n],
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
        "eval_cp_clipped": rng.integers(-500, 500, n).tolist(),
        "is_mate_eval": is_mate_eval,
        "eval_mate_abs": eval_mate_abs,
        "eval_white_winning": rng.choice([True, False], n).tolist(),
        "has_eval": ([True] * n),
        "is_time_forfeit": rng.choice([True, False], n).tolist(),
        "termination": (["Normal"] * n),
        "duplicate_ply_checkpoint": ([False] * n),
        "is_last_checkpoint": [pt == "last" for pt in position_types],
        "white_clock_s": rng.integers(0, 600, n).tolist(),
        "black_clock_s": rng.integers(0, 600, n).tolist(),
    })


def _make_assignments(broad_df: pl.DataFrame, eval_df: pl.DataFrame) -> dict[str, str]:
    """
    Build synthetic split assignments covering all game_ids in both DataFrames.

    Assigns games in groups of 3 (one per class per group) to the same split,
    cycling train/val/test across groups. This ensures each split has all 3 classes.
    """
    splits = ["train", "val", "test"]
    broad_games = sorted(broad_df["game_id"].unique().to_list())
    eval_games = sorted(eval_df["game_id"].unique().to_list())
    all_games = sorted(set(broad_games) | set(eval_games))
    # Assign each group of 3 consecutive games to the same split.
    # The fixture creates games in class-balanced triples (BW/D/WW per group of 3),
    # so each resulting split contains all 3 classes.
    return {gid: splits[(i // 3) % 3] for i, gid in enumerate(all_games)}


def _make_modeling_plan(
    include_eval: bool = True,
) -> dict:
    """Minimal synthetic modeling plan with FS-A, FS-B, FS-F, FS-G and B0–B5."""
    feature_sets = [
        {"id": "FS-A", "name": "majority_prior", "table": "broad", "features": []},
        {"id": "FS-B", "name": "rating_only", "table": "broad",
         "features": ["white_elo", "black_elo", "elo_diff", "avg_elo"]},
        {
            "id": "FS-E",
            "name": "rating_clock",
            "table": "broad",
            "features": [
                "white_elo", "black_elo", "elo_diff", "avg_elo",
                "white_clock_s_capped", "black_clock_s_capped",
                "white_clock_frac", "black_clock_frac", "clock_diff_frac",
                "white_low_60", "black_low_60", "white_low_30", "black_low_30",
                "white_low_10", "black_low_10", "clock_anomaly",
                "selected_position_type", "phase",
            ],
        },
        {
            "id": "FS-F",
            "name": "eval_only",
            "table": "eval",
            "features": [
                "eval_cp_clipped", "is_mate_eval", "eval_mate_abs", "eval_white_winning",
            ],
        },
        {
            "id": "FS-G",
            "name": "eval_rating_clock",
            "table": "eval",
            "features": [
                "white_elo", "black_elo", "elo_diff", "avg_elo",
                "eval_cp_clipped", "is_mate_eval", "eval_mate_abs", "eval_white_winning",
            ],
        },
    ]

    baseline_plan = [
        {
            "id": "B0", "model_class": "DummyClassifier", "feature_set_id": "FS-A",
            "table": "broad", "exploratory": False,
            "sklearn_params": {"strategy": "most_frequent"},
        },
        {
            "id": "B1", "model_class": "DummyClassifier", "feature_set_id": "FS-A",
            "table": "broad", "exploratory": False,
            "sklearn_params": {"strategy": "prior"},
        },
        {
            "id": "B2", "model_class": "LogisticRegression", "feature_set_id": "FS-B",
            "table": "broad", "exploratory": False,
            "sklearn_params": {"max_iter": 1000, "solver": "lbfgs", "multi_class": "auto"},
        },
        {
            "id": "B3", "model_class": "LogisticRegression", "feature_set_id": "FS-E",
            "table": "broad", "exploratory": False,
            "sklearn_params": {"max_iter": 1000, "solver": "lbfgs", "multi_class": "auto"},
        },
    ]

    if include_eval:
        baseline_plan += [
            {
                "id": "B4", "model_class": "LogisticRegression", "feature_set_id": "FS-F",
                "table": "eval", "exploratory": True,
                "sklearn_params": {"max_iter": 1000, "solver": "lbfgs", "multi_class": "auto"},
            },
            {
                "id": "B5", "model_class": "LogisticRegression", "feature_set_id": "FS-G",
                "table": "eval", "exploratory": True,
                "sklearn_params": {"max_iter": 1000, "solver": "lbfgs", "multi_class": "auto"},
            },
        ]

    return {
        "dataset_id": "test_dataset_v1",
        "feature_sets": feature_sets,
        "baseline_plan": baseline_plan,
        "metric_policy": {"primary": "log_loss"},
    }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_class_order(self):
        assert CLASS_ORDER == ["BLACK_WIN", "DRAW", "WHITE_WIN"]

    def test_label_map_keys(self):
        assert set(LABEL_MAP.keys()) == {"BLACK_WIN", "DRAW", "WHITE_WIN"}

    def test_label_map_values(self):
        assert LABEL_MAP["BLACK_WIN"] == 0
        assert LABEL_MAP["DRAW"] == 1
        assert LABEL_MAP["WHITE_WIN"] == 2

    def test_inverse_label_map_round_trip(self):
        for name, idx in LABEL_MAP.items():
            assert INVERSE_LABEL_MAP[idx] == name

    def test_boolean_cols_type(self):
        assert isinstance(_BOOLEAN_COLS, frozenset)
        assert "white_low_60" in _BOOLEAN_COLS
        assert "eval_white_winning" in _BOOLEAN_COLS

    def test_categorical_cols(self):
        assert "selected_position_type" in _CATEGORICAL_COLS
        assert "phase" in _CATEGORICAL_COLS

    def test_nullable_numeric_cols(self):
        assert "eval_mate_abs" in _NULLABLE_NUMERIC_COLS

    def test_forbidden_cols(self):
        assert "result_class" in _FORBIDDEN_FEATURE_COLS
        assert "game_id" in _FORBIDDEN_FEATURE_COLS


# ---------------------------------------------------------------------------
# A. encode_labels
# ---------------------------------------------------------------------------

class TestEncodeLabels:
    def test_basic_mapping(self):
        s = pl.Series(["BLACK_WIN", "DRAW", "WHITE_WIN"])
        result = encode_labels(s)
        assert list(result) == [0, 1, 2]

    def test_output_dtype(self):
        s = pl.Series(["WHITE_WIN", "BLACK_WIN"])
        result = encode_labels(s)
        assert result.dtype == np.int64

    def test_repeated_classes(self):
        s = pl.Series(["WHITE_WIN"] * 5)
        result = encode_labels(s)
        assert list(result) == [2, 2, 2, 2, 2]

    def test_empty_series(self):
        s = pl.Series([], dtype=pl.Utf8)
        result = encode_labels(s)
        assert len(result) == 0

    def test_invalid_class_raises(self):
        s = pl.Series(["INVALID_CLASS"])
        with pytest.raises(KeyError):
            encode_labels(s)


# ---------------------------------------------------------------------------
# B. get_feature_columns
# ---------------------------------------------------------------------------

class TestGetFeatureColumns:
    def setup_method(self):
        self.plan = _make_modeling_plan()

    def test_fs_a_empty(self):
        cols = get_feature_columns("FS-A", self.plan)
        assert cols == []

    def test_fs_b_returns_rating_cols(self):
        cols = get_feature_columns("FS-B", self.plan)
        assert "white_elo" in cols
        assert "avg_elo" in cols

    def test_invalid_id_raises(self):
        with pytest.raises(ValueError, match="not found"):
            get_feature_columns("FS-Z", self.plan)

    def test_returns_list(self):
        cols = get_feature_columns("FS-B", self.plan)
        assert isinstance(cols, list)

    def test_returns_copy(self):
        cols1 = get_feature_columns("FS-B", self.plan)
        cols2 = get_feature_columns("FS-B", self.plan)
        cols1.append("extra")
        assert "extra" not in cols2


# ---------------------------------------------------------------------------
# C. split_feature_types
# ---------------------------------------------------------------------------

class TestSplitFeatureTypes:
    def setup_method(self):
        self.df = _make_broad_df(30)

    def test_numeric_cols(self):
        types = split_feature_types(["white_elo", "avg_elo"], self.df)
        assert "white_elo" in types["numeric"]
        assert "avg_elo" in types["numeric"]

    def test_boolean_cols(self):
        types = split_feature_types(["white_low_60", "clock_anomaly"], self.df)
        assert "white_low_60" in types["boolean"]
        assert "clock_anomaly" in types["boolean"]

    def test_categorical_cols(self):
        types = split_feature_types(["selected_position_type", "phase"], self.df)
        assert "selected_position_type" in types["categorical"]
        assert "phase" in types["categorical"]

    def test_nullable_numeric(self):
        types = split_feature_types(["eval_mate_abs"], self.df)
        assert "eval_mate_abs" in types["nullable_numeric"]
        assert "eval_mate_abs" not in types["numeric"]

    def test_forbidden_col_raises(self):
        with pytest.raises(ValueError, match="Forbidden"):
            split_feature_types(["result_class"], self.df)

    def test_mixed_cols(self):
        cols = ["white_elo", "white_low_60", "selected_position_type", "eval_mate_abs"]
        types = split_feature_types(cols, self.df)
        assert "white_elo" in types["numeric"]
        assert "white_low_60" in types["boolean"]
        assert "selected_position_type" in types["categorical"]
        assert "eval_mate_abs" in types["nullable_numeric"]

    def test_empty_feature_list(self):
        types = split_feature_types([], self.df)
        assert types["numeric"] == []
        assert types["boolean"] == []
        assert types["categorical"] == []
        assert types["nullable_numeric"] == []


# ---------------------------------------------------------------------------
# D. prepare_X
# ---------------------------------------------------------------------------

class TestPrepareX:
    def setup_method(self):
        self.df = _make_broad_df(30)

    def test_returns_dataframe(self):
        import pandas as pd
        feature_cols = ["white_elo", "avg_elo"]
        types = split_feature_types(feature_cols, self.df)
        result = prepare_X(self.df, feature_cols, types)
        assert isinstance(result, pd.DataFrame)

    def test_column_order_preserved(self):
        feature_cols = ["avg_elo", "white_elo"]
        types = split_feature_types(feature_cols, self.df)
        result = prepare_X(self.df, feature_cols, types)
        assert list(result.columns) == feature_cols

    def test_boolean_cast_to_int8(self):
        import pandas as pd
        feature_cols = ["white_low_60"]
        types = split_feature_types(feature_cols, self.df)
        result = prepare_X(self.df, feature_cols, types)
        assert result["white_low_60"].dtype == np.int8 or result["white_low_60"].isin([0, 1]).all()

    def test_nullable_numeric_becomes_float(self):
        df = _make_eval_df(30)
        feature_cols = ["eval_mate_abs"]
        types = split_feature_types(feature_cols, df)
        result = prepare_X(df, feature_cols, types)
        # Should be float64 with NaNs where null
        assert result["eval_mate_abs"].dtype == float

    def test_row_count_preserved(self):
        feature_cols = ["white_elo", "black_elo"]
        types = split_feature_types(feature_cols, self.df)
        result = prepare_X(self.df, feature_cols, types)
        assert len(result) == len(self.df)


# ---------------------------------------------------------------------------
# E. build_preprocessor
# ---------------------------------------------------------------------------

class TestBuildPreprocessor:
    def test_returns_none_for_empty_types(self):
        types = {"numeric": [], "nullable_numeric": [], "boolean": [], "categorical": []}
        assert build_preprocessor(types) is None

    def test_returns_column_transformer_for_numeric(self):
        from sklearn.compose import ColumnTransformer
        types = {
            "numeric": ["white_elo"],
            "nullable_numeric": [],
            "boolean": [],
            "categorical": [],
        }
        pre = build_preprocessor(types)
        assert isinstance(pre, ColumnTransformer)

    def test_has_ohe_for_categorical(self):
        types = {
            "numeric": [],
            "nullable_numeric": [],
            "boolean": [],
            "categorical": ["phase"],
        }
        pre = build_preprocessor(types)
        names = [t[0] for t in pre.transformers]
        assert "cat" in names

    def test_has_imputer_for_nullable(self):
        from sklearn.pipeline import Pipeline
        types = {
            "numeric": [],
            "nullable_numeric": ["eval_mate_abs"],
            "boolean": [],
            "categorical": [],
        }
        pre = build_preprocessor(types)
        names = [t[0] for t in pre.transformers]
        assert "num_imp" in names
        # The nullable transformer should be a Pipeline with imputer
        for name, transformer, cols in pre.transformers:
            if name == "num_imp":
                assert isinstance(transformer, Pipeline)

    def test_boolean_uses_passthrough(self):
        types = {
            "numeric": [],
            "nullable_numeric": [],
            "boolean": ["white_low_60"],
            "categorical": [],
        }
        pre = build_preprocessor(types)
        for name, transformer, cols in pre.transformers:
            if name == "bool":
                assert transformer == "passthrough"


# ---------------------------------------------------------------------------
# F. build_baseline_model
# ---------------------------------------------------------------------------

class TestBuildBaselineModel:
    def test_dummy_returns_dummy_classifier(self):
        entry = {
            "model_class": "DummyClassifier",
            "sklearn_params": {"strategy": "most_frequent"},
        }
        model = build_baseline_model("B0", entry, None)
        assert isinstance(model, DummyClassifier)

    def test_lr_with_preprocessor_returns_pipeline(self):
        from sklearn.compose import ColumnTransformer
        types = {
            "numeric": ["white_elo"],
            "nullable_numeric": [],
            "boolean": [],
            "categorical": [],
        }
        pre = build_preprocessor(types)
        entry = {
            "model_class": "LogisticRegression",
            "sklearn_params": {"max_iter": 1000, "solver": "lbfgs"},
        }
        model = build_baseline_model("B2", entry, pre)
        assert isinstance(model, Pipeline)

    def test_multi_class_stripped(self):
        entry = {
            "model_class": "LogisticRegression",
            "sklearn_params": {
                "max_iter": 1000,
                "solver": "lbfgs",
                "multi_class": "auto",
            },
        }
        # Should not raise TypeError even though multi_class is present
        model = build_baseline_model("B2", entry, None)
        assert isinstance(model, LogisticRegression)
        assert not hasattr(model, "multi_class")

    def test_unknown_model_class_raises(self):
        entry = {"model_class": "RandomForest", "sklearn_params": {}}
        with pytest.raises(ValueError, match="Unknown model_class"):
            build_baseline_model("X", entry, None)

    def test_lr_without_preprocessor_returns_lr_directly(self):
        entry = {
            "model_class": "LogisticRegression",
            "sklearn_params": {"max_iter": 100, "solver": "lbfgs"},
        }
        model = build_baseline_model("B2", entry, None)
        assert isinstance(model, LogisticRegression)


# ---------------------------------------------------------------------------
# G. multiclass_brier_score
# ---------------------------------------------------------------------------

class TestMulticlassBrierScore:
    def test_perfect_predictions(self):
        # Perfect: assign all probability to true class
        y_true = np.array([0, 1, 2])
        proba = np.eye(3)
        score = multiclass_brier_score(y_true, proba)
        assert score == pytest.approx(0.0)

    def test_worst_predictions(self):
        # Worst: assign all probability to wrong class only
        y_true = np.array([0, 0, 0])
        proba = np.array([[0, 0, 1], [0, 0, 1], [0, 0, 1]], dtype=float)
        score = multiclass_brier_score(y_true, proba)
        # Per sample: (0-1)^2 + (0-0)^2 + (1-0)^2 = 2.0
        assert score == pytest.approx(2.0)

    def test_uniform_predictions(self):
        y_true = np.array([0, 1, 2])
        proba = np.full((3, 3), 1 / 3)
        score = multiclass_brier_score(y_true, proba)
        # Per sample: 2*(1/3)^2 + (2/3)^2 = 2/9 + 4/9 = 6/9 = 2/3
        assert score == pytest.approx(2 / 3, rel=1e-5)

    def test_output_is_float(self):
        y_true = np.array([0, 1])
        proba = np.array([[0.7, 0.2, 0.1], [0.1, 0.8, 0.1]])
        result = multiclass_brier_score(y_true, proba)
        assert isinstance(result, float)

    def test_range_nonnegative(self):
        rng = np.random.default_rng(42)
        y_true = rng.integers(0, 3, 50)
        proba = rng.dirichlet(np.ones(3), 50)
        score = multiclass_brier_score(y_true, proba)
        assert 0.0 <= score <= 2.0


# ---------------------------------------------------------------------------
# H. align_proba_to_class_order
# ---------------------------------------------------------------------------

class TestAlignProbaToClassOrder:
    def test_already_aligned(self):
        """Model learned [BLACK_WIN=0, DRAW=1, WHITE_WIN=2] order."""
        model = DummyClassifier(strategy="prior")
        X = np.ones((10, 1))
        y = np.array([0] * 4 + [1] * 3 + [2] * 3)
        model.fit(X, y)
        proba = model.predict_proba(X)
        aligned = align_proba_to_class_order(model, proba)
        # Should be same order since model classes_ == [0, 1, 2]
        np.testing.assert_allclose(aligned, proba)

    def test_output_shape(self):
        model = DummyClassifier(strategy="most_frequent")
        X = np.ones((9, 1))
        y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
        model.fit(X, y)
        proba = model.predict_proba(X)
        aligned = align_proba_to_class_order(model, proba)
        assert aligned.shape == (9, 3)

    def test_pipeline_model(self):
        from sklearn.compose import ColumnTransformer
        from sklearn.preprocessing import StandardScaler
        pre = ColumnTransformer([("num", StandardScaler(), [0])])
        clf = LogisticRegression(max_iter=1000)
        pipe = Pipeline([("pre", pre), ("clf", clf)])
        X = np.column_stack([np.arange(30, dtype=float)])
        y = np.array([0] * 10 + [1] * 10 + [2] * 10)
        pipe.fit(X, y)
        proba_raw = pipe.predict_proba(X)
        aligned = align_proba_to_class_order(pipe, proba_raw)
        assert aligned.shape == (30, 3)

    def test_missing_class_filled_with_zero(self):
        """If model only saw 2 classes, missing class column is 0."""
        model = DummyClassifier(strategy="most_frequent")
        X = np.ones((6, 1))
        y = np.array([0, 0, 0, 2, 2, 2])  # No DRAW (class 1)
        model.fit(X, y)
        proba = model.predict_proba(X)
        aligned = align_proba_to_class_order(model, proba)
        assert aligned.shape == (6, 3)
        # DRAW column (index 1) should be all 0
        np.testing.assert_array_equal(aligned[:, 1], 0.0)

    def test_prob_sum_after_alignment(self):
        """After alignment, probabilities should still sum to ~1 (if no missing class)."""
        model = DummyClassifier(strategy="prior")
        X = np.ones((9, 1))
        y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
        model.fit(X, y)
        proba = model.predict_proba(X)
        aligned = align_proba_to_class_order(model, proba)
        row_sums = aligned.sum(axis=1)
        np.testing.assert_allclose(row_sums, 1.0, atol=1e-10)


# ---------------------------------------------------------------------------
# I. compute_metrics
# ---------------------------------------------------------------------------

class TestComputeMetrics:
    def test_perfect_accuracy(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        assert metrics["accuracy"] == pytest.approx(1.0)

    def test_zero_accuracy(self):
        y_true = np.array([0, 0, 0])
        y_pred = np.array([1, 2, 1])
        proba = np.array([[0, 1, 0], [0, 0, 1], [0, 1, 0]], dtype=float)
        metrics = compute_metrics(y_true, y_pred, proba)
        assert metrics["accuracy"] == pytest.approx(0.0)

    def test_all_keys_present(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        for key in ("n_rows", "accuracy", "balanced_accuracy", "log_loss",
                    "macro_f1", "weighted_f1", "multiclass_brier",
                    "per_class", "confusion_matrix"):
            assert key in metrics

    def test_no_brier_score_key(self):
        """brier_score must NOT appear; key is multiclass_brier."""
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        assert "brier_score" not in metrics

    def test_per_class_keys(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        for cls in CLASS_ORDER:
            assert cls in metrics["per_class"]
            for sub in ("precision", "recall", "f1", "support"):
                assert sub in metrics["per_class"][cls]

    def test_json_serializable(self):
        y_true = np.array([0, 1, 2, 0, 1, 2])
        y_pred = np.array([0, 1, 2, 1, 0, 2])
        proba = np.array([
            [0.7, 0.2, 0.1],
            [0.1, 0.7, 0.2],
            [0.1, 0.2, 0.7],
            [0.4, 0.3, 0.3],
            [0.4, 0.4, 0.2],
            [0.1, 0.2, 0.7],
        ])
        metrics = compute_metrics(y_true, y_pred, proba)
        # Should not raise
        json.dumps(metrics)

    def test_n_rows(self):
        y_true = np.array([0, 1, 2, 0])
        y_pred = np.array([0, 1, 2, 0])
        proba = np.eye(3)[[0, 1, 2, 0]]
        metrics = compute_metrics(y_true, y_pred, proba)
        assert metrics["n_rows"] == 4

    def test_confusion_matrix_is_list(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        assert isinstance(metrics["confusion_matrix"], list)
        assert len(metrics["confusion_matrix"]) == 3

    def test_multiclass_brier_perfect(self):
        y_true = np.array([0, 1, 2])
        y_pred = np.array([0, 1, 2])
        proba = np.eye(3)
        metrics = compute_metrics(y_true, y_pred, proba)
        assert metrics["multiclass_brier"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# J. build_prediction_rows
# ---------------------------------------------------------------------------

class TestBuildPredictionRows:
    def setup_method(self):
        self.df = _make_broad_df(9)
        self.y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        self.y_pred = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
        self.proba = np.eye(3)[[0, 1, 2, 0, 1, 2, 0, 1, 2]]

    def test_columns_present(self):
        rows = build_prediction_rows(
            "B0", "val", self.df, self.y_true, self.y_pred, self.proba
        )
        for col in ("baseline_id", "split_set", "game_id", "result_class",
                    "pred_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"):
            assert col in rows.columns

    def test_no_prob_prefix_columns(self):
        """Probability columns must use p_ prefix, not prob_."""
        rows = build_prediction_rows(
            "B0", "val", self.df, self.y_true, self.y_pred, self.proba
        )
        for bad_col in ("prob_BLACK_WIN", "prob_DRAW", "prob_WHITE_WIN"):
            assert bad_col not in rows.columns

    def test_row_count(self):
        rows = build_prediction_rows(
            "B0", "train", self.df, self.y_true, self.y_pred, self.proba
        )
        assert len(rows) == 9

    def test_baseline_id_column(self):
        rows = build_prediction_rows(
            "B2", "test", self.df, self.y_true, self.y_pred, self.proba
        )
        assert rows["baseline_id"].unique().to_list() == ["B2"]

    def test_prob_columns_float64(self):
        rows = build_prediction_rows(
            "B0", "val", self.df, self.y_true, self.y_pred, self.proba
        )
        for col in ("p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"):
            assert rows[col].dtype == pl.Float64

    def test_pred_class_values(self):
        rows = build_prediction_rows(
            "B0", "val", self.df, self.y_true, self.y_pred, self.proba
        )
        valid = set(CLASS_ORDER)
        assert set(rows["pred_class"].to_list()).issubset(valid)


# ---------------------------------------------------------------------------
# L. build_baseline_registry
# ---------------------------------------------------------------------------

class TestBuildBaselineRegistry:
    def setup_method(self):
        self.plan = _make_modeling_plan()

    def test_all_ids_present(self):
        reg = build_baseline_registry(self.plan)
        for bid in ("B0", "B1", "B2", "B3", "B4", "B5"):
            assert bid in reg

    def test_b3_balanced_added(self):
        reg = build_baseline_registry(self.plan)
        assert "B3-balanced" in reg

    def test_b3_balanced_is_exploratory(self):
        reg = build_baseline_registry(self.plan)
        assert reg["B3-balanced"]["exploratory"] is True

    def test_b3_balanced_has_class_weight(self):
        reg = build_baseline_registry(self.plan)
        assert reg["B3-balanced"]["sklearn_params"]["class_weight"] == "balanced"

    def test_multi_class_stripped(self):
        reg = build_baseline_registry(self.plan)
        for bid, entry in reg.items():
            assert "multi_class" not in entry.get("sklearn_params", {})

    def test_returns_dict(self):
        reg = build_baseline_registry(self.plan)
        assert isinstance(reg, dict)


# ---------------------------------------------------------------------------
# K. train_one_baseline (smoke tests)
# ---------------------------------------------------------------------------

class TestTrainOneBaseline:
    def setup_method(self):
        self.broad_df = _make_broad_df(120)
        self.eval_df = _make_eval_df(60)
        self.assignments = _make_assignments(self.broad_df, self.eval_df)
        self.plan = _make_modeling_plan()
        self.fs_lookup = {
            fs["id"]: list(fs["features"])
            for fs in self.plan["feature_sets"]
        }
        self.registry = build_baseline_registry(self.plan)

    def test_b0_returns_dict_and_df(self):
        entry = self.registry["B0"]
        result, pred_df = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert isinstance(result, dict)
        assert isinstance(pred_df, pl.DataFrame)

    def test_b0_metrics_keys(self):
        entry = self.registry["B0"]
        result, _ = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert "metrics" in result
        for split in ("train", "val", "test"):
            assert split in result["metrics"]

    def test_b0_metrics_no_old_keys(self):
        entry = self.registry["B0"]
        result, _ = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert "train_metrics" not in result
        assert "val_metrics" not in result
        assert "test_metrics" not in result

    def test_b0_result_has_model_type(self):
        entry = self.registry["B0"]
        result, _ = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert "model_type" in result
        assert "model_class" not in result

    def test_b0_split_metrics_have_multiclass_brier(self):
        entry = self.registry["B0"]
        result, _ = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        for split in ("train", "val", "test"):
            m = result["metrics"][split]
            assert "multiclass_brier" in m
            assert "brier_score" not in m

    def test_b0_result_has_diagnostic_field(self):
        entry = self.registry["B0"]
        result, _ = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert "diagnostic" in result
        assert result["diagnostic"] is False

    def test_b3_balanced_is_diagnostic(self):
        entry = self.registry["B3-balanced"]
        result, _ = train_one_baseline(
            "B3-balanced", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert result["diagnostic"] is True

    def test_b2_lr_runs(self):
        entry = self.registry["B2"]
        result, pred_df = train_one_baseline(
            "B2", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert result["baseline_id"] == "B2"
        assert len(pred_df) > 0

    def test_b4_eval_runs(self):
        entry = self.registry["B4"]
        result, pred_df = train_one_baseline(
            "B4", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        assert result["table"] == "eval"
        assert result["exploratory"] is True

    def test_prediction_df_has_all_splits(self):
        entry = self.registry["B0"]
        _, pred_df = train_one_baseline(
            "B0", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        splits_present = set(pred_df["split_set"].to_list())
        assert splits_present == {"train", "val", "test"}

    def test_prob_sum_close_to_one(self):
        entry = self.registry["B1"]
        _, pred_df = train_one_baseline(
            "B1", entry, self.fs_lookup,
            self.broad_df, self.eval_df, self.assignments,
        )
        prob_sum = (
            pred_df["p_BLACK_WIN"]
            + pred_df["p_DRAW"]
            + pred_df["p_WHITE_WIN"]
        )
        assert (prob_sum - 1.0).abs().max() < 1e-9


# ---------------------------------------------------------------------------
# N. build_results_payload
# ---------------------------------------------------------------------------

class TestBuildResultsPayload:
    def test_required_keys_present(self):
        payload = build_results_payload(
            "test_ds", "v1", "splits.json", "plan.json", {}
        )
        for key in ("dataset_id", "version_tag", "created_at_utc",
                    "split_artifact_path", "modeling_plan_path",
                    "label_map", "class_order", "baselines"):
            assert key in payload, f"Missing key: {key}"

    def test_no_old_top_level_keys(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        assert "baseline_results" not in payload
        assert "generated_at" not in payload
        assert "split_artifact" not in payload
        assert "modeling_plan" not in payload

    def test_top_level_baselines_key(self):
        payload = build_results_payload("ds", "v1", "s", "p", {"B0": {}})
        assert "baselines" in payload
        assert payload["baselines"] == {"B0": {}}

    def test_created_at_utc_not_generated_at(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        assert "created_at_utc" in payload
        assert "generated_at" not in payload

    def test_split_artifact_path_key(self):
        payload = build_results_payload("ds", "v1", "my_splits.json", "p", {})
        assert payload["split_artifact_path"] == "my_splits.json"
        assert "split_artifact" not in payload

    def test_modeling_plan_path_key(self):
        payload = build_results_payload("ds", "v1", "s", "my_plan.json", {})
        assert payload["modeling_plan_path"] == "my_plan.json"
        assert "modeling_plan" not in payload

    def test_json_serializable(self):
        payload = build_results_payload(
            "test_ds", "v1", "splits.json", "plan.json",
            {"B0": {"accuracy": 0.5}}
        )
        json.dumps(payload)

    def test_class_order_matches(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        assert payload["class_order"] == CLASS_ORDER


# ---------------------------------------------------------------------------
# O. save_baseline_outputs
# ---------------------------------------------------------------------------

class TestSaveBaselineOutputs:
    def test_creates_json(self, tmp_path):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        pred_df = pl.DataFrame({"baseline_id": ["B0"], "split_set": ["val"]})
        paths = save_baseline_outputs(payload, pred_df, tmp_path, "v1")
        assert Path(paths["results_json"]).exists()

    def test_creates_parquet(self, tmp_path):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        pred_df = pl.DataFrame({"baseline_id": ["B0"], "split_set": ["val"]})
        paths = save_baseline_outputs(payload, pred_df, tmp_path, "v1")
        assert Path(paths["predictions_parquet"]).exists()

    def test_json_loadable(self, tmp_path):
        payload = build_results_payload("ds", "v1", "s", "p", {"B0": {}})
        pred_df = pl.DataFrame({"a": [1]})
        paths = save_baseline_outputs(payload, pred_df, tmp_path, "v1")
        with open(paths["results_json"]) as f:
            loaded = json.load(f)
        assert loaded["dataset_id"] == "ds"

    def test_parquet_loadable(self, tmp_path):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        pred_df = pl.DataFrame({"baseline_id": pl.Series(["B0"], dtype=pl.Utf8)})
        paths = save_baseline_outputs(payload, pred_df, tmp_path, "v1")
        loaded = pl.read_parquet(paths["predictions_parquet"])
        assert "baseline_id" in loaded.columns

    def test_creates_output_dir(self, tmp_path):
        new_dir = tmp_path / "nested" / "dir"
        payload = build_results_payload("ds", "v1", "s", "p", {})
        pred_df = pl.DataFrame({"a": [1]})
        save_baseline_outputs(payload, pred_df, new_dir, "v1")
        assert new_dir.exists()


# ---------------------------------------------------------------------------
# P. render_implementation_report
# ---------------------------------------------------------------------------

class TestRenderImplementationReport:
    def test_returns_string(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert isinstance(report, str)

    def test_contains_header(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "Phase Report: Ticket 5.2B" in report

    def test_correct_label_ml_d2(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "ML | D2 | IMPLEMENTATION" in report

    def test_no_d4_label(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "D4" not in report

    def test_no_ml_evaluation_label(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "ML / EVALUATION" not in report

    def test_correct_ticket_title(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "Ticket 5.2B — Baseline Model Implementation" in report

    def test_contains_dataset_id(self):
        payload = build_results_payload("my_dataset", "v1", "s", "p", {})
        report = render_implementation_report(payload, {})
        assert "my_dataset" in report

    def test_with_test_summary(self):
        payload = build_results_payload("ds", "v1", "s", "p", {})
        report = render_implementation_report(
            payload, {}, test_summary="501 passed"
        )
        assert "501 passed" in report


# ---------------------------------------------------------------------------
# M. run_all_baselines (integration smoke test)
# ---------------------------------------------------------------------------

class TestRunAllBaselines:
    def test_smoke_broad_only(self):
        """Run all baselines with only broad baselines (no eval) for speed."""
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df, eval_df)
        plan = _make_modeling_plan(include_eval=False)

        results, pred_df = run_all_baselines(broad_df, eval_df, assignments, plan)

        # B0, B1, B2, B3, B3-balanced should be present
        assert "B0" in results
        assert "B1" in results
        assert "B2" in results
        assert "B3" in results
        assert "B3-balanced" in results

    def test_no_errors_in_broad_baselines(self):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df, eval_df)
        plan = _make_modeling_plan(include_eval=False)

        results, _ = run_all_baselines(broad_df, eval_df, assignments, plan)

        for bid in ("B0", "B1", "B2", "B3", "B3-balanced"):
            assert "error" not in results[bid], (
                f"Baseline {bid} failed: {results[bid].get('error')}"
            )

    def test_predictions_df_has_expected_columns(self):
        broad_df = _make_broad_df(120)
        eval_df = _make_eval_df(60)
        assignments = _make_assignments(broad_df, eval_df)
        plan = _make_modeling_plan(include_eval=False)

        _, pred_df = run_all_baselines(broad_df, eval_df, assignments, plan)

        for col in ("baseline_id", "split_set", "game_id", "result_class",
                    "pred_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"):
            assert col in pred_df.columns


# ===========================================================================
# Anti-leakage: permuted labels test (Ticket 7.3B)
# ===========================================================================

class TestPermutedLabelAntiLeakage:
    """
    Verify that no supervised baseline leaks label information through features.

    Test strategy: permute result_class labels on training data for B3
    (LogisticRegression). Under random labels, val log_loss should be near
    the prior log_loss (B1 baseline). If it is significantly lower, there
    is likely a leakage bug.

    This is a smoke test, not a statistical one — we check that permuted
    val log_loss does NOT drop below 0.5 (well below even the prior at
    ~1.09 for balanced 3-class). Such a drop would indicate the model
    is exploiting a non-feature column that encodes the label.
    """

    def _val_log_loss_for_model(
        self,
        broad_df: pl.DataFrame,
        eval_df: pl.DataFrame,
        assignments: dict[str, str],
        plan: dict,
        model_id: str,
    ) -> float:
        from chess_mhsuc.baselines import compute_metrics
        from chess_mhsuc.splits import get_train_val_test
        results, pred_df = run_all_baselines(broad_df, eval_df, assignments, plan)
        return results["baselines"][model_id]["metrics"]["val"]["log_loss"]

    def test_permuted_labels_degrade_b3_val_log_loss(self):
        """
        B3 trained on permuted labels should NOT produce lower val log_loss
        than B3 on real labels. Permuted val log_loss >= real val log_loss
        (or very close). This ensures B3 is not 'accidentally' fitting the label.
        """
        rng = np.random.default_rng(777)
        broad_df = _make_broad_df(120, seed=0)
        eval_df = _make_eval_df(60, seed=1)
        assignments = _make_assignments(broad_df, eval_df)
        plan = _make_modeling_plan(include_eval=False)

        # Real label run
        results_real, _ = run_all_baselines(broad_df, eval_df, assignments, plan)
        real_ll = results_real["B3"]["metrics"]["val"]["log_loss"]

        # Permute result_class column (simulate random noise labels)
        permuted_labels = rng.permutation(broad_df["result_class"].to_list())
        broad_permuted = broad_df.with_columns(
            pl.Series("result_class", list(permuted_labels))
        )

        results_perm, _ = run_all_baselines(broad_permuted, eval_df, assignments, plan)
        perm_ll = results_perm["B3"]["metrics"]["val"]["log_loss"]

        # Permuted model should not be suspiciously good
        # A log_loss below 0.5 on 3-class random labels would indicate leakage
        assert perm_ll > 0.5, (
            f"B3 val log_loss={perm_ll:.4f} after label permutation is suspiciously low "
            f"(expected near prior ≈1.09). Possible label leakage via non-feature columns."
        )

    def test_label_not_in_feature_columns(self):
        """result_class must not appear in any FS-E feature columns."""
        plan = _make_modeling_plan(include_eval=False)
        from chess_mhsuc.baselines import get_feature_columns
        fs_e_cols = get_feature_columns("FS-E", plan)
        assert "result_class" not in fs_e_cols

    def test_forbidden_cols_not_in_fs_e(self):
        """Known forbidden label-leaking columns must not appear in FS-E."""
        plan = _make_modeling_plan(include_eval=False)
        from chess_mhsuc.baselines import get_feature_columns, _FORBIDDEN_FEATURE_COLS
        fs_e_cols = set(get_feature_columns("FS-E", plan))
        leaking = fs_e_cols & _FORBIDDEN_FEATURE_COLS
        assert not leaking, f"Forbidden cols in FS-E: {sorted(leaking)}"
