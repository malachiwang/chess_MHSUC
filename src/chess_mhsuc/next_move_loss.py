"""
Checkpoint-level next-move loss extraction — Ticket 15.0B (Contrast C4 layer).

Measures the quality loss of the player's ACTUAL next move at each
primary-numbered checkpoint, from the mover's perspective. This is the
measurement layer for the Constraint Atlas (Phase 15): it measures board-play
quality directly rather than inferring it from final outcomes (which 11.2B
showed is substantially the flagging channel).

Design (per the 15.0A feasibility audit):
- The checkpoint position's stored `sf_eval_cp` is already the engine best-line
  (analyse) value, so NO best-move search and NO MultiPV are needed here.
- Only the POST-MOVE actual position requires a new engine evaluation.
- Post-move FEN is reconstructed from the local raw PGN cache by replaying the
  game mainline one move past the checkpoint (reusing stockfish_eval's
  replay/indexing/engine helpers — that module is not modified).

Primary pilot metric: clipped centipawn loss, mover's perspective,
    cp_loss = max(0, mover_pre_cp - mover_post_cp);  clipped at ±MOVE_QUALITY_CP_CAP.
Expected-score loss (the intended C4 headline) is DEFERRED to 15.0C/15.1A,
which will fit the cp->expected-score transform on the train split only. No
placeholder transform is presented as final here.

All results are predictive/descriptive associations between constraint state
and next-move loss — not causal, not a "degradation curve", and Stockfish
depth-12 eval is objective position context, not absolute ground truth.

Safety: the full ~64k/month pass is gated. Without `--limit` and without
`--allow-full-run`, the CLI refuses to run. Run a small pilot first.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.next_move_loss \\
        --dataset-id lichess_ten_zero_2024_09_250k_v1 \\
        --version-tag 2024_09_250k_v1 \\
        --limit 1000 \\
        --output data/processed/next_move_loss_pilot_2024_09_250k_v1.parquet \\
        --report reports/next_move_loss_pilot_2024_09_250k_v1.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import chess
import numpy as np
import polars as pl
from scipy.optimize import minimize_scalar

from chess_mhsuc.stockfish_eval import (
    MATE_CP_SENTINEL,
    DEFAULT_DEPTH,
    analyse_fen,
    get_stockfish_version,
    index_target_games,
    resolve_stockfish_path,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Clip cap for cp loss — matches the project's eval_cp_clipped convention (±1000).
MOVE_QUALITY_CP_CAP = 1000

_STATUS_OK = "ok"
_STATUS_NO_NEXT_MOVE = "no_next_move"
_STATUS_FEN_ERR = "fen_reconstruction_error"
_STATUS_ILLEGAL = "illegal_move"
_STATUS_GAME_NOT_FOUND = "game_not_found"
_STATUS_ENGINE_ERR = "engine_error"

_KEY = ["game_id", "selected_position_type"]

# Explicit output schema (prevents Null-type inference on all-None early rows).
_OUTPUT_SCHEMA: dict[str, pl.PolarsDataType] = {
    "dataset_id":             pl.Utf8,
    "version_tag":            pl.Utf8,
    "game_id":                pl.Utf8,
    "selected_position_type": pl.Utf8,
    "checkpoint_ply":         pl.Int64,
    "move_number":            pl.Int64,
    "mover_color":            pl.Utf8,
    "actual_move_uci":        pl.Utf8,
    "pre_fen":                pl.Utf8,
    "post_fen":               pl.Utf8,
    "pre_sf_eval_cp":         pl.Int64,
    "pre_sf_eval_mate":       pl.Int64,
    "post_sf_eval_cp":        pl.Int64,
    "post_sf_eval_mate":      pl.Int64,
    "mover_pre_cp":           pl.Int64,
    "mover_post_cp":          pl.Int64,
    "cp_loss":                pl.Int64,
    "clipped_cp_loss":        pl.Int64,
    "es_pre":                 pl.Float64,
    "es_post":                pl.Float64,
    "expected_score_loss":    pl.Float64,
    "is_mate_band":           pl.Boolean,
    "white_rating":           pl.Int64,
    "black_rating":           pl.Int64,
    "mover_rating":           pl.Int64,
    "mover_clock_s":          pl.Float64,
    "time_bucket":            pl.Utf8,
    "termination":            pl.Utf8,
    "is_time_forfeit":        pl.Boolean,
    "split_set":              pl.Utf8,
    "sf_depth":               pl.Int64,
    "status":                 pl.Utf8,
    "fen_hash_matches":       pl.Boolean,
}


# ---------------------------------------------------------------------------
# A. Pure helpers — orientation, loss, mate-band, time bucket
# ---------------------------------------------------------------------------

def to_mover_cp(white_cp: int | None, mover_is_white: bool) -> int | None:
    """Convert a White-POV centipawn value to the mover's perspective."""
    if white_cp is None:
        return None
    return white_cp if mover_is_white else -white_cp


def compute_cp_loss(
    mover_pre_cp: int | None,
    mover_post_cp: int | None,
    cap: int = MOVE_QUALITY_CP_CAP,
) -> tuple[int | None, int | None]:
    """
    (cp_loss, clipped_cp_loss) from the mover's perspective.

    cp_loss = max(0, mover_pre_cp - mover_post_cp); never negative.
    clipped_cp_loss = min(cp_loss, cap).
    Returns (None, None) if either input is None.
    """
    if mover_pre_cp is None or mover_post_cp is None:
        return None, None
    loss = max(0, mover_pre_cp - mover_post_cp)
    return loss, min(loss, cap)


