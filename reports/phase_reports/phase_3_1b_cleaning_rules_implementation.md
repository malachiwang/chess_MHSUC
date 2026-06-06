# Phase Report: Ticket 3.1B — Cleaning Rules Implementation

**Labels:** DATA / TEST | D3 | IMPLEMENTATION
**Date:** 2026-06-06
**Status:** Complete. Real-data run executed; all 8 validation checks passed.

---

## 1. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/cleaning.py` | Created — cleaning functions + CLI |
| `tests/test_cleaning.py` | Created — 30 tests |
| `ROADMAP.md` | Modified — marked 3.1A and 3.1B complete |

No files under `data/` were staged.

---

## 2. Summary of Behavior Added

### cleaning.py

Four pure cleaning functions plus a CLI entry point:

**`clean_game_records(df_games)`**
- Keeps rows where `accepted_basic == True AND termination != "Abandoned"`
- Drops 5 rejected games (accepted_basic=False) and 2 accepted abandoned games
- Retains time forfeit games explicitly (central to research question)
- Retains games missing eval, null rating_diff — no new label columns added

**`clean_position_records(df_positions, df_clean_games)`**
- Inner join on `game_id` — keeps only positions from clean games
- Uses `.join(df_clean_games.select("game_id"), on="game_id", how="inner")`
  (avoids Polars `is_in()` deprecation warning)
- No additional position-level filters; eval_cp nullable, clock anomalies retained

**`filter_eval_positions(df_positions)`**
- Returns the eval-gated subset: `has_eval == True`
- Eval sentinel rows (eval_cp = ±10000) retained

**`build_cleaning_metadata(...)`**
- Returns a dict with 18 keys: version_tag, timestamp_utc, input_paths,
  output_paths, cleaning_rules, row counts, excluded counts, time-forfeit count,
  eval coverage %, and three distributions (result, termination, checkpoint)

**`_validation_checks(df_games_clean, df_positions_broad, df_positions_eval)`**
- 8 integrity checks:
  - `no_username_cols_games` / `_broad` / `_eval`
  - `no_rejected_in_clean`
  - `no_abandoned_in_clean`
  - `broad_game_ids_in_clean`
  - `eval_positions_all_have_eval`
  - `eval_subset_lte_broad`
- Uses Python `set.issubset()` for game_id membership (no Polars `is_in`)

### CLI output naming

```text
ten_zero_game_records_{tag}.parquet
ten_zero_positions_broad_{tag}.parquet
ten_zero_positions_eval_{tag}.parquet
cleaning_metadata_{tag}.json
```

Written to `data/processed/` (gitignored).

---

## 3. Assumptions Made

- `result_class` is already present in the interim game_records (from parser).
  No label columns added in this step.
- Eval nullability is by design — `eval_cp` left as-is.
- Clock anomalies (7 rows with white/black_clock_s > 600) are data artifacts,
  not errors; retained for feature engineering to flag later.
- "Last" checkpoint duplication (83 games where last ply = a numbered checkpoint)
  retained — deduplication is caller's responsibility.

---

## 4. Tests Run

```bash
PYTHONPATH=src .venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py \
    tests/test_run_parser.py tests/test_cleaning.py -v
```

### Test suite summary

| Class | Tests | What is covered |
|-------|-------|-----------------|
| `TestCleanGameRecords` | 7 | keeps normal, keeps time-forfeit, removes abandoned, removes rejected, retains no-eval, retains null rating_diff, mixed batch |
| `TestCleanPositionRecords` | 7 | keeps in-clean-games, removes excluded, retains no-eval, retains last, retains dup last/numbered, retains time-forfeit, mixed game_ids |
| `TestFilterEvalPositions` | 4 | keeps has_eval=True only, retains sentinel ±10000, does not alter eval values, empty input |
| `TestBuildCleaningMetadata` | 7 | required keys, row counts, position counts, distributions are dicts, result dist values, version tag, time forfeit count |
| `TestCleaningCLI` | 5 | exits zero, output files created, metadata has version_tag, no username cols, no CSV files |

