"""
Constraint slice analysis — Ticket 9.2B.

Localizes the replicated E3->E4 clock signal from 9.1B: within-slice paired
game-level bootstrap deltas of validation log_loss between E3 (eval+rating)
and E4 (eval+rating+clock), computed from the EXISTING 9.1B prediction
artifact. No models are trained or retrained here.

Slices (definitions fixed by the 9.2A audit, before results were computed):
    reference  — checkpoint (move_10..move_40)
    P1         — eval decidedness bucket (|sf_eval_cp|)
    P2         — avg_elo bucket
    P3         — min-clock bucket WITHIN late checkpoints (move_30+move_40)
    exploratory — clock imbalance bucket; terminal-exclusion sensitivity

Key 9.2A finding honoured here: marginal clock buckets are confounded with
checkpoint (almost all move_10 rows have >180s remaining), so the clock
analysis is conditioned on late checkpoints and a mandatory confounding
cross-tab is reported.

All results are predictive/descriptive associations on the validation split.
Not causal. Test split is never used.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.constraint_slices \\
        --dataset-id lichess_ten_zero_2024_09_250k_v1 \\
        --version-tag 2024_09_250k_v1 \\
        --predictions data/processed/eval_conditioned_predictions_2024_09_250k_v1.parquet \\
        --features data/processed/feature_positions_broad_2024_09_250k_v1.parquet \\
        --sf-eval data/processed/sf_eval_broad_2024_09_250k_v1.parquet \\
        --output-json data/processed/constraint_slices_2024_09_250k_v1.json \\
        --output-report reports/constraint_slices_2024_09_250k_v1.md \\
        --n-replicates 1000 --seed 42 --min-games-for-ci 300 --overwrite
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from chess_mhsuc.bootstrap_ci import (
    compute_delta_ci,
    run_paired_delta_bootstrap,
)
from chess_mhsuc.eval_conditioned_modeling import validate_pairing


# ---------------------------------------------------------------------------
# Constants — slice definitions fixed BEFORE computing results (9.2A audit)
# ---------------------------------------------------------------------------

DEFAULT_DATASET_ID = "lichess_ten_zero_2024_09_250k_v1"
DEFAULT_VERSION_TAG = "2024_09_250k_v1"

MODEL_A = "E3"  # eval + rating
MODEL_B = "E4"  # eval + rating + clock
DEFAULT_MIN_GAMES_FOR_CI = 300

_PROB_COLS = ["p_BLACK_WIN", "p_DRAW", "p_WHITE_WIN"]

CHECKPOINT_ORDER = ["move_10", "move_20", "move_30", "move_40"]
LATE_CHECKPOINTS = ["move_30", "move_40"]

DECIDEDNESS_ORDER = ["equal", "slight", "decided", "mate"]
ELO_BUCKET_ORDER = ["under_1200", "1200_1600", "1600_2000", "2000_plus"]
LATE_CLOCK_ORDER = ["under_60s", "60_180s", "over_180s"]
IMBALANCE_ORDER = ["balanced", "moderate_imbalance", "large_imbalance"]

SLICE_DEFINITIONS: dict[str, dict] = {
    "checkpoint": {
        "column": "selected_position_type",
        "cells": CHECKPOINT_ORDER,
        "role": "reference",
        "definition": "selected_position_type (primary numbered checkpoints)",
    },
    "decidedness": {
        "column": "decidedness_bucket",
        "cells": DECIDEDNESS_ORDER,
        "role": "primary (P1)",
        "definition": (
            "equal: |sf_eval_cp| < 100; slight: 100 <= |cp| < 300; "
            "decided: 300 <= |cp| < 10000; mate: |cp| >= 10000 "
            "(absolute value — White/Black direction not used)"
        ),
    },
    "elo_bucket": {
        "column": "elo_bucket",
        "cells": ELO_BUCKET_ORDER,
        "role": "primary (P2)",
        "definition": (
            "under_1200: avg_elo < 1200; 1200_1600: 1200 <= avg_elo < 1600; "
            "1600_2000: 1600 <= avg_elo < 2000; 2000_plus: avg_elo >= 2000"
        ),
    },
    "late_clock": {
        "column": "late_clock_bucket",
        "cells": LATE_CLOCK_ORDER,
        "role": "primary (P3)",
        "definition": (
            "WITHIN move_30+move_40 only. min_clock_s = "
            "min(white_clock_s_capped, black_clock_s_capped). "
            "under_60s: min < 60; 60_180s: 60 <= min < 180; "
            "over_180s: min >= 180. Marginal clock buckets are NOT primary: "
            "confounded with checkpoint (see confounding diagnostic)."
        ),
    },
    "clock_imbalance": {
        "column": "imbalance_bucket",
        "cells": IMBALANCE_ORDER,
        "role": "exploratory",
        "definition": (
            "balanced: |clock_diff_s| < 30; moderate_imbalance: "
            "30 <= |diff| < 90; large_imbalance: |diff| >= 90"
        ),
    },
}


# ---------------------------------------------------------------------------
# A. load_e3_e4_val_predictions
# ---------------------------------------------------------------------------

def load_e3_e4_val_predictions(predictions_path: str | Path) -> pl.DataFrame:
    """
    Load the 9.1B prediction artifact, filtered to E3/E4 validation rows.

    Raises if either model is missing, rows are misaligned, or any 'last'
    rows are present. Test split rows are never selected.
    """
    preds = pl.read_parquet(predictions_path)
    val = preds.filter(
        (pl.col("split_set") == "val")
        & pl.col("model_id").is_in([MODEL_A, MODEL_B])
    )
    for mid in (MODEL_A, MODEL_B):
        if len(val.filter(pl.col("model_id") == mid)) == 0:
            raise ValueError(
                f"No validation rows for {mid} in {predictions_path}. "
                f"Available models: {sorted(preds['model_id'].unique().to_list())}"
            )
    if "last" in set(val["selected_position_type"].unique().to_list()):
        raise ValueError("'last' rows present in prediction artifact val split")

    keys_a = val.filter(pl.col("model_id") == MODEL_A).select(
        ["game_id", "selected_position_type", "result_class"]
    )
    keys_b = val.filter(pl.col("model_id") == MODEL_B).select(
        ["game_id", "selected_position_type", "result_class"]
    )
    if not keys_a.equals(keys_b):
        raise ValueError(
            f"{MODEL_A}/{MODEL_B} validation rows are not aligned "
            "(row identities or labels differ)"
        )
    return val.select(
        ["model_id", "split_set", "game_id", "selected_position_type",
         "result_class"] + _PROB_COLS
    )


# ---------------------------------------------------------------------------
# B. derive_slice_keys
# ---------------------------------------------------------------------------

def derive_slice_keys(
    feature_df: pl.DataFrame,
    sf_df: pl.DataFrame,
) -> pl.DataFrame:
    """
    Build the per-position slice-key table for the validation split.

    Join: (game_id, selected_position_type) — unique in both inputs
    (verified); NEVER (game_id, ply). Only the needed columns are selected.
    """
    prim = feature_df.filter(pl.col("selected_position_type") != "last")
    key = ["game_id", "selected_position_type"]
    if prim.select(key).n_unique() != len(prim):
        raise ValueError("(game_id, selected_position_type) not unique in feature table")
    if sf_df.select(key).n_unique() != len(sf_df):
        raise ValueError("(game_id, selected_position_type) not unique in sf_eval artifact")

    feat_slim = prim.select(
        key + ["avg_elo", "white_clock_s_capped", "black_clock_s_capped",
               "clock_diff_s"]
    )
    sf_slim = sf_df.select(key + ["split_set", "sf_eval_cp", "sf_depth"])

    joined = feat_slim.join(sf_slim, on=key, how="left")
    n_orphans = joined["sf_eval_cp"].null_count()
    if n_orphans > 0:
        raise ValueError(f"{n_orphans} orphan rows after sf_eval join")

    val = joined.filter(pl.col("split_set") == "val")

    abs_cp = pl.col("sf_eval_cp").abs()
    min_clock = pl.min_horizontal("white_clock_s_capped", "black_clock_s_capped")
    abs_imb = pl.col("clock_diff_s").abs()

    return val.with_columns([
        pl.when(abs_cp < 100).then(pl.lit("equal"))
        .when(abs_cp < 300).then(pl.lit("slight"))
        .when(abs_cp < 10_000).then(pl.lit("decided"))
        .otherwise(pl.lit("mate"))
        .alias("decidedness_bucket"),

        pl.when(pl.col("avg_elo") < 1200).then(pl.lit("under_1200"))
        .when(pl.col("avg_elo") < 1600).then(pl.lit("1200_1600"))
        .when(pl.col("avg_elo") < 2000).then(pl.lit("1600_2000"))
        .otherwise(pl.lit("2000_plus"))
        .alias("elo_bucket"),

        pl.when(~pl.col("selected_position_type").is_in(LATE_CHECKPOINTS))
        .then(pl.lit(None))
        .when(min_clock < 60).then(pl.lit("under_60s"))
        .when(min_clock < 180).then(pl.lit("60_180s"))
        .otherwise(pl.lit("over_180s"))
        .alias("late_clock_bucket"),

        pl.when(min_clock < 60).then(pl.lit("under_60s"))
        .when(min_clock < 180).then(pl.lit("60_180s"))
        .otherwise(pl.lit("over_180s"))
        .alias("marginal_clock_bucket"),

        pl.when(abs_imb < 30).then(pl.lit("balanced"))
        .when(abs_imb < 90).then(pl.lit("moderate_imbalance"))
        .otherwise(pl.lit("large_imbalance"))
        .alias("imbalance_bucket"),

        (pl.col("sf_depth") == 0).alias("is_terminal"),
    ]).select(
        key + ["decidedness_bucket", "elo_bucket", "late_clock_bucket",
               "marginal_clock_bucket", "imbalance_bucket", "is_terminal"]
    )


# ---------------------------------------------------------------------------
# C. attach_slice_keys
# ---------------------------------------------------------------------------

def attach_slice_keys(
    val_preds: pl.DataFrame,
    slice_keys: pl.DataFrame,
) -> pl.DataFrame:
    """Join slice keys onto prediction rows; assert zero orphans."""
    joined = val_preds.join(
        slice_keys, on=["game_id", "selected_position_type"], how="left"
    )
    n_orphans = joined["decidedness_bucket"].null_count()
    if n_orphans > 0:
        raise ValueError(f"{n_orphans} prediction rows have no slice keys")
    return joined


# ---------------------------------------------------------------------------
# D. compute_cell_result
# ---------------------------------------------------------------------------

def compute_cell_result(
    cell_df: pl.DataFrame,
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict[str, Any]:
    """
    Within-cell paired E3->E4 delta.

    delta = log_loss(E4) - log_loss(E3); negative means E4 (clock) improved.
    CI only when unique games >= min_games_for_ci; sub-threshold cells keep
    the point delta with an explicit note (never silently dropped).
    """
    from chess_mhsuc.bootstrap_ci import compute_point_log_loss, extract_val_rows

    sub = cell_df.select(
        ["model_id", "split_set", "game_id", "result_class"] + _PROB_COLS
    )
    validate_pairing(sub, MODEL_A, MODEL_B)

    rows_a = extract_val_rows(sub, MODEL_A)
    n_rows = len(rows_a)
    n_games = rows_a["game_id"].n_unique()
    n_draw = len(rows_a.filter(pl.col("result_class") == "DRAW"))

    ll_a = compute_point_log_loss(rows_a)
    ll_b = compute_point_log_loss(extract_val_rows(sub, MODEL_B))
    point_delta = ll_b - ll_a

    result: dict[str, Any] = {
        "n_rows": n_rows,
        "n_games": n_games,
        "n_draw_rows": n_draw,
        "log_loss_e3": ll_a,
        "log_loss_e4": ll_b,
        "point_delta": point_delta,
    }

    if n_games >= min_games_for_ci:
        boot = run_paired_delta_bootstrap(
            sub, MODEL_A, MODEL_B, n_replicates=n_replicates, seed=seed
        )
        ci = compute_delta_ci(boot, MODEL_A, MODEL_B, sub)
        result.update({
            "ci_lower": ci["ci_lower"],
            "ci_upper": ci["ci_upper"],
            "contains_zero": ci["contains_zero"],
            "n_replicates": ci["n_replicates"],
            "note": None,
        })
    else:
        result.update({
            "ci_lower": None,
            "ci_upper": None,
            "contains_zero": None,
            "n_replicates": 0,
            "note": "below min game threshold",
        })
    return result


# ---------------------------------------------------------------------------
# E. run_slice_group
# ---------------------------------------------------------------------------

def run_slice_group(
    preds_with_keys: pl.DataFrame,
    slice_column: str,
    cell_order: list[str],
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict[str, dict]:
    """Compute cell results for one slice column, in fixed cell order."""
    out: dict[str, dict] = {}
    for cell in cell_order:
        cell_df = preds_with_keys.filter(pl.col(slice_column) == cell)
        if len(cell_df) == 0:
            out[cell] = {"n_rows": 0, "n_games": 0, "note": "empty cell"}
            continue
        print(f"    [{slice_column}={cell}] "
              f"{len(cell_df) // 2:,} rows/model...", file=sys.stderr)
        out[cell] = compute_cell_result(
            cell_df, n_replicates=n_replicates, seed=seed,
            min_games_for_ci=min_games_for_ci,
        )
    return out


# ---------------------------------------------------------------------------
# F. confounding_crosstab
# ---------------------------------------------------------------------------

def confounding_crosstab(preds_with_keys: pl.DataFrame) -> dict[str, dict]:
    """
    Mandatory diagnostic: marginal clock bucket x checkpoint row/game counts
    (one model's rows). Explains why marginal clock buckets are not primary.
    """
    one_model = preds_with_keys.filter(pl.col("model_id") == MODEL_A)
    out: dict[str, dict] = {}
    for cpt in CHECKPOINT_ORDER:
        sub = one_model.filter(pl.col("selected_position_type") == cpt)
        row: dict[str, dict] = {}
        for clk in LATE_CLOCK_ORDER:
            cell = sub.filter(pl.col("marginal_clock_bucket") == clk)
            row[clk] = {"rows": len(cell), "games": cell["game_id"].n_unique()}
        out[cpt] = row
    return out


# ---------------------------------------------------------------------------
# G. terminal_sensitivity
# ---------------------------------------------------------------------------

def terminal_sensitivity(
    preds_with_keys: pl.DataFrame,
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict[str, dict]:
    """
    Exploratory: overall E3->E4 delta with terminal (sf_depth=0) positions
    included vs excluded. Sensitivity check, not a primary slice.
    """
    incl = compute_cell_result(
        preds_with_keys, n_replicates, seed, min_games_for_ci
    )
    excl = compute_cell_result(
        preds_with_keys.filter(~pl.col("is_terminal")),
        n_replicates, seed, min_games_for_ci,
    )
    return {"terminal_included": incl, "terminal_excluded": excl}


# ---------------------------------------------------------------------------
# H. build_payload
# ---------------------------------------------------------------------------

def build_payload(
    dataset_id: str,
    version_tag: str,
    slice_results: dict[str, dict],
    crosstab: dict,
    terminal_results: dict,
    artifact_paths: dict[str, str],
    n_replicates: int,
    seed: int,
    min_games_for_ci: int,
) -> dict:
    """Assemble the gitignored results JSON payload."""
    return {
        "dataset_id": dataset_id,
        "version_tag": version_tag,
        "ticket": "9.2B",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_a": MODEL_A,
        "model_b": MODEL_B,
        "delta_convention": "delta = log_loss(E4) - log_loss(E3); negative = E4 (clock) improved",
        "n_replicates": n_replicates,
        "seed": seed,
        "min_games_for_ci": min_games_for_ci,
        "artifact_paths": artifact_paths,
        "slice_definitions": {
            name: {k: v for k, v in d.items() if k != "column"}
            for name, d in SLICE_DEFINITIONS.items()
        },
        "slice_results": slice_results,
        "confounding_crosstab_clock_x_checkpoint": crosstab,
        "terminal_sensitivity": terminal_results,
        "caveats": [
            "All slice results are predictive associations on the validation "
            "split, not causal effects.",
            "Fixed-depth Stockfish eval is objective position context, not "
            "ground truth.",
            "Slice analyses localize a single already-confirmed effect; they "
            "are not independent hypothesis tests, and no multiple-comparison "
            "correction is claimed.",
            "Degradation curves are not established by ordered-bucket patterns.",
            "Reasoning quality is not directly measured by any of these metrics.",
            "Test split was not used.",
            "Player-level leakage remains unresolved.",
            "DRAW remains sparse and is not solved.",
        ],
    }


# ---------------------------------------------------------------------------
# I. render_report
# ---------------------------------------------------------------------------

def _fmt(x: float | None, nd: int = 4) -> str:
    if x is None:
        return "—"
    return f"{x:.{nd}f}"


def _cell_row(cell: str, r: dict) -> str:
    if r.get("note") == "empty cell":
        return f"| {cell} | 0 | 0 | — | — | — | — | — | empty cell |"
    ci = (
        f"[{_fmt(r['ci_lower'])}, {_fmt(r['ci_upper'])}]"
        if r.get("ci_lower") is not None else "N/A"
    )
    cz = (
        ("Yes" if r["contains_zero"] else "No")
        if r.get("contains_zero") is not None else "—"
    )
    note = r.get("note") or ""
    return (
        f"| {cell} | {r['n_rows']:,} | {r['n_games']:,} | "
        f"{_fmt(r['log_loss_e3'])} | {_fmt(r['log_loss_e4'])} | "
        f"{_fmt(r['point_delta'])} | {ci} | {cz} | {note} |"
    )


_TABLE_HEADER = (
    "| Cell | Rows | Games | E3 log_loss | E4 log_loss | Delta | 95% CI | "
    "CI contains zero | Note |\n"
    "|---|---|---|---|---|---|---|---|---|"
)


def render_report(payload: dict) -> str:
    """Deterministic markdown report (no timestamps in body)."""
    sr = payload["slice_results"]
    ct = payload["confounding_crosstab_clock_x_checkpoint"]
    ts = payload["terminal_sensitivity"]
    defs = payload["slice_definitions"]
    min_g = payload["min_games_for_ci"]

    lines: list[str] = []
    a = lines.append

    a("# Constraint Slice Analysis — Localizing the E3→E4 Clock Signal")
    a("")
    a("**Ticket:** 9.2B — Constraint Slice / Interaction Implementation")
    a(f"**Dataset:** `{payload['dataset_id']}`")
    a(f"**Version tag:** `{payload['version_tag']}`")
    a("")
    a("---")
    a("")

    a("## 1. ELI5 / TLDR")
    a("")
    a("The 9.1B scale-up confirmed that clock features add predictive signal "
      "for game outcomes after controlling for engine eval and ratings "
      "(E3→E4). This report asks *where* that signal lives, by recomputing "
      "the paired E3→E4 validation delta inside slices defined before any "
      "results were computed: checkpoint, position decidedness, rating "
      "bucket, and — the key design point — clock-pressure buckets *within* "
      "late checkpoints, because marginal clock buckets are confounded with "
      "checkpoint. No models were trained; everything reuses the 9.1B "
      "prediction artifact. All findings are predictive associations, not "
      "causal effects.")
    a("")

    a("## 2. Result Being Localized")
    a("")
    a("E3 (Stockfish eval + rating) → E4 (eval + rating + clock), 9.1B "
      "validation split: delta −0.0138, 95% CI [−0.0186, −0.0091], CI "
      "excludes zero. Per-checkpoint reference deltas are recomputed below "
      "for self-containment.")
    a("")

    a("## 3. Inputs and Join Integrity")
    a("")
    paths = payload["artifact_paths"]
    a(f"- Predictions: `{paths.get('predictions')}` (E3/E4 validation rows, "
      "pairing validated per cell)")
    a(f"- Slice keys: `{paths.get('features')}` + `{paths.get('sf_eval')}` "
      "joined on `(game_id, selected_position_type)` — 0 orphans; `last` "
      "rows excluded; validation split only; test split never read into the "
      "analysis frame.")
    a("")

    a("## 4. Slice Definitions")
    a("")
    a("Fixed by the 9.2A audit before results were computed; not tuned "
      "afterwards.")
    a("")
    a("| Slice | Role | Definition |")
    a("|---|---|---|")
    for name, d in defs.items():
        a(f"| {name} | {d['role']} | {d['definition']} |")
    a("")

    a("## 5. Data Sufficiency")
    a("")
    a(f"Bootstrap CI rule: cells with ≥ {min_g} unique games get a "
      f"game-level clustered bootstrap CI ({payload['n_replicates']} "
      f"replicates, seed={payload['seed']}); smaller cells report the point "
      "delta with an explicit 'below min game threshold' note. No cell is "
      "silently dropped; no cells were merged after seeing results.")
    a("")

    a("## 6. Confounding Diagnostic: Clock Bucket × Checkpoint")
    a("")
    a("Row/game counts per marginal min-clock bucket within each checkpoint "
      "(one model's validation rows). Low clock is almost entirely a "
      "late-checkpoint phenomenon, which is why marginal clock buckets are "
      "not a primary slice and the clock analysis (P3) is conditioned on "
      "move_30+move_40.")
    a("")
    a("| Checkpoint | " + " | ".join(LATE_CLOCK_ORDER) + " |")
    a("|---|" + "---|" * len(LATE_CLOCK_ORDER))
    for cpt in CHECKPOINT_ORDER:
        cells = []
        for clk in LATE_CLOCK_ORDER:
            c = ct[cpt][clk]
            cells.append(f"{c['rows']:,} rows / {c['games']:,} games")
        a(f"| {cpt} | " + " | ".join(cells) + " |")
    a("")

    def _section(num: int, title: str, key: str, order: list[str], blurb: str):
        a(f"## {num}. {title}")
        a("")
        a(blurb)
        a("")
        a(_TABLE_HEADER)
        for cell in order:
            a(_cell_row(cell, sr[key][cell]))
        a("")

    _section(7, "Reference: Per-Checkpoint E3→E4 Deltas", "checkpoint",
             CHECKPOINT_ORDER,
             "Recomputed from the prediction artifact (matches 9.1B).")
    _section(8, "P1: Eval Decidedness Slice", "decidedness",
             DECIDEDNESS_ORDER,
             "Does the clock signal live in contested or decided positions? "
             "Buckets use |sf_eval_cp| (absolute; direction not used).")
    _section(9, "P2: Rating Bucket Slice", "elo_bucket", ELO_BUCKET_ORDER,
             "Is the clock signal skill-dependent? Buckets use avg_elo.")
    _section(10, "P3: Late-Checkpoint Clock Bucket Slice", "late_clock",
             LATE_CLOCK_ORDER,
             "The key constraint test: within move_30+move_40 only, is the "
             "signal concentrated where remaining time is actually low? "
             "Conditioning on late checkpoints controls the clock×checkpoint "
             "confound shown in Section 6.")

    a("## 11. Exploratory Slices")
    a("")
    a("Clearly exploratory; interpret only directionally.")
    a("")
    a("**Clock imbalance (marginal, all checkpoints):**")
    a("")
    a(_TABLE_HEADER)
    for cell in IMBALANCE_ORDER:
        a(_cell_row(cell, sr["clock_imbalance"][cell]))
    a("")
    a("**Terminal-exclusion sensitivity (overall delta, all val rows):**")
    a("")
    a(_TABLE_HEADER)
    a(_cell_row("terminal_included", ts["terminal_included"]))
    a(_cell_row("terminal_excluded", ts["terminal_excluded"]))
    a("")

    a("## 12. Interpretation")
    a("")
    # data-driven cautious interpretation
    late = sr["late_clock"]
    dec = sr["decidedness"]
    interp: list[str] = []
    u60 = late["under_60s"]
    o180 = late["over_180s"]
    interp.append(
        "- Within late checkpoints, the point delta by remaining-time bucket "
        f"is: under_60s {_fmt(u60.get('point_delta'))}, 60_180s "
        f"{_fmt(late['60_180s'].get('point_delta'))}, over_180s "
        f"{_fmt(o180.get('point_delta'))}. Where CIs exist, contains-zero "
        "flags are shown in Section 10."
    )
    interp.append(
        "- By decidedness, the point delta is: equal "
        f"{_fmt(dec['equal'].get('point_delta'))}, slight "
        f"{_fmt(dec['slight'].get('point_delta'))}, decided "
        f"{_fmt(dec['decided'].get('point_delta'))}, mate "
        f"{_fmt(dec['mate'].get('point_delta'))}."
    )
    for line in interp:
        a(line)
    a("")
    a("Allowed readings: clock features provide predictive signal in slices "
      "whose CI excludes zero; the signal is concentrated in later "
      "checkpoints; where the late-game low-clock cells show larger deltas, "
      "the pattern is consistent with time-pressure relevance. If the "
      "signal concentrates in decided positions, a plausible reading is "
      "that clocks help predict whether a winning position is converted "
      "before flagging — that is still a predictive association, not a "
      "statement about reasoning quality.")
    a("")

    a("## 13. Guardrails / Forbidden Claims")
    a("")
    a("- These slices localize one already-confirmed effect; they are not "
      "independent hypothesis tests, and no multiple-comparison correction "
      "is claimed.")
    a("- Nothing here shows that time pressure *degrades* play, and nothing "
      "here directly assesses reasoning — only outcome predictability is "
      "analyzed.")
    a("- Ordered-bucket patterns are reported as patterns; degradation "
      "curves are not established.")
    a("- Stockfish depth=12 eval is objective position context, not ground "
      "truth.")
    a("- Test split was not used. DRAW remains sparse and is not solved.")
    a("")

    a("## 14. Limitations")
    a("")
    a("- Sub-threshold cells (marked 'below min game threshold') have point "
      "deltas only; treat them descriptively.")
    a(f"- Slice keys and predictions come from the same dataset "
      f"(`{payload['dataset_id']}`); external validity beyond the tested "
      "month(s) is not established.")
    a("- Player-level leakage remains unresolved and applies to every slice.")
    a("- Decidedness, checkpoint, and clock depletion are mutually "
      "correlated; P3's late-checkpoint conditioning controls the largest "
      "confound but not all of them.")
    a("")

    a("## 15. Reproducibility")
    a("")
    a("```bash")
    a("PYTHONPATH=src python -m chess_mhsuc.constraint_slices \\")
    a(f"    --dataset-id {payload['dataset_id']} \\")
    a(f"    --version-tag {payload['version_tag']} \\")
    a(f"    --predictions {paths.get('predictions')} \\")
    a(f"    --features {paths.get('features')} \\")
    a(f"    --sf-eval {paths.get('sf_eval')} \\")
    a(f"    --output-json {paths.get('output_json')} \\")
    a(f"    --output-report {paths.get('output_report')} \\")
    a(f"    --n-replicates {payload['n_replicates']} "
      f"--seed {payload['seed']} "
      f"--min-games-for-ci {min_g} --overwrite")
    a("```")
    a("")
    a("Deterministic: fixed slice definitions, seed=42 bootstrap, no "
      "timestamps in the report body (timestamp lives in the JSON only).")
    a("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# J. write_outputs
# ---------------------------------------------------------------------------

def write_outputs(
    payload: dict,
    report_text: str,
    output_json: str | Path,
    output_report: str | Path,
    overwrite: bool = False,
) -> None:
    """Write the JSON artifact (gitignored) and the committed report."""
    paths = [Path(output_json), Path(output_report)]
    for p in paths:
        if p.exists() and not overwrite:
            raise FileExistsError(f"{p} exists; pass --overwrite to replace")
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(paths[0], "w") as f:
        json.dump(payload, f, indent=2)
    paths[1].write_text(report_text)


# ---------------------------------------------------------------------------
# K. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Constraint slice analysis of the E3->E4 clock signal "
                    "(Ticket 9.2B). Uses existing predictions; trains nothing."
    )
    parser.add_argument("--dataset-id", default=DEFAULT_DATASET_ID)
    parser.add_argument("--version-tag", default=DEFAULT_VERSION_TAG)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--sf-eval", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-report", required=True)
    parser.add_argument("--n-replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-games-for-ci", type=int,
                        default=DEFAULT_MIN_GAMES_FOR_CI)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    print("[slices] Loading inputs...", file=sys.stderr)
    val_preds = load_e3_e4_val_predictions(args.predictions)
    feature_df = pl.read_parquet(args.features)
    sf_df = pl.read_parquet(args.sf_eval)
    slice_keys = derive_slice_keys(feature_df, sf_df)
    preds = attach_slice_keys(val_preds, slice_keys)
    n_rows = len(preds.filter(pl.col("model_id") == MODEL_A))
    print(f"  val rows/model: {n_rows:,} | games: "
          f"{preds['game_id'].n_unique():,}", file=sys.stderr)

    slice_results: dict[str, dict] = {}
    for name, d in SLICE_DEFINITIONS.items():
        print(f"[slices] {name} ({d['role']})...", file=sys.stderr)
        slice_results[name] = run_slice_group(
            preds, d["column"], d["cells"],
            n_replicates=args.n_replicates, seed=args.seed,
            min_games_for_ci=args.min_games_for_ci,
        )

    print("[slices] Confounding cross-tab...", file=sys.stderr)
    crosstab = confounding_crosstab(preds)

    print("[slices] Terminal sensitivity...", file=sys.stderr)
    terminal_results = terminal_sensitivity(
        preds, n_replicates=args.n_replicates, seed=args.seed,
        min_games_for_ci=args.min_games_for_ci,
    )

    payload = build_payload(
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
        slice_results=slice_results,
        crosstab=crosstab,
        terminal_results=terminal_results,
        artifact_paths={
            "predictions": str(args.predictions),
            "features": str(args.features),
            "sf_eval": str(args.sf_eval),
            "output_json": str(args.output_json),
            "output_report": str(args.output_report),
        },
        n_replicates=args.n_replicates,
        seed=args.seed,
        min_games_for_ci=args.min_games_for_ci,
    )
    report_text = render_report(payload)
    write_outputs(payload, report_text, args.output_json, args.output_report,
                  overwrite=args.overwrite)
    print(f"[slices] JSON: {args.output_json}", file=sys.stderr)
    print(f"[slices] report: {args.output_report}", file=sys.stderr)

    # console summary
    print("\n=== 9.2B slice summary (E3->E4 delta, val) ===")
    for name in ("checkpoint", "decidedness", "elo_bucket", "late_clock"):
        print(f"  [{name}]")
        for cell, r in slice_results[name].items():
            if r.get("note") == "empty cell":
                print(f"    {cell}: empty")
                continue
            if r.get("ci_lower") is not None:
                zero = "contains 0" if r["contains_zero"] else "EXCLUDES 0"
                print(f"    {cell}: {r['point_delta']:+.4f} "
                      f"[{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}] {zero} "
                      f"({r['n_games']:,} games)")
            else:
                print(f"    {cell}: {r['point_delta']:+.4f} (no CI — "
                      f"{r['n_games']} games < threshold)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
