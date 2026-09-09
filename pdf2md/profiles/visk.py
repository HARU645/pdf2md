# -*- coding: utf-8 -*-
"""VISK (Iso suomen kielioppi) pages printed to PDF from the browser.

Everything specific to that source lives here: the breadcrumb strip at the top
of page one, the Georgia heading, `Asetelma N` table captions, `Huom.` notes,
the kotus.fi cross-references and the visk-NNN.md file naming that ties the
converted set together.
"""
from __future__ import annotations

import os
import re

from .base import Profile

SECTION_URL = re.compile(r"https?://kaino\.kotus\.fi/visk/sisallys\.php\?p=(\d+)")

#: What a converted section is called.  The work runs past § 1400, so three
#: digits would leave the names ragged and sort § 49 after § 1445; four keep
#: every file the same width and in section order.
NAME = "visk-%04d.md"


class ViskProfile(Profile):
    name = "visk"
    label = "VISK (Iso suomen kielioppi)"
    note_prefixes = ("Huom.",)

    @classmethod
    def score(cls, doc) -> float:
        hits = sum(1 for page in doc.pages for _, uri in page.links
                   if "kaino.kotus.fi/visk" in uri)
        first = " ".join(l.text for l in doc.pages[0].lines[:2]) if doc.pages else ""
        crumb = first.strip().startswith("SISÄLLYS")
        titled = bool(re.search(r"§\s*\d+", first))
        return min(1.0, 0.5 * crumb + 0.3 * titled + 0.2 * bool(hits))

    # -- classification -------------------------------------------------
    def classify(self, text, size, x0, doc, page_no, state) -> str:
        if size >= doc.body_size * 1.25:
            state["in_crumb"] = False
            return "title"
        # The breadcrumb opens page one and can wrap onto a second line.  Match
        # it by content rather than by size: a table-heavy page can shift what
        # counts as small type.
        if page_no == 0 and not state.get("body_seen"):
            if text.startswith("SISÄLLYS"):
                state["in_crumb"] = True
                return "breadcrumb"
            if state.get("in_crumb") and size < doc.body_size:
                return "breadcrumb"
        state["in_crumb"] = False
        if text.startswith("Copyright ©"):
            return "drop"
        if re.match(r"^»\s", text) and len(text) < 60:
            return "footer"
        # VISK numbers its tables two ways: 'Asetelma' inline, 'Taulukko' for
        # statistics.  The colon is what separates a caption from a sentence
        # that merely opens with the same words ('Taulukko 3 esittää...').
        if re.match(r"^(Asetelma|Taulukko)\s+\d+\s*:", text):
            return "caption"
        if x0 > doc.margin + 10:
            return "example"
        return "prose"

    # -- naming and links -----------------------------------------------
    def resolve_link(self, uri, known) -> str:
        m = SECTION_URL.match(uri)
        if m and int(m.group(1)) in known:
            return "./" + NAME % int(m.group(1))
        return uri

    def section_id(self, title):
        m = re.match(r"§\s*(\d+)\s+(.*)", title or "")
        return (int(m.group(1)), m.group(2).strip()) if m else None

    def output_name(self, path, doc) -> str:
        m = re.search(r"§\s*(\d+)", os.path.basename(path))
        if m:
            return NAME % int(m.group(1))
        return super().output_name(path, doc)

    def front_matter(self, title, section, breadcrumb, path) -> dict:
        data = {"id": section, "title": title}
        if section:
            data["source"] = ("https://kaino.kotus.fi/visk/sisallys.php?p=%d"
                              % section)
        # The last crumb repeats the title; the ones before it are the hierarchy.
        data["breadcrumb"] = breadcrumb[:-1] if len(breadcrumb) > 1 else breadcrumb
        return data

    def warnings(self, doc) -> list:
        return []
