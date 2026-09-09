# -*- coding: utf-8 -*-
"""Local screen for pdf2md.

    streamlit run app.py

Two ways in.  A folder is typed as a path, because a browser upload hands over
the file contents without the path and a folder job needs to know where it came
from.  Individual files come in as uploads, which suits picking a few at a time.
"""
from __future__ import annotations

import hmac
import io
import os
import stat
import tempfile
import time
import zipfile

import streamlit as st

from pdf2md.convert import (build_index, convert_many, find_sources,
                            missing_references, save)

st.set_page_config(page_title="PDF → Markdown", page_icon="📄", layout="wide")

def _setting(name, fallback=""):
    """Read a local setting.  Kept out of the repository so the code carries no
    one machine's folder layout; absent, the field simply starts empty."""
    try:
        return st.secrets.get(name, fallback)
    except Exception:
        return os.environ.get("PDF2MD_" + name.upper(), fallback)


HERE = os.path.dirname(os.path.abspath(__file__))

#: A copy that travels on a memory stick keeps its documents beside itself, and
#: the drive letter changes from one computer to the next, so the folder next
#: door is the only starting point that stays true.
BESIDE = os.path.join(HERE, "visk")
TRAVELLING = os.path.isdir(BESIDE)

DEFAULT_SOURCE = _setting("source_folder") or (BESIDE if TRAVELLING else "")
DEFAULT_OUT = _setting("output_folder") or (
    os.path.join(BESIDE, "markdown") if TRAVELLING else os.path.join(HERE, "output"))

# Reading and writing folders only makes sense on the machine that holds them.
# Hosted anywhere else the app is upload-in, download-out, and says so.
# Hosts run Linux; set PDF2MD_HOSTED=1 to try that shape here.
LOCAL = os.name == "nt" and os.environ.get("PDF2MD_HOSTED") != "1"


SOURCE_EXT = (".pdf", ".html", ".htm")


def _sources_in(path) -> int:
    """How many convertible files sit directly in a folder."""
    try:
        return sum(1 for e in os.scandir(path)
                   if e.is_file() and e.name.lower().endswith(SOURCE_EXT))
    except OSError:
        return 0


#: Characters that mean something to the file system rather than to a reader.
NOT_IN_A_NAME = set('<>:"/|?*') | {chr(92)} | {chr(c) for c in range(32)}


def scratch_name(name, index) -> str:
    """A name that is safe to write into the scratch folder.

    Nobody checks what the browser sends as a file name, so it can be a path:
    "../../notes.html" would be written wherever that leads, outside the
    scratch folder entirely.  Only the last part of it is kept, and only the
    characters that carry no meaning to the file system.  The name is trimmed
    rather than replaced, because the section number is read out of it later.
    """
    base = name.replace(chr(92), "/").rstrip("/").rsplit("/", 1)[-1]
    base = "".join("_" if c in NOT_IN_A_NAME else c for c in base).strip(" .")
    stem, ext = os.path.splitext(base)
    if ext.lower() not in SOURCE_EXT:
        return ""                   # not one of the kinds this tool converts
    return (stem[:80] or "file-%d" % index) + ext.lower()


#: Windows keeps a crowd of bookkeeping folders beside a person's own ones.
#: They are marked hidden or system, so the marking is what to go by.
BURIED = (getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0)
          | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 0))


def _visible(entry) -> bool:
    if entry.name.startswith((".", "$")):
        return False
    try:
        return not (entry.stat(follow_symlinks=False).st_file_attributes & BURIED)
    except (OSError, AttributeError):
        return True             # no such marking here; show it


def _subfolders(path) -> list:
    """Sub-folders worth showing, in name order."""
    try:
        found = [e for e in os.scandir(path) if e.is_dir() and _visible(e)]
    except OSError:
        return []               # a folder this account may not read
    found.sort(key=lambda e: e.name.lower())
    return found


def _drives() -> list:
    return [d + ":\\" for d in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.isdir(d + ":\\")]


def _parent(path) -> str:
    trimmed = path.rstrip("\\/")
    if len(trimmed) < 3:                # already a drive root such as 'D:'
        return path
    above = os.path.dirname(trimmed)
    return above if os.path.isdir(above) else path


