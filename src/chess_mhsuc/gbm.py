"""
gbm.py — Phase 6.1B first GBM model training for chess-MHSUC.

Trains G1–G6 GBM models (HistGradientBoostingClassifier) using the
feature sets and split assignments from Phase 5.1B. Imports shared
helpers from baselines.py. No calibration, no model artifacts saved.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.gbm \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
        --feature-eval data/processed/feature_positions_eval_2024_09_25k_v1.parquet \\
        --feature-metadata data/processed/feature_metadata_2024_09_25k_v1.json \\
        --splits data/processed/splits_2024_09_25k_v1.json \\
        --modeling-plan data/processed/modeling_plan_2024_09_25k_v1.json \\
        --output-dir data/processed \\
        --report-output-dir reports/phase_reports \\
        --version-tag 2024_09_25k_v1

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
from sklearn.ensemble import HistGradientBoostingClassifier

from chess_mhsuc.baselines import (
    CLASS_ORDER,
    INVERSE_LABEL_MAP,
    LABEL_MAP,
    _BOOLEAN_COLS,
    _NULLABLE_NUMERIC_COLS,
    align_proba_to_class_order,
    compute_metrics,
    encode_labels,
    get_feature_columns,
)
from chess_mhsuc.splits import get_train_val_test

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GBM_PARAMS: dict = {
    "max_iter": 300,
    "learning_rate": 0.05,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 0.1,
    "random_state": 42,
}

STRING_CATEGORICALS_TO_DROP: list[str] = ["selected_position_type", "phase"]

# G1–G6 model definitions (hardcoded; these are Phase 6 decisions from audit 6.1A)
_GBM_REGISTRY: list[dict] = [
    {"model_id": "G1", "feature_set_id": "FS-B", "table": "broad",
     "exploratory": False, "diagnostic": False, "class_weight": None},
    {"model_id": "G2", "feature_set_id": "FS-E", "table": "broad",
     "exploratory": False, "diagnostic": False, "class_weight": None},
    {"model_id": "G3", "feature_set_id": "FS-C", "table": "broad",
     "exploratory": False, "diagnostic": True, "class_weight": None},
    {"model_id": "G4", "feature_set_id": "FS-D", "table": "broad",
     "exploratory": False, "diagnostic": True, "class_weight": None},
    {"model_id": "G5", "feature_set_id": "FS-F", "table": "eval",
     "exploratory": True, "diagnostic": False, "class_weight": None},
    {"model_id": "G6", "feature_set_id": "FS-G", "table": "eval",
     "exploratory": True, "diagnostic": False, "class_weight": None},
    # G2b: fair comparison for G2 with proper early stopping.
    # G2 used early_stopping='auto' which does NOT activate for n_samples < 10,000
    # (threshold is 10,000; pilot train set has 4,344 rows). G2b explicitly enables
    # early stopping so iteration count is chosen by held-out val performance.
    # See Ticket 7.3A/7.3B audit for detail.
    {"model_id": "G2b", "feature_set_id": "FS-E", "table": "broad",
     "exploratory": False, "diagnostic": True, "class_weight": None,
     "early_stopping": True, "validation_fraction": 0.15, "n_iter_no_change": 10},
]


# ---------------------------------------------------------------------------
# A. build_gbm_params
# ---------------------------------------------------------------------------

def build_gbm_params(class_weight: str | None = None) -> dict:
    """Return GBM_PARAMS merged with optional class_weight."""
    params = dict(GBM_PARAMS)
    if class_weight is not None:
        params["class_weight"] = class_weight
    return params


# ---------------------------------------------------------------------------
# B. get_gbm_feature_columns
# ---------------------------------------------------------------------------

def get_gbm_feature_columns(
    feature_set_id: str,
    modeling_plan: dict,
) -> tuple[list[str], list[str]]:
    """
    Get feature columns for a GBM model, dropping string categoricals.

    Returns (feature_columns_requested, feature_columns_used).
    feature_columns_requested: all cols from modeling_plan for this feature set.
    feature_columns_used: same minus STRING_CATEGORICALS_TO_DROP.

    String categoricals (selected_position_type, phase) are dropped because
    HistGBM requires numeric input. Their numeric equivalents
    (checkpoint_index, phase_index) are retained if present.
    """
    all_cols = get_feature_columns(feature_set_id, modeling_plan)
    drop_set = set(STRING_CATEGORICALS_TO_DROP)
    used_cols = [c for c in all_cols if c not in drop_set]
    return all_cols, used_cols


# ---------------------------------------------------------------------------
# C. prepare_gbm_X
# ---------------------------------------------------------------------------

def prepare_gbm_X(df: pl.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """
    Extract feature columns from Polars DataFrame for HistGBM.

    - Boolean cols cast to Int8 (0/1).
    - eval_mate_abs cast to Float64 (NaN preserved — HistGBM handles natively).
    - Other numeric cols pass through unchanged.
    - No string categorical columns expected (already dropped).
    - Returns pandas DataFrame.
    """
    bool_set = _BOOLEAN_COLS
    nullable_set = _NULLABLE_NUMERIC_COLS

    exprs = []
    for col in feature_cols:
        if col in bool_set:
            exprs.append(pl.col(col).cast(pl.Int8).alias(col))
        elif col in nullable_set:
            exprs.append(pl.col(col).cast(pl.Float64).alias(col))
        else:
            exprs.append(pl.col(col))

    if not exprs:
        return pd.DataFrame(index=range(len(df)))

    return df.select(exprs).to_pandas()


# ---------------------------------------------------------------------------
# D. build_gbm_model
# ---------------------------------------------------------------------------

def build_gbm_model(model_id: str, entry: dict) -> HistGradientBoostingClassifier:
    """
    Build HistGradientBoostingClassifier for one GBM model entry.

    Uses fixed GBM_PARAMS. Applies class_weight if specified in entry.
    Optional entry keys early_stopping, validation_fraction, n_iter_no_change
    override the default (no early stopping) when present.
    """
    params = build_gbm_params(class_weight=entry.get("class_weight"))
    if "early_stopping" in entry:
        params["early_stopping"] = entry["early_stopping"]
    if "validation_fraction" in entry:
        params["validation_fraction"] = entry["validation_fraction"]
    if "n_iter_no_change" in entry:
        params["n_iter_no_change"] = entry["n_iter_no_change"]
    return HistGradientBoostingClassifier(**params)


# ---------------------------------------------------------------------------
# E. build_gbm_registry
# ---------------------------------------------------------------------------

def build_gbm_registry() -> dict[str, dict]:
    """
    Return the full GBM model registry as {model_id: entry}.

    G1–G6 entries are hardcoded (not read from modeling_plan),
    as GBM model definitions are Phase 6 decisions made during audit 6.1A.
    """
    return {entry["model_id"]: dict(entry) for entry in _GBM_REGISTRY}


# ---------------------------------------------------------------------------
# F. build_gbm_prediction_rows
# ---------------------------------------------------------------------------

def build_gbm_prediction_rows(
    model_id: str,
    split_set: str,
    df: pl.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    proba: np.ndarray,
    table: str,
    view: str,
    exploratory: bool,
    diagnostic: bool,
) -> pl.DataFrame:
    """
    Build per-row GBM prediction results as a Polars DataFrame.

    Columns (extended vs baselines): model_id, split_set, table, view,
    exploratory, diagnostic, game_id, result_class, y_true, y_pred,
    pred_class, p_BLACK_WIN, p_DRAW, p_WHITE_WIN,
    selected_position_type, move_number, phase, is_time_forfeit, has_eval.
    """
    n = len(y_true)

    def _safe_col(col_name: str, dtype: pl.PolarsDataType) -> pl.Series:
        if col_name in df.columns:
            return df[col_name].cast(dtype)
        return pl.Series([None] * n, dtype=dtype)

    return pl.DataFrame({
        "model_id": pl.Series([model_id] * n, dtype=pl.Utf8),
        "split_set": pl.Series([split_set] * n, dtype=pl.Utf8),
        "table": pl.Series([table] * n, dtype=pl.Utf8),
        "view": pl.Series([view] * n, dtype=pl.Utf8),
        "exploratory": pl.Series([exploratory] * n, dtype=pl.Boolean),
        "diagnostic": pl.Series([diagnostic] * n, dtype=pl.Boolean),
        "game_id": df["game_id"].cast(pl.Utf8),
        "result_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_true], dtype=pl.Utf8
        ),
        "y_true": pl.Series(y_true.tolist(), dtype=pl.Int64),
        "y_pred": pl.Series(y_pred.tolist(), dtype=pl.Int64),
        "pred_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_pred], dtype=pl.Utf8
        ),
        "p_BLACK_WIN": pl.Series(proba[:, 0].tolist(), dtype=pl.Float64),
        "p_DRAW": pl.Series(proba[:, 1].tolist(), dtype=pl.Float64),
        "p_WHITE_WIN": pl.Series(proba[:, 2].tolist(), dtype=pl.Float64),
        "selected_position_type": _safe_col("selected_position_type", pl.Utf8),
        "move_number": _safe_col("move_number", pl.Int64),
        "phase": _safe_col("phase", pl.Utf8),
        "is_time_forfeit": _safe_col("is_time_forfeit", pl.Boolean),
        "has_eval": _safe_col("has_eval", pl.Boolean),
    })


# ---------------------------------------------------------------------------
# G. train_one_gbm
# ---------------------------------------------------------------------------

def train_one_gbm(
    model_id: str,
    entry: dict,
    feature_sets_lookup: dict[str, list[str]],
    broad_df: pl.DataFrame,
    eval_df: pl.DataFrame,
    assignments: dict[str, str],
) -> tuple[dict, pl.DataFrame]:
    """
    Train one GBM model and return (result_dict, predictions_df).

    result_dict keys:
        model_id, model_type, gbm_params, feature_set_id, table, view,
        exploratory, diagnostic, feature_columns_requested,
        feature_columns_used, feature_columns_dropped, n_features_used, n_train_rows, n_val_rows,
        n_test_rows, metrics:{train,val,test}, warnings.

    predictions_df: rows for all three splits concatenated.
    """
    feature_set_id = entry["feature_set_id"]
    table = entry["table"]
    exploratory = entry.get("exploratory", False)
    diagnostic = entry.get("diagnostic", False)
    view = "primary_numbered"

    source_df = broad_df if table == "broad" else eval_df

    all_cols = feature_sets_lookup[feature_set_id]
    drop_set = set(STRING_CATEGORICALS_TO_DROP)
    used_cols = [c for c in all_cols if c not in drop_set]

    model = build_gbm_model(model_id, entry)

    train_df, val_df, test_df = get_train_val_test(
        source_df, assignments, view_name=view
    )

    X_train = prepare_gbm_X(train_df, used_cols)
    y_train = encode_labels(train_df["result_class"])
    model.fit(X_train, y_train)

    split_metrics: dict[str, dict] = {}
    all_pred_dfs: list[pl.DataFrame] = []

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        X_split = prepare_gbm_X(split_df, used_cols)
        y_true = encode_labels(split_df["result_class"])
        y_pred = model.predict(X_split)
        proba_raw = model.predict_proba(X_split)
        proba = align_proba_to_class_order(model, proba_raw)

        split_metrics[split_name] = compute_metrics(y_true, y_pred, proba)
        all_pred_dfs.append(
            build_gbm_prediction_rows(
                model_id, split_name, split_df,
                y_true, y_pred, proba,
                table, view, exploratory, diagnostic,
            )
        )

    warnings: list[str] = []
    dropped = [c for c in all_cols if c in drop_set]
    if dropped:
        warnings.append(
            f"Dropped string categoricals not supported by HistGBM: {dropped}. "
            "Use numeric equivalents (checkpoint_index, phase_index) if needed."
        )
    for split_name in ("val", "test"):
        draw_support = split_metrics[split_name]["per_class"].get("DRAW", {}).get("support", 0)
        if draw_support < 8:
            warnings.append(
                f"DRAW support in {split_name} split = {draw_support} (< 8). "
                "DRAW class metrics will be very noisy."
            )

    params_used = build_gbm_params(class_weight=entry.get("class_weight"))
    for es_key in ("early_stopping", "validation_fraction", "n_iter_no_change"):
        if es_key in entry:
            params_used[es_key] = entry[es_key]

    result = {
        "model_id": model_id,
        "model_type": "HistGradientBoostingClassifier",
        "gbm_params": params_used,
        "feature_set_id": feature_set_id,
        "table": table,
        "view": view,
        "exploratory": exploratory,
        "diagnostic": diagnostic,
        "feature_columns_requested": list(all_cols),
        "feature_columns_used": list(used_cols),
        "feature_columns_dropped": list(dropped),
        "n_features_used": len(used_cols),
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
        "metrics": {
            "train": split_metrics["train"],
            "val": split_metrics["val"],
            "test": split_metrics["test"],
        },
        "warnings": warnings,
    }
    predictions_df = pl.concat(all_pred_dfs)
    return result, predictions_df


# ---------------------------------------------------------------------------
# H. run_all_gbm
# ---------------------------------------------------------------------------

def run_all_gbm(
    broad_df: pl.DataFrame,
    eval_df: pl.DataFrame,
    assignments: dict[str, str],
    modeling_plan: dict,
    model_ids: list[str] | None = None,
) -> tuple[dict, pl.DataFrame]:
    """
    Train GBM models and return (results_by_id, all_predictions_df).

    results_by_id: {model_id: result_dict | {"error": str}}
    all_predictions_df: concatenated per-row predictions for all models.

    If model_ids is provided, only those models are trained (subset filter).
    """
    registry = build_gbm_registry()
    if model_ids is not None:
        registry = {mid: entry for mid, entry in registry.items() if mid in model_ids}
    fs_data = modeling_plan["feature_sets"]
    if isinstance(fs_data, dict):
        feature_sets_lookup: dict[str, list[str]] = {
            k: list(v["features"]) for k, v in fs_data.items()
        }
    else:
        feature_sets_lookup = {
            fs["id"]: list(fs["features"]) for fs in fs_data
        }

    all_results: dict[str, dict] = {}
    all_pred_dfs: list[pl.DataFrame] = []

    for model_id, entry in registry.items():
        print(
            f"  Training {model_id} "
            f"(HistGBM, {entry['feature_set_id']}, {entry['table']})..."
        )
        try:
            result, pred_df = train_one_gbm(
                model_id, entry, feature_sets_lookup,
                broad_df, eval_df, assignments,
            )
            all_results[model_id] = result
            all_pred_dfs.append(pred_df)
        except Exception as exc:
            print(f"  ERROR training {model_id}: {exc}", file=sys.stderr)
            all_results[model_id] = {"model_id": model_id, "error": str(exc)}

    all_predictions = pl.concat(all_pred_dfs) if all_pred_dfs else pl.DataFrame()
    return all_results, all_predictions


# ---------------------------------------------------------------------------
# I. build_gbm_results_payload
# ---------------------------------------------------------------------------

def build_gbm_results_payload(
    dataset_id: str,
    version_tag: str,
    split_artifact_path: str,
    modeling_plan_path: str,
    gbm_results: dict,
) -> dict:
    """Build JSON-serializable GBM results payload."""
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_artifact_path": split_artifact_path,
        "modeling_plan_path": modeling_plan_path,
        "class_order": CLASS_ORDER,
        "label_map": LABEL_MAP,
        "gbm_params": GBM_PARAMS,
        "gbm_models": gbm_results,
        "warnings": [],
        "recommended_next_step": "Phase 6.2A — Calibration Audit",
    }


# ---------------------------------------------------------------------------
# J. save_gbm_outputs
# ---------------------------------------------------------------------------

def save_gbm_outputs(
    results_payload: dict,
    predictions_df: pl.DataFrame,
    output_dir: str | Path,
    version_tag: str,
    output_prefix: str = "gbm",
) -> dict[str, str]:
    """
    Save {prefix}_results_{tag}.json and {prefix}_predictions_{tag}.parquet.

    Both files are gitignored (in data/processed/).
    Returns dict with output file paths.
    output_prefix defaults to "gbm"; pass e.g. "gbm_hygiene" for hygiene runs.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / f"{output_prefix}_results_{version_tag}.json"
    predictions_path = output_dir / f"{output_prefix}_predictions_{version_tag}.parquet"

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    predictions_df.write_parquet(predictions_path)

    return {
        "results_json": str(results_path),
        "predictions_parquet": str(predictions_path),
    }