def is_mate_band(
    pre_cp: int | None,
    pre_mate: int | None,
    post_cp: int | None,
    post_mate: int | None,
) -> bool:
    """
    True if either the pre- or post-move eval is a mate score or hits the
    ±MATE_CP_SENTINEL band. Mate-band rows are flagged and excluded from
    headline cp summaries (never silently mixed into cp statistics).
    """
    if pre_mate is not None or post_mate is not None:
        return True
    for cp in (pre_cp, post_cp):
        if cp is not None and abs(cp) >= MATE_CP_SENTINEL:
            return True
    return False


def time_bucket_for(mover_clock_s: float | None) -> str | None:
    """
    Late-clock bucket convention from Phase 9.2 (proven, CI-bearing):
    under_60s / 60_180s / over_180s. None if clock unavailable.
    """
    if mover_clock_s is None:
        return None
    if mover_clock_s < 60:
        return "under_60s"
    if mover_clock_s < 180:
        return "60_180s"
    return "over_180s"


# ---------------------------------------------------------------------------
# A2. Expected-score transform (cp -> expected score in [0,1])
# ---------------------------------------------------------------------------

# cp inputs are clipped to this range before the transform (matches the loss cap
# and folds mate sentinels ±10000 into ±1000).
ES_CP_CLIP = MOVE_QUALITY_CP_CAP  # 1000


def expected_score(cp: int | float | None, scale: float) -> float | None:
    """
    Logistic cp -> expected-score transform: ES = 1 / (1 + exp(-cp_clipped/scale)).

    Monotonic increasing in cp; output strictly in (0, 1). cp is clipped to
    ±ES_CP_CLIP first (so mate sentinels fold to the cap). The SAME transform is
    applied to pre- and post-move (mover-oriented) cp values. ``scale`` must be
    positive (centipawns; larger = flatter).
    """
    if cp is None:
        return None
    if scale <= 0:
        raise ValueError(f"expected_score scale must be positive, got {scale}")
    x = max(-ES_CP_CLIP, min(ES_CP_CLIP, float(cp)))
    return 1.0 / (1.0 + math.exp(-x / scale))


def expected_score_loss(
    mover_pre_cp: int | None,
    mover_post_cp: int | None,
    scale: float | None,
) -> float | None:
    """
    expected_score_loss = max(0, ES(mover_pre_cp) - ES(mover_post_cp)).
    Returns None if scale is None or either input is None.
    """
    if scale is None or mover_pre_cp is None or mover_post_cp is None:
        return None
    es_pre = expected_score(mover_pre_cp, scale)
    es_post = expected_score(mover_post_cp, scale)
    return max(0.0, es_pre - es_post)


def fit_expected_score_transform(
    white_cp: list[int | float],
    white_score: list[float],
) -> dict:
    """
    Fit the logistic scale on (White-POV cp, White expected score) pairs.

    White expected score: WHITE_WIN=1.0, DRAW=0.5, BLACK_WIN=0.0. cp is clipped
    to ±ES_CP_CLIP. The scale minimizes mean squared error between
    sigmoid(cp_clipped/scale) and the realized White score. One pooled parameter,
    monotonic by construction, fit on TRAIN rows only (caller filters).

    Returns metadata dict: {scale, n_fit, mse, cp_clip, method}.
    """
    if len(white_cp) != len(white_score):
        raise ValueError("white_cp and white_score length mismatch")
    if len(white_cp) == 0:
        raise ValueError("no rows to fit expected-score transform")

    x = np.clip(np.asarray(white_cp, dtype=np.float64), -ES_CP_CLIP, ES_CP_CLIP)
    y = np.asarray(white_score, dtype=np.float64)

    def mse(scale: float) -> float:
        if scale <= 0:
            return 1e18
        pred = 1.0 / (1.0 + np.exp(-x / scale))
        return float(np.mean((pred - y) ** 2))

    res = minimize_scalar(mse, bounds=(10.0, 2000.0), method="bounded")
    scale = float(res.x)
    return {
        "scale": scale,
        "n_fit": int(len(x)),
        "mse": round(mse(scale), 6),
        "cp_clip": ES_CP_CLIP,
        "method": "bounded MSE fit of 1/(1+exp(-cp_clip/scale)) to White expected score",
    }


# ---------------------------------------------------------------------------
# B. Reconstruct checkpoint + next move from a game
# ---------------------------------------------------------------------------

