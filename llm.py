# llm.py (Gemini 전용) - 배포 형식
# -*- coding: utf-8 -*-
# ==========================================
# LLM 관련 기능 모듈
# - Gemini API 초기화
# - 질문 응답(answer_with_context)
# - Provider 이름 반환(get_provider_name)
# - 테이블 설명(explain_tables)
# ==========================================

import os
import streamlit as st
import google.generativeai as genai


# ==============================
# 🔑 GEMINI API KEY 불러오기
# ==============================
# 1. Streamlit Cloud에서는 st.secrets 사용
# 2. 로컬 실행 시 os.getenv(.env, 환경변수)
API_KEY = st.secrets.get("GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "❌ GEMINI_API_KEY가 설정되지 않았습니다.\n"
        "👉 해결 방법:\n"
        "   1) 로컬 실행 시: .env 파일 또는 환경변수에 GEMINI_API_KEY 등록\n"
        "   2) Streamlit Cloud 배포 시: Settings → Secrets에\n"
        '      GEMINI_API_KEY = "발급받은_실제_API_KEY"\n'
    )

# ✅ Google Gemini API 초기화
genai.configure(api_key=API_KEY)


# ==============================
# Provider 이름 반환
# ==============================
def get_provider_name() -> str:
    return "GEMINI"


# ==============================
# 컨텍스트 기반 답변 함수
# ==============================
def answer_with_context(query: str, context: str) -> str:
    """
    query: 사용자가 입력한 질문
    context: 문서/데이터에서 뽑아온 관련 문맥

    return: Gemini 응답 텍스트
    """
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Gemini에 전달할 프롬프트
    prompt = f"""
    아래 문맥(context)을 참고하여 질문(query)에 답변하세요.

    [Context]
    {context}

    [Question]
    {query}
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ 오류 발생: {e}"


# ==============================
# 테이블 설명 함수
# ==============================
def explain_tables(table_text: str) -> str:
    """
    table_text: PDF 등에서 추출된 테이블 문자열

    return: 테이블 의미를 사람이 이해할 수 있게 설명
    """
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
    아래의 표 데이터를 바탕으로 표의 의미와 주요 특징을 설명해 주세요.

    [Table]
    {table_text}
    """

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ 오류 발생: {e}"



# # llm.py (Gemini 전용) - env 형식
# # -*- coding: utf-8 -*-
# """
# LLM (Gemini 전용)
# - 표 요약 / 본문 발췌 요약 / 일반 chat 헬퍼
# - 환각 방지: 미리보기/발췌 + 페이지번호만 근거로 사용
# """

# from __future__ import annotations
# import os
# from typing import Dict, List
# from dotenv import load_dotenv
# import google.generativeai as genai

# # .env 로드
# load_dotenv(override=True)

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
# if not GEMINI_API_KEY:
#     raise RuntimeError("❌ GEMINI_API_KEY가 설정되지 않았습니다. Google AI Studio에서 발급 후 .env에 GEMINI_API_KEY=... 로 넣어주세요.")

# # Gemini 클라이언트 초기화
# genai.configure(api_key=GEMINI_API_KEY)

# # 모델은 경량·속도 우선. 필요하면 pro로 교체 가능.
# DEFAULT_MODEL = "gemini-1.5-flash-latest"

# def get_provider_name() -> str:
#     return "GEMINI"

# # ───────────────────────────────────────────────
# # (A) 표 요약
# # ───────────────────────────────────────────────
# EXPLAIN_TABLES_PROMPT = """
# 당신은 '정책 PDF 표 분석 보조원'입니다. 반드시 규칙을 지키세요.

# [규칙]
# 1) 오직 '제공된 표 미리보기(Markdown)'와 '페이지 번호'만 근거로 사용합니다.
# 2) 표에 없는 수치/항목/해석을 만들어내지 않습니다(추측 금지).
# 3) 출력은 최대 5줄 bullet. 각 bullet은 '무슨 표인지'와 '핵심 변화/특징'을 짧게 기술합니다.
# 4) 가능하면 bullet 끝에 (p.번호)로 근거 페이지를 표기합니다.
# """.strip()

