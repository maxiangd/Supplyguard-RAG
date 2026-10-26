"""图谱服务：按角色取子图、识别问题中的实体、计算多跳影响路径。"""

from app.db.graph_database import run_query

RULE_LABELS = {
    "DIRECT": "直接传导",
    "REGION": "地区传导",
    "PORT": "港口传导",
    "ROUTE": "航线传导",
    "SUPPLY": "供应传导",
}

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
RISK_TO_SEVERITY = {"high": "HIGH", "medium": "MEDIUM", "low": "LOW"}

# 同一问题命中多个实体时，事件优先级最高：事件本身就带传导规则
TYPE_PRIORITY = {"event": 0, "supplier": 1, "factory": 2, "port": 3, "route": 4, "region": 5}

MAX_ENTITIES = 3
MAX_PATHS = 40


def _visible(node: dict, role: str) -> bool:
    """管理员看全图，其他角色只能看到 allowed_roles 包含自己的节点。"""
    return role == "admin" or role in (node.get("allowed_roles") or [])


def _public(node: dict) -> dict:
    """对外只暴露展示字段，不返回别名和权限列表。"""
    return {
        "id": node["id"],
        "name": node["name"],
        "type": node["type"],
        "risk_level": node.get("risk_level"),
        "region": node.get("region"),
        "desc": node.get("desc"),
    }


def _load_nodes(role: str) -> list[dict]:
    """加载当前角色可见的全部节点。"""
    records = run_query(
        "MATCH (n:Entity) RETURN n AS node ORDER BY n.type, n.id"
    )
    nodes = [record["node"] for record in records]
    return [node for node in nodes if _visible(node, role)]


def overview(role: str) -> dict:
    """返回角色可见的节点与两端都可见的关系，供前端画图。"""
    nodes = _load_nodes(role)
    node_ids = {node["id"] for node in nodes}

    records = run_query(
        "MATCH (a:Entity)-[r]->(b:Entity) "
        "RETURN a.id AS source, b.id AS target, type(r) AS relation, properties(r) AS properties"
    )
    links = []
    for record in records:
        if record["source"] not in node_ids or record["target"] not in node_ids:
            continue
        properties = record["properties"] or {}
        detail = properties.get("material") or properties.get("reason") or ""
        links.append(
            {
                "source": record["source"],
                "target": record["target"],
                "relation": record["relation"],
                "detail": detail,
            }
        )

    return {"nodes": [_public(node) for node in nodes], "links": links}


def match_entities(question: str, role: str) -> list[dict]:
    """用节点名与别名做规则匹配，长别名优先，避免「宁德」抢走「宁德漳湾基地」。"""
    candidates = []
    for node in _load_nodes(role):
        terms = [node["name"], *(node.get("aliases") or [])]
        hits = [term for term in terms if term and term in question]
        if hits:
            candidates.append((max(len(term) for term in hits), node))

    candidates.sort(
        key=lambda item: (-item[0], TYPE_PRIORITY.get(item[1]["type"], 9))
    )

    # 事件本身就会展开到地区/港口/航线，没必要再把这几个实体单独走一遍
    if any(node["type"] == "event" for _, node in candidates):
        candidates = [
            item
            for item in candidates
            if item[1]["type"] not in ("region", "port", "route")
        ]

    entities = []
    for _, node in candidates:
        if node["id"] not in {entity["id"] for entity in entities}:
            entities.append(node)
        if len(entities) >= MAX_ENTITIES:
            break
    return entities


def _node(node_id: str) -> dict | None:
    """按 ID 取单个节点。"""
    records = run_query(
        "MATCH (n:Entity {id: $id}) RETURN n AS node", {"id": node_id}
    )
    return records[0]["node"] if records else None


def _supplier_factories(supplier_id: str, role: str) -> list[tuple[dict, dict]]:
    """供应商供货的工厂及其关系属性。"""
    records = run_query(
        "MATCH (s:Entity {id: $id})-[r:SUPPLIES]->(f:Entity) "
        "RETURN f AS node, properties(r) AS properties",
        {"id": supplier_id},
    )
    return [
        (record["node"], record["properties"] or {})
        for record in records
        if _visible(record["node"], role)
    ]


def _factory_ports(factory_id: str, role: str) -> list[dict]:
    """工厂的出海口。"""
    records = run_query(
        "MATCH (f:Entity {id: $id})-[:SHIPS_VIA]->(p:Entity) RETURN p AS node",
        {"id": factory_id},
    )
    return [record["node"] for record in records if _visible(record["node"], role)]


