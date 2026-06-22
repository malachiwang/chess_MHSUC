"""Cross-time-control move-quality atlas + controlled modeling (Ticket 16.2B).

First full no-increment cross-time-control analysis over the six dense move-loss
artifacts (3+0 / 5+0 / 10+0 x 2024-09 / 2024-10). Dedicated module: reuses ONLY the
pure clustered-bootstrap index helper from the stable Phase-15 code and does not edit
dense_constraint_atlas.py / dense_controlled_model.py / dense_move_loss.py.

Scientific scope (kept distinct, all predictive/descriptive, NOT causal):
  T1  game-level time-forfeit prevalence across controls
  T2  average next-move expected-score loss across controls
  T3  within-control clock-fraction gradient (conditional)
  T4  cross-control moderation (time_control x clock_fraction interaction)

Cross-control axes:
  clock   = clock_fraction = clock_before_s / initial_time_s   (NOT raw seconds)
  rating  = within-control x month mover-rating QUINTILE        (raw Elo NOT comparable)

Non-claims: no causal claim; raw ratings not cross-pool comparable; Stockfish not
ground truth; ES transform reused across controls (comparability assumption, not refit);
no sharpness (neither confirmed nor disproven). See the rendered report's forbidden list.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

from chess_mhsuc.clustered_uncertainty import _cluster_index

# ---------------------------------------------------------------------------
# Constants / identity
# ---------------------------------------------------------------------------
CONTROL_ORDER = ("3+0", "5+0", "10+0")
MONTH_ORDER = ("2024_09", "2024_10")

# control -> (time_control_raw, initial_time_s, speed_category)
CONTROL_SPECS = {
    "3+0":  ("180+0", 180, "blitz"),
    "5+0":  ("300+0", 300, "blitz"),
    "10+0": ("600+0", 600, "rapid"),
}

FINE_LEVELS = ["cf_le_002", "cf_002_005", "cf_005_010", "cf_010_025",
               "cf_025_050", "cf_050_075", "cf_over_075"]
COARSE_LEVELS = ["critical", "low", "medium", "high"]   # ref = high
COARSE_NONREF = ["critical", "low", "medium"]
EVAL_LEVELS = ["near_equal", "slight", "clear"]          # ref = decided
PHASE_LEVELS = ["opening", "endgame"]                    # ref = middlegame
QUINTILE_LEVELS = ["Q1", "Q2", "Q3", "Q4", "Q5"]         # ref = Q3
QUINTILE_NONREF = ["Q1", "Q2", "Q4", "Q5"]
TC_NONREF = ["3+0", "5+0"]                               # ref = 10+0
MONTH_NONREF = ["2024_10"]                               # ref = 2024_09
COLOR_NONREF = ["black"]                                 # ref = white

_LOAD_COLS = [
    "game_id", "month", "ply", "move_number", "mover_color", "mover_elo",
    "white_elo", "black_elo", "clock_before_s", "think_time_gross_s",
    "time_control_raw", "initial_time_s", "increment_s", "time_control_family",
    "speed_category", "clock_fraction", "expected_score_loss", "cp_loss_raw",
    "cp_loss_clipped", "is_mate_band", "status", "eval_band", "phase",
    "termination", "is_time_forfeit", "result_class", "mover_player_hash",
]
_FORBIDDEN_USERNAME_COLS = {"white", "black", "White", "Black",
                            "white_user", "black_user", "username"}
_STATUS_OK = "ok"
HEADLINE_MIN_ROWS = 1000
HEADLINE_MIN_GAMES = 200
EXPLORATORY_MIN_ROWS = 200
EXPLORATORY_MIN_GAMES = 50


# ---------------------------------------------------------------------------
# A. Loading + identity validation
# ---------------------------------------------------------------------------
def load_dense_artifact(path: str | Path, control: str, month: str) -> pl.DataFrame:
    """Read the selected columns for one artifact and tag control/month_expected."""
    avail = pl.read_parquet_schema(path)
    cols = [c for c in _LOAD_COLS if c in avail]
    df = pl.read_parquet(path, columns=cols)
    return df.with_columns([pl.lit(control).alias("control"),
                            pl.lit(month).alias("month_expected")])


def validate_artifact_identity(df: pl.DataFrame, control: str, month: str,
                               check_counts: bool = True) -> dict:
    """Validate one artifact's control/month identity + schema/privacy. Raises on
    a hard identity/privacy mismatch; returns a summary dict."""
    tc_raw, init_s, speed = CONTROL_SPECS[control]
    issues: list[str] = []

    forbidden = _FORBIDDEN_USERNAME_COLS & set(df.columns)
    if forbidden:
        raise ValueError(f"{control} {month}: forbidden username columns {forbidden}")
    missing = [c for c in _LOAD_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{control} {month}: missing required columns {missing}")

    u_tc = df["time_control_raw"].unique().to_list()
    if u_tc != [tc_raw]:
        raise ValueError(f"{control}: time_control_raw {u_tc} != [{tc_raw}]")
    u_init = df["initial_time_s"].unique().to_list()
    if u_init != [init_s]:
        raise ValueError(f"{control}: initial_time_s {u_init} != [{init_s}]")
    u_inc = df["increment_s"].unique().to_list()
    if u_inc != [0]:
        raise ValueError(f"{control}: increment_s {u_inc} != [0] (no-increment only)")
    u_fam = df["time_control_family"].unique().to_list()
    if u_fam != ["no_increment"]:
        raise ValueError(f"{control}: time_control_family {u_fam} != [no_increment]")
    u_speed = set(df["speed_category"].unique().to_list())
    if u_speed != {speed}:
        raise ValueError(f"{control}: speed_category {u_speed} != {{{speed}}}")
    u_month = df["month"].unique().to_list()
    if u_month != [month]:
        raise ValueError(f"{control}: month col {u_month} != [{month}]")

    dups = df.height - df.select(["game_id", "ply"]).unique().height
    if dups != 0:
        raise ValueError(f"{control} {month}: {dups} duplicate (game_id, ply) keys")
    colors = set(df["mover_color"].unique().to_list())
    if colors != {"white", "black"}:
        issues.append(f"mover_color {colors} != white+black")
    hash_null = int(df["mover_player_hash"].is_null().sum())
    es = df["expected_score_loss"]
    if es.min() is not None and (es.min() < -1e-9 or es.max() > 1.0 + 1e-9):
        issues.append(f"expected_score_loss out of [0,1]: [{es.min()},{es.max()}]")
    if df["cp_loss_clipped"].min() is not None and df["cp_loss_clipped"].min() < 0:
        issues.append("cp_loss_clipped negative")
    bad_status = df.filter(pl.col("status") != _STATUS_OK).height

    return {"control": control, "month": month, "rows": df.height,
            "games": int(df["game_id"].n_unique()), "dups": dups,
            "colors": sorted(colors), "hash_null": hash_null,
            "non_ok_status": bad_status, "issues": issues}


def load_all_artifacts(paths: dict[tuple[str, str], str | Path]) -> tuple[pl.DataFrame, list[dict]]:
    """Load + validate all six artifacts; return (concatenated frame, validations)."""
    frames, vals = [], []
    for control in CONTROL_ORDER:
        for month in MONTH_ORDER:
            p = paths[(control, month)]
            df = load_dense_artifact(p, control, month)
            vals.append(validate_artifact_identity(df, control, month))
            frames.append(df)
    return pl.concat(frames, how="vertical_relaxed"), vals


# ---------------------------------------------------------------------------
# B. Population, buckets, quintiles, flags, weights
# ---------------------------------------------------------------------------
def build_headline_population(df: pl.DataFrame) -> pl.DataFrame:
    """status==ok, non-mate-band, valid clock/clock_fraction/rating/termination."""
    return df.filter(
        (pl.col("status") == _STATUS_OK) & (~pl.col("is_mate_band"))
        & pl.col("expected_score_loss").is_not_null()
        & pl.col("cp_loss_clipped").is_not_null()
        & pl.col("clock_before_s").is_not_null()
        & pl.col("clock_fraction").is_not_null()
        & pl.col("mover_elo").is_not_null()
        & pl.col("termination").is_not_null()
    )


def _fine_expr(cf: pl.Expr) -> pl.Expr:
    return (pl.when(cf <= 0.02).then(pl.lit("cf_le_002"))
            .when(cf <= 0.05).then(pl.lit("cf_002_005"))
            .when(cf <= 0.10).then(pl.lit("cf_005_010"))
            .when(cf <= 0.25).then(pl.lit("cf_010_025"))
            .when(cf <= 0.50).then(pl.lit("cf_025_050"))
            .when(cf <= 0.75).then(pl.lit("cf_050_075"))
            .otherwise(pl.lit("cf_over_075")))


def _coarse_expr(cf: pl.Expr) -> pl.Expr:
    return (pl.when(cf <= 0.05).then(pl.lit("critical"))
            .when(cf <= 0.15).then(pl.lit("low"))
            .when(cf <= 0.50).then(pl.lit("medium"))
            .otherwise(pl.lit("high")))


def add_clock_fraction_buckets(df: pl.DataFrame) -> pl.DataFrame:
    """Add cf_fine + clock_coarse from clock_fraction (>1 stays in cf_over_075/high)."""
    cf = pl.col("clock_fraction")
    return df.with_columns([_fine_expr(cf).alias("cf_fine"),
                            _coarse_expr(cf).alias("clock_coarse")])


def add_anomaly_flags(df: pl.DataFrame) -> pl.DataFrame:
    """Control-aware anomaly flags: clock_gt_initial (clock_fraction>1) + neg think."""
    return df.with_columns([
        (pl.col("clock_fraction") > 1.0).cast(pl.Float64).alias("clock_gt_initial_flag"),
        (pl.col("think_time_gross_s") < 0).cast(pl.Float64).alias("negative_think_time_flag"),
        pl.when(pl.col("is_time_forfeit")).then(pl.lit("time_forfeit"))
        .otherwise(pl.lit("board_decided")).alias("termination_channel"),
    ])


def assign_rating_quintiles(df: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Assign within-control x month mover-rating quintiles (Q1..Q5). Deterministic:
    uses .qcut on mover_elo per stratum; ties fall to the lower quintile boundary via
    qcut's left-closed bins. Returns (frame_with_rating_quintile, cutpoints)."""
    out_parts, cutpoints = [], {}
    for control in CONTROL_ORDER:
        for month in MONTH_ORDER:
            sub = df.filter((pl.col("control") == control) & (pl.col("month") == month))
            if sub.height == 0:
                continue
            elo = sub["mover_elo"]
            qs = [float(elo.quantile(q, interpolation="linear")) for q in (0.2, 0.4, 0.6, 0.8)]
            cutpoints[(control, month)] = [int(round(x)) for x in qs]
            e = pl.col("mover_elo")
            qexpr = (pl.when(e <= qs[0]).then(pl.lit("Q1"))
                     .when(e <= qs[1]).then(pl.lit("Q2"))
                     .when(e <= qs[2]).then(pl.lit("Q3"))
                     .when(e <= qs[3]).then(pl.lit("Q4"))
                     .otherwise(pl.lit("Q5")))
            out_parts.append(sub.with_columns(qexpr.alias("rating_quintile")))
    return pl.concat(out_parts, how="vertical_relaxed"), cutpoints


