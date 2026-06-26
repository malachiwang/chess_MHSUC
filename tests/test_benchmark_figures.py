"""Tests for benchmark_figures.py (Ticket 17.0B). Pure helpers on synthetic frames;
no Stockfish, no large data, no figure I/O beyond a tmp smoke check of naming."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

import chess_mhsuc.cross_time_control_analysis as ctc
import chess_mhsuc.benchmark_figures as bf


# --- actual-second bins ---
def test_actual_second_edges_span_and_count():
    e = bf.actual_second_edges(180, 18)
    assert e[0] == 0.0 and e[-1] == 180.0 and len(e) == 19


def test_actual_second_edges_rejects_bad():
    with pytest.raises(ValueError):
        bf.actual_second_edges(0, 18)
    with pytest.raises(ValueError):
        bf.actual_second_edges(180, 0)


@pytest.mark.parametrize("s,init,exp", [
    (0, 180, 0), (179.9, 180, 17), (180, 180, 17),       # top clamp
    (90, 180, 9), (300, 180, 17),                         # >initial clamps into top bin
    (None, 180, None),
])
def test_assign_second_bin_clamps(s, init, exp):
    assert bf.assign_second_bin(s, init, 18) == exp


# --- move-number bins ---
def test_move_number_edges():
    e = bf.move_number_edges(80, 5)
    assert e[0] == 5 and e[-1] == 80 and all(b - a == 5 for a, b in zip(e, e[1:]))


def test_move_number_edges_rejects_bad():
    with pytest.raises(ValueError):
        bf.move_number_edges(80, 0)


# --- sparse Elo collapse ---
def test_collapse_sparse_leading_and_trailing_tails():
    counts = {"<1200": 50, "1200-1399": 300, "1400-1599": 5000, "1600-1799": 4000,
              "1800-1999": 3000, "2000-2199": 800, "2200+": 30}
    kept, remap = bf.collapse_sparse_elo_bins(counts, min_count=200)
    # leading <1200 (50<200) merges into next adequate (1200-1399, 300>=200)
    assert remap["<1200"] == "1200-1399"
    # trailing 2200+ (30<200) merges into last adequate (2000-2199, 800>=200)
    assert remap["2200+"] == "2000-2199"
    assert "<1200" not in kept and "2200+" not in kept
    assert kept[0] == "1200-1399" and kept[-1] == "2000-2199"


def test_collapse_deterministic():
    counts = {"1400-1599": 5000, "1600-1799": 4000}
    assert bf.collapse_sparse_elo_bins(counts, 200) == bf.collapse_sparse_elo_bins(counts, 200)


def test_collapse_empty():
    assert bf.collapse_sparse_elo_bins({}, 200) == ([], {})


# --- figure naming ---
def test_figure_name_deterministic_and_png():
    assert bf.figure_name("H1_x") == "H1_x.png"
    assert bf.figure_name("H1_x.png") == "H1_x.png"


def test_figure_name_rejects_path_sep():
    with pytest.raises(ValueError):
        bf.figure_name("a/b")
    with pytest.raises(ValueError):
        bf.figure_name(" lead")


# --- synthetic frame + aggregation/heatmap/privacy ---
def _synth():
    rng = np.random.default_rng(0)
    rows = []
    for control, (tcr, init, sp) in ctc.CONTROL_SPECS.items():
        for mo in ctc.MONTH_ORDER:
            for g in range(30):
                tf = g % 5 == 0
                for ply in range(1, 9):
                    cf = float(rng.uniform(0.01, 0.99))
                    rows.append(dict(
                        game_id=f"{control}_{mo}_g{g}", month=mo, ply=ply, move_number=ply + 5,
                        mover_color="white" if ply % 2 else "black",
                        mover_elo=1100 + g * 30 + ply, white_elo=1500, black_elo=1480,
                        clock_before_s=init * cf, think_time_gross_s=1.0, time_control_raw=tcr,
                        initial_time_s=init, increment_s=0, time_control_family="no_increment",
                        speed_category=sp, clock_fraction=cf,
                        expected_score_loss=0.02 + 0.01 * (ply % 3), cp_loss_raw=10,
                        cp_loss_clipped=10 + ply, is_mate_band=False, status="ok",
                        eval_band=["near_equal", "slight", "clear", "decided"][ply % 4],
                        phase=["opening", "middlegame", "endgame"][ply % 3],
                        termination="Time forfeit" if tf else "Normal", is_time_forfeit=tf,
                        result_class="WHITE_WIN" if g % 2 else "BLACK_WIN",
                        mover_player_hash=f"{control}_h{g}"))
    df = pl.DataFrame(rows)
    return df.with_columns([pl.lit(control).alias("control") if False else pl.col("month").alias("control")]) \
        if False else df


def _prepped():
    df = _synth()
    # tag control/month like load_all_artifacts does
    parts = []
    for control in ctc.CONTROL_ORDER:
        tcr = ctc.CONTROL_SPECS[control][0]
        parts.append(df.filter(pl.col("time_control_raw") == tcr).with_columns([
            pl.lit(control).alias("control"), pl.col("month").alias("month_expected")]))
    d = pl.concat(parts, how="vertical_relaxed")
    h = ctc.build_headline_population(d)
    h = ctc.add_clock_fraction_buckets(h)
    h = ctc.add_anomaly_flags(h)
    h, _ = ctc.assign_rating_quintiles(h)
    return bf.add_raw_elo_bin(h)


def _wprepped():
    """Prepped + game-normalized analysis_weight (the production pipeline order)."""
    return bf.add_raw_elo_bin(ctc.add_analysis_weights(_prepped().drop("elo_bin")))


def test_add_actual_second_bin_within_range():
    h = bf.add_actual_second_bin(_prepped(), n_bins=18)
    assert (h["sec_bin"] >= 0).all() and (h["sec_bin"] <= 17).all()
    # midpoint within [0, initial] for each control
    for c in ctc.CONTROL_ORDER:
        init = ctc.CONTROL_SPECS[c][1]
        s = h.filter(pl.col("control") == c)
        assert s["sec_bin_mid"].min() >= 0 and s["sec_bin_mid"].max() <= init


def test_aggregate_all_vs_board_decided_has_both_populations():
    h = bf.add_actual_second_bin(_wprepped(), n_bins=18)
    agg = bf.aggregate_all_vs_board_decided(h, "sec_bin_mid")
    assert set(agg["population"].unique().to_list()) == {"all", "board_decided"}
    # board-decided rows <= all rows per control-bin
    a = agg.filter(pl.col("population") == "all")["rows"].sum()
    b = agg.filter(pl.col("population") == "board_decided")["rows"].sum()
    assert b < a
    # the plotted es_mean is the GAME-NORMALIZED weighted mean (not the raw row mean)
    assert "es_mean" in agg.columns and "es_mean_raw" in agg.columns


# --- game-normalized weighting (regression for the blocking estimand fix) ---
def test_weighted_mean_helper_matches_formula():
    v = np.array([0.0, 0.1, 0.2]); w = np.array([1.0, 1.0, 2.0])
    assert bf.weighted_mean(v, w) == pytest.approx((0.0 + 0.1 + 0.4) / 4.0)
    assert np.isnan(bf.weighted_mean(np.array([]), np.array([])))


def test_weighted_mean_expr_equals_numpy():
    h = _wprepped()
    sub = h.filter(pl.col("control") == "3+0")
    got = sub.select(bf.weighted_mean_expr("expected_score_loss", "analysis_weight")).item()
    exp = bf.weighted_mean(sub["expected_score_loss"].to_numpy(), sub["analysis_weight"].to_numpy())
    assert got == pytest.approx(exp)


def test_weighted_differs_from_raw_when_game_lengths_differ():
    # one long game (many moves, low loss) + several short games (high loss); the
    # game-normalized mean must differ from the raw row mean (long game down-weighted)
    rows = []
    for ply in range(1, 41):  # long game, 40 moves, loss 0.01
        rows.append(dict(game_id="long", expected_score_loss=0.01, _moves=40))
    for g in range(8):        # 8 short games, 2 moves each, loss 0.06
        for ply in range(2):
            rows.append(dict(game_id=f"short{g}", expected_score_loss=0.06, _moves=2))
    df = pl.DataFrame(rows)
    # game-normalized weight = 1/(games_in_stratum * moves_in_game), then mean-scaled
    df = df.with_columns((1.0 / (pl.col("game_id").n_unique() * pl.col("_moves"))).alias("_w"))
    df = df.with_columns((pl.col("_w") / pl.col("_w").mean()).alias("analysis_weight"))
    raw = float(df["expected_score_loss"].mean())
    wtd = df.select(bf.weighted_mean_expr("expected_score_loss", "analysis_weight")).item()
    assert abs(raw - wtd) > 1e-4               # they genuinely differ
    assert wtd > raw                            # short high-loss games up-weighted


def test_heatmap_masks_sparse_cells():
    h = _wprepped()
    M, secs, mns, C, G = bf.heatmap_cells(h, "3+0", n_sec_bins=18, min_count=1000000, min_games=1)
    # with an impossibly high row threshold every cell is masked
    assert np.isnan(M).all()
    M2, _, _, C2, G2 = bf.heatmap_cells(h, "3+0", n_sec_bins=6, min_count=1, min_games=1)
    assert (~np.isnan(M2)).sum() >= 1 and C2.sum() > 0
    assert G2.shape == M2.shape


def test_heatmap_min_games_threshold_masks_few_game_cells():
    # a cell powered by rows from very few games must be masked by min_games even if rows pass
    h = _wprepped()
    M_lo, _, _, C, G = bf.heatmap_cells(h, "3+0", n_sec_bins=6, min_count=1, min_games=1)
    M_hi, _, _, _, _ = bf.heatmap_cells(h, "3+0", n_sec_bins=6, min_count=1, min_games=10**9)
    # impossibly high game threshold masks everything; low threshold shows cells
    assert np.isnan(M_hi).all() and (~np.isnan(M_lo)).sum() >= 1
    # every displayed cell has games >= the threshold
    M_t, _, _, C_t, G_t = bf.heatmap_cells(h, "3+0", n_sec_bins=6, min_count=1, min_games=3)
    shown = ~np.isnan(M_t)
    assert (G_t[shown] >= 3).all()


def test_game_level_prevalence_matches_synth():
    h = _prepped()
    gt = ctc.build_game_level_table(h)
    prev = bf.game_level_termination_prevalence(gt)
    assert set(prev["control"].unique().to_list()) == set(ctc.CONTROL_ORDER)
    assert (prev["pr_time_forfeit"] >= 0).all() and (prev["pr_time_forfeit"] <= 1).all()


def test_validate_no_usernames_raises():
    h = _prepped().with_columns(pl.lit("alice").alias("white"))
    with pytest.raises(ValueError, match="username"):
        bf.validate_no_usernames(h)


def test_validate_no_usernames_ok():
    bf.validate_no_usernames(_prepped())  # no raise


def test_elo_bin_counts_and_collapse_integration():
    h = bf.add_actual_second_bin(_prepped(), n_bins=18)
    counts = bf.elo_bin_counts(h, "10+0")
    assert all(set(["rows", "games", "movers", "lo", "hi"]) <= set(v.keys()) for v in counts.values())
    gc = {b: counts[b]["games"] for b in counts}
    kept, remap = bf.collapse_sparse_elo_bins(gc, bf.SPARSE_MIN_GAMES)
    assert all(k in bf.RAW_ELO_LABELS for k in kept)
