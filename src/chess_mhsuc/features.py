"""
features.py — v1 feature engineering for chess-MHSUC pipeline.

Reads cleaned position records from data/processed/ and produces two local-only
feature tables plus a metadata JSON sidecar (all gitignored):

  feature_positions_broad_{tag}.parquet   — all checkpoint positions, eval nullable
  feature_positions_eval_{tag}.parquet    — eval-gated subset (has_eval=True)
  feature_metadata_{tag}.json             — column categorization, policy, counts

Feature design from Ticket 3.2A audit:

  Added features:
    Rating:    avg_elo
    Clock:     *_capped, *_frac, *_low_{60,30,10}, clock_anomaly
    Eval:      eval_cp_clipped, is_mate_eval, eval_mate_abs, eval_white_winning
    Position:  is_last_checkpoint, white_to_move_next, checkpoint_index, phase_index
    Slice:     is_time_forfeit
    Flag:      duplicate_ply_checkpoint

  Dropped from input (if present):
    n_plies_total, ply, white_rating_diff, black_rating_diff,
    accepted_basic, accepted_eval, rejection_reason, has_clock,
    result_raw, time_control, source_file, source_month, event,
    utc_date, utc_time

  Labels (not features):
    result_class, white_result_numeric

  Slice columns (not features):
    game_id, termination, is_time_forfeit, has_eval

  Caution columns (present but not default model inputs):
    is_last_checkpoint, side_to_move_next, white_to_move_next,
    duplicate_ply_checkpoint

  Leakage policy:
    result_class, white_result_numeric  — target labels, never features
    termination, n_plies_total          — post-game info, never features
    white_rating_diff, black_rating_diff — post-game rating change, forbidden
    game_id                             — group/split key only, never a feature

Usage:
    PYTHONPATH=src python -m chess_mhsuc.features \\
        --positions-broad data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet \\
        --positions-eval  data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet \\
        --output-dir      data/processed \\
        --version-tag     2024_09_25k_v1

See schemas.py for field definitions.
See DATA_POLICY.md for data safety rules.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLOCK_CAP_S = 600
EVAL_CLIP_CP = 1000
LOW_TIME_THRESHOLDS_S = [60, 30, 10]

_FORBIDDEN_COLS = [
    "n_plies_total",
    "ply",
    "white_rating_diff",
    "black_rating_diff",
    "accepted_basic",
    "accepted_eval",
    "rejection_reason",
    "has_clock",
    "result_raw",
    "time_control",
    "source_file",
    "source_month",
    "event",
    "utc_date",
    "utc_time",
]

_CHECKPOINT_INDEX = {
    "move_10": 0,
    "move_20": 1,
    "move_30": 2,
    "move_40": 3,
    "last": 4,
}

_PHASE_INDEX = {
    "opening": 0,
    "middlegame": 1,
    "endgame": 2,
}


# ---------------------------------------------------------------------------
# Pure feature functions
# ---------------------------------------------------------------------------


def add_rating_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add derived rating features.

    Added:
      avg_elo = (white_elo + black_elo) / 2

    Preserved: white_elo, black_elo, elo_diff
    """
    return df.with_columns(
        ((pl.col("white_elo") + pl.col("black_elo")) / 2.0).alias("avg_elo"),
    )


