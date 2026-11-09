#!/usr/bin/env python3
"""Draws the live GitHub stats panel (assets/stats.svg) from the GitHub API.

Runs in CI (.github/workflows/update-profile.yml); standard library only.

  GITHUB_TOKEN=... python3 scripts/stats.py dist/stats.svg

Metric choice: bytes-per-language is dominated by generated files (for example
Unity shader code), so the chart counts the *primary language of each public,
non-fork repository* instead.
"""
import base64
import datetime
import json
import os
import sys
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

OWNER = os.environ.get("GITHUB_REPOSITORY_OWNER", "aykanugur")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/stats.svg")

INK0, INK1, LINE, LINE2 = "#080b12", "#101725", "#1f2837", "#2c384d"
FG, FG2, FG3, SUN, OK = "#eef1f6", "#a3adbe", "#76829a", "#ffb454", "#3ddc97"


def request(url, body=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    user = request(f"https://api.github.com/users/{OWNER}")
    repos, page = [], 1
    while True:
        batch = request(f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    contributions = None
    try:
        q = {"query": 'query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions}}}}',
             "variables": {"u": OWNER}}
        res = request("https://api.github.com/graphql", q)
        contributions = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except Exception as exc:  # keep the panel alive without the contributions tile
        print("warning: contributions unavailable:", exc, file=sys.stderr)
    return user, repos, contributions


def font_css():
    css = []
    for key, family in (("serif", "AUSerif"), ("sans", "AUSans"), ("mono", "AUMono")):
        b64 = base64.b64encode((ROOT / "assets" / "fonts" / f"{key}.woff2").read_bytes()).decode()
        css.append(f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


SERIF = "AUSerif,'Instrument Serif',Georgia,serif"
SANS = "AUSans,'Instrument Sans','Segoe UI',Helvetica,Arial,sans-serif"
MONO = "AUMono,'JetBrains Mono',ui-monospace,Consolas,monospace"


def text(x, y, s, family, size, fill, anchor="start", tracking=0):
    an = f' text-anchor="{anchor}"' if anchor != "start" else ""
    ls = f' letter-spacing="{tracking}"' if tracking else ""
    return f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}"{an}{ls}>{escape(str(s))}</text>'


def render(user, repos, contributions):
    own = [r for r in repos if not r["fork"]]
    langs = Counter(r["language"] for r in own if r["language"])
    n = sum(langs.values())
    ranked = langs.most_common()
    top, rest = (ranked, []) if len(ranked) <= 6 else (ranked[:5], ranked[5:])
    rows = [(name, c, SUN) for name, c in top]
    if rest:
        rows.append((f"Other ({len(rest)})", sum(c for _, c in rest), FG3))

    W = 880
    metrics = [
        (f'{user["public_repos"]:,}', "PUBLIC REPOSITORIES"),
        (f"{contributions:,}" if contributions is not None else "—", "CONTRIBUTIONS, LAST 12 MONTHS"),
        (user["created_at"][:4], "ON GITHUB SINCE"),
    ]
    ROW0, STEP = 232, 28
    H = ROW0 + STEP * len(rows) + 20
    top_n = max(c for _, c, _ in rows) if rows else 1
    BAR_X, BAR_W = 196, 520

    out = []
    out.append(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="url(#pg)" stroke="{LINE}"/>')
    out.append(f'<path d="M16 1.5H{W-16}" stroke="#fff" stroke-opacity=".07"/>')
    out.append(f'<circle cx="36" cy="30" r="3.5" fill="{OK}"/>')
    out.append(text(48, 34, "GITHUB  /  LIVE", MONO, 10.5, FG3, tracking=1.8))
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%d %b %Y").upper()
    out.append(text(W - 32, 34, f"UPDATED {today}", MONO, 10.5, FG3, anchor="end", tracking=1.8))
    out.append(f'<path d="M0 54.5H{W}" stroke="{LINE}"/>')
    for i, (value, label) in enumerate(metrics):
        x = 32 + i * 282
        out.append(text(x - 2, 126, value, SERIF, 68, FG, tracking=-1))
        out.append(text(x, 152, label, MONO, 10.5, FG3, tracking=1.6))
        if i:
            out.append(f'<path d="M{x-22} 78V158" stroke="{LINE}"/>')
    out.append(f'<path d="M0 180.5H{W}" stroke="{LINE}"/>')
    out.append(text(32, 208, "PRIMARY LANGUAGE OF EACH PUBLIC, NON-FORK REPOSITORY", MONO, 10.5, FG3, tracking=1.6))
    out.append(text(W - 32, 208, f"{n} REPOS", MONO, 10.5, FG3, anchor="end", tracking=1.6))
    for i, (name, count, color) in enumerate(rows):
        y = ROW0 + i * STEP
        w = max(8, BAR_W * count / top_n)
        out.append(text(32, y + 8, name, SANS, 15, FG))
        out.append(f'<rect x="{BAR_X}" y="{y}" width="{BAR_W}" height="8" rx="4" fill="{LINE}" fill-opacity=".7"/>')
        out.append(f'<path d="M{BAR_X} {y}H{BAR_X+w-4:.1f}A4 4 0 0 1 {BAR_X+w-4:.1f} {y+8}H{BAR_X}Z" fill="{color}"/>')
        out.append(text(BAR_X + BAR_W + 16, y + 8.5, count, MONO, 12, FG2))
    body = "\n".join(out)

    desc = (f"GitHub activity for {OWNER}: {metrics[0][0]} public repositories, {metrics[1][0]} contributions in the last 12 months, "
            f"on GitHub since {metrics[2][0]}. Primary languages of public non-fork repositories: "
            + ", ".join(f"{name} {c}" for name, c, _ in rows) + ".")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">\n'
        f'<title id="t">GitHub stats</title>\n<desc id="d">{escape(desc)}</desc>\n'
        f'<defs><linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{INK1}"/>'
        f'<stop offset="1" stop-color="{INK0}"/></linearGradient></defs>\n<style>{font_css()}</style>\n{body}\n</svg>\n'
    )


if __name__ == "__main__":
    svg = render(*fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({len(svg)/1024:.1f} KB)")