def _region_children(region_id: str, role: str) -> list[tuple[dict, str]]:
    """地区上的供应商（原料来源）与工厂（本地生产）。"""
    records = run_query(
        "MATCH (reg:Entity {id: $id})<-[r:SOURCED_FROM|LOCATED_IN]-(x:Entity) "
        "RETURN x AS node, type(r) AS relation",
        {"id": region_id},
    )
    return [
        (record["node"], record["relation"])
        for record in records
        if _visible(record["node"], role)
    ]


def _port_factories(port_id: str, role: str) -> list[dict]:
    """经该港口出货的工厂。"""
    records = run_query(
        "MATCH (p:Entity {id: $id})<-[:SHIPS_VIA]-(f:Entity) RETURN f AS node",
        {"id": port_id},
    )
    return [record["node"] for record in records if _visible(record["node"], role)]


def _route_ports(route_id: str, role: str) -> list[dict]:
    """航线连接的两端港口。"""
    records = run_query(
        "MATCH (rt:Entity {id: $id})-[:CONNECTS]->(p:Entity) RETURN p AS node",
        {"id": route_id},
    )
    return [record["node"] for record in records if _visible(record["node"], role)]


def _affecting_events(entity_id: str, role: str) -> list[dict]:
    """找出影响该实体的风险事件，用来给下游路径补上因果起点。"""
    records = run_query(
        "MATCH (e:Entity {type: 'event'})-[a:AFFECTS]->(n:Entity {id: $id}) "
        "RETURN e AS node, a.rule AS rule, a.severity AS severity, a.reason AS reason",
        {"id": entity_id},
    )
    return [
        record for record in records if _visible(record["node"], role)
    ]


def _build_path(
    rule: str,
    severity: str,
    reason: str,
    nodes: list[dict],
    relations: list[str],
) -> dict:
    """把节点序列和关系序列拼成前端可直接消费的路径。"""
    links = [
        {
            "source": nodes[index]["id"],
            "target": nodes[index + 1]["id"],
            "relation": relations[index],
        }
        for index in range(len(relations))
    ]
    return {
        "rule": rule,
        "rule_label": RULE_LABELS[rule],
        "severity": severity,
        "reason": reason,
        "hops": len(nodes) - 1,
        "summary": " → ".join(node["name"] for node in nodes),
        "nodes": [_public(node) for node in nodes],
        "links": links,
        "affected": nodes[-1]["id"],
    }


def _downstream_paths(
    node: dict,
    role: str,
    rule: str,
    severity: str,
    reason: str,
    prefix_nodes: list[dict],
    prefix_relations: list[str],
    max_hops: int,
) -> list[dict]:
    """沿着「供应商→工厂→港口」继续往下游走，对已受影响的节点补齐路径。"""
    paths = []
    if node["type"] == "supplier":
        for factory, _ in _supplier_factories(node["id"], role):
            nodes = [*prefix_nodes, factory]
            relations = [*prefix_relations, "SUPPLIES"]
            if len(nodes) - 1 > max_hops:
                continue
            paths.append(_build_path(rule, severity, reason, nodes, relations))
            for port in _factory_ports(factory["id"], role):
                if len(nodes) - 1 >= max_hops:
                    continue
                paths.append(
                    _build_path(
                        rule,
                        severity,
                        reason,
                        [*nodes, port],
                        [*relations, "SHIPS_VIA"],
                    )
                )
    elif node["type"] == "factory":
        for port in _factory_ports(node["id"], role):
            nodes = [*prefix_nodes, port]
            if len(nodes) - 1 > max_hops:
                continue
            paths.append(
                _build_path(
                    rule, severity, reason, nodes, [*prefix_relations, "SHIPS_VIA"]
                )
            )
    return paths


def _expand_entity(
    entity: dict, role: str, max_hops: int, rule: str, severity: str, reason: str
) -> list[dict]:
    """从一个实体出发，按类型向上下游展开路径。"""
    paths: list[dict] = []
    entity_type = entity["type"]

    if entity_type == "supplier":
        for factory, _ in _supplier_factories(entity["id"], role):
            paths.append(
                _build_path(
                    "SUPPLY", severity, reason, [entity, factory], ["SUPPLIES"]
                )
            )
            if max_hops >= 2:
                for port in _factory_ports(factory["id"], role):
                    paths.append(
                        _build_path(
                            "SUPPLY",
                            severity,
                            reason,
                            [entity, factory, port],
                            ["SUPPLIES", "SHIPS_VIA"],
                        )
                    )
    elif entity_type == "factory":
        for port in _factory_ports(entity["id"], role):
            paths.append(
                _build_path(
                    "SUPPLY", severity, reason, [entity, port], ["SHIPS_VIA"]
                )
            )
    elif entity_type == "region":
        for child, relation in _region_children(entity["id"], role):
            paths.append(
                _build_path(
                    "REGION", severity, reason, [entity, child], [relation]
                )
            )
            paths.extend(
                _downstream_paths(
                    child,
                    role,
                    "REGION",
                    severity,
                    reason,
                    [entity, child],
                    [relation],
                    max_hops,
                )
            )
    elif entity_type == "port":
        for factory in _port_factories(entity["id"], role):
            paths.append(
                _build_path(
                    "PORT", severity, reason, [entity, factory], ["SHIPS_VIA"]
                )
            )
    elif entity_type == "route":
        for port in _route_ports(entity["id"], role):
            paths.append(
                _build_path(
                    "ROUTE", severity, reason, [entity, port], ["CONNECTS"]
                )
            )
            for factory in _port_factories(port["id"], role):
                if max_hops >= 2:
                    paths.append(
                        _build_path(
                            "ROUTE",
                            severity,
                            reason,
                            [entity, port, factory],
                            ["CONNECTS", "SHIPS_VIA"],
                        )
                    )
    return paths


