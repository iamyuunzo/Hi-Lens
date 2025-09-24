# llm.py — 최종본 (Streamlit Cloud 호환 + 시그니처 맞춤 + 진단)
# ------------------------------------------------------------
# - Lazy init: import 시점 RuntimeError 없음
# - Secrets 우선 → ENV 보조 (여러 이름 허용)
# - 어디서 키를 읽었는지 st.toast로 1회 진단
# - ui_pages.py 호출 시그니처에 맞춤:
#     answer_with_context(query, context, page_label=None)
#     explain_tables(query, tables_ctxs: List[Dict])
# - summarizer.py 호환: llm_chat, SUMMARIZER_DEFAULT_SYSTEM 포함
# ------------------------------------------------------------
import os
from typing import Optional, List, Dict

import streamlit as st
import google.generativeai as genai

# ─────────────────────────────────────────────────────────────
# 내부 상태
# ─────────────────────────────────────────────────────────────
_DIAG_DONE = False   # 키 소스 진단 토스트 1회만 띄우기


# ─────────────────────────────────────────────────────────────
# GEMINI API KEY 읽기 (Secrets → Env, 여러 이름 허용)
# ─────────────────────────────────────────────────────────────
def _get_api_key() -> Optional[str]:
    global _DIAG_DONE
    key = None
    source = None

    # 1) Streamlit Secrets
    try:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            if name in st.secrets:
                key = st.secrets.get(name)  # type: ignore[index]
                if key:
                    source = f"st.secrets[{name}]"
                    break
    except Exception:
        pass  # secrets 접근 불가한 환경(테스트) 대비

    # 2) 환경변수 (.env 포함 — app.py에서 load_dotenv 호출함)
    if not key:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            key = os.getenv(name)
            if key:
                source = f"os.getenv('{name}')"
                break

    # 진단 토스트(1회)
    if not _DIAG_DONE:
        if key:
            st.toast(f"✅ Gemini API 키 감지됨 ({source})", icon="✅")
        else:
            st.toast("❌ Gemini API 키를 찾지 못했습니다. Secrets/ENV 확인 필요", icon="⚠️")
        _DIAG_DONE = True

    return key


# ─────────────────────────────────────────────────────────────
# 모델 핸들
# ─────────────────────────────────────────────────────────────
def _get_model(model_name: str = "gemini-1.5-flash"):
    api_key = _get_api_key()
    if not api_key:
        st.error(
            "❌ GEMINI_API_KEY가 설정되지 않았습니다.\n\n"
            "👉 Streamlit Cloud: **Manage app → Settings → Secrets** 에 아래 형식으로 저장하세요.\n"
            '```toml\nGEMINI_API_KEY = "발급받은_API_KEY"\n```\n'
            "저장 후 **Restart** 하세요. (.env만으로는 Cloud에서 보장되지 않습니다)"
        )
        st.stop()

    genai.configure(api_key=api_key)
    try:
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
def llm_chat(system_prompt: str, user_prompt: str, model_name: str = "gemini-1.5-flash") -> str:
    model = _get_model(model_name)
    try:
        resp = model.generate_content(
            [
                {"role": "system", "parts": [system_prompt]},
                {"role": "user", "parts": [user_prompt]},
            ]
        )
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# ui_pages.py 호환: page_label 인자 허용(사용은 선택)
def answer_with_context(query: str, context: str, page_label: Optional[str] = None) -> str:
    """
    query: 사용자 질문
    context: 문서/발췌 텍스트
    page_label: (옵션) 근거 페이지 표기용
    """
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


# ui_pages.py 호환: 표/그림 RAG 컨텍스트 리스트 처리
def explain_tables(query: str, tables_ctxs: List[Dict]) -> str:
    """
    query: 사용자의 질문(표/그림 관련)
    tables_ctxs: [{ preview_md, page_label, title }, ...] 형태 권장
    """
    model = _get_model()

    # 컨텍스트 조립
    parts = []
    for i, t in enumerate(tables_ctxs, 1):
        md = (t.get("preview_md") or "").strip()
        ttl = (t.get("title") or "").strip()
        pno = t.get("page_label", "?")
        if not md:
            continue
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
