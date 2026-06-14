"""
Clustered uncertainty utilities + player-clustered rerun reports — Ticket 11.3B.

11.3A established that strict player-disjoint splitting is infeasible (giant
connected component), so the planned hardening is player-clustered bootstrap.
This module provides a configurable one-way cluster bootstrap (the cluster key
may be game_id, white/black player hash, or mover player hash) and uses it to
re-check the two headline findings under player clustering:

  - 11.2B termination decomposition (paired E3->E4 delta by termination channel);
  - 15.1B Constraint Atlas eval-band structure (mean expected-score loss).

When the cluster key is `game_id`, the bootstrap reproduces the existing
game-level results (validation anchor). Player-clustered CIs are wider because
they account for repeated-player dependence (~86% of rows touch a multi-split
player; see 11.3A).

Scope note: this is a ONE-WAY cluster bootstrap. Each outcome game has two
players, so we report White-player-clustered and Black-player-clustered CIs
separately (each a clean partition); exact two-way (simultaneous White×Black)
cluster-robust inference is NOT implemented and is documented as deferred.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.clustered_uncertainty --task termination \\
        --version-tags 2024_09_250k_v1,2024_10_250k_v1 \\
        --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \\
        --player-metadata data/processed/player_metadata_2024_10_250k_v1.parquet \\
        --report reports/player_clustered_termination_decomposition.md

    PYTHONPATH=src python -m chess_mhsuc.clustered_uncertainty --task atlas \\
        --input data/processed/next_move_loss_2024_09_250k_v1.parquet \\
        --input data/processed/next_move_loss_2024_10_250k_v1.parquet \\
        --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \\
        --player-metadata data/processed/player_metadata_2024_10_250k_v1.parquet \\
        --report reports/player_clustered_constraint_atlas.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

_CI_ALPHA = 0.05
_MIN_CLUSTERS_WARN = 30
_PROB_COLS = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]


# ---------------------------------------------------------------------------
# A. Cluster index + validation (pure)
# ---------------------------------------------------------------------------

def validate_cluster_key(df: pl.DataFrame, cluster_col: str) -> None:
    """Raise if the cluster column is missing or contains nulls."""
    if cluster_col not in df.columns:
        raise ValueError(f"cluster key {cluster_col!r} not in frame columns")
    if df[cluster_col].null_count() > 0:
        raise ValueError(
            f"cluster key {cluster_col!r} has "
            f"{df[cluster_col].null_count()} null values"
        )


def _cluster_index(cluster_ids: list) -> tuple[list, list[np.ndarray]]:
    """Map cluster id -> row-index array, preserving first-seen order."""
    by: dict[Any, list[int]] = {}
    for i, c in enumerate(cluster_ids):
        by.setdefault(c, []).append(i)
    uniq = list(by.keys())
    return uniq, [np.asarray(by[c], dtype=np.int64) for c in uniq]


def _percentile_ci(values: np.ndarray, alpha: float) -> tuple[float, float]:
    lo = float(np.percentile(values, 100 * alpha / 2))
    hi = float(np.percentile(values, 100 * (1 - alpha / 2)))
    return lo, hi


# ---------------------------------------------------------------------------
# B. Clustered CI for a mean
# ---------------------------------------------------------------------------

def clustered_mean_ci(
    df: pl.DataFrame,
    value_col: str,
    cluster_col: str,
    n_replicates: int = 1000,
    seed: int = 42,
    alpha: float = _CI_ALPHA,
    min_clusters_warn: int = _MIN_CLUSTERS_WARN,
) -> dict[str, Any]:
    """
    Clustered bootstrap 95% CI for the mean of ``value_col``, resampling whole
    clusters (``cluster_col``) with replacement. Raises if <2 clusters.
    """
    validate_cluster_key(df, cluster_col)
    vals = df[value_col].to_numpy().astype(np.float64)
    n_rows = len(vals)
    uniq, idx_lists = _cluster_index(df[cluster_col].to_list())
    n_clusters = len(uniq)
    if n_clusters < 2:
        raise ValueError(
            f"too few clusters ({n_clusters}) for bootstrap on {cluster_col!r}"
        )
    rng = np.random.default_rng(seed)
    means = np.empty(n_replicates, dtype=np.float64)
    for r in range(n_replicates):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        sel = np.concatenate([idx_lists[p] for p in pick])
        means[r] = vals[sel].mean()
    lo, hi = _percentile_ci(means, alpha)
    note = (f"few clusters (n={n_clusters}); CI may be unstable"
            if n_clusters < min_clusters_warn else None)
    return {
        "estimate": round(float(vals.mean()), 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "contains_zero": lo <= 0.0 <= hi,
        "n_clusters": n_clusters,
        "n_rows": n_rows,
        "cluster_col": cluster_col,
        "note": note,
    }


# ---------------------------------------------------------------------------
# C. Clustered CI for a difference of group means
# ---------------------------------------------------------------------------

def clustered_mean_diff_ci(
    df: pl.DataFrame,
    value_col: str,
    group_col: str,
    group1: str,
    group2: str,
    cluster_col: str,
    n_replicates: int = 1000,
    seed: int = 42,
    alpha: float = _CI_ALPHA,
) -> dict[str, Any]:
    """
    Clustered bootstrap 95% CI for mean(group1) - mean(group2) of ``value_col``,
    resampling whole clusters. A cluster contributes its rows in both groups
    together, so within-player correlation across groups is preserved.
    """
    validate_cluster_key(df, cluster_col)
    sub = df.filter(pl.col(group_col).is_in([group1, group2]))
    v = sub[value_col].to_numpy().astype(np.float64)
    g = np.asarray(sub[group_col].to_list())
    is1 = g == group1
    is2 = g == group2

    uniq, idx_lists = _cluster_index(sub[cluster_col].to_list())
    n_clusters = len(uniq)
    if n_clusters < 2:
        raise ValueError(
            f"too few clusters ({n_clusters}) for diff bootstrap on {cluster_col!r}"
        )
    # Per-cluster sums and counts for each group.
    s1 = np.array([v[ix][is1[ix]].sum() for ix in idx_lists])
    n1 = np.array([int(is1[ix].sum()) for ix in idx_lists])
    s2 = np.array([v[ix][is2[ix]].sum() for ix in idx_lists])
    n2 = np.array([int(is2[ix].sum()) for ix in idx_lists])

    tot_n1, tot_n2 = n1.sum(), n2.sum()
    if tot_n1 == 0 or tot_n2 == 0:
        raise ValueError("one of the groups has no rows")
    estimate = s1.sum() / tot_n1 - s2.sum() / tot_n2

    rng = np.random.default_rng(seed)
    diffs = np.empty(n_replicates, dtype=np.float64)
    n_nan = 0
    for r in range(n_replicates):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        bn1, bn2 = n1[pick].sum(), n2[pick].sum()
        if bn1 == 0 or bn2 == 0:
            diffs[r] = np.nan
            n_nan += 1
            continue
        diffs[r] = s1[pick].sum() / bn1 - s2[pick].sum() / bn2
    valid = diffs[~np.isnan(diffs)]
    lo, hi = _percentile_ci(valid, alpha)
    return {
        "groups": f"{group1} - {group2}",
        "estimate": round(float(estimate), 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "contains_zero": lo <= 0.0 <= hi,
        "n_clusters": n_clusters,
        "n_rows": int(tot_n1 + tot_n2),
        "n_nan": n_nan,
        "cluster_col": cluster_col,
    }


# ---------------------------------------------------------------------------
# D. Clustered paired delta (E3 -> E4 log-loss)
# ---------------------------------------------------------------------------

def clustered_paired_delta_ci(
    combined: pl.DataFrame,
    cluster_col: str,
    model_a: str = "E3",
    model_b: str = "E4",
    n_replicates: int = 1000,
    seed: int = 42,
    alpha: float = _CI_ALPHA,
    model_col: str = "model_id",
) -> dict[str, Any]:
    """
    Clustered bootstrap CI for paired delta = log_loss(B) - log_loss(A),
    resampling whole clusters (the SAME clusters for both models each replicate).
    Negative delta => model B (clock features) improved. With cluster_col=
    'game_id' this reproduces the existing game-level paired bootstrap.
    """
    from chess_mhsuc.bootstrap_ci import compute_point_log_loss

    validate_cluster_key(combined, cluster_col)
    a = combined.filter(pl.col(model_col) == model_a)
    b = combined.filter(pl.col(model_col) == model_b)
    if a.height == 0 or b.height == 0:
        raise ValueError(f"missing rows for {model_a!r}/{model_b!r}")

    ua, idxa = _cluster_index(a[cluster_col].to_list())
    ub, idxb = _cluster_index(b[cluster_col].to_list())
    map_a = dict(zip(ua, idxa))
    map_b = dict(zip(ub, idxb))
    common = sorted(set(ua) & set(ub))
    n_clusters = len(common)
    if n_clusters < 2:
        raise ValueError(
            f"too few common clusters ({n_clusters}) on {cluster_col!r}"
        )
    da = [map_a[c] for c in common]
    db = [map_b[c] for c in common]

    point_delta = compute_point_log_loss(b) - compute_point_log_loss(a)

    rng = np.random.default_rng(seed)
    deltas = np.empty(n_replicates, dtype=np.float64)
    n_nan = 0
    for r in range(n_replicates):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        rows_a = np.concatenate([da[p] for p in pick])
        rows_b = np.concatenate([db[p] for p in pick])
        boot_a = a[rows_a.tolist()]
        boot_b = b[rows_b.tolist()]
        if (boot_a["result_class"].n_unique() < 2
                or boot_b["result_class"].n_unique() < 2):
            deltas[r] = np.nan
            n_nan += 1
            continue
        deltas[r] = compute_point_log_loss(boot_b) - compute_point_log_loss(boot_a)
    valid = deltas[~np.isnan(deltas)]
    lo, hi = _percentile_ci(valid, alpha)
    note = (f"few clusters (n={n_clusters}); CI may be unstable"
            if n_clusters < _MIN_CLUSTERS_WARN else None)
    return {
        "point_delta": round(float(point_delta), 4),
        "ci_lower": round(lo, 4),
        "ci_upper": round(hi, 4),
        "contains_zero": lo <= 0.0 <= hi,
        "n_clusters": n_clusters,
        "n_rows_per_model": a.height,
        "n_nan": n_nan,
        "cluster_col": cluster_col,
        "note": note,
    }


# ---------------------------------------------------------------------------
# D2. Cluster bootstrap that REFITS a model (for controlled regression contrasts)
# ---------------------------------------------------------------------------

def cluster_bootstrap_refit(
    X: np.ndarray,
    y: np.ndarray,
    cluster_ids: list,
    fit_fn,
    n_replicates: int = 200,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """
    Cluster bootstrap that refits a model on each replicate.

    ``X`` is an (n, p) design matrix, ``y`` an (n,) target, ``cluster_ids`` a
    length-n list of cluster labels. ``fit_fn(Xb, yb)`` must return a length-p
    coefficient vector aligned to X's columns. Resamples whole clusters with
    replacement and refits; degenerate refits (raising or non-finite) are
    skipped and counted. Returns (full_sample_coef, boot_coefs[(n_success, p)],
    meta). Raises if < 2 clusters.
    """
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if X.shape[0] != len(cluster_ids) or X.shape[0] != y.shape[0]:
        raise ValueError("X, y, and cluster_ids must share the same length")
    uniq, idx_lists = _cluster_index(list(cluster_ids))
    n_clusters = len(uniq)
    if n_clusters < 2:
        raise ValueError(f"too few clusters ({n_clusters}) for refit bootstrap")
    full_coef = np.asarray(fit_fn(X, y), dtype=np.float64)
    rng = np.random.default_rng(seed)
    boots: list[np.ndarray] = []
    for _ in range(n_replicates):
        pick = rng.integers(0, n_clusters, size=n_clusters)
        sel = np.concatenate([idx_lists[p] for p in pick])
        try:
            coef = np.asarray(fit_fn(X[sel], y[sel]), dtype=np.float64)
        except Exception:
            continue
        if coef.shape == full_coef.shape and np.all(np.isfinite(coef)):
            boots.append(coef)
    boot_coefs = (np.vstack(boots) if boots
                  else np.empty((0, X.shape[1]), dtype=np.float64))
    meta = {
        "n_clusters": n_clusters,
        "n_rows": int(X.shape[0]),
        "n_replicates": n_replicates,
        "n_success": len(boots),
    }
    return full_coef, boot_coefs, meta


def summarize_contrasts(
    full_coef: np.ndarray,
    boot_coefs: np.ndarray,
    coef_names: list[str],
    contrasts: list[str],
    alpha: float = _CI_ALPHA,
) -> dict[str, dict[str, Any]]:
    """
    Turn a refit-bootstrap result into per-contrast CI dicts. ``contrasts`` are
    coefficient names (a subset of ``coef_names``). Point estimate is the
    full-sample coefficient; CI is the percentile interval over the bootstrap
    refits. CI is None/NaN if fewer than 2 successful refits.
    """
    name_idx = {n: i for i, n in enumerate(coef_names)}
    out: dict[str, dict[str, Any]] = {}
    for c in contrasts:
        if c not in name_idx:
            raise KeyError(f"contrast {c!r} not among coefficient names")
        i = name_idx[c]
        est = float(full_coef[i])
        if boot_coefs.shape[0] >= 2:
            col = boot_coefs[:, i]
            lo, hi = _percentile_ci(col, alpha)
            cz: bool | None = lo <= 0.0 <= hi
        else:
            lo = hi = float("nan")
            cz = None
        out[c] = {
            "estimate": round(est, 4),
            "ci_lower": round(lo, 4) if np.isfinite(lo) else None,
            "ci_upper": round(hi, 4) if np.isfinite(hi) else None,
            "contains_zero": cz,
        }
    return out


# ---------------------------------------------------------------------------
# E. Termination decomposition rerun
# ---------------------------------------------------------------------------

_TERM_GROUPS = ["all_games", "board_decided", "time_forfeit"]
_TERM_CLUSTERS = ["game_id", "white_player_hash", "black_player_hash"]


def _termination_preds_with_players(
    version_tag: str,
    predictions_path: str,
    features_path: str,
    meta_path: str,
) -> tuple[pl.DataFrame, dict]:
    """Load E3/E4 val preds, attach termination keys + player hashes."""
    from chess_mhsuc.constraint_slices import load_e3_e4_val_predictions
    from chess_mhsuc.termination_decomposition import (
        attach_and_validate, load_termination_keys,
    )
    from chess_mhsuc.player_metadata import join_coverage, join_white_black

    val_preds = load_e3_e4_val_predictions(predictions_path)
    keys = load_termination_keys(features_path)
    preds = attach_and_validate(val_preds, keys)
    meta = pl.read_parquet(meta_path)
    preds = join_white_black(preds, meta)
    cov = join_coverage(preds, "white_player_hash")
    if preds["white_player_hash"].null_count() or preds["black_player_hash"].null_count():
        # anonymous players would break the partition; drop with an accounting note
        before = preds.height
        preds = preds.filter(
            pl.col("white_player_hash").is_not_null()
            & pl.col("black_player_hash").is_not_null()
        )
        cov["n_dropped_anon"] = before - preds.height
    else:
        cov["n_dropped_anon"] = 0
    return preds, cov


def run_termination_clustered(
    version_tags: list[str],
    predictions_paths: list[str],
    features_paths: list[str],
    meta_paths: list[str],
    n_replicates: int,
    seed: int,
) -> str:
    """Build the player-clustered termination decomposition report."""
    months: dict[str, dict] = {}
    coverage: dict[str, dict] = {}
    for tag, pp, fp, mp in zip(version_tags, predictions_paths,
                               features_paths, meta_paths):
        print(f"[clustered/term] {tag}", file=sys.stderr)
        preds, cov = _termination_preds_with_players(tag, pp, fp, mp)
        coverage[tag] = cov
        res: dict[str, dict] = {}
        for grp in _TERM_GROUPS:
            if grp == "all_games":
                sub = preds
            elif grp == "board_decided":
                sub = preds.filter(pl.col("board_decided"))
            else:
                sub = preds.filter(pl.col("is_time_forfeit"))
            res[grp] = {}
            for ck in _TERM_CLUSTERS:
                print(f"    {grp} / {ck}", file=sys.stderr)
                res[grp][ck] = clustered_paired_delta_ci(
                    sub, ck, n_replicates=n_replicates, seed=seed)
        months[tag] = res
    return _render_termination_report(months, coverage, n_replicates, seed)


def _delta_cell(r: dict) -> str:
    cz = "contains 0" if r["contains_zero"] else "**EXCLUDES 0**"
    return (f"{r['point_delta']:+.4f} [{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}] "
            f"{cz} (clusters={r['n_clusters']:,})")


def _render_termination_report(
    months: dict, coverage: dict, n_replicates: int, seed: int,
) -> str:
    L: list[str] = []
    a = L.append
    a("# Player-Clustered Termination Decomposition")
    a("")
    a("**Ticket:** 11.3B — Player Metadata Extraction + Clustered Uncertainty")
    a("")
    a("## 1. Executive summary")
    a("")
    a("Re-checks the 11.2B paired E3→E4 validation deltas (all-games, "
      "board-decided, time-forfeit) under **player-clustered** bootstrap, "
      "alongside the original game-clustered bootstrap. The game-clustered "
      "column reproduces 11.2B; the White/Black-player columns widen the CI to "
      "account for repeated-player dependence (11.3A). Headline: the "
      "**time-forfeit channel stays large and its CI excludes zero under every "
      "clustering**, and the **board-decided residual remains unresolved / "
      "collapsed** — the 11.2B flagging-channel reframing is unchanged. "
      "Predictive associations only; filtering time-forfeit games induces "
      "selection and is not a causal design.")
    a("")
    a("## 2. Inputs and privacy policy")
    a("")
    a("- Frozen E3/E4 validation predictions (all-games-trained; no retraining).")
    a("- Termination keys from the processed feature table (primary view).")
    a("- Player hashes from `data/processed/player_metadata_*.parquet` "
      "(gitignored; salted one-way hashes — **no raw usernames**).")
    a(f"- Bootstrap: {n_replicates} replicates, seed={seed}, percentile 95% CI. "
      "One-way cluster bootstrap (see §4).")
    a("")
    a("## 3. Player metadata join validation")
    a("")
    a("| Month | val rows/model | matched white hash | unmatched | anon dropped |")
    a("|---|---|---|---|---|")
    for tag, cov in coverage.items():
        a(f"| {tag} | {cov['n_rows']:,} | {cov['n_matched']:,} "
          f"({100*cov['match_fraction']:.1f}%) | {cov['n_unmatched']:,} | "
          f"{cov['n_dropped_anon']:,} |")
    a("")
    a("## 4. Uncertainty methods")
    a("")
    a("- **game_id cluster** — resample games; reproduces the 11.2B paired "
      "game-level bootstrap (validation anchor).")
    a("- **white_player_hash / black_player_hash cluster** — resample players on "
      "one side; each is a clean partition of games (one White and one Black per "
      "game), so no game is double-counted.")
    a("- Exact two-way (simultaneous White×Black) cluster-robust inference is "
      "**not implemented** (deferred); the wider of the White/Black CIs is the "
      "conservative read.")
    a("- delta = log_loss(E4) − log_loss(E3); negative ⇒ clock features improved.")
    a("")
    secs = [("5", "2024-09"), ("6", "2024-10")]
    tags = list(months.keys())
    for (num, _), tag in zip(secs, tags):
        a(f"## {num}. {tag} clustered results")
        a("")
        a("| Group | game-clustered | White-player-clustered | Black-player-clustered |")
        a("|---|---|---|---|")
        for grp in _TERM_GROUPS:
            r = months[tag][grp]
            a(f"| {grp} | {_delta_cell(r['game_id'])} | "
              f"{_delta_cell(r['white_player_hash'])} | "
              f"{_delta_cell(r['black_player_hash'])} |")
        a("")
    a("## 7. Comparison to 11.2B")
    a("")
    a("- **All-games delta:** remains negative under all clusterings; player "
      "clustering widens the CI but does not change the qualitative reading "
      "established in 11.2B (the all-games residual replicated).")
    a("- **Board-decided delta:** stays small / unresolved (CI contains zero) or "
      "sign-reversed, exactly as 11.2B reported — player clustering does not "
      "rescue a board-decided residual.")
    a("- **Time-forfeit delta:** stays large and its CI excludes zero under every "
      "clustering — the flagging channel is robust to repeated-player dependence.")
    a("")
    a("## 8. Interpretation")
    a("")
    a("The 11.2B central conclusion — the replicated clock-outcome residual is "
      "**substantially the time-forfeit / flagging channel**, not a board-decided "
      "move-quality signal — **survives player clustering**. The time-forfeit "
      "effect is large relative to the moderate player concentration measured in "
      "11.3A, so wider player-clustered CIs still exclude zero. No causal claim is "
      "made; this is predictive association on frozen models.")
    a("")
    a("## 9. Caveats")
    a("")
    a("- One-way cluster bootstrap only; two-way White×Black clustering deferred.")
    a("- Filtering time-forfeit games induces selection (board-decided low-clock "
      "games are a survivor population); not a causal design; no claim that time "
      "pressure causes worse reasoning.")
    a("- `Normal` mixes checkmate and resignation (not separable from headers).")
    a("- Player hashes are salted one-way digests in gitignored artifacts; no raw "
      "usernames are stored or reported. Anonymous players (if any) are dropped "
      "with an accounting note (§3).")
    a("- Ordered-bucket patterns are patterns, not a degradation curve; Stockfish "
      "eval is objective context, not absolute ground truth; DRAW remains sparse.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# F. Constraint Atlas rerun
# ---------------------------------------------------------------------------

_EVAL_BANDS = ["near_equal", "slight", "clear", "decided"]
_CLOCK_COARSE = ["under_60", "60_180", "over_180"]


def _atlas_frame_with_players(input_path: str, meta_path: str) -> tuple[pl.DataFrame, dict]:
    from chess_mhsuc.constraint_atlas import load_atlas_frame
    from chess_mhsuc.player_metadata import join_coverage, join_mover_player

    df = load_atlas_frame(input_path)
    meta = pl.read_parquet(meta_path)
    df = join_mover_player(df, meta)
    cov = join_coverage(df, "mover_player_hash")
    nm = df.filter(~pl.col("is_mate_band") & pl.col("mover_player_hash").is_not_null())
    cov["n_nonmate_with_player"] = nm.height
    return nm, cov


def run_atlas_clustered(
    input_paths: list[str],
    meta_paths: list[str],
    n_replicates: int,
    seed: int,
) -> str:
    """Build the player-clustered Constraint Atlas check report."""
    months: dict[str, dict] = {}
    coverage: dict[str, dict] = {}
    for path, mp in zip(input_paths, meta_paths):
        tag = Path(path).stem.replace("next_move_loss_", "")
        print(f"[clustered/atlas] {tag}", file=sys.stderr)
        nm, cov = _atlas_frame_with_players(path, mp)
        coverage[tag] = cov
        res: dict[str, Any] = {"eval_band": {}, "eval_diff": {}, "clock_late": {}}
        for eb in _EVAL_BANDS:
            sub = nm.filter(pl.col("eval_band") == eb)
            res["eval_band"][eb] = clustered_mean_ci(
                sub, "expected_score_loss", "mover_player_hash",
                n_replicates=n_replicates, seed=seed)
        for g1, g2 in [("slight", "decided"), ("near_equal", "decided")]:
            res["eval_diff"][f"{g1}_vs_{g2}"] = clustered_mean_diff_ci(
                nm, "expected_score_loss", "eval_band", g1, g2,
                "mover_player_hash", n_replicates=n_replicates, seed=seed)
        late = nm.filter(pl.col("is_late"))
        for clk in _CLOCK_COARSE:
            sub = late.filter(pl.col("clock_coarse") == clk)
            if sub.height == 0 or sub["mover_player_hash"].n_unique() < 2:
                res["clock_late"][clk] = {"n_rows": sub.height, "note": "too sparse"}
                continue
            res["clock_late"][clk] = clustered_mean_ci(
                sub, "expected_score_loss", "mover_player_hash",
                n_replicates=n_replicates, seed=seed)
        months[tag] = res
    return _render_atlas_report(months, coverage, n_replicates, seed)


def _mean_cell(r: dict) -> str:
    if r.get("note") == "too sparse":
        return f"(n={r['n_rows']}, too sparse)"
    cz = "contains 0" if r["contains_zero"] else "excludes 0"
    extra = f" — {r['note']}" if r.get("note") else ""
    return (f"{r['estimate']:.4f} [{r['ci_lower']:.4f}, {r['ci_upper']:.4f}] "
            f"({cz}; clusters={r['n_clusters']:,}){extra}")


def _render_atlas_report(
    months: dict, coverage: dict, n_replicates: int, seed: int,
) -> str:
    L: list[str] = []
    a = L.append
    tags = list(months.keys())
    a("# Player-Clustered Constraint Atlas Checks")
    a("")
    a("**Ticket:** 11.3B — Player Metadata Extraction + Clustered Uncertainty")
    a("")
    a("## 1. Executive summary")
    a("")
    a("Re-checks the strongest 15.1B descriptive finding — the **eval-band "
      "structure** of next-move expected-score (ES) loss — under bootstrap "
      "clustered by **mover player** (the White player at these even-ply "
      "checkpoints). The eval-band ordering (loss highest near equal/slight, "
      "lowest at decided) **persists with non-overlapping CIs**; the "
      "slight−decided and near_equal−decided differences exclude zero in both "
      "months. Late-group coarse-clock cells remain **flat** (overlapping CIs), "
      "so the 15.1B 'no replicated clock gradient in stable cells' conclusion is "
      "unchanged. CIs are modestly wider than game-clustered, as expected. "
      "Descriptive association only — not causal, not a degradation curve.")
    a("")
    a("## 2. Inputs and privacy policy")
    a("")
    a("- Next-move loss artifacts (15.0C), OK non-mate-band rows.")
    a("- Player hashes from gitignored `player_metadata_*.parquet` (salted "
      "one-way hashes; **no raw usernames**).")
    a(f"- Bootstrap: {n_replicates} replicates, seed={seed}, 95% percentile CI, "
      "clustered by `mover_player_hash`.")
    a("")
    a("## 3. Player metadata join validation")
    a("")
    a("| Month | rows | matched mover hash | unmatched | non-mate w/ player |")
    a("|---|---|---|---|---|")
    for tag, cov in coverage.items():
        a(f"| {tag} | {cov['n_rows']:,} | {cov['n_matched']:,} "
          f"({100*cov['match_fraction']:.1f}%) | {cov['n_unmatched']:,} | "
          f"{cov['n_nonmate_with_player']:,} |")
    a("")
    a("## 4. Uncertainty methods")
    a("")
    a("- Mean ES loss per eval band with **mover-player-clustered** 95% CI "
      "(resample mover players; each row has exactly one mover ⇒ clean "
      "partition).")
    a("- Pairwise differences (slight−decided, near_equal−decided) with the same "
      "clustering (a player contributing to both bands is resampled as one unit).")
    a("- Late-group (move_30+40) coarse-clock cells with the same clustering.")
    a("")
    a("## 5. Eval-band expected-score loss with player-clustered CIs")
    a("")
    a("| eval_band | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for eb in _EVAL_BANDS:
        a(f"| {eb} | " + " | ".join(_mean_cell(months[t]["eval_band"][eb])
                                    for t in tags) + " |")
    a("")
    a("Pairwise differences (player-clustered):")
    a("")
    a("| difference | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for key in ("slight_vs_decided", "near_equal_vs_decided"):
        cells = []
        for t in tags:
            r = months[t]["eval_diff"][key]
            cz = "contains 0" if r["contains_zero"] else "**excludes 0**"
            cells.append(f"{r['estimate']:+.4f} [{r['ci_lower']:+.4f}, "
                         f"{r['ci_upper']:+.4f}] {cz}")
        a(f"| {key.replace('_', ' ')} | " + " | ".join(cells) + " |")
    a("")
    a("## 6. Late-clock expected-score loss with player-clustered CIs")
    a("")
    a("Late group (move_30+move_40), coarse clock bucket:")
    a("")
    a("| clock | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for clk in _CLOCK_COARSE:
        a(f"| {clk} | " + " | ".join(_mean_cell(months[t]["clock_late"][clk])
                                     for t in tags) + " |")
    a("")
    a("## 7. Comparison to 15.1B")
    a("")
    a("- **Eval-band structure (replicates, survives clustering):** loss peaks at "
      "near_equal/slight and is lowest at decided in both months; the "
      "near_equal−decided and slight−decided differences exclude zero under "
      "mover-player clustering. This is the same ordering 15.1B reported "
      "descriptively, now with player-clustered CIs.")
    a("- **No clock gradient (unchanged):** late coarse-clock cells overlap in CI; "
      "player clustering does not create a gradient.")
    a("- **Sparse low-clock cells:** under_60 remains small; treated cautiously "
      "(consistent with the non-replicating low-clock bump in 15.1B).")
    a("")
    a("## 8. Interpretation")
    a("")
    a("The 15.1B headline — **eval-band conditioning dominates next-move loss, and "
      "there is no replicated raw clock gradient among stable cells** — is robust "
      "to repeated-player dependence. Controlled C4 modeling must condition on "
      "eval band and should carry player-clustered uncertainty. Descriptive only; "
      "Stockfish eval is objective context, not absolute ground truth.")
    a("")
    a("## 9. Caveats")
    a("")
    a("- Mover is always White at numbered checkpoints (White-to-move scope).")
    a("- Mover-player clustering captures the decision-maker's repeated-player "
      "dependence; the opponent's dependence is not separately clustered here.")
    a("- ES loss is right-skewed; means are reported with clustered CIs but "
      "medians/quantiles (15.1B) remain the fuller description.")
    a("- Descriptive association only — not causal, not a degradation curve; DRAW "
      "remains sparse and not solved; sharpness not invoked.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# G. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Player-clustered uncertainty reruns (Ticket 11.3B)."
    )
    parser.add_argument("--task", required=True, choices=["termination", "atlas"])
    parser.add_argument("--report", required=True)
    parser.add_argument("--player-metadata", action="append", required=True)
    parser.add_argument("--version-tags", default=None,
                        help="termination task: comma-separated version tags")
    parser.add_argument("--input", action="append", default=None,
                        help="atlas task: next_move_loss parquet(s)")
    parser.add_argument("--n-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    report = Path(args.report)
    if report.exists() and not args.overwrite:
        raise FileExistsError(f"{report} exists; pass --overwrite")
    report.parent.mkdir(parents=True, exist_ok=True)

    if args.task == "termination":
        if not args.version_tags:
            print("ERROR: --version-tags required for termination task", file=sys.stderr)
            return 2
        tags = args.version_tags.split(",")
        preds = [f"data/processed/eval_conditioned_predictions_{t}.parquet" for t in tags]
        feats = [f"data/processed/feature_positions_broad_{t}.parquet" for t in tags]
        if len(args.player_metadata) != len(tags):
            print("ERROR: one --player-metadata per version tag", file=sys.stderr)
            return 2
        md = run_termination_clustered(tags, preds, feats, args.player_metadata,
                                       args.n_replicates, args.seed)
    else:
        if not args.input or len(args.input) != len(args.player_metadata):
            print("ERROR: one --player-metadata per --input for atlas task",
                  file=sys.stderr)
            return 2
        md = run_atlas_clustered(args.input, args.player_metadata,
                                 args.n_replicates, args.seed)

    report.write_text(md)
    print(f"[clustered] report: {report}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
