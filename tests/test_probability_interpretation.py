"""
tests/test_probability_interpretation.py — Tests for probability_interpretation.py (Phase 7.2B).

Synthetic fixtures only. No real data/ files loaded.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.probability_interpretation import (
    extract_model_log_loss,
    extract_probability_distribution_notes,
    get_class_order,
    load_baseline_results,
    load_calibration_numbers,
    load_gbm_results,
    main,
    render_allowed_cautious_forbidden_claims_table,
    render_model_trustworthiness_section,
    render_probability_interpretation_report,
    render_probability_semantics_section,
    write_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_baseline_results(include: list[str] | None = None) -> dict:
    """Build a minimal synthetic baseline_results dict."""
    all_ids = include or ["B0", "B1", "B2", "B3", "B4", "B5", "B3-balanced"]
    baselines = {}
    ll_map = {
        "B0": 18.89, "B1": 0.885, "B2": 0.874, "B3": 0.8527,
        "B4": 0.783, "B5": 0.860, "B3-balanced": 1.062,
    }
    for mid in all_ids:
        baselines[mid] = {
            "baseline_id": mid,
            "metrics": {
                "train": {"log_loss": 0.80},
                "val": {"log_loss": ll_map.get(mid, 0.90)},
                "test": {"log_loss": ll_map.get(mid, 0.91) + 0.01},
            },
        }
    return {
        "dataset_id": "test_ds",
        "version_tag": "test_tag",
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "baselines": baselines,
    }


def _make_gbm_results(include: list[str] | None = None) -> dict:
    """Build a minimal synthetic gbm_results dict."""
    all_ids = include or ["G1", "G2", "G3", "G4", "G5", "G6"]
    ll_map = {
        "G1": (0.185, 1.418), "G2": (0.164, 1.233),
        "G3": (0.554, 0.986), "G4": (0.880, 0.881),
        "G5": (0.423, 1.185), "G6": (0.004, 1.641),
    }
    models = {}
    for mid in all_ids:
        tr, va = ll_map.get(mid, (0.50, 0.90))
        models[mid] = {
            "model_id": mid,
            "metrics": {
                "train": {"log_loss": tr},
                "val": {"log_loss": va},
                "test": {"log_loss": va + 0.01},
            },
        }
    return {
        "dataset_id": "test_ds",
        "version_tag": "test_tag",
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "gbm_models": models,
    }


def _make_pred_rows(model_col: str, model_id: str, split: str, n: int = 40) -> dict:
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
        "game_id": [f"{model_id}_g{i}" for i in range(n)],
        "result_class": result_class,
        "pred_class": pred_class,
        "p_BLACK_WIN": p_bw.tolist(),
        "p_DRAW": p_d.tolist(),
        "p_WHITE_WIN": p_ww.tolist(),
    }


def _write_baseline_parquet(tmp_path: Path) -> Path:
    frames = []
    for mid in ["B1", "B3"]:
        for split in ["train", "val", "test"]:
            rows = _make_pred_rows("baseline_id", mid, split, n=30)
            frames.append(pl.DataFrame(rows))
    df = pl.concat(frames)
    p = tmp_path / "baseline_preds.parquet"
    df.write_parquet(p)
    return p


def _write_gbm_parquet(tmp_path: Path) -> Path:
    frames = []
    for mid in ["G2"]:
        for split in ["train", "val", "test"]:
            rows = _make_pred_rows("model_id", mid, split, n=30)
            rows["view"] = ["primary_numbered"] * 30
            rows["table"] = ["broad"] * 30
            frames.append(pl.DataFrame(rows))
    df = pl.concat(frames)
    p = tmp_path / "gbm_preds.parquet"
    df.write_parquet(p)
    return p


def _write_results_json(tmp_path: Path) -> tuple[Path, Path]:
    bl = tmp_path / "baseline_results.json"
    gm = tmp_path / "gbm_results.json"
    bl.write_text(json.dumps(_make_baseline_results()), encoding="utf-8")
    gm.write_text(json.dumps(_make_gbm_results()), encoding="utf-8")
    return bl, gm


# ---------------------------------------------------------------------------
# A. get_class_order
# ---------------------------------------------------------------------------


class TestGetClassOrder:
    def test_returns_three_classes(self):
        assert len(get_class_order()) == 3

    def test_correct_classes(self):
        assert set(get_class_order()) == {"BLACK_WIN", "DRAW", "WHITE_WIN"}

    def test_returns_list(self):
        assert isinstance(get_class_order(), list)


# ---------------------------------------------------------------------------
# B. load_baseline_results
# ---------------------------------------------------------------------------


class TestLoadBaselineResults:
    def test_valid_payload_loads(self, tmp_path):
        p = tmp_path / "bl.json"
        p.write_text(json.dumps(_make_baseline_results()), encoding="utf-8")
        result = load_baseline_results(p)
        assert "baselines" in result

    def test_missing_baselines_key_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"x": 1}), encoding="utf-8")
        with pytest.raises(ValueError, match="baselines"):
            load_baseline_results(p)

    def test_missing_b3_raises(self, tmp_path):
        p = tmp_path / "no_b3.json"
        payload = _make_baseline_results(include=["B0", "B1"])
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="B3"):
            load_baseline_results(p)

    def test_missing_b1_raises(self, tmp_path):
        p = tmp_path / "no_b1.json"
        payload = _make_baseline_results(include=["B3"])
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="B1"):
            load_baseline_results(p)


# ---------------------------------------------------------------------------
# C. load_gbm_results
# ---------------------------------------------------------------------------


class TestLoadGbmResults:
    def test_valid_payload_loads(self, tmp_path):
        p = tmp_path / "gbm.json"
        p.write_text(json.dumps(_make_gbm_results()), encoding="utf-8")
        result = load_gbm_results(p)
        assert "gbm_models" in result

    def test_missing_gbm_models_key_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"x": 1}), encoding="utf-8")
        with pytest.raises(ValueError, match="gbm_models"):
            load_gbm_results(p)

    def test_missing_g2_raises(self, tmp_path):
        p = tmp_path / "no_g2.json"
        payload = _make_gbm_results(include=["G1", "G3"])
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="G2"):
            load_gbm_results(p)


# ---------------------------------------------------------------------------
# D. extract_model_log_loss
# ---------------------------------------------------------------------------


class TestExtractModelLogLoss:
    def test_returns_dict_with_required_keys(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        for key in ["B1_val_log_loss", "B3_val_log_loss",
                    "G2_train_log_loss", "G2_val_log_loss", "G2_overfit_gap"]:
            assert key in result

    def test_b3_val_log_loss_correct(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        assert abs(result["B3_val_log_loss"] - 0.8527) < 0.001

    def test_b1_val_log_loss_correct(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        assert abs(result["B1_val_log_loss"] - 0.885) < 0.001

    def test_g2_overfit_gap_positive(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        assert result["G2_overfit_gap"] > 0

    def test_g2_overfit_gap_equals_val_minus_train(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        expected = result["G2_val_log_loss"] - result["G2_train_log_loss"]
        assert abs(result["G2_overfit_gap"] - expected) < 1e-9

    def test_g2_val_exceeds_b3_val(self):
        bl = _make_baseline_results()
        gm = _make_gbm_results()
        result = extract_model_log_loss(bl, gm)
        assert result["G2_val_log_loss"] > result["B3_val_log_loss"]


# ---------------------------------------------------------------------------
# E. load_calibration_numbers
# ---------------------------------------------------------------------------


class TestLoadCalibrationNumbers:
    def test_returns_dict_with_b1_b3_g2(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = load_calibration_numbers(bl_p, gm_p)
        for mid in ["B1", "B3", "G2"]:
            assert mid in result

    def test_each_summary_has_ece(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = load_calibration_numbers(bl_p, gm_p)
        for mid in ["B1", "B3", "G2"]:
            assert "ece" in result[mid]
            for cls in get_class_order():
                assert cls in result[mid]["ece"]

    def test_each_summary_has_brier(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = load_calibration_numbers(bl_p, gm_p)
        for mid in ["B1", "B3", "G2"]:
            assert "classwise_brier" in result[mid]

    def test_ece_values_non_negative(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = load_calibration_numbers(bl_p, gm_p)
        for mid in ["B1", "B3", "G2"]:
            for cls in get_class_order():
                assert result[mid]["ece"][cls] >= 0.0

    def test_unrelated_models_not_in_result(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = load_calibration_numbers(bl_p, gm_p)
        assert "G4" not in result
        assert "B0" not in result


# ---------------------------------------------------------------------------
# F. extract_probability_distribution_notes
# ---------------------------------------------------------------------------


class TestExtractProbabilityDistributionNotes:
    def test_returns_expected_keys(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = extract_probability_distribution_notes(bl_p, gm_p)
        for key in ["B3_p_WHITE_WIN", "B3_p_DRAW", "G2_p_WHITE_WIN", "G2_p_DRAW"]:
            assert key in result

    def test_stats_have_mean_std_min_max(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = extract_probability_distribution_notes(bl_p, gm_p)
        for k in result:
            assert "mean" in result[k]
            assert "std" in result[k]
            assert "min" in result[k]
            assert "max" in result[k]

    def test_b3_draw_std_small(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        result = extract_probability_distribution_notes(bl_p, gm_p)
        # p_DRAW should have small std relative to p_WHITE_WIN
        assert result["B3_p_DRAW"]["std"] < result["B3_p_WHITE_WIN"]["std"]


# ---------------------------------------------------------------------------
# G. render_allowed_cautious_forbidden_claims_table
# ---------------------------------------------------------------------------


class TestRenderAllowedCautiousForbiddenTable:
    def test_returns_string(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert isinstance(result, str)

    def test_contains_allowed(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "Allowed" in result

    def test_contains_cautious(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "Cautious" in result

    def test_contains_forbidden(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "Forbidden" in result

    def test_contains_b3_safest(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "B3" in result and "safest" in result.lower()

    def test_contains_g2_overconfident(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "G2" in result and "overconfident" in result.lower()

    def test_contains_draw_unreliable(self):
        result = render_allowed_cautious_forbidden_claims_table()
        assert "DRAW" in result

    def test_no_degradation_curve_established(self):
        result = render_allowed_cautious_forbidden_claims_table()
        lower = result.lower()
        # Should not positively claim degradation curve is established
        assert "degradation curve established" not in lower

    def test_forbidden_causal_effect(self):
        result = render_allowed_cautious_forbidden_claims_table()
        lower = result.lower()
        assert "causal" in lower  # should mention causal in forbidden


# ---------------------------------------------------------------------------
# H. render_probability_semantics_section
# ---------------------------------------------------------------------------


class TestRenderProbabilitySemantics:
    def test_returns_string(self):
        assert isinstance(render_probability_semantics_section(), str)

    def test_mentions_p_black_win(self):
        result = render_probability_semantics_section()
        assert "p_BLACK_WIN" in result or "BLACK_WIN" in result

    def test_mentions_p_draw(self):
        result = render_probability_semantics_section()
        assert "p_DRAW" in result or "DRAW" in result

    def test_mentions_p_white_win(self):
        result = render_probability_semantics_section()
        assert "p_WHITE_WIN" in result or "WHITE_WIN" in result

    def test_mentions_human(self):
        result = render_probability_semantics_section()
        assert "human" in result.lower()

    def test_mentions_checkpoint(self):
        result = render_probability_semantics_section()
        assert "checkpoint" in result.lower() or "selected position" in result.lower()


# ---------------------------------------------------------------------------
# I. render_model_trustworthiness_section
# ---------------------------------------------------------------------------


def _make_metrics(tmp_path: Path) -> dict:
    """Build metrics dict by loading synthetic parquets."""
    bl_p = _write_baseline_parquet(tmp_path)
    gm_p = _write_gbm_parquet(tmp_path)
    ll_dict = extract_model_log_loss(_make_baseline_results(), _make_gbm_results())
    cal = load_calibration_numbers(bl_p, gm_p)
    return {"log_loss": ll_dict, "calibration": cal}


class TestRenderModelTrustworthiness:
    def test_returns_string(self, tmp_path):
        metrics = _make_metrics(tmp_path)
        result = render_model_trustworthiness_section(metrics)
        assert isinstance(result, str)

    def test_mentions_b1_trap(self, tmp_path):
        metrics = _make_metrics(tmp_path)
        result = render_model_trustworthiness_section(metrics)
        assert "trap" in result.lower() or "low-ece" in result.lower()

    def test_mentions_b3_safest(self, tmp_path):
        metrics = _make_metrics(tmp_path)
        result = render_model_trustworthiness_section(metrics)
        assert "B3" in result
        assert "safest" in result.lower() or "safe" in result.lower()

    def test_mentions_g2_not_trustworthy(self, tmp_path):
        metrics = _make_metrics(tmp_path)
        result = render_model_trustworthiness_section(metrics)
        assert "G2" in result
        lower = result.lower()
        assert "not" in lower and (
            "trustworthy" in lower or "unsafe" in lower
            or "overconfident" in lower or "overconfidence" in lower
        )

    def test_mentions_draw_caveat(self, tmp_path):
        metrics = _make_metrics(tmp_path)
        result = render_model_trustworthiness_section(metrics)
        assert "DRAW" in result


# ---------------------------------------------------------------------------
# Full report rendering
# ---------------------------------------------------------------------------


def _build_full_report(tmp_path: Path) -> str:
    bl_p = _write_baseline_parquet(tmp_path)
    gm_p = _write_gbm_parquet(tmp_path)
    bl_results = _make_baseline_results()
    gm_results = _make_gbm_results()
    ll_dict = extract_model_log_loss(bl_results, gm_results)
    cal_summaries = load_calibration_numbers(bl_p, gm_p)
    dist_notes = extract_probability_distribution_notes(bl_p, gm_p)
    return render_probability_interpretation_report(
        ll_dict=ll_dict,
        cal_summaries=cal_summaries,
        dist_notes=dist_notes,
        dataset_id="test_ds",
        version_tag="test_tag",
    )


class TestReportLanguage:
    """Tests that required phrases appear in the report."""

    def test_ticket_label_present(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "7.2B — Probability Interpretation Report Implementation" in report

    def test_reporting_label_present(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "REPORTING/ML | D1 | IMPLEMENTATION" in report

    def test_chess_testbed(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "Chess is the testbed" in report

    def test_human_strategy_reasoning(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "human strategy" in report.lower() or "human strategy/reasoning" in report

    def test_b3_safest_current_broad_model(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "B3 is the safest current broad probability model" in report

    def test_g2_not_trustworthy(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        assert "g2" in lower
        # Should say G2 probabilities are not trustworthy or unsafe
        assert ("not trustworthy" in lower or "unsafe" in lower or
                "should not be used" in lower)

    def test_b1_low_ece_trap(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        assert "low-ece trap" in lower or "low ece" in lower

    def test_not_engine(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        assert "not engine" in lower or "not objective engine" in lower

    def test_not_causal(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        assert "not causal" in lower or "not a causal" in lower

    def test_mentions_degradation_curve(self, tmp_path):
        # Report should mention degradation curve in a forbidden/cautionary context
        report = _build_full_report(tmp_path)
        assert "degradation curve" in report.lower()

    def test_draw_probabilities_unreliable(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        assert "draw" in lower and ("unreliable" in lower or "spars" in lower)

    def test_acceptance_criteria_section_present(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "Acceptance Criteria" in report

    def test_reproducibility_section_present(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "Reproducibility" in report


class TestReportSafety:
    """Tests that forbidden positive claims are absent."""

    def test_no_probabilities_are_now_correct(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "probabilities are now correct" not in report.lower()

    def test_no_b1_is_best(self, tmp_path):
        report = _build_full_report(tmp_path)
        # "B1 is best" as a positive claim should not appear
        assert "b1 is best" not in report.lower()

    def test_no_g2_learned_human_strategy(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "g2 learned human strategy" not in report.lower()

    def test_no_g2_trustworthy_positive(self, tmp_path):
        report = _build_full_report(tmp_path)
        # Should not say "G2 probabilities are trustworthy" as a positive claim
        # (negation "not trustworthy" is fine)
        lower = report.lower()
        assert "g2 probabilities are trustworthy" not in lower

    def test_no_draw_well_modeled(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "draw is well modeled" not in report.lower()

    def test_no_engine_win_probabilities(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "engine win probabilities" not in report.lower()

    def test_no_positive_causal_effect(self, tmp_path):
        report = _build_full_report(tmp_path)
        lower = report.lower()
        import re
        # "causal effect" as a positive claim is forbidden; negation is ok.
        # Skip occurrences that are inside Markdown headings (lines starting with #)
        # or inside the forbidden-claims table (context column).
        for m in re.finditer(r"causal effect", lower):
            # Check if this occurrence is on a heading line
            line_start = lower.rfind("\n", 0, m.start()) + 1
            line_end = lower.find("\n", m.end())
            line = lower[line_start: line_end if line_end >= 0 else len(lower)]
            if line.lstrip().startswith("#"):
                continue  # skip section headings
            start = max(0, m.start() - 40)
            context = lower[start: m.end()]
            # Should have a negating word nearby or be in a table/forbidden list
            has_negation = any(neg in context for neg in ["not a", "not ", "no ", "nor "])
            in_table_row = "|" in line
            assert has_negation or in_table_row, \
                f"Possible positive causal effect claim: {lower[start: m.end()+30]!r}"

    def test_no_degradation_curve_established(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "degradation curve established" not in report.lower()

    def test_no_constraint_effects_measured(self, tmp_path):
        report = _build_full_report(tmp_path)
        assert "constraint effects measured" not in report.lower()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestMain:
    def test_cli_creates_output(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        bl_r, gm_r = _write_results_json(tmp_path)
        out = tmp_path / "report.md"
        rc = main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-results", str(bl_r),
            "--gbm-results", str(gm_r),
            "--baseline-predictions", str(bl_p),
            "--gbm-predictions", str(gm_p),
            "--output", str(out),
        ])
        assert rc == 0
        assert out.exists()

    def test_cli_report_nonempty(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        bl_r, gm_r = _write_results_json(tmp_path)
        out = tmp_path / "report.md"
        main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-results", str(bl_r),
            "--gbm-results", str(gm_r),
            "--baseline-predictions", str(bl_p),
            "--gbm-predictions", str(gm_p),
            "--output", str(out),
        ])
        content = out.read_text(encoding="utf-8")
        assert len(content) > 200

    def test_cli_report_contains_title(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        bl_r, gm_r = _write_results_json(tmp_path)
        out = tmp_path / "report.md"
        main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-results", str(bl_r),
            "--gbm-results", str(gm_r),
            "--baseline-predictions", str(bl_p),
            "--gbm-predictions", str(gm_p),
            "--output", str(out),
        ])
        content = out.read_text(encoding="utf-8")
        assert "Probability Interpretation Guardrails Report" in content

    def test_cli_no_model_artifacts(self, tmp_path):
        bl_p = _write_baseline_parquet(tmp_path)
        gm_p = _write_gbm_parquet(tmp_path)
        bl_r, gm_r = _write_results_json(tmp_path)
        out = tmp_path / "report.md"
        main([
            "--dataset-id", "test_ds",
            "--version-tag", "test_tag",
            "--baseline-results", str(bl_r),
            "--gbm-results", str(gm_r),
            "--baseline-predictions", str(bl_p),
            "--gbm-predictions", str(gm_p),
            "--output", str(out),
        ])
        # No .joblib, .pkl, .pt files created
        for suffix in [".joblib", ".pkl", ".pt", ".csv"]:
            assert list(tmp_path.glob(f"*{suffix}")) == []


# ---------------------------------------------------------------------------
# write_text
# ---------------------------------------------------------------------------


class TestWriteText:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "hello")
        assert p.exists()

    def test_content_correct(self, tmp_path):
        p = tmp_path / "out.md"
        write_text(p, "test content")
        assert "test content" in p.read_text(encoding="utf-8")

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "a" / "b" / "out.md"
        write_text(p, "nested")
        assert p.exists()