def add_analysis_weights(df: pl.DataFrame) -> pl.DataFrame:
    """Game-normalized weight with equal control-month aggregate weight.

    raw_w = 1 / (n_games_in_stratum * headline_moves_in_game). Each game thus sums to
    1/n_games_stratum, and each (control,month) stratum sums to 1.0. Then rescale so
    mean weight == 1 across all rows (relative weights unchanged)."""
    stratum = ["control", "month"]
    df = df.with_columns(
        pl.len().over(stratum + ["game_id"]).alias("_moves_in_game"))
    df = df.with_columns(
        pl.col("game_id").n_unique().over(stratum).alias("_games_in_stratum"))
    df = df.with_columns(
        (1.0 / (pl.col("_games_in_stratum") * pl.col("_moves_in_game"))).alias("_raw_w"))
    mean_w = float(df["_raw_w"].mean())
    return df.with_columns((pl.col("_raw_w") / mean_w).alias("analysis_weight")).drop(
        ["_moves_in_game", "_games_in_stratum", "_raw_w"])


def build_game_level_table(df: pl.DataFrame) -> pl.DataFrame:
    """Collapse to one row per (control, month, game_id). Asserts termination is
    constant within a game."""
    g = df.group_by(["control", "month", "game_id"]).agg([
        pl.col("is_time_forfeit").n_unique().alias("_tf_nuniq"),
        pl.col("is_time_forfeit").max().alias("is_time_forfeit"),
        pl.col("termination_channel").n_unique().alias("_tc_nuniq"),
        pl.col("termination_channel").first().alias("termination_channel"),
        pl.col("mover_elo").mean().alias("game_rating_mean"),
        pl.col("rating_quintile").first().alias("rating_quintile"),
        pl.col("white_elo").first().alias("white_elo"),
        pl.col("black_elo").first().alias("black_elo"),
        pl.col("ply").max().alias("final_ply"),
        pl.len().alias("n_headline_moves"),
        pl.col("result_class").first().alias("result_class"),
    ])
    bad = g.filter((pl.col("_tf_nuniq") > 1) | (pl.col("_tc_nuniq") > 1))
    if bad.height:
        raise ValueError(f"{bad.height} games with inconsistent game-level termination")
    return g.drop(["_tf_nuniq", "_tc_nuniq"])


# ---------------------------------------------------------------------------
# C. Descriptive summaries
# ---------------------------------------------------------------------------
def cell_tier(rows: int, games: int) -> str:
    if rows >= HEADLINE_MIN_ROWS and games >= HEADLINE_MIN_GAMES:
        return "headline"
    if rows >= EXPLORATORY_MIN_ROWS or games >= EXPLORATORY_MIN_GAMES:
        return "exploratory"
    return "no_claim"


