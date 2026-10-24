"""上传文件校验与落盘。"""

from pathlib import Path

from app.core.configuration import settings

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


class UploadRejected(Exception):
    """上传文件不满足格式要求。"""


def save_document(content: bytes, filename: str, document_id: str) -> Path:
    """校验扩展名后按文档 ID 命名保存，返回实际路径。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_SUFFIXES))
        raise UploadRejected(f"仅支持 {allowed} 文件")

    directory = Path(settings.upload_directory)
    directory.mkdir(parents=True, exist_ok=True)

    path = directory / f"{document_id}{suffix}"
    path.write_bytes(content)
    return path