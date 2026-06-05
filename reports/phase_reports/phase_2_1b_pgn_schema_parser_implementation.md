# Phase Report: Ticket 2.1B — PGN Schema + Single-Game Parser Implementation

**Labels:** DATA / ML / TEST | D3 | IMPLEMENTATION
**Date:** 2026-06-05
**Status:** Complete

---

## 1. Files Changed

| File | Change type |
|------|-------------|
| `src/chess_mhsuc/schemas.py` | Created — dataclass schemas and constants |
| `src/chess_mhsuc/parse_pgn.py` | Created — single-game parser |
| `tests/fixtures/tiny_clock_eval_game.pgn` | Created — 82-ply synthetic legal fixture |
| `tests/test_parse_pgn.py` | Created — 110 tests |
| `ROADMAP.md` | Modified — marked 2.1A complete, 2.1B complete |

No files under `data/` were touched.

---

## 2. Schema Design Summary (`schemas.py`)

### Constants

| Name | Value |
|------|-------|
| `RESULT_WHITE_WIN` | `"WHITE_WIN"` |
| `RESULT_DRAW` | `"DRAW"` |
| `RESULT_BLACK_WIN` | `"BLACK_WIN"` |
| `TIME_CONTROL_TARGET` | `"600+0"` |
| `PHASE_OPENING` | `"opening"` |
| `PHASE_MIDDLEGAME` | `"middlegame"` |
| `PHASE_ENDGAME` | `"endgame"` |
| `MATE_CP_SENTINEL` | `10_000` |
| `CHECKPOINT_PLIES` | `{20: "move_10", 40: "move_20", 60: "move_30", 80: "move_40"}` |
| `REJECT_WRONG_TC` | `"wrong_time_control"` |
| `REJECT_VARIANT` | `"variant_or_nonstandard"` |
| `REJECT_INVALID_ELO` | `"missing_or_invalid_elo"` |
| `REJECT_INVALID_RESULT` | `"missing_or_invalid_result"` |
| `REJECT_MISSING_CLOCK` | `"missing_clock"` |

### GameRecord (22 fields)

One row per parsed game. Covers accepted and rejected games alike.

Key fields: `game_id`, `source_file`, `source_month`, `utc_date`, `utc_time`,
`time_control`, `result_raw`, `result_class`, `white_result_numeric`,
`termination`, `white_elo`, `black_elo`, `elo_diff`, `white_rating_diff`,
`black_rating_diff`, `event`, `n_plies`, `has_clock`, `has_eval`,
`accepted_basic`, `accepted_eval`, `rejection_reason`.

Username fields (`White`, `Black`) are intentionally absent per DATA_POLICY.md.

### PlyRecord (12 fields)

One row per main-line ply. Raw extracted values before feature engineering.

Key fields: `game_id`, `ply` (1-indexed), `move_number`, `side_to_move_next`,
`san`, `white_clock_s`, `black_clock_s`, `clock_diff_s`, `eval_cp`,
`eval_mate`, `raw_eval`, `has_eval`.

### PositionRecord (19 fields)

One row per selected checkpoint position. Merges ply-level data with game-level
metadata for downstream use.

Key fields: all PlyRecord fields except `san`/`raw_eval`, plus
`selected_position_type`, `phase`, `result_class`, `white_result_numeric`,
`white_elo`, `black_elo`, `elo_diff`, `termination`, `n_plies_total`.

---

## 3. Parser Design Summary (`parse_pgn.py`)

### Functions

| Function | Purpose |
|----------|---------|
| `parse_int(value)` | String → int or None; rejects `"?"` and empty |
| `parse_rating_diff(value)` | Handles signed strings like `"+8"`, `"-5"` |
| `parse_result(headers)` | Maps raw Result to `(result_raw, result_class, white_result_numeric)` |
| `parse_game_id(site)` | Extracts last URL path segment from Site header |
| `parse_source_month(source_file)` | Extracts `YYYY-MM` from archive filename |
| `parse_clock_seconds(clock_str)` | `H:MM:SS` → integer seconds |
| `parse_eval_comment(comment, side_to_move_next)` | Parses `%eval` annotation with White-POV mate convention |
| `phase_for_move(move_number)` | `≤10 → opening`, `11–35 → middlegame`, `>35 → endgame` |
| `_scan_main_line(game)` | Single-pass walk for `(n_plies, has_clock, has_eval)` |
| `extract_game_record(game, source_file)` | Builds `GameRecord`; applies rejection logic |
| `extract_ply_records(game, game_id)` | Builds `list[PlyRecord]` with clock carry-forward |
| `select_checkpoints(ply_records, game_record)` | Builds `list[PositionRecord]` for v1 checkpoints |
| `parse_game(game, source_file)` | Top-level entry point; returns `(GameRecord, list[PositionRecord])` |

