"""
用户管理路由
提供管理员用户管理功能
"""

from typing import Dict, Any, List, Optional
import json
import logging
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import config as auth_config
from auth.permissions import get_current_identity, require_permissions # 更改導入
import global_data

router = APIRouter(prefix="/api/v1/admin/users", tags=["用户管理"])


# ============================
# 模型定义
# ============================

class UserInfo(BaseModel):
    """用户信息"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    role: str = Field(..., description="角色")
    groups: List[str] = Field(default_factory=list, description="身分組列表")
    status: str = Field(..., description="状态")
    created_at: str = Field(..., description="创建时间")
    last_login: str = Field(..., description="最后登录时间")
    generation_count: int = Field(..., description="生成次数")


class UpdateUserRoleRequest(BaseModel):
    """更新用户角色请求"""
    role: str = Field(..., description="新角色")


class UpdateUserStatusRequest(BaseModel):
    """更新用户状态请求"""
    status: str = Field(..., description="新状态")


class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
    email: str = Field(..., description="邮箱")
    groups: Optional[List[str]] = Field(None, description="身分組列表")


class ResetPasswordRequest(BaseModel):
    """重置密码请求 (管理员重置他人密码)"""
    new_password: str = Field(..., description="新密码")


class ResetOwnPasswordAdminRequest(BaseModel):
    """重置自己密码请求 (在管理员界面)"""
    current_password: str = Field(..., description="当前密码")
    new_password: str = Field(..., description="新密码")


class UpdateUserGroupsRequest(BaseModel):
    """更新用户身分組请求"""
    groups: List[str] = Field(..., description="身分組列表")


# ============================
# 工具函数
# ============================

# 由於現在全局配置統一管理，這些私有函數可以移除或簡化
# 直接從 global_data.AUTH_CONFIG 獲取配置
def _load_auth_config_from_global() -> Dict[str, Any]:
    """從 global_data 加載認證配置"""
    if not global_data.AUTH_CONFIG:
        global_data.load_auth_config() # 嘗試重新加載
    return global_data.AUTH_CONFIG

def _save_auth_config_to_global(config: Dict[str, Any]) -> None:
    """保存認證配置到 global_data 並持久化"""
    try:
        # 直接更新 global_data 中的 AUTH_CONFIG
        global_data.AUTH_CONFIG.update(config)
        # 調用 auth_config 的保存函數來持久化
        auth_config._save_auth_config(global_data.AUTH_CONFIG)
    except Exception as e:
        logging.error(f"保存認證配置失敗: {e}")
        raise HTTPException(status_code=500, detail="保存認證配置失敗")


def _find_user_index(config: Dict[str, Any], user_id: str) -> int:
    """查找用户在配置中的索引"""
    if not user_id or not isinstance(user_id, str):
        return -1

    users = config.get("users", [])
    if not isinstance(users, list):
        return -1

    for i, user in enumerate(users):
        if isinstance(user, dict):
            username = user.get("username", "")
            if isinstance(username, str) and username == user_id:
                return i
    return -1


def _get_user_role_and_groups(user: Dict[str, Any]) -> tuple[str, List[str]]:
    """获取用户的角色和组"""
    roles, groups, permissions = auth_config.resolve_effective_roles(user)
    # 取第一个角色作为主要角色，如果没有则默认为 'user'
    role = roles[0] if roles else 'user'
    return role, groups


def _is_admin_user(user: Dict[str, Any]) -> bool:
    """檢查用戶是否是管理員"""
    # 檢查用戶名是否為 admin
    if user.get("username") == "admin":
        return True
    
    # 檢查用戶是否擁有 admin:access 權限
    permissions = user.get("permissions", [])
    if isinstance(permissions, list) and "admin:access" in permissions:
        return True
    
    # 檢查用戶是否屬於 admin 身分組
    groups = user.get("groups", [])
    if isinstance(groups, list) and "admin" in groups:
        return True
    
    return False


def _get_user_status(user: Dict[str, Any]) -> str:
    """获取用户状态"""
    return user.get("status", "active")


def _get_user_generation_count(user: Dict[str, Any]) -> int:
    """获取用户生成次数"""
    return user.get("generation_count", 0)


def _get_user_last_login(user: Dict[str, Any]) -> str:
    """获取用户最后登录时间"""
    last_login = user.get("last_login")
    if last_login:
        return last_login
    # 如果没有最后登录时间，返回创建时间或当前时间
    created_at = user.get("created_at")
    if created_at:
        return created_at
    return datetime.now(timezone.utc).isoformat()


def _get_user_created_at(user: Dict[str, Any]) -> str:
    """获取用户创建时间"""
    created_at = user.get("created_at")
    if created_at:
        return created_at
    # 如果没有创建时间，使用当前时间
    return datetime.now(timezone.utc).isoformat()


# ============================
# 路由
# ============================

@router.get("/", response_model=List[UserInfo])
async def get_all_users(identity: Dict[str, Any] = Depends(require_permissions(["admin:users:read"]))):
    """获取所有用户列表（仅管理员）"""
    logging.info("管理员获取所有用户列表")
    try:
        config = _load_auth_config_from_global()
        users = config.get("users", [])

        user_list = []
        for user in users:
            if isinstance(user, dict):
                username = user.get("username", "")
                if not username:
                    continue

                # 跳過admin用戶，不在用戶管理界面中顯示
                if username == "admin":
                    continue

                # 为现有用户添加缺失的字段
                if "id" not in user:
                    user["id"] = username
                if "email" not in user:
                    user["email"] = f"{username}@example.com"
                if "status" not in user:
                    user["status"] = "active"
                if "created_at" not in user:
                    user["created_at"] = datetime.now(timezone.utc).isoformat()
                if "last_login" not in user:
                    user["last_login"] = datetime.now(timezone.utc).isoformat()
                if "generation_count" not in user:
                    user["generation_count"] = 0

                role, groups = _get_user_role_and_groups(user)
                status = _get_user_status(user)
                created_at = _get_user_created_at(user)
                last_login = _get_user_last_login(user)
                generation_count = _get_user_generation_count(user)

                user_info = UserInfo(
                    id=username,
                    username=username,
                    email=user.get("email", f"{username}@example.com"),
                    role=role,
                    groups=groups,
                    status=status,
                    created_at=created_at,
                    last_login=last_login,
                    generation_count=generation_count
                )
                user_list.append(user_info)

        # 保存更新后的配置（添加了缺失的字段）
        _save_auth_config_to_global(config)

        logging.info(f"成功获取 {len(user_list)} 个用户")
        return user_list

    except Exception as e:
        logging.error(f"获取用户列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")
@router.put("/me/reset-password") # 注意：這個路由應該在 /api/v1/users/me/reset-password，而不是 /api/v1/admin/users/me/reset-password

# 移除 `require_roles(["admin"])` 因為這是用戶自己的操作，只需要認證
async def reset_own_password_admin(
    request: ResetOwnPasswordAdminRequest,
    identity: Dict[str, Any] = Depends(get_current_identity) # 只依賴於 get_current_identity
):
    """重置自己密码请求（任何已認證用戶）"""
    current_username = identity.get("sub")
    logging.info(f"用戶 {current_username} 重置自己的密碼")
    try:
        if not request.new_password or len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="新密碼長度至少為6位")
        new_pw = request.new_password

        if not current_username or not isinstance(current_username, str) or len(current_username.strip()) == 0:
            raise HTTPException(status_code=400, detail="無效的用戶名或無法識別當前用戶")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        user_index = -1
        for i, user in enumerate(users):
            if isinstance(user, dict) and user.get("username") == current_username:
                user_index = i
                break

        if user_index == -1:
            logging.warning(f"JWT token 包含不存在的用戶名: {current_username}")
            raise HTTPException(status_code=401, detail="認證令牌無效，請重新登錄")

        user = users[user_index]

        current_password_hash = user.get("password_hash")
        if not current_password_hash:
            # 兼容：檢查明文密碼字段 (如果存在)
            current_password = user.get("password")
            if current_password is None or current_password != request.current_password:
                raise HTTPException(status_code=400, detail="當前密碼不正確")
        else:
            if not auth_config.verify_password(request.current_password, current_password_hash):
                raise HTTPException(status_code=400, detail="當前密碼不正確")

        user["password_hash"] = auth_config.hash_password(new_pw)
        _save_auth_config_to_global(config)

        logging.info(f"用戶 {current_username} 密碼重置成功")
        return {"message": "密碼已重置"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"重置用戶密碼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"重置用戶密碼失敗: {str(e)}")


@router.put("/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """更新用户角色（仅管理员）"""
    logging.info(f"管理員更新用戶 {user_id} 角色為 {request.role}")
    try:
        valid_roles = ["admin", "moderator", "user"]
        if request.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"無效的角色: {request.role}")

        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用戶 {user_id} 不存在")

        user = users[user_index]

        # 防止修改admin帳號
        if _is_admin_user(user):
            raise HTTPException(status_code=400, detail="不能修改admin帳號的權限")

        # 防止管理員給自己降級（避免失去 admin:access 權限）
        current_username = identity.get("sub", "")
        if current_username == user_id and request.role != "admin":
            raise HTTPException(status_code=400, detail="不能修改自己的管理員權限到非管理員角色") # 更精確的錯誤提示

        # 更新內部角色和組（新的模式下，這裡需要明確處理組）
        user["roles"] = [request.role] # 角色只保留一個主角色
        # 根據需要更新 groups 字段。如果角色和組不同步，可能導致問題
        # 在新的權限模型下，建議角色僅作為用戶的標識，真正的權限由 groups 決定
        # 這裡的邏輯需要與 auth_config.resolve_effective_roles 協同工作
        # 為了簡化，如果設置了角色，就清除 groups，讓 resolve_effective_roles 根據角色來推斷或應用默認組
        user.pop("groups", None) # 移除組設置，由 resolve_effective_roles 處理

        _save_auth_config_to_global(config)

        logging.info(f"用戶 {user_id} 角色更新成功")
        return {"message": f"用戶 {user_id} 角色已更新為 {request.role}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新用戶角色失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新用戶角色失敗: {str(e)}")


@router.put("/{user_id}/status")
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """更新用戶狀態（僅管理員）"""
    logging.info(f"管理員更新用戶 {user_id} 狀態為 {request.status}")
    try:
        valid_statuses = ["active", "inactive", "banned"]
        if request.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"無效的狀態: {request.status}")

        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用戶 {user_id} 不存在")

        user = users[user_index]

        current_username = identity.get("sub", "")
        if current_username == user_id and request.status == "banned":
            raise HTTPException(status_code=400, detail="不能禁用自己的賬戶")

        user["status"] = request.status
        _save_auth_config_to_global(config)

        logging.info(f"用戶 {user_id} 狀態更新成功")
        return {"message": f"用戶 {user_id} 狀態已更新為 {request.status}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新用戶狀態失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新用戶狀態失敗: {str(e)}")


@router.post("/", response_model=UserInfo)
async def create_user(
    request: CreateUserRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """創建新用戶（僅管理員）"""
    logging.info(f"管理員創建新用戶: {request.username}")
    try:
        if not request.username or len(request.username.strip()) == 0:
            raise HTTPException(status_code=400, detail="用戶名不能為空")

        if not request.password or len(request.password) < 6:
            raise HTTPException(status_code=400, detail="密碼長度至少為6位")

        config = _load_auth_config_from_global()
        users = config.get("users", [])

        for user in users:
            if isinstance(user, dict) and user.get("username") == request.username:
                raise HTTPException(status_code=400, detail=f"用戶名 '{request.username}' 已存在")

        new_user = {
            "username": request.username,
            "password_hash": auth_config.hash_password(request.password),
            "email": request.email or f"{request.username}@example.com",
            "id": request.username,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat(),
            "generation_count": 0
        }

        if request.groups:
            # 驗證身分組是否存在（從 global_data 獲取）
            groups_config = global_data.AUTH_CONFIG.get("groups", {})
            invalid_groups = [group for group in request.groups if group not in groups_config]
            if invalid_groups:
                raise HTTPException(status_code=400, detail=f"無效的身分組: {invalid_groups}")
            
            new_user["groups"] = request.groups
            new_user.pop("roles", None) # 設置了身分組，移除 roles 字段
        else:
            # 如果沒有提供身分組，則從 default_user_groups 中獲取身分組
            # 如果 default_user_groups 也為空，則不設置身分組
            default_groups = global_data.AUTH_CONFIG.get("default_user_groups", [])
            if default_groups:
                new_user["groups"] = default_groups
            # 不再設置 roles 字段，因為現在主要通過 groups 管理權限

        users.append(new_user)
        config["users"] = users
        _save_auth_config_to_global(config)

        role, groups = _get_user_role_and_groups(new_user)
        user_info = UserInfo(
            id=request.username,
            username=request.username,
            email=new_user["email"],
            role=role,
            groups=groups,
            status=new_user["status"],
            created_at=new_user["created_at"],
            last_login=new_user["last_login"],
            generation_count=new_user["generation_count"]
        )

        logging.info(f"用戶 {request.username} 創建成功")
        return user_info

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"創建用戶失敗: {e}")
        raise HTTPException(status_code=500, detail=f"創建用戶失敗: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """刪除用戶（僅管理員）"""
    current_username = identity.get("sub", "")
    logging.info(f"管理員 {current_username} 嘗試刪除用戶: {user_id}")
    try:
        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            logging.warning(f"無效的用戶名: {user_id}")
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        logging.debug(f"當前用戶列表: {[u.get('username') for u in users if isinstance(u, dict)]}")

        user_index = _find_user_index(config, user_id)
        logging.debug(f"用戶 {user_id} 的索引: {user_index}")

        if user_index == -1:
            logging.warning(f"用戶 {user_id} 不存在")
            raise HTTPException(status_code=404, detail=f"用戶 {user_id} 不存在")

        user = users[user_index]
        logging.debug(f"找到用戶: {user.get('username')}")

        if current_username == user_id:
            logging.warning(f"管理員 {current_username} 嘗試刪除自己的賬戶")
            raise HTTPException(status_code=400, detail="不能刪除自己的賬戶")

        # 防止刪除超級管理員
        if _is_admin_user(user):
            logging.warning(f"嘗試刪除超級管理員賬戶: {user_id}")
            raise HTTPException(status_code=400, detail="不能刪除超級管理員賬戶")

        # 執行刪除
        deleted_user = users.pop(user_index)
        config["users"] = users
        logging.info(f"從內存中移除了用戶 {user_id}")

        # 保存配置
        _save_auth_config_to_global(config)
        logging.info(f"用戶 {user_id} 刪除成功，已保存到配置文件")

        # 驗證刪除是否成功
        updated_config = _load_auth_config_from_global()
        updated_users = updated_config.get("users", [])
        remaining_usernames = [u.get('username') for u in updated_users if isinstance(u, dict)]
        if user_id in remaining_usernames:
            logging.error(f"用戶 {user_id} 刪除失敗，用戶仍然存在")
            raise HTTPException(status_code=500, detail="刪除用戶失敗，用戶仍然存在")
        else:
            logging.info(f"驗證成功：用戶 {user_id} 已從配置文件中移除")

        return {"message": f"用戶 {user_id} 已刪除"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"刪除用戶失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除用戶失敗: {str(e)}")


@router.put("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    request: ResetPasswordRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """重置用户密码（仅管理员）"""
    logging.info(f"管理員重置用戶 {user_id} 密碼")
    try:
        if not request.new_password or len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="密碼長度至少為6位")

        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用戶 {user_id} 不存在")

        user = users[user_index]

        user["password_hash"] = auth_config.hash_password(request.new_password)
        _save_auth_config_to_global(config)

        logging.info(f"用戶 {user_id} 密碼重置成功")
        return {"message": f"用戶 {user_id} 的密碼已重置"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"重置用戶密碼失敗: {e}")
        raise HTTPException(status_code=500, detail=f"重置用戶密碼失敗: {str(e)}")

@router.put("/{user_id}/groups")
async def update_user_groups(
    user_id: str,
    request: UpdateUserGroupsRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:users:manage"])) # 使用細粒度權限
):
    """更新用戶身分組（僅管理員）"""
    logging.info(f"管理員更新用戶 {user_id} 身分組為 {request.groups}")
    try:
        if not user_id or not isinstance(user_id, str) or len(user_id.strip()) == 0:
            raise HTTPException(status_code=400, detail="無效的用戶名")

        config = _load_auth_config_from_global()
        users = config.get("users", [])
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用戶 {user_id} 不存在")

        user = users[user_index]

        # 防止修改admin帳號
        if _is_admin_user(user):
            raise HTTPException(status_code=400, detail="不能修改admin帳號的權限")

        current_username = identity.get("sub", "")
        if current_username == user_id:
            raise HTTPException(status_code=400, detail="不能修改自己的身分組")

        # 驗證身分組是否存在（從 global_data 獲取）
        groups_config = global_data.AUTH_CONFIG.get("groups", {})
        invalid_groups = [group for group in request.groups if group not in groups_config]
        if invalid_groups:
            raise HTTPException(status_code=400, detail=f"無效的身分組: {invalid_groups}")

        user["groups"] = request.groups
        user.pop("roles", None)  # 移除角色設置，因為現在通過 groups 管理權限

        _save_auth_config_to_global(config)

        logging.info(f"用戶 {user_id} 身分組更新成功")
        return {"message": f"用戶 {user_id} 身分組已更新為 {request.groups}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新用戶身分組失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新用戶身分組失敗: {str(e)}")
