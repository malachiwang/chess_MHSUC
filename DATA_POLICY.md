# Data Policy

This document governs how data is downloaded, stored, processed, transformed, and committed.

## 1. Main rule

Real data does not go into Git.

This includes raw, interim, processed, and model-ready real game data.

## 2. Git-ignored data paths

The following paths are local-only:

```text
data/raw/
data/interim/
data/processed/
```

The `.gitignore` should continue to ignore data artifacts such as:

```text
*.pgn
*.pgn.zst
*.parquet
*.csv
*.duckdb
*.sqlite
*.db
*.joblib
*.pkl
*.pt
*.pth
*.onnx
```

## 3. What may be committed

Allowed:

- source code,
- documentation,
- governance docs,
- markdown reports,
- small figures,
- tests,
- tiny synthetic PGN fixtures,
- configuration templates without secrets.

Conditionally allowed:

- very small generated sample files only if synthetic or explicitly documented as non-real test fixtures.

## 4. What must not be committed

Do not commit:

- real downloaded PGNs,
- `.pgn.zst` archives,
- real parsed game tables,
- Parquet datasets,
- CSV exports of real game data,
- DuckDB databases,
- large model artifacts,
- usernames from processed datasets,
- secrets or API keys.

## 5. Raw data

Raw Lichess archives should live under:

```text
data/raw/lichess/
```

Examples:

```text
data/raw/lichess/lichess_db_standard_rated_YYYY-MM.pgn.zst
```

Raw data should be treated as immutable after download. Pipeline code should read from raw data and write derived outputs elsewhere.

## 6. Interim data

Interim data should live under:

```text
data/interim/
```

Examples:

```text
data/interim/ten_zero_scan_25k_v1.parquet
data/interim/parser_debug_positions_v1.parquet
```

Interim data may be messy or incomplete. It is not the basis for final claims unless explicitly promoted to processed status.

## 7. Processed data

Processed data should live under:

```text
data/processed/
```

Examples:

```text
data/processed/ten_zero_eval_positions_v1.parquet
data/processed/ten_zero_games_v1.parquet
```

Processed datasets must have documented filters, schema, and creation script.

## 8. Data file naming

Use descriptive names with version suffixes:

```text
<scope>_<content>_<version>.<extension>
```

Examples:

```text
ten_zero_eval_positions_v1.parquet
ten_zero_checkpoint_positions_v1.parquet
ten_zero_game_metadata_v1.parquet
```

Avoid vague names:

```text
data.parquet
final.csv
new_dataset.csv
cleaned2.parquet
```

## 9. Usernames and identifiers

Policy:

- Do not retain usernames in processed datasets by default.
- If player-level splitting is needed, use anonymized or hashed IDs.
- Any retention of player identifiers must be justified in a phase report.

## 10. Claude data restrictions

Claude must not delete, overwrite, rename, move, compress, decompress, or bulk-transform data files unless Malachi explicitly asks for that exact operation in the current prompt.

Claude may write scripts that would perform data operations, but running those scripts on real data requires explicit permission.

## 11. Deletion policy

No automated deletion of raw, interim, or processed data is allowed unless explicitly requested by Malachi in the current turn.

Allowed safe commands without special permission:

```text
ls
find
wc
head
tail
du
stat
git status
git diff
```

Potentially dangerous operations requiring explicit permission:

```text
rm
mv
cp -f
find ... -delete
truncate
sed -i
python scripts that overwrite data
bulk decompression/compression
```

## 12. Reproducibility

The repository should provide:

- scripts that regenerate processed datasets,
- exact filter definitions,
- source file names and dates,
- schema reports,
- experiment logs.

It should not provide the real processed datasets themselves.

## 13. Initial sample-size policy

The first iteration should be capped.

Recommended first scans:

```text
10,000 games: parser/data sanity
25,000 games: first useful availability estimates
50,000 games: early modeling if enough qualifying rows exist
100,000+ rows: serious pilot after parser is verified
```

Scale only if the prior step answers:

- Do enough `10+0` games exist in the scanned source?
- Do enough have `%eval` annotations?
- Do enough have complete clock data?
- Are labels and filters behaving correctly?
- Are baseline models stable?

## 14. External data reference

Use the Lichess database page as the canonical source for raw data access instructions:

https://database.lichess.org/
