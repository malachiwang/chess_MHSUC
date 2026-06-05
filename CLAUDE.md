# Claude Code Operating Instructions

This file defines how Claude Code should behave in the `chess-MHSUC` repository.

Claude must treat this repository as a research/data pipeline project where silent parser, cleaning, labeling, or split bugs can invalidate results.

## 1. Required reading before major changes

Before any major implementation, Claude must read:

```text
README.md
PROJECT_CHARTER.md
ROADMAP.md
WORKFLOW.md
DATA_POLICY.md
CLAUDE.md
PIPELINE_OVERVIEW.md
```

For modeling changes, Claude should also inspect:

```text
EXPERIMENT_LOG.md
MODEL_CARD.md
reports/phase_reports/
```

## 2. Default mode

Default mode is **CAUTIOUS**.

Claude should not assume permission for broad rewrites, bulk data operations, dependency installation, or architecture changes.

## 3. Operating modes

### CAUTIOUS mode

Default.

Behavior:

- audit before implementation,
- minimal edits,
- narrow scope,
- preserve existing behavior,
- avoid destructive commands,
- ask before touching data,
- state assumptions explicitly.

### IMPLEMENTATION mode

Used when Malachi provides a clear implementation ticket.

Behavior:

- edit only files in scope,
- implement the requested change,
- avoid unrelated cleanup,
- update tests/docs when required,
- produce a post-implementation report.

### AGGRESSIVE mode

Only when explicitly requested.

Behavior:

- broader refactors allowed,
- still must preserve data safety,
- still must report risks,
- still must not delete or overwrite real data without explicit permission.

### HOTFIX mode

Used for urgent small fixes.

Behavior:

- target the smallest viable change,
- no architecture changes,
- no opportunistic refactors,
- verify quickly,
- report exactly what changed.

## 4. Absolute data safety rules

Claude must not delete, overwrite, rename, move, compress, decompress, or bulk-transform data files unless Malachi explicitly asks for that exact data operation in the current prompt.

This applies to:

```text
data/raw/
data/interim/
data/processed/
*.pgn
*.pgn.zst
*.parquet
*.csv
*.duckdb
*.sqlite
*.db
```

Claude may propose commands for Malachi to run, but must label destructive or expensive operations clearly.

## 5. No real data in Git

Claude must not add real datasets to Git.

Do not stage:

```text
*.pgn
*.pgn.zst
*.parquet
*.csv
*.duckdb
real game extracts
raw data archives
processed datasets
large model files
```

Allowed:

```text
code
docs
markdown reports
small figures
tiny synthetic fixtures under tests/fixtures/
```

## 6. Audit-before-implementation rule

For risky areas, Claude must first produce an audit before implementation.

Mandatory audit areas:

- data acquisition,
- PGN parsing,
- clock extraction,
- eval extraction,
- label extraction,
- cleaning/filtering,
- dataset schema changes,
- train/test splitting,
- model evaluation,
- calibration,
- dependency changes,
- `.gitignore` changes.

An audit should include:

```text
1. Summary
2. Files inspected
3. Current behavior / observed structure
4. Important findings
5. Risks / ambiguities
6. Recommended implementation plan
7. Files expected to change
8. Verification plan
```

## 7. Implementation report requirement

After implementation, Claude must produce a concise report.

Report location: save to `reports/phase_reports/` as a `.md` file named after the ticket (e.g., `phase_1_1b_source_scanner_implementation.md`). Also summarize in chat.

Do not create standalone report tickets. Post-implementation reports are required outputs of implementation tickets, not separate work items.

Report format:

```text
1. Files changed
2. Summary of behavior added/changed
3. Assumptions made
4. Tests or checks run
5. Results of tests/checks
6. Known risks / limitations
7. Suggested next step
```

For data/modeling changes, include:

```text
Dataset source/scope
Filters applied
Rows/games affected if known
Leakage risks
Validation approach
```

## 8. Parser and feature discipline

Claude must not assume PGN fields exist without inspecting real examples or tests.

Parser code should:

- handle missing fields gracefully,
- record skip reasons where practical,
- separate raw parsing from cleaning,
- avoid silently coercing malformed values,
- include tests for result, clock, eval, and time-control parsing.

## 9. Modeling discipline

Claude must not train models before data assumptions are documented.

Modeling code must:

- split by game ID, not by row,
- report baselines,
- use probability metrics,
- avoid claiming success from accuracy alone,
- include calibration assessment when feasible,
- document feature columns and labels.

## 10. Dependency discipline

Claude may propose dependency installs, but Malachi runs install commands unless explicitly granting permission.

No dependency should be added without explaining:

```text
Why it is needed
What it replaces or enables
Whether it is core or optional
```

Initial preferred stack:

```text
python-chess
polars or pandas
duckdb
scikit-learn
matplotlib
pyarrow
zstandard
tqdm
jupyter
```

Later optional:

```text
xgboost
lightgbm
pytorch
```

## 11. Notebook policy

Claude may create notebooks for exploration, but reusable logic belongs in `src/chess_mhsuc/`.

Notebook outputs should be cleared before commit unless explicitly needed for review.

No core parser, cleaning, or modeling logic should live only in a notebook.

## 12. Git discipline

Normal stable work should be committed and pushed after verification.

Before committing, Claude should remind Malachi to run:

```bash
git status
git diff --stat
```

For data-sensitive work, also check:

```bash
git status --ignored
```

Claude should never suggest `git add .` after data generation unless it has verified ignored/untracked data will not be staged.

Prefer explicit staging:

```bash
git add README.md PROJECT_CHARTER.md ROADMAP.md WORKFLOW.md DATA_POLICY.md CLAUDE.md PIPELINE_OVERVIEW.md EXPERIMENT_LOG.md MODEL_CARD.md
```

## 13. Communication style

Claude should be direct and operational.

Avoid:

- vague reassurance,
- overclaiming results,
- hidden assumptions,
- giant unreviewable patches,
- data operations without permission.

Prefer:

- small scoped changes,
- concrete verification commands,
- clear risks,
- concise reports,
- explicit next steps.
