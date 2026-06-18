# Phase 15.5C — Sharpness Result Consolidation / C3c Claim Update

**Labels:** AUDIT / CLAIM-UPDATE | report-only (no code, no models, no figures, no Stockfish/MultiPV, no data artifacts)
**Date:** 2026-06-18
**Owner:** Malachi Wang
**Mode:** CAUTIOUS (consolidation / claim update)

## 1. Executive summary

15.5B produced a useful **checkpoint-overlap, White-mover-only** sharpness analysis on
the dense substrate. **Conclusion of the sharpness arc:** the **sharpness main effect is
clear and replicated** (sharp positions carry higher next-move expected-score loss in
both months), but it is **partly mechanical** (the flag embeds a downside-loss threshold);
the **clock × sharpness moderation remains exploratory** (pooled-positive but
month-fragile, board-decided-fragile, sparse in the key low-clock cells). **C3c stays
UNRESOLVED — not confirmed, not disproven.** Existing artifacts **cannot** support a
dense-wide sharpness claim (coverage is 4.36%, checkpoint-overlap, White-mover only).
**Recommendation:** bound C3c as unresolved and **proceed to Phase 16 (16.1A
cross-time-control)**; keep a stratified dense sharpness extraction and a think-time
loss-rate diagnostic as **optional later branches**, only if Malachi prioritizes
resolving C3c before Phase 16. No code/models/figures/Stockfish/MultiPV; nothing staged.

## 2. Evidence base reviewed

Phase 14 MultiPV / C3c reports (`phase_14_1a/b/c`, `phase_14_2a/b/c/d`, `phase_14_3a`);
`phase_15_5a` audit; `sharpness_enriched_constraint_atlas_10plus0_…md` + `phase_15_5b`
implementation; `phase_15_4d` dense controlled model + its report; ROADMAP /
EXPERIMENT_LOG / PREREGISTRATION; `sharpness_enriched_atlas.py`, `dense_controlled_model.py`,
`multipv_sharpness.py`, `sharpness_interaction.py` (method details only).

## 3. Phase 14 C3c result recap

- **Sharpness definition:** `sharp_value_fragility_v1` = objective **value fragility**
  (`n_good_10es ≤ 2 ∧ worst_top5_loss_es ≥ 0.10 ∧ legal_move_count ≥ 8`), base rate ≈ 0.14;
  explicitly **not** human obviousness/difficulty. MultiPV-5, depth 12, checkpoint positions,
  White-to-move.
- **Primary interaction** `clock=60_180 × sharp_value_fragility_v1` on next-move ES loss,
  mover-player-clustered: **pooled train+val +0.0102 [+0.0013, +0.0194]** (excl 0);
  **per month +0.0074 [−0.0079, +0.0217] (09, contains 0)** and **+0.0131 [+0.0001, +0.0274]
  (10, excl 0)**; **test pooled near zero**; key sharp × 60_180 cells underpowered.
- **Original claim status: not confirmed, not disproven (no-claim).**

## 4. Phase 15.5B checkpoint-overlap result recap

- **Correct join:** `dense.ply = checkpoint_ply + 1` (the White move played from the
  White-to-move checkpoint; naive equal-ply join wrongly matches the Black move).
- **Matched rows: 121,165 headline = 4.36% of dense headline; White-mover only**,
  checkpoint-overlap only (4 plies/game). Sharp rate 0.1414.
- **Sharp × clock cell counts:** over_180 (sharp 16,275); 60_180 (sharp 675); 30_60
  (sharp 113); 10_30 (sharp 49); under_10 (sharp 17).
- **Sharp main effect** (net of controls, at over_180): **+0.0214 [+0.0198, +0.0231]**;
  Sep +0.0213 [+0.0189, +0.0235], Oct +0.0215 [+0.0193, +0.0239].
- **Focal `clock 60_180 × sharp`: +0.0104 [+0.0018, +0.0194] pooled**; **Sep +0.0095
  [−0.0024, +0.0236] (contains 0)**, **Oct +0.0113 [−0.0008, +0.0232] (contains 0)**;
  **board-decided-only +0.0056 [−0.0046, +0.0155] (contains 0)**; lower-clock × sharp
  cells sparse (<200) → no-claim.

## 5. Sharpness main-effect interpretation

Sharp positions have **higher next-move loss**, replicated across both months
(+0.021 net of eval/phase/rating/month/termination — comparable in magnitude to the
eval-band effect). **This is partly mechanical:** `sharp_value_fragility_v1` includes
`worst_top5_loss_es ≥ 0.10`, so the metric identifies positions where value loss is more
**available/likely** by construction — higher realized loss is therefore expected and is
**descriptive localization**, not evidence that humans find sharp positions psychologically
harder. Allowed phrasing: *"the metric identifies objectively fragile positions where
value loss is more available/likely."* Forbidden: *"sharpness proves human difficulty"*;
*"sharp positions cause blunders."*

## 6. Clock × sharpness moderation interpretation

The pooled checkpoint-overlap interaction (`60_180 × sharp` +0.0104) is positive and
**directionally consistent** with the old train+val C3c signal (+0.0102). But **both
per-month CIs contain zero** (Sep +0.0095, Oct +0.0113), the **board-decided robustness
contains zero** (+0.0056), and the **low-clock sharp cells are sparse** (sharp × 60_180 =
675; lower buckets <200). Therefore it **remains exploratory and cannot support a confirmed
moderation claim**. (Estimates and cell counts above, §4.)

## 7. Coverage and power limitations

