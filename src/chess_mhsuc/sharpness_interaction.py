"""
Sharpness × clock move-quality interaction — Ticket 14.2B (Contrast C3c).

Implements the PRE-REGISTERED 14.2A analysis (PREREGISTRATION.md §C3c) exactly:
does the small controlled `60_180`-vs-`over_180` clock association with next-move
expected-score (ES) loss become LARGER in objectively sharp / value-fragile positions?

Primary estimand: the `clock=60_180 × sharp_value_fragility_v1` interaction coefficient
(difference-in-differences) in a controlled OLS, with mover-player-clustered bootstrap.
Positive ⇒ the low-clock association is larger when the position is sharp.

Reuses (no re-extraction, no engine calls):
- controlled_move_quality.build_model_frame (non-mate frame + mover hash + controls + splits),
- clock_association_robustness.{fit_moments, build_variant_design} (controlled design,
  reference levels, rating modes, abs_cp control),
- clustered_uncertainty.{cluster_bootstrap_refit, summarize_contrasts}.

NO design changes are permitted after seeing results. All results are predictive/descriptive
ASSOCIATION + MODERATION — NOT causal; `sharp_value_fragility_v1` is an engine-side
value-fragility proxy, NOT human obviousness; surface-bait is exploratory only.

CLI: see `main()`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from chess_mhsuc import controlled_move_quality as cmq
from chess_mhsuc import clock_association_robustness as car
from chess_mhsuc.clustered_uncertainty import cluster_bootstrap_refit, summarize_contrasts

PRIMARY_INTERACTION = "clock=60_180:sharp"
SECONDARY_INTERACTION = "clock=under_60:sharp"
PRIMARY_SHARP = "sharp_value_fragility_v1"
_SHARP_COLS = [PRIMARY_SHARP, "sharp_value_fragility_v1_relaxed",
               "sharp_value_fragility_v1_strict", "surface_bait_10es"]
_SHARP_JOIN_EXTRA = ["n_good_10es", "worst_top5_loss_es", "ctx_legal_move_count"]
_JOIN_KEYS = ["game_id", "selected_position_type"]


# ---------------------------------------------------------------------------
# A. Load + join + validate
# ---------------------------------------------------------------------------

def recompute_sharp_v1(df: pl.DataFrame) -> pl.Series:
    """Recompute sharp_value_fragility_v1 from primitives (validation)."""
    return ((pl.col("n_good_10es") <= 2)
            & (pl.col("worst_top5_loss_es") >= 0.10)
            & (pl.col("ctx_legal_move_count") >= 8))


def load_joined(nml_path: str, sharp_path: str, players_path: str,
                version_tag: str) -> tuple[pl.DataFrame, dict]:
    """
    Build the modeling frame: controlled_move_quality non-mate frame (mover hash +
    controls + splits) ⋈ sharpness artifact on (game_id, selected_position_type).
    Validates join-key uniqueness, coverage, and exact sharp_value_fragility_v1
    equivalence. Returns (frame, validation dict).
    """
    mf = cmq.build_model_frame(nml_path, players_path, version_tag)  # non-mate, mover hash
    sh = pl.read_parquet(sharp_path)
    val: dict[str, Any] = {}
    val["sharp_rows"] = sh.height
    val["sharp_keys_unique"] = sh.select(_JOIN_KEYS).n_unique() == sh.height
    val["mf_rows"] = mf.height
    val["mf_keys_unique"] = mf.select(_JOIN_KEYS).n_unique() == mf.height
    if not val["sharp_keys_unique"]:
        raise ValueError("sharpness artifact not unique on (game_id, selected_position_type)")
    if not val["mf_keys_unique"]:
        raise ValueError("modeling frame not unique on join key")

    keep = _JOIN_KEYS + _SHARP_COLS + _SHARP_JOIN_EXTRA + ["status", "is_mate_band"]
    sh_ok = sh.filter(pl.col("status") == "ok").select(keep)
    n_before = mf.height
    j = mf.join(sh_ok.rename({"status": "sharp_status", "is_mate_band": "sharp_is_mate_band"}),
                on=_JOIN_KEYS, how="inner")
    val["joined_rows"] = j.height
    val["join_coverage"] = round(j.height / n_before, 4) if n_before else None
    val["no_row_multiplication"] = j.height <= n_before

    # exact sharp recompute equivalence (on rows with non-null primitives)
    chk = j.with_columns(recompute_sharp_v1(j).alias("_recomp"))
    mism = int(chk.filter(
        pl.col("_recomp").fill_null(False) != pl.col(PRIMARY_SHARP).fill_null(False)).height)
    val["sharp_recompute_mismatches"] = mism
    if mism > 0:
        raise ValueError(f"sharp_value_fragility_v1 mismatch on {mism} rows — STOP")

    # rename the primary binary to the design's `sharp` working column later
    return j, val


# ---------------------------------------------------------------------------
# B. Primary row universe
# ---------------------------------------------------------------------------

_REQUIRED_NONNULL = ["expected_score_loss", "clock_coarse", "eval_band",
                     "selected_position_type", "mover_rating", "termination_binary",
                     "mover_player_hash", PRIMARY_SHARP]


def primary_universe(j: pl.DataFrame) -> tuple[pl.DataFrame, dict]:
    """Apply locked primary filters; return (frame, exclusion counts)."""
    counts: dict[str, Any] = {"start_nonmate_joined": j.height}
    df = j
    for col in _REQUIRED_NONNULL:
        before = df.height
        df = df.filter(pl.col(col).is_not_null())
        dropped = before - df.height
        if dropped:
            counts[f"dropped_null_{col}"] = dropped
    # build the working `sharp` integer column (primary feature)
    df = df.with_columns(pl.col(PRIMARY_SHARP).cast(pl.Int64).alias("sharp"))
    counts["primary_rows"] = df.height
    return df, counts


def cell_adequacy(df: pl.DataFrame, sharp_col: str = "sharp") -> dict:
    """Cell counts for the primary interaction: sharp × clock(60_180/over_180)."""
    sub = df.filter(pl.col("clock_coarse").is_in(["60_180", "over_180"]))
    out = {}
    for r in sub.group_by(["clock_coarse", sharp_col]).len().sort(["clock_coarse", sharp_col]).to_dicts():
        out[f"{r['clock_coarse']}_sharp{int(r[sharp_col])}"] = r["len"]
    out["sharp_x_60_180"] = out.get("60_180_sharp1", 0)
    out["under_60_sharp"] = df.filter((pl.col("clock_coarse") == "under_60")
                                      & (pl.col(sharp_col) == 1)).height
    return out


# ---------------------------------------------------------------------------
# C. Design: controlled base + sharp main + clock×sharp interaction
# ---------------------------------------------------------------------------

def build_interaction_design(
    df: pl.DataFrame, moments: dict, *, include_month: bool, include_termination: bool,
    rating_mode: str = "linear", add_abs_cp: bool = False, sharp_col: str = "sharp",
) -> tuple[np.ndarray, list[str]]:
    """
    Controlled base design (reuses clock_association_robustness.build_variant_design,
    which carries the 15.1D/15.1F reference levels + rating modes + optional abs_cp) plus
    a `sharp` main effect and `clock=<lvl>:sharp` interaction columns.
    """
    X_base, names = car.build_variant_design(
        df, moments, include_month=include_month, include_termination=include_termination,
        rating_mode=rating_mode, add_abs_cp=add_abs_cp)
    sharp = df[sharp_col].to_numpy().astype(float)
    cols = [("sharp", sharp)]
    for lv in cmq.CLOCK_LEVELS:  # under_60, 60_180 (ref over_180)
        cname = f"clock={lv}"
        if cname in names:
            cols.append((f"clock={lv}:sharp", X_base[:, names.index(cname)] * sharp))
    X = np.column_stack([X_base] + [c[1] for c in cols])
    names = names + [c[0] for c in cols]
    return X, names


# ---------------------------------------------------------------------------
# D. Fit one specification with clustered bootstrap
# ---------------------------------------------------------------------------

def fit_interaction(
    df: pl.DataFrame, moments: dict, *, target: str, model: str, include_month: bool,
    include_termination: bool, rating_mode: str, add_abs_cp: bool, sharp_col: str,
    cluster_col: str, n_reps: int, seed: int,
) -> dict[str, Any]:
    """Fit the interaction model and cluster-bootstrap the interaction contrasts."""
    X, names = build_interaction_design(
        df, moments, include_month=include_month, include_termination=include_termination,
        rating_mode=rating_mode, add_abs_cp=add_abs_cp, sharp_col=sharp_col)
    y = df[target].to_numpy().astype(float)
    if model == "logistic":
        if len(np.unique(y)) < 2:
            return {"skipped": f"single-class target {target}"}
        fit_fn = cmq._make_logistic_fit()
    else:
        fit_fn = cmq._ols_fit
    clusters = df[cluster_col].to_list()
    full, boot, meta = cluster_bootstrap_refit(X, y, clusters, fit_fn, n_reps, seed)
    wanted = [c for c in (PRIMARY_INTERACTION, SECONDARY_INTERACTION) if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    return {
        "primary": summ.get(PRIMARY_INTERACTION),
        "secondary": summ.get(SECONDARY_INTERACTION),
        "meta": meta, "cluster_col": cluster_col, "target": target, "model": model,
        "n_rows": len(df),
    }


def point_interaction(df, moments, *, include_month, include_termination,
                      rating_mode="linear", sharp_col="sharp") -> dict[str, float]:
    """OLS point estimate of the interaction contrasts (locked test confirmation)."""
    X, names = build_interaction_design(
        df, moments, include_month=include_month, include_termination=include_termination,
        rating_mode=rating_mode, sharp_col=sharp_col)
    beta = cmq._ols_fit(X, df["expected_score_loss"].to_numpy().astype(float))
    idx = {n: i for i, n in enumerate(names)}
    return {lab: round(float(beta[idx[lab]]), 4)
            for lab in (PRIMARY_INTERACTION, SECONDARY_INTERACTION) if lab in idx}


# ---------------------------------------------------------------------------
# E. Runners
# ---------------------------------------------------------------------------

ESTIMATION = cmq.ESTIMATION_SPLITS  # ["train","val"]


def _est_test(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    return (df.filter(pl.col("split_set").is_in(ESTIMATION)),
            df.filter(pl.col("split_set") == cmq.CONFIRMATION_SPLIT))


def run_month(nml, sharp, players, tag, n_reps, seed) -> dict[str, Any]:
    j, val = load_joined(nml, sharp, players, tag)
    df, excl = primary_universe(j)
    est, test = _est_test(df)
    moments = car.fit_moments(est)
    cells = cell_adequacy(est)
    print(f"  [c3c] {tag}: est {est.height:,} (sharp×60_180={cells['sharp_x_60_180']})",
          file=sys.stderr)
    primary = fit_interaction(
        est, moments, target="expected_score_loss", model="ols", include_month=False,
        include_termination=True, rating_mode="linear", add_abs_cp=False,
        sharp_col="sharp", cluster_col="mover_player_hash", n_reps=n_reps, seed=seed)
    test_conf = point_interaction(test, moments, include_month=False,
                                  include_termination=True) if test.height else {}
    robustness = _robustness(est, moments, n_reps, seed)
    return {"version_tag": tag, "month": cmq.month_from_tag(tag), "validation": val,
            "exclusions": excl, "cells": cells, "primary": primary,
            "test_confirmation": test_conf, "robustness": robustness,
            "n_est": est.height, "n_test": test.height, "n_reps": n_reps, "seed": seed,
            "nml": nml, "sharp": sharp, "players": players}


def _robustness(est: pl.DataFrame, moments: dict, n_reps: int, seed: int) -> dict[str, Any]:
    """Pre-registered robustness families (per-month; include_month=False)."""
    R: dict[str, Any] = {}
    def fit(**kw):
        base = dict(target="expected_score_loss", model="ols", include_month=False,
                    include_termination=True, rating_mode="linear", add_abs_cp=False,
                    sharp_col="sharp", cluster_col="mover_player_hash",
                    n_reps=n_reps, seed=seed)
        base.update(kw)
        return fit_interaction(est, moments, **base)
    R["continuous_eval"] = fit(add_abs_cp=True)
    bd = est.filter(pl.col("termination_binary") == "board_decided")
    R["board_decided_only"] = fit_interaction(
        bd, car.fit_moments(bd), target="expected_score_loss", model="ols",
        include_month=False, include_termination=False, rating_mode="linear",
        add_abs_cp=False, sharp_col="sharp", cluster_col="mover_player_hash",
        n_reps=n_reps, seed=seed)
    R["rating_bins"] = fit(rating_mode="bins")
    R["rating_quadratic"] = fit(rating_mode="quadratic")
    R["sharp_relaxed"] = _fit_sharpcol(est, moments, "sharp_value_fragility_v1_relaxed", n_reps, seed)
    R["sharp_strict"] = _fit_sharpcol(est, moments, "sharp_value_fragility_v1_strict", n_reps, seed)
    R["target_clipped_cp"] = fit(target="clipped_cp_loss")
    R["logistic_es005"] = fit(target="large_loss_es_005", model="logistic")
    R["logistic_es010"] = fit(target="large_loss_es_010", model="logistic")
    R["cluster_game"] = fit(cluster_col="game_id")
    R["cluster_white"] = fit(cluster_col="white_player_hash")
    R["cluster_black"] = fit(cluster_col="black_player_hash")
    R["surface_bait_exploratory"] = _fit_sharpcol(est, moments, "surface_bait_10es", n_reps, seed)
    return R


def _fit_sharpcol(est, moments, col, n_reps, seed):
    """Refit with an alternative binary moderator as the `sharp` working column."""
    e2 = est.with_columns(pl.col(col).cast(pl.Int64).alias("sharp"))
    return fit_interaction(e2, moments, target="expected_score_loss", model="ols",
                           include_month=False, include_termination=True,
                           rating_mode="linear", add_abs_cp=False, sharp_col="sharp",
                           cluster_col="mover_player_hash", n_reps=n_reps, seed=seed)


def run_pooled(months: list[dict], n_reps: int, seed: int) -> dict[str, Any]:
    frames = []
    for m in months:
        j, _ = load_joined(m["nml"], m["sharp"], m["players"], m["version_tag"])
        df, _ = primary_universe(j)
        frames.append(df)
    pooled = pl.concat(frames, how="vertical")
    est, test = _est_test(pooled)
    moments = car.fit_moments(est)
    cells = cell_adequacy(est)
    print(f"  [c3c] pooled: est {est.height:,} (sharp×60_180={cells['sharp_x_60_180']})",
          file=sys.stderr)
    primary = fit_interaction(
        est, moments, target="expected_score_loss", model="ols", include_month=True,
        include_termination=True, rating_mode="linear", add_abs_cp=False,
        sharp_col="sharp", cluster_col="mover_player_hash", n_reps=n_reps, seed=seed)
    test_conf = point_interaction(test, moments, include_month=True,
                                  include_termination=True) if test.height else {}
    # pooled robustness: continuous-eval + board-decided (the decisive ones)
    rob = {}
    rob["continuous_eval"] = fit_interaction(
        est, moments, target="expected_score_loss", model="ols", include_month=True,
        include_termination=True, rating_mode="linear", add_abs_cp=True,
        sharp_col="sharp", cluster_col="mover_player_hash", n_reps=n_reps, seed=seed)
    bd = est.filter(pl.col("termination_binary") == "board_decided")
    rob["board_decided_only"] = fit_interaction(
        bd, car.fit_moments(bd), target="expected_score_loss", model="ols",
        include_month=True, include_termination=False, rating_mode="linear",
        add_abs_cp=False, sharp_col="sharp", cluster_col="mover_player_hash",
        n_reps=n_reps, seed=seed)
    return {"cells": cells, "primary": primary, "test_confirmation": test_conf,
            "robustness": rob, "n_est": est.height, "n_test": test.height}


# ---------------------------------------------------------------------------
# F. Classification (14.2A criteria)
# ---------------------------------------------------------------------------

def classify(months: list[dict], pooled: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    pa = months[0]["primary"]["primary"]
    pb = months[1]["primary"]["primary"]
    pp = pooled["primary"]["primary"]
    # underpowered check: limiting cell
    min_cell = min(months[0]["cells"]["sharp_x_60_180"], months[1]["cells"]["sharp_x_60_180"])
    reasons.append(f"sharp×60_180 min monthly cell = {min_cell}")
    if pp is None or pp.get("contains_zero") is None:
        return "underpowered_no_claim", reasons + ["pooled interaction not estimable"]
    both_pos = pa["estimate"] > 0 and pb["estimate"] > 0
    reasons.append(f"months {pa['estimate']:+.4f} / {pb['estimate']:+.4f}; "
                   f"pooled {pp['estimate']:+.4f} [{pp['ci_lower']:+.4f},{pp['ci_upper']:+.4f}] "
                   f"{'excl 0' if not pp['contains_zero'] else 'contains 0'}")
    if min_cell < 300:
        reasons.append("limiting cell < 300/month → underpowered per 14.2A kill criterion")
        return "underpowered_no_claim", reasons
    # robustness direction (continuous eval + board-decided), pooled
    ce = pooled["robustness"]["continuous_eval"]["primary"]
    bd = pooled["robustness"]["board_decided_only"]["primary"]
    rob_ok = (ce and ce["estimate"] > 0 and not ce["contains_zero"]
              and bd and bd["estimate"] > 0)
    if both_pos and not pp["contains_zero"] and rob_ok:
        return "strong_support", reasons
    if (pp["estimate"] > 0 and not pp["contains_zero"]) or (pp["estimate"] > 0 and both_pos):
        return "weak_suggestive", reasons
    return "null_no_support", reasons


# ---------------------------------------------------------------------------
# G. Rendering
# ---------------------------------------------------------------------------

def _ci(c: dict | None, sign: bool = True) -> str:
    if not c:
        return "—"
    lo, hi = c.get("ci_lower"), c.get("ci_upper")
    if lo is None or hi is None:
        return f"{c['estimate']:+.4f} [no CI]"
    cz = "contains 0" if c["contains_zero"] else "**excl 0**"
    return f"{c['estimate']:+.4f} [{lo:+.4f}, {hi:+.4f}] {cz}"


_NONCLAIMS = [
    "Not causal; no claim that time pressure causes worse moves or worse reasoning.",
    "`sharp_value_fragility_v1` is an engine-side value-fragility proxy — **NOT human "
    "obviousness** (deferred Tier B) and not a complete account of practical difficulty.",
    "Surface-bait is an exploratory diagnostic only, never a headline; not human obviousness.",
    "No outcome/flagging (C3a/C3b) sharpness model is run here.",
    "No 'degradation curve'; Stockfish eval is objective context, not ground truth; DRAW "
    "remains sparse and not solved; this is not a best-predictor claim.",
    "On any support, the moderation is a small, secondary, predictive/descriptive finding "
    "on top of eval-state-dominant move quality.",
]

_CLASS_TEXT = {
    "strong_support": "**STRONG SUPPORT**",
    "weak_suggestive": "**WEAK / SUGGESTIVE**",
    "null_no_support": "**NULL / NO SUPPORT**",
    "underpowered_no_claim": "**UNDERPOWERED / NO CLAIM**",
}


def render_month_report(p: dict) -> str:
    L: list[str] = []
    a = L.append
    pr = p["primary"]["primary"]
    a(f"# Sharpness Interaction Modeling — {p['version_tag']}")
    a("")
    a("**Ticket:** 14.2B — C3c clock × sharpness move-quality moderation (pre-registered 14.2A)")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Per-month fit of the locked C3c interaction. Primary `clock=60_180 × "
      f"sharp_value_fragility_v1` (train+val, mover-player-clustered): {_ci(pr)}. Single month "
      "is not decisive — see the combined report for the cross-month classification. "
      "Predictive/descriptive moderation only — not causal; not human obviousness.")
    a("")
    a("## 2. Pre-registered design")
    a("")
    a("PREREGISTRATION §C3c (locked 14.2A). Primary estimand = the `clock=60_180:sharp` "
      "interaction coefficient (difference-in-differences); positive ⇒ low-clock association "
      "larger in sharp positions.")
    a("")
    a("## 3. Input artifacts")
    a("")
    a(f"- `{p['nml']}`, `{p['sharp']}`, `{p['players']}` (player metadata gitignored; hashed).")
    a("")
    a("## 4. Join validation")
    a("")
    v = p["validation"]
    a(f"- sharpness rows {v['sharp_rows']:,}, keys unique {v['sharp_keys_unique']}; modeling "
      f"frame rows {v['mf_rows']:,}, keys unique {v['mf_keys_unique']}; joined {v['joined_rows']:,} "
      f"(coverage {v['join_coverage']}); no row multiplication {v['no_row_multiplication']}; "
      f"**sharp recompute mismatches {v['sharp_recompute_mismatches']}**.")
    a("")
    a("## 5. Primary row universe and exclusions")
    a("")
    a(f"- {p['exclusions']}")
    a(f"- Estimation (train+val) rows: {p['n_est']:,}; test rows: {p['n_test']:,}.")
    a("")
    a("## 6. Cell adequacy")
    a("")
    a(f"- {p['cells']} → sharp×60_180 = {p['cells']['sharp_x_60_180']} "
      f"(14.2A CI threshold ≥300); under_60×sharp = {p['cells']['under_60_sharp']} (exploratory).")
    a("")
    a("## 7. Primary model")
    a("")
    a("`expected_score_loss ~ C(clock,ref=over_180) + sharp + clock:sharp + C(checkpoint,"
      "ref=move_10) + C(eval_band,ref=decided) + rating_z + C(termination_binary,"
      "ref=board_decided)` (OLS; month omitted in single-month fit).")
    a("")
    a("## 8. Primary train+val result")
    a("")
    a(f"- `clock=60_180 × sharp`: {_ci(pr)} (clusters "
      f"{p['primary']['meta']['n_clusters']:,}, rows {p['primary']['meta']['n_rows']:,}).")
    a(f"- secondary `clock=under_60 × sharp` (exploratory): {_ci(p['primary']['secondary'])}.")
    a("")
    a("## 9. Locked test confirmation")
    a("")
    a(f"- test-split point estimate `clock=60_180:sharp`: "
      f"{p['test_confirmation'].get(PRIMARY_INTERACTION, '—')}.")
    a("")
    a("## 10. Robustness checks")
    a("")
    L += _robustness_table(p["robustness"])
    a("")
    a("## 11. Exploratory diagnostics")
    a("")
    a(f"- surface-bait moderator (NOT human obviousness): "
      f"{_ci(p['robustness']['surface_bait_exploratory']['primary'])}. Exploratory only.")
    a("")
    a("## 12. Classification under 14.2A criteria")
    a("")
    a("See the combined report for the binding cross-month classification.")
    a("")
    a("## 13. Limitations and caveats")
    a("")
    for c in _NONCLAIMS:
        a(f"- {c}")
    a("")
    return "\n".join(L)


def _robustness_table(R: dict) -> list[str]:
    rows = [
        ("continuous eval control", "continuous_eval"),
        ("board-decided-only", "board_decided_only"),
        ("rating quantile bins", "rating_bins"),
        ("rating quadratic", "rating_quadratic"),
        ("sharp relaxed", "sharp_relaxed"),
        ("sharp strict", "sharp_strict"),
        ("target: clipped_cp (dir.)", "target_clipped_cp"),
        ("logistic ES>0.05 (dir.)", "logistic_es005"),
        ("logistic ES>0.10 (dir.)", "logistic_es010"),
        ("cluster: game", "cluster_game"),
        ("cluster: White-player", "cluster_white"),
        ("cluster: Black-player", "cluster_black"),
    ]
    L = ["| Robustness check | clock=60_180 × sharp |", "|---|---|"]
    for label, key in rows:
        r = R.get(key, {})
        if r.get("skipped"):
            L.append(f"| {label} | skipped: {r['skipped']} |")
        else:
            L.append(f"| {label} | {_ci(r.get('primary'))} |")
    return L


def render_combined_report(months: list[dict], pooled: dict, cls: str, reasons: list[str]) -> str:
    L: list[str] = []
    a = L.append
    tags = [m["version_tag"] for m in months]
    pp = pooled["primary"]["primary"]
    a("# Sharpness Interaction Modeling — Combined")
    a("")
    a("**Ticket:** 14.2B — C3c clock × sharpness move-quality moderation (pre-registered 14.2A)")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Classification: {_CLASS_TEXT.get(cls, cls)}. Pooled primary `clock=60_180 × "
      f"sharp_value_fragility_v1` interaction = {_ci(pp)}; per month "
      f"{_ci(months[0]['primary']['primary'])} / {_ci(months[1]['primary']['primary'])}. "
      "Predictive/descriptive moderation only — not causal, not human obviousness, no "
      "outcome/flagging claim.")
    a("")
    a("## 2. Pre-registered primary question")
    a("")
    a("Does the small controlled `60_180`-vs-`over_180` clock association with next-move ES "
      "loss become larger in sharp/value-fragile positions? Estimand = the `clock=60_180:sharp` "
      "interaction coefficient (DiD); positive ⇒ yes. Locked in PREREGISTRATION §C3c.")
    a("")
    a("## 3. Inputs and joins")
    a("")
    for m in months:
        v = m["validation"]
        a(f"- {m['version_tag']}: joined {v['joined_rows']:,} (coverage {v['join_coverage']}), "
          f"sharp recompute mismatches {v['sharp_recompute_mismatches']}.")
    a("")
    a("## 4. Primary row universe")
    a("")
    for m in months:
        a(f"- {m['version_tag']}: est {m['n_est']:,}, test {m['n_test']:,}.")
    a(f"- pooled: est {pooled['n_est']:,}, test {pooled['n_test']:,}.")
    a("")
    a("## 5. Primary feature and contrast")
    a("")
    a("Feature `sharp_value_fragility_v1` (validated by exact recompute). Contrast `60_180` vs "
      "`over_180` × sharp. Reference clock `over_180`.")
    a("")
    a("## 6. Cell adequacy")
    a("")
    a("| scope | sharp×60_180 | under_60×sharp |")
    a("|---|---|---|")
    for m in months:
        a(f"| {m['version_tag']} | {m['cells']['sharp_x_60_180']} | {m['cells']['under_60_sharp']} |")
    a(f"| pooled | {pooled['cells']['sharp_x_60_180']} | {pooled['cells']['under_60_sharp']} |")
    a("")
    a("(14.2A CI threshold ≥300/month for the limiting sharp×60_180 cell; under_60×sharp "
      "exploratory only.)")
    a("")
    a("## 7. Primary train+val results")
    a("")
    a("| scope | clock=60_180 × sharp | under_60 × sharp (exploratory) |")
    a("|---|---|---|")
    for m in months:
        a(f"| {m['version_tag']} | {_ci(m['primary']['primary'])} | {_ci(m['primary']['secondary'])} |")
    a(f"| pooled | {_ci(pp)} | {_ci(pooled['primary']['secondary'])} |")
    a("")
    a("## 8. Month-specific replication")
    a("")
    a(f"- 2024-09 {_ci(months[0]['primary']['primary'])}; 2024-10 "
      f"{_ci(months[1]['primary']['primary'])}. Same-sign both months: "
      f"{months[0]['primary']['primary']['estimate'] > 0 and months[1]['primary']['primary']['estimate'] > 0}.")
    a("")
    a("## 9. Pooled estimate")
    a("")
    a(f"- `clock=60_180 × sharp`: {_ci(pp)} (clusters {pooled['primary']['meta']['n_clusters']:,}, "
      f"rows {pooled['primary']['meta']['n_rows']:,}).")
    a("")
    a("## 10. Locked test confirmation")
    a("")
    a(f"- pooled test point estimate `clock=60_180:sharp`: "
      f"{pooled['test_confirmation'].get(PRIMARY_INTERACTION, '—')}; per month "
      + "; ".join(f"{m['version_tag']} {m['test_confirmation'].get(PRIMARY_INTERACTION,'—')}"
                  for m in months) + ".")
    a("")
    a("## 11. Robustness checks")
    a("")
    a("Pooled decisive checks:")
    a(f"- continuous eval control: {_ci(pooled['robustness']['continuous_eval']['primary'])}.")
    a(f"- board-decided-only: {_ci(pooled['robustness']['board_decided_only']['primary'])}.")
    a("")
    a("Per-month robustness tables are in the month reports (continuous-eval, board-decided, "
      "rating bins/quadratic, sharp relaxed/strict, clipped-cp + large-loss logistic targets, "
      "game/White/Black clustering).")
    a("")
    a("## 12. Exploratory surface-bait diagnostics")
    a("")
    a("Surface-bait moderator (per month, exploratory; **NOT human obviousness, no headline**): "
      + "; ".join(f"{m['version_tag']} {_ci(m['robustness']['surface_bait_exploratory']['primary'])}"
                  for m in months) + ".")
    a("")
    a("## 13. Success / weak / null classification")
    a("")
    a(f"**{_CLASS_TEXT.get(cls, cls)}.** Basis: " + "; ".join(reasons) + ".")
    a("")
    if cls == "strong_support":
        a("All 14.2A strong-support conditions hold (positive both months, pooled CI excludes "
          "zero, survives continuous-eval + board-decided robustness, limiting cell ≥300/mo). "
          "The clock×sharpness moderation is credited as a **small, secondary, "
          "predictive/descriptive** association — still not causal, still eval-dominated.")
    elif cls == "weak_suggestive":
        a("Support is weak/suggestive: the interaction is directionally positive but does not "
          "meet all strong-support conditions (CI overlap and/or month inconsistency). Reported "
          "as conditional; not headlined.")
    elif cls == "underpowered_no_claim":
        a("The limiting sharp×60_180 cell and/or the clustered interaction CI are too small to "
          "support a claim. Reported as **underpowered / no claim** per the 14.2A kill "
          "criterion — not a null *finding*, an absence of resolving power.")
    else:
        a("No support: the pooled interaction CI overlaps zero with a small effect and/or month "
          "signs conflict and/or robustness shows confounding. The C3c moderation is not "
          "supported in this setup.")
    a("")
    a("## 14. What this does and does not show")
    a("")
    for c in _NONCLAIMS:
        a(f"- {c}")
    a("")
    a("## 15. Recommended next ticket")
    a("")
    nxt = ("14.2C — Sharpness Interaction Robustness / Interpretation Audit"
           if cls in ("strong_support", "weak_suggestive")
           else "14.2C — Null / Power Interpretation and Roadmap Reconciliation Audit")
    a(f"**{nxt}.** Outcome/flagging sharpness (C3a/C3b) remains a separate later arc; "
      "prior-trajectory extraction is an optional follow-up.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# H. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="C3c sharpness × clock move-quality interaction "
                                            "(Ticket 14.2B; pre-registered 14.2A).")
    p.add_argument("--next-move-loss-09", required=True)
    p.add_argument("--next-move-loss-10", required=True)
    p.add_argument("--sharpness-09", required=True)
    p.add_argument("--sharpness-10", required=True)
    p.add_argument("--players-09", required=True)
    p.add_argument("--players-10", required=True)
    p.add_argument("--report-dir", default="reports")
    p.add_argument("--bootstrap-reps", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--smoke", action="store_true",
                   help="mechanics check only; not for final results")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)

    rd = Path(args.report_dir)
    (rd / "phase_reports").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    specs = [
        ("2024_09_250k_v1", args.next_move_loss_09, args.sharpness_09, args.players_09),
        ("2024_10_250k_v1", args.next_move_loss_10, args.sharpness_10, args.players_10),
    ]
    months = [run_month(nml, sh, pl_, tag, args.bootstrap_reps, args.seed)
              for tag, nml, sh, pl_ in specs]
    pooled = run_pooled(months, args.bootstrap_reps, args.seed)
    cls, reasons = classify(months, pooled)
    print(f"[c3c] classification: {cls} ({time.time()-t0:.0f}s)", file=sys.stderr)

    if args.smoke:
        print(f"[c3c] SMOKE complete (reps={args.bootstrap_reps}); reports NOT written.",
              file=sys.stderr)
        print(f"  pooled primary: {_ci(pooled['primary']['primary'])}", file=sys.stderr)
        return 0

    for m in months:
        path = rd / f"sharpness_interaction_{m['version_tag']}.md"
        path.write_text(render_month_report(m))
    comb = rd / "sharpness_interaction_combined.md"
    comb.write_text(render_combined_report(months, pooled, cls, reasons))
    print(f"[c3c] reports written under {rd}/ ; classification {cls}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
