"""Tests for player_metadata.py (Ticket 11.3B). Synthetic names only."""

from __future__ import annotations

import polars as pl
import pytest

from chess_mhsuc import player_metadata as pm

# Synthetic PGN text — NOT real usernames.
_SYNTH_PGN = """[Event "Rated Blitz game"]
[Site "https://lichess.org/abc12345"]
[White "AlphaTester"]
[Black "  betaUser  "]
[WhiteElo "1500"]
[BlackElo "1490"]
[Termination "Normal"]

1. e4 e5 2. Nf3 *

[Event "Rated Blitz game"]
[Site "https://lichess.org/zzz99999"]
[White "GammaBot"]
[Black "AlphaTester"]
[WhiteTitle "BOT"]
[Termination "Time forfeit"]

1. d4 d5 *
"""


# ---- normalization ----

def test_normalize_lowercases_and_strips():
    assert pm.normalize_username("  AlphaTester ") == "alphatester"


def test_normalize_missing_and_anonymous():
    assert pm.normalize_username(None) is None
    assert pm.normalize_username("") is None
    assert pm.normalize_username("   ") is None
    assert pm.normalize_username("?") is None


# ---- hashing ----

def test_hash_deterministic_same_input_and_pepper():
    h1 = pm.hash_player("alpha", pepper="p")
    h2 = pm.hash_player("alpha", pepper="p")
    assert h1 == h2 and h1 is not None


def test_hash_differs_for_different_inputs_and_pepper():
    assert pm.hash_player("alpha", pepper="p") != pm.hash_player("beta", pepper="p")
    assert pm.hash_player("alpha", pepper="p1") != pm.hash_player("alpha", pepper="p2")


def test_hash_not_equal_to_raw_username():
    raw = "alphatester"
    h = pm.hash_player(raw)
    assert h != raw and raw not in h


def test_hash_none_for_anonymous():
    assert pm.hash_player(None) is None


# ---- header parsing ----

def test_parse_header_line():
    assert pm.parse_header_line('[White "Foo"]') == ("White", "Foo")
    assert pm.parse_header_line("1. e4 e5") is None


def test_game_id_from_site():
    assert pm.game_id_from_site("https://lichess.org/abc12345") == "abc12345"
    assert pm.game_id_from_site("https://lichess.org/abc12345/") == "abc12345"
    assert pm.game_id_from_site(None) is None


def test_headers_from_text_two_games():
    games = pm.headers_from_text(_SYNTH_PGN)
    assert len(games) == 2
    assert games[0]["White"] == "AlphaTester"
    assert games[1]["WhiteTitle"] == "BOT"


# ---- extraction over synthetic text ----

def _meta_from_synth(tmp_path) -> pl.DataFrame:
    p = tmp_path / "synth.pgn"
    p.write_text(_SYNTH_PGN)
    return pm.extract_player_metadata(p, version_tag="t_v1", pepper="pep")


def test_extract_columns_and_no_raw_usernames(tmp_path):
    df = _meta_from_synth(tmp_path)
    assert df.columns == pm._OUTPUT_COLS
    # No raw usernames anywhere in the frame values.
    for col in ("white_player_hash", "black_player_hash"):
        vals = df[col].drop_nulls().to_list()
        assert all("alpha" not in v.lower() and "beta" not in v.lower() for v in vals)


def test_extract_bot_flags(tmp_path):
    df = _meta_from_synth(tmp_path)
    row2 = df.filter(pl.col("game_id") == "zzz99999")
    assert row2["white_is_bot"][0] is True
    assert row2["black_is_bot"][0] is False


def test_extract_same_player_same_hash(tmp_path):
    # AlphaTester is White in game1 and Black in game2 -> identical hash.
    df = _meta_from_synth(tmp_path)
    g1 = df.filter(pl.col("game_id") == "abc12345")["white_player_hash"][0]
    g2 = df.filter(pl.col("game_id") == "zzz99999")["black_player_hash"][0]
    assert g1 == g2


def test_assert_no_raw_usernames_rejects_bad_frame():
    bad = pl.DataFrame({"game_id": ["x"], "white": ["raw"]})
    with pytest.raises(ValueError, match="raw username"):
        pm.assert_no_raw_usernames(bad)


def test_metadata_counts(tmp_path):
    df = _meta_from_synth(tmp_path)
    c = df.pipe(pm.metadata_counts)
    assert c["n_games"] == 2
    assert c["n_bot_games"] == 1
    assert c["game_id_unique"] is True
    # 3 distinct players: AlphaTester, betaUser, GammaBot
    assert c["n_unique_players"] == 3


# ---- joins ----

def _meta_frame() -> pl.DataFrame:
    return pl.DataFrame({
        "game_id": ["g1", "g2"],
        "white_player_hash": ["wh1", "wh2"],
        "black_player_hash": ["bh1", "bh2"],
        "white_is_bot": [False, True],
        "black_is_bot": [False, False],
        "version_tag": ["t", "t"],
    })


def test_join_white_black_preserves_rows():
    df = pl.DataFrame({"game_id": ["g1", "g1", "g2"], "x": [1, 2, 3]})
    out = pm.join_white_black(df, _meta_frame())
    assert out.height == 3
    assert out["white_player_hash"].to_list() == ["wh1", "wh1", "wh2"]


def test_join_mover_white_gets_white_hash():
    df = pl.DataFrame({"game_id": ["g1"], "mover_color": ["white"]})
    out = pm.join_mover_player(df, _meta_frame())
    assert out["mover_player_hash"][0] == "wh1"
    assert out["opponent_player_hash"][0] == "bh1"
    assert out["mover_is_bot"][0] is False


def test_join_mover_black_gets_black_hash():
    df = pl.DataFrame({"game_id": ["g2"], "mover_color": ["black"]})
    out = pm.join_mover_player(df, _meta_frame())
    assert out["mover_player_hash"][0] == "bh2"
    assert out["opponent_player_hash"][0] == "wh2"
    # opponent is White (a bot in g2)
    assert out["opponent_is_bot"][0] is True


def test_join_duplicate_metadata_raises():
    dup = pl.concat([_meta_frame(), _meta_frame().head(1)])
    df = pl.DataFrame({"game_id": ["g1"], "mover_color": ["white"]})
    with pytest.raises(ValueError, match="duplicate game_id"):
        pm.join_white_black(df, dup)


def test_join_coverage_counts_unmatched():
    df = pl.DataFrame({"game_id": ["g1", "g3"], "mover_color": ["white", "white"]})
    out = pm.join_mover_player(df, _meta_frame())
    cov = pm.join_coverage(out, "mover_player_hash")
    assert cov["n_rows"] == 2
    assert cov["n_matched"] == 1
    assert cov["n_unmatched"] == 1


def test_locate_raw_pgn_parses_tag(tmp_path, monkeypatch):
    # Build a fake cache so the existence check passes.
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "data/raw/lichess/lichess_2024_09_first250k.pgn"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    assert pm.locate_raw_pgn("2024_09_250k_v1") == target.relative_to(tmp_path) \
        or pm.locate_raw_pgn("2024_09_250k_v1").exists()


def test_locate_raw_pgn_missing_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        pm.locate_raw_pgn("2024_09_250k_v1")
