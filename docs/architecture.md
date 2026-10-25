# SupplyGuard 技术架构与路线图

> 最后更新：2026-10-22
> 当前阶段：**Phase 1（后端核心基建）进行中**
> 定位：供应链风险 AgentHarness 平台

---

## 1. 项目定位

SupplyGuard 面向采购、物流、质量、财务等多角色，在 RBAC 权限约束下，融合 SecureRAG、GraphRAG、Memory 与 LangGraph 固定工作流，提供**可引用、可审计、可 Benchmark** 的供应链风险洞察与决策支持。

核心流程：

```
风险问题
  → 角色与权限校验
  → 授权文档检索（SecureRAG）
  → 供应链图谱多跳影响分析（GraphRAG）
  → 检索结果权限复核（Review Node）
  → 带引用的结论生成
  → 高风险结论人工审批
  → 审计留痕
  → 可选写入长期记忆
```

## 2. 角色与应用场景

| 角色 | 关注点 | 典型问题 |
|---|---|---|
| `procurement`（采购） | 供应商风险、替代供应源 | 某供应商所在国家发生罢工，哪些物料会受影响？ |
| `logistics`（物流） | 运输中断、港口拥堵 | 上海港停运会影响哪些在途订单？ |
| `quality`（质量） | 质量事故、召回 | 这批来料的质量异常关联哪些供应商与工厂？ |
| `finance`（财务） | 信用风险、付款风险 | 某供应商财务状况恶化，相关合同风险有多大？ |
| `admin`（管理员） | 用户、策略、监控 | 管理权限、审批规则、查看审计 |

本项目面向单一企业（演示主体为宁德时代供应链），不引入多租户。数据隔离只按**角色**：同一份数据，不同角色能看到的内容和可执行的操作不同。

### 非目标

- 不做自动下单、自动取消订单等写操作
- 不做全网爬取，只基于已入库文档与企业图谱
- 不在 MVP 阶段引入代码执行 runtime

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│ Vue 3 SPA                                                    │
│ 风险看板 / 风险问答 / 供应商图谱 / 复核台 / Benchmark / 审计     │
└───────────────────────┬──────────────────────────────────────┘
                        │ HTTP + SSE（JWT 身份上下文）
┌───────────────────────▼──────────────────────────────────────┐
│ FastAPI（中间件、鉴权、RBAC、路由）                             │
└──────────┬───────────────────────────────┬───────────────────┘
           │ 同步请求                       │ 入队
┌──────────▼──────────────┐      ┌─────────▼──────────────────┐
│ 服务层                   │      │ Redis + RQ Worker          │
│ retrieval（SecureRAG）   │      │ 文档摄取 / 图谱构建 / 评测   │
│ graph（GraphRAG）        │      └─────────┬──────────────────┘
│ workflow（LangGraph）    │                │
│ memory / policy / audit  │                │
└──────┬──────────┬────────┴────────┬───────┴────────┬─────────┘
       │          │                 │                │
┌──────▼─────┐ ┌──▼──────┐ ┌────────▼───────┐ ┌──────▼──────┐
│ PostgreSQL │ │ Qdrant  │ │ Neo4j          │ │ Redis       │
│ 业务/记忆   │ │ 文档向量 │ │ 供应链图谱      │ │ 会话/队列    │
│ /审计       │ │ +权限   │ │ 多跳关系        │ │             │
└────────────┘ └─────────┘ └────────────────┘ └─────────────┘

