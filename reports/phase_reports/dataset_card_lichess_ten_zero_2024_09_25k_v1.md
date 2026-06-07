# Dataset Card: lichess_ten_zero_2024_09_25k_v1

**Version tag:** `2024_09_25k_v1`  
**Source:** Lichess standard rated 10+0 (600+0), month 2024-09  
**Created:** 2026-06-07  
**Status:** Local-only pilot dataset. No raw data committed to Git.

---

## 1. ELI5 / TLDR

This dataset contains 8,528 chess position checkpoints from 2,323 unique Lichess 10+0 games (September 2024). Each position is annotated with player ratings, clock times, engine evaluation (where available), game phase, and a three-class outcome label (White win / Draw / Black win). The data is local-only; this card documents what it is, how it was produced, and how to reproduce it.

---

## 2. Dataset Identity

| Field | Value |
|-------|-------|
| `dataset_id` | `lichess_ten_zero_2024_09_25k_v1` |
| `version_tag` | `2024_09_25k_v1` |
| `source_name` | lichess |
| `time_control` | 600+0 (10+0) |
| `source_month` | 2024-09 |
| `raw_games_cap` | 25,000 |
| `max_accepted_basic` | 2,500 |
| `rated_only` | True |
| `standard_only` | True |

---

## 3. Source Provenance

**Source URL:** `https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst`  
**Source file:** `lichess_db_standard_rated_2024-09.pgn.zst`  
**Source month:** 2024-09  
**Time control filter:** `600+0`  

The source archive is a Lichess monthly PGN dump compressed with Zstandard. It is not downloaded or stored locally — the parser streams it directly from the URL.

---

## 4. Pipeline Summary

```
Stage 1: run_parser.py  — stream Lichess PGN → interim parsed tables
  Input:  Lichess .pgn.zst archive (streamed from URL)
  Output: data/interim/game_records_*.parquet
          data/interim/position_records_*.parquet
          data/interim/parser_validation_*_metadata.json

Stage 2: cleaning.py   — apply v1 cleaning rules → processed tables
  Input:  data/interim/game_records_*.parquet
          data/interim/position_records_*.parquet
  Output: data/processed/ten_zero_game_records_*.parquet
          data/processed/ten_zero_positions_broad_*.parquet
          data/processed/ten_zero_positions_eval_*.parquet
          data/processed/cleaning_metadata_*.json

Stage 3: features.py   — add derived features → 40-column feature tables
  Input:  data/processed/ten_zero_positions_broad_*.parquet
          data/processed/ten_zero_positions_eval_*.parquet
  Output: data/processed/feature_positions_broad_*.parquet
          data/processed/feature_positions_eval_*.parquet
          data/processed/feature_metadata_*.json

Stage 4: assess_dataset.py — dataset quality checks → Markdown + JSON
  Input:  feature_positions_broad/eval_*.parquet
          feature_metadata_*.json
  Output: data/processed/assessment_*.json
          reports/phase_reports/phase_4_1b_*.md

Stage 5: dataset_version.py — unified metadata → JSON manifest + this card
  Input:  all metadata JSON files + feature Parquet files
  Output: data/processed/dataset_version_*.json  (local-only)
          reports/phase_reports/dataset_card_*.md  (committed)
```

---

## 5. Artifact Inventory

All artifacts are local-only (gitignored under `data/`). SHA256 hashes enable integrity verification on reproduction.

| Artifact | Stage | Role | Rows | Size | SHA256 (prefix) |
|----------|-------|------|------|------|-----------------|
| `data/interim/game_records_2024_09_25k_v1.parquet` | parser | interim_game_records | 2,467 | 48.5 KB | `c32bd59d12e0...` |
| `data/interim/position_records_2024_09_25k_v1.parquet` | parser | interim_position_records | 8,528 | 116.8 KB | `74e878dcfa85...` |
| `data/interim/parser_validation_2024_09_25k_v1_metadata.json` | parser | parser_metadata | — | 1.3 KB | `494639db6bd8...` |
| `data/processed/ten_zero_game_records_2024_09_25k_v1.parquet` | cleaning | clean_game_records | 2,460 | 48.1 KB | `11563fc6b8bd...` |
| `data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet` | cleaning | clean_positions_broad | 8,528 | 116.8 KB | `74e878dcfa85...` |
| `data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet` | cleaning | clean_positions_eval | 1,168 | 28.1 KB | `cef1c369bd62...` |
| `data/processed/cleaning_metadata_2024_09_25k_v1.json` | cleaning | cleaning_metadata | — | 1.5 KB | `25788880529a...` |
| `data/processed/feature_positions_broad_2024_09_25k_v1.parquet` | features | feature_positions_broad | 8,528 | 204.0 KB | `149192e95fc8...` |
| `data/processed/feature_positions_eval_2024_09_25k_v1.parquet` | features | feature_positions_eval | 1,168 | 50.8 KB | `c8dcdd132318...` |
| `data/processed/feature_metadata_2024_09_25k_v1.json` | features | feature_metadata | — | 3.5 KB | `cc415d07513b...` |
| `data/processed/assessment_2024_09_25k_v1.json` | assessment | assessment_json | — | 15.9 KB | `57222373fa93...` |

