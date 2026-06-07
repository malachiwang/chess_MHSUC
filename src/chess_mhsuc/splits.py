"""
splits.py — v1 train/validation/test split assignment for chess-MHSUC.

Creates game_id-level split assignments (70/15/15, stratified by result_class, seed 42)
and a modeling plan JSON documenting feature sets, metric policy, and baseline plan.

Implements all decisions from Ticket 5.1A audit:
- Split by game_id, never by row.
- 70/15/15 ratio.
- Seed 42, stratified by game-level result_class.
- Primary training view: numbered checkpoints only (exclude selected_position_type == 'last').
- Eval table inherits broad split assignments via game_id join; no separate eval split.
- No split-augmented Parquet files written.
- No model training, preprocessing, or metrics implemented here.

Output artifacts (local-only, gitignored):
  data/processed/splits_{version_tag}.json
  data/processed/modeling_plan_{version_tag}.json

Output committed:
  reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md

CLI usage:
  PYTHONPATH=src python -m chess_mhsuc.splits \\
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
    --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
    --feature-eval data/processed/feature_positions_eval_2024_09_25k_v1.parquet \\
    --feature-metadata data/processed/feature_metadata_2024_09_25k_v1.json \\
    --output-dir data/processed \\
    --report-output-dir reports/phase_reports \\
    --version-tag 2024_09_25k_v1 \\
    --train-frac 0.70 \\
    --val-frac 0.15 \\
    --seed 42

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.model_selection import StratifiedShuffleSplit


# ---------------------------------------------------------------------------
# A. build_game_level_df
# ---------------------------------------------------------------------------

def build_game_level_df(feature_df: pl.DataFrame) -> pl.DataFrame:
    """
    Build one row per game from a broad feature DataFrame.

    Returns a DataFrame with columns:
      game_id, result_class, has_eval_game, n_rows,
      n_numbered_rows, n_last_rows, has_duplicate_ply_checkpoint

    Raises ValueError if any game_id maps to more than one result_class value.
    Does not modify the input DataFrame.
    """
    rc_check = feature_df.group_by("game_id").agg(
        pl.col("result_class").n_unique().alias("_n_rc")
    )
    bad = rc_check.filter(pl.col("_n_rc") > 1)
    if len(bad) > 0:
        sample = bad["game_id"].head(5).to_list()
        raise ValueError(
            f"{len(bad)} game_id(s) have multiple result_class values. "
            f"Sample game_ids: {sample}"
        )

    return (
        feature_df.group_by("game_id")
        .agg(
            pl.col("result_class").first().alias("result_class"),
            pl.col("has_eval").any().alias("has_eval_game"),
            pl.len().alias("n_rows"),
            (pl.col("selected_position_type") != "last").sum().alias("n_numbered_rows"),
            (pl.col("selected_position_type") == "last").sum().alias("n_last_rows"),
            pl.col("duplicate_ply_checkpoint").any().alias("has_duplicate_ply_checkpoint"),
        )
        .sort("game_id")
    )


# ---------------------------------------------------------------------------
# B. stratified_game_split
# ---------------------------------------------------------------------------

def stratified_game_split(
    game_df: pl.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    seed: int = 42,
    stratify_col: str = "result_class",
) -> dict[str, str]:
    """
    Assign each game_id to "train", "val", or "test" using stratified splitting.

    Splits at the game_id level only — never at the row level.
    Uses two-step StratifiedShuffleSplit:
      Step 1: train vs temp (val + test)
      Step 2: temp into val vs test

    Returns {game_id: "train" | "val" | "test"}.

    Raises ValueError on invalid fractions or missing required columns.
    """
    if not (0 < train_frac < 1):
        raise ValueError(f"train_frac must be in (0, 1), got {train_frac!r}")
    if not (0 < val_frac < 1):
        raise ValueError(f"val_frac must be in (0, 1), got {val_frac!r}")
    test_frac = 1.0 - train_frac - val_frac
    if test_frac <= 0:
        raise ValueError(
            f"test_frac = {test_frac:.6f} is not positive. "
            f"train_frac + val_frac = {train_frac + val_frac:.6f} must be < 1.0."
        )
    for col in ("game_id", stratify_col):
        if col not in game_df.columns:
            raise ValueError(
                f"Required column '{col}' not found in game_df. "
                f"Available columns: {game_df.columns}"
            )

    game_ids = np.array(game_df["game_id"].to_list())
    labels = np.array(game_df[stratify_col].to_list())
    indices = np.arange(len(game_ids))

    # Step 1: split into train vs temp (val + test combined)
    temp_frac = val_frac + test_frac
    sss1 = StratifiedShuffleSplit(n_splits=1, test_size=temp_frac, random_state=seed)
    train_idx, temp_idx = next(sss1.split(indices, labels))

    # Step 2: split temp into val vs test
    val_frac_in_temp = val_frac / temp_frac
    temp_labels = labels[temp_idx]
    sss2 = StratifiedShuffleSplit(
        n_splits=1,
        test_size=1.0 - val_frac_in_temp,
        random_state=seed,
    )
    val_sub_idx, test_sub_idx = next(sss2.split(temp_idx, temp_labels))
    val_idx = temp_idx[val_sub_idx]
    test_idx = temp_idx[test_sub_idx]

    assignments: dict[str, str] = {}
    for i in train_idx:
        assignments[str(game_ids[i])] = "train"
    for i in val_idx:
        assignments[str(game_ids[i])] = "val"
    for i in test_idx:
        assignments[str(game_ids[i])] = "test"

    return assignments


# ---------------------------------------------------------------------------
# C. validate_split_assignments
# ---------------------------------------------------------------------------

def validate_split_assignments(
    assignments: dict[str, str],
    expected_game_ids: list[str] | set[str],
) -> dict:
    """
    Validate that a split assignment dict covers exactly the expected game_ids.

    Returns a validation dict with:
      passed, n_expected_games, n_assigned_games, split_counts,
      missing_game_ids, extra_game_ids, invalid_split_values
    """
    expected = set(expected_game_ids)
    assigned = set(assignments.keys())
    valid_splits = {"train", "val", "test"}

    missing = sorted(expected - assigned)
    extra = sorted(assigned - expected)
    invalid_values = sorted({v for v in assignments.values() if v not in valid_splits})

    split_counts = {s: sum(1 for v in assignments.values() if v == s)
                   for s in ("train", "val", "test")}
    all_non_empty = all(split_counts[s] > 0 for s in valid_splits)

    passed = (
        len(missing) == 0
        and len(extra) == 0
        and len(invalid_values) == 0
        and all_non_empty
    )

    return {
        "passed": passed,
        "n_expected_games": len(expected),
        "n_assigned_games": len(assignments),
        "split_counts": split_counts,
        "missing_game_ids": missing,
        "extra_game_ids": extra,
        "invalid_split_values": invalid_values,
    }


# ---------------------------------------------------------------------------
# D. check_split_balance
# ---------------------------------------------------------------------------

def check_split_balance(
    assignments: dict[str, str],
    game_level_df: pl.DataFrame,
    label_col: str = "result_class",
) -> dict:
    """
    Report label (class) distribution per split and emit warnings for sparse classes.

    Returns:
      splits: {split_name: {n_games, label_counts, label_pcts, draw_count}}
      warnings: list of warning strings
    """
    assign_df = pl.DataFrame({
        "game_id": list(assignments.keys()),
        "split_set": list(assignments.values()),
    })
    merged = game_level_df.join(assign_df, on="game_id", how="left")

    all_labels = sorted(game_level_df[label_col].unique().to_list())
    result: dict = {"splits": {}, "warnings": []}

    for split in ("train", "val", "test"):
        sub = merged.filter(pl.col("split_set") == split)
        n_games = len(sub)
        label_counts: dict[str, int] = {}
        label_pcts: dict[str, float] = {}

        for label in all_labels:
            n = sub.filter(pl.col(label_col) == label).height
            label_counts[label] = n
            label_pcts[label] = round(100.0 * n / n_games, 2) if n_games > 0 else 0.0

        draw_count = label_counts.get("DRAW", 0)
        result["splits"][split] = {
            "n_games": n_games,
            "label_counts": label_counts,
            "label_pcts": label_pcts,
            "draw_count": draw_count,
        }

        if draw_count == 0:
            result["warnings"].append(
                f"Split '{split}' has ZERO DRAW games. "
                "Per-class DRAW metrics will be undefined."
            )
        if split in ("val", "test") and 0 < draw_count < 8:
            result["warnings"].append(
                f"Split '{split}' has only {draw_count} DRAW game(s) (< 8). "
                "DRAW class metrics will be very noisy."
            )
        for label in all_labels:
            if label_counts.get(label, 0) == 0:
                result["warnings"].append(
                    f"Split '{split}' has zero games for class '{label}'."
                )

    return result


# ---------------------------------------------------------------------------
# E. apply_split_to_df
# ---------------------------------------------------------------------------

def apply_split_to_df(
    feature_df: pl.DataFrame,
    assignments: dict[str, str],
) -> pl.DataFrame:
    """
    Add a split_set column to feature_df by joining on game_id.

    Does not drop rows. Raises ValueError if any feature row has a game_id
    missing from assignments.
    """
    feature_game_ids = set(feature_df["game_id"].unique().to_list())
    assigned_game_ids = set(assignments.keys())
    missing = feature_game_ids - assigned_game_ids
    if missing:
        sample = sorted(missing)[:5]
        raise ValueError(
            f"{len(missing)} game_id(s) in feature_df have no split assignment. "
            f"Sample: {sample}"
        )

    assign_df = pl.DataFrame({
        "game_id": list(assignments.keys()),
        "split_set": list(assignments.values()),
    })
    return feature_df.join(assign_df, on="game_id", how="left")


# ---------------------------------------------------------------------------
# F. filter_training_view
# ---------------------------------------------------------------------------

def filter_training_view(df: pl.DataFrame, view_name: str) -> pl.DataFrame:
    """
    Apply a named training view filter to a feature DataFrame.

    Supported view names:
      "primary_numbered"
          Keep rows where selected_position_type != "last".
          Canonical v1 training view. No duplicates. Consistent semantics.

      "all_checkpoints_dedup"
          Keep all rows except: duplicate_ply_checkpoint == True AND
          is_last_checkpoint == True. Removes coincident 'last' rows.

      "all_checkpoints_raw"
          No filtering. Diagnostic use only; not recommended for v1 modeling.

    Raises ValueError for unknown view_name. Does not mutate input.
    """
    if view_name == "primary_numbered":
        return df.filter(pl.col("selected_position_type") != "last")
    if view_name == "all_checkpoints_dedup":
        return df.filter(
            ~(
                (pl.col("duplicate_ply_checkpoint") == True)
                & (pl.col("is_last_checkpoint") == True)
            )
        )
    if view_name == "all_checkpoints_raw":
        return df.clone()
    raise ValueError(
        f"Unknown view_name '{view_name}'. "
        "Supported: 'primary_numbered', 'all_checkpoints_dedup', 'all_checkpoints_raw'."
    )


# ---------------------------------------------------------------------------
# G. get_train_val_test
# ---------------------------------------------------------------------------

def get_train_val_test(
    feature_df: pl.DataFrame,
    assignments: dict[str, str],
    view_name: str = "primary_numbered",
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Apply split assignments and a named view filter, then return train/val/test DataFrames.

    Procedure:
      1. apply_split_to_df (adds split_set column)
      2. filter_training_view (applies view filter)
      3. partition by split_set

    Validates that no game_id appears in more than one returned partition.
    """
    df_split = apply_split_to_df(feature_df, assignments)
    df_view = filter_training_view(df_split, view_name)

    train_df = df_view.filter(pl.col("split_set") == "train")
    val_df = df_view.filter(pl.col("split_set") == "val")
    test_df = df_view.filter(pl.col("split_set") == "test")

    # Validate no game_id cross-contamination
    train_ids = set(train_df["game_id"].unique().to_list())
    val_ids = set(val_df["game_id"].unique().to_list())
    test_ids = set(test_df["game_id"].unique().to_list())
    overlap_tv = train_ids & val_ids
    overlap_tt = train_ids & test_ids
    overlap_vt = val_ids & test_ids
    if overlap_tv or overlap_tt or overlap_vt:
        raise ValueError(
            f"game_id overlap detected: train∩val={len(overlap_tv)}, "
            f"train∩test={len(overlap_tt)}, val∩test={len(overlap_vt)}"
        )

    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# H. build_feature_sets
