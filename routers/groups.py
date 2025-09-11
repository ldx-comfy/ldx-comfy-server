"""
身分組管理路由
提供管理員身分組管理功能
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
import global_data # 導入 global_data 以訪問 AUTH_FILE 和 AUTH_CONFIG

logger = logging.getLogger(__name__) # 添加這行

router = APIRouter(prefix="/api/v1/admin/groups", tags=["身分組管理"])


# ============================
# 模型定義
# ============================

class GroupInfo(BaseModel):
    """身分組信息"""
    id: str = Field(..., description="身分組ID")
    name: str = Field(..., description="身分組名稱")
    description: str = Field(..., description="身分組描述")
    permissions: List[str] = Field(..., description="權限列表")
    level: int = Field(..., description="權限等級")
    created_at: str = Field(..., description="創建時間")


class CreateGroupRequest(BaseModel):
    """創建身分組請求"""
    id: str = Field(..., description="身分組ID")
    name: str = Field(..., description="身分組名稱")
    description: str = Field(..., description="身分組描述")
    permissions: List[str] = Field(..., description="權限列表")
    level: int = Field(50, description="權限等級")


class UpdateGroupRequest(BaseModel):
    """更新身分組請求"""
    name: Optional[str] = Field(None, description="身分組名稱")
    description: Optional[str] = Field(None, description="身分組描述")
    permissions: Optional[List[str]] = Field(None, description="權限列表")
    level: Optional[int] = Field(None, description="權限等級")


# ============================
# 工具函數
# ============================

# 移除 _load_groups_config 和 _save_groups_config 函數，直接使用 global_data.AUTH_CONFIG
# 統一由 auth_config 中的 _save_auth_config 處理持久化

def _get_groups_data_from_global() -> Dict[str, Any]:
    """從 global_data.AUTH_CONFIG 獲取身分組數據"""
    if not global_data.AUTH_CONFIG:
        global_data.load_auth_config() # 嘗試重新加載
    return global_data.AUTH_CONFIG.get("groups", {})


def _get_system_permissions_from_global() -> Dict[str, str]:
    """從 global_data 獲取系統權限描述"""
    return global_data.SYSTEM_PERMISSIONS


def _save_auth_config_to_global(config: Dict[str, Any]) -> None:
    """保存 auth_config 到 global_data 並持久化"""
    try:
        # 直接更新 global_data 中的 AUTH_CONFIG
        # 先更新整個 AUTH_CONFIG，而不是只更新 groups 部分
        global_data.AUTH_CONFIG.update(config)
        # 通知 auth_config 模塊將其狀態持久化到文件
        auth_config._save_auth_config(global_data.AUTH_CONFIG)
        global_data.load_auth_config() # 重新加載確保全局變量最新
    except Exception as e:
        logging.error(f"保存認證配置失敗: {e}")
        raise HTTPException(status_code=500, detail="保存認證配置失敗")


def _find_group(config: Dict[str, Any], group_id: str) -> Optional[Dict[str, Any]]:
    """查找身分組在配置中的信息"""
    groups_config = config.get("groups", {})
    return groups_config.get(group_id)


def _is_valid_permission(permission: str, system_permissions: Dict[str, str]) -> bool:
    """驗證權限是否有效，支持通配符權限"""
    # 直接從 global_data.SYSTEM_PERMISSIONS 獲取
    # 這裡只需要匹配是否存在於定義的 SYSTEM_PERMISSIONS 中，或符合通配符模式
    if permission in system_permissions:
        return True
    
    # 通配符匹配 (例如: user:*)
    if permission.endswith(":*"):
        prefix = permission[:-2]  # 移除 ":*"
        for perm_id in system_permissions.keys():
            if perm_id.startswith(prefix + ":"): # 匹配前綴
                return True
    
    return False # 如果沒有找到任何匹配項，則認為無效


# ============================
# 路由
# ============================

@router.get("/", response_model=List[GroupInfo])
async def get_all_groups(identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:read"]))): # 使用細粒度權限
    """獲取所有身分組列表（僅管理員）"""
    logging.info("管理員獲取所有身分組列表")
    try:
        groups_config = _get_groups_data_from_global()
        
        group_list = []
        for group_id, group_data in groups_config.items():
            if isinstance(group_data, dict):
                # 確保必要的字段存在
                if "name" not in group_data:
                    group_data["name"] = group_id
                if "description" not in group_data:
                    group_data["description"] = ""
                if "permissions" not in group_data:
                    group_data["permissions"] = []
                if "level" not in group_data:
                    group_data["level"] = 0
                if "created_at" not in group_data:
                    group_data["created_at"] = datetime.now(timezone.utc).isoformat()

                group_info = GroupInfo(
                    id=group_id,
                    name=group_data["name"],
                    description=group_data["description"],
                    permissions=group_data["permissions"],
                    level=group_data["level"],
                    created_at=group_data["created_at"]
                )
                group_list.append(group_info)

        logging.info(f"成功獲取 {len(group_list)} 個身分組")
        return group_list

    except Exception as e:
        logging.error(f"獲取身分組列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取身分組列表失敗: {str(e)}")


@router.get("/{group_id}", response_model=GroupInfo)
async def get_group(
    group_id: str,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:read"])) # 使用細粒度權限
):
    """獲取指定身分組信息（僅管理員）"""
    logging.info(f"管理員獲取身分組 {group_id} 信息")
    try:
        groups_config = _get_groups_data_from_global()
        group_data = groups_config.get(group_id) # 直接從全局配置獲取
        
        if not group_data:
            raise HTTPException(status_code=404, detail=f"身分組 {group_id} 不存在")

        # 確保必要的字段存在
        if "name" not in group_data:
            group_data["name"] = group_id
        if "description" not in group_data:
            group_data["description"] = ""
        if "permissions" not in group_data:
            group_data["permissions"] = []
        if "level" not in group_data:
            group_data["level"] = 0
        if "created_at" not in group_data:
            group_data["created_at"] = datetime.now(timezone.utc).isoformat()

        group_info = GroupInfo(
            id=group_id,
            name=group_data["name"],
            description=group_data["description"],
            permissions=group_data["permissions"],
            level=group_data["level"],
            created_at=group_data["created_at"]
        )

        logging.info(f"成功獲取身分組 {group_id} 信息")
        return group_info

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"獲取身分組信息失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取身分組信息失敗: {str(e)}")


@router.post("/", response_model=GroupInfo)
async def create_group(
    request: CreateGroupRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:manage"])) # 使用細粒度權限
):
    """創建新身分組（僅管理員）"""
    logging.info(f"管理員創建新身分組: {request.id}")
    try:
        if not request.id or len(request.id.strip()) == 0:
            raise HTTPException(status_code=400, detail="身分組ID不能為空")

        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取整個 auth config
        groups_config = config.get("groups", {})
        
        if request.id in groups_config:
            raise HTTPException(status_code=400, detail=f"身分組ID '{request.id}' 已存在")
        
        system_permissions = _get_system_permissions_from_global() # 從 global_data 獲取系統權限
        invalid_permissions = [perm for perm in request.permissions if not _is_valid_permission(perm, system_permissions)]
        if invalid_permissions:
            raise HTTPException(status_code=400, detail=f"無效的權限: {invalid_permissions}")

        new_group = {
            "name": request.name,
            "description": request.description,
            "permissions": request.permissions,
            "level": request.level,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        groups_config[request.id] = new_group
        config["groups"] = groups_config # 更新整個 config 的 groups 部分
        
        _save_auth_config_to_global(config) # 保存整個 config

        group_info = GroupInfo(
            id=request.id,
            name=request.name,
            description=request.description,
            permissions=request.permissions,
            level=request.level,
            created_at=new_group["created_at"]
        )

        logging.info(f"身分組 {request.id} 創建成功")
        return group_info

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"創建身分組失敗: {e}")
        raise HTTPException(status_code=500, detail=f"創建身分組失敗: {str(e)}")


@router.put("/{group_id}", response_model=GroupInfo)
async def update_group(
    group_id: str,
    request: UpdateGroupRequest,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:manage"])) # 使用細粒度權限
):
    """更新身分組（僅管理員）"""
    logging.info(f"管理員更新身分組: {group_id}")
    try:
        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取整個 auth config
        groups_config = config.get("groups", {})
        
        if group_id not in groups_config:
            raise HTTPException(status_code=404, detail=f"身分組 {group_id} 不存在")
        
        group_data = groups_config[group_id]
        
        if request.name is not None:
            group_data["name"] = request.name
        if request.description is not None:
            group_data["description"] = request.description
        if request.permissions is not None:
            system_permissions = _get_system_permissions_from_global() # 從 global_data 獲取系統權限
            invalid_permissions = [perm for perm in request.permissions if not _is_valid_permission(perm, system_permissions)]
            if invalid_permissions:
                raise HTTPException(status_code=400, detail=f"無效的權限: {invalid_permissions}")
            group_data["permissions"] = request.permissions
        if request.level is not None:
            group_data["level"] = request.level
 
        groups_config[group_id] = group_data
        config["groups"] = groups_config # 更新整個 config 的 groups 部分
        _save_auth_config_to_global(config) # 保存整個 config
 
        group_info = GroupInfo(
            id=group_id,
            name=group_data["name"],
            description=group_data["description"],
            permissions=group_data["permissions"],
            level=group_data["level"],
            created_at=group_data["created_at"] # created_at 應在創建時設置，更新時不變
        )
 
        logging.info(f"身分組 {group_id} 更新成功")
        return group_info
 
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"更新身分組失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新身分組失敗: {str(e)}")


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:manage"])) # 使用細粒度權限
):
    """刪除身分組（僅管理員）"""
    logging.info(f"管理員刪除身分組: {group_id}")
    try:
        config = global_data.AUTH_CONFIG # 直接從 global_data 獲取整個 auth config
        groups_config = config.get("groups", {})
        
        if group_id not in groups_config:
            raise HTTPException(status_code=404, detail=f"身分組 {group_id} 不存在")
        
        # 不允許刪除 admin 和 user 默認組
        if group_id in ["admin", "user"]:
            raise HTTPException(status_code=400, detail=f"不允許刪除默認身分組 '{group_id}'")

        del groups_config[group_id]
        config["groups"] = groups_config # 更新整個 config 的 groups 部分
        
        _save_auth_config_to_global(config) # 保存整個 config
 
        logging.info(f"身分組 {group_id} 刪除成功")
        return {"message": f"身分組 {group_id} 已刪除"}
 
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"刪除身分組失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除身分組失敗: {str(e)}")


@router.get("/permissions/list")
async def get_system_permissions(identity: Dict[str, Any] = Depends(require_permissions(["admin:groups:read"]))): # 使用細粒度權限
    """獲取系統所有權限列表（僅管理員）"""
    logging.info("管理員獲取系統權限列表")
    try:
        system_permissions = _get_system_permissions_from_global() # 直接從 global_data 獲取
        
        permissions_list = [
            {"id": perm_id, "name": perm_name}
            for perm_id, perm_name in system_permissions.items()
        ]
        
        logging.info(f"成功獲取 {len(permissions_list)} 個系統權限")
        return permissions_list

    except Exception as e:
        logging.error(f"獲取系統權限列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取系統權限列表失敗: {str(e)}")


@router.get("/my/permissions")
async def get_my_permissions(identity: Dict[str, Any] = Depends(get_current_identity)):
    """獲取當前用戶的權限列表 (無需管理員權限)"""
    logging.info(f"用戶 {identity.get('sub')} 獲取權限列表")
    # 這裡直接利用身份驗證結果中的 permissions 字段，該字段已在 _issue_token 中由 resolve_effective_roles 填充
    user_permissions_from_claims = identity.get("permissions", [])
    if not isinstance(user_permissions_from_claims, list):
        user_permissions_from_claims = []
    
    # 從 global_data 獲取系統權限描述，以便提供友好的名稱
    system_permissions_desc = global_data.SYSTEM_PERMISSIONS

    permissions_list = []
    for perm_id in user_permissions_from_claims:
        permissions_list.append({
            "id": perm_id,
            "name": system_permissions_desc.get(perm_id, perm_id) # 使用全局的 SYSTEM_PERMISSIONS
        })
    
    logger.warning(f"用戶 {identity.get('sub')} 的實際權限列表 (WARNING): {permissions_list}") # 將 log 等級提高到 WARNING
    logger.info(f"成功獲取用戶 {identity.get('sub')} 的權限列表，共 {len(permissions_list)} 個權限")
    return permissions_list