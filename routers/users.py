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
from routers.auth import get_current_identity, require_roles

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
    role: str = Field("user", description="角色")


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    new_password: str = Field(..., description="新密码")


# ============================
# 工具函数
# ============================

def _get_auth_config_path() -> str:
    """获取认证配置文件路径"""
    return auth_config._effective_config_path()


def _load_auth_config() -> Dict[str, Any]:
    """加载认证配置"""
    path = _get_auth_config_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加载认证配置失败: {e}")
        raise HTTPException(status_code=500, detail="加载认证配置失败")


def _save_auth_config(config: Dict[str, Any]) -> None:
    """保存认证配置"""
    path = _get_auth_config_path()
    try:
        # 创建备份
        if os.path.exists(path):
            backup_path = path + ".bak"
            import shutil
            shutil.copy2(path, backup_path)

        # 保存新配置
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存认证配置失败: {e}")
        raise HTTPException(status_code=500, detail="保存认证配置失败")


def _find_user_index(config: Dict[str, Any], user_id: str) -> int:
    """查找用户在配置中的索引"""
    users = config.get("users", [])
    for i, user in enumerate(users):
        if isinstance(user, dict) and user.get("username", "") == user_id:
            return i
    return -1


def _get_user_role_and_groups(user: Dict[str, Any]) -> tuple[str, List[str]]:
    """获取用户的角色和组"""
    roles, groups = auth_config.resolve_effective_roles(user)
    # 取第一个角色作为主要角色，如果没有则默认为 'user'
    role = roles[0] if roles else 'user'
    return role, groups


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
async def get_all_users(identity: Dict[str, Any] = Depends(require_roles(["admin"]))):
    """获取所有用户列表（仅管理员）"""
    logging.info("管理员获取所有用户列表")
    try:
        config = _load_auth_config()
        users = config.get("users", [])

        user_list = []
        for user in users:
            if isinstance(user, dict):
                username = user.get("username", "")
                if not username:
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

                role, _ = _get_user_role_and_groups(user)
                status = _get_user_status(user)
                created_at = _get_user_created_at(user)
                last_login = _get_user_last_login(user)
                generation_count = _get_user_generation_count(user)

                user_info = UserInfo(
                    id=username,
                    username=username,
                    email=user.get("email", f"{username}@example.com"),
                    role=role,
                    status=status,
                    created_at=created_at,
                    last_login=last_login,
                    generation_count=generation_count
                )
                user_list.append(user_info)

        # 保存更新后的配置（添加了缺失的字段）
        _save_auth_config(config)

        logging.info(f"成功获取 {len(user_list)} 个用户")
        return user_list

    except Exception as e:
        logging.error(f"获取用户列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户列表失败: {str(e)}")


@router.put("/{user_id}/role")
async def update_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """更新用户角色（仅管理员）"""
    logging.info(f"管理员更新用户 {user_id} 角色为 {request.role}")
    try:
        # 验证角色
        valid_roles = ["admin", "moderator", "user"]
        if request.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效的角色: {request.role}")

        config = _load_auth_config()
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

        user = config["users"][user_index]

        # 防止管理员给自己降级
        current_user = identity.get("sub", "")
        if current_user == user_id and request.role != "admin":
            raise HTTPException(status_code=400, detail="不能修改自己的管理员权限")

        # 更新角色
        if request.role == "admin":
            user["roles"] = ["admin"]
            user.pop("groups", None)  # 移除组设置
        elif request.role == "moderator":
            user["roles"] = ["moderator"]
            user.pop("groups", None)
        else:  # user
            user["roles"] = ["user"]
            user.pop("groups", None)

        _save_auth_config(config)

        logging.info(f"用户 {user_id} 角色更新成功")
        return {"message": f"用户 {user_id} 角色已更新为 {request.role}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新用户角色失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新用户角色失败: {str(e)}")


