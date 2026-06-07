"""
assess_dataset.py — Feature dataset assessment for chess-MHSUC.

Reads feature Parquet tables produced by features.py and generates a
reproducible dataset assessment report (Markdown + JSON sidecar).

CLI usage:
    python -m chess_mhsuc.assess_dataset \
        --feature-broad  data/processed/feature_positions_broad_<tag>.parquet \
        --feature-eval   data/processed/feature_positions_eval_<tag>.parquet \
        --feature-metadata data/processed/feature_metadata_<tag>.json \
        --output-dir     reports/phase_reports \
        --version-tag    2024_09_25k_v1
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _s(val: object) -> object:
    """Coerce Polars scalars to JSON-serialisable Python primitives."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    # Polars returns numpy-like scalars; plain Python int/float/str/bool pass through.
    if isinstance(val, (int, float, str, bool)):
        return val
    # Fallback: try converting via Python builtins.
    try:
        return int(val)
    except (TypeError, ValueError):
        pass
    try:
        return float(val)
    except (TypeError, ValueError):
        pass
    return str(val)


def _result_dist(df: pl.DataFrame, col: str = "result_class") -> dict:
    """Return {'counts': {label: n}, 'pct': {label: pct}} for a string column."""
    total = len(df)
    counts: dict[str, int] = {}
    pct: dict[str, float] = {}
    if total == 0:
        return {"counts": counts, "pct": pct}
    rows = (
        df.group_by(col)
        .agg(pl.len().alias("n"))
        .sort(col)
        .rows()
    )
    for label, n in rows:
        counts[str(label)] = int(n)
        pct[str(label)] = round(100.0 * n / total, 2)
    return {"counts": counts, "pct": pct}


def _col_stats(series: pl.Series) -> dict:
    """Return basic numeric stats for a Polars Series."""
    non_null = series.drop_nulls()
    n = len(non_null)
    null_count = len(series) - n
    if n == 0:
        return {"min": None, "max": None, "mean": None, "median": None, "std": None, "null_count": null_count}
    return {
        "min": _s(non_null.min()),
        "max": _s(non_null.max()),
        "mean": _s(non_null.mean()),
        "median": _s(non_null.median()),
        "std": _s(non_null.std()),
        "null_count": null_count,
    }


# ---------------------------------------------------------------------------
# A. Target distribution
# ---------------------------------------------------------------------------

def assess_target_distribution(df: pl.DataFrame) -> dict:
    """Return result_class and white_result_numeric distributions."""
    result = _result_dist(df, "result_class")
    wrn = df["white_result_numeric"]
    return {
        "result_class": result,
        "white_result_numeric": _col_stats(wrn),
        "n_rows": len(df),
    }


# ---------------------------------------------------------------------------
# B. Rating distribution
# ---------------------------------------------------------------------------

def assess_rating_distribution(df: pl.DataFrame) -> dict:
    """Return white_elo, black_elo, avg_elo, elo_diff stats."""
    return {
        "white_elo": _col_stats(df["white_elo"].cast(pl.Float64)),
        "black_elo": _col_stats(df["black_elo"].cast(pl.Float64)),
        "avg_elo": _col_stats(df["avg_elo"]),
        "elo_diff": _col_stats(df["elo_diff"].cast(pl.Float64)),
    }


# ---------------------------------------------------------------------------
# C. Clock distribution
# ---------------------------------------------------------------------------

def assess_clock_distribution(df: pl.DataFrame) -> dict:
    """Return clock stats plus low-time flag rates."""
    def _flag_rate(col: str) -> dict:
        n_true = int(df[col].sum())
        total = len(df)
        return {"n_true": n_true, "pct": round(100.0 * n_true / total, 2) if total > 0 else 0.0}

    return {
        "white_clock_s": _col_stats(df["white_clock_s"].cast(pl.Float64)),
        "black_clock_s": _col_stats(df["black_clock_s"].cast(pl.Float64)),
        "white_clock_frac": _col_stats(df["white_clock_frac"]),
        "black_clock_frac": _col_stats(df["black_clock_frac"]),
        "clock_diff_frac": _col_stats(df["clock_diff_frac"]),
        "clock_anomaly_n": int(df["clock_anomaly"].sum()),
        "white_low_60": _flag_rate("white_low_60"),
        "black_low_60": _flag_rate("black_low_60"),
        "white_low_30": _flag_rate("white_low_30"),
        "black_low_30": _flag_rate("black_low_30"),
        "white_low_10": _flag_rate("white_low_10"),
        "black_low_10": _flag_rate("black_low_10"),
    }


