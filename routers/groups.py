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
from routers.auth import get_current_identity, require_roles
from global_data import GROUPS_FILE

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

def _load_groups_config() -> Dict[str, Any]:
    """加載身分組配置"""
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"加載身分組配置失敗: {e}")
        raise HTTPException(status_code=500, detail="加載身分組配置失敗")


def _save_groups_config(config: Dict[str, Any]) -> None:
    """保存身分組配置"""
    try:
        # 創建備份
        if os.path.exists(GROUPS_FILE):
            backup_path = str(GROUPS_FILE) + ".bak"
            import shutil
            shutil.copy2(GROUPS_FILE, backup_path)

        # 保存新配置
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存身分組配置失敗: {e}")
        raise HTTPException(status_code=500, detail="保存身分組配置失敗")


def _find_group(config: Dict[str, Any], group_id: str) -> Optional[Dict[str, Any]]:
    """查找身分組在配置中的信息"""
    groups_config = config.get("groups", {})
    return groups_config.get(group_id)


# ============================
# 路由
# ============================

@router.get("/", response_model=List[GroupInfo])
async def get_all_groups(identity: Dict[str, Any] = Depends(require_roles(["admin"]))):
    """獲取所有身分組列表（僅管理員）"""
    logging.info("管理員獲取所有身分組列表")
    try:
        config = _load_groups_config()
        groups_config = config.get("groups", {})
        
        # 獲取系統權限定義
        system_permissions = config.get("system_permissions", {})

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
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """獲取指定身分組信息（僅管理員）"""
    logging.info(f"管理員獲取身分組 {group_id} 信息")
    try:
        config = _load_groups_config()
        group_data = _find_group(config, group_id)
        
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
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """創建新身分組（僅管理員）"""
    logging.info(f"管理員創建新身分組: {request.id}")
    try:
        # 驗證身分組ID
        if not request.id or len(request.id.strip()) == 0:
            raise HTTPException(status_code=400, detail="身分組ID不能為空")

        config = _load_groups_config()
        groups_config = config.get("groups", {})
        
        # 檢查身分組ID是否已存在
        if request.id in groups_config:
            raise HTTPException(status_code=400, detail=f"身分組ID '{request.id}' 已存在")
        
        # 驗證權限
        system_permissions = config.get("system_permissions", {})
        invalid_permissions = [perm for perm in request.permissions if perm not in system_permissions]
        if invalid_permissions:
            raise HTTPException(status_code=400, detail=f"無效的權限: {invalid_permissions}")

        # 創建新身分組
        new_group = {
            "name": request.name,
            "description": request.description,
            "permissions": request.permissions,
            "level": request.level,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        groups_config[request.id] = new_group
        config["groups"] = groups_config
        
        _save_groups_config(config)

        # 返回身分組信息
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
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """更新身分組（僅管理員）"""
    logging.info(f"管理員更新身分組: {group_id}")
    try:
        config = _load_groups_config()
        groups_config = config.get("groups", {})
        
        # 檢查身分組是否存在
        if group_id not in groups_config:
            raise HTTPException(status_code=404, detail=f"身分組 {group_id} 不存在")
        
        group_data = groups_config[group_id]
        
        # 更新字段
        if request.name is not None:
            group_data["name"] = request.name
        if request.description is not None:
            group_data["description"] = request.description
        if request.permissions is not None:
            # 驗證權限
            system_permissions = config.get("system_permissions", {})
            invalid_permissions = [perm for perm in request.permissions if perm not in system_permissions]
            if invalid_permissions:
                raise HTTPException(status_code=400, detail=f"無效的權限: {invalid_permissions}")
            group_data["permissions"] = request.permissions
        if request.level is not None:
            group_data["level"] = request.level

        groups_config[group_id] = group_data
        config["groups"] = groups_config
        _save_groups_config(config)

        # 返回更新後的身分組信息
        group_info = GroupInfo(
            id=group_id,
            name=group_data["name"],
            description=group_data["description"],
            permissions=group_data["permissions"],
            level=group_data["level"],
            created_at=group_data["created_at"]
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
    identity: Dict[str, Any] = Depends(require_roles(["admin"]))
):
    """刪除身分組（僅管理員）"""
    logging.info(f"管理員刪除身分組: {group_id}")
    try:
        config = _load_groups_config()
        groups_config = config.get("groups", {})
        
        # 檢查身分組是否存在
        if group_id not in groups_config:
            raise HTTPException(status_code=404, detail=f"身分組 {group_id} 不存在")
        
        # 刪除身分組
        del groups_config[group_id]
        config["groups"] = groups_config
        
        _save_groups_config(config)

        logging.info(f"身分組 {group_id} 刪除成功")
        return {"message": f"身分組 {group_id} 已刪除"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"刪除身分組失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除身分組失敗: {str(e)}")


@router.get("/permissions/list")
async def get_system_permissions(identity: Dict[str, Any] = Depends(require_roles(["admin"]))):
    """獲取系統所有權限列表（僅管理員）"""
    logging.info("管理員獲取系統權限列表")
    try:
        config = _load_groups_config()
        system_permissions = config.get("system_permissions", {})
        
        # 轉換為列表格式
        permissions_list = [
            {"id": perm_id, "name": perm_name}
            for perm_id, perm_name in system_permissions.items()
        ]
        
        logging.info(f"成功獲取 {len(permissions_list)} 個系統權限")
        return permissions_list

    except Exception as e:
        logging.error(f"獲取系統權限列表失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取系統權限列表失敗: {str(e)}")