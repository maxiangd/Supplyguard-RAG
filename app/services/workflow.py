"""LangGraph 固定工作流：把检索、图谱、复核、生成、风险评估、审批门编排为状态机。

节点链：
  START → retrieve → graph_analyze → review → build_context
                                                      ↓
                                              [interrupt: assess_risk]
                                                      ↓
                                               assess_risk
                                                      ↓
                                              [risk_level == HIGH?]
                                                 /            \
                                               YES             NO
                                                ↓               ↓
                                         approval_gate      finalize
                                         [interrupt]            ↓
                                                ↓             END
                                             finalize
                                                ↓
                                               END

interrupt_before 设在 assess_risk 和 approval_gate 两个节点。
- 第一个中断让路由处理器在证据就绪后做流式 LLM 生成
- 第二个中断只在 HIGH 风险时触发，等待人工审批决定

使用 LangGraph 的 Command(resume=...) 机制恢复执行，
配合 threading.Event 实现跨 HTTP 请求的等待/唤醒。
"""

import threading
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.services.retrieval import search_chunks
from app.services.graph import alternatives, impact, overview
from app.services.review import review_chunks, review_entities, review_graph_paths

# ---------------------------------------------------------------------------
# 状态定义
# ---------------------------------------------------------------------------
# 从输入到最终输出，所有中间结果都在这里，一个 dict 贯穿全流程


class SupplyGuardState(TypedDict, total=False):
    """工作流状态：每个节点读取需要的字段，写入产出的字段。"""

    # ---- 输入 ----
    question: str
    role: str
    model: str
    top_k: int
    username: str

    # ---- 会话记忆（从 Redis 加载，注入到 build_context_node）----
    session_history: list[dict]
    """最近 N 轮对话的 {question, answer, role, timestamp} 列表"""
    memory_context: str
    """格式化后的对话历史文本，直接注入到提示词"""

    # ---- 检索结果 ----
    hits: list[dict]
    """Qdrant 检索到的文档块（已做角色过滤）"""

    # ---- 图谱结果 ----
    graph_paths: list[dict]
    """多跳影响路径（已过滤不可见节点）"""
    entities: list[dict]
    """问题命中的图谱实体"""
    alt_context: str
    """替代港口/航线的文本描述"""
    infra_context: str
    """角色可见的基础设施清单（港口/航线及其服务关系）"""

    # ---- 复核结果 ----
    review_passed_hits: list[dict]
    """经 Review Node 二次校验的文档块"""
    review_filtered_hits: list[dict]
    """被 Review Node 过滤掉的文档块（记录原因用于排查）"""
    review_passed_paths: list[dict]
    """经 Review Node 二次校验的图谱路径"""
    review_filtered_paths: list[dict]
    """被 Review Node 过滤掉的图谱路径"""

    # ---- 提示词 ----
    messages: list[dict]
    """拼装好的 LLM 对话消息（system + user）"""

    # ---- 生成结果（由路由处理器在中断期间填入）----
    answer: str
    """LLM 生成的最终回答"""
    reasoning: str | None
    """推理模型的思考过程（deepseek-reasoner）"""

    # ---- 风险评估 ----
    risk_level: str
    """HIGH / MEDIUM / LOW"""
    risk_reason: str
    """LLM 给出的风险判断依据"""

    # ---- 审批 ----
    approval_id: str | None
    """审批单 ID（仅 HIGH 时有值）"""
    approval_status: str
    """pending / approved / rejected / skipped"""

    # ---- 错误 ----
    error: str | None
    """节点执行中的错误信息，前端可据此展示降级提示"""


# ---------------------------------------------------------------------------
# 跨请求决策协调
# ---------------------------------------------------------------------------
# SSE 流阻塞在 LangGraph 中断期间，等待管理员的 HTTP 决定请求。
# 用 threading.Event 实现跨请求的等待/唤醒。

_decision_events: dict[str, threading.Event] = {}
"""approval_id → 等待中的 Event，决定端点 set() 后 SSE 线程继续"""

_decision_results: dict[str, dict] = {}
"""approval_id → {"action": "approve"|"reject", "comment": "..."}"""


# ---------------------------------------------------------------------------
# 图谱证据数量上限
# ---------------------------------------------------------------------------
GRAPH_EVIDENCE_LIMIT = 6


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------


def retrieve_node(state: SupplyGuardState) -> dict:
    """检索当前角色可访问的文档块。

    Qdrant 查询层已做 allowed_roles 过滤（admin 不加过滤），
    返回的 hits 交给 Review Node 做二次校验。
    """
    try:
        hits = search_chunks(state["question"], state["role"], state["top_k"])
    except Exception as exc:
        return {"hits": [], "error": f"检索失败: {exc}"}
    return {"hits": hits}


