"""
bootstrap_ci.py — Phase 7.3B game-level cluster bootstrap confidence intervals.

Computes 95% bootstrap CIs for validation-set log_loss for selected models
(B1, B2, B3, G2, G2b) and pairwise delta CIs using game-level cluster resampling.
Resampling is at the game_id level (not row level) to respect the dependency
structure: all checkpoint rows from the same game must move together.

Bootstrap procedure:
1. Extract unique validation game_ids for the model (N_games).
2. Draw N_games game_ids with replacement.
3. For each replicate, look up all rows belonging to drawn game_ids (with
   multiplicity) and compute log_loss on that bootstrap sample.
4. Repeat for n_replicates (default 1000). Compute 2.5th/97.5th percentile CIs.

Pairwise delta procedure:
Same as above but draws the SAME game_ids for both models in each replicate
(paired bootstrap), then computes delta = log_loss(B) - log_loss(A).
Negative delta means B improved over A. CI contains_zero indicates whether
the improvement is statistically resolvable.

Models assessed: B1, B2, B3, G2, G2b (if extra-predictions supplied).
- B0 excluded: degenerate (majority-class).
- B4/B5 excluded: eval-gated (147 val rows, different population).
- G3/G4 excluded: diagnostic only.
- G5/G6 excluded: exploratory, eval-gated.

Pairwise comparisons: B1→B2, B2→B3, B3→G2, B3→G2b (if G2b present).

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.bootstrap_ci \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
        --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
        --extra-predictions data/processed/gbm_hygiene_predictions_2024_09_25k_v1.parquet \\
        --output-json data/processed/bootstrap_ci_2024_09_25k_v1.json \\
        --output-report reports/bootstrap_ci_2024_09_25k_v1.md \\
        --n-replicates 1000 \\
        --seed 42

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
import polars as pl
from sklearn.metrics import log_loss as sklearn_log_loss

from chess_mhsuc.baselines import CLASS_ORDER, LABEL_MAP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BOOTSTRAP_MODEL_IDS: list[str] = ["B1", "B2", "B3", "G2", "G2b"]
_N_CLASSES: int = 3
_PROB_COLS: list[str] = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]
_CI_ALPHA: float = 0.05  # 95% CI

# Pairwise delta comparisons: (model_a, model_b) → delta = LL(B) - LL(A).
# Negative delta means B improved over A.
# G2b pair is included only when G2b is present in bootstrap_results.
_PAIRWISE_COMPARISONS: list[tuple[str, str]] = [
    ("B1", "B2"),
    ("B2", "B3"),
    ("B3", "G2"),
    ("B3", "G2b"),  # conditional: only when G2b is in results
]


# ---------------------------------------------------------------------------
# A. load_baseline_predictions
# ---------------------------------------------------------------------------

def load_baseline_predictions(path: str | Path) -> pl.DataFrame:
    """
    Load baseline predictions Parquet and validate required columns.

    Required columns: baseline_id, split_set, game_id, result_class,
    p_BLACK_WIN, p_DRAW, p_WHITE_WIN.

    Raises ValueError if required columns are missing.
    """
    df = pl.read_parquet(path)
    required = {"baseline_id", "split_set", "game_id", "result_class",
                "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Baseline predictions missing columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# B. load_gbm_predictions
# ---------------------------------------------------------------------------

def load_gbm_predictions(path: str | Path) -> pl.DataFrame:
    """
    Load GBM predictions Parquet and validate required columns.

    Required columns: model_id, split_set, view, game_id, result_class,
    p_BLACK_WIN, p_DRAW, p_WHITE_WIN.

    Raises ValueError if required columns are missing.
    """
    df = pl.read_parquet(path)
    required = {"model_id", "split_set", "view", "game_id", "result_class",
                "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"GBM predictions missing columns: {sorted(missing)}. "
            f"Found: {sorted(df.columns)}"
        )
    return df


# ---------------------------------------------------------------------------
# C. standardize_prediction_schema
# ---------------------------------------------------------------------------

def standardize_prediction_schema(
    baseline_df: pl.DataFrame,
    gbm_df: pl.DataFrame,
    extra_df: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """
    Merge baseline and GBM predictions into a unified schema.

    Unified columns: model_id, split_set, game_id, result_class,
    p_BLACK_WIN, p_DRAW, p_WHITE_WIN.

    Baseline: rename baseline_id -> model_id.
    GBM: filter to view == 'primary_numbered'.
    Extra (e.g. G2b hygiene): filter to view == 'primary_numbered', same logic.

    Only rows from _BOOTSTRAP_MODEL_IDS are retained.
    """
    baseline_unified = baseline_df.rename({"baseline_id": "model_id"}).select(
        ["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS
    )

    gbm_unified = gbm_df.filter(pl.col("view") == "primary_numbered").select(
        ["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS
    )

    parts = [baseline_unified, gbm_unified]

    if extra_df is not None:
        extra_unified = extra_df.filter(pl.col("view") == "primary_numbered").select(
            ["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS
        )
        parts.append(extra_unified)

    combined = pl.concat(parts)
    return combined.filter(pl.col("model_id").is_in(_BOOTSTRAP_MODEL_IDS))


# ---------------------------------------------------------------------------
# D. extract_val_rows
# ---------------------------------------------------------------------------

def extract_val_rows(combined_df: pl.DataFrame, model_id: str) -> pl.DataFrame:
    """
    Extract validation-split rows for a single model_id.

    Raises ValueError if no rows are found.
    """
    rows = combined_df.filter(
        (pl.col("model_id") == model_id) & (pl.col("split_set") == "val")
    )
    if len(rows) == 0:
        raise ValueError(
            f"No validation rows found for model_id={model_id!r}. "
            f"Available models: {combined_df['model_id'].unique().sort().to_list()}"
        )
    return rows


# ---------------------------------------------------------------------------
# E. get_unique_val_game_ids
# ---------------------------------------------------------------------------

def get_unique_val_game_ids(val_df: pl.DataFrame) -> list[str]:
    """
    Return sorted list of unique game_ids in the validation DataFrame.

    Sorting ensures determinism across runs.
    """
    return sorted(val_df["game_id"].unique().to_list())


# ---------------------------------------------------------------------------
# F. compute_point_log_loss
# ---------------------------------------------------------------------------

def compute_point_log_loss(val_df: pl.DataFrame) -> float:
    """
    Compute log_loss for a validation DataFrame.

    Uses sklearn log_loss with labels=CLASS_ORDER to handle potential
    missing classes in bootstrap samples.
    """
    y_true_str = val_df["result_class"].to_list()
    y_true = np.array([LABEL_MAP[c] for c in y_true_str])
    proba = val_df.select(_PROB_COLS).to_numpy()
    return float(sklearn_log_loss(y_true, proba, labels=[0, 1, 2]))


# ---------------------------------------------------------------------------
# G. build_game_row_index
# ---------------------------------------------------------------------------

def build_game_row_index(val_df: pl.DataFrame) -> dict[str, list[int]]:
    """
    Build a mapping {game_id: [row_index, ...]} for fast bootstrap lookup.

    Row indices are 0-based positional indices into val_df.
    """
    game_ids_col = val_df["game_id"].to_list()
    index: dict[str, list[int]] = {}
    for i, gid in enumerate(game_ids_col):
        if gid not in index:
            index[gid] = []
        index[gid].append(i)
    return index


# ---------------------------------------------------------------------------
# H. bootstrap_one_replicate
# ---------------------------------------------------------------------------

def bootstrap_one_replicate(
    val_df: pl.DataFrame,
    game_ids: list[str],
    game_row_index: dict[str, list[int]],
    rng: np.random.Generator,
) -> float:
    """
    Compute log_loss for one bootstrap replicate.

    Draws len(game_ids) game_ids with replacement. Collects all rows belonging
    to the drawn game_ids (with multiplicity). Computes log_loss on that sample.

    Returns the bootstrap log_loss as a float. Returns NaN if the sample
    contains only one class (degenerate replicate — extremely rare).
    """
    drawn_ids = rng.choice(game_ids, size=len(game_ids), replace=True)
    row_indices: list[int] = []
    for gid in drawn_ids:
        row_indices.extend(game_row_index[gid])

    boot_df = val_df[row_indices]

    classes_present = boot_df["result_class"].n_unique()
    if classes_present < 2:
        return float("nan")

    return compute_point_log_loss(boot_df)


# ---------------------------------------------------------------------------
# I. run_bootstrap
# ---------------------------------------------------------------------------

def run_bootstrap(
    val_df: pl.DataFrame,
    n_replicates: int = 1000,
    seed: int = 42,
) -> np.ndarray:
    """
    Run game-level cluster bootstrap for a single model's validation DataFrame.

    Returns array of shape (n_replicates,) with log_loss values.
    NaN values (degenerate replicates) are included as-is.
    """
    game_ids = get_unique_val_game_ids(val_df)
    game_row_index = build_game_row_index(val_df)
    rng = np.random.default_rng(seed)

    results = np.empty(n_replicates, dtype=np.float64)
    for i in range(n_replicates):
        results[i] = bootstrap_one_replicate(val_df, game_ids, game_row_index, rng)

    return results


# ---------------------------------------------------------------------------
# J. compute_ci_from_bootstrap
# ---------------------------------------------------------------------------

def compute_ci_from_bootstrap(
    bootstrap_values: np.ndarray,
    alpha: float = _CI_ALPHA,
) -> dict[str, float]:
    """
    Compute percentile CI from bootstrap distribution.

    Returns dict with keys: mean, std, ci_lower, ci_upper, n_replicates,
    n_nan (count of degenerate/NaN replicates).

    alpha=0.05 gives a 95% CI (2.5th / 97.5th percentile).
    """
    n_nan = int(np.sum(np.isnan(bootstrap_values)))
    valid = bootstrap_values[~np.isnan(bootstrap_values)]

    if len(valid) == 0:
        return {
            "mean": float("nan"),
            "std": float("nan"),
            "ci_lower": float("nan"),
            "ci_upper": float("nan"),
            "n_replicates": int(len(bootstrap_values)),
            "n_nan": n_nan,
        }

    lower = float(np.percentile(valid, 100 * alpha / 2))
    upper = float(np.percentile(valid, 100 * (1 - alpha / 2)))

    return {
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid)),
        "ci_lower": lower,
        "ci_upper": upper,
        "n_replicates": int(len(bootstrap_values)),
        "n_nan": n_nan,
    }


# ---------------------------------------------------------------------------
# K. run_bootstrap_for_model
# ---------------------------------------------------------------------------

def run_bootstrap_for_model(
    combined_df: pl.DataFrame,
    model_id: str,
    n_replicates: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Run full bootstrap CI pipeline for one model_id.

    Returns dict with: model_id, point_log_loss, n_val_rows,
    n_val_games, bootstrap_seed, and all CI fields from compute_ci_from_bootstrap.
    """
    val_df = extract_val_rows(combined_df, model_id)
    point_ll = compute_point_log_loss(val_df)
    n_val_rows = len(val_df)
    n_val_games = val_df["game_id"].n_unique()

    boot_values = run_bootstrap(val_df, n_replicates=n_replicates, seed=seed)
    ci = compute_ci_from_bootstrap(boot_values)

    return {
        "model_id": model_id,
        "point_log_loss": point_ll,
        "n_val_rows": n_val_rows,
        "n_val_games": n_val_games,
        "bootstrap_seed": seed,
        **ci,
    }


