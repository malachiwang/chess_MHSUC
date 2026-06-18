"""Tests for dense_controlled_model.py (Ticket 15.4D). Pure functions + tiny synthetic
frames; no real artifacts, no Stockfish."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.dense_controlled_model import (
    CLOCK_CONTRASTS,
    EXPECTED_ROWS,
    FOCAL,
    REQUIRED_COLS,
    add_model_columns,
    build_design,
    denominators,
    filter_headline,
    fit_ols_contrasts,
    load_dense,
    main as cm_main,
    ols_cluster_bootstrap,
    ols_fit,
    validate_schema,
)


def _synthetic(n_per_month: int = 600, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    clocks = [3, 8, 20, 45, 120, 250, 480]
    bands = ["near_equal", "slight", "clear", "decided"]
    for month, cnt in (("2024_09", n_per_month), ("2024_10", n_per_month)):
        for i in range(cnt):
            clock = float(rng.choice(clocks))
            band = bands[i % 4]
            es = float(min(abs(rng.normal(0.03, 0.02)), 0.8))
            rows.append({
                "month": month,
                "game_id": f"{month}_g{i // 3}",
                "ply": 10 + i % 60,
                "move_number": 5 + i % 50,
                "mover_color": "white" if i % 2 == 0 else "black",
                "mover_elo": int(rng.choice([950, 1100, 1500, 1700, 1900, 2300])),
                "clock_before_s": clock,
                "think_time_gross_s": float(rng.choice([0.5, 3, 8, 25, -1.0])),
                "expected_score_loss": es,
                "expected_score_before": float(rng.uniform(0.1, 0.9)),
                "eval_before_cp": int(rng.integers(-400, 400)),
                "cp_loss_clipped": int(abs(rng.integers(0, 300))),
                "cp_loss_raw": int(rng.integers(-50, 300)),
                "is_mate_band": (i % 50 == 0),
                "status": "ok",
                "eval_band": band,
                "phase": ["opening", "middlegame", "endgame"][i % 3],
                "termination": "Normal" if i % 7 else "Time forfeit",
                "is_time_forfeit": (i % 7 == 0),
                "mover_player_hash": f"h{i % 40}",
            })
    return pl.DataFrame(rows)


# --- validator ---

def test_validate_accepts_minimal():
    v = validate_schema(_synthetic(), check_counts=False)
    assert set(v["months"]) == {"2024_09", "2024_10"}
    assert v["has_player_hash"] is True


def test_validate_rejects_usernames():
    df = _synthetic().with_columns(pl.lit("bob").alias("white"))
    with pytest.raises(ValueError, match="username"):
        validate_schema(df, check_counts=False)


def test_validate_rejects_missing_cols():
    df = _synthetic().drop("expected_score_loss")
    with pytest.raises(ValueError, match="missing required columns"):
        validate_schema(df, check_counts=False)


def test_validate_count_check_fails_on_synthetic():
    with pytest.raises(ValueError, match="row count mismatch"):
        validate_schema(_synthetic(), check_counts=True)
    assert EXPECTED_ROWS["2024_10"] == 1_436_866


# --- filtering / buckets ---

def test_filter_headline_excludes_mate_band_keeps_colors():
    df = add_model_columns(_synthetic())
    h = filter_headline(df)
    assert h.filter(pl.col("is_mate_band")).height == 0
    assert set(h["mover_color"].unique().to_list()) == {"white", "black"}


def test_add_model_columns_derives_expected():
    df = add_model_columns(_synthetic())
    assert set(df["clock_coarse"].unique().to_list()) <= {
        "under_10", "10_30", "30_60", "60_180", "over_180"}
    assert set(df["termination_channel"].unique().to_list()) == {
        "board_decided", "time_forfeit"}
    assert df["clock_anom"].max() in (0.0, 1.0)


def test_denominators_counts_anomalies():
    d = denominators(_synthetic())
    assert "2024_09" in d and "negative_think" in d["2024_09"]


# --- design matrix + OLS ---

def test_build_design_reference_levels_omitted():
    df = add_model_columns(_synthetic())
    X, names = build_design(filter_headline(df))
    # reference levels must NOT appear as columns
    assert "clock=over_180" not in names
    assert "eval=decided" not in names
    assert "termination=board_decided" not in names
    # focal + intercept present
    assert "intercept" in names
    assert FOCAL in names
    assert X.shape[0] == filter_headline(df).height
    assert X.shape[1] == len(names)


def test_ols_recovers_known_coefficients():
    rng = np.random.default_rng(1)
    n = 4000
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 0.7 + 2.0 * x1 - 1.5 * x2 + rng.normal(scale=0.01, size=n)
    X = np.column_stack([np.ones(n), x1, x2])
    beta = ols_fit(X, y)
    assert abs(beta[0] - 0.7) < 0.02
    assert abs(beta[1] - 2.0) < 0.02
    assert abs(beta[2] + 1.5) < 0.02


def test_cluster_bootstrap_full_matches_lstsq_and_brackets():
    rng = np.random.default_rng(2)
    n = 3000
    x = rng.normal(size=n)
    y = 0.2 + 1.3 * x + rng.normal(scale=0.1, size=n)
    X = np.column_stack([np.ones(n), x])
    clusters = [f"g{i // 5}" for i in range(n)]
    full, boot, meta = ols_cluster_bootstrap(X, y, clusters, n_reps=100, seed=3)
    direct = ols_fit(X, y)
    assert np.allclose(full, direct, atol=1e-8)         # full == lstsq
    assert meta["n_success"] >= 90
    lo, hi = np.percentile(boot[:, 1], [2.5, 97.5])
    assert lo <= full[1] <= hi


def test_cluster_bootstrap_too_few_clusters_raises():
    X = np.column_stack([np.ones(3), np.arange(3.0)])
    y = np.array([0.1, 0.2, 0.3])
    with pytest.raises(ValueError, match="too few clusters"):
        ols_cluster_bootstrap(X, y, ["g", "g", "g"], n_reps=10, seed=0)


def test_fit_ols_contrasts_returns_clock_contrasts():
    df = filter_headline(add_model_columns(_synthetic(n_per_month=900, seed=5)))
    res = fit_ols_contrasts(df, "expected_score_loss", CLOCK_CONTRASTS,
                            "game_id", n_reps=60, seed=7)
    assert "clock 60_180 vs over_180" in res["contrasts"]
    d = res["contrasts"]["clock 60_180 vs over_180"]
    assert "estimate" in d and "ci_lower" in d


def test_large_loss_target_construction():
    df = filter_headline(add_model_columns(_synthetic()))
    df = df.with_columns((pl.col("expected_score_loss") >= 0.10).cast(pl.Float64).alias("es_ge_10"))
    assert set(df["es_ge_10"].unique().to_list()) <= {0.0, 1.0}


def test_board_decided_and_month_splits():
    df = filter_headline(add_model_columns(_synthetic()))
    bd = df.filter(~pl.col("is_time_forfeit"))
    assert bd.filter(pl.col("is_time_forfeit")).height == 0
    m9 = df.filter(pl.col("month") == "2024_09")
    assert set(m9["month"].unique().to_list()) == {"2024_09"}


# --- end-to-end CLI ---

def test_cli_end_to_end(tmp_path):
    df = _synthetic(n_per_month=1500, seed=9)
    p1 = tmp_path / "dm09.parquet"
    p2 = tmp_path / "dm10.parquet"
    df.filter(pl.col("month") == "2024_09").write_parquet(p1)
    df.filter(pl.col("month") == "2024_10").write_parquet(p2)
    report = tmp_path / "model.md"
    rc = cm_main([
        "--dense-month", str(p1), "--dense-month", str(p2),
        "--report", str(report), "--bootstrap", "40", "--seed", "11",
        "--no-count-check",
    ])
    assert rc == 0
    text = report.read_text()
    assert "Controlled Dense Move-Quality Model" in text
    assert "Clock coefficient table" in text
    assert "positive-control" in text
    assert "not causal" in text.lower()
    # no forbidden causal phrasing
    assert "low clock causes blunders" not in text.lower().replace('no "low clock causes blunders"', "")


def test_cli_refuses_missing_columns(tmp_path):
    df = _synthetic(n_per_month=80).drop("clock_before_s")
    p = tmp_path / "bad.parquet"
    df.write_parquet(p)
    with pytest.raises(ValueError, match="missing required columns"):
        cm_main(["--dense-month", str(p), "--report", str(tmp_path / "r.md"),
                 "--bootstrap", "10", "--no-count-check"])
