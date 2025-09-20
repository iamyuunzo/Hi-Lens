# rag.py
# -*- coding: utf-8 -*-
# RAG Index — "표 우선" 검색 + 하이브리드 스코어(임베딩 + BM25)
#
# 변경점(중요):
#  - build(): 각 표 메타에 extract_pdf에서 넣은 diag.is_toc 플래그를 실어둠.
#  - search_tables(): '목차(TOC) 페이지'에서 나온 표 후보는 기본 제외(대안 없을 때만 사용).
#  - 하이브리드 스코어(임베딩 + BM25)는 기존 흐름 유지.
#
# 참고: 기존 인덱싱/검색 흐름과 UI 연결은 현 프로젝트 구조를 유지한다. :contentReference[oaicite:4]{index=4}

import re, os
from typing import Any, Dict, List
import numpy as np

# ---- 임베딩 모델(문장) ----
_EMBEDDING_OK = True
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None
    _EMBEDDING_OK = False

# ---- 벡터 인덱스(faiss) 선택적 ----
_FAISS_OK = True
try:
    import faiss
except Exception:
    faiss = None
    _FAISS_OK = False

# ---- BM25 ----
from rank_bm25 import BM25Okapi

# ---- 간단 토크나이저(한글/영문/숫자) ----
_token_pat = re.compile(r"[가-힣A-Za-z]+|\d+(?:[.,]\d+)?")
def _tok(s: str):
    s = (s or "").lower()
    return _token_pat.findall(s)

TABLE_HINT_WORDS = ["표","table","테이블","나열","목록","list","추세","변화","연도","통계","통계표","지표"]


