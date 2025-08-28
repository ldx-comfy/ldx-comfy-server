from fastapi import FastAPI
from routers import include_routers
from comfy.plugins import plugin_manager
from comfy.logging_config import get_colorful_logger
from contextlib import asynccontextmanager
import urllib.request
import urllib.error
import json
import time

# 配置彩色日志
logger = get_colorful_logger(__name__)


async def check_comfyui_connectivity_on_startup(server_address: str):
    """启动时检查ComfyUI连通性"""
    logger.info(f"正在检查ComfyUI后端连通性 ({server_address})...")

    try:
        # 使用GET /system_stats端点检查连通性
        url = f"http://{server_address}/system_stats"
        req = urllib.request.Request(url, method='GET')

        start_time = time.time()
        with urllib.request.urlopen(req, timeout=10) as response:
            response_time = (time.time() - start_time) * 1000
            response_data = json.loads(response.read().decode('utf-8'))

            logger.info(f"✅ ComfyUI后端连接正常 (响应时间: {response_time:.2f}ms)")

    except urllib.error.HTTPError as e:
        logger.warning(f"⚠️  ComfyUI后端连接失败: HTTP {e.code} - {e.reason}")
        logger.warning("   请检查ComfyUI服务是否正在运行")
    except urllib.error.URLError as e:
        logger.warning(f"⚠️  ComfyUI后端连接失败: {e.reason}")
        logger.warning("   请检查网络连接和ComfyUI服务状态")
    except Exception as e:
        logger.warning(f"⚠️  ComfyUI后端连接检查出错: {str(e)}")
        logger.warning("   请检查ComfyUI服务配置")


# 生命周期管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    # 启动事件
    logger.info("正在初始化插件系统...")
    plugin_manager.discover_and_register_plugins()

    # 初始化插件配置
    config = {
        'server_address': '118.195.246.241:6889',
        'output_dir': 'comfy_out_image'
    }
    plugin_manager.initialize_plugins(config)
    logger.info("插件系统初始化完成")

    # 检查ComfyUI后端连通性
    await check_comfyui_connectivity_on_startup(config['server_address'])

    yield

    # 关闭事件
    logger.info("正在清理插件系统...")
    plugin_manager.cleanup_plugins()
    logger.info("插件系统清理完成")

# 创建FastAPI应用
app = include_routers(FastAPI(lifespan=lifespan))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,reload=True,workers=1)
