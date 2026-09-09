# -*- coding: utf-8 -*-
"""Document profiles.

A profile holds everything that is true of one *kind* of document and of
nothing else: where the title sits, what a table caption looks like, how a
cross-reference should be rewritten.  The engine itself knows none of this, so
supporting a new source means adding a profile, not touching the engine.
"""
from __future__ import annotations

import os
import re


class Profile:
    """Rules for an unknown PDF.  Deliberately cautious."""

    name = "generic"
    label = "일반 PDF"
    #: A paragraph opening with one of these is supplementary, not a main rule.
    note_prefixes: tuple = ()

    @classmethod
    def score(cls, doc) -> float:
        """How well this profile fits the document, 0..1.  The generic profile
        always fits a little, so it wins only when nothing else claims the file."""
        return 0.05 if doc.meta.get("has_text") else 0.0

    # -- classification -------------------------------------------------
    def classify(self, text, size, x0, doc, page_no, state) -> str:
        if size >= doc.body_size * 1.25 and page_no == 0:
            return "title"
        if x0 > doc.margin + 10:
            return "example"
        return "prose"

    # -- naming and links -----------------------------------------------
    def resolve_link(self, uri, known) -> str:
        return uri

    def section_id(self, title):
        return None

    def output_name(self, path, doc) -> str:
        stem = os.path.splitext(os.path.basename(path))[0]
        slug = re.sub(r"[^\w\-]+", "-", stem, flags=re.U).strip("-").lower()
        return (slug or "document") + ".md"

    def front_matter(self, title, section, breadcrumb, path) -> dict:
        return {"title": title, "source": os.path.basename(path)}

    def warnings(self, doc) -> list:
        return ["이 PDF는 알려진 형식이 아닙니다. 기본 규칙으로 변환했으니 "
                "결과를 확인해 주세요."]
