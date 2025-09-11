# app.py
# ------------------------------------------------------------
# 멀티페이지 진입점. 사이드바에서 페이지 선택 → 해당 파일로 이동.
# Streamlit Cloud에서도 동일하게 동작.
# ------------------------------------------------------------
import streamlit as st

st.set_page_config(page_title="LLM PDF 분석 실험", layout="wide")

st.sidebar.title("📑 페이지 선택")
page = st.sidebar.radio("이동하기", ["랜딩페이지", "PDF 비교", "프롬프팅"])

# 멀티페이지 라우팅 (파일명/경로 주의)
if page == "랜딩페이지":
    st.switch_page("pages/1_랜딩.py")
elif page == "PDF 비교":
    st.switch_page("pages/2_비교.py")
elif page == "프롬프팅":
    st.switch_page("pages/3_프롬프팅.py")
