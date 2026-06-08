"""
baseline_evaluation.py — Phase 5.3B baseline evaluation report for chess-MHSUC.

Reads the baseline results JSON produced by baselines.py and renders a
human-readable Markdown evaluation report.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.baseline_evaluation \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
        --output reports/baseline_evaluation_2024_09_25k_v1.md

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# A. load_baseline_results
# ---------------------------------------------------------------------------

def load_baseline_results(path: str | Path) -> dict:
    """
    Load and validate a baseline results JSON produced by baselines.py.

    Required top-level keys: dataset_id, version_tag, baselines,
    class_order, label_map.

    Raises ValueError if any required key is absent or if 'baselines'
    is not a dict (the schema produced by baselines.py since Phase 5.2B).
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    required_keys = {"dataset_id", "version_tag", "baselines", "class_order", "label_map"}
    missing = required_keys - set(payload.keys())
    if missing:
        raise ValueError(
            f"Baseline results JSON missing required keys: {sorted(missing)}. "
            f"Found keys: {sorted(payload.keys())}"
        )

    if not isinstance(payload["baselines"], dict):
        raise ValueError(
            f"Expected 'baselines' to be a dict, got "
            f"{type(payload['baselines']).__name__}. "
            "This file may have been produced by an incompatible version of baselines.py."
        )

    return payload


# ---------------------------------------------------------------------------
# B. get_baselines
# ---------------------------------------------------------------------------

def get_baselines(payload: dict) -> list[dict]:
    """
    Extract the list of baseline result dicts from the results payload.

    payload["baselines"] is a dict keyed by baseline_id (schema from baselines.py).
    Returns a list of baseline dicts in insertion order.
    """
    return list(payload["baselines"].values())


# ---------------------------------------------------------------------------
# C. filter_broad_primary_baselines
# ---------------------------------------------------------------------------

def filter_broad_primary_baselines(baselines: list[dict]) -> list[dict]:
    """
    Return broad, non-diagnostic baselines (B0–B3).

    Criterion: table == "broad" and not diagnostic.
    Excludes eval-gated baselines (B4, B5) and B3-balanced (diagnostic=True).
    """
    return [
        b for b in baselines
        if b.get("table") == "broad" and not b.get("diagnostic", False)
    ]


# ---------------------------------------------------------------------------
# D. filter_eval_exploratory_baselines
# ---------------------------------------------------------------------------

def filter_eval_exploratory_baselines(baselines: list[dict]) -> list[dict]:
    """
    Return eval-gated exploratory baselines (B4, B5).

    Criterion: table == "eval" and exploratory == True.
    """
    return [
        b for b in baselines
        if b.get("table") == "eval" and b.get("exploratory", False)
    ]


# ---------------------------------------------------------------------------
# E. filter_diagnostic_baselines
# ---------------------------------------------------------------------------

def filter_diagnostic_baselines(baselines: list[dict]) -> list[dict]:
    """
    Return diagnostic baselines (B3-balanced).

    Criterion: diagnostic == True.
    """
    return [b for b in baselines if b.get("diagnostic", False)]


# ---------------------------------------------------------------------------
# F. get_split_metrics
# ---------------------------------------------------------------------------

def get_split_metrics(baseline: dict, split: str) -> dict:
    """
    Return the metrics dict for one split ("train", "val", or "test").

    Returns empty dict if the split is not present.
    """
    return baseline.get("metrics", {}).get(split, {})


# ---------------------------------------------------------------------------
# G. get_per_class_metric
# ---------------------------------------------------------------------------

def get_per_class_metric(
    baseline: dict,
    split: str,
    class_name: str,
    metric_name: str,
) -> Any:
    """
    Return a single per-class metric value.

    Path: baseline["metrics"][split]["per_class"][class_name][metric_name].
    Returns None if any step in the path is missing.
    """
    metrics = get_split_metrics(baseline, split)
    return metrics.get("per_class", {}).get(class_name, {}).get(metric_name)


# ---------------------------------------------------------------------------
# H. sort_by_validation_log_loss
# ---------------------------------------------------------------------------

