#!/usr/bin/env python3
"""Draws "The Record", the live section of the README, from the GitHub API.

Runs in CI (.github/workflows/update-profile.yml); standard library only.

  GITHUB_TOKEN=... python3 scripts/stats.py dist/stats.svg

It is typeset like the other pages (paper, double rule, EB Garamond) so the
stack of SVGs reads as one printed page. The language chart counts the *primary
language of each public, non-fork repository*: bytes-per-language is dominated
by generated files (for example Unity shader code). The profile repo itself is
left out, since it only holds this tooling.
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

W = 846
PAPER, INK, INK2, RULE, OX = "#f3ecdc", "#231f1a", "#5c5547", "#cbbf9f", "#7a2331"
FALLBACK = "'EB Garamond',Garamond,'Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif"
ROM = f"AURoman,{FALLBACK}"
ITA = f"AUItalic,{FALLBACK}"


# ------------------------------------------------------------------ data
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
    calendar = None
    try:
        q = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions "
                      "weeks{contributionDays{contributionCount date}}}}}}",
             "variables": {"u": OWNER}}
        res = request("https://api.github.com/graphql", q)
        calendar = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    except Exception as exc:  # keep the page alive without the contribution figures
        print("warning: contributions unavailable:", exc, file=sys.stderr)
    return user, repos, calendar


# ------------------------------------------------------------------ typesetting helpers
ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (f"-{ONES[n % 10]}" if n % 10 else "")
    if n < 1000:
        return f"{ONES[n // 100]} hundred" + (f" and {words(n % 100)}" if n % 100 else "")
    rest = n % 1000
    tail = "" if not rest else (f" and {words(rest)}" if rest < 100 else f" {words(rest)}")
    return f"{words(n // 1000)} thousand{tail}"


def font_css():
    css = []
    for fn, family in (("garamond", "AURoman"), ("garamond-italic", "AUItalic")):
        b64 = base64.b64encode((ROOT / "assets" / "fonts" / f"{fn}.woff2").read_bytes()).decode()
        css.append(f"@font-face{{font-family:{family};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css) + "text{font-variant-numeric:lining-nums}.on{font-variant-numeric:oldstyle-nums}.sc{font-variant-caps:all-small-caps}"


def text(x, y, s, family, size, fill=INK, anchor="start", tracking=0, cls=""):
    if anchor == "middle" and tracking:
        x += tracking / 2
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    ls = f' letter-spacing="{tracking}"' if tracking else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" fill="{fill}"{a}{ls}{c}>{escape(str(s))}</text>'


def sep(y):
    cx, x0, x1 = W / 2, 44, W - 44
    return (f'<g stroke="{INK}" fill="none"><path stroke-width=".8" d="M{x0} {y}H{cx-16}M{cx+16} {y}H{x1}"/>'
            f'<path stroke-width=".4" d="M{x0} {y+3.5}H{cx-16}M{cx+16} {y+3.5}H{x1}"/></g>'
            f'<path d="M{cx} {y-6}L{cx+7} {y+1.75}L{cx} {y+9.5}L{cx-7} {y+1.75}Z" fill="{OX}"/>')


def calendar_grid(cal, y0):
    weeks = cal["weeks"]
    pitch = min(13.5, (W - 128) / len(weeks))
    cell = pitch - 3
    x0 = (W - pitch * len(weeks)) / 2 + 1.5
    mx = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1) or 1
    out, last_month = [], None
    for i, w in enumerate(weeks):
        days = w["contributionDays"]
        month = datetime.date.fromisoformat(days[0]["date"]).strftime("%b")
        if month != last_month:
            out.append(text(x0 + i * pitch, y0 - 8, month, ITA, 12, INK2))
            last_month = month
        for j, d in enumerate(days):
            c = d["contributionCount"]
            if c == 0:
                fill, op = RULE, .55
            else:
                fill, op = OX, (.28, .5, .75, 1)[min(3, int(4 * (c - 1) / mx))]
            out.append(f'<rect x="{x0 + i * pitch:.1f}" y="{y0 + j * pitch:.1f}" width="{cell:.1f}" height="{cell:.1f}" '
                       f'fill="{fill}" fill-opacity="{op}"/>')
    return "".join(out), y0 + 7 * pitch


# ------------------------------------------------------------------ the page
def render(user, repos, cal):
    own = [r for r in repos if not r["fork"] and r["name"].lower() != OWNER.lower()]
    langs = Counter(r["language"] for r in own if r["language"])
    ranked = langs.most_common()
    top, rest = (ranked, []) if len(ranked) <= 6 else (ranked[:5], ranked[5:])
    rows = list(top)
    if rest:
        rows.append((f"Other ({len(rest)})", sum(c for _, c in rest)))

    n_repos, year = user["public_repos"], user["created_at"][:4]
    total = cal["totalContributions"] if cal else None
    body = [sep(36), text(W / 2, 76, "The Record", ROM, 15.5, INK, "middle", 5.5, "sc")]

    lines = [f"{words(n_repos).capitalize()} public repositories;"]
    if total is not None:
        lines.append(f"{words(total)} contributions in the past year;")
    lines.append(f"a member of GitHub since {year}.")
    y = 132
    for ln in lines:
        body.append(text(W / 2, y, ln, ITA, 21, INK, "middle"))
        y += 30

    y += 18
    body.append(text(W / 2, y, "Primary languages", ROM, 13.5, OX, "middle", 3, "sc"))
    body.append(text(W / 2, y + 24, f"by number of public repositories, {sum(c for _, c in rows)} in all, forks excluded", ITA, 15, INK2, "middle"))
    y += 62
    BAR_X, BAR_W, top_n = 230, 460, max(c for _, c in rows)
    for name, count in rows:
        w = max(4, BAR_W * count / top_n)
        first = (name, count) == rows[0]
        body.append(text(64, y, name, ROM, 18, INK))
        body.append(f'<rect x="{BAR_X}" y="{y-9}" width="{w:.1f}" height="5" fill="{OX if first else INK}" fill-opacity="{1 if first else .78}"/>')
        body.append(text(BAR_X + w + 12, y, count, ITA, 16, INK2))
        y += 30

    if cal:
        y += 20
        body.append(text(W / 2, y, "Contributions", ROM, 13.5, OX, "middle", 3, "sc"))
        body.append(text(W / 2, y + 24, "each square a day, over the past twelve months", ITA, 15, INK2, "middle"))
        grid, y_end = calendar_grid(cal, y + 66)
        body.append(grid)
        y = y_end + 14

    revised = datetime.datetime.now(datetime.timezone.utc)
    body.append(text(W / 2, y + 30, f"Revised {revised.day} {revised.strftime('%B %Y')}", ITA, 14, INK2, "middle", cls="on"))
    h = int(y + 56)

    frame = "".join(
        f'<path d="M{10+o} -3V{h+3}M{W-10-o} -3V{h+3}" stroke="{INK}" stroke-width="{sw}" fill="none"/>'
        for o, sw in ((0, 1.4), (5, .6))
    )
    desc = (f"The record. {words(n_repos).capitalize()} public repositories"
            + (f", {words(total)} contributions in the past year" if total is not None else "")
            + f", a member of GitHub since {year}. Primary languages by number of public repositories: "
            + ", ".join(f"{n} {c}" for n, c in rows) + ".")
    grain = ('<filter id="g" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
             '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="5"/>'
             '<feColorMatrix values="0 0 0 0 .30  0 0 0 0 .24  0 0 0 0 .14  1.2 0 0 0 -.45"/></filter>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">\n'
        f'<title id="t">The record</title>\n<desc id="d">{escape(desc)}</desc>\n<defs>{grain}</defs>\n<style>{font_css()}</style>\n'
        f'<rect width="{W}" height="{h}" fill="{PAPER}"/><rect width="{W}" height="{h}" filter="url(#g)" opacity=".2"/>\n'
        f"{frame}\n" + "\n".join(body) + "\n</svg>\n"
    )


if __name__ == "__main__":
    svg = render(*fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"wrote {OUT} ({len(svg)/1024:.1f} KB)")
