# Stockfish Evaluation — Fixed-Depth Pilot Assessment

**Ticket:** 8.1B — Fixed-Depth Stockfish Evaluation Implementation
**Dataset:** `lichess_ten_zero_2024_09_25k_v1`
**Version tag:** `2024_09_25k_v1`

---

## 1. ELI5 / TLDR

This artifact provides local fixed-depth Stockfish evaluations (6,205 positions at depth=12) for the `lichess_ten_zero_2024_09_25k_v1` pilot checkpoint positions. It replaces the sparse, selection-biased Lichess cloud evals (13.7% coverage) with full-coverage objective position context for Phase 8.2 eval-conditioned modeling. This module does NOT train models.

## 2. Scope

- Input: `ten_zero_positions_broad_2024_09_25k_v1.parquet`
- Positions: primary_numbered checkpoints (excludes `selected_position_type == 'last'`)
- Requested: 6,205 positions
- Evaluated: 6,205 positions
- Failed/skipped: 0 positions

## 3. Engine and Depth

- Engine: Stockfish 18
- Depth: 12 (fixed)
- `chess.engine.SimpleEngine` via python-chess 1.11.2
- No time limit; deterministic at fixed depth

## 4. Output Artifact

- `data/processed/sf_eval_broad_2024_09_25k_v1.parquet` (gitignored)
- `data/processed/sf_eval_metadata_2024_09_25k_v1.json` (gitignored)
- This report (committed)

## 5. Coverage

- Positions with sf_eval_available=True: 6,205 (100.0%)
- Positions with existing Lichess eval: 932
- Lichess eval coverage was: 13.7% (sparse, selection-biased)

## 6. Status Counts

| Status | Count |
|---|---|
| ok_cp | 5,993 |
| ok_mate | 212 |

## 7. Eval Distribution

| Bucket | N |
|---|---|
| equal | 1,791 |
| winning_white | 1,385 |
| losing_black | 1,103 |
| slight_white | 1,031 |
| slight_black | 683 |
| mate_white | 119 |
| mate_black | 93 |

sf_eval_cp: mean=79.5, std=1881.2, min=-10000, max=10000

## 8. Lichess Eval Overlap Preview

- Positions with both Lichess eval and SF eval: 932
- Sign agreement (non-mate, lichess vs SF): 829/872 = 95.1%
- Mean absolute difference (cp): 68.8
- Note: exact equality not expected — Lichess evals are variable-depth and from a different Stockfish version.

## 9. Runtime / Storage

- Total runtime: 329s (5.5min)
- Storage estimate: 0.31 MB (Parquet)

## 10. Caveats

- **Local Stockfish eval is objective-position context, not perfect truth.** Stockfish depth=12 provides a strong but approximate evaluation. Different depths or versions may produce different centipawn values.
- **Fixed-depth Stockfish is not causal.** Eval at a checkpoint reflects position strength, not what causes outcomes. A high sf_eval_cp does not mean the stronger position caused the win — player decisions after that checkpoint also matter.
- **Eval does not make clock or rating effects causal.** Clock pressure, rating, and position strength are correlated features, not a causal chain.
- **Existing Lichess eval coverage was sparse and selection-biased.** Only 13.7% of broad rows had Lichess evals; those games had ~20 Elo higher avg_elo. This artifact removes that bias.
- **This artifact prepares Phase 8.2 modeling but does not itself retrain models.** Models using sf_eval_* features will be implemented in Ticket 8.2B.
- **Test split is not used for model selection.** Following WORKFLOW.md §13 holdout policy.
- **Data artifact is gitignored and must not be committed.** Only this report and the phase report are committed.

## 11. Reproducibility

Re-run with the same `--depth`, `--stockfish-path`, and `--positions` to regenerate the artifact. The Markdown report body is deterministic (timestamps kept in JSON metadata only).

```bash
PYTHONPATH=src python -m chess_mhsuc.stockfish_eval \
    --dataset-id lichess_ten_zero_2024_09_25k_v1 \
    --version-tag 2024_09_25k_v1 \
    --positions data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet \
    --raw-pgn <RAW_PGN_PATH_OR_URL> \
    --depth 12 \
    --output-parquet data/processed/sf_eval_broad_2024_09_25k_v1.parquet \
    --output-metadata data/processed/sf_eval_metadata_2024_09_25k_v1.json \
    --output-report reports/stockfish_eval_2024_09_25k_v1.md \
    --overwrite
```