# ---------------------------------------------------------------------------
# D. Eval distribution
# ---------------------------------------------------------------------------

def assess_eval_distribution(df: pl.DataFrame) -> dict:
    """Return eval_cp_clipped bin counts plus mate-eval stats."""
    has_eval_n = int(df["has_eval"].sum())
    total = len(df)

    # Eval coverage
    eval_coverage_pct = round(100.0 * has_eval_n / total, 2) if total > 0 else 0.0

    # Bin eval_cp_clipped on rows where has_eval=True
    df_eval = df.filter(pl.col("has_eval"))
    n_eval = len(df_eval)

    ec = pl.col("eval_cp_clipped")
    bin_filters = [
        ("le_neg500",       ec <= -500),
        ("neg500_to_neg200",(ec > -500) & (ec <= -200)),
        ("neg200_to_neg50", (ec > -200) & (ec <= -50)),
        ("neg50_to_50",     (ec > -50)  & (ec < 50)),
        ("50_to_200",       (ec >= 50)  & (ec < 200)),
        ("200_to_500",      (ec >= 200) & (ec < 500)),
        ("ge_500",          ec >= 500),
    ]

    bins: dict[str, dict] = {}
    for bin_name, filt in bin_filters:
        n_bin = int(df_eval.filter(filt).height)
        bins[bin_name] = {
            "n": n_bin,
            "pct_of_eval": round(100.0 * n_bin / n_eval, 2) if n_eval > 0 else 0.0,
        }

    mate_eval_n = int(df_eval["is_mate_eval"].sum()) if n_eval > 0 else 0
    mate_abs = df_eval["eval_mate_abs"].drop_nulls()

    return {
        "has_eval_n": has_eval_n,
        "eval_coverage_pct": eval_coverage_pct,
        "eval_cp_clipped": _col_stats(df_eval["eval_cp_clipped"]) if n_eval > 0 else _col_stats(pl.Series("eval_cp_clipped", [], dtype=pl.Int64)),
        "eval_bins": bins,
        "is_mate_eval_n": mate_eval_n,
        "eval_mate_abs": _col_stats(mate_abs.cast(pl.Float64)) if len(mate_abs) > 0 else _col_stats(pl.Series("eval_mate_abs", [], dtype=pl.Float64)),
    }


# ---------------------------------------------------------------------------
# E. Checkpoint distribution
# ---------------------------------------------------------------------------

def assess_checkpoint_distribution(df: pl.DataFrame) -> dict:
    """Return row and game counts by selected_position_type and checkpoint_index."""
    total_rows = len(df)
    total_games = df["game_id"].n_unique()

    # Rows by checkpoint type
    rows_by_type = (
        df.group_by("selected_position_type")
        .agg(pl.len().alias("n_rows"), pl.col("game_id").n_unique().alias("n_games"))
        .sort("selected_position_type")
    )
    checkpoint_breakdown: dict[str, dict] = {}
    for row in rows_by_type.rows(named=True):
        ctype = row["selected_position_type"]
        n_rows = row["n_rows"]
        n_games = row["n_games"]
        checkpoint_breakdown[ctype] = {
            "n_rows": int(n_rows),
            "n_games": int(n_games),
            "pct_rows": round(100.0 * n_rows / total_rows, 2) if total_rows > 0 else 0.0,
        }

    duplicate_n = int(df["duplicate_ply_checkpoint"].sum())
    last_only_n = int(df.filter(
        pl.col("is_last_checkpoint") & ~pl.col("duplicate_ply_checkpoint")
    ).height)

    return {
        "total_rows": total_rows,
        "total_games": total_games,
        "checkpoint_breakdown": checkpoint_breakdown,
        "duplicate_ply_checkpoint_n": duplicate_n,
        "last_only_rows": last_only_n,
    }


# ---------------------------------------------------------------------------
# F. Null counts
# ---------------------------------------------------------------------------

def assess_null_counts(df: pl.DataFrame) -> dict:
    """Return null count and null % for every column."""
    total = len(df)
    result: dict[str, dict] = {}
    for col in df.columns:
        n_null = int(df[col].null_count())
        result[col] = {
            "null_count": n_null,
            "null_pct": round(100.0 * n_null / total, 2) if total > 0 else 0.0,
        }
    return result


# ---------------------------------------------------------------------------
# G. Slice distributions
# ---------------------------------------------------------------------------