def add_clock_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add derived clock features.

    Capped values (internal intermediate for fracs and flags):
      white_clock_s_capped = min(white_clock_s, 600)
      black_clock_s_capped = min(black_clock_s, 600)

    Normalized fractions (based on capped values):
      white_clock_frac = white_clock_s_capped / 600.0
      black_clock_frac = black_clock_s_capped / 600.0
      clock_diff_frac  = (white_clock_s_capped - black_clock_s_capped) / 600.0

    Low-time boolean flags (based on capped values):
      white_low_60, black_low_60  (clock_s_capped <= 60)
      white_low_30, black_low_30  (clock_s_capped <= 30)
      white_low_10, black_low_10  (clock_s_capped <= 10)

    Anomaly flag (based on raw values):
      clock_anomaly = white_clock_s > 600 OR black_clock_s > 600

    Raw values preserved: white_clock_s, black_clock_s, clock_diff_s
    Anomaly rows are NOT excluded.
    """
    return df.with_columns(
        pl.col("white_clock_s").clip(upper_bound=CLOCK_CAP_S).alias("white_clock_s_capped"),
        pl.col("black_clock_s").clip(upper_bound=CLOCK_CAP_S).alias("black_clock_s_capped"),
    ).with_columns(
        (pl.col("white_clock_s_capped") / float(CLOCK_CAP_S)).alias("white_clock_frac"),
        (pl.col("black_clock_s_capped") / float(CLOCK_CAP_S)).alias("black_clock_frac"),
        (
            (pl.col("white_clock_s_capped") - pl.col("black_clock_s_capped")) / float(CLOCK_CAP_S)
        ).alias("clock_diff_frac"),
        (pl.col("white_clock_s_capped") <= 60).alias("white_low_60"),
        (pl.col("black_clock_s_capped") <= 60).alias("black_low_60"),
        (pl.col("white_clock_s_capped") <= 30).alias("white_low_30"),
        (pl.col("black_clock_s_capped") <= 30).alias("black_low_30"),
        (pl.col("white_clock_s_capped") <= 10).alias("white_low_10"),
        (pl.col("black_clock_s_capped") <= 10).alias("black_low_10"),
        (
            (pl.col("white_clock_s") > CLOCK_CAP_S) | (pl.col("black_clock_s") > CLOCK_CAP_S)
        ).alias("clock_anomaly"),
    )


def add_eval_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add derived eval features.

    eval_cp_clipped:
      - null when eval_cp is null
      - +1000 when eval_cp > 1000  (includes +10000 mate sentinel)
      - -1000 when eval_cp < -1000 (includes -10000 mate sentinel)
      - otherwise eval_cp

    is_mate_eval:
      True iff eval_mate is not null

    eval_mate_abs:
      abs(eval_mate); null if eval_mate is null

    eval_white_winning:
      True if eval_cp > 0, False if eval_cp <= 0, null if eval_cp is null

    Raw eval_cp and eval_mate are preserved.
    Missing eval is NOT imputed to 0.
    has_eval is preserved as metadata/slice, not a predictive feature.
    """
    return df.with_columns(
        pl.when(pl.col("eval_cp").is_null())
        .then(pl.lit(None, dtype=pl.Int64))
        .when(pl.col("eval_cp") > EVAL_CLIP_CP)
        .then(pl.lit(EVAL_CLIP_CP, dtype=pl.Int64))
        .when(pl.col("eval_cp") < -EVAL_CLIP_CP)
        .then(pl.lit(-EVAL_CLIP_CP, dtype=pl.Int64))
        .otherwise(pl.col("eval_cp"))
        .alias("eval_cp_clipped"),

        pl.col("eval_mate").is_not_null().alias("is_mate_eval"),

        pl.when(pl.col("eval_mate").is_null())
        .then(pl.lit(None, dtype=pl.Int64))
        .otherwise(pl.col("eval_mate").abs())
        .alias("eval_mate_abs"),

        pl.when(pl.col("eval_cp").is_null())
        .then(pl.lit(None, dtype=pl.Boolean))
        .otherwise(pl.col("eval_cp") > 0)
        .alias("eval_white_winning"),
    )


