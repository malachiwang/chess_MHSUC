"""Tests for eval_conditioned_modeling.py (Ticket 8.2B). No real data required."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from chess_mhsuc.eval_conditioned_modeling import (
    CLASS_ORDER,
    EVAL_FEATURE_COLS,
    LICHESS_EVAL_COLS,
    PAIRWISE_COMPARISONS,
    PILOT_E3_E4_CI,
    PILOT_E3_E4_DELTA,
    REFERENCE_MODEL_IDS,
    SF_EVAL_CLIP_CP,
    build_combined_predictions,
    build_eval_feature_sets,
    build_eval_model,
    build_model_registry,
    build_prediction_frame,
    build_results_payload,
    classify_feature_types,
    compute_dataset_stats,
    compute_lichess_overlap_stats,
    decisive_only_diagnostic,
    derive_eval_features,
    join_sf_features,
    load_baseline_reference,
    main as ecm_main,
    parse_expected_split_counts,
    per_checkpoint_key_deltas,
    per_checkpoint_slice,
    render_report,
    run_all_eval_models,
    run_bootstrap_cis,
    run_pairwise_deltas,
    select_best_e_model,
    train_one_eval_model,
    validate_joined,
    validate_pairing,
    validate_sf_artifact,
    write_outputs,
)
from chess_mhsuc.splits import _FS_B_COLS, _FS_C_COLS, _FS_E_COLS


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

_N_GAMES = 30  # 10 train, 10 val, 10 test (game-level split)


def _game_ids() -> list[str]:
    return [f"g{i:03d}" for i in range(_N_GAMES)]


def _split_for(i: int) -> str:
    if i < 10:
        return "train"
    if i < 20:
        return "val"
    return "test"


def _result_for(i: int) -> str:
    # mix of classes in every split
    return ["WHITE_WIN", "BLACK_WIN", "DRAW", "WHITE_WIN", "BLACK_WIN"][i % 5]


def make_feature_df() -> pl.DataFrame:
    """Synthetic feature_positions_broad-like table: 2 checkpoints per game + 1 'last'."""
    rows = []
    rng = np.random.default_rng(0)
    for i, gid in enumerate(_game_ids()):
        for cpt, mv in [("move_10", 10), ("move_20", 20), ("last", 25)]:
            rows.append({
                "game_id": gid,
                "selected_position_type": cpt,
                "move_number": mv,
                "result_class": _result_for(i),
                # FS-B
                "white_elo": 1500.0 + i, "black_elo": 1500.0 - i,
                "elo_diff": float(2 * i), "avg_elo": 1500.0,
                # FS-C
                "white_clock_s_capped": 500.0 - mv, "black_clock_s_capped": 480.0 - mv,
                "clock_diff_s": 20.0, "white_clock_frac": 0.8, "black_clock_frac": 0.75,
                "clock_diff_frac": 0.05,
                "white_low_60": False, "black_low_60": False,
                "white_low_30": False, "black_low_30": False,
                "white_low_10": False, "black_low_10": False,
                "clock_anomaly": False,
                # FS-D
                "phase": "middlegame", "checkpoint_index": mv // 10,
                "phase_index": 1,
                # Lichess eval cols (must never become features)
                "eval_cp": None, "eval_cp_clipped": None, "eval_mate": None,
                "eval_mate_abs": 0.0, "is_mate_eval": False,
                "eval_white_winning": False, "has_eval": False,
                # noise
                "_noise": float(rng.normal()),
            })
    return pl.DataFrame(rows, infer_schema_length=None)


def make_sf_df() -> pl.DataFrame:
    """Synthetic sf_eval artifact: primary checkpoints only (no 'last')."""
    rows = []
    for i, gid in enumerate(_game_ids()):
        for cpt in ("move_10", "move_20"):
            # make sf eval informative of result
            res = _result_for(i)
            cp = {"WHITE_WIN": 250, "BLACK_WIN": -250, "DRAW": 0}[res]
            is_mate = (i % 10 == 9 and cpt == "move_20")
            sf_cp = (
                (10_000 if cp >= 0 else -10_000) if is_mate
                else cp + (5 if cpt == "move_20" else 0)
            )
            # Lichess overlap on a subset (every 3rd game, move_10 only),
            # same sign, +30cp offset, no mate values
            has_li = (i % 3 == 0 and cpt == "move_10" and not is_mate)
            rows.append({
                "game_id": gid,
                "selected_position_type": cpt,
                "split_set": _split_for(i),
                "sf_eval_cp": sf_cp,
                "sf_eval_status": "ok_mate" if is_mate else "ok_cp",
                "sf_eval_available": True,
                "sf_depth": 12,
                "has_lichess_eval": has_li,
                "lichess_eval_cp": (sf_cp + 30) if has_li else None,
                "lichess_eval_mate": None,
            })
    return pl.DataFrame(rows, infer_schema_length=None)


@pytest.fixture
def feature_df() -> pl.DataFrame:
    return make_feature_df()


@pytest.fixture
def sf_df() -> pl.DataFrame:
    return make_sf_df()


@pytest.fixture
def modeling_df(feature_df, sf_df) -> pl.DataFrame:
    return derive_eval_features(join_sf_features(feature_df, sf_df))


# ---------------------------------------------------------------------------
# 1. Join integrity
# ---------------------------------------------------------------------------

class TestJoinIntegrity:
    def test_join_row_count_matches_primary_view(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        assert len(joined) == _N_GAMES * 2  # 'last' excluded

    def test_no_last_rows_after_join(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        assert "last" not in joined["selected_position_type"].unique().to_list()

    def test_zero_orphans(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        assert joined["sf_eval_status"].null_count() == 0

    def test_orphan_raises(self, feature_df, sf_df):
        sf_missing = sf_df.head(len(sf_df) - 1)  # drop one row -> orphan
        with pytest.raises(ValueError, match="orphan"):
            join_sf_features(feature_df, sf_missing)

    def test_duplicate_key_in_sf_raises(self, feature_df, sf_df):
        sf_dup = pl.concat([sf_df, sf_df.head(1)])
        with pytest.raises(ValueError, match="not unique"):
            join_sf_features(feature_df, sf_dup)

    def test_duplicate_key_in_features_raises(self, feature_df, sf_df):
        feat_dup = pl.concat([feature_df, feature_df.head(1)])
        with pytest.raises(ValueError, match="not unique"):
            join_sf_features(feat_dup, sf_df)

    def test_row_order_preserved(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        primary = feature_df.filter(pl.col("selected_position_type") != "last")
        assert joined["game_id"].to_list() == primary["game_id"].to_list()
        assert (joined["selected_position_type"].to_list()
                == primary["selected_position_type"].to_list())

    def test_split_counts(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        summary = validate_joined(joined)
        assert summary["split_counts"] == {"train": 20, "val": 20, "test": 20}

    def test_no_split_game_overlap_validated(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        bad = joined.with_columns(
            pl.when(pl.col("game_id") == "g000")
            .then(pl.lit("val")).otherwise(pl.col("split_set"))
            .alias("split_set")
        )
        # g000 now has rows only in val — no overlap; force a true overlap:
        bad2 = pl.concat([
            joined,
            joined.filter(pl.col("game_id") == "g000").with_columns(
                pl.lit("val").alias("split_set")
            ),
        ])
        with pytest.raises(ValueError, match="overlap"):
            validate_joined(bad2)

    def test_last_rows_in_joined_raises(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        bad = pl.concat([
            joined,
            joined.head(1).with_columns(
                pl.lit("last").alias("selected_position_type")
            ),
        ])
        with pytest.raises(ValueError, match="last"):
            validate_joined(bad)

    def test_no_suffix_pollution(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        assert not [c for c in joined.columns if c.endswith("_right")]

    def test_pilot_reference_constants(self):
        # kept for cross-version report comparison only — never asserted on data
        assert PILOT_E3_E4_DELTA == -0.0138
        assert PILOT_E3_E4_CI == (-0.0266, -0.0002)


# ---------------------------------------------------------------------------
# 2. sf artifact validation
# ---------------------------------------------------------------------------

class TestValidateSfArtifact:
    def test_valid_artifact_passes(self, sf_df):
        summary = validate_sf_artifact(sf_df)
        assert summary["n_rows"] == len(sf_df)

    def test_bad_status_raises(self, sf_df):
        bad = sf_df.with_columns(pl.lit("failed").alias("sf_eval_status"))
        with pytest.raises(ValueError, match="status"):
            validate_sf_artifact(bad)

    def test_unavailable_raises(self, sf_df):
        bad = sf_df.with_columns(pl.lit(False).alias("sf_eval_available"))
        with pytest.raises(ValueError, match="available"):
            validate_sf_artifact(bad)

    def test_cp_out_of_range_raises(self, sf_df):
        bad = sf_df.with_columns(pl.lit(20_000).alias("sf_eval_cp"))
        with pytest.raises(ValueError, match="range"):
            validate_sf_artifact(bad)

    def test_last_positions_raise(self, sf_df):
        bad = pl.concat([
            sf_df,
            sf_df.head(1).with_columns(
                pl.lit("last").alias("selected_position_type"),
                pl.lit("zzz").alias("game_id"),
            ),
        ])
        with pytest.raises(ValueError, match="last"):
            validate_sf_artifact(bad)

    def test_terminal_depth0_rows_counted_not_failed(self, sf_df):
        with_terminal = sf_df.with_columns(
            pl.when(pl.col("game_id") == "g000")
            .then(pl.lit(0)).otherwise(pl.col("sf_depth"))
            .alias("sf_depth")
        )
        summary = validate_sf_artifact(with_terminal)  # must NOT raise
        assert summary["n_terminal_depth0"] == 2  # g000 has 2 checkpoints


# ---------------------------------------------------------------------------
# 3. Feature derivation
# ---------------------------------------------------------------------------

class TestDeriveEvalFeatures:
    def test_clip_sentinels_in_joined_data(self, feature_df, sf_df):
        joined = join_sf_features(feature_df, sf_df)
        out = derive_eval_features(joined)
        mate_rows = out.filter(pl.col("sf_eval_cp").abs() == 10_000)
        assert len(mate_rows) > 0
        assert (mate_rows["sf_eval_cp_clipped"].abs() == SF_EVAL_CLIP_CP).all()

    def test_clip_positive_sentinel(self):
        df = pl.DataFrame({
            "sf_eval_cp": [10_000, 1500],
            "sf_eval_status": ["ok_mate", "ok_cp"],
        })
        out = derive_eval_features(df)
        assert out["sf_eval_cp_clipped"].to_list() == [1000, 1000]

    def test_clip_negative_sentinel(self):
        df = pl.DataFrame({
            "sf_eval_cp": [-10_000, -1500],
            "sf_eval_status": ["ok_mate", "ok_cp"],
        })
        out = derive_eval_features(df)
        assert out["sf_eval_cp_clipped"].to_list() == [-1000, -1000]

    def test_normal_cp_unchanged(self):
        df = pl.DataFrame({
            "sf_eval_cp": [0, 250, -999, 1000],
            "sf_eval_status": ["ok_cp"] * 4,
        })
        out = derive_eval_features(df)
        assert out["sf_eval_cp_clipped"].to_list() == [0, 250, -999, 1000]

    def test_mate_flag(self):
        df = pl.DataFrame({
            "sf_eval_cp": [10_000, 50],
            "sf_eval_status": ["ok_mate", "ok_cp"],
        })
        out = derive_eval_features(df)
        assert out["sf_is_mate_eval"].to_list() == [True, False]

    def test_terminal_depth0_not_treated_as_failure(self):
        # terminal checkmate row: ok_mate, depth 0 — derives normally
        df = pl.DataFrame({
            "sf_eval_cp": [-10_000],
            "sf_eval_status": ["ok_mate"],
            "sf_depth": [0],
        })
        out = derive_eval_features(df)
        assert out["sf_eval_cp_clipped"].to_list() == [-1000]
        assert out["sf_is_mate_eval"].to_list() == [True]


# ---------------------------------------------------------------------------
# 4. Feature sets and registry
# ---------------------------------------------------------------------------

class TestFeatureSets:
    def test_fs_h_exact_columns(self):
        fs = build_eval_feature_sets()
        assert fs["FS-H"]["features"] == ["sf_eval_cp_clipped", "sf_is_mate_eval"]

    def test_fs_i_exact_columns(self):
        fs = build_eval_feature_sets()
        assert fs["FS-I"]["features"] == list(_FS_B_COLS) + EVAL_FEATURE_COLS

    def test_fs_j_exact_columns(self):
        fs = build_eval_feature_sets()
        assert fs["FS-J"]["features"] == (
            list(_FS_B_COLS) + list(_FS_C_COLS) + EVAL_FEATURE_COLS
        )

    def test_fs_k_exact_columns(self):
        fs = build_eval_feature_sets()
        assert fs["FS-K"]["features"] == list(_FS_E_COLS) + EVAL_FEATURE_COLS

    def test_no_lichess_eval_columns_in_any_feature_set(self):
        fs = build_eval_feature_sets()
        for fid, entry in fs.items():
            assert not (set(entry["features"]) & LICHESS_EVAL_COLS), fid

    def test_no_provenance_columns_in_any_feature_set(self):
        forbidden = {"sf_depth", "sf_nodes", "sf_time_ms", "fen_hash",
                     "sf_eval_status", "sf_eval_bucket", "sf_eval_available"}
        fs = build_eval_feature_sets()
        for fid, entry in fs.items():
            assert not (set(entry["features"]) & forbidden), fid

    def test_registry_models(self):
        reg = build_model_registry()
        assert sorted(reg) == ["E1", "E3", "E4", "E5"]

    def test_registry_no_e0_e2(self):
        reg = build_model_registry()
        assert "E0" not in reg and "E2" not in reg

    def test_registry_all_logistic(self):
        reg = build_model_registry()
        assert all(e["model_class"] == "LogisticRegression" for e in reg.values())

    def test_no_gbm_supported(self):
        with pytest.raises(ValueError, match="no GBMs"):
            build_eval_model(
                {"model_class": "HistGradientBoostingClassifier",
                 "sklearn_params": {}},
                None,
            )

    def test_classify_rejects_lichess_eval(self):
        for col in sorted(LICHESS_EVAL_COLS):
            with pytest.raises(ValueError, match="Forbidden"):
                classify_feature_types([col])

    def test_classify_rejects_labels_and_metadata(self):
        for col in ("result_class", "game_id", "split_set", "sf_depth",
                    "fen_hash", "sf_eval_bucket"):
            with pytest.raises(ValueError, match="Forbidden"):
                classify_feature_types([col])

    def test_classify_sf_mate_flag_is_boolean(self):
        types = classify_feature_types(["sf_eval_cp_clipped", "sf_is_mate_eval"])
        assert types["boolean"] == ["sf_is_mate_eval"]
        assert types["numeric"] == ["sf_eval_cp_clipped"]
        assert types["nullable_numeric"] == []

    def test_classify_categoricals(self):
        types = classify_feature_types(["selected_position_type", "phase"])
        assert types["categorical"] == ["selected_position_type", "phase"]


# ---------------------------------------------------------------------------
# 5. Modeling
# ---------------------------------------------------------------------------

class TestModeling:
    def test_train_one_model_runs(self, modeling_df):
        reg = build_model_registry()
        fs = build_eval_feature_sets()
        result, preds = train_one_eval_model("E1", reg["E1"], fs, modeling_df)
        assert result["model_id"] == "E1"
        assert result["n_train_rows"] == 20

    def test_metrics_for_all_splits(self, modeling_df):
        reg = build_model_registry()
        fs = build_eval_feature_sets()
        result, _ = train_one_eval_model("E1", reg["E1"], fs, modeling_df)
        assert set(result["metrics"]) == {"train", "val", "test"}

    def test_probabilities_sum_to_one(self, modeling_df):
        reg = build_model_registry()
        fs = build_eval_feature_sets()
        _, preds = train_one_eval_model("E3", reg["E3"], fs, modeling_df)
        sums = (preds["p_BLACK_WIN"] + preds["p_DRAW"] + preds["p_WHITE_WIN"])
        assert all(abs(s - 1.0) < 1e-6 for s in sums.to_list())

    def test_prediction_row_counts(self, modeling_df):
        results, preds = run_all_eval_models(modeling_df)
        # 4 models x 60 primary rows
        assert len(preds) == 4 * 60
        for mid in ("E1", "E3", "E4", "E5"):
            sub = preds.filter(pl.col("model_id") == mid)
            assert len(sub.filter(pl.col("split_set") == "val")) == 20

    def test_predictions_contain_required_columns(self, modeling_df):
        _, preds = run_all_eval_models(modeling_df)
        required = {"model_id", "split_set", "game_id", "selected_position_type",
                    "result_class", "y_true", "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"}
        assert required.issubset(set(preds.columns))

    def test_class_order_matches_baselines(self):
        from chess_mhsuc.baselines import CLASS_ORDER as BASE_ORDER
        assert CLASS_ORDER == BASE_ORDER == ["BLACK_WIN", "DRAW", "WHITE_WIN"]

    def test_y_true_consistent_with_result_class(self, modeling_df):
        _, preds = run_all_eval_models(modeling_df)
        from chess_mhsuc.baselines import LABEL_MAP
        for rc, yt in zip(preds["result_class"].to_list()[:50],
                          preds["y_true"].to_list()[:50]):
            assert LABEL_MAP[rc] == yt

    def test_best_e_selected_on_val_only(self):
        eval_results = {
            "E1": {"metrics": {"val": {"log_loss": 0.9},
                               "test": {"log_loss": 0.1}}},
            "E3": {"metrics": {"val": {"log_loss": 0.8},
                               "test": {"log_loss": 99.0}}},
        }
        # E3 wins on val even though E1 has better test — test never consulted
        assert select_best_e_model(eval_results) == "E3"

    def test_train_only_fits_on_train_split(self, modeling_df):
        # remove val/test rows: training must produce identical model behavior
        reg = build_model_registry()
        fs = build_eval_feature_sets()
        result_full, preds_full = train_one_eval_model(
            "E1", reg["E1"], fs, modeling_df
        )
        # corrupt val/test labels: train metrics must be unaffected
        corrupted = modeling_df.with_columns(
            pl.when(pl.col("split_set") != "train")
            .then(pl.lit("DRAW")).otherwise(pl.col("result_class"))
            .alias("result_class")
        )
        result_corr, _ = train_one_eval_model("E1", reg["E1"], fs, corrupted)
        assert (result_full["metrics"]["train"]["log_loss"]
                == result_corr["metrics"]["train"]["log_loss"])

    def test_eval_signal_learned(self, modeling_df):
        # synthetic sf_eval is informative; E1 must beat random guessing on val
        reg = build_model_registry()
        fs = build_eval_feature_sets()
        result, _ = train_one_eval_model("E1", reg["E1"], fs, modeling_df)
        assert result["metrics"]["val"]["log_loss"] < 1.0986  # ln(3)


# ---------------------------------------------------------------------------
# 6. Pairing and bootstrap
# ---------------------------------------------------------------------------

def _make_ref_preds(modeling_df: pl.DataFrame, model_id: str) -> pl.DataFrame:
    """Reference predictions aligned with the modeling table row order."""
    n = len(modeling_df)
    return pl.DataFrame({
        "model_id": [model_id] * n,
        "split_set": modeling_df["split_set"],
        "game_id": modeling_df["game_id"],
        "result_class": modeling_df["result_class"],
        "p_BLACK_WIN": [0.3] * n,
        "p_DRAW": [0.2] * n,
        "p_WHITE_WIN": [0.5] * n,
    })


class TestPairingAndBootstrap:
    def test_validate_pairing_passes_when_aligned(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        assert validate_pairing(combined, "B3", "E1")

    def test_validate_pairing_fails_on_row_count_mismatch(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        # head(30) keeps all 20 train rows but only 10 of 20 val rows
        b3 = _make_ref_preds(modeling_df, "B3").head(30)
        combined = build_combined_predictions(eval_preds, b3)
        with pytest.raises(ValueError, match="row counts differ"):
            validate_pairing(combined, "B3", "E1")

    def test_validate_pairing_fails_on_order_mismatch(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3").sort("game_id", descending=True)
        combined = build_combined_predictions(eval_preds, b3)
        with pytest.raises(ValueError, match="order differs"):
            validate_pairing(combined, "B3", "E1")

    def test_bootstrap_cis_run(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        cis = run_bootstrap_cis(combined, n_replicates=20, seed=42)
        assert "E1" in cis and "B3" in cis
        for c in cis.values():
            assert c["ci_lower"] <= c["ci_upper"]

    def test_bootstrap_is_game_level(self, modeling_df):
        # per-model CI result reports n_val_games < n_val_rows (clusters)
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        cis = run_bootstrap_cis(combined, n_replicates=10, seed=42)
        assert cis["E1"]["n_val_games"] == 10
        assert cis["E1"]["n_val_rows"] == 20

    def test_pairwise_deltas_computed(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        deltas = run_pairwise_deltas(combined, best_e="E5",
                                     n_replicates=20, seed=42)
        assert "E3_vs_E4" in deltas
        assert "E1_vs_E3" in deltas
        assert "E4_vs_E5" in deltas
        assert "B3_vs_E1" in deltas
        assert "B3_vs_E5" in deltas

    def test_contains_zero_flag_consistent(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        deltas = run_pairwise_deltas(combined, best_e="E5",
                                     n_replicates=20, seed=42)
        for d in deltas.values():
            expected = d["ci_lower"] <= 0.0 <= d["ci_upper"]
            assert d["contains_zero"] == expected

    def test_best_e_dedup_no_self_pair(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        b3 = _make_ref_preds(modeling_df, "B3")
        combined = build_combined_predictions(eval_preds, b3)
        # best_e == E1 makes B3_vs_BEST_E collapse into B3_vs_E1 (dedup)
        deltas = run_pairwise_deltas(combined, best_e="E1",
                                     n_replicates=10, seed=42)
        keys = [k for k in deltas if k.startswith("B3_vs_")]
        assert keys == ["B3_vs_E1"]

    def test_pairwise_required_comparisons_constant(self):
        assert ("E3", "E4") == PAIRWISE_COMPARISONS[0]  # key comparison first
        assert ("B3", "BEST_E") in PAIRWISE_COMPARISONS


# ---------------------------------------------------------------------------
# 7. Slices and diagnostics
# ---------------------------------------------------------------------------

class TestSlicesAndDiagnostics:
    def test_per_checkpoint_slice(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        slc = per_checkpoint_slice(eval_preds)
        assert set(slc) == {"E1", "E3", "E4", "E5"}
        for mid in slc:
            assert set(slc[mid]) == {"move_10", "move_20"}
            for cell in slc[mid].values():
                assert cell["n_rows"] == 10
                assert cell["log_loss"] >= 0

    def test_decisive_only_diagnostic(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        diag = decisive_only_diagnostic(eval_preds)
        # 20 val rows, 4 DRAW (i%5==2 -> 2 games x 2 rows) -> 16 decisive
        for mid, d in diag.items():
            assert d["n_rows"] == 16
            assert d["log_loss"] >= 0


# ---------------------------------------------------------------------------
# 8. Reference loading
# ---------------------------------------------------------------------------

class TestLoadBaselineReference:
    def test_loads_b1_b2_b3_only(self, tmp_path):
        preds = pl.DataFrame({
            "baseline_id": ["B1", "B2", "B3", "B0", "B4"],
            "split_set": ["val"] * 5,
            "game_id": ["g1"] * 5,
            "result_class": ["DRAW"] * 5,
            "pred_class": ["DRAW"] * 5,
            "p_BLACK_WIN": [0.3] * 5,
            "p_DRAW": [0.4] * 5,
            "p_WHITE_WIN": [0.3] * 5,
        })
        ppath = tmp_path / "preds.parquet"
        preds.write_parquet(ppath)
        results = {
            "baselines": {
                mid: {"metrics": {"val": {"log_loss": 0.9}}}
                for mid in ("B0", "B1", "B2", "B3", "B4")
            }
        }
        rpath = tmp_path / "results.json"
        rpath.write_text(json.dumps(results))

        loaded_preds, metrics = load_baseline_reference(ppath, rpath)
        assert sorted(loaded_preds["model_id"].unique().to_list()) == ["B1", "B2", "B3"]
        assert sorted(metrics) == ["B1", "B2", "B3"]

    def test_reference_ids_constant(self):
        assert REFERENCE_MODEL_IDS == ["B1", "B2", "B3"]


# ---------------------------------------------------------------------------
# 9. Report rendering
# ---------------------------------------------------------------------------

def _make_payload(modeling_df) -> dict:
    eval_results, eval_preds = run_all_eval_models(modeling_df)
    b3 = _make_ref_preds(modeling_df, "B3")
    b1 = _make_ref_preds(modeling_df, "B1")
    b2 = _make_ref_preds(modeling_df, "B2")
    combined = build_combined_predictions(
        eval_preds, pl.concat([b1, b2, b3])
    )
    best_e = select_best_e_model(eval_results)
    cis = run_bootstrap_cis(combined, n_replicates=10, seed=42)
    deltas = run_pairwise_deltas(combined, best_e, n_replicates=10, seed=42)
    ref_metrics = {
        mid: {"val": {"log_loss": 0.9, "accuracy": 0.5,
                      "macro_f1": 0.3, "multiclass_brier": 0.6}}
        for mid in ("B1", "B2", "B3")
    }
    return build_results_payload(
        dataset_id="synthetic_ds",
        version_tag="synthetic_v1",
        eval_results=eval_results,
        reference_metrics=ref_metrics,
        bootstrap_cis=cis,
        pairwise_deltas=deltas,
        checkpoint_slice=per_checkpoint_slice(eval_preds),
        decisive_diag=decisive_only_diagnostic(eval_preds),
        join_summary={"n_rows": 60,
                      "split_counts": {"train": 20, "val": 20, "test": 20}},
        sf_summary={"n_rows": 60, "n_terminal_depth0": 3,
                    "statuses": ["ok_cp", "ok_mate"], "cp_range": [-255, 10000]},
        best_e=best_e,
        artifact_paths={"results_json": "x.json"},
        n_replicates=10,
        seed=42,
        dataset_stats=compute_dataset_stats(modeling_df),
        overlap_stats=compute_lichess_overlap_stats(modeling_df),
        per_checkpoint_deltas=per_checkpoint_key_deltas(
            eval_preds, n_replicates=10, seed=42
        ),
    )


class TestRenderReport:
    @pytest.fixture(scope="class")
    def payload(self):
        return _make_payload(derive_eval_features(
            join_sf_features(make_feature_df(), make_sf_df())
        ))

    def test_required_caveats_present(self, payload):
        text = render_report(payload)
        for phrase in (
            "not ground truth and not a causal variable",
            "predictive associations, not causal effects",
            "per-checkpoint slices are reported",
            "DRAW metrics are directional only",
            "Test split was not used for model selection",
        ):
            assert phrase in text, phrase

    def test_terminal_depth0_caveat_present(self, payload):
        text = render_report(payload)
        assert "sf_depth=0" in text
        assert "not evaluation failures" in text

    def test_per_checkpoint_slice_section(self, payload):
        text = render_report(payload)
        assert "## 9. Per-Checkpoint-Type Slice" in text

    def test_lichess_overlap_appendix_uses_payload(self, payload):
        text = render_report(payload)
        ov = payload["lichess_overlap_stats"]
        # computed from the synthetic run, not pilot literals
        assert f"{ov['n_overlap']:,} of " in text
        assert "95.1%" not in text
        assert "68.8" not in text

    def test_no_pilot_literals_in_synthetic_report(self, payload):
        text = render_report(payload)
        for literal in ("6,205", "931 rows", "348 games", "59/931",
                        "27 of 6,205", "95.1%", "68.8"):
            assert literal not in text, literal

    def test_forbidden_claims_absent(self, payload):
        text = render_report(payload)
        for phrase in (
            "Stockfish proves", "is ground truth", "DRAW solved",
            "DRAW is solved", "degradation curves are established",
            "Phase 9 complete", "causes wins",
        ):
            assert phrase not in text, phrase

    def test_no_gbm_claims(self, payload):
        text = render_report(payload)
        assert "no GBMs were trained" in text

    def test_deterministic_rendering(self, payload):
        assert render_report(payload) == render_report(payload)

    def test_no_timestamp_in_report_body(self, payload):
        text = render_report(payload)
        assert "created_at" not in text
        import re
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", text)

    def test_all_required_sections(self, payload):
        text = render_report(payload)
        for i, title in enumerate([
            "ELI5 / TLDR", "Research Question", "Data and Join Integrity",
            "Eval Feature Semantics", "Models / Feature Sets",
            "Validation Metrics", "Game-Level Bootstrap CIs",
            "Pairwise Delta Results", "Per-Checkpoint-Type Slice",
            "Lichess Eval Overlap Appendix", "DRAW Caveat and Metrics",
            "Terminal Position / sf_depth=0 Caveat",
            "Scientific Interpretation", "Forbidden Claims / Limitations",
            "Reproducibility",
        ], start=1):
            assert f"## {i}. {title}" in text, title

    def test_key_comparison_in_report(self, payload):
        text = render_report(payload)
        assert "E3 → E4" in text or "E3 -> E4" in text


# ---------------------------------------------------------------------------
# 10. Artifact safety
# ---------------------------------------------------------------------------

class TestArtifacts:
    def test_write_outputs_creates_files(self, modeling_df, tmp_path):
        payload = _make_payload(modeling_df)
        _, eval_preds = run_all_eval_models(modeling_df)
        text = render_report(payload)
        rj = tmp_path / "results.json"
        pp = tmp_path / "preds.parquet"
        rm = tmp_path / "report.md"
        write_outputs(payload, eval_preds, text, rj, pp, rm)
        assert rj.exists() and pp.exists() and rm.exists()

    def test_overwrite_guard(self, modeling_df, tmp_path):
        payload = _make_payload(modeling_df)
        _, eval_preds = run_all_eval_models(modeling_df)
        text = render_report(payload)
        rj = tmp_path / "results.json"
        pp = tmp_path / "preds.parquet"
        rm = tmp_path / "report.md"
        write_outputs(payload, eval_preds, text, rj, pp, rm)
        with pytest.raises(FileExistsError):
            write_outputs(payload, eval_preds, text, rj, pp, rm)
        write_outputs(payload, eval_preds, text, rj, pp, rm, overwrite=True)

    def test_results_json_schema(self, modeling_df, tmp_path):
        payload = _make_payload(modeling_df)
        _, eval_preds = run_all_eval_models(modeling_df)
        rj = tmp_path / "results.json"
        write_outputs(payload, eval_preds, render_report(payload),
                      rj, tmp_path / "p.parquet", tmp_path / "r.md")
        loaded = json.loads(rj.read_text())
        for key in ("dataset_id", "version_tag", "eval_models", "feature_sets",
                    "pairwise_deltas", "bootstrap_cis", "best_e_model",
                    "artifact_paths", "caveats", "join_summary"):
            assert key in loaded, key

    def test_predictions_parquet_schema(self, modeling_df, tmp_path):
        payload = _make_payload(modeling_df)
        _, eval_preds = run_all_eval_models(modeling_df)
        pp = tmp_path / "p.parquet"
        write_outputs(payload, eval_preds, render_report(payload),
                      tmp_path / "r.json", pp, tmp_path / "r.md")
        loaded = pl.read_parquet(pp)
        required = {"model_id", "split_set", "game_id",
                    "selected_position_type", "result_class", "y_true",
                    "p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"}
        assert required.issubset(set(loaded.columns))

    def test_data_artifacts_gitignored(self):
        repo = Path(__file__).resolve().parents[1]
        for rel in (
            "data/processed/eval_conditioned_results_2024_09_25k_v1.json",
            "data/processed/eval_conditioned_predictions_2024_09_25k_v1.parquet",
        ):
            proc = subprocess.run(
                ["git", "check-ignore", rel],
                cwd=repo, capture_output=True, text=True,
            )
            assert proc.returncode == 0, f"{rel} is not gitignored"

    def test_payload_caveats_include_required_language(self, modeling_df):
        payload = _make_payload(modeling_df)
        joined = " ".join(payload["caveats"])
        assert "not ground truth" in joined
        assert "not causal effects" in joined
        assert "cautiously" in joined
        assert "Test split was not used" in joined
        assert "sf_depth=0" in joined

    def test_caveats_use_computed_draw_counts(self, modeling_df):
        payload = _make_payload(modeling_df)
        ds = payload["dataset_stats"]
        joined = " ".join(payload["caveats"])
        assert f"{ds['n_val_draw_rows']}/{ds['n_val_rows']} val rows" in joined


# ---------------------------------------------------------------------------
# 11. New stats functions (9.1B parameterization)
# ---------------------------------------------------------------------------

class TestDatasetStats:
    def test_basic_counts(self, modeling_df):
        ds = compute_dataset_stats(modeling_df)
        assert ds["n_rows"] == 60
        assert ds["n_val_rows"] == 20
        assert ds["n_val_games"] == 10
        # i in 10..19, DRAW when i%5==2 -> i=12,17 -> 2 games x 2 rows
        assert ds["n_val_draw_rows"] == 4

    def test_checkpoint_decidedness(self, modeling_df):
        ds = compute_dataset_stats(modeling_df)
        assert set(ds["checkpoint_decidedness"]) == {"move_10", "move_20"}
        for cell in ds["checkpoint_decidedness"].values():
            assert 0.0 <= cell["frac_abs_cp_ge_300"] <= 1.0

    def test_terminal_count_from_depth(self, feature_df, sf_df):
        sf_term = sf_df.with_columns(
            pl.when(pl.col("game_id") == "g000")
            .then(pl.lit(0)).otherwise(pl.col("sf_depth"))
            .alias("sf_depth")
        )
        mdf = derive_eval_features(join_sf_features(feature_df, sf_term))
        ds = compute_dataset_stats(mdf)
        assert ds["n_terminal_depth0"] == 2


class TestLichessOverlapStats:
    def test_overlap_computed(self, modeling_df):
        ov = compute_lichess_overlap_stats(modeling_df)
        assert ov["available"] is True
        assert ov["n_overlap"] == 10  # i%3==0, move_10, non-mate
        assert ov["n_nonmate"] == 10
        assert 0.0 <= ov["sign_agreement_frac"] <= 1.0
        assert ov["mean_abs_cp_diff"] == 30.0

    def test_no_overlap_column(self):
        df = pl.DataFrame({"sf_eval_cp": [10], "sf_eval_status": ["ok_cp"]})
        ov = compute_lichess_overlap_stats(df)
        assert ov["available"] is False

    def test_zero_overlap_rows(self, modeling_df):
        no_ov = modeling_df.with_columns(
            pl.lit(False).alias("has_lichess_eval")
        )
        ov = compute_lichess_overlap_stats(no_ov)
        assert ov["available"] is False


class TestPerCheckpointKeyDeltas:
    def test_deltas_per_checkpoint(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        deltas = per_checkpoint_key_deltas(eval_preds, n_replicates=10, seed=42)
        assert set(deltas) == {"move_10", "move_20"}
        for d in deltas.values():
            assert d["model_a"] == "E3" and d["model_b"] == "E4"
            assert d["ci_lower"] <= d["ci_upper"]
            assert d["contains_zero"] == (d["ci_lower"] <= 0.0 <= d["ci_upper"])

    def test_game_level_clusters_within_checkpoint(self, modeling_df):
        _, eval_preds = run_all_eval_models(modeling_df)
        deltas = per_checkpoint_key_deltas(eval_preds, n_replicates=10, seed=42)
        # 10 val games, each with exactly 1 row per checkpoint type
        assert deltas["move_10"]["n_common_games"] == 10


class TestParseExpectedSplitCounts:
    def test_valid(self):
        assert parse_expected_split_counts("train=10,val=5,test=5") == {
            "train": 10, "val": 5, "test": 5
        }

    def test_missing_split_raises(self):
        with pytest.raises(ValueError):
            parse_expected_split_counts("train=10,val=5")

    def test_unknown_split_raises(self):
        with pytest.raises(ValueError, match="Unknown split"):
            parse_expected_split_counts("train=10,val=5,holdout=5")

    def test_malformed_raises(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_expected_split_counts("train:10,val=5,test=5")


# ---------------------------------------------------------------------------
# 12. End-to-end CLI on synthetic non-pilot-sized data
# ---------------------------------------------------------------------------

def _write_cli_fixtures(tmp_path, modeling_seed_df, feature_df, sf_df):
    """Write synthetic input files for a main() invocation."""
    fpath = tmp_path / "features.parquet"
    spath = tmp_path / "sf.parquet"
    feature_df.write_parquet(fpath)
    sf_df.write_parquet(spath)

    # baseline predictions aligned with the modeling row order
    frames = []
    for mid in ("B1", "B2", "B3"):
        n = len(modeling_seed_df)
        frames.append(pl.DataFrame({
            "baseline_id": [mid] * n,
            "split_set": modeling_seed_df["split_set"],
            "game_id": modeling_seed_df["game_id"],
            "result_class": modeling_seed_df["result_class"],
            "pred_class": ["WHITE_WIN"] * n,
            "p_BLACK_WIN": [0.3] * n,
            "p_DRAW": [0.2] * n,
            "p_WHITE_WIN": [0.5] * n,
        }))
    bp = tmp_path / "baseline_preds.parquet"
    pl.concat(frames).write_parquet(bp)

    br = tmp_path / "baseline_results.json"
    br.write_text(json.dumps({
        "baselines": {
            mid: {"metrics": {"val": {
                "log_loss": 0.9, "accuracy": 0.5,
                "macro_f1": 0.3, "multiclass_brier": 0.6,
            }}}
            for mid in ("B1", "B2", "B3")
        }
    }))
    return fpath, spath, bp, br


class TestEndToEndCLI:
    @pytest.fixture
    def cli_paths(self, tmp_path, feature_df, sf_df):
        modeling_seed = join_sf_features(feature_df, sf_df)
        return tmp_path, _write_cli_fixtures(
            tmp_path, modeling_seed, feature_df, sf_df
        )

    def _argv(self, tmp_path, fpath, spath, bp, br, extra=None):
        argv = [
            "--dataset-id", "synthetic_ds",
            "--version-tag", "synthetic_v9",
            "--features", str(fpath),
            "--sf-eval", str(spath),
            "--baseline-predictions", str(bp),
            "--baseline-results", str(br),
            "--output-results", str(tmp_path / "out_results.json"),
            "--output-predictions", str(tmp_path / "out_preds.parquet"),
            "--output-report", str(tmp_path / "out_report.md"),
            "--n-replicates", "5",
            "--overwrite",
        ]
        return argv + (extra or [])

    def test_runs_on_non_pilot_counts(self, cli_paths):
        tmp_path, (fpath, spath, bp, br) = cli_paths
        # 60 rows != 6,205 — must work without pilot assertions
        rc = ecm_main(self._argv(tmp_path, fpath, spath, bp, br))
        assert rc == 0
        report = (tmp_path / "out_report.md").read_text()
        assert "60" in report
        for literal in ("6,205", "95.1%", "68.8", "59/931"):
            assert literal not in report, literal

    def test_explicit_expected_rows_pass(self, cli_paths):
        tmp_path, (fpath, spath, bp, br) = cli_paths
        rc = ecm_main(self._argv(
            tmp_path, fpath, spath, bp, br,
            extra=["--expected-primary-rows", "60",
                   "--expected-split-counts", "train=20,val=20,test=20"],
        ))
        assert rc == 0

    def test_explicit_expected_rows_mismatch_fails(self, cli_paths):
        tmp_path, (fpath, spath, bp, br) = cli_paths
        with pytest.raises(ValueError, match="Expected 6205 joined rows"):
            ecm_main(self._argv(
                tmp_path, fpath, spath, bp, br,
                extra=["--expected-primary-rows", "6205"],
            ))

    def test_expected_split_mismatch_fails(self, cli_paths):
        tmp_path, (fpath, spath, bp, br) = cli_paths
        with pytest.raises(ValueError, match="Expected split counts"):
            ecm_main(self._argv(
                tmp_path, fpath, spath, bp, br,
                extra=["--expected-split-counts", "train=4344,val=931,test=930"],
            ))

    def test_results_json_has_new_fields(self, cli_paths):
        tmp_path, (fpath, spath, bp, br) = cli_paths
        ecm_main(self._argv(tmp_path, fpath, spath, bp, br))
        res = json.loads((tmp_path / "out_results.json").read_text())
        for key in ("dataset_stats", "lichess_overlap_stats",
                    "per_checkpoint_key_deltas", "pilot_reference"):
            assert key in res, key
        assert res["pilot_reference"]["e3_e4_delta"] == PILOT_E3_E4_DELTA
