"""Tests for dense_constraint_atlas.py (Ticket 15.4B). Pure functions + a tiny
synthetic end-to-end; no real artifacts, no Stockfish, no models."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.dense_constraint_atlas import (
    EXPECTED_ROWS,
    REQUIRED_COLS,
    add_buckets,
    bootstrap_mean_ci,
    cell_status,
    cell_summary,
    clock_coarse_bucket,
    clock_fraction_bucket,
    clock_seconds_bucket,
    filter_headline,
    main as atlas_main,
    phase_move_bucket,
    rating_bucket_200,
    think_bucket,
    validate_schema,
)


# ---------------------------------------------------------------------------
# Bucket helpers
# ---------------------------------------------------------------------------

def test_clock_seconds_bucket():
    assert clock_seconds_bucket(0) == "0_5"
    assert clock_seconds_bucket(7) == "5_10"
    assert clock_seconds_bucket(29) == "10_30"
    assert clock_seconds_bucket(59) == "30_60"
    assert clock_seconds_bucket(120) == "60_180"
    assert clock_seconds_bucket(250) == "180_300"
    assert clock_seconds_bucket(599) == "300+"
    assert clock_seconds_bucket(None) is None


def test_clock_coarse_bucket():
    assert clock_coarse_bucket(5) == "under_10"
    assert clock_coarse_bucket(20) == "10_30"
    assert clock_coarse_bucket(120) == "60_180"
    assert clock_coarse_bucket(400) == "over_180"
    assert clock_coarse_bucket(None) is None


def test_clock_fraction_bucket():
    assert clock_fraction_bucket(0.005) == "0_1"   # 0.5%
    assert clock_fraction_bucket(0.03) == "2_5"    # 3%
    assert clock_fraction_bucket(0.2) == "10_30"   # 20%
    assert clock_fraction_bucket(0.9) == "50+"
    assert clock_fraction_bucket(None) is None


def test_rating_bucket_200():
    assert rating_bucket_200(900) == "<1000"
    assert rating_bucket_200(1000) == "1000_1199"
    assert rating_bucket_200(1650) == "1600_1799"
    assert rating_bucket_200(2200) == "2200+"
    assert rating_bucket_200(2850) == "2200+"
    assert rating_bucket_200(None) is None


def test_phase_move_bucket():
    assert phase_move_bucket(5) == "5_10"
    assert phase_move_bucket(15) == "11_20"
    assert phase_move_bucket(40) == "31_40"
    assert phase_move_bucket(80) == "61+"
    assert phase_move_bucket(None) is None


def test_think_bucket():
    assert think_bucket(0.5) == "0_1"
    assert think_bucket(3) == "2_5"
    assert think_bucket(45) == "30+"
    assert think_bucket(-1) is None      # negative anomaly
    assert think_bucket(None) is None


def test_cell_status():
    assert cell_status(50) == "sparse"
    assert cell_status(500) == "marked"
    assert cell_status(5000) == "headline"


# ---------------------------------------------------------------------------
# Synthetic dense frame
# ---------------------------------------------------------------------------

def _synthetic_dense(n_per_month: int = 400, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for month, cnt in (("2024_09", n_per_month), ("2024_10", n_per_month)):
        for i in range(cnt):
            white = (i % 2 == 0)
            clock = float(rng.choice([3, 8, 20, 45, 120, 250, 480]))
            es = float(abs(rng.normal(0.03, 0.02)))
            rows.append({
                "month": month,
                "game_id": f"{month}_g{i // 4}",   # ~4 rows/game -> clusters
                "ply": 10 + i % 50,
                "move_number": 5 + i % 40,
                "mover_color": "white" if white else "black",
                "mover_elo": int(rng.choice([950, 1100, 1500, 1700, 1900, 2300])),
                "clock_before_s": clock,
                "think_time_gross_s": float(rng.choice([0.5, 3, 8, 25, -1.0])),
                "think_time_net_s": 0.0,
                "time_control_raw": "600+0",
                "initial_time_s": 600,
                "increment_s": 0,
                "speed_category": "rapid",
                "clock_fraction": clock / 600.0,
                "expected_score_loss": min(es, 0.8),
                "cp_loss_raw": int(rng.integers(-50, 300)),
                "cp_loss_clipped": int(abs(rng.integers(0, 300))),
                "is_mate_band": (i % 50 == 0),
                "status": "ok",
                "eval_band": rng.choice(["near_equal", "slight", "clear", "decided"]),
                "phase": "middlegame",
                "termination": "Normal" if i % 7 else "Time forfeit",
                "is_time_forfeit": (i % 7 == 0),
                "mover_player_hash": f"h{i % 30}",
            })
    return pl.DataFrame(rows)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validate_schema_accepts_minimal_valid_frame():
    df = _synthetic_dense()
    val = validate_schema(df, check_counts=False)
    assert val["rows"] == df.height
    assert set(val["months"]) == {"2024_09", "2024_10"}


def test_validate_schema_rejects_username_columns():
    df = _synthetic_dense().with_columns(pl.lit("bob").alias("white"))
    with pytest.raises(ValueError, match="username"):
        validate_schema(df, check_counts=False)


def test_validate_schema_rejects_missing_columns():
    df = _synthetic_dense().drop("expected_score_loss")
    with pytest.raises(ValueError, match="missing required columns"):
        validate_schema(df, check_counts=False)


def test_validate_schema_rejects_non_600_0():
    df = _synthetic_dense().with_columns(pl.lit("180+2").alias("time_control_raw"))
    with pytest.raises(ValueError, match="600"):
        validate_schema(df, check_counts=False)


def test_validate_schema_count_check_fails_on_synthetic():
    # synthetic counts do not match the real EXPECTED_ROWS -> count check must fail
    df = _synthetic_dense()
    with pytest.raises(ValueError, match="row count mismatch"):
        validate_schema(df, check_counts=True)
    assert EXPECTED_ROWS["2024_09"] == 1_496_890


# ---------------------------------------------------------------------------
# Filtering + aggregation
# ---------------------------------------------------------------------------

def test_filter_headline_excludes_mate_band_keeps_both_colors():
    df = add_buckets(_synthetic_dense())
    head = filter_headline(df)
    assert head.filter(pl.col("is_mate_band")).height == 0
    assert set(head["mover_color"].unique().to_list()) == {"white", "black"}
    assert (head["status"] == "ok").all()


def test_cell_summary_has_quantiles_and_large_loss():
    df = add_buckets(filter_headline(_synthetic_dense()))
    summ = cell_summary(df, ["month", "clock_sec_bucket"])
    for c in ["n", "es_mean", "es_median", "es_p75", "es_p90",
              "cp_median", "cp_p75", "cp_p90",
              "p_es_ge_05", "p_es_ge_10", "p_cp_ge_100", "p_cp_ge_200",
              "cell_status"]:
        assert c in summ.columns
    # large-loss rates are probabilities in [0,1]
    assert summ["p_es_ge_05"].min() >= 0.0 and summ["p_es_ge_05"].max() <= 1.0


def test_bootstrap_mean_ci_orders_and_brackets():
    df = filter_headline(_synthetic_dense())
    est, lo, hi = bootstrap_mean_ci(df, "expected_score_loss", n_rep=200, seed=1)
    assert lo <= est <= hi
    assert 0.0 <= est <= 1.0


def test_bootstrap_mean_ci_single_cluster_returns_nan_ci():
    df = pl.DataFrame({"game_id": ["g", "g", "g"],
                       "expected_score_loss": [0.1, 0.2, 0.3]})
    est, lo, hi = bootstrap_mean_ci(df, "expected_score_loss", n_rep=50)
    assert abs(est - 0.2) < 1e-9
    assert np.isnan(lo) and np.isnan(hi)


# ---------------------------------------------------------------------------
# End-to-end CLI on synthetic parquet (figures + report manifest)
# ---------------------------------------------------------------------------

def test_cli_generates_figures_and_report(tmp_path):
    df = _synthetic_dense(n_per_month=400, seed=3)
    p1 = tmp_path / "dm_2024_09.parquet"
    p2 = tmp_path / "dm_2024_10.parquet"
    df.filter(pl.col("month") == "2024_09").write_parquet(p1)
    df.filter(pl.col("month") == "2024_10").write_parquet(p2)
    out_dir = tmp_path / "figs"
    report = tmp_path / "atlas.md"
    rc = atlas_main([
        "--dense-month", str(p1), "--dense-month", str(p2),
        "--out-dir", str(out_dir), "--report", str(report),
        "--bootstrap", "50", "--seed", "7", "--no-count-check",
    ])
    assert rc == 0
    figs = sorted(f.name for f in out_dir.glob("*.png"))
    assert len(figs) == 9
    assert "fig_15_4_01_clock_vs_es_loss_by_month.png" in figs
    text = report.read_text()
    assert "CP / ES Constraint Atlas" in text
    assert "Month replication summary" in text
    assert "not causal" in text
    # figure manifest references all 9 figures
    for f in figs:
        assert f in text


def test_cli_refuses_missing_required_columns(tmp_path):
    df = _synthetic_dense(n_per_month=50).drop("clock_before_s")
    p = tmp_path / "bad.parquet"
    df.write_parquet(p)
    with pytest.raises(ValueError, match="missing required columns"):
        atlas_main([
            "--dense-month", str(p),
            "--out-dir", str(tmp_path / "figs"),
            "--report", str(tmp_path / "r.md"),
            "--bootstrap", "10", "--no-count-check",
        ])
