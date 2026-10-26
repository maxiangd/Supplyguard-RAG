"""单轮问答：先检索证据再调用大模型生成回答，回答后由 LLM 动态评估风险等级，高风险进审批单。"""

import json

from openai import OpenAI

from app.core.configuration import settings
from app.db.tables import User
from app.services.approval import create_approval
from app.services.graph import alternatives, impact, overview
from app.services.retrieval import search_chunks
from app.services.workflow import await_decision, enter_approval, resume_graph

# 图谱路径只取最靠前的几条，避免把提示词撑大
GRAPH_EVIDENCE_LIMIT = 6

REFUSAL_TEXT = "知识库中暂无相关资料"

RISK_ASSESSMENT_PROMPT = """你是供应链风险审核专家。根据以下信息，判断该 AI 回答涉及的风险等级。

证据资料：
{context}

图谱影响路径：
{graph_context}

用户问题：{question}

AI 回答：{answer}

请只输出一个 JSON 对象，不要包含其他内容：
{{"level": "HIGH 或 MEDIUM 或 LOW", "reason": "简述判断依据，不超过 100 字"}}

风险等级定义：
- HIGH：结论涉及供应中断、停产、召回、制裁、重大合规风险，可能影响多个基地或客户交付
- MEDIUM：价格/成本波动、单一供应商依赖、区域性物流延误、合规要求变化
- LOW：常规信息查询、历史回顾、不涉及实质性风险变化"""


def _is_refusal(answer: str) -> bool:
    """只有整段回答以拒答语开头才算拒答，避免部分回答里顺带提到而被误判。"""
    return answer.strip().lstrip("*# >-").startswith(REFUSAL_TEXT)


def _assess_risk(
    question: str, answer: str, hits: list[dict], graph_paths: list[dict], model: str
) -> tuple[str, str]:
    """调用 LLM 动态判断回答的风险等级。失败时降级为 LOW，不触发审批。"""
    if not hits and not graph_paths:
        return "LOW", ""

    context = "\n\n".join(
        f"[{idx}] {hit['filename']}: {hit['text'][:300]}"
        for idx, hit in enumerate(hits[:3], start=1)
    )
    graph_context = (
        build_graph_context(graph_paths[:3]) if graph_paths else "无图谱路径"
    )

    prompt = RISK_ASSESSMENT_PROMPT.format(
        context=context or "无文档证据",
        graph_context=graph_context,
        question=question,
        answer=answer[:1500],
    )

    try:
        response = get_chat_client(model).chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content or "{}")
        level = result.get("level", "LOW")
        reason = result.get("reason", "")
        if level not in ("HIGH", "MEDIUM", "LOW"):
            level = "LOW"
        return level, reason
    except Exception:
        return "LOW", ""

SYSTEM_PROMPT = """你是供应链风险分析助手，只能依据用户提供的资料与图谱路径回答问题。
规则：
1. 资料与图谱路径都无法回答时，只回复「知识库中暂无相关资料」，不要在此基础上继续作答。
2. 只能部分回答时，直接说明哪部分资料未覆盖，不要用「知识库中暂无相关资料」开头。
3. 使用了哪条资料，就在句末用 [编号] 标注，编号对应资料前的数字。
4. 引用了哪条图谱路径，就在句末用 [G编号] 标注。
5. 只能引用实际出现的编号，不要编造资料或路径。
6. 用中文回答，结论先行，必要时分点，不要复述资料原文。"""


def _graph_info(question: str, role: str) -> tuple[list[dict], list[dict]]:
    """返回 (影响路径, 命中实体)。Neo4j 不可用时降级为空列表。"""
    try:
        result = impact(question, None, role)
        return result["paths"][:GRAPH_EVIDENCE_LIMIT], result["entities"]
    except Exception:
        return [], []


def _alternatives_context(entities: list[dict], role: str) -> str:
    """命中的实体里有港口/航线时，查出不受影响的替代节点。"""
    port_ids = [e["id"] for e in entities if e["type"] == "port"]
    route_ids = [e["id"] for e in entities if e["type"] == "route"]
    if not port_ids and not route_ids:
        return ""

    parts = []
    for etype, ids in [("port", port_ids), ("route", route_ids)]:
        if not ids:
            continue
        try:
            alts = alternatives(ids, etype, role)
        except Exception:
            continue
        if not alts:
            continue
        label = "替代港口" if etype == "port" else "替代航线"
        items = []
        for a in alts:
            extra = ""
            if serves := a.get("serves"):
                extra = f"（服务 {'、'.join(serves)}）"
            elif connects := a.get("connects"):
                extra = f"（{' ↔ '.join(connects)}）"
            items.append(f"{a['name']}{extra}")
        parts.append(f"{label}：" + "；".join(items))
    return "\n".join(parts)


