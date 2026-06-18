"""Tests for sharpness_enriched_atlas.py (Ticket 15.5B). Pure functions + tiny synthetic
frames; no real artifacts, no Stockfish/MultiPV."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.sharpness_enriched_atlas import (
    DENSE_EXPECTED_ROWS,
    FOCAL_INTERACTION,
    MODEL_CONTRASTS,
    add_columns,
    build_design,
    cell_status,
    fit_model,
    filter_headline,
    join_checkpoint_overlap,
    main as sea_main,
    sharp_clock_cells,
    validate_dense,
    validate_join,
    validate_sharpness,
)


def _dense(n_per_month=900, seed=0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for month, cnt in (("2024_09", n_per_month), ("2024_10", n_per_month)):
        for i in range(cnt):
            clock = float(rng.choice([3, 8, 20, 45, 120, 250, 480]))
            rows.append({
                "month": month, "game_id": f"{month}_g{i // 4}", "ply": 1 + i % 80,
                "move_number": 5 + i % 40, "mover_color": "white" if i % 2 == 0 else "black",
                "mover_elo": int(rng.choice([950, 1100, 1500, 1700, 1900, 2300])),
                "clock_before_s": clock, "think_time_gross_s": float(rng.choice([0.5, 3, 8, -1.0])),
                "expected_score_loss": float(min(abs(rng.normal(0.03, 0.02)), 0.8)),
                "expected_score_before": float(rng.uniform(0.1, 0.9)),
                "cp_loss_clipped": int(abs(rng.integers(0, 300))),
                "cp_loss_raw": int(rng.integers(-50, 300)),
                "is_mate_band": (i % 60 == 0), "status": "ok",
                "eval_band": ["near_equal", "slight", "clear", "decided"][i % 4],
                "phase": ["opening", "middlegame", "endgame"][i % 3],
                "termination": "Normal" if i % 7 else "Time forfeit",
                "is_time_forfeit": (i % 7 == 0), "mover_player_hash": f"h{i % 40}",
            })
    return pl.DataFrame(rows)


def _sharp(dense: pl.DataFrame, seed=1) -> pl.DataFrame:
    # build sharpness rows at checkpoint_ply = (white dense ply) - 1 so the corrected
    # join (ply == checkpoint_ply+1) matches White-mover dense rows.
    rng = np.random.default_rng(seed)
    w = dense.filter(pl.col("mover_color") == "white")
    rows = []
    for r in w.iter_rows(named=True):
        rows.append({
            "game_id": r["game_id"], "checkpoint_ply": r["ply"] - 1,
            "selected_position_type": "move_x", "side_to_move": "white", "status": "ok",
            "is_mate_band": False,
            "sharp_value_fragility_v1": int(rng.random() < 0.15),
            "sharp_value_fragility_v1_relaxed": 0, "sharp_value_fragility_v1_strict": 0,
            "best_second_gap_es": float(rng.uniform(0, 0.2)), "n_good_10es": int(rng.integers(1, 6)),
            "worst_top5_loss_es": float(rng.uniform(0, 0.3)), "legal_move_count": int(rng.integers(8, 40)),
            "depth": 12, "multipv_k": 5,
        })
    return pl.DataFrame(rows)


# --- validators ---

def test_validate_dense_accepts_and_counts_flag():
    v = validate_dense(_dense(), check_counts=False)
    assert set(v["per_month"]) == {"2024_09", "2024_10"}
    with pytest.raises(ValueError, match="row count mismatch"):
        validate_dense(_dense(), check_counts=True)
    assert DENSE_EXPECTED_ROWS["2024_09"] == 1_496_890


def test_validate_dense_rejects_usernames():
    df = _dense().with_columns(pl.lit("bob").alias("white"))
    with pytest.raises(ValueError, match="username"):
        validate_dense(df, check_counts=False)


def test_validate_sharpness_requires_white_stm():
    sh = _sharp(_dense())
    v = validate_sharpness(sh, None, check_counts=False)
    assert v["side_to_move"] == ["white"]
    bad = sh.with_columns(pl.lit("black").alias("side_to_move"))
    with pytest.raises(ValueError, match="White only"):
        validate_sharpness(bad, None, check_counts=False)


# --- join semantics ---

def test_corrected_join_is_white_only():
    d = _dense(); s = _sharp(d)
    j = join_checkpoint_overlap(d, s)
    assert j.height > 0
    assert set(j["mover_color"].unique().to_list()) == {"white"}
    validate_join(j)  # must not raise


def test_wrong_equal_ply_join_would_match_black():
    # demonstrate the trap: joining on ply==checkpoint_ply matches Black movers and
    # validate_join must reject it.
    d = _dense(); s = _sharp(d)
    sk = (s.filter(pl.col("status") == "ok")
          .select(["game_id", "checkpoint_ply", "sharp_value_fragility_v1"])
          .rename({"checkpoint_ply": "ply"}))
    wrong = d.join(sk, on=["game_id", "ply"], how="inner")
    # the wrong join matches the Black move INTO the checkpoint
    assert "black" in set(wrong["mover_color"].unique().to_list())
    with pytest.raises(ValueError, match="White-mover only"):
        validate_join(wrong)


def test_validate_join_rejects_black_contamination():
    d = _dense(); s = _sharp(d)
    j = join_checkpoint_overlap(d, s).with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(pl.lit("black"))
        .otherwise(pl.col("mover_color")).alias("mover_color"))
    with pytest.raises(ValueError):
        validate_join(j)


# --- filtering / buckets / cells ---

def test_filter_headline_excludes_mate_band():
    j = add_columns(join_checkpoint_overlap(_dense(), _sharp(_dense())))
    h = filter_headline(j)
    assert h.filter(pl.col("is_mate_band")).height == 0


def test_add_columns_sharp_label():
    j = add_columns(join_checkpoint_overlap(_dense(), _sharp(_dense())))
    assert set(j["sharp_label"].unique().to_list()) <= {"sharp", "non_sharp"}
    assert set(j["clock_coarse"].unique().to_list()) <= {
        "under_10", "10_30", "30_60", "60_180", "over_180"}


def test_cell_status_policy():
    assert cell_status(50) == "sparse"
    assert cell_status(500) == "exploratory"
    assert cell_status(5000) == "headline"


def test_sharp_clock_cells_has_metrics():
    h = filter_headline(add_columns(join_checkpoint_overlap(_dense(), _sharp(_dense()))))
    c = sharp_clock_cells(h, ["sharp_label", "clock_coarse"])
    for col in ["n", "es_mean", "cp_median", "p_es_ge_10", "cell"]:
        assert col in c.columns


# --- design / model ---

def test_design_omits_mover_color_and_has_interaction():
    h = filter_headline(add_columns(join_checkpoint_overlap(_dense(), _sharp(_dense()))))
    X, names = build_design(h)
    assert not any(n.startswith("color=") for n in names)  # mover_color omitted
    assert "sharp" in names
    assert any(n.endswith(":sharp") for n in names)        # interaction present
    assert X.shape[1] == len(names)


def test_fit_model_extracts_focal_interaction():
    h = filter_headline(add_columns(join_checkpoint_overlap(_dense(2000, 4), _sharp(_dense(2000, 4), 4))))
    res = fit_model(h, "expected_score_loss", MODEL_CONTRASTS, "game_id", n_reps=40, seed=5)
    # focal interaction should be among extracted contrasts (if column survived constant-drop)
    assert "sharp main effect (at over_180)" in res["contrasts"]


# --- end-to-end CLI ---

def test_cli_end_to_end(tmp_path):
    d = _dense(2500, 7); s = _sharp(d, 7)
    dp1 = tmp_path / "d09.parquet"; dp2 = tmp_path / "d10.parquet"
    sp1 = tmp_path / "s09.parquet"; sp2 = tmp_path / "s10.parquet"
    d.filter(pl.col("month") == "2024_09").write_parquet(dp1)
    d.filter(pl.col("month") == "2024_10").write_parquet(dp2)
    # sharpness needs game_id present per month; split by game_id prefix
    s.join(d.select(["game_id", "month"]).unique(), on="game_id", how="left").filter(
        pl.col("month") == "2024_09").drop("month").write_parquet(sp1)
    s.join(d.select(["game_id", "month"]).unique(), on="game_id", how="left").filter(
        pl.col("month") == "2024_10").drop("month").write_parquet(sp2)
    out_dir = tmp_path / "figs"; report = tmp_path / "atlas.md"
    rc = sea_main([
        "--dense-month", str(dp1), "--dense-month", str(dp2),
        "--sharpness-month", str(sp1), "--sharpness-month", str(sp2),
        "--out-dir", str(out_dir), "--report", str(report),
        "--bootstrap", "30", "--seed", "9", "--no-count-check",
    ])
    assert rc == 0
    figs = sorted(f.name for f in out_dir.glob("*.png"))
    assert len(figs) == 6
    text = report.read_text()
    assert "checkpoint-overlap" in text.lower()
    assert "White-mover only" in text
    assert "not causal" in text.lower()
    assert "C3c" in text


def test_cli_refuses_missing_dense_columns(tmp_path):
    d = _dense(100).drop("expected_score_loss")
    s = _sharp(_dense(100))
    dp = tmp_path / "d.parquet"; sp = tmp_path / "s.parquet"
    d.write_parquet(dp); s.write_parquet(sp)
    with pytest.raises(ValueError, match="missing required columns"):
        sea_main(["--dense-month", str(dp), "--sharpness-month", str(sp),
                  "--out-dir", str(tmp_path / "f"), "--report", str(tmp_path / "r.md"),
                  "--bootstrap", "10", "--no-count-check"])
