# Phase 17.0D — Final Public Polish, GitHub Rendering, and Release Tag Audit

## 1. Executive verdict

**The repository is ready for public use.** The single cosmetic defect carried over from 17.0C — the
H6 y-axis label clipping — is fixed deterministically, touching only `benchmark_figures.py` and
regenerating only `H6_month_replication_summary.png` (H1–H5 byte-identical, `count_tables.md`
unchanged). The plotted estimand is unchanged. Tests remain green (26 targeted / 1,951 full, 3
pre-existing warnings). The GitHub remote is reachable and the repository URL matches `CITATION.cff`.
No framing change, no new research, no data/model/Stockfish activity. One operational reminder: the H6
fix must be committed and pushed for GitHub to render the corrected figure (it currently shows the
pre-fix H6). Nothing staged, nothing committed.

## 2. Commit base and working tree

- Start: clean working tree; HEAD = `c3483bf Ticket 17.0C: verify public release readiness` (17.0C
  committed and, per §6, pushed). Audit proceeded.

## 3. Model/framing clarification

chess-MHSUC does **not** use a literal decision-tree model. The final public package uses
**game-normalized descriptive benchmark figures** plus previously completed **controlled statistical
comparisons**. The main public contribution is a **reproducible replication/benchmark study** that
separates the clock-related final-outcome signal into a **mechanical time-forfeit channel** and a
**board-decided move-quality channel**. It is **not** described as a decision-tree model, a novel ML
model, a state-of-the-art chess predictor, a causal study, or a proof that low time causes worse
reasoning. Framing unchanged from 17.0A–17.0C.

## 4. H6 cosmetic fix

Root cause: the H6 y-axis label (`"game-normalized mean ES loss at critical clock (≤5% of base
time)"`) is rotated 90°, so its **length runs vertically**; on the short (4.6-inch-tall) figure it
overflowed the axis height and `tight_layout` clipped the start of the text ("game-") at the bottom.

Fix (in `src/chess_mhsuc/benchmark_figures.py`, H6 block only):
- Shortened the y-axis label to `"game-normalized mean ES loss"` (fits the axis height).
- Moved the precise threshold into the suptitle, which now reads
  `"H6 — Month replication: critical-clock (≤5% base time), all games vs board-decided (board-decided
  lower = time-forfeit attenuation; Sep≈Oct = replication)"` — kept to ~the original (proven-fitting)
  length by dropping the redundant word "move-quality", so the suptitle does not overflow horizontally.

The estimand is unchanged: game-normalized expected-score loss at critical clock, all-games vs
board-decided, by control and month. No scientific content or values changed. No regression test was
added: the change is a string-only cosmetic edit, no test asserts the H6 label/title text, and a
literal label-string assertion would be brittle without detecting actual clipping.

## 5. Figure regeneration and visual inspection

Regenerated via the existing CLI over the six existing dense Parquets (read-only; no extraction, no
Stockfish). Result: **only `H6_month_replication_summary.png` changed.** H1–H5 PNGs are
byte-identical (sha256 match before/after); `count_tables.md` is byte-identical
(`0f392a38…`). `git status reports/figures/benchmark` shows only H6 modified.

## 6. GitHub rendering audit

- `git remote get-url origin` = `https://github.com/malachiwang06-lgtm/chess-MHSUC.git`.
- `git ls-remote origin refs/heads/main` = `c3483bf…` = **local HEAD** → the remote is reachable and
  17.0C is pushed.
- Local Markdown/link/figure/CFF audit (carried from 17.0C, re-confirmed): all relative links resolve,
  all referenced figures exist, no private local paths, no oversized files, LICENSE/CITATION valid.
- **GitHub rendering not browser-verified** (not fabricated): I did not open the rendered GitHub page.
  Because the pushed commit equals local HEAD, GitHub currently displays the **pre-17.0D** README and
  the **pre-fix (clipped) H6**. After committing and pushing 17.0D, the corrected H6 will render.

## 7. Repository URL and citation audit

`CITATION.cff` `repository-code` = `https://github.com/malachiwang06-lgtm/chess-MHSUC`, which matches
the configured `origin` remote exactly. The only GitHub URL in the public docs is this CITATION field
(README/LICENSE reference NOTICE/LICENSE relatively, not a hardcoded GitHub URL). **URL is correct for
the present remote**; it should be updated only if Malachi later changes his GitHub username and the
remote. No change made in this ticket.

## 8. Test-count consistency

Public docs (`README.md`, `reports/benchmark_report.md`) state "~1,900+ tests" — conservative and
correct against the actual full-suite count of **1,951**. Left as "~1,900+" (acceptable lower-bound
phrasing; not changed). No inconsistency.

## 9. Test results

- Targeted: `pytest tests/test_benchmark_figures.py -q` → **26 passed** (0.33s).
- Full: `pytest -q` → **1,951 passed, 3 warnings** (104.50s). The 3 warnings are the pre-existing
  sklearn `y_pred contains classes not in y_true` notices from
  `test_eval_conditioned_modeling.py` / `test_baselines.py` — not new, not from the benchmark package.

## 10. Forbidden artifact and size checks

- No raw data, dense Parquets, model/checkpoint files, or caches staged or untracked-and-unignored;
  `data/` clean. No third-party prior-art clones inside the repo (they live under
  `/Users/malachiwang/chess-prior-art/`, outside the repository).
- No forbidden file types tracked (`*.parquet` / `*.pgn.zst` / `*.onnx` / `*.pt` / `*.pth`); the only
  tracked data-like file remains the allowed tiny synthetic fixture `tests/fixtures/tiny_clock_eval_game.pgn`.
- Largest tracked file is `EXPERIMENT_LOG.md` (208 KB); benchmark figures total **1.1 MB**
  (H6 now 41 KB, was 48 KB). Sizes remain reasonable.

## 11. Defects found

- **Fixed:** H6 y-axis label clipping (the only 17.0C-recorded cosmetic defect).
- **No new defects.** No blocking issues.

## 12. Required fixes before public use

**None remaining.** (Operational, not a code fix: commit + push 17.0D so GitHub renders the corrected
H6 and updated governance.)

## 13. Optional future polish

1. Confirm the rendered GitHub page in a browser after pushing 17.0D (figures display, README renders,
   CITATION/LICENSE recognized).
2. Consider a tagged release (e.g., `v1.0`) for a stable citation anchor.
3. Optionally tighten "~1,900+ tests" to the exact "1,951 tests" once it stabilizes (current phrasing
   is fine).
4. Update `CITATION.cff` / remote only if the GitHub username changes.

## 14. Final public-use decision

**READY FOR PUBLIC USE.** The cosmetic H6 clipping is resolved with a minimal, deterministic,
estimand-preserving change; all other figures and aggregation counts are unchanged; tests pass; the
remote URL is correct and reachable. The package is suitable for GitHub, LinkedIn, resume, and
outreach once 17.0D is committed and pushed.