def _port_route_inventory(role: str) -> str:
    """返回角色可见的港口/航线及其服务关系，供 LLM 推演绕行方案。"""
    try:
        data = overview(role)
        nodes = data["nodes"]
        links = data["links"]
        node_map = {n["id"]: n for n in nodes}
        ports = [n for n in nodes if n["type"] == "port"]
        routes = [n for n in nodes if n["type"] == "route"]

        # 每个港口服务的工厂（factory -[SHIPS_VIA]-> port）
        port_customers: dict[str, list[str]] = {p["id"]: [] for p in ports}
        for link in links:
            if link["relation"] == "SHIPS_VIA":
                target = link["target"]
                source_node = node_map.get(link["source"])
                if target in port_customers and source_node:
                    port_customers[target].append(source_node["name"])

        # 每条航线连接哪些港口（route -[CONNECTS]-> port）
        route_ports: dict[str, list[str]] = {r["id"]: [] for r in routes}
        for link in links:
            if link["relation"] == "CONNECTS":
                source = link["source"]
                target_node = node_map.get(link["target"])
                if source in route_ports and target_node:
                    route_ports[source].append(target_node["name"])

        lines = []
        if ports:
            items = []
            for p in ports:
                served = port_customers.get(p["id"], [])
                suffix = f"（服务 {'、'.join(served)}）" if served else ""
                items.append(f"{p['name']}{suffix}")
            lines.append("可用港口：" + "；".join(items))
        if routes:
            items = []
            for r in routes:
                connected = route_ports.get(r["id"], [])
                suffix = f"（{' ↔ '.join(connected)}）" if connected else ""
                items.append(f"{r['name']}{suffix}")
            lines.append("可用航线：" + "；".join(items))
        return "\n".join(lines)
    except Exception:
        return ""


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
    question: str, hits: list[dict], graph_paths: list[dict], infrastructure: str = ""
) -> list[dict]:
    """把文档证据、图谱路径与基础设施清单编号后拼成提示词。"""
    context = "\n\n".join(
        f"[{index}] 文件：{hit['filename']}（第 {hit['chunk_index'] + 1} 块）\n{hit['text']}"
        for index, hit in enumerate(hits, start=1)
    )
    sections = []
    if context:
        sections.append(f"资料：\n{context}")
    if graph_paths:
        sections.append(f"图谱影响路径：\n{build_graph_context(graph_paths)}")
    if infrastructure:
        sections.append(f"基础设施（推演替代方案时可用）：\n{infrastructure}")
    materials = "\n\n".join(sections) or "（无可用资料）"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{materials}\n\n问题：{question}"},
    ]


def answer_question(
    question: str, role: str, model: str, top_k: int, db, user: User
) -> dict:
    """检索当前角色可访问的证据并生成回答；回答后由 LLM 评估风险等级，HIGH 则建审批单。"""
    hits = search_chunks(question, role, top_k)
    graph_paths, entities = _graph_info(question, role)
    alt_ctx = _alternatives_context(entities, role)
    infra = _port_route_inventory(role)
    extra = "\n\n".join(filter(None, [alt_ctx, infra]))
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
        "messages": build_messages(question, hits, graph_paths, extra),
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

    result: dict = {
        "answer": answer,
        "reasoning": reasoning,
        "model": model,
        "hits": hits,
        "graph_paths": graph_paths,
    }

    # 回答后由 LLM 二次评估风险，所有等级都通知前端，只有 HIGH 建审批单
    level, reason = _assess_risk(question, answer, hits, graph_paths, model)
    result["risk"] = {"level": level, "reason": reason}
    if level == "HIGH":
        approval = create_approval(
            db, question, answer, hits, graph_paths, level, reason, user
        )
        db.commit()
        result["approval"] = {
            "approval_id": approval.approval_id,
            "level": level,
            "reason": reason,
        }
    return result


def stream_answer(
    question: str, role: str, model: str, top_k: int, db, user: User
):
    """边生成边产出事件。回答后 LLM 评估风险，HIGH 则进审批等待人工决定。"""
    hits = search_chunks(question, role, top_k)
    graph_paths, entities = _graph_info(question, role)
    alt_ctx = _alternatives_context(entities, role)
    infra = _port_route_inventory(role)
    extra = "\n\n".join(filter(None, [alt_ctx, infra]))

    yield {"type": "hits", "hits": hits}
    yield {"type": "graph", "paths": graph_paths}

    if not hits and not graph_paths:
        yield {"type": "delta", "text": "知识库中暂无相关资料，无法回答该问题。"}
        yield {"type": "done", "hits": [], "graph_paths": []}
        return

    parameters = {
        "model": model,
        "messages": build_messages(question, hits, graph_paths, extra),
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
    refused = _is_refusal(answer)

    # 回答全部展示完后，LLM 评估风险等级
    approval_id = None
    if not refused:
        level, reason = _assess_risk(question, answer, hits, graph_paths, model)
        yield {"type": "risk", "level": level, "reason": reason}
        if level == "HIGH":
            # 先建审批单，再进入 LangGraph 等待人工决定
            approval = create_approval(
                db, question, answer, hits, graph_paths, level, reason, user
            )
            db.commit()
            approval_id = approval.approval_id
            yield {
                "type": "approval",
                "approval_id": approval_id,
                "level": level,
                "reason": reason,
            }
            # 进入 LangGraph 中断等待（阻塞当前线程）
            enter_approval(approval_id)
            decision = await_decision(approval_id)
            if decision:
                resume_graph(approval_id)

    yield {
        "type": "done",
        "hits": [] if refused else hits,
        "graph_paths": [] if refused else graph_paths,
        "approval_id": approval_id,
    }
