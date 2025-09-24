# -*- coding: utf-8 -*-
from __future__ import annotations   # ✅ Python 문법상 항상 최상단

import streamlit as st

# ✅ Streamlit 설정은 반드시 첫 번째 Streamlit 명령으로 실행
st.set_page_config(
    page_title="Hi-Lens",
    page_icon="📄",
    layout="wide"
)

# ✅ .env 로드 (LLM OFF 방지)
from dotenv import load_dotenv
load_dotenv(override=True)

from ui_pages import landing_page, loading_page, analysis_page

# 라우팅 초기값 세팅
st.session_state.setdefault("route", "landing")
route = st.session_state.get("route", "landing")

# 라우팅 처리
if route == "landing":
    landing_page()
elif route == "loading":
    loading_page()
elif route == "analysis":
    analysis_page()
else:
    st.session_state["route"] = "landing"
    st.experimental_rerun()
