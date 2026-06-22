"""Tests for rating_clock_moderation.py (Ticket 16.2E). Pure logic + synthetic frames;
no Stockfish, no large data."""
from __future__ import annotations

import numpy as np
import polars as pl
import pytest

import chess_mhsuc.cross_time_control_analysis as ctc
import chess_mhsuc.rating_clock_moderation as r


def _artifact(control, month, n_games=40, plies=6, tf_games=(), draw_tf_games=()):
    tcr, init, sp = ctc.CONTROL_SPECS[control]
    # deterministic seed (NOT hash(), which is process-randomized) so phase/eval/clock
    # vary independently of ply and the design is reproducibly full-rank
    seed = (ctc.CONTROL_ORDER.index(control) * 10 + ctc.MONTH_ORDER.index(month) + 1)
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        is_tf = g in tf_games or g in draw_tf_games
        res = "DRAW" if g in draw_tf_games else ("WHITE_WIN" if g % 2 == 0 else "BLACK_WIN")
        for ply in range(1, plies + 1):
            cf = float(rng.uniform(0.01, 0.99))
            rows.append(dict(
                game_id=f"{control}_{month}_g{g}", month=month, ply=ply, move_number=ply + 5,
                mover_color="white" if ply % 2 == 1 else "black",
                mover_elo=1200 + g * 15 + ply, white_elo=1500 + g, black_elo=1480 - g,
                clock_before_s=init * cf, think_time_gross_s=1.0, time_control_raw=tcr,
                initial_time_s=init, increment_s=0, time_control_family="no_increment",
                speed_category=sp, clock_fraction=cf,
                expected_score_loss=0.02 + 0.01 * (ply % 3), cp_loss_raw=10, cp_loss_clipped=10 + ply,
                is_mate_band=False, status="ok",
                eval_band=str(rng.choice(["near_equal", "slight", "clear", "decided"])),
                phase=str(rng.choice(["opening", "middlegame", "endgame"])),
                termination="Time forfeit" if is_tf else "Normal", is_time_forfeit=is_tf,
                result_class=res, mover_player_hash=f"{control}_h{g}"))
    df = pl.DataFrame(rows)
    return df.with_columns([pl.lit(control).alias("control"), pl.lit(month).alias("month_expected")])


def _prepped(**kw):
    frames = [_artifact(c, mo, **kw) for c in ctc.CONTROL_ORDER for mo in ctc.MONTH_ORDER]
    df = pl.concat(frames, how="vertical_relaxed")
    h = ctc.build_headline_population(df)
    h = ctc.add_clock_fraction_buckets(h); h = ctc.add_anomaly_flags(h)
    h, cuts = ctc.assign_rating_quintiles(h); h = r.assign_rating_percentiles(h)
    return ctc.add_analysis_weights(h), cuts


# --- rating percentile ---
def test_percentile_bounded_and_oriented():
    h, _ = _prepped()
    assert h["rating_percentile"].min() >= -1e-9 and h["rating_percentile"].max() <= 1 + 1e-9
    # higher elo -> higher percentile within a stratum
    sub = h.filter((pl.col("control") == "3+0") & (pl.col("month") == "2024_09"))
    corr = np.corrcoef(sub["mover_elo"].to_numpy(), sub["rating_percentile"].to_numpy())[0, 1]
    assert corr > 0.9


def test_percentile_deterministic():
    h1, _ = _prepped(); h2, _ = _prepped()
    assert h1["rating_percentile"].to_list() == h2["rating_percentile"].to_list()


def test_percentile_ties_equal():
    # two movers same elo in a stratum -> same percentile (average rank)
    h, _ = _prepped()
    sub = h.select(["mover_elo", "rating_percentile", "control", "month"]).unique()
    g = sub.group_by(["control", "month", "mover_elo"]).agg(pl.col("rating_percentile").n_unique().alias("n"))
    assert g["n"].max() == 1


def test_percentile_within_stratum_not_leaked():
    h, _ = _prepped()
    # the max-elo row of each stratum should be percentile 1.0
    for (c, mo), sub in h.group_by(["control", "month"]):
        mx = sub.filter(pl.col("mover_elo") == sub["mover_elo"].max())
        assert abs(float(mx["rating_percentile"][0]) - 1.0) < 1e-9


# --- quintiles ---
def test_quintiles_levels_and_within_control():
    h, cuts = _prepped()
    assert set(h["rating_quintile"].unique().to_list()) <= set(r.QUINTILE_ORDER)
    assert set(cuts.keys()) == {(c, mo) for c in ctc.CONTROL_ORDER for mo in ctc.MONTH_ORDER}
    assert cuts[("3+0", "2024_09")] is not cuts[("10+0", "2024_09")]


# --- designs ---
def test_within_design_interaction_and_refs():
    h, _ = _prepped()
    X, names = r.build_within_control_interaction_design(h.filter(pl.col("control") == "3+0"))
    assert "clock=high" not in names and "rq=Q1" not in names  # refs dropped
    assert any(n == "clock=critical:rq=Q5" for n in names)     # M(c) term


