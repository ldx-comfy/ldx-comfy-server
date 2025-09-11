"""
權限驗證中間件
提供基於路由的權限檢查功能
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Any, Callable, Awaitable, List, Optional
import logging
from auth.permissions import get_current_identity # 這裡保留這個導入，只用於解析 JWT
import auth.config as auth_config
import global_data
import re

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # 統一後端路由的權限映射表 (更精確的模式匹配)
        self.route_permissions_map = {
            # 用戶管理
            re.compile(r"^/api/v1/admin/users/?$"): {"GET": ["admin:users:read"], "POST": ["admin:users:manage"]},
            re.compile(r"^/api/v1/admin/users/[^/]+/role/?$"): {"PUT": ["admin:users:manage"]},
            re.compile(r"^/api/v1/admin/users/[^/]+/status/?$"): {"PUT": ["admin:users:manage"]},
            re.compile(r"^/api/v1/admin/users/[^/]+/groups/?$"): {"PUT": ["admin:users:manage"]},
            re.compile(r"^/api/v1/admin/users/[^/]+/reset-password/?$"): {"PUT": ["admin:users:manage"]},
            re.compile(r"^/api/v1/admin/users/[^/]+/?$"): {"DELETE": ["admin:users:manage"]}, # 刪除用戶

            # 身分組管理
            re.compile(r"^/api/v1/admin/groups/?$"): {"GET": ["admin:groups:read"], "POST": ["admin:groups:manage"]},
            re.compile(r"^/api/v1/admin/groups/[^/]+/?$"): {"GET": ["admin:groups:read"], "PUT": ["admin:groups:manage"], "DELETE": ["admin:groups:manage"]},
            re.compile(r"^/api/v1/admin/groups/permissions/list/?$"): {"GET": ["admin:groups:read"]},
            re.compile(r"^/api/v1/admin/groups/my/permissions/?$"): {"GET": []}, # 用戶獲取自己的權限，只需要身份驗證，不需要特定 admin 權限

            # 工作流管理 (Admin 視圖)
            re.compile(r"^/api/v1/forms/admin/history/?$"): {"GET": ["admin:history:read"]},
            re.compile(r"^/api/v1/forms/admin/history/[^/]+/?$"): {"GET": ["admin:history:read"]},
            re.compile(r"^/api/v1/forms/workflows/upload/?$"): {"POST": ["admin:workflows:manage"]},
            re.compile(r"^/api/v1/forms/workflows/[^/]+/?$"): {"DELETE": ["admin:workflows:manage"]}, # 刪除工作流

            # 授權碼管理
            re.compile(r"^/api/v1/auth/admin/codes/?$"): {"GET": ["admin:codes:read"], "POST": ["admin:codes:manage"]},
            re.compile(r"^/api/v1/auth/admin/codes/[^/]+/?$"): {"DELETE": ["admin:codes:manage"]},

            # 普通用戶功能 (需要身份驗證)
            re.compile(r"^/api/v1/forms/workflows/?$"): {"GET": ["workflow:read:*"]},
            re.compile(r"^/api/v1/forms/user/workflows/?$"): {"GET" : ["workflow:read:*"]},
            re.compile(r"^/api/v1/forms/workflows/[^/]+/form-schema/?$"): {"GET": ["workflow:read:*"]},
            re.compile(r"^/api/v1/forms/workflows/[^/]+/execute/?$"): {"POST": ["workflow:execute:*"]},
            re.compile(r"^/api/v1/forms/user/history/?$"): {"GET": ["history:read:self"]},
            re.compile(r"^/api/v1/forms/user/history/[^/]+/?$"): {"GET": ["history:read:self"]},
            re.compile(r"^/api/v1/auth/me/reset-password/?$"): {"PUT": ["user:reset_password:self"]},

            # 公開路由 (不需要任何認證)
            re.compile(r"^/api/v1/auth/login/?$"): {},
            re.compile(r"^/api/v1/auth/code/?$"): {},
            re.compile(r"^/api/v1/auth/me/?$"): {}, # 獲取自身信息，由 get_current_identity 處理 (即使沒有 token 也不會 401)
            re.compile(r"^/api/v1/health.*$"): {},
            re.compile(r"^/api/v1/admin/ping/?$"): {"GET": ["admin:access"]}, # 管理員 ping 應該是 admin:access
        }

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]):
        path = request.url.path
        method = request.method

        logger.debug(f"AuthMiddleware: 收到請求: {method} {path}")

        identity: Optional[Dict[str, Any]] = None
        authorization = request.headers.get("Authorization")
        if authorization:
            try:
                # 使用 get_current_identity 嘗試解析 JWT
                identity = get_current_identity(authorization)
                request.state.identity = identity # 將身份信息存在 request.state 以便後續路由或依賴使用
                logger.debug(f"AuthMiddleware: 用戶身份已加載: {identity.get('sub', 'unknown')}")
            except HTTPException as e:
                # 即使身份驗證失敗 (例如無效令牌)，也記錄並允許請求繼續，
                # 讓需要身份或權限的路由自行返回 401/403
                logger.debug(f"AuthMiddleware: 身份令牌無效, 錯誤: {e.detail}")
            except Exception as e:
                logger.warning(f"AuthMiddleware: 身份解析出錯: {str(e)}")

        required_permissions = self._get_required_permissions_for_route(path, method)

        if required_permissions is not None:
            if required_permissions: # 如果有明確的權限要求 (列表非空)
                if not identity:
                    logger.warning(f"AuthMiddleware: 路由 {method} {path} 需要身份驗證，但未提供")
                    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "需要身份驗證"})
                
                # 檢查用戶是否具有所需權限
                if not self._check_user_has_permissions(identity, required_permissions):
                    logger.warning(f"AuthMiddleware: 用戶 {identity.get('sub', 'unknown')} 權限不足以訪問 {method} {path}")
                    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "權限不足"})
                logger.debug(f"AuthMiddleware: 用戶 {identity.get('sub', 'unknown')} 通過權限檢查以訪問 {method} {path}")
            else: # required_permissions 為空列表，表示需要身份驗證但無特定權限
                if not identity:
                    logger.warning(f"AuthMiddleware: 路由 {method} {path} 需要身份驗證，但未提供")
                    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "需要身份驗證"})
                logger.debug(f"AuthMiddleware: 路由 {method} {path} 需要身份驗證 (無特定權限)，用戶已通過")
        else:
            # 路由未在映射中定義，視為公共可訪問 (不進行認證/授權檢查)
            logger.debug(f"AuthMiddleware: 路由 {method} {path} 未在權限映射中定義，視為公共路由 (跳過身份/權限檢查)")

        response = await call_next(request)
        return response

    def _get_required_permissions_for_route(self, path: str, method: str) -> Optional[List[str]]:
        """
        根據路徑和方法獲取此路由所需的權限列表。
        返回 None 表示路由未在 map 中定義。
        返回空列表 [] 表示路由需要身份驗證但不需要特定權限 (例如某些用戶個人信息接口)。
        """
        for pattern, method_perms in self.route_permissions_map.items():
            if pattern.fullmatch(path):
                return method_perms.get(method)
        return None # 未在 map 中找到匹配的路由

    def _check_user_has_permissions(self, identity: Dict[str, Any], required_permissions: List[str]) -> bool:
        """
        檢查用戶是否具有所需權限。
        支持通配符權限 (例如，如果 required 是 workflow:read:*, 用戶有 workflow:read:specific)
        """
        # 檢查用戶是否是admin，如果是admin直接通過所有權限檢查
        username = identity.get("sub", "")
        if username == "admin":
            return True

        user_permissions = identity.get("permissions", []) # JWT 中應該已經包含了所有處理後的細粒度權限
        if not isinstance(user_permissions, list):
            user_permissions = []
        user_permissions_set = set(user_permissions)

        if not required_permissions: # 如果 required_permissions 為空列表，表示只需要身份驗證，不需要特定權限
            return True

        #檢查是否含有任一權限
        any_permission_satisfied = False
        for req_perm in required_permissions:
            # 直接匹配 (例如，required: admin:users:read, user_permissions: {"admin:users:read"})
            if req_perm in user_permissions_set:
                any_permission_satisfied = True
                break

            # 檢查用戶是否擁有通配符權限 "*" (最高權限)
            if "*" in user_permissions_set:
                any_permission_satisfied = True
                break

            # 通配符匹配 (例如，required: admin:users:read, user_permissions: {"admin:users:*"})
            for user_perm_with_wildcard in user_permissions_set:
                if user_perm_with_wildcard.endswith(":*"):
                    wildcard_prefix = user_perm_with_wildcard[:-2] + ":"
                    if req_perm.startswith(wildcard_prefix):
                        any_permission_satisfied = True
                        break
            if any_permission_satisfied:
                break

        return any_permission_satisfied