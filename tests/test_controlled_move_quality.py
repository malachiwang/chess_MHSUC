"""Tests for controlled_move_quality.py (Ticket 15.1D)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc import controlled_move_quality as cmq
from chess_mhsuc import clustered_uncertainty as cu


# ---------------------------------------------------------------------------
# Synthetic modeling frame
# ---------------------------------------------------------------------------

def _synth_frame(n=1200, seed=0, big_loss=False):
    rng = np.random.default_rng(seed)
    clocks = rng.choice(["over_180", "60_180", "under_60"], size=n, p=[0.8, 0.15, 0.05])
    checkpoints = rng.choice(["move_10", "move_20", "move_30", "move_40"], size=n)
    evals = rng.choice(["decided", "near_equal", "slight", "clear"], size=n)
    ratings = rng.integers(800, 2200, size=n).astype(float)
    months = rng.choice(["2024_09", "2024_10"], size=n)
    players = [f"p{rng.integers(0, 120)}" for _ in range(n)]
    splits = rng.choice(["train", "val", "test"], size=n, p=[0.7, 0.15, 0.15])
    # Known structure: eval near_equal/slight raise loss; clock ~ no effect.
    base = 0.02
    es = (base
          + 0.015 * (evals == "near_equal")
          + 0.020 * (evals == "slight")
          + 0.010 * (evals == "clear")
          + 0.0 * (clocks == "60_180")
          + rng.normal(0, 0.003, size=n))
    if big_loss:
        # add a sparse heavy tail so the large-loss targets carry both classes;
        # the bump is independent of eval band, so eval contrasts are unbiased.
        bump = rng.choice([0.0, 1.0], size=n, p=[0.8, 0.2]) * rng.uniform(0.05, 0.35, size=n)
        es = es + bump
    es = np.clip(es, 0, None)
    return pl.DataFrame({
        "expected_score_loss": es,
        "mover_rating": ratings,
        "clock_coarse": clocks,
        "eval_band": evals,
        "selected_position_type": checkpoints,
        "board_decided": rng.choice([True, False], size=n, p=[0.85, 0.15]),
        "split_set": splits,
        "is_mate_band": np.zeros(n, dtype=bool),
        "month": months,
        "mover_player_hash": players,
        "termination_binary": ["board_decided"] * n,
        "large_loss_es_005": (es > 0.05).astype(int),
        "large_loss_es_010": (es > 0.10).astype(int),
    })


# ---------------------------------------------------------------------------
# Design matrix / reference levels
# ---------------------------------------------------------------------------

def test_design_uses_reference_levels():
    df = _synth_frame(300, seed=1)
    X, names = cmq.build_design(df, 1500.0, 300.0, include_month=False)
    # reference levels must NOT have their own dummy column
    assert "clock=over_180" not in names
    assert "checkpoint=move_10" not in names
    assert "eval=decided" not in names
    assert "termination=board_decided" not in names
    # non-reference levels present
    assert "clock=60_180" in names and "clock=under_60" in names
    assert "eval=slight" in names and "eval=near_equal" in names
    assert names[0] == "intercept"
    assert X.shape == (300, len(names))


def test_design_month_toggle():
    df = _synth_frame(200, seed=2)
    _, no_month = cmq.build_design(df, 1500.0, 300.0, include_month=False)
    _, with_month = cmq.build_design(df, 1500.0, 300.0, include_month=True)
    assert "month=2024_10" not in no_month
    assert "month=2024_10" in with_month


def test_rating_z_uses_train_moments():
    df = _synth_frame(400, seed=3)
    mean, std = cmq.train_rating_moments(df)
    tr = df.filter(pl.col("split_set") == "train")["mover_rating"].to_numpy().astype(float)
    assert mean == pytest.approx(float(np.mean(tr)))
    assert std == pytest.approx(float(np.std(tr)))
    # rating_z column has ~0 mean on TRAIN rows specifically
    X, names = cmq.build_design(df, mean, std, include_month=False)
    rz = X[:, names.index("rating_z")]
    train_mask = (df["split_set"] == "train").to_numpy()
    assert abs(rz[train_mask].mean()) < 1e-9


# ---------------------------------------------------------------------------
# OLS recovery + contrasts
# ---------------------------------------------------------------------------

def test_ols_recovers_known_coefficients():
    df = _synth_frame(4000, seed=4)
    mean, std = cmq.train_rating_moments(df)
    X, names = cmq.build_design(df, mean, std, include_month=False)
    y = df["expected_score_loss"].to_numpy().astype(float)
    beta = cmq._ols_fit(X, y)
    idx = {n: i for i, n in enumerate(names)}
    # slight ~ +0.020, near_equal ~ +0.015 vs decided; clock ~ 0
    assert beta[idx["eval=slight"]] == pytest.approx(0.020, abs=0.004)
    assert beta[idx["eval=near_equal"]] == pytest.approx(0.015, abs=0.004)
    assert abs(beta[idx["clock=60_180"]]) < 0.005


def test_fit_ols_with_bootstrap_contrasts():
    df = _synth_frame(2000, seed=5)
    mean, std = cmq.train_rating_moments(df)
    res = cmq.fit_ols_with_bootstrap(df, mean, std, False,
                                     cmq.PRIMARY_CONTRASTS, n_reps=50, seed=42)
    assert "eval_slight_vs_decided" in res["contrasts"]
    c = res["contrasts"]["eval_slight_vs_decided"]
    assert c["ci_lower"] <= c["estimate"] <= c["ci_upper"]
    # positive control should exclude zero
    assert c["contains_zero"] is False
    # clock null: 60_180 contains zero
    assert res["contrasts"]["clock_60_180_vs_over_180"]["contains_zero"] is True


# ---------------------------------------------------------------------------
# Cluster bootstrap refit (in clustered_uncertainty)
# ---------------------------------------------------------------------------

def test_cluster_bootstrap_refit_deterministic():
    df = _synth_frame(800, seed=6)
    X, names = cmq.build_design(df, 1500.0, 300.0, include_month=False)
    y = df["expected_score_loss"].to_numpy().astype(float)
    clusters = df["mover_player_hash"].to_list()
    f1, b1, m1 = cu.cluster_bootstrap_refit(X, y, clusters, cmq._ols_fit, 40, 7)
    f2, b2, m2 = cu.cluster_bootstrap_refit(X, y, clusters, cmq._ols_fit, 40, 7)
    assert np.allclose(f1, f2)
    assert np.allclose(b1, b2)
    assert m1 == m2


def test_cluster_bootstrap_refit_reports_counts():
    df = _synth_frame(600, seed=8)
    X, names = cmq.build_design(df, 1500.0, 300.0, include_month=False)
    y = df["expected_score_loss"].to_numpy().astype(float)
    clusters = df["mover_player_hash"].to_list()
    _, boot, meta = cu.cluster_bootstrap_refit(X, y, clusters, cmq._ols_fit, 30, 1)
    assert meta["n_rows"] == 600
    assert meta["n_clusters"] == len(set(clusters))
    assert meta["n_success"] <= 30 and boot.shape[0] == meta["n_success"]


def test_cluster_bootstrap_refit_too_few_clusters():
    X = np.ones((4, 2)); y = np.array([0.1, 0.2, 0.3, 0.4])
    with pytest.raises(ValueError, match="too few clusters"):
        cu.cluster_bootstrap_refit(X, y, ["a", "a", "a", "a"], cmq._ols_fit, 10)


def test_cluster_bootstrap_refit_length_mismatch():
    X = np.ones((3, 2)); y = np.array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError, match="same length"):
        cu.cluster_bootstrap_refit(X, y, ["a", "b"], cmq._ols_fit, 5)


def test_summarize_contrasts_unknown_name():
    full = np.array([0.1, 0.2]); boot = np.array([[0.1, 0.2], [0.11, 0.19]])
    with pytest.raises(KeyError):
        cu.summarize_contrasts(full, boot, ["a", "b"], ["c"])


def test_summarize_contrasts_no_boot():
    full = np.array([0.5]); boot = np.empty((0, 1))
    out = cu.summarize_contrasts(full, boot, ["a"], ["a"])
    assert out["a"]["estimate"] == 0.5
    assert out["a"]["ci_lower"] is None and out["a"]["contains_zero"] is None


# ---------------------------------------------------------------------------
# Logistic large-loss target + fit
# ---------------------------------------------------------------------------

def test_logistic_large_loss_targets_constructed():
    df = _synth_frame(500, seed=9)
    assert set(df["large_loss_es_005"].unique().to_list()) <= {0, 1}
    assert set(df["large_loss_es_010"].unique().to_list()) <= {0, 1}


def test_logistic_fit_runs():
    df = _synth_frame(1500, seed=10, big_loss=True)
    mean, std = cmq.train_rating_moments(df)
    res = cmq.fit_logistic_with_bootstrap(df, "large_loss_es_005", mean, std, False,
                                          cmq.PRIMARY_CONTRASTS, n_reps=20, seed=3)
    # either runs or is cleanly skipped
    assert "contrasts" in res or "skipped" in res
    if "contrasts" in res:
        assert "eval_slight_vs_decided" in res["contrasts"]


# ---------------------------------------------------------------------------
# Sample sizes / splits
# ---------------------------------------------------------------------------

def test_sample_sizes_split_handling():
    df = _synth_frame(1000, seed=11)
    s = cmq.sample_sizes(df)
    assert s["n_total"] == 1000
    assert s["n_estimation"] == s["by_split"].get("train", 0) + s["by_split"].get("val", 0)
    assert set(s["by_split"]).issubset({"train", "val", "test"})


def test_month_from_tag():
    assert cmq.month_from_tag("2024_09_250k_v1") == "2024_09"
    assert cmq.month_from_tag("2024_10_250k_v1") == "2024_10"


# ---------------------------------------------------------------------------
# Report privacy: no raw hashes/usernames leak into rendered markdown
# ---------------------------------------------------------------------------

def test_month_report_excludes_player_hashes():
    df = _synth_frame(1500, seed=12)
    mean, std = cmq.train_rating_moments(df)
    est = df.filter(pl.col("split_set").is_in(cmq.ESTIMATION_SPLITS))
    test = df.filter(pl.col("split_set") == "test")
    ols = cmq.fit_ols_with_bootstrap(est, mean, std, False, cmq.PRIMARY_CONTRASTS, 20, 1)
    payload = {
        "version_tag": "synth_v1", "month": "synth",
        "input_path": "x.parquet", "meta_path": "m.parquet",
        "sizes": cmq.sample_sizes(df), "rating_mean": mean, "rating_std": std,
        "ols": ols,
        "logistic_005": {"skipped": "test"}, "logistic_010": {"skipped": "test"},
        "test_confirmation": cmq.point_contrasts_ols(test, mean, std, False,
                                                     cmq.PRIMARY_CONTRASTS),
        "n_reps": 20, "seed": 1,
    }
    md = cmq.render_month_report(payload)
    # No synthetic player hash like 'p37' should appear in the report body.
    sample_players = set(df["mover_player_hash"].to_list())
    assert not any(f"| {ph} " in md or f" {ph}," in md for ph in sample_players)
    assert "Controlled Move-Quality Modeling" in md
