"""
tests/test_baseline_evaluation.py — Unit tests for baseline_evaluation.py.

Uses synthetic fixtures only — no real data files required.
All tests are deterministic.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from chess_mhsuc.baseline_evaluation import (
    filter_broad_primary_baselines,
    filter_diagnostic_baselines,
    filter_eval_exploratory_baselines,
    format_float,
    get_baselines,
    get_per_class_metric,
    get_split_metrics,
    load_baseline_results,
    render_baseline_evaluation_report,
    render_confusion_matrix,
    render_inventory_table,
    render_signal_decomposition,
    render_test_snapshot,
    render_validation_table,
    sort_by_validation_log_loss,
    write_text,
)


# ---------------------------------------------------------------------------
# Synthetic fixture helpers
# ---------------------------------------------------------------------------

def _make_metrics(ll: float, acc: float) -> dict:
    """Minimal metrics dict matching the baselines.py schema."""
    return {
        "n_rows": 100,
        "accuracy": acc,
        "balanced_accuracy": 0.33,
        "log_loss": ll,
        "macro_f1": 0.30,
        "weighted_f1": 0.35,
        "multiclass_brier": 0.55,
        "per_class": {
            "BLACK_WIN": {"precision": 0.50, "recall": 0.50, "f1": 0.50, "support": 45},
            "DRAW":      {"precision": 0.00, "recall": 0.00, "f1": 0.00, "support": 10},
            "WHITE_WIN": {"precision": 0.50, "recall": 0.50, "f1": 0.50, "support": 45},
        },
        "confusion_matrix": [[20, 0, 25], [5, 0, 5], [15, 0, 30]],
    }


def _make_baseline(
    bid: str,
    model_type: str,
    sklearn_params: dict,
    fs_id: str,
    table: str,
    exploratory: bool,
    diagnostic: bool,
    val_ll: float,
    val_acc: float,
) -> dict:
    """Create a synthetic baseline result dict."""
    return {
        "baseline_id": bid,
        "model_type": model_type,
        "sklearn_params": sklearn_params,
        "feature_set_id": fs_id,
        "table": table,
        "view": "primary_numbered",
        "exploratory": exploratory,
        "diagnostic": diagnostic,
        "n_train_rows": 500,
        "n_val_rows": 100,
        "n_test_rows": 100,
        "n_features": 5,
        "feature_columns": ["f1", "f2", "f3"],
        "preprocessing_summary": "StandardScaler",
        "metrics": {
            "train": _make_metrics(0.80, 0.55),
            "val": _make_metrics(val_ll, val_acc),
            "test": _make_metrics(val_ll + 0.01, val_acc - 0.01),
        },
        "warnings": [],
    }


def _make_payload() -> dict:
    """Create a complete synthetic baseline results payload."""
    return {
        "dataset_id": "test_dataset_v1",
        "version_tag": "test_v1",
        "created_at_utc": "2026-01-01T12:00:00+00:00",
        "split_artifact_path": "fake/splits.json",
        "modeling_plan_path": "fake/modeling_plan.json",
        "class_order": ["BLACK_WIN", "DRAW", "WHITE_WIN"],
        "label_map": {"BLACK_WIN": 0, "DRAW": 1, "WHITE_WIN": 2},
        "baselines": {
            "B0": _make_baseline(
                "B0", "DummyClassifier", {"strategy": "most_frequent"},
                "FS-A", "broad", False, False, val_ll=18.90, val_acc=0.476
            ),
            "B1": _make_baseline(
                "B1", "DummyClassifier", {"strategy": "prior"},
                "FS-A", "broad", False, False, val_ll=0.885, val_acc=0.476
            ),
            "B2": _make_baseline(
                "B2", "LogisticRegression", {},
                "FS-B", "broad", False, False, val_ll=0.874, val_acc=0.512
            ),
            "B3": _make_baseline(
                "B3", "LogisticRegression", {},
                "FS-E", "broad", False, False, val_ll=0.853, val_acc=0.538
            ),
            "B3-balanced": _make_baseline(
                "B3-balanced", "LogisticRegression", {"class_weight": "balanced"},
                "FS-E", "broad", True, True, val_ll=1.062, val_acc=0.439
            ),
            "B4": _make_baseline(
                "B4", "LogisticRegression", {},
                "FS-F", "eval", True, False, val_ll=0.783, val_acc=0.592
            ),
            "B5": _make_baseline(
                "B5", "LogisticRegression", {},
                "FS-G", "eval", True, False, val_ll=0.860, val_acc=0.619
            ),
        },
        "warnings": [],
        "recommended_next_step": "Phase 6.1A",
    }


# ---------------------------------------------------------------------------
# A. load_baseline_results
# ---------------------------------------------------------------------------

class TestLoadBaselineResults:
    def test_load_valid_file(self, tmp_path: Path) -> None:
        payload = _make_payload()
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(p)
        assert loaded["dataset_id"] == "test_dataset_v1"

    def test_load_returns_dict(self, tmp_path: Path) -> None:
        payload = _make_payload()
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(p)
        assert isinstance(loaded, dict)

    def test_load_missing_key_raises(self, tmp_path: Path) -> None:
        payload = _make_payload()
        del payload["baselines"]
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            load_baseline_results(p)

    def test_load_baselines_not_dict_raises(self, tmp_path: Path) -> None:
        payload = _make_payload()
        payload["baselines"] = list(payload["baselines"].values())  # list, not dict
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="Expected 'baselines' to be a dict"):
            load_baseline_results(p)

    def test_load_missing_class_order_raises(self, tmp_path: Path) -> None:
        payload = _make_payload()
        del payload["class_order"]
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            load_baseline_results(p)

    def test_load_preserves_baselines_as_dict(self, tmp_path: Path) -> None:
        payload = _make_payload()
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(p)
        assert isinstance(loaded["baselines"], dict)

    def test_load_accepts_string_path(self, tmp_path: Path) -> None:
        payload = _make_payload()
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(str(p))
        assert "baselines" in loaded


# ---------------------------------------------------------------------------
# B. get_baselines
# ---------------------------------------------------------------------------

class TestGetBaselines:
    def test_returns_list(self) -> None:
        payload = _make_payload()
        result = get_baselines(payload)
        assert isinstance(result, list)

    def test_returns_all_seven(self) -> None:
        payload = _make_payload()
        result = get_baselines(payload)
        assert len(result) == 7

    def test_each_item_is_dict(self) -> None:
        payload = _make_payload()
        for b in get_baselines(payload):
            assert isinstance(b, dict)

    def test_baseline_ids_present(self) -> None:
        payload = _make_payload()
        ids = {b["baseline_id"] for b in get_baselines(payload)}
        assert "B0" in ids
        assert "B3-balanced" in ids


# ---------------------------------------------------------------------------
# C. filter_broad_primary_baselines
# ---------------------------------------------------------------------------

class TestFilterBroadPrimary:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())

    def test_returns_four(self) -> None:
        result = filter_broad_primary_baselines(self.baselines)
        assert len(result) == 4  # B0, B1, B2, B3

    def test_contains_b0_b1_b2_b3(self) -> None:
        ids = {b["baseline_id"] for b in filter_broad_primary_baselines(self.baselines)}
        assert ids == {"B0", "B1", "B2", "B3"}

    def test_excludes_b3_balanced(self) -> None:
        ids = {b["baseline_id"] for b in filter_broad_primary_baselines(self.baselines)}
        assert "B3-balanced" not in ids

    def test_excludes_eval_baselines(self) -> None:
        ids = {b["baseline_id"] for b in filter_broad_primary_baselines(self.baselines)}
        assert "B4" not in ids
        assert "B5" not in ids

    def test_all_results_are_broad(self) -> None:
        for b in filter_broad_primary_baselines(self.baselines):
            assert b["table"] == "broad"

    def test_none_are_diagnostic(self) -> None:
        for b in filter_broad_primary_baselines(self.baselines):
            assert not b.get("diagnostic", False)


# ---------------------------------------------------------------------------
# D. filter_eval_exploratory_baselines
# ---------------------------------------------------------------------------

class TestFilterEvalExploratory:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())

    def test_returns_two(self) -> None:
        result = filter_eval_exploratory_baselines(self.baselines)
        assert len(result) == 2

    def test_contains_b4_b5(self) -> None:
        ids = {b["baseline_id"] for b in filter_eval_exploratory_baselines(self.baselines)}
        assert ids == {"B4", "B5"}

    def test_all_are_eval(self) -> None:
        for b in filter_eval_exploratory_baselines(self.baselines):
            assert b["table"] == "eval"

    def test_all_are_exploratory(self) -> None:
        for b in filter_eval_exploratory_baselines(self.baselines):
            assert b["exploratory"] is True


# ---------------------------------------------------------------------------
# E. filter_diagnostic_baselines
# ---------------------------------------------------------------------------

class TestFilterDiagnostic:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())

    def test_returns_one(self) -> None:
        result = filter_diagnostic_baselines(self.baselines)
        assert len(result) == 1

    def test_is_b3_balanced(self) -> None:
        result = filter_diagnostic_baselines(self.baselines)
        assert result[0]["baseline_id"] == "B3-balanced"

    def test_all_have_diagnostic_true(self) -> None:
        for b in filter_diagnostic_baselines(self.baselines):
            assert b["diagnostic"] is True


# ---------------------------------------------------------------------------
# F. get_split_metrics
# ---------------------------------------------------------------------------

class TestGetSplitMetrics:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.b3 = next(b for b in self.baselines if b["baseline_id"] == "B3")

    def test_returns_dict(self) -> None:
        result = get_split_metrics(self.b3, "val")
        assert isinstance(result, dict)

    def test_val_log_loss(self) -> None:
        m = get_split_metrics(self.b3, "val")
        assert abs(m["log_loss"] - 0.853) < 1e-6

    def test_train_split(self) -> None:
        m = get_split_metrics(self.b3, "train")
        assert "accuracy" in m

    def test_test_split(self) -> None:
        m = get_split_metrics(self.b3, "test")
        assert "log_loss" in m

    def test_missing_split_returns_empty(self) -> None:
        result = get_split_metrics(self.b3, "holdout")
        assert result == {}

    def test_missing_metrics_key_returns_empty(self) -> None:
        b = {"baseline_id": "X"}
        assert get_split_metrics(b, "val") == {}


# ---------------------------------------------------------------------------
# G. get_per_class_metric
# ---------------------------------------------------------------------------

class TestGetPerClassMetric:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.b3 = next(b for b in self.baselines if b["baseline_id"] == "B3")

    def test_draw_recall(self) -> None:
        result = get_per_class_metric(self.b3, "val", "DRAW", "recall")
        assert result == 0.00

    def test_black_win_precision(self) -> None:
        result = get_per_class_metric(self.b3, "val", "BLACK_WIN", "precision")
        assert result == 0.50

    def test_missing_class_returns_none(self) -> None:
        result = get_per_class_metric(self.b3, "val", "UNKNOWN_CLASS", "recall")
        assert result is None

    def test_missing_metric_returns_none(self) -> None:
        result = get_per_class_metric(self.b3, "val", "DRAW", "no_such_metric")
        assert result is None

    def test_support_field(self) -> None:
        result = get_per_class_metric(self.b3, "val", "DRAW", "support")
        assert result == 10


# ---------------------------------------------------------------------------
# H. sort_by_validation_log_loss
# ---------------------------------------------------------------------------

class TestSortByValidationLogLoss:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())

    def test_sorted_ascending(self) -> None:
        sorted_b = sort_by_validation_log_loss(self.baselines)
        lls = [
            get_split_metrics(b, "val").get("log_loss", math.inf)
            for b in sorted_b
        ]
        assert lls == sorted(lls)

    def test_does_not_mutate_input(self) -> None:
        original_first = self.baselines[0]["baseline_id"]
        sort_by_validation_log_loss(self.baselines)
        assert self.baselines[0]["baseline_id"] == original_first

    def test_b3_before_b1_before_b0(self) -> None:
        sorted_b = sort_by_validation_log_loss(self.baselines)
        ids = [b["baseline_id"] for b in sorted_b]
        assert ids.index("B3") < ids.index("B1")
        assert ids.index("B1") < ids.index("B0")

    def test_none_log_loss_placed_last(self) -> None:
        baselines = [
            _make_baseline("X1", "LogisticRegression", {}, "FS-B", "broad",
                           False, False, val_ll=0.9, val_acc=0.5),
            _make_baseline("X2", "LogisticRegression", {}, "FS-B", "broad",
                           False, False, val_ll=0.8, val_acc=0.5),
        ]
        # Manually set log_loss to None for X1
        baselines[0]["metrics"]["val"]["log_loss"] = None
        sorted_b = sort_by_validation_log_loss(baselines)
        assert sorted_b[0]["baseline_id"] == "X2"
        assert sorted_b[-1]["baseline_id"] == "X1"


# ---------------------------------------------------------------------------
# I. format_float
# ---------------------------------------------------------------------------

class TestFormatFloat:
    def test_none_returns_na(self) -> None:
        assert format_float(None) == "N/A"

    def test_four_decimal_places_default(self) -> None:
        assert format_float(0.853) == "0.8530"

    def test_custom_decimals(self) -> None:
        assert format_float(0.853, 2) == "0.85"

    def test_integer_input(self) -> None:
        assert format_float(1, 4) == "1.0000"

    def test_string_numeric_input(self) -> None:
        assert format_float("0.5") == "0.5000"

    def test_invalid_returns_str(self) -> None:
        result = format_float("abc")
        assert result == "abc"

    def test_zero(self) -> None:
        assert format_float(0.0) == "0.0000"

    def test_negative(self) -> None:
        assert format_float(-0.5) == "-0.5000"


# ---------------------------------------------------------------------------
# J. render_inventory_table
# ---------------------------------------------------------------------------

class TestRenderInventoryTable:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.table = render_inventory_table(self.baselines)

    def test_returns_string(self) -> None:
        assert isinstance(self.table, str)

    def test_contains_all_baseline_ids(self) -> None:
        for bid in ["B0", "B1", "B2", "B3", "B3-balanced", "B4", "B5"]:
            assert bid in self.table

    def test_contains_header(self) -> None:
        assert "Val log_loss" in self.table
        assert "Val acc" in self.table

    def test_log_loss_before_acc_in_header(self) -> None:
        ll_pos = self.table.index("Val log_loss")
        acc_pos = self.table.index("Val acc")
        assert ll_pos < acc_pos

    def test_contains_eval_table_label(self) -> None:
        assert "eval" in self.table

    def test_b0_flagged_not_exploratory(self) -> None:
        # B0 is not exploratory — Expl column should show N for B0
        lines = self.table.split("\n")
        b0_line = next(l for l in lines if l.startswith("| B0 "))
        assert "| N |" in b0_line


# ---------------------------------------------------------------------------
# K. render_validation_table
# ---------------------------------------------------------------------------

class TestRenderValidationTable:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.broad_primary = filter_broad_primary_baselines(self.baselines)
        self.table = render_validation_table(self.broad_primary)

    def test_returns_string(self) -> None:
        assert isinstance(self.table, str)

    def test_b0_excluded(self) -> None:
        # B0 should not appear in any data row (may appear in note text)
        data_lines = [
            l for l in self.table.split("\n")
            if l.startswith("| B")
        ]
        ids_in_rows = [l.split("|")[1].strip() for l in data_lines]
        assert "B0" not in ids_in_rows

    def test_b1_b2_b3_present(self) -> None:
        for bid in ["B1", "B2", "B3"]:
            assert bid in self.table

    def test_contains_not_directly_comparable_note(self) -> None:
        assert "not directly comparable" in self.table

    def test_sorted_by_log_loss(self) -> None:
        data_lines = [
            l for l in self.table.split("\n")
            if l.startswith("| B") and "|" in l
        ]
        ids_in_order = [l.split("|")[1].strip() for l in data_lines]
        lls_by_id = {
            b["baseline_id"]: get_split_metrics(b, "val").get("log_loss", math.inf)
            for b in self.baselines
        }
        ordered_lls = [lls_by_id.get(bid, math.inf) for bid in ids_in_order]
        assert ordered_lls == sorted(ordered_lls)

    def test_log_loss_column_before_accuracy(self) -> None:
        ll_pos = self.table.index("Val log_loss")
        acc_pos = self.table.index("Val acc")
        assert ll_pos < acc_pos

    def test_macro_f1_column_present(self) -> None:
        assert "macro_f1" in self.table


# ---------------------------------------------------------------------------
# L. render_confusion_matrix
# ---------------------------------------------------------------------------

class TestRenderConfusionMatrix:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.b3 = next(b for b in self.baselines if b["baseline_id"] == "B3")

    def test_returns_string(self) -> None:
        result = render_confusion_matrix(self.b3, "val")
        assert isinstance(result, str)

    def test_contains_class_labels(self) -> None:
        result = render_confusion_matrix(self.b3, "val")
        assert "BLACK_WIN" in result
        assert "DRAW" in result
        assert "WHITE_WIN" in result

    def test_contains_baseline_id(self) -> None:
        result = render_confusion_matrix(self.b3, "val")
        assert "B3" in result

    def test_contains_split_name(self) -> None:
        result = render_confusion_matrix(self.b3, "val")
        assert "val" in result

    def test_missing_cm_returns_message(self) -> None:
        b = {"baseline_id": "X", "metrics": {"val": {}}}
        result = render_confusion_matrix(b, "val")
        assert "not available" in result.lower()

    def test_table_format(self) -> None:
        result = render_confusion_matrix(self.b3, "val")
        # Should have markdown table rows
        assert "|" in result


# ---------------------------------------------------------------------------
# M. render_signal_decomposition
# ---------------------------------------------------------------------------

class TestRenderSignalDecomposition:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.section = render_signal_decomposition(self.baselines)

    def test_returns_string(self) -> None:
        assert isinstance(self.section, str)

    def test_contains_b1_b2_b3(self) -> None:
        assert "B1" in self.section
        assert "B2" in self.section
        assert "B3" in self.section

    def test_contains_table_header(self) -> None:
        assert "Val log_loss" in self.section

    def test_contains_delta_symbol(self) -> None:
        assert "Δ" in self.section

    def test_references_log_loss_as_primary_metric(self) -> None:
        assert "log_loss" in self.section.lower() or "log_loss" in self.section

    def test_b1_log_loss_value_present(self) -> None:
        # B1 has val_ll=0.885
        assert "0.8850" in self.section


# ---------------------------------------------------------------------------
# N. render_test_snapshot
# ---------------------------------------------------------------------------

class TestRenderTestSnapshot:
    def setup_method(self) -> None:
        self.baselines = get_baselines(_make_payload())
        self.snap = render_test_snapshot(self.baselines)

    def test_returns_string(self) -> None:
        assert isinstance(self.snap, str)

    def test_b0_excluded(self) -> None:
        data_lines = [l for l in self.snap.split("\n") if l.startswith("| B")]
        ids = [l.split("|")[1].strip() for l in data_lines]
        assert "B0" not in ids

    def test_b1_b2_b3_present(self) -> None:
        for bid in ["B1", "B2", "B3"]:
            assert bid in self.snap

    def test_test_log_loss_column_present(self) -> None:
        assert "Test log_loss" in self.snap

    def test_record_keeping_note_present(self) -> None:
        assert "record-keeping" in self.snap


# ---------------------------------------------------------------------------
# O. render_baseline_evaluation_report — key phrase tests
# ---------------------------------------------------------------------------

class TestRenderBaselineEvaluationReport:
    def setup_method(self) -> None:
        self.payload = _make_payload()
        self.report = render_baseline_evaluation_report(self.payload)

    def test_returns_string(self) -> None:
        assert isinstance(self.report, str)

    def test_key_phrase_chess_is_the_testbed(self) -> None:
        assert "Chess is the testbed" in self.report

    def test_key_phrase_human_strategy_reasoning(self) -> None:
        assert "human strategy/reasoning" in self.report

    def test_key_phrase_not_directly_comparable(self) -> None:
        assert "not directly comparable" in self.report

    def test_key_phrase_best_broad_primary_baseline(self) -> None:
        assert "best broad primary baseline" in self.report.lower()

    def test_key_phrase_ticket_53b(self) -> None:
        assert "5.3B" in self.report

    def test_key_phrase_labels(self) -> None:
        assert "ML/REPORTING | D2 | IMPLEMENTATION" in self.report

    def test_key_phrase_pilot(self) -> None:
        assert "pilot" in self.report

    def test_contains_b3_val_log_loss(self) -> None:
        # B3 val_ll=0.853 in the fixture
        assert "0.8530" in self.report

    def test_contains_dataset_id(self) -> None:
        assert "test_dataset_v1" in self.report

    def test_contains_version_tag(self) -> None:
        assert "test_v1" in self.report

    def test_contains_inventory_section(self) -> None:
        assert "Baseline Inventory" in self.report

    def test_contains_validation_section(self) -> None:
        assert "Validation Comparison" in self.report

    def test_contains_signal_section(self) -> None:
        assert "Signal Decomposition" in self.report

    def test_contains_diagnostic_section(self) -> None:
        assert "Diagnostic" in self.report

    def test_contains_test_snapshot_section(self) -> None:
        assert "Test Snapshot" in self.report

    def test_contains_eval_section(self) -> None:
        assert "Eval Baselines" in self.report

    def test_contains_key_findings_section(self) -> None:
        assert "Key Findings" in self.report

    def test_b0_not_in_validation_table_rows(self) -> None:
        # B0 should not be in a data row (| B0 | ...) of the validation table
        lines = self.report.split("\n")
        data_rows = [l for l in lines if l.startswith("| B0 |")]
        # All B0 rows should be in inventory only — check that
        # the validation table header does NOT precede any B0 row
        val_header_idx = next(
            (i for i, l in enumerate(lines) if "Validation Comparison" in l), -1
        )
        test_header_idx = next(
            (i for i, l in enumerate(lines) if "Test Snapshot" in l), len(lines)
        )
        val_section_lines = lines[val_header_idx:test_header_idx]
        b0_in_val = any(l.startswith("| B0 |") for l in val_section_lines)
        assert not b0_in_val

    def test_date_present(self) -> None:
        assert "2026-01-01" in self.report

    def test_markdown_headers(self) -> None:
        assert self.report.startswith("# Baseline Evaluation Report")

    def test_recommended_next_step_present(self) -> None:
        assert "Recommended Next Step" in self.report


# ---------------------------------------------------------------------------
# P. write_text
# ---------------------------------------------------------------------------

class TestWriteText:
    def test_creates_file(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        write_text(p, "hello world")
        assert p.exists()

    def test_content_matches(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        write_text(p, "hello world")
        assert p.read_text(encoding="utf-8") == "hello world"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        p = tmp_path / "a" / "b" / "c" / "report.md"
        write_text(p, "test")
        assert p.exists()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        write_text(str(p), "test")
        assert p.exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        p = tmp_path / "report.md"
        write_text(p, "first")
        write_text(p, "second")
        assert p.read_text(encoding="utf-8") == "second"


# ---------------------------------------------------------------------------
# Integration: round-trip load → render
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_load_and_render(self, tmp_path: Path) -> None:
        payload = _make_payload()
        p = tmp_path / "results.json"
        p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(p)
        report = render_baseline_evaluation_report(loaded)
        assert "Chess is the testbed" in report

    def test_load_render_write(self, tmp_path: Path) -> None:
        payload = _make_payload()
        json_p = tmp_path / "results.json"
        json_p.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_baseline_results(json_p)
        report = render_baseline_evaluation_report(loaded)
        out_p = tmp_path / "report.md"
        write_text(out_p, report)
        assert out_p.exists()
        content = out_p.read_text(encoding="utf-8")
        assert "ML/REPORTING | D2 | IMPLEMENTATION" in content
