# Clock Association Robustness — 2024_09_250k_v1

**Ticket:** 15.1F — Clock Association Robustness Implementation (Contrast C4)

## 1. Executive summary

Single-month robustness of the 15.1D clock contrast (`60_180` vs `over_180`, baseline +0.0031 [+0.0003, +0.0057] **excl 0**). The matrix (§4) reports each mandatory check; read the combined report for the cross-month verdict. Clock effects, where present, are small and secondary to the eval-band structure. Predictive/descriptive only — not causal, not a degradation curve.

## 2. Input artifacts

- Next-move loss: `data/processed/next_move_loss_2024_09_250k_v1.parquet`
- Player metadata (hashed, gitignored): `data/processed/player_metadata_2024_09_250k_v1.parquet`
- Estimation rows (train+val): 52,757. Bootstrap reps 200, seed 42, mover-player-clustered unless noted.

## 3. Baseline replication

Baseline 15.1D model clock contrast (this month): primary +0.0031 [+0.0003, +0.0057] **excl 0**; `under_60` +0.0080 [+0.0020, +0.0137] **excl 0**. Reproduces the 15.1D specification on train+val.

## 4. Robustness matrix

| Check | clock 60_180 vs over_180 | under_60 vs over_180 |
|---|---|---|
| baseline (15.1D) | +0.0031 [+0.0003, +0.0057] **excl 0** | +0.0080 [+0.0020, +0.0137] **excl 0** |
| continuous eval control | +0.0031 [+0.0002, +0.0057] **excl 0** | +0.0084 [+0.0025, +0.0140] **excl 0** |
| late-only (move_30+40) | +0.0028 [-0.0006, +0.0065] contains 0 | +0.0067 [+0.0006, +0.0130] **excl 0** |
| board-decided-only | +0.0040 [+0.0001, +0.0088] **excl 0** | +0.0051 [-0.0024, +0.0147] contains 0 |
| rating quantile bins | +0.0028 [+0.0000, +0.0055] **excl 0** | +0.0076 [+0.0018, +0.0134] **excl 0** |
| rating quadratic | +0.0030 [+0.0001, +0.0056] **excl 0** | +0.0079 [+0.0019, +0.0136] **excl 0** |
| metric: clipped_cp_loss | +5.7711 [+0.8339, +9.9923] **excl 0** | +15.0605 [+4.7079, +24.2799] **excl 0** |
| metric: logistic ES>0.05 | +0.0129 [-0.0974, +0.1183] contains 0 | +0.2987 [+0.0336, +0.5128] **excl 0** |
| metric: logistic ES>0.10 | +0.0800 [-0.1167, +0.2265] contains 0 | +0.4231 [+0.1276, +0.6708] **excl 0** |
| cluster: game_id | +0.0031 [-0.0000, +0.0062] contains 0 | +0.0080 [+0.0032, +0.0137] **excl 0** |
| cluster: White-player | +0.0031 [+0.0003, +0.0057] **excl 0** | +0.0080 [+0.0020, +0.0137] **excl 0** |
| cluster: Black-player | +0.0031 [+0.0001, +0.0061] **excl 0** | +0.0080 [+0.0012, +0.0137] **excl 0** |

## 5. Continuous eval-control sensitivity

Adding standardized within-band |cp| (`abs_cp_z`): clock +0.0031 [+0.0002, +0.0057] **excl 0**.

## 6. Late-only sensitivity

move_30+move_40 only: clock +0.0028 [-0.0006, +0.0065] contains 0.

## 7. Board-decided-only sensitivity

Time-forfeit excluded: clock +0.0040 [+0.0001, +0.0088] **excl 0**.

## 8. Rating-specification sensitivity

Quantile bins: +0.0028 [+0.0000, +0.0055] **excl 0**; quadratic: +0.0030 [+0.0001, +0.0056] **excl 0**.

## 9. Metric sensitivity

clipped_cp_loss: +5.7711 [+0.8339, +9.9923] **excl 0** (directional; cp scale). logistic ES>0.05: +0.0129 [-0.0974, +0.1183] contains 0; ES>0.10: +0.0800 [-0.1167, +0.2265] contains 0 (log-odds).

## 10. Cluster sensitivity

game_id: +0.0031 [-0.0000, +0.0062] contains 0; White-player: +0.0031 [+0.0003, +0.0057] **excl 0**; Black-player: +0.0031 [+0.0001, +0.0061] **excl 0**.

## 11. Optional exploratory checks

None run in this pass (mandatory matrix only; interactions/finer bins are exploratory and deferred per 15.1E).

## 12. Interpretation

Per-month results feed the cross-month verdict in the combined report under the locked 15.1E criteria. A single month is not sufficient to credit or reject the association.

## 13. Limitations and caveats

- Predictive/descriptive association only — not causal; no claim that time pressure causes worse moves or degrades reasoning.
- Ordered-bucket patterns are patterns, not a degradation curve.
- Even where it survives, the clock effect is small and SECONDARY to the eval-band structure (eval contrasts are ~5–8× larger, 15.1D).
- Board-decided move-quality association is distinct from flagging risk; the two are reported separately and never conflated.
- `under_60` is sparse and ~2/3 time-forfeit (15.1E) — exploratory only.
- Mover-player clustering handles repeated movers, not exact two-way (White×Black) dependence (deferred).
- Prior-trajectory control is deferred (absent from artifacts) — the 'clock as symptom of past struggle' confound is unadjusted and stated.
- Stockfish depth-12 eval is objective position context, not absolute ground truth; DRAW remains sparse; sharpness is not implemented or invoked.

## 14. Recommendation

See the combined report for the binding verdict and next-ticket recommendation.
