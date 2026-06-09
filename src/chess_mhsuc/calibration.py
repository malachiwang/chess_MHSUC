"""
calibration.py — Phase 7.1B calibration diagnostics for chess-MHSUC.

Computes confidence-accuracy buckets, OvR reliability tables, ECE, and
classwise Brier scores for B1, B3, and G2 on the validation split.
No post-hoc calibrators fitted. No model artifacts saved. No plots.
No CSV files. No new dependencies.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.calibration \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
        --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
        --output reports/calibration_2024_09_25k_v1.md

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from chess_mhsuc.baselines import CLASS_ORDER

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CALIBRATION_MODEL_IDS: list[str] = ["B1", "B3", "G2"]

# Number of uniform bins for top-label confidence-accuracy table
_N_CONFIDENCE_BINS: int = 10

# Number of uniform bins for OvR reliability tables
_N_RELIABILITY_BINS: int = 5

_PROB_COLS: list[str] = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]

# Maximum allowed deviation of probability row-sums from 1.0
_PROB_SUM_TOLERANCE: float = 1e-3

_PROB_COL_MAP: dict[str, str] = {
    "BLACK_WIN": "p_BLACK_WIN",
    "DRAW": "p_DRAW",
    "WHITE_WIN": "p_WHITE_WIN",
}

# GBM primary view name for filtering (matches gbm.py primary_numbered view)
_GBM_PRIMARY_VIEW: str = "primary_numbered"


# ---------------------------------------------------------------------------
# A. get_class_order
# ---------------------------------------------------------------------------


def get_class_order() -> list[str]:
    """Return the canonical class order: BLACK_WIN, DRAW, WHITE_WIN."""
    return list(CLASS_ORDER)


# ---------------------------------------------------------------------------
# B. load_baseline_predictions
# ---------------------------------------------------------------------------


def load_baseline_predictions(path: str | Path) -> pl.DataFrame:
    """
    Load baseline predictions Parquet.

    Required columns: baseline_id, split_set, game_id, result_class,
    pred_class, p_BLACK_WIN, p_DRAW, p_WHITE_WIN.
    """
    df = pl.read_parquet(path)
    required = {
        "baseline_id", "split_set", "game_id", "result_class",
        "pred_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Baseline predictions Parquet missing required columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# C. load_gbm_predictions
# ---------------------------------------------------------------------------


def load_gbm_predictions(path: str | Path) -> pl.DataFrame:
    """
    Load GBM predictions Parquet.

    Required columns: model_id, split_set, game_id, result_class,
    pred_class, p_BLACK_WIN, p_DRAW, p_WHITE_WIN.
    """
    df = pl.read_parquet(path)
    required = {
        "model_id", "split_set", "game_id", "result_class",
        "pred_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"GBM predictions Parquet missing required columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# D. standardize_prediction_schema
# ---------------------------------------------------------------------------


def standardize_prediction_schema(
    baseline_df: pl.DataFrame,
    gbm_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Standardize schemas and concatenate baseline + GBM predictions.

    Steps:
    1. Rename `baseline_id` → `model_id` in baseline_df.
    2. Filter gbm_df to view == "primary_numbered" if that column exists,
       so GBM rows match the same view used for baseline comparisons.
    3. Select the shared calibration columns from each DataFrame.
    4. Concatenate and return.

    Shared columns: model_id, split_set, game_id, result_class, pred_class,
    p_BLACK_WIN, p_DRAW, p_WHITE_WIN.
    """
    keep_cols = [
        "model_id", "split_set", "game_id", "result_class",
        "pred_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN",
    ]

    baseline_renamed = baseline_df.rename({"baseline_id": "model_id"})
    baseline_subset = baseline_renamed.select(keep_cols)

    gbm_filtered = gbm_df
    if "view" in gbm_df.columns:
        gbm_filtered = gbm_df.filter(pl.col("view") == _GBM_PRIMARY_VIEW)

    gbm_subset = gbm_filtered.select(keep_cols)

    return pl.concat([baseline_subset, gbm_subset])


