"""
鉴权路由与工具
- 提供两种登录方式：用户名+密码、授权码
- 返回 JWT Bearer Token（HS256，标准库实现），exp 自包含
- 不引入新的三方依赖
"""

from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field

from auth import jwt as jwt_lib
from auth import config as auth_config
from auth import permissions as auth_permissions

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/auth", tags=["鉴权"])


# ============================
# 模型定义
# ============================

class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="明文密码（来自 JSON 配置，不做管理端）")


class CodeRequest(BaseModel):
    code: str = Field(..., description="授权码")


class ResetOwnPasswordRequest(BaseModel):
    """重置自己密码请求"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., description="新密码")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CreateCodeRequest(BaseModel):
    """创建授权码请求"""
    name: Optional[str] = Field(None, description="授权码名称")
    code: Optional[str] = Field(None, description="授权码")
    expires_in_seconds: Optional[int] = Field(3600, description="授权码有效秒数")
    roles: Optional[List[str]] = Field(None, description="授权码附带角色")
    groups: Optional[List[str]] = Field(None, description="授权码附带身分組")
    permissions: Optional[List[str]] = Field(None, description="授权码附带权限")


class CodeInfo(BaseModel):
    """授权码信息"""
    code: str = Field(..., description="授权码")
    expires_at: str = Field(..., description="过期时间 (ISO-8601)")
    roles: List[str] = Field(default_factory=list, description="授权码附带角色")
    groups: List[str] = Field(default_factory=list, description="授权码附带身分組")
    permissions: List[str] = Field(default_factory=list, description="授权码附带权限")


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
    permissions: Optional[List[str]] = None,
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
        "permissions": list(permissions or []),
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
    用户名+密码登录（SHA256哈希验证）
    支持 password_hash 字段的哈希密码验证
    """
    user = auth_config.find_user(body.username)
    if not user or not isinstance(user, dict):
        raise _unauthorized("Invalid credentials")

    # 优先检查哈希密码字段
    stored_hash = user.get("password_hash")
    if stored_hash:
        if not auth_config.verify_password(body.password, stored_hash):
            raise _unauthorized("Invalid credentials")
    else:
        # 向后兼容：检查明文密码字段
        stored_password = user.get("password")
        if stored_password is None or stored_password != body.password:
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

    effective_roles, effective_groups = auth_config.resolve_effective_roles(record)
    permissions = record.get("permissions", []) # 从 record 中获取 permissions

    return _issue_token(
        subject=body.code,
        login_mode="code",
        roles=effective_roles,
        groups=effective_groups,
        permissions=permissions # 传递 permissions
    )


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

