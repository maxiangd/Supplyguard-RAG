"""Review Node 单元测试：RBAC 二次校验逻辑。"""

from app.services.review import review_chunks, review_entities, review_graph_paths


def _chunk(allowed_roles: list[str], doc_id: str = "d1", filename: str = "test.md"):
    """快捷构造测试用的文档块。"""
    return {
        "document_id": doc_id,
        "filename": filename,
        "chunk_index": 0,
        "text": "test content",
        "allowed_roles": allowed_roles,
        "score": 0.95,
    }


def _path(node_roles_list: list[list[str] | None]):
    """构造测试用的图谱路径。node_roles_list 每个元素是一个节点的 allowed_roles（None 表示无该字段）。"""
    nodes = []
    for i, roles in enumerate(node_roles_list):
        node = {"id": f"n{i}", "name": f"Node{i}", "type": "factory"}
        if roles is not None:
            node["allowed_roles"] = roles
        nodes.append(node)
    return {
        "rule": "DIRECT",
        "severity": "HIGH",
        "reason": "test",
        "hops": len(nodes) - 1,
        "summary": " → ".join(n["name"] for n in nodes),
        "nodes": nodes,
        "links": [],
        "affected": nodes[-1]["id"],
    }


# ── review_chunks ──


def test_review_chunks_admin_bypass():
    """admin 角色全部通过，不过滤。"""
    chunks = [_chunk(["procurement"]), _chunk(["admin"])]
    passed, filtered = review_chunks(chunks, "admin")
    assert len(passed) == 2
    assert len(filtered) == 0


def test_review_chunks_role_filter():
    """procurement 只保留 allowed_roles 包含 procurement 的块。"""
    chunks = [
        _chunk(["procurement", "finance"]),
        _chunk(["quality"]),
        _chunk(["admin"]),
    ]
    passed, filtered = review_chunks(chunks, "procurement")
    assert len(passed) == 1
    assert passed[0]["allowed_roles"] == ["procurement", "finance"]
    assert len(filtered) == 2


def test_review_chunks_empty_input():
    """空输入返回空。"""
    passed, filtered = review_chunks([], "procurement")
    assert passed == []
    assert filtered == []


def test_review_chunks_no_allowed_roles_field():
    """缺少 allowed_roles 字段的块当作不可见处理。"""
    chunks = [{"document_id": "d1", "filename": "f.md", "chunk_index": 0, "text": "x"}]
    passed, filtered = review_chunks(chunks, "procurement")
    assert len(passed) == 0
    assert len(filtered) == 1


# ── review_graph_paths ──


def test_review_graph_paths_admin_bypass():
    """admin 看到全部路径。"""
    paths = [
        _path([["procurement"], ["quality"]]),
        _path([["admin"]]),
    ]
    passed, filtered = review_graph_paths(paths, "admin")
    assert len(passed) == 2
    assert len(filtered) == 0


def test_review_graph_paths_role_filter():
    """路径中任一节点对角色不可见，整条路径丢弃。"""
    paths = [
        _path([["procurement", "finance"], ["procurement"]]),   # 全部可见
        _path([["procurement"], ["quality"]]),                   # 第二个节点不可见
    ]
    passed, filtered = review_graph_paths(paths, "procurement")
    assert len(passed) == 1
    assert len(filtered) == 1


def test_review_graph_paths_no_allowed_roles_field():
    """节点缺少 allowed_roles 字段 → 放行（认为是 Neo4j 层已过滤）。"""
    paths = [_path([["procurement"], None])]
    passed, filtered = review_graph_paths(paths, "procurement")
    assert len(passed) == 1
    assert len(filtered) == 0


# ── review_entities ──


def test_review_entities_admin_bypass():
    entities = [
        {"id": "e1", "name": "E1", "type": "supplier", "allowed_roles": ["procurement"]},
    ]
    passed, filtered = review_entities(entities, "admin")
    assert len(passed) == 1
    assert len(filtered) == 0


def test_review_entities_filter():
    entities = [
        {"id": "e1", "name": "E1", "type": "supplier", "allowed_roles": ["finance"]},
        {"id": "e2", "name": "E2", "type": "factory", "allowed_roles": ["procurement"]},
    ]
    passed, filtered = review_entities(entities, "procurement")
    assert len(passed) == 1
    assert passed[0]["id"] == "e2"
    assert len(filtered) == 1


def test_review_entities_missing_allowed_roles():
    """实体缺少 allowed_roles 字段 → 放行。"""
    entities = [{"id": "e1", "name": "E1", "type": "factory"}]
    passed, filtered = review_entities(entities, "procurement")
    assert len(passed) == 1
    assert len(filtered) == 0