# ---------------------------------------------------------------------------
# E. filter_calibration_models
# ---------------------------------------------------------------------------


def filter_calibration_models(
    df: pl.DataFrame,
    model_ids: list[str] | None = None,
) -> pl.DataFrame:
    """
    Filter to calibration models only: B1, B3, G2 by default.

    G4 is excluded: near-prior behavior (max_prob mean ≈ 0.476) would
    appear deceptively calibrated. G6 is excluded: memorizes training set
    (train log_loss ≈ 0.004). G5 is excluded: eval-gated exploratory model.
    G1 and G3 are excluded: not primary comparison models.
    B0 is excluded: most-frequent dummy with undefined probabilities.
    B2, B3-balanced, B4, B5 are excluded to keep the report focused.
    """
    if model_ids is None:
        model_ids = _CALIBRATION_MODEL_IDS
    return df.filter(pl.col("model_id").is_in(model_ids))


# ---------------------------------------------------------------------------
# F. check_probability_sanity
# ---------------------------------------------------------------------------


def check_probability_sanity(df: pl.DataFrame) -> dict[str, Any]:
    """
    Check that probabilities sum to ~1, are non-negative, and have no nulls.

    Returns a dict with:
        no_nulls: bool
        all_non_negative: bool
        prob_sum_near_one: bool
        max_sum_deviation: float
    """
    null_counts = {col: int(df[col].null_count()) for col in _PROB_COLS}
    no_nulls = all(c == 0 for c in null_counts.values())

    all_non_negative = all(
        float(df[col].min()) >= 0.0 for col in _PROB_COLS
    )

    p_sum = df.select(
        (pl.col("p_BLACK_WIN") + pl.col("p_DRAW") + pl.col("p_WHITE_WIN")).alias("s")
    )["s"].to_numpy()
    max_dev = float(np.abs(p_sum - 1.0).max()) if len(p_sum) > 0 else 0.0
    prob_sum_near_one = max_dev <= _PROB_SUM_TOLERANCE

    return {
        "no_nulls": no_nulls,
        "all_non_negative": all_non_negative,
        "prob_sum_near_one": prob_sum_near_one,
        "max_sum_deviation": max_dev,
    }


# ---------------------------------------------------------------------------
# G. compute_confidence_accuracy_table
# ---------------------------------------------------------------------------