模型：阿里百炼 Embedding + DeepSeek LLM（OpenAI 兼容接口）
可观测：JSON 日志 / request_id / Prometheus / Grafana
```

### 3.1 模块组合与依赖关系

#### 分层依赖（只能向下调用）

```
┌─────────────────────────────────────────────────────────────┐
│ api/routes/*       接口层：参数校验、权限、调用服务            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ api/dependencies.py 鉴权依赖：当前用户、角色                     │
│ core/security.py   JWT 与密码哈希                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│ services/*         业务逻辑：检索、图谱、工作流、记忆、审批     │
└───────┬──────────────────┬──────────────────┬───────────────┘
        │                  │                  │
┌───────▼──────┐   ┌───────▼──────┐   ┌───────▼─────────────┐
│ db/          │   │ core/        │   │ 外部客户端           │
│ database.py  │   │ configuration.py │   │ Qdrant / Neo4j      │
│ models.py    │   │ logging_*    │   │ Redis / LLM / Embed │
│ audit_db.py  │   │ security.py  │   │                     │
└──────────────┘   └──────────────┘   └─────────────────────┘
```

#### 文件级组合

```
main.py
├── core/logging_setup.py          启动时配置日志
├── core/request_id_middleware.py  中间件：生成请求 ID
├── core/request_logging_middleware.py 中间件：访问日志
├── api/routes/*.py                各业务路由
│     ├── api/dependencies.py      → core/security.py（JWT 校验）
│     └── services/*.py            业务逻辑
│           ├── db/database.py     → db/tables.py（SQL）
│           ├── services/retrieval.py   → Qdrant
│           ├── services/graph.py       → Neo4j
│           ├── services/llm.py         → DeepSeek / 百炼（OpenAI 兼容）
│           ├── services/memory.py      → Redis / PostgreSQL
│           ├── services/queue.py       → Redis / RQ
│           └── services/audit.py       → db/audit_db.py
├── workers/*.py                   后台任务，复用 services
│     ├── ingest_worker.py         解析、分块、向量化
│     ├── graph_worker.py          图谱构建
│     └── benchmark_worker.py      批量评测
└── models/api_models.py           请求/响应模型，供 api 与 services 引用
```

#### 一次风险问答的调用组合

```
POST /api/risks/query
  → RequestID / RequestLogging 中间件
  → api/dependencies.py
       校验 JWT → 加载用户 → 得到 user / role
  → services/workflow.py
       intake
         → classify（规则；LLM 仅兜底）
         → plan（按角色和问题类型选节点）
         → secure_retrieve
              → services/retrieval.py
                   Qdrant filter: allowed_roles
         → graph_impact（可选）
              → services/graph.py
                   Neo4j 多跳查询
         → review
              二次校验 allowed_roles、文档状态
              发现越权 → 丢弃 + 审计
         → synthesize
              → services/llm.py（只接收复核后的证据）
         → approval_gate
              → services/approvals.py（需要时创建审批单）
         → audit
              → services/audit.py → db/audit_db.py
  → services/memory.py
        Redis 写短期会话；Postgres 写长期记忆（可选）
  → 返回 JSON 或 SSE 事件
```

#### 数据存储分工

| 存储 | 存什么 | 谁访问 |
|---|---|---|
| PostgreSQL | 用户、供应商、物料、文档元数据、审批、审计、记忆 | `db/`、`services/*` |
| Qdrant | 文档分块向量 + `allowed_roles` / `sensitivity` | `services/retrieval.py` |
| Neo4j | 供应商、物料、工厂、运输、风险事件及关系 | `services/graph.py` |
| Redis | 会话短期记忆、RQ 队列、进度缓存 | `services/memory.py`、`services/queue.py` |
| 本地磁盘 | 上传的原始文件 | `services/ingest.py`、`workers/` |

#### 依赖规则

- 只能从上往下：`api → services → db/core`
- `core/` 不 import `services/` 和 `api/`
- `db/` 不 import `api/`
- 路由不写业务逻辑，只做参数、权限和调用
- worker 与路由复用同一套 `services/`，避免两份实现

## 4. 固定工作流（LangGraph）

设计原则：**不做 LLM 自主规划**，由规则决定走哪些节点，保证路径可控、可回溯。

### 4.1 图结构

```
intake
  → classify（规则 + 轻量分类）
  → plan（按角色与问题类型选节点）
  → secure_retrieve（授权文档检索）
  → graph_impact（图谱多跳影响分析）
  → review（权限复核 + 策略检查）
       ├─ 发现越权内容 → 丢弃并记录，必要时回到 retrieve
       └─ 通过
  → synthesize（带引用生成结论）
  → approval_gate（高风险结论转人工审批）
  → final / audit
```

### 4.2 规则路由

| 问题类型 | 角色 | 节点路径 |
|---|---|---|
| 文档政策类 | 任意 | `secure_retrieve → review → synthesize` |
| 供应商风险类 | 采购/财务 | `secure_retrieve → graph_impact → review → synthesize` |
| 物流中断类 | 物流 | `secure_retrieve → graph_impact → review → synthesize` |
| 质量追溯类 | 质量 | `secure_retrieve → graph_impact → review → synthesize` |
| 影响面分析 | 任意授权角色 | `graph_impact → secure_retrieve → review → synthesize` |

分类规则优先使用关键词、问题模板与显式参数（如前端选择的“分析类型”），LLM 只做兜底，且不决定工具权限。

### 4.3 节点职责

| 节点 | 输入 | 输出 | 说明 |
|---|---|---|---|
| `intake` | 问题、角色 | 标准化请求 | 写入 request_id、run_id |
| `classify` | 问题 | 类型、实体（供应商/物料/地点） | 规则优先，记录判定依据 |
| `plan` | 类型、角色 | 节点序列 | 决定是否做图谱分析 |
| `secure_retrieve` | 查询、角色 | 授权证据块 | Qdrant payload 过滤 |
| `graph_impact` | 实体、风险事件 | 影响路径与节点 | Neo4j 多跳查询 |
| `review` | 证据、路径、角色 | 通过/剔除 | 二次权限校验与敏感检查 |
| `synthesize` | 证据、路径 | 带引用结论 | 引用文档与图谱路径 |
| `approval_gate` | 结论、风险级别 | 审批单或最终答案 | 复用三级审批思路 |
| `audit` | 全流程 | 审计记录 | 只追加 |

## 5. SecureRAG：权限约束检索

### 5.1 权限元数据

Qdrant 每个 chunk 的 payload：

```json
{
  "document_id": "doc-123",
  "chunk_index": 4,
  "page": 2,
  "text": "...",
  "allowed_roles": ["procurement", "finance"],
  "sensitivity": "high",
  "source_type": "contract"
}
```

### 5.2 检索前过滤

查询时构造 Qdrant filter：

```
must:     allowed_roles match any [当前用户角色]
可选:     source_type / sensitivity / 时间范围
```

### 5.3 检索后复核（Review Node）

即使向量库过滤正确，也要在应用层再校验一次：

- 逐条检查 chunk 的 `allowed_roles` 是否包含当前角色；
- 检查文档状态（已删除/已过期文档不进入上下文）；
- 命中越权内容时丢弃并记录审计，不发送给 LLM；
- 越权丢弃比例超过阈值时，标记本次查询异常。

### 5.4 Benchmark 指标

- 构造「角色 A 提问，但答案只存在于角色 B 文档」的用例；
- 指标：越权拦截率（目标 100%）、合法召回率、丢弃原因分布。

## 6. GraphRAG：供应链多跳影响分析

### 6.1 图模型（Neo4j）

演示图谱基于 `docs/demo-data/` 的公开资料整理。所有节点统一使用 `Entity` 标签，用 `type` 属性区分角色（前端按 type 着色）；每个节点带 `allowed_roles`、`risk_level`、`region`、`desc` 与来源文档 `source`。

| type | 含义 | 数量 | 可见角色 |
|---|---|---|---|
| `supplier` | 材料供应商（份额来自风险台账） | 12 | admin / procurement / finance / quality |
| `factory` | 电芯、材料与海外基地 | 10 | 全部角色 |
| `port` | 出海口 | 4 | admin / logistics |
| `route` | 航线（连接两端港口） | 3 | admin / logistics |
| `region` | 资源来源地与工厂所在地 | 11 | 全部角色 |
| `event` | 风险事件（带传导规则） | 13 | 按事件内容分配 |

关系：

| 关系 | 方向 | 含义 |
|---|---|---|
| `SUPPLIES {material, share}` | Supplier → Factory | 供货关系与份额 |
| `SOURCED_FROM {material}` | Supplier → Region | 原料来源地 |
| `LOCATED_IN` | Factory → Region | 基地所在地 |
| `FEEDS {material}` | Factory → Factory | 内部材料流（宜春冶炼 → 电芯基地） |
| `SHIPS_VIA` | Factory → Port | 出海口 |
| `CONNECTS` | Route → Port | 航线两端港口 |
| `AFFECTS {rule, severity, reason}` | Event → Supplier / Factory / Region / Port / Route | 影响对象与传导方式 |

`AFFECTS.rule` 取 DIRECT / REGION / PORT / ROUTE，决定从事件往下游怎么展开（见 6.2）。

导入：`python -m app.services.graph_seed`（全量 `MERGE`，可重复执行），或管理员调用 `POST /api/graph/seed`。当前演示图谱共 53 个节点、87 条关系。

### 6.2 风险传导规则

规则标注在事件与目标的 `AFFECTS` 边上，由 `services/graph.py` 按目标类型做下游展开。每个角色只看到自己可见的节点，路径中任一节点不可见就整条不返回：

| 规则 | 起点 | 展开 | 跳数 |
|---|---|---|---|
| DIRECT | 事件直接影响的供应商 / 工厂 | 供应商 → 工厂 → 港口 | 1–3 |
| REGION | 事件影响的地区 | 地区 → 供应商 / 工厂 → 工厂 → 港口 | 2–4（默认上限 3） |
| PORT | 事件影响的港口 | 港口 → 经此出货的工厂 | 2 |
| ROUTE | 事件影响的航线 | 航线 → 两端港口 → 工厂 | 2–3 |

路径按跳数升序、严重度降序返回，默认最多 3 跳、40 条；每条路径带 `hops`、`rule_label`、`severity`、`reason`，供前端展示与后续 Benchmark 使用。

问题命中供应商、工厂、港口、地区、航线时，会把「影响该实体的风险事件」作为路径起点（如 `极星 4 召回 → 宁德漳湾基地 → 三都澳`），避免回答缺少风险来源；该角色看不到的事件不会出现。

### 6.3 API 与问答融合

| 接口 | 说明 |
|---|---|
| `GET /api/graph/overview` | 当前角色可见的节点，以及两端都可见的关系 |
| `POST /api/graph/impact` | 按 `question` 或 `entity_id` 做多跳影响分析，`max_hops` 取 1–4 |
| `POST /api/graph/seed` | 管理员幂等导入演示图谱 |

问答链路（`services/chat.py`）在文档检索之后按问题识别实体（节点名 / 别名规则匹配，不调用 LLM），取前 6 条路径以 `[G编号]` 注入提示词；回答可同时引用文档 `[n]` 与图谱 `[G编号]`，流式接口额外推送 `graph` 事件。模型以「知识库中暂无相关资料」开头作答时视为拒答，文档与图谱证据一起清空；只能部分回答时保留证据。Neo4j 不可用时图谱证据降级为空，文档问答继续可用。

### 6.4 路径可信度

- 图谱证据只来自结构化关系，不经过 LLM 生成；
- 每条路径保留跳数、规则类型与事件严重度；
- 文档与图谱证据都为空时才拒答；
- M3 再补独立 ground truth 与路径命中率评测。

## 7. Memory：短期与长期记忆

| 类型 | 存储 | 内容 | 生命周期 |
|---|---|---|---|
| 短期 | Redis | 最近 N 轮问题、检索摘要、当前分析对象 | TTL 1 小时 |
| 长期 | PostgreSQL | 用户偏好、关注供应商、历史风险结论、审批记录 | 持久 |

规则：

- 记忆按 `user_id` 隔离；
- 不把高敏感文档原文写入记忆，只存摘要与引用；
- 长期记忆写入前做一次敏感信息检查；
- 用户可查看与删除自己的长期记忆。

## 8. 数据模型

### 8.1 已有表（Phase 1）

| 表 | 说明 | 状态 |
|---|---|---|
| `users` | 用户、密码哈希、角色 | ✅ |

`users.role` 取值扩展为：`admin` / `procurement` / `logistics` / `quality` / `finance`。

### 8.2 待建业务表

| 表 | 关键字段 |
|---|---|
| `suppliers` | supplier_id、name、country、tier、risk_score、is_available |
| `materials` | material_id、name、sku、criticality、monthly_demand |
| `factories` | site_id、name、country |
| `warehouses` | site_id、name、country |
| `ports` | port_id、name、country |
| `regions` | region_id、name |
| `shipping_routes` | route_id、origin_port_id、dest_port_id、transit_days_normal/current、is_disrupted、disruption_type |
| `shipments` | shipment_id、supplier_id、material_id、origin_port_id、dest_port_id、status、eta、quantity |
| `disruption_events` | event_id、name、type、severity、start/end、is_active、description |
| `supplier_materials` | supplier_id、material_id、share、is_primary |
| `documents` | document_id、filename、source_type、sensitivity、status、allowed_roles（同步写入 Qdrant） |
| `ingest_jobs` | job_id、status、progress、error |
| `conversations` | session_id、user_id、created_at |
| `messages` | message_id、session_id、role、content、cited_docs、created_at |
| `memory_facts` | fact_id、user_id、kind、content、source、confidence |
| `approvals` | approval_id、run_id、status、decided_by、note |
| `audit_logs` | 只追加：timestamp、user、action、input/output、metadata |
| `policies` | approval_mode、risk_threshold、updated_by |
| `benchmark_cases` | case_id、role、question、expected_suppliers、expected_paths、forbidden_docs |
| `benchmark_runs` | run_id、case_set、metrics_json、created_at |

> 图关系存 Neo4j，PostgreSQL 保留实体主数据；两边通过业务 ID 对应。

## 9. API 设计（草案）

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/api/auth/login` | 公开 | 登录，返回 JWT |
| POST | `/api/risks/query` | 任意 | 同步风险问答 |
| POST | `/api/risks/stream` | 任意 | SSE：工作流进度与 token |
| GET | `/api/suppliers` | procurement/finance | 供应商列表与风险分 |
| GET | `/api/suppliers/{id}/impact` | 授权角色 | 图谱影响分析 |
| GET | `/api/graph/impact` | 授权角色 | 按风险事件查询多跳路径 |
| POST | `/api/documents` | 授权角色 | 上传并入库 |
| GET | `/api/documents` | 授权角色 | 按权限返回可见文档 |
| GET | `/api/reviews` | admin/审核角色 | 待复核结论 |
| POST | `/api/reviews/{id}/decision` | admin/审核角色 | 通过/驳回 |
| GET | `/api/approvals` | admin | 审批列表 |
| POST | `/api/approvals/{id}/decision` | admin | 审批决定 |
| GET | `/api/benchmark/runs` | admin | 评测结果 |
| POST | `/api/benchmark/runs` | admin | 发起评测 |
| GET | `/api/audit` | admin | 审计查询与导出 |
| GET | `/api/health/live`、`/api/health/ready` | 公开 | 探针 |

SSE 事件：`run_started`、`classify_done`、`retrieve_done`、`graph_done`、`review_done`、`token`、`approval_required`、`done`、`error`。

## 10. 前端页面

| 页面 | 功能 |
|---|---|
| 登录 | 账号密码、角色展示 |
| 风险看板 | 高风险供应商、风险事件、待审批数量 |
| 风险问答 | 提问、工作流进度、引用面板、图谱路径展示 |
| 供应商图谱 | 节点搜索、多跳路径高亮、风险事件叠加 |
| 复核台 | 待复核结论、证据、通过/驳回 |
| Benchmark | 用例管理、运行评测、指标对比 |
| 审计 | 条件搜索、分页、CSV 导出 |
| 管理 | 用户、角色、策略、监控 |

## 11. 可观测与安全

- 日志：JSON + `request_id`，工作流追加 `run_id`，不记录文档原文与完整证据；
- 指标：查询量、各节点耗时、LLM 调用、越权拦截数、审批积压、Benchmark 指标；
- 安全：上传白名单与大小限制、路径清洗、角色过滤、Prompt 注入防护、审计导出公式转义；
- 权限：接口级 RBAC + 数据级过滤，越权统一返回 403，不泄露资源是否存在。

## 12. 实施路线与验收

### Phase 0 脚手架 ✅
- 依赖、配置、`.gitignore`、本地虚拟环境
- 待补：Docker、Alembic

### Phase 1 后端基建 ✅
- [x] 配置
- [x] 日志（4/5，`log_buffer` 待监控页）
- [x] 数据库会话
- [x] `users` 表
- [x] 安全（bcrypt + JWT）
- [x] `init_db`、演示账号种子
- [x] 应用初始化（lifespan、CORS）
- [ ] 指标、安全响应头

**验收**：启动自动建表、生成演示账号；请求日志带 request_id。

### M1 SecureRAG + 固定工作流
- RBAC 依赖与角色校验
- 文档上传、分块、向量化；payload 写入 `allowed_roles`
- Qdrant 检索过滤 + Review Node
- LangGraph 固定工作流（无图谱）
- 引用展示、审批、审计
- 基础前端：登录、问答、复核

**验收**：角色 A 无法召回角色 B 的文档；越权用例拦截率 100%；答案带可点击引用。

### M2 GraphRAG
- Neo4j 图模型与导入脚本（已完成）
- 多跳影响查询（已完成，DIRECT / REGION / PORT / ROUTE 四类规则）
- 图谱界面与路径高亮（已完成）
- 与 SecureRAG 结果合并（已完成，图谱路径以 `[G编号]` 进入提示词）

**验收**：给定风险事件，返回受影响工厂与出海口路径；图谱证据随回答展示。Benchmark 路径命中率留到 M3。

### M3 Memory + Benchmark + 交付
- Redis 短期记忆、PostgreSQL 长期记忆
- Benchmark 用例集与指标、CI 回归门禁
- Prometheus/Grafana、Docker Compose
- 分层测试、README 与演示脚本

**验收**：多轮追问能利用历史；Benchmark 可复现；`docker compose up` 一键启动。

## 13. 当前进度快照

```
Phase 0  ✅
Phase 1  ✅  配置 / 日志 / 数据库 / 安全 / 应用初始化
M1       🚧  登录、用户、文档摄取、SecureRAG 检索、风险问答（含 SSE）已完成；固定工作流、复核台、审计待补
M2       🚧  图模型、幂等导入、多跳影响分析、图谱页面、问答图谱证据已完成；路径命中率评测待 M3
M3       ⬜
```

## 14. 主要风险与对策

| 风险 | 对策 |
|---|---|
| 范围过大 | 严格按 M1 → M2 → M3，先闭环再扩展 |
| 图谱数据不足 | 用公开供应链数据 + 自造演示数据，明确标注模拟 |
| 权限越权 | 双层过滤 + Review Node + 越权用例测试 |
| LLM 判定不稳定 | 规则路由 + 结构化输出 + 人工审批兜底 |
| Benchmark 数字不可信 | 用例与脚本入库，指标可复现 |
| 记忆泄露 | 按用户隔离，只存摘要，写入前敏感检查 |

## 15. 新增配置项（草案）

```ini
# Neo4j
APP_NEO4J_URI=bolt://localhost:7687
APP_NEO4J_USER=neo4j
APP_NEO4J_PASSWORD=change-me
APP_NEO4J_DATABASE=neo4j

# SecureRAG
APP_SECURE_RAG_ENFORCE_ROLES=true
APP_SECURE_RAG_REVIEW_MAX_RETRIES=1
APP_SECURE_RAG_MAX_DROP_RATIO=0.5

# Memory
APP_MEMORY_SESSION_TTL_SECONDS=3600
APP_MEMORY_MAX_TURNS=10
APP_MEMORY_LONG_TERM_ENABLED=true

# Benchmark
APP_BENCHMARK_MAX_CASES=200
APP_BENCHMARK_MIN_HIT_RATE=0.8
APP_BENCHMARK_REQUIRE_ZERO_LEAK=true
```

## 16. 参考实现：SentinelSCM 对照

本地只读参考：`E:\LLMproject\Multi-Agent Supply Chain Control Tower\sentinel-scm`（MIT）。
只吸收设计与方法，不复制代码。

### 16.1 值得吸收

| 设计 | 参考位置 | 在本项目中的用法 |
|---|---|---|
| 供应链图谱节点与关系 | `backend/database/seed.py` | 第 6.1 节的图模型直接对齐（Supplier / Material / Port / Region / Route / DisruptionEvent / Factory / Warehouse） |
| 四类风险传导规则 | `eval/ground_truth.py` | 第 6.2 节的 DIRECT / REGION / PORT / ROUTE 规则，用纯函数实现 |
| 工作流状态与证据结构 | `backend/agents/state.py` | `Evidence {source, fact, impact}` 作为结论的标准结构 |
| 人工审批中断 | `backend/agents/graph.py` 的 `interrupt_before` | LangGraph checkpointer + `interrupt`，审批后恢复 |
| 独立 ground truth | `backend/eval/ground_truth.py` | 评测脚本不 import 服务代码，纯 Python 重算，防止「自己测自己」 |
| 场景分层评测 | `backend/eval/scenarios.py`、`metrics.py` | 单事件 / 双事件 / 三事件 / held-out；precision / recall / F1 / 风险等级准确率 |
| 单 Agent 基线 | `backend/eval/baseline.py` | 与固定工作流对比，证明图谱推理的价值 |
| 工具边界 | `backend/mcp_server/tools/*` | 风险评估、替代供应商、库存 runway、缓解成本拆成独立 service |

### 16.2 不照搬

| 设计 | 原因 |
|---|---|
| 五 Agent 自由协作 + Planning/Finance 协商循环 | 路径不可控、调试成本高；本项目采用规则路由的固定工作流 |
| MCP 协议调用 | 增加传输层调试成本；MVP 用 service 直接调用，后续再抽协议 |
| 实时网页搜索 | 外部依赖、成本与 SSRF 风险；先用手工/CSV 风险事件 |
| Qwen 特定实现 | 保持 provider 无关，当前接百炼与 DeepSeek，可换其他 OpenAI 兼容服务 |
| 内存 checkpointer 作为唯一状态 | 审批、审计必须持久化到 PostgreSQL |

### 16.3 差异化定位

参考实现 README 自己列出企业化缺口：**tenant isolation、authentication、persistent audit history、production data connectors**。

SupplyGuard 的增量正是这四点：

- 认证 + 接口级/数据级 RBAC
- SecureRAG：文档级权限元数据 + 检索后复核
- 持久化审批单与只追加审计
- 文档、图谱、结构化数据三类输入连接

一句话：**SentinelSCM 证明「图谱 + Agent 推理」可行；SupplyGuard 补上「权限、证据、审批、审计」这一层。**

### 16.4 评测方法沿用

1. 场景集：单事件、事件对、事件三连、held-out 新事件，至少 25 条；
2. ground truth：纯 Python 基于种子数据独立计算，不调用 Neo4j / LLM / 服务代码；
3. 指标：供应商识别 precision / recall / F1、风险等级准确率、图谱路径命中率；
4. 基线：同样的输入交给单次 LLM 调用（无工具、无遍历），对比差距；
5. 新增本项目指标：越权拦截率（目标 100%）、引用覆盖率、审批通过率；
6. 结果写入 `benchmark_runs`，README 只引用可复现的数字。

---

> 维护约定：每完成一个里程碑，更新 README 状态表与本文件第 12–13 节。
