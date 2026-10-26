"""Benchmark 指标计算：precision / recall / F1 / 路径命中率 / 越权拦截率。

所有计算纯函数，不依赖外部服务。
"""

from typing import Any


def compute_metrics(results: list[dict]) -> dict[str, Any]:
    """从 benchmark runner 的结果列表计算汇总指标。

    每条 result 来自 runner 的一次问答测评，包含：
      - expected_entities: list[str]   ground truth 期望命中的实体 ID
      - actual_entities: list[str]     真实链路返回的实体 ID
      - expected_min_paths: int        期望最少路径数
      - actual_paths: int              真实返回路径数
      - expected_path_rules: list[str] 期望出现的传导规则
      - actual_path_rules: list[str]   真实出现的传导规则
      - role_leak: bool                是否发生越权泄漏
      - role: str                      提问角色
      - question: str
    """
    if not results:
        return {"error": "no results to compute"}

    total = len(results)
    role_leaks = [r for r in results if r.get("role_leak")]
    leak_count = len(role_leaks)

    # ---- 实体命中率 ----
    entity_precisions = []
    entity_recalls = []
    for r in results:
        expected = set(r.get("expected_entities", []))
        actual = set(r.get("actual_entities", []))
        if not expected:
            continue  # held-out 用例不算实体指标
        tp = len(expected & actual)
        entity_precisions.append(tp / len(actual) if actual else 0.0)
        entity_recalls.append(tp / len(expected) if expected else 1.0)

    avg_entity_precision = (
        sum(entity_precisions) / len(entity_precisions) if entity_precisions else 0.0
    )
    avg_entity_recall = (
        sum(entity_recalls) / len(entity_recalls) if entity_recalls else 0.0
    )

    # ---- 路径命中率 ----
    path_hits = 0
    path_total = 0
    for r in results:
        expected_min = r.get("expected_min_paths", 0)
        actual = r.get("actual_paths", 0)
        if expected_min > 0:
            path_total += 1
            if actual >= expected_min:
                path_hits += 1

    path_hit_rate = path_hits / path_total if path_total > 0 else 0.0

    # ---- 规则命中率 ----
    rule_precisions = []
    rule_recalls = []
    for r in results:
        expected_rules = set(r.get("expected_path_rules", []))
        actual_rules = set(r.get("actual_path_rules", []))
        if not expected_rules:
            continue
        tp = len(expected_rules & actual_rules)
        rule_precisions.append(tp / len(actual_rules) if actual_rules else 0.0)
        rule_recalls.append(tp / len(expected_rules))

    avg_rule_precision = (
        sum(rule_precisions) / len(rule_precisions) if rule_precisions else 0.0
    )
    avg_rule_recall = (
        sum(rule_recalls) / len(rule_recalls) if rule_recalls else 0.0
    )

    # ---- 越权拦截率 ----
    # 期望越权拦截的用例（cross_role_leak 场景）：expected_min_paths=0
    leak_cases = [r for r in results if r.get("expected_min_paths", 1) == 0
                  and r.get("scenario") == "cross_role_leak"]
    blocked = sum(1 for r in leak_cases if r.get("actual_paths", 0) == 0)

    leak_block_rate = blocked / len(leak_cases) if leak_cases else 1.0

    # ---- 按角色分组 ----
    by_role: dict[str, dict] = {}
    for r in results:
        role = r.get("role", "unknown")
        if role not in by_role:
            by_role[role] = {"total": 0, "leaks": 0, "path_hits": 0, "path_total": 0}
        by_role[role]["total"] += 1
        if r.get("role_leak"):
            by_role[role]["leaks"] += 1
        if r.get("expected_min_paths", 0) > 0:
            by_role[role]["path_total"] += 1
            if r.get("actual_paths", 0) >= r.get("expected_min_paths", 0):
                by_role[role]["path_hits"] += 1

    for role_data in by_role.values():
        role_data["path_hit_rate"] = (
            role_data["path_hits"] / role_data["path_total"]
            if role_data["path_total"] > 0
            else 0.0
        )

    return {
        "total_cases": total,
        "entity_precision": round(avg_entity_precision, 4),
        "entity_recall": round(avg_entity_recall, 4),
        "entity_f1": round(
            2 * avg_entity_precision * avg_entity_recall / (avg_entity_precision + avg_entity_recall)
            if (avg_entity_precision + avg_entity_recall) > 0
            else 0.0,
            4,
        ),
        "path_hit_rate": round(path_hit_rate, 4),
        "rule_precision": round(avg_rule_precision, 4),
        "rule_recall": round(avg_rule_recall, 4),
        "leak_block_rate": round(leak_block_rate, 4),
        "leak_count": leak_count,
        "by_role": {
            role: {
                "total": d["total"],
                "leaks": d["leaks"],
                "path_hit_rate": round(d["path_hit_rate"], 4),
            }
            for role, d in sorted(by_role.items())
        },
    }