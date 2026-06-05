# Project Manifest

Repository: `chess-MHSUC`

This file describes the governance document set, the expected repository structure, and the rules governing what should and should not be committed.

---

## 1. Governance documents

These files define project scope, operating rules, and pipeline conventions.

| File | Purpose |
|------|---------|
| `README.md` | Project overview, research question, initial scope, repo structure summary, data policy summary, development philosophy |
| `PROJECT_CHARTER.md` | Mission, core hypothesis, initial research setting, evidence standards, data ethics, modeling stance, sample-size and compute stances |
| `ROADMAP.md` | Phase-by-phase ticket plan with audit/implementation pairs; updated as the project progresses |
| `WORKFLOW.md` | Standard development loop, audit and implementation ticket formats, post-implementation report rules, commit/push policy, data-operation policy |
| `DATA_POLICY.md` | Full data safety rules: what is ignored by Git, naming conventions, raw/interim/processed separation, Claude data restrictions, reproducibility requirements |
| `CLAUDE.md` | Behavior instructions for Claude Code: operating modes, data safety rules, audit/implementation formats, parser and modeling discipline |
| `PIPELINE_OVERVIEW.md` | Intended data and modeling pipeline stages from raw PGN to calibrated model; feature schema; evaluation requirements |
| `EXPERIMENT_LOG.md` | Template and running log of data/modeling experiments that influence project direction |
| `MODEL_CARD.md` | Template for the first serious model: intended use, training data, labels, features, evaluation, known limitations |
| `MANIFEST.md` | This file |

---

## 2. Expected repository structure

```text
chess-MHSUC/
  README.md
  PROJECT_CHARTER.md
  ROADMAP.md
  WORKFLOW.md
  DATA_POLICY.md
  CLAUDE.md
  PIPELINE_OVERVIEW.md
  EXPERIMENT_LOG.md
  MODEL_CARD.md
  MANIFEST.md

  data/                     # local only; ignored by Git entirely
    raw/lichess/            # immutable raw Lichess PGN archives
    interim/                # work-in-progress parsed/scanned outputs
    processed/              # model-ready cleaned datasets

  notebooks/                # exploratory analysis; outputs cleared before commit
  reports/
    figures/                # small committed figures if useful
    phase_reports/          # durable audit and implementation reports

  src/chess_mhsuc/          # reusable pipeline and modeling code
  tests/                    # parser, feature, and model tests
    fixtures/               # tiny synthetic PGN fixtures only (no real game data)
```

---

## 3. What may be committed

- Source code (`src/`, `tests/`)
- Governance documents (all files listed in Section 1)
- Markdown reports (`reports/phase_reports/`)
- Small figures (`reports/figures/`)
- Tiny synthetic PGN fixtures (`tests/fixtures/`) — not real game data
- Configuration templates without secrets
- `.gitkeep` placeholders for empty tracked directories

---

## 4. What must not be committed

- Real downloaded PGNs (`.pgn`, `.pgn.zst`)
- Parsed or processed game tables (`.parquet`, `.csv`)
- DuckDB or SQLite databases (`.duckdb`, `.sqlite`, `.db`)
- Large model artifacts (`.pkl`, `.joblib`, `.pt`, `.pth`, `.onnx`)
- Usernames or player identifiers from processed datasets
- Secrets, API keys, or environment credentials (`.env`)
- Any file under `data/`

---

## 5. Report conventions

Phase reports are saved to:

```text
reports/phase_reports/
```

Naming convention:

```text
phase_<phase>_<ticket>_<short_description>.md
```

Examples:

```text
reports/phase_reports/phase_0_1b_project_initialization_implementation.md
reports/phase_reports/phase_1_1a_lichess_source_audit.md
reports/phase_reports/phase_2_1b_pgn_parser_implementation.md
```

Post-implementation reports are outputs of their implementation ticket. They are not standalone tickets.
