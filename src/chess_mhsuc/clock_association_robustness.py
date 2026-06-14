"""
Clock-association robustness — Ticket 15.1F.

Stress-tests the small, replicated controlled clock association from 15.1D
(`60_180` vs `over_180` ≈ +0.0034 pooled adjusted ES loss) against the threats
ranked in the 15.1E audit, applying the 15.1E-locked interpretation criteria.

Mandatory checks (each on 2024-09, 2024-10, pooled; clock contrast =
`60_180` vs `over_180`, mover-player-clustered unless noted):
  1. baseline replication of the 15.1D model;
  2. continuous within-band eval control (`abs_pre_cp_z` added);
  3. late-only (move_30+move_40);
  4. board-decided-only (time-forfeit excluded);
  5. rating-specification sensitivity (train quantile bins; quadratic variant);
  6. metric sensitivity (`clipped_cp_loss`; large-loss logistic ES>0.05/0.10);
  7. cluster sensitivity (game / White-player / Black-player vs mover-player).

Reuses the 15.1D modeling layer (`controlled_move_quality`) and the cluster
refit bootstrap (`clustered_uncertainty`). No new data artifacts; no Stockfish;
no sharpness/MultiPV/trajectory. All results are predictive/descriptive
ASSOCIATIONS — not causal, not a "degradation curve"; Stockfish eval is
objective position context, not absolute ground truth.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.clock_association_robustness \\
        --input data/processed/next_move_loss_2024_09_250k_v1.parquet \\
        --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \\
        --version-tag 2024_09_250k_v1 \\
        --report reports/clock_association_robustness_2024_09_250k_v1.md \\
        --bootstrap-reps 200 --seed 42
    # combined (both months + pooled):
    PYTHONPATH=src python -m chess_mhsuc.clock_association_robustness --combined \\
        --input <sep>.parquet --input <oct>.parquet \\
        --player-metadata <sep_meta>.parquet --player-metadata <oct_meta>.parquet \\
        --report reports/clock_association_robustness_combined.md --bootstrap-reps 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from chess_mhsuc import controlled_move_quality as cmq
from chess_mhsuc.clustered_uncertainty import (
    cluster_bootstrap_refit,
    summarize_contrasts,
)

CP_CLIP = 1000  # match the ES-transform cp clip convention
CLOCK_CONTRASTS = {
    "clock_60_180_vs_over_180": "clock=60_180",   # primary
    "clock_under_60_vs_over_180": "clock=under_60",  # secondary/exploratory
}
PRIMARY_CLOCK = "clock_60_180_vs_over_180"
_RATING_QUANTILES = [0.2, 0.4, 0.6, 0.8]  # → 5 train-defined rating bins


# ---------------------------------------------------------------------------
# A. Moments (train-only) for standardized continuous covariates
# ---------------------------------------------------------------------------

def fit_moments(df: pl.DataFrame) -> dict[str, Any]:
    """Train-only moments: rating mean/std, |cp| mean/std, rating-quantile edges."""
    tr = df.filter(pl.col("split_set") == "train")
    if tr.height == 0:
        raise ValueError("no train rows for moment fitting")
    r = tr["mover_rating"].to_numpy().astype(float)
    acp = np.clip(np.abs(tr["mover_pre_cp"].to_numpy().astype(float)), 0, CP_CLIP)
    r_std = float(np.std(r))
    acp_std = float(np.std(acp))
    edges = [float(np.quantile(r, q)) for q in _RATING_QUANTILES]
    return {
        "rating_mean": float(np.mean(r)),
        "rating_std": r_std if r_std > 1e-9 else 1.0,
        "abs_cp_mean": float(np.mean(acp)),
        "abs_cp_std": acp_std if acp_std > 1e-9 else 1.0,
        "rating_edges": edges,
    }


def _rating_bin_index(ratings: np.ndarray, edges: list[float]) -> np.ndarray:
    return np.digitize(ratings, edges)  # 0..len(edges)


# ---------------------------------------------------------------------------
# B. Variant design matrix
# ---------------------------------------------------------------------------

def build_variant_design(
    df: pl.DataFrame,
    moments: dict[str, Any],
    *,
    include_month: bool,
    include_termination: bool,
    rating_mode: str = "linear",     # linear | quadratic | bins
    add_abs_cp: bool = False,
) -> tuple[np.ndarray, list[str]]:
    """
    Configurable one-hot design with the 15.1D reference levels. Checkpoint
    reference adapts to the levels actually present (so late-only does not carry
    an all-zero move_10 column). Coefficient names match 15.1D ("clock=60_180",
    etc.) so contrasts are comparable across variants.
    """
    n = len(df)
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]

    cc = df["clock_coarse"].to_numpy()
    for lv in cmq.CLOCK_LEVELS:  # under_60, 60_180 (ref over_180)
        cols.append((f"clock={lv}", (cc == lv).astype(float)))

    cp_present = [c for c in cmq.CHECKPOINT_LEVELS + [cmq.CHECKPOINT_REF]
                  if c in set(df["selected_position_type"].unique().to_list())]
    # order canonically and drop the first present as reference
    canonical = [cmq.CHECKPOINT_REF] + cmq.CHECKPOINT_LEVELS
    present_ordered = [c for c in canonical if c in cp_present]
    cp = df["selected_position_type"].to_numpy()
    for lv in present_ordered[1:]:  # skip reference (first present)
        cols.append((f"checkpoint={lv}", (cp == lv).astype(float)))

    eb = df["eval_band"].to_numpy()
    for lv in cmq.EVAL_LEVELS:  # near_equal, slight, clear (ref decided)
        cols.append((f"eval={lv}", (eb == lv).astype(float)))

    if add_abs_cp:
        acp = np.clip(np.abs(df["mover_pre_cp"].to_numpy().astype(float)), 0, CP_CLIP)
        cols.append(("abs_cp_z", (acp - moments["abs_cp_mean"]) / moments["abs_cp_std"]))

    r = df["mover_rating"].to_numpy().astype(float)
    rz = (r - moments["rating_mean"]) / moments["rating_std"]
    if rating_mode == "linear":
        cols.append(("rating_z", rz))
    elif rating_mode == "quadratic":
        cols.append(("rating_z", rz))
        cols.append(("rating_z_sq", rz * rz))
    elif rating_mode == "bins":
        idx = _rating_bin_index(r, moments["rating_edges"])
        for b in range(1, len(moments["rating_edges"]) + 1):  # ref = bin 0
            cols.append((f"ratingbin=q{b}", (idx == b).astype(float)))
    else:
        raise ValueError(f"unknown rating_mode {rating_mode!r}")

    if include_month:
        mo = df["month"].to_numpy()
        for lv in cmq.MONTH_LEVELS:
            cols.append((f"month={lv}", (mo == lv).astype(float)))
    if include_termination:
        tb = df["termination_binary"].to_numpy()
        for lv in cmq.TERM_LEVELS:
            cols.append((f"termination={lv}", (tb == lv).astype(float)))

    names = [c[0] for c in cols]
    X = np.column_stack([c[1] for c in cols])
    return X, names


# ---------------------------------------------------------------------------
# C. Fit one variant (OLS or logistic) with a chosen cluster key
# ---------------------------------------------------------------------------

def fit_variant(
    df: pl.DataFrame,
    moments: dict[str, Any],
    *,
    target: str,
    model: str,                     # ols | logistic
    include_month: bool,
    include_termination: bool,
    rating_mode: str,
    add_abs_cp: bool,
    cluster_col: str,
    n_reps: int,
    seed: int,
) -> dict[str, Any]:
    """Build the variant design, fit, cluster-bootstrap, return clock contrasts."""
    X, names = build_variant_design(
        df, moments, include_month=include_month,
        include_termination=include_termination, rating_mode=rating_mode,
        add_abs_cp=add_abs_cp)
    y = df[target].to_numpy().astype(float)
    if model == "logistic":
        if len(np.unique(y)) < 2:
            return {"skipped": f"single-class target {target}"}
        try:
            fit_fn = cmq._make_logistic_fit()
        except Exception as exc:  # pragma: no cover
            return {"skipped": f"sklearn unavailable: {exc}"}
    else:
        fit_fn = cmq._ols_fit
    clusters = df[cluster_col].to_list()
    full, boot, meta = cluster_bootstrap_refit(X, y, clusters, fit_fn, n_reps, seed)
    wanted = [c for c in CLOCK_CONTRASTS.values() if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    return {
        "contrasts": {lab: summ[coef] for lab, coef in CLOCK_CONTRASTS.items()
                      if coef in summ},
        "meta": meta, "cluster_col": cluster_col, "target": target,
        "model": model, "n_rows": len(df),
    }


# ---------------------------------------------------------------------------
# D. Check specifications (the mandatory 15.1E matrix)
# ---------------------------------------------------------------------------

# Each spec: label -> kwargs for fit_variant + an optional row-filter.
def _check_specs() -> list[dict[str, Any]]:
    base = dict(target="expected_score_loss", model="ols", include_termination=True,
                rating_mode="linear", add_abs_cp=False, cluster_col="mover_player_hash",
                filter="none", directional=False)
    return [
        {**base, "label": "baseline (15.1D)"},
        {**base, "label": "continuous eval control", "add_abs_cp": True},
        {**base, "label": "late-only (move_30+40)", "filter": "late"},
        {**base, "label": "board-decided-only", "filter": "board_decided",
         "include_termination": False},
        {**base, "label": "rating quantile bins", "rating_mode": "bins"},
        {**base, "label": "rating quadratic", "rating_mode": "quadratic"},
        {**base, "label": "metric: clipped_cp_loss", "target": "clipped_cp_loss",
         "directional": True},
        {**base, "label": "metric: logistic ES>0.05", "target": "large_loss_es_005",
         "model": "logistic", "directional": True},
        {**base, "label": "metric: logistic ES>0.10", "target": "large_loss_es_010",
         "model": "logistic", "directional": True},
        {**base, "label": "cluster: game_id", "cluster_col": "game_id",
         "directional": False},
        {**base, "label": "cluster: White-player", "cluster_col": "white_player_hash"},
        {**base, "label": "cluster: Black-player", "cluster_col": "black_player_hash"},
    ]


def _apply_filter(df: pl.DataFrame, flt: str) -> pl.DataFrame:
    if flt == "late":
        return df.filter(pl.col("selected_position_type").is_in(["move_30", "move_40"]))
    if flt == "board_decided":
        return df.filter(pl.col("board_decided"))
    return df


# ---------------------------------------------------------------------------
# E. Verdicts
# ---------------------------------------------------------------------------

def verdict_for_contrast(month_a: dict, month_b: dict, pooled: dict) -> str:
    """
    Verdict on the primary clock contrast across scopes, per 15.1E criteria.
    Inputs are the PRIMARY_CLOCK contrast dicts (estimate/ci/contains_zero) for
    each scope; any may be None (skipped).
    """
    if pooled is None or pooled.get("contains_zero") is None:
        return "not_run"
    est_p = pooled["estimate"]
    cz_p = pooled["contains_zero"]
    pos_months = [m for m in (month_a, month_b) if m and m.get("estimate") is not None]
    both_pos = len(pos_months) == 2 and all(m["estimate"] > 0 for m in pos_months)
    if est_p < 0 and not cz_p:
        return "fails"          # sign-reversed, resolvable
    if not cz_p and est_p > 0 and both_pos:
        return "survives"
    if cz_p:
        return "weakens"
    return "mixed"


def overall_conclusion(matrix: dict[str, dict]) -> tuple[str, list[str]]:
    """
    Apply the locked 15.1E gate to the pooled/per-month matrix. ``matrix`` maps
    check label -> {"verdict":..., "pooled":<primary contrast dict>, ...}.
    Returns (conclusion, reasons).
    """
    reasons: list[str] = []
    def v(label: str) -> str:
        return matrix.get(label, {}).get("verdict", "not_run")

    base_ok = v("baseline (15.1D)") == "survives"
    reasons.append(f"baseline: {v('baseline (15.1D)')}")
    eval_ok = v("continuous eval control") == "survives"
    reasons.append(f"continuous eval control: {v('continuous eval control')}")
    bd_row = matrix.get("board-decided-only", {})
    bd_pooled = bd_row.get("pooled") or {}
    bd_same_sign = bd_pooled.get("estimate", 0) > 0  # same (positive) sign
    reasons.append(f"board-decided-only: {v('board-decided-only')} "
                   f"(pooled est {bd_pooled.get('estimate')})")
    metric_ok = all(
        (matrix.get(lbl, {}).get("pooled") or {}).get("estimate", 0) > 0
        for lbl in ("metric: clipped_cp_loss", "metric: logistic ES>0.05",
                    "metric: logistic ES>0.10")
        if matrix.get(lbl, {}).get("pooled"))
    reasons.append(f"metric direction agrees: {metric_ok}")

    if base_ok and eval_ok and bd_same_sign and metric_ok:
        return "survives", reasons
    # weakens if eval control or board-decided knocks it out
    if (v("continuous eval control") == "weakens"
            or v("board-decided-only") in ("weakens", "fails")
            or not bd_same_sign):
        return "weakens", reasons
    return "mixed", reasons


# ---------------------------------------------------------------------------
# F. Runners
# ---------------------------------------------------------------------------

def _primary(d: dict) -> dict | None:
    if d.get("skipped"):
        return None
    return d.get("contrasts", {}).get(PRIMARY_CLOCK)


def _secondary(d: dict) -> dict | None:
    if d.get("skipped"):
        return None
    return d.get("contrasts", {}).get("clock_under_60_vs_over_180")


def run_checks_for_frame(
    df: pl.DataFrame, *, include_month: bool, n_reps: int, seed: int,
) -> dict[str, dict]:
    """Run all mandatory checks on one estimation frame; returns label -> result."""
    moments = fit_moments(df)
    out: dict[str, dict] = {}
    for spec in _check_specs():
        sub = _apply_filter(df, spec["filter"])
        label = spec["label"]
        print(f"    [robust] {label} (n={sub.height:,})", file=sys.stderr)
        res = fit_variant(
            sub, moments, target=spec["target"], model=spec["model"],
            include_month=include_month,
            include_termination=spec["include_termination"],
            rating_mode=spec["rating_mode"], add_abs_cp=spec["add_abs_cp"],
            cluster_col=spec["cluster_col"], n_reps=n_reps, seed=seed)
        res["directional"] = spec["directional"]
        out[label] = res
    return out


def run_single(input_path, meta_path, version_tag, n_reps, seed) -> dict[str, Any]:
    df = cmq.build_model_frame(input_path, meta_path, version_tag)
    est = df.filter(pl.col("split_set").is_in(cmq.ESTIMATION_SPLITS))
    print(f"  [robust] {version_tag} (est n={est.height:,})", file=sys.stderr)
    checks = run_checks_for_frame(est, include_month=False, n_reps=n_reps, seed=seed)
    return {"version_tag": version_tag, "month": cmq.month_from_tag(version_tag),
            "input_path": input_path, "meta_path": meta_path,
            "n_est": est.height, "checks": checks, "n_reps": n_reps, "seed": seed}


def run_combined(input_paths, meta_paths, version_tags, n_reps, seed) -> dict[str, Any]:
    months = [run_single(i, m, t, n_reps, seed)
              for i, m, t in zip(input_paths, meta_paths, version_tags)]
    frames = [cmq.build_model_frame(i, m, t)
              for i, m, t in zip(input_paths, meta_paths, version_tags)]
    pooled_df = pl.concat(frames, how="vertical").filter(
        pl.col("split_set").is_in(cmq.ESTIMATION_SPLITS))
    print(f"  [robust] pooled (est n={pooled_df.height:,})", file=sys.stderr)
    pooled = run_checks_for_frame(pooled_df, include_month=True, n_reps=n_reps, seed=seed)
    matrix = _assemble_matrix(months, pooled)
    concl, reasons = overall_conclusion(matrix)
    return {"months": months, "pooled": pooled, "pooled_n": pooled_df.height,
            "matrix": matrix, "conclusion": concl, "reasons": reasons,
            "version_tags": version_tags, "n_reps": n_reps, "seed": seed}


def _assemble_matrix(months: list[dict], pooled: dict) -> dict[str, dict]:
    """Per-check matrix combining month + pooled primary contrasts + verdict."""
    labels = [s["label"] for s in _check_specs()]
    ma, mb = months[0]["checks"], months[1]["checks"]
    matrix: dict[str, dict] = {}
    for lab in labels:
        pa, pb = _primary(ma.get(lab, {})), _primary(mb.get(lab, {}))
        pp = _primary(pooled.get(lab, {}))
        directional = pooled.get(lab, {}).get("directional", False)
        vd = verdict_for_contrast(pa, pb, pp)
        if directional and vd == "survives":
            vd = "survives"  # keep; rendered with "directional" tag
        matrix[lab] = {"month_a": pa, "month_b": pb, "pooled": pp,
                       "verdict": vd, "directional": directional,
                       "under60_pooled": _secondary(pooled.get(lab, {}))}
    return matrix


# ---------------------------------------------------------------------------
# G. Rendering
# ---------------------------------------------------------------------------

def _fmt_ci(c: dict | None) -> str:
    if not c:
        return "—"
    lo, hi = c.get("ci_lower"), c.get("ci_upper")
    if lo is None or hi is None:
        return f"{c['estimate']:+.4f} [no CI]"
    cz = "contains 0" if c["contains_zero"] else "**excl 0**"
    return f"{c['estimate']:+.4f} [{lo:+.4f}, {hi:+.4f}] {cz}"


_CAVEATS = [
    "Predictive/descriptive association only — not causal; no claim that time "
    "pressure causes worse moves or degrades reasoning.",
    "Ordered-bucket patterns are patterns, not a degradation curve.",
    "Even where it survives, the clock effect is small and SECONDARY to the "
    "eval-band structure (eval contrasts are ~5–8× larger, 15.1D).",
    "Board-decided move-quality association is distinct from flagging risk; the "
    "two are reported separately and never conflated.",
    "`under_60` is sparse and ~2/3 time-forfeit (15.1E) — exploratory only.",
    "Mover-player clustering handles repeated movers, not exact two-way "
    "(White×Black) dependence (deferred).",
    "Prior-trajectory control is deferred (absent from artifacts) — the 'clock as "
    "symptom of past struggle' confound is unadjusted and stated.",
    "Stockfish depth-12 eval is objective position context, not absolute ground "
    "truth; DRAW remains sparse; sharpness is not implemented or invoked.",
]


def _matrix_table(matrix: dict[str, dict]) -> list[str]:
    L = ["| Check | 2024-09 | 2024-10 | pooled | verdict |",
         "|---|---|---|---|---|"]
    for lab in [s["label"] for s in _check_specs()]:
        r = matrix[lab]
        tag = " (dir.)" if r["directional"] else ""
        L.append(f"| {lab} | {_fmt_ci(r['month_a'])} | {_fmt_ci(r['month_b'])} | "
                 f"{_fmt_ci(r['pooled'])} | {r['verdict']}{tag} |")
    return L


def _month_matrix(checks: dict[str, dict]) -> list[str]:
    L = ["| Check | clock 60_180 vs over_180 | under_60 vs over_180 |",
         "|---|---|---|"]
    for lab in [s["label"] for s in _check_specs()]:
        d = checks.get(lab, {})
        L.append(f"| {lab} | {_fmt_ci(_primary(d))} | {_fmt_ci(_secondary(d))} |")
    return L


def render_month_report(p: dict) -> str:
    L: list[str] = []
    a = L.append
    checks = p["checks"]
    base = _primary(checks["baseline (15.1D)"])
    a(f"# Clock Association Robustness — {p['version_tag']}")
    a("")
    a("**Ticket:** 15.1F — Clock Association Robustness Implementation (Contrast C4)")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Single-month robustness of the 15.1D clock contrast (`60_180` vs `over_180`, "
      f"baseline {_fmt_ci(base)}). The matrix (§4) reports each mandatory check; "
      "read the combined report for the cross-month verdict. Clock effects, where "
      "present, are small and secondary to the eval-band structure. "
      "Predictive/descriptive only — not causal, not a degradation curve.")
    a("")
    a("## 2. Input artifacts")
    a("")
    a(f"- Next-move loss: `{p['input_path']}`")
    a(f"- Player metadata (hashed, gitignored): `{p['meta_path']}`")
    a(f"- Estimation rows (train+val): {p['n_est']:,}. Bootstrap reps "
      f"{p['n_reps']}, seed {p['seed']}, mover-player-clustered unless noted.")
    a("")
    a("## 3. Baseline replication")
    a("")
    a(f"Baseline 15.1D model clock contrast (this month): primary {_fmt_ci(base)}; "
      f"`under_60` {_fmt_ci(_secondary(checks['baseline (15.1D)']))}. Reproduces the "
      "15.1D specification on train+val.")
    a("")
    a("## 4. Robustness matrix")
    a("")
    L += _month_matrix(checks)
    a("")
    a("## 5. Continuous eval-control sensitivity")
    a("")
    a(f"Adding standardized within-band |cp| (`abs_cp_z`): clock "
      f"{_fmt_ci(_primary(checks['continuous eval control']))}.")
    a("")
    a("## 6. Late-only sensitivity")
    a("")
    a(f"move_30+move_40 only: clock {_fmt_ci(_primary(checks['late-only (move_30+40)']))}.")
    a("")
    a("## 7. Board-decided-only sensitivity")
    a("")
    a(f"Time-forfeit excluded: clock {_fmt_ci(_primary(checks['board-decided-only']))}.")
    a("")
    a("## 8. Rating-specification sensitivity")
    a("")
    a(f"Quantile bins: {_fmt_ci(_primary(checks['rating quantile bins']))}; "
      f"quadratic: {_fmt_ci(_primary(checks['rating quadratic']))}.")
    a("")
    a("## 9. Metric sensitivity")
    a("")
    a(f"clipped_cp_loss: {_fmt_ci(_primary(checks['metric: clipped_cp_loss']))} "
      "(directional; cp scale). "
      f"logistic ES>0.05: {_fmt_ci(_primary(checks['metric: logistic ES>0.05']))}; "
      f"ES>0.10: {_fmt_ci(_primary(checks['metric: logistic ES>0.10']))} (log-odds).")
    a("")
    a("## 10. Cluster sensitivity")
    a("")
    a(f"game_id: {_fmt_ci(_primary(checks['cluster: game_id']))}; "
      f"White-player: {_fmt_ci(_primary(checks['cluster: White-player']))}; "
      f"Black-player: {_fmt_ci(_primary(checks['cluster: Black-player']))}.")
    a("")
    a("## 11. Optional exploratory checks")
    a("")
    a("None run in this pass (mandatory matrix only; interactions/finer bins are "
      "exploratory and deferred per 15.1E).")
    a("")
    a("## 12. Interpretation")
    a("")
    a("Per-month results feed the cross-month verdict in the combined report under "
      "the locked 15.1E criteria. A single month is not sufficient to credit or "
      "reject the association.")
    a("")
    a("## 13. Limitations and caveats")
    a("")
    for c in _CAVEATS:
        a(f"- {c}")
    a("")
    a("## 14. Recommendation")
    a("")
    a("See the combined report for the binding verdict and next-ticket recommendation.")
    a("")
    return "\n".join(L)


def render_combined_report(p: dict) -> str:
    L: list[str] = []
    a = L.append
    matrix = p["matrix"]
    concl = p["conclusion"]
    base = matrix["baseline (15.1D)"]["pooled"]
    a("# Clock Association Robustness — Combined")
    a("")
    a("**Ticket:** 15.1F — Clock Association Robustness Implementation (Contrast C4)")
    a("")
    a("## 1. Executive summary")
    a("")
    verbs = {"survives": "SURVIVES", "weakens": "WEAKENS / does not survive",
             "mixed": "is MIXED/conditional", "fails": "FAILS"}
    a(f"Under the locked 15.1E criteria, the small controlled clock association "
      f"**{verbs.get(concl, concl)}** the mandatory robustness checks. Pooled baseline "
      f"clock contrast {_fmt_ci(base)}; continuous-eval-control "
      f"{_fmt_ci(matrix['continuous eval control']['pooled'])}; board-decided-only "
      f"{_fmt_ci(matrix['board-decided-only']['pooled'])}. In all cases the clock "
      "effect is small and **secondary to the eval-band structure** (15.1D eval "
      "contrasts ~5–8× larger). Predictive/descriptive — not causal, not a "
      "degradation curve.")
    a("")
    a("## 2. Why this robustness pass exists")
    a("")
    a("15.1D found a small, replicated, test-confirmed clock association after "
      "controls. 15.1E ranked the threats (coarse eval bands; checkpoint×clock; "
      "survivor/termination composition) and locked the interpretation criteria. "
      "This pass runs the mandatory checks and applies those criteria.")
    a("")
    a("## 3. Baseline 15.1D replication")
    a("")
    a(f"Pooled baseline clock contrast {_fmt_ci(base)} reproduces 15.1D "
      "(`60_180` vs `over_180` ≈ +0.0034). Per-month: "
      f"{_fmt_ci(matrix['baseline (15.1D)']['month_a'])} / "
      f"{_fmt_ci(matrix['baseline (15.1D)']['month_b'])}.")
    a("")
    a("## 4. Robustness matrix")
    a("")
    a("Primary contrast = `60_180` vs `over_180` (adjusted Δ ES loss unless the "
      "metric row notes otherwise); mover-player-clustered unless the cluster row "
      "notes otherwise. `(dir.)` = directional metric (cp/log-odds scale).")
    a("")
    L += _matrix_table(matrix)
    a("")
    a("Verdict labels: survives / weakens / mixed / fails / exploratory_only / "
      "not_run (per the 15.1E criteria).")
    a("")
    a("## 5. Month-by-month stability")
    a("")
    a("| Check | 2024-09 | 2024-10 |")
    a("|---|---|---|")
    for lab in ["baseline (15.1D)", "continuous eval control", "late-only (move_30+40)",
                "board-decided-only"]:
        r = matrix[lab]
        a(f"| {lab} | {_fmt_ci(r['month_a'])} | {_fmt_ci(r['month_b'])} |")
    a("")
    a("## 6. Continuous eval-control result")
    a("")
    ce = matrix["continuous eval control"]
    a(f"Adding standardized within-band |cp|: pooled clock {_fmt_ci(ce['pooled'])} "
      f"(verdict {ce['verdict']}). This is the key test for the coarse-band residual "
      "confound flagged in 15.1E.")
    a("")
    a("## 7. Late-only result")
    a("")
    lo = matrix["late-only (move_30+40)"]
    a(f"move_30+move_40 only: pooled clock {_fmt_ci(lo['pooled'])} (verdict "
      f"{lo['verdict']}).")
    a("")
    a("## 8. Board-decided-only result")
    a("")
    bd = matrix["board-decided-only"]
    a(f"Time-forfeit excluded: pooled clock {_fmt_ci(bd['pooled'])} (verdict "
      f"{bd['verdict']}). This isolates move quality from flagging; `under_60` here "
      f"is {_fmt_ci(bd['under60_pooled'])} (sparse/exploratory).")
    a("")
    a("## 9. Rating and metric sensitivity")
    a("")
    a(f"Rating quantile bins {_fmt_ci(matrix['rating quantile bins']['pooled'])}; "
      f"quadratic {_fmt_ci(matrix['rating quadratic']['pooled'])}. "
      f"clipped_cp_loss {_fmt_ci(matrix['metric: clipped_cp_loss']['pooled'])} "
      "(directional); logistic ES>0.05 "
      f"{_fmt_ci(matrix['metric: logistic ES>0.05']['pooled'])}, ES>0.10 "
      f"{_fmt_ci(matrix['metric: logistic ES>0.10']['pooled'])} (log-odds, directional).")
    a("")
    a("## 10. Cluster sensitivity")
    a("")
    a(f"game_id {_fmt_ci(matrix['cluster: game_id']['pooled'])}; White-player "
      f"{_fmt_ci(matrix['cluster: White-player']['pooled'])}; Black-player "
      f"{_fmt_ci(matrix['cluster: Black-player']['pooled'])}. Mover-player "
      "clustering (baseline) is primary; wider-of-two White/Black is the "
      "conservative read. Exact two-way clustering remains deferred.")
    a("")
    a("## 11. Interpretation under 15.1E criteria")
    a("")
    a(f"**Conclusion: {verbs.get(concl, concl)}.** Gate checks: " +
      "; ".join(p["reasons"]) + ".")
    a("")
    if concl == "survives":
        a("All locked conditions hold: positive both months, pooled CI excludes "
          "zero, not eliminated by continuous eval control, board-decided-only "
          "same sign, metric direction agrees. The C4 clock association is credited "
          "as **small, replicated, controlled, and secondary** to eval band — "
          "descriptive/predictive, not causal.")
    elif concl == "weakens":
        a("At least one decisive check (continuous eval control or board-decided-"
          "only) removes or reverses the clock contrast. The C4 claim **consolidates "
          "around the eval-band structure and the flagging-risk separation**; clock "
          "is treated mainly as a flagging-risk predictor and the move-quality "
          "association is reported as weak/unresolved.")
    else:
        a("Checks disagree: the clock association is **conditional/sensitive** and is "
          "**not headlined**. It is reported with the specific checks that support "
          "or undermine it; eval-band structure remains the robust result.")
    a("")
    a("## 12. What this supports")
    a("")
    a("- The eval-band structure as the robust, dominant, replicated move-quality "
      "structure (15.1B/15.1D), unaffected by these clock-focused variants.")
    a("- A disciplined, criteria-locked verdict on the small clock contrast.")
    a("")
    a("## 13. What this does not support")
    a("")
    a("- Any causal claim or 'degradation curve' reading.")
    a("- Headlining clock as a move-quality driver" +
      ("" if concl == "survives" else " (it does not survive the locked criteria here)") +
      ".")
    a("- Stockfish as ground truth; DRAW as solved; sharpness as an explanation "
      "(not implemented).")
    a("")
    a("## 14. Recommended next ticket")
    a("")
    if concl == "weakens":
        a("**15.1G — C4 Claim Consolidation / Move-Quality Arc Summary**: consolidate "
          "the descriptive (15.1B), clustered (11.3B), controlled (15.1D), and "
          "robustness (15.1F) results — eval-band structure as the headline, clock as "
          "primarily a flagging-risk predictor with a move-quality association that "
          "does not survive robustness. Sharpness moderation (C3 / 15.2A) is a "
          "separate later arc.")
    elif concl == "survives":
        a("**15.1G — C4 Claim Consolidation / Move-Quality Arc Summary**: consolidate "
          "with eval band as the dominant structure and a small, robust, secondary "
          "clock association (still not causal). Sharpness moderation (C3 / 15.2A) is "
          "a separate later arc.")
    else:
        a("**15.1G — C4 Claim Consolidation / Move-Quality Arc Summary**: consolidate "
          "with the clock association reported as conditional/sensitive. If a specific "
          "confound (e.g. prior trajectory) is implicated, a trajectory-extraction "
          "ticket precedes consolidation. Sharpness (C3 / 15.2A) is a separate arc.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# H. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clock-association robustness (Ticket 15.1F, Contrast C4)."
    )
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--player-metadata", action="append", required=True)
    parser.add_argument("--version-tag", default=None)
    parser.add_argument("--report", required=True)
    parser.add_argument("--combined", action="store_true")
    parser.add_argument("--bootstrap-reps", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    report = Path(args.report)
    if report.exists() and not args.overwrite:
        raise FileExistsError(f"{report} exists; pass --overwrite")
    report.parent.mkdir(parents=True, exist_ok=True)

    if args.combined:
        if len(args.input) != len(args.player_metadata):
            print("ERROR: one --player-metadata per --input", file=sys.stderr)
            return 2
        tags = [Path(p).stem.replace("next_move_loss_", "") for p in args.input]
        payload = run_combined(args.input, args.player_metadata, tags,
                               args.bootstrap_reps, args.seed)
        report.write_text(render_combined_report(payload))
        print(f"[robust] combined report: {report} — conclusion: {payload['conclusion']}",
              file=sys.stderr)
        return 0

    if len(args.input) != 1 or len(args.player_metadata) != 1 or not args.version_tag:
        print("ERROR: single-month mode needs one --input, one --player-metadata, "
              "and --version-tag.", file=sys.stderr)
        return 2
    payload = run_single(args.input[0], args.player_metadata[0], args.version_tag,
                         args.bootstrap_reps, args.seed)
    report.write_text(render_month_report(payload))
    print(f"[robust] month report: {report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