@router.put("/{user_id}/status")
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """更新用户状态（仅管理员）"""
    logging.info(f"管理员更新用户 {user_id} 状态为 {request.status}")
    try:
        # 验证状态
        valid_statuses = ["active", "inactive", "banned"]
        if request.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"无效的状态: {request.status}")

        config = _load_auth_config()
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

        user = config["users"][user_index]

        # 防止管理员禁用自己
        current_user = identity.get("sub", "")
        if current_user == user_id and request.status == "banned":
            raise HTTPException(status_code=400, detail="不能禁用自己的账户")

        # 更新状态
        user["status"] = request.status

        _save_auth_config(config)

        logging.info(f"用户 {user_id} 状态更新成功")
        return {"message": f"用户 {user_id} 状态已更新为 {request.status}"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新用户状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新用户状态失败: {str(e)}")


@router.post("/", response_model=UserInfo)
async def create_user(
    request: CreateUserRequest,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """创建新用户（仅管理员）"""
    logging.info(f"管理员创建新用户: {request.username}")
    try:
        # 验证用户名
        if not request.username or len(request.username.strip()) == 0:
            raise HTTPException(status_code=400, detail="用户名不能为空")

        # 验证密码
        if not request.password or len(request.password) < 6:
            raise HTTPException(status_code=400, detail="密码长度至少为6位")

        # 验证角色
        valid_roles = ["admin", "moderator", "user"]
        if request.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"无效的角色: {request.role}")

        config = _load_auth_config()
        users = config.get("users", [])

        # 检查用户名是否已存在
        for user in users:
            if isinstance(user, dict) and user.get("username") == request.username:
                raise HTTPException(status_code=400, detail=f"用户名 '{request.username}' 已存在")

        # 创建新用户
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

        # 设置角色
        if request.role == "admin":
            new_user["roles"] = ["admin"]
        elif request.role == "moderator":
            new_user["roles"] = ["moderator"]
        else:  # user
            new_user["roles"] = ["user"]

        users.append(new_user)
        config["users"] = users
        _save_auth_config(config)

        # 返回用户信息
        role, _ = _get_user_role_and_groups(new_user)
        user_info = UserInfo(
            id=request.username,
            username=request.username,
            email=new_user["email"],
            role=role,
            status=new_user["status"],
            created_at=new_user["created_at"],
            last_login=new_user["last_login"],
            generation_count=new_user["generation_count"]
        )

        logging.info(f"用户 {request.username} 创建成功")
        return user_info

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"创建用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """删除用户（仅管理员）"""
    logging.info(f"管理员删除用户: {user_id}")
    try:
        config = _load_auth_config()
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

        user = config["users"][user_index]

        # 防止删除自己
        current_user = identity.get("sub", "")
        if current_user == user_id:
            raise HTTPException(status_code=400, detail="不能删除自己的账户")

        # 防止删除超级管理员（如果有的话）
        if user.get("username") == "admin" and user.get("roles") == ["admin"]:
            raise HTTPException(status_code=400, detail="不能删除超级管理员账户")

        # 删除用户
        config["users"].pop(user_index)
        _save_auth_config(config)

        logging.info(f"用户 {user_id} 删除成功")
        return {"message": f"用户 {user_id} 已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"删除用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除用户失败: {str(e)}")


@router.put("/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    request: ResetPasswordRequest,
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """重置用户密码（仅管理员）"""
    logging.info(f"管理员重置用户 {user_id} 密码")
    try:
        # 验证新密码
        if not request.new_password or len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="密码长度至少为6位")

        config = _load_auth_config()
        user_index = _find_user_index(config, user_id)

        if user_index == -1:
            raise HTTPException(status_code=404, detail=f"用户 {user_id} 不存在")

        user = config["users"][user_index]

        # 更新密码
        user["password_hash"] = auth_config.hash_password(request.new_password)

        _save_auth_config(config)

        logging.info(f"用户 {user_id} 密码重置成功")
        return {"message": f"用户 {user_id} 的密码已重置"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"重置用户密码失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置用户密码失败: {str(e)}")