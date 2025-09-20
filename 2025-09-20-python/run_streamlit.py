# run_streamlit.py
# -*- coding: utf-8 -*-
"""
Windows에서 streamlit run 시 asyncio가 socket.socketpair()를 쓰는 경로를 타면
[WinError 10014] 같은 오류가 날 수 있어요.
→ 앱 실행 전에 이벤트 루프 정책을 Proactor로 강제해 우회합니다.
"""

import os
import sys
import asyncio

# 1) Windows에서 Proactor 이벤트 루프 정책 강제
if sys.platform.startswith("win") and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        # 정책 설정 실패해도 계속 진행(다음 단계에서 동일 오류 시 환경 이슈 가능)
        pass

# 2) Streamlit 서버를 같은 프로세스에서 직접 부팅
from streamlit.web import bootstrap

# CLI 플래그를 넣고 싶으면 아래 args에 추가 가능 (예: "--server.headless=true")
args = []
bootstrap.run("app.py", is_hello=False, args=args, flag_options={"server.headless": True})
