# Repository guide

Start with the [README](README.md) for the question, results, limitations, and
synthetic example. The public repository is
[malachiwang/chess_MHSUC](https://github.com/malachiwang/chess_MHSUC).

## Current documentation

| File | Purpose |
|---|---|
| [PROJECT_CHARTER.md](PROJECT_CHARTER.md) | Scope, changes in direction, and evidence standards |
| [PIPELINE_OVERVIEW.md](PIPELINE_OVERVIEW.md) | Implemented data paths, filtering, measurement, and reproduction prerequisites |
| [MODEL_CARD.md](MODEL_CARD.md) | Model families, evaluation populations, probability diagnostics, and limitations |
| [DATA_POLICY.md](DATA_POLICY.md) | Data storage, privacy, and Git exclusions |
| [WORKFLOW.md](WORKFLOW.md) | Development audits, verification, reports, and holdout policy |
| [CLAUDE.md](CLAUDE.md) | Existing coding-agent operating instructions |
| [NOTICE.md](NOTICE.md) and [CITATION.cff](CITATION.cff) | Attribution, license scope, and citation metadata |

## Scientific records

| Record | What to read it for |
|---|---|
| [Termination decomposition](reports/termination_decomposition_combined.md) | The 10+0 outcome-model clock comparison, including the collapsed non-time-forfeit result |
| [Cross-control report](reports/cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md) | Dense sample counts, clock contrasts, weighting, and robustness |
| [Rating moderation](reports/rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md) | The conditioning-sensitive interaction and unsupported cross-control moderation claim |
| [Sharpness report](reports/sharpness_enriched_constraint_atlas_10plus0_2024_09_2024_10_v1.md) | Sparse checkpoint overlap and the unresolved interaction |
| [Benchmark figures](reports/figures/benchmark/) and [count tables](reports/figures/benchmark/count_tables.md) | Descriptive figures and their denominators |
| [Appendix index](reports/appendix_figure_index.md) | Earlier figures and technical analyses |
| [EXPERIMENT_LOG.md](EXPERIMENT_LOG.md) | Experiment chronology, including negative results and test exposure |
| [PREREGISTRATION.md](PREREGISTRATION.md) | Protocols, locked contrasts, decision rules, and revisions |
| [Phase reports](reports/phase_reports/) | Audits, implementation decisions, dataset cards, and verification records |

Reports remain records of their original runs. Their next-step language and local
paths may be historical. The [benchmark narrative](reports/benchmark_report.md)
contains older shorthand that needs qualification: the source is an archive prefix,
not a full month; recurring players make the months dependent; and the fitted
transform JSON is not tracked. Consult the current pipeline guide for reproduction.

## Historical plans and presentation notes

[ROADMAP.md](ROADMAP.md) gives current status above the preserved ticket history.
The [v11 proposal](docs/roadmap_rescope_v11_draft.md) preserves an earlier design,
and [related work](docs/RELATED_WORK.md) separates current positioning from its
historical literature table. [Presentation notes](reports/portfolio_launch_pack.md)
consolidate the former resume and interview variants;
[external launch notes](reports/external_launch_materials.md) retain metadata guidance.
These are presentation aids, not additional experimental evidence.

## Layout

- `src/chess_mhsuc/`: reusable Python pipeline, models, statistics, and report generators.
- `tests/`: tests and one synthetic PGN under `tests/fixtures/`.
- `reports/`: saved Markdown analyses and figures; `phase_reports/` contains audit records.
- `docs/`: literature context and the historical design proposal.
- `requirements.txt`, `.python-version`: dependency minima and target Python version.
- `data/raw/`, `data/interim/`, `data/processed/`: local-only paths, absent from a fresh clone.

Do not commit real game extracts, Parquets, databases, prediction files, or fitted
model artifacts. The complete rules are in [DATA_POLICY.md](DATA_POLICY.md).
