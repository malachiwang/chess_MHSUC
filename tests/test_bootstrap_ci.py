"""
tests/test_bootstrap_ci.py — Unit tests for src/chess_mhsuc/bootstrap_ci.py.

Uses synthetic fixtures only — no real data files required.
All tests are deterministic (fixed random seeds).
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.bootstrap_ci import (
    _BOOTSTRAP_MODEL_IDS,
    _PAIRWISE_COMPARISONS,
    _PROB_COLS,
    build_bootstrap_payload,
    build_game_row_index,
    compute_ci_from_bootstrap,
    compute_delta_ci,
    compute_point_log_loss,
    extract_val_rows,
    get_unique_val_game_ids,
    load_baseline_predictions,
    load_gbm_predictions,
    render_bootstrap_report,
    run_all_bootstrap,
    run_all_pairwise_deltas,
    run_bootstrap,
    run_bootstrap_for_model,
    run_paired_delta_bootstrap,
    standardize_prediction_schema,
)


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _make_prediction_df(
    n_games: int = 30,
    model_id: str = "B3",
    model_col: str = "model_id",
    split_set: str = "val",
    seed: int = 0,
) -> pl.DataFrame:
    """
    Synthetic prediction DataFrame with 2 rows per game (move_10, move_20).
    Classes cycle: BLACK_WIN, DRAW, WHITE_WIN.
    Probabilities are near-uniform (noisy) for realistic log_loss.
    """
    rng = np.random.default_rng(seed)
    n = n_games * 2
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    result_class = [classes[i % 3] for i in range(n_games) for _ in range(2)]
    game_ids = [f"game_{i:04d}" for i in range(n_games) for _ in range(2)]

    raw = rng.dirichlet(alpha=[2.0, 1.0, 2.0], size=n)
    p_bw = raw[:, 0].tolist()
    p_d = raw[:, 1].tolist()
    p_ww = raw[:, 2].tolist()

    return pl.DataFrame({
        model_col: [model_id] * n,
        "split_set": [split_set] * n,
        "game_id": game_ids,
        "result_class": result_class,
        "p_BLACK_WIN": p_bw,
        "p_DRAW": p_d,
        "p_WHITE_WIN": p_ww,
    })


def _make_baseline_preds(n_games: int = 30, seed: int = 0) -> pl.DataFrame:
    """Synthetic baseline predictions DataFrame using baseline_id column."""
    frames = []
    for mid in ["B1", "B2", "B3"]:
        df = _make_prediction_df(
            n_games=n_games, model_id=mid, model_col="baseline_id",
            split_set="val", seed=seed,
        )
        frames.append(df)
    return pl.concat(frames)


def _make_gbm_preds(n_games: int = 30, seed: int = 0) -> pl.DataFrame:
    """Synthetic GBM predictions DataFrame with view column."""
    df = _make_prediction_df(
        n_games=n_games, model_id="G2", model_col="model_id",
        split_set="val", seed=seed,
    )
    return df.with_columns(pl.lit("primary_numbered").alias("view"))


def _make_combined_df(
    n_games: int = 30,
    include_g2b: bool = False,
    seed: int = 0,
) -> pl.DataFrame:
    """
    Build a unified combined prediction DataFrame for bootstrap tests.
    model_id column, split_set='val', includes B1, B2, B3, G2 (+ optionally G2b).
    """
    n = n_games * 2
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    result_class = [classes[i % 3] for i in range(n_games) for _ in range(2)]
    game_ids = [f"game_{i:04d}" for i in range(n_games) for _ in range(2)]

    frames = []
    for mid in (["B1", "B2", "B3", "G2"] + (["G2b"] if include_g2b else [])):
        rng2 = np.random.default_rng(seed + hash(mid) % 1000)
        raw = rng2.dirichlet(alpha=[2.0, 1.0, 2.0], size=n)
        frames.append(pl.DataFrame({
            "model_id": [mid] * n,
            "split_set": ["val"] * n,
            "game_id": game_ids,
            "result_class": result_class,
            "p_BLACK_WIN": raw[:, 0].tolist(),
            "p_DRAW": raw[:, 1].tolist(),
            "p_WHITE_WIN": raw[:, 2].tolist(),
        }))
    return pl.concat(frames)


# ===========================================================================
# A. load_baseline_predictions
# ===========================================================================

class TestLoadBaselinePredictions:
    def test_loads_valid_df(self, tmp_path):
        df = _make_baseline_preds()
        path = tmp_path / "bp.parquet"
        df.write_parquet(path)
        result = load_baseline_predictions(path)
        assert isinstance(result, pl.DataFrame)

    def test_missing_column_raises(self, tmp_path):
        df = _make_baseline_preds().drop("p_DRAW")
        path = tmp_path / "bp.parquet"
        df.write_parquet(path)
        with pytest.raises(ValueError, match="missing columns"):
            load_baseline_predictions(path)


# ===========================================================================
# B. load_gbm_predictions
# ===========================================================================

class TestLoadGbmPredictions:
    def test_loads_valid_df(self, tmp_path):
        df = _make_gbm_preds()
        path = tmp_path / "gp.parquet"
        df.write_parquet(path)
        result = load_gbm_predictions(path)
        assert isinstance(result, pl.DataFrame)

    def test_missing_view_column_raises(self, tmp_path):
        df = _make_gbm_preds().drop("view")
        path = tmp_path / "gp.parquet"
        df.write_parquet(path)
        with pytest.raises(ValueError, match="missing columns"):
            load_gbm_predictions(path)


# ===========================================================================
# C. standardize_prediction_schema
# ===========================================================================

class TestStandardizePredictionSchema:
    def _make_inputs(self, n_games: int = 20):
        baseline = _make_baseline_preds(n_games)
        gbm = _make_gbm_preds(n_games)
        return baseline, gbm

    def test_returns_polars_df(self):
        baseline, gbm = self._make_inputs()
        result = standardize_prediction_schema(baseline, gbm)
        assert isinstance(result, pl.DataFrame)

    def test_has_model_id_column(self):
        baseline, gbm = self._make_inputs()
        result = standardize_prediction_schema(baseline, gbm)
        assert "model_id" in result.columns

    def test_no_baseline_id_column(self):
        baseline, gbm = self._make_inputs()
        result = standardize_prediction_schema(baseline, gbm)
        assert "baseline_id" not in result.columns

    def test_only_bootstrap_model_ids(self):
        baseline, gbm = self._make_inputs()
        result = standardize_prediction_schema(baseline, gbm)
        ids = set(result["model_id"].unique().to_list())
        assert ids <= set(_BOOTSTRAP_MODEL_IDS)

    def test_extra_df_adds_g2b(self):
        baseline, gbm = self._make_inputs()
        extra = _make_prediction_df(
            n_games=20, model_id="G2b", model_col="model_id",
            split_set="val",
        ).with_columns(pl.lit("primary_numbered").alias("view"))
        result = standardize_prediction_schema(baseline, gbm, extra_df=extra)
        ids = set(result["model_id"].unique().to_list())
        assert "G2b" in ids

    def test_gbm_filtered_to_primary_numbered(self):
        baseline, gbm = self._make_inputs()
        gbm_mixed = gbm.with_columns(pl.lit("other_view").alias("view"))
        result = standardize_prediction_schema(baseline, gbm_mixed)
        ids = set(result["model_id"].unique().to_list())
        assert "G2" not in ids

    def test_b2_included(self):
        baseline, gbm = self._make_inputs()
        result = standardize_prediction_schema(baseline, gbm)
        ids = set(result["model_id"].unique().to_list())
        assert "B2" in ids


# ===========================================================================
# D. extract_val_rows
# ===========================================================================

class TestExtractValRows:
    def test_returns_only_val_rows(self):
        combined = _make_combined_df(n_games=20)
        result = extract_val_rows(combined, "B3")
        assert set(result["split_set"].unique().to_list()) == {"val"}

    def test_returns_only_target_model(self):
        combined = _make_combined_df(n_games=20)
        result = extract_val_rows(combined, "B3")
        assert set(result["model_id"].unique().to_list()) == {"B3"}

    def test_missing_model_raises(self):
        combined = _make_combined_df(n_games=20)
        with pytest.raises(ValueError, match="No validation rows"):
            extract_val_rows(combined, "G99")


# ===========================================================================
# E. get_unique_val_game_ids
# ===========================================================================

class TestGetUniqueValGameIds:
    def test_returns_sorted_list(self):
        combined = _make_combined_df(n_games=10)
        val_df = extract_val_rows(combined, "B3")
        gids = get_unique_val_game_ids(val_df)
        assert gids == sorted(gids)

    def test_no_duplicates(self):
        combined = _make_combined_df(n_games=10)
        val_df = extract_val_rows(combined, "B3")
        gids = get_unique_val_game_ids(val_df)
        assert len(gids) == len(set(gids))

    def test_count_matches_unique_games(self):
        combined = _make_combined_df(n_games=15)
        val_df = extract_val_rows(combined, "B3")
        gids = get_unique_val_game_ids(val_df)
        assert len(gids) == 15


# ===========================================================================
# F. compute_point_log_loss
# ===========================================================================

class TestComputePointLogLoss:
    def test_returns_float(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        result = compute_point_log_loss(val_df)
        assert isinstance(result, float)

    def test_positive(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        assert compute_point_log_loss(val_df) > 0.0

    def test_finite(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        assert math.isfinite(compute_point_log_loss(val_df))


# ===========================================================================
# G. build_game_row_index
# ===========================================================================

class TestBuildGameRowIndex:
    def test_returns_dict(self):
        combined = _make_combined_df(n_games=10)
        val_df = extract_val_rows(combined, "B3")
        idx = build_game_row_index(val_df)
        assert isinstance(idx, dict)

    def test_all_rows_covered(self):
        combined = _make_combined_df(n_games=10)
        val_df = extract_val_rows(combined, "B3")
        idx = build_game_row_index(val_df)
        all_indices = sorted(i for indices in idx.values() for i in indices)
        assert all_indices == list(range(len(val_df)))

    def test_each_game_has_correct_count(self):
        combined = _make_combined_df(n_games=10)
        val_df = extract_val_rows(combined, "B3")
        idx = build_game_row_index(val_df)
        for gid, indices in idx.items():
            expected = (val_df["game_id"] == gid).sum()
            assert len(indices) == expected


# ===========================================================================
# H. run_bootstrap
# ===========================================================================

class TestRunBootstrap:
    def test_returns_array(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        result = run_bootstrap(val_df, n_replicates=50, seed=42)
        assert isinstance(result, np.ndarray)

    def test_correct_length(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        result = run_bootstrap(val_df, n_replicates=50, seed=42)
        assert len(result) == 50

    def test_deterministic(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        r1 = run_bootstrap(val_df, n_replicates=20, seed=99)
        r2 = run_bootstrap(val_df, n_replicates=20, seed=99)
        np.testing.assert_array_equal(r1, r2)

    def test_values_are_positive(self):
        combined = _make_combined_df(n_games=20)
        val_df = extract_val_rows(combined, "B3")
        result = run_bootstrap(val_df, n_replicates=30, seed=42)
        valid = result[~np.isnan(result)]
        assert np.all(valid > 0.0)


# ===========================================================================
# I. compute_ci_from_bootstrap
# ===========================================================================

class TestComputeCiFromBootstrap:
    def test_returns_dict(self):
        values = np.random.default_rng(0).normal(1.0, 0.1, 100)
        result = compute_ci_from_bootstrap(values)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        values = np.random.default_rng(0).normal(1.0, 0.1, 100)
        result = compute_ci_from_bootstrap(values)
        for key in ["mean", "std", "ci_lower", "ci_upper", "n_replicates", "n_nan"]:
            assert key in result, f"missing key: {key}"

    def test_ci_lower_le_upper(self):
        values = np.random.default_rng(0).normal(1.0, 0.1, 100)
        result = compute_ci_from_bootstrap(values)
        assert result["ci_lower"] <= result["ci_upper"]

    def test_n_replicates_correct(self):
        values = np.array([1.0, 2.0, 3.0, 4.0])
        result = compute_ci_from_bootstrap(values)
        assert result["n_replicates"] == 4

    def test_n_nan_counted(self):
        values = np.array([1.0, float("nan"), 2.0, float("nan")])
        result = compute_ci_from_bootstrap(values)
        assert result["n_nan"] == 2

    def test_all_nan_returns_nan_ci(self):
        values = np.array([float("nan"), float("nan")])
        result = compute_ci_from_bootstrap(values)
        assert math.isnan(result["ci_lower"])
        assert math.isnan(result["ci_upper"])


# ===========================================================================
# J. run_bootstrap_for_model
# ===========================================================================

class TestRunBootstrapForModel:
    def test_returns_dict(self):
        combined = _make_combined_df(n_games=20)
        result = run_bootstrap_for_model(combined, "B3", n_replicates=50, seed=42)
        assert isinstance(result, dict)

    def test_has_model_id(self):
        combined = _make_combined_df(n_games=20)
        result = run_bootstrap_for_model(combined, "B3", n_replicates=50, seed=42)
        assert result["model_id"] == "B3"

    def test_has_point_log_loss(self):
        combined = _make_combined_df(n_games=20)
        result = run_bootstrap_for_model(combined, "B3", n_replicates=50, seed=42)
        assert math.isfinite(result["point_log_loss"])

    def test_has_ci_bounds(self):
        combined = _make_combined_df(n_games=20)
        result = run_bootstrap_for_model(combined, "B3", n_replicates=50, seed=42)
        assert result["ci_lower"] <= result["ci_upper"]

    def test_n_val_games_correct(self):
        combined = _make_combined_df(n_games=15)
        result = run_bootstrap_for_model(combined, "B3", n_replicates=20, seed=42)
        assert result["n_val_games"] == 15


# ===========================================================================
# K. run_all_bootstrap
# ===========================================================================

class TestRunAllBootstrap:
    def test_returns_dict(self):
        combined = _make_combined_df(n_games=20)
        result = run_all_bootstrap(combined, n_replicates=30, seed=42)
        assert isinstance(result, dict)

    def test_skips_missing_models(self):
        combined = _make_combined_df(n_games=20)
        result = run_all_bootstrap(combined, n_replicates=30, seed=42)
        # G2b not in combined, should not appear in result
        assert "G2b" not in result

    def test_includes_b2(self):
        combined = _make_combined_df(n_games=20)
        result = run_all_bootstrap(combined, n_replicates=30, seed=42)
        assert "B2" in result

    def test_includes_present_models(self):
        combined = _make_combined_df(n_games=20)
        result = run_all_bootstrap(combined, n_replicates=30, seed=42)
        for mid in ["B1", "B2", "B3", "G2"]:
            assert mid in result

    def test_model_ids_filter(self):
        combined = _make_combined_df(n_games=20)
        result = run_all_bootstrap(combined, model_ids=["B3"], n_replicates=20, seed=42)
        assert list(result.keys()) == ["B3"]

    def test_b2_in_bootstrap_model_ids(self):
        assert "B2" in _BOOTSTRAP_MODEL_IDS


# ===========================================================================
# L. build_bootstrap_payload
# ===========================================================================

class TestBuildBootstrapPayload:
    def test_returns_dict(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, model_ids=["B3"], n_replicates=10, seed=42)
        result = build_bootstrap_payload("ds_id", "v1", br, 10, 42)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, model_ids=["B3"], n_replicates=10, seed=42)
        result = build_bootstrap_payload("ds_id", "v1", br, 10, 42)
        for key in ["dataset_id", "version_tag", "created_at_utc",
                    "n_replicates", "seed", "bootstrap_results"]:
            assert key in result

    def test_dataset_id_preserved(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, model_ids=["B3"], n_replicates=10, seed=42)
        result = build_bootstrap_payload("my_dataset", "v1", br, 10, 42)
        assert result["dataset_id"] == "my_dataset"

    def test_pairwise_results_included_when_provided(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, model_ids=["B2", "B3"], n_replicates=10, seed=42)
        pw = run_all_pairwise_deltas(combined, br, n_replicates=10, seed=42)
        result = build_bootstrap_payload("ds_id", "v1", br, 10, 42, pairwise_results=pw)
        assert "pairwise_results" in result


# ===========================================================================
# R. run_paired_delta_bootstrap
# ===========================================================================

class TestRunPairedDeltaBootstrap:
    def test_returns_array(self):
        combined = _make_combined_df(n_games=20)
        deltas = run_paired_delta_bootstrap(combined, "B2", "B3", n_replicates=50, seed=42)
        assert isinstance(deltas, np.ndarray)

    def test_correct_length(self):
        combined = _make_combined_df(n_games=20)
        deltas = run_paired_delta_bootstrap(combined, "B2", "B3", n_replicates=50, seed=42)
        assert len(deltas) == 50

    def test_deterministic(self):
        combined = _make_combined_df(n_games=20)
        d1 = run_paired_delta_bootstrap(combined, "B2", "B3", n_replicates=30, seed=7)
        d2 = run_paired_delta_bootstrap(combined, "B2", "B3", n_replicates=30, seed=7)
        np.testing.assert_array_equal(d1, d2)

    def test_delta_sign_convention(self):
        # delta = LL(B) - LL(A); negative means B improved
        combined = _make_combined_df(n_games=20)
        deltas = run_paired_delta_bootstrap(combined, "B2", "B3", n_replicates=20, seed=42)
        # Just verify it can be negative or positive — sign is data-dependent
        valid = deltas[~np.isnan(deltas)]
        assert len(valid) > 0

    def test_no_common_game_ids_returns_nan_array(self):
        # If models have disjoint game_ids, common_game_ids is empty → all NaN
        combined = _make_combined_df(n_games=20)
        val_b3 = extract_val_rows(combined, "B3")
        # Create a G2 variant with totally different game_ids
        rng = np.random.default_rng(0)
        n = len(val_b3)
        raw = rng.dirichlet([2.0, 1.0, 2.0], size=n)
        g2_diff = pl.DataFrame({
            "model_id": ["G2"] * n,
            "split_set": ["val"] * n,
            "game_id": [f"other_{i}" for i in range(n)],
            "result_class": val_b3["result_class"].to_list(),
            "p_BLACK_WIN": raw[:, 0].tolist(),
            "p_DRAW": raw[:, 1].tolist(),
            "p_WHITE_WIN": raw[:, 2].tolist(),
        })
        combined_diff = pl.concat([
            extract_val_rows(combined, "B3"),
            g2_diff,
        ])
        deltas = run_paired_delta_bootstrap(
            combined_diff, "B3", "G2", n_replicates=10, seed=42
        )
        assert np.all(np.isnan(deltas))


# ===========================================================================
# S. compute_delta_ci
# ===========================================================================

class TestComputeDeltaCi:
    def _run(self, model_a: str = "B2", model_b: str = "B3", n: int = 50):
        combined = _make_combined_df(n_games=20)
        deltas = run_paired_delta_bootstrap(combined, model_a, model_b,
                                            n_replicates=n, seed=42)
        return compute_delta_ci(deltas, model_a, model_b, combined), combined

    def test_returns_dict(self):
        result, _ = self._run()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result, _ = self._run()
        for key in ["model_a", "model_b", "point_delta", "ci_lower", "ci_upper",
                    "contains_zero", "n_replicates", "n_nan", "n_common_games"]:
            assert key in result, f"missing key: {key}"

    def test_model_ids_stored(self):
        result, _ = self._run("B2", "B3")
        assert result["model_a"] == "B2"
        assert result["model_b"] == "B3"

    def test_contains_zero_is_bool(self):
        result, _ = self._run()
        assert isinstance(result["contains_zero"], bool)

    def test_contains_zero_correct_when_ci_straddles_zero(self):
        # Force a CI that straddles zero by using symmetric noise
        deltas = np.linspace(-0.5, 0.5, 100)
        combined = _make_combined_df(n_games=20)
        result = compute_delta_ci(deltas, "B2", "B3", combined)
        assert result["contains_zero"] is True

    def test_contains_zero_false_when_ci_entirely_negative(self):
        # All deltas negative = B always improved
        deltas = np.full(100, -0.5)
        combined = _make_combined_df(n_games=20)
        result = compute_delta_ci(deltas, "B2", "B3", combined)
        assert result["contains_zero"] is False
        assert result["ci_upper"] < 0.0

    def test_point_delta_is_float(self):
        result, _ = self._run()
        assert isinstance(result["point_delta"], float)

    def test_n_common_games_positive(self):
        result, _ = self._run()
        assert result["n_common_games"] > 0


# ===========================================================================
# T. run_all_pairwise_deltas
# ===========================================================================

class TestRunAllPairedDeltas:
    def test_returns_dict(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert isinstance(result, dict)

    def test_b1_b2_pair_present(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert "B1_vs_B2" in result

    def test_b2_b3_pair_present(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert "B2_vs_B3" in result

    def test_b3_g2_pair_present(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert "B3_vs_G2" in result

    def test_b3_g2b_absent_when_g2b_not_in_results(self):
        combined = _make_combined_df(n_games=20, include_g2b=False)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert "B3_vs_G2b" not in result

    def test_b3_g2b_present_when_g2b_in_results(self):
        combined = _make_combined_df(n_games=20, include_g2b=True)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        assert "B3_vs_G2b" in result

    def test_each_result_has_contains_zero(self):
        combined = _make_combined_df(n_games=20)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        result = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        for key, val in result.items():
            assert "contains_zero" in val, f"{key} missing contains_zero"

    def test_pairwise_comparisons_list_contains_b1_b2(self):
        assert ("B1", "B2") in _PAIRWISE_COMPARISONS

    def test_pairwise_comparisons_list_contains_b2_b3(self):
        assert ("B2", "B3") in _PAIRWISE_COMPARISONS


# ===========================================================================
# P. render_bootstrap_report — report content checks
# ===========================================================================

class TestRenderBootstrapReport:
    def _make_payload(self, include_g2b: bool = False, n: int = 20):
        combined = _make_combined_df(n_games=n, include_g2b=include_g2b)
        br = run_all_bootstrap(combined, n_replicates=20, seed=42)
        pw = run_all_pairwise_deltas(combined, br, n_replicates=20, seed=42)
        return build_bootstrap_payload("test_ds", "v1", br, 20, 42,
                                       pairwise_results=pw)

    def test_returns_string(self):
        payload = self._make_payload()
        assert isinstance(render_bootstrap_report(payload), str)

    def test_no_dynamic_timestamp_in_report(self):
        # Report must not contain "Generated:" (timestamp causes non-determinism)
        payload = self._make_payload()
        report = render_bootstrap_report(payload)
        assert "Generated:" not in report

    def test_b2_b3_delta_in_report(self):
        payload = self._make_payload()
        report = render_bootstrap_report(payload)
        assert "B2" in report and "B3" in report

    def test_contains_zero_appears_in_report(self):
        payload = self._make_payload()
        report = render_bootstrap_report(payload)
        assert "contains_zero" in report or "contains zero" in report.lower()

    def test_no_nonoverlappping_claim_for_g2_g2b(self):
        # Must not claim G2 and G2b CIs are non-overlapping
        payload = self._make_payload(include_g2b=True)
        report = render_bootstrap_report(payload)
        assert "non-overlapping" not in report.lower()

    def test_g2b_comparison_section_present_when_g2b_in_results(self):
        payload = self._make_payload(include_g2b=True)
        report = render_bootstrap_report(payload)
        assert "G2b" in report

    def test_b2_row_in_per_model_table(self):
        payload = self._make_payload()
        report = render_bootstrap_report(payload)
        # B2 should appear in the per-model CI table
        lines = report.split("\n")
        table_lines = [l for l in lines if "| B2 " in l or "| B2|" in l]
        assert len(table_lines) >= 1

    def test_deterministic_output(self):
        # Same payload should produce identical report string
        payload = self._make_payload()
        r1 = render_bootstrap_report(payload)
        r2 = render_bootstrap_report(payload)
        assert r1 == r2

    def test_no_malformed_blockquote(self):
        # Original bug: "> are wide" appearing as broken continuation
        payload = self._make_payload()
        report = render_bootstrap_report(payload)
        lines = report.split("\n")
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(">"):
                # A valid blockquote line should have content, not just "> "
                content = stripped[1:].strip()
                assert len(content) > 0, f"Empty blockquote line: {line!r}"
