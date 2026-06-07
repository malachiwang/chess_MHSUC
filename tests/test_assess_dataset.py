"""
tests/test_assess_dataset.py — Tests for assess_dataset.py

All tests use synthetic Polars DataFrames only.
No real data files are read.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.assess_dataset import (
    _col_stats,
    _result_dist,
    _s,
    assess_checkpoint_distribution,
    assess_clock_distribution,
    assess_eval_distribution,
    assess_leakage_safety,
    assess_null_counts,
    assess_rating_distribution,
    assess_slice_distributions,
    assess_target_distribution,
    build_assessment_report,
    build_baseline_readiness,
    compare_broad_eval,
    main,
    print_assessment_summary,
    render_markdown_report,
)

# ---------------------------------------------------------------------------
# Synthetic schema matching feature table (40 cols)
# ---------------------------------------------------------------------------

_FT_SCHEMA = {
    "game_id": pl.String,
    "selected_position_type": pl.String,
    "move_number": pl.Int64,
    "side_to_move_next": pl.String,
    "phase": pl.String,
    "checkpoint_index": pl.Int64,
    "phase_index": pl.Int64,
    "white_elo": pl.Int64,
    "black_elo": pl.Int64,
    "elo_diff": pl.Int64,
    "avg_elo": pl.Float64,
    "white_clock_s": pl.Int64,
    "black_clock_s": pl.Int64,
    "clock_diff_s": pl.Int64,
    "white_clock_s_capped": pl.Int64,
    "black_clock_s_capped": pl.Int64,
    "white_clock_frac": pl.Float64,
    "black_clock_frac": pl.Float64,
    "clock_diff_frac": pl.Float64,
    "white_low_60": pl.Boolean,
    "black_low_60": pl.Boolean,
    "white_low_30": pl.Boolean,
    "black_low_30": pl.Boolean,
    "white_low_10": pl.Boolean,
    "black_low_10": pl.Boolean,
    "clock_anomaly": pl.Boolean,
    "eval_cp": pl.Int64,
    "eval_cp_clipped": pl.Int64,
    "eval_mate": pl.Int64,
    "eval_mate_abs": pl.Int64,
    "eval_white_winning": pl.Boolean,
    "is_mate_eval": pl.Boolean,
    "has_eval": pl.Boolean,
    "is_last_checkpoint": pl.Boolean,
    "is_time_forfeit": pl.Boolean,
    "duplicate_ply_checkpoint": pl.Boolean,
    "white_to_move_next": pl.Boolean,
    "result_class": pl.String,
    "white_result_numeric": pl.Float64,
    "termination": pl.String,
}


def _make_row(
    game_id: str = "g1",
    selected_position_type: str = "move_10",
    move_number: int = 10,
    side_to_move_next: str = "white",
    phase: str = "opening",
    checkpoint_index: int = 0,
    phase_index: int = 0,
    white_elo: int = 1500,
    black_elo: int = 1500,
    elo_diff: int = 0,
    avg_elo: float = 1500.0,
    white_clock_s: int = 400,
    black_clock_s: int = 400,
    clock_diff_s: int = 0,
    white_clock_s_capped: int = 400,
    black_clock_s_capped: int = 400,
    white_clock_frac: float = 0.667,
    black_clock_frac: float = 0.667,
    clock_diff_frac: float = 0.0,
    white_low_60: bool = False,
    black_low_60: bool = False,
    white_low_30: bool = False,
    black_low_30: bool = False,
    white_low_10: bool = False,
    black_low_10: bool = False,
    clock_anomaly: bool = False,
    eval_cp: int | None = None,
    eval_cp_clipped: int | None = None,
    eval_mate: int | None = None,
    eval_mate_abs: int | None = None,
    eval_white_winning: bool | None = None,
    is_mate_eval: bool = False,
    has_eval: bool = False,
    is_last_checkpoint: bool = False,
    is_time_forfeit: bool = False,
    duplicate_ply_checkpoint: bool = False,
    white_to_move_next: bool = True,
    result_class: str = "WHITE_WIN",
    white_result_numeric: float = 1.0,
    termination: str = "Normal",
) -> dict:
    return {k: v for k, v in locals().items()}


def _df(*rows: dict) -> pl.DataFrame:
    """Build a typed DataFrame from a sequence of row dicts."""
    if not rows:
        return pl.DataFrame(schema=_FT_SCHEMA)
    return pl.DataFrame(list(rows), schema=_FT_SCHEMA)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_s_passthrough_int(self):
        assert _s(42) == 42

    def test_s_passthrough_float(self):
        assert _s(3.14) == 3.14

    def test_s_none(self):
        assert _s(None) is None

    def test_s_nan_to_none(self):
        assert _s(float("nan")) is None

    def test_col_stats_basic(self):
        s = pl.Series("x", [1.0, 2.0, 3.0, 4.0])
        stats = _col_stats(s)
        assert stats["min"] == 1.0
        assert stats["max"] == 4.0
        assert stats["null_count"] == 0

    def test_col_stats_empty(self):
        s = pl.Series("x", [], dtype=pl.Float64)
        stats = _col_stats(s)
        assert stats["min"] is None
        assert stats["null_count"] == 0

    def test_result_dist_basic(self):
        df = _df(
            _make_row(result_class="WHITE_WIN"),
            _make_row(result_class="WHITE_WIN"),
            _make_row(result_class="DRAW"),
        )
        dist = _result_dist(df, "result_class")
        assert dist["counts"]["WHITE_WIN"] == 2
        assert dist["counts"]["DRAW"] == 1
        assert abs(dist["pct"]["WHITE_WIN"] - 66.67) < 0.1

    def test_result_dist_empty(self):
        df = _df()
        dist = _result_dist(df, "result_class")
        assert dist["counts"] == {}
        assert dist["pct"] == {}


# ---------------------------------------------------------------------------
# A. Target distribution
# ---------------------------------------------------------------------------

class TestAssessTargetDistribution:
    def test_basic_counts(self):
        df = _df(
            _make_row(result_class="WHITE_WIN", white_result_numeric=1.0),
            _make_row(result_class="BLACK_WIN", white_result_numeric=0.0),
            _make_row(result_class="DRAW", white_result_numeric=0.5),
        )
        result = assess_target_distribution(df)
        assert result["n_rows"] == 3
        assert result["result_class"]["counts"]["WHITE_WIN"] == 1
        assert result["result_class"]["counts"]["DRAW"] == 1
        assert "white_result_numeric" in result

    def test_n_rows_matches(self):
        rows = [_make_row(game_id=str(i)) for i in range(10)]
        df = _df(*rows)
        result = assess_target_distribution(df)
        assert result["n_rows"] == 10


# ---------------------------------------------------------------------------
# B. Rating distribution
# ---------------------------------------------------------------------------

class TestAssessRatingDistribution:
    def test_required_keys(self):
        df = _df(
            _make_row(white_elo=1400, black_elo=1600, avg_elo=1500.0, elo_diff=-200),
            _make_row(white_elo=1600, black_elo=1400, avg_elo=1500.0, elo_diff=200),
        )
        result = assess_rating_distribution(df)
        for key in ["white_elo", "black_elo", "avg_elo", "elo_diff"]:
            assert key in result
            assert "mean" in result[key]

    def test_avg_elo_mean(self):
        df = _df(
            _make_row(avg_elo=1000.0),
            _make_row(avg_elo=2000.0),
        )
        result = assess_rating_distribution(df)
        assert result["avg_elo"]["mean"] == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# C. Clock distribution
# ---------------------------------------------------------------------------

class TestAssessClockDistribution:
    def test_required_keys(self):
        df = _df(_make_row())
        result = assess_clock_distribution(df)
        for key in ["white_clock_s", "black_clock_s", "white_clock_frac", "black_clock_frac",
                    "clock_diff_frac", "clock_anomaly_n", "white_low_60", "black_low_60",
                    "white_low_10", "black_low_10"]:
            assert key in result

    def test_low_time_flag_rate(self):
        df = _df(
            _make_row(white_low_60=True),
            _make_row(white_low_60=True),
            _make_row(white_low_60=False),
        )
        result = assess_clock_distribution(df)
        assert result["white_low_60"]["n_true"] == 2
        assert abs(result["white_low_60"]["pct"] - 66.67) < 0.1

    def test_clock_anomaly_count(self):
        df = _df(
            _make_row(clock_anomaly=True),
            _make_row(clock_anomaly=False),
        )
        result = assess_clock_distribution(df)
        assert result["clock_anomaly_n"] == 1


# ---------------------------------------------------------------------------
# D. Eval distribution
# ---------------------------------------------------------------------------

class TestAssessEvalDistribution:
    def test_no_eval_rows(self):
        df = _df(_make_row(has_eval=False))
        result = assess_eval_distribution(df)
        assert result["has_eval_n"] == 0
        assert result["eval_coverage_pct"] == 0.0

    def test_eval_bins_present(self):
        df = _df(
            _make_row(has_eval=True, eval_cp=100, eval_cp_clipped=100, is_mate_eval=False),
            _make_row(has_eval=True, eval_cp=-600, eval_cp_clipped=-600, is_mate_eval=False),
        )
        result = assess_eval_distribution(df)
        assert "eval_bins" in result
        assert "le_neg500" in result["eval_bins"]
        assert result["eval_bins"]["le_neg500"]["n"] == 1

    def test_eval_coverage_pct(self):
        df = _df(
            _make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50),
            _make_row(has_eval=False),
        )
        result = assess_eval_distribution(df)
        assert result["eval_coverage_pct"] == 50.0


# ---------------------------------------------------------------------------
# E. Checkpoint distribution
# ---------------------------------------------------------------------------

class TestAssessCheckpointDistribution:
    def test_basic(self):
        df = _df(
            _make_row(game_id="g1", selected_position_type="move_10"),
            _make_row(game_id="g1", selected_position_type="last", is_last_checkpoint=True),
            _make_row(game_id="g2", selected_position_type="move_10"),
        )
        result = assess_checkpoint_distribution(df)
        assert result["total_rows"] == 3
        assert result["total_games"] == 2
        assert result["checkpoint_breakdown"]["move_10"]["n_rows"] == 2
        assert result["checkpoint_breakdown"]["move_10"]["n_games"] == 2

    def test_duplicate_flag_count(self):
        df = _df(
            _make_row(game_id="g1", duplicate_ply_checkpoint=True),
            _make_row(game_id="g1", duplicate_ply_checkpoint=True),
            _make_row(game_id="g2", duplicate_ply_checkpoint=False),
        )
        result = assess_checkpoint_distribution(df)
        assert result["duplicate_ply_checkpoint_n"] == 2


# ---------------------------------------------------------------------------
# F. Null counts
# ---------------------------------------------------------------------------

class TestAssessNullCounts:
    def test_no_nulls(self):
        df = _df(_make_row())
        result = assess_null_counts(df)
        assert result["white_elo"]["null_count"] == 0

    def test_nullable_eval_cp(self):
        df = _df(
            _make_row(eval_cp=None, eval_cp_clipped=None, has_eval=False),
        )
        result = assess_null_counts(df)
        assert result["eval_cp"]["null_count"] == 1

    def test_all_columns_present(self):
        df = _df(_make_row())
        result = assess_null_counts(df)
        for col in df.columns:
            assert col in result


# ---------------------------------------------------------------------------
# G. Slice distributions
# ---------------------------------------------------------------------------

class TestAssessSliceDistributions:
    def test_is_time_forfeit_rate(self):
        df = _df(
            _make_row(is_time_forfeit=True, termination="Time forfeit"),
            _make_row(is_time_forfeit=False, termination="Normal"),
        )
        result = assess_slice_distributions(df)
        assert result["is_time_forfeit"]["n_true"] == 1
        assert result["is_time_forfeit"]["pct"] == 50.0

    def test_termination_distribution(self):
        df = _df(
            _make_row(termination="Normal"),
            _make_row(termination="Normal"),
            _make_row(termination="Time forfeit"),
        )
        result = assess_slice_distributions(df)
        assert result["termination"]["counts"]["Normal"] == 2
        assert result["termination"]["counts"]["Time forfeit"] == 1


# ---------------------------------------------------------------------------
# H. Leakage safety
# ---------------------------------------------------------------------------

class TestAssessLeakageSafety:
    def test_clean_table_is_safe(self):
        df = _df(_make_row())
        result = assess_leakage_safety(df)
        assert result["leakage_safe"] is True
        assert result["forbidden_cols_found"] == []

    def test_forbidden_col_detected(self):
        df = _df(_make_row()).with_columns(pl.lit(0).alias("n_plies_total"))
        result = assess_leakage_safety(df)
        assert result["leakage_safe"] is False
        assert "n_plies_total" in result["forbidden_cols_found"]

    def test_label_and_slice_cols_present(self):
        df = _df(_make_row())
        result = assess_leakage_safety(df)
        assert result["result_class_present"] is True
        assert result["termination_present"] is True
        assert result["game_id_present"] is True


# ---------------------------------------------------------------------------
# I. Compare broad vs. eval
# ---------------------------------------------------------------------------

class TestCompareBroadEval:
    def test_required_keys(self):
        df_broad = _df(_make_row(game_id="g1"), _make_row(game_id="g2", has_eval=True))
        df_eval = _df(_make_row(game_id="g2", has_eval=True))
        result = compare_broad_eval(df_broad, df_eval)
        for key in ["broad_n", "eval_n", "avg_elo_broad", "avg_elo_eval",
                    "result_class_broad", "result_class_eval", "eval_by_checkpoint"]:
            assert key in result

    def test_row_counts(self):
        df_broad = _df(_make_row(), _make_row(game_id="g2"))
        df_eval = _df(_make_row(game_id="g2"))
        result = compare_broad_eval(df_broad, df_eval)
        assert result["broad_n"] == 2
        assert result["eval_n"] == 1


# ---------------------------------------------------------------------------
# J. Build assessment report
# ---------------------------------------------------------------------------

class TestBuildAssessmentReport:
    def _make_dfs(self):
        df_broad = _df(
            *[_make_row(game_id=f"g{i}") for i in range(10)]
        )
        df_eval = _df(
            *[_make_row(game_id=f"g{i}", has_eval=True, eval_cp=50, eval_cp_clipped=50)
              for i in range(3)]
        )
        return df_broad, df_eval

    def test_required_top_level_keys(self):
        df_broad, df_eval = self._make_dfs()
        report = build_assessment_report(
            df_broad=df_broad,
            df_eval=df_eval,
            feature_metadata=None,
            input_paths={},
            output_paths={},
            version_tag="test_v1",
        )
        for key in [
            "version_tag", "timestamp_utc", "target_distribution_broad",
            "target_distribution_eval", "rating_distribution_broad",
            "clock_distribution_broad", "eval_distribution_broad",
            "checkpoint_distribution_broad", "null_counts_broad",
            "slice_distributions_broad", "leakage_safety_broad",
            "leakage_safety_eval", "broad_vs_eval",
        ]:
            assert key in report, f"Missing key: {key}"

    def test_version_tag_propagated(self):
        df_broad, df_eval = self._make_dfs()
        report = build_assessment_report(
            df_broad=df_broad, df_eval=df_eval,
            feature_metadata=None, input_paths={}, output_paths={},
            version_tag="my_tag",
        )
        assert report["version_tag"] == "my_tag"


# ---------------------------------------------------------------------------
# K. Baseline readiness
# ---------------------------------------------------------------------------

class TestBuildBaselineReadiness:
    def _minimal_report(self, broad_n=6000, eval_n=600, games=1200,
                        draw_pct=5.0, eval_cov=10.0, leakage_safe=True):
        """Build a minimal mock report dict for readiness checks."""
        return {
            "target_distribution_broad": {
                "n_rows": broad_n,
                "result_class": {"pct": {"WHITE_WIN": 47.0, "BLACK_WIN": 48.0, "DRAW": draw_pct}},
            },
            "target_distribution_eval": {"n_rows": eval_n},
            "checkpoint_distribution_broad": {"total_games": games, "duplicate_ply_checkpoint_n": 0},
            "eval_distribution_broad": {"eval_coverage_pct": eval_cov, "has_eval_n": int(broad_n * eval_cov / 100)},
            "null_counts_broad": {
                "white_elo": {"null_count": 0},
                "result_class": {"null_count": 0},
            },
            "null_counts_eval": {},
            "leakage_safety_broad": {"leakage_safe": leakage_safe, "forbidden_cols_found": []},
            "leakage_safety_eval": {"leakage_safe": leakage_safe, "forbidden_cols_found": []},
            "broad_vs_eval": {"avg_elo_broad": 1500.0, "avg_elo_eval": 1520.0,
                              "broad_games": games, "eval_games": 300},
        }

    def test_all_pass(self):
        report = self._minimal_report()
        readiness = build_baseline_readiness(report)
        assert readiness["all_checks_pass"] is True

    def test_fails_if_broad_too_small(self):
        report = self._minimal_report(broad_n=100)
        readiness = build_baseline_readiness(report)
        assert readiness["checks"]["broad_rows_sufficient"] is False
        assert readiness["all_checks_pass"] is False

    def test_fails_if_no_draw_class(self):
        report = self._minimal_report(draw_pct=0.0)
        readiness = build_baseline_readiness(report)
        assert readiness["checks"]["draw_class_present"] is False


# ---------------------------------------------------------------------------
# L. Render Markdown report
# ---------------------------------------------------------------------------

class TestRenderMarkdownReport:
    def _make_report(self):
        rows = [_make_row(game_id=str(i), result_class="WHITE_WIN") for i in range(5)]
        rows += [_make_row(game_id=str(i + 5), result_class="BLACK_WIN") for i in range(5)]
        df_broad = _df(*rows)
        df_eval = _df(_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50))
        return build_assessment_report(
            df_broad=df_broad, df_eval=df_eval,
            feature_metadata=None, input_paths={}, output_paths={},
            version_tag="test_v1",
        )

    def test_returns_string(self):
        report = self._make_report()
        md = render_markdown_report(report)
        assert isinstance(md, str)

    def test_contains_ticket_header(self):
        report = self._make_report()
        md = render_markdown_report(report)
        assert "Ticket 4.1B" in md

    def test_contains_version_tag(self):
        report = self._make_report()
        md = render_markdown_report(report)
        assert "test_v1" in md

    def test_contains_leakage_section(self):
        report = self._make_report()
        md = render_markdown_report(report)
        assert "Leakage" in md

    def test_contains_baseline_readiness(self):
        report = self._make_report()
        md = render_markdown_report(report)
        assert "Baseline Readiness" in md


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestAssessDatasetCLI:
    def _write_parquet(self, tmp_path: Path, rows: list[dict], name: str) -> Path:
        df = _df(*rows)
        p = tmp_path / name
        df.write_parquet(p)
        return p

    def test_exit_code_zero(self, tmp_path):
        broad_path = self._write_parquet(
            tmp_path,
            [_make_row(game_id=str(i)) for i in range(5)],
            "broad.parquet",
        )
        eval_path = self._write_parquet(
            tmp_path,
            [_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50)],
            "eval.parquet",
        )
        out_dir = tmp_path / "out"
        rc = main([
            "--feature-broad", str(broad_path),
            "--feature-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", "cli_test",
        ])
        assert rc == 0

    def test_markdown_file_created(self, tmp_path):
        broad_path = self._write_parquet(
            tmp_path,
            [_make_row(game_id=str(i)) for i in range(5)],
            "broad.parquet",
        )
        eval_path = self._write_parquet(
            tmp_path,
            [_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50)],
            "eval.parquet",
        )
        out_dir = tmp_path / "out"
        main([
            "--feature-broad", str(broad_path),
            "--feature-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", "cli_test",
        ])
        md_path = out_dir / "phase_4_1b_feature_dataset_assessment.md"
        assert md_path.exists()

    def test_json_sidecar_created(self, tmp_path):
        broad_path = self._write_parquet(
            tmp_path,
            [_make_row(game_id=str(i)) for i in range(5)],
            "broad.parquet",
        )
        eval_path = self._write_parquet(
            tmp_path,
            [_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50)],
            "eval.parquet",
        )
        out_dir = tmp_path / "out"
        main([
            "--feature-broad", str(broad_path),
            "--feature-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", "cli_test",
        ])
        json_path = tmp_path / "assessment_cli_test.json"
        assert json_path.exists()

    def test_json_is_valid(self, tmp_path):
        broad_path = self._write_parquet(
            tmp_path,
            [_make_row(game_id=str(i)) for i in range(5)],
            "broad.parquet",
        )
        eval_path = self._write_parquet(
            tmp_path,
            [_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50)],
            "eval.parquet",
        )
        out_dir = tmp_path / "out"
        main([
            "--feature-broad", str(broad_path),
            "--feature-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", "cli_test",
        ])
        json_path = tmp_path / "assessment_cli_test.json"
        with open(json_path) as fh:
            data = json.load(fh)
        assert data["version_tag"] == "cli_test"

    def test_no_username_cols_in_output(self, tmp_path):
        broad_path = self._write_parquet(
            tmp_path,
            [_make_row(game_id=str(i)) for i in range(5)],
            "broad.parquet",
        )
        eval_path = self._write_parquet(
            tmp_path,
            [_make_row(has_eval=True, eval_cp=50, eval_cp_clipped=50)],
            "eval.parquet",
        )
        out_dir = tmp_path / "out"
        main([
            "--feature-broad", str(broad_path),
            "--feature-eval", str(eval_path),
            "--output-dir", str(out_dir),
            "--version-tag", "cli_test",
        ])
        json_path = tmp_path / "assessment_cli_test.json"
        with open(json_path) as fh:
            text = fh.read()
        for username_col in ["white_username", "black_username", "WhiteUsername", "BlackUsername"]:
            assert username_col not in text