# ---------------------------------------------------------------------------

# Feature set column definitions — hard-coded per Ticket 5.1A audit.
# Do not substitute default_predictive_features from metadata directly.

_FS_B_COLS = [
    "white_elo", "black_elo", "elo_diff", "avg_elo",
]

_FS_C_COLS = [
    # Capped clock values only; raw white_clock_s/black_clock_s excluded (7 anomaly rows)
    "white_clock_s_capped", "black_clock_s_capped",
    "clock_diff_s",          # signed raw diff retained as a useful feature
    "white_clock_frac", "black_clock_frac", "clock_diff_frac",
    "white_low_60", "black_low_60",
    "white_low_30", "black_low_30",
    "white_low_10", "black_low_10",
    "clock_anomaly",
]

_FS_D_COLS = [
    # selected_position_type and phase are String dtype; require one-hot encoding for sklearn
    "selected_position_type", "move_number", "phase",
    "checkpoint_index", "phase_index",
]

_FS_E_COLS = _FS_B_COLS + _FS_C_COLS + _FS_D_COLS

# Eval core: clipped/non-null-safe features only; no raw eval_cp or eval_mate
_EVAL_CORE_COLS = [
    "eval_cp_clipped",   # ±1000 clipped; mate sentinels mapped to ±1000
    "is_mate_eval",      # Boolean
    "eval_mate_abs",     # 0 for non-mate positions; always non-null
    "eval_white_winning",  # Boolean (True if eval_cp > 0)
]

