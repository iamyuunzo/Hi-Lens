# llm.py
# ==========================================
# Gemini LLM 모듈 (lazy init 버전)
# - Streamlit Cloud Secrets 우선 → 환경변수(os.getenv) 보조
# - import 시점에 RuntimeError 발생하지 않도록 개선
# ==========================================

import os
import streamlit as st
import google.generativeai as genai


# -----------------------------
# 🔑 API 키 가져오기
# -----------------------------
def _get_api_key():
    # 1) Streamlit Secrets
    key = None
    try:
        key = st.secrets.get("GEMINI_API_KEY", None)  # type: ignore
    except Exception:
        pass

    # 2) 환경변수
    if not key:
        key = os.getenv("GEMINI_API_KEY")

    return key


# -----------------------------
# ⚙️ Gemini 모델 가져오기
# -----------------------------
def _get_model(model_name: str = "gemini-1.5-flash"):
    api_key = _get_api_key()
    if not api_key:
        # Streamlit UI에서 에러 출력
        st.error(
            "❌ GEMINI_API_KEY가 설정되지 않았습니다.\n\n"
            "👉 Streamlit Cloud Settings → Secrets에\n"
            '   GEMINI_API_KEY = "발급받은_API_KEY"\n'
            "형식으로 저장했는지 확인하세요."
        )
        st.stop()

    # Gemini SDK 초기화
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


# -----------------------------
# Provider 이름 반환
# -----------------------------
def get_provider_name() -> str:
    return "GEMINI"


# -----------------------------
# 컨텍스트 기반 답변
# -----------------------------
def answer_with_context(query: str, context: str) -> str:
    """
    query: 사용자가 입력한 질문
    context: 문서/데이터에서 뽑아온 관련 문맥
    """
    model = _get_model()

    prompt = f"""
아래 문맥(context)을 참고하여 질문(query)에 한국어로 답변하세요.
- 문맥에 없는 내용은 "문맥에 정보가 없습니다"라고 답하세요.
- 숫자나 표는 핵심만 요약하세요.

[Context]
{context}

[Question]
{query}
"""

    try:
        response = model.generate_content(prompt)
        return getattr(response, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# -----------------------------
# 테이블 설명
# -----------------------------
def explain_tables(table_text: str) -> str:
    """
    table_text: PDF 등에서 추출된 테이블 문자열
    """
    model = _get_model()

    prompt = f"""
아래 표 데이터를 읽고, 다음 기준으로 설명하세요:
1) 표의 주제
2) 눈에 띄는 추세(증가/감소)
3) 중요한 수치 1~2개
4) 정책/의사결정 시사점

[Table]
{table_text}
"""

    try:
        response = model.generate_content(prompt)
        return getattr(response, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"
 