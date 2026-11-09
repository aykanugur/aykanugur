# Scripts

- `build_assets.py` typesets the static pages in `assets/` (title, particulars,
  works, instruments, correspondence) and the font subsets in `assets/fonts/`.
  Needs `pip install fonttools brotli` and the two EB Garamond variable fonts
  (see `assets/fonts/README.md`): `python build_assets.py <fonts-src-dir> assets`
- `stats.py` typesets "The Record" from the GitHub API. It runs in CI
  (`.github/workflows/update-profile.yml`) and publishes to the `output` branch.
