# app.py
# -----------------------------------------------------------------------------
# 엔트리: 접속 시 landing-page로 넘겨주고, 공통 사이드바(render_sidebar) 제공
# 기존 라디오로 페이지 전환하던 코드는 제거(동적 기록 버튼과 충돌하므로)
# -----------------------------------------------------------------------------
import streamlit as st
from utils import render_sidebar

st.set_page_config(page_title="LLM PDF 분석 실험", layout="wide")
render_sidebar()

st.markdown("# 홈으로 이동 중…")
try:
    st.switch_page("landing-page.py")
except Exception:
    st.info("좌측 사이드바의 'landing-page'를 클릭하세요.")
