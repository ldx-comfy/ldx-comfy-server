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
from auth.permissions import get_current_identity, require_permissions # 更改導入
import global_data # 導入 global_data 以訪問 AUTH_CONFIG (用於 _issue_token)

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
# 內部工具
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
    # 這裡的 roles 和 groups 仍然保留，因為它們來自用戶或碼的原始配置，
    # 最終權限會由 auth_config.resolve_effective_roles 處理
    roles: Optional[List[str]] = None,
    groups: Optional[List[str]] = None,
    # 允許直接傳遞 permissions，主要用於 code_login，確保其原始綁定權限得到尊重
    permissions: Optional[List[str]] = None, 
) -> TokenResponse:
    iat = jwt_lib.now_ts()
    expires_in = int(auth_config.get_jwt_expires_seconds())

    # 從 auth_config.resolve_effective_roles 獲取解析後的所有信息
    # resolve_effective_roles 現在返回 (roles, groups, permissions)
    effective_roles, effective_groups, resolved_permissions = auth_config.resolve_effective_roles({"username": subject, "roles": roles, "groups": groups})
    
    # 如果 _issue_token 接收到了額外的 permissions 參數 (例如來自授權碼的直接權限)，
    # 則將它們合并到 resolved_permissions 中
    if permissions:
        # 將 resolved_permissions 轉為 set 以便合併和去重
        merged_permissions_set = set(resolved_permissions)
        merged_permissions_set.update(permissions)
        resolved_permissions = list(merged_permissions_set) # 轉換回列表

    payload: Dict[str, Any] = {
        "sub": subject,
        "login_mode": login_mode,
        "iat": iat,
        "exp": iat + expires_in,
        "roles": list(effective_roles), # 發給 JWT 的是解析後的 effective_roles
        "groups": list(effective_groups), # 發給 JWT 的是解析後的 effective_groups
        "permissions": list(resolved_permissions), # 現在直接使用 resolve_effective_roles 返回的所有權限
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


# get_current_identity 應從 auth.permissions 導入
# 因此這裡的定義可以移除，使用從 auth.permissions 導入的版本

# ============================
# 已移除舊的 require_roles 和 require_groups 依賴
# 現在使用 auth.permissions.require_permissions
# ============================


# ============================
# 路由
# ============================

@router.post("/login", response_model=TokenResponse)
async def password_login(body: LoginRequest) -> TokenResponse:
    """
    用戶名+密碼登錄（SHA256哈希驗證）
    支持 password_hash 字段的哈希密碼驗證
    """
    logger.info(f"用戶 {body.username} 嘗試登錄")
    user = auth_config.find_user(body.username)
    if not user: # user 為 None 表示未找到
        logger.warning(f"用戶 {body.username} 不存在")
        raise _unauthorized("Invalid credentials")

    logger.debug(f"找到用戶: {user.get('username')}")
    logger.debug(f"用戶狀態: {user.get('status')}")

    # 檢查用戶狀態
    if user.get("status") != "active":
        logger.warning(f"用戶 {body.username} 狀態為 {user.get('status')}，拒絕登錄")
        raise _unauthorized("Account is not active")

    # 優先檢查哈希密碼字段
    stored_hash = user.get("password_hash")
    if stored_hash:
        logger.debug(f"驗證哈希密碼: 存儲的哈希={stored_hash}")
        logger.debug(f"輸入密碼哈希: {auth_config.hash_password(body.password)}")
        if not auth_config.verify_password(body.password, stored_hash):
            logger.warning(f"用戶 {body.username} 密碼驗證失敗")
            raise _unauthorized("Invalid credentials")
        logger.debug(f"用戶 {body.username} 密碼驗證成功")
    else:
        # 向後兼容：檢查明文密碼字段
        stored_password = user.get("password")
        if stored_password is None or stored_password != body.password:
            logger.warning(f"用戶 {body.username} 明文密碼驗證失敗")
            raise _unauthorized("Invalid credentials")
        logger.debug(f"用戶 {body.username} 明文密碼驗證成功")

    roles, groups, permissions_from_config = auth_config.resolve_effective_roles(user) # 獲取 permissions
    logger.info(f"用戶 {body.username} 登錄成功，權限: {permissions_from_config}")
    return _issue_token(subject=body.username, login_mode="password", roles=roles, groups=groups, permissions=permissions_from_config)


@router.post("/code", response_model=TokenResponse)
async def code_login(body: CodeRequest) -> TokenResponse:
    """
    授權碼登錄：在配置 codes 中存在且未過期（僅校驗 expires_at）。
    expires_at: ISO-8601（支持 Z/偏移/本地時間，推薦 UTC）
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

    # 授權碼的權限可以從其自身的 permissions 字段獲取，也可以從其綁定的 groups 解析
    # _issue_token 會在內部處理合併
    code_specific_permissions = record.get("permissions", []) 
    # 也解析授權碼綁定的 groups，以獲取額外的權限
    effective_roles, effective_groups, resolved_permissions_from_groups = auth_config.resolve_effective_roles(record)

    return _issue_token(
        subject=body.code,
        login_mode="code",
        roles=effective_roles,
        groups=effective_groups,
        permissions=resolved_permissions_from_groups + code_specific_permissions # 將兩部分權限合併傳遞
    )


@router.get("/me")
async def get_me(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
    """
    返回當前 Token 的 claims（如 sub、login_mode、exp、iat、roles、groups、permissions）
    """
    return identity

@router.get("/admin/ping")
async def admin_ping(identity: Dict[str, Any] = Depends(require_permissions(["admin:access"]))): # 使用細粒度權限
    """
    管理員測試端點：需要 admin:access 權限
    """
    return {"ok": True, "sub": identity.get("sub")}

@router.put("/me/reset-password")
@router.put("/me/reset-password/") # 新增帶斜線的路由，以便同時匹配兩種形式
async def reset_own_password(
    request: ResetOwnPasswordRequest,
    identity: Dict[str, Any] = Depends(get_current_identity)
):
    """重置自己的密碼"""
    current_username = identity.get("sub")
    logger.info(f"用戶 {current_username} 重置自己的密碼")
    try:
        # 驗證新密碼必須提供且長度>=6
        if not request.new_password or len(request.new_password) < 6:
            logger.warning(f"用戶 {current_username} 新密碼長度不足: {len(request.new_password or '')}")
            raise HTTPException(status_code=400, detail="新密碼長度至少為6位")
        new_pw = request.new_password
        logger.debug(f"用戶 {current_username} 新密碼長度驗證通過")

        # 獲取當前用戶
        if not current_username:
            logger.warning("無法從JWT token中獲取用戶名")
            raise HTTPException(status_code=400, detail="無法識別當前用戶")

        # 驗證用戶名是否有效（防止使用無效的JWT token）
        if not isinstance(current_username, str) or len(current_username.strip()) == 0:
            logger.warning(f"無效的用戶名: {current_username}")
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = global_data.AUTH_CONFIG # 直接從全局配置獲取
        users_list = config.get("users", [])
        if not isinstance(users_list, list):
            users_list = []
        logger.debug(f"找到 {len(users_list)} 個用戶")

        user_index = next(
            (i for i, u in enumerate(users_list)
             if isinstance(u, dict) and u.get("username") == current_username),
            -1
        )

        if user_index == -1:
            logger.warning(f"JWT token 包含不存在的用戶名: {current_username}")
            raise HTTPException(status_code=401, detail="認證令牌無效，請重新登錄")

        user = config["users"][user_index]
        logger.debug(f"找到用戶: {user.get('username')}")

        # 驗證當前密碼（兼容明文與哈希）
        current_password_hash = user.get("password_hash")
        if not current_password_hash:
            # 向後兼容：檢查明文密碼字段
            current_password_plain = user.get("password")
            if current_password_plain is None or current_password_plain != request.current_password:
                logger.warning(f"用戶 {current_username} 明文密碼驗證失敗")
                raise HTTPException(status_code=400, detail="當前密碼不正確")
            logger.debug(f"用戶 {current_username} 明文密碼驗證成功")
        else:
            logger.debug(f"用戶 {current_username} 存儲的哈希: {current_password_hash}")
            logger.debug(f"用戶 {current_username} 輸入密碼哈希: {auth_config.hash_password(request.current_password)}")
            if not auth_config.verify_password(request.current_password, current_password_hash):
                logger.warning(f"用戶 {current_username} 哈希密碼驗證失敗")
                raise HTTPException(status_code=400, detail="當前密碼不正確")
            logger.debug(f"用戶 {current_username} 哈希密碼驗證成功")

        # 更新密碼
        old_hash = user["password_hash"]
        user["password_hash"] = auth_config.hash_password(new_pw)
        logger.debug(f"用戶 {current_username} 密碼哈希已更新: {old_hash} -> {user['password_hash']}")

        auth_config._save_auth_config(config) # 保存整個配置
        logger.info(f"用戶 {current_username} 密碼重置成功，已保存到配置文件")

        return {"message": "密碼已重置"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置自己密碼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"重置自己密碼失敗: {str(e)}")


@router.get("/admin/codes", response_model=List[CodeInfo])
async def get_all_codes(
    identity: Dict[str, Any] = Depends(require_permissions(["admin:codes:read"])) # 使用細粒度權限
):
    """
    管理員獲取所有授權碼列表（僅管理員）
    """
    logger.info("管理員獲取所有授權碼列表")
    try:
        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取
        codes = config.get("codes", [])
        
        validated_codes = []
        for c in codes:
            if isinstance(c, dict):
                c.setdefault("roles", [])
                c.setdefault("groups", [])
                c.setdefault("permissions", [])
                validated_codes.append(CodeInfo(**c))
        return validated_codes
    except Exception as e:
        logger.error(f"獲取授權碼列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取授權碼列表失敗: {str(e)}")


@router.post("/admin/codes", response_model=CodeInfo)
async def create_new_code(
    request: CreateCodeRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:codes:manage"])) # 使用細粒度權限
):
    """
    管理員創建新的授權碼（僅管理員）
    """
    code_value = request.code
    if request.name and not code_value:
        code_value = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    elif not code_value:
        raise HTTPException(status_code=400, detail="授權碼或名稱必須提供一個")

    logger.info(f"管理員創建新授權碼: {code_value}")
    try:
        if not code_value or not code_value.strip():
            raise HTTPException(status_code=400, detail="授權碼不能為空")

        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取
        codes = config.get("codes", [])

        for c in codes:
            if isinstance(c, dict) and c.get("code") == code_value:
                raise HTTPException(status_code=400, detail=f"授權碼 '{code_value}' 已存在")

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
        
        codes.append(new_code_record)
        config["codes"] = codes
        auth_config._save_auth_config(config) # 保存整個配置

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
        logger.error(f"創建授權碼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"創建授權碼失敗: {str(e)}")


@router.delete("/admin/codes/{code_value}")
async def delete_code(
    code_value: str,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:codes:manage"])) # 使用細粒度權限
):
    """
    管理員刪除授權碼（僅管理員）
    """
    logger.info(f"管理員刪除授權碼: {code_value}")
    try:
        if not code_value or not code_value.strip():
            raise HTTPException(status_code=400, detail="授權碼不能為空")

        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取
        codes = config.get("codes", [])
        code_index = -1
        for i, c in enumerate(codes):
            if isinstance(c, dict) and c.get("code") == code_value:
                code_index = i
                break
        
        if code_index == -1:
            raise HTTPException(status_code=404, detail=f"授權碼 '{code_value}' 不存在")
        
        codes.pop(code_index)
        config["codes"] = codes
        auth_config._save_auth_config(config) # 保存整個配置

        logger.info(f"授權碼 {code_value} 刪除成功")
        return {"message": f"授權碼 '{code_value}' 已刪除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除授權碼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除授權碼失敗: {str(e)}")


@router.get("/debug/config")
async def debug_config():
    """
    調試端點：返回當前的認證配置快照 (去敏感信息)
    """
    return auth_config.get_effective_config_snapshot() # 使用新的快照函數