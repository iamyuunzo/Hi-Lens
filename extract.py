# extract.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
import re
import numpy as np
from PIL import Image
import fitz  # PyMuPDF

# ---- 라벨 패턴 ----
_RE_TABLE = re.compile(
    r"(?:[<\[\(〈{]\s*표\s*([0-9]+(?:[-–][0-9]+)?)\s*[>\]\)〉}]\s*([^\n\r]*)|"
    r"\b표\s*([0-9]+(?:[-–][0-9]+)?)\s*([^\n\r]*))"
)
_RE_FIG = re.compile(
    r"(?:[<\[\(〈{]\s*그림\s*([0-9]+(?:[-–][0-9]+)?)\s*[>\]\)〉}]\s*([^\n\r]*)|"
    r"\b그림\s*([0-9]+(?:[-–][0-9]+)?)\s*([^\n\r]*))"
)

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _is_toc_page(text: str) -> bool:
    """목차/표 목차/그림 목차 페이지를 탐지해서 스캔에서 제외."""
    head = (text or "")[:600]
    if re.search(r"(목\s*차|표\s*목차|그림\s*목차)", head):
        return True
    # 라벨 라인이 일정 갯수 이상 연속으로 나오면(목차일 확률↑)
    lines = head.splitlines()
    hits = sum(bool(re.search(r"^\s*(표|그림)\s*\d+-\d+", ln)) for ln in lines)
    return hits >= 5

# ---- 렌더/후처리 ----
def _render_region_as_image(page: fitz.Page, rect: fitz.Rect, dpi: int = 220) -> Image.Image:
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, clip=rect, alpha=False)
    return Image.open(BytesIO(pix.tobytes(output="png"))).convert("RGB")

def _refine_crop_to_table_content(pil_img: Image.Image,
                                  top_line_threshold: float = 0.08,
                                  white_thresh: int = 240,
                                  min_gap: int = 24,
                                  pad: int = 6) -> Image.Image:
    """표만 타이트하게 남기기(상단/하단 공백 컷)."""
    g = pil_img.convert("L")
    arr = np.array(g)
    dark = arr < white_thresh
    row_density = dark.mean(axis=1)
    H = arr.shape[0]

    # 상단 시작
    top_idx = 0
    for i, d in enumerate(row_density):
        if d >= top_line_threshold:
            top_idx = i
            break

    # 하단 끝(긴 공백 직전)
    bottom_idx = H - 1
    blank = row_density < 0.01
    run, cutoff = 0, None
    for i in range(max(top_idx + 10, 0), H):
        if blank[i]:
            run += 1
            if run >= min_gap:
                cutoff = i - run
                break
        else:
            run = 0
    if cutoff is not None:
        bottom_idx = max(top_idx + 5, cutoff)
    else:
        nz = np.where(row_density > 0.02)[0]
        bottom_idx = int(nz[-1]) if len(nz) > 0 else H - 1

    top_idx = max(0, top_idx - pad)
    bottom_idx = min(H - 1, bottom_idx + pad)
    if bottom_idx <= top_idx:
        return pil_img
    return pil_img.crop((0, top_idx, pil_img.width, bottom_idx + 1))

def crop_table_image(pdf_bytes: bytes, page_index: int, bbox: Tuple[float, float, float, float], dpi: int = 220) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    rect = fitz.Rect(*bbox)
    img = _render_region_as_image(page, rect, dpi=dpi)
    refined = _refine_crop_to_table_content(img)
    if refined.height < 12 or refined.width < 12:
        return img
    return refined

def crop_figure_image(pdf_bytes: bytes, page_index: int, bbox: Tuple[float, float, float, float], dpi: int = 220) -> Image.Image:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    rect = fitz.Rect(*bbox)
    return _render_region_as_image(page, rect, dpi=dpi)

# ---- 라벨 스캔 ----
def _scan_label_blocks(page: fitz.Page) -> List[Dict[str, Any]]:
    blocks = page.get_text("blocks")
    out: List[Dict[str, Any]] = []
    for b in blocks:
        if len(b) < 5: 
            continue
        x0, y0, x1, y1, txt = b[:5]
        text = (txt or "").strip()
        if not text:
            continue
        m = _RE_TABLE.search(text)
        if m:
            label = (m.group(1) or m.group(3) or "").replace("–", "-")
            out.append({"kind":"table","label":label,"title":_clean(m.group(2) or m.group(4) or ""), "bbox":(x0,y0,x1,y1)})
            continue
        m = _RE_FIG.search(text)
        if m:
            label = (m.group(1) or m.group(3) or "").replace("–", "-")
            out.append({"kind":"figure","label":label,"title":_clean(m.group(2) or m.group(4) or ""), "bbox":(x0,y0,x1,y1)})
    out.sort(key=lambda d: (d["bbox"][1], d["bbox"][0]))
    return out

