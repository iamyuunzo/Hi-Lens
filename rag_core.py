# =========================
# rag_core.py
# =========================
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Callable, Dict, Any
import numpy as np
import re

# ---- (필요 시) PDF 텍스트 추출 라이브러리 ----
# pdfplumber, pypdf 둘 중 하나 사용 가능. 환경에 맞게 선택하여 주석 해제.
# import pdfplumber
# from pypdf import PdfReader


# =========================
# 데이터 구조
# =========================
@dataclass
class Chunk:
    """PDF에서 추출한 텍스트 조각(페이지 단위 + 길이 제한)."""
    doc_id: str            # 파일 식별자(파일명 또는 해시)
    page: int              # 1-based 페이지 번호
    text: str              # 해당 페이지의 부분 텍스트
    embedding: np.ndarray  # L2 정규화된 임베딩 벡터
    chunk_id: str          # 내부 식별용(선택)


@dataclass
class RetrievalResult:
    """검색 결과 + 유사도 점수."""
    chunk: Chunk
    score: float  # cosine similarity (정규화 벡터 dot 결과)


# =========================
# 유틸: 정규화/문자열
# =========================
def l2_normalize(v: np.ndarray) -> np.ndarray:
    """L2 정규화. 0으로 나눔 방지."""
    n = np.linalg.norm(v)
    return v / (n + 1e-12)


