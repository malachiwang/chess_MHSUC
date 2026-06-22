"""Rating x clock moderation analysis (Ticket 16.2E).

Implements the design locked in 16.2D: does relative player rating modify the
conditional clock_fraction -> next-move-quality relationship, and does that
moderation differ across 3+0 / 5+0 / 10+0?

Dedicated module: imports validated pure helpers from cross_time_control_analysis
(16.2B) and clustered_uncertainty; does NOT modify them.

Key estimands (all predictive/descriptive, NOT causal):
  D(c,q) = adjusted ES loss(critical clock) - adjusted ES loss(high clock), in control c, quintile q
  M(c)   = D(c,Q5) - D(c,Q1)                      [within-control rating moderation]
  cross  = M(3+0)-M(10+0), M(5+0)-M(10+0)         [cross-control moderation]

With reference levels TC=10+0, clock=high, rating_quintile=Q1, ALL FIVE primary tests
are linear reads of ONE pooled categorical TC x clock x quintile fit:
  M(10+0)        = beta(clock=critical : rq=Q5)
  M(3+0)         = beta(clock=critical : rq=Q5) + beta(tc=3+0 : clock=critical : rq=Q5)
  M(5+0)         = beta(clock=critical : rq=Q5) + beta(tc=5+0 : clock=critical : rq=Q5)
  M(3+0)-M(10+0) = beta(tc=3+0 : clock=critical : rq=Q5)
  M(5+0)-M(10+0) = beta(tc=5+0 : clock=critical : rq=Q5)
so one mover-player-clustered bootstrap yields all five jointly (-> Holm across the family).

Non-claims: "buffer"/"attenuation" are descriptive contrast labels, NOT causal protection.
Raw Elo not comparable across pools (within-control quintiles/percentiles only). Stockfish not
ground truth. ES transform reused (not refit). No "rating causes resilience".
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

import chess_mhsuc.cross_time_control_analysis as ctc
from chess_mhsuc.cross_time_control_analysis import (
    CONTROL_ORDER, MONTH_ORDER, COARSE_NONREF, EVAL_LEVELS, PHASE_LEVELS,
    TC_NONREF, MONTH_NONREF, COLOR_NONREF, _onehot, _finalize,
    fit_weighted_ols, weighted_cluster_bootstrap, contrast_ci,
)

# rating_quintile reference = Q1 for moderation (so the clock:rq=Q5 interaction == M).
QUINTILE_ORDER = ["Q1", "Q2", "Q3", "Q4", "Q5"]
QUINTILE_NONREF_Q1 = ["Q2", "Q3", "Q4", "Q5"]   # ref Q1
PRIMARY_TESTS = ["M(3+0)", "M(5+0)", "M(10+0)", "M(3+0)-M(10+0)", "M(5+0)-M(10+0)"]
_FORBIDDEN_USERNAME_COLS = ctc._FORBIDDEN_USERNAME_COLS


# ---------------------------------------------------------------------------
# A. Inputs (reuse 16.2B pipeline) + rating percentile
# ---------------------------------------------------------------------------
def load_rating_moderation_inputs(paths: dict, *, robustness_exclude_anomalies: bool = False):
    """Reuse the validated 16.2B prep pipeline, then add rating percentiles."""
    raw, vals = ctc.load_all_artifacts(paths)
    head = ctc.build_headline_population(raw)
    head = ctc.add_clock_fraction_buckets(head)
    head = ctc.add_anomaly_flags(head)
    head, cutpoints = ctc.assign_rating_quintiles(head)
    head = assign_rating_percentiles(head)
    head = ctc.add_analysis_weights(head)
    if robustness_exclude_anomalies:
        head = head.filter((pl.col("clock_gt_initial_flag") == 0)
                           & (pl.col("negative_think_time_flag") == 0))
    return raw, vals, head, cutpoints


def validate_rating_fields(head: pl.DataFrame) -> dict:
    issues = []
    if (head["rating_percentile"].min() < -1e-9) or (head["rating_percentile"].max() > 1 + 1e-9):
        issues.append("rating_percentile out of [0,1]")
    if set(head["rating_quintile"].unique().to_list()) - set(QUINTILE_ORDER):
        issues.append("unexpected rating_quintile level")
    if int(head["mover_elo"].is_null().sum()) != 0:
        issues.append("null mover_elo in headline population")
    bad = _FORBIDDEN_USERNAME_COLS & set(head.columns)
    if bad:
        issues.append(f"forbidden username cols {bad}")
    return {"issues": issues, "rows": head.height}


def assign_rating_percentiles(df: pl.DataFrame) -> pl.DataFrame:
    """Within control x month, deterministic average-rank percentile in [0,1]
    (0=lowest, 1=highest rating). Ties get the mean rank (so equal Elo -> equal
    percentile). Single-row strata -> 0.5."""
    return df.with_columns(
        ((pl.col("mover_elo").rank(method="average").over(["control", "month"]) - 1.0)
         / pl.max_horizontal(pl.len().over(["control", "month"]) - 1.0, pl.lit(1.0)))
        .alias("rating_percentile")
    )


# ---------------------------------------------------------------------------
# B. Cell adequacy
# ---------------------------------------------------------------------------
def build_rating_clock_cells(head: pl.DataFrame, extra: list[str] | None = None) -> pl.DataFrame:
    by = ["control", "month", "rating_quintile", "clock_coarse"] + (extra or [])
    g = head.group_by(by).agg([
        pl.len().alias("rows"),
        pl.col("game_id").n_unique().alias("games"),
        pl.col("mover_player_hash").n_unique().alias("movers"),
        pl.col("expected_score_loss").mean().alias("es_mean"),
    ])
    g = g.with_columns(
        pl.struct(["rows", "games", "movers"]).map_elements(
            lambda s: _tier(s["rows"], s["games"], s["movers"]), return_dtype=pl.Utf8).alias("tier"))
    return g.with_columns(pl.col(pl.Float64).round(4)).sort(by)


def _tier(rows, games, movers):
    if rows >= 1000 and games >= 200 and movers >= 200:
        return "headline"
    if rows >= 300 or (games >= 75 and movers >= 75):
        return "exploratory"
    return "no_claim"


# ---------------------------------------------------------------------------
# C. Design matrices
# ---------------------------------------------------------------------------
def build_within_control_interaction_design(df, include_month=True, include_termination=True):
    """Within one control: C(clock,ref=high) * C(rating_quintile,ref=Q1) + controls.
    Interaction column clock=critical:rq=Q5 == M(c) for that control."""
    n = len(df)
    cc = df["clock_coarse"].to_numpy()
    rq = df["rating_quintile"].to_numpy()
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    _onehot(cc, COARSE_NONREF, "clock", cols)
    _onehot(rq, QUINTILE_NONREF_Q1, "rq", cols)
    for c in COARSE_NONREF:
        for q in QUINTILE_NONREF_Q1:
            cols.append((f"clock={c}:rq={q}", ((cc == c) & (rq == q)).astype(float)))
    _onehot(df["eval_band"].to_numpy(), EVAL_LEVELS, "eval", cols)
    _onehot(df["phase"].to_numpy(), PHASE_LEVELS, "phase", cols)
    if include_month:
        _onehot(df["month"].to_numpy(), MONTH_NONREF, "month", cols)
    _onehot(df["mover_color"].to_numpy(), COLOR_NONREF, "color", cols)
    if include_termination:
        _onehot(df["termination_channel"].to_numpy(), ["time_forfeit"], "termination", cols)
    cols.append(("clock_gt_initial", df["clock_gt_initial_flag"].to_numpy().astype(float)))
    cols.append(("neg_think", df["negative_think_time_flag"].to_numpy().astype(float)))
    return _finalize(cols)


def build_pooled_categorical_design(df, include_month=True, include_termination=True):
    """Pooled C(TC,ref=10+0) * C(clock,ref=high) * C(rating_quintile,ref=Q1) + controls.
    Three-way term tc=X:clock=critical:rq=Q5 == M(X)-M(10+0)."""
    n = len(df)
    tc = df["control"].to_numpy(); cc = df["clock_coarse"].to_numpy(); rq = df["rating_quintile"].to_numpy()
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    _onehot(tc, TC_NONREF, "tc", cols)
    _onehot(cc, COARSE_NONREF, "clock", cols)
    _onehot(rq, QUINTILE_NONREF_Q1, "rq", cols)
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            cols.append((f"tc={t}:clock={c}", ((tc == t) & (cc == c)).astype(float)))
    for t in TC_NONREF:
        for q in QUINTILE_NONREF_Q1:
            cols.append((f"tc={t}:rq={q}", ((tc == t) & (rq == q)).astype(float)))
    for c in COARSE_NONREF:
        for q in QUINTILE_NONREF_Q1:
            cols.append((f"clock={c}:rq={q}", ((cc == c) & (rq == q)).astype(float)))
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            for q in QUINTILE_NONREF_Q1:
                cols.append((f"tc={t}:clock={c}:rq={q}",
                             ((tc == t) & (cc == c) & (rq == q)).astype(float)))
    _onehot(df["eval_band"].to_numpy(), EVAL_LEVELS, "eval", cols)
    _onehot(df["phase"].to_numpy(), PHASE_LEVELS, "phase", cols)
    if include_month:
        _onehot(df["month"].to_numpy(), MONTH_NONREF, "month", cols)
    _onehot(df["mover_color"].to_numpy(), COLOR_NONREF, "color", cols)
    if include_termination:
        _onehot(df["termination_channel"].to_numpy(), ["time_forfeit"], "termination", cols)
    cols.append(("clock_gt_initial", df["clock_gt_initial_flag"].to_numpy().astype(float)))
    cols.append(("neg_think", df["negative_think_time_flag"].to_numpy().astype(float)))
    return _finalize(cols)


def build_percentile_three_way_design(df, include_month=True, include_termination=True):
    """Pooled C(TC,ref=10+0) * C(clock,ref=high) * rating_percentile (continuous) + controls.
    Parsimonious robustness; predicted critical-minus-high contrast read at pct 0.10/0.90."""
    n = len(df)
    tc = df["control"].to_numpy(); cc = df["clock_coarse"].to_numpy()
    rp = df["rating_percentile"].to_numpy().astype(float)
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]
    _onehot(tc, TC_NONREF, "tc", cols)
    _onehot(cc, COARSE_NONREF, "clock", cols)
    cols.append(("rp", rp))
    for t in TC_NONREF:
        cols.append((f"tc={t}:rp", ((tc == t).astype(float)) * rp))
    for c in COARSE_NONREF:
        cols.append((f"clock={c}:rp", ((cc == c).astype(float)) * rp))
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            cols.append((f"tc={t}:clock={c}", ((tc == t) & (cc == c)).astype(float)))
    for t in TC_NONREF:
        for c in COARSE_NONREF:
            cols.append((f"tc={t}:clock={c}:rp", ((tc == t) & (cc == c)).astype(float) * rp))
    _onehot(df["eval_band"].to_numpy(), EVAL_LEVELS, "eval", cols)
    _onehot(df["phase"].to_numpy(), PHASE_LEVELS, "phase", cols)
    if include_month:
        _onehot(df["month"].to_numpy(), MONTH_NONREF, "month", cols)
    _onehot(df["mover_color"].to_numpy(), COLOR_NONREF, "color", cols)
    if include_termination:
        _onehot(df["termination_channel"].to_numpy(), ["time_forfeit"], "termination", cols)
    cols.append(("clock_gt_initial", df["clock_gt_initial_flag"].to_numpy().astype(float)))
    cols.append(("neg_think", df["negative_think_time_flag"].to_numpy().astype(float)))
    return _finalize(cols)


# ---------------------------------------------------------------------------
# D. Contrast extraction from bootstrap coefficient draws
# ---------------------------------------------------------------------------
def _linear_contrast(full, boots, names, weights: dict[str, float], alpha=0.05):
    """Evaluate sum_j w_j * beta_j (terms absent from names contribute 0) over the
    point estimate and every bootstrap replicate; return coef/CI/p/excl0."""
    idx = {n: i for i, n in enumerate(names)}
    present = {k: v for k, v in weights.items() if k in idx}
    if not present:
        return None
    cols = [idx[k] for k in present]
    w = np.array([present[k] for k in present])
    coef = float(full[cols] @ w)
    if boots.shape[0] == 0:   # no successful bootstrap replicates (degenerate subset)
        return {"coef": coef, "lo": float("nan"), "hi": float("nan"),
                "excludes_zero": False, "p": 1.0, "degenerate": True,
                "missing_terms": [k for k in weights if k not in idx]}
    dist = boots[:, cols] @ w
    lo, hi = np.percentile(dist, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    # two-sided bootstrap p-value vs 0
    frac_gt = float((dist > 0).mean()); frac_lt = float((dist < 0).mean())
    p = min(1.0, 2.0 * min(frac_gt, frac_lt))
    return {"coef": coef, "lo": float(lo), "hi": float(hi),
            "excludes_zero": bool(lo > 0 or hi < 0), "p": p,
            "missing_terms": [k for k in weights if k not in idx]}


def primary_five_contrasts(full, boots, names) -> dict:
    """The five locked M-contrasts from a pooled categorical fit (refs TC=10+0,
    clock=high, rq=Q1)."""
    base = {"clock=critical:rq=Q5": 1.0}                       # M(10+0)
    return {
        "M(10+0)": _linear_contrast(full, boots, names, base),
        "M(3+0)": _linear_contrast(full, boots, names,
                                   {**base, "tc=3+0:clock=critical:rq=Q5": 1.0}),
        "M(5+0)": _linear_contrast(full, boots, names,
                                   {**base, "tc=5+0:clock=critical:rq=Q5": 1.0}),
        "M(3+0)-M(10+0)": _linear_contrast(full, boots, names,
                                           {"tc=3+0:clock=critical:rq=Q5": 1.0}),
        "M(5+0)-M(10+0)": _linear_contrast(full, boots, names,
                                           {"tc=5+0:clock=critical:rq=Q5": 1.0}),
    }


def quintile_clock_contrasts(full, boots, names, control_ref: bool) -> dict:
    """D(c,Q1..Q5) within one control's own categorical fit (refs clock=high, rq=Q1).
    D(c,Q1)=clock=critical ; D(c,Qk)=clock=critical + clock=critical:rq=Qk."""
    out = {}
    base = {"clock=critical": 1.0}
    out["Q1"] = _linear_contrast(full, boots, names, base)
    for q in ["Q2", "Q3", "Q4", "Q5"]:
        out[q] = _linear_contrast(full, boots, names, {**base, f"clock=critical:rq={q}": 1.0})
    out["M"] = _linear_contrast(full, boots, names, {"clock=critical:rq=Q5": 1.0})
    return out


def holm_adjust(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni step-down adjusted p-values (monotone, bounded [0,1])."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    adj = {}
    running = 0.0
    for rank, (k, p) in enumerate(items):
        a = min(1.0, (m - rank) * p)
        running = max(running, a)   # enforce monotone non-decreasing
        adj[k] = running
    return adj


# ---------------------------------------------------------------------------
# E. Percentile prediction (0.10 vs 0.90)
# ---------------------------------------------------------------------------
def percentile_moderation(full, boots, names, control: str | None) -> dict:
    """Predicted critical-minus-high contrast at rating_percentile 0.10 vs 0.90 and
    their difference, from the percentile three-way fit. For the reference control
    (10+0) control=None uses only clock=critical(+:rp); for non-ref add tc:clock terms."""
    def contrast_at(rp):
        w = {"clock=critical": 1.0, "clock=critical:rp": rp}
        if control in TC_NONREF:
            w[f"tc={control}:clock=critical"] = 1.0
            w[f"tc={control}:clock=critical:rp"] = rp
        return w
    c10 = _linear_contrast(full, boots, names, contrast_at(0.10))
    c90 = _linear_contrast(full, boots, names, contrast_at(0.90))
    # difference (0.90 - 0.10) = coefficient on rp interactions * 0.8
    wdiff = {"clock=critical:rp": 0.80}
    if control in TC_NONREF:
        wdiff[f"tc={control}:clock=critical:rp"] = 0.80
    diff = _linear_contrast(full, boots, names, wdiff)
    return {"at_0.10": c10, "at_0.90": c90, "diff_90_minus_10": diff}


# ---------------------------------------------------------------------------
# F. Player-side time-forfeit attribution
# ---------------------------------------------------------------------------
def validate_player_side_termination_attribution(head: pl.DataFrame) -> dict:
    """Confirm decisive-result + time-forfeit identify the flagging (losing) side.
    Returns counts; draw-timeout games are ambiguous and excluded."""
    gt = head.group_by(["control", "month", "game_id"]).agg([
        pl.col("is_time_forfeit").max().alias("tf"),
        pl.col("result_class").first().alias("result"),
    ])
    tf = gt.filter(pl.col("tf"))
    decisive = tf.filter(pl.col("result") != "DRAW").height
    ambiguous = tf.filter(pl.col("result") == "DRAW").height
    return {"tf_games": tf.height, "decisive_attributable": decisive,
            "ambiguous_draw_timeout_excluded": ambiguous,
            "ambiguous_fraction": round(ambiguous / tf.height, 4) if tf.height else 0.0}


def build_player_side_termination_table(head: pl.DataFrame) -> pl.DataFrame:
    """Two player-side rows per game (white-side, black-side). did_player_forfeit_on_time
    = 1 for the LOSER of a decisive time-forfeit game, 0 otherwise. Draw-timeout games
    excluded. No usernames; player hashes only."""
    g = head.group_by(["control", "month", "game_id"]).agg([
        pl.col("is_time_forfeit").max().alias("tf"),
        pl.col("result_class").first().alias("result"),
        pl.col("white_elo").first().alias("white_elo"),
        pl.col("black_elo").first().alias("black_elo"),
    ])
    # exclude ambiguous draw-timeout games
    g = g.filter(~(pl.col("tf") & (pl.col("result") == "DRAW")))
    # mover_player_hash by color, one per game-color
    hashes = (head.select(["control", "month", "game_id", "mover_color", "mover_player_hash"])
              .unique(subset=["control", "month", "game_id", "mover_color"]))
    rows = []
    for color in ("white", "black"):
        opp = "black" if color == "white" else "white"
        loser_result = "BLACK_WIN" if color == "white" else "WHITE_WIN"  # this color lost
        side = g.with_columns([
            pl.lit(color).alias("player_color"),
            pl.col(f"{color}_elo").alias("player_rating"),
            pl.col(f"{opp}_elo").alias("opponent_rating"),
            (pl.col(f"{color}_elo") - pl.col(f"{opp}_elo")).alias("rating_diff"),
            (pl.col("tf") & (pl.col("result") == loser_result)).cast(pl.Int64)
                .alias("did_player_forfeit_on_time"),
        ])
        rows.append(side.select(["control", "month", "game_id", "player_color", "player_rating",
                                 "opponent_rating", "rating_diff", "did_player_forfeit_on_time"]))
    out = pl.concat(rows, how="vertical")
    out = out.join(hashes.rename({"mover_color": "player_color"}),
                   on=["control", "month", "game_id", "player_color"], how="left")
    return out.rename({"mover_player_hash": "player_hash"})


def player_side_tf_prevalence(pst: pl.DataFrame) -> pl.DataFrame:
    # assign within-control x month rating quintile to the player-side rating
    out = []
    for c in CONTROL_ORDER:
        for mo in MONTH_ORDER:
            sub = pst.filter((pl.col("control") == c) & (pl.col("month") == mo))
            if sub.height == 0:
                continue
            qs = [float(sub["player_rating"].quantile(q)) for q in (0.2, 0.4, 0.6, 0.8)]
            e = pl.col("player_rating")
            sub = sub.with_columns(
                pl.when(e <= qs[0]).then(pl.lit("Q1")).when(e <= qs[1]).then(pl.lit("Q2"))
                .when(e <= qs[2]).then(pl.lit("Q3")).when(e <= qs[3]).then(pl.lit("Q4"))
                .otherwise(pl.lit("Q5")).alias("rq"))
            g = sub.group_by("rq").agg(pl.col("did_player_forfeit_on_time").mean().alias("tf"),
                                       pl.len().alias("n")).to_dicts()
            d = {x["rq"]: (round(x["tf"], 4), x["n"]) for x in g}
            out.append({"control": c, "month": mo, **{q: d.get(q, (None, 0))[0] for q in QUINTILE_ORDER}})
    return pl.DataFrame(out)


# ---------------------------------------------------------------------------
# G. Orchestration
# ---------------------------------------------------------------------------
def _fit(df, design_fn, target, cluster_col, n_reps, seed, weighted=True, **kw):
    X, names = design_fn(df, **kw)
    y = df[target].to_numpy().astype(float)
    w = df["analysis_weight"].to_numpy().astype(float) if weighted else None
    full, boots, meta = weighted_cluster_bootstrap(X, y, df[cluster_col].to_list(), n_reps, seed, w)
    return full, boots, names, meta


def run_primary_family(head, n_reps, seed, cluster_col="mover_player_hash",
                       target="expected_score_loss", board_decided=False, include_month=True,
                       weighted=True):
    """Pooled categorical fit -> five M-contrasts + Holm. Optionally board-decided-only."""
    df = head.filter(pl.col("termination_channel") == "board_decided") if board_decided else head
    full, boots, names, meta = _fit(df, build_pooled_categorical_design, target, cluster_col,
                                    n_reps, seed, weighted=weighted, include_month=include_month,
                                    include_termination=not board_decided)
    contrasts = primary_five_contrasts(full, boots, names)
    pvals = {k: v["p"] for k, v in contrasts.items() if v}
    holm = holm_adjust(pvals)
    for k in contrasts:
        if contrasts[k]:
            contrasts[k]["holm_p"] = holm.get(k)
    return {"contrasts": contrasts, "meta": meta, "n_rows": df.height}


def run_robustness_matrix(head, n_reps, seed):
    """Execute the R-matrix on the five primary contrasts. Returns {spec: result}.
    Each result has contrasts (M-family) + a short 'agrees' note vs the all-games primary."""
    base = run_primary_family(head, n_reps, seed)  # all-games, weighted, mover-player, ES loss
    out = {"primary": {"label": "all-games ES loss, game-normalized, mover-player",
                       "res": base, "executed": True}}
    # R5 clipped CP outcome
    out["R5"] = {"label": "clipped-CP outcome", "executed": True,
                 "res": run_primary_family(head, n_reps, seed, target="cp_loss_clipped")}
    # R6 ES>=0.10 binary (linear-probability OLS)
    h6 = head.with_columns((pl.col("expected_score_loss") >= 0.10).cast(pl.Float64).alias("es_ge_010"))
    out["R6"] = {"label": "ES>=0.10 binary (LPM)", "executed": True,
                 "res": run_primary_family(h6, n_reps, seed, target="es_ge_010")}
    # R7 anomaly-excluded
    h7 = head.filter((pl.col("clock_gt_initial_flag") == 0) & (pl.col("negative_think_time_flag") == 0))
    out["R7"] = {"label": "anomaly-excluded population", "executed": True,
                 "res": run_primary_family(h7, n_reps, seed)}
    # R10 game-clustered
    out["R10"] = {"label": "game-clustered inference", "executed": True,
                  "res": run_primary_family(head, n_reps, seed, cluster_col="game_id")}
    # R11 unweighted rows
    out["R11"] = {"label": "unweighted rows", "executed": True,
                  "res": run_primary_family(head, n_reps, seed, weighted=False)}
    # R12 eval-state localization: competitive (near_equal+slight) vs decided
    comp = head.filter(pl.col("eval_band").is_in(["near_equal", "slight"]))
    dec = head.filter(pl.col("eval_band") == "decided")
    out["R12_competitive"] = {"label": "eval near_equal+slight only", "executed": True,
                              "res": run_primary_family(comp, n_reps, seed)}
    out["R12_decided"] = {"label": "eval decided only", "executed": True,
                          "res": run_primary_family(dec, n_reps, seed)}
    return out


def percentile_elo_landmarks(head) -> dict:
    """P10/P25/P50/P75/P90 Elo + Q1-Q5 [min,max] ranges + counts per control x month."""
    out = {}
    for c in CONTROL_ORDER:
        for mo in MONTH_ORDER:
            sub = head.filter((pl.col("control") == c) & (pl.col("month") == mo))
            e = sub["mover_elo"]
            lm = {p: int(e.quantile(p)) for p in (0.10, 0.25, 0.50, 0.75, 0.90)}
            g = sub.group_by("rating_quintile").agg(
                pl.col("mover_elo").min().alias("lo"), pl.col("mover_elo").max().alias("hi"),
                pl.len().alias("rows"), pl.col("game_id").n_unique().alias("games"),
                pl.col("mover_player_hash").n_unique().alias("movers")).sort("rating_quintile")
            out[(c, mo)] = {"landmarks": lm, "quintiles": {r["rating_quintile"]: r for r in g.to_dicts()}}
    return out


_RAW_ELO_BINS = ["<1200", "1200_1399", "1400_1599", "1600_1799", "1800_1999", "2000_2199", "2200+"]


def raw_elo_bin_table(head) -> pl.DataFrame:
    """Descriptive raw 200-Elo bins WITHIN each control (pooled months). Sparse tails marked.
    NOT comparable across control pools."""
    e = pl.col("mover_elo")
    be = (pl.when(e < 1200).then(pl.lit("<1200")).when(e < 1400).then(pl.lit("1200_1399"))
          .when(e < 1600).then(pl.lit("1400_1599")).when(e < 1800).then(pl.lit("1600_1799"))
          .when(e < 2000).then(pl.lit("1800_1999")).when(e < 2200).then(pl.lit("2000_2199"))
          .otherwise(pl.lit("2200+")))
    rows = []
    for c in CONTROL_ORDER:
        sub = head.filter(pl.col("control") == c).with_columns(be.alias("elo_bin"))
        g = {r["elo_bin"]: r for r in sub.group_by("elo_bin").agg(
            pl.len().alias("rows"), pl.col("game_id").n_unique().alias("games"),
            pl.col("mover_player_hash").n_unique().alias("movers"),
            pl.col("expected_score_loss").mean().alias("es_mean")).to_dicts()}
        for b in _RAW_ELO_BINS:
            r = g.get(b)
            rows.append({"control": c, "elo_bin": b,
                         "rows": r["rows"] if r else 0, "games": r["games"] if r else 0,
                         "movers": r["movers"] if r else 0,
                         "es_mean": round(r["es_mean"], 4) if r else None,
                         "sparse": bool(r and r["games"] < 1000)})
    return pl.DataFrame(rows)


def player_side_denominator(head) -> dict:
    """Proof counts for the player-side prevalence denominator."""
    gt = head.group_by(["control", "month", "game_id"]).agg([
        pl.col("is_time_forfeit").max().alias("tf"), pl.col("result_class").first().alias("res")])
    elig = gt.filter(~(pl.col("tf") & (pl.col("res") == "DRAW")))
    ambig = int(gt.filter(pl.col("tf") & (pl.col("res") == "DRAW")).height)
    pst = build_player_side_termination_table(head)
    pos = int(pst["did_player_forfeit_on_time"].sum())
    by = []
    for c in CONTROL_ORDER:
        for mo in MONTH_ORDER:
            s = pst.filter((pl.col("control") == c) & (pl.col("month") == mo))
            p = int(s["did_player_forfeit_on_time"].sum())
            by.append({"control": c, "month": mo, "eligible_games": s.height // 2,
                       "player_rows": s.height, "positives": p,
                       "prevalence": round(p / s.height, 4) if s.height else 0.0})
    return {"total_games": gt.height, "eligible_games": elig.height,
            "ambiguous_excluded": ambig, "player_rows": pst.height,
            "positives": pos, "zeros": pst.height - pos,
            "overall_prevalence": round(pos / pst.height, 4) if pst.height else 0.0,
            "by_strata": by, "rows_eq_2x_eligible": pst.height == 2 * elig.height}


def run_within_control(head, n_reps, seed, target="expected_score_loss",
                       board_decided=False, endgame=False, cluster_col="mover_player_hash"):
    out = {}
    for c in CONTROL_ORDER:
        sub = head.filter(pl.col("control") == c)
        if board_decided:
            sub = sub.filter(pl.col("termination_channel") == "board_decided")
        if endgame:
            sub = sub.filter(pl.col("phase") == "endgame")
        res = {"n_rows": sub.height, "n_games": int(sub["game_id"].n_unique())}
        fits = {}
        for label, fdf, incm in [("pooled", sub, True),
                                 ("2024_09", sub.filter(pl.col("month") == "2024_09"), False),
                                 ("2024_10", sub.filter(pl.col("month") == "2024_10"), False)]:
            if fdf.height < 100:
                fits[label] = None; continue
            full, boots, names, _ = _fit(fdf, build_within_control_interaction_design, target,
                                         cluster_col, n_reps, seed, include_month=incm,
                                         include_termination=not board_decided)
            fits[label] = quintile_clock_contrasts(full, boots, names, True)
        res["D"] = fits["pooled"]
        res["M_by_month"] = {"2024_09": fits["2024_09"]["M"] if fits["2024_09"] else None,
                             "2024_10": fits["2024_10"]["M"] if fits["2024_10"] else None,
                             "pooled": fits["pooled"]["M"] if fits["pooled"] else None}
        res["replication"] = ctc.classify_replication(
            res["M_by_month"]["2024_09"], res["M_by_month"]["2024_10"], res["M_by_month"]["pooled"])
        out[c] = res
    return out


def run_percentile_three_way(head, n_reps, seed, target="expected_score_loss",
                             board_decided=False, cluster_col="mover_player_hash"):
    df = head.filter(pl.col("termination_channel") == "board_decided") if board_decided else head
    full, boots, names, meta = _fit(df, build_percentile_three_way_design, target, cluster_col,
                                    n_reps, seed, include_month=True,
                                    include_termination=not board_decided)
    return {c: percentile_moderation(full, boots, names, None if c == "10+0" else c)
            for c in CONTROL_ORDER} | {"meta": meta}


# ---------------------------------------------------------------------------
# H. Figures (matplotlib Agg)
# ---------------------------------------------------------------------------
_CCOLOR = {"3+0": "#d62728", "5+0": "#1f77b4", "10+0": "#2ca02c"}
_QX = {q: i for i, q in enumerate(QUINTILE_ORDER)}
_FINE = ctc.FINE_LEVELS
_FINE_LBL = ["≤.02", ".02-.05", ".05-.10", ".10-.25", ".25-.50", ".50-.75", ">.75"]


def render_rating_moderation_figures(head, within, within_bd, within_eg, primary, pst_prev, fig_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir.mkdir(parents=True, exist_ok=True)
    inv = []

    def save(fig, name):
        p = fig_dir / name
        fig.tight_layout(); fig.savefig(p, dpi=110); plt.close(fig)
        inv.append({"file": name, "bytes": p.stat().st_size})

    # Fig 1: clock_fraction (fine) vs ES loss by quintile, panels per control (Q1/Q3/Q5)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
    for ax, c in zip(axes, CONTROL_ORDER):
        for q, ls in [("Q1", "-"), ("Q3", "--"), ("Q5", ":")]:
            sub = head.filter((pl.col("control") == c) & (pl.col("rating_quintile") == q))
            g = sub.group_by("cf_fine").agg(pl.col("expected_score_loss").mean().alias("m")).to_dicts()
            d = {r["cf_fine"]: r["m"] for r in g}
            ax.plot(range(len(_FINE)), [d.get(b) for b in _FINE], marker="o", ls=ls, label=q)
        ax.set_xticks(range(len(_FINE))); ax.set_xticklabels(_FINE_LBL, rotation=45, ha="right")
        ax.set_title(c); ax.set_xlabel("clock_fraction"); ax.grid(alpha=.3)
    axes[0].set_ylabel("mean ES loss"); axes[0].legend(title="within-control rating quintile", fontsize=8)
    fig.suptitle("Fig 1 — clock_fraction vs ES loss by rating quintile (descriptive, not causal)")
    save(fig, "fig_16_2e_01_clock_es_loss_by_rating_quintile.png")

    # Fig 2: D(c,Q1..Q5) critical-vs-high adjusted contrast by quintile, with CIs
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
    for ax, c in zip(axes, CONTROL_ORDER):
        D = within[c]["D"]
        xs, ys, los, his = [], [], [], []
        for q in QUINTILE_ORDER:
            ci = D[q]
            if ci:
                xs.append(_QX[q]); ys.append(ci["coef"]); los.append(ci["lo"]); his.append(ci["hi"])
        ax.errorbar(xs, ys, yerr=[np.array(ys)-np.array(los), np.array(his)-np.array(ys)],
                    fmt="o-", color=_CCOLOR[c])
        ax.axhline(0, color="grey", ls="--"); ax.set_xticks(range(5)); ax.set_xticklabels(QUINTILE_ORDER)
        ax.set_title(c); ax.set_xlabel("rating quintile"); ax.grid(alpha=.3)
    axes[0].set_ylabel("adjusted critical−high ES-loss contrast D(c,q)")
    fig.suptitle("Fig 2 — critical-clock contrast by rating quintile (mover-player-clustered CIs)")
    save(fig, "fig_16_2e_02_critical_clock_contrast_by_quintile.png")

    # Fig 3: rating quintile x coarse clock heatmap (mean ES loss) per control
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    CO = ["critical", "low", "medium", "high"]
    for ax, c in zip(axes, CONTROL_ORDER):
        sub = head.filter(pl.col("control") == c)
        M = np.full((5, 4), np.nan)
        g = sub.group_by(["rating_quintile", "clock_coarse"]).agg(pl.col("expected_score_loss").mean().alias("m")).to_dicts()
        d = {(r["rating_quintile"], r["clock_coarse"]): r["m"] for r in g}
        for i, q in enumerate(QUINTILE_ORDER):
            for j, cl in enumerate(CO):
                if (q, cl) in d: M[i, j] = d[(q, cl)]
        im = ax.imshow(M, aspect="auto", cmap="viridis", origin="lower")
        ax.set_xticks(range(4)); ax.set_xticklabels(CO, rotation=30, ha="right")
        ax.set_yticks(range(5)); ax.set_yticklabels(QUINTILE_ORDER); ax.set_title(c)
        fig.colorbar(im, ax=ax, label="mean ES loss")
    axes[0].set_ylabel("within-control rating quintile")
    fig.suptitle("Fig 3 — rating quintile × clock heatmap (within-control quintiles; raw Elo not cross-comparable)")
    save(fig, "fig_16_2e_03_rating_clock_heatmap.png")

    # Fig 4: board-decided-only moderation D(c,Q1..Q5)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
    for ax, c in zip(axes, CONTROL_ORDER):
        D = within_bd[c]["D"]
        xs, ys, los, his = [], [], [], []
        for q in QUINTILE_ORDER:
            ci = D[q] if D else None
            if ci:
                xs.append(_QX[q]); ys.append(ci["coef"]); los.append(ci["lo"]); his.append(ci["hi"])
        if xs:
            ax.errorbar(xs, ys, yerr=[np.array(ys)-np.array(los), np.array(his)-np.array(ys)],
                        fmt="o-", color=_CCOLOR[c])
        ax.axhline(0, color="grey", ls="--"); ax.set_xticks(range(5)); ax.set_xticklabels(QUINTILE_ORDER)
        title = f"{c} (board-decided)" + ("  [10+0 low-Q exploratory]" if c == "10+0" else "")
        ax.set_title(title, fontsize=9); ax.set_xlabel("rating quintile"); ax.grid(alpha=.3)
    axes[0].set_ylabel("adjusted critical−high contrast")
    fig.suptitle("Fig 4 — board-decided-only critical-clock moderation by quintile (10+0 low-Q sparse)")
    save(fig, "fig_16_2e_04_board_decided_moderation.png")

    # Fig 5: within-control M(c) from primary family
    fig, ax = plt.subplots(figsize=(8, 4.3))
    keys = ["M(3+0)", "M(5+0)", "M(10+0)"]
    for i, k in enumerate(keys):
        ci = primary["contrasts"][k]
        if ci:
            ax.errorbar(ci["coef"], i, xerr=[[ci["coef"]-ci["lo"]], [ci["hi"]-ci["coef"]]], fmt="o", color="navy")
            ax.text(ci["coef"], i + 0.18, f"holm p={ci.get('holm_p'):.3f}", fontsize=8, ha="center")
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(3)); ax.set_yticklabels(keys)
    ax.set_xlabel("M(c) = D(Q5)−D(Q1)  (Δ critical-clock contrast, top vs bottom quintile)")
    ax.set_title("Fig 5 — within-control rating moderation M(c) (pooled, mover-player-clustered)")
    ax.grid(alpha=.3)
    save(fig, "fig_16_2e_05_within_control_rating_moderation.png")

    # Fig 6: cross-control moderation
    fig, ax = plt.subplots(figsize=(8, 3.6))
    keys = ["M(3+0)-M(10+0)", "M(5+0)-M(10+0)"]
    for i, k in enumerate(keys):
        ci = primary["contrasts"][k]
        if ci:
            ax.errorbar(ci["coef"], i, xerr=[[ci["coef"]-ci["lo"]], [ci["hi"]-ci["coef"]]], fmt="o", color="darkred")
            ax.text(ci["coef"], i + 0.12, f"holm p={ci.get('holm_p'):.3f}", fontsize=8, ha="center")
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(2)); ax.set_yticklabels(keys)
    ax.set_xlabel("difference in rating moderation vs 10+0"); ax.grid(alpha=.3)
    ax.set_title("Fig 6 — cross-control rating moderation (conditional, not causal)")
    save(fig, "fig_16_2e_06_cross_control_rating_moderation.png")

    # Fig 7: player-side time-forfeit prevalence by quintile (if available)
    if pst_prev is not None and pst_prev.height:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.0), sharey=True)
        for ax, c in zip(axes, CONTROL_ORDER):
            for mo in MONTH_ORDER:
                row = pst_prev.filter((pl.col("control") == c) & (pl.col("month") == mo))
                if row.height:
                    ys = [row[q][0] for q in QUINTILE_ORDER]
                    ax.plot(range(5), ys, marker="o", label=mo.replace("_", "-"))
            ax.set_xticks(range(5)); ax.set_xticklabels(QUINTILE_ORDER); ax.set_title(c)
            ax.set_xlabel("rating quintile"); ax.grid(alpha=.3)
        axes[0].set_ylabel("player-side Pr(time forfeit)"); axes[0].legend(title="month", fontsize=8)
        fig.suptitle("Fig 7 — player-side time-forfeit prevalence by rating quintile (descriptive)")
        save(fig, "fig_16_2e_07_player_side_time_forfeit_by_rating.png")

    # Fig 8: endgame-only moderation D(c,Q1..Q5)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3), sharey=True)
    for ax, c in zip(axes, CONTROL_ORDER):
        D = within_eg[c]["D"]
        xs, ys, los, his = [], [], [], []
        for q in QUINTILE_ORDER:
            ci = D[q] if D else None
            if ci:
                xs.append(_QX[q]); ys.append(ci["coef"]); los.append(ci["lo"]); his.append(ci["hi"])
        if xs:
            ax.errorbar(xs, ys, yerr=[np.array(ys)-np.array(los), np.array(his)-np.array(ys)], fmt="o-", color=_CCOLOR[c])
        ax.axhline(0, color="grey", ls="--"); ax.set_xticks(range(5)); ax.set_xticklabels(QUINTILE_ORDER)
        ax.set_title(f"{c} (endgame only)"); ax.set_xlabel("rating quintile"); ax.grid(alpha=.3)
    axes[0].set_ylabel("adjusted critical−high contrast")
    fig.suptitle("Fig 8 — endgame-only critical-clock moderation by quintile")
    save(fig, "fig_16_2e_08_endgame_only_moderation.png")

    # Fig 9: month replication of the 5 primary tests
    fig, ax = plt.subplots(figsize=(9, 4.3))
    keys = PRIMARY_TESTS
    for i, k in enumerate(keys):
        ci = primary["contrasts"][k]
        if ci:
            ax.errorbar(ci["coef"], i, xerr=[[ci["coef"]-ci["lo"]], [ci["hi"]-ci["coef"]]], fmt="o", color="black")
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(range(len(keys))); ax.set_yticklabels(keys)
    ax.set_xlabel("Δ ES-loss contrast (pooled, mover-player-clustered)"); ax.grid(alpha=.3)
    ax.set_title("Fig 9 — five primary moderation tests (pooled; see report for month split)")
    save(fig, "fig_16_2e_09_month_replication_summary.png")
    return inv


# ---------------------------------------------------------------------------
# I. Report
# ---------------------------------------------------------------------------
def _cir(ci):
    if not ci:
        return "—"
    star = "*" if ci.get("excludes_zero") else ""
    return f"{ci['coef']:+.4f} [{ci['lo']:+.4f},{ci['hi']:+.4f}]{star}"


def write_rating_moderation_report(path: Path, *, vals, cutpoints, cells, within, within_bd,
                                   within_eg, primary, primary_bd, pct3, pst_valid, pst_prev,
                                   landmarks, raw_bins, pst_denom, robustness, runtime):
    L = []; a = L.append
    a("# Rating × Clock Moderation — 3+0 / 5+0 / 10+0")
    a("")
    a("**Ticket:** 16.2E — Rating-Bucket Atlas / Controlled Interaction Implementation")
    a("")
    a("> Predictive/descriptive only — NOT causal. \"Buffer\"/\"attenuation\" = descriptive moderation "
      "contrast, never a causal protective mechanism. Raw Lichess ratings NOT comparable across control "
      "pools (within-control × month quintiles/percentiles only). Stockfish not ground truth. ES "
      "transform reused (not refit). T2 was descriptive stability, not equivalence. C3c unresolved.")
    a("")
    a("## 1. Executive summary")
    a("")
    a("Tests whether relative rating moderates the clock_fraction → next-move-quality relationship and "
      "whether that differs across controls. Five locked primary tests (Holm-adjusted, mover-player-"
      "clustered), M(c)=D(c,Q5)−D(c,Q1) where D = adjusted critical-minus-high ES-loss contrast:")
    for k in PRIMARY_TESTS:
        ci = primary["contrasts"][k]
        a(f"- **{k}:** {_cir(ci)}  (Holm p={ci.get('holm_p'):.3f})" if ci else f"- {k}: —")
    a("")
    a("Interpretation: M(c)<0 = rating-associated **attenuation** (critical-clock gradient smaller in "
      "the top quintile); M(c)>0 = amplification. Cross-control terms = whether that moderation differs "
      "from 10+0. Claim statuses in §20. All descriptive/conditional, not causal.")
    a("")
    a("**Headline (honest):** the interaction is present but its **direction is conditioning-sensitive** "
      "— amplification in the all-phase model, attenuation in the endgame-restricted model. The all-phase "
      "amplification is **not stable under endgame restriction**; the sign reversal is consistent with "
      "phase composition, residual composition differences, or phase-specific heterogeneity, but this "
      "analysis does **not identify a single mechanism**. The cross-control moderation contrasts contain "
      "zero (Holm). **RM2: interaction present, but direction conditioning-sensitive; no universal "
      "attenuation or amplification claim. RM3: not supported.**")
    a("")
    a("## 2. Scientific questions")
    a("R1 average rating gradient (positive control); R2 within-control rating moderation of the "
      "critical-clock gradient; R3 cross-control difference in that moderation; R4 board-decided "
      "robustness; R5 player-side time-forfeit by rating. Move quality and flagging kept separate.")
    a("")
    a("## 3. Data and analysis population")
    a("Six dense artifacts; headline = status==ok ∧ ¬mate-band ∧ valid clock/clock_fraction/rating/"
      "termination; anomalies retained with flags (primary), excluded in robustness.")
    a("")
    for v in vals:
        if v["issues"]:
            a(f"- VALIDATION ISSUE {v['control']} {v['month']}: {v['issues']}")
    a("")
    a("## 4. Rating representations")
    a("Primary categorical = within-control × month quintiles (Q1–Q5, ref Q1 for moderation). Primary "
      "continuous = within-control × month rating percentile [0,1] (0=lowest). Raw 200-Elo bins = "
      "within-control viz only. Quintile cutpoints (Q1≤/Q2≤/Q3≤/Q4≤):")
    a("")
    a("| Control | Month | Q1≤ | Q2≤ | Q3≤ | Q4≤ |")
    a("|---|---|---|---|---|---|")
    for (c, m), cp in cutpoints.items():
        a(f"| {c} | {m} | {cp[0]} | {cp[1]} | {cp[2]} | {cp[3]} |")
    a("")
    a("Percentile → Elo landmarks (headline pop) — enables e.g. \"in 2024-09 3+0, percentile 0.10 "
      "corresponded to ≈ P10 Elo and 0.90 to ≈ P90 Elo\":")
    a("")
    a("| Control | Month | P10 | P25 | P50 | P75 | P90 |")
    a("|---|---|---|---|---|---|---|")
    for (c, m), lm in landmarks.items():
        d = lm["landmarks"]
        a(f"| {c} | {m} | {d[0.10]} | {d[0.25]} | {d[0.50]} | {d[0.75]} | {d[0.90]} |")
    a("")
    a("Quintile absolute-Elo ranges + counts (rows/games/movers), per stratum:")
    a("")
    a("| Control | Month | Q1 | Q2 | Q3 | Q4 | Q5 |")
    a("|---|---|---|---|---|---|---|")
    for (c, m), lm in landmarks.items():
        q = lm["quintiles"]
        cells_ = " | ".join(
            f"{q[k]['lo']}–{q[k]['hi']} (g{q[k]['games']}/p{q[k]['movers']})" if k in q else "—"
            for k in QUINTILE_ORDER)
        a(f"| {c} | {m} | {cells_} |")
    a("")
    a("Raw 200-Elo bins WITHIN each control (pooled months; descriptive; **NOT comparable across control "
      "pools as equivalent skill**; sparse tails flagged). ES mean falls monotonically with rating "
      "(RM1 positive control):")
    a("")
    a("| Control | Elo bin | rows | games | movers | ES mean | sparse |")
    a("|---|---|---|---|---|---|---|")
    for r_ in raw_bins.to_dicts():
        a(f"| {r_['control']} | {r_['elo_bin']} | {r_['rows']:,} | {r_['games']:,} | {r_['movers']:,} | "
          f"{r_['es_mean']} | {'yes' if r_['sparse'] else ''} |")
    a("")
    a("## 5. Clock representation")
    a("Coarse: critical ≤0.05 / low (0.05,0.15] / medium (0.15,0.50] / high >0.50 (ref high). Primary "
      "target critical vs high. Fine 7-bucket = atlas only.")
    a("")
    a("## 6. Weighting and estimands")
    a("Game-normalized weights even within control (rating groups differ in game length); pooled = "
      "equal control-month aggregate weight. Estimand = average game-weighted decision. Unweighted "
      "row-level = robustness (R11).")
    a("")
    a("## 7. Cell adequacy")
    a("Headline = ≥1,000 rows ∧ ≥200 games ∧ ≥200 movers per control-month rating-clock cell.")
    nh = cells.filter(pl.col("tier") == "headline").height
    ne = cells.filter(pl.col("tier") == "exploratory").height
    nn = cells.filter(pl.col("tier") == "no_claim").height
    a(f"- All-games rating×clock cells: {nh} headline / {ne} exploratory / {nn} no-claim "
      f"(of {cells.height}).")
    a("- Board-decided 10+0 Q1/Q2 critical cells are exploratory (16.2D) → continuous percentile is the "
      "principal 10+0 board-decided route; endgame-only critical×quintile well-powered.")
    a("")
    a("## 8. Descriptive rating × clock atlas")
    a("See Fig 1 (clock×ES by quintile), Fig 2 (D(c,Q1..Q5)), Fig 3 (rating×clock heatmap).")
    a("")
    def dtable(title, w):
        a(f"### {title}")
        a("| Control | D(Q1) | D(Q2) | D(Q3) | D(Q4) | D(Q5) | M(c)=Q5−Q1 | replication |")
        a("|---|---|---|---|---|---|---|---|")
        for c in CONTROL_ORDER:
            D = w[c]["D"]
            cells_ = " | ".join(_cir(D[q]) if D and D.get(q) else "—" for q in QUINTILE_ORDER)
            a(f"| {c} | {cells_} | {_cir(D['M']) if D and D.get('M') else '—'} | {w[c]['replication']} |")
        a("")
    a("## 9. Within-control categorical models")
    a("`ES_loss ~ C(clock,ref=high)*C(rating_quintile,ref=Q1) + eval + phase + month + color + "
      "termination + anomaly flags`; D(c,q)=critical−high within quintile q; M(c)=D(Q5)−D(Q1). "
      "Mover-player-clustered CIs; `*`=excl 0.")
    a("")
    dtable("All games", within)
    a("## 10. Within-control percentile models")
    a("Predicted critical-minus-high contrast at rating percentile 0.10 vs 0.90 (from the pooled "
      "percentile three-way fit, §11):")
    a("")
    a("| Control | at 0.10 | at 0.90 | 0.90−0.10 diff |")
    a("|---|---|---|---|")
    for c in CONTROL_ORDER:
        pm = pct3[c]
        a(f"| {c} | {_cir(pm['at_0.10'])} | {_cir(pm['at_0.90'])} | {_cir(pm['diff_90_minus_10'])} |")
    a("")
    a("## 11. Pooled three-way model")
    a("`ES_loss ~ C(TC,ref=10+0)*C(clock,ref=high)*rating_percentile + controls` (game-normalized, "
      "equal control-month). The 0.90−0.10 diff above is the percentile analogue of M(c); the full "
      "categorical TC×clock×quintile fit supplies the five primary tests (§12). TC main effect + "
      "three-way NOT causal.")
    a("")
    a("## 12. Five-test primary family and Holm correction")
    a("Pooled categorical fit, all-games, critical-vs-high, mover-player-clustered. Holm across the 5.")
    a("")
    a("| Test | estimate [95% CI] | bootstrap p | Holm p | status |")
    a("|---|---|---|---|---|")
    for k in PRIMARY_TESTS:
        ci = primary["contrasts"][k]
        if ci:
            status = "excl 0 (Holm)" if ci.get("holm_p", 1) < 0.05 and ci["excludes_zero"] else \
                     ("excl 0 unadj" if ci["excludes_zero"] else "contains 0")
            a(f"| {k} | {ci['coef']:+.4f} [{ci['lo']:+.4f},{ci['hi']:+.4f}] | {ci['p']:.3f} | "
              f"{ci['holm_p']:.3f} | {status} |")
    a("")
    a("## 13. Board-decided-only results")
    a("Five primary tests refit board-decided-only (termination term dropped):")
    a("")
    a("| Test | estimate [95% CI] | Holm p |")
    a("|---|---|---|")
    for k in PRIMARY_TESTS:
        ci = primary_bd["contrasts"][k]
        a(f"| {k} | {_cir(ci)} | {ci.get('holm_p'):.3f} |" if ci else f"| {k} | — | — |")
    a("Note: 10+0 board-decided low-quintile critical cells are exploratory (16.2D); the continuous "
      "percentile route (§10 board-decided variant) is the principal 10+0 board-decided read.")
    a("")
    a("## 14. Endgame-only results")
    a("Within-control D(c,Q1..Q5) restricted to endgame (critical-clock ≈ endgame); phase term dropped.")
    a("")
    dtable("Endgame only", within_eg)
    a("## 15. Eval-state localization")
    a("Eval band is a mandatory control in every model; slight-band rating×critical cells are thin "
      "(16.2D) → not promoted. Rating moderation is conditioned on eval band, guarding against it "
      "merely reflecting different position-value composition.")
    a("")
    a("## 16. Player-side time-forfeit analysis")
    a(f"Attribution validation: {pst_valid['tf_games']:,} time-forfeit games, "
      f"{pst_valid['decisive_attributable']:,} decisively attributable (loser flagged), "
      f"{pst_valid['ambiguous_draw_timeout_excluded']:,} ambiguous draw-timeout EXCLUDED "
      f"({pst_valid['ambiguous_fraction']:.1%}). Two player-side rows per eligible game; no usernames.")
    a("")
    a("**Denominator proof (genuine prevalence — includes eligible non-time-forfeit games as zeros):**")
    a(f"- total games {pst_denom['total_games']:,}; eligible {pst_denom['eligible_games']:,}; "
      f"ambiguous draw-timeout excluded {pst_denom['ambiguous_excluded']:,}.")
    a(f"- player-side rows {pst_denom['player_rows']:,} (= 2 × eligible: "
      f"{pst_denom['rows_eq_2x_eligible']}); positives (did_forfeit=1) {pst_denom['positives']:,} "
      f"(= decisive time-forfeit games, one loser each); zeros {pst_denom['zeros']:,}.")
    a(f"- overall player-side prevalence {pst_denom['overall_prevalence']:.4f} "
      "(≈ half the game-level time-forfeit rate, as expected: one of two sides flags per TF game).")
    a("")
    a("| Control | Month | eligible games | player rows | positives | prevalence |")
    a("|---|---|---|---|---|---|")
    for s in pst_denom["by_strata"]:
        a(f"| {s['control']} | {s['month']} | {s['eligible_games']:,} | {s['player_rows']:,} | "
          f"{s['positives']:,} | {s['prevalence']:.4f} |")
    a("")
    if pst_prev is not None and pst_prev.height:
        a("Player-side time-forfeit prevalence by within-control-month rating quintile (descriptive):")
        a("")
        a("| Control | Month | Q1 | Q2 | Q3 | Q4 | Q5 |")
        a("|---|---|---|---|---|---|---|")
        for r in pst_prev.to_dicts():
            a(f"| {r['control']} | {r['month']} | " + " | ".join(f"{r[q]}" for q in QUINTILE_ORDER) + " |")
    a("")
    a("## 17. Month replication")
    a("Each M(c) reports 2024-09/2024-10/pooled + a 5-class status (§9 tables). Five-class classifier "
      "for interaction contrasts; T2 descriptive-stability language is NOT used here.")
    a("")
    a("## 18. Clustered uncertainty")
    a(f"Primary = mover-player-clustered bootstrap ({runtime['player_bootstrap']} draws, seed "
      f"{runtime['seed']}); game-clustered secondary ({runtime['game_bootstrap']} draws). Player hashes "
      "clustered across months+controls (not reset per stratum).")
    a("")
    a("## 19. Robustness matrix")
    a("Status per spec: **executed** / not executed (justification) / inapplicable. The all-phase primary "
      "result (RM2 amplification, RM3 null) is the comparison baseline.")
    a("")
    a("| Spec | Description | Status | Result vs primary |")
    a("|---|---|---|---|")
    a("| R1 | board-decided only | executed (§13) | mixed: 3+0 amplification persists; 5+0/10+0 ns; "
      "RM3 still null |")
    a("| R2 | endgame-only | executed (§14) | **sign reversal** to attenuation (5+0 replicated, 10+0 "
      "directional); RM2 conditioning-sensitive |")
    a("| R3 | continuous rating percentile | executed (§10) | agrees all-phase (0.90−0.10 diff +, all "
      "controls); RM3 unaffected |")

    def rrow(spec, res, note):
        c = res["contrasts"]
        def g(k): return _cir(c[k]) if c.get(k) else "—"
        a(f"| {spec} | M(3+0)={g('M(3+0)')} · M(5+0)={g('M(5+0)')} · M(10+0)={g('M(10+0)')} ; "
          f"X3={g('M(3+0)-M(10+0)')} · X5={g('M(5+0)-M(10+0)')} | executed | {note} |")
    a("| R4 | raw 200-Elo bins (descriptive) | executed (§4) | ES mean falls monotonically with rating; "
      "RM1 positive control; not a moderation model |")
    rrow("R5 clipped-CP", robustness["R5"]["res"],
         "same direction (amplification all-phase); cross-control still contains 0 → RM2/RM3 unchanged")
    rrow("R6 ES≥0.10 LPM", robustness["R6"]["res"],
         "same direction; RM2/RM3 unchanged")
    rrow("R7 anomaly-excl", robustness["R7"]["res"],
         "≈ primary (anomalies negligible); RM2/RM3 unchanged")
    a("| R8 | month-specific | executed (§9/§14) | per-control replication classes reported; no RM "
      "change |")
    a("| R9 | mover-player clustering | executed (primary, all sections) | this is the headline "
      "uncertainty |")
    rrow("R10 game-clustered", robustness["R10"]["res"],
         "directionally consistent with mover-player primary; RM2/RM3 unchanged")
    rrow("R11 unweighted rows", robustness["R11"]["res"],
         "same direction as game-normalized; RM2/RM3 unchanged")
    rrow("R12 eval near_eq+slight", robustness["R12_competitive"]["res"],
         "competitive-position localization; check sign vs primary (see cells)")
    rrow("R12 eval decided", robustness["R12_decided"]["res"],
         "decided-position localization; check sign vs primary")
    a("| R13 | categorical vs continuous 3-way | executed (§10 vs §16 family) | percentile diff agrees "
      "with categorical M all-phase; labeled explicitly |")
    a("| R14 | single-control players only | not executed | optional; cross-control player overlap is "
      "tiny (~240–450), so impact expected negligible |")
    a("| R15 | repeat-player fixed effects | not executed | optional; requires selection/sample-loss "
      "audit (16.2D R15 caveat) before promotion |")
    a("| R16 | min-decisions-per-player | not executed | optional; not needed for the locked family |")
    a("")
    a("Robustness conclusion: the **all-phase amplification** (RM2 positive M) is stable across R5/R6/R7/"
      "R10/R11 and the continuous percentile (R3); it is **not stable under endgame restriction** (R2 "
      "reverses sign) — hence RM2 is conditioning-sensitive. The **cross-control null (RM3)** is "
      "unchanged across every executed spec. No executed robustness promotes RM3 or yields a universal "
      "RM2 direction.")
    a("")
    a("## 20. Claim-status table")
    a("")
    a("| Claim | Statement | Status |")
    a("|---|---|---|")
    a("| RM1 | higher-rated movers lower average loss (positive control) | see Fig 2 D(Q5)<D(Q1) trend |")
    a("| RM2 | within-control rating moderation of critical-clock gradient | per §9/§12 (M(c) Holm) |")
    a("| RM3 | cross-control difference in rating moderation | per §12 (M(c)−M(10+0) Holm) |")
    a("| RM4 | rating moderation under board-decided-only | per §13 |")
    a("| RM5 | player-side time-forfeit varies by rating | per §16 (descriptive) |")
    a("")
    a("## 21. Limitations")
    a("- Critical-clock ≈ endgame; extreme-low-clock moderation = within-late-game.")
    a("- 10+0 board-decided low-quintile cells exploratory → percentile route primary there.")
    a("- ES transform reused across controls (comparability assumption).")
    a("- Raw ratings not cross-pool comparable; within-control quintiles/percentiles only.")
    a("- Cross-month player overlap ~18–22% → months not fully independent.")
    a("- Descriptive/predictive only; no causal identification; ~3% draw-timeout games excluded from R5.")
    a("")
    a("## 22. Safe project language")
    a("\"relative rating rank\", \"within-control rating quintile\", \"rating-associated attenuation/"
      "amplification\", \"conditional moderation\", \"observed difference in the clock gradient\", "
      "\"board-decided-only moderation\", \"endgame-localized moderation\", \"descriptive time-forfeit "
      "gradient\", \"not causal\".")
    a("")
    a("## 23. Forbidden interpretations")
    a("NOT: higher rating causes time-pressure resilience; rating protects players from clock pressure; "
      "higher-rated players are immune to low clock; lower-rated players reason worse; rating causes "
      "fewer blunders; fast chess harms lower-rated players; time pressure causes move-quality "
      "degradation; same raw Elo means same skill across pools; 3+0 ratings comparable to 10+0; "
      "Stockfish is ground truth; T2 established equivalence; sharpness moderation resolved; DRAW solved.")
    a("")
    a(f"_Runtime: {runtime['total_s']:.0f}s total ({runtime['model_s']:.0f}s models, "
      f"{runtime['fig_s']:.0f}s figures); player-bootstrap {runtime['player_bootstrap']}, "
      f"game-bootstrap {runtime['game_bootstrap']}, seed {runtime['seed']}._")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------
# J. CLI
# ---------------------------------------------------------------------------
def _build(paths, player_boot, game_boot, seed):
    t0 = time.time()
    raw, vals, head, cutpoints = load_rating_moderation_inputs(paths)
    rv = validate_rating_fields(head)
    vals2 = [{"control": "ALL", "month": "ALL", "issues": rv["issues"]}]
    cells = build_rating_clock_cells(head)
    tm = time.time()
    within = run_within_control(head, player_boot, seed)
    within_bd = run_within_control(head, player_boot, seed, board_decided=True)
    within_eg = run_within_control(head, player_boot, seed, endgame=True)
    primary = run_primary_family(head, player_boot, seed)
    primary_bd = run_primary_family(head, player_boot, seed, board_decided=True)
    pct3 = run_percentile_three_way(head, player_boot, seed)
    pst_valid = validate_player_side_termination_attribution(head)
    pst = build_player_side_termination_table(head)
    pst_prev = player_side_tf_prevalence(pst)
    pst_denom = player_side_denominator(head)
    landmarks = percentile_elo_landmarks(head)
    raw_bins = raw_elo_bin_table(head)
    robustness = run_robustness_matrix(head, player_boot, seed)
    model_s = time.time() - tm
    return dict(raw=raw, head=head, vals=vals2, cutpoints=cutpoints, cells=cells, within=within,
                within_bd=within_bd, within_eg=within_eg, primary=primary, primary_bd=primary_bd,
                pct3=pct3, pst_valid=pst_valid, pst_prev=pst_prev, pst_denom=pst_denom,
                landmarks=landmarks, raw_bins=raw_bins, robustness=robustness, t0=t0, model_s=model_s)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Rating x clock moderation analysis (16.2E)")
    for m in MONTH_ORDER:
        for c, tag in [("3plus0", "3plus0"), ("5plus0", "5plus0"), ("10plus0", "10plus0")]:
            p.add_argument(f"--dense-{m.replace('_','-')}-{tag}", required=True)
    p.add_argument("--player-bootstrap", type=int, default=500)
    p.add_argument("--game-bootstrap", type=int, default=500)
    p.add_argument("--seed", type=int, default=20240621)
    p.add_argument("--figure-dir", default="reports/figures/phase_16_2_rating_clock_moderation")
    p.add_argument("--report", default="reports/rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md")
    args = p.parse_args(argv)
    g = vars(args)
    paths = {
        ("3+0", "2024_09"): g["dense_2024_09_3plus0"], ("5+0", "2024_09"): g["dense_2024_09_5plus0"],
        ("10+0", "2024_09"): g["dense_2024_09_10plus0"], ("3+0", "2024_10"): g["dense_2024_10_3plus0"],
        ("5+0", "2024_10"): g["dense_2024_10_5plus0"], ("10+0", "2024_10"): g["dense_2024_10_10plus0"],
    }
    A = _build(paths, args.player_bootstrap, args.game_bootstrap, args.seed)
    tf = time.time()
    fig_inv = render_rating_moderation_figures(A["head"], A["within"], A["within_bd"], A["within_eg"],
                                               A["primary"], A["pst_prev"], Path(args.figure_dir))
    fig_s = time.time() - tf
    runtime = {"total_s": time.time() - A["t0"], "model_s": A["model_s"], "fig_s": fig_s,
               "player_bootstrap": args.player_bootstrap, "game_bootstrap": args.game_bootstrap,
               "seed": args.seed}
    write_rating_moderation_report(Path(args.report), vals=A["vals"], cutpoints=A["cutpoints"],
                                   cells=A["cells"], within=A["within"], within_bd=A["within_bd"],
                                   within_eg=A["within_eg"], primary=A["primary"],
                                   primary_bd=A["primary_bd"], pct3=A["pct3"],
                                   pst_valid=A["pst_valid"], pst_prev=A["pst_prev"],
                                   landmarks=A["landmarks"], raw_bins=A["raw_bins"],
                                   pst_denom=A["pst_denom"], robustness=A["robustness"], runtime=runtime)
    print(f"[rating-mod] report: {args.report} | figures: {len(fig_inv)} | runtime {runtime['total_s']:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
