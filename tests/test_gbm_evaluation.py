"""
tests/test_gbm_evaluation.py — Tests for src/chess_mhsuc/gbm_evaluation.py (Phase 6.2B).

Synthetic fixtures only. No real data/ files are loaded.
"""
from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.gbm_evaluation import (
    compute_confidence_buckets,
    compute_slice_accuracy,
    filter_broad_diagnostic_gbms,
    filter_broad_primary_gbms,
    filter_eval_exploratory_gbms,
    format_float,
    get_baseline_models,
    get_gbm_models,
    get_per_class_metric,
    get_split_metrics,
    join_avg_elo_slice,
    load_baseline_results,
    load_feature_broad,
    load_gbm_predictions,
    load_gbm_results,
    main,
    render_gbm_evaluation_report,
    write_text,
)

# ---------------------------------------------------------------------------
# Synthetic fixture helpers (no real data/ files)
# ---------------------------------------------------------------------------


def _make_metrics(
    ll_train: float = 0.50,
    ll_val: float = 0.80,
    ll_test: float = 0.82,
    acc_val: float = 0.55,
    acc_train: float = 0.70,
    acc_test: float = 0.53,
) -> dict:
    per_class = {
        "BLACK_WIN": {"recall": 0.50, "precision": 0.60, "f1": 0.55, "support": 50},
        "DRAW":      {"recall": 0.00, "precision": None,  "f1": 0.00, "support": 6},
        "WHITE_WIN": {"recall": 0.60, "precision": 0.50, "f1": 0.55, "support": 50},
    }
    return {
        "train": {
            "log_loss": ll_train, "accuracy": acc_train,
            "multiclass_brier": 0.30, "macro_f1": 0.40,
            "per_class": per_class,
        },
        "val": {
            "log_loss": ll_val, "accuracy": acc_val,
            "multiclass_brier": 0.50, "macro_f1": 0.37,
            "per_class": per_class,
        },
        "test": {
            "log_loss": ll_test, "accuracy": acc_test,
            "multiclass_brier": 0.50, "macro_f1": 0.36,
            "per_class": per_class,
        },
    }


def _make_gbm_model(
    model_id: str = "G2",
    feature_set_id: str = "FS-E",
    table: str = "broad",
    exploratory: bool = False,
    diagnostic: bool = False,
    ll_train: float = 0.50,
    ll_val: float = 0.80,
) -> dict:
    return {
        "model_id": model_id,
        "feature_set_id": feature_set_id,
        "table": table,
        "exploratory": exploratory,
        "diagnostic": diagnostic,
        "n_train_rows": 4344,
        "n_features_used": 14,
        "feature_columns_dropped": ["selected_position_type", "phase"],
        "metrics": _make_metrics(ll_train=ll_train, ll_val=ll_val),
    }


def _make_gbm_payload() -> dict:
    """GBM results payload; gbm_models is a dict keyed by model_id."""
    return {
        "gbm_models": {
            "G1": _make_gbm_model("G1", "FS-B", "broad", False, False, 0.20,  1.2000),
            "G2": _make_gbm_model("G2", "FS-E", "broad", False, False, 0.164, 1.2326),
            "G3": _make_gbm_model("G3", "FS-C", "broad", False, True,  0.40,  0.8300),
            "G4": _make_gbm_model("G4", "FS-D", "broad", False, True,  0.85,  0.8810),
            "G5": _make_gbm_model("G5", "FS-F", "eval",  True,  False, 0.30,  1.1854),
            "G6": _make_gbm_model("G6", "FS-G", "eval",  True,  False, 0.004, 1.6410),
        },
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "dataset_id": "lichess_ten_zero_2024_09_25k_v1",
        "version_tag": "2024_09_25k_v1",
        "created_at_utc": "2026-06-07T10:00:00Z",
    }


def _make_baseline_payload() -> dict:
    """Baseline results payload; baselines is a dict keyed by baseline_id."""

    def _base(bid, model_type, strategy=None, fs="FS-A", ll_val=0.88):
        params = {"strategy": strategy} if strategy else {}
        return {
            "baseline_id": bid,
            "model_type": model_type,
            "sklearn_params": params,
            "feature_set_id": fs,
            "table": "broad",
            "exploratory": False,
            "diagnostic": False,
            "metrics": _make_metrics(ll_val=ll_val),
        }

    return {
        "baselines": {
            "B0": _base("B0", "DummyClassifier", "most_frequent", ll_val=18.89),
            "B1": _base("B1", "DummyClassifier", "prior",         ll_val=0.8853),
            "B2": _base("B2", "LogisticRegression", fs="FS-B",    ll_val=0.8740),
            "B3": _base("B3", "LogisticRegression", fs="FS-E",    ll_val=0.8527),
        },
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "dataset_id": "lichess_ten_zero_2024_09_25k_v1",
        "version_tag": "2024_09_25k_v1",
    }