---

## 6. Row Counts and Core Statistics

| Metric | Value |
|--------|-------|
| Broad feature rows | 8,528 |
| Eval feature rows | 1,168 |
| Unique games (broad) | 2,323 |
| Unique games (eval) | 365 |
| Draw rate (broad) | 5.83% |
| Eval coverage (broad) | 13.7% |
| avg_elo broad | 1558.7 |
| avg_elo eval subset | 1578.5 (Δ = +19.8 Elo) |
| Clock anomalies | 7 rows |
| Duplicate ply checkpoints | 166 rows |

### Result distribution (broad)

| result_class | Count | % |
|--------------|-------|---|
| WHITE_WIN | 3,985 | 46.73% |
| BLACK_WIN | 4,046 | 47.44% |
| DRAW | 497 | 5.83% |

---

## 7. Column / Feature Schema

Total columns in feature table: **40**

### Default predictive features (24)

```
white_elo, black_elo, elo_diff, avg_elo, white_clock_s, black_clock_s, clock_diff_s, white_clock_s_capped, black_clock_s_capped, white_clock_frac, black_clock_frac, clock_diff_frac, white_low_60, black_low_60, white_low_30, black_low_30, white_low_10, black_low_10, clock_anomaly, selected_position_type, move_number, phase, checkpoint_index, phase_index
```

### Eval predictive features (6, nullable)

```
eval_cp, eval_cp_clipped, eval_mate, is_mate_eval, eval_mate_abs, eval_white_winning
```

### Labels (never model inputs)

```
result_class, white_result_numeric
```

### Caution columns (present but require careful use)

```
is_last_checkpoint, side_to_move_next, white_to_move_next, duplicate_ply_checkpoint
```

### Slice / group columns

```
game_id, termination, is_time_forfeit, has_eval
```

### Nullable columns (expected nulls — eval unavailable for 86.3% of broad rows)

```
eval_cp, eval_cp_clipped, eval_mate, eval_mate_abs, eval_white_winning
```

---

## 8. Leakage and Safety Policy

**Leakage safety confirmed:** `True`  
**Baseline readiness (all checks pass):** `True`

### Forbidden leakage columns

| Column | Reason |
|--------|--------|
| `result_class` | target label, never model input |
| `white_result_numeric` | target label, never model input |
| `termination` | post-game information |
| `is_time_forfeit` | derived from post-game termination |
| `n_plies_total` | post-game length, available only after game ends |
| `white_rating_diff` | post-game rating change |
| `black_rating_diff` | post-game rating change |
| `accepted_basic` | parser internal flag, not a game feature |
| `accepted_eval` | parser internal flag, not a game feature |
| `rejection_reason` | parser internal flag, not a game feature |
| `game_id` | group/split key only, never a model feature |

### Leakage policy summary

result_class and white_result_numeric are target labels and must never be model inputs. termination and n_plies_total are post-game information. white/black_rating_diff are post-game rating changes. game_id is a group/split key only.

---

## 9. Known Caveats

**C1.** DRAW class is ~5.83% of broad rows — minority class. Accuracy alone is misleading; use log loss / Brier score / calibration curves.

**C2.** Eval subset avg_elo is ~20 Elo higher than broad — non-random selection bias. Models trained on eval-gated data may not generalize to lower-rated games.

**C3.** 166 rows (83 games × 2) have duplicate_ply_checkpoint=True — same (game_id, ply) in both a numbered checkpoint and the 'last' checkpoint. Must deduplicate before training (recommended: keep numbered checkpoint, drop coincident 'last').

**C4.** The 'last' checkpoint is semantically different from numbered checkpoints. move_10 through move_40 always have white to move next; 'last' does not. Treat is_last_checkpoint as a caution column.

**C5.** 7 rows have raw clock_s > 600 (clock anomalies). Raw clock values are unreliable for these rows; capped values (white/black_clock_s_capped) are safe to use.

**C6.** 25,000 raw game cap from a single source month (2024-09). Results may not generalize to other months, seasons, or the full Lichess 10+0 population.

**C7.** Split must be by game_id. Never split rows independently — multiple rows from the same game would leak across train/val/test boundaries.

**C8.** All data artifacts are local-only and gitignored. Regenerate from source using the reproduction commands in this document.

---

## 10. Reproduction Commands

All data artifacts must be regenerated locally. The source archive is publicly available at the Lichess open database. A working Python 3.13 environment with project dependencies installed (`pip install -r requirements.txt`) is required.

