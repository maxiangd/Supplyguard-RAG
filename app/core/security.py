"""密码哈希与 JWT。"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

BCRYPT_MAX_BYTES = 72


class TokenError(Exception):
    """JWT 校验失败。"""


@dataclass(frozen=True)
class TokenPayload:
    user_id: str
    role: str | None
    expires_at: datetime


def _password_bytes(password: str) -> bytes:
    data = password.encode("utf-8")
    if not data:
        raise ValueError("密码不能为空")
    if len(data) > BCRYPT_MAX_BYTES:
        raise ValueError("密码过长")
    return data


def hash_password(password: str) -> str:
    """生成 bcrypt 哈希。"""
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


def create_access_token(
    user_id: str,
    *,
    role: str | None = None,
    expires_minutes: int | None = None,
) -> str:
    """签发 JWT，sub 为用户 ID。"""
    now = datetime.now(UTC)
    minutes = (
        settings.access_token_expire_minutes
        if expires_minutes is None
        else expires_minutes
    )
    payload = {"sub": user_id, "iat": now, "exp": now + timedelta(minutes=minutes)}
    if role is not None:
        payload["role"] = role
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """校验并解析 JWT，失败时抛 TokenError。"""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise TokenError("令牌无效或已过期") from exc

    user_id = claims.get("sub")
    exp = claims.get("exp")
    if not isinstance(user_id, str) or not user_id or not isinstance(exp, (int, float)):
        raise TokenError("令牌缺少必要字段")

    role = claims.get("role")
    return TokenPayload(
        user_id=user_id,
        role=role if isinstance(role, str) else None,
        expires_at=datetime.fromtimestamp(exp, UTC),
    )
