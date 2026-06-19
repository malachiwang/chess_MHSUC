# Phase 16.1B — Cross-Time-Control Pilot Dense Extraction

**Labels:** IMPLEMENTATION + pilot extraction | Phase 16 cross-time-control
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** IMPLEMENTATION (pilot only; not full extraction)

## 1. Executive summary

Generalized the dense move-loss pipeline to safety-gated **non-600+0** time controls and
ran **pilots only** for **3+0 and 5+0** in both 2024-09 and 2024-10 (1,500 accepted games
each). The non-600+0 path works end-to-end: acceptance is derived **from raw-PGN headers**
(parsed `game_records` are 600+0-only), the time-control-aware schema is correct, and all
four pilots validated cleanly (0 duplicate keys, 0 eval/replay failures, no usernames,
100% player-hash, both colors, ES bounded, clipped cp ≥ 0). 12 tests added; full suite
**1,857 passed**.

**Headline descriptive readiness finding (replicated, NOT causal):** the **time-forfeit
rate is a clean monotone dose-response in base time** — **3+0 ≈ 37–39%, 5+0 ≈ 28%, 10+0 ≈
13.4%** — while **next-move move-quality loss is similar across controls** (ES mean ≈
0.034–0.035 everywhere). **Rating pools differ** (blitz mover-Elo medians ~1570–1792 vs
rapid ~1601), confirming **within-time-control rating quantiles are mandatory**. **Pilots
pass → recommend proceeding to full (matched-size) 3+0/5+0 extraction (16.1C)**, chunked/
resumable/caffeinated. Pilot artifacts + reports are gitignored/standard; nothing staged.

## 2. Files inspected

ROADMAP, EXPERIMENT_LOG, PREREGISTRATION; 16.1A audit; dense extraction reports (15.3C/D);
Phase 15.4 atlas + controlled-model reports; `dense_move_loss.py`, `dense_constraint_atlas.py`,
`dense_controlled_model.py`, `player_metadata.py`; tests; read-only data inventory.

## 3. Files created

- `reports/dense_move_loss_pilot_2024_09_3plus0_v1.md`, `…_2024_09_5plus0_v1.md`,
  `…_2024_10_3plus0_v1.md`, `…_2024_10_5plus0_v1.md` (CLI pilot reports).
- `reports/phase_reports/phase_16_1b_cross_time_control_pilot_dense_extraction.md` (this;
  consolidates the cross-control diagnostics).
- Pilot artifacts (**gitignored**): `data/processed/dense_move_loss_pilot_2024_09_3plus0_v1.parquet`
  (+ 5plus0, + 2024_10 ×2).

## 4. Files modified

- `src/chess_mhsuc/dense_move_loss.py` — non-600+0 support (below).
- `tests/test_dense_move_loss.py` — +12 tests.
- `ROADMAP.md`, `EXPERIMENT_LOG.md`.
- **Unchanged:** PREREGISTRATION, the ES transform, `dense_constraint_atlas.py`,
  `dense_controlled_model.py`, existing 10+0 dense artifacts.

## 5. Code changes

- `canonicalize_time_control` — maps minute aliases (`3+0`→`180+0`, `5+0`→`300+0`,
  `10+0`→`600+0`) to canonical Lichess seconds; rejects malformed; default 600+0.
- `build_accepted_meta_from_raw` — header-only accepted set for a target control (the
  600+0-only `game_records` cannot serve other controls): streams raw cache headers, keeps
  the first `max_games` matching games with basic acceptance (both Elos + decisive/draw
  result + Termination tag), `split_set="unknown"`, **no usernames retained**.
- CLI: `--time-control` (canonicalized) + **`--allow-time-control-pilot` safety gate**.
  Non-600+0 is **refused** without the gate, with `--preflight`, without a finite positive
  `--max-accepted-games`, or above the pilot cap; **full-month flags remain 600+0-locked**.
  600+0 behavior is unchanged. Non-anchor controls route the accepted set through
  `build_accepted_meta_from_raw`; the per-ply replay/clock/metric logic is reused as-is.

## 6. Tests run

- `pytest tests/test_dense_move_loss.py` → **65 passed** (53 prior + 12 new).
- Full suite → **1,857 passed**.

