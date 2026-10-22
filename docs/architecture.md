# RoleGuard RAG 项目全景指南

> 最后更新：2026-10-22
> 当前阶段：**Phase 1（后端核心基建）进行中**
> 参考架构：Complyra（MIT），本项目为从零重写，不复制其代码

---

## 1. 项目是什么

RoleGuard RAG 是一个**带人工审批门禁的企业级多租户知识问答系统**。

一句话概括：员工向企业知识库提问 → 系统检索并生成答案 → 敏感内容被策略拦截、高风险答案先转人工审批 → 全过程留痕可审计。

它要解决四个现实问题：

| 问题 | 本项目的解法 |
|---|---|
| 不同部门/客户的数据不能互相看到 | 多租户隔离（数据库 + 向量库双层过滤） |
| AI 可能把密钥、内部编号等敏感信息说出去 | 输出策略门禁（正则拦截） |
| 高风险回答不能直接给用户 | 人工审批工作流（human-in-the-loop） |
| 合规要求"谁问了什么、谁批的"可追溯 | 审计日志（只追加、可导出 CSV） |

## 2. 核心能力清单

- **多租户**：用户可属于多个租户，请求按 `X-Tenant-ID` 切换上下文
- **文档摄取**：PDF（逐页解析 + OCR 回退）、TXT/Markdown、图片（Vision 描述）
- **智能分块**：段落 → 句子 → 贪心合并，保留页码
- **混合检索**：dense 向量 + BM25 稀疏向量，RRF 融合排序
- **ReAct 检索循环**：改写问题 → 检索 → 判断是否足够 → 不够就再检索
- **输出策略门禁**：命中敏感正则时拦截并替换回答
- **人工审批**：草稿先入库，审核通过后才返回最终答案
- **审计**：记录问答、审批、管理操作，支持搜索与 CSV 导出
- **可观测**：JSON 结构化日志、请求 ID 串联、Prometheus 指标、Grafana 仪表盘

## 3. 总体架构图

```
┌────────────────────────────────────────────────────────────────┐
│  前端 SPA（React 19 + TypeScript + Vite）                        │
│  Login / 工作台 / 审批 / 审计 / 管理 / 监控 / 知识库               │
└───────────────────────────┬────────────────────────────────────┘
                            │ HTTP + SSE
                            │ Authorization: Bearer <JWT>
                            │ X-Tenant-ID: <租户>
┌───────────────────────────▼────────────────────────────────────┐
│  FastAPI 应用（app/）                                            │
│                                                                │
│  中间件链（由外到内）：                                           │
│    RequestID → RequestLogging → CORS → SecurityHeaders          │
│                                                                │
│  路由层（app/api/routes/）：                                      │
│    auth  users  tenants  documents  ingest                      │
│    chat  approvals  audit  health  monitoring                   │
│                                                                │
│  鉴权与上下文：                                                  │
│    JWT 校验 → 角色检查（RBAC）→ 租户成员校验                       │
└───────────────┬───────────────────────────────┬────────────────┘
                │                               │
┌───────────────▼──────────────┐   ┌────────────▼─────────────────┐
│  业务服务层（app/services/）   │   │  LangGraph 问答工作流          │
│                              │   │                              │
│  embeddings  检索向量化        │◄──┤  rewrite（改写问题）           │
│  retrieval   向量库读写        │   │    ↓                         │
│  llm         模型调用/流式     │   │  retrieve（检索）              │
│  ingest      解析与分块        │   │    ↓                         │
│  policy      输出门禁          │   │  judge（够不够？）──不够──┐     │
│  approval_policy 审批策略链    │   │    ↓ 够                  │     │
│  approvals   审批单           │   │  draft（生成草稿）         │     │
│  audit       审计写入          │   │    ↓                     │     │
│  queue       摄取任务队列      │   │  policy（输出检查）        │     │
│                              │   │    ↓                     │     │
└───────┬──────────┬───────────┘   │  approval 或 final         │     │
        │          │               └────────────────────────────┘     │
        │          │                                                 │
┌───────▼──────┐ ┌─▼──────────┐ ┌───────────────┐ ┌──────────────────┐
│ PostgreSQL   │ │  Qdrant    │ │ Redis + RQ    │ │  LLM / Embedding │
│ 或 SQLite     │ │  向量库     │ │  异步摄取队列   │ │  Ollama / OpenAI │
│              │ │            │ │               │ │  / Gemini        │
│ 租户/用户     │ │ 文档分块     │ │ queued →      │ │                  │
│ 文档/审批     │ │ + 租户过滤   │ │ processing →  │ │ 问答生成          │
│ 审计/策略     │ │            │ │ completed     │ │ 向量化            │
└──────────────┘ └────────────┘ └───────────────┘ └──────────────────┘

可观测性：stdout JSON 日志 / 内存日志缓冲 / Prometheus 指标 / Grafana 面板
```

