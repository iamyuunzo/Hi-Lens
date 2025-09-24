# app.py
# -*- coding: utf-8 -*-
"""
Hi-PolicyLens - Streamlit 라우터
- route: landing -> loading -> analysis
"""
from __future__ import annotations
import streamlit as st
from ui_pages import landing_page, loading_page, analysis_page

st.set_page_config(page_title="Hi-PolicyLens", page_icon="📄", layout="wide")

st.session_state.setdefault("route", "landing")
route = st.session_state.get("route", "landing")

if route == "landing":
    landing_page()
elif route == "loading":
    loading_page()
elif route == "analysis":
    analysis_page()
else:
    st.session_state["route"] = "landing"; st.experimental_rerun()
