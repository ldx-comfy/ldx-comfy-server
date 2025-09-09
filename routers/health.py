"""
健康检查路由
"""
import httpx
import time
from typing import Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from comfy.plugins import plugin_manager
from comfy.plugins.workflow_executors import ComfyUIWorkflowExecutor
router = APIRouter(prefix="/api/v1/health", tags=["健康检查"])


class HealthStatus(BaseModel):
    """健康状态响应模型"""
    status: str  # "healthy" 或 "unhealthy"
    timestamp: str
    services: Dict[str, Any]
    message: str = ""


class ComfyUIStatus(BaseModel):
    """ComfyUI状态模型"""
    status: str  # "connected" 或 "disconnected"
    response_time_ms: float = 0.0
    error: str = ""


@router.get("/", response_model=HealthStatus)
async def get_system_health():
    """获取系统整体健康状态"""
    timestamp = datetime.utcnow().isoformat()

    # 检查ComfyUI后端状态
    comfyui_status = await check_comfyui_health()

    # 确定整体状态
    overall_status = "healthy" if comfyui_status.status == "connected" else "unhealthy"

    services = {
        "comfyui_backend": comfyui_status.dict()
    }

    message = "系统运行正常" if overall_status == "healthy" else "ComfyUI后端连接异常"

    return HealthStatus(
        status=overall_status,
        timestamp=timestamp,
        services=services,
        message=message
    )


@router.get("/comfyui", response_model=ComfyUIStatus)
async def get_comfyui_health():
    """获取ComfyUI后端健康状态"""
    try:
        return await check_comfyui_health()
    except ValueError as e:
        # 如果无法获取服务器地址，返回错误状态
        return ComfyUIStatus(
            status="error",
            response_time_ms=0.0,
            error=str(e)
        )
    except Exception as e:
        # 处理其他异常
        return ComfyUIStatus(
            status="error",
            response_time_ms=0.0,
            error=f"健康检查失败: {str(e)}"
        )


async def check_comfyui_health() -> ComfyUIStatus:
    """检查ComfyUI后端健康状态"""
    # 从插件管理器获取服务器地址
    try:


        executor = plugin_manager.get_workflow_executor()
        # 类型检查：确保是ComfyUIWorkflowExecutor实例
        if isinstance(executor, ComfyUIWorkflowExecutor):
            server_address = executor.server_address
        else:
            # 如果不是ComfyUIWorkflowExecutor，抛出错误
            raise ValueError("未找到ComfyUI工作流执行器")
    except Exception as e:
        # 如果无法获取，抛出错误
        raise ValueError(f"无法获取ComfyUI服务器地址: {str(e)}")

    start_time = time.time()

    try:
        # 使用GET /system_stats端点检查ComfyUI连通性
        url = f"http://{server_address}/system_stats"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response_time = (time.time() - start_time) * 1000

            return ComfyUIStatus(
                status="connected",
                response_time_ms=round(response_time, 2),
                error=""
            )

    except httpx.HTTPStatusError as e:
        response_time = (time.time() - start_time) * 1000
        return ComfyUIStatus(
            status="disconnected",
            response_time_ms=round(response_time, 2),
            error=f"HTTP {e.response.status_code}: {e.response.reason_phrase}"
        )

    except httpx.RequestError as e:
        response_time = (time.time() - start_time) * 1000
        return ComfyUIStatus(
            status="disconnected",
            response_time_ms=round(response_time, 2),
            error=f"连接失败: {str(e)}"
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return ComfyUIStatus(
            status="disconnected",
            response_time_ms=round(response_time, 2),
            error=f"未知错误: {str(e)}"
        )

