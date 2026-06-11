# Ticket 9.3B — Cross-Month Replication Implementation

**Labels:** DATA/ML/ANALYSIS | D3 | IMPLEMENTATION
**Date:** 2026-06-11
**Owner:** Malachi Wang
**Dataset:** `lichess_ten_zero_2024_10_250k_v1`

---

## 1. ELI5 / TLDR

Reran the full pipeline on a fully separate month (2024-10, first 250k raw
games) to test whether the 2024-09 findings are month-specific.

**Both replication targets hit:**
- **Overall E3→E4 (primary): −0.0120, 95% CI [−0.0177, −0.0062] — excludes
  zero** (2024-09 reference: −0.0138 [−0.0186, −0.0091]). REPLICATED.
- **P3 late-clock localization: REPLICATED** — under_60s −0.2468
  (descriptive, 241 games), 60_180s −0.0442 [−0.0636, −0.0242] excludes
  zero, over_180s −0.0066 near zero. The time-scarcity gradient reproduces.

The clock signal now stands on two independent months. Predictive
association only; not causal; reasoning quality not measured.

---

## 2. Files Created

| File | Description |
|---|---|
| `reports/cross_month_replication_2024_10_250k_v1.md` | Committed cross-month report (19 sections) |
| `reports/eval_conditioned_modeling_2024_10_250k_v1.md` | Committed rendered ablation report |
| `reports/constraint_slices_2024_10_250k_v1.md` | Committed rendered slice report |
| `reports/phase_reports/phase_9_3b_cross_month_replication_implementation.md` | This report |

Local-only (gitignored): raw cache `lichess_2024_10_first250k.pgn` (583 MB);
all `*_2024_10_250k_v1` interim/processed artifacts; scratch reports in
`data/processed/cross_month_reports/`.

## 3. Files Modified

| File | Change |
|---|---|
| `src/chess_mhsuc/constraint_slices.py` | A1: limitations prose payload-driven (dataset_id; generic month wording) |
| `src/chess_mhsuc/eval_conditioned_modeling.py` | A2: optional `--reference-label` / `--reference-e3-e4-delta` / `--reference-e3-e4-ci-lower` / `--reference-e3-e4-ci-upper`; "Replication comparison" block; omission preserves prior behavior |
| `tests/test_constraint_slices.py` | +2 payload-driven-prose tests (76 total) |
| `tests/test_eval_conditioned_modeling.py` | +5 reference-comparison tests incl. end-to-end CLI both ways (101 total) |
| `ROADMAP.md` | Phase 9.3 stanza; 9.3A and 9.3B complete |
| `EXPERIMENT_LOG.md` | EXP-011 |

No skip-offset parser work (per invariant); `run_parser.py` untouched.

---

## 4. Dataset / Sampling

`dataset_id = lichess_ten_zero_2024_10_250k_v1`; deterministic first-250k
prefix of the immutable 2024-10 archive — fully disjoint from all 2024-09
data. Counts: 24,908 600+0 games → 24,801 clean → 23,496 broad games →
**62,839 primary positions**; splits (seed=42): 43,946 / 9,442 / 9,451 rows
(16,447 / 3,524 / 3,525 games). Month-to-month comparison table in the
cross-month report §7 — the months are closely matched (avg_elo within
5 points, DRAW rate identical at 6.1%, termination mix similar); no
distribution shift complicating interpretation.

## 5. Pipeline Execution

Exact 9.1B sequence with the new tag: parse with tee-cache (1,397 s) →
cleaning → features → splits → baselines → stockfish_eval →
eval_conditioned_modeling (with `--expected-primary-rows 62839
--expected-split-counts train=43946,val=9442,test=9451` and the 2024-09
reference args) → constraint_slices. Splits/baselines `--report-output-dir`
pointed at gitignored `data/processed/cross_month_reports/` to protect
committed pilot reports. All stage integrity checks ALL PASS.

## 6. Stockfish Protocol

Dry-run (10/10 FENs from local cache, 0.4 s) → medium run (1,000 ok,
25.3 s, depth histogram `{0: 5, 12: 995}`) → resume test (500 → 1,500 rows,
0 duplicates) → **full run after Malachi's explicit approval**:
62,839/62,839 ok, 0 failures, 1,626 s (~27 min). Depth histogram: 62,540 @
12; **299 terminal sf_depth=0 rows** (0.5%). `split_set` joined post-hoc
from the splits JSON (0 nulls; counts exact). Lichess overlap: 10,376 rows,
95.5% non-mate sign agreement (2024-09: 95.6%), mean |cp| diff 59.9.

## 7. Eval-Conditioned Replication Results

Validation (9,442 rows, 3,524 games); 2024-09 values in parentheses:

| Model | val log_loss | 95% CI |
|---|---|---|
| B1 | 0.8803 (0.8813) | [0.8620, 0.8993] |
| B2 | 0.8668 (0.8684) | [0.8478, 0.8861] |
| B3 | 0.8549 (0.8533) | [0.8359, 0.8750] |
| E1 | 0.7531 (0.7568) | [0.7307, 0.7742] |
| E3 | 0.7463 (0.7514) | [0.7240, 0.7687] |
| E4 | 0.7344 (0.7377) | [0.7126, 0.7577] |
| E5 (best) | 0.7302 (0.7329) | [0.7093, 0.7524] |

