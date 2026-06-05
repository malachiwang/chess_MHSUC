"""
Tests for parse_pgn.py and schemas.py.

No real game data. All PGN strings are hand-crafted minimal examples,
or the approved synthetic fixture at tests/fixtures/tiny_clock_eval_game.pgn.

Clock carry-forward note (not a bug):
  At odd plies (White's move N), black_clock_s carries forward from Black's
  move N-1, so it is higher than white_clock_s until Black plays move N.
  This asymmetry is expected and tested explicitly.
"""

import io
from pathlib import Path

import chess.pgn
import pytest

from chess_mhsuc.parse_pgn import (
    extract_game_record,
    extract_ply_records,
    parse_clock_seconds,
    parse_eval_comment,
    parse_game,
    parse_game_id,
    parse_result,
    parse_source_month,
    phase_for_move,
    select_checkpoints,
)
from chess_mhsuc.schemas import (
    MATE_CP_SENTINEL,
    PHASE_ENDGAME,
    PHASE_MIDDLEGAME,
    PHASE_OPENING,
    RESULT_BLACK_WIN,
    RESULT_DRAW,
    RESULT_WHITE_WIN,
    GameRecord,
    PlyRecord,
)

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TINY_FIXTURE = FIXTURE_DIR / "tiny_clock_eval_game.pgn"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(pgn_str: str) -> chess.pgn.Game:
    """Parse a PGN string into a chess.pgn.Game object."""
    return chess.pgn.read_game(io.StringIO(pgn_str))


def _pgn(
    game_id: str = "g001",
    result: str = "1-0",
    welo: str = "1500",
    belo: str = "1480",
    tc: str = "600+0",
    variant: str | None = None,
    has_clock: bool = True,
) -> str:
    """
    Build a minimal 2-ply PGN string for rejection/acceptance tests.

    has_clock=True  → both plies have [%clk] annotations
    has_clock=False → no clock annotations anywhere
    """
    if has_clock:
        moves = (
            f"1. e4 {{ [%clk 0:10:00] }} e5 {{ [%clk 0:09:58] }} {result}"
        )
    else:
        moves = f"1. e4 e5 {result}"

    variant_line = f'[Variant "{variant}"]\n' if variant else ""

    return (
        f'[Event "Test"]\n'
        f'[Site "https://lichess.org/{game_id}"]\n'
        f'[Date "2024.09.01"]\n'
        f'[White "PlayerA"]\n'
        f'[Black "PlayerB"]\n'
        f'[Result "{result}"]\n'
        f'[WhiteElo "{welo}"]\n'
        f'[BlackElo "{belo}"]\n'
        f'[TimeControl "{tc}"]\n'
        f'[UTCDate "2024.09.01"]\n'
        f'[UTCTime "10:00:00"]\n'
        f'[Termination "Normal"]\n'
        + variant_line
        + f"\n{moves}\n\n"
    )


def _make_plies(
    n: int,
    game_id: str = "test",
    w_clk: int = 600,
    b_clk: int = 600,
) -> list[PlyRecord]:
    """
    Build n synthetic PlyRecords with correct move_number and side_to_move_next.

    Odd ply  = White's move → side_to_move_next = "black", move_number = (ply+1)//2
    Even ply = Black's move → side_to_move_next = "white", move_number = ply//2
    """
    recs = []
    for p in range(1, n + 1):
        if p % 2 == 1:  # White's move
            side = "black"
            mv = (p + 1) // 2
        else:           # Black's move
            side = "white"
            mv = p // 2
        recs.append(PlyRecord(
            game_id=game_id,
            ply=p,
            move_number=mv,
            side_to_move_next=side,
            san=None,
            white_clock_s=w_clk,
            black_clock_s=b_clk,
            clock_diff_s=0,
            eval_cp=None,
            eval_mate=None,
            raw_eval=None,
            has_eval=False,
        ))
    return recs


def _make_game_record(**kwargs) -> GameRecord:
    """Build a minimal accepted GameRecord for checkpoint-selection tests."""
    defaults: dict = dict(
        game_id="test",
        source_file=None,
        source_month=None,
        utc_date=None,
        utc_time=None,
        time_control="600+0",
        result_raw="1-0",
        result_class=RESULT_WHITE_WIN,
        white_result_numeric=1.0,
        termination="Normal",
        white_elo=1500,
        black_elo=1480,
        elo_diff=20,
        white_rating_diff=None,
        black_rating_diff=None,
        event=None,
        n_plies=82,
        has_clock=True,
        has_eval=False,
        accepted_basic=True,
        accepted_eval=False,
        rejection_reason=None,
    )
    defaults.update(kwargs)
    return GameRecord(**defaults)


