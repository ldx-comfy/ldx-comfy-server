from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from routers import include_routers
from comfy.plugins import plugin_manager
from logging_config import get_colorful_logger
from contextlib import asynccontextmanager
from auth.config import _init_config
import httpx
import json
import time
import global_data

config_manager = global_data.config_manager

# 配置彩色日志
logger = get_colorful_logger(__name__)
print("Starting application...")


async def check_comfyui_connectivity_on_startup(server_address: str):
    """启动时检查ComfyUI连通性"""
    logger.info(f"正在检查ComfyUI后端连通性 ({server_address})...")

    try:
        # 使用GET /system_stats端点检查连通性
        url = f"http://{server_address}/system_stats"

        start_time = time.time()
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response_time = (time.time() - start_time) * 1000
            response_data = response.json()

            logger.info(f"✅ ComfyUI后端连接正常 (响应时间: {response_time:.2f}ms)")

    except httpx.HTTPStatusError as e:
        logger.warning(f"⚠️  ComfyUI后端连接失败: HTTP {e.response.status_code} - {e.response.reason_phrase}")
        logger.warning("   请检查ComfyUI服务是否正在运行")
    except httpx.RequestError as e:
        logger.warning(f"⚠️  ComfyUI后端连接失败: {str(e)}")
        logger.warning("   请检查网络连接和ComfyUI服务状态")
    except Exception as e:
        logger.warning(f"⚠️  ComfyUI后端连接检查出错: {str(e)}")
        logger.warning("   请检查ComfyUI服务配置")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    # 初始化认证配置
    logger.info("正在初始化认证系统...")
    _init_config()
    logger.info("认证系统初始化完成")

    # 启动事件
    logger.info("正在初始化插件系统...")
    plugin_manager.discover_and_register_plugins()

    # 初始化插件配置
    # 取消超时（ws_timeout/http_timeout 设为 0 或 None 表示无限等待）
    plugin_config = {
        'server_address': '101.34.36.44:6889',
        'output_dir': global_data.COMFY_OUTPUT_DIR,
        'ws_timeout': 0,
        'http_timeout': 0,
    }
    plugin_manager.initialize_plugins(plugin_config)
    logger.info("插件系统初始化完成")

    # 检查ComfyUI后端连通性
    await check_comfyui_connectivity_on_startup(plugin_config['server_address'])

    yield

    # 关闭事件
    logger.info("正在清理插件系统...")
    plugin_manager.cleanup_plugins()
    logger.info("插件系统清理完成")

# 创建FastAPI应用
app = include_routers(FastAPI(lifespan=lifespan))

# 中间件：记录请求和响应信息
async def log_requests(request: Request, call_next):
    # 记录请求开始时间
    start_time = time.time()
    
    # 记录请求信息
    logger.info(f"Request: {request.method} {request.url}")
    
    # 调用下一个中间件或路由处理函数
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    
    # 记录响应信息
    logger.info(f"Response: {response.status_code} (处理时间: {process_time:.2f}s)")
    
    return response

# 注册中间件
app.add_middleware(BaseHTTPMiddleware, dispatch=log_requests)

# 注册權限驗證中間件
from auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

# CORS 配置：允许前端开发服务器跨域访问（Astro dev: http://localhost:4321）
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(config_manager.get("cors", ["*"])), # type: ignore 静态检查无法识别
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 静态文件: 暴露生成图片目录以供前端直接访问
# 例如: http://127.0.0.1:1145/comfy_out_image/ComfyUI_00002_.png
app.mount("/comfy_out_image", StaticFiles(directory=global_data.COMFY_OUTPUT_DIR), name="comfy_out_image")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1145,reload=True,workers=1)