def _event_paths(event: dict, role: str, max_hops: int) -> list[dict]:
    """从事件出发，按 AFFECTS 上标注的规则做多跳展开。"""
    records = run_query(
        "MATCH (e:Entity {id: $id})-[a:AFFECTS]->(t:Entity) "
        "RETURN t AS node, a.rule AS rule, a.severity AS severity, a.reason AS reason",
        {"id": event["id"]},
    )

    paths = []
    for record in records:
        target = record["node"]
        if not _visible(target, role):
            continue
        rule = record["rule"]
        severity = record["severity"] or "MEDIUM"
        reason = record["reason"] or ""

        if rule == "DIRECT":
            paths.append(
                _build_path(
                    "DIRECT", severity, reason, [event, target], ["AFFECTS"]
                )
            )
            paths.extend(
                _downstream_paths(
                    target,
                    role,
                    "DIRECT",
                    severity,
                    reason,
                    [event, target],
                    ["AFFECTS"],
                    max_hops,
                )
            )
        elif rule == "REGION":
            for child, relation in _region_children(target["id"], role):
                paths.append(
                    _build_path(
                        "REGION",
                        severity,
                        reason,
                        [event, target, child],
                        ["AFFECTS", relation],
                    )
                )
                paths.extend(
                    _downstream_paths(
                        child,
                        role,
                        "REGION",
                        severity,
                        reason,
                        [event, target, child],
                        ["AFFECTS", relation],
                        max_hops,
                    )
                )
        elif rule == "PORT":
            for factory in _port_factories(target["id"], role):
                if max_hops >= 2:
                    paths.append(
                        _build_path(
                            "PORT",
                            severity,
                            reason,
                            [event, target, factory],
                            ["AFFECTS", "SHIPS_VIA"],
                        )
                    )
        elif rule == "ROUTE":
            for port in _route_ports(target["id"], role):
                if max_hops >= 2:
                    paths.append(
                        _build_path(
                            "ROUTE",
                            severity,
                            reason,
                            [event, target, port],
                            ["AFFECTS", "CONNECTS"],
                        )
                    )
                for factory in _port_factories(port["id"], role):
                    if max_hops >= 3:
                        paths.append(
                            _build_path(
                                "ROUTE",
                                severity,
                                reason,
                                [event, target, port, factory],
                                ["AFFECTS", "CONNECTS", "SHIPS_VIA"],
                            )
                        )
    return paths


def impact_paths(entities: list[dict], role: str, max_hops: int = 3) -> list[dict]:
    """对识别出的实体逐个展开，合并后按规则、跳数与严重度排序。"""
    paths: list[dict] = []
    for entity in entities:
        if entity["type"] == "event":
            paths.extend(_event_paths(entity, role, max_hops))
            continue

        severity = RISK_TO_SEVERITY.get(entity.get("risk_level"), "MEDIUM")
        reason = f"{entity['name']}相关风险"
        base_paths = _expand_entity(entity, role, max_hops, "SUPPLY", severity, reason)
        events = _affecting_events(entity["id"], role)
        if not events:
            paths.extend(base_paths)
            continue

        # 实体本身没有因果上下文，用影响它的事件作为路径起点，避免回答缺少风险来源
        # 零跳起点让「事件 → 实体」也能成立，不依赖该角色是否看得到下游港口
        prefix_bases = [
            _build_path("SUPPLY", severity, reason, [entity], []),
            *base_paths,
        ]
        for record in events:
            event = record["node"]
            for path in prefix_bases:
                if path["hops"] + 1 > max_hops:
                    continue
                paths.append(
                    _build_path(
                        record["rule"],
                        record["severity"] or severity,
                        record["reason"] or "",
                        [event, *path["nodes"]],
                        ["AFFECTS", *[link["relation"] for link in path["links"]]],
                    )
                )

    unique: dict[tuple, dict] = {}
    for path in paths:
        key = (path["rule"], tuple(node["id"] for node in path["nodes"]))
        unique.setdefault(key, path)

    # 每条路径的节点都来自上面带 _visible 过滤的查询，这里只需去重与排序
    visible_paths = list(unique.values())

    visible_paths.sort(
        key=lambda path: (
            path["hops"],
            -SEVERITY_RANK.get(path["severity"], 0),
            path["rule"],
            path["summary"],
        )
    )
    return visible_paths[:MAX_PATHS]