def _make_pred_df() -> pl.DataFrame:
    """
    Synthetic G2 predictions DataFrame with all 19 required columns.
    10 rows × 3 splits (train/val/test). Deterministic probabilities.
    max_prob per row: [0.45, 0.55, 0.65, 0.75, 0.85, 0.50, 0.60, 0.70, 0.80, 0.90]
    """
    p_bw  = [0.45, 0.55, 0.65, 0.75, 0.85, 0.50, 0.60, 0.70, 0.80, 0.90]
    p_d   = [0.10, 0.10, 0.10, 0.10, 0.05, 0.10, 0.10, 0.10, 0.10, 0.05]
    p_ww  = [0.45, 0.35, 0.25, 0.15, 0.10, 0.40, 0.30, 0.20, 0.10, 0.05]
    y_true = [0, 1, 2, 0, 0, 2, 1, 2, 0, 1]
    y_pred = [0, 0, 2, 0, 2, 2, 0, 2, 0, 0]
    phases = [
        "opening", "middlegame", "endgame", "endgame", "opening",
        "middlegame", "endgame", "endgame", "opening", "middlegame",
    ]
    move_nums = [10, 20, 30, 40, 10, 20, 30, 40, 10, 20]
    forfeits  = [False, False, True, False, False, True, False, False, True, False]
    has_evals = [True, False, True, True, False, True, True, False, True, False]
    result_cls = [
        "BLACK_WIN", "DRAW", "WHITE_WIN", "BLACK_WIN", "BLACK_WIN",
        "WHITE_WIN", "DRAW", "WHITE_WIN", "BLACK_WIN", "DRAW",
    ]
    pred_cls = [
        "BLACK_WIN" if p == 0 else ("DRAW" if p == 1 else "WHITE_WIN")
        for p in y_pred
    ]
    game_ids = [f"game_{i}" for i in range(10)]

    rows: list[dict] = []
    for split in ("train", "val", "test"):
        for j in range(10):
            rows.append({
                "model_id": "G2",
                "split_set": split,
                "table": "broad",
                "view": "primary_numbered",
                "exploratory": False,
                "diagnostic": False,
                "game_id": game_ids[j],
                "result_class": result_cls[j],
                "y_true": y_true[j],
                "y_pred": y_pred[j],
                "pred_class": pred_cls[j],
                "p_BLACK_WIN": p_bw[j],
                "p_DRAW": p_d[j],
                "p_WHITE_WIN": p_ww[j],
                "selected_position_type": "numbered",
                "move_number": move_nums[j],
                "phase": phases[j],
                "is_time_forfeit": forfeits[j],
                "has_eval": has_evals[j],
            })
    return pl.DataFrame(rows)


def _make_feature_broad_df() -> pl.DataFrame:
    """Minimal feature broad DF matching game_ids/move_numbers in _make_pred_df."""
    return pl.DataFrame({
        "game_id":     [f"game_{i}" for i in range(10)],
        "move_number": [10, 20, 30, 40, 10, 20, 30, 40, 10, 20],
        "avg_elo":     [1100, 1300, 1500, 1700, 1900, 2100, 1300, 1500, 1700, 1900],
    })


# ---------------------------------------------------------------------------
# File-writing helpers for I/O tests
# ---------------------------------------------------------------------------


def _write_gbm_json(path: Path) -> Path:
    path.write_text(json.dumps(_make_gbm_payload()), encoding="utf-8")
    return path


def _write_baseline_json(path: Path) -> Path:
    path.write_text(json.dumps(_make_baseline_payload()), encoding="utf-8")
    return path


def _write_pred_parquet(path: Path) -> Path:
    _make_pred_df().write_parquet(path)
    return path


def _write_feature_broad_parquet(path: Path) -> Path:
    _make_feature_broad_df().write_parquet(path)
    return path


# ===========================================================================
# A. load_gbm_results
# ===========================================================================


