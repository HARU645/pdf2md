# -*- coding: utf-8 -*-
"""Convert a saved web page instead of a printout of one.

Printing to PDF throws the document's structure away and leaves only ink on a
page, which then has to be read back from coordinates.  The saved HTML still
says what everything is, so nothing here is inferred: a table is a table, a
note is a note, and a term is marked as a term.
"""
from __future__ import annotations

import os
import re
from html.parser import HTMLParser

from .document import Assembled, Block
from .inline import repair_hyphens, tidy

#: Elements whose content is furniture, not text.
SKIP = {"script", "style", "head", "select", "option", "input", "noscript",
        "textarea", "button"}
VOID = {"br", "img", "hr", "meta", "link", "area", "base", "col", "source"}


class Node:
    __slots__ = ("tag", "cls", "href", "kids")

    def __init__(self, tag="", attrs=None):
        attrs = dict(attrs or {})
        self.tag = tag
        self.cls = set((attrs.get("class") or "").split())
        self.href = attrs.get("href")
        self.kids = []

    def __repr__(self):
        return f"<{self.tag} {' '.join(sorted(self.cls))}>"


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skipping += 1
            return
        if self.skipping or tag in VOID:
            return
        node = Node(tag, attrs)
        self.stack[-1].kids.append(node)
        self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skipping = max(0, self.skipping - 1)
            return
        if self.skipping or tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.skipping and data.strip():
            self.stack[-1].kids.append(data)


def parse(path) -> Node:
    with open(path, encoding="utf-8", errors="replace") as fh:
        tree = _Tree()
        tree.feed(fh.read())
    return tree.root


# ------------------------------------------------------------------ inline
def _inline(node, resolve, italic=False, bold=False) -> str:
    out = []
    for kid in node.kids:
        if isinstance(kid, str):
            # A non-breaking hyphen is a typesetting detail, not a distinction.
            text = re.sub(r"\s+", " ", kid.replace("‑", "-"))
            core = text.strip()
            if not core:
                out.append(" ")
                continue
            if italic:
                core = f"_{core}_"
            if bold:
                core = f"**{core}**"
            out.append(("" if text[0] != " " else " ") + core
                       + ("" if text[-1] != " " else " "))
            continue
        if kid.tag == "a" and kid.href:
            inner = _inline(kid, resolve, italic, bold)
            lead = " " if inner[:1] == " " else ""
            trail = " " if inner[-1:] == " " else ""
            label = inner.strip()
            if label:
                # The page can run a link straight onto the text before it;
                # a gap keeps the label from fusing with the sentence.
                if not lead and out and out[-1] and out[-1][-1] not in " ([":
                    lead = " "
                out.append(f"{lead}[{label}]({resolve(kid.href)}){trail}")
            continue
        if kid.tag in ("em", "i") or "kielenaines" in kid.cls:
            out.append(_inline(kid, resolve, True, bold))
        elif (kid.tag in ("b", "strong") or "kasite" in kid.cls
              or "huomnumero" in kid.cls):
            # 'kasite' is a defined term, set in small capitals on the page.
            out.append(_inline(kid, resolve, italic, True))
        else:
            out.append(_inline(kid, resolve, italic, bold))
    return "".join(out)


def _flat(text) -> str:
    """Collapse the source's line wrapping; it carries no meaning."""
    return re.sub(r"\s+", " ", text).strip()


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(k) for k in node.kids)


# ------------------------------------------------------------------ tables
def _table(node, resolve) -> str:
    rows, counts = [], []
    for tr in _descend(node, lambda n: n.tag == "tr"):
        cells = [tidy(_inline(td, resolve)) for td in tr.kids
                 if isinstance(td, Node) and td.tag in ("td", "th")]
        if cells:
            rows.append(cells)
            counts.append(len(cells))       # before the padding below
    if not rows:
        return ""
    width = max(counts)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # A row that labels the rows beneath it is written as a single cell across
    # the table: one cell, with something in it, where the table is wider.
    # Both halves of that matter.  A row whose last column is simply empty
    # still has the column, so counting the cells keeps it out of here; and a
    # short row that holds several things is a row of headings, not a label,
    # so only the first of them would survive being read as one.
    spanning = [i for i, row in enumerate(rows)
                if counts[i] < width and sum(1 for c in row if c) == 1 and row[0]]
    # A label with no rows under it is labelling nothing, whatever it looked
    # like; keep it as a row of its own rather than dropping it on the floor.
    while spanning and spanning[-1] == len(rows) - 1:
        spanning.pop()
    headless = False
    if spanning and len(spanning) < len(rows):
        labelled, group = [], ""
        for i, row in enumerate(rows):
            if i in spanning:
                group = re.sub(r"\*\*|_", "", row[0]).strip()
            else:
                labelled.append([group] + row)
        rows, width = labelled, width + 1
        # The table opened with a label rather than column names, so the first
        # row that survives is data and the table has no head of its own.
        headless = spanning[0] == 0

    if headless or len(rows) == 1:
        header, data = [""] * width, rows
    else:
        header, data = rows[0], rows[1:]
    # Carry sparse leading columns down: on the page a blank means 'as above'.
    for c in range(width):
        if sum(1 for r in data if r[c]) / len(data) >= 0.6:
            break
        for r in range(1, len(data)):
            if not data[r][c]:
                data[r][c] = data[r - 1][c]

    keep = [c for c in range(width) if header[c] or any(r[c] for r in data)]
    if not keep:
        return ""

    def line(cells):
        return "| " + " | ".join((cells[c] or " ").replace("|", "\\|")
                                 for c in keep) + " |"

    return "\n".join([line(header), "|" + "---|" * len(keep)]
                     + [line(r) for r in data])