@router.put("/me/reset-password")
async def reset_own_password(
    request: ResetOwnPasswordRequest,
    identity: Dict[str, Any] = Depends(get_current_identity)
):
    """重置自己的密码"""
    current_username = identity.get("sub")
    logger.info(f"用户 {current_username} 重置自己的密码 (Kilo Code diagnostic check)")
    try:
        # 验证新密码必须提供且长度>=6
        if not request.new_password or len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="新密码长度至少为6位")
        new_pw = request.new_password

        # 获取当前用户
        if not current_username:
            raise HTTPException(status_code=400, detail="无法识别当前用户")

        # 验证用户名是否有效（防止使用无效的JWT token）
        if not isinstance(current_username, str) or len(current_username.strip()) == 0:
            raise HTTPException(status_code=400, detail="无效的用户名")

        config = auth_config._load_json_file(auth_config._effective_config_path())
        if config is None:
            raise HTTPException(status_code=500, detail="加载认证配置失败")

        # 在本模块内查找当前用户在配置中的索引，避免访问不存在的私有成员
        users_list = config.get("users", [])
        if not isinstance(users_list, list):
            users_list = []
        user_index = next(
            (i for i, u in enumerate(users_list)
             if isinstance(u, dict) and u.get("username") == current_username),
            -1
        )

        if user_index == -1:
            logger.warning(f"JWT token 包含不存在的用户名: {current_username}")
            raise HTTPException(status_code=401, detail="认证令牌无效，请重新登录")

        user = config["users"][user_index]

        # 验证当前密码（兼容明文与哈希）
        current_password_hash = user.get("password_hash")
        if not current_password_hash:
            # 向后兼容：检查明文密码字段
            current_password_plain = user.get("password")
            if current_password_plain is None or current_password_plain != request.current_password:
                raise HTTPException(status_code=400, detail="当前密码不正确")
        else:
            if not auth_config.verify_password(request.current_password, current_password_hash):
                raise HTTPException(status_code=400, detail="当前密码不正确")

        # 更新密码
        user["password_hash"] = auth_config.hash_password(new_pw)
    
        auth_config._save_auth_config(config)
    
        logger.info(f"用户 {current_username} 密码重置成功")
        return {"message": "密码已重置"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置自己密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置自己密码失败: {str(e)}")




@router.get("/admin/codes", response_model=List[CodeInfo])
async def get_all_codes(
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """
    管理员获取所有授权码列表（仅管理员）
    """
    logger.info("管理员获取所有授权码列表")
    try:
        config = auth_config._load_json_file(auth_config._effective_config_path()) or {}
        codes = config.get("codes", [])
        # 为 CodeInfo 构造函数提供缺失的字段的默认值
        validated_codes = []
        for c in codes:
            if isinstance(c, dict):
                # 检查并提供默认值
                c.setdefault("roles", [])
                c.setdefault("groups", [])
                c.setdefault("permissions", [])
                validated_codes.append(CodeInfo(**c))
        return validated_codes
    except Exception as e:
        logger.error(f"获取授权码列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取授权码列表失败: {str(e)}")


@router.post("/admin/codes", response_model=CodeInfo)
async def create_new_code(
    request: CreateCodeRequest,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """
    管理员创建新的授权码（仅管理员）
    """
    # 如果提供了名称但没有提供授权码，则自动生成授权码
    code_value = request.code
    if request.name and not code_value:
        # 生成随机授权码
        code_value = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    elif not code_value:
        raise HTTPException(status_code=400, detail="授权码或名称必须提供一个")

    logger.info(f"管理员创建新授权码: {code_value}")
    try:
        if not code_value or not code_value.strip():
            raise HTTPException(status_code=400, detail="授权码不能为空")

        # 检查授权码是否已存在
        current_codes = auth_config.get_codes()
        for c in current_codes:
            if isinstance(c, dict) and c.get("code") == code_value:
                raise HTTPException(status_code=400, detail=f"授权码 '{code_value}' 已存在")

        # 计算过期时间
        expires_at_ts = jwt_lib.now_ts() + (request.expires_in_seconds or 3600)
        expires_at_dt = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc)

        new_code_record = {
            "code": code_value,
            "name": request.name,
            "expires_at": expires_at_dt.isoformat().replace("+00:00", "Z"),
            "roles": request.roles or [],
            "groups": request.groups or [],
            "permissions": request.permissions or [],
        }

        config = auth_config._load_json_file(auth_config._effective_config_path())
        if config is None:
            config = {}
        if "codes" not in config or not isinstance(config["codes"], list):
            config["codes"] = []
        
        config["codes"].append(new_code_record)
        auth_config._save_auth_config(config)

        # 返回新创建的授权码信息
        return CodeInfo(
            code=new_code_record["code"],
            expires_at=new_code_record["expires_at"],
            roles=new_code_record["roles"],
            groups=new_code_record["groups"],
            permissions=new_code_record["permissions"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建授权码失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建授权码失败: {str(e)}")


@router.delete("/admin/codes/{code_value}")
async def delete_code(
    code_value: str,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """
    管理员删除授权码（仅管理员）
    """
    logger.info(f"管理员删除授权码: {code_value}")
    try:
        if not code_value or not code_value.strip():
            raise HTTPException(status_code=400, detail="授权码不能为空")

        config = auth_config._load_json_file(auth_config._effective_config_path())
        if config is None:
            raise HTTPException(status_code=500, detail="加载认证配置失败")
        
        codes = config.get("codes", [])
        code_index = -1
        for i, c in enumerate(codes):
            if isinstance(c, dict) and c.get("code") == code_value:
                code_index = i
                break
        
        if code_index == -1:
            raise HTTPException(status_code=404, detail=f"授权码 '{code_value}' 不存在")
        
        codes.pop(code_index)
        config["codes"] = codes
        auth_config._save_auth_config(config)

        logger.info(f"授权码 {code_value} 删除成功")
        return {"message": f"授权码 '{code_value}' 已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除授权码失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除授权码失败: {str(e)}")


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