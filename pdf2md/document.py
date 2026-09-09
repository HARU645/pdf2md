# -*- coding: utf-8 -*-
"""Assemble a whole document into Markdown.

Blocks are classified by the profile, paragraphs are rejoined across page
breaks, and the front matter carries the identity the body no longer has to.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .inline import render, repair_hyphens, tidy
from .tables import bands_of, build, find_regions


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

        i = 0
        while i < len(bands):
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
                i = max(region["bands"]) + 1
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
        elif block.kind == "table":
            out.append(block.text + "\n")
    if a.footer:
        out.append("---\n\n" + " · ".join(a.footer) + "\n")
    return repair_hyphens("\n".join(out))