def _descend(node, pred, out=None):
    out = [] if out is None else out
    for kid in node.kids:
        if isinstance(kid, Node):
            if pred(kid):
                out.append(kid)
            _descend(kid, pred, out)
    return out


# ------------------------------------------------------------------ document
def content_root(root):
    """The element holding the section itself, without the site furniture."""
    found = _descend(root, lambda n: "pykala" in n.cls)
    return found[0] if found else root


def assemble(path, profile, known=frozenset()) -> Assembled:
    root = parse(path)
    resolve = lambda href: profile.resolve_link(_absolute(href), known)
    title, crumbs, blocks, footer = "", [], [], []

    for crumb in _descend(root, lambda n: "murupolku" in n.cls):
        crumbs.extend(_flat(c) for c in _text(crumb).split(">"))
        break

    def walk(node):
        nonlocal title
        for kid in node.kids:
            if not isinstance(kid, Node):
                continue
            cls, tag = kid.cls, kid.tag
            if tag == "h2":
                # Headings wrap in the source; a line break inside one would
                # otherwise cut the title in half.
                title = tidy(_flat(_text(kid)))
            elif "huom" in cls:
                # A note is a small document of its own: it holds paragraphs and
                # example groups.  Rendering it as one run would fuse them.
                mark = len(blocks)
                walk(kid)
                for block in blocks[mark:]:
                    if block.kind == "prose":
                        block.kind = "note"
            elif "esimerkkiryhma" in cls:
                lines = []
                for body in _descend(kid, lambda n: "esim_sisalto" in n.cls):
                    heads = [k for k in body.kids if isinstance(k, Node)
                             and "otsikko_esimryhma" in k.cls]
                    for head in heads:
                        text = tidy(_inline(head, resolve))
                        if text:
                            lines.append(text)
                    # The rest is one run: the page writes its own separators
                    # between the examples, so keep it whole.
                    rest = Node("div")
                    rest.kids = [k for k in body.kids if k not in heads]
                    text = tidy(_inline(rest, resolve))
                    if text:
                        lines.append(text)
                label = ""
                for margin in _descend(kid, lambda n: "esim_marginaali" in n.cls):
                    label = _flat(_text(margin))
                    break
                if label and lines:
                    lines[0] = label + " " + lines[0]
                if lines:
                    blocks.append(Block("example", "\n".join(lines)))
            elif tag in ("h3", "h4", "h5", "h6"):
                blocks.append(Block("caption", tidy(_inline(kid, resolve))))
            elif tag == "table":
                md = _table(kid, resolve)
                if md:
                    blocks.append(Block("table", md))
            elif tag in ("ul", "ol"):
                items = [k for k in kid.kids
                         if isinstance(k, Node) and k.tag == "li"]
                # The bibliography links at the foot of the page are a list too;
                # they belong under the rule at the end, not in the body.
                if items and all(_text(i).strip().startswith("»") for i in items):
                    footer.extend(tidy(_inline(i, resolve)) for i in items)
                    continue
                lines = [tidy(_inline(i, resolve)) for i in items]
                lines = ["- " + l for l in lines if l]
                if lines:
                    blocks.append(Block("list", "\n".join(lines)))
                else:
                    walk(kid)
            elif tag == "li" and _text(kid).strip().startswith("»"):
                footer.append(tidy(_inline(kid, resolve)))
            elif tag == "p":
                text = tidy(_inline(kid, resolve))
                if text:
                    blocks.append(Block("prose", text))
            else:
                walk(kid)

    walk(content_root(root))
    for item in _descend(root, lambda n: n.tag == "li"):
        text = tidy(_inline(item, resolve))
        if text.startswith("»") and text not in footer and len(text) < 90:
            footer.append(text)

    section = None
    parsed = profile.section_id(title)
    if parsed:
        section, title = parsed
    return Assembled(title, section, [c for c in crumbs if c], blocks, footer)


#: Elements that end a run of words.  Without a break between them, the last
#: word of one cell would fuse with the first of the next.
BLOCKISH = {"p", "div", "table", "tr", "td", "th", "li", "ul", "ol", "br",
            "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "caption",
            "a"}      # two links written side by side are two separate labels


def _spaced_text(node) -> str:
    if isinstance(node, str):
        return node
    out = []
    for kid in node.kids:
        blockish = isinstance(kid, Node) and kid.tag in BLOCKISH
        if blockish:
            out.append(" ")
        out.append(_spaced_text(kid))
        if blockish:
            out.append(" ")
    return "".join(out)


def source_text(path) -> str:
    """All the words the page itself holds, for checking nothing was dropped."""
    return _spaced_text(content_root(parse(path)))


def _absolute(href) -> str:
    if re.match(r"^[a-z]+:", href or ""):
        return href
    return "https://kaino.kotus.fi/visk/" + (href or "").lstrip("/")


def to_markdown(built, profile, path) -> str:
    from .document import to_markdown as render_doc
    return repair_hyphens(render_doc(built, profile, path))


def looks_like_visk(path) -> bool:
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(4000)
    return "murupolku" in head or "kaino.kotus.fi/visk" in head


def output_name(path) -> str:
    m = re.search(r"§\s*(\d+)", os.path.basename(path))
    return "visk-%03d.md" % int(m.group(1)) if m else None
