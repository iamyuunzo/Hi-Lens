# -*- coding: utf-8 -*-
from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv
from ui_pages import landing_page, loading_page, analysis_page

# ✅ Streamlit 페이지 설정
st.set_page_config(page_title="Hi-Lens", page_icon="📄", layout="wide")

# ✅ .env 로드 (로컬 실행 시)
load_dotenv(override=True)

# 🚪 UI 페이지 라우팅
st.session_state.setdefault("route", "landing")
route = st.session_state.get("route", "landing")

if route == "landing":
    landing_page()
elif route == "loading":
    loading_page()
elif route == "analysis":
    analysis_page()
else:
    st.session_state["route"] = "landing"
    st.experimental_rerun()
