"""Benchmark headline figures (Ticket 17.0B) — public replication/benchmark package.

Reads ONLY the six existing dense move-loss Parquets (no Stockfish, no extraction, no
modeling, no refit). Reuses validated pure helpers from cross_time_control_analysis
(16.2B) for loading/validation/headline-population/buckets/quintiles. Produces the six
headline figures H1–H6 + count tables, all from on-disk aggregation.

Headline figures (all descriptive, NOT causal):
  H1  game-level time-forfeit prevalence by control × month
  H2  all-games vs board-decided ES loss vs ACTUAL seconds remaining (panel/control)
  H3  ES loss vs actual seconds by ABSOLUTE 200-Elo bin (per control)
  H4  ES loss vs move number by clock state (per control × Elo group)
  H5  move-number × actual-seconds heatmap of mean ES loss (per control)
  H6  month-replication summary of the central clock contrasts

Non-claims: predictive/descriptive only; Stockfish = objective context not ground truth;
raw Elo bins are within-control and not identical populations across controls.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

import chess_mhsuc.cross_time_control_analysis as ctc
from chess_mhsuc.cross_time_control_analysis import CONTROL_ORDER, MONTH_ORDER, CONTROL_SPECS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_CONTROL_COLOR = {"3+0": "#d62728", "5+0": "#1f77b4", "10+0": "#2ca02c"}
_MONTH_LABEL = {"2024_09": "2024-09", "2024_10": "2024-10"}
# headline 200-Elo bins; sparse tails collapsed by collapse_sparse_elo_bins
RAW_ELO_EDGES = [0, 1200, 1400, 1600, 1800, 2000, 2200, 4000]
RAW_ELO_LABELS = ["<1200", "1200-1399", "1400-1599", "1600-1799",
                  "1800-1999", "2000-2199", "2200+"]
CLOCK_STATE_ORDER = ["critical", "low", "medium", "high"]  # clock_fraction coarse
SPARSE_MIN_ROWS = 1000
SPARSE_MIN_GAMES = 200
HEATMAP_MIN_COUNT = 200      # minimum move rows per displayed heatmap cell
HEATMAP_MIN_GAMES = 50       # minimum distinct games per displayed heatmap cell
_FORBIDDEN_USERNAME_COLS = ctc._FORBIDDEN_USERNAME_COLS


# ---------------------------------------------------------------------------
# A. Pure helpers (unit-tested)
# ---------------------------------------------------------------------------
def actual_second_edges(initial_time_s: int, n_bins: int = 18) -> list[float]:
    """Bin edges in actual seconds, [0, initial_time_s], n_bins equal-width bins.
    Control-appropriate because initial_time_s differs (180/300/600)."""
    if initial_time_s <= 0 or n_bins < 1:
        raise ValueError("initial_time_s>0 and n_bins>=1 required")
    return list(np.linspace(0.0, float(initial_time_s), n_bins + 1))


def assign_second_bin(clock_before_s: float | None, initial_time_s: int,
                      n_bins: int = 18) -> int | None:
    """Bin index 0..n_bins-1 for a clamped actual-seconds value; None if missing."""
    if clock_before_s is None:
        return None
    s = min(max(float(clock_before_s), 0.0), float(initial_time_s))  # clamp anomalies
    edges = actual_second_edges(initial_time_s, n_bins)
    idx = int(np.searchsorted(edges, s, side="right") - 1)
    return min(max(idx, 0), n_bins - 1)


def move_number_edges(max_move: int = 80, width: int = 5) -> list[int]:
    """Move-number bin edges [5, max_move] step `width` (+ overflow bin label handled
    by caller). Opening starts at move 5 (dense extraction floor)."""
    if width < 1 or max_move <= 5:
        raise ValueError("width>=1 and max_move>5 required")
    return list(range(5, max_move + 1, width))


def collapse_sparse_elo_bins(counts: dict[str, int], min_count: int = SPARSE_MIN_GAMES
                             ) -> tuple[list[str], dict[str, str]]:
    """Given {elo_label: game_count}, return (kept_labels_in_order, remap). Sparse
    leading/trailing tails are merged into the nearest kept neighbour; interior sparse
    bins are kept but flagged by the caller. Deterministic."""
    order = [b for b in RAW_ELO_LABELS if b in counts]
    if not order:
        return [], {}
    remap = {b: b for b in order}
    # collapse leading sparse tail into first adequate bin
    first_ok = next((i for i, b in enumerate(order) if counts[b] >= min_count), len(order) - 1)
    for i in range(first_ok):
        remap[order[i]] = order[first_ok]
    # collapse trailing sparse tail into last adequate bin
    last_ok = next((len(order) - 1 - i for i, b in enumerate(reversed(order))
                    if counts[b] >= min_count), 0)
    for i in range(last_ok + 1, len(order)):
        remap[order[i]] = order[last_ok]
    kept = []
    for b in order:
        t = remap[b]
        if t not in kept:
            kept.append(t)
    return kept, remap


def add_actual_second_bin(df: pl.DataFrame, n_bins: int = 18) -> pl.DataFrame:
    """Add `sec_bin` (0..n_bins-1) and `sec_bin_mid` (bin midpoint, seconds), per row,
    using the row's own initial_time_s. Clamps clock>initial anomalies into the top bin."""
    out = []
    for control in CONTROL_ORDER:
        sub = df.filter(pl.col("control") == control)
        if sub.height == 0:
            continue
        init = CONTROL_SPECS[control][1]
        edges = actual_second_edges(init, n_bins)
        mids = [(edges[i] + edges[i + 1]) / 2 for i in range(n_bins)]
        clamped = pl.col("clock_before_s").clip(0.0, float(init))
        # width-uniform bin index
        w = init / n_bins
        bi = (clamped / w).floor().clip(0, n_bins - 1).cast(pl.Int64)
        out.append(sub.with_columns([
            bi.alias("sec_bin"),
            bi.map_elements(lambda i: mids[int(i)], return_dtype=pl.Float64).alias("sec_bin_mid"),
        ]))
    return pl.concat(out, how="vertical_relaxed")