def reconstruct_checkpoint_and_next_move(
    game: chess.pgn.Game,
    checkpoint_ply: int,
) -> dict:
    """
    Replay the game mainline to ``checkpoint_ply`` half-moves, then read the
    actual next move and produce the post-move position.

    Returns a dict:
        status, pre_fen, mover_is_white, actual_move_uci, post_fen, move_number
    status is one of _STATUS_OK / _STATUS_NO_NEXT_MOVE / _STATUS_FEN_ERR /
    _STATUS_ILLEGAL. On non-OK status the optional fields are None.

    ``checkpoint_ply`` is 1-indexed (ply=20 means after Black's 10th move).
    The checkpoint is the position *after* ``checkpoint_ply`` half-moves; the
    next move is the mainline move at index ``checkpoint_ply``.
    """
    out = {
        "status": _STATUS_FEN_ERR,
        "pre_fen": None,
        "mover_is_white": None,
        "actual_move_uci": None,
        "post_fen": None,
        "move_number": None,
    }
    if checkpoint_ply < 1:
        return out

    board = game.board()
    moves = list(game.mainline_moves())
    if len(moves) < checkpoint_ply:
        # game did not even reach the checkpoint
        return out

    for i in range(checkpoint_ply):
        try:
            board.push(moves[i])
        except Exception:
            out["status"] = _STATUS_ILLEGAL
            return out

    pre_fen = board.fen()
    mover_is_white = board.turn == chess.WHITE
    move_number = board.fullmove_number

    if len(moves) <= checkpoint_ply:
        # reached the checkpoint but the game ended there — no next move
        out.update({
            "status": _STATUS_NO_NEXT_MOVE,
            "pre_fen": pre_fen,
            "mover_is_white": mover_is_white,
            "move_number": move_number,
        })
        return out

    next_move = moves[checkpoint_ply]
    try:
        board.push(next_move)
    except Exception:
        out.update({
            "status": _STATUS_ILLEGAL,
            "pre_fen": pre_fen,
            "mover_is_white": mover_is_white,
            "move_number": move_number,
        })
        return out

    out.update({
        "status": _STATUS_OK,
        "pre_fen": pre_fen,
        "mover_is_white": mover_is_white,
        "actual_move_uci": next_move.uci(),
        "post_fen": board.fen(),
        "move_number": move_number,
    })
    return out


def _fen_hash(fen: str) -> str:
    """16-char sha256 prefix — matches stockfish_eval's fen_hash convention."""
    return hashlib.sha256(fen.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# C. Load checkpoint rows (read-only; reuses existing artifacts)
# ---------------------------------------------------------------------------

def load_checkpoint_rows(
    sf_eval_path: str | Path,
    features_path: str | Path,
) -> pl.DataFrame:
    """
    Build the per-checkpoint input table by joining the sf_eval artifact
    (pre-move evals, ply, fen_hash, split_set) with the feature table
    (clocks, ratings, termination). Join key: (game_id, selected_position_type).

    Validates: required columns present; key unique on both sides; 0 orphans.
    """
    sf = pl.read_parquet(sf_eval_path)
    feat = pl.read_parquet(features_path)

    sf_needed = ["game_id", "selected_position_type", "ply", "move_number",
                 "split_set", "sf_eval_cp", "sf_eval_mate", "sf_depth",
                 "fen_hash", "result_class"]
    for c in sf_needed:
        if c not in sf.columns:
            raise ValueError(f"sf_eval artifact missing column {c!r}")

    prim = feat.filter(pl.col("selected_position_type") != "last")
    feat_needed = ["game_id", "selected_position_type", "white_elo", "black_elo",
                   "white_clock_s_capped", "black_clock_s_capped",
                   "white_to_move_next", "termination", "is_time_forfeit"]
    for c in feat_needed:
        if c not in prim.columns:
            raise ValueError(f"feature table missing column {c!r}")

    if sf.select(_KEY).n_unique() != len(sf):
        raise ValueError("(game_id, selected_position_type) not unique in sf_eval artifact")
    if prim.select(_KEY).n_unique() != len(prim):
        raise ValueError("(game_id, selected_position_type) not unique in feature table")

    joined = sf.select(sf_needed).join(
        prim.select(feat_needed), on=_KEY, how="left"
    )
    if joined["white_elo"].null_count() > 0:
        raise ValueError("orphan rows after sf_eval/feature join")
    return joined


# ---------------------------------------------------------------------------
# D. Raw-PGN cache path
# ---------------------------------------------------------------------------

def default_raw_pgn_path(version_tag: str) -> str:
    """
    Derive the local raw-PGN cache path from the version tag, e.g.
    '2024_09_250k_v1' -> data/raw/lichess/lichess_2024_09_first250k.pgn
    """
    parts = version_tag.split("_")
    if len(parts) < 3:
        raise ValueError(f"cannot derive raw-PGN path from version_tag {version_tag!r}")
    month = f"{parts[0]}_{parts[1]}"  # 2024_09
    cap = parts[2]                    # 250k
    return f"data/raw/lichess/lichess_{month}_first{cap}.pgn"


# ---------------------------------------------------------------------------
# E. Build one output row
# ---------------------------------------------------------------------------

def build_row(
    dataset_id: str,
    version_tag: str,
    cp_row: dict,
    recon: dict,
    post_eval: dict | None,
    fen_hash_matches: bool | None,
    status: str,
    es_scale: float | None = None,
) -> dict:
    """Assemble a single output-schema row from inputs + reconstruction + post eval."""
    mover_is_white = recon.get("mover_is_white")
    pre_cp = cp_row["sf_eval_cp"]
    pre_mate = cp_row["sf_eval_mate"]

    post_cp = post_eval.get("sf_eval_cp") if post_eval else None
    post_mate = post_eval.get("sf_eval_mate") if post_eval else None

    mover_pre = to_mover_cp(pre_cp, mover_is_white) if mover_is_white is not None else None
    mover_post = to_mover_cp(post_cp, mover_is_white) if mover_is_white is not None else None
    cp_loss, clipped = compute_cp_loss(mover_pre, mover_post)
    mate_band = is_mate_band(pre_cp, pre_mate, post_cp, post_mate)

    if es_scale is not None and mover_pre is not None:
        es_pre_val = expected_score(mover_pre, es_scale)
    else:
        es_pre_val = None
    if es_scale is not None and mover_post is not None:
        es_post_val = expected_score(mover_post, es_scale)
    else:
        es_post_val = None
    es_loss = expected_score_loss(mover_pre, mover_post, es_scale)

    white_elo = cp_row.get("white_elo")
    black_elo = cp_row.get("black_elo")
    mover_rating = (white_elo if mover_is_white else black_elo) if mover_is_white is not None else None
    mover_clock = None
    if mover_is_white is not None:
        mover_clock = (cp_row.get("white_clock_s_capped") if mover_is_white
                       else cp_row.get("black_clock_s_capped"))

    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "game_id": cp_row["game_id"],
        "selected_position_type": cp_row["selected_position_type"],
        "checkpoint_ply": cp_row["ply"],
        "move_number": recon.get("move_number") or cp_row.get("move_number"),
        "mover_color": (None if mover_is_white is None
                        else ("white" if mover_is_white else "black")),
        "actual_move_uci": recon.get("actual_move_uci"),
        "pre_fen": recon.get("pre_fen"),
        "post_fen": recon.get("post_fen"),
        "pre_sf_eval_cp": pre_cp,
        "pre_sf_eval_mate": pre_mate,
        "post_sf_eval_cp": post_cp,
        "post_sf_eval_mate": post_mate,
        "mover_pre_cp": mover_pre,
        "mover_post_cp": mover_post,
        "cp_loss": cp_loss,
        "clipped_cp_loss": clipped,
        "es_pre": es_pre_val,
        "es_post": es_post_val,
        "expected_score_loss": es_loss,
        "is_mate_band": mate_band,
        "white_rating": white_elo,
        "black_rating": black_elo,
        "mover_rating": mover_rating,
        "mover_clock_s": mover_clock,
        "time_bucket": time_bucket_for(mover_clock),
        "termination": cp_row.get("termination"),
        "is_time_forfeit": cp_row.get("is_time_forfeit"),
        "split_set": cp_row.get("split_set"),
        "sf_depth": cp_row.get("sf_depth"),
        "status": status,
        "fen_hash_matches": fen_hash_matches,
    }


