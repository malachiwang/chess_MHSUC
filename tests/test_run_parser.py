"""
tests/test_run_parser.py — unit and integration tests for run_parser.py.

All tests use synthetic PGN strings or the project fixture.
No network access is required or used.
"""

import io
import json
from pathlib import Path

import polars as pl
import pytest

from chess_mhsuc.run_parser import (
    GAME_RECORD_SCHEMA,
    POSITION_RECORD_SCHEMA,
    _make_stem,
    _records_to_df,
    stream_and_parse,
    validation_checks,
    write_outputs,
)

# ---------------------------------------------------------------------------
# PGN helpers
# ---------------------------------------------------------------------------

FIXTURE_PGN_PATH = Path(__file__).parent / "fixtures" / "tiny_clock_eval_game.pgn"

# Minimal 600+0 game — accepted_basic=True, 2 plies (too short for checkpoints).
_ACCEPTED_SHORT_A = """\
[Event "Test"]
[Site "https://lichess.org/acc00001"]
[Date "2024.09.01"]
[White "A"]
[Black "B"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1500"]
[TimeControl "600+0"]
[Termination "Normal"]

1. e4 { [%clk 0:09:50] } 1... e5 { [%clk 0:09:50] } 1-0

"""

_ACCEPTED_SHORT_B = """\
[Event "Test"]
[Site "https://lichess.org/acc00002"]
[Date "2024.09.01"]
[White "A"]
[Black "B"]
[Result "0-1"]
[WhiteElo "1600"]
[BlackElo "1400"]
[TimeControl "600+0"]
[Termination "Normal"]

1. d4 { [%clk 0:09:50] } 1... d5 { [%clk 0:09:50] } 0-1

"""

# Non-600+0 game — must be skipped without ply extraction.
_NON_600_PGN = """\
[Event "Test"]
[Site "https://lichess.org/blitz001"]
[Date "2024.09.01"]
[White "A"]
[Black "B"]
[Result "1-0"]
[WhiteElo "1500"]
[BlackElo "1500"]
[TimeControl "300+0"]
[Termination "Normal"]

1. e4 { [%clk 0:04:50] } 1... e5 { [%clk 0:04:50] } 1-0

"""


def _stream(pgn_text: str) -> io.StringIO:
    """Wrap a PGN string in a StringIO for use as a text stream."""
    return io.StringIO(pgn_text)


# ---------------------------------------------------------------------------
# TestMakeStem
# ---------------------------------------------------------------------------

class TestMakeStem:
    def test_standard_filename(self):
        assert (
            _make_stem("lichess_db_standard_rated_2024-09.pgn.zst", 25_000, "v1")
            == "2024_09_25k_v1"
        )

    def test_none_source_file(self):
        assert _make_stem(None, 1_000, "test") == "unknown_1k_test"

    def test_non_round_thousand_cap(self):
        assert (
            _make_stem("lichess_db_standard_rated_2024-01.pgn.zst", 500, "v2")
            == "2024_01_500_v2"
        )

    def test_ten_thousand(self):
        assert (
            _make_stem("lichess_db_standard_rated_2024-11.pgn.zst", 10_000, "v1")
            == "2024_11_10k_v1"
        )


# ---------------------------------------------------------------------------
# TestRecordsToDf
# ---------------------------------------------------------------------------

class TestRecordsToDf:
    def test_empty_game_records_returns_correct_schema(self):
        df = _records_to_df([], GAME_RECORD_SCHEMA)
        assert df.height == 0
        assert set(df.columns) == set(GAME_RECORD_SCHEMA.keys())

    def test_empty_position_records_returns_correct_schema(self):
        df = _records_to_df([], POSITION_RECORD_SCHEMA)
        assert df.height == 0
        assert set(df.columns) == set(POSITION_RECORD_SCHEMA.keys())

    def test_fixture_produces_nonempty_game_df(self):
        text = FIXTURE_PGN_PATH.read_text(encoding="utf-8")
        result = stream_and_parse(_stream(text), source_file=None, max_games=5)
        df = _records_to_df(result["game_records"], GAME_RECORD_SCHEMA)
        assert df.height == 1


# ---------------------------------------------------------------------------
# TestStreamAndParseFixture
# ---------------------------------------------------------------------------