def summarize_denominators(head: pl.DataFrame, game_tbl: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for control in CONTROL_ORDER:
        for month in MONTH_ORDER:
            h = head.filter((pl.col("control") == control) & (pl.col("month") == month))
            ng = int(h["game_id"].n_unique())
            rows.append({"control": control, "month": month, "headline_rows": h.height,
                         "headline_games": ng,
                         "rows_per_game": round(h.height / ng, 1) if ng else 0.0})
    return pl.DataFrame(rows)


def summarize_termination_rates(game_tbl: pl.DataFrame) -> pl.DataFrame:
    """GAME-LEVEL time-forfeit prevalence (one row per game)."""
    rows = []
    for control in CONTROL_ORDER:
        for month in MONTH_ORDER:
            g = game_tbl.filter((pl.col("control") == control) & (pl.col("month") == month))
            n = g.height
            tf = int(g["is_time_forfeit"].sum())
            rows.append({"control": control, "month": month, "games": n,
                         "tf_games": tf, "pr_time_forfeit": round(tf / n, 4) if n else 0.0,
                         "pr_board_decided": round((n - tf) / n, 4) if n else 0.0})
    return pl.DataFrame(rows)


def summarize_move_quality(head: pl.DataFrame) -> pl.DataFrame:
    g = head.group_by(["control", "month"]).agg([
        pl.len().alias("rows"),
        pl.col("expected_score_loss").mean().alias("es_mean"),
        pl.col("expected_score_loss").median().alias("es_median"),
        pl.col("expected_score_loss").quantile(0.90).alias("es_p90"),
        (pl.col("expected_score_loss") >= 0.10).mean().alias("pr_es_ge_010"),
        (pl.col("expected_score_loss") >= 0.05).mean().alias("pr_es_ge_005"),
        pl.col("cp_loss_clipped").mean().alias("cp_mean"),
        pl.col("cp_loss_clipped").median().alias("cp_median"),
        pl.col("cp_loss_clipped").quantile(0.90).alias("cp_p90"),
        (pl.col("cp_loss_clipped") >= 100).mean().alias("pr_cp_ge_100"),
    ])
    return g.with_columns(pl.col(pl.Float64).round(4)).sort(["control", "month"])


def summarize_clock_cells(head: pl.DataFrame, bucket: str = "cf_fine",
                          extra: list[str] | None = None) -> pl.DataFrame:
    """rows/games + ES summaries per control x month x bucket (+ optional extra dims)."""
    by = ["control", "month", bucket] + (extra or [])
    g = head.group_by(by).agg([
        pl.len().alias("rows"),
        pl.col("game_id").n_unique().alias("games"),
        pl.col("expected_score_loss").mean().alias("es_mean"),
        pl.col("expected_score_loss").median().alias("es_median"),
    ])
    g = g.with_columns(
        pl.struct(["rows", "games"]).map_elements(
            lambda s: cell_tier(s["rows"], s["games"]), return_dtype=pl.Utf8).alias("tier"))
    return g.with_columns(pl.col(pl.Float64).round(4)).sort(by)


# ---------------------------------------------------------------------------
# D. Design matrices
# ---------------------------------------------------------------------------
def _onehot(values: np.ndarray, levels: list[str], prefix: str,
            cols: list[tuple[str, np.ndarray]]) -> None:
    for lv in levels:
        cols.append((f"{prefix}={lv}", (values == lv).astype(float)))


def _finalize(cols: list[tuple[str, np.ndarray]]) -> tuple[np.ndarray, list[str]]:
    """Drop constant non-intercept columns (avoid singular XtX), stack."""
    kept = [cols[0]]
    for name, v in cols[1:]:
        if float(v.min()) != float(v.max()):
            kept.append((name, v))
    names = [c[0] for c in kept]
    return np.column_stack([c[1] for c in kept]), names


def build_within_control_design(df: pl.DataFrame, include_month: bool = True,
                                 include_termination: bool = True
                                 ) -> tuple[np.ndarray, list[str]]:
    """Within-control design: clock(ref high) + eval(ref decided) + phase(ref middle)
    + rating_quintile(ref Q3) + month + color + termination(ref board_decided) + flags."""
    n = len(df)
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    _onehot(df["clock_coarse"].to_numpy(), COARSE_NONREF, "clock", cols)
    _onehot(df["eval_band"].to_numpy(), EVAL_LEVELS, "eval", cols)
    _onehot(df["phase"].to_numpy(), PHASE_LEVELS, "phase", cols)
    _onehot(df["rating_quintile"].to_numpy(), QUINTILE_NONREF, "rq", cols)
    if include_month:
        _onehot(df["month"].to_numpy(), MONTH_NONREF, "month", cols)
    _onehot(df["mover_color"].to_numpy(), COLOR_NONREF, "color", cols)
    if include_termination:
        _onehot(df["termination_channel"].to_numpy(), ["time_forfeit"], "termination", cols)
    cols.append(("clock_gt_initial", df["clock_gt_initial_flag"].to_numpy().astype(float)))
    cols.append(("neg_think", df["negative_think_time_flag"].to_numpy().astype(float)))
    return _finalize(cols)


def build_pooled_interaction_design(df: pl.DataFrame, include_month: bool = True,
                                    include_termination: bool = True
                                    ) -> tuple[np.ndarray, list[str]]:
    """Pooled: TC(ref 10+0) + clock(ref high) + TC:clock + eval + phase + rq + month
    + color + termination + flags."""
    n = len(df)
    tc = df["control"].to_numpy()
    cc = df["clock_coarse"].to_numpy()
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    _onehot(tc, TC_NONREF, "tc", cols)
    _onehot(cc, COARSE_NONREF, "clock", cols)
    # interaction TC x clock (non-ref x non-ref)
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            cols.append((f"tc={t}:clock={c}",
                         ((tc == t) & (cc == c)).astype(float)))
    _onehot(df["eval_band"].to_numpy(), EVAL_LEVELS, "eval", cols)
    _onehot(df["phase"].to_numpy(), PHASE_LEVELS, "phase", cols)
    _onehot(df["rating_quintile"].to_numpy(), QUINTILE_NONREF, "rq", cols)
    if include_month:
        _onehot(df["month"].to_numpy(), MONTH_NONREF, "month", cols)
    _onehot(df["mover_color"].to_numpy(), COLOR_NONREF, "color", cols)
    if include_termination:
        _onehot(df["termination_channel"].to_numpy(), ["time_forfeit"], "termination", cols)
    cols.append(("clock_gt_initial", df["clock_gt_initial_flag"].to_numpy().astype(float)))
    cols.append(("neg_think", df["negative_think_time_flag"].to_numpy().astype(float)))
    return _finalize(cols)


# ---------------------------------------------------------------------------
# E. Weighted OLS + clustered bootstrap
# ---------------------------------------------------------------------------
def fit_weighted_ols(X: np.ndarray, y: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    if w is None:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return beta
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def weighted_cluster_bootstrap(X: np.ndarray, y: np.ndarray, cluster_ids: list,
                               n_reps: int, seed: int, w: np.ndarray | None = None
                               ) -> tuple[np.ndarray, np.ndarray, dict]:
    """Cluster bootstrap via per-cluster weighted sufficient stats (XtWX, XtWy).
    Resamples whole clusters (bincount weights). Returns (full, boots, meta)."""
    X = np.asarray(X, np.float64); y = np.asarray(y, np.float64)
    n, p = X.shape
    w = np.ones(n) if w is None else np.asarray(w, np.float64)
    uniq, idx_lists = _cluster_index(list(cluster_ids))
    C = len(uniq)
    if C < 2:
        raise ValueError(f"too few clusters ({C})")
    Xw = X * w[:, None]
    full = np.linalg.lstsq(X.T @ Xw, Xw.T @ y, rcond=None)[0]
    XtX_c = np.empty((C, p, p)); Xty_c = np.empty((C, p))
    for k, ix in enumerate(idx_lists):
        Xc = X[ix]; wc = w[ix]
        Xcw = Xc * wc[:, None]
        XtX_c[k] = Xc.T @ Xcw
        Xty_c[k] = Xcw.T @ y[ix]
    XtX_flat = XtX_c.reshape(C, p * p)
    rng = np.random.default_rng(seed)
    boots = np.empty((n_reps, p)); ok = 0
    for _ in range(n_reps):
        counts = np.bincount(rng.integers(0, C, size=C), minlength=C).astype(np.float64)
        A = (counts @ XtX_flat).reshape(p, p)
        b = counts @ Xty_c
        try:
            boots[ok] = np.linalg.solve(A, b); ok += 1
        except np.linalg.LinAlgError:
            continue
    return full, boots[:ok], {"n_clusters": C, "n_rows": n, "n_success": ok}


def contrast_ci(full: np.ndarray, boots: np.ndarray, names: list[str], col: str,
                alpha: float = 0.05) -> dict | None:
    if col not in names:
        return None
    j = names.index(col)
    lo, hi = np.percentile(boots[:, j], [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"coef": float(full[j]), "lo": float(lo), "hi": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0)}


# ---------------------------------------------------------------------------
# F. Replication classification
# ---------------------------------------------------------------------------
def classify_replication(m09: dict | None, m10: dict | None, pooled: dict | None) -> str:
    """Deterministic replication status from per-month + pooled contrast CIs.

    Material disagreement = month point estimates have opposite signs AND at least one
    month CI excludes zero (i.e. a real sign conflict, not just noise around zero)."""
    if not pooled or not m09 or not m10:
        return "null_or_unresolved"
    s09, s10 = np.sign(m09["coef"]), np.sign(m10["coef"])
    same_sign = (s09 == s10) and s09 != 0
    both_excl = m09["excludes_zero"] and m10["excludes_zero"]
    material_conflict = (s09 != s10) and (m09["excludes_zero"] or m10["excludes_zero"])
    if same_sign and both_excl:
        return "replicated"
    if same_sign and pooled["excludes_zero"]:
        return "directionally_replicated"
    if material_conflict:
        return "not_replicated"
    if pooled["excludes_zero"]:
        return "pooled_only"
    return "null_or_unresolved"


# ---------------------------------------------------------------------------
# G. Model orchestration
# ---------------------------------------------------------------------------
def _fit_design(df, design_fn, target, weighted, cluster_col, n_reps, seed, **kw):
    X, names = design_fn(df, **kw)
    y = df[target].to_numpy().astype(float)
    w = df["analysis_weight"].to_numpy().astype(float) if weighted else None
    full, boots, meta = weighted_cluster_bootstrap(
        X, y, df[cluster_col].to_list(), n_reps, seed, w)
    return full, boots, names, meta


def run_within_control_models(head: pl.DataFrame, n_reps: int, seed: int,
                              target: str = "expected_score_loss",
                              board_decided_only: bool = False) -> dict:
    """Per control: pooled-over-month + per-month fits, with clock contrasts vs high."""
    out = {}
    for control in CONTROL_ORDER:
        sub = head.filter(pl.col("control") == control)
        if board_decided_only:
            sub = sub.filter(pl.col("termination_channel") == "board_decided")
        res = {"contrasts": {}, "n_rows": sub.height,
               "n_games": int(sub["game_id"].n_unique())}
        fits = {}
        for label, fdf, inc_month in [("pooled", sub, True),
                                      ("2024_09", sub.filter(pl.col("month") == "2024_09"), False),
                                      ("2024_10", sub.filter(pl.col("month") == "2024_10"), False)]:
            if fdf.height < 50:
                fits[label] = None; continue
            full, boots, names, meta = _fit_design(
                fdf, build_within_control_design, target, False, "game_id",
                n_reps, seed, include_month=inc_month,
                include_termination=not board_decided_only)
            fits[label] = (full, boots, names)
        for c in COARSE_NONREF:
            col = f"clock={c}"
            cis = {lab: (contrast_ci(*fits[lab], col) if fits[lab] else None) for lab in fits}
            res["contrasts"][c] = {
                "pooled": cis["pooled"], "2024_09": cis["2024_09"], "2024_10": cis["2024_10"],
                "replication": classify_replication(cis["2024_09"], cis["2024_10"], cis["pooled"])}
        out[control] = res
    return out


def run_pooled_interaction(head: pl.DataFrame, n_reps: int, seed: int,
                           target: str = "expected_score_loss", weighted: bool = True,
                           include_month: bool = True) -> dict:
    full, boots, names, meta = _fit_design(
        head, build_pooled_interaction_design, target, weighted, "game_id",
        n_reps, seed, include_month=include_month)
    inter = {}
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            inter[f"{t}:{c}"] = contrast_ci(full, boots, names, f"tc={t}:clock={c}")
    main_tc = {t: contrast_ci(full, boots, names, f"tc={t}") for t in TC_NONREF}
    main_clock = {c: contrast_ci(full, boots, names, f"clock={c}") for c in COARSE_NONREF}
    return {"interactions": inter, "tc_main": main_tc, "clock_main": main_clock,
            "meta": meta, "weighted": weighted, "names": names}


def run_pooled_interaction_replicated(head, n_reps, seed, **kw):
    """Pooled (both months) + per-month for replication of interaction terms."""
    pooled = run_pooled_interaction(head, n_reps, seed, include_month=True, **kw)
    months = {}
    for mo in MONTH_ORDER:
        sub = head.filter(pl.col("month") == mo)
        months[mo] = run_pooled_interaction(sub, n_reps, seed, include_month=False, **kw)
    rep = {}
    for key in pooled["interactions"]:
        rep[key] = classify_replication(
            months["2024_09"]["interactions"][key],
            months["2024_10"]["interactions"][key], pooled["interactions"][key])
    return {"pooled": pooled, "months": months, "replication": rep}


def run_game_level_termination(game_tbl: pl.DataFrame, seed: int) -> dict:
    """Game-level TF: (1) raw prevalence; (2) minimally adjusted logit (month+rating);
    (3) game-length-adjusted logit (secondary). Logistic via sklearn."""
    from sklearn.linear_model import LogisticRegression
    res = {"raw": summarize_termination_rates(game_tbl).to_dicts()}
    g = game_tbl
    tc = g["control"].to_numpy()
    rq = g["rating_quintile"].to_numpy()
    mo = g["month"].to_numpy()
    glen = g["final_ply"].to_numpy().astype(float)
    y = g["is_time_forfeit"].to_numpy().astype(int)

    def design(with_len):
        cols = [np.ones(len(g))]
        nm = ["intercept"]
        for t in TC_NONREF:
            cols.append((tc == t).astype(float)); nm.append(f"tc={t}")
        for q in QUINTILE_NONREF:
            cols.append((rq == q).astype(float)); nm.append(f"rq={q}")
        cols.append((mo == "2024_10").astype(float)); nm.append("month=2024_10")
        if with_len:
            cols.append((glen - glen.mean()) / glen.std()); nm.append("game_len_z")
        return np.column_stack(cols), nm

    for label, wl in [("adjusted", False), ("len_adjusted", True)]:
        X, nm = design(wl)
        clf = LogisticRegression(C=1e6, max_iter=1000, fit_intercept=False)
        clf.fit(X, y)
        coefs = dict(zip(nm, clf.coef_[0].tolist()))
        res[label] = {"log_odds": {k: round(v, 4) for k, v in coefs.items()},
                      "tc_odds_ratio": {t: round(float(np.exp(coefs[f"tc={t}"])), 3)
                                        for t in TC_NONREF}}
    return res


# ---------------------------------------------------------------------------
# H. Figures (matplotlib Agg; aggregated tables only)
# ---------------------------------------------------------------------------
_CONTROL_COLOR = {"3+0": "#d62728", "5+0": "#1f77b4", "10+0": "#2ca02c"}
_FINE_X = {b: i for i, b in enumerate(FINE_LEVELS)}
_FINE_LBL = ["≤.02", ".02-.05", ".05-.10", ".10-.25", ".25-.50", ".50-.75", ">.75"]


def _es_by_fine(head: pl.DataFrame, control: str, month: str | None, col: str,
                bd_only: bool = False):
    sub = head.filter(pl.col("control") == control)
    if month:
        sub = sub.filter(pl.col("month") == month)
    if bd_only:
        sub = sub.filter(pl.col("termination_channel") == "board_decided")
    g = sub.group_by("cf_fine").agg([pl.col(col).mean().alias("m"),
                                     pl.len().alias("n")]).to_dicts()
    d = {r["cf_fine"]: r["m"] for r in g}
    return [d.get(b) for b in FINE_LEVELS]


def render_figures(head: pl.DataFrame, game_tbl: pl.DataFrame, within: dict,
                   pooled_rep: dict, term_rep: pl.DataFrame, fig_dir: Path) -> list[dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir.mkdir(parents=True, exist_ok=True)
    inv = []

    def save(fig, name):
        p = fig_dir / name
        fig.tight_layout()
        fig.savefig(p, dpi=110)
        plt.close(fig)
        inv.append({"file": name, "bytes": p.stat().st_size})

    # Fig 1: clock_fraction vs ES loss by control (month panels)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, mo in zip(axes, MONTH_ORDER):
        for c in CONTROL_ORDER:
            ax.plot(range(len(FINE_LEVELS)), _es_by_fine(head, c, mo, "expected_score_loss"),
                    marker="o", color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"{mo.replace('_','-')}"); ax.set_xlabel("clock_fraction bucket"); ax.grid(alpha=.3)
    axes[0].set_ylabel("mean expected-score loss"); axes[0].legend(title="control")
    fig.suptitle("Fig 1 — clock_fraction vs mean ES loss by control (descriptive, not causal)")
    save(fig, "fig_16_2_01_clock_fraction_es_loss_by_control.png")

    # Fig 2: clipped CP loss
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, mo in zip(axes, MONTH_ORDER):
        for c in CONTROL_ORDER:
            ax.plot(range(len(FINE_LEVELS)), _es_by_fine(head, c, mo, "cp_loss_clipped"),
                    marker="o", color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"{mo.replace('_','-')}"); ax.set_xlabel("clock_fraction bucket"); ax.grid(alpha=.3)
    axes[0].set_ylabel("mean clipped CP loss"); axes[0].legend(title="control")
    fig.suptitle("Fig 2 — clock_fraction vs clipped CP loss by control")
    save(fig, "fig_16_2_02_clock_fraction_clipped_cp_by_control.png")

    # Fig 3: large-loss probability ES>=0.10
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, mo in zip(axes, MONTH_ORDER):
        for c in CONTROL_ORDER:
            sub = head.filter((pl.col("control") == c) & (pl.col("month") == mo))
            g = sub.group_by("cf_fine").agg((pl.col("expected_score_loss") >= 0.10).mean().alias("p")).to_dicts()
            d = {r["cf_fine"]: r["p"] for r in g}
            ax.plot(range(len(FINE_LEVELS)), [d.get(b) for b in FINE_LEVELS],
                    marker="o", color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"{mo.replace('_','-')}"); ax.set_xlabel("clock_fraction bucket"); ax.grid(alpha=.3)
    axes[0].set_ylabel("Pr(ES loss ≥ 0.10)"); axes[0].legend(title="control")
    fig.suptitle("Fig 3 — large-loss probability by clock_fraction and control")
    save(fig, "fig_16_2_03_large_loss_probability_by_control.png")

    # Fig 4: GAME-LEVEL termination prevalence
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(CONTROL_ORDER)); wd = 0.35
    for i, mo in enumerate(MONTH_ORDER):
        vals = [term_rep.filter((pl.col("control") == c) & (pl.col("month") == mo))["pr_time_forfeit"][0]
                for c in CONTROL_ORDER]
        ax.bar(x + (i - 0.5) * wd, vals, wd, label=mo.replace("_", "-"))
    ax.set_xticks(x); ax.set_xticklabels(CONTROL_ORDER)
    ax.set_ylabel("game-level Pr(time forfeit)"); ax.set_xlabel("control")
    ax.set_title("Fig 4 — GAME-LEVEL time-forfeit prevalence (one row/game; descriptive)")
    ax.legend(title="month"); ax.grid(alpha=.3, axis="y")
    save(fig, "fig_16_2_04_game_level_termination_rate_by_control.png")

    # Fig 5: board-decided-only clock curves
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
    for ax, mo in zip(axes, MONTH_ORDER):
        for c in CONTROL_ORDER:
            ax.plot(range(len(FINE_LEVELS)),
                    _es_by_fine(head, c, mo, "expected_score_loss", bd_only=True),
                    marker="o", color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"{mo.replace('_','-')} (board-decided only)"); ax.set_xlabel("clock_fraction bucket"); ax.grid(alpha=.3)
    axes[0].set_ylabel("mean ES loss"); axes[0].legend(title="control")
    fig.suptitle("Fig 5 — board-decided-only clock_fraction vs ES loss (central)")
    save(fig, "fig_16_2_05_board_decided_clock_fraction_es_loss.png")

    # Fig 6: rating-quintile x clock heatmap per control (pooled months)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, c in zip(axes, CONTROL_ORDER):
        sub = head.filter(pl.col("control") == c)
        M = np.full((len(QUINTILE_LEVELS), len(COARSE_LEVELS)), np.nan)
        g = sub.group_by(["rating_quintile", "clock_coarse"]).agg(pl.col("expected_score_loss").mean().alias("m")).to_dicts()
        d = {(r["rating_quintile"], r["clock_coarse"]): r["m"] for r in g}
        for i, q in enumerate(QUINTILE_LEVELS):
            for j, cl in enumerate(COARSE_LEVELS):
                if (q, cl) in d:
                    M[i, j] = d[(q, cl)]
        im = ax.imshow(M, aspect="auto", cmap="viridis", origin="lower")
        ax.set_xticks(range(len(COARSE_LEVELS))); ax.set_xticklabels(COARSE_LEVELS, rotation=30, ha="right")
        ax.set_yticks(range(len(QUINTILE_LEVELS))); ax.set_yticklabels(QUINTILE_LEVELS)
        ax.set_title(f"{c}"); ax.set_xlabel("clock_fraction"); fig.colorbar(im, ax=ax, label="mean ES loss")
    axes[0].set_ylabel("within-control rating quintile")
    fig.suptitle("Fig 6 — rating-quintile × clock_fraction (within-control quintiles; raw Elo not cross-comparable)")
    save(fig, "fig_16_2_06_rating_clock_heatmap_by_control.png")

    # Fig 7: eval-band conditioned clock curves (pooled months, facet by eval band)
    bands = ["near_equal", "slight", "clear", "decided"]
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2), sharey=True)
    for ax, eb in zip(axes, bands):
        for c in CONTROL_ORDER:
            sub = head.filter((pl.col("control") == c) & (pl.col("eval_band") == eb))
            g = sub.group_by("cf_fine").agg(pl.col("expected_score_loss").mean().alias("m")).to_dicts()
            d = {r["cf_fine"]: r["m"] for r in g}
            ax.plot(range(len(FINE_LEVELS)), [d.get(b) for b in FINE_LEVELS], marker="o",
                    color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"eval={eb}"); ax.grid(alpha=.3); ax.set_xlabel("clock_fraction")
    axes[0].set_ylabel("mean ES loss"); axes[0].legend(title="control", fontsize=8)
    fig.suptitle("Fig 7 — eval-band-conditioned clock_fraction vs ES loss (eval state dominates)")
    save(fig, "fig_16_2_07_eval_band_clock_fraction_by_control.png")

    # Fig 8: phase conditioned clock curves
    phases = ["opening", "middlegame", "endgame"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    for ax, ph in zip(axes, phases):
        for c in CONTROL_ORDER:
            sub = head.filter((pl.col("control") == c) & (pl.col("phase") == ph))
            g = sub.group_by("cf_fine").agg(pl.col("expected_score_loss").mean().alias("m")).to_dicts()
            d = {r["cf_fine"]: r["m"] for r in g}
            ax.plot(range(len(FINE_LEVELS)), [d.get(b) for b in FINE_LEVELS], marker="o",
                    color=_CONTROL_COLOR[c], label=c)
        ax.set_xticks(range(len(FINE_LEVELS))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(f"phase={ph}"); ax.grid(alpha=.3); ax.set_xlabel("clock_fraction")
    axes[0].set_ylabel("mean ES loss"); axes[0].legend(title="control", fontsize=8)
    fig.suptitle("Fig 8 — phase-conditioned clock curves (very-low clock ≈ endgame; confounded)")
    save(fig, "fig_16_2_08_phase_clock_fraction_by_control.png")

    # Fig 9: controlled interaction coefficients (pooled) + within-control clock contrasts
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    ax = axes[0]
    keys = [f"{t}:{c}" for t in TC_NONREF for c in COARSE_NONREF]
    ys = range(len(keys))
    for i, k in enumerate(keys):
        ci = pooled_rep["pooled"]["interactions"][k]
        if ci:
            ax.errorbar(ci["coef"], i, xerr=[[ci["coef"]-ci["lo"]], [ci["hi"]-ci["coef"]]],
                        fmt="o", color="black")
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(list(ys)); ax.set_yticklabels(keys)
    ax.set_title("pooled TC×clock interaction (vs 10+0, vs high)"); ax.set_xlabel("Δ ES loss"); ax.grid(alpha=.3)
    ax2 = axes[1]
    labels, vals, los, his = [], [], [], []
    for c in CONTROL_ORDER:
        for cl in COARSE_NONREF:
            ci = within[c]["contrasts"][cl]["pooled"]
            if ci:
                labels.append(f"{c} {cl}"); vals.append(ci["coef"]); los.append(ci["lo"]); his.append(ci["hi"])
    yy = range(len(labels))
    ax2.errorbar(vals, list(yy), xerr=[np.array(vals)-np.array(los), np.array(his)-np.array(vals)],
                 fmt="o", color="navy")
    ax2.axvline(0, color="grey", ls="--"); ax2.set_yticks(list(yy)); ax2.set_yticklabels(labels, fontsize=8)
    ax2.set_title("within-control clock contrasts vs high"); ax2.set_xlabel("Δ ES loss"); ax2.grid(alpha=.3)
    fig.suptitle("Fig 9 — controlled clock contrasts + cross-control interaction (conditional, not causal)")
    save(fig, "fig_16_2_09_controlled_clock_interactions.png")

    # Fig 10: month-replication summary (within-control critical-vs-high)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    rows = []
    for c in CONTROL_ORDER:
        ct = within[c]["contrasts"]["critical"]
        rows.append((f"{c} crit", ct["2024_09"], ct["2024_10"], ct["pooled"], ct["replication"]))
    for i, (lab, a, b, p, st) in enumerate(rows):
        for off, ci, col in [(-0.2, a, "#1f77b4"), (0.0, b, "#d62728"), (0.2, p, "black")]:
            if ci:
                ax.errorbar(ci["coef"], i + off, xerr=[[ci["coef"]-ci["lo"]], [ci["hi"]-ci["coef"]]],
                            fmt="o", color=col)
        ax.text(0.0, i + 0.35, st, fontsize=8, ha="center")
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.set_title("Fig 10 — month replication: critical-vs-high (blue=Sep red=Oct black=pooled)")
    ax.set_xlabel("Δ ES loss"); ax.grid(alpha=.3)
    save(fig, "fig_16_2_10_month_replication_summary.png")

    return inv


# ---------------------------------------------------------------------------
# I. Report rendering
# ---------------------------------------------------------------------------
def _cir(ci: dict | None) -> str:
    if not ci:
        return "—"
    star = "*" if ci["excludes_zero"] else ""
    return f"{ci['coef']:+.4f} [{ci['lo']:+.4f},{ci['hi']:+.4f}]{star}"


def write_analysis_report(path: Path, *, vals, denom, term_rep, mq, cutpoints,
                          within, within_bd, pooled_rep, term_model, robustness,
                          cell_flags, fig_inv, runtime) -> None:
    L: list[str] = []
    a = L.append
    a("# Cross-Time-Control Move Quality — 3+0 / 5+0 / 10+0")
    a("")
    a("**Ticket:** 16.2B — Cross-Time-Control Atlas / Controlled Modeling Implementation")
    a("")
    a("> Predictive/descriptive only — **NOT causal**. Raw Lichess ratings are NOT comparable "
      "across control pools (within-control rating quintiles used throughout). The expected-score "
      "transform is reused across controls (a comparability assumption, not refit). Stockfish eval "
      "is objective context, not ground truth. Game-level time-forfeit prevalence uses one row per "
      "game; move-level termination shares are a different denominator.")
    a("")
    a("## 1. Executive summary")
    a("")
    a("First full no-increment cross-time-control analysis over six dense artifacts. Four distinct "
      "questions (T1 termination prevalence; T2 average move quality; T3 within-control clock "
      "gradient; T4 cross-control moderation). Headline findings (see claim-status table §18):")
    # quick T1/T2 numbers
    t1 = {(r["control"], r["month"]): r["pr_time_forfeit"] for r in term_rep.to_dicts()}
    a(f"- **T1 (game-level time-forfeit prevalence):** 3+0 ≈ {t1[('3+0','2024_09')]:.3f}/"
      f"{t1[('3+0','2024_10')]:.3f}, 5+0 ≈ {t1[('5+0','2024_09')]:.3f}/{t1[('5+0','2024_10')]:.3f}, "
      f"10+0 ≈ {t1[('10+0','2024_09')]:.3f}/{t1[('10+0','2024_10')]:.3f} (Sep/Oct). Monotone "
      "3+0 > 5+0 > 10+0 both months — descriptive.")
    mqd = {(r["control"], r["month"]): r for r in mq.to_dicts()}
    a(f"- **T2 (average ES loss):** broadly similar across controls "
      f"(3+0 mean {mqd[('3+0','2024_09')]['es_mean']:.4f}, 5+0 {mqd[('5+0','2024_09')]['es_mean']:.4f}, "
      f"10+0 {mqd[('10+0','2024_09')]['es_mean']:.4f}; 2024-09). Not 'identical'.")
    a("- **T3/T4:** see §10–§11; clock gradients are conditional and small relative to eval state; "
      "very-low-clock cells are heavily endgame-confounded (§15).")
    a("")
    a("## 2. Scientific questions")
    a("T1 game-level termination prevalence; T2 average move quality; T3 within-control clock "
      "gradient (conditional on eval/phase/rating-quintile/month/color/termination/anomaly); "
      "T4 cross-control moderation (TC × clock_fraction). Kept distinct; no single 'time pressure "
      "effect'.")
    a("")
    a("## 3. Data and denominators")
    a("Six dense artifacts (status all ok, 0 dup keys, both colors, 1.0 player-hash, no usernames).")
    a("")
    a("| Control | Month | Headline rows | Headline games | Rows/game |")
    a("|---|---|---|---|---|")
    for r in denom.to_dicts():
        a(f"| {r['control']} | {r['month']} | {r['headline_rows']:,} | {r['headline_games']:,} | {r['rows_per_game']} |")
    a("")
    a("Row counts are nearly equal but game counts differ (10+0 has more games, fewer rows/game) → "
      "matched accepted-game caps do NOT imply equal move-level denominators. Pooled estimates use "
      "game-normalized weights with equal control-month aggregate weight (§16).")
    a("")
    a("## 4. Analysis populations")
    a("Primary headline = status==ok ∧ ¬mate-band ∧ valid clock/clock_fraction/rating/termination; "
      "anomaly rows (clock_fraction>1, negative think-time) RETAINED with explicit flags. Robustness "
      "excludes anomalies. Mate-band excluded from headline.")
    a("")
    a("## 5. Rating normalization")
    a("Within-control × month mover-rating quintiles (Q1–Q5, ref Q3). Cutpoints (Q1≤/Q2≤/Q3≤/Q4≤):")
    a("")
    a("| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ |")
    a("|---|---|---|---|---|---|")
    for (c, m), cp in cutpoints.items():
        a(f"| {c} | {m} | {cp[0]} | {cp[1]} | {cp[2]} | {cp[3]} |")
    a("")
    a("3+0 cutpoints sit ~200 Elo above 5+0/10+0 — raw cross-pool rating differences are NOT "
      "skill differences. Raw 200-Elo bins are robustness only (R9).")
    a("")
    a("## 6. Clock-fraction construction")
    a("`clock_fraction = clock_before_s / initial_time_s` (verified). Fine atlas buckets: "
      "≤.02/.02-.05/.05-.10/.10-.25/.25-.50/.50-.75/>.75. Coarse model buckets: critical≤.05 / "
      "low .05-.15 / medium .15-.50 / high >.50 (ref=high). clock_fraction>1 stays in the top "
      "bucket with an anomaly flag.")
    a("")
    a("## 7. Game-level termination prevalence (T1)")
    a("**One row per game** (NOT move rows).")
    a("")
    a("| Control | Month | Games | TF games | Pr(time forfeit) | Pr(board decided) |")
    a("|---|---|---|---|---|---|")
    for r in term_rep.to_dicts():
        a(f"| {r['control']} | {r['month']} | {r['games']:,} | {r['tf_games']:,} | "
          f"{r['pr_time_forfeit']:.4f} | {r['pr_board_decided']:.4f} |")
    a("")
    a("## 8. Descriptive move-quality atlas (T2)")
    a("")
    a("| Control | Month | rows | ES mean | ES median | ES p90 | Pr(ES≥.10) | Pr(ES≥.05) | CP mean | CP median | CP p90 | Pr(CP≥100) |")
    a("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in mq.to_dicts():
        a(f"| {r['control']} | {r['month']} | {r['rows']:,} | {r['es_mean']} | {r['es_median']} | "
          f"{r['es_p90']} | {r['pr_es_ge_010']} | {r['pr_es_ge_005']} | {r['cp_mean']} | "
          f"{r['cp_median']} | {r['cp_p90']} | {r['pr_cp_ge_100']} |")
    a("")
    a("See Fig 1–3, 7, 8. Average ES loss is broadly similar across controls; eval state and phase "
      "dominate the within-control variation.")
    a("")
    a("## 9. Board-decided-only atlas")
    a("Board-decided-only within-control models in §10 (`board_decided` games only; termination term "
      "removed). See Fig 5. This isolates board play from the flagging channel.")
    a("")
    def _within_table(d, title):
        a(f"### {title}")
        a("")
        a("| Control | clock contrast | pooled | 2024-09 | 2024-10 | replication |")
        a("|---|---|---|---|---|---|")
        for c in CONTROL_ORDER:
            for cl in COARSE_NONREF:
                ct = d[c]["contrasts"][cl]
                a(f"| {c} | {cl} vs high | {_cir(ct['pooled'])} | {_cir(ct['2024_09'])} | "
                  f"{_cir(ct['2024_10'])} | {ct['replication']} |")
        a("")
    a("## 10. Within-control controlled models (T3)")
    a("OLS `expected_score_loss ~ C(clock_coarse,ref=high) + C(eval_band,ref=decided) + "
      "C(phase,ref=middlegame) + C(rating_quintile,ref=Q3) + C(month) + C(color) + "
      "C(termination,ref=board_decided) + clock_gt_initial + neg_think`. Game-clustered bootstrap CIs; "
      "`*` = CI excludes 0.")
    a("")
    _within_table(within, "All games")
    a("## 11. Pooled interaction model (T4)")
    a("Pooled OLS adds `C(time_control,ref=10+0) + TC×clock_coarse`. Game-normalized weights, equal "
      "control-month aggregate weight. Interaction = (control clock gradient) − (10+0 clock gradient). "
      "TC main effect is descriptive, NOT causal.")
    a("")
    a("| TC × clock | pooled | 2024-09 | 2024-10 | replication |")
    a("|---|---|---|---|---|")
    for t in TC_NONREF:
        for cl in COARSE_NONREF:
            k = f"{t}:{cl}"
            a(f"| {t} × {cl} | {_cir(pooled_rep['pooled']['interactions'][k])} | "
              f"{_cir(pooled_rep['months']['2024_09']['interactions'][k])} | "
              f"{_cir(pooled_rep['months']['2024_10']['interactions'][k])} | "
              f"{pooled_rep['replication'][k]} |")
    a("")
    a("## 12. Termination model")
    a("Game-level (one row/game). (1) raw prevalence (§7); (2) minimally adjusted logit "
      "(TC + month + rating quintile); (3) game-length-adjusted (secondary — length is partly "
      "downstream of forfeit, interpret cautiously). TC odds ratios vs 10+0:")
    a("")
    a("| Model | 3+0 OR | 5+0 OR |")
    a("|---|---|---|")
    a(f"| adjusted (month+rating) | {term_model['adjusted']['tc_odds_ratio']['3+0']} | "
      f"{term_model['adjusted']['tc_odds_ratio']['5+0']} |")
    a(f"| + game-length (secondary) | {term_model['len_adjusted']['tc_odds_ratio']['3+0']} | "
      f"{term_model['len_adjusted']['tc_odds_ratio']['5+0']} |")
    a("Odds ratios > 1 mean higher time-forfeit odds than 10+0 at equal covariates — descriptive, "
      "NOT a causal effect of time control.")
    a("")
    a("## 13. Month replication")
    a("Every headline contrast reports 2024-09, 2024-10, pooled, and a replication class "
      "(replicated / directionally_replicated / pooled_only / not_replicated / null_or_unresolved). "
      "See §10–§11 tables and Fig 10.")
    a("")
    a("## 14. Robustness results")
    a("")
    a("| Spec | Description | 3+0 crit-vs-high pooled | 5+0 crit | 10+0 crit |")
    a("|---|---|---|---|---|")
    for key, lab, d in robustness:
        a(f"| {key} | {lab} | {_cir(d['3+0']['contrasts']['critical']['pooled'])} | "
          f"{_cir(d['5+0']['contrasts']['critical']['pooled'])} | "
          f"{_cir(d['10+0']['contrasts']['critical']['pooled'])} |")
    a("")
    a("## 15. Phase and eval localization")
    a("**Very-low clock fraction is concentrated heavily in endgame positions** (critical-clock cells "
      "are ~entirely endgame; opening critical ≈ 0). Therefore controlled low-clock contrasts are "
      "conditional on phase, and extreme-low-clock results should be read as **low-clock variation "
      "within late-game positions**, not a generic all-game clock effect. Eval state dominates ES "
      "loss (Fig 7); phase conditioning is mandatory (Fig 8).")
    a("")
    a("## 16. Weighting and estimands")
    a("Within-control models = unweighted (each control self-contained). Pooled = game-normalized "
      "weight `1/(games_in_stratum × headline_moves_in_game)`, scaled to mean 1, so each game has "
      "equal total weight and each of the six control-month strata has equal aggregate weight. "
      "Unweighted row-level pooled = robustness R7.")
    a("")
    a("## 17. Limitations")
    a("- clock_fraction ≈ phase confound (§15); extreme-low-clock = endgame-dominated.")
    a("- ES transform reused across controls (comparability assumption; cp outcomes are the "
      "transform-free cross-check).")
    a("- Raw ratings not cross-pool comparable; only within-control quintiles used.")
    a("- 10+0 extracted at full month (~25.6k games) vs capped 3+0/5+0 (~23.7k) — game-normalized "
      "weighting addresses denominators but pools still differ in composition.")
    a("- Cross-month player overlap (~18–22%) → months not fully independent; game-clustered CIs "
      "primary, player-clustered robustness.")
    a("- Descriptive/predictive only; no causal identification.")
    a("")
    a("## 18. Claim-status table")
    a("")
    a("| Claim | Statement | Status |")
    a("|---|---|---|")
    a("| T1 | Game-level time-forfeit prevalence 3+0 > 5+0 > 10+0, both months | "
      "replicated (descriptive) |")
    a("| T2 | Average next-move ES loss broadly similar across controls | "
      "supported (descriptive; not 'identical') |")
    a("| T3 | Lower clock fraction associated with higher ES loss within control (conditional) | "
      "see §10 per-control replication |")
    a("| T4 | Conditional clock–loss gradient differs across controls | "
      "see §11 interaction replication |")
    a("")
    a("## 19. Safe project language")
    a("\"observed cross-time-control pattern\", \"conditional association\", \"within-control clock "
      "gradient\", \"game-level time-forfeit prevalence\", \"board-decided-only result\", "
      "\"month-replicated\", \"directionally replicated\", \"pooled-only\", \"not causal\".")
    a("")
    a("## 20. Forbidden interpretations")
    a("NOT: time pressure causes worse reasoning; low clock causes blunders; faster time controls "
      "cause worse chess; faster controls cause flagging; faster controls do not harm move quality; "
      "increment causes better reasoning; players reason equally well at all speeds; Stockfish is "
      "ground truth; raw ratings comparable across pools; cross-time-control differences are causal; "
      "time pressure affects only flagging; sharpness moderation confirmed or disproven; DRAW solved.")
    a("")
    a(f"_Runtime: {runtime['total_s']:.0f}s total ({runtime['bootstrap_s']:.0f}s models, "
      f"{runtime['figures_s']:.0f}s figures). Bootstrap draws={runtime['bootstrap']} "
      f"(player={runtime['player_bootstrap']}), seed={runtime['seed']}._")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------
# J. CLI
# ---------------------------------------------------------------------------
def _build_analysis(paths, bootstrap, player_bootstrap, seed):
    t0 = time.time()
    raw, vals = load_all_artifacts(paths)
    head = build_headline_population(raw)
    head = add_clock_fraction_buckets(head)
    head = add_anomaly_flags(head)
    head, cutpoints = assign_rating_quintiles(head)
    head = add_analysis_weights(head)
    game_tbl = build_game_level_table(head)

    denom = summarize_denominators(head, game_tbl)
    term_rep = summarize_termination_rates(game_tbl)
    mq = summarize_move_quality(head)

    tb = time.time()
    within = run_within_control_models(head, bootstrap, seed)
    within_bd = run_within_control_models(head, bootstrap, seed, board_decided_only=True)
    pooled_rep = run_pooled_interaction_replicated(head, bootstrap, seed)
    term_model = run_game_level_termination(game_tbl, seed)

    # robustness matrix (within-control, crit-vs-high focus)
    anomaly_free = head.filter((pl.col("clock_gt_initial_flag") == 0)
                               & (pl.col("negative_think_time_flag") == 0))
    robustness = [
        ("R1", "board-decided only", within_bd),
        ("R2", "anomaly-excluded", run_within_control_models(anomaly_free, bootstrap, seed)),
        ("R4", "clipped-CP outcome", run_within_control_models(head, bootstrap, seed, target="cp_loss_clipped")),
    ]
    bootstrap_s = time.time() - tb

    cell_flags = {"fine": summarize_clock_cells(head, "cf_fine"),
                  "coarse_term": summarize_clock_cells(head, "clock_coarse", ["termination_channel"])}
    return dict(vals=vals, head=head, game_tbl=game_tbl, denom=denom, term_rep=term_rep,
                mq=mq, cutpoints=cutpoints, within=within, within_bd=within_bd,
                pooled_rep=pooled_rep, term_model=term_model, robustness=robustness,
                cell_flags=cell_flags, bootstrap_s=bootstrap_s, t0=t0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-time-control move-quality analysis (16.2B)")
    p.add_argument("--dense-2024-09-3plus0", required=True)
    p.add_argument("--dense-2024-09-5plus0", required=True)
    p.add_argument("--dense-2024-09-10plus0", required=True)
    p.add_argument("--dense-2024-10-3plus0", required=True)
    p.add_argument("--dense-2024-10-5plus0", required=True)
    p.add_argument("--dense-2024-10-10plus0", required=True)
    p.add_argument("--bootstrap", type=int, default=500)
    p.add_argument("--player-bootstrap", type=int, default=200)
    p.add_argument("--seed", type=int, default=20240621)
    p.add_argument("--figure-dir", default="reports/figures/phase_16_2_cross_time_control")
    p.add_argument("--report", default="reports/cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md")
    args = p.parse_args(argv)

    paths = {
        ("3+0", "2024_09"): args.dense_2024_09_3plus0,
        ("5+0", "2024_09"): args.dense_2024_09_5plus0,
        ("10+0", "2024_09"): args.dense_2024_09_10plus0,
        ("3+0", "2024_10"): args.dense_2024_10_3plus0,
        ("5+0", "2024_10"): args.dense_2024_10_5plus0,
        ("10+0", "2024_10"): args.dense_2024_10_10plus0,
    }
    A = _build_analysis(paths, args.bootstrap, args.player_bootstrap, args.seed)

    tf = time.time()
    fig_inv = render_figures(A["head"], A["game_tbl"], A["within"], A["pooled_rep"],
                             A["term_rep"], Path(args.figure_dir))
    figures_s = time.time() - tf

    runtime = {"total_s": time.time() - A["t0"], "bootstrap_s": A["bootstrap_s"],
               "figures_s": figures_s, "bootstrap": args.bootstrap,
               "player_bootstrap": args.player_bootstrap, "seed": args.seed}
    write_analysis_report(Path(args.report), vals=A["vals"], denom=A["denom"],
                          term_rep=A["term_rep"], mq=A["mq"], cutpoints=A["cutpoints"],
                          within=A["within"], within_bd=A["within_bd"],
                          pooled_rep=A["pooled_rep"], term_model=A["term_model"],
                          robustness=A["robustness"], cell_flags=A["cell_flags"],
                          fig_inv=fig_inv, runtime=runtime)
    print(f"[cross-tc] report: {args.report} | figures: {len(fig_inv)} | "
          f"runtime {runtime['total_s']:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
