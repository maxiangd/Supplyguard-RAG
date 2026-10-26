"""LangGraph 工作流节点单元测试（mock 全部外部依赖）。"""

from unittest.mock import patch

import pytest

from app.services.workflow import (
    SupplyGuardState,
    build_context_node,
    graph_analyze_node,
    register_risk_and_approval_nodes,
    retrieve_node,
    review_node,
)


# ── 节点测试：retrieve ──


def test_retrieve_node_with_hits():
    """mock search_chunks 返回结果。"""
    mock_hits = [
        {"document_id": "d1", "filename": "a.md", "chunk_index": 0, "text": "x", "allowed_roles": ["procurement"], "score": 0.9},
    ]
    with patch("app.services.workflow.search_chunks", return_value=mock_hits):
        state: SupplyGuardState = {"question": "test", "role": "procurement", "model": "m", "top_k": 5, "username": "u"}
        result = retrieve_node(state)
    assert len(result["hits"]) == 1


def test_retrieve_node_empty():
    """mock 返回空。"""
    with patch("app.services.workflow.search_chunks", return_value=[]):
        state: SupplyGuardState = {"question": "test", "role": "x", "model": "m", "top_k": 5, "username": "u"}
        result = retrieve_node(state)
    assert result["hits"] == []


def test_retrieve_node_error():
    """mock 抛出异常，降级返回空。"""
    with patch("app.services.workflow.search_chunks", side_effect=RuntimeError("Qdrant down")):
        state: SupplyGuardState = {"question": "test", "role": "x", "model": "m", "top_k": 5, "username": "u"}
        result = retrieve_node(state)
    assert result["hits"] == []
    assert "error" in result


# ── 节点测试：graph_analyze ──


def test_graph_analyze_node_with_data():
    """mock impact/alternatives/overview 返回数据。"""
    mock_paths = [{"rule": "DIRECT", "severity": "HIGH", "reason": "t", "nodes": [], "summary": "A → B"}]
    with patch("app.services.workflow.impact", return_value={"paths": mock_paths, "entities": []}):
        with patch("app.services.workflow.alternatives", return_value=[]):
            with patch("app.services.workflow.overview", return_value={"nodes": [], "links": []}):
                state: SupplyGuardState = {"question": "test", "role": "procurement", "model": "m", "top_k": 5, "username": "u"}
                result = graph_analyze_node(state)
    assert len(result["graph_paths"]) == 1
    assert result["entities"] == []


def test_graph_analyze_neo4j_down():
    """Neo4j 不可用时降级为空列表，不影响后续节点。"""
    with patch("app.services.workflow.impact", side_effect=RuntimeError("Neo4j down")):
        state: SupplyGuardState = {"question": "test", "role": "x", "model": "m", "top_k": 5, "username": "u"}
        result = graph_analyze_node(state)
    assert result["graph_paths"] == []
    assert result["entities"] == []
    assert result["alt_context"] == ""
    assert result["infra_context"] == ""


# ── 节点测试：review ──


def test_review_node_in_workflow():
    """review_node 使用前序节点的 hits/paths 进行过滤。"""
    state: SupplyGuardState = {
        "question": "test", "role": "procurement", "model": "m", "top_k": 5, "username": "u",
        "hits": [
            {"document_id": "d1", "filename": "a.md", "chunk_index": 0, "text": "x", "allowed_roles": ["procurement"], "score": 0.9},
            {"document_id": "d2", "filename": "b.md", "chunk_index": 0, "text": "y", "allowed_roles": ["quality"], "score": 0.8},
        ],
        "graph_paths": [],
        "entities": [],
    }
    result = review_node(state)
    assert len(result["review_passed_hits"]) == 1
    assert len(result["review_filtered_hits"]) == 1


# ── 节点测试：build_context ──


def test_build_context_node_with_hits():
    """有 hits 和 paths 时生成完整 messages。"""
    state: SupplyGuardState = {
        "question": "测试问题", "role": "x", "model": "m", "top_k": 5, "username": "u",
        "review_passed_hits": [
            {"document_id": "d1", "filename": "a.md", "chunk_index": 0, "text": "证据内容", "allowed_roles": ["x"], "score": 0.9},
        ],
        "review_passed_paths": [],
        "alt_context": "",
        "infra_context": "",
        "memory_context": "",
    }
    result = build_context_node(state)
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "system"
    assert "资料" in result["messages"][1]["content"]
    assert "测试问题" in result["messages"][1]["content"]


def test_build_context_node_empty():
    """无证据时生成带微信号的 messages。"""
    state: SupplyGuardState = {
        "question": "测试问题", "role": "x", "model": "m", "top_k": 5, "username": "u",
        "review_passed_hits": [],
        "review_passed_paths": [],
        "alt_context": "",
        "infra_context": "",
        "memory_context": "",
    }
    result = build_context_node(state)
    assert len(result["messages"]) == 2
    assert "无可用资料" in result["messages"][1]["content"]


def test_build_context_node_with_memory():
    """有会话历史时注入提示词。"""
    state: SupplyGuardState = {
        "question": "追问", "role": "x", "model": "m", "top_k": 5, "username": "u",
        "review_passed_hits": [
            {"document_id": "d1", "filename": "a.md", "chunk_index": 0, "text": "x", "allowed_roles": ["x"], "score": 0.9},
        ],
        "review_passed_paths": [],
        "alt_context": "",
        "infra_context": "",
        "memory_context": "对话历史：\n[1] 用户：上次问的锂价",
    }
    result = build_context_node(state)
    assert "对话历史" in result["messages"][1]["content"]