class TestLoadGbmResults:
    def test_load_returns_dict(self, tmp_path):
        p = _write_gbm_json(tmp_path / "gbm.json")
        payload = load_gbm_results(p)
        assert isinstance(payload, dict)

    def test_load_has_required_keys(self, tmp_path):
        p = _write_gbm_json(tmp_path / "gbm.json")
        payload = load_gbm_results(p)
        for key in ("gbm_models", "class_order", "dataset_id", "version_tag"):
            assert key in payload

    def test_load_missing_class_order_raises(self, tmp_path):
        data = _make_gbm_payload()
        del data["class_order"]
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="class_order"):
            load_gbm_results(p)

    def test_load_missing_gbm_models_raises(self, tmp_path):
        data = _make_gbm_payload()
        del data["gbm_models"]
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="gbm_models"):
            load_gbm_results(p)

    def test_load_gbm_models_as_list_accepted(self, tmp_path):
        data = _make_gbm_payload()
        data["gbm_models"] = list(data["gbm_models"].values())
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        payload = load_gbm_results(p)
        assert isinstance(payload["gbm_models"], list)

    def test_load_gbm_models_wrong_type_raises(self, tmp_path):
        data = _make_gbm_payload()
        data["gbm_models"] = "not-a-dict-or-list"
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="gbm_models"):
            load_gbm_results(p)


# ===========================================================================
# B. load_baseline_results
# ===========================================================================


class TestLoadBaselineResults:
    def test_load_returns_dict(self, tmp_path):
        p = _write_baseline_json(tmp_path / "bl.json")
        payload = load_baseline_results(p)
        assert isinstance(payload, dict)

    def test_load_has_baselines_key(self, tmp_path):
        p = _write_baseline_json(tmp_path / "bl.json")
        payload = load_baseline_results(p)
        assert "baselines" in payload

    def test_load_missing_baselines_raises(self, tmp_path):
        data = _make_baseline_payload()
        del data["baselines"]
        p = tmp_path / "bl.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="baselines"):
            load_baseline_results(p)

    def test_load_missing_class_order_raises(self, tmp_path):
        data = _make_baseline_payload()
        del data["class_order"]
        p = tmp_path / "bl.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError, match="class_order"):
            load_baseline_results(p)


# ===========================================================================
# C. load_gbm_predictions
# ===========================================================================


class TestLoadGbmPredictions:
    def test_load_returns_dataframe(self, tmp_path):
        p = _write_pred_parquet(tmp_path / "pred.parquet")
        df = load_gbm_predictions(p)
        assert isinstance(df, pl.DataFrame)

    def test_load_has_required_columns(self, tmp_path):
        p = _write_pred_parquet(tmp_path / "pred.parquet")
        df = load_gbm_predictions(p)
        for col in ("model_id", "split_set", "y_true", "y_pred", "p_BLACK_WIN",
                    "phase", "is_time_forfeit", "has_eval", "game_id", "move_number"):
            assert col in df.columns

    def test_load_missing_column_raises(self, tmp_path):
        df = _make_pred_df().drop("p_BLACK_WIN")
        p = tmp_path / "pred.parquet"
        df.write_parquet(p)
        with pytest.raises(ValueError, match="p_BLACK_WIN"):
            load_gbm_predictions(p)


# ===========================================================================
# D. load_feature_broad
# ===========================================================================


class TestLoadFeatureBroad:
    def test_none_path_returns_none(self):
        assert load_feature_broad(None) is None

    def test_load_returns_dataframe(self, tmp_path):
        p = _write_feature_broad_parquet(tmp_path / "feat.parquet")
        df = load_feature_broad(p)
        assert isinstance(df, pl.DataFrame)

    def test_missing_avg_elo_raises(self, tmp_path):
        df = _make_feature_broad_df().drop("avg_elo")
        p = tmp_path / "feat.parquet"
        df.write_parquet(p)
        with pytest.raises(ValueError, match="avg_elo"):
            load_feature_broad(p)


# ===========================================================================
# E. get_gbm_models
# ===========================================================================


class TestGetGbmModels:
    def test_from_dict_returns_list(self):
        payload = _make_gbm_payload()
        models = get_gbm_models(payload)
        assert isinstance(models, list)
        assert len(models) == 6

    def test_from_list_returns_list(self):
        payload = _make_gbm_payload()
        payload["gbm_models"] = list(payload["gbm_models"].values())
        models = get_gbm_models(payload)
        assert len(models) == 6

    def test_sorted_by_model_id(self):
        payload = _make_gbm_payload()
        models = get_gbm_models(payload)
        ids = [m["model_id"] for m in models]
        assert ids == sorted(ids)

    def test_all_model_ids_present(self):
        models = get_gbm_models(_make_gbm_payload())
        ids = {m["model_id"] for m in models}
        assert ids == {"G1", "G2", "G3", "G4", "G5", "G6"}


