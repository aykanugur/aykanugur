#!/usr/bin/env python3
"""Builds the static pages of the profile README.

The README is one printed page assembled from stacked SVGs: warm paper, a double
rule frame, EB Garamond (small capitals, old-style figures), oxblood ink.
Each SVG embeds an exact glyph subset of the font as a woff2 data URI, so it
renders the same everywhere and never depends on a third-party host.

Usage:  python build_assets.py <fonts-src-dir> <out-dir>   (pages go to <out-dir>/pages)
Needs:  pip install fonttools brotli
Font:   EB Garamond (SIL OFL), see assets/fonts/README.md
"""
import base64
import sys
from io import BytesIO
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

W = 846  # GitHub's README column on desktop, so the page is not rescaled
PAPER, INK, INK2, RULE, OX = "#f3ecdc", "#231f1a", "#4d4739", "#cbbf9f", "#7a2331"
FALLBACK = "'EB Garamond',Garamond,'Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif"
FEATURES = ["kern", "liga", "smcp", "c2sc", "onum", "lnum", "swsh", "case", "locl", "ccmp", "mark", "mkmk"]


class Face:
    def __init__(self, path, family):
        font = instancer.instantiateVariableFont(TTFont(str(path)), {"wght": 400}, inplace=False)
        buf = BytesIO()
        font.save(buf)
        self.raw, self.family = buf.getvalue(), family
        font = TTFont(BytesIO(self.raw))
        self.cmap, self.hmtx, self.upem = font.getBestCmap(), font["hmtx"], font["head"].unitsPerEm

    def width(self, text, size, tracking=0.0):
        w = sum(self.hmtx[self.cmap[ord(c)]][0] if ord(c) in self.cmap else self.upem * 0.5 for c in text)
        return w * size / self.upem + tracking * len(text)

    def woff2_b64(self, chars):
        font = TTFont(BytesIO(self.raw))
        opts = subset.Options()
        opts.layout_features, opts.name_IDs, opts.hinting, opts.notdef_outline = FEATURES, [0, 1, 2, 4, 6], False, True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)) + " ")
        sub.subset(font)
        out = BytesIO()
        font.flavor = "woff2"
        font.save(out)
        return base64.b64encode(out.getvalue()).decode()


