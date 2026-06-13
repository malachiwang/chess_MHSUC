# Ticket 11.2B — Termination Decomposition Implementation

**Labels:** ANALYSIS/ML | IMPLEMENTATION
**Date:** 2026-06-12
**Owner:** Malachi Wang

## 1. ELI5 / TLDR

Implemented locked Contrast C2: filter the frozen E3/E4 validation predictions by
termination channel and ask whether the clock residual survives among games decided
on the board. **It does not.** Board-decided delta: +0.0010 (CI contains zero) in
2024-09 and +0.0060 (CI excludes zero, *positive*) in 2024-10; time-forfeit games
carry −0.118/−0.131. Per the pre-registered collapse branch, the central claim is
re-framed honestly: the replicated clock residual predominantly quantifies the
time-forfeit/flagging channel. This is a clean, replicated, pre-registered result —
the contrast did exactly what it was designed to do.

## 2. Files created

| File | Content |
|---|---|
| `src/chess_mhsuc/termination_decomposition.py` | 9 functions + CLI; reuses `constraint_slices` loader and paired-bootstrap cell machinery; no retraining anywhere |
| `tests/test_termination_decomposition.py` | 39 tests (pure functions + synthetic frames; no real data) |
| `reports/termination_decomposition_2024_09_250k_v1.md` | Month report (rendered, deterministic) |
| `reports/termination_decomposition_2024_10_250k_v1.md` | Month report (rendered, deterministic) |
| `reports/termination_decomposition_combined.md` | Combined two-month interpretation |
| `reports/phase_reports/phase_11_2b_termination_decomposition_implementation.md` | This report |

## 3. Files modified

| File | Change |
|---|---|
| `PREREGISTRATION.md` | C2 wording fix applied **before any results were computed** (logged): primary = prediction-side filter of frozen models, no retraining; refit = optional secondary with different estimand. Removed the contradictory "same frozen models, refit" stub phrase |
| `EXPERIMENT_LOG.md` | EXP-015 added |
| `ROADMAP.md` | Next-ticket pointer updated (claim-reframing audit before 11.3A) |

## 4. Commands run

```
PYTHONPATH=src .venv/bin/pytest tests/test_termination_decomposition.py   # 39 passed
PYTHONPATH=src .venv/bin/pytest                                            # full suite
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.termination_decomposition \
  --dataset-id lichess_ten_zero_2024_09_250k_v1 --version-tag 2024_09_250k_v1 --overwrite
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.termination_decomposition \
  --dataset-id lichess_ten_zero_2024_10_250k_v1 --version-tag 2024_10_250k_v1 --overwrite
```

(CLI defaults derive artifact paths from `--version-tag`; the ticket's two-argument
form works as specified.)

## 5. Results summary

| Group | 2024-09 | 2024-10 |
|---|---|---|
| All games | −0.0138 [−0.0186, −0.0091] | −0.0120 [−0.0177, −0.0062] |
| Board-decided | +0.0010 [−0.0029, +0.0049] cz | +0.0060 [+0.0015, +0.0109] excl (positive) |
| Time-forfeit | −0.1183 [−0.1423, −0.0978] | −0.1305 [−0.1525, −0.1091] |
| Retained fraction | 0.07 | 0.50 (sign-reversed — overstates retention) |

Late-clock board-decided: 60_180s −0.0294 (excl) in 2024-09 but −0.0061 (cz) in
2024-10 — the localized board-decided residual does **not** replicate; under_60s
flips to ~+0.17 in both months (descriptive, ~100 games) — among flagging survivors,
clock features actively mislead.

## 6. Implementation notes

- One interpretation-logic bug was found and fixed **during** implementation (before
  reports were finalized): the "not merely flagging" branch lacked a sign guard, and
  `retained_fraction` hid sign reversals. Fixed with a `sign_flipped` flag + sign-aware
  branching; covered by 3 new tests.
- Channel taxonomy per 11.2A: binary `time_forfeit`/`board_decided` primary;
  descriptive `normal_decisive` (mate OR resignation — not separable) / `normal_draw`
  / `rules_infraction_or_other` (1 game per month).
- No JSON/Parquet outputs created (per ticket guidance); reports only.

## 7. Tests / validation

- New suite: **39 passed** (channel mapping incl. boundary vocab; binary mapping;
  join validation failures; retained fraction incl. near-zero and sign-flip; delta
  sign convention with manual check; threshold/descriptive behavior; determinism;
  report sections/caveats; forbidden-language with negated-caveat awareness).
- Full suite: **1,524 passed** (was 1,485; +39), 0 regressions.
- Safety greps: "causes worse reasoning" only in negated caveat contexts;
  "degradation curve" only in caution contexts; the contradictory
  "same frozen models, refit" phrase is gone.

## 8. Preregistration status

C2 executed as pre-registered after a logged pre-implementation wording
clarification. The collapse branch applies. Downstream contrasts (C3 sharpness
moderation; v11 framing) assumed a surviving board-decided residual and need a
re-scoping audit before implementation — permitted under the revision policy because
their inputs do not yet exist.

## 9. Data / git safety

No data artifacts created or staged; predictions/features read-only; no retraining;
no Stockfish; nothing staged or committed.

## 10. Recommended next ticket

**Claim-reframing audit (11.2C or equivalent) before 11.3A**: revisit the v11 novelty
lane and the C3/C4 framing given the flagging-channel finding. Candidate re-framings:
(a) flagging-risk prediction as the explicit object; (b) finer-resolution
board-decided residual analysis; (c) pivot weight toward the move-quality bridge
(C4), which does not depend on outcome deltas.
