# SupplyGuard

供应链风险 AgentHarness 平台。在 RBAC 权限约束下，融合 SecureRAG、GraphRAG、Memory 与 LangGraph 固定工作流，为采购、物流、质量、财务等多角色提供**可引用、可审计、可 Benchmark** 的风险洞察与决策支持。

> 当前状态：**开发中（Phase 1）**。登录与前端页面骨架已可运行，风险检索、图谱分析、审批等功能尚未实现。
> 详细架构与数据模型见 [docs/architecture.md](docs/architecture.md)；执行计划、任务拆分与验收标准见 [PROJECT_PLAN.md](PROJECT_PLAN.md)；依赖函数速查见 [docs/library-cheatsheet.md](docs/library-cheatsheet.md)。

## 演示场景

以**宁德时代（CATL）**的公开供应链信息为背景：锂/钴原料供应商 → 正极与隔膜 → 电芯基地 → 港口 → 海外客户。

所有文档、指标与风险结论均为**演示数据**，基于公开资料改编，不构成对任何真实公司的评价、投资或经营建议。

演示账号（密码统一 `catl123`）：

| 账号 | 角色 |
|---|---|
| `catl_admin` | 管理员 |
| `catl_procurement` | 采购 |
| `catl_logistics` | 物流 |
| `catl_quality` | 质量 |
| `catl_finance` | 财务 |

## 不是又一个 RAG 问答 Demo

普通 RAG 项目做的是「上传文档 → 检索 → 回答」。SupplyGuard 的重点是**在权限和流程约束下做风险决策**：

| 常见 RAG Demo | SupplyGuard |
|---|---|
| 所有用户看到同一批文档 | 向量 payload 带角色权限，检索前过滤 + 检索后复核，越权内容不进入模型上下文 |
| 只有文档检索 | SecureRAG（文档证据）+ GraphRAG（供应链多跳影响）双通道 |
| LLM 自主规划，路径不可控 | 固定多节点工作流 + 规则路由，每一步可回溯 |
| 多轮对话各说各的 | Redis 短期会话 + PostgreSQL 长期记忆，按用户隔离 |
| 回答完就结束 | 结论附证据、可审批、写入审计 |
| 没有评测 | 内置 Benchmark：检索命中率、越权拦截率、图谱路径命中率 |

## 核心能力（规划中）

| 能力 | 说明 | 状态 |
|---|---|---|
| RBAC 多角色 | 采购 / 物流 / 质量 / 财务 / 管理员，权限贯穿检索与接口 | 🚧 |
| SecureRAG | Qdrant payload 写入权限元数据，检索前过滤、Review Node 二次校验 | ⬜ |
| GraphRAG | Neo4j 供应链图谱，风险事件多跳影响分析 | ⬜ |
| 固定工作流 | LangGraph 多节点编排，规则路由替代自主规划 | ⬜ |
| Memory | Redis 短期会话 + PostgreSQL 长期偏好与历史风险 | ⬜ |
| 可引用结论 | 每条风险结论标注来源文档与图谱路径 | ⬜ |
| 审批与审计 | 高风险结论人工审批，全过程只追加审计 | 🚧 |
| Benchmark | 场景集评测：Hit@K、越权拦截率、图谱路径命中率 | ⬜ |

## 技术栈

- **后端**：Python 3.11+ / FastAPI / LangGraph / SQLAlchemy 2.0
- **数据**：PostgreSQL / Qdrant（文档向量）/ Neo4j（供应链图谱）/ Redis + RQ
- **模型**：阿里百炼 Embedding（`text-embedding-v3`）+ DeepSeek LLM（`deepseek-chat`），均走 OpenAI 兼容接口，密钥放 `.env`
- **前端**：Vue 3 + Vite + JavaScript + Element Plus（M1 起逐步）
- **可观测**：JSON 日志、请求 ID、prometheus-client + Grafana
- **部署**：Docker Compose

## 架构示意

