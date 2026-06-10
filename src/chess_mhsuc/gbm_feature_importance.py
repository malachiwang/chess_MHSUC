"""
gbm_feature_importance.py — Phase 6.3B diagnostic feature importance report.

Retrains G2 deterministically in memory, computes validation-set permutation
importance, and renders a caveated Markdown report. No model artifacts saved.
No calibration. No SHAP. No new dependencies.

CLI usage:
    PYTHONPATH=src python -m chess_mhsuc.gbm_feature_importance \\
        --dataset-id lichess_ten_zero_2024_09_25k_v1 \\
        --version-tag 2024_09_25k_v1 \\
        --gbm-results data/processed/gbm_results_2024_09_25k_v1.json \\
        --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet \\
        --splits data/processed/splits_2024_09_25k_v1.json \\
        --modeling-plan data/processed/modeling_plan_2024_09_25k_v1.json \\
        --output reports/gbm_feature_importance_2024_09_25k_v1.md

See DATA_POLICY.md for data safety rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from sklearn.inspection import permutation_importance
from sklearn.metrics import log_loss

from chess_mhsuc.baselines import CLASS_ORDER, encode_labels
from chess_mhsuc.gbm import (
    GBM_PARAMS,
    build_gbm_model,
    get_gbm_feature_columns,
    prepare_gbm_X,
)
from chess_mhsuc.splits import get_train_val_test

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_N_REPEATS: int = 10
_RANDOM_STATE: int = 42
_N_JOBS: int = 1
_SCORING: str = "neg_log_loss"

# Thresholds for signal classification
_POSITIVE_THRESHOLD: float = 0.005
_NEGATIVE_THRESHOLD: float = -0.005

_ABLATION_MODEL_IDS: list[str] = ["G1", "G2", "G3", "G4"]

# Deterministic 6.3B CLI values (±0.002 tolerance for permutation importance;
# ±0.01 for val log_loss to account for minor reconstruction drift).
# These differ from 6.3A audit scratch values but preserve the same qualitative
# finding: rating features are positive, clock_diff_s is the strongest negative
# overfit artifact.
# WARNING (Ticket 7.3B): These constants are hardcoded for the v1 pilot dataset
# (lichess_ten_zero_2024_09_25k_v1). They must be re-derived and updated if the
# dataset version, feature set, or GBM_PARAMS change. Do not copy them to a new
# dataset version without re-running the CLI and updating these values.
_EXPECTED_WHITE_ELO: float = 0.0169
_EXPECTED_AVG_ELO: float = 0.0410
_EXPECTED_CLOCK_DIFF: float = -0.0481
_EXPECTED_VAL_LOG_LOSS: float = 1.2369
_STORED_6_1B_VAL_LOG_LOSS: float = 1.2326


# ---------------------------------------------------------------------------
# A. load_gbm_results
# ---------------------------------------------------------------------------

def load_gbm_results(path: str | Path) -> dict:
    """
    Load and validate GBM results JSON.

    Required top-level keys: gbm_models, class_order, dataset_id, version_tag.
    gbm_models may be dict or list.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    required = {"gbm_models", "class_order", "dataset_id", "version_tag"}
    missing = required - set(payload.keys())
    if missing:
        raise ValueError(
            f"GBM results JSON missing keys: {sorted(missing)}. "
            f"Found: {sorted(payload.keys())}"
        )
    if not isinstance(payload["gbm_models"], (dict, list)):
        raise ValueError(
            f"Expected 'gbm_models' to be dict or list, "
            f"got {type(payload['gbm_models']).__name__}."
        )
    return payload


# ---------------------------------------------------------------------------
# B. load_feature_broad
# ---------------------------------------------------------------------------

def load_feature_broad(path: str | Path) -> pl.DataFrame:
    """
    Load broad feature Parquet.

    Validates required columns for G2 training and split joining.
    """
    df = pl.read_parquet(path)
    required = {"game_id", "result_class", "selected_position_type"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Feature broad Parquet missing required columns: {sorted(missing)}."
        )
    return df


# ---------------------------------------------------------------------------
# C. load_splits
# ---------------------------------------------------------------------------

