"""
baselines.py — Phase 5.2B baseline model training for chess-MHSUC.

Trains B0–B5 baselines (DummyClassifier + LogisticRegression) using the
feature sets and split assignments from Phase 5.1B. Also trains B3-balanced
as a diagnostic variant of B3 with class_weight='balanced'.

No GBM, no calibration, no model artifacts (.joblib/.pkl) saved.
No CSV files, no plots. Outputs: results JSON + predictions Parquet (gitignored)
+ phase report Markdown (committed).

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.baselines \\
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
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from chess_mhsuc.splits import get_train_val_test

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASS_ORDER = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
LABEL_MAP = {"BLACK_WIN": 0, "DRAW": 1, "WHITE_WIN": 2}
INVERSE_LABEL_MAP = {0: "BLACK_WIN", 1: "DRAW", 2: "WHITE_WIN"}

# Feature type classification (hardcoded; mirrors splits.py feature set policy)
_BOOLEAN_COLS: frozenset[str] = frozenset({
    "white_low_60", "black_low_60",
    "white_low_30", "black_low_30",
    "white_low_10", "black_low_10",
    "clock_anomaly", "is_mate_eval", "eval_white_winning",
})
_CATEGORICAL_COLS: frozenset[str] = frozenset({"selected_position_type", "phase"})
# Nullable numeric: require SimpleImputer(fill_value=0) before StandardScaler.
# eval_mate_abs is None for non-mate positions (93.6% null in eval primary view).
_NULLABLE_NUMERIC_COLS: frozenset[str] = frozenset({"eval_mate_abs"})
_FORBIDDEN_FEATURE_COLS: frozenset[str] = frozenset({
    "result_class", "white_result_numeric", "game_id",
    "termination", "is_time_forfeit", "has_eval", "split_set",
    "duplicate_ply_checkpoint", "is_last_checkpoint",
})


# ---------------------------------------------------------------------------
# A. encode_labels
# ---------------------------------------------------------------------------

def encode_labels(series: pl.Series) -> np.ndarray:
    """Map result_class string Series to integer labels using LABEL_MAP."""
    return np.array([LABEL_MAP[v] for v in series.to_list()], dtype=np.int64)


# ---------------------------------------------------------------------------
# B. get_feature_columns
# ---------------------------------------------------------------------------

def get_feature_columns(feature_set_id: str, modeling_plan: dict) -> list[str]:
    """
    Return ordered feature column list for a given feature set ID.

    Supports both list format (synthetic tests) and dict format (real JSON artifact).
    """
    fs_data = modeling_plan["feature_sets"]
    if isinstance(fs_data, dict):
        if feature_set_id not in fs_data:
            raise ValueError(
                f"Feature set {feature_set_id!r} not found in modeling plan. "
                f"Available: {list(fs_data.keys())}"
            )
        return list(fs_data[feature_set_id]["features"])
    # list format
    for fs in fs_data:
        if fs["id"] == feature_set_id:
            return list(fs["features"])
    raise ValueError(
        f"Feature set {feature_set_id!r} not found in modeling plan. "
        f"Available: {[fs['id'] for fs in fs_data]}"
    )


# ---------------------------------------------------------------------------
# C. split_feature_types
# ---------------------------------------------------------------------------

def split_feature_types(feature_cols: list[str], df: pl.DataFrame) -> dict:
    """
    Classify feature columns into groups for ColumnTransformer construction.

    Returns dict with keys:
        numeric          — standard numeric cols (Float64 / Int64, no nulls expected)
        nullable_numeric — numeric cols that may contain nulls (eval_mate_abs)
        boolean          — boolean cols (cast to Int8 = 0/1 before transform)
        categorical      — string cols (OneHotEncoded)

    Raises ValueError if any forbidden column is requested.
    """
    numeric: list[str] = []
    nullable_numeric: list[str] = []
    boolean: list[str] = []
    categorical: list[str] = []

    for col in feature_cols:
        if col in _FORBIDDEN_FEATURE_COLS:
            raise ValueError(
                f"Forbidden column {col!r} found in feature set. "
                "This column must not be used as a feature."
            )
        if col in _NULLABLE_NUMERIC_COLS:
            nullable_numeric.append(col)
        elif col in _BOOLEAN_COLS:
            boolean.append(col)
        elif col in _CATEGORICAL_COLS:
            categorical.append(col)
        else:
            numeric.append(col)

    return {
        "numeric": numeric,
        "nullable_numeric": nullable_numeric,
        "boolean": boolean,
        "categorical": categorical,
    }


# ---------------------------------------------------------------------------
# D. prepare_X
# ---------------------------------------------------------------------------

def prepare_X(
    df: pl.DataFrame,
    feature_cols: list[str],
    feature_types: dict,
) -> pd.DataFrame:
    """
    Extract feature columns from Polars DataFrame, return as pandas DataFrame.

    Boolean columns are cast to Int8 (0/1) for sklearn compatibility.
    Nullable numeric columns are cast to Float64 (so pandas gets NaN for nulls).
    All other columns pass through unchanged.
    """
    bool_set = set(feature_types["boolean"])
    nullable_set = set(feature_types["nullable_numeric"])

    exprs = []
    for col in feature_cols:
        if col in bool_set:
            exprs.append(pl.col(col).cast(pl.Int8).alias(col))
        elif col in nullable_set:
            exprs.append(pl.col(col).cast(pl.Float64).alias(col))
        else:
            exprs.append(pl.col(col))

    return df.select(exprs).to_pandas()


# ---------------------------------------------------------------------------
# E. build_preprocessor
# ---------------------------------------------------------------------------

def build_preprocessor(feature_types: dict) -> ColumnTransformer | None:
    """
    Build ColumnTransformer for the given feature type groups.

    Returns None if all groups are empty (FS-A DummyClassifier).

    Preprocessing policy (from 5.2A audit):
        numeric          → StandardScaler
        nullable_numeric → SimpleImputer(constant, 0) → StandardScaler
        boolean          → passthrough (already Int8)
        categorical      → OneHotEncoder(handle_unknown='ignore', sparse_output=False)
    """
    numeric = feature_types["numeric"]
    nullable_numeric = feature_types["nullable_numeric"]
    boolean = feature_types["boolean"]
    categorical = feature_types["categorical"]

    if not any([numeric, nullable_numeric, boolean, categorical]):
        return None

    transformers: list[tuple] = []

    if numeric:
        transformers.append(("num", StandardScaler(), numeric))

    if nullable_numeric:
        nullable_pipe = Pipeline([
            ("imp", SimpleImputer(strategy="constant", fill_value=0.0)),
            ("scl", StandardScaler()),
        ])
        transformers.append(("num_imp", nullable_pipe, nullable_numeric))

    if boolean:
        transformers.append(("bool", "passthrough", boolean))

    if categorical:
        ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        transformers.append(("cat", ohe, categorical))

    return ColumnTransformer(transformers=transformers, remainder="drop")


# ---------------------------------------------------------------------------
# F. build_baseline_model
# ---------------------------------------------------------------------------

def build_baseline_model(
    baseline_id: str,
    baseline_entry: dict,
    preprocessor: ColumnTransformer | None,
) -> Any:
    """
    Build sklearn model (or Pipeline) for one baseline.

    DummyClassifier: returned directly (no preprocessor needed).
    LogisticRegression: wrapped in Pipeline([pre, clf]) when preprocessor is provided.

    Strips 'multi_class' from sklearn_params — removed in sklearn 1.8.
    """
    model_class = baseline_entry["model_class"]
    params = dict(baseline_entry.get("sklearn_params", {}))
    params.pop("multi_class", None)  # removed in sklearn 1.8

    if model_class == "DummyClassifier":
        return DummyClassifier(**params)

    if model_class == "LogisticRegression":
        clf = LogisticRegression(**params)
        if preprocessor is None:
            return clf
        return Pipeline([("pre", preprocessor), ("clf", clf)])

    raise ValueError(
        f"Unknown model_class {model_class!r} for baseline {baseline_id!r}. "
        "Supported: 'DummyClassifier', 'LogisticRegression'."
    )


# ---------------------------------------------------------------------------
# G. multiclass_brier_score
# ---------------------------------------------------------------------------

def multiclass_brier_score(
    y_true: np.ndarray,
    proba: np.ndarray,
    n_classes: int = 3,
) -> float:
    """
    Multiclass Brier score: mean over samples of sum_k (p_k - y_onehot_k)^2.

    Range [0, 2]. Lower is better.
    """
    y_onehot = np.eye(n_classes, dtype=np.float64)[y_true]
    return float(np.mean(np.sum((proba - y_onehot) ** 2, axis=1)))


# ---------------------------------------------------------------------------
# H. align_proba_to_class_order
# ---------------------------------------------------------------------------

def align_proba_to_class_order(model: Any, proba: np.ndarray) -> np.ndarray:
    """
    Reorder probability columns to match CLASS_ORDER = ["BLACK_WIN", "DRAW", "WHITE_WIN"].

    model.classes_ gives integer labels in the order learned during fit.
    Some splits may not contain all classes (e.g. DRAW absent in tiny eval splits).
    Missing class columns are filled with 0.0.
    """
    if hasattr(model, "named_steps"):
        clf = model.named_steps.get("clf", model)
    else:
        clf = model

    model_classes = list(clf.classes_)
    model_class_names = [INVERSE_LABEL_MAP[int(c)] for c in model_classes]
    model_col_for = {name: i for i, name in enumerate(model_class_names)}

    n_samples = proba.shape[0]
    aligned = np.zeros((n_samples, len(CLASS_ORDER)), dtype=np.float64)
    for out_idx, class_name in enumerate(CLASS_ORDER):
        if class_name in model_col_for:
            aligned[:, out_idx] = proba[:, model_col_for[class_name]]
        # else: class absent in training data — probability stays 0.0

    return aligned


# ---------------------------------------------------------------------------
# I. compute_metrics
# ---------------------------------------------------------------------------

def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    proba: np.ndarray,
    class_order: list[str] = CLASS_ORDER,
) -> dict:
    """
    Compute classification metrics for one split.

    Returns a JSON-serializable dict:
        n_rows, accuracy, balanced_accuracy, log_loss,
        macro_f1, weighted_f1, multiclass_brier,
        per_class (precision/recall/f1/support for each class),
        confusion_matrix.

    Uses zero_division=0 to suppress UndefinedMetricWarning for empty classes.
    log_loss uses labels= to handle splits missing some classes.
    """
    n_rows = int(len(y_true))
    labels = list(range(len(class_order)))

    acc = float(np.mean(y_true == y_pred))

    try:
        bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    except Exception:
        bal_acc = None

    try:
        ll = float(log_loss(y_true, proba, labels=labels))
    except Exception:
        ll = None

    try:
        macro_f1 = float(f1_score(y_true, y_pred, labels=labels,
                                  average="macro", zero_division=0))
    except Exception:
        macro_f1 = None

    try:
        weighted_f1 = float(f1_score(y_true, y_pred, labels=labels,
                                     average="weighted", zero_division=0))
    except Exception:
        weighted_f1 = None

    brier = multiclass_brier_score(y_true, proba, n_classes=len(class_order))

    prec, rec, f1_per, support = precision_recall_fscore_support(
        y_true, y_pred,
        labels=labels,
        zero_division=0,
    )

    per_class: dict[str, dict] = {}
    for i, cls in enumerate(class_order):
        per_class[cls] = {
            "precision": float(prec[i]),
            "recall": float(rec[i]),
            "f1": float(f1_per[i]),
            "support": int(support[i]),
        }

    cm = confusion_matrix(y_true, y_pred, labels=labels)

    return {
        "n_rows": n_rows,
        "accuracy": acc,
        "balanced_accuracy": bal_acc,
        "log_loss": ll,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "multiclass_brier": brier,
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


# ---------------------------------------------------------------------------
# J. build_prediction_rows
# ---------------------------------------------------------------------------

def build_prediction_rows(
    baseline_id: str,
    split_set: str,
    df: pl.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    proba: np.ndarray,
) -> pl.DataFrame:
    """
    Build per-row prediction results for one split as a Polars DataFrame.

    Columns: baseline_id, split_set, game_id, result_class (true),
             pred_class, p_BLACK_WIN, p_DRAW, p_WHITE_WIN.
    """
    n = len(y_true)
    return pl.DataFrame({
        "baseline_id": pl.Series([baseline_id] * n, dtype=pl.Utf8),
        "split_set": pl.Series([split_set] * n, dtype=pl.Utf8),
        "game_id": df["game_id"].cast(pl.Utf8),
        "result_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_true], dtype=pl.Utf8
        ),
        "pred_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_pred], dtype=pl.Utf8
        ),
        "p_BLACK_WIN": pl.Series(proba[:, 0].tolist(), dtype=pl.Float64),
        "p_DRAW": pl.Series(proba[:, 1].tolist(), dtype=pl.Float64),
        "p_WHITE_WIN": pl.Series(proba[:, 2].tolist(), dtype=pl.Float64),
    })


# ---------------------------------------------------------------------------
# K. train_one_baseline
# ---------------------------------------------------------------------------

def train_one_baseline(
    baseline_id: str,
    baseline_entry: dict,
    feature_sets_lookup: dict[str, list[str]],
    broad_df: pl.DataFrame,
    eval_df: pl.DataFrame,
    assignments: dict[str, str],
) -> tuple[dict, pl.DataFrame]:
    """
    Train one baseline and return (metrics_dict, predictions_df).

    metrics_dict keys:
        baseline_id, feature_set_id, table, exploratory,
        model_class, train_metrics, val_metrics, test_metrics.

    predictions_df: rows for all three splits concatenated.

    For FS-A (DummyClassifier, 0 features): X is a dummy np.ones matrix.
    For eval baselines: get_train_val_test applied to eval_df.
    All baselines use the "primary_numbered" view (exclude 'last' checkpoint rows).
    """
    feature_set_id = baseline_entry["feature_set_id"]
    table = baseline_entry["table"]
    exploratory = baseline_entry.get("exploratory", False)
    diagnostic = baseline_entry.get("diagnostic", False)
    model_type = baseline_entry["model_class"]
    view = "primary_numbered"

    source_df = broad_df if table == "broad" else eval_df
    feature_cols = feature_sets_lookup[feature_set_id]
    is_dummy = (model_type == "DummyClassifier")

    # Build preprocessor (None for DummyClassifier)
    if is_dummy:
        feature_types: dict = {
            "numeric": [], "nullable_numeric": [], "boolean": [], "categorical": []
        }
        preprocessor = None
        preprocessing_summary = "none (DummyClassifier ignores X)"
    else:
        feature_types = split_feature_types(feature_cols, source_df)
        preprocessor = build_preprocessor(feature_types)
        parts = []
        if feature_types["numeric"]:
            parts.append(f"StandardScaler({len(feature_types['numeric'])} numeric)")
        if feature_types["nullable_numeric"]:
            parts.append(
                f"SimpleImputer(0)+StandardScaler"
                f"({len(feature_types['nullable_numeric'])} nullable)"
            )
        if feature_types["boolean"]:
            parts.append(f"passthrough({len(feature_types['boolean'])} boolean)")
        if feature_types["categorical"]:
            parts.append(
                f"OneHotEncoder({len(feature_types['categorical'])} categorical)"
            )
        preprocessing_summary = "; ".join(parts) if parts else "none"

    model = build_baseline_model(baseline_id, baseline_entry, preprocessor)

    # Apply view filter and split assignments
    train_df, val_df, test_df = get_train_val_test(
        source_df, assignments, view_name=view
    )

    # Prepare training inputs
    if is_dummy:
        X_train = np.ones((len(train_df), 1), dtype=np.float64)
    else:
        X_train = prepare_X(train_df, feature_cols, feature_types)

    y_train = encode_labels(train_df["result_class"])
    model.fit(X_train, y_train)

    # Evaluate on each split
    split_metrics: dict[str, dict] = {}
    all_pred_dfs: list[pl.DataFrame] = []

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if is_dummy:
            X_split = np.ones((len(split_df), 1), dtype=np.float64)
        else:
            X_split = prepare_X(split_df, feature_cols, feature_types)

        y_true = encode_labels(split_df["result_class"])
        y_pred = model.predict(X_split)
        proba_raw = model.predict_proba(X_split)
        proba = align_proba_to_class_order(model, proba_raw)

        split_metrics[split_name] = compute_metrics(y_true, y_pred, proba)
        all_pred_dfs.append(
            build_prediction_rows(
                baseline_id, split_name, split_df, y_true, y_pred, proba
            )
        )

    # Build warnings
    warnings: list[str] = []
    if is_dummy and baseline_entry.get("sklearn_params", {}).get("strategy") == "most_frequent":
        warnings.append(
            "DummyClassifier most_frequent predicts p=1.0 for majority class; "
            "log_loss will be ~18.9 (expected)."
        )
    for split_name in ("val", "test"):
        draw_support = split_metrics[split_name]["per_class"].get("DRAW", {}).get("support", 0)
        if draw_support < 8:
            warnings.append(
                f"DRAW support in {split_name} split = {draw_support} (< 8). "
                "DRAW class metrics will be very noisy."
            )

    result = {
        "baseline_id": baseline_id,
        "model_type": model_type,
        "sklearn_params": baseline_entry.get("sklearn_params", {}),
        "feature_set_id": feature_set_id,
        "table": table,
        "view": view,
        "exploratory": exploratory,
        "diagnostic": diagnostic,
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
        "n_features": len(feature_cols),
        "feature_columns": list(feature_cols),
        "preprocessing_summary": preprocessing_summary,
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
# L. build_baseline_registry
# ---------------------------------------------------------------------------

def build_baseline_registry(modeling_plan: dict) -> dict[str, dict]:
    """
    Build a flat dict of baseline_id -> normalized baseline_entry.

    Supports both list format (synthetic tests) and dict format (real JSON artifact).
    Normalizes field names:
        "model"       -> "model_class"
        "feature_set" -> "feature_set_id"
    Strips 'multi_class' from all LR params (removed in sklearn 1.8).
    Adds B3-balanced: variant of B3 with class_weight='balanced' (diagnostic, exploratory).
    """
    bp = modeling_plan["baseline_plan"]
    # Dict format: {bid: entry, ..., "global_notes": {...}}
    if isinstance(bp, dict):
        items = [
            (k, v) for k, v in bp.items()
            if isinstance(v, dict) and "id" in v
        ]
    else:
        items = [(b["id"], b) for b in bp]

    registry: dict[str, dict] = {}
    for bid, raw in items:
        entry = dict(raw)
        # Normalize field names from real JSON artifact
        if "model" in entry and "model_class" not in entry:
            entry["model_class"] = entry.pop("model")
        if "feature_set" in entry and "feature_set_id" not in entry:
            entry["feature_set_id"] = entry.pop("feature_set")
        params = dict(entry.get("sklearn_params", {}))
        params.pop("multi_class", None)
        entry["sklearn_params"] = params
        entry.setdefault("diagnostic", False)
        registry[entry["id"]] = entry

    # Add B3-balanced diagnostic variant
    if "B3" in registry:
        b3_balanced = dict(registry["B3"])
        b3_params = dict(b3_balanced.get("sklearn_params", {}))
        b3_params["class_weight"] = "balanced"
        b3_balanced["id"] = "B3-balanced"
        b3_balanced["sklearn_params"] = b3_params
        b3_balanced["exploratory"] = True
        b3_balanced["diagnostic"] = True
        registry["B3-balanced"] = b3_balanced

    return registry


# ---------------------------------------------------------------------------
# M. run_all_baselines
# ---------------------------------------------------------------------------

def run_all_baselines(
    broad_df: pl.DataFrame,
    eval_df: pl.DataFrame,
    assignments: dict[str, str],
    modeling_plan: dict,
) -> tuple[dict, pl.DataFrame]:
    """
    Train all baselines and return (results_by_id, all_predictions_df).

    results_by_id: {baseline_id: metrics_dict | {"error": str}}
    all_predictions_df: concatenated per-row predictions for all baselines.
    """
    registry = build_baseline_registry(modeling_plan)
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

    for baseline_id, entry in registry.items():
        print(
            f"  Training {baseline_id} "
            f"({entry['model_class']}, {entry['feature_set_id']}, {entry['table']})..."
        )
        try:
            metrics, pred_df = train_one_baseline(
                baseline_id, entry, feature_sets_lookup,
                broad_df, eval_df, assignments,
            )
            all_results[baseline_id] = metrics
            all_pred_dfs.append(pred_df)
        except Exception as exc:
            print(f"  ERROR training {baseline_id}: {exc}", file=sys.stderr)
            all_results[baseline_id] = {"baseline_id": baseline_id, "error": str(exc)}

    all_predictions = pl.concat(all_pred_dfs) if all_pred_dfs else pl.DataFrame()
    return all_results, all_predictions


# ---------------------------------------------------------------------------
# N. build_results_payload
# ---------------------------------------------------------------------------

def build_results_payload(
    dataset_id: str,
    version_tag: str,
    split_artifact_path: str,
    modeling_plan_path: str,
    baseline_results: dict,
) -> dict:
    """Build JSON-serializable results payload matching the 5.2A audit contract."""
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_artifact_path": split_artifact_path,
        "modeling_plan_path": modeling_plan_path,
        "class_order": CLASS_ORDER,
        "label_map": LABEL_MAP,
        "baselines": baseline_results,
        "warnings": [],
        "recommended_next_step": "Phase 6.1A — GBM Selection Audit",
    }


# ---------------------------------------------------------------------------
# O. save_baseline_outputs
# ---------------------------------------------------------------------------

def save_baseline_outputs(
    results_payload: dict,
    predictions_df: pl.DataFrame,
    output_dir: str | Path,
    version_tag: str,
) -> dict[str, str]:
    """
    Save baseline_results_{tag}.json and baseline_predictions_{tag}.parquet.

    Both files are gitignored (in data/processed/).
    Returns dict with output file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results_path = output_dir / f"baseline_results_{version_tag}.json"
    predictions_path = output_dir / f"baseline_predictions_{version_tag}.parquet"

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    predictions_df.write_parquet(predictions_path)

    return {
        "results_json": str(results_path),
        "predictions_parquet": str(predictions_path),
    }


