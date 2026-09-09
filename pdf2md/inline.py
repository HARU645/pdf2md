# -*- coding: utf-8 -*-
"""Turn style runs into inline Markdown, and tidy the result.

Emphasis carries meaning in a grammar: italics mark object-language forms and
bold marks the segment under discussion, so both must survive intact.
"""
from __future__ import annotations

import re

import pymupdf

# Finnish coordinators.  "yksi- ja kaksivartaloinen" is ellipsis, not a
# hyphenated word, so the space after the hyphen has to stay.
CONJUNCTIONS = {"ja", "tai", "sekä", "kuin", "että", "eli", "vai", "eikä",
                "mutta", "vaan", "ynnä", "saati", "joko", "ei"}


def run_md(run) -> str:
    text = (run.text.replace("\xa0", " ")
                    .replace("\u00ad", "")      # soft hyphen: never meaningful
                    .replace("\u2011", "-"))    # non-breaking hyphen
    core = text.strip()
    if not core:
        return text
    lead = text[:len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    if run.smallcaps:
        core = f"**{core}**"
    else:
        if run.italic:
            core = f"_{core}_"
        if run.bold:
            core = f"**{core}**"
    return lead + core + trail


def render(runs, links, resolve=lambda uri: uri) -> str:
    """Render runs, wrapping stretches that sit inside a link rectangle."""
    def target(run):
        rect = pymupdf.Rect(run.x0, run.y0, run.x1, run.y1)
        if rect.is_empty:
            return None
        for area, uri in links:
            if (area & rect).get_area() > rect.get_area() * 0.4:
                return uri
        return None

    out: list[str] = []
    prev_x1 = None
    i = 0
    while i < len(runs):
        run = runs[i]
        # Table cells drop pure-whitespace runs; restore the gap they stood for.
        if (prev_x1 is not None and run.x0 - prev_x1 > 1.0
                and out and not out[-1].endswith(" ")
                and not run.text.startswith(" ")):
            out.append(" ")
        uri = target(run)
        if uri is None:
            out.append(run_md(run))
            prev_x1 = run.x1
            i += 1
            continue
        buf = []
        while i < len(runs) and target(runs[i]) == uri:
            buf.append(run_md(runs[i]))
            prev_x1 = runs[i].x1
            i += 1
        label = "".join(buf)
        out.append(f"[{label.strip()}]({resolve(uri)})"
                   + (" " if label != label.rstrip() else ""))
    return "".join(out)


def tidy(text: str) -> str:
    s = text.replace("\xa0", " ")
    s = re.sub(r"\*\*(\s*)\*\*", r"\1", s)      # keep the space between terms
    s = re.sub(r"_(\s*)_", r"\1", s)
    s = re.sub(r"\s+([,.;!?])", r"\1", s)       # ':' is a real separator here
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"\s+([)\]])", r"\1", s)
    # A small-caps term keeps a full capital first letter, so 'A' plus small-cap
    # 'stevaihtelu' arrives as two pieces; make it one term.
    s = re.sub(r"(?<![\w*])([A-ZÄÖÅ])\*\*([^*]+?)\*\*", r"**\1\2**", s)
    for _ in range(3):
        s = re.sub(r"\*\*([^*]*?)\*\*([\s-]?)\*\*([^*]*?)\*\*", r"**\1\2\3**", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def repair_hyphens(md: str) -> str:
    """Undo hyphenation that a line break baked into the text.

    Two different things wear a hyphen here.  A word split across lines should
    be rejoined, but only when the joined form appears elsewhere in the same
    document, so nothing is invented.  A morpheme boundary (talo-n, pui-ta) is
    meant to stay; only the stray space inside it goes.  Finnish coordination
    ellipsis (yksi- ja kaksivartaloinen) must be left completely alone.
    """
    words = set(re.findall(r"[a-zäöå]{3,}", md.lower()))

    def join_if_attested(m):
        a, b = m.group(1), m.group(2)
        return a + b if (a + b).lower() in words else m.group(0)

    md = re.sub(r"\b([a-zäöå]{3,})-([a-zäöå]{3,})\b", join_if_attested, md)
    md = re.sub(r"([a-zäöå_*])- (?=[a-zäöå_*])(\w+)",
                lambda m: m.group(0) if m.group(2) in CONJUNCTIONS
                else m.group(1) + "-" + m.group(2), md)
    return md
