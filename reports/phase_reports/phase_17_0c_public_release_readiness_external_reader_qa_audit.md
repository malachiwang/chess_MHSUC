# Phase 17.0C — Public Release Readiness and External-Reader QA Audit

## 1. Executive verdict

**The repository is release-ready and public-showable.** Opened cold, an external reader can
understand the project, trust the (carefully non-causal) claims, view the headline figures, run the
test suite, and see the engineering scale — without being misled. No blocking defects were found.
One **cosmetic** figure observation (H6 y-axis label left-clipping) is recorded as optional polish; it
does not mislead and fixing it would require regenerating a figure, which is out of scope for an
audit-only ticket. This ticket modified only `ROADMAP.md`, `EXPERIMENT_LOG.md`, and this report.
Nothing staged, nothing committed.

## 2. Working tree and commit base

- Start: `git status --short` → clean working tree.
- Commit base: `c5c9449 Ticket 17.0B: publish replication benchmark package` (HEAD), preceded by
  `4841e6e Ticket 17.0A …`. Matches the expected post-17.0B state.

## 3. Public-reader first-screen audit

`README.md` first screen communicates, in order: what the project studies (human move quality under
clock constraints with a time-forfeit vs board-play decomposition); scale (**145,000+** games,
**8.3M+** move-level observations); **3** time controls; **2** independent months; the central
descriptive finding; an explicit **predictive/descriptive, not causal** boundary; and links to the
benchmark report, headline figures, appendix index, and reproducibility. It does **not** open with
ticket history, a methodology dump, a broad-novelty claim, vague "AI chess" framing, or jargon before
plain English. **Pass.**

## 4. Claim-language audit

The forbidden-term grep over `README.md`, `reports/benchmark_report.md`,
`reports/appendix_figure_index.md`, `NOTICE.md`, `CITATION.cff` returned only:

- `causal` / `causes` / `ground truth` — every occurrence is a **negation/disclaimer** ("predictive
  and descriptive, **not** causal"; "We do **not** claim that time pressure *causes* worse reasoning";
  "objective position context, **not** ground truth"). Acceptable.