```bash
# Stage 1: Parser
# Note: --version-tag 'v1' produces file names with stem '2024_09_25k_v1'
# because run_parser prepends source month and cap to the tag.
PYTHONPATH=src python -m chess_mhsuc.run_parser --url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst --max-games 25000 --max-accepted 2500 --source-file lichess_db_standard_rated_2024-09.pgn.zst --output-dir data/interim --version-tag v1

# Stage 2: Cleaning
PYTHONPATH=src python -m chess_mhsuc.cleaning --game-records data/interim/game_records_2024_09_25k_v1.parquet --position-records data/interim/position_records_2024_09_25k_v1.parquet --output-dir data/processed --version-tag 2024_09_25k_v1

# Stage 3: Feature engineering
PYTHONPATH=src python -m chess_mhsuc.features --positions-broad data/processed/ten_zero_positions_broad_2024_09_25k_v1.parquet --positions-eval data/processed/ten_zero_positions_eval_2024_09_25k_v1.parquet --output-dir data/processed --version-tag 2024_09_25k_v1

# Stage 4: Dataset assessment
PYTHONPATH=src python -m chess_mhsuc.assess_dataset --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet --feature-eval data/processed/feature_positions_eval_2024_09_25k_v1.parquet --feature-metadata data/processed/feature_metadata_2024_09_25k_v1.json --output-dir reports/phase_reports --version-tag 2024_09_25k_v1

# Stage 5: Dataset version manifest (this card)
PYTHONPATH=src python -m chess_mhsuc.dataset_version --dataset-id lichess_ten_zero_2024_09_25k_v1 --version-tag 2024_09_25k_v1 --source-url https://database.lichess.org/standard/lichess_db_standard_rated_2024-09.pgn.zst --source-file lichess_db_standard_rated_2024-09.pgn.zst --source-month 2024-09 --parser-metadata data/interim/parser_validation_2024_09_25k_v1_metadata.json --cleaning-metadata data/processed/cleaning_metadata_2024_09_25k_v1.json --feature-metadata data/processed/feature_metadata_2024_09_25k_v1.json --assessment-json data/processed/assessment_2024_09_25k_v1.json --feature-broad data/processed/feature_positions_broad_2024_09_25k_v1.parquet --feature-eval data/processed/feature_positions_eval_2024_09_25k_v1.parquet --output-dir data/processed --card-output-dir reports/phase_reports
```

---

## 11. Git and Dependency Metadata

### Pipeline code git state
(The committed code state that produced the data artifacts.)

| Field | Value |
|-------|-------|
| Commit | `70b5f7367d1973ea18ad6403e144a1c24d6642b3` |
| Branch | `main` |
| Status clean | `False` |
| Dirty files | M  ROADMAP.md, A  reports/phase_reports/phase_4_1b_feature_dataset_assessment.md, A  src/chess_mhsuc/assess_dataset.py, A  tests/test_assess_dataset.py, ?? src/chess_mhsuc/dataset_version.py |

### Manifest generation git state
(The git state at the time this dataset card was generated.)

| Field | Value |
|-------|-------|
| Commit | `70b5f7367d1973ea18ad6403e144a1c24d6642b3` |
| Branch | `main` |
| Status clean | `False` |
| Dirty/staged files | see manifest JSON for full list |

**Note:** The data artifacts were produced by the pipeline code state shown above. The dataset card itself was generated during Ticket 4.2B, which may introduce additional unstaged/staged files. The commit hash in the pipeline code state is the authoritative reference for reproducing the data.

### Key dependency versions

| Package | Version |
|---------|---------|
| `jupyter` | 1.1.1 |
| `matplotlib` | 3.10.8 |
| `pandas` | 3.0.1 |
| `polars` | 1.38.1 |
| `pyarrow` | 23.0.1 |
| `pytest` | 9.0.2 |
| `scikit-learn` | 1.8.0 |
| `tqdm` | 4.67.1 |
| `zstandard` | 0.24.0 |

---

## 12. Known Metadata Inconsistencies

**version_tag** (parser): Parser metadata JSON records version_tag='v1', while the canonical dataset version_tag is '2024_09_25k_v1'. File names are correct (run_parser._make_stem() prepends source month and cap to the tag), but the version_tag field in parser_validation_..._metadata.json is ambiguous.

> Resolution: This manifest normalizes to the canonical version_tag '2024_09_25k_v1'. Future parser runs should pass --version-tag 2024_09_25k_v1 to eliminate the discrepancy, or the _make_stem() function should be updated to accept a full canonical tag.

**implementation_notes.test_count** (assessment): The assessment JSON (assessment_2024_09_25k_v1.json) contains implementation_notes.test_count = 'TBD'. This placeholder was not updated after the real test run (45 tests). Do not treat 'TBD' as an authoritative count.

> Resolution: The correct test count for Ticket 4.1B is 45 new tests (322 total). The assessment Markdown report was manually updated. The JSON sidecar was not re-generated. This manifest records the correct counts from the test suite.

---

## 13. Data Safety Notes

- All data artifacts under `data/` are gitignored. No Parquet or JSON data is committed.
- Usernames are absent from all processed, feature, and assessment tables.
- The raw Lichess archive (`lichess_db_standard_rated_2024-09.pgn.zst`) was not downloaded to disk; it was streamed directly from the URL during parsing.
- No CSV files, model files, or calibration files were created in this dataset version.
- No data was modified or deleted by the dataset_version stage.

---

## 14. Recommended Next Step

**Ticket 5.1A — Modeling Split and Baseline Audit**

Define the game-level train/validation/test split by `game_id` and establish the baseline model suite (majority-class, rating-only, eval-only, eval+rating, eval+rating+clocks, eval+rating+clocks+phase) before any GBM training.