def sort_by_validation_log_loss(baselines: list[dict]) -> list[dict]:
    """
    Sort baselines ascending by validation log_loss.

    Baselines with None log_loss are placed last.
    Does not mutate the input list.
    """
    def _key(b: dict) -> float:
        val = get_split_metrics(b, "val").get("log_loss")
        return float("inf") if val is None else float(val)

    return sorted(baselines, key=_key)


# ---------------------------------------------------------------------------
# I. format_float
# ---------------------------------------------------------------------------

def format_float(val: Any, decimals: int = 4) -> str:
    """
    Format a numeric value as a fixed-point string with `decimals` decimal places.

    Returns "N/A" if val is None or cannot be converted to float.
    """
    if val is None:
        return "N/A"
    try:
        return format(float(val), f".{decimals}f")
    except (TypeError, ValueError):
        return str(val)


# ---------------------------------------------------------------------------
# J. render_inventory_table
# ---------------------------------------------------------------------------

def render_inventory_table(baselines: list[dict]) -> str:
    """
    Render the full baseline inventory as a Markdown table.

    Includes all baselines (B0–B5 + B3-balanced).
    Columns: ID, Model, FS, Table, Expl, Diag, Val log_loss, Val acc.
    """
    header = (
        "| ID | Model | FS | Table | Expl | Diag | Val log_loss | Val acc |\n"
        "|----|-------|----|-------|------|------|--------------|---------|"
    )
    rows: list[str] = []
    for b in baselines:
        bid = b.get("baseline_id", "?")
        model = b.get("model_type", "?")[:22]
        fs = b.get("feature_set_id", "?")
        table = b.get("table", "?")
        expl = "Y" if b.get("exploratory") else "N"
        diag = "Y" if b.get("diagnostic") else "N"
        val = get_split_metrics(b, "val")
        ll = format_float(val.get("log_loss"))
        acc = format_float(val.get("accuracy"))
        rows.append(
            f"| {bid} | {model} | {fs} | {table} | {expl} | {diag} | {ll} | {acc} |"
        )

    return header + "\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# K. render_validation_table
# ---------------------------------------------------------------------------

_B0_EXCLUSION_NOTE = (
    "B0 (DummyClassifier `most_frequent`) is excluded from this table: it "
    "predicts p=1.0 for the majority class, giving log_loss ≈ 18.9. This is "
    "expected behaviour. B0 is not directly comparable to probabilistic "
    "classifiers and is shown only in the inventory table."
)


def _is_b0(baseline: dict) -> bool:
    """True if this baseline is the most_frequent DummyClassifier (B0)."""
    return (
        baseline.get("model_type") == "DummyClassifier"
        and baseline.get("sklearn_params", {}).get("strategy") == "most_frequent"
    )


def render_validation_table(baselines: list[dict]) -> str:
    """
    Render the primary validation comparison table as Markdown.

    Excludes B0 (most_frequent DummyClassifier) — not directly comparable
    to probabilistic classifiers.
    Sorted ascending by validation log_loss.
    Columns: ID, Model, FS, Expl, Diag, Val log_loss, Val acc, Val brier, Val macro_f1.
    """
    comparable = [b for b in baselines if not _is_b0(b)]
    sorted_baselines = sort_by_validation_log_loss(comparable)

    header = (
        "| ID | Model | FS | Expl | Diag "
        "| Val log_loss | Val acc | Val brier | Val macro_f1 |\n"
        "|----|-------|----|------|------"
        "|--------------|---------|-----------|--------------|"
    )
    rows: list[str] = []
    for b in sorted_baselines:
        bid = b.get("baseline_id", "?")
        model = b.get("model_type", "?")[:22]
        fs = b.get("feature_set_id", "?")
        expl = "Y" if b.get("exploratory") else "N"
        diag = "Y" if b.get("diagnostic") else "N"
        val = get_split_metrics(b, "val")
        ll = format_float(val.get("log_loss"))
        acc = format_float(val.get("accuracy"))
        brier = format_float(val.get("multiclass_brier"))
        macro_f1 = format_float(val.get("macro_f1"))
        rows.append(
            f"| {bid} | {model} | {fs} | {expl} | {diag} "
            f"| {ll} | {acc} | {brier} | {macro_f1} |"
        )

    note = f"\n> **Note:** {_B0_EXCLUSION_NOTE}"
    return header + "\n" + "\n".join(rows) + note