def _normalize(a: np.ndarray) -> np.ndarray:
    if a.ndim == 1:
        denom = (np.linalg.norm(a) + 1e-8)
        return a / denom
    denom = (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
    return a / denom


class _LiteIndex:
    """faiss 대체: numpy 내적으로 top-k 검색(소규모에 충분)"""
    def __init__(self, dim: int):
        self.vecs = None
        self.dim  = dim
    def add(self, arr: np.ndarray):
        self.vecs = arr.astype(np.float32)
    def search(self, q: np.ndarray, k: int):
        sims = (q @ self.vecs.T)[0]    # (N,)
        I = np.argsort(sims)[-k:][::-1]
        D = sims[I]
        return D.reshape(1,-1), I.reshape(1,-1)


class RAGIndex:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = None
        if _EMBEDDING_OK:
            try:
                self.model = SentenceTransformer(model_name)
            except Exception:
                self.model = None

        self.page_texts: List[str] = []
        self.page_meta:  List[Dict[str,Any]] = []
        self.para_texts: List[str] = []
        self.para_meta:  List[Dict[str,Any]] = []

        self.table_texts: List[str] = []
        self.table_meta:  List[Dict[str,Any]] = []
        self.table_texts_full: List[str] = []
        self.table_meta_full:  List[Dict[str,Any]] = []

        self.page_index = None
        self.para_index = None
        self.table_index = None
        self.table_index_full = None

        self.bm25 = None
        self.table_bm25 = None
        self.table_bm25_full = None

    # ------- 인덱스 구축 -------
    def _make_index(self, vec: np.ndarray):
        d = vec.shape[1]
        if _FAISS_OK:
            idx = faiss.IndexFlatIP(d); idx.add(vec.astype(np.float32))
            return idx
        else:
            idx = _LiteIndex(d); idx.add(vec.astype(np.float32))
            return idx

    def _encode(self, texts: List[str]) -> np.ndarray:
        if self.model is None:
            # 임베딩 모델이 없으면 zeros 반환(emb 스코어는 0, BM25만 사용)
            return np.zeros((len(texts), 384), dtype=np.float32)
        v = self.model.encode(texts, normalize_embeddings=True)
        return v.astype(np.float32)

    def build(self, pages: List[Dict[str,Any]]):
        """
        extract.extract_pdf()의 pages를 그대로 받아 인덱스를 구축한다.
        - page_meta: page_index/page_label
        - table_meta(_full): page_index/page_label/table_index/is_toc
        """
        # 페이지 텍스트/메타
        self.page_texts = [p.get("text","") for p in pages]
        self.page_meta  = [{"page_index":p["page_index"], "page_label":p["page_label"]} for p in pages]
        if self.page_texts:
            vec = self._encode(self.page_texts); self.page_index = self._make_index(vec)
            self.bm25 = BM25Okapi([_tok(t) for t in self.page_texts])

        # 표(요약/풀텍스트)
        for p in pages:
            is_toc = bool(p.get("diag", {}).get("is_toc"))
            for ti, ttxt in enumerate(p.get("table_texts", []) or []):
                if ttxt and ttxt.strip():
                    self.table_texts.append(ttxt)
                    self.table_meta.append({
                        "page_index": p["page_index"],
                        "page_label": p["page_label"],
                        "table_index": ti,
                        "is_toc": is_toc
                    })
            for ti, ttxt in enumerate(p.get("table_texts_full", []) or []):
                if ttxt and ttxt.strip():
                    self.table_texts_full.append(ttxt)
                    self.table_meta_full.append({
                        "page_index": p["page_index"],
                        "page_label": p["page_label"],
                        "table_index": ti,
                        "is_toc": is_toc
                    })

        if self.table_texts:
            v = self._encode(self.table_texts); self.table_index = self._make_index(v)
            self.table_bm25 = BM25Okapi([_tok(t) for t in self.table_texts])
        if self.table_texts_full:
            v = self._encode(self.table_texts_full); self.table_index_full = self._make_index(v)
            self.table_bm25_full = BM25Okapi([_tok(t) for t in self.table_texts_full])

    # ------- 공통: 하이브리드 스코어 -------
    def _hybrid_scores(self, query: str, texts: List[str], metas: List[Dict[str,Any]],
                       index, bm25: BM25Okapi, topn: int = 12) -> List[Dict[str,Any]]:
        if not texts:
            return []
        qtok = _tok(query)
        # BM25
        bm = bm25.get_scores(qtok) if bm25 else np.zeros(len(texts), dtype=np.float32)
        # 임베딩
        if index is not None and hasattr(index, "search") and self.model is not None:
            qv = self._encode([query]); qv = _normalize(qv)
            if hasattr(index, "ntotal") or hasattr(index, "vecs"):
                D, I = index.search(qv, min(topn, len(texts)))
                emb_scores = np.zeros_like(bm)
                emb_scores[I[0]] = D[0]
            else:
                emb_scores = np.zeros_like(bm)
        else:
            emb_scores = np.zeros_like(bm)

        # 하이브리드 가중합 (BM25 0.6 + 임베딩 0.4)
        s = 0.6 * (bm / (np.max(bm) + 1e-8)) + 0.4 * (emb_scores / (np.max(emb_scores) + 1e-8))
        order = np.argsort(s)[::-1][:topn]
        out = []
        for idx in order:
            meta = dict(metas[idx])
            meta["score"] = float(s[idx])
            meta["text"]  = texts[idx]
            out.append(meta)
        return out

    # ------- 표 검색(우선) -------
    def search_tables(self, query: str, k: int = 5) -> List[Dict[str,Any]]:
        hits_short = self._hybrid_scores(query, self.table_texts, self.table_meta,
                                         self.table_index, self.table_bm25, max(k*2, 10))
        hits_full  = self._hybrid_scores(query, self.table_texts_full, self.table_meta_full,
                                         self.table_index_full, self.table_bm25_full, max(k*2, 10))
        for h in hits_short: h["source"] = "short"
        for h in hits_full:  h["source"]  = "full"
        hits = hits_short + hits_full

        # 중복제거
        uniq, seen = [], set()
        for h in sorted(hits, key=lambda x: x["score"], reverse=True):
            key = (h.get("page_index"), h.get("table_index"), h.get("source"))
            if key in seen: 
                continue
            seen.add(key)
            uniq.append(h)

        # 1차: 목차(TOC) 페이지가 아닌 것 우선
        non_toc = [h for h in uniq if not h.get("is_toc")]
        final = non_toc[:k] if non_toc else uniq[:k]
        return final
