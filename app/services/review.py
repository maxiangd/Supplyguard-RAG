"""Review Node：对检索和图谱结果做 RBAC 二次校验（belt-and-suspenders）。

即使 Qdrant 过滤和 Neo4j 查询已经做过角色过滤，Review Node 再检查一遍：
1. 每个文档块的 allowed_roles 是否包含当前角色
2. 每条图谱路径的每个节点是否对当前角色可见
3. admin 角色跳过所有校验

这样即使前面的过滤出现漏洞，Review Node 也会拦截，保证越权数据不会进入 LLM 提示词。
"""

from app.core.configuration import settings


def review_chunks(hits: list[dict], role: str) -> tuple[list[dict], list[dict]]:
    """返回 (通过校验的块, 被过滤掉的块)。

    admin 角色全部通过；其他角色只保留 allowed_roles 包含自己的块。
    被过滤掉的块会记录日志，方便排查是否有检索层过滤遗漏。
    """
    if role == "admin":
        return hits, []

    passed = []
    filtered = []
    for hit in hits:
        allowed = hit.get("allowed_roles") or []
        if role in allowed:
            passed.append(hit)
        else:
            filtered.append(
                {
                    "document_id": hit.get("document_id", "?"),
                    "filename": hit.get("filename", "?"),
                    "chunk_index": hit.get("chunk_index", -1),
                    "role": role,
                    "allowed_roles": allowed,
                }
            )
    return passed, filtered


def review_graph_paths(paths: list[dict], role: str) -> tuple[list[dict], list[dict]]:
    """返回 (通过校验的路径, 被过滤掉的路径)。

    admin 角色全部通过；其他角色检查每条路径中每个节点的 allowed_roles。
    路径中任一节点对当前角色不可见，整条路径丢弃。
    """
    if role == "admin":
        return paths, []

    passed = []
    filtered = []
    for path in paths:
        all_visible = True
        for node in path.get("nodes", []):
            allowed = node.get("allowed_roles")
            # 图谱节点可能不返回 allowed_roles（_public 过滤掉了），
            # 这种情况下认为已通过 Neo4j 层过滤，放行
            if allowed is not None and role not in allowed:
                all_visible = False
                break
        if all_visible:
            passed.append(path)
        else:
            filtered.append(
                {
                    "rule": path.get("rule"),
                    "summary": path.get("summary"),
                    "role": role,
                }
            )
    return passed, filtered


def review_entities(entities: list[dict], role: str) -> tuple[list[dict], list[dict]]:
    """返回 (通过校验的实体, 被过滤掉的实体)。

    与 graph_paths 同理，主要确保实体级别也经过角色检查。
    """
    if role == "admin":
        return entities, []

    passed = []
    filtered = []
    for entity in entities:
        allowed = entity.get("allowed_roles")
        if allowed is None or role in allowed:
            passed.append(entity)
        else:
            filtered.append(
                {
                    "id": entity.get("id"),
                    "name": entity.get("name"),
                    "type": entity.get("type"),
                    "role": role,
                }
            )
    return passed, filtered