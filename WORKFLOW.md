# Workflow

This document defines the development workflow for `chess-MHSUC`.

The project should avoid large unreviewed changes. Data pipeline bugs are high-risk because they can invalidate downstream modeling results.

## 1. Standard loop

The default loop is:

```text
Audit -> Implementation -> Report -> Verification -> Commit -> Push
```

This applies especially to:

- data ingestion,
- parsing,
- cleaning,
- label extraction,
- feature engineering,
- model training,
- evaluation,
- train/test splitting.

## 2. Audit ticket format

An audit ticket should include:

```text
Title
Goal
Scope
Files to inspect
Questions to answer
Expected risks
Required output/report
```

An audit should not make broad code changes unless explicitly allowed.

## 3. Audit report format

Audit reports should include:

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

Data-related audit reports should also include:

```text
sample size scanned
filters observed
field availability
missing values if checked
assumptions about labels/features
```

## 4. Implementation ticket format

An implementation ticket should include:

```text
Title
Goal
Inputs from audit
Files allowed to change
Behavior to add/change
Behavior explicitly out of scope
Tests/checks required
Report requirements
```

Implementation tickets should be scoped. Avoid “build the whole pipeline” tickets.

## 5. Post-implementation report format

After implementation, produce:

```text
1. Files changed
2. Summary of changes
3. Exact behavior added/changed
4. Tests/checks run
5. Results of tests/checks
6. Assumptions made
7. Known risks / limitations
8. Suggested next step
```

For data/modeling changes, also include:

```text
Dataset source/scope
Filters applied
Rows/games affected if known
Label definitions
Split method
Metrics reported
Leakage risks
```

## 6. Verification before commit

Before committing, run at minimum:

```bash
git status
git diff --stat
```

If tests exist:

```bash
pytest
```

For data-sensitive work:

```bash
git status --ignored
```

Do not commit if real data is staged.

## 7. Commit policy

Commit stable, verified work.

Recommended commit style:

```text
Initialize project governance documents
Add Lichess source audit report
Implement PGN header scanner
Add synthetic PGN parser tests
Implement checkpoint feature extraction
Add baseline model evaluation report
```

Avoid vague commits:

```text
updates
stuff
fix
new things
```

## 8. Push policy

Push after stable commits.

Normal command sequence:

```bash
git status
git add <explicit files>
git commit -m "Descriptive message"
git push
```

Avoid `git add .` after data generation unless ignored/untracked files have been checked.

## 9. Data-operation policy

Data operations require caution.

Claude should not run destructive or bulk-transform commands on data unless Malachi explicitly requests them in the current prompt.

Dangerous examples:

```bash
rm -rf data/
mv data/processed/* ...
python scripts/build_dataset.py --overwrite
find data -delete
```

Safe read-only examples:

```bash
ls -lah data/raw/lichess
du -sh data
find data -maxdepth 3 -type f | head
```

## 10. Notebook workflow

Notebooks are allowed for exploration.

Rules:

- reusable logic belongs in `src/chess_mhsuc/`,
- notebooks should call reusable functions where possible,
- outputs should be cleared before commit unless intentionally retained,
- important conclusions must be summarized in markdown reports.

## 11. Reports directory

Durable reports should live in:

```text
reports/phase_reports/
```

Small figures may live in:

```text
reports/figures/
```

Suggested report naming:

```text
reports/phase_reports/phase_1_1a_lichess_source_audit.md
reports/phase_reports/phase_2_1b_pgn_parser_implementation.md
```

Post-implementation reports are a required output of their implementation ticket. They are not separate tickets. After completing implementation, Claude must:

1. Save the report as a `.md` file in `reports/phase_reports/`.
2. Summarize the report in the chat response.

Do not create standalone report tickets unless explicitly requested.

## 12. Dependency changes

Dependency additions require explanation.

Before adding a dependency, document:

```text
what it does
why it is needed
whether it is optional or core
whether a current dependency already covers it
```

Malachi runs installation commands unless explicitly granting Claude permission.

## 13. Escalation rule

If a task becomes too broad, split it.

Examples:

Instead of:

```text
Build the entire data pipeline.
```

Use:

```text
1. Audit PGN headers and field availability.
2. Implement header scanner.
3. Audit move/comment parsing.
4. Implement clock/eval extraction.
5. Audit cleaning assumptions.
6. Implement cleaner.
```

Small verified steps beat large opaque changes.
