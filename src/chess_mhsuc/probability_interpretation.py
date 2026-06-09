"""
probability_interpretation.py — Phase 7.2B probability interpretation guardrails.

Synthesizes existing baseline, GBM, feature-importance, and calibration
diagnostics into a written set of probability interpretation guardrails.
No new models trained. No new predictions. No calibrators fitted.
No model artifacts. No plots. No CSV. No new dependencies.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.probability_interpretation \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --baseline-results data/processed/baseline_results_2024_09_25k_v1.json \\
        --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
        --baseline-predictions data/processed/baseline_predictions_2024_09_25k_v1.parquet \\
        --gbm-predictions data/processed/gbm_predictions_2024_09_25k_v1.parquet \\
        --output reports/probability_interpretation_2024_09_25k_v1.md

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import polars as pl

from chess_mhsuc.baselines import CLASS_ORDER
from chess_mhsuc.calibration import (
    filter_calibration_models,
    load_baseline_predictions,
    load_gbm_predictions,
    standardize_prediction_schema,
    summarize_model_calibration,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INTERP_MODEL_IDS: list[str] = ["B1", "B3", "G2"]

# G2 high-confidence bucket lower bound for overconfidence diagnostic
_G2_HIGH_CONF_LOWER: float = 0.9


# ---------------------------------------------------------------------------
# A. get_class_order
# ---------------------------------------------------------------------------


def get_class_order() -> list[str]:
    """Return the canonical class order: BLACK_WIN, DRAW, WHITE_WIN."""
    return list(CLASS_ORDER)


# ---------------------------------------------------------------------------
# B. load_baseline_results
# ---------------------------------------------------------------------------


def load_baseline_results(path: str | Path) -> dict:
    """
    Load baseline_results JSON.

    Validates that B1 and B3 are present in the 'baselines' key.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if "baselines" not in payload:
        raise ValueError(
            f"Baseline results JSON missing 'baselines' key. "
            f"Found: {sorted(payload.keys())}"
        )
    baselines = payload["baselines"]
    for required in ("B1", "B3"):
        if required not in baselines:
            raise ValueError(
                f"Baseline results JSON missing required model '{required}'. "
                f"Found: {sorted(baselines.keys())}"
            )
    return payload


# ---------------------------------------------------------------------------
# C. load_gbm_results
# ---------------------------------------------------------------------------


