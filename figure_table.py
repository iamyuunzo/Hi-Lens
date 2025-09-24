# =========================
# figure_table.py
# (표/그림 요약: '데이터 기반' vs '시각추론' 태그)
# =========================
from __future__ import annotations
from typing import List, Dict, Any
from rag_core import Chunk, RetrievalResult, build_context_and_evidence, RAG_SYSTEM_PROMPT
import re

FIGURE_SUMMARY_PROMPT = """다음 맥락을 바탕으로 표/그림을 요약하세요.
- 수치가 명시된 경우만 수치를 인용하세요.
- 수치가 없다면 추세/특징만 간결히 말하세요.
- 외부 지식/추정 금지.

[맥락]
{context}

[출력 형식]
- 핵심 요점 3~5개 불릿
"""

def has_numeric_data(text: str) -> bool:
    """숫자/퍼센트 패턴이 있는지 간단히 판단."""
    return bool(re.search(r"\d{1,3}(\.\d+)?\s?%|\d{2,}", text))

def summarize_figure_or_table(
    llm_chat,
    retrieved_for_figure: List[RetrievalResult]
) -> Dict[str, Any]:
    """
    - 표/그림에 관련된 chunk(retrieval 결과)를 묶어서 요약
    - basis: 'data_based' if 숫자 존재 else 'vision_infer'
    """
    context, evidences = build_context_and_evidence(retrieved_for_figure)
    merged = " ".join([e["snippet"] for e in evidences])
    basis = "data_based" if has_numeric_data(merged) else "vision_infer"

    prompt = FIGURE_SUMMARY_PROMPT.format(context=context if context else "(컨텍스트 없음)")
    if not context:
        answer = "문서 근거가 부족합니다. 관련 페이지를 더 제공해야 합니다."
    else:
        answer = llm_chat(RAG_SYSTEM_PROMPT, prompt)

    return {
        "basis": basis,          # 'data_based' | 'vision_infer'
        "answer": answer,
        "evidences": evidences
    }
