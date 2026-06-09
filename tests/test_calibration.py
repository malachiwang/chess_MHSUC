"""
tests/test_calibration.py — Tests for calibration.py (Phase 7.1B).

Synthetic fixtures only. No real data/ files loaded.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.calibration import (
    _CALIBRATION_MODEL_IDS,
    _N_CONFIDENCE_BINS,
    _N_RELIABILITY_BINS,
    _PROB_COLS,
    check_probability_sanity,
    compute_classwise_brier,
    compute_confidence_accuracy_table,
    compute_ece,
    compute_reliability_table,
    filter_calibration_models,
    get_class_order,
    load_baseline_predictions,
    load_gbm_predictions,
    render_calibration_report,
    render_markdown_table,
    standardize_prediction_schema,
    summarize_model_calibration,
    write_text,
    main,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pred_rows(model_col: str, model_id: str, split: str, n: int = 30) -> dict:
    """Build a minimal prediction DataFrame with synthetic probabilities."""
    rng = np.random.default_rng(42)
    p_bw = rng.uniform(0.3, 0.6, n)
    p_d = rng.uniform(0.01, 0.08, n)
    p_ww = 1.0 - p_bw - p_d
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    result_class = [classes[i % 3] for i in range(n)]
    pred_class = [classes[int(np.argmax([pb, pd, pw]))]
                  for pb, pd, pw in zip(p_bw, p_d, p_ww)]
    return {
        model_col: [model_id] * n,
        "split_set": [split] * n,
        "game_id": [f"g{i}" for i in range(n)],
        "result_class": result_class,
        "pred_class": pred_class,
        "p_BLACK_WIN": p_bw.tolist(),
        "p_DRAW": p_d.tolist(),
        "p_WHITE_WIN": p_ww.tolist(),
    }


def _make_baseline_df(model_id: str = "B3", split: str = "val", n: int = 30) -> pl.DataFrame:
    data = _make_pred_rows("baseline_id", model_id, split, n)
    return pl.DataFrame(data)


def _make_gbm_df(model_id: str = "G2", split: str = "val", n: int = 30) -> pl.DataFrame:
    data = _make_pred_rows("model_id", model_id, split, n)
    data["view"] = ["primary_numbered"] * n
    data["table"] = ["broad"] * n
    return pl.DataFrame(data)


def _make_combined_df(include_models: list[str] | None = None) -> pl.DataFrame:
    """Build a combined standardized prediction DataFrame."""
    if include_models is None:
        include_models = ["B1", "B3", "G2"]
    frames = []
    for mid in include_models:
        rng = np.random.default_rng(0)
        n = 30
        p_bw = rng.uniform(0.3, 0.6, n)
        p_d = rng.uniform(0.01, 0.08, n)
        p_ww = 1.0 - p_bw - p_d
        classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
        result_class = [classes[i % 3] for i in range(n)]
        pred_class = [classes[int(np.argmax([pb, pd, pw]))]
                      for pb, pd, pw in zip(p_bw, p_d, p_ww)]
        frames.append(pl.DataFrame({
            "model_id": [mid] * n,
            "split_set": ["val"] * n,
            "game_id": [f"{mid}_g{i}" for i in range(n)],
            "result_class": result_class,
            "pred_class": pred_class,
            "p_BLACK_WIN": p_bw.tolist(),
            "p_DRAW": p_d.tolist(),
            "p_WHITE_WIN": p_ww.tolist(),
        }))
    return pl.concat(frames)


# ---------------------------------------------------------------------------
# A. get_class_order
# ---------------------------------------------------------------------------


class TestGetClassOrder:
    def test_returns_list(self):
        result = get_class_order()
        assert isinstance(result, list)

    def test_contains_three_classes(self):
        result = get_class_order()
        assert len(result) == 3

    def test_correct_classes(self):
        result = get_class_order()
        assert set(result) == {"BLACK_WIN", "DRAW", "WHITE_WIN"}

    def test_canonical_order(self):
        result = get_class_order()
        assert result == ["BLACK_WIN", "DRAW", "WHITE_WIN"]

    def test_returns_new_list(self):
        a = get_class_order()
        b = get_class_order()
        a.append("EXTRA")
        assert len(b) == 3


# ---------------------------------------------------------------------------
# B/C. load_baseline_predictions / load_gbm_predictions
# ---------------------------------------------------------------------------


class TestLoadBaseline:
    def test_missing_baseline_id_raises(self, tmp_path):
        df = _make_baseline_df()
        bad = df.drop("baseline_id")
        bad.write_parquet(tmp_path / "bad.parquet")
        with pytest.raises(ValueError, match="baseline_id"):
            load_baseline_predictions(tmp_path / "bad.parquet")

    def test_missing_prob_col_raises(self, tmp_path):
        df = _make_baseline_df()
        bad = df.drop("p_DRAW")
        bad.write_parquet(tmp_path / "bad.parquet")
        with pytest.raises(ValueError, match="p_DRAW"):
            load_baseline_predictions(tmp_path / "bad.parquet")

    def test_valid_parquet_loads(self, tmp_path):
        df = _make_baseline_df()
        df.write_parquet(tmp_path / "bl.parquet")
        result = load_baseline_predictions(tmp_path / "bl.parquet")
        assert len(result) == len(df)
        assert "baseline_id" in result.columns


class TestLoadGbm:
    def test_missing_model_id_raises(self, tmp_path):
        df = _make_gbm_df()
        bad = df.drop("model_id")
        bad.write_parquet(tmp_path / "bad.parquet")
        with pytest.raises(ValueError, match="model_id"):
            load_gbm_predictions(tmp_path / "bad.parquet")

    def test_valid_parquet_loads(self, tmp_path):
        df = _make_gbm_df()
        df.write_parquet(tmp_path / "gbm.parquet")
        result = load_gbm_predictions(tmp_path / "gbm.parquet")
        assert "model_id" in result.columns
        assert len(result) == len(df)


# ---------------------------------------------------------------------------
# D. standardize_prediction_schema
# ---------------------------------------------------------------------------


class TestStandardizePredictionSchema:
    def test_renames_baseline_id(self):
        bl = _make_baseline_df()
        gbm = _make_gbm_df()
        combined = standardize_prediction_schema(bl, gbm)
        assert "model_id" in combined.columns
        assert "baseline_id" not in combined.columns

    def test_combined_row_count(self):
        bl = _make_baseline_df(n=20)
        gbm = _make_gbm_df(n=15)
        combined = standardize_prediction_schema(bl, gbm)
        assert len(combined) == 20 + 15

    def test_filters_gbm_to_primary_numbered(self):
        bl = _make_baseline_df(n=10)
        gbm_rows = _make_pred_rows("model_id", "G2", "val", 10)
        gbm_rows["view"] = ["primary_numbered"] * 5 + ["last"] * 5
        gbm_rows["table"] = ["broad"] * 10
        gbm = pl.DataFrame(gbm_rows)
        combined = standardize_prediction_schema(bl, gbm)
        # Only 5 GBM rows (primary_numbered) + 10 baseline rows
        assert len(combined) == 10 + 5

    def test_no_view_column_in_gbm(self):
        bl = _make_baseline_df(n=10)
        gbm = _make_gbm_df(n=10).drop("view")
        combined = standardize_prediction_schema(bl, gbm)
        assert len(combined) == 10 + 10

    def test_output_has_required_columns(self):
        bl = _make_baseline_df()
        gbm = _make_gbm_df()
        combined = standardize_prediction_schema(bl, gbm)
        for col in ["model_id", "split_set", "result_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]:
            assert col in combined.columns


# ---------------------------------------------------------------------------
# E. filter_calibration_models
# ---------------------------------------------------------------------------


class TestFilterCalibrationModels:
    def test_default_keeps_b1_b3_g2(self):
        df = _make_combined_df(["B1", "B3", "G2", "G4", "G6"])
        result = filter_calibration_models(df)
        assert set(result["model_id"].unique().to_list()) == {"B1", "B3", "G2"}

    def test_excludes_g4(self):
        df = _make_combined_df(["B3", "G2", "G4"])
        result = filter_calibration_models(df)
        assert "G4" not in result["model_id"].to_list()

    def test_custom_model_ids(self):
        df = _make_combined_df(["B1", "B3", "G2"])
        result = filter_calibration_models(df, model_ids=["B3"])
        assert set(result["model_id"].unique().to_list()) == {"B3"}

    def test_empty_result_when_no_match(self):
        df = _make_combined_df(["B1"])
        result = filter_calibration_models(df, model_ids=["G2"])
        assert len(result) == 0


# ---------------------------------------------------------------------------
# F. check_probability_sanity
# ---------------------------------------------------------------------------


class TestCheckProbabilitySanity:
    def test_valid_probs_pass(self):
        df = _make_combined_df()
        result = check_probability_sanity(df)
        assert result["no_nulls"] is True
        assert result["all_non_negative"] is True
        assert result["prob_sum_near_one"] is True

    def test_negative_prob_detected(self):
        df = _make_combined_df(["B3"])
        data = df.to_dict(as_series=False)
        data["p_BLACK_WIN"][0] = -0.1
        data["p_WHITE_WIN"][0] += 0.1
        bad_df = pl.DataFrame(data)
        result = check_probability_sanity(bad_df)
        assert result["all_non_negative"] is False

    def test_max_sum_deviation_returned(self):
        df = _make_combined_df()
        result = check_probability_sanity(df)
        assert isinstance(result["max_sum_deviation"], float)
        assert result["max_sum_deviation"] >= 0.0


# ---------------------------------------------------------------------------
# G. compute_confidence_accuracy_table
# ---------------------------------------------------------------------------


class TestComputeConfidenceAccuracyTable:
    def test_returns_list_of_dicts(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_required_keys(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        if rows:
            for key in ["bin_lower", "bin_upper", "n", "accuracy", "mean_confidence", "gap"]:
                assert key in rows[0]

    def test_bin_counts_sum_to_total(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        total = sum(r["n"] for r in rows)
        assert total == len(df)

    def test_gap_equals_conf_minus_acc(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        for r in rows:
            assert abs(r["gap"] - (r["mean_confidence"] - r["accuracy"])) < 1e-9

    def test_accuracy_in_0_1(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        for r in rows:
            assert 0.0 <= r["accuracy"] <= 1.0

    def test_mean_confidence_in_bin_range(self):
        df = _make_combined_df(["B3"])
        rows = compute_confidence_accuracy_table(df)
        for r in rows:
            assert r["bin_lower"] <= r["mean_confidence"] <= r["bin_upper"] + 1e-9


# ---------------------------------------------------------------------------
# H. compute_reliability_table
# ---------------------------------------------------------------------------


class TestComputeReliabilityTable:
    def test_returns_list_of_dicts(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        assert isinstance(rows, list)

    def test_required_keys(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        if rows:
            for key in ["bin_lower", "bin_upper", "n", "frac_positive", "mean_pred_prob", "gap"]:
                assert key in rows[0]

    def test_bin_counts_sum_to_total(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        total = sum(r["n"] for r in rows)
        assert total == len(df)

    def test_frac_positive_in_0_1(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        for r in rows:
            assert 0.0 <= r["frac_positive"] <= 1.0

    def test_gap_is_pred_minus_frac(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        for r in rows:
            assert abs(r["gap"] - (r["mean_pred_prob"] - r["frac_positive"])) < 1e-9

    def test_draw_class(self):
        df = _make_combined_df(["B3"])
        rows = compute_reliability_table(df, "DRAW", "p_DRAW")
        assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# I. compute_ece
# ---------------------------------------------------------------------------


class TestComputeEce:
    def test_returns_float(self):
        df = _make_combined_df(["B3"])
        rel = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        ece = compute_ece(rel, len(df))
        assert isinstance(ece, float)

    def test_non_negative(self):
        df = _make_combined_df(["B3"])
        rel = compute_reliability_table(df, "BLACK_WIN", "p_BLACK_WIN")
        ece = compute_ece(rel, len(df))
        assert ece >= 0.0

    def test_zero_total_returns_zero(self):
        assert compute_ece([], 0) == 0.0

    def test_empty_rows_returns_zero(self):
        assert compute_ece([], 100) == 0.0

    def test_perfect_calibration_gives_zero(self):
        # If gap=0 for all bins, ECE=0
        rows = [
            {"n": 10, "frac_positive": 0.3, "mean_pred_prob": 0.3, "gap": 0.0},
            {"n": 10, "frac_positive": 0.5, "mean_pred_prob": 0.5, "gap": 0.0},
        ]
        assert compute_ece(rows, 20) == 0.0

    def test_constant_gap_gives_weighted_sum(self):
        # One bin with gap=0.1, weight=1.0
        rows = [{"n": 100, "frac_positive": 0.3, "mean_pred_prob": 0.4, "gap": 0.1}]
        ece = compute_ece(rows, 100)
        assert abs(ece - 0.1) < 1e-9


# ---------------------------------------------------------------------------
# J. compute_classwise_brier
# ---------------------------------------------------------------------------


class TestComputeClasswiseBrier:
    def test_returns_float(self):
        df = _make_combined_df(["B3"])
        brier = compute_classwise_brier(df, "BLACK_WIN", "p_BLACK_WIN")
        assert isinstance(brier, float)

    def test_non_negative(self):
        df = _make_combined_df(["B3"])
        brier = compute_classwise_brier(df, "BLACK_WIN", "p_BLACK_WIN")
        assert brier >= 0.0

    def test_at_most_one(self):
        df = _make_combined_df(["B3"])
        brier = compute_classwise_brier(df, "BLACK_WIN", "p_BLACK_WIN")
        assert brier <= 1.0

    def test_perfect_brier_is_zero(self):
        # If p_pred == y_binary, brier = 0
        df = pl.DataFrame({
            "result_class": ["BLACK_WIN"] * 5,
            "p_BLACK_WIN": [1.0] * 5,
        })
        brier = compute_classwise_brier(df, "BLACK_WIN", "p_BLACK_WIN")
        assert abs(brier) < 1e-9

    def test_worst_brier_is_one(self):
        # p_pred=1 when true is 0 → (1-0)^2 = 1
        df = pl.DataFrame({
            "result_class": ["WHITE_WIN"] * 4,
            "p_BLACK_WIN": [1.0] * 4,
        })
        brier = compute_classwise_brier(df, "BLACK_WIN", "p_BLACK_WIN")
        assert abs(brier - 1.0) < 1e-9

    def test_draw_class(self):
        df = _make_combined_df(["B3"])
        brier = compute_classwise_brier(df, "DRAW", "p_DRAW")
        assert 0.0 <= brier <= 1.0


# ---------------------------------------------------------------------------
# K. summarize_model_calibration
# ---------------------------------------------------------------------------


class TestSummarizeModelCalibration:
    def test_returns_dict_with_required_keys(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        for key in ["model_id", "split_set", "n_rows", "class_counts",
                    "confidence_accuracy_table", "reliability", "ece", "classwise_brier"]:
            assert key in result

    def test_model_id_correct(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "G2", "val")
        assert result["model_id"] == "G2"

    def test_split_set_correct(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        assert result["split_set"] == "val"

    def test_class_counts_keys(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        for cls in get_class_order():
            assert cls in result["class_counts"]

    def test_reliability_keys_are_classes(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        assert set(result["reliability"].keys()) == set(get_class_order())

    def test_ece_keys_are_classes(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        assert set(result["ece"].keys()) == set(get_class_order())

    def test_brier_keys_are_classes(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        assert set(result["classwise_brier"].keys()) == set(get_class_order())

    def test_ece_non_negative(self):
        df = _make_combined_df()
        result = summarize_model_calibration(df, "B3", "val")
        for cls in get_class_order():
            assert result["ece"][cls] >= 0.0


# ---------------------------------------------------------------------------
# L. render_markdown_table
# ---------------------------------------------------------------------------


class TestRenderMarkdownTable:
    def test_returns_string(self):
        result = render_markdown_table(["A", "B"], [["1", "2"]])
        assert isinstance(result, str)

    def test_header_present(self):
        result = render_markdown_table(["Col1", "Col2"], [])
        assert "Col1" in result
        assert "Col2" in result

    def test_separator_present(self):
        result = render_markdown_table(["A"], [])
        assert "---" in result

    def test_row_data_present(self):
        result = render_markdown_table(["X"], [["hello"]])
        assert "hello" in result

    def test_pipe_delimited(self):
        result = render_markdown_table(["A", "B"], [["1", "2"]])
        lines = result.strip().split("\n")
        for line in lines:
            assert line.startswith("|")
            assert line.endswith("|")


# ---------------------------------------------------------------------------
# M. render_calibration_report
# ---------------------------------------------------------------------------


class TestRenderCalibrationReport:
    def _make_summaries(self) -> dict:
        df = _make_combined_df()
        return {mid: summarize_model_calibration(df, mid, "val")
                for mid in ["B1", "B3", "G2"]}

    def test_returns_string(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert isinstance(report, str)

    def test_contains_title(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert "Calibration Diagnostic" in report

    def test_contains_b3(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert "B3" in report

    def test_contains_g2(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert "G2" in report

    def test_contains_draw_caveat(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert "DRAW" in report

    def test_no_post_hoc_calibrators(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "test_dataset", "test_tag")
        assert "no post-hoc calibrators" in report.lower() or \
               "no post-hoc" in report.lower() or \
               "not fitted" in report.lower() or \
               "not applied" in report.lower()

    def test_dataset_id_in_report(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "my_dataset_id", "my_tag")
        assert "my_dataset_id" in report

    def test_version_tag_in_report(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "ver_2024_tag")
        assert "ver_2024_tag" in report

    def test_acceptance_criteria_section_present(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "tag")
        assert "Acceptance Criteria" in report

    def test_no_causal_claim(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "tag")
        lower = report.lower()
        # Must not contain unqualified causal claims
        assert "calibration proves" not in lower
        assert "causes outcomes" not in lower

    def test_g4_exclusion_mentioned(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "tag")
        assert "G4" in report

    def test_g6_exclusion_mentioned(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "tag")
        assert "G6" in report

    def test_reproducibility_section_present(self):
        summaries = self._make_summaries()
        report = render_calibration_report(summaries, "ds", "tag")
        assert "Reproducibility" in report


# ---------------------------------------------------------------------------
# N. write_text
# ---------------------------------------------------------------------------


class TestWriteText:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "test_output.md"
        write_text(p, "hello world")
        assert p.exists()

    def test_content_written(self, tmp_path):
        p = tmp_path / "output.md"
        write_text(p, "test content")
        assert p.read_text(encoding="utf-8").strip() == "test content"

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "c" / "out.md"
        write_text(p, "nested")
        assert p.exists()

    def test_overwrites_existing(self, tmp_path):
        p = tmp_path / "file.md"
        write_text(p, "first")
        write_text(p, "second")
        content = p.read_text(encoding="utf-8")
        assert "second" in content
        assert "first" not in content


# ---------------------------------------------------------------------------
# O. main (CLI)
# ---------------------------------------------------------------------------


class TestMain:
    def _write_parquets(self, tmp_path):
        bl = _make_baseline_df("B1", "val", 30)
        bl2 = _make_baseline_df("B3", "val", 30)
        gbm = _make_gbm_df("G2", "val", 30)
        baseline_all = pl.concat([bl, bl2])
        baseline_all.write_parquet(tmp_path / "baseline_preds.parquet")
        gbm.write_parquet(tmp_path / "gbm_preds.parquet")

    def test_main_creates_output(self, tmp_path):
        self._write_parquets(tmp_path)
        out = tmp_path / "report.md"
        rc = main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-predictions", str(tmp_path / "baseline_preds.parquet"),
            "--gbm-predictions", str(tmp_path / "gbm_preds.parquet"),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()

    def test_main_report_nonempty(self, tmp_path):
        self._write_parquets(tmp_path)
        out = tmp_path / "report.md"
        main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-predictions", str(tmp_path / "baseline_preds.parquet"),
            "--gbm-predictions", str(tmp_path / "gbm_preds.parquet"),
            "--output", str(out),
        ])
        content = out.read_text(encoding="utf-8")
        assert len(content) > 100

    def test_main_report_contains_calibration(self, tmp_path):
        self._write_parquets(tmp_path)
        out = tmp_path / "report.md"
        main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-predictions", str(tmp_path / "baseline_preds.parquet"),
            "--gbm-predictions", str(tmp_path / "gbm_preds.parquet"),
            "--output", str(out),
        ])
        content = out.read_text(encoding="utf-8")
        assert "Calibration" in content
