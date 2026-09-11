# -*- coding: utf-8 -*-
"""Drive a conversion: one file, or a whole folder at once.

A folder is done in two passes.  The first pass reads every PDF so the set of
sections present is known; only then can a cross-reference be turned into a
link to a sibling file rather than back to the website.
"""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import pymupdf

from . import html_source, profiles
from .document import assemble, to_markdown
from .reader import read
from .verify import against_tags, report

SECTION_REF = re.compile(r"sisallys\.php\?p=(\d+)")


@dataclass
class Result:
    path: str
    name: str
    markdown: str
    profile: str
    confidence: float
    section: object = None
    title: str = ""
    lost: object = None
    issues: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    #: Pictures to write beside this file, as {file name: bytes}.
    assets: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.lost and not self.issues

    @property
    def status(self) -> str:
        if self.lost:
            return "손실"
        if self.issues or self.warnings:
            return "확인"
        return "정상"

    def references(self) -> set:
        body = re.sub(r"^---$.*?^---$", "", self.markdown, flags=re.S | re.M)
        found = {int(m) for m in SECTION_REF.findall(body)}
        found |= {int(m) for m in re.findall(r"\./visk-(\d+)\.md", body)}
        return found


def _raw_text(path) -> str:
    doc = pymupdf.open(path)
    text = "\n".join(p.get_text() for p in doc)
    doc.close()
    lines = [l for l in text.split("\n")
             if not l.startswith("SISÄLLYS") and "Copyright ©" not in l]
    return "\n".join(lines)


def is_html(path) -> bool:
    # A page saved as a single file is a saved page too; it simply keeps its
    # pictures inside itself rather than in a folder that can go missing.
    return path.lower().endswith((".html", ".htm", ".mhtml", ".mht"))


def convert_file(path, known=frozenset(), doc=None, profile=None) -> Result:
    if is_html(path):
        return _convert_html(path, known, profile)
    doc = doc or read(path)
    if profile is None:
        profile, confidence = profiles.pick(doc)
    else:
        confidence = 1.0
    built = assemble(doc, profile, known)
    markdown = to_markdown(built, profile, path)
    checks = report(_raw_text(path), markdown, built.title)
    checks["issues"] += against_tags(markdown, path)
    warnings = list(profile.warnings(doc))
    for block in built.blocks:
        warnings += block.warnings
    return Result(path=path, name=profile.output_name(path, doc), markdown=markdown,
                  profile=profile.name, confidence=confidence, section=built.section,
                  title=built.title, lost=checks["lost"] or None,
                  issues=checks["issues"], warnings=warnings)


def _convert_html(path, known, profile) -> Result:
    """A saved web page still carries its own structure, so nothing is inferred."""
    if profile is None:
        profile = profiles.ViskProfile() if html_source.looks_like_visk(path)             else profiles.Profile()
    built = html_source.assemble(path, profile, known)
    markdown = to_markdown(built, profile, path)
    checks = report(html_source.source_text(path), markdown, built.title)
    name = html_source.output_name(path) or profile.output_name(path, None)
    return Result(path=path, name=name, markdown=markdown,
                  profile=profile.name + "+html", confidence=1.0,
                  section=built.section, title=built.title,
                  lost=checks["lost"] or None, issues=checks["issues"],
                  assets=built.assets,
                  warnings=list(profile.warnings(None)) if profile.name == "generic" else [])


def convert_many(files, dst=None, write=True) -> list:
    """Convert a set of PDFs as one group.

    Two passes: read everything first so the sections present are known, then
    convert.  Only then can a cross-reference become a link to a sibling file
    rather than back out to the website.
    """
    files = list(files)
    if not files:
        return []

    docs, chosen = {}, {}
    for path in files:
        if is_html(path):
            chosen[path] = (profiles.ViskProfile()
                            if html_source.looks_like_visk(path)
                            else profiles.Profile(), 1.0)
        else:
            docs[path] = read(path)
            chosen[path] = profiles.pick(docs[path])

    known = set()
    for path in files:
        profile, _ = chosen[path]
        name = (html_source.output_name(path) if is_html(path)
                else profile.output_name(path, docs.get(path)))
        m = re.search(r"(\d+)", name or "")
        if m and profile.name != "generic":
            known.add(int(m.group(1)))

    results = []
    for path in files:
        profile, confidence = chosen[path]
        result = convert_file(path, known, doc=docs.get(path), profile=profile)
        result.confidence = confidence
        results.append(result)

    if write and dst:
        save(results, dst)
    return results


