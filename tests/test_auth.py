"""认证与越权测试：登录、令牌校验、跨角色访问控制。"""


def test_login_valid(client):
    """有效凭证返回 token。"""
    resp = client.post(
        "/api/auth/login",
        json={"username": "catl_admin", "password": "catl123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "catl_admin"


def test_login_invalid_password(client):
    """错误密码返回 401。"""
    resp = client.post(
        "/api/auth/login",
        json={"username": "catl_admin", "password": "wrong"},
    )
    assert resp.status_code == 401


def test_login_invalid_user(client):
    """不存在用户返回 401。"""
    resp = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "catl123"},
    )
    assert resp.status_code == 401


def test_access_without_token(client):
    """无 Authorization header 返回 401 或 403。"""
    resp = client.get("/api/users")
    assert resp.status_code in (401, 403)


def test_access_with_invalid_token(client):
    """伪造 token 返回 401。"""
    resp = client.get("/api/users", headers={"Authorization": "Bearer fake.token.here"})
    assert resp.status_code == 401


def test_admin_can_access_users(client, auth_headers):
    """admin 可以访问用户列表。"""
    headers = auth_headers("admin")
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 200


def test_procurement_cannot_access_users(client, auth_headers):
    """procurement 不能访问用户管理。"""
    headers = auth_headers("procurement")
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code in (401, 403)


def test_procurement_cannot_access_audit(client, auth_headers):
    """审计日志只有 admin 能看。"""
    headers = auth_headers("procurement")
    resp = client.get("/api/audit", headers=headers)
    assert resp.status_code in (401, 403)


def test_quality_can_access_chat_models(client, auth_headers):
    """正常角色可以获取模型列表。"""
    headers = auth_headers("quality")
    resp = client.get("/api/chat/models", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data


def test_logistics_can_access_graph(client, auth_headers):
    """logistics 可以访问图谱概览。"""
    headers = auth_headers("logistics")
    resp = client.get("/api/graph/overview", headers=headers)
    # Neo4j 不可用时返回 500 或降级
    assert resp.status_code in (200, 500, 503)


def test_finance_cannot_access_admin_only_routes(client, auth_headers):
    """finance 不能访问审批决定接口（admin only）。"""
    headers = auth_headers("finance")
    resp = client.post(
        "/api/approvals/fake-id/decide",
        headers=headers,
        json={"action": "approve"},
    )
    assert resp.status_code in (401, 403, 404)