def graph_analyze_node(state: SupplyGuardState) -> dict:
    """图谱影响分析：识别实体、展开多跳路径、查替代方案和基础设施。

    Neo4j 不可用时降级为空列表和空字符串，不影响后续节点执行。
    """
    role = state["role"]
    question = state["question"]

    try:
        result = impact(question, None, role)
        graph_paths = result["paths"][:GRAPH_EVIDENCE_LIMIT]
        entities = result["entities"]
    except Exception:
        graph_paths = []
        entities = []

    alt_ctx = ""
    infra_ctx = ""
    try:
        # 替代方案：命中的港口/航线哪些不受影响
        port_ids = [e["id"] for e in entities if e["type"] == "port"]
        route_ids = [e["id"] for e in entities if e["type"] == "route"]
        alt_parts = []
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
            alt_parts.append(f"{label}：" + "；".join(items))
        alt_ctx = "\n".join(alt_parts)
    except Exception:
        alt_ctx = ""

    try:
        # 基础设施清单：角色可见的港口/航线及服务关系
        data = overview(role)
        node_map = {n["id"]: n for n in data["nodes"]}
        ports = [n for n in data["nodes"] if n["type"] == "port"]
        routes = [n for n in data["nodes"] if n["type"] == "route"]

        port_customers: dict[str, list[str]] = {p["id"]: [] for p in ports}
        for link in data["links"]:
            if link["relation"] == "SHIPS_VIA":
                target = link["target"]
                source_node = node_map.get(link["source"])
                if target in port_customers and source_node:
                    port_customers[target].append(source_node["name"])

        route_ports_map: dict[str, list[str]] = {r["id"]: [] for r in routes}
        for link in data["links"]:
            if link["relation"] == "CONNECTS":
                source = link["source"]
                target_node = node_map.get(link["target"])
                if source in route_ports_map and target_node:
                    route_ports_map[source].append(target_node["name"])

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
                connected = route_ports_map.get(r["id"], [])
                suffix = f"（{' ↔ '.join(connected)}）" if connected else ""
                items.append(f"{r['name']}{suffix}")
            lines.append("可用航线：" + "；".join(items))
        infra_ctx = "\n".join(lines)
    except Exception:
        infra_ctx = ""

    return {
        "graph_paths": graph_paths,
        "entities": entities,
        "alt_context": alt_ctx,
        "infra_context": infra_ctx,
    }


def review_node(state: SupplyGuardState) -> dict:
    """Review Node：对检索和图谱结果做 RBAC 二次校验。

    这是 belt-and-suspenders 安全措施——即使 Qdrant/Neo4j 过滤层
    出现漏洞，Review Node 也会拦截不该看到的数据。
    admin 角色跳过所有校验。
    """
    role = state["role"]

    passed_hits, filtered_hits = review_chunks(state.get("hits", []), role)
    passed_paths, filtered_paths = review_graph_paths(
        state.get("graph_paths", []), role
    )
    passed_entities, _ = review_entities(state.get("entities", []), role)

    return {
        "review_passed_hits": passed_hits,
        "review_filtered_hits": filtered_hits,
        "review_passed_paths": passed_paths,
        "review_filtered_paths": filtered_paths,
        "entities": passed_entities,
    }


# ---- 提示词模板 ----

SYSTEM_PROMPT = """你是供应链风险分析助手，只能依据用户提供的资料与图谱路径回答问题。
规则：
1. 资料与图谱路径都无法回答时，只回复「知识库中暂无相关资料」，不要在此基础上继续作答。
2. 只能部分回答时，直接说明哪部分资料未覆盖，不要用「知识库中暂无相关资料」开头。
3. 使用了哪条资料，就在句末用 [编号] 标注，编号对应资料前的数字。
4. 引用了哪条图谱路径，就在句末用 [G编号] 标注。
5. 只能引用实际出现的编号，不要编造资料或路径。
6. 用中文回答，结论先行，必要时分点，不要复述资料原文。"""


def _build_graph_context(paths: list[dict]) -> str:
    """把影响路径压成带编号的文本，供模型引用。"""
    return "\n".join(
        f"[G{index}] {path['summary']}（{path['rule_label']}，{path['hops']} 跳；"
        f"事件等级 {path['severity']}；原因：{path['reason']}）"
        for index, path in enumerate(paths, start=1)
    )


