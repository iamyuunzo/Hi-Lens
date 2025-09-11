# app.py
# ------------------------------------------------------------
# 멀티페이지 진입점. 사이드바에서 선택 → 해당 파일로 이동.
# (파일명은 pages/ 아래 실제 파일명과 반드시 일치)
# ------------------------------------------------------------
import streamlit as st

st.set_page_config(page_title="LLM PDF 분석 실험", layout="wide")

st.sidebar.title("📑 페이지 선택")
page = st.sidebar.radio("이동하기", ["랜딩페이지", "PDF 비교", "프롬프팅"])

if page == "랜딩페이지":
    st.switch_page("pages/landing-page.py")       # ✅ 파일명 일치
elif page == "PDF 비교":
    st.switch_page("pages/compare-page.py")       # ✅ 파일명 일치
elif page == "프롬프팅":
    st.switch_page("pages/promptying-page.py")    # ✅ 파일명 일치(오탈자 그대로 사용)