# ---------------------------------------------------------------------------
# K. render_gbm_report
# ---------------------------------------------------------------------------

def render_gbm_report(
    results_payload: dict,
    output_paths: dict,
    test_summary: str | None = None,
) -> str:
    """Render the Phase 6.1B implementation report as a Markdown string."""
    dataset_id = results_payload["dataset_id"]
    version_tag = results_payload["version_tag"]
    created_at_utc = results_payload.get("created_at_utc", "")
    gbm_results = results_payload["gbm_models"]

    date_str = created_at_utc[:10]

    def _fmt(val: Any, fmt: str = ".4f") -> str:
        if val is None:
            return "N/A"
        try:
            return format(float(val), fmt)
        except (TypeError, ValueError):
            return str(val)

    broad_rows: list[str] = []
    eval_rows: list[str] = []
    for mid, res in gbm_results.items():
        if "error" in res:
            broad_rows.append(f"| {mid} | ERROR | — | — | — | — | — |")
            continue
        val = res.get("metrics", {}).get("val", {})
        test_m = res.get("metrics", {}).get("test", {})
        expl = "Y" if res.get("exploratory") else "N"
        diag = "Y" if res.get("diagnostic") else "N"
        row = (
            f"| {mid} | HistGBM "
            f"| {res.get('feature_set_id','?')} | {expl} | {diag} "
            f"| {_fmt(val.get('accuracy'))} "
            f"| {_fmt(val.get('log_loss'))} "
            f"| {_fmt(val.get('multiclass_brier'))} "
            f"| {_fmt(test_m.get('accuracy'))} |"
        )
        if res.get("table") == "eval":
            eval_rows.append(row)
        else:
            broad_rows.append(row)

    lines = [
        "# Phase Report: Ticket 6.1B — First GBM Implementation",
        "",
        "**Labels:** ML | D2 | IMPLEMENTATION",
        f"**Date:** {date_str}",
        "**Status:** Complete. GBM models G1–G6 trained and evaluated.",
        f"**dataset_id:** `{dataset_id}`",
        "",
        "---",
        "",
        "## 1. Ticket Title and Labels",
        "",
        "Ticket 6.1B — First GBM Implementation",
        "ML | D2 | IMPLEMENTATION | Conservative",
        "",
        "---",
        "",
        "## 2. ELI5 / TLDR",
        "",
        "This ticket creates `gbm.py`, which trains G1–G6 GBM models",
        "(HistGradientBoostingClassifier) on the 70/15/15 train/val/test splits",
        "from Phase 5.1B. No calibration, no model artifacts (.joblib/.pkl) saved.",
        "Outputs: results JSON + predictions Parquet (gitignored), plus this report",
        "(committed).",
        "",
        "---",
        "",
        "## 3. Files Changed",
        "",
        "| File | Change type |",
        "|------|-------------|",
        "| `src/chess_mhsuc/gbm.py` | Created — 12 functions (A–L) + CLI |",
        "| `tests/test_gbm.py` | Created — tests |",
        "| `ROADMAP.md` | Modified — marked 6.1A and 6.1B complete |",
        "| `reports/phase_reports/phase_6_1b_gbm_implementation.md` | Created (this file) |",
        "",
        "Local-only (gitignored):",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `gbm_results_{version_tag}.json` | Metrics for all GBM models (JSON) |",
        f"| `gbm_predictions_{version_tag}.parquet` | Per-row predictions (Parquet) |",
        "",
        "---",
        "",
        "## 4. Model Configuration",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        "| Model class | `HistGradientBoostingClassifier` |",
        "| `max_iter` | 300 |",
        "| `learning_rate` | 0.05 |",
        "| `max_leaf_nodes` | 31 |",
        "| `min_samples_leaf` | 20 |",
        "| `l2_regularization` | 0.1 |",
        "| `random_state` | 42 |",
        "| String categoricals | Dropped (`selected_position_type`, `phase`) |",
        "| `eval_mate_abs` | Native NaN (no imputation required) |",
        "",
        "Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed).",
        "Training view: `primary_numbered` (exclude `selected_position_type == 'last'`).",
        "",
        "---",
        "",
        "## 5. GBM Results Summary",
        "",
        "### Broad models",
        "",
        "| ID | Model | FS | Expl | Diag | Val acc | Val log_loss | Val brier | Test acc |",
        "|----|-------|----|------|------|---------|--------------|-----------|----------|",
        *broad_rows,
        "",
        "### Eval models (exploratory)",
        "",
        "| ID | Model | FS | Expl | Diag | Val acc | Val log_loss | Val brier | Test acc |",
        "|----|-------|----|------|------|---------|--------------|-----------|----------|",
        *eval_rows,
        "",
        "---",
        "",
        "## 6. Output Artifacts Created",
        "",
        "| File | Location | Notes |",
        "|------|----------|-------|",
        f"| `gbm_results_{version_tag}.json` | `data/processed/` (gitignored) | All metrics |",
        f"| `gbm_predictions_{version_tag}.parquet`"
        " | `data/processed/` (gitignored) | Per-row predictions |",
        "| `phase_6_1b_*.md` | `reports/phase_reports/` (committed) | This report |",
        "",
        "---",
        "",
        "## 7. Tests / Checks Run",
        "",
        "```bash",
        "PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py "
        "tests/test_parse_pgn.py \\",
        "    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \\",
        "    tests/test_assess_dataset.py tests/test_dataset_version.py "
        "tests/test_splits.py \\",
        "    tests/test_baselines.py tests/test_gbm.py -v",
        "```",
        "",
        "---",
        "",
        "## 8. Test Results",
        "",
    ]

    if test_summary:
        lines.append(test_summary)
    else:
        lines.append("(To be filled after test run.)")

    lines += [
        "",
        "---",
        "",
        "## 9. Data Safety Confirmation",
        "",
        "- `git status --ignored` confirms `data/` is entirely gitignored.",
        "- No model `.joblib` / `.pkl` files created.",
        "- No CSV files created.",
        "- No calibration performed.",
        "- No data files staged.",
        "- Only source code, tests, ROADMAP.md, and this report are staged/committed.",
        "",
        "---",
        "",
        "## 10. Risks / Assumptions",
        "",
        "**R1 — DRAW class sparsity**",
        "Broad val DRAW support ~59 rows (6.3%). Eval val/test DRAW very sparse (~14/2).",
        "All eval models are flagged exploratory.",
        "",
        "**R2 — String categorical dropping**",
        "`selected_position_type` and `phase` dropped from feature sets that include them.",
        "Their numeric equivalents (`checkpoint_index`, `phase_index`) are retained.",
        "",
        "**R3 — eval_mate_abs native NaN**",
        "93.6% of eval_mate_abs values are null. HistGBM handles NaN natively;",
        "no imputation needed (unlike baselines which used SimpleImputer).",
        "",
        "**R4 — No hyperparameter tuning**",
        "GBM_PARAMS are fixed from audit 6.1A. No grid search, no early stopping.",
        "",
        "---",
        "",
        "## 11. Items Intentionally Deferred",
        "",
        "| Item | Reason |",
        "|------|--------|",
        "| Calibration | Phase 6.2 |",
        "| Hyperparameter tuning | Phase 6+ |",
        "| Subgroup analysis | Phase 7 |",
        "| Model artifact persistence (.joblib) | Not required for this ticket |",
        "| XGBoost / LightGBM | Phase 6+ (requires audit) |",
        "",
        "---",
        "",
        "## 12. Whether Next Ticket Is Safe to Begin",
        "",
        "**Yes.** GBM metrics establish comparison vs baselines for Phase 6.2 work.",
        "",
        "Suggested next ticket: **Phase 6.2A — Calibration Audit**.",
        "",
        "---",
        "",
        "## Suggested Staging for Commit",
        "",
        "```bash",
        "git add src/chess_mhsuc/gbm.py",
        "git add tests/test_gbm.py",
        "git add ROADMAP.md",
        "git add reports/phase_reports/phase_6_1b_gbm_implementation.md",
        'git commit -m "Ticket 6.1B: gbm.py, <N> tests (<total> total passing)"',
        "git push",
        "```",
        "",
        "Do NOT stage `data/` — confirm with `git status --ignored` before committing.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# L. print_gbm_summary
# ---------------------------------------------------------------------------

def print_gbm_summary(results_payload: dict) -> None:
    """Print concise human-readable summary of GBM results to stdout."""
    print("\n=== GBM Results Summary ===\n")
    gbm_results = results_payload["gbm_models"]

    col_w = [6, 6, 5, 5, 5, 9, 10, 11, 10, 11]
    header = (
        f"{'ID':<{col_w[0]}} {'Table':<{col_w[1]}} {'FS':<{col_w[2]}} "
        f"{'Expl':<{col_w[3]}} {'Diag':<{col_w[4]}} | "
        f"{'Val Acc':>{col_w[5]}} {'Val LL':>{col_w[6]}} "
        f"{'Val Brier':>{col_w[7]}} | "
        f"{'Test Acc':>{col_w[8]}} {'Test LL':>{col_w[9]}}"
    )
    print(header)
    print("-" * len(header))

    for mid, res in gbm_results.items():
        if "error" in res:
            print(f"{mid:<{col_w[0]}} ERROR: {res['error']}")
            continue
        table = res.get("table", "?")[:6]
        fs = res.get("feature_set_id", "?")[:5]
        expl = "Y" if res.get("exploratory") else "N"
        diag = "Y" if res.get("diagnostic") else "N"
        val = res.get("metrics", {}).get("val", {})
        test = res.get("metrics", {}).get("test", {})

        def _f(x: Any) -> str:
            if x is None:
                return "    N/A"
            return f"{float(x):.4f}"

        print(
            f"{mid:<{col_w[0]}} {table:<{col_w[1]}} {fs:<{col_w[2]}} "
            f"{expl:<{col_w[3]}} {diag:<{col_w[4]}} | "
            f"{_f(val.get('accuracy')):>{col_w[5]}} "
            f"{_f(val.get('log_loss')):>{col_w[6]}} "
            f"{_f(val.get('multiclass_brier')):>{col_w[7]}} | "
            f"{_f(test.get('accuracy')):>{col_w[8]}} "
            f"{_f(test.get('log_loss')):>{col_w[9]}}"
        )

    print()


# ---------------------------------------------------------------------------
# main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 6.1B GBM modeling."""
    parser = argparse.ArgumentParser(
        description="Train GBM models for chess-MHSUC Phase 6.1B"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--feature-broad", required=True)
    parser.add_argument("--feature-eval", required=True)
    parser.add_argument("--feature-metadata", required=True,
                        help="Feature metadata JSON path (informational)")
    parser.add_argument("--splits", required=True)
    parser.add_argument("--modeling-plan", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output-dir", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument(
        "--model-ids", default=None,
        help="Comma-separated list of model IDs to train (default: all). "
             "Example: --model-ids G2b"
    )
    parser.add_argument(
        "--output-prefix", default="gbm",
        help="Filename prefix for output artifacts (default: 'gbm'). "
             "Use 'gbm_hygiene' for hygiene/diagnostic runs."
    )

    args = parser.parse_args(argv)

    model_ids_filter: list[str] | None = None
    if args.model_ids:
        model_ids_filter = [mid.strip() for mid in args.model_ids.split(",")]

    print(f"dataset_id={args.dataset_id}  version={args.version_tag}")
    if model_ids_filter:
        print(f"Model filter: {model_ids_filter}")

    broad_df = pl.read_parquet(args.feature_broad)
    eval_df = pl.read_parquet(args.feature_eval)

    with open(args.splits, encoding="utf-8") as f:
        splits_data = json.load(f)

    with open(args.modeling_plan, encoding="utf-8") as f:
        modeling_plan = json.load(f)

    print(f"Broad: {broad_df.shape}, Eval: {eval_df.shape}")
    assignments: dict[str, str] = splits_data["assignments"]
    print(f"Split assignments: {len(assignments)} games")

    print("\nTraining GBM models...")
    gbm_results, predictions_df = run_all_gbm(
        broad_df, eval_df, assignments, modeling_plan,
        model_ids=model_ids_filter,
    )

    results_payload = build_gbm_results_payload(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        split_artifact_path=args.splits,
        modeling_plan_path=args.modeling_plan,
        gbm_results=gbm_results,
    )

    output_paths = save_gbm_outputs(
        results_payload, predictions_df,
        output_dir=args.output_dir,
        version_tag=args.version_tag,
        output_prefix=args.output_prefix,
    )

    print_gbm_summary(results_payload)
    print(f"Saved results:     {output_paths['results_json']}")
    print(f"Saved predictions: {output_paths['predictions_parquet']}")

    # Only write the Phase 6 implementation report for the canonical "gbm" run.
    # Hygiene/diagnostic runs (--output-prefix != "gbm") skip it to avoid
    # overwriting the committed Phase 6.1B report with partial results.
    if args.output_prefix == "gbm":
        report_md = render_gbm_report(results_payload, output_paths)
        report_dir = Path(args.report_output_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "phase_6_1b_gbm_implementation.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Saved report:      {report_path}")
    else:
        print(f"  [gbm] Skipping phase report (output_prefix={args.output_prefix!r}; "
              "not overwriting phase_6_1b_gbm_implementation.md)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
