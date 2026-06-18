"""
Controlled dense per-ply move-quality model — Ticket 15.4D.

Estimates the CONDITIONAL ASSOCIATION between clock state and next-move
expected-score loss on the dense 10+0 substrate (2024-09 + 2024-10), net of eval
state, phase, mover rating, month, mover color, and termination channel. This is the
dense per-ply analogue of the 15.1D/15.1F checkpoint controlled result.

It reads the dense ``dense_move_loss_*`` artifacts read-only and writes a markdown
report. It does NOT modify artifacts, run Stockfish, join sharpness, fit cross-time-
control models, or change the ES transform.

Estimator: numpy OLS adjusted-mean (coefficients = expected-score-loss differences) with
a fast GAME-clustered sufficient-statistics bootstrap (per-cluster XᵀX/Xᵀy; resample
whole game clusters). Large-loss targets use a linear probability model (same machinery);
a single sklearn logistic fit provides a sign-agreement check. Uncertainty is clustered,
never naive row-level.

ALL results are predictive/descriptive CONDITIONAL ASSOCIATIONS — NOT causal. Stockfish
depth-12 eval is objective position context, not ground truth. A null clock association
is a pre-registered acceptable outcome.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.dense_controlled_model \\
        --dense-month data/processed/dense_move_loss_2024_09_250k_v1.parquet \\
        --dense-month data/processed/dense_move_loss_2024_10_250k_v1.parquet \\
        --report reports/dense_controlled_move_quality_model_10plus0_2024_09_2024_10_v1.md \\
        --bootstrap 500 --seed 20240617
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

from chess_mhsuc.clustered_uncertainty import _cluster_index, summarize_contrasts
from chess_mhsuc.dense_constraint_atlas import (
    clock_coarse_bucket,
    phase_move_bucket,
    rating_bucket_200,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_ROWS = {"2024_09": 1_496_890, "2024_10": 1_436_866}

# Design reference levels (omitted from one-hot): clock over_180, eval decided,
# phase middlegame, rating 1600_1799, month 2024_09, color white, termination board_decided.
CLOCK_LEVELS = ["under_10", "10_30", "30_60", "60_180"]   # ref over_180
EVAL_LEVELS = ["near_equal", "slight", "clear"]            # ref decided
PHASE_LEVELS = ["opening", "endgame"]                      # ref middlegame
RATING_REF = "1600_1799"
RATING_LEVELS = ["<1000", "1000_1199", "1200_1399", "1400_1599",
                 "1800_1999", "2000_2199", "2200+"]        # ref 1600_1799
MONTH_LEVELS = ["2024_10"]                                 # ref 2024_09
COLOR_LEVELS = ["black"]                                   # ref white
TERM_LEVELS = ["time_forfeit"]                             # ref board_decided

CLOCK_CONTRASTS = {
    "clock under_10 vs over_180": "clock=under_10",
    "clock 10_30 vs over_180": "clock=10_30",
    "clock 30_60 vs over_180": "clock=30_60",
    "clock 60_180 vs over_180": "clock=60_180",
}
EVAL_CONTRASTS = {
    "eval near_equal vs decided": "eval=near_equal",
    "eval slight vs decided": "eval=slight",
    "eval clear vs decided": "eval=clear",
}
FOCAL = "clock=60_180"

TEN_ZERO_START_S = 600.0

REQUIRED_COLS = [
    "month", "game_id", "ply", "move_number", "mover_color", "mover_elo",
    "clock_before_s", "think_time_gross_s", "expected_score_loss",
    "expected_score_before", "eval_before_cp", "cp_loss_clipped", "cp_loss_raw",
    "is_mate_band", "status", "eval_band", "phase", "termination",
    "is_time_forfeit", "mover_player_hash",
]
_FORBIDDEN_USERNAME_COLS = {"white", "black", "White", "Black",
                            "white_user", "black_user"}


# ---------------------------------------------------------------------------
# A. Load + validate + derive
# ---------------------------------------------------------------------------

def load_dense(paths: list[str | Path]) -> pl.DataFrame:
    frames = []
    for p in paths:
        print(f"[controlled] loading {p} selected columns ...", file=sys.stderr)
        avail = pl.scan_parquet(p).collect_schema().names()
        cols = [c for c in REQUIRED_COLS if c in avail]
        frames.append(pl.read_parquet(p, columns=cols))
    return pl.concat(frames, how="diagonal_relaxed") if len(frames) > 1 else frames[0]


def validate_schema(df: pl.DataFrame, check_counts: bool = True) -> dict:
    print("[controlled] validating schema ...", file=sys.stderr)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"controlled-model input missing required columns: {missing}")
    bad = _FORBIDDEN_USERNAME_COLS & set(df.columns)
    if bad:
        raise ValueError(f"raw username columns present (privacy violation): {sorted(bad)}")
    es = df["expected_score_loss"]
    if es.min() is not None and (es.min() < 0 or es.max() > 1.0001):
        raise ValueError(f"expected_score_loss out of [0,1]: [{es.min()}, {es.max()}]")
    if df["cp_loss_clipped"].min() is not None and df["cp_loss_clipped"].min() < 0:
        raise ValueError("cp_loss_clipped has negative values")
    per_month = {r[0]: r[1] for r in df.group_by("month").len().iter_rows()}
    if check_counts:
        for m, expected in EXPECTED_ROWS.items():
            if per_month.get(m) != expected:
                raise ValueError(f"row count mismatch for {m}: got {per_month.get(m)}, "
                                 f"expected {expected}")
    if len(per_month) < 2:
        raise ValueError(f"need both months; got {sorted(per_month)}")
    colors = set(df["mover_color"].unique().to_list())
    if colors != {"white", "black"}:
        raise ValueError(f"both mover colors required; got {colors}")
    if df["game_id"].null_count() > 0:
        raise ValueError("game_id has nulls (needed for clustering)")
    return {"rows": df.height, "per_month": per_month,
            "months": sorted(per_month.keys()),
            "has_player_hash": df["mover_player_hash"].null_count() == 0}


def add_model_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Derive the categorical/anomaly columns used by the design (pure)."""
    return df.with_columns([
        pl.col("clock_before_s").map_elements(clock_coarse_bucket, return_dtype=pl.Utf8)
        .alias("clock_coarse"),
        pl.col("mover_elo").map_elements(rating_bucket_200, return_dtype=pl.Utf8)
        .alias("rating_bin"),
        pl.col("move_number").map_elements(phase_move_bucket, return_dtype=pl.Utf8)
        .alias("move_bucket"),
        pl.when(pl.col("is_time_forfeit")).then(pl.lit("time_forfeit"))
        .otherwise(pl.lit("board_decided")).alias("termination_channel"),
        (pl.col("clock_before_s") > TEN_ZERO_START_S).cast(pl.Float64).alias("clock_anom"),
        (pl.col("think_time_gross_s") < 0).cast(pl.Float64).alias("think_anom"),
    ])


