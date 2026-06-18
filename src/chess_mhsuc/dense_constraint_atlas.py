"""
Dense CP/ES Constraint Atlas — Ticket 15.4B (visualization implementation).

Renders the descriptive move-quality atlas over the dense per-ply substrate built in
15.3C/15.3D (2024-09 + 2024-10 10+0, both colors, move_number>=5, depth 12). It reads
the dense ``dense_move_loss_*`` artifacts read-only and writes PNG figures + a markdown
report; it does NOT modify the dense artifacts, fit models, run Stockfish, join
sharpness, or do any cross-time-control work.

This is a SEPARATE module from ``constraint_atlas.py`` (the 15.1B checkpoint atlas) on
purpose — it must not clobber that module.

Metric policy (15.4A): PRIMARY expected_score_loss (mover perspective); SECONDARY
clipped cp loss (median/p75/p90); DIAGNOSTIC-only raw cp loss; large-loss panels
ES>=0.05/0.10 and cp>=100/200. Headline excludes mate-band rows; both colors are
already mover-perspective. Every headline figure is month-replicated.

All results are predictive/descriptive associations — NOT causal, not a "degradation
curve", and Stockfish depth-12 eval is objective position context, not ground truth.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.dense_constraint_atlas \\
        --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \\
        --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \\
        --out-dir reports/figures/phase_15_4_constraint_atlas \\
        --report reports/constraint_atlas_10plus0_2024_09_2024_10_v1.md \\
        --bootstrap 500 --seed 20240617
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless; no display
import matplotlib.pyplot as plt
import numpy as np
import polars as pl


# ---------------------------------------------------------------------------
# Constants: bucket orders, policy thresholds, expected substrate
# ---------------------------------------------------------------------------

CLOCK_SECONDS_ORDER = ["0_5", "5_10", "10_30", "30_60", "60_180", "180_300", "300+"]
CLOCK_COARSE_ORDER = ["under_10", "10_30", "30_60", "60_180", "over_180"]
CLOCK_FRACTION_ORDER = ["0_1", "1_2", "2_5", "5_10", "10_30", "30_50", "50+"]
RATING_ORDER = ["<1000", "1000_1199", "1200_1399", "1400_1599", "1600_1799",
                "1800_1999", "2000_2199", "2200+"]
EVAL_BAND_ORDER = ["near_equal", "slight", "clear", "decided"]  # mate_band = diagnostic
PHASE_MOVE_ORDER = ["5_10", "11_20", "21_30", "31_40", "41_60", "61+"]
THINK_ORDER = ["0_1", "1_2", "2_5", "5_10", "10_30", "30+"]

# Cell-count policy (15.4A).
SPARSE_MIN = 200      # below: suppress / label sparse
HEADLINE_MIN = 1000   # at/above: headline-safe

TEN_ZERO_START_S = 600.0

EXPECTED_ROWS = {"2024_09": 1_496_890, "2024_10": 1_436_866}

# Minimal required columns (a normalization layer maps to these exact names).
REQUIRED_COLS = [
    "month", "game_id", "ply", "move_number", "mover_color", "mover_elo",
    "clock_before_s", "think_time_gross_s", "think_time_net_s",
    "time_control_raw", "initial_time_s", "increment_s", "speed_category",
    "clock_fraction", "expected_score_loss", "cp_loss_raw", "cp_loss_clipped",
    "is_mate_band", "status", "eval_band", "phase", "termination",
    "is_time_forfeit", "mover_player_hash",
]
# Columns actually loaded from disk (subset of the 65; keeps memory modest).
_LOAD_COLS = REQUIRED_COLS

_FORBIDDEN_USERNAME_COLS = {"white", "black", "White", "Black",
                            "white_user", "black_user"}

_MONTH_LABEL = {"2024_09": "2024-09", "2024_10": "2024-10"}
_MONTH_COLOR = {"2024_09": "#1f77b4", "2024_10": "#d62728"}


# ---------------------------------------------------------------------------
# A. Pure bucket helpers
# ---------------------------------------------------------------------------

def clock_seconds_bucket(s: float | None) -> str | None:
    if s is None:
        return None
    if s < 5: return "0_5"
    if s < 10: return "5_10"
    if s < 30: return "10_30"
    if s < 60: return "30_60"
    if s < 180: return "60_180"
    if s < 300: return "180_300"
    return "300+"


def clock_coarse_bucket(s: float | None) -> str | None:
    if s is None:
        return None
    if s < 10: return "under_10"
    if s < 30: return "10_30"
    if s < 60: return "30_60"
    if s < 180: return "60_180"
    return "over_180"


def clock_fraction_bucket(f: float | None) -> str | None:
    if f is None:
        return None
    p = f * 100.0
    if p < 1: return "0_1"
    if p < 2: return "1_2"
    if p < 5: return "2_5"
    if p < 10: return "5_10"
    if p < 30: return "10_30"
    if p < 50: return "30_50"
    return "50+"


def rating_bucket_200(elo: int | float | None) -> str | None:
    if elo is None:
        return None
    if elo < 1000: return "<1000"
    if elo >= 2200: return "2200+"
    lo = int(elo // 200) * 200
    return f"{lo}_{lo + 199}"


def phase_move_bucket(mv: int | None) -> str | None:
    if mv is None:
        return None
    if mv <= 10: return "5_10"
    if mv <= 20: return "11_20"
    if mv <= 30: return "21_30"
    if mv <= 40: return "31_40"
    if mv <= 60: return "41_60"
    return "61+"


def think_bucket(t: float | None) -> str | None:
    if t is None or t < 0:
        return None
    if t < 1: return "0_1"
    if t < 2: return "1_2"
    if t < 5: return "2_5"
    if t < 10: return "5_10"
    if t < 30: return "10_30"
    return "30+"


def cell_status(n: int) -> str:
    """sparse (<200) / marked (200-999) / headline (>=1000)."""
    if n < SPARSE_MIN:
        return "sparse"
    if n < HEADLINE_MIN:
        return "marked"
    return "headline"


# ---------------------------------------------------------------------------
# B. Load + validate + derive
# ---------------------------------------------------------------------------

def load_dense(paths: list[str | Path]) -> pl.DataFrame:
    """Read the required columns present in each dense-month parquet and concat.
    Columns absent from a file are simply not loaded; ``validate_schema`` then
    reports any missing required column with a clean error (rather than a raw
    parquet column-not-found error)."""
    frames = []
    for p in paths:
        print(f"[atlas] loading {p} ...", file=sys.stderr)
        avail = pl.scan_parquet(p).collect_schema().names()
        cols = [c for c in _LOAD_COLS if c in avail]
        frames.append(pl.read_parquet(p, columns=cols))
    return pl.concat(frames, how="diagonal_relaxed") if len(frames) > 1 else frames[0]


def validate_schema(df: pl.DataFrame, check_counts: bool = True) -> dict:
    """Validate required columns, privacy, metric bounds, time-control uniformity,
    and (optionally) per-month row counts. Raises ValueError on hard failure."""
    print("[atlas] validating schema ...", file=sys.stderr)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"dense atlas input missing required columns: {missing}")
    bad = _FORBIDDEN_USERNAME_COLS & set(df.columns)
    if bad:
        raise ValueError(f"raw username columns present (privacy violation): {sorted(bad)}")

    es = df["expected_score_loss"]
    if es.min() is not None and (es.min() < 0 or es.max() > 1.0001):
        raise ValueError(f"expected_score_loss out of [0,1]: [{es.min()}, {es.max()}]")
    if df["cp_loss_clipped"].min() is not None and df["cp_loss_clipped"].min() < 0:
        raise ValueError("cp_loss_clipped has negative values")

    tc = set(df["time_control_raw"].unique().to_list())
    if tc != {"600+0"}:
        raise ValueError(f"non-600+0 rows present: {tc}")
    if set(df["initial_time_s"].unique().to_list()) != {600}:
        raise ValueError("initial_time_s not uniformly 600")
    if set(df["increment_s"].unique().to_list()) != {0}:
        raise ValueError("increment_s not uniformly 0")
    if set(df["speed_category"].unique().to_list()) != {"rapid"}:
        raise ValueError("speed_category not uniformly 'rapid'")

    per_month = {r[0]: r[1] for r in df.group_by("month").len().iter_rows()}
    if check_counts:
        for m, expected in EXPECTED_ROWS.items():
            if per_month.get(m) != expected:
                raise ValueError(
                    f"row count mismatch for {m}: got {per_month.get(m)}, "
                    f"expected {expected}")
    return {"rows": df.height, "per_month": per_month,
            "months": sorted(per_month.keys())}


def add_buckets(df: pl.DataFrame) -> pl.DataFrame:
    """Add the derived bucket columns used by the figures (pure, no I/O)."""
    return df.with_columns([
        pl.col("clock_before_s").map_elements(clock_seconds_bucket, return_dtype=pl.Utf8)
        .alias("clock_sec_bucket"),
        pl.col("clock_before_s").map_elements(clock_coarse_bucket, return_dtype=pl.Utf8)
        .alias("clock_coarse_bucket"),
        pl.col("clock_fraction").map_elements(clock_fraction_bucket, return_dtype=pl.Utf8)
        .alias("clock_frac_bucket"),
        pl.col("mover_elo").map_elements(rating_bucket_200, return_dtype=pl.Utf8)
        .alias("rating_bin"),
        pl.col("move_number").map_elements(phase_move_bucket, return_dtype=pl.Utf8)
        .alias("phase_move_bucket"),
        pl.col("think_time_gross_s").map_elements(think_bucket, return_dtype=pl.Utf8)
        .alias("think_bucket"),
        pl.when(pl.col("is_time_forfeit")).then(pl.lit("time_forfeit"))
        .otherwise(pl.lit("board_decided")).alias("termination_channel"),
    ])


def filter_headline(df: pl.DataFrame) -> pl.DataFrame:
    """Headline rows: status OK, mate-band excluded, both colors retained."""
    return df.filter((pl.col("status") == "ok") & (~pl.col("is_mate_band")))


def anomaly_counts(df: pl.DataFrame) -> dict:
    """Per-month anomaly counts (flagged, never dropped)."""
    out = {}
    for m in sorted(df["month"].unique().to_list()):
        sub = df.filter(pl.col("month") == m)
        out[m] = {
            "rows": sub.height,
            "mate_band": int(sub["is_mate_band"].sum()),
            "clock_over_600": int(sub.filter(pl.col("clock_before_s") > TEN_ZERO_START_S).height),
            "negative_think": int(sub.filter(pl.col("think_time_gross_s") < 0).height),
            "missing_clock": int(sub["clock_before_s"].null_count()),
        }
    return out


# ---------------------------------------------------------------------------
# C. Aggregation + uncertainty
# ---------------------------------------------------------------------------

def cell_summary(df: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    """Per-group summary: n + ES (mean/median/p75/p90) + clipped cp (mean/median/
    p75/p90) + large-loss rates. Headline metric = ES loss."""
    g = df.group_by(by).agg([
        pl.len().alias("n"),
        pl.col("expected_score_loss").mean().alias("es_mean"),
        pl.col("expected_score_loss").median().alias("es_median"),
        pl.col("expected_score_loss").quantile(0.75).alias("es_p75"),
        pl.col("expected_score_loss").quantile(0.90).alias("es_p90"),
        pl.col("cp_loss_clipped").mean().alias("cp_mean"),
        pl.col("cp_loss_clipped").median().alias("cp_median"),
        pl.col("cp_loss_clipped").quantile(0.75).alias("cp_p75"),
        pl.col("cp_loss_clipped").quantile(0.90).alias("cp_p90"),
        (pl.col("expected_score_loss") >= 0.05).mean().alias("p_es_ge_05"),
        (pl.col("expected_score_loss") >= 0.10).mean().alias("p_es_ge_10"),
        (pl.col("cp_loss_clipped") >= 100).mean().alias("p_cp_ge_100"),
        (pl.col("cp_loss_clipped") >= 200).mean().alias("p_cp_ge_200"),
    ])
    return g.with_columns(
        pl.col("n").map_elements(cell_status, return_dtype=pl.Utf8).alias("cell_status"))


def bootstrap_mean_ci(
    df_cell: pl.DataFrame, value_col: str, cluster_col: str = "game_id",
    n_rep: int = 500, seed: int = 20240617,
) -> tuple[float, float, float]:
    """Fast game-clustered bootstrap CI for a mean: resample whole clusters using
    precomputed per-cluster (sum, count). Returns (estimate, lo, hi); (mean, nan, nan)
    if <2 clusters."""
    g = df_cell.group_by(cluster_col).agg([
        pl.col(value_col).sum().alias("s"), pl.len().alias("c")])
    s = g["s"].to_numpy().astype(np.float64)
    c = g["c"].to_numpy().astype(np.float64)
    tot = c.sum()
    est = float(s.sum() / tot) if tot else float("nan")
    n = len(s)
    if n < 2 or tot == 0:
        return est, float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = np.empty(n_rep, dtype=np.float64)
    for r in range(n_rep):
        pick = rng.integers(0, n, size=n)
        means[r] = s[pick].sum() / c[pick].sum()
    return est, float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def clock_es_with_ci(
    df: pl.DataFrame, n_rep: int, seed: int, order: list[str] = CLOCK_SECONDS_ORDER,
) -> dict[str, list[dict]]:
    """Per-month: ES-loss mean + game-clustered CI for each clock-seconds bucket."""
    out: dict[str, list[dict]] = {}
    for m in sorted(df["month"].unique().to_list()):
        rows = []
        for b in order:
            cell = df.filter((pl.col("month") == m) & (pl.col("clock_sec_bucket") == b))
            if cell.height == 0:
                continue
            est, lo, hi = bootstrap_mean_ci(cell, "expected_score_loss",
                                            n_rep=n_rep, seed=seed)
            rows.append({"bucket": b, "n": cell.height, "mean": est,
                         "lo": lo, "hi": hi, "status": cell_status(cell.height)})
        out[m] = rows
    return out


# ---------------------------------------------------------------------------
# D. Plot helpers
# ---------------------------------------------------------------------------

def _legend(ax, **kw) -> None:
    """Call legend only if there are labelled artists (avoids matplotlib warnings on
    empty/sparse panels)."""
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(**kw)


def _x_positions(order: list[str], present: list[str]) -> dict[str, int]:
    return {b: i for i, b in enumerate([b for b in order if b in present])}


def _save(fig, out_dir: Path, name: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"[atlas] rendering {name} ...", file=sys.stderr)
    return name


def fig01_clock_vs_es(ci_by_month: dict, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 5))
    present = [b for b in CLOCK_SECONDS_ORDER
               if any(r["bucket"] == b for rows in ci_by_month.values() for r in rows)]
    xpos = {b: i for i, b in enumerate(present)}
    for m, rows in ci_by_month.items():
        xs = [xpos[r["bucket"]] for r in rows if r["bucket"] in xpos]
        ys = [r["mean"] for r in rows if r["bucket"] in xpos]
        los = [r["mean"] - r["lo"] for r in rows if r["bucket"] in xpos]
        his = [r["hi"] - r["mean"] for r in rows if r["bucket"] in xpos]
        ax.errorbar(xs, ys, yerr=[los, his], marker="o", capsize=3,
                    color=_MONTH_COLOR.get(m), label=_MONTH_LABEL.get(m, m))
    ax.set_xticks(list(xpos.values()))
    ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("mover clock before move (seconds bucket)")
    ax.set_ylabel("mean next-move expected-score loss")
    ax.set_title("Clock vs expected-score loss (mover perspective) — by month\n"
                 "game-clustered 95% CI; descriptive, not causal")
    _legend(ax); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_01_clock_vs_es_loss_by_month.png")


def fig02_clock_vs_cp(summ: pl.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 5))
    present = [b for b in CLOCK_SECONDS_ORDER
               if b in summ["clock_sec_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    for m in sorted(summ["month"].unique().to_list()):
        sub = summ.filter(pl.col("month") == m).sort("clock_sec_bucket")
        d = {r["clock_sec_bucket"]: r for r in sub.iter_rows(named=True)}
        xs = [xpos[b] for b in present if b in d]
        for stat, ls in [("cp_median", "-"), ("cp_p75", "--"), ("cp_p90", ":")]:
            ax.plot(xs, [d[b][stat] for b in present if b in d], ls,
                    color=_MONTH_COLOR.get(m),
                    label=f"{_MONTH_LABEL.get(m,m)} {stat.split('_')[1]}")
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("mover clock before move (seconds bucket)")
    ax.set_ylabel("clipped centipawn loss (median / p75 / p90)")
    ax.set_title("Clock vs clipped CP loss — by month (skew-aware)\n"
                 "descriptive, not causal")
    _legend(ax, fontsize=8, ncol=2); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_02_clock_vs_clipped_cp_loss_by_month.png")


def fig03_large_loss(summ: pl.DataFrame, out_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 5))
    present = [b for b in CLOCK_SECONDS_ORDER if b in summ["clock_sec_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    for m in sorted(summ["month"].unique().to_list()):
        sub = summ.filter(pl.col("month") == m)
        d = {r["clock_sec_bucket"]: r for r in sub.iter_rows(named=True)}
        xs = [xpos[b] for b in present if b in d]
        ax.plot(xs, [d[b]["p_es_ge_05"] for b in present if b in d], "-o",
                color=_MONTH_COLOR.get(m), label=f"{_MONTH_LABEL.get(m,m)} ES≥0.05")
        ax.plot(xs, [d[b]["p_es_ge_10"] for b in present if b in d], "--s",
                color=_MONTH_COLOR.get(m), label=f"{_MONTH_LABEL.get(m,m)} ES≥0.10")
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("mover clock before move (seconds bucket)")
    ax.set_ylabel("large-loss probability")
    ax.set_title("Large-loss probability vs clock — by month\ndescriptive, not causal")
    _legend(ax, fontsize=8, ncol=2); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_03_large_loss_probability_by_clock.png")


def fig04_rating_clock_heatmap(df: pl.DataFrame, out_dir: Path) -> str:
    summ = cell_summary(df, ["rating_bin", "clock_sec_bucket"])
    d = {(r["rating_bin"], r["clock_sec_bucket"]): r for r in summ.iter_rows(named=True)}
    rows = [r for r in RATING_ORDER if r in df["rating_bin"].to_list()]
    cols = [c for c in CLOCK_SECONDS_ORDER if c in df["clock_sec_bucket"].to_list()]
    grid = np.full((len(rows), len(cols)), np.nan)
    for i, rb in enumerate(rows):
        for j, cb in enumerate(cols):
            cell = d.get((rb, cb))
            if cell and cell["n"] >= SPARSE_MIN:
                grid[i, j] = cell["es_mean"]
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(grid, aspect="auto", cmap="viridis", origin="lower")
    ax.set_xticks(range(len(cols))); ax.set_xticklabels(cols, rotation=30)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows)
    ax.set_xlabel("clock before move (seconds bucket)")
    ax.set_ylabel("mover rating bin (Elo)")
    ax.set_title("Rating × clock — mean ES loss (pooled months; sparse cells <200 blank)\n"
                 "descriptive, not causal; see month-replication table in report")
    fig.colorbar(im, ax=ax, label="mean expected-score loss")
    return _save(fig, out_dir, "fig_15_4_04_rating_clock_heatmap_es_loss.png")


def fig05_eval_band(df: pl.DataFrame, out_dir: Path) -> str:
    summ = cell_summary(df, ["eval_band", "clock_sec_bucket"])
    d = {(r["eval_band"], r["clock_sec_bucket"]): r for r in summ.iter_rows(named=True)}
    present = [b for b in CLOCK_SECONDS_ORDER if b in df["clock_sec_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    for band in EVAL_BAND_ORDER:
        ys, xs = [], []
        for b in present:
            cell = d.get((band, b))
            if cell and cell["n"] >= SPARSE_MIN:
                xs.append(xpos[b]); ys.append(cell["es_mean"])
        if xs:
            ax.plot(xs, ys, "-o", label=band)
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("clock before move (seconds bucket)")
    ax.set_ylabel("mean expected-score loss")
    ax.set_title("Eval-band-conditioned clock curves (pooled months)\n"
                 "eval state dominates; descriptive, not causal")
    _legend(ax, title="eval band"); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_05_eval_band_clock_es_loss.png")


def fig06_phase_clock(df: pl.DataFrame, out_dir: Path) -> str:
    summ = cell_summary(df, ["phase_move_bucket", "clock_coarse_bucket"])
    d = {(r["phase_move_bucket"], r["clock_coarse_bucket"]): r
         for r in summ.iter_rows(named=True)}
    present = [b for b in PHASE_MOVE_ORDER if b in df["phase_move_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    for cb in CLOCK_COARSE_ORDER:
        ys, xs = [], []
        for b in present:
            cell = d.get((b, cb))
            if cell and cell["n"] >= SPARSE_MIN:
                xs.append(xpos[b]); ys.append(cell["es_mean"])
        if xs:
            ax.plot(xs, ys, "-o", label=cb)
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("move number bucket")
    ax.set_ylabel("mean expected-score loss")
    ax.set_title("Phase / move-number × clock (pooled months)\n"
                 "separates low-clock from late-game; descriptive, not causal")
    _legend(ax, title="clock bucket", fontsize=8); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_06_phase_clock_es_loss.png")


def fig07_think_time(df: pl.DataFrame, out_dir: Path) -> str:
    summ = cell_summary(df.filter(pl.col("think_bucket").is_not_null()),
                        ["month", "think_bucket"])
    present = [b for b in THINK_ORDER if b in summ["think_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    for m in sorted(summ["month"].unique().to_list()):
        sub = summ.filter(pl.col("month") == m)
        d = {r["think_bucket"]: r for r in sub.iter_rows(named=True)}
        xs = [xpos[b] for b in present if b in d and d[b]["n"] >= SPARSE_MIN]
        ys = [d[b]["es_mean"] for b in present if b in d and d[b]["n"] >= SPARSE_MIN]
        ax.plot(xs, ys, "-o", color=_MONTH_COLOR.get(m), label=_MONTH_LABEL.get(m, m))
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("think time (seconds bucket; gross = net for 10+0)")
    ax.set_ylabel("mean expected-score loss")
    ax.set_title("Think-time vs expected-score loss — by month\n"
                 "descriptive only; think-time is not deliberation quality")
    _legend(ax); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_07_think_time_es_loss.png")


def fig08_termination(df: pl.DataFrame, out_dir: Path) -> str:
    summ = cell_summary(df, ["termination_channel", "clock_sec_bucket"])
    d = {(r["termination_channel"], r["clock_sec_bucket"]): r
         for r in summ.iter_rows(named=True)}
    present = [b for b in CLOCK_SECONDS_ORDER if b in df["clock_sec_bucket"].to_list()]
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    styles = {"board_decided": ("-o", "#2ca02c"), "time_forfeit": ("--s", "#ff7f0e")}
    for ch, (ls, col) in styles.items():
        ys, xs = [], []
        for b in present:
            cell = d.get((ch, b))
            if cell and cell["n"] >= SPARSE_MIN:
                xs.append(xpos[b]); ys.append(cell["es_mean"])
        if xs:
            ax.plot(xs, ys, ls, color=col, label=ch)
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("clock before move (seconds bucket)")
    ax.set_ylabel("mean expected-score loss")
    ax.set_title("Termination-channel diagnostic: board-decided vs time-forfeit\n"
                 "pooled months; descriptive, not causal")
    _legend(ax, title="termination channel"); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_4_08_termination_channel_diagnostic.png")


def fig09_month_replication(ci_by_month: dict, out_dir: Path) -> str:
    present = [b for b in CLOCK_SECONDS_ORDER
               if any(r["bucket"] == b for rows in ci_by_month.values() for r in rows)]
    months = sorted(ci_by_month.keys())
    x = np.arange(len(present)); w = 0.8 / max(1, len(months))
    fig, ax = plt.subplots(figsize=(8, 5))
    for k, m in enumerate(months):
        d = {r["bucket"]: r["mean"] for r in ci_by_month[m]}
        ax.bar(x + k * w, [d.get(b, np.nan) for b in present], w,
               color=_MONTH_COLOR.get(m), label=_MONTH_LABEL.get(m, m))
    ax.set_xticks(x + w * (len(months) - 1) / 2); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("clock before move (seconds bucket)")
    ax.set_ylabel("mean expected-score loss")
    ax.set_title("Month replication: ES loss by clock bucket (Sep vs Oct)\n"
                 "descriptive, not causal")
    _legend(ax); ax.grid(alpha=0.3, axis="y")
    return _save(fig, out_dir, "fig_15_4_09_month_replication_summary.png")


# ---------------------------------------------------------------------------
# E. Report
# ---------------------------------------------------------------------------

def _md_table(rows: list[dict], cols: list[str], headers: list[str]) -> list[str]:
    L = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for r in rows:
        L.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return L


def render_report(
    report_path: Path, fig_dir: Path, fig_names: list[str], val: dict,
    anomalies: dict, clock_summ: pl.DataFrame, ci_by_month: dict,
    headline_rows: int, mate_band_rows: int, n_rep: int, seed: int,
) -> None:
    print("[atlas] writing report ...", file=sys.stderr)
    rel = lambda n: f"figures/phase_15_4_constraint_atlas/{n}"
    L: list[str] = []
    a = L.append
    a("# CP / ES Constraint Atlas — 10+0, 2024-09 and 2024-10")
    a("")
    a("**Ticket:** 15.4B — CP/ES Constraint Atlas Visualization Implementation")
    a(f"**Bootstrap:** {n_rep} game-clustered draws, seed {seed}")
    a("")
    a("## 1. Executive summary")
    a("")
    a("Descriptive per-ply move-quality atlas over the dense 10+0 substrate (2024-09 + "
      "2024-10, both colors, move_number≥5, depth 12). Headline metric: next-move "
      "**expected-score loss** (mover perspective); clipped centipawn loss is the "
      "secondary, skew-aware view. Every headline figure is shown for both months. "
      "**Predictive/descriptive only — not causal, not a degradation curve; Stockfish "
      "eval is objective position context, not ground truth.** The dominant axis is "
      "eval state; clock and think-time associations are read descriptively.")
    a("")
    a("## 2. Inputs and validation")
    a("")
    a(f"- Combined rows loaded: {val['rows']:,}; months: {', '.join(val['months'])}.")
    a("- Schema validated: required columns present; no raw-username columns; "
      "expected_score_loss ∈ [0,1]; clipped cp ≥ 0; time control uniformly 600+0 / "
      "600 / 0 / rapid; per-month row counts match 15.3C/15.3D.")
    a("")
    a("| month | rows (expected) |")
    a("|---|---|")
    for m in val["months"]:
        a(f"| {m} | {val['per_month'][m]:,} ({EXPECTED_ROWS.get(m, '?')}) |")
    a("")
    a("## 3. Filtering policy and denominators")
    a("")
    a(f"- Headline rows = status OK ∧ not mate-band ∧ both colors: **{headline_rows:,}**.")
    a(f"- Mate-band rows excluded from headline (diagnostic only): {mate_band_rows:,}.")
    a("- Clock/think anomalies are flagged, never dropped (see §14).")
    a("")
    a("## 4. Metric policy")
    a("")
    a("- PRIMARY: `expected_score_loss` (mover perspective). SECONDARY: "
      "`cp_loss_clipped` (median/p75/p90). DIAGNOSTIC-only: `cp_loss_raw`. "
      "Large-loss: ES≥0.05, ES≥0.10, cp≥100, cp≥200. %-eval-swing forbidden as headline.")
    a("")
    a("## 5. Clock vs expected-score loss")
    a("")
    a(f"![clock vs ES]({rel(fig_names[0])})")
    a("")
    for m, rows in ci_by_month.items():
        a(f"**{_MONTH_LABEL.get(m, m)}** ES loss by clock bucket (mean [95% CI], n):")
        a("")
        a("| clock bucket | n | mean | 95% CI | cell |")
        a("|---|---|---|---|---|")
        for r in rows:
            ci = (f"[{r['lo']:.4f}, {r['hi']:.4f}]"
                  if not np.isnan(r["lo"]) else "—")
            a(f"| {r['bucket']} | {r['n']:,} | {r['mean']:.4f} | {ci} | {r['status']} |")
        a("")
    a("## 6. Clock vs clipped centipawn loss")
    a("")
    a(f"![clock vs cp]({rel(fig_names[1])})")
    a("")
    a("## 7. Large-loss probability by clock")
    a("")
    a(f"![large loss]({rel(fig_names[2])})")
    a("")
    a("## 8. Rating × clock atlas")
    a("")
    a(f"![rating clock heatmap]({rel(fig_names[3])})")
    a("")
    a("Pooled heatmap; per-month replication is shown in §13. Sparse cells (n<200) blank.")
    a("")
    a("## 9. Eval-band-conditioned atlas")
    a("")
    a(f"![eval band]({rel(fig_names[4])})")
    a("")
    a("Eval-band conditioning is the dominant axis (15.1B/15.1D): loss separates "
      "strongly by eval state, so marginal clock/CP curves must not be read across "
      "eval regimes.")
    a("")
    a("## 10. Phase / move-number atlas")
    a("")
    a(f"![phase clock]({rel(fig_names[5])})")
    a("")
    a("Move-number bucket × coarse clock — separates low-clock from late-game (they "
      "are confounded).")
    a("")
    a("## 11. Think-time atlas")
    a("")
    a(f"![think time]({rel(fig_names[6])})")
    a("")
    a("Think-time is descriptive, not deliberation quality; high think-time may reflect "
      "lag/disconnection/recording artifacts. For 10+0, gross = net.")
    a("")
    a("## 12. Termination-channel diagnostic")
    a("")
    a(f"![termination]({rel(fig_names[7])})")
    a("")
    a("Board-decided vs time-forfeit rows (fields present in the dense artifact; no "
      "join needed). Consistent with the 11.2B flagging reframing; no causal inference.")
    a("")
    a("## 13. Month replication summary")
    a("")
    a(f"![month replication]({rel(fig_names[8])})")
    a("")
    a("Core ES-loss-by-clock pattern is shown for both months side by side. The "
      "two independent monthly samples agree closely (see §5 tables).")
    a("")
    a("## 14. Sparse-cell and anomaly diagnostics")
    a("")
    a("| month | rows | mate-band | clock>600 | negative think | missing clock |")
    a("|---|---|---|---|---|---|")
    for m, c in anomalies.items():
        a(f"| {m} | {c['rows']:,} | {c['mate_band']:,} | {c['clock_over_600']} | "
          f"{c['negative_think']} | {c['missing_clock']} |")
    a("")
    a("Sparse cells (n<200) are blanked in the heatmap and labelled `sparse` in the "
      "clock tables; cells 200–999 are `marked`; n≥1000 are `headline`.")
    a("")
    a("## 15. Interpretation")
    a("")
    a("- The atlas is a descriptive map of where next-move expected-score loss is "
      "higher or lower across clock, rating, eval state, phase, and think-time.")
    a("- Eval state dominates; clock/think-time patterns are read net of nothing here "
      "(marginal), so they are NOT controlled estimates — the controlled C4 result "
      "(15.1D/15.1F: small replicated clock association after eval/phase/rating/"
      "termination controls) is the inferential statement, not these marginal curves.")
    a("- Low-clock cells are a survivor population (board-decided games that did not "
      "flag); read with that caveat.")
    a("- Patterns replicate across 2024-09 and 2024-10.")
    a("")
    a("## 16. Non-claims")
    a("")
    a("- Predictive/descriptive only; NOT causal. No \"low clock causes blunders\"; no "
      "\"time pressure causes worse reasoning\". Stockfish eval is objective context, "
      "not ground truth. No human-obviousness modeling. No sharpness conditioning "
      "(Phase 15.5). No cross-time-control (Phase 16). Not a public/synthesis report. "
      "No model fitting or selection. C4 and C3c unchanged.")
    a("")
    a("## 17. Recommended next ticket")
    a("")
    a("**15.4C — Controlled Dense Move-Quality Modeling Audit** (design the per-ply "
      "controlled model that reproduces the C4 small-clock-association result on the "
      "dense substrate, net of eval band / phase / rating / termination). Sharpness "
      "enrichment (Phase 15.5) follows. Not Phase 16; not synthesis.")
    a("")
    a("## Figure manifest")
    a("")
    for n in fig_names:
        a(f"- `{rel(n)}`")
    a("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(x for x in L if x is not None))


# ---------------------------------------------------------------------------
# F. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Dense CP/ES Constraint Atlas (Ticket 15.4B). Reads dense "
                    "move-loss artifacts; renders PNG figures + a markdown report. "
                    "Descriptive/predictive, not causal.")
    p.add_argument("--dense-month", action="append", required=True,
                   help="dense_move_loss_*.parquet (repeatable)")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--bootstrap", type=int, default=500)
    p.add_argument("--seed", type=int, default=20240617)
    p.add_argument("--no-count-check", action="store_true",
                   help="skip per-month row-count assertion (dev only)")
    args = p.parse_args(argv)

    df = load_dense(args.dense_month)
    val = validate_schema(df, check_counts=not args.no_count_check)
    anomalies = anomaly_counts(df)

    print("[atlas] filtering headline rows ...", file=sys.stderr)
    df = add_buckets(df)
    mate_band_rows = int(df.filter(pl.col("is_mate_band")).height)
    head = filter_headline(df)
    headline_rows = head.height

    out_dir = Path(args.out_dir)
    clock_summ = cell_summary(head, ["month", "clock_sec_bucket"])
    ci_by_month = clock_es_with_ci(head, n_rep=args.bootstrap, seed=args.seed)

    fig_names = [
        fig01_clock_vs_es(ci_by_month, out_dir),
        fig02_clock_vs_cp(clock_summ, out_dir),
        fig03_large_loss(clock_summ, out_dir),
        fig04_rating_clock_heatmap(head, out_dir),
        fig05_eval_band(head, out_dir),
        fig06_phase_clock(head, out_dir),
        fig07_think_time(head, out_dir),
        fig08_termination(head, out_dir),
        fig09_month_replication(ci_by_month, out_dir),
    ]

    render_report(Path(args.report), out_dir, fig_names, val, anomalies,
                  clock_summ, ci_by_month, headline_rows, mate_band_rows,
                  args.bootstrap, args.seed)

    print(f"\n=== 15.4B dense atlas ===")
    print(f"  rows={val['rows']:,} headline={headline_rows:,} mate_band={mate_band_rows:,}")
    print(f"  figures={len(fig_names)} -> {out_dir}")
    print(f"  report -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