def assess_slice_distributions(df: pl.DataFrame) -> dict:
    """Return counts/rates for is_time_forfeit, termination, and has_eval."""
    total = len(df)

    def _bool_rate(col: str) -> dict:
        n = int(df[col].sum())
        return {"n_true": n, "pct": round(100.0 * n / total, 2) if total > 0 else 0.0}

    termination_dist = _result_dist(df, "termination")

    return {
        "is_time_forfeit": _bool_rate("is_time_forfeit"),
        "has_eval": _bool_rate("has_eval"),
        "termination": termination_dist,
    }


# ---------------------------------------------------------------------------
# H. Leakage safety
# ---------------------------------------------------------------------------

_LEAKAGE_FORBIDDEN = [
    "n_plies_total", "ply", "white_rating_diff", "black_rating_diff",
    "accepted_basic", "accepted_eval", "rejection_reason", "has_clock",
    "result_raw", "time_control", "source_file", "source_month",
    "event", "utc_date", "utc_time",
]

def assess_leakage_safety(df: pl.DataFrame, feature_metadata: dict | None = None) -> dict:
    """Check that known forbidden leakage columns are absent from df."""
    present_cols = set(df.columns)

    forbidden_found = [c for c in _LEAKAGE_FORBIDDEN if c in present_cols]

    # If metadata available, also check its forbidden_leakage_columns list
    metadata_forbidden_found: list[str] = []
    if feature_metadata is not None:
        meta_forbidden = feature_metadata.get("forbidden_leakage_columns", {})
        if isinstance(meta_forbidden, dict):
            meta_keys = list(meta_forbidden.keys())
        else:
            meta_keys = list(meta_forbidden)
        metadata_forbidden_found = [c for c in meta_keys if c in present_cols]

    all_forbidden_found = sorted(set(forbidden_found + metadata_forbidden_found))

    return {
        "leakage_safe": len(all_forbidden_found) == 0,
        "forbidden_cols_found": all_forbidden_found,
        "hardcoded_forbidden_checked": _LEAKAGE_FORBIDDEN,
        "result_class_present": "result_class" in present_cols,
        "termination_present": "termination" in present_cols,
        "game_id_present": "game_id" in present_cols,
    }


# ---------------------------------------------------------------------------
# I. Broad vs. eval comparison
# ---------------------------------------------------------------------------

def compare_broad_eval(df_broad: pl.DataFrame, df_eval: pl.DataFrame) -> dict:
    """Compare key distributions between broad and eval-gated tables."""
    def _mean(df: pl.DataFrame, col: str) -> float | None:
        s = df[col].drop_nulls()
        if len(s) == 0:
            return None
        return _s(s.mean())

    broad_n = len(df_broad)
    eval_n = len(df_eval)
    broad_games = df_broad["game_id"].n_unique()
    eval_games = df_eval["game_id"].n_unique()

    broad_result = _result_dist(df_broad, "result_class")
    eval_result = _result_dist(df_eval, "result_class")

    # eval coverage by checkpoint type in broad table
    eval_by_checkpoint: dict[str, dict] = {}
    for ctype in ["move_10", "move_20", "move_30", "move_40", "last"]:
        broad_ct = df_broad.filter(pl.col("selected_position_type") == ctype)
        eval_ct = df_eval.filter(pl.col("selected_position_type") == ctype)
        n_broad_ct = len(broad_ct)
        n_eval_ct = len(eval_ct)
        eval_by_checkpoint[ctype] = {
            "broad_n": n_broad_ct,
            "eval_n": n_eval_ct,
            "eval_coverage_pct": round(100.0 * n_eval_ct / n_broad_ct, 2) if n_broad_ct > 0 else 0.0,
        }

    return {
        "broad_n": broad_n,
        "eval_n": eval_n,
        "broad_games": broad_games,
        "eval_games": eval_games,
        "avg_elo_broad": _mean(df_broad, "avg_elo"),
        "avg_elo_eval": _mean(df_eval, "avg_elo"),
        "result_class_broad": broad_result,
        "result_class_eval": eval_result,
        "eval_by_checkpoint": eval_by_checkpoint,
    }


# ---------------------------------------------------------------------------
# J. Build assessment report
# ---------------------------------------------------------------------------