def load_gbm_results(path: str | Path) -> dict:
    """
    Load gbm_results JSON.

    Validates that G2 is present in the 'gbm_models' key.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if "gbm_models" not in payload:
        raise ValueError(
            f"GBM results JSON missing 'gbm_models' key. "
            f"Found: {sorted(payload.keys())}"
        )
    models = payload["gbm_models"]
    model_ids = list(models.keys()) if isinstance(models, dict) else [
        m.get("model_id") for m in models
    ]
    if "G2" not in model_ids:
        raise ValueError(
            f"GBM results JSON missing required model 'G2'. "
            f"Found: {model_ids}"
        )
    return payload


# ---------------------------------------------------------------------------
# D. extract_model_log_loss
# ---------------------------------------------------------------------------


def extract_model_log_loss(
    baseline_payload: dict,
    gbm_payload: dict,
) -> dict[str, Any]:
    """
    Extract key log_loss values for interpretation report.

    Returns dict with:
        B1_val_log_loss, B3_val_log_loss,
        G2_train_log_loss, G2_val_log_loss, G2_overfit_gap.
    """
    bl = baseline_payload["baselines"]

    def _bl_val(mid: str) -> float:
        return float(bl[mid]["metrics"]["val"]["log_loss"])

    b1_ll = _bl_val("B1")
    b3_ll = _bl_val("B3")

    models = gbm_payload["gbm_models"]
    g2 = models["G2"] if isinstance(models, dict) else next(
        m for m in models if m.get("model_id") == "G2"
    )
    g2_train = float(g2["metrics"]["train"]["log_loss"])
    g2_val = float(g2["metrics"]["val"]["log_loss"])

    return {
        "B1_val_log_loss": b1_ll,
        "B3_val_log_loss": b3_ll,
        "G2_train_log_loss": g2_train,
        "G2_val_log_loss": g2_val,
        "G2_overfit_gap": g2_val - g2_train,
    }


# ---------------------------------------------------------------------------
# E. load_calibration_numbers
# ---------------------------------------------------------------------------


def load_calibration_numbers(
    baseline_predictions_path: str | Path,
    gbm_predictions_path: str | Path,
) -> dict[str, dict]:
    """
    Load calibration summaries for B1, B3, G2 on the validation split.

    Reuses calibration.py helpers. Returns dict:
        {model_id: summary_dict}
    where each summary_dict contains n_rows, ece, classwise_brier,
    and confidence_accuracy_table.
    """
    baseline_df = load_baseline_predictions(baseline_predictions_path)
    gbm_df = load_gbm_predictions(gbm_predictions_path)
    combined = standardize_prediction_schema(baseline_df, gbm_df)
    combined = filter_calibration_models(combined, _INTERP_MODEL_IDS)

    summaries: dict[str, dict] = {}
    for mid in _INTERP_MODEL_IDS:
        rows = combined.filter(pl.col("model_id") == mid)
        if len(rows) == 0:
            continue
        summaries[mid] = summarize_model_calibration(combined, mid, "val")
    return summaries


# ---------------------------------------------------------------------------
# F. extract_probability_distribution_notes
# ---------------------------------------------------------------------------


def extract_probability_distribution_notes(
    baseline_predictions_path: str | Path,
    gbm_predictions_path: str | Path,
) -> dict[str, Any]:
    """
    Extract probability distribution statistics for B3 and G2 val predictions.

    Returns dict with B3 and G2 p_WHITE_WIN / p_DRAW mean, std, min, max.
    Intended as a reporting aid only.
    """
    baseline_df = load_baseline_predictions(baseline_predictions_path)
    gbm_df = load_gbm_predictions(gbm_predictions_path)

    b3_val = baseline_df.filter(
        (pl.col("baseline_id") == "B3") & (pl.col("split_set") == "val")
    )
    from chess_mhsuc.calibration import _GBM_PRIMARY_VIEW
    g2_val = gbm_df.filter(
        (pl.col("model_id") == "G2")
        & (pl.col("split_set") == "val")
        & (pl.col("view") == _GBM_PRIMARY_VIEW)
    ) if "view" in gbm_df.columns else gbm_df.filter(
        (pl.col("model_id") == "G2") & (pl.col("split_set") == "val")
    )

    def _stats(df: pl.DataFrame, col: str) -> dict[str, float]:
        s = df[col]
        return {
            "mean": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "max": float(s.max()),
        }

    return {
        "B3_p_WHITE_WIN": _stats(b3_val, "p_WHITE_WIN"),
        "B3_p_DRAW": _stats(b3_val, "p_DRAW"),
        "G2_p_WHITE_WIN": _stats(g2_val, "p_WHITE_WIN"),
        "G2_p_DRAW": _stats(g2_val, "p_DRAW"),
    }


# ---------------------------------------------------------------------------
# G. render_allowed_cautious_forbidden_claims_table
# ---------------------------------------------------------------------------


def render_allowed_cautious_forbidden_claims_table() -> str:
    """Render the allowed/cautious/forbidden claims matrix as Markdown."""
    rows = [
        # (status, claim)
        ("Allowed", "\"B3 is the safest current broad probability model.\""),
        ("Allowed", "\"B3 is moderately calibrated for BLACK_WIN and WHITE_WIN at pilot scale (ECE ≈ 0.026–0.033).\""),
        ("Allowed", "\"G2 probabilities are overconfident and should not be used for interpretation.\""),
        ("Allowed", "\"B1's low ECE is an artifact of prior-only prediction; B1 is not useful for position-level interpretation.\""),
        ("Allowed", "\"DRAW probabilities are unreliable for all current models.\""),
        ("Allowed", "\"Current probabilities are diagnostic only, not final calibrated estimates.\""),
        ("Allowed", "\"Rating/skill signal is robust at pilot scale.\""),
        ("Allowed", "\"Clock and phase probability signals are unstable at pilot scale.\""),
        ("Allowed", "\"Calibration and scaling are needed before probability-level constraint claims.\""),
        ("Cautious", "\"B3 probability differences may be used as rough descriptive outcome scores for position ranking.\" (with caveats: pilot-scale, not causal, DRAW excluded)"),
        ("Cautious", "\"Higher-rated players tend to receive higher B3 p_WHITE_WIN on average.\" (correlation only, not causal)"),
        ("Cautious", "\"B3 probability bins can support pipeline sanity checks.\" (not final claims)"),
        ("Cautious", "\"Rating signal is more reliably captured than clock signal at this dataset scale.\""),
        ("Forbidden", "Claiming the model proves time pressure causes worse play."),
        ("Forbidden", "Claiming a +0.10 probability change is a direct constraint-caused shift."),
        ("Forbidden", "Claiming the GBM learned stable human constraint strategy."),
        ("Forbidden", "Claiming G2's high-confidence predictions are reliable."),
        ("Forbidden", "Claiming DRAW class is adequately modeled because DRAW ECE appears small."),
        ("Forbidden", "Claiming B1 is the most useful model because its ECE is lowest."),
        ("Forbidden", "Framing model outputs as objective engine-based win estimates."),
        ("Forbidden", "Claiming we have established a degradation curve for clock/phase pressure."),
        ("Forbidden", "Claiming subgroup probability differences are final constraint findings."),
        ("Forbidden", "Claiming p_WHITE_WIN equals objective position evaluation."),
        ("Forbidden", "Claiming calibration fully corrects probabilities for constraint analysis."),
    ]
    header = "| Status | Claim |\n| --- | --- |"
    lines = [header]
    for status, claim in rows:
        lines.append(f"| **{status}** | {claim} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# H. render_probability_semantics_section
# ---------------------------------------------------------------------------


def render_probability_semantics_section() -> str:
    """Return Markdown text defining probability semantics."""
    return "\n".join([
        "For a selected mid-game checkpoint position with available features "
        "(player ratings, clock state, move number, game-phase proxy), the model "
        "estimates the probability that the game eventually ends in "
        "**BLACK_WIN / DRAW / WHITE_WIN**, among human games in the sampled "
        "**Lichess 10+0 (600+0) population** with similar feature values.",
        "",
        "More precisely:",
        "",
        "- **`p_BLACK_WIN`**: model-estimated empirical probability that Black wins "
        "the game, conditional on the features available at this checkpoint.",
        "- **`p_DRAW`**: model-estimated empirical probability that the game ends "
        "as a draw.",
        "- **`p_WHITE_WIN`**: model-estimated empirical probability that White wins "
        "the game.",
        "",
        "These probabilities are:",
        "",
        "- **Human-behavior-conditioned.** They reflect how human Lichess players "
        "in this time control tend to resolve games from similar feature contexts, "
        "not how an engine would play from the same position.",
        "- **Feature-conditioned empirical frequencies.** They estimate outcome "
        "rates conditional on the features the model was given — rating, clock, "
        "move number, and phase proxy. They are not conditioned on the full board "
        "position or engine evaluation (for broad models).",
        "- **Checkpoint-level estimates.** Predictions come from selected positions "
        "(after move 10/20/30/40 or the last available pre-result position), not "
        "from every ply. They are snapshots, not continuous trajectory estimates.",
        "- **Sampled-population probabilities.** They are specific to the 2024-09 "
        "Lichess 10+0 pilot extract. Generalization to other time controls, rating "
        "ranges, or populations is not established.",
    ])


# ---------------------------------------------------------------------------
# I. render_model_trustworthiness_section
# ---------------------------------------------------------------------------


def render_model_trustworthiness_section(metrics: dict) -> str:
    """
    Render per-model trustworthiness section.

    metrics: output of extract_model_log_loss + calibration numbers merged.
    """
    ll = metrics.get("log_loss", {})
    cal = metrics.get("calibration", {})

    b3_ll = ll.get("B3_val_log_loss", float("nan"))
    b1_ll = ll.get("B1_val_log_loss", float("nan"))
    g2_val = ll.get("G2_val_log_loss", float("nan"))
    g2_train = ll.get("G2_train_log_loss", float("nan"))
    g2_gap = ll.get("G2_overfit_gap", float("nan"))

    b1_ece_bw = cal.get("B1", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    b3_ece_bw = cal.get("B3", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    b3_ece_ww = cal.get("B3", {}).get("ece", {}).get("WHITE_WIN", float("nan"))
    g2_ece_bw = cal.get("G2", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    g2_ece_ww = cal.get("G2", {}).get("ece", {}).get("WHITE_WIN", float("nan"))

    # G2 high-confidence bucket
    g2_hc = _find_g2_high_conf_bucket(cal)

    lines = [
        "### B1 — DummyClassifier (prior): Low-ECE Trap",
        "",
        f"B1 predicts the class prior (≈47.6% BLACK_WIN / 6.3% DRAW / 46.1% WHITE_WIN) "
        f"for **every single row**, regardless of position, rating, or clock state. "
        f"B1 val log_loss = {b1_ll:.4f}.",
        "",
        f"B1's ECE is extremely low (≈{b1_ece_bw:.4f} for BLACK_WIN) because "
        "the training class prior happens to approximately match validation class "
        "frequencies. **This is the low-ECE trap.** A constant prediction that "
        "ignores all features can appear well-calibrated by ECE. B1 is not a "
        "useful probability model. It is only a base-rate reference anchor.",
        "",
        "---",
        "",
        "### B3 — LogisticRegression on FS-E: Safest Current Broad Model",
        "",
        f"B3 is the best current broad model for probability interpretation. "
        f"Val log_loss = {b3_ll:.4f} (best broad). "
        f"ECE for BLACK_WIN ≈ {b3_ece_bw:.4f}, WHITE_WIN ≈ {b3_ece_ww:.4f} — "
        "moderate calibration for these two classes.",
        "",
        "B3 can be used **cautiously** and **descriptively** for BLACK_WIN and "
        "WHITE_WIN probabilities, with the following conditions:",
        "",
        "- Cite pilot-scale and validation-only context.",
        "- Do not interpret causal effects.",
        "- Do not interpret DRAW probabilities.",
        "- Do not call B3 'calibrated' — call it 'moderately calibrated at pilot scale'.",
        "",
        "---",
        "",
        "### G2 — HistGBM on FS-E: Negative Example of Overconfidence",
        "",
        f"G2 val log_loss = {g2_val:.4f} vs train log_loss = {g2_train:.4f} "
        f"(overfit gap = +{g2_gap:.4f}). G2 is worse than every broad logistic "
        "baseline. ECE for BLACK_WIN ≈ {bw} and WHITE_WIN ≈ {ww} — severe "
        "overconfidence.".format(bw=f"{g2_ece_bw:.4f}", ww=f"{g2_ece_ww:.4f}"),
        "",
    ]

    if g2_hc:
        lines += [
            f"In the [0.9, 1.0] confidence bucket: mean confidence ≈ {g2_hc['mean_confidence']:.3f}, "
            f"accuracy ≈ {g2_hc['accuracy']:.3f}, "
            f"gap = +{g2_hc['gap']:.3f} (n={g2_hc['n']}). "
            "G2 assigns very high confidence to predictions that are correct barely more than half the time.",
            "",
        ]

    lines += [
        "**G2 probabilities must not be used for downstream interpretation or "
        "constraint claims.** G2 is overconfident, overfit, and not trustworthy "
        "as a probability source. It is cited as a reference case illustrating "
        "what overfit overconfidence looks like in probability space.",
        "",
    ]

    return "\n".join(lines)


def _find_g2_high_conf_bucket(cal: dict) -> dict | None:
    """Return G2's [0.9, 1.0] confidence-accuracy bucket if present."""
    g2_summary = cal.get("G2", {})
    conf_table = g2_summary.get("confidence_accuracy_table", [])
    for row in conf_table:
        if row.get("bin_lower", 0) >= _G2_HIGH_CONF_LOWER - 0.001:
            return row
    return None