def find_sources(folder) -> list:
    """What to convert from a folder.

    A saved web page is preferred over a printout of one: the HTML still says
    what everything is, while the PDF has to be read back from coordinates.
    If there is nothing at the top level, look one folder down -- sources are
    often kept in a `html` or `pdf` subfolder beside the output.
    """
    for look in (lambda pat: glob.glob(os.path.join(folder, pat)),
                 lambda pat: [f for entry in sorted(glob.glob(os.path.join(folder, "*")))
                              if os.path.isdir(entry)
                              for f in glob.glob(os.path.join(entry, pat))]):
        pages = [f for pat in WEB for f in look(pat)]
        if pages:
            return _one_each(pages)
        printouts = sorted(look("*.pdf"))
        if printouts:
            return printouts
    return []


#: Saved pages, whichever way the browser was asked to save them.
WEB = ("*.mhtml", "*.mht", "*.html", "*.htm")


def _one_each(pages) -> list:
    """One source per page, when the same page was saved more than one way.

    The single-file kind wins: it is the only one that carries the pictures,
    and the other kind points at a folder that may or may not have come along.
    """
    best = {}
    for path in pages:
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        rank = 0 if path.lower().endswith((".mhtml", ".mht")) else 1
        if stem not in best or rank < best[stem][0]:
            best[stem] = (rank, path)
    return sorted(path for _, path in best.values())


def find_pdfs(folder) -> list:            # kept for callers that want only PDFs
    return [f for f in find_sources(folder) if f.lower().endswith(".pdf")]


def convert_folder(src, dst=None, write=True) -> list:
    """Convert every PDF in a folder."""
    return convert_many(find_sources(src), dst, write)


def save(results, dst) -> list:
    """Write results plus the folder guide.  Returns the paths written."""
    os.makedirs(dst, exist_ok=True)
    written = []
    for result in results:
        path = os.path.join(dst, result.name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(result.markdown)
        written.append(path)
        for name, data in result.assets.items():
            # The pictures the page carried, written where its links point.
            folder = os.path.join(dst, "images")
            os.makedirs(folder, exist_ok=True)
            spot = os.path.join(folder, name)
            with open(spot, "wb") as fh:
                fh.write(data)
            written.append(spot)
    index_path = os.path.join(dst, "index.md")
    with open(index_path, "w", encoding="utf-8") as fh:
        fh.write(build_index(results))
    written.append(index_path)
    return written


def missing_references(results) -> list:
    have = {r.section for r in results if r.section is not None}
    wanted = set()
    for r in results:
        wanted |= r.references()
    return sorted(wanted - have)


def build_index(results) -> str:
    """A short guide to the folder, so a reader knows what is here without
    opening every file."""
    lines = ["---", 'title: "변환된 문서 목록"',
             f"count: {len(results)}", "---", "", "# 문서 목록", ""]

    tree = {}
    for r in results:
        lines_for = r
        key = " / ".join(_hierarchy(r)) or "(분류 없음)"
        tree.setdefault(key, []).append(lines_for)

    for branch in sorted(tree):
        lines.append(f"## {branch}")
        lines.append("")
        for r in sorted(tree[branch], key=lambda x: (x.section or 0, x.name)):
            label = f"§ {r.section} {r.title}" if r.section else r.title or r.name
            lines.append(f"- [{label}](./{r.name})")
        lines.append("")

    missing = missing_references(results)
    if missing:
        lines += ["## 참조되지만 없는 문서", "",
                  "아래 절들이 본문에서 인용되지만 이 폴더에 없습니다. "
                  "링크를 따라가면 원문 사이트로 나갑니다.", "",
                  "```", ", ".join("§ %d" % n for n in missing), "```", ""]
    return "\n".join(lines)


def _hierarchy(result) -> list:
    match = re.search(r"^breadcrumb:\n((?:  - .*\n)+)", result.markdown, re.M)
    if not match:
        return []
    crumbs = re.findall(r'  - "(.*)"', match.group(1))
    return crumbs[1:4]