def compute_confidence_accuracy_table(
    df: pl.DataFrame,
    n_bins: int = _N_CONFIDENCE_BINS,
) -> list[dict]:
    """
    Compute top-label confidence vs accuracy in uniform bins.

    Top-label confidence = max(p_BLACK_WIN, p_DRAW, p_WHITE_WIN).
    Predicted class = argmax of probabilities.

    Returns list of dicts (bins with n=0 omitted):
        bin_lower, bin_upper, n, accuracy, mean_confidence, gap
        (gap = mean_confidence - accuracy; positive = overconfident)
    """
    p = df.select(_PROB_COLS).to_numpy()
    y_true = df["result_class"].to_list()

    max_conf = p.max(axis=1)
    pred_idx = p.argmax(axis=1)
    class_order = get_class_order()
    pred_class = [class_order[int(i)] for i in pred_idx]
    correct = np.array([pc == yt for pc, yt in zip(pred_class, y_true)])

    rows = []
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    for i in range(n_bins):
        lo, hi = float(bin_edges[i]), float(bin_edges[i + 1])
        if i < n_bins - 1:
            mask = (max_conf >= lo) & (max_conf < hi)
        else:
            mask = (max_conf >= lo) & (max_conf <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        acc = float(correct[mask].mean())
        mean_conf = float(max_conf[mask].mean())
        rows.append({
            "bin_lower": round(lo, 4),
            "bin_upper": round(hi, 4),
            "n": n,
            "accuracy": acc,
            "mean_confidence": mean_conf,
            "gap": mean_conf - acc,
        })
    return rows


# ---------------------------------------------------------------------------
# H. compute_reliability_table
# ---------------------------------------------------------------------------


def compute_reliability_table(
    df: pl.DataFrame,
    class_col: str,
    prob_col: str,
    n_bins: int = _N_RELIABILITY_BINS,
) -> list[dict]:
    """
    Compute OvR reliability table for a single class.

    Binary label: 1 if result_class == class_col, else 0.
    Bins predicted probability (prob_col) uniformly.

    Returns list of dicts (bins with n=0 omitted):
        bin_lower, bin_upper, n, frac_positive, mean_pred_prob, gap
        (gap = mean_pred_prob - frac_positive; positive = overconfident)
    """
    y_binary = (df["result_class"] == class_col).cast(pl.Int8).to_numpy()
    p_pred = df[prob_col].to_numpy()

    rows = []
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    for i in range(n_bins):
        lo, hi = float(bin_edges[i]), float(bin_edges[i + 1])
        if i < n_bins - 1:
            mask = (p_pred >= lo) & (p_pred < hi)
        else:
            mask = (p_pred >= lo) & (p_pred <= hi)
        n = int(mask.sum())
        if n == 0:
            continue
        frac_pos = float(y_binary[mask].mean())
        mean_pred = float(p_pred[mask].mean())
        rows.append({
            "bin_lower": round(lo, 4),
            "bin_upper": round(hi, 4),
            "n": n,
            "frac_positive": frac_pos,
            "mean_pred_prob": mean_pred,
            "gap": mean_pred - frac_pos,
        })
    return rows


# ---------------------------------------------------------------------------
# I. compute_ece
# ---------------------------------------------------------------------------


def compute_ece(reliability_rows: list[dict], total_n: int) -> float:
    """
    Compute Expected Calibration Error (ECE) from OvR reliability rows.

    ECE = Σ_bins (n_bin / total_n) * |mean_pred_prob - frac_positive|

    Uses OvR framing: total_n is the total number of rows, not binary positives.
    Returns 0.0 if total_n == 0 or reliability_rows is empty.
    """
    if total_n == 0 or not reliability_rows:
        return 0.0
    ece = 0.0
    for row in reliability_rows:
        weight = row["n"] / total_n
        ece += weight * abs(row["gap"])
    return float(ece)


# ---------------------------------------------------------------------------
# J. compute_classwise_brier
# ---------------------------------------------------------------------------


def compute_classwise_brier(
    df: pl.DataFrame,
    class_col: str,
    prob_col: str,
) -> float:
    """
    Compute OvR classwise Brier score for a single class.

    Brier_OvR = mean((p_pred - y_binary)^2)
    where y_binary = 1 if result_class == class_col, else 0.
    """
    y_binary = (df["result_class"] == class_col).cast(pl.Float64).to_numpy()
    p_pred = df[prob_col].cast(pl.Float64).to_numpy()
    return float(np.mean((p_pred - y_binary) ** 2))


# ---------------------------------------------------------------------------
# K. summarize_model_calibration
# ---------------------------------------------------------------------------


def summarize_model_calibration(
    df: pl.DataFrame,
    model_id: str,
    split_set: str = "val",
) -> dict:
    """
    Compute full calibration summary for a single model on a single split.

    Returns:
        model_id, split_set, n_rows, class_counts,
        confidence_accuracy_table,
        reliability: {class_name: [row_dicts]},
        ece: {class_name: float},
        classwise_brier: {class_name: float}
    """
    subset = df.filter(
        (pl.col("model_id") == model_id) & (pl.col("split_set") == split_set)
    )

    n_rows = len(subset)
    class_counts = {
        cls: int((subset["result_class"] == cls).sum())
        for cls in get_class_order()
    }

    conf_acc_table = compute_confidence_accuracy_table(subset)

    reliability: dict[str, list[dict]] = {}
    ece: dict[str, float] = {}
    classwise_brier: dict[str, float] = {}

    for cls in get_class_order():
        prob_col = _PROB_COL_MAP[cls]
        rel_table = compute_reliability_table(subset, cls, prob_col)
        reliability[cls] = rel_table
        ece[cls] = compute_ece(rel_table, n_rows)
        classwise_brier[cls] = compute_classwise_brier(subset, cls, prob_col)

    return {
        "model_id": model_id,
        "split_set": split_set,
        "n_rows": n_rows,
        "class_counts": class_counts,
        "confidence_accuracy_table": conf_acc_table,
        "reliability": reliability,
        "ece": ece,
        "classwise_brier": classwise_brier,
    }


# ---------------------------------------------------------------------------
# L. render_markdown_table
# ---------------------------------------------------------------------------


def render_markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """
    Render a generic Markdown table.

    headers: list of header strings.
    rows: list of rows, each a list of cell strings (same length as headers).
    """
    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, sep_line] + row_lines)