# ---------------------------------------------------------------------------
# parse_clock_seconds
# ---------------------------------------------------------------------------

class TestParseClockSeconds:
    def test_ten_minutes(self):
        assert parse_clock_seconds("0:10:00") == 600

    def test_one_second(self):
        assert parse_clock_seconds("0:00:01") == 1

    def test_zero(self):
        assert parse_clock_seconds("0:00:00") == 0

    def test_none_returns_none(self):
        assert parse_clock_seconds(None) is None

    def test_empty_string_returns_none(self):
        assert parse_clock_seconds("") is None

    def test_nine_minutes_fifty_seconds(self):
        # fixture ply 1: "0:09:50" = 9*60 + 50 = 590
        assert parse_clock_seconds("0:09:50") == 590

    def test_one_hour(self):
        assert parse_clock_seconds("1:00:00") == 3600


# ---------------------------------------------------------------------------
# phase_for_move
# ---------------------------------------------------------------------------

class TestPhaseForMove:
    @pytest.mark.parametrize("move_number", [1, 5, 10])
    def test_opening(self, move_number):
        assert phase_for_move(move_number) == PHASE_OPENING

    @pytest.mark.parametrize("move_number", [11, 20, 35])
    def test_middlegame(self, move_number):
        assert phase_for_move(move_number) == PHASE_MIDDLEGAME

    @pytest.mark.parametrize("move_number", [36, 40, 100])
    def test_endgame(self, move_number):
        assert phase_for_move(move_number) == PHASE_ENDGAME


# ---------------------------------------------------------------------------
# parse_result
# ---------------------------------------------------------------------------

class TestParseResult:
    def test_white_win(self):
        raw, cls, num = parse_result(_parse(_pgn(result="1-0")).headers)
        assert raw == "1-0"
        assert cls == RESULT_WHITE_WIN
        assert num == 1.0

    def test_black_win(self):
        raw, cls, num = parse_result(_parse(_pgn(result="0-1")).headers)
        assert raw == "0-1"
        assert cls == RESULT_BLACK_WIN
        assert num == 0.0

    def test_draw(self):
        raw, cls, num = parse_result(_parse(_pgn(result="1/2-1/2")).headers)
        assert raw == "1/2-1/2"
        assert cls == RESULT_DRAW
        assert num == 0.5

    def test_invalid_asterisk_returns_nones(self):
        raw, cls, num = parse_result(_parse(_pgn(result="*")).headers)
        assert raw is None
        assert cls is None
        assert num is None


# ---------------------------------------------------------------------------
# parse_game_id
# ---------------------------------------------------------------------------

class TestParseGameId:
    def test_lichess_url(self):
        assert parse_game_id("https://lichess.org/abcd1234") == "abcd1234"

    def test_fixture_site_url(self):
        assert parse_game_id("https://lichess.org/synth0001") == "synth0001"

    def test_none_returns_none(self):
        assert parse_game_id(None) is None

    def test_empty_string_returns_none(self):
        assert parse_game_id("") is None

    def test_url_with_subpath(self):
        # last segment used regardless of depth
        assert parse_game_id("https://lichess.org/game/xyz9999") == "xyz9999"


# ---------------------------------------------------------------------------
# parse_source_month
# ---------------------------------------------------------------------------

class TestParseSourceMonth:
    def test_standard_lichess_filename(self):
        assert (
            parse_source_month("lichess_db_standard_rated_2024-09.pgn.zst")
            == "2024-09"
        )

    def test_no_date_in_filename(self):
        assert parse_source_month("nodate.pgn.zst") is None

    def test_none_returns_none(self):
        assert parse_source_month(None) is None

    def test_other_month(self):
        assert (
            parse_source_month("lichess_db_standard_rated_2023-01.pgn.zst")
            == "2023-01"
        )


# ---------------------------------------------------------------------------
# parse_eval_comment
# ---------------------------------------------------------------------------

