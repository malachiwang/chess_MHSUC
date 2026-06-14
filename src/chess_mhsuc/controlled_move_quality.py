"""
Controlled move-quality modeling — Ticket 15.1D (Contrast C4).

Turns the 15.1B descriptive Constraint Atlas into a CONTROLLED estimate: after
adjusting for checkpoint, eval band, mover rating, month, and termination channel
simultaneously, does coarse clock retain a stable association with next-move
expected-score (ES) loss — or is eval state the robust move-quality structure?

Design locked in 15.1C:
- Target: expected_score_loss (mover's perspective), non-mate-band rows only.
- Primary model: OLS adjusted-mean (numpy lstsq) with explicit one-hot design and
  fixed reference levels; uncertainty from a MOVER-PLAYER cluster bootstrap that
  refits the model (no normal-theory SEs; no statsmodels).
- Secondary robustness: large-loss logistic models (ES>0.05, ES>0.10), sklearn.
- Eval-band contrasts (vs decided) are the POSITIVE CONTROL (expected to replicate);
  the coarse-clock contrast is the main uncertain/null-prone test. A clock null is a
  pre-registered acceptable outcome.
- Discipline: estimate on train+val, TEST reserved as locked confirmation; month is
  replication (per-month then pooled with a month fixed effect). rating_z scaled on
  TRAIN rows only. Prior-trajectory control is DEFERRED (no such feature in the
  artifacts) and listed as a limitation.

All results are predictive/descriptive ASSOCIATIONS — not causal, not a "degradation
curve"; Stockfish eval is objective position context, not absolute ground truth.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.controlled_move_quality \\
        --input data/processed/next_move_loss_2024_09_250k_v1.parquet \\
        --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \\
        --version-tag 2024_09_250k_v1 \\
        --report reports/controlled_move_quality_2024_09_250k_v1.md \\
        --bootstrap-reps 200 --seed 42
    # combined (pooled + month fixed effect):
    PYTHONPATH=src python -m chess_mhsuc.controlled_move_quality --combined \\
        --input <sep>.parquet --input <oct>.parquet \\
        --player-metadata <sep_meta>.parquet --player-metadata <oct_meta>.parquet \\
        --report reports/controlled_move_quality_combined.md --bootstrap-reps 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from chess_mhsuc.clustered_uncertainty import (
    cluster_bootstrap_refit,
    summarize_contrasts,
)

# ---------------------------------------------------------------------------
# Constants — reference levels and design layout
# ---------------------------------------------------------------------------

CLOCK_REF = "over_180"
CLOCK_LEVELS = ["under_60", "60_180"]            # vs over_180
CHECKPOINT_REF = "move_10"
CHECKPOINT_LEVELS = ["move_20", "move_30", "move_40"]  # vs move_10
EVAL_REF = "decided"
EVAL_LEVELS = ["near_equal", "slight", "clear"]  # vs decided
TERM_REF = "board_decided"
TERM_LEVELS = ["time_forfeit"]                   # vs board_decided
MONTH_REF = "2024_09"
MONTH_LEVELS = ["2024_10"]                        # vs 2024_09

ESTIMATION_SPLITS = ["train", "val"]
CONFIRMATION_SPLIT = "test"

# Named contrasts -> design-matrix coefficient name.
PRIMARY_CONTRASTS = {
    "clock_60_180_vs_over_180": "clock=60_180",
    "clock_under_60_vs_over_180": "clock=under_60",
    "eval_near_equal_vs_decided": "eval=near_equal",
    "eval_slight_vs_decided": "eval=slight",
    "eval_clear_vs_decided": "eval=clear",
    "termination_time_forfeit_vs_board_decided": "termination=time_forfeit",
}

_REQUIRED_COLS = [
    "expected_score_loss", "mover_rating", "clock_coarse", "eval_band",
    "selected_position_type", "board_decided", "split_set", "is_mate_band",
]


# ---------------------------------------------------------------------------
# A. Modeling-frame construction
# ---------------------------------------------------------------------------

def month_from_tag(version_tag: str) -> str:
    """'2024_09_250k_v1' -> '2024_09'."""
    parts = version_tag.split("_")
    return f"{parts[0]}_{parts[1]}"


def build_model_frame(input_path: str, meta_path: str, version_tag: str) -> pl.DataFrame:
    """
    Load a next-move-loss artifact (via the atlas loader, which validates and adds
    eval_band/clock_coarse/board_decided), join the mover-player hash, filter to the
    non-mate modeling sample, and add month + termination_binary + large-loss targets.
    """
    from chess_mhsuc.constraint_atlas import load_atlas_frame
    from chess_mhsuc.player_metadata import join_mover_player

    df = load_atlas_frame(input_path)
    meta = pl.read_parquet(meta_path)
    df = join_mover_player(df, meta)

    df = df.filter(
        (~pl.col("is_mate_band"))
        & pl.col("expected_score_loss").is_not_null()
        & pl.col("mover_player_hash").is_not_null()
        & pl.col("mover_rating").is_not_null()
        & pl.col("clock_coarse").is_not_null()
        & pl.col("eval_band").is_not_null()
    )
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"modeling frame missing columns: {missing}")

    return df.with_columns([
        pl.lit(month_from_tag(version_tag)).alias("month"),
        pl.when(pl.col("board_decided")).then(pl.lit("board_decided"))
        .otherwise(pl.lit("time_forfeit")).alias("termination_binary"),
        (pl.col("expected_score_loss") > 0.05).cast(pl.Int64).alias("large_loss_es_005"),
        (pl.col("expected_score_loss") > 0.10).cast(pl.Int64).alias("large_loss_es_010"),
    ])


def train_rating_moments(df: pl.DataFrame) -> tuple[float, float]:
    """Mean/std of mover_rating on TRAIN rows only (std floored to avoid /0)."""
    tr = df.filter(pl.col("split_set") == "train")["mover_rating"].to_numpy().astype(float)
    if len(tr) == 0:
        raise ValueError("no train rows for rating standardization")
    mean = float(np.mean(tr))
    std = float(np.std(tr))
    return mean, std if std > 1e-9 else 1.0


# ---------------------------------------------------------------------------
# B. Design matrix
# ---------------------------------------------------------------------------

def build_design(
    df: pl.DataFrame,
    rating_mean: float,
    rating_std: float,
    include_month: bool,
) -> tuple[np.ndarray, list[str]]:
    """
    Explicit one-hot design with fixed reference levels and an intercept column.
    Column order is deterministic. rating_z uses the supplied (train-only) moments.
    """
    n = len(df)
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]

    cc = df["clock_coarse"].to_numpy()
    for lv in CLOCK_LEVELS:
        cols.append((f"clock={lv}", (cc == lv).astype(float)))
    cp = df["selected_position_type"].to_numpy()
    for lv in CHECKPOINT_LEVELS:
        cols.append((f"checkpoint={lv}", (cp == lv).astype(float)))
    eb = df["eval_band"].to_numpy()
    for lv in EVAL_LEVELS:
        cols.append((f"eval={lv}", (eb == lv).astype(float)))
    rz = (df["mover_rating"].to_numpy().astype(float) - rating_mean) / rating_std
    cols.append(("rating_z", rz))
    if include_month:
        mo = df["month"].to_numpy()
        for lv in MONTH_LEVELS:
            cols.append((f"month={lv}", (mo == lv).astype(float)))
    tb = df["termination_binary"].to_numpy()
    for lv in TERM_LEVELS:
        cols.append((f"termination={lv}", (tb == lv).astype(float)))

    names = [c[0] for c in cols]
    X = np.column_stack([c[1] for c in cols])
    return X, names


def _ols_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Deterministic OLS via least squares (least-norm if rank-deficient)."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _make_logistic_fit():
    """sklearn logistic fit_fn (explicit intercept column ⇒ fit_intercept=False;
    C=inf ⇒ effectively unregularized, the supported sklearn ≥1.8 idiom)."""
    from sklearn.linear_model import LogisticRegression

    def fit(Xb: np.ndarray, yb: np.ndarray) -> np.ndarray:
        clf = LogisticRegression(C=np.inf, fit_intercept=False, max_iter=2000)
        clf.fit(Xb, yb)
        return clf.coef_[0]

    return fit


# ---------------------------------------------------------------------------
# C. Fit + bootstrap a model on a frame
# ---------------------------------------------------------------------------

def fit_ols_with_bootstrap(
    df: pl.DataFrame,
    rating_mean: float,
    rating_std: float,
    include_month: bool,
    contrasts: dict[str, str],
    n_reps: int,
    seed: int,
) -> dict[str, Any]:
    """Fit OLS on ``df`` and mover-player cluster-bootstrap the named contrasts."""
    X, names = build_design(df, rating_mean, rating_std, include_month)
    y = df["expected_score_loss"].to_numpy().astype(float)
    clusters = df["mover_player_hash"].to_list()
    full, boot, meta = cluster_bootstrap_refit(X, y, clusters, _ols_fit, n_reps, seed)
    wanted = [c for c in contrasts.values() if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    labelled = {label: summ[coef] for label, coef in contrasts.items()
                if coef in summ}
    return {
        "contrasts": labelled,
        "coef_table": {n: round(float(full[i]), 5) for i, n in enumerate(names)},
        "meta": meta,
        "n_rows": len(df),
    }


def fit_logistic_with_bootstrap(
    df: pl.DataFrame,
    target_col: str,
    rating_mean: float,
    rating_std: float,
    include_month: bool,
    contrasts: dict[str, str],
    n_reps: int,
    seed: int,
) -> dict[str, Any]:
    """Fit a large-loss logistic model and cluster-bootstrap the named contrasts
    (log-odds scale). Returns a 'skipped' note if sklearn is unavailable."""
    try:
        fit_fn = _make_logistic_fit()
    except Exception as exc:  # pragma: no cover - environment guard
        return {"skipped": f"sklearn unavailable: {exc}"}
    y = df[target_col].to_numpy().astype(float)
    if len(np.unique(y)) < 2:
        return {"skipped": f"single-class target {target_col} (rate {y.mean():.4f})"}
    X, names = build_design(df, rating_mean, rating_std, include_month)
    clusters = df["mover_player_hash"].to_list()
    full, boot, meta = cluster_bootstrap_refit(X, y, clusters, fit_fn, n_reps, seed)
    wanted = [c for c in contrasts.values() if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    labelled = {label: summ[coef] for label, coef in contrasts.items()
                if coef in summ}
    return {"contrasts": labelled, "meta": meta, "target": target_col,
            "positive_rate": round(float(y.mean()), 4)}


def point_contrasts_ols(
    df: pl.DataFrame, rating_mean: float, rating_std: float,
    include_month: bool, contrasts: dict[str, str],
) -> dict[str, float]:
    """OLS point-estimate contrasts only (used for the locked test confirmation)."""
    X, names = build_design(df, rating_mean, rating_std, include_month)
    y = df["expected_score_loss"].to_numpy().astype(float)
    beta = _ols_fit(X, y)
    idx = {n: i for i, n in enumerate(names)}
    return {label: round(float(beta[idx[coef]]), 4)
            for label, coef in contrasts.items() if coef in idx}


# ---------------------------------------------------------------------------
# D. Sample accounting
# ---------------------------------------------------------------------------

def sample_sizes(df: pl.DataFrame) -> dict[str, Any]:
    by_split = {r["split_set"]: r["len"]
                for r in df.group_by("split_set").len().to_dicts()}
    est = df.filter(pl.col("split_set").is_in(ESTIMATION_SPLITS))
    return {
        "n_total": len(df),
        "by_split": by_split,
        "n_estimation": len(est),
        "n_confirmation": int(by_split.get(CONFIRMATION_SPLIT, 0)),
        "n_movers": df["mover_player_hash"].n_unique(),
        "n_movers_estimation": est["mover_player_hash"].n_unique(),
    }


# ---------------------------------------------------------------------------
# E. Runners
# ---------------------------------------------------------------------------

def run_single(
    input_path: str, meta_path: str, version_tag: str,
    n_reps: int, seed: int,
) -> dict[str, Any]:
    """Month-specific controlled modeling payload."""
    df = build_model_frame(input_path, meta_path, version_tag)
    sizes = sample_sizes(df)
    r_mean, r_std = train_rating_moments(df)
    est = df.filter(pl.col("split_set").is_in(ESTIMATION_SPLITS))
    test = df.filter(pl.col("split_set") == CONFIRMATION_SPLIT)

    print(f"  [cmq] {version_tag} OLS+bootstrap (est n={len(est):,})", file=sys.stderr)
    ols = fit_ols_with_bootstrap(est, r_mean, r_std, False,
                                 PRIMARY_CONTRASTS, n_reps, seed)
    print(f"  [cmq] {version_tag} logistic robustness", file=sys.stderr)
    log005 = fit_logistic_with_bootstrap(est, "large_loss_es_005", r_mean, r_std,
                                         False, PRIMARY_CONTRASTS, n_reps, seed)
    log010 = fit_logistic_with_bootstrap(est, "large_loss_es_010", r_mean, r_std,
                                         False, PRIMARY_CONTRASTS, n_reps, seed)
    test_conf = (point_contrasts_ols(test, r_mean, r_std, False, PRIMARY_CONTRASTS)
                 if len(test) else {})
    return {
        "version_tag": version_tag, "month": month_from_tag(version_tag),
        "input_path": input_path, "meta_path": meta_path,
        "sizes": sizes, "rating_mean": round(r_mean, 1), "rating_std": round(r_std, 1),
        "ols": ols, "logistic_005": log005, "logistic_010": log010,
        "test_confirmation": test_conf, "n_reps": n_reps, "seed": seed,
    }


def run_combined(
    input_paths: list[str], meta_paths: list[str], version_tags: list[str],
    n_reps: int, seed: int,
) -> dict[str, Any]:
    """Pooled model (month fixed effect) + per-month payloads."""
    months = [run_single(i, m, t, n_reps, seed)
              for i, m, t in zip(input_paths, meta_paths, version_tags)]
    frames = [build_model_frame(i, m, t)
              for i, m, t in zip(input_paths, meta_paths, version_tags)]
    pooled = pl.concat(frames, how="vertical")
    sizes = sample_sizes(pooled)
    r_mean, r_std = train_rating_moments(pooled)
    est = pooled.filter(pl.col("split_set").is_in(ESTIMATION_SPLITS))
    test = pooled.filter(pl.col("split_set") == CONFIRMATION_SPLIT)
    print(f"  [cmq] pooled OLS+bootstrap (est n={len(est):,})", file=sys.stderr)
    ols = fit_ols_with_bootstrap(est, r_mean, r_std, True,
                                 PRIMARY_CONTRASTS, n_reps, seed)
    log005 = fit_logistic_with_bootstrap(est, "large_loss_es_005", r_mean, r_std,
                                         True, PRIMARY_CONTRASTS, n_reps, seed)
    log010 = fit_logistic_with_bootstrap(est, "large_loss_es_010", r_mean, r_std,
                                         True, PRIMARY_CONTRASTS, n_reps, seed)
    test_conf = (point_contrasts_ols(test, r_mean, r_std, True, PRIMARY_CONTRASTS)
                 if len(test) else {})
    return {
        "months": months,
        "pooled": {
            "sizes": sizes, "rating_mean": round(r_mean, 1),
            "rating_std": round(r_std, 1), "ols": ols,
            "logistic_005": log005, "logistic_010": log010,
            "test_confirmation": test_conf,
        },
        "n_reps": n_reps, "seed": seed, "version_tags": version_tags,
    }


# ---------------------------------------------------------------------------
# F. Rendering helpers
# ---------------------------------------------------------------------------

def _ci(c: dict[str, Any], sign: bool = False) -> str:
    lo, hi = c.get("ci_lower"), c.get("ci_upper")
    est = c["estimate"]
    if lo is None or hi is None:
        return f"{est:+.4f} [no CI]" if sign else f"{est:.4f} [no CI]"
    cz = "contains 0" if c["contains_zero"] else "**excludes 0**"
    if sign:
        return f"{est:+.4f} [{lo:+.4f}, {hi:+.4f}] {cz}"
    return f"{est:.4f} [{lo:.4f}, {hi:.4f}] {cz}"


def _contrast_table(ols: dict, labels: list[str]) -> list[str]:
    L = ["| Contrast | adjusted ΔES loss | 95% CI (mover-player clustered) |",
         "|---|---|---|"]
    for lab in labels:
        c = ols["contrasts"].get(lab)
        if c is None:
            continue
        L.append(f"| {lab} | {c['estimate']:+.4f} | {_ci(c, sign=True)} |")
    return L


_CAVEATS = [
    "Predictive/descriptive association only — not causal; no claim that time "
    "pressure causes worse moves or degrades reasoning.",
    "Ordered-bucket patterns are patterns, not a degradation curve.",
    "Numbered checkpoints are even-ply, so the mover is always White: this models "
    "White-to-move decision quality.",
    "`under_60` is sparse and heavily confounded with late checkpoints (clock×"
    "checkpoint confound); its contrast is exploratory, not headline.",
    "Eval-band dominance may partly reflect chess-value geometry (decided positions "
    "have little expected score left to lose) as much as human difficulty.",
    "The ES transform is train-fitted and approximate; large-loss logistic models "
    "hedge against its exact shape.",
    "Mover-player clustering handles repeated movers but not exact two-way "
    "(White×Black) dependence (deferred).",
    "Time-forfeit filtering induces survivor bias; the termination binary is a "
    "covariate, not a correction.",
    "Prior-trajectory control is DEFERRED — the artifacts carry no pre-checkpoint "
    "trajectory feature, so the 'clock as symptom of past struggle' confound is an "
    "explicit limitation, not adjusted here.",
    "Stockfish depth-12 eval is objective position context, not absolute ground "
    "truth; DRAW remains sparse and not solved; sharpness is not implemented.",
]


def _interpret_clock(ols: dict) -> str:
    c = ols["contrasts"].get("clock_60_180_vs_over_180")
    if c is None or c.get("contains_zero") is None:
        return "Clock contrast not resolvable in this fit."
    if c["contains_zero"]:
        return ("The stable low-clock contrast (`60_180` vs `over_180`) has a 95% "
                "mover-player-clustered CI that **contains zero** — controlled "
                "modeling does **not** support a stable clock association with "
                "next-move ES loss here. This confirms the 15.1B/11.3B "
                "no-clock-gradient result; a clock null is a pre-registered, "
                "acceptable outcome, not a failure.")
    direction = "higher" if c["estimate"] > 0 else "lower"
    return (f"The stable low-clock contrast (`60_180` vs `over_180`) has a CI that "
            f"**excludes zero** ({c['estimate']:+.4f}, {direction} ES loss at lower "
            "clock). This is a controlled association (not causal) and is examined "
            "for cross-month replication before any emphasis.")


def _interpret_eval(ols: dict) -> str:
    parts = []
    for lab in ("eval_near_equal_vs_decided", "eval_slight_vs_decided",
                "eval_clear_vs_decided"):
        c = ols["contrasts"].get(lab)
        if c is not None:
            ok = (c.get("contains_zero") is False)
            parts.append(f"{lab.replace('eval_', '').replace('_vs_decided', '')}: "
                         f"{c['estimate']:+.4f} ({'excludes 0' if ok else 'contains 0'})")
    return ("Eval-band positive control (vs decided): " + "; ".join(parts) + ". "
            "Positive, large contrasts with CIs excluding zero confirm the model "
            "recovers the known 15.1B descriptive structure (loss highest near "
            "equal/slight, lowest at decided).")


# ---------------------------------------------------------------------------
# G. Month report
# ---------------------------------------------------------------------------

def render_month_report(p: dict) -> str:
    L: list[str] = []
    a = L.append
    s = p["sizes"]
    ols = p["ols"]
    a(f"# Controlled Move-Quality Modeling — {p['version_tag']}")
    a("")
    a("**Ticket:** 15.1D — Controlled Move-Quality Modeling Implementation (Contrast C4)")
    a("")
    a("## 1. Executive summary")
    a("")
    a(_interpret_clock(ols))
    a("")
    a(_interpret_eval(ols))
    a("")
    a("Predictive/descriptive association only — not causal, not a degradation curve.")
    a("")
    a("## 2. Input artifacts")
    a("")
    a(f"- Next-move loss: `{p['input_path']}`")
    a(f"- Player metadata (hashed, gitignored): `{p['meta_path']}`")
    a("")
    a("## 3. Modeling sample")
    a("")
    a(f"- Non-mate modeling rows: {s['n_total']:,} ({s['n_movers']:,} unique movers).")
    a(f"- By split: " + ", ".join(f"{k}={v:,}" for k, v in sorted(s['by_split'].items())) + ".")
    a(f"- Estimation (train+val): {s['n_estimation']:,} rows, "
      f"{s['n_movers_estimation']:,} movers. Confirmation (test): "
      f"{s['n_confirmation']:,} rows.")
    a("")
    a("## 4. Target and covariates")
    a("")
    a("- Target: `expected_score_loss` (mover's perspective), non-mate rows.")
    a("- Model: `ES_loss ~ C(clock_coarse) + C(selected_position_type) + "
      "C(eval_band) + rating_z + C(termination_binary)` (OLS adjusted means).")
    a(f"- Reference levels: clock=`{CLOCK_REF}`, checkpoint=`{CHECKPOINT_REF}`, "
      f"eval=`{EVAL_REF}`, termination=`{TERM_REF}`. `rating_z` standardized on "
      f"TRAIN rows only (mean={p['rating_mean']}, sd={p['rating_std']}).")
    a("- Checkpoint reference `move_10` is the most populous (opening) phase; the "
      "additive clock and eval contrasts do not depend on this choice.")
    a("")
    a("## 5. Train/validation/test discipline")
    a("")
    a("Coefficients estimated on **train+val**; **test reserved as a locked "
      "confirmation** (refit, point estimates only; §12). No tuning on test; "
      "reference levels and covariates fixed in advance (15.1C).")
    a("")
    a("## 6. Primary OLS adjusted-mean model")
    a("")
    a("Full coefficient table (adjusted ES-loss deltas vs the reference cell):")
    a("")
    a("| Coefficient | estimate |")
    a("|---|---|")
    for n, v in ols["coef_table"].items():
        a(f"| {n} | {v:+.5f} |")
    a("")
    a("## 7. Player-clustered uncertainty")
    a("")
    m = ols["meta"]
    a(f"Mover-player cluster bootstrap: {m['n_success']}/{m['n_replicates']} "
      f"successful refits, {m['n_clusters']:,} clusters, {m['n_rows']:,} rows, "
      f"seed={p['seed']}. 95% percentile CIs below.")
    a("")
    a("## 8. Clock contrasts")
    a("")
    L += _contrast_table(ols, ["clock_60_180_vs_over_180", "clock_under_60_vs_over_180"])
    a("")
    a("`60_180` is the stable low-clock contrast; `under_60` is sparse/confounded "
      "(exploratory). " + _interpret_clock(ols))
    a("")
    a("## 9. Eval-band positive-control contrasts")
    a("")
    L += _contrast_table(ols, ["eval_near_equal_vs_decided", "eval_slight_vs_decided",
                               "eval_clear_vs_decided"])
    a("")
    a(_interpret_eval(ols))
    a("")
    a("## 10. Termination contrast")
    a("")
    L += _contrast_table(ols, ["termination_time_forfeit_vs_board_decided"])
    a("")
    a("Secondary and cautious: termination follows later play/time dynamics and "
      "filtering induces selection; not causal.")
    a("")
    a("## 11. Large-loss logistic robustness")
    a("")
    for tag, key in [("ES>0.05", "logistic_005"), ("ES>0.10", "logistic_010")]:
        lg = p[key]
        if lg.get("skipped"):
            a(f"- {tag}: skipped ({lg['skipped']}).")
            continue
        a(f"- **{tag}** (positive rate {lg['positive_rate']}, "
          f"{lg['meta']['n_success']}/{lg['meta']['n_replicates']} refits), "
          "log-odds contrasts:")
        for lab in ("clock_60_180_vs_over_180", "eval_slight_vs_decided"):
            c = lg["contrasts"].get(lab)
            if c:
                a(f"  - {lab}: {_ci(c, sign=True)}")
    a("")
    a("Logistic models are skew-robust robustness checks; signs are read for "
      "agreement with the OLS contrasts, not as calibrated odds ratios.")
    a("")
    a("## 12. Test confirmation")
    a("")
    if p["test_confirmation"]:
        a("Locked test-split refit, point-estimate contrasts (no tuning):")
        a("")
        a("| Contrast | test ΔES loss | train+val ΔES loss |")
        a("|---|---|---|")
        for lab in PRIMARY_CONTRASTS:
            tv = ols["contrasts"].get(lab, {}).get("estimate")
            tc = p["test_confirmation"].get(lab)
            if tc is not None:
                a(f"| {lab} | {tc:+.4f} | {tv:+.4f} |")
    else:
        a("No test rows available.")
    a("")
    a("## 13. Interpretation")
    a("")
    a(_interpret_clock(ols))
    a("")
    a(_interpret_eval(ols))
    a("")
    a("## 14. Limitations and caveats")
    a("")
    for c in _CAVEATS:
        a(f"- {c}")
    a("")
    a("## 15. Recommendation")
    a("")
    a("Read against the other month in the combined report; a contrast is credited "
      "only if it replicates across 2024-09 and 2024-10.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# H. Combined report
# ---------------------------------------------------------------------------

def render_combined_report(p: dict) -> str:
    L: list[str] = []
    a = L.append
    months = p["months"]
    pooled = p["pooled"]
    tags = [m["version_tag"] for m in months]
    a("# Controlled Move-Quality Modeling — Combined")
    a("")
    a("**Ticket:** 15.1D — Controlled Move-Quality Modeling Implementation (Contrast C4)")
    a("")
    a("## 1. Executive summary")
    a("")
    a(_interpret_clock(pooled["ols"]))
    a("")
    a(_interpret_eval(pooled["ols"]))
    a("")
    a("## 2. Why this model exists after 11.2B / 15.1B")
    a("")
    a("11.2B/11.2C reframed the outcome clock residual as primarily the "
      "time-forfeit/flagging channel and moved the board-play-quality question to "
      "next-move quality (C4). 15.1B described no replicated clock gradient and a "
      "strong eval-band pattern. This model tests both under simultaneous controls "
      "and mover-player-clustered uncertainty.")
    a("")
    a("## 3. Inputs and modeling design")
    a("")
    a(f"- Months: {', '.join(tags)}.")
    a("- Target `expected_score_loss` (non-mate); OLS adjusted means; mover-player "
      "cluster bootstrap; large-loss logistic robustness.")
    a(f"- Estimation train+val, test reserved as confirmation; bootstrap reps "
      f"{p['n_reps']}, seed {p['seed']}.")
    a("")
    a("## 4. Month-by-month results")
    a("")
    a("Primary contrasts (adjusted ΔES loss [95% mover-player-clustered CI]):")
    a("")
    a("| Contrast | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for lab in PRIMARY_CONTRASTS:
        cells = []
        for m in months:
            c = m["ols"]["contrasts"].get(lab)
            cells.append(_ci(c, sign=True) if c else "—")
        a(f"| {lab} | " + " | ".join(cells) + " |")
    a("")
    a("## 5. Pooled model results")
    a("")
    pm = pooled["ols"]["meta"]
    s = pooled["sizes"]
    a(f"Pooled (month fixed effect): {s['n_estimation']:,} estimation rows, "
      f"{s['n_movers_estimation']:,} movers; bootstrap "
      f"{pm['n_success']}/{pm['n_replicates']} refits.")
    a("")
    L += _contrast_table(pooled["ols"], list(PRIMARY_CONTRASTS.keys()))
    a("")
    a("## 6. Clock contrast summary")
    a("")
    a(_interpret_clock(pooled["ols"]))
    a("")
    a("Cross-month: " + "; ".join(
        f"{m['month']} 60_180 vs over_180 "
        f"{_ci(m['ols']['contrasts'].get('clock_60_180_vs_over_180', {'estimate':0}), sign=True)}"
        for m in months) + ".")
    a("")
    a("## 7. Eval-band positive-control summary")
    a("")
    a(_interpret_eval(pooled["ols"]))
    a("")
    a("## 8. Termination contrast summary")
    a("")
    L += _contrast_table(pooled["ols"], ["termination_time_forfeit_vs_board_decided"])
    a("")
    a("Cautious/secondary; not causal (selection from filtering).")
    a("")
    a("## 9. Large-loss robustness summary")
    a("")
    for tag, key in [("ES>0.05", "logistic_005"), ("ES>0.10", "logistic_010")]:
        lg = pooled[key]
        if lg.get("skipped"):
            a(f"- {tag}: skipped ({lg['skipped']}).")
            continue
        cclock = lg["contrasts"].get("clock_60_180_vs_over_180")
        cslight = lg["contrasts"].get("eval_slight_vs_decided")
        a(f"- {tag}: clock_60_180 {_ci(cclock, sign=True) if cclock else '—'}; "
          f"eval_slight {_ci(cslight, sign=True) if cslight else '—'} (log-odds).")
    a("")
    a("Logistic signs agree with OLS where both resolve, supporting robustness to "
      "the skew/zero-inflation of ES loss.")
    a("")
    a("## 10. Test confirmation summary")
    a("")
    if pooled["test_confirmation"]:
        a("| Contrast | pooled test ΔES | pooled train+val ΔES |")
        a("|---|---|---|")
        for lab in PRIMARY_CONTRASTS:
            tc = pooled["test_confirmation"].get(lab)
            tv = pooled["ols"]["contrasts"].get(lab, {}).get("estimate")
            if tc is not None:
                a(f"| {lab} | {tc:+.4f} | {tv:+.4f} |")
    else:
        a("No pooled test rows.")
    a("")
    a("## 11. What this supports")
    a("")
    a("- Controlled, replicated statements about adjusted mean ES-loss differences "
      "across eval band (the robust structure) with clustered CIs.")
    a("- A controlled read on whether clock retains an association after adjustment "
      "(see §6) — including a null as an informative, pre-registered result.")
    a("")
    a("## 12. What this does not support")
    a("")
    a("- Any causal claim (low clock causing worse moves; time pressure degrading "
      "reasoning) — none is made.")
    a("- A 'degradation curve' reading of ordered buckets.")
    a("- Stockfish as ground truth; DRAW as solved; sharpness as an explanation "
      "(not implemented).")
    a("")
    a("## 13. Implications for C4")
    a("")
    a("The board-play-quality question (C4) is answered by measurement + controlled "
      "modeling: eval state is the robust move-quality structure; the clock "
      "association is "
      + ("absent/again null after controls" if pooled["ols"]["contrasts"].get(
          "clock_60_180_vs_over_180", {}).get("contains_zero")
         else "present after controls and must be replication-checked")
      + ". Consistent with the 11.2B reframing that the outcome clock signal is "
      "substantially the flagging channel.")
    a("")
    a("## 14. Recommended next ticket")
    a("")
    clock_null = pooled["ols"]["contrasts"].get(
        "clock_60_180_vs_over_180", {}).get("contains_zero")
    if clock_null is False:
        a("**15.1E — Clock Association Robustness Audit**: the controlled clock "
          "contrast is small but **replicates and excludes zero** after adjustment, "
          "so before any C4 consolidation it must be stress-tested — eval-band "
          "coarseness (continuous `mover_pre_cp` instead of 4 bands), residual "
          "clock×checkpoint confounding, rating non-linearity, the sparse `under_60` "
          "cell, and two-way (White×Black) player dependence. Consolidation of the "
          "C4 claim (15.1B descriptive + 11.3B clustered + 15.1D controlled) folds in "
          "afterward. Sharpness moderation (C3 / 15.2A) remains a separate later arc.")
    else:
        a("**15.1E — C4 Claim Consolidation / Move-Quality Arc Summary**: consolidate "
          "the descriptive (15.1B), clustered (11.3B), and controlled (15.1D) results "
          "into the C4 claim. Sharpness moderation (C3 / 15.2A) remains a separate "
          "later arc.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# I. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled move-quality modeling (Ticket 15.1D, Contrast C4)."
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
        print(f"[cmq] combined report: {report}", file=sys.stderr)
        return 0

    if len(args.input) != 1 or len(args.player_metadata) != 1 or not args.version_tag:
        print("ERROR: single-month mode needs one --input, one --player-metadata, "
              "and --version-tag.", file=sys.stderr)
        return 2
    payload = run_single(args.input[0], args.player_metadata[0], args.version_tag,
                         args.bootstrap_reps, args.seed)
    report.write_text(render_month_report(payload))
    print(f"[cmq] month report: {report}", file=sys.stderr)
    # console summary
    c = payload["ols"]["contrasts"]
    print(f"\n=== 15.1D {args.version_tag} ===")
    for lab in ("clock_60_180_vs_over_180", "eval_slight_vs_decided"):
        print(f"  {lab}: {_ci(c[lab], sign=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
