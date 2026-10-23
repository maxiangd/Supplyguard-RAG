from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_prefix="APP_" 表示所有环境变量都要带 APP_ 前缀。
    # 映射规则：环境变量名 = "APP_" + 字段名.upper()
    # 例如 database_url → APP_DATABASE_URL
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略未声明的 APP_* 变量，避免环境里多一个变量就报错
    )

    # 应用
    app_name: str = "SupplyGuard"
    app_version: str = "0.1.0"
    env: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"

    # 认证
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    # 字段名必须和 .env 里的 APP_ACCESS_TOKEN_EXPIRE_MINUTES 完全对应
    access_token_expire_minutes: int = 60
    # 演示账号共用一个密码；账号与角色见 db/init_db.py 的 SEED_USERS
    demo_password: str = "catl123"

    # 数据库
    database_url: str = "postgresql+psycopg://supplyguard:123456@127.0.0.1:5432/supplyguard"

    # 向量库
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "supplyguard_chunks"

    # 图谱（GraphRAG）
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"

    # Embedding
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

    # LLM
    llm_provider: str = "ollama"  # ollama | openai | gemini
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:7b"
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4

    # SecureRAG：检索前按角色过滤，检索后再复核一次
    secure_rag_enforce_roles: bool = True
    secure_rag_review_max_retries: int = 1
    # 一次检索中被权限剔除的比例超过该值时，认为查询异常
    secure_rag_max_drop_ratio: float = 0.5

    # Memory：短会话与长期记忆
    memory_session_ttl_seconds: int = 3600
    memory_max_turns: int = 10
    memory_long_term_enabled: bool = True

    # Benchmark
    benchmark_max_cases: int = 200
    benchmark_min_hit_rate: float = 0.8
    benchmark_require_zero_leak: bool = True

    # 审批 / 输出策略
    require_approval: bool = True
    output_policy_enabled: bool = True

    # CORS
    # 用逗号分隔的字符串而不是 list[str]：pydantic-settings 对 list 默认按 JSON 解析，
    # 直接写 origin1,origin2 会报错；用 property 转换更宽容。
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    # lru_cache 保证 .env 只解析一次，全项目共享同一个 Settings 实例
    return Settings()


settings = get_settings()
