# Phase Report: Ticket 0.2B — Environment Documentation Implementation

**Labels:** DEVOPS / DOCS | D1 | IMPLEMENTATION
**Date:** 2026-06-05
**Status:** Complete

---

## 1. Files Changed

| File | Change type |
|------|------------|
| `requirements.txt` | Created — curated direct dependencies, `>=` version pins |
| `.python-version` | Created — single line: `3.13.11` |
| `README.md` | Modified — added `## Setup` section |
| `ROADMAP.md` | Modified — updated Ticket 0.2A and 0.2B descriptions; marked both complete |
| `MANIFEST.md` | Modified — added `requirements.txt` and `.python-version` to repo structure and commit allowlist |

---

## 2. Environment Documentation Added

### `requirements.txt`

Created a curated `requirements.txt` listing 10 direct project dependencies plus `pytest`. Uses `>=` version pins against the versions verified in the project `.venv` during Ticket 0.2A.

Full content:

```
python-chess>=1.999
polars>=1.41.2
pandas>=3.0.3
duckdb>=1.5.3
scikit-learn>=1.9.0
matplotlib>=3.10.9
pyarrow>=24.0.0
zstandard>=0.25.0
tqdm>=4.67.3
jupyter>=1.1.1
pytest
```

Header comments document:
- Install instructions (create `.venv`, activate, `pip install -r requirements.txt`).
- The `python-chess` version discrepancy (pip reports `1.999`; `chess.__version__` may report differently — known package quirk, not a broken install).
- Intentional exclusions: `xgboost` (Phase 6+), `lightgbm` (Phase 6+), `torch` (Phase 10+).

### `.python-version`

Created a one-line `.python-version` file containing `3.13.11`. This is the Python version confirmed in the `.venv` during the 0.2A audit. The file is readable by pyenv, mise, and other version managers. It also serves as plain documentation of the target Python version for contributors or fresh-clone scenarios.

### `README.md` — Setup section

Added `## Setup` section immediately before `## External references`. The section covers:

1. Warning: do not use the system Python or conda base environment.
2. Commands to create and activate `.venv`.
3. `pip install --upgrade pip` before installing dependencies.
4. `pip install -r requirements.txt`.
5. Verification snippet: imports `chess`, `polars`, `duckdb`, `sklearn`, `zstandard` and prints `"environment ok"`.
6. Note that `.venv` is Git-ignored; `requirements.txt` and `.python-version` are the committed records.
7. Homebrew install note for system tools (`stockfish`, `zstd`).

---

## 3. Dependency File Decisions

### Why `requirements.txt` and not `pyproject.toml`

`pyproject.toml` is the modern standard for *distributable* Python packages. This project is a private research pipeline that will not be published to PyPI or installed as a package. Creating a `pyproject.toml` adds structure that does not serve current needs and would invite questions about package metadata, build backends, and entrypoints that are irrelevant at this stage. Deferred per audit recommendation.

### Why `>=` pins and not exact pins

Exact pins (`==`) from `pip freeze` would produce a 100+ line platform-specific lockfile. On a different platform (e.g., Linux, Intel Mac, future macOS version), many of those pins would fail due to platform-specific wheel names and transitive dependency resolution differences. The `>=` approach:
- Documents the minimum verified versions.
- Allows `pip` to resolve compatibly on other platforms.
- Is appropriate for a private research repo where there is one primary developer on one machine.

If exact reproduction becomes important (e.g., before outreach), running `pip freeze > requirements-lock.txt` inside the `.venv` can capture a full pin snapshot at that point.

### Why `pytest` is included without a version pin

`pytest` is a development/testing tool with no version constraint that would affect pipeline behavior. Pinning it to `>=9.0.3` (the version the dry-run would install) is premature. It is listed unpinned as a "get the latest compatible version" dependency. This is standard practice for test runners.

### Why no `Makefile`

No test targets, lint targets, or multi-step build commands exist yet. A `Makefile` with zero useful targets is pure overhead. Deferred until at least `make test` and `make lint` would be meaningful.

---

## 4. Items Intentionally Deferred

