# Scripts

- `build_assets.py` draws the static panels in `assets/` (banner, about, work rows,
  stack, contact) and the font subsets in `assets/fonts/`.
  Needs `pip install fonttools brotli` and the three source fonts (see `assets/fonts/README.md`):
  `python build_assets.py <fonts-src-dir> assets`
- `stats.py` draws the live stats panel from the GitHub API. It runs in CI
  (`.github/workflows/update-profile.yml`) and publishes to the `output` branch.