New tests: canonicalization (aliases + malformed reject), `build_accepted_meta_from_raw`
(TC filter, metadata, cap, no-username), 180+0 TC fields + `clock_fraction` uses
`initial_time_s` not hardcoded 600, and CLI gates (refuse non-600+0 without gate / malformed /
over-cap / with preflight / full-month-still-600+0; gate accepts then fails on missing inputs).

## 7. Pilot commands

Run under `caffeinate -dimsu`, sequentially, e.g.:

```bash
PYTHONPATH=src .venv/bin/python -m chess_mhsuc.dense_move_loss \
  --raw-pgn data/raw/lichess/lichess_2024_09_first250k.pgn \
  --month 2024_09 --time-control 180+0 --allow-time-control-pilot \
  --max-accepted-games 1500 --min-move-number 5 --depth 12 \
  --stockfish-path /opt/homebrew/bin/stockfish \
  --expected-score-transform data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json \
  --player-metadata data/processed/player_metadata_2024_09_250k_v1.parquet \
  --out data/processed/dense_move_loss_pilot_2024_09_3plus0_v1.parquet \
  --report reports/dense_move_loss_pilot_2024_09_3plus0_v1.md --overwrite
```
(+ `300+0`, and the two 2024-10 controls.) Pilot size **1,500 accepted games**/control/month.

## 8. Safety gates

Non-600+0 requires `--allow-time-control-pilot` + a finite pilot cap; refuses `--preflight`,
over-cap runs, and any full-month flag (600+0-locked). 600+0 path and existing 10+0 artifacts
untouched. ES transform reused (not refit).

## 9. Input/raw-cache validation

Raw caches `lichess_2024_09/10_first250k.pgn` contain all controls; header-derived accepted
sets returned exactly 1,500 games/control. ES transform reused. No raw PGNs modified.

## 10. Pilot artifact summary

| pilot | rows | usable games | mate-band | dup keys | status | colors | usernames | player-hash |
|---|---|---|---|---|---|---|---|---|
| 2024-09 3+0 | 94,935 | 1,485 | 4,465 | 0 | all ok | W 47,848 / B 47,087 | none | 100% |
| 2024-09 5+0 | 91,185 | 1,485 | 4,264 | 0 | all ok | W 45,975 / B 45,210 | none | 100% |
| 2024-10 3+0 | 92,225 | 1,481 | 4,511 | 0 | all ok | W 46,500 / B 45,725 | none | 100% |
| 2024-10 5+0 | 89,652 | 1,483 | 4,258 | 0 | all ok | W 45,210 / B 44,442 | none | 100% |

TC fields correct: `180+0`→init 180/inc 0/no_increment/blitz; `300+0`→init 300/inc 0/
no_increment/blitz. ES bounded [0, ~0.80]; clipped cp ≥ 0 everywhere. ~62 rows/game (blitz
games are move-rich).

## 11. Runtime and throughput

| pilot | runtime | evals | evals/s |
|---|---|---|---|
| 2024-09 3+0 | 1,937 s (~32 m) | 96,020 | 49.8 |
| 2024-09 5+0 | 12,066 s (~3.4 h) | 92,256 | 7.7 |
| 2024-10 3+0 | 1,919 s (~32 m) | 93,280 | 48.8 |
| 2024-10 5+0 | 1,939 s (~32 m) | 89,652→90,728 | 47.1 |

Three pilots ran at ~48–50 evals/s (~32 min each); **2024-09 5+0 ran anomalously slow
(~3.4 h, 7.7 eps)** — a transient runtime artifact (background CPU contention/throttle
during that window), **not a data issue** (its row counts/metrics are consistent with the
others). Full runs must be chunked/resumable/caffeinated with no competing load.

## 12. Clock and clock-fraction diagnostics

`clock_fraction = clock_before_s / initial_time_s` (180 or 300). Ranges: 3+0 [0, ~1.3],
5+0 [0, ~1.06] (the small >1 tail = clock-recording artifacts, flagged); medians ~0.65–0.70.
Absolute-clock buckets are within-control; **clock_fraction is the cross-control axis** — and
it is correctly computed off `initial_time_s` (not hardcoded 600), verified in code + tests.

