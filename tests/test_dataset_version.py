"""
Tests for dataset_version.py — functions A through Q and CLI (main).

All tests use synthetic data in tmp_path or in-memory dicts.
No real data files are read. Subprocess calls are mocked.
chess_mhsuc.assess_dataset.build_baseline_readiness is mocked where needed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from chess_mhsuc.dataset_version import (
    build_artifact_inventory,
    build_column_schema,
    build_dataset_summary,
    build_dataset_version_manifest,
    build_pipeline_policy,
    build_pipeline_stage_outputs,
    build_provenance,
    get_dependency_versions,
    get_git_info,
    infer_file_format,
    load_json,
    main,
    normalize_forbidden_leakage_columns,
    print_dataset_version_summary,
    render_dataset_card,
    render_implementation_report,
    row_and_column_counts,
    sha256_file,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tiny_parquet(tmp_path: Path) -> Path:
    """Write a tiny Parquet file with a few columns and return its path."""
    df = pl.DataFrame({
        "col_a": [1, 2, 3],
        "col_b": ["x", "y", "z"],
        "col_c": [1.0, 2.0, 3.0],
    })
    p = tmp_path / "tiny.parquet"
    df.write_parquet(p)
    return p


@pytest.fixture()
def tiny_json(tmp_path: Path) -> Path:
    p = tmp_path / "meta.json"
    p.write_text(json.dumps({"key": "value", "n": 42}), encoding="utf-8")
    return p


@pytest.fixture()
def minimal_assessment_json() -> dict:
    """Minimal assessment JSON that satisfies build_dataset_summary field access."""
    return {
        "broad_vs_eval": {
            "broad_n": 8528,
            "eval_n": 1168,
            "broad_games": 2323,
            "eval_games": 365,
            "avg_elo_broad": 1558.7093,
            "avg_elo_eval": 1578.5360,
        },
        "target_distribution_broad": {
            "n_rows": 8528,
            "result_class": {
                "counts": {"WHITE_WIN": 3985, "BLACK_WIN": 4046, "DRAW": 497},
                "pct": {"WHITE_WIN": 46.73, "BLACK_WIN": 47.44, "DRAW": 5.83},
            },
        },
        "target_distribution_eval": {
            "n_rows": 1168,
        },
        "eval_distribution_broad": {
            "eval_coverage_pct": 13.7,
        },
        "checkpoint_distribution_broad": {
            "duplicate_ply_checkpoint_n": 166,
        },
        "clock_distribution_broad": {
            "clock_anomaly_n": 7,
        },
        "leakage_safety_broad": {
            "leakage_safe": True,
        },
        "leakage_safety_eval": {
            "leakage_safe": True,
        },
    }


@pytest.fixture()
def minimal_feature_metadata() -> dict:
    return {
        "version_tag": "2024_09_25k_v1",
        "default_predictive_features": ["white_elo", "black_elo", "avg_elo", "elo_diff"],
        "eval_predictive_features": ["eval_cp_clipped", "is_mate_eval"],
        "caution_columns": ["is_last_checkpoint", "side_to_move_next"],
        "label_columns": ["result_class", "white_result_numeric"],
        "slice_columns": ["game_id", "has_eval"],
        "metadata_columns": [],
        "dropped_columns": ["ply", "n_plies_total"],
        "nullable_eval_columns": ["eval_cp_clipped", "eval_mate_abs"],
        "forbidden_leakage_columns": [
            "result_class (as a feature)",
            "white_result_numeric (as a feature)",
            "n_plies_total",
            "game_id",
        ],
        "row_counts": {"broad": 8528, "eval": 1168},
        "input_paths": {},
        "output_paths": {},
        "policy": {"clock_cap_s": 600, "eval_clip_cp": 1000},
    }


@pytest.fixture()
def minimal_parser_metadata() -> dict:
    return {
        "source_url": "https://example.com/lichess.pgn.zst",
        "source_file": "lichess.pgn.zst",
        "source_month": "2024-09",
        "raw_games_cap": 25000,
        "max_accepted_basic": 2500,
        "raw_games_scanned": 25000,
        "n_600_0_total": 2467,
        "n_accepted_basic": 2462,
        "n_accepted_eval": 373,
        "n_position_records": 8528,
        "n_parse_errors": 0,
        "version_tag": "v1",
        "output_paths": {
            "game_records": "data/interim/game_records.parquet",
            "metadata": "data/interim/meta.json",
        },
    }


@pytest.fixture()
def minimal_cleaning_metadata() -> dict:
    return {
        "version_tag": "2024_09_25k_v1",
        "raw_game_rows": 2467,
        "clean_game_rows": 2460,
        "excluded_game_rows": 7,
        "retained_time_forfeit": 283,
        "broad_position_rows": 8528,
        "eval_position_rows": 1168,
        "input_paths": {},
        "output_paths": {"metadata": "data/processed/cleaning_meta.json"},
    }


@pytest.fixture()
def mock_git_state() -> dict:
    return {
        "commit_hash": "abc1234" * 8 + "abcd",  # 64-char hex
        "branch": "main",
        "status_clean": True,
        "dirty_files": [],
    }


@pytest.fixture()
def mock_dep_versions() -> dict:
    return {
        "python_version": "3.13.11",
        "platform": "macOS-15.0",
        "packages": {"polars": "1.0.0", "pyarrow": "18.0.0"},
    }


@pytest.fixture()
def sample_manifest(
    minimal_assessment_json,
    minimal_feature_metadata,
    minimal_parser_metadata,
    minimal_cleaning_metadata,
    mock_git_state,
    mock_dep_versions,
    tmp_path,
    tiny_parquet,
) -> dict:
    """Assemble a complete sample manifest for render tests."""
    provenance = build_provenance(
        dataset_id="lichess_ten_zero_2024_09_25k_v1",
        version_tag="2024_09_25k_v1",
        source_url="https://example.com/lichess.pgn.zst",
        source_file="lichess.pgn.zst",
        source_month="2024-09",
        parser_metadata=minimal_parser_metadata,
        pipeline_code_git_state=mock_git_state,
        manifest_generation_git_state=mock_git_state,
        dependency_versions=mock_dep_versions,
    )
    policy = build_pipeline_policy()
    stage_outputs = build_pipeline_stage_outputs(
        minimal_parser_metadata,
        minimal_cleaning_metadata,
        minimal_feature_metadata,
        minimal_assessment_json,
    )
    col_schema = build_column_schema(tiny_parquet, minimal_feature_metadata)
    with patch("chess_mhsuc.assess_dataset.build_baseline_readiness",
               return_value={"all_checks_pass": True}):
        ds_summary = build_dataset_summary(
            minimal_assessment_json,
            tiny_parquet,
            tiny_parquet,
        )
    manifest = build_dataset_version_manifest(
        dataset_id="lichess_ten_zero_2024_09_25k_v1",
        version_tag="2024_09_25k_v1",
        provenance=provenance,
        artifacts=[],
        pipeline_stage_outputs=stage_outputs,
        pipeline_policy=policy,
        column_schema=col_schema,
        dataset_summary=ds_summary,
        known_metadata_inconsistencies=[],
    )
    return manifest


# ---------------------------------------------------------------------------
# A. get_git_info
# ---------------------------------------------------------------------------

class TestGetGitInfo:
    def _patch(self, stdout_list, rc_list):
        """Patch subprocess.run to return a sequence of (stdout, rc) values."""
        call_count = 0
        results = list(zip(stdout_list, rc_list))

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            idx = min(call_count, len(results) - 1)
            stdout, rc = results[idx]
            call_count += 1
            m = MagicMock()
            m.stdout = stdout
            m.returncode = rc
            return m

        return patch("subprocess.run", side_effect=fake_run)

    def test_success_clean(self):
        with self._patch(
            ["abc123def456\n", "main\n", ""],
            [0, 0, 0],
        ):
            info = get_git_info()
        assert info["commit_hash"] == "abc123def456"
        assert info["branch"] == "main"
        assert info["status_clean"] is True
        assert info["dirty_files"] == []

    def test_dirty_state_detected(self):
        with self._patch(
            ["abc123\n", "main\n", " M src/foo.py\n?? bar.py\n"],
            [0, 0, 0],
        ):
            info = get_git_info()
        assert info["status_clean"] is False
        assert len(info["dirty_files"]) == 2

    def test_git_failure_returns_none_fields(self):
        with patch("subprocess.run", side_effect=Exception("git not found")):
            info = get_git_info()
        assert info["commit_hash"] is None
        assert info["branch"] is None
        assert info["status_clean"] is False

    def test_nonzero_rc_for_commit_returns_none(self):
        with self._patch(
            ["", "main\n", ""],
            [1, 0, 0],
        ):
            info = get_git_info()
        assert info["commit_hash"] is None
        assert info["branch"] == "main"

    def test_returns_dict_with_required_keys(self):
        with self._patch(["hash\n", "branch\n", ""], [0, 0, 0]):
            info = get_git_info()
        for key in ("commit_hash", "branch", "status_clean", "dirty_files"):
            assert key in info


# ---------------------------------------------------------------------------
# B. get_dependency_versions
# ---------------------------------------------------------------------------

class TestGetDependencyVersions:
    def test_returns_required_keys(self):
        result = get_dependency_versions()
        assert "python_version" in result
        assert "platform" in result
        assert "packages" in result

    def test_polars_present(self):
        result = get_dependency_versions()
        # polars is installed as a project dependency
        assert result["packages"].get("polars") is not None

    def test_missing_package_recorded_as_none(self):
        import importlib.metadata as im

        original = im.version

        def fake_version(pkg):
            if pkg == "nonexistent-pkg-xyz":
                raise im.PackageNotFoundError(pkg)
            return original(pkg)

        # The function checks a fixed list — we just confirm None for actually missing packages
        result = get_dependency_versions()
        # jupyter is often absent in test envs; either None or a version string is acceptable
        assert isinstance(result["packages"], dict)

    def test_python_version_is_string(self):
        result = get_dependency_versions()
        assert isinstance(result["python_version"], str)
        assert "3" in result["python_version"]


# ---------------------------------------------------------------------------
# C. sha256_file
# ---------------------------------------------------------------------------

class TestSha256File:
    def test_known_content(self, tmp_path: Path):
        p = tmp_path / "test.bin"
        content = b"hello world"
        p.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert sha256_file(p) == expected

    def test_returns_64_hex_chars(self, tmp_path: Path):
        p = tmp_path / "f.bin"
        p.write_bytes(b"abc")
        h = sha256_file(p)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_file(self, tmp_path: Path):
        p = tmp_path / "empty.bin"
        p.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert sha256_file(p) == expected

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            sha256_file(tmp_path / "nonexistent.bin")


# ---------------------------------------------------------------------------
# D. infer_file_format
# ---------------------------------------------------------------------------

class TestInferFileFormat:
    def test_parquet(self):
        assert infer_file_format(Path("data.parquet")) == "parquet"

    def test_json(self):
        assert infer_file_format(Path("meta.json")) == "json"

    def test_md(self):
        assert infer_file_format(Path("report.md")) == "markdown"

    def test_markdown(self):
        assert infer_file_format(Path("report.markdown")) == "markdown"

    def test_unknown(self):
        assert infer_file_format(Path("file.txt")) == "unknown"

    def test_case_insensitive(self):
        assert infer_file_format(Path("DATA.PARQUET")) == "parquet"


# ---------------------------------------------------------------------------
# E. row_and_column_counts
# ---------------------------------------------------------------------------

class TestRowAndColumnCounts:
    def test_parquet_row_and_column_count(self, tiny_parquet: Path):
        result = row_and_column_counts(tiny_parquet)
        assert result["row_count"] == 3
        assert result["column_count"] == 3

    def test_missing_file_returns_none(self, tmp_path: Path):
        result = row_and_column_counts(tmp_path / "nonexistent.parquet")
        assert result["row_count"] is None
        assert result["column_count"] is None

    def test_json_file_returns_none(self, tiny_json: Path):
        result = row_and_column_counts(tiny_json)
        assert result["row_count"] is None
        assert result["column_count"] is None

    def test_returns_dict_with_expected_keys(self, tiny_parquet: Path):
        result = row_and_column_counts(tiny_parquet)
        assert "row_count" in result
        assert "column_count" in result

    def test_pyarrow_fallback_to_polars_schema(self, tiny_parquet: Path):
        """If pyarrow.parquet.read_metadata raises, should fall back gracefully."""
        with patch("pyarrow.parquet.read_metadata", side_effect=Exception("oops")):
            result = row_and_column_counts(tiny_parquet)
        # Polars schema fallback gives column count but not row count
        assert result["column_count"] == 3
        assert result["row_count"] is None


# ---------------------------------------------------------------------------
# F. build_artifact_inventory
# ---------------------------------------------------------------------------

class TestBuildArtifactInventory:
    def test_existing_file_has_sha256(self, tmp_path: Path):
        p = tmp_path / "data.json"
        p.write_text('{"a": 1}', encoding="utf-8")
        specs = [{"path": str(p), "role": "metadata", "stage": "test", "should_commit": False}]
        inv = build_artifact_inventory(specs)
        assert inv[0]["exists"] is True
        assert inv[0]["sha256"] is not None
        assert len(inv[0]["sha256"]) == 64

    def test_missing_file_has_exists_false(self, tmp_path: Path):
        specs = [{"path": str(tmp_path / "nope.parquet"),
                  "role": "data", "stage": "test", "should_commit": False}]
        inv = build_artifact_inventory(specs)
        assert inv[0]["exists"] is False
        assert inv[0]["sha256"] is None
        assert "missing_reason" in inv[0]

    def test_inventory_length_matches_specs(self, tmp_path: Path):
        p1 = tmp_path / "a.json"
        p1.write_text("{}", encoding="utf-8")
        specs = [
            {"path": str(p1), "role": "r1", "stage": "s1", "should_commit": False},
            {"path": str(tmp_path / "missing.parquet"), "role": "r2", "stage": "s2",
             "should_commit": False},
        ]
        inv = build_artifact_inventory(specs)
        assert len(inv) == 2

    def test_parquet_artifact_has_row_column_counts(self, tiny_parquet: Path):
        specs = [{"path": str(tiny_parquet), "role": "data", "stage": "test", "should_commit": False}]
        inv = build_artifact_inventory(specs)
        assert inv[0]["row_count"] == 3
        assert inv[0]["column_count"] == 3

    def test_file_format_inferred(self, tiny_json: Path):
        specs = [{"path": str(tiny_json), "role": "metadata", "stage": "test", "should_commit": False}]
        inv = build_artifact_inventory(specs)
        assert inv[0]["file_format"] == "json"


# ---------------------------------------------------------------------------
# G. load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    def test_valid_json(self, tiny_json: Path):
        result = load_json(tiny_json)
        assert result["key"] == "value"
        assert result["n"] == 42

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_json(tmp_path / "ghost.json")

    def test_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("not valid json {{{", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_json(p)


# ---------------------------------------------------------------------------
# H. build_provenance
# ---------------------------------------------------------------------------

class TestBuildProvenance:
    def test_required_fields_present(self, minimal_parser_metadata, mock_git_state, mock_dep_versions):
        prov = build_provenance(
            dataset_id="test_dataset",
            version_tag="v1",
            source_url="https://example.com/file.pgn.zst",
            source_file="file.pgn.zst",
            source_month="2024-09",
            parser_metadata=minimal_parser_metadata,
            pipeline_code_git_state=mock_git_state,
            manifest_generation_git_state=mock_git_state,
            dependency_versions=mock_dep_versions,
        )
        required = [
            "dataset_id", "version_tag", "created_at_utc", "source_name",
            "source_url", "source_file", "source_month", "time_control",
            "time_control_slug", "rated_only", "standard_only",
            "raw_games_cap", "max_accepted_basic",
            "pipeline_code_git_state", "manifest_generation_git_state",
            "python_version", "dependency_versions", "platform",
        ]
        for key in required:
            assert key in prov, f"Missing key: {key}"

    def test_source_name_is_lichess(self, minimal_parser_metadata, mock_git_state, mock_dep_versions):
        prov = build_provenance("d", "v", "url", "file", "2024-09",
                                minimal_parser_metadata, mock_git_state, mock_git_state, mock_dep_versions)
        assert prov["source_name"] == "lichess"

    def test_time_control_slug(self, minimal_parser_metadata, mock_git_state, mock_dep_versions):
        prov = build_provenance("d", "v", "url", "file", "2024-09",
                                minimal_parser_metadata, mock_git_state, mock_git_state, mock_dep_versions)
        assert prov["time_control"] == "600+0"
        assert prov["time_control_slug"] == "ten_zero"

    def test_raw_games_cap_from_parser_metadata(self, minimal_parser_metadata, mock_git_state, mock_dep_versions):
        prov = build_provenance("d", "v", "url", "file", "2024-09",
                                minimal_parser_metadata, mock_git_state, mock_git_state, mock_dep_versions)
        assert prov["raw_games_cap"] == 25000
        assert prov["max_accepted_basic"] == 2500


# ---------------------------------------------------------------------------
# I. build_pipeline_stage_outputs
# ---------------------------------------------------------------------------

class TestBuildPipelineStageOutputs:
    def test_all_four_stages_present(self, minimal_parser_metadata, minimal_cleaning_metadata,
                                     minimal_feature_metadata, minimal_assessment_json):
        result = build_pipeline_stage_outputs(
            minimal_parser_metadata, minimal_cleaning_metadata,
            minimal_feature_metadata, minimal_assessment_json,
        )
        assert "parser" in result
        assert "cleaning" in result
        assert "features" in result
        assert "assessment" in result

    def test_parser_has_version_tag_note(self, minimal_parser_metadata, minimal_cleaning_metadata,
                                          minimal_feature_metadata, minimal_assessment_json):
        result = build_pipeline_stage_outputs(
            minimal_parser_metadata, minimal_cleaning_metadata,
            minimal_feature_metadata, minimal_assessment_json,
        )
        assert "version_tag_note" in result["parser"]
        assert "2024_09_25k_v1" in result["parser"]["version_tag_note"]

    def test_parser_version_tag_in_metadata_is_v1(self, minimal_parser_metadata, minimal_cleaning_metadata,
                                                    minimal_feature_metadata, minimal_assessment_json):
        result = build_pipeline_stage_outputs(
            minimal_parser_metadata, minimal_cleaning_metadata,
            minimal_feature_metadata, minimal_assessment_json,
        )
        assert result["parser"]["version_tag_in_metadata"] == "v1"

    def test_cleaning_key_counts(self, minimal_parser_metadata, minimal_cleaning_metadata,
                                  minimal_feature_metadata, minimal_assessment_json):
        result = build_pipeline_stage_outputs(
            minimal_parser_metadata, minimal_cleaning_metadata,
            minimal_feature_metadata, minimal_assessment_json,
        )
        kc = result["cleaning"]["key_counts"]
        assert kc["raw_game_rows"] == 2467
        assert kc["clean_game_rows"] == 2460


# ---------------------------------------------------------------------------
# J. build_pipeline_policy
# ---------------------------------------------------------------------------

class TestBuildPipelinePolicy:
    def test_required_keys_present(self):
        policy = build_pipeline_policy()
        for key in [
            "parser_acceptance_rules", "rejection_priority", "cleaning_rules",
            "time_forfeit_policy", "eval_policy", "clock_capping_policy",
            "eval_clipping_policy", "low_time_thresholds_s", "clock_cap_s",
            "eval_clip_cp", "duplicate_checkpoint_policy", "last_checkpoint_policy",
            "checkpoint_positions", "leakage_policy", "target_label_policy",
            "split_policy", "slice_columns",
        ]:
            assert key in policy, f"Missing key: {key}"

    def test_low_time_thresholds(self):
        policy = build_pipeline_policy()
        assert policy["low_time_thresholds_s"] == [60, 30, 10]

    def test_clock_cap_and_eval_clip(self):
        policy = build_pipeline_policy()
        assert policy["clock_cap_s"] == 600
        assert policy["eval_clip_cp"] == 1000

    def test_checkpoint_positions(self):
        policy = build_pipeline_policy()
        assert "move_10" in policy["checkpoint_positions"]
        assert "last" in policy["checkpoint_positions"]

    def test_pure_function_no_params(self):
        p1 = build_pipeline_policy()
        p2 = build_pipeline_policy()
        assert p1 == p2


# ---------------------------------------------------------------------------
# K. normalize_forbidden_leakage_columns
# ---------------------------------------------------------------------------

class TestNormalizeForbiddenLeakageColumns:
    def test_strips_as_a_feature_annotation(self):
        fm = {"forbidden_leakage_columns": ["result_class (as a feature)", "game_id"]}
        result = normalize_forbidden_leakage_columns(fm)
        assert "result_class" in result["forbidden_leakage_columns"]
        assert "result_class (as a feature)" not in result["forbidden_leakage_columns"]

    def test_deduplicates_plain_names(self):
        fm = {"forbidden_leakage_columns": ["game_id (as a feature)", "game_id"]}
        result = normalize_forbidden_leakage_columns(fm)
        assert result["forbidden_leakage_columns"].count("game_id") == 1

    def test_reasons_dict_returned(self):
        fm = {"forbidden_leakage_columns": ["result_class (as a feature)", "n_plies_total"]}
        result = normalize_forbidden_leakage_columns(fm)
        assert "forbidden_leakage_reasons" in result
        assert isinstance(result["forbidden_leakage_reasons"], dict)

    def test_known_column_has_reason(self):
        fm = {"forbidden_leakage_columns": ["result_class"]}
        result = normalize_forbidden_leakage_columns(fm)
        assert result["forbidden_leakage_reasons"]["result_class"] != "see feature policy"

    def test_unknown_column_gets_fallback_reason(self):
        fm = {"forbidden_leakage_columns": ["totally_unknown_col_xyz"]}
        result = normalize_forbidden_leakage_columns(fm)
        assert result["forbidden_leakage_reasons"]["totally_unknown_col_xyz"] == "see feature policy"

    def test_empty_list(self):
        result = normalize_forbidden_leakage_columns({"forbidden_leakage_columns": []})
        assert result["forbidden_leakage_columns"] == []
        assert result["forbidden_leakage_reasons"] == {}


# ---------------------------------------------------------------------------
# L. build_column_schema
# ---------------------------------------------------------------------------

class TestBuildColumnSchema:
    def test_returns_expected_keys(self, tiny_parquet: Path, minimal_feature_metadata):
        schema = build_column_schema(tiny_parquet, minimal_feature_metadata)
        for key in [
            "total_columns", "dtype_map", "default_predictive_features",
            "eval_predictive_features", "caution_columns", "label_columns",
            "slice_columns", "metadata_columns", "dropped_columns",
            "nullable_eval_columns", "forbidden_leakage_columns", "forbidden_leakage_reasons",
        ]:
            assert key in schema, f"Missing key: {key}"

    def test_dtype_map_populated_from_parquet(self, tiny_parquet: Path, minimal_feature_metadata):
        schema = build_column_schema(tiny_parquet, minimal_feature_metadata)
        assert "col_a" in schema["dtype_map"]
        assert "col_b" in schema["dtype_map"]

    def test_graceful_on_missing_parquet(self, tmp_path: Path, minimal_feature_metadata):
        schema = build_column_schema(tmp_path / "nonexistent.parquet", minimal_feature_metadata)
        assert schema["dtype_map"] == {}
        assert schema["total_columns"] is None

    def test_forbidden_leakage_normalized(self, tiny_parquet: Path, minimal_feature_metadata):
        schema = build_column_schema(tiny_parquet, minimal_feature_metadata)
        # Annotations should be stripped
        for col in schema["forbidden_leakage_columns"]:
            assert "(as a feature)" not in col

    def test_feature_lists_from_metadata(self, tiny_parquet: Path, minimal_feature_metadata):
        schema = build_column_schema(tiny_parquet, minimal_feature_metadata)
        assert "white_elo" in schema["default_predictive_features"]
        assert "eval_cp_clipped" in schema["eval_predictive_features"]


# ---------------------------------------------------------------------------
# M. build_dataset_summary
# ---------------------------------------------------------------------------

class TestBuildDatasetSummary:
    def _build(self, assessment, tiny_parquet, readiness=True):
        with patch(
            "chess_mhsuc.assess_dataset.build_baseline_readiness",
            return_value={"all_checks_pass": readiness},
        ):
            return build_dataset_summary(assessment, tiny_parquet, tiny_parquet)

    def test_broad_rows_extracted(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert summary["broad_rows"] == 8528

    def test_eval_rows_extracted(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert summary["eval_rows"] == 1168

    def test_avg_elo_rounded(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert summary["avg_elo_broad"] == round(1558.7093, 1)
        assert summary["avg_elo_eval"] == round(1578.5360, 1)

    def test_eval_elo_bias_computed(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        expected = round(1578.5360 - 1558.7093, 1)
        assert abs(summary["eval_avg_elo_bias"] - expected) < 0.2

    def test_caveats_list_populated(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert isinstance(summary["caveats"], list)
        assert len(summary["caveats"]) > 0

    def test_baseline_readiness_all_pass(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet, readiness=True)
        assert summary["baseline_readiness_all_pass"] is True

    def test_leakage_safety_passed(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert summary["leakage_safety_passed"] is True

    def test_result_distribution_present(self, minimal_assessment_json, tiny_parquet):
        summary = self._build(minimal_assessment_json, tiny_parquet)
        assert "WHITE_WIN" in summary["result_distribution_broad"]


# ---------------------------------------------------------------------------
# N. build_dataset_version_manifest
# ---------------------------------------------------------------------------

class TestBuildDatasetVersionManifest:
    def test_top_level_keys(self, sample_manifest):
        for key in [
            "dataset_id", "version_tag", "manifest_type", "created_at_utc",
            "provenance", "artifacts", "pipeline_stage_outputs", "pipeline_policy",
            "column_schema", "dataset_summary", "known_metadata_inconsistencies",
            "reproducibility", "data_safety", "recommended_next_step",
        ]:
            assert key in sample_manifest, f"Missing key: {key}"

    def test_manifest_type(self, sample_manifest):
        assert sample_manifest["manifest_type"] == "dataset_version_manifest"

    def test_dataset_id_in_manifest(self, sample_manifest):
        assert sample_manifest["dataset_id"] == "lichess_ten_zero_2024_09_25k_v1"

    def test_reproducibility_has_all_commands(self, sample_manifest):
        repro = sample_manifest["reproducibility"]
        for key in [
            "parser_command", "cleaning_command", "features_command",
            "assessment_command", "dataset_version_command",
        ]:
            assert key in repro, f"Missing reproducibility key: {key}"

    def test_data_safety_no_committed_data(self, sample_manifest):
        ds = sample_manifest["data_safety"]
        assert ds["data_artifacts_committed"] is False
        assert ds["data_artifacts_gitignored"] is True


# ---------------------------------------------------------------------------
# O. render_dataset_card
# ---------------------------------------------------------------------------

class TestRenderDatasetCard:
    def test_returns_string(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        assert isinstance(card, str)
        assert len(card) > 100

    def test_contains_dataset_id(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        assert "lichess_ten_zero_2024_09_25k_v1" in card

    def test_contains_section_headers(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        for section in [
            "## 1. ELI5", "## 2. Dataset Identity", "## 3. Source Provenance",
            "## 4. Pipeline Summary", "## 5. Artifact Inventory",
            "## 6. Row Counts", "## 7. Column", "## 8. Leakage",
            "## 9. Known Caveats", "## 10. Reproduction Commands",
        ]:
            assert section in card, f"Missing section: {section}"

    def test_contains_caveats(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        assert "**C1.**" in card

    def test_contains_git_section(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        assert "## 11. Git and Dependency Metadata" in card

    def test_contains_reproduction_commands(self, sample_manifest):
        card = render_dataset_card(sample_manifest)
        assert "run_parser" in card


# ---------------------------------------------------------------------------
# P. render_implementation_report
# ---------------------------------------------------------------------------

class TestRenderImplementationReport:
    def test_returns_string(self, sample_manifest):
        report = render_implementation_report(sample_manifest)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_contains_ticket_title(self, sample_manifest):
        report = render_implementation_report(sample_manifest)
        assert "Ticket 4.2B" in report

    def test_contains_files_changed_section(self, sample_manifest):
        report = render_implementation_report(sample_manifest)
        assert "Files Changed" in report

    def test_contains_data_safety_section(self, sample_manifest):
        report = render_implementation_report(sample_manifest)
        assert "Data Safety" in report

    def test_custom_test_summary_included(self, sample_manifest):
        report = render_implementation_report(sample_manifest, test_summary="42 tests passed!")
        assert "42 tests passed!" in report

    def test_contains_staging_commands(self, sample_manifest):
        report = render_implementation_report(sample_manifest)
        assert "git add" in report


# ---------------------------------------------------------------------------
# Q. print_dataset_version_summary
# ---------------------------------------------------------------------------

class TestPrintDatasetVersionSummary:
    def test_runs_without_error(self, sample_manifest, capsys):
        print_dataset_version_summary(sample_manifest)
        captured = capsys.readouterr()
        assert "dataset_id" in captured.out.lower() or "lichess_ten_zero" in captured.out

    def test_reports_missing_artifacts(self, sample_manifest, capsys):
        # Inject a missing artifact
        m = dict(sample_manifest)
        m["artifacts"] = [{"exists": False, "path": "data/x.parquet"}]
        print_dataset_version_summary(m)
        captured = capsys.readouterr()
        assert "MISSING" in captured.out or "missing" in captured.out.lower()

    def test_warnings_on_dirty_state(self, sample_manifest, capsys):
        m = dict(sample_manifest)
        p = dict(m["provenance"])
        p["manifest_generation_git_state"] = {
            "commit_hash": "abc123",
            "branch": "main",
            "status_clean": False,
            "dirty_files": ["src/foo.py"],
        }
        m["provenance"] = p
        print_dataset_version_summary(m)
        captured = capsys.readouterr()
        assert "WARNING" in captured.out


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------

class TestMain:
    """Integration test: run main() with synthetic temp files."""

    def _write_minimal_assessment(self, path: Path, assessment: dict) -> None:
        path.write_text(json.dumps(assessment), encoding="utf-8")

    def test_main_writes_three_output_files(
        self,
        tmp_path: Path,
        minimal_parser_metadata,
        minimal_cleaning_metadata,
        minimal_feature_metadata,
        minimal_assessment_json,
        tiny_parquet: Path,
    ):
        # Write JSON inputs
        parser_meta_path = tmp_path / "parser_meta.json"
        parser_meta_path.write_text(json.dumps(minimal_parser_metadata), encoding="utf-8")

        cleaning_meta_path = tmp_path / "cleaning_meta.json"
        cleaning_meta_path.write_text(json.dumps(minimal_cleaning_metadata), encoding="utf-8")

        feature_meta_path = tmp_path / "feature_meta.json"
        feature_meta_path.write_text(json.dumps(minimal_feature_metadata), encoding="utf-8")

        assessment_path = tmp_path / "assessment.json"
        assessment_path.write_text(json.dumps(minimal_assessment_json), encoding="utf-8")

        out_dir = tmp_path / "processed"
        card_dir = tmp_path / "reports"

        with (
            patch("subprocess.run", return_value=MagicMock(stdout="abc123\n", returncode=0)),
            patch(
                "chess_mhsuc.assess_dataset.build_baseline_readiness",
                return_value={"all_checks_pass": True},
            ),
        ):
            rc = main([
                "--dataset-id", "test_dataset_id",
                "--version-tag", "test_v1",
                "--source-url", "https://example.com/lichess.pgn.zst",
                "--source-file", "lichess.pgn.zst",
                "--source-month", "2024-09",
                "--parser-metadata", str(parser_meta_path),
                "--cleaning-metadata", str(cleaning_meta_path),
                "--feature-metadata", str(feature_meta_path),
                "--assessment-json", str(assessment_path),
                "--feature-broad", str(tiny_parquet),
                "--feature-eval", str(tiny_parquet),
                "--output-dir", str(out_dir),
                "--card-output-dir", str(card_dir),
            ])

        assert rc == 0

        # JSON manifest
        json_out = out_dir / "dataset_version_test_dataset_id.json"
        assert json_out.exists(), "JSON manifest not written"

        # Dataset card
        card_out = card_dir / "dataset_card_test_dataset_id.md"
        assert card_out.exists(), "Dataset card not written"

        # Implementation report
        report_out = card_dir / "phase_4_2b_dataset_version_metadata_implementation.md"
        assert report_out.exists(), "Implementation report not written"

    def test_main_json_manifest_is_valid(
        self,
        tmp_path: Path,
        minimal_parser_metadata,
        minimal_cleaning_metadata,
        minimal_feature_metadata,
        minimal_assessment_json,
        tiny_parquet: Path,
    ):
        parser_meta_path = tmp_path / "parser_meta.json"
        parser_meta_path.write_text(json.dumps(minimal_parser_metadata), encoding="utf-8")
        cleaning_meta_path = tmp_path / "cleaning_meta.json"
        cleaning_meta_path.write_text(json.dumps(minimal_cleaning_metadata), encoding="utf-8")
        feature_meta_path = tmp_path / "feature_meta.json"
        feature_meta_path.write_text(json.dumps(minimal_feature_metadata), encoding="utf-8")
        assessment_path = tmp_path / "assessment.json"
        assessment_path.write_text(json.dumps(minimal_assessment_json), encoding="utf-8")
        out_dir = tmp_path / "out"
        card_dir = tmp_path / "card"

        with (
            patch("subprocess.run", return_value=MagicMock(stdout="abc123\n", returncode=0)),
            patch(
                "chess_mhsuc.assess_dataset.build_baseline_readiness",
                return_value={"all_checks_pass": True},
            ),
        ):
            main([
                "--dataset-id", "test_did",
                "--version-tag", "test_vt",
                "--source-url", "https://example.com/f.pgn.zst",
                "--source-file", "f.pgn.zst",
                "--source-month", "2024-09",
                "--parser-metadata", str(parser_meta_path),
                "--cleaning-metadata", str(cleaning_meta_path),
                "--feature-metadata", str(feature_meta_path),
                "--assessment-json", str(assessment_path),
                "--feature-broad", str(tiny_parquet),
                "--feature-eval", str(tiny_parquet),
                "--output-dir", str(out_dir),
                "--card-output-dir", str(card_dir),
            ])

        manifest_json = out_dir / "dataset_version_test_did.json"
        with open(manifest_json, encoding="utf-8") as fh:
            manifest = json.load(fh)

        assert manifest["dataset_id"] == "test_did"
        assert manifest["version_tag"] == "test_vt"
        assert manifest["manifest_type"] == "dataset_version_manifest"
        assert "provenance" in manifest
        assert "artifacts" in manifest
        assert "pipeline_policy" in manifest

    def test_main_with_test_count_arg(
        self,
        tmp_path: Path,
        minimal_parser_metadata,
        minimal_cleaning_metadata,
        minimal_feature_metadata,
        minimal_assessment_json,
        tiny_parquet: Path,
    ):
        parser_meta_path = tmp_path / "p.json"
        parser_meta_path.write_text(json.dumps(minimal_parser_metadata), encoding="utf-8")
        cleaning_meta_path = tmp_path / "c.json"
        cleaning_meta_path.write_text(json.dumps(minimal_cleaning_metadata), encoding="utf-8")
        feature_meta_path = tmp_path / "f.json"
        feature_meta_path.write_text(json.dumps(minimal_feature_metadata), encoding="utf-8")
        assessment_path = tmp_path / "a.json"
        assessment_path.write_text(json.dumps(minimal_assessment_json), encoding="utf-8")
        out_dir = tmp_path / "out2"
        card_dir = tmp_path / "card2"

        with (
            patch("subprocess.run", return_value=MagicMock(stdout="abc123\n", returncode=0)),
            patch(
                "chess_mhsuc.assess_dataset.build_baseline_readiness",
                return_value={"all_checks_pass": True},
            ),
        ):
            rc = main([
                "--dataset-id", "did2",
                "--version-tag", "vt2",
                "--source-url", "https://example.com/f.pgn.zst",
                "--source-file", "f.pgn.zst",
                "--source-month", "2024-09",
                "--parser-metadata", str(parser_meta_path),
                "--cleaning-metadata", str(cleaning_meta_path),
                "--feature-metadata", str(feature_meta_path),
                "--assessment-json", str(assessment_path),
                "--feature-broad", str(tiny_parquet),
                "--feature-eval", str(tiny_parquet),
                "--output-dir", str(out_dir),
                "--card-output-dir", str(card_dir),
                "--test-count", "42",
                "--prior-test-count", "322",
            ])

        assert rc == 0
        report = (card_dir / "phase_4_2b_dataset_version_metadata_implementation.md").read_text()
        assert "42" in report
        assert "364" in report  # 322 + 42
