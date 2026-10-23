"""密码哈希与 JWT 访问令牌。

本模块只做两件"纯计算"的事，不依赖数据库、不依赖 FastAPI：
    1. 用户密码 → bcrypt 哈希；校验明文密码与哈希是否匹配
    2. 用户身份 → 签发 JWT；校验 JWT 并解析出身份信息
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt 算法只处理密码的前 72 个字节（字节，不是字符）。
# bcrypt 5.x 遇到超长密码会直接抛 ValueError，所以由我们先检查并给出明确错误。
BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """JWT 校验失败时抛出的统一异常。

    作用：上层（api 层）只需要捕获 TokenError 并返回 401，
        不用知道底层用的是哪个 JWT 库。以后换库不影响路由代码。
    """


@dataclass(frozen=True)
class TokenPayload:
    """从 JWT 里解析出来的身份信息。

    作用：把 jwt.decode 返回的普通 dict 变成字段有名字、有类型的对象，
        上层用 payload.user_id 即可，不用记字符串 key，也不会拼错。
    """

    user_id: str            # 用户唯一 ID，对应 users.user_id
    role: str | None        # 角色；令牌里没写时为 None
    expires_at: datetime    # 过期时间（UTC）


def _password_to_bytes(password: str) -> bytes:
    """把密码转成 bcrypt 需要的字节串，并检查长度上限。

    参数：password —— 用户输入的明文密码。
    返回：UTF-8 编码后的 bytes。
    异常：ValueError —— 密码为空，或编码后超过 72 字节。
    """
    # 空密码直接拒绝：哈希空字符串没有意义，通常说明调用方传错了
    if not password:
        raise ValueError("密码不能为空")

    # bcrypt 限制的是字节数，所以先编码再判断长度
    password_bytes = password.encode("utf-8")

    # 超长时明确报错，不静默截断（截断会让不同的长密码变得等价）
    if len(password_bytes) > BCRYPT_MAX_BYTES:
        raise ValueError(f"密码过长：UTF-8 编码后不能超过 {BCRYPT_MAX_BYTES} 字节")

    return password_bytes


def hash_password(password: str) -> str:
    """把明文密码变成 bcrypt 哈希字符串，用于存入数据库。

    参数：password —— 用户输入的明文密码。
    返回：约 60 字符的哈希串，已包含算法版本、工作因子和随机盐。
    异常：ValueError —— 密码为空或超过 72 字节。
    """
    password_bytes = _password_to_bytes(password)

    # 每次生成新的随机盐：同一个密码两次哈希结果不同，可防彩虹表
    salt = bcrypt.gensalt()

    # hashpw 返回 bytes，例如 b"$2b$12$..."
    hashed = bcrypt.hashpw(password_bytes, salt)

    # 数据库字段是字符串，bcrypt 输出只用 ASCII，解码是安全的
    return hashed.decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """校验「用户输入的密码」与「数据库里的哈希」是否匹配。

    参数：password —— 本次登录输入的明文；password_hash —— 库中存的哈希。
    返回：True 表示密码正确；False 表示不正确、输入非法或哈希损坏。
    """
    try:
        password_bytes = _password_to_bytes(password)
    except ValueError:
        # 空密码或超长，一律按"密码错误"处理，不向调用方暴露细节
        return False

    try:
        # checkpw 内部是恒定时间比较，不会因比较耗时泄露"对了几位"
        return bcrypt.checkpw(password_bytes, password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        # 哈希被手工改坏、或不是合法的 bcrypt 格式，同样视为校验失败
        return False


def create_access_token(
    user_id: str,
    *,
    role: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT 访问令牌。

    参数：
        user_id：用户 ID，写进标准字段 sub。
        role：可选的角色声明。
        expires_minutes：有效期（分钟），不传则用配置里的默认值。
    返回：三段式 JWT 字符串。
    """
    now = datetime.now(UTC)

    # 用 is not None 而不是 or：显式传 0 时不会被默认值覆盖
    minutes = (
        expires_minutes
        if expires_minutes is not None
        else settings.access_token_expire_minutes
    )

    payload: dict[str, Any] = {
        "sub": user_id,                      # 令牌代表谁
        "iat": now,                          # 签发时间
        "exp": now + timedelta(minutes=minutes),  # 过期时间，decode 时自动校验
    }

    # 可选字段：没有就不写
    if role is not None:
        payload["role"] = role

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> TokenPayload:
    """校验 JWT 并解析出身份信息。

    参数：token —— 前端通过 Authorization: Bearer <token> 传来的字符串。
    返回：TokenPayload 对象。
    异常：TokenError —— 签名错误、已过期、格式非法或缺少必要字段。
    """
    try:
        # algorithms 必须显式限定；允许任意算法会留下 alg=none 之类的绕过口子
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        # 签名错误、过期、格式错误都归到 JWTError，统一转成本项目的异常
        raise TokenError("令牌无效或已过期") from exc

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise TokenError("令牌缺少用户标识")

    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        # 不允许没有过期时间的令牌，避免出现永久有效的凭证
        raise TokenError("令牌缺少过期时间")

    role = claims.get("role")

    return TokenPayload(
        user_id=user_id,
        # 类型检查防止伪造出 role=["admin"] 这类意外结构
        role=role if isinstance(role, str) else None,
        expires_at=datetime.fromtimestamp(exp, UTC),
    )
