"""独立 Ground Truth：纯 Python 重算供应链传导规则与实体匹配。

不 import 任何 app 模块、不调 Neo4j/LLM/Qdrant。
所有数据从 seed_data.py 读取（mirror of graph_seed.py）。

用途：Benchmark 运行时对比真实链路输出与 ground truth。
"""

from tests.benchmark.seed_data import EDGES, IMPACTS, NODES

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
TYPE_PRIORITY = {"event": 0, "supplier": 1, "factory": 2, "port": 3, "route": 4, "region": 5}
MAX_ENTITIES = 3


def load_graph() -> dict:
    """返回 {nodes, edges, impacts}。"""
    return {"nodes": NODES, "edges": EDGES, "impacts": IMPACTS}


def _node_map() -> dict[str, dict]:
    """id → node 快速查找。"""
    return {n["id"]: n for n in NODES}


def _edges_by_source(source_id: str) -> list[dict]:
    """从一个节点出发的所有边。"""
    return [e for e in EDGES if e["source"] == source_id]


def _edges_by_target(target_id: str) -> list[dict]:
    """到达一个节点的所有边。"""
    return [e for e in EDGES if e["target"] == target_id]


def _visible(node: dict, role: str) -> bool:
    """角色可见性检查。"""
    return role == "admin" or role in (node.get("allowed_roles") or [])


# ── 实体匹配 ──


def match_entities(question: str) -> list[str]:
    """用节点名与别名做关键词匹配，长匹配优先。

    与 graph.py 的 match_entities 逻辑一致：
    - 如果命中任何 event，则排除 region/port/route 类型
    - 最多返回 MAX_ENTITIES 个实体
    """
    candidates: list[tuple[int, dict]] = []
    for node in NODES:
        terms = [node["name"], *(node.get("aliases") or [])]
        hits = [term for term in terms if term and term in question]
        if hits:
            candidates.append((max(len(t) for t in hits), node))

    candidates.sort(key=lambda item: (-item[0], TYPE_PRIORITY.get(item[1]["type"], 9)))

    # event 命中时排除 region/port/route
    if any(node["type"] == "event" for _, node in candidates):
        candidates = [
            item for item in candidates
            if item[1]["type"] not in ("region", "port", "route")
        ]

    entities: list[str] = []
    for _, node in candidates:
        if node["id"] not in entities:
            entities.append(node["id"])
        if len(entities) >= MAX_ENTITIES:
            break
    return entities


# ── 路径计算 ──


def _supplier_factories(supplier_id: str, role: str) -> list[dict]:
    """该供应商供应的工厂。"""
    nodes = _node_map()
    result = []
    for e in _edges_by_source(supplier_id):
        if e["relation"] == "SUPPLIES" and e["target"] in nodes:
            target = nodes[e["target"]]
            if target["type"] == "factory" and _visible(target, role):
                result.append(target)
    return result


def _factory_ports(factory_id: str, role: str) -> list[dict]:
    """工厂的出海口。"""
    nodes = _node_map()
    result = []
    for e in _edges_by_source(factory_id):
        if e["relation"] == "SHIPS_VIA" and e["target"] in nodes:
            target = nodes[e["target"]]
            if target["type"] == "port" and _visible(target, role):
                result.append(target)
    return result


def _region_children(region_id: str, role: str) -> list[tuple[dict, str]]:
    """地区上的供应商（SOURCED_FROM）与工厂（LOCATED_IN）。"""
    nodes = _node_map()
    result = []
    for e in _edges_by_target(region_id):
        if e["relation"] in ("SOURCED_FROM", "LOCATED_IN"):
            if e["source"] in nodes:
                source = nodes[e["source"]]
                if _visible(source, role):
                    result.append((source, e["relation"]))
    return result


def _port_factories(port_id: str, role: str) -> list[dict]:
    """经该港口出货的工厂。"""
    nodes = _node_map()
    result = []
    for e in _edges_by_target(port_id):
        if e["relation"] == "SHIPS_VIA" and e["source"] in nodes:
            source = nodes[e["source"]]
            if source["type"] == "factory" and _visible(source, role):
                result.append(source)
    return result


def _route_ports(route_id: str, role: str) -> list[dict]:
    """航线连接的两端港口。"""
    nodes = _node_map()
    result = []
    for e in _edges_by_source(route_id):
        if e["relation"] == "CONNECTS" and e["target"] in nodes:
            target = nodes[e["target"]]
            if target["type"] == "port" and _visible(target, role):
                result.append(target)
    return result


