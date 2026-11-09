# Scripts

- `build_assets.py` typesets the static pages in `assets/pages/` (title, works,
  particulars, instruments, correspondence, link tabs) and the font subsets in
  `assets/fonts/`. Needs `pip install fonttools brotli` and the two EB Garamond
  variable fonts (see `assets/fonts/README.md`):
  `python build_assets.py <fonts-src-dir> assets`
- `stats.py` typesets "The Record" from the GitHub API. It runs in CI
  (`.github/workflows/update-profile.yml`) and publishes to the `output` branch.

Note: GitHub serves repo files through a CDN that caches for five minutes and
ignores query strings on redirects. When a page changes, write it to a new
folder name (for example `assets/pages-2/`) so readers never see a mix of old and new.