## 4. 多租户隔离：三层防线

租户 ID 从登录开始一路贯穿，任何一层缺失都可能造成数据泄露。

```
登录
 └─ JWT 里带 tid（默认租户）
      └─ 请求头 X-Tenant-ID 可切换当前租户
           └─ get_tenant_id() 校验：这个用户真的是该租户成员吗？
                └─ SQL 查询：WHERE tenant_id = :tid
                     └─ Qdrant 检索：payload 过滤 tenant_id = :tid
```

| 层 | 作用 | 不做会怎样 |
|---|---|---|
| JWT 携带 `tid` | 确定用户身份与默认租户 | 无法判断请求属于哪个租户 |
| 成员校验 | 防止伪造 `X-Tenant-ID` 越权 | 改个请求头就能看别家数据 |
| SQL `tenant_id` 过滤 | 文档、审批、审计按租户隔离 | 列表接口泄露他人数据 |
| Qdrant payload 过滤 | 向量检索只召回本租户分块 | RAG 答案里混入别家内容 |

## 5. 一次问答的完整流程

### 同步接口 `POST /api/chat/`

```
1. 中间件         生成 request_id，开始计时
2. 鉴权           解析 JWT → 用户、角色、默认租户
3. 租户校验       校验 X-Tenant-ID 是否属于该用户
4. LangGraph      rewrite   → 用 LLM 改写/补全问题
                  retrieve  → Qdrant 混合检索 top_k
                  judge     → LLM 判断证据是否足够
                              └─ 不够：带着新问题回到 retrieve（最多 N 轮）
                  draft     → LLM 基于编号来源生成答案
5. 输出策略        正则扫描敏感内容
                  ├─ 命中：替换为拦截提示，记审计，直接返回
                  └─ 通过：进入下一步
6. 审批判断        document override → tenant policy → 全局开关
                  ├─ 需要审批：写入 approvals，返回 pending 状态与草稿
                  └─ 不需要：返回最终答案
7. 审计写入        question / answer / 命中来源 / 审批状态
8. 响应            写 X-Request-ID，记录访问日志
```

### 流式接口 `POST /api/chat/stream`（SSE）

事件顺序：

```
rewrite_start → rewrite_done
retrieve_start → retrieve_done
judge_start → judge_done        （可能循环多轮）
generate_start → token × N
policy_blocked 或 policy_passed
approval_required 或 done
```

前端用原生 `fetch` + `AbortController` 读取事件流，可随时中断。

## 6. 审批决策链

```
文档级覆盖（documents.approval_override）
 ├─ always → 必须审批
 ├─ never  → 无需审批
 └─ 未设置 → 看租户策略
              ├─ all       → 所有问答都审批
              ├─ sensitive → 仅敏感文档（sensitivity=high）审批
              └─ none      → 不审批
                            └─ 最后看全局 require_approval
```

优先级：**文档 > 租户 > 全局**。这样单个文档可以临时"永远需要人工过目"，也可以让某租户整体免审。

## 7. 数据模型（ER 图）