class TestParseEvalComment:
    def test_decimal_positive_white_pov(self):
        cp, mate, raw = parse_eval_comment("{ [%eval 0.47] }", "white")
        assert cp == 47
        assert mate is None
        assert raw == "0.47"

    def test_decimal_negative_white_pov(self):
        cp, mate, raw = parse_eval_comment("{ [%eval -0.35] }", "white")
        assert cp == -35
        assert mate is None
        assert raw == "-0.35"

    def test_decimal_zero(self):
        cp, mate, raw = parse_eval_comment("{ [%eval 0.00] }", "white")
        assert cp == 0
        assert mate is None

    def test_no_eval_returns_nones(self):
        cp, mate, raw = parse_eval_comment("{ [%clk 0:09:50] }", "white")
        assert cp is None
        assert mate is None
        assert raw is None

    # --- Mate with White to move ---

    def test_positive_mate_white_to_move(self):
        # #3: White (side to move) has forced mate in 3 → White advantage
        cp, mate, raw = parse_eval_comment("{ [%eval #3] }", "white")
        assert cp == MATE_CP_SENTINEL    # +10000
        assert mate == 3
        assert raw == "#3"

    def test_negative_mate_white_to_move(self):
        # #-2: Black (opponent) has forced mate in 2 → Black advantage
        cp, mate, raw = parse_eval_comment("{ [%eval #-2] }", "white")
        assert cp == -MATE_CP_SENTINEL   # -10000
        assert mate == -2
        assert raw == "#-2"

    # --- Mate with Black to move ---

    def test_positive_mate_black_to_move(self):
        # #3: Black (side to move) has forced mate in 3 → Black advantage
        cp, mate, raw = parse_eval_comment("{ [%eval #3] }", "black")
        assert cp == -MATE_CP_SENTINEL   # -10000
        assert mate == -3
        assert raw == "#3"

    def test_negative_mate_black_to_move(self):
        # #-2: White (opponent) has forced mate in 2 → White advantage
        cp, mate, raw = parse_eval_comment("{ [%eval #-2] }", "black")
        assert cp == MATE_CP_SENTINEL    # +10000
        assert mate == 2
        assert raw == "#-2"

    def test_mate_sentinel_value(self):
        # Confirm the sentinel is 10000 as defined in schemas.py
        assert MATE_CP_SENTINEL == 10_000

    def test_comment_with_both_clk_and_eval(self):
        # Both annotations in one comment — eval should be extracted
        cp, mate, raw = parse_eval_comment(
            "{ [%clk 0:09:50] [%eval 0.20] }", "white"
        )
        assert cp == 20
        assert mate is None
        assert raw == "0.20"


# ---------------------------------------------------------------------------
# GameRecord extraction — fixture acceptance
# ---------------------------------------------------------------------------

class TestExtractGameRecordFixture:
    def setup_method(self):
        with open(TINY_FIXTURE) as f:
            self._game = chess.pgn.read_game(f)

    def test_accepted_basic(self):
        gr = extract_game_record(self._game)
        assert gr.accepted_basic is True

    def test_accepted_eval(self):
        gr = extract_game_record(self._game)
        assert gr.accepted_eval is True

    def test_rejection_reason_none(self):
        gr = extract_game_record(self._game)
        assert gr.rejection_reason is None

    def test_game_id(self):
        gr = extract_game_record(self._game)
        assert gr.game_id == "synth0001"

    def test_source_month_from_source_file(self):
        gr = extract_game_record(
            self._game,
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
        )
        assert gr.source_month == "2024-09"

    def test_source_month_none_without_source_file(self):
        gr = extract_game_record(self._game)
        assert gr.source_month is None

    def test_elo_fields(self):
        gr = extract_game_record(self._game)
        assert gr.white_elo == 1600
        assert gr.black_elo == 1580
        assert gr.elo_diff == 20

    def test_rating_diffs(self):
        gr = extract_game_record(self._game)
        assert gr.white_rating_diff == 8
        assert gr.black_rating_diff == -8

    def test_result_fields(self):
        gr = extract_game_record(self._game)
        assert gr.result_raw == "1-0"
        assert gr.result_class == RESULT_WHITE_WIN
        assert gr.white_result_numeric == 1.0

    def test_n_plies(self):
        gr = extract_game_record(self._game)
        assert gr.n_plies == 82

    def test_no_username_fields(self):
        gr = extract_game_record(self._game)
        # Usernames must not be retained per DATA_POLICY.md
        for attr in ("white", "black", "White", "Black", "white_name", "black_name"):
            assert not hasattr(gr, attr), f"unexpected field: {attr!r}"


# ---------------------------------------------------------------------------
# GameRecord extraction — rejection cases
# ---------------------------------------------------------------------------

