"""文档路由：上传、按角色列出、失败重试、删除与权限调整。"""

from pathlib import Path
from typing import get_args

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.configuration import settings
from app.db.database import get_database_session
from app.db.tables import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_QUEUED,
    Document,
    User,
    new_uuid,
)
from app.models.api_models import (
    DocumentChunkResponse,
    DocumentResponse,
    RoleName,
    UpdateDocumentRolesRequest,
)
from app.services.document_storage import UploadRejected, save_document
from app.services.ingestion_queue import enqueue_document
from app.services.retrieval import (
    delete_document_points,
    list_document_chunks,
    sync_document_roles,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def _parse_allowed_roles(raw: str) -> list[str]:
    """把逗号分隔的角色名转成去重后的列表，非法角色直接拒绝。"""
    roles = sorted({item.strip() for item in raw.split(",") if item.strip()})
    if not roles or set(roles) - set(get_args(RoleName)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="allowed_roles 只能包含 admin / procurement / logistics / quality / finance",
        )
    return roles


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    allowed_roles: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> Document:
    """保存上传文件并投递摄取任务。"""
    roles = _parse_allowed_roles(allowed_roles)

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件为空"
        )
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"文件不能超过 {settings.max_upload_size_mb} MB",
        )

    document_id = new_uuid()
    filename = Path(file.filename or "unnamed").name
    try:
        stored_path = save_document(content, filename, document_id)
    except UploadRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    document = Document(
        document_id=document_id,
        filename=filename,
        stored_path=str(stored_path),
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        allowed_roles=roles,
        uploaded_by=current_user.username,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        enqueue_document(document_id)
    except RedisError as exc:
        document.status = DOCUMENT_STATUS_FAILED
        document.error_message = "摄取队列不可用"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="摄取队列不可用，请稍后重试",
        ) from exc

    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> list[Document]:
    """按当前角色返回可见文档，管理员可见全部。"""
    statement = select(Document).order_by(Document.created_at.desc())
    if current_user.role != "admin":
        statement = statement.where(
            Document.allowed_roles.contains([current_user.role])
        )
    return list(db.scalars(statement).all())


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def list_chunks(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> list[DocumentChunkResponse]:
    """返回文档切块内容，仅限有权访问该文档的角色。"""
    document = _get_document_or_404(db, document_id)
    if (
        current_user.role != "admin"
        and current_user.role not in document.allowed_roles
        and document.uploaded_by != current_user.username
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
        )
    if not document.chunk_count:
        return []

    return [
        DocumentChunkResponse(chunk_index=chunk["chunk_index"], text=chunk["text"])
        for chunk in list_document_chunks(document_id)
    ]


@router.post("/{document_id}/retry", response_model=DocumentResponse)
def retry_ingestion(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> Document:
    """把失败的文档重新投递给 worker。"""
    document = _get_document_or_404(db, document_id)
    _ensure_owner_or_admin(document, current_user)

    try:
        enqueue_document(document_id)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="摄取队列不可用，请稍后重试",
        ) from exc

    document.status = DOCUMENT_STATUS_QUEUED
    document.error_message = None
    db.commit()
    db.refresh(document)
    return document


def _get_document_or_404(db: Session, document_id: str) -> Document:
    """按 ID 取文档，不存在直接返回 404。"""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在"
        )
    return document


def _ensure_owner_or_admin(document: Document, current_user: User) -> None:
    """只有上传者本人或管理员可以操作该文档。"""
    if current_user.role != "admin" and document.uploaded_by != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
        )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> None:
    """删除文档记录、落盘文件和全部向量块。"""
    document = _get_document_or_404(db, document_id)
    _ensure_owner_or_admin(document, current_user)

    try:
        delete_document_points(document_id)
    except Exception:
        # 向量库不可用时仍允许删除，避免失败记录永远清不掉
        logger.warning("删除向量失败: {}", document_id)

    Path(document.stored_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()


@router.patch("/{document_id}/roles", response_model=DocumentResponse)
def update_document_roles(
    document_id: str,
    payload: UpdateDocumentRolesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_database_session),
) -> Document:
    """管理员调整可访问角色，并同步已入库的向量。"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可调整权限"
        )
    document = _get_document_or_404(db, document_id)

    roles = sorted(set(payload.allowed_roles))
    # 先改向量再改库：向量库失败就整体不生效，避免两边权限不一致
    if document.chunk_count:
        try:
            sync_document_roles(document_id, roles)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="向量库不可用，权限未修改",
            ) from exc

    document.allowed_roles = roles
    db.commit()
    db.refresh(document)
    return document