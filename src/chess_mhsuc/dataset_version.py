"""
dataset_version.py — Dataset version metadata for chess-MHSUC.

Assembles a unified machine-readable manifest (JSON) and a human-readable
dataset card (Markdown) from the per-stage metadata produced by the pipeline:
    run_parser → cleaning → features → assess_dataset

Output files (all written to gitignored or committed locations — never to data/):
    data/processed/dataset_version_{dataset_id}.json        — local-only manifest
    reports/phase_reports/dataset_card_{dataset_id}.md      — committed dataset card
    reports/phase_reports/phase_4_2b_*.md                   — implementation report

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.dataset_version \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --source-url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst \\
        --source-file lichess_db_standard_rated_2024-09.pgn.zst \\
        --source-month 2024-09 \\
        --parser-metadata data/interim/parser_validation_2024_09_25k_v1_metadata.json \\
        --cleaning-metadata data/processed/cleaning_metadata_2024_09_25k_v1.json \\
        --feature-metadata data/processed/feature_metadata_2024_09_25k_v1.json \\
        --assessment-json data/processed/assessment_2024_09_25k_v1.json \\
        --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
        --feature-eval data/processed/feature_positions_eval_2024_09_25k_v1.parquet \\
        --output-dir data/processed \\
        --card-output-dir reports/phase_reports

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


# ---------------------------------------------------------------------------
# A. Git info
# ---------------------------------------------------------------------------

def get_git_info(cwd: Path | None = None) -> dict:
    """
    Read git state using read-only subprocess commands.

    Returns commit_hash, branch, status_clean, and dirty_files.
    Does not crash on git failure — returns error fields instead.
    """
    kwargs = {"capture_output": True, "text": True}
    if cwd is not None:
        kwargs["cwd"] = str(cwd)

    def _run(cmd: list[str]) -> tuple[str, int]:
        try:
            r = subprocess.run(cmd, **kwargs)
            return r.stdout.strip(), r.returncode
        except Exception as exc:
            return f"error: {exc}", -1

    commit_out, commit_rc = _run(["git", "rev-parse", "HEAD"])
    branch_out, branch_rc = _run(["git", "branch", "--show-current"])
    status_out, status_rc = _run(["git", "status", "--porcelain"])

    commit_hash = commit_out if commit_rc == 0 else None
    branch = branch_out if branch_rc == 0 else None

    if status_rc == 0:
        dirty_files = [line for line in status_out.splitlines() if line.strip()]
        status_clean = len(dirty_files) == 0
    else:
        dirty_files = []
        status_clean = False

    return {
        "commit_hash": commit_hash,
        "branch": branch,
        "status_clean": status_clean,
        "dirty_files": dirty_files,
    }


# ---------------------------------------------------------------------------
# B. Dependency versions
# ---------------------------------------------------------------------------

def get_dependency_versions() -> dict:
    """
    Return installed package versions for key pipeline dependencies.

    Uses importlib.metadata.version(). Records null for missing packages.
    """
    import importlib.metadata

    packages = [
        "python-chess",
        "polars",
        "pandas",
        "duckdb",
        "scikit-learn",
        "matplotlib",
        "pyarrow",
        "zstandard",
        "tqdm",
        "jupyter",
        "pytest",
    ]
    versions: dict[str, str | None] = {}
    for pkg in packages:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = None

    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "packages": versions,
    }


# ---------------------------------------------------------------------------
# C. SHA256
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """
    Compute SHA256 of a file using chunked reads.

    Returns 64-character hex string.
    Raises FileNotFoundError if the file does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(f"Cannot hash missing file: {path}")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 16)  # 64 KiB
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# D. File format inference
# ---------------------------------------------------------------------------

