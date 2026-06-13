# Next-Move Loss Extraction — Combined 2024-09 and 2024-10

**Ticket:** 15.0C — Full Next-Move Loss Extraction + Expected-Score Transform

## 1. Executive summary

The full checkpoint-level next-move loss measurement layer (Contrast C4) is complete for
both independent months. **126k checkpoint moves evaluated end-to-end with 0
reconstruction failures, 0 engine failures, and 0 FEN-hash mismatches.** Both clipped
centipawn loss and expected-score loss (a single pooled-train logistic transform) are
available, and the two months agree closely (median clipped cp loss 19 both; ES median
~0.010 both). This is measurement/extraction, not modeling — no causal claims, no
degradation-curve language; Stockfish depth-12 eval is objective position context, not
absolute ground truth.

## 2. Full extraction status

| | 2024-09 | 2024-10 |
|---|---|---|
| Attempted | 65,368 | 62,839 |
| OK evaluated | 64,371 | 61,868 |
| No next move | 997 | 971 |
| FEN errors / engine errors / hash mismatches | 0 / 0 / 0 | 0 / 0 / 0 |
| Runtime | 1,471 s (~24.5 min) | 1,419 s (~23.7 min) |
| Artifact (gitignored) | `next_move_loss_2024_09_250k_v1.parquet` | `next_move_loss_2024_10_250k_v1.parquet` |

## 3. Month-by-month reconstruction/evaluation success

Both months: 100% of OK rows had their reconstructed checkpoint FEN match the stored
`fen_hash` (0 mismatches), validating the raw-PGN replay path end-to-end. ~1.5% of
checkpoints are no-next-move (game ended at the checkpoint) and excluded by definition.

## 4. Month-by-month loss summaries (OK, non-mate-band)

| Metric | 2024-09 (n=61,956) | 2024-10 (n=59,625) |
|---|---|---|
| Clipped cp loss mean | 58.3 | 57.4 |
| median | 19 | 19 |
| p75 / p90 | 69 / 159 | 68 / 157 |
| zero-loss % | 33.3 | 33.0 |
| >100cp % / >200cp % | 17.3 / 7.3 | 17.0 / 7.0 |
| Expected-score loss mean | 0.0345 | 0.0341 |
| median / p90 | 0.0102 / 0.0949 | 0.0101 / 0.0933 |
| >0.10 % | 9.3 | 9.2 |

Cross-month agreement is strong on every statistic.

## 5. Expected-score transform status

**Implemented (Option A).** One pooled logistic `ES(cp)=1/(1+exp(−cp_clipped/scale))`,
scale=348.4, fit by bounded MSE to White expected score on 89,764 TRAIN rows from both
months (MSE 0.183), cp clipped ±1000, mate-band excluded from summaries. Train-only;
applied unchanged to pre/post and to both months for comparability. cp lineage preserved
(`cp_loss`/`clipped_cp_loss` retained; never silently replaced). Transform metadata:
`data/processed/next_move_expected_score_transform_2024_09_2024_10_v1.json` (gitignored).

## 6. Termination-channel summary

Both months: board-decided vs time-forfeit games have **near-identical checkpoint
next-move loss** (2024-09 clipped cp mean 58.4 vs 57.6; 2024-10 57.4 vs 57.4; ES means
within 0.0009). Descriptive reading: the 11.2B outcome residual that lives in the
time-forfeit channel does **not** correspond to worse board moves at these checkpoints —
consistent with flagging being a clock-exhaustion mechanism rather than a move-quality
effect. Descriptive only; not causal.

## 7. Clock-bucket summary

OK rows by mover clock: 2024-09 over_180s 60,656 / 60_180s 2,855 / under_60s 860;
2024-10 over_180s 58,097 / 60_180s 2,879 / under_60s 892. As in 9.2B, numbered
checkpoints are overwhelmingly high-clock (clock×checkpoint confound) — any clock×loss
analysis must bucket within checkpoint and treat under_60s cells as descriptive
(sub-threshold).

## 8. Depth-parity sensitivity summary

2024-09 400-row depth-13 post-move re-evaluation: mean clipped cp loss 57.8 (d12) vs 58.0
(d13), per-row mean absolute delta 14cp, median delta 0. The pre/post search-parity
asymmetry is benign in aggregate; the depth-12 convention is retained for both months.

## 9. Implications after 11.2B/11.2C

11.2B/11.2C reframed the outcome clock residual as primarily the flagging channel and
moved the board-play-quality question to C4 (this layer). The extraction is now ready to
answer that question descriptively (15.1A) and, after player-leakage hardening, with
controls (15.1B). The §6 near-identical board-decided/time-forfeit checkpoint loss is an
early, descriptive sign consistent with the flagging-channel reframing — but no
conclusion about low clock and move quality should be drawn until the Constraint Atlas
curves and controlled models are run.

## 10. Readiness for Constraint Atlas curves

**Ready.** Both months' artifacts carry the loss metrics, ES, ratings, clocks, time
buckets, eval-band-derivable pre-cp, phase (checkpoint), termination, and split — the full
stratification set for 15.1A. Expected-score loss is available as the intended C4
headline metric.

## 11. Recommended next ticket

**15.1A — Constraint Atlas Descriptive Curves Audit** (design the descriptive
curve/stratification set against the extracted artifacts; bootstrap-CI and cell-count
conventions; no controlled modeling). Player-leakage hardening (11.3A/B) remains required
before 15.1B controlled modeling.
