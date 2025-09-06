"""
鉴权路由与工具
- 提供两种登录方式：用户名+密码、授权码
- 返回 JWT Bearer Token（HS256，标准库实现），exp 自包含
- 不引入新的三方依赖
"""

from __future__ import annotations

from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from auth import jwt as jwt_lib
from auth import config as auth_config


router = APIRouter(prefix="/api/v1/auth", tags=["鉴权"])


# ============================
# 模型定义
# ============================

class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="明文密码（来自 JSON 配置，不做管理端）")


class CodeRequest(BaseModel):
    code: str = Field(..., description="授权码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============================
# 内部工具
# ============================

def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issue_token(
    subject: str,
    login_mode: str,
    roles: Optional[List[str]] = None,
    groups: Optional[List[str]] = None,
) -> TokenResponse:
    iat = jwt_lib.now_ts()
    expires_in = int(auth_config.get_jwt_expires_seconds())
    payload: Dict[str, Any] = {
        "sub": subject,
        "login_mode": login_mode,
        "iat": iat,
        "exp": iat + expires_in,
        "roles": list(roles or []),
        "groups": list(groups or []),
    }
    secret = auth_config.get_jwt_secret()
    token = jwt_lib.encode(payload, secret)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=expires_in)


def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise _unauthorized("Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _unauthorized("Invalid Authorization header")
    token = parts[1].strip()
    if not token:
        raise _unauthorized("Empty Bearer token")
    return token


# ============================
# 依赖：获取当前身份（解析 JWT）
# ============================

def get_current_identity(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    从 Authorization: Bearer <token> 解析并验证 JWT，返回 claims。
    校验失败一律 401。
    """
    token = _extract_bearer_token(authorization)
    secret = auth_config.get_jwt_secret()
    try:
        claims = jwt_lib.decode(token, secret)
        # 简单校验必要字段
        if "sub" not in claims or "exp" not in claims:
            raise ValueError("Invalid claims")
        return claims
    except ValueError as e:
        raise _unauthorized(str(e))


# ============================
# 端点依赖与鉴权（RBAC）
# ============================

def require_roles(required: List[str], match: str = "any"):
    """
    依赖：校验 JWT claims 中的 roles。
    - required: 需要的角色列表
    - match: "any"（任一即可）或 "all"（全部满足）
    校验失败返回 403。
    """
    def _dep(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
        actual = identity.get("roles")
        if not isinstance(actual, list):
            actual = []
        req = [r for r in (required or []) if isinstance(r, str)]
        if not req:
            ok = True
        elif match == "all":
            ok = all(r in actual for r in req)
        else:
            ok = any(r in actual for r in req)
        if not ok:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient roles")
        return identity
    return _dep


def require_groups(required: List[str], match: str = "any"):
    """
    依赖：校验 JWT claims 中的 groups。
    - required: 需要的组列表
    - match: "any"（任一即可）或 "all"（全部满足）
    校验失败返回 403。
    """
    def _dep(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
        actual = identity.get("groups")
        if not isinstance(actual, list):
            actual = []
        req = [g for g in (required or []) if isinstance(g, str)]
        if not req:
            ok = True
        elif match == "all":
            ok = all(g in actual for g in req)
        else:
            ok = any(g in actual for g in req)
        if not ok:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient groups")
        return identity
    return _dep

# ============================
# 路由
# ============================

@router.post("/login", response_model=TokenResponse)
async def password_login(body: LoginRequest) -> TokenResponse:
    """
    用户名+密码登录（明文对比自 JSON）
    注意：若用户仅提供 password_hash 而无明文 password，本实现不做 bcrypt 校验，会登录失败（预留升级位）。
    """
    user = auth_config.find_user(body.username)
    if not user or not isinstance(user, dict):
        raise _unauthorized("Invalid credentials")

    # 优先明文密码字段（来源 JSON）
    stored_password = user.get("password")
    if stored_password is None:
        # 有 password_hash 但无 password 的情况，当前版本不做 bcrypt 校验
        raise _unauthorized("Invalid credentials")

    if stored_password != body.password:
        raise _unauthorized("Invalid credentials")

    roles, groups = auth_config.resolve_effective_roles(user)
    return _issue_token(subject=body.username, login_mode="password", roles=roles, groups=groups)


@router.post("/code", response_model=TokenResponse)
async def code_login(body: CodeRequest) -> TokenResponse:
    """
    授权码登录：在配置 codes 中存在且未过期（仅校验 expires_at）。
    expires_at: ISO-8601（支持 Z/偏移/本地时间，推荐 UTC）
    """
    record: Optional[Dict[str, Any]] = None
    for c in auth_config.get_codes():
        if isinstance(c, dict) and c.get("code") == body.code:
            record = c
            break

    if record is None:
        raise _unauthorized("Invalid code")

    expires_at = record.get("expires_at")
    if not isinstance(expires_at, str) or auth_config.is_code_expired(expires_at):
        raise _unauthorized("Code expired")

    roles, groups = auth_config.resolve_effective_roles(record)
    return _issue_token(subject=body.code, login_mode="code", roles=roles, groups=groups)


@router.get("/me")
async def get_me(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
    """
    返回当前 Token 的 claims（如 sub、login_mode、exp、iat、roles、groups）
    """
    return identity

@router.get("/admin/ping")
async def admin_ping(identity: Dict[str, Any] = Depends(require_roles(["admin"]))):
    """
    管理员测试端点：需要 admin 角色
    """
    return {"ok": True, "sub": identity.get("sub")}

@router.get("/debug/config")
async def debug_config():
    """
    调试端点：返回当前的认证配置
    """
    return {
        "users": auth_config.get_users(),
        "codes": auth_config.get_codes(),
        "jwt_secret": auth_config.get_jwt_secret(),
        "jwt_expires_seconds": auth_config.get_jwt_expires_seconds()
    }