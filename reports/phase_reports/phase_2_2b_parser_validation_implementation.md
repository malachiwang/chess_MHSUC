# Phase Report: Ticket 2.2B — Parser Validation + Capped Real-Data Loading Implementation

**Labels:** DATA / TEST | D3 | IMPLEMENTATION
**Date:** 2026-06-05
**Status:** Complete. Real-data validation run executed; one check corrected post-run.

---

## 1. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/run_parser.py` | Created — streaming CLI parser |
| `tests/test_run_parser.py` | Created — 34 tests |
| `ROADMAP.md` | Modified — marked 2.2A and 2.2B complete |

No files under `data/` were touched.

---

## 2. run_parser.py Design Summary

### Purpose

Capped streaming parser for Lichess monthly `.pgn.zst` archives. Streams
directly from a URL without full decompression to disk. Writes two local-only
Parquet tables plus a metadata JSON sidecar to `data/interim/` (gitignored).

### Architecture

```text
URL (.pgn.zst)
  → urllib.request (streaming HTTP)
  → ZstdDecompressor.stream_reader()
  → io.BufferedReader (128 KiB buffer)
  → io.TextIOWrapper (UTF-8, errors=replace)
  → chess.pgn.read_game() loop
      → TimeControl pre-filter (skip non-600+0 cheaply)
      → extract_game_record()
      → [if accepted_basic] extract_ply_records() + select_checkpoints()
      → per-game exception handling (log + continue)
  → _records_to_df() with explicit Parquet schemas
  → write_outputs() → game_records_{stem}.parquet
                     → position_records_{stem}.parquet
                     → parser_validation_{stem}_metadata.json
  → validation_checks() (11 checks)
  → print_validation_summary()
```

### Key design decisions

**TC pre-filter**: `game.headers.get("TimeControl", "")` checked before any ply
extraction. The 2024-09 scan (Ticket 1.1B) found ~90% of raw games are non-600+0;
skipping them avoids expensive `board()` replay for the vast majority of games.

**Per-game exception handling**: any exception in `extract_game_record`,
`extract_ply_records`, or `select_checkpoints` is caught, logged to `error_log`,
and skipped. The run does not abort on a single bad game.

**Explicit Parquet schemas**: `GAME_RECORD_SCHEMA` and `POSITION_RECORD_SCHEMA`
dicts are passed to `pl.from_dicts(..., schema=schema)`. This prevents polars from
inferring `Null` dtype on columns that happen to be all-None in a small sample.

**max-games required**: `--max-games` is a required CLI argument. There is no
unbounded default. Recommended first run: 25,000 raw games.

**max-accepted optional**: `--max-accepted` provides a secondary cap on
`accepted_basic` games. Useful to bound ply-extraction work when 600+0 rate is
known (~10%). If not set, the raw-games cap is the only limit.

### CLI

```
python -m chess_mhsuc.run_parser \
    --url <url>              # .pgn.zst URL (required)
    --max-games <N>          # raw games cap (required)
    --max-accepted <N>       # accepted_basic cap (optional)
    --source-file <name>     # archive filename for metadata (required)
    --output-dir <dir>       # output directory (required)
    --version-tag <tag>      # filename suffix (required)
```

### Output files

Named `{month}_{cap}_{tag}`, e.g. `2024_09_25k_v1`:

| File | Contents |
|------|----------|
| `game_records_{stem}.parquet` | One row per 600+0 game (accepted + rejected) |
| `position_records_{stem}.parquet` | One row per checkpoint from accepted games |
| `parser_validation_{stem}_metadata.json` | Counts, distributions, elapsed time |

### Validation checks (11)

| Check | Tests |
|-------|-------|
| `no_username_cols_games` | white/black/White/Black absent from game DF |
| `no_username_cols_positions` | same for positions DF |
| `game_id_unique` | no duplicate game_ids |
| `result_class_values_valid` | only WHITE_WIN, DRAW, BLACK_WIN |
| `rejection_reason_values_valid` | only known rejection strings |
| `accepted_basic_n_plies_positive` | n_plies > 0 for accepted_basic rows only |
| `clock_values_non_negative` | white/black_clock_s ≥ 0 |
| `eval_cp_in_bounds` | eval_cp ∈ [−10000, 10000] |
| `eval_sentinel_consistent` | eval_cp = ±10000 ↔ eval_mate is not null |
| `phase_values_valid` | only opening/middlegame/endgame |
| `checkpoint_type_values_valid` | only move_10/20/30/40/last |