- `novel` / `state of the art` — appear only inside **disclaimers** ("What this project does **not**
  claim: a new metric … a causal effect, or state of the art"; "reframed the project from 'novel' to
  'rigorous replication …'"). Acceptable.
- `skill buffer` — appears only as the disclaimed phrase ("so no 'skill buffers time pressure'
  claim"). Acceptable.

No misleading, unsupported, or must-fix wording. All boundaries (descriptive-not-causal; Stockfish as
context not ground truth; no broad novelty; no "humans reason worse"; no universal rating buffer; no
solved sharpness; no SOTA prediction) are preserved. **Pass.**

## 5. Link and path audit

- Every relative Markdown link in `README.md`, `reports/benchmark_report.md`,
  `reports/appendix_figure_index.md`, `NOTICE.md` resolves (programmatic check relative to each file's
  own directory): **all links resolve.**
- Appendix-table figure references (not `[](…)` links) also verified on disk: 10/10 cross-time-control
  figures and 9/9 rating-moderation figures exist; referenced sharpness (15.5c) and prior-art (16.2g)
  reports exist.
- Private-path grep (`/Users/`, `chess-prior-art`, `/tmp/`, `.venv`, tracked-Parquet) found only:
  (a) the generic documented `.venv` create/activate commands, and (b) the repo-relative
  `data/processed/…parquet` regeneration command — which the README explicitly flags as **gitignored
  and not shipped**. No user-specific absolute paths, no private workspace paths, no broken image
  links, no treating ignored Parquets as downloadable repo files. **Pass.**

## 6. Figure audit

All 12 PNGs + `count_tables.md` present in `reports/figures/benchmark/`. Each opens, is non-blank, and
is README-width legible. Visual inspection (H1, H2, H5_3plus0, H6 read directly; H3/H4 dimensions and
naming verified):

| Figure | px | size | open | title/axes/legend | "game-normalized" shown | sparse explained | caption matches estimand |
|---|---|---|---|---|---|---|---|
| H1 | 880×505 | 32K | yes | yes (labeled bars 0.29/0.30, 0.23, 0.12) | n/a (game-level rate) | n/a | yes |
| H2 | 1760×505 | 132K | yes | yes (3 panels, board-decided dashed below all-games at low s) | yes (title + y-axis) | n/a | yes |
| H3 ×3 | 935×550 | 116–132K | yes | yes (Elo bands, ranges in legend) | yes | n/a | yes |
| H4 ×3 | 935×550 | 84–132K | yes | yes (clock-state series) | yes | n/a | yes |
| H5 ×3 | 990×550 | 40–48K | yes | yes (labeled axes + colorbar) | yes (title + colorbar) | yes (in-axes "masked 113/288 cells (<200 rows or <50 games)") | yes |
| H6 | 1540×505 | 48K | yes | yes (board-decided < all-games every cell, both months) | yes (title; y-axis **clipped**, see polish) | n/a | yes |

Benchmark-figure footprint: **1.1 MB** total (largest single PNG 132 KB) — appropriate for a tracked
portfolio package. **Pass** (one cosmetic note in §17).

## 7. Clean-clone reproducibility audit

`git clone` to `/tmp/chess_mhsuc_release_audit`: clean status; full public package present
(`README.md`, `LICENSE`, `NOTICE.md`, `CITATION.cff`, `requirements.txt`, both report MDs, 13 files in
`reports/figures/benchmark/`). `benchmark_figures` imports and `--help` works from the clone.
**0 Parquet files** in the clone (dense datasets correctly gitignored / not shipped). Full test suite
run from the primary repo's `.venv` (see §11). No installation step was performed inside the clone
(would re-resolve the same `requirements.txt`; not run to avoid network/dep churn, and explicitly out
of scope to "fix" anything). **Pass.**

## 8. Figure-regeneration boundary

Running the documented regeneration command **inside the clean clone** (no Parquets) fails immediately
and clearly: `FileNotFoundError … data/processed/dense_move_loss_2024_09_3plus0_24k_v1.parquet`. The
README honestly states the dense Parquets are gitignored and must be rebuilt from raw Lichess PGNs via
`dense_move_loss.py` + local Stockfish; it does **not** imply a fresh cloner can regenerate figures
immediately. Tracked figures are viewable without data; regeneration code and complete commands exist;
required data paths are honestly described. **Pass.**

## 9. License, notice, and citation audit

- `LICENSE`: standard **unmodified MIT**, `Copyright (c) 2026 Malachi Wang`, no third-party scope
  edits inside the license body. **Pass.**
- `NOTICE.md`: states project code/docs are MIT; Stockfish (GPL-3.0) external/not redistributed;
  Lichess data under its own terms; referenced repos (chess-analysis AGPL, maia-chess GPL, maia2 MIT,
  oxi no-license, allie MIT, Arrakis AGPL) cited for attribution only; **no third-party source copied
  or vendored.** **Pass.**
- `CITATION.cff`: validates (`cff-version: 1.2.0`, `license: MIT`, `repository-code:
  https://github.com/malachiwang06-lgtm/chess-MHSUC`, no `your-handle`/`placeholder`). No fabricated
  DOI, no unsupported venue; title/authors appropriate. The repository URL should be confirmed to
  resolve to the actual public repo before announcement (§17). **Pass.**

## 10. Repository-size and artifact audit

- Largest tracked files are docs and figures only: `EXPERIMENT_LOG.md` (204 KB), then PNGs ≤132 KB.
- No tracked Parquet / PGN.zst / model / checkpoint / DB / CSV. The only tracked data-like file is the
  **allowed** tiny synthetic fixture `tests/fixtures/tiny_clock_eval_game.pgn`.
- Nothing untracked-and-unignored (clean tree); `.DS_Store`/`*.pyc` on disk are all gitignored and
  none are stageable; `data/processed` not tracked. `.gitignore` is adequate. **Pass.**

## 11. Test audit

- Targeted: `pytest tests/test_benchmark_figures.py -q` → **26 passed** (0.51s).
- Full: `pytest -q` → **1,951 passed, 3 warnings** in 86.30s. The 3 warnings are pre-existing sklearn
  `y_pred contains classes not in y_true` notices from `test_eval_conditioned_modeling.py` /
  `test_baselines.py` — not new, not from the benchmark package. **Pass.**

## 12. Public narrative audit

`benchmark_report.md`: the main result is graspable in under 2 minutes (executive summary answers
"flagging vs worse board play" plainly); prior work is presented **before** positioning; replication
vs extension is separated; the termination-channel decomposition is explained clearly; a dedicated
"Three relationships, kept distinct" paragraph separates marginal/conditional/board-decided so a reader
cannot mistake the conditional gradient for a raw-aggregate effect; limitations and reproducibility
boundaries are explicit; length is appropriate for a portfolio artifact (single report + portfolio
summary). `README.md`: communicates scale and competence quickly, embeds visual evidence via the H1–H6
table, avoids over-academic clutter, links directly to the resume-ready portfolio summary, and reads as
a finished project. **Pass.**

## 13. Resume and portfolio consistency audit

Every advertised number reconciles to `count_tables.md`:

- 145,000+ games → **145,020** (sum of game counts). ✓
- 8M+ / 8.3M+ move-level observations → **8,353,475** headline rows. ✓
- 3 time controls (3+0/5+0/10+0), 2 monthly samples (2024-09/10). ✓
- Time-forfeit rates 0.29/0.30, 0.23/0.23, 0.12/0.12 → match H1 and count_tables. ✓
- 12 benchmark figures → 12 PNGs. ✓
- Tests: public docs say "~1,900+"; actual is **1,951** (honest lower-bound phrasing). ✓
- "500-draw clustered bootstrap" is **not** asserted in the public package (avoids an unverified
  claim) — acceptable.

Resume bullets claim no novelty, no causal effect, no SOTA model, no human-reasoning-degradation; the
strongest phrasing is "a decomposition not found in directly inspected prior work," which matches the
preregistered discipline. **Pass.**

## 14. Governance audit

`ROADMAP.md` and `EXPERIMENT_LOG.md` already record: 17.0B complete; package is public-facing
replication/benchmark; **no active next research ticket**; increment analysis, new modeling, sharpness,
1+0, preprint all **deferred**; broad-novelty and causal claims **permanently prohibited** in the
package. This ticket adds the 17.0C release-readiness outcome (below) without opening a new research
phase. **Pass.**

## 15. Defects found

**Blocking: none.**

Cosmetic / minor (1):

1. **H6 y-axis label left-clipping.** The label renders as "ne-normalized mean ES loss at critical
   clock (≤5% of base time)" — the leading "game-" is cut off at the left figure margin. Non-misleading
   (title and report caption both say "game-normalized"; the colorbar/axes in other figures render the
   full phrase). Cosmetic only.

## 16. Required fixes before public release

**None.** No blocking public-release defect was found. The package is releasable as-is.

## 17. Optional polish

1. Fix the H6 y-axis label clipping by widening the left margin / shortening the label, then
   regenerate H6 (a figure change — defer to a small follow-up implementation ticket, not this audit).
2. Before public announcement, confirm `https://github.com/malachiwang06-lgtm/chess-MHSUC` actually
   resolves to the pushed public repository (CITATION.cff / README depend on it).
3. Optionally state the exact test count (1,951) instead of "~1,900+" once it stabilizes; current
   lower-bound phrasing is honest and fine.

## 18. Final release-readiness decision

**READY FOR PUBLIC RELEASE.** First-screen, claims, links, figures, clean-clone structure,
regeneration boundary, license/notice/citation, repo size/artifacts, tests (26 / 1,951), narrative,
resume consistency, and governance all pass. The single recorded item is cosmetic and optional. This
audit changed only governance + report files; source, tests, README, figures, data, and
PREREGISTRATION are untouched.
