# Notice — scope of the MIT license and third-party components

The [MIT license](LICENSE) applies **only** to the original source code and documentation in this
repository (the chess-MHSUC project). It does **not** relicense, and confers no rights over, any third
party's work. In particular:

- **Stockfish** (GPL-3.0) is an external chess engine invoked as a system tool. It is not included or
  redistributed here and retains its own license.
- **Lichess open game database** and any data derived from it remain subject to Lichess's terms. The
  dense move-level Parquet datasets are gitignored and are not redistributed by this repository.
- **Referenced external repositories** — including `ianfab/chess-analysis` (AGPL-3.0),
  `CSSLab/maia-chess` (GPL-3.0), `CSSLab/maia2` (MIT), `marcusbuffett/oxi` (no license),
  `ippolito-cmu/allie` (MIT), `bleongcw/Arrakis_Engine` (AGPL-3.0), and others — are cited for
  attribution and comparison only. **No third-party source code is copied or vendored into this
  repository.** Each external project retains its own license.
- **Python dependencies** listed in `requirements.txt` are each governed by their own licenses.

This project independently reimplements standard move-quality metrics and clock parsing; it does not
incorporate code from the copyleft or unlicensed repositories above. See the
[prior-art / repository-overlap audit](reports/phase_reports/phase_16_2g_prior_art_repository_overlap_project_kill_audit.md)
for the full comparison.
