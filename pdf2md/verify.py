# -*- coding: utf-8 -*-
"""Check a conversion against its source.

The point is that a bad conversion should be impossible to mistake for a good
one.  Losing a word is silent otherwise: the Markdown still looks fine.
"""
from __future__ import annotations

import collections
import re

WORD = re.compile(r"[0-9A-Za-zÄÖÅäöåŋɾ]+")
RULE_ROW = re.compile(r"^\|[-|\s]+\|$")


def tokens(text, markdown=False):
    if markdown:
        # The front matter is kept.  Content moves into it -- the breadcrumb and
        # the title -- and a word that lives only there has not been lost.
        text = re.sub(r"^\s*[a-z_]+:", " ", text, flags=re.M)          # yaml keys
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)           # link targets
        for ch in "*_":
            text = text.replace(ch, "")          # markers vanish: _rä_**_tt_**_i_
        for ch in "|#>":
            text = text.replace(ch, " ")         # structure becomes a break
    return collections.Counter(w.lower() for w in WORD.findall(text))


def lost_tokens(raw_text, markdown, title=""):
    """Source words that did not reach the output.

    Two differences are expected and filtered out: the breadcrumb repeats the
    title, and a word split by a line break is rejoined into a longer one.
    """
    source = tokens(raw_text) - tokens(title)
    produced = tokens(markdown, markdown=True)
    missing = source - produced
    long_words = [w for w in produced if len(w) > 3]
    return collections.Counter(
        {w: n for w, n in missing.items()
         if not any(w in longer for longer in long_words)})


def structure_issues(markdown) -> list:
    issues = []

    header = None
    for n, line in enumerate(markdown.split("\n"), 1):
        if not line.startswith("|"):
            header = None
            continue
        cells = line.replace("\\|", "").count("|") - 1
        if header is None:
            header = cells
            continue
        if RULE_ROW.match(line):
            continue
        if cells != header:
            issues.append(f"{n}행: 표의 칸 수가 머리글과 다릅니다 "
                          f"({header} vs {cells})")

    body = re.sub(r"\]\([^)]*\)", "]()", markdown)
    body = re.sub(r"^---$.*?^---$", "", body, flags=re.S | re.M)
    if body.count("_") % 2:
        issues.append("기울임 표시(_)의 짝이 맞지 않습니다")
    if body.count("**") % 2:
        issues.append("굵게 표시(**)의 짝이 맞지 않습니다")
    return issues


def report(raw_text, markdown, title="") -> dict:
    lost = lost_tokens(raw_text, markdown, title)
    issues = structure_issues(markdown)
    return {"lost": lost, "lost_count": sum(lost.values()),
            "issues": issues, "ok": not lost and not issues}