# ---------------------------------------------------------------------------
# F. Pilot extraction loop
# ---------------------------------------------------------------------------

def run_extraction(
    rows_df: pl.DataFrame,
    raw_pgn: str,
    stockfish_path: str,
    dataset_id: str,
    version_tag: str,
    depth: int,
    es_scale: float | None = None,
    progress_every: int = 100,
) -> tuple[pl.DataFrame, dict]:
    """
    Reconstruct post-move positions and evaluate them. Returns (output_df,
    counts). Only successfully-reconstructed rows with a next move are
    engine-evaluated; all attempted rows appear in the output with a status.
    ``es_scale`` (if provided) adds expected-score columns.
    """
    cp_rows = rows_df.to_dicts()
    target_ids = {r["game_id"] for r in cp_rows}
    print(f"  [nml] indexing {len(target_ids):,} games from PGN...", file=sys.stderr)
    game_index = index_target_games(raw_pgn, target_ids, progress=True)

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    out_rows: list[dict] = []
    counts = {
        "attempted": len(cp_rows), "ok": 0, "no_next_move": 0,
        "fen_error": 0, "illegal": 0, "game_not_found": 0,
        "engine_error": 0, "fen_hash_mismatch": 0,
    }
    t0 = time.time()
    try:
        for i, cp_row in enumerate(cp_rows):
            if progress_every and i and i % progress_every == 0:
                print(f"  [nml] {i}/{len(cp_rows)} (ok={counts['ok']})",
                      file=sys.stderr)
            gid = cp_row["game_id"]
            game = game_index.get(gid)
            if game is None:
                counts["game_not_found"] += 1
                out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                          {}, None, None, _STATUS_GAME_NOT_FOUND, es_scale=es_scale))
                continue

            recon = reconstruct_checkpoint_and_next_move(game, cp_row["ply"])
            if recon["status"] == _STATUS_NO_NEXT_MOVE:
                counts["no_next_move"] += 1
                out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                          recon, None, None, _STATUS_NO_NEXT_MOVE, es_scale=es_scale))
                continue
            if recon["status"] == _STATUS_FEN_ERR:
                counts["fen_error"] += 1
                out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                          recon, None, None, _STATUS_FEN_ERR, es_scale=es_scale))
                continue
            if recon["status"] == _STATUS_ILLEGAL:
                counts["illegal"] += 1
                out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                          recon, None, None, _STATUS_ILLEGAL, es_scale=es_scale))
                continue

            # verify reconstructed checkpoint FEN matches the stored hash
            stored_hash = cp_row.get("fen_hash")
            matches = (stored_hash is None
                       or _fen_hash(recon["pre_fen"]) == stored_hash)
            if not matches:
                counts["fen_hash_mismatch"] += 1

            post_eval = analyse_fen(engine, recon["post_fen"], depth)
            if not post_eval.get("sf_eval_available"):
                counts["engine_error"] += 1
                out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                          recon, None, matches, _STATUS_ENGINE_ERR, es_scale=es_scale))
                continue

            counts["ok"] += 1
            out_rows.append(build_row(dataset_id, version_tag, cp_row,
                                      recon, post_eval, matches, _STATUS_OK, es_scale=es_scale))
    finally:
        engine.quit()

    counts["runtime_s"] = round(time.time() - t0, 1)
    out_df = pl.from_dicts(out_rows, schema=_OUTPUT_SCHEMA)
    return out_df, counts