# ===========================================================================
# F. get_baseline_models
# ===========================================================================


class TestGetBaselineModels:
    def test_from_dict_returns_list(self):
        payload = _make_baseline_payload()
        baselines = get_baseline_models(payload)
        assert isinstance(baselines, list)
        assert len(baselines) == 4

    def test_from_list_returns_list(self):
        payload = _make_baseline_payload()
        payload["baselines"] = list(payload["baselines"].values())
        baselines = get_baseline_models(payload)
        assert len(baselines) == 4

    def test_sorted_by_baseline_id(self):
        baselines = get_baseline_models(_make_baseline_payload())
        ids = [b["baseline_id"] for b in baselines]
        assert ids == sorted(ids)


# ===========================================================================
# G/H/I. Filter functions
# ===========================================================================


class TestFilterFunctions:
    def _all_models(self):
        return get_gbm_models(_make_gbm_payload())

    def test_broad_primary_returns_g1_g2(self):
        models = filter_broad_primary_gbms(self._all_models())
        ids = {m["model_id"] for m in models}
        assert ids == {"G1", "G2"}

    def test_broad_primary_excludes_diagnostic(self):
        models = filter_broad_primary_gbms(self._all_models())
        assert all(not m.get("diagnostic") for m in models)

    def test_broad_primary_excludes_eval(self):
        models = filter_broad_primary_gbms(self._all_models())
        assert all(m.get("table") == "broad" for m in models)

    def test_broad_diagnostic_returns_g3_g4(self):
        models = filter_broad_diagnostic_gbms(self._all_models())
        ids = {m["model_id"] for m in models}
        assert ids == {"G3", "G4"}

    def test_eval_exploratory_returns_g5_g6(self):
        models = filter_eval_exploratory_gbms(self._all_models())
        ids = {m["model_id"] for m in models}
        assert ids == {"G5", "G6"}

    def test_eval_exploratory_excludes_broad(self):
        models = filter_eval_exploratory_gbms(self._all_models())
        assert all(m.get("table") == "eval" for m in models)


# ===========================================================================
# J. get_split_metrics
# ===========================================================================


class TestGetSplitMetrics:
    def _model(self):
        return _make_gbm_model()

    def test_val_returns_dict(self):
        m = get_split_metrics(self._model(), "val")
        assert isinstance(m, dict)
        assert "log_loss" in m

    def test_train_returns_dict(self):
        m = get_split_metrics(self._model(), "train")
        assert "log_loss" in m

    def test_missing_split_raises_key_error(self):
        with pytest.raises(KeyError):
            get_split_metrics(self._model(), "nonexistent_split")

    def test_returned_log_loss_value(self):
        model = _make_gbm_model(ll_val=1.2326)
        m = get_split_metrics(model, "val")
        assert abs(m["log_loss"] - 1.2326) < 1e-6


# ===========================================================================
# K. get_per_class_metric
# ===========================================================================


class TestGetPerClassMetric:
    def test_returns_value_when_present(self):
        model = _make_gbm_model()
        val = get_per_class_metric(model, "val", "BLACK_WIN", "recall")
        assert val == pytest.approx(0.50)

    def test_returns_none_for_missing_class(self):
        model = _make_gbm_model()
        val = get_per_class_metric(model, "val", "NONEXISTENT_CLASS", "recall")
        assert val is None

    def test_returns_none_for_missing_split(self):
        model = _make_gbm_model()
        val = get_per_class_metric(model, "missing_split", "BLACK_WIN", "recall")
        assert val is None

    def test_returns_none_for_missing_metric(self):
        model = _make_gbm_model()
        val = get_per_class_metric(model, "val", "BLACK_WIN", "nonexistent_metric")
        assert val is None


# ===========================================================================
# L. format_float
# ===========================================================================


class TestFormatFloat:
    def test_none_returns_na(self):
        assert format_float(None) == "NA"

    def test_float_4_digits(self):
        assert format_float(0.8527) == "0.8527"

    def test_float_2_digits(self):
        assert format_float(0.8527, 2) == "0.85"

    def test_integer(self):
        assert format_float(1) == "1.0000"

    def test_zero(self):
        assert format_float(0.0) == "0.0000"


# ===========================================================================
# M. compute_slice_accuracy
# ===========================================================================


