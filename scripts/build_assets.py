#!/usr/bin/env python3
"""Builds the static SVG components of the profile README.

Design system ("Orrery"): ink panels, hairlines, one sun-amber accent.
Typography is embedded per file as exact glyph subsets (woff2 data URIs), so it
renders identically everywhere and never depends on a third-party host.

Usage:  python build_assets.py <fonts-src-dir> <out-dir>
Needs:  pip install fonttools brotli
Fonts (OFL): Instrument Serif, Instrument Sans, JetBrains Mono (see assets/fonts/LICENSE.md)
"""
import base64
import math
import random
import sys
from io import BytesIO
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ tokens
INK0, INK1 = "#080b12", "#101725"
LINE, LINE2 = "#1f2837", "#2c384d"
FG, FG2, FG3 = "#eef1f6", "#a3adbe", "#76829a"
SUN, EARTH, OK = "#ffb454", "#6fa3ff", "#3ddc97"
RED = "#e0765a"


# ------------------------------------------------------------------ fonts
class Face:
    def __init__(self, path, axes=None, family="", fallback=""):
        font = TTFont(str(path))
        if axes:
            font = instancer.instantiateVariableFont(font, axes, inplace=False)
        buf = BytesIO()
        font.save(buf)
        self.raw = buf.getvalue()
        font = TTFont(BytesIO(self.raw))
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self.upem = font["head"].unitsPerEm
        self.family, self.fallback = family, fallback

    def width(self, text, size, tracking=0.0):
        w = 0
        for ch in text:
            g = self.cmap.get(ord(ch))
            w += self.hmtx[g][0] if g else self.upem * 0.5
        return w * size / self.upem + tracking * len(text)

    def has(self, ch):
        return ord(ch) in self.cmap

    def woff2_b64(self, chars):
        font = TTFont(BytesIO(self.raw))
        opts = subset.Options()
        opts.layout_features = ["kern", "mark", "mkmk", "ccmp", "locl", "case"]
        opts.name_IDs = [0, 1, 2, 4, 6]
        opts.hinting = False
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)) + " ")
        sub.subset(font)
        out = BytesIO()
        font.flavor = "woff2"
        font.save(out)
        return base64.b64encode(out.getvalue()).decode()