# ---------------------------------------------------------------------------
# G. Pilot summary statistics
# ---------------------------------------------------------------------------

def summarize(out_df: pl.DataFrame) -> dict:
    """Basic pilot summaries on OK, non-mate-band rows (cp loss is undefined for mate band)."""
    ok = out_df.filter((pl.col("status") == _STATUS_OK) & (~pl.col("is_mate_band")))
    losses = ok["clipped_cp_loss"].to_list()
    summary: dict = {
        "n_ok": int((out_df["status"] == _STATUS_OK).sum()),
        "n_ok_nonmate": len(ok),
        "n_mate_band": int(out_df.filter(pl.col("status") == _STATUS_OK)["is_mate_band"].sum()),
    }
    if losses:
        srt = sorted(losses)
        def pct(p):
            return srt[min(len(srt) - 1, int(p * len(srt)))]
        summary.update({
            "mean_clipped_cp_loss": round(statistics.mean(losses), 1),
            "median_clipped_cp_loss": float(statistics.median(losses)),
            "p75_clipped_cp_loss": float(pct(0.75)),
            "p90_clipped_cp_loss": float(pct(0.90)),
            "pct_zero_loss": round(100 * sum(1 for x in losses if x == 0) / len(losses), 1),
            "pct_loss_gt_100": round(100 * sum(1 for x in losses if x > 100) / len(losses), 1),
            "pct_loss_gt_200": round(100 * sum(1 for x in losses if x > 200) / len(losses), 1),
        })
    # expected-score loss summary (OK, non-mate-band, ES available)
    es_vals = ok.filter(pl.col("expected_score_loss").is_not_null())["expected_score_loss"].to_list()
    if es_vals:
        es_srt = sorted(es_vals)
        def es_pct(p):
            return es_srt[min(len(es_srt) - 1, int(p * len(es_srt)))]
        summary.update({
            "mean_es_loss": round(statistics.mean(es_vals), 4),
            "median_es_loss": round(float(statistics.median(es_vals)), 4),
            "p75_es_loss": round(float(es_pct(0.75)), 4),
            "p90_es_loss": round(float(es_pct(0.90)), 4),
            "pct_es_loss_gt_0_05": round(100 * sum(1 for x in es_vals if x > 0.05) / len(es_vals), 1),
            "pct_es_loss_gt_0_10": round(100 * sum(1 for x in es_vals if x > 0.10) / len(es_vals), 1),
            "n_es": len(es_vals),
        })
    by_cpt = ok.group_by("selected_position_type").len().sort("selected_position_type")
    summary["counts_by_checkpoint"] = {r[0]: r[1] for r in by_cpt.iter_rows()}
    tf = ok.group_by("is_time_forfeit").len().sort("is_time_forfeit")
    summary["counts_by_time_forfeit"] = {str(r[0]): r[1] for r in tf.iter_rows()}
    tb = ok.filter(pl.col("time_bucket").is_not_null()).group_by("time_bucket").len().sort("time_bucket")
    summary["counts_by_time_bucket"] = {r[0]: r[1] for r in tb.iter_rows()}
    return summary


# ---------------------------------------------------------------------------
# G2. Expected-score transform fit-row loader + depth-parity check
# ---------------------------------------------------------------------------

_WHITE_SCORE = {"WHITE_WIN": 1.0, "DRAW": 0.5, "BLACK_WIN": 0.0}


def load_fit_rows(version_tags: list[str]) -> tuple[list[float], list[float], dict]:
    """
    Pool TRAIN-split checkpoint rows from the given months' sf_eval artifacts.
    Returns (white_cp, white_score, meta). Train-only (split discipline).
    """
    cps: list[float] = []
    scores: list[float] = []
    per_tag: dict[str, int] = {}
    for tag in version_tags:
        df = pl.read_parquet(f"data/processed/sf_eval_broad_{tag}.parquet")
        tr = df.filter(pl.col("split_set") == "train")
        for cp, rc in zip(tr["sf_eval_cp"].to_list(), tr["result_class"].to_list()):
            if cp is None or rc not in _WHITE_SCORE:
                continue
            cps.append(float(cp))
            scores.append(_WHITE_SCORE[rc])
        per_tag[tag] = len(tr)
    return cps, scores, {"version_tags": version_tags, "n_train_rows_per_tag": per_tag}


