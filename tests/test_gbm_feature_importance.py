"""
tests/test_gbm_feature_importance.py — Tests for gbm_feature_importance.py (Phase 6.3B).

Synthetic fixtures only. No real data/ files loaded.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from chess_mhsuc.gbm_feature_importance import (
    classify_importance_signal,
    compute_permutation_importance_table,
    compute_validation_log_loss,
    get_gbm_models,
    get_model_by_id,
    load_gbm_results,
    load_modeling_plan,
    load_splits,
    main,
    prepare_g2_train_val_data,
    render_ablation_table,
    render_gbm_feature_importance_report,
    render_permutation_table,
    retrain_g2_in_memory,
    write_text,
)

# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------


def _make_metrics(ll_train: float = 0.50, ll_val: float = 0.80) -> dict:
    per_class = {
        "BLACK_WIN": {"recall": 0.50, "precision": 0.60, "f1": 0.55, "support": 50},
        "DRAW":      {"recall": 0.00, "precision": None, "f1": 0.00, "support": 5},
        "WHITE_WIN": {"recall": 0.60, "precision": 0.50, "f1": 0.55, "support": 50},
    }
    return {
        "train": {"log_loss": ll_train, "accuracy": 0.70, "multiclass_brier": 0.30,
                  "macro_f1": 0.40, "per_class": per_class},
        "val":   {"log_loss": ll_val,   "accuracy": 0.55, "multiclass_brier": 0.50,
                  "macro_f1": 0.37, "per_class": per_class},
        "test":  {"log_loss": ll_val + 0.02, "accuracy": 0.53,
                  "multiclass_brier": 0.51, "macro_f1": 0.36, "per_class": per_class},
    }


def _make_gbm_model(model_id: str, fs: str = "FS-E", table: str = "broad",
                    exploratory: bool = False, diagnostic: bool = False,
                    ll_train: float = 0.50, ll_val: float = 0.80) -> dict:
    return {
        "model_id": model_id,
        "feature_set_id": fs,
        "table": table,
        "exploratory": exploratory,
        "diagnostic": diagnostic,
        "n_train_rows": 100,
        "n_features_used": 4,
        "feature_columns_dropped": [],
        "metrics": _make_metrics(ll_train=ll_train, ll_val=ll_val),
    }


def _make_gbm_payload() -> dict:
    return {
        "gbm_models": {
            "G1": _make_gbm_model("G1", "FS-B", "broad", False, False, 0.20, 1.42),
            "G2": _make_gbm_model("G2", "FS-E", "broad", False, False, 0.164, 1.2326),
            "G3": _make_gbm_model("G3", "FS-C", "broad", False, True, 0.55, 0.99),
            "G4": _make_gbm_model("G4", "FS-D", "broad", False, True, 0.88, 0.881),
        },
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "dataset_id": "lichess_ten_zero_2024_09_25k_v1",
        "version_tag": "2024_09_25k_v1",
        "created_at_utc": "2026-06-08T10:00:00Z",
    }


def _make_splits_payload() -> dict:
    """Synthetic splits: 30 train games, 10 val games, 10 test games."""
    assignments = {}
    for i in range(30):
        assignments[f"game_train_{i}"] = "train"
    for i in range(10):
        assignments[f"game_val_{i}"] = "val"
    for i in range(10):
        assignments[f"game_test_{i}"] = "test"
    return {
        "version_tag": "2024_09_25k_v1",
        "split_unit": "game_id",
        "seed": 42,
        "train_frac": 0.70,
        "val_frac": 0.15,
        "test_frac": 0.15,
        "stratify_col": "result_class",
        "assignments": assignments,
    }


def _make_modeling_plan() -> dict:
    """Minimal modeling plan with FS-E defined."""
    return {
        "dataset_id": "lichess_ten_zero_2024_09_25k_v1",
        "version_tag": "2024_09_25k_v1",
        "feature_sets": {
            "FS-E": {
                "features": [
                    "white_elo", "black_elo", "elo_diff", "avg_elo",
                    "white_clock_s_capped", "black_clock_s_capped",
                    "clock_diff_s", "white_clock_frac", "black_clock_frac",
                    "clock_diff_frac", "white_low_60", "black_low_60",
                    "white_low_30", "black_low_30", "white_low_10",
                    "black_low_10", "clock_anomaly", "selected_position_type",
                    "move_number", "phase", "checkpoint_index", "phase_index",
                ],
                "table": "broad",
            },
        },
    }


def _make_feature_broad_df(n_train: int = 30, n_val: int = 10,
                            n_test: int = 10) -> pl.DataFrame:
    """Synthetic feature DataFrame with all G2 columns + meta columns."""
    rng = np.random.default_rng(42)
    n = n_train + n_val + n_test
    game_ids = (
        [f"game_train_{i}" for i in range(n_train)] +
        [f"game_val_{i}" for i in range(n_val)] +
        [f"game_test_{i}" for i in range(n_test)]
    )
    # result_class: balanced synthetic labels
    result_classes = (
        ["BLACK_WIN", "WHITE_WIN", "WHITE_WIN", "BLACK_WIN", "WHITE_WIN",
         "DRAW", "BLACK_WIN", "WHITE_WIN", "BLACK_WIN", "BLACK_WIN"] * 5
    )[:n]
    return pl.DataFrame({
        "game_id":                game_ids,
        "result_class":           result_classes,
        "selected_position_type": ["numbered"] * n,
        "white_elo":              rng.integers(1200, 2000, n).tolist(),
        "black_elo":              rng.integers(1200, 2000, n).tolist(),
        "elo_diff":               rng.integers(-200, 200, n).tolist(),
        "avg_elo":                rng.integers(1200, 2000, n).tolist(),
        "white_clock_s_capped":   rng.uniform(0, 600, n).tolist(),
        "black_clock_s_capped":   rng.uniform(0, 600, n).tolist(),
        "clock_diff_s":           rng.uniform(-100, 100, n).tolist(),
        "white_clock_frac":       rng.uniform(0, 1, n).tolist(),
        "black_clock_frac":       rng.uniform(0, 1, n).tolist(),
        "clock_diff_frac":        rng.uniform(-0.5, 0.5, n).tolist(),
        "white_low_60":           [False] * n,
        "black_low_60":           [False] * n,
        "white_low_30":           [False] * n,
        "black_low_30":           [False] * n,
        "white_low_10":           [False] * n,
        "black_low_10":           [False] * n,
        "clock_anomaly":          [False] * n,
        "move_number":            ([10, 20, 30, 40, 10, 20, 30, 40, 10, 20] * (n // 10 + 1))[:n],
        "phase":                  (["opening", "middlegame", "endgame"] * (n // 3 + 1))[:n],
        "checkpoint_index":       rng.integers(0, 4, n).tolist(),
        "phase_index":            ([0, 1, 2] * (n // 3 + 1))[:n],
    })


def _make_importance_rows() -> list[dict]:
    return [
        {"feature": "white_elo",   "delta_log_loss": +0.0289, "std": 0.013,
         "signal": "positive diagnostic signal"},
        {"feature": "avg_elo",     "delta_log_loss": +0.0287, "std": 0.016,
         "signal": "positive diagnostic signal"},
        {"feature": "move_number", "delta_log_loss": -0.0072, "std": 0.004,
         "signal": "negative overfit artifact"},
        {"feature": "clock_diff_s","delta_log_loss": -0.0578, "std": 0.014,
         "signal": "negative overfit artifact"},
        {"feature": "phase_index", "delta_log_loss": +0.0001, "std": 0.0001,
         "signal": "near-zero / unstable"},
    ]


# File-writing helpers
def _write_gbm_json(path: Path) -> Path:
    path.write_text(json.dumps(_make_gbm_payload()), encoding="utf-8")
    return path


def _write_splits_json(path: Path) -> Path:
    path.write_text(json.dumps(_make_splits_payload()), encoding="utf-8")
    return path


def _write_modeling_plan_json(path: Path) -> Path:
    path.write_text(json.dumps(_make_modeling_plan()), encoding="utf-8")
    return path


def _write_feature_broad_parquet(path: Path) -> Path:
    _make_feature_broad_df().write_parquet(path)
    return path


# ===========================================================================
# A. load_gbm_results
# ===========================================================================

class TestLoadGbmResults:
    def test_loads_from_file(self, tmp_path):
        p = _write_gbm_json(tmp_path / "gbm.json")
        payload = load_gbm_results(p)
        assert isinstance(payload, dict)
        assert "gbm_models" in payload

    def test_accepts_gbm_models_as_list(self, tmp_path):
        data = _make_gbm_payload()
        data["gbm_models"] = list(data["gbm_models"].values())
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        payload = load_gbm_results(p)
        assert isinstance(payload["gbm_models"], list)

    def test_missing_gbm_models_raises(self, tmp_path):
        data = _make_gbm_payload()
        del data["gbm_models"]
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="gbm_models"):
            load_gbm_results(p)

    def test_missing_class_order_raises(self, tmp_path):
        data = _make_gbm_payload()
        del data["class_order"]
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="class_order"):
            load_gbm_results(p)

    def test_wrong_type_for_gbm_models_raises(self, tmp_path):
        data = _make_gbm_payload()
        data["gbm_models"] = "not-a-dict-or-list"
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="gbm_models"):
            load_gbm_results(p)


# ===========================================================================
# C. load_splits
# ===========================================================================

class TestLoadSplits:
    def test_loads_from_file(self, tmp_path):
        p = _write_splits_json(tmp_path / "splits.json")
        payload = load_splits(p)
        assert "assignments" in payload

    def test_missing_assignments_raises(self, tmp_path):
        data = {"version_tag": "x", "seed": 42}
        p = tmp_path / "splits.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="assignments"):
            load_splits(p)

    def test_empty_assignments_raises(self, tmp_path):
        data = _make_splits_payload()
        data["assignments"] = {}
        p = tmp_path / "splits.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_splits(p)


# ===========================================================================
# D. load_modeling_plan
# ===========================================================================

class TestLoadModelingPlan:
    def test_loads_from_file(self, tmp_path):
        p = _write_modeling_plan_json(tmp_path / "plan.json")
        payload = load_modeling_plan(p)
        assert "feature_sets" in payload

    def test_missing_feature_sets_raises(self, tmp_path):
        data = {"version_tag": "x"}
        p = tmp_path / "plan.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="feature_sets"):
            load_modeling_plan(p)


# ===========================================================================
# E/F. get_gbm_models / get_model_by_id
# ===========================================================================

class TestGetGbmModels:
    def test_from_dict_returns_sorted_list(self):
        payload = _make_gbm_payload()
        models = get_gbm_models(payload)
        ids = [m["model_id"] for m in models]
        assert ids == sorted(ids)

    def test_from_list_returns_sorted_list(self):
        payload = _make_gbm_payload()
        payload["gbm_models"] = list(payload["gbm_models"].values())
        models = get_gbm_models(payload)
        assert len(models) == 4

    def test_get_model_by_id_returns_g2(self):
        payload = _make_gbm_payload()
        m = get_model_by_id(payload, "G2")
        assert m["model_id"] == "G2"

    def test_get_model_by_id_missing_raises(self):
        payload = _make_gbm_payload()
        with pytest.raises(KeyError):
            get_model_by_id(payload, "NONEXISTENT")


# ===========================================================================
# K. classify_importance_signal
# ===========================================================================

class TestClassifyImportanceSignal:
    def test_positive_above_threshold(self):
        assert classify_importance_signal(0.01) == "positive diagnostic signal"

    def test_negative_below_threshold(self):
        assert classify_importance_signal(-0.01) == "negative overfit artifact"

    def test_near_zero_within_thresholds(self):
        assert classify_importance_signal(0.0) == "near-zero / unstable"
        assert classify_importance_signal(0.004) == "near-zero / unstable"
        assert classify_importance_signal(-0.004) == "near-zero / unstable"

    def test_boundary_values(self):
        assert classify_importance_signal(0.005) == "near-zero / unstable"
        assert classify_importance_signal(-0.005) == "near-zero / unstable"
        assert classify_importance_signal(0.0051) == "positive diagnostic signal"
        assert classify_importance_signal(-0.0051) == "negative overfit artifact"


# ===========================================================================
# G. prepare_g2_train_val_data (synthetic data)
# ===========================================================================

class TestPrepareG2TrainValData:
    def test_returns_five_tuple(self):
        result = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        assert len(result) == 5

    def test_feature_names_excludes_string_categoricals(self):
        _, _, _, _, feature_names = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        assert "selected_position_type" not in feature_names
        assert "phase" not in feature_names

    def test_feature_names_are_list(self):
        _, _, _, _, feature_names = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        assert isinstance(feature_names, list)
        assert len(feature_names) > 0

    def test_train_val_sizes(self):
        X_train, y_train, X_val, y_val, _ = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        assert len(X_train) == 30
        assert len(y_train) == 30
        assert len(X_val) == 10
        assert len(y_val) == 10


# ===========================================================================
# H/I. retrain_g2_in_memory / compute_validation_log_loss (synthetic)
# ===========================================================================

class TestRetrainAndValidate:
    def test_retrain_returns_fitted_model(self):
        X_train, y_train, _, _, _ = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        model = retrain_g2_in_memory(X_train, y_train)
        assert isinstance(model, HistGradientBoostingClassifier)
        assert hasattr(model, "classes_")  # fitted attribute

    def test_compute_validation_log_loss_returns_float(self):
        X_train, y_train, X_val, y_val, _ = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        model = retrain_g2_in_memory(X_train, y_train)
        val_ll = compute_validation_log_loss(model, X_val, y_val)
        assert isinstance(val_ll, float)
        assert val_ll > 0


# ===========================================================================
# J. compute_permutation_importance_table (synthetic)
# ===========================================================================

class TestComputePermutationImportanceTable:
    def _fit_model_and_data(self):
        X_train, y_train, X_val, y_val, feature_names = prepare_g2_train_val_data(
            _make_feature_broad_df(),
            _make_splits_payload(),
            _make_modeling_plan(),
            _make_gbm_payload(),
        )
        model = retrain_g2_in_memory(X_train, y_train)
        return model, X_val, y_val, feature_names

    def test_returns_list(self):
        model, X_val, y_val, feature_names = self._fit_model_and_data()
        rows = compute_permutation_importance_table(model, X_val, y_val, feature_names)
        assert isinstance(rows, list)

    def test_rows_have_required_keys(self):
        model, X_val, y_val, feature_names = self._fit_model_and_data()
        rows = compute_permutation_importance_table(model, X_val, y_val, feature_names)
        for r in rows:
            assert "feature" in r
            assert "delta_log_loss" in r
            assert "std" in r
            assert "signal" in r

    def test_rows_count_matches_feature_count(self):
        model, X_val, y_val, feature_names = self._fit_model_and_data()
        rows = compute_permutation_importance_table(model, X_val, y_val, feature_names)
        assert len(rows) == len(feature_names)

    def test_rows_sorted_descending_by_delta(self):
        model, X_val, y_val, feature_names = self._fit_model_and_data()
        rows = compute_permutation_importance_table(model, X_val, y_val, feature_names)
        deltas = [r["delta_log_loss"] for r in rows]
        assert deltas == sorted(deltas, reverse=True)

    def test_signal_values_are_valid_categories(self):
        model, X_val, y_val, feature_names = self._fit_model_and_data()
        rows = compute_permutation_importance_table(model, X_val, y_val, feature_names)
        valid = {"positive diagnostic signal", "near-zero / unstable", "negative overfit artifact"}
        for r in rows:
            assert r["signal"] in valid


# ===========================================================================
# L/M. render_ablation_table / render_permutation_table
# ===========================================================================

class TestRenderTables:
    def test_ablation_table_contains_all_models(self):
        table = render_ablation_table(_make_gbm_payload())
        for mid in ["G1", "G2", "G3", "G4"]:
            assert mid in table

    def test_ablation_table_marks_g4_near_prior(self):
        table = render_ablation_table(_make_gbm_payload())
        assert "near-prior" in table.lower()

    def test_permutation_table_contains_all_features(self):
        rows = _make_importance_rows()
        table = render_permutation_table(rows)
        for r in rows:
            assert r["feature"] in table

    def test_permutation_table_sorted_descending(self):
        rows = _make_importance_rows()
        table = render_permutation_table(rows)
        # white_elo (+0.0289) should appear before clock_diff_s (-0.0578)
        assert table.index("white_elo") < table.index("clock_diff_s")

    def test_permutation_table_positive_sign_shown(self):
        rows = _make_importance_rows()
        table = render_permutation_table(rows)
        assert "+0.0289" in table or "+0.029" in table


# ===========================================================================
# N. render_gbm_feature_importance_report — content checks
# ===========================================================================

class TestRenderReport:
    def _report(self):
        return render_gbm_feature_importance_report(
            gbm_payload=_make_gbm_payload(),
            importance_rows=_make_importance_rows(),
            val_log_loss_check=1.2326,
            dataset_id="lichess_ten_zero_2024_09_25k_v1",
            version_tag="2024_09_25k_v1",
        )

    def test_report_is_string(self):
        assert isinstance(self._report(), str)

    def test_report_title(self):
        assert "GBM Feature Importance Diagnostic Report" in self._report()

    def test_report_ticket_and_labels(self):
        report = self._report()
        assert "6.3B" in report
        assert "ML/ANALYSIS" in report
        assert "D2" in report
        assert "IMPLEMENTATION" in report

    def test_report_research_framing(self):
        report = self._report()
        assert "Chess is the testbed" in report
        assert "human strategy/reasoning" in report

    def test_report_diagnostic_only(self):
        assert "diagnostic-only" in self._report() or "diagnostic only" in self._report()

    def test_report_overfit_mentioned(self):
        assert "overfit" in self._report()

    def test_report_not_causal(self):
        report = self._report()
        assert "not causal" in report.lower() or "not a causal" in report.lower()

    def test_report_validation_split_only(self):
        report = self._report()
        assert "validation split only" in report.lower() or "validation split" in report.lower()

    def test_report_negative_importance_explained(self):
        report = self._report()
        assert "negative importance" in report.lower()
        assert "overfit artifact" in report.lower()

    def test_report_no_model_artifact_saved(self):
        report = self._report()
        assert "no fitted model object was saved" in report.lower()

    def test_report_contains_white_elo(self):
        assert "white_elo" in self._report()

    def test_report_contains_avg_elo(self):
        assert "avg_elo" in self._report()

    def test_report_contains_clock_diff_s(self):
        assert "clock_diff_s" in self._report()

    def test_report_all_12_sections(self):
        report = self._report()
        for i in range(1, 13):
            assert f"## {i}." in report

    def test_report_no_final_feature_ranking_claim(self):
        report = self._report()
        # may say "not a final ranking" — but not "final feature ranking" as a positive claim
        assert "final feature ranking" not in report or "not" in report[
            max(0, report.find("final feature ranking") - 20):
            report.find("final feature ranking")
        ].lower()

    def test_report_no_causal_positive_claim(self):
        report = self._report()
        # The report should not positively assert "causal" without negation
        # Permitted: "not causal", "no causal claim", "not a causal explanation"
        import re
        causal_mentions = [m.start() for m in re.finditer(r"\bcausal\b", report)]
        for pos in causal_mentions:
            context = report[max(0, pos - 30):pos + 30]
            assert "not" in context.lower() or "no " in context.lower(), (
                f"Found 'causal' without negation at: {context!r}"
            )

    def test_report_does_not_say_clock_does_not_matter(self):
        report = self._report()
        assert "clock does not matter" not in report.lower()

    def test_report_does_not_say_gbm_learned_strategy(self):
        report = self._report()
        assert "gbm learned human strategy" not in report.lower()

    def test_report_no_feature_importance_proves(self):
        report = self._report()
        assert "feature importance proves" not in report.lower()


# ===========================================================================
# O. write_text
# ===========================================================================

class TestWriteText:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "hello")
        assert p.exists()

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "out.md"
        write_text(p, "hello")
        assert p.exists()

    def test_adds_trailing_newline(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "no newline")
        assert p.read_text(encoding="utf-8").endswith("\n")


# ===========================================================================
# P. main / CLI
# ===========================================================================

class TestMain:
    def test_missing_required_args_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--dataset-id", "x"])  # missing most required args
        assert exc_info.value.code != 0

    def test_round_trip(self, tmp_path):
        gbm_json = _write_gbm_json(tmp_path / "gbm.json")
        splits_json = _write_splits_json(tmp_path / "splits.json")
        plan_json = _write_modeling_plan_json(tmp_path / "plan.json")
        feat_parquet = _write_feature_broad_parquet(tmp_path / "feat.parquet")
        out = tmp_path / "report.md"

        rc = main([
            "--dataset-id", "lichess_ten_zero_2024_09_25k_v1",
            "--version-tag", "2024_09_25k_v1",
            "--gbm-results", str(gbm_json),
            "--feature-broad", str(feat_parquet),
            "--splits", str(splits_json),
            "--modeling-plan", str(plan_json),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "GBM Feature Importance Diagnostic Report" in content

    def test_cli_output_contains_required_labels(self, tmp_path):
        gbm_json = _write_gbm_json(tmp_path / "gbm.json")
        splits_json = _write_splits_json(tmp_path / "splits.json")
        plan_json = _write_modeling_plan_json(tmp_path / "plan.json")
        feat_parquet = _write_feature_broad_parquet(tmp_path / "feat.parquet")
        out = tmp_path / "report.md"

        main([
            "--dataset-id", "lichess_ten_zero_2024_09_25k_v1",
            "--version-tag", "2024_09_25k_v1",
            "--gbm-results", str(gbm_json),
            "--feature-broad", str(feat_parquet),
            "--splits", str(splits_json),
            "--modeling-plan", str(plan_json),
            "--output", str(out),
        ])
        content = out.read_text(encoding="utf-8")
        assert "6.3B" in content
        assert "ML/ANALYSIS" in content

    def test_cli_does_not_create_model_artifacts(self, tmp_path):
        gbm_json = _write_gbm_json(tmp_path / "gbm.json")
        splits_json = _write_splits_json(tmp_path / "splits.json")
        plan_json = _write_modeling_plan_json(tmp_path / "plan.json")
        feat_parquet = _write_feature_broad_parquet(tmp_path / "feat.parquet")
        out = tmp_path / "report.md"

        main([
            "--dataset-id", "lichess_ten_zero_2024_09_25k_v1",
            "--version-tag", "2024_09_25k_v1",
            "--gbm-results", str(gbm_json),
            "--feature-broad", str(feat_parquet),
            "--splits", str(splits_json),
            "--modeling-plan", str(plan_json),
            "--output", str(out),
        ])
        # No .joblib or .pkl files should exist in tmp_path
        artifacts = list(tmp_path.rglob("*.joblib")) + list(tmp_path.rglob("*.pkl"))
        assert artifacts == [], f"Unexpected model artifacts: {artifacts}"
