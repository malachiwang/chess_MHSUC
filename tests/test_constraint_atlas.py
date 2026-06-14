"""Tests for constraint_atlas.py (Ticket 15.1B). Pure logic + small synthetic
frames; no Stockfish, no large data."""

from __future__ import annotations

import polars as pl
import pytest

from chess_mhsuc.constraint_atlas import (
    CLOCK_COARSE_ORDER,
    CLOCK_FINE_ORDER,
    EVAL_BAND_ORDER,
    LATE_CHECKPOINTS,
    bootstrap_mean_es_ci,
    cell_status,
    cell_summary,
    checkpoint_is_late,
    clock_bucket_coarse,
    clock_bucket_fine,
    eval_band,
    grouped_summary,
    load_atlas_frame,
    rating_bin,
    render_combined_report,
    render_month_report,
    termination_channel,
)


# ---------------------------------------------------------------------------
# 1. Clock bins
# ---------------------------------------------------------------------------

class TestClockBins:
    def test_coarse_normalization(self):
        assert clock_bucket_coarse("under_60s") == "under_60"
        assert clock_bucket_coarse("60_180s") == "60_180"
        assert clock_bucket_coarse("over_180s") == "over_180"
        assert clock_bucket_coarse(None) is None

    @pytest.mark.parametrize("s,expected", [
        (5.0, "<10"), (9.9, "<10"), (10.0, "10_30"), (29.9, "10_30"),
        (30.0, "30_60"), (59.9, "30_60"), (60.0, "60_180"), (179.9, "60_180"),
        (180.0, "over_180"), (600.0, "over_180"),
    ])
    def test_fine_boundaries(self, s, expected):
        assert clock_bucket_fine(s) == expected

    def test_fine_none(self):
        assert clock_bucket_fine(None) is None


# ---------------------------------------------------------------------------
# 2. Rating bins
# ---------------------------------------------------------------------------

class TestRatingBin:
    def test_200_width(self):
        assert rating_bin(1600) == "1600_1799"
        assert rating_bin(1799) == "1600_1799"
        assert rating_bin(1800) == "1800_1999"
        assert rating_bin(422) == "400_599"

    def test_none(self):
        assert rating_bin(None) is None

    def test_custom_width(self):
        assert rating_bin(1650, width=100) == "1600_1699"


# ---------------------------------------------------------------------------
# 3. Eval bands
# ---------------------------------------------------------------------------

class TestEvalBand:
    @pytest.mark.parametrize("cp,expected", [
        (0, "near_equal"), (100, "near_equal"), (-100, "near_equal"),
        (101, "slight"), (300, "slight"), (-300, "slight"),
        (301, "clear"), (700, "clear"),
        (701, "decided"), (1500, "decided"),
    ])
    def test_bands(self, cp, expected):
        assert eval_band(cp, False) == expected

    def test_mate_band_overrides(self):
        assert eval_band(50, True) == "mate_band"
        assert eval_band(10000, True) == "mate_band"

    def test_none(self):
        assert eval_band(None, False) is None

    def test_order_constant(self):
        assert EVAL_BAND_ORDER == ["near_equal", "slight", "clear", "decided", "mate_band"]


# ---------------------------------------------------------------------------
# 4. Termination channel
# ---------------------------------------------------------------------------

class TestTerminationChannel:
    def test_time_forfeit(self):
        assert termination_channel("Time forfeit", "WHITE_WIN", True) == "time_forfeit"
        # is_time_forfeit takes precedence
        assert termination_channel("Normal", "DRAW", True) == "time_forfeit"

    def test_normal_decisive(self):
        assert termination_channel("Normal", "WHITE_WIN", False) == "normal_decisive"
        assert termination_channel("Normal", "BLACK_WIN", False) == "normal_decisive"

    def test_normal_draw(self):
        assert termination_channel("Normal", "DRAW", False) == "normal_draw"

    def test_other(self):
        assert termination_channel("Rules infraction", "WHITE_WIN", False) == "other"


# ---------------------------------------------------------------------------
# 5. Cell-count status policy
# ---------------------------------------------------------------------------

class TestCellStatus:
    @pytest.mark.parametrize("n,expected", [
        (0, "hidden_sparse"), (49, "hidden_sparse"),
        (50, "descriptive_only"), (299, "descriptive_only"),
        (300, "ci_ok"), (5000, "ci_ok"),
    ])
    def test_thresholds(self, n, expected):
        assert cell_status(n) == expected