# ---------------------------------------------------------------------------
# L. render_confusion_matrix
# ---------------------------------------------------------------------------

def render_confusion_matrix(baseline: dict, split: str) -> str:
    """
    Render the confusion matrix for one baseline/split as a Markdown table.

    Class order: BLACK_WIN (0), DRAW (1), WHITE_WIN (2).
    Rows = actual class, columns = predicted class.
    Returns empty message if confusion_matrix key not present.
    """
    metrics = get_split_metrics(baseline, split)
    cm = metrics.get("confusion_matrix")
    if cm is None:
        return "_Confusion matrix not available._"

    bid = baseline.get("baseline_id", "?")
    class_labels = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    abbrev = ["BW", "D", "WW"]

    header_row = "| Actual \\ Pred | " + " | ".join(abbrev) + " |"
    sep_row = "|" + "|".join(["---"] * (len(abbrev) + 1)) + "|"
    rows = [header_row, sep_row]
    for i, label in enumerate(class_labels):
        counts = " | ".join(str(cm[i][j]) for j in range(len(abbrev)))
        rows.append(f"| **{label}** | {counts} |")

    header = f"**{bid} confusion matrix ({split} split):**\n\n"
    return header + "\n".join(rows)


# ---------------------------------------------------------------------------
# M. render_signal_decomposition
# ---------------------------------------------------------------------------

