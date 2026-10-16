# Documentation cleanup

Date: 2026-10-16. Documentation-only review of `malachiwang/chess_MHSUC`.
Baseline commit: `52039f3` on `main`.

## 1. Repository and files changed

The requested repository was cloned into `/Users/malachiwang/chess_MHSUC` after
read-only local checkout discovery found no matching origin. Git verified the root,
`main` branch, clean initial working tree, and `malachiwang/chess_MHSUC` remote.
The configured HTTPS URL resolves to SSH through the local Git configuration.
The other checkout and its untracked instructions file were not edited. No
`AGENTS.md` was found in the selected checkout or its checked parent directories;
the existing `CLAUDE.md`, workflow, and data policy were read.

Modified:

- [README.md](../../README.md): question, data scope, model/code links, supported
  metrics, limitations, synthetic example, and completed versus deferred work.
- [PROJECT_CHARTER.md](../../PROJECT_CHARTER.md): current scope, original objectives,
  evidence standards, and changes in direction.
- [PIPELINE_OVERVIEW.md](../../PIPELINE_OVERVIEW.md): implemented data paths,
  prerequisites, filtering differences, and figure reproduction command.
- [MODEL_CARD.md](../../MODEL_CARD.md): replaced the placeholder with implemented
  model families, evaluation populations, calibration diagnostics, and limitations.
- [MANIFEST.md](../../MANIFEST.md): navigation to methods, scientific records, and history.
- [ROADMAP.md](../../ROADMAP.md), [v11 proposal](../../docs/roadmap_rescope_v11_draft.md),
  and [related work](../../docs/RELATED_WORK.md): current-status introductions above
  collapsed historical bodies. Original bodies are preserved verbatim apart from
  outer whitespace; source-status labels and protocols remain intact.
- [Presentation notes](../portfolio_launch_pack.md) and
  [external metadata notes](../external_launch_materials.md): consolidated repeated
  resume, interview, and launch language into one explanation and a short metadata guide.
- [CITATION.cff](../../CITATION.cff): correct repository URL and qualified study scope.

Added: this required verification report. No files moved or deleted. Changes remain
uncommitted; nothing was staged or pushed.

## 2. Inspection findings and documentation changes

Inspected root guidance, README, charter, roadmap, workflow, data policy, pipeline,
model card, manifest, experiment history, protocols and relevant phase records;
parser/schema/cleaning/features, split/model/calibration code, dense extraction,
cross-control statistics and figure CLI; the synthetic fixture and selected tests;
and saved count, extraction, outcome, move-quality, rating, and sharpness reports.

The original overview mixed distinct analyses. The new documentation separates
10+0 checkpoint validation from dense three-control descriptive regression, states
metric definitions and denominators, and distinguishes equal-row from game-normalized
weights. The source scope is the first 250,000 games of each archive, not full months.
The months share players. Calibration is diagnostic; no fitted post-hoc calibrator
was located. The tree pilot overfit and draw prediction remained weak.

The pipeline guide documents implementation details that affect interpretation:
source-based rated/standard provenance, different acceptance routes for 10+0 versus
3+0/5+0, differing checkpoint/dense phase boundaries, the meaning of board-decided,
and the difference between missing annotations and mate sentinels. Code was not
changed to reconcile these differences.

Scientific reports, experiment log, preregistration, figures, count tables, datasets,
source code, tests, and dependency files were left unchanged. Older scientific
reports retain their original wording and next-step statements. The README and
manifest explicitly qualify the historical benchmark narrative's full-month,
independent-month, and tracked-transform shorthand.

## 3. Assumptions

Only this checkout supplies project claims and status. Saved reports establish what
was recorded, not an independent recomputation of unavailable local outputs. The
latest experiment-log entry closes the work with public packaging; earlier plans
are historical unless explicitly reopened. Documentation section 8 remains the
phase-convention reference in the pipeline guide and the evidence-standard reference
in the charter, preserving references from code.

## 4. Checks actually run

- Git root, origin, branch, initial/final status, diff statistics, and whitespace check.
- README synthetic parser example on Python 3.13.11. It read the existing fixture
  in memory, wrote no data, and produced the documented six output lines exactly.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3.13 -m pytest -q -p no:cacheprovider tests/test_parse_pgn.py tests/test_benchmark_figures.py`:
  **136 passed in 2.09 seconds**. No training or engine analysis was involved.
- `--help` for `chess_mhsuc.run_parser`, `chess_mhsuc.dense_move_loss`, and
  `chess_mhsuc.benchmark_figures`: all exited successfully. Figure command flags
  were matched to the CLI, including both output destinations.
- Recomputed the six saved count-table totals: **145,020 games and 8,353,475 rows**.
- Local Markdown target and edited-document anchor checks; comparison of archived
  bodies against Git confirmed preservation. Documentation-only diff review.
- The [Lichess database landing page](https://database.lichess.org/) loaded during
  external-link checking. GitHub clone succeeded; a separate web fetch of the GitHub
  page returned a tool cache miss, so GitHub rendering was not verified. Historical
  literature links were preserved, not re-reviewed.

## 5. Environment and checks by inspection only

Available interpreter: Python 3.13.11. Available package versions included
python-chess 1.999, polars 1.38.1, pandas 3.0.1, scikit-learn 1.8.0,
matplotlib 3.10.8, pyarrow 23.0.1, zstandard 0.24.0, tqdm 4.67.1,
jupyter 1.1.1, and pytest 9.0.2. `duckdb` was absent. Several versions are below
`requirements.txt` minima. No dependency was installed or changed; a fresh venv
installation was not verified. The smoke example only needs python-chess.

A Stockfish executable was found at `/opt/homebrew/bin/stockfish`; it was not run
or version-verified. Stockfish 18/depth 12 describes the saved extraction reports.
The full test suite was not run. Figure regeneration and statistical reproduction
were checked against code and records only, because the clone lacks raw prefixes,
six dense Parquets, prediction files, player metadata, and fitted transform JSON.
No download of game archives, engine analysis, training, or report regeneration ran.

## 6. Known limitations

The saved numerical results cannot be independently recomputed from this clone
alone. Historical scientific records contain dated or inconsistent prose; they
remain unchanged under the preservation requirement. No fresh full-environment or
GitHub rendering claim is made. The documentation does not establish causal effects,
independent monthly replication, a successful calibrated predictor, or resolved
sharpness moderation.

## 7. Suggested next step

Review the documentation diff. A later reproduction task would need its own local
artifact preparation and an environment matching the recorded requirements. No
additional research run is required for this documentation cleanup.
