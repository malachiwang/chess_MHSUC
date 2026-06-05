# Phase Report: Ticket 0.1B — Project Initialization + Lichess Source Documentation Implementation

**Labels:** DOCS / DEVOPS / DATA | D1 | IMPLEMENTATION
**Date:** 2026-06-04
**Status:** Complete

---

## 1. Files Changed

| File | Change type |
|------|------------|
| `reports/notes/.gitkeep` | Deleted (directory removed) |
| `reports/phase_reports/.gitkeep` | Created (new directory established) |
| `.gitignore` | Modified — added 7 missing patterns |
| `CLAUDE.md` | Modified — unified audit format, added report-location and no-standalone-report-ticket rules |
| `WORKFLOW.md` | Modified — added explicit report-location and no-standalone-report-ticket rules to Section 11 |
| `MANIFEST.md` | Rewritten — repurposed from unzip instructions to stable project manifest |
| `ROADMAP.md` | Modified — updated Ticket 0.1A and 0.1B descriptions to reflect actual scope |
| `PIPELINE_OVERVIEW.md` | Modified — added Section 16 with Lichess parser-format assumptions |

---

## 2. Structural Changes Made

### `reports/notes/` → `reports/phase_reports/`

- Removed `reports/notes/.gitkeep` and the `reports/notes/` directory.
- Created `reports/phase_reports/.gitkeep` to establish the correctly named directory.
- All governance docs (README, ROADMAP, WORKFLOW, CLAUDE) already referenced `reports/phase_reports/`. The actual directory now matches.

---

## 3. Documentation Changes Made

### `CLAUDE.md` — Section 6: Audit format unified

Old format:
```
1. Goal
2. Relevant files
3. Current behavior
4. Proposed changes
5. Risks
6. Verification plan
7. Files expected to change
```

New format (matches WORKFLOW.md Section 3):
```
1. Summary
2. Files inspected
3. Current behavior / observed structure
4. Important findings
5. Risks / ambiguities
6. Recommended implementation plan
7. Files expected to change
8. Verification plan
```

### `CLAUDE.md` — Section 7: Report rules clarified

Added:
- Explicit report save location: `reports/phase_reports/` as a named `.md` file.
- "Also summarize in chat."
- "Do not create standalone report tickets. Post-implementation reports are required outputs of implementation tickets, not separate work items."
- Added "Results of tests/checks" as a report section (was missing vs. WORKFLOW.md).

### `WORKFLOW.md` — Section 11: Report rules added

Added at end of Section 11:
- Post-implementation reports are a required output of their implementation ticket, not separate tickets.
- Claude must save the report to `reports/phase_reports/` and summarize in chat.

### `MANIFEST.md` — Repurposed

Old content: unzip/git installation instructions from initial governance doc distribution. Not useful as a stable repo artifact.

New content: a stable project manifest describing:
- Purpose of each governance document (table).
- Expected repository structure.
- What may be committed.
- What must not be committed.
- Report naming conventions.

### `ROADMAP.md` — Ticket 0.1A/0.1B descriptions updated

Old Ticket 0.1A was described as a narrow "Governance Audit" with minimal scope.
Old Ticket 0.1B was described as governance-file creation only.

Updated to reflect actual scope:
- 0.1A: project initialization + Lichess source format audit (governance consistency, repo structure, environment assumptions, Lichess source format, data safety).
- 0.1B: project initialization + docs/structure implementation (this ticket).
- Both marked as complete with report path reference.

### `PIPELINE_OVERVIEW.md` — Section 16 added

New section: "Lichess PGN format assumptions."

Documents the following as assumed-but-unverified format details that must be confirmed during later source/schema audits:
- `[%clk H:MM:SS]` clock annotation format.
- `[%eval ...]` eval annotation format (decimal and mate notation).
- Eval sign convention (White-positive).
- `Variant` header may be absent for standard games.
- `UTCDate` / `UTCTime` headers for potential future time-based splits.
- `WhiteRatingDiff` / `BlackRatingDiff` headers for possible provisional-rating filtering.
- `.pgn.zst` streaming via `zstandard` must be verified on a real sample.
- `%eval` availability is not universal — selection bias must be acknowledged.

Former Section 16 (Deliverables by maturity level) renumbered to Section 17. Content unchanged.

---

## 4. `.gitignore` Changes Made

