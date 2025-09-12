"""
設置路由
- 提供獲取和更新ComfyUI服務器地址的API端點
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth.permissions import require_permissions
import global_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/settings", tags=["設置"])

# ============================
# 模型定義
# ============================

class ComfyServerAddressRequest(BaseModel):
    """ComfyUI服務器地址請求"""
    address: str = Field(..., description="ComfyUI服務器地址")

class ComfyServerAddressResponse(BaseModel):
    """ComfyUI服務器地址響應"""
    address: str = Field(..., description="ComfyUI服務器地址")

# ============================
# 路由
# ============================

@router.get("/comfy-server-address", response_model=ComfyServerAddressResponse)
async def get_comfy_server_address(
    request: Request
):
    """
    獲取ComfyUI服務器地址（需要admin:settings:manage權限）
    """
    logger.info("管理員獲取ComfyUI服務器地址")
    try:
        address = global_data.config_manager.get_comfy_server_address()
        return ComfyServerAddressResponse(address=address)
    except Exception as e:
        logger.error(f"獲取ComfyUI服務器地址失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取ComfyUI服務器地址失敗: {str(e)}")

@router.put("/comfy-server-address", response_model=ComfyServerAddressResponse)
async def update_comfy_server_address(
    request: ComfyServerAddressRequest,
    req: Request
):
    """
    更新ComfyUI服務器地址（需要admin:settings:manage權限）
    """
    logger.info(f"管理員更新ComfyUI服務器地址為: {request.address}")
    try:
        global_data.config_manager.set_comfy_server_address(request.address)
        return ComfyServerAddressResponse(address=request.address)
    except Exception as e:
        logger.error(f"更新ComfyUI服務器地址失敗: {e}")
        raise HTTPException(status_code=500, detail=f"更新ComfyUI服務器地址失敗: {str(e)}")