def _affecting_events(entity_id: str, role: str) -> list[dict]:
    """找出影响该实体的风险事件。"""
    nodes = _node_map()
    result = []
    for imp in IMPACTS:
        if imp["target"] == entity_id and imp["event"] in nodes:
            event = nodes[imp["event"]]
            if _visible(event, role):
                result.append({**imp, "event_node": event})
    return result


def _build_path(rule: str, severity: str, reason: str, node_list: list[dict], rel_list: list[str]) -> dict:
    """组装路径字典。"""
    return {
        "rule": rule,
        "severity": severity,
        "reason": reason,
        "hops": len(node_list) - 1,
        "summary": " → ".join(n["name"] for n in node_list),
        "node_ids": [n["id"] for n in node_list],
    }


def _expand_direct_downstream(
    node: dict, role: str, rule: str, severity: str, reason: str,
    prefix_nodes: list[dict], prefix_rels: list[str], max_hops: int,
) -> list[dict]:
    """从已受影响的节点继续往下游展开：supplier→工厂→港口。"""
    paths = []
    if node["type"] == "supplier":
        for factory in _supplier_factories(node["id"], role):
            current_nodes = [*prefix_nodes, factory]
            current_rels = [*prefix_rels, "SUPPLIES"]
            if len(current_nodes) - 1 <= max_hops:
                paths.append(_build_path(rule, severity, reason, current_nodes, current_rels))
                for port in _factory_ports(factory["id"], role):
                    if len(current_nodes) - 1 < max_hops:
                        paths.append(_build_path(
                            rule, severity, reason,
                            [*current_nodes, port], [*current_rels, "SHIPS_VIA"],
                        ))
    elif node["type"] == "factory":
        for port in _factory_ports(node["id"], role):
            if len(prefix_nodes) <= max_hops:
                paths.append(_build_path(
                    rule, severity, reason,
                    [*prefix_nodes, port], [*prefix_rels, "SHIPS_VIA"],
                ))
    return paths


def _entity_paths(entity: dict, role: str, max_hops: int) -> list[dict]:
    """从非事件实体展开路径：supplier→工厂→港口。"""
    paths: list[dict] = []
    etype = entity["type"]
    severity = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}.get(
        entity.get("risk_level", "medium"), "MEDIUM"
    )
    reason = f"{entity['name']}相关风险"

    if etype == "supplier":
        for factory in _supplier_factories(entity["id"], role):
            paths.append(_build_path("SUPPLY", severity, reason, [entity, factory], ["SUPPLIES"]))
            if max_hops >= 2:
                for port in _factory_ports(factory["id"], role):
                    paths.append(_build_path("SUPPLY", severity, reason, [entity, factory, port], ["SUPPLIES", "SHIPS_VIA"]))
    elif etype == "factory":
        for port in _factory_ports(entity["id"], role):
            paths.append(_build_path("SUPPLY", severity, reason, [entity, port], ["SHIPS_VIA"]))
    elif etype == "region":
        for child, relation in _region_children(entity["id"], role):
            paths.append(_build_path("REGION", severity, reason, [entity, child], [relation]))
            paths.extend(_expand_direct_downstream(
                child, role, "REGION", severity, reason, [entity, child], [relation], max_hops,
            ))
    elif etype == "port":
        for factory in _port_factories(entity["id"], role):
            paths.append(_build_path("PORT", severity, reason, [entity, factory], ["SHIPS_VIA"]))
    elif etype == "route":
        for port in _route_ports(entity["id"], role):
            paths.append(_build_path("ROUTE", severity, reason, [entity, port], ["CONNECTS"]))
            if max_hops >= 2:
                for factory in _port_factories(port["id"], role):
                    paths.append(_build_path("ROUTE", severity, reason, [entity, port, factory], ["CONNECTS", "SHIPS_VIA"]))
    return paths