# def explain_tables(user_query: str, table_contexts: List[Dict]) -> str:
#     """
#     여러 표 미리보기(Markdown)와 페이지 라벨을 받아 bullet 요약을 생성.
#     - table_contexts: [{"preview_md": str, "page_label": int, "title": str}, ...]
#     """
#     parts = []
#     for i, t in enumerate(table_contexts, 1):
#         title = (t.get("title") or "").strip()
#         head = f"[표{i}] p.{t.get('page_label','?')}" + (f" · {title}" if title else "")
#         body = (t.get("preview_md") or "").strip()[:3000]
#         if not body:
#             continue
#         parts.append(head + "\n" + body)
#     ctx = "\n\n".join(parts) if parts else "(표 미리보기가 비어있음)"

#     try:
#         model = genai.GenerativeModel(DEFAULT_MODEL)
#         res = model.generate_content(
#             f"{EXPLAIN_TABLES_PROMPT}\n\n사용자 질문: {user_query}\n\n[표 미리보기]\n{ctx}"
#         )
#         out = (res.text or "").strip()
#         lines = [ln for ln in out.splitlines() if ln.strip()]
#         return "\n".join(lines[:8]) if lines else "표 미리보기가 부족하여 요약을 생성할 수 없습니다."
#     except Exception as e:
#         return f"❌ Gemini 호출 실패: {e}"

# # ───────────────────────────────────────────────
# # (B) 본문 발췌 요약
# # ───────────────────────────────────────────────
# ANSWER_WITH_CONTEXT_PROMPT = """
# 당신은 '원문 근거 요약자'입니다. 규칙:
# - '제공된 본문 발췌'에서만 답하세요(추측 금지).
# - 3~5줄 bullet로 간결 요약, 마지막 줄에 (p.번호)를 붙이세요.
# """.strip()

# def answer_with_context(user_query: str, context: str, page_label: str|int = "?") -> str:
#     """간단한 발췌 요약(대화 탭 상단 · 폴백에도 사용)."""
#     if not context.strip():
#         return "근거 발췌가 부족합니다."
#     try:
#         model = genai.GenerativeModel(DEFAULT_MODEL)
#         res = model.generate_content(
#             f"{ANSWER_WITH_CONTEXT_PROMPT}\n\n질문: {user_query}\n\n[본문 발췌]\n{context}\n(p.{page_label})"
#         )
#         return (res.text or "").strip()
#     except Exception as e:
#         return f"❌ Gemini 호출 실패: {e}"

# # ───────────────────────────────────────────────
# # (C) 일반 chat 헬퍼 (계층 요약 등에서 재사용)
# # ───────────────────────────────────────────────
# # 요약 전용 system 프롬프트: 메타데이터(제목/저자/발간정보/초록) 배제
# SUMMARIZER_DEFAULT_SYSTEM = """
# 당신은 정책 문서를 요약하는 분석가입니다.
# - '문서 메타데이터(제목/저자/발행기관/초록/표지/발간정보)'는 요약 대상에서 제외합니다.
# - 본문에 나타난 '정책 변화/시장 동향/핵심 수치/시사점'만 요약합니다.
# - 문서 바깥 지식/추측 금지.
# """.strip()

# def llm_chat(system: str, user: str) -> str:
#     """
#     임의의 system+user 프롬프트를 호출하는 간단한 래퍼.
#     - summarizer.py 등에서 공용으로 사용.
#     """
#     try:
#         model = genai.GenerativeModel(DEFAULT_MODEL)
#         res = model.generate_content(f"{system}\n\n{user}")
#         return (res.text or "").strip()
#     except Exception as e:
#         return f"❌ Gemini 호출 실패: {e}"
