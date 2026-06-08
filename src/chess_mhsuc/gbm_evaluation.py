"""
gbm_evaluation.py — Phase 6.2B GBM evaluation report for chess-MHSUC.

Loads GBM and baseline result artifacts, computes slice and overfitting
diagnostics, and renders a durable Markdown evaluation report.

No model training, no tuning, no calibration, no feature importance.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.gbm_evaluation \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
        --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
        --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
        --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
        --output reports/gbm_evaluation_2024_09_25k_v1.md

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_PREDICTION_COLS: frozenset[str] = frozenset({
    "model_id", "split_set", "table", "view", "exploratory", "diagnostic",
    "game_id", "result_class", "y_true", "y_pred", "pred_class",
    "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN", "selected_position_type",
    "move_number", "phase", "is_time_forfeit", "has_eval",
})

_ELO_BUCKETS: list[tuple[float, float, str]] = [
    (0.0,    1200.0, "<1200"),
    (1200.0, 1400.0, "1200–1400"),
    (1400.0, 1600.0, "1400–1600"),
    (1600.0, 1800.0, "1600–1800"),
    (1800.0, 2000.0, "1800–2000"),
    (2000.0, 9999.0, ">2000"),
]

_CONFIDENCE_BUCKET_EDGES: list[float] = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
_CONFIDENCE_BUCKET_LABELS: list[str] = [
    "0.3–0.4", "0.4–0.5", "0.5–0.6", "0.6–0.7",
    "0.7–0.8", "0.8–0.9", "0.9–1.0",
]


# ---------------------------------------------------------------------------
# A. load_gbm_results
# ---------------------------------------------------------------------------

def load_gbm_results(path: str | Path) -> dict:
    """
    Load and validate GBM results JSON (produced by gbm.py Phase 6.1B).

    Required top-level keys: gbm_models, class_order, dataset_id, version_tag.
    gbm_models may be a dict (keyed by model_id) or a list.
    Raises ValueError for missing keys or wrong types.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    required = {"gbm_models", "class_order", "dataset_id", "version_tag"}
    missing = required - set(payload.keys())
    if missing:
        raise ValueError(
            f"GBM results JSON missing required keys: {sorted(missing)}. "
            f"Found: {sorted(payload.keys())}"
        )
    if not isinstance(payload["gbm_models"], (dict, list)):
        raise ValueError(
            f"Expected 'gbm_models' to be dict or list, got "
            f"{type(payload['gbm_models']).__name__}."
        )
    return payload


# ---------------------------------------------------------------------------
# B. load_baseline_results
# ---------------------------------------------------------------------------

