"""
Eval-conditioned modeling — Ticket 8.2B.

Trains eval-conditioned logistic models (E1, E3, E4, E5) on the broad
primary_numbered view, using the full-coverage fixed-depth Stockfish eval
artifact from Ticket 8.1B as objective position context.

Core research question: after controlling for objective position strength
via fixed-depth Stockfish eval, do human/context features (rating, clock,
checkpoint/phase) still add predictive signal for empirical human game
outcomes?

Models:
    E1 — FS-H: sf_eval only       (sf_eval_cp_clipped, sf_is_mate_eval)
    E3 — FS-I: rating + sf_eval   (FS-B + eval block)
    E4 — FS-J: rating + clock + sf_eval  (FS-B + FS-C + eval block)
    E5 — FS-K: full human context + sf_eval  (FS-E + eval block)

References (NOT retrained): B1 (prior), B2 (rating-only), B3 (current broad
champion) — loaded from the existing baseline predictions artifact.

No GBMs are trained in this ticket. Test split is never used for selection.

Join strategy (per 8.2A audit): direct in-memory join on
(game_id, selected_position_type). NOT (game_id, ply) — duplicate-ply
hazard when a move_N and 'last' checkpoint share a ply.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.eval_conditioned_modeling \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --features data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
        --sf-eval data/processed/sf_eval_broad_2024_09_25k_v1.parquet \\
        --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
        --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
        --output-results data/processed/eval_conditioned_results_2024_09_25k_v1.json \\
        --output-predictions data/processed/eval_conditioned_predictions_2024_09_25k_v1.parquet \\
        --output-report reports/eval_conditioned_modeling_2024_09_25k_v1.md \\
        --overwrite
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from chess_mhsuc.baselines import (
    CLASS_ORDER,
    LABEL_MAP,
    INVERSE_LABEL_MAP,
    align_proba_to_class_order,
    build_preprocessor,
    compute_metrics,
    encode_labels,
    prepare_X,
)
from chess_mhsuc.bootstrap_ci import (
    compute_delta_ci,
    run_bootstrap_for_model,
    run_paired_delta_bootstrap,
)
from chess_mhsuc.splits import _FS_B_COLS, _FS_C_COLS, _FS_D_COLS, _FS_E_COLS

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DATASET_ID = "lichess_ten_zero_2024_09_25k_v1"
DEFAULT_VERSION_TAG = "2024_09_25k_v1"

# Eval clipping bound — same convention as features.py eval_cp_clipped
SF_EVAL_CLIP_CP = 1000

# Primary eval feature block (8.2A audit decision)
EVAL_FEATURE_COLS = ["sf_eval_cp_clipped", "sf_is_mate_eval"]

# Columns selected from the sf_eval artifact during the join.
# split_set comes from the sf artifact (joined post-hoc from splits JSON in 8.1B
# and verified train=4344/val=931/test=930).
_SF_JOIN_KEY = ["game_id", "selected_position_type"]
_SF_SELECT_COLS = _SF_JOIN_KEY + [
    "split_set", "sf_eval_cp", "sf_eval_status", "sf_eval_available", "sf_depth",
]

# Lichess eval columns — excluded from EVERY primary 8.2B feature set
# (sparse 15% coverage, selection-biased, same construct as sf_eval).
LICHESS_EVAL_COLS = frozenset({
    "eval_cp", "eval_cp_clipped", "eval_mate", "eval_mate_abs",
    "is_mate_eval", "eval_white_winning", "has_eval",
})

# Provenance / metadata columns — never features.
_PROVENANCE_COLS = frozenset({
    "sf_eval_available", "sf_eval_status", "sf_eval_bucket", "sf_eval_sign",
    "sf_eval_abs", "sf_eval_mate", "sf_eval_mate_abs", "sf_depth", "sf_nodes",
    "sf_time_ms", "sf_engine_name", "sf_engine_version",
    "sf_eval_timestamp_utc", "sf_error", "fen_hash",
})

# Label / identity columns — never features (mirrors baselines policy).
_FORBIDDEN_COLS = frozenset({
    "result_class", "white_result_numeric", "game_id",
    "termination", "is_time_forfeit", "split_set",
    "duplicate_ply_checkpoint", "is_last_checkpoint",
}) | LICHESS_EVAL_COLS | _PROVENANCE_COLS

# Boolean feature columns (baselines set + the new sf mate flag; Lichess
# boolean eval cols are forbidden here so they are not listed)
_ECM_BOOLEAN_COLS = frozenset({
    "white_low_60", "black_low_60",
    "white_low_30", "black_low_30",
    "white_low_10", "black_low_10",
    "clock_anomaly", "sf_is_mate_eval",
})
_ECM_CATEGORICAL_COLS = frozenset({"selected_position_type", "phase"})

_LR_PARAMS = {"max_iter": 1000, "solver": "lbfgs"}

EXPECTED_PRIMARY_ROWS = 6205
EXPECTED_SPLIT_COUNTS = {"train": 4344, "val": 931, "test": 930}
EXPECTED_TERMINAL_DEPTH0_ROWS = 27

_PROB_COLS = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]

# Reference baselines loaded from existing artifacts (never retrained here)
REFERENCE_MODEL_IDS = ["B1", "B2", "B3"]

# E-models bootstrapped per-model alongside B3
_BOOTSTRAP_TARGETS = ["B1", "B2", "B3", "E1", "E3", "E4", "E5"]

# Required pairwise comparisons (model_a, model_b); "BEST_E" resolved at runtime.
PAIRWISE_COMPARISONS: list[tuple[str, str]] = [
    ("E3", "E4"),   # key scientific comparison: clock after eval + rating
    ("E1", "E3"),   # rating over eval alone
    ("E4", "E5"),   # checkpoint/phase context beyond rating + clock + eval
    ("B3", "E1"),   # objective eval alone vs full human context
    ("B3", "BEST_E"),  # champion vs best eval-conditioned model
]


# ---------------------------------------------------------------------------
# A. build_eval_feature_sets
# ---------------------------------------------------------------------------

def build_eval_feature_sets() -> dict[str, dict]:
    """
    Return feature sets FS-H through FS-K (local registry; the committed
    modeling plan artifact is NOT modified).
    """
    return {
        "FS-H": {
            "id": "FS-H",
            "name": "sf_eval_only",
            "features": list(EVAL_FEATURE_COLS),
            "description": "Local Stockfish eval block only.",
        },
        "FS-I": {
            "id": "FS-I",
            "name": "rating_plus_sf_eval",
            "features": list(_FS_B_COLS) + list(EVAL_FEATURE_COLS),
            "description": "Rating (FS-B) + Stockfish eval block.",
        },
        "FS-J": {
            "id": "FS-J",
            "name": "rating_clock_plus_sf_eval",
            "features": list(_FS_B_COLS) + list(_FS_C_COLS) + list(EVAL_FEATURE_COLS),
            "description": "Rating (FS-B) + clock (FS-C) + Stockfish eval block.",
        },
        "FS-K": {
            "id": "FS-K",
            "name": "full_context_plus_sf_eval",
            "features": list(_FS_E_COLS) + list(EVAL_FEATURE_COLS),
            "description": "Full B3 human context (FS-E) + Stockfish eval block.",
        },
    }


# ---------------------------------------------------------------------------
# B. build_model_registry
# ---------------------------------------------------------------------------

def build_model_registry() -> dict[str, dict]:
    """E1/E3/E4/E5 logistic models. No GBMs. No E0/E2 (duplicate B1/B2)."""
    return {
        "E1": {
            "id": "E1",
            "feature_set_id": "FS-H",
            "model_class": "LogisticRegression",
            "sklearn_params": dict(_LR_PARAMS),
            "description": "sf_eval only.",
        },
        "E3": {
            "id": "E3",
            "feature_set_id": "FS-I",
            "model_class": "LogisticRegression",
            "sklearn_params": dict(_LR_PARAMS),
            "description": "rating + sf_eval.",
        },
        "E4": {
            "id": "E4",
            "feature_set_id": "FS-J",
            "model_class": "LogisticRegression",
            "sklearn_params": dict(_LR_PARAMS),
            "description": "rating + clock + sf_eval.",
        },
        "E5": {
            "id": "E5",
            "feature_set_id": "FS-K",
            "model_class": "LogisticRegression",
            "sklearn_params": dict(_LR_PARAMS),
            "description": "full human context + sf_eval.",
        },
    }


# ---------------------------------------------------------------------------
# C. validate_sf_artifact
# ---------------------------------------------------------------------------

def validate_sf_artifact(sf_df: pl.DataFrame) -> dict[str, Any]:
    """
    Validate the 8.1B sf_eval artifact before joining.

    Raises ValueError on hard violations. Returns a summary dict.
    Terminal sf_depth=0 rows are expected (checkmate/stalemate already on
    board) and are NOT failures.
    """
    n_rows = len(sf_df)
    if sf_df.select(_SF_JOIN_KEY).n_unique() != n_rows:
        raise ValueError("(game_id, selected_position_type) not unique in sf_eval artifact")

    statuses = set(sf_df["sf_eval_status"].unique().to_list())
    if not statuses.issubset({"ok_cp", "ok_mate"}):
        raise ValueError(f"Unexpected sf_eval_status values: {statuses - {'ok_cp', 'ok_mate'}}")

    if not sf_df["sf_eval_available"].all():
        raise ValueError("sf_eval_available is False for some rows")

    cp_min, cp_max = sf_df["sf_eval_cp"].min(), sf_df["sf_eval_cp"].max()
    if cp_min < -10_000 or cp_max > 10_000:
        raise ValueError(f"sf_eval_cp out of range: [{cp_min}, {cp_max}]")

    if "last" in set(sf_df["selected_position_type"].unique().to_list()):
        raise ValueError("sf_eval artifact contains 'last' positions")

    n_depth0 = len(sf_df.filter(pl.col("sf_depth") == 0))

    return {
        "n_rows": n_rows,
        "n_terminal_depth0": n_depth0,
        "statuses": sorted(statuses),
        "cp_range": [int(cp_min), int(cp_max)],
    }


# ---------------------------------------------------------------------------
# D. join_sf_features
# ---------------------------------------------------------------------------

def join_sf_features(
    feature_df: pl.DataFrame,
    sf_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Join sf_eval columns onto the feature table.

    1. Filter feature table to primary_numbered (selected_position_type != 'last').
    2. Assert (game_id, selected_position_type) unique in both inputs.
    3. Left join on (game_id, selected_position_type), selecting only the
       needed sf columns (no suffix pollution).
    4. Assert 0 orphans; preserve feature-table row order via explicit index.

    Never joins on (game_id, ply) — duplicate-ply hazard (8.2A audit).
    """
    primary = feature_df.filter(pl.col("selected_position_type") != "last")

    if primary.select(_SF_JOIN_KEY).n_unique() != len(primary):
        raise ValueError("(game_id, selected_position_type) not unique in feature table")
    if sf_df.select(_SF_JOIN_KEY).n_unique() != len(sf_df):
        raise ValueError("(game_id, selected_position_type) not unique in sf_eval artifact")

    sf_slim = sf_df.select(_SF_SELECT_COLS)

    joined = (
        primary
        .with_row_index("_ecm_row_idx")
        .join(sf_slim, on=_SF_JOIN_KEY, how="left")
        .sort("_ecm_row_idx")
        .drop("_ecm_row_idx")
    )

    if len(joined) != len(primary):
        raise ValueError(
            f"Join changed row count: {len(primary)} -> {len(joined)}"
        )
    n_orphans = joined["sf_eval_status"].null_count()
    if n_orphans > 0:
        raise ValueError(f"{n_orphans} orphan rows after sf_eval join")

    return joined