def _event_paths(event: dict, role: str, max_hops: int) -> list[dict]:
    """从事件出发，按 AFFECTS 上标注的规则做多跳展开。"""
    nodes = _node_map()
    paths: list[dict] = []

    for imp in IMPACTS:
        if imp["event"] != event["id"]:
            continue
        target_id = imp["target"]
        if target_id not in nodes:
            continue
        target = nodes[target_id]
        if not _visible(target, role):
            continue

        rule = imp["rule"]
        severity = imp["severity"] or "MEDIUM"
        reason = imp["reason"] or ""

        if rule == "DIRECT":
            paths.append(_build_path("DIRECT", severity, reason, [event, target], ["AFFECTS"]))
            paths.extend(_expand_direct_downstream(
                target, role, "DIRECT", severity, reason, [event, target], ["AFFECTS"], max_hops,
            ))
        elif rule == "REGION":
            for child, relation in _region_children(target["id"], role):
                paths.append(_build_path("REGION", severity, reason, [event, target, child], ["AFFECTS", relation]))
                paths.extend(_expand_direct_downstream(
                    child, role, "REGION", severity, reason,
                    [event, target, child], ["AFFECTS", relation], max_hops,
                ))
        elif rule == "PORT":
            for factory in _port_factories(target["id"], role):
                if max_hops >= 2:
                    paths.append(_build_path("PORT", severity, reason, [event, target, factory], ["AFFECTS", "SHIPS_VIA"]))
        elif rule == "ROUTE":
            for port in _route_ports(target["id"], role):
                if max_hops >= 2:
                    paths.append(_build_path("ROUTE", severity, reason, [event, target, port], ["AFFECTS", "CONNECTS"]))
                for factory in _port_factories(port["id"], role):
                    if max_hops >= 3:
                        paths.append(_build_path("ROUTE", severity, reason, [event, target, port, factory], ["AFFECTS", "CONNECTS", "SHIPS_VIA"]))
    return paths


def compute_paths(entity_ids: list[str], role: str = "admin", max_hops: int = 3) -> list[dict]:
    """对识别出的实体逐个展开，合并去重排序后返回。"""
    nodes = _node_map()
    all_paths: list[dict] = []

    for eid in entity_ids:
        if eid not in nodes:
            continue
        entity = nodes[eid]
        if entity["type"] == "event":
            all_paths.extend(_event_paths(entity, role, max_hops))
            continue

        severity = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}.get(
            entity.get("risk_level", "medium"), "MEDIUM"
        )
        reason = f"{entity['name']}相关风险"

        base_paths = _entity_paths(entity, role, max_hops)
        events = _affecting_events(eid, role)

        if not events:
            all_paths.extend(base_paths)
            continue

        # 实体本身有因果上下文（事件），用事件作为路径起点
        prefix_bases = [_build_path("SUPPLY", severity, reason, [entity], [])] + base_paths
        for evt_info in events:
            evt = evt_info["event_node"]
            for base in prefix_bases:
                if base["hops"] + 1 > max_hops:
                    continue
                # 从事件到实体的 AFFECTS 关系，后续沿用 SUPPLIES 链路
                downstream_rels = ["SUPPLIES"] * base["hops"] if base["hops"] > 0 else []
                all_paths.append(_build_path(
                    evt_info["rule"],
                    evt_info["severity"] or severity,
                    evt_info["reason"] or "",
                    [evt, *([nodes[nid] for nid in base["node_ids"] if nid in nodes])],
                    ["AFFECTS"] + downstream_rels,
                ))

    # 去重：rule + 节点序列
    unique: dict[tuple, dict] = {}
    for p in all_paths:
        key = (p["rule"], tuple(p["node_ids"]))
        unique.setdefault(key, p)

    visible_paths = list(unique.values())

    # 按角色过滤路径中的每个节点
    if role != "admin":
        visible_paths = [
            p for p in visible_paths
            if all(_visible(nodes.get(nid, {}), role) for nid in p["node_ids"])
        ]

    visible_paths.sort(
        key=lambda p: (p["hops"], -SEVERITY_RANK.get(p["severity"], 1), p["rule"], p["summary"])
    )
    return visible_paths[:40]


def expected_paths_for_case(question: str, role: str) -> dict:
    """一站式接口：匹配实体 + 计算路径。"""
    entity_ids = match_entities(question)
    paths = compute_paths(entity_ids, role)
    rules = list(set(p["rule"] for p in paths))
    return {
        "entity_ids": entity_ids,
        "paths": paths,
        "path_count": len(paths),
        "rules_used": rules,
    }


def compute_visible_docs(role: str) -> set[str]:
    """返回该角色可见的文档 source 集合。"""
    docs = set()
    for node in NODES:
        if _visible(node, role):
            src = node.get("source", "")
            if src:
                docs.add(src)
    return docs