def _safe_bbox(page_rect: fitz.Rect, x0: float, y0: float, x1: float, y1: float) -> Tuple[float, float, float, float]:
    x0 = max(page_rect.x0, min(x0, page_rect.x1))
    x1 = max(page_rect.x0, min(x1, page_rect.x1))
    y0 = max(page_rect.y0, min(y0, page_rect.y1))
    y1 = max(page_rect.y0, min(y1, page_rect.y1))
    if x1 - x0 < 20:
        cx, half = (x0 + x1)/2.0, 120
        x0, x1 = max(page_rect.x0+5, cx-half), min(page_rect.x1-5, cx+half)
    if y1 - y0 < 20:
        base = max(100, int((page_rect.y1 - page_rect.y0) * 0.15))
        y1 = min(page_rect.y1-5, y0 + base)
    return (x0, y0, x1, y1)

def _make_content_regions(page: fitz.Page, label_blocks: List[Dict[str, Any]],
                          left_margin: float = 12.0, right_margin: float = 12.0,
                          top_pad: float = 6.0, bottom_pad: float = 6.0) -> List[Dict[str, Any]]:
    page_rect = page.rect
    items: List[Dict[str, Any]] = []
    for i, lb in enumerate(label_blocks):
        x0, y0, x1, y1 = lb["bbox"]
        region_top = y1 + top_pad
        if i + 1 < len(label_blocks):
            _, ny0, _, _ = label_blocks[i+1]["bbox"]
            region_bot = ny0 - bottom_pad
        else:
            region_bot = page_rect.y1 - bottom_pad
        rx0, rx1 = page_rect.x0 + left_margin, page_rect.x1 - right_margin
        sx0, sy0, sx1, sy1 = _safe_bbox(page_rect, rx0, region_top, rx1, region_bot)
        items.append({
            "kind": lb["kind"], "label": lb["label"], "title": lb["title"],
            "caption": lb["title"], "bbox": (sx0, sy0, sx1, sy1)
        })
    return items

# ---- 메인 ----
def build_chunks(pdf_bytes: bytes, progress: Optional[Any] = None) -> Dict[str, Any]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    tables, figures, texts = [], [], []
    toc_tables, toc_figures = [], []

    for pidx in range(doc.page_count):
        page = doc[pidx]
        page_label = pidx + 1
        full_text = page.get_text()
        texts.append({"page": page_label, "text": full_text})

        is_toc = _is_toc_page(full_text)
        regions = []
        if not is_toc:  # <<<<<< TOC 페이지는 스킵!
            lbs = _scan_label_blocks(page)
            regions = _make_content_regions(page, lbs)

        n_tab_on_page, table_sample = 0, ""
        for it in regions:
            item = {"type": it["kind"], "label": it["label"], "title": it["title"],
                    "caption": it["caption"], "page": page_label, "bbox": tuple(it["bbox"]),
                    "df": None, "md": ""}
            if it["kind"] == "table":
                tables.append(item); n_tab_on_page += 1
                if not table_sample: table_sample = f"〈표 {item['label']}〉 {item['title']}"
                toc_tables.append({"label": item["label"], "title": item["title"], "page": page_label})
            else:
                figures.append(item)
                toc_figures.append({"label": item["label"], "title": item["title"], "page": page_label})

        if progress is not None:
            progress({"page_idx": pidx, "page_label": page_label,
                      "n_tables": n_tab_on_page, "n_words": len(full_text.split()),
                      "is_toc": is_toc, "table_sample": table_sample})

    def _dedup(items):
        seen, out = set(), []
        for x in items:
            key = (x.get("label"), _clean(x.get("title","")))
            if key in seen: continue
            seen.add(key); out.append(x)
        return out

    return {"toc": {"tables": _dedup(toc_tables), "figures": _dedup(toc_figures)},
            "tables": tables, "figures": figures, "texts": texts}

# ---- 검색 ----
def _normalize_label(lab: Optional[str]) -> Optional[str]:
    return lab.replace("–", "-").strip() if lab else None

def find_table_by_label(chunks: Dict[str, Any], label: str):
    lab = _normalize_label(label)
    for t in chunks.get("tables", []):
        if _normalize_label(t.get("label")) == lab:
            return t
    return None

def find_figure_by_label(chunks: Dict[str, Any], label: str):
    lab = _normalize_label(label)
    for f in chunks.get("figures", []):
        if _normalize_label(f.get("label")) == lab:
            return f
    return None