```
┌─────────────┐          ┌──────────────────┐
│  tenants    │1        *│     users        │
│─────────────│◄─────────│──────────────────│
│ tenant_id PK│          │ user_id PK       │
│ name        │          │ username UNIQUE  │
│ created_at  │          │ password_hash    │
└──────┬──────┘          │ role             │
       │                 │ default_tenant_id│
       │                 │ created_at       │
       │                 └───────┬──────────┘
       │                         │
       │      ┌──────────────────┴────────────┐
       │      │           user_tenants        │
       │      │───────────────────────────────│
       │      │ id PK                         │
       │      │ user_id FK → users (CASCADE)  │
       │      │ tenant_id FK → tenants (CASCADE)│
       │      │ UNIQUE(user_id, tenant_id)    │
       │      └───────────────────────────────┘
       │
       │1
       ├──────────────┬───────────────┬──────────────┬──────────────┐
       │*             │*              │*             │1             │*
┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐ ┌────▼─────────┐
│  documents  │ │ ingest_jobs│ │  approvals  │ │audit_logs  │ │tenant_policies│
│─────────────│ │────────────│ │─────────────│ │────────────│ │───────────────│
│ document_id │ │ job_id     │ │ approval_id │ │ id         │ │ tenant_id PK  │
│ tenant_id   │ │ tenant_id  │ │ user_id     │ │ timestamp  │ │ approval_mode │
│ created_by  │ │ created_by │ │ tenant_id   │ │ tenant_id  │ │ updated_at    │
│ filename    │ │ filename   │ │ question    │ │ user       │ │ updated_by    │
│ sensitivity │ │ status     │ │ draft_answer│ │ action     │ └───────────────┘
│ status      │ │ chunks_... │ │ final_answer│ │ input_text │
│ approval_   │ │ document_id│ │ status      │ │ output_text│
│  override   │ │ error_msg  │ │ decision_by │ │ meta_json  │
│ storage_path│ │ created_at │ │ decided_at  │ └────────────┘
│ timestamps  │ │ updated_at │ │ note        │
└─────────────┘ └────────────┘ └─────────────┘
```

### 每张表的作用

| 表 | 作用 | 状态 |
|---|---|---|
| `tenants` | 租户：隔离的最上层单位 | ✅ 已建 |
| `users` | 账号、密码哈希、角色、默认租户 | ✅ 已建 |
| `user_tenants` | 用户与租户的多对多成员关系 | ✅ 已建 |
| `tenant_policies` | 每个租户的审批模式 | ⬜ 待建 |
| `documents` | 文档元数据、敏感级别、审批覆盖 | ⬜ 待建 |
| `ingest_jobs` | 摄取任务进度与错误信息 | ⬜ 待建 |
| `approvals` | 待审批的问答草稿与决定 | ⬜ 待建 |
| `audit_logs` | 只追加的审计记录 | ⬜ 待建 |

## 8. 模块职责地图

```
app/
├── main.py                 应用工厂：日志、中间件、路由组装、启动初始化   🚧
├── core/
│   ├── config.py           pydantic-settings 全量配置（APP_ 前缀）        ✅
│   ├── log_context.py      ContextVar 保存 request_id / user / tenant    ✅
│   ├── logging_config.py   JSON 格式化 + 根 logger 配置                   ✅
│   ├── request_id.py       请求 ID 中间件                                 ✅
│   ├── request_logging.py  访问日志中间件（方法/路径/状态/耗时）           ✅
│   ├── log_buffer.py       内存环形日志缓冲（供监控页）                    ⬜
│   ├── security.py         bcrypt 密码哈希 + JWT 签发/解析                ⬜
│   ├── security_headers.py 安全响应头中间件                               ⬜
│   └── metrics.py          Prometheus 指标 + /metrics 响应                ⬜
├── db/
│   ├── session.py          Engine / SessionLocal / get_db / SQLite PRAGMA  ✅
│   ├── models.py           ORM 表模型（8 张）                              🚧 3/8
│   └── audit_db.py         短生命周期审计 CRUD + init_db + 默认种子        ⬜
├── models/
│   └── schemas.py          Pydantic 请求/响应模型                          ⬜
├── services/
│   ├── embeddings.py       四种 embedding provider                        ⬜
│   ├── sparse_embed.py     BM25 稀疏向量                                  ⬜
│   ├── retrieval.py        Qdrant 集合/写入/混合检索                       ⬜
│   ├── llm.py              LLM 调用、流式输出、健康检查                    ⬜
│   ├── query_rewrite.py    问题改写                                       ⬜
│   ├── relevance_judge.py  证据充分性判断                                  ⬜
│   ├── workflow.py         LangGraph 状态机                               ⬜
│   ├── policy.py           输出策略正则门禁                                ⬜
│   ├── approval_policy.py  三级审批决策链                                  ⬜
│   ├── approvals.py        审批单 CRUD                                    ⬜
│   ├── ingest.py           文档解析 + 智能分块                             ⬜
│   ├── queue.py            Redis/RQ 队列                                  ⬜
│   ├── documents.py        文档 CRUD                                      ⬜
│   ├── users.py            用户管理                                       ⬜
│   └── audit.py            审计读写                                       ⬜
├── api/
│   ├── deps.py             get_current_user / require_roles / get_tenant_id ⬜
│   └── routes/
│       ├── auth.py         登录 / 登出                                     ⬜
│       ├── users.py        管理员建用户、分配租户                           ⬜
│       ├── tenants.py      租户与策略管理                                  ⬜
│       ├── documents.py    文档列表/详情/删除/预览                          ⬜
│       ├── ingest.py       上传、入队、查询进度                             ⬜
│       ├── chat.py         同步问答 + SSE 流式                             ⬜
│       ├── approvals.py    待审批列表、审批决定、取结果                     ⬜
│       ├── audit.py        审计列表/搜索/CSV 导出                          ⬜
│       ├── health.py       存活/就绪探针                                   ⬜
│       └── monitoring.py   指标与日志查看（管理员）                         ⬜
└── workers/
    └── ingest_worker.py    RQ 后台摄取 worker                              ⬜

web/            React SPA（登录/工作台/审批/审计/管理/监控/知识库）        ⬜
tests/          服务单测 + 路由测试 + 端到端流程                           ⬜
ops/            Prometheus 配置、告警规则、Grafana 仪表盘                  ⬜
```