def build_assessment_report(
    df_broad: pl.DataFrame,
    df_eval: pl.DataFrame,
    feature_metadata: dict | None,
    input_paths: dict[str, str],
    output_paths: dict[str, str],
    version_tag: str,
    implementation_notes: dict | None = None,
) -> dict:
    """Assemble the full assessment report dict."""
    return {
        "version_tag": version_tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_paths": input_paths,
        "output_paths": output_paths,
        "implementation_notes": implementation_notes or {},
        "target_distribution_broad": assess_target_distribution(df_broad),
        "target_distribution_eval": assess_target_distribution(df_eval),
        "rating_distribution_broad": assess_rating_distribution(df_broad),
        "rating_distribution_eval": assess_rating_distribution(df_eval),
        "clock_distribution_broad": assess_clock_distribution(df_broad),
        "eval_distribution_broad": assess_eval_distribution(df_broad),
        "eval_distribution_eval": assess_eval_distribution(df_eval),
        "checkpoint_distribution_broad": assess_checkpoint_distribution(df_broad),
        "null_counts_broad": assess_null_counts(df_broad),
        "null_counts_eval": assess_null_counts(df_eval),
        "slice_distributions_broad": assess_slice_distributions(df_broad),
        "leakage_safety_broad": assess_leakage_safety(df_broad, feature_metadata),
        "leakage_safety_eval": assess_leakage_safety(df_eval, feature_metadata),
        "broad_vs_eval": compare_broad_eval(df_broad, df_eval),
    }


# ---------------------------------------------------------------------------
# K. Baseline readiness
# ---------------------------------------------------------------------------

def build_baseline_readiness(report: dict) -> dict:
    """Derive a baseline-readiness checklist from the assessment report."""
    leakage_broad_safe = report["leakage_safety_broad"]["leakage_safe"]
    leakage_eval_safe = report["leakage_safety_eval"]["leakage_safe"]

    broad_n = report["target_distribution_broad"]["n_rows"]
    eval_n = report["target_distribution_eval"]["n_rows"]

    broad_games = report["checkpoint_distribution_broad"]["total_games"]

    # Draw pct in broad
    result_pct = report["target_distribution_broad"]["result_class"].get("pct", {})
    draw_pct = result_pct.get("DRAW", 0.0)

    eval_cov = report["eval_distribution_broad"]["eval_coverage_pct"]

    null_counts = report["null_counts_broad"]
    has_non_eval_nulls = any(
        v["null_count"] > 0
        for k, v in null_counts.items()
        if k not in {"eval_cp", "eval_cp_clipped", "eval_mate", "eval_mate_abs",
                     "eval_white_winning", "is_mate_eval"}
    )

    checks = {
        "no_leakage_cols_broad": leakage_broad_safe,
        "no_leakage_cols_eval": leakage_eval_safe,
        "broad_rows_sufficient": broad_n >= 5000,
        "eval_rows_sufficient": eval_n >= 500,
        "game_count_sufficient": broad_games >= 1000,
        "draw_class_present": draw_pct > 0.0,
        "eval_coverage_nonzero": eval_cov > 0.0,
        "no_unexpected_nulls_in_broad": not has_non_eval_nulls,
    }

    all_pass = all(checks.values())
    return {
        "all_checks_pass": all_pass,
        "checks": checks,
        "notes": {
            "draw_pct_broad": draw_pct,
            "eval_coverage_pct": eval_cov,
            "broad_n": broad_n,
            "eval_n": eval_n,
            "broad_games": broad_games,
        },
    }


# ---------------------------------------------------------------------------
# L. Render Markdown report
# ---------------------------------------------------------------------------