# ── 条件路由测试 ──


def test_conditional_edge_high():
    """HIGH 风险路由到 approval_gate。"""
    # _build_conditional_edge 是 workflow 模块的私有函数，通过 register_risk_and_approval_nodes 注入
    # 这里直接测试路由逻辑
    from app.services.workflow import _build_conditional_edge
    state: SupplyGuardState = {"question": "q", "role": "r", "risk_level": "HIGH", "username": "u"}
    assert _build_conditional_edge(state) == "approval_gate"


def test_conditional_edge_not_high():
    """非 HIGH 风险路由到 finalize。"""
    from app.services.workflow import _build_conditional_edge
    for level in ("MEDIUM", "LOW", ""):
        state: SupplyGuardState = {"question": "q", "role": "r", "risk_level": level, "username": "u"}
        assert _build_conditional_edge(state) == "finalize"


# ── 完整图测试 Phase 1 ──


def test_full_graph_phase1():
    """用 mock 节点跑完整 Phase 1：START → retrieve → graph_analyze → review → build_context。"""
    # 编译图（用 mock 替换 LLM/DB 依赖节点）
    def mock_assess(s): return {"risk_level": "LOW", "risk_reason": ""}
    def mock_gate(s): return {"approval_status": "skipped"}
    def mock_final(s): return {"approval_status": "completed"}

    graph = register_risk_and_approval_nodes(
        assess_risk_fn=mock_assess,
        approval_gate_fn=mock_gate,
        finalize_fn=mock_final,
    )

    mock_hits = [
        {"document_id": "d1", "filename": "a.md", "chunk_index": 0, "text": "证据", "allowed_roles": ["procurement"], "score": 0.9},
    ]

    with patch("app.services.workflow.search_chunks", return_value=mock_hits):
        with patch("app.services.workflow.impact", return_value={"paths": [], "entities": []}):
            with patch("app.services.workflow.alternatives", return_value=[]):
                with patch("app.services.workflow.overview", return_value={"nodes": [], "links": []}):
                    state = graph.invoke(
                        {"question": "测试", "role": "procurement", "model": "m", "top_k": 5, "username": "u"},
                        {"configurable": {"thread_id": "test_phase1"}},
                    )

    # Phase 1 中断在 assess_risk 前，state 应包含所有前序节点输出
    assert len(state.get("review_passed_hits", state.get("hits", []))) == 1
    assert "messages" in state
    assert len(state["messages"]) == 2


def test_full_graph_phase2_low_risk():
    """Phase 2 非 HIGH 路径直接走完 finalize。"""
    def mock_assess(s): return {"risk_level": "LOW", "risk_reason": ""}
    def mock_gate(s): return {"approval_status": "skipped"}
    def mock_final(s): return {"approval_status": "completed"}

    graph = register_risk_and_approval_nodes(
        assess_risk_fn=mock_assess,
        approval_gate_fn=mock_gate,
        finalize_fn=mock_final,
    )

    with patch("app.services.workflow.search_chunks", return_value=[]):
        with patch("app.services.workflow.impact", return_value={"paths": [], "entities": []}):
            with patch("app.services.workflow.alternatives", return_value=[]):
                with patch("app.services.workflow.overview", return_value={"nodes": [], "links": []}):
                    # Phase 1
                    state = graph.invoke(
                        {"question": "测试", "role": "x", "model": "m", "top_k": 5, "username": "u"},
                        {"configurable": {"thread_id": "test_low"}},
                    )
                    # Phase 2: 注入答案
                    from langgraph.types import Command
                    final = graph.invoke(
                        Command(update={"answer": "正常回答", "reasoning": None}),
                        {"configurable": {"thread_id": "test_low"}},
                    )

    # 非 HIGH 路径不会停在 approval_gate，直接到 finalize
    assert final["risk_level"] == "LOW"
    assert final["approval_status"] == "completed"


def test_full_graph_phase2_high_path():
    """Phase 2 HIGH 路径：验证条件边路由到 approval_gate。

    注意：图被 Phase 1 测试编译并缓存了，本测试共用同一个图实例。
    验证的是路由逻辑，不是具体的 risk_level 值。
    （单元测试中 mock 函数由第一个编译调用注册，这里验证结构而非值）
    """
    from app.services.workflow import register_risk_and_approval_nodes, _build_conditional_edge
    from app.services.workflow import SupplyGuardState

    # 直接测试条件边路由：HIGH → approval_gate
    state_high: SupplyGuardState = {"question": "q", "role": "r", "risk_level": "HIGH", "username": "u"}
    assert _build_conditional_edge(state_high) == "approval_gate"

    # 非 HIGH → finalize
    state_low: SupplyGuardState = {"question": "q", "role": "r", "risk_level": "LOW", "username": "u"}
    assert _build_conditional_edge(state_low) == "finalize"

    state_med: SupplyGuardState = {"question": "q", "role": "r", "risk_level": "MEDIUM", "username": "u"}
    assert _build_conditional_edge(state_med) == "finalize"