def impact(question: str | None, entity_id: str | None, role: str, max_hops: int = 3) -> dict:
    """问答与图谱页共用的入口：问题或实体名 → 命中实体与影响路径。"""
    entities: list[dict] = []
    if question:
        entities = match_entities(question, role)
    elif entity_id:
        node = _node(entity_id)
        if node and _visible(node, role):
            entities = [node]

    paths = impact_paths(entities, role, max_hops)
    return {
        "entities": [_public(entity) for entity in entities],
        "paths": paths,
    }


def alternatives(entity_ids: list[str], entity_type: str, role: str) -> list[dict]:
    """找出不受影响、可替代的同类型节点。

    港口替代：查哪些港口没有被 AFFECTS 边指向且服务相同工厂。
    航线替代：查哪些航线没有被 AFFECTS 边指向且连接相同区域。
    """
    if entity_type == "port":
        return _port_alternatives(entity_ids, role)
    if entity_type == "route":
        return _route_alternatives(entity_ids, role)
    return []


def _port_alternatives(disrupted_ids: list[str], role: str) -> list[dict]:
    """排除受影响的港口，返回角色可见的其他港口。"""
    # 找出受影响港口服务的工厂
    factory_records = run_query(
        "MATCH (f:Entity {type: 'factory'})-[:SHIPS_VIA]->(p:Entity) "
        "WHERE p.id IN $ids RETURN DISTINCT f.id AS fid, f.name AS fname",
        {"ids": disrupted_ids},
    )
    factory_map = {r["fid"]: r["fname"] for r in factory_records}

    # 找有哪些港口被事件影响了（有 AFFECTS 入边的港口）
    affected_records = run_query(
        "MATCH (e:Entity {type: 'event'})-[a:AFFECTS]->(p:Entity {type: 'port'}) "
        "RETURN DISTINCT p.id AS pid"
    )
    affected_ids = {r["pid"] for r in affected_records} | set(disrupted_ids)

    # 查所有角色可见且未被影响的港口
    all_ports = _load_nodes(role)
    candidates = [p for p in all_ports if p["type"] == "port" and p["id"] not in affected_ids]

    result = []
    for port in candidates:
        # 查该港口服务哪些工厂（从上面 factory_map 的工厂里）
        serving = run_query(
            "MATCH (f:Entity)-[:SHIPS_VIA]->(p:Entity {id: $pid}) "
            "WHERE f.id IN $fids RETURN f.name AS name",
            {"pid": port["id"], "fids": list(factory_map.keys())},
        )
        serves = [r["name"] for r in serving]
        # 也查该港口服务的所有工厂，用于通用替代
        all_serving = run_query(
            "MATCH (f:Entity {type: 'factory'})-[:SHIPS_VIA]->(p:Entity {id: $pid}) "
            "RETURN f.name AS name",
            {"pid": port["id"]},
        )
        all_serves = [r["name"] for r in all_serving if _visible(r, role)]

        entry = _public(port)
        entry["serves"] = serves if serves else all_serves
        result.append(entry)

    # 按"能服务多少受影响工厂"排序
    result.sort(key=lambda p: len(p.get("serves", [])), reverse=True)
    return result


def _route_alternatives(disrupted_ids: list[str], role: str) -> list[dict]:
    """排除受影响的航线，返回角色可见的其他航线。"""
    affected_records = run_query(
        "MATCH (e:Entity {type: 'event'})-[a:AFFECTS]->(r:Entity {type: 'route'}) "
        "RETURN DISTINCT r.id AS rid"
    )
    affected_ids = {r["rid"] for r in affected_records} | set(disrupted_ids)

    all_nodes = _load_nodes(role)
    candidates = [n for n in all_nodes if n["type"] == "route" and n["id"] not in affected_ids]

    result = []
    for route in candidates:
        ports = run_query(
            "MATCH (rt:Entity {id: $rid})-[:CONNECTS]->(p:Entity) "
            "RETURN p.name AS name",
            {"rid": route["id"]},
        )
        entry = _public(route)
        entry["connects"] = [r["name"] for r in ports]
        result.append(entry)

    return result