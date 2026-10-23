# 依赖函数速查表

只收录本项目实际用到的函数。遇到新的再往对应分组里补。

阅读方法：每个函数问三件事——**输入是什么、返回什么、有没有副作用**。

---

## FastAPI

| 用法 | 作用 | 说明 |
|---|---|---|
| `FastAPI(...)` | 创建应用实例 | `lifespan` 参数绑定启动/关闭钩子 |
| `APIRouter(prefix="/auth", tags=["auth"])` | 创建一组路由 | `prefix` 自动加到路径前，`tags` 用于文档分组 |
| `@router.post("/login")` | 注册 POST 接口 | GET 用 `@router.get` |
| `app.include_router(router, prefix="/api")` | 把路由挂到应用 | 最终路径 = 应用前缀 + 路由前缀 + 路径 |
| `Depends(func)` | 声明依赖 | FastAPI 自动调用 `func` 并把返回值传给参数 |
| `HTTPException(status_code=..., detail=...)` | 主动返回错误 | `raise` 后函数立即结束 |
| `status.HTTP_401_UNAUTHORIZED` | 状态码常量 | 比写数字 401 可读 |
| `response_model=UserResponse` | 声明响应结构 | 多余字段会被过滤，并出现在 `/docs` |

示例：

```python
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_database_session)) -> TokenResponse:
    ...
```

- `payload`：FastAPI 从 JSON 请求体解析并校验；
- `db`：由 `get_database_session` 提供，请求结束自动关闭。

---

## fastapi.security / Starlette

| 用法 | 作用 | 说明 |
|---|---|---|
| `HTTPBearer(auto_error=False)` | 解析 `Authorization: Bearer` | 缺令牌时返回 `None`，方便自定义 401 |
| `HTTPAuthorizationCredentials` | 解析结果 | `.credentials` 是令牌本体 |
| `BaseHTTPMiddleware` | 自定义中间件 | 实现 `dispatch(request, call_next)` |
| `await call_next(request)` | 调用下游 | 返回 Response，或抛异常 |

---

## SQLAlchemy

| 用法 | 作用 | 说明 |
|---|---|---|
| `create_engine(url)` | 创建连接池 | 应用启动时一次 |
| `sessionmaker(bind=engine, ...)` | 会话工厂 | `SessionLocal()` 产生一个会话 |
| `DeclarativeBase` | ORM 模型基类 | 继承后字段用 `mapped_column` 声明 |
| `Mapped[str]` + `mapped_column(...)` | 声明列 | 类型 + 约束（长度、唯一、索引） |
| `Session` | 会话类型 | 用于参数标注 |
| `select(User)` | 构造 `SELECT` | **不执行**，只是查询对象 |
| `.where(User.username == x)` | 加条件 | 多个条件默认 AND；值参数化，防注入 |
| `session.scalar(query)` | 执行并取第一个值 | 整行查询时返回对象或 `None` |
| `session.get(User, pk)` | 按主键查 | 返回对象或 `None` |
| `session.add(obj)` | 登记待插入 | **不发 SQL**，flush/commit 时才写 |
| `session.flush()` | 立即发 SQL，不提交 | 让后续操作能用到新主键 |
| `session.commit()` | 提交事务 | 数据真正落库 |
| `session.rollback()` | 回滚事务 | 异常时清理半截写入 |
| `Base.metadata.create_all(engine)` | 建缺失的表 | 只建不改，改表结构需要迁移工具 |

示例：

```python
user = db.scalar(select(User).where(User.username == payload.username))
```

先构造查询，再由 `scalar` 执行。

---

## Pydantic / pydantic-settings

| 用法 | 作用 | 说明 |
|---|---|---|
| `BaseModel` | 请求/响应模型基类 | 字段校验 + 序列化 |
| `Field(min_length=1, max_length=128)` | 字段约束 | 校验失败返回 422 |
| `field: str \| None = None` | 可选字段 | 序列化为 `null` |
| `BaseSettings` | 配置类基类 | 从环境变量读取 |
| `SettingsConfigDict(env_prefix="APP_", env_file=".env")` | 配置读取规则 | `database_url` ← `APP_DATABASE_URL` |
| `@lru_cache` | 缓存配置实例 | 保证全局只解析一次 `.env` |

---

## loguru

| 用法 | 作用 | 说明 |
|---|---|---|
| `logger.info("...")` | 打日志 | 占位符用 `{}`，不是 `%s` |
| `logger.bind(key=value)` | 附加结构化字段 | 字段会平铺进 JSON |
| `logger.exception("...")` | 记录异常 | 自动带堆栈 |
| `logger.add(sink, level=...)` | 添加输出目标 | sink 可以是函数 |
| `logger.remove()` | 移除默认输出 | 通常在 `setup_logging` 里 |
| `logger.contextualize(request_id=...)` | 给一段代码加日志上下文 | 期间所有日志自动带该字段 |
| `logger.opt(depth=..., exception=...)` | 调整调用位置/异常 | 桥接标准库日志时使用 |

示例：

```python
logger.bind(supplier_id="S-GFLY").warning("供应风险")
```

输出中会多一个 `"supplier_id": "S-GFLY"`。

---

## bcrypt / python-jose

| 用法 | 作用 | 说明 |
|---|---|---|
| `bcrypt.gensalt()` | 生成随机盐 | 每次哈希都不同 |
| `bcrypt.hashpw(password_bytes, salt)` | 生成哈希 | 返回 bytes |
| `bcrypt.checkpw(password_bytes, hash)` | 校验密码 | 恒定时间比较 |
| `jwt.encode(payload, key, algorithm)` | 签发 JWT | 返回三段式字符串 |
| `jwt.decode(token, key, algorithms=[...])` | 校验并解析 | 必须显式指定算法 |
| `JWTError` | JWT 校验异常 | 过期、签名错误、格式错误 |

---

## 启动与调试

```bash
# 启动后端
E:/conda/envs/RoleGuard_RAG/python.exe -m uvicorn app.main:app --port 8000

# 接口文档（可在线调试）
http://127.0.0.1:8000/docs

# 启动前端
cd frontend && npm run dev
```

---

## 怎么查一个没见过的函数

1. IDE 里按住 `Ctrl` 点函数名，跳到定义；
2. 鼠标悬停看类型和文档；
3. 终端里 `help(函数)` 或 `inspect.signature(函数)`；
4. 查对应包的官方文档，优先看示例；
5. 实在不清楚，直接问：「这个函数的输入、输出、副作用是什么？」