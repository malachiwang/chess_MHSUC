"""
Termination decomposition — Ticket 11.2B (locked Contrast C2).

Tests whether the replicated E3->E4 clock residual survives removal of
timeout/time-forfeit games, or is mostly mechanical flagging/timeout risk.

PRIMARY DESIGN (per PREREGISTRATION.md C2, clarified pre-implementation):
prediction-side filtering of the FROZEN all-games E3/E4 models' saved
validation predictions by termination channel. NO retraining.

Channels (from the 11.2A audit; clean 600+0 data contains only
Normal / Time forfeit / Rules infraction — Abandoned is excluded by cleaning):
  - time_forfeit               (Termination == "Time forfeit")
  - normal_decisive            (Normal, decisive result — checkmate OR
                                resignation; NOT separable from headers)
  - normal_draw                (Normal, DRAW result)
  - rules_infraction_or_other  (anything else; ~1 game/month)
Binary: board_decided = NOT time_forfeit.

Reuses the proven machinery: predictions loader and within-cell paired
bootstrap from constraint_slices.py; join key (game_id,
selected_position_type) throughout. All results are predictive associations;
filtering time-forfeit games induces selection (board-decided low-clock games
are a survivor population) and does not create a causal design.

CLI (paths default from --version-tag; overrides available):
    PYTHONPATH=src python -m chess_mhsuc.termination_decomposition \\
        --dataset-id lichess_ten_zero_2024_09_250k_v1 \\
        --version-tag 2024_09_250k_v1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import polars as pl

from chess_mhsuc.constraint_slices import (
    MODEL_A,  # "E3"
    MODEL_B,  # "E4"
    compute_cell_result,
    load_e3_e4_val_predictions,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROB_COLS = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]
_JOIN_KEY = ["game_id", "selected_position_type"]

CHANNEL_ORDER = [
    "time_forfeit", "normal_decisive", "normal_draw", "rules_infraction_or_other",
]
LATE_CHECKPOINTS = ["move_30", "move_40"]
LATE_CLOCK_ORDER = ["under_60s", "60_180s", "over_180s"]

DEFAULT_MIN_GAMES_FOR_CI = 300
# Guard for retained-fraction denominators (log-loss delta units)
_NEAR_ZERO_DELTA = 1e-3


# ---------------------------------------------------------------------------
# A. classify_channel (pure; unit-tested)
# ---------------------------------------------------------------------------

def classify_channel(termination: str, result_class: str) -> str:
    """
    Map (Termination header value, result_class) to a descriptive channel.

    'Normal' mixes checkmate and resignation — they are NOT separable from
    PGN headers, so both map to normal_decisive. Draws within Normal are
    separable via the result.
    """
    if termination == "Time forfeit":
        return "time_forfeit"
    if termination == "Normal":
        return "normal_draw" if result_class == "DRAW" else "normal_decisive"
    return "rules_infraction_or_other"


def is_board_decided(termination: str) -> bool:
    """Binary channel: every clean-set termination except time forfeit."""
    return termination != "Time forfeit"


# ---------------------------------------------------------------------------
# B. load_termination_keys
# ---------------------------------------------------------------------------

def load_termination_keys(features_path: str | Path) -> pl.DataFrame:
    """
    Build the per-position termination/slice-key table from the processed
    feature table (primary view). Columns: join key, termination,
    is_time_forfeit, channel, board_decided, late_clock_bucket.
    """
    f = pl.read_parquet(features_path)
    prim = f.filter(pl.col("selected_position_type") != "last")
    if prim.select(_JOIN_KEY).n_unique() != len(prim):
        raise ValueError("(game_id, selected_position_type) not unique in feature table")
    if prim["termination"].null_count() > 0:
        raise ValueError("null termination values in feature table")

    min_clock = pl.min_horizontal("white_clock_s_capped", "black_clock_s_capped")
    return prim.with_columns([
        pl.struct(["termination", "result_class"]).map_elements(
            lambda s: classify_channel(s["termination"], s["result_class"]),
            return_dtype=pl.Utf8,
        ).alias("channel"),
        (~pl.col("is_time_forfeit")).alias("board_decided"),
        pl.when(~pl.col("selected_position_type").is_in(LATE_CHECKPOINTS))
        .then(pl.lit(None))
        .when(min_clock < 60).then(pl.lit("under_60s"))
        .when(min_clock < 180).then(pl.lit("60_180s"))
        .otherwise(pl.lit("over_180s"))
        .alias("late_clock_bucket"),
    ]).select(
        _JOIN_KEY + ["termination", "is_time_forfeit", "channel",
                     "board_decided", "late_clock_bucket"]
    )


# ---------------------------------------------------------------------------
# C. attach_and_validate
# ---------------------------------------------------------------------------

def attach_and_validate(
    val_preds: pl.DataFrame,
    keys: pl.DataFrame,
) -> pl.DataFrame:
    """
    Join termination keys onto E3/E4 validation predictions.

    Validates: unique keys on the keys side; joined row count equals the
    prediction row count; no missing termination after the join.
    """
    if keys.select(_JOIN_KEY).n_unique() != len(keys):
        raise ValueError("duplicate (game_id, selected_position_type) in keys table")

    joined = val_preds.join(keys, on=_JOIN_KEY, how="left")
    if len(joined) != len(val_preds):
        raise ValueError(
            f"join changed row count: {len(val_preds)} -> {len(joined)}"
        )
    n_missing = joined["termination"].null_count()
    if n_missing > 0:
        raise ValueError(f"{n_missing} prediction rows have no termination after join")
    if joined["is_time_forfeit"].dtype != pl.Boolean:
        joined = joined.with_columns(pl.col("is_time_forfeit").cast(pl.Boolean))
    return joined


# ---------------------------------------------------------------------------
# D. retained_fraction (pure; unit-tested)
# ---------------------------------------------------------------------------

def retained_fraction(
    board_decided_delta: float,
    all_games_delta: float,
    near_zero: float = _NEAR_ZERO_DELTA,
) -> dict[str, Any]:
    """
    |board_decided_delta| / |all_games_delta|, with a near-zero-denominator
    guard: if the all-games delta is within `near_zero` of 0, the fraction is
    not meaningful and is reported as None with a note.
    """
    if abs(all_games_delta) < near_zero:
        return {
            "fraction": None,
            "sign_flipped": None,
            "note": (
                "all-games delta is near zero; retained fraction not meaningful"
            ),
        }
    sign_flipped = (
        board_decided_delta * all_games_delta < 0
        and abs(board_decided_delta) >= near_zero
    )
    return {
        "fraction": abs(board_decided_delta) / abs(all_games_delta),
        "sign_flipped": sign_flipped,
        "note": (
            "board-decided delta has the OPPOSITE sign to the all-games delta; "
            "the magnitude-based fraction overstates retention"
            if sign_flipped else None
        ),
    }


# ---------------------------------------------------------------------------
# E. compute_group_results
# ---------------------------------------------------------------------------

def compute_group_results(
    preds_with_keys: pl.DataFrame,
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict[str, dict]:
    """
    Paired E3->E4 deltas (with CIs where >= min_games_for_ci) for:
    all rows, board_decided, time_forfeit, and each descriptive channel
    with nonzero rows.
    """
    out: dict[str, dict] = {}
    groups: list[tuple[str, pl.DataFrame]] = [
        ("all_games", preds_with_keys),
        ("board_decided", preds_with_keys.filter(pl.col("board_decided"))),
        ("time_forfeit", preds_with_keys.filter(pl.col("is_time_forfeit"))),
    ]
    for ch in CHANNEL_ORDER:
        sub = preds_with_keys.filter(pl.col("channel") == ch)
        if len(sub) > 0 and ch != "time_forfeit":  # TF already covered
            groups.append((f"channel_{ch}", sub))

    for name, df in groups:
        if len(df) == 0:
            out[name] = {"n_rows": 0, "n_games": 0, "note": "empty group"}
            continue
        print(f"    [{name}] {len(df) // 2:,} rows/model...", file=sys.stderr)
        out[name] = compute_cell_result(
            df, n_replicates=n_replicates, seed=seed,
            min_games_for_ci=min_games_for_ci,
        )
    return out


# ---------------------------------------------------------------------------
# F. compute_late_clock_results
# ---------------------------------------------------------------------------

def compute_late_clock_results(
    preds_with_keys: pl.DataFrame,
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict[str, dict[str, dict]]:
    """
    Late-checkpoint (move_30+move_40) min-clock bucket deltas, all-games vs
    board-decided-only. Sub-threshold cells (notably board-decided under_60s)
    follow the descriptive/no-CI convention.
    """
    out: dict[str, dict[str, dict]] = {}
    for label, df in [
        ("all_games", preds_with_keys),
        ("board_decided", preds_with_keys.filter(pl.col("board_decided"))),
    ]:
        out[label] = {}
        for bucket in LATE_CLOCK_ORDER:
            sub = df.filter(pl.col("late_clock_bucket") == bucket)
            if len(sub) == 0:
                out[label][bucket] = {"n_rows": 0, "n_games": 0, "note": "empty group"}
                continue
            print(f"    [late {label}/{bucket}] {len(sub) // 2:,} rows/model...",
                  file=sys.stderr)
            out[label][bucket] = compute_cell_result(
                sub, n_replicates=n_replicates, seed=seed,
                min_games_for_ci=min_games_for_ci,
            )
    return out


# ---------------------------------------------------------------------------
# G. composition tables
# ---------------------------------------------------------------------------

def composition_tables(
    keys: pl.DataFrame,
    preds_with_keys: pl.DataFrame,
    sf_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Termination composition: dataset-wide primary view, val predictions,
    by checkpoint, late group, late-clock bucket, and by split if the
    sf artifact is supplied.
    """
    def _counts(df: pl.DataFrame, who: str) -> dict:
        g = df.group_by(who).agg(
            [pl.len().alias("rows"), pl.col("game_id").n_unique().alias("games")]
        ).sort(who)
        return {r[0]: {"rows": r[1], "games": r[2]} for r in g.iter_rows()}

    one_model = preds_with_keys.filter(pl.col("model_id") == MODEL_A)
    out: dict[str, Any] = {
        "dataset_primary_by_channel": _counts(keys, "channel"),
        "val_by_channel": _counts(one_model, "channel"),
        "val_by_checkpoint_tf": {
            cpt: _counts(
                one_model.filter(pl.col("selected_position_type") == cpt),
                "board_decided",
            )
            for cpt in sorted(one_model["selected_position_type"].unique().to_list())
        },
        "val_late_clock_tf": {
            b: _counts(
                one_model.filter(pl.col("late_clock_bucket") == b), "board_decided"
            )
            for b in LATE_CLOCK_ORDER
        },
    }
    if sf_path is not None and Path(sf_path).exists():
        sf = pl.read_parquet(sf_path).select(_JOIN_KEY + ["split_set"])
        with_split = keys.join(sf, on=_JOIN_KEY, how="left")
        out["dataset_by_split_tf"] = {
            s: _counts(
                with_split.filter(pl.col("split_set") == s), "board_decided"
            )
            for s in ("train", "val", "test")
        }
    return out


