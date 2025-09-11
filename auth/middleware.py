"""
權限驗證中間件
提供基於路由的權限檢查功能
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Dict, Any, Callable, Awaitable
import logging
from auth.permissions import get_current_identity
from auth.config import _load_json_file
import auth.config as auth_config
import global_data
import json

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # 定義需要權限驗證的路由模式
        self.protected_routes = {
            "/api/v1/forms/workflows": ["user:read"],
            "/api/v1/forms/user/workflows": ["user:read"],
            "/api/v1/forms/workflows/[^/]+/form-schema": ["user:read"],
            "/api/v1/forms/workflows/[^/]+/execute": ["user:execute"],
            # 可以根據需要添加更多路由
        }
        
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Any]]):
        # 檢查是否需要權限驗證
        if self._is_protected_route(request):
            logger.info(f"路由 {request.url.path} 需要權限驗證")
            try:
                # 驗證身份
                identity = await self._verify_identity(request)
                logger.info(f"用戶身份驗證成功: {identity.get('sub', 'unknown')}")
                # 檢查權限
                if not await self._check_permissions(request, identity):
                    logger.warning(f"用戶 {identity.get('sub', 'unknown')} 權限不足")
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": "權限不足"}
                    )
            except HTTPException as e:
                logger.warning(f"HTTP異常: {e.status_code} - {e.detail}")
                return JSONResponse(
                    status_code=e.status_code,
                    content={"detail": e.detail}
                )
            except Exception as e:
                logger.error(f"權限驗證錯誤: {str(e)}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"detail": "內部服務器錯誤"}
                )
        else:
            logger.info(f"路由 {request.url.path} 不需要權限驗證")
        
        # 繼續處理請求
        response = await call_next(request)
        return response
    
    def _is_protected_route(self, request: Request) -> bool:
        """檢查是否為受保護的路由"""
        path = request.url.path
        method = request.method
        
        # 保護所有以 /api/v1/admin/ 開頭的路由
        if path.startswith("/api/v1/admin/"):
            return True
            
        # 保護所有以 /api/v1/forms/workflows 開頭的路由
        if path.startswith("/api/v1/forms/workflows"):
            return True
            
        return False
    
    async def _verify_identity(self, request: Request) -> Dict[str, Any]:
        """驗證用戶身份"""
        # 從請求頭中獲取授權信息
        authorization = request.headers.get("Authorization")
        
        # 使用與路由依賴相同的驗證邏輯
        from auth.permissions import get_current_identity
        try:
            identity = get_current_identity(authorization)
            return identity
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"身份驗證錯誤: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="無效的授權信息"
            )
    
    async def _check_permissions(self, request: Request, identity: Dict[str, Any]) -> bool:
        """檢查用戶權限"""
        path = request.url.path
        method = request.method
        logger.info(f"檢查權限: {method} {path}")
        
        # 獲取用戶的權限
        user_permissions = await self._get_user_permissions(identity)
        
        # 檢查路由所需的權限
        required_permissions = self._get_required_permissions(path, method)
        logger.info(f"路由 {method} {path} 所需權限: {required_permissions}")
        
        # 檢查用戶是否具有所需權限
        for perm in required_permissions:
            if not self._has_permission(user_permissions, perm):
                logger.warning(f"用戶缺少權限: {perm}")
                return False
            else:
                logger.info(f"用戶具有權限: {perm}")
                
        logger.info(f"用戶具有訪問 {method} {path} 的所有必要權限")
        return True
    
    async def _get_user_permissions(self, identity: Dict[str, Any]) -> set:
        """獲取用戶權限集合"""
        logger.info(f"獲取用戶權限，身份信息: {identity}")
        
        # 從身分組配置中獲取用戶權限
        try:
            with open(str(global_data.GROUPS_FILE), "r", encoding="utf-8") as f:
                groups_config = json.load(f)
            logger.info("成功加載身分組配置")
        except Exception as e:
            logger.error(f"加載身分組配置失敗: {e}")
            groups_config = {"groups": {}}
        
        # 從認證配置中獲取組映射
        try:
            auth_config_data = _load_json_file(auth_config._effective_config_path())
            groups_map = auth_config_data.get("groups_map", {}) if auth_config_data else {}
            logger.info(f"組映射: {groups_map}")
        except Exception as e:
            logger.error(f"獲取組映射失敗: {e}")
            groups_map = {}
        
        # 獲取用戶的身分組
        user_groups = identity.get("groups", [])
        if not isinstance(user_groups, list):
            user_groups = []
        logger.info(f"用戶的身分組: {user_groups}")
        
        # 獲取用戶的角色
        user_roles = identity.get("roles", [])
        if not isinstance(user_roles, list):
            user_roles = []
        logger.info(f"用戶的角色: {user_roles}")
        
        # 將角色映射到組
        for role in user_roles:
            if role in groups_map:
                mapped_groups = groups_map[role]
                if isinstance(mapped_groups, list):
                    for group in mapped_groups:
                        if group not in user_groups:
                            user_groups.append(group)
        logger.info(f"映射後的用戶身分組: {user_groups}")
        
        # 收集用戶所有權限
        user_permissions = set()
        
        # 從身分組獲取權限
        for group_id in user_groups:
            group_data = groups_config.get("groups", {}).get(group_id, {})
            if isinstance(group_data, dict) and "permissions" in group_data:
                for perm in group_data["permissions"]:
                    user_permissions.add(perm)
        logger.info(f"用戶的權限: {user_permissions}")
                
        return user_permissions
    
    def _get_required_permissions(self, path: str, method: str) -> list:
        """獲取路由所需的權限"""
        # 保護所有以 /api/v1/admin/ 開頭的路由，需要管理員權限
        if path.startswith("/api/v1/admin/"):
            return ["user:*", "group:*", "workflow:*", "history:*"]
        
        # 保護所有以 /api/v1/forms/workflows 開頭的路由
        if path.startswith("/api/v1/forms/workflows"):
            if method in ["POST", "PUT", "DELETE"]:
                return ["workflow:write"]
            else:
                return ["workflow:read"]
        
        return []
    
    def _has_permission(self, user_permissions: set, required_permission: str) -> bool:
        """檢查用戶是否具有指定權限"""
        logger.info(f"檢查用戶是否具有權限: {required_permission}")
        logger.info(f"用戶的權限集合: {user_permissions}")
        
        # 直接匹配
        if required_permission in user_permissions:
            logger.info(f"直接匹配成功: {required_permission}")
            return True
        
        # 通配符匹配 (例如: user:*)
        # 檢查用戶權限中的通配符是否匹配所需權限 (用戶有 workflow:*, 需要 workflow:read)
        for user_perm in user_permissions:
            if user_perm.endswith(":*"):
                prefix = user_perm[:-2]  # 移除 ":*"
                if required_permission.startswith(prefix + ":"):
                    logger.info(f"通配符匹配成功: {user_perm} 匹配 {required_permission}")
                    return True
        
        # 檢查所需權限中的通配符是否匹配用戶權限 (需要 user:*, 用戶有 user:read)
        if required_permission.endswith(":*"):
            prefix = required_permission[:-2]  # 移除 ":*"
            logger.info(f"嘗試通配符匹配，前綴: {prefix}")
            for perm in user_permissions:
                if perm.startswith(prefix + ":"):
                    logger.info(f"通配符匹配成功: {perm}")
                    return True
        
        logger.info(f"權限匹配失敗: {required_permission}")
        return False