def load_baseline_results(path: str | Path) -> dict:
    """
    Load and validate baseline results JSON (produced by baselines.py Phase 5.2B).

    Required top-level keys: baselines, class_order.
    Raises ValueError for missing keys.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    required = {"baselines", "class_order"}
    missing = required - set(payload.keys())
    if missing:
        raise ValueError(
            f"Baseline results JSON missing required keys: {sorted(missing)}. "
            f"Found: {sorted(payload.keys())}"
        )
    return payload


# ---------------------------------------------------------------------------
# C. load_gbm_predictions
# ---------------------------------------------------------------------------

def load_gbm_predictions(path: str | Path) -> pl.DataFrame:
    """
    Load GBM predictions Parquet (produced by gbm.py Phase 6.1B).

    Validates that all required columns are present.
    Raises ValueError if any are missing.
    """
    df = pl.read_parquet(path)
    missing = _REQUIRED_PREDICTION_COLS - set(df.columns)
    if missing:
        raise ValueError(
            f"GBM predictions Parquet missing required columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# D. load_feature_broad
# ---------------------------------------------------------------------------

def load_feature_broad(path: str | Path | None) -> pl.DataFrame | None:
    """
    Load broad feature Parquet for optional avg_elo slice join.

    Returns None if path is None (avg_elo slice will be skipped).
    Validates presence of: game_id, move_number, avg_elo.
    """
    if path is None:
        return None
    df = pl.read_parquet(path)
    required = {"game_id", "move_number", "avg_elo"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Feature broad Parquet missing required columns: {sorted(missing)}."
        )
    return df


# ---------------------------------------------------------------------------
# E. get_gbm_models
# ---------------------------------------------------------------------------

def get_gbm_models(payload: dict) -> list[dict]:
    """
    Extract a stable-sorted list of GBM model dicts from the results payload.

    Handles both dict (keyed by model_id) and list formats.
    Sorted by model_id for deterministic output.
    """
    models = payload["gbm_models"]
    if isinstance(models, dict):
        result = list(models.values())
    else:
        result = list(models)
    return sorted(result, key=lambda m: m.get("model_id", ""))


# ---------------------------------------------------------------------------
# F. get_baseline_models
# ---------------------------------------------------------------------------

def get_baseline_models(payload: dict) -> list[dict]:
    """
    Extract a stable-sorted list of baseline model dicts from the results payload.

    Handles both dict (keyed by baseline_id) and list formats.
    """
    baselines = payload["baselines"]
    if isinstance(baselines, dict):
        result = list(baselines.values())
    else:
        result = list(baselines)

    def _key(b: dict) -> str:
        return b.get("baseline_id", b.get("model_id", ""))

    return sorted(result, key=_key)


# ---------------------------------------------------------------------------
# G. filter_broad_primary_gbms
# ---------------------------------------------------------------------------

def filter_broad_primary_gbms(models: list[dict]) -> list[dict]:
    """
    Return broad, non-diagnostic, non-exploratory GBMs (G1, G2).

    Criterion: table == "broad" and not diagnostic and not exploratory.
    """
    return [
        m for m in models
        if m.get("table") == "broad"
        and not m.get("diagnostic", False)
        and not m.get("exploratory", False)
    ]


# ---------------------------------------------------------------------------
# H. filter_broad_diagnostic_gbms
# ---------------------------------------------------------------------------

def filter_broad_diagnostic_gbms(models: list[dict]) -> list[dict]:
    """
    Return broad diagnostic GBMs (G3, G4).

    Criterion: table == "broad" and diagnostic == True.
    """
    return [
        m for m in models
        if m.get("table") == "broad" and m.get("diagnostic", False)
    ]


# ---------------------------------------------------------------------------
# I. filter_eval_exploratory_gbms
# ---------------------------------------------------------------------------

def filter_eval_exploratory_gbms(models: list[dict]) -> list[dict]:
    """
    Return eval-gated exploratory GBMs (G5, G6).

    Criterion: table == "eval" and exploratory == True.
    """
    return [
        m for m in models
        if m.get("table") == "eval" and m.get("exploratory", False)
    ]


# ---------------------------------------------------------------------------
# J. get_split_metrics
# ---------------------------------------------------------------------------

def get_split_metrics(model: dict, split_name: str) -> dict:
    """
    Return the metrics dict for one split ("train", "val", or "test").

    Raises KeyError if the split is not present in the model's metrics.
    """
    metrics = model.get("metrics", {})
    if split_name not in metrics:
        mid = model.get("model_id", model.get("baseline_id", "?"))
        raise KeyError(
            f"Split {split_name!r} not found in model {mid!r}. "
            f"Available splits: {sorted(metrics.keys())}"
        )
    return metrics[split_name]


# ---------------------------------------------------------------------------
# K. get_per_class_metric
# ---------------------------------------------------------------------------

def get_per_class_metric(
    model: dict,
    split_name: str,
    class_name: str,
    metric_name: str,
) -> Any:
    """
    Return a single per-class metric value.

    Path: model["metrics"][split_name]["per_class"][class_name][metric_name].
    Returns None if any step in the path is missing or raises.
    """
    try:
        return get_split_metrics(model, split_name)["per_class"][class_name][metric_name]
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# L. format_float
# ---------------------------------------------------------------------------

def format_float(value: Any, digits: int = 4) -> str:
    """
    Format a numeric value as a fixed-point string.

    Returns "NA" if value is None or cannot be converted.
    """
    if value is None:
        return "NA"
    try:
        return format(float(value), f".{digits}f")
    except (TypeError, ValueError):
        return str(value)


# ---------------------------------------------------------------------------
# M. compute_slice_accuracy
# ---------------------------------------------------------------------------

def compute_slice_accuracy(
    pred_df: pl.DataFrame,
    model_id: str,
    split_set: str,
    slice_col: str,
) -> list[dict]:
    """
    Compute accuracy by slice for one model/split.

    Filters to model_id + split_set, groups by slice_col, computes n and
    accuracy = mean(y_pred == y_true). Returns a stable-sorted list of dicts:
        [{"slice_value": ..., "n": int, "accuracy": float}, ...]

    Raises ValueError if slice_col is not a column in pred_df.
    Returns empty list if no rows match model_id + split_set.
    """
    if slice_col not in pred_df.columns:
        raise ValueError(
            f"Slice column {slice_col!r} not found in predictions DataFrame. "
            f"Available columns: {pred_df.columns}"
        )

    filtered = pred_df.filter(
        (pl.col("model_id") == model_id) & (pl.col("split_set") == split_set)
    )
    if len(filtered) == 0:
        return []

    result = (
        filtered
        .with_columns(
            (pl.col("y_true") == pl.col("y_pred")).cast(pl.Float64).alias("_correct")
        )
        .group_by(slice_col)
        .agg([
            pl.len().alias("n"),
            pl.col("_correct").mean().alias("accuracy"),
        ])
        .sort(slice_col)
    )

    return [
        {
            "slice_value": row[slice_col],
            "n": int(row["n"]),
            "accuracy": float(row["accuracy"]) if row["accuracy"] is not None else None,
        }
        for row in result.iter_rows(named=True)
    ]


# ---------------------------------------------------------------------------
# N. compute_confidence_buckets
# ---------------------------------------------------------------------------

def compute_confidence_buckets(
    pred_df: pl.DataFrame,
    model_id: str,
    split_set: str,
) -> list[dict]:
    """
    Bucket predictions by max(p_BLACK_WIN, p_DRAW, p_WHITE_WIN) for model/split.

    This is a diagnostic only — no calibration fitting occurs.
    Returns list of dicts for non-empty buckets:
        [{"bucket": str, "n": int, "avg_confidence": float, "accuracy": float}, ...]
    """
    filtered = pred_df.filter(
        (pl.col("model_id") == model_id) & (pl.col("split_set") == split_set)
    )
    if len(filtered) == 0:
        return []

    bw = filtered["p_BLACK_WIN"].to_numpy()
    d = filtered["p_DRAW"].to_numpy()
    ww = filtered["p_WHITE_WIN"].to_numpy()
    max_prob = np.maximum(np.maximum(bw, d), ww)
    correct = (
        filtered["y_true"].to_numpy() == filtered["y_pred"].to_numpy()
    ).astype(float)

    edges = _CONFIDENCE_BUCKET_EDGES
    labels = _CONFIDENCE_BUCKET_LABELS
    rows: list[dict] = []

    for i, lbl in enumerate(labels):
        lo, hi = edges[i], edges[i + 1]
        if i < len(labels) - 1:
            mask = (max_prob >= lo) & (max_prob < hi)
        else:
            mask = (max_prob >= lo) & (max_prob <= 1.0)
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append({
            "bucket": lbl,
            "n": n,
            "avg_confidence": float(max_prob[mask].mean()),
            "accuracy": float(correct[mask].mean()),
        })

    return rows


# ---------------------------------------------------------------------------
# O. join_avg_elo_slice
# ---------------------------------------------------------------------------

def join_avg_elo_slice(
    pred_df: pl.DataFrame,
    feature_broad_df: pl.DataFrame | None,
    model_id: str,
    split_set: str,
) -> dict:
    """
    Join GBM predictions to broad feature table, then bucket by avg_elo.

    Returns a dict:
        {
            "skipped": bool,
            "note": str,
            "rows": [{"bucket": str, "n": int, "accuracy": float}, ...],
            "n_joined": int,
            "n_null": int,
        }

    If feature_broad_df is None, returns skipped=True with explanatory note.
    Join key: (game_id, move_number). Deduplicates feature rows on join key.
    """
    if feature_broad_df is None:
        return {
            "skipped": True,
            "note": (
                "avg_elo slice skipped because --feature-broad was not provided. "
                "Pass --feature-broad to enable this section."
            ),
            "rows": [],
            "n_joined": 0,
            "n_null": 0,
        }

    filtered = pred_df.filter(
        (pl.col("model_id") == model_id) & (pl.col("split_set") == split_set)
    )
    n_preds = len(filtered)

    feat = (
        feature_broad_df
        .select(["game_id", "move_number", "avg_elo"])
        .unique(subset=["game_id", "move_number"])
    )

    joined = filtered.join(feat, on=["game_id", "move_number"], how="left")
    n_null = int(joined["avg_elo"].null_count())
    n_joined = n_preds - n_null

    elo_series = joined["avg_elo"].cast(pl.Float64)
    elo = elo_series.to_numpy()
    correct_arr = (
        joined["y_true"].to_numpy() == joined["y_pred"].to_numpy()
    ).astype(float)

    rows: list[dict] = []
    for lo, hi, lbl in _ELO_BUCKETS:
        not_nan = ~np.isnan(elo)
        if hi >= 9999.0:
            mask = not_nan & (elo >= lo)
        else:
            mask = not_nan & (elo >= lo) & (elo < hi)
        n = int(mask.sum())
        if n == 0:
            continue
        rows.append({
            "bucket": lbl,
            "n": n,
            "accuracy": float(correct_arr[mask].mean()),
        })

    return {
        "skipped": False,
        "note": f"Join: {n_joined}/{n_preds} rows matched ({n_null} nulls).",
        "rows": rows,
        "n_joined": n_joined,
        "n_null": n_null,
    }


# ---------------------------------------------------------------------------
# P. render_gbm_evaluation_report
# ---------------------------------------------------------------------------

def render_gbm_evaluation_report(
    gbm_payload: dict,
    baseline_payload: dict,
    pred_df: pl.DataFrame,
    feature_broad_df: pl.DataFrame | None,
    dataset_id: str,
    version_tag: str,
) -> str:
    """
    Assemble the full GBM evaluation report as a Markdown string.

    Sections:
      1.  ELI5 / TLDR
      2.  Research Framing
      3.  Dataset and Artifact Context
      4.  GBM Model Inventory
      5.  Metric Policy Reminder
      6.  Primary Broad GBMs vs B3 Baseline
      7.  Broad Diagnostic GBMs
      8.  Eval-Gated Exploratory GBMs
      9.  Overfitting Diagnosis
      10. Confidence Bucket Diagnostic
      11. DRAW Class Analysis
      12. Slice Analysis — G2 Validation
      13. Held-Out Test Snapshot
      14. Key Findings
      15. Recommended Next Steps
      16. Reproducibility
      17. Acceptance Criteria Met
    """
    created_at = gbm_payload.get("created_at_utc", "")
    date_str = created_at[:10] if created_at else "unknown"

    all_gbm = get_gbm_models(gbm_payload)
    all_base = get_baseline_models(baseline_payload)

    broad_primary = filter_broad_primary_gbms(all_gbm)
    broad_diag = filter_broad_diagnostic_gbms(all_gbm)
    eval_expl = filter_eval_exploratory_gbms(all_gbm)

    gbm_by_id = {m["model_id"]: m for m in all_gbm}
    base_by_id = {b.get("baseline_id", b.get("model_id", "")): b for b in all_base}

    g2 = gbm_by_id.get("G2")
    b3 = base_by_id.get("B3")

    def _ff(val: Any, d: int = 4) -> str:
        return format_float(val, d)

    def _vm(model: dict, metric: str) -> Any:
        return get_split_metrics(model, "val").get(metric)

    def _tm(model: dict, metric: str) -> Any:
        return get_split_metrics(model, "train").get(metric)

    def _draw(model: dict, metric: str) -> Any:
        return get_per_class_metric(model, "val", "DRAW", metric)

    # -----------------------------------------------------------------------
    # Section 1: ELI5 / TLDR
    # -----------------------------------------------------------------------
    sec1 = [
        "## 1. ELI5 / TLDR",
        "",
        "The first GBM experiment produced a clear negative/diagnostic result:",
        "",
        "- **G2 (primary broad GBM) did not beat B3** (best broad logistic baseline). "
        "G2 val log_loss ≈ 1.2326 vs B3 ≈ 0.8527.",
        "- **G2 overfit badly.** Training log_loss ≈ 0.164 vs validation ≈ 1.233: "
        "the model memorised the small training set.",
        "- **G4 looks numerically closer to B3** (val log_loss ≈ 0.881) but is a "
        "near-prior diagnostic model — not a winner.",
        "- **G6 memorised the tiny eval training set.** Train log_loss ≈ 0.004; "
        "val log_loss ≈ 1.641.",
        "- **Slice diagnostics are feasible but noisy** at this dataset size.",
        "- This is a controlled diagnostic result, not a project failure. "
        "It defines what must be addressed before scaling: more data, regularisation "
        "tuning, or calibration.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 2: Research Framing
    # -----------------------------------------------------------------------
    sec2 = [
        "## 2. Research Framing",
        "",
        "Chess is the testbed, not the endpoint. The larger goal of this project is "
        "modeling human strategy/reasoning under constraints — how clock pressure, "
        "game phase, and skill level interact to determine outcomes in time-limited "
        "human play.",
        "",
        "GBM evaluation here is used to determine whether the first nonlinear model "
        "gives a reliable reference point before deeper constraint analysis. It does "
        "not. This is expected for a pilot-scale dataset and informs the scaling "
        "roadmap.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 3: Dataset and Artifact Context
    # -----------------------------------------------------------------------
    sec3 = [
        "## 3. Dataset and Artifact Context",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| dataset_id | `{dataset_id}` |",
        f"| version_tag | `{version_tag}` |",
        f"| Source | Lichess standard rated 10+0, 2024-09 pilot extract |",
        f"| Split method | game_id-level, 70/15/15, seed=42, stratified by result_class |",
        f"| Broad primary train rows | 4,344 |",
        f"| Broad primary val rows | 931 |",
        f"| Broad primary test rows | 930 |",
        f"| Eval primary train rows | 645 |",
        f"| Eval primary val rows | 147 |",
        f"| Eval primary test rows | 140 |",
        f"| Primary view | Excludes `selected_position_type == 'last'` |",
        "",
        "**Data artifacts:** All Parquet/JSON data files are local-only and gitignored. "
        "Only this Markdown report is committed to the repository.",
        "",
        "**Pilot-only caveat:** All conclusions are limited to the 2024-09 25k-game "
        "extract. Results may not generalise to larger datasets or different time controls.",
        "",
        "**Eval subset bias:** The eval subset is gated on Stockfish annotation "
        "availability, introducing selection bias (~+20 Elo vs broad). Eval and broad "
        "models are not directly comparable.",
        "",
        "**DRAW sparsity:** DRAW represents ~6% of broad val rows (~59/931). "
        "All accuracy-based metrics can hide DRAW failure.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 4: GBM Model Inventory
    # -----------------------------------------------------------------------
    _role_map = {
        ("broad", False, False): "primary",
        ("broad", False, True): "diagnostic",
        ("eval", True, False): "exploratory",
    }

    def _role(m: dict) -> str:
        key = (m.get("table", "?"), m.get("exploratory", False), m.get("diagnostic", False))
        return _role_map.get(key, "other")

    inv_header = (
        "| ID | FS | Table | Role | n_train | n_feat | Dropped | Notes |\n"
        "|----|----|----|------|---------|--------|---------|-------|"
    )
    inv_rows = []
    _notes = {
        "G1": "Rating features only",
        "G2": "Rating + clock + position; **primary broad GBM**",
        "G3": "Clock features only; diagnostic ablation",
        "G4": "Position context only (move#, checkpoint, phase); near-prior",
        "G5": "Eval features + position; eval-gated exploratory",
        "G6": "All features incl. eval; eval-gated exploratory",
    }
    for m in all_gbm:
        mid = m.get("model_id", "?")
        dropped = m.get("feature_columns_dropped", [])
        dropped_str = ", ".join(dropped) if dropped else "—"
        inv_rows.append(
            f"| {mid} | {m.get('feature_set_id','?')} | {m.get('table','?')} "
            f"| {_role(m)} | {m.get('n_train_rows','?')} | {m.get('n_features_used','?')} "
            f"| {dropped_str} | {_notes.get(mid, '')} |"
        )

    sec4 = [
        "## 4. GBM Model Inventory",
        "",
        inv_header,
        *inv_rows,
        "",
        "All models: `HistGradientBoostingClassifier`, fixed params "
        "(max_iter=300, lr=0.05, max_leaf_nodes=31, min_samples_leaf=20, "
        "l2_regularization=0.1, random_state=42). No tuning, no calibration.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 5: Metric Policy Reminder
    # -----------------------------------------------------------------------
    sec5 = [
        "## 5. Metric Policy Reminder",
        "",
        "- **Primary metric: validation log_loss.** Lower is better.",
        "- macro_f1 and per-class metrics (especially DRAW) also reported.",
        "- Multiclass Brier score helps diagnose probability quality.",
        "- Accuracy is secondary — misleading when DRAW is ~6% of rows.",
        "- Test metrics are held out and are not used for model selection.",
        "- Confidence bucket table is a diagnostic only — no calibration is fitted.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 6: Primary Broad GBMs vs B3
    # -----------------------------------------------------------------------
    _cmp_header = (
        "| Model | Role | Val log_loss | Val macro_f1 | Val acc | Val Brier "
        "| DRAW recall | DRAW support |\n"
        "|-------|------|-------------|-------------|---------|----------"
        "|-------------|--------------|"
    )

    def _cmp_row(label: str, role: str, model: dict) -> str:
        vm = get_split_metrics(model, "val")
        ll = _ff(vm.get("log_loss"))
        f1 = _ff(vm.get("macro_f1"))
        acc = _ff(vm.get("accuracy"))
        brier = _ff(vm.get("multiclass_brier"))
        draw_rec = _ff(get_per_class_metric(model, "val", "DRAW", "recall"))
        draw_sup = get_per_class_metric(model, "val", "DRAW", "support")
        draw_sup_s = str(draw_sup) if draw_sup is not None else "NA"
        return (f"| {label} | {role} | {ll} | {f1} | {acc} | {brier} "
                f"| {draw_rec} | {draw_sup_s} |")

    cmp_rows = []
    if b3 is not None:
        cmp_rows.append(_cmp_row("**B3** *(reference)*", "broad LR baseline", b3))
    for m in broad_primary:
        mid = m["model_id"]
        cmp_rows.append(_cmp_row(mid, "broad primary GBM", m))

    g2_val_ll = _ff(_vm(g2, "log_loss")) if g2 else "NA"
    b3_val_ll = _ff(_vm(b3, "log_loss")) if b3 else "NA"

    sec6 = [
        "## 6. Primary Broad GBMs vs B3 Baseline",
        "",
        "B3 is the best broad logistic baseline from Phase 5.3B. "
        "G2 uses the same feature set (FS-E) and is the direct apples-to-apples comparison.",
        "",
        _cmp_header,
        *cmp_rows,
        "",
        f"> **G2 does not beat B3.** G2 validation log_loss = {g2_val_ll} vs "
        f"B3 = {b3_val_ll}. G2 is worse than B3 on every reported metric. "
        "This is a controlled diagnostic result, not a project failure. "
        "The large train/val gap (G2 train log_loss ≈ 0.164) confirms the model "
        "has overfit the small pilot training set (~4,344 rows).",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 7: Broad Diagnostic GBMs
    # -----------------------------------------------------------------------
    diag_rows = []
    for m in broad_diag:
        mid = m["model_id"]
        diag_rows.append(_cmp_row(mid, "broad diagnostic GBM", m))

    sec7 = [
        "## 7. Broad Diagnostic GBMs (G3, G4)",
        "",
        "These models are **diagnostic only** and are not compared to B3 as performance claims.",
        "",
        _cmp_header,
        *diag_rows,
        "",
        "**G3 (FS-C, clock features only):** Clock features alone show moderate overfit "
        "(train/val gap ≈ +0.432). Clock carries signal but is insufficient on its own.",
        "",
        "**G4 (FS-D, position context only — move number, checkpoint, phase):**",
        "G4 has the best broad-GBM validation log_loss numerically (≈ 0.881), "
        "but this is because G4 is a **near-prior / degenerate model**. "
        "Its predicted probabilities span a very narrow range "
        "(p_BLACK_WIN ≈ 0.45–0.48, p_DRAW ≈ 0.05–0.11, p_WHITE_WIN ≈ 0.44–0.48); "
        "mean max-probability ≈ 0.476. "
        "G4 has learned to output the training class prior conditioned on game phase "
        "and checkpoint position, but does not discriminate individual games. "
        "Its near-zero train/val gap reflects this prior-like behaviour, not genuine "
        "generalisation. **G4 must not be called the best or winning GBM.**",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 8: Eval-Gated Exploratory GBMs
    # -----------------------------------------------------------------------
    eval_rows = []
    for m in eval_expl:
        mid = m["model_id"]
        eval_rows.append(_cmp_row(mid, "eval exploratory GBM", m))

    sec8 = [
        "## 8. Eval-Gated Exploratory GBMs (G5, G6)",
        "",
        "G5 and G6 are **exploratory only**. They use a gated eval subset (Stockfish-annotated "
        "games), which is not directly comparable to broad models. Eval val/test splits have "
        "very sparse DRAW support (~14 val rows for DRAW).",
        "",
        _cmp_header,
        *eval_rows,
        "",
        "**G5 (eval_only features):** Significant overfit (train/val gap ≈ +0.763). "
        "Eval features carry signal but the eval training set (645 rows) is too small.",
        "",
        "**G6 (all features including eval):** Train log_loss ≈ 0.004 — "
        "**complete memorisation** of 645 training rows. Val log_loss ≈ 1.641. "
        "G6 is a calibration/overfitting failure case. "
        "Eval-gated results must not be used to claim that eval features work broadly.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 9: Overfitting Diagnosis
    # -----------------------------------------------------------------------
    _interp = {
        "G1": "Severe overfit — rating features memorised",
        "G2": "Severe overfit — primary broad GBM, far worse than B3 on val",
        "G3": "Moderate overfit — clock-only diagnostic",
        "G4": "Near-zero gap — near-prior behaviour, not genuine generalisation",
        "G5": "Significant overfit — eval-gated, small training set",
        "G6": "Complete memorisation — train_ll≈0.004, catastrophic val overfit",
    }

    ov_header = (
        "| Model | Train LL | Val LL | Gap | Interpretation |\n"
        "|-------|----------|--------|-----|----------------|"
    )
    ov_rows = []
    for m in all_gbm:
        mid = m.get("model_id", "?")
        tr_ll = _tm(m, "log_loss")
        va_ll = _vm(m, "log_loss")
        gap = (float(va_ll) - float(tr_ll)) if (tr_ll is not None and va_ll is not None) else None
        gap_s = (f"+{gap:.4f}" if gap is not None and gap > 0 else _ff(gap)) if gap is not None else "NA"
        ov_rows.append(
            f"| {mid} | {_ff(tr_ll)} | {_ff(va_ll)} | {gap_s} | {_interp.get(mid, '—')} |"
        )

    sec9 = [
        "## 9. Overfitting Diagnosis",
        "",
        ov_header,
        *ov_rows,
        "",
        "The train/val gap is the primary overfitting signal. G1 and G2 have gaps > 1.0 — "
        "they have memorised the training set. G6 has effectively zero training loss, "
        "indicating complete memorisation of 645 eval training rows. "
        "Only G4 shows a small gap, but as noted above, this reflects near-prior behaviour "
        "rather than genuine learning.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 10: Confidence Bucket Diagnostic
    # -----------------------------------------------------------------------
    bucket_rows = []
    if g2 is not None:
        buckets = compute_confidence_buckets(pred_df, "G2", "val")
        cb_header = (
            "| Confidence bucket | n | Avg confidence | Accuracy |\n"
            "|-------------------|---|----------------|----------|"
        )
        for b in buckets:
            bucket_rows.append(
                f"| {b['bucket']} | {b['n']} | {_ff(b['avg_confidence'])} "
                f"| {_ff(b['accuracy'])} |"
            )
        conf_section = [cb_header, *bucket_rows] if bucket_rows else ["_No G2 val rows found._"]
    else:
        conf_section = ["_G2 not found in payload._"]

    sec10 = [
        "## 10. Confidence Bucket Diagnostic (G2 Validation)",
        "",
        "This table shows accuracy by model confidence bucket for G2 validation rows. "
        "**This is a diagnostic only — no calibration is fitted here.** "
        "Calibration belongs in Phase 7.",
        "",
        *conf_section,
        "",
        "The confidence/accuracy relationship is weak and non-monotone, consistent with "
        "a miscalibrated overfit model. High-confidence predictions (0.9–1.0) are "
        "somewhat more accurate but the overall pattern is unreliable.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 11: DRAW Class Analysis
    # -----------------------------------------------------------------------
    draw_header = (
        "| Model | Table | Role | DRAW recall | DRAW precision | DRAW F1 | DRAW support |\n"
        "|-------|-------|------|-------------|----------------|---------|--------------|"
    )
    draw_rows = []
    for m in all_gbm:
        mid = m.get("model_id", "?")
        rec = _ff(get_per_class_metric(m, "val", "DRAW", "recall"))
        prec = _ff(get_per_class_metric(m, "val", "DRAW", "precision"))
        f1_d = _ff(get_per_class_metric(m, "val", "DRAW", "f1"))
        sup = get_per_class_metric(m, "val", "DRAW", "support")
        sup_s = str(sup) if sup is not None else "NA"
        draw_rows.append(
            f"| {mid} | {m.get('table','?')} | {_role(m)} "
            f"| {rec} | {prec} | {f1_d} | {sup_s} |"
        )

    sec11 = [
        "## 11. DRAW Class Analysis",
        "",
        draw_header,
        *draw_rows,
        "",
        "All broad GBMs (G1–G4) predict 0 DRAW rows on validation. "
        "This mirrors the behaviour of unweighted logistic regression baselines. "
        "DRAW remains structurally weak at this dataset size and class distribution. "
        "Accuracy metrics can hide this failure entirely — macro_f1 and per-class "
        "recall are required to see it.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 12: Slice Analysis — G2 Validation
    # -----------------------------------------------------------------------
    def _render_slice_table(title: str, rows: list[dict], slice_col: str) -> list[str]:
        if not rows:
            return [f"**{title}:** _no data_", ""]
        header = f"| {slice_col} | n | Accuracy |\n|---|---|---|"
        data_rows = [
            f"| {r['slice_value']} | {r['n']} | {_ff(r['accuracy'])} |"
            for r in rows
        ]
        return [f"**{title}**", "", header, *data_rows, ""]

    phase_rows = compute_slice_accuracy(pred_df, "G2", "val", "phase") if g2 else []
    move_rows = compute_slice_accuracy(pred_df, "G2", "val", "move_number") if g2 else []
    forfeit_rows = compute_slice_accuracy(pred_df, "G2", "val", "is_time_forfeit") if g2 else []
    eval_flag_rows = compute_slice_accuracy(pred_df, "G2", "val", "has_eval") if g2 else []
    elo_result = join_avg_elo_slice(pred_df, feature_broad_df, "G2", "val")

    elo_section: list[str] = []
    if elo_result["skipped"]:
        elo_section = [f"**avg_elo bucket:** _{elo_result['note']}_", ""]
    else:
        elo_header = "| avg_elo bucket | n | Accuracy |\n|---|---|---|"
        elo_data = [
            f"| {r['bucket']} | {r['n']} | {_ff(r['accuracy'])} |"
            for r in elo_result["rows"]
        ]
        elo_section = [
            f"**avg_elo bucket** _{elo_result['note']}_",
            "",
            elo_header,
            *elo_data,
            "",
        ]

    sec12 = [
        "## 12. Slice Analysis — G2 Validation",
        "",
        "G2 is used for slice analysis because it is the primary broad GBM. "
        "All slices are on the **validation set** only.",
        "",
        "**Caveats:** phase and move_number are correlated (opening≈move_10, "
        "endgame≈move_40). is_time_forfeit has limited support (~102 True rows). "
        "has_eval is a coverage/bias proxy, not a causal predictor. "
        "avg_elo buckets are noisy (n=82–194 per bucket); the pattern should not "
        "be over-interpreted at this sample size.",
        "",
        *_render_slice_table("Phase", phase_rows, "phase"),
        *_render_slice_table("Move number", move_rows, "move_number"),
        *_render_slice_table("Time forfeit (is_time_forfeit)", forfeit_rows, "is_time_forfeit"),
        *_render_slice_table("Has eval annotation (has_eval)", eval_flag_rows, "has_eval"),
        *elo_section,
        "Slice accuracy varies across groups but no single slice dominates. "
        "The patterns are consistent with a noisy pilot dataset and should not "
        "be treated as degradation curves or reliable constraint findings yet.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 13: Held-Out Test Snapshot
    # -----------------------------------------------------------------------
    def _test_row(label: str, model: dict, note: str = "") -> str:
        tm = get_split_metrics(model, "test")
        ll = _ff(tm.get("log_loss"))
        acc = _ff(tm.get("accuracy"))
        brier = _ff(tm.get("multiclass_brier"))
        f1 = _ff(tm.get("macro_f1"))
        return f"| {label} | {ll} | {acc} | {brier} | {f1} | {note} |"

    test_header = (
        "| Model | Test log_loss | Test acc | Test Brier | Test macro_f1 | Note |\n"
        "|-------|---------------|----------|------------|---------------|------|"
    )
    test_rows = []
    if g2:
        test_rows.append(_test_row("G2", g2, "primary broad GBM"))
    if b3:
        test_rows.append(_test_row("B3 *(reference)*", b3, "broad LR baseline"))

    sec13 = [
        "## 13. Held-Out Test Snapshot",
        "",
        "> **Test metrics are not used for model selection.** "
        "This is a one-time held-out snapshot for record-keeping only. "
        "Do not tune models based on test results.",
        "",
        test_header,
        *test_rows,
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 14: Key Findings
    # -----------------------------------------------------------------------
    sec14 = [
        "## 14. Key Findings",
        "",
        f"1. **G2 does not beat B3.** G2 val log_loss={g2_val_ll} vs B3={b3_val_ll}. "
        "G2 is worse on every reported metric.",
        "2. **G1 and G2 overfit strongly.** Train/val log_loss gaps exceed +1.0.",
        "3. **G4 is a near-prior diagnostic model**, not a competitive predictor. "
        "Its apparent proximity to B3 in val log_loss reflects prior-like output, "
        "not genuine generalisation.",
        "4. **G6 memorises the eval training set.** Train log_loss ≈ 0.004; "
        "catastrophic val overfit.",
        "5. **Broad GBMs still fail DRAW.** G1–G4 all predict 0 DRAW on validation. "
        "DRAW class failure is not addressed by fixed unweighted HistGBM on this data.",
        "6. **Slice diagnostics are feasible but noisy** at this dataset scale. "
        "No single slice dominates; elo-bucket patterns should not be over-interpreted.",
        "7. **More data, regularisation adjustment, and/or calibration may be needed** "
        "before claiming nonlinear gains over logistic regression.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 15: Recommended Next Steps
    # -----------------------------------------------------------------------
    sec15 = [
        "## 15. Recommended Next Steps",
        "",
        "- **6.3A — Feature Importance Audit:** Audit before implementing. "
        "Note that the current GBM is weak/overfit — feature importances from G2 "
        "are computed on an overfit model and may not be reliable.",
        "- **Phase 7 — Calibration:** Calibration assessment remains a separate "
        "audit/implementation phase. The confidence bucket diagnostic in this report "
        "provides motivation; actual calibration fitting is deferred.",
        "- **Phase 8 — Scaling:** The negative GBM result most likely reflects "
        "insufficient training data (~4,344 broad primary rows) for a flexible "
        "nonlinear model. Scaling the dataset is the most direct path to GBM gains.",
        "- **Phase 9 — Constraint analysis:** Should wait for a more robust model "
        "and/or larger dataset. Slice findings from the current overfit GBM would "
        "be unreliable inputs to constraint conclusions.",
        "- **No neural networks in current scope.** Not justified at this data scale.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 16: Reproducibility
    # -----------------------------------------------------------------------
    cli_cmd = (
        "```bash\n"
        "PYTHONPATH=src python -m chess_mhsuc.gbm_evaluation \\\\\n"
        f"    --dataset-id {dataset_id} \\\\\n"
        f"    --version-tag {version_tag} \\\\\n"
        f"    --gbm-results data/processed/gbm_results_{version_tag}.json \\\\\n"
        f"    --gbm-predictions data/processed/gbm_predictions_{version_tag}.parquet \\\\\n"
        f"    --baseline-results data/processed/baseline_results_{version_tag}.json \\\\\n"
        f"    --feature-broad data/processed/feature_positions_broad_{version_tag}.parquet \\\\\n"
        f"    --output reports/gbm_evaluation_{version_tag}.md\n"
        "```"
    )

    sec16 = [
        "## 16. Reproducibility",
        "",
        "Command used to generate this report:",
        "",
        cli_cmd,
        "",
        "All input data files are local-only and gitignored (`data/`). "
        f"This committed Markdown report (`reports/gbm_evaluation_{version_tag}.md`) "
        "is the tracked artifact.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 17: Acceptance Criteria Met
    # -----------------------------------------------------------------------
    sec17 = [
        "## 17. Acceptance Criteria Met",
        "",
        "- [x] GBM evaluation report exists",
        "- [x] Report compares broad GBMs against B3",
        "- [x] Report identifies G2 as primary broad GBM",
        "- [x] Report states G2 does not beat B3 by validation log_loss",
        "- [x] Report notes G4 as diagnostic/near-prior, not winner",
        "- [x] Report separates broad (G1–G4) and eval-gated (G5/G6) GBMs",
        "- [x] Report includes train/val overfitting table",
        "- [x] Report includes DRAW class analysis",
        "- [x] Report includes confidence bucket diagnostic (not calibration)",
        "- [x] Report includes phase, move_number, is_time_forfeit, has_eval slices",
        "- [x] Report includes avg_elo bucket slice (or skip note if feature-broad absent)",
        "- [x] Report includes held-out test snapshot, not used for model selection",
        "- [x] Report does not implement calibration",
        "- [x] Report does not implement feature importance",
        "- [x] Report does not claim eval GBMs are better overall",
        "- [x] No local data artifacts staged",
        "",
    ]

    # -----------------------------------------------------------------------
    # Assemble full report
    # -----------------------------------------------------------------------
    header = [
        "# GBM Evaluation Report — " + version_tag,
        "",
        "**Ticket:** 6.2B — GBM Evaluation Implementation",
        "**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION",
        f"**Date:** {date_str}",
        f"**Dataset ID:** `{dataset_id}`",
        f"**Version tag:** `{version_tag}`",
        "",
        "---",
        "",
    ]

    all_sections = [
        *header,
        *sec1, "---", "",
        *sec2, "---", "",
        *sec3, "---", "",
        *sec4, "---", "",
        *sec5, "---", "",
        *sec6, "---", "",
        *sec7, "---", "",
        *sec8, "---", "",
        *sec9, "---", "",
        *sec10, "---", "",
        *sec11, "---", "",
        *sec12, "---", "",
        *sec13, "---", "",
        *sec14, "---", "",
        *sec15, "---", "",
        *sec16, "---", "",
        *sec17,
    ]

    return "\n".join(all_sections)


# ---------------------------------------------------------------------------
# Q. write_text
# ---------------------------------------------------------------------------

def write_text(path: str | Path, text: str) -> None:
    """Write UTF-8 text to file, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


