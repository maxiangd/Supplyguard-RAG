"""Redis 短期会话记忆：保存最近 N 轮对话，注入到后续问答的提示词中。

存储格式（每个用户一个 Redis key）：
  Key:   supplyguard:session:{username}
  Value: JSON 列表，每项 {question, answer, role, timestamp}
  TTL:   由 settings.memory_session_ttl_seconds 控制
  轮次上限: 由 settings.memory_max_turns 控制
"""

import json
import time

import redis

from app.core.configuration import settings

SESSION_KEY_PREFIX = "supplyguard:session"


def _redis() -> redis.Redis:
    """返回 Redis 连接（每次新建，自动从连接池复用）。"""
    return redis.from_url(settings.redis_url, decode_responses=True)


def _session_key(username: str) -> str:
    """用户会话的 Redis key。"""
    return f"{SESSION_KEY_PREFIX}:{username}"


def get_session_history(username: str) -> list[dict]:
    """读取用户最近的对话轮次（最多 settings.memory_max_turns 条）。"""
    try:
        raw = _redis().get(_session_key(username))
        if not raw:
            return []
        history = json.loads(raw)
        # 只保留最近 N 轮
        max_turns = settings.memory_max_turns
        return history[-max_turns:] if len(history) > max_turns else history
    except Exception:
        return []


def add_turn(username: str, role: str, question: str, answer: str) -> None:
    """在会话末尾追加一轮对话，自动裁剪到轮次上限并刷新 TTL。"""
    try:
        r = _redis()
        key = _session_key(username)
        raw = r.get(key)

        history: list[dict] = json.loads(raw) if raw else []
        history.append(
            {
                "role": role,
                "question": question,
                "answer": answer,
                "timestamp": time.time(),
            }
        )

        # 裁剪到轮次上限
        max_turns = settings.memory_max_turns
        if len(history) > max_turns:
            history = history[-max_turns:]

        # 写回并重置 TTL
        r.set(key, json.dumps(history, ensure_ascii=False))
        r.expire(key, settings.memory_session_ttl_seconds)
    except Exception:
        # Redis 不可用时静默降级，不影响问答主链路
        pass


def clear_session(username: str) -> bool:
    """删除用户的会话历史。返回 True 表示删除成功。"""
    try:
        _redis().delete(_session_key(username))
        return True
    except Exception:
        return False


def build_memory_context(history: list[dict]) -> str:
    """把历史轮次格式化为提示词片段，供 build_context_node 注入。

    返回空字符串表示无历史（调用方直接跳过）。
    """
    if not history:
        return ""

    lines = ["对话历史（最近几轮问答，可用于理解当前问题的上下文）："]
    for index, turn in enumerate(history, start=1):
        lines.append(f"[{index}] 用户：{turn['question']}")
        # 回答截断到 300 字，避免提示词过长
        answer = turn.get("answer", "")
        if len(answer) > 300:
            answer = answer[:300] + "..."
        lines.append(f"    助手：{answer}")
    lines.append("（以上为历史记录，以下为当前问题）")
    return "\n".join(lines)