---

## 3. Tests (test_run_parser.py)

### Test suite summary

| Class | Tests | What is covered |
|-------|-------|-----------------|
| `TestMakeStem` | 4 | stem generation: standard, None source, non-round cap, 10k |
| `TestRecordsToDf` | 3 | empty GameRecord schema, empty PositionRecord schema, fixture |
| `TestStreamAndParseFixture` | 7 | 1 game, accepted_basic, 5 checkpoints, no errors, counters, URL, no usernames |
| `TestStreamAndParseFilter` | 5 | non-600+0 skip, mixed TC, max_games cap, max_accepted cap, no cap |
| `TestStreamAndParseExceptionHandling` | 2 | exception doesn't crash run, error_log keys |
| `TestValidationChecks` | 7 | all pass for fixture, all pass empty, username fails ×2, dup IDs, bad result class, sentinel |
| `TestWriteOutputs` | 6 | files exist, game DF columns, position DF columns, no usernames, metadata keys, count match |

**Total: 34 tests, all passing.**

### Full suite results

```bash
.venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py tests/test_run_parser.py -v
```

**163 passed in 1.17s**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_source_scan.py` | 19 | All passed (no regression) |
| `test_parse_pgn.py` | 110 | All passed (no regression) |
| `test_run_parser.py` | 34 | All passed |

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 4. Real-Data Validation Run Results

Run command:

```bash
python -m chess_mhsuc.run_parser \
    --url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst \
    --max-games 25000 \
    --max-accepted 2500 \
    --source-file lichess_db_standard_rated_2024-09.pgn.zst \
    --output-dir data/interim \
    --version-tag v1
```

The run completed successfully. Output written to `data/interim/` (gitignored).

### Post-run validation check correction

The initial run produced one failed validation check: `n_plies_positive`.

Manual inspection revealed exactly 5 bad rows, all with:
- `accepted_basic = False`
- `rejection_reason = "missing_clock"`
- `termination = "Abandoned"`
- `n_plies = 0`

These are real games that were abandoned before any moves were recorded. The
parser correctly sets `n_plies = 0` for such games and correctly rejects them.
All `accepted_basic = True` games had `n_plies ≥ 1`.

**Fix applied**: renamed check to `accepted_basic_n_plies_positive` and scoped
it to `accepted_basic` rows only using `df_games.filter(pl.col("accepted_basic"))`.
No parser logic or data output was changed. The fix is in `validation_checks()`
only.

After the fix all 11 validation checks pass. Post-safety check confirmed no
data files were staged (`git status --ignored`).

---

## 5. Data Safety Confirmation

- No files under `data/` were created, modified, or staged.
- No `.pgn`, `.parquet`, `.csv`, `.db`, or `.pkl` files were created outside
  `tests/fixtures/`.
- No network commands were run.
- The real-data validation run (Section 4) has not been executed — it is
  pending explicit user action.

---

## 6. Known Risks / Limitations

**R1 — Validation run not yet executed**
The parser has not been run on real Lichess data in this session. All tests
use synthetic PGN only. Real-data behaviour (eval annotation edge cases, rare
PGN header variants, clock anomalies) is not yet confirmed.

**R2 — Eval carry-forward not re-tested on real data**
The parser stores `None` for plies without `%eval`. Real archives may have
mid-game missing evals more frequently than expected.

**R3 — Rate variation by month**
The 1.1B scan used 2024-09. Other monthly archives may have different 600+0
rates, eval availability, or header formatting.

**R4 — Stream interruption**
If the download is interrupted mid-stream, the output files will contain a
partial result. The metadata will still record accurate counts for what was
written, but the run should be re-executed with fresh output paths.

---

## 7. Suggested Next Step

**Run the validation command in Section 4.** If all 11 checks pass:

- Ticket 2.2B is complete.
- Proceed to Phase 3: Ticket 3.1A (Cleaning and Labeling Audit).

If validation checks fail or parse error rate > 1%:
- Investigate specific failures from the error log.
- Fix in a targeted Ticket 2.2C.

---

## Suggested staging for commit

```bash
git add src/chess_mhsuc/run_parser.py
git add tests/test_run_parser.py
git add ROADMAP.md
git add reports/phase_reports/phase_2_2b_parser_validation_implementation.md
git commit -m "Ticket 2.2B: streaming run_parser, 34 tests (163 total passing)"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