# ---------------------------------------------------------------------------
# L. run_all_bootstrap
# ---------------------------------------------------------------------------

def run_all_bootstrap(
    combined_df: pl.DataFrame,
    model_ids: list[str] | None = None,
    n_replicates: int = 1000,
    seed: int = 42,
) -> dict[str, dict[str, Any]]:
    """
    Run bootstrap CIs for all available models in combined_df.

    If model_ids is provided, only those models are run.
    Models not found in combined_df are skipped with a warning.

    Returns {model_id: result_dict}.
    """
    available = set(
        combined_df.filter(pl.col("split_set") == "val")["model_id"].unique().to_list()
    )
    targets = model_ids if model_ids is not None else _BOOTSTRAP_MODEL_IDS

    results: dict[str, dict[str, Any]] = {}
    for mid in targets:
        if mid not in available:
            print(f"  [bootstrap] WARNING: {mid} not found in combined_df, skipping.",
                  file=sys.stderr)
            continue
        print(f"  [bootstrap] Running {mid} ({n_replicates} replicates)...")
        results[mid] = run_bootstrap_for_model(
            combined_df, mid, n_replicates=n_replicates, seed=seed
        )
        r = results[mid]
        print(
            f"    point_log_loss={r['point_log_loss']:.4f}  "
            f"95% CI=[{r['ci_lower']:.4f}, {r['ci_upper']:.4f}]  "
            f"n_games={r['n_val_games']}  n_rows={r['n_val_rows']}"
        )
    return results