**Added patterns:**

```
# Appended to the Data section:
*.sqlite
*.db

# New Model artifacts section:
*.joblib
*.pkl
*.pt
*.pth
*.onnx
```

**Rationale:** `DATA_POLICY.md` required all of these but they were absent from the original `.gitignore`. The `data/` blanket ignore covers files inside the data directory, but these per-extension patterns protect against artifacts accidentally placed outside `data/` (e.g., model files saved to the repo root or `src/`).

**Unchanged patterns confirmed present:**

```
data/
.venv/
*.pgn
*.pgn.zst
*.parquet
*.duckdb
*.csv
.env
.DS_Store
__pycache__/
*.pyc
.ipynb_checkpoints/
```

---

## 5. Checks Run

### `git status`

```
Changes not staged for commit:
  modified:   .gitignore
  modified:   CLAUDE.md
  modified:   MANIFEST.md
  modified:   PIPELINE_OVERVIEW.md
  modified:   ROADMAP.md
  modified:   WORKFLOW.md
  deleted:    reports/notes/.gitkeep

Untracked files:
  reports/phase_reports/
```

All expected. No data files staged. No unintended files modified.

### `find . -maxdepth 4` (repo structure)

```
reports/
  figures/.gitkeep         ✓
  phase_reports/.gitkeep   ✓  (new — correctly named)
```

`reports/notes/` is gone. `reports/phase_reports/` is present.

### `grep` — `phase_reports` in key docs

Confirmed present in: `WORKFLOW.md`, `CLAUDE.md`, `README.md`, `ROADMAP.md`.

### `grep` — new `.gitignore` patterns

All 7 new patterns confirmed present at lines 14–22:
```
*.sqlite (14), *.db (15), *.joblib (18), *.pkl (19), *.pt (20), *.pth (21), *.onnx (22)
```

---

## 6. Assumptions Made

- `reports/notes/` contained only a `.gitkeep` placeholder and no real content. Confirmed before deletion.
- `PIPELINE_OVERVIEW.md` Section 16 "Deliverables by maturity level" was renumbered to Section 17. Content not changed.
- Lichess `%clk` and `%eval` annotation formats documented as *assumed conventions*, explicitly flagged as unverified until source/schema audits.
- No changes were made to research scope, data acquisition logic, parser code, or any file under `data/`.

---

## 7. Risks / Limitations

- `reports/phase_reports/` is currently untracked (new directory). When staging for commit, it must be explicitly added with `git add reports/phase_reports/`.
- The audit format change in `CLAUDE.md` Section 6 is a documentation change only. It does not retroactively change the format of the Ticket 0.1A audit report (which was already delivered and is coherent).
- `PIPELINE_OVERVIEW.md` now has 17 sections (was 16). No content was removed; only Section 16 was added and Section 17 renumbered. The renumbering is safe since no external references to section numbers exist.

---

## 8. Items Intentionally Deferred

| Item | Reason | Belongs to |
|------|--------|-----------|
| `tests/fixtures/` creation | Requires parser implementation; not a docs ticket | Ticket 2.1B |
| `requirements.txt` / `pyproject.toml` | Environment setup scope | Ticket 0.2B |
| Python version documentation | Part of environment audit | Ticket 0.2A |
| Stockfish / `zstd` CLI availability check | Part of environment audit | Ticket 0.2A |
| Verification of Lichess `%clk` / `%eval` format | Requires real data sample | Ticket 1.1A / 2.1A |
| Actual `%eval` availability rate in `10+0` games | Requires source scan | Ticket 1.1A |

---

## 9. Is the Next Ticket Safe to Begin?

**Yes.**

Ticket 0.2A (Environment Audit) is safe to begin. The repo structure is now consistent with all governance docs, data safety is strengthened, and the audit/report conventions are unified. No blocking issues remain from Phase 0.

Ticket 1.1A (Lichess Source Availability Audit) can also be planned. It should not begin until the environment is verified (0.2A/0.2B) and at least one qualifying Lichess monthly file is accessible locally.

---

## Suggested next step

**Ticket 0.2A — Environment Audit**

Verify:
- Python version and virtual environment
- Installed packages vs. required stack
- Stockfish presence and version
- `zstd` CLI availability
- `.gitignore` behavior under `git status --ignored`
- Repo structure against governance doc expectations