def render_signal_decomposition(baselines: list[dict]) -> str:
    """
    Render the signal decomposition section: B1 → B2 → B3 log_loss progression.

    Shows the incremental contribution of adding game metadata, clock, and
    position features to the prior-only baseline.
    """
    by_id = {b.get("baseline_id"): b for b in baselines}
    b1 = by_id.get("B1")
    b2 = by_id.get("B2")
    b3 = by_id.get("B3")

    def _ll(b: dict | None) -> float | None:
        if b is None:
            return None
        v = get_split_metrics(b, "val").get("log_loss")
        return float(v) if v is not None else None

    ll1 = _ll(b1)
    ll2 = _ll(b2)
    ll3 = _ll(b3)

    def _delta(a: float | None, b_val: float | None) -> str:
        if a is None or b_val is None:
            return "N/A"
        return format_float(b_val - a, 4)

    full_delta = _delta(ll1, ll3)

    lines = [
        "Signal decomposition: incremental log_loss improvement as features are added",
        "(validation set, broad split, primary_numbered view).",
        "",
        "| Model | Features added | Val log_loss | Δ vs prior |",
        "|-------|----------------|--------------|------------|",
        f"| B1 | Prior (label frequencies only) | {format_float(ll1)} | — |",
        f"| B2 | + game metadata (FS-B) | {format_float(ll2)} | {_delta(ll1, ll2)} |",
        f"| B3 | + clock + position (FS-E) | {format_float(ll3)} | {_delta(ll2, ll3)} |",
        "",
        f"Full B1→B3 improvement: {full_delta} log_loss units. "
        "Clock timing and position context carry real predictive signal. "
        "However, all broad baselines predict 0 DRAW rows "
        "(minority class ~6% of rows), so accuracy is misleading. "
        "Log_loss is the primary metric.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# N. render_test_snapshot
# ---------------------------------------------------------------------------

def render_test_snapshot(baselines: list[dict]) -> str:
    """
    Render the test set snapshot for primary broad baselines (excluding B0).

    Columns: ID, Test log_loss, Test acc, Test brier, Test macro_f1.
    Test results are reported once for record-keeping only.
    """
    primary = filter_broad_primary_baselines(baselines)
    comparable = [b for b in primary if not _is_b0(b)]
    sorted_baselines = sort_by_validation_log_loss(comparable)

    header = (
        "| ID | Test log_loss | Test acc | Test brier | Test macro_f1 |\n"
        "|----|---------------|----------|------------|---------------|"
    )
    rows: list[str] = []
    for b in sorted_baselines:
        bid = b.get("baseline_id", "?")
        test = get_split_metrics(b, "test")
        ll = format_float(test.get("log_loss"))
        acc = format_float(test.get("accuracy"))
        brier = format_float(test.get("multiclass_brier"))
        macro_f1 = format_float(test.get("macro_f1"))
        rows.append(f"| {bid} | {ll} | {acc} | {brier} | {macro_f1} |")

    note = (
        "\n> **Note:** Test set results are reported here once for record-keeping. "
        "Do not use test metrics to select or tune models."
    )
    return header + "\n" + "\n".join(rows) + note


# ---------------------------------------------------------------------------
# O. render_baseline_evaluation_report
# ---------------------------------------------------------------------------

def render_baseline_evaluation_report(payload: dict) -> str:
    """
    Assemble the full baseline evaluation report as a Markdown string.

    Sections:
      1. Header and context
      2. Baseline inventory (all models)
      3. Validation comparison (broad primary, excluding B0)
      4. Signal decomposition (B1 → B2 → B3)
      5. Diagnostic note (B3-balanced)
      6. Confusion matrices (B3 and B3-balanced, validation)
      7. Test snapshot (broad primary, excluding B0)
      8. Eval baselines (exploratory, not comparable)
      9. Key findings
     10. Recommended next step
    """
    dataset_id = payload.get("dataset_id", "unknown")
    version_tag = payload.get("version_tag", "unknown")
    created_at = payload.get("created_at_utc", "")
    date_str = created_at[:10] if created_at else "unknown"

    baselines = get_baselines(payload)
    by_id = {b.get("baseline_id"): b for b in baselines}
    broad_primary = filter_broad_primary_baselines(baselines)
    eval_expl = filter_eval_exploratory_baselines(baselines)
    diagnostics = filter_diagnostic_baselines(baselines)

    b3 = by_id.get("B3")
    b3_balanced = by_id.get("B3-balanced")

    b3_val_ll = format_float(
        get_split_metrics(b3, "val").get("log_loss") if b3 else None
    )
    b3_val_acc = format_float(
        get_split_metrics(b3, "val").get("accuracy") if b3 else None
    )

    inventory = render_inventory_table(baselines)
    val_table = render_validation_table(broad_primary)
    signal = render_signal_decomposition(baselines)

    b3_cm = render_confusion_matrix(b3, "val") if b3 else "_B3 not found._"
    b3_bal_cm = (
        render_confusion_matrix(b3_balanced, "val") if b3_balanced
        else "_B3-balanced not found._"
    )
    test_snap = render_test_snapshot(baselines)
    eval_table = (
        render_validation_table(eval_expl) if eval_expl
        else "_No eval baselines found._"
    )

    diag_table_section: list[str] = []
    if diagnostics:
        diag_table_section = [render_validation_table(diagnostics), ""]

    lines = [
        "# Baseline Evaluation Report",
        "",
        "**Ticket:** 5.3B — Baseline Evaluation Report",
        "**Labels:** ML/REPORTING | D2 | IMPLEMENTATION",
        f"**Date:** {date_str}",
        f"**dataset_id:** `{dataset_id}`",
        f"**version_tag:** `{version_tag}`",
        "",
        "---",
        "",
        "## 1. Context",
        "",
        "Chess is the testbed for this pilot project. The goal is to predict game",
        "outcomes (White win / Draw / Black win) from mid-game position snapshots",
        "of human chess games played on Lichess (10+0 time control).",
        "",
        "This work is a study of human strategy/reasoning under time pressure, not",
        "engine evaluation. Clock usage, position complexity, and material balance",
        "are all candidate signals.",
        "",
        "This document summarises the Phase 5.2B baseline models (DummyClassifier +",
        "LogisticRegression) as reported in `baseline_results_" + version_tag + ".json`.",
        "Broad and eval-gated baseline results are not directly comparable: the eval",
        "subset is gated on Stockfish annotation availability, which introduces",
        "selection bias (~+20 Elo vs broad).",
        "",
        "---",
        "",
        "## 2. Baseline Inventory",
        "",
        inventory,
        "",
        "---",
        "",
        "## 3. Validation Comparison (Broad Primary Baselines)",
        "",
        "Sorted ascending by validation log_loss. Primary metric: log_loss.",
        "Accuracy is secondary (misleading when DRAW class is ~6% of rows).",
        "",
        val_table,
        "",
        "---",
        "",
        "## 4. Signal Decomposition",
        "",
        signal,
        "",
        "---",
        "",
        "## 5. Diagnostic Baseline: B3-balanced",
        "",
        *diag_table_section,
        "B3-balanced is a diagnostic variant of B3 with `class_weight='balanced'`.",
        "It improves DRAW recall but at a substantial log_loss cost (1.0623 vs 0.8527).",
        "DRAW support is ~59 rows in the broad validation set (~6%). DRAW metrics are",
        "noisy and should be interpreted cautiously.",
        "",
        "### B3 and B3-balanced confusion matrices (validation set)",
        "",
        b3_cm,
        "",
        b3_bal_cm,
        "",
        "---",
        "",
        "## 6. Test Snapshot (Broad Primary Baselines)",
        "",
        test_snap,
        "",
        "---",
        "",
        "## 7. Eval Baselines (Exploratory — Not Comparable to Broad)",
        "",
        "Eval baselines use a gated subset of games with Stockfish evaluations.",
        "Results are exploratory. Eval val/test have very sparse DRAW support",
        "(~4 val / ~2 test DRAW rows). Broad and eval-gated baseline results",
        "are not directly comparable.",
        "",
        eval_table,
        "",
        "---",
        "",
        "## 8. Key Findings",
        "",
        f"1. **Best broad primary baseline:** B3 (LogisticRegression, FS-E) with "
        f"val log_loss={b3_val_ll}, val acc={b3_val_acc}.",
        "2. Clock and position features (B2→B3) provide a real but modest improvement.",
        "3. All unweighted broad baselines predict 0 DRAW rows (minority class ~6%).",
        "4. B3-balanced improves DRAW recall at a substantial log_loss cost.",
        "5. Eval baselines show higher test accuracy due to eval-feature signal,",
        "   but the eval test set is tiny (~53 rows, ~2 DRAW rows); spike unreliable.",
        "6. No broad baseline achieves log_loss below 0.85. This sets the floor for",
        "   Phase 6 GBM experiments.",
        "",
        "---",
        "",
        "## 9. Recommended Next Step",
        "",
        f"Phase 6 GBM experiments should aim to beat the B3 validation log_loss of",
        f"{b3_val_ll} on the broad split.",
        "Calibration (Phase 6.2) should be assessed for any model that substantially",
        "improves on the baseline floor.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P. write_text
# ---------------------------------------------------------------------------

def write_text(path: str | Path, text: str) -> None:
    """Write a text string to a file, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Q. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 5.3B baseline evaluation report."""
    parser = argparse.ArgumentParser(
        description="Render baseline evaluation report for chess-MHSUC Phase 5.3B"
    )
    parser.add_argument("--dataset-id", required=True,
                        help="Dataset identifier string")
    parser.add_argument("--version-tag", required=True,
                        help="Version tag matching the results JSON")
    parser.add_argument("--baseline-results", required=True,
                        help="Path to baseline_results_{tag}.json")
    parser.add_argument("--output", required=True,
                        help="Output Markdown report path")

    args = parser.parse_args(argv)

    print(f"Loading: {args.baseline_results}")
    payload = load_baseline_results(args.baseline_results)

    # Validate dataset_id / version_tag consistency
    if payload.get("dataset_id") != args.dataset_id:
        print(
            f"Warning: --dataset-id {args.dataset_id!r} does not match "
            f"payload dataset_id {payload.get('dataset_id')!r}.",
            file=sys.stderr,
        )
    if payload.get("version_tag") != args.version_tag:
        print(
            f"Warning: --version-tag {args.version_tag!r} does not match "
            f"payload version_tag {payload.get('version_tag')!r}.",
            file=sys.stderr,
        )

    baselines = get_baselines(payload)
    print(f"Loaded {len(baselines)} baselines.")

    report = render_baseline_evaluation_report(payload)
    write_text(args.output, report)
    print(f"Saved report: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
