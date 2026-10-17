"""Shared drawing kit for the profile README SVGs.

Design: monochrome (near-black, off-white, greys) with one signal-orange accent.
All text is converted to outlines (Geist / Geist Mono) so it renders identically everywhere.
"""
import os, re, math
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.environ.get("SVG_OUT", os.path.join(HERE, "..", "..", "assets"))

BG, PANEL, LINE, HAIR = "#0B0F14", "#141A21", "#28323D", "#1C252E"
TEXT, SUB, MUTED, ACC = "#F4F6F8", "#A3AFBB", "#637381", "#5BE49B"

_fonts = {}
def font(fam, w):
    key = (fam, w)
    if key not in _fonts:
        path = os.path.join(FONTS, "Geist.ttf" if fam == "sans" else "GeistMono.ttf")
        _fonts[key] = instantiateVariableFont(TTFont(path), {"wght": w})
    return _fonts[key]

def measure(text, size, fam="sans", w=400, tr=0):
    f = font(fam, w); gs = f.getGlyphSet(); cmap = f.getBestCmap(); s = size / f["head"].unitsPerEm
    total = 0
    for ch in text:
        g = cmap.get(ord(ch))
        total += (gs[g].width * s if g else size * .3) + tr
    return total - tr

def wrap(text, size, maxw, fam="sans", w=400):
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if cur and measure(cand, size, fam, w) > maxw:
            lines.append(cur); cur = word
        else:
            cur = cand
    return lines + ([cur] if cur else [])

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def attrs(kw):
    return " ".join(f'{k.rstrip("_").replace("_", "-")}="{v}"' for k, v in kw.items())


class Doc:
    """One SVG file. Glyphs are defined once in <defs> and placed with <use>."""

    def __init__(self, w, h, label):
        self.w, self.h, self.label = w, h, label
        self.glyphs, self.defs, self.css, self.body = {}, [], [], []

    def gid(self, fam, w, gname):
        key = (fam, w, gname)
        if key not in self.glyphs:
            gs = font(fam, w).getGlyphSet()
            pen = SVGPathPen(gs)
            gs[gname].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
            self.glyphs[key] = (f"{fam[0]}{w}_{len(self.glyphs)}", pen.getCommands())
        return self.glyphs[key][0]

    def text(self, text, size, x, y, fam="sans", w=400, tr=0, anchor="start", **kw):
        f = font(fam, w); gs = f.getGlyphSet(); cmap = f.getBestCmap(); s = size / f["head"].unitsPerEm
        width = measure(text, size, fam, w, tr)
        x = x - width / 2 if anchor == "middle" else x - width if anchor == "end" else x
        uses, cx = [], x
        for ch in text:
            g = cmap.get(ord(ch))
            if g is None:
                print(f"  missing glyph {ch!r} in {fam}"); cx += size * .3 + tr; continue
            if not ch.isspace():
                uses.append(f'<use href="#{self.gid(fam, w, g)}" transform="translate({cx:.2f} {y:.2f}) scale({s:.5f})"/>')
            cx += gs[g].width * s + tr
        return f'<g {attrs(kw)}>{"".join(uses)}</g>'

    def outline(self, text, size, x, y, w=600, tr=0):
        """Per-glyph absolute paths (used for the stroke-draw animation)."""
        f = font("sans", w); gs = f.getGlyphSet(); cmap = f.getBestCmap(); s = size / f["head"].unitsPerEm
        out, cx = [], x
        for ch in text:
            g = cmap[ord(ch)]
            if not ch.isspace():
                pen = SVGPathPen(gs); gs[g].draw(TransformPen(pen, (s, 0, 0, -s, cx, y))); out.append(pen.getCommands())
            cx += gs[g].width * s + tr
        return out, cx - tr - x

    def add(self, *parts):
        self.body.extend(parts)

    def save(self, name):
        glyph_defs = "".join(f'<path id="{i}" d="{d}"/>' for i, d in self.glyphs.values())
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{self.w}" height="{self.h}" '
               f'viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{esc(self.label)}">\n'
               f'<style>{"".join(self.css)}</style>\n<defs>{glyph_defs}{"".join(self.defs)}</defs>\n{"".join(self.body)}\n</svg>\n')
        path = name if os.path.isabs(name) else os.path.join(OUT, name)
        open(path, "w").write(svg)
        print(f"  {name:24s} {len(svg) / 1024:6.1f} KB")
