"""文档文本提取与分块。"""

from pathlib import Path

import pymupdf


def extract_text(path: Path) -> str:
    """从 PDF 或纯文本文件提取文字。"""
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as pdf:
            return "\n".join(page.get_text() for page in pdf)
    return path.read_text(encoding="utf-8", errors="replace")


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """按字符滑窗切块，相邻块保留重叠内容。"""
    if not text.strip():
        return []
    step = chunk_size - overlap
    return [
        text[start : start + chunk_size].strip()
        for start in range(0, len(text), step)
    ]