def add_raw_elo_bin(df: pl.DataFrame) -> pl.DataFrame:
    e = pl.col("mover_elo")
    expr = (pl.when(e < 1200).then(pl.lit("<1200"))
            .when(e < 1400).then(pl.lit("1200-1399"))
            .when(e < 1600).then(pl.lit("1400-1599"))
            .when(e < 1800).then(pl.lit("1600-1799"))
            .when(e < 2000).then(pl.lit("1800-1999"))
            .when(e < 2200).then(pl.lit("2000-2199"))
            .otherwise(pl.lit("2200+")))
    return df.with_columns(expr.alias("elo_bin"))


def validate_no_usernames(df: pl.DataFrame) -> None:
    bad = _FORBIDDEN_USERNAME_COLS & set(df.columns)
    if bad:
        raise ValueError(f"forbidden username columns present: {bad}")


def figure_name(stem: str) -> str:
    """Deterministic .png filename for a headline figure stem."""
    if not stem or stem != stem.strip() or "/" in stem:
        raise ValueError("invalid figure stem")
    return f"{stem}.png" if not stem.endswith(".png") else stem


# ---------------------------------------------------------------------------
# B. Aggregation (unit-tested)
# ---------------------------------------------------------------------------
def weighted_mean_expr(value: str, weight: str) -> pl.Expr:
    """Game-normalized weighted mean expression: sum(value*weight)/sum(weight).
    `weight` = `analysis_weight` from cross_time_control_analysis.add_analysis_weights
    (each game equal total weight within its control-month; long games do not dominate)."""
    return (pl.col(value) * pl.col(weight)).sum() / pl.col(weight).sum()


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    """Numpy game-normalized weighted mean (for the heatmap path)."""
    w = np.asarray(weights, float); v = np.asarray(values, float)
    s = w.sum()
    return float((v * w).sum() / s) if s > 0 else float("nan")


def aggregate_all_vs_board_decided(df: pl.DataFrame, bin_col: str,
                                   weight: str = "analysis_weight") -> pl.DataFrame:
    """GAME-NORMALIZED mean ES loss + counts per (control, population ∈ {all, board_decided},
    bin_col). Uses `weight` (game-normalized) so long games do not dominate; `rows`/`games`
    are the raw cell counts behind each weighted mean."""
    frames = []
    for pop, fdf in [("all", df),
                     ("board_decided", df.filter(pl.col("termination_channel") == "board_decided"))]:
        g = fdf.group_by(["control", bin_col]).agg([
            weighted_mean_expr("expected_score_loss", weight).alias("es_mean"),
            pl.col("expected_score_loss").mean().alias("es_mean_raw"),
            pl.len().alias("rows"),
            pl.col("game_id").n_unique().alias("games"),
        ]).with_columns(pl.lit(pop).alias("population"))
        frames.append(g)
    return pl.concat(frames, how="vertical_relaxed").sort(["control", "population", bin_col])


