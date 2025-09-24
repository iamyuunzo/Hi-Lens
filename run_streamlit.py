# -*- coding: utf-8 -*-
"""
Windows 바인딩/루프 이슈 회피 + 안정적인 포트 확보
"""
import os, sys, socket, asyncio
from contextlib import closing
from streamlit.web import bootstrap

if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    try: asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception: pass

def env_str(name: str, default: str) -> str:
    val = (os.environ.get(name) or default).strip()
    return val if val else default

def env_int(name: str, default: int) -> int:
    try: return int(os.environ.get(name, default))
    except Exception: return default

ADDR = env_str("HPL_ADDR", "127.0.0.1")
PORT = env_int("HPL_PORT", 8501)

def find_free_port(start_port: int, host: str) -> int:
    for p in range(start_port, start_port + 10):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try: s.bind((host, p)); return p
            except OSError: continue
    return start_port

PORT = find_free_port(PORT, ADDR)
print(f"[Hi-Lens] http://{ADDR}:{PORT}")
bootstrap.run("app.py", is_hello=False, args=[], flag_options={
    "server.headless": True,
    "server.address": ADDR,
    "server.port": PORT,
    "server.enableCORS": True,
    "server.enableXsrfProtection": True,
    "browser.gatherUsageStats": False,
    "client.toolbarMode": "minimal",
})
