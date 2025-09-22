# extract.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
import re
import numpy as np
from PIL import Image
import fitz  # PyMuPDF

# ---------------- 라벨 정규식 ----------------
# 〈표 2-3〉 / <표 3-1> / (표 4-2) / 표2-5 … 등 폭넓게 매칭
_RE_TAB = re.compile(r"(?:^|[\s〈<\(\[])\s*표\s*([0-9]+(?:[-–][0-9]+)?)\s*")
_RE_FIG = re.compile(r"(?:^|[\s〈<\(\[])\s*그림\s*([0-9]+(?:[-–][0-9]+)?)\s*")

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _norm_label(lab: Optional[str]) -> Optional[str]:
    return (lab or "").replace("–", "-").strip() or None

def _label_key(lab: str) -> Tuple[int, int]:
    """'3-11' -> (3, 11) 정렬 키"""
    try:
        a, b = _norm_label(lab).split("-")
        return (int(a), int(b))
    except Exception:
        return (9999, 9999)

def _is_toc_page(text: str) -> bool:
    """목차/표목차/그림목차 페이지 감지 → 스킵"""
    head = (text or "")[:800]
    if re.search(r"(목\s*차|표\s*목차|그림\s*목차)", head):
        return True
    lines = head.splitlines()
    hits = sum(bool(re.search(r"^\s*(표|그림)\s*\d+-\d+", ln)) for ln in lines[:40])
    return hits >= 5

# ---------------- 렌더 & 크롭 ----------------
def _pix_to_pil(pix: fitz.Pixmap) -> Image.Image:
    return Image.open(BytesIO(pix.tobytes(output="png"))).convert("RGB")

def _render_region(page: fitz.Page, rect: fitz.Rect, dpi: int = 220) -> Image.Image:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
    return _pix_to_pil(pix)

def _cut_vertical_whitespace(
    pil: Image.Image,
    upper_ratio: float = 0.08,
    lower_blank: int = 26,
    white: int = 242,
    pad: int = 6,
) -> Image.Image:
    """
    위/아래 여백 자동 컷(표/그림 공용).
    그림 하단 본문·쪽번호 잘림 방지 위해 하단 공백 연속 길이로 컷.
    """
    g = pil.convert("L")
    arr = np.array(g)
    dark = arr < white
    row = dark.mean(axis=1)
    H = arr.shape[0]

    # 상단: 의미있는 픽셀이 나타나는 첫 줄
    top = 0
    for i, d in enumerate(row):
        if d >= upper_ratio:
            top = i
            break

    # 하단: 긴 공백 구간 직전
    blank = row < 0.01
    run, cut = 0, None
    for i in range(max(top + 10, 0), H):
        if blank[i]:
            run += 1
            if run >= lower_blank:
                cut = i - run
                break
        else:
            run = 0

    bottom = cut if cut is not None else int(np.where(row > 0.02)[0][-1]) if np.any(row > 0.02) else H - 1
    top = max(0, top - pad)
    bottom = min(H - 1, bottom + pad)
    if bottom <= top:
        return pil
    return pil.crop((0, top, pil.width, bottom + 1))

def crop_table_image(pdf_bytes: bytes, page_index: int, bbox: Tuple[float, float, float, float], dpi: int = 220) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    img = _render_region(page, fitz.Rect(*bbox), dpi=dpi)
    return _cut_vertical_whitespace(img, upper_ratio=0.08, lower_blank=22)

def crop_figure_image(pdf_bytes: bytes, page_index: int, bbox: Tuple[float, float, float, float], dpi: int = 220) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    img = _render_region(page, fitz.Rect(*bbox), dpi=dpi)
    # 그림은 하단 컷을 약간 더 강하게
    return _cut_vertical_whitespace(img, upper_ratio=0.05, lower_blank=28)

# ---------------- 시각 신호 판별 ----------------
def _is_bold_font(span: Dict[str, Any]) -> bool:
    f = (span.get("font") or "").lower()
    return ("bold" in f) or ("semibold" in f) or ("heavy" in f)

def _lines_in_rect(page: fitz.Page, rect: fitz.Rect) -> int:
    """
    버전에 따라 drawing items 형태가 달라짐을 모두 처리:
    - ('l', x0, y0, x1, y1)  /  ('l', p0, p1)
    - ('re', x, y, w, h)  ← 사각형은 4개 라인으로 가중치
    """
    def _xy(pt):
        if isinstance(pt, (tuple, list)) and len(pt) >= 2:
            return float(pt[0]), float(pt[1])
        if hasattr(pt, "x") and hasattr(pt, "y"):
            return float(pt.x), float(pt.y)
        return None

    n = 0
    try:
        for d in page.get_drawings() or []:
            for it in d.get("items", []) or []:
                if not it:
                    continue
                op = it[0]

                if op == "l":
                    if len(it) >= 5 and all(isinstance(v, (int, float)) for v in it[1:5]):
                        _, x0, y0, x1, y1 = it[:5]
                        r = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                        if rect.intersects(r):
                            n += 1
                        continue
                    if len(it) >= 3:
                        _, p0, p1 = it[:3]
                        xy0 = _xy(p0); xy1 = _xy(p1)
                        if xy0 and xy1:
                            x0, y0 = xy0; x1, y1 = xy1
                            r = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                            if rect.intersects(r):
                                n += 1
                        continue

                if op == "re" and len(it) >= 5:
                    _, x, y, w, h = it[:5]
                    try:
                        box = fitz.Rect(float(x), float(y), float(x) + float(w), float(y) + float(h))
                        if rect.intersects(box):
                            n += 4
                    except Exception:
                        pass
    except Exception:
        return n
    return n

