# run_streamlit.py
# -*- coding: utf-8 -*-
"""
Windows에서 Streamlit 실행 시 소켓 바인딩 단계에서
[WinError 10014]가 뜨는 경우가 있어, 두 가지를 강제합니다.
  1) asyncio 이벤트 루프를 Proactor로 강제
  2) 서버 바인딩 주소를 127.0.0.1로 고정 (IPv4 루프백)
"""

import os
import sys
import asyncio
from streamlit.web import bootstrap

# ── 1) 이벤트 루프 정책(Proactor) 강제
if sys.platform.startswith("win") and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass  # 실패해도 계속 진행

# ── 2) 바인딩 주소/포트 설정 (환경변수로도 오버라이드 가능)
ADDR = os.environ.get("HPL_ADDR", "127.0.0.1")   # ← 여기서 0.0.0.0 대신 127.0.0.1
PORT = int(os.environ.get("HPL_PORT", "8501"))

# 추가 플래그는 여기서 제어
flags = {
    "server.headless": True,
    "server.address": ADDR,
    "server.port": PORT,
    # 보기 좋게 옵션 몇 가지
    "browser.gatherUsageStats": False,
    "client.toolbarMode": "minimal",
}

# 실행
bootstrap.run("app.py", is_hello=False, args=[], flag_options=flags)
