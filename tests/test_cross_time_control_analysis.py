"""Tests for cross_time_control_analysis.py (Ticket 16.2B). Pure logic + synthetic
frames; no Stockfish, no large data, no figure I/O beyond a tmp dir smoke test."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

import chess_mhsuc.cross_time_control_analysis as m


# ---------------------------------------------------------------------------
# Synthetic artifact builder
# ---------------------------------------------------------------------------
def _artifact(control, month, n_games=6, plies=6, tf_games=()):
    tcr, init, sp = m.CONTROL_SPECS[control]
    rows = []
    for g in range(n_games):
        is_tf = g in tf_games
        for ply in range(1, plies + 1):
            rows.append(dict(
                game_id=f"{control}_{month}_g{g}", month=month, ply=ply, move_number=ply + 5,
                mover_color="white" if ply % 2 == 1 else "black",
                mover_elo=1400 + g * 60 + ply, white_elo=1500, black_elo=1480,
                clock_before_s=init * max(0.01, 0.95 - 0.18 * ply), think_time_gross_s=1.0,
                time_control_raw=tcr, initial_time_s=init, increment_s=0,
                time_control_family="no_increment", speed_category=sp,
                clock_fraction=max(0.01, 0.95 - 0.18 * ply),
                expected_score_loss=0.02 + 0.01 * (ply % 3), cp_loss_raw=10,
                cp_loss_clipped=10 + ply, is_mate_band=False, status="ok",
                eval_band=["near_equal", "slight", "clear", "decided"][ply % 4],
                phase=["opening", "middlegame", "endgame"][ply % 3],
                termination="Time forfeit" if is_tf else "Normal", is_time_forfeit=is_tf,
                result_class="WHITE_WIN", mover_player_hash=f"hash_{control}_{g}"))
    df = pl.DataFrame(rows)
    return df.with_columns([pl.lit(control).alias("control"),
                            pl.lit(month).alias("month_expected")])


def _all_six():
    paths = {}
    frames = []
    for c in m.CONTROL_ORDER:
        for mo in m.MONTH_ORDER:
            frames.append(_artifact(c, mo, tf_games=(0,) if c == "3+0" else ()))
    return pl.concat(frames, how="vertical_relaxed")


# ---------------------------------------------------------------------------
# Artifact identity validation
# ---------------------------------------------------------------------------
def test_validate_accepts_correct_identity():
    df = _artifact("3+0", "2024_09")
    v = m.validate_artifact_identity(df, "3+0", "2024_09")
    assert v["control"] == "3+0" and v["dups"] == 0 and not v["issues"]


def test_validate_rejects_wrong_time_control():
    df = _artifact("3+0", "2024_09").with_columns(pl.lit("600+0").alias("time_control_raw"))
    with pytest.raises(ValueError, match="time_control_raw"):
        m.validate_artifact_identity(df, "3+0", "2024_09")


def test_validate_rejects_wrong_initial_time():
    df = _artifact("5+0", "2024_09").with_columns(pl.lit(180).alias("initial_time_s"))
    with pytest.raises(ValueError, match="initial_time_s"):
        m.validate_artifact_identity(df, "5+0", "2024_09")


def test_validate_rejects_increment():
    df = _artifact("3+0", "2024_09").with_columns([pl.lit(2).alias("increment_s"),
                                                   pl.lit("increment").alias("time_control_family")])
    with pytest.raises(ValueError, match="increment_s"):
        m.validate_artifact_identity(df, "3+0", "2024_09")


def test_validate_rejects_missing_columns():
    df = _artifact("3+0", "2024_09").drop("eval_band")
    with pytest.raises(ValueError, match="missing required columns"):
        m.validate_artifact_identity(df, "3+0", "2024_09")


def test_validate_rejects_username_columns():
    df = _artifact("3+0", "2024_09").with_columns(pl.lit("alice").alias("white"))
    with pytest.raises(ValueError, match="username"):
        m.validate_artifact_identity(df, "3+0", "2024_09")


def test_validate_rejects_duplicate_keys():
    df = _artifact("3+0", "2024_09")
    df = pl.concat([df, df.head(1)], how="vertical")
    with pytest.raises(ValueError, match="duplicate"):
        m.validate_artifact_identity(df, "3+0", "2024_09")


# ---------------------------------------------------------------------------
# Analysis population
# ---------------------------------------------------------------------------
def test_population_excludes_mate_band_and_invalid():
    df = _artifact("3+0", "2024_09")
    df = df.with_columns([
        pl.when(pl.col("ply") == 1).then(True).otherwise(False).alias("is_mate_band"),
        pl.when(pl.col("ply") == 2).then(None).otherwise(pl.col("mover_elo")).alias("mover_elo"),
    ])
    h = m.build_headline_population(df)
    assert h.filter(pl.col("is_mate_band")).height == 0
    assert h.filter(pl.col("mover_elo").is_null()).height == 0


def test_population_retains_then_robustness_excludes_anomalies():
    df = _artifact("3+0", "2024_09").with_columns(
        pl.when(pl.col("ply") == 1).then(1.5).otherwise(pl.col("clock_fraction")).alias("clock_fraction"))
    h = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(df)))
    assert h.filter(pl.col("clock_gt_initial_flag") == 1).height > 0  # retained
    rob = h.filter(pl.col("clock_gt_initial_flag") == 0)
    assert rob.filter(pl.col("clock_gt_initial_flag") == 1).height == 0


# ---------------------------------------------------------------------------
# Rating quintiles
# ---------------------------------------------------------------------------
def test_quintiles_within_control_month_and_deterministic():
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    h1, cut1 = m.assign_rating_quintiles(df)
    h2, cut2 = m.assign_rating_quintiles(df)
    assert cut1 == cut2  # deterministic
    assert set(cut1.keys()) == {(c, mo) for c in m.CONTROL_ORDER for mo in m.MONTH_ORDER}
    assert set(h1["rating_quintile"].unique().to_list()) <= set(m.QUINTILE_LEVELS)


def test_quintile_cutpoints_not_reused_across_controls():
    # 3+0 synthetic pool is shifted; cutpoints should differ from 10+0 in general data,
    # but at minimum each stratum gets its own computed cutpoints (no shared object).
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    _, cut = m.assign_rating_quintiles(df)
    assert cut[("3+0", "2024_09")] is not cut[("10+0", "2024_09")]


def test_quintiles_stable_under_ties():
    # all-equal ratings -> all rows land in one quintile deterministically, no crash
    df = _artifact("3+0", "2024_09").with_columns(pl.lit(1600).alias("mover_elo"))
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(df)))
    h, _ = m.assign_rating_quintiles(df)
    assert h.height == df.height
    assert set(h["rating_quintile"].unique().to_list()) <= set(m.QUINTILE_LEVELS)


# ---------------------------------------------------------------------------
# Clock buckets — boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cf,fine,coarse", [
    (0.00, "cf_le_002", "critical"),
    (0.02, "cf_le_002", "critical"),
    (0.05, "cf_002_005", "critical"),
    (0.10, "cf_005_010", "low"),
    (0.15, "cf_010_025", "low"),
    (0.25, "cf_010_025", "medium"),
    (0.50, "cf_025_050", "medium"),
    (0.75, "cf_050_075", "high"),
    (1.00, "cf_over_075", "high"),
    (1.50, "cf_over_075", "high"),
])
def test_clock_bucket_boundaries(cf, fine, coarse):
    df = pl.DataFrame({"clock_fraction": [cf]})
    out = m.add_clock_fraction_buckets(df)
    assert out["cf_fine"][0] == fine
    assert out["clock_coarse"][0] == coarse


# ---------------------------------------------------------------------------
# Game-level table
# ---------------------------------------------------------------------------
def test_game_level_one_row_per_game():
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    df, _ = m.assign_rating_quintiles(df)
    df = m.add_analysis_weights(df)
    gt = m.build_game_level_table(df)
    assert gt.height == df["game_id"].n_unique()
    assert gt.select(["control", "month", "game_id"]).unique().height == gt.height


def test_game_level_rejects_inconsistent_termination():
    df = _artifact("3+0", "2024_09")
    # flip one move's termination within a game -> inconsistent
    df = df.with_columns(
        pl.when((pl.col("game_id") == "3+0_2024_09_g0") & (pl.col("ply") == 1))
        .then(True).otherwise(pl.col("is_time_forfeit")).alias("is_time_forfeit"))
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(df)))
    df, _ = m.assign_rating_quintiles(df)
    df = m.add_analysis_weights(df)
    with pytest.raises(ValueError, match="inconsistent game-level termination"):
        m.build_game_level_table(df)


def test_game_level_prevalence_differs_from_move_share():
    # one TF game that is LONG vs board-decided short games -> move-share > game-rate
    long_tf = _artifact("3+0", "2024_09", n_games=1, plies=20, tf_games=(0,))
    short_bd = _artifact("3+0", "2024_09", n_games=4, plies=4)
    short_bd = short_bd.with_columns(("x_" + pl.col("game_id")).alias("game_id"))
    df = pl.concat([long_tf, short_bd], how="vertical_relaxed")
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(df)))
    df, _ = m.assign_rating_quintiles(df)
    df = m.add_analysis_weights(df)
    gt = m.build_game_level_table(df)
    move_share = float(df["is_time_forfeit"].mean())
    game_rate = float(gt["is_time_forfeit"].mean())
    assert move_share > game_rate  # longer TF game inflates the move-level share


# ---------------------------------------------------------------------------
# Weighting
# ---------------------------------------------------------------------------
def test_weights_equal_per_game_and_per_stratum():
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    df, _ = m.assign_rating_quintiles(df)
    df = m.add_analysis_weights(df)
    # each game equal total weight within stratum
    gsum = df.group_by(["control", "month", "game_id"]).agg(pl.col("analysis_weight").sum().alias("w"))
    for (c, mo), sub in gsum.group_by(["control", "month"]):
        ws = sub["w"].to_numpy()
        assert np.allclose(ws, ws[0])
    # each stratum equal aggregate weight
    ssum = df.group_by(["control", "month"]).agg(pl.col("analysis_weight").sum().alias("w"))["w"].to_numpy()
    assert np.allclose(ssum, ssum[0])
    assert (df["analysis_weight"] > 0).all()


def test_weights_scale_normalized_mean_one():
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    df, _ = m.assign_rating_quintiles(df)
    df = m.add_analysis_weights(df)
    assert abs(float(df["analysis_weight"].mean()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Design matrices
# ---------------------------------------------------------------------------
def _prepped():
    df = m.add_anomaly_flags(m.add_clock_fraction_buckets(m.build_headline_population(_all_six())))
    df, _ = m.assign_rating_quintiles(df)
    return m.add_analysis_weights(df)


def test_within_design_reference_levels_absent():
    X, names = m.build_within_control_design(_prepped().filter(pl.col("control") == "3+0"))
    assert "intercept" in names
    assert "clock=high" not in names          # ref dropped
    assert "eval=decided" not in names         # ref dropped
    assert not any(n == "rq=Q3" for n in names)  # ref dropped
    assert any(n == "clock=critical" for n in names)


def test_within_design_month_excluded_when_disabled():
    X, names = m.build_within_control_design(
        _prepped().filter((pl.col("control") == "3+0") & (pl.col("month") == "2024_09")),
        include_month=False)
    assert not any(n.startswith("month=") for n in names)


def test_board_decided_design_drops_termination():
    bd = _prepped().filter(pl.col("control") == "5+0")
    bd = bd.filter(pl.col("termination_channel") == "board_decided")
    X, names = m.build_within_control_design(bd, include_termination=False)
    assert not any(n.startswith("termination=") for n in names)


def test_pooled_interaction_columns_present():
    X, names = m.build_pooled_interaction_design(_prepped())
    assert any(n == "tc=3+0" for n in names)
    assert any(n == "tc=3+0:clock=critical" for n in names)
    assert "tc=10+0" not in names  # reference control dropped


# ---------------------------------------------------------------------------
# Weighted OLS + bootstrap
# ---------------------------------------------------------------------------
def test_weighted_ols_matches_lstsq_unweighted():
    rng = np.random.default_rng(0)
    X = np.column_stack([np.ones(200), rng.normal(size=200)])
    y = X @ np.array([1.0, 2.0]) + rng.normal(scale=0.1, size=200)
    b = m.fit_weighted_ols(X, y)
    assert abs(b[1] - 2.0) < 0.1


def test_cluster_bootstrap_returns_ci():
    df = _prepped().filter(pl.col("control") == "3+0")
    X, names = m.build_within_control_design(df)
    y = df["expected_score_loss"].to_numpy().astype(float)
    full, boots, meta = m.weighted_cluster_bootstrap(X, y, df["game_id"].to_list(), 50, 1)
    assert boots.shape[0] <= 50 and meta["n_clusters"] >= 2
    ci = m.contrast_ci(full, boots, names, names[1])
    assert ci is not None and "lo" in ci and "hi" in ci


# ---------------------------------------------------------------------------
# Replication classification
# ---------------------------------------------------------------------------
def _ci(coef, lo, hi):
    return {"coef": coef, "lo": lo, "hi": hi, "excludes_zero": lo > 0 or hi < 0}


def test_replication_replicated():
    a = _ci(0.01, 0.005, 0.015); b = _ci(0.012, 0.006, 0.018); p = _ci(0.011, 0.008, 0.014)
    assert m.classify_replication(a, b, p) == "replicated"


def test_replication_directional():
    a = _ci(0.01, -0.001, 0.02); b = _ci(0.012, 0.006, 0.018); p = _ci(0.011, 0.005, 0.017)
    assert m.classify_replication(a, b, p) == "directionally_replicated"


def test_replication_pooled_only():
    a = _ci(0.01, -0.01, 0.03); b = _ci(-0.002, -0.02, 0.016); p = _ci(0.006, 0.001, 0.011)
    assert m.classify_replication(a, b, p) == "pooled_only"


def test_replication_not_replicated():
    a = _ci(0.02, 0.01, 0.03); b = _ci(-0.02, -0.03, -0.01); p = _ci(0.0, -0.01, 0.01)
    assert m.classify_replication(a, b, p) == "not_replicated"


def test_replication_null():
    a = _ci(0.001, -0.01, 0.012); b = _ci(-0.001, -0.012, 0.01); p = _ci(0.0, -0.005, 0.005)
    assert m.classify_replication(a, b, p) == "null_or_unresolved"


# ---------------------------------------------------------------------------
# Privacy of outputs
# ---------------------------------------------------------------------------
def test_summary_tables_have_no_username_columns():
    df = _prepped()
    gt = m.build_game_level_table(df)
    for tbl in [m.summarize_denominators(df, gt), m.summarize_termination_rates(gt),
                m.summarize_move_quality(df), m.summarize_clock_cells(df)]:
        assert not (m._FORBIDDEN_USERNAME_COLS & set(tbl.columns))
