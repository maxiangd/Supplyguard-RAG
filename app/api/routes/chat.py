"""问答路由：按角色检索并用指定模型生成回答。"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import OpenAIError

from app.api.dependencies import get_current_user
from app.core.configuration import settings
from app.db.tables import User
from app.models.api_models import (
    AnswerRequest,
    AnswerResponse,
    ChunkHit,
    ModelListResponse,
)
from app.services.chat import (
    answer_question,
    available_models,
    default_model,
    stream_answer,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    """返回前端可选的模型与默认模型。"""
    return ModelListResponse(models=available_models(), default=default_model())


@router.post("/answer", response_model=AnswerResponse)
def answer(
    payload: AnswerRequest,
    current_user: User = Depends(get_current_user),
) -> AnswerResponse:
    """检索当前角色可见的证据，并调用指定模型回答。"""
    models = available_models()
    if not models:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置可用的大模型密钥",
        )

    model = payload.model or default_model()
    if model not in models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的模型"
        )

    try:
        result = answer_question(
            payload.question,
            current_user.role,
            model,
            payload.top_k or settings.top_k,
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="模型服务不可用，请检查对应的 API Key",
        ) from exc

    return AnswerResponse(
        question=payload.question,
        answer=result["answer"],
        reasoning=result["reasoning"],
        model=result["model"],
        hits=[ChunkHit(**hit) for hit in result["hits"]],
        graph_paths=result["graph_paths"],
    )


@router.post("/answer/stream")
def answer_stream(
    payload: AnswerRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """用 SSE 返回检索证据、思考过程与逐字生成的回答。"""
    models = available_models()
    if not models:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未配置可用的大模型密钥",
        )

    model = payload.model or default_model()
    if model not in models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的模型"
        )

    def generate():
        try:
            events = stream_answer(
                payload.question,
                current_user.role,
                model,
                payload.top_k or settings.top_k,
            )
            for event in events:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except OpenAIError:
            detail = {"type": "error", "detail": "模型服务不可用，请检查对应的 API Key"}
            yield f"data: {json.dumps(detail, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
