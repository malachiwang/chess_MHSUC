# Appendix figure index

Index of technical figures supporting the [benchmark report](benchmark_report.md). The **headline**
figures (H1–H6) are in `reports/figures/benchmark/`; the **technical appendix** reuses the existing
Phase-16 figures (clock-fraction-axis and full statistical detail) under
`reports/figures/phase_16_2_cross_time_control/` and `reports/figures/phase_16_2_rating_clock_moderation/`.
All figures are descriptive/non-causal. Raw Elo bands are within-control and are not identical
populations across controls.

## Headline figures (`reports/figures/benchmark/`)

| File | Figure | Question answered |
|---|---|---|
| H1_time_forfeit_prevalence_by_control.png | H1 | game-level time-forfeit prevalence by control × month |
| H2_all_games_vs_board_decided_actual_seconds.png | H2 | all-games vs board-decided ES loss vs actual seconds |
| H3_move_quality_actual_seconds_by_elo_{3plus0,5plus0,10plus0}.png | H3 | ES loss vs actual seconds by absolute 200-Elo band |
| H4_move_quality_by_move_number_and_clock_state_{3plus0,5plus0,10plus0}.png | H4 | ES loss vs move number by clock state |
| H5_move_number_actual_clock_heatmap_{3plus0,5plus0,10plus0}.png | H5 | move-number × actual-seconds danger-region heatmap |
| H6_month_replication_summary.png | H6 | month replication of the critical-clock time-forfeit attenuation (all vs board-decided) |
| count_tables.md | — | denominators, 200-Elo bin counts, termination prevalence |

## Cross-time-control appendix (`reports/figures/phase_16_2_cross_time_control/`)

Normalized clock-fraction-axis versions and full statistical detail. Source report:
[cross_time_control_move_quality_…_v1.md](cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md).

| File | Content | Role |
|---|---|---|
| fig_16_2_01_clock_fraction_es_loss_by_control.png | ES loss vs clock fraction by control | normalized twin of H2/H3 |
| fig_16_2_02_clock_fraction_clipped_cp_by_control.png | clipped-CP vs clock fraction | transform-free cross-check |
| fig_16_2_03_large_loss_probability_by_control.png | P(ES loss ≥ 0.10) vs clock fraction | large-loss variant |
| fig_16_2_04_game_level_termination_rate_by_control.png | termination rate by control | superseded by H1 |
| fig_16_2_05_board_decided_clock_fraction_es_loss.png | board-decided clock-fraction curves | normalized board-decided twin of H2 |
| fig_16_2_06_rating_clock_heatmap_by_control.png | rating × clock-fraction heatmap | superseded by H5 (move-number × seconds) |
| fig_16_2_07_eval_band_clock_fraction_by_control.png | evaluation-state-localized curves | localization detail |
| fig_16_2_08_phase_clock_fraction_by_control.png | phase-localized curves | localization detail |
| fig_16_2_09_controlled_clock_interactions.png | controlled clock contrasts + interactions | model coefficients |
| fig_16_2_10_month_replication_summary.png | month replication (model contrasts) | technical twin of H6 |

## Rating-moderation appendix (`reports/figures/phase_16_2_rating_clock_moderation/`)

Full rating × clock analysis (quintiles, percentiles, Holm-controlled contrasts). Source report:
[rating_clock_moderation_…_v1.md](rating_clock_moderation_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md).

| File | Content | Role |
|---|---|---|
| fig_16_2e_01_clock_es_loss_by_rating_quintile.png | clock × ES loss by quintile | quintile twin of H3 |
| fig_16_2e_02_critical_clock_contrast_by_quintile.png | D(c,Q1..Q5) critical-clock contrast | rating-moderation detail |
| fig_16_2e_03_rating_clock_heatmap.png | rating × clock heatmap | technical |
| fig_16_2e_04_board_decided_moderation.png | board-decided rating moderation | robustness |
| fig_16_2e_05_within_control_rating_moderation.png | within-control M(c) | technical contrast |
| fig_16_2e_06_cross_control_rating_moderation.png | cross-control moderation (null) | technical contrast |
| fig_16_2e_07_player_side_time_forfeit_by_rating.png | player-side time-forfeit by rating | secondary descriptive |
| fig_16_2e_08_endgame_only_moderation.png | endgame-only rating moderation (sign flip) | conditioning sensitivity |
| fig_16_2e_09_month_replication_summary.png | rating-moderation month replication | technical |

## Marginal vs conditional (disclosure)

The headline figures (H2–H6) show the **descriptive, game-normalized** move-quality curves and the
**board-decided attenuation**. The descriptive curves are U-shaped, and the **unadjusted**
critical-minus-high clock gap is mixed and small (+0.003 / −0.002 / −0.006 for 3+0 / 5+0 / 10+0) —
confounded by game stage, because critical-clock states are concentrated in endgames. The clean
"lower clock → higher loss" **conditional** gradient (critical-vs-high ≈ +0.012 / +0.008 / +0.006) is
a model-adjusted result and lives in the controlled-model report
([cross_time_control_move_quality](cross_time_control_move_quality_3plus0_5plus0_10plus0_2024_09_2024_10_v1.md)),
not in an unadjusted aggregate. The original draft of H6 plotted the unadjusted marginal gap; it was
replaced because the marginal contrast answers a different (composition-confounded) question, and the
marginal numbers are disclosed here and in the [benchmark report](benchmark_report.md) rather than
hidden.

## Unresolved / deferred

- **Position sharpness moderation** — a MultiPV best-versus-second-move-gap analysis (in the spirit of
  Barthelemy variation entropy) is documented in the technical reports
  (`reports/phase_reports/phase_15_5c_sharpness_result_consolidation_c3c_claim_update.md`) and remains
  **unresolved / underpowered**. No headline sharpness figure is generated.
- **Increment time controls** (3+2, 5+3, etc.) — deferred; out of scope for this benchmark.

## Full scientific reports

The complete, preregistered analysis lives in `reports/phase_reports/`
(phases 11–17) and the two main analysis reports above. The prior-art / repository-overlap audit
([phase_16_2g](phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md)) documents
what is replication, what is commodity, and what is apparently distinct.