def clean_text(s: str) -> str:
    """PDF 추출 텍스트 전처리(공백/중복 줄바꿈 정돈)."""
    s = s.replace("\x00", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# =========================
# PDF → 페이지 단위 텍스트 추출
# =========================
def extract_pdf_by_page(file_path: str) -> List[Tuple[int, str]]:
    """
    반환: [(page_number(1-based), page_text), ...]
    - pdfplumber 또는 pypdf 중 환경에 맞게 사용.
    - 아래는 pypdf 예시(간결).
    """
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages.append((i + 1, clean_text(text)))
    return pages


# =========================
# 페이지 텍스트 → 조각(Chunk) 만들기
# =========================
def split_into_chunks(
    doc_id: str,
    pages: List[Tuple[int, str]],
    embed_fn: Callable[[str], np.ndarray],
    max_chars: int = 1200,
    overlap: int = 150
) -> List[Chunk]:
    """
    - 각 페이지 텍스트를 길이 제한으로 슬라이싱하여 Chunk 생성
    - overlap을 줘서 문맥 단절 완화
    - 모든 임베딩은 L2 정규화
    """
    chunks: List[Chunk] = []
    for page_num, page_text in pages:
        if not page_text:
            continue
        start = 0
        idx = 0
        while start < len(page_text):
            end = min(len(page_text), start + max_chars)
            piece = page_text[start:end]
            emb = l2_normalize(embed_fn(piece))
            chunks.append(
                Chunk(
                    doc_id=doc_id,
                    page=page_num,
                    text=piece,
                    embedding=emb,
                    chunk_id=f"{doc_id}:{page_num}:{idx}"
                )
            )
            # 다음 슬라이스(중첩을 남기며 전진)
            if end == len(page_text):
                break
            start = end - overlap
            idx += 1
    return chunks


# =========================
# 간단한 벡터 스토어
# =========================
class SimpleVectorStore:
    """메모리 내 임베딩 인덱스. PoC/테스트용으로 충분."""
    def __init__(self) -> None:
        self._chunks: List[Chunk] = []

    def add(self, chunks: List[Chunk]) -> None:
        self._chunks.extend(chunks)

    def search(
        self, 
        query_emb: np.ndarray, 
        top_k: int = 5, 
        doc_id: str | None = None
    ) -> List[RetrievalResult]:
        """doc_id로 문서 범위를 제한(== 문서 내부 검색) 가능."""
        q = l2_normalize(query_emb)
        pool = self._chunks if doc_id is None else [c for c in self._chunks if c.doc_id == doc_id]
        scored = [(c, float(np.dot(c.embedding, q))) for c in pool]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [RetrievalResult(chunk=c, score=s) for c, s in scored[:top_k]]


# =========================
# LLM 프롬프트(문서 밖 추론 금지)
# =========================
RAG_SYSTEM_PROMPT = """당신은 엄격한 문서 기반 분석가입니다.
아래 '맥락(context)'에 포함된 내용으로만 답하세요.
맥락에 없는 사실, 수치, 해석은 절대 추가하지 마세요.
맥락이 불충분하면 '문서 근거가 부족합니다'라고 답하세요.
답변 마지막에 '출처' 섹션을 만들어 페이지 번호와 근거 문장을 요약해 표시하세요.
"""

RAG_USER_PROMPT_TEMPLATE = """[질문]
{question}

[맥락]
{context}

[요구]
- 맥락 안에서만 추론 (외부 지식 사용 금지)
- 표/그림도 맥락 텍스트에 적힌 범위 내에서만 해석
- 핵심 요점 3~5개로 간결히
- 마지막에 '출처' 섹션 표기 (예: p.24, p.37 등)
"""


# =========================
# 컨텍스트(근거) 구성
# =========================
def build_context_and_evidence(
    retrieved: List[RetrievalResult],
    char_limit: int = 3000
) -> tuple[str, list[dict]]:
    """
    - LLM에 줄 컨텍스트 텍스트 구성
    - 동시에 UI에 표시할 evidence 메타(페이지/유사도/스니펫) 준비
    """
    ctx_parts: List[str] = []
    evidences: List[dict] = []
    acc_len = 0
    for r in retrieved:
        snippet = r.chunk.text.strip().replace("\n", " ")
        piece = f"(p.{r.chunk.page}) {snippet}"
        if acc_len + len(piece) > char_limit:
            break
        ctx_parts.append(piece)
        evidences.append({
            "page": r.chunk.page,
            "similarity": round(r.score, 4),
            "snippet": snippet[:240] + ("..." if len(snippet) > 240 else "")
        })
        acc_len += len(piece)
    return "\n\n".join(ctx_parts), evidences


# =========================
# 메인 Q&A 함수
# =========================
def answer_from_pdf(
    llm_chat: Callable[[str, str], str],   # (system, user) -> answer str
    store: SimpleVectorStore,
    embed_fn: Callable[[str], np.ndarray],
    question: str,
    doc_id: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    - 질문 → (해당 문서 doc_id 범위로) 검색 → 컨텍스트 구성 → LLM 호출
    - 컨텍스트가 거의 없으면 보수적 응답(할루 방지)
    - 반환: answer + evidences(page/sim/snippet) + meta
    """
    q_emb = l2_normalize(embed_fn(question))
    retrieved = store.search(q_emb, top_k=top_k, doc_id=doc_id)
    context, evidences = build_context_and_evidence(retrieved)

    if len(context) < 80:  # 문맥이 너무 부족하면 안전 응답
        return {
            "answer": "문서 근거가 부족합니다. 질문을 더 구체화하거나 다른 페이지를 확인해 주세요.",
            "evidences": evidences,
            "meta": {"doc_id": doc_id, "top_k": top_k, "question": question}
        }

    user_prompt = RAG_USER_PROMPT_TEMPLATE.format(question=question, context=context)
    answer = llm_chat(RAG_SYSTEM_PROMPT, user_prompt)

    return {
        "answer": answer,
        "evidences": evidences,
        "meta": {"doc_id": doc_id, "top_k": top_k, "question": question}
    }


# =========================
# 인덱싱 파이프라인(한 문서)
# =========================
def index_pdf(
    file_path: str,
    doc_id: str,
    store: SimpleVectorStore,
    embed_fn: Callable[[str], np.ndarray],
    max_chars: int = 1200,
    overlap: int = 150
) -> List[Chunk]:
    """PDF → 페이지 텍스트 → 조각 → 벡터스토어 적재."""
    pages = extract_pdf_by_page(file_path)
    chunks = split_into_chunks(
        doc_id=doc_id,
        pages=pages,
        embed_fn=embed_fn,
        max_chars=max_chars,
        overlap=overlap
    )
    store.add(chunks)
    return chunks