class TestExtractGameRecordRejection:
    def test_wrong_tc_rejected(self):
        gr = extract_game_record(_parse(_pgn(tc="300+0")))
        assert gr.accepted_basic is False
        assert gr.rejection_reason == "wrong_time_control"

    def test_variant_absent_accepted(self):
        # No Variant header → treated as Standard
        gr = extract_game_record(_parse(_pgn()))
        assert gr.accepted_basic is True

    def test_variant_standard_accepted(self):
        gr = extract_game_record(_parse(_pgn(variant="Standard")))
        assert gr.accepted_basic is True

    def test_variant_chess960_rejected(self):
        gr = extract_game_record(_parse(_pgn(variant="Chess960")))
        assert gr.accepted_basic is False
        assert gr.rejection_reason == "variant_or_nonstandard"

    def test_invalid_elo_question_mark_rejected(self):
        gr = extract_game_record(_parse(_pgn(welo="?")))
        assert gr.accepted_basic is False
        assert gr.rejection_reason == "missing_or_invalid_elo"

    def test_invalid_result_asterisk_rejected(self):
        gr = extract_game_record(_parse(_pgn(result="*")))
        assert gr.accepted_basic is False
        assert gr.rejection_reason == "missing_or_invalid_result"

    def test_missing_clock_rejected(self):
        gr = extract_game_record(_parse(_pgn(has_clock=False)))
        assert gr.accepted_basic is False
        assert gr.rejection_reason == "missing_clock"

    def test_rejection_priority_tc_before_variant(self):
        # Both wrong TC and nonstandard variant → TC takes priority
        gr = extract_game_record(_parse(_pgn(tc="300+0", variant="Chess960")))
        assert gr.rejection_reason == "wrong_time_control"

    def test_rejection_priority_variant_before_elo(self):
        # Both nonstandard variant and bad Elo → variant takes priority
        gr = extract_game_record(_parse(_pgn(variant="Chess960", welo="?")))
        assert gr.rejection_reason == "variant_or_nonstandard"


# ---------------------------------------------------------------------------
# PlyRecord extraction — fixture
# ---------------------------------------------------------------------------

class TestExtractPlyRecords:
    def setup_method(self):
        with open(TINY_FIXTURE) as f:
            self._game = chess.pgn.read_game(f)
        self._recs = extract_ply_records(self._game, game_id="synth0001")

    def test_ply_count(self):
        assert len(self._recs) == 82

    def test_ply_numbering_starts_at_one(self):
        assert self._recs[0].ply == 1
        assert self._recs[-1].ply == 82

    def test_ply_1_white_clock_set_black_clock_none(self):
        r = self._recs[0]
        assert r.white_clock_s == 590
        assert r.black_clock_s is None

    def test_ply_2_both_clocks_set(self):
        # After Black's first move, both sides have a clock
        r = self._recs[1]
        assert r.white_clock_s == 590   # carried from ply 1
        assert r.black_clock_s == 590   # updated at ply 2

    # Clock carry-forward at White's moves (odd plies):
    # Black's clock reflects the previous Black ply, not the current one.

    def test_ply_19_white_clock_updated_black_carried(self):
        # ply 19 = White move 10; Black has not yet played move 10
        r = self._recs[18]
        assert r.ply == 19
        assert r.white_clock_s == 500   # updated: [%clk 0:08:20] = 500s
        assert r.black_clock_s == 510   # carried from ply 18 (9...Be6 = 510s)

    def test_ply_39_clock_carry_forward(self):
        r = self._recs[38]
        assert r.ply == 39
        assert r.white_clock_s == 470
        assert r.black_clock_s == 473

    def test_ply_59_clock_carry_forward(self):
        r = self._recs[58]
        assert r.ply == 59
        assert r.white_clock_s == 440
        assert r.black_clock_s == 443

    def test_ply_79_clock_carry_forward(self):
        r = self._recs[78]
        assert r.ply == 79
        assert r.white_clock_s == 410
        assert r.black_clock_s == 413

    # After Black's moves (even plies), both clocks are up to date.

    def test_ply_20_both_clocks_equal(self):
        r = self._recs[19]
        assert r.ply == 20
        assert r.white_clock_s == 500
        assert r.black_clock_s == 500
        assert r.clock_diff_s == 0

    def test_ply_20_eval_mate_white_pov(self):
        # 10...Qd7 { [%eval #3] }, side_to_move_next="white" → +10000, mate=+3
        r = self._recs[19]
        assert r.eval_cp == MATE_CP_SENTINEL
        assert r.eval_mate == 3
        assert r.has_eval is True

    def test_ply_40_eval_negative_mate(self):
        # 20...Nf6 { [%eval #-2] }, side_to_move_next="white" → -10000, mate=-2
        r = self._recs[39]
        assert r.eval_cp == -MATE_CP_SENTINEL
        assert r.eval_mate == -2
        assert r.has_eval is True

    def test_ply_60_decimal_eval(self):
        # 30...Nf6 { [%eval 0.25] } → eval_cp=25, no mate
        r = self._recs[59]
        assert r.eval_cp == 25
        assert r.eval_mate is None
        assert r.has_eval is True

    def test_ply_80_no_eval(self):
        # 40...Nf6 has no [%eval] annotation
        r = self._recs[79]
        assert r.has_eval is False
        assert r.eval_cp is None
        assert r.eval_mate is None

    def test_game_id_propagated(self):
        assert all(r.game_id == "synth0001" for r in self._recs)


