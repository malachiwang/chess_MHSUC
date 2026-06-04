# Governance Document Manifest

This zip contains first-version governance documents for `chess-MHSUC`.

## Required project governance docs

```text
README.md
PROJECT_CHARTER.md
ROADMAP.md
WORKFLOW.md
DATA_POLICY.md
CLAUDE.md
PIPELINE_OVERVIEW.md
```

## Optional but included templates

```text
EXPERIMENT_LOG.md
MODEL_CARD.md
```

## Recommended install into repository

From inside the repo root:

```bash
unzip -o ~/Downloads/chess-MHSUC-governance-docs.zip -d .
```

Then inspect:

```bash
git status
git diff --stat
git diff -- README.md PROJECT_CHARTER.md ROADMAP.md WORKFLOW.md DATA_POLICY.md CLAUDE.md PIPELINE_OVERVIEW.md EXPERIMENT_LOG.md MODEL_CARD.md
```

Commit explicitly:

```bash
git add README.md PROJECT_CHARTER.md ROADMAP.md WORKFLOW.md DATA_POLICY.md CLAUDE.md PIPELINE_OVERVIEW.md EXPERIMENT_LOG.md MODEL_CARD.md

git commit -m "Add project governance documents"

git push
```

## Important note

These documents intentionally do not include real data. Real datasets should remain local and ignored by Git.
