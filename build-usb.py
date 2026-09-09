# -*- coding: utf-8 -*-
"""Build the copy that travels on a memory stick.

    python build-usb.py                       # 앱만
    python build-usb.py --documents D:\\...\\visk   # 원본까지 함께

The folder this makes carries its own Python, so it runs on a Windows computer
that has nothing installed -- no Python, no administrator rights, no internet.
That is the whole point: a `venv` is a set of pointers to a Python installed
somewhere on this machine, and pointers do not survive the trip.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist", "pdf2md-usb")
CACHE = os.path.join(ROOT, "dist", "_cache")

PYTHON_VERSION = "3.12.5"
EMBED_URL = ("https://www.python.org/ftp/python/%s/python-%s-embed-amd64.zip"
             % (PYTHON_VERSION, PYTHON_VERSION))
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

#: Copied as they are.  `.streamlit/secrets.toml` is deliberately not here:
#: it holds this machine's password and folder layout.
CARRY = ["app.py", "cli.py", "requirements.txt", "README.md"]
CARRY_TREES = ["pdf2md"]


def fetch(url, path) -> str:
    if not os.path.exists(path):
        print("  받는 중: " + url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(url, path)
    return path


def lay_python(into) -> str:
    """Unpack the Python that needs no installing, and let it see the packages
    that get installed beside it -- the shipped settings file hides them."""
    folder = os.path.join(into, "python")
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile(fetch(EMBED_URL, os.path.join(CACHE, "python-embed.zip"))) as zf:
        zf.extractall(folder)
    name = "python%s._pth" % PYTHON_VERSION.rsplit(".", 1)[0].replace(".", "")
    with open(os.path.join(folder, name), "w", encoding="ascii") as fh:
        fh.write("python{0}.zip\n.\nLib{1}site-packages\n..\n\nimport site\n"
                 .format(PYTHON_VERSION.rsplit(".", 1)[0].replace(".", ""), os.sep))
    return os.path.join(folder, "python.exe")


def install(python) -> None:
    print("  pip 를 넣는 중")
    subprocess.check_call([python, fetch(GET_PIP_URL, os.path.join(CACHE, "get-pip.py")),
                           "-q", "--no-warn-script-location"])
    print("  라이브러리를 넣는 중 (몇 분 걸립니다)")
    subprocess.check_call([python, "-m", "pip", "install", "-q",
                           "--no-warn-script-location", "-r",
                           os.path.join(ROOT, "requirements.txt")])


def copy_app(into) -> None:
    for name in CARRY:
        shutil.copy2(os.path.join(ROOT, name), os.path.join(into, name))
    for name in CARRY_TREES:
        shutil.copytree(os.path.join(ROOT, name), os.path.join(into, name),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    os.makedirs(os.path.join(into, ".streamlit"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, ".streamlit", "config.toml"),
                 os.path.join(into, ".streamlit", "config.toml"))
    for name in os.listdir(os.path.join(ROOT, "portable")):
        shutil.copy2(os.path.join(ROOT, "portable", name), os.path.join(into, name))


def size_of(folder) -> str:
    total = sum(os.path.getsize(os.path.join(where, f))
                for where, _, files in os.walk(folder) for f in files)
    return "%.0f MB" % (total / 1024 / 1024)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--documents", help="함께 넣을 원본 폴더 (html/pdf 가 든 곳)")
    args = ap.parse_args()

    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)

    print("USB 판을 만듭니다 → " + DIST)
    python = lay_python(DIST)
    install(python)
    copy_app(DIST)

    if args.documents:
        target = os.path.join(DIST, "visk")
        print("  원본을 넣는 중: " + args.documents)
        shutil.copytree(args.documents, target,
                        ignore=shutil.ignore_patterns("__pycache__"))

    print("\n끝났습니다. %s · %s" % (DIST, size_of(DIST)))
    print("이 폴더를 통째로 USB에 복사하고, 실행.bat 을 더블클릭하면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