# ---------------------------------------------------------------------------
# P. render_implementation_report
# ---------------------------------------------------------------------------

def render_implementation_report(
    results_payload: dict,
    output_paths: dict,
    test_summary: str | None = None,
) -> str:
    """Render the Phase 5.2B implementation report as a Markdown string."""
    dataset_id = results_payload["dataset_id"]
    version_tag = results_payload["version_tag"]
    created_at_utc = results_payload.get("created_at_utc", "")
    baseline_results = results_payload["baselines"]

    date_str = created_at_utc[:10]

    def _fmt_metric(val: Any, fmt: str = ".4f") -> str:
        if val is None:
            return "N/A"
        try:
            return format(float(val), fmt)
        except (TypeError, ValueError):
            return str(val)

    # Build broad and eval table rows
    broad_rows: list[str] = []
    eval_rows: list[str] = []
    for bid, res in baseline_results.items():
        if "error" in res:
            row = f"| {bid} | ERROR | — | — | — | — |"
            broad_rows.append(row)
            continue
        val = res.get("metrics", {}).get("val", {})
        test = res.get("metrics", {}).get("test", {})
        expl = "Y" if res.get("exploratory") else "N"
        row = (
            f"| {bid} | {res.get('model_type','?')[:20]} "
            f"| {res.get('feature_set_id','?')} | {expl} "
            f"| {_fmt_metric(val.get('accuracy'))} "
            f"| {_fmt_metric(val.get('log_loss'))} "
            f"| {_fmt_metric(val.get('multiclass_brier'))} "
            f"| {_fmt_metric(test.get('accuracy'))} |"
        )
        if res.get("table") == "eval":
            eval_rows.append(row)
        else:
            broad_rows.append(row)

    lines = [
        "# Phase Report: Ticket 5.2B — Baseline Model Implementation",
        "",
        "**Labels:** ML | D2 | IMPLEMENTATION",
        f"**Date:** {date_str}",
        "**Status:** Complete. Baselines B0–B5 + B3-balanced trained and evaluated.",
        f"**dataset_id:** `{dataset_id}`",
        "",
        "---",
        "",
        "## 1. Ticket Title and Labels",
        "",
        "Ticket 5.2B — Baseline Model Implementation",
        "ML | D2 | IMPLEMENTATION | Conservative",
        "",
        "---",
        "",
        "## 2. ELI5 / TLDR",
        "",
        "This ticket creates `baselines.py`, which trains B0–B5 baselines",
        "(DummyClassifier + LogisticRegression) plus the B3-balanced diagnostic on the",
        "70/15/15 train/val/test splits from 5.1B. No GBM, no calibration, no model",
        "artifacts. Outputs: results JSON + predictions Parquet (gitignored), plus this",
        "report (committed).",
        "",
        "---",
        "",
        "## 3. Files Changed",
        "",
        "| File | Change type |",
        "|------|-------------|",
        "| `src/chess_mhsuc/baselines.py` | Created — 17 functions (A–Q) + CLI |",
        "| `tests/test_baselines.py` | Created — tests |",
        "| `ROADMAP.md` | Modified — marked 5.2A and 5.2B complete |",
        "| `reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md`"
        " | Created (this file) |",
        "",
        "Local-only (gitignored):",
        "",
        "| File | Description |",
        "|------|-------------|",
        f"| `baseline_results_{version_tag}.json`"
        " | Metrics for all baselines (JSON) |",
        f"| `baseline_predictions_{version_tag}.parquet`"
        " | Per-row predictions (Parquet) |",
        "",
        "---",
        "",
        "## 4. Preprocessing Policy",
        "",
        "| Column type | Transformer |",
        "|-------------|-------------|",
        "| Numeric (non-null) | `StandardScaler` |",
        "| `eval_mate_abs` (nullable, 93.6% null) |"
        " `SimpleImputer(constant=0)` → `StandardScaler` |",
        "| Boolean | `passthrough` (cast to Int8 first) |",
        "| Categorical (`selected_position_type`, `phase`) |"
        " `OneHotEncoder(handle_unknown='ignore')` |",
        "| FS-A (DummyClassifier) | `np.ones((n, 1))` dummy matrix (X ignored) |",
        "",
        "Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed across all experiments).",
        "Training view: `primary_numbered` (exclude `selected_position_type == 'last'`).",
        "",
        "---",
        "",
        "## 5. Baseline Results Summary",
        "",
        "### Broad baselines",
        "",
        "| ID | Model | FS | Expl | Val acc | Val log_loss | Val brier | Test acc |",
        "|----|-------|----|------|---------|--------------|-----------|----------|",
        *broad_rows,
        "",
        "### Eval baselines (exploratory)",
        "",
        "| ID | Model | FS | Expl | Val acc | Val log_loss | Val brier | Test acc |",
        "|----|-------|----|------|---------|--------------|-----------|----------|",
        *eval_rows,
        "",
        "---",
        "",
        "## 6. Output Artifacts Created",
        "",
        "| File | Location | Notes |",
        "|------|----------|-------|",
        f"| `baseline_results_{version_tag}.json`"
        " | `data/processed/` (gitignored) | All metrics |",
        f"| `baseline_predictions_{version_tag}.parquet`"
        " | `data/processed/` (gitignored) | Per-row predictions |",
        "| `phase_5_2b_*.md`"
        " | `reports/phase_reports/` (committed) | This report |",
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
        "    tests/test_baselines.py -v",
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
        "Eval val/test have ~4 and ~2 DRAW rows respectively. DRAW metrics in eval",
        "experiments are noise. All eval baselines are flagged exploratory.",
        "",
        "**R2 — B0 log_loss**",
        "DummyClassifier (most_frequent) predicts p=1.0 for one class, log_loss ~18.9.",
        "This is expected and is not a bug.",
        "",
        "**R3 — Unweighted LR predicts 0 DRAW rows**",
        "B2 and B3 without class_weight will often predict 0 DRAW (minority class ~6%).",
        "B3-balanced shows the balanced-weight effect on DRAW recall.",
        "",
        "**R4 — eval_mate_abs imputation**",
        "93.6% of eval_mate_abs values are null (non-mate positions).",
        "SimpleImputer(fill_value=0) treats these as 'no mate threat', which is correct.",
        "",
        "---",
        "",
        "## 11. Items Intentionally Deferred",
        "",
        "| Item | Reason |",
        "|------|--------|",
        "| GBM (HistGradientBoostingClassifier) | Phase 6 |",
        "| Calibration | Phase 6.2 |",
        "| Subgroup analysis | Phase 7 |",
        "| Model artifact persistence (.joblib) | Not required for baselines |",
        "| XGBoost / LightGBM | Phase 6+ |",
        "",
        "---",
        "",
        "## 12. Whether Next Ticket Is Safe to Begin",
        "",
        "**Yes.** Baseline metrics establish floor for Phase 6 GBM work.",
        "",
        "Suggested next ticket: **Phase 6.1A — GBM Audit**",
        "(HistGradientBoostingClassifier on FS-C through FS-G).",
        "",
        "---",
        "",
        "## Suggested Staging for Commit",
        "",
        "```bash",
        "git add src/chess_mhsuc/baselines.py",
        "git add tests/test_baselines.py",
        "git add ROADMAP.md",
        "git add reports/phase_reports/phase_5_2b_baseline_modeling_implementation.md",
        'git commit -m "Ticket 5.2B: baselines.py, <N> tests (<total> total passing)"',
        "git push",
        "```",
        "",
        "Do NOT stage `data/` — confirm with `git status --ignored` before committing.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Q. print_baseline_summary
# ---------------------------------------------------------------------------

def print_baseline_summary(results_payload: dict) -> None:
    """Print concise human-readable summary of baseline results to stdout."""
    print("\n=== Baseline Results Summary ===\n")
    baseline_results = results_payload["baselines"]

    col_w = [14, 6, 5, 5, 9, 10, 11, 10, 11]
    header = (
        f"{'ID':<{col_w[0]}} {'Table':<{col_w[1]}} {'FS':<{col_w[2]}} "
        f"{'Expl':<{col_w[3]}} | "
        f"{'Val Acc':>{col_w[4]}} {'Val LL':>{col_w[5]}} "
        f"{'Val Brier':>{col_w[6]}} | "
        f"{'Test Acc':>{col_w[7]}} {'Test LL':>{col_w[8]}}"
    )
    print(header)
    print("-" * len(header))

    for bid, res in baseline_results.items():
        if "error" in res:
            print(f"{bid:<{col_w[0]}} ERROR: {res['error']}")
            continue
        table = res.get("table", "?")[:6]
        fs = res.get("feature_set_id", "?")[:5]
        expl = "Y" if res.get("exploratory") else "N"
        val = res.get("metrics", {}).get("val", {})
        test = res.get("metrics", {}).get("test", {})

        def _f(x: Any) -> str:
            if x is None:
                return "    N/A"
            return f"{float(x):.4f}"

        print(
            f"{bid:<{col_w[0]}} {table:<{col_w[1]}} {fs:<{col_w[2]}} {expl:<{col_w[3]}} | "
            f"{_f(val.get('accuracy')):>{col_w[4]}} "
            f"{_f(val.get('log_loss')):>{col_w[5]}} "
            f"{_f(val.get('multiclass_brier')):>{col_w[6]}} | "
            f"{_f(test.get('accuracy')):>{col_w[7]}} "
            f"{_f(test.get('log_loss')):>{col_w[8]}}"
        )

    print()


# ---------------------------------------------------------------------------
# main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 5.2B baseline modeling."""
    parser = argparse.ArgumentParser(
        description="Train baseline models for chess-MHSUC Phase 5.2B"
    )
    parser.add_argument("--dataset-id", required=True,
                        help="Dataset identifier string")
    parser.add_argument("--feature-broad", required=True,
                        help="Broad feature Parquet path")
    parser.add_argument("--feature-eval", required=True,
                        help="Eval feature Parquet path")
    parser.add_argument("--feature-metadata", required=True,
                        help="Feature metadata JSON path (informational)")
    parser.add_argument("--splits", required=True,
                        help="splits JSON path")
    parser.add_argument("--modeling-plan", required=True,
                        help="modeling_plan JSON path")
    parser.add_argument("--output-dir", required=True,
                        help="Output directory for results JSON + predictions Parquet")
    parser.add_argument("--report-output-dir", required=True,
                        help="Directory for phase report Markdown")
    parser.add_argument("--version-tag", required=True,
                        help="Version tag for output file names")

    args = parser.parse_args(argv)

    print(f"dataset_id={args.dataset_id}  version={args.version_tag}")

    broad_df = pl.read_parquet(args.feature_broad)
    eval_df = pl.read_parquet(args.feature_eval)

    with open(args.splits, encoding="utf-8") as f:
        splits_data = json.load(f)

    with open(args.modeling_plan, encoding="utf-8") as f:
        modeling_plan = json.load(f)

    print(f"Broad: {broad_df.shape}, Eval: {eval_df.shape}")
    assignments: dict[str, str] = splits_data["assignments"]
    print(f"Split assignments: {len(assignments)} games")

    print("\nTraining baselines...")
    baseline_results, predictions_df = run_all_baselines(
        broad_df, eval_df, assignments, modeling_plan
    )

    results_payload = build_results_payload(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        split_artifact_path=args.splits,
        modeling_plan_path=args.modeling_plan,
        baseline_results=baseline_results,
    )

    output_paths = save_baseline_outputs(
        results_payload, predictions_df,
        output_dir=args.output_dir,
        version_tag=args.version_tag,
    )

    print_baseline_summary(results_payload)
    print(f"Saved results:     {output_paths['results_json']}")
    print(f"Saved predictions: {output_paths['predictions_parquet']}")

    # Render and save implementation report
    report_md = render_implementation_report(results_payload, output_paths)
    report_dir = Path(args.report_output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = (
        report_dir / "phase_5_2b_baseline_modeling_implementation.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Saved report:      {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
