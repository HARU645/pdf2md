# -*- coding: utf-8 -*-
"""Regression check against frozen output.

The converter is a pile of interacting rules, so a change made to fix one
document quietly breaks another; that happened repeatedly while it was written.
This compares every conversion against the output that was reviewed and
accepted, and shows the difference when they part ways.

Both routes are checked.  Saved web pages are what the tool now prefers, but
the PDF route still has to work for sources that exist only as printouts.

    python tests/test_golden.py            # check
    python tests/test_golden.py --accept   # adopt current output as correct
"""
from __future__ import annotations

import argparse
import difflib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pdf2md.convert import convert_many, find_sources  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "golden")


def default_source():
    """Where the sample pages live.  Kept out of the repository: it is one
    machine's layout, not part of the tool."""
    env = os.environ.get("PDF2MD_SOURCE_FOLDER")
    if env:
        return env
    secrets = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets):
        try:
            import tomllib
            with open(secrets, "rb") as fh:
                return tomllib.load(fh).get("source_folder", "")
        except Exception:
            pass
    return ""


def routes(source):
    """(name, folder) for each way in, when that folder holds anything."""
    base = os.path.dirname(source.rstrip("\\/")) or source
    for name in ("html", "pdf"):
        folder = os.path.join(base, name)
        if find_sources(folder):
            yield name, folder


def check_route(name, folder, accept) -> int:
    expected_dir = os.path.join(GOLDEN, name)
    os.makedirs(expected_dir, exist_ok=True)
    results = convert_many(find_sources(folder), write=False)
    changed, missing, failed = [], [], []

    for r in results:
        path = os.path.join(expected_dir, r.name)
        if accept:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(r.markdown)
            continue
        if not os.path.exists(path):
            missing.append(r.name)
            continue
        with open(path, encoding="utf-8") as fh:
            expected = fh.read()
        if expected != r.markdown:
            changed.append((r.name, expected, r.markdown))
        if r.lost or r.issues:
            failed.append((r.name, sum(r.lost.values()) if r.lost else 0, r.issues))

    if accept:
        print(f"[{name}] 정답지 {len(results)}개를 갱신했습니다")
        return 0

    for filename, expected, actual in changed:
        print(f"\n=== [{name}] {filename} 달라짐 ===")
        diff = difflib.unified_diff(expected.split("\n"), actual.split("\n"),
                                    "정답지", "지금 결과", lineterm="", n=1)
        for line in list(diff)[:24]:
            print("  " + line[:160])
    for filename in missing:
        print(f"[{name}] 정답지 없음: {filename} (--accept 로 추가할 수 있습니다)")
    for filename, lost, issues in failed:
        print(f"[{name}] 문제: {filename} 손실 {lost}개 {issues}")

    ok = len(results) - len(changed) - len(missing)
    print(f"[{name}] {len(results)}개 중 {ok}개 정답지와 일치"
          + (f", {len(failed)}개 문제 있음" if failed else ""))
    return len(changed) + len(missing) + len(failed)


def run(accept=False, source=None) -> int:
    source = source or default_source()
    found = list(routes(source)) if source else []
    if not found:
        print(f"원본 폴더를 찾을 수 없습니다: {source}")
        return 2
    bad = sum(check_route(name, folder, accept) for name, folder in found)
    if not accept:
        print("\n통과" if bad == 0
              else "\n의도한 변경이면 --accept 로 정답지를 갱신하세요.")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept", action="store_true", help="현재 결과를 정답지로 저장")
    ap.add_argument("--source", default=None)
    args = ap.parse_args()
    raise SystemExit(run(args.accept, args.source))