class TestComputeSliceAccuracy:
    def test_by_phase_returns_list(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "phase")
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_by_phase_has_expected_keys(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "phase")
        for r in rows:
            assert "slice_value" in r
            assert "n" in r
            assert "accuracy" in r

    def test_by_phase_n_sums_to_val_count(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "phase")
        total_n = sum(r["n"] for r in rows)
        assert total_n == 10  # 10 val rows

    def test_by_move_number_returns_data(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "move_number")
        assert len(rows) > 0
        total_n = sum(r["n"] for r in rows)
        assert total_n == 10

    def test_by_is_time_forfeit_has_true_and_false(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "is_time_forfeit")
        values = {r["slice_value"] for r in rows}
        assert True in values
        assert False in values

    def test_by_has_eval_has_true_and_false(self):
        rows = compute_slice_accuracy(_make_pred_df(), "G2", "val", "has_eval")
        values = {r["slice_value"] for r in rows}
        assert True in values
        assert False in values

    def test_invalid_col_raises_value_error(self):
        with pytest.raises(ValueError, match="nonexistent_col"):
            compute_slice_accuracy(_make_pred_df(), "G2", "val", "nonexistent_col")

    def test_no_matching_model_returns_empty(self):
        rows = compute_slice_accuracy(_make_pred_df(), "NONEXISTENT_MODEL", "val", "phase")
        assert rows == []


# ===========================================================================
# N. compute_confidence_buckets
# ===========================================================================


class TestComputeConfidenceBuckets:
    def test_returns_list(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "G2", "val")
        assert isinstance(buckets, list)
        assert len(buckets) > 0

    def test_each_bucket_has_required_keys(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "G2", "val")
        for b in buckets:
            assert "bucket" in b
            assert "n" in b
            assert "avg_confidence" in b
            assert "accuracy" in b

    def test_n_sums_to_val_row_count(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "G2", "val")
        total_n = sum(b["n"] for b in buckets)
        assert total_n == 10  # all 10 val rows distributed across buckets

    def test_no_matching_model_returns_empty(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "NONEXISTENT", "val")
        assert buckets == []

    def test_accuracy_in_valid_range(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "G2", "val")
        for b in buckets:
            assert 0.0 <= b["accuracy"] <= 1.0

    def test_avg_confidence_at_least_bucket_lower_bound(self):
        buckets = compute_confidence_buckets(_make_pred_df(), "G2", "val")
        bucket_mins = {
            "0.4–0.5": 0.4, "0.5–0.6": 0.5, "0.6–0.7": 0.6,
            "0.7–0.8": 0.7, "0.8–0.9": 0.8, "0.9–1.0": 0.9,
        }
        for b in buckets:
            if b["bucket"] in bucket_mins:
                assert b["avg_confidence"] >= bucket_mins[b["bucket"]] - 1e-9


# ===========================================================================
# O. join_avg_elo_slice
# ===========================================================================


class TestJoinAvgEloSlice:
    def test_none_feature_broad_returns_skipped(self):
        result = join_avg_elo_slice(_make_pred_df(), None, "G2", "val")
        assert result["skipped"] is True
        assert "note" in result
        assert result["rows"] == []

    def test_with_feature_broad_not_skipped(self):
        result = join_avg_elo_slice(
            _make_pred_df(), _make_feature_broad_df(), "G2", "val"
        )
        assert result["skipped"] is False

    def test_with_feature_broad_n_joined(self):
        result = join_avg_elo_slice(
            _make_pred_df(), _make_feature_broad_df(), "G2", "val"
        )
        assert result["n_joined"] == 10
        assert result["n_null"] == 0

    def test_with_feature_broad_rows_non_empty(self):
        result = join_avg_elo_slice(
            _make_pred_df(), _make_feature_broad_df(), "G2", "val"
        )
        assert len(result["rows"]) > 0
        for r in result["rows"]:
            assert "bucket" in r
            assert "n" in r
            assert "accuracy" in r

    def test_bucket_row_n_sums_to_n_joined(self):
        result = join_avg_elo_slice(
            _make_pred_df(), _make_feature_broad_df(), "G2", "val"
        )
        total_n = sum(r["n"] for r in result["rows"])
        assert total_n == result["n_joined"]


# ===========================================================================
# P. render_gbm_evaluation_report — key phrases and structure
# ===========================================================================