# ---------------------------------------------------------------------------
# 6. Checkpoint / late group
# ---------------------------------------------------------------------------

class TestCheckpoint:
    def test_late(self):
        assert checkpoint_is_late("move_30") is True
        assert checkpoint_is_late("move_40") is True
        assert checkpoint_is_late("move_10") is False
        assert LATE_CHECKPOINTS == ["move_30", "move_40"]


# ---------------------------------------------------------------------------
# 7. Synthetic frame + summary / load / large-loss
# ---------------------------------------------------------------------------

def make_frame(n=400) -> pl.DataFrame:
    rows = []
    for i in range(n):
        cpt = ["move_10", "move_20", "move_30", "move_40"][i % 4]
        es = (i % 10) / 100.0   # 0.00..0.09
        cp = (i % 10) * 30      # 0..270
        rows.append({
            "game_id": f"g{i//2:04d}", "selected_position_type": cpt,
            "status": "ok", "is_mate_band": (i % 50 == 0),
            "expected_score_loss": es, "clipped_cp_loss": cp,
            "mover_pre_cp": (i % 7) * 100 - 300,
            "mover_clock_s": float([5, 45, 120, 300][i % 4]),
            "time_bucket": ["under_60s", "under_60s", "60_180s", "over_180s"][i % 4],
            "mover_rating": 1000 + (i % 8) * 150,
            "termination": "Time forfeit" if i % 6 == 0 else "Normal",
            "is_time_forfeit": (i % 6 == 0),
            "result_class": ["WHITE_WIN", "BLACK_WIN", "DRAW"][i % 3],
        })
    return pl.DataFrame(rows)


class TestLoadAndSummary:
    def test_load_adds_derived(self, tmp_path):
        p = tmp_path / "f.parquet"
        make_frame().write_parquet(p)
        df = load_atlas_frame(p)
        for c in ("clock_coarse", "clock_fine", "rating_bin", "eval_band",
                  "channel", "board_decided", "is_late", "es_loss_gt_005",
                  "es_loss_gt_010", "clipped_cp_loss_gt_100", "clipped_cp_loss_gt_200"):
            assert c in df.columns

    def test_load_missing_col_raises(self, tmp_path):
        p = tmp_path / "f.parquet"
        make_frame().drop("expected_score_loss").write_parquet(p)
        with pytest.raises(ValueError, match="missing required columns"):
            load_atlas_frame(p)

    def test_load_filters_to_ok(self, tmp_path):
        f = make_frame()
        f = pl.concat([f, f.head(5).with_columns(pl.lit("no_next_move").alias("status"))])
        p = tmp_path / "f.parquet"; f.write_parquet(p)
        df = load_atlas_frame(p)
        assert (df["status"] == "ok").all()

    def test_summary_excludes_mate_band(self, tmp_path):
        p = tmp_path / "f.parquet"; make_frame(400).write_parquet(p)
        df = load_atlas_frame(p)
        s = cell_summary(df)
        # 8 mate-band rows (i%50==0 over 400) excluded from n
        assert s["n"] == 392
        assert s["n_mate_band"] == 8
        assert "mean_es_loss" in s and "median_clipped_cp_loss" in s

    def test_summary_empty(self):
        empty = make_frame(0)
        # build an empty derived frame manually
        df = pl.DataFrame({c: [] for c in
                           ["game_id", "expected_score_loss", "clipped_cp_loss",
                            "is_mate_band"]}, schema_overrides={"is_mate_band": pl.Boolean})
        s = cell_summary(df.with_columns(pl.col("is_mate_band").cast(pl.Boolean)))
        assert s["n"] == 0
        assert "mean_es_loss" not in s

    def test_large_loss_indicators(self, tmp_path):
        p = tmp_path / "f.parquet"; make_frame().write_parquet(p)
        df = load_atlas_frame(p)
        # es values are 0..0.09 so none > 0.10
        assert df["es_loss_gt_010"].sum() == 0
        assert df["clipped_cp_loss_gt_100"].sum() > 0


# ---------------------------------------------------------------------------
# 8. grouped_summary + bootstrap
# ---------------------------------------------------------------------------