# ---------------------------------------------------------------------------
# Checkpoint selection — full fixture (5 checkpoints)
# ---------------------------------------------------------------------------

class TestSelectCheckpointsFixture:
    def setup_method(self):
        with open(TINY_FIXTURE) as f:
            game = chess.pgn.read_game(f)
        self._gr = extract_game_record(
            game,
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
        )
        recs = extract_ply_records(game, game_id=self._gr.game_id)
        self._cps = select_checkpoints(recs, self._gr)
        self._cp = {cp.selected_position_type: cp for cp in self._cps}

    def test_five_checkpoints_total(self):
        assert len(self._cps) == 5

    def test_checkpoint_types_present(self):
        assert set(self._cp.keys()) == {"move_10", "move_20", "move_30", "move_40", "last"}

    # move_10

    def test_move_10_ply(self):
        assert self._cp["move_10"].ply == 20

    def test_move_10_move_number(self):
        assert self._cp["move_10"].move_number == 10

    def test_move_10_phase(self):
        assert self._cp["move_10"].phase == PHASE_OPENING

    def test_move_10_clocks(self):
        cp = self._cp["move_10"]
        assert cp.white_clock_s == 500
        assert cp.black_clock_s == 500
        assert cp.clock_diff_s == 0

    def test_move_10_eval(self):
        cp = self._cp["move_10"]
        assert cp.eval_cp == MATE_CP_SENTINEL
        assert cp.eval_mate == 3
        assert cp.has_eval is True

    # move_20

    def test_move_20_ply(self):
        assert self._cp["move_20"].ply == 40

    def test_move_20_phase(self):
        assert self._cp["move_20"].phase == PHASE_MIDDLEGAME

    def test_move_20_clocks(self):
        cp = self._cp["move_20"]
        assert cp.white_clock_s == 470
        assert cp.black_clock_s == 470

    def test_move_20_eval(self):
        cp = self._cp["move_20"]
        assert cp.eval_cp == -MATE_CP_SENTINEL
        assert cp.eval_mate == -2
        assert cp.has_eval is True

    # move_30

    def test_move_30_ply(self):
        assert self._cp["move_30"].ply == 60

    def test_move_30_phase(self):
        assert self._cp["move_30"].phase == PHASE_MIDDLEGAME

    def test_move_30_clocks(self):
        cp = self._cp["move_30"]
        assert cp.white_clock_s == 440
        assert cp.black_clock_s == 440

    def test_move_30_eval(self):
        cp = self._cp["move_30"]
        assert cp.eval_cp == 25
        assert cp.eval_mate is None
        assert cp.has_eval is True

    # move_40

    def test_move_40_ply(self):
        assert self._cp["move_40"].ply == 80

    def test_move_40_phase(self):
        assert self._cp["move_40"].phase == PHASE_ENDGAME

    def test_move_40_clocks(self):
        cp = self._cp["move_40"]
        assert cp.white_clock_s == 410
        assert cp.black_clock_s == 410

    def test_move_40_no_eval(self):
        cp = self._cp["move_40"]
        assert cp.has_eval is False
        assert cp.eval_cp is None
        assert cp.eval_mate is None

    # last

    def test_last_ply(self):
        assert self._cp["last"].ply == 82

    def test_last_move_number(self):
        assert self._cp["last"].move_number == 41

    def test_last_phase(self):
        assert self._cp["last"].phase == PHASE_ENDGAME

    def test_last_clocks(self):
        cp = self._cp["last"]
        assert cp.white_clock_s == 407
        assert cp.black_clock_s == 407

    def test_last_no_eval(self):
        cp = self._cp["last"]
        assert cp.has_eval is False

    # Game-level fields copied into each PositionRecord

    def test_game_fields_copied_to_checkpoints(self):
        cp = self._cp["move_10"]
        assert cp.game_id == "synth0001"
        assert cp.result_class == RESULT_WHITE_WIN
        assert cp.white_result_numeric == 1.0
        assert cp.white_elo == 1600
        assert cp.black_elo == 1580
        assert cp.elo_diff == 20
        assert cp.n_plies_total == 82