# ---------------------------------------------------------------------------
# E. validate_joined
# ---------------------------------------------------------------------------

def validate_joined(joined: pl.DataFrame) -> dict[str, Any]:
    """
    Validate the joined modeling table: row count, split counts, no 'last'
    rows, disjoint game_ids across splits.
    """
    n_rows = len(joined)
    split_counts = {
        k: len(joined.filter(pl.col("split_set") == k))
        for k in ("train", "val", "test")
    }

    if "last" in set(joined["selected_position_type"].unique().to_list()):
        raise ValueError("'last' rows present in joined primary view")

    by_split_games = {
        k: set(joined.filter(pl.col("split_set") == k)["game_id"].unique().to_list())
        for k in ("train", "val", "test")
    }
    if (by_split_games["train"] & by_split_games["val"]
            or by_split_games["train"] & by_split_games["test"]
            or by_split_games["val"] & by_split_games["test"]):
        raise ValueError("game_id overlap across splits")

    return {"n_rows": n_rows, "split_counts": split_counts}


# ---------------------------------------------------------------------------
# F. derive_eval_features
# ---------------------------------------------------------------------------

def derive_eval_features(joined: pl.DataFrame) -> pl.DataFrame:
    """
    Add derived eval feature columns:

    sf_eval_cp_clipped — sf_eval_cp clipped to ±SF_EVAL_CLIP_CP (mate
        sentinels ±10000 map to ±1000; same convention as eval_cp_clipped).
    sf_is_mate_eval — True where sf_eval_status == 'ok_mate'. Terminal
        depth-0 mate rows are mate evals, not failures.
    """
    return joined.with_columns([
        pl.col("sf_eval_cp")
        .clip(-SF_EVAL_CLIP_CP, SF_EVAL_CLIP_CP)
        .cast(pl.Int64)
        .alias("sf_eval_cp_clipped"),
        (pl.col("sf_eval_status") == "ok_mate").alias("sf_is_mate_eval"),
    ])