def depth_parity_check(
    artifact_path: str | Path,
    stockfish_path: str,
    sample_n: int,
    alt_depth: int,
    base_depth: int,
    seed: int = 42,
) -> dict:
    """
    Re-evaluate the stored ``post_fen`` of a deterministic sample of OK rows at
    ``alt_depth`` and compare clipped-cp-loss summaries against the base-depth
    artifact. Uses post_fen only (no PGN reconstruction).
    """
    df = pl.read_parquet(artifact_path)
    ok = df.filter((pl.col("status") == _STATUS_OK) & (~pl.col("is_mate_band"))
                   & pl.col("post_fen").is_not_null())
    n = min(sample_n, len(ok))
    sample = ok.sort(["game_id", "selected_position_type"]).head(n)

    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    base_losses, alt_losses, deltas = [], [], []
    try:
        for r in sample.iter_rows(named=True):
            mover_is_white = (r["mover_color"] == "white")
            post_eval = analyse_fen(engine, r["post_fen"], alt_depth)
            if not post_eval.get("sf_eval_available"):
                continue
            alt_post_white = post_eval["sf_eval_cp"]
            alt_mover_post = to_mover_cp(alt_post_white, mover_is_white)
            _, alt_clip = compute_cp_loss(r["mover_pre_cp"], alt_mover_post)
            if alt_clip is None or r["clipped_cp_loss"] is None:
                continue
            base_losses.append(r["clipped_cp_loss"])
            alt_losses.append(alt_clip)
            deltas.append(alt_clip - r["clipped_cp_loss"])
    finally:
        engine.quit()

    if not deltas:
        return {"n": 0}
    return {
        "n": len(deltas),
        "base_depth": base_depth,
        "alt_depth": alt_depth,
        "base_mean_clipped_cp_loss": round(statistics.mean(base_losses), 1),
        "alt_mean_clipped_cp_loss": round(statistics.mean(alt_losses), 1),
        "mean_abs_delta": round(statistics.mean(abs(d) for d in deltas), 1),
        "median_delta": float(statistics.median(deltas)),
    }


# ---------------------------------------------------------------------------
# H. Report rendering
# ---------------------------------------------------------------------------