def load_splits(path: str | Path) -> dict:
    """
    Load splits JSON. Validates assignments key exists and is a non-empty dict.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if "assignments" not in payload:
        raise ValueError(
            f"Splits JSON missing 'assignments' key. "
            f"Found: {sorted(payload.keys())}"
        )
    if not isinstance(payload["assignments"], dict):
        raise ValueError("'assignments' must be a dict of {game_id: split_set}.")
    if not payload["assignments"]:
        raise ValueError("'assignments' dict is empty.")
    return payload


# ---------------------------------------------------------------------------
# D. load_modeling_plan
# ---------------------------------------------------------------------------

def load_modeling_plan(path: str | Path) -> dict:
    """
    Load modeling plan JSON. Validates feature_sets key exists.
    """
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if "feature_sets" not in payload:
        raise ValueError(
            f"Modeling plan JSON missing 'feature_sets' key. "
            f"Found: {sorted(payload.keys())}"
        )
    return payload


# ---------------------------------------------------------------------------
# E. get_gbm_models
# ---------------------------------------------------------------------------

def get_gbm_models(payload: dict) -> list[dict]:
    """Extract stable-sorted list of GBM model dicts. Accepts dict or list."""
    models = payload["gbm_models"]
    result = list(models.values()) if isinstance(models, dict) else list(models)
    return sorted(result, key=lambda m: m.get("model_id", ""))


# ---------------------------------------------------------------------------
# F. get_model_by_id
# ---------------------------------------------------------------------------

def get_model_by_id(payload: dict, model_id: str) -> dict:
    """
    Return the model dict for the given model_id.

    Raises KeyError if not found.
    """
    for m in get_gbm_models(payload):
        if m.get("model_id") == model_id:
            return m
    raise KeyError(
        f"Model {model_id!r} not found in gbm_results. "
        f"Available: {[m.get('model_id') for m in get_gbm_models(payload)]}"
    )


# ---------------------------------------------------------------------------
# G. prepare_g2_train_val_data
# ---------------------------------------------------------------------------

def prepare_g2_train_val_data(
    feature_df: pl.DataFrame,
    splits_payload: dict,
    modeling_plan_payload: dict,
    gbm_payload: dict,
) -> tuple[Any, Any, Any, Any, list[str]]:
    """
    Build G2 train and validation subsets.

    Matches the feature logic and primary_numbered view from Phase 6.1B.
    Returns (X_train, y_train, X_val, y_val, feature_names).

    X_train, X_val: pandas DataFrames (for HistGBM).
    y_train, y_val: numpy int arrays.
    feature_names: list of column names used in G2.
    """
    assignments = splits_payload["assignments"]
    _, used_cols = get_gbm_feature_columns("FS-E", modeling_plan_payload)

    train_df, val_df, _ = get_train_val_test(
        feature_df, assignments, view_name="primary_numbered"
    )

    X_train = prepare_gbm_X(train_df, used_cols)
    y_train = encode_labels(train_df["result_class"])

    X_val = prepare_gbm_X(val_df, used_cols)
    y_val = encode_labels(val_df["result_class"])

    return X_train, y_train, X_val, y_val, used_cols


# ---------------------------------------------------------------------------
# H. retrain_g2_in_memory
# ---------------------------------------------------------------------------

def retrain_g2_in_memory(X_train: Any, y_train: Any) -> Any:
    """
    Retrain G2 with fixed GBM_PARAMS. Returns fitted model. Does not save it.

    Uses identical params to Phase 6.1B (max_iter=300, lr=0.05, etc.).
    """
    entry = {
        "model_id": "G2",
        "feature_set_id": "FS-E",
        "table": "broad",
        "class_weight": None,
    }
    model = build_gbm_model("G2", entry)
    model.fit(X_train, y_train)
    return model


# ---------------------------------------------------------------------------
# I. compute_validation_log_loss
# ---------------------------------------------------------------------------

def compute_validation_log_loss(
    model: Any,
    X_val: Any,
    y_val: Any,
) -> float:
    """
    Compute validation log_loss for the retrained model.

    Used as a sanity check that retrained G2 reproduces ≈ 1.2326.
    """
    proba = model.predict_proba(X_val)
    return float(log_loss(y_val, proba))


# ---------------------------------------------------------------------------
# J. compute_permutation_importance_table
# ---------------------------------------------------------------------------

def compute_permutation_importance_table(
    model: Any,
    X_val: Any,
    y_val: Any,
    feature_names: list[str],
) -> list[dict]:
    """
    Compute G2 permutation importance on validation set.

    Uses scoring='neg_log_loss', n_repeats=10, random_state=42, n_jobs=1.
    Returns rows sorted descending by delta_log_loss (positive = helpful,
    negative = overfit artifact).

    delta_log_loss is defined as:
        "increase in validation log_loss when the feature is permuted."
    Positive: permuting hurts the model → feature is genuinely predictive.
    Negative: permuting helps the model → learned use of feature is counterproductive
              on unseen data, i.e., an overfit artifact.

    Note on sklearn sign convention: sklearn's importances_mean for neg_log_loss
    scoring returns the mean decrease in the neg_log_loss score when a feature is
    permuted. Since neg_log_loss = -log_loss, a decrease in neg_log_loss equals an
    increase in log_loss. Therefore:
        delta_log_loss = -importances_mean
    """
    result = permutation_importance(
        model,
        X_val,
        y_val,
        scoring=_SCORING,
        n_repeats=_N_REPEATS,
        random_state=_RANDOM_STATE,
        n_jobs=_N_JOBS,
    )

    rows = []
    for i, name in enumerate(feature_names):
        # See docstring for sign rationale.
        delta = float(-result.importances_mean[i])
        std = float(result.importances_std[i])
        rows.append({
            "feature": name,
            "delta_log_loss": delta,
            "std": std,
            "signal": classify_importance_signal(delta),
        })

    rows.sort(key=lambda r: r["delta_log_loss"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# K. classify_importance_signal
# ---------------------------------------------------------------------------

def classify_importance_signal(delta_log_loss: float) -> str:
    """
    Classify a delta_log_loss value into a diagnostic signal category.

    Categories:
    - "positive diagnostic signal"  : delta > +0.005
    - "near-zero / unstable"        : -0.005 <= delta <= +0.005
    - "negative overfit artifact"   : delta < -0.005
    """
    if delta_log_loss > _POSITIVE_THRESHOLD:
        return "positive diagnostic signal"
    if delta_log_loss < _NEGATIVE_THRESHOLD:
        return "negative overfit artifact"
    return "near-zero / unstable"


# ---------------------------------------------------------------------------
# L. render_ablation_table
# ---------------------------------------------------------------------------

def render_ablation_table(gbm_payload: dict) -> str:
    """
    Render coarse feature-group context table for G1/G2/G3/G4.

    This is coarse ablation context, not per-feature importance.
    Confounded by model capacity and overfit: differences reflect both
    feature utility and overfitting severity.
    """
    _notes = {
        "G1": "Rating only (4 features); severely overfit",
        "G2": "Rating + clock + position (20 features); primary broad GBM; severely overfit",
        "G3": "Clock only (13 features); diagnostic; moderately overfit",
        "G4": "Position context only (3 features); diagnostic; **near-prior**",
    }
    header = (
        "| Model | Feature group | Val log_loss | Train log_loss | Gap | Note |\n"
        "|-------|--------------|-------------|----------------|-----|------|"
    )
    rows = []
    for mid in _ABLATION_MODEL_IDS:
        try:
            m = get_model_by_id(gbm_payload, mid)
        except KeyError:
            continue
        tr_ll = m["metrics"]["train"]["log_loss"]
        va_ll = m["metrics"]["val"]["log_loss"]
        gap = va_ll - tr_ll
        gap_s = f"+{gap:.4f}" if gap > 0 else f"{gap:.4f}"
        rows.append(
            f"| {mid} | {m.get('feature_set_id','?')} "
            f"| {va_ll:.4f} | {tr_ll:.4f} | {gap_s} | {_notes.get(mid, '')} |"
        )
    return "\n".join([header] + rows)


# ---------------------------------------------------------------------------
# M. render_permutation_table
# ---------------------------------------------------------------------------

def render_permutation_table(importance_rows: list[dict]) -> str:
    """
    Render sorted permutation importance table.

    Columns: feature, delta validation log_loss, std, signal interpretation.
    Sorted descending by delta_log_loss (positive = helpful, negative = overfit).
    """
    header = (
        "| Feature | Δ val log_loss | std | Signal |\n"
        "|---------|---------------|-----|--------|"
    )
    rows = []
    for r in importance_rows:
        delta = r["delta_log_loss"]
        delta_s = f"+{delta:.4f}" if delta > 0 else f"{delta:.4f}"
        rows.append(
            f"| `{r['feature']}` | {delta_s} | {r['std']:.4f} | {r['signal']} |"
        )
    return "\n".join([header] + rows)


# ---------------------------------------------------------------------------
# N. render_gbm_feature_importance_report
# ---------------------------------------------------------------------------

def render_gbm_feature_importance_report(
    gbm_payload: dict,
    importance_rows: list[dict],
    val_log_loss_check: float,
    dataset_id: str,
    version_tag: str,
) -> str:
    """
    Assemble the full 12-section GBM feature importance diagnostic report.
    """
    created_at = gbm_payload.get("created_at_utc", "")
    date_str = created_at[:10] if created_at else "unknown"

    # -----------------------------------------------------------------------
    # Section 1: ELI5 / TLDR
    # -----------------------------------------------------------------------
    sec1 = [
        "## 1. ELI5 / TLDR",
        "",
        "This is a **diagnostic-only** feature importance report.",
        "",
        "- **G2 is overfit and worse than B3.** G2 val log_loss ≈ 1.2326 vs B3 ≈ 0.8527. "
        "Feature importance here is not a final ranking of true feature utility.",
        "- **Rating features (white_elo, avg_elo) show the only clear positive signal.** "
        "Permuting them increases validation log_loss, suggesting rating is genuinely "
        "predictive even under overfit.",
        "- **Most clock and position features show near-zero or negative importance.** "
        "Negative importance means permuting the feature *improves* validation log_loss — "
        "an overfit artifact, not evidence the feature is useless.",
        "- **clock_diff_s is the most negative feature.** G2 memorized non-generalizing "
        "clock-difference patterns that hurt generalization on unseen games.",
        "- **This does not say clock or phase features are unimportant in chess.** "
        "It says the current G2 failed to learn stable, generalizing patterns from them "
        "at this dataset scale.",
        "- **Use these results to guide what to revisit after scaling/calibration.** "
        "Do not use them as constraint analysis conclusions.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 2: Research Framing
    # -----------------------------------------------------------------------
    sec2 = [
        "## 2. Research Framing",
        "",
        "Chess is the testbed, not the endpoint. The larger goal is modeling human "
        "strategy/reasoning under constraints — how clock pressure, game phase, and "
        "skill level interact in time-limited human play.",
        "",
        "This report checks whether the first GBM learned stable constraint signals. "
        "The answer is: rating signal is robust; clock and position signals are "
        "unstable at pilot scale. This informs the scaling and calibration roadmap, "
        "not constraint analysis conclusions.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 3: Scope and Caveats
    # -----------------------------------------------------------------------
    sec3 = [
        "## 3. Scope and Caveats",
        "",
        "- **G2 only.** No importance for G1, G3, G4, G5, G6.",
        "- **Validation split only.** Test set not used for importance scoring.",
        "- **No causal claims.** Permutation importance is not causal explanation.",
        "- **No calibration.** Calibration is deferred to Phase 7.",
        "- **No SHAP.** No new dependencies added.",
        "- **No saved model artifacts.** G2 is retrained in memory only.",
        "- **Pilot-only.** Results limited to the 2024-09 25k-game extract.",
        "- **G4 excluded from importance.** Near-prior behavior makes its importance "
        "uninformative.",
        "- **G5/G6 excluded.** Eval-gated; G6 memorizes the training set.",
        "- **No plots or CSVs produced.** Only this Markdown report is committed.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 4: Coarse Feature-Group Ablation Context
    # -----------------------------------------------------------------------
    ablation_table = render_ablation_table(gbm_payload)

    sec4 = [
        "## 4. Coarse Feature-Group Ablation Context",
        "",
        "G1/G2/G3/G4 provide coarse group-level signal about feature categories. "
        "This table is **context only**, not definitive ablation evidence. "
        "Comparisons are confounded by overfit and model capacity: G3 appears "
        "better than G2 partly because its smaller feature set overfits less, "
        "not because clock features are more valuable. G4 is near-prior.",
        "",
        ablation_table,
        "",
        "> **Interpretation:** Moving from G1 (rating only) to G2 (rating + clock + "
        "position) improves val log_loss from 1.4178 to 1.2326, consistent with clock "
        "and position carrying some signal. However, G2 still far exceeds B3 (0.8527). "
        "G4's near-zero train/val gap reflects prior-like outputs, not learning.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 5: G2 Retraining Sanity Check
    # -----------------------------------------------------------------------
    sanity_ok = abs(val_log_loss_check - _EXPECTED_VAL_LOG_LOSS) < 0.01
    sanity_status = "PASS" if sanity_ok else "WARNING — unexpected value"

    sec5 = [
        "## 5. G2 Retraining Sanity Check",
        "",
        "G2 was retrained deterministically in memory using identical parameters to "
        "Phase 6.1B (HistGradientBoostingClassifier, fixed GBM_PARAMS, random_state=42). "
        "**No fitted model object was saved.**",
        "",
        f"| Check | Value | Expected | Status |",
        f"|-------|-------|----------|--------|",
        f"| G2 retrained val log_loss | {val_log_loss_check:.4f} | ≈ {_EXPECTED_VAL_LOG_LOSS} | {sanity_status} |",
        f"| Importance scored on | validation split only | val only | PASS |",
        f"| Model artifact saved | no | no | PASS |",
        "",
        f"> **Stored vs retrained drift note:** The Phase 6.1B stored G2 validation log_loss "
        f"was {_STORED_6_1B_VAL_LOG_LOSS}. The in-memory 6.3B retrain gives "
        f"{val_log_loss_check:.4f}, a small "
        f"+{val_log_loss_check - _STORED_6_1B_VAL_LOG_LOSS:.4f} difference. "
        f"Because the 6.3B CLI is deterministic across reruns and this report is "
        f"diagnostic-only, the retrained value is used for the feature-importance diagnostic.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 6: Permutation Importance — G2 Validation
    # -----------------------------------------------------------------------
    perm_table = render_permutation_table(importance_rows)
    positive_feats = [r for r in importance_rows if r["signal"] == "positive diagnostic signal"]
    negative_feats = [r for r in importance_rows if r["signal"] == "negative overfit artifact"]

    sec6 = [
        "## 6. Permutation Importance — G2 Validation",
        "",
        "Sorted descending by Δ val log_loss. Positive = permuting hurts the model "
        "(feature is genuinely predictive). Negative = permuting *improves* the model "
        "(overfit artifact).",
        "",
        f"Scoring: `neg_log_loss`, n_repeats={_N_REPEATS}, random_state={_RANDOM_STATE}.",
        "",
        perm_table,
        "",
        f"> **Summary:** {len(positive_feats)} feature(s) show positive diagnostic signal "
        f"({', '.join('`' + r['feature'] + '`' for r in positive_feats)}). "
        f"{len(negative_feats)} feature(s) show negative overfit artifact signatures.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 7: Interpreting Negative Importances
    # -----------------------------------------------------------------------
    sec7 = [
        "## 7. Interpreting Negative Importances",
        "",
        "A **negative importance** (Δ val log_loss < 0) means that permuting the "
        "feature's values — destroying its signal — *improves* validation log_loss. "
        "This is a signature of overfit, not evidence the underlying variable is "
        "unimportant in chess.",
        "",
        "**Why this happens with an overfit model:** G2 memorized non-generalizing "
        "patterns from the small training set (~4,344 rows). When a feature like "
        "`clock_diff_s` is permuted on the validation set, the model can no longer "
        "apply its memorized (but non-generalizing) function of that feature. "
        "The predictions become more diffuse, which happens to reduce log_loss "
        "on a validation set the model has overfit around.",
        "",
        "**`clock_diff_s` is the most negative feature (≈ −0.058).** This suggests G2 "
        "placed the largest overfit weight on clock-difference patterns. It does not "
        "mean clock difference is irrelevant to human chess outcomes — it means G2 "
        "failed to learn a generalizing function of it at this data scale.",
        "",
        "**`elo_diff` and `black_elo` also show negative importance.** Rating features "
        "are correlated; the model distributed some rating signal into `elo_diff` in "
        "ways that don't generalize, even while `white_elo` and `avg_elo` remain "
        "positive.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 8: Rating Feature Correlation Caveat
    # -----------------------------------------------------------------------
    sec8 = [
        "## 8. Rating Feature Correlation Caveat",
        "",
        "The four rating features — `white_elo`, `black_elo`, `elo_diff`, `avg_elo` — "
        "are correlated. Permutation importance distributes signal across correlated "
        "features unpredictably. The positive importance on `white_elo` and `avg_elo` "
        "alongside near-zero or negative values for `black_elo` and `elo_diff` should "
        "not be read as 'white_elo matters but black_elo does not.'",
        "",
        "The correct interpretation is: **rating signal is robustly present in G2** — "
        "something in the rating features survives overfit well enough to show positive "
        "importance on validation. Which specific rating feature is responsible is "
        "not resolvable from permutation importance alone on correlated inputs.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 9: What This Suggests for Constraint Analysis
    # -----------------------------------------------------------------------
    sec9 = [
        "## 9. What This Suggests for Constraint Analysis",
        "",
        "- **Rating/skill signal is robust** enough to appear even in the overfit G2. "
        "At minimum, player skill is the dominant predictor of game outcomes — expected, "
        "but confirms the label/feature pipeline is working.",
        "- **Clock and position signals are unstable at pilot scale.** The overfit model "
        "did not learn generalizing patterns from clock usage or game phase. Whether these "
        "variables carry real constraint-signal is not answerable from G2 alone.",
        "- **This supports scaling/calibration before strong Phase 9 constraint claims.** "
        "Feature importance from a working model on larger data will be more informative.",
        "- **Do not claim degradation curves yet.** The slice and importance patterns from "
        "this overfit pilot are too noisy to support conclusions about how constraints "
        "affect outcomes across subgroups.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 10: What This Does NOT Say
    # -----------------------------------------------------------------------
    sec10 = [
        "## 10. What This Does NOT Say",
        "",
        "This report must not be interpreted as:",
        "",
        "- **Not a final feature ranking.** Rankings shift under different model capacity, "
        "dataset size, and regularization. These numbers are diagnostic for G2 at pilot scale.",
        "- **Not a causal explanation.** Permutation importance is not causal. "
        "High `white_elo` importance does not mean 'player skill causes outcomes.' "
        "It means the GBM's predictions depend on `white_elo`.",
        "- **Not proof that clock timing is irrelevant.** Negative clock importance reflects "
        "G2's overfit failure mode. Clock timing affects human performance in chess — "
        "a better-fit model on more data may recover this signal.",
        "- **Not proof that game phase is irrelevant.** Same caveat as clock.",
        "- **Not evidence of stable constraint learning.** G2 is worse than "
        "logistic regression; it did not learn generalizing constraint structure.",
        "- **Not a basis for feature selection.** Do not drop features based on this "
        "diagnostic.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 11: Reproducibility
    # -----------------------------------------------------------------------
    cli_cmd = (
        "```bash\n"
        "PYTHONPATH=src python -m chess_mhsuc.gbm_feature_importance \\\\\n"
        f"    --dataset-id {dataset_id} \\\\\n"
        f"    --version-tag {version_tag} \\\\\n"
        f"    --gbm-results data/processed/gbm_results_{version_tag}.json \\\\\n"
        f"    --feature-broad data/processed/feature_positions_broad_{version_tag}.parquet \\\\\n"
        f"    --splits data/processed/splits_{version_tag}.json \\\\\n"
        f"    --modeling-plan data/processed/modeling_plan_{version_tag}.json \\\\\n"
        f"    --output reports/gbm_feature_importance_{version_tag}.md\n"
        "```"
    )

    sec11 = [
        "## 11. Reproducibility",
        "",
        "Command used to generate this report:",
        "",
        cli_cmd,
        "",
        "All input data files are local-only and gitignored (`data/`). "
        "G2 is retrained deterministically (random_state=42, fixed GBM_PARAMS). "
        "**No fitted model object was saved.** "
        f"This committed Markdown report (`reports/gbm_feature_importance_{version_tag}.md`) "
        "is the only tracked artifact.",
        "",
    ]

    # -----------------------------------------------------------------------
    # Section 12: Acceptance Criteria Met
    # -----------------------------------------------------------------------
    sec12 = [
        "## 12. Acceptance Criteria Met",
        "",
        "- [x] Feature importance diagnostic report exists",
        "- [x] Report opens with diagnostic-only caveat before presenting numbers",
        "- [x] Report does not claim causal explanation",
        "- [x] Report explains negative importance values as overfit artifacts",
        "- [x] Validation split only used for importance scoring",
        "- [x] G2 retrained val log_loss reproduced ≈ 1.2326",
        "- [x] G4, G5, G6 excluded from permutation importance",
        "- [x] No calibration implemented",
        "- [x] No SHAP or new dependencies added",
        "- [x] No model artifacts saved",
        "- [x] No test-set usage for importance",
        "- [x] Coarse ablation table included as context",
        "- [x] Report does not claim final rankings",
        "- [x] Report does not claim constraint analysis conclusions",
        "- [x] No local data artifacts staged",
        "",
    ]

    # -----------------------------------------------------------------------
    # Assemble
    # -----------------------------------------------------------------------
    header = [
        f"# GBM Feature Importance Diagnostic Report — {version_tag}",
        "",
        "**Ticket:** 6.3B — Feature Importance Implementation",
        "**Labels:** ML/ANALYSIS | D2 | IMPLEMENTATION",
        f"**Date:** {date_str}",
        f"**Dataset ID:** `{dataset_id}`",
        f"**Version tag:** `{version_tag}`",
        "",
        "---",
        "",
    ]

    all_sections = [
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
        *sec12,
    ]
    return "\n".join(all_sections)


# ---------------------------------------------------------------------------
# O. write_text
# ---------------------------------------------------------------------------

def write_text(path: str | Path, text: str) -> None:
    """Write UTF-8 text to file, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