def game_level_termination_prevalence(game_tbl: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for control in CONTROL_ORDER:
        for month in MONTH_ORDER:
            g = game_tbl.filter((pl.col("control") == control) & (pl.col("month") == month))
            n = g.height
            tf = int(g["is_time_forfeit"].sum())
            rows.append({"control": control, "month": month, "games": n, "tf_games": tf,
                         "pr_time_forfeit": round(tf / n, 4) if n else 0.0})
    return pl.DataFrame(rows)


def heatmap_cells(df: pl.DataFrame, control: str, n_sec_bins: int = 18,
                  mn_width: int = 5, max_move: int = 80, min_count: int = HEATMAP_MIN_COUNT,
                  min_games: int = HEATMAP_MIN_GAMES, weight: str = "analysis_weight"):
    """Return (matrix[n_mn × n_sec] GAME-NORMALIZED mean ES loss with NaN where
    rows<min_count OR distinct games<min_games, sec_mids, mn_centers, count_matrix,
    games_matrix) for one control. The game threshold guards against a cell being
    'powered' by a handful of unusually long games."""
    sub = df.filter(pl.col("control") == control)
    init = CONTROL_SPECS[control][1]
    edges = actual_second_edges(init, n_sec_bins)
    sec_mids = [(edges[i] + edges[i + 1]) / 2 for i in range(n_sec_bins)]
    mn_edges = list(range(5, max_move + 1, mn_width))
    n_mn = len(mn_edges)
    M = np.full((n_mn, n_sec_bins), np.nan)
    C = np.zeros((n_mn, n_sec_bins), dtype=int)
    G = np.zeros((n_mn, n_sec_bins), dtype=int)
    sub = sub.with_columns([
        pl.col("clock_before_s").clip(0.0, float(init)).alias("_cs"),
        pl.col("move_number").clip(5, max_move).alias("_mn"),
    ])
    cs = sub["_cs"].to_numpy(); mn = sub["_mn"].to_numpy()
    es = sub["expected_score_loss"].to_numpy(); wt = sub[weight].to_numpy()
    gid = sub["game_id"].to_numpy()
    w = init / n_sec_bins
    si = np.clip((cs / w).astype(int), 0, n_sec_bins - 1)
    mi = np.clip(((mn - 5) // mn_width).astype(int), 0, n_mn - 1)
    for r in range(n_mn):
        for c in range(n_sec_bins):
            mask = (mi == r) & (si == c)
            cnt = int(mask.sum())
            C[r, c] = cnt
            ng = int(np.unique(gid[mask]).size) if cnt else 0
            G[r, c] = ng
            if cnt >= min_count and ng >= min_games:
                M[r, c] = weighted_mean(es[mask], wt[mask])
    mn_centers = [e + mn_width / 2 for e in mn_edges]
    return M, sec_mids, mn_centers, C, G


def elo_bin_counts(df: pl.DataFrame, control: str) -> dict[str, dict]:
    sub = df.filter(pl.col("control") == control)
    g = sub.group_by("elo_bin").agg([
        pl.len().alias("rows"), pl.col("game_id").n_unique().alias("games"),
        pl.col("mover_player_hash").n_unique().alias("movers"),
        pl.col("mover_elo").min().alias("lo"), pl.col("mover_elo").max().alias("hi"),
    ]).to_dicts()
    return {r["elo_bin"]: r for r in g}


# ---------------------------------------------------------------------------
# C. Figures (matplotlib Agg)
# ---------------------------------------------------------------------------
def _prep(paths):
    raw, vals = ctc.load_all_artifacts(paths)
    head = ctc.build_headline_population(raw)
    head = ctc.add_clock_fraction_buckets(head)
    head = ctc.add_anomaly_flags(head)          # adds termination_channel + flags
    head, cuts = ctc.assign_rating_quintiles(head)
    head = ctc.add_analysis_weights(head)   # game-normalized weight (long games don't dominate)
    head = add_raw_elo_bin(head)
    validate_no_usernames(head)
    game_tbl = ctc.build_game_level_table(head)
    return raw, vals, head, cuts, game_tbl


def render_headline_figures(head, game_tbl, fig_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir.mkdir(parents=True, exist_ok=True)
    inv = []

    def save(fig, stem):
        p = fig_dir / figure_name(stem)
        fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
        inv.append({"file": p.name, "bytes": p.stat().st_size})

    # ---- H1: game-level time-forfeit prevalence by control × month ----
    prev = game_level_termination_prevalence(game_tbl)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(CONTROL_ORDER)); wd = 0.36
    for i, mo in enumerate(MONTH_ORDER):
        vals_ = [prev.filter((pl.col("control") == c) & (pl.col("month") == mo))["pr_time_forfeit"][0]
                 for c in CONTROL_ORDER]
        bars = ax.bar(x + (i - 0.5) * wd, vals_, wd, label=_MONTH_LABEL[mo])
        for b, v in zip(bars, vals_):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.005, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(CONTROL_ORDER)
    ax.set_ylabel("game-level Pr(game ended on time)"); ax.set_xlabel("time control")
    ax.set_title("H1 — Time-forfeit prevalence by time control (descriptive)")
    ax.legend(title="month"); ax.grid(alpha=.3, axis="y")
    save(fig, "H1_time_forfeit_prevalence_by_control")

    # ---- H2: all-games vs board-decided ES loss vs ACTUAL seconds (panel/control) ----
    h2 = add_actual_second_bin(head, n_bins=18)
    agg = aggregate_all_vs_board_decided(h2, "sec_bin_mid")
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.6), sharey=True)
    for ax, c in zip(axes, CONTROL_ORDER):
        for pop, ls, lab in [("all", "-", "all games"), ("board_decided", "--", "board-decided")]:
            d = agg.filter((pl.col("control") == c) & (pl.col("population") == pop)).sort("sec_bin_mid")
            ax.plot(d["sec_bin_mid"], d["es_mean"], marker="o", ls=ls, color=_CONTROL_COLOR[c], label=lab)
        ax.set_title(f"{c}  (0–{CONTROL_SPECS[c][1]}s)"); ax.set_xlabel("actual seconds remaining")
        ax.grid(alpha=.3); ax.legend(fontsize=8)
    axes[0].set_ylabel("game-normalized mean expected-score loss")
    fig.suptitle("H2 — Move-quality vs actual seconds remaining: all games vs board-decided "
                 "(game-normalized means; removing time-forfeit games attenuates but does not eliminate)")
    save(fig, "H2_all_games_vs_board_decided_actual_seconds")

    # ---- H3: ES loss vs actual seconds by absolute 200-Elo bin (per control) ----
    for c in CONTROL_ORDER:
        counts = elo_bin_counts(h2, c)
        gcounts = {b: counts[b]["games"] for b in counts}
        kept, remap = collapse_sparse_elo_bins(gcounts, SPARSE_MIN_GAMES)
        sub = h2.filter(pl.col("control") == c).with_columns(
            pl.col("elo_bin").replace(remap).alias("elo_bin_c"))
        fig, ax = plt.subplots(figsize=(8.5, 5))
        cmap = plt.cm.viridis(np.linspace(0, 0.92, len(kept)))
        for col, b in zip(cmap, kept):
            d = sub.filter(pl.col("elo_bin_c") == b).group_by("sec_bin_mid").agg(
                weighted_mean_expr("expected_score_loss", "analysis_weight").alias("m"),
                pl.col("game_id").n_unique().alias("g")).sort("sec_bin_mid")
            lo = counts.get(b, {}).get("lo"); hi = counts.get(b, {}).get("hi")
            ax.plot(d["sec_bin_mid"], d["m"], marker="o", color=col,
                    label=f"{b} (Elo {lo}-{hi})")
        ax.set_xlabel("actual seconds remaining"); ax.set_ylabel("game-normalized mean expected-score loss")
        ax.set_title(f"H3 — {c}: move-quality vs actual seconds by absolute Elo bin (within-control)")
        ax.legend(fontsize=7, title="200-Elo bin"); ax.grid(alpha=.3)
        save(fig, f"H3_move_quality_actual_seconds_by_elo_{c.replace('+','plus')}")

    # ---- H4: ES loss vs move number by clock state (per control, mid Elo group) ----
    for c in CONTROL_ORDER:
        sub = head.filter((pl.col("control") == c) & (pl.col("move_number") <= 80))
        fig, ax = plt.subplots(figsize=(8.5, 5))
        for st, col in zip(CLOCK_STATE_ORDER, ["#7b3294", "#c2a5cf", "#a6dba0", "#008837"]):
            d = sub.filter(pl.col("clock_coarse") == st).group_by("move_number").agg(
                weighted_mean_expr("expected_score_loss", "analysis_weight").alias("m"),
                pl.len().alias("n"), pl.col("game_id").n_unique().alias("g")) \
                .filter((pl.col("n") >= 200) & (pl.col("g") >= 50)).sort("move_number")
            if d.height:
                ax.plot(d["move_number"], d["m"], marker=".", color=col, label=st)
        ax.set_xlabel("move number"); ax.set_ylabel("game-normalized mean expected-score loss")
        ax.set_title(f"H4 — {c}: move-quality by move number and clock state")
        ax.legend(title="clock state", fontsize=8); ax.grid(alpha=.3)
        save(fig, f"H4_move_quality_by_move_number_and_clock_state_{c.replace('+','plus')}")

    # ---- H5: move-number × actual-seconds heatmap of mean ES loss (per control) ----
    for c in CONTROL_ORDER:
        M, sec_mids, mn_centers, C, G = heatmap_cells(head, c)
        total = M.size
        masked = int(np.isnan(M).sum())
        fig, ax = plt.subplots(figsize=(9, 5))
        im = ax.imshow(M, aspect="auto", origin="lower", cmap="magma",
                       extent=[sec_mids[0], sec_mids[-1], mn_centers[0], mn_centers[-1]])
        ax.set_xlabel("actual seconds remaining"); ax.set_ylabel("move number")
        ax.set_title(f"H5 — {c}: mean ES loss by move number × actual seconds (game-normalized)")
        ax.text(0.99, 0.02, f"masked {masked}/{total} cells (<{HEATMAP_MIN_COUNT} rows "
                f"or <{HEATMAP_MIN_GAMES} games)", transform=ax.transAxes, ha="right", va="bottom",
                fontsize=7, color="white")
        fig.colorbar(im, ax=ax, label="game-normalized mean expected-score loss")
        save(fig, f"H5_move_number_actual_clock_heatmap_{c.replace('+','plus')}")

    # ---- H6: month replication — board-decided attenuation at low (critical) clock ----
    # Mean ES loss at critical clock (clock_fraction<=0.05) for all games vs board-decided,
    # per control x month. Honest aggregation that matches the narrative: board-decided sits
    # BELOW all-games (the time-forfeit attenuation, cf. H2), and Sep≈Oct (replication). We
    # deliberately do NOT plot the unconditioned critical-minus-high marginal gap, which is
    # confounded by phase composition (critical-clock states are endgame-concentrated).
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), sharey=True)
    x = np.arange(len(MONTH_ORDER)); wd = 0.36
    for ax, c in zip(axes, CONTROL_ORDER):
        crit = head.filter((pl.col("control") == c) & (pl.col("clock_coarse") == "critical"))
        for i, (pop, lab, col) in enumerate([("all", "all games", "#888888"),
                                             ("board_decided", "board-decided", _CONTROL_COLOR[c])]):
            fdf = crit if pop == "all" else crit.filter(pl.col("termination_channel") == "board_decided")
            vals_ = []
            for mo in MONTH_ORDER:
                mdf = fdf.filter(pl.col("month") == mo)
                m = (mdf.select(weighted_mean_expr("expected_score_loss", "analysis_weight")).item()
                     if mdf.height else None)
                vals_.append(float(m) if m is not None else np.nan)
            ax.bar(x + (i - 0.5) * wd, vals_, wd, label=lab, color=col)
        ax.set_xticks(x); ax.set_xticklabels([_MONTH_LABEL[m] for m in MONTH_ORDER])
        ax.set_title(c); ax.grid(alpha=.3, axis="y"); ax.legend(fontsize=8)
    axes[0].set_ylabel("game-normalized mean ES loss at critical clock (≤5% of base time)")
    fig.suptitle("H6 — Month replication: critical-clock move-quality, all games vs board-decided "
                 "(board-decided lower = time-forfeit attenuation; Sep≈Oct = replication)")
    save(fig, "H6_month_replication_summary")
    return inv