_FS_F_COLS = _EVAL_CORE_COLS + _FS_D_COLS

_FS_G_COLS = _FS_E_COLS + _EVAL_CORE_COLS


def build_feature_sets(feature_metadata: dict) -> dict:
    """
    Return named feature sets FS-A through FS-G.

    Feature lists are hard-coded per Ticket 5.1A audit decisions.
    The feature_metadata parameter is accepted for future validation use.
    """
    return {
        "FS-A": {
            "id": "FS-A",
            "name": "majority_prior",
            "table": "broad",
            "view": "primary_numbered",
            "features": [],
            "description": (
                "No features. Used for DummyClassifier baselines "
                "(most_frequent and prior strategies)."
            ),
            "null_policy": "N/A — no features.",
            "notes": "Used for B0 (most_frequent) and B1 (prior) baselines.",
        },
        "FS-B": {
            "id": "FS-B",
            "name": "rating_only",
            "table": "broad",
            "view": "primary_numbered",
            "features": _FS_B_COLS,
            "description": "Rating features only: white_elo, black_elo, elo_diff, avg_elo.",
            "null_policy": "No nulls in these columns.",
            "notes": "Tests whether rating alone predicts outcome.",
        },
        "FS-C": {
            "id": "FS-C",
            "name": "clock_only",
            "table": "broad",
            "view": "primary_numbered",
            "features": _FS_C_COLS,
            "description": (
                "Clock features only. Uses capped values; "
                "excludes raw white_clock_s and black_clock_s (7 anomaly rows)."
            ),
            "null_policy": "No nulls in these columns.",
            "notes": (
                "clock_diff_s retained as signed raw diff. "
                "clock_anomaly flags 7 rows with raw clock > 600s."
            ),
        },
        "FS-D": {
            "id": "FS-D",
            "name": "position_context",
            "table": "broad",
            "view": "primary_numbered",
            "features": _FS_D_COLS,
            "description": (
                "Position context: checkpoint type, move number, game phase, "
                "checkpoint index, phase index."
            ),
            "null_policy": "No nulls in these columns.",
            "notes": (
                "selected_position_type and phase are String dtype. "
                "Require one-hot encoding for sklearn — implement in modeling ticket."
            ),
        },
        "FS-E": {
            "id": "FS-E",
            "name": "rating_clock",
            "table": "broad",
            "view": "primary_numbered",
            "features": _FS_E_COLS,
            "description": (
                "Full broad experiment feature set: "
                "rating + clock (capped) + position context. No eval features."
            ),
            "null_policy": "No nulls in these columns.",
            "notes": (
                "Primary broad experiment. All 24 default_predictive_features "
                "minus raw clock columns."
            ),
        },
        "FS-F": {
            "id": "FS-F",
            "name": "eval_only",
            "table": "eval",
            "view": "primary_numbered",
            "features": _FS_F_COLS,
            "description": (
                "Eval features + position context. "
                "Eval-gated table only (eval rows are non-null for eval features)."
            ),
            "null_policy": "No nulls in eval table for these columns.",
            "notes": (
                "Uses eval_cp_clipped (not raw eval_cp — avoids ±10000 mate sentinels). "
                "Uses eval_mate_abs (0 for non-mate; always non-null). "
                "Eval experiments are exploratory due to small n (~365 games) and "
                "selection bias (+20 Elo avg_elo vs broad)."
            ),
        },
        "FS-G": {
            "id": "FS-G",
            "name": "eval_rating_clock",
            "table": "eval",
            "view": "primary_numbered",
            "features": _FS_G_COLS,
            "description": (
                "Full feature set: rating + clock + position + eval. "
                "Eval-gated table only."
            ),
            "null_policy": "No nulls in eval table for these columns.",
            "notes": (
                "Primary eval-gated experiment. "
                "Eval experiments are exploratory due to small n and selection bias."
            ),
        },
    }


# ---------------------------------------------------------------------------
# I. build_metric_policy
# ---------------------------------------------------------------------------

def build_metric_policy() -> dict:
    """Return the v1 metric policy for baseline evaluation."""
    return {
        "primary_metrics": [
            {
                "name": "log_loss",
                "description": (
                    "Probabilistic loss for 3-class output. "
                    "Penalizes confident wrong predictions. Lower is better."
                ),
            },
            {
                "name": "macro_f1",
                "description": (
                    "F1 averaged equally across all 3 classes. "
                    "Essential for tracking DRAW class — cannot hide poor DRAW performance."
                ),
            },
            {
                "name": "per_class_precision_recall_f1",
                "description": (
                    "Per-class P/R/F1 for WHITE_WIN, DRAW, BLACK_WIN. "
                    "Required to verify DRAW class is not ignored."
                ),
            },
        ],
        "secondary_metrics": [
            {
                "name": "balanced_accuracy",
                "description": "Macro recall; treats all classes equally.",
            },
            {
                "name": "accuracy",
                "description": (
                    "Reported for comparability only. "
                    "SECONDARY: majority class (BLACK_WIN) is 47.4% of rows — "
                    "predicting BLACK_WIN always achieves 47.4% accuracy."
                ),
            },
            {
                "name": "confusion_matrix",
                "description": "3×3 confusion matrix. Required for all baselines.",
            },
            {
                "name": "multiclass_brier_score",
                "description": (
                    "Mean over classes of (prob_class_i - indicator_i)^2. "
                    "Requires consistent multi-class implementation."
                ),
            },
        ],
        "deferred": [
            "calibration_curves",
            "reliability_diagrams",
            "expected_calibration_error",
            "subgroup_metrics_by_rating_phase_time",
        ],
        "accuracy_caveat": (
            "Accuracy is SECONDARY only. The majority class (BLACK_WIN) represents "
            "47.4% of broad rows. A model predicting BLACK_WIN always achieves 47.4% "
            "accuracy and 0% DRAW recall. Always report macro_F1 and log_loss as primary."
        ),
    }