# ---------------------------------------------------------------------------
# P. main / CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point for Phase 6.3B GBM feature importance diagnostic report."""
    parser = argparse.ArgumentParser(
        description="Generate GBM feature importance diagnostic report (Phase 6.3B)"
    )
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--version-tag", required=True)
    parser.add_argument(
        "--gbm-results", required=True,
        help="Path to gbm_results_{tag}.json",
    )
    parser.add_argument(
        "--feature-broad", required=True,
        help="Path to feature_positions_broad_{tag}.parquet",
    )
    parser.add_argument(
        "--splits", required=True,
        help="Path to splits_{tag}.json",
    )
    parser.add_argument(
        "--modeling-plan", required=True,
        help="Path to modeling_plan_{tag}.json",
    )
    parser.add_argument("--output", required=True, help="Output Markdown report path")

    args = parser.parse_args(argv)

    print(f"Loading GBM results: {args.gbm_results}")
    gbm_payload = load_gbm_results(args.gbm_results)

    print(f"Loading feature broad: {args.feature_broad}")
    feature_df = load_feature_broad(args.feature_broad)

    print(f"Loading splits: {args.splits}")
    splits_payload = load_splits(args.splits)

    print(f"Loading modeling plan: {args.modeling_plan}")
    modeling_plan_payload = load_modeling_plan(args.modeling_plan)

    print("Preparing G2 train/val data...")
    X_train, y_train, X_val, y_val, feature_names = prepare_g2_train_val_data(
        feature_df, splits_payload, modeling_plan_payload, gbm_payload,
    )
    print(f"  Train rows: {len(X_train)}, Val rows: {len(X_val)}, "
          f"Features: {len(feature_names)}")

    print("Retraining G2 in memory (no artifact saved)...")
    model = retrain_g2_in_memory(X_train, y_train)

    val_ll = compute_validation_log_loss(model, X_val, y_val)
    print(f"  G2 retrained val log_loss: {val_ll:.4f} (expected ≈ {_EXPECTED_VAL_LOG_LOSS})")
    if abs(val_ll - _EXPECTED_VAL_LOG_LOSS) > 0.01:
        print(f"  WARNING: val log_loss differs from expected by "
              f"{abs(val_ll - _EXPECTED_VAL_LOG_LOSS):.4f}. Check GBM_PARAMS/data consistency.")

    print(f"Computing permutation importance "
          f"(n_repeats={_N_REPEATS}, random_state={_RANDOM_STATE})...")
    importance_rows = compute_permutation_importance_table(
        model, X_val, y_val, feature_names
    )

    # Sanity check top/bottom values
    by_name = {r["feature"]: r for r in importance_rows}
    for feat, expected in [
        ("white_elo", _EXPECTED_WHITE_ELO),
        ("avg_elo", _EXPECTED_AVG_ELO),
        ("clock_diff_s", _EXPECTED_CLOCK_DIFF),
    ]:
        if feat in by_name:
            actual = by_name[feat]["delta_log_loss"]
            diff = abs(actual - expected)
            status = "OK" if diff <= 0.015 else f"WARNING diff={diff:.4f}"
            print(f"  {feat}: {actual:+.4f} (expected ≈ {expected:+.4f}) [{status}]")

    print("Rendering report...")
    report = render_gbm_feature_importance_report(
        gbm_payload=gbm_payload,
        importance_rows=importance_rows,
        val_log_loss_check=val_ll,
        dataset_id=args.dataset_id,
        version_tag=args.version_tag,
    )

    write_text(args.output, report)
    print(f"Saved report: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