def test_pooled_categorical_three_way_present():
    h, _ = _prepped()
    X, names = r.build_pooled_categorical_design(h)
    assert "tc=10+0" not in names                                  # ref TC dropped
    assert any(n == "tc=3+0:clock=critical:rq=Q5" for n in names)  # M(3+0)-M(10+0)
    assert any(n == "tc=5+0:clock=critical:rq=Q5" for n in names)
    assert np.linalg.matrix_rank(X) == X.shape[1]                  # full rank


def test_percentile_three_way_design():
    h, _ = _prepped()
    X, names = r.build_percentile_three_way_design(h)
    assert "rp" in names
    assert any(n == "tc=3+0:clock=critical:rp" for n in names)
    assert "tc=10+0:clock=critical:rp" not in names  # ref TC dropped
    assert np.linalg.matrix_rank(X) == X.shape[1]


# --- contrasts ---
def _toy_boot(names, point):
    full = np.array([point.get(n, 0.0) for n in names])
    boots = np.tile(full, (40, 1)) + np.random.default_rng(0).normal(0, 1e-6, (40, len(names)))
    return full, boots


def test_primary_five_contrasts_linear_reads():
    names = ["intercept", "clock=critical:rq=Q5", "tc=3+0:clock=critical:rq=Q5",
             "tc=5+0:clock=critical:rq=Q5"]
    full, boots = _toy_boot(names, {"clock=critical:rq=Q5": 0.01,
                                    "tc=3+0:clock=critical:rq=Q5": 0.008,
                                    "tc=5+0:clock=critical:rq=Q5": 0.003})
    c = r.primary_five_contrasts(full, boots, names)
    assert abs(c["M(10+0)"]["coef"] - 0.01) < 1e-4
    assert abs(c["M(3+0)"]["coef"] - 0.018) < 1e-4          # 0.01 + 0.008
    assert abs(c["M(5+0)"]["coef"] - 0.013) < 1e-4          # 0.01 + 0.003
    assert abs(c["M(3+0)-M(10+0)"]["coef"] - 0.008) < 1e-4
    assert abs(c["M(5+0)-M(10+0)"]["coef"] - 0.003) < 1e-4


def test_quintile_clock_contrasts():
    names = ["intercept", "clock=critical", "clock=critical:rq=Q5"]
    full, boots = _toy_boot(names, {"clock=critical": 0.005, "clock=critical:rq=Q5": 0.004})
    d = r.quintile_clock_contrasts(full, boots, names, True)
    assert abs(d["Q1"]["coef"] - 0.005) < 1e-4              # ref quintile
    assert abs(d["Q5"]["coef"] - 0.009) < 1e-4              # 0.005 + 0.004
    assert abs(d["M"]["coef"] - 0.004) < 1e-4


def test_missing_term_contributes_zero():
    names = ["intercept", "clock=critical:rq=Q5"]  # no tc three-way term
    full, boots = _toy_boot(names, {"clock=critical:rq=Q5": 0.01})
    c = r.primary_five_contrasts(full, boots, names)
    # the tc three-way term is absent -> cross-control contrast is undefined (None)
    assert c["M(3+0)-M(10+0)"] is None
    # M(10+0) is still defined (its term is present)
    assert abs(c["M(10+0)"]["coef"] - 0.01) < 1e-4


# --- Holm ---
def test_holm_ordering_and_bounds():
    adj = r.holm_adjust({"a": 0.01, "b": 0.04, "c": 0.5})
    assert adj["a"] == pytest.approx(0.03)   # *3
    assert adj["b"] == pytest.approx(0.08)   # *2
    assert adj["c"] == pytest.approx(0.5)    # *1
    assert all(0 <= v <= 1 for v in adj.values())


def test_holm_monotone_nondecreasing():
    adj = r.holm_adjust({"a": 0.02, "b": 0.02, "c": 0.0001, "d": 0.3, "e": 0.9})
    ordered = sorted(adj.items(), key=lambda kv: kv[1])
    vals = [v for _, v in ordered]
    assert vals == sorted(vals)


def test_holm_five_family_only():
    adj = r.holm_adjust({k: 0.01 for k in r.PRIMARY_TESTS})
    assert set(adj.keys()) == set(r.PRIMARY_TESTS)
    assert len(adj) == 5


# --- weighting (delegated to 16.2B but verify within this pipeline) ---
def test_weights_equal_game_and_stratum():
    h, _ = _prepped()
    gsum = h.group_by(["control", "month", "game_id"]).agg(pl.col("analysis_weight").sum().alias("w"))
    for (c, mo), sub in gsum.group_by(["control", "month"]):
        ws = sub["w"].to_numpy()
        assert np.allclose(ws, ws[0])
    ssum = h.group_by(["control", "month"]).agg(pl.col("analysis_weight").sum().alias("w"))["w"].to_numpy()
    assert np.allclose(ssum, ssum[0])
    assert (h["analysis_weight"] > 0).all()


