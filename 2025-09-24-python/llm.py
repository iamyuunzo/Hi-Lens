# llm.py — 최종본 (Gemini v0.5+ 호환)
# ------------------------------------------------------------
# - Lazy init: import 시점 RuntimeError 없음
# - 키 탐색: st.secrets 우선 → os.getenv 보조 (여러 키 이름 허용)
# - 진단: 키를 어디서 읽었는지 st.toast 1회 표시
# - Gemini 최신 SDK 규칙 반영:
#     * system 메시지는 contents에 넣지 말고 system_instruction로 전달
# - ui_pages.py/summarizer.py 시그니처 호환
# ------------------------------------------------------------
from __future__ import annotations
import os
from typing import Optional, List, Dict

import streamlit as st
import google.generativeai as genai

# 내부 진단 플래그
_DIAG_DONE = False


# ─────────────────────────────────────────────────────────────
# API 키 로딩 (Secrets → Env, 다양한 이름 허용)
# ─────────────────────────────────────────────────────────────
def _get_api_key() -> Optional[str]:
    global _DIAG_DONE
    key, source = None, None

    # 1) Streamlit Secrets
    try:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            if name in st.secrets and st.secrets[name]:
                key = st.secrets[name]  # type: ignore[index]
                source = f"st.secrets[{name}]"
                break
    except Exception:
        pass

    # 2) 환경변수
    if not key:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            v = os.getenv(name)
            if v:
                key = v
                source = f"os.getenv('{name}')"
                break

    if not _DIAG_DONE:
        st.toast(f"{'✅' if key else '⚠️'} Gemini API 키 감지"
                 + (f" ({source})" if key else ": Secrets/ENV 확인 필요"), icon="✅" if key else "⚠️")
        _DIAG_DONE = True

    return key


# ─────────────────────────────────────────────────────────────
# 모델 핸들 (system_instruction 지원)
# ─────────────────────────────────────────────────────────────
def _get_model(model_name: str = "gemini-1.5-flash", system_instruction: Optional[str] = None):
    api_key = _get_api_key()
    if not api_key:
        st.error(
            "❌ GEMINI_API_KEY가 설정되지 않았습니다.\n\n"
            "Cloud에서는 **Manage app → Settings → Secrets** 에 아래 형식으로 저장하세요:\n"
            '```toml\nGEMINI_API_KEY = "발급받은_API_KEY"\n```\n'
            "저장 후 **Restart** 하세요."
        )
        st.stop()

    genai.configure(api_key=api_key)
    try:
        if system_instruction:
            return genai.GenerativeModel(model_name, system_instruction=system_instruction)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        st.error(f"⚠️ Gemini 모델 초기화 오류: {e}")
        st.stop()


# ─────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────
def get_provider_name() -> str:
    return "GEMINI"


# summarizer.py 호환: 기본 system 프롬프트
SUMMARIZER_DEFAULT_SYSTEM = (
    "당신은 정책/보고서 전문 요약가입니다. "
    "문서 밖 정보는 추가하지 말고, 간결하고 명확하게 한국어로 작성하세요."
)

# summarizer.py 호환: 공용 채팅 함수
# ⚠️ 중요: system 메시지는 contents에 넣지 않고 system_instruction로 전달
def llm_chat(system_prompt: str, user_prompt: str, model_name: str = "gemini-1.5-flash") -> str:
    model = _get_model(model_name, system_instruction=system_prompt)
    try:
        resp = model.generate_content(user_prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# ui_pages.py 호환: page_label 인자 허용
def answer_with_context(query: str, context: str, page_label: Optional[str] = None) -> str:
    model = _get_model()
    page_note = f"(근거 p.{page_label})" if page_label else ""
    prompt = f"""
아래 문맥(context)을 참고하여 질문(query)에 한국어로 답하세요. {page_note}
- 문맥에 없는 내용은 "문맥에 정보가 없습니다"라고 답하세요.
- 숫자/표는 핵심만 간결히 요약하세요.

[Context]
{context}

[Question]
{query}
""".strip()
    try:
        resp = model.generate_content(prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# ui_pages.py 호환: 표/그림 컨텍스트 리스트 처리
def explain_tables(query: str, tables_ctxs: List[Dict]) -> str:
    model = _get_model()

    parts = []
    for t in tables_ctxs:
        md = (t.get("preview_md") or "").strip()
        ttl = (t.get("title") or "").strip()
        pno = t.get("page_label", "?")
        if md:
            parts.append(f"(p.{pno}) {ttl}\n{md}")
    ctx = "\n\n---\n\n".join(parts)[:8000] if parts else "표 미검출"

    prompt = f"""
다음은 문서에서 추출한 표(또는 그림) 미리보기입니다.
질문에 대해 **표에서 확인 가능한 범위 내에서만** 한국어로 답하세요.
- 표에 없는 내용은 추측 금지, "표에 정보가 없습니다"라고 답하기
- 핵심 포인트 3개 불릿

[질문]
{query}

[표 미리보기(요약 마크다운)]
{ctx}
""".strip()
    try:
        resp = model.generate_content(prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"
