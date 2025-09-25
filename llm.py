# llm.py — 표/그림 컨텍스트 보강 + (신규) 그림 이미지 직접 요약 지원 (전체 코드)

from __future__ import annotations
import os
import io
from typing import Optional, List, Dict, Any, Union

import streamlit as st
import google.generativeai as genai

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

_DIAG_DONE = False


def _get_api_key() -> Optional[str]:
    global _DIAG_DONE
    key, source = None, None
    try:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            if name in st.secrets and st.secrets[name]:
                key = st.secrets[name]; source = f"st.secrets[{name}]"; break
    except Exception:
        pass
    if not key:
        for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVEAI_API_KEY"):
            v = os.getenv(name)
            if v: key, source = v, f"os.getenv('{name}')"; break
    if not _DIAG_DONE:
        st.toast(("✅ 키 감지 " + source) if key else "⚠️ 키 미감지", icon="✅" if key else "⚠️")
        _DIAG_DONE = True
    return key


def _get_model(model_name: str = "gemini-1.5-flash", system_instruction: Optional[str] = None):
    api_key = _get_api_key()
    if not api_key:
        st.error("❌ GEMINI_API_KEY가 없습니다."); st.stop()
    genai.configure(api_key=api_key)
    if system_instruction:
        return genai.GenerativeModel(model_name, system_instruction=system_instruction)
    return genai.GenerativeModel(model_name)


def get_provider_name() -> str:
    return "GEMINI"


SUMMARIZER_DEFAULT_SYSTEM = (
    "당신은 정책/보고서 전문 요약가입니다. 문서 밖 정보를 추가하지 말고 "
    "명확한 한국어로 핵심을 정리하세요."
)


def llm_chat(system_prompt: str, user_prompt: str, model_name: str = "gemini-1.5-flash") -> str:
    model = _get_model(model_name, system_instruction=system_prompt)
    try:
        resp = model.generate_content(user_prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


# -----------------------------------------------------------------------------  
# 🔧 수정: answer_with_context → 답변 형식 강화  
# -----------------------------------------------------------------------------
def answer_with_context(query: str, context: str, page_label: Optional[str] = None) -> str:
    model = _get_model()
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
        resp = model.generate_content(prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


def explain_tables(query: str, tables_ctxs: List[Dict[str, Any]]) -> str:
    model = _get_model()
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
        resp = model.generate_content(prompt)
        return getattr(resp, "text", "").strip() or "⚠️ 응답이 비어 있습니다."
    except Exception as e:
        return f"⚠️ LLM 호출 중 오류: {e}"


def _to_pil(image: Union[bytes, "PILImage.Image", Any]) -> Optional["PILImage.Image"]:
    if PILImage is None:
        return None
    try:
        if isinstance(image, PILImage.Image): return image
        if isinstance(image, (bytes, bytearray)): return PILImage.open(io.BytesIO(image))
        try:
            import numpy as np
            if isinstance(image, np.ndarray):
                if image.ndim == 2: return PILImage.fromarray(image)
                if image.ndim == 3: return PILImage.fromarray(image.astype("uint8"))
        except Exception:
            pass
    except Exception:
        return None
    return None


def explain_figure_image(query: str, image: Union[bytes, "PILImage.Image", Any], neighbor_text: str = "") -> str:
    pil = _to_pil(image)
    if pil is None:
        return answer_with_context(
            query,
            f"[이미지 미전달/로딩실패] 아래 본문만으로 답하세요.\n{(neighbor_text or '')[:1800]}",
            page_label=None,
        )
    system = (
        "당신은 데이터 시각화를 정확히 읽는 분석가입니다. "
        "그래프/차트의 제목/축/범례/단위를 해석하고, 핵심 추세·변화·비교만 간결히 설명하세요. "
        "수치는 중요한 것만, 과도한 나열 금지."
    )
    parts = [
        {"text": f"[질문]\n{query}\n\n[참고 본문]\n{(neighbor_text or '')[:1500]}"},
        pil,
    ]
    try:
        model = _get_model("gemini-1.5-flash", system_instruction=system)
        resp = model.generate_content(parts)
        txt = getattr(resp, "text", "").strip()
        return txt or "⚠️ 응답이 비어 있습니다."
    except Exception:
        return answer_with_context(
            query,
            f"[이미지 요약 실패: 멀티모달 호출 예외] 아래 본문만으로 답하세요.\n{(neighbor_text or '')[:1800]}",
            page_label=None,
        )