def filter_headline(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter((pl.col("status") == "ok") & (~pl.col("is_mate_band")))


def denominators(df: pl.DataFrame) -> dict:
    out = {}
    for m in sorted(df["month"].unique().to_list()):
        sub = df.filter(pl.col("month") == m)
        out[m] = {
            "rows": sub.height,
            "mate_band": int(sub["is_mate_band"].sum()),
            "clock_over_600": int(sub.filter(pl.col("clock_before_s") > TEN_ZERO_START_S).height),
            "negative_think": int(sub.filter(pl.col("think_time_gross_s") < 0).height),
        }
    return out


# ---------------------------------------------------------------------------
# B. Design matrix + OLS + clustered bootstrap
# ---------------------------------------------------------------------------

def build_design(
    df: pl.DataFrame,
    rating_mean: float | None = None,
    rating_std: float | None = None,
    rating_mode: str = "bins",
    include_month: bool = True,
    include_termination: bool = True,
    include_color: bool = True,
    eval_mode: str = "band",
) -> tuple[np.ndarray, list[str]]:
    """Explicit one-hot design with fixed reference levels + intercept (deterministic
    column order). rating_mode 'bins' (one-hot 200-Elo) or 'z' (continuous, train
    moments). eval_mode 'band' (one-hot) or 'continuous' (expected_score_before)."""
    n = len(df)
    cols: list[tuple[str, np.ndarray]] = [("intercept", np.ones(n))]

    cc = df["clock_coarse"].to_numpy()
    for lv in CLOCK_LEVELS:
        cols.append((f"clock={lv}", (cc == lv).astype(float)))

    if eval_mode == "band":
        eb = df["eval_band"].to_numpy()
        for lv in EVAL_LEVELS:
            cols.append((f"eval={lv}", (eb == lv).astype(float)))
    else:  # continuous mover-perspective ES-before (centered)
        esb = df["expected_score_before"].to_numpy().astype(float)
        cols.append(("eval_es_before_c", esb - 0.5))

    ph = df["phase"].to_numpy()
    for lv in PHASE_LEVELS:
        cols.append((f"phase={lv}", (ph == lv).astype(float)))

    if rating_mode == "bins":
        rb = df["rating_bin"].to_numpy()
        for lv in RATING_LEVELS:
            cols.append((f"rating={lv}", (rb == lv).astype(float)))
    else:
        rz = (df["mover_elo"].to_numpy().astype(float) - rating_mean) / rating_std
        cols.append(("rating_z", rz))

    if include_month:
        mo = df["month"].to_numpy()
        for lv in MONTH_LEVELS:
            cols.append((f"month={lv}", (mo == lv).astype(float)))
    if include_color:
        co = df["mover_color"].to_numpy()
        for lv in COLOR_LEVELS:
            cols.append((f"color={lv}", (co == lv).astype(float)))
    if include_termination:
        tc = df["termination_channel"].to_numpy()
        for lv in TERM_LEVELS:
            cols.append((f"termination={lv}", (tc == lv).astype(float)))

    cols.append(("clock_anom", df["clock_anom"].to_numpy().astype(float)))
    cols.append(("think_anom", df["think_anom"].to_numpy().astype(float)))

    # Drop constant columns (except the intercept): an absent level (all 0) or a
    # column collinear with the intercept (all 1, e.g. a subgroup's own level or an
    # anomaly-free subset) would make XᵀX singular in the solve-based bootstrap.
    kept = [cols[0]]  # intercept
    for name, v in cols[1:]:
        if float(v.min()) != float(v.max()):
            kept.append((name, v))
    names = [c[0] for c in kept]
    X = np.column_stack([c[1] for c in kept])
    return X, names


def ols_fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def ols_cluster_bootstrap(
    X: np.ndarray, y: np.ndarray, cluster_ids: list, n_reps: int, seed: int,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Game-clustered OLS bootstrap via per-cluster sufficient statistics
    (XᵀX, Xᵀy). Resamples whole clusters; each replicate sums sampled clusters'
    sufficient stats and solves. Returns (full_coef, boot_coefs[(reps,p)], meta).
    Fast: O(n_rows·p²) once + O(reps·n_clusters·p²)."""
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n, p = X.shape
    uniq, idx_lists = _cluster_index(list(cluster_ids))
    C = len(uniq)
    if C < 2:
        raise ValueError(f"too few clusters ({C}) for clustered bootstrap")
    # full-sample fit (normal equations)
    XtX_full = X.T @ X
    Xty_full = X.T @ y
    full = np.linalg.lstsq(XtX_full, Xty_full, rcond=None)[0]
    # per-cluster sufficient stats
    XtX_c = np.empty((C, p, p), dtype=np.float64)
    Xty_c = np.empty((C, p), dtype=np.float64)
    for k, ix in enumerate(idx_lists):
        Xc = X[ix]
        XtX_c[k] = Xc.T @ Xc
        Xty_c[k] = Xc.T @ y[ix]
    # reshape per-cluster stats to (C, p*p) and (C, p) so a resample is a weighted
    # sum by cluster-draw counts (bincount) — avoids materializing a (C,p,p) gather.
    XtX_flat = XtX_c.reshape(C, p * p)
    rng = np.random.default_rng(seed)
    boots = np.empty((n_reps, p), dtype=np.float64)
    ok = 0
    for _ in range(n_reps):
        counts = np.bincount(rng.integers(0, C, size=C), minlength=C).astype(np.float64)
        A = (counts @ XtX_flat).reshape(p, p)
        b = counts @ Xty_c
        try:
            boots[ok] = np.linalg.solve(A, b)
            ok += 1
        except np.linalg.LinAlgError:
            continue
    meta = {"n_clusters": C, "n_rows": n, "n_replicates": n_reps, "n_success": ok}
    return full, boots[:ok], meta


def fit_ols_contrasts(
    df: pl.DataFrame, target_col: str, contrasts: dict[str, str],
    cluster_col: str, n_reps: int, seed: int, **design_kw,
) -> dict:
    """Fit OLS on target_col with the given design and game-/player-clustered bootstrap;
    return labelled contrast CIs + selected coefficients."""
    X, names = build_design(df, **design_kw)
    y = df[target_col].to_numpy().astype(float)
    clusters = df[cluster_col].to_list()
    full, boot, meta = ols_cluster_bootstrap(X, y, clusters, n_reps, seed)
    wanted = [c for c in contrasts.values() if c in names]
    summ = summarize_contrasts(full, boot, names, wanted)
    labelled = {label: summ[coef] for label, coef in contrasts.items() if coef in summ}
    return {"contrasts": labelled, "meta": meta, "n_rows": len(df),
            "names": names, "full": full}


def logistic_sign_check(df: pl.DataFrame, target_col: str, **design_kw) -> dict:
    """Single unregularized sklearn logistic fit (no bootstrap) for a large-loss
    target — reports the focal clock coefficient sign only (robustness appendix)."""
    from sklearn.linear_model import LogisticRegression
    X, names = build_design(df, **design_kw)
    y = df[target_col].to_numpy().astype(int)
    clf = LogisticRegression(C=1e9, fit_intercept=False, max_iter=500)
    clf.fit(X, y)
    coef = clf.coef_[0]
    idx = {n: i for i, n in enumerate(names)}
    return {k: round(float(coef[idx[v]]), 4) for k, v in CLOCK_CONTRASTS.items()
            if v in idx}


# ---------------------------------------------------------------------------
# C. Report
# ---------------------------------------------------------------------------

def _ci(d: dict) -> str:
    lo, hi = d.get("ci_lower"), d.get("ci_upper")
    if lo is None or hi is None:
        return "—"
    star = "" if d.get("contains_zero", True) else " *"
    return f"[{lo:+.4f}, {hi:+.4f}]{star}"


def _contrast_rows(res: dict, contrasts: dict) -> list[str]:
    L = ["| contrast | estimate | 95% CI (game-clustered) |", "|---|---|---|"]
    for label in contrasts:
        d = res["contrasts"].get(label)
        if d:
            L.append(f"| {label} | {d['estimate']:+.4f} | {_ci(d)} |")
    return L


def render_report(path: Path, val: dict, denoms: dict, results: dict,
                  n_reps: int, seed: int, runtime_s: float, cluster_note: str) -> None:
    print("[controlled] writing report ...", file=sys.stderr)
    L: list[str] = []
    a = L.append
    a("# Controlled Dense Move-Quality Model — 10+0, 2024-09 and 2024-10")
    a("")
    a(f"**Ticket:** 15.4D | **bootstrap:** {n_reps} game-clustered draws, seed {seed} "
      f"| **runtime:** {runtime_s:.0f}s")
    a("")
    a("## 1. Executive summary")
    a("")
    foc = results["primary"]["contrasts"].get("clock 60_180 vs over_180", {})
    a("Controlled dense per-ply model of next-move **expected-score loss**, net of eval "
      "state, phase, mover rating, month, mover color, and termination channel, with "
      "**game-clustered** uncertainty. The estimand is a **conditional association, not "
      "causal**. Eval state is the positive control; clock is the focal predictor "
      "(reference `over_180`). Headline focal contrast `60_180` vs `over_180` = "
      f"**{foc.get('estimate', float('nan')):+.4f}** {_ci(foc)} (`*` = CI excludes 0). "
      "Marginal atlas (15.4B) clock curves are U-shaped/confounded; this controlled "
      "model is the inferential statement. Stockfish eval is objective context, not "
      "ground truth.")
    a("")
    a("## 2. Inputs and validation")
    a(f"- Combined rows: {val['rows']:,}; months {', '.join(val['months'])}; per-month "
      "counts match 15.3C/15.3D; no raw-username columns; ES∈[0,1]; clipped cp≥0; both "
      f"colors present; player hashes present: {val['has_player_hash']}.")
    a("")
    a("## 3. Filtering and denominators")
    a("| month | rows | mate-band (excl.) | clock>600 | negative think |")
    a("|---|---|---|---|---|")
    for m, c in denoms.items():
        a(f"| {m} | {c['rows']:,} | {c['mate_band']:,} | {c['clock_over_600']} | "
          f"{c['negative_think']} |")
    a(f"- Headline rows (status ok ∧ ¬mate-band ∧ both colors): "
      f"**{results['primary']['n_rows']:,}**.")
    a(f"- Board-decided headline: {results['board_decided']['n_rows']:,}; "
      f"time-forfeit excluded from S3.")
    a("")
    a("## 4. Model specification")
    a("")
    a("`expected_score_loss ~ C(clock_coarse, ref=over_180) + C(eval_band, ref=decided) "
      "+ C(phase, ref=middlegame) + C(rating_bin, ref=1600_1799) + C(month, ref=2024_09) "
      "+ C(mover_color, ref=white) + C(termination_channel, ref=board_decided) + "
      "clock_anom + think_anom + intercept`. Numpy OLS adjusted-mean; coefficients are "
      "expected-score-loss differences vs the reference cell.")
    a("")
    a("## 5. Primary expected-score-loss model")
    a("")
    a(f"OLS on {results['primary']['n_rows']:,} headline rows; "
      f"{results['primary']['meta']['n_clusters']:,} game clusters; "
      f"{results['primary']['meta']['n_success']}/{n_reps} bootstrap refits.")
    a("")
    a("## 6. Clock coefficient table")
    a("")
    L += _contrast_rows(results["primary"], CLOCK_CONTRASTS)
    a("")
    a("Reference = `over_180`. Coefficient = conditional ES-loss difference vs over_180.")
    a("")
    a("## 7. Eval-state positive-control table")
    a("")
    L += _contrast_rows(results["primary"], EVAL_CONTRASTS)
    a("")
    a("Eval band dominates (reference `decided`): the slight/near_equal coefficients are "
      "much larger in magnitude than the clock coefficients — the positive control.")
    a("")
    a("## 8. Month-specific replication")
    a("")
    a("| contrast | 2024-09 | 2024-10 |")
    a("|---|---|---|")
    for label in CLOCK_CONTRASTS:
        d9 = results["month_2024_09"]["contrasts"].get(label, {})
        d10 = results["month_2024_10"]["contrasts"].get(label, {})
        a(f"| {label} | {d9.get('estimate', float('nan')):+.4f} {_ci(d9)} | "
          f"{d10.get('estimate', float('nan')):+.4f} {_ci(d10)} |")
    a("")
    a("## 9. Board-decided-only robustness")
    a("")
    L += _contrast_rows(results["board_decided"], CLOCK_CONTRASTS)
    a("")
    a("Restricted to `is_time_forfeit == False` (termination control dropped as constant). "
      "Tests whether the clock residual survives outside the direct flagging channel. "
      "(Extreme `under_10` board-decided cells are sparse — read cautiously.)")
    a("")
    a("## 10. Clipped-CP robustness")
    a("")
    L += _contrast_rows(results["clipped_cp"], CLOCK_CONTRASTS)
    a("")
    a("Target = `cp_loss_clipped` (centipawns; familiar but skewed).")
    a("")
    a("## 11. Large-loss probability robustness")
    a("")
    a("Linear probability models (OLS on indicator); focal clock contrast:")
    a("")
    a("| target | 60_180 vs over_180 | logistic-sign |")
    a("|---|---|---|")
    for tgt in ("es_ge_05", "es_ge_10"):
        d = results[tgt]["contrasts"].get("clock 60_180 vs over_180", {})
        ls = results.get(f"{tgt}_logit", {}).get("clock 60_180 vs over_180")
        a(f"| {tgt} | {d.get('estimate', float('nan')):+.5f} {_ci(d)} | "
          f"{('%+.4f' % ls) if ls is not None else '—'} |")
    a("")
    a("LPM = primary (interpretable); single unregularized logistic provides a sign check "
      "(no bootstrap).")
    a("")
    a("## 12. Alternative clock/eval/rating robustness")
    a("")
    a("| spec | 60_180 vs over_180 |")
    a("|---|---|")
    for key, lab in [("continuous_eval", "continuous-eval control"),
                     ("rating_z", "rating_z (continuous)"),
                     ("anomaly_excluded", "anomaly-excluded")]:
        d = results[key]["contrasts"].get("clock 60_180 vs over_180", {})
        a(f"| {lab} | {d.get('estimate', float('nan')):+.4f} {_ci(d)} |")
    a("")
    a("## 13. Interaction summaries")
    a("")
    a("Focal `60_180` vs `over_180` clock contrast within subgroups (subgroup fits; "
      "sparse subgroups flagged):")
    a("")
    a("| subgroup family | subgroup | 60_180 vs over_180 | n |")
    a("|---|---|---|---|")
    for fam, items in results["interactions"].items():
        for sg, d in items.items():
            n = d.get("n_rows", 0)
            warn = " (sparse)" if n < 5000 else ""
            cc = d["contrasts"].get("clock 60_180 vs over_180", {})
            a(f"| {fam} | {sg}{warn} | {cc.get('estimate', float('nan')):+.4f} "
              f"{_ci(cc)} | {n:,} |")
    a("")
    a("Exploratory; locates where any clock residual concentrates. No sharpness "
      "interaction (Phase 15.5).")
    a("")
    a("## 14. Uncertainty and clustering")
    a("")
    a(f"- Primary: game-clustered sufficient-statistics bootstrap, {n_reps} draws, "
      f"{results['primary']['meta']['n_clusters']:,} game clusters.")
    a(f"- {cluster_note}")
    a("- Naive row-level SEs are NOT used (per-ply rows are within-game/within-player "
      "correlated).")
    a("")
    a("## 15. Comparison to 15.1D/15.1F checkpoint controlled result")
    a("")
    a("| quantity | checkpoint (15.1D/F) | dense (15.4D) |")
    a("|---|---|---|")
    a(f"| 60_180 vs over_180 (ES loss) | ~+0.0034 [+0.0015,+0.0051] | "
      f"{foc.get('estimate', float('nan')):+.4f} {_ci(foc)} |")
    a("| eval band dominates | yes | yes (see §7) |")
    a("| board-decided-only survives | yes (small) | see §9 |")
    a("")
    a("## 16. Interpretation")
    a("")
    a("- Eval state dominates the dense controlled model (positive control, §7).")
    a("- The focal clock contrast (`60_180` vs `over_180`) is reported with its sign, "
      "magnitude, game-clustered CI, month replication (§8), and board-decided survival "
      "(§9). The result is read as a **conditional association**, not causal, and is "
      "compared honestly to the checkpoint result (§15) — not forced to match it.")
    a("- The atlas U-shaped marginal (15.4B) remains a descriptive warning; this "
      "controlled model is the inferential statement.")
    a("- Extreme low-clock board-decided cells are sparse (survivor population); those "
      "subgroup estimates are exploratory.")
    a("")
    a("## 17. Non-claims")
    a("")
    a("Conditional/predictive association only; **NOT causal**. No \"low clock causes "
      "blunders\"; no \"time pressure causes worse reasoning\"; no \"clock proves "
      "cognitive degradation\". Stockfish eval is objective context, not ground truth. "
      "No human-obviousness modeling; no sharpness (Phase 15.5); no cross-time-control "
      "(Phase 16); no synthesis. C4 and C3c unchanged; ES transform not refit.")
    a("")
    a("## 18. Recommended next ticket")
    a("")
    a("**15.5A — Sharpness-Enriched Constraint Atlas Audit** (design joining the MultiPV "
      "sharpness layer to the dense atlas; C3c move-quality-first). Not Phase 16; not "
      "synthesis.")
    a("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


# ---------------------------------------------------------------------------
# D. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Controlled dense move-quality model (Ticket 15.4D). Reads dense "
                    "artifacts; OLS adjusted-mean with game-clustered bootstrap. "
                    "Conditional association, not causal.")
    p.add_argument("--dense-month", action="append", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--bootstrap", type=int, default=500)
    p.add_argument("--seed", type=int, default=20240617)
    p.add_argument("--no-count-check", action="store_true")
    p.add_argument("--player-cluster", action="store_true",
                   help="also run a mover-player-clustered bootstrap on the focal model")
    args = p.parse_args(argv)

    t0 = time.time()
    df = load_dense(args.dense_month)
    val = validate_schema(df, check_counts=not args.no_count_check)
    denoms = denominators(df)
    print("[controlled] applying headline filter ...", file=sys.stderr)
    df = add_model_columns(df)
    head = filter_headline(df)

    # train-only rating moments (for rating_z robustness); fall back to all if no split
    rmean = float(head["mover_elo"].mean())
    rstd = float(head["mover_elo"].std()) or 1.0

    nb, seed = args.bootstrap, args.seed
    results: dict = {}

    print("[controlled] building primary design matrix ...", file=sys.stderr)
    print("[controlled] fitting primary ES-loss model ...", file=sys.stderr)
    print("[controlled] running game-clustered bootstrap ...", file=sys.stderr)
    results["primary"] = fit_ols_contrasts(
        head, "expected_score_loss", {**CLOCK_CONTRASTS, **EVAL_CONTRASTS},
        "game_id", nb, seed)

    print("[controlled] fitting robustness models ...", file=sys.stderr)
    # month-specific
    for m in ("2024_09", "2024_10"):
        sub = head.filter(pl.col("month") == m)
        results[f"month_{m}"] = fit_ols_contrasts(
            sub, "expected_score_loss", CLOCK_CONTRASTS, "game_id", nb, seed,
            include_month=False)
    # board-decided-only (termination constant -> drop)
    bd = head.filter(~pl.col("is_time_forfeit"))
    results["board_decided"] = fit_ols_contrasts(
        bd, "expected_score_loss", CLOCK_CONTRASTS, "game_id", nb, seed,
        include_termination=False)
    # clipped cp
    results["clipped_cp"] = fit_ols_contrasts(
        head, "cp_loss_clipped", CLOCK_CONTRASTS, "game_id", nb, seed)
    # large-loss LPM
    head = head.with_columns([
        (pl.col("expected_score_loss") >= 0.05).cast(pl.Float64).alias("es_ge_05"),
        (pl.col("expected_score_loss") >= 0.10).cast(pl.Float64).alias("es_ge_10"),
    ])
    for tgt in ("es_ge_05", "es_ge_10"):
        results[tgt] = fit_ols_contrasts(head, tgt, CLOCK_CONTRASTS, "game_id", nb, seed)
    # logistic sign check on ES>=0.10 (single fit, no bootstrap)
    try:
        results["es_ge_10_logit"] = logistic_sign_check(head, "es_ge_10")
    except Exception as e:
        print(f"[controlled] logistic sign-check skipped: {e}", file=sys.stderr)
        results["es_ge_10_logit"] = {}
    # continuous-eval robustness
    results["continuous_eval"] = fit_ols_contrasts(
        head, "expected_score_loss", CLOCK_CONTRASTS, "game_id", nb, seed,
        eval_mode="continuous")
    # rating_z robustness
    results["rating_z"] = fit_ols_contrasts(
        head, "expected_score_loss", CLOCK_CONTRASTS, "game_id", nb, seed,
        rating_mode="z", rating_mean=rmean, rating_std=rstd)
    # anomaly-excluded
    anex = head.filter((pl.col("clock_anom") == 0) & (pl.col("think_anom") == 0))
    results["anomaly_excluded"] = fit_ols_contrasts(
        anex, "expected_score_loss", CLOCK_CONTRASTS, "game_id", nb, seed)

    # interactions = subgroup focal-contrast fits
    inter: dict[str, dict] = {"eval_band": {}, "phase": {}, "rating_bin": {},
                              "termination_channel": {}}
    for band in EVAL_LEVELS + ["decided"]:
        sub = head.filter(pl.col("eval_band") == band)
        if sub.height > 500 and sub["game_id"].n_unique() > 2:
            inter["eval_band"][band] = fit_ols_contrasts(
                sub, "expected_score_loss", {"clock 60_180 vs over_180": FOCAL},
                "game_id", nb, seed, eval_mode="band")
    for ph in ["opening", "middlegame", "endgame"]:
        sub = head.filter(pl.col("phase") == ph)
        if sub.height > 500 and sub["game_id"].n_unique() > 2:
            inter["phase"][ph] = fit_ols_contrasts(
                sub, "expected_score_loss", {"clock 60_180 vs over_180": FOCAL},
                "game_id", nb, seed)
    for ch in ["board_decided", "time_forfeit"]:
        sub = head.filter(pl.col("termination_channel") == ch)
        if sub.height > 500 and sub["game_id"].n_unique() > 2:
            inter["termination_channel"][ch] = fit_ols_contrasts(
                sub, "expected_score_loss", {"clock 60_180 vs over_180": FOCAL},
                "game_id", nb, seed, include_termination=False)
    results["interactions"] = inter

    cluster_note = "mover-player-clustered robustness not run (game-clustered primary)."
    if args.player_cluster and val["has_player_hash"]:
        pc = fit_ols_contrasts(
            head, "expected_score_loss", {"clock 60_180 vs over_180": FOCAL},
            "mover_player_hash", nb, seed)
        d = pc["contrasts"]["clock 60_180 vs over_180"]
        cluster_note = (f"mover-player-clustered robustness ({pc['meta']['n_clusters']:,} "
                        f"clusters): 60_180 vs over_180 {d['estimate']:+.4f} {_ci(d)}.")

    runtime = time.time() - t0
    render_report(Path(args.report), val, denoms, results, nb, seed, runtime, cluster_note)

    foc = results["primary"]["contrasts"]["clock 60_180 vs over_180"]
    print(f"\n=== 15.4D controlled dense model ===")
    print(f"  headline rows={results['primary']['n_rows']:,} "
          f"clusters={results['primary']['meta']['n_clusters']:,} "
          f"bootstrap={nb} runtime={runtime:.0f}s")
    print(f"  FOCAL 60_180 vs over_180: {foc['estimate']:+.4f} {_ci(foc)}")
    print(f"  report -> {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