- Existing sharpness coverage is **checkpoint-overlap only** (move_10/20/30/40 positions).
- **White-mover only** (checkpoints are even-ply → White to move).
- ~**4.36%** of dense headline rows matched.
- **Not dense-wide**; the matched subset is **not representative** of all moves (no Black
  moves, no non-checkpoint plies, low-clock mass under-sampled).
- The key **sharp × low-clock cells are sparse** (sharp × 60_180 = 675 pooled, lower buckets
  <200) — the same underpowered corner that left C3c unresolved at the checkpoint level; the
  dense substrate does **not** fix it because sharpness coverage is checkpoint-limited.

## 8. Claim status update for C3c

**C3c remains UNRESOLVED.** Status:
- **not confirmed;** **not disproven;**
- pooled-positive and directionally suggestive (checkpoint-overlap +0.0104; Phase-14
  train+val +0.0102);
- **month-fragile** (both 15.5B per-month CIs contain 0);
- **board-decided-fragile** (CI contains 0);
- **underpowered** in key sharp × low-clock cells;
- **limited to checkpoint-overlap, White-mover rows** — not a dense-wide result.

## 9. What can be said in the project report (safe language)

> Using existing checkpoint-level MultiPV sharpness artifacts, sharp positions show higher
> next-move expected-score loss than non-sharp positions. This sharpness main effect is
> replicated across the two 10+0 months, but the metric is an objective value-fragility
> proxy and partly encodes downside availability, so it should not be interpreted as
> human-obviousness or psychological difficulty. The clock × sharpness moderation estimate
> is pooled-positive but not month-replicated and remains sparse in the key low-clock cells.
> We therefore treat C3c as unresolved rather than confirmed.

## 10. What must not be said (forbidden)

- "Sharpness moderation is confirmed." / "Sharpness moderation is disproven."
- "Sharp positions cause blunders." / "Low clock causes blunders." / "Time pressure causes
  worse reasoning."
- "MultiPV sharpness captures human difficulty." / "human obviousness is modeled."
- "Stockfish is ground truth."
- "This is a dense-wide sharpness result." / "DRAW is solved."

## 11. Decision: proceed, defer, or extract more sharpness

- **Option A — bound C3c here and proceed to Phase 16 (recommended).** Use 15.5B as a
  carefully-bounded exploratory result; keep C3c unresolved; proceed to cross-time-control
  dose-response (16.1A). Scientifically acceptable because C3c has been thoroughly bounded
  (Phase 14 + 15.5A audit + 15.5B implementation all converge on "underpowered/unresolved").
- **Option B — add a stratified dense sharpness extraction audit (15.5D)** only if Malachi
  wants to invest more compute in resolving C3c before Phase 16 (sampled MultiPV over dense
  rows, both colors, stratified; §12).
- **Option C — full dense MultiPV — NOT recommended** (~51–82 h, §12).

**Recommended default: Option A** (proceed to Phase 16), with Option B recorded as an
optional later branch.

## 12. Stratified dense sharpness extraction feasibility

From 15.5A: full dense MultiPV-5 d12 over ~2.78M rows ≈ **51–82 h** (not recommended). A
**stratified ~150k–300k sample** ≈ **~3–9 h** could improve power and remove the
checkpoint/White-only limitation, but it is a **new Stockfish extraction branch** needing
its own audit before implementation. It should: sample **both colors** and **non-checkpoint
plies**; **stratify by clock, eval band, phase, rating, month, and termination** (enrich the
sparse low-clock sharp cells). If pursued, propose **15.5D — Stratified Dense Sharpness
Extraction Feasibility Audit**. If not now: **defer stratified dense sharpness until after
Phase 16 or until specifically needed.**

## 13. Think-Time Loss-Rate / Flagging Signature diagnostic note (future work)

A separate future diagnostic could examine stabilized loss rates such as
`clipped_cp_loss / max(think_time_net_s, 1)` and `expected_score_loss / max(think_time_net_s, 1)`,
split by termination channel (board-decided vs time-forfeit) and clock bucket, to detect
flagging/scramble behavior. This belongs in a **later flagging/scramble diagnostic ticket**,
**not** in the C3c sharpness claim update, and is **not** implemented here.

## 14. Recommended next roadmap step

**Mark C3c unresolved and do not force further sharpness immediately. Proceed to
Phase 16 — 16.1A Time-Control Selection / Feasibility Audit** — unless Malachi explicitly
prioritizes resolving C3c, in which case insert **15.5D — Stratified Dense Sharpness
Extraction Feasibility Audit** first. Record stratified dense sharpness extraction and the
think-time loss-rate diagnostic as optional later branches. (Follows the ROADMAP Phase 16
structure, whose first ticket is 16.1A.)

## 15. Open questions for Malachi (defaults in bold)

1. Spend another compute block to resolve C3c via stratified dense sharpness? — **No
   (default): bound C3c as unresolved.**
2. Or bound C3c and move to Phase 16 cross-time-control? — **Yes (default): proceed to
   16.1A.**
3. Think-time loss-rate / flagging-signature diagnostic before or after Phase 16? —
   **After / optional later ticket (default).**

## Non-claims

Report-only consolidation; no code/models/figures/Stockfish/MultiPV/data artifacts.
Predictive/descriptive; not causal. Sharpness = objective value fragility, **not** human
obviousness/difficulty; MultiPV/Stockfish not ground truth. Checkpoint-overlap, White-mover
only — **not** dense-wide. **C3c not confirmed, not disproven.** No "sharp positions cause
blunders" / "low clock causes blunders" / "time pressure causes worse reasoning" / "DRAW
solved." C4 and C3c unchanged. PREREGISTRATION unchanged.