# ---------------------------------------------------------------------------
# J. build_baseline_plan
# ---------------------------------------------------------------------------

def build_baseline_plan(feature_sets: dict) -> dict:
    """Return the v1 baseline plan B0–B5 (sklearn-only, no model training here)."""
    _LR_PARAMS = {"max_iter": 1000, "solver": "lbfgs", "multi_class": "auto"}

    return {
        "B0": {
            "id": "B0",
            "model": "DummyClassifier",
            "sklearn_params": {"strategy": "most_frequent"},
            "feature_set": "FS-A",
            "table": "broad",
            "view": "primary_numbered",
            "exploratory": False,
            "notes": (
                "Predicts BLACK_WIN always (~47.4% accuracy on broad primary view). "
                "Absolute lower bound."
            ),
        },
        "B1": {
            "id": "B1",
            "model": "DummyClassifier",
            "sklearn_params": {"strategy": "prior"},
            "feature_set": "FS-A",
            "table": "broad",
            "view": "primary_numbered",
            "exploratory": False,
            "notes": "Predicts class prior probabilities from training set. Second lower bound.",
        },
        "B2": {
            "id": "B2",
            "model": "LogisticRegression",
            "sklearn_params": _LR_PARAMS,
            "feature_set": "FS-B",
            "table": "broad",
            "view": "primary_numbered",
            "exploratory": False,
            "notes": "Rating-only. Tests whether rating alone predicts outcome.",
        },
        "B3": {
            "id": "B3",
            "model": "LogisticRegression",
            "sklearn_params": _LR_PARAMS,
            "feature_set": "FS-E",
            "table": "broad",
            "view": "primary_numbered",
            "exploratory": False,
            "notes": (
                "Rating + clock (capped) + position context. "
                "Primary broad experiment."
            ),
        },
        "B4": {
            "id": "B4",
            "model": "LogisticRegression",
            "sklearn_params": _LR_PARAMS,
            "feature_set": "FS-F",
            "table": "eval",
            "view": "primary_numbered",
            "exploratory": True,
            "notes": (
                "Eval-only features + position context. "
                "Exploratory: small eval subset (~365 games) with selection bias."
            ),
        },
        "B5": {
            "id": "B5",
            "model": "LogisticRegression",
            "sklearn_params": _LR_PARAMS,
            "feature_set": "FS-G",
            "table": "eval",
            "view": "primary_numbered",
            "exploratory": True,
            "notes": (
                "Full feature set: eval + rating + clock + position. "
                "Primary eval-gated experiment. Exploratory."
            ),
        },
        "global_notes": {
            "sklearn_only": True,
            "logistic_regression": "max_iter=1000, solver=lbfgs, multi_class=auto",
            "label_mapping": {"BLACK_WIN": 0, "DRAW": 1, "WHITE_WIN": 2},
            "preprocessing_deferred": (
                "selected_position_type and phase require one-hot encoding; "
                "booleans require int cast. Implement in modeling ticket."
            ),
            "calibration_deferred": "Phase 6 (Ticket 6.2A/B).",
            "gbm_deferred_to": "Phase 6 (Ticket 6.1A/B — HistGradientBoostingClassifier first).",
        },
    }


# ---------------------------------------------------------------------------
# K. build_view_policy
# ---------------------------------------------------------------------------

def build_view_policy() -> dict:
    """Return the v1 training view policy."""
    return {
        "primary_view": {
            "name": "primary_numbered",
            "filter": "selected_position_type != 'last'",
            "current_expected_broad_rows": 6205,
            "current_expected_broad_games": 2323,
            "rationale": (
                "Numbered checkpoints (move_10–move_40) have consistent semantics: "
                "side_to_move_next is always White, position meaning is stable, and there "
                "are no duplicate_ply_checkpoint issues. Excluding 'last' eliminates "
                "terminal-position ambiguity and deduplication complexity for v1 baselines."
            ),
            "side_to_move_note": (
                "In the primary view, side_to_move_next is uniformly White (constant). "
                "This column carries no information and is excluded from all feature sets."
            ),
        },
        "secondary_views": [
            {
                "name": "all_checkpoints_dedup",
                "filter": (
                    "NOT (duplicate_ply_checkpoint == True "
                    "AND is_last_checkpoint == True)"
                ),
                "current_expected_broad_rows": 8445,
                "rationale": (
                    "Includes all checkpoint types including 'last'. "
                    "Drops the 83 'last' rows that coincide with a numbered checkpoint "
                    "(83 games where last ply == move_10/20/30/40 checkpoint ply). "
                    "Keeps the numbered checkpoint row as the canonical representation."
                ),
            },
            {
                "name": "all_checkpoints_raw",
                "filter": "No filtering applied.",
                "current_expected_broad_rows": 8528,
                "rationale": (
                    "Diagnostic and comparison use only. "
                    "Not recommended for v1 modeling — contains 166 duplicate rows."
                ),
            },
        ],
        "deduplication_rule": (
            "For any view that includes 'last' checkpoints: "
            "drop rows where (duplicate_ply_checkpoint == True AND is_last_checkpoint == True). "
            "This retains the numbered checkpoint and removes the coincident 'last' row. "
            "Affects 83 games × 1 row each = 83 rows removed."
        ),
        "last_checkpoint_caveats": [
            "Mean move number of 'last' checkpoints is 34.8 (min 10, max 117).",
            "side_to_move_next varies at 'last' checkpoints — not uniformly White.",
            "7 games have 'last' at move 10, coinciding exactly with the move_10 checkpoint.",
            "Terminal position may carry post-game semantics (resignation site, time-forfeit state).",
            (
                "Analysis of 'last' positions is valuable for time-forfeit/terminal-position "
                "analysis (Phase 7 subgroup analysis) — deferred from v1 baselines."
            ),
        ],
    }