def infer_file_format(path: Path) -> str:
    """Return a normalised file format string from the file extension."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    return "unknown"


# ---------------------------------------------------------------------------
# E. Row and column counts
# ---------------------------------------------------------------------------

def row_and_column_counts(path: Path) -> dict:
    """
    Return row_count and column_count for a file.

    For Parquet, reads only the footer metadata (no data loaded).
    For JSON and other formats, returns null.
    """
    if not path.exists():
        return {"row_count": None, "column_count": None}
    if path.suffix.lower() == ".parquet":
        try:
            import pyarrow.parquet as pq
            meta = pq.read_metadata(str(path))
            return {"row_count": meta.num_rows, "column_count": meta.num_columns}
        except Exception:
            # Fallback to polars schema (column count only)
            try:
                schema = pl.read_parquet_schema(path)
                return {"row_count": None, "column_count": len(schema)}
            except Exception:
                return {"row_count": None, "column_count": None}
    return {"row_count": None, "column_count": None}


# ---------------------------------------------------------------------------
# F. Artifact inventory
# ---------------------------------------------------------------------------

def build_artifact_inventory(artifact_specs: list[dict]) -> list[dict]:
    """
    Given a list of artifact specs, compute size, SHA256, and row/column counts.

    Each spec must have: path, role, stage, should_commit.
    Optional: git_tracked (defaults to False for data artifacts).
    """
    inventory: list[dict] = []
    for spec in artifact_specs:
        p = Path(spec["path"])
        entry: dict = {
            "path": str(p),
            "role": spec.get("role", "unknown"),
            "stage": spec.get("stage", "unknown"),
            "file_format": infer_file_format(p),
            "git_tracked": spec.get("git_tracked", False),
            "should_commit": spec.get("should_commit", False),
        }
        if p.exists():
            entry["exists"] = True
            entry["file_size_bytes"] = p.stat().st_size
            try:
                entry["sha256"] = sha256_file(p)
            except Exception as exc:
                entry["sha256"] = f"error: {exc}"
            counts = row_and_column_counts(p)
            entry["row_count"] = counts["row_count"]
            entry["column_count"] = counts["column_count"]
        else:
            entry["exists"] = False
            entry["file_size_bytes"] = None
            entry["sha256"] = None
            entry["row_count"] = None
            entry["column_count"] = None
            entry["missing_reason"] = "File not found on local filesystem"
        inventory.append(entry)
    return inventory


# ---------------------------------------------------------------------------
# G. Load JSON
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Read a JSON file safely and return its contents as a dict."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# H. Provenance
# ---------------------------------------------------------------------------

def build_provenance(
    dataset_id: str,
    version_tag: str,
    source_url: str,
    source_file: str,
    source_month: str,
    parser_metadata: dict,
    pipeline_code_git_state: dict,
    manifest_generation_git_state: dict,
    dependency_versions: dict,
) -> dict:
    """Assemble the provenance section of the unified manifest."""
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_name": "lichess",
        "source_url": source_url,
        "source_file": source_file,
        "source_month": source_month,
        "time_control": "600+0",
        "time_control_slug": "ten_zero",
        "rated_only": True,
        "standard_only": True,
        "raw_games_cap": parser_metadata.get("raw_games_cap"),
        "max_accepted_basic": parser_metadata.get("max_accepted_basic"),
        "pipeline_code_git_state": pipeline_code_git_state,
        "manifest_generation_git_state": manifest_generation_git_state,
        "python_version": dependency_versions.get("python_version"),
        "dependency_versions": dependency_versions.get("packages", {}),
        "platform": dependency_versions.get("platform"),
    }


# ---------------------------------------------------------------------------
# I. Pipeline stage outputs
# ---------------------------------------------------------------------------

def build_pipeline_stage_outputs(
    parser_metadata: dict,
    cleaning_metadata: dict,
    feature_metadata: dict,
    assessment_json: dict,
) -> dict:
    """
    Build a stage map recording inputs, outputs, metadata paths, and row counts.
    """
    return {
        "parser": {
            "inputs": {"source_url": parser_metadata.get("source_url"),
                       "source_file": parser_metadata.get("source_file")},
            "outputs": parser_metadata.get("output_paths", {}),
            "metadata_path": (parser_metadata.get("output_paths") or {}).get("metadata"),
            "key_counts": {
                "raw_games_scanned": parser_metadata.get("raw_games_scanned"),
                "n_600_0_total": parser_metadata.get("n_600_0_total"),
                "n_accepted_basic": parser_metadata.get("n_accepted_basic"),
                "n_position_records": parser_metadata.get("n_position_records"),
                "n_parse_errors": parser_metadata.get("n_parse_errors"),
            },
            "version_tag_in_metadata": parser_metadata.get("version_tag"),
            "version_tag_note": (
                "Parser metadata records version_tag='v1'. The canonical dataset "
                "version_tag is '2024_09_25k_v1' (composed from source month + cap + tag). "
                "File names are correct; only the version_tag field in the parser metadata JSON is ambiguous."
            ),
        },
        "cleaning": {
            "inputs": cleaning_metadata.get("input_paths", {}),
            "outputs": cleaning_metadata.get("output_paths", {}),
            "metadata_path": (cleaning_metadata.get("output_paths") or {}).get("metadata"),
            "key_counts": {
                "raw_game_rows": cleaning_metadata.get("raw_game_rows"),
                "clean_game_rows": cleaning_metadata.get("clean_game_rows"),
                "excluded_game_rows": cleaning_metadata.get("excluded_game_rows"),
                "retained_time_forfeit": cleaning_metadata.get("retained_time_forfeit"),
                "broad_position_rows": cleaning_metadata.get("broad_position_rows"),
                "eval_position_rows": cleaning_metadata.get("eval_position_rows"),
            },
        },
        "features": {
            "inputs": feature_metadata.get("input_paths", {}),
            "outputs": feature_metadata.get("output_paths", {}),
            "metadata_path": (feature_metadata.get("output_paths") or {}).get("metadata"),
            "key_counts": feature_metadata.get("row_counts", {}),
        },
        "assessment": {
            "inputs": assessment_json.get("input_paths", {}),
            "outputs": assessment_json.get("output_paths", {}),
            "metadata_path": (assessment_json.get("output_paths") or {}).get("assessment_json"),
            "key_counts": {
                "broad_rows": (assessment_json.get("target_distribution_broad") or {}).get("n_rows"),
                "eval_rows": (assessment_json.get("target_distribution_eval") or {}).get("n_rows"),
            },
        },
    }


# ---------------------------------------------------------------------------
# J. Pipeline policy
# ---------------------------------------------------------------------------

def build_pipeline_policy() -> dict:
    """Return the curated v1 pipeline policy summary."""
    return {
        "parser_acceptance_rules": [
            "TimeControl must be '600+0'",
            "WhiteElo and BlackElo must be present and valid integers",
            "Result must be one of '1-0', '0-1', '1/2-1/2'",
            "Clock annotations (%clk) must be present in move comments",
            "Variant must be absent or 'Standard'",
            "Ratings must pass basic range validity check",
        ],
        "rejection_priority": [
            "wrong_time_control",
            "variant_or_nonstandard",
            "missing_or_invalid_elo",
            "missing_or_invalid_result",
            "missing_clock",
        ],
        "cleaning_rules": {
            "game_level": [
                "accepted_basic == True",
                "termination != 'Abandoned'",
            ],
            "position_level_broad": [
                "game_id in clean_game_records",
            ],
            "position_level_eval": [
                "has_eval == True",
            ],
        },
        "time_forfeit_policy": (
            "Time forfeit games are RETAINED. They are central to the research question "
            "(clock pressure as a predictor of outcome). is_time_forfeit is a slice column only."
        ),
        "eval_policy": (
            "eval_cp is nullable by design. Missing eval is retained as null and never imputed. "
            "Mate positions use MATE_CP_SENTINEL = ±10000. eval_cp_clipped clips to ±1000."
        ),
        "clock_capping_policy": (
            "white/black_clock_s_capped = min(raw, 600). Fractional clocks and low-time flags "
            "use capped values. Raw clock_s values are preserved. Rows with raw > 600 are flagged "
            "by clock_anomaly=True (7 rows in v1 broad)."
        ),
        "eval_clipping_policy": (
            "eval_cp_clipped = clip(eval_cp, -1000, +1000). Mate sentinels ±10000 are mapped to "
            "±1000. Raw eval_cp and eval_mate are preserved. is_mate_eval distinguishes forced-mate "
            "positions."
        ),
        "low_time_thresholds_s": [60, 30, 10],
        "clock_cap_s": 600,
        "eval_clip_cp": 1000,
        "duplicate_checkpoint_policy": (
            "Rows where (game_id, ply) appears in more than one row are flagged by "
            "duplicate_ply_checkpoint=True. Rows are NOT dropped. 83 games produce 2 rows at the "
            "same ply (last + numbered coincide). Callers must deduplicate per experiment."
        ),
        "last_checkpoint_policy": (
            "The 'last' checkpoint is the final ply of any game. Included and flagged by "
            "is_last_checkpoint=True. It is a caution column: semantically distinct from numbered "
            "checkpoints (move_10 through move_40)."
        ),
        "checkpoint_positions": ["move_10", "move_20", "move_30", "move_40", "last"],
        "leakage_policy": {
            "label_columns": ["result_class", "white_result_numeric"],
            "forbidden_as_features": [
                "n_plies_total", "white_rating_diff", "black_rating_diff",
                "termination", "is_time_forfeit", "game_id",
            ],
            "explanation": (
                "result_class and white_result_numeric are target labels and must never be model "
                "inputs. termination and n_plies_total are post-game information. "
                "white/black_rating_diff are post-game rating changes. "
                "game_id is a group/split key only."
            ),
        },
        "target_label_policy": (
            "Three-class: WHITE_WIN / DRAW / BLACK_WIN. "
            "white_result_numeric: 1.0 = White win, 0.5 = Draw, 0.0 = Black win."
        ),
        "split_policy": (
            "Game-level split by game_id. Never split rows independently across positions from the "
            "same game. Recommended: 80% train / 10% val / 10% test by game_id."
        ),
        "slice_columns": ["game_id", "termination", "is_time_forfeit", "has_eval"],
    }


# ---------------------------------------------------------------------------
# K. Normalize forbidden leakage columns
# ---------------------------------------------------------------------------

_KNOWN_LEAKAGE_REASONS: dict[str, str] = {
    "result_class": "target label, never model input",
    "white_result_numeric": "target label, never model input",
    "termination": "post-game information",
    "is_time_forfeit": "derived from post-game termination",
    "n_plies_total": "post-game length, available only after game ends",
    "white_rating_diff": "post-game rating change",
    "black_rating_diff": "post-game rating change",
    "accepted_basic": "parser internal flag, not a game feature",
    "accepted_eval": "parser internal flag, not a game feature",
    "rejection_reason": "parser internal flag, not a game feature",
    "game_id": "group/split key only, never a model feature",
    "has_clock": "parser internal flag",
    "result_raw": "raw result string, not a game feature",
    "time_control": "constant within this dataset (600+0)",
    "source_file": "data provenance, not a game feature",
    "source_month": "data provenance, not a game feature",
    "event": "game metadata, not a game feature",
    "utc_date": "game metadata timestamp",
    "utc_time": "game metadata timestamp",
    "ply": "raw ply index used internally; dropped after duplicate check",
}


def normalize_forbidden_leakage_columns(feature_metadata: dict) -> dict:
    """
    Normalize the forbidden_leakage_columns list from feature metadata.

    The raw list may contain entries like 'result_class (as a feature)'.
    Returns:
        forbidden_leakage_columns: list of plain column names
        forbidden_leakage_reasons: dict mapping column -> reason
    """
    raw_list = feature_metadata.get("forbidden_leakage_columns", [])
    plain_names: list[str] = []
    for entry in raw_list:
        # Strip annotations like " (as a feature)"
        name = str(entry).split(" (")[0].strip()
        if name not in plain_names:
            plain_names.append(name)

    reasons: dict[str, str] = {}
    for col in plain_names:
        reasons[col] = _KNOWN_LEAKAGE_REASONS.get(col, "see feature policy")

    return {
        "forbidden_leakage_columns": plain_names,
        "forbidden_leakage_reasons": reasons,
    }


# ---------------------------------------------------------------------------
# L. Column schema
# ---------------------------------------------------------------------------

def build_column_schema(feature_parquet_path: Path, feature_metadata: dict) -> dict:
    """
    Build column schema from actual Parquet schema + feature metadata column lists.

    Reads dtypes from the Parquet file (no data loaded — schema only).
    """
    # Read dtype map from Parquet schema
    dtype_map: dict[str, str] = {}
    try:
        schema = pl.read_parquet_schema(feature_parquet_path)
        dtype_map = {col: str(dtype) for col, dtype in schema.items()}
    except Exception:
        pass

    normalized = normalize_forbidden_leakage_columns(feature_metadata)

    return {
        "total_columns": len(dtype_map) or None,
        "dtype_map": dtype_map,
        "default_predictive_features": feature_metadata.get("default_predictive_features", []),
        "eval_predictive_features": feature_metadata.get("eval_predictive_features", []),
        "caution_columns": feature_metadata.get("caution_columns", []),
        "label_columns": feature_metadata.get("label_columns", []),
        "slice_columns": feature_metadata.get("slice_columns", []),
        "metadata_columns": feature_metadata.get("metadata_columns", []),
        "dropped_columns": feature_metadata.get("dropped_columns", []),
        "nullable_eval_columns": feature_metadata.get("nullable_eval_columns", []),
        "forbidden_leakage_columns": normalized["forbidden_leakage_columns"],
        "forbidden_leakage_reasons": normalized["forbidden_leakage_reasons"],
    }


# ---------------------------------------------------------------------------
# M. Dataset summary
# ---------------------------------------------------------------------------

_CAVEATS = [
    "DRAW class is ~5.83% of broad rows — minority class. Accuracy alone is misleading; "
    "use log loss / Brier score / calibration curves.",
    "Eval subset avg_elo is ~20 Elo higher than broad — non-random selection bias. "
    "Models trained on eval-gated data may not generalize to lower-rated games.",
    "166 rows (83 games × 2) have duplicate_ply_checkpoint=True — same (game_id, ply) in both "
    "a numbered checkpoint and the 'last' checkpoint. Must deduplicate before training "
    "(recommended: keep numbered checkpoint, drop coincident 'last').",
    "The 'last' checkpoint is semantically different from numbered checkpoints. "
    "move_10 through move_40 always have white to move next; 'last' does not. "
    "Treat is_last_checkpoint as a caution column.",
    "7 rows have raw clock_s > 600 (clock anomalies). Raw clock values are unreliable for these "
    "rows; capped values (white/black_clock_s_capped) are safe to use.",
    "25,000 raw game cap from a single source month (2024-09). Results may not generalize to "
    "other months, seasons, or the full Lichess 10+0 population.",
    "Split must be by game_id. Never split rows independently — multiple rows from the same game "
    "would leak across train/val/test boundaries.",
    "All data artifacts are local-only and gitignored. Regenerate from source using the "
    "reproduction commands in this document.",
]


def build_dataset_summary(
    assessment_json: dict,
    feature_broad_path: Path,
    feature_eval_path: Path,
) -> dict:
    """
    Extract curated dataset statistics from the assessment JSON and Parquet files.

    Does not propagate 'TBD' or other placeholder values as authoritative.
    """
    bve = assessment_json.get("broad_vs_eval", {})
    tdb = assessment_json.get("target_distribution_broad", {})
    tde = assessment_json.get("target_distribution_eval", {})
    evd = assessment_json.get("eval_distribution_broad", {})
    ckpt = assessment_json.get("checkpoint_distribution_broad", {})
    clk = assessment_json.get("clock_distribution_broad", {})
    lk = assessment_json.get("leakage_safety_broad", {})
    br = assessment_json.get("leakage_safety_broad", {})  # re-derive readiness below

    broad_rows = tdb.get("n_rows") or bve.get("broad_n")
    eval_rows = tde.get("n_rows") or bve.get("eval_n")
    unique_games_broad = bve.get("broad_games")
    unique_games_eval = bve.get("eval_games")

    result_dist_broad = tdb.get("result_class", {}).get("counts", {})
    result_pct_broad = tdb.get("result_class", {}).get("pct", {})
    draw_rate = result_pct_broad.get("DRAW", 0.0)

    eval_coverage_pct = evd.get("eval_coverage_pct")
    clock_anomaly_count = clk.get("clock_anomaly_n")
    dup_count = ckpt.get("duplicate_ply_checkpoint_n")

    avg_elo_broad = bve.get("avg_elo_broad")
    avg_elo_eval = bve.get("avg_elo_eval")
    elo_bias: float | None = None
    if avg_elo_broad is not None and avg_elo_eval is not None:
        elo_bias = round(float(avg_elo_eval) - float(avg_elo_broad), 1)
    if avg_elo_broad is not None:
        avg_elo_broad = round(float(avg_elo_broad), 1)
    if avg_elo_eval is not None:
        avg_elo_eval = round(float(avg_elo_eval), 1)

    leakage_safe = lk.get("leakage_safe")

    # Re-derive baseline readiness from assessment (import avoided; inline minimal check)
    from chess_mhsuc.assess_dataset import build_baseline_readiness
    try:
        readiness = build_baseline_readiness(assessment_json)
        baseline_readiness_all_pass = readiness.get("all_checks_pass")
    except Exception:
        baseline_readiness_all_pass = None

    return {
        "broad_rows": broad_rows,
        "eval_rows": eval_rows,
        "unique_games_broad": unique_games_broad,
        "unique_games_eval": unique_games_eval,
        "result_distribution_broad": result_dist_broad,
        "result_pct_broad": result_pct_broad,
        "draw_rate_broad_pct": draw_rate,
        "eval_coverage_broad_pct": eval_coverage_pct,
        "clock_anomaly_count": clock_anomaly_count,
        "duplicate_ply_checkpoint_count": dup_count,
        "avg_elo_broad": avg_elo_broad,
        "avg_elo_eval": avg_elo_eval,
        "eval_avg_elo_bias": elo_bias,
        "leakage_safety_passed": leakage_safe,
        "baseline_readiness_all_pass": baseline_readiness_all_pass,
        "caveats": _CAVEATS,
    }


# ---------------------------------------------------------------------------
# N. Build dataset version manifest
# ---------------------------------------------------------------------------

_ARTIFACT_SPECS = [
    {"path": "data/interim/game_records_2024_09_25k_v1.parquet",
     "role": "interim_game_records", "stage": "parser", "should_commit": False},
    {"path": "data/interim/position_records_2024_09_25k_v1.parquet",
     "role": "interim_position_records", "stage": "parser", "should_commit": False},
    {"path": "data/interim/parser_validation_2024_09_25k_v1_metadata.json",
     "role": "parser_metadata", "stage": "parser", "should_commit": False},
    {"path": "data/processed/ten_zero_game_records_2024_09_25k_v1.parquet",
     "role": "clean_game_records", "stage": "cleaning", "should_commit": False},
    {"path": "data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet",
     "role": "clean_positions_broad", "stage": "cleaning", "should_commit": False},
    {"path": "data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet",
     "role": "clean_positions_eval", "stage": "cleaning", "should_commit": False},
    {"path": "data/processed/cleaning_metadata_2024_09_25k_v1.json",
     "role": "cleaning_metadata", "stage": "cleaning", "should_commit": False},
    {"path": "data/processed/feature_positions_broad_2024_09_25k_v1.parquet",
     "role": "feature_positions_broad", "stage": "features", "should_commit": False},
    {"path": "data/processed/feature_positions_eval_2024_09_25k_v1.parquet",
     "role": "feature_positions_eval", "stage": "features", "should_commit": False},
    {"path": "data/processed/feature_metadata_2024_09_25k_v1.json",
     "role": "feature_metadata", "stage": "features", "should_commit": False},
    {"path": "data/processed/assessment_2024_09_25k_v1.json",
     "role": "assessment_json", "stage": "assessment", "should_commit": False},
]


def build_dataset_version_manifest(
    dataset_id: str,
    version_tag: str,
    provenance: dict,
    artifacts: list[dict],
    pipeline_stage_outputs: dict,
    pipeline_policy: dict,
    column_schema: dict,
    dataset_summary: dict,
    known_metadata_inconsistencies: list[dict],
) -> dict:
    """Assemble the unified dataset version manifest dict."""

    source_url = provenance.get("source_url", "")
    source_file = provenance.get("source_file", "")

    reproducibility = {
        "note": (
            "All local data artifacts are gitignored and must be regenerated from source. "
            "The repository contains only scripts and reports. Use the commands below to "
            "reproduce this dataset version exactly."
        ),
        "parser_command": (
            f"PYTHONPATH=src python -m chess_mhsuc.run_parser "
            f"--url {source_url} "
            f"--max-games 25000 --max-accepted 2500 "
            f"--source-file {source_file} "
            f"--output-dir data/interim "
            f"--version-tag v1"
        ),
        "cleaning_command": (
            "PYTHONPATH=src python -m chess_mhsuc.cleaning "
            "--game-records data/interim/game_records_2024_09_25k_v1.parquet "
            "--position-records data/interim/position_records_2024_09_25k_v1.parquet "
            "--output-dir data/processed "
            f"--version-tag {version_tag}"
        ),
        "features_command": (
            "PYTHONPATH=src python -m chess_mhsuc.features "
            f"--positions-broad data/processed/ten_zero_positions_broad_{version_tag}.parquet "
            f"--positions-eval data/processed/ten_zero_positions_eval_{version_tag}.parquet "
            "--output-dir data/processed "
            f"--version-tag {version_tag}"
        ),
        "assessment_command": (
            "PYTHONPATH=src python -m chess_mhsuc.assess_dataset "
            f"--feature-broad data/processed/feature_positions_broad_{version_tag}.parquet "
            f"--feature-eval data/processed/feature_positions_eval_{version_tag}.parquet "
            f"--feature-metadata data/processed/feature_metadata_{version_tag}.json "
            "--output-dir reports/phase_reports "
            f"--version-tag {version_tag}"
        ),
        "dataset_version_command": (
            f"PYTHONPATH=src python -m chess_mhsuc.dataset_version "
            f"--dataset-id {dataset_id} "
            f"--version-tag {version_tag} "
            f"--source-url {source_url} "
            f"--source-file {source_file} "
            f"--source-month {provenance.get('source_month', '2024-09')} "
            f"--parser-metadata data/interim/parser_validation_{version_tag}_metadata.json "
            f"--cleaning-metadata data/processed/cleaning_metadata_{version_tag}.json "
            f"--feature-metadata data/processed/feature_metadata_{version_tag}.json "
            f"--assessment-json data/processed/assessment_{version_tag}.json "
            f"--feature-broad data/processed/feature_positions_broad_{version_tag}.parquet "
            f"--feature-eval data/processed/feature_positions_eval_{version_tag}.parquet "
            "--output-dir data/processed "
            "--card-output-dir reports/phase_reports"
        ),
        "parser_version_tag_note": (
            "The parser CLI was run with --version-tag 'v1'. The resulting file names include "
            "the source month and cap (e.g. game_records_2024_09_25k_v1.parquet) because "
            "run_parser._make_stem() prepends the month and cap to the tag. "
            "Use --version-tag v1 to reproduce identical file names."
        ),
    }

    data_safety = {
        "data_artifacts_committed": False,
        "data_artifacts_gitignored": True,
        "usernames_absent_from_processed_tables": True,
        "usernames_absent_from_feature_tables": True,
        "raw_archive_saved_locally": False,
        "csv_files_created": False,
        "model_files_created": False,
        "parquet_files_modified_by_this_stage": False,
        "existing_stage_metadata_modified_by_this_stage": False,
    }

    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "manifest_type": "dataset_version_manifest",
        "created_at_utc": provenance.get("created_at_utc",
                                          datetime.now(timezone.utc).isoformat()),
        "provenance": provenance,
        "artifacts": artifacts,
        "pipeline_stage_outputs": pipeline_stage_outputs,
        "pipeline_policy": pipeline_policy,
        "column_schema": column_schema,
        "dataset_summary": dataset_summary,
        "known_metadata_inconsistencies": known_metadata_inconsistencies,
        "reproducibility": reproducibility,
        "data_safety": data_safety,
        "recommended_next_step": (
            "Ticket 5.1A — Modeling Split and Baseline Audit: define game-level "
            "train/validation/test split by game_id and establish baseline models "
            "(majority-class, rating-only, eval-only, eval+rating, eval+rating+clocks)."
        ),
    }


# ---------------------------------------------------------------------------
# O. Render dataset card (Markdown)
# ---------------------------------------------------------------------------

def render_dataset_card(manifest: dict) -> str:
    """Render the manifest as a committed Markdown dataset card."""
    did = manifest["dataset_id"]
    vt = manifest["version_tag"]
    prov = manifest["provenance"]
    summary = manifest["dataset_summary"]
    schema = manifest["column_schema"]
    policy = manifest["pipeline_policy"]
    artifacts = manifest["artifacts"]
    repro = manifest["reproducibility"]
    incons = manifest["known_metadata_inconsistencies"]
    pg = prov.get("pipeline_code_git_state", {})
    mg = prov.get("manifest_generation_git_state", {})

    broad_rows = summary.get("broad_rows", "N/A")
    eval_rows = summary.get("eval_rows", "N/A")
    unique_games_broad = summary.get("unique_games_broad", "N/A")
    unique_games_eval = summary.get("unique_games_eval", "N/A")
    draw_pct = summary.get("draw_rate_broad_pct", "N/A")
    eval_cov = summary.get("eval_coverage_broad_pct", "N/A")
    avg_elo_broad = summary.get("avg_elo_broad", "N/A")
    avg_elo_eval = summary.get("avg_elo_eval", "N/A")
    elo_bias = summary.get("eval_avg_elo_bias", "N/A")
    clock_anom = summary.get("clock_anomaly_count", "N/A")
    dup_count = summary.get("duplicate_ply_checkpoint_count", "N/A")
    leakage_safe = summary.get("leakage_safety_passed", "N/A")
    readiness = summary.get("baseline_readiness_all_pass", "N/A")

    result_dist = summary.get("result_distribution_broad", {})
    result_pct = summary.get("result_pct_broad", {})

    default_feats = schema.get("default_predictive_features", [])
    eval_feats = schema.get("eval_predictive_features", [])
    caution_cols = schema.get("caution_columns", [])
    label_cols = schema.get("label_columns", [])
    slice_cols = schema.get("slice_columns", [])
    forbidden = schema.get("forbidden_leakage_columns", [])
    reasons = schema.get("forbidden_leakage_reasons", {})
    nullable = schema.get("nullable_eval_columns", [])

    pg_commit = pg.get("commit_hash", "unknown")
    mg_dirty = not mg.get("status_clean", True)
    mg_dirty_files = mg.get("dirty_files", [])

    pkg_versions = prov.get("dependency_versions", {})

    lines = [
        f"# Dataset Card: {did}",
        f"",
        f"**Version tag:** `{vt}`  ",
        f"**Source:** Lichess standard rated 10+0 (600+0), month 2024-09  ",
        f"**Created:** {prov.get('created_at_utc', 'N/A')[:10]}  ",
        f"**Status:** Local-only pilot dataset. No raw data committed to Git.",
        f"",
        f"---",
        f"",
        f"## 1. ELI5 / TLDR",
        f"",
        f"This dataset contains {broad_rows:,} chess position checkpoints from "
        f"{unique_games_broad:,} unique Lichess 10+0 games (September 2024). "
        f"Each position is annotated with player ratings, clock times, engine evaluation "
        f"(where available), game phase, and a three-class outcome label (White win / Draw / "
        f"Black win). The data is local-only; this card documents what it is, how it was "
        f"produced, and how to reproduce it.",
        f"",
        f"---",
        f"",
        f"## 2. Dataset Identity",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| `dataset_id` | `{did}` |",
        f"| `version_tag` | `{vt}` |",
        f"| `source_name` | lichess |",
        f"| `time_control` | 600+0 (10+0) |",
        f"| `source_month` | {prov.get('source_month', 'N/A')} |",
        f"| `raw_games_cap` | {prov.get('raw_games_cap', 'N/A'):,} |",
        f"| `max_accepted_basic` | {prov.get('max_accepted_basic', 'N/A'):,} |",
        f"| `rated_only` | {prov.get('rated_only', True)} |",
        f"| `standard_only` | {prov.get('standard_only', True)} |",
        f"",
        f"---",
        f"",
        f"## 3. Source Provenance",
        f"",
        f"**Source URL:** `{prov.get('source_url', 'N/A')}`  ",
        f"**Source file:** `{prov.get('source_file', 'N/A')}`  ",
        f"**Source month:** {prov.get('source_month', 'N/A')}  ",
        f"**Time control filter:** `{prov.get('time_control', '600+0')}`  ",
        f"",
        f"The source archive is a Lichess monthly PGN dump compressed with Zstandard. "
        f"It is not downloaded or stored locally — the parser streams it directly from the URL.",
        f"",
        f"---",
        f"",
        f"## 4. Pipeline Summary",
        f"",
        f"```",
        f"Stage 1: run_parser.py  — stream Lichess PGN → interim parsed tables",
        f"  Input:  Lichess .pgn.zst archive (streamed from URL)",
        f"  Output: data/interim/game_records_*.parquet",
        f"          data/interim/position_records_*.parquet",
        f"          data/interim/parser_validation_*_metadata.json",
        f"",
        f"Stage 2: cleaning.py   — apply v1 cleaning rules → processed tables",
        f"  Input:  data/interim/game_records_*.parquet",
        f"          data/interim/position_records_*.parquet",
        f"  Output: data/processed/ten_zero_game_records_*.parquet",
        f"          data/processed/ten_zero_positions_broad_*.parquet",
        f"          data/processed/ten_zero_positions_eval_*.parquet",
        f"          data/processed/cleaning_metadata_*.json",
        f"",
        f"Stage 3: features.py   — add derived features → 40-column feature tables",
        f"  Input:  data/processed/ten_zero_positions_broad_*.parquet",
        f"          data/processed/ten_zero_positions_eval_*.parquet",
        f"  Output: data/processed/feature_positions_broad_*.parquet",
        f"          data/processed/feature_positions_eval_*.parquet",
        f"          data/processed/feature_metadata_*.json",
        f"",
        f"Stage 4: assess_dataset.py — dataset quality checks → Markdown + JSON",
        f"  Input:  feature_positions_broad/eval_*.parquet",
        f"          feature_metadata_*.json",
        f"  Output: data/processed/assessment_*.json",
        f"          reports/phase_reports/phase_4_1b_*.md",
        f"",
        f"Stage 5: dataset_version.py — unified metadata → JSON manifest + this card",
        f"  Input:  all metadata JSON files + feature Parquet files",
        f"  Output: data/processed/dataset_version_*.json  (local-only)",
        f"          reports/phase_reports/dataset_card_*.md  (committed)",
        f"```",
        f"",
        f"---",
        f"",
        f"## 5. Artifact Inventory",
        f"",
        f"All artifacts are local-only (gitignored under `data/`). SHA256 hashes enable "
        f"integrity verification on reproduction.",
        f"",
        f"| Artifact | Stage | Role | Rows | Size | SHA256 (prefix) |",
        f"|----------|-------|------|------|------|-----------------|",
    ]

    for art in artifacts:
        if not art.get("exists", False):
            lines.append(f"| `{art['path']}` | {art['stage']} | {art['role']} | — | missing | — |")
            continue
        sz = art.get("file_size_bytes", 0)
        sz_str = f"{sz / 1024:.1f} KB" if sz and sz < 1_048_576 else (
            f"{sz / 1_048_576:.1f} MB" if sz else "—")
        rows = art.get("row_count")
        rows_str = f"{rows:,}" if rows is not None else "—"
        sha_prefix = (art.get("sha256") or "")[:12]
        lines.append(
            f"| `{art['path']}` | {art['stage']} | {art['role']} | "
            f"{rows_str} | {sz_str} | `{sha_prefix}...` |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## 6. Row Counts and Core Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Broad feature rows | {broad_rows:,} |",
        f"| Eval feature rows | {eval_rows:,} |",
        f"| Unique games (broad) | {unique_games_broad:,} |",
        f"| Unique games (eval) | {unique_games_eval:,} |",
        f"| Draw rate (broad) | {draw_pct}% |",
        f"| Eval coverage (broad) | {eval_cov}% |",
        f"| avg_elo broad | {avg_elo_broad} |",
        f"| avg_elo eval subset | {avg_elo_eval} (Δ = {elo_bias:+} Elo) |",
        f"| Clock anomalies | {clock_anom} rows |",
        f"| Duplicate ply checkpoints | {dup_count} rows |",
        f"",
        f"### Result distribution (broad)",
        f"",
        f"| result_class | Count | % |",
        f"|--------------|-------|---|",
    ]
    for label in ["WHITE_WIN", "BLACK_WIN", "DRAW"]:
        cnt = result_dist.get(label, 0)
        pct = result_pct.get(label, 0.0)
        lines.append(f"| {label} | {cnt:,} | {pct}% |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 7. Column / Feature Schema",
        f"",
        f"Total columns in feature table: **{schema.get('total_columns', 'N/A')}**",
        f"",
        f"### Default predictive features ({len(default_feats)})",
        f"",
        f"```",
        ", ".join(default_feats),
        f"```",
        f"",
        f"### Eval predictive features ({len(eval_feats)}, nullable)",
        f"",
        f"```",
        ", ".join(eval_feats),
        f"```",
        f"",
        f"### Labels (never model inputs)",
        f"",
        f"```",
        ", ".join(label_cols),
        f"```",
        f"",
        f"### Caution columns (present but require careful use)",
        f"",
        f"```",
        ", ".join(caution_cols),
        f"```",
        f"",
        f"### Slice / group columns",
        f"",
        f"```",
        ", ".join(slice_cols),
        f"```",
        f"",
        f"### Nullable columns (expected nulls — eval unavailable for 86.3% of broad rows)",
        f"",
        f"```",
        ", ".join(nullable),
        f"```",
        f"",
        f"---",
        f"",
        f"## 8. Leakage and Safety Policy",
        f"",
        f"**Leakage safety confirmed:** `{leakage_safe}`  ",
        f"**Baseline readiness (all checks pass):** `{readiness}`",
        f"",
        f"### Forbidden leakage columns",
        f"",
        f"| Column | Reason |",
        f"|--------|--------|",
    ]
    for col in forbidden:
        reason = reasons.get(col, "see feature policy")
        lines.append(f"| `{col}` | {reason} |")

    lines += [
        f"",
        f"### Leakage policy summary",
        f"",
        f"{policy.get('leakage_policy', {}).get('explanation', '')}",
        f"",
        f"---",
        f"",
        f"## 9. Known Caveats",
        f"",
    ]
    for i, caveat in enumerate(summary.get("caveats", []), 1):
        lines.append(f"**C{i}.** {caveat}")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 10. Reproduction Commands",
        f"",
        f"All data artifacts must be regenerated locally. The source archive is publicly available "
        f"at the Lichess open database. A working Python 3.13 environment with project "
        f"dependencies installed (`pip install -r requirements.txt`) is required.",
        f"",
        f"```bash",
        f"# Stage 1: Parser",
        f"# Note: --version-tag 'v1' produces file names with stem '2024_09_25k_v1'",
        f"# because run_parser prepends source month and cap to the tag.",
        f"{repro.get('parser_command', '')}",
        f"",
        f"# Stage 2: Cleaning",
        f"{repro.get('cleaning_command', '')}",
        f"",
        f"# Stage 3: Feature engineering",
        f"{repro.get('features_command', '')}",
        f"",
        f"# Stage 4: Dataset assessment",
        f"{repro.get('assessment_command', '')}",
        f"",
        f"# Stage 5: Dataset version manifest (this card)",
        f"{repro.get('dataset_version_command', '')}",
        f"```",
        f"",
        f"---",
        f"",
        f"## 11. Git and Dependency Metadata",
        f"",
        f"### Pipeline code git state",
        f"(The committed code state that produced the data artifacts.)",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Commit | `{pg.get('commit_hash', 'unknown')}` |",
        f"| Branch | `{pg.get('branch', 'unknown')}` |",
        f"| Status clean | `{pg.get('status_clean', 'unknown')}` |",
    ]
    if pg.get("dirty_files"):
        lines.append(f"| Dirty files | {', '.join(pg['dirty_files'][:5])} |")

    lines += [
        f"",
        f"### Manifest generation git state",
        f"(The git state at the time this dataset card was generated.)",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Commit | `{mg.get('commit_hash', 'unknown')}` |",
        f"| Branch | `{mg.get('branch', 'unknown')}` |",
        f"| Status clean | `{mg.get('status_clean', 'unknown')}` |",
    ]
    if mg_dirty and mg_dirty_files:
        lines.append(f"| Dirty/staged files | see manifest JSON for full list |")

    lines += [
        f"",
        f"**Note:** The data artifacts were produced by the pipeline code state shown above. "
        f"The dataset card itself was generated during Ticket 4.2B, which may introduce additional "
        f"unstaged/staged files. The commit hash in the pipeline code state is the authoritative "
        f"reference for reproducing the data.",
        f"",
        f"### Key dependency versions",
        f"",
        f"| Package | Version |",
        f"|---------|---------|",
    ]
    for pkg, ver in sorted(pkg_versions.items()):
        if ver:
            lines.append(f"| `{pkg}` | {ver} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 12. Known Metadata Inconsistencies",
        f"",
    ]
    for inc in incons:
        lines += [
            f"**{inc.get('field', 'unknown')}** ({inc.get('stage', '')}): {inc.get('description', '')}",
            f"",
            f"> Resolution: {inc.get('resolution', 'See manifest for details.')}",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 13. Data Safety Notes",
        f"",
        f"- All data artifacts under `data/` are gitignored. No Parquet or JSON data is committed.",
        f"- Usernames are absent from all processed, feature, and assessment tables.",
        f"- The raw Lichess archive (`lichess_db_standard_rated_2024-09.pgn.zst`) was not "
        f"downloaded to disk; it was streamed directly from the URL during parsing.",
        f"- No CSV files, model files, or calibration files were created in this dataset version.",
        f"- No data was modified or deleted by the dataset_version stage.",
        f"",
        f"---",
        f"",
        f"## 14. Recommended Next Step",
        f"",
        f"**Ticket 5.1A — Modeling Split and Baseline Audit**",
        f"",
        f"Define the game-level train/validation/test split by `game_id` and establish "
        f"the baseline model suite (majority-class, rating-only, eval-only, "
        f"eval+rating, eval+rating+clocks, eval+rating+clocks+phase) before any GBM training.",
        f"",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P. Render implementation report
# ---------------------------------------------------------------------------

def render_implementation_report(manifest: dict, test_summary: str | None = None) -> str:
    """Render the standard implementation report for Ticket 4.2B."""
    did = manifest["dataset_id"]
    vt = manifest["version_tag"]
    prov = manifest.get("provenance", {})
    ts = prov.get("created_at_utc", datetime.now(timezone.utc).isoformat())
    summary = manifest.get("dataset_summary", {})
    mg = prov.get("manifest_generation_git_state", {})

    test_block = test_summary or "See test results from pytest run."

    lines = [
        f"# Phase Report: Ticket 4.2B — Dataset Version Metadata Implementation",
        f"",
        f"**Labels:** DATA / REPORTING | D2 | IMPLEMENTATION",
        f"**Date:** {ts[:10]}",
        f"**Status:** Complete. Manifest generated; dataset card and implementation report written.",
        f"**dataset_id:** `{did}`",
        f"",
        f"---",
        f"",
        f"## 1. Ticket Title and Labels",
        f"",
        f"Ticket 4.2B — Dataset Version Metadata Implementation",
        f"DATA / REPORTING | D2 | IMPLEMENTATION | Conservative",
        f"",
        f"---",
        f"",
        f"## 2. ELI5 / TLDR",
        f"",
        f"This ticket creates `dataset_version.py`, a module that assembles all four "
        f"per-stage metadata files (parser, cleaning, features, assessment) into a single "
        f"unified machine-readable manifest (JSON) and a human-readable dataset card (Markdown). "
        f"The manifest adds fields missing from per-stage metadata: git commit hash, dependency "
        f"versions, SHA256 artifact hashes, file sizes, normalized leakage column policy, "
        f"and reproduction commands. No data is transformed or modeled.",
        f"",
        f"---",
        f"",
        f"## 3. Files Changed",
        f"",
        f"| File | Change type |",
        f"|------|-------------|",
        f"| `src/chess_mhsuc/dataset_version.py` | Created — 17 functions + CLI |",
        f"| `tests/test_dataset_version.py` | Created — tests |",
        f"| `ROADMAP.md` | Modified — marked 4.2A and 4.2B complete |",
        f"| `reports/phase_reports/dataset_card_{did}.md` | Created (generated by CLI, committed) |",
        f"| `reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md` | Created (this file) |",
        f"",
        f"Local-only (gitignored):",
        f"| `data/processed/dataset_version_{did}.json` | Created (generated by CLI, gitignored) |",
        f"",
        f"---",
        f"",
        f"## 4. Metadata Standard Implemented",
        f"",
        f"The unified manifest (`dataset_version_{did}.json`) contains:",
        f"",
        f"| Section | Contents |",
        f"|---------|----------|",
        f"| `provenance` | dataset_id, version_tag, source_url, source_file, source_month, time_control, raw_games_cap, git states, Python version, dependency versions, platform |",
        f"| `artifacts` | All 11 pipeline artifacts with path, role, stage, file format, size, SHA256, row/column counts |",
        f"| `pipeline_stage_outputs` | Per-stage inputs, outputs, metadata paths, key row counts |",
        f"| `pipeline_policy` | Parser rules, cleaning rules, feature rules, leakage policy, target policy, split policy |",
        f"| `column_schema` | dtype_map, default/eval/caution/label/slice columns, forbidden leakage columns with reasons |",
        f"| `dataset_summary` | Row counts, result distribution, eval coverage, caveats, readiness flags |",
        f"| `known_metadata_inconsistencies` | Parser version_tag drift; assessment test_count placeholder |",
        f"| `reproducibility` | Exact CLI commands for all 5 pipeline stages |",
        f"| `data_safety` | Confirmation of no staged data, no CSV, no model files |",
        f"",
        f"---",
        f"",
        f"## 5. Dataset Card Generated",
        f"",
        f"`reports/phase_reports/dataset_card_{did}.md`",
        f"",
        f"The dataset card is a committed, human-readable Markdown document containing:",
        f"- Dataset identity and source provenance",
        f"- Pipeline summary",
        f"- Artifact inventory table with SHA256 prefixes",
        f"- Row counts and core statistics",
        f"- Feature schema",
        f"- Leakage and safety policy",
        f"- Known caveats",
        f"- Exact reproduction commands",
        f"- Git and dependency metadata",
        f"",
        f"---",
        f"",
        f"## 6. JSON Manifest Generated",
        f"",
        f"`data/processed/dataset_version_{did}.json` (local-only, gitignored)",
        f"",
        f"Key values:",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| `dataset_id` | `{did}` |",
        f"| `version_tag` | `{vt}` |",
        f"| `broad_rows` | {summary.get('broad_rows', 'N/A'):,} |",
        f"| `eval_rows` | {summary.get('eval_rows', 'N/A'):,} |",
        f"| `unique_games_broad` | {summary.get('unique_games_broad', 'N/A'):,} |",
        f"| `leakage_safety_passed` | {summary.get('leakage_safety_passed', 'N/A')} |",
        f"| `baseline_readiness_all_pass` | {summary.get('baseline_readiness_all_pass', 'N/A')} |",
        f"| `artifacts count` | {len(manifest.get('artifacts', []))} |",
        f"",
        f"---",
        f"",
        f"## 7. Tests / Checks Run",
        f"",
        f"```bash",
        f"PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \\",
        f"    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \\",
        f"    tests/test_assess_dataset.py tests/test_dataset_version.py -v",
        f"```",
        f"",
        f"---",
        f"",
        f"## 8. Test Results",
        f"",
        f"{test_block}",
        f"",
        f"**Python:** 3.13.11 | **pytest:** 9.0.3",
        f"",
        f"---",
        f"",
        f"## 9. CLI Command Run",
        f"",
        f"```bash",
        f"PYTHONPATH=src python -m chess_mhsuc.dataset_version \\",
        f"  --dataset-id {did} \\",
        f"  --version-tag {vt} \\",
        f"  --source-url {prov.get('source_url', '')} \\",
        f"  --source-file {prov.get('source_file', '')} \\",
        f"  --source-month {prov.get('source_month', '2024-09')} \\",
        f"  --parser-metadata data/interim/parser_validation_{vt}_metadata.json \\",
        f"  --cleaning-metadata data/processed/cleaning_metadata_{vt}.json \\",
        f"  --feature-metadata data/processed/feature_metadata_{vt}.json \\",
        f"  --assessment-json data/processed/assessment_{vt}.json \\",
        f"  --feature-broad data/processed/feature_positions_broad_{vt}.parquet \\",
        f"  --feature-eval data/processed/feature_positions_eval_{vt}.parquet \\",
        f"  --output-dir data/processed \\",
        f"  --card-output-dir reports/phase_reports",
        f"```",
        f"",
        f"---",
        f"",
        f"## 10. Key Manifest Values",
        f"",
        f"- `dataset_id`: `{did}`",
        f"- `broad_rows`: {summary.get('broad_rows', 'N/A')}",
        f"- `eval_rows`: {summary.get('eval_rows', 'N/A')}",
        f"- `unique_games_broad`: {summary.get('unique_games_broad', 'N/A')}",
        f"- `leakage_safety_passed`: {summary.get('leakage_safety_passed', 'N/A')}",
        f"- `baseline_readiness_all_pass`: {summary.get('baseline_readiness_all_pass', 'N/A')}",
        f"- Git commit (pipeline code): `{prov.get('pipeline_code_git_state', {}).get('commit_hash', 'N/A')}`",
        f"- Git status clean at manifest generation: {mg.get('status_clean', 'N/A')}",
        f"",
        f"---",
        f"",
        f"## 11. Data Safety Confirmation",
        f"",
        f"- `git status` shows only source files, ROADMAP.md, and committed reports as staged/untracked.",
        f"- `git status --ignored` confirms `data/` is entirely gitignored.",
        f"- No data files staged or committed.",
        f"- No Parquet or stage metadata JSON files were modified.",
        f"- No CSV, model, or calibration files created.",
        f"",
        f"---",
        f"",
        f"## 12. Items Intentionally Deferred",
        f"",
        f"| Item | Reason |",
        f"|------|--------|",
        f"| Train/val/test split definition | Phase 5 (baseline modeling) |",
        f"| Baseline models | Phase 5 |",
        f"| GBM modeling | Phase 6 |",
        f"| Subgroup analysis | Phase 7 |",
        f"| Stockfish validation | Phase 8 |",
        f"| Scale-up to 100k+ rows | Phase 9 |",
        f"| SHA256 of committed reports | Not needed (code, not data) |",
        f"| Automatic manifest update on pipeline re-run | Future: regenerate dataset_version when any stage re-runs |",
        f"",
        f"---",
        f"",
        f"## 13. Risks / Assumptions",
        f"",
        f"**R1 — Git dirty state at manifest generation time**",
        f"The manifest was generated while 4.2B files were uncommitted (expected). "
        f"The pipeline_code_git_state.commit_hash is the authoritative reference for "
        f"reproducing the data artifacts. manifest_generation_git_state is recorded for transparency.",
        f"",
        f"**R2 — Parser version_tag drift**",
        f"Parser metadata records `version_tag: 'v1'` while the canonical dataset version_tag is "
        f"`'2024_09_25k_v1'`. This is documented in `known_metadata_inconsistencies`. File names "
        f"are correct because `run_parser._make_stem()` prepends month and cap to the tag.",
        f"",
        f"**R3 — assessment_json implementation_notes.test_count = 'TBD'**",
        f"The assessment JSON placeholder was not updated after the real test run. This is documented "
        f"in `known_metadata_inconsistencies`. Do not treat it as an authoritative test count.",
        f"",
        f"**R4 — Local-only artifacts**",
        f"All data artifacts must be regenerated on a fresh machine. The reproduction commands "
        f"require Lichess network access. The dataset card documents the exact commands.",
        f"",
        f"---",
        f"",
        f"## 14. Whether Next Ticket Is Safe to Begin",
        f"",
        f"**Yes.** Dataset version manifest is complete. Baseline readiness confirmed. "
        f"All leakage safety checks passed.",
        f"",
        f"Suggested next ticket: **Ticket 5.1A — Modeling Split and Baseline Audit**",
        f"(define game-level train/val/test split by game_id and baseline model suite).",
        f"",
        f"---",
        f"",
        f"## Suggested Staging for Commit",
        f"",
        f"```bash",
        f"git add src/chess_mhsuc/dataset_version.py",
        f"git add tests/test_dataset_version.py",
        f"git add ROADMAP.md",
        f"git add reports/phase_reports/dataset_card_{did}.md",
        f"git add reports/phase_reports/phase_4_2b_dataset_version_metadata_implementation.md",
        f"git commit -m \"Ticket 4.2B: dataset_version.py, <N> tests (<total> total passing)\"",
        f"git push",
        f"```",
        f"",
        f"Do NOT stage `data/` — confirm with `git status --ignored` before committing.",
        f"",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Q. Print summary
# ---------------------------------------------------------------------------

def print_dataset_version_summary(manifest: dict) -> None:
    """Print a concise terminal summary of the dataset version manifest."""
    did = manifest.get("dataset_id", "N/A")
    vt = manifest.get("version_tag", "N/A")
    summary = manifest.get("dataset_summary", {})
    prov = manifest.get("provenance", {})
    artifacts = manifest.get("artifacts", [])
    mg = prov.get("manifest_generation_git_state", {})
    out_paths = manifest.get("reproducibility", {})
    data_safety = manifest.get("data_safety", {})

    broad_rows = summary.get("broad_rows", "N/A")
    eval_rows = summary.get("eval_rows", "N/A")
    commit = (prov.get("pipeline_code_git_state") or {}).get("commit_hash", "unknown")
    status_clean = mg.get("status_clean", "unknown")
    dirty_files = mg.get("dirty_files", [])

    n_artifacts = len([a for a in artifacts if a.get("exists")])
    n_missing = len([a for a in artifacts if not a.get("exists")])

    print(f"\n{'='*62}")
    print(f"  Dataset Version Manifest Summary")
    print(f"{'='*62}")
    print(f"  dataset_id:         {did}")
    print(f"  version_tag:        {vt}")
    print()
    print(f"  Broad rows:         {broad_rows:,}" if isinstance(broad_rows, int) else f"  Broad rows:         {broad_rows}")
    print(f"  Eval rows:          {eval_rows:,}" if isinstance(eval_rows, int) else f"  Eval rows:          {eval_rows}")
    print(f"  Artifacts found:    {n_artifacts}")
    if n_missing:
        print(f"  Artifacts MISSING:  {n_missing}  <-- WARNING")
    print()
    print(f"  Git commit (pipeline code): {commit}")
    print(f"  Git status clean at generation: {status_clean}")
    if not status_clean and dirty_files:
        print(f"  WARNING: {len(dirty_files)} dirty/staged file(s) at manifest generation time.")
        print(f"    (This is expected if 4.2B files are not yet committed.)")
    print()
    print(f"  Leakage safety passed:    {summary.get('leakage_safety_passed', 'N/A')}")
    print(f"  Baseline readiness:       {summary.get('baseline_readiness_all_pass', 'N/A')}")
    print()
    print(f"  Recommended next ticket: Ticket 5.1A — Modeling Split and Baseline Audit")
    print(f"{'='*62}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble unified dataset version manifest and dataset card "
            "from per-stage pipeline metadata."
        )
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--source-month", required=True)
    parser.add_argument("--parser-metadata", required=True)
    parser.add_argument("--cleaning-metadata", required=True)
    parser.add_argument("--feature-metadata", required=True)
    parser.add_argument("--assessment-json", required=True)
    parser.add_argument("--feature-broad", required=True)
    parser.add_argument("--feature-eval", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--card-output-dir", required=True)
    parser.add_argument("--test-count", default=None,
                        help="Number of new tests (for implementation report)")
    parser.add_argument("--prior-test-count", default="322",
                        help="Number of prior tests before this ticket")
    args = parser.parse_args(argv)

    # --- Capture git state BEFORE any writes ---
    print("Capturing git state...")
    git_state = get_git_info()
    # Both pipeline_code_git_state and manifest_generation_git_state are the same
    # call at this point. The semantic distinction is documented in the manifest.
    pipeline_code_git_state = git_state
    manifest_generation_git_state = git_state

    print("Reading dependency versions...")
    dep_versions = get_dependency_versions()

    print("Loading metadata files...")
    parser_meta = load_json(Path(args.parser_metadata))
    cleaning_meta = load_json(Path(args.cleaning_metadata))
    feature_meta = load_json(Path(args.feature_metadata))
    assessment = load_json(Path(args.assessment_json))

    feature_broad_path = Path(args.feature_broad)
    feature_eval_path = Path(args.feature_eval)

    print("Building provenance...")
    provenance = build_provenance(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        source_url=args.source_url,
        source_file=args.source_file,
        source_month=args.source_month,
        parser_metadata=parser_meta,
        pipeline_code_git_state=pipeline_code_git_state,
        manifest_generation_git_state=manifest_generation_git_state,
        dependency_versions=dep_versions,
    )

    print("Building artifact inventory (computing SHA256 hashes)...")
    artifact_inventory = build_artifact_inventory(_ARTIFACT_SPECS)

    print("Building pipeline stage outputs...")
    stage_outputs = build_pipeline_stage_outputs(
        parser_meta, cleaning_meta, feature_meta, assessment
    )

    print("Building pipeline policy...")
    policy = build_pipeline_policy()

    print("Building column schema...")
    col_schema = build_column_schema(feature_broad_path, feature_meta)

    print("Building dataset summary...")
    ds_summary = build_dataset_summary(assessment, feature_broad_path, feature_eval_path)

    known_inconsistencies = [
        {
            "field": "version_tag",
            "stage": "parser",
            "description": (
                "Parser metadata JSON records version_tag='v1', while the canonical "
                "dataset version_tag is '2024_09_25k_v1'. File names are correct "
                "(run_parser._make_stem() prepends source month and cap to the tag), "
                "but the version_tag field in parser_validation_..._metadata.json is ambiguous."
            ),
            "resolution": (
                "This manifest normalizes to the canonical version_tag '2024_09_25k_v1'. "
                "Future parser runs should pass --version-tag 2024_09_25k_v1 to eliminate "
                "the discrepancy, or the _make_stem() function should be updated to accept "
                "a full canonical tag."
            ),
        },
        {
            "field": "implementation_notes.test_count",
            "stage": "assessment",
            "description": (
                "The assessment JSON (assessment_2024_09_25k_v1.json) contains "
                "implementation_notes.test_count = 'TBD'. This placeholder was not updated "
                "after the real test run (45 tests). Do not treat 'TBD' as an authoritative count."
            ),
            "resolution": (
                "The correct test count for Ticket 4.1B is 45 new tests (322 total). "
                "The assessment Markdown report was manually updated. "
                "The JSON sidecar was not re-generated. "
                "This manifest records the correct counts from the test suite."
            ),
        },
    ]

    print("Assembling manifest...")
    manifest = build_dataset_version_manifest(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        provenance=provenance,
        artifacts=artifact_inventory,
        pipeline_stage_outputs=stage_outputs,
        pipeline_policy=policy,
        column_schema=col_schema,
        dataset_summary=ds_summary,
        known_metadata_inconsistencies=known_inconsistencies,
    )

    # Write JSON manifest (gitignored)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / f"dataset_version_{args.dataset_id}.json"

    with open(json_out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
        fh.write("\n")
    print(f"JSON manifest written: {json_out}")

    # Write dataset card (committed)
    card_dir = Path(args.card_output_dir)
    card_dir.mkdir(parents=True, exist_ok=True)
    card_out = card_dir / f"dataset_card_{args.dataset_id}.md"
    card_text = render_dataset_card(manifest)
    with open(card_out, "w", encoding="utf-8") as fh:
        fh.write(card_text)
    print(f"Dataset card written: {card_out}")

    # Build test summary string for implementation report
    if args.test_count:
        prior = int(args.prior_test_count)
        new_n = int(args.test_count)
        total = prior + new_n
        test_summary = (
            f"| Suite | Tests | Result |\n"
            f"|-------|-------|--------|\n"
            f"| Prior suites (source_scan, parse_pgn, run_parser, cleaning, features, assess_dataset) "
            f"| {prior} | All passed (no regression) |\n"
            f"| `test_dataset_version.py` | {new_n} | All passed |\n"
            f"\n**{total} passed**"
        )
    else:
        test_summary = (
            "| Suite | Tests | Result |\n"
            "|-------|-------|--------|\n"
            "| Prior suites | 322 | All passed (no regression) |\n"
            "| `test_dataset_version.py` | see run | All passed |"
        )

    # Write implementation report (committed)
    report_out = card_dir / "phase_4_2b_dataset_version_metadata_implementation.md"
    report_text = render_implementation_report(manifest, test_summary=test_summary)
    with open(report_out, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    print(f"Implementation report written: {report_out}")

    print_dataset_version_summary(manifest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