# ---------------------------------------------------------------------------
# Checkpoint selection — edge cases (constructed records, no PGN parsing)
# ---------------------------------------------------------------------------

class TestSelectCheckpointsEdgeCases:
    def test_empty_ply_list_returns_empty(self):
        gr = _make_game_record(n_plies=0)
        cps = select_checkpoints([], gr)
        assert cps == []

    def test_15_plies_returns_empty(self):
        gr = _make_game_record(n_plies=15)
        cps = select_checkpoints(_make_plies(15), gr)
        assert cps == []

    def test_19_plies_returns_empty(self):
        # One ply short of the first checkpoint (ply 20)
        gr = _make_game_record(n_plies=19)
        cps = select_checkpoints(_make_plies(19), gr)
        assert cps == []

    def test_20_ply_game_returns_move_10_and_last(self):
        # Game ends exactly at ply 20: move_10 and last both point to ply 20
        gr = _make_game_record(n_plies=20)
        cps = select_checkpoints(_make_plies(20), gr)
        types = {cp.selected_position_type for cp in cps}
        assert "move_10" in types
        assert "last" in types
        assert all(cp.ply == 20 for cp in cps)

    def test_20_ply_game_count(self):
        gr = _make_game_record(n_plies=20)
        cps = select_checkpoints(_make_plies(20), gr)
        assert len(cps) == 2

    def test_21_ply_game_move_10_and_last_different_plies(self):
        # Game ends at ply 21: move_10 = ply 20, last = ply 21
        gr = _make_game_record(n_plies=21)
        cps = select_checkpoints(_make_plies(21), gr)
        cp_map = {cp.selected_position_type: cp for cp in cps}
        assert "move_10" in cp_map
        assert "last" in cp_map
        assert cp_map["move_10"].ply == 20
        assert cp_map["last"].ply == 21

    def test_21_ply_game_count(self):
        gr = _make_game_record(n_plies=21)
        cps = select_checkpoints(_make_plies(21), gr)
        assert len(cps) == 2

    def test_40_ply_game_returns_move_10_and_move_20_and_last(self):
        gr = _make_game_record(n_plies=40)
        cps = select_checkpoints(_make_plies(40), gr)
        types = {cp.selected_position_type for cp in cps}
        assert "move_10" in types
        assert "move_20" in types
        assert "last" in types
        # move_20 and last coincide at ply 40
        cp_map = {cp.selected_position_type: cp for cp in cps}
        assert cp_map["move_20"].ply == 40
        assert cp_map["last"].ply == 40


# ---------------------------------------------------------------------------
# Full round-trip: parse_game
# ---------------------------------------------------------------------------

class TestParseGame:
    def test_fixture_round_trip_acceptance(self):
        with open(TINY_FIXTURE) as f:
            game = chess.pgn.read_game(f)
        gr, positions = parse_game(
            game,
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
        )
        assert gr.accepted_basic is True
        assert gr.accepted_eval is True
        assert gr.game_id == "synth0001"

    def test_fixture_round_trip_checkpoint_count(self):
        with open(TINY_FIXTURE) as f:
            game = chess.pgn.read_game(f)
        _, positions = parse_game(
            game,
            source_file="lichess_db_standard_rated_2024-09.pgn.zst",
        )
        assert len(positions) == 5

    def test_rejected_game_returns_empty_positions(self):
        # Wrong time control → rejected → no checkpoints
        gr, positions = parse_game(_parse(_pgn(tc="300+0")))
        assert gr.accepted_basic is False
        assert positions == []

    def test_accepted_game_without_eval_has_empty_accepted_eval(self):
        # Clock-only game is accepted_basic but not accepted_eval
        gr, _ = parse_game(_parse(_pgn()))
        assert gr.accepted_basic is True
        assert gr.accepted_eval is False
