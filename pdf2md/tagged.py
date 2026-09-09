# -*- coding: utf-8 -*-
"""Read a tagged PDF's own structure instead of guessing it from geometry.

A page printed to PDF by a browser keeps the HTML structure inside the file:
headings, paragraphs, tables, rows and cells are all named.  Where that is
present there is nothing to infer -- no working out whether a short line is a
new row or the tail of a wrapped one, no hunting for column edges, no trouble
with a table split across a page break.

Not every PDF is tagged, so the geometry reader stays as the fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pymupdf

from .reader import SC_GID, Run

FLAGS = pymupdf.TEXTFLAGS_RAWDICT | pymupdf.TEXT_COLLECT_STRUCTURE

#: Tags that start a block of their own.  Everything else -- NonStruct, Span,
#: Em, Strong -- is passed through, since the font already carries the emphasis.
BLOCK_TAGS = {"H1", "H2", "H3", "H4", "H5", "H6", "P", "Table",
              "L", "LI", "Caption", "Figure", "BlockQuote", "Blockquote"}


@dataclass
class Node:
    tag: str                      # 'P', 'H2', 'Table', or '' for loose text
    index: int = -1               # stable across a page break: lets a split
    runs: list = field(default_factory=list)          # element be rejoined
    rows: list = field(default_factory=list)          # tables: rows of cells

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


def is_tagged(doc) -> bool:
    try:
        return doc.xref_get_key(doc.pdf_catalog(), "StructTreeRoot")[0] != "null"
    except Exception:
        return False


def _tag(block) -> str:
    return block.get("raw") or block.get("std") or ""


def _smallcaps(page) -> set:
    out = set()
    for span in page.get_texttrace():
        if span.get("type") or not span.get("chars"):
            continue
        for ch in span["chars"]:
            if ch[1] >= SC_GID:
                out.add((round(ch[2][0], 1), round(ch[2][1], 1)))
    return out


def _runs(block, smallcaps, out=None) -> list:
    """Style runs for everything under this element, in reading order."""
    out = [] if out is None else out
    if block.get("type") == 0:
        for line in block.get("lines", []):
            for span in line["spans"]:
                bold = "Bold" in span["font"]
                italic = "Italic" in span["font"]
                for ch in span["chars"]:
                    # A synthetic space was invented by the extractor because a
                    # letter-spaced heading looked like separate words.
                    if ch.get("synthetic") and ch["c"].isspace():
                        continue
                    origin = (round(ch["origin"][0], 1), round(ch["origin"][1], 1))
                    sc = origin in smallcaps
                    x0, y0, x1, y1 = ch["bbox"]
                    if (out and (out[-1].bold, out[-1].italic, out[-1].smallcaps)
                            == (bold, italic, sc)):
                        out[-1].text += ch["c"]
                        out[-1].x1 = x1
                    else:
                        out.append(Run(ch["c"], bold, italic, sc, x0, x1, y0, y1))
            if line is not block["lines"][-1] and out and not out[-1].text.endswith(" "):
                out[-1].text += " "        # a wrapped line is still one sentence
        return out
    for kid in block.get("blocks", []):
        _runs(kid, smallcaps, out)
    return out


def _find(block, tag, out) -> list:
    if _tag(block) == tag:
        out.append(block)
        return out
    for kid in block.get("blocks", []):
        _find(kid, tag, out)
    return out


def _table(block, smallcaps) -> list:
    """Rows of cells, exactly as the document declares them."""
    rows = []
    for tr in _find(block, "TR", []):
        cells = []
        for cell in tr.get("blocks", []):
            if _tag(cell) in ("TD", "TH"):
                cells.append(_runs(cell, smallcaps))
        if not cells:                      # cells nested a level deeper
            for tag in ("TD", "TH"):
                for cell in _find(tr, tag, []):
                    cells.append(_runs(cell, smallcaps))
        rows.append(cells)
    return rows


def page_nodes(page) -> list:
    """Top-level blocks of one page, in reading order."""
    smallcaps = _smallcaps(page)
    data = page.get_text("rawdict", flags=FLAGS)
    nodes: list[Node] = []

    def encloses_block(block) -> bool:
        for kid in block.get("blocks", []):
            if _tag(kid) in BLOCK_TAGS or _tag(kid) == "Table" or encloses_block(kid):
                return True
        return False

    def walk(block):
        tag = _tag(block)
        if tag == "Table":
            nodes.append(Node("Table", block.get("index", -1),
                              rows=_table(block, smallcaps)))
            return
        if tag in BLOCK_TAGS:
            runs = _runs(block, smallcaps)
            if any(r.text.strip() for r in runs):
                nodes.append(Node(tag, block.get("index", -1), runs=runs))
            return
        # An untagged wrapper holding only inline content is one block of text:
        # taking its leaves one by one would shred a line into its emphases.
        if block.get("type") == 0 or not encloses_block(block):
            runs = _runs(block, smallcaps)
            if any(r.text.strip() for r in runs):
                nodes.append(Node("", block.get("index", -1), runs=runs))
            return
        for kid in block.get("blocks", []):
            walk(kid)

    for block in data["blocks"]:
        walk(block)
    return nodes


def read(path) -> list:
    """All pages' nodes, with elements split by a page break rejoined."""
    doc = pymupdf.open(path)
    if not is_tagged(doc):
        doc.close()
        return []
    pages = []
    for page in doc:
        nodes = page_nodes(page)
        if pages and nodes and pages[-1]:
            last, first = pages[-1][-1], nodes[0]
            # The same element continued over the break: same kind, same slot.
            if last.tag == first.tag and last.index == first.index and last.tag:
                if last.tag == "Table":
                    last.rows += first.rows
                else:
                    last.runs += first.runs
                nodes = nodes[1:]
        pages.append(nodes)
    doc.close()
    return pages
