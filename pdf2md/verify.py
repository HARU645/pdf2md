# -*- coding: utf-8 -*-
"""Check a conversion against its source.

The point is that a bad conversion should be impossible to mistake for a good
one.  Losing a word is silent otherwise: the Markdown still looks fine.
"""
from __future__ import annotations

import collections
import re

WORD = re.compile(r"[0-9A-Za-zÄÖÅäöåŋɾ]+")
# The separator under a table head.  It must actually contain dashes: an
# all-blank header row is pipes and spaces too, and is not a separator.
RULE_ROW = re.compile(r"^\|(?:\s*:?-{2,}:?\s*\|)+$")


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


def table_count(markdown) -> int:
    """How many Markdown tables the output holds."""
    return sum(1 for line in markdown.splitlines() if RULE_ROW.match(line))


def against_tags(markdown, path) -> list:
    """Compare the rebuilt tables with the ones the PDF itself declares.

    A browser-printed PDF often keeps the original HTML structure.  Where it
    does, the number of tables is a fact rather than a guess, and a mismatch
    means a table was split or two were run together.  Row counts are not
    compared: wrapped lines are deliberately folded back into their row and
    merged cells are filled down, so the counts are meant to differ.
    """
    from .tagged import read as read_tagged
    try:
        pages = read_tagged(path)
    except Exception:
        return []
    declared = sum(1 for page in pages for node in page if node.tag == "Table")
    if not declared:
        return []                       # untagged, or no tables declared
    built = table_count(markdown)
    if built != declared:
        return [f"표 개수가 PDF의 구조 정보와 다릅니다 "
                f"(문서: {declared}개, 변환 결과: {built}개)"]
    return []
