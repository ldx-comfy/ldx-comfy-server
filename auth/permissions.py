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
    except ValueError as e:
        raise _unauthorized(str(e))


def require_permissions(required: List[str], match: str = "any"):
    """
    依賴：校驗 JWT claims 中的 permissions。
    - required: 需要的權限列表
    - match: "any"（任一即可）或 "all"（全部滿足）
    校驗失敗返回 403。
    """
    def _dep(identity: Dict[str, Any] = Depends(get_current_identity)) -> Dict[str, Any]:
        # 從 global_data 獲取身分組配置
        groups_config = global_data.AUTH_CONFIG.get("groups", {})
        
        # 獲取用戶的身分組
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
        
        # 從直接角色獲取權限（如果角色也代表權限，此處可保留）
        # 在新的權限模型中，建議將所有細粒度權限都定義在 groups 中，
        # roles 僅作為用戶的頂層標識，不再直接作為權限。
        # 如果需要，可以將 roles 映射到 permissions。
        user_roles = identity.get("roles", [])
        if isinstance(user_roles, list):
            for role in user_roles:
                user_permissions.add(role) # 可以考慮移除此行，如果 roles 不直接是 permissions
        
        # 驗證權限
        def _check_permission(req_perm: str) -> bool:
            # 直接匹配
            if req_perm in user_permissions:
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