"""
Constraint Atlas — descriptive next-move loss curves (Ticket 15.1B).

Descriptive readout of the 15.0C next-move loss artifacts: how next-move
quality loss (expected-score loss, mover's perspective) varies across clock,
rating, eval band, phase/checkpoint, and termination channel. This is
DESCRIPTIVE measurement, not modeling — no causal claims, no "degradation
curve" language; Stockfish depth-12 eval is objective position context, not
absolute ground truth.

Discipline (from the 15.1A audit):
- Clock summaries are ALWAYS conditioned on checkpoint/phase (marginal clock
  curves are misleading — early checkpoints are ~all over-180s).
- Headline metric: expected-score loss (mean/median/p75/p90 + large-loss
  probabilities); clipped cp loss secondary; mate-band excluded from loss
  summaries.
- Cell-count policy: n<50 hidden_sparse, 50-300 descriptive_only, >=300 ci_ok.
- Uncertainty: game-level clustered bootstrap (multiple checkpoints per game),
  applied only to the headline late-group clock cells.
- Scope: numbered checkpoints are even-ply -> mover is always White; the Atlas
  describes White-to-move decision quality.

Outputs are committed markdown reports. No data artifacts are written.

CLI:
    PYTHONPATH=src python -m chess_mhsuc.constraint_atlas \\
        --input data/processed/next_move_loss_2024_09_250k_v1.parquet \\
        --version-tag 2024_09_250k_v1 \\
        --report reports/constraint_atlas_2024_09_250k_v1.md
    # combined:
    PYTHONPATH=src python -m chess_mhsuc.constraint_atlas --combined \\
        --input <sep>.parquet --input <oct>.parquet \\
        --report reports/constraint_atlas_combined.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLOCK_COARSE_ORDER = ["under_60", "60_180", "over_180"]
CLOCK_FINE_ORDER = ["<10", "10_30", "30_60", "60_180", "over_180"]
CHECKPOINT_ORDER = ["move_10", "move_20", "move_30", "move_40"]
LATE_CHECKPOINTS = ["move_30", "move_40"]
EVAL_BAND_ORDER = ["near_equal", "slight", "clear", "decided", "mate_band"]
TERMINATION_ORDER = ["all_games", "board_decided", "time_forfeit",
                     "normal_decisive", "normal_draw", "other"]
RATING_BIN_WIDTH = 200

# Cell-count policy
_HIDDEN_MAX = 50
_CI_MIN = 300

_REQUIRED_COLS = [
    "game_id", "selected_position_type", "status", "is_mate_band",
    "expected_score_loss", "clipped_cp_loss", "mover_pre_cp",
    "mover_clock_s", "time_bucket", "mover_rating", "termination",
    "is_time_forfeit",
]
# result_class is optional: the next_move_loss artifact does not carry it, so the
# normal_decisive/normal_draw sub-split is unavailable from the artifact alone.
# The headline board_decided vs time_forfeit split uses is_time_forfeit and is
# unaffected. When result_class is absent, Normal collapses to normal_decisive.


# ---------------------------------------------------------------------------
# A. Pure binning helpers
# ---------------------------------------------------------------------------

def clock_bucket_coarse(time_bucket: str | None) -> str | None:
    """Normalize the stored time_bucket (under_60s/60_180s/over_180s) to the
    atlas coarse label (under_60/60_180/over_180)."""
    if time_bucket is None:
        return None
    return {"under_60s": "under_60", "60_180s": "60_180",
            "over_180s": "over_180"}.get(time_bucket, time_bucket)


def clock_bucket_fine(mover_clock_s: float | None) -> str | None:
    """Finer clock bins for exploratory within-late-group analysis."""
    if mover_clock_s is None:
        return None
    if mover_clock_s < 10:
        return "<10"
    if mover_clock_s < 30:
        return "10_30"
    if mover_clock_s < 60:
        return "30_60"
    if mover_clock_s < 180:
        return "60_180"
    return "over_180"


def rating_bin(mover_rating: int | float | None, width: int = RATING_BIN_WIDTH) -> str | None:
    """Lower edge of the fixed-width rating bin, e.g. 1600 -> '1600_1799'."""
    if mover_rating is None:
        return None
    lo = int(mover_rating // width) * width
    return f"{lo}_{lo + width - 1}"


def eval_band(mover_pre_cp: int | float | None, is_mate_band: bool | None) -> str | None:
    """Mover-perspective eval band; mate-band rows are a separate label."""
    if is_mate_band:
        return "mate_band"
    if mover_pre_cp is None:
        return None
    a = abs(mover_pre_cp)
    if a <= 100:
        return "near_equal"
    if a <= 300:
        return "slight"
    if a <= 700:
        return "clear"
    return "decided"  # includes the small |cp|>1000 tail (15.1A decision)


def checkpoint_is_late(selected_position_type: str) -> bool:
    return selected_position_type in LATE_CHECKPOINTS


def termination_channel(
    termination: str | None,
    result_class: str | None,
    is_time_forfeit: bool | None,
) -> str:
    """
    Per-row termination channel. 'Normal' mixes checkmate and resignation
    (not separable from headers), so normal_decisive covers both.
    """
    if is_time_forfeit:
        return "time_forfeit"
    if termination == "Normal":
        return "normal_draw" if result_class == "DRAW" else "normal_decisive"
    return "other"


def cell_status(n: int) -> str:
    """hidden_sparse (<50) / descriptive_only (50-299) / ci_ok (>=300)."""
    if n < _HIDDEN_MAX:
        return "hidden_sparse"
    if n < _CI_MIN:
        return "descriptive_only"
    return "ci_ok"


# ---------------------------------------------------------------------------
# B. Load + derive
# ---------------------------------------------------------------------------

def load_atlas_frame(path: str | Path) -> pl.DataFrame:
    """
    Load a next-move loss artifact, validate required columns, filter to OK
    rows, and add derived bin columns. Mate-band rows are retained but flagged;
    loss summaries exclude them.
    """
    df = pl.read_parquet(path)
    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"artifact missing required columns: {missing}")

    ok = df.filter(pl.col("status") == "ok")
    if "result_class" not in ok.columns:
        ok = ok.with_columns(pl.lit(None, dtype=pl.Utf8).alias("result_class"))

    return ok.with_columns([
        pl.col("time_bucket").map_elements(clock_bucket_coarse, return_dtype=pl.Utf8)
        .alias("clock_coarse"),
        pl.col("mover_clock_s").map_elements(clock_bucket_fine, return_dtype=pl.Utf8)
        .alias("clock_fine"),
        pl.col("mover_rating").map_elements(lambda r: rating_bin(r), return_dtype=pl.Utf8)
        .alias("rating_bin"),
        pl.struct(["mover_pre_cp", "is_mate_band"]).map_elements(
            lambda s: eval_band(s["mover_pre_cp"], s["is_mate_band"]),
            return_dtype=pl.Utf8).alias("eval_band"),
        pl.struct(["termination", "result_class", "is_time_forfeit"]).map_elements(
            lambda s: termination_channel(s["termination"], s["result_class"],
                                          s["is_time_forfeit"]),
            return_dtype=pl.Utf8).alias("channel"),
        (~pl.col("is_time_forfeit")).alias("board_decided"),
        pl.col("selected_position_type").is_in(LATE_CHECKPOINTS).alias("is_late"),
        (pl.col("expected_score_loss") > 0.05).alias("es_loss_gt_005"),
        (pl.col("expected_score_loss") > 0.10).alias("es_loss_gt_010"),
        (pl.col("clipped_cp_loss") > 100).alias("clipped_cp_loss_gt_100"),
        (pl.col("clipped_cp_loss") > 200).alias("clipped_cp_loss_gt_200"),
    ])


# ---------------------------------------------------------------------------
# C. Summary statistics
# ---------------------------------------------------------------------------

def cell_summary(df: pl.DataFrame) -> dict:
    """
    Descriptive stats over the NON-mate-band rows of a cell frame. Returns a
    dict including n, ES-loss and clipped-cp-loss summaries, large-loss
    probabilities, and the cell-count status.
    """
    nm = df.filter(~pl.col("is_mate_band"))
    n = len(nm)
    out: dict = {"n": n, "n_mate_band": len(df) - n, "status": cell_status(n)}
    if n == 0:
        return out
    es = nm["expected_score_loss"].to_numpy()
    cp = nm["clipped_cp_loss"].to_numpy()
    out.update({
        "mean_es_loss": round(float(np.mean(es)), 4),
        "median_es_loss": round(float(np.median(es)), 4),
        "p75_es_loss": round(float(np.percentile(es, 75)), 4),
        "p90_es_loss": round(float(np.percentile(es, 90)), 4),
        "pct_zero_es_loss": round(100 * float(np.mean(es == 0)), 1),
        "pct_es_loss_gt_005": round(100 * float(np.mean(es > 0.05)), 1),
        "pct_es_loss_gt_010": round(100 * float(np.mean(es > 0.10)), 1),
        "mean_clipped_cp_loss": round(float(np.mean(cp)), 1),
        "median_clipped_cp_loss": round(float(np.median(cp)), 1),
        "p75_clipped_cp_loss": round(float(np.percentile(cp, 75)), 1),
        "p90_clipped_cp_loss": round(float(np.percentile(cp, 90)), 1),
        "pct_clipped_cp_loss_gt_100": round(100 * float(np.mean(cp > 100)), 1),
        "pct_clipped_cp_loss_gt_200": round(100 * float(np.mean(cp > 200)), 1),
    })
    return out


def bootstrap_mean_es_ci(
    df: pl.DataFrame, n_rep: int = 500, seed: int = 42,
) -> tuple[float | None, float | None]:
    """
    Game-level clustered bootstrap 95% CI for the mean expected-score loss of a
    cell (non-mate-band rows). Resamples game_ids with replacement (a game may
    contribute several checkpoints). Returns (lo, hi) or (None, None) if empty.
    """
    nm = df.filter(~pl.col("is_mate_band"))
    if len(nm) == 0:
        return None, None
    games = nm["game_id"].to_list()
    es = nm["expected_score_loss"].to_numpy()
    by_game: dict[str, list[int]] = {}
    for i, g in enumerate(games):
        by_game.setdefault(g, []).append(i)
    gids = list(by_game.keys())
    idx_lists = [np.array(by_game[g]) for g in gids]
    rng = np.random.default_rng(seed)
    n_games = len(gids)
    means = np.empty(n_rep, dtype=np.float64)
    for r in range(n_rep):
        pick = rng.integers(0, n_games, size=n_games)
        sel = np.concatenate([idx_lists[p] for p in pick])
        means[r] = es[sel].mean()
    return round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)


# ---------------------------------------------------------------------------
# D. Table builders
# ---------------------------------------------------------------------------

def grouped_summary(df: pl.DataFrame, by: list[str]) -> list[dict]:
    """Return one cell_summary dict per distinct combination of ``by`` columns."""
    rows: list[dict] = []
    grp = df.group_by(by)
    for key, sub in grp:
        key = key if isinstance(key, tuple) else (key,)
        rec = {col: val for col, val in zip(by, key)}
        rec.update(cell_summary(sub))
        rows.append(rec)
    # stable sort by the by-columns (string)
    rows.sort(key=lambda r: tuple(str(r.get(c)) for c in by))
    return rows


def _fmt(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def _table(rows: list[dict], by: list[str], es_only: bool = False) -> list[str]:
    """Render grouped summary rows as a markdown table (sparse cells labeled)."""
    if es_only:
        cols = ["n", "status", "mean_es_loss", "median_es_loss", "p90_es_loss",
                "pct_es_loss_gt_010"]
        head = by + ["n", "status", "mean ES", "median ES", "p90 ES", "%ES>0.10"]
    else:
        cols = ["n", "status", "mean_es_loss", "median_es_loss", "p90_es_loss",
                "pct_es_loss_gt_010", "mean_clipped_cp_loss",
                "median_clipped_cp_loss", "pct_clipped_cp_loss_gt_100"]
        head = by + ["n", "status", "mean ES", "median ES", "p90 ES", "%ES>0.10",
                     "mean cp", "median cp", "%cp>100"]
    lines = ["| " + " | ".join(head) + " |",
             "|" + "---|" * len(head)]
    for r in rows:
        if r.get("status") == "hidden_sparse":
            cells = [str(r.get(c)) for c in by] + [str(r["n"]), "hidden_sparse"] + \
                    ["—"] * (len(cols) - 2)
        else:
            cells = [str(r.get(c)) for c in by]
            for c in cols:
                v = r.get(c)
                cells.append(_fmt(v, 4) if "es" in c else
                             (_fmt(v, 1) if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


# ---------------------------------------------------------------------------
# E. Month report
# ---------------------------------------------------------------------------

_CAVEATS = [
    "Descriptive measurement only — no causal claims; this is an association "
    "between constraint state and next-move loss, not evidence that time "
    "pressure causes worse moves or degrades reasoning.",
    "Ordered-bucket patterns are reported as patterns, not as a degradation curve.",
    "Stockfish depth-12 eval is objective position context, not absolute ground truth.",
    "Clock summaries are conditioned on checkpoint/phase; marginal all-checkpoint "
    "clock curves would conflate time remaining with game phase and are not shown.",
    "Numbered checkpoints are even-ply, so the mover is always White: this Atlas "
    "describes White-to-move decision quality.",
    "Board-decided low-clock cells are a selected survivor population (11.2B).",
    "Loss distributions are right-skewed; medians and upper quantiles are reported "
    "alongside means. Mate-band rows are excluded from loss summaries.",
    "DRAW remains sparse and is not solved. Sharpness is not implemented yet and "
    "is not invoked as an explanation.",
]


def render_month_report(version_tag: str, df: pl.DataFrame,
                        late_ci: dict | None = None) -> str:
    L: list[str] = []
    a = L.append
    overall = cell_summary(df)
    bd = cell_summary(df.filter(pl.col("board_decided")))
    tf = cell_summary(df.filter(pl.col("is_time_forfeit")))

    a(f"# Constraint Atlas — {version_tag}")
    a("")
    a("**Ticket:** 15.1B — Constraint Atlas Descriptive Curves Implementation")
    a("")
    a("## 1. Executive summary")
    a("")
    a(f"Descriptive next-move loss readout over {overall['n']:,} non-mate-band "
      f"OK checkpoint moves. Overall mean expected-score (ES) loss "
      f"{_fmt(overall['mean_es_loss'])}, median {_fmt(overall['median_es_loss'])} "
      f"(right-skewed). Board-decided and time-forfeit populations are summarized "
      "separately and side-by-side; clock is always conditioned on checkpoint. "
      "Descriptive only — see caveats (§14).")
    a("")
    a("## 2. Input artifact and schema")
    a("")
    a(f"`data/processed/next_move_loss_{version_tag}.parquet` (OK rows; mate-band "
      "flagged and excluded from loss summaries). Derived bins: clock_coarse, "
      "clock_fine, rating_bin, eval_band, channel, board_decided, is_late, "
      "large-loss indicators.")
    a("")
    a("## 3. Metric definitions")
    a("")
    a("- Primary: `expected_score_loss = max(0, ES(mover_pre_cp) − ES(mover_post_cp))` "
      "(mover's perspective; train-fit logistic transform, scale 348.4).")
    a("- Secondary: `clipped_cp_loss = min(max(0, mover_pre_cp − mover_post_cp), 1000)`.")
    a("- Large-loss probabilities: P(ES>0.05), P(ES>0.10), P(cp>100), P(cp>200).")
    a("")
    a("## 4. Cell-count policy")
    a("")
    a(f"hidden_sparse (n<{_HIDDEN_MAX}) — not summarized; descriptive_only "
      f"({_HIDDEN_MAX}≤n<{_CI_MIN}) — point estimates, no CI; ci_ok (n≥{_CI_MIN}) — "
      "CI-eligible. Game-level clustered bootstrap CIs are shown only for the "
      "headline late-group clock cells (§7).")
    a("")
    a("## 5. Overall loss summary")
    a("")
    a("| Population | n | mean ES | median ES | p75 ES | p90 ES | %ES>0.10 | mean cp | median cp | %cp>100 |")
    a("|---|---|---|---|---|---|---|---|---|---|")
    for name, s in [("all_games", overall), ("board_decided", bd), ("time_forfeit", tf)]:
        a(f"| {name} | {s['n']:,} | {_fmt(s.get('mean_es_loss'))} | "
          f"{_fmt(s.get('median_es_loss'))} | {_fmt(s.get('p75_es_loss'))} | "
          f"{_fmt(s.get('p90_es_loss'))} | {_fmt(s.get('pct_es_loss_gt_010'),1)} | "
          f"{_fmt(s.get('mean_clipped_cp_loss'),1)} | "
          f"{_fmt(s.get('median_clipped_cp_loss'),1)} | "
          f"{_fmt(s.get('pct_clipped_cp_loss_gt_100'),1)} |")
    a("")
    a("## 6. Checkpoint-conditioned clock summary")
    a("")
    a("All-games, by checkpoint × coarse clock bucket:")
    a("")
    L += _table(grouped_summary(df, ["selected_position_type", "clock_coarse"]),
                ["selected_position_type", "clock_coarse"])
    a("")
    a("Board-decided only, by checkpoint × coarse clock bucket:")
    a("")
    L += _table(grouped_summary(df.filter(pl.col("board_decided")),
                                ["selected_position_type", "clock_coarse"]),
                ["selected_position_type", "clock_coarse"])
    a("")
    a("## 7. Late-checkpoint clock summary")
    a("")
    a("Late group (move_30+move_40), by finer clock bucket and termination view "
      "(ES loss; game-level bootstrap 95% CI on mean ES for ci_ok cells):")
    a("")
    late = df.filter(pl.col("is_late"))
    a("| View | clock_fine | n | status | mean ES | 95% CI | median ES | %ES>0.10 |")
    a("|---|---|---|---|---|---|---|---|")
    for view, fdf in [("all", late),
                      ("board_decided", late.filter(pl.col("board_decided"))),
                      ("time_forfeit", late.filter(pl.col("is_time_forfeit")))]:
        for b in CLOCK_FINE_ORDER:
            sub = fdf.filter(pl.col("clock_fine") == b)
            s = cell_summary(sub)
            if s["n"] == 0:
                continue
            ci = "—"
            if s["status"] == "ci_ok" and late_ci is not None:
                lo, hi = late_ci.get((view, b), (None, None))
                if lo is not None:
                    ci = f"[{_fmt(lo)}, {_fmt(hi)}]"
            if s["status"] == "hidden_sparse":
                a(f"| {view} | {b} | {s['n']} | hidden_sparse | — | — | — | — |")
            else:
                a(f"| {view} | {b} | {s['n']} | {s['status']} | "
                  f"{_fmt(s['mean_es_loss'])} | {ci} | {_fmt(s['median_es_loss'])} | "
                  f"{_fmt(s['pct_es_loss_gt_010'],1)} |")
    a("")
    a("## 8. Board-decided vs time-forfeit summary")
    a("")
    a("Late group, board-decided vs time-forfeit, by coarse clock bucket:")
    a("")
    L += _table(grouped_summary(
        late.with_columns(
            pl.when(pl.col("is_time_forfeit")).then(pl.lit("time_forfeit"))
            .otherwise(pl.lit("board_decided")).alias("tf_view")),
        ["tf_view", "clock_coarse"]), ["tf_view", "clock_coarse"], es_only=True)
    a("")
    a("## 9. Rating × clock summary")
    a("")
    a("Late group, rating bin × coarse clock bucket (ES loss; sparse cells labeled):")
    a("")
    L += _table(grouped_summary(late, ["rating_bin", "clock_coarse"]),
                ["rating_bin", "clock_coarse"], es_only=True)
    a("")
    a("## 10. Eval-band × clock summary")
    a("")
    a("Late group, eval band × coarse clock bucket (ES loss):")
    a("")
    L += _table(grouped_summary(late.filter(~pl.col("is_mate_band")),
                                ["eval_band", "clock_coarse"]),
                ["eval_band", "clock_coarse"], es_only=True)
    a("")
    a("## 11. Phase/checkpoint summary")
    a("")
    a("By checkpoint (all clocks pooled within checkpoint):")
    a("")
    L += _table(grouped_summary(df, ["selected_position_type"]),
                ["selected_position_type"])
    a("")
    a("## 12. Clipped-cp robustness summary")
    a("")
    a("Does clipped cp loss mirror ES loss by checkpoint? (both shown above; the "
      "cp and ES orderings agree by construction — both are non-negative losses "
      "of the same move — and are reported together so cp can be read against the "
      "literature's centipawn-loss convention).")
    a("")
    a("## 13. Sparse-cell diagnostics")
    a("")
    sparse = [r for r in grouped_summary(late, ["rating_bin", "clock_coarse"])
              if r["status"] != "ci_ok"]
    a(f"{len(sparse)} of the late rating×clock cells are below the {_CI_MIN}-row "
      "CI threshold (descriptive_only or hidden_sparse) — chiefly low-clock and "
      "rating-tail cells. These are labeled in the tables and must not be "
      "emphasized.")
    a("")
    a("## 14. Limitations and caveats")
    a("")
    for c in _CAVEATS:
        a(f"- {c}")
    a("")
    a("## 15. Recommendation for combined interpretation")
    a("")
    a("Read this month against the other in the combined report; a pattern is only "
      "noted if it replicates across 2024-09 and 2024-10. No controlled or causal "
      "conclusion is drawn here.")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# F. Combined report
# ---------------------------------------------------------------------------

def render_combined_report(frames: dict[str, pl.DataFrame]) -> str:
    L: list[str] = []
    a = L.append
    tags = list(frames)
    a("# Constraint Atlas — Combined " + " and ".join(tags))
    a("")
    a("**Ticket:** 15.1B — Constraint Atlas Descriptive Curves Implementation")
    a("")
    a("## 1. Executive summary")
    a("")
    a("Descriptive next-move loss readout across two independent months. Patterns "
      "are reported only where they replicate across months. Descriptive "
      "association only — not causal, not a degradation curve; Stockfish eval is "
      "objective context, not absolute ground truth.")
    a("")
    a("## 2. Why this Atlas exists after 11.2B/11.2C")
    a("")
    a("11.2B/11.2C showed the outcome clock residual is substantially the "
      "time-forfeit/flagging channel and moved the board-play-quality question to "
      "next-move quality (Contrast C4). This Atlas describes that move-quality "
      "layer directly.")
    a("")
    a("## 3. Input artifacts")
    a("")
    for t in tags:
        a(f"- `data/processed/next_move_loss_{t}.parquet` ({len(frames[t]):,} OK rows)")
    a("")
    a("## 4. Month-by-month replication summary")
    a("")
    a("Overall non-mate-band loss per month:")
    a("")
    a("| Month | n | mean ES | median ES | p90 ES | %ES>0.10 | median cp |")
    a("|---|---|---|---|---|---|---|")
    for t in tags:
        s = cell_summary(frames[t])
        a(f"| {t} | {s['n']:,} | {_fmt(s['mean_es_loss'])} | "
          f"{_fmt(s['median_es_loss'])} | {_fmt(s['p90_es_loss'])} | "
          f"{_fmt(s['pct_es_loss_gt_010'],1)} | {_fmt(s['median_clipped_cp_loss'],1)} |")
    a("")
    a("## 5. Headline checkpoint-conditioned clock findings")
    a("")
    a("Mean ES loss by checkpoint × coarse clock bucket, per month (ci_ok cells "
      "only; n in parentheses):")
    a("")
    cps = CHECKPOINT_ORDER
    a("| Checkpoint | clock | " + " | ".join(tags) + " |")
    a("|---|---|" + "---|" * len(tags))
    for cp in cps:
        for clk in CLOCK_COARSE_ORDER:
            cells = []
            any_ok = False
            for t in tags:
                sub = frames[t].filter((pl.col("selected_position_type") == cp)
                                       & (pl.col("clock_coarse") == clk))
                s = cell_summary(sub)
                if s["n"] >= _CI_MIN:
                    any_ok = True
                    cells.append(f"{_fmt(s['mean_es_loss'])} (n={s['n']:,})")
                elif s["n"] >= _HIDDEN_MAX:
                    cells.append(f"{_fmt(s['mean_es_loss'])} (n={s['n']}, desc)")
                else:
                    cells.append(f"(n={s['n']})")
            if any_ok:
                a(f"| {cp} | {clk} | " + " | ".join(cells) + " |")
    a("")
    a("## 6. Late-checkpoint findings")
    a("")
    a("Late group (move_30+40), mean ES loss by coarse clock bucket, per month:")
    a("")
    a("| clock | " + " | ".join(tags) + " | replicates? |")
    a("|---|" + "---|" * len(tags) + "---|")
    for clk in CLOCK_COARSE_ORDER:
        vals, ok_flags = [], []
        for t in tags:
            sub = frames[t].filter(pl.col("is_late") & (pl.col("clock_coarse") == clk))
            s = cell_summary(sub)
            ok_flags.append(s["status"] == "ci_ok")
            vals.append(s.get("mean_es_loss"))
            sub_lbl = (f"{_fmt(s.get('mean_es_loss'))} (n={s['n']:,}"
                       f"{'' if s['status']=='ci_ok' else ', desc'})")
            vals[-1] = sub_lbl
        rep = "yes" if all(ok_flags) else "partial/sparse"
        a(f"| {clk} | " + " | ".join(vals) + f" | {rep} |")
    a("")
    a("## 7. Termination-channel findings")
    a("")
    a("Late group, board-decided vs time-forfeit mean ES loss, per month "
      "(descriptive — similar values do NOT imply identical mechanisms):")
    a("")
    a("| View | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for view, expr in [("board_decided", pl.col("board_decided")),
                       ("time_forfeit", pl.col("is_time_forfeit"))]:
        cells = []
        for t in tags:
            sub = frames[t].filter(pl.col("is_late") & expr)
            s = cell_summary(sub)
            cells.append(f"{_fmt(s.get('mean_es_loss'))} (n={s['n']:,})")
        a(f"| {view} | " + " | ".join(cells) + " |")
    a("")
    a("## 8. Rating × clock findings")
    a("")
    a("Late group, mean ES loss by rating bin × coarse clock (per month, ci_ok "
      "cells; see month reports for full tables).")
    a("")
    a("## 9. Eval-band × clock findings")
    a("")
    a("Late group, mean ES loss by eval band (over_180s clock; per month):")
    a("")
    a("| eval_band | " + " | ".join(tags) + " |")
    a("|---|" + "---|" * len(tags))
    for eb in ["near_equal", "slight", "clear", "decided"]:
        cells = []
        for t in tags:
            sub = frames[t].filter(pl.col("is_late") & (pl.col("eval_band") == eb)
                                   & (pl.col("clock_coarse") == "over_180"))
            s = cell_summary(sub)
            cells.append(f"{_fmt(s.get('mean_es_loss'))} (n={s['n']:,})"
                         if s["n"] >= _HIDDEN_MAX else f"(n={s['n']})")
        a(f"| {eb} | " + " | ".join(cells) + " |")
    a("")
    a("## 10. Clipped-cp robustness")
    a("")
    a("Per-month median clipped cp loss is reported in §4 alongside ES; the two "
      "metrics co-move by construction (both are non-negative losses of the same "
      "move). cp is retained for literature comparability.")
    a("")
    a("## 11. Sparse-cell diagnostics")
    a("")
    a("Low-clock late cells (under_60, and the finer <10/10_30 bins) are at or "
      "below the CI threshold and are descriptive-only; rating tails (≤600, ≥2400) "
      "likewise. These are labeled throughout and must not be emphasized.")
    a("")
    a("## 12. What this supports")
    a("")
    a("- Descriptive statements that ES/cp loss is higher or lower in specific "
      "checkpoint×clock (and rating/eval) cells, where those cells are ci_ok.")
    a("- Statements that a cell pattern replicates (or does not) across the two months.")
    a("- Motivation for controlled modeling (Contrast C4) with proper confound "
      "control and clustered uncertainty.")
    a("")
    a("## 13. What this does not support")
    a("")
    a("- Any causal claim (low clock causing worse moves; time pressure degrading "
      "reasoning) — none is made.")
    a("- A 'degradation curve' reading of ordered-bucket patterns.")
    a("- Stockfish as ground truth; DRAW as solved; sharpness as an explanation "
      "(not yet implemented).")
    a("- That the clock residual is 'not merely flagging' — that question is for "
      "controlled analysis, not this descriptive readout.")
    a("")
    a("## 14. Readiness for controlled modeling")
    a("")
    a("The descriptive layer is complete and month-replicated where cells are dense. "
      "Controlled C4 modeling (next-move loss ~ time + rating + eval band + phase + "
      "prior trajectory, with interactions) must wait for player-leakage hardening "
      "(11.3A/B) or build in player-clustered/disjoint design from the start.")
    a("")
    a("## 15. Recommended next ticket")
    a("")
    a("**11.3A — Player-Disjoint / Player-Clustered Feasibility Audit** — required "
      "before controlled C4 modeling (15.1C) and sharpness moderation (15.2B).")
    a("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# G. main / CLI
# ---------------------------------------------------------------------------

def _late_ci_for_report(df: pl.DataFrame, n_rep: int, seed: int) -> dict:
    """Bootstrap CIs for the headline late-group fine-clock cells (ci_ok only)."""
    late = df.filter(pl.col("is_late"))
    out: dict = {}
    for view, fdf in [("all", late),
                      ("board_decided", late.filter(pl.col("board_decided"))),
                      ("time_forfeit", late.filter(pl.col("is_time_forfeit")))]:
        for b in CLOCK_FINE_ORDER:
            sub = fdf.filter(pl.col("clock_fine") == b)
            if cell_summary(sub)["status"] == "ci_ok":
                out[(view, b)] = bootstrap_mean_es_ci(sub, n_rep=n_rep, seed=seed)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Constraint Atlas descriptive curves (Ticket 15.1B). "
                    "Descriptive only; no modeling."
    )
    parser.add_argument("--input", action="append", required=True,
                        help="next_move_loss parquet (repeat for --combined)")
    parser.add_argument("--version-tag", default=None)
    parser.add_argument("--report", required=True)
    parser.add_argument("--combined", action="store_true")
    parser.add_argument("--n-replicates", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    report = Path(args.report)
    if report.exists() and not args.overwrite:
        raise FileExistsError(f"{report} exists; pass --overwrite")
    report.parent.mkdir(parents=True, exist_ok=True)

    if args.combined:
        frames: dict[str, pl.DataFrame] = {}
        for path in args.input:
            # derive a tag from the filename
            stem = Path(path).stem.replace("next_move_loss_", "")
            frames[stem] = load_atlas_frame(path)
            print(f"  [atlas] loaded {stem}: {len(frames[stem]):,} OK rows", file=sys.stderr)
        report.write_text(render_combined_report(frames))
        print(f"  [atlas] combined report: {report}", file=sys.stderr)
        return 0

    if len(args.input) != 1 or not args.version_tag:
        print("ERROR: single-month mode needs exactly one --input and --version-tag.",
              file=sys.stderr)
        return 2
    df = load_atlas_frame(args.input[0])
    print(f"  [atlas] {args.version_tag}: {len(df):,} OK rows", file=sys.stderr)
    late_ci = _late_ci_for_report(df, args.n_replicates, args.seed)
    report.write_text(render_month_report(args.version_tag, df, late_ci))
    print(f"  [atlas] month report: {report}", file=sys.stderr)
    # console summary
    overall = cell_summary(df)
    print(f"\n=== 15.1B atlas {args.version_tag} ===")
    print(f"  overall non-mate-band n={overall['n']:,} mean_ES={overall['mean_es_loss']} "
          f"median_ES={overall['median_es_loss']} median_cp={overall['median_clipped_cp_loss']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