def build_context_node(state: SupplyGuardState) -> dict:
    """把复核后的文档证据、图谱路径与会话历史拼成 LLM 提示词。

    这是「证据 → 提示词」的唯一组装点，后续节点和路由处理器
    都从这里取 messages。
    """
    hits = state.get("review_passed_hits", state.get("hits", []))
    paths = state.get("review_passed_paths", state.get("graph_paths", []))
    memory_context = state.get("memory_context", "")

    context = "\n\n".join(
        f"[{index}] 文件：{hit['filename']}（第 {hit['chunk_index'] + 1} 块）\n{hit['text']}"
        for index, hit in enumerate(hits, start=1)
    )
    sections = []
    # 会话历史放在最前面，帮助模型理解追问上下文
    if memory_context:
        sections.append(memory_context)
    if context:
        sections.append(f"资料：\n{context}")
    if paths:
        sections.append(f"图谱影响路径：\n{_build_graph_context(paths)}")

    extra = "\n\n".join(
        filter(None, [state.get("alt_context", ""), state.get("infra_context", "")])
    )
    if extra:
        sections.append(f"基础设施（推演替代方案时可用）：\n{extra}")

    materials = "\n\n".join(sections) or "（无可用资料）"

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{materials}\n\n问题：{state['question']}",
            },
        ]
    }


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------

_builder = StateGraph(SupplyGuardState)

# 注册节点
_builder.add_node("retrieve", retrieve_node)
_builder.add_node("graph_analyze", graph_analyze_node)
_builder.add_node("review", review_node)
_builder.add_node("build_context", build_context_node)

# 线性链路：START → retrieve → graph_analyze → review → build_context
_builder.add_edge(START, "retrieve")
_builder.add_edge("retrieve", "graph_analyze")
_builder.add_edge("graph_analyze", "review")
_builder.add_edge("review", "build_context")

# assess_risk 和 approval_gate 由 chat.py 注入（它们依赖 LLM 和 DB session，
# 不便在模块顶层导入）。这里先用占位说明，实际节点通过 add_risk_nodes() 注册。
# 边在 register_risk_and_approval_nodes() 里一次性连好。

# MemorySaver 提供检查点，是 interrupt_before 的前提
_memory = MemorySaver()


def _build_conditional_edge(state: SupplyGuardState) -> str:
    """条件路由：HIGH 进审批门，其他直接到 finalize。"""
    if state.get("risk_level") == "HIGH":
        return "approval_gate"
    return "finalize"


def register_risk_and_approval_nodes(
    assess_risk_fn,
    approval_gate_fn,
    finalize_fn,
) -> StateGraph:
    """注入依赖 LLM 和 DB 的节点，连好边，编译并返回图。

    这样做的好处：
    - workflow 模块不 import chat/approval/audit 模块，避免循环依赖
    - 图结构集中在一处声明，清晰可读
    - 测试时可以用 mock 函数替换这三个节点
    """
    _builder.add_node("assess_risk", assess_risk_fn)
    _builder.add_node("approval_gate", approval_gate_fn)
    _builder.add_node("finalize", finalize_fn)

    # build_context → assess_risk
    _builder.add_edge("build_context", "assess_risk")

    # assess_risk → 条件边 → approval_gate 或 finalize
    _builder.add_conditional_edges("assess_risk", _build_conditional_edge, {
        "approval_gate": "approval_gate",
        "finalize": "finalize",
    })

    # approval_gate → finalize → END
    _builder.add_edge("approval_gate", "finalize")
    _builder.add_edge("finalize", END)

    return _builder.compile(
        interrupt_before=["assess_risk", "approval_gate"],
        checkpointer=_memory,
    )


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------


def get_memory() -> MemorySaver:
    """返回共享的 MemorySaver 实例。"""
    return _memory


def await_decision(approval_id: str, timeout: float = 300) -> dict | None:
    """阻塞等待审批决定（由 /chat/decision 端点唤醒）。

    timeout 秒后仍未决定则返回 None，SSE 流结束。
    """
    event = threading.Event()
    _decision_events[approval_id] = event
    if not event.wait(timeout):
        _decision_events.pop(approval_id, None)
        return None
    return _decision_results.pop(approval_id, None)


def submit_decision(approval_id: str, action: str, comment: str | None) -> bool:
    """提交审批决定并唤醒等待中的 SSE 线程。

    返回 False 表示已有决定（重复提交）。
    """
    if approval_id in _decision_results:
        return False
    _decision_results[approval_id] = {"action": action, "comment": comment or ""}
    event = _decision_events.get(approval_id)
    if event:
        event.set()
    return True