## 9. 分阶段实施路线

### Phase 0 — 脚手架 ✅ 基本完成
- [x] `pyproject.toml`、`requirements.txt`、`requirements-dev.txt`
- [x] `.env` / `.env.example`、`.gitignore`、`.vscode`
- [x] Python 依赖安装
- [ ] `Dockerfile` / `docker-compose.yml` / `entrypoint.sh`
- [ ] `alembic/` 迁移初始化

**验收**：`python -c "import fastapi, sqlalchemy"` 无报错。

### Phase 1 — 后端核心基建 🚧 进行中
- [x] `core/config.py` 分组配置
- [x] 日志子系统：上下文、JSON 格式、请求 ID、访问日志（`log_buffer` 待监控页再补）
- [x] `db/session.py`：Engine / Session / SQLite PRAGMA / 依赖注入
- [x] `db/models.py`：`Tenant`、`User`、`UserTenant`
- [ ] `db/models.py`：`TenantPolicy`、`Document`、`IngestJob`、`Approval`、`AuditLog`
- [ ] `core/security.py`：bcrypt + JWT
- [ ] `db/audit_db.py`：`init_db` + 默认租户/演示用户种子
- [ ] `core/metrics.py` + `core/security_headers.py`
- [ ] `main.py`：lifespan 初始化、CORS、指标中间件

**验收**：启动应用自动建表、生成默认租户和 demo 用户；请求日志带 request_id；`/api/health/live` 正常。

### Phase 2 — 认证 / RBAC / 租户 / 用户 ⬜
- `api/deps.py`：Bearer/Cookie 取 token、当前用户、角色校验、租户成员校验
- 路由：`auth`（登录/登出 + httponly cookie）、`users`、`tenants`
- 请求/响应 schema

**验收**：demo 用户能登录拿到 JWT；普通用户访问管理员接口返回 403；伪造租户头返回 403。

### Phase 3 — 检索与文档摄取 ⬜
- Embedding：Ollama（默认 nomic-embed-text 768 维）/ SentenceTransformer / OpenAI / Gemini
- 稀疏向量、Qdrant 集合与混合检索（RRF）
- 文档解析（PDF/OCR/文本/图片）、智能分块
- Redis + RQ 摄取队列、worker 生命周期
- 文档 CRUD、上传、进度查询

**验收**：上传 txt → 任务完成 → 向量入库；检索只返回本租户内容。