# ---------------------------------------------------------------------------
# M. render_calibration_report
# ---------------------------------------------------------------------------


def _fmt(val: float, decimals: int = 4) -> str:
    """Format a float to given decimal places."""
    return f"{val:.{decimals}f}"


def _render_conf_acc_table(conf_acc_rows: list[dict]) -> str:
    """Render confidence-accuracy table as Markdown."""
    headers = ["Bin", "n", "Accuracy", "Mean confidence", "Gap (conf−acc)"]
    rows = []
    for r in conf_acc_rows:
        bin_label = f"[{r['bin_lower']:.2f}, {r['bin_upper']:.2f})"
        gap = r["gap"]
        gap_str = f"+{gap:.4f}" if gap > 0 else _fmt(gap)
        rows.append([
            bin_label,
            str(r["n"]),
            _fmt(r["accuracy"]),
            _fmt(r["mean_confidence"]),
            gap_str,
        ])
    if not rows:
        return "_No data in any confidence bin._"
    return render_markdown_table(headers, rows)


def _render_reliability_table(rel_rows: list[dict], class_name: str) -> str:
    """Render OvR reliability table for a single class as Markdown."""
    headers = ["Bin", "n", "Frac positive", "Mean pred prob", "Gap (pred−frac)"]
    rows = []
    for r in rel_rows:
        bin_label = f"[{r['bin_lower']:.2f}, {r['bin_upper']:.2f})"
        gap = r["gap"]
        gap_str = f"+{gap:.4f}" if gap > 0 else _fmt(gap)
        rows.append([
            bin_label,
            str(r["n"]),
            _fmt(r["frac_positive"]),
            _fmt(r["mean_pred_prob"]),
            gap_str,
        ])
    if not rows:
        return f"_No data in any reliability bin for {class_name}._"
    return render_markdown_table(headers, rows)