def add_position_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add derived position/checkpoint features.

    is_last_checkpoint:
      True iff selected_position_type == "last"

    white_to_move_next:
      True iff side_to_move_next == "white"

    checkpoint_index:
      move_10->0, move_20->1, move_30->2, move_40->3, last->4

    phase_index:
      opening->0, middlegame->1, endgame->2

    Preserved: selected_position_type, move_number, phase, side_to_move_next
    Note: ply is NOT dropped here; it is dropped in drop_forbidden_columns.
    """
    checkpoint_expr = (
        pl.when(pl.col("selected_position_type") == "move_10").then(pl.lit(0))
        .when(pl.col("selected_position_type") == "move_20").then(pl.lit(1))
        .when(pl.col("selected_position_type") == "move_30").then(pl.lit(2))
        .when(pl.col("selected_position_type") == "move_40").then(pl.lit(3))
        .when(pl.col("selected_position_type") == "last").then(pl.lit(4))
        .otherwise(pl.lit(None, dtype=pl.Int64))
        .alias("checkpoint_index")
    )
    phase_expr = (
        pl.when(pl.col("phase") == "opening").then(pl.lit(0))
        .when(pl.col("phase") == "middlegame").then(pl.lit(1))
        .when(pl.col("phase") == "endgame").then(pl.lit(2))
        .otherwise(pl.lit(None, dtype=pl.Int64))
        .alias("phase_index")
    )
    return df.with_columns(
        (pl.col("selected_position_type") == "last").alias("is_last_checkpoint"),
        (pl.col("side_to_move_next") == "white").alias("white_to_move_next"),
        checkpoint_expr,
        phase_expr,
    )


def add_slice_columns(df: pl.DataFrame) -> pl.DataFrame:
    """
    Add evaluation/slice columns that are NOT model features.

    is_time_forfeit:
      True iff termination == "Time forfeit"
      This is a slice column for subgroup analysis only.
    """
    return df.with_columns(
        (pl.col("termination") == "Time forfeit").alias("is_time_forfeit"),
    )


def add_duplicate_checkpoint_flag(df: pl.DataFrame) -> pl.DataFrame:
    """
    Flag rows where another row in the same game has the same ply but a
    different selected_position_type.

    duplicate_ply_checkpoint:
      True if the (game_id, ply) pair appears in more than one row.
      This identifies games where the final ply coincides with a numbered
      checkpoint, producing two rows with the same ply but different types.

    Duplicate rows are NOT dropped; this flag allows callers to deduplicate
    according to their experiment design.

    Note: 'ply' must still be present when this function is called.
    It is dropped later by drop_forbidden_columns.
    """
    counts = (
        df.group_by(["game_id", "ply"])
        .agg(pl.len().alias("_n_rows_at_ply"))
    )
    return (
        df.join(counts, on=["game_id", "ply"], how="left")
        .with_columns(
            (pl.col("_n_rows_at_ply") > 1).alias("duplicate_ply_checkpoint")
        )
        .drop("_n_rows_at_ply")
    )


def drop_forbidden_columns(df: pl.DataFrame) -> pl.DataFrame:
    """
    Drop post-game and metadata columns that must not appear in feature tables.

    Drops (if present): n_plies_total, ply, white_rating_diff, black_rating_diff,
    accepted_basic, accepted_eval, rejection_reason, has_clock, result_raw,
    time_control, source_file, source_month, event, utc_date, utc_time.

    Uses "if present" logic — safe to call on DataFrames that lack any of these.
    """
    to_drop = [c for c in _FORBIDDEN_COLS if c in df.columns]
    if to_drop:
        return df.drop(to_drop)
    return df


def build_feature_table(df: pl.DataFrame) -> pl.DataFrame:
    """
    Orchestrate all feature engineering steps.

    Step order:
      1. add_rating_features
      2. add_clock_features
      3. add_eval_features
      4. add_position_features   (before drop so ply is still available)
      5. add_slice_columns
      6. add_duplicate_checkpoint_flag (uses ply before it is dropped)
      7. drop_forbidden_columns

    No rows are dropped.
    """
    df = add_rating_features(df)
    df = add_clock_features(df)
    df = add_eval_features(df)
    df = add_position_features(df)
    df = add_slice_columns(df)
    df = add_duplicate_checkpoint_flag(df)
    df = drop_forbidden_columns(df)
    return df


# ---------------------------------------------------------------------------
# Metadata builder
# ---------------------------------------------------------------------------

_DEFAULT_PREDICTIVE_FEATURES = [
    "white_elo", "black_elo", "elo_diff", "avg_elo",
    "white_clock_s", "black_clock_s", "clock_diff_s",
    "white_clock_s_capped", "black_clock_s_capped",
    "white_clock_frac", "black_clock_frac", "clock_diff_frac",
    "white_low_60", "black_low_60",
    "white_low_30", "black_low_30",
    "white_low_10", "black_low_10",
    "clock_anomaly",
    "selected_position_type", "move_number", "phase",
    "checkpoint_index", "phase_index",
]

_EVAL_PREDICTIVE_FEATURES = [
    "eval_cp", "eval_cp_clipped", "eval_mate",
    "is_mate_eval", "eval_mate_abs", "eval_white_winning",
]

_CAUTION_COLUMNS = [
    "is_last_checkpoint",
    "side_to_move_next",
    "white_to_move_next",
    "duplicate_ply_checkpoint",
]

_LABEL_COLUMNS = [
    "result_class",
    "white_result_numeric",
]

_SLICE_COLUMNS = [
    "game_id",
    "termination",
    "is_time_forfeit",
    "has_eval",
]

_DROPPED_COLUMNS = _FORBIDDEN_COLS[:]  # same list

_FORBIDDEN_LEAKAGE_COLUMNS = [
    "result_class (as a feature)",
    "white_result_numeric (as a feature)",
    "termination (as a feature)",
    "is_time_forfeit (as a feature)",
    "n_plies_total",
    "white_rating_diff",
    "black_rating_diff",
    "accepted_basic",
    "accepted_eval",
    "rejection_reason",
    "game_id (as a feature)",
]

_NULLABLE_EVAL_COLUMNS = [
    "eval_cp",
    "eval_cp_clipped",
    "eval_mate",
    "eval_mate_abs",
    "eval_white_winning",
]


def build_feature_metadata(
    df_broad: pl.DataFrame,
    df_eval: pl.DataFrame,
    input_paths: dict,
    output_paths: dict,
    version_tag: str,
) -> dict:
    """Build the feature metadata sidecar dict."""
    clock_anomaly_broad = int(df_broad["clock_anomaly"].sum()) if "clock_anomaly" in df_broad.columns else 0
    clock_anomaly_eval = int(df_eval["clock_anomaly"].sum()) if "clock_anomaly" in df_eval.columns else 0
    dup_broad = int(df_broad["duplicate_ply_checkpoint"].sum()) if "duplicate_ply_checkpoint" in df_broad.columns else 0
    dup_eval = int(df_eval["duplicate_ply_checkpoint"].sum()) if "duplicate_ply_checkpoint" in df_eval.columns else 0

    eval_pct = round(
        100.0 * (df_broad["has_eval"].sum() if "has_eval" in df_broad.columns else 0) / df_broad.height, 2
    ) if df_broad.height > 0 else 0.0

    return {
        "version_tag": version_tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_paths": input_paths,
        "output_paths": output_paths,
        "row_counts": {
            "broad_rows": df_broad.height,
            "eval_rows": df_eval.height,
        },
        "policy": {
            "clock_cap_s": CLOCK_CAP_S,
            "eval_clip_cp": EVAL_CLIP_CP,
            "low_time_thresholds_s": LOW_TIME_THRESHOLDS_S,
            "duplicate_checkpoint_policy": (
                "Rows where (game_id, ply) appears in multiple rows are flagged "
                "by duplicate_ply_checkpoint=True. Rows are NOT dropped. "
                "Callers must decide deduplication strategy per experiment."
            ),
            "last_checkpoint_policy": (
                "The 'last' checkpoint is the final ply of any game. It is "
                "included in the feature table and flagged by is_last_checkpoint=True. "
                "It is a caution column: semantically distinct from numbered checkpoints."
            ),
            "leakage_policy_summary": (
                "result_class and white_result_numeric are labels only. "
                "termination and n_plies_total are post-game info and forbidden as features. "
                "white_rating_diff and black_rating_diff are post-game rating changes and forbidden. "
                "game_id is a group/split key only."
            ),
        },
        "default_predictive_features": _DEFAULT_PREDICTIVE_FEATURES,
        "eval_predictive_features": _EVAL_PREDICTIVE_FEATURES,
        "caution_columns": _CAUTION_COLUMNS,
        "label_columns": _LABEL_COLUMNS,
        "slice_columns": _SLICE_COLUMNS,
        "metadata_columns": [],
        "dropped_columns": _DROPPED_COLUMNS,
        "nullable_eval_columns": _NULLABLE_EVAL_COLUMNS,
        "forbidden_leakage_columns": _FORBIDDEN_LEAKAGE_COLUMNS,
        "clock_anomaly_count_broad": clock_anomaly_broad,
        "clock_anomaly_count_eval": clock_anomaly_eval,
        "duplicate_ply_checkpoint_count_broad": dup_broad,
        "duplicate_ply_checkpoint_count_eval": dup_eval,
        "eval_coverage_broad_pct": eval_pct,
    }


# ---------------------------------------------------------------------------
# Post-feature validation checks
# ---------------------------------------------------------------------------

def _validation_checks(
    df_broad_in: pl.DataFrame,
    df_eval_in: pl.DataFrame,
    df_broad_out: pl.DataFrame,
    df_eval_out: pl.DataFrame,
) -> dict[str, bool]:
    """Run post-feature validation. Returns {check_name: passed}."""
    checks: dict[str, bool] = {}

    # Row counts preserved
    checks["broad_row_count_preserved"] = df_broad_out.height == df_broad_in.height
    checks["eval_row_count_preserved"] = df_eval_out.height == df_eval_in.height

    # Forbidden columns absent
    for col in ["n_plies_total", "ply", "white_rating_diff", "black_rating_diff",
                "accepted_basic", "accepted_eval", "rejection_reason"]:
        checks[f"forbidden_absent_{col}"] = col not in df_broad_out.columns

    # Username columns absent
    bad_cols = {"white", "black", "White", "Black", "white_name", "black_name"}
    checks["no_username_cols_broad"] = not bool(bad_cols & set(df_broad_out.columns))
    checks["no_username_cols_eval"] = not bool(bad_cols & set(df_eval_out.columns))

    # Clock fractions in [0, 1]
    if df_broad_out.height > 0:
        wf = df_broad_out["white_clock_frac"]
        bf = df_broad_out["black_clock_frac"]
        checks["white_clock_frac_in_0_1"] = bool((wf.min() >= 0.0) and (wf.max() <= 1.0))
        checks["black_clock_frac_in_0_1"] = bool((bf.min() >= 0.0) and (bf.max() <= 1.0))
    else:
        checks["white_clock_frac_in_0_1"] = True
        checks["black_clock_frac_in_0_1"] = True

    # eval_cp_clipped in [-1000, +1000]
    ec = df_broad_out["eval_cp_clipped"].drop_nulls()
    if len(ec) > 0:
        checks["eval_cp_clipped_in_bounds"] = bool((ec.min() >= -EVAL_CLIP_CP) and (ec.max() <= EVAL_CLIP_CP))
    else:
        checks["eval_cp_clipped_in_bounds"] = True

    # is_mate_eval == True iff eval_mate is not null
    if df_broad_out.height > 0:
        mate_flag = df_broad_out["is_mate_eval"]
        mate_expected = df_broad_out["eval_mate"].is_not_null()
        checks["is_mate_eval_consistent"] = bool((mate_flag == mate_expected).all())
    else:
        checks["is_mate_eval_consistent"] = True

    # checkpoint_index in {0,1,2,3,4}
    if df_broad_out.height > 0:
        ci = df_broad_out["checkpoint_index"].drop_nulls()
        valid_ci = {0, 1, 2, 3, 4}
        checks["checkpoint_index_valid"] = all(v in valid_ci for v in ci.to_list())
    else:
        checks["checkpoint_index_valid"] = True

    # phase_index in {0,1,2}
    if df_broad_out.height > 0:
        pi = df_broad_out["phase_index"].drop_nulls()
        valid_pi = {0, 1, 2}
        checks["phase_index_valid"] = all(v in valid_pi for v in pi.to_list())
    else:
        checks["phase_index_valid"] = True

    # is_last_checkpoint consistent
    if df_broad_out.height > 0:
        ilc = df_broad_out["is_last_checkpoint"]
        expected = df_broad_out["selected_position_type"] == "last"
        checks["is_last_checkpoint_consistent"] = bool((ilc == expected).all())
    else:
        checks["is_last_checkpoint_consistent"] = True

    # Eval table has no null eval_cp
    if df_eval_out.height > 0:
        checks["eval_table_no_null_eval_cp"] = df_eval_out["eval_cp"].null_count() == 0
    else:
        checks["eval_table_no_null_eval_cp"] = True

    return checks


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(
    df_broad_in: pl.DataFrame,
    df_broad_out: pl.DataFrame,
    df_eval_out: pl.DataFrame,
    metadata: dict,
    checks: dict[str, bool],
) -> None:
    """Print a concise feature engineering summary to stdout."""
    n_added = len(df_broad_out.columns) - (len(df_broad_in.columns) - len([c for c in _FORBIDDEN_COLS if c in df_broad_in.columns]))

    print()
    print("=" * 60)
    print("  Feature Engineering Summary")
    print("=" * 60)
    print(f"  Broad rows (in):           {df_broad_in.height:>8,}")
    print(f"  Broad rows (out):          {df_broad_out.height:>8,}")
    print(f"  Eval rows (out):           {df_eval_out.height:>8,}")
    print(f"  Columns added (approx):    {n_added:>8,}")
    print(f"  Clock anomalies (broad):   {metadata['clock_anomaly_count_broad']:>8,}")
    print(f"  Duplicate ply checkpoints: {metadata['duplicate_ply_checkpoint_count_broad']:>8,}")
    print(f"  Eval coverage (broad):     {metadata['eval_coverage_broad_pct']:>7.1f}%")
    print()
    print(f"  Broad output columns ({len(df_broad_out.columns)}):")
    for col in sorted(df_broad_out.columns):
        print(f"    {col}")
    print()
    print("  Data integrity checks:")
    all_pass = True
    for name, passed in sorted(checks.items()):
        status = "PASS" if passed else "FAIL"
        print(f"    {name:<48} {status}")
        if not passed:
            all_pass = False
    print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES — see above'}")
    print()
    print("  Output paths:")
    for label, path in metadata.get("output_paths", {}).items():
        print(f"    {label:<32} {path}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply v1 feature engineering to cleaned position Parquet files "
            "and write feature tables to data/processed/ (gitignored)."
        )
    )
    parser.add_argument(
        "--positions-broad",
        required=True,
        help="Path to ten_zero_positions_broad_*.parquet",
    )
    parser.add_argument(
        "--positions-eval",
        required=True,
        help="Path to ten_zero_positions_eval_*.parquet",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for feature outputs (e.g. data/processed)",
    )
    parser.add_argument(
        "--version-tag",
        required=True,
        help="Version suffix for output filenames (e.g. 2024_09_25k_v1)",
    )
    args = parser.parse_args(argv)

    tag = args.version_tag
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    broad_out_path = out_dir / f"feature_positions_broad_{tag}.parquet"
    eval_out_path = out_dir / f"feature_positions_eval_{tag}.parquet"
    metadata_out_path = out_dir / f"feature_metadata_{tag}.json"

    print(f"Reading broad positions: {args.positions_broad}", file=sys.stderr)
    print(f"Reading eval positions:  {args.positions_eval}", file=sys.stderr)
    print(f"Output dir:              {out_dir}", file=sys.stderr)
    print(f"Version tag:             {tag}", file=sys.stderr)

    try:
        df_broad_in = pl.read_parquet(args.positions_broad)
        df_eval_in = pl.read_parquet(args.positions_eval)
    except Exception as e:
        print(f"ERROR reading inputs: {e}", file=sys.stderr)
        return 1

    df_broad_out = build_feature_table(df_broad_in)
    df_eval_out = build_feature_table(df_eval_in)

    df_broad_out.write_parquet(str(broad_out_path))
    df_eval_out.write_parquet(str(eval_out_path))

    input_paths = {
        "positions_broad": args.positions_broad,
        "positions_eval": args.positions_eval,
    }
    output_paths = {
        "feature_positions_broad": str(broad_out_path),
        "feature_positions_eval": str(eval_out_path),
        "metadata": str(metadata_out_path),
    }
    metadata = build_feature_metadata(
        df_broad=df_broad_out,
        df_eval=df_eval_out,
        input_paths=input_paths,
        output_paths=output_paths,
        version_tag=tag,
    )
    with open(metadata_out_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    checks = _validation_checks(df_broad_in, df_eval_in, df_broad_out, df_eval_out)
    _print_summary(df_broad_in, df_broad_out, df_eval_out, metadata, checks)

    n_failures = sum(1 for v in checks.values() if not v)
    if n_failures > 0:
        print(f"WARNING: {n_failures} validation check(s) failed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
