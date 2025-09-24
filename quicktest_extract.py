# -*- coding: utf-8 -*-
"""
extract.build_chunks() 빠른 점검 + 표/그림 크롭 저장
사용: python quicktest_extract.py "C:\\path\\to\\file.pdf"
"""
import sys
from pathlib import Path
from typing import Dict, Any
from extract import build_chunks, crop_table_image, crop_figure_image

def print_progress(info: Dict[str, Any]):
    label   = info.get("page_label"); nt = info.get("n_tables"); nw = info.get("n_words")
    is_toc  = "TOC" if info.get("is_toc") else "   "
    print(f"p.{label:>4}  표={nt:<2} | 단어={nw:>4}  {is_toc}")

def main():
    if len(sys.argv) < 2:
        print("사용법: python quicktest_extract.py <PDF경로>"); return
    pdf_path = Path(sys.argv[1]); 
    if not pdf_path.exists(): print("파일 없음"); return

    pdf_bytes = pdf_path.read_bytes()
    chunks = build_chunks(pdf_bytes, progress=print_progress)
    print("\n표 개수:", len(chunks["tables"]), "그림 개수:", len(chunks["figures"]))

    # 샘플 크롭 저장
    if chunks["tables"]:
        t = chunks["tables"][0]
        img = crop_table_image(pdf_bytes, t["page"]-1, t["bbox"])
        img.save(pdf_path.with_suffix(".table_preview.png"))
        print("표 크롭 저장:", pdf_path.with_suffix(".table_preview.png"))
    if chunks["figures"]:
        f = chunks["figures"][0]
        img = crop_figure_image(pdf_bytes, f["page"]-1, f["bbox"])
        img.save(pdf_path.with_suffix(".figure_preview.png"))
        print("그림 크롭 저장:", pdf_path.with_suffix(".figure_preview.png"))

if __name__ == "__main__":
    main()