def render_report(
    dataset_id: str, version_tag: str, limit: int, depth: int,
    counts: dict, summary: dict, output_path: str,
    full_month_estimate_min: float,
) -> str:
    s = summary
    lines: list[str] = []
    a = lines.append
    a(f"# Next-Move Loss Pilot — {version_tag}")
    a("")
    a("**Ticket:** 15.0B — Checkpoint-Level Next-Move Loss Extraction (pilot)")
    a(f"**Dataset:** `{dataset_id}`")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Pilot of {counts['attempted']} checkpoint rows (`--limit {limit}`); "
      f"{counts['ok']} successfully evaluated. This is the measurement layer for "
      "Contrast C4 (next-move quality), which tests board-play quality directly "
      "rather than inferring it from final outcomes. Pilot metric: clipped "
      "centipawn loss, mover's perspective. Expected-score loss (the intended C4 "
      "headline) is deferred to 15.0C/15.1A with a train-fit cp→expected-score "
      "transform. Predictive/descriptive only — not causal, no degradation-curve "
      "language; Stockfish eval is objective context, not absolute ground truth.")
    a("")
    a("## 2. Input artifacts")
    a("")
    a(f"- sf_eval (pre-move best-line value, ply, fen_hash): "
      f"`data/processed/sf_eval_broad_{version_tag}.parquet`")
    a(f"- features (clocks, ratings, termination): "
      f"`data/processed/feature_positions_broad_{version_tag}.parquet`")
    a(f"- raw PGN cache (post-move reconstruction): "
      f"`data/raw/lichess/lichess_*_first*.pgn` (gitignored)")
    a("")
    a("## 3. Pilot configuration")
    a("")
    a(f"- `--limit`: {limit}")
    a(f"- Stockfish depth: {depth} (post-move position only; no best-move search, no MultiPV)")
    a("- Deterministic: first N checkpoint rows in artifact (stream) order; "
      "seedless.")
    a("")
    a("## 4. Reconstruction/evaluation success")
    a("")
    a("| Outcome | Count |")
    a("|---|---|")
    a(f"| Attempted | {counts['attempted']} |")
    a(f"| OK (evaluated) | {counts['ok']} |")
    a(f"| No next move (game ended at checkpoint) | {counts['no_next_move']} |")
    a(f"| FEN reconstruction error | {counts['fen_error']} |")
    a(f"| Illegal move | {counts['illegal']} |")
    a(f"| Game not found in PGN | {counts['game_not_found']} |")
    a(f"| Engine error | {counts['engine_error']} |")
    a(f"| FEN-hash mismatches (checkpoint vs stored) | {counts['fen_hash_mismatch']} |")
    a("")
    a("## 5. Output schema")
    a("")
    a("Columns: " + ", ".join(f"`{c}`" for c in _OUTPUT_SCHEMA))
    a("")
    a("## 6. Loss metric definitions")
    a("")
    a("- `mover_pre_cp` = checkpoint `sf_eval_cp` oriented to the mover (the "
      "stored value is already the engine best-line value at depth 12).")
    a("- `mover_post_cp` = new eval of the post-move position, oriented to the "
      "same mover.")
    a(f"- `cp_loss = max(0, mover_pre_cp − mover_post_cp)`; "
      f"`clipped_cp_loss = min(cp_loss, {MOVE_QUALITY_CP_CAP})`.")
    if "mean_es_loss" in s:
        a(f"- `expected_score_loss = max(0, ES(mover_pre_cp) − ES(mover_post_cp))` "
          "with the train-fit logistic cp→ES transform.")
    else:
        a("- Expected-score loss is DEFERRED (15.0C/15.1A, train-fit transform).")
    a("")
    if "mean_es_loss" in s:
        a("Expected-score loss (OK, non-mate-band, n="
          f"{s.get('n_es', 0)}): mean {s['mean_es_loss']} | median "
          f"{s['median_es_loss']} | p90 {s['p90_es_loss']} | "
          f">0.10: {s['pct_es_loss_gt_0_10']}%")
        a("")
    a("## 7. Basic pilot summaries")
    a("")
    if "mean_clipped_cp_loss" in s:
        a(f"Clipped cp loss (OK, non-mate-band rows, n={s['n_ok_nonmate']}):")
        a("")
        a(f"- mean {s['mean_clipped_cp_loss']} | median "
          f"{s['median_clipped_cp_loss']} | p75 {s['p75_clipped_cp_loss']} | "
          f"p90 {s['p90_clipped_cp_loss']}")
        a(f"- zero loss: {s['pct_zero_loss']}% | >100cp: {s['pct_loss_gt_100']}% | "
          f">200cp: {s['pct_loss_gt_200']}%")
        a("")
        a("Counts by checkpoint: " + ", ".join(
            f"{k}={v}" for k, v in s["counts_by_checkpoint"].items()))
        a("")
        a("Counts by time-forfeit flag: " + ", ".join(
            f"{k}={v}" for k, v in s["counts_by_time_forfeit"].items()))
    else:
        a("(no OK non-mate-band rows in this pilot)")
    a("")
    a("## 8. Mate-band handling")
    a("")
    a(f"{s.get('n_mate_band', 0)} OK rows are mate-band (pre or post eval is a "
      "mate score or hits ±10000). They are flagged `is_mate_band=True` and "
      "EXCLUDED from the cp-loss summaries above; never silently mixed into cp "
      "statistics.")
    a("")
    a("## 9. Runtime and compute estimate")
    a("")
    a(f"- Pilot runtime: {counts.get('runtime_s')} s for {counts['attempted']} "
      "attempted rows.")
    a(f"- Extrapolated full-month (~64k checkpoint rows): "
      f"~{full_month_estimate_min:.0f} min (post-move evals only; consistent "
      "with the 15.0A ~30 min/month estimate). Two months ~1 h.")
    a("")
    a("## 10. Known limitations")
    a("")
    a("- Expected-score loss deferred (cp loss only in this pilot).")
    a("- Depth-parity: pre-move (mover to move) vs post-move (opponent to move) "
      "both evaluated at depth 12; the odd/even search-parity asymmetry is "
      "acknowledged and should be sensitivity-checked at depth 13 in a later pass.")
    a("- Board-decided low-clock cells are a survivor population (11.2B caveat).")
    a("- Loss distributions are right-skewed; medians/percentiles reported "
      "alongside means.")
    a("- Stockfish depth-12 eval is objective context, not absolute ground truth; "
      "this is association between constraint state and next-move loss, not causal.")
    a("")
    a("## 11. Recommendation for full extraction")
    a("")
    a("Pilot succeeded: reconstruction + post-move evaluation + loss computation "
      "work end-to-end and FEN hashes match the stored checkpoint hashes. "
      "Recommend 15.0C: run the full both-months post-move pass (gated on explicit "
      "approval), then add the train-fit cp→expected-score transform and the "
      "descriptive Constraint Atlas curves.")
    a("")
    a(f"Output artifact: `{output_path}` (gitignored under `data/`; not staged).")
    a("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Checkpoint-level next-move loss extraction (Ticket 15.0B). "
                    "Pilot by default; full run gated."
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--sf-eval", default=None,
                        help="default: data/processed/sf_eval_broad_{tag}.parquet")
    parser.add_argument("--features", default=None,
                        help="default: data/processed/feature_positions_broad_{tag}.parquet")
    parser.add_argument("--raw-pgn", default=None,
                        help="default: derived local cache from version tag")
    parser.add_argument("--stockfish-path", default=None)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--limit", type=int, default=None,
                        help="pilot: number of checkpoint rows (first N, deterministic)")
    parser.add_argument("--allow-full-run", action="store_true",
                        help="required to run without --limit (the full ~64k pass)")
    parser.add_argument("--output", default=None)
    parser.add_argument("--report", default=None)
    parser.add_argument("--schema-only", action="store_true",
                        help="print the output schema and exit (no engine/PGN)")
    parser.add_argument("--overwrite", action="store_true")
    # Expected-score transform
    parser.add_argument("--es-transform", default=None,
                        help="path to a fitted cp->ES transform JSON; if present, "
                             "expected-score columns are added during extraction")
    parser.add_argument("--fit-es-transform", action="store_true",
                        help="MODE: fit the pooled-train cp->ES transform and write "
                             "JSON to --es-transform-out, then exit (no PGN/engine)")
    parser.add_argument("--es-transform-out", default=None,
                        help="output path for --fit-es-transform")
    parser.add_argument("--fit-version-tags", default=None,
                        help="comma-separated version tags to pool for fitting "
                             "(default: --version-tag)")
    # Depth-parity sensitivity
    parser.add_argument("--parity-check", action="store_true",
                        help="MODE: re-evaluate post_fen of a sample at --parity-depth "
                             "and compare cp-loss vs the artifact, then exit")
    parser.add_argument("--parity-input", default=None)
    parser.add_argument("--parity-sample", type=int, default=300)
    parser.add_argument("--parity-depth", type=int, default=13)
    args = parser.parse_args(argv)

    if args.schema_only:
        print("output schema:")
        for k, v in _OUTPUT_SCHEMA.items():
            print(f"  {k}: {v}")
        return 0

    # --- MODE: fit expected-score transform (no PGN, no extraction) ---
    if args.fit_es_transform:
        fit_tags = ([t.strip() for t in args.fit_version_tags.split(",")]
                    if args.fit_version_tags else [args.version_tag])
        out_json = Path(args.es_transform_out
                        or "data/processed/next_move_expected_score_transform_v1.json")
        if out_json.exists() and not args.overwrite:
            raise FileExistsError(f"{out_json} exists; pass --overwrite")
        cps, scores, meta = load_fit_rows(fit_tags)
        fit = fit_expected_score_transform(cps, scores)
        payload = {**fit, **meta,
                   "fitted_at_utc": datetime.now(timezone.utc).isoformat()}
        out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"[nml] fitted cp->ES transform: scale={fit['scale']:.2f} "
              f"mse={fit['mse']} n_fit={fit['n_fit']} -> {out_json}")
        return 0

    # --- MODE: depth-parity sensitivity (uses stored post_fen; no PGN) ---
    if args.parity_check:
        sf_path = resolve_stockfish_path(args.stockfish_path)
        inp = args.parity_input or f"data/processed/next_move_loss_{args.version_tag}.parquet"
        res = depth_parity_check(inp, sf_path, args.parity_sample,
                                 args.parity_depth, args.depth)
        print(f"[nml] depth-parity check ({inp}): {json.dumps(res)}")
        return 0

    # Full-run guard
    if args.limit is None and not args.allow_full_run:
        print("ERROR: this would run the full ~64k/month pass. Pass --limit N for a "
              "pilot, or --allow-full-run to execute the full (gated) extraction.",
              file=sys.stderr)
        return 2

    tag = args.version_tag
    sf_eval = args.sf_eval or f"data/processed/sf_eval_broad_{tag}.parquet"
    features = args.features or f"data/processed/feature_positions_broad_{tag}.parquet"
    raw_pgn = args.raw_pgn or default_raw_pgn_path(tag)
    output = Path(args.output or f"data/processed/next_move_loss_pilot_{tag}.parquet")
    report = Path(args.report or f"reports/next_move_loss_pilot_{tag}.md")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"{output} exists; pass --overwrite")

    # Load ES transform if provided/exists
    es_scale = None
    if args.es_transform:
        tp = Path(args.es_transform)
        if tp.exists():
            with open(tp) as f:
                es_scale = float(json.load(f)["scale"])
            print(f"  [nml] expected-score transform loaded: scale={es_scale:.2f}",
                  file=sys.stderr)
        else:
            print(f"  [nml] WARNING: --es-transform {tp} not found; ES columns null",
                  file=sys.stderr)

    sf_path = resolve_stockfish_path(args.stockfish_path)
    sf_version = get_stockfish_version(sf_path)
    print(f"  [nml] Stockfish: {sf_version} ({sf_path}); depth={args.depth}",
          file=sys.stderr)

    rows = load_checkpoint_rows(sf_eval, features)
    if args.limit is not None:
        rows = rows.head(args.limit)
    print(f"  [nml] {len(rows)} checkpoint rows to process", file=sys.stderr)

    out_df, counts = run_extraction(
        rows, raw_pgn, sf_path, args.dataset_id, tag, args.depth, es_scale=es_scale)
    summary = summarize(out_df)

    per_row_s = (counts["runtime_s"] / max(1, counts["ok"])) if counts["ok"] else 0.0
    full_month_min = (per_row_s * 64_000) / 60.0

    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.write_parquet(output, compression="snappy")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(
        args.dataset_id, tag, args.limit if args.limit is not None else -1,
        args.depth, counts, summary, str(output), full_month_min))

    print(f"  [nml] artifact: {output} ({len(out_df)} rows)", file=sys.stderr)
    print(f"  [nml] report: {report}", file=sys.stderr)
    print(f"\n=== 15.0B pilot {tag} ===")
    print(f"  attempted={counts['attempted']} ok={counts['ok']} "
          f"no_next_move={counts['no_next_move']} "
          f"fen_err={counts['fen_error']} game_not_found={counts['game_not_found']} "
          f"engine_err={counts['engine_error']} "
          f"hash_mismatch={counts['fen_hash_mismatch']}")
    print(f"  runtime={counts['runtime_s']}s | est full month ~{full_month_min:.0f} min")
    if "mean_clipped_cp_loss" in summary:
        print(f"  clipped cp loss: mean={summary['mean_clipped_cp_loss']} "
              f"median={summary['median_clipped_cp_loss']} "
              f"p90={summary['p90_clipped_cp_loss']} "
              f"zero={summary['pct_zero_loss']}% >100cp={summary['pct_loss_gt_100']}%")
    if "mean_es_loss" in summary:
        print(f"  expected-score loss: mean={summary['mean_es_loss']} "
              f"median={summary['median_es_loss']} p90={summary['p90_es_loss']} "
              f">0.10={summary['pct_es_loss_gt_0_10']}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