# ---------------------------------------------------------------------------
# M. build_bootstrap_payload
# ---------------------------------------------------------------------------

def build_bootstrap_payload(
    dataset_id: str,
    version_tag: str,
    bootstrap_results: dict[str, dict[str, Any]],
    n_replicates: int,
    seed: int,
    pairwise_results: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build JSON-serializable bootstrap CI payload."""
    payload: dict[str, Any] = {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_replicates": n_replicates,
        "seed": seed,
        "ci_alpha": _CI_ALPHA,
        "bootstrap_results": bootstrap_results,
    }
    if pairwise_results is not None:
        payload["pairwise_results"] = pairwise_results
    return payload


# ---------------------------------------------------------------------------
# N. save_bootstrap_json
# ---------------------------------------------------------------------------

def save_bootstrap_json(payload: dict, path: str | Path) -> None:
    """Save bootstrap CI payload as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


# ---------------------------------------------------------------------------
# O. render_markdown_table
# ---------------------------------------------------------------------------

def render_markdown_table(
    headers: list[str], rows: list[list[str]]
) -> str:
    """Render a Markdown table from headers and rows."""
    sep = ["---"] * len(headers)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# P. render_bootstrap_report
# ---------------------------------------------------------------------------

def render_bootstrap_report(
    payload: dict[str, Any],
) -> str:
    """
    Render a Markdown bootstrap CI report from the payload dict.

    Sections: header, per-model CIs, pairwise delta CIs, methodology, caveats.

    Timestamp is intentionally omitted from the report body (it is in the JSON
    artifact) so that re-running with the same seed produces an identical report.
    """
    dataset_id = payload["dataset_id"]
    version_tag = payload["version_tag"]
    n_replicates = payload["n_replicates"]
    seed = payload["seed"]
    results = payload["bootstrap_results"]
    pairwise = payload.get("pairwise_results", {})

    lines: list[str] = []

    # Header (no dynamic timestamp — timestamp is in the JSON artifact only)
    lines += [
        f"# Bootstrap CI Report — {dataset_id}",
        "",
        f"**Version tag:** `{version_tag}`",
        f"**Ticket:** 7.3B (Modeling Hygiene Hardening)",
        "",
    ]

    # Summary
    present_models = [m for m in _BOOTSTRAP_MODEL_IDS if m in results]
    lines += [
        "## Summary",
        "",
        "Game-level cluster bootstrap 95% confidence intervals for validation "
        "log_loss and pairwise deltas. Resampling is at the game_id level (not row "
        "level) to respect the within-game dependency of checkpoint rows.",
        "",
        f"Models assessed: {', '.join(present_models)}.",
        "",
        f"**Replicates:** {n_replicates}  **Seed:** {seed}  **CI:** 95% (percentile method)",
        "",
    ]

    # Per-model results table
    lines += ["## Per-model log_loss CIs", ""]
    headers = ["Model", "Val log_loss", "CI lower", "CI upper", "Width", "n_games", "n_rows"]
    rows = []
    for mid in _BOOTSTRAP_MODEL_IDS:
        if mid not in results:
            continue
        r = results[mid]
        ll = r["point_log_loss"]
        lo = r["ci_lower"]
        hi = r["ci_upper"]
        width = hi - lo if not (np.isnan(lo) or np.isnan(hi)) else float("nan")
        rows.append([
            mid,
            f"{ll:.4f}",
            f"{lo:.4f}",
            f"{hi:.4f}",
            f"{width:.4f}",
            str(r["n_val_games"]),
            str(r["n_val_rows"]),
        ])
    lines += [render_markdown_table(headers, rows), ""]

    # Pairwise delta table
    if pairwise:
        lines += ["## Pairwise delta log_loss CIs (delta = LL(B) - LL(A))", ""]
        lines += [
            "Negative delta means B improved over A. "
            "**contains_zero** = True means the CI includes 0, "
            "so the improvement is not statistically resolvable at 95%.",
            "",
        ]
        d_headers = ["Comparison", "Point delta", "CI lower", "CI upper", "contains_zero", "n_games"]
        d_rows = []
        for model_a, model_b in _PAIRWISE_COMPARISONS:
            key = f"{model_a}_vs_{model_b}"
            if key not in pairwise:
                continue
            p = pairwise[key]
            d_rows.append([
                f"{model_a} → {model_b}",
                f"{p['point_delta']:+.4f}",
                f"{p['ci_lower']:+.4f}",
                f"{p['ci_upper']:+.4f}",
                str(p["contains_zero"]),
                str(p["n_common_games"]),
            ])
        lines += [render_markdown_table(d_headers, d_rows), ""]

        # Highlight B2→B3
        b2b3_key = "B2_vs_B3"
        if b2b3_key in pairwise:
            p = pairwise[b2b3_key]
            zero_str = "Yes — not statistically resolvable" if p["contains_zero"] else "No — CI excludes 0"
            lines += [
                f"**B2 → B3 (clock features):** point delta = {p['point_delta']:+.4f}  "
                f"95% CI [{p['ci_lower']:+.4f}, {p['ci_upper']:+.4f}]  "
                f"CI contains zero: {zero_str}.",
                "",
            ]

    # Methodology
    lines += [
        "## Methodology",
        "",
        "### Why game-level resampling?",
        "",
        "Each game contributes multiple checkpoint rows (move_10, move_20). "
        "Row-level bootstrap would treat these as independent, underestimating "
        "variance. Game-level cluster bootstrap draws whole games with replacement, "
        "preserving the within-game correlation structure.",
        "",
        "### Paired pairwise bootstrap",
        "",
        "For delta CIs the same bootstrap game_id sample is used for both models "
        "in each replicate (paired bootstrap). This removes game-sampling variance "
        "from the delta estimate and is the correct approach for model comparisons "
        "on the same dataset.",
        "",
        "### Procedure",
        "",
        "1. Extract unique validation game_ids for the model (N games).",
        "2. Draw N game_ids with replacement.",
        "3. Collect all rows belonging to drawn game_ids (with multiplicity).",
        "4. Compute log_loss on that bootstrap sample.",
        f"5. Repeat {n_replicates} times (seed={seed}).",
        "6. Compute 2.5th and 97.5th percentile for 95% CI.",
        "",
        "### Primary_numbered view",
        "",
        "Bootstrap uses the primary_numbered view (excludes `selected_position_type == 'last'`), "
        "consistent with how all broad models are evaluated.",
        "",
    ]

    # Interpretation
    lines += [
        "## Interpretation",
        "",
        "**Note:** At this pilot scale (approx 348 val games, approx 931 rows), "
        "bootstrap CIs are wide. Interval endpoints should not be over-interpreted.",
        "",
    ]

    if "G2" in results and "G2b" in results:
        g2 = results["G2"]
        g2b = results["G2b"]
        lines += [
            "### G2 vs G2b",
            "",
            f"- G2 (300 unstopped iterations): {g2['point_log_loss']:.4f} "
            f"[{g2['ci_lower']:.4f}, {g2['ci_upper']:.4f}]",
            f"- G2b (early stopping, val_fraction=0.15): {g2b['point_log_loss']:.4f} "
            f"[{g2b['ci_lower']:.4f}, {g2b['ci_upper']:.4f}]",
            "",
            "G2b improves point val log_loss over G2. However, the per-model CIs "
            "overlap substantially. Whether the improvement is statistically "
            "resolvable should be judged from the paired B3→G2b delta CI above, "
            "not from comparing the individual CIs.",
            "",
            "G2b is a fair-comparison diagnostic: same FS-E features as G2, but with "
            "`early_stopping=True, validation_fraction=0.15, n_iter_no_change=10`. "
            "G2 ran 300 unstopped iterations because sklearn `early_stopping='auto'` "
            "does not activate below 10,000 training samples (pilot train: 4,344 rows).",
            "",
        ]

    if "B3" in results:
        b3 = results["B3"]
        lines += [
            "### B3 baseline reference",
            "",
            f"B3 (LogisticRegression on FS-E): {b3['point_log_loss']:.4f} "
            f"[{b3['ci_lower']:.4f}, {b3['ci_upper']:.4f}]",
            "",
            "B3 remains the best broad model at this pilot scale. "
            "For a new model to be considered an improvement over B3, "
            "the B3→newmodel paired delta CI must exclude zero.",
            "",
        ]

    # Caveats
    lines += [
        "## Caveats",
        "",
        "- Pilot scale only (approx 348 val games). CIs are wide.",
        "- G2b results depend on the extra predictions artifact (gbm_hygiene). "
        "Re-run bootstrap after any G2b hyperparameter change.",
        "- CIs are percentile-method bootstrap, not BCa. At this sample size "
        "the distinction is negligible.",
        "- If n_nan > 0 in the payload, some replicates drew a sample with fewer "
        "than 2 classes and were excluded from CI computation.",
        "",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# R. run_paired_delta_bootstrap
# ---------------------------------------------------------------------------

def run_paired_delta_bootstrap(
    combined_df: pl.DataFrame,
    model_a: str,
    model_b: str,
    n_replicates: int = 1000,
    seed: int = 42,
) -> np.ndarray:
    """
    Run paired game-level bootstrap for delta = log_loss(B) - log_loss(A).

    Paired: the SAME bootstrap sample of game_ids is used for both models
    each replicate, so within-game correlations are preserved and the
    comparison is correctly paired.

    Negative delta means model_b improved over model_a.

    Returns array of shape (n_replicates,) with delta values.
    NaN for degenerate replicates (< 2 classes in either model's sample).
    """
    val_a = extract_val_rows(combined_df, model_a)
    val_b = extract_val_rows(combined_df, model_b)

    game_ids_a = set(get_unique_val_game_ids(val_a))
    game_ids_b = set(get_unique_val_game_ids(val_b))
    common_game_ids = sorted(game_ids_a & game_ids_b)
    if not common_game_ids:
        return np.full(n_replicates, float("nan"))

    val_a = val_a.filter(pl.col("game_id").is_in(common_game_ids))
    val_b = val_b.filter(pl.col("game_id").is_in(common_game_ids))

    idx_a = build_game_row_index(val_a)
    idx_b = build_game_row_index(val_b)
    rng = np.random.default_rng(seed)

    deltas = np.empty(n_replicates, dtype=np.float64)
    for i in range(n_replicates):
        drawn = rng.choice(common_game_ids, size=len(common_game_ids), replace=True)
        rows_a: list[int] = []
        rows_b: list[int] = []
        for gid in drawn:
            rows_a.extend(idx_a[gid])
            rows_b.extend(idx_b[gid])

        boot_a = val_a[rows_a]
        boot_b = val_b[rows_b]

        if boot_a["result_class"].n_unique() < 2 or boot_b["result_class"].n_unique() < 2:
            deltas[i] = float("nan")
            continue

        deltas[i] = compute_point_log_loss(boot_b) - compute_point_log_loss(boot_a)

    return deltas


# ---------------------------------------------------------------------------
# S. compute_delta_ci
# ---------------------------------------------------------------------------

def compute_delta_ci(
    bootstrap_deltas: np.ndarray,
    model_a: str,
    model_b: str,
    combined_df: pl.DataFrame,
    alpha: float = _CI_ALPHA,
) -> dict[str, Any]:
    """
    Compute CI for paired delta = log_loss(B) - log_loss(A).

    Returns dict with: model_a, model_b, point_delta, ci_lower, ci_upper,
    contains_zero, n_replicates, n_nan, n_common_games.

    contains_zero: True if CI includes 0 (i.e., improvement not statistically
    resolvable at this alpha level).

    Negative point_delta and CI entirely below zero means B is clearly better.
    """
    val_a = extract_val_rows(combined_df, model_a)
    val_b = extract_val_rows(combined_df, model_b)
    common_game_ids = sorted(
        set(get_unique_val_game_ids(val_a)) & set(get_unique_val_game_ids(val_b))
    )
    val_a_common = val_a.filter(pl.col("game_id").is_in(common_game_ids))
    val_b_common = val_b.filter(pl.col("game_id").is_in(common_game_ids))
    point_delta = (
        compute_point_log_loss(val_b_common) - compute_point_log_loss(val_a_common)
    )

    n_nan = int(np.sum(np.isnan(bootstrap_deltas)))
    valid = bootstrap_deltas[~np.isnan(bootstrap_deltas)]

    if len(valid) == 0:
        return {
            "model_a": model_a, "model_b": model_b,
            "point_delta": point_delta,
            "ci_lower": float("nan"), "ci_upper": float("nan"),
            "contains_zero": True,
            "n_replicates": int(len(bootstrap_deltas)),
            "n_nan": n_nan,
            "n_common_games": len(common_game_ids),
        }

    ci_lower = float(np.percentile(valid, 100 * alpha / 2))
    ci_upper = float(np.percentile(valid, 100 * (1 - alpha / 2)))
    contains_zero = ci_lower <= 0.0 <= ci_upper

    return {
        "model_a": model_a,
        "model_b": model_b,
        "point_delta": point_delta,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "contains_zero": contains_zero,
        "n_replicates": int(len(bootstrap_deltas)),
        "n_nan": n_nan,
        "n_common_games": len(common_game_ids),
    }


# ---------------------------------------------------------------------------
# T. run_all_pairwise_deltas
# ---------------------------------------------------------------------------

def run_all_pairwise_deltas(
    combined_df: pl.DataFrame,
    bootstrap_results: dict[str, dict[str, Any]],
    n_replicates: int = 1000,
    seed: int = 42,
) -> dict[str, dict[str, Any]]:
    """
    Run all required pairwise delta bootstraps.

    Pairs are drawn from _PAIRWISE_COMPARISONS. The B3→G2b pair is skipped
    if G2b is not in bootstrap_results.

    Returns {"{A}_vs_{B}": delta_ci_dict}.
    """
    available = set(bootstrap_results.keys())
    results: dict[str, dict[str, Any]] = {}

    for model_a, model_b in _PAIRWISE_COMPARISONS:
        if model_a not in available or model_b not in available:
            continue
        key = f"{model_a}_vs_{model_b}"
        print(f"  [bootstrap] Pairwise {model_a}→{model_b} ({n_replicates} replicates)...")
        deltas = run_paired_delta_bootstrap(
            combined_df, model_a, model_b,
            n_replicates=n_replicates, seed=seed,
        )
        ci = compute_delta_ci(deltas, model_a, model_b, combined_df)
        results[key] = ci
        direction = "B improved" if ci["point_delta"] < 0 else "B worsened"
        zero_note = "CI contains 0" if ci["contains_zero"] else "CI excludes 0"
        print(
            f"    delta={ci['point_delta']:+.4f}  "
            f"95% CI=[{ci['ci_lower']:+.4f}, {ci['ci_upper']:+.4f}]  "
            f"{direction}  {zero_note}"
        )
    return results


# ---------------------------------------------------------------------------
# Q. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 7.3B bootstrap CI computation."""
    parser = argparse.ArgumentParser(
        description="Compute game-level cluster bootstrap CIs for chess-MHSUC"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--baseline-predictions", required=True,
                        help="Path to baseline_predictions_{tag}.parquet")
    parser.add_argument("--gbm-predictions", required=True,
                        help="Path to gbm_predictions_{tag}.parquet")
    parser.add_argument("--extra-predictions", default=None,
                        help="Path to extra GBM predictions Parquet (e.g. G2b hygiene artifact)")
    parser.add_argument("--output-json", required=True,
                        help="Output path for bootstrap CI JSON")
    parser.add_argument("--output-report", required=True,
                        help="Output path for bootstrap CI Markdown report")
    parser.add_argument("--n-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)

    print(f"dataset_id={args.dataset_id}  version={args.version_tag}")
    print(f"n_replicates={args.n_replicates}  seed={args.seed}")

    baseline_df = load_baseline_predictions(args.baseline_predictions)
    gbm_df = load_gbm_predictions(args.gbm_predictions)

    extra_df: pl.DataFrame | None = None
    if args.extra_predictions and Path(args.extra_predictions).exists():
        extra_df = load_gbm_predictions(args.extra_predictions)
        print(f"Loaded extra predictions: {extra_df.shape}")
    elif args.extra_predictions:
        print(
            f"  [bootstrap] WARNING: --extra-predictions path not found: "
            f"{args.extra_predictions}. G2b will be skipped.",
            file=sys.stderr,
        )

    combined_df = standardize_prediction_schema(baseline_df, gbm_df, extra_df)
    print(f"Combined validation models: "
          f"{sorted(combined_df.filter(pl.col('split_set')=='val')['model_id'].unique().to_list())}")

    bootstrap_results = run_all_bootstrap(
        combined_df,
        n_replicates=args.n_replicates,
        seed=args.seed,
    )

    pairwise_results = run_all_pairwise_deltas(
        combined_df,
        bootstrap_results,
        n_replicates=args.n_replicates,
        seed=args.seed,
    )

    payload = build_bootstrap_payload(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        bootstrap_results=bootstrap_results,
        n_replicates=args.n_replicates,
        seed=args.seed,
        pairwise_results=pairwise_results,
    )

    save_bootstrap_json(payload, args.output_json)
    print(f"Saved bootstrap JSON: {args.output_json}")

    report_md = render_bootstrap_report(payload)
    Path(args.output_report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_report, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Saved bootstrap report: {args.output_report}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
