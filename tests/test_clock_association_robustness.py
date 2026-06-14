"""Tests for clock_association_robustness.py (Ticket 15.1F)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc import clock_association_robustness as car
from chess_mhsuc import controlled_move_quality as cmq


def _synth_frame(n=2400, seed=0):
    rng = np.random.default_rng(seed)
    clocks = rng.choice(["over_180", "60_180", "under_60"], size=n, p=[0.8, 0.15, 0.05])
    checkpoints = rng.choice(["move_10", "move_20", "move_30", "move_40"], size=n)
    evals = rng.choice(["decided", "near_equal", "slight", "clear"], size=n)
    ratings = rng.integers(800, 2200, size=n).astype(float)
    months = rng.choice(["2024_09", "2024_10"], size=n)
    players = [f"p{rng.integers(0, 200)}" for _ in range(n)]
    gids = [f"g{i}" for i in range(n)]
    splits = rng.choice(["train", "val", "test"], size=n, p=[0.7, 0.15, 0.15])
    pre_cp = rng.normal(0, 250, size=n)
    es = (0.02 + 0.020 * (evals == "slight") + 0.015 * (evals == "near_equal")
          + 0.010 * (evals == "clear") + 0.004 * (clocks == "60_180")
          + rng.normal(0, 0.003, size=n))
    es = np.clip(es, 0, None)
    return pl.DataFrame({
        "expected_score_loss": es,
        "clipped_cp_loss": np.clip(np.abs(rng.normal(40, 60, size=n)), 0, 1000),
        "mover_pre_cp": pre_cp,
        "mover_rating": ratings,
        "clock_coarse": clocks,
        "eval_band": evals,
        "selected_position_type": checkpoints,
        "board_decided": rng.choice([True, False], size=n, p=[0.85, 0.15]),
        "split_set": splits,
        "is_mate_band": np.zeros(n, dtype=bool),
        "month": months,
        "termination_binary": ["board_decided"] * n,
        "mover_player_hash": players,
        "white_player_hash": players,
        "black_player_hash": [f"b{i%150}" for i in range(n)],
        "game_id": gids,
        "large_loss_es_005": (es > 0.05).astype(int),
        "large_loss_es_010": (es > 0.10).astype(int),
    })


# ---- moments / scaling ----

def test_fit_moments_train_only():
    df = _synth_frame(800, seed=1)
    m = car.fit_moments(df)
    tr = df.filter(pl.col("split_set") == "train")
    assert m["rating_mean"] == pytest.approx(
        float(tr["mover_rating"].mean()))
    assert len(m["rating_edges"]) == 4  # quintile inner edges


def test_abs_cp_z_train_only_zero_mean():
    df = _synth_frame(1000, seed=2)
    m = car.fit_moments(df)
    X, names = car.build_variant_design(df, m, include_month=False,
                                        include_termination=True, add_abs_cp=True)
    z = X[:, names.index("abs_cp_z")]
    tr_mask = (df["split_set"] == "train").to_numpy()
    assert abs(z[tr_mask].mean()) < 1e-9


# ---- design variants ----

def test_continuous_eval_adds_column():
    df = _synth_frame(400, seed=3)
    m = car.fit_moments(df)
    _, names = car.build_variant_design(df, m, include_month=False,
                                        include_termination=True, add_abs_cp=True)
    assert "abs_cp_z" in names
    _, names2 = car.build_variant_design(df, m, include_month=False,
                                         include_termination=True, add_abs_cp=False)
    assert "abs_cp_z" not in names2


def test_rating_modes():
    df = _synth_frame(400, seed=4)
    m = car.fit_moments(df)
    _, lin = car.build_variant_design(df, m, include_month=False,
                                      include_termination=True, rating_mode="linear")
    _, quad = car.build_variant_design(df, m, include_month=False,
                                       include_termination=True, rating_mode="quadratic")
    _, bins = car.build_variant_design(df, m, include_month=False,
                                       include_termination=True, rating_mode="bins")
    assert "rating_z" in lin and "rating_z_sq" not in lin
    assert "rating_z_sq" in quad
    assert any(n.startswith("ratingbin=") for n in bins) and "rating_z" not in bins


def test_late_only_filter_drops_early_checkpoint_dummy():
    df = _synth_frame(600, seed=5)
    late = car._apply_filter(df, "late")
    assert set(late["selected_position_type"].unique().to_list()) <= {"move_30", "move_40"}
    m = car.fit_moments(df)
    _, names = car.build_variant_design(late, m, include_month=False,
                                        include_termination=True)
    # reference becomes move_30 (first present) → only move_40 dummy, no move_10/20
    assert "checkpoint=move_40" in names
    assert "checkpoint=move_10" not in names and "checkpoint=move_20" not in names


def test_board_decided_filter():
    df = _synth_frame(600, seed=6)
    bd = car._apply_filter(df, "board_decided")
    assert bd["board_decided"].all()


def test_clipped_cp_target_selected():
    df = _synth_frame(800, seed=7)
    m = car.fit_moments(df)
    res = car.fit_variant(df, m, target="clipped_cp_loss", model="ols",
                          include_month=False, include_termination=True,
                          rating_mode="linear", add_abs_cp=False,
                          cluster_col="mover_player_hash", n_reps=20, seed=1)
    assert res["target"] == "clipped_cp_loss"
    assert "clock_60_180_vs_over_180" in res["contrasts"]


def test_logistic_target_delegation_or_skip():
    df = _synth_frame(1500, seed=8)
    m = car.fit_moments(df)
    res = car.fit_variant(df, m, target="large_loss_es_005", model="logistic",
                          include_month=False, include_termination=True,
                          rating_mode="linear", add_abs_cp=False,
                          cluster_col="mover_player_hash", n_reps=15, seed=1)
    assert "contrasts" in res or "skipped" in res


# ---- baseline replication: my builder matches cmq.build_design ----

def test_baseline_design_matches_cmq():
    df = _synth_frame(1000, seed=9)
    m = car.fit_moments(df)
    rmean, rstd = cmq.train_rating_moments(df)
    X_car, n_car = car.build_variant_design(df, {**m, "rating_mean": rmean,
                                                 "rating_std": rstd},
                                            include_month=True,
                                            include_termination=True,
                                            rating_mode="linear", add_abs_cp=False)
    X_cmq, n_cmq = cmq.build_design(df, rmean, rstd, include_month=True)
    assert n_car == n_cmq
    assert np.allclose(X_car, X_cmq)


def test_baseline_clock_contrast_reproduces_cmq():
    df = _synth_frame(2000, seed=10)
    est = df.filter(pl.col("split_set").is_in(cmq.ESTIMATION_SPLITS))
    rmean, rstd = cmq.train_rating_moments(df)
    cmq_res = cmq.fit_ols_with_bootstrap(est, rmean, rstd, False,
                                         cmq.PRIMARY_CONTRASTS, n_reps=30, seed=42)
    m = car.fit_moments(est)
    car_res = car.fit_variant(est, {**m, "rating_mean": rmean, "rating_std": rstd},
                              target="expected_score_loss", model="ols",
                              include_month=False, include_termination=True,
                              rating_mode="linear", add_abs_cp=False,
                              cluster_col="mover_player_hash", n_reps=30, seed=42)
    a = cmq_res["contrasts"]["clock_60_180_vs_over_180"]["estimate"]
    b = car_res["contrasts"]["clock_60_180_vs_over_180"]["estimate"]
    assert a == pytest.approx(b, abs=1e-9)


# ---- verdict logic ----

def _c(est, lo, hi):
    return {"estimate": est, "ci_lower": lo, "ci_upper": hi,
            "contains_zero": lo <= 0 <= hi}


def test_verdict_survives():
    pos = _c(0.004, 0.001, 0.007)
    assert car.verdict_for_contrast(pos, pos, pos) == "survives"


def test_verdict_weakens_on_zero_crossing():
    pooled = _c(0.001, -0.001, 0.003)
    assert car.verdict_for_contrast(_c(0.003, 0.001, 0.005),
                                    _c(0.002, 0.0, 0.004), pooled) == "weakens"


def test_verdict_fails_on_sign_reversal():
    neg = _c(-0.004, -0.007, -0.001)
    assert car.verdict_for_contrast(neg, neg, neg) == "fails"


def test_verdict_mixed_when_months_disagree():
    pooled = _c(0.003, 0.001, 0.005)  # excludes 0 but months disagree in sign
    assert car.verdict_for_contrast(_c(0.01, 0.005, 0.015),
                                    _c(-0.005, -0.01, -0.001), pooled) == "mixed"


def test_verdict_not_run_when_none():
    assert car.verdict_for_contrast(None, None, None) == "not_run"


def test_overall_conclusion_weakens_when_eval_control_kills():
    matrix = {
        "baseline (15.1D)": {"verdict": "survives", "pooled": _c(0.0034, 0.001, 0.005)},
        "continuous eval control": {"verdict": "weakens",
                                    "pooled": _c(0.0005, -0.001, 0.002)},
        "board-decided-only": {"verdict": "weakens", "pooled": _c(0.0002, -0.002, 0.002)},
        "metric: clipped_cp_loss": {"pooled": _c(1.0, 0.2, 1.8)},
        "metric: logistic ES>0.05": {"pooled": _c(0.08, 0.01, 0.15)},
        "metric: logistic ES>0.10": {"pooled": _c(0.1, 0.0, 0.2)},
    }
    concl, reasons = car.overall_conclusion(matrix)
    assert concl == "weakens"
    assert any("board-decided" in r for r in reasons)


def test_overall_conclusion_survives_when_all_hold():
    g = _c(0.004, 0.001, 0.006)
    matrix = {
        "baseline (15.1D)": {"verdict": "survives", "pooled": g},
        "continuous eval control": {"verdict": "survives", "pooled": g},
        "board-decided-only": {"verdict": "survives", "pooled": g},
        "metric: clipped_cp_loss": {"pooled": _c(1.0, 0.2, 1.8)},
        "metric: logistic ES>0.05": {"pooled": _c(0.08, 0.01, 0.15)},
        "metric: logistic ES>0.10": {"pooled": _c(0.1, 0.02, 0.2)},
    }
    concl, _ = car.overall_conclusion(matrix)
    assert concl == "survives"


# ---- report privacy ----

def test_month_report_excludes_player_hashes():
    df = _synth_frame(2000, seed=12)
    est = df.filter(pl.col("split_set").is_in(cmq.ESTIMATION_SPLITS))
    checks = car.run_checks_for_frame(est, include_month=False, n_reps=15, seed=1)
    payload = {"version_tag": "synth_v1", "month": "synth",
               "input_path": "x.parquet", "meta_path": "m.parquet",
               "n_est": est.height, "checks": checks, "n_reps": 15, "seed": 1}
    md = car.render_month_report(payload)
    players = set(df["mover_player_hash"].to_list()) | set(df["black_player_hash"].to_list())
    assert not any(f"| {ph} " in md or f" {ph} |" in md for ph in players)
    assert "Clock Association Robustness" in md
