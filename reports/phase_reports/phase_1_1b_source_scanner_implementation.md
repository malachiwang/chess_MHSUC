# Phase Report: Ticket 1.1B — Source Scanner Implementation

**Labels:** PIPELINE / DATA | D1 | IMPLEMENTATION
**Date:** 2026-06-05
**Status:** Complete

---

## 1. Files Changed

| File | Change type |
|------|------------|
| `src/chess_mhsuc/source_scan.py` | Created — streaming capped scanner module |
| `tests/conftest.py` | Created — sys.path fix for `src/` layout |
| `tests/test_source_scan.py` | Created — 19 synthetic-fixture tests |
| `ROADMAP.md` | Modified — marked 1.1A complete, updated 1.1B description |

Output (local only, Git-ignored):

| File | Change type |
|------|------------|
| `data/interim/source_scan_2024_09_50k_v1.json` | Created — scan summary JSON |

---

## 2. Implementation Summary

### `src/chess_mhsuc/source_scan.py`

Streaming capped scanner. Key design points:

- **HTTP streaming**: `urllib.request.urlopen` (not `requests`) with a `User-Agent` header.
- **Decompression chain**: `ZstdDecompressor().stream_reader(response, closefd=False)` → `io.BufferedReader` → `io.TextIOWrapper(encoding="utf-8", errors="replace")`. The `BufferedReader` wrapping is required because `ZstdDecompressionReader` implements `io.RawIOBase`; `TextIOWrapper` requires a buffered stream.
- **PGN parsing**: `chess.pgn.read_game(text_stream)` reads one game at a time. Loop exits at `None` (EOF) or when `n_total == max_games`.
- **Annotation detection**: `_game_has_annotation(game, tag)` walks `node.variations[0]` checking `node.comment` for `%clk` or `%eval` substrings. No board replay — pure string search.
- **Two-tier pass**:
  - `basic_pass`: TimeControl=600+0 + valid integer WhiteElo/BlackElo + Result in {1-0, 0-1, 1/2-1/2} + `%clk` present.
  - `eval_pass`: `basic_pass` + `%eval` present.
- **Output**: `build_summary()` produces a JSON-serializable dict; `write_summary()` creates parent dirs and writes with `json.dump`.
- **CLI**: `argparse` with `--url`, `--max-games`, `--output`. Entry via `python -m chess_mhsuc.source_scan`.

### `tests/conftest.py`

Inserts `src/` into `sys.path` so pytest can import `chess_mhsuc` without `pyproject.toml` or pip install.

### `tests/test_source_scan.py`

19 tests across 6 synthetic PGN fixtures:

| Fixture | Purpose |
|---------|---------|
| `PGN_600_CLOCK_EVAL` | 600+0, valid Elos, %clk + %eval → eval_pass |
| `PGN_600_CLOCK_ONLY` | 600+0, valid Elos, %clk only → basic_pass |
| `PGN_600_NO_CLOCK` | 600+0, no %clk → no_clock rejection |
| `PGN_WRONG_TC` | 300+0 → not counted as 600+0 |
| `PGN_INVALID_ELO` | WhiteElo="?" → invalid_elo rejection |
| `PGN_INVALID_RESULT` | Result="*" → invalid_result rejection |

Test categories: `_is_valid_elo` parametrized (7), `inspect_game` per-fixture (6), `scan_stream` multi-game (4), `build_summary` (2).

---

## 3. Scan Results

**Source file:** `lichess_db_standard_rated_2024-09.pgn.zst`
**Scan cap:** 50,000 games
**Elapsed:** 324.4s (~154 games/sec)

### Time control filter

| Metric | Value |
|--------|-------|
| Total games scanned | 50,000 |
| 600+0 games | 4,925 (9.85%) |

### Pass rates

| Stage | Count | % of 600+0 |
|-------|-------|-----------|
| basic_pass (valid Elos + Result + %clk) | 4,908 | 99.65% |
| eval_pass (basic_pass + %eval) | 746 | **15.2%** |

### Rejection reasons (600+0 games)

| Reason | Count |
|--------|-------|
| invalid_elo | 0 |
| invalid_result | 0 |
| no_clock | 17 |
| no_eval (among basic_pass) | 4,162 |

### Result distribution (basic_pass)

| Result | Count | % |
|--------|-------|---|
| 1-0 | 2,402 | 48.9% |
| 0-1 | 2,286 | 46.6% |
| 1/2-1/2 | 220 | 4.5% |

### Termination distribution (basic_pass)

| Termination | Count | % |
|-------------|-------|---|
| Normal | 4,342 | 88.5% |
| Time forfeit | 555 | 11.3% |
| Abandoned | 10 | 0.2% |
| Rules infraction | 1 | <0.1% |

### Elo distribution (basic_pass)

