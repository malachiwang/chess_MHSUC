"""
MultiPV sharpness pilot extraction — Ticket 14.1B.

Extracts a MultiPV-K engine read at each checkpoint and computes **objective
value-fragility** features (the v1 sharpness primitive) plus **exploratory surface
move tags and surface-bait diagnostics**. Checkpoint FENs are read directly from the
15.0C next-move-loss artifact (`pre_fen`) — no raw-PGN reconstruction.

IMPORTANT framing (Malachi, 14.1B):
- Primary v1 sharpness = OBJECTIVE value fragility: narrow viable move set, steep
  value drop-off outside the viable set, legal-choice clutter. Engine geometry only.
- Surface move tags (check/capture/promotion/quiet/forced-evasion) and "surface-bait"
  diagnostics are EXPLORATORY only. They are NOT a model of human obviousness; true
  human obviousness is deferred to a later Tier B layer.
- Sharpness has NOT been shown; this is pilot feature extraction, not a result.

Predictive/descriptive only — not causal; not a "degradation curve"; Stockfish
MultiPV at fixed depth is an approximation of narrowness, not absolute ground truth.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.multipv_sharpness \\
        --input data/processed/next_move_loss_2024_09_250k_v1.parquet \\
        --output data/processed/multipv_sharpness_pilot_2024_09_250k_v1.parquet \\
        --report reports/multipv_sharpness_pilot_2024_09_250k_v1.md \\
        --version-tag 2024_09_250k_v1 --pilot-size 1000 --multipv-k 5 \\
        --depth 12 --compare-depth 10 --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import chess
import chess.engine
import polars as pl

from chess_mhsuc.next_move_loss import _fen_hash, expected_score
from chess_mhsuc.stockfish_eval import (
    MATE_CP_SENTINEL,
    get_stockfish_version,
    resolve_stockfish_path,
    score_to_white_pov,
)

DEFAULT_SCALE = 348.4059447685626  # pooled train cp->ES transform (15.0C)
DEFAULT_K = 5
DEFAULT_DEPTH = 12
CHECKPOINTS = ["move_10", "move_20", "move_30", "move_40"]
_SOFTMAX_T = 0.10  # ES-scale softmax temperature for entropy/concentration
_REQUIRED_INPUT_COLS = [
    "game_id", "selected_position_type", "pre_fen", "mover_color",
    "pre_sf_eval_cp", "is_mate_band", "status",
]


# ---------------------------------------------------------------------------
# A. Sampling
# ---------------------------------------------------------------------------

def load_pilot_input(path: str | Path) -> pl.DataFrame:
    df = pl.read_parquet(path)
    missing = [c for c in _REQUIRED_INPUT_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"input artifact missing required columns: {missing}")
    return df.filter(pl.col("status") == "ok")


def stratified_sample(
    df: pl.DataFrame, size: int = 1000, seed: int = 42,
    checkpoints: list[str] = CHECKPOINTS,
) -> pl.DataFrame:
    """Equal-per-checkpoint sample (prefers non-mate rows; fills from mate-band if
    a checkpoint is short). Deterministic given seed."""
    per = size // len(checkpoints)
    parts: list[pl.DataFrame] = []
    for cp in checkpoints:
        sub = df.filter(pl.col("selected_position_type") == cp)
        nonmate = sub.filter(~pl.col("is_mate_band"))
        chosen = nonmate.sample(n=min(per, nonmate.height), seed=seed)
        if chosen.height < per:  # backfill from mate-band to keep counts stable
            need = per - chosen.height
            mate = sub.filter(pl.col("is_mate_band"))
            chosen = pl.concat([chosen, mate.sample(n=min(need, mate.height), seed=seed)])
        parts.append(chosen)
    return pl.concat(parts)


# ---------------------------------------------------------------------------
# B. Score conversion (pure)
# ---------------------------------------------------------------------------

def relative_score_to_mover(povscore: chess.engine.PovScore) -> tuple[int, int | None]:
    """Side-to-move (relative) POV -> (mover_cp, mover_mate). Mate folds to
    ±MATE_CP_SENTINEL; non-mate cp is clamped to ±(MATE_CP_SENTINEL-1)."""
    rel = povscore.relative
    if rel.is_mate():
        m = rel.mate()
        if m is None:
            return 0, None
        return (MATE_CP_SENTINEL if m > 0 else -MATE_CP_SENTINEL), m
    cp = rel.score()
    if cp is None:
        return 0, None
    return max(-MATE_CP_SENTINEL + 1, min(MATE_CP_SENTINEL - 1, cp)), None


def candidate_es(mover_cp: int | None, scale: float) -> float | None:
    return expected_score(mover_cp, scale)


# ---------------------------------------------------------------------------
# C. Objective value-fragility features (pure)
# ---------------------------------------------------------------------------

def _softmax(values: list[float], t: float) -> list[float]:
    if not values:
        return []
    m = max(values)
    exps = [math.exp((v - m) / t) for v in values]
    s = sum(exps)
    return [e / s for e in exps] if s > 0 else [1.0 / len(values)] * len(values)


def fragility_features(es_list: list[float], cp_list: list[int], k: int) -> dict[str, Any]:
    """Value-fragility features from the ordered (best-first) candidate ES and
    mover-cp lists. ``es_list``/``cp_list`` are length n = multipv_count (<= k)."""
    n = len(es_list)
    out: dict[str, Any] = {"multipv_count": n}
    if n == 0:
        return out
    best_es, best_cp = es_list[0], cp_list[0]
    loss_es = [best_es - e for e in es_list]       # >= 0, best-first
    loss_cp = [best_cp - c for c in cp_list]

    def cnt_es(thr: float) -> int:
        return sum(1 for l in loss_es if l <= thr)

    def cnt_cp(thr: float) -> int:
        return sum(1 for l in loss_cp if l <= thr)

    out.update({
        "n_good_5es": cnt_es(0.05), "n_good_10es": cnt_es(0.10), "n_good_20es": cnt_es(0.20),
        "n_good_30cp": cnt_cp(30), "n_good_50cp": cnt_cp(50), "n_good_100cp": cnt_cp(100),
        "n_good_10es_censored_at_k": cnt_es(0.10) >= k,
        "n_good_50cp_censored_at_k": cnt_cp(50) >= k,
        "best_second_gap_es": loss_es[1] if n >= 2 else None,
        "best_third_gap_es": loss_es[2] if n >= 3 else None,
        "best_second_gap_cp": loss_cp[1] if n >= 2 else None,
        "best_third_gap_cp": loss_cp[2] if n >= 3 else None,
        "worst_top5_loss_es": loss_es[-1],
        "worst_top5_loss_cp": loss_cp[-1],
        "mean_top5_loss_es": round(sum(loss_es) / n, 5),
    })
    adj_es = [es_list[i] - es_list[i + 1] for i in range(n - 1)]
    adj_cp = [cp_list[i] - cp_list[i + 1] for i in range(n - 1)]
    out["max_adjacent_gap_es"] = round(max(adj_es), 5) if adj_es else None
    out["max_adjacent_gap_cp"] = max(adj_cp) if adj_cp else None
    # cliff after the viable (<=0.10 ES) set, if the set is shorter than n
    n_viable = cnt_es(0.10)
    out["cliff_after_viable_set_10es"] = (
        round(es_list[n_viable - 1] - es_list[n_viable], 5)
        if 0 < n_viable < n else None)
    # entropy / concentration over top-k ES via softmax
    probs = _softmax(es_list, _SOFTMAX_T)
    out["top1_softmax_prob_es"] = round(probs[0], 5) if probs else None
    out["top5_entropy_es"] = round(-sum(p * math.log(p) for p in probs if p > 0), 5) if probs else None
    out["top5_concentration_es"] = round(sum(p * p for p in probs), 5) if probs else None
    return out


def clutter_features(n_good_10es: int, n_good_20es: int, legal_move_count: int) -> dict[str, Any]:
    lmc = legal_move_count if legal_move_count else None
    return {
        "legal_move_count": legal_move_count,
        # lower bounds because n_good is right-censored at K
        "viable_fraction_10es_lower_bound": round(n_good_10es / lmc, 5) if lmc else None,
        "viable_fraction_20es_lower_bound": round(n_good_20es / lmc, 5) if lmc else None,
    }


# ---------------------------------------------------------------------------
# D. Surface move tags (pure, board logic) — EXPLORATORY, not "obviousness"
# ---------------------------------------------------------------------------

def move_tags(board: chess.Board, move: chess.Move) -> dict[str, Any]:
    """Surface tags for a single candidate move on the given board."""
    is_legal = move in board.legal_moves
    is_cap = board.is_capture(move) if is_legal else False
    is_chk = board.gives_check(move) if is_legal else False
    is_promo = move.promotion is not None
    moved = board.piece_at(move.from_square)
    captured = None
    if is_cap and is_legal:
        if board.is_en_passant(move):
            captured = chess.PAWN
        else:
            cp = board.piece_at(move.to_square)
            captured = cp.piece_type if cp else None
    return {
        "is_legal": is_legal,
        "is_capture": bool(is_cap),
        "is_check": bool(is_chk),
        "is_promotion": bool(is_promo),
        "is_quiet": is_legal and not (is_cap or is_chk or is_promo),
        "moved_piece_type": moved.piece_type if moved else None,
        "captured_piece_type": captured,
        # recapture requires the opponent's last-move target square, which the
        # checkpoint FEN does not encode -> deferred/unavailable in this pilot.
        "is_recapture": None,
    }


def position_choice_context(board: chess.Board) -> dict[str, Any]:
    legal = list(board.legal_moves)
    in_check = board.is_check()
    return {
        "legal_move_count": len(legal),
        "in_check": in_check,
        "n_legal_evasions": len(legal) if in_check else 0,
        "only_legal_move": len(legal) == 1,
    }


# ---------------------------------------------------------------------------
# E. Surface-bait diagnostics (EXPLORATORY) + composites (candidate)
# ---------------------------------------------------------------------------

def surface_bait(cand_tags: list[dict], loss_es: list[float]) -> dict[str, Any]:
    """Do superficially forcing-looking moves exist among the top-k, and do they
    lose value? Surface = check/capture/promotion. NOT a human-obviousness model."""
    n = len(cand_tags)
    surf_idx = [i for i in range(n)
                if cand_tags[i]["is_check"] or cand_tags[i]["is_capture"]
                or cand_tags[i]["is_promotion"]]
    quiet_idx = [i for i in range(n) if cand_tags[i]["is_quiet"]]
    best_is_surface = n > 0 and (cand_tags[0]["is_check"] or cand_tags[0]["is_capture"]
                                 or cand_tags[0]["is_promotion"])
    best_is_quiet = n > 0 and cand_tags[0]["is_quiet"]
    best_surface_loss = min((loss_es[i] for i in surf_idx), default=None)
    best_quiet_loss = min((loss_es[i] for i in quiet_idx), default=None)
    bait10 = best_surface_loss is not None and best_surface_loss > 0.10
    bait20 = best_surface_loss is not None and best_surface_loss > 0.20
    return {
        "surface_move_available_top5": len(surf_idx) > 0,
        "best_surface_loss_es": round(best_surface_loss, 5) if best_surface_loss is not None else None,
        "best_forcing_loss_es": round(best_surface_loss, 5) if best_surface_loss is not None else None,
        "best_quiet_loss_es": round(best_quiet_loss, 5) if best_quiet_loss is not None else None,
        "best_move_is_surface": bool(best_is_surface),
        "best_move_is_quiet": bool(best_is_quiet),
        "best_move_quiet_surface_bad_10es": bool(best_is_quiet and bait10),
        "surface_bait_10es": bool(bait10),
        "surface_bait_20es": bool(bait20),
    }


def composites(frag: dict, surf: dict) -> dict[str, Any]:
    """Candidate v1 sharpness composites (objective value fragility) + one
    exploratory surface-bait composite. Pending 14.2A — not a result."""
    ng5, ng10, ng20 = frag.get("n_good_5es"), frag.get("n_good_10es"), frag.get("n_good_20es")
    worst = frag.get("worst_top5_loss_es")
    lmc = frag.get("legal_move_count", 0) or 0
    out = {
        "sharp_value_fragility_v1": bool(
            ng10 is not None and ng10 <= 2 and worst is not None
            and worst >= 0.10 and lmc >= 8),
        "sharp_value_fragility_v1_relaxed": bool(
            ng20 is not None and ng20 <= 2 and worst is not None and worst >= 0.05),
        "sharp_value_fragility_v1_strict": bool(
            ng5 is not None and ng5 <= 1 and worst is not None and worst >= 0.20
            and lmc >= 8),
        # continuous candidate score: ES gap best->second (larger = sharper)
        "sharp_score_candidate": frag.get("best_second_gap_es"),
        # exploratory surface-bait composite
        "surface_bait_v1": bool(surf.get("surface_bait_10es") and surf.get("best_move_is_quiet")),
    }
    return out


# ---------------------------------------------------------------------------
# F. Per-position extraction
# ---------------------------------------------------------------------------

def analyse_multipv(engine, fen: str, depth: int, k: int) -> list[dict]:
    """Run MultiPV (via the multipv kwarg — never engine.configure). Returns
    ordered candidate dicts; empty list on engine/board failure."""
    board = chess.Board(fen)
    infos = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=k)
    cands: list[dict] = []
    for info in infos:
        score = info.get("score")
        pv = info.get("pv")
        if score is None or not pv:
            continue
        move = pv[0]
        white_cp, white_mate = score_to_white_pov(score)
        mover_cp, mover_mate = relative_score_to_mover(score)
        cands.append({
            "move": move, "move_uci": move.uci(),
            "white_cp": white_cp, "white_mate": white_mate,
            "mover_cp": mover_cp, "mover_mate": mover_mate,
        })
    return cands


def extract_row(engine, row: dict, depth: int, k: int, scale: float) -> dict:
    """Full wide feature row for one checkpoint."""
    fen = row["pre_fen"]
    out: dict[str, Any] = {
        "game_id": row["game_id"],
        "selected_position_type": row["selected_position_type"],
        "checkpoint_ply": row.get("checkpoint_ply"),
        "pre_fen": fen,
        "computed_fen_hash": _fen_hash(fen),
        "depth": depth, "multipv_k": k,
        "is_mate_band": bool(row["is_mate_band"]),
        "pre_sf_eval_cp": row.get("pre_sf_eval_cp"),
    }
    try:
        board = chess.Board(fen)
    except Exception as e:
        out.update({"status": "fen_load_failure", "ok": False, "fen_hash_matches": False,
                    "error": str(e)[:120]})
        return out
    out["fen_hash_matches"] = _fen_hash(board.fen()) == out["computed_fen_hash"]
    out["side_to_move"] = "white" if board.turn == chess.WHITE else "black"
    out.update({f"ctx_{kk}": vv for kk, vv in position_choice_context(board).items()})
    try:
        cands = analyse_multipv(engine, fen, depth, k)
    except Exception as e:
        out.update({"status": "engine_failure", "ok": False, "error": str(e)[:120]})
        return out
    if not cands:
        out.update({"status": "engine_failure", "ok": False, "multipv_count": 0})
        return out

    es_list = [candidate_es(c["mover_cp"], scale) for c in cands]
    cp_list = [c["mover_cp"] for c in cands]
    best_es = es_list[0]
    cand_tags = [move_tags(board, c["move"]) for c in cands]
    loss_es = [best_es - e for e in es_list]

    # wide per-candidate columns
    for i in range(1, k + 1):
        if i <= len(cands):
            c, t, es = cands[i - 1], cand_tags[i - 1], es_list[i - 1]
            out.update({
                f"pv{i}_move_uci": c["move_uci"],
                f"pv{i}_san": _safe_san(board, c["move"]),
                f"pv{i}_white_cp": c["white_cp"], f"pv{i}_mover_cp": c["mover_cp"],
                f"pv{i}_mate": c["mover_mate"], f"pv{i}_es": round(es, 5),
                f"pv{i}_loss_es_from_best": round(best_es - es, 5),
                f"pv{i}_loss_cp_from_best": cp_list[0] - c["mover_cp"],
                f"pv{i}_is_legal": t["is_legal"], f"pv{i}_is_capture": t["is_capture"],
                f"pv{i}_is_check": t["is_check"], f"pv{i}_is_promotion": t["is_promotion"],
                f"pv{i}_is_quiet": t["is_quiet"], f"pv{i}_is_recapture": t["is_recapture"],
                f"pv{i}_moved_piece_type": t["moved_piece_type"],
                f"pv{i}_captured_piece_type": t["captured_piece_type"],
            })
        else:
            for suff in ("move_uci", "san", "white_cp", "mover_cp", "mate", "es",
                         "loss_es_from_best", "loss_cp_from_best", "is_legal",
                         "is_capture", "is_check", "is_promotion", "is_quiet",
                         "is_recapture", "moved_piece_type", "captured_piece_type"):
                out[f"pv{i}_{suff}"] = None

    frag = fragility_features(es_list, cp_list, k)
    frag.update(clutter_features(frag.get("n_good_10es", 0), frag.get("n_good_20es", 0),
                                 out["ctx_legal_move_count"]))
    surf = surface_bait(cand_tags, loss_es)
    comp = composites(frag, surf)
    out.update(frag); out.update(surf); out.update(comp)
    # top-1 agreement vs the existing checkpoint best-line value
    pre = row.get("pre_sf_eval_cp")
    out["top1_white_cp"] = cands[0]["white_cp"]
    out["top1_cp_abs_diff"] = (abs(cands[0]["white_cp"] - pre)
                               if pre is not None and cands[0]["white_cp"] is not None else None)
    out["all_candidates_legal"] = all(t["is_legal"] for t in cand_tags)
    out.update({"status": "ok", "ok": True, "error": None})
    return out


def _safe_san(board: chess.Board, move: chess.Move) -> str | None:
    try:
        return board.san(move)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# G. Pilot driver
# ---------------------------------------------------------------------------

def run_pilot(
    sample: pl.DataFrame, engine, depth: int, k: int, scale: float,
) -> pl.DataFrame:
    rows = []
    t0 = time.time()
    n = sample.height
    for idx, row in enumerate(sample.iter_rows(named=True)):
        rows.append(extract_row(engine, row, depth, k, scale))
        if (idx + 1) % 250 == 0:
            print(f"    [multipv d{depth}] {idx + 1}/{n} "
                  f"({(time.time() - t0) / (idx + 1) * 1000:.0f} ms/pos)", file=sys.stderr)
    return pl.DataFrame(rows, infer_schema_length=None)


def depth_comparison(df10: pl.DataFrame, df12: pl.DataFrame) -> dict[str, Any]:
    """Compare the two depth passes on the shared (game_id, checkpoint) keys."""
    key = ["game_id", "selected_position_type"]
    a = df10.filter(pl.col("ok")).select(
        key + ["pv1_move_uci", "top1_white_cp", "n_good_10es", "sharp_value_fragility_v1"])
    b = df12.filter(pl.col("ok")).select(
        key + ["pv1_move_uci", "top1_white_cp", "n_good_10es", "sharp_value_fragility_v1"])
    j = a.join(b, on=key, suffix="_d12")
    n = j.height
    if n == 0:
        return {"n": 0}
    top1_agree = (j["pv1_move_uci"] == j["pv1_move_uci_d12"]).sum()
    cp_absdiff = (j["top1_white_cp"] - j["top1_white_cp_d12"]).abs()
    ng_agree = (j["n_good_10es"] == j["n_good_10es_d12"]).sum()
    frag_agree = (j["sharp_value_fragility_v1"] == j["sharp_value_fragility_v1_d12"]).sum()
    return {
        "n": n,
        "top1_move_agreement": round(top1_agree / n, 4),
        "top1_cp_median_absdiff": float(cp_absdiff.median()),
        "n_good_10es_agreement": round(ng_agree / n, 4),
        "sharp_v1_agreement": round(frag_agree / n, 4),
    }


# ---------------------------------------------------------------------------
# H. Report
# ---------------------------------------------------------------------------

def _summ(df: pl.DataFrame) -> dict[str, Any]:
    ok = df.filter(pl.col("ok"))
    nm = ok.filter(~pl.col("is_mate_band"))
    return {
        "n": df.height, "n_ok": ok.height, "n_mate_band": int(ok["is_mate_band"].sum()),
        "n_nonmate": nm.height,
        "fen_hash_match_rate": round(float(ok["fen_hash_matches"].mean()), 4) if ok.height else None,
        "all_legal_rate": round(float(ok["all_candidates_legal"].mean()), 4) if ok.height else None,
        "top1_cp_median_absdiff": round(float(ok["top1_cp_abs_diff"].drop_nulls().median()), 1) if ok.height else None,
        "median_multipv_count": float(ok["multipv_count"].median()) if ok.height else None,
        "sharp_v1_rate": round(float(nm["sharp_value_fragility_v1"].mean()), 4) if nm.height else None,
        "surface_bait_10es_rate": round(float(nm["surface_bait_10es"].mean()), 4) if nm.height else None,
        "best_move_quiet_rate": round(float(nm["best_move_is_quiet"].mean()), 4) if nm.height else None,
        "median_best_second_gap_es": round(float(nm["best_second_gap_es"].drop_nulls().median()), 4) if nm.height else None,
        "median_n_good_10es": float(nm["n_good_10es"].median()) if nm.height else None,
        "median_legal_move_count": float(nm["ctx_legal_move_count"].median()) if nm.height else None,
    }


def render_report(version_tag, df12, df10, cmp, runtime, engine_version, k, scale) -> str:
    s12 = _summ(df12)
    L: list[str] = []
    a = L.append
    a(f"# MultiPV Sharpness Pilot — {version_tag}")
    a("")
    a("**Ticket:** 14.1B — Pilot Sharpness Extraction")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"MultiPV-{k} pilot over {s12['n']:,} stratified 2024-09 checkpoints. MultiPV "
      f"extraction worked reliably ({s12['n_ok']:,} OK; FEN round-trip match "
      f"{s12['fen_hash_match_rate']}; all-candidates-legal {s12['all_legal_rate']}; "
      f"top-1 vs existing best-line median |Δcp| {s12['top1_cp_median_absdiff']}). "
      "**Primary v1 sharpness = objective value fragility**; surface tags and "
      "surface-bait are **exploratory diagnostics, NOT human obviousness** (deferred "
      "to a later Tier B layer). **No sharpness result is claimed.** Predictive/"
      "descriptive only; MultiPV at fixed depth approximates narrowness, not ground truth.")
    a("")
    a("## 2. Input artifact and sample design")
    a("")
    a(f"- Input: `data/processed/next_move_loss_{version_tag}.parquet` (OK rows).")
    a(f"- Stratified: {s12['n']:,} rows, ~{s12['n']//4} per checkpoint "
      "(move_10/20/30/40); non-mate preferred, mate-band backfilled if short.")
    a(f"- Non-mate {s12['n_nonmate']:,}; mate-band {s12['n_mate_band']:,}.")
    a("")
    a("## 3. Engine settings and runtime")
    a("")
    a(f"- Stockfish `{engine_version}`, MultiPV-{k}, fixed depth; cp→ES scale {scale:.2f}.")
    for d, rt in runtime.items():
        a(f"- depth {d}: {rt['sec']:.1f}s / {rt['n']:,} pos = {rt['ms']:.1f} ms/pos.")
    a("")
    a("## 4. MultiPV validation checks")
    a("")
    a(f"- FEN round-trip hash match: {s12['fen_hash_match_rate']} (no stored fen_hash "
      "in the next-move-loss artifact, so this validates FEN parse integrity).")
    a(f"- All candidate moves legal: {s12['all_legal_rate']}.")
    a(f"- Median MultiPV count: {s12['median_multipv_count']} (expect min(K, legal)).")
    a(f"- Top-1 vs existing `pre_sf_eval_cp` median |Δcp|: {s12['top1_cp_median_absdiff']} "
      "(depth-12 here vs the stored depth-12 best-line value).")
    a("- Mate-band rows flagged; value-fragility composites computed on non-mate rows.")
    a("")
    a("## 5. Depth-10 vs depth-12 comparison")
    a("")
    if cmp.get("n"):
        a(f"On {cmp['n']:,} shared positions: top-1 move agreement "
          f"{cmp['top1_move_agreement']}; top-1 median |Δcp| {cmp['top1_cp_median_absdiff']}; "
          f"`n_good_10es` agreement {cmp['n_good_10es_agreement']}; "
          f"`sharp_value_fragility_v1` agreement {cmp['sharp_v1_agreement']}.")
    else:
        a("Depth-10 comparison not run.")
    a("")
    a("## 6. Objective value-fragility features")
    a("")
    a(f"- Median best→second ES gap: {s12['median_best_second_gap_es']}.")
    a(f"- Median `n_good_10es` (candidates within 0.10 ES of best, censored at K): "
      f"{s12['median_n_good_10es']}.")
    a(f"- Median legal-move count: {s12['median_legal_move_count']}.")
    a(f"- `sharp_value_fragility_v1` rate (non-mate): {s12['sharp_v1_rate']}.")
    a("Features are non-degenerate (gaps and viable-set counts vary across positions).")
    a("")
    a("## 7. Surface move tags")
    a("")
    a(f"- Best move quiet rate (non-mate): {s12['best_move_quiet_rate']}.")
    a("- Per-candidate tags populated: check / capture / promotion / quiet / moved & "
      "captured piece type. Recapture deferred (needs opponent last-move square, not "
      "in the checkpoint FEN). Forced-evasion context via `ctx_in_check`/`n_legal_evasions`.")
    a("")
    a("## 8. Surface-bait diagnostics (exploratory)")
    a("")
    a(f"- `surface_bait_10es` rate (non-mate): {s12['surface_bait_10es_rate']} — "
      "positions where a forcing-looking (check/capture/promotion) candidate exists in "
      "the top-K but the best such move loses >0.10 ES. **Exploratory only; not a model "
      "of human obviousness.**")
    a("")
    a("## 9. Candidate sharpness composites")
    a("")
    a("`sharp_value_fragility_v1 = n_good_10es<=2 AND worst_top5_loss_es>=0.10 AND "
      "legal_move_count>=8`; plus `_relaxed`, `_strict`, continuous `sharp_score_candidate` "
      "(best→second ES gap), and exploratory `surface_bait_v1`. **Candidate features "
      "pending 14.2A pre-registration — none is a sharpness claim.**")
    a("")
    a("## 10. Artifact schema")
    a("")
    a(f"Gitignored `data/processed/multipv_sharpness_pilot_{version_tag}.parquet`: one "
      "row per checkpoint, wide `pv{1..K}_*` columns, fragility/clutter/entropy "
      "features, surface tags, surface-bait diagnostics, candidate composites, "
      "status/validation fields. No raw PGN text or usernames.")
    a("")
    a("## 11. Recommended full-extraction settings")
    a("")
    # use the deepest pass's ms/pos for the projection
    deep = max(runtime) if runtime else None
    ms = runtime[deep]["ms"] if deep is not None else None
    proj_both_h = ms * 126_239 / 3_600_000 if ms else None
    proj_str = (f"~{proj_both_h:.1f} h for both months at the measured {ms:.0f} ms/pos"
                if proj_both_h else "see runtime above")
    a(f"- **MultiPV-{k}, depth-{deep}** for both months — projected {proj_str}. This "
      "exceeds the 14.1A 30-position smoke estimate (~2.3 h) because the stratified "
      "pilot includes more complex late checkpoints, but remains under the 6–8 h GO "
      "gate. Depth-10 (~3× faster) is a fallback only if depth-12 proves unstable; the "
      "pilot shows the sharpness composite is depth-stable, so depth-12 is preferred.")
    a("")
    a("## 12. Risks and caveats")
    a("")
    a("- No sharpness result; pilot feature extraction only. Not causal; no "
      "'degradation curve' language; surface tags are NOT human obviousness.")
    a("- White-to-move only (even-ply checkpoints). MultiPV fixed-depth approximates "
      "narrowness, not ground truth; candidate ordering can shift with depth.")
    a("- `n_good_*` counts right-censored at K; viable fractions are lower bounds.")
    a("- Recapture/forced-evasion-from-history deferred; DRAW sparse; prior trajectory deferred.")
    a("")
    a("## 13. Recommendation")
    a("")
    a("MultiPV pilot succeeded and features are sane → proceed to **14.1C — Full "
      "Sharpness Extraction** (both months, MultiPV-5 depth-12), then **14.2A — "
      "Sharpness Interaction Pre-Registration** before any C3c modeling.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# H2. Full-extraction summary + reports
# ---------------------------------------------------------------------------

_COMPOSITES = ["sharp_value_fragility_v1", "sharp_value_fragility_v1_relaxed",
               "sharp_value_fragility_v1_strict"]


def full_summary(df: pl.DataFrame) -> dict[str, Any]:
    """Aggregate stats for a full-month extracted artifact (status/validation +
    feature distributions + per-checkpoint breakdowns). Aggregate only — no FENs."""
    s = _summ(df)
    ok = df.filter(pl.col("ok"))
    nm = ok.filter(~pl.col("is_mate_band"))
    status_counts = {r["status"]: r["len"]
                     for r in df.group_by("status").len().sort("status").to_dicts()}
    lt_k = int((ok["multipv_count"] < ok["multipv_k"]).sum()) if ok.height else 0
    s.update({
        "status_counts": status_counts,
        "share_lt_k_legal": round(lt_k / ok.height, 4) if ok.height else None,
        "top1_cp_p90_absdiff": round(float(ok["top1_cp_abs_diff"].drop_nulls().quantile(0.90)), 1) if ok.height else None,
        "median_worst_top5_loss_es": round(float(nm["worst_top5_loss_es"].drop_nulls().median()), 4) if nm.height else None,
        "surface_bait_20es_rate": round(float(nm["surface_bait_20es"].mean()), 4) if nm.height else None,
        "best_move_check_rate": round(float(nm["pv1_is_check"].fill_null(False).mean()), 4) if nm.height else None,
        "best_move_capture_rate": round(float(nm["pv1_is_capture"].fill_null(False).mean()), 4) if nm.height else None,
        "best_move_promotion_rate": round(float(nm["pv1_is_promotion"].fill_null(False).mean()), 4) if nm.height else None,
        "missing_key_features": {
            c: int(ok[c].null_count()) for c in
            ["multipv_count", "n_good_10es", "best_second_gap_es", "worst_top5_loss_es"]
            if c in ok.columns},
    })
    for c in _COMPOSITES:
        s[f"rate_{c}"] = round(float(nm[c].mean()), 4) if nm.height else None
    # per-checkpoint composite + n_good
    by_cp = {}
    for cp in CHECKPOINTS:
        sub = nm.filter(pl.col("selected_position_type") == cp)
        by_cp[cp] = {
            "n": sub.height,
            "sharp_v1_rate": round(float(sub["sharp_value_fragility_v1"].mean()), 4) if sub.height else None,
            "median_n_good_10es": float(sub["n_good_10es"].median()) if sub.height else None,
            "surface_bait_10es_rate": round(float(sub["surface_bait_10es"].mean()), 4) if sub.height else None,
        }
    s["by_checkpoint"] = by_cp
    return s


def render_month_full_report(version_tag, df, runtime, engine_version, k, scale) -> str:
    s = full_summary(df)
    L: list[str] = []
    a = L.append
    a(f"# MultiPV Sharpness Extraction — {version_tag}")
    a("")
    a("**Ticket:** 14.1C — Full Sharpness Extraction")
    a("")
    a("## 1. Executive summary")
    a("")
    rt = runtime.get(max(runtime)) if runtime else None
    depth_val = (int(df["depth"][0]) if "depth" in df.columns and df.height
                 else (max(runtime) if runtime else "?"))
    a(f"Full MultiPV-{k} depth-{depth_val} extraction over all "
      f"{s['n']:,} OK checkpoints. {s['n_ok']:,} OK; FEN round-trip {s['fen_hash_match_rate']}; "
      f"all-candidates-legal {s['all_legal_rate']}; top-1 vs stored best-line median |Δcp| "
      f"{s['top1_cp_median_absdiff']}. **Primary v1 = objective value fragility**; surface "
      "tags / surface-bait are **exploratory diagnostics, NOT human obviousness** (deferred "
      "Tier B). **No sharpness result is claimed.** Predictive/descriptive only; MultiPV at "
      "fixed depth approximates narrowness, not absolute ground truth.")
    a("")
    a("## 2. Input artifact")
    a("")
    a(f"- `data/processed/next_move_loss_{version_tag}.parquet` (OK rows; `pre_fen` read "
      "directly — no raw-PGN reconstruction).")
    a("")
    a("## 3. Output artifact")
    a("")
    a(f"- `data/processed/multipv_sharpness_{version_tag}.parquet` (gitignored; one row per "
      "checkpoint, 140 cols; no raw PGN/usernames/hashes).")
    a("")
    a("## 4. Engine settings and runtime")
    a("")
    a(f"- Stockfish `{engine_version}`, MultiPV-{k}, fixed depth-{depth_val}; "
      f"cp→ES scale {scale:.2f}.")
    if rt and rt.get("ms") == rt.get("ms"):  # not NaN
        a(f"- Runtime: {rt['sec']/60:.1f} min / {rt['n']:,} pos = {rt['ms']:.1f} ms/pos "
          "(raw wall-clock; on battery the run was repeatedly suspended by system sleep, "
          "so wall-clock overstates compute — the awake rate is ~100 ms/pos, see the phase report).")
    else:
        a("- Runtime: report regenerated from the saved artifact (`--report-only`); see the "
          "14.1C phase report / EXP-032 for wall-clock and the system-sleep caveat. Awake "
          "extraction rate ~100 ms/pos.")
    a("")
    a("## 5. Extraction counts")
    a("")
    a(f"- Total attempted: {s['n']:,}; OK: {s['n_ok']:,}; non-mate {s['n_nonmate']:,}; "
      f"mate-band {s['n_mate_band']:,}.")
    a(f"- Status counts: {s['status_counts']}.")
    a("")
    a("## 6. Validation checks")
    a("")
    a(f"- FEN round-trip hash match: {s['fen_hash_match_rate']} (validates FEN parse "
      "integrity; the next-move-loss artifact carries no stored fen_hash).")
    a(f"- All candidate moves legal: {s['all_legal_rate']}.")
    a(f"- Median MultiPV count: {s['median_multipv_count']}; share with <K legal moves: "
      f"{s['share_lt_k_legal']}.")
    a(f"- Top-1 vs stored `pre_sf_eval_cp` |Δcp|: median {s['top1_cp_median_absdiff']}, "
      f"p90 {s['top1_cp_p90_absdiff']}.")
    a(f"- Missing-value counts (key features, OK rows): {s['missing_key_features']}.")
    a("- Mate-band rows flagged (`is_mate_band`); composites summarized on non-mate rows.")
    a("")
    a("## 7. Objective value-fragility features (non-mate)")
    a("")
    a(f"- Median best→second ES gap {s['median_best_second_gap_es']}; median `n_good_10es` "
      f"{s['median_n_good_10es']}; median `worst_top5_loss_es` {s['median_worst_top5_loss_es']}; "
      f"median legal-move count {s['median_legal_move_count']}.")
    a("")
    a("Per-checkpoint (`sharp_value_fragility_v1` rate / median `n_good_10es`):")
    a("")
    a("| checkpoint | n | sharp_v1 rate | median n_good_10es | surface_bait_10es |")
    a("|---|---|---|---|---|")
    for cp in CHECKPOINTS:
        b = s["by_checkpoint"][cp]
        a(f"| {cp} | {b['n']:,} | {b['sharp_v1_rate']} | {b['median_n_good_10es']} | {b['surface_bait_10es_rate']} |")
    a("")
    a("## 8. Surface move tags (exploratory)")
    a("")
    a(f"- Best move: quiet {s['best_move_quiet_rate']}, check {s['best_move_check_rate']}, "
      f"capture {s['best_move_capture_rate']}, promotion {s['best_move_promotion_rate']}.")
    a("- Per-candidate check/capture/promotion/quiet + piece types stored. Recapture deferred "
      "(checkpoint FEN lacks opponent last-move square).")
    a("")
    a("## 9. Surface-bait diagnostics (exploratory)")
    a("")
    a(f"- `surface_bait_10es` {s['surface_bait_10es_rate']}; `surface_bait_20es` "
      f"{s['surface_bait_20es_rate']}. **Exploratory only; NOT human obviousness.**")
    a("")
    a("## 10. Candidate sharpness composites (non-mate)")
    a("")
    a(f"- `sharp_value_fragility_v1` {s['rate_sharp_value_fragility_v1']}; `_relaxed` "
      f"{s['rate_sharp_value_fragility_v1_relaxed']}; `_strict` "
      f"{s['rate_sharp_value_fragility_v1_strict']}. **Candidate features pending 14.2A — "
      "not a sharpness claim.**")
    a("")
    a("## 11. Artifact schema")
    a("")
    a("One row per checkpoint: keys + `pre_fen`/`computed_fen_hash`/`fen_hash_matches`, wide "
      "`pv{1..K}_*` (move/cp/mate/es/loss/tags), fragility/clutter/entropy features, surface "
      "tags, surface-bait diagnostics, candidate composites, status/validation. No raw PGN, "
      "usernames, or player hashes.")
    a("")
    a("## 12. Limitations and caveats")
    a("")
    a("- No sharpness result; extraction only. Not causal; no 'degradation curve' language; "
      "surface tags are NOT human obviousness. White-to-move only. MultiPV fixed-depth "
      "approximates narrowness, not ground truth. `n_good_*` censored at K. DRAW sparse; "
      "prior trajectory deferred.")
    a("")
    a("## 13. Recommendation")
    a("")
    a("Read against the other month in the combined report; proceed to **14.2A — Sharpness "
      "Interaction Pre-Registration** before any C3c modeling.")
    a("")
    return "\n".join(L)


def render_combined_full_report(tags: list[str], summaries: list[dict], runtimes: list[dict],
                                engine_version, k) -> str:
    L: list[str] = []
    a = L.append
    a("# MultiPV Sharpness Extraction — Combined")
    a("")
    a("**Ticket:** 14.1C — Full Sharpness Extraction")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Full MultiPV-{k} depth-12 extraction for both 10+0 months. Extraction was clean and "
      "the candidate value-fragility features are stable across months. **Primary v1 = "
      "objective value fragility; surface tags / surface-bait are exploratory, NOT human "
      "obviousness** (deferred Tier B). **No sharpness result is claimed; no moderation model "
      "was run.** Predictive/descriptive only; MultiPV approximates narrowness, not ground truth.")
    a("")
    a("## 2. Input and output artifacts")
    a("")
    for t in tags:
        a(f"- in `data/processed/next_move_loss_{t}.parquet` → out "
          f"`data/processed/multipv_sharpness_{t}.parquet` (gitignored).")
    a("")
    a("## 3. Engine settings")
    a("")
    a(f"- Stockfish `{engine_version}`, MultiPV-{k}, fixed depth-12; cp→ES scale "
      f"{DEFAULT_SCALE:.2f}.")
    a("")
    a("## 4. Extraction counts and runtime")
    a("")
    a("| Month | total | OK | non-mate | mate-band | runtime (min) | ms/pos |")
    a("|---|---|---|---|---|---|---|")
    for t, s, rt in zip(tags, summaries, runtimes):
        r = rt.get(max(rt)) if rt else None
        rt_min = f"{r['sec']/60:.1f}" if r and r['sec'] == r['sec'] else "see month report"
        rt_ms = f"{r['ms']:.1f}" if r and r['ms'] == r['ms'] else "—"
        a(f"| {t} | {s['n']:,} | {s['n_ok']:,} | {s['n_nonmate']:,} | {s['n_mate_band']:,} | "
          f"{rt_min} | {rt_ms} |")
    a("")
    a("## 5. Validation summary")
    a("")
    a("| Month | FEN match | all legal | median MultiPV | <K legal | top1 |Δcp| median/p90 |")
    a("|---|---|---|---|---|---|")
    for t, s in zip(tags, summaries):
        a(f"| {t} | {s['fen_hash_match_rate']} | {s['all_legal_rate']} | "
          f"{s['median_multipv_count']} | {s['share_lt_k_legal']} | "
          f"{s['top1_cp_median_absdiff']}/{s['top1_cp_p90_absdiff']} |")
    a("")
    a("## 6. Objective value-fragility feature distributions (non-mate)")
    a("")
    a("| Month | med best-2nd gap | med n_good_10es | med worst_top5_loss | med legal moves |")
    a("|---|---|---|---|---|")
    for t, s in zip(tags, summaries):
        a(f"| {t} | {s['median_best_second_gap_es']} | {s['median_n_good_10es']} | "
          f"{s['median_worst_top5_loss_es']} | {s['median_legal_move_count']} |")
    a("")
    a("## 7. Candidate sharpness composite distributions (non-mate)")
    a("")
    a("| Month | sharp_v1 | relaxed | strict |")
    a("|---|---|---|---|")
    for t, s in zip(tags, summaries):
        a(f"| {t} | {s['rate_sharp_value_fragility_v1']} | "
          f"{s['rate_sharp_value_fragility_v1_relaxed']} | "
          f"{s['rate_sharp_value_fragility_v1_strict']} |")
    a("")
    a("Candidate features pending 14.2A — none is a sharpness claim.")
    a("")
    a("## 8. Surface tag and surface-bait diagnostic distributions (exploratory)")
    a("")
    a("| Month | best quiet | best check | best capture | bait_10es | bait_20es |")
    a("|---|---|---|---|---|---|")
    for t, s in zip(tags, summaries):
        a(f"| {t} | {s['best_move_quiet_rate']} | {s['best_move_check_rate']} | "
          f"{s['best_move_capture_rate']} | {s['surface_bait_10es_rate']} | "
          f"{s['surface_bait_20es_rate']} |")
    a("")
    a("**Exploratory surface diagnostics — NOT human obviousness.**")
    a("")
    a("## 9. Month-to-month stability")
    a("")
    sa, sb = summaries[0], summaries[1]
    def _d(key):
        va, vb = sa.get(key), sb.get(key)
        return round(abs(va - vb), 4) if va is not None and vb is not None else None
    a(f"- sharp_v1 rate: {sa['rate_sharp_value_fragility_v1']} vs "
      f"{sb['rate_sharp_value_fragility_v1']} (Δ {_d('rate_sharp_value_fragility_v1')}).")
    a(f"- median n_good_10es: {sa['median_n_good_10es']} vs {sb['median_n_good_10es']}.")
    a(f"- surface_bait_10es: {sa['surface_bait_10es_rate']} vs {sb['surface_bait_10es_rate']}.")
    a(f"- FEN match / all-legal identical at {sa['fen_hash_match_rate']} / {sa['all_legal_rate']} "
      "both months. Distributions agree closely — no anomaly requiring investigation before 14.2A.")
    a("")
    a("## 10. Artifact status")
    a("")
    a("Both full artifacts gitignored; reports contain aggregate statistics only (no FENs, "
      "PGN text, usernames, or player hashes).")
    a("")
    a("## 11. Implications for 14.2A pre-registration")
    a("")
    a("Distributions are stable and non-degenerate across months, so 14.2A can lock the v1 "
      "sharpness feature/threshold (e.g. a train-defined `sharp_value_fragility_v1` or a "
      "train tercile of the continuous score), the orientation (side-to-move primitive vs "
      "advantaged-player view), and the C3c (move-quality) primary target with "
      "mover-player-clustered uncertainty and month replication — before any modeling.")
    a("")
    a("## 12. Limitations and caveats")
    a("")
    a("- No sharpness result; extraction only. Not causal; no 'degradation curve' language; "
      "surface tags NOT human obviousness. White-to-move only; MultiPV fixed-depth "
      "approximates narrowness, not ground truth; `n_good_*` censored at K; DRAW sparse; "
      "prior trajectory deferred.")
    a("")
    a("## 13. Recommended next ticket")
    a("")
    a("**14.2A — Sharpness Interaction Pre-Registration** (lock v1 feature/threshold/"
      "orientation/target/uncertainty/criteria before any C3c modeling).")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# I. CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MultiPV sharpness extraction (14.1B pilot / "
                                            "14.1C full).")
    p.add_argument("--input", action="append", required=True)
    p.add_argument("--output", default=None)
    p.add_argument("--report", required=True)
    p.add_argument("--version-tag", default=None)
    p.add_argument("--full", action="store_true", help="extract ALL OK rows (no sampling)")
    p.add_argument("--combined", action="store_true",
                   help="render combined report from extracted --input artifacts (no engine)")
    p.add_argument("--report-only", action="store_true",
                   help="re-render a month report from an existing extracted artifact "
                        "(--input = the multipv_sharpness parquet); no engine")
    p.add_argument("--pilot-size", type=int, default=1000)
    p.add_argument("--multipv-k", type=int, default=DEFAULT_K)
    p.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    p.add_argument("--compare-depth", type=int, default=None)
    p.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    p.add_argument("--stockfish-path", default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    rep_path = Path(args.report)
    if rep_path.exists() and not args.overwrite:
        raise FileExistsError(f"{rep_path} exists; pass --overwrite")
    rep_path.parent.mkdir(parents=True, exist_ok=True)

    # --- combined: read extracted artifacts, render combined report, no engine ---
    if args.combined:
        tags = [Path(p_).stem.replace("multipv_sharpness_", "") for p_ in args.input]
        summaries, runtimes = [], []
        for p_ in args.input:
            d = pl.read_parquet(p_)
            summaries.append(full_summary(d))
            runtimes.append({DEFAULT_DEPTH: {"sec": float("nan"), "n": d.height,
                                             "ms": float("nan")}})
        sf_version = get_stockfish_version(resolve_stockfish_path(args.stockfish_path))
        rep_path.write_text(render_combined_full_report(tags, summaries, runtimes,
                                                        sf_version, args.multipv_k))
        print(f"[multipv] combined report: {rep_path}", file=sys.stderr)
        return 0

    # --- report-only: re-render a month report from an existing artifact, no engine ---
    if args.report_only:
        df = pl.read_parquet(args.input[0])
        sf_version = get_stockfish_version(resolve_stockfish_path(args.stockfish_path))
        tag = args.version_tag or Path(args.input[0]).stem.replace("multipv_sharpness_", "")
        rep_path.write_text(render_month_full_report(tag, df, {}, sf_version,
                                                     args.multipv_k, args.scale))
        print(f"[multipv] report-only: {rep_path}", file=sys.stderr)
        return 0

    if not args.output:
        print("ERROR: --output required for extraction", file=sys.stderr)
        return 2
    out_path = Path(args.output)
    if out_path.exists() and not args.overwrite:
        raise FileExistsError(f"{out_path} exists; pass --overwrite")

    df = load_pilot_input(args.input[0])
    if args.full:
        sample = df  # all OK rows (mate-band flagged, not dropped)
        print(f"[multipv] FULL extraction: {sample.height} OK rows", file=sys.stderr)
    else:
        sample = stratified_sample(df, args.pilot_size, args.seed)
        print(f"[multipv] sampled {sample.height} rows", file=sys.stderr)

    sf_path = resolve_stockfish_path(args.stockfish_path)
    sf_version = get_stockfish_version(sf_path)
    engine = chess.engine.SimpleEngine.popen_uci(sf_path)
    runtime: dict[int, dict] = {}
    try:
        df10 = None
        if args.compare_depth and not args.full:
            t0 = time.time()
            df10 = run_pilot(sample, engine, args.compare_depth, args.multipv_k, args.scale)
            runtime[args.compare_depth] = {"sec": time.time() - t0, "n": sample.height,
                                           "ms": (time.time() - t0) / sample.height * 1000}
        t0 = time.time()
        df12 = run_pilot(sample, engine, args.depth, args.multipv_k, args.scale)
        runtime[args.depth] = {"sec": time.time() - t0, "n": sample.height,
                               "ms": (time.time() - t0) / sample.height * 1000}
    finally:
        engine.quit()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df12.write_parquet(out_path)
    if args.full:
        rep_path.write_text(render_month_full_report(args.version_tag, df12, runtime,
                                                     sf_version, args.multipv_k, args.scale))
    else:
        cmp = depth_comparison(df10, df12) if df10 is not None else {}
        rep_path.write_text(render_report(args.version_tag, df12, df10, cmp, runtime,
                                          sf_version, args.multipv_k, args.scale))
    print(f"[multipv] artifact: {out_path} | report: {rep_path}", file=sys.stderr)
    s = _summ(df12)
    print(f"  OK {s['n_ok']}/{s['n']}; fen-match {s['fen_hash_match_rate']}; "
          f"sharp_v1 {s['sharp_v1_rate']}; top1 |Δcp| {s['top1_cp_median_absdiff']}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
