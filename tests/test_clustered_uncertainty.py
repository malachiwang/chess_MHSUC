"""Tests for clustered_uncertainty.py (Ticket 11.3B)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc import clustered_uncertainty as cu


# ---- validate_cluster_key ----

def test_validate_missing_key_raises():
    df = pl.DataFrame({"x": [1, 2]})
    with pytest.raises(ValueError, match="not in frame"):
        cu.validate_cluster_key(df, "cluster")


def test_validate_null_key_raises():
    df = pl.DataFrame({"cluster": ["a", None], "x": [1, 2]})
    with pytest.raises(ValueError, match="null"):
        cu.validate_cluster_key(df, "cluster")


def test_validate_ok():
    df = pl.DataFrame({"cluster": ["a", "b"], "x": [1, 2]})
    cu.validate_cluster_key(df, "cluster")  # no raise


# ---- clustered_mean_ci ----

def _mean_df(n_clusters=50, rows_per=3, seed=0):
    rng = np.random.default_rng(seed)
    clusters, vals = [], []
    for c in range(n_clusters):
        base = rng.normal(0.5, 0.1)
        for _ in range(rows_per):
            clusters.append(f"c{c}")
            vals.append(base + rng.normal(0, 0.01))
    return pl.DataFrame({"cluster": clusters, "v": vals})


def test_clustered_mean_ci_deterministic():
    df = _mean_df()
    r1 = cu.clustered_mean_ci(df, "v", "cluster", n_replicates=200, seed=42)
    r2 = cu.clustered_mean_ci(df, "v", "cluster", n_replicates=200, seed=42)
    assert r1 == r2
    assert r1["ci_lower"] <= r1["estimate"] <= r1["ci_upper"]


def test_clustered_mean_ci_reports_counts():
    df = _mean_df(n_clusters=40, rows_per=2)
    r = cu.clustered_mean_ci(df, "v", "cluster", n_replicates=100, seed=1)
    assert r["n_clusters"] == 40
    assert r["n_rows"] == 80
    assert r["cluster_col"] == "cluster"


def test_clustered_mean_ci_few_clusters_note():
    df = _mean_df(n_clusters=5, rows_per=2)
    r = cu.clustered_mean_ci(df, "v", "cluster", n_replicates=100, seed=1)
    assert r["note"] is not None and "few clusters" in r["note"]


def test_clustered_mean_ci_too_few_clusters_raises():
    df = pl.DataFrame({"cluster": ["a", "a"], "v": [0.1, 0.2]})
    with pytest.raises(ValueError, match="too few clusters"):
        cu.clustered_mean_ci(df, "v", "cluster", n_replicates=10)


def test_clustered_ci_wider_than_naive_on_repeated_clusters():
    # Strong within-cluster correlation -> clustered CI should be wide.
    # 10 clusters, identical 100 rows each at cluster-specific value.
    clusters, vals = [], []
    rng = np.random.default_rng(3)
    cluster_means = rng.normal(0.5, 0.3, size=10)
    for c in range(10):
        for _ in range(100):
            clusters.append(f"c{c}")
            vals.append(cluster_means[c])
    df = pl.DataFrame({"cluster": clusters, "v": vals})
    clustered = cu.clustered_mean_ci(df, "v", "cluster", n_replicates=500, seed=7)
    width = clustered["ci_upper"] - clustered["ci_lower"]
    # A naive row CI (sd/sqrt(1000)) would be ~0.02; clustered must be far wider.
    assert width > 0.1


# ---- clustered_mean_diff_ci ----

def test_clustered_mean_diff_sign_and_zero():
    # group hi clearly above group lo.
    clusters, vals, grp = [], [], []
    for c in range(40):
        for _ in range(3):
            clusters.append(f"c{c}"); vals.append(0.9); grp.append("hi")
            clusters.append(f"c{c}"); vals.append(0.1); grp.append("lo")
    df = pl.DataFrame({"cluster": clusters, "v": vals, "g": grp})
    r = cu.clustered_mean_diff_ci(df, "v", "g", "hi", "lo", "cluster",
                                  n_replicates=200, seed=5)
    assert r["estimate"] > 0
    assert r["contains_zero"] is False


def test_clustered_mean_diff_missing_group_raises():
    df = pl.DataFrame({"cluster": ["a", "b"], "v": [0.1, 0.2], "g": ["x", "x"]})
    with pytest.raises(ValueError, match="no rows"):
        cu.clustered_mean_diff_ci(df, "v", "g", "x", "y", "cluster",
                                  n_replicates=10)


# ---- clustered_paired_delta_ci ----

def _paired_df(n_clusters=60, rows_per=2, b_better=True, seed=0):
    """E3/E4 paired prediction rows; E4 gives sharper (lower-loss) probs."""
    rng = np.random.default_rng(seed)
    rows = []
    classes = ["BLACK_WIN", "DRAW", "WHITE_WIN"]
    for c in range(n_clusters):
        for _ in range(rows_per):
            true = classes[rng.integers(0, 3)]
            # E3: diffuse; E4: concentrated on the true class.
            for model, conc in [("E3", 0.5), ("E4", 0.85 if b_better else 0.5)]:
                p = {cl: (1 - conc) / 2 for cl in classes}
                p[true] = conc
                rows.append({
                    "model_id": model, "cluster": f"c{c}", "game_id": f"c{c}",
                    "result_class": true,
                    "p_BLACK_WIN": p["BLACK_WIN"], "p_DRAW": p["DRAW"],
                    "p_WHITE_WIN": p["WHITE_WIN"],
                })
    return pl.DataFrame(rows)


def test_paired_delta_negative_when_b_better():
    df = _paired_df(b_better=True, seed=1)
    r = cu.clustered_paired_delta_ci(df, "cluster", n_replicates=200, seed=2)
    assert r["point_delta"] < 0  # E4 improved
    assert r["n_clusters"] == 60


def test_paired_delta_deterministic():
    df = _paired_df(seed=1)
    r1 = cu.clustered_paired_delta_ci(df, "cluster", n_replicates=100, seed=9)
    r2 = cu.clustered_paired_delta_ci(df, "cluster", n_replicates=100, seed=9)
    assert r1 == r2


def test_paired_delta_game_id_matches_cluster_when_equal():
    # cluster == game_id here, so both keys give identical CIs.
    df = _paired_df(seed=4)
    r_game = cu.clustered_paired_delta_ci(df, "game_id", n_replicates=150, seed=11)
    r_clu = cu.clustered_paired_delta_ci(df, "cluster", n_replicates=150, seed=11)
    assert r_game["point_delta"] == r_clu["point_delta"]
    assert r_game["ci_lower"] == r_clu["ci_lower"]


def test_paired_delta_too_few_clusters_raises():
    df = _paired_df(n_clusters=1, rows_per=2, seed=1)
    with pytest.raises(ValueError, match="too few common clusters"):
        cu.clustered_paired_delta_ci(df, "cluster", n_replicates=10)


def test_paired_delta_missing_model_raises():
    df = _paired_df(seed=1).filter(pl.col("model_id") == "E3")
    with pytest.raises(ValueError, match="missing rows"):
        cu.clustered_paired_delta_ci(df, "cluster", n_replicates=10)
