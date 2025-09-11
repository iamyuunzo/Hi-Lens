# pages/landing-page.py
# -----------------------------------------------------------------------------
# 홈: 분석 타이틀 + 여러 PDF 업로드 → '분석하기' 누르면
#   1) 세션에 분석 레코드 생성
#   2) compare-page(단일 템플릿)로 이동하되 ?aid=<생성ID> 로 라우팅
# -----------------------------------------------------------------------------
import streamlit as st
from utils import render_sidebar, create_analysis, goto_compare, extract_text_from_pdf

st.set_page_config(page_title="랜딩페이지 — PDF 업로드 & 기록", layout="wide")
render_sidebar()

st.markdown("## 📂 랜딩페이지 — PDF 업로드 & 기록")
st.caption("한 번에 여러 PDF를 올려 하나의 '분석'으로 관리합니다.")

title = st.text_input("분석 타이틀", placeholder="예) 2025-09-11 센서 논문 비교")

files = st.file_uploader(
    "PDF 여러 개 업로드",
    type=["pdf"],
    accept_multiple_files=True,
    help="파일당 200MB (데모).",
)

st.info("※ 실제 인덱싱/DB 업로드는 팀 인덱서에서 처리. 여긴 UI/라우팅만.", icon="ℹ️")

# 선택적: 첫 페이지 텍스트 미리보기
if files:
    st.markdown("#### 업로드 미리보기")
    for f in files:
        with st.expander(f"미리보기: {f.name}", expanded=False):
            try:
                preview = extract_text_from_pdf(f.read(), max_pages=1)
                st.text(preview or "(텍스트 없음)")
            except Exception as e:
                st.warning(f"미리보기 실패: {e}")

can_run = bool(files)
if st.button("분석하기", type="primary", disabled=not can_run):
    payload = [{"name": f.name, "bytes": f.getvalue()} for f in files]
    aid = create_analysis(title or "제목 없음", payload)
    goto_compare(aid)
