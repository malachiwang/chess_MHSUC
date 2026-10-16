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


## Follow-up: documentation review, 2026-10-16

This second pass starts from the published cleanup at `46ce2df` on `main`. The
original report and its verification record above are preserved. The checks below
belong to this follow-up; the earlier synthetic-example run and 136-test result
were not rerun.

### Repository, scope, and files changed

Verified root `/Users/malachiwang/chess_MHSUC`, branch `main`, and origin
`git@github.com:malachiwang/chess_MHSUC.git`. The initial working tree contained only
untracked `.Rhistory`; its contents remain unchanged. No applicable `AGENTS.md` was
found in the selected checkout or checked parents. Existing repository guidance,
including `CLAUDE.md`, `WORKFLOW.md`, and `DATA_POLICY.md`, was read. The task's
explicit instruction to append here takes precedence over creating a new report.

Seven documentation files changed; none were added, moved, or deleted:

- [README](../../README.md): moved dataset scale near the opening, named the two
  outcome models descriptively, retained both result tables and the synthetic
  example, simplified status, and embedded existing H1/H2 figures with captions
  distinguishing descriptive summaries from adjusted regressions.
- [Pipeline guide](../../PIPELINE_OVERVIEW.md): expanded the ordered route from
  archive-prefix acquisition through parsing, cleaning, features, splits,
  checkpoint evaluation, score-transform fitting, player metadata, dense
  extraction, and benchmark figures. Each stage lists inputs, outputs,
  prerequisites, and verification status. Reproduction outputs use separate paths.
- [Preregistration](../../PREREGISTRATION.md): added dated status and provenance
  based on Git history and the 11.1A/14.2A protocol records. Distinguished locally
  recorded prospective decisions from external registration and later amendments;
  linked completed move-quality work and current dependence limitations.
- [Historical benchmark](../benchmark_report.md): added a dated notice qualifying
  monthly independence, the local-only transform, figure-writing side effects,
  and the archive-prefix meaning of “full month.”
- [Count-table introduction](../figures/benchmark/count_tables.md): distinguished
  equal-row within-control clock regressions from game-normalized pooled
  interactions and descriptive figures. Retained the original raw-versus-weighted
  comparison as a historical observation and preserved every numerical table.
- [External metadata notes](../external_launch_materials.md): revised the suggested
  About description; retained relevant topics. No GitHub setting was changed.
- This report: appended this follow-up without changing the original record.

### Evidence and assumptions

Inspected implementation entry points, argument parsers, output-path construction,
acceptance routes, split propagation, transform fitting, player hashing, dense
extraction gates, regression weights, and figure aggregations. Read the relevant
saved outcome, move-quality, benchmark, extraction, and protocol records. Viewed
both embedded PNGs and checked their generator before choosing them.

Saved records establish what was reported; they are not independently recomputed
results. The protocol's initial/refinement commits (`631328b`, `c184674`) and later
sharpness protocol (`d1c0a09`) support a versioned local planning process. No external
registry link or registration identifier was found in the protocol, experiment log,
or supporting reports. Earlier outcome results already existed; the new notice
makes no claim that all analyses were prospective.

### Checks actually performed in this follow-up

- Git root, remote, branch, baseline, working tree, final diff, and `git diff --check`.
- Nine module help commands exited successfully: `run_parser`, `cleaning`,
  `features`, `splits`, `stockfish_eval`, `next_move_loss`, `player_metadata`,
  `dense_move_loss`, and `benchmark_figures`, under `chess_mhsuc`.
- Validated all 20 expanded recipe argument sets through the real argument parsers,
  intercepting immediately after parsing and before workload execution. Both month
  gates, all six dense inputs, transform paths, and output-path connections agree.
  This checks argument acceptance, not data compatibility or successful extraction.
- `bash -n` passed for all 11 shell blocks in the edited documents. These blocks
  were not executed. Checked local links, anchors, image paths, Markdown fences,
  and incoming links to changed headings; no broken edited references were found.
- Byte comparisons confirmed the historical benchmark and protocol bodies,
  count-table numerical body, and all tracked PNGs match `HEAD`. All README tables,
  setup/example/test blocks, and expected output are unchanged. The existing
  report remains an exact prefix of this file. `.Rhistory` has its original hash.
- Final scope review: only the seven Markdown files above differ from `HEAD`.
  Implementation, tests, dependencies, datasets, scientific numbers, fitted
  artifacts, and figures are unchanged. Nothing was staged, committed, or pushed.

### Environment and reproduction limitations

Python 3.13.11 and the modules needed for CLI checks were available. Package checks
found python-chess 1.999, Polars 1.38.1, NumPy 2.4.1, SciPy 1.16.3,
scikit-learn 1.8.0, PyArrow 23.0.1, zstandard 0.24.0, and Matplotlib 3.10.8.
`duckdb` is absent and several installed versions are below `requirements.txt`
minima. No dependency installation or fresh-environment verification was attempted.
Stockfish was not started or version-verified in this follow-up.

The checkout has no `data/` directory: raw prefixes, parser/features/split artifacts,
checkpoint evaluations, player metadata, the fitted transform JSON, and six dense
Parquets are unavailable. No download, engine analysis, fitting, training, full
processing, or figure regeneration ran. Unchanged examples and tests were not
repeated, and GitHub rendering/external URLs were not rechecked.

Implementation constraints are documented, not repaired: transform fitting reads
hardcoded `data/processed/sf_eval_broad_<tag>.parquet` inputs; the parser CLI has no
local-input flag; October extraction reports compare with historical September
constants; and split-report templates contain historical test language. The figure
generator still emits outdated “read-only” and weighting prose, so newly generated
count tables would need the same qualification as the annotated saved table.

Next step: review this uncommitted documentation diff. A future scientific
reproduction needs the local inputs, a suitable dependency environment, and an
explicitly authorized computational run.
