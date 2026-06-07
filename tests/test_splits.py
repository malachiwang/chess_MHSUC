"""tests/test_splits.py — Unit tests for splits.py (Ticket 5.1B).

Uses synthetic Polars DataFrames and tmp_path only. No real data files.
Covers functions A through N per the Ticket 5.1B specification.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from chess_mhsuc.splits import (
    apply_split_to_df,
    build_baseline_plan,
    build_feature_sets,
    build_game_level_df,
    build_metric_policy,
    build_modeling_plan,
    build_view_policy,
    check_split_balance,
    filter_training_view,
    get_train_val_test,
    load_split_assignments,
    save_split_artifacts,
    stratified_game_split,
    validate_split_assignments,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_feature_df(n_ww: int = 24, n_bw: int = 24, n_draw: int = 12) -> pl.DataFrame:
    """
    Synthetic feature DataFrame for testing.

    Each game contributes 4 rows: move_10, move_20, move_30 (numbered) and last.
    Every 5th game's last row is flagged as a duplicate_ply_checkpoint.
    """
    rows = []
    gid = 0
    for rc, count in [("WHITE_WIN", n_ww), ("BLACK_WIN", n_bw), ("DRAW", n_draw)]:
        for i in range(count):
            gid += 1
            game_id = f"g{gid:04d}"
            for j, cp_type in enumerate(["move_10", "move_20", "move_30", "last"]):
                is_last = cp_type == "last"
                # Every 5th game: last row is a dup checkpoint
                dup = is_last and (i % 5 == 0)
                rows.append({
                    "game_id": game_id,
                    "result_class": rc,
                    "has_eval": j == 0,          # move_10 rows have eval
                    "selected_position_type": cp_type,
                    "duplicate_ply_checkpoint": dup,
                    "is_last_checkpoint": is_last,
                    "move_number": (j + 1) * 10,
                    "phase": "opening" if j == 0 else ("middlegame" if j < 3 else "endgame"),
                    "checkpoint_index": j,
                    "phase_index": j,
                })
    return pl.DataFrame(rows)


@pytest.fixture
def feature_df() -> pl.DataFrame:
    return _make_feature_df()


@pytest.fixture
def game_df(feature_df: pl.DataFrame) -> pl.DataFrame:
    return build_game_level_df(feature_df)


@pytest.fixture
def assignments(game_df: pl.DataFrame) -> dict[str, str]:
    return stratified_game_split(game_df, seed=42)


def _minimal_modeling_plan(version_tag: str = "test_v1") -> dict:
    return {
        "dataset_id": "test_dataset",
        "version_tag": version_tag,
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "split_policy": {
            "split_unit": "game_id",
            "train_frac": 0.70,
            "val_frac": 0.15,
            "test_frac": 0.15,
            "seed": 42,
        },
    }


# ---------------------------------------------------------------------------
# A. build_game_level_df
# ---------------------------------------------------------------------------


class TestBuildGameLevelDf:
    def test_one_row_per_game(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        assert len(result) == feature_df["game_id"].n_unique()

    def test_expected_columns(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        expected = {
            "game_id", "result_class", "has_eval_game",
            "n_rows", "n_numbered_rows", "n_last_rows",
            "has_duplicate_ply_checkpoint",
        }
        assert expected <= set(result.columns)

    def test_result_class_values(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        assert set(result["result_class"].unique().to_list()) == {"WHITE_WIN", "BLACK_WIN", "DRAW"}

    def test_n_rows_sums_to_feature_df(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        assert result["n_rows"].sum() == len(feature_df)

    def test_n_numbered_and_last_per_game(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        # Fixture: 3 numbered + 1 last per game
        assert (result["n_numbered_rows"] == 3).all()
        assert (result["n_last_rows"] == 1).all()

    def test_sorted_by_game_id(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        game_ids = result["game_id"].to_list()
        assert game_ids == sorted(game_ids)

    def test_raises_on_inconsistent_result_class(self) -> None:
        df = pl.DataFrame({
            "game_id": ["gX", "gX"],
            "result_class": ["WHITE_WIN", "BLACK_WIN"],
            "has_eval": [False, False],
            "selected_position_type": ["move_10", "last"],
            "duplicate_ply_checkpoint": [False, False],
            "is_last_checkpoint": [False, True],
            "move_number": [10, 40],
            "phase": ["opening", "endgame"],
            "checkpoint_index": [0, 3],
            "phase_index": [0, 3],
        })
        with pytest.raises(ValueError, match="multiple result_class"):
            build_game_level_df(df)

    def test_has_eval_game_is_any(self) -> None:
        df = pl.DataFrame({
            "game_id":                  ["g001", "g001", "g002", "g002"],
            "result_class":             ["WHITE_WIN", "WHITE_WIN", "BLACK_WIN", "BLACK_WIN"],
            "has_eval":                 [True, False, False, False],
            "selected_position_type":   ["move_10", "last", "move_10", "last"],
            "duplicate_ply_checkpoint": [False, False, False, False],
            "is_last_checkpoint":       [False, True, False, True],
            "move_number":              [10, 40, 10, 40],
            "phase":                    ["opening", "endgame", "opening", "endgame"],
            "checkpoint_index":         [0, 3, 0, 3],
            "phase_index":              [0, 3, 0, 3],
        })
        result = build_game_level_df(df)
        g1 = result.filter(pl.col("game_id") == "g001")["has_eval_game"][0]
        g2 = result.filter(pl.col("game_id") == "g002")["has_eval_game"][0]
        assert g1 == True
        assert g2 == False

    def test_has_duplicate_ply_checkpoint_is_any(self, feature_df: pl.DataFrame) -> None:
        result = build_game_level_df(feature_df)
        # Some games have dup=True (every 5th game in the fixture)
        assert result["has_duplicate_ply_checkpoint"].any()


# ---------------------------------------------------------------------------
# B. stratified_game_split
# ---------------------------------------------------------------------------


class TestStratifiedGameSplit:
    def test_all_games_assigned(self, game_df: pl.DataFrame) -> None:
        a = stratified_game_split(game_df, seed=42)
        assert set(a.keys()) == set(game_df["game_id"].to_list())

    def test_valid_split_values(self, game_df: pl.DataFrame) -> None:
        a = stratified_game_split(game_df, seed=42)
        assert set(a.values()) <= {"train", "val", "test"}

    def test_all_splits_nonempty(self, game_df: pl.DataFrame) -> None:
        a = stratified_game_split(game_df, seed=42)
        for s in ("train", "val", "test"):
            assert sum(1 for v in a.values() if v == s) > 0

    def test_approximate_70_15_15_ratio(self, game_df: pl.DataFrame) -> None:
        a = stratified_game_split(game_df, train_frac=0.70, val_frac=0.15, seed=42)
        n = len(game_df)
        n_train = sum(1 for v in a.values() if v == "train")
        n_val   = sum(1 for v in a.values() if v == "val")
        n_test  = sum(1 for v in a.values() if v == "test")
        assert abs(n_train / n - 0.70) < 0.06
        assert abs(n_val   / n - 0.15) < 0.06
        assert abs(n_test  / n - 0.15) < 0.06

    def test_reproducible_same_seed(self, game_df: pl.DataFrame) -> None:
        a1 = stratified_game_split(game_df, seed=42)
        a2 = stratified_game_split(game_df, seed=42)
        assert a1 == a2

    def test_different_seeds_differ(self, game_df: pl.DataFrame) -> None:
        a1 = stratified_game_split(game_df, seed=42)
        a2 = stratified_game_split(game_df, seed=999)
        assert a1 != a2

    def test_all_classes_represented_in_each_split(
        self, game_df: pl.DataFrame
    ) -> None:
        a = stratified_game_split(game_df, seed=42)
        assign_series = pl.Series(
            "split_set",
            [a[gid] for gid in game_df["game_id"].to_list()],
        )
        merged = game_df.with_columns(assign_series)
        for split in ("train", "val", "test"):
            classes = (
                merged.filter(pl.col("split_set") == split)["result_class"]
                .unique()
                .to_list()
            )
            assert "DRAW" in classes, f"DRAW missing from split '{split}'"

    def test_raises_invalid_train_frac_zero(self, game_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="train_frac"):
            stratified_game_split(game_df, train_frac=0.0)

    def test_raises_invalid_val_frac_zero(self, game_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="val_frac"):
            stratified_game_split(game_df, val_frac=0.0)

    def test_raises_fracs_exceed_one(self, game_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="test_frac"):
            stratified_game_split(game_df, train_frac=0.90, val_frac=0.15)

    def test_raises_missing_game_id_col(self, game_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="game_id"):
            stratified_game_split(game_df.drop("game_id"))

    def test_raises_missing_stratify_col(self, game_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="result_class"):
            stratified_game_split(game_df.drop("result_class"))


# ---------------------------------------------------------------------------
# C. validate_split_assignments
# ---------------------------------------------------------------------------


class TestValidateSplitAssignments:
    def test_valid_passes(self, game_df: pl.DataFrame, assignments: dict) -> None:
        result = validate_split_assignments(assignments, game_df["game_id"].to_list())
        assert result["passed"] is True
        assert result["missing_game_ids"] == []
        assert result["extra_game_ids"] == []
        assert result["invalid_split_values"] == []

    def test_split_counts_sum_to_total(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = validate_split_assignments(assignments, game_df["game_id"].to_list())
        sc = result["split_counts"]
        assert sc["train"] + sc["val"] + sc["test"] == len(game_df)

    def test_detects_missing_game_id(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        missing_id = game_df["game_id"][0]
        reduced = {k: v for k, v in assignments.items() if k != missing_id}
        result = validate_split_assignments(reduced, game_df["game_id"].to_list())
        assert result["passed"] is False
        assert missing_id in result["missing_game_ids"]

    def test_detects_extra_game_id(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        extra = dict(assignments)
        extra["GHOST_GAME"] = "train"
        result = validate_split_assignments(extra, game_df["game_id"].to_list())
        assert result["passed"] is False
        assert "GHOST_GAME" in result["extra_game_ids"]

    def test_detects_invalid_split_value(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        bad = dict(assignments)
        first_key = next(iter(bad))
        bad[first_key] = "splat"
        result = validate_split_assignments(bad, game_df["game_id"].to_list())
        assert result["passed"] is False
        assert "splat" in result["invalid_split_values"]

    def test_n_expected_and_assigned(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = validate_split_assignments(assignments, game_df["game_id"].to_list())
        assert result["n_expected_games"] == len(game_df)
        assert result["n_assigned_games"] == len(assignments)


# ---------------------------------------------------------------------------
# D. check_split_balance
# ---------------------------------------------------------------------------


class TestCheckSplitBalance:
    def test_all_splits_present(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = check_split_balance(assignments, game_df)
        assert set(result["splits"].keys()) == {"train", "val", "test"}

    def test_label_counts_sum_to_n_games(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = check_split_balance(assignments, game_df)
        for split, stats in result["splits"].items():
            total = sum(stats["label_counts"].values())
            assert total == stats["n_games"]

    def test_draw_count_in_stats(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = check_split_balance(assignments, game_df)
        for split in ("train", "val", "test"):
            assert "draw_count" in result["splits"][split]

    def test_warnings_is_list(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = check_split_balance(assignments, game_df)
        assert isinstance(result["warnings"], list)

    def test_warns_low_draw_in_val_test(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        # With 12 DRAW games / 60 total (seed=42), val and test each get ~2 DRAW < 8
        result = check_split_balance(assignments, game_df)
        draw_warns = [w for w in result["warnings"] if "DRAW" in w]
        assert len(draw_warns) > 0

    def test_warns_zero_draw(self) -> None:
        # Force all DRAW games into train; val and test have zero DRAW
        df = _make_feature_df(n_ww=10, n_bw=10, n_draw=4)
        gdf = build_game_level_df(df)
        asgn: dict[str, str] = {}
        non_draw_count = 0
        for row in gdf.to_dicts():
            if row["result_class"] == "DRAW":
                asgn[row["game_id"]] = "train"
            elif non_draw_count % 2 == 0:
                asgn[row["game_id"]] = "val"
                non_draw_count += 1
            else:
                asgn[row["game_id"]] = "test"
                non_draw_count += 1
        result = check_split_balance(asgn, gdf)
        zero_draw_warns = [
            w for w in result["warnings"]
            if "ZERO DRAW" in w or "zero games for class 'DRAW'" in w
        ]
        assert len(zero_draw_warns) > 0

    def test_label_pcts_sum_near_100(
        self, game_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = check_split_balance(assignments, game_df)
        for split, stats in result["splits"].items():
            total_pct = sum(stats["label_pcts"].values())
            assert abs(total_pct - 100.0) < 1.0


# ---------------------------------------------------------------------------
# E. apply_split_to_df
# ---------------------------------------------------------------------------


class TestApplySplitToDf:
    def test_adds_split_set_column(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = apply_split_to_df(feature_df, assignments)
        assert "split_set" in result.columns

    def test_preserves_row_count(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = apply_split_to_df(feature_df, assignments)
        assert len(result) == len(feature_df)

    def test_split_values_valid(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        result = apply_split_to_df(feature_df, assignments)
        assert set(result["split_set"].unique().to_list()) <= {"train", "val", "test"}

    def test_raises_missing_assignment(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        first_game = feature_df["game_id"][0]
        reduced = {k: v for k, v in assignments.items() if k != first_game}
        with pytest.raises(ValueError, match="no split assignment"):
            apply_split_to_df(feature_df, reduced)


# ---------------------------------------------------------------------------
# F. filter_training_view
# ---------------------------------------------------------------------------


class TestFilterTrainingView:
    def test_primary_numbered_removes_last(
        self, feature_df: pl.DataFrame
    ) -> None:
        result = filter_training_view(feature_df, "primary_numbered")
        assert "last" not in result["selected_position_type"].unique().to_list()

    def test_primary_numbered_keeps_numbered_rows(
        self, feature_df: pl.DataFrame
    ) -> None:
        result = filter_training_view(feature_df, "primary_numbered")
        # Each game had 3 numbered rows; all should be kept
        n_games = feature_df["game_id"].n_unique()
        assert len(result) == n_games * 3

    def test_dedup_removes_dup_last(self, feature_df: pl.DataFrame) -> None:
        result = filter_training_view(feature_df, "all_checkpoints_dedup")
        bad = result.filter(
            (pl.col("duplicate_ply_checkpoint") == True)
            & (pl.col("is_last_checkpoint") == True)
        )
        assert len(bad) == 0

    def test_dedup_keeps_non_dup_last(self, feature_df: pl.DataFrame) -> None:
        result = filter_training_view(feature_df, "all_checkpoints_dedup")
        kept_last = result.filter(
            (pl.col("is_last_checkpoint") == True)
            & (pl.col("duplicate_ply_checkpoint") == False)
        )
        assert len(kept_last) > 0

    def test_dedup_fewer_rows_than_raw(self, feature_df: pl.DataFrame) -> None:
        dedup = filter_training_view(feature_df, "all_checkpoints_dedup")
        raw   = filter_training_view(feature_df, "all_checkpoints_raw")
        assert len(dedup) < len(raw)

    def test_raw_preserves_all_rows(self, feature_df: pl.DataFrame) -> None:
        result = filter_training_view(feature_df, "all_checkpoints_raw")
        assert len(result) == len(feature_df)

    def test_raises_unknown_view(self, feature_df: pl.DataFrame) -> None:
        with pytest.raises(ValueError, match="Unknown view_name"):
            filter_training_view(feature_df, "bogus_view")


# ---------------------------------------------------------------------------
# G. get_train_val_test
# ---------------------------------------------------------------------------


class TestGetTrainValTest:
    def test_returns_three_dataframes(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        train, val, test = get_train_val_test(feature_df, assignments)
        for df in (train, val, test):
            assert isinstance(df, pl.DataFrame)

    def test_no_game_id_overlap(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        train, val, test = get_train_val_test(feature_df, assignments)
        train_ids = set(train["game_id"].unique().to_list())
        val_ids   = set(val["game_id"].unique().to_list())
        test_ids  = set(test["game_id"].unique().to_list())
        assert len(train_ids & val_ids) == 0
        assert len(train_ids & test_ids) == 0
        assert len(val_ids & test_ids) == 0

    def test_all_partitions_nonempty(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        train, val, test = get_train_val_test(feature_df, assignments)
        for df in (train, val, test):
            assert len(df) > 0

    def test_primary_numbered_view_applied(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        train, val, test = get_train_val_test(feature_df, assignments, "primary_numbered")
        for df in (train, val, test):
            assert "last" not in df["selected_position_type"].unique().to_list()

    def test_raw_view_total_rows(
        self, feature_df: pl.DataFrame, assignments: dict
    ) -> None:
        train, val, test = get_train_val_test(feature_df, assignments, "all_checkpoints_raw")
        assert len(train) + len(val) + len(test) == len(feature_df)


# ---------------------------------------------------------------------------
# H. build_feature_sets
# ---------------------------------------------------------------------------


class TestBuildFeatureSets:
    @pytest.fixture
    def fsets(self) -> dict:
        return build_feature_sets({})

    def test_all_ids_present(self, fsets: dict) -> None:
        for fs_id in ("FS-A", "FS-B", "FS-C", "FS-D", "FS-E", "FS-F", "FS-G"):
            assert fs_id in fsets

    def test_each_has_required_keys(self, fsets: dict) -> None:
        for fs_id, fs in fsets.items():
            for key in ("id", "name", "table", "view", "features", "description"):
                assert key in fs, f"{fs_id} missing key '{key}'"

    def test_fs_a_empty_features(self, fsets: dict) -> None:
        assert fsets["FS-A"]["features"] == []

    def test_fs_b_rating_cols(self, fsets: dict) -> None:
        assert set(fsets["FS-B"]["features"]) == {"white_elo", "black_elo", "elo_diff", "avg_elo"}

    def test_fs_c_excludes_raw_clocks(self, fsets: dict) -> None:
        fs_c = fsets["FS-C"]["features"]
        assert "white_clock_s" not in fs_c
        assert "black_clock_s" not in fs_c
        assert "white_clock_s_capped" in fs_c
        assert "black_clock_s_capped" in fs_c

    def test_fs_f_uses_eval_clipped(self, fsets: dict) -> None:
        assert "eval_cp_clipped" in fsets["FS-F"]["features"]
        assert "eval_mate_abs" in fsets["FS-F"]["features"]

    def test_fs_f_and_g_are_eval_table(self, fsets: dict) -> None:
        assert fsets["FS-F"]["table"] == "eval"
        assert fsets["FS-G"]["table"] == "eval"

    def test_broad_tables_for_a_e(self, fsets: dict) -> None:
        for fs_id in ("FS-A", "FS-B", "FS-C", "FS-D", "FS-E"):
            assert fsets[fs_id]["table"] == "broad"

    def test_fs_e_is_superset_of_b_c_d(self, fsets: dict) -> None:
        fs_e = set(fsets["FS-E"]["features"])
        for fs_id in ("FS-B", "FS-C", "FS-D"):
            for col in fsets[fs_id]["features"]:
                assert col in fs_e, f"{col} from {fs_id} missing in FS-E"


# ---------------------------------------------------------------------------
# I. build_metric_policy
# ---------------------------------------------------------------------------


class TestBuildMetricPolicy:
    @pytest.fixture
    def mp(self) -> dict:
        return build_metric_policy()

    def test_primary_metrics_present(self, mp: dict) -> None:
        names = [m["name"] for m in mp["primary_metrics"]]
        assert "log_loss" in names
        assert "macro_f1" in names
        assert "per_class_precision_recall_f1" in names

    def test_accuracy_is_secondary_not_primary(self, mp: dict) -> None:
        primary_names   = [m["name"] for m in mp["primary_metrics"]]
        secondary_names = [m["name"] for m in mp["secondary_metrics"]]
        assert "accuracy" not in primary_names
        assert "accuracy" in secondary_names

    def test_accuracy_caveat_says_secondary(self, mp: dict) -> None:
        assert "accuracy_caveat" in mp
        assert "SECONDARY" in mp["accuracy_caveat"]

    def test_deferred_list(self, mp: dict) -> None:
        assert isinstance(mp["deferred"], list)
        assert len(mp["deferred"]) > 0


# ---------------------------------------------------------------------------
# J. build_baseline_plan
# ---------------------------------------------------------------------------


class TestBuildBaselinePlan:
    @pytest.fixture
    def bp(self) -> dict:
        return build_baseline_plan(build_feature_sets({}))

    def test_b0_through_b5_present(self, bp: dict) -> None:
        for bid in ("B0", "B1", "B2", "B3", "B4", "B5"):
            assert bid in bp

    def test_b0_b1_are_dummy_classifier(self, bp: dict) -> None:
        assert bp["B0"]["model"] == "DummyClassifier"
        assert bp["B1"]["model"] == "DummyClassifier"

    def test_b0_most_frequent_strategy(self, bp: dict) -> None:
        assert bp["B0"]["sklearn_params"]["strategy"] == "most_frequent"

    def test_b2_b5_are_logistic_regression(self, bp: dict) -> None:
        for bid in ("B2", "B3", "B4", "B5"):
            assert bp[bid]["model"] == "LogisticRegression"

    def test_b4_b5_eval_exploratory(self, bp: dict) -> None:
        for bid in ("B4", "B5"):
            assert bp[bid]["table"] == "eval"
            assert bp[bid]["exploratory"] is True

    def test_b0_b3_not_exploratory(self, bp: dict) -> None:
        for bid in ("B0", "B1", "B2", "B3"):
            assert bp[bid]["exploratory"] is False

    def test_global_notes_label_mapping(self, bp: dict) -> None:
        lm = bp["global_notes"]["label_mapping"]
        assert lm["BLACK_WIN"] == 0
        assert lm["DRAW"] == 1
        assert lm["WHITE_WIN"] == 2

    def test_lr_max_iter_1000(self, bp: dict) -> None:
        for bid in ("B2", "B3", "B4", "B5"):
            assert bp[bid]["sklearn_params"]["max_iter"] == 1000
            assert bp[bid]["sklearn_params"]["solver"] == "lbfgs"


# ---------------------------------------------------------------------------
# K. build_view_policy
# ---------------------------------------------------------------------------


class TestBuildViewPolicy:
    @pytest.fixture
    def vp(self) -> dict:
        return build_view_policy()

    def test_primary_view_is_primary_numbered(self, vp: dict) -> None:
        assert vp["primary_view"]["name"] == "primary_numbered"

    def test_deduplication_rule_references_dup_ply(self, vp: dict) -> None:
        assert "duplicate_ply_checkpoint" in vp["deduplication_rule"]

    def test_last_checkpoint_caveats_nonempty(self, vp: dict) -> None:
        assert isinstance(vp["last_checkpoint_caveats"], list)
        assert len(vp["last_checkpoint_caveats"]) > 0

    def test_secondary_views_include_expected_names(self, vp: dict) -> None:
        names = [v["name"] for v in vp["secondary_views"]]
        assert "all_checkpoints_dedup" in names
        assert "all_checkpoints_raw" in names


# ---------------------------------------------------------------------------
# L. build_modeling_plan
# ---------------------------------------------------------------------------


class TestBuildModelingPlan:
    @pytest.fixture
    def mplan(self) -> dict:
        split_summary = {
            "total_broad_games": 60,
            "total_eval_games": 12,
            "split_counts": {"train": 42, "val": 9, "test": 9},
            "broad_balance": {"splits": {}},
            "eval_split_counts": {"train": 8, "val": 2, "test": 2},
            "primary_view_rows": {"train": 126, "val": 27, "test": 27},
            "warnings": [],
        }
        return build_modeling_plan(
            dataset_id="test_dataset",
            version_tag="test_v1",
            feature_metadata={},
            split_summary=split_summary,
            seed=42,
            train_frac=0.70,
            val_frac=0.15,
        )

    def test_dataset_id(self, mplan: dict) -> None:
        assert mplan["dataset_id"] == "test_dataset"

    def test_split_policy_fields(self, mplan: dict) -> None:
        sp = mplan["split_policy"]
        assert sp["split_unit"] == "game_id"
        assert sp["train_frac"] == 0.70
        assert sp["val_frac"] == 0.15
        assert sp["seed"] == 42
        assert sp["no_row_level_splitting"] is True

    def test_feature_sets_present(self, mplan: dict) -> None:
        for fs_id in ("FS-A", "FS-B", "FS-C", "FS-D", "FS-E", "FS-F", "FS-G"):
            assert fs_id in mplan["feature_sets"]

    def test_baseline_plan_present(self, mplan: dict) -> None:
        for bid in ("B0", "B1", "B2", "B3", "B4", "B5"):
            assert bid in mplan["baseline_plan"]

    def test_json_serializable(self, mplan: dict) -> None:
        serialized = json.dumps(mplan)
        assert len(serialized) > 100

    def test_recommended_next_step_mentions_5_2(self, mplan: dict) -> None:
        assert "5.2" in mplan["recommended_next_step"]


# ---------------------------------------------------------------------------
# M. save_split_artifacts + load_split_assignments
# ---------------------------------------------------------------------------


class TestSaveLoadSplitArtifacts:
    def test_creates_splits_json(
        self, tmp_path: Path, assignments: dict
    ) -> None:
        paths = save_split_artifacts(
            assignments, _minimal_modeling_plan(), tmp_path, "test_v1"
        )
        assert Path(paths["splits_json"]).exists()

    def test_creates_modeling_plan_json(
        self, tmp_path: Path, assignments: dict
    ) -> None:
        paths = save_split_artifacts(
            assignments, _minimal_modeling_plan(), tmp_path, "test_v1"
        )
        assert Path(paths["modeling_plan_json"]).exists()

    def test_round_trip_assignments(
        self, tmp_path: Path, assignments: dict
    ) -> None:
        paths = save_split_artifacts(
            assignments, _minimal_modeling_plan(), tmp_path, "test_v1"
        )
        loaded = load_split_assignments(Path(paths["splits_json"]))
        assert loaded == assignments

    def test_splits_json_required_keys(
        self, tmp_path: Path, assignments: dict
    ) -> None:
        paths = save_split_artifacts(
            assignments, _minimal_modeling_plan(), tmp_path, "test_v1"
        )
        with open(paths["splits_json"]) as fh:
            data = json.load(fh)
        for key in (
            "version_tag", "split_unit", "seed",
            "train_frac", "val_frac", "test_frac", "assignments",
        ):
            assert key in data

    def test_no_parquet_written(
        self, tmp_path: Path, assignments: dict
    ) -> None:
        save_split_artifacts(
            assignments, _minimal_modeling_plan(), tmp_path, "test_v1"
        )
        assert list(tmp_path.glob("*.parquet")) == []


# ---------------------------------------------------------------------------
# N. CLI (main())
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(tmp_path: Path, feature_df: pl.DataFrame) -> dict[str, Any]:
    """Write synthetic Parquet + metadata files for CLI tests."""
    broad_path = tmp_path / "broad.parquet"
    eval_path  = tmp_path / "eval.parquet"
    meta_path  = tmp_path / "meta.json"
    output_dir = tmp_path / "processed"
    report_dir = tmp_path / "reports"

    feature_df.write_parquet(broad_path)

    # Eval: use first 15 games as the eval subset (strict subset of broad)
    eval_game_ids = sorted(feature_df["game_id"].unique().to_list())[:15]
    eval_df = feature_df.filter(pl.col("game_id").is_in(eval_game_ids))
    eval_df.write_parquet(eval_path)

    with open(meta_path, "w") as fh:
        json.dump({"default_predictive_features": [], "version_tag": "test_v1"}, fh)

    return {
        "broad_path": str(broad_path),
        "eval_path":  str(eval_path),
        "meta_path":  str(meta_path),
        "output_dir": str(output_dir),
        "report_dir": str(report_dir),
        "version_tag": "test_v1",
    }


def _run_cli(env: dict[str, Any]) -> int:
    from chess_mhsuc.splits import main
    return main([
        "--dataset-id",         "test_dataset",
        "--feature-broad",      env["broad_path"],
        "--feature-eval",       env["eval_path"],
        "--feature-metadata",   env["meta_path"],
        "--output-dir",         env["output_dir"],
        "--report-output-dir",  env["report_dir"],
        "--version-tag",        env["version_tag"],
        "--train-frac",         "0.70",
        "--val-frac",           "0.15",
        "--seed",               "42",
    ])


class TestCLI:
    def test_exits_zero(self, cli_env: dict) -> None:
        assert _run_cli(cli_env) == 0

    def test_creates_splits_json(self, cli_env: dict) -> None:
        _run_cli(cli_env)
        assert (Path(cli_env["output_dir"]) / "splits_test_v1.json").exists()

    def test_creates_modeling_plan_json(self, cli_env: dict) -> None:
        _run_cli(cli_env)
        assert (Path(cli_env["output_dir"]) / "modeling_plan_test_v1.json").exists()

    def test_creates_implementation_report(self, cli_env: dict) -> None:
        _run_cli(cli_env)
        report = (
            Path(cli_env["report_dir"])
            / "phase_5_1b_modeling_split_baseline_plan_implementation.md"
        )
        assert report.exists()

    def test_no_parquet_in_output_dir(self, cli_env: dict) -> None:
        _run_cli(cli_env)
        assert list(Path(cli_env["output_dir"]).glob("*.parquet")) == []

    def test_splits_json_valid_assignments(self, cli_env: dict) -> None:
        _run_cli(cli_env)
        splits_json = Path(cli_env["output_dir"]) / "splits_test_v1.json"
        with open(splits_json) as fh:
            data = json.load(fh)
        assert "assignments" in data
        assert set(data["assignments"].values()) <= {"train", "val", "test"}
        assert len(data["assignments"]) == 60  # fixture has 60 games