FACES = {
    "serif": Face(SRC / "InstrumentSerif-Regular.ttf", family="AUSerif",
                  fallback="'Instrument Serif',Georgia,'Times New Roman',serif"),
    "serifi": Face(SRC / "InstrumentSerif-Italic.ttf", family="AUSerifI",
                   fallback="'Instrument Serif',Georgia,'Times New Roman',serif"),
    "sans": Face(SRC / "InstrumentSans-VF.ttf", {"wght": 400, "wdth": 100}, "AUSans",
                 "'Instrument Sans','Segoe UI',Helvetica,Arial,sans-serif"),
    "mono": Face(SRC / "JetBrainsMono-VF.ttf", {"wght": 400}, "AUMono",
                 "'JetBrains Mono',ui-monospace,'SF Mono',Consolas,monospace"),
    "monob": Face(SRC / "JetBrainsMono-VF.ttf", {"wght": 600}, "AUMonoB",
                  "'JetBrains Mono',ui-monospace,'SF Mono',Consolas,monospace"),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class Doc:
    def __init__(self, w, h, title, desc):
        self.w, self.h, self.title, self.desc = w, h, title, desc
        self.defs, self.body, self.css = [], [], []
        self.used = {k: set() for k in FACES}

    def add(self, s):
        self.body.append(s)

    def text(self, face, x, y, s, size, fill, anchor="start", tracking=0, extra=""):
        self.used[face].update(s)
        f = FACES[face]
        ls = f' letter-spacing="{tracking}"' if tracking else ""
        an = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{f.family},{f.fallback}" '
            f'font-size="{size}" fill="{fill}"{an}{ls}{extra}>{esc(s)}</text>'
        )

    def code(self, x, y, size, tokens):
        """One monospace line made of (text, fill) tokens, placed on a fixed column grid."""
        f = FACES["mono"]
        cw = f.width("M", size)
        col, spans = 0, []
        for s, fill in tokens:
            self.used["mono"].update(s)
            spans.append(f'<tspan x="{x + col * cw:.2f}" fill="{fill}">{esc(s)}</tspan>')
            col += len(s)
        self.add(f'<text y="{y:.1f}" font-family="{f.family},{f.fallback}" font-size="{size}" xml:space="preserve">{"".join(spans)}</text>')

    def pill(self, x, y, label, h=20, size=10.5, tracking=1.0):
        f = FACES["mono"]
        w = f.width(label, size, tracking) + 18
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h/2}" fill="none" stroke="{LINE2}"/>')
        self.text("mono", x + 9 + 0.5, y + h / 2 + size * 0.36, label, size, FG2, tracking=tracking)
        return w

    def panel(self, w=None, h=None, rx=16, glow=None):
        w, h = w or self.w, h or self.h
        self.add(f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="{rx}" fill="url(#pg)" stroke="{LINE}"/>')
        self.add(f'<path d="M{rx} 1.5H{w-rx}" stroke="#fff" stroke-opacity=".07"/>')

    def render(self):
        faces = []
        for k, chars in self.used.items():
            if chars:
                faces.append(
                    f"@font-face{{font-family:{FACES[k].family};src:url(data:font/woff2;base64,{FACES[k].woff2_b64(chars)}) format('woff2')}}"
                )
        style = "<style>" + "".join(faces) + "".join(self.css) + "</style>"
        grad = (f'<linearGradient id="pg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{INK1}"/>'
                f'<stop offset="1" stop-color="{INK0}"/></linearGradient>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'role="img" aria-labelledby="t d">\n<title id="t">{esc(self.title)}</title>\n<desc id="d">{esc(self.desc)}</desc>\n'
            f"<defs>{grad}{''.join(self.defs)}</defs>\n{style}\n" + "\n".join(self.body) + "\n</svg>\n"
        )

    def save(self, name):
        svg = self.render()
        (OUT / name).write_text(svg, encoding="utf-8")
        print(f"{name:22s} {len(svg)/1024:6.1f} KB")


def wrap(face, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if face.width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ================================================================== BANNER
def banner():
    W, H = 1000, 340
    d = Doc(W, H, "Aykan Uğur, I build language models",
            "Animated banner: a small orrery of the solar system next to the name Aykan Uğur, "
            "with the line 'I build language models'. Based in İzmir, Turkey. Open to work.")
    d.defs.append(
        f'<radialGradient id="sunglow"><stop offset="0" stop-color="{SUN}" stop-opacity=".55"/>'
        f'<stop offset=".45" stop-color="{SUN}" stop-opacity=".12"/><stop offset="1" stop-color="{SUN}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="wash" cx=".78" cy=".5" r=".6"><stop offset="0" stop-color="#1a2540" stop-opacity=".9"/>'
        f'<stop offset="1" stop-color="#1a2540" stop-opacity="0"/></radialGradient>'
        f'<clipPath id="clip"><rect width="{W}" height="{H}" rx="20"/></clipPath>'
    )
    d.css.append(".blink{animation:b 1.1s steps(1) infinite}@keyframes b{50%{opacity:0}}")
    d.add('<g clip-path="url(#clip)">')
    d.add(f'<rect width="{W}" height="{H}" fill="url(#pg)"/><rect width="{W}" height="{H}" fill="url(#wash)"/>')

    # fine graticule
    grid = "".join(f'<path d="M{x} 0V{H}"/>' for x in range(0, W + 1, 50)) + "".join(f'<path d="M0 {y}H{W}"/>' for y in range(0, H + 1, 50))
    d.add(f'<g stroke="#fff" stroke-opacity=".028">{grid}</g>')

    rnd = random.Random(7)
    stars = "".join(
        f'<circle cx="{rnd.uniform(0, W):.0f}" cy="{rnd.uniform(0, H):.0f}" r="{rnd.choice([.6, .8, 1.0, 1.2])}"/>'
        for _ in range(46)
    )
    d.add(f'<g fill="#fff" fill-opacity=".5">{stars}</g>')

    # --- orrery
    cx, cy = 772, 170
    d.add(f'<g transform="translate({cx} {cy})">')
    R = 152
    circ = 2 * math.pi * R
    d.add(f'<circle r="{R}" fill="none" stroke="{LINE2}" stroke-width="1"/>')
    d.add(f'<circle r="{R-5}" fill="none" stroke="{LINE2}" stroke-width="8" stroke-dasharray="1 {circ/72-1:.3f}" opacity=".8"/>')
    d.add(f'<circle r="{R-8}" fill="none" stroke="{FG3}" stroke-width="14" stroke-dasharray="1.4 {circ/12-1.4:.3f}" opacity=".65"/>')
    d.add(f'<path d="M-{R-24} 0H{R-24}M0 -{R-24}V{R-24}" stroke="{LINE2}" stroke-opacity=".7"/>')
    orbits = [(38, 3.2, "#9aa4b5", 6.5, 35), (64, 4.8, "#e6c9a0", 11, 210), (94, 6.2, EARTH, 18, 100), (124, 4.2, RED, 30, 300)]
    for r, *_ in orbits:
        d.add(f'<circle r="{r}" fill="none" stroke="{LINE2}"/>')
    # sun
    d.add(f'<circle r="64" fill="url(#sunglow)"/><circle r="22" fill="none" stroke="{SUN}" stroke-opacity=".35"/>')
    d.add(f'<circle r="13" fill="{SUN}"><animate attributeName="r" values="13;14.2;13" dur="5s" repeatCount="indefinite"/></circle>')
    for r, pr, col, dur, start in orbits:
        extra = ""
        if col == EARTH:
            d.used["mono"].update("İZMİR")
            extra = (
                f'<circle r="{pr+5}" fill="none" stroke="{EARTH}" stroke-opacity=".45"/>'
                f'<g><animateTransform attributeName="transform" type="rotate" from="{-start}" to="{-start-360}" dur="{dur}s" repeatCount="indefinite"/>'
                f'<path d="M7 -7L17 -17H31" fill="none" stroke="{FG3}" stroke-width=".8"/>'
                f'<text x="35" y="-14" font-family="{FACES["mono"].family},{FACES["mono"].fallback}" font-size="10" letter-spacing="1.4" fill="{FG2}">İZMİR</text></g>'
            )
        d.add(
            f'<g transform="rotate({start})"><g><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="{dur}s" repeatCount="indefinite"/>'
            f'<g transform="translate({r} 0)"><circle r="{pr}" fill="{col}"/>{extra}</g></g></g>'
        )
    d.add("</g>")

    # --- copy
    x0 = 56
    d.add(f'<circle cx="{x0+4}" cy="58" r="4" fill="{OK}"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    d.add(f'<circle cx="{x0+4}" cy="58" r="4" fill="none" stroke="{OK}"><animate attributeName="r" values="4;11" dur="2.4s" repeatCount="indefinite"/><animate attributeName="opacity" values=".7;0" dur="2.4s" repeatCount="indefinite"/></circle>')
    d.text("monob", x0 + 18, 62, "OPEN TO WORK", 11, FG, tracking=2)
    d.text("mono", x0 + 142, 62, "/  İZMİR  38.42°N 27.14°E", 11, FG3, tracking=1.4)
    d.text("serif", x0 - 3, 174, "Aykan Uğur", 108, FG, tracking=-1.5)
    d.used["serifi"].update("I build language models.")
    f = FACES["serifi"]
    d.add(
        f'<text x="{x0}" y="226" font-family="{f.family},{f.fallback}" font-size="38" fill="{FG2}">'
        f'I build <tspan fill="{SUN}">language models.</tspan></text>'
    )
    d.text("mono", x0, 266, "NLP  /  MACHINE LEARNING  /  TURKISH AI", 11.5, FG3, tracking=2)
    d.add(f'<path d="M{x0} 292H520" stroke="{LINE}"/>')
    d.code(x0, 318, 13, [("~ ", FG3), ("$ ", SUN), ("train --model AykanLLM-1.3B", FG2)])
    cw = FACES["mono"].width("M", 13)
    ncol = len("~ $ train --model AykanLLM-1.3B")
    d.add(f'<rect class="blink" x="{x0 + ncol*cw + 3:.1f}" y="307" width="7.5" height="15" fill="{SUN}"/>')

    # corner registration marks
    for mx, my in [(22, 22), (W - 22, 22), (22, H - 22), (W - 22, H - 22)]:
        d.add(f'<path d="M{mx-5} {my}H{mx+5}M{mx} {my-5}V{my+5}" stroke="{LINE2}"/>')
    d.add("</g>")
    d.add(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="20" fill="none" stroke="{LINE2}"/>')
    d.save("banner.svg")


# ================================================================== ABOUT
def about():
    W = 880
    rows = [
        [("class ", SUN), ("AykanUgur", FG), (":", FG3)],
        [("    name        ", FG2), ("= ", FG3), ('"Aykan Uğur"', "#9cc2ff")],
        [("    location    ", FG2), ("= ", FG3), ('"İzmir, Turkey  (a.k.a. Solar System)"', "#9cc2ff")],
        [("    role        ", FG2), ("= ", FG3), ('"Undergraduate Assistant @ İzmir University of Economics"', "#9cc2ff")],
        [("    focus       ", FG2), ("= ", FG3), ("[", FG3), ('"LLMs"', "#9cc2ff"), (", ", FG3), ('"NLP"', "#9cc2ff"), (", ", FG3), ('"Machine Learning"', "#9cc2ff"), (", ", FG3), ('"Teaching"', "#9cc2ff"), ("]", FG3)],
        None,
        [("    building    ", FG2), ("= ", FG3), ('"AykanLLM-1.3B"', "#9cc2ff")],
        [("    studying    ", FG2), ("= ", FG3), ('"a GPT from scratch, via the NeetCode ML course"', "#9cc2ff")],
        [("    exploring   ", FG2), ("= ", FG3), ('"Turkish NLP: models, datasets, papers"', "#9cc2ff")],
        None,
        [("    looking_for ", FG2), ("= ", FG3), ("[", FG3), ('"a job"', "#9cc2ff"), (", ", FG3), ('"collaborators on LLMs & NLP"', "#9cc2ff"), ("]", FG3)],
        [("    fun_fact    ", FG2), ("= ", FG3), ('"Worked at a summer camp. Twice. XD"', "#9cc2ff")],
        [("    reach_me    ", FG2), ("= ", FG3), ('"aykanugur157@gmail.com"', "#9cc2ff")],
    ]
    LH, top = 24, 74
    H = top + LH * len(rows) + 22
    d = Doc(W, H, "About Aykan Uğur",
            "A Python class listing: name Aykan Uğur, from İzmir, Turkey; Undergraduate Assistant at İzmir University of Economics; "
            "focus on LLMs, NLP, machine learning and teaching; building AykanLLM-1.3B; studying a GPT from scratch via the NeetCode ML course; "
            "exploring Turkish NLP; looking for a job and collaborators; reachable at aykanugur157@gmail.com.")
    d.css.append(".blink{animation:b 1.1s steps(1) infinite}@keyframes b{50%{opacity:0}}")
    d.panel()
    d.add(f'<path d="M0 46.5H{W}" stroke="{LINE}"/>')
    d.text("mono", 28, 28, "aykan.py", 12, FG2, tracking=.4)
    d.text("mono", W - 28, 28, "PYTHON", 10.5, FG3, anchor="end", tracking=1.8)
    d.add(f'<circle cx="{28+FACES["mono"].width("aykan.py",12,.4)+14:.1f}" cy="24" r="2.5" fill="{SUN}"/>')
    n = 0
    for i, row in enumerate(rows):
        y = top + i * LH
        if row is None:
            continue
        n += 1
        d.text("mono", 46, y, str(i + 1), 12, FG3, anchor="end", extra=' fill-opacity=".55"')
        d.code(66, y, 14, row)
    # caret after last line
    last = rows[-1]
    cols = sum(len(s) for s, _ in last)
    cw = FACES["mono"].width("M", 14)
    d.add(f'<rect class="blink" x="{66 + cols*cw + 4:.1f}" y="{top + (len(rows)-1)*LH - 13}" width="8" height="17" fill="{SUN}"/>')
    d.add(f'<path d="M58 54V{H-16}" stroke="{LINE}"/>')
    d.save("about.svg")


# ================================================================== WORK ROWS
WORK = [
    dict(file="work-gpt", cat="LANGUAGE MODEL", hue=SUN, title="GPT from scratch", repo="neetcode-gpt",
         desc="BPE tokenizer, multi-head and grouped-query attention, KV-cache and a full transformer, assembled from my NeetCode ML course submissions.",
         tags=["PYTHON", "PYTORCH"]),
    dict(file="work-bhts", cat="SYSTEMS / REAL-TIME", hue=EARTH, title="BHTS Air Tracking", repo="bhts  +  bhts-api",
         desc="Balıkesir Hava Takip Sistemi: an air-tracking system with an ASP.NET Core backend (MessagePack over SignalR) and a React frontend.",
         tags=["C#", "ASP.NET CORE", "REACT", "SIGNALR"]),
    dict(file="work-innovatepam", cat="PLATFORM", hue=EARTH, title="InnovatEPAM Portal", repo="innovatepam-portal",
         desc="An internal innovation platform. Employees submit ideas, admins review them through a configurable multi-stage pipeline, and results are tracked with analytics.",
         tags=["NEXT.JS", "TYPESCRIPT", "PRISMA", "POSTGRESQL"]),
    dict(file="work-taylanator", cat="MACHINE LEARNING", hue=SUN, title="Taylanator", repo="Taylanator-Question-ML-GAME",
         desc="An Akinator-style guessing game. It asks questions and uses machine learning to work out the animal, celebrity, game, movie or object you are thinking of.",
         tags=["PYTHON", "ML"]),
    dict(file="work-quake", cat="DATA APP", hue=EARTH, title="Earthquakes of Turkey", repo="Earthquake-Database-For-Turkey",
         desc="A friendlier way to browse Turkey's earthquakes: sort by any column, filter by your city. A hobby project.",
         tags=["PYTHON"]),
    dict(file="work-german", cat="LEARNING APP", hue=EARTH, title="German Vocabulary Quiz", repo="German-Vocabulary-Quiz-App-TR",
         desc="A vocabulary quiz app for learning German, built for Turkish speakers.",
         tags=["PYTHON"]),
]


def work_rows():
    W, PH, GAP = 880, 124, 8
    for w in WORK:
        d = Doc(W, PH + GAP, f"{w['title']} ({w['repo']})",
                f"{w['cat'].title()} project: {w['title']}. {w['desc']} Built with {', '.join(t.title() for t in w['tags'])}.")
        d.panel(W, PH, 14)
        d.add(f'<circle cx="34" cy="31" r="3.5" fill="{w["hue"]}"/>')
        d.text("mono", 46, 35, w["cat"], 10.5, FG3, tracking=1.8)
        d.text("serif", 32, 76, w["title"], 34, FG, tracking=-.2)
        x = 32
        for t in w["tags"]:
            x += d.pill(x, 90, t) + 6
        d.add(f'<path d="M392 20V{PH-20}" stroke="{LINE}"/>')
        d.text("mono", W - 32, 35, w["repo"] + "  ↗", 11, FG2, anchor="end", tracking=.4)
        lines = wrap(FACES["sans"], w["desc"], 15, W - 32 - 416)
        assert len(lines) <= 3, (w["file"], lines)
        for i, ln in enumerate(lines):
            d.text("sans", 416, 64 + i * 22, ln, 15, FG2)
        d.save(w["file"] + ".svg")


# ================================================================== STACK
def stack():
    W = 880
    groups = [
        ("AI / ML", ["Python", "PyTorch", "TensorFlow", "scikit-learn", "MATLAB"]),
        ("LANGUAGES", ["C#", "Java", "C", "C++", "TypeScript", "JavaScript"]),
        ("BACKEND & DATA", [".NET", "ASP.NET Core", "SignalR", "PostgreSQL", "MySQL", "Firebase", "Prisma"]),
        ("FRONTEND & MOBILE", ["React", "Next.js", "Tailwind CSS", "Flutter", "Android"]),
        ("GAMES & CREATIVE", ["Unity", "Unreal Engine", "Blender", "Figma", "Arduino"]),
        ("TOOLING", ["Git", "GitHub Actions", "Docker", "Linux", "VS Code", "PyCharm", "Rider"]),
    ]
    RH, top = 54, 14
    H = top * 2 + RH * len(groups)
    d = Doc(W, H, "Tech stack",
            "Tech stack by area. " + " ".join(f"{g.title()}: {', '.join(items)}." for g, items in groups))
    d.panel()
    for i, (g, items) in enumerate(groups):
        y = top + i * RH
        if i:
            d.add(f'<path d="M32 {y+.5}H{W-32}" stroke="{LINE}"/>')
        base = y + RH / 2 + 6
        d.text("mono", 32, base - 1, g, 10.5, FG3, tracking=1.8)
        f = FACES["sans"]
        d.used["sans"].update("".join(items) + "\u00b7")
        spans = []
        for j, it in enumerate(items):
            if j:
                spans.append(f'<tspan dx="10" fill="{SUN}" fill-opacity=".85">\u00b7</tspan>')
                spans.append(f'<tspan dx="10">{esc(it)}</tspan>')
            else:
                spans.append(f"<tspan>{esc(it)}</tspan>")
        d.add(f'<text x="220" y="{base:.1f}" font-family="{f.family},{f.fallback}" font-size="16.5" fill="{FG}">{"".join(spans)}</text>')
        approx = 220 + sum(f.width(it, 16.5) for it in items) + 24 * (len(items) - 1)
        assert approx < W - 24, (g, approx)
    d.save("stack.svg")


# ================================================================== CONTACT
def contact():
    W, H = 880, 168
    d = Doc(W, H, "Let's build something",
            "Open to work. Reach Aykan Uğur at aykanugur157@gmail.com, aykanugur.com or linkedin.com/in/aykanugur.")
    d.defs.append(f'<radialGradient id="cg" cx=".12" cy=".2" r=".7"><stop offset="0" stop-color="{SUN}" stop-opacity=".12"/><stop offset="1" stop-color="{SUN}" stop-opacity="0"/></radialGradient>')
    d.panel(rx=16)
    d.add(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="15" fill="url(#cg)"/>')
    d.add(f'<circle cx="36" cy="38" r="4" fill="{OK}"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    d.text("monob", 50, 42, "OPEN TO WORK", 11, FG, tracking=2)
    d.text("mono", 192, 42, "/  İZMİR, TURKEY", 11, FG3, tracking=1.4)
    d.used["serifi"].update("Let's build something")
    f = FACES["serifi"]
    d.add(f'<text x="32" y="112" font-family="{f.family},{f.fallback}" font-size="58" fill="{FG}" letter-spacing="-.5">Let\'s build <tspan fill="{SUN}">something.</tspan></text>')
    d.text("mono", W - 32, 78, "aykanugur157@gmail.com", 13, FG, anchor="end")
    d.text("mono", W - 32, 102, "aykanugur.com", 13, FG2, anchor="end")
    d.text("mono", W - 32, 126, "linkedin.com/in/aykanugur", 13, FG2, anchor="end")
    d.add(f'<path d="M{W-330} 56V{H-28}" stroke="{LINE}"/>')
    d.save("contact.svg")


def generic_fonts():
    """Basic-Latin subsets committed to assets/fonts/, embedded by scripts/stats.py (which has no fontTools)."""
    fdir = OUT / "fonts"
    fdir.mkdir(exist_ok=True)
    chars = "".join(chr(c) for c in range(0x20, 0x7F)) + "\u00b7\u2014\u2013\u00b0"
    for key in ("serif", "sans", "mono"):
        raw = base64.b64decode(FACES[key].woff2_b64(chars))
        (fdir / f"{key}.woff2").write_bytes(raw)
        print(f"fonts/{key}.woff2".ljust(22), f"{len(raw)/1024:6.1f} KB")


if __name__ == "__main__":
    generic_fonts()
    banner()
    about()
    work_rows()
    stack()
    contact()
