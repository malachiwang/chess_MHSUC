# Phase Report: Ticket 3.2B — Feature Engineering Implementation

**Labels:** DATA / ML / ANALYSIS | D3 | IMPLEMENTATION
**Date:** 2026-06-06
**Status:** Complete. Real-data run executed; all 19 validation checks passed.

---

## 1. Ticket Title and Labels

Ticket 3.2B — Feature Engineering Implementation
DATA / ML / ANALYSIS | D3 | IMPLEMENTATION | Conservative

---

## 2. ELI5 / TLDR Summary

This ticket creates a feature engineering module (`features.py`) that reads the
cleaned position Parquet files from Phase 3.1B and adds derived columns needed
for modeling, while dropping post-game leakage columns. The output is two feature
tables (broad: all positions, eval: eval-annotated only) plus a metadata JSON
documenting which columns are features, labels, slice columns, or forbidden.

No modeling, splitting, or calibration is done here. Features are computed from
information available at the checkpoint position.

---

## 3. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/features.py` | Created — feature functions + CLI |
| `tests/test_features.py` | Created — 84 tests |
| `ROADMAP.md` | Modified — marked 3.2A and 3.2B complete |

No files under `data/` were staged.

---

## 4. Feature Policy Implemented

### Added columns (23 new columns)

| Category | Columns |
|----------|---------|
| Rating | `avg_elo` |
| Clock (capped) | `white_clock_s_capped`, `black_clock_s_capped` |
| Clock (normalized) | `white_clock_frac`, `black_clock_frac`, `clock_diff_frac` |
| Clock (low-time flags) | `white_low_60`, `black_low_60`, `white_low_30`, `black_low_30`, `white_low_10`, `black_low_10` |
| Clock (anomaly) | `clock_anomaly` |
| Eval | `eval_cp_clipped`, `is_mate_eval`, `eval_mate_abs`, `eval_white_winning` |
| Position | `is_last_checkpoint`, `white_to_move_next`, `checkpoint_index`, `phase_index` |
| Slice | `is_time_forfeit` |
| Flag | `duplicate_ply_checkpoint` |

### Dropped columns (2 actually present in input)

- `n_plies_total` — post-game leakage (total game length unknown at checkpoint time)
- `ply` — redundant with `move_number`; used internally by `add_duplicate_checkpoint_flag` before drop

The `drop_forbidden_columns` function handles 15 possible forbidden columns with
"if present" logic; the remainder (white_rating_diff, black_rating_diff, etc.)
are not in the PositionRecord schema and are handled silently.

### Column categorization (output table, 40 columns)

| Category | Columns |
|----------|---------|
| Default predictive features (25) | white_elo, black_elo, elo_diff, avg_elo, white_clock_s, black_clock_s, clock_diff_s, white_clock_s_capped, black_clock_s_capped, white_clock_frac, black_clock_frac, clock_diff_frac, white_low_60/30/10, black_low_60/30/10, clock_anomaly, selected_position_type, move_number, phase, checkpoint_index, phase_index |
| Eval predictive features (6) | eval_cp, eval_cp_clipped, eval_mate, is_mate_eval, eval_mate_abs, eval_white_winning |
| Caution columns (4) | is_last_checkpoint, side_to_move_next, white_to_move_next, duplicate_ply_checkpoint |
| Labels (2) | result_class, white_result_numeric |
| Slice columns (4) | game_id, termination, is_time_forfeit, has_eval |
| Dropped from input | n_plies_total, ply (and others not present in position schema) |

### Key design details

- **Clock capping**: `white/black_clock_s_capped = min(raw, 600)`. Capped values used for fracs and low-time flags. Raw values preserved. Anomaly rows (7 total) flagged but not excluded.
- **Eval clipping**: `eval_cp_clipped` clips non-null eval_cp to ±1,000. Mate sentinels (±10,000) → ±1,000. Raw eval_cp and eval_mate preserved. Missing eval stays null — never imputed.
- **Duplicate checkpoint flag**: Groups by (game_id, ply) after `add_position_features` but before `drop_forbidden_columns`. 83 games produce 2 rows at the same ply → 166 rows flagged. Rows are NOT dropped.
- **`is_time_forfeit`**: Slice column only. Not a model feature.
- **`has_eval`**: Preserved as metadata/slice. Not in `default_predictive_features` or `eval_predictive_features`.

