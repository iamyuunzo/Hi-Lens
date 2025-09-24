# rag.py
# -*- coding: utf-8 -*-
"""
RAG Index — 표 검색 (BM25 + 임베딩) + DataFrame 지원
"""
from __future__ import annotations
from typing import Any, Dict, List
import numpy as np
from rank_bm25 import BM25Okapi

try:
    from sentence_transformers import SentenceTransformer
    _EMBEDDING_OK = True
except Exception:
    SentenceTransformer = None
    _EMBEDDING_OK = False

class _LiteIndex:
    def __init__(self, dim: int):
        self.vecs = None; self.dim = dim
    def add(self, arr: np.ndarray): self.vecs = arr.astype(np.float32)
    def search(self, q: np.ndarray, k: int):
        sims = (q @ self.vecs.T)[0]; I = np.argsort(sims)[-k:][::-1]; D = sims[I]
        return D.reshape(1,-1), I.reshape(1,-1)

def _tok(s: str):
    import re
    _token_pat = re.compile(r"[가-힣A-Za-z]+|\d+(?:[.,]\d+)?")
    return _token_pat.findall((s or "").lower())

def _normalize(a: np.ndarray) -> np.ndarray:
    if a.ndim == 1: return a / (np.linalg.norm(a) + 1e-8)
    return a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)

class RAGIndex:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = None
        if _EMBEDDING_OK:
            try: self.model = SentenceTransformer(model_name)
            except Exception: self.model = None
        self.table_texts, self.table_meta, self.table_dfs = [], [], []
        self.table_index, self.table_bm25 = None, None

    def _encode(self, texts: List[str]) -> np.ndarray:
        if self.model is None: return np.zeros((len(texts), 384), dtype=np.float32)
        v = self.model.encode(texts, normalize_embeddings=True)
        return v.astype(np.float32)

    def _make_index(self, vec: np.ndarray):
        idx = _LiteIndex(vec.shape[1]); idx.add(vec); return idx

    def build_from_chunks(self, chunks: Dict[str,Any]):
        self.table_texts, self.table_meta, self.table_dfs = [], [], []
        for t in chunks.get("tables", []):
            md = (t.get("preview_md") or "").strip()
            if not md: continue
            self.table_texts.append(md)
            self.table_meta.append({
                "page_index": t["page"]-1,
                "page_label": t["page"],
                "label": t["label"],
                "title": t.get("title",""),
            })
            self.table_dfs.append(t.get("df"))
        if not self.table_texts: return
        v = self._encode(self.table_texts); self.table_index = self._make_index(v)
        self.table_bm25 = BM25Okapi([_tok(t) for t in self.table_texts])

    def search_tables(self, query: str, k: int = 3) -> List[Dict[str,Any]]:
        if not self.table_texts: return []
        qtok = _tok(query)
        bm = self.table_bm25.get_scores(qtok) if self.table_bm25 else np.zeros(len(self.table_texts))
        emb = np.zeros_like(bm)
        if self.model is not None:
            qv = _normalize(self._encode([query])); D, I = self.table_index.search(qv, min(k*4, len(self.table_texts)))
            emb[I[0]] = D[0]
        s = 0.6 * (bm / (np.max(bm) + 1e-8)) + 0.4 * (emb / (np.max(emb) + 1e-8))
        order = np.argsort(s)[::-1][:max(k*2, 8)]
        uniq = []
        for idx in order:
            m = dict(self.table_meta[idx]); m["score"] = float(s[idx]); m["text"] = self.table_texts[idx]; m["df"] = self.table_dfs[idx]
            uniq.append(m)
        return uniq[:k]