class TestStreamAndParseFixture:
    """Integration tests against the 82-ply synthetic fixture."""

    @pytest.fixture(autouse=True)
    def _parse(self):
        text = FIXTURE_PGN_PATH.read_text(encoding="utf-8")
        self.result = stream_and_parse(
            _stream(text),
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
            max_games=10,
        )

    def test_one_game_record_produced(self):
        assert len(self.result["game_records"]) == 1

    def test_game_record_accepted_basic(self):
        assert self.result["game_records"][0].accepted_basic is True

    def test_five_checkpoints(self):
        # move_10, move_20, move_30, move_40, last
        assert len(self.result["position_records"]) == 5

    def test_no_parse_errors(self):
        assert self.result["n_parse_errors"] == 0

    def test_raw_and_600_counters(self):
        assert self.result["n_raw_scanned"] == 1
        assert self.result["n_600_0_total"] == 1

    def test_url_field_preserved(self):
        text = FIXTURE_PGN_PATH.read_text(encoding="utf-8")
        r = stream_and_parse(
            _stream(text), source_file=None, max_games=5,
            url="http://example.test/file.pgn.zst",
        )
        assert r["url"] == "http://example.test/file.pgn.zst"

    def test_no_username_fields_on_game_record(self):
        gr = self.result["game_records"][0]
        forbidden = {"white", "black", "White", "Black"}
        assert not (forbidden & set(vars(gr).keys()))


# ---------------------------------------------------------------------------
# TestStreamAndParseFilter
# ---------------------------------------------------------------------------

class TestStreamAndParseFilter:
    """TC pre-filter, max_games cap, max_accepted cap."""

    def test_non_600_game_not_in_game_records(self):
        r = stream_and_parse(_stream(_NON_600_PGN), source_file=None, max_games=5)
        assert len(r["game_records"]) == 0
        assert r["n_600_0_total"] == 0

    def test_non_600_mixed_with_600_only_600_parsed(self):
        pgn = _NON_600_PGN + _ACCEPTED_SHORT_A
        r = stream_and_parse(_stream(pgn), source_file=None, max_games=10)
        assert r["n_600_0_total"] == 1
        assert len(r["game_records"]) == 1

    def test_max_games_limits_raw_scanned(self):
        pgn = _NON_600_PGN + _NON_600_PGN  # two games; cap at 1
        r = stream_and_parse(_stream(pgn), source_file=None, max_games=1)
        assert r["n_raw_scanned"] == 1

    def test_max_accepted_stops_after_first_accepted(self):
        pgn = _ACCEPTED_SHORT_A + _ACCEPTED_SHORT_B
        r = stream_and_parse(
            _stream(pgn), source_file=None, max_games=100, max_accepted=1
        )
        assert len(r["game_records"]) == 1

    def test_max_accepted_none_processes_all(self):
        pgn = _ACCEPTED_SHORT_A + _ACCEPTED_SHORT_B
        r = stream_and_parse(
            _stream(pgn), source_file=None, max_games=100, max_accepted=None
        )
        assert len(r["game_records"]) == 2


# ---------------------------------------------------------------------------
# TestStreamAndParseExceptionHandling
# ---------------------------------------------------------------------------

class TestStreamAndParseExceptionHandling:

    def test_exception_in_one_game_does_not_crash_run(self, monkeypatch):
        import chess_mhsuc.run_parser as rp

        call_n = {"n": 0}
        orig = rp.extract_game_record

        def _fail_first(game, source_file):
            call_n["n"] += 1
            if call_n["n"] == 1:
                raise ValueError("synthetic parse error")
            return orig(game, source_file=source_file)

        monkeypatch.setattr(rp, "extract_game_record", _fail_first)

        pgn = _ACCEPTED_SHORT_A + _ACCEPTED_SHORT_B
        r = stream_and_parse(_stream(pgn), source_file=None, max_games=10)
        # First game errored; second should still be processed.
        assert r["n_parse_errors"] == 1
        assert len(r["game_records"]) == 1

    def test_error_log_entry_has_required_keys(self, monkeypatch):
        import chess_mhsuc.run_parser as rp

        def _always_raise(game, source_file):
            raise RuntimeError("boom")

        monkeypatch.setattr(rp, "extract_game_record", _always_raise)

        r = stream_and_parse(_stream(_ACCEPTED_SHORT_A), source_file=None, max_games=10)
        assert len(r["error_log"]) == 1
        entry = r["error_log"][0]
        assert "game_site" in entry
        assert "error" in entry


