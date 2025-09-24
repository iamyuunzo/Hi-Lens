# -*- coding: utf-8 -*-
from __future__ import annotations  # ✅ 항상 최상단에 두세요

# ==============================================================
# app.py (최종)
# - Streamlit Cloud에서 st.secrets에 저장된 GEMINI_API_KEY를
#   환경변수로도 복사해 두는 "브리지" 추가 → 어떤 경로로든 llm.py가 키를 100% 찾게 함
# - .env는 로컬에서만 보장되므로 Cloud에서는 st.secrets가 정답!
# ==============================================================

import os
import streamlit as st

# ✅ Streamlit 페이지 설정 (가장 먼저 호출)
st.set_page_config(page_title="Hi-Lens", page_icon="📄", layout="wide")

# ✅ .env 로드 (로컬 실행 시에만 의미 있음 / Cloud에선 무시될 수 있음)
from dotenv import load_dotenv
load_dotenv(override=True)

# 🔑 [핫픽스] st.secrets → 환경변수 브리지
#     - llm.py는 st.secrets 우선, 없으면 os.getenv 순으로 찾음
#     - 혹시 모를 환경 차이를 없애기 위해 여기서 ENV로도 복사해 둔다.
try:
    # 표준 키 이름
    if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    # 실수 대비: 다른 이름으로 저장했을 수도 있음
    elif "GOOGLE_API_KEY" in st.secrets and st.secrets["GOOGLE_API_KEY"]:
        os.environ["GEMINI_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    elif "GOOGLE_GENERATIVEAI_API_KEY" in st.secrets and st.secrets["GOOGLE_GENERATIVEAI_API_KEY"]:
        os.environ["GEMINI_API_KEY"] = st.secrets["GOOGLE_GENERATIVEAI_API_KEY"]
except Exception:
    # secrets 접근이 불가한 환경(일부 테스트 컨텍스트)에서는 조용히 패스
    pass

# 🚪 UI 페이지 import (이제부터 LLM이 키를 확실히 읽을 수 있음)
from ui_pages import landing_page, loading_page, analysis_page

# 🔀 라우팅 초기값
st.session_state.setdefault("route", "landing")
route = st.session_state.get("route", "landing")

# 🔀 라우팅 처리
if route == "landing":
    landing_page()
elif route == "loading":
    loading_page()
elif route == "analysis":
    analysis_page()
else:
    st.session_state["route"] = "landing"
    st.experimental_rerun()
