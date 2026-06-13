# Termination Decomposition — Combined 2024-09 and 2024-10

**Ticket:** 11.2B — Termination Decomposition Implementation (locked Contrast C2)
**Design:** prediction-side filtering of frozen all-games E3/E4 validation predictions;
no retraining. Paired game-level bootstrap, 1,000 replicates, seed=42; 300-game CI
threshold. Delta = log_loss(E4) − log_loss(E3); negative = clock features improved.

---

## 1. Executive summary

The pre-registered C2 contrast returns a clear answer, replicated across both months:
**the overall E3→E4 clock residual is substantially explained by the
termination/flagging channel.** Among board-decided games, the overall residual
collapses to approximately zero in 2024-09 (+0.0010, CI contains zero, retained
fraction 7%) and reverses sign in 2024-10 (+0.0060, CI excludes zero on the *positive*
side — clock features slightly hurt). Time-forfeit games carry an enormous delta in
both months (−0.118 / −0.131). Per the pre-registered criterion, the central claim is
**re-framed honestly**, not abandoned: the replicated clock residual is real and
predictive, and it predominantly reflects flagging/timeout risk rather than
board-outcome signal. This is itself a quantified, replicated finding about *what*
clock features predict. All claims remain predictive associations; no causal design
exists; this is not a degradation curve.

## 2. Main finding

| Group | 2024-09 delta [95% CI] | 2024-10 delta [95% CI] |
|---|---|---|
| All games | −0.0138 [−0.0186, −0.0091] excl. zero | −0.0120 [−0.0177, −0.0062] excl. zero |
| **Board-decided only** | **+0.0010 [−0.0029, +0.0049] contains zero** | **+0.0060 [+0.0015, +0.0109] excl. zero (positive)** |
| Time-forfeit only | −0.1183 [−0.1423, −0.0978] excl. zero | −0.1305 [−0.1525, −0.1091] excl. zero |
| Retained fraction | 0.07 | 0.50 — **sign-reversed; magnitude-based fraction overstates retention** |

The board-decided residual does not survive in either month: near-zero in one,
slightly sign-reversed in the other. The signal lives in the 11–13% of games decided
by time forfeit.

## 3. Month-by-month comparison

The decomposition replicates cleanly across months: time-forfeit shares are nearly
identical (402/3,678 vs 400/3,524 val games), time-forfeit deltas are large and
similar (−0.118 / −0.131), and board-decided deltas are both ≈ zero-to-slightly-positive.
The only month divergence is at the boundary: 2024-09's board-decided CI straddles
zero while 2024-10's sits narrowly above it — both readings support the same
conclusion.

## 4. All-games vs board-decided-only clock residual

The all-games residual (the EXP-009/EXP-011 anchor result) is unchanged and remains
real. What C2 establishes is its composition: conditioning on eval and rating, clock
features earn their log-loss improvement overwhelmingly by predicting outcomes of
games that end in time forfeit. Among games decided on the board, knowing the clock
state at checkpoints adds nothing on average (and in 2024-10 marginally misleads,
plausibly by predicting flags that never materialize in this filtered, surviving
population).

## 5. Time-forfeit channel

Within time-forfeit games the clock delta is roughly ten times the all-games delta
(−0.12 to −0.13). This is expected and mechanically sensible — clock state is
directly informative about who flags — and it is exactly why the channel needed
quantifying before any "human-realizable value" interpretation was built on the
residual.

## 6. Late-clock localization after filtering

| Late cell (move_30+40) | 2024-09 BD | 2024-10 BD |
|---|---|---|
| under_60s | +0.1686 (101 games — descriptive only) | +0.1662 (94 games — descriptive only) |
| 60_180s | −0.0294 [−0.0530, −0.0064] excl. zero | −0.0061 [−0.0270, +0.0146] contains zero |
| over_180s | −0.0041 [−0.0106, +0.0021] contains zero | −0.0024 [−0.0095, +0.0050] contains zero |

Two observations, stated cautiously: (a) the 60_180s board-decided cell excluded zero
in 2024-09 but **did not replicate** in 2024-10 — the localized board-decided residual
is not established; (b) in both months the under-60s board-decided point delta flips
strongly *positive* (~+0.17, descriptive): among games that survive deep time pressure
without flagging, clock features actively mislead — consistent with the flagging-risk
reading of what those features encode.

## 7. Sample-size limitations

Board-decided under_60s cells hold only ~100 games per month (descriptive-only, below
the 300-game threshold). The 60_180s cells stay CI-bearing (464 / 424 games). The
overall board-decided groups are large (3,276 / 3,124 games), so the headline collapse
is not a power artifact.

## 8. Interpretation for the central claim

The supported claim is revised from "clock features add residual outcome signal beyond
eval and rating" to, conservatively:

> Across two independent Lichess 10+0 monthly samples, after controlling for
> fixed-depth Stockfish eval and ratings, clock features add a small replicated
> predictive signal for game outcomes that is **substantially attributable to the
> time-forfeit/flagging channel**. Among board-decided games the residual is
> approximately zero (one month) or slightly reversed (the other). The project
> therefore quantifies the flagging channel rather than demonstrating a
> board-outcome clock residual.

Required caveats, unchanged: filtering time-forfeit games induces selection bias and
does not create a causal design; board-decided low-clock games are a selected survivor
population; timeout is itself partly a consequence of earlier cognitive time
expenditure, so some genuine clock-relevant signal is removed by the filter — the
decomposition bounds, but does not perfectly separate, the channels. No claim is made
that time pressure causes worse reasoning; this is not a degradation curve; `Normal`
mixes checkmate and resignation; DRAW remains sparse and not solved.

## 9. Preregistration status

C2 executed exactly as pre-registered (after the logged pre-implementation wording
clarification: prediction-side filter of frozen models, no retraining). The
pre-registered collapse branch applies: *"if it collapses, reframe the clock signal as
largely termination/flagging-channel signal"* — this report does so. Downstream
pre-registered contrasts that assumed a surviving board-decided residual (notably C3
sharpness moderation and parts of the v11 framing) need a re-scoping audit **before**
implementation; under the revision policy this is permitted because their inputs do
not yet exist.

## 10. Next recommended ticket

**Claim-reframing audit before 11.3A** (per the 11.2B ticket's contingency): revisit
the v11 novelty lane, PREREGISTRATION C3/C4 framing, and the Phase 12–14 designs in
light of the flagging-channel finding — e.g., whether the interesting object is now
(a) flagging-risk prediction itself, (b) the board-decided residual at finer
resolution, or (c) the move-quality bridge (C4), which does not depend on outcome
deltas. Player-leakage work (11.3A) follows the re-scoping.