```
Vue 3 SPA（风险看板 / 风险问答 / 供应商图谱 / 复核台 / Benchmark）
        │ HTTP + SSE（JWT 身份上下文）
FastAPI（中间件、鉴权、RBAC、路由）
        │
LangGraph 固定工作流
  intake → classify → secure_retrieve → graph_impact
         → review（权限/策略复核）→ synthesize → approval → audit
        │
┌───────────┬────────────┬──────────────┬───────────────┐
│ Qdrant    │ Neo4j      │ PostgreSQL   │ Redis         │
│ 文档证据   │ 供应链图谱  │ 业务/记忆/审计 │ 会话记忆/队列  │
│ + 权限过滤 │ 多跳影响    │              │               │
└───────────┴────────────┴──────────────┴───────────────┘
```

## 快速开始

### 环境要求

- Python 3.11 及以上（本机开发使用 3.13）
- 可选：Qdrant（文档检索）、Neo4j（图谱写分析）、Redis（异步任务与记忆）；Embedding 与 LLM 需要百炼 / DeepSeek 密钥

### 安装与启动

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS / Linux

pip install -r requirements.txt
pip install -r requirements-dev.txt

copy .env.example .env              # Windows
# cp .env.example .env              # macOS / Linux

uvicorn app.main:app --reload --port 8000
```

需要文档摄取时，再启动 Redis 与 worker（两个终端）：

```bash
docker compose up -d redis          # 6380 端口，避开本机已有 Redis
python -m app.workers.ingestion_worker
```

### 验证

```bash
curl http://127.0.0.1:8000/api/health/live
# {"status":"ok","environment":"development"}
```

接口文档：http://127.0.0.1:8000/docs

### 日志

所有日志以一行 JSON 输出到控制台，自动带 `request_id`、`user`：

```json
{"timestamp":"2026-10-22T14:01:50+00:00","level":"INFO","logger":"app.main","message":"应用已创建","request_id":null,"env":"development"}
```

把 `.env` 里 `APP_LOG_LEVEL` 改为 `DEBUG` 可以看到健康检查的访问日志。

## 前端

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

目前登录页、管理页的账号管理、文档库已接真实后端，其余页面仍使用 `src/api/mock.js` 中的占位数据；后端接口就绪后逐个替换为真实请求。

## 项目结构

```
app/
├── main.py             应用工厂：日志、中间件、路由组装
├── core/               配置、日志、请求上下文、安全、指标
├── db/                 数据库会话、ORM 模型、审计 CRUD
├── models/             Pydantic 请求/响应模型
├── services/
│   ├── retrieval.py    Qdrant 检索（SecureRAG）
│   ├── graph.py        Neo4j 图谱查询（GraphRAG）
│   ├── workflow.py     LangGraph 固定工作流
│   ├── memory.py       短期/长期记忆
│   ├── benchmark.py    评测集与指标
│   └── ...             摄取、LLM、审批、审计
├── api/                鉴权依赖与路由
└── workers/            异步摄取、图谱构建、Benchmark worker

docs/architecture.md    架构、数据模型、工作流、路线图
tests/                  分层测试（待补）
ops/                    Prometheus / Grafana 配置（待补）
frontend/               Vue 3 前端（页面与交互完成，数据为 mock）
```

## 开发路线

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 项目脚手架与依赖 | ✅ |
| Phase 1 | 配置、日志、数据库、安全、应用初始化 | ✅ |
| 前端骨架 | Vue 3 页面与交互（mock 数据） | ✅ |
| M1 | RBAC + SecureRAG + 固定工作流 + Review Node + 审计 + 基础前端 | ⬜ |
| M2 | Neo4j 图谱构建 + GraphRAG 多跳影响分析 + 图谱界面 | ⬜ |
| M3 | Memory + Benchmark + 指标 + Docker + 分层测试 | ⬜ |

每个阶段的验收标准见 [docs/architecture.md](docs/architecture.md) 第 12 节。

## 与参考项目的关系

项目基础设施参考 [Complyra](https://github.com/weiguangli-io/complyra)（MIT License）的架构思路（审批、审计、日志）；图谱模型、风险传导规则与评测方法参考本地只读项目 SentinelSCM（MIT）的设计。代码均为独立重写，不复制参考实现；业务域、SecureRAG、RBAC、Memory 与 Benchmark 为本项目新增设计。

## 目录约定

- 业务代码只放 `app/`，不在根目录堆脚本
- 配置一律通过 `.env` + `APP_` 前缀，不写死在代码里
- `.env` 不入库；新增配置项时同步更新 `.env.example`
- 每完成一个里程碑，更新本 README 状态表与 `docs/architecture.md` 的进度