# ---------------------------------------------------------------------------
# G. classify_feature_types
# ---------------------------------------------------------------------------

def classify_feature_types(feature_cols: list[str]) -> dict:
    """
    Classify feature columns for preprocessing (numeric / boolean /
    categorical). Raises on forbidden columns (labels, Lichess eval,
    provenance/metadata).

    There are no nullable numeric columns in the 8.2B feature sets
    (sf_eval_cp_clipped is fully populated).
    """
    numeric: list[str] = []
    boolean: list[str] = []
    categorical: list[str] = []

    for col in feature_cols:
        if col in _FORBIDDEN_COLS:
            raise ValueError(
                f"Forbidden column {col!r} in feature set "
                "(label / Lichess eval / provenance columns are not features)."
            )
        if col in _ECM_BOOLEAN_COLS:
            boolean.append(col)
        elif col in _ECM_CATEGORICAL_COLS:
            categorical.append(col)
        else:
            numeric.append(col)

    return {
        "numeric": numeric,
        "nullable_numeric": [],
        "boolean": boolean,
        "categorical": categorical,
    }


# ---------------------------------------------------------------------------
# H. build_eval_model
# ---------------------------------------------------------------------------

def build_eval_model(entry: dict, preprocessor: Any) -> Any:
    """LogisticRegression pipeline. Only LogisticRegression is supported — no GBMs."""
    if entry["model_class"] != "LogisticRegression":
        raise ValueError(
            f"Unsupported model_class {entry['model_class']!r}: "
            "8.2B trains LogisticRegression only (no GBMs)."
        )
    clf = LogisticRegression(**entry["sklearn_params"])
    if preprocessor is None:
        return clf
    return Pipeline([("pre", preprocessor), ("clf", clf)])


# ---------------------------------------------------------------------------
# I. build_prediction_frame
# ---------------------------------------------------------------------------

def build_prediction_frame(
    model_id: str,
    feature_set_id: str,
    split_set: str,
    split_df: pl.DataFrame,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    proba: np.ndarray,
) -> pl.DataFrame:
    """
    Per-row predictions for one split. Row order matches split_df exactly
    (pairing requirement for game-level paired bootstrap vs baselines).
    """
    n = len(y_true)
    return pl.DataFrame({
        "model_id": pl.Series([model_id] * n, dtype=pl.Utf8),
        "feature_set_id": pl.Series([feature_set_id] * n, dtype=pl.Utf8),
        "split_set": pl.Series([split_set] * n, dtype=pl.Utf8),
        "game_id": split_df["game_id"].cast(pl.Utf8),
        "selected_position_type": split_df["selected_position_type"].cast(pl.Utf8),
        "result_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_true], dtype=pl.Utf8
        ),
        "y_true": pl.Series(y_true.tolist(), dtype=pl.Int64),
        "pred_class": pl.Series(
            [INVERSE_LABEL_MAP[int(v)] for v in y_pred], dtype=pl.Utf8
        ),
        "p_BLACK_WIN": pl.Series(proba[:, 0].tolist(), dtype=pl.Float64),
        "p_DRAW": pl.Series(proba[:, 1].tolist(), dtype=pl.Float64),
        "p_WHITE_WIN": pl.Series(proba[:, 2].tolist(), dtype=pl.Float64),
    })


# ---------------------------------------------------------------------------
# J. train_one_eval_model
# ---------------------------------------------------------------------------

def train_one_eval_model(
    model_id: str,
    entry: dict,
    feature_sets: dict[str, dict],
    modeling_df: pl.DataFrame,
) -> tuple[dict, pl.DataFrame]:
    """
    Train one eval-conditioned model on the train split; evaluate on all
    three splits. Test metrics are computed for the record but MUST NOT be
    used for model selection (WORKFLOW.md §13).
    """
    feature_set_id = entry["feature_set_id"]
    feature_cols = feature_sets[feature_set_id]["features"]
    feature_types = classify_feature_types(feature_cols)
    preprocessor = build_preprocessor(feature_types)
    model = build_eval_model(entry, preprocessor)

    train_df = modeling_df.filter(pl.col("split_set") == "train")
    val_df = modeling_df.filter(pl.col("split_set") == "val")
    test_df = modeling_df.filter(pl.col("split_set") == "test")

    X_train = prepare_X(train_df, feature_cols, feature_types)
    y_train = encode_labels(train_df["result_class"])
    model.fit(X_train, y_train)

    split_metrics: dict[str, dict] = {}
    pred_frames: list[pl.DataFrame] = []

    for split_name, split_df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        X = prepare_X(split_df, feature_cols, feature_types)
        y_true = encode_labels(split_df["result_class"])
        y_pred = model.predict(X)
        proba = align_proba_to_class_order(model, model.predict_proba(X))
        split_metrics[split_name] = compute_metrics(y_true, y_pred, proba)
        pred_frames.append(
            build_prediction_frame(
                model_id, feature_set_id, split_name, split_df, y_true, y_pred, proba
            )
        )

    result = {
        "model_id": model_id,
        "model_class": entry["model_class"],
        "sklearn_params": entry["sklearn_params"],
        "feature_set_id": feature_set_id,
        "n_features": len(feature_cols),
        "feature_columns": list(feature_cols),
        "n_train_rows": len(train_df),
        "n_val_rows": len(val_df),
        "n_test_rows": len(test_df),
        "metrics": split_metrics,
    }
    return result, pl.concat(pred_frames)


# ---------------------------------------------------------------------------
# K. run_all_eval_models
# ---------------------------------------------------------------------------