### Phase 4 — RAG 工作流 / 策略 / 审批 / 审计 ⬜
- 问题改写、相关性判断
- LangGraph 状态机（rewrite → retrieve → judge → draft → policy → approval/final）
- 输出策略正则门禁、三级审批决策链
- `chat`（同步 + SSE）、`approvals`、`audit`、`health`、`monitoring` 路由
- 审计写入与 CSV 导出

**验收**：完整走通问答；敏感内容被拦截；高风险答案进入待审批；审计可查可导出。

### Phase 5 — 前端 ⬜
- Vite + React + TS 脚手架；`api.ts`、`types.ts`、`i18n.ts`
- 视图模块化：Login / Workbench / Approvals / Audit / Admin / Monitoring / KnowledgeBase
- 设计 token 与样式

**验收**：浏览器完成登录 → 上传 → 问答 → 审批 → 查看审计。

### Phase 6 — 可观测与运维 ⬜
- Prometheus 配置、告警规则、Grafana 仪表盘
- `Dockerfile`、`docker-compose.yml`（api/worker/web/postgres/redis/qdrant/prometheus/grafana）
- 日志轮转配置、健康检查、资源限制、数据卷

**验收**：`docker compose up --build -d` 后所有服务健康；Grafana 能看到请求量、延迟、检索与审批指标。

### Phase 7 — 分层测试 ⬜
- fixtures：mock LLM / mock Qdrant / fake embedder
- 服务单测、路由测试、端到端工作流测试

**验收**：`pytest tests/ -v` 全绿，不依赖外部服务。

### Phase 8 — 验证与跑通 ⬜
- 全栈冒烟：login → 上传 → 摄取 → 流式问答 → 审批 → 审计导出
- 前端黄金路径与边界（无文档、策略拦截、审批前不返回答案）

**验收**：上述流程在真实浏览器中全部走通。

## 10. 当前进度快照

```
已完成  █████████░░░░░░░░░░░  Phase 0 脚手架 + Phase 1 约 60%
```

- 日志：4/5 个文件（差监控页用的 `log_buffer.py`）
- 数据库：会话层完成；8 张表完成 3 张
- 安全（bcrypt/JWT）：未开始
- 认证路由：未开始
- RAG / 审批 / 审计：未开始
- 前端 / 容器化：未开始

## 11. 接下来 6 步

1. `models.py` 第 3 批：`TenantPolicy`
2. `models.py` 第 4 批：`Document` + `IngestJob`
3. `models.py` 第 5 批：`Approval` + `AuditLog`
4. `core/security.py`：bcrypt 哈希 + JWT
5. `db/audit_db.py`：`init_db()` + 默认租户 / demo 用户种子
6. `main.py` 收尾：lifespan 初始化、CORS、健康检查 → **Phase 1 完成**

## 12. 与参考实现的刻意差异

| 项目 | 参考实现 | 本项目 | 原因 |
|---|---|---|---|
| 密码哈希 | `passlib` | 直接用 `bcrypt` | passlib 不再维护，Python 3.13 报错 |
| Embedding | BGE / sentence-transformers | 默认 Ollama `nomic-embed-text`（768 维） | 本机没有 torch，Ollama 已就绪 |
| 文档审批覆盖值 | 文档写 `none`，代码判断 `never` | 统一 `always` / `never` | 修正参考实现的不一致 |
| 前端结构 | 单体 `App.tsx` | 按视图拆模块 | 可维护性 |
| 部署自动化 | AWS/Terraform/ECS | 跳过 | 本阶段聚焦应用本体 |

## 13. 运行方式（当前可用部分）

```bash
# 后端（当前只有健康检查）
uvicorn app.main:app --reload --port 8000

# 健康检查
curl http://127.0.0.1:8000/api/health/live
# → {"status":"ok","environment":"development"}

# 访问日志（查看请求 ID）
curl -H "X-Request-ID: my-test-001" http://127.0.0.1:8000/api/health/live

# 前端（Phase 5 后）
cd web && npm run dev

# 测试（Phase 7 后）
PYTHONPATH=. pytest tests/ -v

# 整栈（Phase 6 后）
docker compose up --build -d
```

---

> 维护约定：每完成一批表或一个 Phase，更新第 9、10、11 节的勾选和进度。