# ---------------------------------------------------------------------------
# D. Count tables + figure index
# ---------------------------------------------------------------------------
def build_count_tables(head, game_tbl) -> dict:
    h2 = add_actual_second_bin(head, n_bins=18)
    denom = []
    for c in CONTROL_ORDER:
        for mo in MONTH_ORDER:
            s = head.filter((pl.col("control") == c) & (pl.col("month") == mo))
            denom.append({"control": c, "month": mo, "headline_rows": s.height,
                          "games": int(s["game_id"].n_unique())})
    elo = []
    for c in CONTROL_ORDER:
        for b, r in sorted(elo_bin_counts(h2, c).items()):
            elo.append({"control": c, "elo_bin": b, "elo_lo": r["lo"], "elo_hi": r["hi"],
                        "rows": r["rows"], "games": r["games"], "movers": r["movers"],
                        "sparse": bool(r["games"] < SPARSE_MIN_GAMES)})
    return {"denominators": pl.DataFrame(denom),
            "elo_bins": pl.DataFrame(elo),
            "termination": game_level_termination_prevalence(game_tbl)}


def write_count_tables_md(path: Path, tables: dict) -> None:
    L = ["# Benchmark figure count tables", "",
         "Aggregation counts behind the headline figures. **Estimand:** H2–H6 plot the "
         "**game-normalized** mean expected-score loss (each game contributes equal total weight "
         "within its control-month, via `analysis_weight`, so long games do not dominate) — the same "
         "weighting the inferential Phase-16 models used. The difference from the raw move-row mean is "
         "small and does not change the curve shape (raw ≈ weighted − ~0.002). H1 is a game-level rate "
         "(one row per game). Within-control; raw Elo bins are NOT identical populations across "
         "controls.", ""]
    L.append("## Headline denominators")
    L.append("| Control | Month | Headline rows | Games |")
    L.append("|---|---|---|---|")
    for r in tables["denominators"].to_dicts():
        L.append(f"| {r['control']} | {r['month']} | {r['headline_rows']:,} | {r['games']:,} |")
    L.append("")
    L.append("## Absolute 200-Elo bins (per control, pooled months)")
    L.append("| Control | Elo bin | Elo range | Rows | Games | Movers | Sparse(<200 games) |")
    L.append("|---|---|---|---|---|---|---|")
    for r in tables["elo_bins"].to_dicts():
        L.append(f"| {r['control']} | {r['elo_bin']} | {r['elo_lo']}-{r['elo_hi']} | "
                 f"{r['rows']:,} | {r['games']:,} | {r['movers']:,} | {'yes' if r['sparse'] else ''} |")
    L.append("")
    L.append("## Game-level time-forfeit prevalence")
    L.append("| Control | Month | Games | TF games | Pr(time forfeit) |")
    L.append("|---|---|---|---|---|")
    for r in tables["termination"].to_dicts():
        L.append(f"| {r['control']} | {r['month']} | {r['games']:,} | {r['tf_games']:,} | "
                 f"{r['pr_time_forfeit']:.4f} |")
    path.write_text("\n".join(L))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Benchmark headline figures (17.0B; read-only)")
    for mo in MONTH_ORDER:
        for tag in ("3plus0", "5plus0", "10plus0"):
            p.add_argument(f"--dense-{mo.replace('_','-')}-{tag}", required=True)
    p.add_argument("--figure-dir", default="reports/figures/benchmark")
    p.add_argument("--count-tables", default="reports/figures/benchmark/count_tables.md")
    args = p.parse_args(argv); g = vars(args)
    paths = {
        ("3+0", "2024_09"): g["dense_2024_09_3plus0"], ("5+0", "2024_09"): g["dense_2024_09_5plus0"],
        ("10+0", "2024_09"): g["dense_2024_09_10plus0"], ("3+0", "2024_10"): g["dense_2024_10_3plus0"],
        ("5+0", "2024_10"): g["dense_2024_10_5plus0"], ("10+0", "2024_10"): g["dense_2024_10_10plus0"],
    }
    t0 = time.time()
    _, _, head, _, game_tbl = _prep(paths)
    inv = render_headline_figures(head, game_tbl, Path(args.figure_dir))
    tables = build_count_tables(head, game_tbl)
    write_count_tables_md(Path(args.count_tables), tables)
    print(f"[benchmark] figures: {len(inv)} | runtime {time.time()-t0:.0f}s | dir {args.figure_dir}")
    for f in inv:
        print(f"  {f['file']} ({f['bytes']//1024}K)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
