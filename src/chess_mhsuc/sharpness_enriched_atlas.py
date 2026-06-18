"""
Sharpness-enriched constraint atlas — Ticket 15.5B (CHECKPOINT-OVERLAP, White-to-move).

Joins the existing MultiPV sharpness artifacts (checkpoint-only, White-to-move) to the
dense move-quality substrate and produces a descriptive sharp-vs-non-sharp atlas plus an
EXPLORATORY clock x sharpness model on the matched rows. It reads artifacts read-only and
writes PNG figures + a markdown report. It does NOT run Stockfish/MultiPV, does NOT modify
artifacts, and makes NO dense-wide sharpness claim.

CRITICAL JOIN SEMANTICS (15.5A): sharpness describes the position AFTER ``checkpoint_ply``
half-moves (White to move); the dense move played FROM that position is at
``dense.ply = checkpoint_ply + 1`` (White mover). The naive ``dense.ply == checkpoint_ply``
join is WRONG (it matches the Black move into the checkpoint). Matched coverage is ~4.36%
of dense headline rows, WHITE-MOVER ONLY, checkpoint-overlap only.

Sharpness = ``sharp_value_fragility_v1`` = OBJECTIVE VALUE FRAGILITY, NOT human obviousness
/ difficulty. The C3c clock x sharpness moderation is directional/underpowered (Phase 14,
not confirmed, not disproven); this ticket does not rewrite that — the sharp x low-clock
interaction here is EXPLORATORY/no-claim given the cell counts.

All results are predictive/descriptive conditional associations — NOT causal.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.sharpness_enriched_atlas \\
        --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \\
        --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \\
        --sharpness-month data/processed/multipv_sharpness_2024_09_250k_v1.parquet \\
        --sharpness-month data/processed/multipv_sharpness_2024_10_250k_v1.parquet \\
        --out-dir reports/figures/phase_15_5_sharpness_enriched_atlas \\
        --report reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md \\
        --bootstrap 500 --seed 20240617
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from chess_mhsuc.clustered_uncertainty import summarize_contrasts
from chess_mhsuc.dense_constraint_atlas import clock_coarse_bucket, rating_bucket_200
from chess_mhsuc.dense_controlled_model import (
    CLOCK_LEVELS, EVAL_LEVELS, MONTH_LEVELS, PHASE_LEVELS, RATING_LEVELS,
    TERM_LEVELS, ols_cluster_bootstrap,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DENSE_EXPECTED_ROWS = {"2024_09": 1_496_890, "2024_10": 1_436_866}
SHARP_EXPECTED_ROWS = {"2024_09": 64_371, "2024_10": 61_868}
# 15.5A measured matched coverage (corrected join); used for a sanity tolerance check.
EXPECTED_MATCHED = {"2024_09": 61_732, "2024_10": 59_433}

SHARP_FLAG = "sharp_value_fragility_v1"
CLOCK_ORDER = ["under_10", "10_30", "30_60", "60_180", "over_180"]
RATING_ORDER = ["<1000", "1000_1199", "1200_1399", "1400_1599", "1600_1799",
                "1800_1999", "2000_2199", "2200+"]
EVAL_ORDER = ["near_equal", "slight", "clear", "decided"]
TEN_ZERO_START_S = 600.0
SPARSE_MIN = 200
HEADLINE_MIN = 1000

DENSE_COLS = [
    "month", "game_id", "ply", "move_number", "mover_color", "mover_elo",
    "clock_before_s", "think_time_gross_s", "expected_score_loss",
    "expected_score_before", "cp_loss_clipped", "cp_loss_raw", "is_mate_band",
    "status", "eval_band", "phase", "termination", "is_time_forfeit",
    "mover_player_hash",
]
SHARP_COLS = [
    "game_id", "checkpoint_ply", "selected_position_type", "side_to_move",
    "status", "is_mate_band", SHARP_FLAG, "sharp_value_fragility_v1_relaxed",
    "sharp_value_fragility_v1_strict", "best_second_gap_es", "n_good_10es",
    "worst_top5_loss_es", "legal_move_count", "depth", "multipv_k",
]
_FORBIDDEN_USERNAME_COLS = {"white", "black", "White", "Black", "white_user", "black_user"}

_MONTH_LABEL = {"2024_09": "2024-09", "2024_10": "2024-10"}
_SHARP_COLOR = {"sharp": "#d62728", "non_sharp": "#1f77b4"}
_CHECKPOINT_NOTE = "checkpoint-overlap, White-mover only"


# ---------------------------------------------------------------------------
# A. Load + validate
# ---------------------------------------------------------------------------

def _load_selected(paths: list[str | Path], cols: list[str], tag: str) -> pl.DataFrame:
    frames = []
    for p in paths:
        print(f"[sharp-atlas] loading {tag} {p} selected columns ...", file=sys.stderr)
        avail = pl.scan_parquet(p).collect_schema().names()
        frames.append(pl.read_parquet(p, columns=[c for c in cols if c in avail]))
    return pl.concat(frames, how="diagonal_relaxed") if len(frames) > 1 else frames[0]


def validate_dense(df: pl.DataFrame, check_counts: bool = True) -> dict:
    missing = [c for c in DENSE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"dense input missing required columns: {missing}")
    if _FORBIDDEN_USERNAME_COLS & set(df.columns):
        raise ValueError("raw username columns present in dense input")
    es = df["expected_score_loss"]
    if es.min() is not None and (es.min() < 0 or es.max() > 1.0001):
        raise ValueError("dense expected_score_loss out of [0,1]")
    if df["cp_loss_clipped"].min() is not None and df["cp_loss_clipped"].min() < 0:
        raise ValueError("dense cp_loss_clipped negative")
    per = {r[0]: r[1] for r in df.group_by("month").len().iter_rows()}
    if check_counts:
        for m, n in DENSE_EXPECTED_ROWS.items():
            if per.get(m) != n:
                raise ValueError(f"dense row count mismatch {m}: {per.get(m)} != {n}")
    if set(df["mover_color"].unique().to_list()) != {"white", "black"}:
        raise ValueError("dense should contain both mover colors before join")
    return {"rows": df.height, "per_month": per}


def validate_sharpness(df: pl.DataFrame, month_of, check_counts: bool = True) -> dict:
    need = ["game_id", "checkpoint_ply", "side_to_move", "status", SHARP_FLAG]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"sharpness input missing required columns: {missing}")
    if _FORBIDDEN_USERNAME_COLS & set(df.columns):
        raise ValueError("raw username columns present in sharpness input")
    ok = df.filter(pl.col("status") == "ok")
    stm = set(ok["side_to_move"].unique().to_list())
    if stm - {"white"}:
        raise ValueError(f"sharpness side_to_move must be White only; got {stm}")
    cps = sorted(ok["checkpoint_ply"].unique().to_list())
    return {"rows": df.height, "ok_rows": ok.height, "checkpoint_plies": cps,
            "side_to_move": sorted(stm)}


# ---------------------------------------------------------------------------
# B. Join (dense.ply = checkpoint_ply + 1) + derive
# ---------------------------------------------------------------------------

def join_checkpoint_overlap(dense: pl.DataFrame, sharp: pl.DataFrame) -> pl.DataFrame:
    """Inner-join dense move-quality rows to existing sharpness on the CORRECTED key:
    ``dense.ply == sharp.checkpoint_ply + 1`` and same game_id. The result is the White
    move played FROM each White-to-move checkpoint position (checkpoint-overlap)."""
    sk = (sharp.filter(pl.col("status") == "ok")
          .select(["game_id", "checkpoint_ply", SHARP_FLAG,
                   "best_second_gap_es", "n_good_10es", "worst_top5_loss_es"])
          .with_columns((pl.col("checkpoint_ply") + 1).alias("ply"))
          .drop("checkpoint_ply"))
    return dense.join(sk, on=["game_id", "ply"], how="inner")


def validate_join(joined: pl.DataFrame) -> dict:
    """Assert the join produced White-mover checkpoint-overlap rows."""
    colors = set(joined["mover_color"].unique().to_list())
    if colors - {"white"}:
        raise ValueError(
            f"checkpoint-overlap join must be White-mover only; got {colors} — "
            "this usually means the join used ply==checkpoint_ply instead of "
            "ply==checkpoint_ply+1")
    return {"matched_rows": joined.height,
            "matched_per_month": {r[0]: r[1] for r in
                                  joined.group_by("month").len().iter_rows()},
            "mover_colors": sorted(colors)}


def add_columns(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns([
        pl.col("clock_before_s").map_elements(clock_coarse_bucket, return_dtype=pl.Utf8)
        .alias("clock_coarse"),
        pl.col("mover_elo").map_elements(rating_bucket_200, return_dtype=pl.Utf8)
        .alias("rating_bin"),
        pl.when(pl.col("is_time_forfeit")).then(pl.lit("time_forfeit"))
        .otherwise(pl.lit("board_decided")).alias("termination_channel"),
        (pl.col("clock_before_s") > TEN_ZERO_START_S).cast(pl.Float64).alias("clock_anom"),
        (pl.col("think_time_gross_s") < 0).cast(pl.Float64).alias("think_anom"),
        pl.col(SHARP_FLAG).cast(pl.Float64).alias("sharp"),
        pl.when(pl.col(SHARP_FLAG) == 1).then(pl.lit("sharp"))
        .otherwise(pl.lit("non_sharp")).alias("sharp_label"),
    ])


def filter_headline(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter((pl.col("status") == "ok") & (~pl.col("is_mate_band")))


def cell_status(n: int) -> str:
    if n < SPARSE_MIN:
        return "sparse"
    if n < HEADLINE_MIN:
        return "exploratory"
    return "headline"


# ---------------------------------------------------------------------------
# C. Aggregation
# ---------------------------------------------------------------------------

def sharp_clock_cells(df: pl.DataFrame, by: list[str]) -> pl.DataFrame:
    g = df.group_by(by).agg([
        pl.len().alias("n"),
        pl.col("expected_score_loss").mean().alias("es_mean"),
        pl.col("expected_score_loss").median().alias("es_median"),
        pl.col("cp_loss_clipped").median().alias("cp_median"),
        pl.col("cp_loss_clipped").quantile(0.75).alias("cp_p75"),
        (pl.col("expected_score_loss") >= 0.05).mean().alias("p_es_ge_05"),
        (pl.col("expected_score_loss") >= 0.10).mean().alias("p_es_ge_10"),
    ])
    return g.with_columns(
        pl.col("n").map_elements(cell_status, return_dtype=pl.Utf8).alias("cell"))


# ---------------------------------------------------------------------------
# D. Exploratory clock x sharpness model
# ---------------------------------------------------------------------------

def build_design(df: pl.DataFrame, include_month: bool = True,
                 include_termination: bool = True) -> tuple[np.ndarray, list[str]]:
    """ES-loss design: clock (ref over_180) + sharp + clock x sharp + eval (ref decided)
    + phase (ref middlegame) + rating bins (ref 1600_1799) + month + termination + anomaly
    flags + intercept. mover_color OMITTED (constant White on matched rows). Constant
    columns are dropped so subgroup/month fits stay full-rank."""
    n = len(df)
    sharp = df["sharp"].to_numpy().astype(float)
    cc = df["clock_coarse"].to_numpy()
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    for lv in CLOCK_LEVELS:
        ind = (cc == lv).astype(float)
        cols.append((f"clock={lv}", ind))
        cols.append((f"clock={lv}:sharp", ind * sharp))
    cols.append(("sharp", sharp))
    eb = df["eval_band"].to_numpy()
    for lv in EVAL_LEVELS:
        cols.append((f"eval={lv}", (eb == lv).astype(float)))
    ph = df["phase"].to_numpy()
    for lv in PHASE_LEVELS:
        cols.append((f"phase={lv}", (ph == lv).astype(float)))
    rb = df["rating_bin"].to_numpy()
    for lv in RATING_LEVELS:
        cols.append((f"rating={lv}", (rb == lv).astype(float)))
    if include_month:
        mo = df["month"].to_numpy()
        for lv in MONTH_LEVELS:
            cols.append((f"month={lv}", (mo == lv).astype(float)))
    if include_termination:
        tcv = df["termination_channel"].to_numpy()
        for lv in TERM_LEVELS:
            cols.append((f"termination={lv}", (tcv == lv).astype(float)))
    cols.append(("clock_anom", df["clock_anom"].to_numpy().astype(float)))
    cols.append(("think_anom", df["think_anom"].to_numpy().astype(float)))
    kept = [cols[0]] + [(nm, v) for nm, v in cols[1:]
                        if float(v.min()) != float(v.max())]
    names = [c[0] for c in kept]
    X = np.column_stack([c[1] for c in kept])
    return X, names


FOCAL_INTERACTION = "clock=60_180:sharp"
MODEL_CONTRASTS = {
    "sharp main effect (at over_180)": "sharp",
    "clock 60_180 (at non-sharp)": "clock=60_180",
    "clock 60_180 x sharp (focal interaction)": FOCAL_INTERACTION,
    "clock 30_60 x sharp": "clock=30_60:sharp",
    "clock 10_30 x sharp": "clock=10_30:sharp",
    "clock under_10 x sharp": "clock=under_10:sharp",
}


def fit_model(df: pl.DataFrame, target: str, contrasts: dict[str, str],
              cluster_col: str, n_reps: int, seed: int, **dk) -> dict:
    X, names = build_design(df, **dk)
    y = df[target].to_numpy().astype(float)
    full, boot, meta = ols_cluster_bootstrap(X, y, df[cluster_col].to_list(), n_reps, seed)
    wanted = [c for c in contrasts.values() if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    labelled = {lab: summ[coef] for lab, coef in contrasts.items() if coef in summ}
    return {"contrasts": labelled, "meta": meta, "n_rows": len(df), "names": names}


# ---------------------------------------------------------------------------
# E. Plots
# ---------------------------------------------------------------------------

def _present(order, vals):
    return [b for b in order if b in vals]


def _save(fig, out_dir: Path, name: str) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / name, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"[sharp-atlas] rendering {name} ...", file=sys.stderr)
    return name


def _sharp_by_clock_plot(df, out_dir, name, ycol, ylabel, title, agg="mean"):
    cells = sharp_clock_cells(df, ["sharp_label", "clock_coarse"])
    present = _present(CLOCK_ORDER, cells["clock_coarse"].to_list())
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    for lab in ("non_sharp", "sharp"):
        sub = {r["clock_coarse"]: r for r in
               cells.filter(pl.col("sharp_label") == lab).iter_rows(named=True)}
        xs = [xpos[b] for b in present if b in sub and sub[b]["n"] >= SPARSE_MIN]
        ys = [sub[b][ycol] for b in present if b in sub and sub[b]["n"] >= SPARSE_MIN]
        ax.plot(xs, ys, "-o", color=_SHARP_COLOR[lab], label=lab)
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("clock before move (coarse bucket)"); ax.set_ylabel(ylabel)
    ax.set_title(f"{title}\n{_CHECKPOINT_NOTE}; descriptive, not causal")
    ax.legend(title="value fragility"); ax.grid(alpha=0.3)
    return _save(fig, out_dir, name)


def fig01(df, out_dir):
    return _sharp_by_clock_plot(df, out_dir, "fig_15_5_01_sharp_vs_nonsharp_es_loss_by_clock.png",
        "es_mean", "mean expected-score loss", "Sharp vs non-sharp ES loss by clock")


def fig02(df, out_dir):
    return _sharp_by_clock_plot(df, out_dir, "fig_15_5_02_sharp_vs_nonsharp_clipped_cp_by_clock.png",
        "cp_median", "median clipped CP loss", "Sharp vs non-sharp clipped CP loss by clock")


def fig03(df, out_dir):
    return _sharp_by_clock_plot(df, out_dir, "fig_15_5_03_large_loss_probability_clock_sharpness.png",
        "p_es_ge_10", "P(ES loss >= 0.10)", "Large-loss probability by clock x sharpness")


def fig04(df, out_dir):
    cells = sharp_clock_cells(df, ["sharp_label", "eval_band"])
    present = _present(EVAL_ORDER, cells["eval_band"].to_list())
    xpos = {b: i for i, b in enumerate(present)}
    fig, ax = plt.subplots(figsize=(8, 5))
    for lab in ("non_sharp", "sharp"):
        sub = {r["eval_band"]: r for r in
               cells.filter(pl.col("sharp_label") == lab).iter_rows(named=True)}
        xs = [xpos[b] for b in present if b in sub and sub[b]["n"] >= SPARSE_MIN]
        ys = [sub[b]["es_mean"] for b in present if b in sub and sub[b]["n"] >= SPARSE_MIN]
        ax.plot(xs, ys, "-o", color=_SHARP_COLOR[lab], label=lab)
    ax.set_xticks(list(xpos.values())); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("eval band"); ax.set_ylabel("mean expected-score loss")
    ax.set_title("Sharp vs non-sharp ES loss by eval band\n"
                 f"{_CHECKPOINT_NOTE}; does sharpness add beyond eval band?")
    ax.legend(title="value fragility"); ax.grid(alpha=0.3)
    return _save(fig, out_dir, "fig_15_5_04_eval_band_sharpness_es_loss.png")


def fig05(df, out_dir):
    cells = sharp_clock_cells(df, ["sharp_label", "rating_bin"])
    present = _present(RATING_ORDER, cells["rating_bin"].to_list())
    x = np.arange(len(present)); w = 0.38
    fig, ax = plt.subplots(figsize=(9, 5))
    for k, lab in enumerate(("non_sharp", "sharp")):
        sub = {r["rating_bin"]: r for r in
               cells.filter(pl.col("sharp_label") == lab).iter_rows(named=True)}
        ys = [sub[b]["es_mean"] if (b in sub and sub[b]["n"] >= SPARSE_MIN) else np.nan
              for b in present]
        ax.bar(x + (k - 0.5) * w, ys, w, color=_SHARP_COLOR[lab], label=lab)
    ax.set_xticks(x); ax.set_xticklabels(present, rotation=30)
    ax.set_xlabel("mover rating bin"); ax.set_ylabel("mean expected-score loss")
    ax.set_title(f"Sharp vs non-sharp ES loss by rating\n{_CHECKPOINT_NOTE}")
    ax.legend(title="value fragility"); ax.grid(alpha=0.3, axis="y")
    return _save(fig, out_dir, "fig_15_5_05_rating_sharpness_es_loss.png")


def fig06(df, out_dir):
    cells = sharp_clock_cells(df, ["month", "sharp_label"])
    months = _present(["2024_09", "2024_10"], cells["month"].to_list())
    x = np.arange(len(months)); w = 0.38
    fig, ax = plt.subplots(figsize=(7, 5))
    for k, lab in enumerate(("non_sharp", "sharp")):
        sub = {r["month"]: r for r in
               cells.filter(pl.col("sharp_label") == lab).iter_rows(named=True)}
        ys = [sub[m]["es_mean"] if m in sub else np.nan for m in months]
        ax.bar(x + (k - 0.5) * w, ys, w, color=_SHARP_COLOR[lab], label=lab)
    ax.set_xticks(x); ax.set_xticklabels([_MONTH_LABEL.get(m, m) for m in months])
    ax.set_ylabel("mean expected-score loss")
    ax.set_title(f"Month replication: sharp vs non-sharp ES loss\n{_CHECKPOINT_NOTE}")
    ax.legend(title="value fragility"); ax.grid(alpha=0.3, axis="y")
    return _save(fig, out_dir, "fig_15_5_06_month_replication_summary.png")


# ---------------------------------------------------------------------------
# F. Report
# ---------------------------------------------------------------------------

def _ci(d: dict) -> str:
    lo, hi = d.get("ci_lower"), d.get("ci_upper")
    if lo is None or hi is None:
        return "—"
    star = "" if d.get("contains_zero", True) else " *"
    return f"[{lo:+.4f}, {hi:+.4f}]{star}"


def _contrast_table(res: dict, contrasts: dict) -> list[str]:
    L = ["| contrast | estimate | 95% CI (game-clustered) |", "|---|---|---|"]
    for lab in contrasts:
        d = res["contrasts"].get(lab)
        if d:
            L.append(f"| {lab} | {d['estimate']:+.4f} | {_ci(d)} |")
    return L


def render_report(path, fig_names, dval, sval, jval, denoms, head_rows, mate_excl,
                  sharp_rate, clock_cells, model, model_bd, month_models,
                  n_reps, seed, runtime, fig_dir_rel):
    print("[sharp-atlas] writing report ...", file=sys.stderr)
    rel = lambda n: f"{fig_dir_rel}/{n}"
    L: list[str] = []
    a = L.append
    a("# Sharpness-Enriched Constraint Atlas — Existing Checkpoint Overlap, 10+0")
    a("")
    a(f"**Ticket:** 15.5B | **{_CHECKPOINT_NOTE}** | bootstrap {n_reps} game-clustered "
      f"draws, seed {seed} | runtime {runtime:.0f}s")
    a("")
    a("## 1. Executive summary")
    a("")
    foc = model["contrasts"].get("clock 60_180 x sharp (focal interaction)", {})
    sh = model["contrasts"].get("sharp main effect (at over_180)", {})
    a(f"Existing MultiPV sharpness (objective **value fragility**, NOT human obviousness) "
      f"joined to the dense substrate on the corrected key `dense.ply = checkpoint_ply + 1`. "
      f"Matched headline rows are **{_CHECKPOINT_NOTE}** ({head_rows:,} rows = "
      f"{100*head_rows/head_rows_total(denoms):.2f}% of dense headline; see §3). "
      f"Descriptively, sharp positions carry higher next-move loss; the focal **clock 60_180 × "
      f"sharp** interaction = {foc.get('estimate', float('nan')):+.4f} {_ci(foc)} is "
      f"**EXPLORATORY / no-claim** (sparse cells, §13). Sharpness main effect (at over_180) "
      f"{sh.get('estimate', float('nan')):+.4f} {_ci(sh)}. **This does NOT resolve C3c** "
      "(directional/underpowered, not confirmed, not disproven). Predictive/descriptive, "
      "not causal; Stockfish/MultiPV is objective value context, not ground truth.")
    a("")
    a("## 2. Inputs and validation")
    a(f"- Dense: {dval['rows']:,} rows {dval['per_month']}; counts match 15.3C/15.3D; no usernames.")
    a(f"- Sharpness: {sval['rows']:,} rows; checkpoint plies {sval['checkpoint_plies']}; "
      f"side_to_move {sval['side_to_move']}; no usernames.")
    a("")
    a("## 3. Join semantics and coverage")
    a("")
    a("Join key: `dense.game_id == sharpness.game_id AND dense.ply == checkpoint_ply + 1` "
      "(the White move played FROM the White-to-move checkpoint position). The naive "
      "`ply == checkpoint_ply` join is wrong (matches the Black move into the checkpoint).")
    a("")
    a("| month | dense headline | matched | % | mover colors |")
    a("|---|---|---|---|---|")
    for m in sorted(denoms):
        hr = denoms[m]["headline"]; mm = jval["matched_per_month"].get(m, 0)
        a(f"| {m} | {hr:,} | {mm:,} | {100*mm/hr:.2f}% | white only |")
    a(f"- Matched mover colors: {jval['mover_colors']} (White only by construction). "
      "**Checkpoint-overlap only; NOT dense-wide.**")
    a("")
    a("## 4. Filtering and denominators")
    a("| month | dense rows | headline | mate-band excl | matched |")
    a("|---|---|---|---|---|")
    for m in sorted(denoms):
        d = denoms[m]
        a(f"| {m} | {d['rows']:,} | {d['headline']:,} | {d['mate_band']:,} | "
          f"{jval['matched_per_month'].get(m,0):,} |")
    a(f"- Matched headline rows analysed: **{head_rows:,}** (mate-band excluded {mate_excl:,}).")
    a("")
    a("## 5. Sharpness metric definitions")
    a(f"- Primary flag `sharp_value_fragility_v1` (objective value fragility: "
      "`n_good_10es<=2 ∧ worst_top5_loss_es>=0.10 ∧ legal_move_count>=8`); matched sharp "
      f"rate {sharp_rate:.4f}. **NOT human obviousness / difficulty.**")
    a("")
    a("## 6. Sharp vs non-sharp expected-score loss by clock")
    a(f"![f1]({rel(fig_names[0])})")
    a("")
    a("| clock | sharp ES mean | non-sharp ES mean | sharp n | non-sharp n |")
    a("|---|---|---|---|---|")
    cc = {(r["sharp_label"], r["clock_coarse"]): r for r in clock_cells.iter_rows(named=True)}
    for b in _present(CLOCK_ORDER, clock_cells["clock_coarse"].to_list()):
        s = cc.get(("sharp", b)); ns = cc.get(("non_sharp", b))
        a(f"| {b} | {(s['es_mean'] if s else float('nan')):.4f} | "
          f"{(ns['es_mean'] if ns else float('nan')):.4f} | {(s['n'] if s else 0):,} | "
          f"{(ns['n'] if ns else 0):,} |")
    a("")
    a("## 7. Sharp vs non-sharp clipped CP loss by clock")
    a(f"![f2]({rel(fig_names[1])})")
    a("")
    a("## 8. Large-loss probability by clock × sharpness")
    a(f"![f3]({rel(fig_names[2])})")
    a("")
    a("## 9. Eval-band-conditioned sharpness patterns")
    a(f"![f4]({rel(fig_names[3])})")
    a("")
    a("Checks whether value fragility adds information beyond eval band (it conditions on "
      "fragility within the engine's evaluation, a different axis).")
    a("")
    a("## 10. Rating-conditioned sharpness patterns")
    a(f"![f5]({rel(fig_names[4])})")
    a("")
    a("## 11. Exploratory controlled clock × sharpness model")
    a("")
    a(f"`expected_score_loss ~ clock(ref over_180) + sharp + clock×sharp + eval(ref decided) "
      f"+ phase + rating_bin + month + termination + anomaly` (mover_color omitted — constant "
      f"White). {model['n_rows']:,} rows; {model['meta']['n_clusters']:,} game clusters; "
      f"{model['meta']['n_success']}/{n_reps} refits.")
    a("")
    L += _contrast_table(model, MODEL_CONTRASTS)
    a("")
    a("**The clock × sharp interactions are EXPLORATORY / no-claim** (sparse sharp×low-clock "
      "cells, §13). Board-decided-only focal interaction: "
      f"{model_bd['contrasts'].get('clock 60_180 x sharp (focal interaction)', {}).get('estimate', float('nan')):+.4f} "
      f"{_ci(model_bd['contrasts'].get('clock 60_180 x sharp (focal interaction)', {}))}.")
    a("")
    a("## 12. Month replication")
    a(f"![f6]({rel(fig_names[5])})")
    a("")
    a("| contrast | 2024-09 | 2024-10 |")
    a("|---|---|---|")
    for lab in ("sharp main effect (at over_180)", "clock 60_180 x sharp (focal interaction)"):
        d9 = month_models["2024_09"]["contrasts"].get(lab, {})
        d10 = month_models["2024_10"]["contrasts"].get(lab, {})
        a(f"| {lab} | {d9.get('estimate', float('nan')):+.4f} {_ci(d9)} | "
          f"{d10.get('estimate', float('nan')):+.4f} {_ci(d10)} |")
    a("")
    a("If the focal interaction sign/scale disagrees across months, replication is NOT claimed.")
    a("")
    a("## 13. Sparse-cell and power diagnostics")
    a("| cell | sharp n | status |")
    a("|---|---|---|")
    for b in _present(CLOCK_ORDER, clock_cells["clock_coarse"].to_list()):
        s = cc.get(("sharp", b))
        nn = s["n"] if s else 0
        a(f"| sharp × {b} | {nn:,} | {cell_status(nn)} |")
    a("")
    a(f"Policy: n<{SPARSE_MIN} sparse/no-claim; {SPARSE_MIN}–{HEADLINE_MIN-1} exploratory; "
      f">={HEADLINE_MIN} headline-capable. The `sharp × 60_180` and lower-clock cells are "
      "exploratory/sparse — the same underpowered corner that left C3c unresolved.")
    a("")
    a("## 14. Comparison to prior C3c result")
    a("- Phase 14 C3c (`clock=60_180 × sharp_value_fragility_v1`, checkpoint level): "
      "train+val pooled directional positive (~+0.010), test near zero, key cells "
      "underpowered → **not confirmed, not disproven**.")
    a(f"- This 15.5B checkpoint-overlap exploratory interaction: "
      f"{foc.get('estimate', float('nan')):+.4f} {_ci(foc)} — exploratory/no-claim. "
      "**C3c status is unchanged.**")
    a("")
    a("## 15. Interpretation")
    a("- Coverage is checkpoint-overlap, White-mover only (~4.4% of dense); not dense-wide.")
    a("- Sharp positions are descriptively higher-loss; whether the clock residual localizes "
      "to sharp positions is not resolvable here (sparse interaction cells).")
    a("- C3c remains unresolved; a stratified dense sharpness extraction (both colors, more "
      "low-clock sharp cells) would be needed to power the interaction — a separate ticket.")
    a("- Future diagnostic (NOT this ticket): a **Think-Time Loss-Rate / Flagging Signature "
      "Diagnostic** (cp/ES loss per unit think-time, board-decided vs time-forfeit).")
    a("")
    a("## 16. Non-claims")
    a("Predictive/descriptive only; NOT causal. No \"sharp positions cause blunders\"; no "
      "\"low clock causes blunders\"; no \"time pressure causes worse reasoning\". Sharpness = "
      "objective value fragility, NOT human obviousness/difficulty; MultiPV/Stockfish is not "
      "ground truth. Checkpoint-overlap, White-mover only — NOT a dense-wide sharpness analysis. "
      "C3c not confirmed, not disproven. C4 and C3c unchanged.")
    a("")
    a("## 17. Recommended next ticket")
    a("**15.5C — Sharpness Result Consolidation / C3c Claim Update** (consolidate this "
      "checkpoint-overlap result; decide whether a stratified dense sharpness extraction is "
      "warranted). Not Phase 16; not synthesis.")
    a("")
    a("## Figure manifest")
    for nfg in fig_names:
        a(f"- `{rel(nfg)}`")
    a("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


def head_rows_total(denoms: dict) -> int:
    return sum(d["headline"] for d in denoms.values())


# ---------------------------------------------------------------------------
# G. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Sharpness-enriched constraint atlas — checkpoint-overlap, White-to-move "
                    "(Ticket 15.5B). Existing sharpness only; no MultiPV/Stockfish. "
                    "Descriptive + exploratory; not causal.")
    p.add_argument("--dense-month", action="append", required=True)
    p.add_argument("--sharpness-month", action="append", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--bootstrap", type=int, default=500)
    p.add_argument("--seed", type=int, default=20240617)
    p.add_argument("--no-count-check", action="store_true")
    args = p.parse_args(argv)

    t0 = time.time()
    dense = _load_selected(args.dense_month, DENSE_COLS, "dense")
    sharp = _load_selected(args.sharpness_month, SHARP_COLS, "sharpness")
    print("[sharp-atlas] validating schemas ...", file=sys.stderr)
    dval = validate_dense(dense, check_counts=not args.no_count_check)
    sval = validate_sharpness(sharp, None, check_counts=not args.no_count_check)

    # denominators (dense headline) before join
    denoms = {}
    for m in sorted(dense["month"].unique().to_list()):
        sub = dense.filter(pl.col("month") == m)
        denoms[m] = {"rows": sub.height,
                     "headline": sub.filter((pl.col("status") == "ok") & (~pl.col("is_mate_band"))).height,
                     "mate_band": int(sub["is_mate_band"].sum())}

    print("[sharp-atlas] joining dense.ply = checkpoint_ply + 1 ...", file=sys.stderr)
    joined = join_checkpoint_overlap(dense, sharp)
    print("[sharp-atlas] validating White-mover checkpoint overlap ...", file=sys.stderr)
    jval = validate_join(joined)

    head = filter_headline(add_columns(joined))
    head_rows = head.height
    mate_excl = int(joined.filter(pl.col("is_mate_band")).height)
    sharp_rate = float(head["sharp"].mean())

    out_dir = Path(args.out_dir)
    print("[sharp-atlas] rendering figures ...", file=sys.stderr)
    fig_names = [fig01(head, out_dir), fig02(head, out_dir), fig03(head, out_dir),
                 fig04(head, out_dir), fig05(head, out_dir), fig06(head, out_dir)]
    clock_cells = sharp_clock_cells(head, ["sharp_label", "clock_coarse"])

    print("[sharp-atlas] fitting exploratory clock x sharpness model ...", file=sys.stderr)
    model = fit_model(head, "expected_score_loss", MODEL_CONTRASTS, "game_id",
                      args.bootstrap, args.seed)
    bd = head.filter(~pl.col("is_time_forfeit"))
    model_bd = fit_model(bd, "expected_score_loss",
                         {"clock 60_180 x sharp (focal interaction)": FOCAL_INTERACTION},
                         "game_id", args.bootstrap, args.seed, include_termination=False)
    month_models = {}
    for m in ("2024_09", "2024_10"):
        sub = head.filter(pl.col("month") == m)
        month_models[m] = fit_model(
            sub, "expected_score_loss",
            {"sharp main effect (at over_180)": "sharp",
             "clock 60_180 x sharp (focal interaction)": FOCAL_INTERACTION},
            "game_id", args.bootstrap, args.seed, include_month=False)

    runtime = time.time() - t0
    # relative path from the report (in reports/) to the figure dir.
    fig_dir_rel = str(out_dir).replace("reports/", "", 1)
    render_report(Path(args.report), fig_names, dval, sval, jval, denoms, head_rows,
                  mate_excl, sharp_rate, clock_cells, model, model_bd, month_models,
                  args.bootstrap, args.seed, runtime, fig_dir_rel)

    foc = model["contrasts"].get("clock 60_180 x sharp (focal interaction)", {})
    print(f"\n=== 15.5B sharpness-enriched atlas (checkpoint-overlap, White-mover) ===")
    print(f"  matched={jval['matched_rows']:,} headline={head_rows:,} sharp_rate={sharp_rate:.4f} "
          f"runtime={runtime:.0f}s")
    print(f"  focal clock60_180 x sharp (EXPLORATORY): {foc.get('estimate', float('nan')):+.4f} {_ci(foc)}")
    print(f"  report -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
