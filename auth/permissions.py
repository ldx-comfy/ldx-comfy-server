"""
權限檢查工具
提供基於身分組的權限檢查功能
"""

from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, status, Header
from typing import Any, Dict, List, Optional
from fastapi import Depends, HTTPException, status, Header
from auth import config as auth_config
from auth import jwt as jwt_lib
import global_data
import logging

logger = logging.getLogger(__name__)

def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


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


def get_current_identity(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    從 Authorization: Bearer <token> 解析並驗證 JWT，返回 claims。
    校驗失敗一律 401。
    """
    token = _extract_bearer_token(authorization)
    secret = auth_config.get_jwt_secret()
    try:
        claims = jwt_lib.decode(token, secret)
        # 簡單校驗必要字段
        if "sub" not in claims or "exp" not in claims:
            raise ValueError("Invalid claims")
        return claims
    except Exception as e: # 捕獲更廣泛的異常以記錄
        logger.warning(f"get_current_identity: JWT 解碼失敗，錯誤類型: {type(e).__name__}, 內容: {e}") # 更詳細的日誌
        raise _unauthorized(str(e)) # 重新拋出 401 異常帶有通用信息


def require_permissions(required: List[str], match: str = "any"):
    """
    依賴：校驗 JWT claims 中的 permissions。
    - required: 需要的權限列表
    - match: "any"（任一即可）或 "all"（全部滿足）
    校驗失敗返回 403。
    """
    def _dep(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
        # 檢查用戶是否是admin，如果是admin直接通過所有權限檢查
        username = identity.get("sub", "")
        if username == "admin":
            return identity

        # 從 global_data 獲取最新的身分組配置和用戶信息
        groups_config = global_data.AUTH_CONFIG.get("groups", {})
        users_config = global_data.AUTH_CONFIG.get("users", [])
        
        # 根據用戶名獲取最新的用戶信息
        current_user = None
        for user in users_config:
            if isinstance(user, dict) and user.get("username") == username:
                current_user = user
                break

        # 獲取用戶的身分組（優先使用最新的配置，回退到 JWT token 中的信息）
        user_groups = []
        if current_user and isinstance(current_user.get("groups"), list):
            user_groups = current_user["groups"]
        else:
            user_groups = identity.get("groups", [])
        if not isinstance(user_groups, list):
            user_groups = []

        # 收集用戶所有權限
        user_permissions = set()

        # 從身分組獲取權限
        for group_id in user_groups:
            group_data = groups_config.get(group_id, {})
            if isinstance(group_data, dict) and "permissions" in group_data:
                for perm in group_data["permissions"]:
                    user_permissions.add(perm)

        # 從用戶直接權限字段獲取權限
        if current_user and isinstance(current_user.get("permissions"), list):
            for perm in current_user["permissions"]:
                user_permissions.add(perm)
        else:
            # 回退到 JWT token 中的權限信息
            direct_permissions = identity.get("permissions", [])
            if isinstance(direct_permissions, list):
                for perm in direct_permissions:
                    user_permissions.add(perm)

        # 動態解析用戶角色（基於最新的群組配置）
        user_roles = set()
        if current_user and isinstance(current_user.get("roles"), list):
            user_roles.update(current_user["roles"])
        else:
            # 回退到 JWT token 中的角色信息
            token_roles = identity.get("roles", [])
            if isinstance(token_roles, list):
                user_roles.update(token_roles)
        
        # 檢查用戶所屬的群組是否具有管理員級別的權限
        admin_groups = []
        admin_permission_patterns = ["admin:"]
        for group_id in user_groups:
            group_data = groups_config.get(group_id, {})
            if isinstance(group_data, dict):
                permissions = group_data.get("permissions", [])
                has_admin_level_permissions = False
                for perm in permissions:
                    if isinstance(perm, str):
                        for pattern in admin_permission_patterns:
                            if pattern.endswith(":") and perm.startswith(pattern):
                                has_admin_level_permissions = True
                                break
                            elif pattern.endswith(":*") and perm.startswith(pattern[:-1]):
                                has_admin_level_permissions = True
                                break
                            elif perm == pattern:
                                has_admin_level_permissions = True
                                break
                        if has_admin_level_permissions:
                            break
                if has_admin_level_permissions:
                    admin_groups.append(group_id)
        
        # 如果用戶所屬的群組具有管理員級別的權限，則添加 "admin" 角色
        if admin_groups and "admin" not in user_roles:
            user_roles.add("admin")

        # 驗證權限
        def _check_permission(req_perm: str) -> bool:
            # 直接匹配
            if req_perm in user_permissions:
                return True

            # 檢查用戶是否擁有通配符權限 "*" (最高權限)
            if "*" in user_permissions:
                return True

            # 通配符匹配 (例如: user:*)
            if req_perm.endswith(":*"):
                prefix = req_perm[:-2]  # 移除 ":*"
                for perm in user_permissions:
                    if perm.startswith(prefix + ":") and len(perm) > len(prefix) + 1: # 確保通配符匹配不是自身
                        return True

            return False

        req = [r for r in (required or []) if isinstance(r, str)]
        if not req:
            ok = True
        elif match == "all":
            ok = all(_check_permission(r) for r in req)
        else:
            ok = any(_check_permission(r) for r in req)

        if not ok:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return identity
    return _dep