def browse(key, start):
    """Walk this computer's folders and hand back the one that is picked.

    Deliberately not the system's folder dialog.  The page can be open on a
    different machine from the files, and a dialog would then open beside the
    files, where nobody is looking, with the page waiting on a window that will
    never be answered.  Walking inside the page works either way.
    """
    at = st.session_state.get(key)
    if not at or not os.path.isdir(at):
        at = start if start and os.path.isdir(start) else os.path.expanduser("~")
        st.session_state[key] = at

    def go(path):
        st.session_state[key] = path
        st.rerun()

    st.code(at, language=None)

    drives = _drives()
    row = st.columns([2, 2] + [1] * len(drives))
    if row[0].button("⬆ 상위 폴더", key=key + "-up", width="stretch"):
        go(_parent(at))
    picked = row[1].button("✓ 이 폴더 선택", key=key + "-ok", type="primary",
                           width="stretch")
    for col, drive in zip(row[2:], drives):
        if col.button(drive[:2], key=key + "-drive-" + drive[0], width="stretch"):
            go(drive)

    folders = _subfolders(at)
    shown = folders[:200]
    # Counting means opening every sub-folder, so only do it where the answer is
    # useful: a folder with hundreds of children is somewhere on the way, not
    # the destination.
    counting = len(shown) <= 40
    for i in range(0, len(shown), 4):
        for col, entry in zip(st.columns(4), shown[i:i + 4]):
            held = _sources_in(entry.path) if counting else 0
            label = f"📁 {entry.name}" + (f"  ({held})" if held else "")
            if col.button(label, key=key + "-in-" + entry.path, width="stretch"):
                go(entry.path)
    if len(folders) > len(shown):
        st.caption(f"하위 폴더가 {len(folders)}개라 앞의 200개만 보여줍니다. "
                   "위 칸에 경로를 직접 적어도 됩니다.")
    elif not folders:
        st.caption("하위 폴더가 없습니다.")

    here = _sources_in(at)
    st.caption(f"이 폴더에 변환할 파일 {here}개가 있습니다."
               if here else "이 폴더에는 변환할 파일이 없습니다.")
    return at if picked else None


def folder_field(box, label, key, default):
    """A folder path, typed or picked.  Typing is quicker when the path is
    already known, so the box stays and the browser sits beside it.

    The opener is a button rather than a tick box because picking a folder has
    to close the browser again, and a tick box cannot be un-ticked from here:
    the page refuses to change a control that has already been drawn.
    """
    value = box.text_input(label, value=st.session_state.get(key, default))
    st.session_state[key] = value
    flag = "open-" + key
    open_now = st.session_state.get(flag)
    if box.button("✕ 닫기" if open_now else "📁 폴더 찾아보기",
                  key="toggle-" + key, width="stretch"):
        st.session_state[flag] = not open_now
        st.rerun()
    return value


def folder_browser(key, label):
    if not st.session_state.get("open-" + key):
        return
    with st.container(border=True):
        st.caption(label)
        picked = browse("at-" + key, st.session_state.get(key, ""))
    if picked:
        st.session_state[key] = picked
        st.session_state["open-" + key] = False
        st.rerun()


SECRETS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       ".streamlit", "secrets.toml")


def _password():
    """(password, trouble).

    'Trouble' is the settings file being there but unreadable -- a typo in it,
    say.  That has to lock the door rather than open it: this app hands out the
    contents of the folders on this computer, and a machine reachable from the
    internet must not be opened up by a mistake in a settings file.
    """
    try:
        return st.secrets.get("password"), ""
    except Exception as err:
        if os.path.exists(SECRETS):
            return None, type(err).__name__
        return None, ""             # no settings at all: a fresh copy, no door


def gate() -> bool:
    secret, trouble = _password()
    if trouble:
        st.error("설정 파일(.streamlit/secrets.toml)을 읽을 수 없어 앱을 잠갔습니다. "
                 f"파일을 고친 뒤 앱을 다시 시작해 주세요. ({trouble})")
        return False
    if not secret:
        # Started as a door onto one computer only, there is nobody outside to
        # keep out, and a warning about it would be noise.
        if os.environ.get("PDF2MD_LOCAL_ONLY") != "1":
            st.warning("비밀번호가 설정되어 있지 않습니다. 이 앱은 이 컴퓨터의 폴더를 "
                       "그대로 열어 보여 주므로, 바깥에서 접속할 수 있게 해 두었다면 "
                       ".streamlit/secrets.toml 에 password 를 지금 넣어 주세요.")
        return True
    if st.session_state.get("unlocked"):
        return True

    tries = st.session_state.get("tries", 0)
    if tries >= 8:
        st.error("비밀번호를 너무 여러 번 틀렸습니다. 앱을 다시 시작해 주세요.")
        return False
    entered = st.text_input("비밀번호", type="password")
    if entered:
        # A plain == leaks how much of the password was right through how long
        # the comparison takes; this one always takes the same time.
        if hmac.compare_digest(entered, str(secret)):
            st.session_state["unlocked"] = True
            st.rerun()      # redraw without the password box still on screen
        st.session_state["tries"] = tries + 1
        time.sleep(1)       # a guess costs a second, so guessing in bulk is slow
        st.error("비밀번호가 다릅니다.")
    return False


st.title("PDF → Markdown")
st.caption("AI가 읽기 좋은 마크다운으로 변환합니다. 변환 후 빠진 글자가 없는지 자동으로 검사합니다.")

if not gate():
    st.stop()

if LOCAL:
    mode = st.radio("변환할 대상", ["폴더 통째로", "파일 골라서 올리기"],
                    horizontal=True, key="mode")
