"""Tests for termination_decomposition.py (Ticket 11.2B). Pure functions +
synthetic frames only; no real data artifacts required."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.termination_decomposition import (
    CHANNEL_ORDER,
    DEFAULT_MIN_GAMES_FOR_CI,
    LATE_CHECKPOINTS,
    LATE_CLOCK_ORDER,
    MODEL_A,
    MODEL_B,
    attach_and_validate,
    classify_channel,
    composition_tables,
    compute_group_results,
    compute_late_clock_results,
    is_board_decided,
    load_termination_keys,
    render_report,
    retained_fraction,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures: 12 games x 2 checkpoints (move_10, move_40), val only
# ---------------------------------------------------------------------------

_N = 12


def _gid(i: int) -> str:
    return f"g{i:02d}"


def _term(i: int) -> str:
    # games 0-2 time forfeit; 3 rules infraction; rest Normal
    if i < 3:
        return "Time forfeit"
    if i == 3:
        return "Rules infraction"
    return "Normal"


def _result(i: int) -> str:
    # one Normal draw (i=4); others decisive
    if i == 4:
        return "DRAW"
    return "WHITE_WIN" if i % 2 == 0 else "BLACK_WIN"


def make_feature_df() -> pl.DataFrame:
    rows = []
    for i in range(_N):
        for cpt in ("move_10", "move_40", "last"):
            clk = 30.0 if (cpt == "move_40" and i % 3 == 0) else 400.0
            rows.append({
                "game_id": _gid(i),
                "selected_position_type": cpt,
                "termination": _term(i),
                "is_time_forfeit": _term(i) == "Time forfeit",
                "result_class": _result(i),
                "white_clock_s_capped": clk,
                "black_clock_s_capped": clk + 5.0,
            })
    return pl.DataFrame(rows)


def make_val_preds() -> pl.DataFrame:
    frames = []
    base = []
    for i in range(_N):
        for cpt in ("move_10", "move_40"):
            base.append({
                "game_id": _gid(i),
                "selected_position_type": cpt,
                "result_class": _result(i),
            })
    b = pl.DataFrame(base)
    for mid, pw in ((MODEL_A, 0.45), (MODEL_B, 0.55)):
        frames.append(b.with_columns([
            pl.lit(mid).alias("model_id"),
            pl.lit("val").alias("split_set"),
            pl.lit(0.30).alias("p_BLACK_WIN"),
            pl.lit(round(0.70 - pw, 10)).alias("p_DRAW"),
            pl.lit(pw).alias("p_WHITE_WIN"),
        ]))
    return pl.concat(frames).select(
        ["model_id", "split_set", "game_id", "selected_position_type",
         "result_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]
    )


@pytest.fixture
def keys():
    return load_termination_keys_from_df(make_feature_df())


def load_termination_keys_from_df(df: pl.DataFrame, tmp_path=None):
    # helper: route through the real loader via a temp parquet
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "f.parquet"
        df.write_parquet(p)
        return load_termination_keys(p)


@pytest.fixture
def preds_with_keys(keys):
    return attach_and_validate(make_val_preds(), keys)


# ---------------------------------------------------------------------------
# 1. Channel mapping (pure)
# ---------------------------------------------------------------------------

class TestClassifyChannel:
    def test_time_forfeit(self):
        assert classify_channel("Time forfeit", "WHITE_WIN") == "time_forfeit"
        assert classify_channel("Time forfeit", "DRAW") == "time_forfeit"

    def test_normal_decisive(self):
        assert classify_channel("Normal", "WHITE_WIN") == "normal_decisive"
        assert classify_channel("Normal", "BLACK_WIN") == "normal_decisive"

    def test_normal_draw(self):
        assert classify_channel("Normal", "DRAW") == "normal_draw"

    def test_rules_infraction(self):
        assert classify_channel("Rules infraction", "WHITE_WIN") == \
            "rules_infraction_or_other"

    def test_unknown_value_maps_to_other(self):
        assert classify_channel("Weird", "DRAW") == "rules_infraction_or_other"

    def test_channel_order_constant(self):
        assert CHANNEL_ORDER == [
            "time_forfeit", "normal_decisive", "normal_draw",
            "rules_infraction_or_other",
        ]


class TestBoardDecided:
    def test_time_forfeit_false(self):
        assert is_board_decided("Time forfeit") is False

    def test_normal_true(self):
        assert is_board_decided("Normal") is True

    def test_rules_infraction_true(self):
        assert is_board_decided("Rules infraction") is True


# ---------------------------------------------------------------------------
# 2. Keys loading / channel derivation on frames
# ---------------------------------------------------------------------------

class TestLoadKeys:
    def test_primary_view_only(self, keys):
        assert "last" not in keys["selected_position_type"].unique().to_list()
        assert len(keys) == _N * 2

    def test_channels_derived(self, keys):
        ch = keys.filter(pl.col("game_id") == "g04")["channel"].unique().to_list()
        assert ch == ["normal_draw"]
        ch_tf = keys.filter(pl.col("game_id") == "g00")["channel"].unique().to_list()
        assert ch_tf == ["time_forfeit"]

    def test_board_decided_inverse_of_tf(self, keys):
        assert (keys["board_decided"] == ~keys["is_time_forfeit"]).all()

    def test_late_clock_only_late_checkpoints(self, keys):
        early = keys.filter(pl.col("selected_position_type") == "move_10")
        assert early["late_clock_bucket"].null_count() == len(early)
        late = keys.filter(pl.col("selected_position_type") == "move_40")
        assert late["late_clock_bucket"].null_count() == 0

    def test_null_termination_raises(self):
        df = make_feature_df().with_columns(
            pl.when(pl.col("game_id") == "g00").then(None)
            .otherwise(pl.col("termination")).alias("termination"))
        with pytest.raises(ValueError, match="null termination"):
            load_termination_keys_from_df(df)

    def test_duplicate_key_raises(self):
        df = pl.concat([make_feature_df(), make_feature_df().head(1)])
        with pytest.raises(ValueError, match="not unique"):
            load_termination_keys_from_df(df)


# ---------------------------------------------------------------------------
# 3. Join validation
# ---------------------------------------------------------------------------

class TestAttachAndValidate:
    def test_clean_join(self, preds_with_keys):
        assert preds_with_keys["termination"].null_count() == 0
        assert len(preds_with_keys) == _N * 2 * 2  # 2 models

    def test_missing_keys_raise(self, keys):
        short = keys.head(len(keys) - 2)
        with pytest.raises(ValueError, match="no termination after join"):
            attach_and_validate(make_val_preds(), short)

    def test_duplicate_keys_raise(self, keys):
        dup = pl.concat([keys, keys.head(1)])
        with pytest.raises(ValueError, match="duplicate"):
            attach_and_validate(make_val_preds(), dup)


# ---------------------------------------------------------------------------
# 4. Retained fraction (pure)
# ---------------------------------------------------------------------------

class TestRetainedFraction:
    def test_normal_case(self):
        r = retained_fraction(-0.006, -0.012)
        assert r["fraction"] == pytest.approx(0.5)
        assert r["note"] is None

    def test_sign_insensitive(self):
        r = retained_fraction(0.006, -0.012)
        assert r["fraction"] == pytest.approx(0.5)

    def test_near_zero_denominator(self):
        r = retained_fraction(-0.006, -0.0005)
        assert r["fraction"] is None
        assert "near zero" in r["note"]

    def test_exact_zero_denominator(self):
        r = retained_fraction(0.0, 0.0)
        assert r["fraction"] is None

    def test_sign_flip_flagged(self):
        r = retained_fraction(0.006, -0.012)
        assert r["sign_flipped"] is True
        assert "OPPOSITE sign" in r["note"]

    def test_no_flip_when_same_sign(self):
        r = retained_fraction(-0.006, -0.012)
        assert r["sign_flipped"] is False
        assert r["note"] is None

    def test_tiny_bd_delta_not_flagged_as_flip(self):
        r = retained_fraction(0.0001, -0.012)
        assert r["sign_flipped"] is False


# ---------------------------------------------------------------------------
# 5. Group deltas on synthetic predictions
# ---------------------------------------------------------------------------

class TestGroupResults:
    def test_delta_sign_convention(self, preds_with_keys):
        # E4 puts more mass on WHITE_WIN; majority of synthetic labels are
        # decisive with WHITE_WIN for even i -> verify sign = ll(E4)-ll(E3)
        res = compute_group_results(preds_with_keys, n_replicates=5, seed=42,
                                    min_games_for_ci=4)
        r = res["all_games"]
        assert r["point_delta"] == pytest.approx(
            r["log_loss_e4"] - r["log_loss_e3"], abs=1e-12)

    def test_groups_present(self, preds_with_keys):
        res = compute_group_results(preds_with_keys, 5, 42, 4)
        for k in ("all_games", "board_decided", "time_forfeit",
                  "channel_normal_decisive", "channel_normal_draw",
                  "channel_rules_infraction_or_other"):
            assert k in res, k

    def test_partition_counts(self, preds_with_keys):
        res = compute_group_results(preds_with_keys, 5, 42, 4)
        assert (res["board_decided"]["n_rows"] + res["time_forfeit"]["n_rows"]
                == res["all_games"]["n_rows"])
        assert res["time_forfeit"]["n_games"] == 3  # games 0-2

    def test_threshold_behavior(self, preds_with_keys):
        res = compute_group_results(preds_with_keys, 5, 42,
                                    min_games_for_ci=10_000)
        assert res["all_games"]["ci_lower"] is None
        assert res["all_games"]["note"] == "below min game threshold"
        assert res["all_games"]["point_delta"] is not None

    def test_deterministic(self, preds_with_keys):
        r1 = compute_group_results(preds_with_keys, 20, 42, 4)
        r2 = compute_group_results(preds_with_keys, 20, 42, 4)
        assert r1 == r2


class TestLateClock:
    def test_structure(self, preds_with_keys):
        lc = compute_late_clock_results(preds_with_keys, 5, 42, 2)
        assert set(lc) == {"all_games", "board_decided"}
        for label in lc:
            assert set(lc[label]) == set(LATE_CLOCK_ORDER)

    def test_board_decided_subset_smaller(self, preds_with_keys):
        lc = compute_late_clock_results(preds_with_keys, 5, 42, 2)
        for bucket in LATE_CLOCK_ORDER:
            a = lc["all_games"][bucket].get("n_rows", 0)
            b = lc["board_decided"][bucket].get("n_rows", 0)
            assert b <= a


# ---------------------------------------------------------------------------
# 6. Composition + report
# ---------------------------------------------------------------------------

def _payload(preds_with_keys, keys):
    g = compute_group_results(preds_with_keys, 5, 42, 4)
    return {
        "dataset_id": "synthetic_ds",
        "version_tag": "synthetic_v1",
        "group_results": g,
        "late_clock_results": compute_late_clock_results(
            preds_with_keys, 5, 42, 2),
        "composition": composition_tables(keys, preds_with_keys, None),
        "retained_fraction": retained_fraction(
            g["board_decided"]["point_delta"], g["all_games"]["point_delta"]),
        "join_summary": {"n_val_rows_per_model": _N * 2},
        "artifact_paths": {"predictions": "p.parquet", "features": "f.parquet"},
        "n_replicates": 5,
        "seed": 42,
        "min_games_for_ci": 4,
    }


class TestReport:
    def test_deterministic(self, preds_with_keys, keys):
        p = _payload(preds_with_keys, keys)
        assert render_report(p) == render_report(p)

    def test_required_sections(self, preds_with_keys, keys):
        text = render_report(_payload(preds_with_keys, keys))
        for i, t in enumerate([
            "Executive summary", "Dataset and artifacts",
            "Termination composition", "Join validation",
            "Overall E3→E4 decomposition", "Board-decided-only E3→E4 result",
            "Time-forfeit-only result",
            "Late-checkpoint / late-clock localization",
            "Retained-fraction interpretation", "Risks and caveats",
        ], start=1):
            assert f"## {i}. {t}" in text, t

    def test_required_caveats(self, preds_with_keys, keys):
        text = render_report(_payload(preds_with_keys, keys))
        for phrase in (
            "selection bias", "survivor population",
            "does not create a causal design",
            "not a degradation curve",
            "mixes checkmate and resignation",
            "descriptive-only",
        ):
            assert phrase in text, phrase

    def test_forbidden_language_absent(self, preds_with_keys, keys):
        text = render_report(_payload(preds_with_keys, keys))
        # the negated caveat form is required; the unnegated claim is forbidden
        denegated = text.replace(
            "no claim is made that time pressure causes worse reasoning", "")
        assert "causes worse reasoning" not in denegated
        for phrase in ("is ground truth", "DRAW is solved", "proves"):
            assert phrase not in text, phrase

    def test_negated_causal_caveat_present(self, preds_with_keys, keys):
        text = render_report(_payload(preds_with_keys, keys))
        assert "no claim is made that time pressure causes worse reasoning" in text

    def test_no_timestamp(self, preds_with_keys, keys):
        import re
        text = render_report(_payload(preds_with_keys, keys))
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", text)

    def test_no_retraining_language(self, preds_with_keys, keys):
        text = render_report(_payload(preds_with_keys, keys))
        assert "no retraining" in text or "No retraining" in text
