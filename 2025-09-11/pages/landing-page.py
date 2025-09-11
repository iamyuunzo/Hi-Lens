# pages/1_랜딩.py
# ------------------------------------------------------------
# - PDF 여러 개 업로드
# - 사이드바에 업로드 기록
# - (옵션) 첫 페이지 텍스트 프리뷰
# ------------------------------------------------------------
import streamlit as st
from utils import extract_text_from_pdf

st.title("📂 랜딩페이지 — PDF 업로드 & 기록")

files = st.file_uploader("PDF 여러 개 업로드", type=["pdf"], accept_multiple_files=True)

# 업로드 기록 세션상태
if "uploaded_names" not in st.session_state:
    st.session_state.uploaded_names = []

if files:
    for f in files:
        if f.name not in st.session_state.uploaded_names:
            st.session_state.uploaded_names.append(f.name)
        with st.expander(f"미리보기: {f.name}", expanded=False):
            try:
                preview = extract_text_from_pdf(f.read(), max_pages=1)
                st.text(preview or "(텍스트 없음)")
            except Exception as e:
                st.warning(f"미리보기 실패: {e}")

st.sidebar.subheader("📜 업로드 기록")
for n in st.session_state.uploaded_names:
    st.sidebar.write(f"- {n}")

st.info("※ 실제 인덱싱/DB 업로드는 팀의 인덱서에서 처리됩니다. 여기선 UI만 제공합니다.")