class TestGroupedAndBootstrap:
    def test_grouped_summary(self, tmp_path):
        p = tmp_path / "f.parquet"; make_frame().write_parquet(p)
        df = load_atlas_frame(p)
        rows = grouped_summary(df, ["selected_position_type"])
        assert len(rows) == 4
        assert all("n" in r and "status" in r for r in rows)

    def test_bootstrap_deterministic(self, tmp_path):
        p = tmp_path / "f.parquet"; make_frame(600).write_parquet(p)
        df = load_atlas_frame(p)
        ci1 = bootstrap_mean_es_ci(df, n_rep=100, seed=42)
        ci2 = bootstrap_mean_es_ci(df, n_rep=100, seed=42)
        assert ci1 == ci2
        assert ci1[0] <= ci1[1]

    def test_bootstrap_empty(self):
        df = pl.DataFrame({"game_id": [], "expected_score_loss": [],
                           "is_mate_band": []},
                          schema_overrides={"is_mate_band": pl.Boolean})
        assert bootstrap_mean_es_ci(df) == (None, None)


# ---------------------------------------------------------------------------
# 9. Report rendering — discipline checks
# ---------------------------------------------------------------------------

class TestReports:
    def _df(self, tmp_path):
        p = tmp_path / "f.parquet"; make_frame(800).write_parquet(p)
        return load_atlas_frame(p)

    def test_month_report_sections(self, tmp_path):
        text = render_month_report("synthetic_v1", self._df(tmp_path))
        for i, t in enumerate([
            "Executive summary", "Input artifact and schema", "Metric definitions",
            "Cell-count policy", "Overall loss summary",
            "Checkpoint-conditioned clock summary", "Late-checkpoint clock summary",
            "Board-decided vs time-forfeit summary", "Rating × clock summary",
            "Eval-band × clock summary", "Phase/checkpoint summary",
            "Clipped-cp robustness summary", "Sparse-cell diagnostics",
            "Limitations and caveats", "Recommendation for combined interpretation",
        ], start=1):
            assert f"## {i}. {t}" in text, t

    def test_month_report_caveats(self, tmp_path):
        text = render_month_report("synthetic_v1", self._df(tmp_path))
        for phrase in ("no causal claims", "not as a degradation curve",
                       "not absolute ground truth", "White-to-move",
                       "survivor population"):
            assert phrase in text, phrase

    def test_month_report_forbidden_absent(self, tmp_path):
        text = render_month_report("synthetic_v1", self._df(tmp_path))
        # the only "causes worse" / "degrades reasoning" appear inside the negated
        # caveat; remove that known clause, then assert no unnegated claim remains
        denegated = text.replace(
            "not evidence that time pressure causes worse moves or degrades reasoning",
            "")
        for phrase in ("causes worse", "degrades reasoning"):
            assert phrase not in denegated, phrase
        for phrase in ("proves", "Stockfish is ground truth",
                       "not merely flagging", "DRAW solved"):
            assert phrase not in text, phrase

    def test_month_report_deterministic(self, tmp_path):
        df = self._df(tmp_path)
        assert render_month_report("v", df) == render_month_report("v", df)

    def test_combined_report_sections(self, tmp_path):
        df = self._df(tmp_path)
        text = render_combined_report({"2024_09_250k_v1": df, "2024_10_250k_v1": df})
        for i, t in enumerate([
            "Executive summary", "Why this Atlas exists after 11.2B/11.2C",
            "Input artifacts", "Month-by-month replication summary",
            "Headline checkpoint-conditioned clock findings",
            "Late-checkpoint findings", "Termination-channel findings",
            "Rating × clock findings", "Eval-band × clock findings",
            "Clipped-cp robustness", "Sparse-cell diagnostics",
            "What this supports", "What this does not support",
            "Readiness for controlled modeling", "Recommended next ticket",
        ], start=1):
            assert f"## {i}. {t}" in text, t

    def test_combined_forbidden_absent(self, tmp_path):
        df = self._df(tmp_path)
        text = render_combined_report({"a": df, "b": df})
        for phrase in ("causes worse", "degrades reasoning",
                       "Stockfish is ground truth", "DRAW is solved"):
            assert phrase not in text, phrase

    def test_combined_recommends_11_3a(self, tmp_path):
        df = self._df(tmp_path)
        text = render_combined_report({"a": df, "b": df})
        assert "11.3A" in text