FACES = {
    "rom": Face(SRC / "EBGaramond-VF.ttf", "AURoman"),
    "ita": Face(SRC / "EBGaramond-Italic-VF.ttf", "AUItalic"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Doc:
    def __init__(self, h, title, desc, top=False, bottom=False):
        self.h, self.title, self.desc, self.top, self.bottom = h, title, desc, top, bottom
        self.body = []
        self.used = {k: set() for k in FACES}

    def add(self, s):
        self.body.append(s)

    def _attrs(self, face, size, fill, anchor, tracking, cls):
        f = FACES[face]
        a = f'font-family="{f.family},{FALLBACK}" font-size="{size}" fill="{fill}"'
        if anchor != "start":
            a += f' text-anchor="{anchor}"'
        if tracking:
            a += f' letter-spacing="{tracking}"'
        if cls:
            a += f' class="{cls}"'
        return a

    def text(self, face, x, y, s, size, fill=INK, anchor="start", tracking=0, cls=""):
        self.used[face].update(s)
        if anchor == "middle" and tracking:
            x += tracking / 2  # letter-spacing trails the last glyph
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" {self._attrs(face, size, fill, anchor, tracking, cls)}>{esc(s)}</text>')

    def rich(self, face, x, y, parts, size, anchor="middle", cls="", tracking=0):
        spans = ""
        for s, fill in parts:
            self.used[face].update(s)
            spans += f'<tspan fill="{fill}">{esc(s)}</tspan>'
        if anchor == "middle" and tracking:
            x += tracking / 2
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" {self._attrs(face, size, INK, anchor, tracking, cls)}>{spans}</text>')

    def font_faces(self):
        return "".join(
            f"@font-face{{font-family:{FACES[k].family};src:url(data:font/woff2;base64,{FACES[k].woff2_b64(c)}) format('woff2')}}"
            for k, c in self.used.items() if c
        )

    def render(self):
        h = self.h
        faces = self.font_faces()
        css = ("text{font-variant-numeric:lining-nums}.on{font-variant-numeric:oldstyle-nums}.sc{font-variant-caps:all-small-caps}"
               ".sw{font-feature-settings:'swsh','kern'}")
        yt, yb = (10 if self.top else -3), (h - 10 if self.bottom else h + 3)
        frame = ""
        for off, sw in ((0, 1.4), (5, .6)):
            l, r, t, b = 10 + off, W - 10 - off, (yt + off if self.top else yt), (yb - off if self.bottom else yb)
            if self.top and self.bottom:
                p = f"M{l} {t}H{r}V{b}H{l}Z"
            elif self.top:
                p = f"M{l} {b}V{t}H{r}V{b}"
            elif self.bottom:
                p = f"M{l} {t}V{b}H{r}V{t}"
            else:
                p = f"M{l} {t}V{b}M{r} {t}V{b}"
            frame += f'<path d="{p}" fill="none" stroke="{INK}" stroke-width="{sw}" stroke-linejoin="miter"/>'
        grain = ('<filter id="g" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
                 '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="5"/>'
                 '<feColorMatrix values="0 0 0 0 .30  0 0 0 0 .24  0 0 0 0 .14  1.2 0 0 0 -.45"/></filter>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-labelledby="t d">\n'
            f'<title id="t">{esc(self.title)}</title>\n<desc id="d">{esc(self.desc)}</desc>\n<defs>{grain}</defs>\n'
            f"<style>{faces}{css}</style>\n"
            f'<rect width="{W}" height="{h}" fill="{PAPER}"/><rect width="{W}" height="{h}" filter="url(#g)" opacity=".2"/>\n'
            f"{frame}\n" + "\n".join(self.body) + "\n</svg>\n"
        )

    def save(self, name):
        svg = self.render()
        (OUT / "pages").mkdir(exist_ok=True)
        (OUT / "pages" / name).write_text(svg, encoding="utf-8")
        print(f"{name:22s} {len(svg)/1024:6.1f} KB  h={self.h}")


# ------------------------------------------------------------------ helpers
def wrap(face, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if FACES[face].width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + [cur] if cur else lines


def sep(d, y):
    """Double hairline with an oxblood lozenge: the section divider."""
    cx, x0, x1 = W / 2, 44, W - 44
    d.add(f'<g stroke="{INK}" fill="none"><path stroke-width=".8" d="M{x0} {y}H{cx-16}M{cx+16} {y}H{x1}"/>'
          f'<path stroke-width=".4" d="M{x0} {y+3.5}H{cx-16}M{cx+16} {y+3.5}H{x1}"/></g>')
    d.add(f'<path d="M{cx} {y-6}L{cx+7} {y+1.75}L{cx} {y+9.5}L{cx-7} {y+1.75}Z" fill="{OX}"/>')


def heading(d, y, title):
    d.text("rom", W / 2, y, title, 15.5, INK, anchor="middle", tracking=5.5, cls="sc")


def leader(d, x1, x2, y):
    if x2 - x1 > 14:
        d.add(f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y}" y2="{y}" stroke="{INK2}" stroke-width="1.5" '
              f'stroke-linecap="round" stroke-dasharray="0.1 5" opacity=".65"/>')


# ================================================================== TITLE
def title():
    d = Doc(342, "Aykan Uğur, I build language models",
            "Title page. Aykan Uğur. I build language models. Natural language processing, machine learning, Turkish AI. "
            "İzmir, Turkey. Open to work.", top=True)
    cx = W / 2
    d.text("rom", cx, 62, "Natural language processing  ·  Machine learning  ·  Turkish AI", 14.5, INK2, "middle", 3.2, "sc")
    sep(d, 92)
    d.text("rom", cx, 176, "AYKAN UĞUR", 66, INK, "middle", 10)
    d.rich("ita", cx, 224, [("I build ", INK2), ("language models.", OX)], 32)
    sep(d, 260)
    d.rich("rom", cx, 298, [("İzmir  ·  Turkey   ·   ", INK), ("Open to work", OX)], 15.5, cls="sc", tracking=4)
    d.text("ita", cx, 322, "38° 25′ N,  27° 08′ E", 15, INK2, "middle", cls="on")
    d.save("title.svg")


# ================================================================== PARTICULARS
def particulars():
    rows = [
        ("Name", "Aykan Uğur", INK),
        ("Residence", "İzmir, Turkey", INK),
        ("Occupation", "Undergraduate Assistant, İzmir University of Economics", INK),
        ("Concerned with", "Language models, NLP, machine learning, and teaching", INK),
        ("In hand", "AykanLLM-1.3B, a language model of my own", INK),
        ("Studying", "A GPT from scratch, by way of the NeetCode ML course", INK),
        ("Exploring", "Turkish NLP: its models, datasets and papers", INK),
        ("Seeking", "A position, and collaborators on LLMs and NLP", INK),
        ("Remark", "Has worked at a summer camp. Twice.", INK),
        ("Correspondence", "aykanugur157@gmail.com", OX),
    ]
    LX, VX = 64, 252
    VW = W - 64 - VX
    laid, y = [], 118
    for label, value, color in rows:
        lines = wrap("rom", value, 19, VW)
        laid.append((y, label, lines, color))
        y += 24 * len(lines) + 12
    h = y + 20
    d = Doc(h, "Particulars",
            "Particulars. " + " ".join(f"{l}: {v}." for l, v, _ in rows))
    sep(d, 36)
    heading(d, 76, "Particulars")
    for y, label, lines, color in laid:
        d.text("ita", LX, y, label, 18.5, INK2)
        leader(d, LX + FACES["ita"].width(label, 18.5) + 9, VX - 12, y - 4)
        for i, ln in enumerate(lines):
            d.text("rom", VX, y + 24 * i, ln, 19, color)
    d.save("particulars.svg")


# ================================================================== WORKS
WORK = [
    dict(file="work-gpt", title="GPT from scratch", repo="neetcode-gpt",
         desc="A tokenizer, multi-head and grouped-query attention, a KV-cache and a full transformer, assembled from my NeetCode ML course submissions.",
         tags=["Python", "PyTorch"]),
    dict(file="work-bhts", title="BHTS Air Tracking", repo="bhts  &  bhts-api",
         desc="Balıkesir Hava Takip Sistemi: an air-tracking system with an ASP.NET Core backend, MessagePack over SignalR, and a React frontend.",
         tags=["C#", "ASP.NET Core", "React", "SignalR"]),
    dict(file="work-innovatepam", title="InnovatEPAM Portal", repo="innovatepam-portal",
         desc="An internal innovation platform. Employees submit ideas, administrators review them through a configurable multi-stage pipeline, and results are tracked with analytics.",
         tags=["Next.js", "TypeScript", "Prisma", "PostgreSQL"]),
    dict(file="work-taylanator", title="Taylanator", repo="Taylanator-Question-ML-GAME",
         desc="An Akinator-style guessing game. It asks questions and uses machine learning to work out the animal, celebrity, game, film or object you have in mind.",
         tags=["Python", "Machine learning"]),
    dict(file="work-quake", title="Earthquakes of Turkey", repo="Earthquake-Database-For-Turkey",
         desc="A friendlier way to browse Turkey's earthquakes: sort by any column, filter by your city. A hobby project.",
         tags=["Python"]),
    dict(file="work-german", title="German Vocabulary Quiz", repo="German-Vocabulary-Quiz-App-TR",
         desc="A vocabulary quiz for learning German, made for Turkish speakers.",
         tags=["Python"]),
]


def works():
    d = Doc(104, "Selected works", "Selected works. Each entry links to its repository.")
    sep(d, 30)
    heading(d, 70, "Selected Works")
    d.save("works-head.svg")

    for w in WORK:
        lines = wrap("ita", w["desc"], 18, W - 128)
        y_title = 40
        y_desc = y_title + 34
        y_tags = y_desc + 24 * len(lines) + 12
        h = y_tags + 32
        tags = "  ·  ".join(w["tags"])
        d = Doc(h, f"{w['title']} ({w['repo']})",
                f"{w['title']}, repository {w['repo']}. {w['desc']} {', '.join(w['tags'])}.")
        d.text("rom", 64, y_title, w["title"], 28, INK)
        label = w["repo"] + "  \u2197"
        rw = FACES["ita"].width(label, 16.5)
        d.text("ita", W - 64, y_title, label, 16.5, OX, "end")
        leader(d, 64 + FACES["rom"].width(w["title"], 28) + 12, W - 64 - rw - 12, y_title - 5)
        for i, ln in enumerate(lines):
            d.text("ita", 64, y_desc + 24 * i, ln, 18, INK2)
        d.text("rom", 64, y_tags, tags, 14, OX, tracking=2.4, cls="sc")
        if w is not WORK[-1]:
            d.add(f'<path d="M64 {h-.5}H{W-64}" stroke="{RULE}" stroke-width="1"/>')
        d.save(w["file"] + ".svg")


# ================================================================== INSTRUMENTS
def instruments():
    groups = [
        ("AI & machine learning", "Python, PyTorch, TensorFlow, scikit-learn, MATLAB"),
        ("Languages", "C#, Java, C, C++, TypeScript, JavaScript"),
        ("Backend & data", ".NET, ASP.NET Core, SignalR, PostgreSQL, MySQL, Firebase, Prisma"),
        ("Frontend & mobile", "React, Next.js, Tailwind CSS, Flutter, Android"),
        ("Games & design", "Unity, Unreal Engine, Blender, Figma, Arduino"),
        ("Workshop", "Git, GitHub Actions, Docker, Linux, VS Code, PyCharm, Rider"),
    ]
    CW, X1 = (W - 128 - 44) / 2, 64
    X2 = X1 + CW + 44
    y = 124
    placed = []
    for r in range(3):
        cells = []
        for c in range(2):
            name, items = groups[r * 2 + c]
            cells.append((X1 if c == 0 else X2, name, wrap("rom", items, 18.5, CW)))
        rh = 26 + 24 * max(len(c[2]) for c in cells)
        placed.append((y, cells))
        y += rh + 14
    h = y + 6
    d = Doc(h, "Instruments", "Instruments. " + " ".join(f"{n}: {i}." for n, i in groups))
    sep(d, 36)
    heading(d, 76, "Instruments")
    d.add(f'<path d="M{W/2} 112V{h-24}" stroke="{RULE}"/>')
    for y, cells in placed:
        for x, name, lines in cells:
            d.text("rom", x, y, name, 14, OX, tracking=2.6, cls="sc")
            for i, ln in enumerate(lines):
                d.text("rom", x, y + 26 + 24 * i, ln, 18.5, INK)
    d.save("instruments.svg")


# ================================================================== CORRESPONDENCE
def correspondence():
    h = 372
    d = Doc(h, "Correspondence",
            "Correspondence. I am at present seeking a position, and should be glad to hear from anyone building with "
            "language models. Yours sincerely, Aykan Uğur. aykanugur157@gmail.com, aykanugur.com, linkedin.com/in/aykanugur.",
            bottom=True)
    cx = W / 2
    sep(d, 36)
    heading(d, 76, "Correspondence")
    d.text("ita", cx, 128, "I am at present seeking a position, and should be glad", 20, INK, "middle")
    d.text("ita", cx, 156, "to hear from anyone building with language models.", 20, INK, "middle")
    d.text("ita", cx, 214, "Yours sincerely,", 18, INK2, "middle")
    d.text("ita", cx, 268, "Aykan Uğur", 52, OX, "middle", cls="sw")
    d.text("rom", cx, 318, "aykanugur157@gmail.com   ·   aykanugur.com   ·   linkedin.com/in/aykanugur", 15.5, INK2, "middle")
    d.save("correspondence.svg")


class Tab(Doc):
    """A small clickable paper tab: its own double-rule frame, transparent margin around it."""

    def __init__(self, w, h, title, desc):
        super().__init__(h, title, desc)
        self.w = w

    def render(self):
        w, h = self.w, self.h
        grain = ('<filter id="g" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">'
                 '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" seed="5"/>'
                 '<feColorMatrix values="0 0 0 0 .30  0 0 0 0 .24  0 0 0 0 .14  1.2 0 0 0 -.45"/></filter>')
        css = "text{font-variant-numeric:lining-nums}.sc{font-variant-caps:all-small-caps}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t d">\n'
            f'<title id="t">{esc(self.title)}</title>\n<desc id="d">{esc(self.desc)}</desc>\n<defs>{grain}</defs>\n'
            f"<style>{self.font_faces()}{css}</style>\n"
            f'<rect x="4" y="4" width="{w-8}" height="{h-8}" fill="{PAPER}"/><rect x="4" y="4" width="{w-8}" height="{h-8}" filter="url(#g)" opacity=".2"/>\n'
            f'<rect x="4.5" y="4.5" width="{w-9}" height="{h-9}" fill="none" stroke="{INK}" stroke-width="1.2"/>'
            f'<rect x="8.5" y="8.5" width="{w-17}" height="{h-17}" fill="none" stroke="{INK}" stroke-width=".5"/>\n'
            + "\n".join(self.body) + "\n</svg>\n"
        )


def tabs():
    for fname, label, what in (("tab-website", "Website", "aykanugur.com"), ("tab-linkedin", "LinkedIn", "linkedin.com/in/aykanugur"),
                               ("tab-email", "Email", "aykanugur157@gmail.com"), ("tab-repos", "Repositories", "all public repositories on GitHub")):
        w = int(FACES["rom"].width(label.upper(), 14.5, 3.4) * .82 + 78)
        d = Tab(w, 46, f"{label}", f"Link: {label}, {what}.")
        d.rich("rom", w / 2 - 6, 29.5, [(label, INK), ("  \u2197", OX)], 14.5, cls="sc", tracking=3.4)
        d.save(fname + ".svg")


def generic_fonts():
    """Basic-Latin subsets committed to assets/fonts/, embedded by scripts/stats.py (which has no fontTools)."""
    fdir = OUT / "fonts"
    fdir.mkdir(exist_ok=True)
    chars = "".join(chr(c) for c in range(0x20, 0x7F)) + "·—–’"
    for key, name in (("rom", "garamond"), ("ita", "garamond-italic")):
        raw = base64.b64decode(FACES[key].woff2_b64(chars))
        (fdir / f"{name}.woff2").write_bytes(raw)
        print(f"fonts/{name}.woff2".ljust(28), f"{len(raw)/1024:6.1f} KB")


if __name__ == "__main__":
    generic_fonts()
    title()
    particulars()
    works()
    instruments()
    correspondence()
    tabs()