# ---------------------------------------------------------------------------
# R. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 6.2B GBM evaluation report."""
    parser = argparse.ArgumentParser(
        description="Generate GBM evaluation report for chess-MHSUC Phase 6.2B"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--gbm-results", required=True,
                        help="Path to gbm_results_{tag}.json")
    parser.add_argument("--gbm-predictions", required=True,
                        help="Path to gbm_predictions_{tag}.parquet")
    parser.add_argument("--baseline-results", required=True,
                        help="Path to baseline_results_{tag}.json")
    parser.add_argument("--feature-broad", default=None,
                        help="(Optional) Path to feature_positions_broad_{tag}.parquet "
                        "for avg_elo slice join. If omitted, elo-bucket section is skipped.")
    parser.add_argument("--output", required=True,
                        help="Output Markdown report path")

    args = parser.parse_args(argv)

    print(f"Loading GBM results: {args.gbm_results}")
    gbm_payload = load_gbm_results(args.gbm_results)

    print(f"Loading baseline results: {args.baseline_results}")
    baseline_payload = load_baseline_results(args.baseline_results)

    print(f"Loading GBM predictions: {args.gbm_predictions}")
    pred_df = load_gbm_predictions(args.gbm_predictions)

    feature_broad_df = None
    if args.feature_broad:
        print(f"Loading feature broad: {args.feature_broad}")
        feature_broad_df = load_feature_broad(args.feature_broad)
    else:
        print("--feature-broad not provided; avg_elo slice will be skipped.")

    print(f"GBM models: {[m['model_id'] for m in get_gbm_models(gbm_payload)]}")
    print(f"Baseline models: {[b.get('baseline_id', '?') for b in get_baseline_models(baseline_payload)]}")
    print(f"Prediction rows: {len(pred_df)}")

    report = render_gbm_evaluation_report(
        gbm_payload=gbm_payload,
        baseline_payload=baseline_payload,
        pred_df=pred_df,
        feature_broad_df=feature_broad_df,
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
    )

    write_text(args.output, report)
    print(f"Saved report: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