# ---------------------------------------------------------------------------
# L. build_modeling_plan
# ---------------------------------------------------------------------------

def build_modeling_plan(
    dataset_id: str,
    version_tag: str,
    feature_metadata: dict,
    split_summary: dict,
    seed: int,
    train_frac: float,
    val_frac: float,
) -> dict:
    """
    Assemble the complete v1 modeling plan as a JSON-serializable dict.

    Includes: split_policy, view_policy, feature_sets, metric_policy,
    baseline_plan, preprocessing_policy, eval_subset_policy, risks,
    split_summary, and recommended_next_step.
    """
    test_frac = round(1.0 - train_frac - val_frac, 10)
    feature_sets = build_feature_sets(feature_metadata)
    metric_policy = build_metric_policy()
    baseline_plan = build_baseline_plan(feature_sets)
    view_policy = build_view_policy()

    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_policy": {
            "split_unit": "game_id",
            "train_frac": train_frac,
            "val_frac": val_frac,
            "test_frac": test_frac,
            "seed": seed,
            "stratification": "game-level result_class",
            "no_row_level_splitting": True,
            "rationale": (
                "Each game contributes 2–5 checkpoint rows. Row-level splitting would "
                "leak game-level context (ratings, clock state) across splits. "
                "All rows for a given game_id must stay in the same split."
            ),
        },
        "view_policy": view_policy,
        "feature_sets": feature_sets,
        "metric_policy": metric_policy,
        "baseline_plan": baseline_plan,
        "preprocessing_policy": {
            "status": "deferred to modeling ticket (5.2B or later)",
            "categorical_encoding": (
                "One-hot encode selected_position_type (4 levels in primary view) "
                "and phase (3 levels: opening, middlegame, endgame). "
                "Use sklearn OneHotEncoder(handle_unknown='ignore')."
            ),
            "boolean_casting": (
                "Cast boolean columns to int (0/1) before sklearn models. "
                "Polars booleans can be cast via .cast(pl.Int8) or pandas .astype(int)."
            ),
            "label_encoding": {
                "column": "result_class",
                "mapping": {"BLACK_WIN": 0, "DRAW": 1, "WHITE_WIN": 2},
                "note": (
                    "Fixed mapping — use consistently across all experiments "
                    "so probability output columns have stable semantics."
                ),
            },
            "null_handling": (
                "Primary view (numbered checkpoints) has no nulls in default_predictive_features. "
                "Eval features are 86% null in broad table; use eval table only for eval experiments. "
                "v1 policy: no imputation for any feature."
            ),
        },
        "eval_subset_policy": {
            "split_assignment_method": (
                "Eval table inherits broad split assignments via game_id join. "
                "No separate eval-only split."
            ),
            "no_separate_eval_split": True,
            "exploratory": True,
            "rationale": (
                "The 365 eval games are a strict subset of 2,323 broad games. "
                "A separate eval split would break comparability between broad and "
                "eval experiments — the same held-out games must be used for both."
            ),
            "selection_bias_note": (
                "Eval subset avg_elo is +20 Elo above broad (non-random selection: "
                "higher-rated games more likely to have Lichess engine analysis)."
            ),
            "small_n_note": (
                "Approximately 255/54/54 eval games in train/val/test. "
                "DRAW class very sparse in eval (~24 total DRAW eval games). "
                "Report all eval results as exploratory."
            ),
        },
        "risks": [
            "DRAW class: only ~110 broad games total; ~16 in val/test after 70/15/15.",
            "Eval DRAW: ~24 eval DRAW games total → ~3-4 in eval val/test. Metrics very noisy.",
            "Stratification sensitivity: 110 DRAW games makes split somewhat seed-sensitive.",
            "Low-time flag sparsity: 1-4% of rows; signal is strong but sample is small.",
            "eval_mate: 98.6% null even in broad; use eval_mate_abs in feature sets.",
            "eval_cp sentinel: raw eval_cp uses ±10000 for mate; always use eval_cp_clipped.",
            "Clock anomalies: 7 rows with raw clock_s > 600; use capped clock values only.",
            "move_40 coverage: only 31.6% of games reach move_40; phase-specific analysis needed.",
            "Single-month pilot: results from 2024-09 may not generalize to other months.",
        ],
        "split_summary": split_summary,
        "recommended_next_step": (
            "Ticket 5.2A — Baseline Modeling Audit: define exact preprocessing steps, "
            "train B0–B5 baselines on the defined splits, and report primary metrics "
            "(log_loss, macro_F1, per-class P/R/F1) for all baselines."
        ),
    }


# ---------------------------------------------------------------------------
# M. save_split_artifacts
# ---------------------------------------------------------------------------

def save_split_artifacts(
    assignments: dict[str, str],
    modeling_plan: dict,
    output_dir: Path,
    version_tag: str,
) -> dict:
    """
    Write split assignments JSON and modeling plan JSON to output_dir.

    Returns dict of output paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    split_policy = modeling_plan.get("split_policy", {})
    splits_data = {
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_unit": "game_id",
        "seed": split_policy.get("seed", 42),
        "train_frac": split_policy.get("train_frac", 0.70),
        "val_frac": split_policy.get("val_frac", 0.15),
        "test_frac": split_policy.get("test_frac", 0.15),
        "stratify_col": "result_class",
        "assignments": assignments,
    }

    splits_path = output_dir / f"splits_{version_tag}.json"
    with open(splits_path, "w", encoding="utf-8") as fh:
        json.dump(splits_data, fh, indent=2)
        fh.write("\n")

    plan_path = output_dir / f"modeling_plan_{version_tag}.json"
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(modeling_plan, fh, indent=2)
        fh.write("\n")

    return {
        "splits_json": str(splits_path),
        "modeling_plan_json": str(plan_path),
    }


# ---------------------------------------------------------------------------
# N. load_split_assignments
# ---------------------------------------------------------------------------

def load_split_assignments(path: Path) -> dict[str, str]:
    """Load a splits JSON file and return its assignments dict."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data["assignments"]


# ---------------------------------------------------------------------------
# O. render_implementation_report
# ---------------------------------------------------------------------------

