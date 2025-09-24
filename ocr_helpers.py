# ocr_helpers.py
# -*- coding: utf-8 -*-
"""
이미지/스캔 표에 대한 OCR 폴백:
- 표 크롭 이미지 → pytesseract → 느슨한 Markdown 테이블 프리뷰 생성
- 완벽한 수치 복원이 목적이 아니라, LLM에 던질 최소 프리뷰 확보가 목적
"""

from __future__ import annotations
import os, re
from typing import Tuple
import numpy as np
from PIL import Image

# OCR 준비 (선택적)
_OCR_OK = False
try:
    import pytesseract
    if os.getenv("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
    _OCR_OK = True
except Exception:
    pytesseract = None
    _OCR_OK = False

# extract의 크롭 함수 재사용
from extract import crop_table_image


def ocr_markdown_from_image(img: Image.Image) -> str:
    """
    OCR 텍스트 → 느슨한 Markdown 테이블로 변환
    - 공백/탭/쉼표 등을 구분자로 하여 열을 추정
    - 행 수/열 수가 안정적이지 않으면 빈 문자열 반환
    """
    if not _OCR_OK:
        return ""
    try:
        raw = pytesseract.image_to_string(img, lang="kor+eng")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) < 2:
            return ""
        rows = []
        for ln in lines[:20]:
            # 다중 공백/탭/쉼표 등을 열 구분자로 사용
            parts = re.split(r"\s{2,}|\t+|, +| {1,}\| {1,}", ln)
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) < 2:
                # 콜론/하이픈 등으로도 한 번 더 시도
                parts = re.split(r"\s*[,:;]\s+|\s+-\s+", ln)
                parts = [p.strip() for p in parts if p.strip()]
            rows.append(parts)

        if not rows:
            return ""

        max_cols = max(len(r) for r in rows)
        if max_cols < 2:
            return ""
        # 부족한 셀은 빈칸으로 패딩
        rows = [r + [""] * (max_cols - len(r)) for r in rows]

        header = rows[0]
        md = []
        md.append("| " + " | ".join(header) + " |")
        md.append("| " + " | ".join(["---"] * max_cols) + " |")
        for r in rows[1:]:
            md.append("| " + " | ".join(r) + " |")
        return "\n".join(md)
    except Exception:
        return ""


def ocr_preview_markdown(pdf_bytes: bytes, page_index: int, bbox: Tuple[float, float, float, float]) -> str:
    """
    표 미리보기가 비어 있을 때 사용하는 OCR 폴백:
    - PDF 특정 영역 크롭 → OCR → Markdown 프리뷰
    """
    try:
        img = crop_table_image(pdf_bytes, page_index, bbox, dpi=220)
        return ocr_markdown_from_image(img)
    except Exception:
        return ""


def ocr_available() -> bool:
    """UI에서 안내용으로 사용."""
    return _OCR_OK
