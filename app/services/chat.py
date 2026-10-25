"""单轮问答：先按角色检索证据，再调用大模型生成带引用的回答。"""

from openai import OpenAI

from app.core.configuration import settings
from app.services.graph import impact
from app.services.retrieval import search_chunks

# 图谱路径只取最靠前的几条，避免把提示词撑大
GRAPH_EVIDENCE_LIMIT = 6

REFUSAL_TEXT = "知识库中暂无相关资料"


def _is_refusal(answer: str) -> bool:
    """只有整段回答以拒答语开头才算拒答，避免部分回答里顺带提到而被误判。"""
    return answer.strip().lstrip("*# >-").startswith(REFUSAL_TEXT)

SYSTEM_PROMPT = """你是供应链风险分析助手，只能依据用户提供的资料与图谱路径回答问题。
规则：
1. 资料与图谱路径都无法回答时，只回复「知识库中暂无相关资料」，不要在此基础上继续作答。
2. 只能部分回答时，直接说明哪部分资料未覆盖，不要用「知识库中暂无相关资料」开头。
3. 使用了哪条资料，就在句末用 [编号] 标注，编号对应资料前的数字。
4. 引用了哪条图谱路径，就在句末用 [G编号] 标注。
5. 只能引用实际出现的编号，不要编造资料或路径。
6. 用中文回答，结论先行，必要时分点，不要复述资料原文。"""


def _graph_paths(question: str, role: str) -> list[dict]:
    """图谱是可选证据：Neo4j 不可用时降级为纯文档问答。"""
    try:
        return impact(question, None, role)["paths"][:GRAPH_EVIDENCE_LIMIT]
    except Exception:
        return []


def build_graph_context(graph_paths: list[dict]) -> str:
    """把影响路径压成带编号的文本，供模型引用。"""
    return "\n".join(
        f"[G{index}] {path['summary']}（{path['rule_label']}，{path['hops']} 跳；"
        f"事件等级 {path['severity']}；原因：{path['reason']}）"
        for index, path in enumerate(graph_paths, start=1)
    )


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


def build_messages(
    question: str, hits: list[dict], graph_paths: list[dict]
) -> list[dict]:
    """把文档证据与图谱路径编号后拼成提示词。"""
    context = "\n\n".join(
        f"[{index}] 文件：{hit['filename']}（第 {hit['chunk_index'] + 1} 块）\n{hit['text']}"
        for index, hit in enumerate(hits, start=1)
    )
    sections = []
    if context:
        sections.append(f"资料：\n{context}")
    if graph_paths:
        sections.append(f"图谱影响路径：\n{build_graph_context(graph_paths)}")
    materials = "\n\n".join(sections) or "（无可用资料）"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{materials}\n\n问题：{question}"},
    ]


def answer_question(question: str, role: str, model: str, top_k: int) -> dict:
    """检索当前角色可访问的证据，并生成回答。"""
    hits = search_chunks(question, role, top_k)
    graph_paths = _graph_paths(question, role)
    if not hits and not graph_paths:
        return {
            "answer": "知识库中暂无相关资料，无法回答该问题。",
            "reasoning": None,
            "model": model,
            "hits": [],
            "graph_paths": [],
        }

    parameters = {
        "model": model,
        "messages": build_messages(question, hits, graph_paths),
    }
    # 推理模型不支持 temperature 参数
    if "reasoner" not in model:
        parameters["temperature"] = 0.2

    response = get_chat_client(model).chat.completions.create(**parameters)
    message = response.choices[0].message
    answer = message.content or ""
    # 推理模型会额外返回思考过程，普通模型没有该字段
    reasoning = getattr(message, "reasoning_content", None)
    # 模型拒答时即使写了引用标记，引用的也是无关片段，一律不展示
    if _is_refusal(answer):
        return {
            "answer": answer,
            "reasoning": reasoning,
            "model": model,
            "hits": [],
            "graph_paths": [],
        }
    return {
        "answer": answer,
        "reasoning": reasoning,
        "model": model,
        "hits": hits,
        "graph_paths": graph_paths,
    }


def stream_answer(question: str, role: str, model: str, top_k: int):
    """边生成边产出事件：hits / graph / reasoning / delta / done。"""
    hits = search_chunks(question, role, top_k)
    graph_paths = _graph_paths(question, role)
    yield {"type": "hits", "hits": hits}
    yield {"type": "graph", "paths": graph_paths}

    if not hits and not graph_paths:
        yield {"type": "delta", "text": "知识库中暂无相关资料，无法回答该问题。"}
        yield {"type": "done", "hits": [], "graph_paths": []}
        return

    parameters = {
        "model": model,
        "messages": build_messages(question, hits, graph_paths),
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
    refused = _is_refusal(answer)
    yield {
        "type": "done",
        "hits": [] if refused else hits,
        "graph_paths": [] if refused else graph_paths,
    }
