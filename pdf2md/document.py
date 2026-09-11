# -*- coding: utf-8 -*-
"""Assemble a whole document into Markdown.

Blocks are classified by the profile, paragraphs are rejoined across page
breaks, and the front matter carries the identity the body no longer has to.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .inline import render, repair_hyphens, tidy
from .tables import (aligns_with, bands_of, build, continuation,
                     find_regions, rows_from)


@dataclass
class Block:
    kind: str
    text: str
    warnings: list = field(default_factory=list)


@dataclass
class Assembled:
    title: str
    section: object
    breadcrumb: list
    blocks: list
    footer: list
    warnings: list = field(default_factory=list)
    #: Pictures the document carries with it, as {file name: bytes}.  A page
    #: saved as a single file holds them inside itself; they are written out
    #: beside the Markdown so that the links in it lead somewhere.
    assets: dict = field(default_factory=dict)


def assemble(doc, profile, known=frozenset()) -> Assembled:
    resolve = lambda uri: profile.resolve_link(uri, known)
    title_parts, breadcrumb, footer, blocks = [], [], [], []
    paragraph, paragraph_blocks = None, set()
    state = {"body_seen": False}

    def close():
        nonlocal paragraph, paragraph_blocks
        if paragraph:
            blocks.append(Block(_note_kind(paragraph, profile), tidy(paragraph)))
        paragraph, paragraph_blocks = None, set()

    carry = None            # a table left hanging by a page break
    for page in doc.pages:
        bands = bands_of(page.lines)
        # A caption announces the next table, so it must not sit inside one.
        breaks = set()
        for n, band in enumerate(bands):
            text = " ".join(l.text for l in band).replace("\xa0", " ").strip()
            if not text:
                continue
            kind = profile.classify(text, max(l.size for l in band),
                                    min(l.x0 for l in band), doc, page.number,
                                    dict(state))
            if kind == "caption":
                breaks.add(n)
        regions = find_regions(bands, page.rules, doc.margin, breaks)
        owner = {}
        for n, region in enumerate(regions):
            for i in region["bands"]:
                owner[i] = n

        skip = set()
        if carry:
            top = page.height * 0.09
            extra = []
            # A table opening the page and lining up with the one the last page
            # ended on is the same table, however far down it runs.
            for region in regions:
                first = region["bands"][0]
                if first != 0 or bands[first][0].yc > top:
                    continue
                if aligns_with(bands[first], carry["cols"]):
                    extra = list(region["bands"])
                break
            if not extra:               # or just a row or two left stranded
                extra = continuation(bands, carry["cols"], doc.margin,
                                     page.height, set(owner))
            if extra:
                width = len(carry["table"].header)
                rows = carry["table"].rows
                for row in rows_from(bands, extra, carry["cols"],
                                     page.links, resolve):
                    row = ([""] * (width - len(row))) + row if len(row) < width                         else row[:width]
                    # Same rule as within a page: a row that leaves the leading
                    # column empty is the tail of the one above, not a new row.
                    if rows and not row[0].strip():
                        for c, cell in enumerate(row):
                            if cell:
                                rows[-1][c] = (rows[-1][c] + " " + cell).strip()
                    else:
                        rows.append(row)
                carry["block"].text = carry["table"].to_markdown()
                skip = set(extra)
        carry = None

        i = 0
        while i < len(bands):
            if i in skip:
                i += 1
                continue
            if i in owner:
                close()
                region = regions[owner[i]]
                table = build(bands, region, page.links, resolve)
                md = table.to_markdown()
                if md:
                    blocks.append(Block("table", md, list(table.warnings)))
                for stray in table.orphans:
                    # A spanning line that labelled no rows is a note about the
                    # table; it belongs beside it, not nowhere.
                    blocks.append(Block("prose", tidy(stray)))
                last = max(region["bands"])
                # A table running to the foot of the page probably carries on.
                if md and bands[last][0].yc > page.height * 0.88:
                    carry = {"table": table, "block": blocks[-1 - len(table.orphans)],
                             "cols": region["cols"]}
                i = last + 1
                continue

            band = bands[i]
            i += 1
            text = " ".join(l.text for l in band).replace("\xa0", " ").strip()
            if not text:
                continue
            size = max(l.size for l in band)
            x0 = min(l.x0 for l in band)
            kind = profile.classify(text, size, x0, doc, page.number, state)
            md = tidy(" ".join(render(l.runs, page.links, resolve) for l in band))
            ids = {l.block for l in band}

            if kind == "title":
                title_parts.append(text)
                close()
            elif kind == "breadcrumb":
                breadcrumb.append(text)
            elif kind == "drop":
                continue
            elif kind == "footer":
                close()
                footer.append(md)
            elif kind == "caption":
                close()
                blocks.append(Block("caption", md.replace("**", "")))
                state["body_seen"] = True
            elif kind == "example":
                state["body_seen"] = True
                if blocks and blocks[-1].kind == "example" and paragraph is None:
                    blocks[-1].text += "\n" + md
                else:
                    close()
                    blocks.append(Block("example", md))
            else:
                state["body_seen"] = True
                if paragraph is not None and (ids & paragraph_blocks):
                    paragraph += " " + md
                    paragraph_blocks |= ids
                else:
                    close()
                    paragraph, paragraph_blocks = md, set(ids)
    close()

    title = " ".join(title_parts).strip()
    section = None
    parsed = profile.section_id(title)
    if parsed:
        section, title = parsed
    crumbs = [c.strip() for c in " ".join(breadcrumb).split(">") if c.strip()]
    return Assembled(title, section, crumbs, blocks, footer)


def _note_kind(text, profile) -> str:
    plain = text.replace("**", "").replace("_", "").lstrip()
    return "note" if any(plain.startswith(p) for p in profile.note_prefixes) else "prose"


def to_markdown(a: Assembled, profile, path) -> str:
    front = profile.front_matter(a.title, a.section, a.breadcrumb, path)
    out = ["---"]
    for key, value in front.items():
        if value is None:
            continue
        if isinstance(value, list):
            out.append(f"{key}:")
            out += ['  - "%s"' % v.replace('"', "'") for v in value]
        elif isinstance(value, str):
            out.append('%s: "%s"' % (key, value.replace('"', "'")))
        else:
            out.append(f"{key}: {value}")
    out.append("---")
    out.append("")
    heading = f"# § {a.section} {a.title}" if a.section else f"# {a.title}"
    out.append(heading)
    out.append("")

    for block in a.blocks:
        if block.kind == "prose":
            out.append(block.text + "\n")
        elif block.kind == "note":
            out.append("> [!NOTE]\n> " + block.text.replace("\n", "\n> ") + "\n")
        elif block.kind == "caption":
            out.append("### " + block.text + "\n")
        elif block.kind == "example":
            out.append("\n".join("> " + l for l in block.text.split("\n")) + "\n")
        elif block.kind == "list":
            out.append(block.text + "\n")
        elif block.kind == "table":
            out.append(block.text + "\n")
    if a.footer:
        out.append("---\n\n" + " · ".join(a.footer) + "\n")
    return repair_hyphens("\n".join(out))
