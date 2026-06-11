"""Tests for constraint_slices.py (Ticket 9.2B). No real data required."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.constraint_slices import (
    CHECKPOINT_ORDER,
    DECIDEDNESS_ORDER,
    DEFAULT_MIN_GAMES_FOR_CI,
    ELO_BUCKET_ORDER,
    IMBALANCE_ORDER,
    LATE_CHECKPOINTS,
    LATE_CLOCK_ORDER,
    MODEL_A,
    MODEL_B,
    SLICE_DEFINITIONS,
    attach_slice_keys,
    build_payload,
    compute_cell_result,
    confounding_crosstab,
    derive_slice_keys,
    load_e3_e4_val_predictions,
    main as slices_main,
    render_report,
    run_slice_group,
    terminal_sensitivity,
    write_outputs,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures: 24 games x 2 checkpoints (move_10, move_40) in val
# ---------------------------------------------------------------------------

_N_GAMES = 24


def _gid(i: int) -> str:
    return f"g{i:03d}"


def _result_for(i: int) -> str:
    return ["WHITE_WIN", "BLACK_WIN", "DRAW"][i % 3]


def make_feature_df() -> pl.DataFrame:
    """Synthetic feature table incl. a 'last' row per game."""
    rows = []
    for i in range(_N_GAMES):
        for cpt in ("move_10", "move_40", "last"):
            # vary slice drivers deterministically
            avg_elo = [1100.0, 1400.0, 1800.0, 2100.0][i % 4]
            # late rows get lower clocks for some games
            if cpt == "move_40":
                min_c = [20.0, 100.0, 400.0][i % 3]
            else:
                min_c = 550.0
            rows.append({
                "game_id": _gid(i),
                "selected_position_type": cpt,
                "result_class": _result_for(i),
                "avg_elo": avg_elo,
                "white_clock_s_capped": min_c,
                "black_clock_s_capped": min_c + 10.0,
                "clock_diff_s": [-10.0, 50.0, 120.0][i % 3],
            })
    return pl.DataFrame(rows)


def make_sf_df() -> pl.DataFrame:
    """Synthetic sf artifact (primary rows only)."""
    rows = []
    for i in range(_N_GAMES):
        for cpt in ("move_10", "move_40"):
            cp = [50, -150, 500, 10_000][i % 4]
            rows.append({
                "game_id": _gid(i),
                "selected_position_type": cpt,
                "split_set": "val",
                "sf_eval_cp": cp,
                "sf_depth": 0 if (i == 0 and cpt == "move_40") else 12,
            })
    return pl.DataFrame(rows)


def make_predictions_df() -> pl.DataFrame:
    """Aligned E3/E4 (+E1 noise model) prediction rows for the val split."""
    frames = []
    base_rows = []
    for i in range(_N_GAMES):
        for cpt in ("move_10", "move_40"):
            base_rows.append({
                "game_id": _gid(i),
                "selected_position_type": cpt,
                "result_class": _result_for(i),
            })
    base = pl.DataFrame(base_rows)
    n = len(base)
    for mid, p_white in (("E1", 0.40), (MODEL_A, 0.45), (MODEL_B, 0.55)):
        frames.append(base.with_columns([
            pl.lit(mid).alias("model_id"),
            pl.lit("val").alias("split_set"),
            pl.lit(0.30).alias("p_BLACK_WIN"),
            pl.lit(round(1.0 - 0.30 - p_white, 10)).alias("p_DRAW"),
            pl.lit(p_white).alias("p_WHITE_WIN"),
        ]))
    # add a test-split block that must never be read
    test_block = frames[1].with_columns(pl.lit("test").alias("split_set"))
    return pl.concat(frames + [test_block]).select(
        ["model_id", "split_set", "game_id", "selected_position_type",
         "result_class", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]
    )


@pytest.fixture
def feature_df():
    return make_feature_df()


@pytest.fixture
def sf_df():
    return make_sf_df()


@pytest.fixture
def preds_path(tmp_path):
    p = tmp_path / "preds.parquet"
    make_predictions_df().write_parquet(p)
    return p


@pytest.fixture
def preds_with_keys(preds_path, feature_df, sf_df):
    val = load_e3_e4_val_predictions(preds_path)
    keys = derive_slice_keys(feature_df, sf_df)
    return attach_slice_keys(val, keys)


# ---------------------------------------------------------------------------
# 1. Slice key derivation — bucket boundaries
# ---------------------------------------------------------------------------

def _keys_for(cp=None, elo=None, wclk=None, bclk=None, diff=None,
              cpt="move_40"):
    feat = pl.DataFrame([{
        "game_id": "g", "selected_position_type": cpt,
        "avg_elo": elo if elo is not None else 1500.0,
        "white_clock_s_capped": wclk if wclk is not None else 300.0,
        "black_clock_s_capped": bclk if bclk is not None else 300.0,
        "clock_diff_s": diff if diff is not None else 0.0,
    }])
    sf = pl.DataFrame([{
        "game_id": "g", "selected_position_type": cpt,
        "split_set": "val",
        "sf_eval_cp": cp if cp is not None else 0,
        "sf_depth": 12,
    }])
    return derive_slice_keys(feat, sf).row(0, named=True)


class TestDecidednessBoundaries:
    @pytest.mark.parametrize("cp,expected", [
        (0, "equal"), (99, "equal"), (-99, "equal"),
        (100, "slight"), (-100, "slight"), (299, "slight"),
        (300, "decided"), (-300, "decided"), (9999, "decided"),
        (10_000, "mate"), (-10_000, "mate"),
    ])
    def test_boundary(self, cp, expected):
        assert _keys_for(cp=cp)["decidedness_bucket"] == expected


class TestEloBoundaries:
    @pytest.mark.parametrize("elo,expected", [
        (1199, "under_1200"), (1200, "1200_1600"), (1599, "1200_1600"),
        (1600, "1600_2000"), (1999, "1600_2000"), (2000, "2000_plus"),
    ])
    def test_boundary(self, elo, expected):
        assert _keys_for(elo=float(elo))["elo_bucket"] == expected


class TestClockBoundaries:
    @pytest.mark.parametrize("clk,expected", [
        (29, "under_60s"), (59, "under_60s"),
        (60, "60_180s"), (179, "60_180s"),
        (180, "over_180s"), (600, "over_180s"),
    ])
    def test_late_clock_boundary(self, clk, expected):
        keys = _keys_for(wclk=float(clk), bclk=float(clk), cpt="move_40")
        assert keys["late_clock_bucket"] == expected

    def test_min_horizontal_used(self):
        keys = _keys_for(wclk=500.0, bclk=45.0, cpt="move_30")
        assert keys["late_clock_bucket"] == "under_60s"

    def test_early_checkpoint_gets_null_late_bucket(self):
        keys = _keys_for(wclk=20.0, bclk=20.0, cpt="move_10")
        assert keys["late_clock_bucket"] is None
        # marginal bucket still populated (for the confounding cross-tab)
        assert keys["marginal_clock_bucket"] == "under_60s"

    @pytest.mark.parametrize("cpt", ["move_30", "move_40"])
    def test_late_checkpoints_populated(self, cpt):
        assert _keys_for(wclk=200.0, bclk=200.0, cpt=cpt)[
            "late_clock_bucket"] == "over_180s"


class TestImbalanceBoundaries:
    @pytest.mark.parametrize("diff,expected", [
        (0, "balanced"), (29, "balanced"), (-29, "balanced"),
        (30, "moderate_imbalance"), (-30, "moderate_imbalance"),
        (89, "moderate_imbalance"),
        (90, "large_imbalance"), (-90, "large_imbalance"),
    ])
    def test_boundary(self, diff, expected):
        assert _keys_for(diff=float(diff))["imbalance_bucket"] == expected


class TestTerminalFlag:
    def test_depth0_is_terminal(self):
        feat = make_feature_df()
        sf = make_sf_df()
        keys = derive_slice_keys(feat, sf)
        term = keys.filter(pl.col("is_terminal"))
        assert len(term) == 1
        assert term["game_id"][0] == "g000"


# ---------------------------------------------------------------------------
# 2. Join integrity
# ---------------------------------------------------------------------------

class TestJoinIntegrity:
    def test_no_last_rows(self, feature_df, sf_df):
        keys = derive_slice_keys(feature_df, sf_df)
        assert "last" not in keys["selected_position_type"].unique().to_list()

    def test_val_only(self, feature_df, sf_df):
        sf_mixed = pl.concat([
            sf_df,
            sf_df.head(2).with_columns([
                pl.lit("test").alias("split_set"),
                (pl.col("game_id") + "_t").alias("game_id"),
            ]),
        ])
        feat_mixed = pl.concat([
            feature_df,
            feature_df.head(2).with_columns(
                (pl.col("game_id") + "_t").alias("game_id")),
        ])
        keys = derive_slice_keys(feat_mixed, sf_mixed)
        # only val rows kept
        assert not any(g.endswith("_t") for g in keys["game_id"].to_list())

    def test_duplicate_feature_key_raises(self, feature_df, sf_df):
        with pytest.raises(ValueError, match="not unique"):
            derive_slice_keys(pl.concat([feature_df, feature_df.head(1)]), sf_df)

    def test_duplicate_sf_key_raises(self, feature_df, sf_df):
        with pytest.raises(ValueError, match="not unique"):
            derive_slice_keys(feature_df, pl.concat([sf_df, sf_df.head(1)]))

    def test_orphan_raises(self, feature_df, sf_df):
        with pytest.raises(ValueError, match="orphan"):
            derive_slice_keys(feature_df, sf_df.head(len(sf_df) - 1))

    def test_attach_orphan_raises(self, preds_path, feature_df, sf_df):
        val = load_e3_e4_val_predictions(preds_path)
        keys = derive_slice_keys(feature_df, sf_df).head(10)
        with pytest.raises(ValueError, match="no slice keys"):
            attach_slice_keys(val, keys)

    def test_attach_zero_orphans(self, preds_with_keys):
        assert preds_with_keys["decidedness_bucket"].null_count() == 0


# ---------------------------------------------------------------------------
# 3. Prediction loading / pairing validity
# ---------------------------------------------------------------------------

class TestLoadPredictions:
    def test_loads_e3_e4_val_only(self, preds_path):
        val = load_e3_e4_val_predictions(preds_path)
        assert sorted(val["model_id"].unique().to_list()) == [MODEL_A, MODEL_B]
        assert val["split_set"].unique().to_list() == ["val"]

    def test_test_split_never_loaded(self, preds_path):
        val = load_e3_e4_val_predictions(preds_path)
        assert "test" not in val["split_set"].unique().to_list()

    def test_missing_model_fails(self, tmp_path):
        df = make_predictions_df().filter(pl.col("model_id") != "E4")
        p = tmp_path / "p.parquet"
        df.write_parquet(p)
        with pytest.raises(ValueError, match="No validation rows for E4"):
            load_e3_e4_val_predictions(p)

    def test_misaligned_labels_fail(self, tmp_path):
        df = make_predictions_df()
        # corrupt one E4 label
        df = df.with_columns(
            pl.when((pl.col("model_id") == "E4")
                    & (pl.col("game_id") == "g000")
                    & (pl.col("split_set") == "val")
                    & (pl.col("selected_position_type") == "move_10"))
            .then(pl.lit("DRAW")).otherwise(pl.col("result_class"))
            .alias("result_class")
        )
        p = tmp_path / "p.parquet"
        df.write_parquet(p)
        with pytest.raises(ValueError, match="not aligned"):
            load_e3_e4_val_predictions(p)

    def test_last_rows_fail(self, tmp_path):
        df = make_predictions_df()
        bad = df.filter(
            (pl.col("model_id") == MODEL_A) & (pl.col("split_set") == "val")
        ).head(2).with_columns(
            pl.lit("last").alias("selected_position_type"))
        p = tmp_path / "p.parquet"
        pl.concat([df, bad]).write_parquet(p)
        with pytest.raises(ValueError, match="last"):
            load_e3_e4_val_predictions(p)


# ---------------------------------------------------------------------------
# 4. Delta computation
# ---------------------------------------------------------------------------

class TestDeltaComputation:
    def test_sign_convention(self, preds_with_keys):
        # E4 puts more mass on WHITE_WIN; WHITE_WIN is the most common label
        # in the fixture (i%3==0 -> 8 of 24 games... actually 1/3). Verify
        # delta = ll(E4) - ll(E3) matches manual computation.
        r = compute_cell_result(preds_with_keys, n_replicates=5, seed=42,
                                min_games_for_ci=5)
        assert r["point_delta"] == pytest.approx(
            r["log_loss_e4"] - r["log_loss_e3"], abs=1e-12)

    def test_log_loss_manual(self):
        import numpy as np
        # one game, one row, label WHITE_WIN; E3 p=0.45, E4 p=0.55
        rows = []
        for mid, pw in ((MODEL_A, 0.45), (MODEL_B, 0.55)):
            rows.append({
                "model_id": mid, "split_set": "val", "game_id": "g",
                "selected_position_type": "move_10",
                "result_class": "WHITE_WIN",
                "p_BLACK_WIN": 0.30, "p_DRAW": round(0.70 - pw, 10),
                "p_WHITE_WIN": pw,
                "decidedness_bucket": "equal", "elo_bucket": "1200_1600",
                "late_clock_bucket": None, "marginal_clock_bucket": "over_180s",
                "imbalance_bucket": "balanced", "is_terminal": False,
            })
        df = pl.DataFrame(rows)
        r = compute_cell_result(df, n_replicates=2, seed=42,
                                min_games_for_ci=1000)
        assert r["log_loss_e3"] == pytest.approx(-np.log(0.45), abs=1e-9)
        assert r["log_loss_e4"] == pytest.approx(-np.log(0.55), abs=1e-9)
        assert r["point_delta"] < 0  # E4 improved -> negative

    def test_draw_count(self, preds_with_keys):
        r = compute_cell_result(preds_with_keys, n_replicates=2, seed=42,
                                min_games_for_ci=10_000)
        # 24 games x 2 rows, i%3==2 -> 8 games DRAW -> 16 rows
        assert r["n_draw_rows"] == 16


# ---------------------------------------------------------------------------
# 5. Bootstrap behavior
# ---------------------------------------------------------------------------

class TestBootstrap:
    def test_ci_above_threshold(self, preds_with_keys):
        r = compute_cell_result(preds_with_keys, n_replicates=20, seed=42,
                                min_games_for_ci=10)
        assert r["ci_lower"] is not None
        assert r["ci_lower"] <= r["ci_upper"]
        assert r["contains_zero"] == (r["ci_lower"] <= 0 <= r["ci_upper"])
        assert r["note"] is None

    def test_no_ci_below_threshold(self, preds_with_keys):
        r = compute_cell_result(preds_with_keys, n_replicates=20, seed=42,
                                min_games_for_ci=1_000)
        assert r["ci_lower"] is None
        assert r["contains_zero"] is None
        assert r["note"] == "below min game threshold"
        assert r["point_delta"] is not None  # not silently dropped

    def test_deterministic_with_seed(self, preds_with_keys):
        r1 = compute_cell_result(preds_with_keys, 50, 42, 10)
        r2 = compute_cell_result(preds_with_keys, 50, 42, 10)
        assert r1 == r2

    def test_game_level_cluster_counts(self, preds_with_keys):
        r = compute_cell_result(preds_with_keys, 5, 42, 10)
        assert r["n_games"] == _N_GAMES
        assert r["n_rows"] == _N_GAMES * 2


# ---------------------------------------------------------------------------
# 6. Slice groups, cross-tab, terminal sensitivity
# ---------------------------------------------------------------------------

class TestSliceGroups:
    def test_all_groups_run(self, preds_with_keys):
        for name, d in SLICE_DEFINITIONS.items():
            res = run_slice_group(preds_with_keys, d["column"], d["cells"],
                                  n_replicates=5, seed=42, min_games_for_ci=4)
            assert set(res) == set(d["cells"])

    def test_empty_cell_marked(self, preds_with_keys):
        # fixture has no move_20/move_30 rows
        res = run_slice_group(preds_with_keys, "selected_position_type",
                              CHECKPOINT_ORDER, 5, 42, 4)
        assert res["move_20"]["note"] == "empty cell"
        assert res["move_30"]["note"] == "empty cell"
        assert res["move_10"]["n_games"] == _N_GAMES

    def test_late_clock_only_late_rows(self, preds_with_keys):
        res = run_slice_group(preds_with_keys, "late_clock_bucket",
                              LATE_CLOCK_ORDER, 5, 42, 4)
        total_rows = sum(r.get("n_rows", 0) for r in res.values())
        # only move_40 rows (24 games x 1 row x 2 models -> n_rows counts E3 rows)
        assert total_rows == _N_GAMES

    def test_confounding_crosstab_shape(self, preds_with_keys):
        ct = confounding_crosstab(preds_with_keys)
        assert set(ct) == set(CHECKPOINT_ORDER)
        for cpt in CHECKPOINT_ORDER:
            assert set(ct[cpt]) == set(LATE_CLOCK_ORDER)
        # all move_10 rows in fixture have 550s clocks
        assert ct["move_10"]["over_180s"]["rows"] == _N_GAMES
        assert ct["move_10"]["under_60s"]["rows"] == 0

    def test_terminal_sensitivity(self, preds_with_keys):
        ts = terminal_sensitivity(preds_with_keys, 5, 42, 4)
        assert ts["terminal_included"]["n_rows"] == _N_GAMES * 2
        assert ts["terminal_excluded"]["n_rows"] == _N_GAMES * 2 - 1


# ---------------------------------------------------------------------------
# 7. Payload and report
# ---------------------------------------------------------------------------

def _make_payload(preds_with_keys) -> dict:
    slice_results = {
        name: run_slice_group(preds_with_keys, d["column"], d["cells"],
                              5, 42, 4)
        for name, d in SLICE_DEFINITIONS.items()
    }
    return build_payload(
        dataset_id="synthetic_ds", version_tag="synthetic_v1",
        slice_results=slice_results,
        crosstab=confounding_crosstab(preds_with_keys),
        terminal_results=terminal_sensitivity(preds_with_keys, 5, 42, 4),
        artifact_paths={"predictions": "p.parquet", "features": "f.parquet",
                        "sf_eval": "s.parquet", "output_json": "o.json",
                        "output_report": "o.md"},
        n_replicates=5, seed=42, min_games_for_ci=4,
    )


class TestPayloadAndReport:
    @pytest.fixture(scope="class")
    def payload(self):
        preds_path_ = None
        feature_df = make_feature_df()
        sf_df = make_sf_df()
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "preds.parquet"
            make_predictions_df().write_parquet(p)
            val = load_e3_e4_val_predictions(p)
        keys = derive_slice_keys(feature_df, sf_df)
        return _make_payload(attach_slice_keys(val, keys))

    def test_payload_required_fields(self, payload):
        for key in ("dataset_id", "version_tag", "slice_definitions",
                    "slice_results", "confounding_crosstab_clock_x_checkpoint",
                    "terminal_sensitivity", "n_replicates", "seed",
                    "min_games_for_ci", "artifact_paths", "caveats",
                    "delta_convention"):
            assert key in payload, key

    def test_report_deterministic(self, payload):
        assert render_report(payload) == render_report(payload)

    def test_report_required_sections(self, payload):
        text = render_report(payload)
        for i, title in enumerate([
            "ELI5 / TLDR", "Result Being Localized",
            "Inputs and Join Integrity", "Slice Definitions",
            "Data Sufficiency",
            "Confounding Diagnostic: Clock Bucket × Checkpoint",
            "Reference: Per-Checkpoint E3→E4 Deltas",
            "P1: Eval Decidedness Slice", "P2: Rating Bucket Slice",
            "P3: Late-Checkpoint Clock Bucket Slice", "Exploratory Slices",
            "Interpretation", "Guardrails / Forbidden Claims",
            "Limitations", "Reproducibility",
        ], start=1):
            assert f"## {i}. {title}" in text, title

    def test_required_caveats(self, payload):
        text = render_report(payload)
        for phrase in (
            "predictive associations",
            "not causal",
            "not ground truth",
            "degradation curves are not established",
            "no multiple-comparison correction",
            "Test split was not used",
            "Player-level leakage remains unresolved",
            "not solved",
        ):
            assert phrase.lower() in text.lower(), phrase

    def test_forbidden_phrases_absent(self, payload):
        text = render_report(payload)
        for phrase in (
            "causes worse", "proves degradation", "establishes degradation",
            "measures reasoning", "Stockfish is truth", "is ground truth",
            "DRAW solved", "DRAW is solved",
        ):
            assert phrase not in text, phrase

    def test_sub_threshold_note_in_report(self, preds_with_keys):
        slice_results = {
            name: run_slice_group(preds_with_keys, d["column"], d["cells"],
                                  5, 42, 10_000)  # force sub-threshold
            for name, d in SLICE_DEFINITIONS.items()
        }
        payload = build_payload(
            "ds", "v", slice_results,
            confounding_crosstab(preds_with_keys),
            terminal_sensitivity(preds_with_keys, 5, 42, 10_000),
            {"predictions": "p"}, 5, 42, 10_000,
        )
        text = render_report(payload)
        assert "below min game threshold" in text
        assert "N/A" in text

    def test_no_hardcoded_dataset_counts(self, payload):
        text = render_report(payload)
        for literal in ("9,823", "3,678", "65,368", "250k rows"):
            assert literal not in text, literal

    def test_confounding_table_in_report(self, payload):
        text = render_report(payload)
        assert "## 6. Confounding Diagnostic" in text
        assert "move_10 |" in text

    def test_no_timestamp_in_body(self, payload):
        import re
        text = render_report(payload)
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", text)


# ---------------------------------------------------------------------------
# 8. Outputs / artifact safety / CLI
# ---------------------------------------------------------------------------

class TestOutputs:
    def test_write_and_overwrite_guard(self, preds_with_keys, tmp_path):
        payload = _make_payload(preds_with_keys)
        text = render_report(payload)
        oj = tmp_path / "out.json"
        om = tmp_path / "out.md"
        write_outputs(payload, text, oj, om)
        assert oj.exists() and om.exists()
        with pytest.raises(FileExistsError):
            write_outputs(payload, text, oj, om)
        write_outputs(payload, text, oj, om, overwrite=True)

    def test_json_schema(self, preds_with_keys, tmp_path):
        payload = _make_payload(preds_with_keys)
        oj = tmp_path / "out.json"
        write_outputs(payload, render_report(payload), oj, tmp_path / "o.md")
        loaded = json.loads(oj.read_text())
        assert loaded["dataset_id"] == "synthetic_ds"
        assert "slice_definitions" in loaded
        assert "slice_results" in loaded
        cell = loaded["slice_results"]["checkpoint"]["move_10"]
        for k in ("n_rows", "n_games", "point_delta"):
            assert k in cell

    def test_real_artifact_path_gitignored(self):
        repo = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            ["git", "check-ignore",
             "data/processed/constraint_slices_2024_09_250k_v1.json"],
            cwd=repo, capture_output=True, text=True,
        )
        assert proc.returncode == 0

    def test_cli_end_to_end(self, tmp_path, feature_df, sf_df):
        fpath = tmp_path / "feat.parquet"
        spath = tmp_path / "sf.parquet"
        ppath = tmp_path / "preds.parquet"
        feature_df.write_parquet(fpath)
        sf_df.write_parquet(spath)
        make_predictions_df().write_parquet(ppath)
        oj = tmp_path / "out.json"
        om = tmp_path / "out.md"
        rc = slices_main([
            "--dataset-id", "synthetic_ds",
            "--version-tag", "synthetic_v1",
            "--predictions", str(ppath),
            "--features", str(fpath),
            "--sf-eval", str(spath),
            "--output-json", str(oj),
            "--output-report", str(om),
            "--n-replicates", "5",
            "--seed", "42",
            "--min-games-for-ci", "4",
            "--overwrite",
        ])
        assert rc == 0
        assert oj.exists() and om.exists()
        loaded = json.loads(oj.read_text())
        assert set(loaded["slice_results"]) == set(SLICE_DEFINITIONS)

    def test_constants(self):
        assert MODEL_A == "E3" and MODEL_B == "E4"
        assert DEFAULT_MIN_GAMES_FOR_CI == 300
        assert LATE_CHECKPOINTS == ["move_30", "move_40"]
        assert DECIDEDNESS_ORDER == ["equal", "slight", "decided", "mate"]
        assert ELO_BUCKET_ORDER == [
            "under_1200", "1200_1600", "1600_2000", "2000_plus"]
        assert LATE_CLOCK_ORDER == ["under_60s", "60_180s", "over_180s"]
        assert IMBALANCE_ORDER == [
            "balanced", "moderate_imbalance", "large_imbalance"]


# ---------------------------------------------------------------------------
# 9. Payload-driven limitations prose (9.3B)
# ---------------------------------------------------------------------------

class TestPayloadDrivenLimitations:
    def test_limitations_use_dataset_id(self, preds_with_keys):
        payload = _make_payload(preds_with_keys)
        text = render_report(payload)
        assert "`synthetic_ds`" in text
        # no hardcoded month/sample prose
        assert "superset 250k sample" not in text
        assert "2024-09" not in text
        assert "2024_09_250k" not in text

    def test_external_validity_caveat_generic(self, preds_with_keys):
        payload = _make_payload(preds_with_keys)
        text = render_report(payload)
        assert "external validity beyond the tested month(s) is not established" in text