def run_all_eval_models(
    modeling_df: pl.DataFrame,
) -> tuple[dict[str, dict], pl.DataFrame]:
    """Train E1/E3/E4/E5; return ({model_id: result}, concatenated predictions)."""
    registry = build_model_registry()
    feature_sets = build_eval_feature_sets()

    results: dict[str, dict] = {}
    pred_frames: list[pl.DataFrame] = []
    for model_id, entry in registry.items():
        print(f"  [ecm] Training {model_id} ({entry['feature_set_id']}: "
              f"{entry['description']})", file=sys.stderr)
        result, preds = train_one_eval_model(model_id, entry, feature_sets, modeling_df)
        results[model_id] = result
        pred_frames.append(preds)
        print(f"    val log_loss={result['metrics']['val']['log_loss']:.4f}",
              file=sys.stderr)

    return results, pl.concat(pred_frames)


# ---------------------------------------------------------------------------
# L. load_baseline_reference
# ---------------------------------------------------------------------------

def load_baseline_reference(
    predictions_path: str | Path,
    results_path: str | Path,
) -> tuple[pl.DataFrame, dict[str, dict]]:
    """
    Load reference baseline predictions (B1/B2/B3 only) and their stored
    metrics. Baselines are NOT retrained.
    """
    preds = pl.read_parquet(predictions_path)
    preds = (
        preds.rename({"baseline_id": "model_id"})
        .filter(pl.col("model_id").is_in(REFERENCE_MODEL_IDS))
        .select(["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS)
    )
    with open(results_path) as f:
        results_json = json.load(f)
    ref_metrics = {
        mid: results_json["baselines"][mid]["metrics"]
        for mid in REFERENCE_MODEL_IDS
    }
    return preds, ref_metrics


# ---------------------------------------------------------------------------
# M. build_combined_predictions
# ---------------------------------------------------------------------------

def build_combined_predictions(
    eval_preds: pl.DataFrame,
    baseline_preds: pl.DataFrame,
) -> pl.DataFrame:
    """Unified schema for bootstrap: model_id, split_set, game_id, result_class, probs."""
    eval_slim = eval_preds.select(
        ["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS
    )
    return pl.concat([baseline_preds, eval_slim])


# ---------------------------------------------------------------------------
# N. validate_pairing
# ---------------------------------------------------------------------------

def validate_pairing(
    combined: pl.DataFrame,
    model_a: str,
    model_b: str,
    split_set: str = "val",
) -> bool:
    """
    Validate that two models' prediction rows align for paired bootstrap:
    same per-game row sequences (game_id order and within-game multiplicity).
    Raises ValueError on misalignment.
    """
    seq_a = combined.filter(
        (pl.col("model_id") == model_a) & (pl.col("split_set") == split_set)
    )["game_id"].to_list()
    seq_b = combined.filter(
        (pl.col("model_id") == model_b) & (pl.col("split_set") == split_set)
    )["game_id"].to_list()

    if len(seq_a) != len(seq_b):
        raise ValueError(
            f"Pairing failure {model_a} vs {model_b}: row counts differ "
            f"({len(seq_a)} vs {len(seq_b)})"
        )
    if seq_a != seq_b:
        raise ValueError(
            f"Pairing failure {model_a} vs {model_b}: game_id row order differs"
        )
    return True


# ---------------------------------------------------------------------------
# O. run_bootstrap_cis
# ---------------------------------------------------------------------------

def run_bootstrap_cis(
    combined: pl.DataFrame,
    n_replicates: int = 1000,
    seed: int = 42,
) -> dict[str, dict]:
    """Per-model game-level bootstrap CIs for references + E models."""
    results: dict[str, dict] = {}
    for mid in _BOOTSTRAP_TARGETS:
        present = len(combined.filter(
            (pl.col("model_id") == mid) & (pl.col("split_set") == "val")
        ))
        if present == 0:
            print(f"  [ecm] WARNING: {mid} missing from combined predictions, skipping",
                  file=sys.stderr)
            continue
        print(f"  [ecm] Bootstrap CI for {mid} ({n_replicates} replicates)...",
              file=sys.stderr)
        results[mid] = run_bootstrap_for_model(
            combined, mid, n_replicates=n_replicates, seed=seed
        )
    return results


# ---------------------------------------------------------------------------
# P. select_best_e_model
# ---------------------------------------------------------------------------

def select_best_e_model(eval_results: dict[str, dict]) -> str:
    """Best E-model by VALIDATION log_loss (test split never consulted)."""
    return min(
        eval_results,
        key=lambda mid: eval_results[mid]["metrics"]["val"]["log_loss"],
    )


# ---------------------------------------------------------------------------
# Q. run_pairwise_deltas
# ---------------------------------------------------------------------------

def run_pairwise_deltas(
    combined: pl.DataFrame,
    best_e: str,
    n_replicates: int = 1000,
    seed: int = 42,
) -> dict[str, dict]:
    """
    Run the required paired game-level bootstrap deltas
    (delta = log_loss(B) - log_loss(A); negative = B improved).
    Pairing validity is asserted for each pair before resampling.
    """
    resolved: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for a, b in PAIRWISE_COMPARISONS:
        pair = (a, best_e if b == "BEST_E" else b)
        if pair[0] == pair[1] or pair in seen:
            continue
        seen.add(pair)
        resolved.append(pair)

    deltas: dict[str, dict] = {}
    for model_a, model_b in resolved:
        validate_pairing(combined, model_a, model_b)
        print(f"  [ecm] Pairwise {model_a} -> {model_b} ({n_replicates} replicates)...",
              file=sys.stderr)
        boot = run_paired_delta_bootstrap(
            combined, model_a, model_b, n_replicates=n_replicates, seed=seed
        )
        ci = compute_delta_ci(boot, model_a, model_b, combined)
        deltas[f"{model_a}_vs_{model_b}"] = ci
        zero = "contains 0" if ci["contains_zero"] else "excludes 0"
        print(f"    delta={ci['point_delta']:+.4f} "
              f"[{ci['ci_lower']:+.4f}, {ci['ci_upper']:+.4f}] CI {zero}",
              file=sys.stderr)
    return deltas


# ---------------------------------------------------------------------------
# R. per_checkpoint_slice
# ---------------------------------------------------------------------------

def per_checkpoint_slice(eval_preds: pl.DataFrame) -> dict[str, dict[str, dict]]:
    """
    Per-checkpoint-type validation log_loss slice for E models.

    Returns {model_id: {selected_position_type: {n_rows, log_loss}}}.
    Late checkpoints are increasingly decided positions; this slice exists
    so pooled metrics are not over-read.
    """
    from sklearn.metrics import log_loss as sk_log_loss

    out: dict[str, dict[str, dict]] = {}
    val = eval_preds.filter(pl.col("split_set") == "val")
    for mid in sorted(val["model_id"].unique().to_list()):
        mdf = val.filter(pl.col("model_id") == mid)
        out[mid] = {}
        for cpt in sorted(mdf["selected_position_type"].unique().to_list()):
            sub = mdf.filter(pl.col("selected_position_type") == cpt)
            y = np.array([LABEL_MAP[c] for c in sub["result_class"].to_list()])
            proba = sub.select(_PROB_COLS).to_numpy()
            out[mid][cpt] = {
                "n_rows": len(sub),
                "log_loss": float(sk_log_loss(y, proba, labels=[0, 1, 2])),
            }
    return out


# ---------------------------------------------------------------------------
# S. decisive_only_diagnostic
# ---------------------------------------------------------------------------

def decisive_only_diagnostic(eval_preds: pl.DataFrame) -> dict[str, dict]:
    """
    Diagnostic only: validation log_loss restricted to decisive rows
    (WHITE_WIN / BLACK_WIN). Does NOT replace the primary multiclass metric.
    """
    from sklearn.metrics import log_loss as sk_log_loss

    out: dict[str, dict] = {}
    val = eval_preds.filter(
        (pl.col("split_set") == "val") & (pl.col("result_class") != "DRAW")
    )
    for mid in sorted(val["model_id"].unique().to_list()):
        sub = val.filter(pl.col("model_id") == mid)
        y = np.array([LABEL_MAP[c] for c in sub["result_class"].to_list()])
        proba = sub.select(_PROB_COLS).to_numpy()
        out[mid] = {
            "n_rows": len(sub),
            "log_loss": float(sk_log_loss(y, proba, labels=[0, 1, 2])),
        }
    return out


# ---------------------------------------------------------------------------
# T. build_results_payload
# ---------------------------------------------------------------------------

def build_results_payload(
    dataset_id: str,
    version_tag: str,
    eval_results: dict[str, dict],
    reference_metrics: dict[str, dict],
    bootstrap_cis: dict[str, dict],
    pairwise_deltas: dict[str, dict],
    checkpoint_slice: dict,
    decisive_diag: dict,
    join_summary: dict,
    sf_summary: dict,
    best_e: str,
    artifact_paths: dict[str, str],
    n_replicates: int,
    seed: int,
) -> dict:
    """Assemble the results JSON payload."""
    feature_sets = build_eval_feature_sets()
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "ticket": "8.2B",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sf_artifact_summary": sf_summary,
        "join_summary": join_summary,
        "feature_sets": {
            fid: fs["features"] for fid, fs in feature_sets.items()
        },
        "eval_models": eval_results,
        "reference_baseline_metrics": reference_metrics,
        "best_e_model": best_e,
        "bootstrap_cis": bootstrap_cis,
        "pairwise_deltas": pairwise_deltas,
        "per_checkpoint_slice": checkpoint_slice,
        "decisive_only_diagnostic": decisive_diag,
        "bootstrap_n_replicates": n_replicates,
        "bootstrap_seed": seed,
        "artifact_paths": artifact_paths,
        "caveats": [
            "Fixed-depth Stockfish eval is objective position context, "
            "not ground truth and not a causal variable.",
            "Residual rating/clock associations after conditioning on eval are "
            "predictive associations, not causal effects of those variables on outcomes.",
            "Late checkpoints are increasingly decided positions; per-checkpoint "
            "slices are reported for this reason.",
            "DRAW metrics are directional only because DRAW is sparse "
            "(59/931 val rows).",
            "Test split was not used for model selection.",
            "27 terminal positions have sf_depth=0 (checkmate/stalemate already "
            "on board); expected, not evaluation failures.",
        ],
    }


# ---------------------------------------------------------------------------
# U. render_report
# ---------------------------------------------------------------------------

def _fmt(x: float | None, nd: int = 4) -> str:
    if x is None:
        return "—"
    return f"{x:.{nd}f}"


def render_report(payload: dict) -> str:
    """
    Render the committed eval-conditioned modeling report. Deterministic:
    no timestamps in the markdown body (timestamp lives in the JSON only).
    """
    eval_models = payload["eval_models"]
    refs = payload["reference_baseline_metrics"]
    cis = payload["bootstrap_cis"]
    deltas = payload["pairwise_deltas"]
    best_e = payload["best_e_model"]
    fs = payload["feature_sets"]
    slice_ = payload["per_checkpoint_slice"]
    decisive = payload["decisive_only_diagnostic"]
    join_summary = payload["join_summary"]
    sf_summary = payload["sf_artifact_summary"]

    b3_val_ll = refs["B3"]["val"]["log_loss"]
    best_val_ll = eval_models[best_e]["metrics"]["val"]["log_loss"]
    best_beats_b3 = best_val_ll < b3_val_ll

    key_delta = deltas.get("E3_vs_E4")
    b3_best_key = f"B3_vs_{best_e}"
    b3_best_delta = deltas.get(b3_best_key)

    lines: list[str] = []
    a = lines.append

    a("# Eval-Conditioned Modeling — Ablation Report")
    a("")
    a("**Ticket:** 8.2B — Existing-vs-Fixed Eval Comparison Implementation "
      "(implementation includes eval-conditioned ablation per 8.2A audit)")
    a(f"**Dataset:** `{payload['dataset_id']}`")
    a(f"**Version tag:** `{payload['version_tag']}`")
    a("")
    a("---")
    a("")

    # 1
    a("## 1. ELI5 / TLDR")
    a("")
    a("This report asks: once a chess engine has told us how good the position is, "
      "do human-context facts (player ratings, clock situation, game phase) still "
      "help predict how the game actually ended? We trained four logistic models "
      "that all see the local Stockfish evaluation from Ticket 8.1B, then added "
      "human-context features step by step and measured what improves on the "
      "validation split with game-level bootstrap confidence intervals.")
    a("")
    if key_delta is not None:
        if key_delta["contains_zero"]:
            a("Headline: adding clock features on top of eval + rating did NOT produce "
              "a statistically resolvable improvement at this sample size "
              f"(E3→E4 delta {_fmt(key_delta['point_delta'])}, 95% CI "
              f"[{_fmt(key_delta['ci_lower'])}, {_fmt(key_delta['ci_upper'])}], "
              "CI contains zero).")
        else:
            a("Headline: adding clock features on top of eval + rating produced a "
              "statistically resolvable improvement "
              f"(E3→E4 delta {_fmt(key_delta['point_delta'])}, 95% CI "
              f"[{_fmt(key_delta['ci_lower'])}, {_fmt(key_delta['ci_upper'])}], "
              "CI excludes zero).")
    a("")
    if best_beats_b3:
        a(f"The best eval-conditioned model ({best_e}, val log_loss "
          f"{_fmt(best_val_ll)}) improves on the current broad champion B3 "
          f"({_fmt(b3_val_ll)}).")
    else:
        a(f"The best eval-conditioned model ({best_e}, val log_loss "
          f"{_fmt(best_val_ll)}) does not improve on the current broad champion "
          f"B3 ({_fmt(b3_val_ll)}).")
    a("")

    # 2
    a("## 2. Research Question")
    a("")
    a("After controlling for objective position strength via fixed-depth "
      "Stockfish eval, do human/context features (rating, clock, "
      "checkpoint/phase) still add predictive signal for empirical human game "
      "outcomes? This is the transition from ordinary chess outcome prediction "
      "to human outcome probability under constraints. All comparisons are "
      "predictive associations on the validation split — not causal claims.")
    a("")

    # 3
    a("## 3. Data and Join Integrity")
    a("")
    a("| Check | Value |")
    a("|---|---|")
    a(f"| Joined rows (primary_numbered) | {join_summary['n_rows']:,} |")
    a(f"| Train / val / test rows | "
      f"{join_summary['split_counts']['train']:,} / "
      f"{join_summary['split_counts']['val']:,} / "
      f"{join_summary['split_counts']['test']:,} |")
    a(f"| Orphan rows after join | 0 |")
    a(f"| sf artifact rows | {sf_summary['n_rows']:,} |")
    a(f"| Terminal sf_depth=0 rows | {sf_summary['n_terminal_depth0']} |")
    a("")
    a("Join key: `(game_id, selected_position_type)` — unique in both tables. "
      "The `(game_id, ply)` key was rejected per the 8.2A audit (duplicate-ply "
      "hazard when a move_N and 'last' checkpoint share a ply). Only `sf_*` "
      "columns plus keys were selected from the sf artifact (no suffix "
      "pollution). 'last' positions are excluded throughout (primary_numbered "
      "view, consistent with B3 and 8.1B).")
    a("")

    # 4
    a("## 4. Eval Feature Semantics")
    a("")
    a("- `sf_eval_cp_clipped` — `sf_eval_cp` clipped to ±1000 cp (White POV); "
      "mate sentinels ±10000 map to ±1000. Same convention as the existing "
      "`eval_cp_clipped`.")
    a("- `sf_is_mate_eval` — True where `sf_eval_status == \"ok_mate\"`.")
    a("")
    a("Excluded from features: `sf_eval_available` (constant), `sf_eval_status` "
      "and `sf_eval_bucket` (strings; bucket reserved for report slicing), "
      "`sf_eval_sign`/`sf_eval_abs` (redundant or direction-destroying), "
      "`sf_eval_mate_abs` (sparse), `sf_depth`/`sf_nodes`/`sf_time_ms`/engine "
      "metadata (provenance). All Lichess eval columns (`eval_cp`, "
      "`eval_cp_clipped`, `eval_mate`, `eval_mate_abs`, `is_mate_eval`, "
      "`eval_white_winning`, `has_eval`) are excluded from every primary "
      "feature set — they are sparse (15% coverage), selection-biased, and "
      "measure the same construct as `sf_eval_cp`.")
    a("")

    # 5
    a("## 5. Models / Feature Sets")
    a("")
    a("| Model | Feature set | N features | Description |")
    a("|---|---|---|---|")
    for mid in ("E1", "E3", "E4", "E5"):
        m = eval_models[mid]
        a(f"| {mid} | {m['feature_set_id']} | {m['n_features']} | "
          f"{', '.join(fs[m['feature_set_id']][:4])}"
          f"{'…' if len(fs[m['feature_set_id']]) > 4 else ''} |")
    a("")
    a("References (not retrained; loaded from the committed baseline run): "
      "B1 (prior), B2 (rating-only logistic), B3 (rating + clock + context "
      "logistic — current broad champion). All models are logistic "
      "regression (`max_iter=1000`, `lbfgs`); no GBMs were trained in this "
      "ticket.")
    a("")

    # 6
    a("## 6. Validation Metrics")
    a("")
    a("All primary metrics on the validation split (931 rows, 348 games). "
      "Test split untouched for selection.")
    a("")
    a("| Model | val log_loss | val accuracy | val macro_f1 | val Brier |")
    a("|---|---|---|---|---|")
    for mid in ("B1", "B2", "B3"):
        m = refs[mid]["val"]
        a(f"| {mid} (ref) | {_fmt(m['log_loss'])} | {_fmt(m['accuracy'])} | "
          f"{_fmt(m['macro_f1'])} | {_fmt(m['multiclass_brier'])} |")
    for mid in ("E1", "E3", "E4", "E5"):
        m = eval_models[mid]["metrics"]["val"]
        marker = " **(best E)**" if mid == best_e else ""
        a(f"| {mid}{marker} | {_fmt(m['log_loss'])} | {_fmt(m['accuracy'])} | "
          f"{_fmt(m['macro_f1'])} | {_fmt(m['multiclass_brier'])} |")
    a("")
    a("Decisive-only diagnostic (val rows with WHITE_WIN/BLACK_WIN only; "
      "diagnostic — does not replace the primary multiclass metric):")
    a("")
    a("| Model | n rows | decisive-only log_loss |")
    a("|---|---|---|")
    for mid in sorted(decisive):
        d = decisive[mid]
        a(f"| {mid} | {d['n_rows']} | {_fmt(d['log_loss'])} |")
    a("")

    # 7
    a("## 7. Game-Level Bootstrap CIs")
    a("")
    a(f"Game-level cluster bootstrap, {payload['bootstrap_n_replicates']} "
      f"replicates, seed={payload['bootstrap_seed']}. Rows from the same game "
      "are resampled together (1–4 rows per game; row-level CIs would be "
      "invalid).")
    a("")
    a("| Model | val log_loss | 95% CI lower | 95% CI upper |")
    a("|---|---|---|---|")
    for mid in _BOOTSTRAP_TARGETS:
        if mid not in cis:
            continue
        c = cis[mid]
        a(f"| {mid} | {_fmt(c['point_log_loss'])} | {_fmt(c['ci_lower'])} | "
          f"{_fmt(c['ci_upper'])} |")
    a("")

    # 8
    a("## 8. Pairwise Delta Results")
    a("")
    a("Paired game-level bootstrap; delta = log_loss(B) − log_loss(A). "
      "Negative delta means B improved. A CI excluding zero means the "
      "difference is statistically resolvable at this sample size; it does "
      "not establish any causal mechanism.")
    a("")
    a("| Comparison | Point delta | 95% CI lower | 95% CI upper | CI contains zero |")
    a("|---|---|---|---|---|")
    for key, d in deltas.items():
        a(f"| {d['model_a']} → {d['model_b']} | {_fmt(d['point_delta'])} | "
          f"{_fmt(d['ci_lower'])} | {_fmt(d['ci_upper'])} | "
          f"{'Yes' if d['contains_zero'] else 'No'} |")
    a("")
    a("Interpretation (cautious):")
    a("")
    if key_delta is not None:
        if key_delta["contains_zero"]:
            a("- **E3 → E4 (key comparison):** adding clock features after eval + "
              "rating improves the point estimate but the CI contains zero — "
              "not statistically resolvable at pilot scale. This is an absence "
              "of resolvable evidence, not evidence of absence.")
        else:
            a("- **E3 → E4 (key comparison):** adding clock features after eval + "
              "rating produces a CI excluding zero — clock carries predictive "
              "signal beyond objective position strength and rating at this "
              "sample size. This is a predictive association, not a causal claim.")
    if "E1_vs_E3" in deltas:
        d = deltas["E1_vs_E3"]
        a(f"- **E1 → E3:** rating over eval alone: delta {_fmt(d['point_delta'])}, "
          f"CI {'contains' if d['contains_zero'] else 'excludes'} zero.")
    if "E4_vs_E5" in deltas:
        d = deltas["E4_vs_E5"]
        a(f"- **E4 → E5:** checkpoint/phase context beyond rating + clock + eval: "
          f"delta {_fmt(d['point_delta'])}, "
          f"CI {'contains' if d['contains_zero'] else 'excludes'} zero.")
    if "B3_vs_E1" in deltas:
        d = deltas["B3_vs_E1"]
        a(f"- **B3 → E1:** eval alone vs full human context: delta "
          f"{_fmt(d['point_delta'])}, "
          f"CI {'contains' if d['contains_zero'] else 'excludes'} zero.")
    if b3_best_delta is not None:
        a(f"- **B3 → {best_e} (best E):** delta "
          f"{_fmt(b3_best_delta['point_delta'])}, "
          f"CI {'contains' if b3_best_delta['contains_zero'] else 'excludes'} zero.")
    a("")

    # 9
    a("## 9. Per-Checkpoint-Type Slice")
    a("")
    a("Validation log_loss by checkpoint type. Late checkpoints are "
      "increasingly decided positions (move_40: 71% of positions have "
      "|cp| ≥ 300), so pooled metrics blend easy late positions with hard "
      "early ones. This slice exists so the pooled number is not over-read. "
      "It does not establish degradation curves.")
    a("")
    cpts = ["move_10", "move_20", "move_30", "move_40"]
    a("| Model | " + " | ".join(cpts) + " |")
    a("|---|" + "---|" * len(cpts))
    for mid in sorted(slice_):
        cells = []
        for cpt in cpts:
            cell = slice_[mid].get(cpt)
            cells.append(
                f"{_fmt(cell['log_loss'])} (n={cell['n_rows']})" if cell else "—"
            )
        a(f"| {mid} | " + " | ".join(cells) + " |")
    a("")

    # 10
    a("## 10. Lichess Eval Overlap Appendix")
    a("")
    a("Sanity context from 8.1B (descriptive only; no model in this ticket "
      "was trained on Lichess eval columns):")
    a("")
    a("- 932 of 6,205 positions also have a Lichess cloud eval.")
    a("- Non-mate sign agreement: 829/872 = 95.1%.")
    a("- Mean absolute cp difference: 68.8 cp (different Stockfish versions, "
      "variable Lichess depth vs fixed depth=12 locally).")
    a("- Lichess eval columns and `sf_eval_cp_clipped` were never mixed in "
      "any primary feature set.")
    a("")

    # 11
    a("## 11. DRAW Caveat")
    a("")
    a("DRAW is 59/931 validation rows (6.3%). DRAW metrics are directional "
      "only because DRAW is sparse; per-class DRAW numbers must not be "
      "treated as reliable at pilot scale.")
    a("")

    # 12
    a("## 12. Terminal Position / sf_depth=0 Caveat")
    a("")
    a("27 of 6,205 positions are terminal (26 checkmate already on board, "
      "1 stalemate). The engine returns sf_depth=0 for these because no "
      "search is possible — expected behavior, not evaluation failures. "
      "These rows are legitimate population members but are mechanically "
      "decided, so they trivially favor eval-conditioned models; they are "
      "0.4% of rows.")
    a("")

    # 13
    a("## 13. Scientific Interpretation")
    a("")
    a("Fixed-depth Stockfish eval is objective position context, not ground "
      "truth and not a causal variable. Residual rating/clock associations "
      "after conditioning on eval are predictive associations, not causal "
      "effects of those variables on outcomes. Late checkpoints are "
      "increasingly decided positions; per-checkpoint slices are reported "
      "for this reason. DRAW metrics are directional only because DRAW is "
      "sparse. Test split was not used for model selection.")
    a("")

    # 14
    a("## 14. Forbidden Claims / Limitations")
    a("")
    a("- No causal claims are made or supported by this report.")
    a("- Stockfish depth=12 eval is an approximation, not ground truth; "
      "deeper or different engine versions would differ.")
    a("- This report does not establish degradation curves.")
    a("- DRAW is not solved; DRAW metrics are directional only.")
    a("- Phase 9 (scaling) is not started; no cross-stratum claims.")
    a("- Test-split metrics are recorded but were not used for any selection.")
    a("- Pilot scale (931 val rows, 348 games) produces wide CIs; interval "
      "endpoints should not be over-interpreted.")
    a("")

    # 15
    a("## 15. Reproducibility")
    a("")
    a("```bash")
    a("PYTHONPATH=src python -m chess_mhsuc.eval_conditioned_modeling \\")
    a(f"    --dataset-id {payload['dataset_id']} \\")
    a(f"    --version-tag {payload['version_tag']} \\")
    a("    --features data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\")
    a("    --sf-eval data/processed/sf_eval_broad_2024_09_25k_v1.parquet \\")
    a("    --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\")
    a("    --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\")
    a("    --output-results data/processed/eval_conditioned_results_2024_09_25k_v1.json \\")
    a("    --output-predictions data/processed/eval_conditioned_predictions_2024_09_25k_v1.parquet \\")
    a("    --output-report reports/eval_conditioned_modeling_2024_09_25k_v1.md \\")
    a("    --overwrite")
    a("```")
    a("")
    a("The markdown report body is deterministic (timestamps live in the "
      "results JSON only). LogisticRegression with lbfgs is deterministic "
      "for fixed inputs; bootstrap uses seed=42.")
    a("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# V. write_outputs
# ---------------------------------------------------------------------------

def write_outputs(
    payload: dict,
    predictions: pl.DataFrame,
    report_text: str,
    output_results: str | Path,
    output_predictions: str | Path,
    output_report: str | Path,
    overwrite: bool = False,
) -> None:
    """Write results JSON, predictions Parquet, and the markdown report."""
    paths = [Path(output_results), Path(output_predictions), Path(output_report)]
    for p in paths:
        if p.exists() and not overwrite:
            raise FileExistsError(f"{p} exists; pass --overwrite to replace")
        p.parent.mkdir(parents=True, exist_ok=True)

    with open(paths[0], "w") as f:
        json.dump(payload, f, indent=2)
    predictions.write_parquet(paths[1], compression="snappy")
    paths[2].write_text(report_text)


# ---------------------------------------------------------------------------
# W. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Eval-conditioned logistic modeling (Ticket 8.2B)."
    )
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--version-tag", default=DEFAULT_VERSION_TAG)
    parser.add_argument("--features", required=True,
                        help="feature_positions_broad parquet")
    parser.add_argument("--sf-eval", required=True,
                        help="sf_eval_broad parquet (8.1B artifact)")
    parser.add_argument("--baseline-predictions", required=True,
                        help="baseline_predictions parquet (B1/B2/B3 references)")
    parser.add_argument("--baseline-results", required=True,
                        help="baseline_results JSON (reference metrics)")
    parser.add_argument("--output-results", required=True)
    parser.add_argument("--output-predictions", required=True)
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--n-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    print("[ecm] Loading inputs...", file=sys.stderr)
    feature_df = pl.read_parquet(args.features)
    sf_df = pl.read_parquet(args.sf_eval)

    sf_summary = validate_sf_artifact(sf_df)
    print(f"  sf artifact: {sf_summary['n_rows']} rows, "
          f"{sf_summary['n_terminal_depth0']} terminal depth-0 rows",
          file=sys.stderr)

    joined = join_sf_features(feature_df, sf_df)
    join_summary = validate_joined(joined)
    print(f"  joined: {join_summary['n_rows']} rows, "
          f"splits={join_summary['split_counts']}", file=sys.stderr)

    if join_summary["n_rows"] != EXPECTED_PRIMARY_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_PRIMARY_ROWS} joined rows, "
            f"got {join_summary['n_rows']}"
        )
    if join_summary["split_counts"] != EXPECTED_SPLIT_COUNTS:
        raise ValueError(
            f"Expected split counts {EXPECTED_SPLIT_COUNTS}, "
            f"got {join_summary['split_counts']}"
        )

    modeling_df = derive_eval_features(joined)

    print("[ecm] Training eval-conditioned models...", file=sys.stderr)
    eval_results, eval_preds = run_all_eval_models(modeling_df)
    best_e = select_best_e_model(eval_results)
    print(f"  best E-model by val log_loss: {best_e}", file=sys.stderr)

    print("[ecm] Loading baseline references...", file=sys.stderr)
    baseline_preds, reference_metrics = load_baseline_reference(
        args.baseline_predictions, args.baseline_results
    )
    combined = build_combined_predictions(eval_preds, baseline_preds)

    # Pairing validity for the paired bootstrap (B3 vs E rows must align)
    for mid in ("E1", "E3", "E4", "E5"):
        validate_pairing(combined, "B3", mid)
    print("  pairing validated: B3 vs E1/E3/E4/E5 row orders align",
          file=sys.stderr)

    print("[ecm] Bootstrap CIs...", file=sys.stderr)
    bootstrap_cis = run_bootstrap_cis(
        combined, n_replicates=args.n_replicates, seed=args.seed
    )

    print("[ecm] Pairwise deltas...", file=sys.stderr)
    pairwise = run_pairwise_deltas(
        combined, best_e, n_replicates=args.n_replicates, seed=args.seed
    )

    checkpoint_slice = per_checkpoint_slice(eval_preds)
    decisive_diag = decisive_only_diagnostic(eval_preds)

    payload = build_results_payload(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        eval_results=eval_results,
        reference_metrics=reference_metrics,
        bootstrap_cis=bootstrap_cis,
        pairwise_deltas=pairwise,
        checkpoint_slice=checkpoint_slice,
        decisive_diag=decisive_diag,
        join_summary=join_summary,
        sf_summary=sf_summary,
        best_e=best_e,
        artifact_paths={
            "results_json": str(args.output_results),
            "predictions_parquet": str(args.output_predictions),
            "report_markdown": str(args.output_report),
            "sf_eval_parquet": str(args.sf_eval),
            "features_parquet": str(args.features),
        },
        n_replicates=args.n_replicates,
        seed=args.seed,
    )
    report_text = render_report(payload)

    write_outputs(
        payload, eval_preds, report_text,
        args.output_results, args.output_predictions, args.output_report,
        overwrite=args.overwrite,
    )
    print(f"[ecm] results: {args.output_results}", file=sys.stderr)
    print(f"[ecm] predictions: {args.output_predictions} "
          f"({len(eval_preds)} rows)", file=sys.stderr)
    print(f"[ecm] report: {args.output_report}", file=sys.stderr)

    # Console summary
    print("\n=== 8.2B summary (validation split) ===")
    for mid in ("B1", "B2", "B3"):
        print(f"  {mid} (ref): log_loss={reference_metrics[mid]['val']['log_loss']:.4f}")
    for mid in ("E1", "E3", "E4", "E5"):
        marker = "  <- best E" if mid == best_e else ""
        print(f"  {mid}: log_loss="
              f"{eval_results[mid]['metrics']['val']['log_loss']:.4f}{marker}")
    for key, d in pairwise.items():
        zero = "contains 0" if d["contains_zero"] else "EXCLUDES 0"
        print(f"  {d['model_a']} -> {d['model_b']}: "
              f"delta={d['point_delta']:+.4f} "
              f"[{d['ci_lower']:+.4f}, {d['ci_upper']:+.4f}] {zero}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
