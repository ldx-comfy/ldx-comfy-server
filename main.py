from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from routers import include_routers
from comfy.plugins import plugin_manager
from logging_config import get_colorful_logger
from contextlib import asynccontextmanager
import httpx
import json
import time
import global_data

config_manager = global_data.config_manager

# 配置彩色日志
logger = get_colorful_logger(__name__)
print("Starting application...")


async def check_comfyui_connectivity_on_startup(server_address: str):
    """啟動時檢查ComfyUI連通性"""
    logger.info(f"正在檢查ComfyUI後端連通性 ({server_address})...")

    try:
        # 使用GET /system_stats端點檢查連通性
        url = f"http://{server_address}/system_stats"

        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response_time = (time.time() - start_time) * 1000
            response_data = response.json()

            logger.info(f"✅ ComfyUI後端連接正常 (響應時間: {response_time:.2f}ms)")

    except httpx.HTTPStatusError as e:
        logger.warning(f"⚠️  ComfyUI後端連接失敗: HTTP {e.response.status_code} - {e.response.reason_phrase}")
        logger.warning("   請檢查ComfyUI服務是否正在運行")
    except httpx.RequestError as e:
        logger.warning(f"⚠️  ComfyUI後端連接失敗: {str(e)}")
        logger.warning("   請檢查網絡連接和ComfyUI服務狀態")
    except Exception as e:
        logger.warning(f"⚠️  ComfyUI後端連接檢查出錯: {str(e)}")
        logger.warning("   請檢查ComfyUI服務配置")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用生命週期管理器"""
    # 認證配置已通過 global_data 在模塊加載時初始化
    logger.info("認證系統已初始化")

    # 啟動事件
    logger.info("正在初始化插件系統...")
    plugin_manager.discover_and_register_plugins()

    # 初始化插件配置
    # 取消超時（ws_timeout/http_timeout 設為 0 或 None 表示無限等待）
    plugin_config = {
        'server_address': '124.222.207.240:6889',
        'output_dir': global_data.COMFY_OUTPUT_DIR,
        'ws_timeout': 0,
        'http_timeout': 0,
    }
    plugin_manager.initialize_plugins(plugin_config)
    logger.info("插件系統初始化完成")

    # 檢查ComfyUI後端連通性
    await check_comfyui_connectivity_on_startup(plugin_config['server_address'])

    yield

    # 關閉事件
    logger.info("正在清理插件系統...")
    plugin_manager.cleanup_plugins()
    logger.info("插件系統清理完成")

# 創建FastAPI應用
app = include_routers(FastAPI(lifespan=lifespan))

# 中間件：記錄請求和響應信息
async def log_requests(request: Request, call_next):
    # 記錄請求開始時間
    start_time = time.time()
    
    # 記錄請求信息
    logger.info(f"Request: {request.method} {request.url}")
    
    # 調用下一個中間件或路由處理函數
    response = await call_next(request)
    
    # 計算處理時間
    process_time = time.time() - start_time
    
    # 記錄響應信息
    logger.info(f"Response: {response.status_code} (處理時間: {process_time:.2f}s)")
    
    return response

# 註冊中間件
app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)

# 註冊權限驗證中間件
from auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

# CORS 配置：允許前端開發服務器跨域訪問（Astro dev: http://localhost:4321）
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config_manager.get("cors", ["*"])), # type: ignore 靜態檢查無法識別
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 靜態文件: 暴露生成圖片目錄以供前端直接訪問
# 例如: http://127.0.0.1:1145/comfy_out_image/ComfyUI_00002_.png
app.mount("/comfy_out_image", StaticFiles(directory=global_data.COMFY_OUTPUT_DIR), name="comfy_out_image")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1145,reload=True,workers=1)