---

## 5. Leakage Protections Implemented

| Protection | Implementation |
|------------|---------------|
| `result_class` | Retained as label; excluded from all feature lists |
| `white_result_numeric` | Retained as label; excluded from all feature lists |
| `termination` | Retained as slice; excluded from all feature lists |
| `n_plies_total` | Dropped from output table |
| `ply` | Dropped after duplicate flag uses it |
| `white_rating_diff` | Dropped if present |
| `black_rating_diff` | Dropped if present |
| `game_id` | Retained as split key; excluded from predictive feature lists |
| `has_eval` | Retained as slice; excluded from predictive features |
| `is_time_forfeit` | Marked slice only; excluded from predictive features |

The metadata JSON explicitly records `forbidden_leakage_columns` with explanations so
downstream callers know which columns must never be used as model inputs.

---

## 6. Output Artifacts Created (local-only, gitignored)

| File | Rows | Columns |
|------|------|---------|
| `data/processed/feature_positions_broad_2024_09_25k_v1.parquet` | 8,528 | 40 |
| `data/processed/feature_positions_eval_2024_09_25k_v1.parquet` | 1,168 | 40 |
| `data/processed/feature_metadata_2024_09_25k_v1.json` | — | — |

---

## 7. Test Design Summary

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestAddRatingFeatures` | 4 | avg_elo computed, equal ratings, original cols preserved, dtype |
| `TestAddClockFeatures` | 11 | caps >600, anomaly flag, fracs, diff_frac uses capped, zero clock, 45s/15s thresholds, raw preserved |
| `TestAddEvalFeatures` | 16 | null pass-through, within-clip, over-clip, sentinels, is_mate_eval, eval_mate_abs, eval_white_winning, raw preserved |
| `TestAddPositionFeatures` | 6 | is_last_checkpoint, white_to_move_next, checkpoint_index mapping, phase_index mapping, original cols preserved |
| `TestAddSliceColumns` | 3 | is_time_forfeit true/false/mixed |
| `TestAddDuplicateCheckpointFlag` | 4 | detects same game_id/ply, no false positives, different games, no rows dropped |
| `TestDropForbiddenColumns` | 9 | removes n_plies_total/ply/rating_diff, safe if missing, preserves labels/game_id/termination/has_eval |
| `TestBuildFeatureTable` | 7 | row count, added cols, forbidden absent, nullable eval rows kept, is_time_forfeit, labels |
| `TestBuildFeatureMetadata` | 17 | required keys, exclusions from feature lists, caution/label/slice/dropped cols, version tag, anomaly count, dup count |
| `TestFeatureCLI` | 8 | exit code, files created, metadata version_tag, no usernames, no CSV, row counts, forbidden absent |

**Total: 84 new tests.**

---

## 8. Tests / Checks Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py tests/test_features.py -v
```

```bash
PYTHONPATH=src python -m chess_mhsuc.features \
    --positions-broad data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet \
    --positions-eval  data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet \
    --output-dir      data/processed \
    --version-tag     2024_09_25k_v1
```

---

## 9. Test Results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_source_scan.py` | 19 | All passed (no regression) |
| `test_parse_pgn.py` | 110 | All passed (no regression) |
| `test_run_parser.py` | 34 | All passed (no regression) |
| `test_cleaning.py` | 30 | All passed (no regression) |
| `test_features.py` | 84 | All passed |

**277 passed in 1.25s**

**Python:** 3.13.11 | **pytest:** 9.0.3

Bugs found and fixed during implementation:
1. `ec.height` on a Polars Series → fixed to `len(ec)` (Series has no `.height`)
2. `isinstance(dtype, type(pl.Float64))` → fixed to `dtype == pl.Float64`

---

## 10. Feature CLI Command Run

```bash
PYTHONPATH=src python -m chess_mhsuc.features \
    --positions-broad data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet \
    --positions-eval  data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet \
    --output-dir      data/processed \
    --version-tag     2024_09_25k_v1
```

---

## 11. Feature Run Results