else:
    mode = "파일 골라서 올리기"
    st.info("파일을 올려서 변환하고 결과를 내려받는 방식입니다. "
            "폴더째 변환은 PDF가 있는 컴퓨터에서 직접 실행할 때만 됩니다.")

files: list = []
source_label = ""

if mode == "폴더 통째로":
    col_a, col_b = st.columns(2)
    source = folder_field(col_a, "원본이 든 폴더 (PDF 또는 저장한 웹페이지)",
                          "source", DEFAULT_SOURCE)
    out_dir = folder_field(col_b, "저장할 폴더", "out", DEFAULT_OUT)
    folder_browser("source", "원본이 든 폴더를 고르세요")
    folder_browser("out", "결과를 저장할 폴더를 고르세요")
    if not os.path.isdir(source):
        st.warning("폴더를 찾을 수 없습니다. 경로를 확인해 주세요.")
    else:
        files = find_sources(source)
        if files:
            kind = "웹페이지" if files[0].lower().endswith((".html", ".htm")) else "PDF"
            source_label = f"{kind} {len(files)}개를 찾았습니다."
        else:
            st.warning("이 폴더에 변환할 파일이 없습니다.")
else:
    uploads = st.file_uploader("파일을 고르세요 (PDF 또는 저장한 웹페이지, 여러 개 가능)",
                               type=["pdf", "html", "htm"],
                               accept_multiple_files=True)
    out_dir = None
    if LOCAL:
        out_dir = folder_field(st, "저장할 폴더 (내 컴퓨터에 바로 저장할 때만 사용)",
                               "out", DEFAULT_OUT)
        folder_browser("out", "결과를 저장할 폴더를 고르세요")
    if uploads:
        # Uploads arrive as bytes; the converter reads from disk, so park them
        # in a scratch folder that lives as long as the page session.
        scratch = st.session_state.setdefault(
            "scratch", tempfile.mkdtemp(prefix="pdf2md-"))
        files = []
        for index, upload in enumerate(uploads):
            name = scratch_name(upload.name, index)
            if not name:
                st.warning("변환할 수 없는 파일이라 건너뛰었습니다: " + upload.name)
                continue
            path = os.path.join(scratch, name)
            with open(path, "wb") as fh:
                fh.write(upload.getbuffer())
            files.append(path)
        source_label = f"파일 {len(files)}개를 올렸습니다."

if source_label:
    st.caption(source_label)

if files and st.button("변환하기", type="primary"):
    with st.spinner("변환 중…"):
        st.session_state["results"] = convert_many(files, write=False)

results = st.session_state.get("results")
if results:
    lost_total = sum(sum(r.lost.values()) for r in results if r.lost)
    ok = sum(1 for r in results if r.ok)

    m1, m2, m3 = st.columns(3)
    m1.metric("문서", len(results))
    m2.metric("정상", ok)
    m3.metric("빠진 단어", lost_total)

    unknown = [r for r in results if r.profile == "generic"]
    if unknown:
        st.warning(f"{len(unknown)}개 파일이 알려진 형식이 아닙니다. "
                   "기본 규칙으로 변환했으니 결과를 확인해 주세요.")

    st.subheader("결과")
    for r in results:
        lost = sum(r.lost.values()) if r.lost else 0
        icon = "🔴" if lost else ("🟡" if r.issues or r.warnings else "🟢")
        with st.expander(f"{icon}  {r.name}  ·  {r.title or '(제목 없음)'}"):
            if lost:
                st.error(f"원본에 있는 단어 {lost}개가 빠졌습니다: "
                         + ", ".join(list(r.lost)[:12]))
            for note in r.issues:
                st.warning(note)
            for note in r.warnings:
                st.info(note)
            st.download_button("이 파일만 내려받기", r.markdown, file_name=r.name,
                               mime="text/markdown", key="dl-" + r.name)
            left, right = st.columns(2)
            left.caption("미리보기")
            left.markdown(r.markdown[:4000])
            right.caption("마크다운 원문")
            right.code(r.markdown[:4000], language="markdown")

    missing = missing_references(results)
    if missing:
        with st.expander(f"참조되지만 함께 변환하지 않은 문서 {len(missing)}개"):
            st.write("본문이 인용하지만 이번에 변환한 목록에 없는 절입니다. "
                     "링크를 따라가면 원문 사이트로 나갑니다.")
            st.code(", ".join("§ %d" % n for n in missing))

    st.subheader("저장")
    if LOCAL:
        col_save, col_zip = st.columns(2)
        if col_save.button("이 컴퓨터의 폴더에 저장", type="primary"):
            written = save(results, out_dir)
            st.success(f"{len(written)}개 파일을 저장했습니다 → {out_dir}")
    else:
        col_zip = st.container()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            zf.writestr(r.name, r.markdown)
        zf.writestr("index.md", build_index(results))
    col_zip.download_button("전부 ZIP으로 내려받기", buffer.getvalue(),
                            file_name="pdf2md.zip", mime="application/zip")