| Item | Reason | Belongs to |
|------|--------|-----------|
| `pyproject.toml` | Not a distributable package; overkill at this stage | Revisit only if packaging for distribution |
| `Makefile` | No useful targets yet | Add when `make test` / `make lint` are meaningful |
| Exact version lockfile (`pip freeze`) | Platform-specific; not needed for single-developer private repo | Create before outreach if needed |
| Stockfish path configuration | Stockfish verified present; exact invocation from Python deferred | Ticket 8.1A |
| `pytest` actual installation | `pytest` not yet in `.venv`; this ticket only documents it in `requirements.txt` | Next time `pip install -r requirements.txt` is run |
| `tests/fixtures/` creation | Requires parser implementation | Ticket 2.1B |

---

## 5. Checks Run

### `cat requirements.txt`

All 11 lines (10 packages + pytest) confirmed present with correct version pins and comment block.

### `cat .python-version`

Confirmed: `3.13.11`.

### `grep` — README Setup section

```
113: ## Setup
119: python3.13 -m venv .venv
122: source .venv/bin/activate
125: python -m pip install --upgrade pip
128: python -m pip install -r requirements.txt
144: The `.venv` directory is ignored by Git. See `requirements.txt` ...
```

Setup section confirmed present at line 113.

### `pip install --dry-run -r requirements.txt` (against `.venv`)

Result: all 10 core packages already satisfied. Only newly needed:

```
Would install: iniconfig-2.3.0  pluggy-1.6.0  pytest-9.0.3
```

This confirms:
- `requirements.txt` is syntactically valid.
- All project packages are already installed in the `.venv`.
- `pytest` is the only package not yet present; it will be installed on the next `pip install -r requirements.txt` run.

### `git status`

```
Changes not staged for commit:
  modified:   MANIFEST.md
  modified:   README.md
  modified:   ROADMAP.md

Untracked files:
  .python-version
  requirements.txt
```

All expected. No data files staged. No unintended files modified. The `reports/phase_reports/` directory (created in 0.1B) is already tracked.

---

## 6. Risks / Assumptions

**Risk R1 — pytest not yet installed in `.venv`**

`pytest` is documented in `requirements.txt` but not yet installed. The dry-run confirms it would be installed as `pytest-9.0.3` plus `iniconfig` and `pluggy`. No tests exist yet, so this has no immediate impact. Running `pip install -r requirements.txt` inside the activated `.venv` will install it.

**Risk R2 — Two Python environments still coexist**

The miniconda base environment (`/opt/miniconda3/bin/python`) remains available and will continue to be the default Python if the `.venv` is not activated. The README setup section warns about this. There is no technical enforcement; discipline is required. The risk is low until pipeline code exists.

**Risk R3 — `python-chess` version string discrepancy**

`pip list` reports `python-chess 1.999`; `chess.__version__` returns `1.11.2`. Documented in `requirements.txt` comments. This is a known internal quirk of the package. All required APIs are present and functional.

**Risk R4 — `>=` pins could resolve to incompatible future versions**

If any of the listed packages releases a breaking change, `pip install -r requirements.txt` on a fresh clone could install a version that breaks something. This risk is low for established packages and is standard for `>=` pinning. Tighten to `==` before outreach/publication if needed.

---

## 7. Is the Next Ticket Safe to Begin?

**Yes.**

Phase 0 (governance and setup) is now complete. The environment is documented, reproducible, and ready for pipeline work.

**Ticket 1.1A — Lichess Source Availability Audit** is the next ticket. It requires:
- A qualifying Lichess monthly `.pgn.zst` file accessible locally under `data/raw/lichess/`.
- The `.venv` activated with all packages installed (including `python-chess`, `zstandard`).
- No data downloads should happen without an explicit ticket authorizing the specific file.

Before starting 1.1A, Malachi should confirm that a Lichess source file is available or download one explicitly. The 1.1A audit ticket will authorize the first capped scan.

---

## Suggested staging for commit

```bash
git add requirements.txt .python-version README.md ROADMAP.md MANIFEST.md reports/phase_reports/phase_0_2b_environment_documentation_implementation.md
git commit -m "Ticket 0.2B: add requirements.txt, .python-version, README setup docs"
git push
```