class TestRenderReport:
    def _report(self, feature_broad_df=None):
        return render_gbm_evaluation_report(
            gbm_payload=_make_gbm_payload(),
            baseline_payload=_make_baseline_payload(),
            pred_df=_make_pred_df(),
            feature_broad_df=feature_broad_df,
            dataset_id="lichess_ten_zero_2024_09_25k_v1",
            version_tag="2024_09_25k_v1",
        )

    def test_report_is_string(self):
        assert isinstance(self._report(), str)

    def test_report_contains_title(self):
        assert "GBM Evaluation Report" in self._report()

    def test_report_ticket_and_labels(self):
        report = self._report()
        assert "6.2B" in report
        assert "ML/ANALYSIS" in report

    def test_report_research_framing(self):
        report = self._report()
        assert "Chess is the testbed" in report
        assert "human strategy/reasoning" in report

    def test_report_g2_does_not_beat_b3(self):
        assert "G2 does not beat B3" in self._report()

    def test_report_controlled_diagnostic_result(self):
        assert "controlled diagnostic result" in self._report()

    def test_report_near_prior_for_g4(self):
        assert "near-prior" in self._report()

    def test_report_not_directly_comparable(self):
        assert "not directly comparable" in self._report()

    def test_report_draw_mentioned(self):
        assert "DRAW" in self._report()

    def test_report_no_calibration_fitting(self):
        report = self._report()
        assert "no calibration is fitted" in report or "no calibration" in report.lower()

    def test_report_not_used_for_model_selection(self):
        assert "not used for model selection" in self._report()

    def test_report_does_not_contain_gbm_failed(self):
        report = self._report()
        assert "GBM failed" not in report

    def test_report_g4_not_called_best_gbm(self):
        report = self._report()
        assert "G4 is best" not in report
        assert "G4 is the best" not in report
        assert "G4 wins" not in report

    def test_report_b3_reference_row_present(self):
        assert "B3" in self._report()

    def test_report_all_17_sections(self):
        report = self._report()
        for i in range(1, 18):
            assert f"## {i}." in report

    def test_report_log_loss_before_accuracy_in_header(self):
        report = self._report()
        ll_pos = report.find("log_loss")
        acc_pos = report.find("accuracy")
        assert ll_pos < acc_pos, "log_loss should appear before accuracy in report"

    def test_report_with_feature_broad_has_elo_data(self):
        report = self._report(feature_broad_df=_make_feature_broad_df())
        assert "avg_elo" in report or "1200" in report

    def test_report_without_feature_broad_has_skip_note(self):
        report = self._report(feature_broad_df=None)
        assert "--feature-broad" in report or "skipped" in report


# ===========================================================================
# Q. write_text
# ===========================================================================


class TestWriteText:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "hello world")
        assert p.exists()
        assert p.read_text(encoding="utf-8").startswith("hello world")

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "deep" / "out.md"
        write_text(p, "content")
        assert p.exists()

    def test_adds_trailing_newline_if_missing(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "no newline at end")
        content = p.read_text(encoding="utf-8")
        assert content.endswith("\n")


# ===========================================================================
# R. main / CLI
# ===========================================================================


class TestMain:
    def test_missing_required_args_exits_nonzero(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--dataset-id", "x"])  # missing most required args
        assert exc_info.value.code != 0

    def test_round_trip_without_feature_broad(self, tmp_path):
        gbm_json = _write_gbm_json(tmp_path / "gbm.json")
        bl_json = _write_baseline_json(tmp_path / "bl.json")
        pred_parquet = _write_pred_parquet(tmp_path / "pred.parquet")
        out = tmp_path / "report.md"

        rc = main([
            "--dataset-id", "lichess_ten_zero_2024_09_25k_v1",
            "--version-tag", "2024_09_25k_v1",
            "--gbm-results", str(gbm_json),
            "--gbm-predictions", str(pred_parquet),
            "--baseline-results", str(bl_json),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "GBM Evaluation Report" in content

    def test_round_trip_with_feature_broad(self, tmp_path):
        gbm_json = _write_gbm_json(tmp_path / "gbm.json")
        bl_json = _write_baseline_json(tmp_path / "bl.json")
        pred_parquet = _write_pred_parquet(tmp_path / "pred.parquet")
        feat_parquet = _write_feature_broad_parquet(tmp_path / "feat.parquet")
        out = tmp_path / "report.md"

        rc = main([
            "--dataset-id", "lichess_ten_zero_2024_09_25k_v1",
            "--version-tag", "2024_09_25k_v1",
            "--gbm-results", str(gbm_json),
            "--gbm-predictions", str(pred_parquet),
            "--baseline-results", str(bl_json),
            "--feature-broad", str(feat_parquet),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "6.2B" in content
