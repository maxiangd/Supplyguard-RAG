"""单轮问答：先按角色检索证据，再调用大模型生成带引用的回答。"""

from openai import OpenAI

from app.core.configuration import settings
from app.services.retrieval import search_chunks

SYSTEM_PROMPT = """你是供应链风险分析助手，只能依据用户提供的资料回答问题。
规则：
1. 资料不足以回答时，直接回复「知识库中暂无相关资料」，不要猜测或补充常识。
2. 使用了哪条资料，就在句末用 [编号] 标注，编号对应资料前的数字。
3. 用中文回答，结论先行，必要时分点，不要复述资料原文。"""


def available_models() -> list[str]:
    """返回当前密钥下真正可用的模型。"""
    models = []
    for item in settings.llm_available_models.split(","):
        model = item.strip()
        if not model:
            continue
        is_qwen = model.startswith("qwen")
        if is_qwen and not settings.embedding_api_key:
            continue
        if not is_qwen and not settings.llm_api_key:
            continue
        models.append(model)
    return models


def default_model() -> str:
    """配置的默认模型不可用时，退回第一个可用模型。"""
    models = available_models()
    if settings.llm_model in models:
        return settings.llm_model
    return models[0] if models else settings.llm_model


def get_chat_client(model: str) -> OpenAI:
    """按模型名选择服务商：qwen-* 走百炼，其余走 DeepSeek。"""
    if model.startswith("qwen"):
        # 百炼同一把 key 同时用于向量化和对话模型
        return OpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url,
        )
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def build_messages(question: str, hits: list[dict]) -> list[dict]:
    """把检索到的证据编号后拼成提示词。"""
    context = "\n\n".join(
        f"[{index}] 文件：{hit['filename']}（第 {hit['chunk_index'] + 1} 块）\n{hit['text']}"
        for index, hit in enumerate(hits, start=1)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"资料：\n{context}\n\n问题：{question}"},
    ]


def answer_question(question: str, role: str, model: str, top_k: int) -> dict:
    """检索当前角色可访问的证据，并生成回答。"""
    hits = search_chunks(question, role, top_k)
    if not hits:
        return {
            "answer": "知识库中暂无相关资料，无法回答该问题。",
            "reasoning": None,
            "model": model,
            "hits": [],
        }

    parameters = {"model": model, "messages": build_messages(question, hits)}
    # 推理模型不支持 temperature 参数
    if "reasoner" not in model:
        parameters["temperature"] = 0.2

    response = get_chat_client(model).chat.completions.create(**parameters)
    message = response.choices[0].message
    answer = message.content or ""
    # 推理模型会额外返回思考过程，普通模型没有该字段
    reasoning = getattr(message, "reasoning_content", None)
    # 模型拒答时即使写了引用标记，引用的也是无关片段，一律不展示
    if "知识库中暂无相关资料" in answer:
        return {
            "answer": answer,
            "reasoning": reasoning,
            "model": model,
            "hits": [],
        }
    return {"answer": answer, "reasoning": reasoning, "model": model, "hits": hits}


def stream_answer(question: str, role: str, model: str, top_k: int):
    """边生成边产出事件：hits / reasoning / delta / done。"""
    hits = search_chunks(question, role, top_k)
    yield {"type": "hits", "hits": hits}

    if not hits:
        yield {"type": "delta", "text": "知识库中暂无相关资料，无法回答该问题。"}
        yield {"type": "done", "hits": []}
        return

    parameters = {
        "model": model,
        "messages": build_messages(question, hits),
        "stream": True,
    }
    if "reasoner" not in model:
        parameters["temperature"] = 0.2

    answer_parts = []
    for chunk in get_chat_client(model).chat.completions.create(**parameters):
        delta = chunk.choices[0].delta
        reasoning = getattr(delta, "reasoning_content", None)
        if reasoning:
            yield {"type": "reasoning", "text": reasoning}
        if delta.content:
            answer_parts.append(delta.content)
            yield {"type": "delta", "text": delta.content}

    answer = "".join(answer_parts)
    # 模型拒答时即使写了引用标记，引用的也是无关片段，一律不展示
    final_hits = [] if "知识库中暂无相关资料" in answer else hits
    yield {"type": "done", "hits": final_hits}
