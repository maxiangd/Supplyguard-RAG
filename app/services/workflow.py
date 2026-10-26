"""LangGraph 审批工作流：高风险结论暂停在人工审批节点，等待决定后恢复。

使用 LangGraph 的 interrupt_before + Command(resume=...) 模式。
前端通过 SSE 收到 approval 事件后，调 /api/chat/decision 提交决定。"""

import threading
import uuid
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

# ---------------------------------------------------------------------------
# 会话存储
# ---------------------------------------------------------------------------
_decision_events: dict[str, threading.Event] = {}
_decision_results: dict[str, dict] = {}
_memory = MemorySaver()


# ---------------------------------------------------------------------------
# 图定义
# ---------------------------------------------------------------------------
def _noop(state: dict, config: dict) -> dict:
    """占位节点：所有实际逻辑在 chat.py 里完成，图只负责编排暂停/恢复。"""
    return state


_builder = StateGraph(dict)
_builder.add_node("human_review", _noop)
_builder.add_node("finalize", _noop)
_builder.add_edge(START, "human_review")
_builder.add_edge("human_review", "finalize")
_builder.add_edge("finalize", END)
approval_graph = _builder.compile(
    interrupt_before=["human_review"], checkpointer=_memory
)


# ---------------------------------------------------------------------------
# 公共接口
# ---------------------------------------------------------------------------
def enter_approval(approval_id: str) -> str:
    """进入审批流程，返回 thread_id（即 approval_id）。"""
    config = {"configurable": {"thread_id": approval_id}}
    # invoke 会在 human_review 节点前暂停（interrupt_before）
    approval_graph.invoke({"approval_id": approval_id}, config)
    return approval_id


def await_decision(approval_id: str, timeout: float = 300) -> dict | None:
    """阻塞等待审批决定（由 decision 端点唤醒）。"""
    event = threading.Event()
    _decision_events[approval_id] = event
    if not event.wait(timeout):
        _decision_events.pop(approval_id, None)
        return None
    return _decision_results.pop(approval_id, None)


def submit_decision(approval_id: str, action: str, comment: str | None) -> bool:
    """提交审批决定并唤醒等待方。"""
    result = _decision_results.get(approval_id)
    if result is not None:
        # 已有决定，说明被重复提交
        return False
    _decision_results[approval_id] = {"action": action, "comment": comment or ""}
    event = _decision_events.get(approval_id)
    if event:
        event.set()
    return True


def resume_graph(approval_id: str) -> dict:
    """恢复 LangGraph 执行，走完 finalize。"""
    config = {"configurable": {"thread_id": approval_id}}
    return approval_graph.invoke(Command(resume="approved"), config)