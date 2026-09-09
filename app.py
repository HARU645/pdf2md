# -*- coding: utf-8 -*-
"""Local screen for pdf2md.

    streamlit run app.py

Two ways in.  A folder is typed as a path, because a browser upload hands over
the file contents without the path and a folder job needs to know where it came
from.  Individual files come in as uploads, which suits picking a few at a time.
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile

import streamlit as st

from pdf2md.convert import (build_index, convert_many, find_pdfs,
                            missing_references, save)

st.set_page_config(page_title="PDF → Markdown", page_icon="📄", layout="wide")

def _setting(name, fallback=""):
    """Read a local setting.  Kept out of the repository so the code carries no
    one machine's folder layout; absent, the field simply starts empty."""
    try:
        return st.secrets.get(name, fallback)
    except Exception:
        return os.environ.get("PDF2MD_" + name.upper(), fallback)


DEFAULT_SOURCE = _setting("source_folder")
DEFAULT_OUT = _setting("output_folder", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output"))

# Reading and writing folders only makes sense on the machine that holds them.
# Hosted anywhere else the app is upload-in, download-out, and says so.
# Hosts run Linux; set PDF2MD_HOSTED=1 to try that shape here.
LOCAL = os.name == "nt" and os.environ.get("PDF2MD_HOSTED") != "1"


def gate() -> bool:
    """Ask for a password when one is configured; absent, the app is open."""
    try:
        secret = st.secrets.get("password")
    except Exception:
        secret = None
    if not secret or st.session_state.get("unlocked"):
        return True
    entered = st.text_input("비밀번호", type="password")
    if entered and entered == secret:
        st.session_state["unlocked"] = True
        st.rerun()          # redraw without the password box still on screen
    if entered:
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
    source = col_a.text_input("PDF가 든 폴더",
                              value=st.session_state.get("source", DEFAULT_SOURCE))
    st.session_state["source"] = source
    out_dir = col_b.text_input("저장할 폴더",
                               value=st.session_state.get("out", DEFAULT_OUT))
    st.session_state["out"] = out_dir
    if not os.path.isdir(source):
        st.warning("폴더를 찾을 수 없습니다. 경로를 확인해 주세요.")
    else:
        files = find_pdfs(source)
        if files:
            source_label = f"PDF {len(files)}개를 찾았습니다."
        else:
            st.warning("이 폴더에 PDF가 없습니다.")
else:
    uploads = st.file_uploader("PDF 파일을 고르세요 (여러 개 가능)", type="pdf",
                               accept_multiple_files=True)
    out_dir = None
    if LOCAL:
        out_dir = st.text_input("저장할 폴더 (내 컴퓨터에 바로 저장할 때만 사용)",
                                value=st.session_state.get("out", DEFAULT_OUT))
        st.session_state["out"] = out_dir
    if uploads:
        # Uploads arrive as bytes; the converter reads from disk, so park them
        # in a scratch folder that lives as long as the page session.
        scratch = st.session_state.setdefault(
            "scratch", tempfile.mkdtemp(prefix="pdf2md-"))
        files = []
        for upload in uploads:
            path = os.path.join(scratch, upload.name)
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