Pairwise (all exclude zero, as in 2024-09): **E3→E4 −0.0120
[−0.0177, −0.0062] — PRIMARY TARGET REPLICATED**; E1→E3 −0.0068; E4→E5
−0.0042; B3→E1 −0.1018; B3→E5 −0.1248.

Per-checkpoint: move_10 −0.0002 (cz), move_20 −0.0005 (cz), move_30 −0.0218
(excl), move_40 −0.0625 (excl) — pattern reproduces.

## 8. Constraint Slice Replication Results

**P3 (localization target): REPLICATED** — under_60s −0.2468 (241 games,
descriptive; 2024-09 −0.2541), 60_180s −0.0442 [−0.0636, −0.0242] excludes
zero (−0.0534), over_180s −0.0066 [−0.0133, +0.0007] contains zero narrowly
(−0.0074 barely excluded) — the boundary cell flips at the resolvability
edge across months, consistent with a small residual effect; the gradient
(low-clock ≫ high-clock) reproduces.

P1 decidedness: equal −0.0187 (excl), slight −0.0068 (contains; was
−0.0096 excl), decided −0.0106 (excl), mate −0.0136 (287 games,
descriptive). P2 rating: middle bands exclude zero (−0.0121/−0.0119);
under_1200 contains (624 games); 2000_plus −0.0151 descriptive this month
(277 games). Exploratory: imbalance graded (large −0.0345 excl); terminal
sensitivity — delta unchanged (−0.0120) without terminal rows.

## 9. Month-to-Month Comparison

Full table in the cross-month report §7. Highlights: 2024-10 has ~4% fewer
10+0 games in the first 250k; rating distribution within 5 Elo of 2024-09;
DRAW rate identical (6.1%); termination mix similar; sign agreement with
Lichess cloud evals nearly identical (95.5% vs 95.6%). Baseline metrics
within ~0.002 across months.

## 10. Tests / Validation

- New tests: +7 (5 ecm reference-comparison incl. CLI-on/CLI-off; 2 slices
  payload-driven prose). Targeted suites: 177 passed.
- Full suite: **1,485 passed** (was 1,478), 0 regressions.
- Slice definitions unchanged since 9.2A — not tuned on 2024-10 results.
- Artifact validation: 251,356 prediction rows (4 × 62,839); probabilities
  sum to 1 within 1e-6; all five 2024-10 data artifacts verified gitignored.
- Language grep: only negated/caveated forms. Forbidden artifact scan: clean.

## 11. Data / Git Safety

All 2024-10 artifacts under `data/` (gitignored). Committed: 4 reports,
2 source files, 2 test files, ROADMAP, EXPERIMENT_LOG. No `git add .`; no
data staged; no model binaries/CSVs/plots. Full SF run executed only after
explicit approval.

## 12. Scientific Caveats

- Predictive associations on validation splits — **not causal**; reasoning
  quality **not directly measured**.
- Two adjacent months, one platform, one time control — external validity
  beyond these months is not proven.
- Stockfish depth=12 eval is position context, **not ground truth**.
- Degradation curves **not established**; ordered-bucket patterns only.
- under_60s and 2000_plus cells descriptive this month (<300 games).
- DRAW not solved (575/9,442 val rows; zero DRAW argmax).
- Player-level leakage unresolved; applies across months too.
- Test split untouched for selection. Phase 10 not started.

## 13. Acceptance Criteria

| Criterion | Status |
|---|---|
| A1/A2 source fixes with tests | DONE |
| Deterministic 2024-10 250k prefix parsed (tee-cached) | DONE |
| Clean/broad/primary counts documented | DONE |
| Game-level splits seed=42 | DONE |
| SF protocol: dry-run/medium/resume → approval → full run | DONE |
| SF coverage 100%, terminal rows documented (299) | DONE |
| B1/B2/B3 retrained; E1/E3/E4/E5 rerun | DONE |
| Overall E3→E4 replication reported vs 2024-09 | DONE — REPLICATED |
| Per-checkpoint + P3 slice replication reported | DONE — REPLICATED |
| Month-to-month comparison table | DONE |
| No test selection; no causal claims; slice defs untouched | DONE |
| 1,485 tests pass; reports deterministic (renderer-tested) | DONE |
| Data artifacts ignored and unstaged | DONE |

## 14. Suggested Commit

```bash
git add src/chess_mhsuc/constraint_slices.py
git add src/chess_mhsuc/eval_conditioned_modeling.py
git add tests/test_constraint_slices.py
git add tests/test_eval_conditioned_modeling.py
git add reports/cross_month_replication_2024_10_250k_v1.md
git add reports/eval_conditioned_modeling_2024_10_250k_v1.md
git add reports/constraint_slices_2024_10_250k_v1.md
git add reports/phase_reports/phase_9_3b_cross_month_replication_implementation.md
git add ROADMAP.md
git add EXPERIMENT_LOG.md
git commit -m "Ticket 9.3B: implement cross-month replication"
```

Do NOT stage `data/` (raw caches, interim, processed) or any Parquet/JSON
data artifacts.
