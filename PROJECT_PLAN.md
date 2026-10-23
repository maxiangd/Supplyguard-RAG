# SupplyGuard 项目规划大纲

> 配套文档：[README.md](README.md)（项目简介）、[docs/architecture.md](docs/architecture.md)（技术架构）
> 本文回答的是：**这个项目怎么一步步做出来，每一步怎么验收。**

---

## 1. 项目目标

### 最终目标

做出一个可运行、可演示、可讲清设计的供应链风险 AgentHarness 平台：

- 采购、物流、质量、财务四类角色，看到的证据不同
- 风险结论带文档引用与图谱路径，可回溯
- 高风险结论需要人工审批
- 全过程写入审计
- 有一套可复现的 Benchmark，能给出真实指标

**演示主体**：以宁德时代（CATL）的公开供应链信息为背景（锂/钴原料 → 正极/隔膜 → 电芯基地 → 港口 → 海外客户）。所有数据为公开资料改编的演示数据，不构成对真实公司的评价。

### 三个必须演示成功的场景

| 场景 | 验收点 |
|---|---|
| 角色越权 | 采购角色提问，系统不会召回只属于财务的合同内容 |
| 图谱影响 | 输入「某港口停运」，返回受影响的物料、供应商、在途订单路径 |
| 审批闭环 | 高风险结论进入审批台，批准后才能拿到最终答案，审计可查 |

### 非目标（明确不做）

- 不自动下单、不修改 ERP 数据
- 不做全网爬虫
- 不在 MVP 阶段做代码执行沙箱
- 不追求多智能体自由协作，工作流保持固定、可回溯

---

## 2. 交付物

| 交付物 | 内容 | 状态 |
|---|---|---|
| 可运行代码 | FastAPI 后端 + Vue 3 前端 + worker | ⬜ |
| 数据库与迁移 | SQLite/PostgreSQL 表结构 + Alembic | ⬜ |
| Docker Compose | api / worker / web / postgres / qdrant / neo4j / redis | ⬜ |
| 文档 | README、架构、项目规划、API 说明 | 🚧 |
| 演示数据 | 供应商、物料、工厂、风险事件、制度文档 | ⬜ |
| 演示脚本 | 5–8 分钟走完三个场景 | ⬜ |
| Benchmark 报告 | 指标、用例、复现命令 | ⬜ |
| 测试 | 单测 + 路由 + 端到端 | ⬜ |

---

## 3. 里程碑总览

| 里程碑 | 目标 | 主要交付 | 依赖 | 验收 |
|---|---|---|---|---|
| Phase 0 | 脚手架 | 依赖、配置、目录 | 无 | 能启动空应用 |
| Phase 1 | 后端基建 | 日志、数据库、安全、应用初始化 | Phase 0 | 健康检查 + 自动建表 + 默认账号 |
| M1 | SecureRAG 闭环 | RBAC、文档摄取、权限检索、固定工作流、审批审计、基础前端 | Phase 1 | 三个场景中的「角色越权」「审批闭环」 |
| M2 | GraphRAG | Neo4j 图谱、多跳查询、图谱界面 | M1 | 「图谱影响」场景 |
| M3 | Memory + Benchmark | 记忆、评测集、指标、Docker、测试 | M2 | 指标可复现、一键启动 |

---

## 4. 工作分解（WBS）

### A. 基础设施

- [x] Python 依赖与虚拟环境
- [x] 配置（pydantic-settings，`APP_` 前缀）
- [x] JSON 日志、请求 ID、访问日志
- [ ] 内存日志缓冲 `log_buffer.py`
- [ ] 安全响应头、Prometheus 指标
- [ ] Dockerfile / docker-compose
- [ ] Alembic 迁移

### B. 身份与权限

- [x] bcrypt 密码哈希 + JWT 签发/解析
- [x] `api/dependencies.py`：当前用户、角色校验
- [ ] 登录 / 登出 / 刷新
- [ ] 用户管理（管理员）
- [ ] 角色：`admin` / `procurement` / `logistics` / `quality` / `finance`
- [ ] 越权测试：跨角色访问、伪造令牌

### C. 文档与 SecureRAG

- [ ] 文档上传、校验、存储
- [ ] 异步摄取：解析、分块、向量化
- [ ] Qdrant 集合与 payload（`allowed_roles`、`sensitivity`）
- [ ] 检索前过滤（Qdrant filter）
- [ ] 检索后复核（Review Node）
- [ ] 文档列表按权限返回
- [ ] 越权召回测试

### D. 固定工作流

