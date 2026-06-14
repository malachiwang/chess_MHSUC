# Clock Association Robustness — 2024_10_250k_v1

**Ticket:** 15.1F — Clock Association Robustness Implementation (Contrast C4)

## 1. Executive summary

Single-month robustness of the 15.1D clock contrast (`60_180` vs `over_180`, baseline +0.0038 [+0.0012, +0.0063] **excl 0**). The matrix (§4) reports each mandatory check; read the combined report for the cross-month verdict. Clock effects, where present, are small and secondary to the eval-band structure. Predictive/descriptive only — not causal, not a degradation curve.

## 2. Input artifacts

- Next-move loss: `data/processed/next_move_loss_2024_10_250k_v1.parquet`
- Player metadata (hashed, gitignored): `data/processed/player_metadata_2024_10_250k_v1.parquet`
- Estimation rows (train+val): 50,634. Bootstrap reps 200, seed 42, mover-player-clustered unless noted.

## 3. Baseline replication

Baseline 15.1D model clock contrast (this month): primary +0.0038 [+0.0012, +0.0063] **excl 0**; `under_60` +0.0065 [+0.0020, +0.0124] **excl 0**. Reproduces the 15.1D specification on train+val.

## 4. Robustness matrix

| Check | clock 60_180 vs over_180 | under_60 vs over_180 |
|---|---|---|
| baseline (15.1D) | +0.0038 [+0.0012, +0.0063] **excl 0** | +0.0065 [+0.0020, +0.0124] **excl 0** |
| continuous eval control | +0.0038 [+0.0012, +0.0065] **excl 0** | +0.0067 [+0.0022, +0.0123] **excl 0** |
| late-only (move_30+40) | +0.0037 [+0.0005, +0.0065] **excl 0** | +0.0054 [+0.0006, +0.0112] **excl 0** |
| board-decided-only | +0.0028 [-0.0002, +0.0060] contains 0 | +0.0041 [-0.0038, +0.0124] contains 0 |
| rating quantile bins | +0.0035 [+0.0009, +0.0062] **excl 0** | +0.0063 [+0.0016, +0.0122] **excl 0** |
| rating quadratic | +0.0036 [+0.0011, +0.0063] **excl 0** | +0.0064 [+0.0018, +0.0123] **excl 0** |
| metric: clipped_cp_loss | +6.4126 [+2.2354, +10.7528] **excl 0** | +11.0289 [+2.7580, +20.3013] **excl 0** |
| metric: logistic ES>0.05 | +0.1501 [+0.0452, +0.2670] **excl 0** | +0.2189 [-0.0252, +0.4483] contains 0 |
| metric: logistic ES>0.10 | +0.1871 [+0.0239, +0.3436] **excl 0** | +0.4241 [+0.1084, +0.7318] **excl 0** |
| cluster: game_id | +0.0038 [+0.0009, +0.0077] **excl 0** | +0.0065 [+0.0020, +0.0108] **excl 0** |
| cluster: White-player | +0.0038 [+0.0012, +0.0063] **excl 0** | +0.0065 [+0.0020, +0.0124] **excl 0** |
| cluster: Black-player | +0.0038 [+0.0011, +0.0065] **excl 0** | +0.0065 [+0.0020, +0.0120] **excl 0** |

## 5. Continuous eval-control sensitivity

Adding standardized within-band |cp| (`abs_cp_z`): clock +0.0038 [+0.0012, +0.0065] **excl 0**.

## 6. Late-only sensitivity

move_30+move_40 only: clock +0.0037 [+0.0005, +0.0065] **excl 0**.

## 7. Board-decided-only sensitivity

Time-forfeit excluded: clock +0.0028 [-0.0002, +0.0060] contains 0.

## 8. Rating-specification sensitivity

Quantile bins: +0.0035 [+0.0009, +0.0062] **excl 0**; quadratic: +0.0036 [+0.0011, +0.0063] **excl 0**.

## 9. Metric sensitivity

clipped_cp_loss: +6.4126 [+2.2354, +10.7528] **excl 0** (directional; cp scale). logistic ES>0.05: +0.1501 [+0.0452, +0.2670] **excl 0**; ES>0.10: +0.1871 [+0.0239, +0.3436] **excl 0** (log-odds).

## 10. Cluster sensitivity

game_id: +0.0038 [+0.0009, +0.0077] **excl 0**; White-player: +0.0038 [+0.0012, +0.0063] **excl 0**; Black-player: +0.0038 [+0.0011, +0.0065] **excl 0**.

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