### Rejection priority

```text
wrong_time_control
  → variant_or_nonstandard
    → missing_or_invalid_elo
      → missing_or_invalid_result
        → missing_clock
```

---

## 4. Eval Policy Implemented

**Option C (nullable)** from the Ticket 2.1A audit.

- `eval_cp`: centipawns, White POV. `None` if no `%eval` on this ply.
  `±MATE_CP_SENTINEL` (±10000) for forced-mate positions.
- `eval_mate`: mate distance, White POV. `None` if not a mate score.
  Positive = White has mate. Negative = Black has mate.
- `has_eval: bool`: True if `%eval` annotation present on this ply.
- `raw_eval: str | None`: raw token string (`"0.47"`, `"#3"`, `"#-2"`),
  retained for auditing, excluded from processed data.

### Mate sign convention

Lichess reports mate scores as `#N` (side to move has mate) or `#-N`
(opponent has mate). The parser converts to White POV using `side_to_move_next`:

| Token | side_to_move_next | eval_cp | eval_mate |
|-------|------------------|---------|-----------|
| `#3`  | `"white"` | +10000 | +3 |
| `#3`  | `"black"` | −10000 | −3 |
| `#-2` | `"white"` | −10000 | −2 |
| `#-2` | `"black"` | +10000 | +2 |

---

## 5. Clock Policy Implemented

- Clocks stored as integer seconds remaining after the move.
- **Carry-forward rule**: each side's clock is updated only when they move.
  The other side's most recent clock value is propagated forward.
- `clock_diff_s = white_clock_s − black_clock_s`. Positive = White has more time.
  `None` if either component is `None`.
- `black_clock_s` is `None` on ply 1 (White has moved, Black has not yet).

