"""
cleaning.py — v1 cleaning rules for chess-MHSUC pipeline.

Applies post-parser cleaning filters to produce three local-only datasets
under data/processed/ (gitignored):

  ten_zero_game_records_{tag}.parquet        — clean game-level records
  ten_zero_positions_broad_{tag}.parquet     — all checkpoints, eval nullable
  ten_zero_positions_eval_{tag}.parquet      — eval-gated subset (has_eval=True)
  cleaning_metadata_{tag}.json               — counts, filters, version

v1 cleaning rules (from Ticket 3.1A audit):

  Game-level:
    - accepted_basic == True              (drops 5 rejected zero-ply abandoned games)
    - termination != "Abandoned"          (drops accepted 1-ply abandoned games)
    - Time forfeit games RETAINED         (core to research question)
    - missing eval RETAINED               (eval is nullable by design)
    - null rating_diff RETAINED           (not a v1 feature)
    - no new label columns added
    - no feature engineering

  Position-level (broad):
    - game_id in clean game records       (inherits game-level exclusions)
    - eval_cp nullable                    (eval is nullable by design)
    - clock anomalies retained            (flagging is feature engineering work)
    - last checkpoint duplicates retained (deduplication is caller responsibility)
    - eval sentinel ±10000 retained       (valid forced-mate positions)

  Position-level (eval-gated):
    - has_eval == True
    - eval_cp and eval_mate unchanged
    - sentinel rows retained

Usage:
    PYTHONPATH=src python -m chess_mhsuc.cleaning \\
        --game-records data/interim/game_records_2024_09_25k_v1.parquet \\
        --position-records data/interim/position_records_2024_09_25k_v1.parquet \\
        --output-dir data/processed \\
        --version-tag 2024_09_25k_v1

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
# Pure cleaning functions
# ---------------------------------------------------------------------------

def clean_game_records(df_games: pl.DataFrame) -> pl.DataFrame:
    """
    Apply v1 game-level cleaning filters.

    Keeps:
      - accepted_basic == True
      - termination != "Abandoned"

    Retains explicitly:
      - Termination "Time forfeit"    (central to the research question)
      - accepted_eval == False        (eval is nullable by design)
      - null white_rating_diff / black_rating_diff
    """
    return df_games.filter(
        (pl.col("accepted_basic") == True)
        & (pl.col("termination") != "Abandoned")
    )


def clean_position_records(
    df_positions: pl.DataFrame,
    df_clean_games: pl.DataFrame,
) -> pl.DataFrame:
    """
    Keep only position rows whose game_id appears in df_clean_games.

    No additional filtering is applied:
      - eval_cp is left nullable
      - clock anomalies are retained
      - last checkpoint duplicates are retained
      - eval sentinel ±10000 rows are retained
      - time-forfeit position rows are retained
    """
    return df_positions.join(
        df_clean_games.select("game_id"),
        on="game_id",
        how="inner",
    )


def filter_eval_positions(df_positions: pl.DataFrame) -> pl.DataFrame:
    """
    Return the eval-gated position subset: has_eval == True.

    eval_cp and eval_mate are not altered.
    Sentinel rows (eval_cp == ±10000) are retained.
    """
    return df_positions.filter(pl.col("has_eval") == True)


def build_cleaning_metadata(
    df_games_raw: pl.DataFrame,
    df_games_clean: pl.DataFrame,
    df_positions_raw: pl.DataFrame,
    df_positions_broad: pl.DataFrame,
    df_positions_eval: pl.DataFrame,
    input_paths: dict,
    output_paths: dict,
    version_tag: str,
) -> dict:
    """Build the cleaning metadata sidecar dict."""
    n_raw = df_games_raw.height
    n_clean = df_games_clean.height

    n_not_accepted = df_games_raw.filter(
        pl.col("accepted_basic") == False
    ).height
    n_abandoned_accepted = df_games_raw.filter(
        (pl.col("accepted_basic") == True)
        & (pl.col("termination") == "Abandoned")
    ).height
    n_time_forfeit = df_games_clean.filter(
        pl.col("termination") == "Time forfeit"
    ).height

    # Result distribution (clean games, non-null result_class)
    result_dist: dict = {}
    if n_clean > 0:
        result_dist = dict(
            df_games_clean
            .filter(pl.col("result_class").is_not_null())
            .group_by("result_class")
            .agg(pl.len().alias("n"))
            .sort("result_class")
            .rows()
        )

    # Termination distribution (clean games)
    term_dist: dict = {}
    if n_clean > 0:
        term_dist = dict(
            df_games_clean
            .group_by("termination")
            .agg(pl.len().alias("n"))
            .sort("termination")
            .rows()
        )

    # Checkpoint distribution (broad positions)
    n_broad = df_positions_broad.height
    checkpoint_dist: dict = {}
    if n_broad > 0:
        checkpoint_dist = dict(
            df_positions_broad
            .group_by("selected_position_type")
            .agg(pl.len().alias("n"))
            .sort("selected_position_type")
            .rows()
        )

    # Eval coverage in broad positions
    n_broad_eval = (
        df_positions_broad.filter(pl.col("has_eval") == True).height
        if n_broad > 0 else 0
    )
    eval_pct = round(100 * n_broad_eval / n_broad, 2) if n_broad > 0 else 0.0

    return {
        "version_tag": version_tag,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_paths": input_paths,
        "output_paths": output_paths,
        "cleaning_rules": {
            "game_level": [
                "accepted_basic == True",
                "termination != 'Abandoned'",
            ],
            "position_level_broad": [
                "game_id in clean_game_records",
            ],
            "position_level_eval": [
                "has_eval == True",
            ],
        },
        "raw_game_rows": n_raw,
        "clean_game_rows": n_clean,
        "excluded_game_rows": n_raw - n_clean,
        "excluded_not_accepted_basic": n_not_accepted,
        "excluded_abandoned_accepted": n_abandoned_accepted,
        "retained_time_forfeit": n_time_forfeit,
        "raw_position_rows": df_positions_raw.height,
        "broad_position_rows": n_broad,
        "eval_position_rows": df_positions_eval.height,
        "eval_coverage_broad_pct": eval_pct,
        "result_distribution_clean": result_dist,
        "termination_distribution_clean": term_dist,
        "checkpoint_distribution_broad": checkpoint_dist,
    }


# ---------------------------------------------------------------------------
# Post-clean validation checks
# ---------------------------------------------------------------------------

def _validation_checks(
    df_games_clean: pl.DataFrame,
    df_positions_broad: pl.DataFrame,
    df_positions_eval: pl.DataFrame,
) -> dict[str, bool]:
    """Run post-clean data integrity checks. Returns {check_name: passed}."""
    checks: dict[str, bool] = {}

    bad_cols = {"white", "black", "White", "Black", "white_name", "black_name"}
    checks["no_username_cols_games"] = not bool(bad_cols & set(df_games_clean.columns))
    checks["no_username_cols_broad"] = not bool(bad_cols & set(df_positions_broad.columns))
    checks["no_username_cols_eval"] = not bool(bad_cols & set(df_positions_eval.columns))

    if df_games_clean.height > 0:
        checks["no_rejected_in_clean"] = (
            int(df_games_clean["accepted_basic"].sum()) == df_games_clean.height
        )
        checks["no_abandoned_in_clean"] = (
            df_games_clean.filter(pl.col("termination") == "Abandoned").height == 0
        )
    else:
        checks["no_rejected_in_clean"] = True
        checks["no_abandoned_in_clean"] = True

    if df_positions_broad.height > 0:
        clean_ids = set(df_games_clean["game_id"].to_list())
        pos_ids = set(df_positions_broad["game_id"].to_list())
        checks["broad_game_ids_in_clean"] = pos_ids.issubset(clean_ids)
    else:
        checks["broad_game_ids_in_clean"] = True

    if df_positions_eval.height > 0:
        checks["eval_positions_all_have_eval"] = (
            int(df_positions_eval["has_eval"].sum()) == df_positions_eval.height
        )
    else:
        checks["eval_positions_all_have_eval"] = True

    checks["eval_subset_lte_broad"] = (
        df_positions_eval.height <= df_positions_broad.height
    )

    return checks


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(metadata: dict, checks: dict[str, bool]) -> None:
    """Print a concise cleaning summary to stdout."""
    print()
    print("=" * 60)
    print("  Cleaning Summary")
    print("=" * 60)
    print(f"  Raw game rows:             {metadata['raw_game_rows']:>8,}")
    print(f"  Clean game rows:           {metadata['clean_game_rows']:>8,}")
    print(f"  Excluded (not accepted):   {metadata['excluded_not_accepted_basic']:>8,}")
    print(f"  Excluded (abandoned):      {metadata['excluded_abandoned_accepted']:>8,}")
    print(f"  Retained time forfeits:    {metadata['retained_time_forfeit']:>8,}")
    print()
    print(f"  Raw position rows:         {metadata['raw_position_rows']:>8,}")
    print(f"  Broad position rows:       {metadata['broad_position_rows']:>8,}")
    print(f"  Eval position rows:        {metadata['eval_position_rows']:>8,}")
    print(f"  Eval coverage (broad):     {metadata['eval_coverage_broad_pct']:>7.1f}%")

    if metadata["result_distribution_clean"]:
        print()
        print("  Result distribution (clean games):")
        for k, v in sorted(metadata["result_distribution_clean"].items()):
            print(f"    {k:<24} {v:>6,}")

    if metadata["termination_distribution_clean"]:
        print()
        print("  Termination distribution (clean games):")
        for k, v in sorted(metadata["termination_distribution_clean"].items()):
            print(f"    {k:<24} {v:>6,}")

    if metadata["checkpoint_distribution_broad"]:
        print()
        print("  Checkpoint distribution (broad positions):")
        for k, v in sorted(metadata["checkpoint_distribution_broad"].items()):
            print(f"    {k:<24} {v:>6,}")

    print()
    print("  Data integrity checks:")
    all_pass = True
    for name, passed in sorted(checks.items()):
        status = "PASS" if passed else "FAIL"
        print(f"    {name:<42} {status}")
        if not passed:
            all_pass = False
    print(f"  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES — see above'}")

    print()
    print("  Output paths:")
    for label, path in metadata.get("output_paths", {}).items():
        print(f"    {label:<28} {path}")
    print("=" * 60)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apply v1 cleaning rules to interim Parquet outputs and write "
            "processed datasets to data/processed/ (gitignored)."
        )
    )
    parser.add_argument(
        "--game-records",
        required=True,
        help="Path to interim game_records Parquet file",
    )
    parser.add_argument(
        "--position-records",
        required=True,
        help="Path to interim position_records Parquet file",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for processed outputs (e.g. data/processed)",
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

    game_records_out = out_dir / f"ten_zero_game_records_{tag}.parquet"
    positions_broad_out = out_dir / f"ten_zero_positions_broad_{tag}.parquet"
    positions_eval_out = out_dir / f"ten_zero_positions_eval_{tag}.parquet"
    metadata_out = out_dir / f"cleaning_metadata_{tag}.json"

    print(f"Reading game records:     {args.game_records}", file=sys.stderr)
    print(f"Reading position records: {args.position_records}", file=sys.stderr)
    print(f"Output dir:               {out_dir}", file=sys.stderr)
    print(f"Version tag:              {tag}", file=sys.stderr)

    try:
        df_games_raw = pl.read_parquet(args.game_records)
        df_positions_raw = pl.read_parquet(args.position_records)
    except Exception as e:
        print(f"ERROR reading inputs: {e}", file=sys.stderr)
        return 1

    # Apply cleaning
    df_games_clean = clean_game_records(df_games_raw)
    df_positions_broad = clean_position_records(df_positions_raw, df_games_clean)
    df_positions_eval = filter_eval_positions(df_positions_broad)

    # Write processed outputs
    df_games_clean.write_parquet(str(game_records_out))
    df_positions_broad.write_parquet(str(positions_broad_out))
    df_positions_eval.write_parquet(str(positions_eval_out))

    # Build and write metadata sidecar
    input_paths = {
        "game_records": str(args.game_records),
        "position_records": str(args.position_records),
    }
    output_paths = {
        "game_records_clean": str(game_records_out),
        "positions_broad": str(positions_broad_out),
        "positions_eval": str(positions_eval_out),
        "metadata": str(metadata_out),
    }
    metadata = build_cleaning_metadata(
        df_games_raw=df_games_raw,
        df_games_clean=df_games_clean,
        df_positions_raw=df_positions_raw,
        df_positions_broad=df_positions_broad,
        df_positions_eval=df_positions_eval,
        input_paths=input_paths,
        output_paths=output_paths,
        version_tag=tag,
    )
    with open(metadata_out, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")

    # Validate and print summary
    checks = _validation_checks(df_games_clean, df_positions_broad, df_positions_eval)
    _print_summary(metadata, checks)

    n_failures = sum(1 for v in checks.values() if not v)
    if n_failures > 0:
        print(f"WARNING: {n_failures} validation check(s) failed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