# ---------------------------------------------------------------------------
# H. render_report
# ---------------------------------------------------------------------------

def _fmt(x: float | None, nd: int = 4) -> str:
    return "—" if x is None else f"{x:.{nd}f}"


def _row(name: str, r: dict) -> str:
    if r.get("note") == "empty group":
        return f"| {name} | 0 | 0 | — | — | — | — | — | empty |"
    ci = (f"[{_fmt(r['ci_lower'])}, {_fmt(r['ci_upper'])}]"
          if r.get("ci_lower") is not None else "N/A")
    cz = (("Yes" if r["contains_zero"] else "No")
          if r.get("contains_zero") is not None else "—")
    return (f"| {name} | {r['n_rows']:,} | {r['n_games']:,} | "
            f"{_fmt(r['log_loss_e3'])} | {_fmt(r['log_loss_e4'])} | "
            f"{_fmt(r['point_delta'])} | {ci} | {cz} | {r.get('note') or ''} |")


_HDR = ("| Group | Rows | Games | E3 ll | E4 ll | Delta | 95% CI | "
        "CI contains zero | Note |\n|---|---|---|---|---|---|---|---|---|")


def render_report(payload: dict) -> str:
    """Deterministic month report (no timestamps in body)."""
    g = payload["group_results"]
    lc = payload["late_clock_results"]
    comp = payload["composition"]
    rf = payload["retained_fraction"]
    lines: list[str] = []
    a = lines.append

    a(f"# Termination Decomposition — {payload['version_tag']}")
    a("")
    a("**Ticket:** 11.2B — Termination Decomposition Implementation (locked Contrast C2)")
    a(f"**Dataset:** `{payload['dataset_id']}`")
    a("")
    a("---")
    a("")

    a("## 1. Executive summary")
    a("")
    all_d = g["all_games"]["point_delta"]
    bd = g["board_decided"]
    frac_s = (f"{100 * rf['fraction']:.0f}%" if rf["fraction"] is not None
              else "not meaningful (near-zero denominator)")
    cz = ("excludes zero" if bd.get("contains_zero") is False
          else "contains zero" if bd.get("contains_zero") else "no CI")
    a(f"All-games E3→E4 validation delta: {_fmt(all_d)}. Board-decided-only delta "
      f"(frozen models, prediction-side filter, no retraining): "
      f"{_fmt(bd['point_delta'])} ({cz}); retained fraction {frac_s}. "
      "Interpretation in Section 9. Predictive associations only — filtering "
      "time-forfeit games induces selection and does not create a causal design.")
    a("")

    a("## 2. Dataset and artifacts")
    a("")
    p = payload["artifact_paths"]
    a(f"- Predictions (frozen E3/E4, all-games-trained): `{p['predictions']}`")
    a(f"- Termination keys: `{p['features']}` (primary view; join on "
      "`(game_id, selected_position_type)`)")
    a(f"- Bootstrap: {payload['n_replicates']} replicates, seed={payload['seed']}, "
      f"game-level clusters; CI threshold {payload['min_games_for_ci']} games.")
    a("")

    a("## 3. Termination composition")
    a("")
    a("Dataset primary view, by descriptive channel (rows/games):")
    a("")
    for ch, c in comp["dataset_primary_by_channel"].items():
        a(f"- {ch}: {c['rows']:,} rows / {c['games']:,} games")
    a("")
    a("Validation rows by checkpoint (board_decided True/False games):")
    a("")
    for cpt, d in comp["val_by_checkpoint_tf"].items():
        parts = [f"{('board-decided' if k else 'time-forfeit')}: "
                 f"{v['rows']:,}r/{v['games']:,}g" for k, v in d.items()]
        a(f"- {cpt}: " + "; ".join(parts))
    a("")
    a("Late-checkpoint validation rows by min-clock bucket "
      "(board-decided vs time-forfeit):")
    a("")
    for b, d in comp["val_late_clock_tf"].items():
        parts = [f"{('board-decided' if k else 'time-forfeit')}: "
                 f"{v['rows']:,}r/{v['games']:,}g" for k, v in d.items()]
        a(f"- {b}: " + ("; ".join(parts) if parts else "empty"))
    a("")
    if "dataset_by_split_tf" in comp:
        a("Dataset by split (board-decided True/False games):")
        a("")
        for s, d in comp["dataset_by_split_tf"].items():
            parts = [f"{('board-decided' if k else 'time-forfeit')}: "
                     f"{v['rows']:,}r/{v['games']:,}g" for k, v in d.items()]
            a(f"- {s}: " + "; ".join(parts))
        a("")

    a("## 4. Join validation")
    a("")
    jv = payload["join_summary"]
    a(f"- Prediction validation rows per model: {jv['n_val_rows_per_model']:,}; "
      f"joined rows equal prediction rows: yes; missing termination after join: 0; "
      f"keys unique on both sides: yes.")
    a("")

    a("## 5. Overall E3→E4 decomposition")
    a("")
    a(_HDR)
    for name in ("all_games", "board_decided", "time_forfeit"):
        a(_row(name, g[name]))
    for name in sorted(k for k in g if k.startswith("channel_")):
        a(_row(name, g[name]))
    a("")
    a("Delta = log_loss(E4) − log_loss(E3); negative = clock features improved. "
      "`normal_decisive` mixes checkmate and resignation (not separable from PGN "
      "headers); channel rows beyond the binary split are descriptive.")
    a("")

    a("## 6. Board-decided-only E3→E4 result")
    a("")
    a(_row("board_decided", bd))
    a("")

    a("## 7. Time-forfeit-only result")
    a("")
    a(_row("time_forfeit", g["time_forfeit"]))
    a("")
    a("Time-forfeit games are where the mechanical flagging channel lives; a large "
      "delta here is expected and does not by itself say anything about "
      "board-decided play.")
    a("")

    a("## 8. Late-checkpoint / late-clock localization")
    a("")
    a("Move_30+move_40 only, by min-clock bucket; all-games vs board-decided "
      "(prediction-side filter):")
    a("")
    a(_HDR)
    for label in ("all_games", "board_decided"):
        for bucket in LATE_CLOCK_ORDER:
            a(_row(f"{label} / {bucket}", lc[label][bucket]))
    a("")
    a("Board-decided under_60s cells are expected to be descriptive-only "
      "(sample-size collapse; see Section 10). Board-decided low-clock games are a "
      "selected survivor population (players who navigated time pressure without "
      "flagging).")
    a("")

    a("## 9. Retained-fraction interpretation")
    a("")
    if rf["fraction"] is not None:
        a(f"Retained fraction |board_decided| / |all_games| = "
          f"{rf['fraction']:.2f} ({100 * rf['fraction']:.0f}%)."
          + (f" **Caution: {rf['note']}.**" if rf.get("note") else ""))
        a("")
        bd_delta = bd.get("point_delta", 0)
        if (bd_delta < 0 and bd.get("contains_zero") is False
                and rf["fraction"] >= 0.5 and not rf.get("sign_flipped")):
            a("The board-decided delta retains a meaningful share of the all-games "
              "magnitude, in the same direction, with a CI excluding zero: the "
              "clock residual is **not merely timeout/flagging** in this month. "
              "(Predictive claim only.)")
        elif bd_delta < 0 and bd.get("contains_zero") is False:
            a("The board-decided delta shrinks but remains negative with a CI "
              "excluding zero: part of the signal is timeout-related, and a "
              "board-decided residual remains. (Predictive claim only.)")
        elif bd_delta < 0:
            a("The board-decided delta is directionally negative but its CI "
              "contains zero: part of the signal is timeout-related and the "
              "board-decided residual is not separately resolvable in this month.")
        else:
            a("The board-decided delta collapses (zero or sign-reversed): the "
              "clock residual in this month is substantially explained by the "
              "termination channel; the central claim must be re-framed honestly "
              "toward the flagging channel.")
    else:
        a(f"Retained fraction: {rf['note']}.")
    a("")

    a("## 10. Risks and caveats")
    a("")
    a("- Timeout is not purely mechanical: flagging is often the consequence of "
      "earlier time expenditure, so removing time-forfeit games removes some "
      "genuine clock-relevant signal as well.")
    a("- Filtering induces selection bias; board-decided low-clock games are a "
      "survivor population. Nothing here is a causal design, and no claim is made "
      "that time pressure causes worse reasoning.")
    a("- `Normal` mixes checkmate and resignation; draws are separable only via the "
      "result. No mate-vs-resignation claims.")
    a("- Board-decided under_60s late-clock cells are descriptive-only due to "
      "sample-size collapse; the localization conclusion rests on 60_180s.")
    a("- Ordered-bucket patterns are patterns; this is not a degradation curve.")
    a("- Player-level clustering remains unresolved (Phase 11.3); DRAW remains "
      "sparse and not solved; Stockfish eval is position context, not ground truth.")
    a("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Termination decomposition of the E3->E4 clock residual "
                    "(Ticket 11.2B, Contrast C2). Frozen predictions; no retraining."
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument("--predictions", default=None,
                        help="default: data/processed/eval_conditioned_predictions_{tag}.parquet")
    parser.add_argument("--features", default=None,
                        help="default: data/processed/feature_positions_broad_{tag}.parquet")
    parser.add_argument("--sf-eval", default=None,
                        help="optional, for split composition; default: "
                             "data/processed/sf_eval_broad_{tag}.parquet if present")
    parser.add_argument("--output-report", default=None,
                        help="default: reports/termination_decomposition_{tag}.md")
    parser.add_argument("--n-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-games-for-ci", type=int,
                        default=DEFAULT_MIN_GAMES_FOR_CI)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    tag = args.version_tag
    predictions = args.predictions or f"data/processed/eval_conditioned_predictions_{tag}.parquet"
    features = args.features or f"data/processed/feature_positions_broad_{tag}.parquet"
    sf_eval = args.sf_eval or f"data/processed/sf_eval_broad_{tag}.parquet"
    output_report = Path(args.output_report
                         or f"reports/termination_decomposition_{tag}.md")
    if output_report.exists() and not args.overwrite:
        raise FileExistsError(f"{output_report} exists; pass --overwrite")

    print("[term] Loading inputs...", file=sys.stderr)
    val_preds = load_e3_e4_val_predictions(predictions)
    keys = load_termination_keys(features)
    preds = attach_and_validate(val_preds, keys)
    n_per_model = len(preds.filter(pl.col("model_id") == MODEL_A))
    print(f"  val rows/model: {n_per_model:,}", file=sys.stderr)

    print("[term] Group deltas...", file=sys.stderr)
    group_results = compute_group_results(
        preds, args.n_replicates, args.seed, args.min_games_for_ci)

    print("[term] Late-clock slices...", file=sys.stderr)
    late_clock = compute_late_clock_results(
        preds, args.n_replicates, args.seed, args.min_games_for_ci)

    comp = composition_tables(keys, preds, sf_eval)
    rf = retained_fraction(
        group_results["board_decided"]["point_delta"],
        group_results["all_games"]["point_delta"],
    )

    payload = {
        "dataset_id": args.dataset_id,
        "version_tag": tag,
        "group_results": group_results,
        "late_clock_results": late_clock,
        "composition": comp,
        "retained_fraction": rf,
        "join_summary": {"n_val_rows_per_model": n_per_model},
        "artifact_paths": {"predictions": predictions, "features": features},
        "n_replicates": args.n_replicates,
        "seed": args.seed,
        "min_games_for_ci": args.min_games_for_ci,
    }
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(render_report(payload))
    print(f"[term] report: {output_report}", file=sys.stderr)

    # console summary
    print(f"\n=== 11.2B {tag} (E3->E4 delta, val) ===")
    for name in ("all_games", "board_decided", "time_forfeit"):
        r = group_results[name]
        ci = (f"[{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}] "
              f"{'contains 0' if r['contains_zero'] else 'EXCLUDES 0'}"
              if r.get("ci_lower") is not None else "(no CI)")
        print(f"  {name}: {r['point_delta']:+.4f} {ci} "
              f"({r['n_games']:,} games)")
    if rf["fraction"] is not None:
        print(f"  retained fraction: {rf['fraction']:.2f}")
    for label in ("all_games", "board_decided"):
        for bucket in LATE_CLOCK_ORDER:
            r = late_clock[label][bucket]
            if r.get("note") == "empty group":
                continue
            ci = (f"[{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}] "
                  f"{'cz' if r['contains_zero'] else 'EXCL'}"
                  if r.get("ci_lower") is not None else "no CI")
            print(f"  late {label}/{bucket}: {r['point_delta']:+.4f} {ci} "
                  f"({r['n_games']} games)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