# --- cluster bootstrap (mover-player across strata) ---
def test_cluster_bootstrap_player_across_strata():
    h, _ = _prepped()
    # same player hash appears across months within a control in the synthetic data
    X, names = r.build_within_control_interaction_design(h.filter(pl.col("control") == "3+0"))
    y = h.filter(pl.col("control") == "3+0")["expected_score_loss"].to_numpy().astype(float)
    cl = h.filter(pl.col("control") == "3+0")["mover_player_hash"].to_list()
    full, boots, meta = ctc.weighted_cluster_bootstrap(X, y, cl, 30, 1)
    assert boots.shape[0] <= 30 and meta["n_clusters"] >= 2


# --- board-decided / endgame designs ---
def test_board_decided_design_drops_termination():
    h, _ = _prepped(tf_games=(1, 2))
    bd = h.filter((pl.col("control") == "5+0") & (pl.col("termination_channel") == "board_decided"))
    X, names = r.build_within_control_interaction_design(bd, include_termination=False)
    assert not any(n.startswith("termination=") for n in names)


def test_endgame_filter_excludes_other_phases():
    h, _ = _prepped()
    eg = h.filter(pl.col("phase") == "endgame")
    assert set(eg["phase"].unique().to_list()) == {"endgame"}


# --- player-side termination attribution ---
def test_player_side_two_rows_and_loser_flagged():
    # decisive TF game g=0 (WHITE_WIN -> black flagged); draw-TF g=1 excluded
    h, _ = _prepped(tf_games=(0,), draw_tf_games=(1,))
    val = r.validate_player_side_termination_attribution(h)
    assert val["ambiguous_draw_timeout_excluded"] >= 1
    pst = r.build_player_side_termination_table(h)
    # exactly two rows per non-excluded game
    per_game = pst.group_by(["control", "month", "game_id"]).len()
    assert per_game["len"].max() == 2 and per_game["len"].min() == 2
    # in a WHITE_WIN time-forfeit game the black side has forfeit==1, white==0
    g0 = pst.filter(pl.col("game_id") == "3+0_2024_09_g0")
    fw = g0.filter(pl.col("player_color") == "white")["did_player_forfeit_on_time"][0]
    fb = g0.filter(pl.col("player_color") == "black")["did_player_forfeit_on_time"][0]
    assert fw == 0 and fb == 1


def test_player_side_draw_timeout_excluded():
    h, _ = _prepped(draw_tf_games=(3,))
    pst = r.build_player_side_termination_table(h)
    assert pst.filter(pl.col("game_id") == "3+0_2024_09_g3").height == 0  # excluded


def test_player_side_no_username_columns():
    h, _ = _prepped(tf_games=(0,))
    pst = r.build_player_side_termination_table(h)
    assert not (r._FORBIDDEN_USERNAME_COLS & set(pst.columns))
    assert "player_hash" in pst.columns


# --- validate_rating_fields ---
def test_validate_rating_fields_clean():
    h, _ = _prepped()
    assert r.validate_rating_fields(h)["issues"] == []


# --- player-side denominator proof ---
def test_player_side_denominator_includes_nonforfeit_zeros():
    h, _ = _prepped(tf_games=(0,), draw_tf_games=(1,))
    d = r.player_side_denominator(h)
    # player rows == 2 * eligible games (eligible excludes ambiguous draw-timeout)
    assert d["rows_eq_2x_eligible"]
    assert d["player_rows"] == 2 * d["eligible_games"]
    # positives == decisive TF games; zeros include all non-forfeit eligible sides
    assert d["positives"] >= 1 and d["zeros"] > d["positives"]
    assert d["ambiguous_excluded"] >= 1
    # prevalence is positives / all player rows (NOT positives / TF games); 4dp rounded
    assert abs(d["overall_prevalence"] - d["positives"] / d["player_rows"]) < 1e-3


# --- percentile -> Elo landmarks ---
def test_percentile_elo_landmarks_ordered():
    h, _ = _prepped()
    lm = r.percentile_elo_landmarks(h)
    d = lm[("3+0", "2024_09")]["landmarks"]
    assert d[0.10] <= d[0.25] <= d[0.50] <= d[0.75] <= d[0.90]
    assert set(lm[("3+0", "2024_09")]["quintiles"].keys()) <= set(r.QUINTILE_ORDER)


# --- raw Elo bins ---
def test_raw_elo_bin_table_within_control():
    h, _ = _prepped()
    t = r.raw_elo_bin_table(h)
    assert set(t["control"].unique().to_list()) == set(ctc.CONTROL_ORDER)
    assert set(t["elo_bin"].unique().to_list()) <= set(r._RAW_ELO_BINS)
    # counts are non-negative; sparse flag is boolean
    assert (t["rows"] >= 0).all()


# --- robustness matrix executes the required specs ---
def test_robustness_matrix_executes_required_specs():
    h, _ = _prepped()
    rob = r.run_robustness_matrix(h, 20, 1)
    for spec in ["R5", "R6", "R7", "R10", "R11", "R12_competitive", "R12_decided"]:
        assert spec in rob and rob[spec]["executed"]
        assert "M(3+0)" in rob[spec]["res"]["contrasts"]