**Total: 30 new tests, all passing.**

### Full suite results

| Suite | Tests | Result |
|-------|-------|--------|
| `test_source_scan.py` | 19 | All passed (no regression) |
| `test_parse_pgn.py` | 110 | All passed (no regression) |
| `test_run_parser.py` | 34 | All passed (no regression) |
| `test_cleaning.py` | 30 | All passed |

**193 passed in 1.32s**

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 5. Real-Data Run Results

Run command:

```bash
PYTHONPATH=src python -m chess_mhsuc.cleaning \
    --game-records data/interim/game_records_2024_09_25k_v1.parquet \
    --position-records data/interim/position_records_2024_09_25k_v1.parquet \
    --output-dir data/processed \
    --version-tag 2024_09_25k_v1
```

### Cleaning summary

```text
Raw game rows:                2,467
Clean game rows:              2,460
Excluded (not accepted):          5
Excluded (abandoned):             2
Retained time forfeits:         283

Raw position rows:            8,528
Broad position rows:          8,528
Eval position rows:           1,168
Eval coverage (broad):        13.7%
```

Note: `broad_position_rows == raw_position_rows` because all 8,528 position rows
belong to accepted games. The 7 excluded games (5 rejected + 2 accepted-abandoned)
had no position rows in the interim dataset.

### Result distribution (clean games)

| result_class | count |
|--------------|-------|
| WHITE_WIN    | 1,192 |
| BLACK_WIN    | 1,156 |
| DRAW         |   112 |

### Termination distribution (clean games)

| termination  | count |
|--------------|-------|
| Normal       | 2,177 |
| Time forfeit |   283 |

### Checkpoint distribution (broad positions)

| selected_position_type | count |
|------------------------|-------|
| move_10                | 2,323 |
| move_20                | 1,882 |
| move_30                | 1,266 |
| move_40                |   734 |
| last                   | 2,323 |

### Validation checks

All 8 checks passed:

```
broad_game_ids_in_clean                    PASS
eval_positions_all_have_eval               PASS
eval_subset_lte_broad                      PASS
no_abandoned_in_clean                      PASS
no_rejected_in_clean                       PASS
no_username_cols_broad                     PASS
no_username_cols_eval                      PASS
no_username_cols_games                     PASS
Overall: ALL PASS
```

---

## 6. Data Safety Confirmation

- `git status` shows only `cleaning.py` and `test_cleaning.py` as untracked.
- `git status --ignored` shows `data/` is entirely gitignored.
- No data files staged.

---

## 7. Known Risks / Limitations

**R1 — Broad == raw position count**
All interim positions belong to accepted games, so the broad filter has no effect
here. This is expected for the 25k pilot but may not hold at scale if rejected
games somehow produce position rows (a parser invariant, not a cleaning issue).

**R2 — Eval coverage 13.7%**
Only 1,168 of 8,528 broad positions have eval. Eval-gated modeling will use a
small subset. This is a known constraint from Ticket 1.1B (15.2% eval rate on
accepted games).

**R3 — Clock anomalies retained**
7 position rows have clock_s > 600. These are Lichess PGN artifacts. Low-time
flagging and clock anomaly handling are deferred to Phase 3.2 (feature engineering).

**R4 — "Last" checkpoint duplication**
83 games contribute two rows at the same ply (one "last", one numbered). Retained
by design; callers must deduplicate if needed.

---

## 8. Suggested Next Step

Ticket 3.2A — Feature Engineering Audit.

Define the first feature set:
- Rating features (white_elo, black_elo, elo_diff)
- Clock features (clock_s at each checkpoint, low-time flags)
- Phase features (selected_position_type encoded)
- Eval features (eval_cp, has_eval, eval_mate indicator)
- Termination features (time_forfeit flag)

---

## Suggested staging for commit

```bash
git add src/chess_mhsuc/cleaning.py
git add tests/test_cleaning.py
git add ROADMAP.md
git add reports/phase_reports/phase_3_1b_cleaning_rules_implementation.md
git commit -m "Ticket 3.1B: cleaning.py, 30 tests (193 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