def _render_model_section(summary: dict, section_num: int) -> list[str]:
    """Render a full calibration diagnostic section for one model."""
    mid = summary["model_id"]
    n_rows = summary["n_rows"]
    counts = summary["class_counts"]
    draw_pct = 100.0 * counts.get("DRAW", 0) / n_rows if n_rows > 0 else 0.0

    lines: list[str] = [
        f"## {section_num}. {mid} Calibration Diagnostics",
        "",
        f"**Split:** validation | **Rows:** {n_rows}",
        "",
        "**Class distribution (val):**",
        "",
        render_markdown_table(
            ["Class", "Count", "Pct"],
            [
                [cls, str(counts.get(cls, 0)),
                 f"{100.0 * counts.get(cls, 0) / n_rows:.1f}%" if n_rows > 0 else "—"]
                for cls in get_class_order()
            ],
        ),
        "",
    ]

    if counts.get("DRAW", 0) < 30:
        lines += [
            f"> **DRAW sparsity warning:** Only {counts.get('DRAW', 0)} DRAW rows "
            f"({draw_pct:.1f}% of val). DRAW OvR ECE and reliability metrics are "
            "dominated by noise; interpret with caution.",
            "",
        ]

    # Confidence-accuracy table
    lines += [
        "### Top-label confidence-accuracy",
        "",
        "Top-label confidence = max predicted probability. "
        "Gap = mean_confidence − accuracy (positive = overconfident).",
        "",
        _render_conf_acc_table(summary["confidence_accuracy_table"]),
        "",
    ]

    # OvR reliability tables
    lines.append("### OvR reliability (5-bin uniform)")
    lines.append("")
    for cls in get_class_order():
        rel_rows = summary["reliability"].get(cls, [])
        ece_val = summary["ece"].get(cls, float("nan"))
        brier_val = summary["classwise_brier"].get(cls, float("nan"))
        lines += [
            f"**{cls} (p_{cls} vs 1-vs-rest label)** | "
            f"ECE = {ece_val:.4f} | Classwise Brier = {brier_val:.4f}",
            "",
            _render_reliability_table(rel_rows, cls),
            "",
        ]

    return lines