**Carry-forward asymmetry** (not a bug): At odd plies (White's move N),
`black_clock_s` reflects Black's move N−1, so it can exceed `white_clock_s`.
Both clocks equalize after Black plays move N (the corresponding even ply).

Verified carry-forward values from fixture (82-ply game, shuttle phase 3s/move):

| Ply | white_clock_s | black_clock_s | Note |
|-----|--------------|--------------|------|
| 1 | 590 | None | Black hasn't moved |
| 19 | 500 | 510 | White move 10; Black still on move 9 clock |
| 20 | 500 | 500 | Black move 10; both equal |
| 39 | 470 | 473 | White move 20; Black still on move 19 clock |
| 40 | 470 | 470 | Black move 20; both equal |

---

## 6. Checkpoint Policy Implemented

**v1 checkpoint definition** (from Ticket 2.1A audit):

Checkpoints are taken after Black's Nth full move (even plies, side_to_move_next="white"):

| Label | Ply | Condition |
|-------|-----|-----------|
| `move_10` | 20 | always if game reaches ply 20 |
| `move_20` | 40 | if game reaches ply 40 |
| `move_30` | 60 | if game reaches ply 60 |
| `move_40` | 80 | if game reaches ply 80 |
| `last` | final ply | always if game reaches ply 20 |

Rules:
- Games shorter than 20 plies produce no checkpoint rows.
- `"last"` is always emitted if `last_ply >= 20`.
- If `"last"` coincides with a numbered checkpoint (e.g. game ends at ply 40),
  both rows are emitted with different `selected_position_type` values.
  Deduplication is the caller's responsibility.
- Checkpoints are only emitted for `accepted_basic=True` games.

Low-time flags (`under_60`, `under_30`, `under_10`) are deferred to feature
engineering (Phase 3, Ticket 3.2B), as decided in the 2.1A audit.

---

## 7. Tests Run

```bash
.venv/bin/pytest tests/test_source_scan.py tests/test_parse_pgn.py -v
```

**Result: 129 passed in 0.71s**

| Suite | Tests | Result |
|-------|-------|--------|
| `test_source_scan.py` | 19 | All passed (no regression) |
| `test_parse_pgn.py` | 110 | All passed |

### test_parse_pgn.py coverage

| Test class | Tests | What is covered |
|-----------|-------|----------------|
| `TestParseClockSeconds` | 7 | H:MM:SS parsing, None/empty, boundary values |
| `TestPhaseForMove` | 9 | All three phases, boundary values |
| `TestParseResult` | 4 | All valid results + `"*"` invalid |
| `TestParseGameId` | 5 | Normal URL, None, empty, subpath |
| `TestParseSourceMonth` | 4 | Valid filename, no date, None |
| `TestParseEvalComment` | 10 | Decimal ±, missing, mate ×4 cases, sentinel, both annotations |
| `TestExtractGameRecordFixture` | 11 | All acceptance fields, no username fields |
| `TestExtractGameRecordRejection` | 9 | All rejection reasons + priority ordering |
| `TestExtractPlyRecords` | 14 | Ply count, ply 1, clock carry-forward ×4, eval ×4, game_id |
| `TestSelectCheckpointsFixture` | 22 | All 5 checkpoints, all fields, game-level copy |
| `TestSelectCheckpointsEdgeCases` | 8 | Empty, 15-ply, 19-ply, 20-ply, 21-ply, 40-ply |
| `TestParseGame` | 4 | Full round-trip, rejected game, eval flag |

**Python:** 3.13.11 | **pytest:** 9.0.3

---

## 8. Data Safety Confirmation

- No files under `data/` were created, modified, or staged.
- No real game data was downloaded, processed, or committed.
- No `.pgn`, `.parquet`, `.csv`, `.db`, or `.pkl` files were created outside
  `tests/fixtures/`.
- `tests/fixtures/tiny_clock_eval_game.pgn` is a fully synthetic hand-crafted
  game (no real Lichess game data).
- No network commands were run.

---

## 9. Items Intentionally Deferred

| Item | Deferred to |
|------|-------------|
| Low-time pressure flags (`under_60`, `under_30`, `under_10`) | Ticket 3.2B (Feature Engineering) |
| Material-based phase detection | Later ticket after v1 phase is validated |
| Multi-game streaming integration | Ticket 2.2B (Parser Hardening) |
| Parquet/CSV dataset writing | Phase 3 |

---

## 10. Risks / Assumptions

**R1 — Eval availability on real data**
The eval carry-forward test assumes partial eval coverage is handled correctly.
The parser stores `None` on plies without `%eval` — this is verified by tests.
However, the parser has not yet been run on a real Lichess archive. Ticket 2.2A
(Parser Validation Audit) will validate on a capped real sample.

**R2 — Mate score convention**
The White-POV mate sign conversion has been unit-tested for all four
(token, side) combinations. However, only White-to-move cases appear in the
synthetic fixture. Black-to-move mate cases are covered only by unit tests on
`parse_eval_comment` directly.

**R3 — Clock carry-forward on real games**
Real games may have missing `%clk` annotations on some plies (hardware issues,
delay before computer analysis, etc.). The parser handles this by propagating
the last known clock — this behaviour is correct but means `clock_diff_s` can
become stale. The validation audit (Ticket 2.2A) should check the frequency of
mid-game missing clocks.

**R4 — SAN derivation**
`san` uses `node.parent.board().san(node.move)`. This recomputes the board
from scratch at each ply, which is correct but slow for very long games.
SAN is not used in modeling features for Phase 3 and can be dropped or
lazily computed if performance becomes a concern at scale.

**R5 — Single-game parser only**
`parse_pgn.py` processes one `chess.pgn.Game` at a time. Integration with
the streaming decompressor (`source_scan.py`) is not yet implemented.
That integration belongs to Ticket 2.2B.

---

## 11. Whether the Next Ticket Is Safe to Begin

**Yes. Ticket 2.2A (Parser Validation Audit) is safe to begin.**

The parser is unit-tested, schemas are locked, and the fixture-based tests
cover all critical code paths. The next audit should run the parser on a
capped real sample (≤10,000 600+0 games) to confirm:
- Rejection rates match source-scan estimates.
- Eval parsing behaves correctly on real annotation formats.
- Clock carry-forward is stable across real game lengths.
- No unexpected crashes or silent misparses.

The audit should not require changes to `schemas.py` or `parse_pgn.py`
unless specific bugs are found. Any bugs found in 2.2A should be fixed
in a targeted Ticket 2.2B (Parser Hardening).

---

## Suggested staging for commit

```bash
git add src/chess_mhsuc/schemas.py
git add src/chess_mhsuc/parse_pgn.py
git add tests/fixtures/tiny_clock_eval_game.pgn
git add tests/test_parse_pgn.py
git add ROADMAP.md
git add reports/phase_reports/phase_2_1b_pgn_schema_parser_implementation.md
git commit -m "Ticket 2.1B: PGN schemas, single-game parser, 110 tests"
git push
```

Do NOT stage `data/` — confirm with `git status --ignored` before committing.
