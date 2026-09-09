# -*- coding: utf-8 -*-
"""Regression check against frozen output.

The converter is a pile of interacting rules, so a change made to fix one
document quietly breaks another; that happened repeatedly while it was written.
This compares every conversion against the output that was reviewed and
accepted, and shows the difference when they part ways.

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

from pdf2md.convert import convert_folder  # noqa: E402

GOLDEN = os.path.join(ROOT, "tests", "golden")


def default_source():
    """Where the sample PDFs live.  Kept out of the repository: it is one
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


SOURCE = default_source()


def run(accept=False, source=SOURCE) -> int:
    if not os.path.isdir(source):
        print(f"원본 폴더를 찾을 수 없습니다: {source}")
        return 2

    results = convert_folder(source, write=False)
    os.makedirs(GOLDEN, exist_ok=True)
    changed, missing, failed = [], [], []

    for r in results:
        expected_path = os.path.join(GOLDEN, r.name)
        if accept:
            with open(expected_path, "w", encoding="utf-8") as fh:
                fh.write(r.markdown)
            continue
        if not os.path.exists(expected_path):
            missing.append(r.name)
            continue
        with open(expected_path, encoding="utf-8") as fh:
            expected = fh.read()
        if expected != r.markdown:
            changed.append((r.name, expected, r.markdown))
        if r.lost:
            failed.append((r.name, sum(r.lost.values())))

    if accept:
        print(f"정답지 {len(results)}개를 갱신했습니다: {GOLDEN}")
        return 0

    for name, expected, actual in changed:
        print(f"\n=== {name} 달라짐 ===")
        diff = difflib.unified_diff(expected.split("\n"), actual.split("\n"),
                                    "정답지", "지금 결과", lineterm="", n=1)
        for line in list(diff)[:24]:
            print("  " + line[:160])

    for name in missing:
        print(f"정답지 없음: {name} (--accept 로 추가할 수 있습니다)")
    for name, n in failed:
        print(f"내용 손실: {name} 에서 단어 {n}개")

    total = len(results)
    bad = len(changed) + len(missing) + len(failed)
    print(f"\n{total}개 중 {total - len(changed) - len(missing)}개 정답지와 일치"
          + (f", {len(failed)}개 손실 발생" if failed else ""))
    if bad == 0:
        print("통과")
    else:
        print("의도한 변경이면 --accept 로 정답지를 갱신하세요.")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept", action="store_true", help="현재 결과를 정답지로 저장")
    ap.add_argument("--source", default=SOURCE)
    raise SystemExit(run(ap.parse_args().accept, ap.parse_args().source))