- [ ] `WorkflowState` 定义
- [ ] 节点：intake / classify / plan / secure_retrieve / graph_impact / review / synthesize / approval_gate / audit
- [ ] 规则路由表
- [ ] 条件边与循环上限
- [ ] SSE 事件输出
- [ ] 工作流单测（mock LLM / Qdrant / Neo4j）

### E. GraphRAG

- [ ] Neo4j 连接与约束
- [ ] 节点/关系模型：Company、Supplier、Material、Factory、Warehouse、Port、Region、ShippingRoute、Shipment、DisruptionEvent
- [ ] 导入脚本（种子数据幂等写入，参考 SentinelSCM 的 MERGE 方式）
- [ ] 四类风险传导规则（DIRECT / REGION / PORT / ROUTE）用纯函数实现
- [ ] 纯函数单测 + 与图谱查询结果对照
- [ ] 多跳查询模板
- [ ] 路径可信度与跳数限制
- [ ] 图谱接口与前端可视化

### F. Memory

- [ ] Redis 会话读写（TTL、轮次上限）
- [ ] PostgreSQL 长期记忆表与 CRUD
- [ ] 记忆摘要生成与敏感检查
- [ ] 多轮追问场景测试

### G. 审批与审计

- [ ] 审批策略：风险阈值 + 角色
- [ ] 审批单创建、列表、决定
- [ ] 审批前不返回最终结论
- [ ] 审计只追加写入
- [ ] 审计搜索与 CSV 导出（公式注入转义）

### H. Benchmark

- [ ] 用例格式：问题、角色、期望供应商/物料、期望路径、禁止文档
- [ ] 场景分层：单事件、事件对、事件三连、held-out 新事件（至少 25 条）
- [ ] 独立 ground truth：纯 Python 重算，不 import 服务 / Neo4j / LLM
- [ ] 单 Agent 基线：同样输入只调用一次 LLM，用于对比
- [ ] 指标：precision / recall / F1、风险等级准确率、路径命中率、Hit@K、越权拦截率
- [ ] 报告输出（JSON + Markdown）
- [ ] CI 回归门禁

### I. 前端（页面与交互完成，数据为 mock）

- [x] 登录（真实后端接口）
- [x] 风险看板
- [x] 风险问答（工作流进度、引用面板）
- [x] 供应商图谱
- [x] 复核台 / 审批台
- [x] Benchmark 页面
- [x] 审计与管理

### J. 交付

- [ ] 演示数据与种子脚本
- [ ] 演示脚本（5–8 分钟）
- [ ] Docker Compose 一键启动
- [ ] README / 架构 / 规划文档同步
- [ ] 提交与推送

---

## 5. 代码结构与依赖规则

```
app/
├── main.py          组装：日志、中间件、路由、生命周期
├── core/            无业务依赖：配置、日志、安全、指标
├── db/              数据层：会话、ORM 模型、审计 CRUD
├── models/          Pydantic 请求/响应模型
├── services/        业务逻辑：检索、图谱、工作流、记忆、审批
├── api/             接口层：依赖、路由
└── workers/         后台任务：摄取、图谱构建、评测
```

### 依赖方向（只能单向）

```
api → services → db / core
workers → services → db / core
models/schemas ← api / services
```

规则：

- `core/` 不能 import `services/`、`api/`
- `db/` 不能 import `api/`
- 路由函数只做参数校验与调用服务，不写业务逻辑
- Prompt、SQL、图谱查询分别放在对应 service 内，不散落在路由里

### 新增一个功能时，按这个顺序放

1. 数据结构 → `db/tables.py`（表）或 `models/api_models.py`（接口模型）
2. 业务逻辑 → `services/<模块>.py`
3. 接口 → `api/routes/<模块>.py` + 在 `main.py` 注册
4. 权限 → `api/dependencies.py`
5. 测试 → `tests/`
6. 文档 → README 状态表 / 架构文档

---

## 6. 开发流程（每个任务都这样走）

1. **明确验收**：用一句话写出「什么情况算完成」
2. **先设计数据**：字段、索引、权限归属
3. **写服务层**：纯函数/类，不依赖 FastAPI
4. **写接口**：参数校验、权限、调用服务
5. **写测试**：正常 + 越权 + 边界
6. **本地验证**：真实请求或脚本跑一次
7. **更新文档**：README 状态、架构变化
8. **提交**：一个任务一个 commit

### 任务卡片模板

```
任务：实现 XX
输入：
输出：
涉及文件：
验收：
  - 正常情况：
  - 越权情况：
  - 失败情况：
```

### 完成定义（DoD）

一个任务只有同时满足以下条件才算完成：

- [ ] 代码已实现并本地跑通
- [ ] 有测试或可复现的验证命令
- [ ] 越权/异常路径有处理
- [ ] 文档已同步
- [ ] 已提交

---

