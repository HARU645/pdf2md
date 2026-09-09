# -*- coding: utf-8 -*-
"""Command line entry point.

    python cli.py "C:\\myfiles\\pdf" -o "C:\\myfiles\\markdown"
    python cli.py one-file.pdf -o output --quiet
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

from pdf2md.convert import (convert_many, find_sources, missing_references,
                            save)

STATUS = {"정상": "OK  ", "확인": "확인", "손실": "손실"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="pdf2md",
        description="PDF와 저장한 웹페이지를 AI가 읽기 좋은 마크다운으로 바꿉니다.")
    ap.add_argument("source", nargs="+",
                    help="PDF나 저장한 웹페이지(.html), 또는 그것이 든 폴더")
    ap.add_argument("-o", "--out", default="output", help="저장할 폴더 (기본: output)")
    ap.add_argument("--dry-run", action="store_true", help="변환만 하고 저장하지 않음")
    ap.add_argument("--quiet", action="store_true", help="요약만 출력")
    args = ap.parse_args(argv)

    files = []
    for item in args.source:
        if os.path.isdir(item):
            files += find_sources(item)
        elif os.path.isfile(item):
            files.append(item)
        else:
            print(f"찾을 수 없습니다: {item}", file=sys.stderr)
            return 2

    results = convert_many(files, write=False)
    if results and not args.dry_run:
        save(results, args.out)

    if not results:
        print("변환할 파일을 찾지 못했습니다.", file=sys.stderr)
        return 1

    lost_total = 0
    for r in results:
        lost = sum(r.lost.values()) if r.lost else 0
        lost_total += lost
        if not args.quiet:
            mark = "!!" if lost else ("??" if r.issues or r.warnings else "OK")
            print(f"  {mark}  {r.name:<18} {r.profile}")
            if lost:
                words = ", ".join(list(r.lost)[:8])
                print(f"        빠진 단어 {lost}개: {words}")
            for note in r.issues + r.warnings:
                print(f"        - {note}")

    ok = sum(1 for r in results if r.ok)
    print(f"\n{len(results)}개 중 {ok}개 정상"
          + (f", 단어 {lost_total}개 손실" if lost_total else ", 손실 없음"))

    missing = missing_references(results)
    if missing:
        print(f"\n참조되지만 이 폴더에 없는 문서 {len(missing)}개:")
        print("  " + ", ".join("§ %d" % n for n in missing))
    if not args.dry_run:
        print(f"\n저장 위치: {os.path.abspath(args.out)}")
    return 1 if lost_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
