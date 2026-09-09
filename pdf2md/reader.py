# -*- coding: utf-8 -*-
"""Pull text, styling, drawn rules and links out of a PDF page.

Everything downstream works on the structures produced here, so this module
holds the only PyMuPDF-specific knowledge in the package.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

import pymupdf

YTOL = 3.0          # lines within this many points share a horizontal band
GAP = 5.0           # a blank wider than this separates table cells, not words
SC_GID = 1000       # small-cap glyph variants live high in the font subset


@dataclass
class Run:
    """A stretch of characters sharing one style."""
    text: str
    bold: bool
    italic: bool
    smallcaps: bool
    x0: float
    x1: float
    y0: float
    y1: float

    @property
    def blank(self) -> bool:
        return not self.text.strip()


@dataclass
class Line:
    runs: list[Run]
    x0: float
    x1: float
    yc: float
    size: float
    block: int

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


@dataclass
class Page:
    number: int
    lines: list[Line]
    rules: dict[float, list[float]]
    links: list[tuple]


@dataclass
class Document:
    path: str
    pages: list[Page]
    body_size: float = 9.0
    margin: float = 28.5
    meta: dict = field(default_factory=dict)

    @property
    def lines(self):
        for p in self.pages:
            yield from p.lines


def _smallcap_origins(page) -> set:
    """VISK's small caps are separate glyphs in the same font at the same size;
    only the glyph id gives them away, so collect where they were drawn."""
    out = set()
    for span in page.get_texttrace():
        if span.get("type") or not span.get("chars"):
            continue
        for ch in span["chars"]:
            if ch[1] >= SC_GID:
                out.add((round(ch[2][0], 1), round(ch[2][1], 1)))
    return out


def _lines(page) -> list[Line]:
    smallcaps = _smallcap_origins(page)
    traces = _trace_strings(page)
    out = []
    for block in page.get_text("rawdict")["blocks"]:
        if block["type"]:
            continue
        for ln in block["lines"]:
            runs: list[Run] = []
            cur: Run | None = None
            for span in ln["spans"]:
                bold, italic = "Bold" in span["font"], "Italic" in span["font"]
                for ch in span["chars"]:
                    origin = (round(ch["origin"][0], 1), round(ch["origin"][1], 1))
                    sc = origin in smallcaps
                    x0, y0, x1, y1 = ch["bbox"]
                    # A wide blank is a cell boundary, not a word space; without
                    # this the columns of a same-styled table row merge into one.
                    wide = ch["c"].isspace() and x1 - x0 > 4.5
                    if wide:
                        cur = None
                    if (cur is not None and (cur.bold, cur.italic, cur.smallcaps)
                            == (bold, italic, sc) and x0 - cur.x1 <= GAP):
                        cur.text += ch["c"]
                        cur.x1 = x1
                    else:
                        cur = Run(ch["c"], bold, italic, sc, x0, x1, y0, y1)
                        runs.append(cur)
                        if wide:
                            cur = None
            if not "".join(r.text for r in runs).strip():
                continue
            runs = _unspace(runs, traces)
            x0, y0, x1, y1 = ln["bbox"]
            out.append(Line(runs, x0, x1, (y0 + y1) / 2,
                            round(max(s["size"] for s in ln["spans"]), 1),
                            block["number"]))
    out.sort(key=lambda l: (round(l.yc, 1), l.x0))
    return out


def _trace_strings(page) -> list:
    """The strings as the PDF actually stores them, with their boxes."""
    out = []
    for span in page.get_texttrace():
        if span.get("type") or not span.get("chars"):
            continue
        text = "".join(chr(c[0]) for c in span["chars"])
        x0, y0, x1, y1 = span["bbox"]
        out.append((y0, y1, x0, x1, text))
    return out


def _unspace(runs: list[Run], traces: list) -> list[Run]:
    """Undo letter-spacing.

    A heading drawn with wide letter-spacing carries no space characters of its
    own; the extractor inserts one between every letter because the gaps look
    like word breaks.  Rather than guess from the gaps -- which would also
    rewrite a table row like `p : v | t : d` -- compare against the string the
    PDF actually stores.  Only a difference of pure whitespace is repaired.
    """
    text = "".join(r.text for r in runs)
    pieces = text.split()
    # Letter-spacing shows up as a line of mostly single characters.  A table
    # row is also one style with wide gaps, so this test keeps it out.
    if len(pieces) < 4 or sum(1 for p in pieces if len(p) == 1) < len(pieces) * 0.8:
        return runs
    styles = {(r.bold, r.italic, r.smallcaps) for r in runs if r.text.strip()}
    if len(styles) != 1:                       # mixed emphasis: leave it alone
        return runs

    yc = (runs[0].y0 + runs[0].y1) / 2
    x0 = min(r.x0 for r in runs)
    x1 = max(r.x1 for r in runs)
    parts = [t for (ty0, ty1, tx0, tx1, t) in traces
             if ty0 - 1 <= yc <= ty1 + 1 and tx0 >= x0 - 1 and tx1 <= x1 + 1]
    if not parts:
        return runs
    true_text = "".join(parts)
    squeeze = lambda s: "".join(s.split())
    if squeeze(true_text) != squeeze(text) or true_text == text:
        return runs

    first = next(r for r in runs if r.text.strip())
    return [Run(true_text, first.bold, first.italic, first.smallcaps,
                x0, x1, first.y0, first.y1)]


def _rules(page) -> dict[float, list[float]]:
    """Thin horizontal fills.  Browser-printed HTML tables draw their cell
    borders this way, which hands us exact column and group boundaries."""
    found = collections.defaultdict(set)
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if r.height <= 2.0 and r.width >= 20:
            found[round(r.y0, 1)] |= {round(r.x0, 1), round(r.x1, 1)}
    return {y: sorted(xs) for y, xs in found.items()}


def _links(page) -> list[tuple]:
    return [(pymupdf.Rect(l["from"]), l["uri"])
            for l in page.get_links() if l.get("uri")]


def read(path: str) -> Document:
    doc = pymupdf.open(path)
    pages = [Page(i, _lines(p), _rules(p), _links(p)) for i, p in enumerate(doc)]
    # Measure the body on long lines only.  Short lines are table cells, and in
    # a table-heavy page they outnumber the prose and skew both statistics.
    sizes = collections.Counter()
    starts = collections.Counter()
    for p in pages:
        for ln in p.lines:
            if len(ln.text.strip()) >= 40:
                sizes[ln.size] += len(ln.text)
            starts[round(ln.x0, 1)] += 1
    if not sizes:
        for p in pages:
            for ln in p.lines:
                sizes[ln.size] += len(ln.text)
    body = sizes.most_common(1)[0][0] if sizes else 9.0
    # The margin is the leftmost position text repeatedly starts at.
    repeated = [x for x, n in starts.items() if n >= 3]
    margin = min(repeated) if repeated else (min(starts) if starts else 28.5)
    out = Document(path, pages, body, margin)
    out.meta["page_count"] = len(pages)
    out.meta["has_text"] = any(p.lines for p in pages)
    doc.close()
    return out