| Stat | White | Black |
|------|-------|-------|
| count | 4,908 | 4,908 |
| min | 514 | 445 |
| max | 2,677 | 2,652 |
| mean | 1,531.4 | 1,533.4 |
| median | 1,541.0 | 1,543.5 |
| stdev | 356.9 | 355.8 |

---

## 4. Critical Finding: Eval Availability

**Only 15.2% of 600+0 basic_pass games have `%eval` annotations.**

This is the most consequential result of this scan. It means:

- A strictly eval-gated model would train on ~1,650 games per 50k scanned, or roughly 1,650 × (total_archive_size / 50k) games from the full archive.
- The 2024-09 archive is approximately 61M games total. At 9.85% 600+0 rate and 15.2% eval rate, the eval-gated pool is roughly 61M × 0.0985 × 0.152 ≈ 912,000 games. That is viable but not enormous.
- Alternatively, the pipeline can be designed to handle two tiers: a larger no-eval tier for clock/rating/phase features, and a smaller eval tier when eval-dependent features are included.

This design question must be addressed in Ticket 2.1A (PGN Schema Audit) before the parser is built.

**Clock availability is very high**: 99.65% of 600+0 games have clock annotations. The 0.35% without clocks (17 out of 4,925) can be dropped without meaningful data loss.

---

## 5. Assumptions

- The first 50,000 games in the 2024-09 archive are representative of the archive's time-control mix. This is a reasonable assumption given Lichess archives are ordered chronologically and 10+0 is played throughout the month.
- `%clk` detection by substring search in `node.comment` is correct for the Lichess PGN format confirmed in the 1.1A audit.
- `%eval` presence on any main-line ply is used as a game-level signal. This does not guarantee every ply has eval.

---

## 6. Tests Run

```
19 passed in 0.07s
Python 3.13.11, pytest-9.0.3
```

All 19 tests passed on first run.

---

## 7. Checks Run

### git status (data safety)

Confirmed `data/interim/source_scan_2024_09_50k_v1.json` is untracked and ignored — it falls under the `data/` directory which is excluded by `.gitignore`. It must not be staged.

### Scan output file

`data/interim/source_scan_2024_09_50k_v1.json` written successfully. All fields present and JSON-valid.

---

## 8. Known Risks / Limitations

**Risk R1 — 50k games is a small sample of the full archive**

The 2024-09 archive likely contains tens of millions of games. The 50k cap gives a good first estimate but may not perfectly reflect the overall eval rate. Eval coverage may vary by time period. This is acceptable for planning purposes; the full parser run (Ticket 2.1B+) will use a larger sample.

**Risk R2 — Scan speed (154 games/s) implies full-archive scanning is expensive**

A full 61M-game archive at 154 games/s would take ~110 hours. The pipeline must work on a capped subset unless dedicated hardware is used. The 10+0 fraction (~9.85%) means 6M qualifying games; even scanning 500k takes ~90 minutes. This should guide the dataset size strategy in Phase 2.

**Risk R3 — Eval coverage may not be uniform across the archive**

Lichess added server-side eval annotations to a subset of games based on infrastructure availability. The 15.2% rate in 2024-09 may differ from other months. Check at least one other month before committing to an eval-dependent feature set.

**Risk R4 — `%eval` detected by substring only**

The scanner checks whether any main-line ply comment contains `%eval`. It does not parse the eval value or verify it's on every ply. The parser (Ticket 2.1B) must handle partial eval coverage (some plies annotated, others not).

**Risk R5 — Time forfeit at 11.3%**

Time forfeit is significant (555 of 4,908 basic_pass games). These games should be tracked with a termination flag in the feature schema. Their outcomes may be systematically different from normal termination games (e.g., a player in a better position but running low on time). This is relevant to the research question.

---

## 9. Suggested Next Step

**Ticket 2.1A — PGN Schema Audit**

Before building the parser, the schema audit must resolve:

1. Whether to require `%eval` (small eval-gated dataset) or make it optional (larger dataset with eval as a conditional feature).
2. Which specific fields to extract per game and per ply/checkpoint.
3. How to handle the 11.3% time-forfeit games.
4. Whether to look at eval coverage in a second monthly archive to check consistency.

The scanner (`source_scan.py`) is reusable for any monthly archive URL. It can be run on additional months with a single CLI invocation.

---

## Suggested staging for commit

```bash
git add src/chess_mhsuc/source_scan.py tests/conftest.py tests/test_source_scan.py ROADMAP.md reports/phase_reports/phase_1_1b_source_scanner_implementation.md
git commit -m "Ticket 1.1B: streaming source scanner, 19 tests, 50k scan results"
git push
```

Do NOT stage `data/interim/source_scan_2024_09_50k_v1.json` — it is local scan output and must remain Git-ignored.