# ---------------------------------------------------------------------------
# TestValidationChecks
# ---------------------------------------------------------------------------

class TestValidationChecks:

    @pytest.fixture
    def fixture_dfs(self):
        text = FIXTURE_PGN_PATH.read_text(encoding="utf-8")
        result = stream_and_parse(_stream(text), source_file=None, max_games=10)
        df_g = _records_to_df(result["game_records"], GAME_RECORD_SCHEMA)
        df_p = _records_to_df(result["position_records"], POSITION_RECORD_SCHEMA)
        return df_g, df_p

    def test_all_checks_pass_for_fixture(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        checks = validation_checks(df_g, df_p)
        failures = [k for k, v in checks.items() if not v]
        assert not failures, f"Failed checks: {failures}"

    def test_all_checks_pass_for_empty_dfs(self):
        df_g = _records_to_df([], GAME_RECORD_SCHEMA)
        df_p = _records_to_df([], POSITION_RECORD_SCHEMA)
        checks = validation_checks(df_g, df_p)
        assert all(checks.values())

    def test_username_col_in_games_fails(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        df_bad = df_g.with_columns(pl.lit("leaked").alias("White"))
        checks = validation_checks(df_bad, df_p)
        assert checks["no_username_cols_games"] is False

    def test_username_col_in_positions_fails(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        df_bad = df_p.with_columns(pl.lit("leaked").alias("black"))
        checks = validation_checks(df_g, df_bad)
        assert checks["no_username_cols_positions"] is False

    def test_duplicate_game_ids_fail(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        df_dup = pl.concat([df_g, df_g])
        checks = validation_checks(df_dup, df_p)
        assert checks["game_id_unique"] is False

    def test_unknown_result_class_fails(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        df_bad = df_g.with_columns(pl.lit("UNKNOWN").alias("result_class"))
        checks = validation_checks(df_bad, df_p)
        assert checks["result_class_values_valid"] is False

    def test_eval_sentinel_without_mate_fails(self, fixture_dfs):
        df_g, df_p = fixture_dfs
        # Sentinel eval_cp with no eval_mate is inconsistent.
        df_bad = df_p.with_columns([
            pl.lit(10_000, dtype=pl.Int64).alias("eval_cp"),
            pl.lit(None, dtype=pl.Int64).alias("eval_mate"),
        ])
        checks = validation_checks(df_g, df_bad)
        assert checks["eval_sentinel_consistent"] is False


# ---------------------------------------------------------------------------
# TestWriteOutputs
# ---------------------------------------------------------------------------

class TestWriteOutputs:

    @pytest.fixture
    def fixture_result(self):
        text = FIXTURE_PGN_PATH.read_text(encoding="utf-8")
        return stream_and_parse(
            _stream(text),
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
            max_games=10,
        )

    def _write(self, fixture_result, tmp_path, **overrides):
        kwargs = dict(
            source_url="http://test.url/file.pgn.zst",
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
            raw_games_cap=10,
            max_accepted_basic=None,
            version_tag="test",
        )
        kwargs.update(overrides)
        g = tmp_path / "gr.parquet"
        p = tmp_path / "pr.parquet"
        m = tmp_path / "meta.json"
        meta = write_outputs(fixture_result, g, p, m, **kwargs)
        return g, p, m, meta

    def test_output_files_created(self, fixture_result, tmp_path):
        g, p, m, _ = self._write(fixture_result, tmp_path)
        assert g.exists() and p.exists() and m.exists()

    def test_game_records_parquet_columns(self, fixture_result, tmp_path):
        g, _, _, _ = self._write(fixture_result, tmp_path)
        assert set(pl.read_parquet(str(g)).columns) == set(GAME_RECORD_SCHEMA.keys())

    def test_position_records_parquet_columns(self, fixture_result, tmp_path):
        _, p, _, _ = self._write(fixture_result, tmp_path)
        assert set(pl.read_parquet(str(p)).columns) == set(POSITION_RECORD_SCHEMA.keys())

    def test_no_username_cols_in_parquet(self, fixture_result, tmp_path):
        g, p, _, _ = self._write(fixture_result, tmp_path)
        forbidden = {"white", "black", "White", "Black"}
        assert not (forbidden & set(pl.read_parquet(str(g)).columns))
        assert not (forbidden & set(pl.read_parquet(str(p)).columns))

    def test_metadata_required_keys(self, fixture_result, tmp_path):
        _, _, m, _ = self._write(fixture_result, tmp_path)
        meta = json.loads(m.read_text())
        required = {
            "source_url", "source_file", "source_month", "raw_games_cap",
            "raw_games_scanned", "n_600_0_total", "n_game_records",
            "n_accepted_basic", "n_accepted_eval", "n_position_records",
            "n_parse_errors", "rejection_reason_counts", "result_distribution",
            "termination_distribution", "checkpoint_type_distribution",
            "phase_distribution", "elapsed_s", "timestamp_utc", "version_tag",
            "output_paths",
        }
        assert required <= set(meta.keys())

    def test_metadata_counts_match_parquet(self, fixture_result, tmp_path):
        g, p, m, _ = self._write(fixture_result, tmp_path)
        meta = json.loads(m.read_text())
        assert meta["n_game_records"] == pl.read_parquet(str(g)).height
        assert meta["n_position_records"] == pl.read_parquet(str(p)).height

# ---------------------------------------------------------------------------
# TestTeeTextStream (9.1B raw cache)
# ---------------------------------------------------------------------------

from chess_mhsuc.run_parser import TeeTextStream  # noqa: E402


class TestTeeTextStream:
    def test_tee_copies_consumed_lines(self, tmp_path):
        src = _stream(_ACCEPTED_SHORT_A + _ACCEPTED_SHORT_B)
        sink_path = tmp_path / "cache.pgn"
        with open(sink_path, "w", encoding="utf-8") as sink:
            teed = TeeTextStream(src, sink)
            result = stream_and_parse(
                teed, source_file=None, max_games=2, url=""
            )
        assert result["n_raw_scanned"] == 2
        cached = sink_path.read_text()
        assert "acc00001" in cached
        assert "acc00002" in cached

    def test_tee_cache_is_reparseable(self, tmp_path):
        src = _stream(_ACCEPTED_SHORT_A + _NON_600_PGN + _ACCEPTED_SHORT_B)
        sink_path = tmp_path / "cache.pgn"
        with open(sink_path, "w", encoding="utf-8") as sink:
            teed = TeeTextStream(src, sink)
            first = stream_and_parse(
                teed, source_file=None, max_games=3, url=""
            )
        # re-parse from the cached file: identical raw counts
        with open(sink_path, encoding="utf-8") as f:
            second = stream_and_parse(
                f, source_file=None, max_games=3, url=""
            )
        assert second["n_raw_scanned"] == first["n_raw_scanned"] == 3
        assert second["n_600_0_total"] == first["n_600_0_total"] == 2

    def test_tee_respects_max_games_cap(self, tmp_path):
        src = _stream(_ACCEPTED_SHORT_A + _ACCEPTED_SHORT_B)
        sink_path = tmp_path / "cache.pgn"
        with open(sink_path, "w", encoding="utf-8") as sink:
            teed = TeeTextStream(src, sink)
            result = stream_and_parse(
                teed, source_file=None, max_games=1, url=""
            )
        assert result["n_raw_scanned"] == 1
        cached = sink_path.read_text()
        assert "acc00001" in cached
        # second game never consumed -> not in cache (read_game may consume
        # the next game's first header line; the body must be absent)
        assert "1. d4" not in cached

    def test_empty_stream_creates_empty_cache(self, tmp_path):
        src = _stream("")
        sink_path = tmp_path / "cache.pgn"
        with open(sink_path, "w", encoding="utf-8") as sink:
            teed = TeeTextStream(src, sink)
            result = stream_and_parse(
                teed, source_file=None, max_games=5, url=""
            )
        assert result["n_raw_scanned"] == 0
        assert sink_path.read_text() == ""