## 7. 分支与提交规范

个人项目也要保持可读的提交历史：

```
main                始终可运行
feature/<模块>      一个功能分支
```

提交信息前缀：

| 前缀 | 用途 |
|---|---|
| `feat:` | 新功能 |
| `fix:` | 修复 |
| `docs:` | 文档 |
| `refactor:` | 重构 |
| `test:` | 测试 |
| `chore:` | 依赖、配置 |

示例：

```
feat(security): 实现 bcrypt 密码哈希与 JWT 签发
feat(retrieval): Qdrant 检索增加 allowed_roles 过滤
test(retrieval): 增加跨角色越权召回用例
docs: 更新 M1 进度与接口说明
```

提交前检查：

- `git status` 不包含 `.env`、`data/`、缓存
- `ruff check app` 通过
- 应用能启动

---

## 8. 测试策略

| 层级 | 测什么 | 是否依赖外部服务 |
|---|---|---|
| 单元 | 分块、权限过滤、风险评分、路由规则 | 否 |
| 服务 | 检索、工作流节点、审批链 | 用 Fake LLM / Fake Embedder / 内存 Qdrant |
| 路由 | 登录、越权、参数校验、状态码 | 用 TestClient + SQLite 内存库 |
| 端到端 | 上传 → 检索 → 结论 → 审批 → 审计 | 本地 Docker 或 mock 全套 |
| Benchmark | 越权拦截率、命中率、路径命中率 | 可在 CI 用 mock 跑 |

原则：

- 默认测试不依赖 Ollama / Qdrant / Neo4j / Redis
- 真实环境用 Docker Compose 做冒烟
- 越权用例是必测项，不能省

---

## 9. 文档策略

| 文档 | 什么时候更新 |
|---|---|
| `README.md` | 每个里程碑结束时更新状态表 |
| `docs/architecture.md` | 架构、数据模型、工作流变化时 |
| `PROJECT_PLAN.md`（本文） | 任务完成勾选、计划调整时 |
| `docs/adr/`（可选） | 重要技术取舍，如「为什么用 Neo4j 而不是 SQL 递归查询」 |

---

## 10. 风险与应对

| 风险 | 表现 | 应对 |
|---|---|---|
| 范围膨胀 | 同时做图谱、记忆、前端 | 严格按 M1 → M2 → M3，M1 不碰 Neo4j |
| 指标造假 | 简历写了 100% 但没测过 | Benchmark 入库、可复现，数字只从报告里抄 |
| 图谱数据不足 | 没有真实供应链数据 | 用公开数据 + 自造演示数据，文档标注模拟 |
| 权限漏洞 | 只做接口校验，忘了数据层 | SQL 与 Qdrant 双层过滤 + 越权测试 |
| LLM 不稳定 | 输出格式乱、判定漂移 | 结构化输出 + 规则兜底 + 人工审批 |
| 时间不足 | 每个模块都做一半 | 每个阶段先做最小闭环，再补细节 |

---

## 11. 进度看板

| 模块 | 状态 | 备注 |
|---|---|---|
| Phase 0 脚手架 | ✅ | Docker/Alembic 待补 |
| Phase 1 基建 | ✅ | 配置、日志、会话、3 张表、bcrypt+JWT、启动初始化完成 |
| 身份与权限 | 🚧 | 登录、JWT、用户/角色依赖完成；用户管理接口待补 |
| 文档与 SecureRAG | ⬜ | M1 |
| 固定工作流 | ⬜ | M1 |
| 审批与审计 | ⬜ | M1 |
| GraphRAG | ⬜ | M2 |
| Memory | ⬜ | M3 |
| Benchmark | ⬜ | M3 |
| 前端 | 🚧 | 8 个页面与交互完成，数据为 mock，待接后端 |
| 部署与交付 | ⬜ | M3 |

---

## 12. 接下来的任务顺序

1. `core/security.py`：bcrypt + JWT
2. `db/initialize_database.py`：`init_db` + 演示账号种子
3. `main.py` 收尾：lifespan、CORS、安全响应头
4. `models/api_models.py` + `api/dependencies.py`：登录、当前用户、角色校验
5. 用户管理接口
6. 文档表、上传与摄取队列
7. Qdrant 集合、payload、检索过滤
8. Review Node 与越权测试
9. 四类风险传导规则（纯函数）+ 证据结构（source / fact / impact）
10. LangGraph 固定工作流 + `interrupt` 审批恢复
11. Neo4j 图模型、导入脚本与多跳影响分析
12. 独立 ground truth、场景集与单 Agent 基线
13. 审批、审计、SSE 与基础前端

> 每完成一项，勾选第 4 节对应任务，并更新第 11 节状态。
