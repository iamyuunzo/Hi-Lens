# llm.py — GPT(OpenAI) 전용 버전
from __future__ import annotations
import os
from typing import Optional, List, Dict, Any, Union

import streamlit as st
from openai import OpenAI

try:
    from PIL import Image as PILImage
except Exception:
    PILImage = None

__all__ = [
    "get_provider_name",
    "SUMMARIZER_DEFAULT_SYSTEM",
    "llm_chat",
    "answer_with_context",
    "explain_tables",
    "explain_figure_image",
]

# -------------------------------------------------------------------
# 🔑 OpenAI API 키 가져오기
# -------------------------------------------------------------------
def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("❌ OPENAI_API_KEY가 없습니다."); st.stop()
    return OpenAI(api_key=api_key)


def get_provider_name() -> str:
    return "OPENAI"


SUMMARIZER_DEFAULT_SYSTEM = (
    "당신은 정책/보고서 전문 요약가입니다. 문서 밖 정보를 추가하지 말고 "
    "명확한 한국어로 핵심을 정리하세요."
)

# -------------------------------------------------------------------
# 🔧 공통 LLM 호출 함수
# -------------------------------------------------------------------
def llm_chat(system_prompt: str, user_prompt: str, model_name: str = "gpt-4o-mini") -> str:
    client = _get_openai_client()
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# -------------------------------------------------------------------
# 📄 문맥 기반 답변
# -------------------------------------------------------------------
def answer_with_context(query: str, context: str, page_label: Optional[str] = None,
                        model_name: str = "gpt-4o-mini") -> str:
    client = _get_openai_client()
    page_note = f"(근거 p.{page_label})" if page_label else ""
    prompt = f"""
아래 문맥을 바탕으로 질문에 답하세요. {page_note}

[답변 규칙]
- 답변은 3~4문장 정도의 단락형 요약으로 작성
- 번호 매기기, 불릿 사용 금지
- 문맥에 없는 내용은 "문맥에 정보가 없습니다"라고 답하세요
- 불필요한 <br>, HTML, 표는 금지

[문맥]
{context}

[질문]
{query}
""".strip()
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SUMMARIZER_DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# -------------------------------------------------------------------
# 📊 표 설명
# -------------------------------------------------------------------
def explain_tables(query: str, tables_ctxs: List[Dict[str, Any]],
                   model_name: str = "gpt-4o-mini") -> str:
    client = _get_openai_client()
    parts = []
    for t in tables_ctxs:
        title = (t.get("title") or "").strip()
        pno   = t.get("page_label", "?")
        prev  = (t.get("preview_md") or "").strip()
        nb    = (t.get("neighbor_text") or "").strip()
        sparse = len(prev) < 40 or prev.count("|") <= 2
        ctx_block = f"(p.{pno}) {title}\n"
        if sparse and nb:
            ctx_block += f"[표 미리보기 추정이 빈약하여 본문 보강]\n{nb}\n"
        ctx_block += (prev if prev else "")
        parts.append(ctx_block)

    ctx = ("\n\n---\n\n".join(parts))[:7800] if parts else "표 미검출"
    prompt = f"""
당신은 표/그림을 설명하는 분석가입니다.
- [컨텍스트] 범위 내에서만 답하세요.
- 답변은 문장 단위로 간결히.
- 추세·비교·핵심 포인트만 설명하세요.

[질문]
{query}

[컨텍스트]
{ctx}
""".strip()

    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SUMMARIZER_DEFAULT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# -------------------------------------------------------------------
# 🖼️ 그림 요약
# -------------------------------------------------------------------
def explain_figure_image(query: str, image: Union[bytes, "PILImage.Image", Any],
                         neighbor_text: str = "", model_name: str = "gpt-4o-mini") -> str:
    client = _get_openai_client()
    prompt = f"""
[질문]
{query}

[참고 본문]
{(neighbor_text or '')[:1500]}
""".strip()
    try:
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "당신은 데이터 시각화를 정확히 읽는 분석가입니다."},
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return answer_with_context(
            query,
            f"[이미지 요약 실패: 멀티모달 호출 예외] 아래 본문만으로 답하세요.\n{(neighbor_text or '')[:1800]}",
            page_label=None,
        )