# ---------------------------------------------------------------------------
# J. render_probability_interpretation_report
# ---------------------------------------------------------------------------


def render_probability_interpretation_report(
    ll_dict: dict,
    cal_summaries: dict,
    dist_notes: dict,
    dataset_id: str,
    version_tag: str,
) -> str:
    """Assemble the full 14-section probability interpretation report."""

    metrics = {"log_loss": ll_dict, "calibration": cal_summaries}

    b3_ll = ll_dict.get("B3_val_log_loss", float("nan"))
    b1_ll = ll_dict.get("B1_val_log_loss", float("nan"))
    g2_val = ll_dict.get("G2_val_log_loss", float("nan"))
    g2_train = ll_dict.get("G2_train_log_loss", float("nan"))
    g2_gap = ll_dict.get("G2_overfit_gap", float("nan"))

    b3_ece_bw = cal_summaries.get("B3", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    b3_ece_ww = cal_summaries.get("B3", {}).get("ece", {}).get("WHITE_WIN", float("nan"))
    b3_ece_d = cal_summaries.get("B3", {}).get("ece", {}).get("DRAW", float("nan"))
    g2_ece_bw = cal_summaries.get("G2", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    g2_ece_ww = cal_summaries.get("G2", {}).get("ece", {}).get("WHITE_WIN", float("nan"))
    g2_hc = _find_g2_high_conf_bucket(cal_summaries)
    draw_count = cal_summaries.get("B3", {}).get("class_counts", {}).get("DRAW", 59)
    n_val = cal_summaries.get("B3", {}).get("n_rows", 931)

    b3_ww_mean = dist_notes.get("B3_p_WHITE_WIN", {}).get("mean", float("nan"))
    b3_ww_std = dist_notes.get("B3_p_WHITE_WIN", {}).get("std", float("nan"))
    b3_ww_max = dist_notes.get("B3_p_WHITE_WIN", {}).get("max", float("nan"))
    b3_d_std = dist_notes.get("B3_p_DRAW", {}).get("std", float("nan"))
    b3_d_max = dist_notes.get("B3_p_DRAW", {}).get("max", float("nan"))
    g2_ww_std = dist_notes.get("G2_p_WHITE_WIN", {}).get("std", float("nan"))

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    header = [
        f"# Probability Interpretation Guardrails Report — {version_tag}",
        "",
        "**Ticket:** 7.2B — Probability Interpretation Report Implementation",
        "**Labels:** REPORTING/ML | D1 | IMPLEMENTATION",
        f"**Dataset ID:** `{dataset_id}`",
        f"**Version tag:** `{version_tag}`",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 1: ELI5 / TLDR
    # -----------------------------------------------------------------------
    sec1 = [
        "## 1. ELI5 / TLDR",
        "",
        "This report defines what model probabilities mean and do not mean, "
        "and establishes guardrails for how they may be used in future phases.",
        "",
        "Chess is the testbed, not the endpoint. The larger project is modeling "
        "human strategy/reasoning under constraints. Before future phases can make "
        "claims about how time pressure, game phase, or rating affect outcomes, "
        "they need a clear statement of what current probabilities are and are not.",
        "",
        "Key guardrails:",
        "",
        "- **B3 is the safest current broad probability model.** "
        f"Val log_loss = {b3_ll:.4f}. "
        f"Moderately calibrated for BLACK_WIN/WHITE_WIN (ECE ≈ {b3_ece_bw:.3f}–{b3_ece_ww:.3f}).",
        "- **B3 is only cautiously usable for BLACK_WIN and WHITE_WIN.** "
        "DRAW probabilities from B3 are unreliable.",
        "- **G2 probabilities are not trustworthy for interpretation.** "
        f"G2 val log_loss = {g2_val:.4f} with overfit gap = +{g2_gap:.4f}. "
        f"ECE BLACK_WIN/WHITE_WIN ≈ {g2_ece_bw:.3f}–{g2_ece_ww:.3f}.",
        "- **B1's low ECE is a trap.** B1 predicts only class priors; "
        "appearing calibrated does not make it useful.",
        "- **Current probabilities are human empirical outcome estimates, "
        "not engine evaluations or causal effects.**",
        "- **No constraint-effect claims are established yet.** "
        "Phase 8 and Phase 9 are required before any causal or subgroup conclusions.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 2: What a Predicted Probability Means
    # -----------------------------------------------------------------------
    sec2 = [
        "## 2. What a Predicted Probability Means",
        "",
        render_probability_semantics_section(),
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 3: What a Predicted Probability Does NOT Mean
    # -----------------------------------------------------------------------
    sec3 = [
        "## 3. What a Predicted Probability Does NOT Mean",
        "",
        "Current model probabilities are **not**:",
        "",
        "- **Not objective engine evaluation.** Broad models (B3, G2) do not use "
        "Stockfish evaluation. A high p_WHITE_WIN can reflect a large rating "
        "advantage, not an objectively winning position.",
        "- **Not a true game-theoretic win probability.** Human outcomes depend "
        "on player fatigue, time pressure, blunder probability, and psychology — "
        "not on minimax search. These estimates reflect human behavior, not "
        "perfect-play analysis.",
        "- **Not a causal effect.** A higher p_WHITE_WIN when clock < 30s does "
        "not prove that time pressure causes White to win more. It is a "
        "correlation in the training data, potentially confounded by rating, "
        "game phase, and position selection.",
        "- **Not a stable out-of-sample guarantee.** These probabilities are "
        "conditioned on the specific 2024-09 Lichess 10+0 pilot extract. "
        "Generalization to other time controls, rating ranges, or years "
        "is not established.",
        "- **Not a full trajectory probability from every ply.** Predictions "
        "are made at selected checkpoints only (after move 10/20/30/40 or "
        "the last pre-result position). They do not describe how probability "
        "evolves continuously through a game.",
        "- **Not a final constraint-effect measurement.** Subgroup comparisons "
        "(e.g., probability by rating bucket, by clock pressure, by phase) are "
        "descriptive patterns in a small pilot dataset, not validated constraint "
        "findings.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 4: Model Trustworthiness Summary
    # -----------------------------------------------------------------------
    trust_table = "\n".join([
        "| Model | Type | Val log_loss | Status |",
        "| --- | --- | --- | --- |",
        f"| B1 | DummyClassifier (prior) | {b1_ll:.4f} | Prior reference only. Low ECE is a trap. |",
        f"| **B3** | LogisticRegression (FS-E) | {b3_ll:.4f} | **Safest current broad model.** Cautious use only. |",
        f"| G2 | HistGBM (FS-E) | {g2_val:.4f} | Not trustworthy. Overfit, overconfident. |",
        "| G4 | HistGBM (FS-D) | 0.881 | Deceptive near-prior. Not useful. |",
        "| G5/G6 | HistGBM (FS-F/G, eval-gated) | 1.185 / 1.641 | Selection-biased. G6 memorizes. Not broad. |",
        "| B3-balanced | LR class_weight=balanced | 1.062 | Class-weight diagnostic. Not probability-calibrated. |",
        "| B4/B5 | LR (eval-gated, exploratory) | 0.783 / 0.860 | Eval-gated, biased. Not for broad claims. |",
    ])

    sec4 = [
        "## 4. Current Model Trustworthiness Summary",
        "",
        trust_table,
        "",
        "> Note: log_loss values are from the validation split on the broad primary_numbered view. "
        "B4/B5/G5/G6 are restricted to eval-annotated positions (~13.7% of positions) "
        "and are not comparable to broad model values.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 5: B1 Low-ECE Trap
    # -----------------------------------------------------------------------
    b1_ece_bw = cal_summaries.get("B1", {}).get("ece", {}).get("BLACK_WIN", float("nan"))
    sec5 = [
        "## 5. B1 Interpretation — The Low-ECE Trap",
        "",
        f"B1 has ECE ≈ {b1_ece_bw:.4f} for BLACK_WIN — lower than B3's "
        f"{b3_ece_bw:.4f}. This is not evidence that B1 is a better probability model.",
        "",
        "B1 predicts the class prior for every single row: approximately "
        "47.6% BLACK_WIN, 6.3% DRAW, 46.1% WHITE_WIN. It assigns the same "
        "probability regardless of position, rating, or clock state.",
        "",
        "Its low ECE occurs because validation class frequencies happen to "
        "approximately match the training class prior. Any model that ignores "
        "all features and always outputs the prior will show low ECE when the "
        "class distribution is stable across splits.",
        "",
        "**This is a known pitfall in calibration evaluation:** ECE alone does not "
        "measure whether a model is informative. A perfectly uninformative model "
        "that predicts the marginal class frequency can appear well-calibrated.",
        "",
        "**B1 is useful only as a base-rate reference.** It establishes the "
        "prior probability floor. Any model that does not beat B1 in log_loss "
        "has not learned meaningful signal beyond class frequencies.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 6: B3 — Safest Current Broad Model
    # -----------------------------------------------------------------------
    sec6 = [
        "## 6. B3 Interpretation — Safest Current Broad Model",
        "",
        f"B3 (LogisticRegression on FS-E) achieves val log_loss = {b3_ll:.4f}, "
        "the best of all broad models. Its probability spread is meaningful: "
        f"p_WHITE_WIN has mean ≈ {b3_ww_mean:.3f}, std ≈ {b3_ww_std:.3f}, "
        f"ranging up to {b3_ww_max:.3f} for large rating gaps.",
        "",
        "**Calibration:** ECE for BLACK_WIN ≈ {bw:.4f} and WHITE_WIN ≈ {ww:.4f} "
        "indicate moderate calibration for these classes. "
        "DRAW ECE ≈ {d:.4f} appears small but is misleading — see Section 8.".format(
            bw=b3_ece_bw, ww=b3_ece_ww, d=b3_ece_d,
        ),
        "",
        "**What B3 probabilities capture:** Primarily the effect of rating "
        "differential on outcome probability. Clock and position features "
        "contribute additional signal, but their individual effects are not "
        "isolated in the current model.",
        "",
        "**Safe use:** B3 BLACK_WIN/WHITE_WIN probabilities may be cited "
        "descriptively as rough outcome scores, subject to the following conditions:",
        "",
        "1. Explicitly label as 'pilot-scale, descriptive, not causal'.",
        "2. Cite that broad models do not use engine evaluation.",
        "3. Never interpret B3 DRAW probabilities as meaningful.",
        "4. Do not use B3 for final constraint analysis — that requires Phase 8/9.",
        "5. Do not call B3 'calibrated' without caveats about its limitations.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 7: G2 Negative Example
    # -----------------------------------------------------------------------
    g2_hc_lines: list[str] = []
    if g2_hc:
        g2_hc_lines = [
            f"In G2's [0.9, 1.0] top-label confidence bucket "
            f"(n={g2_hc['n']}): mean confidence = {g2_hc['mean_confidence']:.3f}, "
            f"accuracy = {g2_hc['accuracy']:.3f}, gap = +{g2_hc['gap']:.3f}. "
            "G2 assigns very high confidence to predictions that are correct barely "
            "more than half the time. This is overfit overconfidence: the model "
            "learned to be extremely certain about training patterns that do not "
            "generalize.",
            "",
        ]

    sec7 = [
        "## 7. G2 Interpretation — Negative Example of Overfit Overconfidence",
        "",
        f"G2 (HistGBM on FS-E): train log_loss = {g2_train:.4f}, "
        f"val log_loss = {g2_val:.4f}, overfit gap = +{g2_gap:.4f}. "
        "G2 does not beat B3 on any metric. It is worse than logistic regression "
        "because the small pilot dataset (~4,344 train rows) is insufficient to "
        "support the nonlinear capacity of a gradient-boosted model.",
        "",
        f"ECE: BLACK_WIN = {g2_ece_bw:.4f}, WHITE_WIN = {g2_ece_ww:.4f}. "
        f"G2 probability spread: p_WHITE_WIN std ≈ {g2_ww_std:.3f} "
        "(compared to B3 std ≈ {b3_std:.3f}). "
        "G2's wider spread is not a sign of richer signal — it is a sign of "
        "overfit noise pushing predictions toward the extremes.".format(
            b3_std=b3_ww_std,
        ),
        "",
        *g2_hc_lines,
        "**G2 probabilities must not be used for downstream interpretation, "
        "probability claims, or constraint analysis.** G2 is documented here "
        "as a reference case illustrating what miscalibrated overconfidence looks "
        "like in a small-data GBM.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 8: DRAW Caveat
    # -----------------------------------------------------------------------
    draw_pct = 100.0 * draw_count / n_val if n_val > 0 else 0.0
    sec8 = [
        "## 8. DRAW Probability Caveat",
        "",
        f"DRAW is sparse: {draw_count}/{n_val} validation rows ({draw_pct:.1f}%). "
        "This imbalance means DRAW is systematically under-modeled in every "
        "current model.",
        "",
        "**All current models keep p_DRAW near the class prior for almost every "
        f"row.** B3 p_DRAW has std ≈ {b3_d_std:.3f}, max ≈ {b3_d_max:.3f}. "
        "The model rarely assigns p_DRAW above 0.15, regardless of position.",
        "",
        f"B3 DRAW ECE ≈ {b3_ece_d:.4f} — extremely small, but this is "
        "misleading. When a model outputs near-zero p_DRAW for nearly every row "
        "and the true DRAW rate is also low (~6.3%), the OvR calibration error "
        "is trivially small even if the model has no DRAW-discriminating power.",
        "",
        "**DRAW probability interpretation rules:**",
        "",
        "- Do not interpret p_DRAW values from any current model.",
        "- Do not cite DRAW ECE as evidence of DRAW calibration.",
        "- Acknowledge that DRAW is not currently modeled.",
        "- Future work (more data, class rebalancing, or alternative DRAW "
        "indicators) is required before DRAW probabilities can be discussed.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 9: Probability vs Engine Evaluation
    # -----------------------------------------------------------------------
    sec9 = [
        "## 9. Probability vs Engine Evaluation",
        "",
        "Broad models (B1 through B3, G1 through G4) **do not use Stockfish "
        "evaluation at all.** Their probabilities are conditioned solely on "
        "rating, clock, and position-context features.",
        "",
        "This creates a crucial distinction:",
        "",
        "- A position where White has a 400-Elo rating advantage may receive "
        "high p_WHITE_WIN from B3 regardless of whether the position is "
        "objectively advantageous.",
        "- A position that is objectively lost for Black (by engine analysis) "
        "may receive balanced B3 probabilities if the rating gap is small.",
        "- B3 probabilities reflect **human outcome frequencies under observed "
        "feature conditioning**, not objective chess truth.",
        "",
        "Eval-gated models (B4/B5 for LR, G5/G6 for GBM) add Stockfish "
        "evaluation features but are restricted to the ~13.7% of positions "
        "with eval annotations — a selection-biased subset with avg_elo ≈ +20 "
        "Elo vs the broad population. These models are exploratory and cannot "
        "support broad population claims.",
        "",
        "**Phase 8 (Stockfish validation)** will assess whether conclusions "
        "from broad models align with objectively evaluated positions. Until "
        "then, broad model probabilities must not be framed as engine-based "
        "win assessments.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 10: Probability vs Constraint Claims
    # -----------------------------------------------------------------------
    sec10 = [
        "## 10. Probability vs Causal Constraint Claims",
        "",
        "The project's core hypothesis is that human outcomes depend on "
        "constraints (clock pressure, game phase, rating, position complexity). "
        "Future phases may want to claim: 'under time pressure, players convert "
        "winning positions less often.'",
        "",
        "**Current probabilities do not support such claims.** Here is why:",
        "",
        "- **Observational confounding.** Clock state, rating, and game phase "
        "are correlated in the training data. A model that sees 'low clock → "
        "lower p_WHITE_WIN' may simply be capturing the confound that "
        "lower-rated players run low on time more often.",
        "- **No causal design.** We have not constructed matched samples, "
        "controlled experiments, or instrumental variables. Probability "
        "differences across subgroups are descriptive patterns, not causal "
        "constraint effects.",
        "- **No stable clock signal.** G2 permutation importance shows "
        "clock_diff_s has the strongest negative importance at pilot scale — "
        "the model failed to learn generalizing clock patterns. B3 uses clock "
        "features but has not been ablated to isolate their independent "
        "probability contributions.",
        "- **Noisy at pilot scale.** Slice diagnostics from the 2024-09 "
        "extract (931 val rows, 82–194 per elo bucket) are too noisy for "
        "reliable constraint conclusions.",
        "",
        "**What is needed for Phase 9 constraint analysis:**",
        "",
        "1. A better-fit model (after Phase 8 scaling/Stockfish validation).",
        "2. Larger dataset for stable subgroup-level signal.",
        "3. Explicit causal or quasi-experimental design.",
        "4. Calibration check on any model used for constraint claims.",
        "5. Documentation per PROJECT_CHARTER.md §8 evidence standards.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 11: Claims Matrix
    # -----------------------------------------------------------------------
    sec11 = [
        "## 11. Allowed / Cautious / Forbidden Claims",
        "",
        render_allowed_cautious_forbidden_claims_table(),
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 12: Phase 8 / Phase 9 Readiness
    # -----------------------------------------------------------------------
    sec12 = [
        "## 12. Readiness for Phase 8 and Phase 9",
        "",
        "| Phase | Status | Condition |",
        "| --- | --- | --- |",
        "| Phase 8: Stockfish validation | Not started | Needed to check whether broad model conclusions align with objective position strength |",
        "| Phase 8: Model scaling | Not started | More data needed for stable clock/phase signal |",
        "| Phase 9: Constraint analysis | Not ready | Requires better-fit model, larger dataset, causal design, calibration check |",
        "",
        "**B3 may be used as a cautious diagnostic baseline for Phase 8** to "
        "compare broad-model probabilities against eval-conditioned probabilities.",
        "",
        "**G2 must not be used for any Phase 8 or Phase 9 probability claims.** "
        "Its overfit and overconfidence make it an unreliable reference.",
        "",
        "**Any future subgroup or constraint claim must include:**",
        "",
        "- Documented dataset version and split.",
        "- Calibration assessment on the model used.",
        "- Baseline comparison (at minimum against B3).",
        "- Explicit acknowledgment that correlational findings are not causal.",
        "- Written report per project workflow.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 13: Reproducibility
    # -----------------------------------------------------------------------
    cli_cmd = (
        "```bash\n"
        "PYTHONPATH=src python -m chess_mhsuc.probability_interpretation \\\\\n"
        f"    --dataset-id {dataset_id} \\\\\n"
        f"    --version-tag {version_tag} \\\\\n"
        f"    --baseline-results data/processed/baseline_results_{version_tag}.json \\\\\n"
        f"    --gbm-results data/processed/gbm_results_{version_tag}.json \\\\\n"
        f"    --baseline-predictions data/processed/baseline_predictions_{version_tag}.parquet \\\\\n"
        f"    --gbm-predictions data/processed/gbm_predictions_{version_tag}.parquet \\\\\n"
        f"    --output reports/probability_interpretation_{version_tag}.md\n"
        "```"
    )

    sec13 = [
        "## 13. Reproducibility / Source Artifacts",
        "",
        "Command used to generate this report:",
        "",
        cli_cmd,
        "",
        "**Source artifacts (all local-only, gitignored under `data/`):**",
        "",
        f"- `data/processed/baseline_results_{version_tag}.json`",
        f"- `data/processed/gbm_results_{version_tag}.json`",
        f"- `data/processed/baseline_predictions_{version_tag}.parquet`",
        f"- `data/processed/gbm_predictions_{version_tag}.parquet`",
        "",
        "**Source context reports (committed):**",
        "",
        f"- `reports/calibration_{version_tag}.md`",
        f"- `reports/baseline_evaluation_{version_tag}.md`",
        f"- `reports/gbm_evaluation_{version_tag}.md`",
        f"- `reports/gbm_feature_importance_{version_tag}.md`",
        "",
        "No new model outputs, model artifacts, plots, or CSV files were created. "
        f"This committed Markdown report (`reports/probability_interpretation_{version_tag}.md`) "
        "is the only tracked artifact from this ticket.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 14: Acceptance Criteria
    # -----------------------------------------------------------------------
    sec14 = [
        "## 14. Acceptance Criteria Met",
        "",
        "- [x] Probability interpretation report exists",
        "- [x] Report defines probability semantics (what p_BLACK_WIN/DRAW/WHITE_WIN means)",
        "- [x] Report lists what probabilities do NOT mean",
        "- [x] Report identifies B3 as safest current broad probability model",
        "- [x] Report explains B1 low-ECE trap",
        "- [x] Report explains why G2 probabilities are not trustworthy",
        "- [x] Report explains DRAW probability unreliability",
        "- [x] Report distinguishes probabilities from engine evaluation",
        "- [x] Report distinguishes probability differences from causal constraint effects",
        "- [x] Report includes allowed/cautious/forbidden claims table",
        "- [x] Report does not compute new model predictions",
        "- [x] Report does not fit post-hoc calibrators",
        "- [x] Report does not make Phase 9 constraint claims",
        "- [x] Report cites actual ECE and log_loss values from prior artifacts",
        "- [x] No model artifacts saved",
        "- [x] No CSV files created",
        "- [x] No plots created",
        "- [x] No new dependencies added",
        "- [x] ROADMAP.md updated (7.2A complete, 7.2B complete)",
        "- [x] EXPERIMENT_LOG.md updated (EXP-005 added)",
        "- [x] Local data artifacts remain gitignored",
        "",
    ]

    # -----------------------------------------------------------------------
    # Assemble
    # -----------------------------------------------------------------------
    parts = [
        *header,
        *sec1,  "---", "",
        *sec2,  "---", "",
        *sec3,  "---", "",
        *sec4,  "---", "",
        *sec5,  "---", "",
        *sec6,  "---", "",
        *sec7,  "---", "",
        *sec8,  "---", "",
        *sec9,  "---", "",
        *sec10, "---", "",
        *sec11, "---", "",
        *sec12, "---", "",
        *sec13, "---", "",
        *sec14,
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# K. write_text
# ---------------------------------------------------------------------------


def write_text(path: str | Path, text: str) -> None:
    """Write UTF-8 text to file, creating parent directories as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


# ---------------------------------------------------------------------------
# L. main / CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 7.2B probability interpretation guardrails."""
    parser = argparse.ArgumentParser(
        description="Generate probability interpretation guardrails report (Phase 7.2B)"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument(
        "--baseline-results", required=True,
        help="Path to baseline_results_{tag}.json",
    )
    parser.add_argument(
        "--gbm-results", required=True,
        help="Path to gbm_results_{tag}.json",
    )
    parser.add_argument(
        "--baseline-predictions", required=True,
        help="Path to baseline_predictions_{tag}.parquet",
    )
    parser.add_argument(
        "--gbm-predictions", required=True,
        help="Path to gbm_predictions_{tag}.parquet",
    )
    parser.add_argument("--output", required=True, help="Output Markdown report path")

    args = parser.parse_args(argv)

    print("[pi] Loading baseline results...", file=sys.stderr)
    baseline_payload = load_baseline_results(args.baseline_results)

    print("[pi] Loading GBM results...", file=sys.stderr)
    gbm_payload = load_gbm_results(args.gbm_results)

    print("[pi] Extracting log_loss values...", file=sys.stderr)
    ll_dict = extract_model_log_loss(baseline_payload, gbm_payload)

    print("[pi] Loading calibration numbers...", file=sys.stderr)
    cal_summaries = load_calibration_numbers(
        args.baseline_predictions, args.gbm_predictions
    )

    print("[pi] Extracting probability distribution notes...", file=sys.stderr)
    dist_notes = extract_probability_distribution_notes(
        args.baseline_predictions, args.gbm_predictions
    )

    print("[pi] Rendering report...", file=sys.stderr)
    report = render_probability_interpretation_report(
        ll_dict=ll_dict,
        cal_summaries=cal_summaries,
        dist_notes=dist_notes,
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
    )

    write_text(args.output, report)
    print(f"[pi] Report written → {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
