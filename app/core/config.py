"""应用配置：环境变量与 .env 统一使用 APP_ 前缀。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", extra="ignore"
    )

    app_name: str = "SupplyGuard"
    app_version: str = "0.1.0"
    env: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"

    # 认证
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    demo_password: str = "catl123"

    # 数据库
    database_url: str = (
        "postgresql+psycopg://supplyguard:123456@127.0.0.1:5432/supplyguard"
    )

    # 向量库
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "supplyguard_chunks"

    # 图谱
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change-me"
    neo4j_database: str = "neo4j"

    # Embedding
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768

    # LLM
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "deepseek-r1:7b"
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 4

    # SecureRAG
    secure_rag_enforce_roles: bool = True
    secure_rag_review_max_retries: int = 1
    secure_rag_max_drop_ratio: float = 0.5

    # Memory
    memory_session_ttl_seconds: int = 3600
    memory_max_turns: int = 10
    memory_long_term_enabled: bool = True

    # Benchmark
    benchmark_max_cases: int = 200
    benchmark_min_hit_rate: float = 0.8
    benchmark_require_zero_leak: bool = True

    # 审批
    require_approval: bool = True
    output_policy_enabled: bool = True

    # CORS：逗号分隔，用 property 转成列表
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