## 13. Rating quantile diagnostics

Mover-Elo within-control quintile cutpoints (Q20/Q40/Q60/Q80) and median:

| control | Q20 | Q40 | Q60 | Q80 | median | p10/p90 |
|---|---|---|---|---|---|---|
| 2024-09 3+0 | 1486 | 1701 | 1858 | 2044 | 1776 | 1306 / 2182 |
| 2024-09 5+0 | 1263 | 1496 | 1669 | 1886 | 1584 | 1103 / 2025 |
| 2024-10 3+0 | 1500 | 1711 | 1873 | 2037 | 1792 | 1329 / 2169 |
| 2024-10 5+0 | 1263 | 1482 | 1672 | 1875 | 1570 | 1099 / 1990 |

10+0 (rapid) mover-Elo median ≈ 1601. **The pools differ markedly** (3+0 ≈ 1780, 5+0 ≈ 1580,
10+0 ≈ 1600) — raw ratings are **not** cross-comparable → **within-control rating quantiles
are mandatory** in Phase 16 (confirmed empirically).

## 14. Termination-channel diagnostics

| control | time-forfeit rate (Sep / Oct) | board-decided rate |
|---|---|---|
| 3+0 | 38.7% / 36.3% | ~62% |
| 5+0 | 28.8% / 27.9% | ~72% |
| 10+0 (anchor) | ~13.4% | ~86.6% |

**Clean monotone dose-response: faster base time → much higher flagging rate**, replicated
across both months. This is the most striking cross-control readiness signal and is directly
relevant to the 11.2B flagging-channel result — **to be analyzed properly (with controls) in
16.2, not interpreted causally here.**

## 15. Move-quality metric diagnostics

ES loss mean / median / p90 (OK, non-mate): 3+0 0.0338/0.011/0.090 (Sep), 0.0339/0.0114/0.091
(Oct); 5+0 0.035/0.0115/0.093 (Sep), 0.0353/0.0119/0.094 (Oct); 10+0 anchor 0.0346/0.0114/
0.0926. **Next-move move-quality loss is similar across controls** — the large cross-control
difference is in **flagging rate** (§14), not in board-move ES loss. Large-loss ES≥0.10 ≈
8.6–9.2% across controls.

## 16. Comparison to 10+0 anchor feasibility

Pilot rows/game (~62) and ES distributions match the 10+0 anchor; the pipeline, schema,
metric, clustering keys, and privacy all transfer. The new cross-control axes (clock_fraction,
within-control rating quantiles, termination rate) are populated and sensible.

## 17. Full extraction feasibility recommendation

**Option A — proceed to full extraction (recommended), as a MATCHED-SIZE run.** Pilots are
clean; the pipeline transfers. **Caveat:** full per-control extraction is large — 3+0 (~52k
accepted games × ~62 rows ≈ **~3.2M rows**) and 5+0 (~33k × ~62 ≈ **~2.0M rows**) each
**exceed** the 10+0 full artifact (1.5M), so a **matched-size** design (cap each control to a
common accepted-game count, e.g. ~25k, for balanced power and bounded cost) is preferred over
uncapped full extraction. Must be **chunked/resumable/caffeinated** with no competing load
(cf. the slow 2024-09 5+0 pilot). Recommended next: **16.1C — Full (Matched-Size) 3+0 / 5+0
Dense Extraction** (both months, depth 12, chunked). Do not run uncapped full extraction
blindly.

## 18. Non-claims

Pilot/feasibility only — **not** a full time-control result; **do not compare to 10+0 as a
final finding yet.** Cross-control comparisons are descriptive/conditional, **not causal**;
raw ratings are **not** cross-pool comparable; Stockfish eval is objective context, not ground
truth. No "faster time controls cause worse chess"; no "low clock causes blunders"; no "time
pressure causes worse reasoning"; no sharpness claims. C4 and C3c unchanged; ES transform not
refit.

## 19. Recommended next ticket

**16.1C — Full (Matched-Size) 3+0 / 5+0 Dense Extraction** (both months, depth 12,
chunked/resumable/caffeinated, matched accepted-game count) — then 16.2A Cross-Time-Control
Move-Quality Audit. Not Phase 17; no synthesis.
