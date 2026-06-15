"""Tests for sharpness_interaction.py (Ticket 14.2B). No engine; synthetic frames."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc import sharpness_interaction as si
from chess_mhsuc import clock_association_robustness as car


def _frame(n=3000, seed=0, interaction=0.03):
    """Synthetic modeling frame with a known clock×sharp interaction effect."""
    rng = np.random.default_rng(seed)
    clock = rng.choice(["over_180", "60_180", "under_60"], n, p=[0.8, 0.12, 0.08])
    sharp = rng.integers(0, 2, n)
    es = (0.03 + 0.02 * (clock == "60_180") + 0.01 * sharp
          + interaction * ((clock == "60_180") & (sharp == 1))
          + rng.normal(0, 0.003, n))
    es = np.clip(es, 0, None)
    return pl.DataFrame({
        "expected_score_loss": es,
        "clipped_cp_loss": np.clip(np.abs(rng.normal(40, 60, n)), 0, 1000),
        "mover_pre_cp": rng.normal(0, 250, n),
        "mover_rating": rng.integers(800, 2200, n).astype(float),
        "clock_coarse": clock,
        "eval_band": rng.choice(["decided", "near_equal", "slight", "clear"], n),
        "selected_position_type": rng.choice(["move_10", "move_20", "move_30", "move_40"], n),
        "termination_binary": rng.choice(["board_decided", "time_forfeit"], n, p=[0.86, 0.14]),
        "month": rng.choice(["2024_09", "2024_10"], n),
        "split_set": rng.choice(["train", "val", "test"], n, p=[0.7, 0.15, 0.15]),
        "mover_player_hash": [f"p{rng.integers(0, 300)}" for _ in range(n)],
        "white_player_hash": [f"w{rng.integers(0, 300)}" for _ in range(n)],
        "black_player_hash": [f"b{rng.integers(0, 300)}" for _ in range(n)],
        "game_id": [f"g{i}" for i in range(n)],
        "large_loss_es_005": (es > 0.05).astype(int),
        "large_loss_es_010": (es > 0.10).astype(int),
        "sharp": sharp,
        "sharp_value_fragility_v1": sharp.astype(bool),
        "sharp_value_fragility_v1_relaxed": rng.integers(0, 2, n).astype(bool),
        "sharp_value_fragility_v1_strict": rng.integers(0, 2, n).astype(bool),
        "surface_bait_10es": rng.integers(0, 2, n).astype(bool),
        "n_good_10es": rng.integers(1, 6, n),
        "worst_top5_loss_es": rng.uniform(0, 0.3, n),
        "ctx_legal_move_count": rng.integers(1, 40, n),
    })


# ---- sharp recompute ----

def test_recompute_sharp_matches_definition():
    df = pl.DataFrame({"n_good_10es": [2, 3, 1], "worst_top5_loss_es": [0.12, 0.20, 0.05],
                       "ctx_legal_move_count": [10, 20, 30]})
    got = df.select(si.recompute_sharp_v1(df).alias("s"))["s"].to_list()
    assert got == [True, False, False]  # row1 sharp; row2 fails n_good; row3 fails loss


def test_recompute_requires_legal_ge_8():
    # narrow + steep drop-off but only 5 legal moves -> NOT sharp (clutter requirement)
    df = pl.DataFrame({"n_good_10es": [1], "worst_top5_loss_es": [0.5], "ctx_legal_move_count": [5]})
    assert df.select(si.recompute_sharp_v1(df).alias("s"))["s"].to_list() == [False]


# ---- primary universe ----

def test_primary_universe_filters_and_sharp_col():
    df = _frame(500, 1)
    df2, counts = si.primary_universe(df.with_columns(
        pl.when(pl.col("game_id") == "g0").then(None).otherwise(pl.col("eval_band")).alias("eval_band")))
    assert counts["dropped_null_eval_band"] == 1
    assert "sharp" in df2.columns
    assert df2["sharp"].dtype == pl.Int64


# ---- cell adequacy ----

def test_cell_adequacy_keys():
    df, _ = si.primary_universe(_frame(2000, 2))
    cells = si.cell_adequacy(df)
    assert "sharp_x_60_180" in cells and "under_60_sharp" in cells
    assert cells["sharp_x_60_180"] == cells.get("60_180_sharp1", 0)


# ---- design ----

def test_design_has_interaction_columns():
    df, _ = si.primary_universe(_frame(800, 3))
    m = car.fit_moments(df.filter(pl.col("split_set") != "test"))
    X, names = si.build_interaction_design(df, m, include_month=True, include_termination=True)
    assert "sharp" in names
    assert si.PRIMARY_INTERACTION in names  # clock=60_180:sharp
    assert si.SECONDARY_INTERACTION in names  # clock=under_60:sharp
    assert X.shape == (df.height, len(names))


def test_interaction_column_is_product():
    df, _ = si.primary_universe(_frame(600, 4))
    m = car.fit_moments(df.filter(pl.col("split_set") != "test"))
    X, names = si.build_interaction_design(df, m, include_month=False, include_termination=True)
    clk = X[:, names.index("clock=60_180")]
    shp = X[:, names.index("sharp")]
    inter = X[:, names.index(si.PRIMARY_INTERACTION)]
    assert np.allclose(inter, clk * shp)


# ---- DiD recovery ----

def test_did_interaction_recovered_positive():
    df, _ = si.primary_universe(_frame(8000, 5, interaction=0.03))
    m = car.fit_moments(df.filter(pl.col("split_set") != "test"))
    pt = si.point_interaction(df, m, include_month=True, include_termination=True)
    assert pt[si.PRIMARY_INTERACTION] > 0.015  # recovers the +0.03-ish interaction


def test_did_interaction_near_zero_when_absent():
    df, _ = si.primary_universe(_frame(8000, 6, interaction=0.0))
    m = car.fit_moments(df.filter(pl.col("split_set") != "test"))
    pt = si.point_interaction(df, m, include_month=True, include_termination=True)
    assert abs(pt[si.PRIMARY_INTERACTION]) < 0.01


# ---- fit + bootstrap ----

def test_fit_interaction_runs_and_bootstraps():
    df, _ = si.primary_universe(_frame(3000, 7, interaction=0.03))
    est = df.filter(pl.col("split_set").is_in(si.ESTIMATION))
    m = car.fit_moments(est)
    res = si.fit_interaction(est, m, target="expected_score_loss", model="ols",
                             include_month=False, include_termination=True,
                             rating_mode="linear", add_abs_cp=False, sharp_col="sharp",
                             cluster_col="mover_player_hash", n_reps=20, seed=42)
    assert res["primary"]["estimate"] > 0
    assert res["meta"]["n_clusters"] > 1


def test_fit_interaction_logistic_or_skip():
    df, _ = si.primary_universe(_frame(3000, 8))
    est = df.filter(pl.col("split_set").is_in(si.ESTIMATION))
    m = car.fit_moments(est)
    res = si.fit_interaction(est, m, target="large_loss_es_005", model="logistic",
                             include_month=False, include_termination=True,
                             rating_mode="linear", add_abs_cp=False, sharp_col="sharp",
                             cluster_col="mover_player_hash", n_reps=10, seed=1)
    assert "primary" in res or "skipped" in res


# ---- classification ----

def _month_stub(est09, pp_est, pp_cz, cell=400):
    pr = {"estimate": est09, "ci_lower": est09 - 0.01, "ci_upper": est09 + 0.01,
          "contains_zero": est09 - 0.01 <= 0 <= est09 + 0.01}
    return {"primary": {"primary": pr, "secondary": pr, "meta": {"n_clusters": 100, "n_rows": 1000}},
            "cells": {"sharp_x_60_180": cell, "under_60_sharp": 50}}


def test_classify_underpowered_small_cell():
    m1 = _month_stub(0.02, 0.02, False, cell=120)
    m2 = _month_stub(0.02, 0.02, False, cell=120)
    pooled = {"primary": {"primary": {"estimate": 0.02, "ci_lower": 0.01, "ci_upper": 0.03,
                                      "contains_zero": False}},
              "robustness": {"continuous_eval": {"primary": {"estimate": 0.02, "contains_zero": False}},
                             "board_decided_only": {"primary": {"estimate": 0.02, "contains_zero": False}}}}
    cls, _ = si.classify([m1, m2], pooled)
    assert cls == "underpowered_no_claim"


def test_classify_strong_support():
    m1 = _month_stub(0.02, 0.02, False, cell=400)
    m2 = _month_stub(0.018, 0.018, False, cell=400)
    pooled = {"primary": {"primary": {"estimate": 0.019, "ci_lower": 0.01, "ci_upper": 0.028,
                                      "contains_zero": False}},
              "robustness": {"continuous_eval": {"primary": {"estimate": 0.018, "contains_zero": False}},
                             "board_decided_only": {"primary": {"estimate": 0.017, "contains_zero": False}}}}
    cls, _ = si.classify([m1, m2], pooled)
    assert cls == "strong_support"


def test_classify_null():
    m1 = _month_stub(0.001, 0.001, True, cell=400)
    m2 = _month_stub(-0.002, -0.002, True, cell=400)
    pooled = {"primary": {"primary": {"estimate": 0.0, "ci_lower": -0.01, "ci_upper": 0.01,
                                      "contains_zero": True}},
              "robustness": {"continuous_eval": {"primary": {"estimate": 0.0, "contains_zero": True}},
                             "board_decided_only": {"primary": {"estimate": 0.0, "contains_zero": True}}}}
    cls, _ = si.classify([m1, m2], pooled)
    assert cls == "null_no_support"


# ---- report ordering + non-claims ----

def test_combined_report_primary_before_exploratory_and_nonclaims():
    df, _ = si.primary_universe(_frame(2500, 9, interaction=0.03))
    est = df.filter(pl.col("split_set").is_in(si.ESTIMATION))
    m = car.fit_moments(est)
    prim = si.fit_interaction(est, m, target="expected_score_loss", model="ols",
                              include_month=False, include_termination=True,
                              rating_mode="linear", add_abs_cp=False, sharp_col="sharp",
                              cluster_col="mover_player_hash", n_reps=10, seed=1)
    sb = si._fit_sharpcol(est, m, "surface_bait_10es", 10, 1)
    month = {"version_tag": "synth", "month": "synth", "validation": {
        "sharp_rows": 1, "sharp_keys_unique": True, "mf_rows": 1, "mf_keys_unique": True,
        "joined_rows": 1, "join_coverage": 1.0, "no_row_multiplication": True,
        "sharp_recompute_mismatches": 0},
        "exclusions": {}, "cells": si.cell_adequacy(est), "primary": prim,
        "test_confirmation": {si.PRIMARY_INTERACTION: 0.02},
        "robustness": {"surface_bait_exploratory": sb,
                       "continuous_eval": prim, "board_decided_only": prim},
        "n_est": est.height, "n_test": 0, "n_reps": 10, "seed": 1,
        "nml": "x", "sharp": "y", "players": "z"}
    pooled = {"cells": si.cell_adequacy(est), "primary": prim,
              "test_confirmation": {si.PRIMARY_INTERACTION: 0.02},
              "robustness": {"continuous_eval": prim, "board_decided_only": prim},
              "n_est": est.height, "n_test": 0}
    md = si.render_combined_report([month, month], pooled, "weak_suggestive", ["r"])
    assert md.index("## 7. Primary train+val results") < md.index("## 12. Exploratory")
    assert "NOT human obviousness" in md
    assert "not causal" in md.lower()


def test_cli_parses():
    with pytest.raises(SystemExit):
        si.main(["--help"])