def _has_image_block(page_dict: Dict[str, Any], rect: fitz.Rect) -> bool:
    """텍스트 딕셔너리의 이미지 블록(type=1)이 rect와 겹치는지"""
    for b in page_dict.get("blocks", []):
        if b.get("type", 0) == 1:
            x0, y0, x1, y1 = b["bbox"]
            if rect.intersects(fitz.Rect(x0, y0, x1, y1)):
                return True
    return False

def _digit_density(page: fitz.Page, rect: fitz.Rect) -> float:
    """
    표가 벡터 라인 없이 텍스트만 있는 경우를 위해 '숫자 밀도'를 측정.
    - 0.06~0.08 이상이면 데이터 표로 간주하기에 충분.
    """
    try:
        txt = page.get_text("text", clip=rect) or ""
        if not txt.strip():
            return 0.0
        digits = sum(ch.isdigit() for ch in txt)
        return digits / max(1, len(txt))
    except Exception:
        return 0.0

# ---------------- 라벨 스캔(가장 중요) ----------------
def _scan_labels(page: fitz.Page) -> List[Dict[str, Any]]:
    """
    1) 굵은(Bold) 라벨 span에서 '표 2-3', '그림 1-1' 라벨 후보 추출
    2) 라벨 아래 박스(rect)에 '표 신호(라인/숫자/이미지)' 또는 '그림 신호(이미지)'가 있으면 확정
    """
    pd = page.get_text("dict")
    page_rect = page.rect
    cand: List[Dict[str, Any]] = []

    # 1) Bold span에서 라벨 후보 수집
    for bl in pd.get("blocks", []):
        for ln in bl.get("lines", []):
            for sp in ln.get("spans", []):
                txt = sp.get("text", "") or ""
                if not txt.strip():
                    continue
                if not _is_bold_font(sp):
                    continue
                m_tab = _RE_TAB.search(txt)
                m_fig = _RE_FIG.search(txt)
                if not (m_tab or m_fig):
                    continue
                lab = _norm_label((m_tab.group(1) if m_tab else m_fig.group(1)))
                kind = "table" if m_tab else "figure"
                x0, y0, x1, y1 = sp["bbox"]
                cand.append({"kind": kind, "label": lab, "title": _clean(txt), "y1": y1, "bbox_lab": (x0, y0, x1, y1)})

    # 2) 라벨 아래 영역 검사(신호 확인)
    out: List[Dict[str, Any]] = []
    cand.sort(key=lambda d: d["y1"])  # 위→아래
    for i, lb in enumerate(cand):
        top = lb["y1"] + 4
        bottom = cand[i + 1]["bbox_lab"][1] - 4 if i + 1 < len(cand) else page_rect.y1 - 6
        rect = fitz.Rect(page_rect.x0 + 8, top, page_rect.x1 - 8, bottom)

        # 비정상 박스(높이/폭 0)는 스킵
        if rect.height <= 1 or rect.width <= 1:
            continue

        if lb["kind"] == "table":
            # ✅ 완화 규칙: (1) 라인 ≥ 3  OR  (2) 이미지 블록 존재  OR  (3) 숫자 밀도 ≥ 0.07
            line_cnt = _lines_in_rect(page, rect)
            has_img = _has_image_block(pd, rect)
            dens = _digit_density(page, rect)
            if not (line_cnt >= 3 or has_img or dens >= 0.07):
                continue
        else:
            # 그림은 이미지 블록 필수
            if not _has_image_block(pd, rect):
                continue

        lb["bbox"] = (rect.x0, rect.y0, rect.x1, rect.y1)
        out.append(lb)

    return out

# ---------------- 메인 빌드 ----------------
def build_chunks(pdf_bytes: bytes, progress=None) -> Dict[str, Any]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    tables, figures, texts = [], [], []

    for pidx in range(doc.page_count):
        page = doc[pidx]
        full = page.get_text()

        # 텍스트는 항상 저장(추천 질문/자연어 QA용)
        texts.append({"page": pidx + 1, "text": full})

        # 목차류는 스킵
        if _is_toc_page(full):
            if progress:
                progress({"page_idx": pidx, "page_label": pidx + 1, "n_tables": 0, "n_words": len(full.split()), "is_toc": True})
            continue

        lbs = _scan_labels(page)
        for lb in lbs:
            item = {
                "type": lb["kind"],
                "label": lb["label"],
                "title": lb["title"],
                "caption": lb["title"],
                "page": pidx + 1,
                "bbox": lb["bbox"],
                "df": None,
                "md": "",
            }
            if lb["kind"] == "table":
                tables.append(item)
            else:
                figures.append(item)

        if progress:
            n_tab = sum(1 for x in lbs if x["kind"] == "table")
            progress({"page_idx": pidx, "page_label": pidx + 1, "n_tables": n_tab, "n_words": len(full.split()), "is_toc": False})

    # 라벨 정렬(TOC 순서와 일치)
    tables.sort(key=lambda t: _label_key(t["label"]))
    figures.sort(key=lambda f: _label_key(f["label"]))

    toc_tables = [{"label": t["label"], "title": t["title"], "page": t["page"]} for t in tables]
    toc_figs   = [{"label": f["label"], "title": f["title"], "page": f["page"]} for f in figures]

    return {
        "toc": {"tables": toc_tables, "figures": toc_figs},
        "tables": tables,
        "figures": figures,
        "texts": texts,
    }

# ---------------- 헬퍼(검색) ----------------
def find_table_by_label(chunks: Dict[str, Any], label: str):
    lab = _norm_label(label)
    for t in chunks.get("tables", []):
        if _norm_label(t.get("label")) == lab:
            return t
    return None

def find_figure_by_label(chunks: Dict[str, Any], label: str):
    lab = _norm_label(label)
    for f in chunks.get("figures", []):
        if _norm_label(f.get("label")) == lab:
            return f
    return None