```text
Broad rows (in):              8,528
Broad rows (out):             8,528   (no rows dropped)
Eval rows (out):              1,168   (no rows dropped)
Columns added (approx):          23
Clock anomalies (broad):          7   (flagged, not excluded)
Duplicate ply checkpoints:      166   (83 games × 2 rows; flagged, not dropped)
Eval coverage (broad):        13.7%
Output columns (broad):          40
```

All 19 validation checks passed:

```
black_clock_frac_in_0_1                PASS
broad_row_count_preserved              PASS
checkpoint_index_valid                 PASS
eval_cp_clipped_in_bounds              PASS
eval_row_count_preserved               PASS
eval_table_no_null_eval_cp             PASS
forbidden_absent_accepted_basic        PASS
forbidden_absent_accepted_eval         PASS
forbidden_absent_black_rating_diff     PASS
forbidden_absent_n_plies_total         PASS
forbidden_absent_ply                   PASS
forbidden_absent_rejection_reason      PASS
forbidden_absent_white_rating_diff     PASS
is_last_checkpoint_consistent          PASS
is_mate_eval_consistent                PASS
no_username_cols_broad                 PASS
no_username_cols_eval                  PASS
phase_index_valid                      PASS
white_clock_frac_in_0_1               PASS
Overall: ALL PASS
```

---

## 12. Data Safety Confirmation

- `git status` shows only `features.py`, `test_features.py`, `ROADMAP.md`, and this report as untracked/modified.
- `git status --ignored` confirms `data/` is entirely gitignored.
- No data files staged.
- No CSV files created.
- No model files created.

---

## 13. Items Intentionally Deferred

| Item | Reason |
|------|--------|
| Rating bucket columns | Phase 7 subgroup analysis only |
| `either_low_time_*` / `both_low_time_*` composite flags | Derivable from existing flags by caller |
| `elo_bucket` / `phase_bucket` | Phase 7 |
| One-hot encoding of `selected_position_type` / `phase` | Modeling step responsibility |
| Deduplication of duplicate_ply_checkpoint rows | Caller/experiment responsibility; policy documented in metadata |
| Feature selection for specific model experiments | Phase 5 (baselines) |
| Null imputation for any feature | No imputation is v1 policy |
| Feature importance analysis | Phase 6 (GBM) |

---

## 14. Risks / Assumptions

**R1 — Duplicate ply checkpoint handling**
166 rows are flagged. If training code does not deduplicate, these 83 games each
contribute 2 rows at the same ply to whatever checkpoint is duplicated. The
`duplicate_ply_checkpoint` flag allows callers to filter, but this must be
deliberately handled in each experiment.

**R2 — `eval_cp_clipped` for mate positions**
Mate sentinel (±10,000) → ±1,000. This compresses the "forced mate" signal into
the same range as "very winning" positions. `is_mate_eval` and `eval_mate_abs`
provide separate signals for mate-specific features.

**R3 — `side_to_move_next` at numbered checkpoints is constant**
All move_10–move_40 rows have `side_to_move_next == "white"`. This column is only
informative at "last" checkpoints. Both `is_last_checkpoint` and
`white_to_move_next` are caution columns; models should use them deliberately.

**R4 — Clock anomaly rows remain**
7 rows have raw clock_s > 600. Capped values keep model features bounded, but
raw clock columns (`white_clock_s`, `black_clock_s`) are unreliable for these
7 rows. The `clock_anomaly` flag allows callers to exclude them if needed.

**R5 — Eval coverage 13.7% in broad**
The eval-gated table (1,168 rows) is a non-random subset. Models trained on
it may not generalize to all 10+0 games.

---

## 15. Whether Next Ticket Is Safe to Begin

**Yes.** Feature tables are ready for Phase 4 dataset assessment and Phase 5 baseline modeling.

Suggested next ticket: **Ticket 4.1A — Dataset Assessment Audit** (verify dataset
quality before modeling) or **Ticket 5.1A — Modeling Split and Baseline Audit**
(define train/val/test split and baseline model design).

---

## Suggested Staging for Commit

```bash
git add src/chess_mhsuc/features.py
git add tests/test_features.py
git add ROADMAP.md
git add reports/phase_reports/phase_3_2b_feature_engineering_implementation.md
git commit -m "Ticket 3.2B: features.py, 84 tests (277 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