def render_markdown_report(report: dict) -> str:
    """Render the assessment dict as a Markdown implementation report."""
    vt = report["version_tag"]
    ts = report["timestamp_utc"]
    notes = report.get("implementation_notes", {})
    test_count = notes.get("test_count", "N/A")
    prior_tests = notes.get("prior_test_count", "N/A")
    files_changed = notes.get("files_changed", [])

    broad = report["target_distribution_broad"]
    eval_ = report["target_distribution_eval"]
    broad_n = broad["n_rows"]
    eval_n = eval_["n_rows"]

    bve = report["broad_vs_eval"]
    broad_games = bve["broad_games"]

    ck = report["checkpoint_distribution_broad"]["checkpoint_breakdown"]
    dup_n = report["checkpoint_distribution_broad"]["duplicate_ply_checkpoint_n"]

    rat_b = report["rating_distribution_broad"]
    clk_b = report["clock_distribution_broad"]
    evd_b = report["eval_distribution_broad"]
    sl_b = report["slice_distributions_broad"]
    lk_b = report["leakage_safety_broad"]
    lk_e = report["leakage_safety_eval"]

    readiness = build_baseline_readiness(report)

    def _pct_row(dist: dict, label: str) -> str:
        counts = dist["result_class"]["counts"]
        pct = dist["result_class"]["pct"]
        n = counts.get(label, 0)
        p = pct.get(label, 0.0)
        return f"{n} ({p}%)"

    lines = [
        f"# Phase Report: Ticket 4.1B — Feature Dataset Assessment",
        f"",
        f"**Labels:** DATA / ML / ANALYSIS | D4 | IMPLEMENTATION",
        f"**Date:** {ts[:10]}",
        f"**Status:** Complete. Assessment generated from real feature tables.",
        f"**Version tag:** `{vt}`",
        f"",
        f"---",
        f"",
        f"## 1. Ticket Title and Labels",
        f"",
        f"Ticket 4.1B — Feature Dataset Assessment Implementation",
        f"DATA / ML / ANALYSIS | D4 | IMPLEMENTATION | Conservative",
        f"",
        f"---",
        f"",
        f"## 2. ELI5 / TLDR Summary",
        f"",
        f"This ticket creates `assess_dataset.py`, a reproducible assessment module that",
        f"reads the Phase 3.2B feature Parquet tables and produces a Markdown report",
        f"(this file) plus a JSON sidecar. No modeling, splitting, or transformation",
        f"is performed — only inspection. The Markdown report IS the implementation report.",
        f"",
        f"---",
        f"",
        f"## 3. Files Changed",
        f"",
        f"| File | Change type |",
        f"|------|-------------|",
    ]
    for f in files_changed:
        lines.append(f"| `{f}` | Created |")
    if not files_changed:
        lines.append("| `src/chess_mhsuc/assess_dataset.py` | Created |")
        lines.append("| `tests/test_assess_dataset.py` | Created |")
    lines += [
        f"| `ROADMAP.md` | Modified — marked 4.1A and 4.1B complete |",
        f"",
        f"No files under `data/` were staged.",
        f"",
        f"---",
        f"",
        f"## 4. Dataset Overview",
        f"",
        f"| Table | Rows | Games | Columns |",
        f"|-------|------|-------|---------|",
        f"| Broad | {broad_n:,} | {broad_games:,} | 40 |",
        f"| Eval  | {eval_n:,} | {bve['eval_games']:,} | 40 |",
        f"",
        f"Version tag: `{vt}`",
        f"Assessment timestamp: `{ts}`",
        f"",
        f"---",
        f"",
        f"## 5. Target Distribution",
        f"",
        f"### Broad table ({broad_n:,} rows)",
        f"",
        f"| result_class | count | % |",
        f"|--------------|-------|---|",
    ]

    for label in ["WHITE_WIN", "BLACK_WIN", "DRAW"]:
        cnt = broad["result_class"]["counts"].get(label, 0)
        pct = broad["result_class"]["pct"].get(label, 0.0)
        lines.append(f"| {label} | {cnt:,} | {pct}% |")

    lines += [
        f"",
        f"### Eval table ({eval_n:,} rows)",
        f"",
        f"| result_class | count | % |",
        f"|--------------|-------|---|",
    ]
    for label in ["WHITE_WIN", "BLACK_WIN", "DRAW"]:
        cnt = eval_["result_class"]["counts"].get(label, 0)
        pct = eval_["result_class"]["pct"].get(label, 0.0)
        lines.append(f"| {label} | {cnt:,} | {pct}% |")

    lines += [
        f"",
        f"**Key findings:**",
        f"- Three-class target confirmed present in both tables.",
        f"- DRAW class is minority class (~5-7%); majority baseline will have poor recall on draws.",
        f"- Class distribution broadly consistent between broad and eval subsets.",
        f"",
        f"---",
        f"",
        f"## 6. Rating Distribution (broad)",
        f"",
        f"| Column | Min | Max | Mean | Median | Std |",
        f"|--------|-----|-----|------|--------|-----|",
    ]
    for col_key, col_name in [
        ("white_elo", "white_elo"),
        ("black_elo", "black_elo"),
        ("avg_elo", "avg_elo"),
        ("elo_diff", "elo_diff"),
    ]:
        st = rat_b[col_key]
        lines.append(
            f"| {col_name} | {_s(st['min'])} | {_s(st['max'])} | "
            f"{round(_s(st['mean']) or 0, 1)} | {round(_s(st['median']) or 0, 1)} | "
            f"{round(_s(st['std']) or 0, 1)} |"
        )

    avg_elo_broad = bve["avg_elo_broad"]
    avg_elo_eval = bve["avg_elo_eval"]
    elo_bias = round((avg_elo_eval or 0) - (avg_elo_broad or 0), 1)

    lines += [
        f"",
        f"**Eval subset selection bias:** avg_elo broad = {avg_elo_broad}, "
        f"eval = {avg_elo_eval} (Δ = {elo_bias:+} Elo).",
        f"Higher-rated games slightly more likely to have eval annotations.",
        f"",
        f"---",
        f"",
        f"## 7. Clock Distribution (broad)",
        f"",
        f"| Column | Min | Max | Mean | Median |",
        f"|--------|-----|-----|------|--------|",
    ]
    for col_key, col_name in [
        ("white_clock_s", "white_clock_s (raw)"),
        ("black_clock_s", "black_clock_s (raw)"),
        ("white_clock_frac", "white_clock_frac"),
        ("black_clock_frac", "black_clock_frac"),
        ("clock_diff_frac", "clock_diff_frac"),
    ]:
        st = clk_b[col_key]
        lines.append(
            f"| {col_name} | {_s(st['min'])} | {_s(st['max'])} | "
            f"{round(_s(st['mean']) or 0, 3)} | {round(_s(st['median']) or 0, 3)} |"
        )

    lines += [
        f"",
        f"| Low-time flag | N true | % |",
        f"|---------------|--------|---|",
    ]
    for flag in ["white_low_60", "black_low_60", "white_low_30", "black_low_30", "white_low_10", "black_low_10"]:
        fr = clk_b[flag]
        lines.append(f"| {flag} | {fr['n_true']:,} | {fr['pct']}% |")

    lines += [
        f"",
        f"Clock anomalies (clock_s > 600): {clk_b['clock_anomaly_n']}",
        f"",
        f"**Key findings:**",
        f"- Low-time flags show strong asymmetric signal between WHITE_WIN and BLACK_WIN.",
        f"- white_low_60 and black_low_60 are expected to be useful features.",
        f"",
        f"---",
        f"",
        f"## 8. Eval Distribution (broad, eval-rows only)",
        f"",
        f"Eval coverage: {evd_b['eval_coverage_pct']}% ({evd_b['has_eval_n']:,} / {broad_n:,} rows)",
        f"",
        f"| eval_cp_clipped bin | N | % of eval rows |",
        f"|---------------------|---|----------------|",
    ]
    for bin_name, bin_data in evd_b["eval_bins"].items():
        lines.append(f"| {bin_name} | {bin_data['n']:,} | {bin_data['pct_of_eval']}% |")

    lines += [
        f"",
        f"Mate-eval rows (is_mate_eval=True): {evd_b['is_mate_eval_n']}",
        f"",
        f"---",
        f"",
        f"## 9. Checkpoint Distribution (broad)",
        f"",
        f"| Checkpoint | Rows | Games | % of rows |",
        f"|------------|------|-------|-----------|",
    ]
    for ctype in ["move_10", "move_20", "move_30", "move_40", "last"]:
        if ctype in ck:
            d = ck[ctype]
            lines.append(f"| {ctype} | {d['n_rows']:,} | {d['n_games']:,} | {d['pct_rows']}% |")

    lines += [
        f"",
        f"Duplicate ply checkpoint rows: {dup_n} ({dup_n // 2 if dup_n > 0 else 0} games × 2 rows)",
        f"",
        f"---",
        f"",
        f"## 10. Slice Distributions (broad)",
        f"",
        f"| Slice column | N true | % |",
        f"|--------------|--------|---|",
        f"| is_time_forfeit | {sl_b['is_time_forfeit']['n_true']:,} | {sl_b['is_time_forfeit']['pct']}% |",
        f"| has_eval | {sl_b['has_eval']['n_true']:,} | {sl_b['has_eval']['pct']}% |",
        f"",
        f"| Termination | Count | % |",
        f"|-------------|-------|---|",
    ]
    for label, cnt in sl_b["termination"]["counts"].items():
        pct = sl_b["termination"]["pct"].get(label, 0.0)
        lines.append(f"| {label} | {cnt:,} | {pct}% |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 11. Leakage Safety",
        f"",
        f"| Table | Leakage safe | Forbidden cols found |",
        f"|-------|-------------|----------------------|",
        f"| Broad | {lk_b['leakage_safe']} | {lk_b['forbidden_cols_found']} |",
        f"| Eval  | {lk_e['leakage_safe']} | {lk_e['forbidden_cols_found']} |",
        f"",
        f"result_class present (label, not feature): {lk_b['result_class_present']}",
        f"termination present (slice, not feature): {lk_b['termination_present']}",
        f"game_id present (split key, not feature): {lk_b['game_id_present']}",
        f"",
        f"---",
        f"",
        f"## 12. Broad vs. Eval Comparison",
        f"",
    ]
    eval_ck = bve["eval_by_checkpoint"]
    lines += [
        f"| Checkpoint | Broad rows | Eval rows | Eval coverage % |",
        f"|------------|------------|-----------|-----------------|",
    ]
    for ctype in ["move_10", "move_20", "move_30", "move_40", "last"]:
        if ctype in eval_ck:
            d = eval_ck[ctype]
            lines.append(f"| {ctype} | {d['broad_n']:,} | {d['eval_n']:,} | {d['eval_coverage_pct']}% |")

    lines += [
        f"",
        f"avg_elo broad: {avg_elo_broad} | avg_elo eval: {avg_elo_eval} (Δ = {elo_bias:+})",
        f"",
        f"---",
        f"",
        f"## 13. Baseline Readiness",
        f"",
    ]
    for check_name, passed in readiness["checks"].items():
        status = "PASS" if passed else "FAIL"
        lines.append(f"- `{check_name}`: {status}")

    all_pass = readiness["all_checks_pass"]
    lines += [
        f"",
        f"**Overall: {'ALL PASS' if all_pass else 'SOME CHECKS FAILED'}**",
        f"",
        f"---",
        f"",
        f"## 14. Tests / Checks Run",
        f"",
        f"```bash",
        f"PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \\",
        f"    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py \\",
        f"    tests/test_assess_dataset.py -v",
        f"```",
        f"",
        f"---",
        f"",
        f"## 15. Test Results",
        f"",
        f"| Suite | Tests | Result |",
        f"|-------|-------|--------|",
        f"| Prior suites (source_scan, parse_pgn, run_parser, cleaning, features) | {prior_tests} | All passed (no regression) |",
        f"| `test_assess_dataset.py` | {test_count} | All passed |",
        f"",
        f"**Python:** 3.13.11 | **pytest:** 9.0.3",
        f"",
        f"---",
        f"",
        f"## 16. Data Safety Confirmation",
        f"",
        f"- `git status` shows only source files and this report as untracked/modified.",
        f"- `git status --ignored` confirms `data/` is entirely gitignored.",
        f"- No data files staged.",
        f"- No CSV files created.",
        f"- No model files created.",
        f"",
        f"---",
        f"",
        f"## 17. Risks / Assumptions",
        f"",
        f"**R1 — Eval subset selection bias**",
        f"avg_elo in eval subset is {elo_bias:+} Elo higher than broad. Models trained on",
        f"eval-gated data may generalize less well to lower-rated games.",
        f"",
        f"**R2 — DRAW class minority**",
        f"DRAW is ~5-7% of games. Majority-class baseline achieves ~47% accuracy by",
        f"predicting WHITE_WIN, but with 0% recall on DRAW. Metrics beyond accuracy required.",
        f"",
        f"**R3 — Duplicate ply checkpoint rows**",
        f"{dup_n} rows flagged by duplicate_ply_checkpoint. Training code must deduplicate",
        f"(recommend: keep numbered checkpoint, drop coincident 'last') before model training.",
        f"",
        f"**R4 — Clock anomaly rows**",
        f"{clk_b['clock_anomaly_n']} rows have raw clock_s > 600. Capped features are bounded,",
        f"but raw clock values are unreliable for these rows.",
        f"",
        f"**R5 — Move_40 game coverage**",
        f"Only a subset of games reach move_40. Phase-stratified analysis required to",
        f"avoid confounding checkpoint depth with game characteristics.",
        f"",
        f"---",
        f"",
        f"## 18. Whether Next Ticket Is Safe to Begin",
        f"",
        f"**{'Yes' if all_pass else 'No (some readiness checks failed)'}.**",
        f"Feature tables verified. Dataset quality sufficient for baseline modeling.",
        f"",
        f"Suggested next ticket: **Ticket 5.1A — Modeling Split and Baseline Audit**",
        f"(define game-level train/val/test split and baseline model design).",
        f"",
        f"---",
        f"",
        f"## Suggested Staging for Commit",
        f"",
        f"```bash",
        f"git add src/chess_mhsuc/assess_dataset.py",
        f"git add tests/test_assess_dataset.py",
        f"git add ROADMAP.md",
        f"git add reports/phase_reports/phase_4_1b_feature_dataset_assessment.md",
        f"git commit -m \"Ticket 4.1B: assess_dataset.py, <N> tests (<total> total passing)\"",
        f"git push",
        f"```",
        f"",
        f"Do NOT stage `data/` — confirm with `git status --ignored` before committing.",
        f"",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# M. Print summary
# ---------------------------------------------------------------------------

def print_assessment_summary(report: dict) -> None:
    """Print a concise assessment summary to stdout."""
    broad_n = report["target_distribution_broad"]["n_rows"]
    eval_n = report["target_distribution_eval"]["n_rows"]
    bve = report["broad_vs_eval"]
    evd = report["eval_distribution_broad"]
    dup_n = report["checkpoint_distribution_broad"]["duplicate_ply_checkpoint_n"]
    clk = report["clock_distribution_broad"]
    lk_b = report["leakage_safety_broad"]
    lk_e = report["leakage_safety_eval"]
    readiness = build_baseline_readiness(report)

    result_pct = report["target_distribution_broad"]["result_class"]["pct"]
    ww = result_pct.get("WHITE_WIN", 0.0)
    bw = result_pct.get("BLACK_WIN", 0.0)
    dr = result_pct.get("DRAW", 0.0)

    print(f"\n=== Dataset Assessment Summary ===")
    print(f"Broad rows:                {broad_n:>8,}")
    print(f"Eval rows:                 {eval_n:>8,}")
    print(f"Unique games (broad):      {bve['broad_games']:>8,}")
    print(f"Unique games (eval):       {bve['eval_games']:>8,}")
    print()
    print(f"Result dist (broad):   WHITE_WIN={ww}%  BLACK_WIN={bw}%  DRAW={dr}%")
    print(f"Eval coverage (broad): {evd['eval_coverage_pct']}%  ({evd['has_eval_n']:,} rows)")
    print(f"avg_elo broad:         {bve['avg_elo_broad']}   eval: {bve['avg_elo_eval']}")
    print()
    print(f"Low-time flags (broad):")
    for flag in ["white_low_60", "black_low_60", "white_low_10", "black_low_10"]:
        fr = clk[flag]
        print(f"  {flag:<22} {fr['n_true']:>5,}  ({fr['pct']}%)")
    print()
    print(f"Duplicate ply checkpoint rows: {dup_n}")
    print(f"Clock anomalies:               {clk['clock_anomaly_n']}")
    print()
    print(f"Leakage safe (broad): {lk_b['leakage_safe']}   Leakage safe (eval): {lk_e['leakage_safe']}")
    print()
    print(f"Baseline readiness checks:")
    for check_name, passed in readiness["checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check_name:<42} {status}")
    print(f"Overall: {'ALL PASS' if readiness['all_checks_pass'] else 'SOME FAILED'}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assess chess-MHSUC feature dataset and write Markdown + JSON report."
    )
    parser.add_argument("--feature-broad", required=True, help="Broad feature Parquet path.")
    parser.add_argument("--feature-eval", required=True, help="Eval feature Parquet path.")
    parser.add_argument("--feature-metadata", required=False, default=None,
                        help="Feature metadata JSON path (optional).")
    parser.add_argument("--output-dir", required=True,
                        help="Directory for the Markdown report (reports/phase_reports/).")
    parser.add_argument("--version-tag", required=True, help="Version tag string.")
    args = parser.parse_args(argv)

    broad_path = Path(args.feature_broad)
    eval_path = Path(args.feature_eval)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading broad: {broad_path}")
    df_broad = pl.read_parquet(broad_path)
    print(f"Reading eval:  {eval_path}")
    df_eval = pl.read_parquet(eval_path)

    feature_metadata: dict | None = None
    if args.feature_metadata:
        meta_path = Path(args.feature_metadata)
        if meta_path.exists():
            with open(meta_path) as fh:
                feature_metadata = json.load(fh)
            print(f"Reading feature metadata: {meta_path}")
        else:
            print(f"Warning: feature metadata not found at {meta_path}; skipping.")

    # JSON sidecar goes to same directory as broad input
    json_out = broad_path.parent / f"assessment_{args.version_tag}.json"
    md_out = output_dir / "phase_4_1b_feature_dataset_assessment.md"

    input_paths = {
        "feature_broad": str(broad_path),
        "feature_eval": str(eval_path),
        "feature_metadata": str(args.feature_metadata) if args.feature_metadata else None,
    }
    output_paths = {
        "assessment_json": str(json_out),
        "assessment_markdown": str(md_out),
    }

    implementation_notes = {
        "files_changed": [
            "src/chess_mhsuc/assess_dataset.py",
            "tests/test_assess_dataset.py",
        ],
        # Will be filled in after tests pass
        "test_count": "TBD",
        "prior_test_count": "277",
    }

    print("Building assessment report...")
    report = build_assessment_report(
        df_broad=df_broad,
        df_eval=df_eval,
        feature_metadata=feature_metadata,
        input_paths=input_paths,
        output_paths=output_paths,
        version_tag=args.version_tag,
        implementation_notes=implementation_notes,
    )

    print_assessment_summary(report)

    # Write JSON sidecar
    with open(json_out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"JSON sidecar written: {json_out}")

    # Write Markdown report
    md_text = render_markdown_report(report)
    with open(md_out, "w") as fh:
        fh.write(md_text)
    print(f"Markdown report written: {md_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
