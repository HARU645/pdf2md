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

from . import profiles
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


def convert_file(path, known=frozenset(), doc=None, profile=None) -> Result:
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


def convert_many(files, dst=None, write=True) -> list:
    """Convert a set of PDFs as one group.

    Two passes: read everything first so the sections present are known, then
    convert.  Only then can a cross-reference become a link to a sibling file
    rather than back out to the website.
    """
    files = list(files)
    if not files:
        return []

    docs = {path: read(path) for path in files}
    chosen = {path: profiles.pick(doc) for path, doc in docs.items()}
    known = set()
    for path, doc in docs.items():
        profile, _ = chosen[path]
        m = re.search(r"(\d+)", profile.output_name(path, doc))
        if m and profile.name != "generic":
            known.add(int(m.group(1)))

    results = []
    for path in files:
        profile, confidence = chosen[path]
        result = convert_file(path, known, doc=docs[path], profile=profile)
        result.confidence = confidence
        results.append(result)

    if write and dst:
        save(results, dst)
    return results


def find_pdfs(folder) -> list:
    """PDFs in a folder.  If there are none, look one level down: people often
    keep the sources in a `pdf` subfolder next to where the output goes."""
    here = sorted(glob.glob(os.path.join(folder, "*.pdf")))
    if here:
        return here
    deeper = []
    for entry in sorted(glob.glob(os.path.join(folder, "*"))):
        if os.path.isdir(entry):
            deeper += sorted(glob.glob(os.path.join(entry, "*.pdf")))
    return deeper


def convert_folder(src, dst=None, write=True) -> list:
    """Convert every PDF in a folder."""
    return convert_many(find_pdfs(src), dst, write)


def save(results, dst) -> list:
    """Write results plus the folder guide.  Returns the paths written."""
    os.makedirs(dst, exist_ok=True)
    written = []
    for result in results:
        path = os.path.join(dst, result.name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(result.markdown)
        written.append(path)
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
