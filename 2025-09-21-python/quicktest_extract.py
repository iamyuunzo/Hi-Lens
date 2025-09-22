# quicktest_extract.py
# -*- coding: utf-8 -*-
"""
통합 빠른 테스트 스크립트
- build_chunks(..., progress=...)로 페이지별 진행 로그 출력
- 라벨로 표/그림 찾기:
    1) 표: 원본 표 이미지 크롭 (crop_table_image)
    2) 그림: 원본 그림 이미지 크롭 (crop_figure_image)
    3) DF 정보 일부 출력
사용:
  python quicktest_extract.py "C:\\path\\to\\파일.pdf"
옵션:
  python quicktest_extract.py "C:\\...pdf" --label 2-1      # <표 2-1>
  python quicktest_extract.py "C:\\...pdf" --fig 3-1        # [그림 3-1]
"""

import sys
from pathlib import Path
from typing import Dict, Any

from extract import (
    build_chunks,
    crop_table_image,
    crop_figure_image,
    find_table_by_label,
    find_figure_by_label,
)

# -------- 진행 상황 콜백 --------
def print_progress(info: Dict[str, Any]):
    label   = info.get("page_label")
    nt      = info.get("n_tables")
    nw      = info.get("n_words")
    ni      = info.get("n_images")
    nv      = info.get("n_vectors")
    is_toc  = "TOC" if info.get("is_toc") else "   "
    sample  = (info.get("table_sample") or "").replace("\n", " ")
    print(f"p.{label:>4}  표={nt:<2} | 단어={nw:>4}  이미지={ni:>2}  벡터={nv:>3}  {is_toc}")
    if sample:
        print(f"  - 표 미리보기(md 일부): {sample[:100]}...", flush=True)

def main():
    if len(sys.argv) < 2:
        print("사용법: python quicktest_extract.py <PDF경로> [--label 2-1] [--fig 3-1]")
        return

    args = sys.argv[1:]
    pdf_path = Path(args[0])
    label = None
    fig_label = None
    if "--label" in args:
        idx = args.index("--label")
        if idx + 1 < len(args):
            label = args[idx + 1]
    if "--fig" in args:
        idx = args.index("--fig")
        if idx + 1 < len(args):
            fig_label = args[idx + 1]

    if not pdf_path.exists():
        print(f"파일을 찾을 수 없습니다: {pdf_path}")
        return

    print("=" * 60)
    print(f"파일: {pdf_path}")
    print("페이지별 처리 로그 ↓\n")

    pdf_bytes = pdf_path.read_bytes()

    # 1) 청크 빌드
    chunks = build_chunks(pdf_bytes, progress=print_progress)

    # 2) 요약
    print("\n" + "=" * 60)
    print(f"총 표 개수(필터 후): {len(chunks['tables'])}")
    print(f"총 그림(차트) 개수: {len(chunks['figures'])}")
    print(f"텍스트 청크 수: {len(chunks['texts'])}")
    if chunks.get("toc", {}).get("tables"):
        print(f"TOC(표) 항목 수: {len(chunks['toc']['tables'])}")
    if chunks.get("toc", {}).get("figures"):
        print(f"TOC(그림) 항목 수: {len(chunks['toc']['figures'])}")
    print("=" * 60)

    # 3) 표 라벨 지정 시
    if label:
        print(f"\n라벨 '<표 {label}>' 탐색 중 ...")
        t = find_table_by_label(chunks, label)
        if not t:
            print("❌ 해당 라벨의 표를 찾지 못했습니다.")
        else:
            print(f"✅ 찾음: page={t['page']}, label={t['label']}, conf={t.get('confidence',0):.2f}")
            if t.get("bbox") is not None:
                img = crop_table_image(pdf_bytes, t["page"] - 1, t["bbox"], dpi=200)
                out_path = pdf_path.with_suffix(f".table_{label.replace('-', '_')}.png")
                img.save(out_path)
                print(f"   - 원본 표 이미지 저장: {out_path}")
            df = t["df"]
            print(f"   - DataFrame shape: {df.shape}")
            print("   - 컬럼:", list(df.columns)[:10])
            print("   - 첫 5행:\n", df.head().to_string(index=False))

    # 4) 그림 라벨 지정 시
    if fig_label:
        print(f"\n라벨 '[그림 {fig_label}]' 탐색 중 ...")
        f = find_figure_by_label(chunks, fig_label)
        if not f:
            print("❌ 해당 라벨의 그림을 찾지 못했습니다.")
        else:
            print(f"✅ 찾음: page={f['page']}, label={f['label']}, caption={(f.get('caption') or '')[:40]}")
            if f.get("bbox") is not None:
                img = crop_figure_image(pdf_bytes, f["page"] - 1, f["bbox"], dpi=220)
                out_path = pdf_path.with_suffix(f".figure_{fig_label.replace('-', '_')}.png")
                img.save(out_path)
                print(f"   - 원본 그림 이미지 저장: {out_path}")

if __name__ == "__main__":
    main()