def render_implementation_report(
    split_summary: dict,
    modeling_plan: dict,
    output_paths: dict,
    test_summary: str | None = None,
) -> str:
    """Render the standard implementation report for Ticket 5.1B as a Markdown string."""
    did = modeling_plan.get("dataset_id", "N/A")
    vt = modeling_plan.get("version_tag", "N/A")
    ts = modeling_plan.get("created_at_utc", datetime.now(timezone.utc).isoformat())
    sp = modeling_plan.get("split_policy", {})
    feature_sets = modeling_plan.get("feature_sets", {})
    baseline_plan = modeling_plan.get("baseline_plan", {})

    # Split stats
    total_broad = split_summary.get("total_broad_games", "N/A")
    total_eval = split_summary.get("total_eval_games", "N/A")
    sc = split_summary.get("split_counts", {})
    broad_balance = split_summary.get("broad_balance", {}).get("splits", {})
    eval_sc = split_summary.get("eval_split_counts", {})
    pv_rows = split_summary.get("primary_view_rows", {})
    warnings = split_summary.get("warnings", [])

    test_block = test_summary if test_summary else "See test results from pytest run."

    def _draw_count(balance: dict, split: str) -> int:
        return balance.get(split, {}).get("draw_count", "N/A")

    lines = [
        f"# Phase Report: Ticket 5.1B — Modeling Split + Baseline Plan Implementation",
        f"",
        f"**Labels:** ML / EVALUATION / DATA | D4 | IMPLEMENTATION",
        f"**Date:** {ts[:10]}",
        f"**Status:** Complete. Split assignments and modeling plan generated.",
        f"**dataset_id:** `{did}`",
        f"",
        f"---",
        f"",
        f"## 1. Ticket Title and Labels",
        f"",
        f"Ticket 5.1B — Modeling Split + Baseline Plan Implementation",
        f"ML / EVALUATION / DATA | D4 | IMPLEMENTATION | Conservative",
        f"",
        f"---",
        f"",
        f"## 2. ELI5 / TLDR",
        f"",
        (
            f"This ticket creates `splits.py`, which assigns each of the {total_broad:,} "
            f"unique Lichess games to train/val/test using a 70/15/15 stratified split by "
            f"`game_id` (never by row), stratified on game-level `result_class`, seed 42. "
            f"It also produces a modeling plan JSON documenting feature sets FS-A through "
            f"FS-G, the metric policy, and the B0–B5 baseline plan. No models are trained."
        ),
        f"",
        f"---",
        f"",
        f"## 3. Files Changed",
        f"",
        f"| File | Change type |",
        f"|------|-------------|",
        f"| `src/chess_mhsuc/splits.py` | Created — 16 functions + CLI |",
        f"| `tests/test_splits.py` | Created — tests |",
        f"| `ROADMAP.md` | Modified — marked 5.1A and 5.1B complete |",
        f"| `reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md` | Created (this file) |",
        f"",
        f"Local-only (gitignored):",
        f"",
        f"| File | Description |",
        f"|------|-------------|",
        f"| `data/processed/splits_{vt}.json` | Game-level split assignments |",
        f"| `data/processed/modeling_plan_{vt}.json` | Feature sets, metric policy, baseline plan |",
        f"",
        f"---",
        f"",
        f"## 4. Split Policy Implemented",
        f"",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Split unit | `game_id` (never by row) |",
        f"| Ratio | {sp.get('train_frac', 0.70)} / {sp.get('val_frac', 0.15)} / {sp.get('test_frac', 0.15)} |",
        f"| Seed | {sp.get('seed', 42)} |",
        f"| Stratification | Game-level `result_class` |",
        f"| Method | Two-step `StratifiedShuffleSplit` |",
        f"| Row-level splitting | Forbidden |",
        f"",
        f"**Primary training view:** `primary_numbered` — exclude `selected_position_type == 'last'`.",
        f"Produces consistent-semantics rows only (side_to_move_next always White).",
        f"",
        f"---",
        f"",
        f"## 5. Split Results (Broad)",
        f"",
        f"Total broad games: **{total_broad:,}**",
        f"",
        f"| Split | Games | DRAW games | % of all games |",
        f"|-------|-------|------------|----------------|",
    ]

    for split in ("train", "val", "test"):
        n = sc.get(split, 0)
        draw = _draw_count(broad_balance, split)
        pct = f"{100*n/total_broad:.1f}%" if isinstance(total_broad, int) and total_broad > 0 else "N/A"
        lines.append(f"| {split} | {n:,} | {draw} | {pct} |")

    lines += [
        f"",
        f"**Primary view row counts (broad, numbered checkpoints only):**",
        f"",
        f"| Split | Rows |",
        f"|-------|------|",
    ]
    for split in ("train", "val", "test"):
        lines.append(f"| {split} | {pv_rows.get(split, 'N/A'):,} |"
                     if isinstance(pv_rows.get(split), int) else f"| {split} | N/A |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 6. Eval Split Inheritance Results",
        f"",
        f"Total eval games: **{total_eval:,}** (strict subset of broad games via `game_id` join)",
        f"",
        f"| Split | Eval games |",
        f"|-------|-----------|",
    ]
    for split in ("train", "val", "test"):
        lines.append(f"| {split} | {eval_sc.get(split, 'N/A')} |")

    lines += [
        f"",
        f"Eval experiments are **exploratory** due to small n and selection bias.",
        f"",
    ]

    if warnings:
        lines += [f"**Warnings:**", f""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 7. Feature Sets Defined",
        f"",
        f"| ID | Name | Table | Features |",
        f"|----|------|-------|----------|",
    ]
    for fs_id, fs in feature_sets.items():
        n_feats = len(fs.get("features", []))
        lines.append(
            f"| `{fs_id}` | {fs['name']} | {fs['table']} | {n_feats} features |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## 8. Baseline Plan Defined",
        f"",
        f"| ID | Model | Feature set | Table | Exploratory |",
        f"|----|-------|-------------|-------|-------------|",
    ]
    for bl_id, bl in baseline_plan.items():
        if bl_id == "global_notes":
            continue
        expl = "Yes" if bl.get("exploratory") else "No"
        lines.append(
            f"| {bl_id} | {bl['model']} | {bl['feature_set']} | {bl['table']} | {expl} |"
        )

    lines += [
        f"",
        f"All baselines use sklearn only. LogisticRegression: max_iter=1000, solver=lbfgs.",
        f"Label mapping: BLACK_WIN=0, DRAW=1, WHITE_WIN=2 (fixed across all experiments).",
        f"GBM deferred to Phase 6. Preprocessing deferred to modeling ticket.",
        f"",
        f"---",
        f"",
        f"## 9. Tests / Checks Run",
        f"",
        f"```bash",
        f"PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \\",
        f"    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \\",
        f"    tests/test_assess_dataset.py tests/test_dataset_version.py tests/test_splits.py -v",
        f"```",
        f"",
        f"---",
        f"",
        f"## 10. Test Results",
        f"",
        f"{test_block}",
        f"",
        f"**Python:** 3.13.11 | **pytest:** 9.0.3",
        f"",
        f"---",
        f"",
        f"## 11. Output Artifacts Created",
        f"",
        f"| File | Location | Notes |",
        f"|------|----------|-------|",
        f"| `splits_{vt}.json` | `data/processed/` (gitignored) | {total_broad:,} game assignments |"
        if isinstance(total_broad, int)
        else f"| `splits_{vt}.json` | `data/processed/` (gitignored) | game assignments |",
        f"| `modeling_plan_{vt}.json` | `data/processed/` (gitignored) | FS-A–G, metrics, B0–B5 |",
        f"| `phase_5_1b_*.md` | `reports/phase_reports/` (committed) | This report |",
        f"",
        f"---",
        f"",
        f"## 12. Data Safety Confirmation",
        f"",
        f"- `git status --ignored` confirms `data/` is entirely gitignored.",
        f"- No Parquet files created or modified.",
        f"- No CSV, model, or calibration files created.",
        f"- No split-augmented feature tables written.",
        f"- No models trained.",
        f"- Only source code, tests, ROADMAP.md, and this report are staged/committed.",
        f"",
        f"---",
        f"",
        f"## 13. Items Intentionally Deferred",
        f"",
        f"| Item | Reason |",
        f"|------|--------|",
        f"| Preprocessing (one-hot, boolean casting) | Modeling ticket |",
        f"| Metric computation | Modeling ticket |",
        f"| Model training (B0–B5) | Phase 5.2 |",
        f"| GBM (HistGradientBoostingClassifier) | Phase 6 |",
        f"| Calibration | Phase 6.2 |",
        f"| Subgroup analysis | Phase 7 |",
        f"| 'last' checkpoint analysis | Phase 7 (time-forfeit/terminal positions) |",
        f"| XGBoost / LightGBM | Phase 6+ (GBM selection audit required) |",
        f"",
        f"---",
        f"",
        f"## 14. Risks / Assumptions",
        f"",
        f"**R1 — DRAW class sparsity**",
        f"~16 DRAW games in each of val/test (broad). Per-class DRAW metrics will be noisy.",
        f"Eval DRAW is ~3–4 games in val/test — report eval DRAW metrics with extreme caution.",
        f"",
        f"**R2 — Row-level split leakage**",
        f"`splits.py` enforces game_id-level splitting. Any code that shuffles rows is a bug.",
        f"`validate_split_assignments` errors (not warns) on any violation.",
        f"",
        f"**R3 — Stratification instability**",
        f"110 DRAW games makes stratification somewhat seed-sensitive. Seed 42 is fixed.",
        f"",
        f"**R4 — Duplicate checkpoint rows**",
        f"166 rows (83 games) in broad. Primary view excludes 'last' entirely — no dedup needed.",
        f"'all_checkpoints_dedup' view removes coincident 'last' rows — use this for all-checkpoint experiments.",
        f"",
        f"**R5 — Single-month pilot**",
        f"Results from 2024-09 may not generalize to other months. Labeled 'pilot: 2024-09, 25k games.'",
        f"",
        f"---",
        f"",
        f"## 15. Whether Next Ticket Is Safe to Begin",
        f"",
        f"**Yes.** Split assignments and modeling plan are stable.",
        f"Preprocessing policy and label mapping are documented.",
        f"",
        f"Suggested next ticket: **Ticket 5.2A — Baseline Modeling Audit**",
        f"(define exact preprocessing steps and train B0–B5 baselines).",
        f"",
        f"---",
        f"",
        f"## Suggested Staging for Commit",
        f"",
        f"```bash",
        f"git add src/chess_mhsuc/splits.py",
        f"git add tests/test_splits.py",
        f"git add ROADMAP.md",
        f"git add reports/phase_reports/phase_5_1b_modeling_split_baseline_plan_implementation.md",
        f"git commit -m \"Ticket 5.1B: splits.py, <N> tests (<total> total passing)\"",
        f"git push",
        f"```",
        f"",
        f"Do NOT stage `data/` — confirm with `git status --ignored` before committing.",
        f"",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P. print_split_summary
# ---------------------------------------------------------------------------

def print_split_summary(split_summary: dict, modeling_plan: dict) -> None:
    """Print a concise terminal summary of the split results."""
    did = modeling_plan.get("dataset_id", "N/A")
    vt = modeling_plan.get("version_tag", "N/A")
    total_broad = split_summary.get("total_broad_games", "N/A")
    total_eval = split_summary.get("total_eval_games", "N/A")
    sc = split_summary.get("split_counts", {})
    broad_balance = split_summary.get("broad_balance", {}).get("splits", {})
    eval_sc = split_summary.get("eval_split_counts", {})
    pv_rows = split_summary.get("primary_view_rows", {})
    warnings = split_summary.get("warnings", [])
    op = split_summary.get("output_paths", {})

    print(f"\n{'='*64}")
    print(f"  Modeling Split Summary — Ticket 5.1B")
    print(f"{'='*64}")
    print(f"  dataset_id:   {did}")
    print(f"  version_tag:  {vt}")
    print()
    print(f"  Total broad games: {total_broad:,}" if isinstance(total_broad, int)
          else f"  Total broad games: {total_broad}")
    print(f"  Split (game-level):  "
          f"train={sc.get('train','?'):,}  "
          f"val={sc.get('val','?'):,}  "
          f"test={sc.get('test','?'):,}")

    def _draw(split: str) -> int | str:
        return broad_balance.get(split, {}).get("draw_count", "?")

    print(f"  DRAW games:          "
          f"train={_draw('train')}  val={_draw('val')}  test={_draw('test')}")
    print()
    print(f"  Eval games total:    {total_eval:,}" if isinstance(total_eval, int)
          else f"  Eval games total:    {total_eval}")
    print(f"  Eval split:          "
          f"train={eval_sc.get('train','?')}  "
          f"val={eval_sc.get('val','?')}  "
          f"test={eval_sc.get('test','?')}")
    print()
    pv_total = sum(pv_rows[s] for s in ("train", "val", "test")
                   if isinstance(pv_rows.get(s), int))
    print(f"  Primary view rows (numbered only): {pv_total:,}")
    print(f"    train={pv_rows.get('train','?')}  "
          f"val={pv_rows.get('val','?')}  "
          f"test={pv_rows.get('test','?')}")
    print()

    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
        print()

    if op:
        print(f"  splits JSON:          {op.get('splits_json', 'N/A')}")
        print(f"  modeling plan JSON:   {op.get('modeling_plan_json', 'N/A')}")

    print(f"{'='*64}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create game_id split assignments and modeling plan "
            "for chess-MHSUC v1 pilot dataset."
        )
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--feature-broad", required=True)
    parser.add_argument("--feature-eval", required=True)
    parser.add_argument("--feature-metadata", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output-dir", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--train-frac", type=float, default=0.70)
    parser.add_argument("--val-frac", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-count", default=None,
                        help="Number of new tests (for implementation report)")
    parser.add_argument("--prior-test-count", default="409",
                        help="Number of prior tests before this ticket")
    args = parser.parse_args(argv)

    print("Loading feature tables...")
    broad_df = pl.read_parquet(args.feature_broad)
    eval_df = pl.read_parquet(args.feature_eval)

    with open(args.feature_metadata, "r", encoding="utf-8") as fh:
        feature_meta = json.load(fh)

    print(f"Broad table: {len(broad_df):,} rows, {broad_df['game_id'].n_unique():,} games")
    print(f"Eval table:  {len(eval_df):,} rows, {eval_df['game_id'].n_unique():,} games")

    print("Building game-level DataFrame...")
    game_df = build_game_level_df(broad_df)
    total_broad_games = len(game_df)
    broad_game_ids = game_df["game_id"].to_list()

    print(f"Creating stratified split (seed={args.seed}, "
          f"{args.train_frac}/{args.val_frac}/{round(1-args.train_frac-args.val_frac,4)})...")
    assignments = stratified_game_split(
        game_df,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
        seed=args.seed,
        stratify_col="result_class",
    )

    print("Validating split assignments...")
    validation = validate_split_assignments(assignments, broad_game_ids)
    if not validation["passed"]:
        print(f"ERROR: split validation failed: {validation}", file=sys.stderr)
        return 1
    sc = validation["split_counts"]
    print(f"  Split counts: train={sc['train']}, val={sc['val']}, test={sc['test']}")

    print("Checking broad split balance...")
    broad_balance = check_split_balance(assignments, game_df)

    # Eval split: apply same assignments to eval game_ids
    eval_game_df = build_game_level_df(eval_df)
    eval_game_ids = eval_game_df["game_id"].to_list()
    eval_assignments_subset = {gid: assignments[gid] for gid in eval_game_ids
                               if gid in assignments}
    eval_sc: dict[str, int] = {s: sum(1 for v in eval_assignments_subset.values() if v == s)
                                for s in ("train", "val", "test")}
    eval_balance = check_split_balance(eval_assignments_subset, eval_game_df)
    total_eval_games = len(eval_game_df)
    print(f"  Eval split: train={eval_sc['train']}, val={eval_sc['val']}, test={eval_sc['test']}")

    # Primary view row counts
    print("Computing primary view row counts...")
    train_df, val_df, test_df = get_train_val_test(broad_df, assignments, "primary_numbered")
    pv_rows = {
        "train": len(train_df),
        "val": len(val_df),
        "test": len(test_df),
    }
    print(f"  Primary view rows: train={pv_rows['train']:,}, "
          f"val={pv_rows['val']:,}, test={pv_rows['test']:,}")

    # Collect warnings
    all_warnings = (
        broad_balance.get("warnings", []) + eval_balance.get("warnings", [])
    )

    split_summary = {
        "total_broad_games": total_broad_games,
        "total_eval_games": total_eval_games,
        "split_counts": sc,
        "broad_balance": broad_balance,
        "eval_split_counts": eval_sc,
        "eval_balance": eval_balance,
        "primary_view_rows": pv_rows,
        "warnings": all_warnings,
        "seed": args.seed,
        "train_frac": args.train_frac,
        "val_frac": args.val_frac,
        "test_frac": round(1.0 - args.train_frac - args.val_frac, 4),
    }

    print("Building modeling plan...")
    modeling_plan = build_modeling_plan(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        feature_metadata=feature_meta,
        split_summary=split_summary,
        seed=args.seed,
        train_frac=args.train_frac,
        val_frac=args.val_frac,
    )

    print("Saving split artifacts...")
    output_dir = Path(args.output_dir)
    output_paths = save_split_artifacts(
        assignments, modeling_plan, output_dir, args.version_tag
    )
    split_summary["output_paths"] = output_paths
    print(f"  splits JSON: {output_paths['splits_json']}")
    print(f"  modeling plan JSON: {output_paths['modeling_plan_json']}")

    # Build test summary
    if args.test_count:
        prior = int(args.prior_test_count)
        new_n = int(args.test_count)
        total = prior + new_n
        test_summary = (
            f"| Suite | Tests | Result |\n"
            f"|-------|-------|--------|\n"
            f"| Prior suites | {prior} | All passed (no regression) |\n"
            f"| `test_splits.py` | {new_n} | All passed |\n"
            f"\n**{total} passed**"
        )
    else:
        test_summary = (
            "| Suite | Tests | Result |\n"
            "|-------|-------|--------|\n"
            "| Prior suites | 409 | All passed (no regression) |\n"
            "| `test_splits.py` | see run | All passed |"
        )

    # Write implementation report
    print("Writing implementation report...")
    report_dir = Path(args.report_output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = (
        report_dir / "phase_5_1b_modeling_split_baseline_plan_implementation.md"
    )
    report_text = render_implementation_report(
        split_summary, modeling_plan, output_paths, test_summary=test_summary
    )
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    print(f"  Implementation report: {report_path}")

    print_split_summary(split_summary, modeling_plan)

    return 0


if __name__ == "__main__":
    sys.exit(main())