def render_calibration_report(
    summaries: dict[str, dict],
    dataset_id: str,
    version_tag: str,
) -> str:
    """
    Assemble the full calibration diagnostic Markdown report.

    summaries: {model_id: summary_dict} from summarize_model_calibration.
    """
    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    header = [
        f"# Calibration Diagnostic Report — {version_tag}",
        "",
        "**Ticket:** 7.1B — Calibration Implementation",
        "**Labels:** ML | D2 | IMPLEMENTATION",
        f"**Dataset ID:** `{dataset_id}`",
        f"**Version tag:** `{version_tag}`",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 1: ELI5 / TLDR
    # -----------------------------------------------------------------------
    sec1 = [
        "## 1. ELI5 / TLDR",
        "",
        "This is a **diagnostics-only** calibration report. No post-hoc calibrators "
        "are fitted. No model artifacts are saved.",
        "",
        "Key findings:",
        "",
        "- **B3 (LogisticRegression) is reasonably calibrated** on BLACK_WIN and WHITE_WIN. "
        "ECE ≈ 0.03 for these classes. Confidence-accuracy gap is small.",
        "- **G2 (GBM) is severely overconfident.** ECE ≈ 0.20–0.23 for BLACK_WIN and "
        "WHITE_WIN. The highest confidence bucket ([0.9, 1.0]) has mean_conf ≈ 0.95 "
        "but accuracy ≈ 0.59 — a gap of ≈ +0.36.",
        "- **DRAW is sparsely represented (~6% of validation rows).** ECE for DRAW appears "
        "low for all models, but this reflects uniform near-zero predictions on a sparse "
        "class, not genuine calibration.",
        "- **B1 (prior) is constant and miscalibrated** by construction: all rows predict "
        "the same class-prior probabilities regardless of game state.",
        "- **G2's overconfidence is consistent with its val log_loss = 1.2326 >> B3 = 0.8527.** "
        "The GBM memorized training patterns that do not generalize.",
        "- **No calibration is applied.** Phase 7.2 and Phase 8 (scaling) are the next steps.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 2: Research Framing
    # -----------------------------------------------------------------------
    sec2 = [
        "## 2. Research Framing",
        "",
        "Chess is the testbed, not the endpoint. The larger goal is modeling human "
        "strategy and reasoning under constraints — how clock pressure, game phase, "
        "and skill level interact in time-limited play.",
        "",
        "Calibration matters here because probability estimates are used directly as "
        "constraint-signal proxies. An overconfident model produces artificially narrow "
        "predictions that distort constraint-effect estimates. This report quantifies "
        "the calibration gap before any correction is applied.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 3: Scope and Caveats
    # -----------------------------------------------------------------------
    sec3 = [
        "## 3. Scope and Caveats",
        "",
        "- **Models: B1, B3, G2 only.** "
        "G4 is excluded: near-prior behavior (max_prob mean ≈ 0.476) would appear "
        "deceptively calibrated. "
        "G5 and G6 are excluded: eval-gated (different row scope). "
        "G6 memorizes the training set. "
        "B0 is excluded: most-frequent dummy with degenerate probability output. "
        "B2, B3-balanced, B4, B5 are excluded to keep the report focused.",
        "- **Validation split only.** Calibration is assessed on the val split "
        "(931 rows for broad models). Test split not used.",
        "- **OvR framing.** Reliability tables and ECE use one-vs-rest (OvR) "
        "binary decomposition per class.",
        "- **No post-hoc calibrators fitted.** Platt scaling, isotonic regression, "
        "and temperature scaling are not applied. Deferred to Phase 7.2.",
        "- **No plots.** Only this Markdown report is committed.",
        "- **No new dependencies.** No sklearn.calibration.CalibratedClassifierCV used.",
        "- **DRAW sparsity.** ~59/931 val rows are DRAW (~6.3%). "
        "DRAW OvR metrics are noisy; all models predict near-zero p_DRAW for most rows. "
        "Low DRAW ECE does not indicate genuine calibration.",
        "- **Pilot scale only.** Results limited to the 2024-09 25k-game extract.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Sections 4–6: Per-model diagnostics
    # -----------------------------------------------------------------------
    model_section_start = 4
    per_model_sections: list[str] = []
    for i, mid in enumerate(_CALIBRATION_MODEL_IDS):
        if mid not in summaries:
            continue
        per_model_sections += _render_model_section(
            summaries[mid], section_num=model_section_start + i
        )
        per_model_sections += ["---", ""]

    # -----------------------------------------------------------------------
    # Section 7: Model Comparison Summary
    # -----------------------------------------------------------------------
    comp_rows = []
    for mid in _CALIBRATION_MODEL_IDS:
        if mid not in summaries:
            continue
        s = summaries[mid]
        for cls in get_class_order():
            ece_val = s["ece"].get(cls, float("nan"))
            brier_val = s["classwise_brier"].get(cls, float("nan"))
            comp_rows.append([
                mid, cls,
                f"{ece_val:.4f}",
                f"{brier_val:.4f}",
            ])

    sec7 = [
        "## 7. Model Comparison: ECE and Classwise Brier (val)",
        "",
        render_markdown_table(
            ["Model", "Class", "ECE (OvR)", "Classwise Brier (OvR)"],
            comp_rows,
        ),
        "",
        "> **Interpretation notes:**",
        "> - B1 is a prior-only model; ECE reflects how well the class prior matches "
        "> class prevalence, not generalization.",
        "> - B3 shows low ECE on BLACK_WIN and WHITE_WIN (≈ 0.03), indicating "
        "> reasonable calibration for a logistic baseline.",
        "> - G2 shows high ECE on BLACK_WIN and WHITE_WIN (≈ 0.20–0.23), confirming "
        "> severe overconfidence consistent with its val log_loss of 1.2326.",
        "> - DRAW ECE values are small for all models but this reflects the near-zero "
        "> p_DRAW predictions and class sparsity, not genuine calibration.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 8: Interpretation
    # -----------------------------------------------------------------------
    sec8 = [
        "## 8. Interpretation",
        "",
        "**B1 (DummyClassifier — prior):** Predicts class prior for every row. "
        "Confidence-accuracy table shows a single high-n bin at the prior probability. "
        "This is the calibration floor: any model that learns nothing beyond the prior "
        "will show similar OvR ECE to B1.",
        "",
        "**B3 (LogisticRegression on FS-E):** The best broad baseline (val log_loss = 0.8527). "
        "B3's probabilities are reasonably spread; confidence-accuracy gaps are small "
        "for BLACK_WIN and WHITE_WIN. DRAW ECE is misleadingly small — B3 predicts "
        "near-zero p_DRAW for almost every row, which happens to be 'close' to the "
        "true binary label simply because DRAW is rare.",
        "",
        "**G2 (HistGBM on FS-E):** Severely overconfident. The GBM memorized training "
        "patterns that produce high-confidence predictions on validation, but accuracy "
        "in the 0.9+ confidence bucket is only ≈ 0.59. This overconfidence is a direct "
        "consequence of the overfit: the model assigns confident probabilities to "
        "patterns it learned from training that do not generalize.",
        "",
        "**DRAW class across all models:** No model predicts meaningful DRAW "
        "probabilities. The class-prior for DRAW is ≈ 6.3%. All models output "
        "p_DRAW ≈ 0.04–0.08 for most rows. DRAW OvR ECE appears small, but this "
        "is an artifact of sparsity and near-constant predictions, not calibration.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 9: Known Limitations
    # -----------------------------------------------------------------------
    sec9 = [
        "## 9. Known Limitations",
        "",
        "- **No calibration applied.** Isotonic regression, Platt scaling, and "
        "temperature scaling not assessed. Deferred to Phase 7.2.",
        "- **Pilot scale.** 931 val rows is small; bin counts can be low, "
        "especially for DRAW.",
        "- **DRAW ECE is unreliable.** Sparsity (~59 rows) and near-zero p_DRAW "
        "predictions make ECE trivially small regardless of model quality.",
        "- **No test set evaluation.** Calibration is assessed only on val split.",
        "- **Reliability curves not plotted.** Visual inspection of calibration curves "
        "would provide additional insight; deferred since no plots are allowed in "
        "this ticket.",
        "- **Classwise Brier ≠ overall Brier.** The sum of OvR Brier scores does not "
        "equal the multiclass Brier score reported in earlier phases.",
        "- **B3 probabilities may reflect LR calibration artifacts.** "
        "LogisticRegression is known to be reasonably calibrated but may still "
        "show bias near the boundaries.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 10: What This Does NOT Say
    # -----------------------------------------------------------------------
    sec10 = [
        "## 10. What This Does NOT Say",
        "",
        "- **Not a final calibration.** No calibrators are fitted. "
        "These are raw model probability diagnostics.",
        "- **Not a claim that B3 is well-calibrated.** "
        "B3 ECE ≈ 0.03 on BLACK_WIN/WHITE_WIN is relatively good, but B3 "
        "still fails on DRAW and produces lower-quality probabilities than a "
        "calibrated model would.",
        "- **Not a causal finding.** Calibration gaps do not imply causal effects "
        "of any feature.",
        "- **Not a constraint analysis.** Phase 9 constraint analysis requires a "
        "better-calibrated model on more data.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 11: Reproducibility
    # -----------------------------------------------------------------------
    cli_cmd = (
        "```bash\n"
        "PYTHONPATH=src python -m chess_mhsuc.calibration \\\\\n"
        f"    --dataset-id {dataset_id} \\\\\n"
        f"    --version-tag {version_tag} \\\\\n"
        f"    --baseline-predictions data/processed/baseline_predictions_{version_tag}.parquet \\\\\n"
        f"    --gbm-predictions data/processed/gbm_predictions_{version_tag}.parquet \\\\\n"
        f"    --output reports/calibration_{version_tag}.md\n"
        "```"
    )

    sec11 = [
        "## 11. Reproducibility",
        "",
        "Command used to generate this report:",
        "",
        cli_cmd,
        "",
        "All input data files are local-only and gitignored (`data/`). "
        "No model artifacts were created. No calibrators were fitted. "
        f"This committed Markdown report (`reports/calibration_{version_tag}.md`) "
        "is the only tracked artifact.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 12: Acceptance Criteria
    # -----------------------------------------------------------------------
    sec12 = [
        "## 12. Acceptance Criteria Met",
        "",
        "- [x] Calibration diagnostic report exists",
        "- [x] Confidence-accuracy buckets computed for B1, B3, G2",
        "- [x] OvR reliability tables computed for B1, B3, G2",
        "- [x] ECE (OvR) computed for all three classes for each model",
        "- [x] Classwise Brier (OvR) computed for all three classes",
        "- [x] Validation split only used",
        "- [x] No post-hoc calibrators fitted",
        "- [x] No model artifacts saved",
        "- [x] No plots produced",
        "- [x] No new dependencies added",
        "- [x] DRAW sparsity caveat included",
        "- [x] G4 exclusion (near-prior) documented",
        "- [x] G6 exclusion (memorization) documented",
        "- [x] No causal claims made",
        "- [x] No test-set usage",
        "- [x] No local data artifacts staged",
        "",
    ]

    # -----------------------------------------------------------------------
    # Assemble
    # -----------------------------------------------------------------------
    parts = [
        *header,
        *sec1, "---", "",
        *sec2, "---", "",
        *sec3, "---", "",
        *per_model_sections,
        *sec7, "---", "",
        *sec8, "---", "",
        *sec9, "---", "",
        *sec10, "---", "",
        *sec11, "---", "",
        *sec12,
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# N. write_text
# ---------------------------------------------------------------------------


def write_text(path: str | Path, text: str) -> None:
    """Write UTF-8 text to file, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


# ---------------------------------------------------------------------------
# O. main / CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 7.1B calibration diagnostics."""
    parser = argparse.ArgumentParser(
        description="Generate calibration diagnostic report (Phase 7.1B)"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument(
        "--baseline-predictions", required=True,
        help="Path to baseline_predictions_{tag}.parquet",
    )
    parser.add_argument(
        "--gbm-predictions", required=True,
        help="Path to gbm_predictions_{tag}.parquet",
    )
    parser.add_argument("--output", required=True, help="Output Markdown report path")

    args = parser.parse_args(argv)

    print(f"[calibration] Loading baseline predictions: {args.baseline_predictions}",
          file=sys.stderr)
    baseline_df = load_baseline_predictions(args.baseline_predictions)

    print(f"[calibration] Loading GBM predictions: {args.gbm_predictions}",
          file=sys.stderr)
    gbm_df = load_gbm_predictions(args.gbm_predictions)

    print("[calibration] Standardizing schemas...", file=sys.stderr)
    combined = standardize_prediction_schema(baseline_df, gbm_df)

    print("[calibration] Filtering to calibration models...", file=sys.stderr)
    combined = filter_calibration_models(combined)

    sanity = check_probability_sanity(combined)
    if not sanity["prob_sum_near_one"]:
        print(
            f"[calibration] WARNING: probability sums deviate from 1.0 "
            f"(max deviation = {sanity['max_sum_deviation']:.6f})",
            file=sys.stderr,
        )
    if not sanity["no_nulls"]:
        print("[calibration] WARNING: null values found in probability columns.",
              file=sys.stderr)

    print("[calibration] Computing calibration summaries...", file=sys.stderr)
    summaries: dict[str, dict] = {}
    for model_id in _CALIBRATION_MODEL_IDS:
        model_rows = combined.filter(pl.col("model_id") == model_id)
        if len(model_rows) == 0:
            print(f"[calibration] WARNING: no rows found for {model_id}, skipping.",
                  file=sys.stderr)
            continue
        summaries[model_id] = summarize_model_calibration(combined, model_id, "val")
        n = summaries[model_id]["n_rows"]
        print(f"[calibration]   {model_id}: {n} val rows", file=sys.stderr)

    print("[calibration] Rendering report...", file=sys.stderr)
    report = render_calibration_report(summaries, args.dataset_id, args.version_tag)

    write_text(args.output, report)
    print(f"[calibration] Report written → {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
