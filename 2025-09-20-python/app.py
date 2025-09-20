# app.py
# -*- coding: utf-8 -*-
"""
Hi-PolicyLens - Streamlit 라우터
- route: landing -> loading -> analysis
- ui_pages의 함수들을 호출하여 화면을 구성
"""

from __future__ import annotations
import streamlit as st

from ui_pages import (
    landing_page,
    loading_page,
    analysis_page,
)

# 페이지 기본 설정
st.set_page_config(
    page_title="Hi-PolicyLens",
    page_icon="📄",
    layout="wide",
)

# 세션 상태 초기화
if "route" not in st.session_state:
    st.session_state["route"] = "landing"
if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None
if "pdf_name" not in st.session_state:
    st.session_state["pdf_name"] = None
if "chunks" not in st.session_state:
    st.session_state["chunks"] = None

# 라우팅
route = st.session_state.get("route", "landing")

if route == "landing":
    landing_page()
elif route == "loading":
    loading_page()
elif route == "analysis":
    analysis_page()
else:
    # fallback
    st.session_state["route"] = "landing"
    st.experimental_rerun()
